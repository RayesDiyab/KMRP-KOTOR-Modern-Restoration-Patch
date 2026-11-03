// KMRP for macOS: the pad on KMRP's own option pages and their entry buttons on Graphics Options.
// The port of Windows' src/controller-native/K1OptionsPad.h. Those pages are built at run time,
// so they are in none of the controller patch's tables of the game's screens; they ask it by name
// (kmrp-controller/pages.cpp): whether the pad is the device in use, its glyph family, to keep a
// control off the pad's focus, to paint the A an entry button shows while focused, and whether
// confirm is held. Without the controller patch every answer is "no pad" and nothing here draws or
// skips anything.
//
// Windows' GetModuleHandle has no Mac counterpart in dlsym(RTLD_DEFAULT): a patch's module is
// loaded local, so its names are found through its own handle (audit MAC-5). The module stands
// beside this one, patches/kmrp-controller.dylib under the patch's id, and RTLD_NOLOAD asks
// for it only if it is loaded, as the controller patch asks for patches/kmrp.dylib
// (standalone.cpp). Every patch's module is loaded before the game runs, so the first asking,
// from a GUI frame, is the answer for the run.
//
// A page's buttons that the pad presses by itself (B Close, Y Default, X the HUD page's other tab)
// show its glyph beside their caption while the pad is in use: a label of the page wearing
// kmr<family>rm<code>, the controller patch's glyph art. Windows puts Default and Close on the
// pixels of Graphics Options' own Y and B with pictures the controller draws at run time
// (KmrpBadgeGlyphK1); the Mac's controller patch carries its pictures made
// (macos/README.md), so the glyph stands beside the caption as Windows' other glyphs do.
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <string>

