/* kmrp-guiadapt: layouts KMRP adapts for the size in use, at run time.
 *
 *   kmrp-guiadapt galaxy KEY SET_GUI OUT_GUI [SOURCE_GUI]
 *   kmrp-guiadapt mainmenu SET_GUI OUT_GUI
 *   kmrp-guiadapt live KEY|GAME_GUI NAME WIDTH HEIGHT OUT_GUI [SOURCE_GUI|- [PROMPTS]]
 *   kmrp-guiadapt hudcues SOURCE_GUI OUT_GUI
 *
 * Three things, sharing the reading and writing of a layout's EXTENTs: the galaxy map's
 * planets (KmrpGalaxyMap, below), the main menu's buttons on the bars of their art
 * (KmrpMainMenuBars) and Live Adaptive Layout, a screen laid out for the size in use from
 * the game's own file or a mod's (KmrpLiveLayout, at the end).
 *
 * The galaxy map: the planets where the game's own layout has them, on this
 * size's KMRP map. Made from the player's own game; no release carries the positions.
 *
 * KEY is the game's chitin.key. SET_GUI is KMRP's galaxymap.gui for the size in use, OUT_GUI
 * the file written. SOURCE_GUI, when given, is a galaxymap.gui of the player's (a mod's, in
 * Override) whose places are taken instead of the game's own.
 *
 * What it is about (issue 67, and the maintainer, 2026-10-21: "our placement [should be]
 * exactly like vanilla"). Every size's galaxymap.gui came from High Resolution Menus' sets,
 * whose planets and the Xbox Live slots (LBL_Live01..05, which mods use for destinations of
 * their own) were placed by hand, in another arrangement than the game's: Tatooine below the
 * core, Korriban to its right. And a mod that moves a slot ships the game's 640x480 file, which
 * KMRP had to leave to the game, so the map was drawn 640x480 in the middle of the screen.
 *
 * The planets and the slots are labels over 3D_PlanetDisplay, in which the engine draws the
 * galaxy. Measured on the maintainer's PC at 1920x1200 (2026-10-21), the game's 640x480 map in
 * Override against KMRP's: the galaxy is drawn at the height of its rectangle, about its
 * middle, the same scale both ways (2.47 for a rectangle 528 tall against the game's 214,
 * correlation 0.973 over the picture, no offset); a wider rectangle shows more of the space
 * beside it. So a label is placed by its centre, moved from the middle of the source's
 * rectangle by its distance there times (this rectangle's height / the source's), and sized by
 * the same factor: the game's 24-pixel planets are 72 at 3440x1440, the size KMRP had.
 *
 * Only the four numbers of each of those labels' EXTENT change, in place; everything else is
 * KMRP's file as it was. A label the source does not have keeps KMRP's place.
 *
 * GFF, as far as this needs it: the header's six (offset, count) pairs; a structure is
 * (type, data, field count), a field (type, label index, data); 5 is an INT whose value is
 * the data, 10 a CExoString (a length and its characters in the field data), 14 a
 * structure, 15 a list (a count and the structures' indices in the list indices).
 */
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define strcasecmp _stricmp
#define strncasecmp _strnicmp
#else
#include <strings.h>
#endif
#ifdef _MSC_VER
#define fseeko _fseeki64
#endif

#define TYPE_GUI 2047

typedef struct { uint8_t *data; size_t size; } Buffer;

static uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
static void put_u32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

static Buffer read_file(const char *path) {
    Buffer b = { NULL, 0 };
    FILE *f = fopen(path, "rb");
    if (!f) return b;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size > 0 && size < (4L << 20) && (b.data = malloc((size_t)size)) && fread(b.data, 1, (size_t)size, f) == (size_t)size)
        b.size = (size_t)size;
    else { free(b.data); b.data = NULL; }
    fclose(f);
    return b;
}

/* One resource through chitin.key (as kmrp-swoophud.c reads one). */
static Buffer keyed_resource(const Buffer *key, const char *key_path, const char *resref, int type) {
    Buffer none = { NULL, 0 };
    if (!key->data || key->size < 24 || memcmp(key->data, "KEY V1  ", 8) != 0) return none;
    uint32_t bif_count = u32(key->data + 8), key_count = u32(key->data + 12);
    uint32_t file_table = u32(key->data + 16), key_table = u32(key->data + 20);
    for (uint32_t i = 0; i < key_count; i++) {
        size_t at = key_table + (size_t)i * 22;
        if (at + 22 > key->size) break;
        char name[17] = { 0 };
        memcpy(name, key->data + at, 16);
        if (strcasecmp(name, resref) != 0 || u16(key->data + at + 16) != type) continue;
        uint32_t id = u32(key->data + at + 18), bif_index = id >> 20, index = id & 0xFFFFF;
        size_t entry = file_table + (size_t)bif_index * 12;
        if (bif_index >= bif_count || entry + 12 > key->size) return none;
        uint32_t name_offset = u32(key->data + entry + 4);
        uint16_t name_length = u16(key->data + entry + 8);
        char bif_path[4096], relative[512] = { 0 };
        if (name_length >= sizeof relative || (size_t)name_offset + name_length > key->size) return none;
        memcpy(relative, key->data + name_offset, name_length);
        for (char *p = relative; *p; p++) if (*p == '\\') *p = '/';
        const char *slash = strrchr(key_path, '/');
        const char *other = strrchr(key_path, '\\');
        if (other && (!slash || other > slash)) slash = other;
        int dir_length = slash ? (int)(slash - key_path) : 1;
        snprintf(bif_path, sizeof bif_path, "%.*s/%s", dir_length, slash ? key_path : ".", relative);
        FILE *f = fopen(bif_path, "rb");
        if (!f) return none;
        uint8_t head[20], record[16];
        Buffer out = none;
        if (fread(head, 1, 20, f) == 20 && memcmp(head, "BIFFV1  ", 8) == 0 && index < u32(head + 8) &&
            fseeko(f, (long long)u32(head + 16) + (long long)index * 16, SEEK_SET) == 0 &&
            fread(record, 1, 16, f) == 16 && (u32(record) & 0xFFFFF) == index) {
            uint32_t offset = u32(record + 4), size = u32(record + 8);
            if (size > 0 && size < (4u << 20) && fseeko(f, offset, SEEK_SET) == 0 && (out.data = malloc(size))) {
                if (fread(out.data, 1, size, f) == size) out.size = size;
                else { free(out.data); out.data = NULL; }
            }
        }
        fclose(f);
        return out;
    }
    return none;
}

/* A GUI file's sections, checked once. */
typedef struct {
    uint8_t *d; size_t size;
    uint32_t structs, nstructs, fields, nfields, labels, nlabels, values, nvalues, indices, nindices, lists, nlists;
} Gff;

static int gff_open(Gff *g, uint8_t *d, size_t size) {
    if (size < 56 || memcmp(d, "GUI V3.2", 8) != 0) return 0;
    g->d = d; g->size = size;
    uint32_t *slot[12] = { &g->structs, &g->nstructs, &g->fields, &g->nfields, &g->labels, &g->nlabels,
                           &g->values, &g->nvalues, &g->indices, &g->nindices, &g->lists, &g->nlists };
    for (int i = 0; i < 12; i++) *slot[i] = u32(d + 8 + i * 4);
    const uint32_t stride[6] = { 12, 12, 16, 1, 1, 1 };
    for (int i = 0; i < 6; i++) {
        uint64_t end = (uint64_t)*slot[i * 2] + (uint64_t)*slot[i * 2 + 1] * stride[i];
        if (*slot[i * 2] < 56 || end > size) return 0;
    }
    return g->nstructs > 0;
}

/* The field named `name` of structure `s`, or -1. */
static long gff_field(const Gff *g, uint32_t s, const char *name) {
    if (s >= g->nstructs) return -1;
    const uint8_t *st = g->d + g->structs + (size_t)s * 12;
    uint32_t data = u32(st + 4), count = u32(st + 8);
    if (count > g->nfields) return -1;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t f = data;
        if (count != 1) {
            if ((uint64_t)data + (uint64_t)i * 4 + 4 > g->nindices) return -1;
            f = u32(g->d + g->indices + data + i * 4);
        }
        if (f >= g->nfields) return -1;
        uint32_t label = u32(g->d + g->fields + (size_t)f * 12 + 4);
        if (label >= g->nlabels) return -1;
        if (strncmp((const char *)g->d + g->labels + (size_t)label * 16, name, 16) == 0) return (long)f;
    }
    return -1;
}
static uint32_t field_type(const Gff *g, long f) { return u32(g->d + g->fields + (size_t)f * 12); }
static uint8_t *field_data(const Gff *g, long f) { return g->d + g->fields + (size_t)f * 12 + 8; }

/* A structure-valued field's structure, or -1. */
static long gff_child(const Gff *g, uint32_t s, const char *name) {
    long f = gff_field(g, s, name);
    if (f < 0 || field_type(g, f) != 14) return -1;
    uint32_t child = u32(field_data(g, f));
    return child < g->nstructs ? (long)child : -1;
}

/* The control's TAG into `out`, or 0. */
static int control_tag(const Gff *g, uint32_t s, char *out, size_t room) {
    long f = gff_field(g, s, "TAG");
    if (f < 0 || field_type(g, f) != 10) return 0;
    uint32_t at = u32(field_data(g, f));
    if ((uint64_t)at + 4 > g->nvalues) return 0;
    uint32_t n = u32(g->d + g->values + at);
    if (n >= room || (uint64_t)at + 4 + n > g->nvalues) return 0;
    memcpy(out, g->d + g->values + at + 4, n);
    out[n] = 0;
    return 1;
}

