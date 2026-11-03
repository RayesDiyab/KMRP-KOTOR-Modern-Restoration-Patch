/*
  KMRP for macOS: the HUD Size page. A button in Graphics Options above "Text Size and Font" opens a
  page that sizes each part of each HUD. The port of src/controller-native/K1HudOptions.cpp, whose
  comments give the reasons for each measure and the maintainer's requests; docs/hud-size-options.md
  describes the page. The rules are Windows' own files, compiled here: K1HudOptionsPolicy.h,
  K1PcHudLayout.h and K1PcHudLayout.inc, so the preview is the HUD. The Xbox-style HUD's table is
  this patch's Mac twin, kmrp-controller/xbox_hud_layout.inc, whose offsets are the Mac's:
  kmrp-layout/hud_sizes.h has the rule that reads them.

  Built as Windows builds it: the loaded graphics screen's own controls (its title, gamma label
  and slider, shadows checkbox, Default and Back), bound from optgraphics again and placed from the
  live screen's rectangles, so it follows every set and resolution. Under the title two tabs, Mouse
  & Keyboard and Controller; left, Link HUD Sizes and a row per part of the tab's HUD; right, the
  preview, the screen in miniature inside the description box. Below, Default, the other tab and
  Close. Saved in swkotor.ini, [KMRP HUD Size] (hud_sizes.h). This page only chooses the sizes;
  each HUD applies them: the mouse and keyboard HUD in this module (pc_hud.cpp), the Xbox-style HUD
  in the controller patch's (xbox_hud.cpp), which reads the same section.

  The engine on the Mac (KOTOR_Exe 1.4.0), Windows' beside it:

      panel, 0x80 bytes (0x64)  +0x08 extent (+0x04), +0x20 manager (+0x18), +0x28 active control
                                (+0x1C), +0x30 controls (+0x20), +0x38 their count (+0x24), +0x5C
                                flags, 16 bits (+0x44)
      control                   +0x08 extent, +0x50 panel (+0x34), +0x58 events, +0x68 flags (+0x44;
                                bit 1 visible, 3 selectable), +0x70 the value of the event being
                                handled, +0x74 id (+0x50)
      navigable control         +0x80 the description's strref (+0x58), then its neighbours: +0x88
                                up, +0x90 left, +0x98 down, +0xA0 right (+0x5C to +0x68), read from
                                CSWGuiNavigable::HandleInputEvent (0x1004A4972)
      label, 0x198 (0x140)      ctor 0x1004A54AA; CSWGuiText +0x110 (+0xD0), its params +0x130
                                (+0xE8); border params +0xA0 (+0x70): alpha +0x0C, colour +0x10,
                                fill style +0x1C, fill's name +0x3D (+0x40)
      button, 0x240 (0x1C4)     ctor 0x1004A5E8E, vtable 0x1005B47B8; CSWGuiText +0x1B8 (+0x154),
                                params +0x1D8 (+0x16C); caption colour at +0x28 of them (+0x1C);
                                border params +0xC0 (+0x80), colour +0x10
      slider, 0x228 (0x1B8)     ctor 0x1004A646E; +0xAC maximum, +0xB0 value (+0x70, +0x74),
                                written directly: Windows' SetMaximum (0x00417EC0) has no Mac
                                function of its own
      options checkbox, 0x358   CSWGuiButtonToggle's ctor 0x1004A5E16, then vtable 0x1005AC6A8, as
                  (0x2B4)       CSWGuiOptionsGraphics' constructor (0x1002CA132) makes it; +0x240
                                the event that flips it (+0x1C4; -1: only this page's handler
                                does), bit 0 of +0x244 its state (Windows' 0x00685540 sets it; here
                                as CSWGuiOptionsGraphics::SetUpOptions, 0x1002CADF0, writes it)
      list                      +0x168 its scrollbar's width (+0x110)
      manager                   +0xA4, +0xA6 the screen (+0x6C, +0x6E); +0x10 bit 0 left button held
      Graphics Options          vtable 0x1005AC1C0 (Windows 0x007586F8); the description's label
                                +0x440 (+0x35C), and 0x1002CB104(panel, strref) fills the box
                                (0x006DEE40)

  Calls: CSWGuiControl::AddEvent 0x1004A4C5A, whose handler is (receiver, control), the SysV
  shape of Windows' `ret 4` handlers; CSWGuiPanel::AddControl 0x10049E5E2 (0x0040B9A0); the button's
  copy of another 0x1004A5AB2 (0x00418D80); CSWGuiTextParams::SetText 0x1004A3714 (0x00415E00),
  SetColor 0x1004A380E (0x00414E10), SetAlignment 0x1004A37A2 (0x00415F20); CSWGuiText::SetExtent
  0x1004A3D4C (0x00416280); NewCAurGUIImage 0x1001BE304 (0x0045A260); AurTextureGetReference
  0x1001F9FF4 (0x00423A60), which FUN_1001942DE calls with (name, 0); CAurTexture::Bind 0x1001F72B0
  (0x004214B0).

  What differs from Windows, all because of the Mac's controller patch, which carries its pictures
  made instead of drawing them at run time: no batch and no queue of pictures, and the glyphs of
  Default and Close stand beside their captions (options_pad.h). Since a handler on the Mac can
  read the value of its event, a press acts and its release does not; Armed stays, for the press
  that opens the page and the one that closes it.

  Nothing here has been seen in the game.
*/
#include "../../../src/controller-native/K1HudOptionsPolicy.h"
#include "../../../src/controller-native/K1PcHudLayout.h"
#include "../kmrp-layout/hud_sizes.h"
#include "../kmrp-layout/slider_grip.h"
#include "assets.h"
#include "hud_options.h"
#include "options_pad.h"
#include "panels.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <map>
#include <new>
#include <string>
#include <vector>

// The Text Size page's entry and whether that page is open (Windows' K1TextOptions.h). Weak, so
// this part links before that page is there, and the page's own definitions, with C names, take
// their place. Without the entry this button stands where that one would, above Advanced Options.
extern "C" __attribute__((weak)) void* KmrpTextOptionsEntryK1(void*) { return nullptr; }
extern "C" __attribute__((weak)) bool KmrpTextOptionsOpenK1() { return false; }
extern "C" void* CGLGetCurrentContext();   // OpenGL, which the module links

