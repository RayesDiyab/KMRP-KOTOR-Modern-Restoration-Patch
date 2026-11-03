/*
  KMRP for macOS: the mouse and keyboard HUD, placed by KMRP for the screen the game is drawing and
  sized part by part as the HUD Size page says. The port of src/controller-native/K1PcHud.cpp, with
  Windows' own table and arithmetic (K1PcHudLayout.inc, K1PcHudLayout.h): whatever HUD layout file
  the game loaded gives the controls and their art, and each control is then moved to its place,
  anchored to the screen's corners and scaled by its height. At every part's 50% that is KMRP's HUD
  as it ships. On a size KMRP has no menus for, where the widescreen patch lays the menus out
  itself (layouts_ini.cpp), the HUD is left to it.

  A control is found by its tag in the HUD panel (layout.cpp keeps every control's tag as InitControl
  files it), so nothing here depends on which file was loaded; a tag the file lacks is left alone.

  Besides the controls, the HUD keeps numbers it worked out from its layout when it was built, which
  the engine goes on using, so they are set with the controls. CSWGuiMainInterface on the Mac
  (vtable 0x1005A6220, constructor 0x100232DA0), each read from the routine named, Windows' beside it:

      +0x7B08   the rectangle the map is drawn in, left, top, width, height (+0x6080): its drawing,
                0x100237848, sets the viewport to width x width, and the arrow in its middle
      +0xD170   the bottom edge the action description grows up from (+0xA454): the constructor
                stores LBL_ACTIONDESC's top plus height there
      +0x100    the target menu (+0xBC), and in it, read from CSWGuiTargetActionMenu::Initialize
                (0x10023082C) and SetNameLabel (0x1002309C6):
        +0x1BA0   its width, taken from LBL_NAME's (+0x15B4)
        +0x1BA8   the rectangle it is kept inside, from LBL_ARROW_MARGIN's left, LBL_MENUBG's bottom
                  and TB_PAUSE's top, in the HUD's constructor (+0x15BC)
        +0x2238, +0x2239   the gaps under the name to the health bar and to the slots, bytes
                  (+0x1AE8, +0x1AE9), from which SetNameLabel stacks them again for each target
      +0x2828   CSWGuiMainInterfaceChar[3], 0x12B0 each (+0x1F88, 0xEA8); the first is LBL_BACK1 and
                PB_VIT1 (the constructor's Initialize calls, index 1 to 3)
        +0x12A0, +0x12A2   its place, shorts, top then left of PB_VITn (+0xE98, +0xE9A), written by
                  CSWGuiMainInterfaceChar::Initialize (0x10023234A) from the bar's extent, which
                  the portrait is moved back to after the party is changed
      +0xD174   the byte ShowActionQueue (0x1002351B0) moves the minimap and the notices down by in
                combat mode (+0xA458); +0xD175 bit 1, the queue is shown (+0xA45C bit 1)

  Placed again only when something changes: the HUD object, the screen's size, a size on the page,
  or the Xbox-style HUD giving the HUD back. Nothing per frame but the comparison.

  The combat cues LBL_KMRPY and LBL_KMRPX stand beside Clear and Disengage (CombatCueRect, item
  119 (1)); they exist only where the controller patch has bound them (cues.cpp).

  Nothing here has been seen in the game.
*/
#include "../../../src/controller-native/K1HudOptionsPolicy.h"
#include "../../../src/controller-native/K1PcHudLayout.h"
#include "assets.h"
#include "hud_options.h"
#include "options_pad.h"
#include "panels.h"

#include <array>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <vector>

