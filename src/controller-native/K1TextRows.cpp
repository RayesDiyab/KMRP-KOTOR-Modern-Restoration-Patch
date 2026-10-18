// Font-aware native list content. Address evidence and dirty-layout side effects:
// build/text-layout-inventory/row-adapter-contract/contract.json;
// reverse-engineering/listbox-geometry.md and docs/native-text-coverage.md.
#include "K1TextRows.h"
#include "K1TextLayout.h"
#include "K1TextOptions.h"
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <cstring>
#include <map>
#include <vector>

#ifdef KMRP_TEXT_LAYOUT_TEST
extern void* KmrpTextRowsTestFunctionK1(std::uintptr_t address);
#endif
namespace {
template<class T> T& F(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p) + n); }
template<class T> T Fn(std::uintptr_t address) {
#ifdef KMRP_TEXT_LAYOUT_TEST
    return reinterpret_cast<T>(KmrpTextRowsTestFunctionK1(address));
#else
    return reinterpret_cast<T>(address);
#endif
}
struct Rect { int left, top, width, height; };
bool Same(const Rect& a, const Rect& b) { return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height; }
bool Valid(const Rect& r) { return r.width > 0 && r.width <= 32767 && r.height > 0 && r.height <= 32767; }
// frame/hilight: the two borders a class's SetExtent pins to its icon's height
// instead of the row's (see Stretch); zero for classes that pass the row through.
// icon: the first of the three icon borders, 0x74 apart, each a native square.
// chart: a feat or power chart row (see Chart), no text of its own.
struct Kind { unsigned text = 0, amount = 0; bool content = false; unsigned frame = 0, hilight = 0, icon = 0; bool chart = false; };
Kind Type(void* row) {
    switch (F<std::uintptr_t>(row, 0)) {
        case 0x73E5B8: case 0x73E8E8: return {0xD0, 0, true}; // Label / LabelHilight
        // Button, CSWGuiButtonToggle (Graphics/Feedback option rows) and
        // CSWGuiSaveLoadEntry (save/load rows). The toggle's SetExtent (0x417BA0)
        // and the save entry's, CSWGuiButton's own (0x417A20), give every border
        // and the text the row's whole height (decompiled 2026-10-17).
        case 0x73E658: case 0x73EB88: case 0x757740: return {0x154, 0, false};
        // CSWGuiInGameItemEntry and CSWGuiStoreItemEntry (inventory, store,
        // container; 0x6B5270) and CSWUpgradeItemEntry (workbench; 0x6C2650).
        case 0x7568F8: case 0x756850: return {0x154, 0x324, false, 0x6C, 0xE0, 0x1C8};
        case 0x757108: return {0x154, 0x334, false, 0x6C, 0xE0, 0x1D8};
        // CSWGuiInGameSkillEntry (skill and power rows; 0x6AB8E0): a highlight
        // label whose border +0x5C and highlight +0x140 are pinned to 0x2A, scaled.
        case 0x755ED0: return {0xD0, 0, false, 0x5C, 0x140, 0x1B4};
        // CSWGuiSkillFlow (the feat and power charts' rows; 0x6CCE30).
        case 0x7578A8: { Kind k; k.chart = true; return k; }
        default: return {};
    }
}
void* At(void* p, unsigned n) { return static_cast<char*>(p) + n; }
void Extent(void* p, const Rect& r) {
#ifdef KMRP_TEXT_LAYOUT_TEST
    const auto method = F<std::uintptr_t>(p, 0); // test resolver maps the class's SetExtent
#else
    const auto method = F<std::uintptr_t*>(p, 0)[1];
#endif
    Fn<void(__thiscall*)(void*, const Rect*)>(method)(p, &r);
}
void Organize(void* list) { Fn<void(__thiscall*)(void*)>(0x41B140)(list); }
// CSWGuiStoreItemEntry::SetExtent (0x6B5270: inventory, store and container rows),
// CSWUpgradeItemEntry::SetExtent (0x6C2650: workbench rows) and
// CSWGuiInGameSkillEntry::SetExtent (0x6AB8E0: skills and powers) give the row's
// border, highlight and text the icon's fixed height, 0x38 or 0x2A scaled, whatever
// height the row itself is given (decompiled 2026-10-17; offsets in Type). A grown
// row kept its text in that native box, so a two-line name showed only its last
// line (measured in play at 1920x1080: row 103, text box 654 x 76, two lines).
// Stretch the frame, highlight and text to the row's full height.
//
// The icon (the same square native art, drawn larger; nothing is regenerated)
// grows with the requested menu text size: KmrpTextSizePercentK1 / 50, where 50
// is the size the game had before, and never below the native square. It follows
// the text size, not the row's height, so a larger icon cannot narrow the text into
// more lines, grow the row and enlarge the icon again. Rows are kept at least the
// icon's height plus the native padding (IconMinimum), and the icon is centred.
// Text and frame start right of it, keeping the native insets the game gave the
// text inside its frame.
//
// The native layout calls SetExtent again on every pass, scrolling included,
// which resets all of this; so it is checked on every list draw, and the native
// geometry is re-read whenever the icon is not where this put it.
// The icon's borders fill with textures the game draws one texel per pixel and TILES
// (CSWGuiBorder::Draw, 0x004168C0: FILLSTYLE 0 tiles, 1 centres, 2 stretches; the
// low two bits of the flags at +0x1C of the border's params, which sit at +0x14). The
// row constructor (0x006B4DB0) gives its lbl_hex_3 frames style 0, which is why the
// installer bakes that frame at exactly the icon box's size. In a larger box it tiled
// into four corner pieces (seen in play, 2026-10-18). So a scaled icon's borders are
// switched to stretch, drawing the same art larger, and get their own style back at
// the native size, where the baked art fits one texel per pixel.
constexpr unsigned kBorderFillFlags = 0x14 + 0x1C;
struct Stretched {
    int icon = 0, insetLeft = 0, insetTop = 0, insetRight = 0, insetBottom = 0; Rect applied{};
    unsigned fill[3] = {}; bool fillKnown = false;
};
std::map<void*, Stretched> stretched;
double IconScale() { return std::max(1.0, KmrpTextSizePercentK1() / 50.0); }
int IconSide(const Stretched& s) {
    return std::max(s.icon, std::min(32767, static_cast<int>(std::lround(s.icon * IconScale()))));
}
// The row height the scaled icon needs: the icon plus the padding the native row
// leaves around its native one. Zero until the row's native geometry is known.
int IconMinimum(void* row, int baselineHeight) {
    const auto found = stretched.find(row);
    if (found == stretched.end() || found->second.icon <= 0) return 0;
    const int padding = std::max(0, baselineHeight - found->second.icon);
    return std::min(32767, IconSide(found->second) + padding);
}
// A feat or power chart row (CSWGuiSkillFlow, 0x7578A8) lays out three cells, each a
// square as tall as the row, at its left, centre and right (SetExtent, 0x006CCE30):
// a CSWGuiFlowSkillStruct of 0x128 bytes from +0x5C, holding the cell's border, the
// feat icon (a CSWGuiImage at +0x74) and the lbl_indent background stretched over the
// cell (+0xC8); and two lbl_skarr arrows (+0x3D4, +0x428) of a fixed 32 x 32, centred
// between them. The cells, their borders and backgrounds follow the row's height. The
// icon and the arrows do not: the constructor (0x006CCCC0) gives them draw style 1,
// drawn at the texture's own size, centred, whatever the box. CSWGuiImage::SetExtent
// (0x00415B70) works that rectangle out and keeps it at +0x14, which is all
// CSWGuiImage::Draw (0x00415C90) uses (decompiled 2026-10-18; at 50% at 3440x1440 the
// rows were 100 high, cells 100 x 100 at 22, 647 and 1273, arrows 32 x 32: read from
// the running game). So the row grows with the icon scale (ChartHeight) and each of
// those five drawn rectangles is scaled by it about its own centre: the same art drawn
// larger, as the inventory's icons are. An icon stays inside its cell. The drawn
// rectangle is whatever SetExtent last left there, so it is re-read whenever it is
// not the one this put.
constexpr unsigned kChartImages[5] = {0x5C + 0x74, 0x184 + 0x74, 0x2AC + 0x74, 0x3D4, 0x428};
struct ChartImage { Rect native{}, applied{}; };
struct ChartRow { ChartImage image[5]; };
std::map<void*, ChartRow> charts;
void Chart(void* row) {
    const double scale = IconScale();
    const Rect outer = F<Rect>(row, 4);
    if (!Valid(outer)) return;
    ChartRow& state = charts[row];
    for (unsigned i = 0; i < 5; ++i) {
        void* const image = At(row, kChartImages[i]);
        Rect& drawn = F<Rect>(image, 0x14);
        if (!Valid(drawn)) continue;
        ChartImage& s = state.image[i];
        if (!Same(drawn, s.applied)) s.native = drawn;
        const Rect box = i < 3 ? F<Rect>(image, 4) : Rect{outer.left, outer.top, outer.width, outer.height};
        const int width = std::max(1, std::min(Valid(box) ? box.width : 32767, static_cast<int>(std::lround(s.native.width * scale))));
        const int height = std::max(1, std::min(Valid(box) ? box.height : 32767, static_cast<int>(std::lround(s.native.height * scale))));
        const Rect scaled{s.native.left + (s.native.width - width) / 2, s.native.top + (s.native.height - height) / 2, width, height};
        if (!Same(drawn, scaled)) drawn = scaled;
        s.applied = scaled;
    }
}
// The chart row's height: its native one (100 at 50% at 3440x1440) times the icon scale.
int ChartHeight(int baseline) {
    return std::max(1, std::min(32767, static_cast<int>(std::lround(baseline * IconScale()))));
}
void Stretch(void* row) {
    const Kind kind = Type(row);
    if (kind.chart) { Chart(row); return; }
    if (!kind.frame) return;
    const Rect outer = F<Rect>(row, 4);
    void* const iconPart = At(row, kind.icon);
    void* const frameBorder = At(row, kind.frame);
    void* const textWrapper = At(row, kind.text);
    const Rect icon = F<Rect>(iconPart, 4), frame = F<Rect>(frameBorder, 4), text = F<Rect>(textWrapper, 4);
    if (!Valid(outer) || !Valid(icon) || !Valid(frame) || !Valid(text)) return;
    Stretched& s = stretched[row];
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
    const Rect newText{newFrame.left + s.insetLeft, newFrame.top + s.insetTop,
                       newFrame.width - s.insetLeft - s.insetRight,
                       newFrame.height - s.insetTop - s.insetBottom};
    if (!Valid(newFrame) || !Valid(newText)) return;
    for (unsigned part = 0; part < 3; ++part) {
        unsigned& flags = F<unsigned>(At(row, kind.icon + part * 0x74), kBorderFillFlags);
        if (!s.fillKnown) s.fill[part] = flags & 3u;
        const unsigned style = side > s.icon ? 2u : s.fill[part];
        if ((flags & 3u) != style) flags = (flags & ~3u) | style;
    }
    s.fillKnown = true;
    if (!Same(icon, newIcon))
        for (unsigned part = 0; part < 3; ++part) Extent(At(row, kind.icon + part * 0x74), newIcon);
    if (!Same(frame, newFrame)) {
        Extent(frameBorder, newFrame);
        Extent(At(row, kind.hilight), newFrame);
    }
    if (!Same(text, newText))
        Fn<void(__thiscall*)(void*, const Rect*)>(0x416280)(textWrapper, &newText);
    s.applied = newIcon;
}
void StretchAll(void** rows, int count) {
    for (int i = 0; i < count; ++i) if (rows[i]) Stretch(rows[i]);
}
std::uint64_t Mix(std::uint64_t a, std::uint64_t b) { return (a ^ b) * 1099511628211ull; }
std::uint64_t TextSignature(void* wrapper) {
    void* text = F<void*>(wrapper, 0x14);
    std::uint64_t h = reinterpret_cast<std::uintptr_t>(text);
    const Rect bounds = F<Rect>(wrapper, 4);
    h = Mix(Mix(h, bounds.width), bounds.height);
    if (!text || F<std::uintptr_t>(text, 0) != 0x741878) return h;
    const unsigned char* value = F<unsigned char*>(text, 0x14);
    h = Mix(h, reinterpret_cast<std::uintptr_t>(value));
    // CExoString buffers can be reused. Pointer/length identity alone misses a
    // changed word boundary or a different-width digit at the same address.
    if (value) for (unsigned i = 0; i < 65536; ++i) {
        h = Mix(h, value[i]); if (!value[i]) break;
    }
    h = Mix(h, reinterpret_cast<std::uintptr_t>(F<void*>(text, 0x18)));
    h = Mix(h, F<unsigned>(text, 0x38));
    h = Mix(h, F<unsigned>(text, 0x40)); // local scale bits; generation covers requested font metrics
    return h;
}
struct Row {
    std::uintptr_t table = 0;
    Rect baseline{}, applied{}, saved{};
    int inset = 0;
    double baselineScale = 1;
    bool known = false;
    bool amountKnown = false;
    Rect amountNative{}, amountApplied{}; // relative to the live icon rectangle
    int amountRightInset = 0, amountBottomInset = 0;
};
struct List {
    std::map<void*, Row> rows;
    std::uint64_t signature = 0;
    bool valid = false;
    bool busy = false;
};
std::map<void*, List> lists;
int viewportHeight = 720;
double ViewScale() { return std::max(1.0, viewportHeight / 720.0); }
int Minimum(const Row& row) {
    const double height = row.baseline.height * ViewScale() / row.baselineScale;
    return std::max(1, std::min(32767, static_cast<int>(std::lround(height))));
}
std::uint64_t Signature(void* list, void** rows, int count) {
    std::uint64_t h = Mix(Mix(1469598103934665603ull, KmrpTextLayoutGenerationK1()), viewportHeight);
    const Rect r = F<Rect>(list, 4);
    h = Mix(Mix(Mix(h, r.width), r.height), F<unsigned>(list, 0x2BC) & 0x108);
    h = Mix(h, reinterpret_cast<std::uintptr_t>(rows)); h = Mix(h, count);
    for (int i = 0; i < count; ++i) if (rows[i]) {
        void* p = rows[i]; const Kind kind = Type(p);
        h = Mix(h, reinterpret_cast<std::uintptr_t>(p));
        h = Mix(h, F<std::uintptr_t>(p, 0));
        const Rect extent = F<Rect>(p, 4);
        h = Mix(Mix(h, extent.width), extent.height);
        if (kind.text) h = Mix(h, TextSignature(At(p, kind.text)));
        if (kind.amount) h = Mix(h, TextSignature(At(p, kind.amount)));
    }
    return h;
}
void Flow(void* row) {
    if (row) { const Kind kind = Type(row); if (kind.text) KmrpTextFlowK1(At(row, kind.text)); }
}
void Amounts(void** rows, int count, std::map<void*, Row>& states) {
    for (int i = 0; i < count; ++i) if (rows[i]) {
        void* p = rows[i]; const Kind kind = Type(p);
        auto found = states.find(p);
        if (!kind.amount || found == states.end()) continue;
        Row& state = found->second;
        void* wrapper = At(p, kind.amount);
        const unsigned iconOffset = kind.amount == 0x334 ? 0x1D8 : 0x1C8;
        const Rect icon = F<Rect>(At(p, iconOffset), 4);
        const Rect outer = F<Rect>(p, 4);
        const Rect current = F<Rect>(wrapper, 4);
        if (!Valid(icon) || !Valid(current) || !Valid(outer)) { KmrpTextBoundedK1(wrapper); continue; }
        const Rect relative{current.left - icon.left, current.top - icon.top, current.width, current.height};
        if (!state.amountKnown || !Same(relative, state.amountApplied)) {
            // A native SetExtent placed the counter against the native icon square
            // at the row's top-left; Stretch may already have scaled and centred the
            // live icon, so measure the native insets against the square the game used.
            Rect native = icon;
            const auto scaled = stretched.find(p);
            if (scaled != stretched.end() && scaled->second.icon > 0)
                native = {outer.left, outer.top, scaled->second.icon, scaled->second.icon};
            const Rect nativeRelative{current.left - native.left, current.top - native.top, current.width, current.height};
            state.amountNative = nativeRelative; state.amountKnown = true;
            state.amountRightInset = native.width - nativeRelative.left - nativeRelative.width;
            state.amountBottomInset = native.height - nativeRelative.top - nativeRelative.height;
        }
        // The game put a fixed-size count box flush with the icon square's corner, so a
        // larger count overflowed it and stood past the hex frame. The count is a box
        // the size of its digits at the requested size, its bottom-right corner at
        // (52, 54) of the 56 px lbl_hex_6 art, in proportion to the live icon, at every
        // size and text size: the maintainer's choice, 2026-10-18, after trying it
        // centred in the art's bottom-right notch, at (52, 53), (56, 56) and (52, 52). Capped
        // at half the icon each way; the fit below shrinks a count too long for that.
        // Placed from the live icon each time, so nothing accumulates.
        KmrpTextFlowK1(wrapper); // measure at the requested scale before any cap
        const double naturalWidth = KmrpTextNaturalWidthK1(wrapper);
        const double naturalHeight = KmrpTextNaturalLineHeightK1(wrapper);
        Rect desired = current;
        if (std::isfinite(naturalWidth) && std::isfinite(naturalHeight) &&
            naturalWidth > 0 && naturalWidth <= 32767 && naturalHeight > 0 && naturalHeight <= 32767) {
            desired.width = std::max(1, std::min(icon.width / 2, static_cast<int>(std::ceil(naturalWidth))));
            desired.height = std::max(1, std::min(icon.height / 2, static_cast<int>(std::ceil(naturalHeight))));
            desired.left = icon.left + static_cast<int>(std::lround(icon.width * (52.0 / 56.0))) - desired.width;
            desired.top = icon.top + static_cast<int>(std::lround(icon.height * (54.0 / 56.0))) - desired.height;
            desired.left = std::min(desired.left, outer.left + outer.width - desired.width);
            desired.top = std::min(desired.top, outer.top + outer.height - desired.height);
            if (!Same(current, desired)) Fn<void(__thiscall*)(void*, const Rect*)>(0x416280)(wrapper, &desired);
        }
        state.amountApplied = {desired.left-icon.left, desired.top-icon.top, desired.width, desired.height};
        KmrpTextBoundedK1(wrapper); // cap only overflow beyond the live icon/row
    }
}
}
void KmrpTextRowsK1(void* list) {
    if (!list || F<std::uintptr_t>(list, 0) != 0x73E840) return;
    auto& state = lists[list]; if (state.busy) return;
    void** rows = F<void**>(list, 0x29C);
    const int count = F<int>(list, 0x2A0);
    if (count < 0 || count > 4096 || (count && !rows)) return;
    Flow(F<void*>(list, 0x2CC));
    if (!count) { state.rows.clear(); state.valid = false; return; }
    StretchAll(rows, count);  // before the signature: undo a native layout pass's reset
    const auto signature = Signature(list, rows, count);
    if (state.valid && state.signature == signature) return;
    state.busy = true;
    Rect* saved = F<Rect*>(list, 0x2A8);
    const int savedCount = F<int>(list, 0x2AC);
    const bool fixed = !(F<unsigned>(list, 0x2BC) & 0x100);
    // The fixed native dirty pass restores every saved extent before measuring.
    // Refuse malformed native arrays rather than leaving a partially adapted list.
    if (fixed && (!saved || savedCount != count)) { state.busy = false; return; }
    for (int pass = 0; pass < 3; ++pass) {
        std::map<void*, Row> next;
        bool changed = false;
        for (int i = 0; i < count; ++i) {
            void* p = rows[i]; if (!p) continue;
            const Kind kind = Type(p); if (!kind.text && !kind.chart) continue;
            const Rect current = F<Rect>(p, 4); if (!Valid(current)) continue;
            Row row;
            const auto old = state.rows.find(p);
            if (old != state.rows.end() && old->second.table == F<std::uintptr_t>(p, 0)) row = old->second;
            // A native repopulation/resolution change supplies a new authored extent.
            // Keep the last native baseline otherwise, including when font sizes shrink.
            const bool newGeometry = !row.known || current.width != row.applied.width ||
                (fixed && saved[i].height != row.saved.height);
            if (newGeometry) {
                const int previousBase = row.baseline.height;
                const bool authoredHeight = !row.known || (fixed && saved[i].height != row.saved.height);
                row.table = F<std::uintptr_t>(p, 0);
                row.baseline = fixed ? saved[i] : current;
                // A width-only reflow must not promote our expanded saved height to
                // the new minimum. Native replacement heights are adopted explicitly.
                if (!authoredHeight) row.baseline.height = previousBase;
                else row.baselineScale = ViewScale();
                if (kind.text) {
                    const Rect textRect = F<Rect>(At(p, kind.text), 4);
                    row.inset = std::max(0, current.height - textRect.height);
                }
                row.known = true;
            }
            Flow(p);
            // The text's final width, right of a scaled icon, before measuring it.
            Stretch(p);
            if (kind.chart) {
                Rect desired = current;
                desired.height = ChartHeight(Minimum(row));
                if (fixed) {
                    Rect target = saved[i]; target.height = desired.height;
                    if (!Same(saved[i], target)) { saved[i] = target; changed = true; }
                    row.saved = saved[i];
                }
                if (current.height != desired.height) { Extent(p, desired); changed = true; }
                row.applied = F<Rect>(p, 4); next[p] = row;
                continue;
            }
            // Native layout already supplied the real text width and border insets.
            // NaturalHeight restores requested scale and wraps at that width.
            const int natural = KmrpTextNaturalHeightK1(At(p, kind.text));
            if (natural <= 0 || natural > 32767 - row.inset) { row.applied = current; next[p] = row; continue; }
            Rect desired = current;
            desired.height = natural + row.inset;
            if (!kind.content) desired.height = std::max(Minimum(row), desired.height);
            if (kind.frame) desired.height = std::max(desired.height, IconMinimum(p, Minimum(row)));
            desired.height = std::max(1, std::min(32767, desired.height));
            if (fixed) {
                Rect target = saved[i]; target.height = desired.height;
                if (!Same(saved[i], target)) { saved[i] = target; changed = true; }
                row.saved = saved[i];
            }
            if (current.height != desired.height) { Extent(p, desired); changed = true; }
            row.applied = F<Rect>(p, 4); next[p] = row;
        }
        if (changed || (F<unsigned>(list, 0x2BC) & 8)) {
            const short top = F<short>(list, 0x2C8);
            const short selection = F<short>(list, 0x2C6);
            const short page = F<short>(list, 0x2C2);
            F<unsigned>(list, 0x2BC) |= 8;
            Organize(list);
            // Dirty native layout resets top-visible. Retain the user's position,
            // then let its normal placement/scrollbar path consume the restored index.
            const int visible = std::max(1, static_cast<int>(F<short>(list, 0x2C4)));
            const short restored = static_cast<short>(std::max(0, std::min(static_cast<int>(top), std::max(0, count - (fixed ? visible : 1)))));
            F<short>(list, 0x2C6) = selection >= -1 && selection < count ? selection : -1;
            if (F<short>(list, 0x2C8) != restored) {
                F<short>(list, 0x2C8) = restored;
                if (!fixed) { F<short>(list, 0x2CA) = -1; F<unsigned>(list, 0x2BC) |= 0x80; }
                Organize(list);
            }
            if (fixed) {
                // Oversized content uses a separate one-based line/page index,
                // not top-visible. Native dirty layout recomputes +2B8 from the
                // current viewport/font height. GetPagesToScroll(4182B0) consumes
                // that ratio; clamp just as native drag handling41B739..41B779.
                const int viewport = F<int>(list, 0x298);
                if (viewport > 0 && F<int>(list, 0x2B4) > viewport) {
                    const int pages = Fn<int(__thiscall*)(void*)>(0x4182B0)(list);
                    const short restoredPage = static_cast<short>(std::max(1, std::min(static_cast<int>(page), std::min(32767, std::max(1, pages)))));
                    if (F<short>(list, 0x2C2) != restoredPage) {
                        F<short>(list, 0x2C2) = restoredPage;
                        Fn<void(__thiscall*)(void*)>(0x41A2D0)(list);
                    }
                } else F<short>(list, 0x2C2) = 1;
            }
        }
        for (auto& entry : next) entry.second.applied = F<Rect>(entry.first, 4);
        state.rows.swap(next);
        StretchAll(rows, count);  // the native pass above reset the entry rows' boxes
        bool settled = true;
        for (const auto& entry : state.rows) {
            const Kind kind = Type(entry.first);
            if (kind.chart) {
                const int allocated = fixed ? entry.second.saved.height : F<Rect>(entry.first, 4).height;
                if (ChartHeight(Minimum(entry.second)) != allocated) settled = false;
                continue;
            }
            const int natural = KmrpTextNaturalHeightK1(At(entry.first, kind.text));
            int needed = kind.content ? natural + entry.second.inset : std::max(Minimum(entry.second), natural + entry.second.inset);
            if (kind.frame) needed = std::max(needed, IconMinimum(entry.first, Minimum(entry.second)));
            const int allocated = fixed ? entry.second.saved.height : F<Rect>(entry.first, 4).height;
            if (natural > 0 && needed > 0 && needed <= 32767 && needed != allocated) settled = false;
        }
        if (settled) break;
        if (pass == 2) for (const auto& entry : state.rows) {
            const Kind kind = Type(entry.first); if (kind.text) KmrpTextBoundedK1(At(entry.first, kind.text));
        }
    }
    Amounts(rows, count, state.rows); // after the final native row SetExtent
    StretchAll(rows, count);
    state.signature = Signature(list, rows, count); state.valid = true; state.busy = false;
}
void KmrpTextRowsForgetK1(void* control) {
    lists.erase(control);
    stretched.erase(control);
    charts.erase(control);
    for (auto& list : lists) { if (list.second.rows.erase(control)) list.second.valid = false; }
}

void KmrpTextRowsViewportK1(int height) {
    if (height > 0 && height <= 32767) viewportHeight = height;
}
