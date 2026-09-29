// KMRP for macOS, controller support: reading the pad.
//
// Not the game's own pad layer: Aspyr's port carries SDL 2.0.7 (2017) behind a DirectInput
// joystick emulation, and its controller list stops at the PS4 pad, so a DualSense does
// nothing in it (seen 2026-09-29). The pad is read through SDL 3.4.16 instead, the release
// the Windows build ships (backend_sdl.cpp), and, only when kmrp-sdl3.dylib is missing,
// through Apple's GameController framework, which is weak-linked: on a system without it
// the module still loads and reports no pad.
//
// KMRP_PAD_SCRIPT=<file> replaces the pad with a script, for tests driven by the devkit.
// One line per change, "SECONDS CONTROL VALUE", seconds since the game started:
//   12.0 A 1        press A          12.2 A 0       release it
//   20.0 LY 1       left stick up    21.0 LY 0
// Controls: A B X Y LB RB BACK START L3 R3 UP DOWN LEFT RIGHT (0 or 1), LX LY RX RY (-1..1),
// LT RT (0..1). '#' starts a comment.
#import <AppKit/AppKit.h>
#import <GameController/GameController.h>

#include "pad.h"
#include "backend_sdl.h"

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>

namespace kmrp {

// Also appended to ~/Library/Logs/KMRP/controller.log: a game started from Steam sends its
// stderr nowhere, and that log is how a player's own session can be read afterwards.
FILE* LogFile() {
    static FILE* file = [] {
        const char* home = std::getenv("HOME");
        if (!home) return static_cast<FILE*>(nullptr);
        std::string dir = std::string(home) + "/Library/Logs/KMRP";
        [[NSFileManager defaultManager] createDirectoryAtPath:@(dir.c_str()) withIntermediateDirectories:YES
                                                   attributes:nil error:nil];
        return std::fopen((dir + "/controller.log").c_str(), "w");
    }();
    return file;
}

void Log(const char* format, ...) {
    char line[1024];
    va_list args;
    va_start(args, format);
    std::vsnprintf(line, sizeof line, format, args);
    va_end(args);
    std::fprintf(stderr, "[KMRP controller] %s\n", line);
    std::fflush(stderr);
    if (FILE* f = LogFile()) {
        timespec t;
        clock_gettime(CLOCK_MONOTONIC, &t);
        static const double start = t.tv_sec + t.tv_nsec / 1e9;
        std::fprintf(f, "[%8.2f] %s\n", t.tv_sec + t.tv_nsec / 1e9 - start, line);
        std::fflush(f);
    }
}

namespace {

double Now() {
    timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

const double g_start = Now();   // module load, a moment after the game starts
std::string g_name;

// ------------------------------------------------------------------ the scripted pad

struct ScriptStep {
    double at;
    std::string control;
    float value;
};

std::vector<ScriptStep> g_script;
bool g_scriptLoaded = false;
bool g_scripted = false;
PadState g_scriptState;
size_t g_scriptNext = 0;

void LoadScript() {
    g_scriptLoaded = true;
    const char* path = std::getenv("KMRP_PAD_SCRIPT");
    if (!path || !*path) return;
    FILE* f = std::fopen(path, "r");
    if (!f) { Log("KMRP_PAD_SCRIPT %s: cannot open", path); return; }
    char line[256];
    while (std::fgets(line, sizeof line, f)) {
        if (char* hash = std::strchr(line, '#')) *hash = 0;
        double at; char control[32]; float value;
        if (std::sscanf(line, "%lf %31s %f", &at, control, &value) == 3)
            g_script.push_back({at, control, value});
    }
    std::fclose(f);
    g_scripted = true;
    g_scriptState.present = true;
    g_name = "scripted pad";
    Log("scripted pad: %zu steps from %s", g_script.size(), path);
}

void ApplyStep(const ScriptStep& step) {
    static const struct { const char* name; std::uint32_t bit; } kButtons[] = {
        {"A", kPadA}, {"B", kPadB}, {"X", kPadX}, {"Y", kPadY}, {"LB", kPadLB}, {"RB", kPadRB},
        {"BACK", kPadBack}, {"START", kPadStart}, {"L3", kPadL3}, {"R3", kPadR3},
        {"UP", kPadUp}, {"DOWN", kPadDown}, {"LEFT", kPadLeft}, {"RIGHT", kPadRight},
    };
    PadState& s = g_scriptState;
    for (const auto& b : kButtons) {
        if (step.control == b.name) {
            s.buttons = step.value != 0 ? (s.buttons | b.bit) : (s.buttons & ~b.bit);
            return;
        }
    }
    if (step.control == "LX") s.lx = step.value;
    else if (step.control == "LY") s.ly = step.value;
    else if (step.control == "RX") s.rx = step.value;
    else if (step.control == "RY") s.ry = step.value;
    else if (step.control == "LT") s.lt = step.value;
    else if (step.control == "RT") s.rt = step.value;
    else Log("script: unknown control %s", step.control.c_str());
}

bool ReadScripted(PadState* out) {
    const double t = Now() - g_start;
    while (g_scriptNext < g_script.size() && g_script[g_scriptNext].at <= t) {
        ApplyStep(g_script[g_scriptNext]);
        Log("script %.2fs: %s %g", t, g_script[g_scriptNext].control.c_str(), g_script[g_scriptNext].value);
        ++g_scriptNext;
    }
    *out = g_scriptState;
    return true;
}

// ------------------------------------------------------------------ GameController

// GameController announces pads on the main thread's run loop, and only once something has
// asked for them there: in an x86_64 probe (2026-09-29), a pad read from a background thread
// stayed absent until the main run loop had run after a main-thread request. The game polls
// input on its own thread ("WinMain"), so the framework is started here, on the main thread,
// when the module loads, before the game's window exists.
std::atomic<bool> g_mainQueueAlive{false};
std::atomic<int> g_connects{0};

__attribute__((constructor)) void StartGameController() {
    // SDL3 reads the pads when it is there (backend_sdl.cpp), as on Windows; GameController
    // only when it is not, so the two never both hold a pad.
    if (SdlAvailable()) return;
    if (![GCController class]) { Log("GameController is not available; no pad"); return; }
    Log("GameController started on the %s thread: %lu pads now", [NSThread isMainThread] ? "main" : "OTHER",
        (unsigned long)[GCController controllers].count);
    [[NSNotificationCenter defaultCenter] addObserverForName:GCControllerDidConnectNotification object:nil queue:nil
                                                  usingBlock:^(NSNotification* note) {
        GCController* c = note.object;
        g_connects++;
        const char* name = nullptr;
        if (@available(macOS 10.15, *)) name = c.vendorName.UTF8String;
        Log("GameController: connected %s (extended gamepad: %s)", name ? name : "?", c.extendedGamepad ? "yes" : "no");
    }];
    [[NSNotificationCenter defaultCenter] addObserverForName:GCControllerDidDisconnectNotification object:nil queue:nil
                                                  usingBlock:^(NSNotification*) { Log("GameController: a pad disconnected"); }];
    dispatch_async(dispatch_get_main_queue(), ^{ g_mainQueueAlive = true; });
}

GCExtendedGamepad* FirstGamepad() API_AVAILABLE(macos(10.9)) {
    for (GCController* controller in [GCController controllers]) {
        if (controller.extendedGamepad) {
            if (@available(macOS 10.15, *)) {
                const char* name = controller.vendorName.UTF8String;
                g_name = name ? name : "gamepad";
            } else {
                g_name = "gamepad";
            }
            return controller.extendedGamepad;
        }
    }
    g_name.clear();
    return nil;
}

}  // namespace

bool ReadPad(PadState* out) {
    if (!g_scriptLoaded) LoadScript();
    if (g_scripted) return ReadScripted(out);
    if (SdlAvailable()) {
        const bool present = ReadSdlPad(out, &g_name);
        if (!present) g_name.clear();
        return present;
    }

    *out = PadState();
    if (![GCController class]) return false;   // weak-linked and absent
    @autoreleasepool {
        GCExtendedGamepad* pad = FirstGamepad();
        if (!pad) return false;
        std::uint32_t b = 0;
        if (pad.buttonA.pressed) b |= kPadA;
        if (pad.buttonB.pressed) b |= kPadB;
        if (pad.buttonX.pressed) b |= kPadX;
        if (pad.buttonY.pressed) b |= kPadY;
        if (pad.leftShoulder.pressed) b |= kPadLB;
        if (pad.rightShoulder.pressed) b |= kPadRB;
        if (pad.dpad.up.pressed) b |= kPadUp;
        if (pad.dpad.down.pressed) b |= kPadDown;
        if (pad.dpad.left.pressed) b |= kPadLeft;
        if (pad.dpad.right.pressed) b |= kPadRight;
        if (@available(macOS 10.14.1, *)) {
            if (pad.leftThumbstickButton.pressed) b |= kPadL3;
            if (pad.rightThumbstickButton.pressed) b |= kPadR3;
        }
        if (@available(macOS 10.15, *)) {
            if (pad.buttonMenu.pressed) b |= kPadStart;
            if (pad.buttonOptions.pressed) b |= kPadBack;
        }
        out->present = true;
        out->buttons = b;
        out->lx = pad.leftThumbstick.xAxis.value;
        out->ly = pad.leftThumbstick.yAxis.value;
        out->rx = pad.rightThumbstick.xAxis.value;
        out->ry = pad.rightThumbstick.yAxis.value;
        out->lt = pad.leftTrigger.value;
        out->rt = pad.rightTrigger.value;
    }
    return true;
}

const char* PadName() {
    return g_name.c_str();
}

namespace {

std::atomic<bool> g_appActive{true};

// AppKit's own notifications, delivered on the main thread; the game's thread reads the flag.
__attribute__((constructor)) void WatchAppActivation() {
    NSNotificationCenter* center = [NSNotificationCenter defaultCenter];
    [center addObserverForName:NSApplicationDidBecomeActiveNotification object:nil queue:nil
                    usingBlock:^(NSNotification*) { g_appActive = true; }];
    [center addObserverForName:NSApplicationDidResignActiveNotification object:nil queue:nil
                    usingBlock:^(NSNotification*) { g_appActive = false; }];
}

// GameController's product category, for the fallback backend (macOS 10.15 and later).
int GameControllerFamily() {
    if (![GCController class]) return -1;
    if (@available(macOS 10.15, *)) {
        for (GCController* controller in [GCController controllers]) {
            if (!controller.extendedGamepad) continue;
            NSString* category = controller.productCategory;
            if ([category containsString:@"DualSense"] || [category containsString:@"DualShock"]) return 1;
            if ([category containsString:@"Switch"] || [category containsString:@"Joy-Con"]) return 2;
            return 0;
        }
        return -1;
    }
    return 0;
}

}  // namespace

int PadFamily() {
    if (g_scripted) {
        const char* letter = std::getenv("KMRP_PAD_FAMILY");
        switch (letter ? *letter : 'p') {
            case 's': return 1;
            case 'n': return 2;
            case 'd': return 3;
            default: return 0;
        }
    }
    if (SdlAvailable()) return SdlPadFamily();
    @autoreleasepool {
        return GameControllerFamily();
    }
}

bool AppActive() {
    return g_appActive;
}

bool SetRumble(float heavy, float light) {
    if (g_scripted || !SdlAvailable()) return false;
    return SdlRumble(heavy, light, g_appActive);
}

void Status() {
    if (SdlAvailable()) {
        Log("status: SDL3 backend, pad %s, polled on the %s thread", g_name.empty() ? "none" : g_name.c_str(),
            [NSThread isMainThread] ? "main" : "game's");
        return;
    }
    const unsigned long pads = [GCController class] ? (unsigned long)[GCController controllers].count : 0;
    Log("status: %lu pads known to GameController, %d connect notifications, main queue %s, polled on the %s thread",
        pads, g_connects.load(), g_mainQueueAlive ? "running" : "NOT RUNNING", [NSThread isMainThread] ? "main" : "game's");
}

}  // namespace kmrp
