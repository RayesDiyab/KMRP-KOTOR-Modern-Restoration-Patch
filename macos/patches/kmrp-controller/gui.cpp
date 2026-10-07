// KMRP for macOS, controller support: menus.
//
// The Mac port of K1NativeJoystick.cpp's focus-navigation layer, with the same rules and the
// same per-screen knowledge; the reasoning behind each rule is written there and in
// docs/controller-behaviour-matrix.md, and is summarised here only where the Mac differs.
//
// KOTOR navigates its screens with the mouse, and the retained console events reach only the
// focused control, which on most screens nothing focuses. This layer gives the pad a focus to
// move: geometric, for any panel, standing down wherever a screen or control navigates itself.
//
// What differs on the Mac, all read from its code (KOTOR_Exe 1.4.0, x86_64):
//   - the layouts are 64-bit: CSWGuiManager panels +0xD8/+0xE0; CSWGuiPanel manager +0x20,
//     active control +0x28, controls +0x30/+0x38, flags (a word) +0x5C; CSWGuiControl extent
//     +0x08..+0x14, events +0x58/+0x60 in 0x20-byte entries {receiver, handler, this-adjust,
//     event}, flags (a byte) +0x68; HandleInputEvent is vtable +0x80 (Windows +0x3C: one slot
//     later, the Itanium ABI's second destructor).
//   - a button that presses A, B, X or Y on its own panel is registered with a pointer to
//     CSWGuiPanel's virtual OnAButtonPressed and the rest (vtable +0xA8..+0xC0, each
//     HandleInputEvent(event, 1) on the panel), which the Itanium ABI stores as the vtable
//     offset + 1: 72 of the image's AddEvent calls do it that way. Windows reaches the same
//     methods through MSVC's vcall thunks.
//   - the guards Windows makes as KPM hooks rewriting the event on the stack (the chargen,
//     Solo Mode and resolution confirms) are wrappers in the panel's vtable here: on x86_64
//     the event is a register, which a KPM detour cannot rewrite. Each wrapper applies the same
//     test and calls the original dispatcher with the event it decided on.
//   - the echo guard replaces CSWGuiPanel::HandleInputEvent (0x10049dc72, 28 bytes) whole,
//     where Windows hooks it: the same function, reached by every panel that does not override
//     it and by every override's call to its base.
//   - per-screen control offsets come from the Mac's own bind calls, by tag
//     (work/port/mac_control_offsets.py in the port's workspace, KMRP's
//     tools/extract_control_offsets.py for Windows).
#include "gui.h"

#include "engine.h"
#include "hud.h"
#include "layout.h"
#include "pad.h"
#include "prompts.h"
#include "state.h"
#include "../kmrp-layout/options.h"
#include "../kmrp-layout/text.h"
#include "standalone.h"

