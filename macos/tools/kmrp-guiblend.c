/*
 * kmrp-guiblend: derive KMRP's GUI set for a resolution the build has no set for.
 *
 *   kmrp-guiblend TABLE WIDTH HEIGHT OUTDIR SETDIR    writes every .gui for WIDTHxHEIGHT
 *   kmrp-guiblend TABLE WIDTH HEIGHT                  prints the sets it would blend, writes nothing
 *
 * TABLE is gui-blend.bin from tools/build_gui_blend_table.py: per .gui file a template, the
 * numeric fields that vary between resolutions, and their values in each finished set the
 * build made. This does the blend tools/derive_resolution_gui_set.py does on upstream: the
 * two aspect-ratio families on either side of WIDTH/HEIGHT, each at the two heights around
 * HEIGHT, weighted and rounded once (half away from zero). It interpolates numbers the build
 * made; KMRP's layout logic stays in the build. Every step mirrors the Python, so the output
 * is byte-identical to it (testing/regression/Test-GuiBlendHelper.py checks that).
 *
 * Three exceptions. Two since table version 2 (2026-09-30), both done with the fonts of the
 * set the installer takes them from, SETDIR (its files extracted there):
 *   - the Container is widened, in some sets and not others, until "Switch To Give Item"
 *     and its badge fit. The table holds it unwidened, with the rule's fields and constants,
 *     and this applies the rule to the blend as prepare_universal_resources.py's
 *     fit_container_to_caption does, with the caption width SETDIR/kmrp_prompts.txt gives;
 *   - the Controller Layout screen is generated at each resolution, not scaled. This does
 *     build_controller_layout.py's build_gui arithmetic, step for step and in the same order
 *     (the float results must round the same), with every number from the table by name,
 *     the panel size from the blend and the caption font's TXI from SETDIR. The regression
 *     compares the result with build_gui's own, byte for byte, at every size it derives.
 * And the lists scale_listbox_padding.py makes as tall as whole rows (the Container, the
 * granted popup, the character-generation Feats list and a few full-screen lists at low
 * resolutions): the table holds them before the fit, and this fits the blend with the same
 * arithmetic (fit_rows), from the row sizes at HEIGHT.
 *
 * And the controller badges: every texture the prompt
 * manifest lists, drawn again for its blended button. A badge is a 512x64 texture the engine
 * stretches over its whole button, drawn to come out round on that button, so the nearest
 * set's, drawn for that set's buttons, came out stretched on buttons of another shape (1.86
 * times as wide as tall at 3440x1400). This is build_controller_prompt_textures.py's
 * build_prompt_tga with Pillow's arithmetic -- the Lanczos resample on premultiplied alpha in
 * 22-bit fixed point, the masked paste, alpha_composite -- from the artwork the table carries,
 * with the label widths of SETDIR's manifest, so a set the blend resolves to itself comes out
 * with the build's badges byte for byte. It also writes that manifest with the blended button
 * sizes, the Container's widening and the row fits, and lbl_mileftbot.tga, the HUD's
 * button-row boxes, which build_menubg_texture.py draws from each set's mipc28x6.gui and which
 * the nearest set's drew out of step with the blended buttons, from the blended HUD.
 *
 * The row fits and the badges both came as table version 3 on 2026-09-30, on two branches, in
 * two formats; the merge of the two the same day is version 4, which carries both.
 *
 * Exit status: 0 written, 1 usage or I/O error, 2 resolution outside the anchors' range.
 */
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <direct.h>
#define strcasecmp _stricmp
#define strncasecmp _strnicmp
#define mkdir(path, mode) _mkdir(path)
#else
#include <strings.h>
#endif
#include <sys/stat.h>

#ifdef KMRP_GUI_EMBEDDED
/* The command-line helper exits after one derivation. The DLL can derive again
 * after each mode change, so collect every temporary allocation even on error. */
typedef struct BlendAllocation { void *data; struct BlendAllocation *next; } BlendAllocation;
static BlendAllocation *blend_allocations;
static void *blend_malloc(size_t size) {
    void *data = malloc(size);
    if (!data) return NULL;
    BlendAllocation *node = malloc(sizeof *node);
    if (!node) { free(data); return NULL; }
    node->data = data; node->next = blend_allocations; blend_allocations = node;
    return data;
}
static void *blend_calloc(size_t count, size_t size) {
    if (size && count > SIZE_MAX / size) return NULL;
    void *data = blend_malloc(count * size);
    if (data) memset(data, 0, count * size);
    return data;
}
static void blend_free(void *data) {
    BlendAllocation **link = &blend_allocations;
    while (*link && (*link)->data != data) link = &(*link)->next;
    if (*link) { BlendAllocation *node = *link; *link = node->next; free(node); free(data); }
}
static void blend_clear(void) { while (blend_allocations) blend_free(blend_allocations->data); }
#define malloc blend_malloc
#define calloc blend_calloc
#define free blend_free
#define main blend_main
#endif

/* Byte-identical to the Python blend means the same rounding at every step: no fused
 * multiply-add, which clang emits by default on arm64 and which rounds exact .5 ties
 * differently (7 files differed before this, 2026-09-29). */
#ifndef _MSC_VER
#pragma STDC FP_CONTRACT OFF
#endif

typedef struct { uint32_t width, height, family; } Anchor;
typedef struct { int index; double weight; } Term;
/* build_gui_blend_table.py's fit record: fit_container_to_caption and the badge geometry of
 * build_controller_prompt_textures.py (badge_radius, badge_fit_width). */
typedef struct {
    char name[256], row[64];
    double radius_short, radius, gap, edge;
    uint32_t short_below, left, width, button_width, button_height, count, widths[16];
} Fit;
/* build_gui_blend_table.py's layout record: build_controller_layout.py's layout_constants,
 * layout_rows and where each control's extent sits. */
typedef struct { char side; double glyph_x, row_y; char caption[128]; } Row;
typedef struct {
    char name[256], font[64];
    uint32_t constants;
    char constant_names[96][32];
    double constant_values[96];
    uint32_t rows;
    Row row[32];
    uint32_t root_width, root_height, controls, extent[96][4];
} Layout;
/* build_gui_blend_table.py's row-fit record (table version 4): a list that
 * scale_listbox_padding.py's fit_list_to_rows makes as tall as whole rows. */
typedef struct {
    char name[256], tag[64];
    uint8_t popup;
    double loose;
    uint32_t divisor, bases, base[4], height, dimension, bar, panel_top, panel_height, below, below_top[16];
} RowFit;
/* A caption font as parse_font_metrics reads its TXI, and build_gui's line height. */
typedef struct { double advances[256]; int count; double spacing, line_h; } Font;
/* The badges (table version 4): build_prompt_tga's constants, the glyph artwork as
 * _load_glyph_art loads it, and per prompt manifest row where its button is, its glyph, its
 * backing and the controls whose least height sizes it. */
typedef struct { uint32_t width, height; uint8_t *rgba; } Glyph;
typedef struct {
    char resref[32], gui[256];
    uint32_t width_at, height_at, glyph, sizing_count, sizing[16];
    uint8_t backed, backing[4];
} Prompt;
typedef struct {
    uint32_t texture_w, texture_h, short_below, glyph_count, prompt_count;
    double radius, radius_short, gap, edge, center_y, fallback_x;
    uint8_t footer[64];
    uint16_t footer_len;
    Glyph *glyphs;
    Prompt *prompts;
} Badges;
/* A blended file, kept until the badges are drawn from its buttons. */
typedef struct { char name[256]; uint8_t *data; uint32_t size; } Output;
/* build_menubg_texture.py's lbl_mileftbot.tga: the HUD's button-row boxes, drawn from where
 * LBL_MENUBG and the eight buttons sit in the HUD the size loads. */
