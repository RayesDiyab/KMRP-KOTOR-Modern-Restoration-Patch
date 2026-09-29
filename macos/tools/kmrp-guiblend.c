/*
 * kmrp-guiblend: derive KMRP's GUI set for a resolution the build has no set for.
 *
 *   kmrp-guiblend TABLE WIDTH HEIGHT OUTDIR     writes every .gui for WIDTHxHEIGHT
 *   kmrp-guiblend TABLE WIDTH HEIGHT            prints the sets it would blend, writes nothing
 *
 * TABLE is gui-blend.bin from tools/build_gui_blend_table.py: per .gui file a template, the
 * numeric fields that vary between resolutions, and their values in each finished set the
 * build made. This does the blend tools/derive_resolution_gui_set.py does on upstream: the
 * two aspect-ratio families on either side of WIDTH/HEIGHT, each at the two heights around
 * HEIGHT, weighted and rounded once (half away from zero). It interpolates numbers the build
 * made; KMRP's layout logic stays in the build. Every step mirrors the Python, so the output
 * is byte-identical to it (testing/regression/Test-GuiBlendHelper.py checks that).
 *
 * Exit status: 0 written, 1 usage or I/O error, 2 resolution outside the anchors' range.
 */
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/* Byte-identical to the Python blend means the same rounding at every step: no fused
 * multiply-add, which clang emits by default on arm64 and which rounds exact .5 ties
 * differently (7 files differed before this, 2026-09-29). */
#pragma STDC FP_CONTRACT OFF

typedef struct { uint32_t width, height, family; } Anchor;
typedef struct { int index; double weight; } Term;

static uint8_t *table;
static size_t table_size, pos;

static int take(void *out, size_t n) {
    if (pos + n > table_size) return 0;
    memcpy(out, table + pos, n);
    pos += n;
    return 1;
}

static uint32_t take_u32(void) {
    uint32_t v = 0;
    if (!take(&v, 4)) { fprintf(stderr, "kmrp-guiblend: table truncated\n"); exit(1); }
    return v;
}

static double round_half_away(double v) {
    return copysign(floor(fabs(v) + 0.5), v);
}

/* The family at `height`: one set, or the two around it with their weights. Among sets of
 * the same height, the one nearest the family's aspect ratio (1360x768 against 1366x768). */
