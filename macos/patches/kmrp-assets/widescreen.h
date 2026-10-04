// KMRP for macOS: the widescreen patch, as KMRP's code talks to it (widescreen.cpp).
#pragma once

namespace kmrp {
namespace widescreen {

// The resolution the widescreen patch lays the game out for.
void Target(int* width, int* height);

// The same, changed while the game runs (the game's own mode switch).
void SetTarget(int width, int height);

// Asks the patch for layouts from .gui files, whatever swkotor.ini says. True when the patch
// has that entry point and took the request; false for a patch built into this module, whose
// read of swkotor.ini is answered instead (layouts_ini.cpp).
bool UseGuiFileLayouts();

}  // namespace widescreen
}  // namespace kmrp
