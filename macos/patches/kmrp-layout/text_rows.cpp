/*
  KMRP for macOS: list rows that grow with their text, and the icons of feats, powers and skills at
  the text size and at the Icon Size slider's. The port of Windows' src/controller-native/K1TextRows.cpp
  and of the icon wrappers in K1RuntimeLayout.cpp (handoff items 57 and 130), whose rules these are.

  CSWGuiListBox (vtable 0x1005b4318), from OrganizeControls (0x1004a82b4), its unequal builder
  (0x1004a94f8) and its oversized builder (0x1004a936e); Windows' offset after each:

      +0x338 the content's rectangle; +0x340 its width, +0x344 its height     +0x294, +0x298
      +0x348 the rows, +0x350 how many                                        +0x29C, +0x2A0
      +0x358 each row's saved rectangle, +0x360 how many                      +0x2A8, +0x2AC
      +0x368 the tallest row, +0x36C the oversized list's ratio               +0x2B4, +0x2B8
      +0x370 the flags: 8 dirty, 0x80 from the top, 0x100 rows of their own   +0x2BC
             height (unequal), with PADDING in the byte above them at +0x373
      +0x376 the oversized list's page, +0x378 the rows a page holds          +0x2C2, +0x2C4
      +0x37A the selection, +0x37C the top row, +0x37E the last               +0x2C6, +0x2C8, +0x2CA
      +0x380 the prototype row                                                +0x2CC

  A fixed list's dirty pass gives every row its saved rectangle and takes the tallest as the pitch,
  so a row is made taller by its saved rectangle. Windows' GetPagesToScroll (0x4182B0) has no
  function of its own here, it is inside the oversized builder (Pages, below).

  Row classes: the offsets in Type. Each row border is 0x88 long here (Windows 0x74) and its
  extent at +0x08, its fill's flags at +0x34 with the style in the low two bits (+0x30), its fill
  at +0x80 (+0x70). A CSWGuiImage is 0x60 long (0x54): box at +0x08, drawn rectangle at +0x18
  (+0x14), picture at +0x28 (+0x24), flags at +0x54 with 2 "at the texture's own size".

  A row is forgotten by CSWGuiControl's destructor (text_fit.cpp, KmrpTextControlDestroyed).
*/
#include "text_fit.h"

#include "../../tools/kmrp-iconsize.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mach/mach.h>
#include <map>
#include <vector>

