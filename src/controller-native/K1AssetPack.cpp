// KMRP's art pack: see K1AssetPack.h, and tools/kmrp_pack.py for the format.
#include "K1AssetPack.h"
#include "LzmaDec.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>

namespace KmrpPack {
namespace {
const unsigned char kMagic[8] = {'K', 'M', 'R', 'P', 'A', 'K', '0', '1'};

struct Reader {
    const unsigned char* at;
    const unsigned char* end;
    bool bytes(void* out, std::size_t size)
    {
        if (static_cast<std::size_t>(end - at) < size) return false;
        std::memcpy(out, at, size);
        at += size;
        return true;
    }
    bool u32(std::uint32_t& value)
    {
        unsigned char b[4];
        if (!bytes(b, 4)) return false;
        value = b[0] | (b[1] << 8) | (b[2] << 16) | (static_cast<std::uint32_t>(b[3]) << 24);
        return true;
    }
    bool name(std::string& value)
    {
        unsigned char b[2];
        if (!bytes(b, 2)) return false;
        const unsigned length = b[0] | (b[1] << 8);
        if (!length || length > 255 || static_cast<std::size_t>(end - at) < length) return false;
        value.assign(reinterpret_cast<const char*>(at), length);
        at += length;
        // A name becomes a file in the cache: no folders, no way out of it.
        return value.find_first_of("/\\:") == std::string::npos && value.find("..") == std::string::npos;
    }
};

void* Allocate(ISzAllocPtr, size_t size) { return std::malloc(size); }
void Release(ISzAllocPtr, void* address) { std::free(address); }
const ISzAlloc kAllocator = {Allocate, Release};

// Filter 1: the MED prediction added back to every byte, row by row in the file's order,
// then green added back to blue and red.
bool UnfilterTga(unsigned char* data, std::size_t size)
{
    if (size < 18 || data[1] != 0 || data[2] != 2) return false;
    const unsigned width = data[12] | (data[13] << 8), height = data[14] | (data[15] << 8), bits = data[16];
    const unsigned channels = bits / 8;
    const std::size_t start = 18 + static_cast<std::size_t>(data[0]);
    if ((bits != 24 && bits != 32) || !width || !height) return false;
    const std::size_t row = static_cast<std::size_t>(width) * channels;
    if (start > size || row * height > size - start) return false;
    unsigned char* pixels = data + start;
    for (unsigned y = 0; y < height; ++y) {
        unsigned char* line = pixels + row * y;
        const unsigned char* up = y ? line - row : nullptr;
        for (unsigned c = 0; c < channels; ++c) {
            int left = 0, upLeft = 0;
            for (std::size_t at = c; at < row; at += channels) {
                const int above = up ? up[at] : 0;
                const int low = (std::min)(left, above), high = (std::max)(left, above);
                const int predicted = upLeft >= high ? low : upLeft <= low ? high : left + above - upLeft;
                line[at] = static_cast<unsigned char>(line[at] + predicted);
                left = line[at];
                upLeft = above;
            }
        }
    }
    for (std::size_t at = 0; at < row * height; at += channels) {
        pixels[at] = static_cast<unsigned char>(pixels[at] + pixels[at + 1]);
        pixels[at + 2] = static_cast<unsigned char>(pixels[at + 2] + pixels[at + 1]);
    }
    return true;
}

// Filters 2 and 3: the fields of every whole DXT block after the TPC's header put back
// together, the block's bytes one after another again.
bool UnfilterDxt(unsigned char* data, std::size_t size, std::size_t block, const std::size_t* widths, unsigned fields)
{
    const std::size_t header = 128;
    if (size < header + 16) return false;
    const std::size_t count = (size - header) / block;
    std::vector<unsigned char> split(data + header, data + header + count * block);
    std::size_t from = 0, into = 0;
    for (unsigned f = 0; f < fields; ++f) {
        for (std::size_t i = 0; i < count; ++i)
            std::memcpy(data + header + i * block + into, split.data() + from + i * widths[f], widths[f]);
        from += count * widths[f];
        into += widths[f];
    }
    return true;
}
}

bool ReadHeader(const unsigned char* data, std::size_t size, Key& identity, std::uint32_t& start)
{
    if (size < kHeaderSize || std::memcmp(data, kMagic, 8)) return false;
    std::memcpy(identity.data(), data + 8, 32);
    Reader reader{data + 40, data + size};
    return reader.u32(start) && start >= kHeaderSize && start <= kLargestIndex;
}

bool ReadIndex(const unsigned char* data, std::size_t size, std::uint64_t fileSize, Index& index)
{
    Index parsed;
    if (!ReadHeader(data, size, parsed.identity, parsed.start) || parsed.start != size) return false;
    Reader reader{data + 44, data + size};
    std::uint32_t groupCount, blockCount, objectCount;
    if (!reader.u32(groupCount) || !reader.u32(blockCount) || !reader.u32(objectCount) ||
        !reader.bytes(parsed.table.data(), 32) || groupCount > 1000 || blockCount > objectCount || objectCount > 200000)
        return false;
    for (std::uint32_t i = 0; i < groupCount; ++i) {
        Group group{};
        std::uint32_t count;
        if (!reader.u32(group.width) || !reader.u32(group.height) || !reader.u32(count) || count > 100000) return false;
        group.entries.reserve(count);
        for (std::uint32_t j = 0; j < count; ++j) {
            Entry entry;
            if (!reader.name(entry.name) || !reader.bytes(entry.key.data(), 32)) return false;
            group.entries.push_back(std::move(entry));
        }
        parsed.groups.push_back(std::move(group));
    }
    for (std::uint32_t i = 0; i < blockCount; ++i) {
        Block block{};
        if (!reader.u32(block.offset) || !reader.u32(block.stored) || !reader.u32(block.size) ||
            !reader.bytes(block.properties, 5) || block.offset < parsed.start || !block.size ||
            block.size > kLargestFile || block.offset + static_cast<std::uint64_t>(block.stored) > fileSize) return false;
        parsed.blocks.push_back(block);
    }
    for (std::uint32_t i = 0; i < objectCount; ++i) {
        Key key;
        Object object{};
        if (!reader.bytes(key.data(), 32) || !reader.u32(object.size) || !reader.u32(object.block) ||
            !reader.u32(object.offset) || !reader.bytes(&object.filter, 1) || !object.size || object.filter > 3 ||
            object.block >= parsed.blocks.size() ||
            object.offset + static_cast<std::uint64_t>(object.size) > parsed.blocks[object.block].size ||
            !parsed.objects.emplace(key, object).second) return false;
        ++parsed.blocks[object.block].objects;
    }
    if (reader.at != reader.end || !parsed.objects.count(parsed.table)) return false;
    index = std::move(parsed);
    return true;
}

bool Unpack(const Block& block, const unsigned char* stored, unsigned char* out)
{
    SizeT produced = block.size, consumed = block.stored;
    ELzmaStatus status;
    const SRes result = LzmaDecode(out, &produced, stored, &consumed, block.properties, LZMA_PROPS_SIZE,
                                   LZMA_FINISH_END, &status, &kAllocator);
    return result == SZ_OK && produced == block.size && consumed == block.stored &&
           (status == LZMA_STATUS_FINISHED_WITH_MARK || status == LZMA_STATUS_MAYBE_FINISHED_WITHOUT_MARK);
}

bool Unfilter(unsigned char filter, unsigned char* data, std::size_t size)
{
    static const std::size_t dxt1[] = {4, 4}, dxt5[] = {2, 6, 4, 4};
    switch (filter) {
    case 0: return true;
    case 1: return UnfilterTga(data, size);
    case 2: return UnfilterDxt(data, size, 8, dxt1, 2);
    case 3: return UnfilterDxt(data, size, 16, dxt5, 4);
    }
    return false;
}

std::string IdentityText(const Key& identity)
{
    static const char digits[] = "0123456789abcdef";
    std::string text;
    for (unsigned char byte : identity) {
        text += digits[byte >> 4];
        text += digits[byte & 15];
    }
    return text;
}
}
