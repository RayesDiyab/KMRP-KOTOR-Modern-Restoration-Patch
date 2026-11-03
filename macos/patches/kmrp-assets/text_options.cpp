/*
  KMRP for macOS: the Text Size and Font page. A button in Graphics Options above Advanced Options
  opens a page of the graphics screen's own controls: four text-size sliders, Link Text Sizes, the
  two fonts (Original Font, HD Font), a preview of each size, the Feat & Skill Icons slider with
  its preview, and Default, Save and Close. The port of src/controller-native/K1TextOptions.cpp,
  whose comments give the reasons and the maintainer's requests; docs/ingame-text-options.md
  describes the page. Handoff items 56, 64, 70, 129, 130 and the rows of 133 about this page.

  Built as Windows builds it and as hud_options.cpp builds its page, whose note holds the engine's
  offsets on the Mac: controls bound from optgraphics again and placed from the live screen's
  rectangles, so it follows every set and resolution. Its rules are Windows' own header,
  K1TextOptionsPolicy.h, and the icons' macos/tools/kmrp-iconsize.h. What is chosen is held in
  kmrp-layout/text_settings.cpp, which asks swkotor.ini, and the fonts are fonts.cpp's.

  The page's controls show a change at once, by the fonts' metrics alone, and nothing is made or
  written until Save: fitting the HD atlases takes over a second the first time at a size, and a
  stretched atlas is a fair preview. A change of font fits at once, so it is seen as it will be.
  Close with something unsaved asks, in the game's own message box.

  The engine on the Mac, beyond hud_options.cpp's note:

      CSWGuiMessageBox, 0xC18 (0x984)  ctor 0x1003062C4 (0x00626DF0); FUN_1003063FE(box, 1) shows the
                                       second button (0x00627130); +0x79 bit 0 OK was chosen (+0x64);
                                       the callback 0x100306C6E(box, receiver, handler, adjust,
                                       argument) sets +0x90, +0x80, +0x88, +0x98 (+0x6C, +0x68, none,
                                       +0x70); SetMessage 0x100306506(box, CExoString*), which on
                                       the Mac takes it by reference (a class with a destructor)
                                       and leaves it to the caller; +0xC14 the mouse goes to OK as
                                       it opens (+0x980); OK +0x3D0, Cancel +0x610 (+0x2F4, +0x4B8)
      CSWGuiTextParams                 the base font's name +0x45 (+0x3C); ResetFont 0x1004A3670,
                                       inlined into Windows' SetBaseFont (0x00415DD0) by Aspyr's
                                       compiler: the name is written, then ResetFont is called

  Differences from Windows: the glyphs of Default, Save and Close stand beside their captions
  (options_pad.h). Nothing here has been seen in the game.
*/
#include "fonts.h"
#include "options_pad.h"
#include "panels.h"
#include "text_options.h"
#include "../kmrp-layout/slider_grip.h"
#include "../kmrp-layout/text_fit.h"
#include "../kmrp-layout/text_settings.h"
#include "../../tools/kmrp-iconsize.h"

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

