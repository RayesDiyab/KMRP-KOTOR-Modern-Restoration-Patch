/* kmrp-gameart.c when memory runs out and when chitin.key lies. Test-GameArtFailure.py builds
 * this for x86, as the module is, and gives it an empty folder. Every allocation is made to
 * fail in turn; a bad key must be refused, and a good one still read. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static long allocations = 0, failing = -1;
static void *counted_malloc(size_t size)
{
    return ++allocations == failing ? NULL : malloc(size);
}
static void *counted_calloc(size_t count, size_t size)
{
    return ++allocations == failing ? NULL : calloc(count, size);
}
#define malloc counted_malloc
#define calloc counted_calloc
#define KMRP_EMBEDDED
#include "../../macos/tools/kmrp-gameart.c"
#undef malloc
#undef calloc
#undef main

static int failures = 0;
static void check(int ok, const char *what)
{
    printf("%s %s\n", ok ? "ok  " : "FAIL", what);
    if (!ok) ++failures;
}
static void put32(uint8_t *at, uint32_t value) { memcpy(at, &value, 4); }
static void put16(uint8_t *at, uint16_t value) { memcpy(at, &value, 2); }
static void write_bytes(const char *path, const void *data, size_t size)
{
    FILE *f = fopen(path, "wb");
    fwrite(data, 1, size, f);
    fclose(f);
}

/* A key of one BIF and one resource, with what is given where it says. */
static void write_key(const char *path, uint32_t file_table, uint32_t name_offset, uint16_t name_length)
{
    uint8_t key[80] = { 0 };
    memcpy(key, "KEY V1  ", 8);
    put32(key + 8, 1); put32(key + 12, 1);
    put32(key + 16, file_table); put32(key + 20, 36);
    put32(key + 24 + 4, name_offset); put16(key + 24 + 8, name_length);
    memcpy(key + 36, "tutorial", 8);
    put16(key + 36 + 16, TYPE_2DA);
    put32(key + 36 + 18, 0);
    memcpy(key + 70, "x.bif", 5);
    write_bytes(path, key, sizeof key);
}

int main(int argc, char **argv)
{
    char source[600], out[600], keyPath[600], bifPath[600];
    if (argc != 2) return 2;
    snprintf(source, sizeof source, "%s/source.tga", argv[1]);
    snprintf(out, sizeof out, "%s/out.tga", argv[1]);
    snprintf(keyPath, sizeof keyPath, "%s/chitin.key", argv[1]);
    snprintf(bifPath, sizeof bifPath, "%s/x.bif", argv[1]);

    uint8_t tgaFile[18 + 8 * 8 * 4] = { 0 };
    tgaFile[2] = 2; tgaFile[12] = 8; tgaFile[14] = 8; tgaFile[16] = 32; tgaFile[17] = 8;
    for (size_t i = 18; i < sizeof tgaFile; ++i) tgaFile[i] = (uint8_t)i;
    write_bytes(source, tgaFile, sizeof tgaFile);

    const char *filters[] = { "linear", "nearest" };
    for (int f = 0; f < 2; ++f) {
        failing = -1; allocations = 0;
        const int whole = KmrpDeriveImage(source, 64, 48 - 16 * f, 0, 0, filters[f], out);
        const long used = allocations;
        check(whole == 0 && used >= 6, f ? "nearest: made, with memory" : "linear: made, with memory");
        int bad = 0;
        for (long n = 1; n <= used; ++n) {
            failing = n; allocations = 0;
            const int result = KmrpDeriveImage(source, 64, 48 - 16 * f, 0, 0, filters[f], out);
            if (result != 1 && result != 2) ++bad;
        }
        failing = -1;
        printf("     %ld allocations failed in turn\n", used);
        check(!bad, "each failed allocation is answered, with no crash");
    }

    /* A good key and BIF: the reader still reads. */
    uint8_t bif[40] = { 0 };
    memcpy(bif, "BIFFV1  ", 8);
    put32(bif + 8, 1); put32(bif + 16, 20);
    put32(bif + 20 + 4, 36); put32(bif + 20 + 8, 4);
    memcpy(bif + 36, "abcd", 4);
    write_bytes(bifPath, bif, sizeof bif);
    write_key(keyPath, 24, 70, 5);
    Buffer good = keyed_file(keyPath, "tutorial", TYPE_2DA);
    check(good.data && good.size == 4 && !memcmp(good.data, "abcd", 4), "a good key still reads its resource");
    free(good.data);
    /* And a bad one is refused: these read far outside the file until 2026-11-01 (GUI-7). */
    write_key(keyPath, 24, 0x7FFFFFF0u, 5);
    check(!keyed_file(keyPath, "tutorial", TYPE_2DA).data, "a BIF name outside the key is refused");
    write_key(keyPath, 0x7FFFFF00u, 70, 5);
    check(!keyed_file(keyPath, "tutorial", TYPE_2DA).data, "a file table outside the key is refused");
    write_key(keyPath, 0xFFFFFFF8u, 70, 5);
    check(!keyed_file(keyPath, "tutorial", TYPE_2DA).data, "a file table that wraps a 32-bit sum is refused");

    printf("%d failed\n", failures);
    return failures ? 1 : 0;
}