#include <mach/mach.h>
#include <mach/mach_vm.h>

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace kmrp {
namespace gui {
namespace {

using engine::At;

// ------------------------------------------------------------------------ layout

const std::size_t kMgrPanels = 0xd8, kMgrPanelCount = 0xe0;
const std::size_t kPanelManager = 0x20, kPanelActive = 0x28, kPanelControls = 0x30, kPanelControlCount = 0x38;
const std::size_t kPanelFlags = 0x5c;
const std::uint16_t kPanelFlagSkip = 0x600;   // CSWGuiManager's "not in front" bits, as on Windows
const std::size_t kCtlX = 0x08, kCtlY = 0x0c, kCtlW = 0x10, kCtlH = 0x14;
const std::size_t kCtlEvents = 0x58, kCtlEventCount = 0x60, kCtlFlags = 0x68;
const std::uint8_t kCtlVisible = 0x02, kCtlSelectable = 0x08, kCtlDisabled = 0x20;
const std::size_t kEntryBytes = 0x20, kEntryReceiver = 0x00, kEntryHandler = 0x08, kEntryAdjust = 0x10,
                  kEntryEvent = 0x18;
const std::size_t kVtHandleInput = 0x80;

using HandleFn = void (*)(void* object, int event, int value);
using PanelFn = void (*)(void* panel);
using FeatPickedFn = void (*)(void* panel, int feat);
using SetActiveControlFn = void (*)(void* panel, void* control, int playSound);
using PlayGuiSoundFn = void (*)(void* manager, int sound);

// CSWGuiPanel::SetActiveControl (Windows 0x0040A630): exit to the old control, enter to the
// new, and the GUI sound. CSWGuiManager::PlayGuiSound (Windows 0x0040A140), which it calls.
SetActiveControlFn SetActiveControl() { return reinterpret_cast<SetActiveControlFn>(0x10049de24UL); }
PlayGuiSoundFn PlayGuiSound() { return reinterpret_cast<PlayGuiSoundFn>(0x10049dea0UL); }

// Dispatchers: the vtable +0x80 of each class, named as in K1NativeJoystick.cpp.
const std::uintptr_t kInGameMenu = 0x100304a86UL;     // CSWGuiInGameMenu, the tab strip
const std::uintptr_t kListBox = 0x1004a8a38UL;
const std::uintptr_t kNavigable = 0x1004a4972UL;      // CSWGuiNavigable / edit box
const std::uintptr_t kSlider = 0x1004a694cUL;
const std::uintptr_t kButtonHandle = 0x1004a5ccaUL;   // CSWGuiButton
const std::uintptr_t kControlHandle = 0x1004a4a94UL;  // CSWGuiControl
const std::uintptr_t kAbilities = 0x10022d672UL, kFeats = 0x1002eedd2UL, kMap = 0x1002b572eUL;
const std::uintptr_t kPowers = 0x1002c36baUL, kWager = 0x10021e566UL, kStatusSummary = 0x10030766cUL;
const std::uintptr_t kCharacter = 0x1002e9612UL, kSkillInfo = 0x10028ea9aUL, kEquip = 0x1002bd2a8UL;
const std::uintptr_t kInventory = 0x10024be8aUL, kAttributesChargen = 0x100349572UL;
const std::uintptr_t kSkillsChargen = 0x100250a12UL, kPortraitChargen = 0x10033fccaUL;
const std::uintptr_t kNameChargen = 0x1002aa9f4UL, kResolution = 0x1002cdb5aUL, kJournal = 0x10032e7e6UL;
const std::uintptr_t kSoloModeQuery = 0x1002c826aUL;

// GUI events.
const int kEventA = 0x27, kEventB = 0x28, kEventX = 0x29, kEventY = 0x2A, kEventBlack = 0x2B;
const int kEventConfirmAlias = 0x2D;
const int kEventLeft = 0x2F, kEventRight = 0x30, kEventUp = 0x31, kEventDown = 0x32;
const int kEventPrevScreen = 0x35, kEventNextScreen = 0x36, kEventDescUp = 0x39, kEventDescDown = 0x3A;
const int kEventChangeChar = 0xCE;   // a screen's "next party member" (0x09 is the world's)
const int kSlotA = 0x74, kSlotX = 0x76, kSlotY = 0x77;

// Timing, K1NativeJoystick.cpp's.
const std::uint64_t kNavHoldDelayMs = 400, kNavRepeatMs = 120;
const float kNavStickEngage = 0.55f, kNavStickRelease = 0.35f;
const float kDescStickEngage = 0.45f, kDescStickRelease = 0.25f;
const int kNavCrossAxisPenalty = 6, kNavOverlapPenalty = 2;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

std::uintptr_t VtableOf(void* object) {
    return LooksLikePointer(object) ? *reinterpret_cast<std::uintptr_t*>(object) : 0;
}

// ------------------------------------------------------------------------ guarded dispatchers

// The vtables whose dispatcher slot this module points at a guard, and each original, so a
// dispatcher lookup still answers with the class's own function.
struct Guarded {
    const char* name;
    std::uintptr_t vtable;     // the value an object of the class holds at +0
    std::uintptr_t original;   // its dispatcher, checked before the slot is changed
    void* wrapper;
    bool installed;
};
Guarded* GuardedList(std::size_t* count);

std::uintptr_t Dispatcher(void* object) {
    const std::uintptr_t vtable = VtableOf(object);
    if (!LooksLikePointer(reinterpret_cast<void*>(vtable))) return 0;
    const std::uintptr_t slot = *reinterpret_cast<std::uintptr_t*>(vtable + kVtHandleInput);
    std::size_t n = 0;
    Guarded* list = GuardedList(&n);
    for (std::size_t i = 0; i < n; ++i)
        if (list[i].installed && slot == reinterpret_cast<std::uintptr_t>(list[i].wrapper)) return list[i].original;
    return slot;
}

// Hands an event to an object's own HandleInputEvent, through its vtable, as the engine does.
void Handle(void* object, int event, int value) {
    const std::uintptr_t vtable = VtableOf(object);
    if (!vtable) return;
    reinterpret_cast<HandleFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtHandleInput))(object, event, value);
}

bool InList(std::uintptr_t value, const std::uintptr_t* list, std::size_t count) {
    for (std::size_t i = 0; i < count; ++i)
        if (list[i] == value) return true;
    return false;
}
template <std::size_t N> bool InList(std::uintptr_t value, const std::uintptr_t (&list)[N]) {
    return InList(value, list, N);
}

// ------------------------------------------------------------------------ per-screen knowledge

// Panels on which the pad never moves the focus (K1_NO_PAD_FOCUS_PANELS): each answers its
// buttons itself and then hands the same event to the focused control, whose click raises it
// again.
const std::uintptr_t kNoPadFocusPanels[] = {kStatusSummary, kCharacter, kSkillInfo};

// Panels whose own dispatcher implements the direction events (K1_NATIVE_DIRECTION_PANELS).
const std::uintptr_t kNativeDirectionPanels[] = {kAbilities, kFeats, kMap, kPowers, kWager};

// Controls that consume the direction events themselves (K1_NATIVE_DIRECTION_CONTROLS).
const std::uintptr_t kNativeDirectionControls[] = {kNavigable, kListBox, kSlider};

// The four screens about a party member, which implement 0xCE (K1_PARTY_SWITCH_PANELS).
const std::uintptr_t kPartySwitchPanels[] = {kAbilities, kCharacter, kEquip, kInventory};

// Screens whose A is resolved by their own guard (K1_OWN_CONFIRM_DISPATCHERS).
const std::uintptr_t kOwnConfirmPanels[] = {kAttributesChargen, kSkillsChargen, kFeats, kPowers,
                                            kPortraitChargen, kNameChargen, kResolution};

// The description pane of each screen (FindK1DescriptionListbox): the focus layer never
// focuses it, and the right stick scrolls it. By class; the Mac has no Advanced Sound screen.
struct Offset {
    std::uintptr_t vtable;
    std::size_t offset;
};
const Offset kDescriptionPanes[] = {
    {0x1005aba30UL, 0x1fe8},   // CSWGuiInGameOptions LB_DESC
    {0x1005a76d0UL, 0x3b0},    // CSWGuiInGameGameplay LB_DESC
    {0x1005a5d30UL, 0x1c40},   // CSWGuiInGameAutoPause LB_DETAILS
    {0x1005abfe0UL, 0x1370},   // CSWGuiOptionsMain LB_DESC
    {0x1005ac0d0UL, 0x750},    // CSWGuiOptionsFeedback LB_DESC
    {0x1005ac580UL, 0x3b0},    // CSWGuiOptionsMouse LB_DESC
    {0x1005ac1c0UL, 0x770},    // CSWGuiOptionsGraphics LB_DESC
    {0x1005ac2b0UL, 0x3b0},    // CSWGuiOptionsGraphicsAdvanced LB_DESC
    {0x1005ac490UL, 0x12b0},   // CSWGuiOptionsSound LB_DESC
    {0x1005a5180UL, 0x1f08},   // CSWGuiUpgrade LB_DESC
    {0x1005a5090UL, 0x420},    // CSWGuiUpgradeItemSelect LB_DESCRIPTION
    {0x1005a75c0UL, 0xa80},    // CSWGuiInGameInventory LB_DESCRIPTION
    {0x1005ad040UL, 0x2160},   // CSWGuiStore LB_DESCRIPTION
    {0x1005a5f80UL, 0x4010},   // CSWGuiInGameAbilities LB_DESC
    {0x1005adc40UL, 0x1d20},   // CSWGuiFeatsCharGen LB_DESC
    {0x1005abb40UL, 0x1420},   // CSWGuiPowersLevelUp LB_DESC
    {0x1005ab508UL, 0x41e8},   // CSWGuiInGameEquip LB_DESC
};

// Y is Default on the settings screens that have one (K1_DEFAULT_BUTTONS).
const Offset kDefaultButtons[] = {
    {0x1005a5d30UL, 0x1a00},   // CSWGuiInGameAutoPause BTN_DEFAULT
    {0x1005a76d0UL, 0x990},    // CSWGuiInGameGameplay BTN_DEFAULT
    {0x1005ac0d0UL, 0xd30},    // CSWGuiOptionsFeedback BTN_DEFAULT
    {0x1005ac1c0UL, 0x1d00},   // CSWGuiOptionsGraphics BTN_DEFAULT
    {0x1005ac2b0UL, 0x27d8},   // CSWGuiOptionsGraphicsAdvanced BTN_DEFAULT
    {0x1005ac580UL, 0x990},    // CSWGuiOptionsMouse BTN_DEFAULT
    {0x1005ac490UL, 0x1890},   // CSWGuiOptionsSound BTN_DEFAULT
    {0x1005a72d0UL, 0x228},    // CSWGuiInGameOptKeyMappings BTN_Default
};

// Settings rows stepped by a - and a + either side of their value (K1_CYCLE_ROWS). Left and
// Right press the arrows and the focus stays on the value. The Mac's Graphics screen steps its
// resolution in place (Windows opens a box), so that row is here as well.
struct CycleRow {
    std::uintptr_t vtable;
    std::size_t value, lower, raise;
};
const CycleRow kCycleRows[] = {
    {0x1005a76d0UL, 0x1050, 0x14d0, 0x1290},   // Gameplay: Difficulty
    {0x1005ac2b0UL, 0x1ed8, 0x2118, 0x2358},   // Advanced Graphics: Texture Quality
    {0x1005ac2b0UL, 0x1818, 0x1a58, 0x1c98},   //   Anti-aliasing
    {0x1005ac2b0UL, 0x1158, 0x1398, 0x15d8},   //   Anisotropy
    {0x1005ac1c0UL, 0xb10, 0xd50, 0xf90},      // Graphics: Resolution
};

// Character creation's points screens, Attributes and Skills (K1_POINTS_SCREENS): the rows
// are their value buttons (*_POINTS_BTN) top to bottom as drawn, the strip Recommended, OK,
// Cancel. lower and raise are what each dispatcher calls on Left and Right (0x100349754 and
// 0x100349968 on Attributes, the latter named OnAcceptButton in KPM's Mac database; 0x100250c56
// and 0x100250e1e on Skills).
struct PointsScreen {
    std::uintptr_t dispatcher;
    std::uintptr_t lower, raise;
    int rowCount;
    std::size_t rows[8];
    std::size_t strip[3];
};
const PointsScreen kPointsScreens[] = {
    // STR DEX CON INT WIS CHA as drawn; INT and WIS are bound the other way round.
    {kAttributesChargen, 0x100349754UL, 0x100349968UL, 6,
     {0x1f48, 0x2188, 0x23c8, 0x2848, 0x2608, 0x2a88}, {0x3148, 0x2cc8, 0x2f08}},
    // Computer Use, Demolitions, Stealth, Awareness, Persuade, Repair, Security, Treat Injury.
    {kSkillsChargen, 0x100250c56UL, 0x100250e1eUL, 8,
     {0x20e0, 0x2320, 0x2560, 0x27a0, 0x29e0, 0x2c20, 0x2e60, 0x30a0}, {0x3760, 0x32e0, 0x3520}},
};

const PointsScreen* PointsScreenFor(std::uintptr_t dispatcher) {
    for (const PointsScreen& s : kPointsScreens)
        if (s.dispatcher == dispatcher) return &s;
    return nullptr;
}

// Buttons that raise A, B, X or Y on their own panel (K1_RAISE_THUNKS): CSWGuiPanel's
// OnAButtonPressed, OnBButtonPressed, OnXButtonPressed and OnYButtonPressed (its vtable
// +0xA8..+0xC0), each HandleInputEvent(event, 1) on the panel, and a second copy of the B one.
struct RaiseThunk {
    std::uintptr_t handler;
    int event;
};
const RaiseThunk kRaiseThunks[] = {
    {0x1002abb40UL, kEventA}, {0x100303210UL, kEventB}, {0x10021e4e6UL, kEventB},
    {0x1002154b0UL, kEventX}, {0x10021c4e0UL, kEventY},
};

// Solo Mode's query (a message box) and the resolution box: their Cancel buttons.
const std::size_t kMessageBoxCancel = 0x610, kResolutionCancel = 0x7f8;

// Feats (CSWGuiFeatsCharGen): its dispatcher answers A with "add the highlighted feat" and X
// with OK, the reverse of every other screen; KMRP swaps them. OnAccept is what its X calls
// (0x1002ee8ce), OnFeatPicked what its A calls (0x1002eefd0) with the grid's highlighted feat.
const std::uintptr_t kFeatsOnAccept = 0x1002ee8ceUL, kFeatsOnFeatPicked = 0x1002eefd0UL;

// ------------------------------------------------------------------------ state

struct State {
    // navigation: what the input hook asks, what the GUI frame does
    int navHeldX = 0, navHeldY = 0, navPendingX = 0, navPendingY = 0;
    std::uint64_t navRepeatDeadline = 0;
    int stickNavX = 0, stickNavY = 0;
    int descHeld = 0;
    std::uint64_t descDeadline = 0;
    int remapSlot = 0;
    std::uint64_t remapRequested = 0;
    bool allowSelfNavigating = false;   // while scanning a tab's content panel
    void* pointsPanel = nullptr;
    int pointsRow = -1;
    struct { bool active; int reentries; } chargenPress = {false, 0};
    // counters
    unsigned long navMoves = 0, navDeclined = 0, dispatched = 0, descScrolls = 0, remaps = 0;
    unsigned long partySwitches = 0, echoesStopped = 0, focusedPresses = 0, confirmGuards = 0;
} g;

// ------------------------------------------------------------------------ the panel stack

void* Manager() {
    void* internal = engine::ClientInternal();
    return internal ? At<void*>(internal, engine::kInternalGuiManager) : nullptr;
}

int PanelCount() {
    void* manager = Manager();
    if (!LooksLikePointer(manager)) return 0;
    const int count = At<int>(manager, kMgrPanelCount);
    return count > 0 && count <= 256 ? count : 0;
}

void* PanelAt(int index) {
    void* manager = Manager();
    if (!LooksLikePointer(manager)) return nullptr;
    void** panels = At<void**>(manager, kMgrPanels);
    if (!LooksLikePointer(panels) || index < 0 || index >= PanelCount()) return nullptr;
    return LooksLikePointer(panels[index]) ? panels[index] : nullptr;
}

bool Skipped(void* panel) { return (At<std::uint16_t>(panel, kPanelFlags) & kPanelFlagSkip) != 0; }

// The panel in front: the last in the list without the skip bits (CSWGuiManager::IsOnTop).
void* TopPanel() {
    for (int i = PanelCount() - 1; i >= 0; --i) {
        void* panel = PanelAt(i);
        if (panel && !Skipped(panel)) return panel;
    }
    return nullptr;
}

void* PanelWithDispatcher(std::uintptr_t dispatcher) {
    for (int i = PanelCount() - 1; i >= 0; --i) {
        void* panel = PanelAt(i);
        if (panel && !Skipped(panel) && Dispatcher(panel) == dispatcher) return panel;
    }
    return nullptr;
}

// The in-game menu's tab strip, when it is the panel in front (TabBarPanelK1).
void* TabBarPanel() {
    void* top = TopPanel();
    return top && Dispatcher(top) == kInGameMenu ? top : nullptr;
}

struct Rect {
    int x, y, w, h;
    int cx() const { return x + w / 2; }
    int cy() const { return y + h / 2; }
};

// Actionable: visible, not disabled, selectable, with a real size, and answering something
// (ControlIsNavigableK1). A control with no events is decoration (the main menu's full-screen
// background passes every other test), unless it is a list, edit box or slider on a tab's
// content, which answer through their own class.
bool Navigable(void* control, Rect& rect) {
    if (!LooksLikePointer(control)) return false;
    const std::uint8_t flags = At<std::uint8_t>(control, kCtlFlags);
    if (!(flags & kCtlVisible) || (flags & kCtlDisabled) || !(flags & kCtlSelectable)) return false;
    void* events = At<void*>(control, kCtlEvents);
    const int eventCount = At<int>(control, kCtlEventCount);
    if (!LooksLikePointer(events) || eventCount <= 0 || eventCount > 64) {
        if (!g.allowSelfNavigating || !InList(Dispatcher(control), kNativeDirectionControls)) return false;
    }
    rect = {At<int>(control, kCtlX), At<int>(control, kCtlY), At<int>(control, kCtlW), At<int>(control, kCtlH)};
    return rect.w > 0 && rect.h > 0;
}

bool HasNavigableControl(void* panel) {
    void** controls = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    if (!LooksLikePointer(controls) || count <= 0 || count > 512) return false;
    Rect rect{};
    for (int i = 0; i < count; ++i)
        if (Navigable(controls[i], rect)) return true;
    return false;
}

// The content panel for the tab on screen: the topmost panel below the strip with anything to
// focus (TabContentPanelK1).
void* TabContentPanel(void* tabBar) {
    if (!tabBar) return nullptr;
    const bool allow = g.allowSelfNavigating;
    g.allowSelfNavigating = true;
    void* found = nullptr;
    for (int i = PanelCount() - 1; i >= 0 && !found; --i) {
        void* panel = PanelAt(i);
        if (panel && panel != tabBar && !Skipped(panel) && HasNavigableControl(panel)) found = panel;
    }
    g.allowSelfNavigating = allow;
    return found;
}

// Where a direction press acts: a tab's content when the menu is open, else the panel in
// front (NavigationPanelK1). The strip itself is never the answer: LT and RT change tabs.
void* NavigationPanel(void** outTabBar) {
    void* tabBar = TabBarPanel();
    if (outTabBar) *outTabBar = tabBar;
    return tabBar ? TabContentPanel(tabBar) : TopPanel();
}

void* DescriptionPane(void* panel) {
    const std::uintptr_t vtable = VtableOf(panel);
    for (const Offset& d : kDescriptionPanes) {
        if (d.vtable != vtable) continue;
        void* control = static_cast<char*>(panel) + d.offset;
        return (At<std::uint8_t>(control, kCtlFlags) & kCtlVisible) ? control : nullptr;
    }
    return nullptr;
}

int Overlap(int aStart, int aSize, int bStart, int bSize) {
    const int lo = aStart > bStart ? aStart : bStart;
    const int hi = aStart + aSize < bStart + bSize ? aStart + aSize : bStart + bSize;
    return hi - lo;
}

// The control a press in (dx, dy) moves to (ChooseNeighbourK1): the nearest ahead, keeping to
// its row or column, and wrapping to the farthest the other way at the end.
void* ChooseNeighbour(void* panel, void* current, int dx, int dy) {
    void** controls = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    if (!LooksLikePointer(controls) || count <= 0 || count > 512) return nullptr;
    Rect from{};
    const bool haveCurrent = Navigable(current, from);
    void* const descriptionPane = DescriptionPane(panel);
    void* best = nullptr;
    long bestScore = 0;
    void* wrap = nullptr;
    long wrapScore = 0;
    for (int i = 0; i < count; ++i) {
        void* candidate = controls[i];
        if (candidate == current || candidate == descriptionPane) continue;
        Rect to{};
        if (!Navigable(candidate, to)) continue;
        if (!haveCurrent) {   // nothing focused: the topmost, then leftmost
            const long score = static_cast<long>(to.y) * 10000L + to.x;
            if (!best || score < bestScore) { best = candidate; bestScore = score; }
            continue;
        }
        const int along = dx != 0 ? to.cx() - from.cx() : to.cy() - from.cy();
        const int cross = dx != 0 ? std::abs(to.cy() - from.cy()) : std::abs(to.cx() - from.cx());
        const int overlap = dx != 0 ? Overlap(from.y, from.h, to.y, to.h) : Overlap(from.x, from.w, to.x, to.w);
        const int forward = along * (dx != 0 ? dx : dy);
        const long score = static_cast<long>(forward) +
                           static_cast<long>(cross) * (overlap > 0 ? kNavOverlapPenalty : kNavCrossAxisPenalty);
        if (forward > 0) {
            if (!best || score < bestScore) { best = candidate; bestScore = score; }
        } else if (!wrap || score < wrapScore) {
            wrap = candidate;
            wrapScore = score;
        }
    }
    return best ? best : wrap;
}

enum class Axis { Any, Horizontal, Vertical };

// A slider takes only the axis it slides along (ControlOwnsAxisK1).
bool ControlOwnsAxis(void* control, std::uintptr_t dispatcher, Axis axis) {
    if (dispatcher != kSlider || axis == Axis::Any) return true;
    const bool horizontal = At<int>(control, kCtlH) <= At<int>(control, kCtlW);
    return horizontal == (axis == Axis::Horizontal);
}

bool NavigatesItself(void* panel, void* active, bool reachable, Axis axis) {
    if (reachable && InList(Dispatcher(panel), kNativeDirectionPanels)) return true;
    const std::uintptr_t d = Dispatcher(active);
    return d != 0 && InList(d, kNativeDirectionControls) && ControlOwnsAxis(active, d, axis);
}

bool SetFocus(void* panel, void* target) {
    if (!panel || !target) return false;
    SetActiveControl()(panel, target, 1);
    ++g.navMoves;
    return true;
}

void Sound(void* panel, int sound) {
    if (void* manager = At<void*>(panel, kPanelManager)) PlayGuiSound()(manager, sound);
}

bool Clickable(void* control) {
    if (!LooksLikePointer(control)) return false;
    const std::uint8_t flags = At<std::uint8_t>(control, kCtlFlags);
    return (flags & kCtlVisible) && !(flags & kCtlDisabled);
}

const CycleRow* CycleRowFor(void* panel, void* control) {
    if (!control) return nullptr;
    const std::uintptr_t vtable = VtableOf(panel);
    char* base = static_cast<char*>(panel);
    for (const CycleRow& row : kCycleRows)
        if (row.vtable == vtable &&
            (control == base + row.value || control == base + row.lower || control == base + row.raise))
            return &row;
    return nullptr;
}

// Left or Right on a stepped row: its - or +, pressed as a click, with the focus kept on the
// value (StepCycleRowK1).
void StepCycleRow(void* panel, void* active, const CycleRow& row, int dx) {
    char* base = static_cast<char*>(panel);
    if (active != base + row.value) SetFocus(panel, base + row.value);
    void* arrow = base + (dx < 0 ? row.lower : row.raise);
    if (!Clickable(arrow)) return;   // hidden at the end of its range
    Sound(panel, 1);
    Handle(arrow, kEventA, 1);
}

// Attributes and Skills (NavigatePointsScreenK1): Up/Down walk the rows and reach OK from the
// last, Left/Right change the row's value on a row and walk the strip on the strip.
bool NavigatePointsScreen(void* panel, void* active, const PointsScreen& s, int dx, int dy) {
    auto control = [panel](std::size_t offset) { return static_cast<void*>(static_cast<char*>(panel) + offset); };
    if (g.pointsPanel != panel) { g.pointsPanel = panel; g.pointsRow = -1; }
    int strip = -1, row = -1;
    for (int i = 0; i < 3; ++i) if (active == control(s.strip[i])) strip = i;
    for (int i = 0; i < s.rowCount; ++i) if (active == control(s.rows[i])) row = i;
    if (row < 0 && strip < 0 && active) {   // a - or + in focus: the row it sits in
        const int y = At<int>(active, kCtlY) + At<int>(active, kCtlH) / 2;
        for (int i = 0; i < s.rowCount; ++i) {
            const int top = At<int>(control(s.rows[i]), kCtlY);
            if (y >= top && y < top + At<int>(control(s.rows[i]), kCtlH)) row = i;
        }
    }
    if (row >= 0) g.pointsRow = row;
    if (strip >= 0) {
        if (dx != 0) {
            const int next = strip + (dx < 0 ? -1 : 1);
            if (next >= 0 && next < 3) SetFocus(panel, control(s.strip[next]));
        } else if (dy < 0) {
            const int back = g.pointsRow >= 0 ? g.pointsRow : s.rowCount - 1;
            SetFocus(panel, control(s.rows[back]));
            g.pointsRow = back;
        }
        return true;
    }
    if (row < 0) {
        row = g.pointsRow >= 0 ? g.pointsRow : 0;
        SetFocus(panel, control(s.rows[row]));
        g.pointsRow = row;
        return true;
    }
    if (dy != 0) {
        const int next = row + (dy < 0 ? -1 : 1);
        if (next >= s.rowCount) {
            SetFocus(panel, control(s.strip[1]));   // OK, directly below
        } else if (next >= 0) {
            SetFocus(panel, control(s.rows[next]));
            g.pointsRow = next;
        }
        return true;
    }
    if (active != control(s.rows[row])) SetFocus(panel, control(s.rows[row]));
    Sound(panel, 1);
    reinterpret_cast<PanelFn>(dx < 0 ? s.lower : s.raise)(panel);
    return true;
}

int DirectionEvent(int dx, int dy) {
    if (dy < 0) return kEventUp;
    if (dy > 0) return kEventDown;
    return dx < 0 ? kEventLeft : kEventRight;
}

// One navigation step (NavigateFocusK1). True when something happened.
bool NavigateFocus(int dx, int dy) {
    if (engine::CurrentInputClass() != engine::kClassPCGUI) return false;
    void* tabBar = nullptr;
    void* panel = NavigationPanel(&tabBar);
    if (!panel) return false;
    void* active = At<void*>(panel, kPanelActive);
    struct Scope {
        explicit Scope(bool allow) { g.allowSelfNavigating = allow; }
        ~Scope() { g.allowSelfNavigating = false; }
    } scope(tabBar != nullptr);
    const std::uintptr_t dispatcher = Dispatcher(panel);

    if (const PointsScreen* points = PointsScreenFor(dispatcher)) return NavigatePointsScreen(panel, active, *points, dx, dy);
    if (InList(dispatcher, kNoPadFocusPanels)) { ++g.navDeclined; return false; }
    if (!tabBar && dispatcher == kWager) { ++g.navDeclined; return false; }

    // A screen that is itself the cursor (Powers, Feats, the Map, Abilities) behind the strip:
    // handed its own direction event.
    if (tabBar && NavigatesItself(panel, nullptr, true, Axis::Any)) {
        Handle(panel, DirectionEvent(dx, dy), 1);
        ++g.dispatched;
        return true;
    }
    // A focused control that owns the direction: behind the strip it is handed the event
    // itself, because nothing routes events to a panel that is not in front; in front the
    // engine routes it (the native codes went out).
    if (NavigatesItself(panel, active, false, dy != 0 ? Axis::Vertical : Axis::Horizontal)) {
        if (tabBar && Dispatcher(active)) {
            Handle(active, DirectionEvent(dx, dy), 1);
            ++g.dispatched;
            return true;
        }
        ++g.navDeclined;
        return false;
    }
    void* from = active;
    if (const CycleRow* row = CycleRowFor(panel, active)) {
        if (dy == 0) {
            StepCycleRow(panel, active, *row, dx);
            return true;
        }
        from = static_cast<char*>(panel) + row->value;
    }
    // The Portrait screen: Left and Right pick the portrait (its 0x35/0x36; no control there
    // answers them, so the focus stays put).
    if (dx != 0 && dy == 0 && dispatcher == kPortraitChargen) {
        Handle(panel, dx < 0 ? kEventPrevScreen : kEventNextScreen, 1);
        return true;
    }
    void* target = ChooseNeighbour(panel, from, dx, dy);
    if (const CycleRow* landed = CycleRowFor(panel, target)) target = static_cast<char*>(panel) + landed->value;
    if (!target || target == active) return false;
    return SetFocus(panel, target);
}

// ------------------------------------------------------------------------ the echo guard

// The event `control`'s own handler for `event` raises on `panel`, or 0 (RaisedOnPanelK1).
// Only plain buttons, and, for the echo, plain controls: a list runs its own class first.
int RaisedOnPanel(void* control, void* panel, int event, bool buttonsOnly) {
    if (!LooksLikePointer(control)) return 0;
    const std::uintptr_t handle = Dispatcher(control);
    if (handle != kButtonHandle && (buttonsOnly || handle != kControlHandle)) return 0;
    char* entries = At<char*>(control, kCtlEvents);
    const int count = At<int>(control, kCtlEventCount);
    if (!LooksLikePointer(entries) || count <= 0 || count > 64) return 0;
    // As CSWGuiControl::HandleInputEvent does: the first entry for this event with a handler.
    for (int i = 0; i < count; ++i) {
        char* entry = entries + i * kEntryBytes;
        if (At<int>(entry, kEntryEvent) != event) continue;
        const std::uintptr_t handler = At<std::uintptr_t>(entry, kEntryHandler);
        if (handler == 0) continue;
        char* receiver = At<char*>(entry, kEntryReceiver) + At<std::intptr_t>(entry, kEntryAdjust);
        if (receiver != panel) return 0;
        // Most are registered as pointers to CSWGuiPanel's virtual OnAButtonPressed and the
        // rest, which the Itanium ABI stores as the vtable offset + 1 and the control resolves
        // through the receiver's vtable: 0xA9 A, 0xB1 B, 0xB9 X, 0xC1 Y. It raises the event
        // only while the receiver's class keeps the base method in that slot.
        std::uintptr_t function = handler;
        if (handler & 1) {
            const std::uintptr_t vtable = VtableOf(panel);
            if (!vtable || handler - 1 > 0x400) return 0;
            function = *reinterpret_cast<std::uintptr_t*>(vtable + handler - 1);
        }
        for (const RaiseThunk& t : kRaiseThunks)
            if (function == t.handler) return t.event;
        return 0;
    }
    return 0;
}

// The focused button, when its click presses something on its panel (FocusedRaiseButtonK1).
void* FocusedRaiseButton() {
    void* panel = NavigationPanel(nullptr);
    if (!panel || InList(Dispatcher(panel), kOwnConfirmPanels)) return nullptr;
    void* focused = At<void*>(panel, kPanelActive);
    if (!Clickable(focused)) return nullptr;
    return RaisedOnPanel(focused, panel, kEventA, true) != 0 ? focused : nullptr;
}

// Does this control answer A with a click of its own (ClicksOnConfirmK1)?
bool ClicksOnConfirm(void* control) {
    if (!LooksLikePointer(control)) return false;
    char* entries = At<char*>(control, kCtlEvents);
    const int count = At<int>(control, kCtlEventCount);
    if (!LooksLikePointer(entries) || count <= 0 || count > 64) return false;
    for (int i = 0; i < count; ++i) {
        char* entry = entries + i * kEntryBytes;
        if (At<int>(entry, kEntryEvent) == kEventA && At<std::uintptr_t>(entry, kEntryHandler) != 0) return true;
    }
    return false;
}

// ------------------------------------------------------------------------ remaps

void* DefaultButtonOf(void* panel) {
    const std::uintptr_t vtable = VtableOf(panel);
    for (const Offset& d : kDefaultButtons)
        if (d.vtable == vtable) return static_cast<char*>(panel) + d.offset;
    return nullptr;
}
bool HasDefaultButton(void* panel) { return DefaultButtonOf(panel) != nullptr; }
void PressDefault(void* panel) {
    void* button = DefaultButtonOf(panel);
    if (!Clickable(button)) return;
    Sound(panel, 0);
    Handle(button, kEventA, 1);
}

bool HasFocusedRaiseButton(void*) { return FocusedRaiseButton() != nullptr; }
void PressFocusedRaiseButton(void*) {
    if (void* button = FocusedRaiseButton()) {
        ++g.focusedPresses;
        Handle(button, kEventA, 1);
    }
}

// Feats' A: a focused button pressed as a click, else OK as its X does it.
void FeatsConfirm(void* panel) {
    void* focused = At<void*>(panel, kPanelActive);
    if (ClicksOnConfirm(focused)) {
        g.chargenPress = {true, 0};
        Handle(focused, kEventA, 1);
        g.chargenPress = {false, 0};
        return;
    }
    Sound(panel, 0);
    reinterpret_cast<PanelFn>(kFeatsOnAccept)(panel);
}

// Feats' X: its A without the hand-on, the highlighted feat as its dispatcher computes it.
void FeatsAdd(void* panel) {
    Sound(panel, 0);
    int feat = 0xffff;
    if (At<int>(panel, 0x2130) >= 1) {
        char* columns = At<char*>(panel, 0x2128);
        char* column = *reinterpret_cast<char**>(columns + static_cast<std::size_t>(At<std::uint8_t>(panel, 0x2139)) * 8);
        feat = *reinterpret_cast<std::uint16_t*>(column + 0x1d0 + static_cast<std::size_t>(At<std::uint8_t>(panel, 0x2138)) * 0x150);
    }
    reinterpret_cast<FeatPickedFn>(kFeatsOnFeatPicked)(panel, feat);
}

struct Remap {
    std::uintptr_t panel;   // the dispatcher it applies to, when accepts is null
    int slot;
    int event;              // dispatched to that panel, when action is null
    const char* what;
    void (*action)(void* panel);
    bool (*accepts)(void* panel);
};
const Remap kRemaps[] = {
    {kJournal, kSlotA, kEventY, "A: Active/Completed", nullptr, nullptr},
    {kJournal, kSlotY, kEventBlack, "Y: sort order", nullptr, nullptr},
    {kFeats, kSlotA, kEventX, "A: OK (Feats)", FeatsConfirm, nullptr},
    {kFeats, kSlotX, kEventA, "X: Add Feat (Feats)", FeatsAdd, nullptr},
    {0, kSlotY, kEventY, "Y: Default (settings)", PressDefault, HasDefaultButton},
    // Last, so the Journal's and Feats' own A come first.
    {0, kSlotA, kEventA, "A: the focused button", PressFocusedRaiseButton, HasFocusedRaiseButton},
};

bool RemapApplies(const Remap& r, void* panel) {
    return r.accepts ? r.accepts(panel) : Dispatcher(panel) == r.panel;
}

// ------------------------------------------------------------------------ frame work

void UpdateDescriptionScroll() {
    if (engine::CurrentInputClass() != engine::kClassPCGUI) { g.descHeld = 0; return; }
    const float ny = g_rightY;   // up positive
    const float magnitude = std::fabs(ny);
    if (magnitude < kDescStickRelease) { g.descHeld = 0; return; }
    if (magnitude < kDescStickEngage) return;
    const int want = ny > 0 ? -1 : 1;
    const std::uint64_t now = NowMs();
    if (want != g.descHeld) {
        g.descHeld = want;
        g.descDeadline = now + kNavHoldDelayMs;
    } else if (now < g.descDeadline) {
        return;
    } else {
        g.descDeadline = now + kNavRepeatMs;
    }
    void* tabBar = TabBarPanel();
    void* target = tabBar ? TabContentPanel(tabBar) : TopPanel();
    if (!target) return;
    Handle(target, want < 0 ? kEventDescUp : kEventDescDown, 1);
    ++g.descScrolls;
}

void PerformPartySwitch() {
    if (!TakeRequest(g_requests.partySwitch) || engine::CurrentInputClass() != engine::kClassPCGUI) return;
    for (std::uintptr_t d : kPartySwitchPanels) {
        if (void* panel = PanelWithDispatcher(d)) {
            Handle(panel, kEventChangeChar, 1);
            ++g.partySwitches;
            return;
        }
    }
}

void PerformRemap() {
    const int slot = g.remapSlot;
    if (!slot) return;
    g.remapSlot = 0;
    if (NowMs() - g.remapRequested > kRequestWindowMs || engine::CurrentInputClass() != engine::kClassPCGUI) return;
    for (const Remap& r : kRemaps) {
        if (r.slot != slot) continue;
        void* panel = nullptr;
        if (r.accepts) {
            void* top = TopPanel();
            if (top && r.accepts(top)) panel = top;
        } else {
            panel = PanelWithDispatcher(r.panel);
        }
        if (!panel) continue;
        if (r.action) r.action(panel);
        else Handle(panel, r.event, 1);
        ++g.remaps;
        return;
    }
}

// ------------------------------------------------------------------------ guards

// The confirm guards (GuardChargenConfirmK1 and the Solo Mode and resolution resolvers), as
// wrappers in each class's dispatcher slot. A returned false drops the event (Windows makes it
// the inert 0x41, which no dispatcher and no control answers).
bool GuardChargen(void* panel, int& event, int value) {
    if (event != kEventA && event != kEventConfirmAlias) return true;
    if (g.chargenPress.active) return ++g.chargenPress.reentries <= 1;   // the click's own re-entry only
    if (value == 0) return false;                                       // a release clicks nothing
    void* focused = At<void*>(panel, kPanelActive);
    if (!ClicksOnConfirm(focused)) return true;                         // the screen's own A
    ++g.confirmGuards;
    g.chargenPress = {true, 0};
    Handle(focused, kEventA, 1);
    g.chargenPress = {false, 0};
    return false;
}

// A with Cancel focused, from the pad, is Cancel: these two panels implement A themselves and
// never look at the focus.
bool PadPressedRecently() { return g_lastPadPressMs != 0 && NowMs() - g_lastPadPressMs < 500; }

void ResolveCancelFocus(void* panel, int& event, int value, std::size_t cancel, bool alias) {
    if (value == 0 || (event != kEventA && !(alias && event == kEventConfirmAlias)) || !PadPressedRecently()) return;
    if (At<void*>(panel, kPanelActive) == static_cast<char*>(panel) + cancel) {
        event = kEventB;
        ++g.confirmGuards;
    }
}

#define KMRP_CHARGEN_GUARD(fn, original) \
    void fn(void* panel, int event, int value) { \
        if (GuardChargen(panel, event, value)) reinterpret_cast<HandleFn>(original)(panel, event, value); \
    }
KMRP_CHARGEN_GUARD(GuardAttributes, kAttributesChargen)
KMRP_CHARGEN_GUARD(GuardSkills, kSkillsChargen)
KMRP_CHARGEN_GUARD(GuardFeats, kFeats)
KMRP_CHARGEN_GUARD(GuardPowers, kPowers)
KMRP_CHARGEN_GUARD(GuardPortrait, kPortraitChargen)
KMRP_CHARGEN_GUARD(GuardName, kNameChargen)
#undef KMRP_CHARGEN_GUARD

void GuardSoloMode(void* panel, int event, int value) {
    ResolveCancelFocus(panel, event, value, kMessageBoxCancel, true);
    reinterpret_cast<HandleFn>(kSoloModeQuery)(panel, event, value);
}
void GuardResolution(void* panel, int event, int value) {
    ResolveCancelFocus(panel, event, value, kResolutionCancel, false);
    reinterpret_cast<HandleFn>(kResolution)(panel, event, value);
}

Guarded g_guarded[] = {
    {"Attributes", 0x1005b0950UL, kAttributesChargen, reinterpret_cast<void*>(&GuardAttributes), false},
    {"Skills", 0x1005a7820UL, kSkillsChargen, reinterpret_cast<void*>(&GuardSkills), false},
    {"Feats", 0x1005adc40UL, kFeats, reinterpret_cast<void*>(&GuardFeats), false},
    {"Powers", 0x1005abb40UL, kPowers, reinterpret_cast<void*>(&GuardPowers), false},
    {"Portrait", 0x1005afea0UL, kPortraitChargen, reinterpret_cast<void*>(&GuardPortrait), false},
    {"Name", 0x1005aac10UL, kNameChargen, reinterpret_cast<void*>(&GuardName), false},
    {"Solo Mode", 0x1005abea0UL, kSoloModeQuery, reinterpret_cast<void*>(&GuardSoloMode), false},
    {"Resolution", 0x1005ac3a0UL, kResolution, reinterpret_cast<void*>(&GuardResolution), false},
};

Guarded* GuardedList(std::size_t* count) {
    *count = sizeof g_guarded / sizeof g_guarded[0];
    return g_guarded;
}

// Writes into the game's image and puts the page's protection back as it was, read from the
// region itself: a vtable page may be read-only or writable data, and leaving writable data
// read-only would fault the next write to anything else on that page.
bool WriteProtected(std::uintptr_t address, const void* value, std::size_t size) {
    mach_vm_address_t region = address;
    mach_vm_size_t regionSize = 0;
    vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t infoCount = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object = MACH_PORT_NULL;
    if (mach_vm_region(mach_task_self(), &region, &regionSize, VM_REGION_BASIC_INFO_64,
                       reinterpret_cast<vm_region_info_t>(&info), &infoCount, &object) != KERN_SUCCESS ||
        region > address)
        return false;
    const std::uintptr_t first = address & ~std::uintptr_t(0xFFF);
    const std::uintptr_t last = (address + size + 0xFFF) & ~std::uintptr_t(0xFFF);
    if (vm_protect(mach_task_self(), first, last - first, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) !=
        KERN_SUCCESS)
        return false;
    std::memcpy(reinterpret_cast<void*>(address), value, size);
    vm_protect(mach_task_self(), first, last - first, FALSE, info.protection);
    return true;
}

}  // namespace