typedef struct {
    char gui[256], texture[64];
    uint32_t width, height, edge_alpha, backdrop_left, backdrop_width, count, left[16], button_width[16];
} Hud;

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

static int take_text(char *out, size_t size) {
    uint16_t n = 0;
    if (!take(&n, 2) || n == 0 || n >= size || !take(out, n)) return 0;
    out[n] = 0;
    return 1;
}

/* The baked label width of `row` in a prompt manifest: "prompt <row> <w> <h> <width> ...". */
static int caption_width(const char *manifest, const char *row, double *width) {
    FILE *f = fopen(manifest, "r");
    if (!f) return 0;
    char line[8192], name[64];
    int found = 0;
    while (!found && fgets(line, sizeof line, f)) {
        int w, h;
        if (sscanf(line, "prompt %63s %d %d %lf", name, &w, &h, width) == 4 && strcmp(name, row) == 0)
            found = 1;
    }
    fclose(f);
    return found;
}

static int32_t get_i32(const uint8_t *data, uint32_t offset) {
    int32_t v;
    memcpy(&v, data + offset, 4);
    return v;
}

static void add_i32(uint8_t *data, uint32_t offset, int32_t delta) {
    int32_t v = get_i32(data, offset) + delta;
    memcpy(data + offset, &v, 4);
}

/* fit_container_to_caption on the blended file: widen until the button holds the caption
 * and its badge at the designed gap, by an even number of pixels, the panel about its centre.
 * Returns the widening, for the manifest's "widened" line. */
static int32_t apply_fit(const Fit *fit, uint8_t *data, double caption) {
    int32_t height = get_i32(data, fit->button_height);
    double radius = height * (height < (int32_t)fit->short_below ? fit->radius_short : fit->radius);
    double need = caption + 2.0 * radius * (fit->gap + 1.0 + fit->edge);
    int32_t extra = (int32_t)ceil(need - get_i32(data, fit->button_width));
    if (extra <= 0) return 0;
    extra += extra % 2;
    add_i32(data, fit->left, -(extra / 2));
    add_i32(data, fit->width, extra);
    for (uint32_t i = 0; i < fit->count; i++) add_i32(data, fit->widths[i], extra);
    return extra;
}

/* ------------------------------------------------------------------ the badges
 * Pillow 12's arithmetic, as build_prompt_tga reaches it: Image.resize(LANCZOS) on RGBA goes
 * through premultiplied RGBa (Convert.c's rgba2rgbA and rgbA2rgba), Resample.c's two passes
 * with precompute_coeffs and normalize_coeffs_8bpc, and 64-bit sums where Pillow's are
 * 32-bit, which never overflow here (255 x at most 1.3 x 2^22). */
#define PRECISION_BITS (32 - 8 - 2)
static const double PI = 3.14159265358979323846;   /* M_PI */

static double sinc_filter(double x) {
    if (x == 0.0) return 1.0;
    x = x * PI;
    return sin(x) / x;
}

static double lanczos_filter(double x) {
    if (-3.0 <= x && x < 3.0) return sinc_filter(x) * sinc_filter(x / 3);
    return 0.0;
}

/* Per output pixel: the first input pixel, how many, and their fixed-point weights. */
static int precompute_coeffs(int in_size, int out_size, int **bounds_out, int32_t **kk_out) {
    double scale = (double)(float)in_size / out_size, filterscale = scale;
    if (filterscale < 1.0) filterscale = 1.0;
    double support = 3.0 * filterscale;
    int ksize = (int)ceil(support) * 2 + 1;
    int *bounds = malloc(sizeof(int) * 2 * out_size);
    int32_t *kk = calloc((size_t)out_size * ksize, sizeof(int32_t));
    double *k = malloc(sizeof(double) * ksize);
    for (int xx = 0; xx < out_size; xx++) {
        double center = 0.0 + (xx + 0.5) * scale, ww = 0.0, ss = 1.0 / filterscale;
        int xmin = (int)(center - support + 0.5);
        if (xmin < 0) xmin = 0;
        int xmax = (int)(center + support + 0.5);
        if (xmax > in_size) xmax = in_size;
        xmax -= xmin;
        for (int x = 0; x < xmax; x++) {
            double w = lanczos_filter((x + xmin - center + 0.5) * ss);
            k[x] = w;
            ww += w;
        }
        for (int x = 0; x < xmax; x++) {
            if (ww != 0.0) k[x] /= ww;
            kk[xx * ksize + x] = k[x] < 0 ? (int32_t)(-0.5 + k[x] * (1 << PRECISION_BITS))
                                          : (int32_t)(0.5 + k[x] * (1 << PRECISION_BITS));
        }
        bounds[xx * 2] = xmin;
        bounds[xx * 2 + 1] = xmax;
    }
    free(k);
    *bounds_out = bounds;
    *kk_out = kk;
    return ksize;
}

static uint8_t clip8(int64_t in) {
    if (in >= ((int64_t)1 << PRECISION_BITS << 8)) return 255;
    if (in <= 0) return 0;
    return (uint8_t)(in >> PRECISION_BITS);
}

static uint8_t muldiv255(unsigned a, unsigned b) {
    unsigned t = a * b + 128;
    return (uint8_t)(((t >> 8) + t) >> 8);
}

/* Image.resize((dw, dh), LANCZOS) of a straight-alpha RGBA image. */
static uint8_t *resize_rgba(const uint8_t *in, int w, int h, int dw, int dh) {
    uint8_t *out = malloc((size_t)dw * dh * 4);
    if (dw == w && dh == h) {   /* resize() returns a copy */
        memcpy(out, in, (size_t)w * h * 4);
        return out;
    }
    uint8_t *pre = malloc((size_t)w * h * 4);
    for (int i = 0; i < w * h; i++) {
        unsigned a = in[i * 4 + 3];
        for (int c = 0; c < 3; c++) pre[i * 4 + c] = muldiv255(in[i * 4 + c], a);
        pre[i * 4 + 3] = (uint8_t)a;
    }
    int *hb, *vb;
    int32_t *hk, *vk;
    int hks = precompute_coeffs(w, dw, &hb, &hk);
    int vks = precompute_coeffs(h, dh, &vb, &vk);
    const uint8_t *img = pre;
    int iw = w;
    uint8_t *tmp = NULL;
    if (dw != w) {
        int first = vb[0], last = vb[(dh - 1) * 2] + vb[(dh - 1) * 2 + 1];
        for (int i = 0; i < dh; i++) vb[i * 2] -= first;
        tmp = malloc((size_t)dw * (last - first) * 4);
        for (int yy = first; yy < last; yy++)
            for (int xx = 0; xx < dw; xx++) {
                int64_t ss[4] = {1 << (PRECISION_BITS - 1), 1 << (PRECISION_BITS - 1),
                                 1 << (PRECISION_BITS - 1), 1 << (PRECISION_BITS - 1)};
                const int32_t *k = &hk[xx * hks];
                for (int x = 0; x < hb[xx * 2 + 1]; x++)
                    for (int c = 0; c < 4; c++)
                        ss[c] += (int64_t)img[((size_t)yy * iw + x + hb[xx * 2]) * 4 + c] * k[x];
                for (int c = 0; c < 4; c++) tmp[((size_t)(yy - first) * dw + xx) * 4 + c] = clip8(ss[c]);
            }
        img = tmp;
        iw = dw;
    }
    uint8_t *res = out;
    if (dh != h) {
        for (int yy = 0; yy < dh; yy++)
            for (int xx = 0; xx < iw; xx++) {
                int64_t ss[4] = {1 << (PRECISION_BITS - 1), 1 << (PRECISION_BITS - 1),
                                 1 << (PRECISION_BITS - 1), 1 << (PRECISION_BITS - 1)};
                const int32_t *k = &vk[yy * vks];
                for (int y = 0; y < vb[yy * 2 + 1]; y++)
                    for (int c = 0; c < 4; c++)
                        ss[c] += (int64_t)img[((size_t)(y + vb[yy * 2]) * iw + xx) * 4 + c] * k[y];
                for (int c = 0; c < 4; c++) res[((size_t)yy * dw + xx) * 4 + c] = clip8(ss[c]);
            }
    } else {
        memcpy(res, img, (size_t)dw * dh * 4);
    }
    for (int i = 0; i < dw * dh; i++) {   /* RGBa back to RGBA */
        unsigned a = res[i * 4 + 3];
        if (a == 255 || a == 0) continue;
        for (int c = 0; c < 3; c++) {
            unsigned v = 255u * res[i * 4 + c] / a;
            res[i * 4 + c] = (uint8_t)(v > 255 ? 255 : v);
        }
    }
    free(pre); free(tmp); free(hb); free(vb); free(hk); free(vk);
    return res;
}

