// KMRP for macOS: the HUD Size page (hud_options.cpp) and the mouse and keyboard HUD placed from
// it (pc_hud.cpp). Windows' K1HudOptions.h.
#pragma once

namespace kmrp {
namespace hud {

// The page's frame: the entry on Graphics Options, the page opened, the sliders read.
void PageFrame(void* manager);
// A panel going away: the entry's button on it, the page's parent.
void PageDestroyed(void* panel);
bool PageOpen();
// A part's size in percent, 50 today's (KmrpHudOptions::Element).
int SizePercent(int element);

// The HUD placed when something changed, and a HUD going away (pc_hud.cpp).
void PcHudFrame(void* manager);
void PcHudForget(void* panel);

}  // namespace hud
}  // namespace kmrp
