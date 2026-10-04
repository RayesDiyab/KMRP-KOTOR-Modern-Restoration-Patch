#include "K1ControllerBackend.h"
#include <SDL3/SDL.h>
#ifdef KMRP_NATIVE_RUNTIME
#include "K1RuntimeAssets.h"
#endif
#define SDL_MAIN_HANDLED
#include <SDL3/SDL_main.h>
#include <cstdlib>
#include <cstring>

namespace {
#define SDL_FUNCTIONS(X) \
    X(SDL_SetMainReady) X(SDL_SetHint) X(SDL_InitSubSystem) X(SDL_SetGamepadEventsEnabled) \
    X(SDL_SetJoystickEventsEnabled) X(SDL_UpdateGamepads) X(SDL_GetGamepads) \
    X(SDL_OpenGamepad) X(SDL_CloseGamepad) X(SDL_GamepadConnected) \
    X(SDL_GetGamepadAxis) X(SDL_GetGamepadButton) X(SDL_GetGamepadType) \
    X(SDL_GetGamepadVendor) X(SDL_RumbleGamepad) X(SDL_free)
#define DECLARE(name) decltype(&name) p##name = nullptr;
SDL_FUNCTIONS(DECLARE)
#undef DECLARE

struct Device {
    bool connected = false;
    SDL_JoystickID id = 0;
    SDL_Gamepad* pad = nullptr;
    XINPUT_STATE state{};
    XINPUT_GAMEPAD previous{};
};
Device devices[20]; // four XInput slots, up to sixteen SDL gamepads
int active = -1;
DWORD nextScan = 0;
bool scanned = false, sdlReady = false, attempted = false;
unsigned long generation = 0;
DWORD motorTick = 0;
DWORD motors = 0;
bool motorAccepted = true;

void InitSdl()
{
    if (attempted) return;
    attempted = true;
    // Resolve only our owned adjacent library, never a DLL from the cwd/PATH.
    HMODULE self = nullptr;
    wchar_t path[MAX_PATH];
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&InitSdl), &self)) return;
    DWORD length = GetModuleFileNameW(self, path, MAX_PATH);
    if (!length || length >= MAX_PATH) return;
    wchar_t* slash = wcsrchr(path, L'\\');
    if (!slash || slash - path + 16 >= MAX_PATH) return;
    wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-sdl3.dll");
    HMODULE lib = LoadLibraryExW(path, nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    // Under KOTOR Patch Manager's runtime -- KPM's own or the one KMRP's installer
    // installs -- this module sits in the patches folder, and KMRP's installer puts
    // SDL beside the game. Still an owned, absolute path -- never the cwd or PATH.
    if (!lib) {
        length = GetModuleFileNameW(nullptr, path, MAX_PATH);
        slash = (length && length < MAX_PATH) ? wcsrchr(path, L'\\') : nullptr;
        if (slash && slash - path + 16 < MAX_PATH) {
            wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-sdl3.dll");
            lib = LoadLibraryExW(path, nullptr,
                LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        }
    }
#ifdef KMRP_NATIVE_RUNTIME
    // The standalone module has no installer to put SDL beside the game: it carries
    // the library and unpacks it with its other files. Still an owned, absolute path.
    if (!lib) {
        const std::wstring cached = KmrpRuntimeAssetDirectory() + L"\\kmrp-sdl3.dll";
        if (cached.size() < MAX_PATH) {
            lib = LoadLibraryExW(cached.c_str(), nullptr,
                LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        }
    }
#endif
    if (!lib) return; // Xbox remains available if SDL is absent or rejected.
#define RESOLVE(name) p##name = reinterpret_cast<decltype(&name)>(GetProcAddress(lib, #name)); if (!p##name) { FreeLibrary(lib); return; }
    SDL_FUNCTIONS(RESOLVE)
#undef RESOLVE
    pSDL_SetHint(SDL_HINT_TIMER_RESOLUTION, "0");
    pSDL_SetHint(SDL_HINT_XINPUT_ENABLED, "0");
    pSDL_SetHint(SDL_HINT_JOYSTICK_RAWINPUT, "0");
    pSDL_SetHint(SDL_HINT_JOYSTICK_DIRECTINPUT, "0");
    pSDL_SetHint(SDL_HINT_JOYSTICK_WGI, "0");
    pSDL_SetHint(SDL_HINT_JOYSTICK_GAMEINPUT, "0");
    // SDL owns no window here. KMRP filters focus against the game's process.
    pSDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_XBOX, "0");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_STEAM, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_STEAMDECK, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_ENHANCED_REPORTS, "auto");
    pSDL_SetMainReady();
    sdlReady = pSDL_InitSubSystem(SDL_INIT_GAMEPAD);
    if (sdlReady) {
        // No SDL window or message pump; the engine owns both. State polling
        // needs neither an event queue nor a timer-resolution request.
        pSDL_SetGamepadEventsEnabled(false);
        pSDL_SetJoystickEventsEnabled(false);
    }
}