static uint8_t div255(unsigned a) {
    unsigned t = a + 128;
    return (uint8_t)(((t >> 8) + t) >> 8);
}

/* build_prompt_tga for a control of cw x ch: the TGA, header and footer included. */
static uint8_t *draw_badge(const Badges *B, const Glyph *art, int cw, int ch, double label,
                           int radius_height, const uint8_t *backing, size_t *size) {
    const int tw = (int)B->texture_w, th = (int)B->texture_h;
    double center_y = ch * B->center_y;
    int sizing = radius_height > 0 ? radius_height : ch;
    double radius = sizing * (sizing < (int)B->short_below ? B->radius_short : B->radius);
    double center_x;
    if (label > 0) {
        double gap = radius * B->gap;
        center_x = (cw - label) / 2.0 - gap - radius;
        center_x = fmax(radius * B->edge, center_x);
    } else {
        center_x = ch * B->fallback_x;
    }
    double diameter = radius * 2.0, aspect = (double)art->width / art->height;
    double box_w = aspect < 1.0 ? diameter * aspect : diameter;
    double box_h = aspect > 1.0 ? diameter / aspect : diameter;
    int dst_w = (int)rint(box_w * tw / cw), dst_h = (int)rint(box_h * th / ch);
    if (dst_w < 1) dst_w = 1;
    if (dst_h < 1) dst_h = 1;
    int left = (int)rint((center_x - box_w / 2.0) * tw / cw);
    int top = (int)rint((center_y - box_h / 2.0) * th / ch);
    uint8_t *glyph = resize_rgba(art->rgba, (int)art->width, (int)art->height, dst_w, dst_h);

    uint8_t *sheet = calloc((size_t)tw * th, 4);   /* top row first, RGBA */
    for (int y = 0; y < dst_h; y++) {
        if (top + y < 0 || top + y >= th) continue;
        for (int x = 0; x < dst_w; x++) {
            if (left + x < 0 || left + x >= tw) continue;
            const uint8_t *s = &glyph[((size_t)y * dst_w + x) * 4];
            uint8_t *d = &sheet[((size_t)(top + y) * tw + left + x) * 4];
            for (int c = 0; c < 4; c++)   /* paste(art, box, art): BLEND over nothing; else a copy */
                d[c] = backing ? s[c] : div255((unsigned)s[c] * s[3]);
        }
    }
    if (backing) {   /* alpha_composite(the backing, the sheet) */
        for (int i = 0; i < tw * th; i++) {
            uint8_t *s = &sheet[i * 4];
            if (s[3] == 0) {
                memcpy(s, backing, 4);
                continue;
            }
            uint32_t blend = (uint32_t)backing[3] * (255 - s[3]);
            uint32_t outa255 = (uint32_t)s[3] * 255 + blend;
            uint32_t coef1 = (uint32_t)s[3] * 255 * 255 * (1 << 7) / outa255;
            uint32_t coef2 = 255 * (1 << 7) - coef1;
            for (int c = 0; c < 3; c++) {
                uint32_t t = s[c] * coef1 + backing[c] * coef2 + (0x80 << 7);
                s[c] = (uint8_t)(((((t >> 8) + t) >> 8)) >> 7);
            }
            uint32_t a = outa255 + 0x80;
            s[3] = (uint8_t)(((a >> 8) + a) >> 8);
        }
    }
    *size = 18 + (size_t)tw * th * 4 + B->footer_len;
    uint8_t *tga = calloc(1, *size);
    tga[2] = 2;
    tga[12] = (uint8_t)tw; tga[13] = (uint8_t)(tw >> 8);
    tga[14] = (uint8_t)th; tga[15] = (uint8_t)(th >> 8);
    tga[16] = 32; tga[17] = 0x08;
    for (int y = 0; y < th; y++)   /* bottom row first, BGRA */
        for (int x = 0; x < tw; x++) {
            const uint8_t *s = &sheet[((size_t)(th - 1 - y) * tw + x) * 4];
            uint8_t *d = &tga[18 + ((size_t)y * tw + x) * 4];
            d[0] = s[2]; d[1] = s[1]; d[2] = s[0]; d[3] = s[3];
        }
    memcpy(tga + 18 + (size_t)tw * th * 4, B->footer, B->footer_len);
    free(glyph);
    free(sheet);
    return tga;
}

/* scale_listbox_padding.py's row_height: a row of `base` at a screen `height`, the base
 * times s = max(1, height / 720) in single precision, rounded half to even, as the game's
 * layout patch and the Windows installer size them. */
static int32_t row_height(uint32_t base, uint32_t height) {
    float s = (float)((double)height / 720.0);
    if (s < 1.0f) s = 1.0f;
    float product = (float)((double)(float)base * (double)s);
    return (int32_t)nearbyint((double)product);
}

/* fit_list_to_rows on the blended file: the list as tall as whole rows, each row // divisor
 * from the next, every kind of row keeping the count that fits; a popup's controls below
 * the list move with its bottom and its panel changes about its centre; a full-screen list
 * only shrinks, and only when a kind's gap is looser than `loose` of its row. 0 on success,
 * with the change in height in *changed, for the manifest's "fitted" line. */
