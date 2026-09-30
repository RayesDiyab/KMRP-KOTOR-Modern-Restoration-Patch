// KMRP for macOS, controller support: what the input hook hands the frame hooks.
//
// The input hook (native.cpp) runs inside CExoInput's polling and only records what a press
// asks for. The engine is called from the frame hooks (gameplay.cpp), outside the polling,
// as K1NativeJoystick.cpp does it: calling back into creature or GUI code from inside the
// input poll would re-enter the engine where it never re-enters itself.
#pragma once

#include <cstdint>

namespace kmrp {

// Monotonic milliseconds.
std::uint64_t NowMs();

// A request is the time it was made, 0 when there is none. A frame hook takes it only within
// kRequestWindowMs and only where it still applies; a request nothing takes is dropped, so a
// press made in a menu cannot act on the world after the menu closes.
struct Requests {
    std::uint64_t flourish = 0;       // L3 in the world
    std::uint64_t freeLookExit = 0;   // R3 in free look
    std::uint64_t mapOpen = 0;        // Start in the world
    std::uint64_t interact = 0;       // A in the world: the default action on the target
    std::uint64_t partySwitch = 0;    // R3 on a screen about a party member
};
const std::uint64_t kRequestWindowMs = 250;
extern Requests g_requests;

// Takes a request: true when it was made within the window. Clears it either way.
bool TakeRequest(std::uint64_t& request);

// The right stick, -1..1, up positive, for the camera; the left stick's drive after the
// deadzone, 0..1 (0 when centred); and when the input hook last filled a pad buffer.
extern float g_rightX, g_rightY;
extern std::uint64_t g_lastPadPressMs;   // the last button press on the pad
extern std::uint32_t g_padButtons;       // the pad's buttons at the last poll (pad.h's bits)
extern float g_analogMagnitude;
// The left stick as the buffer sends it (after the radial deadzone), -1..1, Y growing downward.
extern float g_leftX, g_leftY;
extern std::uint64_t g_lastBufferMs;

// gameplay.cpp: whether the left stick drives the character this frame, and one log line on
// what the world's bridges did.
bool AnalogDriving();
void GameplayStatus();

}  // namespace kmrp
