#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <windows.h>

#include "K1XboxControlsXInput.h"

namespace {

constexpr int MAX_ACTION_BUTTON_COUNT = 9;
constexpr std::uint32_t CONTROL_VISIBLE = 0x0002;
constexpr std::uint32_t PANEL_IGNORED_BY_INPUT = 0x0600;

constexpr std::uint32_t DIK_UP = 0xC8;
constexpr std::uint32_t DIK_DOWN = 0xD0;
constexpr std::uint32_t DIK_LEFT = 0xCB;
constexpr std::uint32_t DIK_RIGHT = 0xCD;
constexpr std::uint32_t DIK_R = 0x13;
constexpr std::uint32_t DIK_RETURN = 0x1C;
constexpr std::uint32_t DIK_ESCAPE = 0x01;
constexpr std::uint32_t DIK_DELETE = 0xD3;
constexpr std::uint32_t DIK_SPACE = 0x39;
constexpr std::uint32_t DIK_HOME = 0xC7;
constexpr std::uint32_t DIK_END = 0xCF;
constexpr std::uint32_t DIK_INSERT = 0xD2;
constexpr std::uint32_t DIK_PRIOR = 0xC9;
constexpr std::uint32_t DIK_NEXT = 0xD1;
constexpr std::uint32_t DIK_F9 = 0x43;
constexpr std::uint32_t KEY_PRESSED = 0x80;

constexpr std::uint32_t PENDING_UP = 1 << 0;
constexpr std::uint32_t PENDING_DOWN = 1 << 1;
constexpr std::uint32_t PENDING_LEFT = 1 << 2;
constexpr std::uint32_t PENDING_RIGHT = 1 << 3;
constexpr std::uint32_t PENDING_ACTIVATE = 1 << 4;
constexpr std::uint32_t PENDING_CONTEXT_CANCEL = 1 << 5;
constexpr std::uint32_t PENDING_CONTROLLER_X = 1 << 6;
constexpr std::uint32_t PENDING_CONTROLLER_LEFT = 1 << 7;
constexpr std::uint32_t PENDING_CONTROLLER_RIGHT = 1 << 8;
constexpr std::uint32_t PENDING_K1_PAZAAK_SWITCH_GRID = 1 << 12;
constexpr std::uint32_t PENDING_K1_PAZAAK_PLAY = 1 << 13;
constexpr std::uint32_t PENDING_K1_PAZAAK_RETURN = 1 << 14;
constexpr std::uint32_t PENDING_K1_PAZAAK_INITIAL_FOCUS = 1 << 15;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_LEFT = 1 << 16;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_RIGHT = 1 << 17;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_PLAY_CARD = 1 << 18;
constexpr std::uint32_t PENDING_K1_PARTY_BUTTON_ROW = 1 << 19;
constexpr std::uint32_t PENDING_K1_PARTY_GRID_RETURN = 1 << 20;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_FLIP_DOWN = 1 << 21;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_FLIP_UP = 1 << 22;
constexpr std::uint32_t PENDING_K1_PAZAAK_GAME_FLIP_CARD = 1 << 23;
constexpr std::uint32_t PENDING_K1_CLASS_SELECT_LEFT = 1 << 27;
constexpr std::uint32_t PENDING_K1_CLASS_SELECT_RIGHT = 1 << 28;
// constexpr std::uint32_t PENDING_K1_MENU_ACTION = 1 << 29;  // dead, never raised
// Experimental: End/Home/Insert -> generic X/Y/Black dispatch to whatever panel is active.
constexpr std::uint32_t PENDING_K1_GENERIC_BUTTON = 1 << 30;
constexpr std::uint32_t PENDING_K1_SETTINGS_NAV = 1u << 31;

// ---------------------------------------------------------------------------
// DEAD CODE, disabled 2026-09-06. Kept rather than deleted because it documents
// an intended design and may be revived.
//
// This per-panel "menu action map" was meant to let X/Y/Black invoke a named
// button on each screen by calling the handler that button registers. It never
// runs: PENDING_K1_MENU_ACTION is only ever TESTED and CLEARED -- nothing raises
// it, and g_pendingMenuAction is never assigned -- so ResolveK1MenuAction and
// every *_CALLBACK address below are unreachable.
//
// What actually drives those buttons is CaptureK1GenericButton: X/Y/LB carry a
// second scancode (End/Home/Insert) which is captured and dispatched to the
// panel as the retained Xbox GUI events, letting each panel's own handler act.
// A and B need no map either -- A is Return (activates the focused control) and
// B is Delete, rewritten to Escape for menu panels.
//
// This mattered: it was read as the thing that made the shipped badges truthful,
// which led to the wrong conclusion about which glyphs are safe to add.
// ---------------------------------------------------------------------------
#if 0   // dead: menu action map types
enum class MenuActionSlot : std::uint8_t {
    Primary,
    Secondary,
    Auxiliary1,
    Auxiliary2,
};

struct MenuActionTarget {
    std::ptrdiff_t offset;
    std::ptrdiff_t stride;
    int index;
    std::uintptr_t callback;
};

constexpr MenuActionTarget NO_MENU_ACTION = {-1, 0, -1, 0};

struct MenuActionMap {
    MenuActionTarget primary;
    MenuActionTarget secondary;
    MenuActionTarget auxiliary1;
    MenuActionTarget auxiliary2;
};

constexpr MenuActionMap NO_MENU_ACTIONS = {
    NO_MENU_ACTION,
    NO_MENU_ACTION,
    NO_MENU_ACTION,
    NO_MENU_ACTION,
};
#endif  // 0

constexpr std::uint32_t PENDING_ACTION_BAR_INPUT =
    PENDING_UP | PENDING_DOWN | PENDING_LEFT | PENDING_RIGHT | PENDING_ACTIVATE;
constexpr std::uint32_t PENDING_CONTEXT_INPUT =
    PENDING_CONTEXT_CANCEL | PENDING_CONTROLLER_X |
    PENDING_CONTROLLER_LEFT | PENDING_CONTROLLER_RIGHT |
    PENDING_K1_PAZAAK_SWITCH_GRID |
    PENDING_K1_PAZAAK_PLAY | PENDING_K1_PAZAAK_RETURN |
    PENDING_K1_PAZAAK_INITIAL_FOCUS |
    PENDING_K1_PAZAAK_GAME_LEFT | PENDING_K1_PAZAAK_GAME_RIGHT |
    PENDING_K1_PAZAAK_GAME_PLAY_CARD |
    PENDING_K1_PARTY_BUTTON_ROW | PENDING_K1_PARTY_GRID_RETURN |
    PENDING_K1_PAZAAK_GAME_FLIP_DOWN |
    PENDING_K1_PAZAAK_GAME_FLIP_UP |
    PENDING_K1_PAZAAK_GAME_FLIP_CARD |
    PENDING_K1_CLASS_SELECT_LEFT | PENDING_K1_CLASS_SELECT_RIGHT |
    PENDING_K1_GENERIC_BUTTON |
    PENDING_K1_SETTINGS_NAV;
constexpr std::uint32_t PENDING_K1_MENU_INPUT =
    PENDING_CONTROLLER_X |
    PENDING_K1_PAZAAK_SWITCH_GRID | PENDING_K1_PAZAAK_PLAY |
    PENDING_K1_PAZAAK_RETURN | PENDING_K1_PAZAAK_INITIAL_FOCUS |
    PENDING_K1_PAZAAK_GAME_LEFT | PENDING_K1_PAZAAK_GAME_RIGHT |
    PENDING_K1_PAZAAK_GAME_PLAY_CARD |
    PENDING_K1_PARTY_BUTTON_ROW | PENDING_K1_PARTY_GRID_RETURN |
    PENDING_K1_PAZAAK_GAME_FLIP_DOWN |
    PENDING_K1_PAZAAK_GAME_FLIP_UP |
    PENDING_K1_PAZAAK_GAME_FLIP_CARD |
    PENDING_K1_CLASS_SELECT_LEFT | PENDING_K1_CLASS_SELECT_RIGHT |
    PENDING_K1_GENERIC_BUTTON |
    PENDING_K1_SETTINGS_NAV;

constexpr int K2_GUI_CONTROLLER_X_EVENT = 0x29;
constexpr int K2_GUI_CONTROLLER_LEFT_EVENT = 0x2F;
constexpr int K2_GUI_CONTROLLER_RIGHT_EVENT = 0x30;
constexpr int K1_GUI_CONTROLLER_X_EVENT = 0x29;
// Experimental generic button events (real GuiEvents enum values, per-panel meaning is up to the panel).
constexpr int K1_GUI_A_BUTTON_EVENT = 0x27;
constexpr int K1_GUI_B_BUTTON_EVENT = 0x28;
constexpr int K1_GUI_Y_BUTTON_EVENT = 0x2A;
constexpr int K1_GUI_BLACK_BUTTON_EVENT = 0x2B;
constexpr std::uintptr_t K1_ABILITIES_PANEL_VTABLE = 0x00755E50;
constexpr std::uintptr_t K1_CHARACTER_PANEL_VTABLE = 0x00756100;
constexpr std::uintptr_t K1_INVENTORY_PANEL_VTABLE = 0x007564E0;
constexpr std::uintptr_t K1_JOURNAL_PANEL_VTABLE = 0x00751960;
constexpr std::uintptr_t K1_MAP_PANEL_VTABLE = 0x00754830;
constexpr std::uintptr_t K1_MESSAGES_PANEL_VTABLE = 0x0074FD18;
constexpr std::uintptr_t K1_LEVEL_UP_PANEL_VTABLE = 0x00759568;
constexpr std::uintptr_t K1_POWERS_PANEL_VTABLE = 0x00759780;
constexpr std::uintptr_t K1_FEATS_PANEL_VTABLE = 0x007598B0;
constexpr std::uintptr_t K1_SKILLS_PANEL_VTABLE = 0x00759990;
constexpr std::uintptr_t K1_NAME_PANEL_VTABLE = 0x00759F38;
constexpr std::uintptr_t K1_ABILITIES_CHARGEN_PANEL_VTABLE = 0x00759C68;
constexpr std::uintptr_t K1_SOLO_MODE_QUERY_PANEL_VTABLE = 0x00756F28;
constexpr std::uintptr_t K1_PAZAAK_SETUP_PANEL_VTABLE = 0x007532E8;
constexpr std::uintptr_t K1_PAZAAK_GAME_PANEL_VTABLE = 0x00753358;
constexpr std::uintptr_t K1_PARTY_SELECT_PANEL_VTABLE = 0x00756D28;
constexpr std::uintptr_t K1_CLASS_SELECT_PANEL_VTABLE = 0x00758020;
constexpr std::uintptr_t K1_CONTAINER_PANEL_VTABLE = 0x007567E0;
constexpr std::uintptr_t K1_SAVELOAD_PANEL_VTABLE = 0x00757650;
constexpr std::uintptr_t K1_UPGRADE_SELECTION_PANEL_VTABLE = 0x007571B0;
constexpr std::uintptr_t K1_MAIN_MENU_PANEL_VTABLE = 0x00752F70;
constexpr std::uintptr_t K1_INGAME_GAMEPLAY_PANEL_VTABLE = 0x00758E00;
constexpr std::uintptr_t K1_INGAME_AUTOPAUSE_PANEL_VTABLE = 0x00758EE0;
constexpr std::uintptr_t K1_UPGRADE_ITEM_SELECT_PANEL_VTABLE = 0x00757228;
constexpr std::uintptr_t K1_UPGRADE_PANEL_VTABLE = 0x00757298;
// The store needs no strip table: CSWGuiStore::HandleInputEvent already answers
// the X button by toggling ShowBuyGUI/ShowSellGUI, and B closes, so its bottom
// row is reachable through the face buttons once the panel is recognised at all.
constexpr std::uintptr_t K1_STORE_PANEL_VTABLE = 0x00756E38;
constexpr std::uintptr_t K1_INGAME_OPTIONS_PANEL_VTABLE = 0x00755DE0;
constexpr std::uintptr_t K1_KEY_MAPPINGS_PANEL_VTABLE = 0x00759358;
constexpr std::uintptr_t K1_OPTIONS_MAIN_PANEL_VTABLE = 0x00758838;
constexpr std::uintptr_t K1_OPTIONS_FEEDBACK_PANEL_VTABLE = 0x007581E8;
constexpr std::uintptr_t K1_OPTIONS_GRAPHICS_PANEL_VTABLE = 0x007586F8;
constexpr std::uintptr_t K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE = 0x007584A0;
constexpr std::uintptr_t K1_OPTIONS_MOUSE_PANEL_VTABLE = 0x007585F8;
constexpr std::uintptr_t K1_OPTIONS_RESOLUTION_PANEL_VTABLE = 0x00758348;
constexpr std::uintptr_t K1_OPTIONS_SOUND_PANEL_VTABLE = 0x007587C0;
constexpr std::uintptr_t K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE = 0x00758550;
constexpr std::uintptr_t K1_FLOATY_TEXT_PANEL_VTABLE = 0x00753EA8;
constexpr std::uintptr_t K1_BARK_BUBBLE_PANEL_VTABLE = 0x00755C60;
constexpr std::uintptr_t K1_MESSAGE_BOX_PANEL_VTABLE = 0x0074FDB0;
constexpr std::uintptr_t K1_CONTROLLER_LOSS_BOX_PANEL_VTABLE = 0x007513F8;
constexpr std::uintptr_t K1_GUI_BORDER_SET_FILL_IMAGE = 0x00414C00;
constexpr std::ptrdiff_t K1_BUTTON_BORDER_PARAMS_OFFSET = 0x0080;
constexpr std::ptrdiff_t K1_BUTTON_HILIGHT_PARAMS_OFFSET = 0x00F4;
constexpr std::uintptr_t K1_GUI_MANAGER_GLOBAL = 0x007A39F4;
constexpr std::ptrdiff_t K1_PAZAAK_AVAILABLE_OFFSET = 0x01A4;
constexpr int K1_PAZAAK_AVAILABLE_COUNT = 18;
constexpr int K1_PAZAAK_AVAILABLE_ROWS = 6;
constexpr std::ptrdiff_t K1_PAZAAK_CHOSEN_OFFSET = 0x501C;
constexpr int K1_PAZAAK_CHOSEN_COUNT = 10;
constexpr int K1_PAZAAK_CHOSEN_COLUMNS = 2;
constexpr std::ptrdiff_t K1_PAZAAK_PLAY_OFFSET = 0x7108;
constexpr std::ptrdiff_t K1_PAZAAK_CARD_STRIDE = 0x031C;
constexpr std::ptrdiff_t K1_PAZAAK_HAND_OFFSET = 0x2DE0;
constexpr int K1_PAZAAK_HAND_COUNT = 4;
constexpr std::ptrdiff_t K1_PAZAAK_FLIP_OFFSET = 0x62BC;
constexpr std::ptrdiff_t K1_PAZAAK_FLIP_STRIDE = 0x01C4;
constexpr std::ptrdiff_t K1_PAZAAK_END_TURN_OFFSET = 0x6C4C;
constexpr std::uintptr_t K1_PAZAAK_PLAY_CARD_CALLBACK = 0x0067EF80;
constexpr std::uintptr_t K1_PAZAAK_FLIP_CARD_CALLBACK = 0x0067DDA0;
constexpr std::ptrdiff_t K1_PARTY_GRID_OFFSET = 0x007C;
constexpr std::ptrdiff_t K1_PARTY_GRID_STRIDE = 0x0454;
constexpr int K1_PARTY_GRID_COUNT = 9;
constexpr int K1_PARTY_BOTTOM_ROW_START = 6;
constexpr std::ptrdiff_t K1_PARTY_DONE_OFFSET = 0x28B0;
constexpr std::ptrdiff_t K1_PARTY_BACK_OFFSET = 0x36F4;
constexpr std::ptrdiff_t K1_CLASS_SELECT_OFFSET = 0x006C;
constexpr std::ptrdiff_t K1_CLASS_SELECT_STRIDE = 0x025C;
constexpr int K1_CLASS_SELECT_COUNT = 6;
constexpr std::ptrdiff_t K1_CHARACTER_SCRIPTS_OFFSET = 0x5400;
constexpr std::ptrdiff_t K1_CHARACTER_EXIT_OFFSET = 0x523C;
constexpr std::ptrdiff_t K1_CONTAINER_GET_ITEMS_OFFSET = 0x0AD0;
constexpr std::ptrdiff_t K1_CONTAINER_CANCEL_OFFSET = 0x0C94;
constexpr std::ptrdiff_t K1_CONTAINER_GIVE_ITEMS_OFFSET = 0x0E58;
constexpr std::ptrdiff_t K1_SAVELOAD_LOAD_OFFSET = 0x0C14;
constexpr std::ptrdiff_t K1_SAVELOAD_BACK_OFFSET = 0x0DD8;
constexpr std::ptrdiff_t K1_SAVELOAD_DELETE_OFFSET = 0x0F9C;
constexpr std::ptrdiff_t K1_UPGRADE_ITEMS_OFFSET = 0x01A4;
constexpr std::ptrdiff_t K1_NAME_EDITBOX_OFFSET = 0x0230;
constexpr std::ptrdiff_t K1_NAME_OK_OFFSET = 0x006C;
constexpr std::ptrdiff_t K1_NAME_CANCEL_OFFSET = 0x0610;
constexpr std::ptrdiff_t K1_NAME_RANDOM_OFFSET = 0x07D4;
constexpr std::ptrdiff_t K1_SOLO_QUERY_OK_OFFSET = 0x02F4;
constexpr std::ptrdiff_t K1_SOLO_QUERY_CANCEL_OFFSET = 0x04B8;
#if 0   // dead: handler addresses for the menu action map
// Handlers each button already registers via AddEvent(0x27, ...) in its constructor.
constexpr std::uintptr_t K1_CHARACTER_SCRIPTS_CALLBACK = 0x00624BC0;
constexpr std::uintptr_t K1_CONTAINER_GET_ITEMS_CALLBACK = 0x00624BA0;
constexpr std::uintptr_t K1_CONTAINER_GIVE_ITEMS_CALLBACK = 0x00624BC0;
constexpr std::uintptr_t K1_SAVELOAD_LOAD_CALLBACK = 0x00624BA0;
constexpr std::uintptr_t K1_SAVELOAD_DELETE_CALLBACK = 0x00624BC0;
constexpr std::uintptr_t K1_UPGRADE_ITEMS_CALLBACK = 0x006C2B60;
#endif  // 0

// Member offsets below are from kotor1_0_3.db `offsets`, keyed by the class each
// vtable resolves to. `*_TAIL*` are the bottom few controls of a panel's option
// column, listed bottom-up: which of them is actually present varies by context
// (Quit is hidden on some Options screens), so the tail is resolved at runtime by
// taking the first selectable one. Strip offsets are left-to-right on screen.
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_QUIT_OFFSET = 0x0CC0;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_SOUND_OFFSET = 0x0AFC;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_GRAPHICS_OFFSET = 0x0938;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_AUTOPAUSE_OFFSET = 0x0774;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_FEEDBACK_OFFSET = 0x05B0;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_GAMEPLAY_OFFSET = 0x03EC;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_SAVEGAME_OFFSET = 0x0228;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_TAIL_LOADGAME_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_EXIT_OFFSET = 0x1BE8;
constexpr std::ptrdiff_t K1_INGAME_GAMEPLAY_TAIL_KEYMAP_OFFSET = 0x094C;
constexpr std::ptrdiff_t K1_INGAME_GAMEPLAY_TAIL_MOUSE_OFFSET = 0x0B10;
constexpr std::ptrdiff_t K1_INGAME_GAMEPLAY_DEFAULT_OFFSET = 0x0788;
constexpr std::ptrdiff_t K1_INGAME_GAMEPLAY_BACK_OFFSET = 0x05C4;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_TRIGGERS_OFFSET = 0x0DE8;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_ACTION_MENU_OFFSET = 0x0B34;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_PARTY_KILLED_OFFSET = 0x0880;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_MINE_OFFSET = 0x05CC;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_ENEMY_OFFSET = 0x0318;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_TAIL_END_ROUND_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_DEFAULT_OFFSET = 0x14E0;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_BACK_OFFSET = 0x131C;
// Upgrade Bench, screen 1: a 2x2 category grid over an Upgrade Items / Close
// strip. Tail is listed bottom row first, left to right, then the row above in the
// same order, so index + bottomRowWidth is always the cell directly above.
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_TAIL_MELEE_OFFSET = 0x08B4;
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_TAIL_ARMOR_OFFSET = 0x0A78;
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_TAIL_LIGHTSABER_OFFSET = 0x052C;
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_TAIL_RANGED_OFFSET = 0x06F0;
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_UPGRADE_OFFSET = 0x01A4;
constexpr std::ptrdiff_t K1_UPGRADE_SELECTION_BACK_OFFSET = 0x0368;
// Screen 3, CSWGuiUpgrade: one row of upgrade slots over Assemble / Cancel.
// upgrade.gui carries two alternative slot rows - BTN_UPGRADE41..44 for four-slot
// items (CSWGuiButton[4] at 0x0064) and BTN_UPGRADE31..33 for three (the [3] at
// 0x0774) - and only one row is live at a time, so all seven are listed as one
// bottom row and the hidden set is filtered out at runtime. The four-slot row goes
// first so the leftmost live slot resolves as the return target either way.
// Assemble and Cancel are the class's only standalone buttons, matching the .gui's
// only standalone buttons BTN_ASSEMBLE and BTN_BACK; no method of the class
// references either offset, so the pairing comes from the LBL_UPGRADES ->
// LBL_UPGRADE_COUNT -> BTN_ASSEMBLE run being consecutive in both.
constexpr std::ptrdiff_t K1_UPGRADE_SLOT4_1_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT4_2_OFFSET = 0x0228;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT4_3_OFFSET = 0x03EC;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT4_4_OFFSET = 0x05B0;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT3_1_OFFSET = 0x0774;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT3_2_OFFSET = 0x0938;
constexpr std::ptrdiff_t K1_UPGRADE_SLOT3_3_OFFSET = 0x0AFC;
constexpr std::ptrdiff_t K1_UPGRADE_ASSEMBLE_OFFSET = 0x2AA0;
constexpr std::ptrdiff_t K1_UPGRADE_BACK_OFFSET = 0x2D84;
constexpr int K1_UPGRADE_SLOT_COUNT = 7;
// Screen 2: the chosen category's items in a listbox over Upgrade Item / Close.
constexpr std::ptrdiff_t K1_UPGRADE_ITEM_SELECT_TAIL_LISTBOX_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_UPGRADE_ITEM_SELECT_UPGRADE_OFFSET = 0x08A4;
constexpr std::ptrdiff_t K1_UPGRADE_ITEM_SELECT_BACK_OFFSET = 0x0A68;
// Key Mapping's binding rows are individual buttons held in keymap_buttons, so no
// fixed offset names them; it navigates as a dynamic column keyed off the row's
// own null `down` link, with event_list_list_box as the return target.
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_TAIL_LIST_OFFSET = 0x0C48;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_TAB_MOVEMENT_OFFSET = 0x06FC;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_TAB_GAME_OFFSET = 0x08C0;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_TAB_MINIGAME_OFFSET = 0x0A84;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_FILTER_CATEGORY_OFFSET = 0x0F28;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_DEFAULT_OFFSET = 0x01B0;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_CANCEL_OFFSET = 0x0538;
constexpr std::ptrdiff_t K1_KEY_MAPPINGS_ACCEPT_OFFSET = 0x0374;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_QUIT_OFFSET = 0x0938;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_SOUND_OFFSET = 0x0774;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_GRAPHICS_OFFSET = 0x05B0;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_AUTOPAUSE_OFFSET = 0x03EC;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_FEEDBACK_OFFSET = 0x0228;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_TAIL_GAMEPLAY_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_BACK_OFFSET = 0x0D7C;
constexpr std::ptrdiff_t K1_OPTIONS_FEEDBACK_TAIL_LISTBOX_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_OPTIONS_FEEDBACK_DEFAULT_OFFSET = 0x0A68;
constexpr std::ptrdiff_t K1_OPTIONS_FEEDBACK_BACK_OFFSET = 0x08A4;
constexpr std::ptrdiff_t K1_OPTIONS_MOUSE_TAIL_REVERSE_OFFSET = 0x0C44;
constexpr std::ptrdiff_t K1_OPTIONS_MOUSE_TAIL_SENSITIVITY_OFFSET = 0x094C;
constexpr std::ptrdiff_t K1_OPTIONS_MOUSE_DEFAULT_OFFSET = 0x0788;
constexpr std::ptrdiff_t K1_OPTIONS_MOUSE_BACK_OFFSET = 0x05C4;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_TAIL_ADVANCED_OFFSET = 0x1370;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_TAIL_GRASS_OFFSET = 0x10BC;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_TAIL_SHADOWS_OFFSET = 0x0E08;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_TAIL_RESOLUTION_OFFSET = 0x08BC;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_TAIL_GAMMA_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_DEFAULT_OFFSET = 0x16F8;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_BACK_OFFSET = 0x1534;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_VSYNC_OFFSET = 0x0B2C;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_SOFTSHADOW_OFFSET = 0x0878;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_FRAMEBUFFER_OFFSET = 0x05C4;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_ANISOTROPY_OFFSET = 0x0DE0;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_ANTIALIAS_OFFSET = 0x132C;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_TEXQUALITY_OFFSET = 0x1878;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_OK_OFFSET = 0x1DC4;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_DEFAULT_OFFSET = 0x1F88;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_CANCEL_OFFSET = 0x214C;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_TAIL_ADVANCED_OFFSET = 0x152C;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_TAIL_MOVIE_OFFSET = 0x058C;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_DEFAULT_OFFSET = 0x1368;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_BACK_OFFSET = 0x11A4;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_TAIL_EAX_OFFSET = 0x031C;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_TAIL_SOFTWARE_OFFSET = 0x0064;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_OK_OFFSET = 0x0DC8;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_DEFAULT_OFFSET = 0x0F8C;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_CANCEL_OFFSET = 0x1150;
constexpr int K1_GUI_LEFT_BUTTON_EVENT = 0x2F;
constexpr int K1_GUI_RIGHT_BUTTON_EVENT = 0x30;
// GuiEvents has verbs for scrolling a listbox that are separate from the
// directional ones, so a description pane can be scrolled without moving
// focus into it. CSWGuiListBox::HandleInputEvent (0x0041CE20, reached through
// the control vtable at +0x3C like every other dispatch here) takes them.
// This is the whole reason the pane is reachable at all: the mouse wheel path
// the engine offers is hit-tested against the cursor, so with a controller it
// scrolls whatever the pointer was last left over, which is usually nothing.
constexpr int K1_GUI_SCROLL_DOWN_ARROW_EVENT = 0x1FB;
constexpr int K1_GUI_SCROLL_UP_ARROW_EVENT = 0x1FC;
// Equipment is not in IsK1MenuPanel, so FindK1MenuPanel never returns it and
// its entry in the table below stays dead. Listing it anyway keeps the address
// with the rest; bringing the screen under the mod is a separate decision.
constexpr std::uintptr_t K1_EQUIP_PANEL_VTABLE = 0x007569A0;
// Written by its constructor at 0x006D26FB.
constexpr std::uintptr_t K1_QUESTITEM_PANEL_VTABLE = 0x00757C20;
// description_listbox on each panel that has one, from kotor1_0_3.db and
// cross-checked against the shipped .gui files. Two are named differently in
// the engine: AutoPause calls it details_list_box (LB_DETAILS) and Mouse
// carries the original misspelling descritpion. Character and Container have
// no description pane at all, so they are deliberately absent.
constexpr std::ptrdiff_t K1_INGAME_OPTIONS_DESC_OFFSET = 0x1908;
constexpr std::ptrdiff_t K1_INGAME_GAMEPLAY_DESC_OFFSET = 0x02E4;
constexpr std::ptrdiff_t K1_INGAME_AUTOPAUSE_DESC_OFFSET = 0x16A4;
constexpr std::ptrdiff_t K1_OPTIONS_MAIN_DESC_OFFSET = 0x0F40;
constexpr std::ptrdiff_t K1_OPTIONS_FEEDBACK_DESC_OFFSET = 0x05C4;
constexpr std::ptrdiff_t K1_OPTIONS_MOUSE_DESC_OFFSET = 0x02E4;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_DESC_OFFSET = 0x05DC;
constexpr std::ptrdiff_t K1_OPTIONS_GRAPHICS_ADVANCED_DESC_OFFSET = 0x02E4;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_DESC_OFFSET = 0x0EC4;
constexpr std::ptrdiff_t K1_OPTIONS_SOUND_ADVANCED_DESC_OFFSET = 0x0AE8;
constexpr std::ptrdiff_t K1_UPGRADE_DESC_OFFSET = 0x1860;
constexpr std::ptrdiff_t K1_UPGRADE_ITEM_SELECT_DESC_OFFSET = 0x0344;
constexpr std::ptrdiff_t K1_INVENTORY_DESC_OFFSET = 0x0844;
constexpr std::ptrdiff_t K1_STORE_DESC_OFFSET = 0x1A40;
constexpr std::ptrdiff_t K1_ABILITIES_DESC_OFFSET = 0x33BC;
// The Abilities screen: three tabs in a row across the top (Skills, Powers,
// Feats, left to right on screen), the ability list below them, and Close in the
// bottom strip. Offsets are from kotor1_0_3.db class CSWGuiInGameAbilities,
// which names them; description_listbox in that table is 0x33BC, matching the
// constant above, so the table agrees with what already shipped.
//
// Before this the panel had no strip entry at all, so the module contributed no
// navigation here and the three tabs could not be reached with a controller --
// they are ordinary buttons and nothing routed focus to them.
constexpr std::ptrdiff_t K1_ABILITIES_TAB_SKILLS_OFFSET = 0x2F18;
constexpr std::ptrdiff_t K1_ABILITIES_TAB_POWERS_OFFSET = 0x2D54;
constexpr std::ptrdiff_t K1_ABILITIES_TAB_FEATS_OFFSET = 0x2B90;
constexpr std::ptrdiff_t K1_ABILITIES_LISTBOX_OFFSET = 0x30DC;
constexpr std::ptrdiff_t K1_ABILITIES_EXIT_OFFSET = 0x369C;

// The in-game tab screens. Offsets, extents and labels were all measured on the
// live panels, and so were the glyphs.
//
// An earlier version made every one of these an A badge, reasoning that these
// panels sit behind the tab strip so the retained 0x28 and 0x29 cannot reach
// them. Wrong: on the live Inventory screen B changes 95% of the display and
// takes the input class from 2 to 0 -- it closes -- and X changes 3.2% while
// staying in the menu, so X acts on the screen. Y changes 0.27%, which is noise.
// Close is B, the screen's own action is X, and everything else is focus + A.
constexpr std::uintptr_t K1_INGAME_MENU_PANEL_VTABLE = 0x00750148;

constexpr std::ptrdiff_t K1_INVENTORY_CLOSE_OFFSET     = 0x1164;
constexpr std::ptrdiff_t K1_INVENTORY_USEITEM_OFFSET   = 0x1328;
constexpr std::ptrdiff_t K1_INVENTORY_SHOWNEW_OFFSET   = 0x14EC;

constexpr std::ptrdiff_t K1_MESSAGES_CLOSE_OFFSET      = 0x0930;
constexpr std::ptrdiff_t K1_MESSAGES_FEEDBACK_OFFSET   = 0x076C;

constexpr std::ptrdiff_t K1_JOURNAL_QUESTITEMS_OFFSET  = 0x08A4;
constexpr std::ptrdiff_t K1_JOURNAL_COMPLETED_OFFSET   = 0x0A68;
constexpr std::ptrdiff_t K1_JOURNAL_SORT_OFFSET        = 0x0C2C;
constexpr std::ptrdiff_t K1_JOURNAL_CLOSE_OFFSET       = 0x0DF0;

constexpr std::ptrdiff_t K1_MAP_RETURN_OFFSET          = 0x0564;
constexpr std::ptrdiff_t K1_MAP_PARTY_OFFSET           = 0x0728;
constexpr std::ptrdiff_t K1_MAP_CLOSE_OFFSET           = 0x08EC;
constexpr std::ptrdiff_t K1_FEATS_DESC_OFFSET = 0x16DC;
constexpr std::ptrdiff_t K1_POWERS_DESC_OFFSET = 0x0FCC;
constexpr std::ptrdiff_t K1_EQUIP_DESC_OFFSET = 0x33B8;

// Parking the pointer when the mouse goes idle, so a controller session is not
// played around a stray cursor sitting on a button.
//
// Hiding alone is not enough and is the trap here: CExoInputInternal::HideMouse
// is only a ShowCursor(0) loop, so the pointer keeps hit-testing while
// invisible - it would still highlight controls and still swallow clicks. And
// KOTOR draws a second, software cursor through the GUI manager, so even the
// visual side needs both layers.
//
// Parking is just a move, through the engine's own MoveMouseToPosition, and
// nothing here hides anything. Two earlier approaches are worth not repeating:
//
// Hiding via HideSoftwareMouse/ShowSoftwareMouse produced a second cursor on
// screen. Hide destroys the software cursor at manager+0x20 and clears +0x24,
// but Show only tests +0x24 before calling ActivateSoftwareMouse, so toggling
// can build a second one. Leaving that pair alone avoids the whole problem.
//
// Parking off-screen panned the camera. MoveMouseToPosition forwards to
// HandleMouseMove, whose first act is feeding the position into the 3D scene
// view at param_1[9] as (x, height - y) scaled by 0.01, and SetMousePos clamps
// the pointer to a screen edge - which is where edge-scroll panning lives.
//
// Near the top-centre dodges both: horizontally centred is neutral for edge
// panning, and the small vertical inset keeps the cursor off the window edge
// without placing it over the controls below.
// Hiding goes through the engine's own reason mask at CClientExoAppInternal
// +0x3D8: HideMouse ORs a reason in, ShowMouse clears one and only actually
// shows the cursor once every reason has cleared. Holding a reason of our own
// is what makes this stick - the engine shows the mouse itself at scene
// transitions, and entering gameplay is one, but its ShowMouse passes its own
// bits and so cannot clear ours.
//
// An earlier attempt drove Win32 ShowCursor directly and lost that fight every
// time gameplay started. The mask is also why HideSoftwareMouse is safe here
// when it was not before: the engine owns both sides of the pair, so the
// destroy and recreate stay balanced instead of stacking a second cursor on
// top of the hardware one.
//
// 0x02 and 0x04 are the engine's own reasons and it tests 0x4A and 0x14, so
// this takes a bit well clear of anything in use.
constexpr std::uintptr_t K1_CLIENT_HIDE_MOUSE = 0x0061F9C0;
constexpr std::uintptr_t K1_CLIENT_SHOW_MOUSE = 0x0061FA00;
constexpr std::ptrdiff_t K1_CLIENT_MOUSE_HIDE_MASK_OFFSET = 0x03D8;
constexpr std::uint32_t K1_CURSOR_HIDE_REASON = 0x0100;
constexpr std::uintptr_t K1_GUI_MOVE_MOUSE_TO_POSITION = 0x0040C790;
constexpr std::ptrdiff_t K1_MANAGER_MOUSE_X_OFFSET = 0x0000;
constexpr std::ptrdiff_t K1_MANAGER_MOUSE_Y_OFFSET = 0x0004;
constexpr int K1_PARKED_CURSOR_Y = 16;
constexpr std::ptrdiff_t K1_MANAGER_VIEWPORT_WIDTH_OFFSET = 0x006C;
constexpr std::ptrdiff_t K1_MANAGER_VIEWPORT_HEIGHT_OFFSET = 0x006E;
constexpr std::uintptr_t K2_INVENTORY_PANEL_VTABLE = 0x00992994;
constexpr std::uintptr_t K2_JOURNAL_PANEL_VTABLE = 0x00992274;
constexpr std::uintptr_t K1_MOVIE_PLAYER_POINTER = 0x007A3CF4;
constexpr std::uintptr_t K1_CANCEL_MOVIE = 0x00404C40;
// CSWGuiNavigable's directional links, four control pointers at 0x5C + dir * 4
// (up, left, down, right). CSWGuiNavigable::HandleInputEvent walks these for GUI
// events 0x31/0x2F/0x32/0x30 and stops when a link is null.
// CSWGuiControl.extent (+0x04) is a CSWGuiExtent {left, top, width, height}.
constexpr std::ptrdiff_t K1_CONTROL_WIDTH_OFFSET = 0x0C;
constexpr std::ptrdiff_t K1_CONTROL_HEIGHT_OFFSET = 0x10;
// CSWGuiListBox: `controls` at 0x029C is a CExoArrayList {data, size, capacity},
// so the row count is its size field. selection_index is a 16-bit field.
constexpr std::ptrdiff_t K1_LISTBOX_ROW_COUNT_OFFSET = 0x02A0;
constexpr std::ptrdiff_t K1_LISTBOX_SELECTION_INDEX_OFFSET = 0x02C6;
constexpr std::ptrdiff_t K1_NAVIGABLE_UP_OFFSET = 0x5C;
constexpr std::ptrdiff_t K1_NAVIGABLE_DOWN_OFFSET = 0x64;
constexpr std::uint32_t WM_KEYDOWN_MESSAGE = 0x0100;
constexpr std::uint32_t VK_ESCAPE_KEY = 0x1B;
constexpr std::uint32_t VK_DELETE_KEY = 0x2E;
constexpr std::uint32_t VK_SPACE_KEY = 0x20;

struct BufferedInputRecord {
    std::uint32_t offset;
    std::uint32_t value;
};

struct GameConfig {
    std::ptrdiff_t panelManagerOffset;
    std::ptrdiff_t panelActiveControlOffset;
    std::ptrdiff_t panelFlagsOffset;
    std::ptrdiff_t targetActionMenuOffset;
    std::ptrdiff_t personalActionsOffset;
    std::ptrdiff_t actionGroupSize;
    std::array<std::ptrdiff_t, 4> actionControlOffsets;
    int personalActionCount;
    std::uintptr_t inGameMessagePanelVtable;
    std::uintptr_t inGameFadePanelVtable;
    std::uintptr_t inGamePausePanelVtable;
    std::uintptr_t keyboardDeviceIndex;
    std::uintptr_t getIsSelectable;
    std::uintptr_t setActiveControl;
    std::uintptr_t getControlAt;
    std::uintptr_t personalPrevious;
    std::uintptr_t personalNext;
    std::uintptr_t targetPrevious;
    std::uintptr_t targetNext;
    std::uintptr_t activate;
    std::uintptr_t cancelLastAction;
    std::uintptr_t handleGuiInputEvent;
};

constexpr std::ptrdiff_t MANAGER_PANEL_LIST_OFFSET = 0x0088;
constexpr std::ptrdiff_t MANAGER_PANEL_COUNT_OFFSET = 0x008C;
constexpr std::ptrdiff_t MANAGER_MODAL_LIST_OFFSET = 0x0094;
constexpr std::ptrdiff_t MANAGER_MODAL_COUNT_OFFSET = 0x0098;
constexpr std::ptrdiff_t TARGET_ACTIONS_OFFSET = 0x0054;
constexpr std::ptrdiff_t TARGET_ACTION_LIST_COUNT_OFFSET = 0x0004;
constexpr std::ptrdiff_t TARGET_ACTION_LIST_SIZE = 0x000C;
constexpr int TARGET_ACTION_COUNT = 3;

constexpr GameConfig K1_CONFIG = {
    0x18, 0x1C, 0x44, 0xBC, 0x772C, 0x71C,
    {0x000, 0x1C4, 0x388, 0x54C},
    4,
    0x0074FC60,
    0,
    0,
    0x0074D3C8,
    0x004189D0,
    0x0040A630,
    0x0040ABE0,
    0x0068AF70,
    0x0068AFE0,
    0x006884B0,
    0x00688520,
    0x0068B970,
    0x00688790,
    0x0040C8E0,
};

constexpr GameConfig K2_CONFIG = {
    0x1C, 0x20, 0x48, 0xCC, 0x733C, 0x750,
    {0x000, 0x1D0, 0x3A0, 0x570},
    6,
    0x0098E1EC,
    0x0099313C,
    0x00993334,
    0x00997514,
    0x00917340,
    0x0090D080,
    0x0051CB20,
    0x005233B0,
    0x00523460,
    0x00523510,
    0x005235C0,
    0x00522E30,
    0x00523AE0,
    0x0090EF20,
};

using ActionButtons = std::array<void*, MAX_ACTION_BUTTON_COUNT>;
using GetIsSelectableFn = bool(__thiscall*)(void*);
using SetActiveControlFn = void(__thiscall*)(void*, void*, int);
using K1GetControlAtFn = int(__thiscall*)(
    void*, int, int, void**, void**, int);
using K2GetControlAtFn = void*(__thiscall*)(void*, int, int);
using ActionCallbackFn = void(__thiscall*)(void*, void*);
using CancelLastActionFn = void(__thiscall*)(void*);
using CancelMovieFn = void(__thiscall*)(void*, int, int);
using HandleInputEventFn = void(__thiscall*)(void*, int, int);
using K1PazaakPlayCardFn = void(__thiscall*)(void*, void*);
using K1PazaakFlipCardFn = void(__thiscall*)(void*, void*);
using GuiManagerMoveMouseFn = void(__thiscall*)(void*, int, int);
using ClientMouseFn = void(__thiscall*)(void*, std::uint32_t);
using SetFillImageFn = void(__thiscall*)(void*, const void*, int);

std::uint32_t g_pendingInput = 0;
// std::uint8_t g_pendingMenuAction = 0;  // dead, never assigned
std::uint8_t g_pendingGenericButtonEvent = 0;
void* g_pendingSettingsTarget = nullptr;
int g_pendingSettingsEvent = 0;
std::uint8_t g_pendingSettingsNav = 0;
std::ptrdiff_t g_pendingK1PartyTargetOffset = -1;
// g_pendingInput has no bits left - PENDING_K1_SETTINGS_NAV is already 1u << 31 -
// and a scroll wants a count rather than a flag anyway, so a burst of notches
// arriving in one frame is not collapsed into a single line of movement.
// Negative scrolls up, positive scrolls down.
int g_pendingDescScroll = 0;
// Preserve normal Windows keyboard/mouse operation on startup. Controller users
// can still press F9 to park and hide the cursor when they want an unobstructed
// controller-only session.
bool g_cursorParked = false;
bool g_cursorFollowedControllerMode = false;
bool g_pendingCursorToggle = false;
void* g_mainInterface = nullptr;
void* g_k1PazaakReturnControl = nullptr;
bool g_k1SuppressPazaakFlipEnterRelease = false;
bool MouseIsBeingUsedK1(int mouseX, int mouseY);

void* g_k1PromptPanel = nullptr;
std::uintptr_t g_k1PromptPanelVtable = 0;
bool g_k1PromptMode = false;
bool g_k1PromptStateKnown = false;
// The caption variant last painted. Without this the early-out below would hold
// the first texture for as long as the screen stayed up, and cycling the filter
// would leave the badge placed for the caption before it.
int g_k1PromptVariant = -1;
// The control that held the focus when the badges were last painted, so a
// badge that follows the focus is repainted when the focus moves.
void* g_k1PromptFocus = nullptr;

// Which caption a button is showing, when it has more than one and the badge
// is placed differently for each. None means the single texture, placed against
// the widest wording, is the only one there is.
enum class PromptVariantK1 {
    None,
    InventoryFilter,
    // Painted only while this control holds the panel's focus, and cleared the
    // moment it does not. The main menu wants one A that travels with the
    // selection rather than five that sit there permanently.
    FocusOnly,
};

struct ControllerPromptBinding {
    std::ptrdiff_t controlOffset;
    const char* resref;
    PromptVariantK1 variant;
};

// The inventory filter button. Its caption is "Show " followed by the filter it
// will switch to, and the engine picks that from a six-entry STRREF table at
// 0x00756444 indexed by the byte at CGuiInGame+0xBC1 plus one, wrapping:
//
//     006B3A58  call 0x005ED690               CClientExoApp::GetGuiInGame
//     006B3A5D  movzx eax, byte [eax+0xBC1]   the current filter
//     006B3A64  inc eax                       the button offers the NEXT one
//     006B3A65  cmp eax, 6 / mov 0            six wraps to zero
//     006B3A88  mov edx, [ecx*4 + 0x756444]
//
// so these are in the table's order, and index i is the badge placed against
// the caption for table entry i:
//
//     0 All Items      1 New Items       2 Quest Items
//     3 Equippable     4 Utility Items   5 Useable Items
//
// Listed in full rather than built with a format string so the drift check can
// see that every one of them is actually generated.
constexpr int K1_INVENTORY_FILTER_COUNT = 6;
const char* const K1_INVENTORY_FILTER_RESREFS[K1_INVENTORY_FILTER_COUNT] = {
    "kmrpx_invnew0",
    "kmrpx_invnew1",
    "kmrpx_invnew2",
    "kmrpx_invnew3",
    "kmrpx_invnew4",
    "kmrpx_invnew5",
};

// CClientExoApp is [[0x007A39FC]+4], its internal [+4] again, and CGuiInGame
// hangs off that at +0x40 -- which is all CClientExoApp::GetGuiInGame
// (0x005ED690) does: `mov eax,[ecx+4]` then `mov eax,[eax+0x40]`.
constexpr std::uintptr_t K1_CLIENT_EXO_APP_ROOT_ADDRESS = 0x007A39FC;
constexpr std::ptrdiff_t K1_IN_GAME_GUI_OFFSET = 0x40;
constexpr std::ptrdiff_t K1_IN_GAME_INVENTORY_FILTER = 0xBC1;

// The caption the inventory filter button is showing, as an index into the
// table above, or -1 when it cannot be read. Three dereferences off the same
// CClientExoApp root this file already uses -- GetGuiInGame is only
// `mov eax,[ecx+4]` then `mov eax,[eax+0x40]`.
int K1InventoryFilterVariant()
{
    void** root = *reinterpret_cast<void***>(K1_CLIENT_EXO_APP_ROOT_ADDRESS);
    if (!root) {
        return -1;
    }
    void** app = static_cast<void**>(root[1]);
    if (!app) {
        return -1;
    }
    void* internal = app[1];
    if (!internal) {
        return -1;
    }
    // Read directly rather than through ReadPointer, which is defined
    // further down this file.
    void* inGame = *reinterpret_cast<void**>(
        static_cast<unsigned char*>(internal) + K1_IN_GAME_GUI_OFFSET);
    if (!inGame) {
        return -1;
    }
    const unsigned char current = *reinterpret_cast<unsigned char*>(
        static_cast<unsigned char*>(inGame) + K1_IN_GAME_INVENTORY_FILTER);
    if (current >= K1_INVENTORY_FILTER_COUNT) {
        return -1;                  // not a filter index; leave the fallback
    }
    return (current + 1) % K1_INVENTORY_FILTER_COUNT;
}

// The control this panel currently has focused, or null.
void* K1ActiveControl(void* panel)
{
    if (!panel) {
        return nullptr;
    }
    // Read directly rather than through ReadPointer, which is defined
    // further down this file.
    return *reinterpret_cast<void**>(
        static_cast<unsigned char*>(panel) + K1_CONFIG.panelActiveControlOffset);
}

// The badge for what the button is showing right now, or its single texture,
// or nothing at all when it is a FocusOnly badge and the focus is elsewhere.
const char* K1PromptResref(const ControllerPromptBinding& binding, void* panel,
                           void* control, int* outVariant)
{
    if (outVariant) {
        *outVariant = -1;
    }
    if (binding.variant == PromptVariantK1::FocusOnly) {
        // One badge that travels with the selection rather than five that sit
        // there at once. Clearing is as much the point as painting: without it
        // the badge would be left behind on the entry the focus just left.
        return control == K1ActiveControl(panel) ? binding.resref : nullptr;
    }
    if (binding.variant == PromptVariantK1::InventoryFilter) {
        const int index = K1InventoryFilterVariant();
        if (index >= 0) {
            if (outVariant) {
                *outVariant = index;
            }
            return K1_INVENTORY_FILTER_RESREFS[index];
        }
    }
    return binding.resref;
}

constexpr ControllerPromptBinding K1_CHARACTER_PROMPTS[] = {
    {K1_CHARACTER_EXIT_OFFSET, "kmrpb_charexit"},
    {K1_CHARACTER_SCRIPTS_OFFSET, "kmrpx_charscr"},
};
constexpr ControllerPromptBinding K1_CONTAINER_PROMPTS[] = {
    {K1_CONTAINER_GET_ITEMS_OFFSET, "kmrpa_contok"},
    {K1_CONTAINER_GIVE_ITEMS_OFFSET, "kmrpx_contgive"},
    {K1_CONTAINER_CANCEL_OFFSET, "kmrpb_contback"},
};
constexpr ControllerPromptBinding K1_SAVELOAD_PROMPTS[] = {
    {K1_SAVELOAD_DELETE_OFFSET, "kmrpx_savdel"},
    {K1_SAVELOAD_BACK_OFFSET, "kmrpb_savback"},
    {K1_SAVELOAD_LOAD_OFFSET, "kmrpa_savload"},
};
constexpr ControllerPromptBinding K1_UPGRADE_SELECTION_PROMPTS[] = {
    {K1_UPGRADE_SELECTION_UPGRADE_OFFSET, "kmrpa_upgitem"},
    {K1_UPGRADE_SELECTION_BACK_OFFSET, "kmrpb_upgback"},
};

// Back/cancel on every remaining navigable screen, added 2026-09-06. B is the
// only glyph asserted here rather than assumed: B's Delete scancode is rewritten
// to Escape for any menu panel (see the DIK_DELETE branch of
// CaptureActionBarInputK1), and none of these panels is one of the four
// transient overlays that suppress that rewrite. The offsets are the ones the
// settings-strip navigation already uses for these same buttons.

constexpr ControllerPromptBinding K1_INVENTORY_PROMPTS[] = {
    {K1_INVENTORY_CLOSE_OFFSET, "kmrpb_invclose"},
    {K1_INVENTORY_USEITEM_OFFSET, "kmrpa_invuse"},
    {K1_INVENTORY_SHOWNEW_OFFSET, "kmrpx_invnew", PromptVariantK1::InventoryFilter},
};

constexpr ControllerPromptBinding K1_MESSAGES_PROMPTS[] = {
    {K1_MESSAGES_CLOSE_OFFSET, "kmrpb_msgclose"},
    {K1_MESSAGES_FEEDBACK_OFFSET, "kmrpx_msgfeed"},
};

// The main menu. Offsets read out of the bind calls at 0x0067AD43-0x0067AF76;
// note BTN_EXIT at 0x1084 does not continue the 0x1C4 stride the first four sit
// on, because it is bound before them.
constexpr ControllerPromptBinding K1_MAIN_MENU_PROMPTS[] = {
    {0x03F0, "kmrpa_mmnew",  PromptVariantK1::FocusOnly},
    {0x05B4, "kmrpa_mmload", PromptVariantK1::FocusOnly},
    {0x0778, "kmrpa_mmmovi", PromptVariantK1::FocusOnly},
    {0x093C, "kmrpa_mmopt",  PromptVariantK1::FocusOnly},
    {0x1084, "kmrpa_mmexit", PromptVariantK1::FocusOnly},
};

// The equipment screen. Offsets from the bind calls at 0x006BB131 and
// 0x006BB166. B closes it -- CSWGuiInGameEquip's dispatcher implements 0x28 at
// 0x006BA41F -- and A equips whatever the slot grid has selected.
constexpr ControllerPromptBinding K1_EQUIP_PROMPTS[] = {
    {0x3698, "kmrpa_eqpequip", PromptVariantK1::None},
    {0x385C, "kmrpb_eqpback",  PromptVariantK1::None},
};

// The quest items screen, which has exactly one button. Offset from the bind
// call at 0x006D2836, whose control arrives in ebx from 0x006D2745.
constexpr ControllerPromptBinding K1_QUESTITEM_PROMPTS[] = {
    {0x08A8, "kmrpb_qitback", PromptVariantK1::None},
};

constexpr ControllerPromptBinding K1_JOURNAL_PROMPTS[] = {
    {K1_JOURNAL_QUESTITEMS_OFFSET, "kmrpx_jrnitems"},
    {K1_JOURNAL_COMPLETED_OFFSET, "kmrpa_jrndone"},
    {K1_JOURNAL_SORT_OFFSET, "kmrpy_jrnsort"},
    {K1_JOURNAL_CLOSE_OFFSET, "kmrpb_jrnclose"},
};

constexpr ControllerPromptBinding K1_MAP_PROMPTS[] = {
    {K1_MAP_RETURN_OFFSET, "kmrpx_mapebon"},
    {K1_MAP_PARTY_OFFSET, "kmrpa_mapparty"},
    {K1_MAP_CLOSE_OFFSET, "kmrpb_mapclose"},
};

constexpr ControllerPromptBinding K1_ABILITIES_PROMPTS[] = {
    {K1_ABILITIES_EXIT_OFFSET, "kmrpb_abilexit"},
};

constexpr ControllerPromptBinding K1_SOLO_MODE_QUERY_PROMPTS[] = {
    {K1_SOLO_QUERY_CANCEL_OFFSET, "kmrpb_confirm"},
};

constexpr ControllerPromptBinding K1_OPTIONS_MAIN_PROMPTS[] = {
    {K1_OPTIONS_MAIN_BACK_OFFSET, "kmrpb_optmain"},
};

constexpr ControllerPromptBinding K1_INGAME_OPTIONS_PROMPTS[] = {
    {K1_INGAME_OPTIONS_EXIT_OFFSET, "kmrpb_optingame"},
};

constexpr ControllerPromptBinding K1_INGAME_GAMEPLAY_PROMPTS[] = {
    {K1_INGAME_GAMEPLAY_BACK_OFFSET, "kmrpb_optgame"},
};

constexpr ControllerPromptBinding K1_INGAME_AUTOPAUSE_PROMPTS[] = {
    {K1_INGAME_AUTOPAUSE_BACK_OFFSET, "kmrpb_optpause"},
};

constexpr ControllerPromptBinding K1_OPTIONS_FEEDBACK_PROMPTS[] = {
    {K1_OPTIONS_FEEDBACK_BACK_OFFSET, "kmrpb_optfeed"},
};

constexpr ControllerPromptBinding K1_OPTIONS_MOUSE_PROMPTS[] = {
    {K1_OPTIONS_MOUSE_BACK_OFFSET, "kmrpb_optmouse"},
};

constexpr ControllerPromptBinding K1_OPTIONS_GRAPHICS_PROMPTS[] = {
    {K1_OPTIONS_GRAPHICS_BACK_OFFSET, "kmrpb_optgfx"},
};

constexpr ControllerPromptBinding K1_OPTIONS_GRAPHICS_ADVANCED_PROMPTS[] = {
    {K1_OPTIONS_GRAPHICS_ADVANCED_CANCEL_OFFSET, "kmrpb_optgfxadv"},
    {K1_OPTIONS_GRAPHICS_ADVANCED_OK_OFFSET, "kmrpa_optgfxadv"},
};

constexpr ControllerPromptBinding K1_OPTIONS_SOUND_PROMPTS[] = {
    {K1_OPTIONS_SOUND_BACK_OFFSET, "kmrpb_optsnd"},
};

constexpr ControllerPromptBinding K1_OPTIONS_SOUND_ADVANCED_PROMPTS[] = {
    {K1_OPTIONS_SOUND_ADVANCED_CANCEL_OFFSET, "kmrpb_optsndadv"},
    {K1_OPTIONS_SOUND_ADVANCED_OK_OFFSET, "kmrpa_optsndadv"},
};

constexpr ControllerPromptBinding K1_KEY_MAPPINGS_PROMPTS[] = {
    {K1_KEY_MAPPINGS_CANCEL_OFFSET, "kmrpb_optkeys"},
    {K1_KEY_MAPPINGS_ACCEPT_OFFSET, "kmrpa_optkeys"},
};

constexpr ControllerPromptBinding K1_UPGRADE_PROMPTS[] = {
    {K1_UPGRADE_BACK_OFFSET, "kmrpb_upgasm"},
    {K1_UPGRADE_ASSEMBLE_OFFSET, "kmrpa_upgasm"},
};

constexpr ControllerPromptBinding K1_UPGRADE_ITEM_SELECT_PROMPTS[] = {
    {K1_UPGRADE_ITEM_SELECT_BACK_OFFSET, "kmrpb_upgitm"},
    {K1_UPGRADE_ITEM_SELECT_UPGRADE_OFFSET, "kmrpa_upgitm"},
};

void* OffsetPointer(void* base, std::ptrdiff_t offset)
{
    return reinterpret_cast<void*>(reinterpret_cast<std::uintptr_t>(base) + offset);
}

void* ReadPointer(void* base, std::ptrdiff_t offset)
{
    return *reinterpret_cast<void**>(OffsetPointer(base, offset));
}

int ReadInt(void* base, std::ptrdiff_t offset)
{
    return *reinterpret_cast<int*>(OffsetPointer(base, offset));
}

int ReadShort(void* base, std::ptrdiff_t offset)
{
    return *reinterpret_cast<short*>(OffsetPointer(base, offset));
}

int ActionButtonCount(const GameConfig& config)
{
    return TARGET_ACTION_COUNT + config.personalActionCount;
}

bool IsIgnoredByInput(const GameConfig& config, void* panel)
{
    return (ReadInt(panel, config.panelFlagsOffset) & PANEL_IGNORED_BY_INPUT) != 0;
}

bool IsGameplayHudActive(
    const GameConfig& config,
    void* manager,
    void* mainInterface)
{
    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(config, modalPanels[i])) {
            return false;
        }
    }

    void** panels = static_cast<void**>(
        ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
    int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
    for (int i = panelCount - 1; i >= 0; --i) {
        void* panel = panels[i];
        if (IsIgnoredByInput(config, panel)) {
            continue;
        }
        if (panel == mainInterface) {
            return true;
        }
        std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
        if (vtable != config.inGameMessagePanelVtable &&
            vtable != config.inGameFadePanelVtable &&
            vtable != config.inGamePausePanelVtable) {
            return false;
        }
    }
    return false;
}