/* The four INTs of an EXTENT: pointers to their values, for reading and writing in place. */
typedef struct { uint8_t *v[4]; } Extent;
static int extent_of(const Gff *g, uint32_t s, Extent *e) {
    static const char *names[4] = { "LEFT", "TOP", "WIDTH", "HEIGHT" };
    long ext = gff_child(g, s, "EXTENT");
    if (ext < 0) return 0;
    for (int i = 0; i < 4; i++) {
        long f = gff_field(g, (uint32_t)ext, names[i]);
        if (f < 0 || (field_type(g, f) != 5 && field_type(g, f) != 4)) return 0;
        e->v[i] = field_data(g, f);
    }
    return 1;
}
static int32_t ev(const Extent *e, int i) { return (int32_t)u32(e->v[i]); }

/* The structure of the control tagged `tag`, or -1. */
static long control(const Gff *g, const char *tag) {
    long f = gff_field(g, 0, "CONTROLS");
    if (f < 0 || field_type(g, f) != 15) return -1;
    uint32_t at = u32(field_data(g, f));
    if ((uint64_t)at + 4 > g->nlists) return -1;
    uint32_t n = u32(g->d + g->lists + at);
    if (n > 512 || (uint64_t)at + 4 + (uint64_t)n * 4 > g->nlists) return -1;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t s = u32(g->d + g->lists + at + 4 + i * 4);
        char name[64];
        if (control_tag(g, s, name, sizeof name) && strcasecmp(name, tag) == 0) return (long)s;
    }
    return -1;
}

static int moved_label(const char *tag) {
    return strncasecmp(tag, "LBL_Planet_", 11) == 0 || strncasecmp(tag, "LBL_Live", 8) == 0;
}

/* Map every planet and slot of `source` onto `out` (a copy of KMRP's file). The number moved. */
static int place(Gff *out, const Gff *source) {
    long od = control(out, "3D_PlanetDisplay"), sd = control(source, "3D_PlanetDisplay");
    Extent oe, se;
    if (od < 0 || sd < 0 || !extent_of(out, (uint32_t)od, &oe) || !extent_of(source, (uint32_t)sd, &se)) return -1;
    if (ev(&oe, 3) <= 0 || ev(&se, 3) <= 0) return -1;
    const double scale = (double)ev(&oe, 3) / ev(&se, 3);
    const double ocx = ev(&oe, 0) + ev(&oe, 2) / 2.0, ocy = ev(&oe, 1) + ev(&oe, 3) / 2.0;
    const double scx = ev(&se, 0) + ev(&se, 2) / 2.0, scy = ev(&se, 1) + ev(&se, 3) / 2.0;
    long f = gff_field(out, 0, "CONTROLS");
    if (f < 0 || field_type(out, f) != 15) return -1;
    uint32_t at = u32(field_data(out, f)), n = u32(out->d + out->lists + at);
    int moved = 0;
    for (uint32_t i = 0; i < n && i < 512; i++) {
        uint32_t s = u32(out->d + out->lists + at + 4 + i * 4);
        char tag[64];
        Extent mine, theirs;
        if (!control_tag(out, s, tag, sizeof tag) || !moved_label(tag)) continue;
        long from = control(source, tag);
        if (from < 0 || !extent_of(out, s, &mine) || !extent_of(source, (uint32_t)from, &theirs)) continue;
        if (ev(&theirs, 2) <= 0 || ev(&theirs, 3) <= 0) continue;
        const double cx = ocx + (ev(&theirs, 0) + ev(&theirs, 2) / 2.0 - scx) * scale;
        const double cy = ocy + (ev(&theirs, 1) + ev(&theirs, 3) / 2.0 - scy) * scale;
        const int w = (int)lround(ev(&theirs, 2) * scale), h = (int)lround(ev(&theirs, 3) * scale);
        put_u32(mine.v[0], (uint32_t)(int32_t)lround(cx - w / 2.0));
        put_u32(mine.v[1], (uint32_t)(int32_t)lround(cy - h / 2.0));
        put_u32(mine.v[2], (uint32_t)w);
        put_u32(mine.v[3], (uint32_t)h);
        moved++;
    }
    return moved;
}

/* 0: written. 1: KMRP's file, or the places to take, could not be read; nothing written.
 * 2: could not write. 3: SOURCE is not the game's 640x480 layout; nothing written, and the
 * player's file is left to the game. */
int KmrpGalaxyMap(const char *key_path, const char *set_gui, const char *out_gui, const char *source_gui) {
    Buffer mine = read_file(set_gui), theirs = { NULL, 0 }, key = { NULL, 0 };
    if (source_gui && *source_gui) theirs = read_file(source_gui);
    else {
        key = read_file(key_path);
        theirs = keyed_resource(&key, key_path, "galaxymap", TYPE_GUI);
    }
    int result = 1;
    Gff out, source;
    if (mine.data && theirs.data && gff_open(&out, mine.data, mine.size) && gff_open(&source, theirs.data, theirs.size)) {
        Extent root;
        if (!extent_of(&source, 0, &root)) result = 1;
        else if (ev(&root, 2) != 640 || ev(&root, 3) != 480) result = 3;
        else if (place(&out, &source) > 0) {
            FILE *f = fopen(out_gui, "wb");
            result = 2;
            if (f) {
                int ok = fwrite(mine.data, 1, mine.size, f) == mine.size;
                if (fclose(f) == 0 && ok) result = 0;
            }
        }
    }
    free(mine.data); free(theirs.data); free(key.data);
    return result;
}

/* The main menu's five buttons on the five bars of their art. The menu's art, LBL_MENUBG
 * (lbl_mmenubut, 128 rows), has its bars on rows 3-25, 28-50, 53-75, 78-100 and 103-124,
 * 25 apart, measured on the maintainer's PC at 3440x1440 (2026-10-22), where the art is drawn
 * at three times: bars at 663, 738, 813, 888 and 963 on the screen, 75 apart. The game's own
 * layout puts the buttons 24 apart (BTN_NEWGAME 222, LOADGAME 246, MOVIES 270, OPTIONS 294,
 * EXIT 318 at 640x480, the art at 218), so each caption drifts a row further from its bar,
 * which a pixel hides at 640x480 and six do not at three times (the captions were 6, 3, 0, -3
 * and 5 pixels off their bars' middles; the maintainer: "I feel like they arent [centered]
 * vertically"). Each button is given its bar's rows, by the art's rectangle in this file; its
 * left and width stay. The engine draws a caption's letters about a row of the art below the
 * middle of its button (its line has room under the letters): with the buttons on the bars
 * exactly, the captions stood 2.5 to 3 pixels low at three times, so each button is lifted
 * by LIFT rows. 0: written. 1: not a main menu this knows (no art or a button missing);
 * nothing written. 2: could not write. */
#define LIFT 1.0
static const struct { const char *tag; int top, bottom; } BARS[5] = {
    { "BTN_NEWGAME", 3, 25 }, { "BTN_LOADGAME", 28, 50 }, { "BTN_MOVIES", 53, 75 },
    { "BTN_OPTIONS", 78, 100 }, { "BTN_EXIT", 103, 124 },
};
int KmrpMainMenuBars(const char *set_gui, const char *out_gui) {
    Buffer mine = read_file(set_gui);
    int result = 1;
    Gff g;
    Extent art;
    long a;
    if (mine.data && gff_open(&g, mine.data, mine.size) && (a = control(&g, "LBL_MENUBG")) >= 0 &&
        extent_of(&g, (uint32_t)a, &art) && ev(&art, 3) > 0) {
        Extent button[5];
        int found = 1;
        for (int i = 0; i < 5 && found; i++) {
            long b = control(&g, BARS[i].tag);
            found = b >= 0 && extent_of(&g, (uint32_t)b, &button[i]);
        }
        if (found) {
            const double top = ev(&art, 1), scale = ev(&art, 3) / 128.0;
            for (int i = 0; i < 5; i++) {
                const int y = (int)lround(top + (BARS[i].top - LIFT) * scale);
                const int bottom = (int)lround(top + (BARS[i].bottom - LIFT) * scale);
                put_u32(button[i].v[1], (uint32_t)(int32_t)y);
                put_u32(button[i].v[3], (uint32_t)(bottom - y));
            }
            FILE *f = fopen(out_gui, "wb");
            result = 2;
            if (f) {
                int ok = fwrite(mine.data, 1, mine.size, f) == mine.size;
                if (fclose(f) == 0 && ok) result = 0;
            }
        }
    }
    free(mine.data);
    return result;
}

/* Live Adaptive Layout: a screen's layout, the game's own or a mod's, laid out for the size
 * in use (tools/build_live_layout.py has the method and the measurements; it makes the table
 * and holds the same layout in Python, which testing/regression/Test-LiveLayout.py holds
 * this to). Every structure with an EXTENT (the root, each control by TAG, a list's
 * PROTOITEM and SCROLLBAR) is placed by its rule from its value in the file, with s = H / BH
 * and BW x BH the file's own size (its root's when that fills the screen from 0,0, else
 * 640x480). Where the table has the structure and the file has the game's own extent there,
 * the gold 3440x1440 value carries it, as a ratio, to the size; a control a mod moved keeps
 * the mod's place, by its rule alone, and one the table does not know gets the default rule.
 * Then the build's list gutters (PADDING). Only those numbers change, in place. */
#include "kmrp-livelayout-table.h"

enum { LL_SCALE, LL_STRETCH, LL_FIXED, LL_ASPECT, LL_CENTRE, LL_RIGHT, LL_FRAME, LL_FRAME_INCLUSIVE };
#define LL_LISTBOX 11

/* An INT field of structure `s` (the inline value), or NULL. */
static uint8_t *int_field(const Gff *g, uint32_t s, const char *name) {
    long f = gff_field(g, s, name);
    return f >= 0 && (field_type(g, f) == 5 || field_type(g, f) == 4) ? field_data(g, f) : NULL;
}

/* The root's CONTROLS: their count and where their indices are, or 0. */
static uint32_t controls_of(const Gff *g, uint32_t *at) {
    long f = gff_field(g, 0, "CONTROLS");
    if (f < 0 || field_type(g, f) != 15) return 0;
    *at = u32(field_data(g, f));
    if ((uint64_t)*at + 4 > g->nlists) return 0;
    uint32_t n = u32(g->d + g->lists + *at);
    return n <= 512 && (uint64_t)*at + 4 + (uint64_t)n * 4 <= g->nlists ? n : 0;
}

