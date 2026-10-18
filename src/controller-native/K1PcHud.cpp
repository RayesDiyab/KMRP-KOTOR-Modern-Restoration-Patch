// The mouse and keyboard HUD, placed by KMRP for the screen the game is drawing and
// sized part by part as the HUD Size page says (the maintainer's direction, 2026-10-18:
// drawn "like the current controller GUI ... so it's compatible with any other
// widescreen mods"). The Xbox-style HUD (K1XboxHud.cpp) has been placed this way since
// 2026-10-05: whatever HUD layout file the game loaded (KMRP's, another mod's, the
// game's own) gives the controls and their art, and each control is then moved to its
// place from a table. Here the table is KMRP's HUD as it ships at 3440x1440
// (K1PcHudLayout.inc, tools/build_pc_hud.py), anchored to the screen's corners and
// scaled by its height, and each part (menu buttons, minimap, action bar, portraits,
// attack buttons, Disengage button) is then sized about its corner (K1PcHudLayout.h,
// shared with the page's preview).
//
// A control is found by its tag in the HUD panel (K1RuntimeLayout.cpp keeps every
// control's tag as InitControl files it), so nothing here depends on which file was
// loaded or where the executable keeps a control. Each tag is looked up again on each
// placing; a tag the loaded file lacks is left alone.
//
// Besides the controls, the HUD keeps numbers it worked out from its layout when it
// was built, which the engine goes on using, so they are set with the controls
// (each read from the executable, 2026-10-18, by the names of a Ghidra database kept
// outside the repository):
//   - the rectangle the map is drawn in, +0x6080 (left, top, width, height): DrawMap
//     (0x0068AB10) draws it width x width, and the arrow in its middle;
//   - the bottom edge the action description grows up from, +0xA454
//     (SetActionDescription, 0x00685560, sets the label's top to it less the text's
//     height, and keeps the label's left and width);
//   - in the target menu (+0xBC): its width (+0x15B4, the clip of its drawing; the
//     engine takes LBL_NAME's width), the gaps under the name to the health bar and to
//     the slots (+0x1AE8, +0x1AE9, bytes, from which SetNameLabel, 0x00685AF0, stacks
//     them again for each target), and the rectangle it is kept inside (+0x15BC, from
//     LBL_ARROW_MARGIN's left, LBL_MENUBG's bottom and TB_PAUSE's top in the HUD's
//     constructor, 0x0068C100);
//   - each portrait's place, +0xE98 in its CSWGuiMainInterfaceChar (two shorts, top
//     then left, of PB_VITn), which CSWGuiMainInterfaceChar::Adjust (0x006851B0) moves
//     the portrait back to after the party is changed.
// Two things the engine does to a placed HUD then come out right without help: in
// combat mode ShowActionQueue (0x006874C0) moves the minimap, its button, its window
// and the notices beside it down by the byte at +0xA458 and back up after (and that is
// added here while combat mode is on, +0xA45C bit 1); and SetNameLabel moves the
// target's slots by the difference from their own top, keeping their size.
//
// Placed again only when something changes: the HUD object, the screen's size, a
// size on the page, or the Xbox-style HUD giving the HUD back. Nothing per frame but
// the comparison.
#include "K1HudOptions.h"
#include "K1HudOptionsPolicy.h"
#include "K1PcHudLayout.h"
#include "K1RuntimeLayout.h"
#include <windows.h>
#include <array>
#include <cstdint>
#include <cstring>

namespace {
using namespace KmrpPcHud;
using KmrpHudOptions::ElementCount;
template<class T> T& At(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p) + n); }

constexpr std::uintptr_t kHudTable = 0x00753F50;        // CSWGuiMainInterface's vtable
constexpr unsigned kHudManager = 0x18;
constexpr unsigned kHudMapWindow = 0x6080;
constexpr unsigned kHudDescriptionBottom = 0xA454;
constexpr unsigned kHudCombatShift = 0xA458;             // byte
constexpr unsigned kHudFlags = 0xA45C;                   // bit 1: the combat queue is shown
constexpr unsigned kHudTargetMenu = 0xBC;
constexpr unsigned kMenuWidth = 0x15B4;
constexpr unsigned kMenuClamp = 0x15BC;                  // left, top, width, height
constexpr unsigned kMenuHealthGap = 0x1AE8, kMenuSlotGap = 0x1AE9;   // bytes
constexpr unsigned kHudParty = 0x1F88, kPartySize = 0xEA8;          // CSWGuiMainInterfaceChar[3], LBL_BACK1..3
constexpr unsigned kCharHome = 0xE98;                    // short top, short left

