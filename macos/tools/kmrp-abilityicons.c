/*
 * kmrp-abilityicons: enlarge the feat, Force-power and skill icons for KMRP's rows.
 *
 *   kmrp-abilityicons ERF HEIGHT OUTDIR [RESERVED]
 *
 * The Mac port of src/patcher/AbilityIconGenerator.cs, which the Windows installer runs for
 * the resolution it installs. The Abilities screen draws each feat or power icon inside a
 * chain-row slot whose frame grows with the row (50s, macos/patches/kmrp-layout), but the
 * engine draws GUI artwork one texel per pixel, never scaled, so the 32x32 and 64x64 icons
 * stay small in a large frame unless a bigger file is supplied. This writes one: every
 * uncompressed square i_* or ip_* texture in ERF (the game's TexturePacks/swpc_tex_gui.erf),
 * resized to the slot's icon box, round(50s) - 4 with s = max(1, HEIGHT / 720), capped at
 * twice its size, as a 32-bit TGA in OUTDIR. The skill icons (isk_*) grow with their row, the
 * Skills tab's 50s (vanilla's 42): a canvas of round(size * s * 50 / 42), capped the same way,
 * with the picture inside it round(50s * 0.62) on transparent pixels, moved (round(-0.5s *
 * 50 / 42), round(-2s * 50 / 42)) from the centre, so it sits inside the row's frame
 * (lbl_hex_3) rather than on its border (the C#'s SkillPictureOfBox says why). Icons already
 * right for the height are skipped, as are names listed in RESERVED (one file name per line:
 * files KMRP installs itself).
 *
 * Every step mirrors the C#, so the files are byte-identical to what the Windows installer
 * writes for the same height (testing/regression/Test-AbilityIcons.py checks that). They are
 * made from the player's own game files, which is why they are generated, not shipped.
 *
 * Exit status: 0 done (possibly writing nothing), 1 usage or I/O error.
 */
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/* The same rounding as the C# at every step: no fused multiply-add. */
#pragma STDC FP_CONTRACT OFF

enum {
    TPC_HEADER_SIZE = 128,
    ERF_KEY_SIZE = 24,
    ERF_RESOURCE_SIZE = 8,
    RESOURCE_TYPE_TPC = 3007,
    FEAT_ROW_BASE = 50, /* the feat/power chain row group in RowSizeGroups */
    SKILL_ROW_BASE = 50, /* the skills group in RowSizeGroups */
    VANILLA_SKILL_ROW = 42, /* the row the 32 px skill icons were drawn for */
    ICON_INSET = 4,     /* the icon control is the row height minus this */
};

/* AbilityIconGenerator.SkillPictureOfBox, SkillShiftX, SkillShiftY: the skill picture's share
 * of the row's icon box, and its move from the canvas's centre to the frame opening's, in
 * pixels per unit of scale of the vanilla box, so times SKILL_ROW_BASE / VANILLA_SKILL_ROW
 * (the C# says how they were measured). */
static const double SKILL_PICTURE_OF_BOX = 0.62;
static const double SKILL_SHIFT_X = -0.5;
static const double SKILL_SHIFT_Y = -2.0;

