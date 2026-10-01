// KMRP for macOS, controller support: the SDL3 backend.
//
// The Mac port of src/controller-native/K1ControllerBackend.cpp's SDL path, and read against
// it: the same official SDL release (3.4.16), loaded the same way (by full path, from beside
// this module or else beside the game, as kmrp-sdl3.dylib; Windows loads kmrp-sdl3.dll), the
// same hints, the same
// button and axis normalisation, and the same choice of pad (the one last used, rescanned
// once a second). What differs is only what Windows has and the Mac does not: there is no
// XInput, so Xbox pads go through SDL too (its HIDAPI driver), where Windows keeps them on
// XInput.
//
// SDL is initialised and polled on the game's input thread (the thread GetEvents runs on),
// as on Windows. It creates no window and no event queue. If kmrp-sdl3.dylib is missing or
// incomplete, SdlAvailable() is false and pad.mm falls back to Apple's GameController.
#include "backend_sdl.h"
#include "pad.h"

#include <SDL3/SDL.h>

#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <string>
#include <time.h>

namespace kmrp {
namespace {

#define SDL_FUNCTIONS(X) \
    X(SDL_SetHint) X(SDL_InitSubSystem) X(SDL_SetGamepadEventsEnabled) \
    X(SDL_SetJoystickEventsEnabled) X(SDL_UpdateGamepads) X(SDL_GetGamepads) \
    X(SDL_OpenGamepad) X(SDL_CloseGamepad) X(SDL_GamepadConnected) \
    X(SDL_GetGamepadAxis) X(SDL_GetGamepadButton) X(SDL_GetGamepadType) \
    X(SDL_GetGamepadVendor) X(SDL_GetGamepadName) X(SDL_RumbleGamepad) X(SDL_free) \
    X(SDL_GetError) X(SDL_GetVersion)
#define DECLARE(name) decltype(&name) p##name = nullptr;
SDL_FUNCTIONS(DECLARE)
#undef DECLARE

struct Device {
    bool connected = false;
    SDL_JoystickID id = 0;
    SDL_Gamepad* pad = nullptr;
    PadState state;
    PadState previous;
};
Device devices[16];
int active = -1;
double nextScan = 0;
bool scanned = false, loaded = false, sdlReady = false, attempted = false;
unsigned long generation = 0;
std::uint32_t motors = 0;          // the motors last sent, low << 16 | high
bool motorAccepted = true;
double motorSent = 0;

double Now() {
    timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

// Resolves the library beside this module, else beside the game (KOTOR_Exe), never one from
// elsewhere. KMRP's installer puts it beside the game: KPM extracts only a patch's module, and
// its Apply empties patches/, so under KPM's runtime this module's folder has no SDL
// (K1ControllerBackend.cpp looks in the same two places on Windows).
void Load() {
    Dl_info self;
    if (!dladdr(reinterpret_cast<const void*>(&Load), &self) || !self.dli_fname) return;
    std::string path = self.dli_fname;
    path = path.substr(0, path.rfind('/') + 1) + "kmrp-sdl3.dylib";
    void* lib = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        char exe[4096];
        uint32_t size = sizeof(exe);
        if (_NSGetExecutablePath(exe, &size) == 0) {
            path = exe;
            path = path.substr(0, path.rfind('/') + 1) + "kmrp-sdl3.dylib";
            lib = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
        }
    }
    if (!lib) { Log("SDL3: %s not loaded (%s); using GameController", path.c_str(), dlerror()); return; }
#define RESOLVE(name) p##name = reinterpret_cast<decltype(&name)>(dlsym(lib, #name)); \
    if (!p##name) { Log("SDL3: %s missing; using GameController", #name); dlclose(lib); return; }
    SDL_FUNCTIONS(RESOLVE)
#undef RESOLVE
    loaded = true;
    const int v = pSDL_GetVersion();
    Log("SDL3 %d.%d.%d loaded from %s", SDL_VERSIONNUM_MAJOR(v), SDL_VERSIONNUM_MINOR(v), SDL_VERSIONNUM_MICRO(v),
        path.c_str());
}

void InitSdl() {
    if (attempted) return;
    attempted = true;
    if (!loaded) return;
    // SDL owns no window here; the game's own focus decides whether input counts.
    pSDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_STEAM, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_STEAMDECK, "1");
    pSDL_SetHint(SDL_HINT_JOYSTICK_ENHANCED_REPORTS, "auto");
    sdlReady = pSDL_InitSubSystem(SDL_INIT_GAMEPAD);
    if (!sdlReady) { Log("SDL3: SDL_InitSubSystem failed: %s", pSDL_GetError()); return; }
    // No message pump: state polling needs neither an event queue nor SDL's events.
    pSDL_SetGamepadEventsEnabled(false);
    pSDL_SetJoystickEventsEnabled(false);
    Log("SDL3: gamepad subsystem started");
}

float Axis(Sint16 value) { return value / 32767.0f; }
float UpPositive(Sint16 value) { return value == -32768 ? 1.0f : -value / 32767.0f; }

void ReadSdl(Device& d) {
    PadState& s = d.state;
    s = PadState();
    s.present = true;
    // SDL buttons are positions, not printed letters: SOUTH is A on an Xbox pad, cross on a
    // PlayStation pad and B on a Nintendo one, as on Windows.
    static const SDL_GamepadButton kButtons[] = {
        SDL_GAMEPAD_BUTTON_DPAD_UP, SDL_GAMEPAD_BUTTON_DPAD_DOWN, SDL_GAMEPAD_BUTTON_DPAD_LEFT,
        SDL_GAMEPAD_BUTTON_DPAD_RIGHT, SDL_GAMEPAD_BUTTON_START, SDL_GAMEPAD_BUTTON_BACK,
        SDL_GAMEPAD_BUTTON_LEFT_STICK, SDL_GAMEPAD_BUTTON_RIGHT_STICK, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER,
        SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, SDL_GAMEPAD_BUTTON_SOUTH, SDL_GAMEPAD_BUTTON_EAST,
        SDL_GAMEPAD_BUTTON_WEST, SDL_GAMEPAD_BUTTON_NORTH};
    static const std::uint32_t kMasks[] = {kPadUp, kPadDown, kPadLeft, kPadRight, kPadStart, kPadBack, kPadL3,
                                           kPadR3, kPadLB, kPadRB, kPadA, kPadB, kPadX, kPadY};
    for (int i = 0; i < 14; ++i)
        if (pSDL_GetGamepadButton(d.pad, kButtons[i])) s.buttons |= kMasks[i];
    s.lx = Axis(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFTX));
    s.ly = UpPositive(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFTY));
    s.rx = Axis(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHTX));
    s.ry = UpPositive(pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHTY));
    const int lt = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER);
    const int rt = pSDL_GetGamepadAxis(d.pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
    s.lt = lt > 0 ? lt / 32767.0f : 0;
    s.rt = rt > 0 ? rt / 32767.0f : 0;
}