namespace {

using namespace KmrpHudOptions;
namespace pad = kmrp::pad;

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}
template <typename F> F Fn(std::uintptr_t address) { return reinterpret_cast<F>(address); }

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}
std::uintptr_t VtableOf(void* object) { return LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

const std::size_t kPanelManager = 0x20, kPanelActive = 0x28, kPanelControls = 0x30, kPanelCount = 0x38;
const std::size_t kPanelFlags = 0x5c, kPanelSize = 0x80;
const std::size_t kExtent = 0x08, kCtlFlags = 0x68, kCtlValue = 0x70, kCtlId = 0x74;
const std::size_t kCtlStrRef = 0x80, kNavUp = 0x88, kNavLeft = 0x90, kNavDown = 0x98, kNavRight = 0xa0;
const std::uint8_t kVisible = 2, kSelectable = 8;
const std::size_t kVtSetExtent = 0x10, kVtDeleting = 0x08;
const std::size_t kLabelSize = 0x198, kButtonSize = 0x240, kSliderSize = 0x228, kCheckboxSize = 0x358;
const std::uintptr_t kLabelCtor = 0x1004a54aaUL, kButtonCtor = 0x1004a5e8eUL, kSliderCtor = 0x1004a646eUL;
const std::uintptr_t kToggleCtor = 0x1004a5e16UL, kCheckboxTable = 0x1005ac6a8UL;
const std::uintptr_t kGraphicsTable = 0x1005ac1c0UL, kButtonTable = 0x1005b47b8UL;
const std::uintptr_t kBasePanelTable = 0x1005b3730UL;
const int kBasePanelSlots = 28;
const std::size_t kLabelText = 0x110, kLabelTextParams = 0x130, kLabelParams = 0xa0;
const std::size_t kParamsAlpha = 0x0c, kParamsColour = 0x10, kParamsFlags = 0x1c, kParamsFill = 0x3d;
const std::size_t kButtonText = 0x1b8, kButtonTextParams = 0x1d8, kTextColour = 0x28;
const std::size_t kButtonFrameColour = 0xc0 + 0x10;
const std::size_t kSliderMaximum = 0xac, kSliderValue = 0xb0;
const std::size_t kCheckboxEvent = 0x240, kCheckboxState = 0x244;
const std::size_t kListBarWidth = 0x168;
const std::size_t kGraphicsDescription = 0x440;
const std::size_t kManagerWidth = 0xa4, kManagerHeight = 0xa6, kManagerButtons = 0x10;
const int kEventEnter = 0x00, kEventLeave = 0x01, kEventA = 0x27, kEventB = 0x28, kEventX = 0x29, kEventY = 0x2a;

using HandlerFn = void (*)(void* receiver, void* control);
using StringFn = void (*)(void* string, const char* text);
using StringFreeFn = void (*)(void* string);
using ExistsFn = int (*)(void* manager, void* panel);
using SetActiveFn = void (*)(void* panel, void* control, int sound);
using InputFn = void (*)(void* panel, int event, int value);
using AddEventFn = void (*)(void* control, int event, void* receiver, void* handler, long adjust);
using AddControlFn = void (*)(void* panel, void* control);
using AlignFn = void (*)(void* params, unsigned char alignment);
using SetValueFn = void (*)(void* slider, int value);

const auto StringCtor = Fn<StringFn>(0x10034cca8UL);
const auto StringDtor = Fn<StringFreeFn>(0x10034cdf2UL);
const auto SetText = Fn<void (*)(void*, void*)>(0x1004a3714UL);
const auto SetColor = Fn<void (*)(void*, const float*)>(0x1004a380eUL);
const auto SetAlignment = Fn<AlignFn>(0x1004a37a2UL);
const auto TextSetExtent = Fn<void (*)(void*, const Rect*)>(0x1004a3d4cUL);
const auto AddEvent = Fn<AddEventFn>(0x1004a4c5aUL);
const auto AddControlTo = Fn<AddControlFn>(0x10049e5e2UL);
const auto CopyButton = Fn<void (*)(void*, const Rect*, void*)>(0x1004a5ab2UL);
const auto InitControl = Fn<void (*)(void*, void*, void*, int)>(0x10049e476UL);
const auto PanelCtor = Fn<void (*)(void*, void*)>(0x10049d7f8UL);
const auto PanelDtor = Fn<void (*)(void*)>(0x10049d8c8UL);
const auto ResRefCtor = Fn<void (*)(void*, const char*)>(0x100367b62UL);
const auto StartLoad = Fn<void (*)(void*, const void*)>(0x10049dfe4UL);
const auto StopLoad = Fn<void (*)(void*)>(0x10049d986UL);
const auto AddPanel = Fn<void (*)(void*, void*, int, int)>(0x10049ecaeUL);
const auto PanelExists = Fn<ExistsFn>(0x10049d9ceUL);
const auto RemovePanel = Fn<ExistsFn>(0x10049da14UL);
const auto SetActive = Fn<SetActiveFn>(0x10049de24UL);
const auto PanelInput = Fn<InputFn>(0x10049dc72UL);
const auto SetSliderValue = Fn<SetValueFn>(0x1004a6920UL);
const auto ShowDescription = Fn<void (*)(void*, std::uint64_t)>(0x1002cb104UL);
const auto NewImage = Fn<void* (*)(const char*)>(0x1001be304UL);
const auto TextureReference = Fn<void* (*)(const char*, int)>(0x1001f9ff4UL);
const auto BindTexture = Fn<void (*)(void*)>(0x1001f72b0UL);

// The preview's screen, its dimmed pieces and its edges, and the tab not shown: Windows' numbers.
const float kBackdrop[3] = {58 / 255.0f, 66 / 255.0f, 78 / 255.0f};
const float kDimmed = 0.5f, kEdges = 0.3f, kTabDimmed = 0.4f;
// The options checkbox draws its circle (i_checkbox01, 48 x 48 in every set) at the texture's own
// size against the control's left edge.
const int kCheckboxCircle = 48;

const char* const captions[ElementCount] = {
    "Menu Buttons", "Minimap", "Action Bar", "Portraits", "Attack Buttons", "Disengage Button",
    "Action Menu", "Party Switch", "Minimap", "Top Left Bar", "Disengage"};
const char* const hudNames[2] = {"Mouse & Keyboard", "Controller"};
// The footer's button for the other tab: the tab's whole name nearly fills it and leaves its glyph
// no room (seen at 3024x1964).
const char* const hudFooterNames[2] = {"Mouse", "Controller"};

// The Xbox-style HUD's table, with the types it is written in (as xbox_hud.cpp declares them) and
// that file's Placed arithmetic for the pieces the preview draws.
namespace xbox {
enum Kind : unsigned char { kLabel, kButton, kToggle, kProgress };
enum Side : unsigned char { kLeft, kRight, kCentre, kRelative };
enum Edge : unsigned char { kTop, kBottom };
enum : unsigned char { kHide = 1, kRow = 2, kSetFont = 4, kParty = 8 };
struct Piece {
    unsigned short offset; Kind kind; Side side; Edge edge; short box[4];
    signed char places; unsigned char flags; const char* fill; const char* hilight; const char* progress;
};
#include "../kmrp-controller/xbox_hud_layout.inc"
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

struct Entry { void* button = nullptr; int badged = -1; char family = 0; void* described = nullptr; };

// A label of the preview: the element it belongs to (-1: drawn for context, never scaled), its
// rectangle on the screen, and the HUD style it is part of.
struct Shown { void* label; int element; Rect screen; int style; char art[17]; };
const int Both = 2;   // a piece shown with either HUD: the screen's outline

// Allocated once and never freed: nothing here may depend on the order globals are made or
// destroyed in (the rule of kmrp_layout.cpp), and the game can end with the page open.
struct Page {
    std::map<void*, Entry> entries;
    void* pending = nullptr;
    void* current = nullptr;
    void* parent = nullptr;
    void* returnFocus = nullptr;
    std::uintptr_t table[kBasePanelSlots + 2] = {};   // offset-to-top, RTTI, then the slots
    std::vector<void*> owned;
    void* labels[ElementCount] = {};
    void* sliders[ElementCount] = {};
    void* linkSizes = nullptr;
    void* backdrop = nullptr;
    void* tabs[2] = {};
    void* otherButton = nullptr;
    void* defaultsButton = nullptr;
    void* backButton = nullptr;
    float tabColour[3] = {}, tabFrame[3] = {};
    pad::Glyph defaultsGlyph, otherGlyph, backGlyph;
    std::vector<Shown> pieces;
    Rect groups[ElementCount] = {};
    Preview preview;
    bool initialized = false, dirty = false;
    Sizes sizing, requested;
    int releasedFrames = 2;
    bool blockReopen = false;
    std::array<int, ElementCount> displayed{};
    int displayedLinked = -1, displayedFocus = -2;
    int shownStyle = Pc, displayedStyle = -1;
    std::array<int, ElementCount> drawn{};
    int screenWidth = 0, screenHeight = 0;
    std::map<std::string, void*> keptImages;
    std::vector<void*> preloadedTextures;
    std::vector<std::string> preloaded;
    std::size_t preloadNext = 0;
};
Page& P() {
    static Page* page = new Page;
    return *page;
}

// Return and Space through CoreGraphics, which this part does not link (layouts_ini.cpp): the
// controller patch's answer covers the pad, the same two keys and, here, the mouse is the
// manager's own bit, which the engine's slider reads too.
bool KeyHeld(unsigned short key) {
    using KeyState = bool (*)(int, unsigned short);
    static KeyState state = [] {
        void* cg = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY | RTLD_LOCAL);
        return cg ? reinterpret_cast<KeyState>(dlsym(cg, "CGEventSourceKeyState")) : nullptr;
    }();
    return state && state(0, key);   // kCGEventSourceStateCombinedSessionState
}
bool ConfirmHeld(void* manager) {
    return pad::ConfirmHeld() || (At<std::uint8_t>(manager, kManagerButtons) & 1) || KeyHeld(36) || KeyHeld(49);
}
bool Armed() { return P().releasedFrames >= 2; }
// A handler's press: the pad's A reaches it as it goes down and again as it comes up, the mouse
// only as it comes up, with the value 1 (CSWGuiControl::HandleLMouseUp, 0x1004A50A0). As the
// graphics screen's own handlers read it.
bool Pressed(void* control) { return !control || At<int>(control, kCtlValue) != 0; }

void Initialize() {
    Page& p = P();
    if (p.initialized) return;
    p.initialized = true;
    p.sizing = kmrp::hud::ReadSizes();
    p.sizing.Link(p.sizing.linked);
    p.requested = p.sizing;
}

void Extent(void* control, const Rect& rect) {
    reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtSetExtent))(control, &rect);
}
void DestroyControl(void* control) {
    if (!LooksLikePointer(control)) return;
    reinterpret_cast<void (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtDeleting))(control);
}
void TextOf(void* params, const char* text) {
    void* string[2] = {nullptr, nullptr};   // CExoString
    StringCtor(string, text);
    SetText(params, string);
    StringDtor(string);
}
void Text(void* control, const char* text, bool button = false) {
    TextOf(static_cast<char*>(control) + (button ? kButtonTextParams : kLabelTextParams), text);
}
void Align(void* control, unsigned char alignment, bool button = false) {
    SetAlignment(static_cast<char*>(control) + (button ? kButtonTextParams : kLabelTextParams), alignment);
}
bool AddControl(void* panel, void* control) {
    const int count = At<int>(panel, kPanelCount);
    if (count < 0 || count >= 512) return false;
    At<int>(control, kCtlId) = count;
    AddControlTo(panel, control);
    return At<int>(panel, kPanelCount) == count + 1 && At<void**>(panel, kPanelControls)[count] == control;
}
void* CloneButton(void* owner, void* prototype) {
    if (VtableOf(prototype) != kButtonTable) return nullptr;
    void* c = ::operator new(kButtonSize, std::nothrow);
    if (!c) return nullptr;
    std::memset(c, 0, kButtonSize);
    Fn<void (*)(void*)>(kButtonCtor)(c);
    const Rect rect = At<Rect>(prototype, kExtent);
    CopyButton(c, &rect, prototype);
    At<std::uint8_t>(c, kCtlFlags) = (At<std::uint8_t>(c, kCtlFlags) & ~0x2Eu) | (At<std::uint8_t>(prototype, kCtlFlags) & 0x2Eu);
    if (!AddControl(owner, c)) { DestroyControl(c); return nullptr; }
    return c;
}
// A control of the page bound from the graphics screen's file. `table`: the class's vtable when
// its constructor leaves another (the options checkbox).
void* Bind(void* panel, const char* tag, std::size_t size, std::uintptr_t ctor, std::uintptr_t table = 0) {
    void* c = ::operator new(size, std::nothrow);
    if (!c) return nullptr;
    std::memset(c, 0, size);
    Fn<void (*)(void*)>(ctor)(c);
    if (table) At<std::uintptr_t>(c, 0) = table;
    At<int>(c, kCtlId) = -1;
    void* name[2] = {nullptr, nullptr};
    StringCtor(name, tag);
    InitControl(panel, c, name, 0);
    StringDtor(name);
    if (At<int>(c, kCtlId) < 0 || !AddControl(panel, c)) { DestroyControl(c); return nullptr; }
    P().owned.push_back(c);
    return c;
}
void* BindLabel(void* panel, const char* tag) { return Bind(panel, tag, kLabelSize, kLabelCtor); }
void* BindButton(void* panel, const char* tag) { return Bind(panel, tag, kButtonSize, kButtonCtor); }

