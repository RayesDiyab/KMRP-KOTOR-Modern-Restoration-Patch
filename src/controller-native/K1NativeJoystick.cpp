// Feed normalized XInput/SDL state into KOTOR's retained joystick pipeline.
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
#include "K1ControllerBackend.h"
#include "K1ControllerLayout.h"
#include "K1Rumble.h"

#include <windows.h>
#include <xinput.h>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

// Defined in vendor/K1XboxControlsXInput.cpp, at global scope. Declared here
// rather than by including that header, and ABOVE the anonymous namespace
// below -- inside it the declaration would take internal linkage and fail
// to resolve, which is exactly what it did.
bool IsControllerInputActiveK1();

// Defined in vendor/K1XboxControls.cpp beside the panel vtables and control
// offsets it reads. Declared here for the same linkage reason as above.
bool MessageBoxCancelHasFocusK1(void* panel);

namespace {

// ---------------------------------------------------------------- engine ABI

constexpr std::uintptr_t K1_CREATE_NEW_EVENT   = 0x005E0E20;  // CExoInputInternal
constexpr std::uintptr_t K1_ADD_EVENT          = 0x005E0FA0;  // CExoInputInternal
constexpr std::uintptr_t K1_POLL_INPUT         = 0x005E23C0;  // PollInput_2
constexpr std::uintptr_t K1_OPERATOR_NEW       = 0x006FA7E6;
constexpr std::uintptr_t K1_OPERATOR_DELETE    = 0x006FA390;
// The CRT free, distinct from operator delete above. Named `_free` in the
// symbol archive, and the same address KPM's grass patch documents as the one
// that guards NULL explicitly.
constexpr std::uintptr_t K1_FREE               = 0x006FB7B2;
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

// The per-pad raw state array, which vanilla never allocates because vanilla
// has no pad. CExoInputInternal+0x140 is the CExoRawInputInternal;
// CExoRawInputInternal+0x30 is the array base; GetLastState indexes it as
// base + (deviceIndex - 2) * 0x74 at 0x005E397F-0x005E3985. Four slots is
// more than the one pad the device count claims, and costs 464 bytes once.
constexpr std::size_t K1_INPUT_RAW_INPUT      = 0x140;
constexpr std::size_t K1_RAW_JOYSTICK_STATE   = 0x30;
constexpr std::size_t K1_RAW_JOYSTICK_STRIDE  = 0x74;
constexpr int         K1_PAD_STATE_SLOTS      = 4;

// Input classes, matching keymap.2da's IC* columns.
// The gameplay HUD's bottom-right action bar is driven through Saul0097's
// existing implementation in vendor/K1XboxControls.cpp, which calls the engine's
// own CSWGuiMainInterface functions:
//
//   getIsSelectable   0x004189D0    can this slot take focus
//   setActiveControl  0x0040A630    move the highlight
//   targetPrevious    0x006884B0    cycle a target-action slot backwards
//   targetNext        0x00688520      "        "        "     forwards
//   personalPrevious  0x0068AF70    cycle a personal/ability slot backwards
//   personalNext      0x0068AFE0      "        "        "      forwards
//   activate          0x0068B970    use the selected action
//
// None of that is reimplemented here. His path feeds those calls from buffered
// KEYBOARD records and therefore needs synthesised arrow keys; KMRP feeds them
// from the D-pad it already has, so nothing is synthesised.
extern "C" void __cdecl KmrpActionBarApplyK1(void* mainInterface, int dx, int dy,
                                             int activate);
extern "C" int  __cdecl KmrpActionBarFocusedK1(void* mainInterface);
extern "C" int  __cdecl KmrpActionBarStateK1(void* mainInterface);
extern "C" void __cdecl KmrpActionBarReleaseK1(void* mainInterface);

// The on-screen prompt layer, also Saul0097's and also unreachable in native
// mode until now: UpdateK1ControllerPrompts was called from DispatchMenuInputK1
// alone, and the device-activity flag it consults was raised from PollXInputK1
// alone. Both are legacy hooks that native mode drops, so every badge table and
// every badge texture in the patch sat there unused.
extern "C" void __cdecl KmrpUpdatePromptsK1();
extern "C" void* __cdecl KmrpDescriptionPaneK1(void* panel);
extern "C" void __cdecl KmrpUpdateCursorK1();
extern "C" void __cdecl KmrpNoteMouseK1(int mouseX, int mouseY);
extern "C" void __cdecl KmrpMarkControllerActiveK1();
extern "C" void __cdecl KmrpNotePadPresentK1(int present);
extern "C" unsigned long __cdecl KmrpDeviceStateK1();
extern "C" void __cdecl KmrpMarkKeyboardMouseK1();
extern "C" void __cdecl KmrpNoteKeyboardK1(void* record, int inputDevice);

constexpr int K1_CLASS_PC       = 0;   // gameplay
constexpr int K1_CLASS_MINIGAME = 1;   // Pazaak, swoop, the turret
constexpr int K1_CLASS_PCGUI  = 2;   // menus
constexpr int K1_CLASS_DIALOG = 3;   // ICDialog -- conversations

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

// Where a Start press goes, chosen on the press (issue #18): the game's own 0x0B
// here and there, but the Map from the world and a close from the in-game menu.
constexpr int K1_START_NATIVE      = 0;
constexpr int K1_START_OPENS_MAP   = 1;
constexpr int K1_START_CLOSES_MENU = 2;

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

// The gameplay verbs, reached through the same router as free look.
// CClientExoAppInternal::HandleInputEvent routes a low console-id switch at
// 0x00621238 and a high PC-id switch at 0x00621254, and eight handlers are
// reached from both. The high id is the keymap.2da action number, which is what
// identifies each one:
//
//   low   high        action        handler calls
//   0x02  0xE0 (224)  Pause         RestoreCamera, SetInputClass
//   0x05  0xCD (205)  SelectNext    CClientExoAppInternal::SelectNearestObject
//   0x06  0xCC (204)  SelectPrev    -- and leaves free look when in it
//   0x09  0xCE (206)  ChangeChar    ChangeCharacterToNextLivingPartyMember
//   0x0A  0xCF (207)  PartyActive   CGuiInGame::ShowSoloModeQuery
//
// SelectPrev IS free-look exit: one event, and the handler at 0x0062184C decides
// by camera mode. So it lives on exactly one button -- see the registration.
constexpr int K1_EVENT_PAUSE        = 0x02;
constexpr int K1_EVENT_SELECT_NEXT  = 0x05;
constexpr int K1_EVENT_SELECT_PREV  = K1_EVENT_FREELOOK_EXIT;
constexpr int K1_EVENT_CHANGE_CHAR  = 0x09;
constexpr int K1_EVENT_PARTY_ACTIVE = 0x0A;

// Changing the party member a MENU is showing, which is a different layer from
// the gameplay verb above: 0x09 goes to CClientExoAppInternal and swaps who the
// player is controlling in the world, while 0xCE is a GUI event the screens
// implement themselves and swaps who the screen is about.
//
// Four panels implement it, and they are exactly the four that carry the pair of
// party portraits in their bottom bar -- read out of the full retained event
// inventory rather than guessed at:
//
//     ABILITIES    dispatcher 0x006AE5F0   handler 0x006AE620
//     CHARACTER    dispatcher 0x006B2250   handler 0x006B2383
//     EQUIP        dispatcher 0x006BA3F0   handler 0x006BA5C3
//     INVENTORY    dispatcher 0x006B3ED0   handler 0x006B3F45
//
// See reverse-engineering/retained-gui-event-inventory.txt, and
// retained-xbox-gui-events.md for how 0x09 and 0xCE were paired to one action.
constexpr int K1_GUI_EVENT_CHANGE_CHAR = 0xCE;

constexpr std::uintptr_t K1_PARTY_SWITCH_PANELS[] = {
    0x006AE5F0,   // ABILITIES -- the Skills / Powers / Feats screen
    0x006B2250,   // CHARACTER
    0x006BA3F0,   // EQUIP
    0x006B3ED0,   // INVENTORY
};
constexpr int K1_PARTY_SWITCH_PANEL_COUNT =
    sizeof(K1_PARTY_SWITCH_PANELS) / sizeof(K1_PARTY_SWITCH_PANELS[0]);

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
    { 0x0020, 0x7A, K1_EVENT_BLACK,       "Back" },   // Black; the Journal sort
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

// What each button does in GAMEPLAY, on the slot it already emits.
//
// No new slot and no change to the buffer: a control slot resolves to whichever
// event is registered for it in the CURRENT input class, so one button carries a
// GUI event in ICPCGUI and a gameplay verb in ICPC. Free look already works this
// way on slot 0x7E.
//
// The cost is that these five slots stop carrying their GUI event in ICPC. For
// LB and RB that is a real trade: 0x39 and 0x3A ARE implemented by the gameplay
// HUD dispatcher, at 0x006E622E and 0x006E6250. Target cycling was judged worth
// more than HUD feedback scrolling. Back, LT and RT lose nothing -- 0x2B, 0x35
// and 0x36 are not implemented by that dispatcher at all, which is exactly why
// those three did nothing in the world before this.
struct GameplayBinding {
    int         slot;
    int         event;
    bool        guiEventInMenus;   // keep this slot's GUI event in ICPCGUI?
    const char* name;
};

constexpr GameplayBinding K1_GAMEPLAY_ACTIONS[] = {
    // LB and RB carry no GUI event in menus. The right stick already scrolls
    // descriptions there -- UpdateDescriptionScrollK1 dispatches 0x39/0x3A
    // straight to the screen's own panel, with its own hold-and-repeat -- so
    // registering the same two events on these slots was a second route to one
    // behaviour. Their descriptions still exist, because ICDialog uses them for
    // computer-terminal scrolling and that DOES arrive through these slots.
    { 0x78, K1_EVENT_SELECT_PREV,  false, "LB"   },   // cycle target backwards
    { 0x79, K1_EVENT_SELECT_NEXT,  false, "RB"   },   // cycle target forwards
    { 0x7A, K1_EVENT_PARTY_ACTIVE, true,  "Back" },   // solo mode query
    { 0x7B, K1_EVENT_CHANGE_CHAR,  true,  "LT"   },   // next living party member
    { 0x7D, K1_EVENT_PAUSE,        true,  "RT"   },   // pause
};
constexpr int K1_GAMEPLAY_ACTION_COUNT =
    sizeof(K1_GAMEPLAY_ACTIONS) / sizeof(K1_GAMEPLAY_ACTIONS[0]);

// Does a gameplay verb own this slot in ICPC? If so the slot's GUI event is
// registered in ICPCGUI only, or one control code would resolve to two events.
inline bool GameplayVerbOwnsSlotK1(int slot)
{
    for (int i = 0; i < K1_GAMEPLAY_ACTION_COUNT; ++i) {
        if (K1_GAMEPLAY_ACTIONS[i].slot == slot) {
            return true;
        }
    }
    return false;
}

// Should this slot's GUI event still be registered in ICPCGUI? False only where
// something else already provides the behaviour in menus.
inline bool GuiEventWantedInMenusK1(int slot)
{
    for (int i = 0; i < K1_GAMEPLAY_ACTION_COUNT; ++i) {
        if (K1_GAMEPLAY_ACTIONS[i].slot == slot) {
            return K1_GAMEPLAY_ACTIONS[i].guiEventInMenus;
        }
    }
    return true;
}

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

// The camera turn. Traced after the physical right stick produced no rotation.
//
// CExoInputInternal+0x3A0 -- the mouse X delta the module used to write -- is
// fetched by UpdateCamera (0x005F5E10) into a stack slot and never read again.
// GetMouseDelta (0x005DF610, single caller) writes +0x3A0 to its first argument
// and +0x3A4 to its second, and UpdateCamera reloads only the second, for the
// mode-gated tilt at 0x0063FCC0. Writing +0x3A0 could never rotate anything.
//
// Horizontal rotation is CSWCModule::RotateCamera, called from UpdateCamera at
// 0x005F601F with the negated event 0x11C axis value and the frame delta the
// caller was given (the global at 0x0078E574, pushed at 0x006039A7). Its
// receiver is [CClientExoAppInternal+0x18], which 0x006039CA confirms by
// calling RotateCamera(0, 0) through the same field when input is suppressed.
//
// Event 0x11C cannot carry the stick instead: it is a live type-4 two-button
// axis on the keyboard device (slots 0x36 / 0x33), and PollInput's type-4 path
// at 0x005E242F recomputes it from those two control states on every poll, so
// there is no value to write. Repointing its slots would take the keyboard's
// own camera turn away. Hence a direct call to the engine's own function.
// Pre-rendered movies. The player object is the global at 0x007A3CF4 and
// CExoMoviePlayerInternal::CancelMovie is 0x00404C40, __thiscall with two stack
// arguments.
//
// Called as CancelMovie(player, 0, 0) on purpose. Its second argument is a
// force flag: non-zero takes the branch at 0x00404C5C and raises the cancel flag
// at [player+0x14] unconditionally, while zero goes through the engine's own
// guard at 0x00404C4D --
//
//     cmp dword ptr [ecx+0x30], 1     ; is this movie cancellable at all
//     jne 0x00404C69                  ; if not, only record the result field
//
// so passing zero honours the game's own rule about which movies may be
// skipped rather than overriding it. The keyboard's Space path does the same.
//
// There is no retained controller event for this: movies own the game loop, so
// CExoInput is not being polled and no description can be delivered. A direct
// bridge from inside the movie loop is the only path, which is why the poll runs
// from a hook inside CExoMoviePlayerInternal::PlayMovieLoop.
constexpr std::uintptr_t K1_MOVIE_PLAYER_PTR   = 0x007A3CF4;
constexpr std::uintptr_t K1_CANCEL_MOVIE       = 0x00404C40;

// The two fields CancelMovie's own guard reads before it will cancel anything.
// They have to be tested HERE as well, because the call is not side-effect free
// when the guard fails -- see NativeMovieFrameK1.
constexpr std::size_t K1_MOVIE_PLAYING     = 0x30;   // CExoMoviePlayerInternal::movie_playing
constexpr std::size_t K1_MOVIE_ENTRY_SKIPPABLE = 0x9C;   // skippable_flags[current entry]

// Movie geometry, for diagnosing the crash reported from play: a vision movie
// that rendered zoomed, ended on a black frame with only the HUD, and died.
//
// The engine sizes the picture at 0x004057AC, which KMRP replaces with the
// aspect-fit stub in .kmv. Vanilla derives the height from the requested width
// and the movie's aspect and never checks it against the window, which is the
// zoom bug the stub exists to fix. The stub instead picks its own target
// rectangle, and then the untouched tail at 0x0040581F-0x0040582C turns the
// result into the blit offsets:
//
//   00405819  mov [esi+0x84], eax    ; horizontal offset
//   0040582C  mov [esi+0x88], eax    ; vertical offset
//   00405867  call BinkBufferSetOffset
//
// Both are (window - picture)/2, so a picture computed LARGER than the window
// makes them negative and Bink blits outside its buffer. That is the shape of
// the reported failure, so these are what to measure. Read rather than assumed:
// this logs the engine's own numbers on the first frame of every movie.
constexpr std::size_t K1_MOVIE_INFO            = 0x48;   // -> {width, height}
constexpr std::size_t K1_MOVIE_WINDOW          = 0x50;   // the HWND Bink blits to

constexpr std::size_t K1_MOVIE_OFFSET_X        = 0x84;
constexpr std::size_t K1_MOVIE_OFFSET_Y        = 0x88;

// A and Start only. Both are conventional "skip" buttons and neither means
// anything else while a movie is on screen. B and LB are equally safe -- nothing
// else consumes them here -- but binding four buttons to one action makes an
// accidental skip likelier, so the extra two are left out until asked for.
constexpr std::uint16_t K1_MOVIE_SKIP_MASK = 0x1000 | 0x0010;   // A | START

constexpr std::uintptr_t K1_ROTATE_CAMERA       = 0x00640090;  // CSWCModule::RotateCamera
constexpr std::uintptr_t K1_CAMERA_FRAME_DELTA  = 0x0078E574;  // what UpdateCamera is passed
constexpr std::size_t    K1_INTERNAL_CAMERA_OWNER = 0x18;      // CClientExoAppInternal+0x18

// World interaction: "do the default action on whatever is targeted".
//
// The retained path exists and is event 0xEF, whose handler at 0x00621FC1
// checks the target at [internal+0x2b4] against OBJECT_INVALID, calls
// CClientExoAppInternal::GetDefaultActions, and executes the first action --
// which is what talks to an NPC, opens a container or uses a door.
//
// It cannot be reached as a native joystick event: descriptions are one per
// event id and 0xEF already carries the keyboard's, on slot 0x44. The router
// lists no low-id console partner for it, unlike 0x0B/0xDF or 0x01/0xD0. So
// this is a bridge -- but a bridge to the engine's *own event router*, not a
// reimplementation: calling HandleInputEvent(0xEF, 1) runs the retained handler
// with every one of its guards intact.
constexpr std::uintptr_t K1_HANDLE_INPUT_EVENT = 0x00621210;  // CClientExoAppInternal
constexpr int K1_EVENT_DEFAULT_ACTION = 0xEF;

// The keyboard's in-game menu hotkeys are events 0xD1-0xD8, and the router's jump
// table sends all eight to one handler (0x006218D5) that computes the screen as
// event - 0xD1 and passes it to CGuiInGame::ShowSWInGameGui. The index is the
// tab's control ID in top.gui -- LBLH_EQU 0 through LBLH_OPT 7 -- and the order
// CGuiInGame keeps its screens in (Lane's header: in_game_equip ... in_game_map,
// in_game_options). So 0xD7 is the Map. Start's own event, 0x0B, passes 7:
// Options, which is why Start used to open the Escape-style menu.
constexpr int K1_EVENT_MENU_MAP = 0xD7;

// Start, with the in-game menu in front, sends B's control code instead of its
// own: B is the close measured from every tab, and B's slot is 0x75.
constexpr std::uint32_t DIJOFS_BUTTON_B_OFFSET = DIJOFS_BUTTON0_OFFSET + (0x75 - 0x74);
constexpr std::size_t K1_INTERNAL_TARGET = 0x2B4;
constexpr std::uint32_t K1_OBJECT_INVALID = 0x7F000000;

using HandleInputEventFn = int(__thiscall*)(void*, int, int);

using ClientExoAppVoidFn = void(__thiscall*)(void*);
using ClientExoAppPtrFn  = void*(__thiscall*)(void*);
using ClientExoAppIntFn  = int(__thiscall*)(void*);

using CreateNewEventFn = int(__thiscall*)(void*, int, int, int, int, int);
using AddEventFn       = int(__thiscall*)(void*, int, int);
using PollInputFn      = float(__thiscall*)(void*, int, int);
using OperatorNewFn    = void*(__cdecl*)(std::size_t);
using FreeFn           = void(__cdecl*)(void*);
using OperatorDeleteFn = void(__cdecl*)(void*);
using NormalizeFn      = void(__thiscall*)(void*);
using RotateCameraFn   = void(__thiscall*)(void*, float, float);
using CancelMovieFn    = void(__thiscall*)(void*, int, int);


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
// A per-axis deadzone would make the stick feel like it snaps to the cardinals
// and could not express a half-deflected diagonal at all, so this is radial.
//
// The value is a **feel decision, not a measurement**, and the measurement is
// worth keeping straight: the physical controller's resting magnitude was
// measured at no more than 1.46% of full scale over 381 samples, so any value
// above about 3% already silences drift completely. 8% did that. 25% is chosen
// deliberately larger, to put the whole low range under the player's thumb
// rather than to fix drift -- it matches the quarter-travel the engine's own
// GetMinUseable threw away, and leaves 75% of the travel for the proportional
// range.
//
// It only became a sensible choice once the analog magnitude actually reached
// the character. While Vector::Normalize was discarding it, every deflection
// past the deadzone ran at full speed, so a larger deadzone would merely have
// moved where the character snapped from a standstill to a sprint.
//
// Tried on a physical controller in this order: 25%, then 15%, then 8%. All
// three sat far above THAT pad's 1.46% resting drift, so the choice looked
// like comfort rather than a drift threshold -- the smaller the value, the
// more of the stick's travel is usable and the finer the slow-walk control.
//
// 8% was wrong, and the premise is why. A second physical pad rests at 9.6%:
// raw=(1091,-2948) is sqrt(1091^2 + 2948^2) / 32767 = 0.096, ABOVE the
// deadzone. Four faults followed from that one fact, and only the first was
// visible as a stick problem:
//
//   * the prompts never handed back to mouse and keyboard, because the
//     device-activity test reused this constant -- now K1_ACTIVITY_STICK;
//   * the character crept while the stick was untouched;
//   * NativeStickVectorK1 returned true every frame, so the drift vector
//     displaced whatever the keyboard had just written to the movement
//     fields -- the "inside the deadzone: keyboard keeps control" path was
//     never taken;
//   * NativeAnalogDrivingK1 stayed true, so NativeJoystickSkipNormalizeK1
//     consumed every call and Vector::Normalize never ran, making keyboard
//     diagonals travel sqrt(2) times too fast.
//
// So a drifting pad quietly broke KEYBOARD movement. A deadzone tuned on one
// pad is a sample of one; this one has to clear the worst pad, not the best.
// 0.15 clears 9.6% with margin and is still well under the engine's own
// quarter-deflection deadzone and under XInput's recommended
// XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE of 7849/32767 = 0.24.
constexpr float K1_STICK_DEADZONE = 0.15f;

// The right stick drives RotateCamera directly, so its value is in the units of
// the engine's own turn axis, where a held keyboard turn key is exactly 1.0.
// Full deflection therefore matches a full keyboard turn. This is not a tuned
// number -- it is the neutral one, chosen so the stick and the keyboard agree.
// The previous value of 14.0 was in mouse pixels, for a field the camera does
// not read; it is not comparable and was never carried over.
constexpr float K1_CAMERA_SPEED = 1.0f;
// No longer 'a touch higher' than the movement deadzone -- that one went to
// 0.15 to clear a pad resting at 9.6%, and this one stayed. It is kept lower
// deliberately: the right stick on the same pad rests at 0.048
// (rx=-376, ry=1525), so 0.12 clears it with margin, and a larger value
// costs fine camera control for no measured benefit. If a right stick is
// ever measured resting above this, raise it the same way.
constexpr float K1_CAMERA_DEADZONE = 0.12f;

// How far a stick must go before the pad counts as the device IN USE. Not a
// deadzone -- nothing is gated on it except which prompts are shown -- and
// deliberately far above both deadzones above.
//
// It used to reuse K1_STICK_DEADZONE, which asks a different question.
// Movement wants the smallest deadzone a pad can bear; activity wants a
// deliberate push. On a pad measured resting at 0.096 -- raw=(1091,-2948)
// against a deadzone of 0.08 -- the old test was true on every frame, so the
// pad always counted as in use and the prompts never hid for mouse and
// keyboard.
constexpr float K1_ACTIVITY_STICK = 0.35f;

struct StickState {
    bool          initialised = false;
    std::int32_t  lastX = 0;
    std::int32_t  lastY = 0;
    std::uint16_t lastButtons = 0;
    unsigned long freeLookExitRequested = 0;   // R3 pressed while in free look
    unsigned long freeLookExits = 0;           // bridged exits performed
    unsigned long partySwitchRequested = 0;    // R3 pressed on a party screen
    unsigned long partySwitches = 0;           // menu party changes performed
    unsigned long lastGuiFrameTick = 0;        // for our own frame delta
    unsigned long slowFrames = 0;              // frames over K1_SLOW_FRAME_MS
    unsigned long worstFrameMs = 0;            // the longest one seen
    unsigned long saveBuffersFreed = 0;        // leaked save buffers reclaimed
    unsigned long guiCuesInstalled = 0;        // cue controls bound
    unsigned long guiCuesRejected = 0;       // binds that did not take
    unsigned long guiCueToggles = 0;         // show/hide flips performed
    unsigned long flourishRequestedTick = 0;   // 0 = nothing pending
    unsigned long flourishesPerformed = 0;
    unsigned long flourishesDeclined = 0;
    int freeLookBound = 0;                     // bit 0 = enter, bit 1 = exit
    unsigned long navMoves = 0;                // focus moves this layer performed
    unsigned long navDeclinedNative = 0;       // presses left to native navigation
    unsigned long lastNavTick = 0;
    unsigned long lastGuiTick = 0;
    int navFromY = -1, navToY = -1, navDir = 0;
    int dialogBound = 0;   // bitmask of ICDialog registrations that took
    int miniGameBound = 0; // bitmask of ICMiniGame registrations that took
    unsigned long interactRequestedTick = 0;
    int           padSlot = -1;                   // XInput slot the pad answered on
    unsigned long rumbleCalls = 0;                // SetRumble calls observed
    unsigned long rumbleSent = 0;                 // XInputSetState calls made
    unsigned long rumbleTableInstalled = 0;       // pattern tables handed over
    int           remapRequestedSlot = 0;         // a button the screen redefines
    std::uint8_t  remapSuppressed = 0;            // which buttons took the remap
    unsigned long remapDispatched = 0;            // remapped presses performed
    unsigned long rumbleLast = 0;                 // last magnitudes, packed 16:16
    unsigned long rumbleRawA = 0;                 // last float bits the engine sent
    unsigned long rumbleRawB = 0;
    unsigned long interactsPerformed = 0;
    unsigned long interactsDeclined = 0;
    std::uint8_t dpadEmitted = 0;   // which direction presses actually went out
    std::uint8_t dpadRepeatMask = 0;           // what the native repeat is tracking
    unsigned long dpadRepeatDeadline = 0;      // when that native press repeats
    unsigned long dpadRepeats = 0;             // native repeats emitted
    unsigned long navRepeatDeadline = 0;       // when a held direction may repeat
    int navHeldX = 0, navHeldY = 0;            // the direction currently held
    int navPendingX = 0, navPendingY = 0;      // requested, not yet performed
    int hudPendingX = 0, hudPendingY = 0;      // the same, for the gameplay HUD
    unsigned long hudActivateRequested = 0;    // A, while a HUD slot has focus
    unsigned long hudReleaseRequested = 0;     // B in gameplay: let go of the HUD
    unsigned long combatClearRequested = 0;    // Y in gameplay: undo the last queued action
    unsigned long disengageRequested = 0;      // X in gameplay: the Disengage button
    unsigned long hudReleases = 0;             // focus handed back to the world
    unsigned long mapOpenRequested = 0;        // Start in gameplay
    unsigned long mapOpens = 0;                // the Map opened by Start
    int           cursorConfined = 0;          // is the mouse clipped right now
    unsigned long cursorConfinements = 0;      // times the clip was taken
    unsigned long cursorReleases = 0;          // times it was given back
    int           startRoute = 0;              // K1_START_*, decided on the press
    int           glyphFamily = 0;             // K1_GLYPH_*, what the badges show
    int           glyphSlot = -2;              // the slot it was decided for; -2 never
    unsigned long long steamInfoWritten = 0;   // Steam's pad file, when last read
    unsigned long steamInfoChecked = 0;        // tick of the last look at its time
    unsigned long glyphChanges = 0;            // family switches seen
    bool          padPresent = false;          // a pad answered this frame
    unsigned long hudMoves = 0;                // slot changes performed
    unsigned long hudCycles = 0;               // action cycles performed
    unsigned long hudActivations = 0;          // slots used
    unsigned long padActiveTicks = 0;          // frames the pad was the live device
    unsigned long promptUpdates = 0;           // prompt refreshes performed
    int           descHeld = 0;                // right stick's latched scroll direction
    unsigned long descDeadline = 0;            // when a held deflection may repeat
    unsigned long descScrolls = 0;             // description scrolls dispatched
    unsigned long hudInterface = 0;            // what the hook was handed
    int           hudState = 0;                // KmrpActionBarStateK1 bits
    int stickNavX = 0, stickNavY = 0;          // left stick's latched direction
    unsigned long cameraFeedCalls = 0;      // times the bridge ran
    unsigned long cameraWrites = 0;         // times it actually wrote
    unsigned long cameraBelowDeadzone = 0;  // times it bailed on the deadzone
    float         cameraApplied = 0.0f;     // last turn amount handed to the engine
    unsigned long cameraWrongClass = 0;     // times it bailed on the input class
    unsigned long cameraNoOwner = 0;        // times there was no live module
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
    unsigned long inputRebuilds = 0;        // times the engine replaced CExoInputInternal
    unsigned long classRetriesTaken = 0;    // per-class registrations won on retry
    unsigned long deviceCountDeferred = 0;  // frames the pad was withheld from the engine
    unsigned long deviceCountRestored = 0;  // times the count had dropped
    unsigned long padStateAllocated = 0;    // times the raw pad state was created
    unsigned long verbsBound = 0;           // gameplay verbs registered in ICPC
    float         rawMagnitude = 0.0f;      // straight from XInput, 0..1
    float         analogMagnitude = 0.0f;   // post-deadzone, 0 when not driving
    unsigned long lastBufferTick = 0;
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
    XINPUT_STATE state{};
    if (ReadControllerK1(state)) {
        g_stick.padSlot = ControllerXInputSlotK1();
        x = state.Gamepad.sThumbLX;
        y = -static_cast<std::int32_t>(state.Gamepad.sThumbLY);
        buttons = state.Gamepad.wButtons;
        rx = state.Gamepad.sThumbRX;
        ry = state.Gamepad.sThumbRY;
        lt = state.Gamepad.bLeftTrigger;
        rt = state.Gamepad.bRightTrigger;
        KmrpNotePadPresentK1(1);
        g_stick.padPresent = true;
        return true;
    }
    g_stick.padSlot = -1;
    KmrpNotePadPresentK1(0);
    g_stick.padPresent = false;
    return false;
}

}  // namespace

