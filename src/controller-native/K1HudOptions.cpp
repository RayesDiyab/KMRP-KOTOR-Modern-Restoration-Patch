// The HUD Size page: a button in Graphics Options above "Text Size and Font" opens a
// page that sizes each HUD element (the maintainer's request, 2026-10-18). Built the
// way K1TextOptions.cpp builds its page: the loaded graphics screen's own controls
// (its title, gamma label and slider, shadows checkbox, Default and Back), placed from
// the live screen's rectangles, so it follows every skin and resolution.
//
// Under the title two tabs, "Mouse & Keyboard" (the PC HUD) and "Controller" (the
// Xbox-style HUD), kept apart (the maintainer, 2026-10-18; tabs since 2026-10-19, with a
// button between Default and Close that shows the other tab, X with the pad). Left:
// "Link HUD Sizes" (on by default; it moves the sliders of one HUD together), and under
// it one row per element of the tab's HUD, its caption and its slider side by side, 25%
// to 100% with 50% the HUD as it is today (counted as the text sliders count): the mouse
// and keyboard HUD's menu buttons, minimap, action bar, portraits, attack buttons and
// Disengage button; the controller HUD's action menu, party switch, minimap, top left
// bar and Disengage button (bottom centre). The two HUDs keep separate sizes. Right, and
// nothing else there: a preview, the screen in miniature
// inside the description box (less its scrollbar's strip, which the box's art does not
// cover: the first build drew past the frame at 3440x1440). It shows the mouse and
// keyboard HUD placed by the code that places it in the game (K1PcHudLayout.h, since
// 2026-10-18; until then from the layout file KMRP loads), or, while the controller HUD
// is chosen, the Xbox-style HUD, placed from the table that HUD is placed from
// (K1XboxHudLayout.inc, with K1XboxHud.cpp's Placed arithmetic).
// Each element is scaled about its screen corner as its slider says; the element whose
// slider has the focus is drawn at full strength, the others dimmed.
//
// Saved in swkotor.ini, section [KMRP HUD Size] ([KMRP Text]'s HudSize is the HUD text
// slider; the first build's [KMRP HUD] counted 100 for today and is not read). This page
// only chooses the sizes; each HUD applies them: the mouse and keyboard HUD in this
// module (K1PcHud.cpp), the Xbox-style HUD in the controller patch's (K1XboxHud.cpp,
// which reads the same section).
#include "K1HudOptions.h"
#include "K1HudOptionsPolicy.h"
#include "K1OptionsPad.h"
#include "K1PcHudLayout.h"
#include "K1TextOptions.h"
#include "K1TextOptionsPolicy.h"
#include "K1RuntimeLayout.h"
#include "K1SliderGrip.h"
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <map>
#include <string>
#include <vector>


namespace {
using namespace KmrpHudOptions;
template<class T> T& At(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p) + n); }
template<class T> T Fn(std::uintptr_t n) { return reinterpret_cast<T>(n); }
void** Vtable(void* p) { return reinterpret_cast<void**>(At<std::uintptr_t>(p, 0)); }
using Simple = void(__thiscall*)(void*);
using Ctor = void*(__thiscall*)(void*);
using New = void*(__cdecl*)(unsigned);
using Delete = void(__cdecl*)(void*);
using Event = void(__thiscall*)(void*, int, void*, void*);
using Focus = void(__thiscall*)(void*, void*, int);
using Exists = int(__thiscall*)(void*, void*);
using SetExtentFn = void(__thiscall*)(void*, const Rect*);
constexpr std::uintptr_t GraphicsTable = 0x7586F8, ButtonTable = 0x73E658;
// A label's border parameters (+0x70): its fill texture through 0x00414C00, its alpha
// at +0x0C and its fill style in the low two bits at +0x1C (2 stretches; K1TextRows.cpp).
constexpr unsigned kLabelParams = 0x70, kParamsAlpha = 0x0C, kParamsFlags = 0x1C;
constexpr unsigned kParamsColour = 0x10;   // three floats, the fill's tint (K1XboxHud.cpp draws its strip so)
// The preview's screen: a calm cool slate, #3A424E, under the HUD's pieces. On black the
// HUD's art (dark navy fills, cyan lines) disappeared once dimmed (the maintainer,
// 2026-10-18: "you can't see the unhighlighted things very well. Put a neutral,
// good-looking color as background"). A grey with a little of the GUI's blue in it, as
// dark as a typical scene behind the HUD: the cyan lines stand about 3.4 to 1 against
// it, and the navy fills still read as shapes. The pieces not being sized are drawn at
// half strength on it (they were at 35% on black).
constexpr float kBackdrop[3] = {58 / 255.0f, 66 / 255.0f, 78 / 255.0f};
constexpr float kDimmed = 0.5f, kEdges = 0.3f;

const wchar_t* const* const keys = IniKeys;
// Each HUD's own sliders are shown on their own (the choice at the top says which HUD),
// so the captions need not repeat its name.
const char* const captions[ElementCount] = {
    "Menu Buttons", "Minimap", "Action Bar", "Portraits", "Attack Buttons", "Disengage Button",
    "Action Menu", "Party Switch", "Minimap", "Top Left Bar", "Disengage"};
const char* const hudNames[2] = {"Mouse & Keyboard", "Controller"};
// The Xbox-style HUD's table, with the types it is written in (as K1XboxHud.cpp
// declares them) and K1XboxHud.cpp's Placed arithmetic for the pieces the preview draws.
namespace xbox {
enum Kind : unsigned char { kLabel, kButton, kToggle, kProgress };
enum Side : unsigned char { kLeft, kRight, kCentre, kRelative };
enum Edge : unsigned char { kTop, kBottom };
enum : unsigned char { kHide = 1, kRow = 2, kSetFont = 4, kParty = 8 };
struct Piece {
    unsigned short offset; Kind kind; Side side; Edge edge; short box[4];
    signed char places; unsigned char flags; const char* fill; const char* hilight; const char* progress;
};
#include "K1XboxHudLayout.inc"
constexpr int kBaseHeight = 480;
int Scale(int value, int height) {
    return value >= 0 ? (2 * value * height + kBaseHeight) / (2 * kBaseHeight)
                      : -((2 * -value * height + kBaseHeight) / (2 * kBaseHeight));
}
Rect Placed(const Piece& piece, int width, int height) {
    const int x = piece.box[0], y = piece.box[1];
    const int w = Scale(piece.box[2], height), h = Scale(piece.box[3], height);
    if (piece.flags & kParty) {
        const double f = kPartyScale / 100.0;
        auto exact = [height](double units) { return static_cast<int>(units * height / kBaseHeight + 0.5); };
        const int pw = exact(piece.box[2] * f), ph = exact(piece.box[3] * f);
        return {width - exact(kLayoutWidth - kOutX - kPartyCorner[0] + (kPartyCorner[0] - x) * f),
                height - exact(kLayoutHeight - kOutY - kPartyCorner[1] + (kPartyCorner[1] - y) * f),
                pw > 0 ? pw : 1, ph > 0 ? ph : 1};
    }
    int left;
    if (piece.side == kLeft) left = Scale(x - kOutX, height);
    else if (piece.side == kRight) left = width - Scale(kLayoutWidth - x - kOutX, height);
    else left = x >= kLayoutWidth / 2 ? width / 2 + Scale(x - kLayoutWidth / 2, height)
                                       : width / 2 - Scale(kLayoutWidth / 2 - x, height);
    const int top = piece.edge == kTop ? Scale(y, height) : height - Scale(kLayoutHeight - y - kOutY, height);
    return {left + piece.places * Scale(kSlotPitch, height), top, w > 0 ? w : 1, h > 0 ? h : 1};
}
}  // namespace xbox

