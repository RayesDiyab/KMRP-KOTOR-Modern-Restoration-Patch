#pragma once

#include <cstdint>

// Last-input-device state used by KMRP's dynamic menu prompts. Controller
// injected keyboard events are identified separately so the DirectInput hook
// does not immediately switch the prompts back to keyboard mode.
bool IsControllerInputActiveK1();
bool IsControllerGeneratedKeyK1(std::uint32_t scancode);
void MarkKeyboardMouseInputK1();
extern "C" void __cdecl KmrpNotePadPresentK1(int present);
extern "C" unsigned long __cdecl KmrpDeviceStateK1();