void Navigation(void* c, void* up, void* down, void* left = nullptr, void* right = nullptr) {
    At<void*>(c, kNavUp) = up; At<void*>(c, kNavLeft) = left;
    At<void*>(c, kNavDown) = down; At<void*>(c, kNavRight) = right;
}
void Close() {
    void* current = P().current;
    if (current) {
        std::uint16_t& flags = At<std::uint16_t>(current, kPanelFlags);
        flags = static_cast<std::uint16_t>((flags & ~0x700u) | 0x400u);
    }
}
// A bound control selectable as its live counterpart on the graphics screen is (K1HudOptions.cpp,
// SelectableAs): one bound from the file does not get the bit, and the pad moves only to a control
// that has it.
void SelectableAs(void* control, void* owner, const char* tag) {
    void* original = kmrp::panels::ControlByTag(owner, tag);
    if (!control || !original) return;
    At<std::uint8_t>(control, kCtlFlags) = (At<std::uint8_t>(control, kCtlFlags) & ~0x2Cu) | (At<std::uint8_t>(original, kCtlFlags) & 0x2Cu);
}
void Dirty() {
    Page& p = P();
    p.dirty = p.requested.values != p.sizing.values || p.requested.linked != p.sizing.linked;
}
void Back(void*, void* control) { if (Armed() && Pressed(control)) Close(); }
void Open(void* owner, void* control) {
    Page& p = P();
    if (Pressed(control) && !p.current && !p.pending && !p.blockReopen) p.pending = owner;
}
void ToggleLink(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { p.requested.Link(!p.requested.linked); Dirty(); p.releasedFrames = 0; }
}
void Defaults(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { p.requested = Sizes{}; Dirty(); p.releasedFrames = 0; }
}
// A slider's events, as the graphics screen gives Brightness its own (0x1002CA132): entering and
// leaving, its four movement events and a click, and the Default command. The controller patch
// takes a control with no events for decoration (gui.cpp, Navigable). The value is read every
// frame, so moving needs nothing more here.
void SliderEvent(void*, void*) {}
void SliderEvents(void* slider, void* panel) {
    for (const int event : {kEventEnter, kEventLeave, 0x2F, 0x30, 0x3F, 0x40, kEventA})
        AddEvent(slider, event, panel, reinterpret_cast<void*>(&SliderEvent), 0);
    AddEvent(slider, kEventY, panel, reinterpret_cast<void*>(&Defaults), 0);
}
void ToggleHud(void*, void* control);
// B closes, Y restores the defaults and X shows the other tab, wherever the focus is: those buttons
// are off the pad's focus. The panel's slot +0x80, HandleInputEvent, as in the controller's
// layout.cpp.
void Input(void* self, int event, int value) {
    if (value && event == kEventB) { Close(); return; }
    if (event == kEventY) { if (value) Defaults(nullptr, nullptr); return; }
    if (event == kEventX) { if (value) ToggleHud(nullptr, nullptr); return; }
    PanelInput(self, event, value);
}
// The page's destructors. The manager has removed the panel already on a normal close; an engine
// shutdown may destroy it still attached.
void Destroy(void* self) {
    Page& p = P();
    void* manager = At<void*>(self, kPanelManager);
    if (LooksLikePointer(manager) && PanelExists(manager, self)) RemovePanel(manager, self);
    SetActive(self, nullptr, 0);
    void** array = At<void**>(self, kPanelControls);
    for (int i = 0; LooksLikePointer(array) && i < At<int>(self, kPanelCount); ++i) array[i] = nullptr;
    for (void* c : {p.tabs[0], p.tabs[1], p.otherButton, p.defaultsButton, p.backButton}) pad::SkipFocus(c, false);
    for (void* c : p.owned) DestroyControl(c);
    p.owned.clear();
    p.pieces.clear();
    p.linkSizes = p.tabs[0] = p.tabs[1] = p.otherButton = p.defaultsButton = p.backButton = p.backdrop = nullptr;
    p.defaultsGlyph = p.otherGlyph = p.backGlyph = pad::Glyph{};
    for (void*& c : p.labels) c = nullptr;
    for (void*& c : p.sliders) c = nullptr;
    PanelDtor(self);
    p.current = nullptr;
    if (p.parent && LooksLikePointer(manager) && PanelExists(manager, p.parent)) SetActive(p.parent, p.returnFocus, 0);
    p.parent = p.returnFocus = nullptr;
    p.blockReopen = true;
    p.releasedFrames = 0;
}
void DestroyComplete(void* self) { Destroy(self); }
void DestroyDeleting(void* self) {
    Destroy(self);
    ::operator delete(self);
}

