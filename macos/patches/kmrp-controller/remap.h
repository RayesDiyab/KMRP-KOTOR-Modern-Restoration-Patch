// KMRP for macOS, controller support: controller remapping at run time (remap.cpp), Windows'
// K1ButtonRemap.h. The rules are the shared K1ButtonRemapPolicy.h, included here as Windows has
// it: it names _stricmp, which the Mac spells strcasecmp.
#pragma once

#include <cstdint>
#include <strings.h>

#ifndef _stricmp
#define _stricmp strcasecmp
#endif
#include "../../../src/controller-native/K1ButtonRemapPolicy.h"

namespace kmrp {
namespace remap {

// The layout saved in the controller's settings file: read once, the default without one.
const KmrpRemap::Mapping& Saved();

// Saves a complete layout as the one in use (KmrpRemapSaveK1). False when it could not be written.
bool Save(const KmrpRemap::Mapping& mapping);

// The pad's buttons as the rest of the controller code should see them (KmrpRemapButtonsK1), from
// the input poll: `buttons` as XInput lays them out, the triggers folded into 0x0400 and 0x0800;
// `world` in the world's input classes.
std::uint16_t Apply(std::uint16_t buttons, bool world);

// The pad's buttons as pressed, as Apply last saw them (KmrpPadButtonsK1): what the Controller
// Layout reads while it waits for a button, since menus send no event for LB or a stick's click.
std::uint16_t Physical();

// The picture of the button an action is on (KmrpRemapGlyphK1): kmr?rm<code>, the family's letter
// in place of the ?. A default action names its own button.
void Glyph(int action, char family, char (&resref)[16]);

}  // namespace remap
}  // namespace kmrp
