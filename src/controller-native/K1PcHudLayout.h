#pragma once
// The mouse and keyboard HUD placed for any screen, from KMRP's own table
// (K1PcHudLayout.inc, written by tools/build_pc_hud.py, which says where every number
// comes from), and each of its parts sized about its corner as the HUD Size page says.
// Shared by the page's preview (K1HudOptions.cpp) and the HUD itself (K1PcHud.cpp), so
// the preview is the HUD. Kept apart from the engine so it can be tested
// (testing/regression/hud_options_harness.cpp).
#include "K1HudOptionsPolicy.h"
#include <algorithm>
#include <array>
#include <cmath>

namespace KmrpPcHud {
using KmrpHudOptions::Rect;
using KmrpHudOptions::Round;

// How a piece's rectangle is anchored: to a corner of the screen or the middle of its
// bottom edge, keeping its distance from there at the screen's scale; or in the target
// menu's own coordinates (the engine draws the menu at the target); or relative to its
// portrait (the engine keeps the combat-effect arrows so).
enum PcAnchor : unsigned char {
    kPcTopLeft, kPcTopRight, kPcBottomLeft, kPcBottomRight, kPcBottomCentre, kPcMenuSpace, kPcCharSpace
};
enum : unsigned char {
    kWindow = 1,    // LBL_MAPVIEW: the rectangle the map is drawn in (the HUD keeps it at +0x6080)
    kArrow = 2,     // LBL_ARROW: the player's arrow, in the middle of the map's window
    kFollow = 4,    // keeps its size and moves with the minimap's right edge
    kPreview = 8,   // drawn by the HUD Size page's preview
};
struct PcPiece {
    const char* tag;
    signed char element;    // KmrpHudOptions::Element, or -1: placed with the screen only
    PcAnchor anchor;
    short box[4];           // at 3440x1440
    const char* fill;
    unsigned char flags;
};
#include "K1PcHudLayout.inc"
constexpr int kPcPieceCount = static_cast<int>(sizeof kPcPieces / sizeof kPcPieces[0]);

// A length at 3440x1440 on this screen: the screen's height over 1440.
inline double ScreenScale(int height) { return double(height) / kPcBaseHeight; }
// The target menu's scale, as the packager scaled it for each size
// (apply_gold_hud_proportions.target_menu_extents): half of the height over 720, never
// below a half.
inline double MenuScale(int height) { return (std::max)(1.0, height / 720.0) / 2.0; }

// A piece on this screen before any part is sized.
inline Rect Placed(const PcPiece& p, int width, int height)
{
    const double s = p.anchor == kPcMenuSpace ? MenuScale(height) : ScreenScale(height);
    double screenX = 0, baseX = 0, screenY = 0, baseY = 0;
    if (p.anchor == kPcTopRight || p.anchor == kPcBottomRight) { screenX = width; baseX = kPcBaseWidth; }
    if (p.anchor == kPcBottomCentre) { screenX = width / 2.0; baseX = kPcBaseWidth / 2.0; }
    if (p.anchor == kPcBottomLeft || p.anchor == kPcBottomRight || p.anchor == kPcBottomCentre) {
        screenY = height; baseY = kPcBaseHeight;
    }
    const int left = Round(screenX + (p.box[0] - baseX) * s), top = Round(screenY + (p.box[1] - baseY) * s);
    const int right = Round(screenX + (p.box[0] + p.box[2] - baseX) * s);
    const int bottom = Round(screenY + (p.box[1] + p.box[3] - baseY) * s);
    return {left, top, (std::max)(1, right - left), (std::max)(1, bottom - top)};
}

struct Layout {
    Rect rect[kPcPieceCount]{};     // each piece where it goes (the arrow: inside the map's window)
    Rect group[KmrpHudOptions::ElementCount]{};   // each part's box, sized
    Rect window{};                  // the map's window on the screen; square, as DrawMap draws it
    std::array<int, KmrpHudOptions::ElementCount> size{};   // each part's size as drawn (FittingSize)
};

inline Rect Union(const Rect& a, const Rect& b)
{
    const int left = (std::min)(a.left, b.left), top = (std::min)(a.top, b.top);
    const int right = (std::max)(a.left + a.width, b.left + b.width), bottom = (std::max)(a.top + a.height, b.top + b.height);
    return {left, top, right - left, bottom - top};
}

// The HUD on a width x height screen with each part at its size (percent, 50 today's).
inline Layout Lay(int width, int height, const std::array<int, KmrpHudOptions::ElementCount>& sizes)
{
    using namespace KmrpHudOptions;
    Layout out;
    Rect placed[kPcPieceCount], group[ElementCount]{};
    bool seen[ElementCount]{};
    for (int i = 0; i < kPcPieceCount; ++i) {
        const PcPiece& p = kPcPieces[i];
        placed[i] = Placed(p, width, height);
        if (p.element < 0 || p.anchor == kPcCharSpace || (p.flags & (kFollow | kArrow))) continue;
        group[p.element] = seen[p.element] ? Union(group[p.element], placed[i]) : placed[i];
        seen[p.element] = true;
    }
    // Each part at its size, or as large as the screen holds it (FittingSize). The
    // attack buttons are in the target menu's own space, which the engine keeps on the
    // screen itself.
    out.size = sizes;
    for (int e = 0; e < ElementCount; ++e) {
        if (seen[e] && e != PcAttack) out.size[e] = FittingSize(group[e], CornerOf(e), sizes[e], width, height);
        out.group[e] = seen[e] ? ScaleAbout(group[e], group[e], CornerOf(e), out.size[e]) : Rect{};
    }
    // What a larger minimap pushes right: the combat-mode message beside it.
    const int follow = out.group[PcMinimap].left + out.group[PcMinimap].width - (group[PcMinimap].left + group[PcMinimap].width);
    for (int i = 0; i < kPcPieceCount; ++i) {
        const PcPiece& p = kPcPieces[i];
        const Rect r = placed[i];
        if (p.element < 0) { out.rect[i] = r; continue; }
        const double f = Factor(out.size[p.element]);
        if (p.flags & kFollow) {
            out.rect[i] = {r.left + follow, r.top, r.width, r.height};
        } else if (p.anchor == kPcCharSpace || (p.flags & kArrow)) {
            out.rect[i] = {Round(r.left * f), Round(r.top * f), (std::max)(1, Round(r.width * f)), (std::max)(1, Round(r.height * f))};
        } else {
            out.rect[i] = ScaleAbout(r, group[p.element], CornerOf(p.element), out.size[p.element]);
        }
        if (p.flags & kWindow) {
            out.window = out.rect[i];
            out.window.height = out.window.width;
        }
    }
    // The target menu: the name strip (its name, the name's frame and the health bar)
    // as wide as the attack buttons when they are wider, so both stay centred on one
    // line (the packager's rule, apply_gold_hud_proportions.target_menu_extents: "each
    // strip control widened to the buttons' right edge where it falls short"); and the
    // whole moved right so nothing starts left of the menu's own corner, where the
    // engine's drawing of it begins.
    {
        Rect strip{};
        bool any = false;
        for (int i = 0; i < kPcPieceCount; ++i)
            if (kPcPieces[i].anchor == kPcMenuSpace && kPcPieces[i].element < 0) {
                strip = any ? Union(strip, out.rect[i]) : out.rect[i];
                any = true;
            }
        const Rect slots = out.group[PcAttack];
        if (any && slots.width > strip.width)
            for (int i = 0; i < kPcPieceCount; ++i)
                if (kPcPieces[i].anchor == kPcMenuSpace && kPcPieces[i].element < 0) {
                    out.rect[i].left = slots.left;
                    out.rect[i].width = slots.width;
                }
        int least = 0;
        for (int i = 0; i < kPcPieceCount; ++i)
            if (kPcPieces[i].anchor == kPcMenuSpace) least = (std::min)(least, out.rect[i].left);
        for (int i = 0; i < kPcPieceCount; ++i)
            if (kPcPieces[i].anchor == kPcMenuSpace) out.rect[i].left -= least;
        out.group[PcAttack].left -= least;
    }
    // The arrow in the middle of the window, as the HUD's constructor puts it
    // (CSWGuiMainInterface, 0x0068C100: half of what the window leaves either way).
    for (int i = 0; i < kPcPieceCount; ++i) {
        if (!(kPcPieces[i].flags & kArrow)) continue;
        Rect& a = out.rect[i];
        a.left = (out.window.width - a.width) / 2;
        a.top = (out.window.height - a.height) / 2;
    }
    return out;
}

inline int Find(const char* tag)
{
    for (int i = 0; i < kPcPieceCount; ++i) {
        const char* a = kPcPieces[i].tag;
        const char* b = tag;
        while (*a && *a == *b) { ++a; ++b; }
        if (!*a && !*b) return i;
    }
    return -1;
}

// A combat cue beside its button, as the packager places it (add_combat_cues): a square
// whose side is kPcCombatCueScale of the Disengage button's height (Python's round, half
// to even), at least 8; a quarter of it, at least 2, left of the button; centred on the
// button's height. Until 2026-10-30 only the packager placed the cues, at the HUD's
// default size, so with the Disengage part sized away from 50% they stayed behind.
inline Rect CombatCueRect(const Rect& disengage, const Rect& button)
{
    const int size = (std::max)(8, static_cast<int>(std::nearbyint(disengage.height * kPcCombatCueScale)));
    const int gap = (std::max)(2, size / 4);
    return Rect{button.left - gap - size, button.top + (button.height - size) / 2, size, size};
}
}  // namespace KmrpPcHud
