/*
  KMRP for macOS: each native text string fitted to its box when the engine draws it.

  The port of Windows' src/controller-native/K1TextLayout.cpp (handoff items 57 and 68, and the
  letters' middle of item 104), whose rules these are. The size search is Windows' own header,
  K1TextFitPolicy.h. Fixed boxes are drawn at the largest size up to the chosen one that fits; list
  rows grow with their text (text_rows.cpp); scrolling descriptions and text entry keep the chosen
  size.

  The engine, KOTOR_Exe 1.4.0, CAurGUIStringInternal (vtable 0x1005a2860, Windows 0x741878), from
  its constructor (0x1001bbd68), WrapStrings (0x1001bc644) and its draw (0x1001bcb04):

      +0x08 left  +0x0C top  +0x10 width  +0x14 height      Windows +0x04 ... +0x10
      +0x18 the text                                        +0x14
      +0x20 the font, whose vtable +0x78 is its information +0x18, vtable +0x38
      +0x38 each line's width, +0x40 how many               +0x28, +0x2C
      +0x48 each line's length, +0x50 how many lines        +0x34, +0x38
      +0x58 the scale                                       +0x40
      +0x5E the alignment (0x38 vertical, 0x10 centred)     +0x46

  CSWGuiText (vtable 0x1005b38c0, CSWGuiEditText 0x1005d2ab0; Windows 0x73E3A4, 0x73E444) keeps its
  string at +0x18 (Windows +0x14) and its box at +0x08. A label's is at +0x110, a button's at
  +0x1B8, an edit box's at +0x130 (Windows +0xD0, +0x154, +0xE0).

  The font's information is as text.h has it: fontheight +0x04, texturewidth +0x0C, spacingR
  +0x10, spacingB +0x14, the coordinates at [+0x18] and [+0x28] (Windows +0x24), 12 bytes a glyph.

  Six hooks (kotor1-steam-aspyr-macos.hooks.toml in this folder), Windows' six: the constructor's
  end, the destructor, WrapStrings, GetIdealPixelHeight, the draw and CSWGuiListBox::Draw. A
  seventh, CSWGuiControl's destructor, is Windows' KmrpControlDestroyedK1.

  The Container's widening is Windows' too (Container, below), since 2026-11-03: the sets widen
  that panel for their own fonts (kmrp-guiblend.c, fit_container_to_caption), and the fonts the
  game is given are now fonts.cpp's, whose captions are wider (at 3024x1964 the X stood on the S of
  "Switch To Give Item" at 50%, the coordinator's run of 2026-11-03).
  Those measure the caption alone, so the pad's X stands on the S of "Switch To Give Item" (seen at
  3024x1964, 2026-11-03). A port of Windows' run-time widening was tried and taken out the same day:
  the caption's measured width came back as half the drawn one, then the panel narrowed.

  The file is about each string's state. Nothing here is needed before the module's constructors
  have run, and nothing is a global with a constructor (kmrp_layout.cpp's rule): TheState() is made
  on first use.
*/
#include "text_fit.h"

#include "caption_ink.h"
#include "text.h"

#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <limits>
#include <map>
#include <string>
#include <strings.h>
#include <tuple>
#include <vector>

extern "C" void* CGLGetCurrentContext();