/* The structures a layout has an EXTENT in, in the order build_live_layout.structures gives
 * them, one at a time: `index` from 0; 0 when there are no more. */
typedef struct { uint32_t s; char tag[64]; const char *sub; int type; } LLStruct;
static int ll_struct(const Gff *g, int index, LLStruct *out) {
    static const char *subs[2] = { "PROTOITEM", "SCROLLBAR" };
    Extent e;
    if (index == 0) {
        out->s = 0; out->tag[0] = 0; out->sub = ""; out->type = -1;
        return 1;
    }
    uint32_t at, n = controls_of(g, &at);
    int k = 1;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        if (c >= g->nstructs) continue;
        char tag[64];
        if (!control_tag(g, c, tag, sizeof tag) || !tag[0]) snprintf(tag, sizeof tag, "#%u", i);
        uint8_t *type = int_field(g, c, "CONTROLTYPE");
        /* The control itself, then its prototype and scroll bar, each where it has an EXTENT. */
        uint32_t found[3];
        const char *names[3];
        int m = 0;
        if (extent_of(g, c, &e)) { found[m] = c; names[m++] = ""; }
        for (int j = 0; j < 2; j++) {
            long sub = gff_child(g, c, subs[j]);
            if (sub >= 0 && extent_of(g, (uint32_t)sub, &e)) { found[m] = (uint32_t)sub; names[m++] = subs[j]; }
        }
        if (index < k + m) {
            out->s = found[index - k];
            memcpy(out->tag, tag, sizeof tag);
            out->sub = names[index - k];
            out->type = type ? (int32_t)u32(type) : -1;
            return 1;
        }
        k += m;
    }
    return 0;
}

static const LLFile *ll_file(const char *name) {
    for (size_t i = 0; i < sizeof LL_FILES / sizeof *LL_FILES; i++)
        if (strcasecmp(LL_FILES[i].name, name) == 0) return &LL_FILES[i];
    return NULL;
}

static const LLRow *ll_row(const LLFile *file, const char *tag, const char *sub) {
    for (int i = 0; i < file->count; i++)
        if (strcmp(file->rows[i].tag, tag) == 0 && strcmp(file->rows[i].sub, sub) == 0) return &file->rows[i];
    return NULL;
}

/* The structure of `g` with this key, or -1. */
static long ll_find(const Gff *g, const char *tag, const char *sub) {
    LLStruct st;
    for (int i = 0; ll_struct(g, i, &st); i++)
        if (strcmp(st.tag, tag) == 0 && strcmp(st.sub, sub) == 0) return (long)st.s;
    return -1;
}

static void ll_base(const Gff *g, int *bw, int *bh) {
    Extent e;
    *bw = 640; *bh = 480;
    if (extent_of(g, 0, &e) && ev(&e, 0) == 0 && ev(&e, 1) == 0 && ev(&e, 2) >= 640 && ev(&e, 3) >= 480) {
        *bw = ev(&e, 2); *bh = ev(&e, 3);
    }
}

static int ll_rhalf(double x) { return (int)copysign(floor(fabs(x) + 0.5), x); }

/* A rule's unrounded value, as build_live_layout.value computes it, operation for operation. */
static double ll_origin(int rule, int field) {
    if (rule != LL_FRAME && rule != LL_FRAME_INCLUSIVE) return 0;
    return field < 2 ? -LL_FRAME_MARGIN : 2 * LL_FRAME_MARGIN + (rule == LL_FRAME_INCLUSIVE && field == 3);
}

static double ll_value(int rule, int field, int v, int w, int width, int height, int bw, int bh) {
    const double s = (double)height / bh;
    switch (rule) {
    case LL_SCALE: return v * s;
    case LL_FIXED: return (double)v;
    case LL_STRETCH: return (double)((long long)v * width) / bw;
    case LL_ASPECT: return field == 0 ? (v + w / 2.0) * width / bw - w * s / 2 : v * s;
    case LL_CENTRE: return field == 0 ? width / 2.0 + (v - bw / 2.0) * s : v * s;
    case LL_RIGHT: return field == 0 ? width - (bw - v) * s : v * s;
    case LL_FRAME:
    case LL_FRAME_INCLUSIVE: {
        const double origin = ll_origin(rule, field);
        const double factor = field == 0 || field == 2 ? (double)width / bw : s;
        return (v - origin) * factor + origin;
    }
    }
    return (double)v;
}

static int ll_default(int field, const char *sub, int type, int w, int h) {
    if (strcmp(sub, "PROTOITEM") == 0) return LL_FIXED;
    if (field == 1 || field == 3) return LL_SCALE;
    if (!*sub && type != LL_LISTBOX && type != -1 && h > 0 && 0.8 <= (double)w / h && (double)w / h <= 1.25)
        return field == 0 ? LL_ASPECT : LL_SCALE;
    return LL_STRETCH;
}

static int ll_placed(int field, int rule, const int v4[4], int gold, int width, int height, int bw, int bh) {
    const double r = ll_value(rule, field, v4[field], v4[2], width, height, bw, bh);
    if (gold == LL_NO_GOLD) return ll_rhalf(r);
    const double at_gold = ll_value(rule, field, v4[field], v4[2], LL_GOLD_WIDTH, LL_GOLD_HEIGHT, bw, bh);
    if (gold == ll_rhalf(at_gold)) return ll_rhalf(r);
    const double origin = ll_origin(rule, field);
    if (at_gold == origin) return ll_rhalf(r + gold - at_gold);
    return ll_rhalf((gold - origin) * ((r - origin) / (at_gold - origin)) + origin);
}

static int ll_gutter(double unit, int height) {
    double scale = height / LL_FONT_HEIGHT_DIVISOR - LL_FONT_SCALE_OFFSET;
    if (scale < 1.0) scale = 1.0;
    return (int)nearbyint(unit * scale);   /* half to even, as Python's round */
}

/* Is `source` laid out for the game's size: the game's own base, and its root inside it? */
static int ll_game_size(const Gff *source, const Gff *game) {
    int sw, sh, gw, gh;
    Extent root;
    ll_base(source, &sw, &sh);
    ll_base(game, &gw, &gh);
    if (sw != gw || sh != gh || !extent_of(source, 0, &root)) return 0;
    return ev(&root, 0) >= 0 && ev(&root, 1) >= 0 && ev(&root, 0) + ev(&root, 2) <= sw && ev(&root, 1) + ev(&root, 3) <= sh;
}

static void ll_fit_rows(Gff *g, const LLRowList *list, int height);
static void ll_centre_rows(Gff *g, int width);
static void ll_fit_journal(Gff *g, int height);
static void ll_widen(Gff *g, double caption);
static long ll_control(const Gff *g, const char *tag, int last_exact);
static int ll_row_height(int base, int height);

/* Redirect only this field to an empty resref. Never zero a shared value payload:
 * a mod may have another field pointing at the same bytes. */
static const uint8_t *ll_resref(const Gff *g, long f) {
    if (f < 0 || field_type(g, f) != 11) return NULL;
    const uint32_t at = u32(field_data(g, f));
    if (at >= g->nvalues) return NULL;
    const uint8_t *p = g->d + g->values + at;
    return *p <= 16 && (uint64_t)at + 1 + *p <= g->nvalues ? p : NULL;
}

static void ll_clear_border(Gff *source, const Gff *game, uint32_t s, long own, unsigned mask) {
    const char *borders[] = {"BORDER", "BORDER", "HILIGHT", "HILIGHT"};
    const char *parts[] = {"CORNER", "EDGE", "CORNER", "EDGE"};
    /* Any existing zero byte in FieldData encodes a valid empty resref. Reusing
     * it changes no payload and needs no appended section. */
    const uint8_t *empty = (const uint8_t *)memchr(source->d + source->values, 0, source->nvalues);
    if (own < 0 || !empty) return;
    for (int bit = 0; bit < 4; ++bit) {
        if (!(mask & (1u << bit))) continue;
        const long sb = gff_child(source, s, borders[bit]), gb = gff_child(game, (uint32_t)own, borders[bit]);
        const long sf = sb >= 0 ? gff_field(source, (uint32_t)sb, parts[bit]) : -1;
        const long gf = gb >= 0 ? gff_field(game, (uint32_t)gb, parts[bit]) : -1;
        const uint8_t *sv = ll_resref(source, sf), *gv = ll_resref(game, gf);
        if (sv && gv && *sv == *gv && memcmp(sv, gv, 1 + *sv) == 0)
            put_u32(field_data(source, sf), (uint32_t)(empty - source->d - source->values));
    }
}

/* `source` laid out in place for width x height. `caption`: the Container's caption width
 * from the size's prompt manifest, or below 0 for none (the Container is then not widened). */