// The chosen HUD's rows shown and the other's hidden, its tab at full strength and the other
// dimmed, the middle button naming the other tab, and the focus's links rebuilt over what is
// shown: "Link HUD Sizes", then the sliders under it, up and down and round. A slider has no left
// or right neighbour, so the engine's left and right move it and keep the focus on it (item 66).
void ShowHud(int style) {
    Page& p = P();
    p.shownStyle = style;
    std::vector<void*> shown;
    for (int i = 0; i < ElementCount; ++i) {
        const bool visible = StyleOf(i) == style;
        for (void* c : {p.labels[i], p.sliders[i]}) {
            std::uint8_t& flags = At<std::uint8_t>(c, kCtlFlags);
            flags = visible ? (flags | kVisible) : (flags & ~kVisible);
        }
        if (visible) shown.push_back(p.sliders[i]);
    }
    Navigation(p.linkSizes, shown.back(), shown.front());
    for (std::size_t i = 0; i < shown.size(); ++i)
        Navigation(shown[i], i ? shown[i - 1] : p.linkSizes, i + 1 < shown.size() ? shown[i + 1] : p.linkSizes);
    Navigation(p.defaultsButton, shown.back(), p.linkSizes, p.backButton, p.otherButton);
    Navigation(p.otherButton, shown.back(), p.linkSizes, p.defaultsButton, p.backButton);
    Navigation(p.backButton, shown.back(), p.linkSizes, p.otherButton, p.defaultsButton);
    for (int i = 0; i < 2; ++i) {
        const float strength = i == style ? 1.0f : kTabDimmed;
        float caption[3], frame[3];
        for (int c = 0; c < 3; ++c) { caption[c] = p.tabColour[c] * strength; frame[c] = p.tabFrame[c] * strength; }
        SetColor(static_cast<char*>(p.tabs[i]) + kButtonTextParams, caption);
        std::memcpy(&At<float>(p.tabs[i], kButtonFrameColour), frame, sizeof frame);
    }
    Text(p.otherButton, hudFooterNames[style == Pc ? Xbox : Pc], true);
}
void SelectPc(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { if (p.shownStyle != Pc) ShowHud(Pc); p.releasedFrames = 0; }
}
void SelectXbox(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { if (p.shownStyle != Xbox) ShowHud(Xbox); p.releasedFrames = 0; }
}
void ToggleHud(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { ShowHud(p.shownStyle == Pc ? Xbox : Pc); p.releasedFrames = 0; }
}

// The element whose slider has the focus, or -1.
int FocusedElement() {
    Page& p = P();
    if (!p.current) return -1;
    void* focus = At<void*>(p.current, kPanelActive);
    for (int i = 0; i < ElementCount; ++i) if (focus && focus == p.sliders[i]) return i;
    return -1;
}

// Where a piece of the preview stands on the screen at the sizes asked for: `screen` is its place
// at the default size, `e` its element (-1: context, never scaled).
Rect SizedOnScreen(int e, const Rect& screen) {
    Page& p = P();
    const int size = e < 0 ? Default
        : e == PcAttack ? p.requested.values[e]
        : FittingSize(p.groups[e], CornerOf(e), p.requested.values[e], p.screenWidth, p.screenHeight);
    Rect r = e < 0 ? screen : ScaleAbout(screen, p.groups[e], CornerOf(e), size);
    // Kept on the screen: the combat strip spans its width and grows from the middle of the top.
    const int right = (std::min)(p.screenWidth, r.left + r.width), bottom = (std::min)(p.screenHeight, r.top + r.height);
    r.left = (std::max)(0, r.left);
    r.top = (std::max)(0, r.top);
    r.width = (std::max)(1, right - r.left);
    r.height = (std::max)(1, bottom - r.top);
    return r;
}

