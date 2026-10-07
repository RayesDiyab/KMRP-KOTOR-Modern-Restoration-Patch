/*
  Text measured from a font, and the status summary found: what KMRP's module (the status
  summary's layout, status_summary.cpp) and the controller patch's (its badges beside captions,
  kmrp-controller) both need. Compiled into both: each is a module of its own since 2026-10-07.
*/
#include "text.h"

#include <mach/mach.h>
#include <mach/mach_vm.h>

namespace kmrp {
namespace {

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

const std::size_t kCtlExtent = 0x08;
const std::size_t kVtSetExtent = 0x10;
using SetExtentFn = void (*)(void* control, const int* rect);
std::uintptr_t VtableOf(void* object) { return text::LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

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

// CSWGuiStatusSummary is 0x1005AE9A0; the manager's panels are [+0xD8], +0xE0 of them, and its
// modal panels [+0xE8], +0xF0.
void* Find(void* manager) {
    if (!text::LooksLikePointer(manager)) return nullptr;
    static const std::size_t kLists[2][2] = {{0xd8, 0xe0}, {0xe8, 0xf0}};
    for (const auto& list : kLists) {
        void** const panels = At<void**>(manager, list[0]);
        const int count = At<int>(manager, list[1]);
        if (count <= 0 || count > 256 || !text::LooksLikePointer(panels)) continue;
        for (int i = 0; i < count; ++i)
            if (VtableOf(panels[i]) == kStatusSummaryVtable) return panels[i];
    }
    return nullptr;
}

}  // namespace summary
}  // namespace kmrp
