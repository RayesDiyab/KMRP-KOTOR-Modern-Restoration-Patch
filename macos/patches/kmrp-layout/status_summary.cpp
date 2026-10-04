/*
  The status summary laid out at the font's size, with or without controller support
  ----------------------------------------------------------------------------------------------
  Status-summary rows use the native text object's wrapping result, not a glyph-width estimate.
  Native centred drawing can discard a leading line when a fractional font height exceeds an
  integer box by even one float ULP. Each row therefore gets ceil(native line height * lines).
  Width is searched up to the viewport cap; unavoidable multiline text gets a taller row.
  The GUI Update entry callback runs before the native manager update, not after it.

  Until 2026-10-02 this was the controller module's (layout.cpp), so an install without
  controller support kept the game's own layout, as a tester's screenshot showed. Windows calls
  it without the controller from a core stand-in hook (StatusSummaryFrameK1); here the
  controller's GUI frame calls Update and adds the pad's A beside OK, and without the controller
  KmrpCoreGuiFrame, on the same CSWGuiManager::Update entry (without-controller/), calls it alone.

  CSWGuiStatusSummary is 0x1005AE9A0 on the Mac: its nine icons from +0x3C8 and their lines from
  +0x1220, 0x198 apart in the same order, OK at +0x2078. The manager's panels are [+0xD8], +0xE0
  of them, and its modal panels [+0xE8], +0xF0; its viewport is +0xA4 and +0xA6.
*/
#include "status_summary.h"

#include <cmath>
#include <mach/mach.h>
#include <mach/mach_vm.h>

