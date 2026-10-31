/*
 * kmrp-gameart: make, from the player's own game, the files KMRP builds from the game's art.
 *
 *   kmrp-gameart ERF KEY HEIGHT OUTDIR
 *
 * The Mac port of src/patcher/GameArtGenerator.cs, which the Windows installer runs for the
 * resolution it installs; the files are byte-identical for the same height and game files
 * (testing/regression/Test-GameArt.py checks that). Until 2026-09-29 the resource build made
 * them from the build machine's copy of the game and every release shipped them. Now nothing
 * of the game's is shipped:
 *
 *   lbl_hex, lbl_hex_3, lbl_hex_6, lbl_hex_7   the hex frames list rows tile behind item
 *                                              icons, at the row's icon box, 56s
 *   tut_*.tga (13)                             the tutorial popup's private icon copies, at
 *                                              its icon rect, 64s
 *   tutorial.2da                               the game's table, its icon column pointed at
 *                                              those copies
 *
 * s = max(1, HEIGHT / 720) in double precision, rounded half to even: the build's sizes.
 * ERF is the game's TexturePacks/swpc_tex_gui.erf; KEY its chitin.key, whose directory the
 * BIF paths are relative to. DXT5 is decoded with the standard formulas in integer arithmetic.
 *
 * All or nothing: OUTDIR is written only when every file was made.
 * Exit status: 0 done, 1 a file could not be read or written, 2 usage.
 */
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kmrp-path.h"
#include "kmrp-2da.h"
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#define strcasecmp _stricmp
#define mkdir(path, mode) _mkdir(path)
#else
#include <strings.h>
#endif

/* The same rounding as the C# at every step: no fused multiply-add. */
#ifndef _MSC_VER
#pragma STDC FP_CONTRACT OFF
#endif

enum { TPC_HEADER = 128, ERF_KEY_SIZE = 24, ERF_RESOURCE_SIZE = 8, TYPE_TPC = 3007, TYPE_2DA = 2017 };
enum { FRAME_BASE = 56, TUTORIAL_ICON_BASE = 64 };

static const char *FRAMES[] = { "lbl_hex", "lbl_hex_3", "lbl_hex_6", "lbl_hex_7" };
static const char *TUTORIAL_ICONS[][2] = {
    { "lbl_icn_abi3", "tut_abi3" },   { "lbl_icn_char3", "tut_char3" }, { "lbl_icn_inv3", "tut_inv3" },
    { "lbl_icn_map3", "tut_map3" },   { "lbl_icn_msg3", "tut_msg3" },   { "i_attack", "tut_attack" },
    { "lbl_icredits", "tut_credits" }, { "lbl_idside", "tut_dside" },   { "lbl_ilside", "tut_lside" },
    { "lbl_iplotxp", "tut_plotxp" },   { "lbl_iquest", "tut_quest" },   { "lbl_ireceive", "tut_receive" },
    { "lbl_itaken", "tut_taken" },
};
#define COUNT(a) (sizeof(a) / sizeof((a)[0]))

typedef struct { uint8_t *data; size_t size; } Buffer;
typedef struct { char name[32]; Buffer file; } Output;

static Output outputs[COUNT(FRAMES) + COUNT(TUTORIAL_ICONS) + 1];
static size_t output_count;

static int fail(const char *what) { fprintf(stderr, "kmrp-gameart: %s\n", what); return 0; }

/* What each file is made from, for the run time to make it again from a mod's copy of its
 * source (K1RuntimeAssets.cpp, DeriveFromOverrideK1): kmrp_derive.txt in OUTDIR, one line a
 * file, added to by every tool that makes files there (kmrp-abilityicons.c too):
 *
 *   OUTPUT \t SOURCE \t CANVAS \t PICTURE \t LEFT \t BOTTOM \t FILTER
 *
 * SOURCE is the game resource OUTPUT was made from, without its extension. For a picture
 * the rest says how: SOURCE drawn PICTURE x PICTURE at LEFT, BOTTOM (from the bottom left)
 * on a transparent CANVAS x CANVAS, "nearest" where PICTURE is a whole multiple of a square
 * source, else "linear". A table or a model has OUTPUT and SOURCE only: its format says
 * how it is merged (kmrp-2da.h for a 2DA). */