bool IsK2FilterPanel(void* panel)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    return vtable == K2_INVENTORY_PANEL_VTABLE ||
        vtable == K2_JOURNAL_PANEL_VTABLE ||
        vtable == K2_CONFIG.inGameMessagePanelVtable;
}

void* FindK2FilterPanel(void* manager)
{
    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K2_CONFIG, modalPanels[i]) &&
            IsK2FilterPanel(modalPanels[i])) {
            return modalPanels[i];
        }
    }

    void** panels = static_cast<void**>(
        ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
    int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
    for (int i = panelCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K2_CONFIG, panels[i]) &&
            IsK2FilterPanel(panels[i])) {
            return panels[i];
        }
    }
    return nullptr;
}

bool IsK1MenuPanel(void* panel)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    return vtable == K1_ABILITIES_PANEL_VTABLE ||
        vtable == K1_CHARACTER_PANEL_VTABLE ||
        vtable == K1_INVENTORY_PANEL_VTABLE ||
        vtable == K1_JOURNAL_PANEL_VTABLE ||
        vtable == K1_MAP_PANEL_VTABLE ||
        vtable == K1_MESSAGES_PANEL_VTABLE ||
        vtable == K1_LEVEL_UP_PANEL_VTABLE ||
        vtable == K1_POWERS_PANEL_VTABLE ||
        vtable == K1_FEATS_PANEL_VTABLE ||
        vtable == K1_SKILLS_PANEL_VTABLE ||
        vtable == K1_NAME_PANEL_VTABLE ||
        vtable == K1_ABILITIES_CHARGEN_PANEL_VTABLE ||
        vtable == K1_SOLO_MODE_QUERY_PANEL_VTABLE ||
        vtable == K1_PAZAAK_SETUP_PANEL_VTABLE ||
        vtable == K1_PAZAAK_GAME_PANEL_VTABLE ||
        vtable == K1_PARTY_SELECT_PANEL_VTABLE ||
        vtable == K1_CLASS_SELECT_PANEL_VTABLE ||
        vtable == K1_CONTAINER_PANEL_VTABLE ||
        vtable == K1_SAVELOAD_PANEL_VTABLE ||
        vtable == K1_UPGRADE_SELECTION_PANEL_VTABLE ||
        vtable == K1_INGAME_GAMEPLAY_PANEL_VTABLE ||
        vtable == K1_INGAME_AUTOPAUSE_PANEL_VTABLE ||
        vtable == K1_UPGRADE_ITEM_SELECT_PANEL_VTABLE ||
        vtable == K1_UPGRADE_PANEL_VTABLE ||
        vtable == K1_STORE_PANEL_VTABLE ||
        vtable == K1_INGAME_OPTIONS_PANEL_VTABLE ||
        vtable == K1_KEY_MAPPINGS_PANEL_VTABLE ||
        vtable == K1_OPTIONS_MAIN_PANEL_VTABLE ||
        vtable == K1_OPTIONS_FEEDBACK_PANEL_VTABLE ||
        vtable == K1_OPTIONS_GRAPHICS_PANEL_VTABLE ||
        vtable == K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE ||
        vtable == K1_OPTIONS_MOUSE_PANEL_VTABLE ||
        vtable == K1_OPTIONS_RESOLUTION_PANEL_VTABLE ||
        vtable == K1_OPTIONS_SOUND_PANEL_VTABLE ||
        vtable == K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE;
}