// ------------------------------------------------------------- registration

// Is one of our event descriptions still present on this input object?
//
// Comparing the object POINTER is not enough. The engine destroys
// CExoInputInternal around a movie and builds a new one, and the allocator is
// free to hand back the same address for a same-sized block -- in which case a
// pointer test reports "already registered", registration is skipped, and the
// new object carries none of this module's events. That looks like the pad
// half-dying rather than crashing, which is exactly how it presented: the crash
// went away and the triggers stopped.
//
// So ask the object instead. [input+0x128] is the description table indexed by
// event id -- the same table AddEvent reads at 0x005E0FB3/0x005E0FBD -- and
// [input+0x12C] is its length. A null slot for an event we registered means our
// registration is gone, whatever the pointer says.
constexpr std::size_t K1_INPUT_EVENT_TABLE = 0x128;
constexpr std::size_t K1_INPUT_EVENT_COUNT = 0x12C;

bool DescriptionPresentK1(void* input, int eventId)
{
    const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(input);
    if (base < 0x00010000u || base > 0xFFFF0000u) {
        return false;
    }
    auto* const bytes = static_cast<std::uint8_t*>(input);
    void** const table =
        *reinterpret_cast<void***>(bytes + K1_INPUT_EVENT_TABLE);
    const std::int32_t count =
        *reinterpret_cast<std::int32_t*>(bytes + K1_INPUT_EVENT_COUNT);
    const std::uintptr_t tableAddress = reinterpret_cast<std::uintptr_t>(table);
    if (tableAddress < 0x00010000u || tableAddress > 0xFFFF0000u) {
        return false;
    }
    if (eventId < 0 || eventId >= count) {
        return false;
    }
    return table[eventId] != nullptr;
}