static char derivations[8192];
static size_t derivations_length;
static void derived(const char *output, const char *source, int canvas, int picture, int left, int bottom,
                    const char *filter) {
    int n = filter ? snprintf(derivations + derivations_length, sizeof derivations - derivations_length,
                              "%s\t%s\t%d\t%d\t%d\t%d\t%s\n", output, source, canvas, picture, left, bottom, filter)
                   : snprintf(derivations + derivations_length, sizeof derivations - derivations_length,
                              "%s\t%s\n", output, source);
    if (n > 0 && (size_t)n < sizeof derivations - derivations_length) derivations_length += (size_t)n;
}

static Buffer read_file(const char *path) {
    Buffer b = { NULL, 0 };
    FILE *f = kmrp_fopen(path, "rb");
    if (!f) return b;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size > 0 && (b.data = malloc((size_t)size)) && fread(b.data, 1, (size_t)size, f) == (size_t)size)
        b.size = (size_t)size;
    else { free(b.data); b.data = NULL; }
    fclose(f);
    return b;
}

static uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }

/* GameArtGenerator.ScaledSize: the build's rule. */
static int scaled_size(int native, int height) {
    double scale = height / 720.0;
    if (scale < 1.0) scale = 1.0;
    int size = (int)nearbyint(native * scale);
    return size < 1 ? 1 : size;
}

/* ---------------------------------------------------------------- textures */

static void unpack565(int value, int out[3]) {
    int r = (value >> 11) & 0x1F, g = (value >> 5) & 0x3F, b = value & 0x1F;
    out[0] = (r << 3) | (r >> 2);
    out[1] = (g << 2) | (g >> 4);
    out[2] = (b << 3) | (b >> 2);
}

static void dxt5_block(const uint8_t *block, uint8_t *rgba, int width, int height, int left, int top) {
    int alpha[8] = { block[0], block[1] };
    if (alpha[0] > alpha[1]) {
        for (int i = 2; i < 8; i++) alpha[i] = ((8 - i) * alpha[0] + (i - 1) * alpha[1]) / 7;
    } else {
        for (int i = 2; i < 6; i++) alpha[i] = ((6 - i) * alpha[0] + (i - 1) * alpha[1]) / 5;
        alpha[6] = 0;
        alpha[7] = 255;
    }
    uint64_t alpha_bits = 0;
    for (int i = 0; i < 6; i++) alpha_bits |= (uint64_t)block[2 + i] << (8 * i);
    int color[4][3];
    unpack565(u16(block + 8), color[0]);
    unpack565(u16(block + 10), color[1]);
    for (int c = 0; c < 3; c++) {
        color[2][c] = (2 * color[0][c] + color[1][c]) / 3;
        color[3][c] = (color[0][c] + 2 * color[1][c]) / 3;
    }
    uint32_t color_bits = u32(block + 12);
    for (int y = 0; y < 4; y++) {
        for (int x = 0; x < 4; x++) {
            int px = left + x, py = top + y;
            if (px >= width || py >= height) continue;
            int texel = 4 * y + x;
            int ci = (color_bits >> (2 * texel)) & 3, ai = (int)((alpha_bits >> (3 * texel)) & 7);
            uint8_t *o = rgba + ((size_t)py * width + px) * 4;
            o[0] = (uint8_t)color[ci][0]; o[1] = (uint8_t)color[ci][1]; o[2] = (uint8_t)color[ci][2];
            o[3] = (uint8_t)alpha[ai];
        }
    }
}

