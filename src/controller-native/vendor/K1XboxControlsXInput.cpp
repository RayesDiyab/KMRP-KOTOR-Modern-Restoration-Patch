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

constexpr std::uint32_t XI_SUCCESS = 0;

constexpr std::uint16_t XI_DPAD_UP = 0x0001;
constexpr std::uint16_t XI_DPAD_DOWN = 0x0002;
constexpr std::uint16_t XI_DPAD_LEFT = 0x0004;
constexpr std::uint16_t XI_DPAD_RIGHT = 0x0008;
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
constexpr std::uint8_t XI_TRIGGER_THRESHOLD = 30;

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
constexpr std::uint8_t SC_W = 0x11;
constexpr std::uint8_t SC_E = 0x12;
constexpr std::uint8_t SC_R = 0x13;
constexpr std::uint8_t SC_RETURN = 0x1C;
constexpr std::uint8_t SC_A = 0x1E;
constexpr std::uint8_t SC_S = 0x1F;
constexpr std::uint8_t SC_D = 0x20;
constexpr std::uint8_t SC_F = 0x21;
constexpr std::uint8_t SC_G = 0x22;
constexpr std::uint8_t SC_Z = 0x2C;
constexpr std::uint8_t SC_X = 0x2D;
constexpr std::uint8_t SC_C = 0x2E;
constexpr std::uint8_t SC_V = 0x2F;
constexpr std::uint8_t SC_B = 0x30;
constexpr std::uint8_t SC_SPACE = 0x39;
constexpr std::uint8_t SC_CAPSLOCK = 0x3A;
constexpr std::uint8_t SC_HOME = 0xC7;
constexpr std::uint8_t SC_UP = 0xC8;
constexpr std::uint8_t SC_PRIOR = 0xC9;
constexpr std::uint8_t SC_LEFT = 0xCB;
constexpr std::uint8_t SC_RIGHT = 0xCD;
constexpr std::uint8_t SC_END = 0xCF;
constexpr std::uint8_t SC_DOWN = 0xD0;
constexpr std::uint8_t SC_NEXT = 0xD1;
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

constexpr float LSTICK_ENTER = 0.24f;  // XINPUT left thumb deadzone 7849 / 32767
constexpr float LSTICK_EXIT = 0.20f;
constexpr float RUN_ENTER = 0.70f;
constexpr float RUN_EXIT = 0.60f;
constexpr float RSTICK_ENTER = 0.30f;
constexpr float RSTICK_EXIT = 0.24f;

// Vertical on the right stick scrolls a menu description pane. This is the one
// input here that repeats while held, and it has to: DirectInput reports key
// transitions only, so a held key would move exactly one line and a long pane
// would be unreadable. Rate scales with deflection, which is what makes a
// nudge read as a line and a full push as a page.
constexpr float RSTICK_SCROLL_ENTER = 0.30f;
constexpr float RSTICK_SCROLL_EXIT = 0.24f;
constexpr DWORD SCROLL_INTERVAL_SLOW_MS = 250;
constexpr DWORD SCROLL_INTERVAL_FAST_MS = 50;

// D-pad auto-repeat. The first press fires immediately, the second waits
// DPAD_REPEAT_DELAY_MS, and the rest follow every DPAD_REPEAT_INTERVAL_MS.
// These are the shape of a keyboard's own repeat rather than the scroll ramp
// above: a menu selection should step predictably, where a description pane
// should accelerate with how hard the stick is pushed.
//
// 400/120 is close to a Windows default (roughly 250-1000 ms delay, ~30/s at
// the fast end). Erring slow on the delay matters more than erring fast: too
// short and a single deliberate press double-steps, which is worse than a
// repeat that starts a beat late.
constexpr DWORD DPAD_REPEAT_DELAY_MS = 400;
constexpr DWORD DPAD_REPEAT_INTERVAL_MS = 120;

