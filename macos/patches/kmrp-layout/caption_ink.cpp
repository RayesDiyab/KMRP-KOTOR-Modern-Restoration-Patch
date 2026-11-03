// KMRP for macOS: the letters of each font, read from its picture as the game uploads it
// (caption_ink.h says why this is not Windows' header).
#define GL_SILENCE_DEPRECATION
#include "caption_ink.h"

#include "text.h"
#include "text_fit.h"

#include <OpenGL/gl.h>
#include <cstdlib>
#include <cstring>

namespace kmrp {
namespace ink {
namespace {

const std::size_t kInfoCoordinateCountLeft = 0x20, kInfoCoordinateCountRight = 0x30;

// The fonts read, by their information: a text holds its own reference to the font, which forwards
// to the one texture. Made on first use (kmrp_layout.cpp's rule on globals).
Font* Fonts() {
    static Font* fonts = new Font[24];
    return fonts;
}
Font& Slot(const char* info) {
    static int next = 0;
    Font* const fonts = Fonts();
    for (int i = 0; i < 24; ++i)
        if (fonts[i].info == info) return fonts[i];
    Font& f = fonts[next];
    next = (next + 1) % 24;
    f.info = info;
    f.read = f.failed = false;
    return f;
}

bool ReadFont(Font& f, unsigned name, const char* info) {
    int width = 0, height = 0;
    unsigned char* const pixels = ReadUploaded(name, &width, &height);
    if (!pixels) return false;
    // Ink: covered and lit, so a font drawn in its alpha and one drawn in its colour both read (a
    // quarter of full either way).
    const auto ink = [&](int x, int y) {
        const unsigned char* p = pixels + (static_cast<std::size_t>(y) * width + x) * 4;
        int lit = p[0] > p[1] ? p[0] : p[1];
        if (p[2] > lit) lit = p[2];
        return p[3] >= 64 && lit >= 64;
    };
    const char* const upperLeft = *reinterpret_cast<const char* const*>(info + text::kInfoUpperLeft);
    const char* const lowerRight = *reinterpret_cast<const char* const*>(info + text::kInfoLowerRight);
    const int left = *reinterpret_cast<const int*>(info + kInfoCoordinateCountLeft);
    const int right = *reinterpret_cast<const int*>(info + kInfoCoordinateCountRight);
    const int count = left < right ? left : right;
    for (int c = 0; c < 256; ++c) {
        f.top[c] = 1.0f;
        f.bottom[c] = 0.0f;
        if (c >= count || !upperLeft || !lowerRight) continue;
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

}  // namespace

unsigned char* ReadUploaded(unsigned name, int* width, int* height) {
    if (!name) return nullptr;
    GLint before = 0, alignment = 4;
    *width = *height = 0;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &before);
    glBindTexture(GL_TEXTURE_2D, name);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, height);
    unsigned char* pixels = nullptr;
    if (*width > 0 && *height > 0 && *width <= 8192 && *height <= 8192)
        pixels = static_cast<unsigned char*>(std::malloc(static_cast<std::size_t>(*width) * *height * 4));
    if (pixels) {
        glGetIntegerv(GL_PACK_ALIGNMENT, &alignment);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
        glPixelStorei(GL_PACK_ALIGNMENT, alignment);
    }
    glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(before));
    return pixels;
}

void FontUploaded(const char* info, unsigned name) {
    Font& f = Slot(info);
    f.read = ReadFont(f, name, info);
    f.failed = !f.read;
}

const Font* FontFor(const void* info) {
    Font* const fonts = Fonts();
    for (int i = 0; i < 24; ++i)
        if (fonts[i].info == info && fonts[i].read) return &fonts[i];
    return nullptr;
}

bool Middle(const Font& f, const char* chars, double* middle) {
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

int Shift(double middle, double line) {
    const double s = (middle - 0.5) * line;
    return static_cast<int>(s < 0 ? s - 0.5 : s + 0.5);
}

}  // namespace ink
}  // namespace kmrp

// CAurTextureBasic's build (0x1001f907c, Windows 0x004216A0), just after its upload (0x1001f703e,
// Windows' glImage): rbx the texture. A font's letters are read here, once each time it is loaded.
extern "C" __attribute__((visibility("default"))) void KmrpTextureUploaded(void* texture) {
    if (!texture) return;
    char* const object = static_cast<char*>(texture);
    const unsigned name = *reinterpret_cast<const unsigned*>(object + 0x7C);
    if (!name) return;
    const char* const info = *reinterpret_cast<const char* const*>(object + 0x48);
    if (info && *reinterpret_cast<const int*>(info + 0x20) > 0 && *reinterpret_cast<const char* const*>(info + 0x18))
        kmrp::ink::FontUploaded(info, name);
    char picture[33] = {};
    std::memcpy(picture, object + 0x9C, 32);    // its own name (Windows +0x78)
    kmrp::textfit::PictureUploaded(picture, name);
}