static void ll_layout(const char *name, const LLFile *file, Gff *source, const Gff *game, int width, int height,
                      double caption) {
    int bw, bh;
    ll_base(source, &bw, &bh);
    LLStruct st;
    for (int i = 0; ll_struct(source, i, &st); i++) {
        Extent e;
        if (!extent_of(source, st.s, &e)) continue;
        int v4[4];
        for (int f = 0; f < 4; f++) v4[f] = ev(&e, f);
        const LLRow *row = ll_row(file, st.tag, st.sub);
        int unmoved = 0;
        if (row) {
            long own = ll_find(game, st.tag, st.sub);
            Extent oe;
            unmoved = own >= 0 && extent_of(game, (uint32_t)own, &oe);
            for (int f = 0; f < 4 && unmoved; f++) unmoved = ev(&oe, f) == v4[f];
        }
        int out[4];
        for (int f = 0; f < 4; f++) {
            const int rule = row ? row->rule[f] : ll_default(f, st.sub, st.type, v4[2], v4[3]);
            out[f] = ll_placed(f, rule, v4, unmoved ? row->gold[f] : LL_NO_GOLD, width, height, bw, bh);
        }
        for (int f = 0; f < 4; f++) put_u32(e.v[f], (uint32_t)(int32_t)out[f]);
        uint8_t *padding = int_field(source, st.s, "PADDING");
        if (unmoved && row->gold_padding != LL_NO_PADDING && width == LL_GOLD_WIDTH && height == LL_GOLD_HEIGHT && padding)
            put_u32(padding, (uint32_t)(int32_t)row->gold_padding);
        /* Gold's text alignment, where the file still has the game's own. */
        if (row && row->gold_align != LL_NO_ALIGN) {
            long text = gff_child(source, st.s, "TEXT"), own = ll_find(game, st.tag, st.sub), own_text;
            uint8_t *align = text >= 0 ? int_field(source, (uint32_t)text, "ALIGNMENT") : NULL, *own_align;
            if (align && own >= 0 && (own_text = gff_child(game, (uint32_t)own, "TEXT")) >= 0 &&
                (own_align = int_field(game, (uint32_t)own_text, "ALIGNMENT")) && u32(own_align) == u32(align))
                put_u32(align, (uint32_t)(int32_t)row->gold_align);
        }
        /* And its border's fill style, the same way. */
        if (row && row->gold_fill != LL_NO_FILL) {
            long border = gff_child(source, st.s, "BORDER"), own = ll_find(game, st.tag, st.sub), own_border;
            uint8_t *fill = border >= 0 ? int_field(source, (uint32_t)border, "FILLSTYLE") : NULL, *own_fill;
            if (fill && own >= 0 && (own_border = gff_child(game, (uint32_t)own, "BORDER")) >= 0 &&
                (own_fill = int_field(game, (uint32_t)own_border, "FILLSTYLE")) && u32(own_fill) == u32(fill))
                put_u32(fill, (uint32_t)(int32_t)row->gold_fill);
        }
        if (row && row->clear_border)
            ll_clear_border(source, game, st.s, ll_find(game, st.tag, st.sub), row->clear_border);
    }
    /* The build's gutters, never reducing one but for the hand-set ones. */
    for (int i = 1; ll_struct(source, i, &st); i++) {
        uint8_t *padding;
        if (*st.sub || st.type != LL_LISTBOX || !(padding = int_field(source, st.s, "PADDING"))) continue;
        for (size_t t = 0; t < sizeof LL_GUTTERS / sizeof *LL_GUTTERS; t++) {
            if (strcasecmp(LL_GUTTERS[t].tag, st.tag) != 0) continue;
            const int g = ll_gutter(LL_GUTTERS[t].unit, height);
            if ((int32_t)u32(padding) < g) put_u32(padding, (uint32_t)g);
        }
        for (size_t t = 0; t < sizeof LL_FILE_GUTTERS / sizeof *LL_FILE_GUTTERS; t++)
            if (strcasecmp(LL_FILE_GUTTERS[t].file, name) == 0 && strcasecmp(LL_FILE_GUTTERS[t].tag, st.tag) == 0)
                put_u32(padding, (uint32_t)ll_gutter(LL_FILE_GUTTERS[t].unit, height));
    }
    /* The build's steps after the gutters, in its order: Script Selection's rows centred, the
     * Journal's fitted, the Feedback rows, the lists made as tall as whole rows, and last the
     * Container widened. */
    if (strcasecmp(name, LL_CENTRE_SCREEN) == 0) ll_centre_rows(source, width);
    if (strcasecmp(name, LL_JOURNAL_SCREEN) == 0) ll_fit_journal(source, height);
    /* Checkbox rows are built at their own template height, unlike text rows. */
    if (strcasecmp(name, LL_FEEDBACK_SCREEN) == 0) {
        long c = ll_control(source, LL_FEEDBACK_TAG, 0);
        long proto = c < 0 ? -1 : gff_child(source, (uint32_t)c, "PROTOITEM");
        Extent e;
        if (proto >= 0 && extent_of(source, (uint32_t)proto, &e))
            put_u32(e.v[3], (uint32_t)ll_row_height(ev(&e, 3), height));
    }
    for (int t = 0; t < LL_ROW_LIST_COUNT; t++)
        if (strcasecmp(LL_ROW_LISTS[t].file, name) == 0) ll_fit_rows(source, &LL_ROW_LISTS[t], height);
    if (caption >= 0 && strcasecmp(name, LL_WIDEN_SCREEN) == 0) ll_widen(source, caption);
}

static int ll_r3_screen(const char *name) {
    for (int i = 0; LL_R3_SCREENS[i]; i++)
        if (strcasecmp(LL_R3_SCREENS[i], name) == 0) return 1;
    return 0;
}

/* Python's floor division, for the build's arithmetic on numbers that can be negative. */
static int ll_floordiv(int a, int b) {
    int q = a / b;
    if ((a % b) != 0 && ((a < 0) != (b < 0))) q--;
    return q;
}

/* The control of the root's CONTROLS tagged `tag`, or -1: the first (case-insensitive, as
 * fit_list_to_rows finds it) or the last (exact, as add_party_switch_cue's by_tag keeps it). */
static long ll_control(const Gff *g, const char *tag, int last_exact) {
    uint32_t at, n = controls_of(g, &at);
    long found = -1;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        char name[64];
        if (c >= g->nstructs || !control_tag(g, c, name, sizeof name)) continue;
        if (last_exact ? strcmp(name, tag) == 0 : strcasecmp(name, tag) == 0) {
            found = (long)c;
            if (!last_exact) break;
        }
    }
    return found;
}

/* scale_listbox_padding.row_height: a template row's height at a screen height, the
 * template times max(1, H / 720), both single precision, rounded half to even. */
static int ll_row_height(int base, int height) {
    float scale = (float)(height / 720.0);
    if (scale < 1.0f) scale = 1.0f;
    return (int)nearbyint((double)((float)base * scale));
}

/* scale_listbox_padding.fit_list_to_rows on `g`, in place: the list as tall as whole rows,
 * each an eleventh of a row from the next. A screen's list only shrinks, when a kind of row
 * sits looser than LOOSE_GAP; a popup's grows or shrinks and moves what is below it, its panel
 * kept centred. Nothing changes where the build would stop with an error. */
static void ll_fit_rows(Gff *g, const LLRowList *list, int height) {
    long target = ll_control(g, list->tag, 0), border;
    Extent te, be, root;
    uint8_t *dimension;
    if (target < 0 || !extent_of(g, (uint32_t)target, &te) || (border = gff_child(g, (uint32_t)target, "BORDER")) < 0 ||
        !(dimension = int_field(g, (uint32_t)border, "DIMENSION")) || !extent_of(g, 0, &root)) return;
    const int top = ev(&te, 1), old = ev(&te, 3), inner = old - 2 * (int32_t)u32(dimension);
    int best = 0, loose = 0;
    for (int i = 0; i < list->count; i++) {
        const int row = ll_row_height(list->bases[i], height);
        if (row <= 0) return;
        const int rows = ll_floordiv(inner, row);
        if (rows < 1) return;
        loose |= ll_floordiv(inner - rows * row, rows) > row * LL_LOOSE_GAP;
        const int fit = rows * (row + ll_floordiv(row, LL_ROW_GAP_DIVISOR));
        if (i == 0 || fit > best) best = fit;
    }
    const int change = best - inner;
    if (change == 0 || (!list->popup && (!loose || change > 0))) return;
    long bar = gff_child(g, (uint32_t)target, "SCROLLBAR");
    int bar_ok = bar < 0 || extent_of(g, (uint32_t)bar, &be);
    uint32_t at, n = controls_of(g, &at);
    if (!bar_ok) return;
    if (list->popup)       /* every control's extent is read before anything moves */
        for (uint32_t i = 0; i < n; i++) {
            Extent ce;
            if (!extent_of(g, u32(g->d + g->lists + at + 4 + i * 4), &ce)) return;
        }
    put_u32(te.v[3], (uint32_t)(old + change));
    if (bar >= 0) put_u32(be.v[3], (uint32_t)(ev(&be, 3) + change));
    if (!list->popup) return;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        Extent ce;
        if ((long)c == target || !extent_of(g, c, &ce)) continue;
        if (ev(&ce, 1) >= top + old) put_u32(ce.v[1], (uint32_t)(ev(&ce, 1) + change));
    }
    put_u32(root.v[1], (uint32_t)(ev(&root, 1) - ll_floordiv(change, 2)));
    put_u32(root.v[3], (uint32_t)(ev(&root, 3) + change));
}

/* scale_listbox_padding.centre_rows_in_frame on `g`: Script Selection's list PADDING so its
 * rows sit centred in the box its art draws at fixed fractions of the screen width. The last
 * control so tagged, any case, as the build's loop finds it; a list without a PADDING keeps
 * none (the C adds no fields), and Python leaves it the same way. */
static void ll_centre_rows(Gff *g, int width) {
    uint32_t at, n = controls_of(g, &at);
    long target = -1, bar;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        char name[64];
        if (c < g->nstructs && control_tag(g, c, name, sizeof name) && strcasecmp(name, LL_CENTRE_TAG) == 0)
            target = (long)c;
    }
    Extent te, be;
    uint8_t *padding;
    if (target < 0 || !extent_of(g, (uint32_t)target, &te) || (bar = gff_child(g, (uint32_t)target, "SCROLLBAR")) < 0 ||
        !extent_of(g, (uint32_t)bar, &be) || !(padding = int_field(g, (uint32_t)target, "PADDING"))) return;
    const int left = ev(&te, 0), list_width = ev(&te, 2), bar_width = ev(&be, 2);
    const double frame_left = LL_CENTRE_FRAME_LEFT * width, frame_right = LL_CENTRE_FRAME_RIGHT * width;
    int value = (int)nearbyint(frame_left + frame_right - (left + list_width) - left - bar_width);
    const int most = ll_floordiv(list_width - bar_width, 2) - 1;
    if (value > 255) value = 255;
    if (value > most) value = most;
    if (value < 0) value = 0;
    put_u32(padding, (uint32_t)value);
}