static int fit_rows(const RowFit *fit, uint8_t *data, uint32_t height, int32_t *changed) {
    *changed = 0;
    int32_t inner = get_i32(data, fit->height) - 2 * get_i32(data, fit->dimension);
    int32_t wanted = 0;
    int loose = 0;
    for (uint32_t i = 0; i < fit->bases; i++) {
        int32_t row = row_height(fit->base[i], height);
        if (row < 1 || inner < row) {
            fprintf(stderr, "kmrp-guiblend: %s %s: no %d-px row fits %d px\n", fit->name, fit->tag, row, inner);
            return 1;
        }
        int32_t rows = inner / row;
        loose |= (double)((inner - rows * row) / rows) > row * fit->loose;
        int32_t rows_height = rows * (row + row / (int32_t)fit->divisor);
        if (rows_height > wanted) wanted = rows_height;
    }
    int32_t change = wanted - inner;
    if (change == 0 || (!fit->popup && (!loose || change > 0))) return 0;
    *changed = change;
    add_i32(data, fit->height, change);
    if (fit->bar) add_i32(data, fit->bar, change);
    if (fit->popup) {
        for (uint32_t i = 0; i < fit->below; i++) add_i32(data, fit->below_top[i], change);
        add_i32(data, fit->panel_top, -(int32_t)floor(change / 2.0));   /* Python's change // 2 */
        add_i32(data, fit->panel_height, change);
    }
    return 0;
}

/* parse_font_metrics (build_controller_prompt_textures.py): glyph advances
 * (lowerright.u - upperleft.u) * texturewidth * 100, spacingR * 100; and build_gui's line
 * height, fontheight * 100 from the first line matching "^fontheight (\S+)". */
static int read_font(const char *path, Font *font) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    static double upper[256], lower[256];
    int uppers = 0, lowers = 0, mode = 0, have_height = 0;   /* mode: 0 none, 1 upper, 2 lower */
    double texture_width = 0.0, spacing = 0.0;
    font->line_h = 0.0;
    char line[512];
    while (fgets(line, sizeof line, f)) {
        if (!have_height && strncasecmp(line, "fontheight ", 11) == 0 && line[11] &&
            !strchr(" \t\r\n", line[11])) {
            font->line_h = strtod(line + 11, NULL) * 100;
            have_height = 1;
        }
        char copy[512], *parts[4];
        int count = 0;
        strcpy(copy, line);
        for (char *p = strtok(copy, " \t\r\n\f\v"); p && count < 4; p = strtok(NULL, " \t\r\n\f\v"))
            parts[count++] = p;
        if (count == 0) continue;
        if (strcasecmp(parts[0], "texturewidth") == 0 && count > 1) {
            texture_width = strtod(parts[1], NULL); mode = 0;
        } else if (strcasecmp(parts[0], "spacingr") == 0 && count > 1) {
            spacing = strtod(parts[1], NULL); mode = 0;
        } else if (strcasecmp(parts[0], "upperleftcoords") == 0) {
            mode = 1;
        } else if (strcasecmp(parts[0], "lowerrightcoords") == 0) {
            mode = 2;
        } else if (mode && count >= 2) {
            char *end;
            double value = strtod(parts[0], &end);
            if (*end) { mode = 0; continue; }
            if (mode == 1 && uppers < 256) upper[uppers++] = value;
            else if (mode == 2 && lowers < 256) lower[lowers++] = value;
        }
    }
    fclose(f);
    if (texture_width == 0.0 || uppers == 0 || lowers < uppers) return 0;
    font->count = uppers < lowers ? uppers : lowers;
    for (int i = 0; i < font->count; i++) font->advances[i] = (lower[i] - upper[i]) * texture_width * 100.0;
    font->spacing = spacing * 100.0;
    return 1;
}

/* measure_label */
static double measure(const Font *font, const char *text) {
    double total = 0.0;
    for (int i = 0; text[i]; i++) {
        int code = (unsigned char)text[i];
        if (code < font->count) total += font->advances[code];
        if (i) total += font->spacing;
    }
    return total;
}

static double constant(const Layout *layout, const char *name) {
    for (uint32_t i = 0; i < layout->constants; i++)
        if (strcmp(layout->constant_names[i], name) == 0) return layout->constant_values[i];
    fprintf(stderr, "kmrp-guiblend: the table has no layout constant %s\n", name);
    exit(1);
}

static void set_extent(const Layout *layout, uint8_t *data, uint32_t *index,
                       double x, double y, double w, double h) {
    const double v[4] = {x, y, w, h};
    for (int k = 0; k < 4; k++) {
        int32_t rounded = (int32_t)rint(v[k]);   /* Python's round(): half to even */
        memcpy(data + layout->extent[*index][k], &rounded, 4);
    }
    (*index)++;
}

/* build_controller_layout.py's build_gui, its extents only: every other byte of the file is
 * the blend's. Each expression keeps the Python's order of operations. */
