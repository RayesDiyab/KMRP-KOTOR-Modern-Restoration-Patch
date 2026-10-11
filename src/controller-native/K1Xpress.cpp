#include "K1Xpress.h"

#include <cstdint>
#include <cstring>
#include <vector>

// The container, measured against cabinet.dll on Windows 11 (2026-10-10): 24 bytes
// (the magic 0A 51 E5 C0, the header's size 0x18 as 16 bits, a check byte, the
// algorithm as one byte, the decoded size as 64 bits, the chunk size as 64 bits:
// the decoded size up to 64 MB), then for each chunk its stored size as 32 bits and
// its bytes. A chunk whose stored size is its decoded size is not compressed. The
// rest is LZ77 with Huffman codes as [MS-XCA] 2.2 describes it: a new 256-byte table
// of 512 four-bit code lengths for every 65,536 decoded bytes.

namespace {

constexpr std::size_t kHeader = 24;
constexpr std::size_t kTableBytes = 256;
constexpr std::size_t kBlock = 65536;
constexpr unsigned kCodeBits = 15;

struct Stream {
    const unsigned char* at;
    const unsigned char* end;

    // The next 16 bits of the code stream; zeros once the input is used up, which a
    // well-formed chunk only reads as the bits after its last symbol.
    std::uint32_t word()
    {
        if (end - at < 2) { at = end; return 0; }
        const std::uint32_t value = at[0] | static_cast<std::uint32_t>(at[1]) << 8;
        at += 2;
        return value;
    }
};

// The symbol and code length for each 15-bit prefix, as symbol << 4 | length; zero
// where no code begins with that prefix.
bool BuildTable(const unsigned char* lengths, std::vector<std::uint16_t>& table)
{
    std::size_t filled = 0;
    for (unsigned length = 1; length <= kCodeBits; ++length) {
        const std::size_t span = static_cast<std::size_t>(1) << (kCodeBits - length);
        for (unsigned symbol = 0; symbol < 512; ++symbol) {
            const unsigned held = symbol & 1 ? lengths[symbol >> 1] >> 4 : lengths[symbol >> 1] & 15;
            if (held != length) continue;
            if (table.size() - filled < span) return false;
            const std::uint16_t entry = static_cast<std::uint16_t>(symbol << 4 | length);
            for (std::size_t i = 0; i < span; ++i) table[filled + i] = entry;
            filled += span;
        }
    }
    for (std::size_t i = filled; i < table.size(); ++i) table[i] = 0;
    return filled != 0;
}

bool DecodeChunk(const unsigned char* in, std::size_t inSize, unsigned char* out, std::size_t outSize,
                 std::vector<std::uint16_t>& table)
{
    Stream stream{in, in + inSize};
    std::size_t written = 0;
    while (written < outSize) {
        if (static_cast<std::size_t>(stream.end - stream.at) < kTableBytes || !BuildTable(stream.at, table)) return false;
        stream.at += kTableBytes;
        std::uint32_t bits = stream.word() << 16;
        bits |= stream.word();
        int extra = 16;
        const std::size_t blockEnd = outSize - written > kBlock ? written + kBlock : outSize;
        // A match may run past the block's end; the next table follows it all the same.
        while (written < blockEnd) {
            const std::uint16_t entry = table[bits >> (32 - kCodeBits)];
            const unsigned codeLength = entry & 15;
            if (!codeLength) return false;
            unsigned symbol = entry >> 4;
            bits <<= codeLength;
            extra -= static_cast<int>(codeLength);
            if (extra < 0) { bits |= stream.word() << -extra; extra += 16; }
            if (symbol < 256) { out[written++] = static_cast<unsigned char>(symbol); continue; }
            symbol -= 256;
            std::size_t length = symbol & 15;
            const unsigned offsetBits = symbol >> 4;
            if (length == 15) {
                if (stream.at == stream.end) return false;
                length = *stream.at++;
                if (length == 255) {
                    if (stream.end - stream.at < 2) return false;
                    length = stream.at[0] | static_cast<std::size_t>(stream.at[1]) << 8;
                    stream.at += 2;
                    if (length == 0) {
                        if (stream.end - stream.at < 4) return false;
                        length = stream.at[0] | static_cast<std::size_t>(stream.at[1]) << 8 |
                                 static_cast<std::size_t>(stream.at[2]) << 16 | static_cast<std::size_t>(stream.at[3]) << 24;
                        stream.at += 4;
                    }
                    if (length < 15) return false;
                    length -= 15;
                }
                length += 15;
            }
            length += 3;
            const std::size_t offset = (offsetBits ? bits >> (32 - offsetBits) : 0) + (static_cast<std::size_t>(1) << offsetBits);
            bits <<= offsetBits;
            extra -= static_cast<int>(offsetBits);
            if (extra < 0) { bits |= stream.word() << -extra; extra += 16; }
            if (offset > written || length > outSize - written) return false;
            // Byte by byte: a match may overlap what it writes.
            const unsigned char* from = out + written - offset;
            unsigned char* to = out + written;
            for (std::size_t i = 0; i < length; ++i) to[i] = from[i];
            written += length;
        }
    }
    return true;
}

std::uint64_t Read64(const unsigned char* at)
{
    std::uint64_t value = 0;
    for (int i = 7; i >= 0; --i) value = value << 8 | at[i];
    return value;
}

}  // namespace

bool KmrpXpressDecode(const unsigned char* in, std::size_t inSize, unsigned char* out, std::size_t outSize)
{
    static const unsigned char magic[4] = {0x0A, 0x51, 0xE5, 0xC0};
    if (inSize < kHeader || std::memcmp(in, magic, 4) || in[4] != kHeader || in[5] != 0 || in[7] != 4) return false;
    const std::uint64_t total = Read64(in + 8), chunk = Read64(in + 16);
    if (total != outSize || (outSize && (!chunk || chunk > total))) return false;
    std::vector<std::uint16_t> table(static_cast<std::size_t>(1) << kCodeBits);
    const unsigned char* at = in + kHeader;
    const unsigned char* end = in + inSize;
    std::size_t written = 0;
    while (written < outSize) {
        if (end - at < 4) return false;
        const std::size_t stored = at[0] | static_cast<std::size_t>(at[1]) << 8 |
                                   static_cast<std::size_t>(at[2]) << 16 | static_cast<std::size_t>(at[3]) << 24;
        at += 4;
        const std::size_t size = outSize - written > chunk ? static_cast<std::size_t>(chunk) : outSize - written;
        if (static_cast<std::size_t>(end - at) < stored || stored > size) return false;
        if (stored == size) std::memcpy(out + written, at, size);
        else if (!DecodeChunk(at, stored, out + written, size, table)) return false;
        at += stored;
        written += size;
    }
    return at == end;
}