namespace {

using namespace KmrpPcHud;
using KmrpHudOptions::ElementCount;

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

const std::uintptr_t kHudVtable = 0x1005a6220UL;
const std::size_t kExtent = 0x08, kVtSetExtent = 0x10;
const std::size_t kManagerWidth = 0xa4, kManagerHeight = 0xa6;
const std::size_t kHudMapWindow = 0x7b08;
const std::size_t kHudDescriptionBottom = 0xd170;
const std::size_t kHudCombatShift = 0xd174, kHudFlags = 0xd175;   // bytes; bit 1: the combat queue is shown
const std::size_t kHudTargetMenu = 0x100;
const std::size_t kMenuWidth = 0x1ba0, kMenuClamp = 0x1ba8;       // the clamp: left, top, width, height
const std::size_t kMenuHealthGap = 0x2238, kMenuSlotGap = 0x2239; // bytes
const std::size_t kHudParty = 0x2828, kPartySize = 0x12b0;        // CSWGuiMainInterfaceChar[3]
const std::size_t kCharHome = 0x12a0;                             // short top, short left

struct Key {
    void* hud = nullptr;
    int width = 0, height = 0;
    std::array<int, ElementCount> sizes{};
    int shift = -1;
};
struct State {
    Key applied;
    std::array<int, ElementCount> appliedSizes{};   // what the live HUD shows, for KmrpHudAppliedSizeK1
    int asked[2] = {0, 0};                          // the size Covers was last asked about
    bool covered = false;
};
State& S() {
    static State* state = new State;
    return *state;
}

void SetExtent(void* control, const Rect& r) {
    if (!std::memcmp(&At<Rect>(control, kExtent), &r, sizeof r)) return;
    reinterpret_cast<void (*)(void*, const Rect*)>(*reinterpret_cast<std::uintptr_t*>(
        At<std::uintptr_t>(control, 0) + kVtSetExtent))(control, &r);
}

void* Control(void* hud, const char* tag) { return kmrp::panels::ControlByTag(hud, tag); }

// The Xbox-style HUD (the controller patch's module) owns the HUD while the pad is in use: it moves
// the same controls, and gives them back as they were when it took them. Found by its own handle,
// as the pad's other names are (options_pad.h).
bool XboxOwns() {
    using Owns = int (*)();
    static Owns owns = [] {
        void* module = kmrp::pad::ModuleBeside(reinterpret_cast<const void*>(&kmrp::pad::ModuleBeside), "kmrp-controller.dylib");
        return module ? reinterpret_cast<Owns>(dlsym(module, "KmrpXboxHudOwnsK1")) : nullptr;
    }();
    return owns && owns();
}

Rect PieceRect(const Layout& layout, const char* tag) {
    const int i = Find(tag);
    return i >= 0 ? layout.rect[i] : Rect{};
}
int Bottom(const Rect& r) { return r.top + r.height; }

void Apply(void* hud, int width, int height, const std::array<int, ElementCount>& sizes, int shift) {
    using namespace KmrpHudOptions;
    const Layout layout = Lay(width, height, sizes);
    // The target menu's name keeps the height the engine gave it for the target's name
    // (SetNameLabel: its text's height); what is under it follows that height.
    void* name = Control(hud, "LBL_NAME");
    const Rect nameAt = PieceRect(layout, "LBL_NAME");
    const int nameHeight = name && At<Rect>(name, kExtent).height > 0 ? At<Rect>(name, kExtent).height : nameAt.height;
    const int below = nameHeight - nameAt.height;
    // The description keeps the height the engine gave it for its text, its bottom on the edge it
    // grows up from.
    const Rect description = PieceRect(layout, "LBL_ACTIONDESC");
    const int descriptionBottom = Bottom(description);
    void* descriptionLabel = Control(hud, "LBL_ACTIONDESC");
    const int descriptionHeight = descriptionLabel ? At<Rect>(descriptionLabel, kExtent).height : description.height;
    for (int i = 0; i < kPcPieceCount; ++i) {
        const PcPiece& p = kPcPieces[i];
        if (p.flags & kWindow) continue;     // not a control the HUD keeps: the window is +0x7B08
        void* control = Control(hud, p.tag);
        if (!control) continue;
        Rect r = layout.rect[i];
        if (p.element == PcMinimap && !(p.flags & (kFollow | kArrow))) r.top += shift;
        if (!std::strcmp(p.tag, "LBL_ACTIONDESC") || !std::strcmp(p.tag, "LBL_ACTIONDESCBG")) {
            r.height = descriptionHeight > 0 ? descriptionHeight : r.height;
            r.top = descriptionBottom - r.height;
        } else if (!std::strcmp(p.tag, "LBL_NAME") || !std::strcmp(p.tag, "LBL_NAMEBG")) {
            r.height = nameHeight;
        } else if (p.anchor == kPcMenuSpace) {
            r.top += below;
        }
        SetExtent(control, r);
    }
    // KMRP's combat cues beside Clear and Disengage, from the buttons as just placed.
    const Rect disengage = PieceRect(layout, "BTN_CLEARALL");
    for (const PcCombatCue& cue : kPcCombatCues) {
        void* label = Control(hud, cue.tag);
        const Rect button = PieceRect(layout, cue.button);
        if (label && disengage.height > 0 && button.height > 0) SetExtent(label, CombatCueRect(disengage, button));
    }
    // The map's window.
    int* window = &At<int>(hud, kHudMapWindow);
    window[0] = layout.window.left;
    window[1] = layout.window.top + shift;
    window[2] = layout.window.width;
    window[3] = layout.window.height;
    At<int>(hud, kHudDescriptionBottom) = descriptionBottom;
    // The target menu: its width the name strip's or its slots' if they reach further, the gaps
    // under the name, and where it is kept on the screen (below).
    void* menu = static_cast<char*>(hud) + kHudTargetMenu;
    const Rect strip = PieceRect(layout, "LBL_NAMEBG"), health = PieceRect(layout, "PB_HEALTH");
    const Rect slots = layout.group[PcAttack];
    At<int>(menu, kMenuWidth) = (std::max)(strip.left + strip.width, slots.left + slots.width);
    const int healthGap = health.top - Bottom(nameAt), slotGap = slots.top - Bottom(nameAt);
    At<unsigned char>(menu, kMenuHealthGap) = static_cast<unsigned char>((std::max)(0, (std::min)(255, healthGap)));
    At<unsigned char>(menu, kMenuSlotGap) = static_cast<unsigned char>((std::max)(0, (std::min)(255, slotGap)));
    // Where a target's circle may stand (LBL_ARROW_MARGIN; outside it the engine draws an arrow on
    // its edge instead, CSWGuiMainInterface::UpdateIndicator, 0x1002369FC): the screen less the
    // HUD's thinner band at the top and at the bottom, a little in from the sides.
    const int side = (std::max)(1, Round(3 * ScreenScale(height)));
    const int top = (std::min)(Bottom(layout.group[PcMinimap]) + shift, Bottom(layout.group[PcMenu]));
    const int bottom = (std::max)({layout.group[PcActions].top, layout.group[PcPortraits].top, layout.group[PcDisengage].top});
    const Rect margin{side, top, width - 2 * side, (std::max)(1, bottom - top)};
    if (void* arrowMargin = Control(hud, "LBL_ARROW_MARGIN")) SetExtent(arrowMargin, margin);
    // The menu is kept where the constructor keeps it: from the margin's left, under the menu
    // buttons' strip, across the screen less the margin both sides, down to the pause button.
    int* clamp = &At<int>(menu, kMenuClamp);
    const Rect menuStrip = PieceRect(layout, "LBL_MENUBG"), pause = PieceRect(layout, "TB_PAUSE");
    clamp[0] = margin.left;
    clamp[1] = Bottom(menuStrip);
    clamp[2] = width - 2 * margin.left;
    clamp[3] = pause.top - Bottom(menuStrip);
    // Each portrait's place, for after a change of party.
    for (int member = 0; member < 3; ++member) {
        char tag[8] = "PB_VIT1";
        tag[6] = static_cast<char>('1' + member);
        const Rect vitality = PieceRect(layout, tag);
        char* character = static_cast<char*>(hud) + kHudParty + member * kPartySize;
        At<short>(character, kCharHome) = static_cast<short>(vitality.top);
        At<short>(character, kCharHome + 2) = static_cast<short>(vitality.left);
    }
    S().appliedSizes = layout.size;
}

}  // namespace