struct Entry { void* button = nullptr; int badged = -1; char family = 0; };
std::map<void*, Entry> entries;
void *pending = nullptr, *current = nullptr, *parent = nullptr, *returnFocus = nullptr;
std::uintptr_t table[27]{};
std::vector<void*> owned;
void* labels[ElementCount]{};
void* sliders[ElementCount]{};
void* linkSizes = nullptr;
void* backdrop = nullptr;   // the preview's screen (kBackdrop)
// The tabs under the title, "Mouse & Keyboard" and "Controller": which HUD's sliders
// and preview show, the one shown with its frame and caption at full strength, the
// other's dimmed (kTabDimmed). Between Default and Close a button naming the other tab,
// which X presses (the maintainer, 2026-10-19). Until then two round choices at the top
// of the right-hand box said which HUD showed, with "Link HUD Sizes" under them; the
// first tabs had a line under the one shown, which ran into its frame's bottom edge.
void* tabs[2]{};
void* otherButton = nullptr;
float tabColour[3]{}, tabFrame[3]{};   // the buttons' own caption and frame colours
constexpr float kTabDimmed = 0.4f;
// A button's normal frame colour: its border's parameters (+0x80) and their colour
// (+0x10, three floats), as K1ControllerLayout.cpp greys its Save button.
constexpr unsigned kButtonFrameColour = 0x80 + 0x10;
// The options checkbox draws its circle (i_checkbox01, 48 x 48 in every set,
// override-common) at the texture's own size against the control's left edge
// (measured at 3440x1440, 2026-10-19: 48 px wide at x 323 for a 1290 x 120 control).
constexpr int kCheckboxCircle = 48;
// Default, the other tab and Close: the pad presses them itself (Y, X, B), so they and
// the tabs are off its focus, and the three wear its glyph while it is in use.
KmrpOptionsPad::Glyph defaultsGlyph, otherGlyph, backGlyph;
void* NativeRoutine(std::uintptr_t address) { return reinterpret_cast<void*>(address); }
// A label of the preview: the element it belongs to (-1: drawn for context, never
// scaled), its rectangle on the screen, and the HUD style it is part of.
struct Shown { void* label; int element; Rect screen; int style; char art[17]; };
constexpr int Both = 2;   // a piece shown with either HUD: the screen's outline
std::vector<Shown> pieces;
Rect groups[ElementCount]{};
Preview preview;
bool initialized = false, dirty = false;
Sizes sizing, requested;
int releasedFrames = 2;
bool blockReopen = false;
std::array<int, ElementCount> displayed{};   // filled with -1 as the page opens
int displayedLinked = -1;
int displayedFocus = -2;
int shownStyle = Pc, displayedStyle = -1;   // the HUD chosen at the top: its sliders and preview
std::array<int, ElementCount> drawn{};

bool ConfirmHeld() {
    using Query = int(__cdecl*)();
    HMODULE controller = GetModuleHandleW(L"kmrp-controller.dll");
    auto query = controller ? reinterpret_cast<Query>(GetProcAddress(controller, "KmrpControllerConfirmHeldK1")) : nullptr;
    return (query && query()) || (GetAsyncKeyState(VK_LBUTTON) & 0x8000) ||
           (GetAsyncKeyState(VK_RETURN) & 0x8000) || (GetAsyncKeyState(VK_SPACE) & 0x8000);
}
bool Armed() { return releasedFrames >= 2; }

bool ConfigPath(wchar_t (&path)[MAX_PATH]) {
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? std::wcsrchr(path, L'\\') : nullptr;
    return slash && !wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"swkotor.ini");
}
void Initialize() {
    if (initialized) return;
    initialized = true;
    wchar_t path[MAX_PATH];
    if (ConfigPath(path)) {
        sizing.linked = false;   // read every value as stored, then apply the link
        for (int i = 0; i < ElementCount; ++i)
            sizing.values[i] = Percent(static_cast<int>(GetPrivateProfileIntW(IniSection, keys[i], Default, path)));
        sizing.linked = GetPrivateProfileIntW(IniSection, L"LinkSizes", 1, path) != 0;
    }
    requested = sizing;
}
bool Save() {
    wchar_t path[MAX_PATH], value[16];
    if (!ConfigPath(path)) return false;
    for (int i = 0; i < ElementCount; ++i) {
        swprintf_s(value, L"%d", sizing.values[i]);
        if (!WritePrivateProfileStringW(IniSection, keys[i], value, path)) return false;
    }
    return WritePrivateProfileStringW(IniSection, L"LinkSizes", sizing.linked ? L"1" : L"0", path) != 0;
}

