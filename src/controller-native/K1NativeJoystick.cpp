// Feed XInput into KOTOR's retained native joystick pipeline.
//
// Every address and structure offset here was measured against
// swkotor.exe 1.03, and the reasoning is recorded in
// `reverse-engineering/retained-xbox-gui-events.md`. The short version:
//
//   CExoRawInputInternal::GetJoystickBuffer  polls a DIJOYSTATE and synthesises
//   DIDEVICEOBJECTDATA records from it, edge-triggered. GetEvents matches each
//   record against the descriptions registered for that (input class, device),
//   comparing a control code resolved through a table at +0x164 against the
//   record's dwOfs. A match stores the value on the description, and PollInput
//   returns it as a float.
//
// Nothing in that chain was removed. Only two things are missing: the joystick
// device count is a hardcoded zero, and no description names a joystick
// control. This file supplies both, then reads the result back through the
// engine's own PollInput.

#include "K1NativeJoystick.h"

#include <windows.h>
#include <xinput.h>

#include <cmath>
#include <cstdint>
#include <cstring>

namespace {

// ---------------------------------------------------------------- engine ABI

constexpr std::uintptr_t K1_CREATE_NEW_EVENT   = 0x005E0E20;  // CExoInputInternal
constexpr std::uintptr_t K1_ADD_EVENT          = 0x005E0FA0;  // CExoInputInternal
constexpr std::uintptr_t K1_POLL_INPUT         = 0x005E23C0;  // PollInput_2
constexpr std::uintptr_t K1_OPERATOR_NEW       = 0x006FA7E6;
constexpr std::uintptr_t K1_OPERATOR_DELETE    = 0x006FA390;
constexpr std::uintptr_t K1_VECTOR_NORMALIZE   = 0x004AB130;

// GetMinUseable returns this float for a joystick axis, and ScaledValue treats
// it as a deadzone: 8191.75 of 32767 is exactly a quarter of full deflection,
// which is far too much for a modern thumbstick. Lowered at startup so the
// engine imposes none, and a radial deadzone is applied here instead -- see
// K1_STICK_DEADZONE. Doing both would stack two deadzones.
constexpr std::uintptr_t K1_JOY_MIN_USEABLE     = 0x0074D708;

// CExoInputInternal offsets.
constexpr std::size_t K1_INPUT_DEVICE_COUNT    = 0x158;  // keyboard + mouse + pads
constexpr std::size_t K1_INPUT_RAW             = 0x140;  // CExoRawInputInternal*

// The accumulated mouse delta. UpdateCamera reads both through GetMouseDelta,
// and feeds the X component -- scaled by the mouse sensitivity setting and by
// the invert flag at 0x007A22A4 -- into CSWCModule::TiltCamera, which rotates
// the camera. Writing here is how the right stick reaches the camera at all:
// event 0x11C, the only other camera input, is a keyboard two-button axis on
// DIK_A/DIK_D and cannot take a joystick description.
constexpr std::size_t K1_MOUSE_DELTA_X          = 0x3A0;
constexpr std::size_t K1_MOUSE_DELTA_Y          = 0x3A4;

// Control slots, indices into the +0x164 control-code table. Populated by the
// engine's own constructor on every launch, joystick entries included.
constexpr int K1_SLOT_JOY_X = 0x6E;   // -> DIJOFS_X
constexpr int K1_SLOT_JOY_Y = 0x6F;   // -> DIJOFS_Y
constexpr int K1_SLOT_NONE  = 0x84;   // the "no control" sentinel

// Device indices. -1 is "any", 0 keyboard, 1 mouse, joysticks upward from 2.
constexpr int K1_DEVICE_JOYSTICK = 2;

// Input classes, matching keymap.2da's IC* columns.
constexpr int K1_CLASS_PC     = 0;   // gameplay
constexpr int K1_CLASS_PCGUI  = 2;   // menus

// Description types. Type 0 is the single-control analog path: PollInput
// returns the stored raw value as a float, unscaled. Type 3 would apply the
// engine's own normalisation, but only once ScaleEvent has configured
// desc+0x20, so type 0 plus our own curve is both simpler and gives us the
// radial deadzone the engine cannot express.
constexpr int K1_DESC_ANALOG = 0;

// Buttons are digital. IsDigital already reports joystick codes 0x30..0x4F as
// digital, and the type 1 store path writes dwData straight to desc+0x04.
constexpr int K1_DESC_DIGITAL = 1;

// Event ids for our joystick axes. The retained console range 0x27..0x40 is
// entirely unregistered -- verified live -- so these collide with nothing.
// They deliberately do NOT reuse 0x118/0x119: those already hold the keyboard's
// movement descriptions, and descriptions[] is one slot per event id, so
// reusing them would take movement away from the keyboard.
constexpr int K1_EVENT_JOY_X = 0x3B;
constexpr int K1_EVENT_JOY_Y = 0x3C;

// The retained console button events. ProcessInput routes any id in 0x27..0x40
// to CSWGuiManager::HandleInputEvent, and the panels still implement them -- see
// reverse-engineering/retained-xbox-gui-events.md. Nothing in the executable
// registers them, so they are free to bind, and binding them is what makes a pad
// button reach the game's own console handler instead of a synthetic keystroke.
constexpr int K1_EVENT_A     = 0x27;
constexpr int K1_EVENT_B     = 0x28;
constexpr int K1_EVENT_X     = 0x29;
constexpr int K1_EVENT_Y     = 0x2A;
constexpr int K1_EVENT_BLACK = 0x2B;

// Screen cycling, natively. The InGameMenu registers these on each of its eight
// tabs, and the handlers are CGuiInGame::PrevSWInGameGui (0x00624C00) and
// NextSWInGameGui (0x00624C30). This is the engine's own "previous / next
// screen", so the triggers need no synthetic keystroke.
constexpr int K1_EVENT_PREV_SCREEN = 0x35;
constexpr int K1_EVENT_NEXT_SCREEN = 0x36;

// The description-box scroll, implemented by 17 and 19 panels respectively --
// wider coverage than any button except B. Bound to the shoulders because it is
// the action a player reaches for most often while reading an item or feat.
constexpr int K1_EVENT_DESC_UP   = 0x39;
constexpr int K1_EVENT_DESC_DOWN = 0x3A;

// NOT used, and deliberately: 0x2D and 0x2E resolve to the same panel handlers
// as A and B wherever they are implemented -- on CSWGuiInGameCharacter all three
// of B, 0x2D and 0x2E reach 0x006B2459 -- so they are confirm/cancel aliases
// rather than distinct actions, and binding Start or Back to them would just
// duplicate A and B.

// Joystick button control slots. The +0x164 table maps 0x74..0x7E to
// DIJOFS_BUTTON(0)..BUTTON(10). Slot 0x7C -- button 8 -- is already taken by the
// game's own event 0x0B, so it is left alone; the rest are unused.
constexpr int K1_SLOT_BUTTON0 = 0x74;

struct ButtonBinding {
    std::uint16_t xinputMask;
    int           slot;          // control slot -> DIJOFS_BUTTON(n)
    int           event;         // retained console event
    const char*   name;
};

// Mapped to the console layout the panels were written for, so A confirms and B
// backs out exactly as the retained handlers expect.
// The D-pad. The engine does not expose a POV hat as one control: its own
// GetJoystickBuffer decodes the hat's angle into four direction codes, 0x384,
// 0x388, 0x38C and 0x390, which the +0x164 table reaches through slots 0x7F..
// 0x82. Those slots are unused, so the pad's four directions bind to the
// retained scroll and D-pad events and menus become navigable.
//
// Which code is which direction is NOT established -- the engine's decoder
// derives them from bit shifts this code has not unpicked -- so the pairing
// below is a first guess and may need two of the four swapped after a playtest.
constexpr ButtonBinding K1_DPAD[] = {
    { 0x0001, 0x7F, 0x31, "Up"    },   // code 0x384 -> retained scroll up
    { 0x0002, 0x81, 0x32, "Down"  },   // code 0x388 -> retained scroll down
    { 0x0004, 0x80, 0x2F, "Left"  },   // code 0x38C -> retained D-pad left
    { 0x0008, 0x82, 0x30, "Right" },   // code 0x390 -> retained D-pad right
};
constexpr int K1_DPAD_COUNT = sizeof(K1_DPAD) / sizeof(K1_DPAD[0]);

// Triggers. DirectInput traditionally merges an Xbox pad's triggers onto one
// shared axis, where opposite pulls cancel; XInput reports them separately, so
// they are treated here as two independent digital controls with their own
// button slots, inheriting nothing from that limitation.
constexpr int K1_TRIGGER_THRESHOLD = 60;   // of 255 -- a light pull already counts

// Start opens and closes the in-game menu, and costs no control slot at all.
//
// The game already registers its own joystick description for event 0x0B on
// slot 0x7C, which the +0x164 table resolves to DIJOFS_BUTTON(8). That event
// reaches the action router's handler at 0x006213BC, which reads the GUI's
// current state at [module+0x40]+0x34 and calls CGuiInGame::HideSWInGameGui or
// ShowSWInGameGui accordingly -- a real toggle, with the engine's own checks for
// a dead character, a missing party and so on.
//
// So Start needs no description, no slot and no bridge: emitting the control
// code the game is already listening for is enough. This is why 0x7C was left
// alone when the button slots were budgeted.
constexpr std::uint32_t DIJOFS_BUTTON8_OFFSET = 0x38;
constexpr std::uint16_t XINPUT_START_MASK     = 0x0010;

// The face buttons, shoulders and Back. Start is the game's own slot 0x7C, the
// triggers take 0x7B and 0x7D, the D-pad takes 0x7F..0x82, and the stick clicks
// are handled above.
// ---------------------------------------------------------- the stick clicks
//
// L3 and R3 were left unbound while the slot budget looked full. It was not:
// the +0x164 control-code table runs 0x6E..0x82 and slot 0x7E ->
// DIJOFS_BUTTON(10) is the one free entry. What was actually missing was an
// action worth binding, and both now have one.
//
// R3 = Free Look. This is a restoration, not an invention. The action router
// pairs a low console id with a high PC id for the same handler -- 0x0B/0xDF
// for the menu, and here 0x01/0xD0 to enter free look and 0x06/0xCC to leave
// it. The high ids carry the game's own keyboard descriptions; both low ids are
// unbound, which is exactly the shape Start had.
//
//   0x01 -> handler 0x006216C7: GetPlayerCreature, then CSWParty::
//           GetPlayerCharacter -> CSWCModule::SetFreeLookCamera, then sets the
//           input class at [internal+0x9c] to 4 and calls CExoInput::ClearEvents.
//   0x06 -> handler 0x0062184C: if ClientOptions+0x6D (the camera mode) reads 5,
//           CSWCModule::RestoreCamera and SetInputClass(0, 1).
//
// Both are registered on the same control slot, which is safe because they are
// registered in *different input classes* and only one class is ever polled:
// entering switches the class to ICFreeLook, so the enter event stops being
// visible at the moment the exit event starts being. That makes the toggle
// deterministic rather than dependent on dispatch order within a frame.
//
// L3 = Flourish Weapons. This one has no console id -- handler 0x00621C21
// serves only the PC id 0xF2, whose keyboard description already owns that
// event, and descriptions are one per event id. So it cannot be a native
// binding and is the project's first engine bridge instead.
constexpr int K1_SLOT_BUTTON10 = 0x7E;                    // the one free slot
constexpr std::uint32_t DIJOFS_BUTTON10_OFFSET = 0x3A;    // DIJOFS_BUTTON(10)

constexpr int K1_EVENT_FREELOOK_ENTER = 0x01;
constexpr int K1_EVENT_FREELOOK_EXIT  = 0x06;

// The six keymap.2da input-class columns load in a fixed order -- ICPC,
// ICMiniGame, ICPCGUI, ICDialog, ICFreeLook, ICMovie -- which puts ICPC at 0 and
// ICPCGUI at 2, the two indices already known from the working bindings. That
// makes ICFreeLook 4, and the enter handler agrees: it writes exactly 4 into the
// input-class field at [internal+0x9c].
constexpr int K1_CLASS_FREELOOK = 4;

constexpr std::uint16_t XINPUT_LEFT_THUMB_MASK  = 0x0040;
constexpr std::uint16_t XINPUT_RIGHT_THUMB_MASK = 0x0080;

// How a stick click reaches the engine. Adding a kind here is the only thing a
// future remapping needs to touch.
enum class StickAction {
    None,             // deliberately unbound
    FreeLook,         // native: emits the retained joystick event
    FlourishWeapons,  // bridge: calls the engine action directly
};

struct StickClickBinding {
    std::uint16_t xinputMask;
    StickAction   action;
    const char*   name;
};

// The KMRP defaults, isolated here on purpose.
//
// R3 = Free Look restores the original Xbox behaviour and should not move.
// L3 = Flourish Weapons is a KMRP default and *not* a settled design decision:
// changing it means editing this one row, and nothing about the architecture
// depends on which action a click carries.
constexpr StickClickBinding K1_STICK_CLICKS[] = {
    { XINPUT_LEFT_THUMB_MASK,  StickAction::FlourishWeapons, "L3" },
    { XINPUT_RIGHT_THUMB_MASK, StickAction::FreeLook,        "R3" },
};
constexpr int K1_STICK_CLICK_COUNT =
    sizeof(K1_STICK_CLICKS) / sizeof(K1_STICK_CLICKS[0]);

constexpr ButtonBinding K1_BUTTONS[] = {
    { 0x1000, 0x74, K1_EVENT_A,           "A"    },   // confirm
    { 0x2000, 0x75, K1_EVENT_B,           "B"    },   // cancel, 35 panels
    { 0x4000, 0x76, K1_EVENT_X,           "X"    },   // per-panel, 10 panels
    { 0x8000, 0x77, K1_EVENT_Y,           "Y"    },   // per-panel, 8 panels
    { 0x0100, 0x78, K1_EVENT_DESC_UP,     "LB"   },   // description scroll, 17 panels
    { 0x0200, 0x79, K1_EVENT_DESC_DOWN,   "RB"   },   // description scroll, 19 panels
    { 0x0020, 0x7A, K1_EVENT_BLACK,       "Back" },   // Black; Journal quest items
    // 0x7B and 0x7D carry the triggers; 0x7C is the game's own.
};
constexpr int K1_BUTTON_COUNT = sizeof(K1_BUTTONS) / sizeof(K1_BUTTONS[0]);

// LT and RT drive the engine's own screen cycling. The xinputMask field is
// unused for these -- the trigger value is a byte, not a bit -- so it carries
// the threshold index instead: 0 for left, 1 for right.
constexpr ButtonBinding K1_TRIGGERS[] = {
    { 0, 0x7B, K1_EVENT_PREV_SCREEN, "LT" },
    { 1, 0x7D, K1_EVENT_NEXT_SCREEN, "RT" },
};
constexpr int K1_TRIGGER_COUNT = sizeof(K1_TRIGGERS) / sizeof(K1_TRIGGERS[0]);

// DIJOYSTATE control codes, as the +0x164 table resolves our slots to.
constexpr std::uint32_t DIJOFS_X_OFFSET = 0x00;
constexpr std::uint32_t DIJOFS_Y_OFFSET = 0x04;
constexpr std::uint32_t DIJOFS_BUTTON0_OFFSET = 0x30;   // DIJOFS_BUTTON(0)

// The engine bridge. CClientExoApp lives at [[0x007A39FC]+4]; the action router
// reaches it exactly that way at 0x00621C2B before calling the flourish.
//
// PlayerFlourishWeapons resolves the player by game-object id and calls
// CSWCCreature::ComputeWeaponOverlays(0, 1) on the result -- with **no null
// check**. The router gets away with that because it only ever runs in a live
// module. A bridge does not have that guarantee, so GetPlayerCreature is
// checked first and the call is skipped when there is no player.
constexpr std::uintptr_t K1_CLIENT_EXO_APP_ROOT = 0x007A39FC;
constexpr std::uintptr_t K1_PLAYER_FLOURISH     = 0x005EDE90;  // CClientExoApp::PlayerFlourishWeapons
constexpr std::uintptr_t K1_GET_PLAYER_CREATURE = 0x005ED540;  // CClientExoApp::GetPlayerCreature
constexpr std::uintptr_t K1_GET_IN_FREE_LOOK    = 0x005EE230;  // CClientExoApp::GetInFreeLook

using ClientExoAppVoidFn = void(__thiscall*)(void*);
using ClientExoAppPtrFn  = void*(__thiscall*)(void*);
using ClientExoAppIntFn  = int(__thiscall*)(void*);

using CreateNewEventFn = int(__thiscall*)(void*, int, int, int, int, int);
using AddEventFn       = int(__thiscall*)(void*, int, int);
using PollInputFn      = float(__thiscall*)(void*, int, int);
using OperatorNewFn    = void*(__cdecl*)(std::size_t);
using OperatorDeleteFn = void(__cdecl*)(void*);
using NormalizeFn      = void(__thiscall*)(void*);


template <typename T> T EngineFn(std::uintptr_t address)
{
    return reinterpret_cast<T>(address);
}

float* FloatAt(void* base, std::size_t offset)
{
    return reinterpret_cast<float*>(static_cast<char*>(base) + offset);
}

std::int32_t* IntAt(void* base, std::size_t offset)
{
    return reinterpret_cast<std::int32_t*>(static_cast<char*>(base) + offset);
}

// -------------------------------------------------------------- record format

// The engine's own record shape: DIDEVICEOBJECTDATA, 0x14 bytes. It writes
// dwOfs, dwData, and zeroes dwTimeStamp and dwSequence. dwSequence is read by
// the cross-device merge, but every engine record carries zero, so ordering
// falls back to device order -- matching that exactly is deliberate. Inventing
// sequence numbers would make joystick records sort differently from the
// keyboard's.
struct InputRecord {
    std::uint32_t offset;
    std::int32_t  data;
    std::uint32_t timestamp;
    std::uint32_t sequence;
    std::uint32_t appData;
};

struct RecordBuffer {
    InputRecord* records;
    std::int32_t count;
};

constexpr std::size_t K1_RECORD_CAPACITY = 0x100;                 // 256
constexpr std::size_t K1_BUFFER_BYTES    = K1_RECORD_CAPACITY * sizeof(InputRecord);
static_assert(sizeof(InputRecord) == 0x14, "record must match DIDEVICEOBJECTDATA");
static_assert(K1_BUFFER_BYTES == 0x1400, "buffer must match the engine's 0x1400");

// ------------------------------------------------------------- stick handling

// XInput's thumbstick range is -32768..32767, and the engine's own
// GetMaxUseable for a joystick axis is 32767.0 -- the same full scale. So the
// raw value passes through untouched and only the curve is ours.
constexpr float K1_AXIS_FULL_SCALE = 32767.0f;

// A radial deadzone, not a per-axis one. Per-axis deadzones make a stick feel
// like it snaps to the cardinal directions, and they cannot express "this
// diagonal is only half deflected".
// Ours, applied radially to the stick as a vector, with the remaining travel
// rescaled to the full range. The engine's own is neutralised at startup.
//
// 8% is chosen, not guessed. KOTOR's own value is 8191.75 of 32767, a quarter of
// full deflection, and Microsoft's XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE is 7849 --
// about 24% -- so the engine simply matched the era's advice for a square,
// per-axis deadzone on 2003 hardware. Current practice for a movement stick is
// 5-8%, radial and rescaled, because a healthy modern thumbstick rests well
// below that.
//
// The lower bound comes from measurement rather than taste: the test
// controller's resting drift was (-1184, -1058), a magnitude of 4.8% of full
// scale, so 5% would sit on top of the noise. 8% clears it with room while
// discarding a third of the travel the engine's own value threw away.
//
// A per-axis deadzone would make the stick feel like it snaps to the cardinals
// and could not express a half-deflected diagonal at all.
constexpr float K1_STICK_DEADZONE = 0.08f;

// The right stick drives the camera through the mouse-delta field, so its value
// has to be in the units a mouse produces: pixels of movement in one frame,
// before the game's own sensitivity multiplier. Full deflection is treated as a
// brisk but not violent sweep. Unmeasured against the mouse -- this is the first
// number to change if the camera feels too fast or too slow.
constexpr float K1_CAMERA_SPEED = 14.0f;
constexpr float K1_CAMERA_DEADZONE = 0.12f;   // a touch higher; camera drift is more visible

struct StickState {
    bool          initialised = false;
    std::int32_t  lastX = 0;
    std::int32_t  lastY = 0;
    std::uint16_t lastButtons = 0;
    unsigned long flourishRequestedTick = 0;   // 0 = nothing pending
    unsigned long flourishesPerformed = 0;
    unsigned long flourishesDeclined = 0;
    int freeLookBound = 0;                     // bit 0 = enter, bit 1 = exit
    unsigned long navMoves = 0;                // focus moves this layer performed
    unsigned long navDeclinedNative = 0;       // presses left to native navigation
    unsigned long lastNavTick = 0;
    unsigned long lastGuiTick = 0;
    int navFromY = -1, navToY = -1, navDir = 0;
    std::uint8_t dpadEmitted = 0;   // which direction presses actually went out
    unsigned long navRepeatDeadline = 0;       // when a held direction may repeat
    int navHeldX = 0, navHeldY = 0;            // the direction currently held
    int navPendingX = 0, navPendingY = 0;      // requested, not yet performed
    int stickNavX = 0, stickNavY = 0;          // left stick's latched direction
    std::int32_t  rightX = 0;
    std::int32_t  rightY = 0;
    std::uint8_t  lastTriggers = 0;
    bool          registered = false;
    void*         input = nullptr;
    // Set at Control's entry, read a few instructions later at the
    // Vector::Normalize call site. Both live inside one Control call, so the
    // flag is never stale.
    bool          overrideActive = false;
    // Stamped at Control's entry. Control runs every gameplay frame whether or
    // not the stick is deflected, and never in menus, which makes it a reliable
    // "gameplay is live" signal without needing to ask the GUI anything.
    unsigned long lastMovementTick = 0;
    // Diagnostics. Cheap counters rather than a trace: the question is which
    // stages run at all, and reading that from a file beats stepping a game
    // that has to keep running to reproduce the problem.
    unsigned long initCalls = 0;
    unsigned long bufferCalls = 0;
    unsigned long recordsEmitted = 0;
    unsigned long movementCalls = 0;
    unsigned long overrideFrames = 0;
    std::int32_t  lastRawX = 0;
    std::int32_t  lastRawY = 0;
    float         lastPollX = 0.0f;
    float         lastPollY = 0.0f;
    bool          createFailed = false;
    int           addResult[6] = {0,0,0,0,0,0};
    unsigned long buttonsBound = 0;
    float         pollByClass[6] = {0,0,0,0,0,0};
    void*         playerControl = nullptr;
};

StickState g_stick;

// Read the pad once per frame. Returns raw axis values in XInput's range.
bool ReadPadAxes(std::int32_t& x, std::int32_t& y, std::uint16_t& buttons,
                 std::int32_t& rx, std::int32_t& ry,
                 std::uint8_t& lt, std::uint8_t& rt)
{
    for (DWORD slot = 0; slot < XUSER_MAX_COUNT; ++slot) {
        XINPUT_STATE state{};
        if (XInputGetState(slot, &state) != ERROR_SUCCESS) {
            continue;
        }
        x = state.Gamepad.sThumbLX;
        // Negated, and this was measured rather than assumed: with a straight
        // pass-through, pushing the stick up walked the character backwards.
        // XInput reports the thumbstick Y as up-positive; the engine's UpDown
        // axis runs the other way.
        y = -static_cast<std::int32_t>(state.Gamepad.sThumbLY);
        buttons = state.Gamepad.wButtons;
        rx = state.Gamepad.sThumbRX;
        ry = state.Gamepad.sThumbRY;
        lt = state.Gamepad.bLeftTrigger;
        rt = state.Gamepad.bRightTrigger;
        return true;
    }
    return false;
}

}  // namespace

