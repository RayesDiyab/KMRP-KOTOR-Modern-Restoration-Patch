#pragma once

// Last-input-device state used by KMRP's dynamic menu prompts.
bool IsControllerInputActiveK1();
void MarkKeyboardMouseInputK1();
extern "C" void __cdecl KmrpNotePadPresentK1(int present);
extern "C" void __cdecl KmrpMarkControllerActiveK1();
extern "C" unsigned long __cdecl KmrpDeviceStateK1();

