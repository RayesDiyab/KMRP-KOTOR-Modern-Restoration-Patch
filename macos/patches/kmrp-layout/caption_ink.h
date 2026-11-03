// KMRP for macOS: where a caption's letters stand in its line, read from the font's own picture
// (handoff item 104). The Mac's copy of Windows' src/controller-native/K1CaptionInk.h, which cannot
// be shared: it is written against windows.h and the 32-bit font layout. Its rules are Windows'.
//
// The string's draw (0x1001bcb04, Windows 0x0045A850) draws each character as one quad, the line's
// whole height (fontheight x 100 x the string's scale) from the line's top, with the texture
// coordinates of its upper left and lower right corners (the font information's arrays at +0x18 and
// +0x28, 12 bytes a character, u then v, their counts at +0x20 and +0x30; Windows +0x18, +0x24). A
// letter's ink is where its cell of the font's picture is not empty, so its share of the line is
// (v at its top - v of the ink) / (v at its top - v at its bottom).
//
// Fonts are read where the game uploads them, once each time a font is loaded: a hook just after
// the upload (0x1001f90d9 in the texture build, Windows 0x004216F1), from the OpenGL name at
// +0x7C of the CAurTextureBasic (Windows +0x58), its font information at +0x48 (Windows +0x38).
// Never through the engine's Bind, which binds nothing while textures are locked.
#pragma once

#include <cstddef>
#include <cstdint>

namespace kmrp {
namespace ink {

// A font's letters: each character's ink, top and bottom, as shares of the line (top above bottom
// when it has none).
struct Font {
    const void* info = nullptr;
    bool read = false;
    bool failed = false;      // uploaded, and its picture could not be read: not asked again
    float top[256], bottom[256];
};

// The pixels of an uploaded texture as OpenGL holds them, RGBA, row 0 first (v = row / height), on
// the game's thread; the binding before is put back. Null when it cannot be read; freed by the caller.
unsigned char* ReadUploaded(unsigned name, int* width, int* height);

// A font's picture has just been uploaded as `name`: its letters read now.
void FontUploaded(const char* info, unsigned name);
// A font's letters, or null until its picture has been uploaded.
const Font* FontFor(const void* info);

// The middle of the letters of `chars` as a share of the line: the average of each inked
// character's own middle, letters and digits only where the caption has any; false when none of
// its characters has ink.
bool Middle(const Font& f, const char* chars, double* middle);
// How far a vertically centred text is moved up so its letters' middle is its box's middle, in
// pixels, for letters whose middle is `middle` of a line `line` tall.
int Shift(double middle, double line);

}  // namespace ink
}  // namespace kmrp