bool IsK1TitleMenuPanel(void* panel)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    return vtable == K1_MAIN_MENU_PANEL_VTABLE ||
        vtable == K1_SAVELOAD_PANEL_VTABLE ||
        IsK1MenuPanel(panel);
}

bool IsK1DeleteEscapeSuppressedPanel(void* panel)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    return vtable == K1_FLOATY_TEXT_PANEL_VTABLE ||
        vtable == K1_BARK_BUBBLE_PANEL_VTABLE ||
        vtable == K1_MESSAGE_BOX_PANEL_VTABLE ||
        vtable == K1_CONTROLLER_LOSS_BOX_PANEL_VTABLE;
}

bool HasK1DeleteEscapeSuppressedPanel(void* manager)
{
    if (!manager) {
        return false;
    }

    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K1_CONFIG, modalPanels[i]) &&
            IsK1DeleteEscapeSuppressedPanel(modalPanels[i])) {
            return true;
        }
    }

    void** panels = static_cast<void**>(
        ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
    int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
    for (int i = panelCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K1_CONFIG, panels[i]) &&
            IsK1DeleteEscapeSuppressedPanel(panels[i])) {
            return true;
        }
    }
    return false;
}

void* GetK1TitleGuiManager()
{
    return *reinterpret_cast<void**>(K1_GUI_MANAGER_GLOBAL);
}

void* FindK1MenuPanel(void* manager)
{
    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (IsIgnoredByInput(K1_CONFIG, modalPanels[i])) {
            continue;
        }
        return IsK1MenuPanel(modalPanels[i])
            ? modalPanels[i]
            : nullptr;
    }

    void** panels = static_cast<void**>(
        ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
    int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
    for (int i = panelCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K1_CONFIG, panels[i]) &&
            IsK1MenuPanel(panels[i])) {
            return panels[i];
        }
    }
    return nullptr;
}

void* FindK1TitleMenuPanel(void* manager)
{
    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K1_CONFIG, modalPanels[i]) &&
            IsK1TitleMenuPanel(modalPanels[i])) {
            return modalPanels[i];
        }
    }

    void** panels = static_cast<void**>(
        ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
    int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
    for (int i = panelCount - 1; i >= 0; --i) {
        if (!IsIgnoredByInput(K1_CONFIG, panels[i]) &&
            IsK1TitleMenuPanel(panels[i])) {
            return panels[i];
        }
    }
    return nullptr;
}

void* FindK1MenuPanelForInput(void** managerOut)
{
    void* mainInterface = g_mainInterface;
    void* manager = mainInterface
        ? ReadPointer(mainInterface, K1_CONFIG.panelManagerOffset)
        : nullptr;
    void* panel = manager ? FindK1MenuPanel(manager) : nullptr;
    if (panel) {
        *managerOut = manager;
        return panel;
    }

    manager = GetK1TitleGuiManager();
    panel = manager ? FindK1TitleMenuPanel(manager) : nullptr;
    if (panel) {
        *managerOut = manager;
    }
    return panel;
}