static int clamp(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

static uint8_t *pack;
static size_t pack_size;

static int32_t i32(size_t at) { int32_t v; memcpy(&v, pack + at, 4); return v; }
static uint16_t u16(size_t at) { uint16_t v; memcpy(&v, pack + at, 2); return v; }

/* ResolutionPatch.ScaleForHeight: height / 720f, never below 1. */
static float scale_for_height(int height) {
    float scale = (float)height / 720.0f;
    return scale < 1.0f ? 1.0f : scale;
}

/* AbilityIconGenerator.TargetSize: the slot's icon box, capped at 2x the source. */
static int target_size(double scale, int native) {
    int box = (int)nearbyint(FEAT_ROW_BASE * scale) - ICON_INSET;
    if (box <= native) return native;
    return box < native * 2 ? box : native * 2;
}

/* AbilityIconGenerator.SkillTargetSize: grown with the Skills row, capped at 2x the source. */
static int skill_target_size(double scale, int native) {
    int grown = (int)nearbyint(native * scale * SKILL_ROW_BASE / VANILLA_SKILL_ROW);
    if (grown <= native) return native;
    return grown < native * 2 ? grown : native * 2;
}

/* AbilityIconGenerator.SkillPictureSize: the picture inside that canvas, never larger. */
static int skill_picture_size(double scale, int canvas) {
    int picture = (int)nearbyint(SKILL_ROW_BASE * scale * SKILL_PICTURE_OF_BOX);
    return picture < canvas ? picture : canvas;
}

static uint8_t *resize(const uint8_t *pixels, int width, int height, int new_width, int new_height) {
    uint8_t *result = malloc((size_t)new_width * new_height * 4);
    double x_ratio = (double)width / new_width;
    double y_ratio = (double)height / new_height;
    for (int y = 0; y < new_height; y++) {
        /* Sample at pixel centres, as the C# does. */
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

/* Uncompressed 32-bit BGRA TGA, bottom-up, as the game's own. Returns 0 on failure. */
static int write_tga(const char *path, const uint8_t *rgba, int width, int height) {
    uint8_t header[18] = {0};
    header[2] = 2;
    header[12] = width & 0xff; header[13] = (width >> 8) & 0xff;
    header[14] = height & 0xff; header[15] = (height >> 8) & 0xff;
    header[16] = 32;
    header[17] = 0x08;
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    int ok = fwrite(header, 1, 18, f) == 18;
    for (int i = 0; ok && i < width * height; i++) {
        uint8_t bgra[4] = { rgba[i * 4 + 2], rgba[i * 4 + 1], rgba[i * 4], rgba[i * 4 + 3] };
        ok = fwrite(bgra, 1, 4, f) == 4;
    }
    return fclose(f) == 0 && ok;
}

static char **reserved;
static size_t reserved_count;

static void load_reserved(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "kmrp-abilityicons: %s: %s\n", path, strerror(errno)); exit(1); }
    char line[512];
    while (fgets(line, sizeof line, f)) {
        line[strcspn(line, "\r\n")] = 0;
        for (char *p = line; *p; p++) *p = (char)tolower((unsigned char)*p);
        if (!*line) continue;
        reserved = realloc(reserved, (reserved_count + 1) * sizeof *reserved);
        reserved[reserved_count++] = strdup(line);
    }
    fclose(f);
}

static int is_reserved(const char *file) {
    for (size_t i = 0; i < reserved_count; i++)
        if (strcmp(reserved[i], file) == 0) return 1;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) {
        fprintf(stderr, "usage: kmrp-abilityicons ERF HEIGHT OUTDIR [RESERVED]\n");
        return 1;
    }
    int height = atoi(argv[2]);
    if (height < 480) { fprintf(stderr, "kmrp-abilityicons: bad height\n"); return 1; }
    const char *outdir = argv[3];
    if (argc == 5) load_reserved(argv[4]);

    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "kmrp-abilityicons: %s: %s\n", argv[1], strerror(errno)); return 1; }
    fseek(f, 0, SEEK_END);
    pack_size = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    pack = malloc(pack_size);
    if (!pack || fread(pack, 1, pack_size, f) != pack_size) { fprintf(stderr, "kmrp-abilityicons: read failed\n"); return 1; }
    fclose(f);
    if (pack_size < 0x20 || memcmp(pack, "ERF ", 4) != 0) { fprintf(stderr, "kmrp-abilityicons: not an ERF\n"); return 1; }

    const double scale = (double)scale_for_height(height);
    int32_t entries = i32(16), keys = i32(24), resources = i32(28);
    int written = 0;
    mkdir(outdir, 0755);
    for (int32_t i = 0; i < entries; i++) {
        size_t key_at = (size_t)keys + (size_t)i * ERF_KEY_SIZE;
        size_t resource_at = (size_t)resources + (size_t)i * ERF_RESOURCE_SIZE;
        if (key_at + ERF_KEY_SIZE > pack_size || resource_at + ERF_RESOURCE_SIZE > pack_size) break;
        if (u16(key_at + 20) != RESOURCE_TYPE_TPC) continue;

        char name[17] = {0};
        for (int n = 0; n < 16 && pack[key_at + n]; n++) name[n] = (char)tolower(pack[key_at + n]);
        int skill = strncmp(name, "isk_", 4) == 0;
        if (!skill && strncmp(name, "i_", 2) != 0 && strncmp(name, "ip_", 3) != 0) continue;
        char file[32];
        snprintf(file, sizeof file, "%s.tga", name);
        if (is_reserved(file)) continue;

        int32_t offset = i32(resource_at), size = i32(resource_at + 4);
        if (offset < 0 || size < 0 || (size_t)offset + (size_t)size > pack_size) continue;
        if (size < TPC_HEADER_SIZE + 4) continue;

        /* dataSize != 0 is DXT-compressed; icons never are, and anything else is left alone. */
        int32_t data_size = i32((size_t)offset);
        int width = u16((size_t)offset + 8), tex_height = u16((size_t)offset + 10);
        int encoding = pack[offset + 12];
        if (data_size != 0 || width <= 0 || tex_height <= 0 || width != tex_height) continue;
        int channels = encoding == 2 ? 3 : encoding == 4 ? 4 : 0;
        if (!channels) continue;
        if ((int64_t)TPC_HEADER_SIZE + (int64_t)width * tex_height * channels > size) continue;

        int target = skill ? skill_target_size(scale, width) : target_size(scale, width);
        int picture = skill ? skill_picture_size(scale, target) : target;
        if (target == width && picture == width) continue;

        /* TPC rows run bottom-up, and so do the TGA's: no flip. */
        uint8_t *source = malloc((size_t)width * tex_height * 4);
        for (int p = 0; p < width * tex_height; p++) {
            size_t from = (size_t)offset + TPC_HEADER_SIZE + (size_t)p * channels;
            source[p * 4] = pack[from];
            source[p * 4 + 1] = pack[from + 1];
            source[p * 4 + 2] = pack[from + 2];
            source[p * 4 + 3] = channels == 4 ? pack[from + 3] : 255;
        }
        uint8_t *scaled = resize(source, width, tex_height, picture, picture);
        if (picture != target) {
            /* On a transparent canvas of the full size, centred and then moved to the frame
             * opening's centre, as the C# does. Rows are bottom-up. */
            uint8_t *canvas = calloc((size_t)target * target, 4);
            int inset = (target - picture) / 2;
            int left = clamp(inset + (int)nearbyint(SKILL_SHIFT_X * scale * SKILL_ROW_BASE / VANILLA_SKILL_ROW),
                             0, target - picture);
            int top = clamp(inset + (int)nearbyint(SKILL_SHIFT_Y * scale * SKILL_ROW_BASE / VANILLA_SKILL_ROW),
                            0, target - picture);
            int bottom = target - top - picture;
            for (int y = 0; y < picture; y++)
                memcpy(canvas + ((size_t)(y + bottom) * target + left) * 4,
                       scaled + (size_t)y * picture * 4, (size_t)picture * 4);
            free(scaled);
            scaled = canvas;
        }
        char path[4096];
        snprintf(path, sizeof path, "%s/%s", outdir, file);
        if (!write_tga(path, scaled, target, target)) {
            fprintf(stderr, "kmrp-abilityicons: %s: write failed\n", path);
            return 1;
        }
        free(source);
        free(scaled);
        written++;
    }
    printf("%d icons\n", written);
    return 0;
}