struct Key {
    void* hud = nullptr;
    int width = 0, height = 0;
    std::array<int, ElementCount> sizes{};
    int shift = -1;
    bool operator==(const Key& o) const {
        return hud == o.hud && width == o.width && height == o.height && sizes == o.sizes && shift == o.shift;
    }
};
Key applied;
std::array<int, ElementCount> appliedSizes{};   // what the live HUD shows, for KmrpHudAppliedSizeK1

void SetExtent(void* control, const Rect& r)
{
    if (!std::memcmp(&At<Rect>(control, 4), &r, sizeof r)) return;
    auto table = At<void**>(control, 0);
    reinterpret_cast<void(__thiscall*)(void*, const Rect*)>(table[1])(control, &r);
}

// The Xbox-style HUD (kmrp-controller.dll) owns the HUD while the pad is in use: it
// moves the same controls, and gives them back as they were when it took them.
bool XboxOwns()
{
    using Owns = int(__cdecl*)();
    static HMODULE module = nullptr;
    static Owns owns = nullptr;
    if (!module) {
        module = GetModuleHandleW(L"kmrp-controller.dll");
        if (module) owns = reinterpret_cast<Owns>(GetProcAddress(module, "KmrpXboxHudOwnsK1"));
    }
    return owns && owns();
}

Rect PieceRect(const Layout& layout, const char* tag)
{
    const int i = Find(tag);
    return i >= 0 ? layout.rect[i] : Rect{};
}
int Bottom(const Rect& r) { return r.top + r.height; }

void Apply(void* hud, int width, int height, const std::array<int, ElementCount>& sizes, int shift)
{
    using namespace KmrpHudOptions;
    const Layout layout = Lay(width, height, sizes);
    // The target menu's name keeps the height the engine gave it for the target's name
    // (SetNameLabel: its text's height); what is under it follows that height.
    void* name = KmrpRuntimeControlByTagK1(hud, "LBL_NAME");
    const Rect nameAt = PieceRect(layout, "LBL_NAME");
    const int nameHeight = name && At<Rect>(name, 4).height > 0 ? At<Rect>(name, 4).height : nameAt.height;
    const int below = nameHeight - nameAt.height;
    // The description keeps the height the engine gave it for its text, its bottom on
    // the edge it grows up from.
    const Rect description = PieceRect(layout, "LBL_ACTIONDESC");
    const int descriptionBottom = Bottom(description);
    void* descriptionLabel = KmrpRuntimeControlByTagK1(hud, "LBL_ACTIONDESC");
    const int descriptionHeight = descriptionLabel ? At<Rect>(descriptionLabel, 4).height : description.height;
    for (int i = 0; i < kPcPieceCount; ++i) {
        const PcPiece& p = kPcPieces[i];
        if (p.flags & kWindow) continue;     // not a control the HUD keeps: the window is +0x6080
        void* control = KmrpRuntimeControlByTagK1(hud, p.tag);
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
    // The map's window.
    int* window = &At<int>(hud, kHudMapWindow);
    window[0] = layout.window.left;
    window[1] = layout.window.top + shift;
    window[2] = layout.window.width;
    window[3] = layout.window.height;
    At<int>(hud, kHudDescriptionBottom) = descriptionBottom;
    // The target menu: its width the name strip's or its slots' if they reach further,
    // the gaps under the name, and where it is kept on the screen (below).
    void* menu = static_cast<char*>(hud) + kHudTargetMenu;
    const Rect strip = PieceRect(layout, "LBL_NAMEBG"), health = PieceRect(layout, "PB_HEALTH");
    const Rect slots = layout.group[PcAttack];
    At<int>(menu, kMenuWidth) = (std::max)(strip.left + strip.width, slots.left + slots.width);
    const int healthGap = health.top - Bottom(nameAt), slotGap = slots.top - Bottom(nameAt);
    At<unsigned char>(menu, kMenuHealthGap) = static_cast<unsigned char>((std::max)(0, (std::min)(255, healthGap)));
    At<unsigned char>(menu, kMenuSlotGap) = static_cast<unsigned char>((std::max)(0, (std::min)(255, slotGap)));
    // Where a target's circle may stand (LBL_ARROW_MARGIN; outside it the engine draws
    // an arrow on its edge instead, CSWGuiMainInterface::UpdateIndicator, 0x0068A310):
    // the screen less the HUD's thinner band at the top and at the bottom, a little in
    // from the sides. The HUD's parts are in its corners, so a band as deep as the
    // largest of them would hide the circle across the whole width: with the minimap
    // at two and a half times (690 px at 3440x1440, 100% until 2026-10-19) a target in the upper half of the
    // screen had an arrow over the character's head instead (seen 2026-10-18). The
    // file's own rectangle was made for one size of each part (at 3440x1440 it is 3,
    // 129, 2554, 501, and a target in the lower half of the screen got the arrow,
    // docs/controller-xbox-hud.md, "The target's circle").
    const int side = (std::max)(1, Round(3 * ScreenScale(height)));
    const int top = (std::min)(Bottom(layout.group[PcMinimap]) + shift, Bottom(layout.group[PcMenu]));
    const int bottom = (std::max)({layout.group[PcActions].top, layout.group[PcPortraits].top, layout.group[PcDisengage].top});
    const Rect margin{side, top, width - 2 * side, (std::max)(1, bottom - top)};
    if (void* arrowMargin = KmrpRuntimeControlByTagK1(hud, "LBL_ARROW_MARGIN")) SetExtent(arrowMargin, margin);
    // The menu is kept where the constructor keeps it: from the margin's left, under
    // the menu buttons' strip, across the screen less the margin both sides, down to
    // the pause button.
    int* clamp = &At<int>(menu, kMenuClamp);
    const Rect menuStrip = PieceRect(layout, "LBL_MENUBG"), pause = PieceRect(layout, "TB_PAUSE");
    clamp[0] = margin.left;
    clamp[1] = Bottom(menuStrip);
    clamp[2] = width - 2 * margin.left;
    clamp[3] = pause.top - Bottom(menuStrip);
    // Each portrait's place, for Adjust after a change of party.
    for (int member = 0; member < 3; ++member) {
        char tag[8] = "PB_VIT1";
        tag[6] = static_cast<char>('1' + member);
        const Rect vitality = PieceRect(layout, tag);
        char* character = static_cast<char*>(hud) + kHudParty + member * kPartySize;
        At<short>(character, kCharHome) = static_cast<short>(vitality.top);
        At<short>(character, kCharHome + 2) = static_cast<short>(vitality.left);
    }
    appliedSizes = layout.size;
}
}  // namespace

