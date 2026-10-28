#pragma once

// Where a caption's letters stand in its line, read from the font's own picture, so a
// glyph beside a caption can stand on the letters' middle (the maintainer, 2026-10-28:
// "make it in the code linked to the button text, dont just move it down until it
// fits"). Used by the controller patch's badges (ShowK1BadgeOverlay) and KMRP's own
// pages (K1OptionsPad.h), so the two place a glyph alike.
//
// CAurGUIStringInternal::Draw (0x0045A850) draws each character as one quad, the line's
// whole height (fontheight x 100 x the string's scale at +0x40) from the line's top, with
// the texture coordinates of its upper left and lower right corners (the font
// information's arrays at +0x18 and +0x24, 12 bytes a character, u then v). A letter's
// ink is where its cell of the font's picture is not empty, so its share of the line is
// (v at its top - v of the ink) / (v at its top - v at its bottom). The font is itself
// the texture (AurTextureGetReference returns it): its Bind (virtual +0xB4, 0x004214B0),
// then OpenGL's own read of the bound texture, once a font, on the game's thread.

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace K1CaptionInk {

inline bool Readable(const void* p, std::size_t size) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    if (v < 0x10000u || v >= 0x7FFF0000u) return false;
    MEMORY_BASIC_INFORMATION info{};
    constexpr DWORD ok = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    if (!VirtualQuery(p, &info, sizeof info) || info.State != MEM_COMMIT ||
            !(info.Protect & ok) || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) return false;
    return static_cast<const char*>(p) + size <= static_cast<const char*>(info.BaseAddress) + info.RegionSize;
}

// A font's letters: each character's ink, top and bottom, as shares of the line (top
// above bottom when it has none).
struct Font {
    const void* font = nullptr;
    const void* info = nullptr;
    bool read = false;
    bool failed = false;      // uploaded, and its picture could not be read: not asked again
    float top[256], bottom[256];
};

// The OpenGL name a texture has once the game has uploaded its picture, or 0 while it has
// not: the CAurTextureBasic its reference forwards to (GetTarget, virtual +0x08; AsBasic,
// +0x04), its name at +0x58 (glImage, 0x00420970, sets it). A font or picture is read
// only then, from that name: the engine's Bind (0x004214B0) binds nothing while textures
// are locked or the texture is still the null placeholder, which KMRP's pages met
// ("the texture bound nothing", 2026-10-28).
inline unsigned UploadedName(void* texture) {
    if (!Readable(texture, sizeof(void*))) return 0;
    void** vtable = *reinterpret_cast<void***>(texture);
    if (!Readable(vtable, 0x0C)) return 0;
    void* const target = reinterpret_cast<void*(__thiscall*)(void*)>(vtable[0x08 / 4])(texture);
    if (!Readable(target, sizeof(void*))) return 0;
    vtable = *reinterpret_cast<void***>(target);
    if (!Readable(vtable, 0x08)) return 0;
    void* const basic = reinterpret_cast<void*(__thiscall*)(void*)>(vtable[0x04 / 4])(target);
    if (!Readable(basic, 0x5C)) return 0;
    return *reinterpret_cast<const unsigned*>(static_cast<char*>(basic) + 0x58);
}