/* A TPC's top mip as RGBA, rows in stored (bottom-up) order; uncompressed RGB/RGBA or DXT5. */
static uint8_t *decode_tpc(const uint8_t *tpc, size_t size, int *width, int *height) {
    if (size < TPC_HEADER) return NULL;
    uint32_t data_size = u32(tpc);
    int w = u16(tpc + 8), h = u16(tpc + 10), encoding = tpc[12];
    if (w <= 0 || h <= 0) return NULL;
    size_t pixels = (size_t)w * h;
    uint8_t *rgba = malloc(pixels * 4);
    if (!rgba) return NULL;
    if (data_size == 0) {
        int channels = encoding == 2 ? 3 : encoding == 4 ? 4 : 0;
        if (!channels || TPC_HEADER + pixels * channels > size) { free(rgba); return NULL; }
        for (size_t i = 0; i < pixels; i++) {
            const uint8_t *from = tpc + TPC_HEADER + i * channels;
            rgba[i * 4] = from[0]; rgba[i * 4 + 1] = from[1]; rgba[i * 4 + 2] = from[2];
            rgba[i * 4 + 3] = channels == 4 ? from[3] : 255;
        }
    } else {
        int bw = (w + 3) / 4, bh = (h + 3) / 4;
        if (encoding != 4 || data_size != (uint32_t)(bw * bh * 16) || TPC_HEADER + data_size > size) {
            free(rgba); return NULL;
        }
        for (int by = 0; by < bh; by++)
            for (int bx = 0; bx < bw; bx++)
                dxt5_block(tpc + TPC_HEADER + ((size_t)by * bw + bx) * 16, rgba, w, h, bx * 4, by * 4);
    }
    *width = w; *height = h;
    return rgba;
}

#include "../../src/controller-native/K1GuiPreloadData.h"

/* Top mip for the controller preload worker. Decode without calling the engine. */
static uint8_t *preload_tpc(const uint8_t *data, size_t size, int *width, int *height) {
    if (size < 128) return NULL;
    const int w = u16(data + 8), h = u16(data + 10);
    if (w < 1 || h < 1 || w > 8192 || h > 8192) return NULL;
    if (!u32(data) || data[12] == 4) return decode_tpc(data, size, width, height);
    const int bw = (w + 3) / 4, bh = (h + 3) / 4;
    if (data[12] != 2 || (size_t)bw * bh * 8 > size - 128) return NULL;
    uint8_t *rgba = malloc((size_t)w * h * 4);
    if (!rgba) return NULL;
    for (int by = 0; by < bh; ++by) for (int bx = 0; bx < bw; ++bx) {
        const uint8_t *b = data + 128 + ((size_t)by * bw + bx) * 8;
        int color[4][3]; unpack565(u16(b), color[0]); unpack565(u16(b + 2), color[1]);
        const int four = u16(b) > u16(b + 2);
        for (int c = 0; c < 3; ++c) {
            color[2][c] = four ? (2 * color[0][c] + color[1][c]) / 3 : (color[0][c] + color[1][c]) / 2;
            color[3][c] = four ? (color[0][c] + 2 * color[1][c]) / 3 : 0;
        }
        const uint32_t bits = u32(b + 4);
        for (int y = 0; y < 4; ++y) for (int x = 0; x < 4; ++x) {
            const int px = bx * 4 + x, py = by * 4 + y, ci = (bits >> (2 * (y * 4 + x))) & 3;
            if (px >= w || py >= h) continue;
            uint8_t *out = rgba + ((size_t)py * w + px) * 4;
            for (int c = 0; c < 3; ++c) out[c] = (uint8_t)color[ci][c];
            out[3] = !four && ci == 3 ? 0 : 255;
        }
    }
    *width = w; *height = h; return rgba;
}

static uint8_t *preload_tga(const uint8_t *data, size_t size, int *width, int *height) {
    if (size < 18 || data[1] || (data[2] != 2 && data[2] != 10)) return NULL;
    const int w = u16(data + 12), h = u16(data + 14), channels = data[16] / 8;
    if (w < 1 || h < 1 || w > 8192 || h > 8192 || (channels != 3 && channels != 4)) return NULL;
    const size_t count = (size_t)w * h;
    size_t at = 18 + data[0], pixel = 0;
    uint8_t *rgba = malloc(count * 4);
    if (!rgba) return NULL;
    while (pixel < count) {
        int repeated = 0; size_t run = 1;
        if (data[2] == 10) {
            if (at >= size) { free(rgba); return NULL; }
            repeated = data[at] & 128; run = (data[at++] & 127) + 1;
        }
        if (run > count - pixel || at + (repeated ? 1 : run) * channels > size) { free(rgba); return NULL; }
        for (size_t k = 0; k < run; ++k, ++pixel) {
            const uint8_t *p = data + at + (repeated ? 0 : k * channels);
            size_t x = pixel % w, y = pixel / w;
            if (data[17] & 32) y = h - 1 - y;
            if (data[17] & 16) x = w - 1 - x;
            uint8_t *o = rgba + (y * w + x) * 4;
            o[0] = p[2]; o[1] = p[1]; o[2] = p[0]; o[3] = channels == 4 ? p[3] : 255;
        }
        at += (repeated ? 1 : run) * channels;
    }
    *width = w; *height = h; return rgba;
}