// The preview's pieces of the style shown, where the requested sizes put them; the focused
// element's at full strength, the others dimmed; the other style's hidden. Only what changed.
void UpdatePreview() {
    Page& p = P();
    const int focus = FocusedElement();
    const bool moved = p.drawn != p.requested.values, switched = p.shownStyle != p.displayedStyle;
    if (!moved && !switched && focus == p.displayedFocus) return;
    for (const Shown& piece : p.pieces) {
        const bool visible = piece.style == p.shownStyle || piece.style == Both;
        std::uint8_t& flags = At<std::uint8_t>(piece.label, kCtlFlags);
        flags = visible ? (flags | kVisible) : (flags & ~kVisible);
        if (!visible) continue;
        if (moved || switched) Extent(piece.label, p.preview.Map(SizedOnScreen(piece.element, piece.screen)));
        const bool lit = focus < 0 || focus == piece.element;
        At<float>(piece.label, kLabelParams + kParamsAlpha) =
            piece.label == p.backdrop ? 1.0f : piece.style == Both ? kEdges : lit ? 1.0f : kDimmed;
    }
    p.drawn = p.requested.values;
    p.displayedFocus = focus;
    p.displayedStyle = p.shownStyle;
}

void UpdateCaptions() {
    Page& p = P();
    if (!p.current) return;
    for (int i = 0; i < ElementCount; ++i) if (p.displayed[i] != p.requested.values[i]) {
        char caption[64];
        std::snprintf(caption, sizeof caption, "%s: %d%%", captions[i], p.requested.values[i]);
        Text(p.labels[i], caption);
        SetSliderValue(p.sliders[i], (p.requested.values[i] - Minimum) / Step);
        p.displayed[i] = p.requested.values[i];
    }
    if (p.displayedLinked != int(p.requested.linked)) {
        std::uint8_t& state = At<std::uint8_t>(p.linkSizes, kCheckboxState);
        state = static_cast<std::uint8_t>((state & ~1u) | (p.requested.linked ? 1u : 0u));
        p.displayedLinked = p.requested.linked;
    }
}

// An element's whole box grows to hold one more of its rectangles.
void Grow(int element, const Rect& r, bool (&seen)[ElementCount]) {
    if (element < 0) return;
    Rect& box = P().groups[element];
    if (!seen[element]) { box = r; seen[element] = true; return; }
    const int right = (std::max)(box.left + box.width, r.left + r.width), bottom = (std::max)(box.top + box.height, r.top + r.height);
    box.left = (std::min)(box.left, r.left);
    box.top = (std::min)(box.top, r.top);
    box.width = right - box.left;
    box.height = bottom - box.top;
}
// A preview label wearing `art`, stretched to whatever size the preview gives it, and carrying
// `text` where the HUD's control shows words; a control with words and no picture (Disengage) is
// its words alone.
void AddShown(void* panel, const char* art, int element, const Rect& r, int style, const char* text = "") {
    Page& p = P();
    const bool hasArt = art && art[0], hasText = text && text[0];
    if ((!hasArt && !hasText) || p.pieces.size() >= 128) return;
    void* label = BindLabel(panel, "LBL_GAMMA");
    if (!label) return;
    Extent(label, p.preview.Map(r));
    Text(label, text);
    Shown piece{label, element, r, style, {}};
    if (hasArt) {
        std::memcpy(piece.art, art, (std::min)(std::strlen(art), sizeof piece.art - 1));
        std::uint8_t& flags = At<std::uint8_t>(label, kLabelParams + kParamsFlags);
        flags = static_cast<std::uint8_t>((flags & ~3u) | 2u);   // stretched: the art drawn at the preview's size
    }
    p.pieces.push_back(piece);
}
void SetPreviewPictures() {
    for (const Shown& piece : P().pieces)
        if (piece.art[0]) pad::SetFill(static_cast<char*>(piece.label) + kLabelParams, piece.art);
}
// An image of every picture the page has shown, kept for the session: a border's image is made by
// name when its fill is set and released when the page closes, so the game would load the
// preview's textures again at every opening (K1HudOptions.cpp, KeepImage).
void KeepImage(void* control, std::size_t params) {
    char name[17] = {};
    std::memcpy(name, static_cast<const char*>(control) + params + kParamsFill, 16);
    Page& p = P();
    if (!name[0] || p.keptImages.count(name)) return;
    if (void* image = NewImage(name)) p.keptImages[name] = image;
}
// The Xbox-style HUD's element of a piece of its table, or -1 for context.
int XboxElement(const xbox::Piece& x) {
    return kmrp::hud::XboxElementOf(x.offset, (x.flags & xbox::kParty) != 0, (x.flags & xbox::kRow) != 0,
                                    x.side == xbox::kLeft && x.edge == xbox::kBottom);
}
// The PC HUD from its table: every control of its six elements that the table marks for the
// preview and that has a texture, in the file's order (later ones on top); BTN_CLEARALL, which
// shows a word and no picture, as that word over the combat queue's frame. The Xbox-style HUD from
// its table, less the combat strip across the top. Under both, the screen in slate, with a faint
// outline. `add(art, element, rect, style, text)` for each piece, in drawing order; the elements'
// whole boxes (`groups`) found on the way.
template <class Add> void PreviewPieces(int width, int height, Add add) {
    Page& p = P();
    if (p.preview.scale > 0) {
        const int t = (std::max)(1, static_cast<int>(2.0 / p.preview.scale + 0.5));
        const Rect edges[4] = {{0, 0, width, t}, {0, height - t, width, t}, {0, 0, t, height}, {width - t, 0, t, height}};
        add("whitefill", -1, Rect{0, 0, width, height}, Both, "");
        for (const Rect& edge : edges) add("whitefill", -1, edge, Both, "");
    }
    bool seen[ElementCount] = {};
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
        // The target menu, which the game draws at the target, a third of the way down, centred.
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
        if (x.flags & xbox::kRow) continue;
        const Rect r = xbox::Placed(x, width, height);
        Grow(element, r, seen);
        // A bar shows its filling; anything else its own art.
        add(x.kind == xbox::kProgress && x.progress ? x.progress : x.fill, element, r, Xbox, "");
    }
}

void MakePreview(void* panel, const Rect& area, int width, int height) {
    Page& p = P();
    p.preview = Preview::Fit(area, width, height);
    p.screenWidth = width;
    p.screenHeight = height;
    PreviewPieces(width, height, [&](const char* art, int element, const Rect& r, int style, const char* text) {
        const std::size_t before = p.pieces.size();
        AddShown(panel, art, element, r, style, text);
        if (p.pieces.size() == before) return;
        if (before == 0) {
            p.backdrop = p.pieces.back().label;
            std::memcpy(&At<float>(p.backdrop, kLabelParams + kParamsColour), kBackdrop, sizeof kBackdrop);
        }
        // Disengage centred in its box, as the game's file has it (ALIGNMENT 18); the label it is
        // made from (LBL_GAMMA) reads from the left (item 62).
        if (text && text[0]) Align(p.pieces.back().label, 18);
    });
}

