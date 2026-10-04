#pragma once
#include <string>
bool KmrpRuntimeAssetsDimensions(int width, int height);
// Whether the finished layout sets reach this size: one of them, or a size the
// blend derives from the sets around it (4:3 to 32:9, from 640x480 up).
bool KmrpRuntimeAssetsCovers(int width, int height);
const std::wstring& KmrpRuntimeAssetDirectory();