namespace kmrp {
namespace {

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

const std::size_t kLabelSize = 0x198;
const std::size_t kPanelControls = 0x30, kPanelControlCount = 0x38;
const std::size_t kCtlExtent = 0x08, kCtlId = 0x74, kCtlFlags = 0x68;
const std::uint8_t kCtlVisible = 0x02;
const std::size_t kVtSetExtent = 0x10;
using SetExtentFn = void (*)(void* control, const int* rect);

// The font's vtable+0x78 is its CAurFontInfo (CAurFontInfo::ParseField, 0x1001F850E): fontheight
// +0x04, texturewidth +0x0C, spacingR +0x10, the upper-left and lower-right coordinates at
// [+0x18] and [+0x28], 12 bytes a glyph. The Windows offsets are 0xD0, 0x14, 0x14, 0x18, 0x34,
// 0x38, 0x40, vtable+0x38, and the same font fields but for the coordinates, at +0x18 and +0x24.
const std::size_t kVtFontInfo = 0x78;
const std::size_t kInfoHeight = 0x04, kInfoTextureWidth = 0x0c, kInfoSpacingR = 0x10;
const std::size_t kInfoUpperLeft = 0x18, kInfoLowerRight = 0x28;
using FontInfoFn = char* (*)(void* font);

const std::uintptr_t kStatusSummaryVtable = 0x1005ae9a0UL;
const std::size_t kSummaryIcons = 0x3c8, kSummaryLines = 0x1220, kSummaryOk = 0x2078;
const int kSummaryRows = 9;
const std::size_t kMgrViewportWidth = 0xa4, kMgrViewportHeight = 0xa6;

std::uintptr_t VtableOf(void* object) { return text::LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

bool BoundTo(void* panel, void* control) {
    const int id = At<int>(control, kCtlId), count = At<int>(panel, kPanelControlCount);
    void** const array = At<void**>(panel, kPanelControls);
    return id >= 0 && id < count && text::LooksLikePointer(array) && array[id] == control;
}

using WrapFn = void (*)(void*, int);

struct FitCache {
    void* label;
    void* object;
    void* font;
    std::uint64_t hash;
    float height, scale;
    int cap, width, appliedWidth, lines;
};
FitCache g_fit[kSummaryRows] = {};

// Native wrapping is monotonic in width. Find the narrowest width retaining the
// line count achievable at the screen cap (explicit newlines may require multiple lines).
int FittingWidth(void* label, int cap, FitCache& cache, float& height) {
    void* object = At<void*>(static_cast<char*>(label) + text::kLabelText, text::kTextObject);
    if (!text::Readable(object, 0x60) || cap < 1) return 0;
    text::Font font{};
    if (!text::FontOf(object, font)) return 0;
    const float scale = At<float>(object, text::kObjScale);
    const auto fontObject = At<void*>(object, text::kObjFont);
    char* info = reinterpret_cast<FontInfoFn>(*reinterpret_cast<std::uintptr_t*>(
        At<std::uintptr_t>(fontObject, 0) + kVtFontInfo))(fontObject);
    height = At<float>(info, kInfoHeight) * scale * 100.0f;
    if (!std::isfinite(height) || height <= 0 || height > 4096) return 0;
    const char* string = At<const char*>(object, text::kObjString);
    std::uint64_t hash = 1469598103934665603ULL;
    bool ended = false;
    for (int i = 0; i < 4096; ++i) {
        if (!text::Readable(string + i, 1)) return 0;
        const unsigned char c = string[i];
        hash = (hash ^ c) * 1099511628211ULL;
        if (!c) { ended = true; break; }
    }
    if (!ended) return 0;
    if (cache.label == label && cache.object == object && cache.font == fontObject &&
        cache.hash == hash && cache.height == height && cache.scale == scale && cache.cap == cap &&
        cache.lines == At<int>(object, text::kObjLineCount)) return cache.width;
    const auto wrap = reinterpret_cast<WrapFn>(*reinterpret_cast<std::uintptr_t*>(VtableOf(object) + 0xa0));
    const int savedWidth = At<int>(object, 0x10);
    wrap(object, cap);
    const int target = At<int>(object, text::kObjLineCount);
    if (target <= 0 || target > 4096) { wrap(object, savedWidth); return 0; }
    int low = 1, high = cap;
    while (low < high) {
        const int mid = low + (high - low) / 2;
        wrap(object, mid);
        const int lines = At<int>(object, text::kObjLineCount);
        // Zero lines means the native short-string guard rejected this width.
        if (lines > 0 && lines <= target) high = mid;
        else low = mid + 1;
    }
    wrap(object, savedWidth);
    cache = {label, object, fontObject, hash, height, scale, cap, low, 0, 0};
    return low;
}

bool Layout(void* manager, void* panel, summary::Result* out) {
    char* const base = static_cast<char*>(panel);
    const int screenW = At<std::int16_t>(manager, kMgrViewportWidth), screenH = At<std::int16_t>(manager, kMgrViewportHeight);
    if (screenW <= 0 || screenH <= 0) return false;
    int rows[kSummaryRows] = {};
    float heights[kSummaryRows] = {};
    int count = 0, widest = 0, lineHeight = 0;
    for (int i = 0; i < kSummaryRows; ++i) {
        void* const icon = base + kSummaryIcons + i * kLabelSize;
        void* const line = base + kSummaryLines + i * kLabelSize;
        if (!(At<std::uint8_t>(icon, kCtlFlags) & kCtlVisible) || !BoundTo(panel, icon) || !BoundTo(panel, line)) continue;
        int ignored = 0;
        text::LabelTextWidth(line, ignored);
        if (ignored > lineHeight) lineHeight = ignored;
        rows[count++] = i;
    }
    if (!count || lineHeight <= 0) return false;
    auto at16 = [lineHeight](int v) { return (v * lineHeight + 8) / 16; };
    const int lineX = at16(52);
    const int cap = screenW - lineX - at16(10);
    if (cap <= 0) return false;
    for (int n = 0; n < count; ++n) {
        const int i = rows[n];
        const int width = FittingWidth(base + kSummaryLines + i * kLabelSize, cap, g_fit[i], heights[i]);
        if (width <= 0) return false;
        if (width > widest) widest = width;
    }
    const int lineW = widest;
    int boxW = lineX + lineW + at16(10);
    // Room for OK, the pad's A left of it and as much again on the right, so OK stays centred.
    const int okW = at16(100), okH = at16(22);
    const int roomy = okW + 2 * (okH + okH / 4 + at16(4));
    if (boxW < roomy) boxW = roomy < screenW ? roomy : screenW;
    int y = at16(10);
    for (int n = 0; n < count; ++n) {
        void* const icon = base + kSummaryIcons + rows[n] * kLabelSize;
        void* const line = base + kSummaryLines + rows[n] * kLabelSize;
        FitCache& fit = g_fit[rows[n]];
        void* const object = fit.object;
        if (fit.appliedWidth != lineW || At<int>(object, 0x10) != lineW ||
            fit.lines != At<int>(object, text::kObjLineCount)) {
            reinterpret_cast<WrapFn>(*reinterpret_cast<std::uintptr_t*>(VtableOf(object) + 0xa0))(object, lineW);
        }
        const int lines = At<int>(object, text::kObjLineCount);
        if (lines <= 0 || lines > 4096) return false;
        const int textHeight = static_cast<int>(std::ceil(heights[rows[n]] * static_cast<float>(lines)));
        const int rowHeight = textHeight > at16(32) ? textHeight : at16(32);
        const int iconRect[4] = {at16(10), y, at16(32), at16(32)};
        const int lineRect[4] = {lineX, y - at16(1), lineW, rowHeight};
        text::SetExtentIfChanged(icon, iconRect);
        text::SetExtentIfChanged(line, lineRect);
        fit.appliedWidth = lineW;
        fit.lines = At<int>(object, text::kObjLineCount);
        y += rowHeight + at16(5);
    }
    const int okY = y;
    const int boxH = okY + at16(32);
    const int okRect[4] = {(boxW - okW) / 2, okY, okW, okH};
    const int boxRect[4] = {(screenW - boxW) / 2, (screenH - boxH) / 2, boxW, boxH};
    text::SetExtentIfChanged(base + kSummaryOk, okRect);
    text::SetExtentIfChanged(panel, boxRect);
    if (out) {
        *out = {panel, count, lineHeight, widest, {}, {}};
        for (int i = 0; i < 4; ++i) { out->box[i] = boxRect[i]; out->ok[i] = okRect[i]; }
    }
    return true;
}

}  // namespace

namespace text {

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

bool Readable(const void* p, std::size_t size) {
    if (!LooksLikePointer(p) || size == 0) return false;
    unsigned char probe;
    mach_vm_size_t got = 0;
    const auto at = reinterpret_cast<mach_vm_address_t>(p);
    return mach_vm_read_overwrite(mach_task_self(), at, 1, reinterpret_cast<mach_vm_address_t>(&probe), &got) ==
               KERN_SUCCESS &&
           mach_vm_read_overwrite(mach_task_self(), at + size - 1, 1, reinterpret_cast<mach_vm_address_t>(&probe),
                                  &got) == KERN_SUCCESS;
}

bool FontOf(void* object, Font& out) {
    void* const font = At<void*>(object, kObjFont);
    if (!Readable(font, 8)) return false;
    const std::uintptr_t vtable = At<std::uintptr_t>(font, 0);
    if (!Readable(reinterpret_cast<void*>(vtable), kVtFontInfo + 8)) return false;
    char* const info = reinterpret_cast<FontInfoFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtFontInfo))(font);
    if (!Readable(info, 0x30)) return false;
    out.upperLeft = At<const char*>(info, kInfoUpperLeft);
    out.lowerRight = At<const char*>(info, kInfoLowerRight);
    if (!Readable(out.upperLeft, 256 * 12) || !Readable(out.lowerRight, 256 * 12)) return false;
    out.texels = At<float>(info, kInfoTextureWidth) * 100.0f;
    out.spacing = At<float>(info, kInfoSpacingR) * 100.0f;
    out.lineHeight = static_cast<int>(At<float>(info, kInfoHeight) * 100.0f + 0.5f);
    return true;
}

float GlyphWidth(const Font& f, unsigned char c) {
    const int glyph = c * 12;
    return (*reinterpret_cast<const float*>(f.lowerRight + glyph) - *reinterpret_cast<const float*>(f.upperLeft + glyph)) *
           f.texels;
}

// A label's whole text on one line, in pixels, plus the font's spacingR after each glyph but
// the last (labelTextWidth), and that font's line height.
int LabelTextWidth(void* label, int& lineHeight) {
    char* const text = static_cast<char*>(label) + kLabelText;
    char* const object = At<char*>(text, kTextObject);
    if (!Readable(object, 0x60)) return 0;
    const char* const string = At<const char*>(object, kObjString);
    if (!Readable(string, 1)) return 0;
    Font font{};
    if (!FontOf(object, font)) return 0;
    float width = 0.0f;
    int glyphs = 0;
    for (int i = 0; i < 256; ++i) {
        if (!Readable(string + i, 1) || string[i] == '\0') break;
        if (string[i] == '\n') continue;
        width += GlyphWidth(font, static_cast<unsigned char>(string[i]));
        ++glyphs;
    }
    if (glyphs > 1 && font.spacing > 0.0f && font.spacing < 8.0f) width += font.spacing * (glyphs - 1);
    lineHeight = font.lineHeight;
    return static_cast<int>(width + 0.5f);
}

void SetExtentIfChanged(void* control, const int* rect) {
    const int* now = reinterpret_cast<const int*>(static_cast<char*>(control) + kCtlExtent);
    if (now[0] != rect[0] || now[1] != rect[1] || now[2] != rect[2] || now[3] != rect[3])
        reinterpret_cast<SetExtentFn>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtSetExtent))(control, rect);
}


}  // namespace text