// The left column's places: each the graphics screen's caption height (the link, and each HUD's
// parts on the places after it).
int Places() {
    int most = 0, count[2] = {};
    for (int i = 0; i < ElementCount; ++i) most = (std::max)(most, ++count[StyleOf(i)]);
    return most + 1;
}

Rect RectOf(void* owner, const char* tag) { return At<Rect>(kmrp::panels::ControlByTag(owner, tag), kExtent); }

// The right-hand box of the page, where the preview goes, from Graphics Options' own controls:
// inside the frame the player sees round its description list, below a line for the caption
// "Preview". `slot` is that line's height, the left column's place. The list's scrollbar strip on
// the right is left out and the rest centred in the frame (K1HudOptions.cpp, PreviewArea).
Rect PreviewArea(void* owner, int* slot) {
    const Rect label = RectOf(owner, "LBL_GAMMA"), desc = RectOf(owner, "LB_DESC");
    const int bar = At<int>(kmrp::panels::ControlByTag(owner, "LB_DESC"), kListBarWidth);
    const bool barKnown = bar > 0 && bar < desc.width / 2;
    *slot = (std::max)(1, (std::min)(label.height, desc.height / Places()));
    const int margin = (std::max)(2, desc.height / 32);
    Rect area = desc;
    if (barKnown) {
        const int left = desc.left - Round(bar * 23 / 86.0);
        const int right = desc.left + desc.width - bar - Round(bar * 13 / 86.0);
        area.left = left;
        area.width = right - left;
    }
    area.top = desc.top + margin + *slot;
    area.height = desc.top + desc.height - margin - area.top;
    area.left += area.width / 20;
    area.width -= area.width / 10;
    return area;
}

