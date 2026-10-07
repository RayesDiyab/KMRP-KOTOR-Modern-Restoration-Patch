// KMRP for macOS, the controller patch: the Xbox-style HUD (xbox_hud.cpp), as the rest of the
// module asks about it.
#pragma once

namespace kmrp {
namespace xboxhud {

// Whether the Xbox-style HUD was chosen (KmrpXboxHudEnabledK1): the patch's option `xbox-hud`
// when a manager recorded one, otherwise [Hud] Style=Xbox in kmrp-controller.ini. Decided once.
bool Enabled();

// A panel built or destroyed (KmrpXboxHudForgetK1): when it is the HUD the layout was kept
// from, everything kept is dropped, since a HUD object at an address seen before is a new HUD.
void Forget(void* panel);

}  // namespace xboxhud
}  // namespace kmrp
