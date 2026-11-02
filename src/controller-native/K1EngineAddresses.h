#pragma once
// Every address of the game that more than one file here uses (audit S-8), each under one name
// and written only here; Test-EngineAddresses holds the files to that. An address only one file
// uses stays beside its code. The Mac's addresses are its own.
#include <cstdint>

// Code.
constexpr std::uintptr_t K1_GAME_TEXT_START       = 0x00401000;   // the first byte of .text
constexpr std::uintptr_t K1_CANCEL_MOVIE          = 0x00404C40;   // CExoMoviePlayerInternal::SetSkip
constexpr std::uintptr_t K1_SET_ACTIVE_CONTROL    = 0x0040A630;   // CSWGuiPanel::SetActiveControl(control, playSound)
constexpr std::uintptr_t K1_BORDER_SET_FILL_IMAGE = 0x00414C00;   // CSWGuiBorderParams::SetFillImage(name, 1)
constexpr std::uintptr_t K1_TEXT_SET_COLOUR       = 0x00414E10;   // CSWGuiTextParams::SetColor(Vector*)
constexpr std::uintptr_t K1_TEXT_EXTENT           = 0x00414F10;   // CSWGuiText::GetIdealWidthAndHeight(CSWGuiExtent*)
constexpr std::uintptr_t K1_TEXT_SET_TEXT         = 0x00415E00;   // CSWGuiTextParams::SetText(CExoString*)
constexpr std::uintptr_t K1_TEXT_SET_BASE_FONT    = 0x00415DD0;   // CSWGuiTextParams::SetBaseFont(CResRef*)
constexpr std::uintptr_t K1_CONTROL_HANDLE_INPUT  = 0x00418750;   // CSWGuiControl: enter/exit, then the table
constexpr std::uintptr_t K1_GUI_LABEL_CTOR        = 0x0041ACD0;   // CSWGuiLabel::CSWGuiLabel
constexpr std::uintptr_t K1_SLIDER_DISPATCHER     = 0x0041ADF0;   // CSWGuiSlider::HandleInputEvent
constexpr std::uintptr_t K1_LISTBOX_DISPATCHER    = 0x0041CE20;   // CSWGuiListBox::HandleInputEvent
constexpr std::uintptr_t K1_LOAD_TEXTURE_REF      = 0x00423A60;   // AurTextureGetReference
constexpr std::uintptr_t K1_GET_PARTY_TABLE       = 0x004AEE70;   // CServerExoApp, ret 0
constexpr std::uintptr_t K1_EXOSTRING_CTOR        = 0x005E5A90;   // CExoString::CExoString(const char*)
constexpr std::uintptr_t K1_EXOSTRING_DTOR        = 0x005E5C20;   // CExoString::~CExoString
constexpr std::uintptr_t K1_GET_PLAYER_CREATURE   = 0x005ED540;   // CClientExoApp::GetPlayerCreature
constexpr std::uintptr_t K1_GET_IN_GAME_GUI       = 0x005ED690;   // CClientExoApp::GetInGameGui
constexpr std::uintptr_t K1_GET_GUI_STRING        = 0x005EDEB0;   // CClientExoApp::GetGUIString(CExoString*, strref)
constexpr std::uintptr_t K1_GET_SERVER_CREATURE   = 0x0060FB20;   // CSWCCreature::GetServerCreature
constexpr std::uintptr_t K1_OPERATOR_NEW          = 0x006FA7E6;

// Immediates in the game's code, which KMRP's Icon Size slider rewrites.
constexpr std::uintptr_t K1_SKILL_ENTRY_HEIGHT    = 0x006ACB20;   // a Skills tab row's height
constexpr std::uintptr_t K1_SKILL_FLOW_HEIGHT     = 0x006CD8D9;   // a feat or power chart row's height

