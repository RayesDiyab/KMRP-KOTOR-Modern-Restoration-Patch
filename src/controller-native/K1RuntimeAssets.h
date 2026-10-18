#pragma once
#include <string>
bool KmrpRuntimeAssetsDimensions(int width, int height);
// Whether the finished layout sets reach this size: one of them, or a size the
// blend derives from the sets around it (4:3 to 32:9, from 640x480 up).
bool KmrpRuntimeAssetsCovers(int width, int height);
const std::wstring& KmrpRuntimeAssetDirectory();
// Finalize Override font metrics at native LoadTXI return, before first layout.
extern "C" void __cdecl KmrpFontMetricsLoadedK1(void* texture);
// Rewrite only bundled font images for a style switch, preserving Override.
bool KmrpRuntimeApplyTextPreferencesK1();
// Known GUI font resource names; do not rebuild unrelated texture metadata.
bool KmrpRuntimeIsFontK1(const char* name);
