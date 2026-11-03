/*
  KMRP for macOS, the controller patch: the Xbox-style HUD.

  The Mac port of src/controller-native/K1XboxHud.cpp, which says why each thing is done and
  what the maintainer saw that led to it; docs/controller-xbox-hud.md is the feature's
  reference. While the pad is the device in use, the game's own HUD is laid out the way the Xbox
  game's mi8x6.gui lays out its own: tools/build_xbox_hud.py --mac writes where each control
  goes and what it wears (xbox_hud_layout.inc, the Windows table with this executable's
  offsets), and this file applies that to the live controls and takes it off again for the mouse
  and keyboard. What a layout cannot say is done before every draw: the target's name, bar and
  slots pinned to the screen (CSWGuiTargetActionMenu draws in a viewport of its own that follows
  the target), the slot with the focus drawn large, the action box as tall as its text, the
  combat-mode strip and line, the pause notice as one line, and the party's bars drawn curved.

  Hooks, as on Windows. KmrpXboxHud is at the entry of the HUD's map drawing (0x100237848;
  Windows CSWGuiMainInterface::DrawMap, 0x0068AB10), which CSWGuiMainInterface::Draw
  (0x100235E44) calls after its own updating (the portraits at 0x1002361B8, UpdateIndicator, the
  six personal slots' 0x10022FCC2) and immediately before CSWGuiPanel::Draw. KmrpXboxHudBars is
  at the entry of the target menu's Draw (0x100230EEE; Windows 0x00685ED0), the call right after
  CSWGuiPanel::Draw. Both sites were read from the decompiled Draw on 2026-10-07.
  KmrpXboxHudLists (0x100231179) is inside CSWGuiTargetActionMenu::PopulateMenus, where the row's
  lists are made; KmrpXboxHudPauseReason and KmrpXboxHudPauseReasonDone are at the two ends of
  CSWGuiInGamePause::SetPauseReason. Each says below what it does.

  Every offset and address below was read from the Mac executable (KOTOR_Exe 1.4.0) on
  2026-10-07, in the decompiled functions named beside it. Run in the game the same day beside
  KMRP at 1512x982 with the scripted pad: the action box with the default action and its
  slots, the slot with the focus large with its description, the target's name and bar at the
  top left, the map at the top right, the party framed with its bars at the bottom right; and
  alone on the unmodified game, where a key press brought the game's own HUD back and the pad
  the Xbox one again. Not seen: a fight (the combat strip and line), the pause notice, the
  speech box. What differs from Windows in kind, not only in number:

    - a resource name (CResRef) is 17 bytes here, at +0x3D of a border's parameters (Windows: 16
      at +0x40), so every kept name is 17 bytes;
    - a control's flags are one byte at +0x68 (Windows: an int at +0x44), and a border's flags
      one byte at +0x1C of its parameters, with resource names right behind it;
    - an object id is 64 bits (the HUD's target at +0x80), and so is the combat message's number
      at +0x97D8 (the constructor writes 0xBC50 there as a quadword);
    - CSWGuiText::GetIdealWidthAndHeight (0x1004A3E48) takes the text alone and returns the
      extent in rax:rdx, which is how a 16-byte struct of four ints comes back under the System V
      ABI; its decompile ends `auVar2._0_4_ = iVar5 + 10; ... return auVar2 << 0x40;`;
    - CClientExoApp::GetGUIString (0x10028C4BA) returns a CExoString, so the place to build it
      comes first and the app second, and a CExoString is 16 bytes (the text, then its length);
    - CClientExoAppInternal::GetDefaultActions (0x1002FBD42) is not dead code here: the input
      router (0x1002FA8C9) and 0x1002FB910 call it. Both read its list (+0x6B8, count +0x6C0)
      in the instructions right after their own call, and the routine empties and refills the
      list every time, so a call from here between two of theirs changes nothing they read.

  What came from Windows' 1.6 (handoff items 52, 58, 65, 66, 69, 85, 112 and 136), read against
  the Mac executable and K1XboxHud.cpp on 2026-11-03 and compiled, not yet seen in the game: the
  six places of the Xbox manual with Stealth, the action box as tall as the tallest action, the
  name bar that grows with a long name, the focus let go of on an empty slot, the pause notice
  in two lines where one has no room, and the parts' sizes from KMRP's HUD Size page.

  The option. Enabled() is KOTOR Patch Manager's `xbox-hud` when the manager recorded one
  (configs/kmrp-controller.ini beside the executable, [Patch Options]); otherwise [Hud] Style in
  the settings file (standalone::SettingsPath, KMRP/controller.ini in the game's settings
  folder): on unless it says `PC`, compared without case, and on without the line.
  On the Mac the Xbox-style HUD is the controller's standard since 2026-10-07, at the
  maintainer's word; on Windows it is off unless chosen. The environment variable
  KMRP_XBOX_HUD=1 turns it on whatever either says, for automated tests. Decided once.

  The handlers leave xmm0, the frame time both hooked functions read after their prologue, to
  KOTOR Patch Manager's wrapper, as KmrpGuiFrame at CSWGuiManager::Update does: the 64-bit
  wrapper saves and restores the floating-point state around the handler (FXSAVE64 in
  src/KotorPatcher/src/core/wrapper_x86_64.cpp).
*/
#include "xbox_hud.h"

#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl.h>

#include "../kmrp-layout/options.h"
#include "../kmrp-layout/text.h"
#include "engine.h"
#include "hud.h"
#include "pad.h"
#include "prompts.h"
#include "remap.h"
#include "standalone.h"
#include "state.h"

// The rules of the HUD Size page, shared with Windows. Its rectangle's helper is Windows' calling
// convention, which this file does not use.
#define __thiscall
#include "../../../src/controller-native/K1HudOptionsPolicy.h"
#undef __thiscall

#include <dlfcn.h>
#include <sys/stat.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <map>
#include <string>
#include <strings.h>

