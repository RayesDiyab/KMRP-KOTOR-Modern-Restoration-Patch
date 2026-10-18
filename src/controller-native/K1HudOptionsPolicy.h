#pragma once
// The HUD Size page's rules, kept apart from the engine so they can be tested
// (testing/regression/Test-HudOptions.py). The page is K1HudOptions.cpp.
#include <algorithm>
#include <array>
#include <cmath>

namespace KmrpHudOptions {
// As the text sliders count: 25% to 100%, 50% the HUD as KMRP lays it out today, 25%
// half of it (the maintainer, 2026-10-18: "the current 100% should be basically 50%";
// the first build counted 50% to 200% with 100% for today). 1% steps.
constexpr int Minimum = 25, Maximum = 100, Step = 1, Default = 50;
constexpr int SliderMaximum = (Maximum - Minimum) / Step;
inline int Percent(int value) {
    value = (std::max)(Minimum, (std::min)(Maximum, value));
    return Minimum + ((value - Minimum + Step / 2) / Step) * Step;
}

// The elements, by HUD: the mouse and keyboard HUD (the PC HUD) and the controller's
// Xbox-style HUD, which keep separate sizes and are shown apart (the maintainer,
// 2026-10-18: "have a clear separation of controller ui and mouse and keyboard UI").
// Added that day: the mouse and keyboard HUD's attack buttons (the target's action
// buttons, sword, grenade and the like, shown in combat; the controller HUD has them in
// its action menu) and its Disengage button, which is the combat queue with the button
// in it, one element; the controller HUD's minimap, top left bar and Disengage button.
enum Element {
    PcMenu = 0, PcMinimap, PcActions, PcPortraits, PcAttack, PcDisengage,
    XboxActions, XboxParty, XboxMinimap, XboxTargetBar, XboxDisengage, ElementCount
};
enum Style { Pc = 0, Xbox = 1 };
inline Style StyleOf(int element) { return element >= XboxActions ? Xbox : Pc; }
inline int FirstOf(int style) { return style == Xbox ? XboxActions : PcMenu; }

// Where on the screen each element grows from, so it never slides off the screen: a
// corner, or the middle of the top or bottom edge for what sits there.
enum Corner { TopLeft, TopRight, BottomLeft, BottomRight, TopCentre, BottomCentre };
inline Corner CornerOf(int element) {
    switch (element) {
        case PcMenu: return TopRight;
        case PcMinimap: return TopLeft;
        case PcActions: return BottomRight;
        case PcPortraits: return BottomLeft;
        // The attack buttons stay centred under the target's name, as the packager
        // centres them (apply_gold_hud_proportions.target_menu_extents); about their
        // top left corner they grew to the right, the engine centred the wider menu on
        // the target, and the name stood left of the target's circle (2026-10-18).
        case PcAttack: return TopCentre;
        case PcDisengage: return BottomCentre;
        case XboxActions: return BottomLeft;
        case XboxParty: return BottomRight;
        case XboxMinimap: return TopRight;
        case XboxTargetBar: return TopLeft;
        // XboxDisengage: the disengage button and its queue at the bottom centre. The
        // combat strip across the top is not it: that keeps its size, and only its text
        // follows the text options (the maintainer, 2026-10-18).
        default: return BottomCentre;
    }
}

// Where the sizes are kept: swkotor.ini beside the game, read by both HUDs' modules
// (K1HudOptions.cpp and K1PcHud.cpp in KMRP's, K1XboxHud.cpp in the controller
// patch's, which has no page of its own and reads them itself).
constexpr const wchar_t* IniSection = L"KMRP HUD Size";
constexpr const wchar_t* IniKeys[ElementCount] = {
    L"PcMenu", L"PcMinimap", L"PcActionBar", L"PcPortraits", L"PcAttackButtons", L"PcDisengage",
    L"XboxActionMenu", L"XboxPartySwitch", L"XboxMinimap", L"XboxTopLeftBar", L"XboxDisengage"};

// The part of the Xbox-style HUD a piece of its table (K1XboxHudLayout.inc) belongs to,
// by the piece's place in CSWGuiMainInterface and its flags, or -1: the combat strip
// across the top keeps its size, and only its text follows the text options (the
// maintainer, 2026-10-18). Anything else at the bottom left is the action menu.
inline int XboxElementOf(unsigned offset, bool party, bool row, bool bottomLeft) {
    if (party) return XboxParty;
    if (row) return -1;
    switch (offset) {
        case 0x5CC0: case 0x6098: return XboxMinimap;                             // LBL_MAPBORDER, BTN_MINIMAP
        case 0x1688: case 0x17C8: case 0x1A48: case 0x1908: return XboxTargetBar;  // LBL_NAME(BG), PB_HEALTH, LBL_HEALTHBG
        // The disengage button and its queue: LBL_COMBATBG1, LBL_QUEUE0..3, BTN_CLEARONE(2).
        case 0x675C: case 0x625C: case 0x639C: case 0x64DC: case 0x661C: case 0x6CD0: case 0x6E94: return XboxDisengage;
    }
    return bottomLeft ? XboxActions : -1;
}

// "Link HUD Sizes", on by default: a slider moved while linked moves the other
// sliders of the same HUD with it; the other HUD keeps its own sizes.
struct Sizes {
    std::array<int, ElementCount> values{};
    bool linked = true;
    Sizes() { values.fill(Default); }
    void Set(int element, int value) {
        if (element < 0 || element >= ElementCount) return;
        value = Percent(value);
        if (!linked) { values[element] = value; return; }
        for (int i = 0; i < ElementCount; ++i)
            if (StyleOf(i) == StyleOf(element)) values[i] = value;
    }
    // Linking makes each HUD's sliders equal to that HUD's first.
    void Link(bool value) {
        linked = value;
        if (!linked) return;
        for (int i = 0; i < ElementCount; ++i) values[i] = values[FirstOf(StyleOf(i))];
    }
};

struct Rect { int left, top, width, height; };
inline int Round(double value) { return static_cast<int>(std::lround(value)); }

// How much larger than today a size draws: half at 25%, today's at 50%, two and a half
// times at 100%, in a straight line on each side of 50% (0.03 a percent above it). Until
// the maintainer had seen it in the game, 100% was twice today's; the same day: "the
// 50% in the slider would be the current 50%, but the 100% should be like the 250%".
constexpr double MostFactor = 2.5;
inline double Factor(int size) {
    return size <= Default ? double(size) / Default
                           : 1.0 + (size - Default) * (MostFactor - 1.0) / (Maximum - Default);
}
// The largest size whose factor is at most `factor` (Factor's inverse, rounded down).
inline int SizeForFactor(double factor) {
    const double size = factor <= 1.0 ? factor * Default
                                      : Default + (factor - 1.0) * (Maximum - Default) / (MostFactor - 1.0);
    return static_cast<int>(std::floor(size + 1e-9));
}

// A rectangle of an element whose whole box is `group`, scaled by Factor(size) about
// the group's corner on its screen side: the corner stays put and everything else
// moves towards or away from it in proportion.
inline Rect ScaleAbout(const Rect& r, const Rect& group, Corner corner, int size) {
    const double f = Factor(size);
    const double ax = (corner == TopRight || corner == BottomRight) ? group.left + group.width
                    : (corner == TopCentre || corner == BottomCentre) ? group.left + group.width / 2.0 : group.left;
    const double ay = (corner == BottomLeft || corner == BottomRight || corner == BottomCentre) ? group.top + group.height : group.top;
    const int left = Round(ax + (r.left - ax) * f), top = Round(ay + (r.top - ay) * f);
    const int right = Round(ax + (r.left + r.width - ax) * f), bottom = Round(ay + (r.top + r.height - ay) * f);
    return {left, top, (std::max)(1, right - left), (std::max)(1, bottom - top)};
}

// The size a part is drawn at on a width x height screen: the size asked for, or the
// largest at which the part, grown about its corner, still ends at the screen's edges
// (a 100% part is two and a half times today's, more than a small screen may hold).
// Never below today's size: at 50% the HUD is as it was, whatever the screen.
inline int FittingSize(const Rect& group, Corner corner, int size, int width, int height) {
    if (group.width <= 0 || group.height <= 0 || size <= Default) return size;
    const double right = group.left + group.width, bottom = group.top + group.height;
    double most;   // the largest factor that fits
    switch (corner) {
        case TopLeft: most = (std::min)((width - group.left) / double(group.width), (height - group.top) / double(group.height)); break;
        case TopRight: most = (std::min)(right / group.width, (height - group.top) / double(group.height)); break;
        case BottomLeft: most = (std::min)((width - group.left) / double(group.width), bottom / group.height); break;
        case BottomRight: most = (std::min)(right / group.width, bottom / group.height); break;
        case TopCentre: {
            const double centre = group.left + group.width / 2.0;
            most = (std::min)(2 * (std::min)(centre, width - centre) / group.width, (height - group.top) / double(group.height));
            break;
        }
        default: {
            const double centre = group.left + group.width / 2.0;
            most = (std::min)(2 * (std::min)(centre, width - centre) / group.width, bottom / group.height);
            break;
        }
    }
    return (std::max)(Default, (std::min)(size, SizeForFactor(most)));
}

// The preview: the screen (width x height) drawn as large as fits in `area`, its
// aspect kept, centred; a screen rectangle mapped into it.
struct Preview {
    double scale = 1; int left = 0, top = 0, width = 0, height = 0;
    static Preview Fit(const Rect& area, int screenWidth, int screenHeight) {
        Preview p;
        if (screenWidth <= 0 || screenHeight <= 0 || area.width <= 0 || area.height <= 0) return p;
        p.scale = (std::min)(double(area.width) / screenWidth, double(area.height) / screenHeight);
        p.width = Round(screenWidth * p.scale); p.height = Round(screenHeight * p.scale);
        p.left = area.left + (area.width - p.width) / 2; p.top = area.top + (area.height - p.height) / 2;
        return p;
    }
    Rect Map(const Rect& r) const {
        const int x = left + Round(r.left * scale), y = top + Round(r.top * scale);
        const int right = left + Round((r.left + r.width) * scale), bottom = top + Round((r.top + r.height) * scale);
        return {x, y, (std::max)(1, right - x), (std::max)(1, bottom - y)};
    }
};
}  // namespace KmrpHudOptions
