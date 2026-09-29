// KMRP for macOS, controller support: the gameplay HUD (hud.cpp), as the input hook asks it.
#pragma once

namespace kmrp {
namespace hud {

// What a press in the world asks of the HUD, performed on its own frame (KmrpHudFrame).
void RequestMove(int dx, int dy);   // the D-pad: Left/Right along the action bar, Up/Down its action
void RequestActivate();             // A: the focused slot's action, when a slot has focus
void RequestRelease();              // B: let go of the action bar
void RequestClearOne();             // Y in combat: remove the last queued action
void RequestDisengage();            // X in combat: disengage

// Whether a slot of the action bar has focus, in which case A belongs to it and not to the
// world (asked by the world's interaction bridge).
bool ActionBarFocused();

// One log line on what the HUD did.
void Status();

}  // namespace hud
}  // namespace kmrp