namespace kmrp {
namespace xboxhud {
namespace {

using engine::At;
using text::LooksLikePointer;
using text::Readable;

struct Extent { int left, top, width, height; };
struct String { char* text = nullptr; std::uint32_t length = 0; };   // CExoString, 16 bytes

// CSWGuiControl: the extent at +0x08, the flags byte at +0x68, SetExtent the vtable's third
// entry (layout.cpp, hud.cpp).
const std::size_t kControlExtent = 0x08, kControlFlags = 0x68, kVtSetExtent = 0x10;
const std::uint8_t kControlVisible = 0x02;
const std::size_t kResRefBytes = 17;
// A control's border parameters (CSWGuiBorderParams): a label's border is at +0x88 and a
// button's two at +0xA8 and +0x130, each with its parameters 0x18 in (cues.cpp, prompts.cpp).
// In the parameters: the alpha at +0x0C (CSWGuiBorder::Draw, 0x1004A1E40, reads it at +0x24 of
// the border, swaps the pulsing alpha in for it and passes it on with the colour; the target
// menu's refill, 0x1002310E6, writes 1.0 to +0xCC and +0x154 of a slot's button), the colour at
// +0x10 and the flags byte at +0x1C, whose low two bits are FILLSTYLE (CSWGuiBorder::Load,
// 0x1004A1C1A), and the fill's name at +0x3D.
const std::size_t kLabelBorderParams = 0xa0, kButtonBorderParams = 0xc0, kButtonHilightParams = 0x148;
const std::size_t kParamsAlpha = 0x0c, kParamsColour = 0x10, kParamsFlags = 0x1c, kParamsFill = 0x3d;
// A label (0x198 bytes): its CSWGuiText at +0x110 (text.h) and its CSWGuiTextParams at +0x130
// (CSWGuiLabel::ReSetFont, 0x1004A5782), which begins with the text, a CExoString, and has the
// colour at +0x28 (CSWGuiTextParams::SetColor, 0x1004A380E) and the opacity at +0x34
// (0x100231C78 writes 1.0 to +0x9464 of the HUD, LBL_CMBTMODEMSG's).
const std::size_t kLabelSize = 0x198, kLabelTextParams = 0x130, kTextColour = 0x28, kTextOpacity = 0x34;
// CSWGuiProgressBar (0x1A8 bytes): its greatest and current value (SetCurValue, 0x1004A7104),
// its border and its fill, each a CSWGuiBorder (CSWGuiProgressBar::Draw, 0x1004A6F2C, draws
// +0x98 and then +0x120), with their parameters 0x18 in.
const std::size_t kBarMost = 0x88, kBarValue = 0x8c, kBarBorder = 0x98, kBarFill = 0x120;
const std::size_t kBarBorderParams = 0xb0, kBarFillParams = 0x138;
// CSWGuiManager: the viewport's size, two shorts (prompts.cpp).
const std::size_t kManagerViewportWidth = 0xa4, kManagerViewportHeight = 0xa6;

// CSWGuiMainInterface (vtable 0x1005A6220; constructor 0x100232DA0).
const std::uintptr_t kHudVtable = 0x1005a6220UL;
const std::size_t kHudManager = 0x20;              // CSWGuiPanel's manager
const std::size_t kHudTargetId = 0x80;             // 64 bits (UpdateIndicator, 0x1002369FC)
// The personal lists, six of 0x10 bytes with the count at +8: the constructor zeroes the twelve
// quadwords from +0xA0 to the target menu at +0x100, whose own three lists have that shape.
const std::size_t kHudPersonalLists = 0xa0;
const std::size_t kListStride = 0x10, kListCount = 0x08;
const std::size_t kHudTargetMenu = 0x100;          // CSWGuiTargetActionMenu
const std::size_t kHudMouldings = 0x2360;          // CSWGuiLabel[3]: LBL_MOULDING1 to 3
const std::size_t kHudActionBox = 0x2360;          // LBL_MOULDING1
const std::size_t kHudParty = 0x2828, kPartySize = 0x12b0;   // CSWGuiMainInterfaceChar[3]
const std::size_t kPartyBars[2] = {0x9c8, 0xb70};  // PB_VIT, PB_FORCE (Char::Initialize, 0x10023234A)
const std::size_t kPartyVitalityFill = 0xb00;      // the vitality bar's fill parameters (0x9C8 + 0x138)
const std::size_t kHudMarker = 0x72f0;             // the label UpdateIndicator draws the circle or arrow on
const std::size_t kHudMapBorder = 0x7640;          // LBL_MAPBORDER
const std::size_t kHudMapWindow = 0x7b08;          // left, top, width, height (0x100237848's viewport)
const std::size_t kHudMapWindowTop = 0x7b0c;
const std::size_t kHudMapButton = 0x7b20;          // BTN_MINIMAP
const std::size_t kHudQueueButton = 0x8aa8;        // BTN_CLEARONE, which the Y cue follows
const std::size_t kHudMessage = 0x9300;            // LBL_CMBTMODEMSG, which the X cue follows here
const std::size_t kHudMessageBack = 0x9498;        // LBL_CMBTMSGBG
const std::size_t kHudMessageNumber = 0x97d8;      // 64 bits (0x100231C78 keeps the strref there)
const std::size_t kHudPersonalActions = 0x97e0;    // CSWGuiMainInterfaceAction[]
const std::size_t kHudDescription = 0xce40;        // LBL_ACTIONDESC
const std::size_t kHudDescriptionBack = 0xcfd8;    // LBL_ACTIONDESCBG, which SetActionDescription sizes with it
const std::size_t kHudDescriptionBottom = 0xd170;  // the edge the description grows up from (0x1002355E6)
const std::size_t kHudSpareButton = 0xe918;        // BTN_MSG
const std::size_t kHudSpareLabel = 0xf218;         // LBL_MENUBG
const std::size_t kHudArrowMargin = 0xf3b0;        // LBL_ARROW_MARGIN
// A party member's frame, portrait and bars, and what shares the portrait's rectangle
// (LBL_CHAR1, BTN_CHAR1, LBL_DEBILATATED1, LBL_LVLUPBG1, LBL_LEVELUP1), all for the first member.
const std::size_t kPartyFrame = 0x2860, kPartyPortrait = 0x3058, kPartyVitality = 0x31f0, kPartyForce = 0x3398;
const std::size_t kPartyPictures[] = {0x3058, 0x3870, 0x29f8, 0x2ec0, 0x2d28};
// CSWGuiMainInterfaceAction (0x910 bytes): frame button, icon button, up, down (hud.cpp).
const std::size_t kActionSize = 0x910;
const std::size_t kActionParts[4] = {0x000, 0x240, 0x480, 0x6c0};
const std::size_t kActionIcon = 0x240;

// CSWGuiTargetActionMenu, from its start: the three lists, the chosen id by kind and list
// (0x100230CB4 reads `menu + kind * 0xC + 0x30 + list * 4`), the three slots, the HUD
// (Initialize, 0x10023082C), the viewport's origin, width and height and the rectangle it is
// kept inside (the menu's Draw and the HUD's constructor), the four name controls
// (Initialize), and three bytes: the target's kind, the slot the name bar shows and bit 0
// "there is a target" (0x1002310E6, 0x100230CB4, the menu's Draw).
const std::size_t kMenuActionLists = 0x00, kMenuChosen = 0x30, kMenuActions = 0x60;
const std::size_t kMenuInterface = 0x1b90;
const std::size_t kMenuOrigin = 0x1b98, kMenuWidth = 0x1ba0, kMenuHeight = 0x1ba4, kMenuClamp = 0x1ba8;
const std::size_t kMenuNameLabel = 0x1bb8, kMenuNameBackground = 0x1d50, kMenuHealthBackground = 0x1ee8;
const std::size_t kMenuHealthBar = 0x2080;
const std::size_t kMenuTargetKind = 0x223a, kMenuNamedSlot = 0x223b, kMenuFlags = 0x223c;
const std::size_t kHudNameFrame = kHudTargetMenu + kMenuNameBackground;   // LBL_NAMEBG
// A list's entry (CSWGuiInterfaceAction, 0x48 bytes): its name first, its id at +0x10, its
// icon at +0x30 (GetDefaultActions writes 0x404 and "i_noaction" there and steps by 0x48).
const std::size_t kEntrySize = 0x48, kEntryId = 0x10, kEntryIcon = 0x30;
// And the rest (CSWGuiInterfaceAction::Clear, 0x10033AFF0, writes each): a member pointer's routine
// and its adjustment, the 64-bit id of the object acted on, a flags byte (bit 0 "can be used") and
// a count.
const std::size_t kEntryRoutine = 0x18, kEntryObject = 0x28, kEntryFlags = 0x40, kEntryCount = 0x44;
const std::size_t kDefaultActions = 0x6b8;         // GetDefaultActions' list, in CClientExoAppInternal
const int kMostEntries = 256;

// CGuiInGame (CClientExoAppInternal +0x80, engine.h): the speech box at +0x88
// (CGuiInGame::GetBarkBubbleVisible, 0x100262160), whose Draw (0x1002DDFA2) puts it back on
// the rectangle kept at +0x218 (left, top, width) before every draw; the pause notice at +0xE8
// (0x100257494 stores the new CSWGuiInGamePause there), whose vtable its constructor
// (0x1002E0832) sets to 0x1005AD640 and whose controls it binds at +0x80, +0x218 and +0x3B0.
const std::size_t kInGameBarkBubble = 0x88, kBubbleExtent = 0x218;
const std::size_t kInGamePause = 0xe8;
const std::uintptr_t kPauseVtable = 0x1005ad640UL;
const std::size_t kPauseReason = 0x80, kPausePress = 0x218, kPauseButton = 0x3b0, kPauseSize = 0x5f8;

const auto SetFillImage = reinterpret_cast<void (*)(void* params, const void* resref, int force)>(0x1004a17c2UL);
const auto GetGameObject = reinterpret_cast<void* (*)(void* app, std::uint64_t id)>(0x10028bc78UL);
const auto GetGuiString = reinterpret_cast<void (*)(String* out, void* app, std::uint64_t strref)>(0x10028c4baUL);
const auto StringFromText = reinterpret_cast<void (*)(String* string, const char* text)>(0x10034cca8UL);
const auto StringDestroy = reinterpret_cast<void (*)(String* string)>(0x10034cdf2UL);
// CSWGuiMainInterface::SetActionDescription(CExoString*) and
// CSWGuiTargetActionMenu::UpdateNameLabel(CSWCObject*), both unnamed in the Mac database:
// 0x1002355E6 sets LBL_ACTIONDESC's text and ends it at +0xD170; 0x100230CB4 reads the named
// slot at +0x223B and ends in SetNameLabel.
const auto SetDescription = reinterpret_cast<void (*)(void* hud, void* string)>(0x1002355e6UL);
const auto SetActiveControl = reinterpret_cast<void (*)(void* panel, void* control, int sound)>(0x10049de24UL);
const auto UpdateNameLabel = reinterpret_cast<void (*)(void* menu, void* object)>(0x100230cb4UL);
const auto GetDefaultActions = reinterpret_cast<void (*)(void* internal)>(0x1002fbd42UL);
const auto SetBarValue = reinterpret_cast<void (*)(void* bar, int value)>(0x1004a7104UL);
// What the target menu's Draw calls to clip its own drawing to a rectangle. AurGUISetupViewport
// takes an alpha in xmm0 (the HUD's Draw passes its panel's, the menu's Draw 1.0) and the
// colouring as a pointer; 0x1005733C0 is the one the menu's Draw passes.
const auto StartLayer = reinterpret_cast<void (*)()>(0x1001bb937UL);
const auto StopLayer = reinterpret_cast<void (*)()>(0x1001bba41UL);
const auto SetupViewport =
    reinterpret_cast<int (*)(float alpha, int x, int y, int width, int height, const void* colour, int)>(0x1001bba8aUL);
const auto CloseViewport = reinterpret_cast<void (*)()>(0x1001bbcdeUL);
const void* const kNoColouring = reinterpret_cast<const void*>(0x1005733c0UL);
const auto SetTextColour = reinterpret_cast<void (*)(void* params, const void* vector)>(0x1004a380eUL);
const auto SetTextOf = reinterpret_cast<void (*)(void* params, String* text)>(0x1004a3714UL);
const auto TextHeight = reinterpret_cast<int (*)(void* text)>(0x1004a3dc4UL);     // CSWGuiText::GetIdealHeight
const auto MeasureText = reinterpret_cast<Extent (*)(void* text)>(0x1004a3e48UL);  // GetIdealWidthAndHeight
// CSWGuiMainInterface::SetupPauseGuiExtent (0x100239496; CGuiInGame's, 0x100262D06, only hands
// it the HUD): the pause notice's left and top under the PC HUD's Equipment button.
const auto SetupPauseExtent = reinterpret_cast<void (*)(void* hud, Extent* extent)>(0x100239496UL);
// CSWGuiLabel::Draw, CSWGuiButton::Draw and CSWGuiBorder::Draw, each with the frame time in
// xmm0. Called by address, as their classes are known: Windows calls the first two through the
// vtable (its entry 14) and the border's through its entry 3.
const auto LabelDraw = reinterpret_cast<void (*)(void* label, float seconds)>(0x1004a5604UL);
const auto ButtonDraw = reinterpret_cast<void (*)(void* button, float seconds)>(0x1004a5c86UL);
const auto BorderDraw = reinterpret_cast<void (*)(void* border, float seconds)>(0x1004a1e40UL);
const std::size_t kVtAsSWCObject = 0x20;           // the game object's AsSWCObject (UpdateIndicator)

// The name's frame for a friendly and for a hostile target, the slots' frames, the arrows and
// the bars: the drawings tools/build_xbox_hud_art.py makes (kmrx_*), and the game's own names
// they stand in for.
const char kFrameFriendly[kResRefBytes] = "kmrx_miindic01f";
const char kFrameHostile[kResRefBytes] = "kmrx_miindic01e";
// The same frames in three slices, friendly then hostile: the top to row 32 of the 64, a plain
// middle that stretches, the bottom from row 32 (tools/build_xbox_hud_art.py, target_bar_slice),
// for a name taller than its row.
const char kFrameSlices[2][3][kResRefBytes] = {{"kmrx_miindic1ft", "kmrx_miindic1fm", "kmrx_miindic1fb"},
                                               {"kmrx_miindic1et", "kmrx_miindic1em", "kmrx_miindic1eb"}};
const int kFrameSplit = 32;
const char kSlotHostile[kResRefBytes] = "lbl_miscroll_h";
const char kSlotEnginePrefix[] = "lbl_miscroll";       // CSWGuiTargetActionMenu::SetFriend (0x100230B4A) names both
const char kSlotFrame[kResRefBytes] = "kmrx_mibox01";
const char kSlotFrameSelected[kResRefBytes] = "kmrx_mibox02";
const char kArrows[kResRefBytes] = "kmrx_miarrow01";
const char kArrowsSelected[kResRefBytes] = "kmrx_miarrow02";
const char kFlatHealth[kResRefBytes] = "redfill";      // the portraits' update (0x1002361B8) writes these two
const char kFlatPoison[kResRefBytes] = "greenfill";
const char kCurvedHealth[kResRefBytes] = "kmrx_health";
const char kCurvedPoison[kResRefBytes] = "kmrx_healthp";
const char kNoActionIcon[kResRefBytes] = "i_noaction";
const char kMapFrame[kResRefBytes] = "kmrx_minimap";
const char kStripFill[kResRefBytes] = "blackfill";
const char kLineFill[kResRefBytes] = "whitefill";

// The numbers K1XboxHud.cpp explains: the action box above its text, the small and the large
// slot (frame, icon, arrow), the six places of the seven slots, the name bar's parts from
// LBL_NAME's corner, the combat strip, the combat line's button and the minimap frame's line.
const int kBaseHeight = 480;       // the Xbox drew these pixel sizes on 480 lines (build_xbox_hud.py, SCALE_H)
const int kBoxAboveText = 6, kBoxEmptyLine = 16;
const int kSlots = 7, kTargetSlots = 3;
const int kSmall[3][2] = {{41, 41}, {21, 21}, {11, 41}};
const int kLarge[3][2] = {{64, 64}, {32, 32}, {14, 56}};
// The Xbox manual's six places (K1XboxHud.cpp says how they were found, issues #55 and #50): the
// default action, the feats and skills, offensive Force powers, grenades or mines, the
// character's own Force powers, and the medical and other usable items together. The feats and
// the skills share a place, the grenades and the mines another.
const int kPlace[kSlots] = {1, 2, 3, 4, 5, 1, 3};
const int kSharedTarget = 2;       // the grenade slot, of the seven
const int kSharedPersonal = 6;     // the mines' slot
const int kFeatsSlot = 0;          // the target's first slot
const int kSkillsSlot = 5;         // the third personal slot, holding the skills (KmrpXboxHudLists)
const int kRowPlaces = 5;          // the places after the first, which this file draws
// Where xbox_hud_layout.inc puts the first two personal slots (BTN_ACTION0, 1): the row's
// geometry is read from them (ReadRow), whatever kPlace shows there now.
const int kTablePlaces[2] = {1, 4};
const int kParked = -4000;
const int kNameHeight = 26;                            // LBL_NAME
const int kNameFrame[4] = {-10, -14, 271, 64};         // LBL_INDICATE, from LBL_NAME's corner
const int kHealthBar[4] = {1, 26, 247, 9};             // PB_HEALTH, from the same corner
const int kStripHeight = 44, kStripShift = 14;
const float kStripAlpha = 0.55f;
const float kLineColour[3] = {0.32f, 0.46f, 0.92f};    // the HUD text's blue
const int kButtonSize = 22, kButtonGap = 9;            // pixels, beside a 16 px font
const double kMapFrameLine = 4.0;                      // kmrx_minimap's line ends 4.0 of its 64 in
// dialog.tlk. 48208 and 32236 are in the Mac code as 0xBC50 (the HUD's constructor) and 0x7DEC
// (GetDefaultActions); 42475 and 48384 are the Windows file's.
const std::uint64_t kEngagedString = 48208, kEngagedPadString = 42475, kNoActionString = 32236;
const std::uint64_t kPausePressString = 48384;         // "PRESS THE PAUSE BUTTON TO CONTINUE"
const std::uint64_t kStealthName = 325;                // "Stealth"
// What the Windows engine makes of "<bbutton>" in 42475. Not verified on the Mac: when the
// character is not in the string the line is not split and the game's own message stays.
const char kButtonCharacter = 0x11;

void* Part(void* base, std::size_t offset) { return static_cast<char*>(base) + offset; }

std::uintptr_t VtableOf(void* object) { return LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

void SetExtent(void* control, const Extent& wanted) {
    const Extent& now = At<Extent>(control, kControlExtent);
    if (now.left == wanted.left && now.top == wanted.top && now.width == wanted.width && now.height == wanted.height)
        return;
    const std::uintptr_t vtable = VtableOf(control);
    if (!LooksLikePointer(reinterpret_cast<void*>(vtable))) return;
    reinterpret_cast<void (*)(void*, const Extent*)>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtSetExtent))(control,
                                                                                                           &wanted);
}

bool Visible(void* control) { return (At<std::uint8_t>(control, kControlFlags) & kControlVisible) != 0; }
void Show(void* control) { At<std::uint8_t>(control, kControlFlags) |= kControlVisible; }
void Hide(void* control) { At<std::uint8_t>(control, kControlFlags) &= static_cast<std::uint8_t>(~kControlVisible); }

// A resource's name is 16 characters at most and need not end in a zero before the 17th byte.
bool SameName(const char* a, const char* b) { return strncasecmp(a, b, 16) == 0; }

// `name` must be kResRefBytes long: the engine copies all of a resource's name.
void SetFill(void* params, const char* name) {
    if (SameName(&At<char>(params, kParamsFill), name)) return;
    SetFillImage(params, name, 1);
}

void SetFillName(void* params, const char* name) {
    char padded[kResRefBytes] = {};
    for (std::size_t i = 0; i < 16 && name[i]; ++i) padded[i] = name[i];
    SetFill(params, padded);
}

// A layout length on this screen, rounding half up, as build_xbox_hud.py rounds.
int Scale(int value, int height) {
    return value >= 0 ? (2 * value * height + kBaseHeight) / (2 * kBaseHeight)
                      : -((2 * -value * height + kBaseHeight) / (2 * kBaseHeight));
}

const char* TextOf(const String& string) { return Readable(string.text, 1) ? string.text : nullptr; }

void SetText(void* label, String* text) { SetTextOf(Part(label, kLabelTextParams), text); }

void SetText(void* label, const char* text) {
    String made;
    StringFromText(&made, text);
    SetText(label, &made);
    StringDestroy(&made);
}

// A label's CSWGuiText measures through its string object (+0x18), which
// GetIdealWidthAndHeight does not test for.
bool HasString(void* label) { return Readable(At<void*>(Part(label, text::kLabelText), text::kTextObject), 8); }

// A line's width, which the engine gives to the nearest 10.
int LineWidth(void* label) {
    return HasString(label) ? MeasureText(Part(label, text::kLabelText)).width : 0;
}

void* Client() {
    void* client = engine::ClientApp();
    return LooksLikePointer(client) ? client : nullptr;
}

void* InGame() {
    void* internal = engine::ClientInternal();
    void* inGame = LooksLikePointer(internal) ? At<void*>(internal, engine::kInternalGuiInGame) : nullptr;
    return LooksLikePointer(inGame) ? inGame : nullptr;
}

int* BarkBubble() {
    void* inGame = InGame();
    void* bubble = inGame ? At<void*>(inGame, kInGameBarkBubble) : nullptr;
    return Readable(bubble, kBubbleExtent + 3 * sizeof(int)) ? &At<int>(bubble, kBubbleExtent) : nullptr;
}

void* PausePanel() {
    void* inGame = InGame();
    void* pause = inGame ? At<void*>(inGame, kInGamePause) : nullptr;
    return Readable(pause, kPauseSize) && VtableOf(pause) == kPauseVtable ? pause : nullptr;
}

// A bar emptied for the panel's draw, and the value to draw and give back.
struct Bar { void* bar = nullptr; int value = 0; };
Bar g_bars[3][2];

Extent g_messageRow{};     // the combat-mode message's row in the Xbox layout (ApplyXbox)

// The combat-mode message (K1XboxHud.cpp, CombatMessage). While "COMBAT MODE engaged. Press the
// Disengage button to cancel." (48208) is up and the pad is in use, the line is the Xbox game's
// (42475) with the pad's own disengage button in the token's place: the text before the token
// in the message label, as wide as its text; the button, which is the X cue label; the text
// after it in the message's background label. Any other message, and this one with the mouse in
// use, is the game's. Called before each draw while the Xbox layout is up, and once more as it
// is taken off.
// A label's font as its string is drawn (text.h): the glyphs' widths and the spacing in
// pixels at scale 1, the string's scale, and the line's height, fontheight * scale * 100
// rounded half up as Windows has it.
struct Measures { text::Font font{}; float scale = 1.0f; int lineHeight = 0; };

bool MeasuresOf(void* label, Measures& out) {
    char* const object = At<char*>(Part(label, text::kLabelText), text::kTextObject);
    if (!Readable(object, 0x60) || !text::FontOf(object, out.font)) return false;
    out.scale = At<float>(object, text::kObjScale);
    if (!(out.scale > 0.01f && out.scale < 100.0f)) out.scale = 1.0f;
    // FontOf has just called the font's information routine and read the block it returns.
    void* const font = At<void*>(object, text::kObjFont);
    const char* const info =
        reinterpret_cast<text::FontInfoFn>(*reinterpret_cast<std::uintptr_t*>(At<std::uintptr_t>(font, 0) + text::kVtFontInfo))(font);
    if (!Readable(info, 0x30)) return false;
    out.lineHeight = static_cast<int>(*reinterpret_cast<const float*>(info + text::kInfoHeight) * out.scale * 100.0f + 0.5f);
    return true;
}

int Wide(const Measures& m, const char* words) {
    float sum = 0.0f;
    for (; *words; ++words) sum += text::GlyphWidth(m.font, static_cast<unsigned char>(*words)) + m.font.spacing;
    return static_cast<int>(sum * m.scale + 0.999f);
}

void CombatMessage(void* hud, void* client, int width) {
    const Extent messageWas = g_messageRow, backWas = g_messageRow;
    static bool changed = false;
    static String before, after, nothing;
    static bool split = false, tried = false;
    void* message = Part(hud, kHudMessage);
    void* back = Part(hud, kHudMessageBack);
    void* button = cues::Following(hud, kHudMessage);
    if (!tried && client) {
        tried = true;
        String whole;
        GetGuiString(&whole, client, kEngagedPadString);
        const char* all = TextOf(whole);
        const char* token = all ? std::strchr(all, kButtonCharacter) : nullptr;
        if (token) {
            char left[256] = {}, right[256] = {};
            std::size_t n = static_cast<std::size_t>(token - all);
            while (n > 0 && all[n - 1] == ' ') --n;
            if (n < sizeof left) std::memcpy(left, all, n);
            const char* rest = token + 1;
            while (*rest == ' ') ++rest;
            std::snprintf(right, sizeof right, "%s", rest);
            StringFromText(&before, left);
            StringFromText(&after, right);
            StringFromText(&nothing, "");
            split = before.text && after.text;
        }
        StringDestroy(&whole);
    }
    const bool engaged = split && button && device::PadInUse() &&
                         At<std::uint64_t>(hud, kHudMessageNumber) == kEngagedString && Visible(message);
    void* messageText = Part(message, kLabelTextParams);
    void* backText = Part(back, kLabelTextParams);
    if (engaged) {
        // The second half takes the first's colour and opacity, which the engine sets per
        // message and fades.
        SetText(message, &before);
        SetText(back, &after);
        SetTextColour(backText, Part(messageText, kTextColour));
        At<float>(backText, kTextOpacity) = At<float>(messageText, kTextOpacity);
        // The whole line centred: the two texts' widths, with the button between. Everything
        // from the line's own height, as the pause notice is made: the picture a line and
        // three eighths tall, nine sixteenths of a line between it and the words, and each
        // text's width from its font, so that neither can break. Until 2026-10-08 the picture
        // was 22 px and the gaps 9, right beside a 16 px font, and the widths were the
        // engine's, to the nearest 10: at 3840x2160 the picture was a dot and "COMBAT MODE
        // ENGAGED." stood on two lines (the maintainer saw it on a 4K television).
        Measures measures;
        const bool measured = MeasuresOf(message, measures) && measures.lineHeight > 0;
        const int lineHeight = measured ? measures.lineHeight : 16;
        const int size = measured ? lineHeight + lineHeight * 3 / 8 : kButtonSize;
        const int gap = measured ? (lineHeight * 9 + 8) / 16 : kButtonGap;
        const int slack = measured ? lineHeight / 2 : 0;
        int first = LineWidth(message), second = LineWidth(back);
        if (measured) {
            const int wide = Wide(measures, TextOf(before));
            if (wide > first) first = wide;
            Measures own;
            const int after2 = Wide(MeasuresOf(back, own) && own.lineHeight > 0 ? own : measures, TextOf(after));
            if (after2 > second) second = after2;
        }
        const int total = first + gap + size + gap + second;
        const int joint = (width - total) / 2 + first;
        // The first text is centred in its rectangle, which has half a line to spare on
        // either side of it.
        SetExtent(message, {joint - first - slack, messageWas.top, first + 2 * slack, messageWas.height});
        SetExtent(button, {joint + gap, messageWas.top + (messageWas.height - size) / 2, size, size});
        const int from = joint + gap + size + gap;
        // The second label's text starts at its top left, the first's is centred in its row:
        // the second is given the row the first's text is on.
        const int line = TextHeight(Part(message, text::kLabelText));
        const int down = line > 0 && line < messageWas.height ? (messageWas.height - line) / 2 : 0;
        SetExtent(back, {from, messageWas.top + down, width - from, messageWas.height - down});
        changed = true;
        return;
    }
    if (button) SetExtent(button, {kParked, kParked, kButtonSize, kButtonSize});
    if (changed) {
        changed = false;
        SetExtent(message, messageWas);
        SetExtent(back, backWas);
        SetText(back, &nothing);
        // The game's own line again, if it is still this message (the mouse came back).
        if (client && At<std::uint64_t>(hud, kHudMessageNumber) == kEngagedString) {
            String own;
            GetGuiString(&own, client, kEngagedString);
            SetText(message, &own);
            StringDestroy(&own);
        }
    }
}

// The first place, as the first hook decided it and the second draws it.
struct FirstPlace {
    bool draw = false, selected = false;
    char icon[kResRefBytes] = {};
    Extent frame{}, picture{};
    int empties = 0;
    Extent empty[kRowPlaces]{};        // the places with no slot shown: a dim frame each
    int width = 0, height = 0;
} g_first;

// The name frame's three slices, for a name taller than its row, as the first hook placed them
// and the second draws them (K1XboxHud.cpp, NameSlices).
struct NameSlices {
    bool draw = false;
    int hostile = 0;
    Extent top{}, middle{}, bottom{};
    int width = 0, height = 0;
} g_nameSlices;

// ---- The layout, applied to the live controls.
//
// The game always loads its own HUD layout (or whatever layout another patch put in its
// place). While the pad is the device in use, each control is moved to its Xbox place for the
// screen the game is drawing and given its Xbox art; when the mouse or keyboard takes over,
// each is put back exactly as it was. A control is found by its offset in CSWGuiMainInterface,
// where the executable builds it whatever the file says.
enum Kind : unsigned char { kLabel, kButton, kToggle, kProgress };
enum Side : unsigned char { kLeft, kRight, kCentre, kRelative };
enum Edge : unsigned char { kTop, kBottom };
enum : unsigned char { kHide = 1, kRow = 2, kSetFont = 4, kParty = 8 };
struct Piece {
    unsigned short offset;
    Kind kind;
    Side side;
    Edge edge;
    short box[4];
    signed char places;
    unsigned char flags;
    const char* fill;
    const char* hilight;
    const char* progress;
};
#include "xbox_hud_layout.inc"
const int kPieceCount = static_cast<int>(sizeof kPieces / sizeof kPieces[0]);

void* Dress(void* control, Kind kind, int which) {   // 0 the fill, 1 the focused fill, 2 a bar's filling
    switch (kind) {
    case kLabel: return which == 0 ? Part(control, kLabelBorderParams) : nullptr;
    case kButton:
        return which == 0 ? Part(control, kButtonBorderParams) : which == 1 ? Part(control, kButtonHilightParams) : nullptr;
    case kProgress: return which == 0 ? Part(control, kBarBorderParams) : which == 2 ? Part(control, kBarFillParams) : nullptr;
    default: return nullptr;
    }
}

// A label's font. CSWGuiText::Load (0x1004A3AA0) copies the layout's FONT name to +0x45 of the
// text's parameters, 16 characters and a zero, and calls 0x1004A3670 on them, which reads that
// name, has CSWGuiManager::GetUpdatedFontName add the letter the engine picks for the screen
// and the player's font option, and loads the font when it is not the one in use. The same two
// steps here are Windows' CSWGuiTextParams::SetBaseFont (0x00415DD0). The four labels that
// change font take the Xbox layout's, dialogfont16x16, which the game's own HUD layouts use too:
// Windows records a crash on loading a save with a font the HUD's layouts do not use.
const std::size_t kTextFontName = 0x45;
void SetFont(void* label, const char* name) {
    char* const params = static_cast<char*>(Part(label, kLabelTextParams));
    char padded[kResRefBytes] = {};
    for (std::size_t i = 0; i + 1 < kResRefBytes && name[i]; ++i) padded[i] = name[i];
    if (std::memcmp(params + kTextFontName, padded, kResRefBytes) == 0) return;
    std::memcpy(params + kTextFontName, padded, kResRefBytes);
    reinterpret_cast<void (*)(void*)>(0x1004a3670UL)(params);
}

// The party's bars are drawn through a viewport that ends at the bar's edge, and with the
// texture repeating, the row beyond that edge is the texture's far side: a line of the bar's
// other end. After each is drawn its texture is still the one bound, and it is told to clamp at
// its edges (Windows' ClampBoundTexture); the setting belongs to the texture, so it holds from
// the next draw on. These textures are used by nothing but this HUD.
void ClampBoundTexture() {
    GLint bound = 0;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &bound);
    if (!bound) return;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

// ---- The sizes of this HUD's parts, from the HUD Size page in KMRP's Graphics Options (handoff
// items 59 and 66): the action menu, the party, the minimap, the target's bar at the top left and
// the Disengage button, each made larger or smaller about its corner of the screen, 50% being
// the HUD as it was, 100% twice that. The page is KMRP's and this patch works without KMRP
// (handoff item 112). Only while KMRP's module is loaded beside this one does it read the page's
// section of swkotor.ini: once, and again whenever the file has been written since (looked at
// twice a second at most, which costs a file's attributes), so a slider moved on the page shows
// on the HUD when the game is back. Without KMRP every part stays at the standard 50%, even when
// that section remains from an earlier install. Windows' Sizes.
namespace sizes = KmrpHudOptions;
using sizes::ElementCount;
using HudSizes = std::array<int, ElementCount>;

std::string Trimmed(const std::string& s);

const HudSizes& Sizes() {
    static HudSizes held = [] { HudSizes all; all.fill(sizes::Default); return all; }();
    if (!standalone::BesideKmrp()) {
        held.fill(sizes::Default);
        return held;
    }
    static std::uint64_t looked = 0;
    static timespec written{};
    static bool once = false;
    const std::uint64_t now = NowMs();
    if (once && now - looked < 500) return held;
    once = true;
    looked = now;
    const char* home = std::getenv("HOME");
    if (!home || !*home) return held;
    const std::string path = std::string(home) + "/Library/Application Support/Knights of the Old Republic/swkotor.ini";
    struct stat about;
    if (stat(path.c_str(), &about) != 0) return held;
    if (about.st_mtimespec.tv_sec == written.tv_sec && about.st_mtimespec.tv_nsec == written.tv_nsec) return held;
    written = about.st_mtimespec;
    FILE* f = std::fopen(path.c_str(), "r");
    if (!f) return held;
    HudSizes read = held;
    for (int e = sizes::XboxActions; e < ElementCount; ++e) read[e] = sizes::Default;
    bool ours = false;
    char buffer[1024];
    while (std::fgets(buffer, sizeof buffer, f)) {
        const std::string line = Trimmed(buffer);
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;
        if (line[0] == '[') {
            const std::size_t close = line.find(']');
            ours = close != std::string::npos && strcasecmp(Trimmed(line.substr(1, close - 1)).c_str(), "KMRP HUD Size") == 0;
            continue;
        }
        const std::size_t eq = line.find('=');
        if (!ours || eq == std::string::npos) continue;
        const std::string key = Trimmed(line.substr(0, eq));
        for (int e = sizes::XboxActions; e < ElementCount; ++e) {
            std::string wanted;
            for (const wchar_t* k = sizes::IniKeys[e]; *k; ++k) wanted += static_cast<char>(*k);
            if (strcasecmp(key.c_str(), wanted.c_str()) == 0) read[e] = sizes::Percent(std::atoi(line.c_str() + eq + 1));
        }
    }
    std::fclose(f);
    held = read;
    return held;
}

// Each part's box as the table places it on this screen, before its size, and the size it was
// placed at: what Sized and SizedHeight work from (ApplyXbox sets them).
sizes::Rect g_parts[ElementCount]{};
HudSizes g_placedSizes{};

sizes::Rect AsRect(const Extent& e) { return {e.left, e.top, e.width, e.height}; }
Extent AsExtent(const sizes::Rect& r) { return {r.left, r.top, r.width, r.height}; }
// A rectangle of a part, at the part's size, about the part's corner.
Extent Sized(int element, const Extent& at) {
    return AsExtent(sizes::ScaleAbout(AsRect(at), g_parts[element], sizes::CornerOf(element), g_placedSizes[element]));
}
// The screen height a part's lengths are drawn for: the screen's, at the part's size.
// Scale(value, SizedHeight(part, height)) is a length of that part at its size.
int SizedHeight(int element, int height) { return sizes::Round(height * sizes::Factor(g_placedSizes[element])); }

// The size the mouse and keyboard HUD's minimap is shown at by KMRP (Windows K1PcHud.cpp), or 50
// without KMRP: the minimap here is the game's own HUD's size (ApplyXbox), and that is taken as
// it would be at 50% so that each HUD's slider sizes only its own. KMRP's export is found through
// its module's handle, beside this one's: a patch's module is loaded local, so a search of every
// image finds nothing (audit MAC-5). A module without it is taken for 50%.
int PcMinimapSize() {
    if (!standalone::BesideKmrp()) return sizes::Default;
    using Applied = int (*)(int);
    static Applied applied = nullptr;
    if (!applied) {
        Dl_info self;
        if (dladdr(reinterpret_cast<const void*>(&PcMinimapSize), &self) && self.dli_fname) {
            std::string path(self.dli_fname);
            path = path.substr(0, path.rfind('/') + 1) + "kmrp.dylib";
            if (void* const kmrp = dlopen(path.c_str(), RTLD_NOLOAD | RTLD_LAZY)) {
                applied = reinterpret_cast<Applied>(dlsym(kmrp, "KmrpHudAppliedSizeK1"));
                dlclose(kmrp);
            }
        }
    }
    return applied ? sizes::Percent(applied(sizes::PcMinimap)) : sizes::Default;
}

struct Kept { Extent extent; char art[3][kResRefBytes]; char font[kResRefBytes]; };
struct Layout {
    void* hud = nullptr;
    bool xbox = false;
    int width = 0, height = 0;         // the screen the Xbox layout was applied for
    Kept kept[kPieceCount]{};
    int descriptionBottom = 0, mapWindow[4]{}, menu[8]{};
    Extent queueCue{};
    char cueFill[kResRefBytes]{};
    bool cues = false;
    int bubble[3]{};
    bool bubbleKept = false;
    int bubbleTop = 0;                 // the speech box's top in the Xbox layout, under the name bar
    Extent arrowMargin{};      // LBL_ARROW_MARGIN's rectangle as the layout has it
    bool arrowMarginKept = false;
    float spareAlpha = 1.0f;           // of LBL_MENUBG's fill, which the hooks draw with
    HudSizes sizes{};                  // the parts' sizes the Xbox layout was applied at
} g_layout;

const char* Piece::* const kArt[3] = {&Piece::fill, &Piece::hilight, &Piece::progress};

// The first sight of a HUD object, which is as its layout file and the engine made it.
void Keep(void* hud) {
    g_layout = Layout{};
    g_layout.hud = hud;
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        void* control = Part(hud, piece.offset);
        Kept& kept = g_layout.kept[i];
        kept.extent = At<Extent>(control, kControlExtent);
        for (int which = 0; which < 3; ++which)
            if (void* params = Dress(control, piece.kind, which))
                std::memcpy(kept.art[which], &At<char>(params, kParamsFill), kResRefBytes);
        if (piece.kind == kLabel) {
            std::memcpy(kept.font, &At<char>(Part(control, kLabelTextParams), kTextFontName), kResRefBytes);
            kept.font[kResRefBytes - 1] = 0;
        }
    }
    g_layout.spareAlpha = At<float>(Part(Part(hud, kHudSpareLabel), kLabelBorderParams), kParamsAlpha);
    g_layout.descriptionBottom = At<int>(hud, kHudDescriptionBottom);
    std::memcpy(g_layout.mapWindow, &At<int>(hud, kHudMapWindow), sizeof g_layout.mapWindow);
    std::memcpy(g_layout.menu, &At<int>(Part(hud, kHudTargetMenu), kMenuOrigin), sizeof g_layout.menu);
}

Extent Placed(const Piece& piece, const Kept& kept, int width, int height) {
    const int x = piece.box[0], y = piece.box[1];
    const int w = Scale(piece.box[2], height), h = Scale(piece.box[3], height);
    if (piece.flags & kHide) return {kParked, kParked, kept.extent.width, kept.extent.height};
    if (piece.flags & kParty) {
        // The party's group, smaller about its bottom right corner (build_xbox_hud.py,
        // PARTY_SCALE). Lengths here need not be whole units, so they are scaled as they are
        // and rounded half up once.
        const double f = kPartyScale / 100.0;
        auto exact = [height](double units) { return static_cast<int>(units * height / kBaseHeight + 0.5); };
        const int pw = exact(piece.box[2] * f), ph = exact(piece.box[3] * f);
        if (piece.side == kRelative) return {exact(x * f), exact(y * f), pw > 0 ? pw : 1, ph > 0 ? ph : 1};
        return {width - exact(kLayoutWidth - kOutX - kPartyCorner[0] + (kPartyCorner[0] - x) * f),
                height - exact(kLayoutHeight - kOutY - kPartyCorner[1] + (kPartyCorner[1] - y) * f),
                pw > 0 ? pw : 1, ph > 0 ? ph : 1};
    }
    if (piece.flags & kRow) return {0, Scale(y, height), width, h};
    if (piece.side == kRelative) return {Scale(x, height), Scale(y, height), w > 0 ? w : 1, h > 0 ? h : 1};
    int left;
    if (piece.side == kLeft) left = Scale(x - kOutX, height);
    else if (piece.side == kRight) left = width - Scale(kLayoutWidth - x - kOutX, height);
    else left = x >= kLayoutWidth / 2 ? width / 2 + Scale(x - kLayoutWidth / 2, height)
                                       : width / 2 - Scale(kLayoutWidth / 2 - x, height);
    const int top = piece.edge == kTop ? Scale(y, height) : height - Scale(kLayoutHeight - y - kOutY, height);
    return {left + piece.places * Scale(kSlotPitch, height), top, w > 0 ? w : 1, h > 0 ? h : 1};
}

void ReadRow(void* hud, int height);

// Each portrait's frame, put around the portrait as it stands in pixels, with its two bars
// (K1XboxHud.cpp, FramePortraits). The frame is a whole number of pixels wide, so of the two
// widths nearest the exact one, the one that puts the portrait's side edges closest to the
// art's hairlines is taken; the picture is kept one whole pixel clear of each lens.
void FramePortraits(void* hud) {
    auto nearest = [](double v) { return static_cast<int>(v + 0.5); };
    for (int member = 0; member < 3; ++member) {
        const std::size_t at = member * kPartySize;
        Extent portrait = At<Extent>(Part(hud, kPartyPortrait + at), kControlExtent);
        void* frame = Part(hud, kPartyFrame + at);
        const Extent was = At<Extent>(frame, kControlExtent);
        if (portrait.width <= 0 || portrait.height <= 0 || was.width <= 0) continue;
        Extent now{};
        const double panel = (64.0 - 2 * kPortraitInset[0]) / 64.0;       // the picture's share of the frame's width
        const int under = static_cast<int>(std::floor(portrait.width / panel));
        double off = 4.0;
        for (int width = under; width <= under + 1; ++width) {
            const double left = portrait.left - width * kPortraitInset[0] / 64.0;
            const double miss = std::fabs(left - std::floor(left + 0.5)) + std::fabs(width * panel - portrait.width) / 2.0;
            if (miss < off) {
                off = miss;
                now.width = width;
                now.left = static_cast<int>(std::floor(left + 0.5));
            }
        }
        {
            const double lens = (kPortraitInset[0] - kPortraitHairline) / 64.0;      // the lens's inner edge
            const int left = static_cast<int>(std::ceil(now.left + now.width * lens - 0.05)) + 1;
            const int right = static_cast<int>(std::floor(now.left + now.width * (1.0 - lens) + 0.05)) - 1;
            if ((left > portrait.left || right < portrait.left + portrait.width) && right - left > 8) {
                const int less = portrait.width - (right - left);
                portrait = {left, portrait.top + less / 2, right - left, portrait.height - less};
                for (const std::size_t part : kPartyPictures) SetExtent(Part(hud, part + at), portrait);
            }
        }
        now.height = nearest(portrait.height * 64.0 / (64.0 - 2 * kPortraitInset[1]));
        now.top = nearest(portrait.top + portrait.height / 2.0 - now.height / 2.0);
        SetExtent(frame, now);
        // The bars, on the frame's two sides and as tall as it: each as wide as its art is (16
        // to 64 of its height), reaching 9/78 of the frame's width into the frame.
        const int reach = nearest(now.width * 9.0 / 78.0);
        Extent bar{0, now.top, nearest(now.height * 16.0 / 64.0), now.height};
        bar.left = now.left + reach - bar.width;
        SetExtent(Part(hud, kPartyVitality + at), bar);
        bar.left = now.left + now.width - reach;
        SetExtent(Part(hud, kPartyForce + at), bar);
    }
}

// The part of the HUD a piece belongs to, or -1 (K1HudOptionsPolicy.h's XboxElementOf, whose
// offsets are Windows'): the combat strip across the top keeps its size, and anything else at the
// bottom left is the action menu.
int ElementOf(const Piece& piece) {
    if (piece.flags & kHide) return -1;
    if (piece.flags & kParty) return sizes::XboxParty;
    if (piece.flags & kRow) return -1;
    switch (piece.offset) {
        case 0x7640: case 0x7b20: return sizes::XboxMinimap;                               // LBL_MAPBORDER, BTN_MINIMAP
        case 0x1cb8: case 0x1e50: case 0x1fe8: case 0x2180: return sizes::XboxTargetBar;   // LBL_NAME(BG), LBL_HEALTHBG, PB_HEALTH
        // The disengage button and its queue: LBL_COMBATBG1, LBL_QUEUE0..3, BTN_CLEARONE(2).
        case 0x83c0: case 0x7d60: case 0x7ef8: case 0x8090: case 0x8228: case 0x8aa8: case 0x8ce8:
            return sizes::XboxDisengage;
    }
    return piece.side == kLeft && piece.edge == kBottom ? sizes::XboxActions : -1;
}

void ApplyXbox(void* hud, int width, int height) {
    // Each piece where the table puts it, then at its part's size about the part's corner. A
    // part's box is all its pieces on the screen; the portraits' combat-effect arrows, which the
    // engine keeps relative to their portrait, are sized from their own origin.
    HudSizes partSizes = Sizes();
    Extent placed[kPieceCount];
    bool seen[ElementCount] = {};
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        placed[i] = Placed(piece, g_layout.kept[i], width, height);
        const int element = ElementOf(piece);
        if (element < 0 || piece.side == kRelative) continue;
        const sizes::Rect r = AsRect(placed[i]);
        if (!seen[element]) { g_parts[element] = r; seen[element] = true; continue; }
        sizes::Rect& box = g_parts[element];
        const int right = std::max(box.left + box.width, r.left + r.width), bottom = std::max(box.top + box.height, r.top + r.height);
        box.left = std::min(box.left, r.left);
        box.top = std::min(box.top, r.top);
        box.width = right - box.left;
        box.height = bottom - box.top;
    }
    // Each part at its size, or as large as the screen holds it (FittingSize).
    for (int e = sizes::XboxActions; e < ElementCount; ++e)
        if (seen[e]) partSizes[e] = sizes::FittingSize(g_parts[e], sizes::CornerOf(e), partSizes[e], width, height);
    g_placedSizes = partSizes;
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        void* control = Part(hud, piece.offset);
        const int element = ElementOf(piece);
        Extent at = placed[i];
        if (element >= 0 && piece.side == kRelative) {
            const double f = sizes::Factor(partSizes[element]);
            at = {sizes::Round(at.left * f), sizes::Round(at.top * f), std::max(1, sizes::Round(at.width * f)),
                  std::max(1, sizes::Round(at.height * f))};
        } else if (element >= 0) {
            at = Sized(element, at);
        }
        SetExtent(control, at);
        for (int which = 0; which < 3; ++which) {
            const char* name = piece.*kArt[which];
            void* params = Dress(control, piece.kind, which);
            if (name && params) SetFillName(params, name);
        }
        if (piece.flags & kSetFont) SetFont(control, kLayoutFont);
    }
    FramePortraits(hud);
    // The box's upper half down to its lower one (build_xbox_hud.py, SEAM_OVERLAP).
    {
        void* upper = Part(hud, kHudMouldings);
        Extent box = At<Extent>(upper, kControlExtent);
        box.height = At<Extent>(Part(upper, 2 * kLabelSize), kControlExtent).top + kSeamOverlap - box.top;
        SetExtent(upper, box);
    }
    // The action description's bottom edge, which the box grows up from, with the action menu at
    // its size.
    {
        const int bottom = height - Scale(kLayoutHeight - kDescriptionBottom - kOutY, height);
        At<int>(hud, kHudDescriptionBottom) = Sized(sizes::XboxActions, {0, bottom, 1, 1}).top;
    }
    // The minimap is the size the game's own HUD has it. Its frame is fitted around the map
    // (the art's line ends 4 of its 64 in) and keeps the Xbox frame's top right corner; the
    // button and the rectangle the map is drawn in keep their places inside the frame. The game's
    // own HUD's map, as at 50% on KMRP's page, then at this HUD's minimap size, its button with it.
    {
        void* border = Part(hud, kHudMapBorder);
        void* button = Part(hud, kHudMapButton);
        Extent wasButton{};
        for (int i = 0; i < kPieceCount; ++i)
            if (kPieces[i].offset == kHudMapButton) wasButton = g_layout.kept[i].extent;
        const Extent xbox = At<Extent>(border, kControlExtent);
        const double mapScale = sizes::Factor(partSizes[sizes::XboxMinimap]) / sizes::Factor(PcMinimapSize());
        const int mapWidth = std::max(1, sizes::Round(g_layout.mapWindow[2] * mapScale));
        const int mapHeight = std::max(1, sizes::Round(g_layout.mapWindow[3] * mapScale));
        Extent frame{};
        frame.width = static_cast<int>(mapWidth * 64.0 / (64.0 - 2 * kMapFrameLine) + 0.5);
        frame.height = static_cast<int>(mapHeight * 64.0 / (64.0 - 2 * kMapFrameLine) + 0.5);
        frame.left = xbox.left + xbox.width - frame.width;
        frame.top = xbox.top;
        const int mapLeft = frame.left + (frame.width - mapWidth) / 2, mapTop = frame.top + (frame.height - mapHeight) / 2;
        SetExtent(border, frame);
        SetExtent(button, {mapLeft + sizes::Round((wasButton.left - g_layout.mapWindow[0]) * mapScale),
                           mapTop + sizes::Round((wasButton.top - g_layout.mapWindow[1]) * mapScale),
                           std::max(1, sizes::Round(wasButton.width * mapScale)),
                           std::max(1, sizes::Round(wasButton.height * mapScale))});
        int* map = &At<int>(hud, kHudMapWindow);
        map[0] = mapLeft;
        map[1] = mapTop;
        map[2] = mapWidth;
        map[3] = mapHeight;
    }
    g_messageRow = {0, Scale(kMessageRow[0], height), width, Scale(kMessageRow[1], height)};
    // The pad's two cues on the HUD, labels the patch's own layout adds (they are missing when
    // another patch's layout is loaded, and then there is nothing to do).
    void* queueCue = cues::Following(hud, kHudQueueButton);
    void* messageCue = cues::Following(hud, kHudMessage);
    if (!g_layout.cues) {
        g_layout.cues = true;
        if (queueCue) g_layout.queueCue = At<Extent>(queueCue, kControlExtent);
        if (messageCue)
            std::memcpy(g_layout.cueFill, &At<char>(messageCue, kLabelBorderParams + kParamsFill), kResRefBytes);
    }
    if (queueCue)
        SetExtent(queueCue, Sized(sizes::XboxDisengage,
                                  {width / 2 - Scale(kLayoutWidth / 2 - kQueueCue[0], height),
                                   height - Scale(kLayoutHeight - kQueueCue[1] - kOutY, height),
                                   Scale(kQueueCue[2], height), Scale(kQueueCue[3], height)}));
    if (messageCue) SetFillName(Part(messageCue, kLabelBorderParams), kDisengageFill);
    // The speech box: from just left of the target's bar, right under it. (The Mac's Draw
    // takes the screen's width less the safe margins in place of the kept width while
    // 0x100262E9A answers 0 for the in-game GUI; what that asks was not read.)
    if (int* bubble = BarkBubble()) {
        if (!g_layout.bubbleKept) {
            g_layout.bubbleKept = true;
            std::memcpy(g_layout.bubble, bubble, sizeof g_layout.bubble);
        }
        // With the target's bar at its size: the box stays under it.
        const Extent box = Sized(sizes::XboxTargetBar, {Scale(kBark[0] - kOutX, height), Scale(kBark[1], height),
                                                        Scale(kBark[2], height), 1});
        bubble[0] = box.left;
        bubble[1] = box.top;
        bubble[2] = box.width;
        g_layout.bubbleTop = box.top;  // Frame moves it down with the name bar
    }
    g_layout.xbox = true;
    g_layout.width = width;
    g_layout.height = height;
    g_layout.sizes = Sizes();          // as asked, to see a change; g_placedSizes holds them as drawn
    ReadRow(hud, height);
}