// ------------------------------------------------------------- registration

void EnsureNativeJoystickK1(void* exoInputInternal)
{
    if (!exoInputInternal || g_stick.registered) {
        return;
    }
    g_stick.input = exoInputInternal;

    auto createEvent = EngineFn<CreateNewEventFn>(K1_CREATE_NEW_EVENT);
    auto addEvent    = EngineFn<AddEventFn>(K1_ADD_EVENT);

    // CreateNewEvent(eventId, descType, device, controlSlot, secondControlSlot).
    // Returns 0 when the event id is already taken, which is why the ids above
    // come from the unregistered console range.
    const bool madeX = createEvent(exoInputInternal, K1_EVENT_JOY_X, K1_DESC_ANALOG,
                                   K1_DEVICE_JOYSTICK, K1_SLOT_JOY_X, K1_SLOT_NONE) != 0;
    const bool madeY = createEvent(exoInputInternal, K1_EVENT_JOY_Y, K1_DESC_ANALOG,
                                   K1_DEVICE_JOYSTICK, K1_SLOT_JOY_Y, K1_SLOT_NONE) != 0;
    ++g_stick.initCalls;
    if (!madeX || !madeY) {
        g_stick.createFailed = true;
        return;                     // leave g_stick.registered false and retry
    }

    // AddEvent(eventId, inputClass) -- note the order; it is not
    // (class, event). Gameplay needs the PC class; the GUI class is registered
    // too so the same axes can drive menus later.
    // Registered in every input class. Which class is active in gameplay was
    // read as 0 at the main menu and is not safe to assume elsewhere, and a
    // description only receives values while its (class, device) list is the
    // one being matched.
    for (int cls = 0; cls < 6; ++cls) {
        g_stick.addResult[cls] =
            (addEvent(exoInputInternal, K1_EVENT_JOY_X, cls) != 0 ? 1 : 0) |
            (addEvent(exoInputInternal, K1_EVENT_JOY_Y, cls) != 0 ? 2 : 0);
    }

    // Make the poll loop iterate device index 2. This must be the live count on
    // CExoInputInternal, not CExoRawInputInternal+0x18: the constructor has
    // already consumed the latter, so writing it at runtime does nothing.
    std::int32_t* count = IntAt(exoInputInternal, K1_INPUT_DEVICE_COUNT);
    if (*count < K1_DEVICE_JOYSTICK + 1) {
        *count = K1_DEVICE_JOYSTICK + 1;
    }

    // Buttons, bound to the retained console events. Registered in the GUI
    // class so menus respond, and in the gameplay class so the panels that open
    // over the world see them too. A failure here is not fatal: the axes are
    // independent and the log records which bindings took.
    for (int b = 0; b < K1_BUTTON_COUNT; ++b) {
        const ButtonBinding& binding = K1_BUTTONS[b];
        if (createEvent(exoInputInternal, binding.event, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0) {
            continue;               // id already taken; leave it alone
        }
        addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        ++g_stick.buttonsBound;
    }

    for (int r = 0; r < K1_TRIGGER_COUNT; ++r) {
        const ButtonBinding& binding = K1_TRIGGERS[r];
        if (createEvent(exoInputInternal, binding.event, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0) {
            continue;
        }
        addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        ++g_stick.buttonsBound;
    }

    for (int d = 0; d < K1_DPAD_COUNT; ++d) {
        const ButtonBinding& binding = K1_DPAD[d];
        if (createEvent(exoInputInternal, binding.event, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0) {
            continue;
        }
        addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        ++g_stick.buttonsBound;
    }

    // Free look, on the one free control slot. Both events share slot 0x7E and
    // that is deliberate: they are registered in different input classes, so
    // whichever one is not applicable right now is not even polled.
    //
    // Enter is a gameplay action, so it goes in ICPC. Exit goes in ICFreeLook,
    // because entering switches the class to 4 -- registering it in ICPC too
    // would let a single press enter and then immediately leave again.
    for (int c = 0; c < K1_STICK_CLICK_COUNT; ++c) {
        if (K1_STICK_CLICKS[c].action != StickAction::FreeLook) {
            continue;
        }
        if (createEvent(exoInputInternal, K1_EVENT_FREELOOK_ENTER, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, K1_SLOT_BUTTON10, K1_SLOT_NONE) != 0) {
            addEvent(exoInputInternal, K1_EVENT_FREELOOK_ENTER, K1_CLASS_PC);
            ++g_stick.buttonsBound;
            g_stick.freeLookBound |= 1;
        }
        if (createEvent(exoInputInternal, K1_EVENT_FREELOOK_EXIT, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, K1_SLOT_BUTTON10, K1_SLOT_NONE) != 0) {
            addEvent(exoInputInternal, K1_EVENT_FREELOOK_EXIT, K1_CLASS_FREELOOK);
            ++g_stick.buttonsBound;
            g_stick.freeLookBound |= 2;
        }
    }

    // Neutralise the engine's quarter-scale joystick deadzone. Its own value
    // suits a 2003 flight stick with a loose centre, not a thumbstick, and it
    // cannot be expressed radially. Ours replaces it below.
    DWORD previous = 0;
    void* const minUseable = reinterpret_cast<void*>(K1_JOY_MIN_USEABLE);
    if (VirtualProtect(minUseable, sizeof(float), PAGE_EXECUTE_READWRITE, &previous)) {
        *reinterpret_cast<float*>(minUseable) = 0.0f;
        VirtualProtect(minUseable, sizeof(float), previous, &previous);
    }

    g_stick.registered = true;
}


// Defined further down with the focus-navigation layer; declared here because
// the record emitter feeds them.
bool KmrpOwnsDirectionsK1();
void UpdateStickNavigationK1(float x, float y);
void RequestNavigationK1(int dx, int dy, bool edge);
// ------------------------------------------------------------- record filling

void FillNativeJoystickBufferK1(int deviceIndex, void* outBuffer)
{
    ++g_stick.bufferCalls;
    auto* out = static_cast<RecordBuffer*>(outBuffer);
    if (!out) {
        return;
    }

    // The engine frees the previous buffer and allocates a fresh one on every
    // call, and its consumer frees what we hand back, so use the same allocator
    // rather than a static buffer.
    if (out->records) {
        EngineFn<OperatorDeleteFn>(K1_OPERATOR_DELETE)(out->records);
        out->records = nullptr;
    }
    out->count = 0;
    out->records = static_cast<InputRecord*>(
        EngineFn<OperatorNewFn>(K1_OPERATOR_NEW)(K1_BUFFER_BYTES));
    if (!out->records) {
        return;
    }

    if (deviceIndex != 0) {
        return;                     // only the first pad, for now
    }

    std::int32_t x = 0;
    std::int32_t y = 0;
    std::uint16_t buttons = 0;
    std::int32_t rx = 0;
    std::int32_t ry = 0;
    std::uint8_t lt = 0;
    std::uint8_t rt = 0;
    if (!ReadPadAxes(x, y, buttons, rx, ry, lt, rt)) {
        x = 0;
        y = 0;                      // treat a disconnect as centred
        buttons = 0;                // and as everything released
        rx = 0;
        ry = 0;
        lt = 0;
        rt = 0;
    }

    // Edge-triggered, exactly as the engine's own button loop is: emit only on
    // change. The zero transition is the one that matters most. Because a match
    // stores the value on the description and PollInput reads it back, failing
    // to emit a record when the stick returns to centre would leave the last
    // non-zero value in place and the character would walk forever.
    if (!g_stick.initialised) {
        g_stick.initialised = true;
        g_stick.lastX = x + 1;      // force both axes to report once
        g_stick.lastY = y + 1;
    }

    auto emit = [&](std::uint32_t offset, std::int32_t value) {
        if (static_cast<std::size_t>(out->count) >= K1_RECORD_CAPACITY) {
            return;
        }
        InputRecord& record = out->records[out->count];
        // Only the first 0x100 bytes of the allocation are cleared by the
        // original, so every field is written explicitly rather than assumed
        // zero.
        record.offset    = offset;
        record.data      = value;
        record.timestamp = 0;
        record.sequence  = 0;
        record.appData   = 0;
        ++out->count;
    };

    g_stick.lastRawX = x;
    g_stick.lastRawY = y;

    // Axes are emitted EVERY frame carrying the absolute position, and are
    // deliberately not edge-triggered the way buttons are.
    //
    // The engine's analog joystick descriptions (events 0x07 and 0x08) are
    // description type 3, whose store accumulates -- `add [desc+0x24], dwData`
    // -- while PollInput returns `[+0x24] - [+0x04]` and then sets the baseline
    // `[+0x04]` to the accumulator, consuming what it just read. So one record
    // per frame carrying the current position makes each poll return exactly
    // that position, which is what the movement code wants.
    //
    // Edge-triggering them, as an earlier version did, breaks this twice over: a
    // held stick emits nothing, so the accumulator stops moving and the poll
    // returns zero, and any frame the engine does not poll leaves the delta
    // uncollected so the next one reads a stale sum. Holding forward across
    // three pushes was measured at -98301, exactly -32767 times three.
    //
    // A centred stick needs no record: contributing zero to the accumulator and
    // contributing nothing are the same thing, and the poll correctly reads zero.
    // Radial deadzone, then rescale what is left across the full range so the
    // first movement past it starts from a standstill rather than jumping.
    // Applied to the vector, not per axis, so a half-deflected diagonal stays
    // half deflected.
    const float nx = static_cast<float>(x) / K1_AXIS_FULL_SCALE;
    const float ny = static_cast<float>(y) / K1_AXIS_FULL_SCALE;
    float magnitude = std::sqrt(nx * nx + ny * ny);
    if (magnitude > K1_STICK_DEADZONE) {
        if (magnitude > 1.0f) {
            magnitude = 1.0f;               // the corners of a square gate
        }
        const float scaled = (magnitude - K1_STICK_DEADZONE) / (1.0f - K1_STICK_DEADZONE);
        const float factor = (scaled / magnitude) * K1_AXIS_FULL_SCALE;
        const std::int32_t ex = static_cast<std::int32_t>(nx * factor);
        const std::int32_t ey = static_cast<std::int32_t>(ny * factor);
        if (ex != 0) {
            emit(DIJOFS_X_OFFSET, ex);
        }
        if (ey != 0) {
            emit(DIJOFS_Y_OFFSET, ey);
        }
    }
    // Buttons stay edge-triggered, unlike the axes. The engine's own button
    // loop emits only on change, and the digital store path writes the value
    // rather than accumulating it, so a held button needs no repeat.
    for (int b = 0; b < K1_BUTTON_COUNT; ++b) {
        const std::uint16_t mask = K1_BUTTONS[b].xinputMask;
        const bool now = (buttons & mask) != 0;
        const bool was = (g_stick.lastButtons & mask) != 0;
        if (now != was) {
            emit(DIJOFS_BUTTON0_OFFSET + static_cast<std::uint32_t>(b), now ? 1 : 0);
        }
    }
    // Whether the native direction codes go out at all. On a screen the engine
    // navigates properly they must; on one this layer navigates they must not,
    // or focus moves twice for one press.
    const bool kmrpDirections = KmrpOwnsDirectionsK1();

    for (int d = 0; d < K1_DPAD_COUNT; ++d) {
        const std::uint16_t mask = K1_DPAD[d].xinputMask;
        const bool now = (buttons & mask) != 0;
        const bool was = (g_stick.lastButtons & mask) != 0;
        if (now != was) {
            // The direction codes are 0x384, 0x388, 0x38C, 0x390 -- the same
            // values the engine's own POV decoder produces -- reached here
            // through the slot each binding names.
            static const std::uint32_t codes[] = { 0x384, 0x388, 0x38C, 0x390 };
            const std::uint8_t bit = static_cast<std::uint8_t>(1u << d);
            if (now) {
                // Suppression is decided once, at the press, and remembered.
                // Deciding it again at the release would let a screen change
                // mid-press emit a press with no matching release, and a
                // digital description that never sees its zero stays stuck on.
                if (!kmrpDirections) {
                    emit(codes[d], 1);
                    g_stick.dpadEmitted |= bit;
                }
            } else if ((g_stick.dpadEmitted & bit) != 0) {
                emit(codes[d], 0);
                g_stick.dpadEmitted &= static_cast<std::uint8_t>(~bit);
            }
        }
    }

    // The same presses feed the focus-navigation layer. Exactly one of the two
    // acts on any given screen: where the engine navigates properly the codes
    // above went out and this declines, and where it does not, the codes were
    // suppressed and this moves the focus instead.
    {
        // K1_DPAD order is Up, Down, Left, Right.
        static const int dirs[K1_DPAD_COUNT][2] = { {0,-1}, {0,1}, {-1,0}, {1,0} };
        int dx = 0;
        int dy = 0;
        bool edge = false;
        for (int d = 0; d < K1_DPAD_COUNT; ++d) {
            const std::uint16_t mask = K1_DPAD[d].xinputMask;
            if ((buttons & mask) != 0) {
                dx = dirs[d][0];
                dy = dirs[d][1];
                if ((g_stick.lastButtons & mask) == 0) {
                    edge = true;
                }
            }
        }
        // The left stick drives the same operation, with its own hysteresis, and
        // only when the D-pad is not already asking for something.
        if (dx == 0 && dy == 0) {
            UpdateStickNavigationK1(nx, ny);
            if (g_stick.stickNavX != 0 || g_stick.stickNavY != 0) {
                dx = g_stick.stickNavX;
                dy = g_stick.stickNavY;
                if (g_stick.navHeldX != dx || g_stick.navHeldY != dy) {
                    edge = true;
                }
            }
        } else {
            g_stick.stickNavX = 0;
            g_stick.stickNavY = 0;
        }
        RequestNavigationK1(dx, dy, edge);
    }
    // Triggers, edge-triggered on the threshold crossing so a held pull does not
    // repeat. Each has its own slot, so LT and RT can be pulled together without
    // interfering -- the DirectInput shared-axis problem does not arise here.
    const std::uint8_t triggerValues[K1_TRIGGER_COUNT] = { lt, rt };
    for (int r = 0; r < K1_TRIGGER_COUNT; ++r) {
        const bool now = triggerValues[r] > K1_TRIGGER_THRESHOLD;
        const bool was = (g_stick.lastTriggers & (1u << r)) != 0;
        if (now != was) {
            emit(DIJOFS_BUTTON0_OFFSET + static_cast<std::uint32_t>(K1_TRIGGERS[r].slot - 0x74),
                 now ? 1 : 0);
            if (now) {
                g_stick.lastTriggers |= static_cast<std::uint8_t>(1u << r);
            } else {
                g_stick.lastTriggers &= static_cast<std::uint8_t>(~(1u << r));
            }
        }
    }

    // Start -> the game's own menu toggle. Edge-triggered like every other
    // button; the handler toggles, so a held press must not repeat.
    {
        const bool now = (buttons & XINPUT_START_MASK) != 0;
        const bool was = (g_stick.lastButtons & XINPUT_START_MASK) != 0;
        if (now != was) {
            emit(DIJOFS_BUTTON8_OFFSET, now ? 1 : 0);
        }
    }

    // The stick clicks. Free look emits its retained event like any other
    // button; the flourish is a bridge and is only *requested* here, never
    // called from inside the input hook -- see PerformPendingStickActionsK1.
    for (int c = 0; c < K1_STICK_CLICK_COUNT; ++c) {
        const StickClickBinding& click = K1_STICK_CLICKS[c];
        const bool now = (buttons & click.xinputMask) != 0;
        const bool was = (g_stick.lastButtons & click.xinputMask) != 0;
        if (now == was) {
            continue;
        }
        switch (click.action) {
        case StickAction::FreeLook:
            emit(DIJOFS_BUTTON10_OFFSET, now ? 1 : 0);
            break;
        case StickAction::FlourishWeapons:
            if (now) {
                g_stick.flourishRequestedTick = GetTickCount();
            }
            break;
        case StickAction::None:
            break;
        }
    }

    g_stick.lastButtons = buttons;

    g_stick.rightX = rx;
    g_stick.rightY = ry;
    g_stick.lastX = x;
    g_stick.lastY = y;
    g_stick.recordsEmitted += static_cast<unsigned long>(out->count);
}

// ------------------------------------------------------------- stick geometry

bool ReadNativeStickK1(float& x, float& y)
{
    if (!g_stick.registered || !g_stick.input) {
        return false;
    }

    // Read back through the engine's own path rather than from XInput directly.
    // That is the point of the exercise: if the description, the record and the
    // matching are not all working, this returns zero and the keyboard keeps
    // control, instead of movement silently bypassing the pipeline under test.
    auto poll = EngineFn<PollInputFn>(K1_POLL_INPUT);
    const float rawX = poll(g_stick.input, K1_EVENT_JOY_X, K1_CLASS_PC);
    const float rawY = poll(g_stick.input, K1_EVENT_JOY_Y, K1_CLASS_PC);
    g_stick.lastPollX = rawX;
    g_stick.lastPollY = rawY;
    for (int cls = 0; cls < 6; ++cls) {
        g_stick.pollByClass[cls] = poll(g_stick.input, K1_EVENT_JOY_X, cls);
    }

    // Treat the stick as one vector. Deadzoning each axis separately makes a
    // stick feel like it snaps to the cardinals, and cannot express a
    // half-deflected diagonal at all.
    float nx = rawX / K1_AXIS_FULL_SCALE;
    float ny = rawY / K1_AXIS_FULL_SCALE;

    const float magnitude = std::sqrt(nx * nx + ny * ny);
    if (magnitude <= K1_STICK_DEADZONE) {
        return false;               // inside the deadzone: keyboard keeps control
    }

    // Rescale what is left of the range to 0..1 so the first movement past the
    // deadzone starts from a standstill rather than jumping to a quarter speed.
    float scaled = (magnitude - K1_STICK_DEADZONE) / (1.0f - K1_STICK_DEADZONE);
    if (scaled > 1.0f) {
        scaled = 1.0f;              // the corners of a square gate exceed 1
    }

    const float unitX = nx / magnitude;
    const float unitY = ny / magnitude;
    x = unitX * scaled;
    y = unitY * scaled;
    return true;
}

// ------------------------------------------------------------- hook entry points

extern "C" void __cdecl NativeJoystickDumpK1();

// CExoInputInternal::GetEvents entry, ecx = the input singleton. Runs every
// frame; the registration inside is idempotent and cheap after the first call.
// Add the right stick to the accumulated mouse delta, so the camera rotates.
//
// The timing is what makes this work without a new hook. ProcessInput calls
// UpdateMouseDelta at 0x006228A3, then GetEvents -- this hook -- at 0x006228D2,
// and UpdateCamera runs later in the frame. So this lands after the delta is
// computed and before the camera reads it. Adding rather than assigning leaves a
// real mouse working normally in the same frame.
//
// Nothing here moves the cursor: the cursor is positioned elsewhere, and these
// two fields are only ever read by GetMouseDelta, whose single caller is
// UpdateCamera.
void FeedNativeCameraK1(void* exoInputInternal)
{
    if (!exoInputInternal) {
        return;
    }
    const float nx = static_cast<float>(g_stick.rightX) / K1_AXIS_FULL_SCALE;
    const float ny = static_cast<float>(g_stick.rightY) / K1_AXIS_FULL_SCALE;
    const float magnitude = std::sqrt(nx * nx + ny * ny);
    if (magnitude <= K1_CAMERA_DEADZONE) {
        return;
    }
    const float scaled = (magnitude - K1_CAMERA_DEADZONE) / (1.0f - K1_CAMERA_DEADZONE);
    const float factor = (scaled > 1.0f ? 1.0f : scaled) / magnitude * K1_CAMERA_SPEED;
    *FloatAt(exoInputInternal, K1_MOUSE_DELTA_X) += nx * factor;
}

extern "C" void __cdecl NativeJoystickInitK1(void* exoInputInternal)
{
    EnsureNativeJoystickK1(exoInputInternal);
    FeedNativeCameraK1(exoInputInternal);
    // Dumped from here as well as from the movement hook: GetEvents runs in
    // menus too, so registration and record counts can be inspected without
    // first loading a save.
    NativeJoystickDumpK1();
}

// Replaces CExoRawInputInternal::GetJoystickBuffer. Hooked a few instructions
// past the entry, at the point where esi holds the caller's record buffer --
// KPM sources hook parameters from registers, and at the true entry the buffer
// is still only on the stack. ebx, esi and edi are all pushed by then, so the
// consumed exit at 0x005E319B unwinds correctly, and GetEvents ignores this
// function's return value.
extern "C" int __cdecl NativeJoystickBufferK1(void* outBuffer)
{
    FillNativeJoystickBufferK1(0, outBuffer);
    return 1;                       // consumed: skip the original body
}

// CSWPlayerControlCamRelative::Control entry, ecx = the player control object.
// By this point ProcessInput has already clamped the keyboard axes into
// +0x10 / +0x14, so overwriting them here is the single convergence point for
// every control scheme -- rather than patching the eight separate PollInput
// sites ProcessInput uses for events 0x118 and 0x119.
//
// Reading the stick as one vector and writing both fields together is
// deliberate: it is the only way a half-deflected diagonal can survive, and
// doing it in one place means the two axes can never disagree about the
// deadzone.
// =========================================================== focus navigation
//
// KOTOR's PC build navigates a screen with the mouse. The retained console
// events only reach the *focused* control, and on most screens nothing focuses
// anything, so a D-pad press has nowhere to go. This is the layer that gives
// the controller a focus to move.
//
// It is deliberately not a Main Menu hack. The rule is geometric and applies to
// any panel; the per-panel knowledge is limited to one measured question --
// "does this screen already navigate itself?" -- and where the answer is yes,
// nothing here runs.
//
// Structures, all read live and all confirmed against the running game:
//
//   CSWGuiManager  +0x88 panel array, +0x8C panel count
//   CSWGuiPanel    +0x1C active control, +0x20 control array, +0x24 count,
//                  +0x44 flags
//   CSWGuiControl  +0x04 x, +0x08 y, +0x0C width, +0x10 height, +0x44 flags
//
// The control flags are read as a **byte**, because that is what the engine
// does: CSWGuiControl::HitCheckMouse tests `cl`, not `ecx`, and the upper three
// bytes of that dword hold unrelated data that would otherwise poison the test.

constexpr std::uintptr_t K1_GUI_MANAGER_PTR    = 0x007A39F4;
constexpr std::uintptr_t K1_SET_ACTIVE_CONTROL = 0x0040A630;  // (control, playSound)

constexpr std::size_t K1_MGR_PANEL_ARRAY = 0x88;
constexpr std::size_t K1_MGR_PANEL_COUNT = 0x8C;

constexpr std::size_t K1_PANEL_ACTIVE        = 0x1C;
constexpr std::size_t K1_PANEL_CONTROL_ARRAY = 0x20;
constexpr std::size_t K1_PANEL_CONTROL_COUNT = 0x24;
constexpr std::size_t K1_PANEL_FLAGS         = 0x44;

constexpr std::size_t K1_CTL_X     = 0x04;
constexpr std::size_t K1_CTL_Y     = 0x08;
constexpr std::size_t K1_CTL_W     = 0x0C;
constexpr std::size_t K1_CTL_H     = 0x10;
constexpr std::size_t K1_CTL_FLAGS = 0x44;
constexpr std::size_t K1_CTL_EVENT_TABLE = 0x38;   // CSWGuiControl::AddEvent's table
constexpr std::size_t K1_CTL_EVENT_COUNT = 0x3C;

constexpr std::size_t K1_VTABLE_HANDLE_INPUT = 0x3C;

// CSWGuiManager::IsOnTop walks the panel list from the end and skips anything
// carrying these bits, so the topmost panel without them is the one in front.
constexpr std::uint32_t K1_PANEL_FLAG_SKIP = 0x600;

constexpr std::uint8_t K1_CTL_FLAG_VISIBLE    = 0x02;
constexpr std::uint8_t K1_CTL_FLAG_SELECTABLE = 0x08;
constexpr std::uint8_t K1_CTL_FLAG_DISABLED   = 0x20;

// Panels whose own dispatcher implements the direction events. Measured, not
// assumed: these are every panel in the retained-event inventory implementing
// any of 0x2F / 0x30 / 0x31 / 0x32 or their 0x3D..0x40 aliases. On these screens
// the engine already navigates itself and this layer stands down.
constexpr std::uintptr_t K1_NATIVE_DIRECTION_PANELS[] = {
    0x006AE5F0,   // ABILITIES
    0x006F8880,   // ABILITIES_CHARGEN
    0x006F4680,   // FEATS
    0x00693BC0,   // MAP
    0x006F28C0,   // POWERS
    0x006F6A10,   // SKILLS
};

// Control classes that consume the direction events themselves. A focused list
// box scrolls its own rows, and stealing the press to move focus off it would
// break navigation that already works.
constexpr std::uintptr_t K1_NATIVE_DIRECTION_CONTROLS[] = {
    0x0041A9D0,   // CSWGuiNavigable / CSWGuiEditbox -- up, down, left, right
    0x0041CE20,   // CSWGuiListBox -- up, down, plus its own scrollbar codes
    0x0041ADF0,   // CSWGuiSlider -- axis depends on orientation
};

using SetActiveControlFn = void(__thiscall*)(void*, void*, int);

template <typename T> T* FieldAt(void* base, std::size_t offset)
{
    return reinterpret_cast<T*>(reinterpret_cast<std::uint8_t*>(base) + offset);
}

bool LooksLikePointerK1(const void* p)
{
    const std::uintptr_t v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x00010000u && v < 0x7FFF0000u;
}

bool InListK1(std::uintptr_t value, const std::uintptr_t* list, std::size_t count)
{
    for (std::size_t i = 0; i < count; ++i) {
        if (list[i] == value) {
            return true;
        }
    }
    return false;
}

std::uintptr_t DispatcherOfK1(void* object)
{
    if (!LooksLikePointerK1(object)) {
        return 0;
    }
    void* const vtable = *reinterpret_cast<void**>(object);
    if (!LooksLikePointerK1(vtable)) {
        return 0;
    }
    return *FieldAt<std::uintptr_t>(vtable, K1_VTABLE_HANDLE_INPUT);
}

void* TopPanelK1()
{
    void* const manager = *reinterpret_cast<void**>(K1_GUI_MANAGER_PTR);
    if (!LooksLikePointerK1(manager)) {
        return nullptr;
    }
    void** const panels = *FieldAt<void**>(manager, K1_MGR_PANEL_ARRAY);
    const int count = *FieldAt<int>(manager, K1_MGR_PANEL_COUNT);
    if (!LooksLikePointerK1(panels) || count <= 0 || count > 256) {
        return nullptr;
    }
    for (int i = count - 1; i >= 0; --i) {
        void* const panel = panels[i];
        if (!LooksLikePointerK1(panel)) {
            continue;
        }
        if ((*FieldAt<std::uint32_t>(panel, K1_PANEL_FLAGS) & K1_PANEL_FLAG_SKIP) == 0) {
            return panel;
        }
    }
    return nullptr;
}

struct RectK1 {
    int x, y, w, h;
    int cx() const { return x + w / 2; }
    int cy() const { return y + h / 2; }
};

// Actionable means what the player would call actionable: on screen, not greyed
// out, selectable, and occupying real space. Labels, borders and background art
// fail the selectable bit and never receive focus.
bool ControlIsNavigableK1(void* control, RectK1& rect)
{
    if (!LooksLikePointerK1(control)) {
        return false;
    }
    const std::uint8_t flags =
        static_cast<std::uint8_t>(*FieldAt<std::uint32_t>(control, K1_CTL_FLAGS) & 0xFFu);
    if ((flags & K1_CTL_FLAG_VISIBLE) == 0) {
        return false;
    }
    if ((flags & K1_CTL_FLAG_DISABLED) != 0) {
        return false;
    }
    if ((flags & K1_CTL_FLAG_SELECTABLE) == 0) {
        return false;
    }

    // The decisive test, and the engine's own: a control that has registered no
    // events cannot respond to anything, so it is decoration however selectable
    // its flags claim to be. CSWGuiControl::AddEvent builds this table.
    //
    // Without it the Main Menu is unusable. Its background is a control the full
    // size of the screen -- 3440x1440 -- carrying the visible and selectable
    // bits, and its centre sits closer to the menu column than the next button
    // does, so every press downward would have focused the wallpaper. The five
    // real entries each register four events; the background, the logo and the
    // side art register none.
    void** const events = *FieldAt<void**>(control, K1_CTL_EVENT_TABLE);
    const int eventCount = *FieldAt<int>(control, K1_CTL_EVENT_COUNT);
    if (!LooksLikePointerK1(events) || eventCount <= 0 || eventCount > 64) {
        return false;
    }

    rect.x = *FieldAt<int>(control, K1_CTL_X);
    rect.y = *FieldAt<int>(control, K1_CTL_Y);
    rect.w = *FieldAt<int>(control, K1_CTL_W);
    rect.h = *FieldAt<int>(control, K1_CTL_H);
    return rect.w > 0 && rect.h > 0;
}

// How strongly a move prefers to stay in its row or column. A candidate that
// overlaps the current control on the cross axis pays nothing for its offset; a
// candidate that does not pays this multiple of it. Large on purpose: a menu is
// a column, and sliding out of that column reads as a bug even when the
// diagonal distance is genuinely shorter.
constexpr int K1_NAV_CROSS_AXIS_PENALTY = 6;

int OverlapK1(int aStart, int aSize, int bStart, int bSize)
{
    const int lo   = aStart > bStart ? aStart : bStart;
    const int aEnd = aStart + aSize;
    const int bEnd = bStart + bSize;
    const int hi   = aEnd < bEnd ? aEnd : bEnd;
    return hi - lo;                       // <= 0 when they do not overlap
}

int AbsIntK1(int v) { return v < 0 ? -v : v; }

// Pick the control a press in (dx, dy) should move to; exactly one of dx and dy
// is non-zero. Returns null when there is nowhere sensible to go.
void* ChooseNeighbourK1(void* panel, void* current, int dx, int dy)
{
    void** const controls = *FieldAt<void**>(panel, K1_PANEL_CONTROL_ARRAY);
    const int count = *FieldAt<int>(panel, K1_PANEL_CONTROL_COUNT);
    if (!LooksLikePointerK1(controls) || count <= 0 || count > 512) {
        return nullptr;
    }

    RectK1 from{};
    const bool haveCurrent = ControlIsNavigableK1(current, from);

    void* best = nullptr;
    long bestScore = 0;
    void* wrap = nullptr;
    long wrapScore = 0;

    for (int i = 0; i < count; ++i) {
        void* const candidate = controls[i];
        if (candidate == current) {
            continue;
        }
        RectK1 to{};
        if (!ControlIsNavigableK1(candidate, to)) {
            continue;
        }

        // Nothing focused yet: take the topmost, then leftmost control. That is
        // where a player's eye starts, and it makes the first press predictable.
        if (!haveCurrent) {
            const long score = static_cast<long>(to.y) * 10000L + to.x;
            if (!best || score < bestScore) {
                best = candidate;
                bestScore = score;
            }
            continue;
        }

        const int alongDelta  = dx != 0 ? (to.cx() - from.cx()) : (to.cy() - from.cy());
        const int crossOffset = dx != 0 ? AbsIntK1(to.cy() - from.cy())
                                        : AbsIntK1(to.cx() - from.cx());
        const int crossOverlap = dx != 0 ? OverlapK1(from.y, from.h, to.y, to.h)
                                         : OverlapK1(from.x, from.w, to.x, to.w);

        const int direction = dx != 0 ? dx : dy;
        const int forward   = alongDelta * direction;
        const long penalty  = crossOverlap > 0
            ? 0L
            : static_cast<long>(crossOffset) * K1_NAV_CROSS_AXIS_PENALTY;

        if (forward > 0) {
            const long score = static_cast<long>(forward) + penalty;
            if (!best || score < bestScore) {
                best = candidate;
                bestScore = score;
            }
        } else {
            // Wrapping: the farthest control the other way, still preferring the
            // same line. A console menu wraps from the last entry back to the
            // first, and stopping dead at the end feels broken beside it.
            const long score = static_cast<long>(forward) + penalty;
            if (!wrap || score < wrapScore) {
                wrap = candidate;
                wrapScore = score;
            }
        }
    }

    return best ? best : wrap;
}

// True when the screen already navigates itself, in which case this layer must
// keep its hands off and let the retained events do their job.
bool PanelNavigatesItselfK1(void* panel, void* active)
{
    const std::uintptr_t panelDispatcher = DispatcherOfK1(panel);
    if (panelDispatcher != 0 &&
        InListK1(panelDispatcher, K1_NATIVE_DIRECTION_PANELS,
                 sizeof(K1_NATIVE_DIRECTION_PANELS) / sizeof(K1_NATIVE_DIRECTION_PANELS[0]))) {
        return true;
    }
    const std::uintptr_t controlDispatcher = DispatcherOfK1(active);
    return controlDispatcher != 0 &&
        InListK1(controlDispatcher, K1_NATIVE_DIRECTION_CONTROLS,
                 sizeof(K1_NATIVE_DIRECTION_CONTROLS) / sizeof(K1_NATIVE_DIRECTION_CONTROLS[0]));
}

// Does KMRP own the direction presses on whatever is currently in front?
//
// This has to be answerable from the record emitter, because the answer decides
// whether the native direction codes are sent at all. It is pure memory reading
// -- no engine calls -- so it is safe to ask from inside the input hook.
//
// It matters because the engine is not inert here. CSWGuiManager::HandleInputEvent
// does move focus on 0x2F..0x32, but not in the order a player reads the screen:
// measured on the Main Menu, its own sequence from the top entry runs
// 666 -> 810 -> 954 -> 738 -> 882, skipping an entry each time and wrapping
// oddly. Leaving those events enabled alongside this layer moved focus twice per
// press -- once sensibly and once not.
// The engine's own input class, at CClientExoAppInternal+0x9c: 0 while the
// player is in the world, 2 once a GUI screen has the input, 4 in free look.
// Focus navigation is a GUI operation and must be confined to class 2 -- in
// gameplay the panel in front is the HUD, whose controls are not menu entries,
// and taking the direction presses there would both hijack the D-pad's own
// bindings and let the layer wander around the heads-up display.
int InputClassK1()
{
    void** const appManager = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT);
    if (!LooksLikePointerK1(appManager)) {
        return -1;
    }
    void** const app = static_cast<void**>(appManager[1]);
    if (!LooksLikePointerK1(app)) {
        return -1;
    }
    void* const internal = app[1];
    if (!LooksLikePointerK1(internal)) {
        return -1;
    }
    return *FieldAt<int>(internal, 0x9C);
}

bool KmrpOwnsDirectionsK1()
{
    if (InputClassK1() != K1_CLASS_PCGUI) {
        return false;
    }
    void* const panel = TopPanelK1();
    if (!panel) {
        return false;
    }
    void* const active = *FieldAt<void**>(panel, K1_PANEL_ACTIVE);
    return !PanelNavigatesItselfK1(panel, active);
}

// One navigation step. Returns true when focus actually moved, which is what
// the end-to-end tests assert on.
bool NavigateFocusK1(int dx, int dy)
{
    if (InputClassK1() != K1_CLASS_PCGUI) {
        return false;              // gameplay: the D-pad has its own bindings
    }
    void* const panel = TopPanelK1();
    if (!panel) {
        return false;
    }
    void* const active = *FieldAt<void**>(panel, K1_PANEL_ACTIVE);
    if (PanelNavigatesItselfK1(panel, active)) {
        ++g_stick.navDeclinedNative;
        return false;
    }
    void* const target = ChooseNeighbourK1(panel, active, dx, dy);
    if (!target || target == active) {
        return false;
    }
    // The engine's own focus mechanism: it clears the previous control's focus,
    // sets the new one, plays the GUI sound, and lets each control draw its own
    // highlight. Nothing here draws anything of its own.
    {
        RectK1 fromRect{};
        RectK1 toRect{};
        ControlIsNavigableK1(active, fromRect);
        ControlIsNavigableK1(target, toRect);
        g_stick.navFromY = fromRect.y;
        g_stick.navToY = toRect.y;
        g_stick.navDir = dx != 0 ? dx * 10 : dy;
    }
    EngineFn<SetActiveControlFn>(K1_SET_ACTIVE_CONTROL)(panel, target, 1);
    ++g_stick.navMoves;
    g_stick.lastNavTick = GetTickCount();
    return true;
}

// ------------------------------------------------- navigation input timing
//
// A held direction should move once immediately, pause, then repeat steadily.
// Those three numbers are the whole feel of menu navigation, so they are named
// rather than buried.
constexpr unsigned long K1_NAV_HOLD_DELAY_MS   = 400;   // before a hold repeats
constexpr unsigned long K1_NAV_REPEAT_MS       = 120;   // between repeats

// The left stick drives the same navigation as the D-pad. Two thresholds, not
// one: it must be pushed past ENGAGE to register a direction and must fall back
// below RELEASE before another can be registered. Without that gap a stick
// resting near the threshold chatters, and a worn stick with resting drift
// would walk through a menu on its own -- which is the specific thing this must
// never do. RELEASE is well below the 8% movement deadzone for the same reason.
constexpr float K1_NAV_STICK_ENGAGE  = 0.55f;
constexpr float K1_NAV_STICK_RELEASE = 0.35f;

// Latch a left-stick direction with hysteresis. Returns the direction the stick
// is currently asking for, or (0, 0).
void UpdateStickNavigationK1(float x, float y)
{
    int wantX = 0;
    int wantY = 0;
    // Whichever axis is pushed further wins, so a diagonal push does not fire
    // both and jump diagonally through a menu.
    const float ax = x < 0.0f ? -x : x;
    const float ay = y < 0.0f ? -y : y;
    if (ax >= ay) {
        if (ax > K1_NAV_STICK_ENGAGE) { wantX = x > 0.0f ? 1 : -1; }
    } else {
        if (ay > K1_NAV_STICK_ENGAGE) { wantY = y > 0.0f ? 1 : -1; }
    }

    // Still held? Keep the latched direction until the stick relaxes.
    if (g_stick.stickNavX != 0 || g_stick.stickNavY != 0) {
        const float along = g_stick.stickNavX != 0 ? ax : ay;
        if (along < K1_NAV_STICK_RELEASE) {
            g_stick.stickNavX = 0;
            g_stick.stickNavY = 0;
        }
        return;
    }
    g_stick.stickNavX = wantX;
    g_stick.stickNavY = wantY;
}

// Called from the buffer hook, which runs in menus as well as in gameplay.
// It only records intent; the move itself happens on the GUI's own frame.
void RequestNavigationK1(int dx, int dy, bool edge)
{
    if (dx == 0 && dy == 0) {
        g_stick.navHeldX = 0;
        g_stick.navHeldY = 0;
        return;
    }
    const unsigned long now = GetTickCount();
    const bool changed = (dx != g_stick.navHeldX) || (dy != g_stick.navHeldY);
    if (edge || changed) {
        // Immediate first move, then wait out the hold delay.
        g_stick.navHeldX = dx;
        g_stick.navHeldY = dy;
        g_stick.navPendingX = dx;
        g_stick.navPendingY = dy;
        g_stick.navRepeatDeadline = now + K1_NAV_HOLD_DELAY_MS;
        return;
    }
    if (now >= g_stick.navRepeatDeadline) {
        g_stick.navPendingX = dx;
        g_stick.navPendingY = dy;
        g_stick.navRepeatDeadline = now + K1_NAV_REPEAT_MS;
    }
}

// The GUI's own per-frame update, hooked so focus moves happen where the engine
// expects GUI work to happen rather than inside CExoInput's polling.
extern "C" void __cdecl NativeGuiFrameK1(void* guiManager)
{
    (void)guiManager;
    g_stick.lastGuiTick = GetTickCount();

    const int dx = g_stick.navPendingX;
    const int dy = g_stick.navPendingY;
    if (dx == 0 && dy == 0) {
        return;
    }
    g_stick.navPendingX = 0;
    g_stick.navPendingY = 0;
    NavigateFocusK1(dx, dy);
}

// ------------------------------------------------------------- engine bridge

void* ClientExoAppK1()
{
    void** const root = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT);
    return root ? root[1] : nullptr;          // [[0x007A39FC]+4]
}

bool InFreeLookK1()
{
    void* const app = ClientExoAppK1();
    return app && EngineFn<ClientExoAppIntFn>(K1_GET_IN_FREE_LOOK)(app) != 0;
}

// Runs from the gameplay heartbeat, not from the input hook.
//
// Two reasons. The buffer hook sits inside CExoInput's own polling, and calling
// back into creature code from there re-enters the engine at a point the router
// never does. And the heartbeat only runs during gameplay, so a click in a menu
// or a cutscene cannot reach the action at all -- which is most of what "safely
// does nothing where flourish is unavailable" means in practice.
//
// A request that nothing consumes is dropped rather than kept. Without that, a
// click pressed in a menu would fire the moment the player returned to the
// world, which is a surprise rather than a feature.
void PerformPendingStickActionsK1()
{
    if (g_stick.flourishRequestedTick == 0) {
        return;
    }
    const unsigned long requested = g_stick.flourishRequestedTick;
    g_stick.flourishRequestedTick = 0;

    if (GetTickCount() - requested > 250ul) {
        ++g_stick.flourishesDeclined;         // stale; the click was elsewhere
        return;
    }

    void* const app = ClientExoAppK1();
    if (!app) {
        ++g_stick.flourishesDeclined;
        return;
    }
    // PlayerFlourishWeapons dereferences the creature without checking it.
    if (EngineFn<ClientExoAppPtrFn>(K1_GET_PLAYER_CREATURE)(app) == nullptr) {
        ++g_stick.flourishesDeclined;
        return;
    }
    // Free look drives the camera, not the character; a flourish there would be
    // acting on a body the player is not currently controlling.
    if (InFreeLookK1()) {
        ++g_stick.flourishesDeclined;
        return;
    }

    EngineFn<ClientExoAppVoidFn>(K1_PLAYER_FLOURISH)(app);
    ++g_stick.flourishesPerformed;
}

extern "C" void __cdecl NativeJoystickMovementK1(void* playerControl)
{
    if (!playerControl) {
        return;
    }
    g_stick.lastMovementTick = GetTickCount();
    g_stick.playerControl = playerControl;
    ++g_stick.movementCalls;
    NativeJoystickDumpK1();

    // Deliberately writes nothing.
    //
    // KOTOR already registers its own analog joystick descriptions -- event
    // 0x08 on DIJOFS_X and event 0x07 on DIJOFS_Y, both description type 3 --
    // and ProcessInput already polls them for movement at 0x006238D3 and
    // 0x006238E5. Once GetJoystickBuffer emits records, those descriptions
    // receive the values and vanilla drives movement by itself, deadzone,
    // scaling and diagonal handling included.
    //
    // An earlier version wrote the stick into playerControl+0x10/+0x14 here as
    // well. That made two writers race for the same two fields every frame,
    // which is what produced movement in every direction at inconsistent
    // speeds. The hook is kept only as a gameplay heartbeat: it tells the older
    // XInput layer when to stand its keystroke synthesis down, and it drives the
    // diagnostic dump.
    g_stick.overrideActive = false;
    float sampleX = 0.0f;
    float sampleY = 0.0f;
    ReadNativeStickK1(sampleX, sampleY);   // diagnostics only

    PerformPendingStickActionsK1();
}

bool NativeMovementOwnsLeftStickK1()
{
    if (!g_stick.registered || g_stick.lastMovementTick == 0) {
        return false;
    }
    // A quarter second is many frames of slack, so a stutter cannot hand the
    // stick back mid-stride, while leaving a menu still releases it promptly.
    return (GetTickCount() - g_stick.lastMovementTick) < 250;
}

// Conditional bypass of Control's own Vector::Normalize at 0x00679B71.
//
// That call exists because the keyboard drives each axis at exactly +/-1, so an
// unnormalised diagonal would travel sqrt(2) times too fast. It is correct for
// digital input and wrong for analog: it would rescale a half-deflected
// diagonal back to full speed, discarding the magnitude ReadNativeStickK1 was
// careful to preserve.
//
// Skipping it is safe, and was verified rather than assumed. Vector::Normalize
// is __thiscall taking only the vector, touches no globals and no engine state,
// balances its own stack (its push ecx is undone by add esp,4), and its return
// value is dead -- the very next instruction overwrites eax. The x87 stack is
// empty at the call site, the preceding fcomp having popped it. So bypassing to
// 0x00679B76 changes nothing except that the vector stays as we wrote it.
//
// Only bypassed when the stick is actually driving this frame. Keyboard and
// mouse still normalise exactly as they always did -- a global patch here would
// give keyboard diagonals sqrt(2) overspeed.
extern "C" int __cdecl NativeJoystickSkipNormalizeK1(void* vector)
{
    // ALWAYS consumes, and that is not an optimisation -- it is required.
    //
    // The five bytes at 0x00679B71 are `call rel32`. A relative branch's target
    // is computed from where it executes, so letting the detour re-run those
    // bytes from its trampoline would call trampoline+0xFFE315BA and crash. An
    // earlier version returned 0 on the keyboard path to "run the original",
    // and it crashed on entering gameplay. Every one of the module's other
    // hooks steals only position-independent instructions; this site cannot.
    //
    // So the keyboard path calls Vector::Normalize here instead, through an
    // absolute function pointer, which is immune to relocation and preserves
    // vanilla behaviour exactly: without it a keyboard diagonal would travel
    // sqrt(2) times too fast.
    // overrideActive is now always false -- see NativeJoystickMovementK1 -- so
    // this always reproduces vanilla. Kept rather than removed because the
    // stolen bytes are a relative call that must not be re-executed from the
    // trampoline; the hook has to stay consuming even when it does nothing new.
    if (!g_stick.overrideActive && vector) {
        EngineFn<NormalizeFn>(K1_VECTOR_NORMALIZE)(vector);
    }
    return 1;
}

// Diagnostic dump. Written from the movement hook a few times a second, so a
// run can be inspected afterwards without holding the game in a debugger while
// trying to reproduce a feel problem.
extern "C" void __cdecl NativeJoystickDumpK1()
{
    static unsigned long nextDump = 0;
    const unsigned long now = GetTickCount();
    if (now < nextDump) {
        return;
    }
    nextDump = now + 500;

    // The engine's live device count, read back rather than assumed: if the
    // count did not take, the poll loop never calls the buffer hook and nothing
    // downstream can work.
    long liveCount = -1;
    if (g_stick.input) {
        liveCount = *IntAt(g_stick.input, K1_INPUT_DEVICE_COUNT);
    }

    char line[512];
    const int written = wsprintfA(
        line,
        "reg=%d createFail=%d count=%ld init=%lu buf=%lu rec=%lu mov=%lu ovr=%lu "
        "raw=(%ld,%ld) poll=(%ld,%ld) add=[%d %d %d %d %d %d] "
        "byclass=[%ld %ld %ld %ld %ld %ld] "
        // ev7/ev8 are the engine's own analog axes. ud/lr and vel are the
        // movement state, scaled by 1000 because wsprintfA has no %f. pc is the
        // player-control pointer, published so a test harness can read those
        // fields live rather than sampling this line twice a second.
        // Stick clicks. fl = free-look bindings that took (bit 0 enter, bit 1
        // exit); flour = performed/declined. Counters are the only honest way
        // to watch a bridge fire: the flourish is an animation, and screen
        // diffing cannot separate it from the character's idle motion.
        "ev7=%ld ev8=%ld ud=%ld lr=%ld vel=(%ld,%ld) pc=%08lX "
        // nav = focus moves this layer performed / presses it left to native
        // navigation. gui = last tick the GUI frame hook ran, which is how the
        // tests tell a menu frame from a gameplay frame.
        "fl=%d flour=%lu/%lu nav=%lu/%lu gui=%lu move=%d->%d dir=%d\r\n",
        g_stick.registered ? 1 : 0, g_stick.createFailed ? 1 : 0, liveCount,
        g_stick.initCalls, g_stick.bufferCalls, g_stick.recordsEmitted,
        g_stick.movementCalls, g_stick.overrideFrames,
        static_cast<long>(g_stick.lastRawX), static_cast<long>(g_stick.lastRawY),
        static_cast<long>(g_stick.lastPollX), static_cast<long>(g_stick.lastPollY),
        g_stick.addResult[0], g_stick.addResult[1], g_stick.addResult[2],
        g_stick.addResult[3], g_stick.addResult[4], g_stick.addResult[5],
        static_cast<long>(g_stick.pollByClass[0]), static_cast<long>(g_stick.pollByClass[1]),
        static_cast<long>(g_stick.pollByClass[2]), static_cast<long>(g_stick.pollByClass[3]),
        static_cast<long>(g_stick.pollByClass[4]), static_cast<long>(g_stick.pollByClass[5]),
        // The engine's OWN analog joystick events, and what the movement code
        // did with them. ev7/ev8 are vanilla descriptions on DIJOFS_Y / DIJOFS_X.
        static_cast<long>(g_stick.input
            ? EngineFn<PollInputFn>(K1_POLL_INPUT)(g_stick.input, 7, K1_CLASS_PC) : 0.0f),
        static_cast<long>(g_stick.input
            ? EngineFn<PollInputFn>(K1_POLL_INPUT)(g_stick.input, 8, K1_CLASS_PC) : 0.0f),
        static_cast<long>(g_stick.playerControl ? *FloatAt(g_stick.playerControl, 0x10) * 1000.0f : 0.0f),
        static_cast<long>(g_stick.playerControl ? *FloatAt(g_stick.playerControl, 0x14) * 1000.0f : 0.0f),
        static_cast<long>(g_stick.playerControl ? *FloatAt(g_stick.playerControl, 0x5C) * 1000.0f : 0.0f),
        static_cast<long>(g_stick.playerControl ? *FloatAt(g_stick.playerControl, 0x60) * 1000.0f : 0.0f),
        static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(g_stick.playerControl)),
        g_stick.freeLookBound, g_stick.flourishesPerformed, g_stick.flourishesDeclined,
        g_stick.navMoves, g_stick.navDeclinedNative, g_stick.lastGuiTick,
        g_stick.navFromY, g_stick.navToY, g_stick.navDir);

    HANDLE file = CreateFileA("kmrp-native-joystick.log", FILE_APPEND_DATA,
                              FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD done = 0;
        WriteFile(file, line, static_cast<DWORD>(written), &done, nullptr);
        CloseHandle(file);
    }
}
