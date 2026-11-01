#include "K1XboxControlsXInput.h"
#include "K1NativeJoystick.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <windows.h>

#if defined(_MSC_VER)
// create-patch.bat links only sqlite3 and the cached Common library, and MSVC
// does not pull user32 in by default, but SendInput and the two focus queries
// below live there. MinGW gets it from its default library set, so declaring
// it here covers the gap without touching build infrastructure that every
// other patch shares.
#pragma comment(lib, "user32.lib")
#endif

namespace {

// ---------------------------------------------------------------------------
// XInput, resolved at runtime
// ---------------------------------------------------------------------------
// create-patch.bat and create-patch.py both hardcode their link line to
// sqlite3 and kernel32, so linking an XInput import library would mean editing
// build infrastructure every other patch shares. GetProcAddress costs nothing
// and keeps this patch self-contained.
//
// The structs are declared here rather than pulled from <xinput.h> so the MSVC
// and MinGW builds cannot disagree about which SDK header they happened to
// find. The layout is fixed ABI and has not changed since XInput 9.1.0.

struct XInputGamepad {
    std::uint16_t buttons;
    std::uint8_t leftTrigger;
    std::uint8_t rightTrigger;
    std::int16_t thumbLX;
    std::int16_t thumbLY;
    std::int16_t thumbRX;
    std::int16_t thumbRY;
};

struct XInputState {
    std::uint32_t packetNumber;
    XInputGamepad gamepad;
};

using XInputGetStateFn = std::uint32_t(__stdcall*)(std::uint32_t, XInputState*);

constexpr std::uint16_t XI_START = 0x0010;
constexpr std::uint16_t XI_BACK = 0x0020;
constexpr std::uint16_t XI_LEFT_THUMB = 0x0040;
constexpr std::uint16_t XI_RIGHT_THUMB = 0x0080;
constexpr std::uint16_t XI_LEFT_SHOULDER = 0x0100;
constexpr std::uint16_t XI_RIGHT_SHOULDER = 0x0200;
constexpr std::uint16_t XI_A = 0x1000;
constexpr std::uint16_t XI_B = 0x2000;
constexpr std::uint16_t XI_X = 0x4000;
constexpr std::uint16_t XI_Y = 0x8000;

// wButtons leaves 0x0400 and 0x0800 unused. Folding the analog triggers into
// them lets one table cover every digital input instead of special-casing two.
constexpr std::uint16_t XI_LEFT_TRIGGER = 0x0400;
constexpr std::uint16_t XI_RIGHT_TRIGGER = 0x0800;

// ---------------------------------------------------------------------------
// Scancodes
// ---------------------------------------------------------------------------
// DirectInput DIK_* values and the scancodes SendInput takes with
// KEYEVENTF_SCANCODE are the same set-1 codes, so nothing here needs a
// virtual-key translation table. The one rule: a code with 0x80 set is an
// E0-prefixed extended key and needs KEYEVENTF_EXTENDEDKEY. That is why the
// arrows and the Home/End/Insert/Delete block sit above 0x80, matching the
// DIK_* constants in K1XboxControls.cpp exactly.

constexpr std::uint8_t SC_ESCAPE = 0x01;
constexpr std::uint8_t SC_TAB = 0x0F;
constexpr std::uint8_t SC_Q = 0x10;
constexpr std::uint8_t SC_E = 0x12;
constexpr std::uint8_t SC_R = 0x13;
constexpr std::uint8_t SC_RETURN = 0x1C;
constexpr std::uint8_t SC_F = 0x21;
constexpr std::uint8_t SC_G = 0x22;
constexpr std::uint8_t SC_X = 0x2D;
constexpr std::uint8_t SC_V = 0x2F;
constexpr std::uint8_t SC_SPACE = 0x39;
constexpr std::uint8_t SC_CAPSLOCK = 0x3A;
constexpr std::uint8_t SC_HOME = 0xC7;
constexpr std::uint8_t SC_END = 0xCF;
constexpr std::uint8_t SC_INSERT = 0xD2;
constexpr std::uint8_t SC_DELETE = 0xD3;

// ---------------------------------------------------------------------------
// Button table
// ---------------------------------------------------------------------------
// Buttons that mean one thing in the world and another in a menu send both
// keys at once. Nothing here checks which context is active, because the main
// mod already resolves it: CaptureK1GenericButton only runs inside
// CaptureActionBarInputK1's menu-panel branch, so End/Home/Insert are inert
// during gameplay, while Tab/X/V are engine action bindings that GUI panels
// ignore. Whichever half is meaningful wins; the other is dropped by code that
// already exists.
//
// The A button's Enter+R pair is why the demand set below counts keys rather
// than flagging them.

struct ButtonBinding {
    std::uint16_t mask;
    std::uint8_t primary;
    std::uint8_t secondary;  // 0 when the button sends a single key
};

// The D-pad is deliberately absent: it is driven by ApplyDpad as repeating taps
// rather than through the demand set. The set produces exactly one edge per
// state change, so a held direction moved the selection one row and then sat
// there. A keyboard does not behave that way -- holding an arrow key makes the
// OS auto-repeat, and the engine sees a stream of keydowns -- so holding a
// direction here was strictly less faithful than the keyboard it emulates.
constexpr ButtonBinding BUTTON_BINDINGS[] = {
    {XI_A,              SC_RETURN,   SC_R},
    {XI_B,              SC_DELETE,   0},
    {XI_X,              SC_G,        SC_END},
    {XI_Y,              SC_F,        SC_HOME},
    {XI_LEFT_SHOULDER,  SC_SPACE,    SC_INSERT},
    {XI_RIGHT_SHOULDER, SC_TAB,      0},
    {XI_LEFT_TRIGGER,   SC_Q,        0},
    {XI_RIGHT_TRIGGER,  SC_E,        0},
    {XI_BACK,           SC_V,        0},
    {XI_START,          SC_ESCAPE,   0},
    {XI_LEFT_THUMB,     SC_X,        0},
    {XI_RIGHT_THUMB,    SC_CAPSLOCK, 0},
};

constexpr int BUTTON_BINDING_COUNT =
    sizeof(BUTTON_BINDINGS) / sizeof(BUTTON_BINDINGS[0]);

// ---------------------------------------------------------------------------
// Stick thresholds
// ---------------------------------------------------------------------------
// Every threshold is paired with a lower exit value. Without that gap a stick
// resting on a boundary re-crosses it every frame, which for the walk/run line
// means pressing and releasing B sixty times a second and a character visibly
// stuttering between gaits.
//
// The walk/run split is the whole console-feel mechanism, and a threshold is
// all the engine can express: CreatureSpeed2DA has exactly RUNRATE and
// WALKRATE, and CSWCCreature.isRunning is one boolean, so there is no
// continuous speed curve to drive even if we computed one.

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

bool g_resolveAttempted = false;

volatile LONG g_recentInjectedUntil[256] = {};
volatile LONG g_controllerInputActive = 0;
volatile LONG g_controllerConnected = 0;
// Whether either device has actually been used yet. Until one has, the question
// of which the player is on is open, and a connected pad answers it -- a pad
// plugged in is a statement of intent, a keyboard sitting there is not. Without
// this a player who launches with a pad, and skips the intro movies with it,
// still meets a main menu with no badges on it.
volatile LONG g_inputDeviceChosen = 0;
// Diagnostics for the opening state, which is not behaving as reasoned.
volatile LONG g_keyboardMouseMarks = 0;
volatile LONG g_keyboardMouseLastTick = 0;
bool g_movieSkipHeld = false;

bool g_leftStickLive = false;
bool g_leftStickRunning = false;
bool g_rightStickLive = false;
bool g_scrollLive = false;
bool g_scrollPrimed = false;

// ---------------------------------------------------------------------------

} // namespace