struct Row {
    void* hud = nullptr;
    int height = 0;        // the viewport height the row was read at
    int nameTop = 0, mapBorderTop = 0, mapButtonTop = 0, mapWindowTop = 0;   // as the layout has them
    Extent part[4]{};      // the first personal slot, as the layout has it
    int pitch = 0;
    bool usable = false;
} g_row;

// The layout's own geometry, read from the first two personal slots: nothing in the engine
// moves those. Read again for another HUD object or another screen height.
void ReadRow(void* hud, int height) {
    g_row = Row{};
    g_row.hud = hud;
    g_row.height = height;
    void* first = Part(hud, kHudPersonalActions);
    void* second = Part(first, kActionSize);
    for (int p = 0; p < 4; ++p) g_row.part[p] = At<Extent>(Part(first, kActionParts[p]), kControlExtent);
    // The table puts the first two personal slots three places apart (kTablePlaces).
    g_row.pitch = (At<Extent>(second, kControlExtent).left - g_row.part[0].left) / (kTablePlaces[1] - kTablePlaces[0]);
    g_row.nameTop = At<Extent>(Part(Part(hud, kHudTargetMenu), kMenuNameLabel), kControlExtent).top;
    g_row.mapBorderTop = At<Extent>(Part(hud, kHudMapBorder), kControlExtent).top;
    g_row.mapButtonTop = At<Extent>(Part(hud, kHudMapButton), kControlExtent).top;
    g_row.mapWindowTop = At<int>(hud, kHudMapWindowTop);
    // The Xbox layout has the frame at its scaled 41 px and a positive pitch. Anything else is
    // not that layout: leave it be.
    const int frame = Scale(kSmall[0][0], SizedHeight(sizes::XboxActions, height));
    g_row.usable = g_row.pitch > 0 && g_row.part[0].width >= frame - 1 && g_row.part[0].width <= frame + 1 &&
                   g_row.part[0].left >= 0 && g_row.part[0].top >= 0;
}