// CSWGuiPanel::HandleInputEvent (0x10049dc72), replaced whole: it hands the event to the
// focused control, unless that control would only press the same event back on this panel,
// which has already acted on it: the echo (GuardPanelEchoK1).
extern "C" __attribute__((visibility("default"))) void KmrpPanelHandleInputEvent(void* panel, int event, int value) {
    void* focused = At<void*>(panel, kPanelActive);
    if (!focused) return;
    if (RaisedOnPanel(focused, panel, event, false) == event) {
        ++g.echoesStopped;
        return;
    }
    Handle(focused, event, value);
}

// CSWGuiManager::Update, entry (0x10049f636; Windows 0x0040CE70, NativeGuiFrameK1): the GUI's
// own frame, where focus moves are made, the screen remaps and the party switch performed, and
// the right stick scrolls descriptions; then the prompts and the cursor catch up with all of it
// (prompts.cpp), so a badge that follows the focus is painted on the frame the focus moved.
//
// The one hook the module shares with the build without controller support (kmrp-layout's
// KmrpCoreGuiFrame): two hooks on one address, one per value of the option, are refused by a
// manager without options, so the patch with options keeps this one whatever was chosen and the
// choice is made here. With the controller off, the frame is the status summary's alone.
extern "C" __attribute__((visibility("default"))) void KmrpGuiFrame(void* manager) {
    // Another patch adds a resource directory when the resolution is changed in the game (KMRP's
    // menu set for the new size), which would then be searched before this patch's files.
    static int lastWidth = 0, lastHeight = 0;
    if (LooksLikePointer(manager)) {
        const int width = At<std::int16_t>(manager, 0xa4), height = At<std::int16_t>(manager, 0xa6);
        if (width > 0 && height > 0 && (width != lastWidth || height != lastHeight)) {
            if (lastWidth) kmrp::standalone::RegisterAgain();
            lastWidth = width;
            lastHeight = height;
        }
    }
    PerformPartySwitch();
    UpdateDescriptionScroll();
    PerformRemap();
    const int dx = g.navPendingX, dy = g.navPendingY;
    if (dx != 0 || dy != 0) {
        g.navPendingX = g.navPendingY = 0;
        NavigateFocus(dx, dy);
    }
    prompts::Frame();
    layout::Frame(manager);
}

