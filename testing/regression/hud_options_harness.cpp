// The HUD Size page's rules (src/controller-native/K1HudOptionsPolicy.h), no game.
#include "../../src/controller-native/K1HudOptionsPolicy.h"
#include "../../src/controller-native/K1PcHudLayout.h"
#include "../../src/controller-native/K1SliderGrip.h"
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <iostream>
using namespace KmrpHudOptions;

int main() {
    // 25% to 100%, 50% today's size (as the text sliders count); half at 25%, two and a
    // half times at 100%, a straight line each side of 50%.
    assert(Percent(10) == 25 && Percent(250) == 100 && Percent(73) == 73 && Default == 50);
    assert(SliderMaximum == 75 && Factor(50) == 1 && Factor(25) == 0.5 && Factor(100) == 2.5);
    assert(std::abs(Factor(75) - 1.75) < 1e-12 && std::abs(Factor(51) - 1.03) < 1e-12);
    for (int s = Minimum; s <= Maximum; ++s) assert(SizeForFactor(Factor(s)) == s);
    // A part kept on the screen: the 3440x1440 menu strip (597 wide, its right edge at
    // 3441) grows two and a half times about its top right corner and still fits; a
    // part whose corner is 200 from the far edge and 100 wide grows twice at most (83%,
    // 1.99 times); at 50% or below nothing changes, whatever the screen.
    assert(FittingSize({2844, 4, 597, 64}, TopRight, 100, 3440, 1440) == 100);
    assert(FittingSize({100, 2, 100, 32}, TopRight, 100, 1720, 720) == 83);
    assert(FittingSize({0, 0, 400, 400}, TopLeft, 100, 1000, 600) == 66);
    assert(FittingSize({0, 0, 4000, 400}, TopLeft, 50, 1000, 600) == 50);
    assert(FittingSize({0, 0, 400, 400}, TopLeft, 30, 1000, 600) == 30);

    // Linked (the default): a slider moves its own style's sliders, not the other style's.
    Sizes s;
    assert(s.linked);
    s.Set(PcMinimap, 75);
    for (int i = 0; i < ElementCount; ++i) assert(s.values[i] == (StyleOf(i) == Pc ? 75 : 50));
    assert(StyleOf(PcDisengage) == Pc && StyleOf(XboxActions) == Xbox && StyleOf(XboxDisengage) == Xbox);
    s.Set(XboxParty, 35);
    assert(s.values[XboxActions] == 35 && s.values[PcMenu] == 75);
    // Unlinked: one slider alone; linking again makes each style its first slider's size.
    s.Link(false);
    s.Set(PcActions, 90);
    assert(s.values[PcActions] == 90 && s.values[PcMenu] == 75);
    s.Link(true);
    assert(s.values[PcActions] == 75 && s.values[XboxParty] == 35 && s.values[XboxTargetBar] == 35);

    // Each element grows from its own screen corner: that corner stays put.
    const Rect menu{2844, 4, 597, 64};          // mipc210x7.gui's LBL_MENUBG at 3440x1440
    const Rect bigger = ScaleAbout(menu, menu, CornerOf(PcMenu), 100);
    assert(bigger.left + bigger.width == 2844 + 597 && bigger.top == 4);
    assert(bigger.width == 1492 && bigger.height == 160);       // two and a half times, at 100%
    const Rect map{0, 0, 276, 276};
    const Rect half = ScaleAbout(map, map, CornerOf(PcMinimap), 25);
    assert(half.left == 0 && half.top == 0 && half.width == 138 && half.height == 138);
    const Rect slot{3077, 1318, 74, 120}, bar{3077, 1260, 356, 178};
    const Rect moved = ScaleAbout(slot, bar, CornerOf(PcActions), 75);
    // The bar's bottom right corner (3433, 1438) holds; the slot moves away from it.
    assert(moved.left == 3433 - 623 && moved.width == 130 && moved.height == 210);   // 1.75 times, at 75%
    assert(ScaleAbout(slot, bar, CornerOf(PcActions), 50).left == slot.left);
    // The Disengage button (the combat queue with the button in it) grows from the
    // middle of its bottom edge; the attack buttons from the middle of their top edge.
    assert(CornerOf(PcAttack) == TopCentre);
    const Rect queue{1584, 1258, 262, 180};
    const Rect wide = ScaleAbout(queue, queue, CornerOf(PcDisengage), 100);
    assert(wide.left == 1388 && wide.width == 655 && wide.top + wide.height == 1438 && wide.height == 450);

    // The preview keeps the screen's shape and centres it in its area.
    const Preview p = Preview::Fit({100, 200, 860, 600}, 3440, 1440);
    assert(p.width == 860 && p.height == 360 && p.left == 100 && p.top == 200 + 120);
    const Rect mapped = p.Map({3440 - 597, 0, 597, 64});
    assert(mapped.left + mapped.width == 960 && mapped.top == 320 && mapped.width == 149);
    std::cout << "PASS: HUD Size range, linking by style, corner scaling and preview fit\n";

    // A slider dragged by the mouse (K1SliderGrip.h): the ends at the ends, every step
    // reachable, and the thumb drawn for a value (as the engine lays it out, 0x00418F20)
    // giving that value back, for every travel at least twice the steps.
    for (const int steps : {75, 100, 10}) {
        for (int travel = 2 * steps; travel <= 3000; travel += 7) {
            assert(KmrpSliderK1::DragValue(0, travel, steps) == 0 && KmrpSliderK1::DragValue(-40, travel, steps) == 0);
            assert(KmrpSliderK1::DragValue(travel, travel, steps) == steps);
            assert(KmrpSliderK1::DragValue(travel + 40, travel, steps) == steps);
            int last = 0;
            for (int at = 0; at <= travel; ++at) {
                const int v = KmrpSliderK1::DragValue(at, travel, steps);
                assert(v == last || v == last + 1);
                last = v;
            }
            for (int v = 0; v <= steps; ++v) assert(KmrpSliderK1::DragValue(travel * v / steps, travel, steps) == v);
        }
    }
    std::cout << "PASS: a dragged slider reaches both ends and every step where its thumb is drawn\n";

    // The mouse and keyboard HUD placed from KMRP's table (K1PcHudLayout.h).
    using namespace KmrpPcHud;
    std::array<int, ElementCount> sizes{};
    sizes.fill(Default);
    // At 3440x1440 and every part at 50% it is the HUD exactly as KMRP ships it there:
    // every rectangle the table's (tools/build_pc_hud.py compared the table with the
    // file in the running game's cache). The arrow, which the engine centres in the map's
    // window, and the window, which the engine draws square, are what the engine makes
    // of theirs.
    {
        const Layout l = Lay(3440, 1440, sizes);
        for (int i = 0; i < kPcPieceCount; ++i) {
            const PcPiece& piece = kPcPieces[i];
            const Rect r = l.rect[i];
            if (piece.flags & kArrow) continue;
            assert(r.left == piece.box[0] && r.top == piece.box[1] && r.width == piece.box[2] && r.height == piece.box[3]);
        }
        assert(l.window.width == l.window.height && l.window.width == 270);
        const Rect arrow = l.rect[Find("LBL_ARROW")];
        assert(arrow.left == (270 - 48) / 2 && arrow.top == (270 - 48) / 2 && arrow.width == 48);
    }
    // On every screen and at every size: each part on the screen, its corner where the
    // 50% part has it, and at 50% no two parts overlapping. Overlaps at other sizes are
    // the player's to choose (a 100% HUD on a 4:3 screen is crowded) and are counted.
    // Up to 100% (two and a half times), each part as large as the screen holds it
    // (FittingSize), so on the screen at every size.
    const int screens[][2] = {{800, 600}, {1024, 768}, {1280, 720}, {1280, 960}, {1600, 1200}, {1280, 1024},
                              {1920, 1080}, {1920, 1200}, {2560, 1080}, {2560, 1440}, {3440, 1440}, {3840, 2160}, {5120, 1440}};
    int crowded = 0;
    for (const auto& screen : screens) {
        const int width = screen[0], height = screen[1];
        const Layout usual = Lay(width, height, sizes);
        for (const int size : {25, 37, 50, 63, 75, 88, 100}) {
            std::array<int, ElementCount> each{};
            each.fill(size);
            const Layout l = Lay(width, height, each);
            const int parts[] = {PcMenu, PcMinimap, PcActions, PcPortraits, PcDisengage};
            for (const int e : parts) {
                const Rect g = l.group[e], u = usual.group[e];
                // On the screen. The menu buttons' background reaches a pixel past its
                // right edge in the shipped HUD (LBL_MENUBG, 2844 + 597 at 3440 wide), at the screen's scale.
                const bool on = g.left >= 0 && g.top >= 0 && g.left + g.width <= width + (height + 1439) / 1440 && g.top + g.height <= height;
                if (!on) std::cout << width << "x" << height << " at " << size << ": part " << e << " at " << g.left << "," << g.top << " " << g.width << "x" << g.height << std::endl;
                assert(on);
                const Corner c = CornerOf(e);
                if (size <= 50) assert(l.size[e] == size);
                if (c == TopLeft) assert(g.left == u.left && g.top == u.top);
                if (c == TopRight) assert(g.left + g.width == u.left + u.width && g.top == u.top);
                if (c == BottomLeft) assert(g.left == u.left && g.top + g.height == u.top + u.height);
                if (c == BottomRight) assert(g.left + g.width == u.left + u.width && g.top + g.height == u.top + u.height);
                if (c == BottomCentre)
                    assert(g.top + g.height == u.top + u.height && std::abs((g.left + g.width / 2) - (u.left + u.width / 2)) <= 1);
            }
            for (const int a : parts)
                for (const int b : parts) {
                    if (a >= b) continue;
                    const Rect x = l.group[a], y = l.group[b];
                    const bool overlap = x.left < y.left + y.width && y.left < x.left + x.width &&
                                         x.top < y.top + y.height && y.top < x.top + x.height;
                    if (size == 50 && overlap) std::cout << width << "x" << height << ": parts " << a << " and " << b << " overlap\n";
                    if (size == 50) assert(!overlap);
                    crowded += overlap;
                }
            // The window square and the arrow in its middle, at any size.
            assert(l.window.width == l.window.height && l.window.width > 0);
            const Rect arrow = l.rect[Find("LBL_ARROW")];
            assert(std::abs(2 * arrow.left + arrow.width - l.window.width) <= 1);
            // The combat-mode message as far from the minimap's notices as at 50% (the
            // shipped HUD has it starting 9 of 1440's pixels inside LBL_CASH's box, which
            // shows only while credits come in).
            const auto gap = [](const Layout& at) {
                const Rect message = at.rect[Find("LBL_CMBTMODEMSG")], notices = at.rect[Find("LBL_CASH")];
                return message.left - (notices.left + notices.width);
            };
            assert(std::abs(gap(l) - gap(usual)) <= 1);
        }
    }
    std::cout << "PASS: the mouse and keyboard HUD placed on " << sizeof screens / sizeof screens[0]
              << " screens at seven sizes; pairs of parts overlapping at a size other than 50%: " << crowded << "\n";
}