void MakeScreen(void* manager, void* owner) {
    using kmrp::panels::ControlByTag;
    Page& s = P();
    const char* required[] = {"LBL_TITLE", "SLI_GAMMA", "LBL_GAMMA", "BTN_DEFAULT", "BTN_BACK", "LB_DESC", "CB_SHADOWS", "BTN_ADVANCED"};
    for (const char* tag : required) if (!ControlByTag(owner, tag)) return;
    void* p = ::operator new(kPanelSize, std::nothrow);
    if (!p) return;
    std::memset(p, 0, kPanelSize);
    PanelCtor(p, manager);
    std::memcpy(s.table, reinterpret_cast<const void*>(kBasePanelTable - 16), sizeof s.table);
    s.table[2 + 0] = reinterpret_cast<std::uintptr_t>(&DestroyComplete);
    s.table[2 + 1] = reinterpret_cast<std::uintptr_t>(&DestroyDeleting);
    s.table[2 + 16] = reinterpret_cast<std::uintptr_t>(&Input);   // HandleInputEvent, +0x80
    At<std::uintptr_t*>(p, 0) = &s.table[2];
    s.current = p;
    s.parent = owner;
    s.returnFocus = At<void*>(owner, kPanelActive);
    s.owned.clear();
    s.pieces.clear();
    char resref[32] = {};
    ResRefCtor(resref, "optgraphics");
    StartLoad(p, resref);
    void* title = BindLabel(p, "LBL_TITLE");
    for (void*& tab : s.tabs) tab = BindButton(p, "BTN_DEFAULT");
    for (int i = 0; i < ElementCount; ++i) {
        s.labels[i] = BindLabel(p, "LBL_GAMMA");
        s.sliders[i] = Bind(p, "SLI_GAMMA", kSliderSize, kSliderCtor);
        kmrp::slider::TakeMouse(s.sliders[i]);   // dragged to the end is the maximum (slider_grip.h)
    }
    s.linkSizes = Bind(p, "CB_SHADOWS", kCheckboxSize, kToggleCtor, kCheckboxTable);
    if (s.linkSizes) At<int>(s.linkSizes, kCheckboxEvent) = -1;
    const Rect titleRect = RectOf(owner, "LBL_TITLE"), label = RectOf(owner, "LBL_GAMMA"), track = RectOf(owner, "SLI_GAMMA");
    const Rect defaultsRect = RectOf(owner, "BTN_DEFAULT"), backRect = RectOf(owner, "BTN_BACK"), desc = RectOf(owner, "LB_DESC");
    void* const resolution = ControlByTag(owner, "BTN_RESOLUTION");
    const int gap = (std::max)(2, track.height / 3);
    // The screen's own art, which the page cannot move: the title's band ends where the title
    // does, and the right-hand box's frame stands round the description list. Windows' captures
    // at 3440x1440, kept as shares of the scrollbar's width and of the panel.
    const int bar = At<int>(ControlByTag(owner, "LB_DESC"), kListBarWidth);
    const bool barKnown = bar > 0 && bar < desc.width / 2;
    const int frameTop = desc.top - (barKnown ? Round(bar * 19 / 86.0) : gap);
    const Rect panel = At<Rect>(owner, kExtent);
    const auto artX = [&](int x) { return panel.left + Round(x * panel.width / 3440.0); };
    const auto artY = [&](int y) { return panel.top + Round(y * panel.height / 1440.0); };
    const int rowHeight = resolution ? At<Rect>(resolution, kExtent).height : label.height;
    // The tabs, a pair of the buttons' frames side by side, as wide together as the title's band
    // and as tall as it, a fifth of their height apart, in the gap between the title and the box's
    // frame.
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
    MakePreview(p, area, At<short>(manager, kManagerWidth), At<short>(manager, kManagerHeight));
    void* previewCaption = BindLabel(p, "LBL_GAMMA");
    void* defaults = BindButton(p, "BTN_DEFAULT");
    void* other = BindButton(p, "BTN_DEFAULT");
    void* back = BindButton(p, "BTN_BACK");
    // The pad's Y, X and B beside the three buttons' captions (options_pad.h).
    void* marks[3];
    for (void*& mark : marks) mark = BindLabel(p, "LBL_GAMMA");
    StopLoad(p);
    bool complete = title && s.tabs[0] && s.tabs[1] && s.linkSizes && defaults && other && back &&
                    marks[0] && marks[1] && marks[2] && previewCaption;
    for (int i = 0; i < ElementCount; ++i) complete = complete && s.labels[i] && s.sliders[i];
    if (!complete) { DestroyDeleting(p); return; }
    s.defaultsButton = defaults;
    s.backButton = back;
    s.otherButton = other;
    // The sliders get the bit outright: Brightness itself lacks it on the graphics screen, so
    // copying it gives nothing, and the slider class's own test says yes.
    for (void* slider : s.sliders) {
        SelectableAs(slider, owner, "SLI_GAMMA");
        At<std::uint8_t>(slider, kCtlFlags) |= kSelectable;
        SliderEvents(slider, p);
    }
    SelectableAs(s.linkSizes, owner, "CB_SHADOWS");
    for (void* button : {s.tabs[0], s.tabs[1], defaults, other}) SelectableAs(button, owner, "BTN_DEFAULT");
    SelectableAs(back, owner, "BTN_BACK");
    Extent(p, At<Rect>(owner, kExtent));
    Extent(title, titleRect);
    for (int i = 0; i < 2; ++i) Extent(s.tabs[i], tabRects[i]);
    // Default, the other tab and Close, one width, spread evenly along the tray's bottom line, two
    // gaps apart, a resolution button's height, in the middle of the tray.
    {
        const int trayLeft = artX(612), trayRight = artX(2912), trayTop = artY(1221), trayBottom = artY(1311);
        const int buttonGap = 2 * gap;
        const int buttonWidth = (std::max)(1, (trayRight - trayLeft - 2 * buttonGap) / 3);
        const int buttonHeight = (std::max)(1, (std::min)((std::min)(defaultsRect.height, backRect.height), rowHeight));
        const int buttonTop = trayTop + (trayBottom - trayTop - buttonHeight) / 2;
        void* const row[3] = {defaults, other, back};
        for (int i = 0; i < 3; ++i)
            Extent(row[i], Rect{trayLeft + i * (buttonWidth + buttonGap), buttonTop, buttonWidth, buttonHeight});
    }
    // The left column, level with the right-hand box: seven places evenly apart, the first with the
    // link's circle at the frame's top line, the last ending at the list's bottom. Each HUD's rows
    // take the same places, the other HUD's being hidden.
    const int places = Places();
    const int firstTop = frameTop - (slot - kCheckboxCircle) / 2;
    const int lastTop = desc.top + desc.height - slot;
    const auto placeTop = [&](int k) { return firstTop + k * (lastTop - firstTop) / (places - 1); };
    Extent(s.linkSizes, Rect{label.left, placeTop(0), label.width, slot});
    // Its caption read from the left beside its circle (17: left, middle line); the checkbox
    // centres it across the whole control otherwise.
    Align(s.linkSizes, 17, true);
    {
        const Rect caption{label.left + kCheckboxCircle + gap, placeTop(0), label.width - kCheckboxCircle - gap, slot};
        TextSetExtent(static_cast<char*>(s.linkSizes) + kButtonText, &caption);
    }
    // The captions as wide as the widest of them at 100%, at the text size in use, and each slider
    // from there to the column's edge.
    int widest = 0;
    for (int i = 0; i < ElementCount; ++i) {
        Extent(s.labels[i], Rect{label.left, 0, label.width, slot});
        char probe[64];
        std::snprintf(probe, sizeof probe, "%s: 100%%", captions[i]);
        Text(s.labels[i], probe);
        widest = (std::max)(widest, pad::MeasureText(static_cast<char*>(s.labels[i]) + kLabelText).width);
    }
    const int captionWidth = (std::max)(label.width / 4, (std::min)(label.width / 2, widest + gap));
    const int sliderLeft = label.left + captionWidth + gap;
    const int sliderWidth = label.left + label.width - sliderLeft;
    const int sliderHeight = (std::min)(track.height, slot);
    int row[2] = {};
    for (int i = 0; i < ElementCount; ++i) {
        const int top = placeTop(1 + row[StyleOf(i)]++);
        Extent(s.labels[i], Rect{label.left, top, captionWidth, slot});
        Align(s.labels[i], 17);   // read from the left, in the middle of its row
        Extent(s.sliders[i], Rect{sliderLeft, top + (slot - sliderHeight) / 2, sliderWidth, sliderHeight});
        At<int>(s.sliders[i], kSliderMaximum) = SliderMaximum;
    }
    // "Preview" over the miniature screen, centred on it, in the line kept above it.
    Extent(previewCaption, Rect{s.preview.left, s.preview.top - slot, s.preview.width, slot});
    Align(previewCaption, 18);
    Text(previewCaption, "Preview");
    Text(s.linkSizes, "Link HUD Sizes", true);
    for (int i = 0; i < 2; ++i) Text(s.tabs[i], hudNames[i], true);
    Text(title, "HUD Size");
    // The tabs' colours at full strength: the buttons' own caption and frame colours.
    std::memcpy(s.tabColour, &At<float>(s.tabs[0], kButtonTextParams + kTextColour), sizeof s.tabColour);
    std::memcpy(s.tabFrame, &At<float>(s.tabs[0], kButtonFrameColour), sizeof s.tabFrame);
    for (void* mark : marks) { Text(mark, ""); At<std::uint8_t>(mark, kCtlFlags) &= ~kVisible; }
    s.defaultsGlyph = pad::Glyph{}; s.defaultsGlyph.label = marks[0]; s.defaultsGlyph.button = defaults; s.defaultsGlyph.code = 'y';
    s.otherGlyph = pad::Glyph{}; s.otherGlyph.label = marks[1]; s.otherGlyph.button = other; s.otherGlyph.code = 'x';
    s.backGlyph = pad::Glyph{}; s.backGlyph.label = marks[2]; s.backGlyph.button = back; s.backGlyph.code = 'b';
    for (void* button : {s.tabs[0], s.tabs[1], defaults, other, back}) pad::SkipFocus(button, true);
    AddEvent(s.linkSizes, kEventA, p, reinterpret_cast<void*>(&ToggleLink), 0);
    AddEvent(s.tabs[Pc], kEventA, p, reinterpret_cast<void*>(&SelectPc), 0);
    AddEvent(s.tabs[Xbox], kEventA, p, reinterpret_cast<void*>(&SelectXbox), 0);
    AddEvent(other, kEventA, p, reinterpret_cast<void*>(&ToggleHud), 0);
    AddEvent(defaults, kEventA, p, reinterpret_cast<void*>(&Defaults), 0);
    AddEvent(back, kEventA, p, reinterpret_cast<void*>(&Back), 0);
    s.displayed.fill(-1);
    s.drawn.fill(-1);
    s.displayedLinked = -1;
    s.displayedFocus = -2;
    s.displayedStyle = -1;
    ShowHud(Pc);
    // The page opens on "Link HUD Sizes", as the Text Size page on its link.
    SetActive(p, s.linkSizes, 0);
    s.releasedFrames = 0;
    UpdateCaptions();
    UpdatePreview();
    SetPreviewPictures();
    // The pad's Y, X and B before the page is shown, not on its next frame.
    {
        const bool padInUse = pad::PadInUse();
        const char family = pad::Family();
        for (pad::Glyph* glyph : {&s.defaultsGlyph, &s.otherGlyph, &s.backGlyph}) pad::Update(*glyph, padInUse, family);
    }
    for (const Shown& piece : s.pieces) if (piece.art[0]) KeepImage(piece.label, kLabelParams);
    for (pad::Glyph* glyph : {&s.defaultsGlyph, &s.otherGlyph, &s.backGlyph})
        if (glyph->label) KeepImage(glyph->label, kLabelParams);
    AddPanel(manager, p, 3, 1);
}