void Extent(void* control, const Rect& rect) { reinterpret_cast<SetExtentFn>(Vtable(control)[1])(control, &rect); }
void DestroyControl(void* c) { if (c) reinterpret_cast<void*(__thiscall*)(void*, unsigned)>(Vtable(c)[0])(c, 1); }
void Text(void* c, const char* text, bool button = false) {
    void* string[2]{};
    Fn<void(__thiscall*)(void*, const char*)>(0x5E5A90)(string, text);
    Fn<void(__thiscall*)(void*, void*)>(0x415E00)(static_cast<char*>(c) + (button ? 0x16C : 0xE8), string);
    Fn<Simple>(0x5E5C20)(string);
}
bool AddControl(void* panel, void* control) {
    const int count = At<int>(panel, 0x24);
    if (count < 0 || count >= 512) return false;
    At<int>(control, 0x50) = count;
    Fn<void(__thiscall*)(void*, void*)>(0x40B9A0)(panel, control);
    return At<int>(panel, 0x24) == count + 1 && At<void**>(panel, 0x20)[count] == control;
}
void* CloneButton(void* owner, void* prototype) {
    if (!prototype || At<std::uintptr_t>(prototype, 0) != ButtonTable) return nullptr;
    void* c = Fn<New>(0x6FA7E6)(0x1C4);
    if (!c) return nullptr;
    Fn<Ctor>(0x41C0F0)(c);
    const Rect rect = At<Rect>(prototype, 4);
    Fn<void(__thiscall*)(void*, const Rect*, void*)>(0x418D80)(c, &rect, prototype);
    At<unsigned>(c, 0x44) = (At<unsigned>(c, 0x44) & ~0x2Eu) | (At<unsigned>(prototype, 0x44) & 0x2Eu);
    if (!AddControl(owner, c)) { DestroyControl(c); return nullptr; }
    return c;
}
void* Bind(void* panel, const char* tag, unsigned size, unsigned ctor) {
    void* c = Fn<New>(0x6FA7E6)(size);
    if (!c) return nullptr;
    Fn<Ctor>(ctor)(c);
    At<int>(c, 0x50) = -1;
    void* name[2]{};
    Fn<void(__thiscall*)(void*, const char*)>(0x5E5A90)(name, tag);
    Fn<void(__thiscall*)(void*, void*, void*, int)>(0x40B930)(panel, c, name, 0);
    Fn<Simple>(0x5E5C20)(name);
    if (At<int>(c, 0x50) < 0 || !AddControl(panel, c)) { DestroyControl(c); return nullptr; }
    owned.push_back(c);
    return c;
}
void Navigation(void* c, void* up, void* down, void* left = nullptr, void* right = nullptr) {
    At<void*>(c, 0x5C) = up; At<void*>(c, 0x60) = left;
    At<void*>(c, 0x64) = down; At<void*>(c, 0x68) = right;
}
void Close() {
    if (current) At<unsigned>(current, 0x44) = (At<unsigned>(current, 0x44) & ~0x700u) | 0x400u;
}
// A bound control selectable as its live counterpart on the graphics screen is. The
// pad moves only to a control that CSWGuiControl::GetIsSelectable (0x004189D0) accepts:
// bit 8 of its flags (+0x44) and its class's own test. A control bound from the
// template (InitControl, its last argument 0) does not get the bit, so the sliders
// could not be reached with the pad (the maintainer, 2026-10-18). CloneButton copies
// the same bits for the entry button; visibility (bit 2) is left as it is.
void SelectableAs(void* control, void* owner, const char* tag) {
    void* original = KmrpRuntimeControlByTagK1(owner, tag);
    if (!control || !original) return;
    At<unsigned>(control, 0x44) = (At<unsigned>(control, 0x44) & ~0x2Cu) | (At<unsigned>(original, 0x44) & 0x2Cu);
}
void Dirty() { dirty = requested.values != sizing.values || requested.linked != sizing.linked; }
void __fastcall Back(void*, void*, void*) { if (Armed()) Close(); }
void __fastcall OnB(void*, void*, int value) { if (value) Close(); }
void __fastcall Open(void* owner, void*, void*) { if (!current && !pending && !blockReopen) pending = owner; }
// A click is acted on once: the pad's A reaches a handler as it goes down and again as
// it comes up (the mouse only as it comes up), and "Link HUD Sizes" unticked and ticked
// itself again (the maintainer, 2026-10-18). Each handler disarms the page, which is
// armed again after the confirm button has been up for two frames (Armed).
void __fastcall ToggleLink(void*, void*, void*) { if (Armed()) { requested.Link(!requested.linked); Dirty(); releasedFrames = 0; } }
void __fastcall Defaults(void*, void*, void*) { if (Armed()) { requested = Sizes{}; Dirty(); releasedFrames = 0; } }
// A slider's events, as the graphics screen gives Brightness its own
// (CSWGuiOptionsGraphics's constructor, 0x006E2E70, through CSWGuiControl::AddEvent,
// 0x0041AB20): entering and leaving (0x00, 0x01), its four movement events (0x2F, 0x30,
// 0x3F, 0x40) and a click (0x27), and the Default command (0x2A). The controller patch
// takes a control with no events for decoration (the Main Menu's wallpaper rule,
// K1NativeJoystick.cpp), so without them the pad could not reach the sliders while the
// buttons, which have their click, it could (the maintainer, 2026-10-18). The handlers
// are the game's shape: the panel in ecx and one word on the stack, `ret 4`, as
// OnMoveGammaSlider (0x006DED30), OnEnterSlider (0x006E0150) and OnExitSlider
// (0x006DED90) are. The value is read every frame (KmrpHudOptionsFrameK1), so moving
// needs nothing more here, and the page has no description pane to fill on entering.
void __fastcall SliderEvent(void*, void*, void*) {}
void SliderEvents(void* slider, void* panel) {
    const auto add = [slider, panel](int event, void* handler) { Fn<Event>(0x41AB20)(slider, event, panel, handler); };
    for (const int event : {0x00, 0x01, 0x2F, 0x30, 0x3F, 0x40, 0x27}) add(event, reinterpret_cast<void*>(&SliderEvent));
    add(0x2A, reinterpret_cast<void*>(&Defaults));
}
void __fastcall ToggleHud(void*, void*, void*);
// B closes, Y restores the defaults and X shows the other tab, wherever the focus is:
// those buttons are off the pad's focus (the maintainer, 2026-10-19).
void __fastcall Input(void* self, void*, int event, int value) {
    if (value && event == 0x28) { Close(); return; }
    if (event == 0x2A) { if (value) Defaults(nullptr, nullptr, nullptr); return; }
    if (event == 0x29) { if (value) ToggleHud(nullptr, nullptr, nullptr); return; }
    Fn<void(__thiscall*)(void*, int, int)>(0x409E60)(self, event, value);
}
void* __fastcall Destroy(void* self, void*, unsigned flags) {
    void* manager = At<void*>(self, 0x18);
    if (manager && Fn<Exists>(0x40BD70)(manager, self)) Fn<Exists>(0x40C830)(manager, self);
    Fn<Focus>(0x40A630)(self, nullptr, 0);
    auto array = At<void**>(self, 0x20);
    for (int i = 0; array && i < At<int>(self, 0x24); ++i) array[i] = nullptr;
    for (void* c : {tabs[0], tabs[1], otherButton, defaultsGlyph.button, backGlyph.button}) KmrpOptionsPad::SkipFocus(c, false);
    for (void* c : owned) DestroyControl(c);
    owned.clear(); pieces.clear(); linkSizes = tabs[0] = tabs[1] = otherButton = backdrop = nullptr;
    defaultsGlyph = otherGlyph = backGlyph = KmrpOptionsPad::Glyph{};
    for (void*& p : labels) p = nullptr;
    for (void*& p : sliders) p = nullptr;
    Fn<Simple>(0x40CF70)(self);
    current = nullptr;
    if (parent && manager && Fn<Exists>(0x40BD70)(manager, parent)) Fn<Focus>(0x40A630)(parent, returnFocus, 0);
    parent = returnFocus = nullptr;
    blockReopen = true; releasedFrames = 0;
    if (flags & 1) Fn<Delete>(0x6FA390)(self);
    return self;
}

void* defaultsButton = nullptr;
void* backButton = nullptr;
int screenWidth = 0, screenHeight = 0;

// The chosen HUD's rows shown and the other's hidden, its tab at full strength with the
// line under it and the other dimmed, the middle button naming the other tab, and the
// pad's focus rebuilt over what is shown: "Link HUD Sizes", then the sliders under it,
// up and down and round. Left and right move a slider, as on the Text Size page; until
// 2026-10-19 they led to the HUD choice as well, so with a pad a press moved the slider
// one step and then the focus went to the choice (the maintainer). The tabs and the
// three buttons are off the pad's focus (X, Y, B; Input); their links are the keys'.
void ShowHud(int style) {
    shownStyle = style;
    std::vector<void*> shown;
    for (int i = 0; i < ElementCount; ++i) {
        const bool visible = StyleOf(i) == style;
        for (void* c : {labels[i], sliders[i]}) {
            unsigned& flags = At<unsigned>(c, 0x44);
            flags = visible ? (flags | 2u) : (flags & ~2u);
        }
        if (visible) shown.push_back(sliders[i]);
    }
    Navigation(linkSizes, shown.back(), shown.front());
    for (std::size_t i = 0; i < shown.size(); ++i)
        Navigation(shown[i], i ? shown[i - 1] : linkSizes, i + 1 < shown.size() ? shown[i + 1] : linkSizes);
    Navigation(defaultsButton, shown.back(), linkSizes, backButton, otherButton);
    Navigation(otherButton, shown.back(), linkSizes, defaultsButton, backButton);
    Navigation(backButton, shown.back(), linkSizes, otherButton, defaultsButton);
    for (int i = 0; i < 2; ++i) {
        const float strength = i == style ? 1.0f : kTabDimmed;
        float caption[3], frame[3];
        for (int c = 0; c < 3; ++c) { caption[c] = tabColour[c] * strength; frame[c] = tabFrame[c] * strength; }
        Fn<void(__thiscall*)(void*, const float*)>(0x414E10)(static_cast<char*>(tabs[i]) + 0x16C, caption);
        std::memcpy(&At<float>(tabs[i], kButtonFrameColour), frame, sizeof frame);
    }
    Text(otherButton, hudNames[style == Pc ? Xbox : Pc], true);
}
void __fastcall SelectPc(void*, void*, void*) { if (Armed()) { if (shownStyle != Pc) ShowHud(Pc); releasedFrames = 0; } }
void __fastcall SelectXbox(void*, void*, void*) { if (Armed()) { if (shownStyle != Xbox) ShowHud(Xbox); releasedFrames = 0; } }
void __fastcall ToggleHud(void*, void*, void*) { if (Armed()) { ShowHud(shownStyle == Pc ? Xbox : Pc); releasedFrames = 0; } }

