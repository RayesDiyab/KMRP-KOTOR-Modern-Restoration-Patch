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

#include "K1CaptionInk.h"

namespace KmrpOptionsPad {

struct Api {
    int (__cdecl* padInUse)() = nullptr;
    char (__cdecl* family)() = nullptr;
    void (__cdecl* skip)(void*, int) = nullptr;
    void (__cdecl* entryBadge)(void*, int) = nullptr;
    // Since 2026-10-28: a picture of the patch's set on a border as its drawing for the
    // border's size, and a batch of them listed once (KmrpSetPictureK1, KmrpPictureBatchK1).
    void (__cdecl* setPicture)(void*, const char*) = nullptr;
    void (__cdecl* batch)(int) = nullptr;
    // Since 2026-10-28: a Graphics Options badge's glyph, its box and drawing for a label
    // placed as that screen's (KmrpBadgeGlyphK1).
    int (__cdecl* badgeGlyph)(const char*, char, int*, char*) = nullptr;
    // And a picture queued for drawing in the background at a size (KmrpQueuePictureK1).
    void (__cdecl* queuePicture)(const char*, int, int) = nullptr;
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
        api.setPicture = reinterpret_cast<void(__cdecl*)(void*, const char*)>(GetProcAddress(module, "KmrpSetPictureK1"));
        api.batch = reinterpret_cast<void(__cdecl*)(int)>(GetProcAddress(module, "KmrpPictureBatchK1"));
        api.badgeGlyph = reinterpret_cast<int(__cdecl*)(const char*, char, int*, char*)>(GetProcAddress(module, "KmrpBadgeGlyphK1"));
        api.queuePicture = reinterpret_cast<void(__cdecl*)(const char*, int, int)>(GetProcAddress(module, "KmrpQueuePictureK1"));
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

// A picture on a border (its parameters, `params`): the controller patch's drawing of it for
// the border's size where the patch is there and has it, so the page shows no missing texture
// for a frame (the HUD pages flashed as they opened, 2026-10-28); the engine's own by name
// otherwise. Set the border's size first. Several at once go between Batch(true) and
// Batch(false), which the patch lists in one go.
inline void SetPicture(void* params, const char* name, Resolve resolve) {
    const Api& a = Controller();
    if (a.setPicture) { a.setPicture(params, name); return; }
    char resref[16] = {};
    for (int i = 0; i < 16 && name[i]; ++i) resref[i] = name[i];
    reinterpret_cast<void(__thiscall*)(void*, const char*, int)>(resolve(kSetFillImage))(params, resref, 1);
}
inline void Batch(bool begin) { const Api& a = Controller(); if (a.batch) a.batch(begin ? 1 : 0); }
// The picture `name` drawn in the background for a border `width` by `height`, ahead of
// its use, where the controller patch is there to draw it.
inline void QueuePicture(const char* name, int width, int height) {
    const Api& a = Controller();
    if (a.queuePicture && name && name[0]) a.queuePicture(name, width, height);
}
constexpr std::uintptr_t kMeasureText = 0x00414F10;    // CSWGuiText::GetIdealWidthAndHeight(CSWGuiExtent*)
constexpr unsigned kLabelParams = 0x70, kParamsFlags = 0x1C;
constexpr unsigned kButtonText = 0x154;                 // a button's CSWGuiText
constexpr unsigned kFlags = 0x44, kVisible = 2;
// A button's border parameters (+0x80): the frame's DIMENSION at +0x00, its corner art at
// +0x54; the fill is inset by DIMENSION only where there is corner art (the controller
// patch's K1ButtonFillInset).
constexpr unsigned kButtonBorder = 0x80, kBorderCorner = 0x54;
// The glyph's share of the height a settings screen's badge is drawn in: 93,750 hundred-
// thousandths of the area the button's border fills (Graphics Options' Default and Close,
// kmrpy_optgfxdef and kmrpb_optgfx in K1ControllerBadgeShapes.inc); and of the square a
// glyph label's picture fills (SQUARE_GLYPH_FILL, build_controller_prompt_textures.py).
constexpr double kBadgeGlyphShare = 0.9375, kSquareGlyphFill = 0.86;

struct Box { int left, top, width, height; };

// The settings screens' badges as the build placed them (K1ControllerBadgeShapes.inc, the
// controller patch's own table, the same row type): a page button that is a copy of one of
// Graphics Options' (Default, Close) wears its glyph in that badge's box, so the two screens
// show it on the same pixels (the maintainer, 2026-10-28: "the buttons are like a pixel or
// two off make it the same").
struct BadgeShape {
    const char* resref; short width, height, glyph, glyphWidth;
    const char* glyphName; int boxLeft, boxTop, boxWidth, boxHeight;
};
#include "K1ControllerBadgeShapes.inc"
inline const BadgeShape* Badge(const char* resref) {
    if (!resref) return nullptr;
    for (const BadgeShape& shape : kBadgeShapes)
        if (!std::strcmp(shape.resref, resref)) return &shape;
    return nullptr;
}
template<class T> T& At(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p) + n); }