// The entry button, above "Text Size and Font" (which sits above Advanced Options): a third of a
// button's height between the two, as KmrpTextOptions::Entry has it.
Rect EntryAbove(const Rect& below) {
    return {below.left, below.top - below.height - (std::max)(2, below.height / 3), below.width, below.height};
}
void UpdateEntry(void* owner, Entry& e) {
    void* below = KmrpTextOptionsEntryK1(owner);
    if (!below) below = kmrp::panels::ControlByTag(owner, "BTN_ADVANCED");
    if (VtableOf(below) != kButtonTable) return;
    if (!e.button) {
        e.button = CloneButton(owner, below);
        if (!e.button) return;
        Text(e.button, "HUD Size", true);
        AddEvent(e.button, kEventA, owner, reinterpret_cast<void*>(&Open), 0);
    }
    const Rect wanted = EntryAbove(At<Rect>(below, kExtent));
    if (std::memcmp(&At<Rect>(e.button, kExtent), &wanted, sizeof wanted)) Extent(e.button, wanted);
    std::uint8_t& flags = At<std::uint8_t>(e.button, kCtlFlags);
    flags = (flags & ~4u) | (At<std::uint8_t>(below, kCtlFlags) & 4u);
    void* above = At<void*>(below, kNavUp);
    if (above != e.button) {
        Navigation(e.button, above, below, At<void*>(below, kNavLeft), At<void*>(below, kNavRight));
        At<void*>(below, kNavUp) = e.button;
        if (above && above != below && At<void*>(above, kNavDown) == below) At<void*>(above, kNavDown) = e.button;
    }
}
// The entry's A, as Advanced Options' below it has, while the entry has its screen's focus, the
// pad is in use and neither KMRP page is open over the screen. Painted only on a change.
void EntryBadge(void* owner, Entry& e, bool padInUse, char family) {
    if (!e.button) return;
    const bool want = padInUse && !P().current && !KmrpTextOptionsOpenK1() && At<void*>(owner, kPanelActive) == e.button;
    if (int(want) == e.badged && (!want || family == e.family)) return;
    pad::EntryBadge(e.button, want);
    e.badged = want;
    e.family = family;
}
// The description box for the rows the game gave none: its focus handlers fill the box for the
// other rows, and on these it kept the last row's words. The game's own call lays the box out, for
// Grass, whose text is the tallest, and these words then replace it. On a change of focus only.
void EntryDescription(void* owner, Entry& e) {
    using kmrp::panels::ControlByTag;
    void* const active = At<void*>(owner, kPanelActive);
    if (active == e.described) return;
    e.described = active;
    if (!active) return;
    const char* text = nullptr;
    if (active == e.button) {
        text = "Change the size of the on-screen HUD: the action bar, portraits, target bar and minimap.";
    } else if (active == KmrpTextOptionsEntryK1(owner)) {
        text = "Change the size of the game's text and of feat and skill icons, and choose the font.";
    } else if (active == ControlByTag(owner, "BTN_ADVANCED")) {
        text = "Change anti-aliasing, texture quality and other advanced graphics settings.";
    }
    void* const grass = ControlByTag(owner, "CB_GRASS");
    if (!text || !grass) return;
    ShowDescription(owner, At<std::uint64_t>(grass, kCtlStrRef));
    Text(static_cast<char*>(owner) + kGraphicsDescription, text);
}

// Two textures a GUI frame, so no frame stalls: every texture the preview's mouse and keyboard HUD
// shows, and the preview's screen, each from the engine's own reference to it, with a GL context
// current (item 59; Windows' KmrpPreloadHudPagesK1, audit THR-1). The Xbox-style HUD's pictures
// are not among them, as there.
void PreloadPage() {
    using namespace KmrpPcHud;
    Page& p = P();
    constexpr std::size_t kPerFrame = 2;
    const std::size_t count = sizeof kPcPieces / sizeof kPcPieces[0];
    // KMRP's art first: a texture asked for before its set is registered would be the game's.
    if (p.preloadNext > count || !kmrp::assets::Registered() || !CGLGetCurrentContext()) return;
    for (std::size_t done = 0; done < kPerFrame && p.preloadNext <= count; ++p.preloadNext) {
        const char* name = p.preloadNext == count ? "whitefill" : kPcPieces[p.preloadNext].fill;
        if (p.preloadNext < count) {
            const PcPiece& piece = kPcPieces[p.preloadNext];
            if (!(piece.flags & kPreview) || piece.element < 0 || !name || !name[0]) continue;
        }
        if (std::find(p.preloaded.begin(), p.preloaded.end(), name) != p.preloaded.end()) continue;
        p.preloaded.push_back(name);
        void* texture = TextureReference(name, 0);
        if (!texture) continue;
        BindTexture(texture);
        p.preloadedTextures.push_back(texture);
        ++done;
    }
}

}  // namespace

namespace kmrp {
namespace hud {

bool PageOpen() { return P().current != nullptr; }

int SizePercent(int element) {
    Initialize();
    return element >= 0 && element < ElementCount ? P().sizing.values[element] : Default;
}

void PageDestroyed(void* panel) {
    Page& p = P();
    const auto found = p.entries.find(panel);
    if (found != p.entries.end()) {
        void* button = found->second.button;
        void** array = At<void**>(panel, kPanelControls);
        for (int i = 0; LooksLikePointer(array) && i < At<int>(panel, kPanelCount); ++i)
            if (array[i] == button) array[i] = nullptr;
        p.entries.erase(found);
        DestroyControl(button);
    }
    if (p.pending == panel) p.pending = nullptr;
    if (p.parent == panel) { p.parent = p.returnFocus = nullptr; Close(); }
}

void PageFrame(void* manager) {
    if (!LooksLikePointer(manager)) return;
    Initialize();
    Page& p = P();
    if (!Armed()) {
        if (ConfirmHeld(manager)) p.releasedFrames = 0;
        else ++p.releasedFrames;
    }
    if (p.blockReopen && Armed()) p.blockReopen = false;
    const bool padInUse = pad::PadInUse();
    const char family = pad::Family();
    static std::vector<void*>* graphics = new std::vector<void*>;
    graphics->clear();
    panels::WithVtable(kGraphicsTable, manager, *graphics);
    for (void* panel : *graphics) {
        Entry& e = p.entries[panel];
        UpdateEntry(panel, e);
        EntryBadge(panel, e, padInUse, family);
        EntryDescription(panel, e);
    }
    if (p.current)
        for (pad::Glyph* glyph : {&p.defaultsGlyph, &p.otherGlyph, &p.backGlyph}) pad::Update(*glyph, padInUse, family);
    if (p.pending) {
        void* owner = p.pending;
        p.pending = nullptr;
        if (!p.current && PanelExists(manager, owner)) MakeScreen(manager, owner);
    }
    if (p.current && p.sliders[0] && !p.dirty) {
        for (int i = 0; i < ElementCount; ++i) {
            const int moved = Minimum + (std::max)(0, (std::min)(SliderMaximum, At<int>(p.sliders[i], kSliderValue))) * Step;
            if (moved != p.requested.values[i]) { p.requested.Set(i, moved); Dirty(); break; }
        }
    }
    if (p.dirty) {
        p.sizing = p.requested;
        p.dirty = false;
        WriteSizes(p.sizing);
        UpdateCaptions();
    }
    if (p.current) UpdatePreview();
    PreloadPage();
}

}  // namespace hud
}  // namespace kmrp
