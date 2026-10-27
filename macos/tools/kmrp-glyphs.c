/*
 * kmrp-glyphs: the controller button pictures drawn from their outlines (issue 68). See
 * kmrp-glyphs.h. Moved here from kmrp-guiblend.c on 2026-10-27, unchanged but for its names
 * and the reader's input, so the controller module draws with the same code.
 */
#include "kmrp-glyphs.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Byte-identical to the Python means the same rounding at every step (kmrp-guiblend.c). */
#ifndef _MSC_VER
#pragma STDC FP_CONTRACT OFF
#endif

#define GLYPH_SS 8
#define GLYPH_SUB 2048
#define GLYPH_SAMPLE (GLYPH_SUB / GLYPH_SS)
#define GLYPH_FULL ((int64_t)GLYPH_SS * GLYPH_SS * 65025)

static int64_t floor_div(int64_t a, int64_t b) {   /* Python's //, for either sign of b */
    int64_t q = a / b;
    return (a % b != 0 && (a < 0) != (b < 0)) ? q - 1 : q;
}

static int64_t isqrt64(int64_t n) {
    int64_t r = (int64_t)sqrt((double)n);
    while (r > 0 && r * r > n) r--;
    while ((r + 1) * (r + 1) <= n) r++;
    return r;
}

/* A paint's colour at glyph point (xa, ya). */
static void glyph_paint(const KmrpGlyphItem *it, int64_t xa, int64_t ya, int64_t out[4]) {
    if (it->kind == 0) {
        for (int c = 0; c < 4; c++) out[c] = it->rgba[c];
        return;
    }
    int64_t tt;
    if (it->kind == 1) {
        tt = floor_div(it->coef[0] * xa + it->coef[1] * ya + it->coef[2], 65536);
    } else {
        int64_t u = floor_div(it->coef[0] * xa + it->coef[1] * ya + it->coef[2], 65536);
        int64_t v = floor_div(it->coef[3] * xa + it->coef[4] * ya + it->coef[5], 65536);
        tt = isqrt64(u * u + v * v);
    }
    if (tt < 0) tt = 0;
    if (tt > 65536) tt = 65536;
    for (int c = 0; c < 4; c++) out[c] = it->stop_rgba[0][c];
    for (uint32_t s = 0; s + 1 < it->stop_count; s++) {
        int64_t p0 = it->stop_at[s], p1 = it->stop_at[s + 1];
        if (p1 > p0 && tt >= p0)
            for (int c = 0; c < 4; c++) {
                int64_t c0 = it->stop_rgba[s][c], c1 = it->stop_rgba[s + 1][c];
                out[c] = c0 + floor_div((c1 - c0) * (tt - p0) * 2 + (p1 - p0), 2 * (p1 - p0));
            }
        if (tt >= p1)
            for (int c = 0; c < 4; c++) out[c] = it->stop_rgba[s + 1][c];
    }
}

/* A glyph drawn into a dw x dh rectangle: per pixel the sums of its 64 samples' P (three
 * channels) and Q, before any backing. The drawing is the same at every whole-pixel
 * position, so a run keeps its latest drawings, up to GLYPH_CACHE of them and GLYPH_BUDGET
 * bytes (the helper also runs inside the 32-bit game): the same glyph comes up at the same
 * size on many buttons of a set (about 950 textures). */
typedef struct { const KmrpGlyph *glyph; int dw, dh; int64_t *sums; size_t bytes; } GlyphTile;
#define GLYPH_CACHE 256
#define GLYPH_BUDGET ((size_t)8 << 20)
static GlyphTile glyph_cache[GLYPH_CACHE];
static int glyph_cache_count, glyph_cache_next;
static size_t glyph_cache_bytes;

/* Forgets every kept drawing: the blend helper calls it as a run starts, since its embedded
 * build frees all of a run's memory when the run ends. */
KMRP_GLYPHS_API void kmrp_glyph_cache_reset(void) {
    glyph_cache_count = glyph_cache_next = 0;
    glyph_cache_bytes = 0;
}