void EnsureNativeJoystickK1(void* exoInputInternal)
{
    if (!exoInputInternal) {
        return;
    }
    // Re-register whenever the engine hands us a DIFFERENT object, not once per
    // process. Measured: playing a movie destroys CExoInputInternal and builds a
    // new one --
    //
    //   JOYINIT call=1   input=03F03E60 cached=00000000 registered=0
    //   JOYINIT call=508 input=18F5D008 cached=03F03E60 registered=1
    //
    // -- with the old object's six per-class bitmaps freed in between (CLSREC
    // showed all six ptr=00000000 with their sizes left stale, which is a
    // destructor, not the array's own Resize(0) at 0x00405150: that one zeroes
    // the counts too).
    //
    // A latch on `registered` alone made this function return early on the new
    // object, so g_stick.input went on pointing at freed memory. Two failures
    // followed from that one line: EnsureDeviceCountK1 wrote the device count
    // into the freed block once a frame, and every event this module registers
    // stayed on the dead object while the live one had none -- which is why the
    // pad went dead after a movie, and why the engine's own state query at
    // 0x005E0DFB eventually read through a corrupted heap.
    if (g_stick.registered && exoInputInternal == g_stick.input &&
        DescriptionPresentK1(exoInputInternal, K1_EVENT_JOY_X)) {
        return;                     // our events are still live on this object
    }
    if (g_stick.input != exoInputInternal ||
        !DescriptionPresentK1(exoInputInternal, K1_EVENT_JOY_X)) {
        // A rebuild. Drop every cached fact about the old object before
        // touching the new one; none of it describes the new object, and the
        // old pointer must not be read or written again.
        g_stick.registered = false;
        g_stick.initialised = false;
        for (int cls = 0; cls < 6; ++cls) {
            g_stick.addResult[cls] = 0;
        }
        g_stick.lastButtons = 0;
        g_stick.lastTriggers = 0;
        g_stick.dpadEmitted = 0;
        ++g_stick.inputRebuilds;
    }
    g_stick.input = exoInputInternal;

    auto createEvent = EngineFn<CreateNewEventFn>(K1_CREATE_NEW_EVENT);
    auto addEvent    = EngineFn<AddEventFn>(K1_ADD_EVENT);

    // CreateNewEvent(eventId, descType, device, controlSlot, secondControlSlot).
    // Returns 0 when the event id is already taken, which is why the ids above
    // come from the unregistered console range.
    // `|| DescriptionPresentK1` because CreateNewEvent returns 0 both when the
    // id is genuinely unusable and when the description already exists. Only the
    // first is a failure. Without this, re-registering an object that kept some
    // of our descriptions would bail here and leave the pad half-bound.
    const bool madeX =
        createEvent(exoInputInternal, K1_EVENT_JOY_X, K1_DESC_ANALOG,
                    K1_DEVICE_JOYSTICK, K1_SLOT_JOY_X, K1_SLOT_NONE) != 0 ||
        DescriptionPresentK1(exoInputInternal, K1_EVENT_JOY_X);
    const bool madeY =
        createEvent(exoInputInternal, K1_EVENT_JOY_Y, K1_DESC_ANALOG,
                    K1_DEVICE_JOYSTICK, K1_SLOT_JOY_Y, K1_SLOT_NONE) != 0 ||
        DescriptionPresentK1(exoInputInternal, K1_EVENT_JOY_Y);
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
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0 &&
            !DescriptionPresentK1(exoInputInternal, binding.event)) {
            continue;               // genuinely unusable; leave it alone
        }
        if (GuiEventWantedInMenusK1(binding.slot)) {
            addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        }
        if (!GameplayVerbOwnsSlotK1(binding.slot)) {
            addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        }
        ++g_stick.buttonsBound;
    }

    for (int r = 0; r < K1_TRIGGER_COUNT; ++r) {
        const ButtonBinding& binding = K1_TRIGGERS[r];
        if (createEvent(exoInputInternal, binding.event, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0 &&
            !DescriptionPresentK1(exoInputInternal, binding.event)) {
            continue;
        }
        if (GuiEventWantedInMenusK1(binding.slot)) {
            addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        }
        if (!GameplayVerbOwnsSlotK1(binding.slot)) {
            addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        }
        ++g_stick.buttonsBound;
    }

    for (int d = 0; d < K1_DPAD_COUNT; ++d) {
        const ButtonBinding& binding = K1_DPAD[d];
        if (createEvent(exoInputInternal, binding.event, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, binding.slot, K1_SLOT_NONE) == 0 &&
            !DescriptionPresentK1(exoInputInternal, binding.event)) {
            continue;
        }
        addEvent(exoInputInternal, binding.event, K1_CLASS_PCGUI);
        addEvent(exoInputInternal, binding.event, K1_CLASS_PC);
        ++g_stick.buttonsBound;
    }

    // ICDialog, input class 3.
    //
    // Conversations run in their own input class, and a description is only
    // polled in the classes it was added to. Registering the buttons in the
    // gameplay and GUI classes alone therefore left the whole pad inert in
    // dialogue: measured, every button undelivered, the reply highlight frozen
    // on the first line, while the engine's own handlers sat there working.
    //
    // Only the events with a **proven consumer** are added, read out of the two
    // dialogue dispatchers rather than assumed:
    //
    //   CSWGuiDialog::HandleInputEvent          0x006A7230
    //     0x27 / 0x2D -> 0x006A7266  skip the line while one plays, else choose
    //                                the highlighted reply
    //     0x31 / 0x3D -> 0x006A72B9  previous reply: [panel+0x68] decremented,
    //                                floored at 0
    //     0x32        -> 0x006A72DB  next reply: incremented, capped at
    //                                [panel+0x6C] - 1
    //     everything else falls to the default and does nothing.
    //
    //   CSWGuiDialogComputer::HandleInputEvent  0x006A81E0
    //     0x39 -> re-dispatches 0x31 to the terminal's text control
    //     0x3A -> re-dispatches 0x32
    //     default -> falls through to CSWGuiDialog::HandleInputEvent
    //
    // Note the panel owns the selection index itself; the focused list box never
    // receives these, because the default branch only forwards events 0 and 1.
    // So B, X, Y, Back, Left, Right, the triggers and Start are deliberately NOT
    // registered here -- they have no handler in dialogue and adding them would
    // advertise buttons that do nothing.
    {
        static const int dialogEvents[] = {
            K1_EVENT_A,          // 0x27  select / skip
            0x31,                // D-pad up    -- previous reply
            0x32,                // D-pad down  -- next reply
            K1_EVENT_DESC_UP,    // 0x39 LB -- computer terminal scroll up
            K1_EVENT_DESC_DOWN,  // 0x3A RB -- computer terminal scroll down
        };
        for (int i = 0; i < static_cast<int>(sizeof(dialogEvents) / sizeof(dialogEvents[0])); ++i) {
            if (addEvent(exoInputInternal, dialogEvents[i], K1_CLASS_DIALOG) != 0) {
                g_stick.dialogBound |= (1 << i);
            }
        }
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
        // 0x06 lives on LB, not on R3.
        //
        // It is free-look exit AND SelectPrev -- one event, and the handler at
        // 0x0062184C decides which by camera mode. It can therefore sit on
        // exactly one button, and LB is where target cycling was asked for. So
        // free look is ENTERED with R3 and LEFT with LB.
        //
        // The alternative was a second slot on the same description, keeping the
        // exit on R3 at the cost of R3 in the world firing 0x01 and 0x06
        // together -- entering free look and cycling the target in one press.
        // That was considered and rejected; going back is one slot argument.
        if (createEvent(exoInputInternal, K1_EVENT_FREELOOK_EXIT, K1_DESC_DIGITAL,
                        K1_DEVICE_JOYSTICK, 0x78, K1_SLOT_NONE) != 0) {
            addEvent(exoInputInternal, K1_EVENT_FREELOOK_EXIT, K1_CLASS_FREELOOK);
            ++g_stick.buttonsBound;
            g_stick.freeLookBound |= 2;
        }

        // And the verbs themselves, in the gameplay class only.
        for (int v = 0; v < K1_GAMEPLAY_ACTION_COUNT; ++v) {
            const GameplayBinding& verb = K1_GAMEPLAY_ACTIONS[v];
            if (verb.event != K1_EVENT_SELECT_PREV) {
                // SelectPrev's description is the free-look exit one above.
                if (createEvent(exoInputInternal, verb.event, K1_DESC_DIGITAL,
                                K1_DEVICE_JOYSTICK, verb.slot, K1_SLOT_NONE) == 0 &&
                    !DescriptionPresentK1(exoInputInternal, verb.event)) {
                    continue;
                }
            }
            addEvent(exoInputInternal, verb.event, K1_CLASS_PC);
            ++g_stick.verbsBound;
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

    // ICMiniGame, input class 1.
    //
    // Registered on the same rule as ICDialog: only events with a consumer that
    // was read out of a dispatcher, never the whole pad. From the retained
    // inventory --
    //
    //   PAZAAK_SETUP  0x006816F0   0x28/0x2E -> 0x0068175C   leave the table
    //                              0x2A      -> 0x006817BC   the Y action
    //                              0x35      -> 0x006817D6   previous
    //                              0x36      -> 0x0068180B   next
    //   PAZAAK_GAME   0x0067E8F0   0x28/0x2E -> 0x0067E90F   end turn / leave
    //
    // so B, Y and the two bumpers have somewhere to go and A does not: neither
    // minigame dispatcher implements 0x27, and adding it would send a press into
    // a default case. The analog axes are already registered in all six classes.
    //
    // NOT VERIFIED IN PLAY. Pazaak, swoop and the turret cannot be reached from
    // the save the harness loads, so this is registration on measured evidence
    // rather than a demonstrated button press, and it is listed as such in
    // docs/controller-behaviour-matrix.md.
    {
        static const int miniGameEvents[] = {
            K1_EVENT_B,            // 0x28  leave the table / end turn
            K1_EVENT_Y,            // 0x2A  the setup screen's Y action
            K1_EVENT_PREV_SCREEN,  // 0x35  previous
            K1_EVENT_NEXT_SCREEN,  // 0x36  next
        };
        for (std::size_t i = 0; i < sizeof(miniGameEvents) / sizeof(miniGameEvents[0]); ++i) {
            if (addEvent(exoInputInternal, miniGameEvents[i], K1_CLASS_MINIGAME) != 0) {
                g_stick.miniGameBound |= (1 << i);
            }
        }
    }

    g_stick.registered = true;
}


// Defined further down with the focus-navigation layer; declared here because
// the record emitter feeds them.
bool KmrpOwnsDirectionsK1(bool vertical);
template <typename T> T* FieldAt(void* base, std::size_t offset);
bool LooksLikePointerK1(const void* p);
bool IsReadableK1(const void* p, std::size_t size);
void* ClientInternalK1();
int InputClassK1();
void EnsureDeviceCountK1();
void EnsurePadStateK1();
int RemappedButtonEventK1(int slot);
void PerformPendingFreeLookExitK1();
void PerformPendingPartySwitchK1();
void PerformPendingMapOpenK1();
void* TabBarPanelK1();
void InstallGuiCuesK1(void* panel);
bool PressHudButtonK1(void* mainInterface, std::size_t member, std::uintptr_t handler);
// The HUD's combat buttons and their click handlers; see PressHudButtonK1.
constexpr std::uintptr_t K1_MAIN_INTERFACE_VTABLE = 0x00753F50;
constexpr std::size_t    K1_HUD_CLEAR_ONE         = 0x6CD0;      // BTN_CLEARONE
constexpr std::size_t    K1_HUD_CLEAR_ALL         = 0x7058;      // BTN_CLEARALL, "Disengage"
constexpr std::uintptr_t K1_ON_CLEAR_ONE          = 0x0068B050;  // CSWGuiMainInterface::OnClearOneButtonPressed
constexpr std::uintptr_t K1_ON_CLEAR_ALL          = 0x0068B0A0;  // CSWGuiMainInterface::OnClearAllButtonPressed
void ForgetGuiCuesK1(void* panel);
void UpdateGuiCuesK1();
void EnsureRumbleTableK1(void* owner);
void UpdateStickNavigationK1(float x, float y);
void RequestNavigationK1(int dx, int dy, bool edge, bool fromDpad);
// ------------------------------------------------- navigation input timing
//
// A held direction should move once immediately, pause, then repeat steadily.
// Those two numbers are the whole feel of menu navigation, so they are named
// rather than buried. Declared here rather than beside the navigation code
// because the record emitter below needs them too: it repeats the presses the
// ENGINE consumes, using the same cadence, so a held D-pad feels identical
// whichever layer is handling the screen.
constexpr unsigned long K1_NAV_HOLD_DELAY_MS   = 400;   // before a hold repeats
constexpr unsigned long K1_NAV_REPEAT_MS       = 120;   // between repeats

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
    g_stick.rawMagnitude = magnitude;
    g_stick.analogMagnitude = 0.0f;
    g_stick.lastBufferTick = GetTickCount();
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
        // How far the stick is actually driving, after the deadzone. This is
        // what decides whether the engine's Normalize is skipped: a centred
        // stick, or one inside the deadzone, must leave vanilla alone. On a
        // disconnect the XInput read fails, x and y stay zero, and this stays
        // zero with it.
        if (ex != 0 || ey != 0) {
            g_stick.analogMagnitude = scaled;
        }
    }
    // Buttons stay edge-triggered, unlike the axes. The engine's own button
    // loop emits only on change, and the digital store path writes the value
    // rather than accumulating it, so a held button needs no repeat.
    for (int b = 0; b < K1_BUTTON_COUNT; ++b) {
        const std::uint16_t mask = K1_BUTTONS[b].xinputMask;
        const bool now = (buttons & mask) != 0;
        const bool was = (g_stick.lastButtons & mask) != 0;
        if (now == was) {
            continue;
        }
        // A screen may redefine a button -- the Journal's A and Y, whose badges
        // and whose engine events disagree. The native code is suppressed so the
        // press means one thing, and the replacement is dispatched on the GUI
        // frame rather than here, because it rebuilds the list.
        //
        // Decided at the PRESS and remembered, like the direction codes: deciding
        // again at the release would let a screen change mid-press leave a
        // digital description holding a value nothing clears.
        const std::uint8_t bit = static_cast<std::uint8_t>(1u << b);
        if (now) {
            const int remapped = RemappedButtonEventK1(K1_BUTTONS[b].slot);
            if (remapped != 0) {
                g_stick.remapSuppressed |= bit;
                g_stick.remapRequestedSlot = K1_BUTTONS[b].slot;
                continue;
            }
            emit(DIJOFS_BUTTON0_OFFSET + static_cast<std::uint32_t>(b), 1);
        } else if ((g_stick.remapSuppressed & bit) != 0) {
            g_stick.remapSuppressed &= static_cast<std::uint8_t>(~bit);
        } else {
            emit(DIJOFS_BUTTON0_OFFSET + static_cast<std::uint32_t>(b), 0);
        }
    }
    // Whether the native direction codes go out at all. On a screen the engine
    // navigates properly they must; on one this layer navigates they must not,
    // or focus moves twice for one press.
    // Asked per axis: a focused horizontal slider keeps Left/Right for its value
    // while KMRP takes Up/Down (see ControlOwnsAxisK1).
    const bool kmrpVertical = KmrpOwnsDirectionsK1(true);
    const bool kmrpHorizontal = KmrpOwnsDirectionsK1(false);

    // The direction codes are 0x384, 0x388, 0x38C, 0x390 -- the same values the
    // engine's own POV decoder produces -- reached here through the slot each
    // binding names. Hoisted out of the loop because the repeat below needs them.
    static const std::uint32_t codes[] = { 0x384, 0x388, 0x38C, 0x390 };

    for (int d = 0; d < K1_DPAD_COUNT; ++d) {
        const std::uint16_t mask = K1_DPAD[d].xinputMask;
        const bool now = (buttons & mask) != 0;
        const bool was = (g_stick.lastButtons & mask) != 0;
        if (now != was) {
            const std::uint8_t bit = static_cast<std::uint8_t>(1u << d);
            if (now) {
                // Suppression is decided once, at the press, and remembered.
                // Deciding it again at the release would let a screen change
                // mid-press emit a press with no matching release, and a
                // digital description that never sees its zero stays stuck on.
                // K1_DPAD order is Up, Down, Left, Right.
                const bool kmrpOwns = d < 2 ? kmrpVertical : kmrpHorizontal;
                if (!kmrpOwns) {
                    emit(codes[d], 1);
                    g_stick.dpadEmitted |= bit;
                }
            } else if ((g_stick.dpadEmitted & bit) != 0) {
                emit(codes[d], 0);
                g_stick.dpadEmitted &= static_cast<std::uint8_t>(~bit);
            }
        }
    }

    // A held direction repeats on the screens the ENGINE navigates.
    //
    // Its list boxes act on the press and nothing after it -- there is no
    // auto-repeat anywhere in CSWGuiListBox -- so holding Down moved exactly one
    // row and stopped. Reported on Quest Items, which is one of the screens that
    // reaches the engine: NavigateFocusK1 stands down when a focused control
    // navigates itself and the screen has no tab strip, and KmrpOwnsDirectionsK1
    // agrees, so the native code goes out and this layer does not act.
    //
    // Only where the engine owns the press. Where KMRP owns it the repeat
    // already exists in RequestNavigationK1, and emitting here as well would
    // deliver the direction twice -- the same double-step that
    // KmrpOwnsDirectionsK1 exists to prevent. dpadEmitted is exactly the set of
    // presses that actually went out, so testing it tests the real condition
    // rather than re-deriving it.
    //
    // Released and re-pressed rather than pressed again, because a second press
    // with no intervening release is not a new press: the engine's button state
    // is already set and the edge it acts on never arrives.
    if (g_stick.dpadEmitted != 0) {
        const unsigned long nowTicks = GetTickCount();
        if (g_stick.dpadEmitted != g_stick.dpadRepeatMask) {
            // A new or changed direction: move once, then wait out the delay.
            g_stick.dpadRepeatMask = g_stick.dpadEmitted;
            g_stick.dpadRepeatDeadline = nowTicks + K1_NAV_HOLD_DELAY_MS;
        } else if (nowTicks >= g_stick.dpadRepeatDeadline) {
            for (int d = 0; d < K1_DPAD_COUNT; ++d) {
                if ((g_stick.dpadEmitted & static_cast<std::uint8_t>(1u << d)) != 0) {
                    emit(codes[d], 0);
                    emit(codes[d], 1);
                    ++g_stick.dpadRepeats;
                }
            }
            g_stick.dpadRepeatDeadline = nowTicks + K1_NAV_REPEAT_MS;
        }
    } else {
        g_stick.dpadRepeatMask = 0;
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
        bool fromDpad = false;
        for (int d = 0; d < K1_DPAD_COUNT; ++d) {
            const std::uint16_t mask = K1_DPAD[d].xinputMask;
            if ((buttons & mask) != 0) {
                dx = dirs[d][0];
                dy = dirs[d][1];
                fromDpad = true;
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
        RequestNavigationK1(dx, dy, edge, fromDpad);
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

    // Start is a Map toggle (issue #18). In the world it opens the Map: the
    // engine's own Map hotkey, 0xD7, bridged on the frame because it has no
    // joystick description and every free slot is spent -- instead of Start's own
    // 0x0B, which opens Options. With the in-game menu in front it sends B, the
    // close measured from every tab, so Start shuts the Map or whichever screen
    // LT/RT moved to. Anywhere else it is still the game's own Start. The route is
    // chosen on the press and kept for the release, so a press and its release
    // always go to the same place, and only ever one place.
    {
        const bool now = (buttons & XINPUT_START_MASK) != 0;
        const bool was = (g_stick.lastButtons & XINPUT_START_MASK) != 0;
        if (now && !was) {
            const int inputClass = InputClassK1();
            g_stick.startRoute = inputClass == K1_CLASS_PC ? K1_START_OPENS_MAP
                : (inputClass == K1_CLASS_PCGUI && TabBarPanelK1() != nullptr) ? K1_START_CLOSES_MENU
                : K1_START_NATIVE;
        }
        if (now != was) {
            switch (g_stick.startRoute) {
            case K1_START_OPENS_MAP:
                if (now) {
                    g_stick.mapOpenRequested = GetTickCount();
                }
                break;
            case K1_START_CLOSES_MENU:
                emit(DIJOFS_BUTTON_B_OFFSET, now ? 1 : 0);
                break;
            default:
                emit(DIJOFS_BUTTON8_OFFSET, now ? 1 : 0);
                break;
            }
        }
    }

    // B lets go of the bottom-right action bar (issue #17). B does nothing else
    // in the world, so no press is taken from anything; the release is made on
    // the HUD frame and only when one of its slots has focus.
    {
        const bool now = (buttons & 0x2000) != 0;      // XINPUT_GAMEPAD_B
        const bool was = (g_stick.lastButtons & 0x2000) != 0;
        if (now && !was && InputClassK1() == K1_CLASS_PC) {
            g_stick.hudReleaseRequested = GetTickCount();
        }
    }

    // X and Y press the HUD's combat buttons: Y removes the last queued action
    // (BTN_CLEARONE), X disengages (BTN_CLEARALL). Only requested here; they are
    // pressed on the HUD frame, NativeActionBarK1, through the engine's own click
    // handlers, and only while the button is on screen. Their GUI events 0x29
    // and 0x2A still go out, and gameplay still ignores them.
    {
        const bool xNow = (buttons & 0x4000) != 0;     // XINPUT_GAMEPAD_X
        const bool xWas = (g_stick.lastButtons & 0x4000) != 0;
        const bool yNow = (buttons & 0x8000) != 0;     // XINPUT_GAMEPAD_Y
        const bool yWas = (g_stick.lastButtons & 0x8000) != 0;
        if (InputClassK1() == K1_CLASS_PC) {
            if (xNow && !xWas) {
                g_stick.disengageRequested = GetTickCount();
            }
            if (yNow && !yWas) {
                g_stick.combatClearRequested = GetTickCount();
            }
        }
    }

    // A also asks for the world-interaction bridge. The native 0x27 above is
    // still emitted and still reaches whatever has focus; in gameplay nothing
    // does, which is why A did nothing in the world before this. Only the
    // request is made here -- the call happens on the gameplay frame.
    //
    // Only while gameplay owns the input, the same gate B uses above. The
    // consumer checks the class too, but it checks it when it runs, and a press
    // that answered a modal dialog outlives the dialog: closing it returns the
    // class to gameplay well inside the request's 250 ms window, so the press
    // that dismissed a confirmation went on to act on the world behind it.
    // Answering "do you wish to turn Solo Mode on?" then started a conversation
    // with whoever was targeted. Reported as issue #21.
    {
        const bool now = (buttons & 0x1000) != 0;      // XINPUT_GAMEPAD_A
        const bool was = (g_stick.lastButtons & 0x1000) != 0;
        if (now && !was && InputClassK1() == K1_CLASS_PC) {
            g_stick.interactRequestedTick = GetTickCount();
            // And of the gameplay HUD, which takes it only when a slot has
            // focus.
            g_stick.hudActivateRequested = GetTickCount();
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
            // In free look the native event is not the one we want. 0x01 is
            // registered in ICPC only -- entering switches the class to
            // ICFreeLook, where it is no longer polled -- so emitting it here
            // would do nothing at all. The exit is bridged instead, on the
            // gameplay frame, and the code is suppressed so the press means one
            // thing.
            if (InputClassK1() == K1_CLASS_FREELOOK) {
                if (now) {
                    g_stick.freeLookExitRequested = GetTickCount();
                }
                break;
            }
            // In a menu R3 means "show me the next party member", on the four
            // screens that are about a party member. Requested here and
            // performed on the GUI frame: the handlers rebuild the screen.
            //
            // The native code is suppressed rather than sent alongside. It does
            // nothing in a menu -- free-look enter is registered in ICPC only,
            // so this slot is not polled in ICPCGUI -- but one press meaning one
            // thing is the rule everywhere else in this file.
            if (InputClassK1() == K1_CLASS_PCGUI) {
                if (now) {
                    g_stick.partySwitchRequested = GetTickCount();
                }
                break;
            }
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

    // The pad is the live device the moment it does anything meaningful. Same
    // test as the legacy path's: any button, either trigger past its threshold,
    // or either stick past the engage threshold -- not mere connection, and not
    // resting drift, which would pin the prompts on forever.
    {
        // Deliberately NOT the movement deadzone. That one is as small as a pad
        // can bear so the character answers a light push; this one decides which
        // device the prompts follow, and anything near the movement deadzone
        // pins them on for a pad that rests off centre.
        //
        // Measured on a real pad: raw=(1091,-2948) at rest is a magnitude of
        // 0.096 against a movement deadzone of 0.08, so the old test was true
        // every frame and the prompts never hid for mouse and keyboard.
        const bool meaningful =
            buttons != 0 ||
            lt > K1_TRIGGER_THRESHOLD || rt > K1_TRIGGER_THRESHOLD ||
            std::sqrt(nx * nx + ny * ny) > K1_ACTIVITY_STICK ||
            (std::sqrt(static_cast<float>(rx) * rx + static_cast<float>(ry) * ry)
             / K1_AXIS_FULL_SCALE) > K1_ACTIVITY_STICK;
        if (meaningful) {
            KmrpMarkControllerActiveK1();
            ++g_stick.padActiveTicks;
        }
    }

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
void FeedNativeCameraK1(void* clientInternal)
{
    ++g_stick.cameraFeedCalls;
    if (!LooksLikePointerK1(clientInternal)) {
        clientInternal = ClientInternalK1();
        if (!clientInternal) {
            ++g_stick.cameraNoOwner;
            return;
        }
    }

    // Only where the engine turns the camera itself. UpdateCamera is skipped
    // entirely in the minigames (0x0060399A tests the input class against 1),
    // and a GUI screen owning the input is not turning the world camera.
    const int inputClass = *FieldAt<int>(clientInternal, 0x9C);
    if (inputClass != K1_CLASS_PC && inputClass != K1_CLASS_FREELOOK) {
        ++g_stick.cameraWrongClass;
        g_stick.cameraApplied = 0.0f;
        return;
    }

    const float nx = static_cast<float>(g_stick.rightX) / K1_AXIS_FULL_SCALE;
    const float ny = static_cast<float>(g_stick.rightY) / K1_AXIS_FULL_SCALE;
    const float magnitude = std::sqrt(nx * nx + ny * ny);
    if (magnitude <= K1_CAMERA_DEADZONE) {
        ++g_stick.cameraBelowDeadzone;
        g_stick.cameraApplied = 0.0f;
        return;
    }

    void* const owner = *FieldAt<void*>(clientInternal, K1_INTERNAL_CAMERA_OWNER);
    if (!LooksLikePointerK1(owner)) {
        ++g_stick.cameraNoOwner;
        return;                 // no live module: RotateCamera has no receiver
    }

    // Radial, and rescaled like the left stick so the first movement past the
    // deadzone starts from a standstill rather than jumping.
    const float scaled = (magnitude - K1_CAMERA_DEADZONE) / (1.0f - K1_CAMERA_DEADZONE);
    const float amount = nx * ((scaled > 1.0f ? 1.0f : scaled) / magnitude) * K1_CAMERA_SPEED;

    // Not negated. UpdateCamera does negate its axis at 0x005F6018, but its
    // axis is event 0x11C, whose two-button description already runs opposite
    // to the stick; mirroring the fchs as well flipped left and right, which a
    // playtest caught. Measured in the game, not reasoned from the listing.
    //
    // The engine's own camera-invert option at 0x00832920 is deliberately not
    // read here yet -- it has not been tested against the stick, and guessing
    // at it is what produced this bug in the first place.
    const float delta = *reinterpret_cast<const float*>(K1_CAMERA_FRAME_DELTA);
    EngineFn<RotateCameraFn>(K1_ROTATE_CAMERA)(owner, amount, delta);

    g_stick.cameraApplied = amount;
    ++g_stick.cameraWrites;
}

extern "C" void __cdecl NativeJoystickInitK1(void* exoInputInternal)
{
    EnsureNativeJoystickK1(exoInputInternal);
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
// Movie playback state. Separate from the pad state because the movie loop owns
// the game loop: none of the other hooks run while it is up.
struct MovieStateK1 {
    void*         player = nullptr;   // the movie this state describes
    bool          armed = false;      // a release has been seen since it started
    unsigned long skips = 0;          // cancels actually issued
    unsigned long frames = 0;         // loop iterations observed
    unsigned long refused = 0;        // presses on a movie that may not be skipped
    unsigned long windowsPainted = 0;   // black-filled windows, one per entry
    bool          classBlackened = false;  // SWMovieWindow has a brush now
    // The last geometry logged. PlayMovieList loops over its entries reusing one
    // player object, so keying the log on the player alone logs the first entry
    // of a playlist and silently skips the rest -- which is how the first run of
    // this probe measured three startup logos and missed the movie under
    // investigation entirely. Geometry is recomputed per entry, so watch that.
    std::int32_t lastW = -1, lastH = -1, lastOffX = -1, lastOffY = -1;
};

MovieStateK1 g_movie;

// Make the movie window black, and keep it black.
//
// The grey flash before and after a movie is the window CLASS, and the Ghidra
// archive says so outright. CExoMoviePlayerInternal::InitializeMovie registers
// "SWMovieWindow" at 0x004053E0, and the WNDCLASSA it fills in leaves
// hbrBackground NULL:
//
//   0040545C  mov dword ptr [esp+0x4c], ebx   ; ebx is 0 here -- no brush
//   00405464  mov dword ptr [esp+0x54], 0x73d7fc   ; "SWMovieWindow"
//
// Its window procedure at 0x00405190 handles WM_ACTIVATEAPP, WM_KEYDOWN,
// WM_SYSKEYDOWN and the mouse messages and hands everything else to
// DefWindowProc, so WM_ERASEBKGND is never handled either -- and with a NULL
// brush DefWindowProc erases nothing. The window is created WS_POPUP |
// WS_VISIBLE over the whole screen at 0x00405536, so from that moment until
// Bink's first blit, and again from the last blit until DestroyWindow in
// ShutDown at 0x00404C01, what is on screen is whatever was already in that
// memory. That is the flash, and it is grey because nothing ever painted it.
//
// The main game window does not have this problem: InitOpenGLWindow asks for
// GetStockObject(4) -- BLACK_BRUSH -- at 0x00403779. The movie window is the
// one class BioWare left without one.
//
// So give the class a brush. That is the whole fix rather than a patch over it:
// the class is registered once, on the first movie of the session, and every
// movie window afterwards is created with it. The FillRect is for the window
// that already exists by the time this first runs, since a class brush only
// affects the next erase.
//
// A stock brush is process-wide, is never deleted, and may be handed to a
// window class safely even though the class outlives every window on it.
void BlackenMovieWindowK1(void* player)
{
    if (!LooksLikePointerK1(player)) {
        return;
    }
    HWND const window = *FieldAt<HWND>(player, K1_MOVIE_WINDOW);
    if (!IsWindow(window)) {
        return;
    }
    HBRUSH const black = static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH));
    if (!g_movie.classBlackened) {
        SetClassLongPtrA(window, GCLP_HBRBACKGROUND,
                         reinterpret_cast<LONG_PTR>(black));
        g_movie.classBlackened = true;
    }
    HDC const dc = GetDC(window);
    if (!dc) {
        return;
    }
    RECT client;
    if (GetClientRect(window, &client)) {
        FillRect(dc, &client, black);
        ++g_movie.windowsPainted;
    }
    ReleaseDC(window, dc);
}

// ------------------------------------------------------ the rumble pattern table
//
// The engine's rumble subsystem is complete and running; one field stops it.
// CClientExoAppInternal::PlayRumblePattern tests the caller's index against the
// pattern COUNT before it does anything else:
//
//     005FB49F  cmp ebp, dword ptr [ecx+0x344]
//     005FB4A5  jge 0x5fb536                      -> return 0, nothing queued
//
// and on PC that count is zero for the life of the process, so every rumble the
// game asks for is dropped at the door. Two writes to those fields exist in the
// whole class -- the constructor zeroing them (0x005FC15C, 0x005FC168) and the
// destructor freeing and re-zeroing (0x005FC82A, 0x005FC844). Nothing loads a
// table, because the loader went with the Xbox build.
//
// Providing one is the entire fix. PlayRumblePattern then appends an instance,
// UpdateRumble walks the list every frame taking each motor's maximum through
// CSWRumblePattern::GetMagnitudes, and SetRumble is handed the pair -- where the
// detour already on 0x005F7617 forwards it to XInput.
//
// The layout is read out of GetMagnitudes (0x0068FDD0) and the envelope
// evaluator it calls twice (0x0068FCB0):
//
//     envelope, 0x10 bytes
//       +0x00  float* magnitudes
//       +0x04  float* times, in seconds; the end test reads times[count-1]
//       +0x08  int    count
//       +0x0C  int    cursor -- the evaluator CACHES its segment here
//
//     pattern, 0x24 bytes
//       +0x00  envelope A, the first magnitude out
//       +0x10  envelope B, the second
//       +0x20  int loop
//
// The evaluator interpolates linearly between the two keyframes bracketing the
// elapsed time (0x0068FD96-0x0068FDB7), and GetMagnitudes reports the pattern
// finished -- returning 0, which makes UpdateRumble drop the instance -- once
// the time is past the last keyframe of both envelopes and loop is clear.

struct RumbleEnvelopeK1 {
    const float* magnitudes;
    const float* times;             // seconds, ascending, first entry 0
    int          count;
    int          cursor;            // the engine writes this; not ours to read
};

struct RumblePatternK1 {
    RumbleEnvelopeK1 heavy;         // envelope A -> the low-frequency motor
    RumbleEnvelopeK1 light;         // envelope B -> the high-frequency motor
    int              loop;
};

static_assert(sizeof(RumbleEnvelopeK1) == 0x10, "envelope must be 0x10 bytes");
static_assert(sizeof(RumblePatternK1) == 0x24, "pattern must be 0x24 bytes");

constexpr std::size_t K1_INTERNAL_RUMBLE_TABLE = 0x340;
constexpr std::size_t K1_INTERNAL_RUMBLE_COUNT = 0x344;

// BioWare's own table: K1's rumble.2da, all 22 rows, as published by the OpenKotOR
// wiki (wiki/odyssey-engine/2da/rumble-k1.md). The PC build ships neither the
// file nor a loader for it -- the loader went with the Xbox build -- so the rows
// are compiled in here, generated from that page and validated row by row:
// every sample count matches its filled cells, times ascend and magnitudes stay
// in 0..1. The l* columns are envelope A and the r* columns envelope B, because
// UpdateRumble calls SetRumble(0, A, B, 600000) at 0x005F7626 and XInput takes
// (left, right) in that order. Left is the heavy, low-frequency motor on an Xbox
// pad.
//
// Until 2026-09-25 this held nine shapes KMRP had authored, for the indices
// shipped content asks for, with every other index silent. The comment then
// said BioWare's envelopes could not be recovered from the PC files. They were
// never in them, but they are in this table, and its row names confirm the
// indices: 14 is FragGenade (the grenade VFX), 12 Ceiling (k_pkor_ceil_fall),
// 15 and 16 Endar_01/02 (the k_pend_ scripts), and 17 Heavy_step (the Stomp
// footsteps).
//
// How the evaluator (0x0068FCB0) and GetMagnitudes (0x0068FDD0) read the data,
// so that it reads exactly as authored:
//   * an envelope with no samples has null pointers and count 0. The evaluator
//     returns 0.0 for a null pointer (0x0068FCB9, 0x0068FCC3), and
//     GetMagnitudes' end test reads times[count-1] only when that index is in
//     range, otherwise 0.0 (0x0068FE0B-0x0068FE1B);
//   * before an envelope's first keyframe the segment search finds nothing and
//     returns 0.0 (0x0068FDBF), so a late start -- Endar_01's left motor at
//     5.5 s -- is silence until then, as authored;
//   * `looping` wraps the elapsed time by the last keyframe's time. Rows 0
//     (LightSaberOn) and 21 (Whirlwind) loop. Nothing in the shipped PC content
//     plays either: the only callers are the script command (0x00541120), a
//     client message (0x004FF94D) and the positional wrapper (0x005FBBC4), all
//     with the index as data. So a loop runs only if a mod asks for it, until
//     StopRumblePattern -- which is what the table says it should do.
//
// Since the Enhanced haptics pass (2026-09-25) the rows live in K1Rumble.cpp,
// and the engine's own instance list is bypassed: a hook on PlayRumblePattern
// hands every play to the mixer there, which evaluates these rows the same way
// and also attaches rows 0 and 21 to the saber and Whirlwind. The table is still
// installed here, so that without that hook the engine plays it itself.

// Install it once, and again if the object is ever rebuilt -- the destructor
// frees the table and zeroes both fields, so the null test picks a new one up by
// itself. Never over a table the engine owns: if either field is already set,
// something loaded one and this has no business replacing it.
void EnsureRumbleTableK1(void* owner)
{
    void* const internal = ClientInternalK1();
    if (!internal || internal != owner) {
        // Not an inference. The pointer stored below is one the engine's
        // destructor hands to free(), so putting it on the wrong object would
        // be heap corruption rather than a harmless miss. `owner` is
        // UpdateRumble's own `this`, straight out of ebp.
        return;
    }
    void** const slot = FieldAt<void*>(internal, K1_INTERNAL_RUMBLE_TABLE);
    int* const count = FieldAt<int>(internal, K1_INTERNAL_RUMBLE_COUNT);
    if (*slot != nullptr || *count != 0) {
        return;
    }
    const std::size_t bytes = sizeof(RumblePatternK1) * K1_RUMBLE_PATTERN_COUNT;
    auto* const patterns = static_cast<RumblePatternK1*>(
        EngineFn<OperatorNewFn>(K1_OPERATOR_NEW)(bytes));
    if (!patterns) {
        return;
    }
    std::memset(patterns, 0, bytes);
    for (int index = 0; index < K1_RUMBLE_PATTERN_COUNT; ++index) {
        const RumbleRowK1* const row = KmrpBioWareRumbleRowK1(index);
        if (!row) {
            continue;               // unreachable as written; cheap to keep true
        }
        RumblePatternK1& pattern = patterns[index];
        pattern.heavy = { row->heavyMagnitudes, row->heavyTimes, row->heavyCount, 0 };
        pattern.light = { row->lightMagnitudes, row->lightTimes, row->lightCount, 0 };
        pattern.loop = row->loop;
    }
    // Pointer before count, because the count is what PlayRumblePattern gates on
    // and it reads the pointer immediately after passing that gate.
    *slot = patterns;
    *count = K1_RUMBLE_PATTERN_COUNT;
    ++g_stick.rumbleTableInstalled;
}

// The engine's rumble, routed to XInput.
//
// KOTOR still runs the Xbox build's rumble subsystem: UpdateRumble at
// 0x005F7500 walks the active pattern list every frame, takes the maximum of
// each motor across them through CSWRumblePattern::GetMagnitudes, and hands the
// pair to CExoInput::SetRumble at 0x005DF550. That call ends in DirectInput
// force feedback, which the pad this module invents cannot receive -- so the
// game has always been asking for rumble and nothing has been listening.
//
// Hooked at 0x005F7617, where both magnitudes are already in registers for the
// pushes that follow. At SetRumble's own entry they are stack arguments, and
// KPM sources hook parameters from registers only.
//
// WHICH REGISTER IS WHICH, which was previously left open. UpdateRumble keeps
// two accumulators and maxes each instance's two outputs into them:
//
//     005F760F  mov eax, dword ptr [esp+4]    envelope B's maximum
//     005F7613  mov ecx, dword ptr [esp+8]    envelope A's maximum
//
// so the first parameter, from EAX, is envelope B and the second, from ECX, is
// envelope A. The table this module installs treats envelope A as the heavy
// low-frequency motor and B as the light high-frequency one, which is the
// pairing the shapes were cut for -- so A goes left and B goes right, and the
// two lines below are no longer arbitrary.
//
// The magnitudes arrive as float bit patterns, because the engine moves them
// with `mov` rather than the x87 stack. Both are recorded raw in the diagnostic
// line as `raw=`, alongside `rum=` counting calls seen and XInputSetState calls
// issued, so the scale and the plumbing can each be read from a real run rather
// than assumed. The code treats them as 0..1 and clamps, which is right if
// GetMagnitudes is normalised and saturates harmlessly if it is not.
//
// UpdateRumble reaches this call on its early-bail path too, so a finished
// pattern sends zero and the motors stop without any timeout here.
// A on Cancel in a panel that answers A itself. The Solo Mode query and the
// resolution screen implement the raw A, 0x27, at panel level and never read
// which button has focus, so A on Cancel confirmed. Each hook sits at its
// panel's HandleInputEvent entry, where the event and its value are still the
// stack arguments; KPM passes POINTERS to those slots (an `esp+N` source is
// emitted as LEA), and when A arrives with Cancel focused the event is
// rewritten to 0x28, B. The panel's own dispatcher then takes its own Cancel
// path. A on OK is left alone and reaches the vanilla confirm exactly once.
//
// These were consumed-exit hooks until 2026-09-24, deeper in each dispatcher.
// KPM runs a hook's stolen bytes BEFORE it tests EAX for the consumed exit, and
// the Solo hook's stolen `mov eax,[0x7A39FC]` replaced the answer with the app
// pointer: every A, OK included, took the close path. The log from that build
// showed one confirm per press, each decided "toggle", each refused. See
// kotor1.hooks.toml.
//
// The return value is ignored: no consumed exit, every register restored.
// Two exports rather than one shared test, because check_patcher_hook_table.py
// keys the tracked and emitted tables by function name.
namespace {
constexpr int K1_GUI_EVENT_CONFIRM = 0x27;
constexpr int K1_GUI_EVENT_CONFIRM_ALIAS = 0x2D;   // Solo Mode also takes 0x2D
constexpr int K1_GUI_EVENT_CANCEL = 0x28;

// Diagnostic for the validation build, bounded to 64 lines a session.
void LogConfirmK1(const char* panel, int event, int value, const char* why)
{
    static int logged = 0;
    if (logged >= 64) {
        return;
    }
    ++logged;
    FILE* f = nullptr;
    if (!fopen_s(&f, "kmrp-confirm-focus.log", "a") && f) {
        fprintf(f, "%lu %s event=0x%X value=%d -> %s\n",
                GetTickCount(), panel, event, value, why);
        fclose(f);
    }
}
}

extern "C" int __cdecl ResolveSoloModeConfirmK1(void* panel, int* event, int* value)
{
    if (!panel || !event || !value || *value == 0) {
        return 0;
    }
    if (*event != K1_GUI_EVENT_CONFIRM && *event != K1_GUI_EVENT_CONFIRM_ALIAS) {
        return 0;
    }
    const bool onCancel = MessageBoxCancelHasFocusK1(panel);
    LogConfirmK1("solo", *event, *value, onCancel ? "a-on-cancel -> b" : "a-on-ok");
    if (onCancel) {
        *event = K1_GUI_EVENT_CANCEL;
    }
    return 0;
}

extern "C" int __cdecl ResolveResolutionConfirmK1(void* panel, int* event, int* value)
{
    if (!panel || !event || !value || *value == 0 || *event != K1_GUI_EVENT_CONFIRM) {
        return 0;
    }
    const bool onCancel = MessageBoxCancelHasFocusK1(panel);
    LogConfirmK1("resolution", *event, *value, onCancel ? "a-on-cancel -> b" : "a-on-ok");
    if (onCancel) {
        *event = K1_GUI_EVENT_CANCEL;
    }
    return 0;
}

namespace {
// Character creation and level-up: A on the five screens that answer A themselves
// AND pass it on.
//
// CSWGuiAbilitiesCharGen, CSWGuiSkillsCharGen, CSWGuiFeatsCharGen,
// CSWGuiPowersLevelUp and CSWGuiPortraitCharGen are retained Xbox panels. Each
// dispatcher runs its own A action and then calls CSWGuiPanel::HandleInputEvent
// (0x00409E60), which hands the same event to the focused control, [panel+0x1C].
// Their buttons are wired to raise the panel's events: Attributes' OK registers
// A (0x27) -> Global::AcceptButtonCallback (0x00624BA0) -> the panel's vtable
// +0x50 (0x0040B640) -> HandleInputEvent(0x27, 1) on the panel again. So with OK
// focused, one A is the panel's A, then OK's click, then the panel's A again,
// without end: a stack overflow (0xC00000FD, three times on 2026-09-25, after
// confirming "Attribute scores cannot be reduced below 8"). With 30 points left
// each pass also re-showed the "spend your points" box. A mouse never loops,
// because clicking does not set the panel's focused control; the pad's D-pad
// focus does. The same wiring makes A on a focused Cancel run the screen's
// accept and then Cancel.
//
// The guard, at each dispatcher's entry:
//   * A pressed with a button in focus presses that button, once, the way A
//     does on every other KMRP screen -- the button's own click decides (OK
//     accepts, Cancel cancels, + raises), and the event the panel would have
//     handled is made inert;
//   * the one re-entry that click raises is let through, and any deeper one --
//     the loop -- is made inert;
//   * a release (value 0) is made inert, so it can never click anything;
//   * A with no button in focus is left alone: the screen's own A, as on Xbox.
// Inert is 0x41: above every dispatcher's 0x27..0x40 table, outside
// CSWGuiNavigable's 0x2F..0x40, and registered by no AddEvent call in the image.
constexpr int K1_GUI_EVENT_INERT = 0x41;

struct ChargenPressK1 { bool active; int reentries; };
ChargenPressK1 g_chargenPress = {};

// Does this control answer A with a click of its own? CSWGuiControl::AddEvent
// (0x0041AB20) keeps 12-byte entries {receiver, handler, code} at [control+0x38],
// their count at +0x3C; CSWGuiControl::HandleInputEvent (0x00418750) runs the
// handler of the entry whose code matches.
bool ClicksOnConfirmK1(void* control)
{
    if (!IsReadableK1(control, 0x40)) {
        return false;
    }
    const char* const entries = *reinterpret_cast<const char* const*>(
        static_cast<char*>(control) + 0x38);
    const int count = *reinterpret_cast<const int*>(static_cast<char*>(control) + 0x3C);
    if (count <= 0 || count > 64 || !IsReadableK1(entries, count * 12)) {
        return false;
    }
    for (int i = 0; i < count; ++i) {
        const char* const entry = entries + i * 12;
        if (*reinterpret_cast<const int*>(entry + 8) == K1_GUI_EVENT_CONFIRM &&
            *reinterpret_cast<void* const*>(entry + 4) != nullptr) {
            return true;
        }
    }
    return false;
}

int GuardChargenConfirmK1(const char* name, void* panel, int* event, int* value)
{
    if (!panel || !event || !value) {
        return 0;
    }
    if (*event != K1_GUI_EVENT_CONFIRM && *event != K1_GUI_EVENT_CONFIRM_ALIAS) {
        return 0;
    }
    if (g_chargenPress.active) {
        if (++g_chargenPress.reentries > 1) {
            LogConfirmK1(name, *event, *value, "loop -> inert");
            *event = K1_GUI_EVENT_INERT;
        }
        return 0;
    }
    if (*value == 0) {
        *event = K1_GUI_EVENT_INERT;
        return 0;
    }
    void* const focused = *reinterpret_cast<void**>(static_cast<char*>(panel) + 0x1C);
    if (!ClicksOnConfirmK1(focused)) {
        LogConfirmK1(name, *event, *value, "no button in focus -> the screen's A");
        return 0;
    }
    LogConfirmK1(name, *event, *value, "press the focused button");
    g_chargenPress = {true, 0};
    using Handle = void(__thiscall*)(void*, int, int);
    void** const vtable = *reinterpret_cast<void***>(focused);
    reinterpret_cast<Handle>(vtable[0x3C / 4])(focused, K1_GUI_EVENT_CONFIRM, 1);
    g_chargenPress = {};
    *event = K1_GUI_EVENT_INERT;
    return 0;
}
}

// One export per hooked dispatcher: check_patcher_hook_table.py keys hooks by name.
extern "C" int __cdecl GuardAbilitiesConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("abilities", panel, event, value);
}

extern "C" int __cdecl GuardSkillsConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("skills", panel, event, value);
}

extern "C" int __cdecl GuardFeatsConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("feats", panel, event, value);
}

extern "C" int __cdecl GuardPowersConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("powers", panel, event, value);
}

extern "C" int __cdecl GuardPortraitConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("portrait", panel, event, value);
}