// The minimap's frame beside another patch that moves LBL_MAPBORDER inside the map's drawing,
// after the first hook (on Windows Scaled Kotor; here the Widescreen Patch has hooks further
// into 0x100237848). After the panel is drawn the frame is compared with where this file put
// it; if something moved it, the engine's frame is left without art while the Xbox layout is up
// and this file draws one around the map as it is.
Extent g_mapBorderSet{};
bool g_mapBorderForeign = false;

// What the first hook changes before each draw that the engine does not set again by itself:
// which slots it parked, the frames the engine last gave the target's slots, and the arrows it
// hid.
bool g_parked[kSlots] = {};
// Since this file draws a dim frame in every place with no slot shown (issue #55), an empty slot
// is never visible: a slot is shown exactly while its list has entries. What the PC HUD had is
// kept for RestorePc alone: whether a slot was visible when this layout hid it, so the mouse and
// keyboard HUD gets its empty frames back as the engine left them (K1XboxHud.cpp, g_pcShown).
// Until 2026-11-03 the Mac kept a parked slot's visibility and gave it back here too, which also
// brought back as visible a slot whose list had emptied meanwhile.
bool g_pcShown[kSlots] = {};
bool g_hidden[kSlots] = {};
void HideSlot(int slot, void* action) {
    if (!g_hidden[slot]) {
        g_pcShown[slot] = Visible(action);
        g_hidden[slot] = true;
    }
    Hide(action);
}
char g_engineFrame[kTargetSlots][2][kResRefBytes] = {};
bool g_arrowsHidden = false;

void* SlotAction(void* hud, int slot) {
    return slot < kTargetSlots ? Part(Part(Part(hud, kHudTargetMenu), kMenuActions), slot * kActionSize)
                               : Part(Part(hud, kHudPersonalActions), (slot - kTargetSlots) * kActionSize);
}

int SlotCount(void* hud, int slot) {
    return slot < kTargetSlots
               ? At<int>(Part(hud, kHudTargetMenu), kMenuActionLists + slot * kListStride + kListCount)
               : At<int>(hud, kHudPersonalLists + (slot - kTargetSlots) * kListStride + kListCount);
}

// The HUD as it was: every control back where the layout file and the engine had it, in its
// own art. `seen` is the target, or null.
void RestorePc(void* hud, void* seen) {
    void* menu = Part(hud, kHudTargetMenu);
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        const Kept& kept = g_layout.kept[i];
        void* control = Part(hud, piece.offset);
        SetExtent(control, kept.extent);
        // Every fill, not only the ones the table changes: the hooks borrow two parked
        // controls to draw with (LBL_MENUBG, BTN_MSG), and LBL_MENUBG is the dark backing of
        // the PC HUD's menu buttons.
        for (int which = 0; which < 3; ++which)
            if (void* params = Dress(control, piece.kind, which)) SetFill(params, kept.art[which]);
        if ((piece.flags & kSetFont) && kept.font[0]) SetFont(control, kept.font);
    }
    At<float>(Part(Part(hud, kHudSpareLabel), kLabelBorderParams), kParamsAlpha) = g_layout.spareAlpha;
    At<int>(hud, kHudDescriptionBottom) = g_layout.descriptionBottom;
    std::memcpy(&At<int>(hud, kHudMapWindow), g_layout.mapWindow, sizeof g_layout.mapWindow);
    std::memcpy(&At<int>(menu, kMenuOrigin), g_layout.menu, sizeof g_layout.menu);
    if (g_layout.cues) {
        if (void* cue = cues::Following(hud, kHudQueueButton)) SetExtent(cue, g_layout.queueCue);
        if (void* cue = cues::Following(hud, kHudMessage)) SetFill(Part(cue, kLabelBorderParams), g_layout.cueFill);
    }
    if (g_layout.bubbleKept)
        if (int* bubble = BarkBubble()) std::memcpy(bubble, g_layout.bubble, sizeof g_layout.bubble);
    g_mapBorderForeign = false;        // its art came back with the other controls', above
    // The slots. The engine frames a target's slots when the target changes, and shows a
    // slot's button and arrows when its contents change, not every frame.
    for (int slot = 0; slot < kSlots; ++slot) {
        void* action = SlotAction(hud, slot);
        if (slot < kTargetSlots) {
            if (g_engineFrame[slot][0][0]) SetFill(Part(action, kButtonBorderParams), g_engineFrame[slot][0]);
            if (g_engineFrame[slot][1][0]) SetFill(Part(action, kButtonHilightParams), g_engineFrame[slot][1]);
        }
        const int count = SlotCount(hud, slot);
        // A slot this layout hid comes back as the PC HUD had it: shown if its list has entries,
        // and an empty one as the engine left it (some it shows empty).
        if (g_hidden[slot]) {
            if (count > 0 || g_pcShown[slot]) Show(action);
            else Hide(action);
            g_hidden[slot] = false;
        }
        g_parked[slot] = false;
        if (slot == 0 && g_arrowsHidden && count > 1) {
            Show(Part(action, kActionParts[2]));
            Show(Part(action, kActionParts[3]));
        }
    }
    g_arrowsHidden = false;
    // The box's text was this file's ("Attack", "No Action"); the PC HUD has one only while a
    // slot is pointed at.
    String nothing;
    SetDescription(hud, &nothing);
    // The engine stacks the health bar and the slots under the name again.
    if (seen) UpdateNameLabel(menu, seen);
    g_first = FirstPlace{};
    g_nameSlices = NameSlices{};
    for (auto& member : g_bars)
        for (Bar& held : member) held = Bar{};
    g_layout.xbox = false;
}