// The middle of a button's caption letters on screen, top to bottom, or -1 when its font
// cannot be read: the letters' place in the line from the font's picture
// (K1CaptionInk.h), the lines where Draw puts them in the text's rectangle by the
// string's alignment (+0x46: 0x10 the middle, 0x20 the bottom, anything else the top).
// The controller patch places its badges by the same (ShowK1BadgeOverlay).
inline int LettersMiddle(void* button) {
    char* const text = static_cast<char*>(button) + kButtonText;
    void* const string = At<void*>(text, 0x14);
    double share = 0.0;
    int line = 0;
    if (!K1CaptionInk::Letters(string, &share, &line)) return -1;
    // Where the string itself is drawn from: its own top and height (+0x08, +0x10),
    // which KMRP's draw moves to put a centred caption's letters on its art
    // (CentreLetters, K1TextLayout.cpp).
    const Box block{0, At<int>(string, 0x08), 0, At<int>(string, 0x10)};
    const unsigned vertical = At<unsigned char>(string, 0x46) & 0x38u;
    const int lines = At<int>(string, 0x38) > 1 ? At<int>(string, 0x38) : 1;
    const int all = lines * line;
    int top = block.top;
    if (vertical == 0x10u) top = block.top + (block.height - all) / 2;
    else if (vertical == 0x20u) top = block.top + block.height - all;
    return static_cast<int>(top + (lines - 1) * line / 2.0 + share * line + 0.5);
}

struct Glyph {
    void* label = nullptr;    // the page's label that shows it
    void* button = nullptr;   // the button whose caption it stands beside
    char code = 0;            // 'a', 'b', 'x' or 'y'
    const char* badge = nullptr;   // the settings badge whose box it takes (Badge), or none
    char family = 0;          // the art it wears now
    Box placedFor{};          // the button's rectangle it was placed for
    int caption = -1;         // the caption's width it was placed for
    int drawnTop = 0;         // and the top its string is drawn from (LettersMiddle)
    Box badgeAt{};            // where its settings badge's label goes (Badge), for the glyph in it
    int shown = -1;
};

