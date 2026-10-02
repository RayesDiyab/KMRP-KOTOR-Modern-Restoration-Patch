// KMRP for macOS: the status summary laid out at the font's size (status_summary.cpp), and the
// text measuring it needs, which the controller's dialogue A shares.
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

struct Result { void* panel; int rows, lineHeight, widest; int box[4], ok[4]; };

// Finds the status summary in the GUI manager's panel or modal list and lays it out; true and
// out filled when there was one with rows to lay out.
bool Update(void* manager, Result* out);

}  // namespace summary
}  // namespace kmrp