// sin(22.5 deg). A component past this share of the magnitude engages its
// direction, splitting the circle into eight even sectors: pure cardinals fire
// one key, diagonals fire two.
constexpr float SECTOR_COMPONENT = 0.3827f;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

XInputGetStateFn g_getState = nullptr;
bool g_resolveAttempted = false;

int g_padSlot = -1;
DWORD g_nextScanTick = 0;

// Indexed by scancode: what the game currently believes is down because we
// pressed it. The matching demand set is rebuilt from scratch every frame.
std::uint8_t g_held[256] = {};
volatile LONG g_recentInjectedUntil[256] = {};
volatile LONG g_controllerInputActive = 0;
volatile LONG g_controllerConnected = 0;
bool g_movieSkipHeld = false;

bool g_leftStickLive = false;
bool g_leftStickRunning = false;
bool g_rightStickLive = false;
bool g_scrollLive = false;
bool g_scrollPrimed = false;
DWORD g_nextScrollTick = 0;

// The single D-pad direction currently repeating, and when its next tap is due.
// One direction at a time on purpose: pressing a second while the first is held
// hands over to the new one and restarts the delay, which is what a menu wants.
// Holding two at once otherwise walks the selection diagonally at double rate.
std::uint16_t g_dpadDirection = 0;
DWORD g_nextDpadTick = 0;

// ---------------------------------------------------------------------------

XInputGetStateFn ResolveXInputGetState()
{
    if (g_resolveAttempted) {
        return g_getState;
    }
    g_resolveAttempted = true;

    // Newest first. 1_4 ships with Windows 8 and later; 9_1_0 is the
    // redistributable-free fallback present on essentially every install.
    static const char* const dllNames[] = {
        "xinput1_4.dll",
        "xinput1_3.dll",
        "xinput9_1_0.dll",
    };

    for (int i = 0; i < 3; ++i) {
        HMODULE module = LoadLibraryA(dllNames[i]);
        if (!module) {
            continue;
        }
        g_getState = reinterpret_cast<XInputGetStateFn>(
            GetProcAddress(module, "XInputGetState"));
        if (g_getState) {
            break;
        }
        FreeLibrary(module);
    }

    return g_getState;
}

// XInputGetState on an empty slot is slow enough to matter at 60fps, so a
// missing controller must not cost four probes a frame. Once a slot answers we
// stay on it, and a full rescan is rate-limited to every two seconds.
bool ReadPad(XInputState* out)
{
    if (g_padSlot >= 0) {
        if (g_getState(static_cast<std::uint32_t>(g_padSlot), out) == XI_SUCCESS) {
            InterlockedExchange(&g_controllerConnected, 1);
            return true;
        }
        g_padSlot = -1;
    }

    DWORD now = GetTickCount();
    // Signed difference, so this survives GetTickCount's 49-day wrap.
    if (static_cast<int>(now - g_nextScanTick) < 0) {
        return false;
    }

    for (std::uint32_t slot = 0; slot < 4; ++slot) {
        if (g_getState(slot, out) == XI_SUCCESS) {
            g_padSlot = static_cast<int>(slot);
            InterlockedExchange(&g_controllerConnected, 1);
            return true;
        }
    }

    g_nextScanTick = now + 2000;
    InterlockedExchange(&g_controllerConnected, 0);
    return false;
}

bool GameHasFocus()
{
    DWORD pid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    return pid == GetCurrentProcessId();
}

INPUT MakeKeyEvent(std::uint8_t scancode, bool release)
{
    INPUT event = {};
    event.type = INPUT_KEYBOARD;
    event.ki.wVk = 0;
    event.ki.wScan = scancode & 0x7F;
    event.ki.dwFlags = KEYEVENTF_SCANCODE;
    if ((scancode & 0x80) != 0) {
        event.ki.dwFlags |= KEYEVENTF_EXTENDEDKEY;
    }
    if (release) {
        event.ki.dwFlags |= KEYEVENTF_KEYUP;
    }
    return event;
}

