// KMRP for macOS, controller support: the pad, read once per input poll.
//
// The state is normalised to XInput's layout so the bindings read like the Windows module's
// (src/controller-native/K1NativeJoystick.cpp): the same button bits, sticks from -1 to 1
// with up positive, triggers from 0 to 1.
#pragma once

#include <cstdint>

namespace kmrp {

enum PadButton : std::uint32_t {
    kPadUp = 0x0001, kPadDown = 0x0002, kPadLeft = 0x0004, kPadRight = 0x0008,
    kPadStart = 0x0010, kPadBack = 0x0020, kPadL3 = 0x0040, kPadR3 = 0x0080,
    kPadLB = 0x0100, kPadRB = 0x0200,
    kPadA = 0x1000, kPadB = 0x2000, kPadX = 0x4000, kPadY = 0x8000,
};

struct PadState {
    bool present = false;
    std::uint32_t buttons = 0;
    float lx = 0, ly = 0, rx = 0, ry = 0;   // -1..1, up positive
    float lt = 0, rt = 0;                   // 0..1
};

// The pad last used, through SDL3 (or Apple's GameController without it), or, when
// KMRP_PAD_SCRIPT names a file, the scripted pad it describes (for automated tests; see
// pad.mm). False when there is none.
bool ReadPad(PadState* out);

// The pad's product name, for the log. Empty when there is none.
const char* PadName();

// The pad's glyph family, for the prompts: 0 Xbox or generic, 1 PlayStation, 2 Nintendo,
// 3 Steam (K1ControllerBackend.cpp's families); -1 without a pad. The scripted pad is Xbox
// unless KMRP_PAD_FAMILY names another (p, s, n or d, the art's letters).
int PadFamily();

// The pad's two motors, 0..1 each (heavy the left, low-frequency one; light the right), through
// SDL3. Nothing without it, or for the scripted pad. True when a send was accepted.
bool SetRumble(float heavy, float light);

// Whether the game is the active application, as AppKit last announced on the main thread.
// The cursor is parked only then: a warp made while the player is in another app would take
// their pointer.
bool AppActive();

// One line on which backend reads the pad and what it sees, for the log.
void Status();

// "[KMRP controller] ..." to stderr, which the game's own output goes to as well.
void Log(const char* format, ...) __attribute__((format(printf, 1, 2)));

}  // namespace kmrp