// The element whose slider has the focus, or -1.
int FocusedElement() {
    if (!current) return -1;
    void* focus = At<void*>(current, 0x1C);
    for (int i = 0; i < ElementCount; ++i) if (focus && focus == sliders[i]) return i;
    return -1;
}

// Where a piece of the preview stands on the screen at the sizes asked for: `screen` is
// its place at the default size, `e` its element (-1: context, never scaled).
Rect SizedOnScreen(int e, const Rect& screen) {
    const int size = e < 0 ? Default
        : e == PcAttack ? requested.values[e]
        : FittingSize(groups[e], CornerOf(e), requested.values[e], screenWidth, screenHeight);
    Rect r = e < 0 ? screen : ScaleAbout(screen, groups[e], CornerOf(e), size);
    // Kept on the screen: the combat strip spans its width and grows from the
    // middle of the top, so a larger one would reach past both sides.
    const int right = (std::min)(screenWidth, r.left + r.width), bottom = (std::min)(screenHeight, r.top + r.height);
    r.left = (std::max)(0, r.left); r.top = (std::max)(0, r.top);
    r.width = (std::max)(1, right - r.left); r.height = (std::max)(1, bottom - r.top);
    return r;
}

// The preview's pieces of the style shown, where the requested sizes put them; the
// focused element's at full strength, the others dimmed; the other style's hidden.
// Only what changed is written.
void UpdatePreview() {
    const int focus = FocusedElement();
    const bool moved = drawn != requested.values, switched = shownStyle != displayedStyle;
    if (!moved && !switched && focus == displayedFocus) return;
    for (const Shown& piece : pieces) {
        const bool visible = piece.style == shownStyle || piece.style == Both;
        unsigned& flags = At<unsigned>(piece.label, 0x44);
        flags = visible ? (flags | 2u) : (flags & ~2u);
        if (!visible) continue;
        if (moved || switched) Extent(piece.label, preview.Map(SizedOnScreen(piece.element, piece.screen)));
        const bool lit = focus < 0 || focus == piece.element;
        At<float>(piece.label, kLabelParams + kParamsAlpha) =
            piece.label == backdrop ? 1.0f : piece.style == Both ? kEdges : lit ? 1.0f : kDimmed;
    }
    drawn = requested.values; displayedFocus = focus; displayedStyle = shownStyle;
}

void UpdateCaptions() {
    if (!current) return;
    for (int i = 0; i < ElementCount; ++i) if (displayed[i] != requested.values[i]) {
        char caption[64]; sprintf_s(caption, "%s: %d%%", captions[i], requested.values[i]);
        Text(labels[i], caption);
        Fn<void(__thiscall*)(void*, int)>(0x417EE0)(sliders[i], (requested.values[i] - Minimum) / Step);
        displayed[i] = requested.values[i];
    }
    if (displayedLinked != int(requested.linked)) {
        Fn<void(__thiscall*)(void*, unsigned)>(0x685540)(linkSizes, requested.linked);
        displayedLinked = requested.linked;
    }
}

// An element's whole box grows to hold one more of its rectangles.
void Grow(int element, const Rect& r, bool (&seen)[ElementCount]) {
    if (element < 0) return;
    Rect& box = groups[element];
    if (!seen[element]) { box = r; seen[element] = true; return; }
    const int right = (std::max)(box.left + box.width, r.left + r.width), bottom = (std::max)(box.top + box.height, r.top + r.height);
    box.left = (std::min)(box.left, r.left); box.top = (std::min)(box.top, r.top);
    box.width = right - box.left; box.height = bottom - box.top;
}
// A preview label wearing `art`, stretched to whatever size the preview gives it, and
// carrying `text` where the HUD's control shows words; a control with words and no
// picture (Disengage) is its words alone.
void AddShown(void* p, const char* art, int element, const Rect& r, int style, const char* text = "") {
    const bool hasArt = art && art[0], hasText = text && text[0];
    if ((!hasArt && !hasText) || pieces.size() >= 128) return;
    void* label = Bind(p, "LBL_GAMMA", 0x140, 0x41ACD0);
    if (!label) return;
    // Its place in the preview from the start, before its picture: a label made from
    // LBL_GAMMA is that label's size (1290x72 at 3440x1440), and the other style's pieces,
    // hidden, are not placed by UpdatePreview until shown, so the controller patch drew all
    // eleven Xbox-style frames at 1290x72 as the page opened, 0.7 s in all (its log, the
    // maintainer's game, 2026-10-28: "there is lag when entering hud text or hud size").
    Extent(label, preview.Map(r));
    Text(label, text);
    Shown piece{label, element, r, style, {}};
    if (hasArt) {
        // The picture itself is set once the preview is laid out (SetPreviewPictures).
        std::memcpy(piece.art, art, (std::min)(std::strlen(art), sizeof piece.art - 1));
        unsigned& flags = At<unsigned>(label, kLabelParams + kParamsFlags);
        flags = (flags & ~3u) | 2u;   // stretched: the art drawn at the preview's size
    }
    pieces.push_back(piece);
}
// Every piece's picture, once the preview has placed it: the controller patch's drawing for
// the piece's size, all listed in one go (K1OptionsPad.h, SetPicture). Set by name as each
// piece was made, until 2026-10-28, every one showed a missing texture for the page's first
// frame (a flash as HUD Size opened) and was drawn again at its preview size the next.
void SetPreviewPictures() {
    KmrpOptionsPad::Batch(true);
    for (const Shown& piece : pieces)
        if (piece.art[0]) KmrpOptionsPad::SetPicture(static_cast<char*>(piece.label) + kLabelParams, piece.art, &NativeRoutine);
    KmrpOptionsPad::Batch(false);
}
// An image of every picture the page has shown, kept for the session. A border's image is
// made by name when its fill is set (CSWGuiBorderParams::SetFillImage, 0x00414C00, through
// NewCAurGUIImage, 0x0045A260, the swkotor1-reconstruction project) and released when the
// page closes, so the game loaded the preview's textures again as it first drew the page,
// at every opening: that frame took 363 to 427 ms, the page's own making 1 to 3 (the
// maintainer's log, 2026-10-28). One more image of the same name keeps each loaded.
std::map<std::string, void*> keptImages;
// The preview's game textures, loaded while the intro movies play and kept for the session
// (KmrpPreloadHudPagesK1): AurTextureGetReference (0x00423A60) finds or makes a texture by
// name without loading it, CAurTexture::Bind (0x004214B0) loads and uploads it, as the page's
// first drawing did, 363 to 427 ms on its first frame (the maintainer, 2026-10-28: "lets
// preload all these heavy screen while the game plays the intro movies").
std::vector<void*> preloadedTextures;
std::size_t preloadNext = 0;
void KeepImage(const void* control, unsigned params) {
    char name[17] = {};
    std::memcpy(name, static_cast<const char*>(control) + params + 0x40, 16);   // the fill's resref
    if (!name[0] || keptImages.count(name)) return;
    if (void* image = Fn<void*(__cdecl*)(const char*)>(0x45A260)(name)) keptImages[name] = image;
}
// The Xbox-style HUD's element of a piece of its table, or -1 for context.
int XboxElement(const xbox::Piece& x) {
    return XboxElementOf(x.offset, (x.flags & xbox::kParty) != 0, (x.flags & xbox::kRow) != 0,
                         x.side == xbox::kLeft && x.edge == xbox::kBottom);
}
// The PC HUD from its table: every control of its six elements that the table marks
// for the preview and that has a texture, in the file's order (later ones on top);
// BTN_CLEARALL, which shows a word and no picture, as that word over the combat queue's
// frame, as the game draws it. The Xbox-style HUD from its table:
// the action box, its slots and description (bottom left), the party, the minimap's
// frame, the target's bar (top left) and the disengage button and queue (bottom
// centre); not the combat strip across the top. Under both, the screen in slate
// (kBackdrop), with a faint outline, so a corner's growth reads against its edges.
// `add(art, element, rect, style, text)` for each piece, in drawing order; the elements'
// whole boxes (`groups`) found on the way.
template<class Add> void PreviewPieces(int width, int height, Add add) {
    // The screen's edges: four lines two preview pixels thick, faint (whitefill at the
    // alpha of a dimmed piece, set by UpdatePreview), shown with either HUD.
    if (preview.scale > 0) {
        const int t = (std::max)(1, static_cast<int>(2.0 / preview.scale + 0.5));
        const Rect edges[4] = {{0, 0, width, t}, {0, height - t, width, t}, {0, 0, t, height}, {width - t, 0, t, height}};
        // The screen itself first, so every piece is drawn over it.
        add("whitefill", -1, Rect{0, 0, width, height}, Both, "");
        for (const Rect& edge : edges) add("whitefill", -1, edge, Both, "");
    }
    bool seen[ElementCount]{};
    // The mouse and keyboard HUD from the table it is placed from in the game
    // (K1PcHudLayout.h, K1PcHud.cpp), so the preview is that HUD at every size. The
    // target menu, which the game draws at the target, is shown a third of the way down
    // the screen, centred.
    {
        using namespace KmrpPcHud;
        Rect menuBox{};
        bool menuSeen = false;
        for (const PcPiece& piece : kPcPieces)
            if (piece.anchor == kPcMenuSpace) {
                const Rect r = Placed(piece, width, height);
                menuBox = menuSeen ? Union(menuBox, r) : r;
                menuSeen = true;
            }
        const int menuX = width / 2 - (menuBox.left + menuBox.width / 2), menuY = height / 3;
        for (const PcPiece& piece : kPcPieces) {
            if (!(piece.flags & kPreview) || piece.element < 0) continue;
            Rect r = Placed(piece, width, height);
            if (piece.anchor == kPcMenuSpace) { r.left += menuX; r.top += menuY; }
            Grow(piece.element, r, seen);
            if (!std::strcmp(piece.tag, "BTN_CLEARALL")) add("", piece.element, r, Pc, "Disengage");
            else add(piece.fill, piece.element, r, Pc, "");
        }
    }
    for (const xbox::Piece& x : xbox::kPieces) {
        if ((x.flags & xbox::kHide) || x.side == xbox::kRelative) continue;
        const int element = XboxElement(x);
        // The combat strip across the top ("COMBAT MODE engaged. (B) to disengage.") is
        // not drawn: it is not a slider's, shows only in combat, and the maintainer had it
        // taken out of the preview (2026-10-18).
        if (x.flags & xbox::kRow) continue;
        const Rect r = xbox::Placed(x, width, height);
        Grow(element, r, seen);
        // A bar shows its filling; anything else its own art.
        add(x.kind == xbox::kProgress && x.progress ? x.progress : x.fill, element, r, Xbox, "");
    }
}

