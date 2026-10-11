// The x86 half of Test-Xpress.py: decodes each vector of the file it is given with the
// modules' own decoder (src/controller-native/K1Xpress.cpp) and holds the result
// against the vector's SHA-256. A vector is its decoded size and stored size as 32
// bits each, the SHA-256 of the decoded bytes, then the stored bytes. Each small
// vector is also decoded cut short and with bytes changed, which must not read or
// write outside its buffers (the output sits against a guard page).
//
// Documentation standard: see `docs/documentation-standard.md`.
#include "../../src/controller-native/K1Xpress.h"
#include <windows.h>
#include <bcrypt.h>
#include <cstdio>
#include <cstring>
#include <vector>

static bool Sha(const unsigned char* data, std::size_t size, unsigned char* out)
{
    BCRYPT_ALG_HANDLE algorithm = nullptr; BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0 &&
        BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
        BCryptHashData(hash, const_cast<PUCHAR>(data), static_cast<ULONG>(size), 0) >= 0 &&
        BCryptFinishHash(hash, out, 32, 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
}

// `size` writable bytes that end where an inaccessible page begins.
struct Guarded {
    unsigned char* base = nullptr;
    unsigned char* data = nullptr;
    explicit Guarded(std::size_t size)
    {
        const std::size_t page = 4096, pages = (size + page - 1) / page;
        base = static_cast<unsigned char*>(VirtualAlloc(nullptr, (pages + 1) * page, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
        if (!base) return;
        DWORD old;
        VirtualProtect(base + pages * page, page, PAGE_NOACCESS, &old);
        data = base + pages * page - size;
    }
    ~Guarded() { if (base) VirtualFree(base, 0, MEM_RELEASE); }
};

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    FILE* file = nullptr;
    if (fopen_s(&file, argv[1], "rb") || !file) return 2;
    unsigned count = 0, wrong = 0, hostile = 0, accepted = 0;
    unsigned long long decoded = 0;
    LARGE_INTEGER frequency, started, now;
    QueryPerformanceFrequency(&frequency);
    double seconds = 0;
    unsigned head[2];
    unsigned char key[32], measured[32];
    while (fread(head, 4, 2, file) == 2 && fread(key, 1, 32, file) == 32) {
        std::vector<unsigned char> packed(head[1]);
        if (head[1] && fread(packed.data(), 1, head[1], file) != head[1]) return 2;
        std::vector<unsigned char> out(head[0]);
        QueryPerformanceCounter(&started);
        const bool ok = KmrpXpressDecode(packed.data(), packed.size(), out.data(), out.size());
        QueryPerformanceCounter(&now);
        seconds += static_cast<double>(now.QuadPart - started.QuadPart) / frequency.QuadPart;
        ++count; decoded += head[0];
        if (!ok || !Sha(out.data(), out.size(), measured) || std::memcmp(measured, key, 32)) {
            ++wrong;
            if (wrong <= 5) std::printf("wrong: vector %u, %u bytes from %u\n", count, head[0], head[1]);
        }
        if (head[0] > 300000 || head[1] < 30) continue;
        // Hostile input: the same stream cut short, then with one byte changed at a
        // time. Either may fail; neither may leave its buffers.
        Guarded in(packed.size()), guarded(out.size());
        if (!in.data || !guarded.data) return 2;
        for (std::size_t cut = packed.size() - 1; cut > 24; cut = cut * 3 / 4) {
            unsigned char* at = in.data + packed.size() - cut;
            std::memcpy(at, packed.data(), cut);
            if (KmrpXpressDecode(at, cut, guarded.data, out.size())) ++accepted;
            ++hostile;
        }
        std::memcpy(in.data, packed.data(), packed.size());
        unsigned seed = count * 2654435761u;
        for (int round = 0; round < 24; ++round) {
            seed = seed * 1664525u + 1013904223u;
            const std::size_t at = 24 + (seed >> 8) % (packed.size() - 24);
            const unsigned char held = in.data[at];
            in.data[at] = static_cast<unsigned char>(held ^ (1u << (seed & 7)) ^ (seed >> 28));
            KmrpXpressDecode(in.data, packed.size(), guarded.data, out.size());
            in.data[at] = held;
            ++hostile;
        }
    }
    fclose(file);
    std::printf("%u vectors, %llu bytes decoded in %.2f s, %u wrong; %u hostile streams survived, %u cut streams accepted\n",
                count, decoded, seconds, wrong, hostile, accepted);
    return wrong || accepted || !count ? 1 : 0;
}