// Name entry (CSWGuiNameChargen, dispatcher 0x006FA220) answers A through its
// focused control only -- its jump table starts at 0x28 -- and both the name box
// and OK register A to HandleDoneButton (0x006F9CD0). So the release of the A
// that opened the screen, from the step list, reached the name box and confirmed
// the name at once: the screen stayed up only while A was held (play-test,
// 2026-09-25). Guarded for that release; a press still reaches the focused
// control exactly as before, the guard pressing it itself.
extern "C" int __cdecl GuardNameConfirmK1(void* panel, int* event, int* value)
{
    return GuardChargenConfirmK1("name", panel, event, value);
}

extern "C" void __cdecl NativeRumbleK1(int envelopeBBits, int envelopeABits,
                                       void* rumbleOwner, float* frameTime)
{
    ++g_stick.rumbleCalls;
    g_stick.rumbleRawA = static_cast<unsigned long>(envelopeABits);
    g_stick.rumbleRawB = static_cast<unsigned long>(envelopeBBits);
    // UpdateRumble runs every frame from the main loop, so this is the earliest
    // and most reliable place to hand the engine its pattern table. Installing
    // from inside the call it gates is safe: with the count still zero there can
    // be no instances, so the loop above this point did nothing.
    EnsureRumbleTableK1(rumbleOwner);

    auto toFloat = [](int bits) -> float {
        float value = 0.0f;
        std::memcpy(&value, &bits, sizeof(value));
        return value > 0.0f ? value : 0.0f;     // also catches NaN
    };
    auto toMotor = [](float value) -> WORD {
        if (!(value > 0.0f)) {
            return 0;
        }
        if (value > 1.0f) {
            value = 1.0f;
        }
        return static_cast<WORD>(value * 65535.0f);
    };

    // Every pattern the engine starts is played by the mixer (K1Rumble.cpp),
    // which also applies mode, strength, pause and menus. What the engine mixed
    // itself is passed along too, and is zero whenever the play hook is present.
    const float dt = IsReadableK1(frameTime, sizeof(float)) ? *frameTime : 0.0f;
    float heavy = 0.0f;
    float light = 0.0f;
    KmrpRumbleTickK1(rumbleOwner, dt, toFloat(envelopeABits), toFloat(envelopeBBits),
                     heavy, light);
    // The mixer ticks with or without a pad, so that health and saber state
    // are current when one connects rather than read as one huge change.
    if (!g_stick.padPresent) {
        return;                         // no pad has answered yet
    }

    XINPUT_VIBRATION vibration{};
    vibration.wLeftMotorSpeed = toMotor(heavy);      // envelope A
    vibration.wRightMotorSpeed = toMotor(light);     // envelope B

    const unsigned long packed =
        (static_cast<unsigned long>(vibration.wLeftMotorSpeed) << 16) |
        vibration.wRightMotorSpeed;
    g_stick.rumbleLast = packed;
    if (SetControllerRumbleK1(vibration.wLeftMotorSpeed, vibration.wRightMotorSpeed))
        ++g_stick.rumbleSent;
}

// The movie window has just been created, inside InitializeMovie and before the
// message pump has had a chance to show anything. This is the earliest point the
// handle exists -- CreateWindowExA returns at 0x00405536 and the handle is
// stored to player+0x50 immediately after.
extern "C" void __cdecl NativeMovieWindowOpenK1(void* player)
{
    g_movie.lastW = -1;                // a fresh window: repaint on frame one
    BlackenMovieWindowK1(player);
}

// CExoMoviePlayerInternal::ShutDown, before it closes the Bink buffer and
// destroys the window. Bink has stopped drawing by now, so without this the
// window shows its last frame or nothing at all until it goes away.
extern "C" void __cdecl NativeMovieWindowCloseK1(void* player)
{
    BlackenMovieWindowK1(player);
}

// Has this playlist entry's geometry changed since the last frame?
//
// PlayMovieList loops over its entries reusing one player object and recomputes
// the picture size per entry, so this is the only edge that says "a new movie
// just started" from inside the playback loop. Both the surface clear and the
// aspect-fit checks hang off it.
void PaintMovieWindowK1(void* player)
{
    const void* const info = *FieldAt<void*>(player, K1_MOVIE_INFO);
    if (!LooksLikePointerK1(info)) {
        return;
    }
    const std::int32_t movieW = *FieldAt<std::int32_t>(const_cast<void*>(info), 0);
    const std::int32_t movieH = *FieldAt<std::int32_t>(const_cast<void*>(info), 4);
    const std::int32_t offX = *FieldAt<std::int32_t>(player, K1_MOVIE_OFFSET_X);
    const std::int32_t offY = *FieldAt<std::int32_t>(player, K1_MOVIE_OFFSET_Y);
    if (movieW == g_movie.lastW && movieH == g_movie.lastH &&
        offX == g_movie.lastOffX && offY == g_movie.lastOffY) {
        return;                        // same entry still playing
    }
    g_movie.lastW = movieW;
    g_movie.lastH = movieH;
    g_movie.lastOffX = offX;
    g_movie.lastOffY = offY;

    // Black the WINDOW, not the Bink buffer.
    //
    // Two earlier attempts got this wrong and both are worth remembering:
    //
    //   * Clearing the Bink buffer does nothing. The buffer is allocated at the
    //     MOVIE's size, so it holds only pixels BinkCopyToBuffer rewrites every
    //     frame. The bars are screen OUTSIDE the blit, which the buffer cannot
    //     reach.
    //   * Padding the buffer to the window's aspect and centring the picture
    //     inside it broke playback outright. The engine blits dirty rectangles
    //     from BinkGetRects, and those are in the movie's coordinate space --
    //     so offsetting the picture desynced the blit from it, and the intro
    //     logos rendered with only their left portion on screen.
    //
    // The bars are unpainted window, and so is the flash at either end. Both
    // are the same defect, so both get the same answer.
    BlackenMovieWindowK1(player);
}

// One iteration of CExoMoviePlayerInternal::PlayMovieLoop, with esi holding the
// player. This is the only place a controller can be read during a movie.
//
// The arming rule is what keeps "one press, one skip" honest. A button that was
// already down when the movie started -- the A that dismissed the menu, or the
// Start that began a new game -- must not count as a press against the movie
// that follows. So a new player pointer disarms, and the first frame with the
// skip buttons released arms it. Without that, the startup logos skipped
// themselves the instant a held button carried over.
extern "C" void __cdecl NativeMovieFrameK1(void* moviePlayer)
{
    if (!LooksLikePointerK1(moviePlayer)) {
        g_movie.player = nullptr;      // no movie: nothing can be pending
        g_movie.armed = false;
        return;
    }
    ++g_movie.frames;
    if (moviePlayer != g_movie.player) {
        g_movie.player = moviePlayer;  // a different movie: start again
        g_movie.armed = false;
        g_movie.lastW = -1;            // a new player: report its first entry
    }
    // Every frame, not just on a new player: the function itself suppresses
    // repeats, and only a per-frame check catches the second and later entries
    // of a playlist. Before the pad is read, so a movie is measured whether or
    // not a controller is connected.
    PaintMovieWindowK1(moviePlayer);

    std::int32_t x = 0, y = 0, rx = 0, ry = 0;
    std::uint16_t buttons = 0;
    std::uint8_t lt = 0, rt = 0;
    if (!ReadPadAxes(x, y, buttons, rx, ry, lt, rt)) {
        return;                        // no pad: the keyboard path still works
    }

    const bool down = (buttons & K1_MOVIE_SKIP_MASK) != 0;
    if (!g_movie.armed) {
        if (!down) {
            g_movie.armed = true;      // released at last; now a press counts
        }
        return;
    }
    if (!down) {
        return;
    }
    g_movie.armed = false;             // one press, one skip

    // Only call it when the engine would actually cancel. CancelMovie is NOT
    // side-effect free when its own guard fails:
    //
    //   00404C4D  cmp dword ptr [ecx+0x30], 1
    //   00404C50  jne 0x00404C69          ; "not cancellable"
    //   00404C69  mov dword ptr [ecx+0x18], arg1   <-- still writes
    //
    // Both branches write [player+0x18], which is what the code after the movie
    // loop reads. So pressing skip during a story movie that may not be skipped
    // left the movie running and quietly zeroed its result, and the game came
    // back from the vision to a black screen with only the HUD, and then died.
    // Reported from play, and the reason this guard exists.
    const int cancellable = *FieldAt<int>(moviePlayer, K1_MOVIE_PLAYING);
    void* const ready = *FieldAt<void*>(moviePlayer, K1_MOVIE_ENTRY_SKIPPABLE);
    if (cancellable != 1 || ready == nullptr) {
        ++g_movie.refused;             // not skippable: leave it entirely alone
        return;
    }
    EngineFn<CancelMovieFn>(K1_CANCEL_MOVIE)(moviePlayer, 0, 0);
    ++g_movie.skips;
}

// Keyboard and mouse activity, so the prompts go away when the player stops
// using the pad. Requirement, not polish: a badge that stays on screen while
// someone types is worse than no badge, because it claims the wrong device.
//
// Both sites are the ones Saul0097's build uses for the same purpose. His
// versions also do action-bar work; these do only the device bookkeeping,
// because KMRP's own action bar already runs from its own hook.
extern "C" void __cdecl NativeNoteKeyboardK1(void* record, int inputDevice)
{
    KmrpNoteKeyboardK1(record, inputDevice);
}

extern "C" void __cdecl NativeNoteMouseK1(void* manager, int mouseX, int mouseY)
{
    (void)manager;
    KmrpNoteMouseK1(mouseX, mouseY);
}

// Every save leaks one buffer per resource written.
//
// CERFFile::WriteResource hands a buffer to CExoFile::Write (0x005E69A0) and
// then abandons it -- the pointer in esi is never freed. Adopted from the Kotor
// Patch Manager project's SaveGameMemoryLeak patch (Lane Dibello); the
// ownership analysis is theirs and was reviewed there, not re-derived here.
extern "C" void __cdecl NativeFreeSaveBufferK1(void* buffer)
{
    if (!buffer) {
        return;
    }
    EngineFn<FreeFn>(K1_FREE)(buffer);
    ++g_stick.saveBuffersFreed;
}

// CSWGuiPanel::ReleaseGff, with ecx holding the panel. Every one of the 68 panel
// constructors calls this as its last act, and it is the last instant at which a
// control can be added: it deletes the parsed .gui the binder resolves tags
// against. Panels that are not party screens are left alone.
extern "C" void __cdecl NativePanelReleaseGffK1(void* panel)
{
    ControllerLayoutReleaseGffK1(panel);
    ForgetGuiCuesK1(panel);
    InstallGuiCuesK1(panel);
}

// CSWGuiMainInterface's per-frame update, with ecx holding the interface. The
// gameplay HUD's action bar is driven from here: the engine functions it calls
// expect to run during GUI work, not inside CExoInput's polling.
//
// The D-pad's retained codes are suppressed in gameplay for the same reason the
// menu layer suppresses them -- exactly one mechanism may act on a press.
extern "C" void __cdecl NativeActionBarK1(void* mainInterface)
{
    const int dx = g_stick.hudPendingX;
    const int dy = g_stick.hudPendingY;
    g_stick.hudPendingX = 0;
    g_stick.hudPendingY = 0;

    int activate = 0;
    if (g_stick.hudActivateRequested != 0) {
        g_stick.hudActivateRequested = 0;
        // A means "use this slot" only while a slot has focus. Otherwise it is
        // the world action, and PerformPendingInteractionK1 asks the same
        // question, so exactly one of the two answers yes however the two hooks
        // happen to be ordered within a frame.
        activate = KmrpActionBarFocusedK1(mainInterface);
        if (activate != 0) {
            // This press is the slot's. Take the world consumer's request too:
            // the slot keeps focus now, so the world consumer would decline it
            // anyway, but one press doing exactly one thing should not depend
            // on that.
            g_stick.interactRequestedTick = 0;
        }
    }
    int release = 0;
    if (g_stick.hudReleaseRequested != 0) {
        g_stick.hudReleaseRequested = 0;
        release = KmrpActionBarFocusedK1(mainInterface);
    }
    // Taken now whatever happens below, so a press made in gameplay can never
    // act later on a different screen.
    const bool clearOne = g_stick.combatClearRequested != 0;
    const bool disengage = g_stick.disengageRequested != 0;
    g_stick.combatClearRequested = 0;
    g_stick.disengageRequested = 0;

    if (InputClassK1() != K1_CLASS_PC || !LooksLikePointerK1(mainInterface)) {
        // Ask nothing of the interface outside gameplay. KmrpActionBarStateK1
        // walks the button array and the panel manager, and free look changes
        // the input class from under this hook, so anything read here during a
        // transition is read from an object that may be mid-rebuild.
        g_stick.hudState = 0;
        return;
    }
    g_stick.hudInterface = reinterpret_cast<unsigned long>(mainInterface);
    g_stick.hudState = KmrpActionBarStateK1(mainInterface);
    // Y, then X: undo the last queued action, then disengage altogether.
    if (clearOne) {
        PressHudButtonK1(mainInterface, K1_HUD_CLEAR_ONE, K1_ON_CLEAR_ONE);
    }
    if (disengage) {
        PressHudButtonK1(mainInterface, K1_HUD_CLEAR_ALL, K1_ON_CLEAR_ALL);
    }
    if (release != 0) {
        KmrpActionBarReleaseK1(mainInterface);   // B: cancel, and nothing else
        ++g_stick.hudReleases;
        return;
    }
    if (dx == 0 && dy == 0 && activate == 0) {
        return;
    }
    KmrpActionBarApplyK1(mainInterface, dx, dy, activate);
    if (dx != 0) {
        ++g_stick.hudMoves;
    }
    if (dy != 0) {
        ++g_stick.hudCycles;
    }
    if (activate != 0) {
        // The slot KEEPS focus once used, so A can be pressed again at once --
        // attack, attack, attack -- without D-pad Right each time. Only B lets
        // go of the bar. Until 2026-09-25 a used slot released it (issue #17);
        // in combat that meant re-entering the bar after every action, and the
        // user asked for it to stay.
        ++g_stick.hudActivations;
    }
}

// Runs at 0x006039CF, where both of UpdateCamera's paths converge and ESI is
// CClientExoAppInternal. Applying the turn here rather than from GetEvents is
// what makes it stick: ScrollCamera zeroes camera+0x10C from inside
// UpdateCamera, so anything written earlier in the frame is gone by now.
extern "C" void __cdecl NativeCameraFrameK1(void* clientInternal)
{
    FeedNativeCameraK1(clientInternal);
}

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

// The engine's own texture-load instrumentation, sampled read-only for the
// white-flash investigation. See reverse-engineering/texture-residency.md.
//
// The queue drain (AurTextureBuildAndStoreAll, 0x004217F0) is unbounded and
// synchronous -- it empties the whole queue in one pass, each entry costing a
// disk read and a decode in ConstructImage. If that lands in a single frame
// these numbers say so, and nothing here writes to the engine.
constexpr std::uintptr_t K1_G_DELTA_T              = 0x0078E574;  // float
constexpr std::uintptr_t K1_G_MAX_DELTA_T          = 0x007A4750;  // float
constexpr std::uintptr_t K1_G_MAX_TEXTURE_TIME     = 0x007A46B0;  // int
constexpr std::uintptr_t K1_G_CURRENT_TEXTURE_TIME = 0x007A4754;  // int
constexpr std::uintptr_t K1_G_LOAD_IMAGE_TIME      = 0x007A4758;  // int
constexpr std::uintptr_t K1_G_MAX_TEX_LOAD_TIME    = 0x007A472C;  // int

// The highest GL texture name the engine has seen, written by
// AurTextureBuildAndStoreAll at 0x0042192F. It matters because
// AddPartToMeshBuckets (0x0046BDF0) indexes a stride-12 array at 0x008194E0 by
// this id with NO range check, and AurTextureGetMaxTexID (0x0041FEB0) hands it
// out unclamped as an iteration count. KPM's TextureBucketSafety patch bounds
// both at 5000, and KMRP installs it through this component's patch_config.toml;
// KMRP still loads far more textures than vanilla, so the number is worth watching.
constexpr std::uintptr_t K1_G_MAX_TEX_ID = 0x007A46BC;
constexpr long K1_TEXTURE_BUCKET_ENTRIES = 5000;

// A frame this long is not a hitch, it is a stall a player would notice. Used
// only to count them, never to change behaviour.
constexpr unsigned long K1_SLOW_FRAME_MS = 100;

// ------------------------------------------------- the party-switch cue
//
// R3 changes which party member the four party screens are showing, and there is
// no control in any of them to say so. The build adds one -- LBL_KMRPR3, between
// the two portraits or right of them -- and this binds it, because a panel
// builds the controls it knows by name and would never build this one.
//
// There is exactly one moment when that is possible. Every panel constructor
// ends by calling CSWGuiPanel::ReleaseGff, which deletes the parsed .gui and
// nulls the pointer the binder reads, so afterwards no tag can be resolved on
// that panel ever again. Hooking ReleaseGff itself puts us at that moment on
// every panel with the panel already in ecx -- one hook rather than four, and
// its prologue (56 8B F1 F6 46 44 02) has no relative operand to relocate.
constexpr std::uintptr_t K1_GUI_PANEL_BIND_CONTROL = 0x0040B930;
constexpr std::uintptr_t K1_GUI_LABEL_CTOR         = 0x0041ACD0;
constexpr std::uintptr_t K1_EXOSTRING_CTOR         = 0x005E5A90;
constexpr std::uintptr_t K1_EXOSTRING_DTOR         = 0x005E5C20;

// CSWGuiControl 0x5C + CSWGuiBorder 0x74 + CSWGuiText 0x70. Measured three ways:
// the spacing of INVENTORY's adjacent embedded labels, the `add ecx, 0x140` in
// CHARACTER's LBL_GOOD loop, and the constructor's own sub-object offsets.
constexpr std::size_t K1_GUI_LABEL_SIZE = 0x140;

// CSWGuiPanel::gff. Non-null only until ReleaseGff runs.
constexpr std::size_t K1_PANEL_GFF           = 0x2C;
// CSWGuiPanel's own vtable. The base destructor stores it and then calls
// ReleaseGff, with the .gui long gone and the control array still in place: the
// one moment a panel's end is visible from a hook. K1ControllerLayout.cpp keys
// its own cleanup on the same pair, and its lifecycle log shows it firing.
constexpr std::uintptr_t K1_BASE_PANEL_VTABLE = 0x0073E010;
// CSWGuiControl::bit_flags and ::id.
constexpr std::size_t K1_CONTROL_FLAGS = 0x44;
constexpr std::size_t K1_CONTROL_ID    = 0x50;
// The bit CSWGuiPanel::Draw tests before drawing a child. The engine sets it on
// a control that loaded (0x0040A854) and clears it to hide one -- CHARACTER's
// constructor hides all ten LBL_GOOD labels that way immediately after binding
// them. Driving it is what the game itself does.
constexpr std::uint32_t K1_CONTROL_FLAG_DRAWN = 2;

// The HUD's combat buttons: members of CSWGuiMainInterface (vtable 0x00753F50),
// whose constructor registers their click handlers for event 0x27 --
// OnClearOneButtonPressed on BTN_CLEARONE at 0x0068D0C3 (and on BTN_CLEARONE2 at
// 0x0068D0DC), OnClearAllButtonPressed on BTN_CLEARALL at 0x0068D0EF.
//
//   OnClearOneButtonPressed  shows the tutorial the first time, as a click
//                            does, then calls OnCombatYButton (0x006880C0):
//                            CSWSCombatRound::RemoveLastAction, or, with nothing
//                            left to remove, CSWSObject::ClearAllActions. The
//                            Xbox build's Y in combat, by its name.
//   OnClearAllButtonPressed  the Disengage button: ClearAllActions (0x006887D0),
//                            which leaves combat mode, clears every action and
//                            plays the button's sound.
//
// Pressed through those handlers with the button itself as the argument, so a
// pad press is exactly a mouse click; and only while the button is drawn, the
// test OnClearOneButtonPressed makes itself ([this+0x6D14] & 2 at 0x0068B05E).
using HudButtonHandlerFn = void(__thiscall*)(void*, void*);

bool PressHudButtonK1(void* mainInterface, std::size_t member, std::uintptr_t handler)
{
    if (!IsReadableK1(mainInterface, K1_HUD_CLEAR_ALL + 0x50) ||
        *FieldAt<std::uintptr_t>(mainInterface, 0) != K1_MAIN_INTERFACE_VTABLE) {
        return false;
    }
    void* const button = FieldAt<std::uint8_t>(mainInterface, member);
    if ((*FieldAt<std::uint32_t>(button, K1_CONTROL_FLAGS) & K1_CONTROL_FLAG_DRAWN) == 0) {
        return false;                   // not in combat, or nothing to clear
    }
    EngineFn<HudButtonHandlerFn>(handler)(mainInterface, button);
    return true;
}

// Which cue belongs on which panel. Matched on the panel's vtable because
// ReleaseGff is called by all 68 panel constructors and only these want one, and
// a panel may want more than one -- the tab strip carries both triggers.
//
// Every tag here must also exist in the matching .gui, which
// tools/prepare_universal_resources.py adds at build time. A tag that is not
// there binds nothing and is counted as rejected rather than failing.
struct GuiCueBindingK1 {
    std::uintptr_t panelVtable;
    const char*    tag;
    // A control on the panel, by its offset in the panel object, whose
    // visibility the cue copies; 0 for a cue shown whenever the pad is live.
    std::size_t    follow;
};

constexpr GuiCueBindingK1 K1_GUI_CUES[] = {
    // R3 changes the party member these four are about. They are exactly the
    // four panels that implement 0xCE, and the four that carry the portraits.
    {0x00755E50, "LBL_KMRPR3"},   // ABILITIES -- Skills / Powers / Feats
    // X cycles that screen's sub-tab -- its 0x29 handler (0x006AE714)
    // switches a byte at CGuiInGame+0xBC0 through 0/1/2 and wraps.
    {0x00755E50, "LBL_KMRPSWAP"},
    {0x00756100, "LBL_KMRPR3"},   // CHARACTER
    {0x007569A0, "LBL_KMRPR3"},   // EQUIP
    {0x007564E0, "LBL_KMRPR3"},   // INVENTORY
    // LT and RT move along the menu tab strip, which top.gui owns. Its panel
    // draws with the BASE CSWGuiPanel::Draw, the same array walk everything else
    // here relies on.
    {0x00750148, "LBL_KMRPLT"},
    {0x00750148, "LBL_KMRPRT"},
    // X and Y beside the HUD's combat buttons, each shown only while its button
    // is: Y by BTN_CLEARONE, X by BTN_CLEARALL (see PressHudButtonK1).
    {K1_MAIN_INTERFACE_VTABLE, "LBL_KMRPY", K1_HUD_CLEAR_ONE},
    {K1_MAIN_INTERFACE_VTABLE, "LBL_KMRPX", K1_HUD_CLEAR_ALL},
};
constexpr int K1_GUI_CUE_COUNT =
    sizeof(K1_GUI_CUES) / sizeof(K1_GUI_CUES[0]);

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
// Character creation's Portrait screen, whose Left/Right pick a portrait; see
// NavigateFocusK1.
constexpr std::uintptr_t K1_PORTRAIT_CHARGEN_DISPATCHER = 0x006F8FF0;
constexpr std::uintptr_t K1_PAZAAK_WAGER_DISPATCHER = 0x0067E150;
// Panels on which the pad never moves the focus; see NavigateFocusK1. Each
// answers its buttons from its own dispatcher, whatever holds focus, and then
// passes the same event on to the focused control, whose click raises that
// event on the panel again (the AddEvent thunks 0x00624BA0, "raise A", and
// 0x00644720, "raise Y", through the panel's vtable +0x50 and +0x5C).
constexpr std::uintptr_t K1_NO_PAD_FOCUS_PANELS[] = {
    // The status summary, "Journal Entry Added" and the like. With OK focused,
    // one A ran panel -> OK -> panel until the stack was gone: 0xC00000FD,
    // measured 2026-09-25.
    0x00625AC0,   // STATUS_SUMMARY
    // The Character screen. A levels up and Y auto-levels (0x006B2295,
    // 0x006B233C), X opens Scripts, B closes and R3 changes party member, all
    // with nothing focused. With Level Up focused, one A opened the level-up
    // screen twice, stacked, and the game froze (2026-09-26); focused Auto Level
    // Up would have run the Y action on top of the A one.
    0x006B2250,   // CHARACTER
    // "You have been granted the following feat(s)" (skillinfo.gui). A closes it
    // whatever holds focus (0x006CD3E7), and its OK raises A like the status
    // summary's. Its list holds the focus and keeps the D-pad, so the pad never
    // reached OK in play (2026-09-26); listed so it never can.
    0x006CD3C0,   // SKILL_INFO
};

constexpr std::uintptr_t K1_NATIVE_DIRECTION_PANELS[] = {
    0x006AE5F0,   // ABILITIES
    0x006F4680,   // FEATS
    0x00693BC0,   // MAP
    0x006F28C0,   // POWERS
    // Pazaak's wager box, added 2026-09-25: Left and Down lower the wager, Right
    // and Up raise it (0x0067E221, 0x0067E23D), whatever holds focus. It was
    // missing because the retained-event inventory never listed the panel, so
    // the pad moved the focus between its buttons and the wager never changed.
    0x0067E150,   // PAZAAK_WAGER
    // ABILITIES_CHARGEN (0x006F8880) and SKILLS (0x006F6A10) were here until
    // 2026-09-25; KMRP now navigates them itself -- see K1_POINTS_SCREENS.
};

