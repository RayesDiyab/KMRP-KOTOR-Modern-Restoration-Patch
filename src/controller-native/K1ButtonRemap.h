#pragma once
// Controller remapping at run time (K1ButtonRemap.cpp; the rules are
// K1ButtonRemapPolicy.h).
#include "K1ButtonRemapPolicy.h"
#include <cstdint>

// The layout in force: kmrp-controller.ini's [Controller Remap], read once; the
// default layout when there is none or it is not complete.
const KmrpRemap::Mapping& KmrpRemapSavedK1();
// Keeps a complete layout and writes it; false (nothing kept) for an incomplete one.
bool KmrpRemapSaveK1(const KmrpRemap::Mapping& mapping);
// The pad's button word (triggers folded in, KmrpRemap::Mask) as the controller code
// should see it: translated in the world, as it is everywhere else.
std::uint16_t KmrpRemapButtonsK1(std::uint16_t pad, bool world);
// The picture of the button an action is on, for a prompt naming it (kmr?rm<code>,
// the family's letter in place; KmrpRemap::GlyphCodes). Writes 16 bytes.
void KmrpRemapGlyphK1(int action, char family, char (&resref)[16]);