namespace kmrp {
namespace hud {

void PcHudForget(void* panel) {
    State& s = S();
    if (panel && panel == s.applied.hud) {
        s.applied = Key{};
        s.appliedSizes.fill(KmrpHudOptions::Default);
    }
}

void PcHudFrame(void* manager) {
    static std::vector<void*>* found = new std::vector<void*>;
    found->clear();
    panels::WithVtable(kHudVtable, manager, *found);
    if (found->empty()) return;
    void* hud = found->front();
    State& s = S();
    if (XboxOwns()) { s.applied = Key{}; return; }
    Key key;
    key.hud = hud;
    key.width = At<short>(manager, kManagerWidth);
    key.height = At<short>(manager, kManagerHeight);
    for (int e = 0; e < ElementCount; ++e) key.sizes[e] = SizePercent(e);
    key.shift = (At<std::uint8_t>(hud, kHudFlags) & 2) ? At<std::uint8_t>(hud, kHudCombatShift) : 0;
    if (key.width <= 0 || key.height <= 0) return;
    // Combat mode coming or going is the engine's own move (ShowActionQueue) and needs nothing; it
    // is in the key only for a placing that happens meanwhile.
    if (key.hud == s.applied.hud && key.width == s.applied.width && key.height == s.applied.height &&
        key.sizes == s.applied.sizes) return;
    if (key.width != s.asked[0] || key.height != s.asked[1]) {
        s.asked[0] = key.width;
        s.asked[1] = key.height;
        s.covered = assets::Covers(key.width, key.height);
    }
    if (!s.covered) return;
    Apply(hud, key.width, key.height, key.sizes, key.shift);
    s.applied = key;
}

void Frame(void* manager) {
    if (!manager) return;
    PageFrame(manager);
    PcHudFrame(manager);
}

void PanelDestroyed(void* panel) {
    PageDestroyed(panel);
    PcHudForget(panel);
}

}  // namespace hud
}  // namespace kmrp

// The size, in percent, at which each part of the mouse and keyboard HUD is now shown (50 until it
// has been placed): the Xbox-style HUD reads the minimap's to keep its own minimap independent of
// it (xbox_hud.cpp). The controller patch asks for it through this module's handle.
extern "C" __attribute__((visibility("default"))) int KmrpHudAppliedSizeK1(int element) {
    if (element < 0 || element >= ElementCount || !S().applied.hud) return KmrpHudOptions::Default;
    return S().appliedSizes[element];
}
