#pragma once
// The pad on KMRP's own option pages (K1TextOptions.cpp, K1HudOptions.cpp) and their
// entry buttons on Graphics Options. Those are built at run time, so they are in none
// of the controller patch's tables of the game's screens; they ask it by name
// (vendor/K1XboxControls.cpp, exported by kmrp-controller.dll): whether the pad is the
// device in use, its glyph family, to keep a control off the pad's focus, and to paint
// the A an entry button shows while focused. Without the controller patch every answer
// is "no pad" and nothing here draws or skips anything.
//
// The pages' buttons that the pad presses by itself (B Close, Y Default, X the HUD
// page's other tab) show its glyph beside their caption while the pad is in use, as
// the Controller Layout screen's footer does (K1ControllerLayout.cpp): a label of the
// page wearing kmr<family>rm<code>, the controller patch's glyph art (the maintainer,
// 2026-10-19: "I want the close button to have the B glyph", "I should never be able to
// focus on these two buttons").
#include <windows.h>
#include <cstdint>
#include <cstring>

namespace KmrpOptionsPad {

struct Api {
    int (__cdecl* padInUse)() = nullptr;
    char (__cdecl* family)() = nullptr;
    void (__cdecl* skip)(void*, int) = nullptr;
    void (__cdecl* entryBadge)(void*, int) = nullptr;
};
inline const Api& Controller() {
    static Api api;
    static bool asked = false;
    if (!asked) {
        HMODULE module = GetModuleHandleW(L"kmrp-controller.dll");
        if (!module) return api;    // asked again later: the patch may load after this one
        asked = true;
        api.padInUse = reinterpret_cast<int(__cdecl*)()>(GetProcAddress(module, "KmrpPadInUseK1"));
        api.family = reinterpret_cast<char(__cdecl*)()>(GetProcAddress(module, "KmrpGlyphLetterK1"));
        api.skip = reinterpret_cast<void(__cdecl*)(void*, int)>(GetProcAddress(module, "KmrpPadFocusSkipK1"));
        api.entryBadge = reinterpret_cast<void(__cdecl*)(void*, int)>(GetProcAddress(module, "KmrpPaintGraphicsEntryPromptK1"));
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

// The engine's routines a glyph uses, found through the page's own lookup (the text
// page's harness answers them with mocks).
using Resolve = void* (*)(std::uintptr_t);
constexpr std::uintptr_t kSetFillImage = 0x00414C00;   // CSWGuiBorderParams::SetFillImage(name, 1)
constexpr std::uintptr_t kMeasureText = 0x00414F10;    // CSWGuiText::GetIdealWidthAndHeight(CSWGuiExtent*)
constexpr unsigned kLabelParams = 0x70, kParamsFlags = 0x1C;
constexpr unsigned kButtonText = 0x154;                 // a button's CSWGuiText
constexpr unsigned kFlags = 0x44, kVisible = 2;

struct Box { int left, top, width, height; };
template<class T> T& At(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p) + n); }

struct Glyph {
    void* label = nullptr;    // the page's label that shows it
    void* button = nullptr;   // the button whose caption it stands beside
    char code = 0;            // 'a', 'b', 'x' or 'y'
    char family = 0;          // the art it wears now
    Box placedFor{};          // the button's rectangle it was placed for
    int caption = -1;         // the caption's width it was placed for
    int shown = -1;
};

// Beside the caption's left, as tall as its line and three eighths more (the HUD's
// pause notice: a 22 pixel picture beside a 16 pixel font, K1XboxHud.cpp), a quarter of
// its size apart; kept inside the button. Only what changed is written.
inline void Update(Glyph& g, bool pad, char family, Resolve resolve) {
    if (!g.label || !g.button) return;
    const bool show = pad && (At<unsigned>(g.button, kFlags) & kVisible) != 0;
    if (show) {
        Box measured{};
        reinterpret_cast<void(__thiscall*)(void*, Box*)>(resolve(kMeasureText))(static_cast<char*>(g.button) + kButtonText, &measured);
        const Box button = At<Box>(g.button, 4);
        if (std::memcmp(&button, &g.placedFor, sizeof button) || measured.width != g.caption) {
            const int line = measured.height > 0 ? measured.height : button.height / 2;
            int size = line + line * 3 / 8;
            if (size > button.height - 2) size = button.height - 2;
            if (size < 1) size = 1;
            int left = button.left + (button.width - measured.width) / 2 - size - size / 4;
            if (left < button.left + 2) left = button.left + 2;
            const Box at{left, button.top + (button.height - size) / 2, size, size};
            reinterpret_cast<void(__thiscall*)(void*, const Box*)>((*reinterpret_cast<void***>(g.label))[1])(g.label, &at);
            g.placedFor = button; g.caption = measured.width;
        }
        if (family != g.family) {
            char resref[16] = {'k', 'm', 'r', family, 'r', 'm', g.code};
            reinterpret_cast<void(__thiscall*)(void*, const char*, int)>(resolve(kSetFillImage))(
                static_cast<char*>(g.label) + kLabelParams, resref, 1);
            unsigned& fill = At<unsigned>(g.label, kLabelParams + kParamsFlags);
            fill = (fill & ~3u) | 2u;      // stretched over the label
            g.family = family;
        }
    }
    if (int(show) != g.shown) {
        unsigned& flags = At<unsigned>(g.label, kFlags);
        flags = show ? (flags | kVisible) : (flags & ~kVisible);
        g.shown = show;
    }
}

}  // namespace KmrpOptionsPad