/* scale_listbox_padding.fit_rows_to_list on `g`: the Journal's row template, the largest whose
 * JOURNAL_ROWS rows fill the list with an eleventh of a row between them. Nothing changes
 * where the build would stop with an error. */
static void ll_fit_journal(Gff *g, int height) {
    long target = ll_control(g, LL_JOURNAL_TAG, 0), border, proto;
    Extent te, pe;
    uint8_t *dimension;
    if (target < 0 || !extent_of(g, (uint32_t)target, &te) || (border = gff_child(g, (uint32_t)target, "BORDER")) < 0 ||
        !(dimension = int_field(g, (uint32_t)border, "DIMENSION")) ||
        (proto = gff_child(g, (uint32_t)target, "PROTOITEM")) < 0 || !extent_of(g, (uint32_t)proto, &pe)) return;
    const int inner = ev(&te, 3) - 2 * (int32_t)u32(dimension), rows = LL_JOURNAL_ROWS;
    const double spread = rows * (1 + 1.0 / LL_ROW_GAP_DIVISOR);
    float scale = (float)(height / 720.0);
    if (scale < 1.0f) scale = 1.0f;
#define LL_FITS(t) ((double)(ll_row_height((t), height) * rows) * (1 + 1.0 / LL_ROW_GAP_DIVISOR) <= inner)
    int best = (int)((double)inner / spread / (double)scale);
    for (int guard = 0; !LL_FITS(best); best--)
        if (++guard > 100000) return;
    for (int guard = 0; LL_FITS(best + 1); best++)
        if (++guard > 100000) return;
#undef LL_FITS
    const int row = ll_row_height(best, height);
    if (row <= 0 || ll_floordiv(inner, row) != rows) return;
    put_u32(pe.v[3], (uint32_t)best);
}

/* prepare_universal_resources.widen_container on `g`: the Container's column widened, by an
 * even number of pixels about its centre, until Give Items holds `caption` and its badge
 * (build_controller_prompt_textures.badge_fit_width). Controls by exact TAG, the last of a
 * TAG, as the build's by_tag keeps them; nothing changes when one is missing. */
static void ll_widen(Gff *g, double caption) {
    long widened[sizeof LL_WIDENED / sizeof *LL_WIDENED];
    Extent ext[sizeof LL_WIDENED / sizeof *LL_WIDENED], root;
    for (size_t i = 0; i < sizeof LL_WIDENED / sizeof *LL_WIDENED; i++)
        if ((widened[i] = ll_control(g, LL_WIDENED[i], 1)) < 0 || !extent_of(g, (uint32_t)widened[i], &ext[i])) return;
    long button = ll_control(g, LL_WIDEN_TAG, 1), border, corner;
    Extent be;
    if (button < 0 || !extent_of(g, (uint32_t)button, &be) || !extent_of(g, 0, &root) ||
        (border = gff_child(g, (uint32_t)button, "BORDER")) < 0 ||
        (corner = gff_field(g, (uint32_t)border, "CORNER")) < 0) return;
    const uint8_t *art = ll_resref(g, corner);
    if (!art) return;
    int inset = 0;
    if (*art) {   /* fill_inset: corner art insets the fill by the border's DIMENSION */
        uint8_t *dimension = int_field(g, (uint32_t)border, "DIMENSION");
        if (!dimension || (int32_t)u32(dimension) <= 0) return;
        inset = (int32_t)u32(dimension);
    }
    const int h = ev(&be, 3);
    double radius = h * (h < LL_BADGE_SHORT_BELOW ? LL_BADGE_RADIUS_SHORT : LL_BADGE_RADIUS);
    if (inset > 0) radius = fmin(radius, (h - 2 * inset) / 2.0 - LL_FIT_MARGIN);
    const double need = caption + 2.0 * (inset + radius * (LL_BADGE_GAP + 1.0 + LL_BADGE_EDGE));
    int extra = (int)ceil(need - ev(&be, 2));
    if (extra <= 0) return;
    extra += extra % 2;
    put_u32(root.v[0], (uint32_t)(ev(&root, 0) - extra / 2));
    put_u32(root.v[2], (uint32_t)(ev(&root, 2) + extra));
    for (size_t i = 0; i < sizeof LL_WIDENED / sizeof *LL_WIDENED; i++)
        put_u32(ext[i].v[2], (uint32_t)(ev(&ext[i], 2) + extra));
}

/* A GFF written again with structures added: every section copied as it is and new entries
 * appended at its end, so every offset already in the file stays right. */
typedef struct { uint8_t *d; size_t n, cap; } Grow;
static int grow(Grow *b, const void *p, size_t n) {
    if (b->n + n > b->cap) {
        size_t cap = b->cap ? b->cap * 2 : 4096;
        while (cap < b->n + n) cap *= 2;
        uint8_t *d = realloc(b->d, cap);
        if (!d) return 0;
        b->d = d; b->cap = cap;
    }
    if (n) memcpy(b->d + b->n, p, n);
    b->n += n;
    return 1;
}
static int grow_u32(Grow *b, uint32_t v) { uint8_t p[4]; put_u32(p, v); return grow(b, p, 4); }
typedef struct { Grow s, f, l, d, i, li; int ok; } Sections;

/* The `k`th field of structure `s`, or -1. */
static long ll_field_at(const Gff *g, uint32_t s, uint32_t k) {
    const uint8_t *st = g->d + g->structs + (size_t)s * 12;
    uint32_t data = u32(st + 4), count = u32(st + 8);
    if (k >= count) return -1;
    if (count == 1) return data < g->nfields ? (long)data : -1;
    if ((uint64_t)data + (uint64_t)k * 4 + 4 > g->nindices) return -1;
    uint32_t f = u32(g->d + g->indices + data + k * 4);
    return f < g->nfields ? (long)f : -1;
}

/* What the cue's clone changes: by the role of the structure being cloned. */
enum { ROLE_NONE, ROLE_CUE, ROLE_EXTENT, ROLE_BORDER, ROLE_TEXT };
/* caption != NULL clones an entry button's border unchanged, with that caption. */
typedef struct { int id, box[4]; const char *tag, *fill, *caption; } CueValues;

static int ll_label_is(const Gff *g, long f, const char *name) {
    uint32_t label = u32(g->d + g->fields + (size_t)f * 12 + 4);
    return label < g->nlabels && strncmp((const char *)g->d + g->labels + (size_t)label * 16, name, 16) == 0;
}

static uint32_t ll_clone_struct(const Gff *g, uint32_t s, Sections *out, int role, const CueValues *cue);

/* One field of a clone: its label kept; inline values copied, complex data shared (it is only
 * read), structures and lists cloned; the cue's own values written with pykotor's types. */
static uint32_t ll_clone_field(const Gff *g, long f, Sections *out, int role, const CueValues *cue) {
    const uint8_t *entry = g->d + g->fields + (size_t)f * 12;
    uint32_t type = u32(entry), label = u32(entry + 4), data = u32(entry + 8);
    int set_int = 0, int_type = 5;
    int32_t int_value = 0;
    const char *text = NULL;
    int text_type = 10;
    if (role == ROLE_CUE && ll_label_is(g, f, "TAG")) { text = cue->tag; text_type = 10; }
    else if (role == ROLE_CUE && ll_label_is(g, f, "ID")) { set_int = 1; int_value = cue->id; }
    else if (role == ROLE_EXTENT) {
        static const char *names[4] = { "LEFT", "TOP", "WIDTH", "HEIGHT" };
        for (int k = 0; k < 4; k++)
            if (ll_label_is(g, f, names[k])) { set_int = 1; int_value = cue->box[k]; }
    } else if (role == ROLE_BORDER && !cue->caption) {
        if (ll_label_is(g, f, "FILL")) { text = cue->fill; text_type = 11; }
        else if (ll_label_is(g, f, "CORNER") || ll_label_is(g, f, "EDGE")) { text = ""; text_type = 11; }
        else if (ll_label_is(g, f, "DIMENSION")) { set_int = 1; int_value = 0; }
    } else if (role == ROLE_TEXT) {
        if (ll_label_is(g, f, "TEXT")) { text = cue->caption ? cue->caption : ""; text_type = 10; }
        else if (ll_label_is(g, f, "STRREF")) { set_int = 1; int_type = 4; int_value = (int32_t)0xFFFFFFFFu; }
    }
    if (set_int) { type = (uint32_t)int_type; data = (uint32_t)int_value; }
    else if (text) {
        size_t n = strlen(text);
        type = (uint32_t)text_type;
        data = (uint32_t)out->d.n;
        if (text_type == 11) { uint8_t len = (uint8_t)n; out->ok &= grow(&out->d, &len, 1); }
        else out->ok &= grow_u32(&out->d, (uint32_t)n);
        out->ok &= grow(&out->d, text, n);
    } else if (type == 14) {
        int child = ROLE_NONE;
        if (role == ROLE_CUE && ll_label_is(g, f, "EXTENT")) child = ROLE_EXTENT;
        if (role == ROLE_CUE && ll_label_is(g, f, "BORDER")) child = ROLE_BORDER;
        if (role == ROLE_CUE && ll_label_is(g, f, "TEXT")) child = ROLE_TEXT;
        data = data < g->nstructs ? ll_clone_struct(g, data, out, child, cue) : (out->ok = 0);
    } else if (type == 15) {
        uint32_t n = (uint64_t)data + 4 <= g->nlists ? u32(g->d + g->lists + data) : 0;
        if (n > 4096 || (uint64_t)data + 4 + (uint64_t)n * 4 > g->nlists) { out->ok = 0; n = 0; }
        uint32_t *items = n ? malloc(n * sizeof *items) : NULL;
        for (uint32_t k = 0; k < n && items; k++) {
            uint32_t c = u32(g->d + g->lists + data + 4 + k * 4);
            items[k] = c < g->nstructs ? ll_clone_struct(g, c, out, ROLE_NONE, cue) : (out->ok = 0);
        }
        if (n && !items) out->ok = 0;
        data = (uint32_t)out->li.n;
        out->ok &= grow_u32(&out->li, n);
        for (uint32_t k = 0; k < n && items; k++) out->ok &= grow_u32(&out->li, items[k]);
        free(items);
    }
    uint32_t index = (uint32_t)(out->f.n / 12);
    out->ok &= grow_u32(&out->f, type) && grow_u32(&out->f, label) && grow_u32(&out->f, data);
    return index;
}

