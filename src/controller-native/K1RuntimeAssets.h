#pragma once
#include <string>
bool KmrpRuntimeAssetsDimensions(int width, int height);
// Whether the finished layout sets reach this size: one of them, or a size the
// blend derives from the sets around it (4:3 to 32:9, from 640x480 up).
bool KmrpRuntimeAssetsCovers(int width, int height);
// This run's folder of the common files (the controller's SDL library among them).
const std::wstring& KmrpRuntimeAssetDirectory();
// This run's folder for the size in use: its layouts (.gui) and the rest of its set.
const std::wstring& KmrpRuntimeLayoutDirectory();
// A layout file (name with extension) as the game reads it at the size in use: the
// adapted party roster from its own folder when there is one, else the set's.
std::wstring KmrpRuntimeLayoutFile(const std::wstring& name);
// Finalize Override font metrics at native LoadTXI return, before first layout.
extern "C" void __cdecl KmrpFontMetricsLoadedK1(void* texture);
// Rewrite only bundled font images for a style switch, preserving Override.
bool KmrpRuntimeApplyTextPreferencesK1();
// Known GUI font resource names; do not rebuild unrelated texture metadata.
bool KmrpRuntimeIsFontK1(const char* name);
// The Icon Size slider (issue 80): its percent (K1TextOptions.cpp, swkotor.ini [KMRP Text]
// IconSize), and the rows sized for a new one.
int KmrpIconSizePercentK1();
bool KmrpRuntimeApplyIconSizeK1();
// Told before each part of KmrpRuntimeAssetsPrepare: parts done, parts in all, and the
// size about to be made (0, 0 for the common files and at the end). Nonzero stops.
typedef int (__stdcall* KmrpPrepareStep)(int done, int total, int width, int height, void* context);
// The installer's preparation: the common files, then every size the display offers that
// KMRP covers, largest first, each with the fonts in use at its height, all into the
// cache; or a share of it, for one of `shares` workers each in a process of its own
// (`share` 0 makes the common files). The number of sizes made, or -1 when the pack
// cannot be read or the common files cannot be made.
int KmrpRuntimeAssetsPrepare(int share, int shares, KmrpPrepareStep step, void* context);