// Vtables.
constexpr std::uintptr_t K1_GUI_LABEL_VTABLE                       = 0x0073E5B8;
constexpr std::uintptr_t K1_GUI_BUTTON_VTABLE                      = 0x0073E658;
constexpr std::uintptr_t K1_GUI_BUTTON_TOGGLE_VTABLE               = 0x0073EB88;
constexpr std::uintptr_t K1_INGAME_MENU_PANEL_VTABLE               = 0x00750148;
constexpr std::uintptr_t K1_MAIN_MENU_PANEL_VTABLE                 = 0x00752F70;
constexpr std::uintptr_t K1_PAZAAK_SETUP_PANEL_VTABLE              = 0x007532E8;
constexpr std::uintptr_t K1_PAZAAK_GAME_PANEL_VTABLE               = 0x00753358;
constexpr std::uintptr_t K1_MAIN_INTERFACE_VTABLE                  = 0x00753F50;   // CSWGuiMainInterface
constexpr std::uintptr_t K1_MAP_PANEL_VTABLE                       = 0x00754830;   // CSWGuiInGameMap
constexpr std::uintptr_t K1_ABILITIES_PANEL_VTABLE                 = 0x00755E50;
constexpr std::uintptr_t K1_CHARACTER_PANEL_VTABLE                 = 0x00756100;
constexpr std::uintptr_t K1_INVENTORY_PANEL_VTABLE                 = 0x007564E0;
constexpr std::uintptr_t K1_EQUIP_PANEL_VTABLE                     = 0x007569A0;
constexpr std::uintptr_t K1_PARTY_RECORD_VTABLE                    = 0x00756BB8;
constexpr std::uintptr_t K1_PARTY_SELECT_PANEL_VTABLE              = 0x00756D28;
constexpr std::uintptr_t K1_SKILL_INFO_PANEL_VTABLE                = 0x00757940;
constexpr std::uintptr_t K1_CLASS_SELECT_PANEL_VTABLE              = 0x00758020;
constexpr std::uintptr_t K1_OPTIONS_FEEDBACK_PANEL_VTABLE          = 0x007581E8;
constexpr std::uintptr_t K1_OPTIONS_GRAPHICS_ADVANCED_PANEL_VTABLE = 0x007584A0;
constexpr std::uintptr_t K1_OPTIONS_SOUND_ADVANCED_PANEL_VTABLE    = 0x00758550;
constexpr std::uintptr_t K1_OPTIONS_MOUSE_PANEL_VTABLE             = 0x007585F8;
constexpr std::uintptr_t K1_OPTIONS_GRAPHICS_PANEL_VTABLE          = 0x007586F8;
constexpr std::uintptr_t K1_OPTIONS_SOUND_PANEL_VTABLE             = 0x007587C0;
constexpr std::uintptr_t K1_INGAME_GAMEPLAY_PANEL_VTABLE           = 0x00758E00;
constexpr std::uintptr_t K1_INGAME_AUTOPAUSE_PANEL_VTABLE          = 0x00758EE0;
constexpr std::uintptr_t K1_KEY_MAPPINGS_PANEL_VTABLE              = 0x00759358;
constexpr std::uintptr_t K1_CUSTOM_CHARGEN_PANEL_VTABLE            = 0x007595E0;
constexpr std::uintptr_t K1_QUICK_CHARGEN_PANEL_VTABLE             = 0x00759668;

// Variables.
constexpr std::uintptr_t K1_SCREEN_WIDTH        = 0x0078D1D4;
constexpr std::uintptr_t K1_SCREEN_HEIGHT       = 0x0078D1D8;
constexpr std::uintptr_t K1_GL_SGIS_MIPMAP_BIT  = 0x0078E4CC;   // glcaps.h: the extension's bits in the mask,
constexpr std::uintptr_t K1_GL_ATI_MIPMAP_BIT   = 0x0078E4D0;   // two words each
constexpr std::uintptr_t K1_GL_MIPMAP_ANSWER    = 0x0078E538;   // the engine's cached answer
constexpr std::uintptr_t K1_GL_EXTENSION_MASK   = 0x007BB85C;
constexpr std::uintptr_t K1_G_DELTA_T           = 0x0078E574;   // float: this frame's seconds, what UpdateCamera is passed
constexpr std::uintptr_t K1_EXO_INPUT           = 0x007A39E4;   // CExoInput*, null while there is none
constexpr std::uintptr_t K1_GUI_MANAGER_PTR     = 0x007A39F4;
constexpr std::uintptr_t K1_CLIENT_EXO_APP_ROOT = 0x007A39FC;   // [[it] + 4] is CClientExoApp
constexpr std::uintptr_t K1_TEXTURE_LIST        = 0x007A4798;
constexpr std::uintptr_t K1_TEXTURE_COUNT       = 0x007A479C;