Extent Centred(const Extent& on, int width, int height) {
    return {on.left + (on.width - width) / 2, on.top + (on.height - height) / 2, width, height};
}

// Centred on the box a slot's frame draws, which is not the middle of the frame's rectangle:
// the art has the box two and a half of its 64 pixels above its texture's middle and half a
// pixel left (kSlotBoxCentre).
Extent OnBox(const Extent& frame, int width, int height) {
    Extent at = Centred(frame, width, height);
    at.left += static_cast<int>(std::floor(frame.width * (kSlotBoxCentre[0] - 32.0) / 64.0 + 0.5));
    at.top += static_cast<int>(std::floor(frame.height * (kSlotBoxCentre[1] - 32.0) / 64.0 + 0.5));
    return at;
}

std::string Trimmed(const std::string& s) {
    const std::size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return std::string();
    return s.substr(first, s.find_last_not_of(" \t\r\n") - first + 1);
}

// [Hud] Style in the settings file, or empty: GetPrivateProfileString's part, read as
// rumble.cpp's IniValue reads [Rumble] (section and key without regard to case, the first of a
// key, `;` and `#` lines skipped).
std::string HudStyle() {
    const std::string path = standalone::SettingsPath();
    FILE* f = path.empty() ? nullptr : std::fopen(path.c_str(), "r");
    if (!f) return std::string();
    std::string style;
    bool ours = false;
    char buffer[1024];
    while (std::fgets(buffer, sizeof buffer, f)) {
        const std::string line = Trimmed(buffer);
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;
        if (line[0] == '[') {
            const std::size_t close = line.find(']');
            ours = close != std::string::npos && strcasecmp(Trimmed(line.substr(1, close - 1)).c_str(), "Hud") == 0;
            continue;
        }
        const std::size_t eq = line.find('=');
        if (!ours || eq == std::string::npos) continue;
        if (strcasecmp(Trimmed(line.substr(0, eq)).c_str(), "Style") != 0) continue;
        style = Trimmed(line.substr(eq + 1));
        break;
    }
    std::fclose(f);
    return style;
}

// ---- The pause notice.
//
// "Paused", or why the game paused itself, and how to go on: a panel of its own,
// CSWGuiInGamePause, with a label for the reason, a label under it for how to go on and a
// button over both for the mouse. Each time the game pauses, the HUD places it under the PC
// row's Equipment button (SetupPauseGuiExtent), which the Xbox layout parks, and
// SetPauseReason (0x1002E0BA4) lays it out in part: the reason's text and height, the second
// label two pixels under it and as tall as its own text (or hidden), the panel ending five
// pixels under the last label, the button on the reason's rectangle with the panel's height.
// With this HUD the notice stands left of the minimap and is one line, "PAUSED. PRESS [the
// button that pauses] TO CONTINUE", that button drawn on the panel's own button; the words are
// English and are used only where the game's own line is the English one.
//
// Two things are kept to give the box back (K1XboxHud.cpp says what went wrong with less): the
// layout's own places and widths, taken while the button has no trigger on it, and each reason
// the game writes with whether the second label was shown.
struct PauseOwn {
    bool valid = false;
    int reasonLeft = 0, reasonTop = 0, reasonWidth = 0;
    int pressLeft = 0, pressWidth = 0;
    int panelWidth = 0;
    char press[256] = {};
} g_pauseOwn;
struct PauseKept {
    bool kept = false;
    char reason[256] = {};
    bool pressShown = true;
} g_pauseKept;
bool g_pauseForget = false;        // PauseNotice is to forget what it last set
bool g_pauseStripped = false;      // KmrpXboxHudPauseReason took the picture off: the box is still this file's

// The pause button's two borders as pause.gui has them, kept while it shows the picture.
bool g_pauseButtonKept[2] = {};
float g_pauseButtonColour[2][3] = {};
std::uint8_t g_pauseButtonFlags[2] = {};

// Whether the box carries this file's line: its button has one of the pictures PauseNotice puts
// there, whichever family's (the fourth letter of the name): the button Pause is on (kmr?rm<code>,
// remap::Glyph). Any button, not only the one Pause is on now: a layout saved while the box is up
// leaves the old picture in it until PauseNotice sets the new one, and that box is still this
// file's. The right trigger's picture, kmrprt_pause until 1.6, is no longer shown.
bool PauseCarriesOurs(void* pause) {
    char fill[kResRefBytes + 1] = {};
    std::memcpy(fill, &At<char>(Part(Part(pause, kPauseButton), kButtonBorderParams), kParamsFill), 16);
    if (strncasecmp(fill, "kmr", 3) != 0 || !fill[3] || strncasecmp(fill + 4, "rm", 2) != 0) return false;
    for (const char* code : KmrpRemap::GlyphCodes)
        if (strcasecmp(fill + 6, code) == 0) return true;
    return false;
}

// The box as the game has it; true when there was something of this file's to undo.
bool RestorePauseNotice(void* pause) {
    if (!PauseCarriesOurs(pause)) return false;
    void* reason = Part(pause, kPauseReason);
    void* press = Part(pause, kPausePress);
    void* button = Part(pause, kPauseButton);
    if (g_pauseOwn.valid) {
        // The layout's places and widths first: a text is measured in its label's width.
        Extent first = At<Extent>(reason, kControlExtent);
        first.left = g_pauseOwn.reasonLeft;
        first.top = g_pauseOwn.reasonTop;
        first.width = g_pauseOwn.reasonWidth;
        SetExtent(reason, first);
        Extent second = At<Extent>(press, kControlExtent);
        second.left = g_pauseOwn.pressLeft;
        second.width = g_pauseOwn.pressWidth;
        SetExtent(press, second);
        if (g_pauseKept.kept) SetText(reason, g_pauseKept.reason);
        SetText(press, g_pauseOwn.press);
        // And SetPauseReason's own steps.
        first.height = TextHeight(Part(reason, text::kLabelText));
        SetExtent(reason, first);
        Extent last = first;
        if (!g_pauseKept.kept || g_pauseKept.pressShown) {
            Show(press);
            second.top = first.top + 2 + first.height;
            second.height = TextHeight(Part(press, text::kLabelText));
            SetExtent(press, second);
            last = second;
        } else {
            Hide(press);
        }
        Extent box = At<Extent>(pause, kControlExtent);
        box.width = g_pauseOwn.panelWidth;
        box.height = last.top + 5 + last.height;
        SetExtent(pause, box);
        SetExtent(button, {first.left, first.top, first.width, box.height});
    }
    // The button without the picture, its two borders as pause.gui has them.
    const char none[kResRefBytes] = {};
    int which = 0;
    for (const std::size_t border : {kButtonBorderParams, kButtonHilightParams}) {
        void* params = Part(button, border);
        SetFill(params, none);
        if (g_pauseButtonKept[which]) {
            std::memcpy(&At<float>(params, kParamsColour), g_pauseButtonColour[which], 3 * sizeof(float));
            At<std::uint8_t>(params, kParamsFlags) = g_pauseButtonFlags[which];
            g_pauseButtonKept[which] = false;
        }
        ++which;
    }
    g_pauseKept.kept = false;
    g_pauseForget = true;
    return true;
}

// The target's name frame as drawn, with the rows a long name adds: the frame's label, not
// LBL_NAMEBG of the HUD beneath it, which is narrower and ends inside the frame.
Extent g_nameFrameDrawn{};

// The pause notice as one line, made the way the combat-mode message is: the words before the
// picture in one label, the words after it in the other, the picture between them, each
// label's rectangle as wide as its words. Called before every draw while the Xbox layout is
// up: the game writes the reason and gives the three controls their rectangles anew every
// time it pauses, so everything set here is compared with what is there and set again when
// anything differs.
//
// `room` is what the screen leaves for the one line left of the minimap and `frameWidth` the
// target's name frame. True when the line did not fit there, so the box is laid out in two lines,
// frameWidth wide, for PlacePause to put under that frame (handoff item 136).
bool PauseNotice(void* pause, void* client, int room, int frameWidth) {
    static bool tried = false, english = false;
    if (!tried && client) {
        tried = true;
        String line;
        GetGuiString(&line, client, kPausePressString);
        const char* words = TextOf(line);
        english = words && strcasecmp(words, "PRESS THE PAUSE BUTTON TO CONTINUE") == 0;
        StringDestroy(&line);
    }
    if (!english) return false;
    void* reason = Part(pause, kPauseReason);
    void* press = Part(pause, kPausePress);
    void* button = Part(pause, kPauseButton);
    const char* const reasonNow = TextOf(At<String>(reason, kLabelTextParams));
    const char* const pressNow = TextOf(At<String>(press, kLabelTextParams));
    if (!reasonNow) return false;
    // The layout's own, while the box has nothing of this file's in it (PauseOwn).
    if (!PauseCarriesOurs(pause) && !g_pauseStripped) {
        const Extent r = At<Extent>(reason, kControlExtent), p = At<Extent>(press, kControlExtent);
        g_pauseOwn.valid = true;
        g_pauseOwn.reasonLeft = r.left;
        g_pauseOwn.reasonTop = r.top;
        g_pauseOwn.reasonWidth = r.width;
        g_pauseOwn.pressLeft = p.left;
        g_pauseOwn.pressWidth = p.width;
        g_pauseOwn.panelWidth = At<Extent>(pause, kControlExtent).width;
        std::snprintf(g_pauseOwn.press, sizeof g_pauseOwn.press, "%s", pressNow ? pressNow : "");
    }

    static char first[160] = {};                    // the words before the picture, as last set
    static const char second[] = "TO CONTINUE";
    static Extent set[4]{};                         // reason, press, button, panel, as last set
    static char familyShown[16] = {};               // the picture as last set
    static int roomShown = 0, frameShown = 0;       // what it was laid out for
    static bool stacked = false;                    // in two lines, as last set
    if (g_pauseForget) {
        g_pauseForget = false;
        first[0] = 0;
        familyShown[0] = 0;
        roomShown = frameShown = 0;
        for (Extent& one : set) one = Extent{};
    }
    // The button that pauses: LB, or the button Pause was moved to (remap.h).
    char pauses[16] = {};
    remap::Glyph(KmrpRemap::LB, prompts::FamilyLetter(), pauses);
    char family[kResRefBytes] = {};
    std::memcpy(family, pauses, sizeof pauses);
    const auto same = [](const Extent& x, const Extent& y) {
        return x.left == y.left && x.top == y.top && x.width == y.width && x.height == y.height;
    };
    const Extent panelNow = At<Extent>(pause, kControlExtent);
    if (first[0] && std::strcmp(reasonNow, first) == 0 && pressNow && std::strcmp(pressNow, second) == 0 &&
        same(At<Extent>(reason, kControlExtent), set[0]) && same(At<Extent>(press, kControlExtent), set[1]) &&
        same(At<Extent>(button, kControlExtent), set[2]) && panelNow.width == set[3].width &&
        panelNow.height == set[3].height && Visible(press) && std::memcmp(familyShown, pauses, sizeof pauses) == 0 && room == roomShown &&
        frameWidth == frameShown && !g_pauseStripped)
        return stacked;

    // A reason that is not this file's line is the game's, just written, and with it whether
    // the second label is shown (PauseKept).
    if (!(first[0] && std::strcmp(reasonNow, first) == 0)) {
        g_pauseKept.kept = true;
        std::snprintf(g_pauseKept.reason, sizeof g_pauseKept.reason, "%s", reasonNow);
        g_pauseKept.pressShown = Visible(press);
    }

    // The font's measures, from the first label's string as it is drawn.
    Measures measures;
    if (!MeasuresOf(reason, measures)) return false;
    const int lineHeight = measures.lineHeight;
    if (lineHeight <= 0) return false;

    // The words before the picture: the reason's first line (the PC puts "Press the Pause key
    // ..." on a second line for an enemy or a mine sighted), a full stop unless it ends in a
    // mark of its own, and "PRESS". A reason that is already this line, from the last pause,
    // is kept.
    if (!(first[0] && std::strcmp(reasonNow, first) == 0)) {
        char words[160] = {};
        const char* end = std::strchr(reasonNow, '\n');
        std::size_t n = end ? static_cast<std::size_t>(end - reasonNow) : std::strlen(reasonNow);
        if (n > 120) n = 120;
        while (n > 0 && reasonNow[n - 1] == ' ') --n;
        std::memcpy(words, reasonNow, n);
        const char last = n ? words[n - 1] : 0;
        std::strcpy(words + n, last == '.' || last == '!' || last == '?' ? " PRESS" : ". PRESS");
        std::memcpy(first, words, sizeof first);
        SetText(reason, first);     // reasonNow is the engine's old text and is not read again
    }
    if (!(pressNow && std::strcmp(pressNow, second) == 0)) SetText(press, second);
    Show(press);

    // One line: the picture as tall as the line and three eighths more, nine sixteenths of the
    // line between it and the words on either side, the line's height at the box's ends and a
    // third of it above and below the picture. A label's rectangle is its words' width and
    // half a line more on each side, so that the words, centred in it, cannot break.
    const int glyph = lineHeight + lineHeight * 3 / 8;
    const int gap = (lineHeight * 9 + 8) / 16;
    const int end = lineHeight, edge = lineHeight / 3, slack = lineHeight / 2;
    const int firstWide = Wide(measures, first);
    int secondWide = Wide(measures, second);
    // The second label in its own string's measures, where it has one.
    {
        Measures own;
        if (MeasuresOf(press, own)) {
            const int measured = Wide(own, second);
            if (measured > secondWide) secondWide = measured;
        }
    }
    const int top = edge + (glyph - lineHeight) / 2;
    set[0] = {end - slack, top, firstWide + 2 * slack, lineHeight};
    set[2] = {end + firstWide + gap, edge, glyph, glyph};
    set[1] = {set[2].left + glyph + gap - slack, top, secondWide + 2 * slack, lineHeight};
    Extent box = panelNow;
    box.width = set[1].left + slack + secondWide + end;
    box.height = glyph + 2 * edge;
    // Too wide for its place beside the name frame (800x600: over the frame, the maintainer saw
    // it on Windows, 2026-11-02): as wide as the frame, words above, picture and words below,
    // each centred.
    stacked = frameWidth > 0 && box.width > room;
    if (stacked) {
        const int below = edge + lineHeight + edge;
        const int across = (frameWidth - (glyph + gap + secondWide)) / 2;
        set[0] = {(frameWidth - firstWide) / 2 - slack, edge, firstWide + 2 * slack, lineHeight};
        set[2] = {across, below, glyph, glyph};
        set[1] = {across + glyph + gap - slack, below + (glyph - lineHeight) / 2, secondWide + 2 * slack, lineHeight};
        box.width = frameWidth;
        box.height = below + glyph + edge;
    }
    roomShown = room;
    frameShown = frameWidth;
    SetExtent(reason, set[0]);
    SetExtent(press, set[1]);
    SetExtent(button, set[2]);
    SetExtent(pause, box);
    set[3] = box;

    // The button's two borders are near black in pause.gui and draw a fill at its own size in
    // their middle; while the picture is shown they are white and stretch it over the button
    // (FILLSTYLE 2).
    int which = 0;
    for (const std::size_t border : {kButtonBorderParams, kButtonHilightParams}) {
        void* params = Part(button, border);
        float* colour = &At<float>(params, kParamsColour);
        std::uint8_t& flags = At<std::uint8_t>(params, kParamsFlags);
        if (!g_pauseButtonKept[which]) {
            g_pauseButtonKept[which] = true;
            std::memcpy(g_pauseButtonColour[which], colour, 3 * sizeof(float));
            g_pauseButtonFlags[which] = flags;
        }
        colour[0] = colour[1] = colour[2] = 1.0f;
        flags = static_cast<std::uint8_t>((flags & ~3u) | 2u);
        SetFill(params, family);
        ++which;
    }
    g_pauseStripped = false;
    Show(button);
    std::memcpy(familyShown, pauses, sizeof pauses);
    return stacked;
}

