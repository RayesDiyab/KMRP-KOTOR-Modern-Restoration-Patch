// KMRP for macOS: the fonts at the sizes in use, and the font style chosen (fonts.cpp).
#pragma once

#include <cstdint>
#include <string>

namespace kmrp {
namespace fonts {

// The fonts the game's override has, as listed at the start: 0 when none, else a number of their
// names, sizes and times (Modded Font, kmrp-layout/text_settings.cpp).
std::uint64_t OverrideFontSet();

// A size's view of its set has just been made (assets.cpp, Prepare; `whole` the set in the cache,
// `view` the folder the game is shown, `height` the screen's): the chosen style's fonts at the sizes
// in use go in place of the set's, and the sizes the loader finishes every font at are noted.
void Prepare(const std::string& whole, const std::string& view, int height);

// The style and sizes in force changed (the page): the view registered last holds the fonts made
// for them. False when something could not be made; the view is then as it was.
bool Apply();
// The fonts' metrics read again, each finished at the sizes in force, and with `images` their
// pictures too; every string then measures again.
void Reload(bool images);
bool IsFont(const char* name);
// Every known panel laid out again at the fonts' new metrics (layout.cpp, KmrpReflowTextK1):
// ResetFont through each control, then each control's SetExtent, which wraps its text anew.
void ReflowPanels();

}  // namespace fonts
}  // namespace kmrp
