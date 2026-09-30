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
 * Two exceptions, since table version 2 (2026-09-30), both done with the fonts of the set
 * the installer takes them from, SETDIR (its files extracted there):
 *   - the Container is widened, in some sets and not others, until "Switch To Give Item"
 *     and its badge fit. The table holds it unwidened, with the rule's fields and constants,
 *     and this applies the rule to the blend as prepare_universal_resources.py's
 *     fit_container_to_caption does, with the caption width SETDIR/kmrp_prompts.txt gives;
 *   - the Controller Layout screen is generated at each resolution, not scaled. This does
 *     build_controller_layout.py's build_gui arithmetic, step for step and in the same order
 *     (the float results must round the same), with every number from the table by name,
 *     the panel size from the blend and the caption font's TXI from SETDIR. The regression
 *     compares the result with build_gui's own, byte for byte, at every size it derives.
 *
 * Exit status: 0 written, 1 usage or I/O error, 2 resolution outside the anchors' range.
 */
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

/* Byte-identical to the Python blend means the same rounding at every step: no fused
 * multiply-add, which clang emits by default on arm64 and which rounds exact .5 ties
 * differently (7 files differed before this, 2026-09-29). */
#pragma STDC FP_CONTRACT OFF

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
/* A caption font as parse_font_metrics reads its TXI, and build_gui's line height. */
typedef struct { double advances[256]; int count; double spacing, line_h; } Font;

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
 * and its badge at the designed gap, by an even number of pixels, the panel about its centre. */
static void apply_fit(const Fit *fit, uint8_t *data, double caption) {
    int32_t height = get_i32(data, fit->button_height);
    double radius = height * (height < (int32_t)fit->short_below ? fit->radius_short : fit->radius);
    double need = caption + 2.0 * radius * (fit->gap + 1.0 + fit->edge);
    int32_t extra = (int32_t)ceil(need - get_i32(data, fit->button_width));
    if (extra <= 0) return;
    extra += extra % 2;
    add_i32(data, fit->left, -(extra / 2));
    add_i32(data, fit->width, extra);
    for (uint32_t i = 0; i < fit->count; i++) add_i32(data, fit->widths[i], extra);
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
    if (!take(magic, 4) || memcmp(magic, "KGBL", 4) != 0 || take_u32() != 2) {
        fprintf(stderr, "kmrp-guiblend: not a version 2 blend table\n");
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
        for (uint32_t i = 0; i < fit_count; i++) {
            if (strcmp(fits[i].name, name) != 0) continue;
            int bad = fits[i].left + 4 > size || fits[i].width + 4 > size ||
                      fits[i].button_width + 4 > size || fits[i].button_height + 4 > size;
            for (uint32_t k = 0; k < fits[i].count; k++) bad |= fits[i].widths[k] + 4 > size;
            if (bad) { fprintf(stderr, "kmrp-guiblend: %s: fit outside the file\n", name); return 1; }
            apply_fit(&fits[i], out, captions[i]);
        }
        for (uint32_t i = 0; i < layout_count; i++) {
            if (strcmp(layouts[i].name, name) != 0) continue;
            int bad = layouts[i].root_width + 4 > size || layouts[i].root_height + 4 > size;
            for (uint32_t k = 0; k < layouts[i].controls; k++)
                for (int e = 0; e < 4; e++) bad |= layouts[i].extent[k][e] + 4 > size;
            if (bad) { fprintf(stderr, "kmrp-guiblend: %s: layout outside the file\n", name); return 1; }
            generate(&layouts[i], &fonts[i], out);
        }
        snprintf(path, sizeof path, "%s/%s", outdir, name);
        FILE *o = fopen(path, "wb");
        if (!o || fwrite(out, 1, size, o) != size || fclose(o) != 0) { fprintf(stderr, "kmrp-guiblend: %s: write failed\n", path); return 1; }
        free(out);
        free(offsets);
    }
    return 0;
}