// ------------------------------------------------------------------------ the input hook's side

bool OwnsDirections(bool vertical) {
    const int inputClass = engine::CurrentInputClass();
    if (inputClass == engine::kClassPC) return true;   // the HUD's action bar has the D-pad
    if (inputClass != engine::kClassPCGUI) return false;
    void* tabBar = nullptr;
    void* panel = NavigationPanel(&tabBar);
    if (!panel) return false;
    if (tabBar && panel != tabBar) return true;
    if (PointsScreenFor(Dispatcher(panel))) return true;
    return !NavigatesItself(panel, At<void*>(panel, kPanelActive), true, vertical ? Axis::Vertical : Axis::Horizontal);
}

int RemappedButtonEvent(int slot) {
    if (engine::CurrentInputClass() != engine::kClassPCGUI) return 0;
    for (const Remap& r : kRemaps) {
        if (r.slot != slot) continue;
        if (r.action) {
            void* top = TopPanel();
            if (top && RemapApplies(r, top)) return r.event;
            continue;
        }
        if (PanelWithDispatcher(r.panel)) return r.event;
    }
    return 0;
}

void RequestRemap(int slot) {
    g.remapSlot = slot;
    g.remapRequested = NowMs();
}

bool TabBarOpen() { return TabBarPanel() != nullptr; }

