/* What the C tools here give the modules that compile them in with KMRP_EMBEDDED. Each tool
 * includes this, so a changed signature stops the build (audit S-8). */
#ifndef KMRP_EMBEDDED_H
#define KMRP_EMBEDDED_H
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* kmrp-guiblend.c */
int KmrpGuiBlend(const char *table_path, unsigned width, unsigned height, const char *outdir, const char *setdir);
int KmrpGuiBlendCovers(const char *table_path, unsigned width, unsigned height);

/* kmrp-abilityicons.c and kmrp-gameart.c */
int KmrpAbilityIcons(const char *erf, unsigned height, const char *outdir, const char *reserved_path);
int KmrpGameArt(const char *erf, const char *key, unsigned height, const char *outdir);
/* A generated picture made again from a mod's copy of its source, as its kmrp_derive.txt line
 * says. 0 written; 1 the mod's picture cannot be read. */
int KmrpDeriveImage(const char *source, int canvas, int picture, int left, int bottom, const char *filter,
                    const char *out);

/* kmrp-swoophud.c: the swoop race's HUD model, its parked speed segment moved out of a wide
 * screen's view (issue #47). 0 written, 1 not the game's model (left alone), 3 the screen is
 * not wide enough to need it. */
int KmrpSwoopHud(const char *key_path, const char *outdir, unsigned width, unsigned height);
/* The same change made on a mod's copy of the model. 0 written; 1 not the game's model where
 * it changes it (the fix is off); 3 not needed at this size. */
int KmrpSwoopHudModel(const char *mdl_path, const char *mdx_path, const char *outdir, unsigned width, unsigned height);

/* kmrp-guiadapt.c: the galaxy map's planets and Live slots where the game's 640x480 layout (or
 * a mod's, in Override) has them, on this size's map (issue 67). 0 written, 1 a layout could
 * not be read, 2 could not write, 3 the mod's file is not 640x480 (left to the game). */
int KmrpGalaxyMap(const char *key_path, const char *set_gui, const char *out_gui, const char *source_gui);
/* The main menu's buttons on the bars of their art. 0 written. */
int KmrpMainMenuBars(const char *set_gui, const char *out_gui);
/* Live Adaptive Layout, a screen the game's own file or a mod's (in Override) lays out, laid
 * out for the size (tools/build_live_layout.py). 0 written, 1 a layout could not be read, 2
 * could not write, 3 the mod's file is not laid out for the game's size (left to the game), 4
 * not a screen it lays out. `set`: the size's set folder, whose kmrp_prompts.txt gives the
 * Container's caption width and whose kmrplayout.gui is the donor of the controller badge
 * labels (confirm.gui's LBL_KMRPA). */
int KmrpLiveLayoutSet(const char *key_path, const char *name, const char *source_gui, int width, int height,
                      const char *out_gui, const char *set);
int KmrpLiveLayoutCount(void);
const char *KmrpLiveLayoutName(int i);
/* What Live Adaptive Layout noted about the last file it laid out. */
const char *KmrpLiveLayoutNotes(void);
/* A mod's mouse and keyboard HUD file with KMRP's combat cues added. 0 written, 3 nothing to
 * add, else not written; and the HUD files' names. */
int KmrpHudCues(const char *source_gui, const char *out_gui);
const char *KmrpHudFileName(int i);
/* The controller patch's cues on a screen (Controller Live Adaptive Layout). */
int KmrpControllerCues(const char *key_path, const char *name, const char *source_gui, const char *out_gui,
                       const char *donor_gui);
const char *KmrpControllerCueScreen(int i);
/* The game's chitin.key resource of a name and type (the vanilla side of a three-way merge). */
int KmrpReadKeyedResource(const char *key_path, const char *resref, int type, unsigned char **data, size_t *size);

/* kmrp-merge.c: any 2DA the player's Override has merged with KMRP's change of it, three ways
 * against vanilla (kmrp-2da.h). 0 merged; 3 not merged safely (the mod's is used). */
int KmrpMerge2da(const char *name, const unsigned char *base, size_t base_size, const unsigned char *ours,
                 size_t ours_size, const unsigned char *theirs, size_t theirs_size, unsigned char **out,
                 size_t *out_size, char **notes, int counts[4]);
void KmrpMergeFree(void *p);

#ifdef __cplusplus
}
#endif
#endif