void KmrpPcHudForgetK1(void* panel)
{
    if (panel && panel == applied.hud) { applied = Key{}; appliedSizes.fill(KmrpHudOptions::Default); }
}

void KmrpPcHudFrameK1(void* manager)
{
    if (!manager) return;
    for (void* hud : KmrpRuntimeAllPanelsK1()) {
        if (At<std::uintptr_t>(hud, 0) != kHudTable || At<void*>(hud, kHudManager) != manager) continue;
        if (XboxOwns()) { applied = Key{}; return; }
        Key key;
        key.hud = hud;
        key.width = At<short>(manager, 0x6C);
        key.height = At<short>(manager, 0x6E);
        for (int e = 0; e < ElementCount; ++e) key.sizes[e] = KmrpHudSizePercentK1(e);
        key.shift = (At<unsigned>(hud, kHudFlags) & 2) ? At<unsigned char>(hud, kHudCombatShift) : 0;
        if (key.width <= 0 || key.height <= 0) return;
        // Combat mode coming or going is the engine's own move (ShowActionQueue) and
        // needs nothing; it is in the key only for a placing that happens meanwhile.
        if (key.hud == applied.hud && key.width == applied.width && key.height == applied.height &&
            key.sizes == applied.sizes) return;
        Apply(hud, key.width, key.height, key.sizes, key.shift);
        applied = key;
        return;
    }
}

// The size, in percent, at which each part of the mouse and keyboard HUD is now shown
// (50 until it has been placed): the Xbox-style HUD reads the minimap's to keep its own
// minimap independent of it (K1XboxHud.cpp).
extern "C" int __cdecl KmrpHudAppliedSizeK1(int element)
{
    if (element < 0 || element >= ElementCount || !applied.hud) return KmrpHudOptions::Default;
    return appliedSizes[element];
}