// Beside the caption's left, a quarter of its size apart, kept inside the button; its glyph
// as tall as a settings screen's badge on a button of this size, so the page's Y, X and B
// match Graphics Options' own (67 px at 3440x1440). Until 2026-10-28 the label was the
// caption's line and three eighths more, after the HUD's pause notice: 44 px there, its
// glyph 38 (the maintainer: "the glyphs there are too small"). Only what changed is written.
inline void Update(Glyph& g, bool pad, char family, Resolve resolve) {
    if (!g.label || !g.button) return;
    const bool show = pad && (At<unsigned>(g.button, kFlags) & kVisible) != 0;
    if (show) {
        Box measured{};
        reinterpret_cast<void(__thiscall*)(void*, Box*)>(resolve(kMeasureText))(static_cast<char*>(g.button) + kButtonText, &measured);
        const Box button = At<Box>(g.button, 4);
        void* const string = At<void*>(static_cast<char*>(g.button) + kButtonText, 0x14);
        const int drawnTop = string ? At<int>(string, 0x08) : 0;
        if (std::memcmp(&button, &g.placedFor, sizeof button) || measured.width != g.caption || drawnTop != g.drawnTop) {
            g.drawnTop = drawnTop;
            const char* border = static_cast<const char*>(g.button) + kButtonBorder;
            const int inset = *reinterpret_cast<void* const*>(border + kBorderCorner) ? *reinterpret_cast<const int*>(border) : 0;
            const int area = button.height - 2 * inset;
            int size = static_cast<int>(area * kBadgeGlyphShare / kSquareGlyphFill + 0.5);
            if (size > button.height - 2) size = button.height - 2;
            if (size < 1) size = 1;
            int left = button.left + (button.width - measured.width) / 2 - size - size / 4;
            if (left < button.left + 2) left = button.left + 2;
            const int letters = LettersMiddle(g.button);
            Box at{left, letters >= 0 ? letters - size / 2 : button.top + (button.height - size) / 2, size, size};
            if (const BadgeShape* shape = Badge(g.badge)) {
                // Placed as the controller patch places Graphics Options' own badge on its
                // label, step for step (ShowK1BadgeOverlay, K1UniformBadge), and showing
                // the same picture drawn at that size, so the two screens' Y and B are the
                // same pixels (the maintainer, 2026-10-28: "can Text size and font copy the
                // buttons layout for Graphics options Default and close buttons?"). Until
                // that day a square glyph picture placed by a rule of its own, 5 px off by
                // hand; its caption's width was the engine's ideal width, which it finds in
                // steps of ten, where the controller sums the font's letters (CaptionWidth).
                const int width = button.width - 2 * inset, height = button.height - 2 * inset;
                int w = width, h = height;
                if (static_cast<long long>(width) * shape->height >= static_cast<long long>(shape->width) * height) {
                    h = height;
                    w = static_cast<int>((static_cast<long long>(height) * shape->width + shape->height / 2) / shape->height);
                } else {
                    w = width;
                    h = static_cast<int>((static_cast<long long>(width) * shape->height + shape->width / 2) / shape->width);
                }
                const int least = (height * 3 + 2) / 4;
                if (h < least) {
                    h = least;
                    w = static_cast<int>((static_cast<long long>(least) * shape->width + shape->height / 2) / shape->height);
                }
                const Box text = At<Box>(static_cast<char*>(g.button) + kButtonText, 4);
                const int middle = text.width > 0 ? text.left + text.width / 2 : button.left + button.width / 2;
                const int fromFont = string ? K1CaptionInk::CaptionWidth(string) : 0;
                const int caption = fromFont > 0 ? fromFont : measured.width;
                const int gap = h / 4, air = h / 8;
                const int glyphLeft = static_cast<int>(static_cast<long long>(w) * (shape->glyph - shape->glyphWidth / 2) / 1000);
                const int glyphRight = static_cast<int>(static_cast<long long>(w) * (shape->glyph + shape->glyphWidth / 2) / 1000);
                int x = shape->glyph < 500 ? middle - caption / 2 - gap - glyphRight
                                           : middle + (caption + 1) / 2 + gap - glyphLeft;
                const int first = button.left + inset, last = first + width;
                if (x + glyphRight > last - air) x = last - air - glyphRight;
                if (x + glyphLeft < first + air) x = first + air - glyphLeft;
                at = {x, letters >= 0 ? letters - h / 2 : button.top + button.height / 2 - h / 2, w, h};
                g.badgeAt = at;
            }
            reinterpret_cast<void(__thiscall*)(void*, const Box*)>((*reinterpret_cast<void***>(g.label))[1])(g.label, &at);
            g.placedFor = button; g.caption = measured.width;
            g.family = 0;             // its picture drawn again for the size it now has
        }
        if (family != g.family) {
            char resref[16] = {'k', 'm', 'r', family, 'r', 'm', g.code};
            int glyph[4] = {g.badgeAt.left, g.badgeAt.top, g.badgeAt.width, g.badgeAt.height};
            char drawn[17] = {};
            const Api& api = Controller();
            if (Badge(g.badge) && api.badgeGlyph && api.badgeGlyph(g.badge, family, glyph, drawn)) {
                // The controller's own drawing of the badge's glyph, on its box in the
                // label, as on Graphics Options (KmrpBadgeGlyphK1).
                const Box box{glyph[0], glyph[1], glyph[2], glyph[3]};
                reinterpret_cast<void(__thiscall*)(void*, const Box*)>((*reinterpret_cast<void***>(g.label))[1])(g.label, &box);
                reinterpret_cast<void(__thiscall*)(void*, const char*, int)>(resolve(kSetFillImage))(
                    static_cast<char*>(g.label) + kLabelParams, drawn, 1);
            } else {
                if (const BadgeShape* shape = Badge(g.badge)) {
                    // The whole badge on its label, in this family's letters (the fourth).
                    std::strncpy(resref, shape->resref, 15);
                    resref[3] = family;
                }
                SetPicture(static_cast<char*>(g.label) + kLabelParams, resref, resolve);
            }
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