unsigned char *KmrpReadPreloadTexture(const char *game, const char *assets, const char *name, int *width, int *height) {
    if (!game || !name || !*name || strlen(name) > 16 || strpbrk(name, "/\\:")) return NULL;
    char path[4096];
    for (int pass = 0; pass < 4; ++pass) {
        const int tga = pass & 1;
        if (pass >= 2 && (!assets || !*assets)) continue;
        if (pass < 2) snprintf(path, sizeof path, "%s/Override/%s.%s", game, name, tga ? "tga" : "tpc");
        else snprintf(path, sizeof path, "%s/%s.%s", assets, name, tga ? "tga" : "tpc");
        FILE *f = kmrp_fopen(path, "rb");
        if (!f) continue;
        fseek(f, 0, SEEK_END); long length = ftell(f); rewind(f);
        uint8_t *data = length > 0 && length <= (64L << 20) ? malloc((size_t)length) : NULL;
        const int read = data && fread(data, 1, (size_t)length, f) == (size_t)length;
        fclose(f);
        uint8_t *rgba = read ? (tga ? preload_tga(data, (size_t)length, width, height)
                                  : preload_tpc(data, (size_t)length, width, height)) : NULL;
        free(data); return rgba; /* Never silently replace a mod's unsupported texture. */
    }
    snprintf(path, sizeof path, "%s/TexturePacks/swpc_tex_gui.erf", game);
    FILE *f = kmrp_fopen(path, "rb");
    if (!f) return NULL;
    uint8_t head[160], key[24], resource[8];
    uint8_t *rgba = NULL;
    if (fread(head, 1, sizeof head, f) != sizeof head) { fclose(f); return NULL; }
    const uint32_t count = u32(head + 16), keys = u32(head + 24), resources = u32(head + 28);
    for (uint32_t i = 0; i < count && i < 100000; ++i) {
        if (fseek(f, (long)keys + (long)i * 24, SEEK_SET) || fread(key, 1, 24, f) != 24) break;
        char ref[17] = {0}; memcpy(ref, key, 16);
        if (u16(key + 20) != TYPE_TPC || strcasecmp(ref, name)) continue;
        const uint32_t id = u32(key + 16);
        if (id >= count || fseek(f, (long)resources + (long)id * 8, SEEK_SET) || fread(resource, 1, 8, f) != 8) break;
        const uint32_t length = u32(resource + 4);
        uint8_t *data = length && length <= (64u << 20) ? malloc(length) : NULL;
        if (data && !fseek(f, (long)u32(resource), SEEK_SET) && fread(data, 1, length, f) == length)
            rgba = preload_tpc(data, length, width, height);
        free(data); break;
    }
    fclose(f); return rgba;
}

static uint8_t *flip_rows(const uint8_t *pixels, int width, int height) {
    size_t stride = (size_t)width * 4;
    uint8_t *out = malloc(stride * height);
    for (int y = 0; y < height; y++) memcpy(out + (size_t)(height - 1 - y) * stride, pixels + (size_t)y * stride, stride);
    return out;
}

static uint8_t *nearest(const uint8_t *pixels, int width, int height, int factor) {
    int nw = width * factor, nh = height * factor;
    uint8_t *out = malloc((size_t)nw * nh * 4);
    for (int y = 0; y < nh; y++)
        for (int x = 0; x < nw; x++)
            memcpy(out + ((size_t)y * nw + x) * 4, pixels + ((size_t)(y / factor) * width + x / factor) * 4, 4);
    return out;
}