// K1ControllerBackend.cpp's Rumble: a finite lease, so SDL stops the motors if the game stalls
// or exits.
bool Rumble(int index, Uint16 low, Uint16 high) {
    if (index < 0 || !devices[index].connected || !devices[index].pad) return false;
    return pSDL_RumbleGamepad(devices[index].pad, low, high, 1500);
}

// K1ControllerBackend.cpp's Activity, in normalised units: a new press, a trigger past
// 30/255, or a stick past 8000/32767.
bool Activity(const PadState& g, const PadState& prev) {
    if (g.buttons & ~prev.buttons) return true;
    const float kTrigger = 30 / 255.0f, kStick = 8000 / 32767.0f, kMove = 4000 / 32767.0f;
    if ((g.lt > kTrigger && prev.lt <= kTrigger) || (g.rt > kTrigger && prev.rt <= kTrigger)) return true;
    const float now[] = {g.lx, g.ly, g.rx, g.ry}, old[] = {prev.lx, prev.ly, prev.rx, prev.ry};
    for (int i = 0; i < 4; ++i) {
        if (std::abs(now[i]) > kStick && (std::abs(old[i]) <= kStick || std::abs(now[i] - old[i]) > kMove)) return true;
    }
    return false;
}

}  // namespace

bool SdlAvailable() {
    static bool once = (Load(), true);
    (void)once;
    return loaded;
}

