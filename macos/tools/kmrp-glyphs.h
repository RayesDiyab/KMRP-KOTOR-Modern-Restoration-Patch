/*
 * kmrp-glyphs: the controller button pictures drawn from their outlines (issue 68).
 *
 * tools/controller_glyphs.py's drawing, step for step: integers only, so every copy draws
 * the same bytes (testing/regression/Test-ControllerGlyphs.py checks this one against the
 * Python). That file's docstring states the rules; the names here follow it.
 *
 * Used by the blend helper (kmrp-guiblend.c includes kmrp-glyphs.c, its functions then
 * private: KMRP_GLYPHS_API static) and by the controller module, which draws each badge at
 * the size of the label it shows it on (vendor/K1XboxControls.cpp).
 */
#ifndef KMRP_GLYPHS_H
#define KMRP_GLYPHS_H

#include <stddef.h>
#include <stdint.h>

#ifndef KMRP_GLYPHS_API
#define KMRP_GLYPHS_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Closed polygons kept as edges, a fill rule and a paint. */
typedef struct {
    uint8_t rule, kind, rgba[4];          /* rule 0 nonzero, 1 even-odd; kind 0 solid, 1 linear, 2 radial */
    int64_t coef[6];
    uint32_t stop_count, edge_count;
    uint32_t stop_at[16];
    uint8_t stop_rgba[16][4];
    int32_t *edges;                       /* x0 y0 x1 y1 per edge, in glyph units */
} KmrpGlyphItem;

/* A box of width x height units and the items painted in it, in order. */
typedef struct { uint32_t width, height, item_count; KmrpGlyphItem *items; } KmrpGlyph;

/* One glyph as controller_glyphs.pack writes it, from data[*pos], *pos moved past it.
 * 1 on success, 0 for data that is not one. */
KMRP_GLYPHS_API int kmrp_glyph_read(const uint8_t *data, size_t size, size_t *pos, KmrpGlyph *g);

/* draw_into: the glyph drawn into the dw x dh rectangle at (left, top) of `sheet` (tw x th,
 * RGBA, top row first, transparent or all `backing`). */
KMRP_GLYPHS_API void kmrp_glyph_draw(const KmrpGlyph *g, uint8_t *sheet, int tw, int th, int left, int top,
                                     int dw, int dh, const uint8_t *backing);

/* The same drawing without the kept ones: nothing shared between calls, so safe on another
 * thread while kmrp_glyph_draw runs. */
KMRP_GLYPHS_API void kmrp_glyph_draw_alone(const KmrpGlyph *g, uint8_t *sheet, int tw, int th, int left, int top,
                                           int dw, int dh, const uint8_t *backing);

/* Forgets the kept drawings (kmrp_glyph_draw keeps its latest, up to 8 MB). */
KMRP_GLYPHS_API void kmrp_glyph_cache_reset(void);

#ifdef __cplusplus
}
#endif

#endif
