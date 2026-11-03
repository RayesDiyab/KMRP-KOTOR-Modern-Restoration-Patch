// KMRP for macOS: the Text Size and Font page (text_options.cpp). Windows' K1TextOptions.h.
#pragma once

namespace kmrp {
namespace text {

// The page's frame: the entry on Graphics Options, the page opened, the sliders read.
void PageFrame(void* manager);
// A panel going away: the entry's button on it, the page's parent.
void PageDestroyed(void* panel);

}  // namespace text

namespace hud {
bool PageOpen();   // hud_options.cpp
}

}  // namespace kmrp