// Diffing a freshly built demand set against what we hold is what makes
// shared bindings safe in general: a key stays down while any button still
// wants it, and releasing one of them does not send an up event another
// relies on. It also means we can only ever release keys we pressed, so a key
// the player is physically holding is never cancelled out from under them.
void Commit(const std::uint8_t* want)
{
    INPUT batch[32];
    int queued = 0;

    for (int scancode = 0; scancode < 256; ++scancode) {
        bool wanted = want[scancode] != 0;
        bool held = g_held[scancode] != 0;
        if (wanted == held) {
            continue;
        }

        if (queued == 32) {
            SendInput(queued, batch, sizeof(INPUT));
            queued = 0;
        }
        InterlockedExchange(
            &g_recentInjectedUntil[scancode],
            static_cast<LONG>(GetTickCount() + 250));
        batch[queued++] =
            MakeKeyEvent(static_cast<std::uint8_t>(scancode), !wanted);
        g_held[scancode] = wanted ? 1 : 0;
    }

    if (queued > 0) {
        SendInput(queued, batch, sizeof(INPUT));
    }
}

void ReleaseAll()
{
    static const std::uint8_t nothing[256] = {};
    g_leftStickLive = false;
    g_leftStickRunning = false;
    g_rightStickLive = false;
    g_scrollLive = false;
    g_scrollPrimed = false;
    // Otherwise a direction still held when the pad drops out or the game loses
    // focus stays "current", and the first press after coming back repeats at
    // interval speed instead of waiting the delay.
    g_dpadDirection = 0;
    Commit(nothing);
}

float Normalize(std::int16_t axis)
{
    // -32768 has no positive counterpart; clamping keeps the magnitude inside
    // the unit circle the thresholds assume.
    float value = static_cast<float>(axis) / 32767.0f;
    if (value < -1.0f) {
        return -1.0f;
    }
    return value;
}

void ApplyLeftStick(const XInputGamepad& pad, std::uint8_t* want)
{
    // In gameplay the native joystick path drives movement directly, with real
    // analog magnitude. Synthesising W/S/Z/C here as well would drive the same
    // axes digitally at the same time, and the B this function holds below its
    // run threshold is the engine's walk modifier, which halves whatever the
    // native path just wrote. That combination is what made analog movement
    // lurch between speeds regardless of how far the stick was pushed.
    //
    // Menus are unaffected: Control does not run there, so this returns false
    // and the keystrokes still drive list navigation as before.
    if (NativeMovementOwnsLeftStickK1()) {
        g_leftStickLive = false;
        g_leftStickRunning = false;
        return;
    }

    float x = Normalize(pad.thumbLX);
    float y = Normalize(pad.thumbLY);
    float magnitude = std::sqrt(x * x + y * y);

    g_leftStickLive = g_leftStickLive ? magnitude > LSTICK_EXIT
                                      : magnitude > LSTICK_ENTER;
    if (!g_leftStickLive) {
        g_leftStickRunning = false;
        return;
    }

    float gate = magnitude * SECTOR_COMPONENT;
    if (y > gate) {
        ++want[SC_W];
    }
    if (y < -gate) {
        ++want[SC_S];
    }
    if (x < -gate) {
        ++want[SC_Z];
    }
    if (x > gate) {
        ++want[SC_C];
    }

    g_leftStickRunning = g_leftStickRunning ? magnitude > RUN_EXIT
                                            : magnitude > RUN_ENTER;
    // B is the momentary walk modifier, so walking is the state where we hold
    // it and running is simply its absence.
    if (!g_leftStickRunning) {
        ++want[SC_B];
    }
}

void ApplyRightStick(const XInputGamepad& pad, std::uint8_t* want)
{
    float x = Normalize(pad.thumbRX);
    float magnitude = x < 0.0f ? -x : x;

    g_rightStickLive = g_rightStickLive ? magnitude > RSTICK_EXIT
                                        : magnitude > RSTICK_ENTER;
    if (!g_rightStickLive) {
        return;
    }

    // Horizontal only; vertical is handled by ApplyScroll below.
    ++want[x < 0.0f ? SC_A : SC_D];
}

