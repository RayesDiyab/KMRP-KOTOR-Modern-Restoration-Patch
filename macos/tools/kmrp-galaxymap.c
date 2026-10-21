/* kmrp-galaxymap: the galaxy map's planets where the game's own layout has them, on this
 * size's KMRP map. Made from the player's own game; no release carries the positions.
 *
 *   kmrp-galaxymap KEY SET_GUI OUT_GUI [SOURCE_GUI]
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

#ifndef KMRP_EMBEDDED
int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) { fprintf(stderr, "usage: kmrp-galaxymap KEY SET_GUI OUT_GUI [SOURCE_GUI]\n"); return 2; }
    int result = KmrpGalaxyMap(argv[1], argv[2], argv[3], argc == 5 ? argv[4] : NULL);
    if (result == 0) printf("%s written: the planets where %s has them\n", argv[3], argc == 5 ? argv[4] : "the game");
    if (result == 1) fprintf(stderr, "kmrp-galaxymap: a layout could not be read; nothing written\n");
    if (result == 2) fprintf(stderr, "kmrp-galaxymap: %s: %s\n", argv[3], strerror(errno));
    if (result == 3) printf("%s is not the game's 640x480 layout; nothing written\n", argv[4]);
    return result == 3 ? 0 : result;
}
#endif