// The pause notice as this HUD has it and where: left of the minimap, level with the minimap's
// frame and as far from it as the frame is from the screen's edge.
void PlacePause(void* hud, void* pause, void* client, int width) {
    const Extent map = At<Extent>(Part(hud, kHudMapBorder), kControlExtent);
    // The frame's art has a clear edge, a 44th of its width on each side (measured on Windows at
    // 800x600 and 1280x720, 2026-11-02): the box takes the width that is drawn.
    Extent name = g_nameFrameDrawn;
    const int clear = name.width / 44;
    name.left += clear;
    name.width -= 2 * clear;
    const int margin = std::max(0, width - (map.left + map.width));
    const int room = map.left - margin - (name.left + name.width) - margin;
    const bool stacked = PauseNotice(pause, client, room, name.width);
    Extent& at = At<Extent>(pause, kControlExtent);
    if (stacked) {
        at.left = name.left;
        at.top = name.top + name.height + margin / 2;
    } else if (map.width > 0 && at.width > 0) {
        const int left = map.left - margin - at.width;
        at.left = left > 0 ? left : 0;
        at.top = map.top;
    }
}

// "No Action" (dialog.tlk 32236), which the box names when there is nothing to do; fetched once
// and kept.
String* NoActionName(void* client) {
    static String name;
    static bool fetched = false;
    if (!fetched && client) {
        GetGuiString(&name, client, kNoActionString);
        fetched = true;
    }
    return fetched ? &name : nullptr;
}

const int kListLimit = 1024;

int ListCount(void* list) {
    const int count = At<int>(list, kListCount);
    return count >= 0 && count <= kListLimit && LooksLikePointer(At<char*>(list, 0)) ? count : 0;
}

// The height of the tallest description of every action seen this session (K1XboxHud.cpp,
// TallestDescription; handoff item 65): each entry of the target's three lists and of the four
// personal lists the row shows, the default action and "No Action", remembered from draw to draw.
// The action box is that tall whichever is shown, so it keeps one height while the pad moves
// through them and never gets smaller during a session. A name is measured once, the way
// SetActionDescription measures the one it shows: set as the description label's text, the
// label's ideal height at its width. When the label's width or its font's measures change, every
// name seen is measured again. The label's own text is put back after measuring. The names are
// copied: the lists are made anew for every draw.
int TallestDescription(void* hud, void* menu, const char* usualEntry, String* none) {
    struct Measure {
        const void* info = nullptr;
        int lineHeight = 0;
        float texels = 0.0f, scale = 0.0f;
        int width = 0;
        bool operator==(const Measure& o) const {
            return info == o.info && lineHeight == o.lineHeight && texels == o.texels && scale == o.scale && width == o.width;
        }
    };
    static Measure measuredWith;
    static std::map<std::string, int> heights;      // every name seen; -1 while unmeasured
    static int tallest = 0;
    static bool unmeasured = false;
    void* label = Part(hud, kHudDescription);
    char* const object = At<char*>(Part(label, text::kLabelText), text::kTextObject);
    text::Font font{};
    if (!Readable(object, 0x60) || !text::FontOf(object, font)) return tallest;
    Measure now;
    now.info = font.upperLeft;
    now.lineHeight = font.lineHeight;
    now.texels = font.texels;
    now.scale = At<float>(object, text::kObjScale);
    now.width = At<Extent>(label, kControlExtent).width;
    if (!(now == measuredWith)) {
        for (auto& item : heights) item.second = -1;
        tallest = 0;
        unmeasured = !heights.empty();
        measuredWith = now;
    }

    // The names in the row now, remembered.
    auto remember = [&](const String* name) {
        const char* const words = name ? TextOf(*name) : nullptr;
        if (!words || !*words) return;
        const std::string text(words, strnlen(words, 1024));
        if (heights.find(text) == heights.end()) {
            heights.emplace(text, -1);
            unmeasured = true;
        }
    };
    auto rememberList = [&](void* list) {
        char* entries = At<char*>(list, 0);
        for (int i = 0, n = ListCount(list); i < n; ++i) remember(reinterpret_cast<const String*>(entries + i * kEntrySize));
    };
    for (int slot = 0; slot < kTargetSlots; ++slot) rememberList(Part(menu, kMenuActionLists + slot * kListStride));
    for (int slot = kTargetSlots; slot < kSlots; ++slot)
        rememberList(Part(hud, kHudPersonalLists + (slot - kTargetSlots) * kListStride));
    if (usualEntry) remember(reinterpret_cast<const String*>(usualEntry));
    remember(none);
    if (!unmeasured) return tallest;

    // Those not yet measured at this size.
    std::string shown;
    if (const char* was = TextOf(At<String>(label, kLabelTextParams))) shown.assign(was, strnlen(was, 4096));
    for (auto& item : heights) {
        if (item.second >= 0) continue;
        String copy{const_cast<char*>(item.first.c_str()), static_cast<std::uint32_t>(item.first.size())};  // SetText copies it
        SetText(label, &copy);
        const int measured = TextHeight(Part(label, text::kLabelText));
        item.second = measured > 0 ? measured : 0;
        tallest = std::max(tallest, item.second);
    }
    unmeasured = false;
    String back{shown.empty() ? nullptr : &shown[0], static_cast<std::uint32_t>(shown.size())};
    SetText(label, &back);
    return tallest;
}