const ControllerPromptBinding* GetK1ControllerPrompts(
    void* panel,
    int* count)
{
    *count = 0;
    if (!panel) {
        return nullptr;
    }
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_CHARACTER_PANEL_VTABLE:
        *count = sizeof(K1_CHARACTER_PROMPTS) / sizeof(K1_CHARACTER_PROMPTS[0]);
        return K1_CHARACTER_PROMPTS;
    case K1_CONTAINER_PANEL_VTABLE:
        *count = sizeof(K1_CONTAINER_PROMPTS) / sizeof(K1_CONTAINER_PROMPTS[0]);
        return K1_CONTAINER_PROMPTS;
    case K1_SAVELOAD_PANEL_VTABLE:
        *count = sizeof(K1_SAVELOAD_PROMPTS) / sizeof(K1_SAVELOAD_PROMPTS[0]);
        return K1_SAVELOAD_PROMPTS;
    case K1_UPGRADE_SELECTION_PANEL_VTABLE:
        *count = sizeof(K1_UPGRADE_SELECTION_PROMPTS) /
            sizeof(K1_UPGRADE_SELECTION_PROMPTS[0]);
        return K1_UPGRADE_SELECTION_PROMPTS;
    case K1_OPTIONS_MAIN_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_MAIN_PROMPTS) / sizeof(K1_OPTIONS_MAIN_PROMPTS[0]);
        return K1_OPTIONS_MAIN_PROMPTS;
    case K1_SOLO_MODE_QUERY_PANEL_VTABLE:
        *count = sizeof(K1_SOLO_MODE_QUERY_PROMPTS) /
            sizeof(K1_SOLO_MODE_QUERY_PROMPTS[0]);
        return K1_SOLO_MODE_QUERY_PROMPTS;
    case K1_INVENTORY_PANEL_VTABLE:
        *count = sizeof(K1_INVENTORY_PROMPTS) / sizeof(K1_INVENTORY_PROMPTS[0]);
        return K1_INVENTORY_PROMPTS;
    case K1_MESSAGES_PANEL_VTABLE:
        *count = sizeof(K1_MESSAGES_PROMPTS) / sizeof(K1_MESSAGES_PROMPTS[0]);
        return K1_MESSAGES_PROMPTS;
    case K1_JOURNAL_PANEL_VTABLE:
        *count = sizeof(K1_JOURNAL_PROMPTS) / sizeof(K1_JOURNAL_PROMPTS[0]);
        return K1_JOURNAL_PROMPTS;
    case K1_MAIN_MENU_PANEL_VTABLE:
        *count = sizeof(K1_MAIN_MENU_PROMPTS) / sizeof(K1_MAIN_MENU_PROMPTS[0]);
        return K1_MAIN_MENU_PROMPTS;
    case K1_EQUIP_PANEL_VTABLE:
        *count = sizeof(K1_EQUIP_PROMPTS) / sizeof(K1_EQUIP_PROMPTS[0]);
        return K1_EQUIP_PROMPTS;
    case K1_QUESTITEM_PANEL_VTABLE:
        *count = sizeof(K1_QUESTITEM_PROMPTS) / sizeof(K1_QUESTITEM_PROMPTS[0]);
        return K1_QUESTITEM_PROMPTS;
    case K1_MAP_PANEL_VTABLE:
        *count = sizeof(K1_MAP_PROMPTS) / sizeof(K1_MAP_PROMPTS[0]);
        return K1_MAP_PROMPTS;
    case K1_ABILITIES_PANEL_VTABLE:
        *count = sizeof(K1_ABILITIES_PROMPTS) / sizeof(K1_ABILITIES_PROMPTS[0]);
        return K1_ABILITIES_PROMPTS;
    case K1_INGAME_OPTIONS_PANEL_VTABLE:
        *count = sizeof(K1_INGAME_OPTIONS_PROMPTS) / sizeof(K1_INGAME_OPTIONS_PROMPTS[0]);
        return K1_INGAME_OPTIONS_PROMPTS;
    case K1_INGAME_GAMEPLAY_PANEL_VTABLE:
        *count = sizeof(K1_INGAME_GAMEPLAY_PROMPTS) / sizeof(K1_INGAME_GAMEPLAY_PROMPTS[0]);
        return K1_INGAME_GAMEPLAY_PROMPTS;
    case K1_INGAME_AUTOPAUSE_PANEL_VTABLE:
        *count = sizeof(K1_INGAME_AUTOPAUSE_PROMPTS) / sizeof(K1_INGAME_AUTOPAUSE_PROMPTS[0]);
        return K1_INGAME_AUTOPAUSE_PROMPTS;
    case K1_OPTIONS_FEEDBACK_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_FEEDBACK_PROMPTS) / sizeof(K1_OPTIONS_FEEDBACK_PROMPTS[0]);
        return K1_OPTIONS_FEEDBACK_PROMPTS;
    case K1_OPTIONS_MOUSE_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_MOUSE_PROMPTS) / sizeof(K1_OPTIONS_MOUSE_PROMPTS[0]);
        return K1_OPTIONS_MOUSE_PROMPTS;
    case K1_OPTIONS_GRAPHICS_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_GRAPHICS_PROMPTS) / sizeof(K1_OPTIONS_GRAPHICS_PROMPTS[0]);
        return K1_OPTIONS_GRAPHICS_PROMPTS;
    case K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_GRAPHICS_ADVANCED_PROMPTS) / sizeof(K1_OPTIONS_GRAPHICS_ADVANCED_PROMPTS[0]);
        return K1_OPTIONS_GRAPHICS_ADVANCED_PROMPTS;
    case K1_OPTIONS_SOUND_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_SOUND_PROMPTS) / sizeof(K1_OPTIONS_SOUND_PROMPTS[0]);
        return K1_OPTIONS_SOUND_PROMPTS;
    case K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE:
        *count = sizeof(K1_OPTIONS_SOUND_ADVANCED_PROMPTS) / sizeof(K1_OPTIONS_SOUND_ADVANCED_PROMPTS[0]);
        return K1_OPTIONS_SOUND_ADVANCED_PROMPTS;
    case K1_KEY_MAPPINGS_PANEL_VTABLE:
        *count = sizeof(K1_KEY_MAPPINGS_PROMPTS) / sizeof(K1_KEY_MAPPINGS_PROMPTS[0]);
        return K1_KEY_MAPPINGS_PROMPTS;
    case K1_UPGRADE_PANEL_VTABLE:
        *count = sizeof(K1_UPGRADE_PROMPTS) / sizeof(K1_UPGRADE_PROMPTS[0]);
        return K1_UPGRADE_PROMPTS;
    case K1_UPGRADE_ITEM_SELECT_PANEL_VTABLE:
        *count = sizeof(K1_UPGRADE_ITEM_SELECT_PROMPTS) / sizeof(K1_UPGRADE_ITEM_SELECT_PROMPTS[0]);
        return K1_UPGRADE_ITEM_SELECT_PROMPTS;
    default:
        return nullptr;
    }
}

void SetK1ControllerPromptFill(void* control, const char* value)
{
    if (!control) {
        return;
    }
    char resref[16] = {};
    if (value) {
        for (int i = 0; i < 16 && value[i] != '\0'; ++i) {
            resref[i] = value[i];
        }
    }
    SetFillImageFn setFill = reinterpret_cast<SetFillImageFn>(
        K1_GUI_BORDER_SET_FILL_IMAGE);
    setFill(
        OffsetPointer(control, K1_BUTTON_BORDER_PARAMS_OFFSET), resref, 1);
    setFill(
        OffsetPointer(control, K1_BUTTON_HILIGHT_PARAMS_OFFSET), resref, 1);
}

void UpdateK1ControllerPrompts()
{
    void* manager = nullptr;
    void* panel = FindK1MenuPanelForInput(&manager);

    // The in-game tab strip is always the panel in front while the menu is open,
    // and it carries no badges of its own -- so every tab screen came up with no
    // controller art at all, however complete its table was. Inventory, Journal,
    // Messages, Map and Abilities all sit BEHIND it. When the strip is what was
    // found, use the screen behind it instead.
    if (panel && manager &&
        *reinterpret_cast<std::uintptr_t*>(panel) == K1_INGAME_MENU_PANEL_VTABLE) {
        void** panels = static_cast<void**>(
            ReadPointer(manager, MANAGER_PANEL_LIST_OFFSET));
        const int panelCount = ReadInt(manager, MANAGER_PANEL_COUNT_OFFSET);
        for (int i = panelCount - 1; i >= 0; --i) {
            void* candidate = panels ? panels[i] : nullptr;
            if (!candidate || candidate == panel) {
                continue;
            }
            int probe = 0;
            if (GetK1ControllerPrompts(candidate, &probe) && probe > 0) {
                panel = candidate;
                break;
            }
        }
    }
    // Show prompts while the pad is what the player is actually using, and drop
    // them the moment they touch mouse or keyboard. This was previously tied to
    // mere connection because the mouse hook could not tell KOTOR's own cursor
    // recentring from real movement; MouseIsBeingUsedK1 now makes that
    // distinction, so the honest question can be asked.
    const bool controllerMode = IsControllerInputActiveK1();
    const std::uintptr_t vtable = panel
        ? *reinterpret_cast<std::uintptr_t*>(panel)
        : 0;

    // The caption can change without the panel or the mode changing, so it is
    // part of what "nothing has changed" means. So is the focus, now that a
    // badge can follow it: without this the early-out would hold the first
    // frame's badge for as long as the screen stayed up, and the A would sit on
    // whichever entry happened to be selected when the menu opened.
    const int variant = controllerMode ? K1InventoryFilterVariant() : -1;
    void* const focused = controllerMode ? K1ActiveControl(panel) : nullptr;

    if (g_k1PromptStateKnown && panel == g_k1PromptPanel &&
        vtable == g_k1PromptPanelVtable && controllerMode == g_k1PromptMode &&
        variant == g_k1PromptVariant && focused == g_k1PromptFocus) {
        return;
    }

    // A newly constructed PC panel already has empty normal fills. Only write
    // the empty value when we are actively removing prompts from the same live
    // panel; this avoids needless texture churn while using keyboard/mouse.
    const bool mustApply = controllerMode ||
        (g_k1PromptStateKnown && g_k1PromptMode && panel == g_k1PromptPanel &&
         vtable == g_k1PromptPanelVtable);

    if (mustApply && panel) {
        int count = 0;
        const ControllerPromptBinding* prompts =
            GetK1ControllerPrompts(panel, &count);
        for (int i = 0; i < count; ++i) {
            void* control = OffsetPointer(panel, prompts[i].controlOffset);
            SetK1ControllerPromptFill(
                control,
                controllerMode
                    ? K1PromptResref(prompts[i], panel, control, nullptr)
                    : nullptr);
        }
    }

    g_k1PromptPanel = panel;
    g_k1PromptPanelVtable = vtable;
    g_k1PromptMode = controllerMode;
    g_k1PromptVariant = variant;
    g_k1PromptFocus = focused;
    g_k1PromptStateKnown = true;
}

bool IsK1SelectableControl(void* control)
{
    return control &&
        (ReadInt(control, K1_CONFIG.panelFlagsOffset) & CONTROL_VISIBLE) != 0 &&
        reinterpret_cast<GetIsSelectableFn>(
            K1_CONFIG.getIsSelectable)(control);
}

// Click-only controls: real, visible, mouse-clickable column entries that the
// engine still refuses keyboard focus for, so vanilla's arrow walk steps over
// them. Graphics' Screen Resolution is one - optgraphics.gui gives it healthy
// MOVETO links (UP=SLI_GAMMA, DOWN=CB_SHADOWS, and both neighbours point back at
// it) and a 240x22 extent, yet GetIsSelectable says no, so the column skips from
// Brightness straight to Shadows. Listing the offset here lets the settings walk
// focus it anyway; Enter then activates it into the resolution sub-panel.
bool IsK1ForcedNavTarget(void* panel, void* control)
{
    if (!panel || !control) {
        return false;
    }
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_OPTIONS_GRAPHICS_PANEL_VTABLE:
        return control ==
            OffsetPointer(panel, K1_OPTIONS_GRAPHICS_TAIL_RESOLUTION_OFFSET);
    default:
        return false;
    }
}

// A control can pass visible-and-selectable yet occupy no space on screen: Options
// Main carries a quit_button that is not part of that screen, and focusing it puts
// the highlight nowhere while the description pane reads "Bad StrRef". Only the
// settings paths use this; Pazaak and the rest keep the plain test.
// A forced entry skips the selectable test but still has to be visible and sized,
// so the quit_button case stays rejected on its zero extent.
bool IsK1SettingsNavTarget(void* panel, void* control)
{
    if (!control) {
        return false;
    }
    bool usable = IsK1ForcedNavTarget(panel, control)
        ? (ReadInt(control, K1_CONFIG.panelFlagsOffset) & CONTROL_VISIBLE) != 0
        : IsK1SelectableControl(control);
    return usable &&
        ReadInt(control, K1_CONTROL_WIDTH_OFFSET) > 0 &&
        ReadInt(control, K1_CONTROL_HEIGHT_OFFSET) > 0;
}

bool HasK1BlockingModal(void* manager, void* panel)
{
    void** modalPanels = static_cast<void**>(
        ReadPointer(manager, MANAGER_MODAL_LIST_OFFSET));
    int modalCount = ReadInt(manager, MANAGER_MODAL_COUNT_OFFSET);
    for (int i = modalCount - 1; i >= 0; --i) {
        if (IsIgnoredByInput(K1_CONFIG, modalPanels[i])) {
            continue;
        }
        return modalPanels[i] != panel;
    }
    return false;
}

// Vanilla navigation walks an options panel's option column fine, but the .gui
// link graph never joins that column to the bottom button strip, so the strip is
// mouse-only. These describe the seam: the column's last control, and the strip
// laid out left-to-right.
struct SettingsStripExit {
    // Holds a whole column where one is known, not just its last few controls:
    // anything left outside falls back to vanilla's links, which is where the
    // skipping comes from. Entries past columnTailCount are never read.
    std::array<std::ptrdiff_t, 8> columnTail;
    int columnTailCount;
    std::array<std::ptrdiff_t, 3> strip;
    int stripCount;
    // Set only where the column is listbox rows allocated at runtime, so no fixed
    // offset can name them and we have to fall back to the null-link test.
    bool dynamicColumn;
    // Width of the tail's bottom row. The Upgrade Bench's categories are a 2x2
    // grid, so both bottom cells exit down into the strip and Up from each must
    // reach the cell directly above it. 0 and 1 both mean a plain column.
    int bottomRowWidth;
    // A row of tabs sitting above the column, like Key Mapping's Movement / Game
    // / Mini Games. Reached by pressing Up at the top of the column; movement
    // between the tabs themselves and back down is left to vanilla.
    std::array<std::ptrdiff_t, 3> header;
    int headerCount;
    // Optional panel member holding the index of the active tab, so Up lands on
    // the tab that is actually selected rather than always the first. -1 to skip.
    std::ptrdiff_t headerIndexOffset;
};

struct SettingsCycleGroup {
    std::ptrdiff_t valueOffset;
    std::ptrdiff_t leftOffset;
    std::ptrdiff_t rightOffset;
};

constexpr SettingsStripExit NO_SETTINGS_STRIP_EXIT =
    {{-1, -1, -1, -1, -1, -1, -1, -1}, 0, {-1, -1, -1}, 0,
     false, 0, {-1, -1, -1}, 0, -1};
constexpr SettingsCycleGroup NO_SETTINGS_CYCLE_GROUP = {-1, -1, -1};

// All 32 bits of g_pendingInput are taken, so PENDING_K1_SETTINGS_NAV carries a
// mode alongside it rather than getting a bit per intent.
constexpr std::uint8_t SETTINGS_NAV_CYCLE = 1;
constexpr std::uint8_t SETTINGS_NAV_ENTER_STRIP = 2;
constexpr std::uint8_t SETTINGS_NAV_RETURN_COLUMN = 3;
constexpr std::uint8_t SETTINGS_NAV_STRIP_PREV = 4;
constexpr std::uint8_t SETTINGS_NAV_STRIP_NEXT = 5;
constexpr std::uint8_t SETTINGS_NAV_COLUMN_UP = 6;
constexpr std::uint8_t SETTINGS_NAV_COLUMN_DOWN = 7;
constexpr std::uint8_t SETTINGS_NAV_HEADER = 8;
constexpr std::uint8_t SETTINGS_NAV_HEADER_PREV = 9;
constexpr std::uint8_t SETTINGS_NAV_HEADER_NEXT = 10;

std::array<SettingsCycleGroup, 3> GetK1SettingsCycleGroups(void* panel)
{
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_INGAME_GAMEPLAY_PANEL_VTABLE:
        return {{{0x0CD4, 0x105C, 0x0E98},
                 NO_SETTINGS_CYCLE_GROUP,
                 NO_SETTINGS_CYCLE_GROUP}};
    case K1_OPTIONS_GRAPHICS_PANEL_VTABLE:
        return {{{0x08BC, 0x0A80, 0x0C44},
                 NO_SETTINGS_CYCLE_GROUP,
                 NO_SETTINGS_CYCLE_GROUP}};
    case K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE:
        return {{{0x0DE0, 0x0FA4, 0x1168},
                 {0x132C, 0x14F0, 0x16B4},
                 {0x1878, 0x1A3C, 0x1C00}}};
    case K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE:
        return {{{0x031C, 0x06A4, 0x04E0},
                 NO_SETTINGS_CYCLE_GROUP,
                 NO_SETTINGS_CYCLE_GROUP}};
    default:
        return {NO_SETTINGS_CYCLE_GROUP,
                NO_SETTINGS_CYCLE_GROUP,
                NO_SETTINGS_CYCLE_GROUP};
    }
}

bool CaptureK1SettingsCycle(void* panel, std::uint32_t keyOffset)
{
    if (keyOffset != DIK_LEFT && keyOffset != DIK_RIGHT) {
        return false;
    }

    void* activeControl = ReadPointer(
        panel,
        K1_CONFIG.panelActiveControlOffset);
    std::array<SettingsCycleGroup, 3> groups =
        GetK1SettingsCycleGroups(panel);
    for (const SettingsCycleGroup& group : groups) {
        if (group.valueOffset < 0) {
            continue;
        }

        void* valueControl = OffsetPointer(panel, group.valueOffset);
        void* leftControl = OffsetPointer(panel, group.leftOffset);
        void* rightControl = OffsetPointer(panel, group.rightOffset);
        if (activeControl != valueControl &&
            activeControl != leftControl &&
            activeControl != rightControl) {
            continue;
        }

        g_pendingSettingsTarget = keyOffset == DIK_LEFT
            ? leftControl
            : rightControl;
        g_pendingSettingsEvent = K1_GUI_A_BUTTON_EVENT;
        g_pendingSettingsNav = SETTINGS_NAV_CYCLE;
        g_pendingInput |= PENDING_K1_SETTINGS_NAV;
        return true;
    }
    return false;
}

// Each supported panel contributes its verified column tail and bottom strip.
SettingsStripExit GetK1SettingsStripExit(void* panel)
{
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_SOLO_MODE_QUERY_PANEL_VTABLE:
        return {{K1_SOLO_QUERY_OK_OFFSET}, 1,
                {K1_SOLO_QUERY_CANCEL_OFFSET, -1, -1}, 1, false, 0};
    case K1_ABILITIES_PANEL_VTABLE:
        // dynamicColumn: the column is listbox rows allocated at runtime, so no
        // fixed offset names them. Header is left-to-right as drawn.
        return {{K1_ABILITIES_LISTBOX_OFFSET}, 1,
                {K1_ABILITIES_EXIT_OFFSET, -1, -1}, 1, true, 0,
                {K1_ABILITIES_TAB_SKILLS_OFFSET,
                 K1_ABILITIES_TAB_POWERS_OFFSET,
                 K1_ABILITIES_TAB_FEATS_OFFSET}, 3,
                -1};
    case K1_KEY_MAPPINGS_PANEL_VTABLE:
        return {{K1_KEY_MAPPINGS_TAIL_LIST_OFFSET}, 1,
                {K1_KEY_MAPPINGS_DEFAULT_OFFSET,
                 K1_KEY_MAPPINGS_CANCEL_OFFSET,
                 K1_KEY_MAPPINGS_ACCEPT_OFFSET}, 3, true, 0,
                {K1_KEY_MAPPINGS_TAB_MOVEMENT_OFFSET,
                 K1_KEY_MAPPINGS_TAB_GAME_OFFSET,
                 K1_KEY_MAPPINGS_TAB_MINIGAME_OFFSET}, 3,
                K1_KEY_MAPPINGS_FILTER_CATEGORY_OFFSET};
    case K1_UPGRADE_SELECTION_PANEL_VTABLE:
        return {{K1_UPGRADE_SELECTION_TAIL_MELEE_OFFSET,
                 K1_UPGRADE_SELECTION_TAIL_ARMOR_OFFSET,
                 K1_UPGRADE_SELECTION_TAIL_LIGHTSABER_OFFSET,
                 K1_UPGRADE_SELECTION_TAIL_RANGED_OFFSET}, 4,
                {K1_UPGRADE_SELECTION_UPGRADE_OFFSET,
                 K1_UPGRADE_SELECTION_BACK_OFFSET, -1}, 2, false, 2};
    case K1_UPGRADE_PANEL_VTABLE:
        return {{K1_UPGRADE_SLOT4_1_OFFSET,
                 K1_UPGRADE_SLOT4_2_OFFSET,
                 K1_UPGRADE_SLOT4_3_OFFSET,
                 K1_UPGRADE_SLOT4_4_OFFSET,
                 K1_UPGRADE_SLOT3_1_OFFSET,
                 K1_UPGRADE_SLOT3_2_OFFSET,
                 K1_UPGRADE_SLOT3_3_OFFSET}, K1_UPGRADE_SLOT_COUNT,
                {K1_UPGRADE_ASSEMBLE_OFFSET,
                 K1_UPGRADE_BACK_OFFSET, -1}, 2,
                false, K1_UPGRADE_SLOT_COUNT};
    case K1_UPGRADE_ITEM_SELECT_PANEL_VTABLE:
        return {{K1_UPGRADE_ITEM_SELECT_TAIL_LISTBOX_OFFSET, -1, -1, -1}, 1,
                {K1_UPGRADE_ITEM_SELECT_UPGRADE_OFFSET,
                 K1_UPGRADE_ITEM_SELECT_BACK_OFFSET, -1}, 2, true};
    case K1_INGAME_OPTIONS_PANEL_VTABLE:
        // Whole column, bottom-up. Quit is absent on some screens, which the
        // selectable-first tail resolution already handles.
        return {{K1_INGAME_OPTIONS_TAIL_QUIT_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_SOUND_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_GRAPHICS_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_AUTOPAUSE_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_FEEDBACK_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_GAMEPLAY_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_SAVEGAME_OFFSET,
                 K1_INGAME_OPTIONS_TAIL_LOADGAME_OFFSET}, 8,
                {K1_INGAME_OPTIONS_EXIT_OFFSET, -1, -1}, 1};
    case K1_INGAME_GAMEPLAY_PANEL_VTABLE:
        return {{K1_INGAME_GAMEPLAY_TAIL_KEYMAP_OFFSET,
                 K1_INGAME_GAMEPLAY_TAIL_MOUSE_OFFSET, -1, -1}, 2,
                {K1_INGAME_GAMEPLAY_DEFAULT_OFFSET,
                 K1_INGAME_GAMEPLAY_BACK_OFFSET, -1}, 2};
    case K1_INGAME_AUTOPAUSE_PANEL_VTABLE:
        // Whole column, bottom-up: New Target Selected, Action Menu Used, Party
        // Member Down, Mine Sighted, Enemy Sighted, End of Combat Round.
        return {{K1_INGAME_AUTOPAUSE_TAIL_TRIGGERS_OFFSET,
                 K1_INGAME_AUTOPAUSE_TAIL_ACTION_MENU_OFFSET,
                 K1_INGAME_AUTOPAUSE_TAIL_PARTY_KILLED_OFFSET,
                 K1_INGAME_AUTOPAUSE_TAIL_MINE_OFFSET,
                 K1_INGAME_AUTOPAUSE_TAIL_ENEMY_OFFSET,
                 K1_INGAME_AUTOPAUSE_TAIL_END_ROUND_OFFSET}, 6,
                {K1_INGAME_AUTOPAUSE_DEFAULT_OFFSET,
                 K1_INGAME_AUTOPAUSE_BACK_OFFSET, -1}, 2};
    case K1_OPTIONS_MAIN_PANEL_VTABLE:
        // Whole column, bottom-up: Quit (hidden on some screens), Sound,
        // Graphics, Auto-Pause, Feedback, Gameplay.
        return {{K1_OPTIONS_MAIN_TAIL_QUIT_OFFSET,
                 K1_OPTIONS_MAIN_TAIL_SOUND_OFFSET,
                 K1_OPTIONS_MAIN_TAIL_GRAPHICS_OFFSET,
                 K1_OPTIONS_MAIN_TAIL_AUTOPAUSE_OFFSET,
                 K1_OPTIONS_MAIN_TAIL_FEEDBACK_OFFSET,
                 K1_OPTIONS_MAIN_TAIL_GAMEPLAY_OFFSET}, 6,
                {K1_OPTIONS_MAIN_BACK_OFFSET, -1, -1}, 1};
    case K1_OPTIONS_FEEDBACK_PANEL_VTABLE:
        return {{K1_OPTIONS_FEEDBACK_TAIL_LISTBOX_OFFSET, -1, -1, -1}, 1,
                {K1_OPTIONS_FEEDBACK_DEFAULT_OFFSET,
                 K1_OPTIONS_FEEDBACK_BACK_OFFSET, -1}, 2, true};
    case K1_OPTIONS_MOUSE_PANEL_VTABLE:
        return {{K1_OPTIONS_MOUSE_TAIL_REVERSE_OFFSET,
                 K1_OPTIONS_MOUSE_TAIL_SENSITIVITY_OFFSET, -1, -1}, 2,
                {K1_OPTIONS_MOUSE_DEFAULT_OFFSET,
                 K1_OPTIONS_MOUSE_BACK_OFFSET, -1}, 2};
    case K1_OPTIONS_GRAPHICS_PANEL_VTABLE:
        // Whole column, bottom-up: Advanced Options, Grass, Shadows, Screen
        // Resolution, Brightness.
        return {{K1_OPTIONS_GRAPHICS_TAIL_ADVANCED_OFFSET,
                 K1_OPTIONS_GRAPHICS_TAIL_GRASS_OFFSET,
                 K1_OPTIONS_GRAPHICS_TAIL_SHADOWS_OFFSET,
                 K1_OPTIONS_GRAPHICS_TAIL_RESOLUTION_OFFSET,
                 K1_OPTIONS_GRAPHICS_TAIL_GAMMA_OFFSET}, 5,
                {K1_OPTIONS_GRAPHICS_DEFAULT_OFFSET,
                 K1_OPTIONS_GRAPHICS_BACK_OFFSET, -1}, 2};
    case K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE:
        // Whole column, bottom-up: V-Sync, Soft Shadows, Frame Buffer Effects,
        // Anisotropy, 8 sample AA, texture quality ("High").
        return {{K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_VSYNC_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_SOFTSHADOW_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_FRAMEBUFFER_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_ANISOTROPY_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_ANTIALIAS_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_TAIL_TEXQUALITY_OFFSET}, 6,
                {K1_OPTIONS_GRAPHICS_ADVANCED_DEFAULT_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_CANCEL_OFFSET,
                 K1_OPTIONS_GRAPHICS_ADVANCED_OK_OFFSET}, 3};
    case K1_OPTIONS_SOUND_PANEL_VTABLE:
        return {{K1_OPTIONS_SOUND_TAIL_ADVANCED_OFFSET,
                 K1_OPTIONS_SOUND_TAIL_MOVIE_OFFSET, -1, -1}, 2,
                {K1_OPTIONS_SOUND_DEFAULT_OFFSET,
                 K1_OPTIONS_SOUND_BACK_OFFSET, -1}, 2};
    case K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE:
        return {{K1_OPTIONS_SOUND_ADVANCED_TAIL_EAX_OFFSET,
                 K1_OPTIONS_SOUND_ADVANCED_TAIL_SOFTWARE_OFFSET, -1, -1}, 2,
                {K1_OPTIONS_SOUND_ADVANCED_DEFAULT_OFFSET,
                 K1_OPTIONS_SOUND_ADVANCED_CANCEL_OFFSET,
                 K1_OPTIONS_SOUND_ADVANCED_OK_OFFSET}, 3};
    default:
        return NO_SETTINGS_STRIP_EXIT;
    }
}

