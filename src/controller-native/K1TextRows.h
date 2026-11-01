#pragma once

// Native CSWGuiListBox only. Uses its existing rows, saved extents and scrolling
// contract; never owns, replaces or creates controls.
void KmrpTextRowsK1(void* list);
void KmrpTextRowsForgetK1(void* control);

// Called with the validated GUI viewport before visiting native lists. The draw
// hook uses this same last-observed scale until the next GUI frame.
void KmrpTextRowsViewportK1(int height);

// K1RuntimeLayout.cpp. The Icon Size slider owns a skill row's icon, the third icon border
// (+0x29C) once it has left its default this session; `cell` is the box the row gives it.
bool KmrpSkillIconOwnedK1();
void KmrpSizeSkillIconK1(void* icon, const void* cell);