void MakePreview(void* p, const Rect& area, int width, int height) {
    preview = Preview::Fit(area, width, height);
    screenWidth = width; screenHeight = height;
    PreviewPieces(width, height, [&](const char* art, int element, const Rect& r, int style, const char* text) {
        const size_t before = pieces.size();
        AddShown(p, art, element, r, style, text);
        if (pieces.size() == before) return;
        if (before == 0) {
            backdrop = pieces.back().label;     // the screen in slate (kBackdrop)
            std::memcpy(&At<float>(backdrop, kLabelParams + kParamsColour), kBackdrop, sizeof kBackdrop);
        }
        // Disengage centred in its box, as the game's file has it (ALIGNMENT 18); the label
        // it is made from (LBL_GAMMA) reads from the left. CSWGuiTextParams::SetAlignment,
        // 0x00415F20, `ret 4`.
        if (text && text[0]) Fn<void(__thiscall*)(void*, int)>(0x415F20)(static_cast<char*>(pieces.back().label) + 0xE8, 18);
    });
}

// The left column's places: seven, each the graphics screen's caption height (the link,
// and each HUD's parts on the places after it).
int Places() {
    int most = 0, count[2]{};
    for (int i = 0; i < ElementCount; ++i) most = (std::max)(most, ++count[StyleOf(i)]);
    return most + 1;
}

// The right-hand box of the page, where the preview goes, from Graphics Options' own
// controls (`owner`): inside the frame the player sees round its description list, below
// a line for the caption "Preview". `slot` is that line's height, the left column's place.
Rect PreviewArea(void* owner, int* slot) {
    const auto rect = [owner](const char* tag) { return At<Rect>(KmrpRuntimeControlByTagK1(owner, tag), 4); };
    const Rect label = rect("LBL_GAMMA"), desc = rect("LB_DESC");
    const int bar = At<int>(KmrpRuntimeControlByTagK1(owner, "LB_DESC"), 0x110);
    const bool barKnown = bar > 0 && bar < desc.width / 2;
    *slot = (std::max)(1, (std::min)(label.height, desc.height / Places()));
    // The right-hand box is the preview alone (the maintainer, 2026-10-19: "on the right
    // side it should just be the preview"), inside the frame the player sees. It leaves
    // out the list's scrollbar strip on the right (the bar's width at +0x110), which the
    // frame does not cover (the first build drew past the frame at 3440x1440), and is
    // centred in the frame: centred on the list, the preview stood 18 px right of the
    // frame's middle (the maintainer, 2026-10-18: "the left has a wider gap"); the frame
    // runs to 13 px short of the strip.
    const int margin = (std::max)(2, desc.height / 32);
    Rect area = desc;
    if (barKnown) {
        const int left = desc.left - Round(bar * 23 / 86.0);
        const int right = desc.left + desc.width - bar - Round(bar * 13 / 86.0);
        area.left = left;
        area.width = right - left;
    }
    // A line at the top for its caption, "Preview" (below).
    area.top = desc.top + margin + *slot;
    area.height = desc.top + desc.height - margin - area.top;
    area.left += area.width / 20; area.width -= area.width / 10;
    return area;
}

// The preview's pictures drawn in the background while Graphics Options is up, before HUD
// Size is opened from it: each of the controller patch's pictures the page will set, at the
// size the page gives it as it opens (the other style's pieces at their default size,
// hidden) and with that style shown (at the sizes asked for). Its first opening drew the
// Xbox-style HUD's 16 pieces then, about 170 ms (the maintainer, 2026-10-28: "a small wait
// time on first launch compared to opening after that"). The game textures of the mouse
// and keyboard HUD are loaded while the intro movies play (KmrpPreloadHudPagesK1); these
// cannot be, as their sizes come from Graphics Options' layout. Once per layout and sizes.
void QueuePreviewPictures(void* manager, void* owner) {
    if (current || !owner || !KmrpRuntimeControlByTagK1(owner, "LB_DESC") || !KmrpRuntimeControlByTagK1(owner, "LBL_GAMMA")) return;
    const int width = At<short>(manager, 0x6C), height = At<short>(manager, 0x6E);
    int slot = 0;
    const Rect area = PreviewArea(owner, &slot);
    static Rect queuedArea{};
    static decltype(requested.values) queuedSizes{};
    static int queuedWidth = 0, queuedHeight = 0;
    if (!std::memcmp(&area, &queuedArea, sizeof area) && queuedSizes == requested.values &&
            queuedWidth == width && queuedHeight == height) return;
    queuedArea = area; queuedSizes = requested.values; queuedWidth = width; queuedHeight = height;
    preview = Preview::Fit(area, width, height);
    screenWidth = width; screenHeight = height;
    struct Wanted { std::string art; int element; Rect screen; };
    std::vector<Wanted> wanted;
    PreviewPieces(width, height, [&](const char* art, int element, const Rect& r, int, const char*) {
        if (art && art[0]) wanted.push_back({art, element, r});
    });
    // After every piece is listed: an element's sizes need its whole box (groups).
    for (const Wanted& item : wanted)
        for (const Rect& r : {item.screen, SizedOnScreen(item.element, item.screen)}) {
            const Rect at = preview.Map(r);
            KmrpOptionsPad::QueuePicture(item.art.c_str(), at.width, at.height);
        }
}