// Character creation's two points screens, Attributes and Skills, in both chargen
// and level-up. Their dispatchers are the Xbox design: Up/Down had no handler of
// their own, and Left/Right (0x2F/0x3F, 0x30/0x40) lowered and raised the selected
// row -- whatever held focus -- and were then passed to the focused control too.
// With the pad's focus on the bottom strip, Left from OK therefore lowered the
// attribute AND moved to Recommended, and Right to Cancel raised it (play-test,
// 2026-09-25). KMRP owns every direction on these screens instead:
//   Up/Down     the rows, top to bottom; Down from the last row reaches OK, Up
//               from the strip returns to the row last in focus;
//   Left/Right  on a row, that row's value, calling the panel's own lower/raise
//               with its own sound, and focus stays put; on the strip, the next
//               button along, and no value changes.
// A row is its value button (*_POINTS_BTN). Focusing one runs the engine's
// "enter" event for it -- SetActiveControl (0x0040A630) sends exit (1) to the old
// control and enter (0) to the new -- and the panels register enter on exactly
// those buttons (Attributes 0x006F8200, OnEnterPointsButton 0x006F70E0; Skills
// 0x006F5FD0, 0x006F4BF0), which is what selects the row the value calls act on.
struct PointsScreenK1 {
    std::uintptr_t dispatcher;
    std::uintptr_t lower;          // thiscall(panel), no arguments
    std::uintptr_t raise;
    int rowCount;
    std::size_t rows[8];           // value buttons, top to bottom as drawn
    std::size_t strip[3];          // Recommended, OK, Cancel, left to right
};
constexpr PointsScreenK1 K1_POINTS_SCREENS[] = {
    // CSWGuiAbilitiesCharGen: STR DEX CON INT WIS CHA as drawn. INT and WIS are
    // bound the other way round (0x1F9C and 0x1DD8), so this is not the stride.
    {0x006F8880, 0x006F8480, 0x006F8670, 6,
     {0x188C, 0x1A50, 0x1C14, 0x1F9C, 0x1DD8, 0x2160}, {0x26AC, 0x2324, 0x24E8}},
    // CSWGuiSkillsCharGen: Computer Use, Demolitions, Stealth, Awareness,
    // Persuade, Repair, Security, Treat Injury.
    {0x006F6A10, 0x006F6370, 0x006F6570, 8,
     {0x19CC, 0x1B90, 0x1D54, 0x1F18, 0x20DC, 0x22A0, 0x2464, 0x2628},
     {0x2B74, 0x27EC, 0x29B0}},
};

const PointsScreenK1* PointsScreenForK1(std::uintptr_t dispatcher)
{
    for (const PointsScreenK1& screen : K1_POINTS_SCREENS) {
        if (screen.dispatcher == dispatcher) {
            return &screen;
        }
    }
    return nullptr;
}

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

// Is [p, p + size) committed, readable memory right now? LooksLikePointerK1 only
// says an address is in range, and a remembered object can outlive itself:
// loading a save destroys every in-game screen, and once a freed page is
// released, reading it faults. That was the Load Game crash of 2026-09-24,
// kmrp-controller.module+0x3CC8, in the cue loop. VirtualQuery answers without
// touching the memory.
bool IsReadableK1(const void* p, std::size_t size)
{
    if (!LooksLikePointerK1(p) || size == 0) {
        return false;
    }
    constexpr DWORD readable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    const std::uint8_t* at = static_cast<const std::uint8_t*>(p);
    const std::uint8_t* const end = at + size;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(at, &info, sizeof(info)) || info.State != MEM_COMMIT ||
            !(info.Protect & readable) || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
            return false;
        }
        at = static_cast<const std::uint8_t*>(info.BaseAddress) + info.RegionSize;
    }
    return true;
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

// --------------------------------------------------- the in-game tab bar
//
// The in-game menu is two panels, and the navigation layer only ever looked at
// one of them. CSWGuiInGameMenu is the strip of eight tab icons and sits in
// front; the screen's actual content is a separate panel below it in the
// manager's list. Everything here was read out of the running game and the
// image rather than assumed, because the obvious reading is wrong twice over.
//
// The strip carries SIXTEEN focusable controls, not eight:
//
//   indices 0-7    192x192 at y=96, one per tab, each registering ONLY 0x35 and
//                  0x36 (previous/next screen). These are the engine's own focus
//                  targets: CSWGuiInGameMenu::SetActiveControlID @ 0x00624BD0
//                  indexes the panel's control array directly, so tab k is
//                  control k, and the array is in visual left-to-right order.
//   indices 8-15   156x120 at y=129, sitting INSIDE the frame above them, each
//                  registering 0x27 with its own handler. These are the mouse
//                  hotspots.
//
// Both sets pass the navigable test, so left/right used to walk sixteen stops
// through an eight-tab strip, landing half the time on a frame that A cannot
// activate. Excluding the overlays from focus is what makes the strip read as
// eight tabs.
//
// The eight 0x27 handlers all call one function with a different constant:
//
//   00624CF0  SetScreen(0)      00624D70  SetScreen(3)
//   00624D10  SetScreen(1)      00624DD0  SetScreen(4)
//   00624D30  SetScreen(2)      00624D90  SetScreen(5)
//   00624D50  SetScreen(6)      00624DB0  SetScreen(7)
//
// so there is nothing per-tab to encode: activating a tab means handing its own
// registered 0x27 to its own overlay, exactly as a mouse click does.
constexpr std::uintptr_t K1_INGAME_MENU_DISPATCHER = 0x00624970;

// CSWGuiListBox, and the two fields its own up handler reads.
//
// A retained direction event cannot reach a panel behind the strip: the strip is
// in front, its dispatcher answers only 0xF3/0xF4, and the base class then routes
// to the strip's OWN focused control. So standing down "so the list can navigate
// natively" handed the press to nothing at all. The list is driven by handing it
// its own retained event directly instead -- its own HandleInputEvent, the same
// call the engine would make -- so the navigation stays the engine's.
//
// The boundary comes from the engine too. CSWGuiListBox::HandleInputEvent's
// 0x31 case at 0x0041CF3E computes its own "did anything happen":
//
//     mov  ax, [esi+0x2C8]     ; the selected row
//     test ax, ax
//     setne cl                 ; moved = (row != 0)
//
// so a list sitting on row 0 cannot scroll up, and that is exactly when up
// should leave it for the tab strip. +0x2C6 selects a different branch when it
// is not -1, so the escape is only taken on the plain-row path.
constexpr std::uintptr_t K1_LISTBOX_DISPATCHER = 0x0041CE20;

// CSWGuiInGameJournal. Its four actions are events its dispatcher implements
// directly, read at 0x006456E0:
//
//     0x29  0x00645C8C  Quest Items -- a sound, then 0x0040BC70 on [panel+0xFB4]
//     0x2A  0x006459CE  Active/Completed -- 0x00645610, then a re-sort
//     0x2B  0x0064573F  the sort order, `inc eax / cmp eax, 4` into [0x00833A90]
//     0x28  0x00645CAB  close
constexpr std::uintptr_t K1_JOURNAL_DISPATCHER = 0x006456E0;

// Buttons whose meaning changes on one particular screen.
//
// The Journal's badges say A for Active/Completed and Y for the sort, and the
// engine disagrees: 0x2A is what Y sends, and the sort is on 0x2B, which only
// Back sends and no badge mentions. Reported from play as "the Active Quests
// button doesn't work, it's actually Y that presses it" and "Sort by doesn't
// work with any controller button".
//
// Remapping rather than relabelling because the labels are the sensible layout
// -- A confirms the view you want, Y is the odd-job button -- and because the
// sort is otherwise reachable only from a button nothing advertises.
struct ButtonRemapK1 {
    std::uintptr_t panel;       // the dispatcher of the panel this applies to
    int            slot;        // the pad slot, as K1_BUTTONS names it
    int            event;       // what to dispatch to that panel instead
    const char*    what;
    // Or, when set, what to do instead of dispatching `event` -- and the remap
    // then applies only while that panel is the one in front, so a message box
    // over it keeps its own A.
    void         (*action)(void* panel);
    // When set, which panels the remap applies to, in place of `panel`. The
    // settings screens share the base panel's dispatcher, so a dispatcher cannot
    // tell them apart; their class can.
    bool         (*accepts)(void* panel);
};

// Feats (CSWGuiFeatsCharGen, chargen and level-up): its dispatcher answers A with
// "add the highlighted feat" (0x006F46EF) and X with OK (0x006F46CF) -- the
// reverse of every other screen, Powers included. Swapped at the maintainer's
// request, 2026-09-25, so the pad's A is OK and X adds, and the badges follow.
// Both call the panel's own routines, not its dispatcher: the dispatcher passes
// the event on to the focused control afterwards, and an X dispatched as A would
// then also click a focused OK.
void FeatsConfirmK1(void* panel)
{
    // A button in focus: A presses it, as on the other character-creation
    // screens (GuardChargenConfirmK1). Its click raises the panel's own event.
    void* const focused = *FieldAt<void**>(panel, 0x1C);
    if (ClicksOnConfirmK1(focused)) {
        g_chargenPress = {true, 0};
        using Handle = void(__thiscall*)(void*, int, int);
        reinterpret_cast<Handle>((*reinterpret_cast<void***>(focused))[0x3C / 4])(
            focused, K1_GUI_EVENT_CONFIRM, 1);
        g_chargenPress = {};
        return;
    }
    // Otherwise OK, exactly as Feats' X handler does it: its sound, then
    // OnAccept (0x006F44C0).
    if (void* const manager = *FieldAt<void*>(panel, 0x18)) {
        using PlayGuiSoundFn = void(__thiscall*)(void*, int);
        EngineFn<PlayGuiSoundFn>(0x0040A140)(manager, 0);
    }
    using AcceptFn = void(__thiscall*)(void*);
    EngineFn<AcceptFn>(0x006F44C0)(panel);
}

void FeatsAddK1(void* panel)
{
    // Feats' A handler without its pass-on: its sound, the grid's highlighted
    // feat (0x006ABA50 on the grid at +0x1A08), then OnFeatPicked (0x006F3C20).
    if (void* const manager = *FieldAt<void*>(panel, 0x18)) {
        using PlayGuiSoundFn = void(__thiscall*)(void*, int);
        EngineFn<PlayGuiSoundFn>(0x0040A140)(manager, 0);
    }
    using SelectedFn = int(__thiscall*)(void*);
    const int feat = EngineFn<SelectedFn>(0x006ABA50)(static_cast<char*>(panel) + 0x1A08);
    using PickFn = void(__thiscall*)(void*, int);
    EngineFn<PickFn>(0x006F3C20)(panel, feat);
}

constexpr std::uintptr_t K1_FEATS_DISPATCHER = 0x006F4680;

// Y is Default on every settings screen that has one (2026-09-25, with the Y
// badge on each: "add glyphs to all settings screens"). No settings panel answers
// Y itself -- the five Y registrations on Graphics and Sound are their sliders'
// change callbacks (0x006E0190, 0x006E0F50), which only re-apply the current
// value -- so the pad presses the button, its own registered 0x27 as a click
// does. Gameplay's handler, for one, resets through 0x0061D4E0 and refreshes the
// panel (0x006E68B0). Offsets from the bind calls; the classes are the same
// from the main menu and in game.
struct DefaultButtonK1 {
    std::uintptr_t vtable;
    std::size_t    offset;
};
constexpr DefaultButtonK1 K1_DEFAULT_BUTTONS[] = {
    {0x007586F8, 0x16F8},   // Graphics
    {0x007584A0, 0x1F88},   // Advanced Graphics
    {0x007587C0, 0x1368},   // Sound
    {0x00758550, 0x0F8C},   // Advanced Sound
    {0x00758E00, 0x0788},   // Gameplay
    {0x007585F8, 0x0788},   // Mouse
    {0x007581E8, 0x0A68},   // Feedback
    {0x00758EE0, 0x14E0},   // Auto-Pause
    {0x00759358, 0x01B0},   // Key Mapping
};

void* DefaultButtonOfK1(void* panel)
{
    if (!LooksLikePointerK1(panel)) {
        return nullptr;
    }
    const std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    for (const DefaultButtonK1& entry : K1_DEFAULT_BUTTONS) {
        if (entry.vtable == vtable) {
            return static_cast<char*>(panel) + entry.offset;
        }
    }
    return nullptr;
}

bool HasDefaultButtonK1(void* panel)
{
    return DefaultButtonOfK1(panel) != nullptr;
}

void PressDefaultK1(void* panel)
{
    void* const button = DefaultButtonOfK1(panel);
    if (!button) {
        return;
    }
    const std::uint32_t flags = *FieldAt<std::uint32_t>(button, K1_CTL_FLAGS);
    if ((flags & K1_CTL_FLAG_VISIBLE) == 0 || (flags & K1_CTL_FLAG_DISABLED) != 0) {
        return;
    }
    if (void* const manager = *FieldAt<void*>(panel, 0x18)) {
        using PlayGuiSoundFn = void(__thiscall*)(void*, int);
        EngineFn<PlayGuiSoundFn>(0x0040A140)(manager, 0);   // as Feats' OK
    }
    using HandleFn = void(__thiscall*)(void*, int, int);
    reinterpret_cast<HandleFn>((*reinterpret_cast<void***>(button))[K1_VTABLE_HANDLE_INPUT / 4])(
        button, K1_GUI_EVENT_CONFIRM, 1);
}

// ------------------------------------------------ the echo guard (2026-09-28)
//
// Many buttons do nothing of their own: their click presses a button on their own
// panel. AddEvent (0x0041AB20) stores {receiver, handler, event} at
// [control+0x38], and these handlers are two-instruction thunks through the
// panel's vtable, where +0x50..+0x5C are 0x0040B640..0x0040B670, each
// `HandleInputEvent(E, 1)` on the panel:
//
//   0x00624BA0 -> +0x50 -> A (0x27)      0x00624BC0 -> +0x58 -> X (0x29)
//   0x00624BB0 -> +0x54 -> B (0x28)      0x00644720 -> +0x5C -> Y (0x2A)
//
// A mouse click runs the button, which presses E on the panel, whose dispatcher
// acts and then hands E to the focused control (CSWGuiPanel::HandleInputEvent,
// 0x00409E60) -- normally none, because a click does not set the focus. The pad's
// D-pad does set it, and then one A went wrong two ways:
//   * an echo: the focused button presses the same A back, so the panel acts
//     again and hands A on again, without end -- the status summary's stack
//     overflow (2026-09-25), the Character screen's double level-up and freeze
//     (2026-09-26);
//   * a second action: the panel acts on A, then the focused button presses B, X
//     or Y as well -- A with Cancel focused both accepted and cancelled.
// A scan of all 515 AddEvent calls in the image found 62 such registrations on 39
// panels (reverse-engineering/retained-xbox-gui-events.md). Two halves fix both, for
// every panel at once:
//   1. A with such a button focused presses that button, and only it -- exactly a
//      mouse click (PressFocusedRaiseButtonK1, a remap of the pad's A);
//   2. a panel never hands an event to a focused control whose own handler would
//      press that same event back on it: the hand-off is made inert
//      (GuardPanelEchoK1, a hook on 0x00409E60).
// The chargen screens, Feats and the resolution box keep their own tested A paths.
struct RaiseThunkK1 { std::uintptr_t handler; std::size_t slot; int event; };
constexpr RaiseThunkK1 K1_RAISE_THUNKS[] = {
    {0x00624BA0, 0x50, 0x27},   // AcceptButtonCallback: A
    {0x00624BB0, 0x54, 0x28},   // B
    {0x00624BC0, 0x58, 0x29},   // X
    {0x00644720, 0x5C, 0x2A},   // Y
};
constexpr std::uintptr_t K1_PANEL_RAISE_A = 0x0040B640;   // +0x50; B, X, Y 0x10 apart
constexpr std::uintptr_t K1_BUTTON_HANDLE_INPUT = 0x0041AD40;   // CSWGuiButton: sound, then 0x0041A9D0
constexpr std::uintptr_t K1_CONTROL_HANDLE_INPUT = 0x00418750;  // CSWGuiControl: enter/exit, then the table

void LogGuardK1(const char* what, void* panel, int event, int value)
{
    static int logged = 0;
    if (logged >= 256) {
        return;
    }
    ++logged;
    FILE* f = nullptr;
    if (!fopen_s(&f, "kmrp-confirm-focus.log", "a") && f) {
        const std::uintptr_t vtable = LooksLikePointerK1(panel)
            ? *reinterpret_cast<std::uintptr_t*>(panel) : 0;
        fprintf(f, "%lu guard panel=%08lX event=0x%X value=%d -> %s\n",
                GetTickCount(), static_cast<unsigned long>(vtable), event, value, what);
        fclose(f);
    }
}

// The event `control`'s own handler for `event` presses on `panel`, or 0 when it
// does something else. Only plain buttons (and, for the echo, plain controls):
// a list box runs its own class logic first, and Save / Load's list, which
// carries such a handler, loaded the save correctly with the pad (2026-09-26).
int RaisedOnPanelK1(void* control, void* panel, int event, bool buttonsOnly)
{
    if (!LooksLikePointerK1(control) || !IsReadableK1(control, 0x58) ||
        !IsReadableK1(panel, 4)) {
        return 0;
    }
    void** const vtable = *reinterpret_cast<void***>(control);
    if (!IsReadableK1(vtable, 0x40)) {
        return 0;
    }
    const std::uintptr_t handle = reinterpret_cast<std::uintptr_t>(vtable[0x3C / 4]);
    if (handle != K1_BUTTON_HANDLE_INPUT &&
        (buttonsOnly || handle != K1_CONTROL_HANDLE_INPUT)) {
        return 0;
    }
    const char* const entries = *FieldAt<const char*>(control, 0x38);
    const int count = *FieldAt<int>(control, 0x3C);
    if (count <= 0 || count > 64 || !IsReadableK1(entries, count * 12)) {
        return 0;
    }
    // As 0x00418750 does: the first entry for this event with a handler runs.
    for (int i = 0; i < count; ++i) {
        const char* const entry = entries + i * 12;
        if (*reinterpret_cast<const int*>(entry + 8) != event) {
            continue;
        }
        const std::uintptr_t handler = *reinterpret_cast<const std::uintptr_t*>(entry + 4);
        if (handler == 0) {
            continue;
        }
        if (*reinterpret_cast<void* const*>(entry) != panel) {
            return 0;
        }
        void** const panelVtable = *reinterpret_cast<void***>(panel);
        for (const RaiseThunkK1& thunk : K1_RAISE_THUNKS) {
            if (handler != thunk.handler) {
                continue;
            }
            if (!IsReadableK1(panelVtable, thunk.slot + 4)) {
                return 0;
            }
            const std::uintptr_t raise =
                reinterpret_cast<std::uintptr_t>(panelVtable[thunk.slot / 4]);
            return raise == K1_PANEL_RAISE_A + (thunk.slot - 0x50) * 4 ? thunk.event : 0;
        }
        return 0;
    }
    return 0;
}

// CSWGuiPanel::HandleInputEvent (0x00409E60), with ecx the panel: it hands the
// event to [panel+0x1C]. When that control would only press the same event back,
// the panel has already acted on it, so the hand-off is the echo and is made the
// inert 0x41 (see K1_GUI_EVENT_INERT). Releases too: a control runs its handler
// on a release as well, and the thunk presses with value 1 regardless.
extern "C" int __cdecl GuardPanelEchoK1(void* panel, int* event, int* value)
{
    if (!panel || !event || !value || *event == K1_GUI_EVENT_INERT) {
        return 0;
    }
    if (!IsReadableK1(panel, K1_PANEL_ACTIVE + sizeof(void*))) {
        return 0;
    }
    void* const focused = *FieldAt<void*>(panel, K1_PANEL_ACTIVE);
    if (!focused || RaisedOnPanelK1(focused, panel, *event, false) != *event) {
        return 0;
    }
    LogGuardK1("the focused control would press it back -> inert", panel, *event, *value);
    *event = K1_GUI_EVENT_INERT;
    return 0;
}

void* NavigationPanelK1(void** outTabBar);

// Screens whose A already presses the focused button, or is resolved otherwise:
// Attributes, Skills, Feats, Powers, Portrait and Name (GuardChargenConfirmK1,
// FeatsConfirmK1) and the resolution box (ResolveResolutionConfirmK1).
constexpr std::uintptr_t K1_OWN_CONFIRM_DISPATCHERS[] = {
    0x006F8880, 0x006F6A10, 0x006F4680, 0x006F28C0, 0x006F8FF0, 0x006FA220, 0x006E0CF0,
};

// The focused button, when it is one whose click presses something on its panel.
void* FocusedRaiseButtonK1()
{
    void* const panel = NavigationPanelK1(nullptr);
    if (!panel || InListK1(DispatcherOfK1(panel), K1_OWN_CONFIRM_DISPATCHERS,
                           sizeof(K1_OWN_CONFIRM_DISPATCHERS) /
                               sizeof(K1_OWN_CONFIRM_DISPATCHERS[0]))) {
        return nullptr;
    }
    void* const focused = *FieldAt<void*>(panel, K1_PANEL_ACTIVE);
    if (!LooksLikePointerK1(focused) || !IsReadableK1(focused, 0x58)) {
        return nullptr;
    }
    const std::uint32_t flags = *FieldAt<std::uint32_t>(focused, K1_CTL_FLAGS);
    if ((flags & K1_CTL_FLAG_VISIBLE) == 0 || (flags & K1_CTL_FLAG_DISABLED) != 0) {
        return nullptr;
    }
    return RaisedOnPanelK1(focused, panel, K1_GUI_EVENT_CONFIRM, true) != 0 ? focused : nullptr;
}

bool HasFocusedRaiseButtonK1(void*)
{
    return FocusedRaiseButtonK1() != nullptr;
}

void PressFocusedRaiseButtonK1(void*)
{
    void* const button = FocusedRaiseButtonK1();
    if (!button) {
        return;
    }
    LogGuardK1("A presses the focused button", NavigationPanelK1(nullptr),
               K1_GUI_EVENT_CONFIRM, 1);
    using HandleFn = void(__thiscall*)(void*, int, int);
    reinterpret_cast<HandleFn>((*reinterpret_cast<void***>(button))[K1_VTABLE_HANDLE_INPUT / 4])(
        button, K1_GUI_EVENT_CONFIRM, 1);
}

constexpr ButtonRemapK1 K1_BUTTON_REMAPS[] = {
    { K1_JOURNAL_DISPATCHER, 0x74, K1_EVENT_Y,     "A: Active/Completed", nullptr },
    { K1_JOURNAL_DISPATCHER, 0x77, K1_EVENT_BLACK, "Y: sort order",       nullptr },
    { K1_FEATS_DISPATCHER,   0x74, K1_EVENT_X,     "A: OK (Feats)",       FeatsConfirmK1 },
    { K1_FEATS_DISPATCHER,   0x76, K1_EVENT_A,     "X: Add Feat (Feats)", FeatsAddK1 },
    { 0,                     0x77, K1_EVENT_Y,     "Y: Default (settings)", PressDefaultK1,
      HasDefaultButtonK1 },
    // Last, so the Journal's and Feats' own A come first. See the echo guard.
    { 0,                     0x74, K1_EVENT_A,     "A: the focused button", PressFocusedRaiseButtonK1,
      HasFocusedRaiseButtonK1 },
};

// Does this remap apply to `panel`?
bool RemapAppliesToK1(const ButtonRemapK1& remap, void* panel)
{
    return remap.accepts != nullptr ? remap.accepts(panel)
                                    : DispatcherOfK1(panel) == remap.panel;
}
constexpr int K1_BUTTON_REMAP_COUNT =
    sizeof(K1_BUTTON_REMAPS) / sizeof(K1_BUTTON_REMAPS[0]);


constexpr std::size_t    K1_LISTBOX_ROW        = 0x2C8;   // int16, selected row
constexpr std::size_t    K1_LISTBOX_PROTO      = 0x2C6;   // int16, -1 = plain rows
constexpr std::size_t    K1_LISTBOX_PROTO_ROW  = 0x2C2;   // int16, 1-based proto row

constexpr int K1_EVENT_DPAD_LEFT  = 0x2F;
constexpr int K1_EVENT_DPAD_RIGHT = 0x30;
constexpr int K1_EVENT_SCROLL_UP  = 0x31;
constexpr int K1_EVENT_SCROLL_DOWN = 0x32;

int DirectionEventK1(int dx, int dy)
{
    if (dy < 0) {
        return K1_EVENT_SCROLL_UP;
    }
    if (dy > 0) {
        return K1_EVENT_SCROLL_DOWN;
    }
    return dx < 0 ? K1_EVENT_DPAD_LEFT : K1_EVENT_DPAD_RIGHT;
}

// CGuiInGame, at CClientExoAppInternal+0x40. CClientExoApp::GetGuiInGame
// @ 0x005ED690 reaches it the same way, and CGuiInGame::SetScreen @ 0x0062CF10
// reads the current index from +0x2C and refuses to run at all while +0x108 is
// null. Read only -- KMRP never writes either field.
constexpr std::size_t K1_INTERNAL_GUI_IN_GAME  = 0x40;
constexpr std::size_t K1_IN_GAME_SCREEN_INDEX  = 0x2C;
constexpr int         K1_TAB_COUNT             = 8;

// CSWGuiControl::AddEvent builds a table of 12-byte {receiver, handler, code}
// entries at +0x38 with the count at +0x3C, and CSWGuiControl::HandleInputEvent
// @ 0x00418750 walks it for anything its class did not handle itself.
constexpr std::size_t K1_EVENT_ENTRY_BYTES = 12;
constexpr std::size_t K1_EVENT_ENTRY_CODE  = 8;

using HandleControlInputFn = void(__thiscall*)(void*, int, int);

void* PanelAtK1(int index)
{
    void* const manager = *reinterpret_cast<void**>(K1_GUI_MANAGER_PTR);
    if (!LooksLikePointerK1(manager)) {
        return nullptr;
    }
    void** const panels = *FieldAt<void**>(manager, K1_MGR_PANEL_ARRAY);
    const int count = *FieldAt<int>(manager, K1_MGR_PANEL_COUNT);
    if (!LooksLikePointerK1(panels) || index < 0 || index >= count || count > 256) {
        return nullptr;
    }
    return LooksLikePointerK1(panels[index]) ? panels[index] : nullptr;
}