// The pixels of the uploaded texture `name` as OpenGL holds them, RGBA, row 0 first
// (v = row / height), read on the game's thread with glGetTexImage; the binding before is
// put back. nullptr when it cannot be read; the caller frees it.
inline unsigned char* ReadUploaded(unsigned name, int* width, int* height) {
    using GetInteger = void(__stdcall*)(unsigned, int*);
    using BindTexture = void(__stdcall*)(unsigned, unsigned);
    using LevelParameter = void(__stdcall*)(unsigned, int, unsigned, int*);
    using GetTexImage = void(__stdcall*)(unsigned, int, unsigned, unsigned, void*);
    using PixelStore = void(__stdcall*)(unsigned, int);
    const HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    if (!gl) return nullptr;
    const auto getInteger = reinterpret_cast<GetInteger>(GetProcAddress(gl, "glGetIntegerv"));
    const auto bindTexture = reinterpret_cast<BindTexture>(GetProcAddress(gl, "glBindTexture"));
    const auto levelParameter = reinterpret_cast<LevelParameter>(GetProcAddress(gl, "glGetTexLevelParameteriv"));
    const auto getTexImage = reinterpret_cast<GetTexImage>(GetProcAddress(gl, "glGetTexImage"));
    const auto pixelStore = reinterpret_cast<PixelStore>(GetProcAddress(gl, "glPixelStorei"));
    if (!getInteger || !bindTexture || !levelParameter || !getTexImage || !pixelStore) return nullptr;
    constexpr unsigned kTexture2D = 0x0DE1, kBinding2D = 0x8069, kWidth = 0x1000, kHeight = 0x1001,
                       kRgba = 0x1908, kUnsignedByte = 0x1401, kPackAlignment = 0x0D05;

    if (name == 0) return nullptr;
    int before = 0, alignment = 4;
    *width = *height = 0;
    getInteger(kBinding2D, &before);
    bindTexture(kTexture2D, name);
    levelParameter(kTexture2D, 0, kWidth, width);
    levelParameter(kTexture2D, 0, kHeight, height);
    unsigned char* pixels = nullptr;
    if (*width > 0 && *height > 0 && *width <= 8192 && *height <= 8192)
        pixels = static_cast<unsigned char*>(std::malloc(static_cast<std::size_t>(*width) * *height * 4));
    if (pixels) {
        getInteger(kPackAlignment, &alignment);
        pixelStore(kPackAlignment, 1);
        getTexImage(kTexture2D, 0, kRgba, kUnsignedByte, pixels);
        pixelStore(kPackAlignment, alignment);
    }
    bindTexture(kTexture2D, static_cast<unsigned>(before));
    return pixels;
}

inline bool ReadFont(Font& f, unsigned name, const char* info) {
    int width = 0, height = 0;
    unsigned char* const pixels = ReadUploaded(name, &width, &height);
    if (!pixels) return false;

    // Ink: covered and lit, so a font drawn in its alpha and one drawn in its colour
    // both read (a quarter of full either way).
    const auto ink = [&](int x, int y) {
        const unsigned char* p = pixels + (static_cast<std::size_t>(y) * width + x) * 4;
        int lit = p[0] > p[1] ? p[0] : p[1];
        if (p[2] > lit) lit = p[2];
        return p[3] >= 64 && lit >= 64;
    };
    const char* const upperLeft = *reinterpret_cast<const char* const*>(info + 0x18);
    const char* const lowerRight = *reinterpret_cast<const char* const*>(info + 0x24);
    const int count = *reinterpret_cast<const int*>(info + 0x18 + 4) < *reinterpret_cast<const int*>(info + 0x24 + 4)
        ? *reinterpret_cast<const int*>(info + 0x18 + 4) : *reinterpret_cast<const int*>(info + 0x24 + 4);
    for (int c = 0; c < 256; ++c) {
        f.top[c] = 1.0f;
        f.bottom[c] = 0.0f;
        if (c >= count) continue;
        const float* ul = reinterpret_cast<const float*>(upperLeft + c * 12);
        const float* lr = reinterpret_cast<const float*>(lowerRight + c * 12);
        const float span = ul[1] - lr[1];
        if (!(span > 1e-6f || span < -1e-6f)) continue;
        int x0 = static_cast<int>(ul[0] * width), x1 = static_cast<int>(lr[0] * width + 0.999f);
        int y0 = static_cast<int>((ul[1] < lr[1] ? ul[1] : lr[1]) * height);
        int y1 = static_cast<int>((ul[1] < lr[1] ? lr[1] : ul[1]) * height + 0.999f);
        if (x0 < 0) x0 = 0;
        if (y0 < 0) y0 = 0;
        if (x1 > width) x1 = width;
        if (y1 > height) y1 = height;
        for (int y = y0; y < y1; ++y) {
            bool any = false;
            for (int x = x0; x < x1 && !any; ++x) any = ink(x, y);
            if (!any) continue;
            // This row's share of the line, from the top: its upper and lower edge.
            const float a = (ul[1] - static_cast<float>(y) / height) / span;
            const float b = (ul[1] - static_cast<float>(y + 1) / height) / span;
            const float from = a < b ? a : b, to = a < b ? b : a;
            if (from < f.top[c]) f.top[c] = from;
            if (to > f.bottom[c]) f.bottom[c] = to;
        }
    }
    std::free(pixels);
    return true;
}