// Focus keeper. Activating a tab leaves the screen with nothing focused, so the
// next D-pad press has nothing to move from.
//
// A is not intercepted -- it is injected as Return and the game activates the
// focused control itself. The tab's handler then repopulates the screen and
// leaves panelActiveControlOffset null, and the module never learns the press
// happened. Nothing else restores focus, so it is restored here.
//
// Restoring ONLY from null is the whole safety argument. Focus moving elsewhere
// is legitimate -- pressing Down into the list is a normal thing to do, and
// fighting that would be worse than the bug. A null active control is never
// useful state; it is exactly the "focus went away" this fixes.
bool IsK1HeaderControl(void* panel, const SettingsStripExit& exit, void* control)
{
    for (int i = 0; i < exit.headerCount; ++i) {
        if (OffsetPointer(panel, exit.header[i]) == control) {
            return true;
        }
    }
    return false;
}

void* g_tabFocusPanel = nullptr;
void* g_tabFocusControl = nullptr;

// KeepK1MenuFocus lived here until 2026-09-06. It restored focus a frame AFTER
// the game moved it, which could not work: the module's other hook runs at
// ProcessInput entry, so the wrong focus was already drawn before anything could
// react -- the one-frame flicker -- and a fast direction press landed in the list
// during the gap. OnSetActiveControlK1 declines the move instead, so the state it
// used to repair is never created. Removed rather than left dormant, because two
// mechanisms racing for the same field is what produced the visible bounce.

// Which tail control is actually on screen varies by context, so take the
// bottom-most one that is currently selectable rather than a fixed offset.
void* FindK1SettingsColumnTail(void* panel, const SettingsStripExit& exit)
{
    for (int index = 0; index < exit.columnTailCount; ++index) {
        void* control = OffsetPointer(panel, exit.columnTail[index]);
        if (IsK1SettingsNavTarget(panel, control)) {
            return control;
        }
    }
    return nullptr;
}

int FindK1SettingsStripIndex(
    void* panel,
    void* control,
    const SettingsStripExit& exit)
{
    if (!control) {
        return -1;
    }
    for (int index = 0; index < exit.stripCount; ++index) {
        if (OffsetPointer(panel, exit.strip[index]) == control) {
            return index;
        }
    }
    return -1;
}

// A strip button can be present but hidden (Advanced Sound omits Cancel on some
// paths), so scan outwards the way the engine's own navigator skips unselectable
// links rather than landing on a dead control.
void* FindK1SelectableStripButton(
    void* panel,
    const SettingsStripExit& exit,
    int start,
    int direction)
{
    for (int index = start;
         index >= 0 && index < exit.stripCount;
         index += direction) {
        void* control = OffsetPointer(panel, exit.strip[index]);
        if (IsK1SettingsNavTarget(panel, control)) {
            return control;
        }
    }
    return nullptr;
}

int K1SettingsTailRowWidth(const SettingsStripExit& exit)
{
    return exit.bottomRowWidth > 0 ? exit.bottomRowWidth : 1;
}

// The bottom row is the first rowWidth *selectable* tail entries rather than
// indices 0..rowWidth-1, because a leading entry can be absent on a given screen
// (Options Main hides Quit, leaving Sound as the real bottom of the column).
bool IsK1InTailBottomRow(
    void* panel,
    void* control,
    const SettingsStripExit& exit)
{
    int rowWidth = K1SettingsTailRowWidth(exit);
    int found = 0;
    for (int index = 0;
         index < exit.columnTailCount && found < rowWidth;
         ++index) {
        void* candidate = OffsetPointer(panel, exit.columnTail[index]);
        if (!IsK1SettingsNavTarget(panel, candidate)) {
            continue;
        }
        if (candidate == control) {
            return true;
        }
        ++found;
    }
    return false;
}

int FindK1SettingsTailIndex(
    void* panel,
    void* control,
    const SettingsStripExit& exit)
{
    if (!control) {
        return -1;
    }
    for (int index = 0; index < exit.columnTailCount; ++index) {
        if (OffsetPointer(panel, exit.columnTail[index]) == control) {
            return index;
        }
    }
    return -1;
}

// Walk the tail from tailIndex by whole rows until a usable control turns up.
// Entries can be unusable for real reasons - the Upgrade Bench greys out any
// category you own nothing for - so capture calls this too, and only swallows the
// key when a target exists. Otherwise the key dies here and focus wedges.
void* FindK1TailStepTarget(
    void* panel,
    const SettingsStripExit& exit,
    int tailIndex,
    int step)
{
    if (tailIndex < 0 || step == 0) {
        return nullptr;
    }
    for (int i = tailIndex + step;
         i >= 0 && i < exit.columnTailCount;
         i += step) {
        void* candidate = OffsetPointer(panel, exit.columnTail[i]);
        if (IsK1SettingsNavTarget(panel, candidate)) {
            return candidate;
        }
    }
    return nullptr;
}

// Feedback's column is a single focusable listbox whose internal selection picks
// the row, so intercepting every Down would strand the rows we never let it reach.
// Only hand off to the strip once its selection is on the last row.
// Mirror of IsK1ListboxAtLastRow for the top of the list. Key Mapping's rows are
// listbox children whose own up/down links chain between each other, so a null
// link never appears at the top; the listbox's selection index is what actually
// tells us we are on the first row.
bool IsK1ListboxAtFirstRow(void* listbox)
{
    if (!listbox) {
        return false;
    }

    int rowCount = ReadInt(listbox, K1_LISTBOX_ROW_COUNT_OFFSET);
    if (rowCount <= 0) {
        return false;
    }

    int selection = *reinterpret_cast<std::int16_t*>(
        OffsetPointer(listbox, K1_LISTBOX_SELECTION_INDEX_OFFSET));
    return selection <= 0;
}

bool IsK1ListboxAtLastRow(void* listbox)
{
    int rowCount = ReadInt(listbox, K1_LISTBOX_ROW_COUNT_OFFSET);
    if (rowCount <= 0) {
        // Offsets not behaving as expected: leave the arrows to vanilla rather
        // than risk trapping focus on one row.
        return false;
    }

    int selection = *reinterpret_cast<std::int16_t*>(
        OffsetPointer(listbox, K1_LISTBOX_SELECTION_INDEX_OFFSET));
    return selection >= rowCount - 1;
}

// A grid tail (bottomRowWidth > 1) is the entire control group, so unlike a plain
// column there is no vanilla chain above it to fall through to. The Upgrade Bench
// greys out any category you own nothing for, so with a column of the grid empty a
// row-step runs off the end and the keypress dies with focus wedged. Wrap to the
// topmost live cell so there is always a way out. Plain columns never wrap: there
// Up above the tail is vanilla's business.
void* FindK1TailUpTarget(
    void* panel,
    const SettingsStripExit& exit,
    int tailIndex)
{
    int rowWidth = K1SettingsTailRowWidth(exit);
    void* stepped = FindK1TailStepTarget(panel, exit, tailIndex, rowWidth);
    if (stepped || rowWidth <= 1 || tailIndex < 0) {
        return stepped;
    }

    for (int i = exit.columnTailCount - 1; i >= 0; --i) {
        if (i == tailIndex) {
            continue;
        }
        void* candidate = OffsetPointer(panel, exit.columnTail[i]);
        if (IsK1SettingsNavTarget(panel, candidate)) {
            return candidate;
        }
    }
    return nullptr;
}

// Are we on the first row of a dynamic column, and so due to leave it upward?
// Prefer the listbox selection index; fall back to a null `up` link for panels
// whose rows are standalone controls rather than listbox children.
bool IsK1AtDynamicColumnTop(
    void* panel,
    const SettingsStripExit& exit,
    void* control)
{
    if (!exit.dynamicColumn) {
        return false;
    }

    void* tail = FindK1SettingsColumnTail(panel, exit);
    if (tail && IsK1ListboxAtFirstRow(tail)) {
        return true;
    }
    if (control == tail) {
        return false;
    }
    return ReadPointer(control, K1_NAVIGABLE_UP_OFFSET) == nullptr;
}

// Prefer the tab that is currently selected, so Up out of the list lands where the
// highlight already is rather than snapping to the leftmost tab.
void* FindK1HeaderTarget(void* panel, const SettingsStripExit& exit)
{
    if (exit.headerCount <= 0) {
        return nullptr;
    }

    if (exit.headerIndexOffset >= 0) {
        int active = ReadInt(panel, exit.headerIndexOffset);
        if (active >= 0 && active < exit.headerCount) {
            void* control = OffsetPointer(panel, exit.header[active]);
            if (IsK1SettingsNavTarget(panel, control)) {
                return control;
            }
        }
    }

    for (int index = 0; index < exit.headerCount; ++index) {
        void* control = OffsetPointer(panel, exit.header[index]);
        if (IsK1SettingsNavTarget(panel, control)) {
            return control;
        }
    }
    return nullptr;
}

int FindK1HeaderIndex(
    void* panel,
    void* control,
    const SettingsStripExit& exit)
{
    if (!control) {
        return -1;
    }
    for (int index = 0; index < exit.headerCount; ++index) {
        if (OffsetPointer(panel, exit.header[index]) == control) {
            return index;
        }
    }
    return -1;
}

bool CaptureK1SettingsNavigation(
    void* manager,
    void* panel,
    std::uint32_t keyOffset)
{
    if (keyOffset != DIK_UP && keyOffset != DIK_DOWN &&
        keyOffset != DIK_LEFT && keyOffset != DIK_RIGHT) {
        return false;
    }

    SettingsStripExit exit = GetK1SettingsStripExit(panel);
    if (exit.stripCount == 0) {
        return false;
    }

    // A confirm dialog over the options screen must keep the arrows; without
    // this we would move focus on the panel underneath it.
    if (manager && HasK1BlockingModal(manager, panel)) {
        return false;
    }

    void* activeControl = ReadPointer(
        panel,
        K1_CONFIG.panelActiveControlOffset);
    if (!activeControl) {
        return false;
    }

    int stripIndex = FindK1SettingsStripIndex(panel, activeControl, exit);
    int tailIndex = FindK1SettingsTailIndex(panel, activeControl, exit);
    int headerIndex = FindK1HeaderIndex(panel, activeControl, exit);
    std::uint8_t mode = 0;
    if (headerIndex >= 0) {
        // On a tab: step along the row, and Down returns to the column. The tabs
        // have no `down` link of their own, so without this the row is a dead end.
        if (keyOffset == DIK_LEFT && headerIndex > 0) {
            mode = SETTINGS_NAV_HEADER_PREV;
        } else if (keyOffset == DIK_RIGHT &&
                   headerIndex < exit.headerCount - 1) {
            mode = SETTINGS_NAV_HEADER_NEXT;
        } else if (keyOffset == DIK_DOWN &&
                   FindK1SettingsColumnTail(panel, exit) != nullptr) {
            mode = SETTINGS_NAV_RETURN_COLUMN;
        }
    } else if (stripIndex < 0) {
        int rowWidth = K1SettingsTailRowWidth(exit);
        bool atColumnEnd;
        if (exit.dynamicColumn) {
            // Dynamic columns come in two shapes and we accept either signal:
            // Feedback focuses the listbox itself, so compare its selection to
            // the row count; Key Mapping focuses individual row buttons, where a
            // null `down` link is the engine's own end-of-list marker. The null
            // test is safe here only because a dynamic column has no tail chain
            // of ours to skip over.
            atColumnEnd =
                (activeControl == FindK1SettingsColumnTail(panel, exit) &&
                 IsK1ListboxAtLastRow(activeControl)) ||
                ReadPointer(activeControl, K1_NAVIGABLE_DOWN_OFFSET) == nullptr;
        } else {
            atColumnEnd = IsK1InTailBottomRow(panel, activeControl, exit);
        }
        // Inside the tail our chain is authoritative. Vanilla's links there are
        // variously null, aimed into the button strip, or aimed at the wrong
        // control (Frame Buffer Effects skips straight past Anisotropy), and a
        // wrong-but-non-null link is indistinguishable from a healthy one.
        // Outside the tail nothing is swallowed, so vanilla keeps the rest.
        if (keyOffset == DIK_DOWN && atColumnEnd) {
            mode = SETTINGS_NAV_ENTER_STRIP;
        } else if (keyOffset == DIK_DOWN &&
                   FindK1TailStepTarget(panel, exit, tailIndex, -rowWidth)) {
            mode = SETTINGS_NAV_COLUMN_DOWN;
        } else if (keyOffset == DIK_UP &&
                   FindK1TailUpTarget(panel, exit, tailIndex)) {
            mode = SETTINGS_NAV_COLUMN_UP;
        } else if (keyOffset == DIK_UP &&
                   exit.headerCount > 0 &&
                   IsK1AtDynamicColumnTop(panel, exit, activeControl) &&
                   FindK1HeaderTarget(panel, exit)) {
            mode = SETTINGS_NAV_HEADER;
        }
    } else if (keyOffset == DIK_UP &&
               FindK1SettingsColumnTail(panel, exit) != nullptr) {
        // Only claim Up out of the strip if there is somewhere to land, else we
        // swallow the key, resolve nothing, and trap focus in the strip.
        mode = SETTINGS_NAV_RETURN_COLUMN;
    } else if (keyOffset == DIK_LEFT && stripIndex > 0) {
        mode = SETTINGS_NAV_STRIP_PREV;
    } else if (keyOffset == DIK_RIGHT &&
               stripIndex < exit.stripCount - 1) {
        mode = SETTINGS_NAV_STRIP_NEXT;
    }

    if (mode == 0) {
        return false;
    }

    g_pendingSettingsNav = mode;
    g_pendingInput |= PENDING_K1_SETTINGS_NAV;
    return true;
}

int FindK1PazaakControlIndex(
    void* panel,
    void* control,
    std::ptrdiff_t offset,
    int count)
{
    std::uintptr_t first =
        reinterpret_cast<std::uintptr_t>(OffsetPointer(panel, offset));
    std::uintptr_t current = reinterpret_cast<std::uintptr_t>(control);
    if (current < first) {
        return -1;
    }

    std::uintptr_t delta = current - first;
    if (delta % K1_PAZAAK_CARD_STRIDE != 0) {
        return -1;
    }

    int index = static_cast<int>(delta / K1_PAZAAK_CARD_STRIDE);
    return index < count ? index : -1;
}

bool IsK1PazaakGridControl(void* panel, void* control)
{
    return FindK1PazaakControlIndex(
               panel,
               control,
               K1_PAZAAK_AVAILABLE_OFFSET,
               K1_PAZAAK_AVAILABLE_COUNT) >= 0 ||
        FindK1PazaakControlIndex(
               panel,
               control,
               K1_PAZAAK_CHOSEN_OFFSET,
               K1_PAZAAK_CHOSEN_COUNT) >= 0;
}

int FindK1PazaakHandIndex(void* panel, void* control)
{
    return FindK1PazaakControlIndex(
        panel,
        control,
        K1_PAZAAK_HAND_OFFSET,
        K1_PAZAAK_HAND_COUNT);
}

int FindK1PazaakFlipIndex(void* panel, void* control)
{
    std::uintptr_t first = reinterpret_cast<std::uintptr_t>(
        OffsetPointer(panel, K1_PAZAAK_FLIP_OFFSET));
    std::uintptr_t current = reinterpret_cast<std::uintptr_t>(control);
    if (current < first) {
        return -1;
    }

    std::uintptr_t delta = current - first;
    if (delta % K1_PAZAAK_FLIP_STRIDE != 0) {
        return -1;
    }

    int index = static_cast<int>(delta / K1_PAZAAK_FLIP_STRIDE);
    return index < K1_PAZAAK_HAND_COUNT ? index : -1;
}

int FindK1PartyGridIndex(void* panel, void* control)
{
    std::uintptr_t first = reinterpret_cast<std::uintptr_t>(
        OffsetPointer(panel, K1_PARTY_GRID_OFFSET));
    std::uintptr_t current = reinterpret_cast<std::uintptr_t>(control);
    if (current < first) {
        return -1;
    }

    std::uintptr_t delta = current - first;
    if (delta % K1_PARTY_GRID_STRIDE != 0) {
        return -1;
    }

    int index = static_cast<int>(delta / K1_PARTY_GRID_STRIDE);
    return index < K1_PARTY_GRID_COUNT ? index : -1;
}

int FindK1ClassSelectIndex(void* panel, void* control)
{
    std::uintptr_t first = reinterpret_cast<std::uintptr_t>(
        OffsetPointer(panel, K1_CLASS_SELECT_OFFSET));
    std::uintptr_t current = reinterpret_cast<std::uintptr_t>(control);
    if (current < first) {
        return -1;
    }

    std::uintptr_t delta = current - first;
    if (delta % K1_CLASS_SELECT_STRIDE != 0) {
        return -1;
    }

    int index = static_cast<int>(delta / K1_CLASS_SELECT_STRIDE);
    return index < K1_CLASS_SELECT_COUNT ? index : -1;
}

#if 0   // dead: menu action map lookup and resolver
MenuActionMap GetK1MenuActionMap(void* panel)
{
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_CHARACTER_PANEL_VTABLE:
        return {
            {K1_CHARACTER_SCRIPTS_OFFSET, 0, 0, K1_CHARACTER_SCRIPTS_CALLBACK},
            NO_MENU_ACTION,
            NO_MENU_ACTION,
            NO_MENU_ACTION,
        };
    case K1_CONTAINER_PANEL_VTABLE:
        return {
            {K1_CONTAINER_GET_ITEMS_OFFSET, 0, 0, K1_CONTAINER_GET_ITEMS_CALLBACK},
            {K1_CONTAINER_GIVE_ITEMS_OFFSET, 0, 0, K1_CONTAINER_GIVE_ITEMS_CALLBACK},
            NO_MENU_ACTION,
            NO_MENU_ACTION,
        };
    case K1_SAVELOAD_PANEL_VTABLE:
        return {
            {K1_SAVELOAD_DELETE_OFFSET, 0, 0, K1_SAVELOAD_DELETE_CALLBACK},
            {K1_SAVELOAD_LOAD_OFFSET, 0, 0, K1_SAVELOAD_LOAD_CALLBACK},
            NO_MENU_ACTION,
            NO_MENU_ACTION,
        };
    case K1_UPGRADE_SELECTION_PANEL_VTABLE:
        return {
            {K1_UPGRADE_ITEMS_OFFSET, 0, 0, K1_UPGRADE_ITEMS_CALLBACK},
            NO_MENU_ACTION,
            NO_MENU_ACTION,
            NO_MENU_ACTION,
        };
    default:
        return NO_MENU_ACTIONS;
    }
}

