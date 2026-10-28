#pragma once

// The HUD Size page in Graphics Options (K1HudOptions.cpp).
// Every GUI frame: the page's entry button, the page itself, its saving and preview.
void KmrpHudOptionsFrameK1(void* manager);
void KmrpHudOptionsDestroyedK1(void* panel);
// Once a movie frame while the intro movies play (CoreMovieFrameK1): a few of the HUD Size
// preview's textures loaded and kept, so the page's first opening does not load them.
void KmrpPreloadHudPagesK1();
// The page is open (the Text Size page's entry shows no A over it).
bool KmrpHudOptionsOpenK1();
// The size chosen for an element (KmrpHudOptions::Element), in percent; 50 is today's.
int KmrpHudSizePercentK1(int element);
// The mouse and keyboard HUD placed from KMRP's table and sized (K1PcHud.cpp): every
// GUI frame, and as a panel is destroyed.
void KmrpPcHudFrameK1(void* manager);
void KmrpPcHudForgetK1(void* panel);