/* AbilityIconGenerator.Resize (and kmrp-abilityicons.c, resize_rgba in the build). */
static uint8_t *resize(const uint8_t *pixels, int width, int height, int new_width, int new_height) {
    uint8_t *result = malloc((size_t)new_width * new_height * 4);
    double x_ratio = (double)width / new_width;
    double y_ratio = (double)height / new_height;
    for (int y = 0; y < new_height; y++) {
        double sy = (y + 0.5) * y_ratio - 0.5;
        int y0 = (int)sy;
        if (y0 > height - 1) y0 = height - 1;
        if (y0 < 0) y0 = 0;
        int y1 = y0 + 1 < height - 1 ? y0 + 1 : height - 1;
        double wy = sy - y0;
        if (wy < 0) wy = 0;
        for (int x = 0; x < new_width; x++) {
            double sx = (x + 0.5) * x_ratio - 0.5;
            int x0 = (int)sx;
            if (x0 > width - 1) x0 = width - 1;
            if (x0 < 0) x0 = 0;
            int x1 = x0 + 1 < width - 1 ? x0 + 1 : width - 1;
            double wx = sx - x0;
            if (wx < 0) wx = 0;
            int i00 = (y0 * width + x0) * 4, i01 = (y0 * width + x1) * 4;
            int i10 = (y1 * width + x0) * 4, i11 = (y1 * width + x1) * 4;
            int o = (y * new_width + x) * 4;
            for (int c = 0; c < 4; c++) {
                double top = pixels[i00 + c] * (1 - wx) + pixels[i01 + c] * wx;
                double bottom = pixels[i10 + c] * (1 - wx) + pixels[i11 + c] * wx;
                result[o + c] = (uint8_t)(top * (1 - wy) + bottom * wy + 0.5);
            }
        }
    }
    return result;
}

/* Uncompressed 32-bit BGRA TGA, bottom-up rows given, as the game's own. */
static Buffer tga(const uint8_t *bottom_up, int width, int height) {
    Buffer b;
    b.size = 18 + (size_t)width * height * 4;
    b.data = calloc(1, b.size);
    b.data[2] = 2;
    b.data[12] = width & 0xff; b.data[13] = (width >> 8) & 0xff;
    b.data[14] = height & 0xff; b.data[15] = (height >> 8) & 0xff;
    b.data[16] = 32;
    b.data[17] = 0x08;
    for (size_t i = 0; i < (size_t)width * height; i++) {
        b.data[18 + i * 4] = bottom_up[i * 4 + 2];
        b.data[18 + i * 4 + 1] = bottom_up[i * 4 + 1];
        b.data[18 + i * 4 + 2] = bottom_up[i * 4];
        b.data[18 + i * 4 + 3] = bottom_up[i * 4 + 3];
    }
    return b;
}

/* The first TPC entry of `resref` in the ERF, as the build's exporters took it. */
static int find_tpc(const Buffer *erf, const char *resref, const uint8_t **data, size_t *size) {
    uint32_t entries = u32(erf->data + 16), keys = u32(erf->data + 24), resources = u32(erf->data + 28);
    for (uint32_t i = 0; i < entries; i++) {
        size_t key = keys + (size_t)i * ERF_KEY_SIZE, res = resources + (size_t)i * ERF_RESOURCE_SIZE;
        if (key + ERF_KEY_SIZE > erf->size || res + ERF_RESOURCE_SIZE > erf->size) return 0;
        if (u16(erf->data + key + 20) != TYPE_TPC) continue;
        char name[17] = { 0 };
        memcpy(name, erf->data + key, 16);
        if (strcasecmp(name, resref) != 0) continue;
        uint32_t offset = u32(erf->data + res), length = u32(erf->data + res + 4);
        if ((uint64_t)offset + length > erf->size) return 0;
        *data = erf->data + offset; *size = length;
        return 1;
    }
    return 0;
}