namespace kmrp {
namespace pad {

struct Box { int left, top, width, height; };

struct Api {
    int (*padInUse)() = nullptr;
    char (*family)() = nullptr;
    void (*skip)(void*, int) = nullptr;
    void (*entryBadge)(void*, int) = nullptr;
    int (*confirmHeld)() = nullptr;
};

// The module beside this one by its file name, if it is loaded, or null. `anchor` is any function
// of the asker's.
inline void* ModuleBeside(const void* anchor, const char* name) {
    Dl_info self;
    if (!dladdr(anchor, &self) || !self.dli_fname) return nullptr;
    std::string path(self.dli_fname);
    const std::size_t slash = path.rfind('/');
    if (slash == std::string::npos) return nullptr;
    path = path.substr(0, slash + 1) + name;
    return dlopen(path.c_str(), RTLD_NOLOAD | RTLD_LAZY);
}

inline const Api& Controller() {
    static Api api;
    static bool asked = false;
    if (!asked) {
        asked = true;
        if (void* module = ModuleBeside(reinterpret_cast<const void*>(&ModuleBeside), "kmrp-controller.dylib")) {
            api.padInUse = reinterpret_cast<int (*)()>(dlsym(module, "KmrpPadInUseK1"));
            api.family = reinterpret_cast<char (*)()>(dlsym(module, "KmrpGlyphLetterK1"));
            api.skip = reinterpret_cast<void (*)(void*, int)>(dlsym(module, "KmrpPadFocusSkipK1"));
            api.entryBadge = reinterpret_cast<void (*)(void*, int)>(dlsym(module, "KmrpPaintGraphicsEntryPromptK1"));
            api.confirmHeld = reinterpret_cast<int (*)()>(dlsym(module, "KmrpControllerConfirmHeldK1"));
        }
    }
    return api;
}
inline bool PadInUse() { const Api& a = Controller(); return a.padInUse && a.padInUse() != 0; }
inline char Family() { const Api& a = Controller(); return a.family ? a.family() : 'p'; }
inline void SkipFocus(void* control, bool skipped) {
    const Api& a = Controller();
    if (a.skip && control) a.skip(control, skipped ? 1 : 0);
}
inline void EntryBadge(void* button, bool shown) {
    const Api& a = Controller();
    if (a.entryBadge && button) a.entryBadge(button, shown ? 1 : 0);
}
inline bool ConfirmHeld() { const Api& a = Controller(); return a.confirmHeld && a.confirmHeld() != 0; }

template <typename T> T& Field(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

// The engine, on the Mac (Windows' in K1OptionsPad.h):
//   label: its border's parameters +0xA0 (+0x70), the fill style in the low two bits at +0x1C of
//   them; button: its CSWGuiText +0x1B8 (+0x154), its border's parameters +0xC0 (+0x80), of which
//   +0x00 is the frame's DIMENSION and +0x58 the corner art (+0x54); +0x68 a control's flags, bit
//   1 visible; vtable +0x10 SetExtent.
const std::size_t kLabelParams = 0xA0, kParamsFlags = 0x1C;
const std::size_t kButtonText = 0x1B8, kButtonBorder = 0xC0, kBorderCorner = 0x58;
const std::size_t kExtent = 0x08, kFlags = 0x68;
const std::uint8_t kVisible = 2;
const std::size_t kVtSetExtent = 0x10;
// The glyph's share of the height a settings screen's badge is drawn in, and of the square a
// glyph label's picture fills (K1OptionsPad.h, kBadgeGlyphShare and kSquareGlyphFill).
const double kBadgeGlyphShare = 0.9375, kSquareGlyphFill = 0.86;

// CSWGuiText::GetIdealWidthAndHeight (0x1004A3E48; Windows 0x00414F10), which returns the rect in
// rax and rdx; CSWGuiBorderParams::SetFillImage (0x1004A17C2; Windows 0x00414C00).
inline Box MeasureText(void* text) { return reinterpret_cast<Box (*)(void*)>(0x1004a3e48UL)(text); }
inline void SetFill(void* params, const char* name) {
    char resref[16] = {};
    std::strncpy(resref, name, sizeof resref);
    reinterpret_cast<void (*)(void*, const void*, int)>(0x1004a17c2UL)(params, resref, 1);
}
inline void SetExtent(void* control, const Box& box) {
    reinterpret_cast<void (*)(void*, const Box*)>(*reinterpret_cast<std::uintptr_t*>(
        Field<std::uintptr_t>(control, 0) + kVtSetExtent))(control, &box);
}

// The middle of a button's caption letters on screen, top to bottom, or -1 when its font cannot be
// read (K1OptionsPad.h, LettersMiddle): where the letters stand in the line from the font's picture
// (kmrp-layout/text_fit.cpp), the lines where Draw puts them by the string's alignment.
extern "C" int KmrpCaptionLetters(void* string, double* middle, int* line);
inline int LettersMiddle(void* button) {
    char* const text = static_cast<char*>(button) + kButtonText;
    void* const string = Field<void*>(text, 0x18);
    double share = 0.0;
    int line = 0;
    if (!string || !KmrpCaptionLetters(string, &share, &line)) return -1;
    const unsigned vertical = Field<std::uint8_t>(string, 0x5e) & 0x38u;
    const int lines = Field<int>(string, 0x50) > 1 ? Field<int>(string, 0x50) : 1;
    const int all = lines * line, height = Field<int>(string, 0x14);
    int top = Field<int>(string, 0x0c);
    if (vertical == 0x10u) top += (height - all) / 2;
    else if (vertical == 0x20u) top += height - all;
    return static_cast<int>(top + (lines - 1) * line / 2.0 + share * line + 0.5);
}

struct Glyph {
    void* label = nullptr;    // the page's label that shows it
    void* button = nullptr;   // the button whose caption it stands beside
    char code = 0;            // 'a', 'b', 'x' or 'y'
    char family = 0;          // the art it wears now
    Box placedFor{};          // the button's rectangle it was placed for
    int caption = -1;         // the caption's width it was placed for
    int drawnTop = 0;         // and the top its string is drawn from (LettersMiddle)
    int shown = -1;
};

// Beside the caption's left, a quarter of its size apart, kept inside the button; as tall as a
// settings screen's badge on a button of this size. Only what changed is written.
inline void Update(Glyph& g, bool pad, char family) {
    if (!g.label || !g.button) return;
    const bool show = pad && (Field<std::uint8_t>(g.button, kFlags) & kVisible) != 0;
    if (show) {
        const Box measured = MeasureText(static_cast<char*>(g.button) + kButtonText);
        const Box button = Field<Box>(g.button, kExtent);
        void* const string = Field<void*>(static_cast<char*>(g.button) + kButtonText, 0x18);
        const int drawnTop = string ? Field<int>(string, 0x0c) : 0;
        if (std::memcmp(&button, &g.placedFor, sizeof button) || measured.width != g.caption || drawnTop != g.drawnTop) {
            g.drawnTop = drawnTop;
            char* const border = static_cast<char*>(g.button) + kButtonBorder;
            const int inset = Field<void*>(border, kBorderCorner) ? Field<int>(border, 0) : 0;
            const int area = button.height - 2 * inset;
            int size = static_cast<int>(area * kBadgeGlyphShare / kSquareGlyphFill + 0.5);
            if (size > button.height - 2) size = button.height - 2;
            if (size < 1) size = 1;
            int left = button.left + (button.width - measured.width) / 2 - size - size / 4;
            if (left < button.left + 2) left = button.left + 2;
            const int letters = LettersMiddle(g.button);
            SetExtent(g.label, Box{left, letters >= 0 ? letters - size / 2 : button.top + (button.height - size) / 2, size, size});
            g.placedFor = button;
            g.caption = measured.width;
        }
        if (family != g.family) {
            char resref[16] = {};
            std::snprintf(resref, sizeof resref, "kmr%crm%c", family, g.code);
            SetFill(static_cast<char*>(g.label) + kLabelParams, resref);
            std::uint8_t& fill = Field<std::uint8_t>(g.label, kLabelParams + kParamsFlags);
            fill = static_cast<std::uint8_t>((fill & ~3u) | 2u);   // stretched over the label
            g.family = family;
        }
    }
    if (int(show) != g.shown) {
        std::uint8_t& flags = Field<std::uint8_t>(g.label, kFlags);
        flags = show ? (flags | kVisible) : (flags & ~kVisible);
        g.shown = show;
    }
}

}  // namespace pad
}  // namespace kmrp
