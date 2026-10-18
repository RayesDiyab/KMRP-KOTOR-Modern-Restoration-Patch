// The HUD Size page: a button in Graphics Options above "Text Size and Font" opens a
// page that sizes each HUD element (the maintainer's request, 2026-10-18). Built the
// way K1TextOptions.cpp builds its page: the loaded graphics screen's own controls
// (its title, gamma label and slider, shadows checkbox, Default and Back), placed from
// the live screen's rectangles, so it follows every skin and resolution.
//
// Left, at the top, a choice of HUD: "Mouse & Keyboard HUD" (the PC HUD) or
// "Controller HUD" (the Xbox-style HUD), kept apart (the maintainer, 2026-10-18).
// Under it one row per element of that HUD, its caption and its slider side by side,
// 25% to 250% with 50% the HUD as it is today (counted as the text sliders count): the
// mouse and keyboard HUD's menu buttons, minimap, action bar, portraits, attack buttons
// and Disengage button; the controller HUD's action menu, party switch, minimap, top
// left bar and Disengage button (bottom centre). The two HUDs keep separate sizes; "Link HUD Sizes" (on
// by default) moves the sliders of one HUD together. Right: a preview, the screen in miniature
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
const char* const hudNames[2] = {"Mouse & Keyboard HUD", "Controller HUD"};
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

struct Entry { void* button = nullptr; };
std::map<void*, Entry> entries;
void *pending = nullptr, *current = nullptr, *parent = nullptr, *returnFocus = nullptr;
std::uintptr_t table[27]{};
std::vector<void*> owned;
void* labels[ElementCount]{};
void* sliders[ElementCount]{};
void* linkSizes = nullptr;
void* backdrop = nullptr;   // the preview's screen (kBackdrop)
void* hudChoices[2]{};   // "Mouse & Keyboard HUD" and "Controller HUD": which HUD's sliders show
// A label of the preview: the element it belongs to (-1: drawn for context, never
// scaled), its rectangle on the screen, and the HUD style it is part of.
struct Shown { void* label; int element; Rect screen; int style; };
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
void __fastcall Input(void* self, void*, int event, int value) {
    if (value && event == 0x28) { Close(); return; }
    Fn<void(__thiscall*)(void*, int, int)>(0x409E60)(self, event, value);
}
void* __fastcall Destroy(void* self, void*, unsigned flags) {
    void* manager = At<void*>(self, 0x18);
    if (manager && Fn<Exists>(0x40BD70)(manager, self)) Fn<Exists>(0x40C830)(manager, self);
    Fn<Focus>(0x40A630)(self, nullptr, 0);
    auto array = At<void**>(self, 0x20);
    for (int i = 0; array && i < At<int>(self, 0x24); ++i) array[i] = nullptr;
    for (void* c : owned) DestroyControl(c);
    owned.clear(); pieces.clear(); linkSizes = hudChoices[0] = hudChoices[1] = backdrop = nullptr;
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

// The chosen HUD's rows shown and the other's hidden, and the focus order rebuilt over
// what is shown, by column as the page is laid out: on the left the sliders down to
// Default, on the right the two HUD choices and the link down to Back; left and right
// cross between the columns.
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
    void* const first = shown.front();
    void* const choice = hudChoices[style];
    for (std::size_t i = 0; i < shown.size(); ++i)
        Navigation(shown[i], i ? shown[i - 1] : backButton, i + 1 < shown.size() ? shown[i + 1] : defaultsButton, choice, choice);
    Navigation(hudChoices[Pc], backButton, hudChoices[Xbox], first, first);
    Navigation(hudChoices[Xbox], hudChoices[Pc], linkSizes, first, first);
    Navigation(linkSizes, hudChoices[Xbox], backButton, first, first);
    Navigation(defaultsButton, shown.back(), first, backButton, backButton);
    Navigation(backButton, linkSizes, hudChoices[Pc], defaultsButton, defaultsButton);
    for (int i = 0; i < 2; ++i) Fn<void(__thiscall*)(void*, unsigned)>(0x685540)(hudChoices[i], i == style);
}
void __fastcall SelectPc(void*, void*, void*) { if (Armed()) { if (shownStyle != Pc) ShowHud(Pc); releasedFrames = 0; } }
void __fastcall SelectXbox(void*, void*, void*) { if (Armed()) { if (shownStyle != Xbox) ShowHud(Xbox); releasedFrames = 0; } }