// Emitted straight to SendInput rather than through the demand set, because
// this is a repeating tap and that set only ever produces one edge per state
// change. PageUp/PageDown are never members of it, so the two cannot collide.
//
// No menu check here. The main mod consumes these keys only when the active
// panel actually has a description pane, and during gameplay there is no panel
// to find, so they fall through to the engine where both are unbound.
void ApplyScroll(const XInputGamepad& pad)
{
    float y = Normalize(pad.thumbRY);
    float magnitude = y < 0.0f ? -y : y;

    g_scrollLive = g_scrollLive ? magnitude > RSTICK_SCROLL_EXIT
                                : magnitude > RSTICK_SCROLL_ENTER;
    if (!g_scrollLive) {
        g_scrollPrimed = false;
        return;
    }

    DWORD now = GetTickCount();
    if (g_scrollPrimed && static_cast<int>(now - g_nextScrollTick) < 0) {
        return;
    }

    // Pushing up walks down the list. The pane moves under a fixed viewport
    // rather than the viewport moving over the pane, so tying up to PageUp
    // reads as inverted in the game even though it looks right written down.
    std::uint8_t scancode = y > 0.0f ? SC_NEXT : SC_PRIOR;
    INPUT tap[2] = {
        MakeKeyEvent(scancode, false),
        MakeKeyEvent(scancode, true),
    };
    InterlockedExchange(
        &g_recentInjectedUntil[scancode],
        static_cast<LONG>(now + 250));
    SendInput(2, tap, sizeof(INPUT));

    float t = (magnitude - RSTICK_SCROLL_ENTER) / (1.0f - RSTICK_SCROLL_ENTER);
    if (t < 0.0f) {
        t = 0.0f;
    }
    if (t > 1.0f) {
        t = 1.0f;
    }
    g_scrollPrimed = true;
    g_nextScrollTick = now + static_cast<DWORD>(
        SCROLL_INTERVAL_SLOW_MS -
        t * (SCROLL_INTERVAL_SLOW_MS - SCROLL_INTERVAL_FAST_MS));
}

// Emitted as taps straight to SendInput, for the same reason ApplyScroll is: the
// demand set produces one edge per state change, so a held direction stepped the
// selection once and stopped. A keyboard auto-repeats, and the engine only ever
// sees keydowns, so tapping is the faithful emulation -- not a workaround.
//
// Diagonals are ignored rather than sent as two directions. KOTOR's menus are
// one-dimensional lists, so a diagonal has no meaning in them, and the rounding
// that would pick a winner belongs to the stick sectors above, not here.
void ApplyDpad(std::uint16_t buttons)
{
    std::uint16_t direction = 0;
    int pressed = 0;
    const std::uint16_t masks[] = {
        XI_DPAD_UP, XI_DPAD_DOWN, XI_DPAD_LEFT, XI_DPAD_RIGHT};
    for (int i = 0; i < 4; ++i) {
        if ((buttons & masks[i]) != 0) {
            direction = masks[i];
            ++pressed;
        }
    }
    if (pressed != 1) {
        g_dpadDirection = 0;
        return;
    }

    DWORD now = GetTickCount();
    if (direction == g_dpadDirection) {
        if (static_cast<int>(now - g_nextDpadTick) < 0) {
            return;
        }
        g_nextDpadTick = now + DPAD_REPEAT_INTERVAL_MS;
    } else {
        // A fresh press, or a change of direction: act at once, then wait the
        // longer delay before the run of repeats starts.
        g_dpadDirection = direction;
        g_nextDpadTick = now + DPAD_REPEAT_DELAY_MS;
    }

    std::uint8_t scancode = SC_UP;
    if (direction == XI_DPAD_DOWN) {
        scancode = SC_DOWN;
    } else if (direction == XI_DPAD_LEFT) {
        scancode = SC_LEFT;
    } else if (direction == XI_DPAD_RIGHT) {
        scancode = SC_RIGHT;
    }

    INPUT tap[2] = {
        MakeKeyEvent(scancode, false),
        MakeKeyEvent(scancode, true),
    };
    InterlockedExchange(
        &g_recentInjectedUntil[scancode],
        static_cast<LONG>(now + 250));
    SendInput(2, tap, sizeof(INPUT));
}

} // namespace