static const int64_t *glyph_tile(const KmrpGlyph *g, int dw, int dh) {
    for (int j = 1; j <= glyph_cache_count; j++) {   /* the kept ones, newest first */
        const GlyphTile *kept = &glyph_cache[(glyph_cache_next + GLYPH_CACHE - j) % GLYPH_CACHE];
        if (kept->glyph == g && kept->dw == dw && kept->dh == dh)
            return kept->sums;
    }
    const int rows = dh * GLYPH_SS, cols = dw * GLYPH_SS;
    const int64_t W = g->width, H = g->height;
    int32_t *P = calloc((size_t)rows * cols * 3, sizeof(int32_t));
    int32_t *Q = calloc((size_t)rows * cols, sizeof(int32_t));
    int32_t *diff = malloc(sizeof(int32_t) * (size_t)rows * (cols + 1));
    int32_t *paint = malloc(sizeof(int32_t) * (size_t)dw * dh * 4);
    int64_t *edge = NULL;
    uint32_t edge_room = 0;
    for (uint32_t i = 0; i < g->item_count; i++) {
        const KmrpGlyphItem *it = &g->items[i];
        if (it->edge_count > edge_room) {
            free(edge);
            edge_room = it->edge_count;
            edge = malloc(sizeof(int64_t) * 4 * edge_room);
        }
        /* The edges in sample units, once; the rows each crosses, and the item's box. */
        int r_lo = rows, r_hi = -1;
        int64_t x_lo = INT64_MAX, x_hi = INT64_MIN;
        uint32_t n = 0;
        for (uint32_t e = 0; e < it->edge_count; e++) {
            const int32_t *ed = &it->edges[e * 4];
            int64_t *q = &edge[n * 4];
            q[0] = floor_div((int64_t)ed[0] * dw * GLYPH_SUB, W);
            q[1] = floor_div((int64_t)ed[1] * dh * GLYPH_SUB, H);
            q[2] = floor_div((int64_t)ed[2] * dw * GLYPH_SUB, W);
            q[3] = floor_div((int64_t)ed[3] * dh * GLYPH_SUB, H);
            if (q[1] == q[3]) continue;
            n++;
        }
        memset(diff, 0, sizeof(int32_t) * (size_t)rows * (cols + 1));
        for (uint32_t e = 0; e < n; e++) {
            const int64_t x0 = edge[e * 4], y0 = edge[e * 4 + 1], x1 = edge[e * 4 + 2], y1 = edge[e * 4 + 3];
            const int64_t lo = y0 < y1 ? y0 : y1, hi = y0 < y1 ? y1 : y0;
            /* the sample rows with lo <= sy < hi, sy = r * GLYPH_SAMPLE + GLYPH_SAMPLE / 2 */
            int64_t first = -floor_div(GLYPH_SAMPLE / 2 - lo, GLYPH_SAMPLE);
            int64_t last = -floor_div(GLYPH_SAMPLE / 2 - hi, GLYPH_SAMPLE) - 1;
            if (first < 0) first = 0;
            if (last > rows - 1) last = rows - 1;
            const int32_t dir = y1 > y0 ? 1 : -1;
            for (int64_t r = first; r <= last; r++) {
                const int64_t sy = r * GLYPH_SAMPLE + GLYPH_SAMPLE / 2;
                const int64_t xc = x0 + floor_div((x1 - x0) * (sy - y0), y1 - y0);
                int64_t k = -floor_div(GLYPH_SAMPLE / 2 - xc, GLYPH_SAMPLE);
                if (k < 0) k = 0;
                if (k > cols) k = cols;
                diff[(size_t)r * (cols + 1) + k] += dir;
                if (k < x_lo) x_lo = k;
                if (k > x_hi) x_hi = k;
            }
            if (first <= last) {
                if (first < r_lo) r_lo = (int)first;
                if (last > r_hi) r_hi = (int)last;
            }
        }
        if (r_hi < r_lo) continue;
        if (x_hi > cols) x_hi = cols;
        /* The paint, for the pixels the item can cover: one colour, or a gradient's. */
        const int px_lo = (int)(x_lo / GLYPH_SS), px_hi = (int)((x_hi - 1) / GLYPH_SS);
        const int py_lo = r_lo / GLYPH_SS, py_hi = r_hi / GLYPH_SS;
        if (it->kind != 0)
            for (int py = py_lo; py <= py_hi; py++)
                for (int px = px_lo; px <= px_hi && px < dw; px++) {
                    int64_t c[4];
                    glyph_paint(it, ((2 * (int64_t)px + 1) * W) / (2 * (int64_t)dw),
                                ((2 * (int64_t)py + 1) * H) / (2 * (int64_t)dh), c);
                    for (int k = 0; k < 4; k++) paint[((size_t)py * dw + px) * 4 + k] = (int32_t)c[k];
                }
        for (int r = r_lo; r <= r_hi; r++) {
            const int32_t *d = &diff[(size_t)r * (cols + 1)];
            int32_t winding = 0;
            for (int s = (int)x_lo; s < (int)x_hi; s++) {
                winding += d[s];
                if (it->rule ? (winding & 1) == 0 : winding == 0) continue;
                int32_t c[4];
                if (it->kind == 0) {
                    for (int k = 0; k < 4; k++) c[k] = it->rgba[k];
                } else {
                    memcpy(c, &paint[((size_t)(r / GLYPH_SS) * dw + s / GLYPH_SS) * 4], sizeof c);
                }
                const int32_t a = c[3], inv = 255 - a;
                int32_t *ps = &P[((size_t)r * cols + s) * 3], *qs = &Q[(size_t)r * cols + s];
                for (int k = 0; k < 3; k++) ps[k] = c[k] * a + (ps[k] * inv + 127) / 255;
                *qs = 255 * a + (*qs * inv + 127) / 255;
            }
        }
    }
    int64_t *sums = malloc(sizeof(int64_t) * 4 * (size_t)dw * dh);
    for (int py = 0; py < dh; py++)
        for (int px = 0; px < dw; px++) {
            int64_t sp[3] = {0, 0, 0}, sq = 0;
            for (int y = 0; y < GLYPH_SS; y++) {
                size_t at = (size_t)(py * GLYPH_SS + y) * cols + (size_t)px * GLYPH_SS;
                for (int x = 0; x < GLYPH_SS; x++, at++) {
                    sp[0] += P[at * 3];
                    sp[1] += P[at * 3 + 1];
                    sp[2] += P[at * 3 + 2];
                    sq += Q[at];
                }
            }
            int64_t *o = &sums[((size_t)py * dw + px) * 4];
            o[0] = sp[0]; o[1] = sp[1]; o[2] = sp[2]; o[3] = sq;
        }
    free(P); free(Q); free(diff); free(paint); free(edge);
    const size_t bytes = sizeof(int64_t) * 4 * (size_t)dw * dh;
    while (glyph_cache_count > 0 &&
           (glyph_cache_count == GLYPH_CACHE || glyph_cache_bytes + bytes > GLYPH_BUDGET)) {
        GlyphTile *oldest = &glyph_cache[(glyph_cache_next + GLYPH_CACHE - glyph_cache_count) % GLYPH_CACHE];
        free(oldest->sums);
        glyph_cache_bytes -= oldest->bytes;
        glyph_cache_count--;
    }
    GlyphTile *slot = &glyph_cache[glyph_cache_next];
    slot->glyph = g; slot->dw = dw; slot->dh = dh; slot->sums = sums; slot->bytes = bytes;
    glyph_cache_bytes += bytes;
    glyph_cache_count++;
    glyph_cache_next = (glyph_cache_next + 1) % GLYPH_CACHE;
    return sums;
}

