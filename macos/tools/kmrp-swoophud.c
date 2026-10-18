/* kmrp-swoophud: the swoop race's HUD model with its parked speed segment moved out of
 * a wide screen's view. Made from the player's own game; no release carries the file.
 *
 *   kmrp-swoophud KEY OUTDIR WIDTH HEIGHT
 *
 * KEY is the game's chitin.key, whose directory the BIF paths in it are relative to.
 * Writes OUTDIR/m17mg_camera.mdl (changed) and OUTDIR/m17mg_camera.mdx (as it is, so the
 * pair comes from one place).
 *
 * What it is about (issue #47). A swoop race has no layout file: its dashboard, timer and
 * gauges are one model, m17mg_camera, that rides in front of the camera, the same on all
 * three tracks (the player's Models in the MiniGame block of m03mg.are, m17mg.are and
 * m26mg.are). The speed gauge is the node "guagedummy" with ten chevrons under it,
 * Plane01 to Plane10, laid along the node's own z, which on screen runs left to right.
 * The last two are kept out of sight until the bike is that fast, by standing to the
 * left of the screen, and are brought in by the animations "meter8" and "meter9", whose
 * position keys are added to the node's own position:
 *
 *   Plane09   own z -1.55    meter8, meter9: +2.4      beside the gauge, 1.55 to its left
 *   Plane10   own z -99.87   meter9: +100.9            far away
 *
 * The gauge's own z is the camera's x exactly (guagedummy's rotation is the quaternion
 * -0.5 -0.5 -0.5 -0.5, the camera's is none), and the gauge stands 0.476 left of the
 * middle, 1.619 in front of the camera: Plane09 is parked 2.026 left of the middle and
 * is 0.08 wide to either side. The camera's view is 65 degrees high (CameraViewAngle),
 * so at that depth half the view's height is 1.031 and half its width 1.375 at 4:3:
 * the parked chevron is 0.57 outside. Half the width is 1.834 at 16:9, still short of
 * it, and 2.464 at 21:9, where the chevron stands in the picture, red, at the bottom
 * left, the whole race (seen by the maintainer at 3440x1440, 2026-10-13).
 *
 * So Plane09 is parked as far outside this screen as the game parks it outside a 4:3
 * one: 0.57 beyond half the view's width plus the chevron's own 0.08. Its own z, and the
 * same value in its position key in the model, move left by that much, and the
 * animations' keys that bring it in grow by the same, so it arrives where it always did.
 * At 4:3 and narrower nothing needs moving and nothing is written; at 16:9, where the
 * game's spot is only 0.11 outside, it moves 0.46. Only a model that has
 * exactly the game's values is changed; any other is left to the game.
 *
 * Not where the artists parked Plane10. That was the first attempt (2026-10-13): parked
 * 98 units further, the ninth chevron no longer showed at top speed (the maintainer,
 * the same day). The game goes from one animation to the next over a moment, and a
 * chevron that has a hundred units to cross is not at the gauge for most of it; the
 * gauge moves between "meter7" and "meter8" all the time at that speed. With the game's
 * own distance, or little more, it slides in as it always did.
 *
 * The model's layout, as far as this needs it (every offset is from byte 12 of the file):
 *   0x28  root node, 0x58  animations (offset, count), 0xB8  names (offset, count)
 *   node: +0x04 name index (u16), +0x10 position (3 floats), +0x2C children (offset,
 *         count), +0x38 controllers (offset, count), +0x44 controller data (offset)
 *   controller, 16 bytes: type (8 is position), +0x06 rows (u16), +0x0A the first value's
 *         index into the controller data (u16); a row is three floats
 *   animation: +0x28 its root node
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
#define mkdir(path, mode) _mkdir(path)
#else
#include <strings.h>
#include <sys/stat.h>
#endif
#ifdef _MSC_VER
#define fseeko _fseeki64
#endif

#define MODEL "m17mg_camera"
#define NODE "Plane09"
#define TYPE_MDL 2002
#define TYPE_MDX 3008
static const float PARKED = -1.55f, BROUGHT_IN = 2.4f, NEAR_ENOUGH = 0.02f;
/* The gauge and the view, in the model's units at the gauge's depth (see above). */
static const float GAUGE_LEFT_OF_MIDDLE = 0.476f, HALF_HEIGHT = 1.0314f, OUTSIDE = 0.65f;   /* 0.57, and the chevron's own 0.08 */
static float SHIFT;

typedef struct { uint8_t *data; size_t size; } Buffer;

static uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
static float f32(const uint8_t *p) { float f; memcpy(&f, p, 4); return f; }
static void put_f32(uint8_t *p, float f) { memcpy(p, &f, 4); }

static Buffer read_file(const char *path) {
    Buffer b = { NULL, 0 };
    FILE *f = fopen(path, "rb");
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

/* One resource through chitin.key. Only its own bytes are read: models.bif is 950 MB. */
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
            if (size > 0 && size < (64u << 20) && fseeko(f, offset, SEEK_SET) == 0 && (out.data = malloc(size))) {
                if (fread(out.data, 1, size, f) == size) out.size = size;
                else { free(out.data); out.data = NULL; }
            }
        }
        fclose(f);
        return out;
    }
    return none;
}

typedef struct { uint8_t *m; size_t size; uint32_t names, name_count; int visited, changed, strange; } Model;

static int named(const Model *model, uint32_t node, const char *wanted) {
    uint32_t index = u16(model->m + node + 4);
    if (index >= model->name_count) return 0;
    uint32_t at = u32(model->m + model->names + (size_t)index * 4);
    size_t length = strlen(wanted);
    return at + length < model->size && strcasecmp((const char *)model->m + at, wanted) == 0;
}

/* Walks a tree of nodes; at the node, moves what is there. `animation`: its keys are
 * what is added to the node's own position. */
