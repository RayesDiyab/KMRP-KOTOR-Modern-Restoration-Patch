// KMRP for macOS, controller support: the gameplay HUD. The action bar on the D-pad, A and B
// on it, X and Y on the combat buttons.
//
// The Mac port of NativeActionBarK1 and the action-bar logic it drives (Saul0097's
// MoveFocus / CycleAction / activate in src/controller-native/vendor/K1XboxControls.cpp, and
// PressHudButtonK1): the same seven slots (three target actions, four personal ones), the same
// moves, performed on the HUD's own frame. Windows calls the slots' handlers directly with the
// slot; the Mac's handlers read the press from the control they are given, so the slot's label
// and arrows are pressed through their own HandleInputEvent, exactly as a click reaches them.
//
// CSWGuiMainInterface on the Mac (vtable 0x1005a6220), read from its constructor (0x100232da0):
// the target menu (CSWGuiTargetActionMenu) at +0x100, whose action lists are {ptr, count, cap}
// at +0x00/+0x10/+0x20 (count +8) and whose three slots start at +0x60; the personal slots at
// +0x97e0; each slot a CSWGuiMainInterfaceAction of 0x910 bytes: its button at +0, its label
// at +0x240 (A: the slot's action, 0x10023059a), its up and down arrows at +0x480 and +0x6c0
// (the previous and next action). BTN_CLEARONE +0x8aa8 and BTN_CLEARALL +0x8f28, whose A
// handlers are OnClearOneButtonPressed (0x1002354c0) and OnClearAllButtonPressed
// (0x1002354d2).
#include "hud.h"

#include "engine.h"
#include "pad.h"
#include "state.h"
#include "xbox_hud.h"

#include <cstdint>