// A font's letters, read once and kept (by its information alone: each text holds its
// own reference to the font, which forwards to the one texture, CAurTexture +0x10);
// nullptr when its picture cannot be read. `font` and `info` are known readable.
// The fonts read, by their information (each text holds its own reference to the font,
// which forwards to the one texture); KMRP fills it as each font is uploaded
// (FontUploaded), a module without that hook as a font is first asked for.
inline Font* Fonts() { static Font fonts[16]; return fonts; }
inline Font& FontSlot(const char* info) {
    static int next = 0;
    Font* const fonts = Fonts();
    for (int i = 0; i < 16; ++i)
        if (fonts[i].info == info) return fonts[i];
    Font& f = fonts[next];
    next = (next + 1) % 16;
    f.info = info;
    f.read = f.failed = false;
    return f;
}

// A font whose picture is uploaded as OpenGL texture `name`: its letters read now. KMRP
// calls it as the game uploads each picture (KmrpTextureUploadedK1, K1TextLayout.cpp),
// so a font is read once, when it is loaded, and again when it is loaded anew.
inline const Font* FontUploaded(void* font, unsigned name, const char* info) {
    Font& f = FontSlot(info);
    f.font = font;
    f.read = ReadFont(f, name, info);
    f.failed = !f.read;
    return f.read ? &f : nullptr;
}

// A font's letters, read once, or nullptr while its picture is not uploaded (it is read
// when it is: FontUploaded in KMRP, or the next time it is asked for).
inline const Font* FontFor(void* font, const char* info) {
    Font* const fonts = Fonts();
    for (int i = 0; i < 16; ++i)
        if (fonts[i].info == info && (fonts[i].read || fonts[i].failed)) return fonts[i].read ? &fonts[i] : nullptr;
    if (!GetModuleHandleW(L"opengl32.dll")) return nullptr;     // nothing to read with (a test's mock)
    const unsigned name = UploadedName(font);
    if (!name) return nullptr;
    return FontUploaded(font, name, info);
}

// The middle of the letters of `chars` (a terminated text) as a share of the line: the
// average of each inked character's own middle, so each letter counts as much as it
// shows; false when none of its characters has ink. Until 2026-10-28 the middle of all
// their inked rows together, which the few full capitals set: in the menu font they run
// from 29% to 88% of the line and the small capitals, most of a caption, from 40% to 87%,
// so a caption centred so looked about 2 px low at 3440x1440 though the art and the
// letters agreed (the maintainer, of the bottom row's captions on every tab; "Average of
// the letters" chosen that day).
// Letters and digits only, where the caption has any: a full stop or comma sits on the
// line's foot and a bracket spans it, and they would pull the average.
inline bool Middle(const Font& f, const char* chars, double* middle) {
    for (int pass = 0; pass < 2; ++pass) {
        const bool lettersOnly = pass == 0;
        double sum = 0.0;
        int count = 0;
        for (int i = 0; i < 4096 && chars[i]; ++i) {
            const unsigned char c = static_cast<unsigned char>(chars[i]);
            if (c <= ' ' || f.top[c] > f.bottom[c]) continue;
            const bool letter = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c >= 0xC0;
            if (lettersOnly && !letter) continue;
            sum += (f.top[c] + f.bottom[c]) / 2.0;
            ++count;
        }
        if (count) { *middle = sum / count; return true; }
    }
    return false;
}

