/* kmrp-iconsize.h: the Icon Size slider's arithmetic (issue 80), the one copy, for the
 * module: the rows (K1RuntimeEngine.cpp), the icons the engine draws at the size
 * (K1RuntimeLayout.cpp) and the page's preview (K1TextOptions.cpp). The icon files are
 * KMRP's (kmrp-abilityicons.c) at 50% as always; at any other size the engine stretches
 * them.
 *
 * The maintainer's scale (2026-10-31): 25% the game's own icon, 50% the size KMRP has
 * always made it (the default), 100% three times that. Between those points the size moves
 * in a straight line, so 75% is twice the default. Feat, Force power and skill icons share
 * it (one slider), on the Text Size page.
 *
 * Header only: every function is static inline, plain C, and the same in C++. */
#ifndef KMRP_ICONSIZE_H
#define KMRP_ICONSIZE_H

#include <math.h>

enum { KMRP_ICON_MINIMUM = 25, KMRP_ICON_DEFAULT = 50, KMRP_ICON_MAXIMUM = 100 };

/* KMRP's two row bases and the game's: the feat and power chain rows and the Skills tab's
 * rows are 50 at a scale of 1 (the engine recipe, tools/build_native_engine.py); the game's
 * skill rows were 42, and its icons are NATIVE pixels square. */
enum { KMRP_ICON_ROW_BASE = 50, KMRP_ICON_INSET = 4, KMRP_ICON_VANILLA_SKILL_ROW = 42, KMRP_ICON_NATIVE = 32 };

static inline int kmrp_icon_percent(int percent) {
    return percent < KMRP_ICON_MINIMUM ? KMRP_ICON_MINIMUM : percent > KMRP_ICON_MAXIMUM ? KMRP_ICON_MAXIMUM : percent;
}

/* An icon's size at PERCENT, TODAY being KMRP's own size for it (50%) and NATIVE the game's
 * (25%); never smaller than NATIVE. */
static inline int kmrp_icon_sized(int today, int native, int percent) {
    percent = kmrp_icon_percent(percent);
    if (percent == KMRP_ICON_DEFAULT || today <= 0) return today;
    double size = percent < KMRP_ICON_DEFAULT
        ? native + (today - native) * (percent - KMRP_ICON_MINIMUM) / (double)(KMRP_ICON_DEFAULT - KMRP_ICON_MINIMUM)
        : today * (1.0 + 2.0 * (percent - KMRP_ICON_DEFAULT) / (double)(KMRP_ICON_MAXIMUM - KMRP_ICON_DEFAULT));
    int rounded = (int)nearbyint(size);
    return rounded < native ? native : rounded;
}

/* The scale KMRP's art is made at on a screen HEIGHT lines high: max(1, HEIGHT / 720) in
 * single precision, as kmrp-abilityicons.c (scale_for_height) and the engine recipe
 * (FieldValue) compute it, so a size here is the size made there to the pixel. */
static inline double kmrp_icon_scale(int height) {
    float scale = (float)height / 720.0f;
    return scale < 1.0f ? 1.0 : (double)scale;
}

/* KMRP's own sizes at a scale, for a NATIVE icon, as kmrp-abilityicons.c makes them
 * (target_size, skill_target_size). */
static inline int kmrp_icon_feat_today(double scale, int native) {
    int box = (int)nearbyint(KMRP_ICON_ROW_BASE * scale) - KMRP_ICON_INSET;
    if (box <= native) return native;
    return box < native * 2 ? box : native * 2;
}
static inline int kmrp_icon_skill_today(double scale, int native) {
    int grown = (int)nearbyint(native * scale * KMRP_ICON_ROW_BASE / KMRP_ICON_VANILLA_SKILL_ROW);
    if (grown <= native) return native;
    return grown < native * 2 ? grown : native * 2;
}

/* The game's own size of an icon drawn TODAY pixels at the default: 32 or 64 where KMRP
 * made TODAY from an icon of that size (the game's are both: 148 feat and 52 power icons
 * of 32, 28 and 71 of 64, swpc_tex_gui.erf counted 2026-10-31), else TODAY itself, an icon
 * KMRP did not enlarge (a mod's, or one already right). */
static inline int kmrp_icon_native_of(int today, double scale) {
    if (today == kmrp_icon_feat_today(scale, 32) || today == kmrp_icon_skill_today(scale, 32)) return 32;
    if (today == kmrp_icon_feat_today(scale, 64)) return 64;
    return today;
}

/* An icon drawn TODAY pixels at the default, at PERCENT: the size the engine draws it at
 * (K1RuntimeLayout.cpp) and the preview shows it at (K1TextOptions.cpp). */
static inline int kmrp_icon_drawn(int today, double scale, int percent) {
    return kmrp_icon_sized(today, kmrp_icon_native_of(today, scale), percent);
}

/* The row heights the icons need at PERCENT: never lower than ROW, the height the row has
 * without the slider. A feat or power chain row holds its icon in a box its height less
 * the inset, sized for the largest icons it can hold, those of 64 (KMRP draws them as
 * large as the box); a skill row holds its icon as the game's 42 held its 32 (every skill
 * icon is 32). */
/* At the default and below the rows are as they always were: the icons are no larger than
 * KMRP's own, which fit (and the skill rule rounds a pixel over at some heights, 728 lines
 * among them, which the default must never change; Test-ModCompatibility.py). */
static inline int kmrp_icon_chain_row(int row, double scale, int percent) {
    if (kmrp_icon_percent(percent) <= KMRP_ICON_DEFAULT) return row;
    int icon = kmrp_icon_sized(kmrp_icon_feat_today(scale, 2 * KMRP_ICON_NATIVE), 2 * KMRP_ICON_NATIVE, percent);
    return icon + KMRP_ICON_INSET > row ? icon + KMRP_ICON_INSET : row;
}
static inline int kmrp_icon_skill_row(int row, double scale, int percent) {
    if (kmrp_icon_percent(percent) <= KMRP_ICON_DEFAULT) return row;
    int icon = kmrp_icon_sized(kmrp_icon_skill_today(scale, KMRP_ICON_NATIVE), KMRP_ICON_NATIVE, percent);
    int needed = (icon * KMRP_ICON_VANILLA_SKILL_ROW + KMRP_ICON_NATIVE - 1) / KMRP_ICON_NATIVE;
    return needed > row ? needed : row;
}

#endif