int PanelCountK1()
{
    void* const manager = *reinterpret_cast<void**>(K1_GUI_MANAGER_PTR);
    if (!LooksLikePointerK1(manager)) {
        return 0;
    }
    const int count = *FieldAt<int>(manager, K1_MGR_PANEL_COUNT);
    return (count > 0 && count <= 256) ? count : 0;
}

// The panel in front carrying this dispatcher, or null. Pure memory reads, so it
// is safe to ask from inside the input hook.
void* PanelWithDispatcherK1(std::uintptr_t dispatcher)
{
    const int count = PanelCountK1();
    for (int i = count - 1; i >= 0; --i) {
        void* const panel = PanelAtK1(i);
        if (!panel) {
            continue;
        }
        if ((*FieldAt<std::uint32_t>(panel, K1_PANEL_FLAGS) & K1_PANEL_FLAG_SKIP) != 0) {
            continue;
        }
        if (DispatcherOfK1(panel) == dispatcher) {
            return panel;
        }
    }
    return nullptr;
}

// Which event this button should send instead, on whatever is on screen now, or
// 0 for the usual one. Asked from the record emitter, so it must not call into
// the engine.
// One entry per bound cue. Small and fixed: only a few of these panels are live
// at once, and a table that cannot grow cannot leak.
struct GuiCueK1 {
    void*       panel;
    void*       control;
    int         id;
    std::size_t follow;             // GuiCueBindingK1::follow
};
GuiCueK1 g_guiCues[16];
constexpr int K1_GUI_CUE_SLOTS =
    sizeof(g_guiCues) / sizeof(g_guiCues[0]);

using GuiLabelCtorFn   = void*(__thiscall*)(void*);
using BindControlFn    = void(__thiscall*)(void*, void*, void*, int);
using ExoStringCtorFn  = void*(__thiscall*)(void*, const char*);
using ExoStringDtorFn  = void(__thiscall*)(void*);

// Is this control still the one the panel has at that id? Panels are heap
// objects and an address can be reused, so a remembered pointer is only trusted
// when the panel still agrees with it.
//
// A second line of defence only. Cues are forgotten when their panel is
// destroyed (ForgetGuiCuesK1); this used to be the ONLY check, and it read the
// panel to decide whether the panel still existed -- which faults once a freed
// screen's memory is released. Nothing here is read until IsReadableK1 agrees.
bool GuiCueStillLiveK1(const GuiCueK1& cue)
{
    if (!cue.panel || !cue.control ||
        !IsReadableK1(cue.panel, K1_PANEL_CONTROL_COUNT + sizeof(int))) {
        return false;
    }
    void** const controls = *FieldAt<void**>(cue.panel, K1_PANEL_CONTROL_ARRAY);
    const int count = *FieldAt<int>(cue.panel, K1_PANEL_CONTROL_COUNT);
    if (cue.id < 0 || cue.id >= count ||
        !IsReadableK1(controls + cue.id, sizeof(void*))) {
        return false;
    }
    return controls[cue.id] == cue.control;
}

// Bind one cue by tag onto a panel that still has its .gui.
void BindOneCueK1(void* panel, const char* tag, std::size_t follow)
{
    void* const control = EngineFn<OperatorNewFn>(K1_OPERATOR_NEW)(
        K1_GUI_LABEL_SIZE);
    if (!control) {
        return;
    }
    EngineFn<GuiLabelCtorFn>(K1_GUI_LABEL_CTOR)(control);

    // The binder takes a CExoString, not a char*, so one is built and destroyed
    // exactly as every call site in the game builds one.
    void* name[2] = { nullptr, nullptr };         // { char* data; int length }
    EngineFn<ExoStringCtorFn>(K1_EXOSTRING_CTOR)(&name, tag);
    EngineFn<BindControlFn>(K1_GUI_PANEL_BIND_CONTROL)(panel, control, &name, 1);
    EngineFn<ExoStringDtorFn>(K1_EXOSTRING_DTOR)(&name);

    const int id = *FieldAt<int>(control, K1_CONTROL_ID);
    void** const controls = *FieldAt<void**>(panel, K1_PANEL_CONTROL_ARRAY);
    const int count = *FieldAt<int>(panel, K1_PANEL_CONTROL_COUNT);
    if (!LooksLikePointerK1(controls) || id < 0 || id >= count ||
        controls[id] != control) {
        // The tag was not in this .gui, or the id collided. The control is not
        // reachable and is deliberately NOT freed: the panel may hold it.
        ++g_stick.guiCuesRejected;
        return;
    }

    // Hidden until the pad is the live device, the same rule the badges follow.
    *FieldAt<std::uint32_t>(control, K1_CONTROL_FLAGS) &= ~K1_CONTROL_FLAG_DRAWN;

    // An empty slot first; a dead one only if there is none, and then only
    // through the safe liveness test.
    for (int pass = 0; pass < 2; ++pass) {
        for (int i = 0; i < K1_GUI_CUE_SLOTS; ++i) {
            const bool usable = pass == 0 ? g_guiCues[i].panel == nullptr
                                          : !GuiCueStillLiveK1(g_guiCues[i]);
            if (usable) {
                g_guiCues[i].panel = panel;
                g_guiCues[i].control = control;
                g_guiCues[i].id = id;
                g_guiCues[i].follow = follow;
                ++g_stick.guiCuesInstalled;
                return;
            }
        }
    }
    ++g_stick.guiCuesRejected;      // table full: drawn, but never toggled
}

// A panel's end: forget its cues and free the labels bound into it. Called from
// ReleaseGff, which the base destructor calls with CSWGuiPanel's own vtable back
// in place and the .gui already released, before it disposes of the control
// array -- so the slots can still be cleared. Until 2026-09-24 nothing did this:
// the table kept screens that loading a save had destroyed, and the next frame
// read one whose memory was gone. The labels are KMRP's, allocated in
// BindOneCueK1; the panel's array refers to them but does not own them (see
// reverse-engineering/custom-gui-controls.md), so they are freed here, the way
// K1ControllerLayout.cpp frees its own entry button.
void ForgetGuiCuesK1(void* panel)
{
    if (!IsReadableK1(panel, K1_PANEL_GFF + sizeof(void*)) ||
        *FieldAt<std::uintptr_t>(panel, 0) != K1_BASE_PANEL_VTABLE ||
        *FieldAt<void*>(panel, K1_PANEL_GFF) != nullptr) {
        return;
    }
    using DeletingDtorFn = void*(__thiscall*)(void*, unsigned);
    for (int i = 0; i < K1_GUI_CUE_SLOTS; ++i) {
        GuiCueK1& cue = g_guiCues[i];
        if (cue.panel != panel) {
            continue;
        }
        void** const controls = *FieldAt<void**>(panel, K1_PANEL_CONTROL_ARRAY);
        const int count = *FieldAt<int>(panel, K1_PANEL_CONTROL_COUNT);
        // Freed only while the panel still holds it at its id. Anything else
        // means the slot was reused, and a leak is safer than a double free.
        if (cue.id >= 0 && cue.id < count &&
            IsReadableK1(controls + cue.id, sizeof(void*)) &&
            controls[cue.id] == cue.control &&
            IsReadableK1(cue.control, sizeof(void*))) {
            controls[cue.id] = nullptr;
            void** const vtable = *FieldAt<void**>(cue.control, 0);
            reinterpret_cast<DeletingDtorFn>(vtable[0])(cue.control, 1);
        }
        cue = GuiCueK1{};
    }
}

// Build whatever cues this panel is owed, while it still has its .gui.
void InstallGuiCuesK1(void* panel)
{
    if (!LooksLikePointerK1(panel)) {
        return;
    }
    const std::uintptr_t vtable = *FieldAt<std::uintptr_t>(panel, 0);
    // The tags are resolved out of this, so there is nothing to bind without it.
    if (!LooksLikePointerK1(*FieldAt<void**>(panel, K1_PANEL_GFF))) {
        return;
    }
    for (int i = 0; i < K1_GUI_CUE_COUNT; ++i) {
        if (K1_GUI_CUES[i].panelVtable == vtable) {
            BindOneCueK1(panel, K1_GUI_CUES[i].tag, K1_GUI_CUES[i].follow);
        }
    }
}

// Show the cues while the pad is the live device, hide them otherwise.
// ------------------------------------------------- controller family (issue #19)
//
// The badges show the buttons of the pad KMRP actually reads, identified the way
// SDL identifies it. XInputGetCapabilitiesEx -- xinput1_4.dll ordinal 108,
// undocumented but present since Windows 8 -- returns the USB vendor and product
// id of the device behind an XInput slot:
//
//   vendor  product   family
//   054C    any       PlayStation
//   057E    any       Switch
//   28DE    1205      Steam Deck (its built-in controls)
//   28DE    11FF      Steam Input's virtual pad -- Steam says what is behind it
//   anything else     Xbox
//
// Steam publishes the physical controller behind each of its virtual pads: the
// file named by the SteamVirtualGamepadInfo environment variable has a [slot N]
// section with that controller's VID and PID, and for Steam's pad the
// capabilities' last field is N. Those ids are then read against the same table.
// A translator that presents an Xbox 360 pad of its own -- DS4Windows, for one --
// is indistinguishable from the pad it imitates and gets Xbox buttons: that is
// what it tells every game, and nothing here second-guesses it.
//
// Asked when the pad KMRP reads connects or moves to another slot, the only
// times the answer can change; for Steam's pad also when Steam rewrites its file,
// looked at once a second, as SDL does. Without the call (Windows 7, a Wine
// without it) the family is Xbox, or Steam Deck when Steam sets SteamDeck=1.
constexpr int K1_GLYPH_XBOX        = 0;
constexpr int K1_GLYPH_PLAYSTATION = 1;
constexpr int K1_GLYPH_SWITCH      = 2;
constexpr int K1_GLYPH_STEAMDECK   = 3;
// The fourth letter of each family's texture resrefs: kmrpb_charexit is the Xbox
// B badge, kmrsb_charexit the PlayStation one. Must match FAMILY_LETTERS in
// tools/build_controller_prompt_textures.py.
constexpr char K1_GLYPH_FAMILY_LETTERS[] = { 'p', 's', 'n', 'd' };
constexpr WORD K1_VENDOR_SONY              = 0x054C;
constexpr WORD K1_VENDOR_NINTENDO          = 0x057E;
constexpr WORD K1_VENDOR_VALVE             = 0x28DE;
constexpr WORD K1_PRODUCT_STEAM_DECK       = 0x1205;
constexpr WORD K1_PRODUCT_STEAM_VIRTUAL_PAD = 0x11FF;
constexpr unsigned long K1_STEAM_INFO_CHECK_MS = 1000;
bool g_steamVirtualPad = false;

// SDL_XINPUT_CAPABILITIES_EX: the documented structure, then the ids.
struct XInputCapabilitiesExK1 {
    XINPUT_CAPABILITIES capabilities;
    WORD  vendorId;
    WORD  productId;
    WORD  productVersion;
    WORD  reserved;
    DWORD steamSlot;       // SDL's unk2: Steam's slot number, for Steam's pad
};
static_assert(sizeof(XInputCapabilitiesExK1) == 32, "SDL_XINPUT_CAPABILITIES_EX is 32 bytes");
using XInputGetCapabilitiesExFn = DWORD(WINAPI*)(DWORD, DWORD, DWORD, XInputCapabilitiesExK1*);

int FamilyForDeviceK1(WORD vendor, WORD product)
{
    if (vendor == K1_VENDOR_SONY) {
        return K1_GLYPH_PLAYSTATION;
    }
    if (vendor == K1_VENDOR_NINTENDO) {
        return K1_GLYPH_SWITCH;
    }
    if (vendor == K1_VENDOR_VALVE && product == K1_PRODUCT_STEAM_DECK) {
        return K1_GLYPH_STEAMDECK;
    }
    return K1_GLYPH_XBOX;
}

bool SteamDeckEnvironmentK1()
{
    char value[8] = {};
    const DWORD length = GetEnvironmentVariableA("SteamDeck", value, sizeof(value));
    return length == 1 && value[0] == '1';
}

// Steam's pad file, and its last-write time, or false outside Steam.
bool SteamPadInfoK1(char (&path)[MAX_PATH], unsigned long long& written)
{
    const DWORD length = GetEnvironmentVariableA("SteamVirtualGamepadInfo", path, MAX_PATH);
    WIN32_FILE_ATTRIBUTE_DATA data;
    if (length == 0 || length >= MAX_PATH ||
        !GetFileAttributesExA(path, GetFileExInfoStandard, &data)) {
        return false;
    }
    written = (static_cast<unsigned long long>(data.ftLastWriteTime.dwHighDateTime) << 32) |
              data.ftLastWriteTime.dwLowDateTime;
    return true;
}

// The family of the pad in XInput `slot`.
int IdentifyPadFamilyK1(int slot)
{
    static XInputGetCapabilitiesExFn getCapabilitiesEx = nullptr;
    static bool resolved = false;
    if (!resolved) {
        resolved = true;
        const HMODULE xinput = LoadLibraryExA("xinput1_4.dll", nullptr,
                                              LOAD_LIBRARY_SEARCH_SYSTEM32);
        if (xinput) {
            getCapabilitiesEx = reinterpret_cast<XInputGetCapabilitiesExFn>(
                GetProcAddress(xinput, MAKEINTRESOURCEA(108)));
        }
    }
    g_steamVirtualPad = false;
    XInputCapabilitiesExK1 capabilities = {};
    if (!getCapabilitiesEx ||
        getCapabilitiesEx(1, static_cast<DWORD>(slot), 0, &capabilities) != ERROR_SUCCESS) {
        return SteamDeckEnvironmentK1() ? K1_GLYPH_STEAMDECK : K1_GLYPH_XBOX;
    }
    if (capabilities.vendorId != K1_VENDOR_VALVE ||
        capabilities.productId != K1_PRODUCT_STEAM_VIRTUAL_PAD) {
        return FamilyForDeviceK1(capabilities.vendorId, capabilities.productId);
    }
    g_steamVirtualPad = true;
    char path[MAX_PATH];
    unsigned long long written = 0;
    if (!SteamPadInfoK1(path, written)) {
        return K1_GLYPH_XBOX;
    }
    g_stick.steamInfoWritten = written;
    char section[24];
    wsprintfA(section, "slot %lu", capabilities.steamSlot);
    char vendor[16] = {};
    char product[16] = {};
    GetPrivateProfileStringA(section, "VID", "", vendor, sizeof(vendor), path);
    GetPrivateProfileStringA(section, "PID", "", product, sizeof(product), path);
    return FamilyForDeviceK1(static_cast<WORD>(std::strtoul(vendor, nullptr, 0)),
                             static_cast<WORD>(std::strtoul(product, nullptr, 0)));
}

// Once per GUI frame; does work only when the answer can have changed.
void UpdateGlyphFamilyK1()
{
    static unsigned long previousGeneration = 0;
    const unsigned long generation = ControllerGenerationK1();
    const int sdlFamily = ControllerSdlFamilyK1();
    if (g_stick.padPresent && sdlFamily >= 0) {
        if (g_stick.glyphFamily != sdlFamily) {
            g_stick.glyphFamily = sdlFamily;
            ++g_stick.glyphChanges;
        }
        g_stick.glyphSlot = -1;
        g_stick.steamInfoWritten = 0;
        previousGeneration = generation;
        return;
    }
    const int slot = g_stick.padPresent ? g_stick.padSlot : -1;
    bool ask = slot != g_stick.glyphSlot || generation != previousGeneration;
    previousGeneration = generation;
    if (!ask && slot >= 0 && g_steamVirtualPad) {
        const unsigned long now = GetTickCount();
        if (now - g_stick.steamInfoChecked >= K1_STEAM_INFO_CHECK_MS) {
            g_stick.steamInfoChecked = now;
            char path[MAX_PATH];
            unsigned long long written = 0;
            const bool found = SteamPadInfoK1(path, written);
            ask = found ? written != g_stick.steamInfoWritten
                        : g_stick.steamInfoWritten != 0;
        }
    }
    if (!ask) {
        return;
    }
    g_stick.glyphSlot = slot;
    g_stick.steamInfoWritten = 0;
    if (slot < 0) {
        return;             // no pad: the badges are hidden, keep the last family
    }
    const int family = IdentifyPadFamilyK1(slot);
    if (family != g_stick.glyphFamily) {
        g_stick.glyphFamily = family;
        ++g_stick.glyphChanges;
    }
}

// For the prompt layer in vendor/K1XboxControls.cpp, which names the Xbox art.
extern "C" char __cdecl KmrpGlyphLetterK1()
{
    const int family = g_stick.glyphFamily;
    return (family >= 0 && family < 4) ? K1_GLYPH_FAMILY_LETTERS[family] : 'p';
}

// A cue is a CSWGuiLabel: CSWGuiControl (0x5C), then its one CSWGuiBorder, whose
// border params sit after a vtable and a 16-byte extent -- so at +0x70 -- with
// the fill resref at +0x40 within them (Lane's swkotor.exe.h; the button
// equivalents are the prompt layer's 0x80 and 0xF4). The .gui names the Xbox art,
// and CSWGuiBorder::SetFillImage (0x00414C00) swaps it for the family's.
constexpr std::size_t K1_LABEL_BORDER_PARAMS = 0x70;
constexpr std::size_t K1_BORDER_PARAMS_FILL  = 0x40;
constexpr std::uintptr_t K1_BORDER_SET_FILL_IMAGE = 0x00414C00;
using SetFillImageFn = void(__thiscall*)(void*, const void*, int);

void MatchCueFamilyK1(void* label)
{
    char* const params = static_cast<char*>(label) + K1_LABEL_BORDER_PARAMS;
    char resref[16];
    std::memcpy(resref, params + K1_BORDER_PARAMS_FILL, sizeof(resref));
    const char wanted = KmrpGlyphLetterK1();
    if (resref[0] != 'k' || resref[1] != 'm' || resref[2] != 'r' || resref[3] == wanted) {
        return;
    }
    resref[3] = wanted;
    EngineFn<SetFillImageFn>(K1_BORDER_SET_FILL_IMAGE)(params, resref, 1);
}

void UpdateGuiCuesK1()
{
    const bool visible = IsControllerInputActiveK1();
    for (int i = 0; i < K1_GUI_CUE_SLOTS; ++i) {
        if (!GuiCueStillLiveK1(g_guiCues[i])) {
            g_guiCues[i].panel = nullptr;
            g_guiCues[i].control = nullptr;
            continue;
        }
        // A cue that follows a control shows only while that control does.
        bool shown = visible;
        if (shown && g_guiCues[i].follow != 0) {
            void* const followed = FieldAt<std::uint8_t>(g_guiCues[i].panel, g_guiCues[i].follow);
            shown = IsReadableK1(followed, K1_CONTROL_FLAGS + sizeof(std::uint32_t)) &&
                    (*FieldAt<std::uint32_t>(followed, K1_CONTROL_FLAGS) & K1_CONTROL_FLAG_DRAWN) != 0;
        }
        std::uint32_t& flags =
            *FieldAt<std::uint32_t>(g_guiCues[i].control, K1_CONTROL_FLAGS);
        const std::uint32_t wanted = shown
            ? (flags | K1_CONTROL_FLAG_DRAWN)
            : (flags & ~K1_CONTROL_FLAG_DRAWN);
        if (wanted != flags) {
            flags = wanted;
            ++g_stick.guiCueToggles;
        }
        if (shown) {
            MatchCueFamilyK1(g_guiCues[i].control);
        }
    }
}

int RemappedButtonEventK1(int slot)
{
    if (InputClassK1() != K1_CLASS_PCGUI) {
        return 0;                       // gameplay keeps every button as it is
    }
    for (int i = 0; i < K1_BUTTON_REMAP_COUNT; ++i) {
        if (K1_BUTTON_REMAPS[i].slot != slot) {
            continue;
        }
        if (K1_BUTTON_REMAPS[i].action != nullptr) {
            void* const top = TopPanelK1();
            if (top != nullptr && RemapAppliesToK1(K1_BUTTON_REMAPS[i], top)) {
                return K1_BUTTON_REMAPS[i].event;
            }
            continue;
        }
        if (PanelWithDispatcherK1(K1_BUTTON_REMAPS[i].panel) != nullptr) {
            return K1_BUTTON_REMAPS[i].event;
        }
    }
    return 0;
}

// The tab strip, or null when the in-game menu is not open.
void* TabBarPanelK1()
{
    const int count = PanelCountK1();
    for (int i = count - 1; i >= 0; --i) {
        void* const panel = PanelAtK1(i);
        if (!panel) {
            continue;
        }
        if ((*FieldAt<std::uint32_t>(panel, K1_PANEL_FLAGS) & K1_PANEL_FLAG_SKIP) != 0) {
            continue;
        }
        if (DispatcherOfK1(panel) == K1_INGAME_MENU_DISPATCHER) {
            return panel;
        }
        // Only the panel in front counts. Once a tab opens a sub-screen of its
        // own -- a container, a confirmation -- that panel owns navigation and
        // the strip below it must be left alone.
        return nullptr;
    }
    return nullptr;
}

bool PanelHasNavigableControlK1(void* panel);   // defined with the geometry below

// The content panel for the tab currently shown: the topmost panel below the
// strip that has anything to focus. Chosen this way rather than by dispatcher
// because it has to work for all eight tabs without a table of screens, and
// rather than "the panel below" because the stack also carries panels with
// nothing navigable on them.
void* TabContentPanelK1(void* tabBar)
{
    if (!tabBar) {
        return nullptr;
    }
    const int count = PanelCountK1();
    for (int i = count - 1; i >= 0; --i) {
        void* const panel = PanelAtK1(i);
        if (!panel || panel == tabBar) {
            continue;
        }
        if ((*FieldAt<std::uint32_t>(panel, K1_PANEL_FLAGS) & K1_PANEL_FLAG_SKIP) != 0) {
            continue;
        }
        if (PanelHasNavigableControlK1(panel)) {
            return panel;
        }
    }
    return nullptr;
}

int CurrentTabIndexK1()
{
    void* const internal = ClientInternalK1();
    if (!internal) {
        return -1;
    }
    void* const inGame = *FieldAt<void*>(internal, K1_INTERNAL_GUI_IN_GAME);
    if (!LooksLikePointerK1(inGame)) {
        return -1;
    }
    const int screen = *FieldAt<int>(inGame, K1_IN_GAME_SCREEN_INDEX);
    return (screen >= 0 && screen < K1_TAB_COUNT) ? screen : -1;
}

// The frame of the tab currently shown. SetActiveControlID's own arithmetic:
// control k is tab k. Verified against the frame test rather than trusted.
struct RectK1 {
    int x, y, w, h;
    int cx() const { return x + w / 2; }
    int cy() const { return y + h / 2; }
};

// Set only while scanning a tab's content panel. Everything runs on the game's
// one thread inside a single navigation call, so a plain flag is enough and a
// parameter threaded through five call sites would not buy anything.
bool g_navAllowSelfNavigating = false;

struct NavContentScopeK1 {
    explicit NavContentScopeK1(bool allow) { g_navAllowSelfNavigating = allow; }
    ~NavContentScopeK1() { g_navAllowSelfNavigating = false; }
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
        // ...unless this is a tab's content panel AND the control's own
        // class handles input. A list box, an editbox and a slider respond
        // through their class dispatcher and register nothing, so "no events"
        // means decoration for a plain control and nothing of the sort here.
        //
        // This is why the Messages list and the Journal's quest list could not
        // be reached: both are CSWGuiListBox with an empty event table, so the
        // wallpaper rule threw them out and focus could only reach the buttons
        // underneath them.
        //
        // Scoped to tab content on purpose. A message box's text pane is also a
        // zero-event list box, and relaxing this everywhere let a confirmation
        // dialog's prose take focus -- which the modal test caught immediately.
        if (!g_navAllowSelfNavigating) {
            return false;
        }
        const std::uintptr_t dispatcher = DispatcherOfK1(control);
        if (!InListK1(dispatcher, K1_NATIVE_DIRECTION_CONTROLS,
                      sizeof(K1_NATIVE_DIRECTION_CONTROLS)
                          / sizeof(K1_NATIVE_DIRECTION_CONTROLS[0]))) {
            return false;
        }
    }

    rect.x = *FieldAt<int>(control, K1_CTL_X);
    rect.y = *FieldAt<int>(control, K1_CTL_Y);
    rect.w = *FieldAt<int>(control, K1_CTL_W);
    rect.h = *FieldAt<int>(control, K1_CTL_H);
    return rect.w > 0 && rect.h > 0;
}

bool PanelHasNavigableControlK1(void* panel)
{
    void** const controls = *FieldAt<void**>(panel, K1_PANEL_CONTROL_ARRAY);
    const int count = *FieldAt<int>(panel, K1_PANEL_CONTROL_COUNT);
    if (!LooksLikePointerK1(controls) || count <= 0 || count > 512) {
        return false;
    }
    RectK1 rect{};
    for (int i = 0; i < count; ++i) {
        if (ControlIsNavigableK1(controls[i], rect)) {
            return true;
        }
    }
    return false;
}

// How strongly a move prefers to stay in its row or column, as a multiple of
// the candidate's cross-axis offset. Large on purpose: a menu is a column, and
// sliding out of that column reads as a bug even when the diagonal distance is
// genuinely shorter.
constexpr int K1_NAV_CROSS_AXIS_PENALTY = 6;