void MakeScreen(void* manager, void* owner) {
    const char* required[] = {"LBL_TITLE", "SLI_GAMMA", "LBL_GAMMA", "BTN_DEFAULT", "BTN_BACK", "LB_DESC", "CB_SHADOWS", "BTN_ADVANCED"};
    for (const char* tag : required) if (!KmrpRuntimeControlByTagK1(owner, tag)) return;
    void* p = Fn<New>(0x6FA7E6)(0x64);
    if (!p) return;
    Fn<void*(__thiscall*)(void*, void*)>(0x40B570)(p, manager);
    std::memcpy(table, reinterpret_cast<void*>(0x73E010), sizeof(table));
    table[0] = reinterpret_cast<std::uintptr_t>(&Destroy);
    table[15] = reinterpret_cast<std::uintptr_t>(&Input);
    table[21] = reinterpret_cast<std::uintptr_t>(&OnB);
    At<std::uintptr_t*>(p, 0) = table;
    current = p; parent = owner; returnFocus = At<void*>(owner, 0x1C); owned.clear(); pieces.clear();
    char resref[16] = "optgraphics";
    Fn<void(__thiscall*)(void*, void*)>(0x40A680)(p, resref);
    void* title = Bind(p, "LBL_TITLE", 0x140, 0x41ACD0);
    for (void*& tab : tabs) tab = Bind(p, "BTN_DEFAULT", 0x1C4, 0x41C0F0);
    for (int i = 0; i < ElementCount; ++i) {
        labels[i] = Bind(p, "LBL_GAMMA", 0x140, 0x41ACD0);
        sliders[i] = Bind(p, "SLI_GAMMA", 0x1B8, 0x41BAA0);
        KmrpSliderTakeMouseK1(sliders[i]);   // dragged to the end is the maximum (K1SliderGrip.h)
    }
    linkSizes = Bind(p, "CB_SHADOWS", 0x2B4, 0x6E00D0);
    if (linkSizes) At<int>(linkSizes, 0x1C4) = -1;
    const auto rect = [owner](const char* tag) { return At<Rect>(KmrpRuntimeControlByTagK1(owner, tag), 4); };
    const Rect titleRect = rect("LBL_TITLE"), label = rect("LBL_GAMMA"), track = rect("SLI_GAMMA");
    const Rect defaultsRect = rect("BTN_DEFAULT"), backRect = rect("BTN_BACK"), desc = rect("LB_DESC");
    void* const resolution = KmrpRuntimeControlByTagK1(owner, "BTN_RESOLUTION");
    const int gap = (std::max)(2, track.height / 3);
    // The screen's own art, which the page cannot move: the title's band ends where the
    // title does, and the right-hand box's frame stands round the description list, its
    // top line 19 px above the list and its left 23 px left of it at 3440x1440, for a
    // scrollbar 86 wide (measured in captures, 2026-10-18 and 2026-10-19). The layout
    // scales as one, so the insets are kept as shares of the bar's width.
    const int bar = At<int>(KmrpRuntimeControlByTagK1(owner, "LB_DESC"), 0x110);
    const bool barKnown = bar > 0 && bar < desc.width / 2;
    const int frameTop = desc.top - (barKnown ? Round(bar * 19 / 86.0) : gap);
    // And the background's bands (lbl_optback, stretched over the panel), measured in the
    // maintainer's capture at 3440x1440 (2026-10-19), kept as shares of the panel: the
    // title's band from x 609 to 2828, 59 px tall (y 120 to 179); the tray under the
    // buttons, its straight bottom line from x 612 to 2912 at y 1311, its ends rising
    // to y 1221.
    const Rect panel = At<Rect>(owner, 4);
    const auto artX = [&](int x) { return panel.left + Round(x * panel.width / 3440.0); };
    const auto artY = [&](int y) { return panel.top + Round(y * panel.height / 1440.0); };
    const int rowHeight = resolution ? At<Rect>(resolution, 4).height : label.height;
    // The tabs, a pair of the buttons' frames side by side, as wide together as the title's
    // band and as tall as it (the maintainer, 2026-10-19: "as big as that HUD size above
    // artwork"), a fifth of their height apart, in the gap between the title and the box's
    // frame. The first tabs were each Default's size and ran into the frame; the second,
    // three quarters of Default's width, were smaller than the band (the maintainer's
    // captures, 2026-10-19).
    const int band = frameTop - (titleRect.top + titleRect.height);
    const int bandLeft = artX(609), bandRight = artX(2828);
    const int tabHeight = (std::max)(1, (std::min)(artY(179) - artY(120), band - 2));
    const int tabGap = (std::max)(2, tabHeight / 5);
    const int tabWidth = (std::max)(1, (bandRight - bandLeft - tabGap) / 2);
    const int tabsTop = titleRect.top + titleRect.height + (band - tabHeight) / 2;
    const Rect tabRects[2] = {{bandLeft, tabsTop, tabWidth, tabHeight},
                              {bandRight - tabWidth, tabsTop, tabWidth, tabHeight}};
    int slot = 0;
    const Rect area = PreviewArea(owner, &slot);
    MakePreview(p, area, At<short>(manager, 0x6C), At<short>(manager, 0x6E));
    void* previewCaption = Bind(p, "LBL_GAMMA", 0x140, 0x41ACD0);
    void* defaults = Bind(p, "BTN_DEFAULT", 0x1C4, 0x41C0F0);
    void* other = Bind(p, "BTN_DEFAULT", 0x1C4, 0x41C0F0);
    void* back = Bind(p, "BTN_BACK", 0x1C4, 0x41C0F0);
    // The pad's Y, X and B beside the three buttons' captions (K1OptionsPad.h).
    void* marks[3];
    for (void*& mark : marks) mark = Bind(p, "LBL_GAMMA", 0x140, 0x41ACD0);
    Fn<Simple>(0x40B8F0)(p);
    bool complete = title && tabs[0] && tabs[1] && linkSizes && defaults && other && back &&
                    marks[0] && marks[1] && marks[2] && previewCaption;
    for (int i = 0; i < ElementCount; ++i) complete = complete && labels[i] && sliders[i];
    if (!complete) { Destroy(p, nullptr, 1); return; }
    defaultsButton = defaults; backButton = back; otherButton = other;
    // The sliders get the bit outright: Brightness itself lacks it on the graphics
    // screen, where the controller patch reaches it through that screen's own table,
    // so copying it gave nothing; the slider class's own test (0x00641DB0) says yes.
    for (void* slider : sliders) { SelectableAs(slider, owner, "SLI_GAMMA"); At<unsigned>(slider, 0x44) |= 8u; SliderEvents(slider, p); }
    SelectableAs(linkSizes, owner, "CB_SHADOWS");
    for (void* button : {tabs[0], tabs[1], defaults, other}) SelectableAs(button, owner, "BTN_DEFAULT");
    SelectableAs(back, owner, "BTN_BACK");
    Extent(p, At<Rect>(owner, 4));
    Extent(title, titleRect);
    for (int i = 0; i < 2; ++i) Extent(tabs[i], tabRects[i]);
    // Default, the other tab and Close, one width, spread evenly along the tray's bottom
    // line, two gaps apart, a resolution button's height, in the middle of the tray: as far
    // below its ends' tops as above its bottom line (the maintainer, 2026-10-19: "same
    // spacing between the top of the button and the bottom of the button compared to the
    // artwork behind it"). The first build kept Default and Close where the graphics
    // screen has them, each 785 wide at 3440x1440, with a third of that width between
    // them: the frames overlapped, and the buttons stood on the tray's line (the
    // maintainer's captures). Close keeps the graphics screen's Back as its template.
    {
        const int trayLeft = artX(612), trayRight = artX(2912), trayTop = artY(1221), trayBottom = artY(1311);
        const int buttonGap = 2 * gap;
        const int buttonWidth = (std::max)(1, (trayRight - trayLeft - 2 * buttonGap) / 3);
        const int buttonHeight = (std::max)(1, (std::min)((std::min)(defaultsRect.height, backRect.height), rowHeight));
        const int buttonTop = trayTop + (trayBottom - trayTop - buttonHeight) / 2;
        void* const row[3] = {defaults, other, back};
        for (int i = 0; i < 3; ++i)
            Extent(row[i], {trayLeft + i * (buttonWidth + buttonGap), buttonTop, buttonWidth, buttonHeight});
    }
    // The left column, level with the right-hand box: seven places evenly apart, the
    // first with the link's circle at the frame's top line (the maintainer, 2026-10-19:
    // the border "as tall as the top of link HUD sizes"), the last ending at the list's
    // bottom: "Link HUD Sizes", then the six parts of the mouse and keyboard HUD (the
    // controller HUD's five take the first five). A part's row is its caption on the left
    // and its slider beside it (the maintainer, 2026-10-19: "make the slider smaller, have
    // link HUD sizes above them"). Until then the column ran from under the first tabs to
    // above Default, its link 120 px tall. Each HUD's rows take the same places, the
    // other HUD's being hidden.
    const int places = Places();
    const int firstTop = frameTop - (slot - kCheckboxCircle) / 2;
    const int lastTop = desc.top + desc.height - slot;
    const auto placeTop = [&](int k) { return firstTop + k * (lastTop - firstTop) / (places - 1); };
    Extent(linkSizes, {label.left, placeTop(0), label.width, slot});
    // Its caption read from the left beside its circle, as the parts' captions are; the
    // checkbox centres it across the whole control otherwise (as Shadows and Grass on the
    // graphics screen are), which left it floating in the middle of the column.
    // CSWGuiTextParams::SetAlignment (0x00415F20, 17: left, middle line) and
    // CSWGuiText::SetExtent (0x00416280) of the checkbox's text (+0x16C, +0x154, as a
    // button's).
    Fn<void(__thiscall*)(void*, int)>(0x415F20)(static_cast<char*>(linkSizes) + 0x16C, 17);
    {
        const Rect caption{label.left + kCheckboxCircle + gap, placeTop(0), label.width - kCheckboxCircle - gap, slot};
        Fn<void(__thiscall*)(void*, const Rect*)>(0x416280)(static_cast<char*>(linkSizes) + 0x154, &caption);
    }
    // The captions as wide as the widest of them at 100% ("Disengage Button: 100%"), at
    // the text size in use, and each slider from there to the column's edge. Until
    // 2026-10-19 the captions had 55% of the column and the sliders stood far from them
    // (the maintainer: "horizontally longer, so it doesn't have as much dead space").
    int widest = 0;
    for (int i = 0; i < ElementCount; ++i) {
        Extent(labels[i], {label.left, 0, label.width, slot});
        char probe[64];
        sprintf_s(probe, "%s: 100%%", captions[i]);
        Text(labels[i], probe);
        Rect measured{};
        Fn<void(__thiscall*)(void*, Rect*)>(0x414F10)(static_cast<char*>(labels[i]) + 0xD0, &measured);
        widest = (std::max)(widest, measured.width);
    }
    const int captionWidth = (std::max)(label.width / 4, (std::min)(label.width / 2, widest + gap));
    const int sliderLeft = label.left + captionWidth + gap;
    const int sliderWidth = label.left + label.width - sliderLeft;
    const int sliderHeight = (std::min)(track.height, slot);
    int row[2]{};
    for (int i = 0; i < ElementCount; ++i) {
        const int top = placeTop(1 + row[StyleOf(i)]++);
        Extent(labels[i], {label.left, top, captionWidth, slot});
        // Read from the left, in the middle of its row (CSWGuiTextParams::SetAlignment,
        // 0x00415F20, `ret 4`; 1 left, 16 the middle line).
        Fn<void(__thiscall*)(void*, int)>(0x415F20)(static_cast<char*>(labels[i]) + 0xE8, 17);
        Extent(sliders[i], {sliderLeft, top + (slot - sliderHeight) / 2, sliderWidth, sliderHeight});
        Fn<void(__thiscall*)(void*, int)>(0x417EC0)(sliders[i], SliderMaximum);
    }
    // "Preview" over the miniature screen, centred on it, in the line kept above it (the
    // maintainer, 2026-10-19).
    Extent(previewCaption, {preview.left, preview.top - slot, preview.width, slot});
    Fn<void(__thiscall*)(void*, int)>(0x415F20)(static_cast<char*>(previewCaption) + 0xE8, 18);
    Text(previewCaption, "Preview");
    Text(linkSizes, "Link HUD Sizes", true);
    for (int i = 0; i < 2; ++i) Text(tabs[i], hudNames[i], true);
    Text(title, "HUD Size");
    // The tabs' colours at full strength: the buttons' own caption and frame colours.
    std::memcpy(tabColour, &At<float>(tabs[0], 0x16C + 0x1C), sizeof tabColour);
    std::memcpy(tabFrame, &At<float>(tabs[0], kButtonFrameColour), sizeof tabFrame);
    for (void* mark : marks) { Text(mark, ""); At<unsigned>(mark, 0x44) &= ~2u; }
    defaultsGlyph = KmrpOptionsPad::Glyph{}; defaultsGlyph.label = marks[0]; defaultsGlyph.button = defaults; defaultsGlyph.code = 'y';
    otherGlyph = KmrpOptionsPad::Glyph{}; otherGlyph.label = marks[1]; otherGlyph.button = other; otherGlyph.code = 'x';
    backGlyph = KmrpOptionsPad::Glyph{}; backGlyph.label = marks[2]; backGlyph.button = back; backGlyph.code = 'b';
    // Default and Close on the pixels of Graphics Options' own Y and B (K1OptionsPad.h);
    // the other tab's X has no counterpart there and stands beside its caption.
    defaultsGlyph.badge = "kmrpy_optgfxdef"; backGlyph.badge = "kmrpb_optgfx";
    for (void* button : {tabs[0], tabs[1], defaults, other, back}) KmrpOptionsPad::SkipFocus(button, true);
    Fn<Event>(0x41AB20)(linkSizes, 0x27, p, reinterpret_cast<void*>(&ToggleLink));
    Fn<Event>(0x41AB20)(tabs[Pc], 0x27, p, reinterpret_cast<void*>(&SelectPc));
    Fn<Event>(0x41AB20)(tabs[Xbox], 0x27, p, reinterpret_cast<void*>(&SelectXbox));
    Fn<Event>(0x41AB20)(other, 0x27, p, reinterpret_cast<void*>(&ToggleHud));
    Fn<Event>(0x41AB20)(defaults, 0x27, p, reinterpret_cast<void*>(&Defaults));
    Fn<Event>(0x41AB20)(back, 0x27, p, reinterpret_cast<void*>(&Back));
    displayed.fill(-1); drawn.fill(-1); displayedLinked = -1; displayedFocus = -2; displayedStyle = -1;
    ShowHud(Pc);
    // The page opens on "Link HUD Sizes", as the Text Size page on its link.
    Fn<Focus>(0x40A630)(p, linkSizes, 0);
    releasedFrames = 0; UpdateCaptions(); UpdatePreview();
    SetPreviewPictures();
    // The pad's Y, X and B before the page is shown, not on its next frame: they popped
    // in after it (the maintainer, 2026-10-28).
    {
        const bool pad = KmrpOptionsPad::PadInUse();
        const char family = KmrpOptionsPad::Family();
        KmrpOptionsPad::Batch(true);
        for (KmrpOptionsPad::Glyph* glyph : {&defaultsGlyph, &otherGlyph, &backGlyph})
            KmrpOptionsPad::Update(*glyph, pad, family, &NativeRoutine);
        KmrpOptionsPad::Batch(false);
    }
    for (const Shown& piece : pieces) if (piece.art[0]) KeepImage(piece.label, kLabelParams);
    for (KmrpOptionsPad::Glyph* glyph : {&defaultsGlyph, &otherGlyph, &backGlyph})
        if (glyph->label) KeepImage(glyph->label, kLabelParams);
    Fn<void(__thiscall*)(void*, void*, int, int)>(0x40BC70)(manager, p, 3, 1);
}