static int add_texture(const Buffer *erf, const char *resref, const char *out_name, int size, int nearest_on_multiples) {
    const uint8_t *tpc; size_t tpc_size;
    if (!find_tpc(erf, resref, &tpc, &tpc_size)) return fail("a texture is missing from the texture pack");
    int w, h;
    uint8_t *bottom_up = decode_tpc(tpc, tpc_size, &w, &h);
    if (!bottom_up) return fail("a texture in the pack is in an unexpected format");
    uint8_t *top_down = flip_rows(bottom_up, w, h);
    uint8_t *scaled = nearest_on_multiples && w == h && size % w == 0
        ? nearest(top_down, w, h, size / w) : resize(top_down, w, h, size, size);
    uint8_t *out_rows = flip_rows(scaled, size, size);
    Output *o = &outputs[output_count++];
    snprintf(o->name, sizeof o->name, "%s.tga", out_name);
    o->file = tga(out_rows, size, size);
    free(bottom_up); free(top_down); free(scaled); free(out_rows);
    derived(o->name, resref, size, size, 0, 0, nearest_on_multiples ? "nearest" : "linear");
    return 1;
}

/* A picture made again from a mod's copy of its source: SOURCE (a .tga or .tpc, in any
 * format the game's own preload reads: uncompressed, RLE, DXT1, DXT5) drawn as a
 * kmrp_derive.txt line says, the same steps as the game's copy, into OUT, an uncompressed
 * TPC when OUT ends in .tpc (so it is found before a mod's .tpc of that name, which the game
 * prefers to a .tga wherever each is), else a TGA. 0 written; 1 SOURCE cannot be read or
 * decoded (the mod's picture is then used as it is); 2 OUT could not be written. */
int KmrpDeriveImage(const char *source, int canvas, int picture, int left, int bottom, const char *filter,
                    const char *out) {
    if (canvas < 1 || canvas > 4096 || picture < 1 || picture > canvas || left < 0 || bottom < 0 ||
        left + picture > canvas || bottom + picture > canvas)
        return 1;
    Buffer file = read_file(source);
    if (!file.data) return 1;
    const size_t length = strlen(source);
    const int from_tpc = length > 4 && strcasecmp(source + length - 4, ".tpc") == 0;
    int w = 0, h = 0;
    uint8_t *bottom_up = from_tpc ? preload_tpc(file.data, file.size, &w, &h) : preload_tga(file.data, file.size, &w, &h);
    float alpha = 0;
    if (from_tpc && file.size >= 8) memcpy(&alpha, file.data + 4, 4);
    free(file.data);
    if (!bottom_up) return 1;
    uint8_t *top_down = flip_rows(bottom_up, w, h);
    uint8_t *scaled = filter && strcmp(filter, "nearest") == 0 && w == h && picture % w == 0
        ? nearest(top_down, w, h, picture / w) : resize(top_down, w, h, picture, picture);
    uint8_t *drawn = calloc((size_t)canvas * canvas, 4);
    const int top = canvas - bottom - picture;
    for (int y = 0; drawn && y < picture; y++)
        memcpy(drawn + ((size_t)(top + y) * canvas + left) * 4, scaled + (size_t)y * picture * 4, (size_t)picture * 4);
    uint8_t *rows = drawn ? flip_rows(drawn, canvas, canvas) : NULL;
    free(bottom_up); free(top_down); free(scaled); free(drawn);
    if (!rows) return 2;
    const size_t out_length = strlen(out);
    Buffer image;
    if (out_length > 4 && strcasecmp(out + out_length - 4, ".tpc") == 0) {
        image.size = TPC_HEADER + (size_t)canvas * canvas * 4;
        image.data = calloc(1, image.size);
        if (image.data) {
            memcpy(image.data + 4, &alpha, 4);
            image.data[8] = canvas & 0xff; image.data[9] = (canvas >> 8) & 0xff;
            image.data[10] = canvas & 0xff; image.data[11] = (canvas >> 8) & 0xff;
            image.data[12] = 4;   /* RGBA, uncompressed (data size 0), one mip */
            image.data[13] = 1;
            memcpy(image.data + TPC_HEADER, rows, (size_t)canvas * canvas * 4);
        }
    } else image = tga(rows, canvas, canvas);
    free(rows);
    if (!image.data) return 2;
    FILE *f = kmrp_fopen(out, "wb");
    int ok = f && fwrite(image.data, 1, image.size, f) == image.size;
    if (f && fclose(f) != 0) ok = 0;
    free(image.data);
    return ok ? 0 : 2;
}

/* ---------------------------------------------------------------- tutorial.2da */