namespace {

using namespace KmrpTextOptions;
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
const std::size_t kExtent = 0x08, kCtlPanel = 0x50, kCtlFlags = 0x68, kCtlValue = 0x70, kCtlId = 0x74;
const std::size_t kNavUp = 0x88, kNavLeft = 0x90, kNavDown = 0x98, kNavRight = 0xa0;
const std::uint8_t kVisible = 2, kSelectable = 8;
const std::size_t kVtSetExtent = 0x10, kVtDeleting = 0x08;
const std::size_t kLabelSize = 0x198, kButtonSize = 0x240, kSliderSize = 0x228, kCheckboxSize = 0x358, kBoxSize = 0xc18;
const std::uintptr_t kLabelCtor = 0x1004a54aaUL, kButtonCtor = 0x1004a5e8eUL, kSliderCtor = 0x1004a646eUL;
const std::uintptr_t kToggleCtor = 0x1004a5e16UL, kCheckboxTable = 0x1005ac6a8UL;
const std::uintptr_t kGraphicsTable = 0x1005ac1c0UL, kButtonTable = 0x1005b47b8UL, kBasePanelTable = 0x1005b3730UL;
const int kBasePanelSlots = 28;
const std::size_t kLabelText = 0x110, kLabelTextParams = 0x130, kLabelParams = 0xa0, kParamsFlags = 0x1c;
const std::size_t kButtonText = 0x1b8, kButtonTextParams = 0x1d8, kTextColour = 0x28, kBaseFont = 0x45;
const std::size_t kButtonFrameColour = 0xc0 + 0x10;
const std::size_t kSliderMaximum = 0xac, kSliderValue = 0xb0;
const std::size_t kCheckboxEvent = 0x240, kCheckboxState = 0x244;
const std::size_t kListBarWidth = 0x168;
const std::size_t kManagerHeight = 0xa6, kManagerButtons = 0x10;
const std::size_t kBoxChoice = 0x79, kBoxForceOk = 0xc14, kBoxOk = 0x3d0, kBoxCancel = 0x610;
const int kEventEnter = 0x00, kEventLeave = 0x01, kEventA = 0x27, kEventB = 0x28, kEventX = 0x29, kEventY = 0x2a;
const int kAlignLeftMiddle = 17;

using Rect = KmrpTextOptions::Rect;
using AddEventFn = void (*)(void* control, int event, void* receiver, void* handler, long adjust);

const auto StringCtor = Fn<void (*)(void*, const char*)>(0x10034cca8UL);
const auto StringDtor = Fn<void (*)(void*)>(0x10034cdf2UL);
const auto SetText = Fn<void (*)(void*, void*)>(0x1004a3714UL);
const auto SetColor = Fn<void (*)(void*, const float*)>(0x1004a380eUL);
const auto SetAlignment = Fn<void (*)(void*, unsigned char)>(0x1004a37a2UL);
const auto ResetFont = Fn<void (*)(void*)>(0x1004a3670UL);
const auto TextSetExtent = Fn<void (*)(void*, const Rect*)>(0x1004a3d4cUL);
const auto AddEvent = Fn<AddEventFn>(0x1004a4c5aUL);
const auto AddControlTo = Fn<void (*)(void*, void*)>(0x10049e5e2UL);
const auto CopyButton = Fn<void (*)(void*, const Rect*, void*)>(0x1004a5ab2UL);
const auto InitControl = Fn<void (*)(void*, void*, void*, int)>(0x10049e476UL);
const auto PanelCtor = Fn<void (*)(void*, void*)>(0x10049d7f8UL);
const auto PanelDtor = Fn<void (*)(void*)>(0x10049d8c8UL);
const auto ResRefCtor = Fn<void (*)(void*, const char*)>(0x100367b62UL);
const auto StartLoad = Fn<void (*)(void*, const void*)>(0x10049dfe4UL);
const auto StopLoad = Fn<void (*)(void*)>(0x10049d986UL);
const auto AddPanel = Fn<void (*)(void*, void*, int, int)>(0x10049ecaeUL);
const auto PanelExists = Fn<int (*)(void*, void*)>(0x10049d9ceUL);
const auto RemovePanel = Fn<int (*)(void*, void*)>(0x10049da14UL);
const auto SetActive = Fn<void (*)(void*, void*, int)>(0x10049de24UL);
const auto PanelInput = Fn<void (*)(void*, int, int)>(0x10049dc72UL);
const auto SetSliderValue = Fn<void (*)(void*, int)>(0x1004a6920UL);
const auto BoxCtor = Fn<void (*)(void*, void*)>(0x1003062c4UL);
const auto BoxButtons = Fn<void (*)(void*, int)>(0x1003063feUL);
const auto BoxCallback = Fn<void (*)(void*, void*, void*, long, void*)>(0x100306c6eUL);
const auto BoxMessage = Fn<void (*)(void*, void*)>(0x100306506UL);

// The options checkbox draws its circle at the texture's own size against its left edge (as
// hud_options.cpp), its caption centred across the whole control unless told.
const int kCheckboxCircle = 48;

const char* const groupLabels[] = {"Menus & Replies", "Subtitles & Body", "Small Text", "HUD Text"};
const char* const previewFonts[] = {"dialogfont16x16", "fnt_d16x16", "dialogfont10x10", "fnt_console"};
const char* const previewTexts[] = {"Menus and reply choices", "Subtitles and descriptions", "Small text preview", "HUD: 0123456789"};
const char* const iconPreviewNames[] = {"i_flurry01", "ip_push", "isk_stealth"};
constexpr int SaveDelayFrames = 2;
constexpr float SaveDimmed = 0.4f;

struct EntryButton { void* button = nullptr; int badged = -1; char family = 0; };

// Allocated once and never freed: nothing here may depend on the order globals are made or
// destroyed in (the rule of kmrp_layout.cpp), and the game can end with the page open.
struct Page {
    std::map<void*, EntryButton> entries;
    void* pending = nullptr;
    void* current = nullptr;
    void* parent = nullptr;
    void* returnFocus = nullptr;
    std::uintptr_t table[kBasePanelSlots + 2] = {};   // offset-to-top, RTTI, then the slots
    std::vector<void*> owned;
    void* sizeLabels[TextGroupCount] = {};
    void* sliders[TextGroupCount] = {};
    void* previews[TextGroupCount] = {};
    void* fontChoices[FontChoiceCount] = {};
    void* linkSizes = nullptr;
    void* help = nullptr;
    void* iconLabel = nullptr;
    void* iconSlider = nullptr;
    void* iconPreviews[3] = {};
    Rect iconArea{};
    int screenHeight = 0;
    void* defaultsButton = nullptr;
    void* saveButton = nullptr;
    void* backButton = nullptr;
    pad::Glyph defaultsGlyph, saveGlyph, backGlyph;
    float saveCaption[3] = {}, saveFrame[3] = {};
    void* warningBox = nullptr;
    bool initialized = false, dirty = false;
    Sizes requestedSizing, fitted;
    int requestedStyle = HdOriginal, requestedIcon = KMRP_ICON_DEFAULT;
    int releasedFrames = 2;
    bool blockReopen = false;
    int saveFrames = 0;
    bool closeAfterSave = false, closeAfterDiscard = false;
    int shownSaveState = -1;
    std::array<int, TextGroupCount> displayedSizes{{-1, -1, -1, -1}};
    int displayedLinked = -1, displayedStyle = -1, displayedIcon = -1;
};
Page& P() {
    static Page* page = new Page;
    return *page;
}

// Return and Space through CoreGraphics, which this part does not link: hud_options.cpp's way.
bool KeyHeld(unsigned short key) {
    using KeyState = bool (*)(int, unsigned short);
    static KeyState state = [] {
        void* cg = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY | RTLD_LOCAL);
        return cg ? reinterpret_cast<KeyState>(dlsym(cg, "CGEventSourceKeyState")) : nullptr;
    }();
    return state && state(0, key);
}
bool ConfirmHeld(void* manager) {
    return pad::ConfirmHeld() || (At<std::uint8_t>(manager, kManagerButtons) & 1) || KeyHeld(36) || KeyHeld(49);
}
bool Armed() { return P().releasedFrames >= 2; }
// A handler's press: the pad's A reaches it as it goes down and again as it comes up, the mouse
// only as it comes up, with the value 1.
bool Pressed(void* control) { return !control || At<int>(control, kCtlValue) != 0; }