struct ResolvedMenuAction {
    void* control;
    std::uintptr_t callback;
};

ResolvedMenuAction ResolveK1MenuAction(void* panel, MenuActionSlot slot)
{
    MenuActionMap map = GetK1MenuActionMap(panel);
    const MenuActionTarget* target = nullptr;
    switch (slot) {
    case MenuActionSlot::Primary:
        target = &map.primary;
        break;
    case MenuActionSlot::Secondary:
        target = &map.secondary;
        break;
    case MenuActionSlot::Auxiliary1:
        target = &map.auxiliary1;
        break;
    case MenuActionSlot::Auxiliary2:
        target = &map.auxiliary2;
        break;
    }
    if (!target || target->offset < 0) {
        return {nullptr, 0};
    }
    return {
        OffsetPointer(panel, target->offset + target->stride * target->index),
        target->callback,
    };
}

#endif  // 0

// Experimental: End/Home/Insert stand in for X/Y/Black, dispatched generically
// (same mechanism as J's Space->X-button fallback) instead of a per-panel offset map.
void* GetK1ActiveGuiManager()
{
    void* mainInterface = g_mainInterface;
    void* manager = mainInterface
        ? ReadPointer(mainInterface, K1_CONFIG.panelManagerOffset)
        : nullptr;
    return manager ? manager : GetK1TitleGuiManager();
}

// Driven off the live mask rather than a remembered flag, so if anything ever
// clears our reason the next frame simply puts it back.
void SetK1CursorHidden(void* clientApp, bool hide)
{
    if (!clientApp) {
        return;
    }

    std::uint32_t mask = static_cast<std::uint32_t>(
        ReadInt(clientApp, K1_CLIENT_MOUSE_HIDE_MASK_OFFSET));
    if (hide == ((mask & K1_CURSOR_HIDE_REASON) != 0)) {
        return;
    }

    reinterpret_cast<ClientMouseFn>(
        hide ? K1_CLIENT_HIDE_MOUSE : K1_CLIENT_SHOW_MOUSE)(
        clientApp,
        K1_CURSOR_HIDE_REASON);
}

// Set while the module is moving the cursor itself. MoveMouseToPosition
// forwards to HandleMouseMove, which is the function KMRP hooks to notice mouse
// activity -- so without this every park, and every re-assert of the park spot,
// reads as though a hand had moved the pointer.
//
// It breaks the detector both ways. Several panels place the cursor on a default
// control as they open; the re-assert that undoes that would accumulate the 24
// pixels and 2 events that mean "the mouse is in use" and hand the pointer back
// in the middle of a controller session. And while parked, a real movement and
// the snap-back that cancels it both count, so the distance measured bears
// little relation to how far the hand actually moved.
bool g_movingCursorOurselves = false;

bool MoveK1Cursor(bool toParkedSpot)
{
    void* manager = GetK1ActiveGuiManager();
    if (!manager) {
        return false;
    }

    int width = ReadShort(manager, K1_MANAGER_VIEWPORT_WIDTH_OFFSET);
    int height = ReadShort(manager, K1_MANAGER_VIEWPORT_HEIGHT_OFFSET);
    if (width <= 0 || height <= 0) {
        return false;
    }

    // Unparking drops it in the middle of the viewport rather than restoring
    // wherever it was, so bringing the pointer back always puts it somewhere
    // visible instead of back under the top edge it was just moved out of.
    g_movingCursorOurselves = true;
    reinterpret_cast<GuiManagerMoveMouseFn>(K1_GUI_MOVE_MOUSE_TO_POSITION)(
        manager,
        width / 2,
        toParkedSpot ? K1_PARKED_CURSOR_Y : height / 2);
    g_movingCursorOurselves = false;
    return true;
}

// F9 only. An idle timer drove this at first and fired about three seconds
// into the title screen, which is how the calling convention bug in the old
// hide path surfaced; manual control is enough until parking itself is proven.
void UpdateK1CursorState(void* clientApp)
{
    // Park the pointer when the pad becomes the input device in use, and give it
    // back the moment mouse or keyboard is touched. Edge-triggered on the change
    // rather than asserted every frame, so F9 still works as a manual override
    // within a mode instead of being stamped on by the next frame.
    //
    // The comment below records that an IDLE TIMER drove this once and misfired
    // three seconds into the title screen. This is not that: IsControllerInputActiveK1
    // is the same signal the button badges already use, it is false until the
    // player actually presses something on the pad, and MouseIsBeingUsedK1 clears
    // it on real pointer movement -- KOTOR's own cursor recentring does not.
    //
    // It routes through g_pendingCursorToggle deliberately, so parking still runs
    // the one proven path (MoveK1Cursor then SetK1CursorHidden) rather than a
    // second one that could drift from it.
    const bool controllerMode = IsControllerInputActiveK1();
    if (controllerMode != g_cursorFollowedControllerMode) {
        g_cursorFollowedControllerMode = controllerMode;
        // Assigned, not just raised. The flag means "flip it", and now that a
        // failed flip is retried rather than dropped, one can still be pending
        // when the device changes again -- at which point the flip it asked for
        // is the wrong way round. Recomputing here cancels a stale request
        // instead of letting it park the cursor against the device in use.
        //
        // This also means a device change wins over a pending F9, which is the
        // right precedence: F9 is an override within a mode.
        g_pendingCursorToggle = (controllerMode != g_cursorParked);
    }

    if (g_pendingCursorToggle) {
        // Cleared only once the move has actually happened. MoveK1Cursor fails
        // whenever there is no active GUI manager or its viewport is not sized
        // yet -- during a load, a movie, a scene transition -- and dropping the
        // request there left the cursor parked and hidden while the player was
        // using the mouse, with the re-assert below pinning it to the top of the
        // screen every frame. Invisible, immovable, hit-testing nothing: the
        // mouse appeared to stop working entirely, and only a second change of
        // input device could ever raise the request again.
        if (MoveK1Cursor(!g_cursorParked)) {
            g_pendingCursorToggle = false;
            g_cursorParked = !g_cursorParked;
            SetK1CursorHidden(clientApp, g_cursorParked);
        }
        return;
    }

    if (!g_cursorParked) {
        return;
    }

    // Ahead of the position work and not gated on the GUI manager, so the
    // opening hidden state lands as early as the client object exists.
    SetK1CursorHidden(clientApp, true);

    void* manager = GetK1ActiveGuiManager();
    if (!manager) {
        return;
    }
    int width = ReadShort(manager, K1_MANAGER_VIEWPORT_WIDTH_OFFSET);
    if (width <= 0) {
        return;
    }

    // Re-assert the park spot instead of trusting it to stay put. Several
    // panels place the pointer on a default control as they open, which drags
    // a parked cursor back into the layout; snapping it back the same frame
    // blocks that without having to intercept each caller. Comparing first
    // keeps this to a no-op on the frames where nothing moved it.
    if (ReadInt(manager, K1_MANAGER_MOUSE_X_OFFSET) != width / 2 ||
        ReadInt(manager, K1_MANAGER_MOUSE_Y_OFFSET) != K1_PARKED_CURSOR_Y) {
        MoveK1Cursor(true);
    }
}

void* FindK1DescriptionListbox(void* panel)
{
    std::ptrdiff_t offset;
    switch (*reinterpret_cast<std::uintptr_t*>(panel)) {
    case K1_INGAME_OPTIONS_PANEL_VTABLE:
        offset = K1_INGAME_OPTIONS_DESC_OFFSET;
        break;
    case K1_INGAME_GAMEPLAY_PANEL_VTABLE:
        offset = K1_INGAME_GAMEPLAY_DESC_OFFSET;
        break;
    case K1_INGAME_AUTOPAUSE_PANEL_VTABLE:
        offset = K1_INGAME_AUTOPAUSE_DESC_OFFSET;
        break;
    case K1_OPTIONS_MAIN_PANEL_VTABLE:
        offset = K1_OPTIONS_MAIN_DESC_OFFSET;
        break;
    case K1_OPTIONS_FEEDBACK_PANEL_VTABLE:
        offset = K1_OPTIONS_FEEDBACK_DESC_OFFSET;
        break;
    case K1_OPTIONS_MOUSE_PANEL_VTABLE:
        offset = K1_OPTIONS_MOUSE_DESC_OFFSET;
        break;
    case K1_OPTIONS_GRAPHICS_PANEL_VTABLE:
        offset = K1_OPTIONS_GRAPHICS_DESC_OFFSET;
        break;
    case K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE:
        offset = K1_OPTIONS_GRAPHICS_ADVANCED_DESC_OFFSET;
        break;
    case K1_OPTIONS_SOUND_PANEL_VTABLE:
        offset = K1_OPTIONS_SOUND_DESC_OFFSET;
        break;
    case K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE:
        offset = K1_OPTIONS_SOUND_ADVANCED_DESC_OFFSET;
        break;
    case K1_UPGRADE_PANEL_VTABLE:
        offset = K1_UPGRADE_DESC_OFFSET;
        break;
    case K1_UPGRADE_ITEM_SELECT_PANEL_VTABLE:
        offset = K1_UPGRADE_ITEM_SELECT_DESC_OFFSET;
        break;
    case K1_INVENTORY_PANEL_VTABLE:
        offset = K1_INVENTORY_DESC_OFFSET;
        break;
    case K1_STORE_PANEL_VTABLE:
        offset = K1_STORE_DESC_OFFSET;
        break;
    case K1_ABILITIES_PANEL_VTABLE:
        offset = K1_ABILITIES_DESC_OFFSET;
        break;
    case K1_FEATS_PANEL_VTABLE:
        offset = K1_FEATS_DESC_OFFSET;
        break;
    case K1_POWERS_PANEL_VTABLE:
        offset = K1_POWERS_DESC_OFFSET;
        break;
    case K1_EQUIP_PANEL_VTABLE:
        offset = K1_EQUIP_DESC_OFFSET;
        break;
    default:
        return nullptr;
    }

    // Visibility only, not selectability: a description pane is never
    // selectable, which is the whole reason focus cannot reach it and the
    // event has to be delivered to the control directly. Panels that hide
    // theirs must still let the key through to whatever else wants it.
    void* control = OffsetPointer(panel, offset);
    return (ReadInt(control, K1_CONFIG.panelFlagsOffset) & CONTROL_VISIBLE) != 0
        ? control
        : nullptr;
}

bool CaptureK1DescriptionScroll(void* panel, std::uint32_t keyOffset)
{
    int direction;
    switch (keyOffset) {
    case DIK_PRIOR:
        direction = -1;
        break;
    case DIK_NEXT:
        direction = 1;
        break;
    default:
        return false;
    }

    if (!FindK1DescriptionListbox(panel)) {
        return false;
    }

    // Bounded so a dispatch that never runs - panel torn down mid-frame, say -
    // cannot bank an unbounded scroll that all fires at once when it resumes.
    if (direction < 0 ? g_pendingDescScroll > -32 : g_pendingDescScroll < 32) {
        g_pendingDescScroll += direction;
    }
    return true;
}

bool CaptureK1GenericButton(std::uint32_t keyOffset)
{
    int event;
    switch (keyOffset) {
    case DIK_END:
        event = K1_GUI_CONTROLLER_X_EVENT;
        break;
    case DIK_HOME:
        event = K1_GUI_Y_BUTTON_EVENT;
        break;
    case DIK_INSERT:
        event = K1_GUI_BLACK_BUTTON_EVENT;
        break;
    default:
        return false;
    }

    g_pendingGenericButtonEvent = static_cast<std::uint8_t>(event);
    g_pendingInput |= PENDING_K1_GENERIC_BUTTON;
    return true;
}

void DispatchPanelInput(void* panel, int event)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(panel);
    void* activeControl = ReadPointer(
        panel,
        K1_CONFIG.panelActiveControlOffset);
    std::uintptr_t activeVtable = activeControl
        ? *reinterpret_cast<std::uintptr_t*>(activeControl)
        : 0;
    int activeFlags = activeControl
        ? ReadInt(activeControl, 0x44)
        : 0;
    char trace[192];
    std::snprintf(
        trace,
        sizeof(trace),
        "[K1Xbox] generic event=0x%02X panel=0x%08X active=0x%p control_vtable=0x%08X flags=0x%08X\n",
        event,
        static_cast<unsigned int>(vtable),
        activeControl,
        static_cast<unsigned int>(activeVtable),
        static_cast<unsigned int>(activeFlags));
    OutputDebugStringA(trace);
    std::uintptr_t callback =
        *reinterpret_cast<std::uintptr_t*>(vtable + 0x3C);
    reinterpret_cast<HandleInputEventFn>(callback)(panel, event, 1);
}

void DispatchControlInput(void* control, int event)
{
    std::uintptr_t vtable = *reinterpret_cast<std::uintptr_t*>(control);
    std::uintptr_t callback =
        *reinterpret_cast<std::uintptr_t*>(vtable + 0x3C);
    reinterpret_cast<HandleInputEventFn>(callback)(control, event, 1);
}

ActionButtons GetActionButtons(const GameConfig& config, void* mainInterface)
{
    ActionButtons buttons{};
    void* targetActions = OffsetPointer(
        mainInterface,
        config.targetActionMenuOffset + TARGET_ACTIONS_OFFSET);

    for (int i = 0; i < TARGET_ACTION_COUNT; ++i) {
        buttons[i] = OffsetPointer(targetActions, i * config.actionGroupSize);
    }

    void* personalActions = OffsetPointer(
        mainInterface,
        config.personalActionsOffset);
    for (int i = 0; i < config.personalActionCount; ++i) {
        buttons[TARGET_ACTION_COUNT + i] =
            OffsetPointer(personalActions, i * config.actionGroupSize);
    }

    return buttons;
}

int FindButton(
    const GameConfig& config,
    const ActionButtons& buttons,
    void* button)
{
    for (int i = 0; i < ActionButtonCount(config); ++i) {
        if (buttons[i] == button) {
            return i;
        }
    }
    return -1;
}

bool IsActionBarFocused(const GameConfig& config, void* mainInterface)
{
    void* manager = mainInterface
        ? ReadPointer(mainInterface, config.panelManagerOffset)
        : nullptr;
    if (!manager || !IsGameplayHudActive(config, manager, mainInterface)) {
        return false;
    }

    ActionButtons buttons = GetActionButtons(config, mainInterface);
    void* activeControl = ReadPointer(
        mainInterface,
        config.panelActiveControlOffset);
    return FindButton(config, buttons, activeControl) >= 0;
}

bool IsActionControl(
    const GameConfig& config,
    const ActionButtons& buttons,
    void* control)
{
    for (int i = 0; i < ActionButtonCount(config); ++i) {
        for (std::ptrdiff_t offset : config.actionControlOffsets) {
            if (OffsetPointer(buttons[i], offset) == control) {
                return true;
            }
        }
    }
    return false;
}

int FindSelectableButton(
    const GameConfig& config,
    void* mainInterface,
    const ActionButtons& buttons,
    int start,
    int direction)
{
    const int buttonCount = ActionButtonCount(config);
    const auto getIsSelectable =
        reinterpret_cast<GetIsSelectableFn>(config.getIsSelectable);
    int index = start;
    for (int count = 0; count < buttonCount; ++count) {
        index = (index + direction + buttonCount) % buttonCount;
        if (index < TARGET_ACTION_COUNT) {
            void* targetMenu = OffsetPointer(
                mainInterface,
                config.targetActionMenuOffset);
            if (ReadInt(
                    targetMenu,
                    index * TARGET_ACTION_LIST_SIZE +
                        TARGET_ACTION_LIST_COUNT_OFFSET) <= 0) {
                continue;
            }
        }
        if ((ReadInt(buttons[index], config.panelFlagsOffset) & CONTROL_VISIBLE) != 0 &&
            getIsSelectable(buttons[index])) {
            return index;
        }
    }
    return -1;
}

void MoveFocus(
    const GameConfig& config,
    void* mainInterface,
    const ActionButtons& buttons,
    int activeIndex,
    int direction)
{
    const int buttonCount = ActionButtonCount(config);
    int start = activeIndex;
    if (start < 0) {
        start = direction > 0 ? buttonCount - 1 : 0;
    }

    int nextIndex = FindSelectableButton(
        config,
        mainInterface,
        buttons,
        start,
        direction);
    if (nextIndex >= 0) {
        reinterpret_cast<SetActiveControlFn>(config.setActiveControl)(
            mainInterface,
            buttons[nextIndex],
            1);
    }
}

void CycleAction(
    const GameConfig& config,
    void* mainInterface,
    const ActionButtons& buttons,
    int activeIndex,
    bool next)
{
    if (activeIndex < 0) {
        return;
    }

    std::uintptr_t callback;
    if (activeIndex < TARGET_ACTION_COUNT) {
        callback = next ? config.targetNext : config.targetPrevious;
    } else {
        callback = next ? config.personalNext : config.personalPrevious;
    }

    reinterpret_cast<ActionCallbackFn>(callback)(
        mainInterface,
        buttons[activeIndex]);
}

std::uint32_t InputBit(std::uint32_t keyOffset)
{
    switch (keyOffset) {
    case DIK_UP:
        return PENDING_UP;
    case DIK_DOWN:
        return PENDING_DOWN;
    case DIK_LEFT:
        return PENDING_LEFT;
    case DIK_RIGHT:
        return PENDING_RIGHT;
    case DIK_RETURN:
        return PENDING_ACTIVATE;
    default:
        return 0;
    }
}

void CaptureActionBarInput(
    const GameConfig& config,
    const BufferedInputRecord* input,
    int inputDevice)
{
    if (!input || inputDevice != *reinterpret_cast<int*>(config.keyboardDeviceIndex)) {
        return;
    }

    if ((input->value & KEY_PRESSED) != 0 &&
        input->offset == DIK_DELETE &&
        config.handleGuiInputEvent != 0) {
        g_pendingInput |= PENDING_CONTEXT_CANCEL;
        return;
    }

    void* mainInterface = g_mainInterface;
    void* manager = mainInterface
        ? ReadPointer(mainInterface, config.panelManagerOffset)
        : nullptr;
    if (!manager || !IsGameplayHudActive(config, manager, mainInterface)) {
        g_pendingInput &= PENDING_CONTEXT_INPUT;
        return;
    }

    if ((input->value & KEY_PRESSED) != 0) {
        g_pendingInput |= InputBit(input->offset);
    }
}

void UpdateActionBarControls(const GameConfig& config, void* mainInterface)
{
    g_mainInterface = mainInterface;
    std::uint32_t pending = g_pendingInput & PENDING_ACTION_BAR_INPUT;
    g_pendingInput &= PENDING_CONTEXT_INPUT;

    if (!mainInterface || pending == 0) {
        return;
    }

    void* manager = ReadPointer(mainInterface, config.panelManagerOffset);
    if (!manager || !IsGameplayHudActive(config, manager, mainInterface)) {
        return;
    }

    ActionButtons buttons = GetActionButtons(config, mainInterface);
    void* activeControl = ReadPointer(
        mainInterface,
        config.panelActiveControlOffset);
    int activeIndex = FindButton(config, buttons, activeControl);

    if ((pending & PENDING_LEFT) != 0) {
        MoveFocus(config, mainInterface, buttons, activeIndex, -1);
    }
    if ((pending & PENDING_RIGHT) != 0) {
        MoveFocus(config, mainInterface, buttons, activeIndex, 1);
    }
    if ((pending & PENDING_UP) != 0) {
        CycleAction(config, mainInterface, buttons, activeIndex, false);
    }
    if ((pending & PENDING_DOWN) != 0) {
        CycleAction(config, mainInterface, buttons, activeIndex, true);
    }
    if ((pending & PENDING_ACTIVATE) != 0 && activeIndex >= 0) {
        reinterpret_cast<ActionCallbackFn>(config.activate)(
            mainInterface,
            buttons[activeIndex]);
    }
}

void ClearActionBarKeyboardFocus(
    const GameConfig& config,
    void* hoveredPanel,
    void* hoveredControl)
{
    void* mainInterface = g_mainInterface;
    if (!mainInterface || hoveredPanel != mainInterface) {
        return;
    }

    ActionButtons buttons = GetActionButtons(config, mainInterface);
    if (!IsActionControl(config, buttons, hoveredControl)) {
        return;
    }

    void* activeControl = ReadPointer(
        mainInterface,
        config.panelActiveControlOffset);
    if (FindButton(config, buttons, activeControl) >= 0) {
        reinterpret_cast<SetActiveControlFn>(config.setActiveControl)(
            mainInterface,
            nullptr,
            1);
    }
}

} // namespace