static void walk(Model *model, uint32_t node, int animation, int depth) {
    if (depth > 64 || ++model->visited > 100000 || (size_t)node + 80 > model->size) { model->strange = 1; return; }
    uint8_t *n = model->m + node;
    if (named(model, node, NODE)) {
        if (!animation) {
            float z = f32(n + 16 + 8);
            if (fabsf(z - PARKED) > NEAR_ENOUGH) model->strange = 1;
            else { put_f32(n + 16 + 8, z - SHIFT); model->changed++; }
        }
        uint32_t controllers = u32(n + 56), count = u32(n + 60), values = u32(n + 68);
        if (count > 64 || (size_t)controllers + (size_t)count * 16 > model->size) { model->strange = 1; return; }
        for (uint32_t c = 0; c < count; c++) {
            const uint8_t *controller = model->m + controllers + (size_t)c * 16;
            if (u32(controller) != 8) continue;
            uint32_t rows = u16(controller + 6), first = u16(controller + 10);
            for (uint32_t r = 0; r < rows; r++) {
                size_t at = (size_t)values + ((size_t)first + (size_t)r * 3 + 2) * 4;
                if (at + 4 > model->size) { model->strange = 1; return; }
                float z = f32(model->m + at);
                if (!animation) {
                    if (fabsf(z - PARKED) > NEAR_ENOUGH) model->strange = 1;
                    else { put_f32(model->m + at, z - SHIFT); model->changed++; }
                } else if (fabsf(z - BROUGHT_IN) <= NEAR_ENOUGH) {
                    put_f32(model->m + at, z + SHIFT); model->changed++;
                } else if (fabsf(z) > NEAR_ENOUGH) {
                    model->strange = 1;
                }
            }
        }
    }
    uint32_t children = u32(n + 44), count = u32(n + 48);
    if (count > 4096 || (size_t)children + (size_t)count * 4 > model->size) { model->strange = 1; return; }
    for (uint32_t c = 0; c < count; c++) walk(model, u32(model->m + children + (size_t)c * 4), animation, depth + 1);
}

/* 1 when the model was the game's and is changed; 0 when it is left alone. */
static int park_further(Buffer *mdl) {
    if (mdl->size < 12 + 0xC4) return 0;
    Model model = { mdl->data + 12, mdl->size - 12, 0, 0, 0, 0, 0 };
    uint32_t root = u32(model.m + 0x28), animations = u32(model.m + 0x58), animation_count = u32(model.m + 0x5C);
    model.names = u32(model.m + 0xB8);
    model.name_count = u32(model.m + 0xBC);
    if (model.name_count > 4096 || (size_t)model.names + (size_t)model.name_count * 4 > model.size) return 0;
    if (animation_count > 1024 || (size_t)animations + (size_t)animation_count * 4 > model.size) return 0;
    walk(&model, root, 0, 0);
    int own = model.changed;
    for (uint32_t a = 0; a < animation_count; a++) {
        uint32_t animation = u32(model.m + animations + (size_t)a * 4);
        if ((size_t)animation + 0x2C > model.size) return 0;
        walk(&model, u32(model.m + animation + 0x28), 1, 0);
    }
    /* The node's own position and its one key, and at least one key that brings it in. */
    return !model.strange && own == 2 && model.changed > own;
}

static int write_file(const char *directory, const char *name, const Buffer *b) {
    char path[4096];
    snprintf(path, sizeof path, "%s/%s", directory, name);
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    int ok = fwrite(b->data, 1, b->size, f) == b->size;
    return fclose(f) == 0 && ok;
}

/* 0: written. 1: the game's model is not the one this knows, or cannot be read; nothing
 * is written and the game keeps its own. 2: could not write. 3: this screen is no wider
 * than the game parks the chevron for; nothing is written. */
int KmrpSwoopHud(const char *key_path, const char *outdir, unsigned width, unsigned height) {
    if (!width || !height) return 1;
    /* How far left of the middle the chevron has to be parked on this screen, and how
     * much further that is than the game's 2.026. */
    float wanted = HALF_HEIGHT * (float)width / (float)height + OUTSIDE;
    SHIFT = wanted - (GAUGE_LEFT_OF_MIDDLE - PARKED);
    if (SHIFT < 0.01f) return 3;
    Buffer key = read_file(key_path);
    Buffer mdl = keyed_resource(&key, key_path, MODEL, TYPE_MDL);
    Buffer mdx = keyed_resource(&key, key_path, MODEL, TYPE_MDX);
    int result = 1;
    if (mdl.data && mdx.data && park_further(&mdl)) {
        mkdir(outdir, 0755);
        result = write_file(outdir, MODEL ".mdl", &mdl) && write_file(outdir, MODEL ".mdx", &mdx) ? 0 : 2;
    }
    free(key.data); free(mdl.data); free(mdx.data);
    return result;
}

#ifndef KMRP_EMBEDDED
int main(int argc, char **argv) {
    if (argc != 5) { fprintf(stderr, "usage: kmrp-swoophud KEY OUTDIR WIDTH HEIGHT\n"); return 2; }
    int result = KmrpSwoopHud(argv[1], argv[2], (unsigned)atoi(argv[3]), (unsigned)atoi(argv[4]));
    if (result == 3) printf("the game's own model is right for this screen; nothing written\n");
    if (result == 1) fprintf(stderr, "kmrp-swoophud: %s is not the game's model, or could not be read; nothing written\n", MODEL);
    if (result == 2) fprintf(stderr, "kmrp-swoophud: %s: %s\n", argv[2], strerror(errno));
    if (result == 0) printf("%s.mdl and .mdx written, the chevron parked %.3f further left\n", MODEL, SHIFT);
    return result == 3 ? 0 : result;
}
#endif