void Initialize() {
    Page& p = P();
    if (p.initialized) return;
    p.initialized = true;
    const Settings& live = kmrp::textfit::Live();
    p.requestedSizing = live.sizing;
    p.requestedStyle = live.style;
    p.requestedIcon = live.icon;
    p.fitted = live.sizing;
}
Settings Requested() { const Page& p = P(); return {p.requestedSizing, p.requestedStyle, p.requestedIcon}; }
bool Unsaved() { return !SameSettings(Requested(), kmrp::textfit::Saved()); }

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
    At<void*>(c, kCtlPanel) = owner;
    const Rect rect = At<Rect>(prototype, kExtent);
    CopyButton(c, &rect, prototype);
    At<std::uint8_t>(c, kCtlFlags) = (At<std::uint8_t>(c, kCtlFlags) & ~0x2Eu) | (At<std::uint8_t>(prototype, kCtlFlags) & 0x2Eu);
    if (!AddControl(owner, c)) { DestroyControl(c); return nullptr; }
    return c;
}
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
void* BindCheckbox(void* panel) {
    void* c = Bind(panel, "CB_SHADOWS", kCheckboxSize, kToggleCtor, kCheckboxTable);
    // No automatic toggling: the page's handler says what each one shows.
    if (c) At<int>(c, kCheckboxEvent) = -1;
    return c;
}
void Checked(void* box, bool on) {
    std::uint8_t& state = At<std::uint8_t>(box, kCheckboxState);
    state = static_cast<std::uint8_t>((state & ~1u) | (on ? 1u : 0u));
}
// A checkbox placed, its caption read from the left beside its circle.
void PlaceCheckbox(void* box, const Rect& rect, int gap) {
    Extent(box, rect);
    SetAlignment(static_cast<char*>(box) + kButtonTextParams, kAlignLeftMiddle);
    const Rect caption{rect.left + kCheckboxCircle + gap, rect.top, rect.width - kCheckboxCircle - gap, rect.height};
    TextSetExtent(static_cast<char*>(box) + kButtonText, &caption);
}

void Navigation(void* c, void* up, void* down, void* left = nullptr, void* right = nullptr) {
    At<void*>(c, kNavUp) = up;
    At<void*>(c, kNavLeft) = left;
    At<void*>(c, kNavDown) = down;
    At<void*>(c, kNavRight) = right;
}
void Close() {
    void* current = P().current;
    if (current) {
        std::uint16_t& flags = At<std::uint16_t>(current, kPanelFlags);
        flags = static_cast<std::uint16_t>((flags & ~0x700u) | 0x400u);
    }
}
void SelectableAs(void* control, void* owner, const char* tag) {
    void* original = kmrp::panels::ControlByTag(owner, tag);
    if (!control || !original) return;
    At<std::uint8_t>(control, kCtlFlags) = (At<std::uint8_t>(control, kCtlFlags) & ~0x2Cu) | (At<std::uint8_t>(original, kCtlFlags) & 0x2Cu);
}
void Dirty() {
    Page& p = P();
    const Settings& live = kmrp::textfit::Live();
    p.dirty = p.requestedSizing.values != live.sizing.values || p.requestedSizing.linked != live.sizing.linked || p.requestedStyle != live.style;
}

