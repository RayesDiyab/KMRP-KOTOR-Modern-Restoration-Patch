#pragma once

#include <cstdint>

// Polls an attached Xbox controller and emits the keystrokes the rest of this
// patch (and the engine's own key bindings) already understand. Call once per
// frame; see K1XboxControlsXInput.cpp for why this is the whole interface.
void PollXInputK1();

// Last-input-device state used by KMRP's dynamic menu prompts. Controller
// injected keyboard events are identified separately so the DirectInput hook
// does not immediately switch the prompts back to keyboard mode.
bool IsControllerInputActiveK1();
bool IsControllerConnectedK1();
bool IsControllerGeneratedKeyK1(std::uint32_t scancode);
unsigned long LastInjectedDeadlineK1(std::uint32_t scancode);
void MarkKeyboardMouseInputK1();
extern "C" void __cdecl KmrpNotePadPresentK1(int present);

// The normal game input loop is suspended during Bink playback. The movie
// frame hook calls this separate edge detector so A, B, LB, or Start can cancel
// the current movie without relying on synthetic keyboard messages.
bool ConsumeMovieSkipK1();
