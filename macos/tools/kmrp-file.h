/* A whole file in memory and little-endian reads, for the tools that take the game's files
 * apart (kmrp-gameart.c, kmrp-guiadapt.c, kmrp-swoophud.c; audit S-8). Included after
 * kmrp-path.h and the C library's headers. A tool may define KMRP_FILE_LIMIT first as the
 * size it refuses from.
 *
 * kmrp-guiblend.c and kmrp-macho.c keep readers of their own, as they differ on purpose:
 * they stop the tool on a failure, and the first terminates the data. */
#ifndef KMRP_FILE_H
#define KMRP_FILE_H

#ifndef KMRP_FILE_LIMIT
#define KMRP_FILE_LIMIT 0x7FFFFFFFL
#endif

typedef struct { uint8_t *data; size_t size; } Buffer;

static inline uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static inline uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }

static inline Buffer read_file(const char *path) {
    Buffer b = { NULL, 0 };
    FILE *f = kmrp_fopen(path, "rb");
    if (!f) return b;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size > 0 && size < KMRP_FILE_LIMIT && (b.data = malloc((size_t)size)) &&
        fread(b.data, 1, (size_t)size, f) == (size_t)size)
        b.size = (size_t)size;
    else { free(b.data); b.data = NULL; }
    fclose(f);
    return b;
}

#endif