extern "C" void __cdecl CaptureActionBarInputK1(
    BufferedInputRecord* input,
    int inputDevice)
{
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        (input->value & KEY_PRESSED) != 0 &&
        !IsControllerGeneratedKeyK1(input->offset)) {
        MarkKeyboardMouseInputK1();
    }

    // Ahead of everything else, and outside the menu-panel branch further down,
    // so the toggle answers in gameplay as well as menus. Acted on at the next
    // frame rather than here, because parking the cursor talks to the GUI
    // manager and this runs on the input thread.
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        input->offset == DIK_F9) {
        if ((input->value & KEY_PRESSED) != 0) {
            g_pendingCursorToggle = true;
        }
        input->offset = 0;
        input->value = 0;
        return;
    }

    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        input->offset == DIK_DELETE) {
        void* mainInterface = g_mainInterface;
        void* manager = mainInterface
            ? ReadPointer(mainInterface, K1_CONFIG.panelManagerOffset)
            : nullptr;
        if (!manager ||
            !HasK1DeleteEscapeSuppressedPanel(manager) &&
            !IsGameplayHudActive(K1_CONFIG, manager, mainInterface)) {
            input->offset = DIK_ESCAPE;
            return;
        }
    }

    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        input->offset == DIK_RETURN &&
        (input->value & KEY_PRESSED) == 0 &&
        g_k1SuppressPazaakFlipEnterRelease) {
        input->offset = 0;
        g_k1SuppressPazaakFlipEnterRelease = false;
    }

    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        input->offset == DIK_R &&
        IsActionBarFocused(K1_CONFIG, g_mainInterface)) {
        input->offset = 0;
        input->value = 0;
        return;
    }

    CaptureActionBarInput(K1_CONFIG, input, inputDevice);
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        (input->value & KEY_PRESSED) != 0) {
        void* manager = nullptr;
        void* panel = FindK1MenuPanelForInput(&manager);
        if (!panel) {
            return;
        }

        if (CaptureK1SettingsCycle(panel, input->offset)) {
            input->offset = 0;
            input->value = 0;
            return;
        }

        // Clearing only the pressed bit is what the party-select path does: the
        // engine then sees a release and won't also walk its own link graph.
        if (CaptureK1SettingsNavigation(manager, panel, input->offset)) {
            input->value = 0;
            return;
        }

        if (CaptureK1GenericButton(input->offset)) {
            input->offset = 0;
            input->value = 0;
            return;
        }

        // Ahead of the per-panel branches below, because a description pane is
        // the same control on every screen that has one and none of those
        // branches know about it. Falls through untouched on panels without
        // one, so PageUp/PageDown keep whatever meaning they already had.
        if (CaptureK1DescriptionScroll(panel, input->offset)) {
            input->offset = 0;
            input->value = 0;
            return;
        }

        bool isJournal =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_JOURNAL_PANEL_VTABLE;
        bool isPazaak =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_PAZAAK_SETUP_PANEL_VTABLE;
        bool isPazaakGame =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_PAZAAK_GAME_PANEL_VTABLE;
        bool isPartySelect =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_PARTY_SELECT_PANEL_VTABLE;
        bool isClassSelect =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_CLASS_SELECT_PANEL_VTABLE;
        bool isFeats =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_FEATS_PANEL_VTABLE;
        bool isPowers =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_POWERS_PANEL_VTABLE;
        bool isLevelUp =
            *reinterpret_cast<std::uintptr_t*>(panel) ==
            K1_LEVEL_UP_PANEL_VTABLE;
        if (isLevelUp) {
            return;
        }
        if (isPowers) {
            return;
        }
        if (isFeats) {
            return;
        }
        if (isPartySelect) {
            if (HasK1BlockingModal(manager, panel)) {
                return;
            }

            void* activeControl = ReadPointer(
                panel,
                K1_CONFIG.panelActiveControlOffset);
            int gridIndex =
                FindK1PartyGridIndex(panel, activeControl);
            std::uint32_t pending = 0;
            if (input->offset == DIK_DOWN &&
                gridIndex >= K1_PARTY_BOTTOM_ROW_START) {
                pending = PENDING_K1_PARTY_BUTTON_ROW;
                g_pendingK1PartyTargetOffset = K1_PARTY_DONE_OFFSET;
            } else if (input->offset == DIK_RIGHT &&
                       activeControl == OffsetPointer(
                           panel,
                           K1_PARTY_DONE_OFFSET)) {
                pending = PENDING_K1_PARTY_BUTTON_ROW;
                g_pendingK1PartyTargetOffset = K1_PARTY_BACK_OFFSET;
            } else if (input->offset == DIK_LEFT &&
                       activeControl == OffsetPointer(
                           panel,
                           K1_PARTY_BACK_OFFSET)) {
                pending = PENDING_K1_PARTY_BUTTON_ROW;
                g_pendingK1PartyTargetOffset = K1_PARTY_DONE_OFFSET;
            } else if (input->offset == DIK_UP &&
                       (activeControl == OffsetPointer(
                            panel,
                            K1_PARTY_DONE_OFFSET) ||
                        activeControl == OffsetPointer(
                            panel,
                            K1_PARTY_BACK_OFFSET))) {
                pending = PENDING_K1_PARTY_GRID_RETURN;
                g_pendingK1PartyTargetOffset = -1;
            }

            if (pending != 0) {
                g_pendingInput |= pending;
                input->value = 0;
            }
            return;
        }
        if (isClassSelect) {
            if (input->offset != DIK_LEFT && input->offset != DIK_RIGHT) {
                return;
            }
            if (HasK1BlockingModal(manager, panel)) {
                return;
            }

            void* activeControl = ReadPointer(
                panel,
                K1_CONFIG.panelActiveControlOffset);
            int gridIndex =
                FindK1ClassSelectIndex(panel, activeControl);
            if (gridIndex < 0) {
                return;
            }

            std::uint32_t pending = 0;
            if (input->offset == DIK_LEFT && gridIndex > 0) {
                pending = PENDING_K1_CLASS_SELECT_LEFT;
            } else if (input->offset == DIK_RIGHT &&
                       gridIndex < K1_CLASS_SELECT_COUNT - 1) {
                pending = PENDING_K1_CLASS_SELECT_RIGHT;
            }

            if (pending != 0) {
                g_pendingInput |= pending;
                input->value = 0;
            }
            return;
        }
        if (isPazaakGame) {
            if (HasK1BlockingModal(manager, panel)) {
                return;
            }

            void* activeControl = ReadPointer(
                panel,
                K1_CONFIG.panelActiveControlOffset);
            int handIndex =
                FindK1PazaakHandIndex(panel, activeControl);
            int flipIndex =
                FindK1PazaakFlipIndex(panel, activeControl);
            std::uint32_t pending = 0;
            if (input->offset == DIK_LEFT &&
                (handIndex >= 0 ||
                 activeControl == OffsetPointer(
                     panel,
                     K1_PAZAAK_END_TURN_OFFSET))) {
                pending = PENDING_K1_PAZAAK_GAME_LEFT;
            } else if (input->offset == DIK_RIGHT &&
                       handIndex >= 0) {
                pending = PENDING_K1_PAZAAK_GAME_RIGHT;
            } else if (input->offset == DIK_DOWN &&
                       handIndex >= 0 &&
                       IsK1SelectableControl(OffsetPointer(
                           panel,
                           K1_PAZAAK_FLIP_OFFSET +
                               handIndex * K1_PAZAAK_FLIP_STRIDE))) {
                pending = PENDING_K1_PAZAAK_GAME_FLIP_DOWN;
            } else if (input->offset == DIK_UP &&
                       flipIndex >= 0) {
                pending = PENDING_K1_PAZAAK_GAME_FLIP_UP;
            } else if (input->offset == DIK_RETURN &&
                       handIndex >= 0) {
                pending = PENDING_K1_PAZAAK_GAME_PLAY_CARD;
            } else if (input->offset == DIK_RETURN &&
                       flipIndex >= 0) {
                pending = PENDING_K1_PAZAAK_GAME_FLIP_CARD;
                g_k1SuppressPazaakFlipEnterRelease = true;
            }

            if (pending != 0) {
                g_pendingInput |= pending;
                input->value = 0;
                if (pending == PENDING_K1_PAZAAK_GAME_FLIP_CARD) {
                    input->offset = 0;
                }
            }
            return;
        }
        if (isPazaak) {
            if (input->offset != DIK_UP &&
                input->offset != DIK_DOWN &&
                input->offset != DIK_LEFT &&
                input->offset != DIK_RIGHT) {
                return;
            }
            if (HasK1BlockingModal(manager, panel)) {
                return;
            }

            void* activeControl = ReadPointer(
                panel,
                K1_CONFIG.panelActiveControlOffset);
            int availableIndex = FindK1PazaakControlIndex(
                panel,
                activeControl,
                K1_PAZAAK_AVAILABLE_OFFSET,
                K1_PAZAAK_AVAILABLE_COUNT);
            int chosenIndex = FindK1PazaakControlIndex(
                panel,
                activeControl,
                K1_PAZAAK_CHOSEN_OFFSET,
                K1_PAZAAK_CHOSEN_COUNT);
            void* playControl =
                OffsetPointer(panel, K1_PAZAAK_PLAY_OFFSET);
            std::uint32_t pending = 0;

            if (availableIndex < 0 &&
                chosenIndex < 0 &&
                activeControl != playControl) {
                pending = PENDING_K1_PAZAAK_INITIAL_FOCUS;
            } else if (input->offset == DIK_RIGHT &&
                       availableIndex / K1_PAZAAK_AVAILABLE_ROWS == 2) {
                pending = PENDING_K1_PAZAAK_SWITCH_GRID;
            } else if (input->offset == DIK_LEFT &&
                       chosenIndex >= 0 &&
                       chosenIndex % K1_PAZAAK_CHOSEN_COLUMNS == 0) {
                pending = PENDING_K1_PAZAAK_SWITCH_GRID;
            } else if (input->offset == DIK_DOWN &&
                       ((availableIndex >= 0 &&
                         availableIndex % K1_PAZAAK_AVAILABLE_ROWS ==
                             K1_PAZAAK_AVAILABLE_ROWS - 1) ||
                        chosenIndex >=
                            K1_PAZAAK_CHOSEN_COUNT -
                                K1_PAZAAK_CHOSEN_COLUMNS)) {
                g_k1PazaakReturnControl = activeControl;
                pending = PENDING_K1_PAZAAK_PLAY;
            } else if (input->offset == DIK_UP &&
                       activeControl == playControl) {
                pending = PENDING_K1_PAZAAK_RETURN;
            }

            if (pending != 0) {
                g_pendingInput |= pending;
                input->value = 0;
            }
            return;
        }

    }
}