// The element whose slider has the focus, or -1.
int FocusedElement() {
    if (!current) return -1;
    void* focus = At<void*>(current, 0x1C);
    for (int i = 0; i < ElementCount; ++i) if (focus && focus == sliders[i]) return i;
    return -1;
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
        if (moved || switched) {
            const int e = piece.element;
            const int size = e < 0 ? Default
                : e == PcAttack ? requested.values[e]
                : FittingSize(groups[e], CornerOf(e), requested.values[e], screenWidth, screenHeight);
            Rect r = e < 0 ? piece.screen : ScaleAbout(piece.screen, groups[e], CornerOf(e), size);
            // Kept on the screen: the combat strip spans its width and grows from the
            // middle of the top, so a larger one would reach past both sides.
            const int right = (std::min)(screenWidth, r.left + r.width), bottom = (std::min)(screenHeight, r.top + r.height);
            r.left = (std::max)(0, r.left); r.top = (std::max)(0, r.top);
            r.width = (std::max)(1, right - r.left); r.height = (std::max)(1, bottom - r.top);
            Extent(piece.label, preview.Map(r));
        }
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
    Text(label, text);
    if (!hasArt) { pieces.push_back({label, element, r, style}); return; }
    char fill[16]{};
    std::memcpy(fill, art, (std::min)(std::strlen(art), sizeof fill));
    Fn<void(__thiscall*)(void*, const char*, int)>(0x414C00)(static_cast<char*>(label) + kLabelParams, fill, 1);
    unsigned& flags = At<unsigned>(label, kLabelParams + kParamsFlags);
    flags = (flags & ~3u) | 2u;   // stretched: the art drawn at the preview's size
    pieces.push_back({label, element, r, style});
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
void MakePreview(void* p, const Rect& area, int width, int height) {
    preview = Preview::Fit(area, width, height);
    screenWidth = width; screenHeight = height;
    // The screen's edges: four lines two preview pixels thick, faint (whitefill at the
    // alpha of a dimmed piece, set by UpdatePreview), shown with either HUD.
    if (preview.scale > 0) {
        const int t = (std::max)(1, static_cast<int>(2.0 / preview.scale + 0.5));
        const Rect edges[4] = {{0, 0, width, t}, {0, height - t, width, t}, {0, 0, t, height}, {width - t, 0, t, height}};
        // The screen itself first, so every piece is drawn over it.
        AddShown(p, "whitefill", -1, {0, 0, width, height}, Both);
        if (!pieces.empty()) {
            backdrop = pieces.back().label;
            std::memcpy(&At<float>(backdrop, kLabelParams + kParamsColour), kBackdrop, sizeof kBackdrop);
        }
        for (const Rect& edge : edges) AddShown(p, "whitefill", -1, edge, Both);
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
            if (!std::strcmp(piece.tag, "BTN_CLEARALL")) {
                // Centred in its box, as the game's file has it (ALIGNMENT 18); the label
                // it is made from (LBL_GAMMA) reads from the left. CSWGuiTextParams::
                // SetAlignment, 0x00415F20, `ret 4`.
                const size_t before = pieces.size();
                AddShown(p, "", piece.element, r, Pc, "Disengage");
                if (pieces.size() > before)
                    Fn<void(__thiscall*)(void*, int)>(0x415F20)(static_cast<char*>(pieces.back().label) + 0xE8, 18);
            }
            else AddShown(p, piece.fill, piece.element, r, Pc);
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
        AddShown(p, x.kind == xbox::kProgress && x.progress ? x.progress : x.fill, element, r, Xbox);
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
    for (int i = 0; i < ElementCount; ++i) {
        labels[i] = Bind(p, "LBL_GAMMA", 0x140, 0x41ACD0);
        sliders[i] = Bind(p, "SLI_GAMMA", 0x1B8, 0x41BAA0);
        KmrpSliderTakeMouseK1(sliders[i]);   // dragged to the end is the maximum (K1SliderGrip.h)
    }
    linkSizes = Bind(p, "CB_SHADOWS", 0x2B4, 0x6E00D0);
    if (linkSizes) At<int>(linkSizes, 0x1C4) = -1;
    // The two HUD choices: native round option controls with their own toggling off,
    // as the text page's font choices are; the page sets the one chosen.
    for (void*& choice : hudChoices) {
        choice = Bind(p, "CB_SHADOWS", 0x2B4, 0x6E00D0);
        if (choice) At<int>(choice, 0x1C4) = -1;
    }
    const auto rect = [owner](const char* tag) { return At<Rect>(KmrpRuntimeControlByTagK1(owner, tag), 4); };
    // The right-hand box holds the HUD choice and the preview, as the text page's holds
    // its font choice and its samples: the two choices stacked at its top, in the font
    // choices' rows (the box's width less a 32nd each side, a resolution button's
    // height), the preview below them. The preview leaves out the box's scrollbar strip
    // on the right (LB_DESC is a list: the bar's width at +0x110), which its frame does
    // not cover (the first build drew past the frame at 3440x1440).
    const Rect desc = rect("LB_DESC");
    const int choiceGap = (std::max)(2, rect("SLI_GAMMA").height / 3);
    const int margin = (std::max)(2, desc.height / 32);
    const Rect choiceRow{desc.left + desc.width / 32, desc.top + margin, desc.width - desc.width / 16, rect("BTN_RESOLUTION").height};
    Rect area = desc;
    const int bar = At<int>(KmrpRuntimeControlByTagK1(owner, "LB_DESC"), 0x110);
    if (bar > 0 && bar < area.width / 2) {
        // Centred in the frame the player sees, which is the screen's background art and
        // not the list's own rectangle: at 3440x1440 it runs from 23 px left of the list
        // to 13 px short of the scrollbar's strip (bar 86 wide; measured in a capture,
        // 2026-10-18). Centred on the list, the preview stood 18 px right of the
        // frame's middle (the maintainer: "the left has a wider gap"). The layout scales
        // as one, so the two insets are kept as shares of the bar's width.
        const int left = desc.left - Round(bar * 23 / 86.0);
        const int right = desc.left + desc.width - bar - Round(bar * 13 / 86.0);
        area.left = left;
        area.width = right - left;
    }
    // Three rows: the two HUD choices, then "Link HUD Sizes" a little apart from them.
    area.top = choiceRow.top + 3 * (choiceRow.height + choiceGap) + 2 * choiceGap;
    area.height = desc.top + desc.height - margin - area.top;
    area.left += area.width / 20; area.width -= area.width / 10;
    MakePreview(p, area, At<short>(manager, 0x6C), At<short>(manager, 0x6E));
    void* defaults = Bind(p, "BTN_DEFAULT", 0x1C4, 0x41C0F0);
    void* back = Bind(p, "BTN_BACK", 0x1C4, 0x41C0F0);
    Fn<Simple>(0x40B8F0)(p);
    bool complete = title && linkSizes && hudChoices[0] && hudChoices[1] && defaults && back;
    for (int i = 0; i < ElementCount; ++i) complete = complete && labels[i] && sliders[i];
    if (!complete) { Destroy(p, nullptr, 1); return; }
    defaultsButton = defaults; backButton = back;
    // The sliders get the bit outright: Brightness itself lacks it on the graphics
    // screen, where the controller patch reaches it through that screen's own table,
    // so copying it gave nothing; the slider class's own test (0x00641DB0) says yes.
    for (void* slider : sliders) { SelectableAs(slider, owner, "SLI_GAMMA"); At<unsigned>(slider, 0x44) |= 8u; SliderEvents(slider, p); }
    for (void* toggle : {linkSizes, hudChoices[0], hudChoices[1]}) SelectableAs(toggle, owner, "CB_SHADOWS");
    SelectableAs(defaults, owner, "BTN_DEFAULT");
    SelectableAs(back, owner, "BTN_BACK");
    Extent(p, At<Rect>(owner, 4));
    Extent(title, rect("LBL_TITLE"));
    Extent(defaults, rect("BTN_DEFAULT")); Extent(back, rect("BTN_BACK"));
    const Rect label = rect("LBL_GAMMA"), track = rect("SLI_GAMMA");
    const int gap = (std::max)(2, track.height / 3);
    // The right-hand box: the HUD choices, then "Link HUD Sizes" a little apart (above).
    // On the left, as on the graphics screen and the text page, each element's caption
    // above its full-width slider, the chosen HUD's pairs from the top down to Default.
    // A pair is its caption, at the graphics screen's height while the pitch allows,
    // directly above its slider; what is left of the pitch goes between pairs. With the
    // link on the left as well, six pairs left a 36 px caption for a 64 px line at
    // 3440x1440, hence the link's place in the box. Each HUD's pairs take the same
    // places, the other HUD's being hidden.
    for (int i = 0; i < 2; ++i)
        Extent(hudChoices[i], {choiceRow.left, choiceRow.top + i * (choiceRow.height + choiceGap), choiceRow.width, choiceRow.height});
    Extent(linkSizes, {choiceRow.left, choiceRow.top + 2 * (choiceRow.height + choiceGap) + choiceGap, choiceRow.width, choiceRow.height});
    const int bottom = rect("BTN_DEFAULT").top - gap;
    int most = 0, count[2]{};
    for (int i = 0; i < ElementCount; ++i) most = (std::max)(most, ++count[StyleOf(i)]);
    const int pitch = (bottom - label.top) / most;
    const int caption = (std::max)(track.height / 2, (std::min)(label.height, pitch - track.height));
    int row[2]{};
    for (int i = 0; i < ElementCount; ++i) {
        const int top = label.top + row[StyleOf(i)]++ * pitch;
        Extent(labels[i], {label.left, top, label.width, caption});
        Extent(sliders[i], {track.left, top + caption, track.width, track.height});
        Fn<void(__thiscall*)(void*, int)>(0x417EC0)(sliders[i], SliderMaximum);
    }
    Text(linkSizes, "Link HUD Sizes", true);
    for (int i = 0; i < 2; ++i) Text(hudChoices[i], hudNames[i], true);
    Text(title, "HUD Size");
    Fn<Event>(0x41AB20)(linkSizes, 0x27, p, reinterpret_cast<void*>(&ToggleLink));
    Fn<Event>(0x41AB20)(hudChoices[Pc], 0x27, p, reinterpret_cast<void*>(&SelectPc));
    Fn<Event>(0x41AB20)(hudChoices[Xbox], 0x27, p, reinterpret_cast<void*>(&SelectXbox));
    Fn<Event>(0x41AB20)(defaults, 0x27, p, reinterpret_cast<void*>(&Defaults));
    Fn<Event>(0x41AB20)(back, 0x27, p, reinterpret_cast<void*>(&Back));
    displayed.fill(-1); drawn.fill(-1); displayedLinked = -1; displayedFocus = -2; displayedStyle = -1;
    ShowHud(Pc);
    Fn<Focus>(0x40A630)(p, sliders[PcMenu], 0);
    releasedFrames = 0; UpdateCaptions(); UpdatePreview();
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
}  // namespace

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
    for (void* p : KmrpRuntimePanelsK1("optgraphics"))
        if (At<std::uintptr_t>(p, 0) == GraphicsTable) UpdateEntry(p, entries[p]);
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