namespace kmrp {
namespace textfit {
namespace {

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

const std::uintptr_t kStringVtable = 0x1005a2860UL;
const std::uintptr_t kTextVtable = 0x1005b38c0UL, kEditTextVtable = 0x1005d2ab0UL;
const std::uintptr_t kListVtable = 0x1005b4318UL;
const std::uintptr_t kEditboxVtable = 0x1005b4480UL, kSaveEditBoxVtable = 0x1005ae4e0UL;
const std::uintptr_t kHudVtable = 0x1005a6220UL;       // CSWGuiMainInterface, Windows 0x753F50
const std::uintptr_t kDialogVtable = 0x1005a6c88UL;    // CSWGuiDialogCinematic, Windows 0x755800

const std::size_t kStrLeft = 0x08, kStrTop = 0x0C, kStrWidth = 0x10, kStrHeight = 0x14, kStrText = 0x18, kStrFont = 0x20;
const std::size_t kStrWidths = 0x38, kStrWidthCount = 0x40, kStrLengths = 0x48, kStrLines = 0x50, kStrScale = 0x58, kStrAlign = 0x5E;
const std::size_t kTextString = 0x18;
const std::size_t kVtFontInfo = 0x78;
const std::size_t kLabelText = 0x110, kEditText = 0x130;
const std::size_t kExtent = 0x08, kPanelManager = 0x20, kFlags = 0x68;
const std::size_t kManagerWidth = 0xA4, kManagerHeight = 0xA6;
const std::size_t kVtSetExtent = 0x10;
const std::size_t kPanelBorder = 0x70, kPanelControls = 0x30, kPanelCount = 0x38;
const std::uintptr_t kButtonVtable = 0x1005b47b8UL, kToggleVtable = 0x1005b3da8UL, kLabelVtable = 0x1005b3c50UL;

struct Rect { int left, top, width, height; };
bool Same(const Rect& a, const Rect& b) {
    return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height;
}
void Extent(void* control, const Rect& value) {
    if (Same(At<Rect>(control, kExtent), value)) return;
    reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(At<std::uintptr_t>(control, 0) + kVtSetExtent))(control, &value);
}

enum class Mode { Bounded, Flow, Editable };
struct Metrics {
    void* font = nullptr;
    void* info = nullptr;
    const float* first = nullptr;
    const float* last = nullptr;
    double height = 0, textureWidth = 0, spacing = 0, leading = 0;
};
struct Key {
    void* font = nullptr;
    void* info = nullptr;
    const char* text = nullptr;
    const float* first = nullptr;
    const float* last = nullptr;
    std::uint64_t hash = 0;
    unsigned generation = 0;
    int width = 0, height = 0;
    float requested = 1;
    double lineHeight = 0, textureWidth = 0, spacing = 0, leading = 0;
    unsigned alignment = 0;
    Mode mode = Mode::Bounded;
    bool operator==(const Key& b) const {
        return std::tie(font, info, text, first, last, hash, generation, width, height, requested, lineHeight, textureWidth,
                        spacing, leading, alignment, mode) ==
               std::tie(b.font, b.info, b.text, b.first, b.last, b.hash, b.generation, b.width, b.height, b.requested,
                        b.lineHeight, b.textureWidth, b.spacing, b.leading, b.alignment, b.mode);
    }
};
struct StringState {
    float requested = 1, applied = 1;
    // The last fit's result, and whether a native wrap or measurement has put the request back
    // since (Restore): the next draw re-applies it, one wrap.
    float fitted = 1;
    bool restored = false;
    Mode mode = Mode::Bounded;
    bool cached = false;
    Key key{};
    KmrpTextFit::Measurement measured{0, 0, 0, false};
    std::vector<int> drawWidths, drawLengths;
    // Its letters on its box's middle (CentreLetters): the top the layout gave it, the one
    // written, and what the move was worked out for.
    bool inkMoved = false;
    int inkFrom = 0, inkTo = 0;
    const void* inkInfo = nullptr;
    const char* inkText = nullptr;
    std::uint64_t inkHash = 0;
    float inkScale = 0;
    int inkShift = 0;
    bool inkRead = false;     // the font was read for inkShift; else it is asked again
    // The middle, on screen, of the art its control is drawn on (ArtCaptions), or INT_MIN: its
    // letters go there instead of its box's middle.
    int artMiddle = INT_MIN;
};
// A stretched picture's light, read once it is uploaded, and where a control's art was found.
struct ArtPicture { std::string name; int width = 0, height = 0; std::vector<unsigned char> light; bool read = false; };
struct ArtPlace { std::string name; Rect behind{}, control{}; int middle = INT_MIN; bool read = false; };
struct PanelState { std::string resource; std::map<void*, std::string> controls; };
struct PauseState {
    bool kept = false;
    int left = 0, right = 0, top = 0, bottom = 0, gap = 2, underMenu = 2;
    int reasonInset = 0, pressInset = 0;
    Rect lastPanel{}, lastReason{}, lastPress{}, lastButton{};
    bool cached = false, pressShown = false;
    Key reasonKey{}, pressKey{};
};
// The container panel's widening (Container): the panel and its controls as the game last laid
// them out, and what was added.
struct Widened {
    bool known = false;
    int grow = 0;
    Rect base{}, applied{};
    std::vector<std::pair<void*, Rect>> controls;
};
struct State {
    std::map<void*, Widened> widened;
    std::map<void*, StringState> strings;
    std::map<void*, PanelState> panels;
    std::map<void*, PauseState> pauses;
    unsigned generation = 1;
    bool measuring = false;
    int lastWidth = 0, lastHeight = 0;
    std::vector<ArtPicture> artPictures;     // the last few read, newest last
    std::map<void*, ArtPlace> artPlaces;     // by control, until it goes
    std::map<void*, void*> captionsLike;     // CaptionLike
};
State& TheState() {
    static State* state = new State;
    return *state;
}

struct Measuring {
    bool was;
    Measuring() : was(TheState().measuring) { TheState().measuring = true; }
    ~Measuring() { TheState().measuring = was; }
};

bool Scale(float value) { return std::isfinite(value) && value > 0 && value <= 128; }

void ObserveScale(void* object, StringState& state) {
    const float current = At<float>(object, kStrScale);
    if (Scale(current) && current != state.applied) {
        state.requested = current;
        state.applied = current;
        state.cached = false;
    }
}
void WriteScale(void* object, StringState& state, float value) {
    At<float>(object, kStrScale) = value;
    state.applied = value;
}
// The engine's own wrap at the string's box, through its table as CSWGuiText::SetExtent calls it.
void Wrap(void* object) {
    Measuring guard;
    reinterpret_cast<void (*)(void*, int)>(0x1001bc644)(object, -1);
}
bool Font(void* object, Metrics& result) {
    result.font = At<void*>(object, kStrFont);
    if (!result.font) return false;
    const auto table = At<std::uintptr_t>(result.font, 0);
    result.info = reinterpret_cast<void* (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(table + kVtFontInfo))(result.font);
    if (!result.info) return false;
    result.height = At<float>(result.info, text::kInfoHeight) * 100.0;
    result.textureWidth = At<float>(result.info, text::kInfoTextureWidth);
    result.spacing = At<float>(result.info, text::kInfoSpacingR);
    result.leading = At<float>(result.info, 0x14) * 100.0;
    result.first = At<const float*>(result.info, text::kInfoUpperLeft);
    result.last = At<const float*>(result.info, text::kInfoLowerRight);
    return result.first && result.last && std::isfinite(result.height) && result.height > 0 && result.height < 65536 &&
        std::isfinite(result.textureWidth) && result.textureWidth > 0 && result.textureWidth < 65536 &&
        std::isfinite(result.spacing) && std::fabs(result.spacing) < 65536 && std::isfinite(result.leading) &&
        std::fabs(result.leading) < 65536;
}
bool MakeKey(void* object, const StringState& state, const Metrics& font, Key& key) {
    const char* text = At<const char*>(object, kStrText);
    if (!text || !*text) return false;
    // The game owns this buffer. Hash contents as well as its address: its allocator and some
    // setters reuse a buffer for a different HUD message.
    std::uint64_t hash = 1469598103934665603ull;
    unsigned length = 0;
    for (; length < 262144 && text[length]; ++length) {
        hash ^= static_cast<unsigned char>(text[length]);
        hash *= 1099511628211ull;
    }
    if (length == 262144) return false;
    key.font = font.font; key.info = font.info; key.text = text;
    key.first = font.first; key.last = font.last; key.hash = hash;
    key.generation = TheState().generation; key.width = At<int>(object, kStrWidth); key.height = At<int>(object, kStrHeight);
    key.requested = state.requested; key.lineHeight = font.height; key.textureWidth = font.textureWidth;
    key.spacing = font.spacing; key.leading = font.leading; key.mode = state.mode;
    key.alignment = At<unsigned char>(object, kStrAlign);
    return key.width > 0 && key.width <= 32767 && key.height >= 0 && key.height <= 32767;
}
KmrpTextFit::Measurement WrappedMeasurement(void* object, float scale, const Metrics& font, std::vector<int>* drawWidths = nullptr,
                                            std::vector<int>* drawLengths = nullptr) {
    const int count = At<int>(object, kStrLines);
    const int widthsCount = At<int>(object, kStrWidthCount);
    const int* lengths = At<const int*>(object, kStrLengths);
    const int* widths = At<const int*>(object, kStrWidths);
    const char* cursor = At<const char*>(object, kStrText);
    if (count < 0 || count > 262144 || widthsCount < count || (count && (!lengths || !widths)) || !cursor) return {0, 0, 0, false};
    double widest = 0;
    std::size_t consumed = 0;
    if (drawWidths) drawWidths->clear();
    if (drawLengths) drawLengths->clear();
    for (int line = 0; line < count; ++line) {
        const int signedLength = lengths[line];
        if (signedLength == (std::numeric_limits<int>::min)()) return {0, 0, 0, false};
        const unsigned length = static_cast<unsigned>(signedLength < 0 ? -signedLength : signedLength);
        if (length > 262144 || consumed + length > 262144) return {0, 0, 0, false};
        double pen = 0, right = 0;
        const auto glyph = [&](unsigned char value) {
            const unsigned g = static_cast<unsigned>(value) * 3;
            const double width = (font.last[g] - font.first[g]) * font.textureWidth * 100.0 * scale;
            right = (std::max)(right, pen + width);
            pen += width + font.spacing * 100.0 * scale;
        };
        for (unsigned i = 0; i < length; ++i) {
            if (!cursor[i]) return {0, 0, 0, false};
            glyph(static_cast<unsigned char>(cursor[i]));
        }
        if (signedLength < 0) glyph('-');
        widest = (std::max)(widest, (std::max)(right, static_cast<double>(widths[line])));
        // The draw's centring and right alignment use this integer array, while the glyph quads
        // use fractional advances (0x1001bcb04, at its line loop). Round outward so alignment
        // cannot put a fitting last glyph beyond the box.
        if (drawWidths) {
            if (!std::isfinite(right) || right > (std::numeric_limits<int>::max)()) return {0, 0, 0, false};
            drawWidths->push_back((std::max)(widths[line], static_cast<int>(std::ceil(right))));
        }
        if (drawLengths) drawLengths->push_back(signedLength);
        cursor += length; consumed += length;
        if (*cursor == '\n' || *cursor == ' ') { ++cursor; ++consumed; }
    }
    const double line = font.height * scale;
    const double leading = count > 1 ? (count - 1) * (std::max)(0.0, font.leading * scale) : 0.0;
    // The draw centres by count * fontheight, then advances lines by fontheight plus leading. A
    // centred block therefore needs the leading on both sides of its centring equation, not only
    // in its total drawn height.
    const bool centred = (At<unsigned char>(object, kStrAlign) & 0x38) == 0x10;
    const double height = count * line + (centred ? 2.0 : 1.0) * leading;
    return {widest, height, count, std::isfinite(widest) && widest >= 0 && std::isfinite(height)};
}
KmrpTextFit::Measurement Measure(void* object, float scale, const Metrics& font) {
    At<float>(object, kStrScale) = scale;
    Wrap(object);
    return WrappedMeasurement(object, scale, font);
}
// For a bounded box: a word the line breaker had to cut (a line of negative length, drawn with a
// hyphen; WrapStrings, 0x1001bc644, does so when a word is wider than the box) does not fit. The
// box's height may well hold the second line, so Fits alone accepted it. When no size makes it
// whole the request stands, as for any measurement nothing fits. Two kinds of text:
//   - one word (no space or newline), a name or a number: never cut.
//   - a figure, a text without letters, such as a vitality: one line. Equip's and Inventory's
//     vitality labels ask the label's ideal height and, where "%d/%d" is taller than one line, set
//     "%d/ %d" instead, so that it breaks after the slash (CSWGuiInGameEquip::UpdateInventory,
//     0x1002bb1c6, and 0x10024afc2 for Inventory). At 100% text at 3024x1964 Equip's narrow box cut that
//     into "94-" / "4/" / "1056" and Inventory's showed "944/" / "1056" (the coordinator's run of
//     2026-11-03). No part of the figure is cut: it breaks only at the engine's space, at the
//     largest size that keeps both halves whole. Not drawn on one line: that shrank it to a sliver at
//     the default size, where the game itself shows "944/" over "1056" (seen in the Mac App Store's
//     game at 1512x982, the same day).
// In a sentence a cut long word costs less than the whole sentence drawn at the size that word
// would need, so a text with letters and spaces keeps the native rule.
KmrpTextFit::Measurement MeasureWhole(void* object, float scale, const Metrics& font) {
    KmrpTextFit::Measurement measured = Measure(object, scale, font);
    const char* const text = At<const char*>(object, kStrText);
    if (!text || !measured.valid) return measured;
    bool spaced = false, letters = false;
    for (int i = 0; i < 4096 && text[i]; ++i) {
        const unsigned char c = static_cast<unsigned char>(text[i]);
        if (c == ' ' || c == '\n') spaced = true;
        else if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c >= 0xC0) letters = true;
    }
    if (spaced && letters) return measured;
    const int count = At<int>(object, kStrLines);
    const int* lengths = At<const int*>(object, kStrLengths);
    if (count > 0 && lengths)
        for (int line = 0; line < count; ++line)
            if (lengths[line] < 0) { measured.lines = 0; break; }
    return measured;
}
void DrawWidths(void* object, const StringState& state) {
    if (state.mode != Mode::Bounded || !state.cached || At<int>(object, kStrLines) != static_cast<int>(state.drawWidths.size()) ||
        At<int>(object, kStrWidthCount) < At<int>(object, kStrLines)) return;
    int* widths = At<int*>(object, kStrWidths);
    const int* lengths = At<const int*>(object, kStrLengths);
    if (!widths || !lengths || state.drawLengths.size() != state.drawWidths.size()) return;
    for (std::size_t i = 0; i < state.drawLengths.size(); ++i)
        if (lengths[i] != state.drawLengths[i]) return;
    for (std::size_t i = 0; i < state.drawWidths.size(); ++i) widths[i] = state.drawWidths[i];
}
void Apply(void* object, bool outerWrap) {
    State& all = TheState();
    if (!object || all.measuring) return;
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return;  // construction has not completed yet
    StringState& state = found->second;
    ObserveScale(object, state);
    if (state.mode == Mode::Flow) {
        if (At<float>(object, kStrScale) != state.requested) {
            WriteScale(object, state, state.requested);
            if (!outerWrap) Wrap(object);
        }
        return;
    }
    Metrics font;
    Key key;
    if (!Font(object, font) || !MakeKey(object, state, font, key) || key.height <= 0) return;
    if (state.cached && state.key == key) {
        // Same text, box and font as the last fit: put its result back if a native wrap or
        // measurement restored the request since. One wrap, no search.
        if (state.restored && state.fitted != At<float>(object, kStrScale)) {
            WriteScale(object, state, state.fitted);
            if (!outerWrap) Wrap(object);
        }
        state.restored = false;
        return;
    }
    state.restored = false;
    const auto measure = [&](float scale) {
        // The underscore caret is in this same string. Never shrink a growing input by its length
        // or change its native horizontal rules.
        if (state.mode == Mode::Editable) return KmrpTextFit::Measurement{0, font.height * scale, 1, true};
        return MeasureWhole(object, scale, font);
    };
    const KmrpTextFit::Bounds bounds{static_cast<double>(key.width), static_cast<double>(key.height)};
    const float effective = KmrpTextFit::Fit(state.requested, bounds, measure);
    WriteScale(object, state, effective);
    state.fitted = effective;
    // The last solver trial might not have been its returned value (an invalid native measurement
    // keeps the request). Finish with one consistent wrap.
    if (!outerWrap || state.mode != Mode::Editable) Wrap(object);
    state.drawWidths.clear();
    state.drawLengths.clear();
    if (state.mode == Mode::Bounded) {
        const auto final = WrappedMeasurement(object, effective, font, &state.drawWidths, &state.drawLengths);
        if (!final.valid) { state.drawWidths.clear(); state.drawLengths.clear(); }
    }
    state.key = key;
    state.cached = true;
}
void* Internal(void* wrapper) {
    if (!wrapper) return nullptr;
    const auto table = At<std::uintptr_t>(wrapper, 0);
    if (table != kTextVtable && table != kEditTextVtable) return nullptr;
    void* object = At<void*>(wrapper, kTextString);
    return object && At<std::uintptr_t>(object, 0) == kStringVtable ? object : nullptr;
}
void Policy(void* wrapper, Mode mode) {
    void* object = Internal(wrapper);
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return;
    StringState& state = found->second;
    ObserveScale(object, state);
    if (state.mode != mode) { state.mode = mode; state.cached = false; }
    if (mode == Mode::Flow && At<float>(object, kStrScale) != state.requested) {
        WriteScale(object, state, state.requested);
        Wrap(object);
    }
    if (mode != Mode::Flow) Apply(object, false);
}
void* Control(void* panel, const char* tag) {
    State& all = TheState();
    const auto found = all.panels.find(panel);
    if (found == all.panels.end()) return nullptr;
    for (const auto& item : found->second.controls)
        if (item.second == tag) return item.first;
    return nullptr;
}
bool CurrentKey(void* object, Key& key) {
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return false;
    ObserveScale(object, found->second);
    Metrics font;
    return Font(object, font) && MakeKey(object, found->second, font, key);
}

// The pause notice takes the menu-button row's width (Windows' Pause): directly under the row, as
// far below it as its buttons stand apart, from the live row, so any HUD layout or size keeps it.
void Pause(void* panel, void* hud, int screenWidth, int screenHeight) {
    void* reason = Control(panel, "LBL_PAUSEREASON");
    void* press = Control(panel, "LBL_PRESS");
    void* button = Control(panel, "BTN_UNPAUSE");
    if (!reason || !press || !button) return;
    const char* const tags[] = {"BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI", "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT"};
    int left = screenWidth, right = 0, bottom = 0;
    Rect rowFirst{}, rowSecond{};
    for (const char* tag : tags) {
        void* c = Control(hud, tag);
        if (!c) return;
        const Rect r = At<Rect>(c, kExtent);
        // The Xbox HUD parks this row. Its own pause adapter owns that layout.
        if (r.left < 0 || r.top < 0 || r.width <= 0 || r.height <= 0 || r.left + r.width > screenWidth) return;
        left = (std::min)(left, r.left);
        right = (std::max)(right, r.left + r.width);
        bottom = (std::max)(bottom, r.top + r.height);
        if (tag == tags[0]) rowFirst = r;
        else if (tag == tags[1]) rowSecond = r;
    }
    const int spacing = rowSecond.left - (rowFirst.left + rowFirst.width);
    const int underMenu = spacing >= 0 && spacing < screenHeight / 8 ? spacing : 2;
    const Rect panelNow = At<Rect>(panel, kExtent), rNow = At<Rect>(reason, kExtent), pNow = At<Rect>(press, kExtent);
    void* const reasonWrapper = static_cast<char*>(reason) + kLabelText;
    void* const pressWrapper = static_cast<char*>(press) + kLabelText;
    void* reasonText = Internal(reasonWrapper);
    void* pressText = Internal(pressWrapper);
    if (!reasonText || !pressText) return;
    PauseState& state = TheState().pauses[panel];
    const bool pressShown = (At<unsigned char>(press, kFlags) & 2u) != 0;
    Key reasonKey, pressKey;
    if (state.cached && pressShown == state.pressShown && left == state.lastPanel.left && right - left == state.lastPanel.width &&
        bottom + state.underMenu == state.lastPanel.top && Same(panelNow, state.lastPanel) && Same(rNow, state.lastReason) &&
        Same(pNow, state.lastPress) && Same(At<Rect>(button, kExtent), state.lastButton) && CurrentKey(reasonText, reasonKey) &&
        reasonKey == state.reasonKey && (!pressShown || (CurrentKey(pressText, pressKey) && pressKey == state.pressKey)))
        return;
    if (!state.kept || (panelNow.width != state.lastPanel.width && rNow.width != state.lastReason.width)) {
        state.left = (std::max)(0, rNow.left);
        state.right = (std::max)(0, panelNow.width - rNow.left - rNow.width);
        state.top = (std::max)(0, rNow.top);
        // Label::SetExtent removes its border's client insets before giving the text its bounds.
        // NaturalHeight measures that inner text box.
        state.reasonInset = (std::max)(0, rNow.height - At<int>(reasonText, kStrHeight));
        state.pressInset = (std::max)(0, pNow.height - At<int>(pressText, kStrHeight));
        const Rect& last = pressShown ? pNow : rNow;
        state.bottom = (std::max)(0, panelNow.height - last.top - last.height);
        const int gap = pNow.top - rNow.top - rNow.height;
        state.gap = pressShown && gap >= 0 && gap < screenHeight / 4 ? gap : 2;   // the game's SetPauseReason gap
        state.kept = true;
    }
    state.underMenu = underMenu;
    const int width = right - left, contentWidth = width - state.left - state.right;
    if (contentWidth < 1) return;
    Flow(reasonWrapper);
    Flow(pressWrapper);
    Extent(reason, {state.left, state.top, contentWidth, (std::max)(1, rNow.height)});
    Extent(press, {state.left, pNow.top, contentWidth, (std::max)(1, pNow.height)});
    const int reasonNatural = NaturalHeight(reasonWrapper);
    const int pressNatural = pressShown ? NaturalHeight(pressWrapper) : 0;
    if (reasonNatural <= 0 || (pressShown && pressNatural <= 0)) return;
    const int reasonHeight = reasonNatural + state.reasonInset;
    const int pressHeight = pressShown ? pressNatural + state.pressInset : 0;
    const int top = bottom + state.underMenu;
    const int available = (std::max)(1, screenHeight - top);
    const int gap = pressShown ? state.gap : 0;
    int first = reasonHeight, second = pressHeight;
    const int content = (std::max)(1, available - state.top - state.bottom - gap);
    if (first + second > content) {
        first = (std::max)(1, static_cast<int>(double(content) * first / (first + second)));
        second = pressShown ? (std::max)(1, content - first) : 0;
    }
    const Rect firstRect{state.left, state.top, contentWidth, first};
    const Rect secondRect{state.left, state.top + first + gap, contentWidth, pressShown ? second : pNow.height};
    const int height = state.top + first + gap + second + state.bottom;
    Extent(panel, {left, top, width, height});
    Extent(reason, firstRect);
    if (pressShown) Extent(press, secondRect);
    Extent(button, {state.left, state.top, contentWidth, first + gap + second});
    if (first < reasonHeight) Bounded(reasonWrapper);
    if (pressShown && second < pressHeight) Bounded(pressWrapper);
    state.lastPanel = At<Rect>(panel, kExtent);
    state.lastReason = At<Rect>(reason, kExtent);
    state.lastPress = At<Rect>(press, kExtent);
    state.lastButton = At<Rect>(button, kExtent);
    state.pressShown = pressShown;
    state.cached = CurrentKey(reasonText, state.reasonKey) && (!pressShown || CurrentKey(pressText, state.pressKey));
}

// The container panel (container.gui): its three buttons share the panel's width, and "Switch To
// Give Item" did not fit. The panel widens by what its widest button text needs at the requested
// size, centred on its old place, and every control in it (title, list, buttons) widens with it, so
// the item names gain the room too. Measured from the game's own layout each time it lays the panel
// out, so it never accumulates; at most the screen's width. Room around the text: one and a half
// lines on each side, as the pad's badge stands left of the caption, a line wide and a quarter off
// (Windows' Container, K1TextLayout.cpp, and the maintainer's reasons there).
//
// The caption's width is at its requested scale (NaturalWidth), not at the one the string holds:
// that is the fit's between the draw and the next native wrap and the request after it, so a width
// read from the string itself came and went by the fit's factor, frame to frame (259 and 514 px at
// 3024x1964, the coordinator's run of 2026-11-03). CSWGuiText::GetIdealWidthAndHeight (0x1004a3e48)
// is no measure of it either: it starts from a fixed 400 px (+0x80 of the CSWGuiText, its
// constructor's 400) and steps down by ten while the line count stays the one at 400, so a caption
// wider than 400 comes back as the narrowest width holding it in two lines.
const std::size_t kButtonText = 0x1b8;
void Container(void* panel, int screenWidth) {
    Widened& s = TheState().widened[panel];
    const Rect now = At<Rect>(panel, kExtent);
    void** const array = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelCount);
    if (!array || count < 0 || count > 256) return;
    if (!s.known || !Same(now, s.applied)) {
        s.base = now;
        s.grow = 0;
        s.controls.clear();
        for (int i = 0; i < count; ++i)
            if (array[i]) s.controls.emplace_back(array[i], At<Rect>(array[i], kExtent));
        s.known = true;
        s.applied = now;
    }
    int need = 0;
    for (const char* tag : {"BTN_OK", "BTN_GIVEITEMS", "BTN_CANCEL"}) {
        void* const button = Control(panel, tag);
        if (!button || At<std::uintptr_t>(button, 0) != kButtonVtable) continue;
        Rect native{};
        for (const auto& c : s.controls)
            if (c.first == button) native = c.second;
        void* const wrapper = static_cast<char*>(button) + kButtonText;
        const double natural = NaturalWidth(wrapper);
        const int inset = At<Rect>(button, kExtent).width - At<Rect>(wrapper, kExtent).width;
        const double margin = NaturalLineHeight(wrapper) * 3;
        if (native.width <= 0 || !(natural > 0) || natural > 32767 || inset < 0 || !(margin >= 0) || margin > 32767) continue;
        need = (std::max)(need, static_cast<int>(std::ceil(natural + margin)) + inset - native.width);
    }
    int grow = (std::min)(need, (std::max)(0, screenWidth - s.base.width));
    grow += grow & 1;   // an even growth keeps the centre exact
    const Rect target{s.base.left - grow / 2, s.base.top, s.base.width + grow, s.base.height};
    if (Same(target, now) && Same(target, s.applied)) return;
    Extent(panel, target);
    for (const auto& c : s.controls) {
        Rect r = c.second;
        r.width += grow;
        Extent(c.first, r);
    }
    s.grow = grow;
    s.applied = At<Rect>(panel, kExtent);
}

