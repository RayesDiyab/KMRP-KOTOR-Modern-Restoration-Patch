// KMRP for macOS, controller support: the button prompts, and which device the player is on.
//
// The Mac port of the prompt layer in src/controller-native/vendor/K1XboxControls.cpp
// (UpdateK1ControllerPrompts, Saul0097's, with KMRP's changes) and of the device bookkeeping
// around it (IsControllerInputActiveK1 in K1XboxControlsXInput.cpp, MouseIsBeingUsedK1 and
// UpdateK1CursorState in K1XboxControls.cpp), with the same rules; the reasoning behind each is
// written there. A badge is a texture swap on a button's own borders: while the pad is in use
// each screen's bound buttons show the pad's button for them (A on OK, B on Back, ...) in the
// pad's family (Xbox, PlayStation, Nintendo or Steam art, the resref's fourth letter), and the
// moment the mouse or keyboard is used they go back to the game's. The cursor follows the same
// question: parked at the top of the screen and hidden while the pad is in use.
//
// The tables are Windows' (K1XboxControls.cpp's K1_*_PROMPTS), each control's offset replaced
// with the Mac's: the same tag, found in the Mac class's own bind call. They were generated from
// the two by the port's prompt_table.py, which also checked that each table names its controls
// in the Windows order; the Windows offset is kept beside each.
//
// What differs on the Mac:
//   - a button's normal and highlight fills are its border params at +0xC0 and +0x148 (Windows
//     +0x80 and +0xF4), set through CSWGuiBorderParams::SetFillImage (0x1004A17C2);
//   - keyboard use is read where GetEvents asks for the keyboard's buffer (Windows reads each
//     buffered record; see the hooks file), and mouse use from the pointer position Aspyr's
//     frame loop samples, not at CSWGuiManager::HandleMouseMove as on Windows: the Mac's
//     ProcessInput calls HandleMouseMove only while its own cursor is shown and was moved in
//     the last 400 ms (0x1003578DC keeps that flag, 0x1005D34E4), and the hidden cursor of pad
//     play is exactly when it is not, so a hand on the mouse would never be seen there;
//   - the cursor is parked, and put back, only while the game is the active application: a warp
//     made while the player is in another app would move the pointer they are using there;
//   - the cursor is not confined to the window (Windows' ClipCursor, UpdateCursorConfinementK1):
//     macOS has nothing that keeps the pointer in a window and still lets it move.
#include "prompts.h"

#include "engine.h"
#include "gui.h"
#include "pad.h"
#include "state.h"

#include <cmath>
#include <cstdint>
#include <cstring>