static Buffer keyed_resource(const char *key_path, const char *resref, int type) {
    Buffer none = { NULL, 0 }, key = read_file(key_path);
    if (!key.data || key.size < 24 || memcmp(key.data, "KEY V1  ", 8) != 0) return none;
    uint32_t bif_count = u32(key.data + 8), key_count = u32(key.data + 12);
    uint32_t file_table = u32(key.data + 16), key_table = u32(key.data + 20);
    for (uint32_t i = 0; i < key_count; i++) {
        size_t at = key_table + (size_t)i * 22;
        if (at + 22 > key.size) break;
        char name[17] = { 0 };
        memcpy(name, key.data + at, 16);
        if (strcasecmp(name, resref) != 0 || u16(key.data + at + 16) != type) continue;
        uint32_t id = u32(key.data + at + 18), bif_index = id >> 20, index = id & 0xFFFFF;
        if (bif_index >= bif_count) break;
        size_t entry = file_table + (size_t)bif_index * 12;
        uint32_t name_offset = u32(key.data + entry + 4);
        uint16_t name_length = u16(key.data + entry + 8);
        char bif_path[4096], relative[512] = { 0 };
        if (name_length >= sizeof relative) break;
        memcpy(relative, key.data + name_offset, name_length);
        for (char *p = relative; *p; p++) if (*p == '\\') *p = '/';
        /* Either separator: on Windows the module passes C:\...\chitin.key, and with '/'
           alone the BIF was looked for in the current folder, which is the game's only
           when the game itself runs this. The installer's prebuild of every size
           (2026-10-19) runs elsewhere, so tutorial.2da was never read and nothing was
           made (2026-10-23; kmrp-guiadapt.c and kmrp-swoophud.c had this fix already). */
        const char *slash = strrchr(key_path, '/');
        const char *other = strrchr(key_path, '\\');
        if (other && (!slash || other > slash)) slash = other;
        int dir_length = slash ? (int)(slash - key_path) : 1;
        snprintf(bif_path, sizeof bif_path, "%.*s/%s", dir_length, slash ? key_path : ".", relative);
        Buffer bif = read_file(bif_path);
        free(key.data);
        if (!bif.data || bif.size < 20 || memcmp(bif.data, "BIFFV1  ", 8) != 0) { free(bif.data); return none; }
        uint32_t variable_count = u32(bif.data + 8), variable_table = u32(bif.data + 16);
        size_t record = variable_table + (size_t)index * 16;
        if (index >= variable_count || record + 16 > bif.size || (u32(bif.data + record) & 0xFFFFF) != index) {
            free(bif.data); return none;
        }
        uint32_t offset = u32(bif.data + record + 4), size = u32(bif.data + record + 8);
        if ((uint64_t)offset + size > bif.size) { free(bif.data); return none; }
        Buffer out = { malloc(size ? size : 1), size };
        memcpy(out.data, bif.data + offset, size);
        free(bif.data);
        return out;
    }
    free(key.data);
    return none;
}

/* The game's table, its icon column pointed at the popup's own copies. The table is read and
 * written by kmrp-2da.h, the same code that merges a mod's copy of any table with KMRP's
 * (kmrp-merge.c); what KMRP changes in it is this alone. */
static int add_tutorial_table(const char *key_path) {
    Buffer original = keyed_resource(key_path, "tutorial", TYPE_2DA);
    if (!original.data) return fail("tutorial.2da could not be read through chitin.key");
    Kmrp2da t;
    const int read = kmrp_2da_parse(original.data, original.size, &t) && !t.text;
    free(original.data);
    if (!read) return fail("tutorial.2da is not a binary 2DA");
    const int icon = kmrp_2da_column(&t, "icon");
    if (icon < 0) { kmrp_2da_free(&t); return fail("tutorial.2da has no icon column"); }
    for (int r = 0; r < t.rows; r++) {
        const char *cell = kmrp_2da_cell(&t, r, icon);
        for (size_t i = 0; i < COUNT(TUTORIAL_ICONS); i++)
            if (strcasecmp(cell, TUTORIAL_ICONS[i][0]) == 0) { kmrp_2da_set(&t, r, icon, TUTORIAL_ICONS[i][1]); break; }
    }
    Kmrp2daBytes bytes = kmrp_2da_write(&t);
    kmrp_2da_free(&t);
    if (!bytes.data) return fail("tutorial.2da could not be written");
    Output *o = &outputs[output_count++];
    snprintf(o->name, sizeof o->name, "tutorial.2da");
    o->file.data = bytes.data;
    o->file.size = bytes.size;
    derived("tutorial.2da", "tutorial", 0, 0, 0, 0, NULL);
    return 1;
}