// The rate for a candidate that still OVERLAPS the current control on the cross
// axis. It used to be zero -- overlap waived the penalty outright -- and that
// was wrong wherever a grid's rows overlap each other, because it threw away the
// only thing that could separate the candidates.
//
// The equip screen is the case that found it: a 3x3 grid of 192x192 slots on a
// row pitch of 150, so consecutive rows overlap by 42 pixels, while the columns
// on a pitch of 268 do not overlap at all. Pressing right from BODY scored
// ARM_R, HANDS and WEAP_R at exactly 268 apiece -- same horizontal step, all
// three "in the row" by the overlap test -- and the tie-break is a strict less
// than, so the first in the control array won. The array runs top to bottom, so
// left and right jumped a row up every time.
//
// Overlapping by 42 of 192 is not the same as being in the row. A discount says
// so; a waiver does not.
constexpr int K1_NAV_OVERLAP_PENALTY = 2;

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
    // Never the description pane: see KmrpDescriptionPaneK1. It can pass
    // ControlIsNavigableK1 on a tab screen, where zero-event list boxes are
    // admitted so that the Messages and Journal lists can be reached.
    void* const descriptionPane = KmrpDescriptionPaneK1(panel);

    for (int i = 0; i < count; ++i) {
        void* const candidate = controls[i];
        if (candidate == current || candidate == descriptionPane) {
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
        const long penalty  = static_cast<long>(crossOffset) *
            (crossOverlap > 0 ? K1_NAV_OVERLAP_PENALTY : K1_NAV_CROSS_AXIS_PENALTY);

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
//
// `reachable` says whether a retained event can actually arrive at this panel,
// which is true only of the panel in front. Standing down in favour of native
// navigation that cannot be delivered is not standing down, it is doing nothing:
// on the Abilities tab the content panel is one of the six that navigate
// themselves, but it sits BEHIND the tab strip, and CSWGuiInGameMenu's
// dispatcher handles 0xF3/0xF4 and then routes to its own focused control. The
// press reached the strip and died there, so focus entered the tab and could
// never leave it -- for that tab and, once the flag stuck, every tab after.
// Which axis a press is on, where it matters: a slider consumes only the axis it
// slides along.
enum class NavAxisK1 { Any, Horizontal, Vertical };

constexpr std::uintptr_t K1_SLIDER_DISPATCHER = 0x0041ADF0;

// Does this self-navigating control actually take presses on `axis`?
//
// CSWGuiSlider::HandleInputEvent (0x0041ADF0) decides its orientation from its own
// extent -- `mov eax,[esi+0x10]; cmp eax,[esi+0xC]` at 0x0041AE05, height against
// width -- and a horizontal slider handles only 0x2F/0x30 and their 0x3F/0x40
// aliases, changing its value. Every other direction falls through to the base
// handler and the control's own navigation links. Those links are where vanilla's
// options screens go wrong: on Sound Options, Down from Movie Volume skipped
// Advanced Options for Default, while Up from Default -- a plain button, so KMRP's
// spatial navigation -- reached Advanced correctly (reported 2026-09-24). So a
// slider claims only its sliding axis, and the other goes to ChooseNeighbourK1
// like any button. List boxes and edit boxes still claim both.
bool ControlOwnsAxisK1(void* control, std::uintptr_t dispatcher, NavAxisK1 axis)
{
    if (dispatcher != K1_SLIDER_DISPATCHER || axis == NavAxisK1::Any) {
        return true;
    }
    const int width = *FieldAt<int>(control, 0x0C);
    const int height = *FieldAt<int>(control, 0x10);
    const bool horizontal = height <= width;
    return horizontal == (axis == NavAxisK1::Horizontal);
}

bool PanelNavigatesItselfK1(void* panel, void* active, bool reachable = true,
                            NavAxisK1 axis = NavAxisK1::Any)
{
    const std::uintptr_t panelDispatcher = DispatcherOfK1(panel);
    if (reachable && panelDispatcher != 0 &&
        InListK1(panelDispatcher, K1_NATIVE_DIRECTION_PANELS,
                 sizeof(K1_NATIVE_DIRECTION_PANELS) / sizeof(K1_NATIVE_DIRECTION_PANELS[0]))) {
        return true;
    }
    const std::uintptr_t controlDispatcher = DispatcherOfK1(active);
    return controlDispatcher != 0 &&
        InListK1(controlDispatcher, K1_NATIVE_DIRECTION_CONTROLS,
                 sizeof(K1_NATIVE_DIRECTION_CONTROLS) / sizeof(K1_NATIVE_DIRECTION_CONTROLS[0])) &&
        ControlOwnsAxisK1(active, controlDispatcher, axis);
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
void* ClientInternalK1()
{
    void** const appManager = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT);
    if (!LooksLikePointerK1(appManager)) {
        return nullptr;
    }
    void** const app = static_cast<void**>(appManager[1]);
    if (!LooksLikePointerK1(app)) {
        return nullptr;
    }
    void* const internal = app[1];
    return LooksLikePointerK1(internal) ? internal : nullptr;
}

int InputClassK1()
{
    void* const internal = ClientInternalK1();
    return internal ? *FieldAt<int>(internal, 0x9C) : -1;
}

// Where navigation is currently pointed.
//
// The tab strip stays in front the whole time the menu is open, so "the panel in
// front" cannot answer this once focus has moved down into a tab's content --
// and it cannot be derived either, because both panels carry an active control
// simultaneously and always have. So it is remembered. The state is narrow: one
// flag, cleared whenever the strip stops being in front.
struct TabNavStateK1 {
    bool  inContent = false;
    int   contentTab = -1;          // the tab focus went down into
    void* contentPanel = nullptr;
    unsigned long dispatched = 0;   // directions handed to a control's own handler
};

TabNavStateK1 g_tabNav;

// The panel a direction press should act on, with the strip reported alongside
// it so callers can tell "on the tabs" from "in a tab's content".
void* NavigationPanelK1(void** outTabBar)
{
    void* const tabBar = TabBarPanelK1();
    if (outTabBar) {
        *outTabBar = tabBar;
    }
    if (!tabBar) {
        g_tabNav.inContent = false;         // the menu is gone; forget the rest
        g_tabNav.contentPanel = nullptr;
        return TopPanelK1();
    }
    // The strip itself is never the answer. It used to be, back when left and
    // right walked the eight frames -- which was how a screen was chosen before
    // LT and RT did it. With those working, the strip is not a focus target at
    // all, and a direction press always means the content of the tab on screen.
    void* const content = TabContentPanelK1(tabBar);
    if (!content) {
        g_tabNav.inContent = false;
        g_tabNav.contentPanel = nullptr;
        return nullptr;                     // nothing to navigate here
    }
    g_tabNav.inContent = true;
    g_tabNav.contentPanel = content;
    g_tabNav.contentTab = CurrentTabIndexK1();
    return content;
}

bool KmrpOwnsDirectionsK1(bool vertical)
{
    // In gameplay the D-pad drives the HUD's action bar, so its retained codes
    // are suppressed for the same reason they are in menus: one press, one
    // mechanism. Nothing else in gameplay consumes 0x2F..0x32 -- the survey of
    // AddEvent registrations found no consumer outside the GUI panels.
    if (InputClassK1() == K1_CLASS_PC) {
        return true;
    }
    if (InputClassK1() != K1_CLASS_PCGUI) {
        return false;
    }
    void* tabBar = nullptr;
    void* const panel = NavigationPanelK1(&tabBar);
    if (!panel) {
        return false;
    }
    // Focus inside a tab's content: KMRP handles the press either way -- it
    // dispatches the event to a self-navigating control itself, or it moves
    // focus spatially -- so it owns the press and the retained code must not
    // also go out.
    //
    // This was the D-pad double-step. A focused list made
    // PanelNavigatesItselfK1 true at the control level, which returned false
    // here and let the native code out, while NavigateFocusK1 dispatched the
    // same event to the same list a moment later. Two deliveries, two rows per
    // tap. The left stick moved one row because it never emitted a retained
    // code in the first place, which is exactly the asymmetry that was reported.
    if (tabBar != nullptr && panel != tabBar) {
        return true;
    }
    if (PointsScreenForK1(DispatcherOfK1(panel)) != nullptr) {
        return true;                // see K1_POINTS_SCREENS
    }
    void* const active = *FieldAt<void**>(panel, K1_PANEL_ACTIVE);
    return !PanelNavigatesItselfK1(panel, active, true,
                                   vertical ? NavAxisK1::Vertical : NavAxisK1::Horizontal);
}

// One navigation step. Returns true when focus actually moved, which is what
// the end-to-end tests assert on.
// Move focus to a control on a panel that may not be the one in front. The
// engine is happy to be told this -- SetActiveControl takes the panel as its
// receiver -- and each panel keeps its own active control, which is why the
// active tab stays lit while focus is down in the content.
bool SetFocusK1(void* panel, void* target)
{
    if (!panel || !target) {
        return false;
    }
    EngineFn<SetActiveControlFn>(K1_SET_ACTIVE_CONTROL)(panel, target, 1);
    ++g_stick.navMoves;
    g_stick.lastNavTick = GetTickCount();
    return true;
}

// The settings rows whose value is stepped by a - and a + either side of it
// (2026-09-25). Left and Right on the row press them the way a click does --
// the arrow's own registered 0x27, as the keyboard path always has
// (CaptureK1SettingsCycle, vendor/K1XboxControls.cpp) -- and the focus stays on
// the value. Before, the pad only ever moved the focus spatially: Right from the
// value reached the +, and Right again found nothing ("pressing D-pad right
// doesn't change the settings", play-test that day). Gameplay's Difficulty has
// the Xbox handlers for 0x2F/0x30 registered on its value (0x006E68E0,
// 0x006E6930), but a focused plain button never receives the retained codes
// here -- KmrpOwnsDirectionsK1 -- so pressing its arrows is the one path, the
// same on every row. Offsets from the panels' bind calls
// (tools/extract_control_offsets.py).
struct CycleRowK1 {
    std::uintptr_t vtable;
    std::size_t value;             // the row's own button, which keeps the focus
    std::size_t lower;             // BTN_*LEFT, the -
    std::size_t raise;             // BTN_*RIGHT, the +
};
constexpr CycleRowK1 K1_CYCLE_ROWS[] = {
    {0x00758E00, 0x0CD4, 0x105C, 0x0E98},   // Gameplay: Difficulty
    {0x007584A0, 0x1878, 0x1A3C, 0x1C00},   // Advanced Graphics: Texture Quality
    {0x007584A0, 0x132C, 0x14F0, 0x16B4},   //   Anti-aliasing
    {0x007584A0, 0x0DE0, 0x0FA4, 0x1168},   //   Anisotropy
    {0x00758550, 0x031C, 0x06A4, 0x04E0},   // Advanced Sound: EAX
};

// The row `control` belongs to -- its value or either arrow -- or null.
const CycleRowK1* CycleRowForK1(void* panel, void* control)
{
    if (!LooksLikePointerK1(panel) || !control) {
        return nullptr;
    }
    const std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    char* const base = static_cast<char*>(panel);
    for (const CycleRowK1& row : K1_CYCLE_ROWS) {
        if (row.vtable == vtable &&
            (control == base + row.value || control == base + row.lower ||
             control == base + row.raise)) {
            return &row;
        }
    }
    return nullptr;
}

// Left or Right on a row: its - or +, pressed. The focus goes to the value first
// if the mouse left it on an arrow, so the row stays the thing highlighted. An
// arrow is hidden at the end of its range, where a click could not reach it
// either, and the press then does nothing.
void StepCycleRowK1(void* panel, void* active, const CycleRowK1& row, int dx)
{
    char* const base = static_cast<char*>(panel);
    void* const value = base + row.value;
    if (active != value) {
        SetFocusK1(panel, value);
    }
    void* const arrow = base + (dx < 0 ? row.lower : row.raise);
    const std::uint32_t flags = *FieldAt<std::uint32_t>(arrow, K1_CTL_FLAGS);
    if ((flags & K1_CTL_FLAG_VISIBLE) == 0 || (flags & K1_CTL_FLAG_DISABLED) != 0) {
        return;
    }
    if (void* const manager = *FieldAt<void*>(panel, 0x18)) {
        using PlayGuiSoundFn = void(__thiscall*)(void*, int);
        EngineFn<PlayGuiSoundFn>(0x0040A140)(manager, 1);  // as the points screens
    }
    using HandleFn = void(__thiscall*)(void*, int, int);
    reinterpret_cast<HandleFn>((*reinterpret_cast<void***>(arrow))[K1_VTABLE_HANDLE_INPUT / 4])(
        arrow, K1_GUI_EVENT_CONFIRM, 1);
}

// The row last in focus on a points screen, so Up from the strip returns to it.
struct PointsRowK1 { void* panel; int row; };
PointsRowK1 g_pointsRow = {nullptr, -1};

bool NavigatePointsScreenK1(void* panel, void* active, const PointsScreenK1& s,
                            int dx, int dy)
{
    auto control = [panel](std::size_t offset) {
        return static_cast<void*>(static_cast<char*>(panel) + offset);
    };
    if (g_pointsRow.panel != panel) {
        g_pointsRow = {panel, -1};
    }
    int strip = -1;
    int row = -1;
    for (int i = 0; i < 3; ++i) {
        if (active == control(s.strip[i])) strip = i;
    }
    for (int i = 0; i < s.rowCount; ++i) {
        if (active == control(s.rows[i])) row = i;
    }
    // A - or + button (or a label) holds focus: its row is the one whose value
    // button spans the same height.
    if (row < 0 && strip < 0 && active != nullptr) {
        const int y = *FieldAt<int>(active, K1_CTL_Y) + *FieldAt<int>(active, K1_CTL_H) / 2;
        for (int i = 0; i < s.rowCount; ++i) {
            void* const r = control(s.rows[i]);
            const int top = *FieldAt<int>(r, K1_CTL_Y);
            if (y >= top && y < top + *FieldAt<int>(r, K1_CTL_H)) row = i;
        }
    }
    if (row >= 0) {
        g_pointsRow.row = row;
    }

    if (strip >= 0) {
        if (dx != 0) {
            const int next = strip + (dx < 0 ? -1 : 1);
            if (next >= 0 && next < 3) {
                SetFocusK1(panel, control(s.strip[next]));
            }
        } else if (dy < 0) {
            const int back = g_pointsRow.row >= 0 ? g_pointsRow.row : s.rowCount - 1;
            SetFocusK1(panel, control(s.rows[back]));
            g_pointsRow.row = back;
        }
        return true;
    }
    if (row < 0) {                  // nothing of ours in focus: land on a row first
        row = g_pointsRow.row >= 0 ? g_pointsRow.row : 0;
        SetFocusK1(panel, control(s.rows[row]));
        g_pointsRow.row = row;
        return true;
    }
    if (dy != 0) {
        const int next = row + (dy < 0 ? -1 : 1);
        if (next >= s.rowCount) {
            SetFocusK1(panel, control(s.strip[1]));     // OK, directly below
        } else if (next >= 0) {
            SetFocusK1(panel, control(s.rows[next]));
            g_pointsRow.row = next;
        }
        return true;
    }
    // Left / Right on a row. Its value button takes focus first if a - or +
    // button had it, so the row's enter event has selected it.
    if (active != control(s.rows[row])) {
        SetFocusK1(panel, control(s.rows[row]));
    }
    void* const manager = *FieldAt<void*>(panel, 0x18);
    if (manager != nullptr) {
        using PlayGuiSoundFn = void(__thiscall*)(void*, int);
        EngineFn<PlayGuiSoundFn>(0x0040A140)(manager, 1);  // the handlers' own sound
    }
    using ValueFn = void(__thiscall*)(void*);
    reinterpret_cast<ValueFn>(dx < 0 ? s.lower : s.raise)(panel);
    return true;
}

bool NavigateFocusK1(int dx, int dy)
{
    if (InputClassK1() != K1_CLASS_PCGUI) {
        return false;              // gameplay: the D-pad has its own bindings
    }
    void* tabBar = nullptr;
    void* const panel = NavigationPanelK1(&tabBar);
    if (!panel) {
        return false;
    }
    void* const active = *FieldAt<void**>(panel, K1_PANEL_ACTIVE);
    // A tab's content may hold a list that registers nothing.
    const NavContentScopeK1 scope(tabBar != nullptr);

    if (const PointsScreenK1* points = PointsScreenForK1(DispatcherOfK1(panel))) {
        return NavigatePointsScreenK1(panel, active, *points, dx, dy);
    }

    // No focus moves at all on these (K1_NO_PAD_FOCUS_PANELS): every action there
    // has its own button, and a focused button made A act twice or without end.
    // In front, the retained direction codes stay suppressed (KmrpOwnsDirectionsK1
    // owns them for a panel with nothing that navigates itself, and for tab
    // content), so the engine moves no focus either. The status summary's check
    // was on its own until 2026-09-26, and required no tab strip; the Character
    // screen is tab content.
    if (InListK1(DispatcherOfK1(panel), K1_NO_PAD_FOCUS_PANELS,
                 sizeof(K1_NO_PAD_FOCUS_PANELS) / sizeof(K1_NO_PAD_FOCUS_PANELS[0]))) {
        ++g_stick.navDeclinedNative;
        return false;
    }

    // Pazaak's wager: its dispatcher moves the wager on every direction whatever
    // holds focus, and the codes went out (K1_NATIVE_DIRECTION_PANELS). Moving
    // the focus as well would be a second thing for one press.
    if (tabBar == nullptr && DispatcherOfK1(panel) == K1_PAZAAK_WAGER_DISPATCHER) {
        ++g_stick.navDeclinedNative;
        return false;
    }

    // The SCREEN may be the thing that navigates, rather than any control on it.
    // Powers, Skills, Feats and the Map all work this way: their selection is a
    // cursor on the panel, not a focused control, and no amount of moving a
    // focus rectangle around will touch it.
    //
    // Measured in POWERS::HandleInputEvent, whose one directional arm serves all
    // eight of 0x2F/0x30/0x31/0x32/0x3D/0x3E/0x3F/0x40:
    //
    //     006F297B  push edi                  the event id
    //     006F297C  lea  ecx, [esi+0x19FC]    the grid cursor: +0x0C column,
    //     006F2982  call 0x006CDD80           +0x0D row, +0x04 the count
    //     006F2988  call 0x006F1460           select what it walked to
    //     006F1476  mov  [esi+0x19C4], ebx    the new selection, on the PANEL
    //
    // This was the bug behind "the D-pad cannot move through the powers list".
    // The check below asks PanelNavigatesItselfK1 with reachable=false, which
    // by design drops the panel half of the test and leaves only the control
    // half, so the panel was never dispatched to; the press then fell through to
    // the spatial layer, which sees no controls there because the grid is not
    // made of controls, and died.
    //
    // Tried before the focused control, not after. On these screens the screen
    // owns all four directions and forwards to its own description box where
    // that is what it means -- 0x006F299E takes 0x3A and sends 0x32 to the
    // listbox at +0xFCC -- so a description list that happened to hold focus
    // would otherwise swallow up and down and leave the grid frozen.
    //
    // Deliberate consequence: up no longer climbs back to the tab strip here.
    // The grid wraps (0x006CDDB8 sets the row to 0 on passing the last), so
    // there is no top edge to detect and no press at which leaving is the
    // natural reading. LT and RT still change screen, which is what the strip
    // was being focused to do.
    if (tabBar != nullptr && PanelNavigatesItselfK1(panel, nullptr, true)) {
        const std::uintptr_t screenDispatcher = DispatcherOfK1(panel);
        if (screenDispatcher != 0) {
            reinterpret_cast<HandleControlInputFn>(screenDispatcher)(
                panel, DirectionEventK1(dx, dy), 1);
            ++g_tabNav.dispatched;
            return true;
        }
    }

    // Behind the strip a focused control that owns the direction keys is handed
    // its own retained event directly. Standing down here used to mean the press
    // vanished: nothing routes retained events to a panel that is not in front.
    if (PanelNavigatesItselfK1(panel, active, false,
                               dy != 0 ? NavAxisK1::Vertical : NavAxisK1::Horizontal)) {
        if (tabBar != nullptr) {
            const std::uintptr_t dispatcher = DispatcherOfK1(active);
            if (dispatcher != 0) {
                reinterpret_cast<HandleControlInputFn>(dispatcher)(
                    active, DirectionEventK1(dx, dy), 1);
                ++g_tabNav.dispatched;
                return true;
            }
        }
        ++g_stick.navDeclinedNative;
        return false;              // in front: the engine routes it itself
    }

    // A settings row stepped by - and +: Left and Right press them, and Up and
    // Down leave from the row rather than from an arrow, which has no vertical
    // neighbours of its own.
    void* from = active;
    if (const CycleRowK1* row = CycleRowForK1(panel, active)) {
        if (dy == 0) {
            StepCycleRowK1(panel, active, *row, dx);
            return true;
        }
        from = static_cast<char*>(panel) + row->value;
    }

    // Character creation's Portrait screen: Left and Right pick the previous and
    // next portrait. Its dispatcher (0x006F8FF0) serves them on 0x2F/0x35/0x3F and
    // 0x30/0x36/0x40 (0x006F905F, 0x006F9094), and passes the event on to the
    // focused control afterwards. LT/RT's 0x35/0x36 are sent rather than
    // 0x2F/0x30 because no control there answers them, so focus stays where it
    // is. Only LT and RT cycled portraits until 2026-09-25.
    if (dx != 0 && dy == 0 && DispatcherOfK1(panel) == K1_PORTRAIT_CHARGEN_DISPATCHER) {
        reinterpret_cast<HandleControlInputFn>(K1_PORTRAIT_CHARGEN_DISPATCHER)(
            panel, dx < 0 ? K1_EVENT_PREV_SCREEN : K1_EVENT_NEXT_SCREEN, 1);
        return true;
    }

    void* target = ChooseNeighbourK1(panel, from, dx, dy);
    // Never onto a row's arrow: the row's value holds the focus.
    if (const CycleRowK1* landed = CycleRowForK1(panel, target)) {
        target = static_cast<char*>(panel) + landed->value;
    }
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
    return SetFocusK1(panel, target);
}

// The left stick drives the same navigation as the D-pad. Two thresholds, not
// one: it must be pushed past ENGAGE to register a direction and must fall back
// below RELEASE before another can be registered. Without that gap a stick
// resting near the threshold chatters, and a worn stick with resting drift
// would walk through a menu on its own -- which is the specific thing this must
// never do. RELEASE is well below the 8% movement deadzone for the same reason.
// The right stick scrolls a description pane in menus. Its own thresholds:
// the same hysteresis idea as the navigation stick, but it may be engaged
// deliberately and held, so the engage point is a touch lower and the release
// point well clear of any resting drift.
constexpr float K1_DESC_STICK_ENGAGE  = 0.45f;
constexpr float K1_DESC_STICK_RELEASE = 0.25f;

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
void RequestNavigationK1(int dx, int dy, bool edge, bool fromDpad)
{
    if (dx == 0 && dy == 0) {
        g_stick.navHeldX = 0;
        g_stick.navHeldY = 0;
        return;
    }
    // Menus and the gameplay HUD each get their own copy of the request, with
    // the same edge-then-repeat cadence. Two consumers rather than one because
    // they run from different per-frame hooks, and whichever ran first would
    // otherwise swallow the press before the other saw it.
    //
    // Only the D-PAD reaches the HUD. The left stick feeds this function too --
    // it navigates menus -- and letting it through cycled the bottom-right
    // action bar while the player was simply walking, which is what physical QA
    // caught. In gameplay the left stick means movement and nothing else.
    const unsigned long now = GetTickCount();
    const bool changed = (dx != g_stick.navHeldX) || (dy != g_stick.navHeldY);
    if (edge || changed) {
        // Immediate first move, then wait out the hold delay.
        g_stick.navHeldX = dx;
        g_stick.navHeldY = dy;
        g_stick.navPendingX = dx;
        g_stick.navPendingY = dy;
        if (fromDpad) {
            g_stick.hudPendingX = dx;
            g_stick.hudPendingY = dy;
        }
        g_stick.navRepeatDeadline = now + K1_NAV_HOLD_DELAY_MS;
        return;
    }
    if (now >= g_stick.navRepeatDeadline) {
        g_stick.navPendingX = dx;
        g_stick.navPendingY = dy;
        if (fromDpad) {
            g_stick.hudPendingX = dx;
            g_stick.hudPendingY = dy;
        }
        g_stick.navRepeatDeadline = now + K1_NAV_REPEAT_MS;
    }
}

// Scroll the description pane with the right stick.
//
// This is the engine's own path, not a new one: 17 panels implement the
// retained pair 0x39 / 0x3A as a panel-level scroll of their description box --
// Inventory, Equipment, Journal, Abilities, Powers, Feats, Skills, Store,
// Upgrade and the options screens among them. The stick simply hands the panel
// the event it already understands.
//
// A panel that does not implement the pair drops it in its default case, so the
// stick does nothing on screens with nothing to scroll, which is the required
// behaviour and costs no test of our own.
//
// It cannot move focus or change a list selection because it never touches
// either: the event goes to the PANEL, and the panel's handler scrolls text.
void UpdateDescriptionScrollK1()
{
    if (InputClassK1() != K1_CLASS_PCGUI) {
        g_stick.descHeld = 0;
        return;
    }
    const float ny = static_cast<float>(g_stick.rightY) / K1_AXIS_FULL_SCALE;
    const float magnitude = ny < 0.0f ? -ny : ny;
    if (magnitude < K1_DESC_STICK_RELEASE) {
        g_stick.descHeld = 0;
        return;
    }
    if (magnitude < K1_DESC_STICK_ENGAGE) {
        return;                      // between the two thresholds: hold, do not fire
    }

    // XInput reports the stick up-positive; 0x39 scrolls the description up.
    // One scroll on the first deflection, a pause, then a steady repeat while
    // it is held -- the same cadence the D-pad uses in menus.
    const int want = ny > 0.0f ? -1 : 1;
    const unsigned long now = GetTickCount();
    if (want != g_stick.descHeld) {
        g_stick.descHeld = want;
        g_stick.descDeadline = now + K1_NAV_HOLD_DELAY_MS;
    } else if (now < g_stick.descDeadline) {
        return;
    } else {
        g_stick.descDeadline = now + K1_NAV_REPEAT_MS;
    }

    // The description belongs to the screen, not to the strip in front of it.
    void* const tabBar = TabBarPanelK1();
    void* const target = tabBar ? TabContentPanelK1(tabBar) : TopPanelK1();
    if (!LooksLikePointerK1(target)) {
        return;
    }
    const std::uintptr_t dispatcher = DispatcherOfK1(target);
    if (dispatcher == 0) {
        return;
    }
    reinterpret_cast<HandleControlInputFn>(dispatcher)(
        target, want < 0 ? K1_EVENT_DESC_UP : K1_EVENT_DESC_DOWN, 1);
    ++g_stick.descScrolls;
}

// The GUI's own per-frame update, hooked so focus moves happen where the engine
// expects GUI work to happen rather than inside CExoInput's polling.
// Keep the mouse inside the game window while KOTOR is the foreground window.
//
// Reported for multi-monitor setups: KOTOR turns the camera with mouse movement
// but never clips the cursor, so a wide enough sweep walks it onto the next
// display and the camera stops following. The game imports no ClipCursor at all
// -- SetCapture, ShowCursor and SetCursorPos are the only cursor calls in its
// import table -- so nothing in the engine is fighting this. Issue #20.
//
// The clip is re-applied every frame rather than once, because Windows drops it
// whenever the foreground window changes: that is also what releases it on
// Alt-Tab, on minimise, and if the process dies, so the cursor can never be
// left trapped by a crash. The explicit release below is for the case the
// system keeps it -- losing focus without a foreground change.
//
// It follows the window rather than the monitor, so a windowed game confines to
// its own client area, and moving the window or changing resolution is picked
// up on the next frame.
void UpdateCursorConfinementK1()
{
    HWND foreground = GetForegroundWindow();
    DWORD pid = 0;
    if (foreground) {
        GetWindowThreadProcessId(foreground, &pid);
    }
    const bool ours = foreground != nullptr
        && pid == GetCurrentProcessId()
        && !IsIconic(foreground);

    if (!ours) {
        if (g_stick.cursorConfined) {
            ClipCursor(nullptr);
            g_stick.cursorConfined = 0;
            ++g_stick.cursorReleases;
        }
        return;
    }

    RECT client = {};
    if (!GetClientRect(foreground, &client)
            || client.right <= client.left
            || client.bottom <= client.top) {
        return;                      // mid-resize or zero-sized; try next frame
    }
    POINT corners[2] = {{client.left, client.top}, {client.right, client.bottom}};
    if (!ClientToScreen(foreground, &corners[0])
            || !ClientToScreen(foreground, &corners[1])) {
        return;
    }
    RECT screen = {corners[0].x, corners[0].y, corners[1].x, corners[1].y};
    if (ClipCursor(&screen)) {
        if (!g_stick.cursorConfined) {
            ++g_stick.cursorConfinements;
        }
        g_stick.cursorConfined = 1;
    }
}

extern "C" void __cdecl NativeGuiFrameK1(void* guiManager)
{
    (void)guiManager;
    g_stick.lastGuiTick = GetTickCount();
    UpdateCursorConfinementK1();
    EnsureDeviceCountK1();     // menus re-enumerate devices too

    // Which controller family the badges show, before they are updated.
    UpdateGlyphFamilyK1();
    ControllerLayoutFrameK1(guiManager);

    // Keep the badges in step with the screen and with the live input device.
    // Cheap: it returns immediately unless the panel, its class or the device
    // has actually changed.
    KmrpUpdatePromptsK1();
    ++g_stick.promptUpdates;

    // The cursor answers the same question as the badges -- which device is the
    // player on -- so it is updated in the same frame. This is the native call
    // site it never had: its only other caller is a legacy hook this path does
    // not install, which is why the pointer never hid for a pad.
    KmrpUpdateCursorK1();

    PerformPendingFreeLookExitK1();
    PerformPendingMapOpenK1();

    PerformPendingPartySwitchK1();

    UpdateGuiCuesK1();

    // Our own frame delta, measured across this hook. Counting only; the engine
    // is not touched.
    {
        const unsigned long now = GetTickCount();
        if (g_stick.lastGuiFrameTick != 0) {
            const unsigned long elapsed = now - g_stick.lastGuiFrameTick;
            if (elapsed > g_stick.worstFrameMs) {
                g_stick.worstFrameMs = elapsed;
            }
            if (elapsed >= K1_SLOW_FRAME_MS) {
                ++g_stick.slowFrames;
            }
        }
        g_stick.lastGuiFrameTick = now;
    }

    UpdateDescriptionScrollK1();

    // A button this screen redefines. Performed here rather than in the input
    // hook because the Journal's handlers re-sort and rebuild the list.
    if (g_stick.remapRequestedSlot != 0) {
        const int slot = g_stick.remapRequestedSlot;
        g_stick.remapRequestedSlot = 0;
        if (InputClassK1() == K1_CLASS_PCGUI) {
            for (int i = 0; i < K1_BUTTON_REMAP_COUNT; ++i) {
                if (K1_BUTTON_REMAPS[i].slot != slot) {
                    continue;
                }
                void* panel = nullptr;
                if (K1_BUTTON_REMAPS[i].accepts != nullptr) {
                    void* const top = TopPanelK1();
                    if (top != nullptr && K1_BUTTON_REMAPS[i].accepts(top)) {
                        panel = top;
                    }
                } else {
                    panel = PanelWithDispatcherK1(K1_BUTTON_REMAPS[i].panel);
                }
                if (!panel) {
                    continue;           // the screen went away between the two
                }
                if (K1_BUTTON_REMAPS[i].action != nullptr) {
                    K1_BUTTON_REMAPS[i].action(panel);
                    ++g_stick.remapDispatched;
                    break;
                }
                const std::uintptr_t dispatcher = DispatcherOfK1(panel);
                if (dispatcher != 0) {
                    reinterpret_cast<HandleControlInputFn>(dispatcher)(
                        panel, K1_BUTTON_REMAPS[i].event, 1);
                    ++g_stick.remapDispatched;
                }
                break;
            }
        }
    }

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

// The current target, or OBJECT_INVALID when nothing is targeted. Cheap enough
// to ask every frame, which is what a future "hide the prompt" check would do.
std::uint32_t CurrentTargetK1()
{
    void** const appManager = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT);
    if (!LooksLikePointerK1(appManager)) {
        return K1_OBJECT_INVALID;
    }
    void** const app = static_cast<void**>(appManager[1]);
    if (!LooksLikePointerK1(app)) {
        return K1_OBJECT_INVALID;
    }
    void* const internal = app[1];
    if (!LooksLikePointerK1(internal)) {
        return K1_OBJECT_INVALID;
    }
    return *FieldAt<std::uint32_t>(internal, K1_INTERNAL_TARGET);
}

bool HasTargetK1()
{
    const std::uint32_t target = CurrentTargetK1();
    return target != K1_OBJECT_INVALID && target != 0;
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
// Leaving free look, asked of the engine's own router rather than
// reimplemented: 0x06's handler at 0x0062184C tests the camera mode itself,
// which is what separates "leave free look" from "select the previous target"
// -- the two meanings of this one event.
//
// Called from BOTH per-frame hooks on purpose. The movement heartbeat runs while
// the character is being driven, and in free look it is the camera that moves,
// not the character; the GUI frame runs whenever the interface updates. Whichever
// ticks first consumes the request, and the staleness test keeps a late one from
// firing into a session that has already left.
void PerformPendingFreeLookExitK1()
{
    if (g_stick.freeLookExitRequested != 0) {
        const unsigned long requested = g_stick.freeLookExitRequested;
        g_stick.freeLookExitRequested = 0;
        if (GetTickCount() - requested <= 250ul &&
            InputClassK1() == K1_CLASS_FREELOOK) {
            void* const internal = ClientInternalK1();
            if (internal) {
                EngineFn<HandleInputEventFn>(K1_HANDLE_INPUT_EVENT)(
                    internal, K1_EVENT_FREELOOK_EXIT, 1);
                ++g_stick.freeLookExits;
            }
        }
    }
}

// Start in the world: the Map, through the engine's own hotkey handler, with
// every guard it applies (a dead player, no party, a modal already up). Checked
// again here, because the input class can change between the press and the
// frame.
void PerformPendingMapOpenK1()
{
    if (g_stick.mapOpenRequested == 0) {
        return;
    }
    const unsigned long requested = g_stick.mapOpenRequested;
    g_stick.mapOpenRequested = 0;
    if (GetTickCount() - requested > 250ul || InputClassK1() != K1_CLASS_PC) {
        return;
    }
    void* const internal = ClientInternalK1();
    if (!internal) {
        return;
    }
    EngineFn<HandleInputEventFn>(K1_HANDLE_INPUT_EVENT)(internal, K1_EVENT_MENU_MAP, 1);
    ++g_stick.mapOpens;
}

// R3 on a screen that is about a party member: show the next one.
//
// Dispatched to the PANEL, not to CClientExoAppInternal. The two are different
// actions that share one name: 0x09 changes who the player controls in the
// world, 0xCE changes who a screen is displaying. In a menu only the second is
// wanted -- swapping the controlled character underneath an open Equip screen
// would be a different feature, and a surprising one.
//
// Performed here rather than in the input hook because these handlers rebuild
// the screen around the new character, which is the same reason the Journal's
// remapped buttons are deferred to this frame.
//
// The 250 ms window matches the other deferred actions: a press that could not
// be performed because the screen changed in between is dropped rather than
// applied late to whatever is in front now.
void PerformPendingPartySwitchK1()
{
    if (g_stick.partySwitchRequested == 0) {
        return;
    }
    const unsigned long requested = g_stick.partySwitchRequested;
    g_stick.partySwitchRequested = 0;
    if (GetTickCount() - requested > 250ul ||
        InputClassK1() != K1_CLASS_PCGUI) {
        return;
    }
    for (int i = 0; i < K1_PARTY_SWITCH_PANEL_COUNT; ++i) {
        void* const panel = PanelWithDispatcherK1(K1_PARTY_SWITCH_PANELS[i]);
        if (!panel) {
            continue;               // not the screen in front
        }
        reinterpret_cast<HandleControlInputFn>(K1_PARTY_SWITCH_PANELS[i])(
            panel, K1_GUI_EVENT_CHANGE_CHAR, 1);
        ++g_stick.partySwitches;
        return;
    }
}

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

    // Gameplay only. This checked free look but never the input class, so a
    // stick click in any menu still swung the character's weapon behind the
    // open screen -- measured on Equipment, Inventory, Messages, Journal, Map
    // and Options, where the performed counter rose on every press.
    if (InputClassK1() != K1_CLASS_PC) {
        ++g_stick.flourishesDeclined;
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

// A in gameplay: the default action on the target.
//
// Same discipline as the flourish -- requested from the input hook, performed
// here on the gameplay frame, and declined rather than guessed at when there is
// nothing to act on. The engine's handler checks the target itself; this checks
// too, so the counters distinguish "pressed with no target" from "pressed and
// the engine declined".
void PerformPendingInteractionK1()
{
    if (g_stick.interactRequestedTick == 0) {
        return;
    }
    const unsigned long requested = g_stick.interactRequestedTick;
    g_stick.interactRequestedTick = 0;

    if (GetTickCount() - requested > 250ul) {
        ++g_stick.interactsDeclined;
        return;
    }
    if (InputClassK1() != K1_CLASS_PC) {
        ++g_stick.interactsDeclined;      // only in the world
        return;
    }
    // A belongs to the HUD action bar while one of its slots has focus. Both
    // consumers ask the same question, so exactly one acts however the two
    // per-frame hooks happen to be ordered.
    // Ask with the pointer this frame's HUD hook was handed, never with the
    // vendor's cached one: that global outlives the object it points at across a
    // screen change, and a null argument used to fall back to it.
    void* const hudInterface = reinterpret_cast<void*>(g_stick.hudInterface);
    if (LooksLikePointerK1(hudInterface) &&
        KmrpActionBarFocusedK1(hudInterface) != 0) {
        ++g_stick.interactsDeclined;
        return;
    }
    if (!HasTargetK1()) {
        ++g_stick.interactsDeclined;      // nothing targeted: A must do nothing
        return;
    }
    void** const appManager = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT);
    void** const app = appManager ? static_cast<void**>(appManager[1]) : nullptr;
    void* const internal = LooksLikePointerK1(app) ? app[1] : nullptr;
    if (!LooksLikePointerK1(internal)) {
        ++g_stick.interactsDeclined;
        return;
    }
    EngineFn<HandleInputEventFn>(K1_HANDLE_INPUT_EVENT)(
        internal, K1_EVENT_DEFAULT_ACTION, 1);
    ++g_stick.interactsPerformed;
}

// Keep the engine's device count high enough to reach our joystick.
//
// The init hook raises it once, at startup. That is not enough: the count can
// drop back to 2 while the game runs -- measured live, with the poll loop then
// making **zero** GetJoystickBuffer calls in two seconds while the movement
// hook kept running, so the pad went completely dead mid-session. Writing 3
// back restored polling immediately, 126 calls in the next 2.5 seconds, which
// is what identified this as the cause rather than a deadzone or a binding.
//
// The likely trigger is a device re-enumeration -- plugging a controller in
// after launch is the obvious one -- so the count has to be re-asserted rather
// than set once. It is two instructions on a frame that already runs.
// Measured, not assumed: classes 0 (ICPC) and 4 (ICFreeLook) reject the two
// analog axis events permanently -- add=[0 3 3 3 0 3] in every log, and retrying
// every frame for a whole session won none of them back. That is NOT a fault and
// not the cause of the 0x005E0DFB crash: gameplay movement does not come from
// those descriptions at all, it comes from the movement hook, which is why the
// pad has always worked in gameplay despite class 0 refusing them.
//
// Gating the device count on those classes was tried and was wrong. It withheld
// the pad for an entire session (cls=0/1024) and the crash still happened, so
// polling unregistered per-class state is not the mechanism.
// Raising the device count claims a pad exists. This is the other half of that
// claim: the pad's raw state block, which DirectInput never created because
// there is no DirectInput pad.
//
// CExoRawInputInternal::GetLastState computes
// [rawInput+0x30] + (deviceIndex - 2) * 0x74 and dereferences it. With the base
// NULL that is a null read, and it is what crashed the game the moment R3
// entered free look -- measured at 0x005E399B with eax = 0, called from
// GetEvents at 0x005E2968 with (2, 0), offset 0 being DIJOFS_X.
//
// Free look reaches it because vanilla registers the analog stick events in ICPC
// and ICFreeLook only, and the free-look enter handler calls
// CExoInput::ClearEvents, which empties the buffered records the pad normally
// speaks through -- so the poll falls back to raw state.
//
// Allocated with the engine's own operator new, as the record buffers are, so a
// future engine free of this pointer is legal. Only when the slot is null: a
// real DirectInput joystick would have its own block and must keep it.
void EnsurePadStateK1()
{
    void* const raw = *FieldAt<void*>(g_stick.input, K1_INPUT_RAW_INPUT);
    if (!LooksLikePointerK1(raw)) {
        return;
    }
    void** const slot = FieldAt<void*>(raw, K1_RAW_JOYSTICK_STATE);
    if (*slot != nullptr) {
        return;                     // the engine owns one; leave it alone
    }
    const std::size_t bytes = K1_RAW_JOYSTICK_STRIDE * K1_PAD_STATE_SLOTS;
    void* const block = EngineFn<OperatorNewFn>(K1_OPERATOR_NEW)(bytes);
    if (!block) {
        return;
    }
    std::memset(block, 0, bytes);   // centred axes, nothing pressed
    *slot = block;
    ++g_stick.padStateAllocated;
}

void EnsureDeviceCountK1()
{
    if (!g_stick.input) {
        return;
    }
    std::int32_t* const count = IntAt(g_stick.input, K1_INPUT_DEVICE_COUNT);
    if (*count < K1_DEVICE_JOYSTICK + 1) {
        *count = K1_DEVICE_JOYSTICK + 1;
        ++g_stick.deviceCountRestored;
    }
    EnsurePadStateK1();
}

// Is the analog stick the thing driving movement right now?
//
// This is the whole gate on skipping the engine's Vector::Normalize, so it is
// deliberately conservative: every condition must hold, and any doubt means
// vanilla behaviour.
//
//   registered        the descriptions took, so the pad can reach movement
//   gameplay class    ICPC only; menus, dialogue and free look never override
//   fresh buffer      GetJoystickBuffer ran recently, so a disconnect (whose
//                     XInput read fails and leaves the axes at zero) or a
//                     stalled poll loop cannot leave the bypass latched on
//   driving           post-deadzone magnitude is non-zero, so a centred or
//                     barely-touched stick leaves the keyboard's normalize alone
//
// The keyboard is covered by the last two: it does not go through
// GetJoystickBuffer at all, so analogMagnitude stays zero and Normalize runs
// exactly as it always has. Without that a keyboard diagonal, which is +/-1 on
// each axis, would travel sqrt(2) times too fast.
bool NativeAnalogDrivingK1()
{
    if (!g_stick.registered) {
        return false;
    }
    if (InputClassK1() != K1_CLASS_PC) {
        return false;
    }
    if (g_stick.lastBufferTick == 0 ||
        (GetTickCount() - g_stick.lastBufferTick) > 250ul) {
        return false;
    }
    return g_stick.analogMagnitude > 0.0f;
}

extern "C" void __cdecl NativeJoystickMovementK1(void* playerControl)
{
    if (!playerControl) {
        return;
    }
    g_stick.lastMovementTick = GetTickCount();
    g_stick.playerControl = playerControl;
    EnsureDeviceCountK1();
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
    // speeds. The hook still writes nothing; it is the gameplay heartbeat, it
    // tells the older XInput layer when to stand its keystroke synthesis down,
    // and it drives the diagnostic dump.
    //
    // It also decides, once per frame and just before Control reaches its
    // Normalize call, whether the analog magnitude survives. Control does:
    //
    //     vector = (-LeftRight, UpDown)
    //     Vector::Normalize(vector)          <-- discards the magnitude
    //     if (walking) vector *= 0.5
    //
    // so with the normalize left in place the stick only ever chooses a
    // direction and every deflection runs at full speed. That is what made a
    // 6.5% input move at 8.10, the maximum: measured, not inferred. Skipping it
    // while the stick drives is the entire point of the analog path.
    g_stick.overrideActive = NativeAnalogDrivingK1();
    float sampleX = 0.0f;
    float sampleY = 0.0f;
    ReadNativeStickK1(sampleX, sampleY);   // diagnostics only

    PerformPendingFreeLookExitK1();
    PerformPendingMapOpenK1();
    PerformPendingStickActionsK1();
    PerformPendingInteractionK1();
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
    // overrideActive is set once per frame by NativeJoystickMovementK1, which
    // runs immediately before Control reaches this call. When the analog stick
    // is driving, Normalize is skipped and the vector keeps its magnitude, so
    // speed becomes proportional. Otherwise -- keyboard, centred stick,
    // disconnect, or any input class but gameplay -- Normalize runs through the
    // absolute pointer and vanilla is preserved exactly.
    //
    // The hook consumes either way. That is not an optimisation, it is the
    // crash fix: the stolen bytes are a relative call and must never be
    // re-executed from the trampoline.
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

    // 2048, not 512, and the size is load-bearing.
    //
    // wsprintfA does no bounds checking. This line had grown to 521 bytes
    // in a 512-byte array -- 409 of the lines in one session's log were
    // already past 500 -- and the nine bytes over the end tripped /GS on
    // return: int 0x29 with ecx=2, FAST_FAIL_STACK_COOKIE_CHECK_FAILURE.
    // The game froze on loading a save, because the counters have to grow
    // wide before the line is long enough to overrun.
    //
    // wsprintfA will not emit more than 1024 bytes including the null, so
    // 2048 cannot be overrun however many fields are added later. Anything
    // added here still has to respect that 1024-byte ceiling or the line
    // will simply be truncated.
    char line[2048];
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
        // dlg = which ICDialog registrations took, one bit each in the order
        // A, up, down, LB, RB. 0x1F means all five.
        // act = world interactions performed/declined; tgt = the current target
        // id, 7F000000 when nothing is targeted.
        // ovr = the Normalize bypass this frame; amag = post-deadzone stick
        // magnitude x1000. Together they say whether the analog path is
        // actually driving, which is the thing that was silently off.
        // ovr = the Normalize bypass this frame. rmag/amag/dz are the stick's
        // raw magnitude, its magnitude after the deadzone, and the deadzone
        // constant itself, all x1000 -- so a log line says what the stick did,
        // what survived, and what the threshold was, without reading the source.
        "fl=%d dlg=%02X mg=%02X flour=%lu/%lu act=%lu/%lu tgt=%08lX "
        // dcr = times the engine's device count had dropped below ours and had
        // to be put back. Non-zero means the pad would have gone dead without
        // the guard, which is worth knowing rather than silently repairing.
        // The right-stick camera chain, end to end: the raw axes the buffer hook
        // last stored, how often the bridge ran, wrote, and bailed on its
        // deadzone, and the delta it added versus the field's value straight
        // after. cam* are x100.
        "ovr=%d rmag=%ld amag=%ld dz=%ld dcr=%lu cls=%lu/%lu reb=%lu "
        "rx=%ld ry=%ld camrun=%lu camwr=%lu camdz=%lu camapp=%ld camcls=%lu camown=%lu "
        "nav=%lu/%lu hud=%lu/%lu/%lu/%08lX/%d pad=%lu prm=%lu dsc=%lu gui=%lu tab=%lu tabin=%d mve=%lu/%lu/%lu move=%d->%d dir=%d rum=%lu/%lu/%08lX raw=%08lX/%08lX slot=%d rtab=%lu rmp=%lu fle=%lu drp=%lu psw=%lu cue=%lu/%lu/%lu sbf=%lu map=%lu hrel=%lu gly=%d/%lu frm=%lu/%lu dt=%ld/%ld tex=%ld/%ld/%ld/%ld tid=%ld/%ld dev=%08lX cur=%d/%lu/%lu\r\n",
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
        g_stick.freeLookBound, g_stick.dialogBound,
        g_stick.miniGameBound,
        g_stick.flourishesPerformed, g_stick.flourishesDeclined,
        g_stick.interactsPerformed, g_stick.interactsDeclined,
        // tgt comes before ovr in the format string; the new fields were
        // inserted ahead of it once and every column after act= read the wrong
        // argument, which showed up as a boolean printing 2, 4, 5 and 7.
        static_cast<unsigned long>(CurrentTargetK1()),
        g_stick.overrideActive ? 1 : 0,
        static_cast<long>(g_stick.rawMagnitude * 1000.0f),
        static_cast<long>(g_stick.analogMagnitude * 1000.0f),
        static_cast<long>(K1_STICK_DEADZONE * 1000.0f),
        g_stick.deviceCountRestored,
        g_stick.classRetriesTaken, g_stick.deviceCountDeferred,
        g_stick.inputRebuilds,
        static_cast<long>(g_stick.rightX), static_cast<long>(g_stick.rightY),
        g_stick.cameraFeedCalls, g_stick.cameraWrites, g_stick.cameraBelowDeadzone,
        static_cast<long>(g_stick.cameraApplied * 100.0f),
        g_stick.cameraWrongClass, g_stick.cameraNoOwner,
        g_stick.navMoves, g_stick.navDeclinedNative,
        g_stick.hudMoves, g_stick.hudCycles, g_stick.hudActivations,
        g_stick.hudInterface, g_stick.hudState,
        g_stick.padActiveTicks, g_stick.promptUpdates, g_stick.descScrolls,
        g_stick.lastGuiTick,
        g_tabNav.dispatched,
        g_tabNav.inContent ? 1 : 0,
        g_movie.frames, g_movie.skips, g_movie.refused,
        g_stick.navFromY, g_stick.navToY, g_stick.navDir,
        g_stick.rumbleCalls, g_stick.rumbleSent, g_stick.rumbleLast,
        g_stick.rumbleRawA, g_stick.rumbleRawB, g_stick.padSlot,
        g_stick.rumbleTableInstalled, g_stick.remapDispatched,
        g_stick.freeLookExits, g_stick.dpadRepeats, g_stick.partySwitches,
        g_stick.guiCuesInstalled, g_stick.guiCuesRejected,
        g_stick.guiCueToggles, g_stick.saveBuffersFreed,
        // map: Start opening the Map from the world; hrel: action-bar focus
        // handed back to the world by B.
        g_stick.mapOpens, g_stick.hudReleases,
        // gly: the controller family the badges show (0 Xbox, 1 PlayStation,
        // 2 Switch, 3 Steam Deck), and how many times it has changed.
        g_stick.glyphFamily, g_stick.glyphChanges,
        // frm: frames at or over K1_SLOW_FRAME_MS, and the worst seen.
        g_stick.slowFrames, g_stick.worstFrameMs,
        // dt: the engine's own frame delta and its high-water mark, in
        // milliseconds -- both are floats in seconds, so x1000.
        static_cast<long>(*reinterpret_cast<const float*>(K1_G_DELTA_T) * 1000.0f),
        static_cast<long>(*reinterpret_cast<const float*>(K1_G_MAX_DELTA_T) * 1000.0f),
        // tex: the engine's texture timers, exactly as it keeps them.
        static_cast<long>(*reinterpret_cast<const int*>(K1_G_MAX_TEXTURE_TIME)),
        static_cast<long>(*reinterpret_cast<const int*>(K1_G_CURRENT_TEXTURE_TIME)),
        static_cast<long>(*reinterpret_cast<const int*>(K1_G_LOAD_IMAGE_TIME)),
        static_cast<long>(*reinterpret_cast<const int*>(K1_G_MAX_TEX_LOAD_TIME)),
        // tid: the highest GL texture name seen, against the size of the
        // unbounded bucket arrays it indexes. Reaching the second number is
        // an out-of-range write in AddPartToMeshBuckets.
        static_cast<long>(*reinterpret_cast<const int*>(K1_G_MAX_TEX_ID)),
        K1_TEXTURE_BUCKET_ENTRIES,
        KmrpDeviceStateK1(),
        // cur: whether the mouse is clipped to the window right now,
        // and how many times the clip has been taken and given back.
        // Appended at the very end -- see the warning above about
        // inserting a column into the middle of the format string.
        g_stick.cursorConfined, g_stick.cursorConfinements,
        g_stick.cursorReleases);

    HANDLE file = CreateFileA("kmrp-native-joystick.log", FILE_APPEND_DATA,
                              FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD done = 0;
        WriteFile(file, line, static_cast<DWORD>(written), &done, nullptr);
        CloseHandle(file);
    }
}

// Is a confirm input down right now: A on the pad, or Enter or Space? The
// Controller Layout screen uses it to ignore the press that opened it -- see
// the arming rule in K1ControllerLayout.cpp. lastButtons is written by the
// engine's per-frame joystick poll, in menus as well as in play.
// At file scope, outside the anonymous namespace, so the layout screen links.
bool ControllerConfirmHeldK1()
{
    return (g_stick.lastButtons & 0x1000) != 0 ||       // XINPUT_GAMEPAD_A
           (GetAsyncKeyState(VK_RETURN) & 0x8000) != 0 ||
           (GetAsyncKeyState(VK_SPACE) & 0x8000) != 0;
}
