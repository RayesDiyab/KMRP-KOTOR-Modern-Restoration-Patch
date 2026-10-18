#pragma once
#include <vector>
bool KmrpRuntimeLayoutDimensions(void* manager, int width, int height);
// Every GUI frame: the lists of newly loaded panels made as wide as their rows need
// (K1RuntimeLayout.cpp, "List rows").
void KmrpListRowsFrame(void* manager);
void* KmrpRuntimeControlByTagK1(void* panel, const char* tag);
void KmrpReflowTextK1();
std::vector<void*> KmrpRuntimePanelsK1(const char* resource);