static void generate(const Layout *L, const Font *font, uint8_t *data) {
#define K(name) constant(L, name)
    const double width = get_i32(data, L->root_width), height = get_i32(data, L->root_height);
    const double scale = fmax(1, height / K("SCALE_HEIGHT"));
    const double left = width / 2 - K("DESIGN_W") / 2 * scale;
    const double spread = fmin(K("SPREAD"), fmax(0.0, height / scale - K("COMPACT_H") - K("SCREEN_MARGIN")));
    const double up = rint(spread * K("SPREAD_UP") / K("SPREAD"));
    const double down = spread - up;
    const double top = fmax(K("TOP_MIN_PX") + up * scale,
                            (height - (K("COMPACT_H") + spread) * scale) / 2 + up * scale);
    uint32_t index = 0;
#define ADD(x, y, w, h) set_extent(L, data, &index, left + (x) * scale, top + (y) * scale, (w) * scale, (h) * scale)
    ADD(0, -up, K("DESIGN_W"), K("TITLE_H"));
    ADD(K("BACK_X"), K("BACK_Y") + down, K("BACK_W"), K("BACK_H"));
    for (int i = 0; i < 4; i++) ADD(0, K("FAMILY_Y") - up, K("DESIGN_W"), K("FAMILY_H"));
    for (int i = 0; i < 2; i++) ADD(0, 0, 0, 0);
    ADD(K("BOARD_X"), K("BOARD_Y"), K("BOARD_W"), K("BOARD_H"));
    ADD(0, K("HELP_Y") + down, K("DESIGN_W"), K("HELP_H"));

    double need[3] = {0.0, 0.0, 0.0};   /* L, R, T */
    for (uint32_t i = 0; i < L->rows; i++) {
        double w = measure(font, L->row[i].caption) * K("RENDER_FACTOR") / scale + K("CAPTION_PAD");
        int side = L->row[i].side == 'L' ? 0 : L->row[i].side == 'R' ? 1 : 2;
        need[side] = fmax(need[side], w);
    }
    const double screen_left = -left / scale + K("EDGE_GAP");
    const double screen_right = (width - left) / scale - K("EDGE_GAP");
    const double left_w = fmin(fmax(K("CAPTION_W"), need[0]), K("LEFT_GLYPH_X") - K("CAPTION_GAP") - screen_left);
    const double right_w = fmin(fmax(K("CAPTION_W"), need[1]),
                                screen_right - (K("RIGHT_GLYPH_X") + K("GLYPH") + K("CAPTION_GAP")));
    const double top_w = fmax(K("TOP_CAPTION_W"), need[2]);
    const double overhang = fmax(left_w, right_w) - K("CAPTION_W");
    const double two_lines = fmax(K("LINE_BOX_H"), K("TWO_LINES") * font->line_h / scale);
    for (uint32_t i = 0; i < L->rows; i++) {
        const Row *r = &L->row[i];
        const double y = K("BOARD_Y") + r->row_y;
        ADD(r->glyph_x, y - K("GLYPH") / 2, K("GLYPH"), K("GLYPH"));
        if (r->side == 'T') {
            const double tw = top_w, tx = r->glyph_x + K("GLYPH") / 2 - tw / 2;
            ADD(tx, y - K("GLYPH") / 2 - K("TOP_CAPTION_RISE"), tw, K("TOP_CAPTION_H"));
            continue;
        }
        const double tw = r->side == 'L' ? left_w : right_w;
        const double tx = r->side == 'L' ? K("LEFT_GLYPH_X") - K("CAPTION_GAP") - tw
                                         : K("RIGHT_GLYPH_X") + K("GLYPH") + K("CAPTION_GAP");
        const double caption = measure(font, r->caption) * K("RENDER_FACTOR") / scale + K("CAPTION_PAD");
        const double th = caption > tw ? two_lines : K("LINE_BOX_H");
        ADD(tx, y - th / 2, tw, th);
    }

    /* controller_layout_backdrop.py's placements, already rounded there and again here. */
    const double hair_upper = K("HEADING_BOTTOM") - up + K("HAIR_BELOW_HEADING");
    const double hair_lower = down >= K("HAIR_OPEN_DOWN") ? K("HELP_Y") + down - K("HAIR_ABOVE_HELP")
                                                          : K("HAIR_COMPACT_Y");
    const double design_w = K("DESIGN_W") + 2 * overhang, s = scale;
    const double gap = K("DECOR_EDGE_GAP") * s, c = K("DECOR_CORNER") * s;
    double decor[16][4] = {
        {gap, gap, c, c}, {width - gap - c, gap, c, c},
        {gap, height - gap - c, c, c}, {width - gap - c, height - gap - c, c, c},
    };
    int n = 4;
    const double x0 = gap + c * K("HAIR_OVERLAP"), x1 = width - gap - c * K("HAIR_OVERLAP");
    const double hairs[2] = {hair_upper, hair_lower};
    for (int k = 0; k < 2; k++) {
        const double cy = top + hairs[k] * s;
        decor[n][0] = x0; decor[n][1] = cy - K("HAIR_H") * s / 2; decor[n][2] = x1 - x0; decor[n][3] = K("HAIR_H") * s;
        n++;
    }
    const double rw = K("READOUT_W") * s, rh = K("READOUT_H") * s, inset = gap + K("READOUT_INSET") * s;
    decor[n][0] = inset; decor[n][1] = inset; decor[n][2] = rw; decor[n][3] = rh; n++;
    decor[n][0] = width - inset - rw; decor[n][1] = height - inset - rh; decor[n][2] = rw; decor[n][3] = rh; n++;
    const double margin = (width / s - design_w) / 2;
    const double art = fmin(fmin(K("ART_MAX_W"), margin - 2 * K("ART_MARGIN")), (height / s - 2 * K("DECOR_CORNER")) / 2);
    for (int side = 0; side < 2; side++) {
        if (art < K("ART_MIN_W")) {
            decor[n][0] = decor[n][1] = decor[n][2] = decor[n][3] = 0; n++;
            continue;
        }
        const double cx = side == 0 ? margin / 2 : width / s - margin / 2;
        decor[n][0] = (cx - art / 2) * s; decor[n][1] = height / 2 - art * s;
        decor[n][2] = art * s; decor[n][3] = 2 * art * s;
        n++;
    }
    for (int k = 0; k < n; k++)
        set_extent(L, data, &index, rint(decor[k][0]), rint(decor[k][1]), rint(decor[k][2]), rint(decor[k][3]));

    /* The B inside Back. */
    const double back_x = K("BACK_X"), back_y = K("BACK_Y") + down, size = K("BACK_H") - K("BACK_GLYPH_TRIM");
    set_extent(L, data, &index, left + (back_x + K("BACK_GLYPH_X")) * scale,
               top + (back_y + K("BACK_GLYPH_Y")) * scale, size * scale, size * scale);
#undef ADD
#undef K
}

static uint8_t *read_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc(n > 0 ? (size_t)n + 1 : 1);
    if (!data || (n > 0 && fread(data, 1, (size_t)n, f) != (size_t)n)) { fclose(f); return NULL; }
    fclose(f);
    data[n > 0 ? n : 0] = 0;
    *size = n > 0 ? (size_t)n : 0;
    return data;
}

typedef struct { int32_t left, right; } Box;

static int box_order(const void *a, const void *b) {
    const Box *x = a, *y = b;
    if (x->left != y->left) return x->left < y->left ? -1 : 1;
    return x->right < y->right ? -1 : x->right > y->right;
}

/* build_menubg_texture.py's build_tga, from geometry_from_gui's boxes in the blended HUD:
 * one alpha row, each box opaque black with a 1 px edge at the edge alpha, every row alike. */
static uint8_t *draw_hud(const Hud *m, const uint8_t *gui, const uint8_t *footer, uint16_t footer_len,
                         size_t *size) {
    int32_t origin = get_i32(gui, m->backdrop_left), span = get_i32(gui, m->backdrop_width);
    Box boxes[16];
    for (uint32_t i = 0; i < m->count; i++) {
        boxes[i].left = get_i32(gui, m->left[i]) - origin;
        boxes[i].right = boxes[i].left + get_i32(gui, m->button_width[i]);
    }
    qsort(boxes, m->count, sizeof boxes[0], box_order);
    if (span <= 0 || m->count == 0 || boxes[0].left < 0 || boxes[m->count - 1].right > span) {
        fprintf(stderr, "kmrp-guiblend: %s: buttons fall outside LBL_MENUBG\n", m->gui);
        return NULL;
    }
    const int w = (int)m->width, h = (int)m->height;
    double scale = (double)w / span;
    uint8_t *alpha = calloc((size_t)w, 1);
    for (uint32_t i = 0; i < m->count; i++) {
        int start = (int)rint(boxes[i].left * scale), end = (int)rint(boxes[i].right * scale);
        if (start < 0) start = 0;
        if (end > w) end = w;
        for (int x = start; x < end; x++) alpha[x] = (uint8_t)(x == start || x == end - 1 ? m->edge_alpha : 255);
    }
    *size = 18 + (size_t)w * h * 4 + footer_len;
    uint8_t *tga = calloc(1, *size);
    tga[2] = 2;
    tga[12] = (uint8_t)w; tga[13] = (uint8_t)(w >> 8);
    tga[14] = (uint8_t)h; tga[15] = (uint8_t)(h >> 8);
    tga[16] = 32; tga[17] = 0x08;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) tga[18 + ((size_t)y * w + x) * 4 + 3] = alpha[x];
    memcpy(tga + 18 + (size_t)w * h * 4, footer, footer_len);
    free(alpha);
    return tga;
}

static int write_file(const char *path, const uint8_t *data, size_t size) {
    FILE *o = fopen(path, "wb");
    if (!o || fwrite(data, 1, size, o) != size || fclose(o) != 0) {
        fprintf(stderr, "kmrp-guiblend: %s: write failed\n", path);
        return 0;
    }
    return 1;
}

/* The next line of a manifest, from *at: its length with its line end. */
static size_t next_line(const uint8_t *text, size_t size, size_t at) {
    size_t end = at;
    while (end < size && text[end] != '\n') end++;
    return (end < size ? end + 1 : end) - at;
}

/* The label width a manifest's row for `resref` bakes: "prompt <resref> <w> <h> <width> ...". */
static int manifest_label(const uint8_t *text, size_t size, const char *resref, double *label) {
    for (size_t at = 0, n; at < size; at += n) {
        n = next_line(text, size, at);
        char line[8192], name[64];
        if (n >= sizeof line) continue;
        memcpy(line, text + at, n);
        line[n] = 0;
        int w, h;
        if (sscanf(line, "prompt %63s %d %d %lf", name, &w, &h, label) == 4 && strcmp(name, resref) == 0)
            return 1;
    }
    return 0;
}