// The middle of the letters of `string` (a CAurGUIStringInternal) as a share of its line,
// and that line's height in pixels; false when the font cannot be read.
inline bool Letters(void* string, double* middle, int* line) {
    if (!Readable(string, 0x44)) return false;
    void* const font = *reinterpret_cast<void**>(static_cast<char*>(string) + 0x18);
    if (!Readable(font, sizeof(void*))) return false;
    void** const vtable = *reinterpret_cast<void***>(font);
    if (!Readable(vtable, 0xB8)) return false;
    const char* const info = reinterpret_cast<const char*(__thiscall*)(void*)>(vtable[0x38 / 4])(font);
    if (!Readable(info, 0x30)) return false;
    const char* const upperLeft = *reinterpret_cast<const char* const*>(info + 0x18);
    const char* const lowerRight = *reinterpret_cast<const char* const*>(info + 0x24);
    if (!Readable(upperLeft, 12) || !Readable(lowerRight, 12)) return false;
    const int count = *reinterpret_cast<const int*>(info + 0x1C);
    if (count <= 0 || count > 256 || *reinterpret_cast<const int*>(info + 0x28) < count ||
            !Readable(upperLeft, count * 12u) || !Readable(lowerRight, count * 12u)) return false;
    const char* const chars = *reinterpret_cast<const char* const*>(static_cast<char*>(string) + 0x14);
    if (!Readable(chars, 1)) return false;
    const Font* const f = FontFor(font, info);
    if (!f) return false;

    int length = 0;
    while (length < 4096 && Readable(chars + length, 1) && chars[length]) ++length;
    if (length >= 4096 || !Readable(chars + length, 1) || !Middle(*f, chars, middle)) return false;
    float scale = *reinterpret_cast<const float*>(static_cast<char*>(string) + 0x40);
    if (!(scale > 0.01f && scale < 100.0f)) scale = 1.0f;
    const int height = static_cast<int>(*reinterpret_cast<const float*>(info + 0x04) * scale * 100.0f + 0.5f);
    if (height <= 0) return false;
    *line = height;
    return true;
}

// How wide a one-line caption is drawn, in pixels, as Draw (0x0045A850) sums it: for each
// character (lower right u - upper left u) x texturewidth + spacingR, times the string's
// scale and 100; 0 when it cannot be told or the caption has more than one line. The
// controller patch's MeasureK1CaptionByFont makes the same sum (K1XboxControls.cpp).
inline int CaptionWidth(void* string) {
    if (!Readable(string, 0x44)) return 0;
    if (*reinterpret_cast<const int*>(static_cast<char*>(string) + 0x38) > 1) return 0;
    void* const font = *reinterpret_cast<void**>(static_cast<char*>(string) + 0x18);
    if (!Readable(font, sizeof(void*))) return 0;
    void** const vtable = *reinterpret_cast<void***>(font);
    if (!Readable(vtable, 0x3C)) return 0;
    const char* const info = reinterpret_cast<const char*(__thiscall*)(void*)>(vtable[0x38 / 4])(font);
    if (!Readable(info, 0x28)) return 0;
    const char* const upperLeft = *reinterpret_cast<const char* const*>(info + 0x18);
    const char* const lowerRight = *reinterpret_cast<const char* const*>(info + 0x24);
    if (!Readable(upperLeft, 256 * 12) || !Readable(lowerRight, 256 * 12)) return 0;
    const char* const chars = *reinterpret_cast<const char* const*>(static_cast<char*>(string) + 0x14);
    if (!Readable(chars, 1)) return 0;
    float scale = *reinterpret_cast<const float*>(static_cast<char*>(string) + 0x40);
    if (!(scale > 0.01f && scale < 100.0f)) scale = 1.0f;
    const float texels = *reinterpret_cast<const float*>(info + 0x0C);
    const float spacing = *reinterpret_cast<const float*>(info + 0x10);
    float width = 0.0f;
    for (int i = 0; i < 256 && Readable(chars + i, 1) && chars[i] != '\0'; ++i) {
        if (chars[i] == '\n') return 0;
        const int glyph = static_cast<unsigned char>(chars[i]) * 12;
        width += (*reinterpret_cast<const float*>(lowerRight + glyph) -
                  *reinterpret_cast<const float*>(upperLeft + glyph)) * texels + spacing;
    }
    return width > 0.0f ? static_cast<int>(width * scale * 100.0f + 0.5f) : 0;
}

// How far KMRP's draw moves a vertically centred text up so its letters' middle is its
// box's middle (KmrpTextStringDrawK1, K1TextLayout.cpp), in pixels, for letters whose
// middle is `middle` of a line `line` tall: the controller patch places a glyph on the
// letters where they are then drawn.
inline int Shift(double middle, double line) {
    const double s = (middle - 0.5) * line;
    return static_cast<int>(s < 0 ? s - 0.5 : s + 0.5);
}

}  // namespace K1CaptionInk
