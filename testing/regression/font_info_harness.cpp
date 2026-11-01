// K1FontInfo.h and the two widths built on it, on a made-up font whose numbers are worked out by
// hand below. Test-FontInfo.py builds this for x86: the font's virtual is __thiscall.
#include "K1CaptionInk.h"
#include "K1GuiControls.h"

#include <cmath>
#include <cstdio>

namespace {

float g_upperLeft[256 * 3], g_lowerRight[256 * 3];
struct Info {
    char pad0[4];
    float height;           // +0x04
    char pad1[4];
    float texels;           // +0x0C
    float spacing;          // +0x10
    char pad2[4];
    const float* upperLeft;  // +0x18
    char pad3[8];
    const float* lowerRight;  // +0x24
} g_info;
static_assert(offsetof(Info, height) == 0x04 && offsetof(Info, texels) == 0x0C && offsetof(Info, spacing) == 0x10 &&
              offsetof(Info, upperLeft) == 0x18 && offsetof(Info, lowerRight) == 0x24, "the font information's layout");

const Info* g_answer = &g_info;
// __fastcall stands in for __thiscall, which only a member may name: `this` is in ecx for both.
const Info* __fastcall InfoOf(void*, void*) { return g_answer; }

void* g_table[16];
void* g_font[1] = { g_table };

struct StringObject {
    char pad0[0x14];
    const char* chars;      // +0x14
    void* font;             // +0x18
    char pad1[0x38 - 0x1C];
    int lines;              // +0x38
    char pad2[4];
    float scale;            // +0x40
} g_string;
static_assert(offsetof(StringObject, chars) == 0x14 && offsetof(StringObject, font) == 0x18 &&
              offsetof(StringObject, lines) == 0x38 && offsetof(StringObject, scale) == 0x40, "the string's layout");

int g_failed = 0;
void Check(bool ok, const char* what)
{
    std::printf("%s %s\n", ok ? "ok  " : "FAIL", what);
    if (!ok) g_failed = 1;
}
bool Near(float a, float b) { return std::fabs(a - b) < 0.0001f; }

void SetGlyph(char c, float left, float right)
{
    const int at = static_cast<unsigned char>(c) * 3;
    g_upperLeft[at] = left;
    g_lowerRight[at] = right;
}

}  // namespace

int main()
{
    g_table[0x38 / 4] = reinterpret_cast<void*>(&InfoOf);
    g_info = {};
    g_info.height = 0.16f;
    g_info.texels = 0.5f;
    g_info.spacing = 0.01f;
    g_info.upperLeft = g_upperLeft;
    g_info.lowerRight = g_lowerRight;
    SetGlyph('A', 0.1f, 0.3f);
    SetGlyph('B', 0.3f, 0.7f);
    g_string.chars = "AB";
    g_string.font = g_font;
    g_string.lines = 1;
    g_string.scale = 1.5f;

    KmrpFontK1 font;
    Check(KmrpFontOfStringK1(&g_string, font), "a string's font is read");
    Check(font.font == g_font && font.info == reinterpret_cast<const char*>(&g_info), "the font and its information");
    Check(Near(font.height, 0.16f) && Near(font.texels, 0.5f) && Near(font.spacing, 0.01f), "fontheight, texturewidth, spacingR");
    Check(Near(font.scale, 1.5f), "the string's scale");
    Check(Near(font.Span('A'), 0.2f) && Near(font.Span('B'), 0.4f), "a character's span");

    // (0.2 x 0.5 + 0.01) + (0.4 x 0.5 + 0.01) = 0.32, times 1.5 and 100.
    Check(K1CaptionInk::CaptionWidth(&g_string) == 48, "a caption's width, as Draw sums it");

    // The control's text at +0xD0, its string object at +0x14 of that. Its sum leaves the
    // scale out: (0.2 + 0.4) x 50, and one spacing of 1 between the two glyphs.
    char control[0xD0 + 0x18] = {};
    *reinterpret_cast<void**>(control + 0xD0 + 0x14) = &g_string;
    int lineHeight = 0;
    Check(KmrpGui::labelTextWidth(control, lineHeight) == 31, "a label's width");
    Check(lineHeight == 16, "a label's line height");

    g_string.scale = 0.0f;
    Check(KmrpFontOfStringK1(&g_string, font) && font.scale == 1.0f, "a scale of 0 reads as 1");
    g_string.scale = 500.0f;
    Check(KmrpFontOfStringK1(&g_string, font) && font.scale == 1.0f, "a scale of 500 reads as 1");
    g_string.scale = 1.0f;

    g_string.lines = 2;
    Check(K1CaptionInk::CaptionWidth(&g_string) == 0, "a caption of two lines has no one width");
    g_string.lines = 1;

    Check(!KmrpFontOfStringK1(nullptr, font), "no string");
    g_string.font = nullptr;
    Check(!KmrpFontOfStringK1(&g_string, font), "no font");
    g_string.font = g_font;
    g_answer = nullptr;
    Check(!KmrpFontOfStringK1(&g_string, font), "no font information");
    g_answer = &g_info;
    g_info.lowerRight = nullptr;
    Check(!KmrpFontOfStringK1(&g_string, font), "no glyphs");
    return g_failed;
}