SHORT UpPositive(Sint16 value)
{
    return value == -32768 ? 32767 : static_cast<SHORT>(-value);
}

void ReadSdl(Device& d)
{
    XINPUT_GAMEPAD& g = d.state.Gamepad;
    g = {};
    // SDL buttons are positions, not printed letters. Do not swap Nintendo
    // a second time here; glyph selection already maps these positions.
    const SDL_GamepadButton buttons[] = {
        SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN,
        SDL_GAMEPAD_BUTTON_DPAD_LEFT, SDL_GAMEPAD_BUTTON_DPAD_RIGHT,
        SDL_GAMEPAD_BUTTON_START, SDL_GAMEPAD_BUTTON_BACK,
        SDL_GAMEPAD_BUTTON_LEFT_STICK, SDL_GAMEPAD_BUTTON_RIGHT_STICK,
        SDL_GAMEPAD_BUTTON_LEFT_SHOULDER, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER,
        SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST,
        SDL_GAMEPAD_BUTTON_WEST, SDL_GAMEPAD_BUTTON_NORTH
    };
    const WORD masks[] = {1,2,4,8,16,32,64,128,256,512,4096,8192,16384,32768};
    for (int i = 0; i < 14; ++i)
        if (pSDL_GetGamepadButton(d.pad, buttons[i])) g.wButtons |= masks[i];
    g.sThumbLX = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFTX);
    g.sThumbLY = UpPositive(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFTY));
    g.sThumbRX = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHTX);
    g.sThumbRY = UpPositive(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHTY));
    const int lt = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER);
    const int rt = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
    g.bLeftTrigger = static_cast<BYTE>(lt > 0 ? lt * 255 / 32767 : 0);
    g.bRightTrigger = static_cast<BYTE>(rt > 0 ? rt * 255 / 32767 : 0);
}

bool Activity(const XINPUT_GAMEPAD& g, const XINPUT_GAMEPAD& prev)
{
    if (g.wButtons & ~prev.wButtons) return true;
    if ((g.bLeftTrigger > 30 && prev.bLeftTrigger <= 30) ||
        (g.bRightTrigger > 30 && prev.bRightTrigger <= 30)) return true;
    const SHORT axes[] = {g.sThumbLX,g.sThumbLY,g.sThumbRX,g.sThumbRY};
    const SHORT old[] = {prev.sThumbLX,prev.sThumbLY,prev.sThumbRX,prev.sThumbRY};
    for (int i=0; i<4; ++i)
        if (std::abs(static_cast<int>(axes[i])) > 8000 &&
            (std::abs(static_cast<int>(old[i])) <= 8000 ||
             std::abs(static_cast<int>(axes[i])-old[i]) > 4000)) return true;
    return false;
}

