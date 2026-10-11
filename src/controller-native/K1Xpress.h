#pragma once

#include <cstddef>

// Decodes what the Windows Compression API's Compress() writes for
// COMPRESS_ALGORITHM_XPRESS_HUFF, the form the two embedded banks are stored in
// (tools/build_native_assets.py, tools/build_controller_assets.py), without calling
// that API. Wine and Proton do not have its decoder: cabinet.dll there has no
// CreateDecompressor (ordinal 40) up to Wine 11.0, and Wine's later one is a stub
// that decodes nothing, so a module that imported it ended the game at startup
// (issue 30). `outSize` is the size the bank records for the object; false unless
// exactly that many bytes were decoded.
bool KmrpXpressDecode(const unsigned char* in, std::size_t inSize, unsigned char* out, std::size_t outSize);
