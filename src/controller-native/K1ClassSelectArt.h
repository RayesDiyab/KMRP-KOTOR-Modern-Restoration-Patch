#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <utility>
#include <vector>
struct ClassBoxK1 { int left, top, width, height; };
struct ClassArtResultK1 {
    char drawn[17] = {};
    ClassBoxK1 selectAt{}, cancelAt{};
    std::vector<std::uint8_t> sheet;
};
// Pure pixels/geometry: shared by the preload worker and the live fallback.
inline bool BuildClassSelectArtK1(const char* fill, const ClassBoxK1& panel, const ClassBoxK1& cancel,
                                  const unsigned char* pixels, int width, int height, ClassArtResultK1& result)
{
    if (panel.width <= 0 || panel.height <= 0 || width < 64 || height < 64) {
        return false;
    }
    // Rows counted from the picture's top as drawn; OpenGL's row 0 is its foot.
    const auto at = [&](int x, int y) { return pixels + (static_cast<std::size_t>(height - 1 - y) * width + x) * 4; };
    const auto light = [&](int x, int y) { const unsigned char* p = at(x, y); return (std::max)(p[0], (std::max)(p[1], p[2])); };
    const auto texX = [&](int sx) { return static_cast<int>(static_cast<long long>(sx - panel.left) * width / panel.width); };
    const auto texY = [&](int sy) { return static_cast<int>(static_cast<long long>(sy - panel.top) * height / panel.height); };
    const int r0 = (std::max)(0, texY(cancel.top + cancel.height / 10));
    const int r1 = (std::min)(height - 1, texY(cancel.top + cancel.height - cancel.height / 10));
    const int c = texX(cancel.left + cancel.width / 2);
    bool fine = r1 > r0 && c > 0 && c < width - 1;
    // Each column's brightest texel within Cancel's rows.
    std::vector<int> most(static_cast<std::size_t>(width), 0);
    for (int x = 0; fine && x < width; ++x) {
        for (int y = r0; y <= r1; ++y) most[x] = (std::max)(most[x], static_cast<int>(light(x, y)));
    }
    // The capsule: from its middle out to where the light falls below six tenths of its
    // middle's (in lbl_cg_clsssel: the middle 40 to 47, the rounded ends 84, the gap 21);
    // then the dark gap, out to the arrow, which is half again as bright as the middle and
    // more (230 and over). Each end is as wide as the run brighter than the middle.
    const int inside = fine ? most[c] : 0;
    int capL = c, capR = c, arrowL = -1, arrowR = -1;
    if (fine && inside > 0) {
        while (capL > 0 && most[capL - 1] * 10 >= inside * 6) --capL;
        while (capR < width - 1 && most[capR + 1] * 10 >= inside * 6) ++capR;
        // The original game's dark-blue foot has the same brightness in its
        // middle and gaps. Find its two brighter rounded ends instead. KMRP's
        // higher-contrast art continues through the original detector above.
        if (capL == 0 || capR == width - 1) {
            capL = capR = c;
            while (capL > 0 && most[capL] <= inside + 3) --capL;
            while (capR < width - 1 && most[capR] <= inside + 3) ++capR;
            while (capL > 0 && most[capL - 1] > inside + 3) --capL;
            while (capR < width - 1 && most[capR + 1] > inside + 3) ++capR;
        }
        for (int x = capL - 1; x > 0 && arrowL < 0; --x) if (most[x] * 2 >= inside * 3) arrowL = x;
        for (int x = capR + 1; x < width - 1 && arrowR < 0; ++x) if (most[x] * 2 >= inside * 3) arrowR = x;
    }
    int end = 0;
    while (fine && capL + end < c && most[capL + end] > inside + 3) ++end;
    const int capsule = capR - capL + 1;
    const int gapL = capL - arrowL - 1, gapR = arrowR - capR - 1;
    fine = fine && inside > 0 && arrowL >= 0 && arrowR >= 0 && gapL > 0 && gapR > 0 &&
           gapL < capsule / 4 && gapR < capsule / 4 && end > 0 && end < capsule / 3;
    const int gap = (gapL + gapR) / 2;
    const int span = arrowR - arrowL - 1;
    const int each = (span - 3 * gap) / 2;
    fine = fine && each > 2 * end + 4;
    if (!fine) {
        return false;
    }
    const int x0 = arrowL + 1 + gap, x1 = x0 + each, x2 = x1 + gap, x3 = x2 + each;
    // The capsule's rows: where an end's column differs from the gap's.
    const int endColumn = capL + end / 2, gapColumn = arrowL + 1 + gapL / 2;
    int top = -1, bottom = -1;
    const int reach = (std::max)(2, (r1 - r0) / 2);
    for (int y = (std::max)(0, r0 - reach); y <= (std::min)(height - 1, r1 + reach); ++y) {
        const unsigned char *a = at(endColumn, y), *b = at(gapColumn, y);
        if (std::abs(a[0] - b[0]) + std::abs(a[1] - b[1]) + std::abs(a[2] - b[2]) > 12) {
            if (top < 0) top = y;
            bottom = y;
        }
    }
    if (top < 0) {
        return false;
    }
    // The drawing, top row first: the picture, and between the arrows in those rows (and
    // one more each side) the gap's column, and the two capsules.
    std::vector<std::uint8_t> sheet(static_cast<std::size_t>(width) * height * 4);
    for (int y = 0; y < height; ++y) std::memcpy(&sheet[static_cast<std::size_t>(y) * width * 4], at(0, y), static_cast<std::size_t>(width) * 4);
    const auto from = [&](int i) {         // a capsule's column `i` of `each`, in the old capsule
        if (i < end) return capL + i;
        if (i >= each - end) return capR - (each - 1 - i);
        return c;
    };
    for (int y = (std::max)(0, top - 1); y <= (std::min)(height - 1, bottom + 1); ++y) {
        for (int x = arrowL + 1; x < arrowR; ++x) {
            const int source = x >= x0 && x < x1 ? from(x - x0) : x >= x2 && x < x3 ? from(x - x2) : gapColumn;
            std::memcpy(&sheet[(static_cast<std::size_t>(y) * width + x) * 4], at(source, y), 4);
        }
    }
    std::uint32_t hash = 2166136261u;
    for (const int v : {width, height, panel.left, panel.top, panel.width, panel.height,
                        cancel.left, cancel.top, cancel.width, cancel.height}) {
        hash = (hash ^ static_cast<std::uint32_t>(v)) * 16777619u;
    }
    for (const char* f = fill; *f; ++f) hash = (hash ^ static_cast<unsigned char>(*f)) * 16777619u;
    char drawn[17] = {};
    std::snprintf(drawn, sizeof drawn, "kmzcls%08x", hash);
    result.sheet = std::move(sheet);
    const auto screenX = [&](int tx) { return panel.left + static_cast<int>(static_cast<long long>(tx) * panel.width / width); };
    std::memcpy(result.drawn, drawn, sizeof drawn);
    result.selectAt = {screenX(x0), cancel.top, screenX(x1) - screenX(x0), cancel.height};
    result.cancelAt = {screenX(x2), cancel.top, screenX(x3) - screenX(x2), cancel.height};
    return true;
}