bool Rumble(int index, WORD low, WORD high)
{
    if (index < 0 || !devices[index].connected) return false;
    if (index < 4) {
        XINPUT_VIBRATION v = {low, high};
        return XInputSetState(index, &v) == ERROR_SUCCESS;
    }
    // Finite lease: SDL stops the motors if game polling stalls or exits.
    return pSDL_RumbleGamepad(devices[index].pad, low, high, 1500);
}
}

bool ReadControllerK1(XINPUT_STATE& state)
{
    InitSdl();
    DWORD foregroundPid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &foregroundPid);
    const bool focused = foregroundPid == GetCurrentProcessId();
    const DWORD now = GetTickCount();
    const bool scan = !scanned || static_cast<LONG>(now - nextScan) >= 0;
    if (sdlReady) pSDL_UpdateGamepads();
    if (scan) {
        scanned = true;
        nextScan = now + 1000;
        if (sdlReady) {
            int count = 0;
            SDL_JoystickID* ids = pSDL_GetGamepads(&count);
            for (int j=0; ids && j<count; ++j) {
                int empty = -1;
                bool found = false;
                for (int i=4; i<20; ++i) {
                    if (devices[i].pad && devices[i].id == ids[j]) found = true;
                    if (!devices[i].pad && empty < 0) empty = i;
                }
                if (!found && empty >= 0) {
                    devices[empty].pad = pSDL_OpenGamepad(ids[j]);
                    devices[empty].id = ids[j];
                }
            }
            pSDL_free(ids);
        }
    }
    int chosen = active;
    for (int i=0; i<20; ++i) {
        Device& d = devices[i];
        if (i < 4) {
            if (d.connected || scan)
                d.connected = XInputGetState(i, &d.state) == ERROR_SUCCESS;
        } else if (d.pad) {
            d.connected = pSDL_GamepadConnected(d.pad);
            if (d.connected) ReadSdl(d);
            else {
                pSDL_CloseGamepad(d.pad);
                d.pad = nullptr;
                d.previous = {};
            }
        }
        if (focused && d.connected && Activity(d.state.Gamepad, d.previous)) chosen = i;
        d.previous = d.connected ? d.state.Gamepad : XINPUT_GAMEPAD{};
    }
    if (chosen < 0 || !devices[chosen].connected) {
        chosen = -1;
        for (int i=0; i<20; ++i) if (devices[i].connected) { chosen=i; break; }
    }
    if (chosen != active) {
        Rumble(active, 0, 0);
        active = chosen;
        motors = 0;
        motorAccepted = true;
        ++generation;
        // Release old-device edges before exposing a new device's held input.
        state = {};
        return active >= 0;
    }
    if (!focused && motors) {
        Rumble(active, 0, 0);
        motors = 0;
    }
    state = focused && active >= 0 ? devices[active].state : XINPUT_STATE{};
    return active >= 0;
}

int ControllerXInputSlotK1() { return active >= 0 && active < 4 ? active : -1; }
unsigned long ControllerGenerationK1() { return generation; }
int ControllerSdlFamilyK1()
{
    if (active < 4) return -1;
    SDL_Gamepad* pad = devices[active].pad;
    if (pSDL_GetGamepadVendor(pad) == 0x28de) return 3;
    switch (pSDL_GetGamepadType(pad)) {
    case SDL_GAMEPAD_TYPE_PS3: case SDL_GAMEPAD_TYPE_PS4: case SDL_GAMEPAD_TYPE_PS5: return 1;
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO:
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT:
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT:
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR: return 2;
    default: return 0;
    }
}
bool SetControllerRumbleK1(WORD low, WORD high)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    if (pid != GetCurrentProcessId()) low = high = 0;
    const DWORD value = (static_cast<DWORD>(low) << 16) | high;
    const DWORD now = GetTickCount();
    if (value == motors && !((!motorAccepted || (active >= 4 && value)) &&
                            now - motorTick >= 1000)) return false;
    motorAccepted = Rumble(active, low, high);
    motors = value;
    motorTick = now;
    return motorAccepted;
}