static void append(uint8_t **buffer, size_t *size, size_t *room, const void *data, size_t n) {
    if (*size + n > *room) {
        *room = (*size + n) * 2;
        *buffer = realloc(*buffer, *room);
    }
    memcpy(*buffer + *size, data, n);
    *size += n;
}

/* SETDIR's manifest with each row's button size the blended one, each widened screen's
 * widening and each fitted list's change this blend's; every other byte as it was, line ends
 * included. */
static uint8_t *rewrite_manifest(const uint8_t *text, size_t size, const Badges *B, const int *sizes,
                                 const Fit *fits, uint32_t fit_count, const int32_t *widened,
                                 const RowFit *row_fits, uint32_t row_fit_count, const int32_t *fitted,
                                 size_t *out_size) {
    uint8_t *out = NULL;
    size_t used = 0, room = 0;
    uint32_t rows = 0;
    for (size_t at = 0, n; at < size; at += n) {
        n = next_line(text, size, at);
        const char *line = (const char *)text + at;
        char head[512];
        if (n > 7 && memcmp(line, "prompt ", 7) == 0) {
            /* "prompt", the resref, the two sizes, then the rest as it was. */
            size_t f[4], k = 0;
            for (size_t i = 0; i < n && k < 4; i++)
                if (line[i] == ' ') f[k++] = i;
            if (k < 4 || f[1] - f[0] - 1 >= 32) { fprintf(stderr, "kmrp-guiblend: a prompt manifest row is malformed\n"); return NULL; }
            char resref[32];
            memcpy(resref, line + f[0] + 1, f[1] - f[0] - 1);
            resref[f[1] - f[0] - 1] = 0;
            uint32_t i = 0;
            while (i < B->prompt_count && strcmp(B->prompts[i].resref, resref) != 0) i++;
            if (i == B->prompt_count) { fprintf(stderr, "kmrp-guiblend: the table has no badge %s\n", resref); return NULL; }
            int m = snprintf(head, sizeof head, "prompt %s %d %d", resref, sizes[i * 2], sizes[i * 2 + 1]);
            append(&out, &used, &room, head, (size_t)m);
            append(&out, &used, &room, line + f[3], n - f[3]);
            rows++;
            continue;
        }
        if (n > 8 && memcmp(line, "widened ", 8) == 0) {
            size_t g = 8, e;
            while (g < n && line[g] != ' ') g++;
            for (e = g + 1; e < n && line[e] >= '0' && line[e] <= '9'; e++) {}
            uint32_t i = 0;
            while (i < fit_count && (strlen(fits[i].name) != g - 8 || memcmp(fits[i].name, line + 8, g - 8) != 0)) i++;
            if (i < fit_count && g < n) {
                int m = snprintf(head, sizeof head, "widened %s %d", fits[i].name, widened[i]);
                append(&out, &used, &room, head, (size_t)m);
                append(&out, &used, &room, line + e, n - e);
                continue;
            }
        }
        if (n > 7 && memcmp(line, "fitted ", 7) == 0) {
            /* "fitted", the .gui, the list's tag, the change (it may be negative). */
            size_t g = 7, t, e;
            while (g < n && line[g] != ' ') g++;
            for (t = g + 1; t < n && line[t] != ' '; t++) {}
            e = t + 1;
            if (e < n && line[e] == '-') e++;
            while (e < n && line[e] >= '0' && line[e] <= '9') e++;
            uint32_t i = 0;
            while (i < row_fit_count &&
                   (strlen(row_fits[i].name) != g - 7 || memcmp(row_fits[i].name, line + 7, g - 7) != 0 ||
                    t >= n || strlen(row_fits[i].tag) != t - g - 1 || memcmp(row_fits[i].tag, line + g + 1, t - g - 1) != 0))
                i++;
            if (i < row_fit_count) {
                int m = snprintf(head, sizeof head, "fitted %s %s %d", row_fits[i].name, row_fits[i].tag, fitted[i]);
                append(&out, &used, &room, head, (size_t)m);
                append(&out, &used, &room, line + e, n - e);
                continue;
            }
        }
        append(&out, &used, &room, line, n);
    }
    if (rows != B->prompt_count) {
        fprintf(stderr, "kmrp-guiblend: the manifest lists %u badges, the table %u\n", rows, B->prompt_count);
        return NULL;
    }
    *out_size = used;
    return out;
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
    if (argc != 4 && argc != 6) {
        fprintf(stderr, "usage: kmrp-guiblend TABLE WIDTH HEIGHT [OUTDIR PROMPTS]\n");
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
    if (!take(magic, 4) || memcmp(magic, "KGBL", 4) != 0 || take_u32() != 4) {
        fprintf(stderr, "kmrp-guiblend: not a version 4 blend table\n");
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
    uint32_t fit_count = take_u32();
    if (fit_count > 4) { fprintf(stderr, "kmrp-guiblend: bad fit count\n"); return 1; }
    Fit fits[4];
    for (uint32_t i = 0; i < fit_count; i++) {
        Fit *fit = &fits[i];
        if (!take_text(fit->name, sizeof fit->name) || !take_text(fit->row, sizeof fit->row) ||
            !take(&fit->radius_short, 8) || !take(&fit->radius, 8)) {
            fprintf(stderr, "kmrp-guiblend: bad fit record\n");
            return 1;
        }
        fit->short_below = take_u32();
        take(&fit->gap, 8);
        take(&fit->edge, 8);
        fit->left = take_u32();
        fit->width = take_u32();
        fit->button_width = take_u32();
        fit->button_height = take_u32();
        fit->count = take_u32();
        if (fit->count > 16) { fprintf(stderr, "kmrp-guiblend: bad fit record\n"); return 1; }
        for (uint32_t k = 0; k < fit->count; k++) fit->widths[k] = take_u32();
    }
    uint32_t layout_count = take_u32();
    if (layout_count > 1) { fprintf(stderr, "kmrp-guiblend: bad layout count\n"); return 1; }
    static Layout layouts[1];
    for (uint32_t i = 0; i < layout_count; i++) {
        Layout *l = &layouts[i];
        if (!take_text(l->name, sizeof l->name) || !take_text(l->font, sizeof l->font)) {
            fprintf(stderr, "kmrp-guiblend: bad layout record\n");
            return 1;
        }
        l->constants = take_u32();
        if (l->constants > 96) { fprintf(stderr, "kmrp-guiblend: bad layout record\n"); return 1; }
        for (uint32_t k = 0; k < l->constants; k++)
            if (!take_text(l->constant_names[k], sizeof l->constant_names[k]) || !take(&l->constant_values[k], 8)) {
                fprintf(stderr, "kmrp-guiblend: bad layout record\n");
                return 1;
            }
        l->rows = take_u32();
        if (l->rows > 32) { fprintf(stderr, "kmrp-guiblend: bad layout record\n"); return 1; }
        for (uint32_t k = 0; k < l->rows; k++) {
            uint8_t side = 0;
            if (!take(&side, 1) || !take(&l->row[k].glyph_x, 8) || !take(&l->row[k].row_y, 8) ||
                !take_text(l->row[k].caption, sizeof l->row[k].caption)) {
                fprintf(stderr, "kmrp-guiblend: bad layout record\n");
                return 1;
            }
            l->row[k].side = (char)side;
        }
        l->root_width = take_u32();
        l->root_height = take_u32();
        l->controls = take_u32();
        if (l->controls > 96) { fprintf(stderr, "kmrp-guiblend: bad layout record\n"); return 1; }
        for (uint32_t k = 0; k < l->controls; k++)
            for (int e = 0; e < 4; e++) l->extent[k][e] = take_u32();
        /* build_gui's control count, which generate() writes in order. */
        const uint32_t expected = 10 + 2 * (uint32_t)constant(l, "ROWS") + (uint32_t)constant(l, "DECOR_COUNT") + 1;
        if (l->controls != expected || l->rows != (uint32_t)constant(l, "ROWS")) {
            fprintf(stderr, "kmrp-guiblend: %s: %u controls, the layout makes %u\n", l->name, l->controls, expected);
            return 1;
        }
    }
    uint32_t row_fit_count = take_u32();
    if (row_fit_count > 16) { fprintf(stderr, "kmrp-guiblend: bad row-fit count\n"); return 1; }
    static RowFit row_fits[16];
    for (uint32_t i = 0; i < row_fit_count; i++) {
        RowFit *r = &row_fits[i];
        if (!take_text(r->name, sizeof r->name) || !take_text(r->tag, sizeof r->tag) ||
            !take(&r->popup, 1) || !take(&r->loose, 8)) {
            fprintf(stderr, "kmrp-guiblend: bad row-fit record\n");
            return 1;
        }
        r->divisor = take_u32();
        r->bases = take_u32();
        if (r->divisor == 0 || r->bases == 0 || r->bases > 4) { fprintf(stderr, "kmrp-guiblend: bad row-fit record\n"); return 1; }
        for (uint32_t k = 0; k < r->bases; k++) r->base[k] = take_u32();
        r->height = take_u32();
        r->dimension = take_u32();
        r->bar = take_u32();
        r->panel_top = take_u32();
        r->panel_height = take_u32();
        r->below = take_u32();
        if (r->below > 16) { fprintf(stderr, "kmrp-guiblend: bad row-fit record\n"); return 1; }
        for (uint32_t k = 0; k < r->below; k++) r->below_top[k] = take_u32();
    }
    static Badges badges;
    badges.texture_w = take_u32();
    badges.texture_h = take_u32();
    take(&badges.radius, 8);
    take(&badges.radius_short, 8);
    badges.short_below = take_u32();
    take(&badges.gap, 8);
    take(&badges.edge, 8);
    take(&badges.center_y, 8);
    take(&badges.fallback_x, 8);
    if (!take(&badges.footer_len, 2) || badges.footer_len > sizeof badges.footer ||
        !take(badges.footer, badges.footer_len) || badges.texture_w == 0 || badges.texture_w > 4096 ||
        badges.texture_h == 0 || badges.texture_h > 4096) {
        fprintf(stderr, "kmrp-guiblend: bad badge record\n");
        return 1;
    }
    badges.glyph_count = take_u32();
    if (badges.glyph_count > 64) { fprintf(stderr, "kmrp-guiblend: bad glyph count\n"); return 1; }
    badges.glyphs = calloc(badges.glyph_count ? badges.glyph_count : 1, sizeof(Glyph));
    for (uint32_t i = 0; i < badges.glyph_count; i++) {
        Glyph *g = &badges.glyphs[i];
        g->width = take_u32();
        g->height = take_u32();
        if (g->width == 0 || g->height == 0 || g->width > 1024 || g->height > 1024 ||
            pos + (size_t)g->width * g->height * 4 > table_size) {
            fprintf(stderr, "kmrp-guiblend: bad glyph\n");
            return 1;
        }
        g->rgba = table + pos;
        pos += (size_t)g->width * g->height * 4;
    }
    badges.prompt_count = take_u32();
    if (badges.prompt_count > 4096) { fprintf(stderr, "kmrp-guiblend: bad prompt count\n"); return 1; }
    badges.prompts = calloc(badges.prompt_count ? badges.prompt_count : 1, sizeof(Prompt));
    for (uint32_t i = 0; i < badges.prompt_count; i++) {
        Prompt *pr = &badges.prompts[i];
        if (!take_text(pr->resref, sizeof pr->resref) || !take_text(pr->gui, sizeof pr->gui)) {
            fprintf(stderr, "kmrp-guiblend: bad prompt record\n");
            return 1;
        }
        pr->width_at = take_u32();
        pr->height_at = take_u32();
        pr->glyph = take_u32();
        if (!take(&pr->backed, 1) || !take(pr->backing, 4)) { fprintf(stderr, "kmrp-guiblend: bad prompt record\n"); return 1; }
        pr->sizing_count = take_u32();
        if (pr->glyph >= badges.glyph_count || pr->sizing_count > 16) {
            fprintf(stderr, "kmrp-guiblend: bad prompt record\n");
            return 1;
        }
        for (uint32_t k = 0; k < pr->sizing_count; k++) pr->sizing[k] = take_u32();
    }
    uint32_t hud_count = take_u32();
    if (hud_count > 1) { fprintf(stderr, "kmrp-guiblend: bad HUD count\n"); return 1; }
    static Hud huds[1];
    for (uint32_t i = 0; i < hud_count; i++) {
        Hud *m = &huds[i];
        if (!take_text(m->gui, sizeof m->gui) || !take_text(m->texture, sizeof m->texture)) {
            fprintf(stderr, "kmrp-guiblend: bad HUD record\n");
            return 1;
        }
        m->width = take_u32();
        m->height = take_u32();
        m->edge_alpha = take_u32();
        m->backdrop_left = take_u32();
        m->backdrop_width = take_u32();
        m->count = take_u32();
        if (m->count > 16 || m->width == 0 || m->width > 4096 || m->height == 0 || m->height > 4096 ||
            m->edge_alpha > 255 || strchr(m->texture, '/') || strchr(m->texture, '\\')) {
            fprintf(stderr, "kmrp-guiblend: bad HUD record\n");
            return 1;
        }
        for (uint32_t k = 0; k < m->count; k++) {
            m->left[k] = take_u32();
            m->button_width[k] = take_u32();
        }
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
    char path[4096];
    double captions[4];
    snprintf(path, sizeof path, "%s/kmrp_prompts.txt", argv[5]);
    for (uint32_t i = 0; i < fit_count; i++)
        if (!caption_width(path, fits[i].row, &captions[i])) {
            fprintf(stderr, "kmrp-guiblend: %s has no row for %s\n", path, fits[i].row);
            return 1;
        }
    static Font fonts[1];
    for (uint32_t i = 0; i < layout_count; i++) {
        snprintf(path, sizeof path, "%s/%s.txi", argv[5], layouts[i].font);
        if (!read_font(path, &fonts[i])) { fprintf(stderr, "kmrp-guiblend: %s: no glyph metrics\n", path); return 1; }
    }
    mkdir(outdir, 0755);
    uint32_t file_count = take_u32();
    Output *outputs = calloc(file_count ? file_count : 1, sizeof(Output));
    int32_t widened[4] = {0, 0, 0, 0};
    int32_t fitted[16] = {0};
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
        /* The row fits first, as the build makes them before widening the Container. */
        for (uint32_t i = 0; i < row_fit_count; i++) {
            const RowFit *r = &row_fits[i];
            if (strcmp(r->name, name) != 0) continue;
            int bad = r->height + 4 > size || r->dimension + 4 > size || r->bar + 4 > size ||
                      r->panel_top + 4 > size || r->panel_height + 4 > size;
            for (uint32_t k = 0; k < r->below; k++) bad |= r->below_top[k] + 4 > size;
            if (bad || (r->popup && (!r->panel_top || !r->panel_height))) {
                fprintf(stderr, "kmrp-guiblend: %s: row fit outside the file\n", name);
                return 1;
            }
            if (fit_rows(r, out, height, &fitted[i])) return 1;
        }
        for (uint32_t i = 0; i < fit_count; i++) {
            if (strcmp(fits[i].name, name) != 0) continue;
            int bad = fits[i].left + 4 > size || fits[i].width + 4 > size ||
                      fits[i].button_width + 4 > size || fits[i].button_height + 4 > size;
            for (uint32_t k = 0; k < fits[i].count; k++) bad |= fits[i].widths[k] + 4 > size;
            if (bad) { fprintf(stderr, "kmrp-guiblend: %s: fit outside the file\n", name); return 1; }
            widened[i] = apply_fit(&fits[i], out, captions[i]);
        }
        for (uint32_t i = 0; i < layout_count; i++) {
            if (strcmp(layouts[i].name, name) != 0) continue;
            int bad = layouts[i].root_width + 4 > size || layouts[i].root_height + 4 > size;
            for (uint32_t k = 0; k < layouts[i].controls; k++)
                for (int e = 0; e < 4; e++) bad |= layouts[i].extent[k][e] + 4 > size;
            if (bad) { fprintf(stderr, "kmrp-guiblend: %s: layout outside the file\n", name); return 1; }
            generate(&layouts[i], &fonts[i], out);
        }
        strcpy(outputs[fi].name, name);
        outputs[fi].data = out;
        outputs[fi].size = size;
        free(offsets);
    }

    /* The badges, each for its blended button, with the label width SETDIR's manifest
     * gives it, and that manifest with the blended button sizes, widening and row fits. */
    snprintf(path, sizeof path, "%s/kmrp_prompts.txt", argv[5]);
    size_t manifest_size = 0;
    uint8_t *manifest = read_file(path, &manifest_size);
    if (!manifest) { fprintf(stderr, "kmrp-guiblend: %s: %s\n", path, strerror(errno)); return 1; }
    int *sizes = calloc((size_t)badges.prompt_count * 2 + 1, sizeof(int));
    for (uint32_t i = 0; i < badges.prompt_count; i++) {
        const Prompt *pr = &badges.prompts[i];
        const Output *gui = NULL;
        for (uint32_t k = 0; k < file_count; k++)
            if (strcmp(outputs[k].name, pr->gui) == 0) gui = &outputs[k];
        int bad = !gui || pr->width_at + 4 > gui->size || pr->height_at + 4 > gui->size;
        for (uint32_t k = 0; !bad && k < pr->sizing_count; k++) bad |= pr->sizing[k] + 4 > gui->size;
        if (bad) { fprintf(stderr, "kmrp-guiblend: %s: its button is outside %s\n", pr->resref, pr->gui); return 1; }
        int cw = get_i32(gui->data, pr->width_at), ch = get_i32(gui->data, pr->height_at), radius_height = 0;
        for (uint32_t k = 0; k < pr->sizing_count; k++) {
            int h = get_i32(gui->data, pr->sizing[k]);
            if (k == 0 || h < radius_height) radius_height = h;
        }
        double label = 0;
        if (cw <= 0 || ch <= 0 || !manifest_label(manifest, manifest_size, pr->resref, &label)) {
            fprintf(stderr, "kmrp-guiblend: %s: no manifest row, or no button\n", pr->resref);
            return 1;
        }
        sizes[i * 2] = cw;
        sizes[i * 2 + 1] = ch;
#ifndef KMRP_NO_CONTROLLER
        size_t tga_size;
        uint8_t *tga = draw_badge(&badges, &badges.glyphs[pr->glyph], cw, ch, label, radius_height,
                                  pr->backed ? pr->backing : NULL, &tga_size);
        snprintf(path, sizeof path, "%s/%s.tga", outdir, pr->resref);
        if (!write_file(path, tga, tga_size)) return 1;
        free(tga);
#endif
    }
    size_t rewritten_size = 0;
    uint8_t *rewritten = rewrite_manifest(manifest, manifest_size, &badges, sizes, fits, fit_count, widened,
                                          row_fits, row_fit_count, fitted, &rewritten_size);
    if (!rewritten) return 1;
    snprintf(path, sizeof path, "%s/kmrp_prompts.txt", outdir);
    if (!write_file(path, rewritten, rewritten_size)) return 1;
    for (uint32_t i = 0; i < hud_count; i++) {
        const Output *gui = NULL;
        for (uint32_t k = 0; k < file_count; k++)
            if (strcmp(outputs[k].name, huds[i].gui) == 0) gui = &outputs[k];
        int bad = !gui || huds[i].backdrop_left + 4 > gui->size || huds[i].backdrop_width + 4 > gui->size;
        for (uint32_t k = 0; !bad && k < huds[i].count; k++)
            bad |= huds[i].left[k] + 4 > gui->size || huds[i].button_width[k] + 4 > gui->size;
        if (bad) { fprintf(stderr, "kmrp-guiblend: %s: its HUD is outside %s\n", huds[i].texture, huds[i].gui); return 1; }
        size_t hud_size;
        uint8_t *tga = draw_hud(&huds[i], gui->data, badges.footer, badges.footer_len, &hud_size);
        if (!tga) return 1;
        snprintf(path, sizeof path, "%s/%s", outdir, huds[i].texture);
        if (!write_file(path, tga, hud_size)) return 1;
        free(tga);
    }
    for (uint32_t fi = 0; fi < file_count; fi++) {
#ifdef KMRP_NO_CONTROLLER
        if (strcmp(outputs[fi].name, "kmrplayout.gui") == 0) { free(outputs[fi].data); continue; }
#endif
        snprintf(path, sizeof path, "%s/%s", outdir, outputs[fi].name);
        if (!write_file(path, outputs[fi].data, outputs[fi].size)) return 1;
        free(outputs[fi].data);
    }
    return 0;
}

#ifdef KMRP_GUI_EMBEDDED
/* 1 when the finished sets reach WIDTHxHEIGHT: the tool's own answer with no output
 * directory, where it stops after choosing its sets (exit status 0), or 2 outside them. */
int KmrpGuiBlendCovers(const char *table_path, unsigned width, unsigned height) {
    char width_text[16], height_text[16];
    snprintf(width_text, sizeof width_text, "%u", width);
    snprintf(height_text, sizeof height_text, "%u", height);
    char *args[] = { "kmrp-guiblend", (char *)table_path, width_text, height_text };
    pos = 0; table = NULL; table_size = 0;
    int result = blend_main(4, args);
    blend_clear();
    table = NULL; table_size = pos = 0;
    return result == 0;
}

int KmrpGuiBlend(const char *table_path, unsigned width, unsigned height,
                 const char *outdir, const char *setdir) {
    char width_text[16], height_text[16];
    snprintf(width_text, sizeof width_text, "%u", width);
    snprintf(height_text, sizeof height_text, "%u", height);
    char *args[] = { "kmrp-guiblend", (char *)table_path, width_text, height_text,
                     (char *)outdir, (char *)setdir };
    pos = 0; table = NULL; table_size = 0;
    int result = blend_main(6, args);
    blend_clear();
    table = NULL; table_size = pos = 0;
    return result;
}
#endif