static int family_at_height(const Anchor *anchors, uint32_t count, uint32_t family, double aspect,
                            uint32_t height, Term out[2], double *width_there) {
    int best_below = -1, best_above = -1, exact = -1;
    for (uint32_t i = 0; i < count; i++) {
        const Anchor *a = &anchors[i];
        if (a->family != family) continue;
        double off = fabs((double)a->width / a->height - aspect);
        if (a->height == height) {
            if (exact < 0 || off < fabs((double)anchors[exact].width / anchors[exact].height - aspect))
                exact = (int)i;
        } else if (a->height < height) {
            if (best_below < 0 || a->height > anchors[best_below].height ||
                (a->height == anchors[best_below].height &&
                 off < fabs((double)anchors[best_below].width / anchors[best_below].height - aspect)))
                best_below = (int)i;
        } else {
            if (best_above < 0 || a->height < anchors[best_above].height ||
                (a->height == anchors[best_above].height &&
                 off < fabs((double)anchors[best_above].width / anchors[best_above].height - aspect)))
                best_above = (int)i;
        }
    }
    if (exact >= 0) {
        out[0].index = exact; out[0].weight = 1.0;
        *width_there = anchors[exact].width;
        return 1;
    }
    if (best_below < 0 || best_above < 0) return 0;
    const Anchor *lo = &anchors[best_below], *hi = &anchors[best_above];
    double t = ((double)height - lo->height) / ((double)hi->height - lo->height);
    out[0].index = best_below; out[0].weight = 1.0 - t;
    out[1].index = best_above; out[1].weight = t;
    *width_there = lo->width + ((double)hi->width - lo->width) * t;
    return 2;
}

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) {
        fprintf(stderr, "usage: kmrp-guiblend TABLE WIDTH HEIGHT [OUTDIR]\n");
        return 1;
    }
    uint32_t width = (uint32_t)strtoul(argv[2], NULL, 10);
    uint32_t height = (uint32_t)strtoul(argv[3], NULL, 10);
    if (width < 640 || height < 480) { fprintf(stderr, "kmrp-guiblend: bad resolution\n"); return 1; }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "kmrp-guiblend: %s: %s\n", argv[1], strerror(errno)); return 1; }
    fseek(f, 0, SEEK_END);
    table_size = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    table = malloc(table_size);
    if (!table || fread(table, 1, table_size, f) != table_size) { fprintf(stderr, "kmrp-guiblend: read failed\n"); return 1; }
    fclose(f);

    char magic[4];
    if (!take(magic, 4) || memcmp(magic, "KGBL", 4) != 0 || take_u32() != 1) {
        fprintf(stderr, "kmrp-guiblend: not a version 1 blend table\n");
        return 1;
    }
    uint32_t family_count = take_u32();
    double aspects[16];
    if (family_count == 0 || family_count > 16) { fprintf(stderr, "kmrp-guiblend: bad family count\n"); return 1; }
    for (uint32_t i = 0; i < family_count; i++) take(&aspects[i], 8);
    uint32_t anchor_count = take_u32();
    Anchor *anchors = calloc(anchor_count, sizeof *anchors);
    for (uint32_t i = 0; i < anchor_count; i++) {
        anchors[i].width = take_u32();
        anchors[i].height = take_u32();
        anchors[i].family = take_u32();
    }

    /* Families in order of aspect ratio. */
    uint32_t order[16];
    for (uint32_t i = 0; i < family_count; i++) order[i] = i;
    for (uint32_t i = 1; i < family_count; i++)
        for (uint32_t j = i; j > 0 && aspects[order[j]] < aspects[order[j - 1]]; j--) {
            uint32_t t = order[j]; order[j] = order[j - 1]; order[j - 1] = t;
        }

    double aspect = (double)width / height;
    Term terms[4];
    int term_count = 0;
    int same = -1;
    for (uint32_t i = 0; i < family_count; i++)
        if (fabs(aspects[order[i]] - aspect) < 0.005) { same = (int)order[i]; break; }
    if (same >= 0) {
        double w;
        term_count = family_at_height(anchors, anchor_count, (uint32_t)same, aspects[same], height, terms, &w);
    } else {
        int lower = -1, upper = -1;
        for (uint32_t i = 0; i < family_count; i++) {
            if (aspects[order[i]] < aspect) lower = (int)order[i];
            else if (aspects[order[i]] > aspect && upper < 0) upper = (int)order[i];
        }
        Term a[2], b[2];
        double wa = 0, wb = 0;
        int na = lower >= 0 ? family_at_height(anchors, anchor_count, (uint32_t)lower, aspects[lower], height, a, &wa) : 0;
        int nb = upper >= 0 ? family_at_height(anchors, anchor_count, (uint32_t)upper, aspects[upper], height, b, &wb) : 0;
        if (na && nb) {
            double s = ((double)width - wa) / (wb - wa);
            for (int i = 0; i < na; i++) { terms[term_count] = a[i]; terms[term_count++].weight *= 1.0 - s; }
            for (int i = 0; i < nb; i++) { terms[term_count] = b[i]; terms[term_count++].weight *= s; }
        }
    }
    /* Drop terms with no weight, as the Python does (weight > 1e-9). */
    int kept = 0;
    for (int i = 0; i < term_count; i++)
        if (terms[i].weight > 1e-9) terms[kept++] = terms[i];
    term_count = kept;
    if (term_count == 0) {
        fprintf(stderr, "kmrp-guiblend: %ux%u is outside the resolutions the sets cover\n", width, height);
        return 2;
    }
    for (int i = 0; i < term_count; i++)
        printf("%ux%u %.6f\n", anchors[terms[i].index].width, anchors[terms[i].index].height, terms[i].weight);
    if (argc == 4) return 0;

    const char *outdir = argv[4];
    mkdir(outdir, 0755);
    uint32_t file_count = take_u32();
    for (uint32_t fi = 0; fi < file_count; fi++) {
        uint16_t name_len = 0;
        take(&name_len, 2);
        char name[256];
        if (name_len == 0 || name_len >= sizeof name || !take(name, name_len)) { fprintf(stderr, "kmrp-guiblend: bad file name\n"); return 1; }
        name[name_len] = 0;
        if (strchr(name, '/') || strchr(name, '\\')) { fprintf(stderr, "kmrp-guiblend: bad file name %s\n", name); return 1; }
        uint32_t size = take_u32();
        if (pos + size > table_size) { fprintf(stderr, "kmrp-guiblend: table truncated\n"); return 1; }
        uint8_t *out = malloc(size);
        memcpy(out, table + pos, size);
        pos += size;
        uint32_t slots = take_u32();
        uint32_t *offsets = malloc(slots * sizeof *offsets);
        for (uint32_t s = 0; s < slots; s++) {
            offsets[s] = take_u32();
            if (take_u32() != 5 || offsets[s] + 4 > size) { fprintf(stderr, "kmrp-guiblend: %s: unsupported field\n", name); return 1; }
        }
        const uint8_t *values = table + pos;
        if (pos + (size_t)anchor_count * slots * 4 > table_size) { fprintf(stderr, "kmrp-guiblend: table truncated\n"); return 1; }
        pos += (size_t)anchor_count * slots * 4;
        for (uint32_t s = 0; s < slots; s++) {
            double sum = 0.0;
            for (int t = 0; t < term_count; t++) {
                int32_t v;
                memcpy(&v, values + ((size_t)terms[t].index * slots + s) * 4, 4);
                sum += v * terms[t].weight;
            }
            int32_t blended = (int32_t)round_half_away(sum);
            memcpy(out + offsets[s], &blended, 4);
        }
        char path[4096];
        snprintf(path, sizeof path, "%s/%s", outdir, name);
        FILE *o = fopen(path, "wb");
        if (!o || fwrite(out, 1, size, o) != size || fclose(o) != 0) { fprintf(stderr, "kmrp-guiblend: %s: write failed\n", path); return 1; }
        free(out);
        free(offsets);
    }
    return 0;
}