// Save, from the button or the pad's X. Done in the frame (PageFrame): pressed, the button says
// Saving, which must be drawn before the work that holds up the frame.
void AskToSave() {
    Page& p = P();
    if (!p.current || !p.saveButton || p.saveFrames || !Unsaved()) return;
    p.saveFrames = SaveDelayFrames;
}
void SaveClicked(void*, void* control) {
    if (Armed() && Pressed(control)) { AskToSave(); P().releasedFrames = 0; }
}
// The warning's two buttons. The box has closed itself by now and is still in use on the stack
// (CSWGuiMessageBox::HandleInputEvent, 0x1003062CE), so only flags are set here.
void WarningClosed(void* box, void*) {
    Page& p = P();
    if (!p.current) return;
    if (At<std::uint8_t>(box, kBoxChoice) & 1u) {
        p.closeAfterSave = true;
        AskToSave();
    } else {
        const Settings& saved = kmrp::textfit::Saved();
        p.requestedSizing = saved.sizing;
        p.requestedStyle = saved.style;
        p.requestedIcon = saved.icon;
        Dirty();
        p.closeAfterDiscard = true;
    }
    p.releasedFrames = 0;
}
// The box's buttons as snug as FixMessageLabel leaves them had their captions touching their ends.
// One width, half a line wider than the longer caption at each end, centred; and room kept at the
// left for the pad's A, which stands beside the focused button.
void WidenWarningButtons() {
    void* const box = P().warningBox;
    void* ok = static_cast<char*>(box) + kBoxOk;
    void* cancel = static_cast<char*>(box) + kBoxCancel;
    Rect first = At<Rect>(ok, kExtent), second = At<Rect>(cancel, kExtent);
    const int panel = At<Rect>(box, kExtent).width, snug = (std::max)(first.width, second.width);
    const int room = panel - 2 * (first.height + first.height / 2);
    int width = (std::max)(snug, (std::min)(snug + first.height, room));
    width += (panel - width) & 1;   // an even remainder keeps the centre exact
    first.left = second.left = (panel - width) / 2;
    first.width = second.width = width;
    Extent(ok, first);
    Extent(cancel, second);
}
bool WarnOfUnsaved() {
    Page& p = P();
    void* manager = At<void*>(p.current, kPanelManager);
    if (!p.warningBox) {
        void* box = ::operator new(kBoxSize, std::nothrow);
        if (!box) return false;
        std::memset(box, 0, kBoxSize);
        BoxCtor(box, manager);
        p.warningBox = box;
    }
    BoxButtons(p.warningBox, 1);   // the second button shown, so B answers it
    // Each time: the box puts OK and Cancel back as it closes (ResetButtonMessage, 0x100306B40).
    Text(static_cast<char*>(p.warningBox) + kBoxOk, "Save", true);
    Text(static_cast<char*>(p.warningBox) + kBoxCancel, "Don't Save", true);
    BoxCallback(p.warningBox, p.warningBox, reinterpret_cast<void*>(&WarningClosed), 0, nullptr);
    void* message[2] = {nullptr, nullptr};
    StringCtor(message, "You have unsaved changes.");
    BoxMessage(p.warningBox, message);
    StringDtor(message);
    WidenWarningButtons();
    At<int>(p.warningBox, kBoxForceOk) = 1;
    AddPanel(manager, p.warningBox, 1, 1);
    return true;
}
void AskToClose() {
    Page& p = P();
    if (p.saveFrames || p.closeAfterDiscard) return;
    if (!Unsaved() || !WarnOfUnsaved()) Close();
}
void Back(void*, void* control) { if (Armed() && Pressed(control)) AskToClose(); }
void Open(void* owner, void* control) {
    Page& p = P();
    if (Pressed(control) && !p.current && !p.pending && !p.blockReopen) p.pending = owner;
}
void Choose(int value, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { p.requestedStyle = Style(value); Dirty(); p.releasedFrames = 0; }
}
void ToggleLink(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) { p.requestedSizing.Link(!p.requestedSizing.linked); Dirty(); p.releasedFrames = 0; }
}
void SelectOriginal(void*, void* control) { Choose(Original, control); }
void SelectHdOriginal(void*, void* control) { Choose(HdOriginal, control); }
void Defaults(void*, void* control) {
    Page& p = P();
    if (Armed() && Pressed(control)) {
        p.requestedSizing = Sizes{};
        p.requestedStyle = HdOriginal;
        p.requestedIcon = KMRP_ICON_DEFAULT;
        Dirty();
        p.releasedFrames = 0;
    }
}
// A slider's events, as the graphics screen gives Brightness its own (0x1002CA132): the controller
// patch takes a control with no events for decoration. The value is read every frame.
void SliderEvent(void*, void*) {}
void SliderEvents(void* slider, void* panel) {
    for (const int event : {kEventEnter, kEventLeave, 0x2F, 0x30, 0x3F, 0x40, kEventA})
        AddEvent(slider, event, panel, reinterpret_cast<void*>(&SliderEvent), 0);
    AddEvent(slider, kEventY, panel, reinterpret_cast<void*>(&Defaults), 0);
}
// B closes, Y restores the defaults and X saves, wherever the focus is: those buttons are off the
// pad's focus. The panel's slot +0x80, HandleInputEvent.
void Input(void* self, int event, int value) {
    if (value && event == kEventB) { AskToClose(); return; }
    if (event == kEventY) { if (value) Defaults(nullptr, nullptr); return; }
    if (event == kEventX) { if (value) AskToSave(); return; }
    PanelInput(self, event, value);
}
void Destroy(void* self) {
    Page& p = P();
    void* manager = At<void*>(self, kPanelManager);
    if (LooksLikePointer(manager) && PanelExists(manager, self)) RemovePanel(manager, self);
    SetActive(self, nullptr, 0);
    void** array = At<void**>(self, kPanelControls);
    for (int i = 0; LooksLikePointer(array) && i < At<int>(self, kPanelCount); ++i) array[i] = nullptr;
    for (void* c : {p.defaultsButton, p.saveButton, p.backButton}) pad::SkipFocus(c, false);
    for (void* c : p.owned) DestroyControl(c);
    p.owned.clear();
    p.help = p.linkSizes = p.defaultsButton = p.saveButton = p.backButton = nullptr;
    p.defaultsGlyph = p.saveGlyph = p.backGlyph = pad::Glyph{};
    p.saveFrames = 0;
    p.closeAfterSave = p.closeAfterDiscard = false;
    p.shownSaveState = -1;
    // Gone with its parent, say, and no one was asked: what is saved stands.
    if (p.initialized) {
        const Settings& saved = kmrp::textfit::Saved();
        p.requestedSizing = saved.sizing;
        p.requestedStyle = saved.style;
        p.requestedIcon = saved.icon;
        Dirty();
    }
    for (void*& c : p.sizeLabels) c = nullptr;
    for (void*& c : p.sliders) c = nullptr;
    for (void*& c : p.previews) c = nullptr;
    for (void*& c : p.fontChoices) c = nullptr;
    p.iconLabel = p.iconSlider = nullptr;
    for (void*& c : p.iconPreviews) c = nullptr;
    p.displayedIcon = -1;
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

void UpdateCaptions() {
    Page& p = P();
    if (!p.current) return;
    for (int i = 0; i < TextGroupCount; ++i) if (p.displayedSizes[i] != p.requestedSizing.values[i]) {
        char caption[64];
        std::snprintf(caption, sizeof caption, "%s: %d%%", groupLabels[i], p.requestedSizing.values[i]);
        Text(p.sizeLabels[i], caption);
        SetSliderValue(p.sliders[i], (p.requestedSizing.values[i] - Minimum) / Step);
        p.displayedSizes[i] = p.requestedSizing.values[i];
    }
    if (p.displayedIcon != p.requestedIcon && p.iconLabel && p.iconSlider) {
        char caption[64];
        std::snprintf(caption, sizeof caption, "Feat & Skill Icons: %d%%", p.requestedIcon);
        Text(p.iconLabel, caption);
        SetSliderValue(p.iconSlider, (p.requestedIcon - Minimum) / Step);
        p.displayedIcon = p.requestedIcon;
    }
    if (p.displayedLinked != int(p.requestedSizing.linked)) {
        Checked(p.linkSizes, p.requestedSizing.linked);
        p.displayedLinked = p.requestedSizing.linked;
    }
    if (p.displayedStyle != p.requestedStyle) {
        for (int i = 0; i < FontChoiceCount; ++i) Checked(p.fontChoices[i], FontChoices[i] == p.requestedStyle);
        p.displayedStyle = p.requestedStyle;
        // Right (or left) from "Link Text Sizes" goes to the font chosen.
        if (p.linkSizes) At<void*>(p.linkSizes, kNavLeft) = At<void*>(p.linkSizes, kNavRight) = p.fontChoices[ChoiceOf(p.requestedStyle)];
    }
}
// Save: greyed unless there is something to save, and "Saving..." while it is done. The caption's
// colour and the frame's, each at full strength from the button's own.
void UpdateSaveButton() {
    Page& p = P();
    if (!p.saveButton) return;
    const int state = p.saveFrames ? 2 : Unsaved() ? 1 : 0;
    if (state == p.shownSaveState) return;
    p.shownSaveState = state;
    Text(p.saveButton, state == 2 ? "Saving..." : "Save", true);
    const float strength = state == 1 ? 1.0f : SaveDimmed;
    float caption[3];
    for (int c = 0; c < 3; ++c) {
        caption[c] = p.saveCaption[c] * strength;
        (&At<float>(p.saveButton, kButtonFrameColour))[c] = p.saveFrame[c] * strength;
    }
    SetColor(static_cast<char*>(p.saveButton) + kButtonTextParams, caption);
}
// The preview's three icons at the size in force, side by side and centred in their area: the size
// the lists draw them at, smaller only where the area is shorter than the icon.
void PlaceIconPreviews(int percent) {
    Page& p = P();
    if (!p.iconPreviews[0]) return;
    const double scale = kmrp_icon_scale(p.screenHeight);
    const int feat = kmrp_icon_drawn(kmrp_icon_feat_today(scale, KMRP_ICON_NATIVE), scale, percent);
    const int skill = kmrp_icon_drawn(kmrp_icon_skill_today(scale, KMRP_ICON_NATIVE), scale, percent);
    const int sizes[3] = {(std::min)(feat, p.iconArea.height), (std::min)(feat, p.iconArea.height), (std::min)(skill, p.iconArea.height)};
    const int gap = (std::max)(4, p.iconArea.width / 48);
    int left = p.iconArea.left + (p.iconArea.width - (sizes[0] + sizes[1] + sizes[2] + 2 * gap)) / 2;
    for (int i = 0; i < 3; ++i) {
        Extent(p.iconPreviews[i], Rect{left, p.iconArea.top + (p.iconArea.height - sizes[i]) / 2, sizes[i], sizes[i]});
        left += sizes[i] + gap;
    }
}
Rect RectOf(void* owner, const char* tag) { return At<Rect>(kmrp::panels::ControlByTag(owner, tag), kExtent); }

void MakeScreen(void* manager, void* owner) {
    using kmrp::panels::ControlByTag;
    Page& s = P();
    const char* required[] = {"LBL_TITLE", "SLI_GAMMA", "LBL_GAMMA", "BTN_RESOLUTION", "BTN_DEFAULT", "BTN_BACK", "LB_DESC", "CB_SHADOWS", "BTN_ADVANCED"};
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
    char resref[32] = {};
    ResRefCtor(resref, "optgraphics");
    StartLoad(p, resref);
    void* title = BindLabel(p, "LBL_TITLE");
    for (int i = 0; i < TextGroupCount; ++i) {
        s.sizeLabels[i] = BindLabel(p, "LBL_GAMMA");
        s.sliders[i] = Bind(p, "SLI_GAMMA", kSliderSize, kSliderCtor);
        kmrp::slider::TakeMouse(s.sliders[i]);   // dragged to the end is the maximum (slider_grip.h)
    }
    s.linkSizes = BindCheckbox(p);
    for (void*& choice : s.fontChoices) choice = BindCheckbox(p);
    s.help = BindLabel(p, "LBL_GAMMA");
    for (void*& preview : s.previews) preview = BindLabel(p, "LBL_GAMMA");
    s.iconLabel = BindLabel(p, "LBL_GAMMA");
    s.iconSlider = Bind(p, "SLI_GAMMA", kSliderSize, kSliderCtor);
    kmrp::slider::TakeMouse(s.iconSlider);
    for (void*& icon : s.iconPreviews) icon = BindLabel(p, "LBL_GAMMA");
    void* defaults = BindButton(p, "BTN_DEFAULT");
    void* save = BindButton(p, "BTN_DEFAULT");
    void* back = BindButton(p, "BTN_BACK");
    void* marks[3];   // the pad's Y, X and B beside the three captions (options_pad.h)
    for (void*& mark : marks) mark = BindLabel(p, "LBL_GAMMA");
    StopLoad(p);
    bool complete = title && s.linkSizes && s.fontChoices[0] && s.fontChoices[1] && s.help && defaults && back && save &&
                    marks[0] && marks[1] && marks[2] && s.iconLabel && s.iconSlider;
    for (int i = 0; i < TextGroupCount; ++i) complete = complete && s.sizeLabels[i] && s.sliders[i] && s.previews[i];
    for (void* icon : s.iconPreviews) complete = complete && icon;
    if (!complete) { DestroyDeleting(p); return; }
    s.defaultsButton = defaults;
    s.saveButton = save;
    s.backButton = back;
    // The sliders get the selectable bit outright (Brightness itself lacks it) and Brightness's
    // events.
    for (void* slider : s.sliders) {
        SelectableAs(slider, owner, "SLI_GAMMA");
        At<std::uint8_t>(slider, kCtlFlags) |= kSelectable;
        SliderEvents(slider, p);
    }
    SelectableAs(s.iconSlider, owner, "SLI_GAMMA");
    At<std::uint8_t>(s.iconSlider, kCtlFlags) |= kSelectable;
    SliderEvents(s.iconSlider, p);
    SelectableAs(s.linkSizes, owner, "CB_SHADOWS");
    for (void* choice : s.fontChoices) SelectableAs(choice, owner, "CB_SHADOWS");
    SelectableAs(defaults, owner, "BTN_DEFAULT");
    SelectableAs(save, owner, "BTN_DEFAULT");
    SelectableAs(back, owner, "BTN_BACK");
    Extent(p, At<Rect>(owner, kExtent));
    Extent(title, RectOf(owner, "LBL_TITLE"));
    // Default, Save and Close: one width, Save midway, the ends where the game has them. They
    // narrow only where three of Default's width would not fit.
    {
        const Rect first = RectOf(owner, "BTN_DEFAULT"), last = RectOf(owner, "BTN_BACK");
        const int room = last.left + last.width - first.left, space = (std::max)(4, first.height / 3);
        const int width = (std::min)(first.width, (room - 2 * space) / 3);
        Extent(defaults, Rect{first.left, first.top, width, first.height});
        Extent(save, Rect{first.left + (room - width) / 2, first.top, width, first.height});
        Extent(back, Rect{last.left + last.width - width, first.top, width, first.height});
    }
    const Rect label = RectOf(owner, "LBL_GAMMA"), track = RectOf(owner, "SLI_GAMMA"), checkbox = RectOf(owner, "CB_SHADOWS");
    const int gap = (std::max)(2, track.height / 3);
    const Rect advanced = RectOf(owner, "BTN_ADVANCED");
    const int bottom = (std::min)(advanced.top + advanced.height, RectOf(owner, "BTN_DEFAULT").top - gap);
    // The four text sizes and, under them, the icon size: five pairs. Where five do not fit with
    // each slider as far under its caption as Brightness's is, the slider comes up to just under
    // its caption.
    const int step = (bottom - label.top - checkbox.height - gap) / (TextGroupCount + 1);
    const int captionHeight = (std::min)(label.height, step - track.height);
    const int pairOffset = (std::max)(captionHeight, (std::min)(track.top - label.top, step - track.height));
    // "Link Text Sizes" at the top of the column and the pairs under it, so the page opens on the
    // link and right from it reaches the fonts without passing every slider.
    PlaceCheckbox(s.linkSizes, Rect{label.left, label.top, label.width, checkbox.height}, gap);
    const int first = checkbox.height + gap;
    for (int i = 0; i <= TextGroupCount; ++i) {
        Rect l = label, t = track;
        l.top += first + i * step;
        l.height = captionHeight;
        t.top = l.top + pairOffset;
        void* caption = i < TextGroupCount ? s.sizeLabels[i] : s.iconLabel;
        void* slider = i < TextGroupCount ? s.sliders[i] : s.iconSlider;
        Extent(caption, l);
        Extent(slider, t);
        At<int>(slider, kSliderMaximum) = SliderMaximum;
        Extent(slider, t);
    }
    Text(s.linkSizes, "Link Text Sizes", true);
    for (void* mark : marks) { Text(mark, ""); At<std::uint8_t>(mark, kCtlFlags) &= ~kVisible; }
    s.defaultsGlyph = pad::Glyph{}; s.defaultsGlyph.label = marks[0]; s.defaultsGlyph.button = defaults; s.defaultsGlyph.code = 'y';
    s.saveGlyph = pad::Glyph{}; s.saveGlyph.label = marks[1]; s.saveGlyph.button = save; s.saveGlyph.code = 'x';
    s.backGlyph = pad::Glyph{}; s.backGlyph.label = marks[2]; s.backGlyph.button = back; s.backGlyph.code = 'b';
    for (void* button : {defaults, save, back}) pad::SkipFocus(button, true);
    kmrp::textfit::CaptionLike(save, defaults);
    // The right-hand column, inside the frame the player sees round the description list (item
    // 70): the frame stands 23/86 of the list's scrollbar width left of the list and ends 13/86
    // of it short of the scrollbar's strip, which it does not cover. The column keeps its left, a
    // 32nd of the list's width in from the list, and stays as far in from the frame on the right.
    Rect desc = RectOf(owner, "LB_DESC");
    {
        const int bar = At<int>(ControlByTag(owner, "LB_DESC"), kListBarWidth);
        const int inset = desc.width / 32;
        if (bar > 0 && bar < desc.width / 2) {
            const int outside = (bar * 23 + 43) / 86, shortOfStrip = (bar * 13 + 43) / 86;
            const int frameRight = desc.left + desc.width - bar - shortOfStrip;
            desc.left += inset;
            desc.width = frameRight - (inset + outside) - desc.left;
        } else {
            desc.left += inset;
            desc.width -= 2 * inset;
        }
    }
    const int margin = (std::max)(2, desc.height / 32);
    Rect choiceRect{desc.left, desc.top + margin, desc.width, RectOf(owner, "BTN_RESOLUTION").height};
    for (int i = 0; i < FontChoiceCount; ++i) {
        PlaceCheckbox(s.fontChoices[i], choiceRect, gap);
        choiceRect.top += choiceRect.height + gap;
    }
    // The icons' preview at the bottom, as tall as the largest icon and never more than half the
    // column under the fonts; one short sample per font group above it, each in the native
    // renderer.
    s.screenHeight = At<short>(manager, kManagerHeight);
    {
        const double scale = kmrp_icon_scale(s.screenHeight);
        const int biggest = kmrp_icon_drawn(kmrp_icon_feat_today(scale, KMRP_ICON_NATIVE), scale, KMRP_ICON_MAXIMUM);
        const int columnBottom = desc.top + desc.height - margin;
        const int room = (std::min)(biggest + 2 * margin, (columnBottom - choiceRect.top) / 2);
        s.iconArea = {desc.left, columnBottom - room, desc.width, room};
    }
    const int previewStep = (s.iconArea.top - choiceRect.top) / TextGroupCount;
    for (int i = 0; i < TextGroupCount; ++i) {
        Extent(s.previews[i], Rect{desc.left, choiceRect.top + i * previewStep, desc.width, previewStep});
        char* const params = static_cast<char*>(s.previews[i]) + kLabelTextParams;
        // SetBaseFont: the name, 16 characters and a zero, then ResetFont, which adds the
        // suffix of the screen's size.
        std::memset(params + kBaseFont, 0, 17);
        std::strncpy(params + kBaseFont, previewFonts[i], 16);
        ResetFont(params);
        Text(s.previews[i], previewTexts[i]);
    }
    // A native text control for save and application errors, hidden until a message needs it.
    Extent(s.help, Rect{desc.left, choiceRect.top, desc.width, desc.top + desc.height - choiceRect.top});
    At<std::uint8_t>(s.help, kCtlFlags) &= ~kVisible;
    for (int i = 0; i < 3; ++i) Text(s.iconPreviews[i], "");   // a picture, not the template's "Brightness"
    PlaceIconPreviews(kmrp::textfit::Live().icon);
    for (int i = 0; i < 3; ++i) {
        std::uint8_t& fill = At<std::uint8_t>(s.iconPreviews[i], kLabelParams + kParamsFlags);
        fill = static_cast<std::uint8_t>((fill & ~3u) | 2u);   // drawn at the label's size, which is the icon's
        pad::SetFill(static_cast<char*>(s.iconPreviews[i]) + kLabelParams, iconPreviewNames[i]);
    }
    Text(title, "Text Size and Font");
    Text(s.fontChoices[ChoiceOf(Original)], "Original Font", true);
    Text(s.fontChoices[ChoiceOf(HdOriginal)], "HD Font", true);
    AddEvent(s.linkSizes, kEventA, p, reinterpret_cast<void*>(&ToggleLink), 0);
    AddEvent(s.fontChoices[ChoiceOf(Original)], kEventA, p, reinterpret_cast<void*>(&SelectOriginal), 0);
    AddEvent(s.fontChoices[ChoiceOf(HdOriginal)], kEventA, p, reinterpret_cast<void*>(&SelectHdOriginal), 0);
    AddEvent(defaults, kEventA, p, reinterpret_cast<void*>(&Defaults), 0);
    AddEvent(save, kEventA, p, reinterpret_cast<void*>(&SaveClicked), 0);
    AddEvent(back, kEventA, p, reinterpret_cast<void*>(&Back), 0);
    std::memcpy(s.saveCaption, &At<float>(save, kButtonTextParams + kTextColour), sizeof s.saveCaption);
    std::memcpy(s.saveFrame, &At<float>(save, kButtonFrameColour), sizeof s.saveFrame);
    // The pad's focus: the link and the sliders under it, up and down and round; the fonts, up and
    // down and round; left and right between the link and the font chosen (UpdateCaptions), and
    // nothing from a slider, whose left and right move it. Default, Save and Close are off the
    // pad's focus; their links are the keys'.
    Navigation(s.linkSizes, s.iconSlider, s.sliders[0]);
    for (int i = 0; i < TextGroupCount; ++i)
        Navigation(s.sliders[i], i ? s.sliders[i - 1] : s.linkSizes, i + 1 < TextGroupCount ? s.sliders[i + 1] : s.iconSlider);
    Navigation(s.iconSlider, s.sliders[TextGroupCount - 1], s.linkSizes);
    Navigation(s.fontChoices[0], s.fontChoices[1], s.fontChoices[1], s.linkSizes, s.linkSizes);
    Navigation(s.fontChoices[1], s.fontChoices[0], s.fontChoices[0], s.linkSizes, s.linkSizes);
    Navigation(defaults, s.iconSlider, s.linkSizes, back, back);
    Navigation(back, s.fontChoices[FontChoiceCount - 1], s.fontChoices[0], defaults, defaults);
    SetActive(p, s.linkSizes, 0);
    s.displayedSizes.fill(-1);
    s.displayedLinked = s.displayedStyle = s.displayedIcon = -1;
    s.releasedFrames = 0;
    UpdateCaptions();
    UpdateSaveButton();
    // The pad's glyphs before the page is shown, not on its next frame.
    {
        const bool padInUse = pad::PadInUse();
        const char family = pad::Family();
        pad::Update(s.defaultsGlyph, padInUse, family);
        pad::Update(s.saveGlyph, padInUse && Unsaved(), family);
        pad::Update(s.backGlyph, padInUse, family);
    }
    AddPanel(manager, p, 3, 1);
}

void UpdateEntry(void* owner, EntryButton& e) {
    void* advanced = kmrp::panels::ControlByTag(owner, "BTN_ADVANCED");
    if (VtableOf(advanced) != kButtonTable) return;
    if (!e.button) {
        e.button = CloneButton(owner, advanced);
        if (!e.button) return;
        Text(e.button, "Text Size and Font", true);
        AddEvent(e.button, kEventA, owner, reinterpret_cast<void*>(&Open), 0);
    }
    const Rect wanted = KmrpTextOptions::Entry(At<Rect>(advanced, kExtent));
    if (std::memcmp(&At<Rect>(e.button, kExtent), &wanted, sizeof wanted)) Extent(e.button, wanted);
    // Follow the button's native focus policy, including skins that change it.
    std::uint8_t& flags = At<std::uint8_t>(e.button, kCtlFlags);
    flags = (flags & ~4u) | (At<std::uint8_t>(advanced, kCtlFlags) & 4u);
    void* above = At<void*>(advanced, kNavUp);
    if (above != e.button) {
        Navigation(e.button, above, advanced, At<void*>(advanced, kNavLeft), At<void*>(advanced, kNavRight));
        At<void*>(advanced, kNavUp) = e.button;
        if (above && above != advanced && At<void*>(above, kNavDown) == advanced) At<void*>(above, kNavDown) = e.button;
    }
}
void EntryBadge(void* owner, EntryButton& e, bool padInUse, char family) {
    if (!e.button) return;
    const bool want = padInUse && !P().current && !kmrp::hud::PageOpen() && At<void*>(owner, kPanelActive) == e.button;
    if (int(want) == e.badged && (!want || family == e.family)) return;
    pad::EntryBadge(e.button, want);
    e.badged = want;
    e.family = family;
}
void Error(const char* message) {
    Page& p = P();
    if (!p.help) return;
    std::uint8_t& flags = At<std::uint8_t>(p.help, kCtlFlags);
    flags = message ? (flags | kVisible) : (flags & ~kVisible);
    for (void* preview : p.previews) {
        if (!preview) continue;
        std::uint8_t& shown = At<std::uint8_t>(preview, kCtlFlags);
        shown = message ? (shown & ~kVisible) : (shown | kVisible);
    }
    if (message) Text(p.help, message);
}
void ReloadFonts(bool images) {
    kmrp::fonts::Reload(images);
    kmrp::fonts::ReflowPanels();
}
// The HD atlases, for the sizes in use. Original Font keeps its atlas at every size, so its metrics
// are all there is. A failure leaves the text as it was, stretched and readable.
bool FitFonts() {
    Page& p = P();
    const Settings& live = kmrp::textfit::Live();
    if (live.style == Original || p.fitted.values == live.sizing.values) return true;
    if (!kmrp::fonts::Apply()) return false;
    ReloadFonts(true);
    p.fitted = live.sizing;
    return true;
}
void FinishSave() {
    Page& p = P();
    const bool close = p.closeAfterSave;
    p.closeAfterSave = false;
    Settings& live = kmrp::textfit::Live();
    if (FitFonts() && kmrp::textfit::WriteSettings(live)) {
        kmrp::textfit::Saved() = live;
        Error(nullptr);
        if (close) Close();
    } else {
        Error("Could not save settings.\nChanges apply this session.");
    }
}

}  // namespace

