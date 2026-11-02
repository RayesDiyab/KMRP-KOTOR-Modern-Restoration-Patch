#include "../../src/controller-native/K1DisplayModePolicy.h"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace KmrpDisplayMode;

static bool Same(const Mode& a, int width, int height, int rate) {
    return a.width == width && a.height == height && a.rate == rate;
}

int main() {
    const auto all = [](int, int) { return true; };
    const std::vector<Mode> ultrawide = {
        {1280, 720, 60}, {1920, 1080, 60}, {1920, 1080, 120}, {3440, 1440, 60}, {3440, 1440, 100}, {3440, 1440, 165}, {800, 600, 60}};

    // A valid mode is the player's, however low, with or without High FPS Fix.
    for (const Mode saved : {Mode{800, 600, 60}, Mode{1920, 1080, 120}, Mode{3440, 1440, 165}})
        for (const bool high : {false, true})
            for (const bool wine : {false, true})
                assert(!Decide(saved, ultrawide, all, high, wine).change);
    // No rate saved: not invalid.
    assert(!Decide({1920, 1080, 0}, ultrawide, all, true, false).change);

    // A size with a rate it no longer has: highest size, highest rate with High FPS Fix.
    Choice rate = Decide({1920, 1080, 144}, ultrawide, all, true, false);
    assert(rate.change && Same(rate.mode, 3440, 1440, 165) && std::strstr(rate.why, "rate"));
    // Without it, the lowest of 60 Hz or more: never a rate the game's timing cannot take.
    rate = Decide({1920, 1080, 144}, ultrawide, all, false, false);
    assert(rate.change && Same(rate.mode, 3440, 1440, 60));

    // A size the display lacks, and malformed or missing values.
    for (const Mode saved : {Mode{2560, 1440, 165}, Mode{0, 0, 0}, Mode{-1, 99999, 60}})
        assert(Same(Decide(saved, ultrawide, all, true, false).mode, 3440, 1440, 165));

    // Wine: a render size above the panel stays; a rate the display lacks is corrected.
    const Choice super = Decide({3840, 2160, 60}, ultrawide, all, true, true);
    assert(!super.change && Same(super.mode, 3840, 2160, 60));
    assert(Decide({1920, 1080, 75}, ultrawide, all, true, true).change);

    // A size KMRP has no layout for is never chosen, and a saved one is replaced.
    const auto noUltrawide = [](int width, int) { return width < 3000; };
    assert(Same(Decide({3440, 1440, 165}, ultrawide, noUltrawide, true, false).mode, 1920, 1080, 120));

    // Nothing known, or nothing usable: left.
    assert(!Decide({640, 480, 60}, {}, all, true, false).change);
    assert(!Decide({640, 480, 60}, {{1024, 768, 50}}, all, true, false).change);
    assert(!Decide({640, 480, 60}, ultrawide, [](int, int) { return false; }, true, false).change);

    // The same area both ways round: the wider, whatever the list's order.
    const std::vector<Mode> square = {{1200, 1600, 60}, {1600, 1200, 60}};
    assert(Same(Decide({1, 1, 60}, square, all, true, false).mode, 1600, 1200, 60));
    const std::vector<Mode> reversed = {{1600, 1200, 60}, {1200, 1600, 60}};
    assert(Same(Decide({1, 1, 60}, reversed, all, true, false).mode, 1600, 1200, 60));

    std::cout << "display mode policy: ok\n";
    return 0;
}
