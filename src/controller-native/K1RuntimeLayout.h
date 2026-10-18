#pragma once
#include <vector>
bool KmrpRuntimeLayoutDimensions(void* manager, int width, int height);
// Every GUI frame: the lists of newly loaded panels made as wide as their rows need
// (K1RuntimeLayout.cpp, "List rows").
void KmrpListRowsFrame(void* manager);
void* KmrpRuntimeControlByTagK1(void* panel, const char* tag);
void KmrpReflowTextK1();
std::vector<void*> KmrpRuntimePanelsK1(const char* resource);
std::vector<void*> KmrpRuntimeAllPanelsK1();   // every panel loaded and not yet destroyed
// A top-level control of a layout file in KMRP's cache for the size in force: its tag,
// extent and its border's fill texture (empty if none). For the HUD Size preview.
struct KmrpGuiPiece { char tag[32]; int left, top, width, height; char fill[17]; };
bool KmrpRuntimeGuiPiecesK1(const char* resource, std::vector<KmrpGuiPiece>& pieces);