namespace kmrp {
namespace hud {
namespace {

using engine::At;

const std::uintptr_t kHudVtable = 0x1005a6220UL;    // CSWGuiMainInterface
const std::uintptr_t kFadeVtable = 0x1005a90e0UL;   // CSWGuiFade, which sits over it in play
const std::size_t kPanelManager = 0x20, kPanelActive = 0x28, kPanelFlags = 0x5c;
const std::uint16_t kPanelIgnored = 0x600;
const std::size_t kMgrPanels = 0xd8, kMgrPanelCount = 0xe0, kMgrModals = 0xe8, kMgrModalCount = 0xf0;
const std::size_t kCtlFlags = 0x68;
const std::uint8_t kCtlVisible = 0x02;
const std::size_t kTargetMenu = 0x100, kTargetListStride = 0x10, kTargetListCount = 0x08, kTargetSlots = 0x60;
const std::size_t kPersonalSlots = 0x97e0, kSlotStride = 0x910;
const std::size_t kSlotLabel = 0x240, kSlotUp = 0x480, kSlotDown = 0x6c0;
const int kTargetCount = 3, kPersonalCount = 4, kSlotCount = kTargetCount + kPersonalCount;
const std::size_t kClearOne = 0x8aa8, kClearAll = 0x8f28;
const std::size_t kVtHandleInput = 0x80;
const int kEventA = 0x27;

using IsSelectableFn = bool (*)(void* control);
using SetActiveControlFn = void (*)(void* panel, void* control, int playSound);
IsSelectableFn IsSelectable() { return reinterpret_cast<IsSelectableFn>(0x1004a4fbcUL); }
SetActiveControlFn SetActiveControl() { return reinterpret_cast<SetActiveControlFn>(0x10049de24UL); }

// What the input hook asked for, and when (state.h's rule): the HUD's Update does not run while
// a menu is open, so a request it never took would otherwise act when the menu closes (seen
// 2026-09-29: a D-pad Right in the options moved the bar's focus to Heal on leaving the menu).
struct Pending {
    int dx = 0, dy = 0;
    bool activate = false, release = false, clearOne = false, disengage = false;
    std::uint64_t madeMs = 0;
} g_pending;

void* g_hud = nullptr;   // the HUD this frame's hook was handed; checked against the manager's list

struct Counters {
    unsigned long moves = 0, cycles = 0, activations = 0, releases = 0, clearOnes = 0, disengages = 0;
} g_count;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

std::uintptr_t VtableOf(void* object) {
    return LooksLikePointer(object) ? *reinterpret_cast<std::uintptr_t*>(object) : 0;
}

bool Ignored(void* panel) { return (At<std::uint16_t>(panel, kPanelFlags) & kPanelIgnored) != 0; }

void* Slot(void* hud, int i) {
    char* base = static_cast<char*>(hud);
    return i < kTargetCount ? base + kTargetMenu + kTargetSlots + i * kSlotStride
                            : base + kPersonalSlots + (i - kTargetCount) * kSlotStride;
}

// Whether the HUD is the screen the player is on (IsGameplayHudActive): no modal up, and
// nothing in front of it but the fade.
bool HudActive(void* hud) {
    void* manager = At<void*>(hud, kPanelManager);
    if (!LooksLikePointer(manager)) return false;
    void** modals = At<void**>(manager, kMgrModals);
    for (int i = At<int>(manager, kMgrModalCount) - 1; i >= 0; --i)
        if (LooksLikePointer(modals) && LooksLikePointer(modals[i]) && !Ignored(modals[i])) return false;
    void** panels = At<void**>(manager, kMgrPanels);
    const int count = At<int>(manager, kMgrPanelCount);
    if (!LooksLikePointer(panels) || count <= 0 || count > 256) return false;
    for (int i = count - 1; i >= 0; --i) {
        void* panel = panels[i];
        if (!LooksLikePointer(panel) || Ignored(panel)) continue;
        if (panel == hud) return true;
        if (VtableOf(panel) != kFadeVtable) return false;
    }
    return false;
}

// The HUD of this frame, only while it is still in the manager's list and still the HUD: the
// world's interaction bridge asks from another hook, and a HUD is rebuilt when a save loads.
void* LiveHud() {
    void* hud = g_hud;
    if (!LooksLikePointer(hud) || VtableOf(hud) != kHudVtable) return nullptr;
    void* internal = engine::ClientInternal();
    void* manager = internal ? At<void*>(internal, engine::kInternalGuiManager) : nullptr;
    if (!LooksLikePointer(manager)) return nullptr;
    void** panels = At<void**>(manager, kMgrPanels);
    const int count = At<int>(manager, kMgrPanelCount);
    for (int i = 0; LooksLikePointer(panels) && i < count && i < 256; ++i)
        if (panels[i] == hud) return hud;
    return nullptr;
}

int FocusedIndex(void* hud) {
    void* active = At<void*>(hud, kPanelActive);
    if (!active) return -1;
    for (int i = 0; i < kSlotCount; ++i)
        if (Slot(hud, i) == active) return i;
    return -1;
}

// A slot the focus may land on (FindSelectableButton): shown and selectable, and for a target
// slot one with actions.
bool Selectable(void* hud, int i) {
    if (i < kTargetCount &&
        At<int>(hud, kTargetMenu + static_cast<std::size_t>(i) * kTargetListStride + kTargetListCount) <= 0)
        return false;
    void* slot = Slot(hud, i);
    return (At<std::uint8_t>(slot, kCtlFlags) & kCtlVisible) && IsSelectable()(slot);
}

void MoveFocus(void* hud, int active, int direction) {
    // The Xbox-style HUD shows the seven slots in six places and in another order (xbox_hud.cpp,
    // kPlace): left and right follow what is on screen. The grenade and mine slots share a
    // place, and the one not shown is not selectable. The first place is the default action and
    // has no slot: it is "no slot has the focus", -1 here, and reaching it lets the focus go.
    if (xboxhud::Enabled()) {
        static const int order[8] = {-1, 0, 3, 1, 2, 6, 4, 5};
        int at = 0;
        for (int i = 0; i < 8; ++i)
            if (order[i] == active) at = i;
        for (int step = 0; step < 8; ++step) {
            at = (at + (direction > 0 ? 1 : 7)) % 8;
            if (order[at] < 0) {
                SetActiveControl()(hud, nullptr, 1);
                ++g_count.moves;
                return;
            }
            if (Selectable(hud, order[at])) {
                SetActiveControl()(hud, Slot(hud, order[at]), 1);
                ++g_count.moves;
                return;
            }
        }
        return;
    }
    int index = active >= 0 ? active : (direction > 0 ? kSlotCount - 1 : 0);
    for (int n = 0; n < kSlotCount; ++n) {
        index = (index + direction + kSlotCount) % kSlotCount;
        if (Selectable(hud, index)) {
            SetActiveControl()(hud, Slot(hud, index), 1);
            ++g_count.moves;
            return;
        }
    }
}

void Press(void* control) {
    const std::uintptr_t vtable = VtableOf(control);
    if (!vtable) return;
    using HandleFn = void (*)(void*, int, int);
    reinterpret_cast<HandleFn>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtHandleInput))(control, kEventA, 1);
}

// Y and X in combat press the HUD's own buttons, only while they are drawn (PressHudButtonK1).
bool PressIfShown(void* hud, std::size_t member) {
    void* button = static_cast<char*>(hud) + member;
    if (!(At<std::uint8_t>(button, kCtlFlags) & kCtlVisible)) return false;
    Press(button);
    return true;
}

}  // namespace

