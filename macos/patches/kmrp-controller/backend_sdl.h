// KMRP for macOS, controller support: the SDL3 backend (backend_sdl.cpp).
#pragma once

#include <string>

namespace kmrp {

struct PadState;

// True once kmrp-sdl3.dylib, beside this module, is loaded with every function it needs.
bool SdlAvailable();

// The pad last used, normalised; false when there is none. Starts SDL's gamepad subsystem
// on the first call, on the calling thread, which must be the thread that polls.
bool ReadSdlPad(PadState* out, std::string* name);

// The active pad's glyph family (0 Xbox or generic, 1 PlayStation, 2 Nintendo, 3 Steam), or
// -1; and a count that changes whenever the active pad does.
int SdlPadFamily();
unsigned long SdlGeneration();

// The active pad's motors, 0..1 each (heavy the left, low-frequency one), as
// K1ControllerBackend.cpp's SetControllerRumbleK1 sends them. True when a send was accepted.
bool SdlRumble(float heavy, float light, bool appActive);

}  // namespace kmrp