static uint32_t ll_clone_struct(const Gff *g, uint32_t s, Sections *out, int role, const CueValues *cue) {
    const uint8_t *st = g->d + g->structs + (size_t)s * 12;
    uint32_t type = u32(st), count = u32(st + 8);
    if (count > 4096) { out->ok = 0; count = 0; }
    /* Native localized buttons have STRREF without a TEXT string. add_entry's
     * text() creates it; reuse the outer TEXT field's existing label here. */
    const int caption_field = role == ROLE_TEXT && cue->caption && gff_field(g, s, "TEXT") < 0;
    const uint32_t final_count = count + caption_field;
    /* The structure's entry first, so the clone's index is known; its fields after. */
    uint32_t index = (uint32_t)(out->s.n / 12);
    out->ok &= grow_u32(&out->s, type) && grow_u32(&out->s, 0) && grow_u32(&out->s, final_count);
    uint32_t *fields = final_count ? malloc(final_count * sizeof *fields) : NULL;
    for (uint32_t k = 0; k < count && fields; k++) {
        long f = ll_field_at(g, s, k);
        fields[k] = f >= 0 ? ll_clone_field(g, f, out, role, cue) : (out->ok = 0);
    }
    if (final_count && !fields) out->ok = 0;
    if (caption_field && fields) {
        uint32_t label = 0;
        while (label < g->nlabels && strncmp((const char *)g->d + g->labels + (size_t)label * 16, "TEXT", 16) != 0) label++;
        if (label == g->nlabels) out->ok = 0;
        const uint32_t data = (uint32_t)out->d.n;
        const size_t length = strlen(cue->caption);
        out->ok &= grow_u32(&out->d, (uint32_t)length) && grow(&out->d, cue->caption, length);
        fields[count] = (uint32_t)(out->f.n / 12);
        out->ok &= grow_u32(&out->f, 10) && grow_u32(&out->f, label) && grow_u32(&out->f, data);
    }
    uint32_t data = 0;
    if (final_count == 1 && fields) data = fields[0];
    else if (final_count > 1 && fields) {
        data = (uint32_t)out->i.n;
        for (uint32_t k = 0; k < final_count; k++) out->ok &= grow_u32(&out->i, fields[k]);
    }
    if (out->ok) put_u32(out->s.d + (size_t)index * 12 + 4, data);
    free(fields);
    return index;
}

/* Does extent `b` overlap the square (x, y, size)? */
static int ll_overlaps(const Extent *b, int x, int y, int size) {
    return x < ev(b, 0) + ev(b, 2) && ev(b, 0) < x + size && y < ev(b, 1) + ev(b, 3) && ev(b, 1) < y + size;
}

/* Append one cue without changing existing field offsets or shared template data. */
static int ll_append_cue(const Gff *g, long template, const CueValues *values, Buffer *out) {
    uint32_t at, n = controls_of(g, &at);
    long border;
    Extent te;
    if (template < 0 || !int_field(g, (uint32_t)template, "ID") || gff_field(g, (uint32_t)template, "TAG") < 0 ||
        !extent_of(g, (uint32_t)template, &te) || (border = gff_child(g, (uint32_t)template, "BORDER")) < 0 ||
        gff_field(g, (uint32_t)border, "FILL") < 0) return 0;
    Sections s = { { 0 }, { 0 }, { 0 }, { 0 }, { 0 }, { 0 }, 1 };
    s.ok &= grow(&s.s, g->d + g->structs, (size_t)g->nstructs * 12) && grow(&s.f, g->d + g->fields, (size_t)g->nfields * 12) &&
            grow(&s.l, g->d + g->labels, (size_t)g->nlabels * 16) && grow(&s.d, g->d + g->values, g->nvalues) &&
            grow(&s.i, g->d + g->indices, g->nindices) && grow(&s.li, g->d + g->lists, g->nlists);
    const uint32_t cue = ll_clone_struct(g, (uint32_t)template, &s, ROLE_CUE, values);
    /* The controls again, at the end of the list indices, with the cue last. */
    long controls = gff_field(g, 0, "CONTROLS");
    if (controls >= 0 && s.ok) {
        const uint32_t list = (uint32_t)s.li.n;
        s.ok &= grow_u32(&s.li, n + 1);
        for (uint32_t i = 0; i < n; i++) s.ok &= grow_u32(&s.li, u32(g->d + g->lists + at + 4 + i * 4));
        s.ok &= grow_u32(&s.li, cue);
        if (s.ok) put_u32(s.f.d + (size_t)controls * 12 + 8, list);
    }
    int done = 0;
    Grow file = { 0 };
    if (controls >= 0 && s.ok) {
        const Grow *parts[6] = { &s.s, &s.f, &s.l, &s.d, &s.i, &s.li };
        const size_t counts[6] = { s.s.n / 12, s.f.n / 12, s.l.n / 16, s.d.n, s.i.n, s.li.n };
        uint32_t offset = 56;
        done = grow(&file, g->d, 8);
        for (int k = 0; k < 6; k++) {
            done &= grow_u32(&file, offset) && grow_u32(&file, (uint32_t)counts[k]);
            offset += (uint32_t)parts[k]->n;
        }
        for (int k = 0; k < 6; k++) done &= grow(&file, parts[k]->d, parts[k]->n);
    }
    free(s.s.d); free(s.f.d); free(s.l.d); free(s.d.d); free(s.i.d); free(s.li.d);
    if (!done) { free(file.d); return 0; }
    out->data = file.d;
    out->size = file.n;
    return 1;
}

/* prepare_universal_resources.add_party_switch_cue on `g`: the R3 cue, a clone of the first
 * label with its tag, the next ID, its square and its picture, appended to the controls. 1 and
 * `out` the new file; 0 where the build would leave the file as it is or stop with an error. */
static int ll_cue(const Gff *g, Buffer *out) {
    if (ll_control(g, LL_R3_TAG, 1) >= 0) return 0;
    long c1 = ll_control(g, "BTN_CHANGE1", 1), c2 = ll_control(g, "BTN_CHANGE2", 1);
    Extent a, b, root;
    if (c1 < 0 || c2 < 0 || !extent_of(g, (uint32_t)c1, &a) || !extent_of(g, (uint32_t)c2, &b) || !extent_of(g, 0, &root))
        return 0;
    if (ev(&b, 0) < ev(&a, 0) + ev(&a, 2)) return 0;
    int size = ll_floordiv(ev(&a, 3) * LL_R3_PERCENT + 50, 100);   /* r3_cue_size */
    if (size < 1) size = 1;
    const int y = ev(&a, 1) + ll_floordiv(ev(&a, 3) - size, 2);
    const int gap_left = ev(&a, 0) + ev(&a, 2), gap = ev(&b, 0) - gap_left;
    const int x = gap >= size + 2 * (int)(size * LL_R3_MARGIN) ? gap_left + ll_floordiv(gap - size, 2)
                                                                : ev(&b, 0) + ev(&b, 2) + size / 3;
    if (x < 0 || y < 0 || x + size > ev(&root, 2) || y + size > ev(&root, 3)) return 0;
    uint32_t at, n = controls_of(g, &at);
    long template = -1;
    int id = 0, any_id = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        if (c >= g->nstructs) return 0;
        uint8_t *type = int_field(g, c, "CONTROLTYPE");
        const int t = type ? (int32_t)u32(type) : -1;
        if (type && t >= 0 && t < 32 && (LL_R3_BLOCKING >> t) & 1u) {
            Extent ce;
            if (!extent_of(g, c, &ce)) return 0;
            if (ll_overlaps(&ce, x, y, size)) return 0;
        }
        if (template < 0 && type && t == 4) template = (long)c;
        uint8_t *cid = int_field(g, c, "ID");
        if (cid && (!any_id || (int32_t)u32(cid) > id)) { id = (int32_t)u32(cid); any_id = 1; }
    }
    long border;
    Extent te;
    if (template < 0 || !any_id || !int_field(g, (uint32_t)template, "ID") || gff_field(g, (uint32_t)template, "TAG") < 0 ||
        !extent_of(g, (uint32_t)template, &te) || (border = gff_child(g, (uint32_t)template, "BORDER")) < 0 ||
        gff_field(g, (uint32_t)border, "FILL") < 0) return 0;
    const CueValues values = { id + 1, { x, y, size, size }, LL_R3_TAG, LL_R3_FILL };
    return ll_append_cue(g, template, &values, out);
}

static int ll_next_id(const Gff *g, int *id) {
    uint32_t at, n = controls_of(g, &at);
    int any = 0, highest = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        if (c >= g->nstructs) return 0;
        uint8_t *v = int_field(g, c, "ID");
        if (v && (!any || (int32_t)u32(v) > highest)) { highest = (int32_t)u32(v); any = 1; }
    }
    if (!any || highest == INT32_MAX) return 0;
    *id = highest + 1;
    return 1;
}