// The first hook's work (K1XboxHud.cpp, KmrpXboxHudK1), before every draw of the HUD.
void Frame(void* hud) {
    void* menu = Part(hud, kHudTargetMenu);
    void* manager = At<void*>(hud, kHudManager);
    if (!LooksLikePointer(manager)) return;
    const int width = At<std::int16_t>(manager, kManagerViewportWidth);
    const int height = At<std::int16_t>(manager, kManagerViewportHeight);
    if (width <= 0 || height <= 0) return;

    void* client = Client();
    const bool target = (At<std::uint8_t>(menu, kMenuFlags) & 1) != 0;
    void* object = client && target ? GetGameObject(client, At<std::uint64_t>(hud, kHudTargetId)) : nullptr;
    void* seen = nullptr;
    {
        const std::uintptr_t vtable = Readable(object, 8) ? At<std::uintptr_t>(object, 0) : 0;
        if (LooksLikePointer(reinterpret_cast<void*>(vtable)))
            seen = reinterpret_cast<void* (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(vtable + kVtAsSWCObject))(object);
        if (!LooksLikePointer(seen)) seen = nullptr;
    }

    // The Xbox HUD while the pad is the device in use, the game's own otherwise.
    if (g_layout.hud != hud) Keep(hud);
    if (!device::PadInUse()) {
        const bool wasXbox = g_layout.xbox;
        if (g_layout.xbox) {
            CombatMessage(hud, client, width);
            RestorePc(hud, seen);
            if (g_layout.arrowMarginKept) {
                At<Extent>(Part(hud, kHudArrowMargin), kControlExtent) = g_layout.arrowMargin;
                g_layout.arrowMarginKept = false;
            }
        }
        // The pause notice as the game has it and where its own HUD has it. Looked at on every
        // frame, not only as the Xbox layout comes off: it costs one comparison of a name while
        // there is nothing to undo.
        if (void* pause = PausePanel()) {
            const bool undone = RestorePauseNotice(pause);
            if (undone || wasXbox) SetupPauseExtent(hud, &At<Extent>(pause, kControlExtent));
        }
        return;
    }
    // The game's own HUD is kept anew each time this layout takes it, not only at its first
    // sight: KMRP places that HUD itself and places it again when its sizes change, so what was
    // kept at first sight could be out of date by the time this layout gave it back.
    if (!g_layout.xbox) Keep(hud);
    if (!g_layout.xbox || g_layout.width != width || g_layout.height != height || g_layout.sizes != Sizes())
        ApplyXbox(hud, width, height);
    // Where the target's circle may stand. UpdateIndicator draws the marker as an arrow on the
    // edge of LBL_ARROW_MARGIN's rectangle when the target's point is outside it, and the
    // layout's rectangle is made for the PC HUD's bars; with this HUD it is the screen between
    // the target's name frame and the action box. Every frame: the name frame stands lower in
    // combat mode and the action box grows with its text.
    {
        const Extent name = At<Extent>(Part(hud, kHudNameFrame), kControlExtent);
        const Extent box = At<Extent>(Part(hud, kHudActionBox), kControlExtent);
        Extent& margin = At<Extent>(Part(hud, kHudArrowMargin), kControlExtent);
        const int top = name.top + name.height, bottom = box.top;
        const int side = name.left > 0 && name.left < width / 4 ? name.left : 0;
        if (bottom - top > height / 4) {
            if (!g_layout.arrowMarginKept) {
                g_layout.arrowMargin = margin;
                g_layout.arrowMarginKept = true;
            }
            margin = {side, top, width - 2 * side, bottom - top};
        }
    }
    // The target's circle at the Xbox's size: the engine's 16 to 64 pixels scaled by the
    // screen's height over 480, about its middle. The engine sets the label's rectangle
    // whenever it updates the indicator; a rectangle that is still the one set here has not
    // been updated since and is left.
    {
        void* marker = Part(hud, kHudMarker);
        static Extent set{};
        const Extent now = At<Extent>(marker, kControlExtent);
        char fill[kResRefBytes + 1] = {};
        std::memcpy(fill, &At<char>(Part(marker, kLabelBorderParams), kParamsFill), kResRefBytes);
        const bool circle = std::strstr(fill, "reticle") != nullptr;      // not the arrow on the rectangle's edge
        const bool ours = now.left == set.left && now.top == set.top && now.width == set.width && now.height == set.height;
        if (circle && !ours && now.width > 0 && height > kBaseHeight && Visible(marker)) {
            const int size = (2 * now.width * height + kBaseHeight) / (2 * kBaseHeight);
            set = {now.left + now.width / 2 - size / 2, now.top + now.height / 2 - size / 2, size, size};
            SetExtent(marker, set);
        }
    }
    // The pause notice left of the minimap: level with the minimap's frame and as far from it
    // as the frame is from the screen's edge. Every frame: the game places it anew whenever it
    // pauses, and the minimap stands lower in combat mode.
    if (void* pause = PausePanel()) PlacePause(hud, pause, client, width);
    if (!g_row.usable) return;

    // The menu's viewport starts at the screen's corner and is as wide as the screen. A clamp
    // rectangle no taller than the menu keeps the engine's placing of the menu (0x1002312E4)
    // from moving it between two draws.
    int* origin = &At<int>(menu, kMenuOrigin);
    origin[0] = 0;
    origin[1] = 0;
    At<int>(menu, kMenuWidth) = width;
    int* clamp = &At<int>(menu, kMenuClamp);
    clamp[0] = 0; clamp[1] = 0; clamp[2] = width; clamp[3] = 0;

    // The default action, the first place's. CClientExoAppInternal::GetDefaultActions makes a
    // one-entry list for the HUD's target with the action's name and icon, and returns without
    // touching its list when there is no target object, so that case is "No Action" here. (On
    // the Mac the engine calls it too; see the top of the file.)
    const int kind = At<signed char>(menu, kMenuTargetKind);
    char* usualEntry = nullptr;
    if (seen) {
        void* internal = engine::ClientInternal();
        if (LooksLikePointer(internal)) {
            GetDefaultActions(internal);
            char* list = At<char*>(internal, kDefaultActions);
            if (At<int>(internal, kDefaultActions + kListCount) > 0 && Readable(list, kEntrySize)) usualEntry = list;
        }
    }

    CombatMessage(hud, client, width);

    // The target's first list holds the default action too, where it is one of the target's
    // own actions. The slot keeps to the others: the second place is the feats, a door's lock,
    // a droid's repair.
    char* first = target ? At<char*>(menu, kMenuActionLists) : nullptr;
    int firstCount = first ? At<int>(menu, kMenuActionLists + kListCount) : 0;
    if (firstCount <= 0 || firstCount > kMostEntries || !Readable(first, firstCount * kEntrySize)) {
        first = nullptr;
        firstCount = 0;
    }
    int usual = -1;
    for (int i = 0; usualEntry && i < firstCount; ++i)
        if (At<int>(first + i * kEntrySize, kEntryId) == At<int>(usualEntry, kEntryId)) usual = i;
    const int others = firstCount - (usual >= 0 ? 1 : 0);
    const bool feats = others >= 1 && kind >= 0 && kind < 4;
    if (feats && usual >= 0) {
        int& chosen = At<int>(menu, kMenuChosen + kind * 3 * 4);
        int found = -1;
        for (int i = 0; i < firstCount; ++i)
            if (At<int>(first + i * kEntrySize, kEntryId) == chosen) found = i;
        // The engine's up and down walk the whole list and so reach the default action: coming
        // from the entry after it, it was going backwards, and is sent on to the entry before;
        // otherwise on to the entry after.
        static int last = -1;
        if (found < 0 || found == usual) {
            const int after = (usual + 1) % firstCount, before = (usual + firstCount - 1) % firstCount;
            const bool backwards = found == usual && last == At<int>(first + after * kEntrySize, kEntryId);
            char* entry = first + (backwards ? before : after) * kEntrySize;
            chosen = At<int>(entry, kEntryId);
            void* icon = Part(Part(menu, kMenuActions), kActionIcon);
            SetFill(Part(icon, kButtonBorderParams), entry + kEntryIcon);
            SetFill(Part(icon, kButtonHilightParams), entry + kEntryIcon);
        }
        last = chosen;
    }

    // The texts. The Xbox names the selected action in the box and keeps the target's name in
    // the name bar; the PC puts a target slot's action in the name bar and nothing in the box.
    // The slot the HUD holds as its active control, even while another screen has the input: the
    // one lit place (issue 56, handoff item 85).
    int focused = hud::FocusedSlot(hud);
    // A slot the game still holds after its list has emptied: after a cutscene, or as combat ends,
    // the game leaves its focus on a target slot with nothing in it. This layout hides an empty
    // slot (HideSlot), so the selection was nowhere to be seen, the first place was not lit
    // because a slot held the focus, and left and right started from the hidden slot's place at
    // the row's far end. The focus is let go of: the first place is the selection then, as
    // whenever no slot holds it, through the panel's own SetActiveControl, with no sound.
    if (focused >= 0 && SlotCount(hud, focused) <= 0) {
        SetActiveControl(hud, nullptr, 0);
        focused = -1;
    }
    // debug-logs=2: the row's state each time it changes (issue 56).
    static const bool rowLog = PatchOption("debug-logs", 0) >= 2;
    if (rowLog) {
        static char lastLine[160];
        char line[160];
        std::snprintf(line, sizeof line, "xbox row: focused %d, kind %d, target %d, first list %d, default at %d, feats %d, chosen %d",
                      focused, kind, target ? 1 : 0, firstCount, usual, feats ? 1 : 0,
                      kind >= 0 && kind < 4 ? At<int>(menu, kMenuChosen + kind * 3 * 4) : -1);
        if (std::strcmp(line, lastLine) != 0) {
            std::strcpy(lastLine, line);
            Log("%s", line);
        }
    }
    if (target && focused >= 0 && focused < kTargetSlots && kind >= 0 && kind < 4) {
        char* list = At<char*>(menu, kMenuActionLists + focused * kListStride);
        const int count = At<int>(menu, kMenuActionLists + focused * kListStride + kListCount);
        if (count > 0 && count <= kMostEntries && Readable(list, count * kEntrySize)) {
            char* entry = list;
            const int chosen = At<int>(menu, kMenuChosen + (kind * 3 + focused) * 4);
            for (int i = 0; i < count; ++i)
                if (At<int>(list + i * kEntrySize, kEntryId) == chosen) entry = list + i * kEntrySize;
            SetDescription(hud, entry);      // an entry begins with its name, a CExoString
        }
        if (seen) {
            char& named = At<char>(menu, kMenuNamedSlot);
            const char was = named;
            named = -1;
            UpdateNameLabel(menu, seen);
            named = was;
        }
    } else if (focused < 0) {
        if (usualEntry) {
            SetDescription(hud, usualEntry);
        } else if (String* none = NoActionName(client)) {
            SetDescription(hud, none);
        }
    }

    // The strip the Xbox game lays across the top of the screen in combat mode, with the
    // combat-mode message on it and a thin line in the text's blue along its lower edge; the
    // target's name bar and the minimap stand lower while it is there. It is there while the
    // engine shows the combat-mode message's label, and is drawn at once, before the panel,
    // with the spare label in two plain textures of the game's.
    const int actionHeight = SizedHeight(sizes::XboxActions, height);   // the action menu's lengths at its size
    const bool strip = Visible(Part(hud, kHudMessage));
    const int lower = strip ? Scale(kStripShift, height) : 0;
    if (strip) {
        void* label = Part(hud, kHudSpareLabel);
        void* fill = Part(label, kLabelBorderParams);
        const Extent was = At<Extent>(label, kControlExtent);
        float* colour = &At<float>(fill, kParamsColour);
        const float colourWas[3] = {colour[0], colour[1], colour[2]};
        StartLayer();
        if (SetupViewport(1.0f, 0, 0, width, height, kNoColouring, 0)) {
            const int bottom = Scale(kStripHeight, height);
            SetFill(fill, kStripFill);
            At<float>(fill, kParamsAlpha) = kStripAlpha;
            SetExtent(label, {0, 0, width, bottom});
            LabelDraw(label, 0.0f);
            SetFill(fill, kLineFill);
            At<float>(fill, kParamsAlpha) = 1.0f;
            std::memcpy(colour, kLineColour, sizeof kLineColour);
            SetExtent(label, {0, bottom - 2, width, 2});
            LabelDraw(label, 0.0f);
            std::memcpy(colour, colourWas, sizeof colourWas);
            CloseViewport();
        }
        StopLayer();
        SetExtent(label, was);
    }
    {
        void* border = Part(hud, kHudMapBorder);
        void* window = Part(hud, kHudMapButton);
        Extent at = At<Extent>(border, kControlExtent);
        at.top = g_row.mapBorderTop + lower;
        SetExtent(border, at);
        g_mapBorderSet = at;
        if (g_mapBorderForeign) SetFillName(Part(border, kLabelBorderParams), "");
        at = At<Extent>(window, kControlExtent);
        at.top = g_row.mapButtonTop + lower;
        SetExtent(window, at);
        At<int>(hud, kHudMapWindowTop) = g_row.mapWindowTop + lower;
    }

    // The name, its frame and the health bar. SetNameLabel shrinks the name to its text, gives
    // the background the same rectangle and stacks the bar right under it; the Xbox frame has
    // a fixed row for each. A name too long for one row keeps the height the engine gave it.
    void* nameLabel = Part(menu, kMenuNameLabel);
    Extent name = At<Extent>(nameLabel, kControlExtent);
    const int barHeight = SizedHeight(sizes::XboxTargetBar, height);
    const int nameRow = Scale(kNameHeight, barHeight);
    if (name.height < nameRow || name.top != g_row.nameTop + lower) {
        if (name.height < nameRow) name.height = nameRow;
        name.top = g_row.nameTop + lower;
        SetExtent(nameLabel, name);
    }
    auto fromName = [&](const int box[4]) {
        return Extent{name.left + Scale(box[0], barHeight), name.top + Scale(box[1], barHeight), Scale(box[2], barHeight),
                      Scale(box[3], barHeight)};
    };
    // Red around a hostile target's name. The engine's frame on the first target slot is the
    // sign; once the Xbox frame has replaced it, the last sign seen stands until the engine
    // writes another.
    static bool hostile = false;
    {
        const char* frame = &At<char>(Part(menu, kMenuActions), kButtonBorderParams + kParamsFill);
        if (strncasecmp(frame, kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) hostile = SameName(frame, kSlotHostile);
    }
    // A name taller than its row, on two lines or one at a large text size: the frame grows by
    // the difference and the health bar moves down by it (handoff item 69). The frame is then
    // drawn in three slices, so that only its plain middle stretches and its lines and ends stay
    // as they are: the second hook draws all three under the menu's controls, and the frame
    // label, covering them, has no art. A name that fits its row keeps the whole frame on the
    // label, as before.
    const int extra = name.height - nameRow;
    const Extent frame = fromName(kNameFrame);
    g_nameFrameDrawn = {frame.left, frame.top, frame.width, frame.height + std::max(0, extra)};
    void* frameLabel = Part(menu, kMenuNameBackground);
    g_nameSlices = NameSlices{};
    if (extra > 0) {
        const int split = name.top + Scale(kNameFrame[1] + kFrameSplit, barHeight);
        SetExtent(frameLabel, {frame.left, frame.top, frame.width, frame.height + extra});
        SetFillName(Part(frameLabel, kLabelBorderParams), "");
        g_nameSlices.draw = true;
        g_nameSlices.hostile = hostile ? 1 : 0;
        g_nameSlices.top = {frame.left, frame.top, frame.width, split - frame.top};
        g_nameSlices.middle = {frame.left, split, frame.width, extra};
        g_nameSlices.bottom = {frame.left, split + extra, frame.width, frame.top + frame.height - split};
        g_nameSlices.width = width;
        g_nameSlices.height = height;
    } else {
        SetExtent(frameLabel, frame);
        SetFill(Part(frameLabel, kLabelBorderParams), hostile ? kFrameHostile : kFrameFriendly);
    }
    Extent health = fromName(kHealthBar);
    health.top += std::max(0, extra);
    SetExtent(Part(menu, kMenuHealthBar), health);
    SetExtent(Part(menu, kMenuHealthBackground), health);
    // The speech box stays under the name bar: down with the combat strip and with a taller frame.
    if (int* bubble = BarkBubble())
        if (g_layout.bubbleKept) bubble[1] = g_layout.bubbleTop + lower + std::max(0, extra);

    // Its height: the whole screen. The engine ends the viewport at the health bar for a
    // target with no action, which hides the three slots.
    At<int>(menu, kMenuHeight) = height;
    const bool grenades = target && At<int>(menu, kMenuActionLists + kSharedTarget * kListStride + kListCount) != 0;

    // The action box, as tall as the tallest description of every action seen this session at the
    // text size in use (TallestDescription), whichever is shown, with the description in the middle
    // of that height. The engine sets the description, and its background, to its own text's
    // height on the edge it grows up from (SetActionDescription); it is moved only while it is
    // there, so it is moved once per text. kBoxEmptyLine is for a row with no action to measure.
    {
        const int tallest = TallestDescription(hud, menu, usualEntry, NoActionName(client));
        void* box = Part(hud, kHudMouldings);
        void* label = Part(hud, kHudDescription);
        Extent words = At<Extent>(label, kControlExtent);
        const int edge = At<int>(hud, kHudDescriptionBottom);
        const int band = std::max({tallest, words.height, tallest > 0 ? 0 : Scale(kBoxEmptyLine, actionHeight)});
        if (words.height > 0 && words.height < band && words.top + words.height == edge) {
            words.top = edge - band + (band - words.height) / 2;
            SetExtent(label, words);
            SetExtent(Part(hud, kHudDescriptionBack), words);
        }
        Extent wanted = At<Extent>(box, kControlExtent);
        const int bottom = wanted.top + wanted.height;
        wanted.top = edge - band - Scale(kBoxAboveText, actionHeight);
        wanted.height = bottom - wanted.top;
        if (wanted.height > 0 && wanted.top >= 0) SetExtent(box, wanted);
    }

    // The party's vitality bars in the Xbox HUD's curved art, and every visible bar emptied for
    // the panel's draw: the second hook draws it afterwards.
    for (int member = 0; member < 3; ++member) {
        void* fill = Part(hud, kHudParty + member * kPartySize + kPartyVitalityFill);
        const char* now = &At<char>(fill, kParamsFill);
        if (SameName(now, kFlatHealth)) SetFill(fill, kCurvedHealth);
        else if (SameName(now, kFlatPoison)) SetFill(fill, kCurvedPoison);
        for (int which = 0; which < 2; ++which) {
            void* bar = Part(hud, kHudParty + member * kPartySize + kPartyBars[which]);
            Bar& held = g_bars[member][which];
            held = Bar{};
            if (!Visible(bar)) continue;
            held.bar = bar;
            held.value = At<int>(bar, kBarValue);
            Hide(bar);     // not by the panel: the second hook draws it
        }
    }

    // The first place: the default action, selected while no slot has the focus.
    g_first = FirstPlace{};
    g_first.draw = true;
    g_first.selected = focused < 0;
    g_first.width = width;
    g_first.height = height;
    std::memcpy(g_first.icon, usualEntry ? usualEntry + kEntryIcon : kNoActionIcon, kResRefBytes);
    g_first.frame = g_row.part[0];
    g_first.picture = g_row.part[1];
    g_first.frame.left -= kTablePlaces[0] * g_row.pitch;
    g_first.picture.left -= kTablePlaces[0] * g_row.pitch;
    if (g_first.selected) {
        const Extent place = g_first.frame;
        g_first.frame = Centred(place, Scale(kLarge[0][0], actionHeight), Scale(kLarge[0][1], actionHeight));
        g_first.picture = OnBox(g_first.frame, Scale(kLarge[1][0], actionHeight), Scale(kLarge[1][1], actionHeight));
    } else {
        g_first.picture = OnBox(g_first.frame, g_first.picture.width, g_first.picture.height);
    }

    // The slots: each at its place in the row, the focused one large. Two pairs share a place
    // (kPlace): the grenades and the mines (grenades while the target offers any), and the
    // target's feats and the character's skills (the feats, with the skills joined to their end,
    // while the target has any; the skills alone otherwise).
    bool occupied[kRowPlaces + 1] = {};
    for (int slot = 0; slot < kSlots; ++slot) {
        void* action = SlotAction(hud, slot);
        const int shift = (kPlace[slot] - kTablePlaces[0]) * g_row.pitch;
        Extent part[4];
        for (int p = 0; p < 4; ++p) {
            part[p] = g_row.part[p];
            part[p].left += shift;
        }
        // The slot's button carries the focus, so it alone is made invisible while the slot is
        // parked, and visible again when the slot comes back: the engine sets that flag when a
        // slot's contents change, not every frame.
        if (slot == (grenades ? kSharedPersonal : kSharedTarget) || slot == (feats ? kSkillsSlot : kFeatsSlot)) {
            for (int p = 0; p < 4; ++p) {
                part[p].left = part[p].top = kParked;
                SetExtent(Part(action, kActionParts[p]), part[p]);
            }
            HideSlot(slot, action);
            g_parked[slot] = true;
            continue;
        }
        // Shown exactly while its list has entries, whether it was parked or not (g_pcShown): the
        // pad cannot choose an empty slot, and its place gets the dim frame below.
        if (SlotCount(hud, slot) <= 0) {
            HideSlot(slot, action);
        } else if (g_hidden[slot]) {
            Show(action);
            g_hidden[slot] = false;
        }
        g_parked[slot] = false;
        // The engine hides a slot whose list is empty.
        if (Visible(action)) occupied[kPlace[slot]] = true;
        const Extent frame = part[0];
        const int (*size)[2] = slot == focused ? kLarge : kSmall;
        if (slot == focused) {
            part[0] = Centred(frame, Scale(size[0][0], actionHeight), Scale(size[0][1], actionHeight));
            for (int p = 1; p < 3; ++p)
                part[p] = OnBox(part[0], Scale(size[p][0], actionHeight), Scale(size[p][1], actionHeight));
            part[3] = {part[2].left, part[2].top + part[2].height / 2, part[2].width, part[2].height - part[2].height / 2};
        } else {
            part[1] = OnBox(frame, part[1].width, part[1].height);     // a small slot's picture, in its box's middle too
        }
        if (slot < kTargetSlots) {
            // A target slot's frame is the engine's, lbl_miscroll_h or lbl_miscroll_f; the Xbox
            // game frames a target's slots like the others.
            void* normal = Part(action, kButtonBorderParams);
            void* selected = Part(action, kButtonHilightParams);
            if (strncasecmp(&At<char>(normal, kParamsFill), kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) {
                std::memcpy(g_engineFrame[slot][0], &At<char>(normal, kParamsFill), kResRefBytes);
                SetFill(normal, kSlotFrame);
            }
            if (strncasecmp(&At<char>(selected, kParamsFill), kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) {
                std::memcpy(g_engineFrame[slot][1], &At<char>(selected, kParamsFill), kResRefBytes);
                SetFill(selected, kSlotFrameSelected);
            }
        }
        // The selected slot's arrows are yellow on the Xbox, the others' blue. The arrow strip
        // is on the up button (build_xbox_hud.py).
        SetFill(Part(Part(action, kActionParts[2]), kButtonBorderParams), slot == focused ? kArrowsSelected : kArrows);
        for (int p = 0; p < 4; ++p) SetExtent(Part(action, kActionParts[p]), part[p]);
        // With the default action and one feat, the slot has nothing to walk through.
        if (slot == kFeatsSlot && others == 1) {
            g_arrowsHidden = true;
            Hide(Part(action, kActionParts[2]));
            Hide(Part(action, kActionParts[3]));
        }
    }
    // Every place with no slot shown: a dim frame, which the second hook draws.
    g_first.empties = 0;
    for (int place = 1; place <= kRowPlaces; ++place) {
        if (occupied[place]) continue;
        Extent dim = g_row.part[0];
        dim.left += (place - kTablePlaces[0]) * g_row.pitch;
        g_first.empty[g_first.empties++] = dim;
    }
}

// The second hook's work (K1XboxHud.cpp, KmrpXboxHudBarsK1), right after the panel is drawn:
// the first place of the action row, and the filled part of each party bar the first hook
// emptied. A bar on the Xbox empties from the top and keeps its curve; the PC's progress bar
// gives its fill the rectangle of the filled part and stretches the texture into it. So the
// bar is drawn here whole, through a viewport that is the filled part's rectangle, the way the
// engine itself clips the target menu.
void Bars(void* menu) {
    // The name frame's three slices (a name taller than its row), drawn before the menu draws the
    // name and the health bar over them, and only while it shows the frame, with LBL_MENUBG in
    // the frame label's colour and strength. Each slice's texture is told to clamp right after it
    // is drawn, as the party bars' are: the engine samples with wrap, and a dark line crossed the
    // frame's sides at both joins on Windows (the maintainer's capture, 2026-10-19).
    if (g_nameSlices.draw) {
        const NameSlices slices = g_nameSlices;
        g_nameSlices.draw = false;
        void* hud = At<void*>(menu, kMenuInterface);
        void* own = Part(menu, kMenuNameBackground);
        if (VtableOf(hud) == kHudVtable && hud == g_layout.hud && Visible(own)) {
            void* label = Part(hud, kHudSpareLabel);
            void* fill = Part(label, kLabelBorderParams);
            void* ownFill = Part(own, kLabelBorderParams);
            const Extent was = At<Extent>(label, kControlExtent);
            float* colour = &At<float>(fill, kParamsColour);
            const float colourWas[3] = {colour[0], colour[1], colour[2]};
            const float alphaWas = At<float>(fill, kParamsAlpha);
            std::memcpy(colour, &At<float>(ownFill, kParamsColour), sizeof colourWas);
            At<float>(fill, kParamsAlpha) = At<float>(ownFill, kParamsAlpha);
            StartLayer();
            if (SetupViewport(1.0f, 0, 0, slices.width, slices.height, kNoColouring, 0)) {
                const Extent* const where[3] = {&slices.top, &slices.middle, &slices.bottom};
                for (int i = 0; i < 3; ++i) {
                    SetFill(fill, kFrameSlices[slices.hostile][i]);
                    SetExtent(label, *where[i]);
                    LabelDraw(label, 0.0f);
                    ClampBoundTexture();
                }
                CloseViewport();
            }
            StopLayer();
            std::memcpy(colour, colourWas, sizeof colourWas);
            At<float>(fill, kParamsAlpha) = alphaWas;
            SetExtent(label, was);
        }
    }
    // The first place of the action row, and the dim frame of every place with no slot shown.
    if (g_first.draw) {
        const FirstPlace first = g_first;
        g_first.draw = false;
        void* hud = At<void*>(menu, kMenuInterface);
        if (VtableOf(hud) == kHudVtable && hud == g_layout.hud) {
            void* label = Part(hud, kHudSpareLabel);
            void* button = Part(hud, kHudSpareButton);
            void* frame = Part(label, kLabelBorderParams);
            const Extent labelWas = At<Extent>(label, kControlExtent), buttonWas = At<Extent>(button, kControlExtent);
            StartLayer();
            // The minimap's frame, when another patch has taken the engine's away.
            Extent mapFrame{};
            {
                const Extent now = At<Extent>(Part(hud, kHudMapBorder), kControlExtent);
                if (!g_mapBorderForeign && (now.left != g_mapBorderSet.left || now.top != g_mapBorderSet.top ||
                                            now.width != g_mapBorderSet.width || now.height != g_mapBorderSet.height))
                    g_mapBorderForeign = true;
                const int* map = &At<int>(hud, kHudMapWindow);
                const int* was = g_layout.mapWindow;
                if (g_mapBorderForeign && was[2] > 0 && was[3] > 0) {
                    // Around the map as it stands now, as ApplyXbox fits it.
                    mapFrame.width = static_cast<int>(map[2] * 64.0 / (64.0 - 2 * kMapFrameLine) + 0.5);
                    mapFrame.height = static_cast<int>(map[3] * 64.0 / (64.0 - 2 * kMapFrameLine) + 0.5);
                    mapFrame.left = map[0] - (mapFrame.width - map[2]) / 2;
                    mapFrame.top = map[1] - (mapFrame.height - map[3]) / 2;
                }
            }
            if (SetupViewport(1.0f, 0, 0, first.width, first.height, kNoColouring, 0)) {
                if (mapFrame.width > 0 && mapFrame.height > 0) {
                    SetFill(frame, kMapFrame);
                    SetExtent(label, mapFrame);
                    LabelDraw(label, 0.0f);
                }
                if (first.empties > 0) {
                    SetFill(frame, kSlotFrame);
                    At<float>(frame, kParamsAlpha) = 0.5f;
                    for (int i = 0; i < first.empties && i < kRowPlaces; ++i) {
                        SetExtent(label, first.empty[i]);
                        LabelDraw(label, 0.0f);
                    }
                    At<float>(frame, kParamsAlpha) = 1.0f;
                }
                SetFill(frame, first.selected ? kSlotFrameSelected : kSlotFrame);
                SetExtent(label, first.frame);
                LabelDraw(label, 0.0f);
                SetFill(Part(button, kButtonBorderParams), first.icon);
                SetExtent(button, first.picture);
                ButtonDraw(button, 0.0f);
                CloseViewport();
            }
            StopLayer();
            SetExtent(label, labelWas);
            SetExtent(button, buttonWas);
        }
    }
    for (auto& member : g_bars) {
        for (int which = 0; which < 2; ++which) {
            Bar& held = member[which];
            if (!held.bar) continue;
            void* bar = held.bar;
            const int value = held.value;
            held = Bar{};
            const Extent whole = At<Extent>(bar, kControlExtent);
            const int most = At<int>(bar, kBarMost);
            Show(bar);
            if (most <= 0 || whole.width <= 2 || whole.height <= 0) continue;
            // The empty bar, then its filling through a viewport that is the filled part's
            // rectangle.
            const int filled = value <= 0 ? 0 : value >= most ? whole.height : whole.height * value / most;
            auto part = [&](std::size_t piece, int rows) {
                if (rows <= 0) return;
                StartLayer();
                if (SetupViewport(1.0f, whole.left, whole.top + whole.height - rows, whole.width, rows, kNoColouring, 0)) {
                    // The bar full, placed so that its lower `rows` rows are the viewport's.
                    SetExtent(bar, {0, rows - whole.height, whole.width, whole.height});
                    SetBarValue(bar, most);
                    BorderDraw(Part(bar, piece), 0.0f);
                    ClampBoundTexture();
                    CloseViewport();
                }
                StopLayer();
            };
            part(kBarBorder, whole.height);
            part(kBarFill, filled);
            SetExtent(bar, whole);
            SetBarValue(bar, value);
        }
    }
}

// ---- The row's lists, shaped as the Xbox's six places (kPlace; issues #55, #50; handoff items 52
// and 58, the second replacing the first's hook).
//
// The lists are the engine's, made anew for every draw: CSWGuiMainInterface::PopulateMenus
// (0x10023725E) empties the six personal lists, fills each from CSWCCreature::GetPersonalActions
// (0x1002A54E8: the character's own Force powers, then the usable items of kinds 1, 4 and 2), and
// calls CSWGuiTargetActionMenu::PopulateMenus (0x1002310E6), which fills the target's three lists
// and then shows the target's slots by them; the personal slots are shown after it returns. This
// is hooked in that routine after its loop has filled the target's lists and before it shows any
// slot (KmrpXboxHudLists). Only while the Xbox layout is the one shown: with mouse or keyboard
// every list is the game's own.
//
//   - the other usable items (the third personal list) are joined to the end of the medical items
//     (the second): the Xbox has one place for defensive items;
//   - the third personal list, so emptied, holds the skills: Stealth, while it can be used. With
//     no target it is the second place;
//   - with a target, Stealth is joined to the end of the target's first list as well, whose other
//     entries are the feats: the second place is "your feats and skills".
//
// An entry carries its own routine, and the game calls it the same way from any list:
// DoPersonalAction (0x100238EBA) and DoTargetAction (0x100231938) find the object the entry names
// (+0x28, through CClientExoApp::GetGameObject and its AsSWCObject), add the member pointer's
// adjustment (+0x20) and call [entry+0x18] with that, the entry's id in esi and the character in
// rdx. So a copied entry is used as from its own slot. An entry whose id the list already has is
// left out, so a chosen id names one entry.
//
// Stealth: condition and action are TB_STEALTH's own, the routine its press calls (0x10023558E):
// CSWCCreature::IsStealthCapable (0x1002A6042) and PartyMenuStealth (0x1002A38AE). The Windows
// routine takes two words off the stack, which ended the game on a first build there (handoff
// item 52); the Mac's is System V, reads only rdi and returns plainly, and the toggle passes it
// two zeros in esi and edx, as here. Name and icon are the skill's: dialog.tlk 325 and isk_stealth.
const auto GetParty = reinterpret_cast<void* (*)(void* app)>(0x10028bf42UL);                  // CClientExoApp::GetSWParty
const auto GetPlayerCharacter = reinterpret_cast<void* (*)(void* party)>(0x1002a70aeUL);      // CSWParty::GetPlayerCharacter
const auto IsStealthCapable = reinterpret_cast<int (*)(void* creature)>(0x1002a6042UL);
const auto PartyMenuStealth = reinterpret_cast<void (*)(void* creature, int, int)>(0x1002a38aeUL);
// CExoArrayList<CSWGuiInterfaceAction>::Allocate(int): the list's array remade with that capacity
// (+0x0C), its entries kept and the count left alone (GetDefaultActions, 0x1002FBD42, calls it).
const auto ActionsAllocate = reinterpret_cast<void (*)(void* list, int capacity)>(0x1002875b4UL);
const auto ActionClear = reinterpret_cast<void (*)(void* entry)>(0x10033aff0UL);              // CSWGuiInterfaceAction::Clear
const auto StringAssign = reinterpret_cast<void* (*)(void* to, const void* from)>(0x10034ce1eUL);  // CExoString::operator=
const auto ResRefAssign = reinterpret_cast<void (*)(void* resref, const char* name)>(0x100367afcUL);
const std::size_t kListCapacity = 0x0c;
const std::size_t kObjectId = 0x08;                // a client object's 64-bit id
const char kStealthIcon[] = "isk_stealth";
const int kStealthId = 0x10000002;                 // skill 2; a Force power's id is its number | 0x20000000

bool StealthCapable(void* creature) { return LooksLikePointer(creature) && IsStealthCapable(creature) != 0; }

// The entry's routine, called as a member of the character with the id and the character. Aligned
// because the low bit of a member pointer's routine marks a virtual one.
__attribute__((aligned(16))) void StealthChosen(void*, int, void* creature) {
    if (StealthCapable(creature)) PartyMenuStealth(creature, 0, 0);
}

bool ListHasId(void* list, int id) {
    char* entries = At<char*>(list, 0);
    for (int i = 0, count = ListCount(list); i < count; ++i)
        if (At<int>(entries + i * kEntrySize, kEntryId) == id) return true;
    return false;
}

// `count` more entries at a list's end, through the engine's own Allocate where its array is too
// small; the first of them, or null. Entries past the count are as the engine's array has them:
// constructed, and cleared by the engine before it emptied the list.
char* GrowList(void* list, int count) {
    const int had = At<int>(list, kListCount);
    if (had < 0 || had + count > kListLimit || count <= 0) return nullptr;
    if (!LooksLikePointer(At<char*>(list, 0)) || At<int>(list, kListCapacity) < had + count) ActionsAllocate(list, had + count);
    char* entries = At<char*>(list, 0);
    if (!LooksLikePointer(entries)) return nullptr;
    At<int>(list, kListCount) = had + count;
    return entries + had * kEntrySize;
}

// Every entry of `from` whose id `to` lacks, copied to the end of `to`: the name (a CExoString) by
// the engine's own assignment, the rest (id, routine, object, icon, flags, count) as plain data.
void JoinList(void* to, void* from) {
    char* source = At<char*>(from, 0);
    const int count = ListCount(from);
    int take[kListLimit], taking = 0;
    for (int i = 0; i < count; ++i)
        if (!ListHasId(to, At<int>(source + i * kEntrySize, kEntryId))) take[taking++] = i;
    char* entry = GrowList(to, taking);
    for (int k = 0; entry && k < taking; ++k, entry += kEntrySize) {
        const char* copied = source + take[k] * kEntrySize;
        StringAssign(entry, copied);
        std::memcpy(entry + kEntryId, copied + kEntryId, kEntrySize - kEntryId);
    }
}

// A list emptied as PopulateMenus empties one: each entry cleared, the count 0.
void EmptyList(void* list) {
    char* entries = At<char*>(list, 0);
    for (int i = 0, count = ListCount(list); i < count; ++i) ActionClear(entries + i * kEntrySize);
    At<int>(list, kListCount) = 0;
}

void AddStealth(void* list, void* creature, void* client) {
    if (ListHasId(list, kStealthId)) return;
    char* entry = GrowList(list, 1);
    if (!entry) return;
    String name;
    GetGuiString(&name, client, kStealthName);
    StringAssign(entry, &name);
    StringDestroy(&name);
    At<int>(entry, kEntryId) = kStealthId;
    void (*const routine)(void*, int, void*) = StealthChosen;
    std::memset(Part(entry, kEntryRoutine), 0, 16);
    std::memcpy(Part(entry, kEntryRoutine), &routine, sizeof routine);
    At<std::uint64_t>(entry, kEntryObject) = At<std::uint64_t>(creature, kObjectId);
    ResRefAssign(Part(entry, kEntryIcon), kStealthIcon);
    At<std::uint8_t>(entry, kEntryFlags) = static_cast<std::uint8_t>((At<std::uint8_t>(entry, kEntryFlags) & 0xe0) | 1);
    At<int>(entry, kEntryCount) = 1;
}

void ShapeLists(void* menu) {
    void* hud = At<void*>(menu, kMenuInterface);
    void* client = Client();
    if (VtableOf(hud) != kHudVtable || !client) return;
    void* medical = Part(hud, kHudPersonalLists + 1 * kListStride);
    void* skills = Part(hud, kHudPersonalLists + 2 * kListStride);     // the other usable items, until joined
    JoinList(medical, skills);
    EmptyList(skills);
    void* party = GetParty(client);
    void* creature = LooksLikePointer(party) ? GetPlayerCharacter(party) : nullptr;
    if (!StealthCapable(creature)) return;
    AddStealth(skills, creature, client);
    void* feats = Part(menu, kMenuActionLists + kFeatsSlot * kListStride);
    if (ListCount(feats) > 0) AddStealth(feats, creature, client);
}

}  // namespace

bool Enabled() {
    static const bool on = [] {
        const char* forced = std::getenv("KMRP_XBOX_HUD");
        bool chosen;
        const char* by;
        if (forced && std::strcmp(forced, "1") == 0) {
            chosen = true;
            by = "KMRP_XBOX_HUD";
        } else if (const int option = PatchOption("xbox-hud", -1); option >= 0) {
            chosen = option != 0;
            by = "the patch's option";
        } else {
            // The Xbox-style HUD is the controller's standard on the Mac (the maintainer,
            // 2026-10-07: "this is standard with controller"): on unless the settings file says
            // Style=PC. Windows' is off unless it says Style=Xbox.
            const std::string style = HudStyle();
            chosen = strcasecmp(style.c_str(), "PC") != 0;
            by = style.empty() ? "default" : "[Hud] Style";
        }
        if (chosen) Log("Xbox-style HUD: on, by %s", by);
        return chosen;
    }();
    return on;
}

void Forget(void* panel) {
    if (!panel || panel != g_layout.hud) return;
    g_layout = Layout{};
    g_row = Row{};
    g_first = FirstPlace{};
    g_nameSlices = NameSlices{};
    for (auto& member : g_bars)
        for (Bar& held : member) held = Bar{};
    for (bool& parked : g_parked) parked = false;
    for (bool& hidden : g_hidden) hidden = false;
    g_mapBorderForeign = false;
    std::memset(g_engineFrame, 0, sizeof g_engineFrame);
    g_arrowsHidden = false;
}

}  // namespace xboxhud
}  // namespace kmrp

