#pragma once
#include <windows.h>
#include <xinput.h>

// XInput-shaped normalized state. SDL's SOUTH/EAST/WEST/NORTH are physical
// positions, including Nintendo B/A/Y/X. Y is up-positive at this boundary.
bool ReadControllerK1(XINPUT_STATE& state);
int ControllerXInputSlotK1();       // -1 for SDL or disconnected
int ControllerSdlFamilyK1();        // -1 for XInput; 0/1/2/3 glyph families
unsigned long ControllerGenerationK1();
bool SetControllerRumbleK1(WORD low, WORD high);
