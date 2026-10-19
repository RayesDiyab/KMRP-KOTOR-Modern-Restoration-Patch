// Reads a whole art pack back with the module's own decoder (src/controller-native/
// K1AssetPack.cpp and the LZMA SDK's LzmaDec.c, as the module compiles them): every block
// unpacked, every file un-filtered and held against its SHA-256. Run by
// Test-NativeAssetsBank.py; portable C++, so the Mac can run it on its pack too.
//
//     asset_pack_harness PACK [IDENTITY]
//
// IDENTITY, when given, is what the module was built to expect (KMRP_ASSET_BUILD).
// Prints one line of counts and times and "PASS", or what failed and exits 1.
#include "K1AssetPack.h"
#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {
// SHA-256 (FIPS 180-4), small and slow enough for a test.
struct Sha256 {
    std::uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    static std::uint32_t Rotate(std::uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
    void Block(const unsigned char* p)
    {
        static const std::uint32_t k[64] = {
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
        std::uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (std::uint32_t(p[4 * i]) << 24) | (p[4 * i + 1] << 16) | (p[4 * i + 2] << 8) | p[4 * i + 3];
        for (int i = 16; i < 64; ++i) {
            const std::uint32_t s0 = Rotate(w[i - 15], 7) ^ Rotate(w[i - 15], 18) ^ (w[i - 15] >> 3);
            const std::uint32_t s1 = Rotate(w[i - 2], 17) ^ Rotate(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        std::uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i) {
            const std::uint32_t t1 = hh + (Rotate(e, 6) ^ Rotate(e, 11) ^ Rotate(e, 25)) + ((e & f) ^ (~e & g)) + k[i] + w[i];
            const std::uint32_t t2 = (Rotate(a, 2) ^ Rotate(a, 13) ^ Rotate(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }
    KmrpPack::Key Of(const unsigned char* data, std::size_t size)
    {
        std::size_t at = 0;
        for (; at + 64 <= size; at += 64) Block(data + at);
        unsigned char tail[128] = {};
        const std::size_t left = size - at;
        std::memcpy(tail, data + at, left);
        tail[left] = 0x80;
        const std::size_t blocks = left + 9 > 64 ? 2 : 1;
        const std::uint64_t bits = std::uint64_t(size) * 8;
        for (int i = 0; i < 8; ++i) tail[blocks * 64 - 1 - i] = static_cast<unsigned char>(bits >> (8 * i));
        for (std::size_t i = 0; i < blocks; ++i) Block(tail + 64 * i);
        KmrpPack::Key key;
        for (int i = 0; i < 8; ++i)
            for (int j = 0; j < 4; ++j) key[4 * i + j] = static_cast<unsigned char>(h[i] >> (24 - 8 * j));
        return key;
    }
};

int Fail(const char* what)
{
    std::printf("FAIL %s\n", what);
    return 1;
}
}

int main(int argc, char** argv)
{
    if (argc < 2) return Fail("usage: asset_pack_harness PACK [IDENTITY]");
    std::vector<unsigned char> file;
    if (FILE* in = std::fopen(argv[1], "rb")) {
        unsigned char chunk[1 << 16];
        for (std::size_t got; (got = std::fread(chunk, 1, sizeof chunk, in)) > 0;) file.insert(file.end(), chunk, chunk + got);
        std::fclose(in);
    }
    if (file.size() < KmrpPack::kHeaderSize) return Fail("no pack");
    KmrpPack::Key identity;
    std::uint32_t start;
    if (!KmrpPack::ReadHeader(file.data(), file.size(), identity, start) || start > file.size())
        return Fail("not a pack");
    if (argc > 2 && KmrpPack::IdentityText(identity) != argv[2]) return Fail("the pack is not the identity given");
    // Not what the reader is given, which is only the index; but the identity holds.
    if (Sha256().Of(file.data() + 40, file.size() - 40) != identity) return Fail("the pack does not match its identity");
    KmrpPack::Index index;
    if (!KmrpPack::ReadIndex(file.data(), start, file.size(), index)) return Fail("the index cannot be read");
    std::vector<std::vector<std::pair<KmrpPack::Key, KmrpPack::Object>>> members(index.blocks.size());
    for (const auto& item : index.objects) members[item.second.block].push_back(item);
    double unpacking = 0, unfiltering = 0;
    unsigned long long bytes = 0;
    std::vector<unsigned char> out, object;
    for (std::size_t b = 0; b < index.blocks.size(); ++b) {
        const auto& block = index.blocks[b];
        out.assign(block.size, 0);
        const auto t0 = std::chrono::steady_clock::now();
        if (!KmrpPack::Unpack(block, file.data() + block.offset, out.data())) return Fail("a block does not unpack");
        const auto t1 = std::chrono::steady_clock::now();
        unpacking += std::chrono::duration<double>(t1 - t0).count();
        for (const auto& item : members[b]) {
            object.assign(out.begin() + item.second.offset, out.begin() + item.second.offset + item.second.size);
            const auto t2 = std::chrono::steady_clock::now();
            if (!KmrpPack::Unfilter(item.second.filter, object.data(), object.size())) return Fail("a filter cannot be undone");
            unfiltering += std::chrono::duration<double>(std::chrono::steady_clock::now() - t2).count();
            if (Sha256().Of(object.data(), object.size()) != item.first) {
                std::printf("FAIL block %zu filter %u size %u does not give its file back\n", b,
                            static_cast<unsigned>(item.second.filter), static_cast<unsigned>(item.second.size));
                return 1;
            }
            bytes += object.size();
        }
    }
    unsigned names = 0;
    for (const auto& group : index.groups) names += static_cast<unsigned>(group.entries.size());
    std::printf("%zu groups naming %u files, %zu objects in %zu blocks, %.1f MiB unpacked from %.1f MiB; "
                "LZMA %.2f s, filters %.2f s\nPASS\n",
                index.groups.size(), names, index.objects.size(), index.blocks.size(), bytes / 1048576.0,
                file.size() / 1048576.0, unpacking, unfiltering);
    return 0;
}
