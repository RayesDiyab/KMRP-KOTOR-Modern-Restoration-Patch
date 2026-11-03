// KMRP for macOS, controller support: the parts of the Aspyr engine the module calls.
//
// KOTOR_Exe 1.4.0 (C1FCB8D3...6D71), x86_64. Each entry names the Windows 1.0.3 equivalent
// the Windows module (src/controller-native/K1NativeJoystick.cpp) uses, so the two can be
// read side by side. Offsets are 64-bit: most are the Windows ones doubled, and every one
// was read from the Mac code, not derived.
#pragma once

#include <cstddef>
#include <cstdint>

namespace kmrp {
namespace engine {

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

// g_pAppManager (Windows 0x007A39FC). The app manager's +8 is the CClientExoApp (Windows +4),
// whose +8 is its CClientExoAppInternal (Windows +4).
inline void* ClientApp() {
    void* manager = *reinterpret_cast<void**>(0x100677cf0UL);
    return manager ? At<void*>(manager, 8) : nullptr;
}
inline void* ClientInternal() {
    void* app = ClientApp();
    return app ? At<void*>(app, 8) : nullptr;
}

// CClientExoAppInternal.
const std::size_t kInternalModule = 0x30;       // CSWCModule*, the camera's owner; Windows +0x18
const std::size_t kInternalGuiInGame = 0x80;    // CGuiInGame*; Windows +0x40
const std::size_t kGuiInGameScreen = 0x50;      // the screen last shown, 0..7; Windows +0x2C
const std::size_t kInternalInputClass = 0x128;  // SetInputClass (0x1002fb622) writes it; Windows +0x9C
const std::size_t kInternalGuiManager = 0x390;  // CSWGuiManager*
const std::size_t kInternalTarget = 0x408;      // the target, a 64-bit object id; Windows +0x2B4
const std::uint64_t kObjectInvalid = 0x7f000000;

// Input classes, keymap.2da's IC* columns.
enum InputClass { kClassPC = 0, kClassMiniGame = 1, kClassPCGUI = 2, kClassDialog = 3, kClassFreeLook = 4 };

inline int CurrentInputClass() {
    void* internal = ClientInternal();
    return internal ? At<int>(internal, kInternalInputClass) : -1;
}

// CClientExoAppInternal::HandleInputEvent (0x1002fa0a0; Windows 0x00621210), the router the
// keyboard's actions go through. Called with an event id, it runs the retained handler with
// all of that handler's own guards.
using HandleInputEventFn = int (*)(void* internal, int event, int value);
inline HandleInputEventFn HandleInputEvent() { return reinterpret_cast<HandleInputEventFn>(0x1002fa0a0UL); }

// CClientExoApp. GetPlayerCreature (Windows 0x005ED540); GetInFreeLook (not in KPM's Mac
// database: 0x10028c480 returns internal+0x4A0, and the router and AcclTurnCamera read it
// where Windows calls GetInFreeLook); PlayerFlourishWeapons (Windows 0x005EDE90: the router's
// 0xF2 handler calls 0x10028c49e, which hands internal to the flourish itself).
using AppPtrFn = void* (*)(void* app);
using AppIntFn = int (*)(void* app);
using AppVoidFn = void (*)(void* app);
inline AppPtrFn GetPlayerCreature() { return reinterpret_cast<AppPtrFn>(0x10028bc40UL); }
inline AppIntFn GetInFreeLook() { return reinterpret_cast<AppIntFn>(0x10028c480UL); }
inline AppVoidFn PlayerFlourishWeapons() { return reinterpret_cast<AppVoidFn>(0x10028c49eUL); }

// CClientExoAppInternal::UpdateCamera (0x1002695b0; Windows 0x005F5E10): (frame seconds,
// internal). MainLoop passes it the float at 0x1005ca818.
using UpdateCameraFn = void (*)(float seconds, void* internal);
inline UpdateCameraFn UpdateCamera() { return reinterpret_cast<UpdateCameraFn>(0x1002695b0UL); }
inline float FrameSeconds() { return *reinterpret_cast<const float*>(0x1005ca818UL); }

// CSWCModule::AcclTurnCamera (0x1002915fa; Windows 0x00640090): (turn, module). In the normal
// camera it adds the turn to the camera's rate, which the camera integrates; UpdateCamera
// passes the keyboard's turn axis, -1..1, through it.
using TurnCameraFn = void (*)(float turn, void* module);
inline TurnCameraFn AcclTurnCamera() { return reinterpret_cast<TurnCameraFn>(0x1002915faUL); }

// CSWCModule's free-look pitch (0x100291266; Windows 0x0063FDB0): (rate, module). With the camera
// in mode 5 it writes the rate, negated, to the free-look camera's +0x38 (behaviour 0x106E,
// Windows +0x24), which CSWCameraFreeLook::Control (0x1002B2908) adds to its pitch and clears, so
// it is given on every frame it should last. ProcessInput calls it the same way (0x1002F8226) when the camera mode, options +0x5B, is 5.
inline TurnCameraFn PitchCamera() { return reinterpret_cast<TurnCameraFn>(0x100291266UL); }

// Vector::Normalize (0x10036f38e; Windows 0x004AB130).
using NormalizeFn = void (*)(void* vector);
inline NormalizeFn VectorNormalize() { return reinterpret_cast<NormalizeFn>(0x10036f38eUL); }

// Router events, K1NativeJoystick.cpp's.
const int kEventFreeLookExit = 0x06;    // also SelectPrev: the handler decides by camera mode
const int kEventMenuMap = 0xD7;         // the in-game menu's Map screen (0xD1 + 6)
const int kEventDefaultAction = 0xEF;   // the default action on the target
const int kEventMenuFirst = 0xD1;       // the in-game menu's screens: 0xD1 + the screen, 0..7
const int kScreenCount = 8;

}  // namespace engine
}  // namespace kmrp