// Whether this layout has the HUD, or takes it at its next draw (KmrpXboxHudOwnsK1): KMRP's module,
// which places the game's own HUD, leaves the HUD alone while it does. Asked for by name from
// the other module (dlsym), so this one has the Windows name too.
extern "C" __attribute__((visibility("default"))) int KmrpXboxHudOwnsK1() {
    using namespace kmrp::xboxhud;
    return Enabled() && (g_layout.xbox || kmrp::device::PadInUse()) ? 1 : 0;
}

// CSWGuiTargetActionMenu::PopulateMenus, after its loop has filled the target's three lists and
// before it shows any slot (0x100231179; Windows 0x0068947A, KmrpXboxHudListsK1). r14 is the menu
// from 0x100231173 on. Only while the Xbox layout is shown.
extern "C" __attribute__((visibility("default"))) void KmrpXboxHudLists(void* menu) {
    using namespace kmrp::xboxhud;
    if (!Enabled() || !g_layout.xbox || !kmrp::device::PadInUse() || !Readable(menu, kMenuFlags + 1)) return;
    ShapeLists(menu);
}

// The HUD's map drawing, entry (0x100237848; Windows CSWGuiMainInterface::DrawMap, 0x0068AB10,
// KmrpXboxHudK1): after everything that moves or re-dresses a control and before anything is
// drawn. rdi is the HUD.
extern "C" __attribute__((visibility("default"))) void KmrpXboxHud(void* hud) {
    using namespace kmrp::xboxhud;
    if (!Enabled() || VtableOf(hud) != kHudVtable) return;
    Frame(hud);
}

// The target menu's Draw, entry (0x100230EEE; Windows CSWGuiTargetActionMenu::Draw, 0x00685ED0,
// KmrpXboxHudBarsK1), which the HUD calls right after it has drawn its panel. rdi is the menu,
// at +0x100 of the HUD it points back to.
extern "C" __attribute__((visibility("default"))) void KmrpXboxHudBars(void* menu) {
    using namespace kmrp::xboxhud;
    if (!Enabled() || !Readable(menu, kMenuFlags + 1)) return;
    Bars(menu);
}

// CSWGuiInGamePause::SetPauseReason, entry (0x1002E0BA4): the game is about to write a reason
// and lay the box out its own way, which puts the button on the reason's rectangle with the
// panel's height. While the button carried the trigger's picture, stretched over it, the
// picture was drawn that size for the one frame before PauseNotice next ran (the maintainer,
// 2026-10-08, in a fight: the trigger "zoomed out very big every time" an action was queued
// while the game was paused). The picture comes off here and PauseNotice puts it back at its
// size; the box is still this file's meanwhile (g_pauseStripped), so its places are not taken
// for the layout's own.
extern "C" __attribute__((visibility("default"))) void KmrpXboxHudPauseReason(void* pause) {
    using namespace kmrp::xboxhud;
    if (!Enabled() || !Readable(pause, kPauseSize) || !PauseCarriesOurs(pause)) return;
    const char none[kResRefBytes] = {};
    void* button = Part(pause, kPauseButton);
    for (const std::size_t border : {kButtonBorderParams, kButtonHilightParams}) SetFill(Part(button, border), none);
    g_pauseStripped = true;
}

// CSWGuiInGamePause::SetPauseReason, its end (0x1002E0D04): the game has laid the box out its
// own way, two lines with the button over both. Frame only puts that right before the HUD's
// next draw, and the box could be drawn first: the maintainer's slow-motion film of 2026-10-08
// shows one frame with "TO CONTINUE" under the reason each time an action was queued in the
// first pause after a cutscene. The box is made this HUD's here, before anything can draw it.
// rbx is the box's button at this place.
extern "C" __attribute__((visibility("default"))) void KmrpXboxHudPauseReasonDone(void* button) {
    using namespace kmrp::xboxhud;
    if (!Enabled() || !LooksLikePointer(button)) return;
    void* pause = static_cast<char*>(button) - kPauseButton;
    if (!g_layout.xbox || !kmrp::device::PadInUse() || pause != PausePanel() || !Readable(g_layout.hud, 8)) return;
    PlacePause(g_layout.hud, pause, Client(), g_layout.width);
}