// The entry button, above "Text Size and Font" (which sits above Advanced Options).
void UpdateEntry(void* owner, Entry& e) {
    void* text = KmrpTextOptionsEntryK1(owner);
    if (!text || At<std::uintptr_t>(text, 0) != ButtonTable) return;
    if (!e.button) {
        e.button = CloneButton(owner, text);
        if (!e.button) return;
        Text(e.button, "HUD Size", true);
        Fn<Event>(0x41AB20)(e.button, 0x27, owner, reinterpret_cast<void*>(&Open));
    }
    const KmrpTextOptions::Rect place = KmrpTextOptions::Entry(At<KmrpTextOptions::Rect>(text, 4));
    const Rect wanted{place.left, place.top, place.width, place.height};
    if (std::memcmp(&At<Rect>(e.button, 4), &wanted, sizeof wanted)) Extent(e.button, wanted);
    At<unsigned>(e.button, 0x44) = (At<unsigned>(e.button, 0x44) & ~4u) | (At<unsigned>(text, 0x44) & 4u);
    void* above = At<void*>(text, 0x5C);
    if (above != e.button) {
        Navigation(e.button, above, text, At<void*>(text, 0x60), At<void*>(text, 0x68));
        At<void*>(text, 0x5C) = e.button;
        if (above && above != text && At<void*>(above, 0x64) == text) At<void*>(above, 0x64) = e.button;
    }
}
// The entry's A, as Advanced Options' below it has, while the entry has its screen's
// focus, the pad is in use and neither KMRP page is open over the screen
// (K1OptionsPad.h; the maintainer, 2026-10-19). Painted only on a change.
void EntryBadge(void* owner, Entry& e, bool pad, char family) {
    if (!e.button) return;
    const bool want = pad && !current && !KmrpTextOptionsOpenK1() && At<void*>(owner, 0x1C) == e.button;
    if (int(want) == e.badged && (!want || family == e.family)) return;
    KmrpOptionsPad::EntryBadge(e.button, want);
    e.badged = want; e.family = family;
}
}  // namespace