bool IsControllerInputActiveK1()
{
    if (InterlockedCompareExchange(&g_controllerInputActive, 0, 0) != 0) {
        return true;
    }
    if (InterlockedCompareExchange(&g_inputDeviceChosen, 0, 0) != 0) {
        return false;           // asked and answered: it is not the pad
    }
    // Nothing has been used yet, so a pad being present decides it.
    return InterlockedCompareExchange(&g_controllerConnected, 0, 0) != 0;
}

bool IsControllerGeneratedKeyK1(std::uint32_t scancode)
{
    const std::uint8_t key = static_cast<std::uint8_t>(scancode);
    const DWORD until = static_cast<DWORD>(
        InterlockedCompareExchange(&g_recentInjectedUntil[key], 0, 0));
    return until != 0 && static_cast<int>(GetTickCount() - until) <= 0;
}

void MarkKeyboardMouseInputK1()
{
    InterlockedExchange(&g_controllerInputActive, 0);
    InterlockedExchange(&g_inputDeviceChosen, 1);
    InterlockedIncrement(&g_keyboardMouseMarks);
    InterlockedExchange(&g_keyboardMouseLastTick,
                        static_cast<LONG>(GetTickCount()));
}

// The native path reads XInput itself, so it reports device activity itself.
// PollXInputK1 -- the only other place that raises this flag -- runs solely from
// the legacy DispatchMenuInputK1 hook, so without this the flag was never set in
// native mode and the prompts stayed hidden forever.
void ControllerLogK1(const char* text);     // K1NativeJoystick.cpp, the debug log

extern "C" void __cdecl KmrpMarkControllerActiveK1()
{
    if (InterlockedExchange(&g_controllerInputActive, 1) == 0) {
        ControllerLogK1("the game goes to the pad");
    }
    InterlockedExchange(&g_inputDeviceChosen, 1);
}

// The native path reads XInput itself rather than through ReadPad, so it is the
// only thing that knows whether a pad is answering. Without this the connected
// flag stays 0 in native mode and the opening state above could never fire.
extern "C" void __cdecl KmrpNotePadPresentK1(int present)
{
    InterlockedExchange(&g_controllerConnected, present ? 1 : 0);
}

// The opening-state machinery, packed for the diagnostic line: bit 0 a pad is
// connected, bit 1 the question has been closed, bit 2 the pad is the live
// device. The high bits carry how many times keyboard-or-mouse closed it.
extern "C" unsigned long __cdecl KmrpDeviceStateK1()
{
    unsigned long state = 0;
    if (InterlockedCompareExchange(&g_controllerConnected, 0, 0) != 0) {
        state |= 1u;
    }
    if (InterlockedCompareExchange(&g_inputDeviceChosen, 0, 0) != 0) {
        state |= 2u;
    }
    if (InterlockedCompareExchange(&g_controllerInputActive, 0, 0) != 0) {
        state |= 4u;
    }
    const unsigned long marks = static_cast<unsigned long>(
        InterlockedCompareExchange(&g_keyboardMouseMarks, 0, 0));
    return state | (marks << 8);
}