KMRP_GLYPHS_API void kmrp_glyph_draw(const KmrpGlyph *g, uint8_t *sheet, int tw, int th, int left, int top,
                                     int dw, int dh, const uint8_t *backing) {
    const int64_t *sums = glyph_tile(g, dw, dh);
    for (int py = 0; py < dh; py++) {
        if (top + py < 0 || top + py >= th) continue;
        for (int px = 0; px < dw; px++) {
            if (left + px < 0 || left + px >= tw) continue;
            const int64_t *o = &sums[((size_t)py * dw + px) * 4];
            int64_t sp[3] = {o[0], o[1], o[2]}, sq = o[3];
            if (backing) {
                const int64_t rest = GLYPH_FULL - sq, ba = backing[3];
                for (int k = 0; k < 3; k++) sp[k] += (backing[k] * ba * rest) / 65025;
                sq += (255 * ba * rest) / 65025;
            }
            uint8_t *d = &sheet[((size_t)(top + py) * tw + left + px) * 4];
            for (int k = 0; k < 3; k++) {
                int64_t v = sq > 0 ? (255 * sp[k] + sq / 2) / sq : 0;
                d[k] = (uint8_t)(v > 255 ? 255 : v);
            }
            d[3] = (uint8_t)((sq + GLYPH_SS * GLYPH_SS * 127) / (GLYPH_SS * GLYPH_SS * 255));
        }
    }
}

