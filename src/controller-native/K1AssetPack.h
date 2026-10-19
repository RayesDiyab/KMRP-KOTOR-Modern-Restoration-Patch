#pragma once
// KMRP's art pack, kmrp-assets.pack (tools/kmrp_pack.py, which documents the format): its
// index, and its files back from their blocks. Plain C++ with no system calls, so Windows'
// module (K1RuntimeAssets.cpp) and the Mac's read it with the same code; reading the file
// is the caller's. The blocks are LZMA, unpacked by the LZMA SDK's decoder
// (third_party/lzma-sdk/LzmaDec.c, compiled as C beside this).
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace KmrpPack {
using Key = std::array<unsigned char, 32>;
struct Entry { std::string name; Key key; };
struct Group { unsigned width, height; std::vector<Entry> entries; };
struct Block { std::uint32_t offset, stored, size; unsigned char properties[5]; unsigned objects; };
struct Object { std::uint32_t size, block, offset; unsigned char filter; };
struct Index {
    Key identity{};
    std::uint32_t start = 0;   // where the blocks begin: the index is the bytes before
    Key table{};               // gui-blend.bin
    std::vector<Group> groups;
    std::vector<Block> blocks;
    std::map<Key, Object> objects;
};

// The fixed part at the start of the file: this many bytes.
constexpr std::size_t kHeaderSize = 88;
// The largest file the pack may hold, and the largest index: far past what KMRP has, so a
// damaged size field is refused before anything is allocated for it.
constexpr std::uint32_t kLargestFile = 256u << 20;
constexpr std::uint32_t kLargestIndex = 64u << 20;

// From the first kHeaderSize bytes: the pack's identity and where its index ends. False when
// the bytes are not a pack's.
bool ReadHeader(const unsigned char* data, std::size_t size, Key& identity, std::uint32_t& start);
// The index from the file's first `start` bytes, every block held within `fileSize`.
bool ReadIndex(const unsigned char* data, std::size_t size, std::uint64_t fileSize, Index& index);
// A block's stored bytes unpacked into `out`, block.size bytes.
bool Unpack(const Block& block, const unsigned char* stored, unsigned char* out);
// An object's bytes as its block holds them turned back into the file, in place.
bool Unfilter(unsigned char filter, unsigned char* data, std::size_t size);
// The identity as the build writes it into KMRP_ASSET_BUILD: 64 lowercase hex digits.
std::string IdentityText(const Key& identity);
}
