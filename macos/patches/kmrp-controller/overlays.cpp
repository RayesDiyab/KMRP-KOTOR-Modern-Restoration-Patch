/*
  KMRP for macOS, the controller patch: a badge that keeps its shape on any interface.

  A badge is a texture on its button's fill, which the engine stretches over the area the
  button's border leaves (prompts.cpp, FillInset), so it is round only on a button of the shape
  it was made for. This patch's badges are made for the game's own layouts. Beside KMRP, beside
  the Widescreen Patch's own layout or beside any later interface patch the buttons have other
  shapes, and the caption is somewhere else in them. The maintainer's rule (2026-10-06, on
  Windows): the controller patch fits itself to whatever interface is loaded, from what it
  measures in the running game, and takes nothing from another patch; a badge's width and
  height never change apart. This is the port of Windows' ShowK1BadgeOverlay and its companions
  (src/controller-native/vendor/K1XboxControls.cpp).

  The shape each badge was made for is K1ControllerBadgeShapes.inc, the file Windows compiles
  (tools/build_controller_assets.py --badge-shapes): the Mac game's layouts and this patch's
  textures give the same 133 rows, which macos/build.sh checks. Every badge is drawn on a label
  of this patch's own and its button carries none (since 2026-10-08, Windows' master 843320b;
  until then only a button of another shape than the made one, by more than a fiftieth, had a
  label, and the others kept the texture as their fill):

    - in the made-for proportions and as large as fits the button's fill area both ways
      (UniformBadge), so the glyph is as round as it was drawn and a row taller than its
      fellows has no larger badge;
    - placed so the glyph stands a quarter of the badge's height from the caption as the
      caption is drawn now, measured from the caption's own font, on the side it has in its
      texture, and kept inside the button;
    - in the middle of its button, top to bottom. A caption that is not on the button's middle
      line is brought there, in a rectangle one line tall, for as long as the badge is shown;
    - in the unchanged game, where the area is exactly the made one, laid over the area the
      fill covered, the caption left where the screen has it.

  The label is a CSWGuiLabel made here (constructor 0x1004A54AA, 0x198 bytes), given the panel
  (+0x50) and the next free id (+0x74) and added to the panel's control array with the engine's
  CExoArrayList::Add (0x100215440, as CSWGuiPanel::InitControl, 0x10049E476, files a loaded
  control), so the panel draws it. Its fill is set to stretch: FILLSTYLE is the low two bits of
  the byte at +0x1C of the border's params (CSWGuiBorder::Load, 0x1004A1C1A; 0 tiles, 1
  centres, 2 stretches). It is freed when its panel ends.

  The engine's pieces, on the Mac: a button's caption is the CSWGuiText at +0x1B8
  (CSWGuiButton::SetExtent, 0x1004A5ADC), whose rectangle is at +0x08, whose string object is
  at +0x18 and whose ALIGNMENT is the low six bits of the byte at +0x64 (CSWGuiText::Load,
  0x1004A3AA0, through 0x1004A37A2: 8 top, 16 middle, 32 bottom); CSWGuiText::SetExtent is
  0x1004A3D4C.
*/
#include "overlays.h"

#include "../kmrp-layout/text.h"
#include "engine.h"
#include "pad.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <new>