/* The Abilities swap cue: the build's placement, after the party cue and row fitting. */
static int ll_swap_cue(const Gff *g, Buffer *out) {
    if (ll_control(g, LL_SWAP_TAG, 1) >= 0) return 0;
    long template = -1, beside = ll_control(g, LL_SWAP_BESIDE, 1);
    Extent close;
    if (beside < 0 || !extent_of(g, (uint32_t)beside, &close)) return 0;
    int height = 0;
    for (size_t i = 0; i < sizeof LL_SUBTABS / sizeof *LL_SUBTABS; i++) {
        long c = ll_control(g, LL_SUBTABS[i], 1);
        Extent e;
        if (c < 0 || !extent_of(g, (uint32_t)c, &e)) return 0;
        if (i == 0) template = c;
        if (ev(&e, 3) > height) height = ev(&e, 3);
    }
    const int width = height * LL_SWAP_ASPECT;
    const int x = ev(&close, 0) - ll_floordiv(height, 3) - width;
    const int y = ev(&close, 1) + ll_floordiv(ev(&close, 3) - height, 2);
    if (x < 0) return 0;
    uint32_t at, n = controls_of(g, &at);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        if (c >= g->nstructs) return 0;
        char tag[64] = { 0 };
        control_tag(g, c, tag, sizeof tag);
        if (strcmp(tag, LL_SWAP_BESIDE) == 0) continue;
        uint8_t *type = int_field(g, c, "CONTROLTYPE");
        int t = type ? (int32_t)u32(type) : -1;
        if ((t >= 0 && t < 32 && ((LL_R3_BLOCKING >> t) & 1u)) || strncmp(tag, "LBL_KMRP", 8) == 0) {
            Extent e;
            if (!extent_of(g, c, &e)) return 0;
            if (ev(&e, 0) < x + width && x < ev(&e, 0) + ev(&e, 2) &&
                ev(&e, 1) < y + height && y < ev(&e, 1) + ev(&e, 3)) return 0;
        }
    }
    CueValues values = { 0, { x, y, width, height }, LL_SWAP_TAG, LL_SWAP_FILL };
    return ll_next_id(g, &values.id) && ll_append_cue(g, template, &values, out);
}

/* LT/RT outside the sorted tab strip. Existing cues are preserved as the build does. */
static int ll_tab_cues(const Gff *g, Buffer *out) {
    if (ll_control(g, LL_TAB_TAGS[0], 1) >= 0 || ll_control(g, LL_TAB_TAGS[1], 1) >= 0) return 0;
    int tabs[sizeof LL_TABS / sizeof *LL_TABS][4];
    for (size_t i = 0; i < sizeof LL_TABS / sizeof *LL_TABS; i++) {
        long c = ll_control(g, LL_TABS[i], 1);
        Extent e;
        if (c < 0 || !extent_of(g, (uint32_t)c, &e)) return 0;
        for (int k = 0; k < 4; k++) tabs[i][k] = ev(&e, k);
        /* Python sorts the four-tuples, including ties in LEFT. */
        for (size_t j = i; j > 0; j--) {
            int order = 0;
            for (int k = 0; k < 4 && !order; k++) order = tabs[j][k] < tabs[j-1][k] ? -1 : tabs[j][k] > tabs[j-1][k];
            if (order >= 0) break;
            for (int k = 0; k < 4; k++) { int tmp = tabs[j][k]; tabs[j][k] = tabs[j-1][k]; tabs[j-1][k] = tmp; }
        }
    }
    const size_t last = sizeof LL_TABS / sizeof *LL_TABS - 1;
    const int size = tabs[0][3], gap = ll_floordiv(size, 3), half = ll_floordiv(size, 2);
    const int x[2] = { tabs[0][0] - gap - 2 * half, tabs[last][0] + tabs[last][2] + gap };
    long template = -1;
    uint32_t at, n = controls_of(g, &at);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t c = u32(g->d + g->lists + at + 4 + i * 4);
        if (c >= g->nstructs) return 0;
        uint8_t *type = int_field(g, c, "CONTROLTYPE");
        if (type && u32(type) == 4) { template = c; break; }
    }
    if (template < 0) template = ll_control(g, LL_TABS[0], 1);
    CueValues values = { 0, { x[0], tabs[0][1], size, size }, LL_TAB_TAGS[0], LL_TAB_FILLS[0] };
    if (!ll_next_id(g, &values.id) || values.id == INT32_MAX) return 0;
    Buffer first = { NULL, 0 };
    if (!ll_append_cue(g, template, &values, &first)) return 0;
    Gff next;
    int done = 0;
    values.id++;
    values.box[0] = x[1]; values.tag = LL_TAB_TAGS[1]; values.fill = LL_TAB_FILLS[1];
    if (gff_open(&next, first.data, first.size)) done = ll_append_cue(&next, template, &values, out);
    free(first.data);
    return done;
}

/* prepare_universal_resources.add_combat_cues on `g`: the Y and B cues left of Clear and
 * Disengage, clones of LBL_QUEUE1, square at SCALE of Disengage's height (at least 8), a
 * quarter of that apart (at least 2), centred on each button. 0 where the build would leave
 * the file as it is (a cue is there) or stop (a control missing, a cue off the panel's top or
 * left, the two overlapping). Their places on screen are K1PcHud.cpp's, by the same rule. */
static int ll_combat_cues(const Gff *g, Buffer *out) {
    enum { CUES = sizeof LL_COMBAT_CUES / sizeof *LL_COMBAT_CUES };
    for (int i = 0; i < CUES; i++)
        if (ll_control(g, LL_COMBAT_CUES[i].tag, 1) >= 0) return 0;
    const long template = ll_control(g, LL_COMBAT_TEMPLATE, 1), sizing = ll_control(g, LL_COMBAT_SIZE_BUTTON, 1);
    Extent se;
    if (template < 0 || sizing < 0 || !extent_of(g, (uint32_t)sizing, &se)) return 0;
    int size = (int)nearbyint(ev(&se, 3) * LL_COMBAT_SCALE);   /* Python's round, half to even */
    if (size < 8) size = 8;
    int gap = size / 4;
    if (gap < 2) gap = 2;
    int at[CUES][2];
    for (int i = 0; i < CUES; i++) {
        const long button = ll_control(g, LL_COMBAT_CUES[i].button, 1);
        Extent be;
        if (button < 0 || !extent_of(g, (uint32_t)button, &be)) return 0;
        at[i][0] = ev(&be, 0) - gap - size;
        at[i][1] = ev(&be, 1) + ll_floordiv(ev(&be, 3) - size, 2);
        if (at[i][0] < 0 || at[i][1] < 0) return 0;
    }
    if (!(at[0][1] + size <= at[1][1] || at[1][1] + size <= at[0][1] ||
          at[0][0] + size <= at[1][0] || at[1][0] + size <= at[0][0])) return 0;
    CueValues values = { 0, { at[0][0], at[0][1], size, size }, LL_COMBAT_CUES[0].tag, LL_COMBAT_CUES[0].fill };
    if (!ll_next_id(g, &values.id) || values.id == INT32_MAX) return 0;
    Buffer first = { NULL, 0 };
    if (!ll_append_cue(g, template, &values, &first)) return 0;
    Gff next;
    int done = 0;
    values.id++;
    values.box[0] = at[1][0]; values.box[1] = at[1][1];
    values.tag = LL_COMBAT_CUES[1].tag; values.fill = LL_COMBAT_CUES[1].fill;
    if (gff_open(&next, first.data, first.size)) done = ll_append_cue(&next, template, &values, out);
    free(first.data);
    return done;
}

/* The Gameplay entry, cloned before lifting the original buttons. Publish the new
 * file only after every needed field has been found, so failure leaves the source intact. */
static int ll_gameplay_entry(const Gff *g, Buffer *out) {
    if (ll_control(g, LL_ENTRY_TAG, 1) >= 0) return 0;
    const long key = ll_control(g, LL_ENTRY_TEMPLATE, 1), mouse = ll_control(g, LL_ENTRY_PREVIOUS, 1);
    Extent k, m;
    if (key < 0 || !extent_of(g, (uint32_t)key, &k) || (mouse >= 0 && !extent_of(g, (uint32_t)mouse, &m))) return 0;
    long text = gff_child(g, (uint32_t)key, "TEXT");
    if (text < 0 || gff_field(g, (uint32_t)text, "STRREF") < 0) return 0;
    const int step = mouse >= 0 ? ev(&k, 1) - ev(&m, 1) : (int)nearbyint(ev(&k, 3) * LL_ENTRY_FALLBACK_STEP);
    const int lift = ll_floordiv(step, LL_ENTRY_LIFT_DIVISOR);
    CueValues values = { 0, { ev(&k, 0), ev(&k, 1) + step - lift, ev(&k, 2), ev(&k, 3) },
                        LL_ENTRY_TAG, NULL, LL_ENTRY_CAPTION };
    Buffer next = { NULL, 0 };
    if (!ll_next_id(g, &values.id) || !ll_append_cue(g, key, &values, &next)) return 0;
    Gff changed;
    Extent nk, nm;
    if (!gff_open(&changed, next.data, next.size) || !extent_of(&changed, (uint32_t)key, &nk) ||
        (mouse >= 0 && !extent_of(&changed, (uint32_t)mouse, &nm))) { free(next.data); return 0; }
    put_u32(nk.v[1], (uint32_t)(ev(&k, 1) - lift));
    if (mouse >= 0) put_u32(nm.v[1], (uint32_t)(ev(&m, 1) - lift));
    *out = next;
    return 1;
}

/* Each append preserves the old structures' indices; re-open before the next control. */
static void ll_add_cues(const char *name, Buffer *file) {
    for (int step = 0; step < 3; step++) {
        Gff g;
        Buffer next = { NULL, 0 };
        if (!gff_open(&g, file->data, file->size)) return;
        const int done = step == 0 ? (ll_r3_screen(name) && ll_cue(&g, &next)) : step == 2 ?
            (strcasecmp(name, LL_ENTRY_SCREEN) == 0 && ll_gameplay_entry(&g, &next)) :
            strcasecmp(name, LL_SWAP_SCREEN) == 0 ? ll_swap_cue(&g, &next) :
            strcasecmp(name, LL_TAB_SCREEN) == 0 ? ll_tab_cues(&g, &next) : 0;
        if (done) { free(file->data); *file = next; }
    }
}

/* The layout `name` for width x height into OUT_GUI, from SOURCE_GUI (a mod's, when given)
 * or the game's own; GAME is the game's own file, read through chitin.key when KEY_PATH ends
 * in ".key", else read as it is. 0: written. 1: a layout could not be read; nothing written.
 * 2: could not write. 3: SOURCE is not laid out for the game's size; nothing written, and the
 * player's file is left to the game. 4: not a layout this lays out.
 * KmrpLiveLayoutPrompts: the same, with PROMPTS the size's prompt manifest (kmrp_prompts.txt),
 * whose Give Items caption width the Container is widened for; without it, it is not. */