namespace kmrp {
namespace textfit {
namespace {

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

struct Rect { int left, top, width, height; };
bool Same(const Rect& a, const Rect& b) { return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height; }
bool Valid(const Rect& r) { return r.width > 0 && r.width <= 32767 && r.height > 0 && r.height <= 32767; }

const std::uintptr_t kListVtable = 0x1005b4318UL, kStringVtable = 0x1005a2860UL;
const std::size_t kExtent = 0x08;
const std::size_t kListContentHeight = 0x344, kListRows = 0x348, kListRowCount = 0x350, kListSaved = 0x358, kListSavedCount = 0x360;
const std::size_t kListTallest = 0x368, kListFlags = 0x370, kListPage = 0x376, kListVisible = 0x378, kListSelection = 0x37A;
const std::size_t kListTop = 0x37C, kListLast = 0x37E, kListPrototype = 0x380, kListRatio = 0x36C;
const std::size_t kBorderSize = 0x88, kBorderFillFlags = 0x34, kBorderFill = 0x80;
const std::size_t kImageDrawn = 0x18, kImagePicture = 0x28, kImageFlags = 0x54;
const std::size_t kVtSetExtent = 0x10, kVtImageWidth = 0x28;
const unsigned kSkillIcon = 0x220;       // the first of a skill row's three icon borders, Windows 0x1B4

// frame/hilight: the two borders a class's SetExtent pins to its icon's height instead of the
// row's (see Stretch); zero for classes that pass the row through. icon: the first of the three
// icon borders, 0x88 apart, each a native square. chart: a feat or power chart row (see Chart),
// no text of its own.
struct Kind { unsigned text = 0, amount = 0; bool content = false; unsigned frame = 0, hilight = 0, icon = 0; bool chart = false; };
Kind Type(void* row) {
    switch (At<std::uintptr_t>(row, 0)) {
        case 0x1005b3c50: case 0x1005b4638: return {0x110, 0, true};   // Label, LabelHilight
        // Button, CSWGuiButtonToggle (Graphics and Feedback option rows) and CSWGuiSaveLoadEntry
        // (save and load rows): their SetExtent (0x1004a5fa2; CSWGuiButton's own, 0x1004a5adc) give
        // every border and the text the row's whole height.
        case 0x1005b47b8: case 0x1005b3da8: case 0x1005d3090: return {0x1b8, 0, false};
        // CSWGuiInGameItemEntry and CSWGuiStoreItemEntry (inventory, store, container;
        // 0x1002be3fe, 0x1002bfb06) and CSWUpgradeItemEntry (workbench; 0x10021c020).
        case 0x1005ab5f8: case 0x1005ab848: return {0x1b8, 0x3e0, false, 0xa8, 0x130, 0x248};
        case 0x1005a5270: return {0x1b8, 0x3f0, false, 0xa8, 0x130, 0x258};
        // CSWGuiInGameSkillEntry (skill and power rows; 0x10022f21e): a highlight label whose border
        // +0x88 and highlight +0x198 are pinned to its icon's height.
        case 0x1005a6070: return {0x110, 0, false, 0x88, 0x198, kSkillIcon};
        // CSWGuiSkillFlow (the feat and power charts' rows; 0x10028cb6a).
        case 0x1005a9cd0: { Kind k; k.chart = true; return k; }
        default: return {};
    }
}
void* Part(void* p, unsigned n) { return static_cast<char*>(p) + n; }
void Extent(void* p, const Rect& r) {
    reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(At<std::uintptr_t>(p, 0) + kVtSetExtent))(p, &r);
}
void TextExtent(void* wrapper, const Rect* r) { reinterpret_cast<void (*)(void*, const Rect*)>(0x1004a3d4c)(wrapper, r); }
void Organize(void* list) { reinterpret_cast<void (*)(void*)>(0x1004a82b4)(list); }

// The stored state of a row's stretched borders (Stretch).
struct Stretched {
    int icon = 0, insetLeft = 0, insetTop = 0, insetRight = 0, insetBottom = 0;
    Rect applied{};
    unsigned fill[3] = {};
    bool fillKnown = false;
};
const unsigned kChartImages[5] = {0x110, 0x260, 0x3b0, 0x478, 0x4d8};
struct ChartImage { Rect native{}, applied{}; };
struct ChartRow { ChartImage image[5]; };
struct Row {
    std::uintptr_t table = 0;
    Rect baseline{}, applied{}, saved{};
    int inset = 0;
    double baselineScale = 1;
    bool known = false;
    bool amountKnown = false;
    Rect amountNative{}, amountApplied{};   // relative to the live icon rectangle
    int amountRightInset = 0, amountBottomInset = 0;
};
struct List {
    std::map<void*, Row> rows;
    std::uint64_t signature = 0;
    bool valid = false;
    bool busy = false;
};
struct State {
    std::map<void*, Stretched> stretched;
    std::map<void*, ChartRow> charts;
    std::map<void*, List> lists;
    int viewportHeight = 720;
    bool iconsScaled = false;   // the slider has left its default this session
    int iconPercent = -1, iconHeight = 0;
    // The granted popup (GrantedFrame): what its fill left.
    void* grantedPending = nullptr;
    struct { bool valid; int list[4], ok[4], panel[4], row, rows; } granted = {};
};
State& TheState() {
    static State* state = new State;
    return *state;
}

double IconScale() { return std::max(1.0, TextSizePercent() / 50.0); }
int IconSide(const Stretched& s) { return std::max(s.icon, std::min(32767, static_cast<int>(std::lround(s.icon * IconScale())))); }
// The row height the scaled icon needs: the icon plus the padding the native row leaves around its
// native one. Zero until the row's native geometry is known.
int IconMinimum(void* row, int baselineHeight) {
    State& all = TheState();
    const auto found = all.stretched.find(row);
    if (found == all.stretched.end() || found->second.icon <= 0) return 0;
    const int padding = std::max(0, baselineHeight - found->second.icon);
    return std::min(32767, IconSide(found->second) + padding);
}

// ------------------------------------------------------------------------ the Icon Size slider

bool SkillIconOwned() {
    State& all = TheState();
    return all.iconsScaled = all.iconsScaled || IconSizePercent() != KMRP_ICON_DEFAULT;
}
Rect CentredSquare(const Rect& box, int side) {
    if (side > box.width) side = box.width;
    if (side > box.height) side = box.height;
    return {box.left + (box.width - side) / 2, box.top + (box.height - side) / 2, side, side};
}
// An icon's side at the slider's size, from its texture (a CAurGUIImage), or 0 for none: what the
// game draws today is 50% (kmrp_icon_drawn), so at the default the square is exactly the one the
// game centred the icon in, whatever its size.
int SliderSide(void* image) {
    if (!image) return 0;
    const int today = reinterpret_cast<int (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(At<std::uintptr_t>(image, 0) + kVtImageWidth))(image);
    if (today <= 0 || today > 4096) return 0;
    return kmrp_icon_drawn(today, kmrp_icon_scale(TheState().viewportHeight), IconSizePercent());
}
void SizeSkillIcon(void* icon, const Rect& cell) {
    const int side = SliderSide(At<void*>(icon, kBorderFill));
    if (!side) return;
    unsigned char& flags = At<unsigned char>(icon, kBorderFillFlags);
    flags = (flags & ~3u) | 2u;   // the fill drawn at its area's size (CSWGuiBorder::Draw, style 2)
    const Rect box = CentredSquare(cell, side);
    if (!Same(At<Rect>(icon, kExtent), box)) Extent(icon, box);
}
// The third icon border of a skill row, +0x330 (Windows +0x29C), holds the icon's fill.
void SkillRowExtent(void* self, const Rect* extent) {
    reinterpret_cast<void (*)(void*, const Rect*)>(0x10022f21e)(self, extent);
    if (!SkillIconOwned()) return;
    // The game places nothing for a row no wider than its icon square (it returns before setting
    // the row's extent): its icon's box is then still the last one this gave it.
    if (!Same(At<Rect>(self, kExtent), *extent)) return;
    void* icon = Part(self, kSkillIcon + 2 * kBorderSize);
    const Rect cell = At<Rect>(icon, kExtent);
    SizeSkillIcon(icon, cell);
}
// A chart row's three cells: the icon, a CSWGuiImage, is given the cell's inner box and drawn at
// its own size, centred (its flags have 2, CSWGuiImage::SetExtent 0x1004a2bbc); without 2 it is
// drawn at its box's size, which is what Windows' SetScaled(0) leaves.
void ChainRowExtent(void* self, const Rect* extent) {
    reinterpret_cast<void (*)(void*, const Rect*)>(0x10028cb6a)(self, extent);
    State& all = TheState();
    if (!(all.iconsScaled = all.iconsScaled || IconSizePercent() != KMRP_ICON_DEFAULT)) return;
    for (int i = 0; i < 3; ++i) {
        void* icon = Part(self, kChartImages[i]);
        const int side = SliderSide(At<void*>(icon, kImagePicture));
        if (!side) continue;   // an empty cell
        const Rect box = At<Rect>(icon, kExtent);
        At<unsigned short>(icon, kImageFlags) &= static_cast<unsigned short>(~2u);
        const Rect square = CentredSquare(box, side);
        reinterpret_cast<void (*)(void*, const Rect*)>(0x1004a2bbc)(icon, &square);
    }
}

// Writes an int of the game's code or read-only data.
bool WriteInt(std::uintptr_t address, int value) {
    const std::uintptr_t first = address & ~std::uintptr_t(0xFFF);
    const std::size_t span = ((address + 4 + 0xFFF) & ~std::uintptr_t(0xFFF)) - first;
    if (vm_protect(mach_task_self(), first, span, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) != KERN_SUCCESS) return false;
    std::memcpy(reinterpret_cast<void*>(address), &value, 4);
    vm_protect(mach_task_self(), first, span, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
    return true;
}

// The two slots, swapped once, each only where it still holds the game's routine: both SetExtents
// are called through the table alone (the table's +0x10, the only reference to either). The tables
// are in __DATA, which is writable.
void InstallIconRows() {
    static bool tried = false;
    if (tried) return;
    tried = true;
    const struct { std::uintptr_t at, game; void* wrapper; } slots[] = {
        {0x1005a6080, 0x10022f21e, reinterpret_cast<void*>(&SkillRowExtent)},
        {0x1005a9ce0, 0x10028cb6a, reinterpret_cast<void*>(&ChainRowExtent)},
    };
    for (const auto& s : slots) {
        auto* const slot = reinterpret_cast<std::uintptr_t*>(s.at);
        if (*slot == s.game) *slot = reinterpret_cast<std::uintptr_t>(s.wrapper);
    }
}

// The rows sized for the icons (Windows' engine recipe, KmrpEngineFieldValue, its kind 3 at the
// chart row's and the skill row's height): the chart row's rectangle 0x100570efc, read by both
// creators, and the skill row's icon square and height, 0x10022f257 and 0x10022f60f. The widescreen
// patch writes all three for the size, 50 scaled; written again here whenever the size or the slider
// moves. At the default and below, and until the slider has left its default this session,
// nothing is touched.
void ApplyIconRows(int height) {
    State& all = TheState();
    const int percent = IconSizePercent();
    if (percent == all.iconPercent && height == all.iconHeight) return;
    all.iconPercent = percent;
    all.iconHeight = height;
    if (percent <= KMRP_ICON_DEFAULT && !all.iconsScaled) return;
    all.iconsScaled = true;
    const double scale = kmrp_icon_scale(height);
    const int row = static_cast<int>(std::floor(KMRP_ICON_ROW_BASE * static_cast<float>(scale) + 0.5f));
    WriteInt(0x100570efc, kmrp_icon_chain_row(row, scale, percent));
    const int skill = kmrp_icon_skill_row(row, scale, percent);
    WriteInt(0x10022f257, skill);
    WriteInt(0x10022f60f, skill);
}

// ------------------------------------------------------------------------ chart rows

// A feat or power chart row (CSWGuiSkillFlow) lays out three cells, each a square as tall as the
// row, at its left, centre and right (SetExtent, 0x10028cb6a): from +0x88, 0x150 apart, each with
// its border, the feat icon (a CSWGuiImage at +0x110 of the row for the first) and the lbl_indent
// background stretched over the cell (+0x170); and two lbl_skarr arrows (+0x478, +0x4D8) of a fixed
// 32 x 32, centred between them. The cells follow the row's height; the icon and the arrows do
// not: they are drawn at the texture's own size, centred, in the rectangle at +0x18, all the draw
// uses (0x1004a2e86). So the row grows with the icon scale (ChartHeight) and each of those five
// drawn rectangles is scaled by it about its own centre, an icon kept inside its cell. The drawn
// rectangle is whatever SetExtent last left there, so it is re-read whenever it is not the one this
// put.
void Chart(void* row) {
    const double scale = IconScale();
    const Rect outer = At<Rect>(row, kExtent);
    if (!Valid(outer)) return;
    ChartRow& state = TheState().charts[row];
    for (unsigned i = 0; i < 5; ++i) {
        void* const image = Part(row, kChartImages[i]);
        Rect& drawn = At<Rect>(image, kImageDrawn);
        if (!Valid(drawn)) continue;
        ChartImage& s = state.image[i];
        if (!Same(drawn, s.applied)) s.native = drawn;
        const Rect box = i < 3 ? At<Rect>(image, kExtent) : Rect{outer.left, outer.top, outer.width, outer.height};
        const int width = std::max(1, std::min(Valid(box) ? box.width : 32767, static_cast<int>(std::lround(s.native.width * scale))));
        const int height = std::max(1, std::min(Valid(box) ? box.height : 32767, static_cast<int>(std::lround(s.native.height * scale))));
        const Rect scaled{s.native.left + (s.native.width - width) / 2, s.native.top + (s.native.height - height) / 2, width, height};
        if (!Same(drawn, scaled)) drawn = scaled;
        s.applied = scaled;
    }
}
int ChartHeight(int baseline) { return std::max(1, std::min(32767, static_cast<int>(std::lround(baseline * IconScale())))); }

// ------------------------------------------------------------------------ item and skill rows

// CSWGuiStoreItemEntry::SetExtent and its two kin (the offsets in Type) give the row's border,
// highlight and text the icon's fixed height whatever height the row itself is given. A grown row
// kept its text in that native box, so a two-line name showed only its last line. Stretch the
// frame, highlight and text to the row's full height.
//
// The icon (the same square native art, drawn larger) grows with the requested menu text size:
// percent / 50, where 50 is the size the game had before, and never below the native square. It
// follows the text size, not the row's height, so a larger icon cannot narrow the text into more
// lines, grow the row and enlarge the icon again. Rows are kept at least the icon's height plus the
// native padding (IconMinimum), and the icon is centred. Text and frame start right of it, keeping
// the native insets the game gave the text inside its frame.
//
// The native layout calls SetExtent again on every pass, scrolling included, which resets all of
// this; so it is checked on every list draw, and the native geometry is re-read whenever the icon
// is not where this put it.
//
// The icon's borders fill with textures the game draws one texel per pixel and tiles
// (CSWGuiBorder::Draw, 0x1004a1e40: style 0 tiles, 1 centres, 2 stretches). In a larger box a
// lbl_hex_3 frame tiled into four corner pieces (seen in play on Windows, 2026-10-18). So a scaled
// icon's borders are switched to stretch and get their own style back at the native size.
void Stretch(void* row) {
    const Kind kind = Type(row);
    if (kind.chart) { Chart(row); return; }
    if (!kind.frame) return;
    const Rect outer = At<Rect>(row, kExtent);
    void* const iconPart = Part(row, kind.icon);
    void* const frameBorder = Part(row, kind.frame);
    void* const textWrapper = Part(row, kind.text);
    const Rect icon = At<Rect>(iconPart, kExtent), frame = At<Rect>(frameBorder, kExtent), text = At<Rect>(textWrapper, kExtent);
    if (!Valid(outer) || !Valid(icon) || !Valid(frame) || !Valid(text)) return;
    Stretched& s = TheState().stretched[row];
    if (!Same(icon, s.applied)) {
        // A native SetExtent ran since this last did: record what it laid out.
        s.icon = icon.width;
        s.insetLeft = text.left - frame.left;
        s.insetTop = text.top - frame.top;
        s.insetRight = frame.left + frame.width - (text.left + text.width);
        s.insetBottom = frame.top + frame.height - (text.top + text.height);
    }
    const int side = std::min(IconSide(s), outer.height);
    const Rect newIcon{outer.left, outer.top + (outer.height - side) / 2, side, side};
    const Rect newFrame{outer.left + side, outer.top, outer.width - side, outer.height};
    const Rect newText{newFrame.left + s.insetLeft, newFrame.top + s.insetTop, newFrame.width - s.insetLeft - s.insetRight,
                       newFrame.height - s.insetTop - s.insetBottom};
    if (!Valid(newFrame) || !Valid(newText)) return;
    // Two rules sized a skill row's icon: this one, by Text Size, and the Icon Size slider's. The
    // slider owns it (the maintainer, Windows' GUI-2), in the box this gives the row's icon.
    const unsigned sized = kind.icon == kSkillIcon && SkillIconOwned() ? kind.icon + 2 * kBorderSize : 0;
    for (unsigned part = 0; part < 3; ++part) {
        if (sized && kind.icon + part * kBorderSize == sized) continue;
        unsigned char& flags = At<unsigned char>(Part(row, kind.icon + part * kBorderSize), kBorderFillFlags);
        if (!s.fillKnown) s.fill[part] = flags & 3u;
        const unsigned style = side > s.icon ? 2u : s.fill[part];
        if ((flags & 3u) != style) flags = (flags & ~3u) | style;
    }
    s.fillKnown = true;
    if (!Same(icon, newIcon))
        for (unsigned part = 0; part < 3; ++part) Extent(Part(row, kind.icon + part * kBorderSize), newIcon);
    if (sized) SizeSkillIcon(Part(row, sized), newIcon);
    if (!Same(frame, newFrame)) {
        Extent(frameBorder, newFrame);
        Extent(Part(row, kind.hilight), newFrame);
    }
    if (!Same(text, newText)) TextExtent(textWrapper, &newText);
    s.applied = newIcon;
}
void StretchAll(void** rows, int count) {
    for (int i = 0; i < count; ++i)
        if (rows[i]) Stretch(rows[i]);
}

std::uint64_t Mix(std::uint64_t a, std::uint64_t b) { return (a ^ b) * 1099511628211ull; }
std::uint64_t TextSignature(void* wrapper) {
    void* text = At<void*>(wrapper, 0x18);
    std::uint64_t h = reinterpret_cast<std::uintptr_t>(text);
    const Rect bounds = At<Rect>(wrapper, kExtent);
    h = Mix(Mix(h, bounds.width), bounds.height);
    if (!text || At<std::uintptr_t>(text, 0) != kStringVtable) return h;
    const unsigned char* value = At<unsigned char*>(text, 0x18);
    h = Mix(h, reinterpret_cast<std::uintptr_t>(value));
    // String buffers can be reused. Pointer and length identity alone miss a changed word boundary
    // or a different-width digit at the same address.
    if (value) for (unsigned i = 0; i < 65536; ++i) {
        h = Mix(h, value[i]);
        if (!value[i]) break;
    }
    h = Mix(h, reinterpret_cast<std::uintptr_t>(At<void*>(text, 0x20)));
    h = Mix(h, At<unsigned>(text, 0x50));
    h = Mix(h, At<unsigned>(text, 0x58));   // local scale bits; the generation covers the fonts
    return h;
}
double ViewScale() { return std::max(1.0, TheState().viewportHeight / 720.0); }
int Minimum(const Row& row) {
    const double height = row.baseline.height * ViewScale() / row.baselineScale;
    return std::max(1, std::min(32767, static_cast<int>(std::lround(height))));
}
std::uint64_t Signature(void* list, void** rows, int count) {
    std::uint64_t h = Mix(Mix(1469598103934665603ull, Generation()), TheState().viewportHeight);
    const Rect r = At<Rect>(list, kExtent);
    h = Mix(Mix(Mix(h, r.width), r.height), At<unsigned>(list, kListFlags) & 0x108);
    h = Mix(h, reinterpret_cast<std::uintptr_t>(rows));
    h = Mix(h, count);
    for (int i = 0; i < count; ++i) if (rows[i]) {
        void* p = rows[i];
        const Kind kind = Type(p);
        h = Mix(h, reinterpret_cast<std::uintptr_t>(p));
        h = Mix(h, At<std::uintptr_t>(p, 0));
        const Rect extent = At<Rect>(p, kExtent);
        h = Mix(Mix(h, extent.width), extent.height);
        if (kind.text) h = Mix(h, TextSignature(Part(p, kind.text)));
        if (kind.amount) h = Mix(h, TextSignature(Part(p, kind.amount)));
    }
    return h;
}
void FlowRow(void* row) {
    if (!row) return;
    const Kind kind = Type(row);
    if (kind.text) Flow(Part(row, kind.text));
}
void Amounts(void** rows, int count, std::map<void*, Row>& states) {
    State& all = TheState();
    for (int i = 0; i < count; ++i) if (rows[i]) {
        void* p = rows[i];
        const Kind kind = Type(p);
        auto found = states.find(p);
        if (!kind.amount || found == states.end()) continue;
        Row& state = found->second;
        void* wrapper = Part(p, kind.amount);
        const Rect icon = At<Rect>(Part(p, kind.icon), kExtent);
        const Rect outer = At<Rect>(p, kExtent);
        const Rect current = At<Rect>(wrapper, kExtent);
        if (!Valid(icon) || !Valid(current) || !Valid(outer)) { Bounded(wrapper); continue; }
        const Rect relative{current.left - icon.left, current.top - icon.top, current.width, current.height};
        if (!state.amountKnown || !Same(relative, state.amountApplied)) {
            // A native SetExtent placed the counter against the native icon square at the row's
            // top-left; Stretch may already have scaled and centred the live icon, so measure the
            // native insets against the square the game used.
            Rect native = icon;
            const auto scaled = all.stretched.find(p);
            if (scaled != all.stretched.end() && scaled->second.icon > 0)
                native = {outer.left, outer.top, scaled->second.icon, scaled->second.icon};
            const Rect nativeRelative{current.left - native.left, current.top - native.top, current.width, current.height};
            state.amountNative = nativeRelative;
            state.amountKnown = true;
            state.amountRightInset = native.width - nativeRelative.left - nativeRelative.width;
            state.amountBottomInset = native.height - nativeRelative.top - nativeRelative.height;
        }
        // The game put a fixed-size count box flush with the icon square's corner, so a larger
        // count overflowed it and stood past the hex frame. The count is a box the size of its
        // digits at the requested size, its bottom-right corner at (52, 54) of the 56 px lbl_hex_6
        // art, in proportion to the live icon, at every size and text size (the maintainer's
        // choice, 2026-10-18). Capped at half the icon each way; the fit below shrinks a count too
        // long for that. Placed from the live icon each time, so nothing accumulates.
        Flow(wrapper);   // measure at the requested scale before any cap
        const double naturalWidth = NaturalWidth(wrapper);
        const double naturalHeight = NaturalLineHeight(wrapper);
        Rect desired = current;
        if (std::isfinite(naturalWidth) && std::isfinite(naturalHeight) && naturalWidth > 0 && naturalWidth <= 32767 &&
            naturalHeight > 0 && naturalHeight <= 32767) {
            desired.width = std::max(1, std::min(icon.width / 2, static_cast<int>(std::ceil(naturalWidth))));
            desired.height = std::max(1, std::min(icon.height / 2, static_cast<int>(std::ceil(naturalHeight))));
            desired.left = icon.left + static_cast<int>(std::lround(icon.width * (52.0 / 56.0))) - desired.width;
            desired.top = icon.top + static_cast<int>(std::lround(icon.height * (54.0 / 56.0))) - desired.height;
            desired.left = std::min(desired.left, outer.left + outer.width - desired.width);
            desired.top = std::min(desired.top, outer.top + outer.height - desired.height);
            if (!Same(current, desired)) TextExtent(wrapper, &desired);
        }
        state.amountApplied = {desired.left - icon.left, desired.top - icon.top, desired.width, desired.height};
        Bounded(wrapper);   // cap only overflow beyond the live icon and row
    }
}

// Windows' GetPagesToScroll (0x4182B0), as the oversized builder (0x1004a936e) works it out.
int Pages(void* list) {
    const int viewport = At<int>(list, kListContentHeight);
    if (viewport == 0) return 1;
    const float ratio = At<float>(list, kListRatio);
    return (1 - static_cast<int>(ratio)) + static_cast<int>(static_cast<float>(At<int>(list, kListTallest)) * ratio / static_cast<float>(viewport) + 0.9999f);
}

}  // namespace

// The granted popup: the GUI manager's +0x128, vtable 0x1005a9e18, LB_SKILLS at +0x80, OK at +0x5B8
// (granted_popup.cpp). Its fill cuts the list to the rows' height at that moment and the rows then
// grow with the text size, so a grown row outgrew the list and was cut off (Windows, measured
// 2026-10-18: "Critical Strike" at 100%, row 228, list inner 109). So the list grows with its rows
// again, OK moves down and the panel grows by the same, keeping its centre; by at most half the
// popup's own height, so it is never more than 1.5 times its size (the maintainer's limit), and
// beyond that the list scrolls. Measured from what the fill left, so it never accumulates. Windows'
// KmrpGrantedPopupFrameK1. Windows reads what the fill left in the fill; here the fill's fit may be
// the widescreen patch's stub, so it is read as the list is first adapted after the fill, before
// a row has grown (GrantedBaseline, from Rows).
const std::size_t kGrantedList = 0x80, kGrantedOk = 0x5b8;
const std::uintptr_t kGrantedVtable = 0x1005a9e18UL;
void GrantedBaseline(void* list) {
    State& all = TheState();
    if (all.grantedPending != list) return;
    all.grantedPending = nullptr;
    char* const popup = static_cast<char*>(list) - kGrantedList;
    std::memcpy(all.granted.list, &At<int>(list, kExtent), sizeof all.granted.list);
    std::memcpy(all.granted.ok, &At<int>(popup + kGrantedOk, kExtent), sizeof all.granted.ok);
    std::memcpy(all.granted.panel, &At<int>(popup, kExtent), sizeof all.granted.panel);
    all.granted.row = At<int>(list, kListTallest);
    const int count = At<int>(list, kListRowCount), fit = At<short>(list, kListVisible);
    all.granted.rows = count < fit ? count : fit;
    all.granted.valid = true;
}

void Rows(void* list) {
    if (!list || At<std::uintptr_t>(list, 0) != kListVtable) return;
    GrantedBaseline(list);
    State& all = TheState();
    auto& state = all.lists[list];
    if (state.busy) return;
    void** rows = At<void**>(list, kListRows);
    const int count = At<int>(list, kListRowCount);
    if (count < 0 || count > 4096 || (count && !rows)) return;
    FlowRow(At<void*>(list, kListPrototype));
    if (!count) { state.rows.clear(); state.valid = false; return; }
    StretchAll(rows, count);   // before the signature: undo a native layout pass's reset
    const auto signature = Signature(list, rows, count);
    if (state.valid && state.signature == signature) return;
    state.busy = true;
    Rect* saved = At<Rect*>(list, kListSaved);
    const int savedCount = At<int>(list, kListSavedCount);
    const bool fixed = !(At<unsigned>(list, kListFlags) & 0x100);
    // The fixed native dirty pass restores every saved extent before measuring. Refuse malformed
    // native arrays rather than leaving a partially adapted list.
    if (fixed && (!saved || savedCount != count)) { state.busy = false; return; }
    for (int pass = 0; pass < 3; ++pass) {
        std::map<void*, Row> next;
        bool changed = false;
        for (int i = 0; i < count; ++i) {
            void* p = rows[i];
            if (!p) continue;
            const Kind kind = Type(p);
            if (!kind.text && !kind.chart) continue;
            const Rect current = At<Rect>(p, kExtent);
            if (!Valid(current)) continue;
            Row row;
            const auto old = state.rows.find(p);
            if (old != state.rows.end() && old->second.table == At<std::uintptr_t>(p, 0)) row = old->second;
            // A native repopulation or resolution change supplies a new authored extent. Keep the
            // last native baseline otherwise, including when font sizes shrink.
            const bool newGeometry = !row.known || current.width != row.applied.width || (fixed && saved[i].height != row.saved.height);
            if (newGeometry) {
                const int previousBase = row.baseline.height;
                const bool authoredHeight = !row.known || (fixed && saved[i].height != row.saved.height);
                row.table = At<std::uintptr_t>(p, 0);
                row.baseline = fixed ? saved[i] : current;
                // A width-only reflow must not promote our expanded saved height to the new
                // minimum. Native replacement heights are adopted explicitly.
                if (!authoredHeight) row.baseline.height = previousBase;
                else row.baselineScale = ViewScale();
                if (kind.text) {
                    const Rect textRect = At<Rect>(Part(p, kind.text), kExtent);
                    row.inset = std::max(0, current.height - textRect.height);
                }
                row.known = true;
            }
            FlowRow(p);
            // The text's final width, right of a scaled icon, before measuring it.
            Stretch(p);
            if (kind.chart) {
                Rect desired = current;
                desired.height = ChartHeight(Minimum(row));
                if (fixed) {
                    Rect target = saved[i];
                    target.height = desired.height;
                    if (!Same(saved[i], target)) { saved[i] = target; changed = true; }
                    row.saved = saved[i];
                }
                if (current.height != desired.height) { Extent(p, desired); changed = true; }
                row.applied = At<Rect>(p, kExtent);
                next[p] = row;
                continue;
            }
            // Native layout already supplied the real text width and border insets.
            // NaturalHeight restores the requested scale and wraps at that width.
            const int natural = NaturalHeight(Part(p, kind.text));
            if (natural <= 0 || natural > 32767 - row.inset) { row.applied = current; next[p] = row; continue; }
            Rect desired = current;
            desired.height = natural + row.inset;
            if (!kind.content) desired.height = std::max(Minimum(row), desired.height);
            if (kind.frame) desired.height = std::max(desired.height, IconMinimum(p, Minimum(row)));
            desired.height = std::max(1, std::min(32767, desired.height));
            if (fixed) {
                Rect target = saved[i];
                target.height = desired.height;
                if (!Same(saved[i], target)) { saved[i] = target; changed = true; }
                row.saved = saved[i];
            }
            if (current.height != desired.height) { Extent(p, desired); changed = true; }
            row.applied = At<Rect>(p, kExtent);
            next[p] = row;
        }
        if (changed || (At<unsigned>(list, kListFlags) & 8)) {
            const short top = At<short>(list, kListTop);
            const short selection = At<short>(list, kListSelection);
            const short page = At<short>(list, kListPage);
            At<unsigned char>(list, kListFlags) |= 8;
            Organize(list);
            // The dirty layout resets top-visible. Retain the player's position, then let its
            // normal placement and scrollbar path consume the restored index.
            const int visible = std::max(1, static_cast<int>(At<short>(list, kListVisible)));
            const short restored = static_cast<short>(std::max(0, std::min(static_cast<int>(top), std::max(0, count - (fixed ? visible : 1)))));
            At<short>(list, kListSelection) = selection >= -1 && selection < count ? selection : -1;
            if (At<short>(list, kListTop) != restored) {
                At<short>(list, kListTop) = restored;
                if (!fixed) { At<short>(list, kListLast) = -1; At<unsigned char>(list, kListFlags) |= 0x80; }
                Organize(list);
            }
            if (fixed) {
                // Oversized content uses a separate one-based page index, not top-visible. The
                // dirty layout recomputes the ratio from the current viewport and font height, and
                // the page is clamped as the game's drag handling does.
                const int viewport = At<int>(list, kListContentHeight);
                if (viewport > 0 && At<int>(list, kListTallest) > viewport) {
                    const int pages = Pages(list);
                    const short restoredPage = static_cast<short>(std::max(1, std::min(static_cast<int>(page), std::min(32767, std::max(1, pages)))));
                    if (At<short>(list, kListPage) != restoredPage) {
                        At<short>(list, kListPage) = restoredPage;
                        reinterpret_cast<void (*)(void*)>(0x1004a936e)(list);
                    }
                } else {
                    At<short>(list, kListPage) = 1;
                }
            }
        }
        for (auto& entry : next) entry.second.applied = At<Rect>(entry.first, kExtent);
        state.rows.swap(next);
        StretchAll(rows, count);   // the native pass above reset the entry rows' boxes
        bool settled = true;
        for (const auto& entry : state.rows) {
            const Kind kind = Type(entry.first);
            if (kind.chart) {
                const int allocated = fixed ? entry.second.saved.height : At<Rect>(entry.first, kExtent).height;
                if (ChartHeight(Minimum(entry.second)) != allocated) settled = false;
                continue;
            }
            const int natural = NaturalHeight(Part(entry.first, kind.text));
            int needed = kind.content ? natural + entry.second.inset : std::max(Minimum(entry.second), natural + entry.second.inset);
            if (kind.frame) needed = std::max(needed, IconMinimum(entry.first, Minimum(entry.second)));
            const int allocated = fixed ? entry.second.saved.height : At<Rect>(entry.first, kExtent).height;
            if (natural > 0 && needed > 0 && needed <= 32767 && needed != allocated) settled = false;
        }
        if (settled) break;
        if (pass == 2) for (const auto& entry : state.rows) {
            const Kind kind = Type(entry.first);
            if (kind.text) Bounded(Part(entry.first, kind.text));
        }
    }
    Amounts(rows, count, state.rows);   // after the final native row SetExtent
    StretchAll(rows, count);
    state.signature = Signature(list, rows, count);
    state.valid = true;
    state.busy = false;
}

void RowsForget(void* control) {
    State& all = TheState();
    all.lists.erase(control);
    all.stretched.erase(control);
    all.charts.erase(control);
    for (auto& list : all.lists)
        if (list.second.rows.erase(control)) list.second.valid = false;
}

void GrantedFilled(void* list) {
    if (list && At<std::uintptr_t>(static_cast<char*>(list) - kGrantedList, 0) == kGrantedVtable) TheState().grantedPending = list;
}

void GrantedFrame(void* manager) {
    State& all = TheState();
    if (!all.granted.valid) return;
    char* const popup = At<char*>(manager, 0x128);
    if (!popup || At<std::uintptr_t>(popup, 0) != kGrantedVtable) return;
    void* const list = popup + kGrantedList;
    const int row = At<int>(list, kListTallest);
    const int count = At<int>(list, kListRowCount);
    if (row <= 0 || row > 32767 || count <= 0 || count > 64) return;
    // Only the rows the fill showed, and only by what each has grown since: a popup with more
    // feats than fit already scrolls.
    int grow = all.granted.rows * (row - all.granted.row);
    if (grow < 0) grow = 0;
    if (grow > all.granted.panel[3] / 2) grow = all.granted.panel[3] / 2;
    Rect extent, ok, panel;
    std::memcpy(&extent, all.granted.list, sizeof extent);
    std::memcpy(&ok, all.granted.ok, sizeof ok);
    std::memcpy(&panel, all.granted.panel, sizeof panel);
    extent.height += grow;
    ok.top += grow;
    panel.top -= grow / 2;
    panel.height += grow;
    if (!Same(At<Rect>(list, kExtent), extent)) Extent(list, extent);
    if (!Same(At<Rect>(popup + kGrantedOk, kExtent), ok)) Extent(popup + kGrantedOk, ok);
    if (!Same(At<Rect>(popup, kExtent), panel)) Extent(popup, panel);
}

void RowsViewport(int height) {
    if (height > 0 && height <= 32767) TheState().viewportHeight = height;
    InstallIconRows();
    ApplyIconRows(TheState().viewportHeight);
}

}  // namespace textfit
}  // namespace kmrp