namespace kmrp {
namespace overlays {
namespace {

using engine::At;
using text::LooksLikePointer;
using text::Readable;

struct BadgeShape { const char* resref; short width, height, glyph, glyphWidth; };
#include "../../../src/controller-native/K1ControllerBadgeShapes.inc"

struct Rect { int left, top, width, height; };

const std::size_t kCtlExtent = 0x08, kCtlPanel = 0x50, kCtlFlags = 0x68, kCtlId = 0x74;
const std::uint8_t kCtlVisible = 0x02;
const std::size_t kVtDeletingDtor = 0x08, kVtSetExtent = 0x10;
const std::size_t kPanelControls = 0x30, kPanelControlCount = 0x38, kPanelGff = 0x40;
const std::uintptr_t kBasePanelVtable = 0x1005b3730UL;
const std::size_t kLabelSize = 0x198, kLabelBorder = 0x88;
const std::size_t kBorderParams = 0x18, kParamsStyle = 0x1c, kParamsCorner = 0x58;
const std::size_t kButtonBorder = 0xa8, kButtonHilight = 0x130, kButtonText = 0x1b8;
const std::size_t kTextExtent = 0x08, kTextAlignment = 0x64;

const auto LabelCtor = reinterpret_cast<void (*)(void*)>(0x1004a54aaUL);
const auto ArrayAdd = reinterpret_cast<void (*)(void* list, void* item)>(0x100215440UL);
const auto SetFillImage = reinterpret_cast<void (*)(void* params, const void* resref, int force)>(0x1004a17c2UL);
const auto TextSetExtent = reinterpret_cast<void (*)(void* text, const Rect* rect)>(0x1004a3d4cUL);

struct Overlay {
    void* panel;
    void* button;
    void* label;
    int id;
    Rect textWas;
    bool textMoved;
    char resref[17];
    bool shown;
    // A badge on a button that keeps its own box (ShowBacked): how tall the badge is, whether it
    // stands outside the button, the button's rectangle before it was made wider and after, and
    // the lines its caption had.
    int tall;
    bool outside;
    Rect buttonWas, grownTo;
    bool grown;
    int lines;
};
Overlay g_overlays[256] = {};     // 96 until every badge went on a label (2026-10-08)
unsigned g_made = 0, g_refused = 0, g_freed = 0;

std::uintptr_t VtableOf(void* object) { return LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

// True when the rectangle changed.
bool SetExtent(void* control, const Rect& rect) {
    const Rect& now = At<Rect>(control, kCtlExtent);
    if (now.left == rect.left && now.top == rect.top && now.width == rect.width && now.height == rect.height) return false;
    reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtSetExtent))(control, &rect);
    return true;
}

// How far inside a button one of its borders draws its fill (prompts.cpp, FillInset).
int FillInset(void* button, std::size_t border) {
    char* const params = static_cast<char*>(button) + border + kBorderParams;
    return At<void*>(params, kParamsCorner) ? At<int>(params, 0) : 0;
}

// The one place a badge's size on screen is decided (Windows' K1UniformBadge): its texture was
// made for an area `madeWidth` by `madeHeight` and is drawn in those proportions, as large as
// fits the area both ways, so a badge is never wider without being as much taller and a button
// taller than its fellows has no larger badge.
void UniformBadge(long areaWidth, long areaHeight, long madeWidth, long madeHeight, int& width, int& height) {
    if (areaWidth * madeHeight >= madeWidth * areaHeight) {
        height = static_cast<int>(areaHeight);
        width = static_cast<int>((areaHeight * madeWidth + madeHeight / 2) / madeHeight);
    } else {
        width = static_cast<int>(areaWidth);
        height = static_cast<int>((areaWidth * madeHeight + madeWidth / 2) / madeWidth);
    }
    // Never less than three quarters of the area's height. A texture is as wide as the button
    // it was made for and the glyph is a small part of it, so where the layout in force has
    // made a button much taller in proportion, fitting the whole texture across it leaves a
    // glyph a fraction of the button's height: the container's three buttons, made for a fill
    // area of 273x10, had badges a quarter as tall as their buttons in KMRP's sets (the
    // maintainer, 2026-10-08, at 3840x2160: "too small"). The label is then wider than its
    // button, as it was before 2026-10-08, and is placed by its glyph. The main menu's Quit,
    // which the fit both ways is for, is at 0.79 of its row and is not touched.
    const int least = static_cast<int>((areaHeight * 3 + 2) / 4);
    if (height < least) {
        height = least;
        width = static_cast<int>((static_cast<long>(least) * madeWidth + madeHeight / 2) / madeHeight);
    }
}

// Whether a texture made for one area is drawn in its own proportions when stretched over
// another (Windows' K1BadgeKeepsShape): the two scales, across and down, differ by less than
// half a pixel over the area's height.
bool KeepsShape(long width, long height, long madeWidth, long madeHeight) {
    if (width <= 0 || height <= 0 || madeWidth <= 0 || madeHeight <= 0) return false;
    const double across = static_cast<double>(width) / static_cast<double>(madeWidth);
    const double down = static_cast<double>(height) / static_cast<double>(madeHeight);
    const double apart = across > down ? across / down - 1.0 : down / across - 1.0;
    return apart * static_cast<double>(height) < 0.5;
}

const BadgeShape* ShapeOf(const char* resref) {
    const auto same = [](const char* name, const char* row, std::size_t length) {
        for (std::size_t i = 0; i < length; ++i) {
            const char c = i == 3 ? 'p' : name[i];
            if (c != row[i]) return false;
        }
        return row[length] == '\0';
    };
    const std::size_t length = strnlen(resref, 16);
    for (const BadgeShape& shape : kBadgeShapes)
        if (same(resref, shape.resref, length)) return &shape;
    // A badge with one texture per caption (kmrpx_invnew0 to 5) has one row, without the digit.
    if (length > 1 && resref[length - 1] >= '0' && resref[length - 1] <= '9')
        for (const BadgeShape& shape : kBadgeShapes)
            if (same(resref, shape.resref, length - 1)) return &shape;
    return nullptr;
}

// A button's caption as drawn: its width in pixels, the widest of its lines, and its line's
// height. The sum Draw makes: for each character its texture width plus the font's spacingR,
// times the string's scale. 0 when the caption or its font cannot be read.
int MeasureCaption(void* button, int& lineHeight) {
    lineHeight = 0;
    char* const object = At<char*>(static_cast<char*>(button) + kButtonText, text::kTextObject);
    if (!Readable(object, 0x60)) return 0;
    const char* const string = At<const char*>(object, text::kObjString);
    if (!Readable(string, 1)) return 0;
    text::Font font{};
    if (!text::FontOf(object, font)) return 0;
    float scale = At<float>(object, text::kObjScale);
    if (!(scale > 0.01f && scale < 100.0f)) scale = 1.0f;
    const auto advance = [&font](unsigned char c) { return text::GlyphWidth(font, c) + font.spacing; };
    const int lines = At<int>(object, text::kObjLineCount);
    const int* const lengths = At<const int*>(object, text::kObjLineLengths);
    float widest = 0.0f;
    if (lines > 1 && lines <= 16 && Readable(lengths, static_cast<std::size_t>(lines) * 4)) {
        // The engine's own lines: a negative length repeats the one before; one space or newline
        // between two lines is not drawn.
        const char* at = string;
        int length = 0;
        for (int line = 0; line < lines; ++line) {
            if (lengths[line] >= 0) length = lengths[line];
            if (length > 512 || !Readable(at, static_cast<std::size_t>(length) + 1)) return 0;
            float width = 0.0f;
            for (int i = 0; i < length && at[i]; ++i) width += advance(static_cast<unsigned char>(at[i]));
            if (width > widest) widest = width;
            at += length;
            if (*at == ' ' || *at == '\n') ++at;
        }
    } else {
        for (int i = 0; i < 256; ++i) {
            if (!Readable(string + i, 1) || string[i] == '\0') break;
            if (string[i] == '\n') return 0;   // lines of its own the engine has not laid out yet
            widest += advance(static_cast<unsigned char>(string[i]));
        }
    }
    if (widest <= 0.0f) return 0;
    lineHeight = static_cast<int>(font.lineHeight * scale + 0.5f);
    return static_cast<int>(widest * scale + 0.5f);
}

// The narrowest width that holds the caption in `lines` lines, breaking at spaces as the engine
// does: the sums of consecutive words are tried, and the narrowest that fills no more than
// `lines` lines greedily is taken. 0 when the caption or its font cannot be read.
int MeasureWrapped(void* button, int lines) {
    char* const object = At<char*>(static_cast<char*>(button) + kButtonText, text::kTextObject);
    if (!Readable(object, 0x60)) return 0;
    const char* const string = At<const char*>(object, text::kObjString);
    if (!Readable(string, 1)) return 0;
    text::Font font{};
    if (!text::FontOf(object, font)) return 0;
    float scale = At<float>(object, text::kObjScale);
    if (!(scale > 0.01f && scale < 100.0f)) scale = 1.0f;
    const auto advance = [&font](unsigned char c) { return text::GlyphWidth(font, c) + font.spacing; };
    float words[32];
    int count = 0;
    float word = 0.0f;
    bool any = false;
    for (int i = 0; i < 256; ++i) {
        const char c = Readable(string + i, 1) ? string[i] : '\0';
        if (c == ' ' || c == '\n' || c == '\0') {
            if (any && count < 32) words[count++] = word;
            word = 0.0f;
            any = false;
            if (c == '\0') break;
        } else {
            word += advance(static_cast<unsigned char>(c));
            any = true;
        }
    }
    if (!count) return 0;
    const float space = advance(' ');
    float total = space * (count - 1), widest = 0.0f;
    for (int i = 0; i < count; ++i) {
        total += words[i];
        if (words[i] > widest) widest = words[i];
    }
    float best = total;
    for (int first = 0; first < count; ++first) {
        float candidate = 0.0f;
        for (int last = first; last < count; ++last) {
            candidate += words[last] + (last > first ? space : 0.0f);
            if (candidate < widest || candidate >= best) continue;
            int used = 1;
            float line = 0.0f;
            for (int i = 0; i < count; ++i) {
                const float with = line > 0.0f ? line + space + words[i] : words[i];
                if (with > candidate + 0.01f && line > 0.0f) { ++used; line = words[i]; }
                else line = with;
            }
            if (used <= lines) best = candidate;
        }
    }
    return static_cast<int>(best * scale + 0.5f);
}

int CaptionLines(void* button) {
    char* const object = At<char*>(static_cast<char*>(button) + kButtonText, text::kTextObject);
    const int lines = Readable(object, 0x60) ? At<int>(object, text::kObjLineCount) : 1;
    return lines < 1 ? 1 : lines > 4 ? 4 : lines;
}

Overlay* Find(void* button) {
    for (Overlay& entry : g_overlays)
        if (entry.label && entry.button == button) return &entry;
    return nullptr;
}

// A label of this patch's own in the panel's control array, once per button.
Overlay* Make(void* panel, void* button) {
    if (Overlay* entry = Find(button)) return entry;
    Overlay* slot = nullptr;
    for (Overlay& entry : g_overlays)
        if (!entry.label) { slot = &entry; break; }
    if (!slot || !LooksLikePointer(panel)) { ++g_refused; return nullptr; }
    void* label = ::operator new(kLabelSize, std::nothrow);
    if (!label) return nullptr;
    std::memset(label, 0, kLabelSize);
    LabelCtor(label);
    const int id = At<int>(panel, kPanelControlCount);
    At<void*>(label, kCtlPanel) = panel;
    At<int>(label, kCtlId) = id;
    ArrayAdd(static_cast<char*>(panel) + kPanelControls, label);
    void** const array = At<void**>(panel, kPanelControls);
    if (!LooksLikePointer(array) || At<int>(panel, kPanelControlCount) <= id || array[id] != label) {
        ++g_refused;   // not freed: the array may hold it somewhere
        return nullptr;
    }
    At<std::uint8_t>(label, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
    *slot = {};
    slot->panel = panel;
    slot->button = button;
    slot->label = label;
    slot->id = id;
    ++g_made;
    return slot;
}

}  // namespace

void Hide(void* button) {
    Overlay* const entry = Find(button);
    if (!entry) return;
    entry->shown = false;
    At<std::uint8_t>(entry->label, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
    if (entry->textMoved) {
        TextSetExtent(static_cast<char*>(button) + kButtonText, &entry->textWas);
        entry->textMoved = false;
    }
    if (entry->grown) {
        const Rect& now = At<Rect>(button, kCtlExtent);
        if (now.left == entry->grownTo.left && now.top == entry->grownTo.top && now.width == entry->grownTo.width &&
            now.height == entry->grownTo.height)
            SetExtent(button, entry->buttonWas);
        entry->grown = false;
    }
}

bool Show(void* panel, void* button, const char* resref) {
    const BadgeShape* const shape = resref ? ShapeOf(resref) : nullptr;
    const Rect at = At<Rect>(button, kCtlExtent);
    const int inset = FillInset(button, kButtonBorder), focusInset = FillInset(button, kButtonHilight);
    const int width = at.width - 2 * inset;
    int height = at.height - 2 * inset;
    if (!shape || width <= 0 || height <= 0) { Hide(button); return false; }

    char* const caption = static_cast<char*>(button) + kButtonText;
    Overlay* const known = Find(button);
    Rect text = known && known->textMoved ? known->textWas : At<Rect>(caption, kTextExtent);
    const unsigned alignment = At<std::uint8_t>(caption, kTextAlignment) & 0x3f;
    int line = 0;
    const int captionWidth = MeasureCaption(button, line);
    const auto lineMiddle = [&](const Rect& area) {
        if (alignment & 16) return area.top + area.height / 2;
        if (alignment & 32) return area.top + area.height - line / 2;
        return area.top + line / 2;
    };

    // The shape it was made for, in the normal state and the focused one, and its caption's line.
    bool asMade = KeepsShape(width, height, shape->width, shape->height);
    if (asMade && focusInset != inset) {
        const int step = 2 * (inset - focusInset);
        const int focusWidth = at.width - 2 * focusInset, focusHeight = at.height - 2 * focusInset;
        const int madeWidth = shape->width + step, madeHeight = shape->height + step;
        if (focusWidth > 0 && focusHeight > 0 && madeWidth > 0 && madeHeight > 0)
            asMade = KeepsShape(focusWidth, focusHeight, madeWidth, madeHeight);
    }
    if (asMade && height != shape->height && captionWidth > 0 && line > 0) {
        const int off = lineMiddle(text.height > 0 ? text : at) - (at.top + at.height / 2);
        const int allowed = height / 6 > 2 ? height / 6 : 2;
        if (std::abs(off) > allowed) asMade = false;
    }
    // One way to the screen for every badge (Windows, master 843320b): the label below. Until
    // 2026-10-08 a badge whose button had the shape its texture was made for stayed the button's
    // fill. Only in the unchanged game, where the area is exactly the made one, does the label
    // lie where the fill was and the caption stay where the screen has it; on any other
    // interface every badge stands beside its caption.
    const bool whereMade = asMade && width == shape->width && height == shape->height;

    Overlay* const entry = Make(panel, button);
    if (!entry) return false;

    // One factor for width and height, the largest at which the badge fits the area both ways;
    // and in the middle of its button, top to bottom.
    Rect wanted;
    UniformBadge(width, height, shape->width, shape->height, wanted.width, wanted.height);
    height = wanted.height;
    wanted.top = at.top + (at.height - height) / 2;
    const int centred = (width - wanted.width) / 2;
    const int glyph = centred + wanted.width * shape->glyph / 1000, reach = height / 2 + height / 8;
    const bool fits = glyph - reach >= 0 && glyph + reach <= width;
    wanted.left = at.left + inset + (fits ? centred : shape->glyph < 500 ? 0 : width - wanted.width);

    if (whereMade && entry->textMoved) {
        TextSetExtent(caption, &entry->textWas);     // the caption where the screen had it
        entry->textMoved = false;
    }
    if (captionWidth > 0 && !whereMade) {
        // The caption to the button's middle line, in a rectangle one line tall: one that is
        // aligned to the top or the bottom, and one in the middle of a rectangle whose middle
        // is not the button's.
        const int buttonMiddle = at.top + at.height / 2;
        const bool offMiddle = (alignment & 16) == 0 || std::abs(text.top + text.height / 2 - buttonMiddle) > 1;
        if (line > 0 && offMiddle && text.height > 0 && line < at.height) {
            const Rect centredLine = {text.left, at.top + (at.height - line) / 2, text.width, line};
            const Rect& now = At<Rect>(caption, kTextExtent);
            if (now.left != centredLine.left || now.top != centredLine.top || now.width != centredLine.width ||
                now.height != centredLine.height) {
                if (!entry->textMoved) { entry->textWas = now; entry->textMoved = true; }
                TextSetExtent(caption, &centredLine);
            }
            text = centredLine;
        }
        wanted.top = buttonMiddle - wanted.height / 2;
        const int middle = text.width > 0 ? text.left + text.width / 2 : at.left + at.width / 2;
        const int gap = height / 4, air = height / 8;
        const int glyphLeft = wanted.width * (shape->glyph - shape->glyphWidth / 2) / 1000;
        const int glyphRight = wanted.width * (shape->glyph + shape->glyphWidth / 2) / 1000;
        int left = shape->glyph < 500 ? middle - captionWidth / 2 - gap - glyphRight
                                      : middle + (captionWidth + 1) / 2 + gap - glyphLeft;
        const int first = at.left + inset, last = first + width;
        if (left + glyphRight > last - air) left = last - air - glyphRight;
        if (left + glyphLeft < first + air) left = first + air - glyphLeft;
        wanted.left = left;
    }

    // A label that changes size takes its texture again: one made before the resolution was
    // changed in the game went on drawing it at the old size, unstretched (seen 2026-10-07).
    const bool resized = SetExtent(entry->label, wanted);
    char* const params = static_cast<char*>(entry->label) + kLabelBorder + kBorderParams;
    std::uint8_t& style = At<std::uint8_t>(params, kParamsStyle);
    style = static_cast<std::uint8_t>((style & ~3) | 2);
    char name[32] = {};
    for (int i = 0; i < 16 && resref[i]; ++i) name[i] = resref[i];
    if (resized || !entry->shown || std::memcmp(entry->resref, name, 17) != 0) {
        SetFillImage(params, name, 1);
        std::memcpy(entry->resref, name, 17);
    }
    entry->shown = true;
    std::uint8_t& flags = At<std::uint8_t>(entry->label, kCtlFlags);
    const bool drawn = At<std::uint8_t>(button, kCtlFlags) & kCtlVisible;
    flags = drawn ? (flags | kCtlVisible) : (flags & ~kCtlVisible);
    return true;
}

namespace {

// Level Up and Auto Level Up. Their badges were the button's own box (dialog2) with the glyph on
// it, and both buttons have a 16-unit border with corner art, so the fill, and the texture with
// it, is a strip 8 and 20 units tall: the A was a dot and the Y a smear (Windows, 2026-10-06, in
// the unchanged game too). The box stays on the button, and the glyph is drawn from a plain
// badge of the same letter on a label, as tall as the Close button's 28 units are of the
// button's own height in the game's layout.
struct Backed { const char* resref; short height; const char* plain; };
const Backed kBacked[] = {
    {"kmrpa_charlvl", 40, "kmrpa_abcgok"},
    {"kmrpy_charauto", 52, "kmrpy_abcgrec"},
};
// The two buttons in the Character screen (prompts.cpp's rows: BTN_LEVELUP, BTN_AUTO).
const std::size_t kLevelUp = 0x5d98, kAutoLevelUp = 0x5b58;

const Backed* BackedOf(const char* resref) {
    for (const Backed& backed : kBacked) {
        bool same = true;
        for (int i = 0; same && i < 17; ++i) {
            const char c = i == 3 && resref[i] ? 'p' : resref[i];
            same = c == backed.resref[i];
            if (!backed.resref[i]) break;
        }
        if (same) return &backed;
    }
    return nullptr;
}

Rect OwnRect(void* button) {
    const Overlay* const entry = Find(button);
    const Rect& now = At<Rect>(button, kCtlExtent);
    if (entry && entry->grown && now.left == entry->grownTo.left && now.width == entry->grownTo.width) return entry->buttonWas;
    return now;
}

// How wide the button has to be for badge and caption: three quarters of the badge's height at
// each end, the glyph, a third of the badge's height, the caption in its own lines.
int WidthNeeded(void* button, const Backed& backed, int lines) {
    const BadgeShape* const shape = ShapeOf(backed.plain);
    const Rect own = OwnRect(button);
    const int caption = MeasureWrapped(button, lines);
    if (!shape || caption <= 0 || own.height <= 0) return 0;
    const int tall = own.height * 28 / backed.height;
    const int glyph = tall * shape->width * shape->glyphWidth / (shape->height * 1000);
    return 2 * (tall * 3 / 4) + glyph + tall / 3 + caption + 2;
}

}  // namespace

bool IsBacked(const char* resref) { return resref && BackedOf(resref) != nullptr; }

bool ShowBacked(void* panel, void* button, const char* resref) {
    const Backed* const backed = BackedOf(resref);
    if (!backed) return false;
    char plain[17] = {};
    for (int i = 0; i < 16 && backed->plain[i]; ++i) plain[i] = backed->plain[i];
    plain[3] = resref[3];
    const BadgeShape* const shape = ShapeOf(plain);
    if (!shape) return false;
    const Rect own = OwnRect(button);
    Overlay* known = Find(button);
    const int lines = known && known->lines ? known->lines : CaptionLines(button);
    int tall = (own.height * 28 + backed->height / 2) / backed->height;
    if (tall < 8) tall = 8;
    int needed = WidthNeeded(button, *backed, lines);
    // Both buttons get the wider of the two needs, so the two badges stand under each other.
    if (LooksLikePointer(panel)) {
        void* const levelUp = static_cast<char*>(panel) + kLevelUp;
        void* const autoLevel = static_cast<char*>(panel) + kAutoLevelUp;
        void* const other = button == levelUp ? autoLevel : button == autoLevel ? levelUp : nullptr;
        if (other) {
            const Overlay* const theirs = Find(other);
            const int width = WidthNeeded(other, button == levelUp ? kBacked[1] : kBacked[0],
                                          theirs && theirs->lines ? theirs->lines : CaptionLines(other));
            if (width > needed) needed = width;
        }
    }
    const bool outside = needed > 2 * own.width;
    Rect grown = own;
    if (!outside && needed > own.width) grown = {own.left - (needed - own.width) / 2, own.top, needed, own.height};
    Overlay* const entry = Make(panel, button);
    if (!entry) return false;
    const Rect& now = At<Rect>(button, kCtlExtent);
    if (now.left != grown.left || now.width != grown.width) {
        if (entry->textMoved) entry->textMoved = false;   // the button lays its caption out again
        SetExtent(button, grown);
    }
    entry->lines = lines;
    entry->grown = grown.width != own.width;
    entry->buttonWas = own;
    entry->grownTo = grown;

    // The badge on its label: as tall as `tall`, in the button's middle line, at the button's
    // left end with the caption beside it, or outside the button on the left.
    const Rect at = At<Rect>(button, kCtlExtent);
    Rect wanted;
    wanted.height = tall < at.height ? tall : at.height;
    wanted.top = at.top + (at.height - wanted.height) / 2;
    wanted.width = (wanted.height * shape->width + shape->height / 2) / shape->height;
    const int glyphLeft = wanted.width * (shape->glyph - shape->glyphWidth / 2) / 1000;
    const int glyphRight = wanted.width * (shape->glyph + shape->glyphWidth / 2) / 1000;
    char* const caption = static_cast<char*>(button) + kButtonText;
    if (outside) {
        wanted.left = at.left - wanted.height / 4 - glyphRight;
    } else {
        wanted.left = at.left + wanted.height * 3 / 4 - glyphLeft;
        const Rect whole = entry->textMoved ? entry->textWas : At<Rect>(caption, kTextExtent);
        const int from = wanted.left + glyphRight + wanted.height / 3;
        const Rect beside = {from, whole.top, (at.left + at.width - wanted.height * 3 / 4) - from, whole.height};
        if (beside.width > 0) {
            if (!entry->textMoved) { entry->textWas = whole; entry->textMoved = true; }
            TextSetExtent(caption, &beside);
        }
    }
    // A label that changes size takes its texture again: one made before the resolution was
    // changed in the game went on drawing it at the old size, unstretched (seen 2026-10-07).
    const bool resized = SetExtent(entry->label, wanted);
    char* const params = static_cast<char*>(entry->label) + kLabelBorder + kBorderParams;
    std::uint8_t& style = At<std::uint8_t>(params, kParamsStyle);
    style = static_cast<std::uint8_t>((style & ~3) | 2);
    if (resized || !entry->shown || std::memcmp(entry->resref, plain, 17) != 0) {
        char name[32] = {};
        std::memcpy(name, plain, 17);
        SetFillImage(params, name, 1);
        std::memcpy(entry->resref, plain, 17);
    }
    entry->shown = true;
    entry->tall = tall;
    entry->outside = outside;
    std::uint8_t& flags = At<std::uint8_t>(entry->label, kCtlFlags);
    const bool drawn = At<std::uint8_t>(button, kCtlFlags) & kCtlVisible;
    flags = drawn ? (flags | kCtlVisible) : (flags & ~kCtlVisible);
    return true;
}

std::uint32_t Signature(void* button) {
    std::uint32_t hash = 2166136261u;
    const auto add = [&hash](const unsigned char* bytes, std::size_t count) {
        for (std::size_t i = 0; i < count; ++i) hash = (hash ^ bytes[i]) * 16777619u;
    };
    if (!Readable(button, kButtonText + 0x20)) return hash;
    add(reinterpret_cast<const unsigned char*>(static_cast<char*>(button) + kCtlExtent), 16);
    add(reinterpret_cast<const unsigned char*>(static_cast<char*>(button) + kCtlFlags), 1);
    char* const object = At<char*>(static_cast<char*>(button) + kButtonText, text::kTextObject);
    if (Readable(object, 0x60)) {
        const char* const string = At<const char*>(object, text::kObjString);
        for (int i = 0; i < 96 && Readable(string + i, 1) && string[i]; ++i)
            add(reinterpret_cast<const unsigned char*>(string + i), 1);
        // The caption's font as it is now: after the resolution is changed in the game the same
        // caption in the same rectangle is drawn from another size's font, and a badge placed
        // from the old one stood on the caption (seen 2026-10-07, 1512x982 to 3024x1964).
        text::Font font{};
        if (text::FontOf(object, font)) {
            const float metrics[4] = {static_cast<float>(font.lineHeight), font.spacing, text::GlyphWidth(font, 'M'),
                                      At<float>(object, text::kObjScale)};
            add(reinterpret_cast<const unsigned char*>(metrics), sizeof metrics);
        }
    }
    return hash;
}

// A button made wider for its badge (ShowBacked) is its screen's own size again while another
// screen is the one in front; shown again, it is made wider again from what its screen then
// gives it. Windows' RestoreK1GrownButtons (2026-10-09): after the resolution is changed in the
// game every live control is laid out again from where it stands, so a button left wide on a
// screen that was not in front was laid out from the wide rectangle, taken here as the
// screen's own at the new size, and stayed wider than its layout's after a change and back.
void RestoreGrown(void* front) {
    for (Overlay& entry : g_overlays) {
        if (!entry.label || !entry.button || !entry.grown || entry.panel == front) continue;
        const Rect& now = At<Rect>(entry.button, kCtlExtent);
        if (now.left == entry.grownTo.left && now.top == entry.grownTo.top && now.width == entry.grownTo.width &&
            now.height == entry.grownTo.height) {
            if (entry.textMoved) entry.textMoved = false;   // the button lays its caption out again
            SetExtent(entry.button, entry.buttonWas);
        }
        entry.grown = false;
    }
}

void Sync(void* panel) {
    for (Overlay& entry : g_overlays) {
        if (!entry.label || entry.panel != panel || !entry.shown) continue;
        std::uint8_t& flags = At<std::uint8_t>(entry.label, kCtlFlags);
        const bool drawn = At<std::uint8_t>(entry.button, kCtlFlags) & kCtlVisible;
        flags = drawn ? (flags | kCtlVisible) : (flags & ~kCtlVisible);
    }
}

void Forget(void* panel) {
    if (VtableOf(panel) != kBasePanelVtable || At<void*>(panel, kPanelGff) != nullptr) return;
    for (Overlay& entry : g_overlays) {
        if (!entry.label || entry.panel != panel) continue;
        void** const array = At<void**>(panel, kPanelControls);
        const int count = At<int>(panel, kPanelControlCount);
        // Only while the panel still holds it at its id: a leak is safer than a double free.
        if (LooksLikePointer(array) && entry.id >= 0 && entry.id < count && array[entry.id] == entry.label) {
            array[entry.id] = nullptr;
            const std::uintptr_t vtable = VtableOf(entry.label);
            if (vtable) reinterpret_cast<void (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtDeletingDtor))(entry.label);
            ++g_freed;
        }
        entry = {};
    }
}

void Status() { Log("overlays: %u made, %u refused, %u freed", g_made, g_refused, g_freed); }

}  // namespace overlays
}  // namespace kmrp