// The conversation's lower panel (CSWGuiDialogCinematic, dialog.gui) inside the bottom black bar.
// The bars stay as they are; only the text's room inside the bottom one grows: down to the
// screen's bottom less the gap between the picture's lower edge and the panel's top, the same
// space below the text as above it (Windows' Dialogue, the maintainer's rule of 2026-10-18).
// Panel, message and list each reach that limit, never past it and never shrunk: a longer
// subtitle is then fitted to its box (LBL_MESSAGE is a bounded text) and more replies scroll. The
// bar's top is the letterbox recipe's, height less (height + 3) / 6; the Mac's bar is the
// widescreen patch's K7, the same height. A panel not inside that bar is left alone. The panel's
// own height is written in place, not through its SetExtent, which lays its children out again;
// the engine sets it again on every line, so this runs every frame.
void Dialogue(void* panel, int screenHeight) {
    if (At<std::uintptr_t>(panel, 0) != kDialogVtable) return;
    Rect& box = At<Rect>(panel, kExtent);
    const int barTop = screenHeight - (screenHeight + 3) / 6;
    if (box.top < barTop || box.top >= screenHeight || box.height <= 0) return;
    const int limit = screenHeight - (box.top - barTop);
    if (box.top + box.height < limit) box.height = limit - box.top;
    for (const char* tag : {"LBL_MESSAGE", "LB_REPLIES"}) {
        void* const control = Control(panel, tag);
        if (!control) continue;
        Rect r = At<Rect>(control, kExtent);
        const int want = limit - (box.top + r.top);
        if (r.height > 0 && want > r.height && want <= 32767) { r.height = want; Extent(control, r); }
    }
}

