// What to do with the display mode saved in swkotor.ini (issue 92). No Windows and no game in
// here, so a harness can feed it any display (testing/regression/Test-DisplayModePolicy.py).
//
// A saved mode the display still has is the player's and is left, however low. Only one it no
// longer has is replaced: the largest size KMRP has a layout for, at that size's highest rate
// the game may use. That rate is the size's highest with High FPS Fix, and otherwise its lowest
// of 60 Hz or more, as the game's own list then shows (EnumModesOnce, K1RuntimeResolution.cpp).
//
// Under Wine, Proton and Gamescope a render size above the panel is a choice the display's list
// need not show, so a size missing from the list is left. A size it has with a rate it lacks is
// the report behind this issue (a monitor's rate changed, menu text broke) and is corrected there
// too. No list at all means nothing is known, and nothing is changed.
#pragma once
#include <vector>

namespace KmrpDisplayMode {
struct Mode {
    int width = 0, height = 0, rate = 0;
};
struct Choice {
    bool change = false;
    Mode mode{};
    const char* why = "";
};

template <typename Covers>
Choice Decide(const Mode& saved, const std::vector<Mode>& modes, Covers covers, bool highRates, bool wine)
{
    if (modes.empty()) return {false, saved, "the display lists no modes"};
    bool size = false, rate = saved.rate == 0;      // no rate saved: the game chooses, as ever
    for (const Mode& mode : modes) {
        if (mode.width != saved.width || mode.height != saved.height) continue;
        size = true;
        rate = rate || mode.rate == saved.rate;
    }
    if (size && rate && covers(saved.width, saved.height)) return {false, saved, "the display has this mode"};
    if (wine && !size) return {false, saved, "Wine may render above the panel"};

    Mode best{};
    for (const Mode& mode : modes) {
        if (mode.rate < 60 || !covers(mode.width, mode.height)) continue;
        const long long area = static_cast<long long>(mode.width) * mode.height;
        const long long bestArea = static_cast<long long>(best.width) * best.height;
        const bool bigger = area > bestArea || (area == bestArea && mode.width > best.width);
        const bool sameSize = mode.width == best.width && mode.height == best.height;
        if (bigger || (sameSize && (highRates ? mode.rate > best.rate : mode.rate < best.rate))) best = mode;
    }
    if (!best.width) return {false, saved, "no mode of the display can replace it"};
    return {true, best, size ? "the display has this size but not this rate" : "the display has no mode of this size"};
}
}