bool KmrpHudOptionsOpenK1() { return current != nullptr; }

// For the controller patch's movie frame, which holds the movie site beside KMRP
// (NativeMovieFrameK1, K1NativeJoystick.cpp); KMRP's own frame calls the preload itself.
extern "C" void __cdecl KmrpMovieFrameK1() { KmrpPreloadHudPagesK1(); }

// Two textures a movie frame, so a movie does not stall: every texture the preview's mouse
// and keyboard HUD shows (the pieces MakePreview draws), and the preview's screen. The
// Xbox-style HUD's pictures are the controller patch's, drawn for the preview's sizes when
// the page is laid out, and are not among them.
void KmrpPreloadHudPagesK1()
{
    using namespace KmrpPcHud;
    constexpr std::size_t kPerFrame = 2;
    const std::size_t count = sizeof kPcPieces / sizeof kPcPieces[0];
    using Queue = void(__cdecl*)(const char*);
    HMODULE controller = GetModuleHandleW(L"kmrp-controller.dll");
    Queue queue = controller ? reinterpret_cast<Queue>(GetProcAddress(controller, "KmrpQueueTexturePreloadK1")) : nullptr;
    for (std::size_t done = 0; done < kPerFrame && preloadNext <= count; ++preloadNext) {
        const char* name = preloadNext == count ? "whitefill" : kPcPieces[preloadNext].fill;
        if (preloadNext < count) {
            const PcPiece& piece = kPcPieces[preloadNext];
            if (!(piece.flags & kPreview) || piece.element < 0 || !name || !name[0]) continue;
        }
        static std::vector<std::string> loaded;
        bool seen = false;
        for (const std::string& known : loaded) seen = seen || known == name;
        if (seen) continue;
        loaded.push_back(name);
        if (queue) { queue(name); ++done; continue; }
        void* texture = Fn<void*(__cdecl*)(const char*, int)>(0x423A60)(name, 0);
        if (!texture) continue;
        Fn<void(__thiscall*)(void*)>(0x4214B0)(texture);
        preloadedTextures.push_back(texture);
        ++done;
    }
}

int KmrpHudSizePercentK1(int element) {
    Initialize();
    return element >= 0 && element < ElementCount ? sizing.values[element] : Default;
}

void KmrpHudOptionsDestroyedK1(void* panel) {
    const auto found = entries.find(panel);
    if (found != entries.end()) {
        void* button = found->second.button;
        void** array = At<void**>(panel, 0x20);
        for (int i = 0; array && i < At<int>(panel, 0x24); ++i) if (array[i] == button) array[i] = nullptr;
        entries.erase(found); DestroyControl(button);
    }
    if (pending == panel) pending = nullptr;
    if (parent == panel) { parent = returnFocus = nullptr; Close(); }
}

void KmrpHudOptionsFrameK1(void* manager) {
    if (!manager) return;
    Initialize();
    if (!Armed()) {
        if (ConfirmHeld()) releasedFrames = 0;
        else ++releasedFrames;
    }
    if (blockReopen && Armed()) blockReopen = false;
    const bool pad = KmrpOptionsPad::PadInUse();
    const char family = KmrpOptionsPad::Family();
    for (void* p : KmrpRuntimePanelsK1("optgraphics"))
        if (At<std::uintptr_t>(p, 0) == GraphicsTable) {
            UpdateEntry(p, entries[p]); EntryBadge(p, entries[p], pad, family);
            QueuePreviewPictures(manager, p);   // drawn ahead, while Graphics Options is up
        }
    if (current) {
        KmrpOptionsPad::Batch(true);
        for (KmrpOptionsPad::Glyph* glyph : {&defaultsGlyph, &otherGlyph, &backGlyph})
            KmrpOptionsPad::Update(*glyph, pad, family, &NativeRoutine);
        KmrpOptionsPad::Batch(false);
    }
    if (pending) {
        void* owner = pending; pending = nullptr;
        if (!current && Fn<Exists>(0x40BD70)(manager, owner)) MakeScreen(manager, owner);
    }
    if (current && sliders[0] && !dirty) {
        for (int i = 0; i < ElementCount; ++i) {
            const int moved = Minimum + (std::max)(0, (std::min)(SliderMaximum, At<int>(sliders[i], 0x74))) * Step;
            if (moved != requested.values[i]) { requested.Set(i, moved); Dirty(); break; }
        }
    }
    if (dirty) {
        sizing = requested; dirty = false;
        Save();
        UpdateCaptions();
    }
    if (current) UpdatePreview();
}