// A text centred top to bottom in its box is drawn with its letters' middle on the box's middle,
// not its lines' (Windows' CentreLetters, the maintainer, 2026-10-28: "on all screens please,
// every single one"). Where the letters stand is read from the font's own picture (caption_ink.h);
// the draw places the lines from the string's top at +0x0C when the alignment has 0x10, so that
// top is moved up by the letters' distance below the line's middle: kept while the layout leaves
// it, worked out again when the layout writes another, given back when the text stops being
// centred. Its height, and so the lines the draw shows, are not touched.
void CentreLetters(void* object, StringState& state) {
    int& top = At<int>(object, kStrTop);
    const int from = state.inkMoved && top == state.inkTo ? state.inkFrom : top;
    const auto giveBack = [&] {
        if (state.inkMoved && top == state.inkTo) top = state.inkFrom;
        state.inkMoved = false;
    };
    if ((At<unsigned char>(object, kStrAlign) & 0x38u) != 0x10u) return giveBack();
    // On its art's bar instead of its box's middle, where it has one (ArtCaptions).
    const int target = state.artMiddle != INT_MIN ? state.artMiddle - At<int>(object, kStrHeight) / 2 : from;
    Metrics font;
    const char* text = At<const char*>(object, kStrText);
    if (!text || !Font(object, font)) return giveBack();
    std::uint64_t hash = 1469598103934665603ull;
    for (int i = 0; i < 4096 && text[i]; ++i) hash = (hash ^ static_cast<unsigned char>(text[i])) * 1099511628211ull;
    const float scale = At<float>(object, kStrScale);
    if (font.info != state.inkInfo || text != state.inkText || hash != state.inkHash || scale != state.inkScale || !state.inkRead) {
        state.inkInfo = font.info;
        state.inkText = text;
        state.inkHash = hash;
        state.inkScale = scale;
        state.inkShift = 0;
        const ink::Font* letters = ink::FontFor(font.info);
        state.inkRead = letters != nullptr;
        double middle = 0.5;
        if (letters && Scale(scale) && ink::Middle(*letters, text, &middle)) state.inkShift = ink::Shift(middle, font.height * scale);
    }
    if (state.inkShift == 0 && target == from) return giveBack();
    top = target - state.inkShift;
    state.inkFrom = from;
    state.inkTo = top;
    state.inkMoved = true;
}

