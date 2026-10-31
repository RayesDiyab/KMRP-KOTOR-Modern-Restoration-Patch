/* kmrp-merge: a game resource the player's Override has, merged with KMRP's change of it,
 * three ways against vanilla, by its format alone.
 *
 *   kmrp-merge 2da NAME BASE OURS THEIRS OUT
 *
 * BASE is vanilla's resource (from chitin.key), OURS KMRP's change of it (what KMRP would
 * load without the mod), THEIRS the mod's copy in Override, OUT where the merged resource
 * goes: a KMRP-owned folder, never Override. NAME only labels the notes, which go to
 * standard output one a line. Nothing here depends on NAME: any 2DA merges the same way
 * (kmrp-2da.h has the rules). The run time calls KmrpMerge2da with the same bytes
 * (K1RuntimeAssets.cpp, DeriveFromOverrideK1).
 *
 * Exit status: 0 merged and OUT written; 3 not merged safely (OUT not written: the mod's
 * resource is used as it is, and the notes say what of KMRP's that loses; also when the
 * mod's file is not a 2DA KMRP can read); 1 a file could not be read or written, or
 * vanilla's or KMRP's copy is not a 2DA; 2 usage. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kmrp-path.h"
#include "kmrp-2da.h"

/* NAME's three copies merged. 0: *OUT holds the merged resource; 3: not merged safely (the
 * mod's copy is used as it is); 1: vanilla's or KMRP's copy is not a 2DA. *NOTES (always set, free with KmrpMergeFree) holds the notes,
 * and COUNTS, when given, conflicts, lost KMRP changes, rows the mod moved, changes made. */
int KmrpMerge2da(const char *name, const uint8_t *base, size_t base_size, const uint8_t *ours, size_t ours_size,
                 const uint8_t *theirs, size_t theirs_size, uint8_t **out, size_t *out_size, char **notes, int counts[4]) {
    Kmrp2da b, o, t, merged;
    Kmrp2daNotes n = { NULL, 0, 0, 0, 0, 0, 0 };
    *out = NULL; *out_size = 0; *notes = NULL;
    int result = 1;
    const int have_b = kmrp_2da_parse(base, base_size, &b), have_o = kmrp_2da_parse(ours, ours_size, &o),
              have_t = kmrp_2da_parse(theirs, theirs_size, &t);
    if (!have_t) kmrp_2da_note(&n, "%s: the mod's file is not a 2DA KMRP can read; it is used as it is", name);
    else if (!have_b) kmrp_2da_note(&n, "%s: vanilla's table could not be read; the mod's is used as it is", name);
    else if (!have_o) kmrp_2da_note(&n, "%s: KMRP's table could not be read; the mod's is used as it is", name);
    else {
        const int merge = kmrp_2da_merge(name, &b, &o, &t, &merged, &n);
        if (merge == KMRP_2DA_MERGED) {
            Kmrp2daBytes bytes = kmrp_2da_write(&merged);
            if (bytes.data) { *out = bytes.data; *out_size = bytes.size; result = 0; }
            else kmrp_2da_note(&n, "%s: the merged table is too large for a binary 2DA; the mod's is used as it is", name);
            kmrp_2da_free(&merged);
        } else result = 3;
    }
    /* A mod's file that is not a table KMRP can read is a mod's file all the same: not
     * merged, used as it is (3). 1 is kept for vanilla's or KMRP's copy not being one. */
    if (result == 1 && !have_t) result = 3;
    if (have_b) kmrp_2da_free(&b);
    if (have_o) kmrp_2da_free(&o);
    if (have_t) kmrp_2da_free(&t);
    if (counts) { counts[0] = n.conflicts; counts[1] = n.lost; counts[2] = n.moved; counts[3] = n.applied; }
    *notes = n.text ? n.text : kmrp_2da_dup("", 0);
    return result;
}

void KmrpMergeFree(void *p) { free(p); }

#ifndef KMRP_EMBEDDED
static uint8_t *read_all(const char *path, size_t *size) {
    FILE *f = kmrp_fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long length = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = length >= 0 ? (uint8_t *)malloc((size_t)length + 1) : NULL;
    if (data && fread(data, 1, (size_t)length, f) != (size_t)length) { free(data); data = NULL; }
    fclose(f);
    *size = data ? (size_t)length : 0;
    return data;
}

int main(int argc, char **argv) {
    if (argc != 7 || strcmp(argv[1], "2da") != 0) {
        fprintf(stderr, "usage: kmrp-merge 2da NAME BASE OURS THEIRS OUT\n");
        return 2;
    }
    size_t sizes[3];
    uint8_t *files[3];
    for (int i = 0; i < 3; i++)
        if (!(files[i] = read_all(argv[3 + i], &sizes[i]))) { fprintf(stderr, "kmrp-merge: %s: %s\n", argv[3 + i], strerror(errno)); return 1; }
    uint8_t *out;
    size_t out_size;
    char *notes;
    int counts[4];
    int result = KmrpMerge2da(argv[2], files[0], sizes[0], files[1], sizes[1], files[2], sizes[2], &out, &out_size, &notes, counts);
    fputs(notes, stdout);
    printf("conflicts %d, lost %d, moved %d, applied %d\n", counts[0], counts[1], counts[2], counts[3]);
    if (result == 0) {
        FILE *f = kmrp_fopen(argv[6], "wb");
        if (!f || fwrite(out, 1, out_size, f) != out_size || fclose(f) != 0) {
            fprintf(stderr, "kmrp-merge: %s: write failed\n", argv[6]);
            return 1;
        }
    }
    free(out); free(notes);
    for (int i = 0; i < 3; i++) free(files[i]);
    return result;
}
#endif