extern "C" __attribute__((visibility("default"))) void* KmrpTextOptionsEntryK1(void* owner) {
    Page& p = P();
    const auto found = p.entries.find(owner);
    return found == p.entries.end() ? nullptr : found->second.button;
}
extern "C" __attribute__((visibility("default"))) int KmrpTextOptionsOpenK1() { return P().current != nullptr; }

namespace kmrp {
namespace text {

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
        EntryButton& e = p.entries[panel];
        UpdateEntry(panel, e);
        EntryBadge(panel, e, padInUse, family);
    }
    if (p.current) {
        pad::Update(p.defaultsGlyph, padInUse, family);
        pad::Update(p.saveGlyph, padInUse && Unsaved() && !p.saveFrames, family);
        pad::Update(p.backGlyph, padInUse, family);
    }
    if (p.pending) {
        void* owner = p.pending;
        p.pending = nullptr;
        if (!p.current && PanelExists(manager, owner)) MakeScreen(manager, owner);
    }
    if (p.current && p.sliders[0] && !p.dirty) {
        for (int i = 0; i < TextGroupCount; ++i) {
            const int moved = Minimum + (std::max)(0, (std::min)(SliderMaximum, At<int>(p.sliders[i], kSliderValue))) * Step;
            if (moved != p.requestedSizing.values[i]) { p.requestedSizing.Set(i, moved); Dirty(); break; }
        }
    }
    // The Icon Size slider: its caption, preview and size follow it at once.
    Settings& live = textfit::Live();
    if (p.current && p.iconSlider) {
        const int moved = Minimum + (std::max)(0, (std::min)(SliderMaximum, At<int>(p.iconSlider, kSliderValue))) * Step;
        if (moved != p.requestedIcon) { p.requestedIcon = moved; UpdateCaptions(); PlaceIconPreviews(moved); }
    }
    if (p.requestedIcon != live.icon) {
        live.icon = p.requestedIcon;   // the rows follow in the next frame (text_rows.cpp, ApplyIconRows)
        PlaceIconPreviews(live.icon);
        UpdateCaptions();
    }
    if (p.dirty) {
        const Sizes previous = live.sizing;
        const int previousFont = live.style;
        live.sizing = p.requestedSizing;
        live.style = p.requestedStyle;
        p.dirty = false;
        if (previousFont == live.style || fonts::Apply()) {
            if (previous.values != live.sizing.values || previousFont != live.style) ReloadFonts(previousFont != live.style);
            // A change of font has just fitted every atlas, so it can be seen as it will be.
            if (previousFont != live.style) p.fitted = live.sizing;
            Error(nullptr);
        } else {
            live.sizing = p.requestedSizing = previous;
            live.style = p.requestedStyle = previousFont;
            fonts::Apply();
            Error("Font could not be changed.\nPrevious selection kept.");
        }
        UpdateCaptions();
    }
    if (p.saveFrames && --p.saveFrames == 0) FinishSave();
    if (p.closeAfterDiscard && !p.dirty) {
        p.closeAfterDiscard = false;
        FitFonts();   // those made since it was opened are for sizes no longer in use
        Close();
    }
    UpdateSaveButton();
}

}  // namespace text
}  // namespace kmrp
