/* Drives macos/tools/kmrp-guiblend.c's draw_glyph alone, for Test-ControllerGlyphs.py: reads
 * glyphs as controller_glyphs.pack writes them and draws them as the badges do.
 *
 *   glyph_draw_harness JOBS.txt
 *
 * One job per line, all in one run (started once per job, the test took three minutes):
 *
 *   GLYPH.bin OUT.rgba TW TH LEFT TOP DW DH [R G B A]
 *
 * OUT.rgba is the TW x TH sheet, RGBA, top row first; with R G B A it starts as that backing.
 * Every glyph is read into memory of its own and kept, so draw_glyph's cache, which knows a
 * glyph by its address, sees every glyph and size of the run, as in a blend. */
#define main kmrp_guiblend_main
#include "../../macos/tools/kmrp-guiblend.c"
#undef main

static uint8_t *read_job_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    *size = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc(*size ? *size : 1);
    if (fread(data, 1, *size, f) != *size) { fclose(f); return NULL; }
    fclose(f);
    return data;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: glyph_draw_harness JOBS.txt\n");
        return 1;
    }
    FILE *jobs = fopen(argv[1], "r");
    if (!jobs) return 1;
    char line[4096], glyph_path[1024], out_path[1024];
    int done = 0;
    while (fgets(line, sizeof line, jobs)) {
        int tw, th, left, top, dw, dh, rgba[4];
        int n = sscanf(line, "%1023s %1023s %d %d %d %d %d %d %d %d %d %d", glyph_path, out_path,
                       &tw, &th, &left, &top, &dw, &dh, &rgba[0], &rgba[1], &rgba[2], &rgba[3]);
        if (n != 8 && n != 12) continue;
        table = read_job_file(glyph_path, &table_size);
        if (!table) { fprintf(stderr, "glyph_draw_harness: cannot read %s\n", glyph_path); return 1; }
        pos = 0;
        Glyph *g = calloc(1, sizeof(Glyph));
        if (!read_glyph(g) || pos != table_size) {
            fprintf(stderr, "glyph_draw_harness: bad glyph %s\n", glyph_path);
            return 1;
        }
        uint8_t backing[4], *b = NULL;
        uint8_t *sheet = calloc((size_t)tw * th, 4);
        if (n == 12) {
            for (int c = 0; c < 4; c++) backing[c] = (uint8_t)rgba[c];
            b = backing;
            for (int i = 0; i < tw * th; i++) memcpy(&sheet[(size_t)i * 4], b, 4);
        }
        /* Twice: the second drawing is the kept one (glyph_tile's cache), so it is checked too. */
        draw_glyph(g, sheet, tw, th, left, top, dw, dh, b);
        draw_glyph(g, sheet, tw, th, left, top, dw, dh, b);
        FILE *o = fopen(out_path, "wb");
        if (!o) return 1;
        fwrite(sheet, 4, (size_t)tw * th, o);
        fclose(o);
        free(sheet);
        done++;
    }
    fclose(jobs);
    printf("%d\n", done);
    return 0;
}
