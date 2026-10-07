// KMRP for macOS: text measured from a font, and the status summary found (text.cpp). Shared by
// KMRP's module and the controller patch's, each of which compiles it.
#pragma once

#include <cstddef>
#include <cstdint>

namespace kmrp {
namespace text {

// A label's CSWGuiText is at +0x110; its text object at +0x18 of that keeps the string at
// +0x18, the font at +0x20, each line's length at [+0x48] and the line count at +0x50, and its
// scale at +0x58 (read from the object's draw, 0x1001BCB04).
const std::size_t kLabelText = 0x110, kTextObject = 0x18;
const std::size_t kObjString = 0x18, kObjFont = 0x20, kObjLineLengths = 0x48, kObjLineCount = 0x50, kObjScale = 0x58;

// The font's vtable+0x78 is its CAurFontInfo (CAurFontInfo::ParseField, 0x1001F850E): fontheight
// +0x04, texturewidth +0x0C, spacingR +0x10, the upper-left and lower-right coordinates at
// [+0x18] and [+0x28], 12 bytes a glyph. The Windows offsets are 0xD0, 0x14, 0x14, 0x18, 0x34,
// 0x38, 0x40, vtable+0x38, and the same font fields but for the coordinates, at +0x18 and +0x24.
const std::size_t kVtFontInfo = 0x78;
const std::size_t kInfoHeight = 0x04, kInfoTextureWidth = 0x0c, kInfoSpacingR = 0x10;
const std::size_t kInfoUpperLeft = 0x18, kInfoLowerRight = 0x28;
using FontInfoFn = char* (*)(void* font);

bool LooksLikePointer(const void* p);
bool Readable(const void* p, std::size_t size);

struct Font { const char* upperLeft; const char* lowerRight; float texels, spacing; int lineHeight; };
bool FontOf(void* object, Font& out);
float GlyphWidth(const Font& f, unsigned char c);

// A label's whole text on one line, in pixels, and its font's line height.
int LabelTextWidth(void* label, int& lineHeight);

// Sets a control's extent through its vtable, only when it differs.
void SetExtentIfChanged(void* control, const int* rect);

}  // namespace text

namespace summary {

// The status summary's panel and where its OK button is in it.
const std::uintptr_t kStatusSummaryVtable = 0x1005ae9a0UL;
const std::size_t kSummaryOk = 0x2078;

// The status summary in the GUI manager's panel or modal list, or null.
void* Find(void* manager);

}  // namespace summary
}  // namespace kmrp