bool IsTabBar(void* panel) { return LooksLikePointer(panel) && Dispatcher(panel) == kInGameMenu; }

// Menus and the HUD's action bar each get the request, with the same edge-then-repeat cadence,
// because they are performed by different frame hooks. Only the D-pad reaches the HUD, and only
// in the world: there the left stick means movement and nothing else, and a menu's D-pad is the
// menu's.
void RequestNavigation(int dx, int dy, bool edge, bool fromDpad) {
    if (dx == 0 && dy == 0) { g.navHeldX = g.navHeldY = 0; return; }
    const std::uint64_t now = NowMs();
    bool fire = false;
    if (edge || dx != g.navHeldX || dy != g.navHeldY) {
        g.navHeldX = dx;
        g.navHeldY = dy;
        g.navRepeatDeadline = now + kNavHoldDelayMs;
        fire = true;
    } else if (now >= g.navRepeatDeadline) {
        g.navRepeatDeadline = now + kNavRepeatMs;
        fire = true;
    }
    if (!fire) return;
    g.navPendingX = dx;
    g.navPendingY = dy;
    if (fromDpad && engine::CurrentInputClass() == engine::kClassPC) hud::RequestMove(dx, dy);
}

void StickNavigation(float x, float y, int* dx, int* dy, bool* edge) {
    // y is up positive here; the focus layer's dy grows downward.
    const float ax = std::fabs(x), ay = std::fabs(y);
    int wantX = 0, wantY = 0;
    if (ax >= ay) {
        if (ax > kNavStickEngage) wantX = x > 0 ? 1 : -1;
    } else if (ay > kNavStickEngage) {
        wantY = y > 0 ? -1 : 1;
    }
    *edge = false;
    if (g.stickNavX != 0 || g.stickNavY != 0) {
        const float along = g.stickNavX != 0 ? ax : ay;
        if (along < kNavStickRelease) g.stickNavX = g.stickNavY = 0;
    } else if (wantX || wantY) {
        g.stickNavX = wantX;
        g.stickNavY = wantY;
        *edge = true;
    }
    *dx = g.stickNavX;
    *dy = g.stickNavY;
}