// A caption whose control has no art of its own is drawn on the art behind it, which the game's
// screens draw as part of the panel's picture (the Map screen's whole background is lbl_map,
// stretched over the panel; its Party Selection and Return rows are bars in it). The art's bars were
// not drawn on the controls' middles, so a caption centred on its button stood below its bar
// (Windows' ArtCaptions, the maintainer, 2026-10-28: "still not centered on the art"). Its letters
// now go on the bar's middle, found in the picture itself, so a mod's art is followed too.
//
// What is behind a control: the last control before it in the panel's list whose rectangle holds
// its middle and that shows a stretched fill of its own, else the panel's picture (its border at
// +0x70). The parameters are 0x18 into a border: flags at +0x1C (the fill style in the low two
// bits, 2 stretched), the corner, edge and fill's names at +0x1D, +0x2D and +0x3D (Windows' +0x20,
// +0x30, +0x40; CSWGuiBorderParams::SetFillImage, 0x1004a17c2). A control has no art of its own when
// its border has none of the three. Only a stretched picture is read.
//
// The bar: the picture's rows under the middle three fifths of the control, each row's light the
// mean of its pixels' brightest channel; from the row at the control's middle, up and down to the
// first row whose light differs from the next by more than kArtEdge. See BarMiddle.
const int kArtEdge = 10;
const int kArtTopBorder = 2;    // rows of the art's top border counted into a box
const std::size_t kParamsOfLabel = 0xa0, kParamsOfButton = 0xc0, kParamsOfBorder = 0x18;
const std::size_t kParamsFlags = 0x1c, kParamsCorner = 0x1d, kParamsEdge = 0x2d, kParamsFill = 0x3d;

