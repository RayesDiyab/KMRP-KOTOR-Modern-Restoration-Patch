#pragma once
// The font a string (a CAurGUIStringInternal) is drawn in, as Draw (0x0045A850) reads it: the
// font at +0x18, its information by the font's virtual at +0x38, the scale at +0x40. A
// character is (lower right u - upper left u) x texturewidth + spacingR wide, times the scale
// and 100 (0x0045ABDF). Six places read all this by hand (audit S-8). K1CaptionInk::Letters
// and K1TextLayout's Font ask more of the font and read it themselves.
#include "K1EngineMemory.h"

struct KmrpFontK1 {
    void* font = nullptr;
    const char* info = nullptr;         // the font information
    const char* upperLeft = nullptr;    // +0x18 and +0x24: a coordinate pair per glyph, 12 bytes
    const char* lowerRight = nullptr;
    float height = 0.0f;                // fontheight, +0x04
    float texels = 0.0f;                // texturewidth, +0x0C
    float spacing = 0.0f;               // spacingR, +0x10
    float scale = 1.0f;                 // the string's, 1 where it is not a sane number

    // Lower right u less upper left u: the rest of a character's width is the caller's sum.
    float Span(char c) const {
        const int glyph = static_cast<unsigned char>(c) * 12;
        return *reinterpret_cast<const float*>(lowerRight + glyph) -
               *reinterpret_cast<const float*>(upperLeft + glyph);
    }
};

inline bool KmrpFontOfStringK1(void* string, KmrpFontK1& out) {
    if (!IsReadableK1(string, 0x44)) return false;
    const char* const object = static_cast<const char*>(string);
    out.font = *reinterpret_cast<void* const*>(object + 0x18);
    if (!IsReadableK1(out.font, sizeof(void*))) return false;
    void** const vtable = *static_cast<void***>(out.font);
    if (!IsReadableK1(vtable, 0x3C)) return false;
    out.info = reinterpret_cast<const char*(__thiscall*)(void*)>(vtable[0x38 / 4])(out.font);
    if (!IsReadableK1(out.info, 0x28)) return false;
    out.upperLeft = *reinterpret_cast<const char* const*>(out.info + 0x18);
    out.lowerRight = *reinterpret_cast<const char* const*>(out.info + 0x24);
    if (!IsReadableK1(out.upperLeft, 256 * 12) || !IsReadableK1(out.lowerRight, 256 * 12)) return false;
    out.height = *reinterpret_cast<const float*>(out.info + 0x04);
    out.texels = *reinterpret_cast<const float*>(out.info + 0x0C);
    out.spacing = *reinterpret_cast<const float*>(out.info + 0x10);
    out.scale = *reinterpret_cast<const float*>(object + 0x40);
    if (!(out.scale > 0.01f && out.scale < 100.0f)) out.scale = 1.0f;
    return true;
}