void Status() {
    Log("menus: %lu focus moves (%lu declined), %lu handed to a screen or control, %lu description scrolls, "
        "%lu remaps, %lu party switches, %lu echoes stopped, %lu focused presses, %lu confirm guards",
        g.navMoves, g.navDeclined, g.dispatched, g.descScrolls, g.remaps, g.partySwitches, g.echoesStopped,
        g.focusedPresses, g.confirmGuards);
}

void Install() {
    // The echo guard: CSWGuiPanel::HandleInputEvent replaced by a jump, checked byte for byte.
    static const std::uint8_t kPanelHandle[28] = {0x55, 0x48, 0x89, 0xe5, 0x48, 0x8b, 0x7f, 0x28, 0x48, 0x85,
                                                  0xff, 0x74, 0x0d, 0x48, 0x8b, 0x07, 0x48, 0x8b, 0x80, 0x80,
                                                  0x00, 0x00, 0x00, 0x5d, 0xff, 0xe0, 0x5d, 0xc3};
    const std::uintptr_t site = 0x10049dc72UL;
    if (std::memcmp(reinterpret_cast<const void*>(site), kPanelHandle, sizeof kPanelHandle) == 0) {
        std::uint8_t jump[14] = {0xFF, 0x25, 0, 0, 0, 0};
        const std::uint64_t target = reinterpret_cast<std::uint64_t>(&KmrpPanelHandleInputEvent);
        std::memcpy(jump + 6, &target, 8);
        Log("echo guard %s", WriteProtected(site, jump, sizeof jump) ? "installed" : "NOT installed");
    } else {
        Log("echo guard: CSWGuiPanel::HandleInputEvent holds other bytes; not installed");
    }
    // The confirm guards, in their classes' vtables.
    for (Guarded& guard : g_guarded) {
        const std::uintptr_t slot = guard.vtable + kVtHandleInput;
        if (*reinterpret_cast<std::uintptr_t*>(slot) != guard.original) {
            Log("%s guard: the vtable slot holds 0x%lx, not the dispatcher; not installed", guard.name,
                static_cast<unsigned long>(*reinterpret_cast<std::uintptr_t*>(slot)));
            continue;
        }
        const std::uintptr_t value = reinterpret_cast<std::uintptr_t>(guard.wrapper);
        guard.installed = WriteProtected(slot, &value, sizeof value);
        if (!guard.installed) Log("%s guard: the vtable could not be written", guard.name);
    }
}

}  // namespace gui
}  // namespace kmrp