std::string ResRef(const char* at) {
    char name[17] = {};
    std::memcpy(name, at, 16);
    return name;
}
bool OwnArt(const char* params) {
    return !ResRef(params + kParamsCorner).empty() || !ResRef(params + kParamsEdge).empty() || !ResRef(params + kParamsFill).empty();
}
bool ReadPicture(ArtPicture& p, unsigned glName) {
    int width = 0, height = 0;
    unsigned char* const pixels = ink::ReadUploaded(glName, &width, &height);
    if (!pixels) return false;
    p.width = width;
    p.height = height;
    p.light.resize(static_cast<std::size_t>(width) * height);
    for (std::size_t i = 0; i < p.light.size(); ++i) {
        const unsigned char* px = pixels + i * 4;
        p.light[i] = (std::max)(px[0], (std::max)(px[1], px[2]));
    }
    std::free(pixels);
    p.read = true;
    return true;
}
// The OpenGL name a texture reference has once the game has uploaded its picture, or 0 while it
// has not: its target (vtable +0x18), that one's CAurTextureBasic (+0x10), the name at +0x7C.
unsigned UploadedName(void* texture) {
    if (!texture) return 0;
    const auto call = [](void* object, std::size_t slot) {
        return reinterpret_cast<void* (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(At<std::uintptr_t>(object, 0) + slot))(object);
    };
    void* const target = call(texture, 0x18);
    void* const basic = target ? call(target, 0x10) : nullptr;
    return basic ? At<unsigned>(basic, 0x7c) : 0;
}
// A picture read once its texture is uploaded: now if it is, else as the game uploads it
// (PictureUploaded), which ArtCaptions finds on its next frame.
const ArtPicture* Picture(const std::string& name) {
    State& all = TheState();
    for (const ArtPicture& p : all.artPictures)
        if (p.name == name) return p.read ? &p : nullptr;
    if (!CGLGetCurrentContext()) return nullptr;   // a frame with no context (a movie): asked again
    // AurTextureGetReference, Windows' K1_LOAD_TEXTURE_REF.
    void* const texture = reinterpret_cast<void* (*)(const char*, int)>(0x1001f9ff4)(name.c_str(), 0);
    const unsigned glName = UploadedName(texture);
    if (all.artPictures.size() >= 6) all.artPictures.erase(all.artPictures.begin());
    ArtPicture entry;
    entry.name = name;
    all.artPictures.push_back(entry);
    if (!glName) return nullptr;              // waits for its upload
    return ReadPicture(all.artPictures.back(), glName) ? &all.artPictures.back() : nullptr;
}
// The screen row of the middle of the bar `at` is drawn on, in `picture` stretched over `behind`;
// INT_MIN when there is none. OpenGL's row 0 is v = 0, the picture's bottom as drawn. Windows'
// BarMiddle, every number measured there: from the bar's edges out to a thin rim line beyond each,
// and two more of the art's rows above, the top border's own (the maintainer, 2026-10-28).
int BarMiddle(const ArtPicture& p, const Rect& behind, const Rect& at) {
    if (behind.width <= 0 || behind.height <= 0 || at.height <= 0) return INT_MIN;
    const auto rowOf = [&](double y) { return static_cast<int>(std::floor((1.0 - (y - behind.top) / behind.height) * p.height)); };
    const auto screenOf = [&](int row) { return behind.top + (1.0 - (row + 0.5) / p.height) * behind.height; };
    int x0 = static_cast<int>((at.left + at.width * 0.2 - behind.left) * p.width / behind.width);
    int x1 = static_cast<int>((at.left + at.width * 0.8 - behind.left) * p.width / behind.width);
    x0 = (std::max)(0, x0);
    x1 = (std::min)(p.width, x1);
    if (x1 <= x0) return INT_MIN;
    const int step = (std::max)(1, (x1 - x0) / 64);
    const auto light = [&](int row) {
        if (row < 0 || row >= p.height) return -1000;
        int sum = 0, n = 0;
        for (int x = x0; x < x1; x += step, ++n) sum += p.light[static_cast<std::size_t>(row) * p.width + x];
        return n ? sum / n : -1000;
    };
    const int middle = rowOf(at.top + at.height / 2.0);
    // A row of a higher number is higher on screen: row + 1 is above.
    int above = middle, below = middle;
    const int reach = (std::max)(2, rowOf(at.top) - rowOf(at.top + at.height)) * 2;
    while (above - middle < reach && std::abs(light(above + 1) - light(above)) <= kArtEdge) ++above;
    while (middle - below < reach && std::abs(light(below - 1) - light(below)) <= kArtEdge) --below;
    const int rimRows = (std::max)(3, (rowOf(at.top) - rowOf(at.top + at.height)) / 8);
    const auto rim = [&](int edge, int direction) {
        int peak = 1;
        while (peak < rimRows && light(edge + direction * (peak + 1)) >= light(edge + direction * peak)) ++peak;
        const int peakLight = light(edge + direction * peak);
        for (int k = peak + 1; k <= rimRows; ++k)
            if (light(edge + direction * k) < peakLight - 2 * kArtEdge) return edge + direction * peak;
        return edge;
    };
    above = rim(above, 1);
    below = rim(below, -1);
    above += kArtTopBorder;
    const double top = screenOf(above), bottom = screenOf(below);
    const double span = bottom - top, centre = (top + bottom) / 2.0;
    if (span < at.height * 0.5 || span > at.height * 1.5 || centre < at.top || centre > at.top + at.height) return INT_MIN;
    return static_cast<int>(std::lround(centre));
}
void ArtCaptions(void* panel) {
    State& all = TheState();
    void** const array = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelCount);
    if (!array || count <= 0 || count > 4096) return;
    char* const panelBorder = At<char*>(panel, kPanelBorder);
    for (int i = 0; i < count; ++i) {
        void* const control = array[i];
        if (!control) continue;
        const std::uintptr_t table = At<std::uintptr_t>(control, 0);
        std::size_t params = 0, wrapper = 0;
        if (table == kButtonVtable || table == kToggleVtable) { params = kParamsOfButton; wrapper = 0x1b8; }
        else if (table == kLabelVtable) { params = kParamsOfLabel; wrapper = kLabelText; }
        else continue;
        void* const string = At<void*>(control, wrapper + kTextString);
        const auto found = string ? all.strings.find(string) : all.strings.end();
        if (found == all.strings.end()) continue;
        int& artMiddle = found->second.artMiddle;
        artMiddle = INT_MIN;
        if (OwnArt(static_cast<char*>(control) + params)) continue;
        const Rect at = At<Rect>(control, kExtent);
        // What it is drawn on.
        std::string name;
        Rect behind{};
        for (int j = i - 1; j >= 0 && name.empty(); --j) {
            void* const under = array[j];
            if (!under || At<std::uintptr_t>(under, 0) != kLabelVtable) continue;
            const Rect r = At<Rect>(under, kExtent);
            const int mx = at.left + at.width / 2, my = at.top + at.height / 2;
            if (mx < r.left || mx >= r.left + r.width || my < r.top || my >= r.top + r.height) continue;
            char* const p = static_cast<char*>(under) + kParamsOfLabel;
            if ((At<unsigned char>(p, kParamsFlags) & 3u) != 2u || ResRef(p + kParamsFill).empty()) continue;
            name = ResRef(p + kParamsFill);
            behind = r;
        }
        if (name.empty() && text::LooksLikePointer(panelBorder)) {
            char* const p = panelBorder + kParamsOfBorder;
            if ((At<unsigned char>(p, kParamsFlags) & 3u) == 2u) {
                name = ResRef(p + kParamsFill);
                behind = At<Rect>(panel, kExtent);
            }
        }
        if (name.empty()) continue;
        ArtPlace& place = all.artPlaces[control];
        if (place.name != name || !Same(place.behind, behind) || !Same(place.control, at) || !place.read) {
            place.name = name;
            place.behind = behind;
            place.control = at;
            const ArtPicture* const picture = Picture(name);
            place.middle = picture ? BarMiddle(*picture, behind, at) : INT_MIN;
            place.read = picture != nullptr;     // else asked again once it is uploaded
        }
        artMiddle = place.middle;
        // Listed after the control it follows, so that one's is up to date.
        const auto like = all.captionsLike.find(control);
        const auto leader = like == all.captionsLike.end() ? all.artPlaces.end() : all.artPlaces.find(like->second);
        if (leader != all.artPlaces.end()) artMiddle = leader->second.middle;
        // Moved now, before the screen is drawn or a glyph is placed beside it.
        CentreLetters(string, found->second);
    }
}