namespace kmrp {
namespace {

using engine::At;

// ------------------------------------------------------------------------ engine ABI

// CSWGuiBorderParams::SetFillImage(params, const CResRef*, force) (Windows 0x00414C00). An empty
// resref leaves the border with no fill, which is what a caption button has of its own.
using SetFillImageFn = void (*)(void* params, const void* resref, int force);
const auto SetFillImage = reinterpret_cast<SetFillImageFn>(0x1004a17c2UL);
const std::size_t kButtonBorderFill = 0xc0, kButtonHilightFill = 0x148;

// CClientExoAppInternal::HideMouse and ShowMouse(internal, reason) (Windows 0x0061F9C0 and
// 0x0061FA00, reached on the Mac through CClientExoApp's 0x10028C72C and 0x10028C73A): a mask of
// reasons at +0x588 (Windows +0x3D8), the cursor hidden while any is set. The engine's own are
// 0x02 and 0x04 and it tests 0x4A and 0x14, so KMRP's is well clear of them.
using MouseFn = void (*)(void* internal, std::uint32_t reason);
const auto HideMouse = reinterpret_cast<MouseFn>(0x1002fca30UL);
const auto ShowMouse = reinterpret_cast<MouseFn>(0x1002fc99aUL);
const std::size_t kInternalMouseHideMask = 0x588;
const std::uint32_t kCursorHideReason = 0x100;

// CSWGuiManager::MoveMouseToPosition(manager, x, y) (Windows 0x0040C790), which forwards to
// HandleMouseMove. The manager's mouse position is at +0 and +4, its viewport's size at +0xA4
// and +0xA6 (Windows +0x6C and +0x6E).
using MoveMouseFn = void (*)(void* manager, int x, int y);
const auto MoveMouseToPosition = reinterpret_cast<MoveMouseFn>(0x1004a11b4UL);
const std::size_t kMgrMouseX = 0x0, kMgrMouseY = 0x4, kMgrViewportWidth = 0xa4, kMgrViewportHeight = 0xa6;
const int kParkedCursorY = 16;

// The pointer, as the game's frame loop samples it from the platform once a frame for Aspyr's
// cursor-idle tracking (0x1003578DC, from the loop at 0x1004ABBC6): x at 0x10068A188, y at
// 0x10068A18C, in the platform's coordinates. Distances there are what the filter below
// measures; a move the module makes itself shows up a frame later and is not counted.
const std::uintptr_t kSampledPointerX = 0x10068a188UL, kSampledPointerY = 0x10068a18cUL;
const std::uint64_t kOwnMoveSettleMs = 150;

// The raw input's read of the keyboard's buffered records (0x10035984C; Windows reads the same
// records in GetEvents' loop): {records, count}, 0x18-byte records whose value has 0x80 set on a
// press, as DirectInput's.
using ReadBufferFn = bool (*)(void* raw, void* buffer);
const auto ReadKeyboardBuffer = reinterpret_cast<ReadBufferFn>(0x10035984cUL);
const std::size_t kRecordBytes = 0x18, kRecordValue = 0x04;
const std::uint32_t kKeyPressed = 0x80;

// CGuiInGame's inventory filter (Windows +0xBC1): the inventory's filter button shows "Show "
// and the filter after this one, from a table in the same order as Windows' (All, New, Quest,
// Equippable, Utility, Useable; the Mac's at 0x100570B40, read at 0x1002496A5).
const std::size_t kGuiInGameInventoryFilter = 0xd51;
const int kInventoryFilterCount = 6;

// CSWGuiManager's panels and modals, CSWGuiPanel's focus and flags.
const std::size_t kMgrPanels = 0xd8, kMgrPanelCount = 0xe0, kMgrModals = 0xe8, kMgrModalCount = 0xf0;
const std::size_t kPanelActive = 0x28, kPanelFlags = 0x5c;
const std::uint16_t kPanelIgnored = 0x600;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}

std::uintptr_t VtableOf(void* object) {
    return LooksLikePointer(object) ? *reinterpret_cast<std::uintptr_t*>(object) : 0;
}

// ------------------------------------------------------------------------ the tables

// Which caption a button is showing, when the badge depends on more than the button
// (PromptVariantK1).
enum class Variant {
    None,
    InventoryFilter,   // the filter button: one badge per caption, placed against its wording
    FocusOnly,         // painted only while this control has the focus (the main menu's A)
    FocusFallback,     // painted unless the focus is on another badged control (Add, then OK)
};

struct PromptBinding {
    std::size_t offset;
    const char* resref;              // the Xbox art's; the family's letter replaces the fourth
    Variant variant;
    const char* restore;             // the button's own art when no badge shows (null: nothing)
    const char* restoreHilight;
};

struct PromptScreen {
    std::uintptr_t vtable;
    const PromptBinding* prompts;
    std::size_t count;
};

// Generated by the port's prompt_table.py from K1XboxControls.cpp's tables and the Mac's bind calls.
const PromptBinding kCharacterPrompts[] = {   // CSWGuiInGameCharacter
    {0x68d8, "kmrpb_charexit", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x523C)
    {0x6b18, "kmrpx_charscr", Variant::None, nullptr, nullptr},   // BTN_SCRIPTS (Windows 0x5400)
    {0x5d98, "kmrpa_charlvl", Variant::None, "dialog2", "dialog2"},   // BTN_LEVELUP (Windows 0x4968)
    {0x5b58, "kmrpy_charauto", Variant::None, "dialog2", "dialog2"},   // BTN_AUTO (Windows 0x47A4)
};
const PromptBinding kContainerPrompts[] = {   // CSWGuiContainer
    {0xdc0, "kmrpa_contok", Variant::None, nullptr, nullptr},   // BTN_OK (Windows 0x0AD0)
    {0x1240, "kmrpx_contgive", Variant::None, nullptr, nullptr},   // BTN_GIVEITEMS (Windows 0x0E58)
    {0x1000, "kmrpb_contback", Variant::None, nullptr, nullptr},   // BTN_CANCEL (Windows 0x0C94)
};
const PromptBinding kSaveloadPrompts[] = {   // CSWGuiSaveLoad
    {0x13d8, "kmrpx_savdel", Variant::None, nullptr, nullptr},   // BTN_DELETE (Windows 0x0F9C)
    {0x1198, "kmrpb_savback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0DD8)
    {0xf58, "kmrpa_savload", Variant::None, nullptr, nullptr},   // BTN_SAVELOAD (Windows 0x0C14)
};
const PromptBinding kUpgradeSelectionPrompts[] = {   // CSWGuiUpgradeSelection
    {0x218, "kmrpa_upgitem", Variant::None, nullptr, nullptr},   // BTN_UPGRADEITEMS (Windows 0x01A4)
    {0x458, "kmrpb_upgback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0368)
};
const PromptBinding kInventoryPrompts[] = {   // CSWGuiInGameInventory
    {0x1618, "kmrpb_invclose", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x1164)
    {0x1858, "kmrpa_invuse", Variant::None, nullptr, nullptr},   // BTN_USEITEM (Windows 0x1328)
    {0x1a98, "kmrpx_invnew", Variant::InventoryFilter, nullptr, nullptr},   // BTN_QUESTITEMS (Windows 0x14EC)
};
const PromptBinding kMessagesPrompts[] = {   // CSWGuiInGameMessages
    {0xba8, "kmrpb_msgclose", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x0930)
    {0x968, "kmrpx_msgfeed", Variant::None, nullptr, nullptr},   // BTN_SHOW (Windows 0x076C)
};
const PromptBinding kMainMenuPrompts[] = {   // CSWGuiMainMenu
    {0x518, "kmrpa_mmnew", Variant::FocusOnly, nullptr, nullptr},   // BTN_NEWGAME (Windows 0x03F0)
    {0x758, "kmrpa_mmload", Variant::FocusOnly, nullptr, nullptr},   // BTN_LOADGAME (Windows 0x05B4)
    {0x998, "kmrpa_mmmovi", Variant::FocusOnly, nullptr, nullptr},   // BTN_MOVIES (Windows 0x0778)
    {0xbd8, "kmrpa_mmopt", Variant::FocusOnly, nullptr, nullptr},   // BTN_OPTIONS (Windows 0x093C)
    {0x1520, "kmrpa_mmexit", Variant::FocusOnly, nullptr, nullptr},   // BTN_EXIT (Windows 0x1084)
};
const PromptBinding kEquipPrompts[] = {   // CSWGuiInGameEquip
    {0x4588, "kmrpa_eqpequip", Variant::None, nullptr, nullptr},   // BTN_EQUIP (Windows 0x3698)
    {0x47c8, "kmrpb_eqpback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x385C)
};
const PromptBinding kScriptSelectPrompts[] = {   // CSWGuiScriptSelect
    {0xd40, "kmrpa_scrsel", Variant::None, nullptr, nullptr},   // BTN_Accept (Windows 0x0A74)
    {0xb00, "kmrpb_scrback", Variant::None, nullptr, nullptr},   // BTN_Back (Windows 0x08B0)
};
const PromptBinding kPartySelectPrompts[] = {   // CSWGuiPartySelection
    {0x4870, "kmrpa_ptyadd", Variant::FocusFallback, nullptr, nullptr},   // BTN_ACCEPT (Windows 0x38B8)
    {0x3400, "kmrpa_ptyok", Variant::FocusOnly, nullptr, nullptr},   // BTN_DONE (Windows 0x28B0)
    {0x4630, "kmrpb_ptyback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x36F4)
};
const PromptBinding kQuestitemPrompts[] = {   // CSWGuiQuestItem
    {0xaf8, "kmrpb_qitback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x08A8)
};
const PromptBinding kJournalPrompts[] = {   // CSWGuiInGameJournal
    {0xaf0, "kmrpx_jrnitems", Variant::None, nullptr, nullptr},   // BTN_QUESTITEMS (Windows 0x08A4)
    {0xd30, "kmrpa_jrndone", Variant::None, nullptr, nullptr},   // BTN_SWAPTEXT (Windows 0x0A68)
    {0xf70, "kmrpy_jrnsort", Variant::None, nullptr, nullptr},   // BTN_SORT (Windows 0x0C2C)
    {0x11b0, "kmrpb_jrnclose", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x0DF0)
};
const PromptBinding kMapPrompts[] = {   // CSWGuiInGameMap
    {0x6e0, "kmrpx_mapebon", Variant::None, nullptr, nullptr},   // BTN_RETURN (Windows 0x0564)
    {0x920, "kmrpa_mapparty", Variant::None, nullptr, nullptr},   // BTN_PRTYSLCT (Windows 0x0728)
    {0xb60, "kmrpb_mapclose", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x08EC)
};
const PromptBinding kAbilitiesPrompts[] = {   // CSWGuiInGameAbilities
    {0x43b0, "kmrpb_abilexit", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x369C)
};
const PromptBinding kOptionsResolutionPrompts[] = {   // CSWGuiOptionsResolution
    {0x5b8, "kmrpa_resok", Variant::None, nullptr, nullptr},   // BTN_OK (Windows 0x0484)
    {0x7f8, "kmrpb_rescancel", Variant::None, nullptr, nullptr},   // BTN_CANCEL (Windows 0x0648)
};
const PromptBinding kOptionsMainPrompts[] = {   // CSWGuiOptionsMain
    {0x1130, "kmrpb_optmain", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0D7C)
    {0x80, "kmrpa_omgame", Variant::FocusOnly, nullptr, nullptr},   // BTN_GAMEPLAY (Windows 0x0064)
    {0x2c0, "kmrpa_omfeed", Variant::FocusOnly, nullptr, nullptr},   // BTN_FEEDBACK (Windows 0x0228)
    {0x500, "kmrpa_ompause", Variant::FocusOnly, nullptr, nullptr},   // BTN_AUTOPAUSE (Windows 0x03EC)
    {0x740, "kmrpa_omgfx", Variant::FocusOnly, nullptr, nullptr},   // BTN_GRAPHICS (Windows 0x05B0)
    {0x980, "kmrpa_omsnd", Variant::FocusOnly, nullptr, nullptr},   // BTN_SOUND (Windows 0x0774)
};
const PromptBinding kTitleMoviesPrompts[] = {   // CSWGuiTitleMovies
    {0x5b8, "kmrpb_movies", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0484)
};
const PromptBinding kIngameOptionsPrompts[] = {   // CSWGuiInGameOptions
    {0x2388, "kmrpb_optingame", Variant::None, nullptr, nullptr},   // BTN_EXIT (Windows 0x1BE8)
    {0x80, "kmrpa_oiload", Variant::FocusOnly, nullptr, nullptr},   // BTN_LOADGAME (Windows 0x0064)
    {0x2c0, "kmrpa_oisave", Variant::FocusOnly, nullptr, nullptr},   // BTN_SAVEGAME (Windows 0x0228)
    {0x500, "kmrpa_oigame", Variant::FocusOnly, nullptr, nullptr},   // BTN_GAMEPLAY (Windows 0x03EC)
    {0x740, "kmrpa_oifeed", Variant::FocusOnly, nullptr, nullptr},   // BTN_FEEDBACK (Windows 0x05B0)
    {0x980, "kmrpa_oipause", Variant::FocusOnly, nullptr, nullptr},   // BTN_AUTOPAUSE (Windows 0x0774)
    {0xbc0, "kmrpa_oigfx", Variant::FocusOnly, nullptr, nullptr},   // BTN_GRAPHICS (Windows 0x0938)
    {0xe00, "kmrpa_oisnd", Variant::FocusOnly, nullptr, nullptr},   // BTN_SOUND (Windows 0x0AFC)
    {0x1040, "kmrpa_oiquit", Variant::FocusOnly, nullptr, nullptr},   // BTN_QUIT (Windows 0x0CC0)
};
const PromptBinding kIngameGameplayPrompts[] = {   // CSWGuiInGameGameplay
    {0x750, "kmrpb_optgame", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x05C4)
    {0x990, "kmrpy_optgamedef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x0788)
    {0xe10, "kmrpa_optgamemse", Variant::FocusOnly, nullptr, nullptr},   // BTN_MOUSE (Windows 0x0B10)
    {0xbd0, "kmrpa_optgamekey", Variant::FocusOnly, nullptr, nullptr},   // BTN_KEYMAP (Windows 0x094C)
};
const PromptBinding kIngameAutopausePrompts[] = {   // CSWGuiInGameAutoPause
    {0x17c0, "kmrpb_optpause", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x131C)
    {0x1a00, "kmrpy_optpsedef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x14E0)
};
const PromptBinding kOptionsFeedbackPrompts[] = {   // CSWGuiOptionsFeedback
    {0xaf0, "kmrpb_optfeed", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x08A4)
    {0xd30, "kmrpy_optfeeddef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x0A68)
};
const PromptBinding kOptionsMousePrompts[] = {   // CSWGuiOptionsMouse
    {0x750, "kmrpb_optmouse", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x05C4)
    {0x990, "kmrpy_optmsedef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x0788)
};
const PromptBinding kOptionsGraphicsPrompts[] = {   // CSWGuiOptionsGraphics
    {0x1ac0, "kmrpb_optgfx", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x1534)
    {0x1d00, "kmrpy_optgfxdef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x16F8)
    {0xb10, "kmrpa_optgfxres", Variant::FocusOnly, nullptr, nullptr},   // BTN_RESOLUTION (Windows 0x08BC)
    {0x1880, "kmrpa_optgfxadvn", Variant::FocusOnly, nullptr, nullptr},   // BTN_ADVANCED (Windows 0x1370)
};
const PromptBinding kOptionsGraphicsAdvancedPrompts[] = {   // CSWGuiOptionsGraphicsAdvanced
    {0x2a18, "kmrpb_optgfxadv", Variant::None, nullptr, nullptr},   // BTN_CANCEL (Windows 0x214C)
    {0x2598, "kmrpa_optgfxadv", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x1DC4)
    {0x27d8, "kmrpy_optgfxadef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x1F88)
};
const PromptBinding kOptionsSoundPrompts[] = {   // CSWGuiOptionsSound
    {0x1650, "kmrpb_optsnd", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x11A4)
    {0x1890, "kmrpy_optsnddef", Variant::None, nullptr, nullptr},   // BTN_DEFAULT (Windows 0x1368)
};
const PromptBinding kKeyMappingsPrompts[] = {   // CSWGuiInGameOptKeyMappings
    {0x6a8, "kmrpb_optkeys", Variant::None, nullptr, nullptr},   // BTN_Cancel (Windows 0x0538)
    {0x468, "kmrpa_optkeys", Variant::None, nullptr, nullptr},   // BTN_Accept (Windows 0x0374)
    {0x228, "kmrpy_optkeysdef", Variant::None, nullptr, nullptr},   // BTN_Default (Windows 0x01B0)
};
const PromptBinding kPazaakWagerPrompts[] = {   // CSWGuiWagerPopup
    {0x9e8, "kmrpa_pzkwager", Variant::None, nullptr, nullptr},   // BTN_WAGER (Windows 0x07CC)
    {0xc28, "kmrpb_pzkquit", Variant::None, nullptr, nullptr},   // BTN_QUIT (Windows 0x0990)
};
const PromptBinding kSkillInfoPrompts[] = {   // CSWGuiSkillInfoBox
    {0x5b8, "kmrpa_skillok", Variant::None, nullptr, nullptr},   // BTN_OK (Windows 0x0484)
};
const PromptBinding kUpgradePrompts[] = {   // CSWGuiUpgrade
    {0x3a18, "kmrpb_upgasm", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x2D84)
    {0x3638, "kmrpa_upgasm", Variant::None, nullptr, nullptr},   // BTN_ASSEMBLE (Windows 0x2AA0)
};
const PromptBinding kUpgradeItemSelectPrompts[] = {   // CSWGuiUpgradeItemSelect
    {0xd30, "kmrpb_upgitm", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0A68)
    {0xaf0, "kmrpa_upgitm", Variant::None, nullptr, nullptr},   // BTN_UPGRADEITEM (Windows 0x08A4)
};
const PromptBinding kClassSelectPrompts[] = {   // CSWGuiClassSelection
    {0x19b0, "kmrpb_clsback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x1394)
};
const PromptBinding kQuickOrCustomPrompts[] = {   // CSWGuiQuickOrCustomPanel
    {0x90, "kmrpa_qcquick", Variant::FocusOnly, nullptr, nullptr},   // QUICK_CHAR_BTN (Windows 0x006C)
    {0x2d0, "kmrpa_qccust", Variant::FocusOnly, nullptr, nullptr},   // CUST_CHAR_BTN (Windows 0x0230)
    {0xf10, "kmrpb_qcback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0BD4)
};
const PromptBinding kCustomChargenPrompts[] = {   // CSWGuiCustomPanel
    {0x16e0, "kmrpa_cust1", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME0 (Windows 0x1224)
    {0x1920, "kmrpa_cust2", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME1 (Windows 0x13E8)
    {0x1b60, "kmrpa_cust3", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME2 (Windows 0x15AC)
    {0x1da0, "kmrpa_cust4", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME3 (Windows 0x1770)
    {0x1fe0, "kmrpa_cust5", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME4 (Windows 0x1934)
    {0x2220, "kmrpa_cust6", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME5 (Windows 0x1AF8)
    {0x25f8, "kmrpb_custback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x1DFC)
    {0x2838, "kmrpa_custcncl", Variant::FocusOnly, nullptr, nullptr},   // BTN_CANCEL (Windows 0x1FC0)
};
const PromptBinding kQuickChargenPrompts[] = {   // CSWGuiQuickPanel
    {0xd50, "kmrpa_quik1", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME0 (Windows 0x0A88)
    {0xf90, "kmrpa_quik2", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME1 (Windows 0x0C4C)
    {0x11d0, "kmrpa_quik3", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME2 (Windows 0x0E10)
    {0x1410, "kmrpb_quikback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0FD4)
    {0x1650, "kmrpa_quikcncl", Variant::FocusOnly, nullptr, nullptr},   // BTN_CANCEL (Windows 0x1198)
};
const PromptBinding kPortraitChargenPrompts[] = {   // CSWGuiPortraitCharGen
    {0xe20, "kmrpa_portok", Variant::FocusFallback, nullptr, nullptr},   // BTN_ACCEPT (Windows 0x0AFC)
    {0x1060, "kmrpb_portback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0CC0)
};
const PromptBinding kAbilitiesChargenPrompts[] = {   // CSWGuiAbilitiesCharGen
    {0x2cc8, "kmrpa_abcgok", Variant::FocusFallback, nullptr, nullptr},   // BTN_ACCEPT (Windows 0x2324)
    {0x3148, "kmrpy_abcgrec", Variant::None, nullptr, nullptr},   // BTN_RECOMMENDED (Windows 0x26AC)
    {0x2f08, "kmrpb_abcgback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x24E8)
};
const PromptBinding kSkillsChargenPrompts[] = {   // CSWGuiSkillsCharGen
    {0x32e0, "kmrpa_skcgok", Variant::FocusFallback, nullptr, nullptr},   // BTN_ACCEPT (Windows 0x27EC)
    {0x3760, "kmrpy_skcgrec", Variant::None, nullptr, nullptr},   // BTN_RECOMMENDED (Windows 0x2B74)
    {0x3520, "kmrpb_skcgback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x29B0)
};
const PromptBinding kFeatsChargenPrompts[] = {   // CSWGuiFeatsCharGen
    {0x1740, "kmrpx_ftcgadd", Variant::None, nullptr, nullptr},   // BTN_SELECT (Windows 0x1238)
    {0x1080, "kmrpa_ftcgok", Variant::FocusFallback, nullptr, nullptr},   // BTN_ACCEPT (Windows 0x0CEC)
    {0x1500, "kmrpy_ftcgrec", Variant::None, nullptr, nullptr},   // BTN_RECOMMENDED (Windows 0x1074)
    {0x12c0, "kmrpb_ftcgback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0EB0)
};
const PromptBinding kNameChargenPrompts[] = {   // CSWGuiNameChargen
    {0x90, "kmrpa_nameok", Variant::FocusFallback, nullptr, nullptr},   // END_BTN (Windows 0x006C)
    {0xa08, "kmrpy_namernd", Variant::None, nullptr, nullptr},   // BTN_RANDOM (Windows 0x07D4)
    {0x7c8, "kmrpb_nameback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x0610)
};
const PromptBinding kLevelUpPrompts[] = {   // CSWGuiLevelUpPanel
    {0x14c0, "kmrpa_lvl1", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME0 (Windows 0x1070)
    {0x1700, "kmrpa_lvl2", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME1 (Windows 0x1234)
    {0x1940, "kmrpa_lvl3", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME2 (Windows 0x13F8)
    {0x1b80, "kmrpa_lvl4", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME3 (Windows 0x15BC)
    {0x1dc0, "kmrpa_lvl5", Variant::FocusOnly, nullptr, nullptr},   // BTN_STEPNAME4 (Windows 0x1780)
    {0x2000, "kmrpb_lvlback", Variant::None, nullptr, nullptr},   // BTN_BACK (Windows 0x1944)
};
const PromptBinding kPowersLevelupPrompts[] = {   // CSWGuiPowersLevelUp
    {0x1c40, "kmrpa_pwrok", Variant::FocusFallback, nullptr, nullptr},   // ACCEPT_BTN (Windows 0x1634)
    {0x1a00, "kmrpx_pwrsel", Variant::None, nullptr, nullptr},   // SELECT_BTN (Windows 0x1470)
    {0x17c0, "kmrpy_pwrrec", Variant::None, nullptr, nullptr},   // RECOMMENDED_BTN (Windows 0x12AC)
    {0x1e80, "kmrpb_pwrback", Variant::None, nullptr, nullptr},   // BACK_BTN (Windows 0x17F8)
};
const PromptScreen kPromptScreens[] = {
    {0x1005ad790UL, kCharacterPrompts, sizeof kCharacterPrompts / sizeof kCharacterPrompts[0]},   // CSWGuiInGameCharacter
    {0x1005ab758UL, kContainerPrompts, sizeof kContainerPrompts / sizeof kContainerPrompts[0]},   // CSWGuiContainer
    {0x1005ae300UL, kSaveloadPrompts, sizeof kSaveloadPrompts / sizeof kSaveloadPrompts[0]},   // CSWGuiSaveLoad
    {0x1005a4fa0UL, kUpgradeSelectionPrompts, sizeof kUpgradeSelectionPrompts / sizeof kUpgradeSelectionPrompts[0]},   // CSWGuiUpgradeSelection
    {0x1005a75c0UL, kInventoryPrompts, sizeof kInventoryPrompts / sizeof kInventoryPrompts[0]},   // CSWGuiInGameInventory
    {0x1005ae790UL, kMessagesPrompts, sizeof kMessagesPrompts / sizeof kMessagesPrompts[0]},   // CSWGuiInGameMessages
    {0x1005aefa0UL, kMainMenuPrompts, sizeof kMainMenuPrompts / sizeof kMainMenuPrompts[0]},   // CSWGuiMainMenu
    {0x1005ab508UL, kEquipPrompts, sizeof kEquipPrompts / sizeof kEquipPrompts[0]},   // CSWGuiInGameEquip
    {0x1005acc70UL, kScriptSelectPrompts, sizeof kScriptSelectPrompts / sizeof kScriptSelectPrompts[0]},   // CSWGuiScriptSelect
    {0x1005ada20UL, kPartySelectPrompts, sizeof kPartySelectPrompts / sizeof kPartySelectPrompts[0]},   // CSWGuiPartySelection
    {0x1005a4d10UL, kQuestitemPrompts, sizeof kQuestitemPrompts / sizeof kQuestitemPrompts[0]},   // CSWGuiQuestItem
    {0x1005aed10UL, kJournalPrompts, sizeof kJournalPrompts / sizeof kJournalPrompts[0]},   // CSWGuiInGameJournal
    {0x1005ab010UL, kMapPrompts, sizeof kMapPrompts / sizeof kMapPrompts[0]},   // CSWGuiInGameMap
    {0x1005a5f80UL, kAbilitiesPrompts, sizeof kAbilitiesPrompts / sizeof kAbilitiesPrompts[0]},   // CSWGuiInGameAbilities
    {0x1005ac3a0UL, kOptionsResolutionPrompts, sizeof kOptionsResolutionPrompts / sizeof kOptionsResolutionPrompts[0]},   // CSWGuiOptionsResolution
    {0x1005abfe0UL, kOptionsMainPrompts, sizeof kOptionsMainPrompts / sizeof kOptionsMainPrompts[0]},   // CSWGuiOptionsMain
    {0x1005abc50UL, kTitleMoviesPrompts, sizeof kTitleMoviesPrompts / sizeof kTitleMoviesPrompts[0]},   // CSWGuiTitleMovies
    {0x1005aba30UL, kIngameOptionsPrompts, sizeof kIngameOptionsPrompts / sizeof kIngameOptionsPrompts[0]},   // CSWGuiInGameOptions
    {0x1005a76d0UL, kIngameGameplayPrompts, sizeof kIngameGameplayPrompts / sizeof kIngameGameplayPrompts[0]},   // CSWGuiInGameGameplay
    {0x1005a5d30UL, kIngameAutopausePrompts, sizeof kIngameAutopausePrompts / sizeof kIngameAutopausePrompts[0]},   // CSWGuiInGameAutoPause
    {0x1005ac0d0UL, kOptionsFeedbackPrompts, sizeof kOptionsFeedbackPrompts / sizeof kOptionsFeedbackPrompts[0]},   // CSWGuiOptionsFeedback
    {0x1005ac580UL, kOptionsMousePrompts, sizeof kOptionsMousePrompts / sizeof kOptionsMousePrompts[0]},   // CSWGuiOptionsMouse
    {0x1005ac1c0UL, kOptionsGraphicsPrompts, sizeof kOptionsGraphicsPrompts / sizeof kOptionsGraphicsPrompts[0]},   // CSWGuiOptionsGraphics
    {0x1005ac2b0UL, kOptionsGraphicsAdvancedPrompts, sizeof kOptionsGraphicsAdvancedPrompts / sizeof kOptionsGraphicsAdvancedPrompts[0]},   // CSWGuiOptionsGraphicsAdvanced
    {0x1005ac490UL, kOptionsSoundPrompts, sizeof kOptionsSoundPrompts / sizeof kOptionsSoundPrompts[0]},   // CSWGuiOptionsSound
    {0x1005a72d0UL, kKeyMappingsPrompts, sizeof kKeyMappingsPrompts / sizeof kKeyMappingsPrompts[0]},   // CSWGuiInGameOptKeyMappings
    {0x1005a59a0UL, kPazaakWagerPrompts, sizeof kPazaakWagerPrompts / sizeof kPazaakWagerPrompts[0]},   // CSWGuiWagerPopup
    {0x1005a9e18UL, kSkillInfoPrompts, sizeof kSkillInfoPrompts / sizeof kSkillInfoPrompts[0]},   // CSWGuiSkillInfoBox
    {0x1005a5180UL, kUpgradePrompts, sizeof kUpgradePrompts / sizeof kUpgradePrompts[0]},   // CSWGuiUpgrade
    {0x1005a5090UL, kUpgradeItemSelectPrompts, sizeof kUpgradeItemSelectPrompts / sizeof kUpgradeItemSelectPrompts[0]},   // CSWGuiUpgradeItemSelect
    {0x1005af890UL, kClassSelectPrompts, sizeof kClassSelectPrompts / sizeof kClassSelectPrompts[0]},   // CSWGuiClassSelection
    {0x1005a9a30UL, kQuickOrCustomPrompts, sizeof kQuickOrCustomPrompts / sizeof kQuickOrCustomPrompts[0]},   // CSWGuiQuickOrCustomPanel
    {0x1005a6960UL, kCustomChargenPrompts, sizeof kCustomChargenPrompts / sizeof kCustomChargenPrompts[0]},   // CSWGuiCustomPanel
    {0x1005adb30UL, kQuickChargenPrompts, sizeof kQuickChargenPrompts / sizeof kQuickChargenPrompts[0]},   // CSWGuiQuickPanel
    {0x1005afea0UL, kPortraitChargenPrompts, sizeof kPortraitChargenPrompts / sizeof kPortraitChargenPrompts[0]},   // CSWGuiPortraitCharGen
    {0x1005b0950UL, kAbilitiesChargenPrompts, sizeof kAbilitiesChargenPrompts / sizeof kAbilitiesChargenPrompts[0]},   // CSWGuiAbilitiesCharGen
    {0x1005a7820UL, kSkillsChargenPrompts, sizeof kSkillsChargenPrompts / sizeof kSkillsChargenPrompts[0]},   // CSWGuiSkillsCharGen
    {0x1005adc40UL, kFeatsChargenPrompts, sizeof kFeatsChargenPrompts / sizeof kFeatsChargenPrompts[0]},   // CSWGuiFeatsCharGen
    {0x1005aac10UL, kNameChargenPrompts, sizeof kNameChargenPrompts / sizeof kNameChargenPrompts[0]},   // CSWGuiNameChargen
    {0x1005a4c00UL, kLevelUpPrompts, sizeof kLevelUpPrompts / sizeof kLevelUpPrompts[0]},   // CSWGuiLevelUpPanel
    {0x1005abb40UL, kPowersLevelupPrompts, sizeof kPowersLevelupPrompts / sizeof kPowersLevelupPrompts[0]},   // CSWGuiPowersLevelUp
};

// The filter button's badge per caption, in the filter table's order (K1_INVENTORY_FILTER_RESREFS).
const char* const kInventoryFilterResrefs[kInventoryFilterCount] = {
    "kmrpx_invnew0", "kmrpx_invnew1", "kmrpx_invnew2", "kmrpx_invnew3", "kmrpx_invnew4", "kmrpx_invnew5",
};

const PromptScreen* PromptsFor(void* panel) {
    const std::uintptr_t vtable = VtableOf(panel);
    if (!vtable) return nullptr;
    for (const PromptScreen& screen : kPromptScreens)
        if (screen.vtable == vtable) return &screen;
    return nullptr;
}

// ------------------------------------------------------------------------ the device

// IsControllerInputActiveK1's three flags: the pad was the last device used; some device has
// been used at all; a pad is answering.
struct Device {
    bool padActive = false;
    bool chosen = false;
    bool padConnected = false;
    unsigned long keyboardMarks = 0, mouseMarks = 0, padMarks = 0;
} g_device;

// MarkKeyboardMouseInputK1.
void MarkKeyboardMouse(bool keyboard) {
    if (g_device.padActive || !g_device.chosen) Log("device: %s in use", keyboard ? "keyboard" : "mouse");
    g_device.padActive = false;
    g_device.chosen = true;
    ++(keyboard ? g_device.keyboardMarks : g_device.mouseMarks);
}

// K1NativeJoystick.cpp's activity test: K1_TRIGGER_THRESHOLD (60 of 255) and K1_ACTIVITY_STICK.
const float kTriggerThreshold = 60.0f / 255.0f;
const float kActivityStick = 0.35f;

// MouseIsBeingUsedK1: 2 moves and 24 pixels within a quarter second, and a jump of more than
// 300 pixels in one move is the engine placing the pointer, not a hand moving it. A move is a
// frame's change of the sampled position.
const std::uint64_t kMouseUseWindowMs = 250;
const int kMouseUseDistance = 24, kMouseUseMinEvents = 2, kMouseTeleport = 300;

struct Mouse {
    bool known = false;
    int lastX = 0, lastY = 0;
    std::uint64_t windowStart = 0;
    int windowDistance = 0, windowEvents = 0;
    std::uint64_t ownMoveUntil = 0;   // until then a change is the module's own move settling
    unsigned long moves = 0;          // changes of position seen, KMRP's own left out
} g_mouse;

struct Cursor {
    bool parked = false, followedPadMode = false, pendingToggle = false;
    unsigned long parks = 0, returns = 0, reasserts = 0;
} g_cursor;

bool MouseIsBeingUsed(int x, int y) {
    const std::uint64_t now = NowMs();
    if (!g_mouse.known || now < g_mouse.ownMoveUntil) {   // g_movingCursorOurselves' baseline
        g_mouse.known = true;
        g_mouse.lastX = x;
        g_mouse.lastY = y;
        g_mouse.windowStart = now;
        return false;
    }
    const int dx = x - g_mouse.lastX, dy = y - g_mouse.lastY;
    g_mouse.lastX = x;
    g_mouse.lastY = y;
    if (dx == 0 && dy == 0) return false;
    ++g_mouse.moves;
    if (dx > kMouseTeleport || dx < -kMouseTeleport || dy > kMouseTeleport || dy < -kMouseTeleport) return false;
    if (now - g_mouse.windowStart > kMouseUseWindowMs) {
        g_mouse.windowStart = now;
        g_mouse.windowDistance = 0;
        g_mouse.windowEvents = 0;
    }
    g_mouse.windowDistance += (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);
    ++g_mouse.windowEvents;
    return g_mouse.windowEvents >= kMouseUseMinEvents && g_mouse.windowDistance >= kMouseUseDistance;
}

// ------------------------------------------------------------------------ the cursor

void* Manager() {
    void* internal = engine::ClientInternal();
    void* manager = internal ? At<void*>(internal, engine::kInternalGuiManager) : nullptr;
    return LooksLikePointer(manager) ? manager : nullptr;
}

// MoveK1Cursor: to the parked spot, or back to the middle of the viewport, so a returned
// pointer is always somewhere visible.
bool MoveCursor(bool toParked) {
    void* manager = Manager();
    if (!manager) return false;
    const int width = At<std::int16_t>(manager, kMgrViewportWidth);
    const int height = At<std::int16_t>(manager, kMgrViewportHeight);
    if (width <= 0 || height <= 0) return false;
    MoveMouseToPosition(manager, width / 2, toParked ? kParkedCursorY : height / 2);
    g_mouse.ownMoveUntil = NowMs() + kOwnMoveSettleMs;
    return true;
}

// SetK1CursorHidden, off the live mask, so a reason cleared by anything else is put back.
void SetCursorHidden(void* internal, bool hide) {
    const std::uint32_t mask = At<std::uint32_t>(internal, kInternalMouseHideMask);
    if (hide == ((mask & kCursorHideReason) != 0)) return;
    (hide ? HideMouse : ShowMouse)(internal, kCursorHideReason);
}

// UpdateK1CursorState: parked when the pad becomes the device in use, given back the moment the
// mouse or keyboard is; a move that fails (no viewport yet, a load) is retried, not dropped; and
// while parked, the park spot is re-asserted against panels that place the pointer as they open.
void UpdateCursor() {
    if (!AppActive()) return;
    void* internal = engine::ClientInternal();
    if (!internal) return;
    const bool padMode = device::PadInUse();
    if (padMode != g_cursor.followedPadMode) {
        g_cursor.followedPadMode = padMode;
        g_cursor.pendingToggle = padMode != g_cursor.parked;
    }
    if (g_cursor.pendingToggle) {
        if (MoveCursor(!g_cursor.parked)) {
            g_cursor.pendingToggle = false;
            g_cursor.parked = !g_cursor.parked;
            ++(g_cursor.parked ? g_cursor.parks : g_cursor.returns);
            SetCursorHidden(internal, g_cursor.parked);
        }
        return;
    }
    if (!g_cursor.parked) return;
    SetCursorHidden(internal, true);
    void* manager = Manager();
    if (!manager) return;
    const int width = At<std::int16_t>(manager, kMgrViewportWidth);
    if (width <= 0) return;
    if (At<int>(manager, kMgrMouseX) != width / 2 || At<int>(manager, kMgrMouseY) != kParkedCursorY) {
        MoveCursor(true);
        ++g_cursor.reasserts;
    }
}

// ------------------------------------------------------------------------ the badges

// The family letter the art is named with (KmrpGlyphLetterK1); the last pad's while there is
// none, since then the badges are hidden anyway.
const char kFamilyLetters[] = {'p', 's', 'n', 'd'};
char g_familyLetter = 'p';

void UpdateFamily() {
    const int family = PadFamily();
    if (family >= 0 && family < 4 && kFamilyLetters[family] != g_familyLetter) {
        g_familyLetter = kFamilyLetters[family];
        Log("prompts: %c art", g_familyLetter);
    }
}

// Every panel painted and not cleared since, with its class, so a panel freed and replaced by
// another at the same address is recognised as a stranger (g_k1PaintedPanels).
struct Painted {
    void* panel;
    std::uintptr_t vtable;
};
const int kPaintedSlots = 32;
Painted g_painted[kPaintedSlots] = {};
int g_paintedNext = 0;

void RememberPainted(void* panel, std::uintptr_t vtable) {
    int free = -1;
    for (int i = 0; i < kPaintedSlots; ++i) {
        if (g_painted[i].panel == panel) { g_painted[i].vtable = vtable; return; }
        if (!g_painted[i].panel && free < 0) free = i;
    }
    if (free < 0) {
        free = g_paintedNext;
        g_paintedNext = (g_paintedNext + 1) % kPaintedSlots;
    }
    g_painted[free] = {panel, vtable};
}

bool TakePainted(void* panel, std::uintptr_t vtable) {
    for (int i = 0; i < kPaintedSlots; ++i) {
        if (g_painted[i].panel != panel) continue;
        const bool same = g_painted[i].vtable == vtable;
        g_painted[i] = {};
        return same;
    }
    return false;
}

struct PromptState {
    bool known = false, padMode = false;
    void* panel = nullptr;
    std::uintptr_t vtable = 0;
    int variant = -1;
    void* focus = nullptr;
    char family = 'p';
    unsigned long paints = 0, clears = 0;
} g_prompt;

void* ActiveControl(void* panel) { return panel ? At<void*>(panel, kPanelActive) : nullptr; }
bool Ignored(void* panel) { return (At<std::uint16_t>(panel, kPanelFlags) & kPanelIgnored) != 0; }

// The caption the filter button shows, as an index into the table, or -1 (K1InventoryFilterVariant).
int InventoryFilterVariant() {
    void* internal = engine::ClientInternal();
    void* inGame = internal ? At<void*>(internal, engine::kInternalGuiInGame) : nullptr;
    if (!LooksLikePointer(inGame)) return -1;
    const int current = At<std::uint8_t>(inGame, kGuiInGameInventoryFilter);
    if (current >= kInventoryFilterCount) return -1;
    return (current + 1) % kInventoryFilterCount;
}

// The panel taking input (FindK1MenuPanelForInput): the modal in front, if there is one, else
// the topmost panel with prompts, or the in-game menu's strip, whose prompts are its screen's.
void* FrontPanel(void* manager) {
    void** modals = At<void**>(manager, kMgrModals);
    const int modalCount = At<int>(manager, kMgrModalCount);
    for (int i = modalCount - 1; LooksLikePointer(modals) && i >= 0 && i < 256; --i)
        if (LooksLikePointer(modals[i]) && !Ignored(modals[i])) return modals[i];
    void** panels = At<void**>(manager, kMgrPanels);
    const int count = At<int>(manager, kMgrPanelCount);
    for (int i = count - 1; LooksLikePointer(panels) && i >= 0 && i < 256; --i) {
        void* panel = panels[i];
        if (!LooksLikePointer(panel) || Ignored(panel)) continue;
        if (gui::IsTabBar(panel) || PromptsFor(panel)) return panel;
    }
    return nullptr;
}

// The screen behind the strip: the topmost other panel with prompts.
void* ScreenBehindTabBar(void* manager, void* tabBar) {
    void** panels = At<void**>(manager, kMgrPanels);
    const int count = At<int>(manager, kMgrPanelCount);
    for (int i = count - 1; LooksLikePointer(panels) && i >= 0 && i < 256; --i) {
        void* panel = panels[i];
        if (panel != tabBar && LooksLikePointer(panel) && !Ignored(panel) && PromptsFor(panel)) return panel;
    }
    return nullptr;
}

bool OtherBadgedControlFocused(void* panel, const PromptScreen& screen, const PromptBinding& self) {
    void* active = ActiveControl(panel);
    if (!active) return false;
    for (std::size_t i = 0; i < screen.count; ++i)
        if (&screen.prompts[i] != &self && static_cast<char*>(panel) + screen.prompts[i].offset == active) return true;
    return false;
}

// K1PromptResref: the badge for what the button shows now, or nothing when the focus says this
// is not what the button would do.
const char* PromptResref(const PromptBinding& binding, void* panel, void* control, const PromptScreen& screen) {
    switch (binding.variant) {
        case Variant::FocusFallback:
            return OtherBadgedControlFocused(panel, screen, binding) ? nullptr : binding.resref;
        case Variant::FocusOnly:
            return control == ActiveControl(panel) ? binding.resref : nullptr;
        case Variant::InventoryFilter: {
            const int index = InventoryFilterVariant();
            return index >= 0 ? kInventoryFilterResrefs[index] : binding.resref;
        }
        case Variant::None:
            break;
    }
    return binding.resref;
}

struct ResRef {
    char name[32];   // CResRef is 16 characters; the rest stays zero
};

ResRef MakeResRef(const char* value, bool family) {
    ResRef r{};
    for (int i = 0; value && i < 16 && value[i]; ++i) r.name[i] = value[i];
    if (family && std::strncmp(r.name, "kmrp", 4) == 0) r.name[3] = g_familyLetter;
    return r;
}

// SetK1ControllerPromptFill: both borders, always as a pair: the engine draws the highlight
// border instead of the normal one while the control has the focus, so a badge written to one
// alone vanishes the moment it is focused.
void SetPromptFill(void* control, const char* value) {
    const ResRef r = MakeResRef(value, true);
    SetFillImage(static_cast<char*>(control) + kButtonBorderFill, r.name, 1);
    SetFillImage(static_cast<char*>(control) + kButtonHilightFill, r.name, 1);
}

// SetK1ControllerPromptArt: the button's own art back on both borders, verbatim.
void SetPromptArt(void* control, const char* border, const char* hilight) {
    const ResRef normal = MakeResRef(border, false);
    const ResRef focused = MakeResRef(hilight ? hilight : border, false);
    SetFillImage(static_cast<char*>(control) + kButtonBorderFill, normal.name, 1);
    SetFillImage(static_cast<char*>(control) + kButtonHilightFill, focused.name, 1);
}

// UpdateK1ControllerPrompts: nothing is written unless the panel, its class, the device, the
// filter's caption, the focus or the family changed. A panel is cleared when it is found in
// front with the keyboard or mouse in use and was painted before, which covers the screens the
// in-game menu keeps alive between visits.
void UpdatePrompts() {
    void* manager = Manager();
    void* panel = manager ? FrontPanel(manager) : nullptr;
    if (panel && gui::IsTabBar(panel)) panel = ScreenBehindTabBar(manager, panel);

    const bool padMode = device::PadInUse();
    const std::uintptr_t vtable = VtableOf(panel);
    const int variant = padMode ? InventoryFilterVariant() : -1;
    void* const focused = padMode ? ActiveControl(panel) : nullptr;

    if (g_prompt.known && panel == g_prompt.panel && vtable == g_prompt.vtable && padMode == g_prompt.padMode &&
        variant == g_prompt.variant && focused == g_prompt.focus && g_familyLetter == g_prompt.family)
        return;

    const bool clearing =
        !padMode && ((g_prompt.known && g_prompt.padMode && panel == g_prompt.panel && vtable == g_prompt.vtable) |
                     (panel != nullptr && TakePainted(panel, vtable)));
    const PromptScreen* screen = PromptsFor(panel);
    if ((padMode || clearing) && screen) {
        for (std::size_t i = 0; i < screen->count; ++i) {
            const PromptBinding& binding = screen->prompts[i];
            void* control = static_cast<char*>(panel) + binding.offset;
            const char* shown = padMode ? PromptResref(binding, panel, control, *screen) : nullptr;
            if (!shown && binding.restore) SetPromptArt(control, binding.restore, binding.restoreHilight);
            else SetPromptFill(control, shown);
        }
        if (padMode) {
            RememberPainted(panel, vtable);
            ++g_prompt.paints;
        } else {
            ++g_prompt.clears;
        }
    }

    g_prompt.known = true;
    g_prompt.panel = panel;
    g_prompt.vtable = vtable;
    g_prompt.padMode = padMode;
    g_prompt.variant = variant;
    g_prompt.focus = focused;
    g_prompt.family = g_familyLetter;
}

}  // namespace

// ------------------------------------------------------------------------ interface

namespace device {

void NotePad(bool present, const PadState& pad) {
    if (present != g_device.padConnected) {
        g_device.padConnected = present;
        Log("device: pad %s", present ? "present" : "gone");
    }
    if (!present) return;
    const bool meaningful = pad.buttons != 0 || pad.lt > kTriggerThreshold || pad.rt > kTriggerThreshold ||
                            std::sqrt(pad.lx * pad.lx + pad.ly * pad.ly) > kActivityStick ||
                            std::sqrt(pad.rx * pad.rx + pad.ry * pad.ry) > kActivityStick;
    if (!meaningful) return;
    if (!g_device.padActive) Log("device: pad in use");
    g_device.padActive = true;
    g_device.chosen = true;
    ++g_device.padMarks;
}

bool PadInUse() {
    if (g_device.padActive) return true;
    if (g_device.chosen) return false;
    return g_device.padConnected;
}

}  // namespace device

namespace prompts {

char FamilyLetter() { return g_familyLetter; }

void PaintLayoutEntry(void* button, bool shown) { SetPromptFill(button, shown ? "kmrpa_optgamelay" : nullptr); }

void Frame() {
    if (MouseIsBeingUsed(*reinterpret_cast<const int*>(kSampledPointerX),
                         *reinterpret_cast<const int*>(kSampledPointerY)))
        MarkKeyboardMouse(false);
    UpdateFamily();
    UpdatePrompts();
    cues::Update();
    UpdateCursor();
}

void Status() {
    Log("prompts: pad %s (%s), %lu screens painted, %lu cleared, %c art; keyboard seen %lu times, mouse %lu "
        "(%lu positions); cursor parked %lu times, given back %lu, re-parked %lu",
        device::PadInUse() ? "in use" : "not in use", g_device.chosen ? "chosen" : "by presence", g_prompt.paints,
        g_prompt.clears, g_familyLetter, g_device.keyboardMarks, g_device.mouseMarks, g_mouse.moves, g_cursor.parks,
        g_cursor.returns, g_cursor.reasserts);
}

}  // namespace prompts
}  // namespace kmrp

// GetEvents' read of the keyboard's buffer (0x1003563F3): the read made here, then its records
// looked at (KmrpNoteKeyboardK1). Every record in it is a key's: a key pressed is the keyboard
// in use. Always consumes: the stolen bytes are a relative call, which cannot run from the
// wrapper, and its result is not used by GetEvents.
extern "C" __attribute__((visibility("default"))) int KmrpNoteKeyboard(void* raw, void* buffer) {
    if (!raw || !buffer) return 1;
    kmrp::ReadKeyboardBuffer(raw, buffer);
    const char* records = *static_cast<char**>(buffer);
    const int count = *reinterpret_cast<int*>(static_cast<char*>(buffer) + 8);
    for (int i = 0; records && i < count && i < 256; ++i) {
        const std::uint32_t value = *reinterpret_cast<const std::uint32_t*>(records + i * kmrp::kRecordBytes + kmrp::kRecordValue);
        if (value & kmrp::kKeyPressed) {
            kmrp::MarkKeyboardMouse(true);
            break;
        }
    }
    return 1;
}