extern "C" void __cdecl CaptureActionBarInputK2(
    BufferedInputRecord* input,
    const void* getEventsFrame)
{
    const int inputDevice = *reinterpret_cast<const int*>(
        static_cast<const std::uint8_t*>(getEventsFrame) - 0x10);
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K2_CONFIG.keyboardDeviceIndex) &&
        input->offset == DIK_DELETE) {
        void* mainInterface = g_mainInterface;
        void* manager = mainInterface
            ? ReadPointer(mainInterface, K2_CONFIG.panelManagerOffset)
            : nullptr;
        if (!manager ||
            !IsGameplayHudActive(K2_CONFIG, manager, mainInterface)) {
            input->offset = DIK_ESCAPE;
            return;
        }
    }

    CaptureActionBarInput(K2_CONFIG, input, inputDevice);
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K2_CONFIG.keyboardDeviceIndex) &&
        (input->value & KEY_PRESSED) != 0) {
        void* mainInterface = g_mainInterface;
        void* manager = mainInterface
            ? ReadPointer(mainInterface, K2_CONFIG.panelManagerOffset)
            : nullptr;
        if (!manager) {
            return;
        }
        if (input->offset == DIK_SPACE &&
            !IsGameplayHudActive(K2_CONFIG, manager, mainInterface)) {
            g_pendingInput |= PENDING_CONTROLLER_X;
        } else if (!IsGameplayHudActive(
                       K2_CONFIG,
                       manager,
                       mainInterface) &&
                   FindK2FilterPanel(manager)) {
            if (input->offset == DIK_LEFT) {
                g_pendingInput |= PENDING_CONTROLLER_LEFT;
            } else if (input->offset == DIK_RIGHT) {
                g_pendingInput |= PENDING_CONTROLLER_RIGHT;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// KMRP native path entry points.
//
// The action bar logic above is Saul0097's and is reused unchanged: MoveFocus,
// CycleAction and the activate callback are the engine's own
// CSWGuiMainInterface functions, and rediscovering them would only risk getting
// them wrong. What KMRP replaces is how the intent arrives.
//
// His CaptureActionBarInput reads BUFFERED KEYBOARD RECORDS -- DIK_LEFT,
// DIK_RIGHT, DIK_UP, DIK_DOWN, DIK_RETURN -- which is why his path needs the
// XInput layer to synthesise those keys first. KMRP's D-pad already exists as
// controller state, so it raises the same pending bits directly and no key is
// ever synthesised.
// ---------------------------------------------------------------------------

// Refresh the on-screen prompts. Saul0097's UpdateK1ControllerPrompts does all
// of the work -- it finds the panel taking input, asks
// IsControllerInputActiveK1 whether a pad is what the player is using, and swaps
// each bound control's BORDER.FILL to the badge texture or back to nothing.
//
// It was reachable from exactly one place: DispatchMenuInputK1, which is one of
// the legacy hooks. Native mode installs none of those, so in the shipping
// configuration NO PROMPT WAS EVER DRAWN ON ANY SCREEN. The tables, the
// textures and the mode logic were all present and all unreachable.
// A buffered input record, asked whether it is a genuine keyboard press. The
// device check matters: the same buffer carries mouse and joystick records, and
// KMRP's own pad records must not be mistaken for someone reaching for the keys.
extern "C" void __cdecl KmrpNoteKeyboardK1(void* record, int inputDevice)
{
    const BufferedInputRecord* input =
        static_cast<const BufferedInputRecord*>(record);
    if (input &&
        inputDevice == *reinterpret_cast<int*>(K1_CONFIG.keyboardDeviceIndex) &&
        (input->value & KEY_PRESSED) != 0 &&
        !IsControllerGeneratedKeyK1(input->offset)) {
        MarkKeyboardMouseInputK1();
    }
}

extern "C" void __cdecl KmrpUpdatePromptsK1()
{
    UpdateK1ControllerPrompts();
}

// Mouse movement, asked through the same filter the legacy hook used: KOTOR
// recentres its own cursor, and treating that as use would hide the prompts a
// frame after showing them.
extern "C" void __cdecl KmrpNoteMouseK1(int mouseX, int mouseY)
{
    if (MouseIsBeingUsedK1(mouseX, mouseY)) {
        MarkKeyboardMouseInputK1();
    }
}

extern "C" void __cdecl KmrpActionBarApplyK1(
    void* mainInterface,
    int dx,
    int dy,
    int activate)
{
    if (!mainInterface) {
        return;
    }
    std::uint32_t bits = 0;
    if (dx < 0) {
        bits |= PENDING_LEFT;
    } else if (dx > 0) {
        bits |= PENDING_RIGHT;
    }
    if (dy < 0) {
        bits |= PENDING_UP;
    } else if (dy > 0) {
        bits |= PENDING_DOWN;
    }
    if (activate != 0) {
        bits |= PENDING_ACTIVATE;
    }
    if (bits == 0) {
        g_mainInterface = mainInterface;   // keep the pointer fresh regardless
        return;
    }
    g_pendingInput |= bits;
    UpdateActionBarControls(K1_CONFIG, mainInterface);
}

// Does a bottom-right action slot currently hold focus? Decides which of the two
// things A means -- use the selected action, or act on the world.
// Why the action bar is or is not reachable, for the diagnostic line:
//   bit 0  the gameplay HUD is the active screen
//   bit 1  one of the seven slots holds focus
//   bit 2  at least one slot is selectable, so MoveFocus has somewhere to go
extern "C" int __cdecl KmrpActionBarStateK1(void* mainInterface)
{
    void* target = mainInterface ? mainInterface : g_mainInterface;
    if (!target) {
        return 0;
    }
    int bits = 0;
    void* manager = ReadPointer(target, K1_CONFIG.panelManagerOffset);
    if (manager && IsGameplayHudActive(K1_CONFIG, manager, target)) {
        bits |= 1;
    }
    if (IsActionBarFocused(K1_CONFIG, target)) {
        bits |= 2;
    }
    ActionButtons buttons = GetActionButtons(K1_CONFIG, target);
    if (FindSelectableButton(K1_CONFIG, target, buttons, 0, 1) >= 0) {
        bits |= 4;
    }
    return bits;
}

extern "C" int __cdecl KmrpActionBarFocusedK1(void* mainInterface)
{
    // No fallback to g_mainInterface. That global keeps pointing at an
    // interface after the screen it belonged to has gone, and answering a
    // question about a dead object is worse than declining to answer.
    return (mainInterface && IsActionBarFocused(K1_CONFIG, mainInterface)) ? 1 : 0;
}

extern "C" void __cdecl UpdateActionBarControlsK1(void* mainInterface)
{
    UpdateActionBarControls(K1_CONFIG, mainInterface);

    if ((g_pendingInput & PENDING_CONTEXT_CANCEL) == 0) {
        return;
    }

    g_pendingInput &= ~PENDING_CONTEXT_CANCEL;
    void* manager = mainInterface
        ? ReadPointer(mainInterface, K1_CONFIG.panelManagerOffset)
        : nullptr;
    if (!manager ||
        !IsGameplayHudActive(K1_CONFIG, manager, mainInterface)) {
        return;
    }

    reinterpret_cast<CancelLastActionFn>(K1_CONFIG.cancelLastAction)(
        mainInterface);

    // Delete also drops keyboard focus off the action menu and hotbar. MoveFocus
    // treats those seven buttons as one wrap-around ring, so before this there was
    // no keyboard way out of them - only the mouse-move hook ever cleared focus.
    // One-way by construction: once focus is gone there is nothing left to clear,
    // and Left/Right brings it back through MoveFocus's activeIndex < 0 seed.
    // Read the active control after the cancel above, in case it moved focus.
    ActionButtons buttons = GetActionButtons(K1_CONFIG, mainInterface);
    void* activeControl = ReadPointer(
        mainInterface,
        K1_CONFIG.panelActiveControlOffset);
    if (FindButton(K1_CONFIG, buttons, activeControl) >= 0) {
        reinterpret_cast<SetActiveControlFn>(K1_CONFIG.setActiveControl)(
            mainInterface,
            nullptr,
            1);
    }
}

extern "C" void __cdecl UpdateActionBarControlsK2(void* mainInterface)
{
    UpdateActionBarControls(K2_CONFIG, mainInterface);
}

extern "C" void __cdecl CancelMovieOnSpaceK1(
    std::uint32_t message,
    std::uint32_t key)
{
    if (message != WM_KEYDOWN_MESSAGE || key != VK_SPACE_KEY) {
        return;
    }

    void* moviePlayer =
        *reinterpret_cast<void**>(K1_MOVIE_PLAYER_POINTER);
    if (moviePlayer) {
        reinterpret_cast<CancelMovieFn>(K1_CANCEL_MOVIE)(
            moviePlayer,
            0,
            0);
    }
}

extern "C" void __cdecl PollMovieControllerK1(void* moviePlayer)
{
    if (moviePlayer && ConsumeMovieSkipK1()) {
        reinterpret_cast<CancelMovieFn>(K1_CANCEL_MOVIE)(
            moviePlayer,
            0,
            0);
    }
}

extern "C" void __cdecl MapMovieDeleteToEscapeK2(void* movieWindowFrame)
{
    if (!movieWindowFrame) {
        return;
    }

    std::uint8_t* frame = static_cast<std::uint8_t*>(movieWindowFrame);
    std::uint32_t* message = reinterpret_cast<std::uint32_t*>(frame + 0x0C);
    std::uint32_t* key = reinterpret_cast<std::uint32_t*>(frame + 0x10);
    if (*message == WM_KEYDOWN_MESSAGE && *key == VK_DELETE_KEY) {
        *key = VK_ESCAPE_KEY;
    }
}

// Declines the focus move the Abilities tab handler makes for itself.
//
// Read out of the game at 0x006AD917, after a breakpoint caught it live. The
// handler does NOT move focus once, it does it twice:
//
//     006AD919  push ebx              ; flag  = 0
//     006AD91A  push ebx              ; control = NULL
//     006AD91D  call [eax+8]          ; SetActiveControl(panel, NULL)  -- clears
//     006AD923  lea eax, [esi+0x30DC] ; the ability listbox
//     006AD92C  call [edx+8]          ; SetActiveControl(panel, listbox)
//
// The clear is why three earlier attempts failed. Each of them asked "is the
// panel's current active control a tab?", which is true on the first call and
// FALSE on the second, because the first call already nulled it. The first call
// was also skipped outright by an `if (!control) return 0;` guard. So both moves
// escaped, and whatever put focus back afterwards did so a frame late -- the
// visible drop into the list, and the race that let a fast Right press land in
// the list instead of on the tabs.
//
// So the tab is remembered when focus ARRIVES on it, and the guard holds until
// the player presses a direction. Nothing is read back from the panel, so the
// handler nulling its own field cannot disarm it.
//
// Hooked at 0x0040A638 with EDI = panel and ESI = control; returning non-zero
// sends the wrapper to 0x0040A678, the function's own pop/pop/ret, so the store
// at 0x0040A64E never runs and no wrong state is ever drawn.
extern "C" int __cdecl OnSetActiveControlK1(void* panel, void* control)
{
    if (!panel || !IsControllerInputActiveK1()) {
        return 0;
    }
    SettingsStripExit exit = GetK1SettingsStripExit(panel);
    if (exit.headerCount <= 0) {
        return 0;                       // only screens that have a tab row
    }

    // Focus arriving ON a tab is always allowed, and is what arms the guard.
    // Remembering the tab here rather than reading the panel's current active
    // control is the whole fix: see below for why reading it does not work.
    if (control && IsK1HeaderControl(panel, exit, control)) {
        g_tabFocusPanel = panel;
        g_tabFocusControl = control;
        return 0;
    }

    if (panel != g_tabFocusPanel || !g_tabFocusControl) {
        return 0;
    }

    // Let the player leave whenever the player is the one leaving. Every
    // direction and every A press is injected by this module and stamped in
    // g_recentInjectedUntil, so the stamps say which was pressed most recently.
    // A newer direction means a deliberate move, and it disarms the guard.
    const DWORD activate = LastInjectedDeadlineK1(DIK_RETURN);
    const DWORD directions[] = {
        LastInjectedDeadlineK1(DIK_UP),
        LastInjectedDeadlineK1(DIK_DOWN),
        LastInjectedDeadlineK1(DIK_LEFT),
        LastInjectedDeadlineK1(DIK_RIGHT),
    };
    for (int i = 0; i < 4; ++i) {
        // Signed compare, so this survives GetTickCount's wrap.
        if (activate == 0 || static_cast<int>(directions[i] - activate) >= 0) {
            g_tabFocusPanel = nullptr;
            g_tabFocusControl = nullptr;
            return 0;
        }
    }
    return 1;
}

extern "C" void __cdecl DispatchMenuInputK1(void* clientApp)
{
    // Poll here because this hook sits at the entry of
    // CClientExoAppInternal::ProcessInput, which runs once per frame in every
    // context: gameplay, menus, main menu and movies. It has to go above the
    // early return below, which only guards the queued menu work and would
    // otherwise skip the poll on most frames.
    PollXInputK1();
    UpdateK1ControllerPrompts();
    // clientApp is CClientExoAppInternal, straight from ECX at the ProcessInput
    // entry this hook sits on, which is the exact this the mouse mask lives on.
    UpdateK1CursorState(clientApp);

    // Above the early return, since the scroll count lives outside
    // g_pendingInput and would otherwise be stranded whenever no menu bit is
    // set - which is most frames a description pane is actually being read.
    if (g_pendingDescScroll != 0) {
        int scroll = g_pendingDescScroll;
        g_pendingDescScroll = 0;

        // Resolved again here rather than captured at key time, matching the
        // settings path: a panel torn down in between must not leave us
        // dispatching into a freed control.
        void* scrollManager = nullptr;
        void* scrollPanel = FindK1MenuPanelForInput(&scrollManager);
        void* listbox = scrollPanel
            ? FindK1DescriptionListbox(scrollPanel)
            : nullptr;
        if (listbox) {
            int event = scroll < 0
                ? K1_GUI_SCROLL_UP_ARROW_EVENT
                : K1_GUI_SCROLL_DOWN_ARROW_EVENT;
            int notches = scroll < 0 ? -scroll : scroll;
            for (int i = 0; i < notches; ++i) {
                DispatchControlInput(listbox, event);
            }
        }
    }

    if (!clientApp ||
        (g_pendingInput & PENDING_K1_MENU_INPUT) == 0) {
        return;
    }

    std::uint32_t pending = g_pendingInput & PENDING_K1_MENU_INPUT;
    g_pendingInput &= ~PENDING_K1_MENU_INPUT;
    void* manager = nullptr;
    void* panel = FindK1MenuPanelForInput(&manager);
    if (!panel) {
        return;
    }

    if ((pending & PENDING_K1_SETTINGS_NAV) != 0) {
        std::uint8_t mode = g_pendingSettingsNav;
        void* target = g_pendingSettingsTarget;
        int event = g_pendingSettingsEvent;
        g_pendingSettingsNav = 0;
        g_pendingSettingsTarget = nullptr;
        g_pendingSettingsEvent = 0;

        if (mode == SETTINGS_NAV_CYCLE) {
            // Fire the arrow without focusing it. Only the value control between
            // the arrows is meant to hold focus, and an arrow has no vertical
            // links, so moving focus there strands it.
            if (target && IsK1SelectableControl(target) && event != 0) {
                DispatchControlInput(target, event);
            }
        } else if (mode != 0) {
            // Resolve against the panel found on this thread rather than a
            // pointer captured earlier, so a panel torn down in between can't
            // leave us dereferencing a stale control.
            SettingsStripExit exit = GetK1SettingsStripExit(panel);
            if (exit.stripCount != 0) {
                void* activeControl = ReadPointer(
                    panel,
                    K1_CONFIG.panelActiveControlOffset);
                int stripIndex = FindK1SettingsStripIndex(
                    panel,
                    activeControl,
                    exit);
                void* resolved = nullptr;
                switch (mode) {
                case SETTINGS_NAV_ENTER_STRIP:
                    resolved = FindK1SelectableStripButton(panel, exit, 0, 1);
                    break;
                case SETTINGS_NAV_RETURN_COLUMN:
                    resolved = FindK1SettingsColumnTail(panel, exit);
                    break;
                case SETTINGS_NAV_STRIP_PREV:
                    if (stripIndex > 0) {
                        resolved = FindK1SelectableStripButton(
                            panel, exit, stripIndex - 1, -1);
                    }
                    break;
                case SETTINGS_NAV_STRIP_NEXT:
                    if (stripIndex >= 0) {
                        resolved = FindK1SelectableStripButton(
                            panel, exit, stripIndex + 1, 1);
                    }
                    break;
                case SETTINGS_NAV_HEADER:
                    resolved = FindK1HeaderTarget(panel, exit);
                    break;
                case SETTINGS_NAV_HEADER_PREV:
                case SETTINGS_NAV_HEADER_NEXT: {
                    int headerIndex = FindK1HeaderIndex(
                        panel,
                        activeControl,
                        exit);
                    int step = mode == SETTINGS_NAV_HEADER_NEXT ? 1 : -1;
                    for (int i = headerIndex + step;
                         headerIndex >= 0 && i >= 0 && i < exit.headerCount;
                         i += step) {
                        void* candidate = OffsetPointer(
                            panel,
                            exit.header[i]);
                        if (IsK1SettingsNavTarget(panel, candidate)) {
                            resolved = candidate;
                            break;
                        }
                    }
                    break;
                }
                case SETTINGS_NAV_COLUMN_UP:
                case SETTINGS_NAV_COLUMN_DOWN: {
                    // columnTail runs bottom-up, so climbing means a higher
                    // index and descending means a lower one.
                    int tailIndex = FindK1SettingsTailIndex(
                        panel,
                        activeControl,
                        exit);
                    resolved = mode == SETTINGS_NAV_COLUMN_UP
                        ? FindK1TailUpTarget(panel, exit, tailIndex)
                        : FindK1TailStepTarget(
                              panel,
                              exit,
                              tailIndex,
                              -K1SettingsTailRowWidth(exit));
                    break;
                }
                default:
                    break;
                }
                if (resolved && IsK1SettingsNavTarget(panel, resolved)) {
                    reinterpret_cast<SetActiveControlFn>(
                        K1_CONFIG.setActiveControl)(panel, resolved, 1);
                }
            }
        }
        pending &= ~PENDING_K1_SETTINGS_NAV;
        if (pending == 0) {
            return;
        }
    }

#if 0   // dead: the only consumer of the menu action map (see the note at its
        // definition). Nothing ever raises PENDING_K1_MENU_ACTION, so this block
        // was unreachable.
    if ((pending & PENDING_K1_MENU_ACTION) != 0) {
        MenuActionSlot slot = static_cast<MenuActionSlot>(
            g_pendingMenuAction);
        g_pendingMenuAction = 0;
        ResolvedMenuAction action = ResolveK1MenuAction(panel, slot);
        if (action.control && IsK1SelectableControl(action.control)) {
            if (action.callback) {
                reinterpret_cast<ActionCallbackFn>(action.callback)(
                    panel, action.control);
            } else {
                reinterpret_cast<SetActiveControlFn>(
                    K1_CONFIG.setActiveControl)(panel, action.control, 1);
                DispatchControlInput(action.control, K1_GUI_A_BUTTON_EVENT);
            }
        }
        pending &= ~PENDING_K1_MENU_ACTION;
        if (pending == 0) {
            return;
        }
    }
#endif  // 0

    if ((pending & PENDING_K1_GENERIC_BUTTON) != 0) {
        DispatchPanelInput(panel, g_pendingGenericButtonEvent);
        pending &= ~PENDING_K1_GENERIC_BUTTON;
        if (pending == 0) {
            return;
        }
    }

    bool isJournal =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_JOURNAL_PANEL_VTABLE;
    bool isPazaak =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_PAZAAK_SETUP_PANEL_VTABLE;
    bool isPazaakGame =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_PAZAAK_GAME_PANEL_VTABLE;
    bool isPartySelect =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_PARTY_SELECT_PANEL_VTABLE;
    bool isClassSelect =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_CLASS_SELECT_PANEL_VTABLE;
    bool isFeats =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_FEATS_PANEL_VTABLE;
    bool isPowers =
        *reinterpret_cast<std::uintptr_t*>(panel) ==
        K1_POWERS_PANEL_VTABLE;
    if (isPowers) {
        return;
    }
    if (isFeats) {
        return;
    }
    if (isPartySelect) {
        void* target = nullptr;
        if ((pending & PENDING_K1_PARTY_BUTTON_ROW) != 0) {
            target = OffsetPointer(
                panel,
                g_pendingK1PartyTargetOffset >= 0
                    ? g_pendingK1PartyTargetOffset
                    : K1_PARTY_DONE_OFFSET);
            g_pendingK1PartyTargetOffset = -1;
        } else if ((pending & PENDING_K1_PARTY_GRID_RETURN) != 0) {
            target = OffsetPointer(
                panel,
                K1_PARTY_GRID_OFFSET +
                    (K1_PARTY_GRID_COUNT - 1) *
                        K1_PARTY_GRID_STRIDE);
        }
        if (target) {
            reinterpret_cast<SetActiveControlFn>(
                K1_CONFIG.setActiveControl)(panel, target, 1);
        }
        return;
    }
    if (isClassSelect) {
        void* activeControl = ReadPointer(
            panel,
            K1_CONFIG.panelActiveControlOffset);
        int gridIndex = FindK1ClassSelectIndex(panel, activeControl);
        if (gridIndex < 0) {
            return;
        }

        int targetIndex = gridIndex;
        if ((pending & PENDING_K1_CLASS_SELECT_LEFT) != 0) {
            targetIndex = gridIndex - 1;
        } else if ((pending & PENDING_K1_CLASS_SELECT_RIGHT) != 0) {
            targetIndex = gridIndex + 1;
        }

        if (targetIndex != gridIndex &&
            targetIndex >= 0 &&
            targetIndex < K1_CLASS_SELECT_COUNT) {
            void* target = OffsetPointer(
                panel,
                K1_CLASS_SELECT_OFFSET +
                    targetIndex * K1_CLASS_SELECT_STRIDE);
            if (IsK1SelectableControl(target)) {
                reinterpret_cast<SetActiveControlFn>(
                    K1_CONFIG.setActiveControl)(panel, target, 1);
            }
        }
        return;
    }
    if (isPazaakGame) {
        void* activeControl = ReadPointer(
            panel,
            K1_CONFIG.panelActiveControlOffset);
        int handIndex =
            FindK1PazaakHandIndex(panel, activeControl);
        int flipIndex =
            FindK1PazaakFlipIndex(panel, activeControl);
        void* target = nullptr;

        if ((pending & PENDING_K1_PAZAAK_GAME_FLIP_DOWN) != 0 &&
            handIndex >= 0) {
            target = OffsetPointer(
                panel,
                K1_PAZAAK_FLIP_OFFSET +
                    handIndex * K1_PAZAAK_FLIP_STRIDE);
        } else if ((pending & PENDING_K1_PAZAAK_GAME_FLIP_UP) != 0 &&
                   flipIndex >= 0) {
            target = OffsetPointer(
                panel,
                K1_PAZAAK_HAND_OFFSET +
                    flipIndex * K1_PAZAAK_CARD_STRIDE);
        } else if ((pending & PENDING_K1_PAZAAK_GAME_LEFT) != 0) {
            int startIndex = handIndex >= 0
                ? handIndex - 1
                : K1_PAZAAK_HAND_COUNT - 1;
            for (int i = startIndex; i >= 0; --i) {
                void* card = OffsetPointer(
                    panel,
                    K1_PAZAAK_HAND_OFFSET +
                        i * K1_PAZAAK_CARD_STRIDE);
                if (IsK1SelectableControl(card)) {
                    target = card;
                    break;
                }
            }
        } else if ((pending & PENDING_K1_PAZAAK_GAME_RIGHT) != 0) {
            for (int i = handIndex + 1;
                 i < K1_PAZAAK_HAND_COUNT;
                 ++i) {
                void* card = OffsetPointer(
                    panel,
                    K1_PAZAAK_HAND_OFFSET +
                        i * K1_PAZAAK_CARD_STRIDE);
                if (IsK1SelectableControl(card)) {
                    target = card;
                    break;
                }
            }
            if (!target) {
                void* endTurn = OffsetPointer(
                    panel,
                    K1_PAZAAK_END_TURN_OFFSET);
                if (IsK1SelectableControl(endTurn)) {
                    target = endTurn;
                }
            }
        }

        if (target) {
            reinterpret_cast<SetActiveControlFn>(
                K1_CONFIG.setActiveControl)(panel, target, 1);
        }
        if ((pending & PENDING_K1_PAZAAK_GAME_PLAY_CARD) != 0 &&
            handIndex >= 0 &&
            IsK1SelectableControl(activeControl)) {
            reinterpret_cast<K1PazaakPlayCardFn>(
                K1_PAZAAK_PLAY_CARD_CALLBACK)(
                    panel,
                    activeControl);
        }
        if ((pending & PENDING_K1_PAZAAK_GAME_FLIP_CARD) != 0 &&
            flipIndex >= 0 &&
            IsK1SelectableControl(activeControl)) {
            reinterpret_cast<K1PazaakFlipCardFn>(
                K1_PAZAAK_FLIP_CARD_CALLBACK)(
                    panel,
                    activeControl);
        }
        return;
    }
    if (isPazaak) {
        if ((pending & PENDING_K1_PAZAAK_SWITCH_GRID) != 0) {
            void* activeControl = ReadPointer(
                panel,
                K1_CONFIG.panelActiveControlOffset);
            int availableIndex = FindK1PazaakControlIndex(
                panel,
                activeControl,
                K1_PAZAAK_AVAILABLE_OFFSET,
                K1_PAZAAK_AVAILABLE_COUNT);
            int chosenIndex = FindK1PazaakControlIndex(
                panel,
                activeControl,
                K1_PAZAAK_CHOSEN_OFFSET,
                K1_PAZAAK_CHOSEN_COUNT);
            void* target = nullptr;
            if (availableIndex >= 0) {
                int row = availableIndex % K1_PAZAAK_AVAILABLE_ROWS;
                int chosenRows =
                    K1_PAZAAK_CHOSEN_COUNT /
                    K1_PAZAAK_CHOSEN_COLUMNS;
                int targetIndex =
                    (row < chosenRows ? row : chosenRows - 1) *
                    K1_PAZAAK_CHOSEN_COLUMNS;
                target = OffsetPointer(
                    panel,
                    K1_PAZAAK_CHOSEN_OFFSET +
                        targetIndex * K1_PAZAAK_CARD_STRIDE);
            } else if (chosenIndex >= 0) {
                int row = chosenIndex / K1_PAZAAK_CHOSEN_COLUMNS;
                int targetIndex =
                    2 * K1_PAZAAK_AVAILABLE_ROWS + row;
                target = OffsetPointer(
                    panel,
                    K1_PAZAAK_AVAILABLE_OFFSET +
                        targetIndex * K1_PAZAAK_CARD_STRIDE);
            }
            if (target) {
                reinterpret_cast<SetActiveControlFn>(
                    K1_CONFIG.setActiveControl)(panel, target, 1);
            }
        }
        if ((pending & PENDING_K1_PAZAAK_PLAY) != 0) {
            reinterpret_cast<SetActiveControlFn>(
                K1_CONFIG.setActiveControl)(
                panel,
                OffsetPointer(panel, K1_PAZAAK_PLAY_OFFSET),
                1);
        }
        if ((pending & PENDING_K1_PAZAAK_RETURN) != 0) {
            void* target = g_k1PazaakReturnControl;
            if (!IsK1PazaakGridControl(panel, target)) {
                target =
                    OffsetPointer(panel, K1_PAZAAK_AVAILABLE_OFFSET);
            }
            reinterpret_cast<SetActiveControlFn>(
                K1_CONFIG.setActiveControl)(panel, target, 1);
        }
        if ((pending & PENDING_K1_PAZAAK_INITIAL_FOCUS) != 0) {
            reinterpret_cast<SetActiveControlFn>(
                K1_CONFIG.setActiveControl)(
                panel,
                OffsetPointer(panel, K1_PAZAAK_AVAILABLE_OFFSET),
                1);
        }
        return;
    }

    if ((pending & PENDING_CONTROLLER_X) != 0 && !isJournal) {
        DispatchPanelInput(panel, K1_GUI_CONTROLLER_X_EVENT);
    }
}

extern "C" void __cdecl DispatchContextCancelK2(void* clientApp)
{
    if (!clientApp ||
        (g_pendingInput & PENDING_CONTEXT_INPUT) == 0) {
        return;
    }

    std::uint32_t pending = g_pendingInput & PENDING_CONTEXT_INPUT;
    g_pendingInput &= ~PENDING_CONTEXT_INPUT;
    void* mainInterface = g_mainInterface;
    void* manager = mainInterface
        ? ReadPointer(mainInterface, K2_CONFIG.panelManagerOffset)
        : nullptr;
    if ((pending & PENDING_CONTROLLER_X) != 0 && manager) {
        reinterpret_cast<HandleInputEventFn>(K2_CONFIG.handleGuiInputEvent)(
            manager,
            K2_GUI_CONTROLLER_X_EVENT,
            1);
    }
    void* filterPanel = manager ? FindK2FilterPanel(manager) : nullptr;
    if ((pending & PENDING_CONTROLLER_LEFT) != 0 && filterPanel) {
        DispatchPanelInput(filterPanel, K2_GUI_CONTROLLER_LEFT_EVENT);
    }
    if ((pending & PENDING_CONTROLLER_RIGHT) != 0 && filterPanel) {
        DispatchPanelInput(filterPanel, K2_GUI_CONTROLLER_RIGHT_EVENT);
    }
    if ((pending & PENDING_CONTEXT_CANCEL) != 0 &&
        manager &&
        IsGameplayHudActive(K2_CONFIG, manager, mainInterface)) {
        reinterpret_cast<CancelLastActionFn>(K2_CONFIG.cancelLastAction)(
            mainInterface);
    } else if ((pending & PENDING_CONTEXT_CANCEL) != 0 && manager) {
        reinterpret_cast<HandleInputEventFn>(K2_CONFIG.handleGuiInputEvent)(
            manager,
            DIK_ESCAPE,
            1);
    }
}

extern "C" void __cdecl ClearActionBarControlsK2(void* mainInterface)
{
    if (g_mainInterface == mainInterface) {
        g_mainInterface = nullptr;
        g_pendingInput = 0;
    }
}

extern "C" void __cdecl ClearActionBarControlsK1(void* mainInterface)
{
    if (g_mainInterface == mainInterface) {
        g_mainInterface = nullptr;
        g_pendingInput = 0;
        g_k1PazaakReturnControl = nullptr;
        g_k1SuppressPazaakFlipEnterRelease = false;
        g_pendingSettingsNav = 0;
        g_pendingSettingsTarget = nullptr;
        g_pendingSettingsEvent = 0;
    }
}

// A hand on the mouse produces a stream of moves; KOTOR's own cursor recentring
// during scene and menu transitions produces a single jump. Marking on every
// event made the two indistinguishable, which is why prompt artwork used to be
// tied to "a pad is connected" rather than "a pad is what you are using" -- the
// artwork vanished on every transition.
//
// Requiring several distinct positions, and real accumulated distance, inside a
// short window separates them without needing to know where the engine recentres
// to. Isolated jumps never reach the threshold; actually moving the mouse
// reaches it almost immediately.
namespace {
constexpr DWORD MOUSE_USE_WINDOW_MS = 250;
constexpr int MOUSE_USE_DISTANCE_PX = 24;
constexpr int MOUSE_USE_MIN_EVENTS = 2;

int g_lastMouseX = 0x7FFFFFFF;
int g_lastMouseY = 0x7FFFFFFF;
DWORD g_mouseWindowStart = 0;
int g_mouseWindowDistance = 0;
int g_mouseWindowEvents = 0;

// True when this move is part of real mouse use rather than an engine recentre.
bool MouseIsBeingUsedK1(int mouseX, int mouseY)
{
    if (g_movingCursorOurselves) {
        // The module moved the pointer, not a hand. Take the new position as the
        // baseline so the next real movement is measured from where the cursor
        // actually is, but report nothing.
        g_lastMouseX = mouseX;
        g_lastMouseY = mouseY;
        return false;
    }

    const DWORD now = GetTickCount();
    if (g_lastMouseX == 0x7FFFFFFF) {
        g_lastMouseX = mouseX;
        g_lastMouseY = mouseY;
        g_mouseWindowStart = now;
        return false;
    }

    int dx = mouseX - g_lastMouseX;
    int dy = mouseY - g_lastMouseY;
    g_lastMouseX = mouseX;
    g_lastMouseY = mouseY;
    if (dx == 0 && dy == 0) {
        return false;
    }

    if (now - g_mouseWindowStart > MOUSE_USE_WINDOW_MS) {
        g_mouseWindowStart = now;
        g_mouseWindowDistance = 0;
        g_mouseWindowEvents = 0;
    }
    g_mouseWindowDistance += (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy);
    ++g_mouseWindowEvents;
    return g_mouseWindowEvents >= MOUSE_USE_MIN_EVENTS &&
           g_mouseWindowDistance >= MOUSE_USE_DISTANCE_PX;
}
}  // namespace

extern "C" void __cdecl CancelActionBarKeyboardFocusOnMouseMoveK1(
    void* manager,
    int mouseX,
    int mouseY)
{
    if (MouseIsBeingUsedK1(mouseX, mouseY)) {
        MarkKeyboardMouseInputK1();
    }
    void* mainInterface = g_mainInterface;
    if (!mainInterface ||
        ReadPointer(mainInterface, K1_CONFIG.panelManagerOffset) != manager) {
        return;
    }

    void* hoveredPanel = nullptr;
    void* hoveredControl = nullptr;
    reinterpret_cast<K1GetControlAtFn>(K1_CONFIG.getControlAt)(
        manager,
        mouseX,
        mouseY,
        &hoveredPanel,
        &hoveredControl,
        0);
    ClearActionBarKeyboardFocus(
        K1_CONFIG,
        hoveredPanel,
        hoveredControl);
}

extern "C" void __cdecl CancelActionBarKeyboardFocusOnMouseMoveK2(
    void* inputInternal)
{
    void* mainInterface = g_mainInterface;
    if (!mainInterface || !inputInternal) {
        return;
    }

    int mouseX = ReadInt(inputInternal, 0x3E4);
    int mouseY = ReadInt(mainInterface, 0x10) -
        ReadInt(inputInternal, 0x3E8);
    void* hoveredControl = reinterpret_cast<K2GetControlAtFn>(
        K2_CONFIG.getControlAt)(mainInterface, mouseX, mouseY);
    ClearActionBarKeyboardFocus(
        K2_CONFIG,
        mainInterface,
        hoveredControl);
}
