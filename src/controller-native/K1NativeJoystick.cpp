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

// The slot budget is fixed and small: 0x74..0x7E is eleven button slots, and
// 0x7C belongs to the game's own event 0x0B, leaving ten. Twelve pad controls do
// not fit, so Start, L3 and R3 are deliberately left unbound -- no retained
// console event was found for them, and spending a slot on a guess would cost a
// control that has one. They stay on the legacy path.
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
    for (int d = 0; d < K1_DPAD_COUNT; ++d) {
        const std::uint16_t mask = K1_DPAD[d].xinputMask;
        const bool now = (buttons & mask) != 0;
        const bool was = (g_stick.lastButtons & mask) != 0;
        if (now != was) {
            // The direction codes are 0x384, 0x388, 0x38C, 0x390 -- the same
            // values the engine's own POV decoder produces -- reached here
            // through the slot each binding names.
            static const std::uint32_t codes[] = { 0x384, 0x388, 0x38C, 0x390 };
            emit(codes[d], now ? 1 : 0);
        }
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
        "ev7=%ld ev8=%ld ud=%ld lr=%ld vel=(%ld,%ld) pc=%08lX\r\n",
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
        static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(g_stick.playerControl)));

    HANDLE file = CreateFileA("kmrp-native-joystick.log", FILE_APPEND_DATA,
                              FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD done = 0;
        WriteFile(file, line, static_cast<DWORD>(written), &done, nullptr);
        CloseHandle(file);
    }
}