void Restore(void* object) {
    State& all = TheState();
    if (all.measuring || !object) return;
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return;
    StringState& state = found->second;
    ObserveScale(object, state);
    if (At<float>(object, kStrScale) != state.requested) {
        WriteScale(object, state, state.requested);
        state.restored = true;
    }
}

}  // namespace

void Flow(void* wrapper) { Policy(wrapper, Mode::Flow); }
void Bounded(void* wrapper) { Policy(wrapper, Mode::Bounded); }
void Editable(void* wrapper) { Policy(wrapper, Mode::Editable); }
unsigned Generation() { return TheState().generation; }

int NaturalHeight(void* wrapper) {
    void* object = Internal(wrapper);
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return 0;
    Policy(wrapper, Mode::Flow);
    StringState& state = found->second;
    Metrics font;
    Key key;
    if (!Font(object, font) || !MakeKey(object, state, font, key)) return 0;
    if (!state.cached || !(state.key == key)) {
        state.measured = Measure(object, state.requested, font);
        state.applied = state.requested;
        state.key = key;
        state.cached = true;
    }
    const double height = state.measured.height;
    return state.measured.valid && height > 0 && height <= 32767 ? static_cast<int>(std::ceil(height)) : 0;
}
double NaturalWidth(void* wrapper) {
    void* object = Internal(wrapper);
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return 0;
    ObserveScale(object, found->second);
    Metrics font;
    if (!Font(object, font)) return 0;
    const char* text = At<const char*>(object, kStrText);
    if (!text) return 0;
    const double scale = found->second.requested;
    double pen = 0, right = 0, widest = 0;
    for (unsigned i = 0; i < 262144; ++i) {
        const unsigned char value = static_cast<unsigned char>(text[i]);
        if (!value || value == '\n') {
            widest = (std::max)(widest, right);
            if (!value) return std::isfinite(widest) ? widest : 0;
            pen = right = 0;
            continue;
        }
        const unsigned glyph = static_cast<unsigned>(value) * 3;
        const double width = (font.last[glyph] - font.first[glyph]) * font.textureWidth * 100.0 * scale;
        right = (std::max)(right, pen + width);
        pen += width + font.spacing * 100.0 * scale;
    }
    return 0;
}
double NaturalLineHeight(void* wrapper) {
    void* object = Internal(wrapper);
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return 0;
    ObserveScale(object, found->second);
    Metrics font;
    return Font(object, font) ? font.height * found->second.requested : 0;
}
void FontsChanged() {
    State& all = TheState();
    if (++all.generation == 0) ++all.generation;
    for (auto& item : all.strings) {
        if (At<std::uintptr_t>(item.first, 0) != kStringVtable) continue;
        ObserveScale(item.first, item.second);
        WriteScale(item.first, item.second, item.second.requested);
        item.second.cached = false;
    }
}
void TrackPanel(void* panel, const char* resource) {
    if (!panel || !resource) return;
    State& all = TheState();
    all.panels[panel] = PanelState{resource, {}};
    all.pauses.erase(panel);
}
void TrackControl(void* panel, void* control, const char* tag) {
    if (!panel || !control || !tag) return;
    State& all = TheState();
    const auto found = all.panels.find(panel);
    if (found != all.panels.end()) found->second.controls[control] = tag;
}
void ForgetControl(void* control) {
    State& all = TheState();
    all.artPlaces.erase(control);
    all.captionsLike.erase(control);
    RowsForget(control);
    for (auto& item : TheState().panels) item.second.controls.erase(control);
}
void ForgetPanel(void* panel) {
    State& all = TheState();
    const auto found = all.panels.find(panel);
    if (found != all.panels.end()) {
        for (const auto& item : found->second.controls) {
            all.artPlaces.erase(item.first);
            all.captionsLike.erase(item.first);
            RowsForget(item.first);
        }
        all.panels.erase(found);
    }
    all.pauses.erase(panel);
    all.widened.erase(panel);
}
void* ControlByTag(void* panel, const char* tag) { return Control(panel, tag); }

// The width Container has added to a control of `panel`, 0 if none: only while the control still
// has the width given to it there. For layout.cpp's Relayout, which puts the panel back to its
// file at a change of size: taken for the engine's own addition it was scaled and kept, and the
// buttons came out wider than the panel (Windows' audit GUI-4).
int Widened(void* panel, void* control) {
    State& all = TheState();
    const auto found = all.widened.find(panel);
    if (found == all.widened.end()) return 0;
    for (const auto& c : found->second.controls)
        if (c.first == control) return At<Rect>(control, kExtent).width == c.second.width + found->second.grow ? found->second.grow : 0;
    return 0;
}
void ForgetWidened(void* panel) { TheState().widened.erase(panel); }

