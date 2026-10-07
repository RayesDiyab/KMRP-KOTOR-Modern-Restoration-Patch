#pragma once
bool KmrpRuntimeLayoutDimensions(void* manager, int width, int height);
// Every GUI frame: the lists of newly loaded panels made as wide as their rows need
// (K1RuntimeLayout.cpp, "List rows").
void KmrpListRowsFrame(void* manager);
