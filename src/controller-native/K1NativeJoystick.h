#pragma once

// KOTOR's own joystick pipeline, fed from XInput.
//
// The PC build kept every layer of the console input system except two: no
// joystick device is ever enumerated (the count is a hardcoded zero), and no
// input-event description names a joystick control. Everything below that --
// the DIJOYSTATE poll, the POV decode, the record format, the control-code
// table, the description matching, the analog value path and the movement
// integrator -- is present and works. See
// `reverse-engineering/retained-xbox-gui-events.md`.
//
// This file supplies only the two missing pieces, so that input arrives through
// the engine's own path rather than as synthetic keystrokes.

// Once-per-session setup: registers joystick descriptions and makes the engine
// believe a joystick device exists. Safe to call every frame; does its work on
// the first call that finds the input singleton constructed.
void EnsureNativeJoystickK1(void* exoInputInternal);

// Replacement for CExoRawInputInternal::GetJoystickBuffer. Emits
// DIDEVICEOBJECTDATA records synthesised from XInput, edge-triggered exactly as
// the original was.
void FillNativeJoystickBufferK1(int deviceIndex, void* outBuffer);

// The left stick as one 2D vector, deadzoned radially and clamped to length 1.
// Returns false when inside the deadzone, in which case x and y are untouched
// and the caller must leave the keyboard's values alone.
bool ReadNativeStickK1(float& x, float& y);

// True while the native path owns gameplay movement, i.e. Control has run very
// recently. Used by the older XInput layer to stand its left-stick keystroke
// synthesis down in gameplay without disturbing it in menus, where Control does
// not run and those keystrokes still drive list navigation.
bool NativeMovementOwnsLeftStickK1();