// The scale a string is asked to be drawn at, which its +0x58 holds only between a native wrap
// and the next draw (the fit's result in between). For the controller's badges, which measure a
// caption to stand beside it. The string's own scale where it is not one of the fit's.
extern "C" __attribute__((visibility("default"))) float KmrpTextRequestedScale(void* object) {
    if (!object) return 0.0f;
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found == all.strings.end()) return At<float>(object, kStrScale);
    ObserveScale(object, found->second);
    return found->second.requested;
}
void CaptionLike(void* control, void* like) { TheState().captionsLike[control] = like; }

// A picture just uploaded (caption_ink.cpp): one a caption's art waits for is read now.
void PictureUploaded(const char* name, unsigned glName) {
    for (ArtPicture& p : TheState().artPictures)
        if (!p.read && !strcasecmp(p.name.c_str(), name)) ReadPicture(p, glName);
}

void Frame(void* manager) {
    if (!manager) return;
    State& all = TheState();
    const int width = At<short>(manager, kManagerWidth), height = At<short>(manager, kManagerHeight);
    if (width <= 0 || height <= 0) return;
    if (width != all.lastWidth || height != all.lastHeight) {
        // A font object may keep its address while its metrics change with resolution. Rows and
        // cached strings must remeasure that same object.
        FontsChanged();
        all.pauses.clear();
        all.lastWidth = width;
        all.lastHeight = height;
    }
    RowsViewport(height);
    void* hud = nullptr;
    for (auto& item : all.panels) {
        if (At<void*>(item.first, kPanelManager) != manager) continue;
        if (At<std::uintptr_t>(item.first, 0) == kHudVtable) hud = item.first;
        for (const auto& c : item.second.controls) {
            const auto table = At<std::uintptr_t>(c.first, 0);
            if (table == kListVtable) Rows(c.first);
            else if (table == kEditboxVtable || table == kSaveEditBoxVtable) Editable(static_cast<char*>(c.first) + kEditText);
        }
    }
    if (hud)
        for (auto& item : all.panels)
            if (item.second.resource == "pause" && At<void*>(item.first, kPanelManager) == manager)
                Pause(item.first, hud, width, height);
    // Captions on the art behind them; before the draws that use it.
    for (auto& item : all.panels)
        if (At<void*>(item.first, kPanelManager) == manager) ArtCaptions(item.first);
    for (auto& item : all.panels) {
        if (At<void*>(item.first, kPanelManager) != manager) continue;
        if (item.second.resource == "container") Container(item.first, width);
        else if (item.second.resource == "dialog") Dialogue(item.first, height);
    }
    GrantedFrame(manager);
}

}  // namespace textfit
}  // namespace kmrp

using namespace kmrp::textfit;

// The end of CAurGUIStringInternal's constructor (0x1001bbe49, Windows 0x0045BAC0): rbx the string,
// its scale just stored.
extern "C" __attribute__((visibility("default"))) void KmrpTextStringCreated(void* object) {
    if (!object || At<std::uintptr_t>(object, 0) != kStringVtable) return;
    const float scale = At<float>(object, kStrScale);
    if (Scale(scale)) {
        StringState state;
        state.requested = state.applied = scale;
        TheState().strings[object] = state;
    }
}

// Its destructor's entry (0x1001bbea0, Windows 0x0045BC70): rdi the string.
extern "C" __attribute__((visibility("default"))) void KmrpTextStringDestroyed(void* object) { TheState().strings.erase(object); }

// CSWGuiControl's destructor (0x1004a5510, Windows' KmrpControlDestroyedK1), which every control's
// ends in: rdi the control. Its rows and its place in its panel go with it, and an owner's row
// state cannot outlive it when the memory is used again (Windows' THR-6, handoff item 104).
extern "C" __attribute__((visibility("default"))) void KmrpTextControlDestroyed(void* control) { ForgetControl(control); }

// GetIdealPixelHeight's entry (0x1001bc412, Windows 0x0045B7A0). Asked with -1 once lines exist, it
// answers from the stored line count and the scale at +0x58 and does not wrap; a caller that
// measures without setting the text first would read the fit. Put the request back and lay it out
// once at that scale; the next draw re-applies the fit.
extern "C" __attribute__((visibility("default"))) void KmrpTextIdealHeight(void* object) {
    if (TheState().measuring || !object) return;
    const float before = At<float>(object, kStrScale);
    Restore(object);
    if (At<float>(object, kStrScale) != before) Wrap(object);
}

// WrapStrings' entry (0x1001bc644, Windows 0x0045A2F0): rdi the string. Every native wrap
// (persistent, from SetText or a resize; or GetIdealHeight's trial at a width) lays out and
// measures at the requested scale. The fit belongs to the draw only: the game sizes some boxes from
// the text every frame (the target's name, the action description), and fitting inside its wrap
// shrank the text to the previous frame's box, which then held itself in place (measured on
// Windows, 2026-10-18).
//
// CSWGuiText::SetExtent (0x1004a3d4c) places the string and then rebuilds it, which comes here: its
// letters go where they are drawn now, not at its next draw, so a patch that sets a caption's
// rectangle reads the place it will have.
extern "C" __attribute__((visibility("default"))) void KmrpTextStringWrap(void* object) {
    Restore(object);
    State& all = TheState();
    if (!all.measuring && object) {
        const auto found = all.strings.find(object);
        if (found != all.strings.end()) CentreLetters(object, found->second);
    }
}

// The letters' middle of a string as a share of its line and its line's height, for the controller
// patch's badges (Windows' K1CaptionInk::Letters, which its K1XboxControls.cpp includes): a module of
// its own, it finds this by name. 0 when the font's picture has not been read.
extern "C" __attribute__((visibility("default"))) int KmrpCaptionLetters(void* object, double* middle, int* line) {
    if (!object || !middle || !line || At<std::uintptr_t>(object, 0) != kStringVtable) return 0;
    Metrics font;
    const char* text = At<const char*>(object, kStrText);
    if (!text || !Font(object, font)) return 0;
    const kmrp::ink::Font* const letters = kmrp::ink::FontFor(font.info);
    if (!letters || !kmrp::ink::Middle(*letters, text, middle)) return 0;
    float scale = At<float>(object, kStrScale);
    if (!Scale(scale)) scale = 1.0f;
    const int height = static_cast<int>(font.height * scale + 0.5);
    if (height <= 0) return 0;
    *line = height;
    return 1;
}

// The draw's entry (0x1001bcb04, Windows 0x0045A857): rdi the string, xmm0 the alpha, which the
// hook's wrapper keeps. An outer native wrap runs after our entry callback and rewrites widths:
// this instance's verified final widths go back immediately before drawing, including cache hits,
// without another wrap or a shared-font write.
extern "C" __attribute__((visibility("default"))) void KmrpTextStringDraw(void* object) {
    Apply(object, false);
    State& all = TheState();
    const auto found = all.strings.find(object);
    if (found != all.strings.end()) {
        DrawWidths(object, found->second);
        CentreLetters(object, found->second);
    }
}

// CSWGuiListBox::Draw's entry (0x1004a99d4, Windows 0x0041A3E0): lists may populate after the GUI
// frame; adapt their rows before this first draw as well. rdi the list.
extern "C" __attribute__((visibility("default"))) void KmrpTextListDraw(void* list) { Rows(list); }