static int ll_manifest_caption(const char *path, double *width) {
    FILE *f = path && *path ? fopen(path, "r") : NULL;
    if (!f) return 0;
    char line[8192], row[64];
    int found = 0, w, h;
    while (!found && fgets(line, sizeof line, f))
        if (sscanf(line, "prompt %63s %d %d %lf", row, &w, &h, width) == 4 && strcmp(row, LL_WIDEN_CAPTION_ROW) == 0)
            found = 1;
    fclose(f);
    return found;
}

int KmrpLiveLayoutPrompts(const char *key_path, const char *name, const char *source_gui, int width, int height,
                          const char *out_gui, const char *prompts) {
    const LLFile *file = ll_file(name);
    if (!file) return 4;
    double caption = -1;
    if (!ll_manifest_caption(prompts, &caption) || caption < 0) caption = -1;
    Buffer game = { NULL, 0 }, theirs = { NULL, 0 };
    size_t length = strlen(key_path);
    if (length > 4 && strcasecmp(key_path + length - 4, ".key") == 0) {
        Buffer key = read_file(key_path);
        char resref[17] = { 0 };
        const char *dot = strrchr(name, '.');
        size_t n = dot ? (size_t)(dot - name) : strlen(name);
        if (n < sizeof resref) {
            memcpy(resref, name, n);
            game = keyed_resource(&key, key_path, resref, TYPE_GUI);
        }
        free(key.data);
    } else game = read_file(key_path);
    if (source_gui && *source_gui) theirs = read_file(source_gui);
    else if (game.data && (theirs.data = malloc(game.size))) {
        memcpy(theirs.data, game.data, game.size);
        theirs.size = game.size;
    }
    int result = 1;
    Gff own, source;
    if (game.data && theirs.data && width > 0 && height > 0 && gff_open(&own, game.data, game.size) &&
        gff_open(&source, theirs.data, theirs.size)) {
        if (!ll_game_size(&source, &own)) result = 3;
        else {
            ll_layout(name, file, &source, &own, width, height, caption);
            ll_add_cues(name, &theirs);
            FILE *f = fopen(out_gui, "wb");
            result = 2;
            if (f) {
                int ok = fwrite(theirs.data, 1, theirs.size, f) == theirs.size;
                if (fclose(f) == 0 && ok) result = 0;
            }
        }
    }
    free(game.data); free(theirs.data);
    return result;
}

int KmrpLiveLayout(const char *key_path, const char *name, const char *source_gui, int width, int height,
                   const char *out_gui) {
    return KmrpLiveLayoutPrompts(key_path, name, source_gui, width, height, out_gui, NULL);
}

/* A HUD file (a mod's mipc*.gui) with KMRP's combat cues added into OUT_GUI, laid out as it
 * is: KMRP's module places the HUD and the cues itself (K1PcHud.cpp). 0: written. 1: the file
 * could not be read. 2: could not write. 3: nothing to add (it has them, or the build would
 * refuse it); nothing written. */
int KmrpHudCues(const char *source_gui, const char *out_gui) {
    Buffer file = read_file(source_gui), with = { NULL, 0 };
    Gff g;
    int result = 1;
    if (file.data && gff_open(&g, file.data, file.size)) {
        result = 3;
        if (ll_combat_cues(&g, &with)) {
            FILE *f = fopen(out_gui, "wb");
            result = 2;
            if (f) {
                int ok = fwrite(with.data, 1, with.size, f) == with.size;
                if (fclose(f) == 0 && ok) result = 0;
            }
        }
    }
    free(file.data); free(with.data);
    return result;
}

/* Whether a name is one of the HUD files KmrpHudCues is for, and the i-th of them. */
const char *KmrpHudFileName(int i) {
    return i >= 0 && i < (int)(sizeof LL_HUD_FILES / sizeof *LL_HUD_FILES) - 1 ? LL_HUD_FILES[i] : NULL;
}

/* How many layouts KmrpLiveLayout lays out, and the name of one. */
int KmrpLiveLayoutCount(void) { return (int)(sizeof LL_FILES / sizeof *LL_FILES); }
#include "../../src/controller-native/K1GuiPreloadData.h"

/* File-only metadata for the controller's preload worker. No engine objects. */
int KmrpReadPreloadGui(const char *key_path, const char *source, const char *name,
                      K1PreloadClassInfo *info, K1PreloadPicture *pictures, int capacity) {
    Buffer bytes = source && *source ? read_file(source) : (Buffer){NULL, 0};
    if (!bytes.data) {
        Buffer key = read_file(key_path);
        bytes = keyed_resource(&key, key_path, name, TYPE_GUI);
        free(key.data);
    }
    Gff g;
    if (!bytes.data || !gff_open(&g, bytes.data, bytes.size)) { free(bytes.data); return -1; }
    memset(info, 0, sizeof *info);
    Extent box;
    if (extent_of(&g, 0, &box)) for (int i = 0; i < 4; ++i) info->panel[i] = ev(&box, i);
    const long cancel = control(&g, "BTN_BACK");
    if (cancel >= 0 && extent_of(&g, (uint32_t)cancel, &box))
        for (int i = 0; i < 4; ++i) info->cancel[i] = ev(&box, i);
    int count = 0;
    LLStruct st;
    for (int i = 0; ll_struct(&g, i, &st); ++i) {
        if (*st.sub || !extent_of(&g, st.s, &box)) continue;
        for (int which = 0; which < 2; ++which) {
            const long border = gff_child(&g, st.s, which ? "HILIGHT" : "BORDER");
            if (border < 0) continue;
            const uint8_t *fill = ll_resref(&g, gff_field(&g, (uint32_t)border, "FILL"));
            if (!fill || !*fill) continue;
            if (i == 0 && !which) { memcpy(info->fill, fill + 1, *fill); info->fill[*fill] = 0; }
            const uint8_t *corner = ll_resref(&g, gff_field(&g, (uint32_t)border, "CORNER"));
            const uint8_t *dimension = int_field(&g, (uint32_t)border, "DIMENSION");
            const int inset = corner && *corner && dimension ? (int32_t)u32(dimension) : 0;
            if (count < capacity) {
                K1PreloadPicture *p = &pictures[count++];
                memset(p, 0, sizeof *p); memcpy(p->fill, fill + 1, *fill);
                p->width = ev(&box, 2) - 2 * inset; p->height = ev(&box, 3) - 2 * inset;
            }
        }
    }
    free(bytes.data);
    return count;
}
const char *KmrpLiveLayoutName(int i) { return i >= 0 && i < KmrpLiveLayoutCount() ? LL_FILES[i].name : NULL; }

#ifndef KMRP_EMBEDDED
int main(int argc, char **argv) {
    if (argc >= 7 && argc <= 9 && strcmp(argv[1], "live") == 0) {
        /* SOURCE "-": the game's own, for giving PROMPTS without a mod's file. */
        const char *source = argc >= 8 && strcmp(argv[7], "-") != 0 ? argv[7] : NULL;
        int result = KmrpLiveLayoutPrompts(argv[2], argv[3], source, atoi(argv[4]), atoi(argv[5]), argv[6],
                                           argc == 9 ? argv[8] : NULL);
        if (result == 0) printf("%s written: %s laid out for %sx%s\n", argv[6], argv[3], argv[4], argv[5]);
        if (result == 1) fprintf(stderr, "kmrp-guiadapt: a layout could not be read; nothing written\n");
        if (result == 2) fprintf(stderr, "kmrp-guiadapt: %s: %s\n", argv[6], strerror(errno));
        if (result == 3) printf("%s is not laid out for the game's size; nothing written\n", argv[7]);
        if (result == 4) fprintf(stderr, "kmrp-guiadapt: %s is not a layout this lays out\n", argv[3]);
        return result == 3 ? 0 : result;
    }
    if (argc == 4 && strcmp(argv[1], "hudcues") == 0) {
        int result = KmrpHudCues(argv[2], argv[3]);
        if (result == 0) printf("%s written: %s with the combat cues\n", argv[3], argv[2]);
        if (result == 1) fprintf(stderr, "kmrp-guiadapt: %s could not be read\n", argv[2]);
        if (result == 2) fprintf(stderr, "kmrp-guiadapt: %s: %s\n", argv[3], strerror(errno));
        if (result == 3) printf("%s: nothing to add; nothing written\n", argv[2]);
        return result == 3 ? 0 : result;
    }
    if (argc >= 4 && strcmp(argv[1], "mainmenu") == 0) {
        int result = KmrpMainMenuBars(argv[2], argv[3]);
        if (result == 0) printf("%s written: the buttons on their bars\n", argv[3]);
        if (result == 1) fprintf(stderr, "kmrp-guiadapt: %s is not a main menu this knows; nothing written\n", argv[2]);
        if (result == 2) fprintf(stderr, "kmrp-guiadapt: %s: %s\n", argv[3], strerror(errno));
        return result;
    }
    if (argc < 5 || argc > 6 || strcmp(argv[1], "galaxy") != 0) {
        fprintf(stderr, "usage: kmrp-guiadapt galaxy KEY SET_GUI OUT_GUI [SOURCE_GUI]\n"
                        "       kmrp-guiadapt mainmenu SET_GUI OUT_GUI\n");
        return 2;
    }
    int result = KmrpGalaxyMap(argv[2], argv[3], argv[4], argc == 6 ? argv[5] : NULL);
    if (result == 0) printf("%s written: the planets where %s has them\n", argv[4], argc == 6 ? argv[5] : "the game");
    if (result == 1) fprintf(stderr, "kmrp-guiadapt: a layout could not be read; nothing written\n");
    if (result == 2) fprintf(stderr, "kmrp-guiadapt: %s: %s\n", argv[4], strerror(errno));
    if (result == 3) printf("%s is not the game's 640x480 layout; nothing written\n", argv[5]);
    return result == 3 ? 0 : result;
}
#endif