void PollXInputK1()
{
    if (!ResolveXInputGetState()) {
        return;
    }

    XInputState state;
    if (!ReadPad(&state)) {
        ReleaseAll();
        InterlockedExchange(&g_controllerInputActive, 0);
        return;
    }

    // Without this an alt-tab with the stick deflected keeps typing into
    // whatever window took focus, and leaves those keys stuck when it does.
    if (!GameHasFocus()) {
        ReleaseAll();
        return;
    }

    std::uint16_t buttons = state.gamepad.buttons;
    if (state.gamepad.leftTrigger > XI_TRIGGER_THRESHOLD) {
        buttons |= XI_LEFT_TRIGGER;
    }
    if (state.gamepad.rightTrigger > XI_TRIGGER_THRESHOLD) {
        buttons |= XI_RIGHT_TRIGGER;
    }

    const bool meaningfulInput =
        buttons != 0 ||
        std::abs(Normalize(state.gamepad.thumbLX)) > LSTICK_ENTER ||
        std::abs(Normalize(state.gamepad.thumbLY)) > LSTICK_ENTER ||
        std::abs(Normalize(state.gamepad.thumbRX)) > RSTICK_ENTER ||
        std::abs(Normalize(state.gamepad.thumbRY)) > RSTICK_SCROLL_ENTER;
    if (meaningfulInput) {
        InterlockedExchange(&g_controllerInputActive, 1);
    }

    std::uint8_t want[256] = {};
    for (int i = 0; i < BUTTON_BINDING_COUNT; ++i) {
        const ButtonBinding& binding = BUTTON_BINDINGS[i];
        if ((buttons & binding.mask) == 0) {
            continue;
        }

        ++want[binding.primary];
        if (binding.secondary != 0) {
            ++want[binding.secondary];
        }
    }

    ApplyLeftStick(state.gamepad, want);
    ApplyRightStick(state.gamepad, want);

    Commit(want);

    // After Commit so these taps land behind this frame's held-key edges rather
    // than in between them.
    ApplyScroll(state.gamepad);
    ApplyDpad(buttons);
}

bool IsControllerInputActiveK1()
{
    return InterlockedCompareExchange(&g_controllerInputActive, 0, 0) != 0;
}

bool IsControllerConnectedK1()
{
    return InterlockedCompareExchange(&g_controllerConnected, 0, 0) != 0;
}

bool ConsumeMovieSkipK1()
{
    if (!ResolveXInputGetState() || !GameHasFocus()) {
        g_movieSkipHeld = false;
        return false;
    }

    XInputState state = {};
    if (!ReadPad(&state)) {
        g_movieSkipHeld = false;
        return false;
    }

    const std::uint16_t skipMask =
        XI_A | XI_B | XI_LEFT_SHOULDER | XI_START;
    const bool held = (state.gamepad.buttons & skipMask) != 0;
    const bool pressed = held && !g_movieSkipHeld;
    g_movieSkipHeld = held;
    if (held) {
        InterlockedExchange(&g_controllerInputActive, 1);
    }
    return pressed;
}

// The raw deadline stored when this module last injected `scancode`, or 0. Two
// scancodes can be compared by it to ask which the player pressed more recently,
// which a boolean "was it injected in the last 250 ms" cannot answer -- and that
// is exactly what switching tabs quickly needs.
DWORD LastInjectedDeadlineK1(std::uint32_t scancode)
{
    const std::uint8_t key = static_cast<std::uint8_t>(scancode);
    return static_cast<DWORD>(
        InterlockedCompareExchange(&g_recentInjectedUntil[key], 0, 0));
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
}