namespace summary {

bool Update(void* manager, Result* out) {
    if (!text::LooksLikePointer(manager)) return false;
    static const std::size_t kLists[2][2] = {{0xd8, 0xe0}, {0xe8, 0xf0}};
    for (const auto& list : kLists) {
        void** const panels = At<void**>(manager, list[0]);
        const int count = At<int>(manager, list[1]);
        if (count <= 0 || count > 256 || !text::LooksLikePointer(panels)) continue;
        for (int i = 0; i < count; ++i) {
            if (VtableOf(panels[i]) == kStatusSummaryVtable) return Layout(manager, panels[i], out);
        }
    }
    return false;
}

}  // namespace summary
}  // namespace kmrp

// CSWGuiManager::Update, entry (0x10049f636; Windows 0x0040CE70, StatusSummaryFrameK1): the GUI's
// own frame, hooked here only in the build without controller support, whose own hook on the
// same entry (gui.cpp, KmrpGuiFrame) calls summary::Update itself.
namespace kmrp { extern void (*g_frameHook)(void* manager); }
extern "C" __attribute__((visibility("default"))) void KmrpCoreGuiFrame(void* manager) {
    if (kmrp::g_frameHook) kmrp::g_frameHook(manager);
    kmrp::summary::Update(manager, nullptr);
}