void RequestMove(int dx, int dy) {
    g_pending.dx = dx;
    g_pending.dy = dy;
    g_pending.madeMs = NowMs();
}
void RequestActivate() { g_pending.activate = true; g_pending.madeMs = NowMs(); }
void RequestRelease() { g_pending.release = true; g_pending.madeMs = NowMs(); }
void RequestClearOne() { g_pending.clearOne = true; g_pending.madeMs = NowMs(); }
void RequestDisengage() { g_pending.disengage = true; g_pending.madeMs = NowMs(); }

// A slot has the focus and can still act. The focus outlives what made it useful: a target slot
// keeps it after the target changes to one with no actions in that slot (a door, which has
// none), and A then pressed an empty slot while the world's default action, opening the door,
// was declined (2026-10-01, in play). Such a slot no longer holds A.
bool ActionBarFocused() {
    void* hud = LiveHud();
    if (!hud || !HudActive(hud)) return false;
    const int active = FocusedIndex(hud);
    return active >= 0 && Selectable(hud, active);
}

int FocusedSlot(void* hud) {
    return LooksLikePointer(hud) && VtableOf(hud) == kHudVtable ? FocusedIndex(hud) : -1;
}

void Status() {
    Log("HUD: %lu slot moves, %lu action cycles, %lu slot actions, %lu releases, %lu last-action removals, "
        "%lu disengages",
        g_count.moves, g_count.cycles, g_count.activations, g_count.releases, g_count.clearOnes, g_count.disengages);
}

// CSWGuiMainInterface::Update, entry (0x100237a86; Windows 0x00686BA0, NativeActionBarK1).
extern "C" __attribute__((visibility("default"))) void KmrpHudFrame(void* hud) {
    const Pending pending = g_pending;   // taken whatever happens, so a press never acts later
    g_pending = Pending();
    if (!LooksLikePointer(hud) || VtableOf(hud) != kHudVtable) return;
    g_hud = hud;
    if (pending.madeMs == 0 || NowMs() - pending.madeMs > kRequestWindowMs) return;
    if (engine::CurrentInputClass() != engine::kClassPC || !HudActive(hud)) return;
    int active = FocusedIndex(hud);
    // Y, then X: remove the last queued action, then disengage altogether.
    // With the Xbox-style HUD, B with no slot to let go of disengages, as B does on the Xbox
    // ("COMBAT MODE engaged. (B) to disengage."). X still does.
    const bool disengage = pending.disengage || (pending.release && active < 0 && xboxhud::Enabled());
    if (pending.clearOne && PressIfShown(hud, kClearOne)) ++g_count.clearOnes;
    if (disengage && PressIfShown(hud, kClearAll)) ++g_count.disengages;
    if (pending.release && active >= 0) {   // B: let go of the bar, and nothing else
        SetActiveControl()(hud, nullptr, 1);
        ++g_count.releases;
        return;
    }
    if (pending.dx != 0) {
        MoveFocus(hud, active, pending.dx);
        active = FocusedIndex(hud);
    }
    if (pending.dy != 0 && active >= 0) {   // Up the previous action, Down the next
        Press(static_cast<char*>(Slot(hud, active)) + (pending.dy < 0 ? kSlotUp : kSlotDown));
        ++g_count.cycles;
    }
    // A uses the focused slot's action, and the slot keeps the focus, so A can be pressed again
    // at once; only B lets go.
    if (pending.activate && active >= 0 && Selectable(hud, active)) {
        Press(static_cast<char*>(Slot(hud, active)) + kSlotLabel);
        ++g_count.activations;
    }
}

}  // namespace hud
}  // namespace kmrp