bool ReadSdlPad(PadState* out, std::string* name) {
    InitSdl();
    *out = PadState();
    if (!sdlReady) return false;
    const double now = Now();
    const bool scan = !scanned || now >= nextScan;
    pSDL_UpdateGamepads();
    if (scan) {
        scanned = true;
        nextScan = now + 1.0;
        int count = 0;
        SDL_JoystickID* ids = pSDL_GetGamepads(&count);
        for (int j = 0; ids && j < count; ++j) {
            int empty = -1;
            bool found = false;
            for (int i = 0; i < 16; ++i) {
                if (devices[i].pad && devices[i].id == ids[j]) found = true;
                if (!devices[i].pad && empty < 0) empty = i;
            }
            if (!found && empty >= 0) {
                devices[empty].pad = pSDL_OpenGamepad(ids[j]);
                devices[empty].id = ids[j];
                if (devices[empty].pad) {
                    const char* n = pSDL_GetGamepadName(devices[empty].pad);
                    Log("SDL3: opened %s (type %d, vendor 0x%04x)", n ? n : "?",
                        static_cast<int>(pSDL_GetGamepadType(devices[empty].pad)),
                        pSDL_GetGamepadVendor(devices[empty].pad));
                }
            }
        }
        pSDL_free(ids);
    }
    int chosen = active;
    for (int i = 0; i < 16; ++i) {
        Device& d = devices[i];
        if (d.pad) {
            d.connected = pSDL_GamepadConnected(d.pad);
            if (d.connected) ReadSdl(d);
            else {
                Log("SDL3: a pad disconnected");
                pSDL_CloseGamepad(d.pad);
                d.pad = nullptr;
                d.previous = PadState();
            }
        }
        if (d.connected && Activity(d.state, d.previous)) chosen = i;
        d.previous = d.connected ? d.state : PadState();
    }
    if (chosen < 0 || !devices[chosen].connected) {
        chosen = -1;
        for (int i = 0; i < 16; ++i) if (devices[i].connected) { chosen = i; break; }
    }
    if (chosen != active) {
        Rumble(active, 0, 0);
        active = chosen;
        motors = 0;
        motorAccepted = true;
        ++generation;
        // Release the old pad's held input before exposing the new one's.
        return active >= 0;
    }
    if (active < 0) return false;
    *out = devices[active].state;
    if (name) {
        const char* n = pSDL_GetGamepadName(devices[active].pad);
        *name = n ? n : "gamepad";
    }
    return true;
}

// 0 Xbox or generic, 1 PlayStation, 2 Nintendo, 3 Steam: K1ControllerBackend.cpp's families,
// for the prompts. -1 without a pad.
int SdlPadFamily() {
    if (active < 0 || !devices[active].pad) return -1;
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

unsigned long SdlGeneration() { return generation; }

// SetControllerRumbleK1: silent while the game is not the active app, sent only on a change, and
// renewed each second while the motors run (the lease is 1.5 s) or the last send failed.
bool SdlRumble(float heavy, float light, bool appActive) {
    if (!sdlReady || active < 0) return false;
    auto motor = [](float v) -> Uint16 { return v > 0 ? static_cast<Uint16>((v > 1 ? 1 : v) * 65535.0f) : 0; };
    Uint16 low = motor(heavy), high = motor(light);
    if (!appActive) low = high = 0;
    const std::uint32_t value = (static_cast<std::uint32_t>(low) << 16) | high;
    const double now = Now();
    if (value == motors && !((!motorAccepted || value) && now - motorSent >= 1.0)) return false;
    motorAccepted = Rumble(active, low, high);
    motors = value;
    motorSent = now;
    return motorAccepted;
}

}  // namespace kmrp