#ifdef KMRP_EMBEDDED
/* Windows standalone module: called once per resolution, in the game process. */
#define main gameart_main
static Buffer embedded_pack;
#define erf embedded_pack
#endif
int main(int argc, char **argv) {
#ifndef KMRP_EMBEDDED
    if (argc == 9 && strcmp(argv[1], "derive") == 0)
        return KmrpDeriveImage(argv[2], atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atoi(argv[6]), argv[7], argv[8]);
#endif
    if (argc != 5) {
        fprintf(stderr, "usage: kmrp-gameart ERF KEY HEIGHT OUTDIR\n"
                        "       kmrp-gameart derive SOURCE CANVAS PICTURE LEFT BOTTOM FILTER OUT\n");
        return 2;
    }
    derivations_length = 0;
    int height = atoi(argv[3]);
    if (height < 480) { fprintf(stderr, "kmrp-gameart: bad height\n"); return 2; }
#ifdef KMRP_EMBEDDED
    erf = read_file(argv[1]);
#else
    Buffer erf = read_file(argv[1]);
#endif
    if (!erf.data || erf.size < 32 || memcmp(erf.data, "ERF ", 4) != 0) { fail("the texture pack could not be read"); return 1; }

    int frame_size = scaled_size(FRAME_BASE, height), icon_size = scaled_size(TUTORIAL_ICON_BASE, height);
    for (size_t i = 0; i < COUNT(FRAMES); i++)
        if (!add_texture(&erf, FRAMES[i], FRAMES[i], frame_size, 0)) return 1;
    for (size_t i = 0; i < COUNT(TUTORIAL_ICONS); i++)
        if (!add_texture(&erf, TUTORIAL_ICONS[i][0], TUTORIAL_ICONS[i][1], icon_size, 1)) return 1;
    if (!add_tutorial_table(argv[2])) return 1;

    kmrp_mkdir(argv[4]);
    for (size_t i = 0; i < output_count; i++) {
        char path[4096];
        snprintf(path, sizeof path, "%s/%s", argv[4], outputs[i].name);
        FILE *f = kmrp_fopen(path, "wb");
        if (!f || fwrite(outputs[i].file.data, 1, outputs[i].file.size, f) != outputs[i].file.size) {
            fprintf(stderr, "kmrp-gameart: %s: %s\n", path, strerror(errno));
            if (f) fclose(f);
            return 1;
        }
        if (fclose(f) != 0) { fprintf(stderr, "kmrp-gameart: %s: write failed\n", path); return 1; }
    }
    char path[4096];
    snprintf(path, sizeof path, "%s/kmrp_derive.txt", argv[4]);
    FILE *f = kmrp_fopen(path, "ab");
    if (!f || fwrite(derivations, 1, derivations_length, f) != derivations_length || fclose(f) != 0) {
        fprintf(stderr, "kmrp-gameart: %s: write failed\n", path);
        return 1;
    }
    printf("%zu files (%d px frames, %d px tutorial icons)\n", output_count, frame_size, icon_size);
    return 0;
}

#ifdef KMRP_EMBEDDED
#undef erf
int KmrpGameArt(const char *erf, const char *key, unsigned height, const char *outdir) {
    char text[16];
    snprintf(text, sizeof text, "%u", height);
    char *args[] = { "kmrp-gameart", (char *)erf, (char *)key, text, (char *)outdir };
    for (size_t i = 0; i < output_count; i++) free(outputs[i].file.data);
    output_count = 0;
    int result = gameart_main(5, args);
    /* The command-line tool exits after one run; here the pack is 100 MB per call. */
    free(embedded_pack.data); embedded_pack.data = NULL; embedded_pack.size = 0;
    return result;
}
#endif