/* Readers of the buffer, each 0 when it runs out. */
static int glyph_take(const uint8_t *data, size_t size, size_t *pos, void *out, size_t n) {
    if (*pos + n > size) return 0;
    memcpy(out, data + *pos, n);
    *pos += n;
    return 1;
}

static int glyph_u32(const uint8_t *data, size_t size, size_t *pos, uint32_t *out) {
    return glyph_take(data, size, pos, out, 4);
}

KMRP_GLYPHS_API int kmrp_glyph_read(const uint8_t *data, size_t size, size_t *pos, KmrpGlyph *g) {
    memset(g, 0, sizeof *g);
    if (!glyph_u32(data, size, pos, &g->width) || !glyph_u32(data, size, pos, &g->height) ||
        !glyph_u32(data, size, pos, &g->item_count))
        return 0;
    if (g->width == 0 || g->height == 0 || g->width > 65536 || g->height > 65536 || g->item_count > 64)
        return 0;
    g->items = calloc(g->item_count ? g->item_count : 1, sizeof(KmrpGlyphItem));
    if (!g->items) return 0;
    for (uint32_t j = 0; j < g->item_count; j++) {
        KmrpGlyphItem *it = &g->items[j];
        if (!glyph_take(data, size, pos, &it->rule, 1) || !glyph_take(data, size, pos, &it->kind, 1) ||
            it->rule > 1 || it->kind > 2)
            return 0;
        if (it->kind == 0) {
            if (!glyph_take(data, size, pos, it->rgba, 4)) return 0;
        } else {
            if (!glyph_take(data, size, pos, it->coef, 8 * (it->kind == 1 ? 3 : 6))) return 0;
            if (!glyph_u32(data, size, pos, &it->stop_count) || it->stop_count == 0 || it->stop_count > 16)
                return 0;
            for (uint32_t s = 0; s < it->stop_count; s++)
                if (!glyph_u32(data, size, pos, &it->stop_at[s]) || !glyph_take(data, size, pos, it->stop_rgba[s], 4))
                    return 0;
        }
        uint32_t polygons;
        if (!glyph_u32(data, size, pos, &polygons)) return 0;
        size_t start = *pos, edges = 0;
        for (uint32_t k = 0; k < polygons; k++) {   /* count first, then copy */
            uint32_t n;
            if (!glyph_u32(data, size, pos, &n) || n > 1000000 || *pos + (size_t)n * 8 > size) return 0;
            *pos += (size_t)n * 8;
            edges += n;
        }
        it->edge_count = (uint32_t)edges;
        it->edges = malloc(sizeof(int32_t) * 4 * (edges ? edges : 1));
        if (!it->edges) return 0;
        *pos = start;
        size_t e = 0;
        for (uint32_t k = 0; k < polygons; k++) {
            uint32_t n;
            glyph_u32(data, size, pos, &n);
            const uint8_t *v = data + *pos;
            for (uint32_t m = 0; m < n; m++) {
                int32_t xy[4];
                memcpy(&xy[0], v + (size_t)m * 8, 8);
                memcpy(&xy[2], v + (size_t)((m + 1) % n) * 8, 8);
                memcpy(&it->edges[e * 4], xy, sizeof xy);
                e++;
            }
            *pos += (size_t)n * 8;
        }
    }
    return 1;
}
