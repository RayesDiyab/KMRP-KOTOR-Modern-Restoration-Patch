// The Xbox-style HUD's runtime half.
//
// While the pad is the device in use, the game's own HUD is laid out the way the
// Xbox game's mi8x6.gui lays out its own: tools/build_xbox_hud.py writes where each
// control goes and what it wears (K1XboxHudLayout.inc), and this file applies that
// to the live controls and takes it off again for the mouse and keyboard ("The
// layout, applied to the live controls", below). That is most of the HUD. What a
// layout cannot say, this file also does, before every draw:
//
// 1. The target's name, health bar and three action slots are one object,
//    CSWGuiTargetActionMenu, which the engine draws in its own viewport and moves to
//    wherever the target is on screen. On the Xbox they never move: the name is top
//    left, the slots are the first three of the row in the action box. So the menu's
//    origin is pinned to the screen's corner with a viewport as wide as the screen,
//    and its controls are laid out in screen coordinates.
//
//    The slots still need putting back every time the name changes. SetNameLabel
//    (0x00685AF0) re-stacks the health bar and the slots under the name from two
//    offsets Initialize (0x0068BF50) stored as single bytes; top left to bottom left
//    is more than 255 pixels, so the stored offset has wrapped and the slots land in
//    the wrong place. The first personal slot is an ordinary control nothing moves,
//    and the row is one pitch apart throughout, so the target slots are placed from
//    it.
//
// 2. The Xbox drew the slot under the cursor large (a 64 px frame around a 32 px
//    icon) and the others small (41 and 21). The layout holds the small size; the
//    slot with the focus is grown about its centre here.
//
// 3. The action box is as tall as its text, the name's frame is red for a hostile
//    target, and the party's vitality bars are the Xbox HUD's curved ones; each is
//    explained where it is done.
//
// All of it runs from one hook at the entry of CSWGuiMainInterface::DrawMap
// (0x0068AB10, ecx = the HUD). CSWGuiMainInterface::Draw (0x0068B4A0) does the HUD's
// updating itself (UpdatePortraits, PopulateMenus, the slots' Update) and then calls
// DrawMap, the panel's Draw and the target menu's Draw, in that order: DrawMap's
// entry is after everything that moves or re-dresses a control and before anything
// is drawn. Two other sites were tried on 2026-10-05. The target menu's Draw
// (0x00685ED0) is after the panel has been drawn, so the vitality bars, which
// UpdatePortraits re-fills with a flat colour every frame, were always drawn flat.
// The entry of Draw is before that updating, so the name bar and the target slots
// were put back where the engine stacks them.
//
// Documentation standard: see `docs/documentation-standard.md`.
#include <windows.h>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdio>

#include "KmrpOptions.h"

// K1XboxControls.cpp: which of the seven slots has the focus (0-2 the target's,
// 3-6 personal), or -1.
int KmrpFocusedActionSlotK1(void* mainInterface);
// K1XboxControlsXInput.cpp: the pad is the device in use. K1NativeJoystick.cpp: the
// cue label on a panel that follows the control at an offset.
bool IsControllerInputActiveK1();
void* KmrpGuiCueK1(void* panel, std::size_t follow);

namespace {

struct Extent { int left, top, width, height; };

// CSWGuiTargetActionMenu (size 0x1AF0), inside CSWGuiMainInterface at +0xBC.
constexpr std::ptrdiff_t kMenuActionLists = 0x00;      // CExoArrayList[3]: pointer, count, capacity
constexpr std::ptrdiff_t kMenuActions = 0x54;          // CSWGuiMainInterfaceAction[3]
constexpr std::ptrdiff_t kMenuOrigin = 0x15AC;         // x, y: where its viewport starts
constexpr std::ptrdiff_t kMenuWidth = 0x15B4;          // the viewport's width
constexpr std::ptrdiff_t kMenuHeight = 0x15B8;         // and height
constexpr std::ptrdiff_t kMenuClamp = 0x15BC;          // left, top, width, height it is kept inside
constexpr std::ptrdiff_t kMenuFlags = 0x1AEC;          // bit 0: there is a target, the menu is drawn
constexpr std::ptrdiff_t kMenuNameLabel = 0x15CC;
constexpr std::ptrdiff_t kMenuNameBackground = 0x170C;
constexpr std::ptrdiff_t kMenuHealthBackground = 0x184C;
constexpr std::ptrdiff_t kMenuHealthBar = 0x198C;
// CSWGuiMainInterface.
constexpr std::ptrdiff_t kHudTargetMenu = 0xBC;        // CSWGuiTargetActionMenu
constexpr std::ptrdiff_t kHudManager = 0x18;           // CSWGuiPanel's manager
constexpr std::ptrdiff_t kHudPersonalActions = 0x772C; // CSWGuiMainInterfaceAction[]
// Measured in the running game, 2026-10-05: the three LBL_MOULDING labels in tag
// order (the box, the curve, the box's lower strip), the action description, and in
// each of the three portrait slots the parameters of the vitality bar's fill.
constexpr std::ptrdiff_t kHudMouldings = 0x1BC8;       // CSWGuiLabel[3], 0x140 each
constexpr std::ptrdiff_t kLabelSize = 0x140;
constexpr std::ptrdiff_t kHudDescription = 0xA1D4;     // CSWGuiLabel
constexpr std::ptrdiff_t kHudParty = 0x1F88;           // CSWGuiMainInterfaceChar[3], 0xEA8 each
constexpr std::ptrdiff_t kPartySize = 0xEA8;
constexpr std::ptrdiff_t kPartyVitalityFill = 0x898;   // CSWGuiBorderParams of the bar's progress
// CSWGuiMainInterfaceAction (size 0x71C): four buttons.
constexpr std::ptrdiff_t kActionSize = 0x71C;
constexpr std::ptrdiff_t kActionParts[4] = {0x000, 0x1C4, 0x388, 0x54C};   // frame, icon, up, down
// CSWGuiManager.
constexpr std::ptrdiff_t kManagerViewportWidth = 0x6C;   // short
constexpr std::ptrdiff_t kManagerViewportHeight = 0x6E;  // short
// CSWGuiControl: vtable, then the extent; SetExtent is the vtable's second entry.
constexpr std::ptrdiff_t kControlExtent = 0x04;
// A control's border parameters (CSWGuiBorderParams): in a label, measured in the
// running game (the border repeats the control's extent at +0x60, its parameters
// follow); in a button, as K1XboxControls.cpp has it. The fill's name is 16 bytes
// at +0x40 of the parameters, and CSWGuiBorderParams::SetFillImage loads another.
constexpr std::ptrdiff_t kLabelBorderParams = 0x70;
constexpr std::ptrdiff_t kButtonBorderParams = 0x80;
constexpr std::ptrdiff_t kParamsFill = 0x40;
constexpr std::uintptr_t kSetFillImage = 0x00414C00;
// The name's frame for a friendly and for a hostile target, both in the game's data
// (mi8x6.gui names the first). The engine marks a hostile target by giving the
// target slots the frame lbl_miscroll_h (CSWGuiMainInterfaceAction::Update).
// (Since 2026-10-05 the Xbox HUD wears drawings of the game's frames, kmrx_*, made by
// tools/build_xbox_hud_art.py: the names below that begin so are those.)
constexpr char kFrameFriendly[16] = "kmrx_miindic01f";
constexpr char kFrameHostile[16] = "kmrx_miindic01e";
constexpr char kSlotHostile[16] = "lbl_miscroll_h";
// The vitality bar. The PC engine fills it with a flat colour, "redfill", or
// "greenfill" for a poisoned character (CSWGuiMainInterface::UpdatePortraits); the
// Xbox HUD's bar is the curved lbl_health, and the data has lbl_healthp beside it.
constexpr char kFlatHealth[16] = "redfill";
constexpr char kFlatPoison[16] = "greenfill";
constexpr char kCurvedHealth[16] = "kmrx_health";
constexpr char kCurvedPoison[16] = "kmrx_healthp";
// The action box is as tall as its text. Measured in the reference video
// (640x480 units): with the one-line "Attack" the box's top edge is at 364 and the
// text's line ends at 385, where maininterface.gui ends LBL_ACTIONDESC; the file's
// 90 px box, top 326, is the size for three lines. The PC engine already keeps the
// description's bottom there and grows it upward with its text, so the box's top
// follows the description's: 6 above it, and a 16 px line when there is no text.
constexpr int kBoxAboveText = 6;
constexpr int kBoxEmptyLine = 16;

constexpr int kSlots = 7;
constexpr int kTargetSlots = 3;
// mi8x6.gui (and maininterface.gui, the same sizes): the small and the large slot (LBH_BORDER1B/1, LBL_ICON1B/1,
// LBH_ARROW1B/1), and LBL_INDICATE around LBL_NAME. build_xbox_hud.py has the same.
constexpr int kBaseHeight = 480;   // the Xbox drew these pixel sizes on 480 lines (build_xbox_hud.py, SCALE_H)
constexpr int kSmall[3][2] = {{41, 41}, {21, 21}, {11, 41}};   // frame, icon, arrow
// The selected slot's arrow strip is the file's 16x64 drawn at 14x56, the same shape:
// at 64 the arrowheads stood three units clear of the bracket, and on the Xbox they
// touch it and reach a little outside the box (the maintainer's photograph of the
// Xbox game, and the reference video at 21:21, where the heads are 26 from the
// slot's centre).
constexpr int kLarge[3][2] = {{64, 64}, {32, 32}, {14, 56}};
// Six places for the PC's seven slots, as the Xbox row has six. The maintainer's
// frames of the Xbox game show its rule: the right-hand places are the character's
// own and stay (out of combat: a mine, medical, items), and the left-hand ones are
// the target's when there is one (attack, feats, a Force power, grenades), the
// fourth place changing from the mine to the grenade. With the PC's lists that is,
// from the left: the target's attacks and feats; the character's skills and friendly
// powers; the target's Force powers; the target's grenades while it offers any and
// the character's mines otherwise; medical items; other items. The Xbox has the
// plain attack in the first place and the feats in the second, which the PC keeps
// in one list. The slot of the shared place that is not shown is parked off the
// screen and made invisible, so that the focus cannot land on it.
// K1XboxControls.cpp walks the focus in this order (MoveFocus).
//
// Later the same day, after more of the maintainer's frames: the Xbox's first place
// is the target's default action alone ("Attack", "Open", or "No Action" without a
// target) and is the selected one whenever nothing else is; its second place is the
// target's other actions of that kind (the feats), or the character's skills when
// the target has none. The PC has the default action and the feats in one list (the
// target's first), and no slot for the default action: it is simply what the A
// button does while no slot has the focus. So here the first place is drawn by this
// file and stands for "no slot has the focus"; the target's first slot is kept off
// its first entry and shown in the second place when it has more than that entry,
// and the character's skills are there otherwise.
constexpr int kPlace[kSlots] = {1, 2, 3, 1, 4, 5, 3};
constexpr int kSharedTarget = 2;      // the grenade slot, of the seven
constexpr int kSharedPersonal = 6;    // the mines' slot
constexpr int kFeatsSlot = 0;         // the target's first slot
constexpr int kSkillsSlot = 3;        // the first personal slot
constexpr int kFirstPersonalPlace = 1;
constexpr int kForcePlace = 2;
// The target's lists (CExoArrayList<CSWGuiInterfaceAction>, three, at the menu's
// start), an entry's fields, and where the menu remembers which entry of each list
// is the chosen one: four kinds of target by three lists
// (CSWGuiTargetActionMenu::PopulateMenus, 0x00689410; DoTargetAction, 0x00689610).
constexpr std::ptrdiff_t kEntrySize = 0x38;
constexpr std::ptrdiff_t kEntryId = 0x08;
constexpr std::ptrdiff_t kEntryIcon = 0x20;
constexpr std::ptrdiff_t kMenuChosen = 0x24;           // int[4][3]
constexpr std::ptrdiff_t kMenuTargetKind = 0x1AEA;     // char
constexpr std::ptrdiff_t kMenuNamedSlot = 0x1AEB;      // char: the slot whose action the name bar shows
constexpr std::ptrdiff_t kMenuInterface = 0x15A8;      // CSWGuiMainInterface*
constexpr std::ptrdiff_t kHudTargetId = 0x64;
constexpr std::ptrdiff_t kHudPersonalLists = 0x74;     // CExoArrayList[6], as the target's
constexpr std::ptrdiff_t kActionIcon = 0x1C4;          // the slot's icon, a CSWGuiButton
// Two controls the Xbox layout has no use for, which draw the first place: the
// menu row's background label is its frame and the Messages button its icon.
constexpr std::ptrdiff_t kHudSpareLabel = 0xBE2C;      // LBL_MENUBG
constexpr std::ptrdiff_t kHudSpareButton = 0xB71C;     // BTN_MSG
constexpr std::ptrdiff_t kParamsAlpha = 0x0C;
constexpr std::uintptr_t kAppManager = 0x007A39FC;     // [[it] + 4] is CClientExoApp
constexpr std::uintptr_t kGetGameObject = 0x005ED580;  // CClientExoApp::GetGameObject(id)
constexpr std::uintptr_t kGetGuiString = 0x005EDEB0;   // CClientExoApp::GetGUIString(CExoString*, strref)
constexpr std::uintptr_t kStringDestroy = 0x005E5C20;  // CExoString::~CExoString
constexpr std::uintptr_t kSetDescription = 0x00685560; // CSWGuiMainInterface::SetActionDescription(CExoString*)
constexpr std::uintptr_t kUpdateNameLabel = 0x00685CB0;// CSWGuiTargetActionMenu::UpdateNameLabel(CSWCObject*)
constexpr std::uintptr_t kGetDefaultActions = 0x00620620;  // CClientExoAppInternal::GetDefaultActions()
constexpr std::ptrdiff_t kDefaultActions = 0x4C8;      // its list, in CClientExoAppInternal
constexpr int kNoActionString = 32236;                 // dialog.tlk: "No Action"
constexpr char kNoActionIcon[16] = "i_noaction";
constexpr int kParked = -4000;
// A target slot's frame is not the layout's art: the engine gives it lbl_miscroll_h
// (hostile, red) or lbl_miscroll_f (CSWGuiMainInterfaceAction::Update, 0x006858E0).
// The Xbox game frames a target's slots like the others, in lbl_mibox01 with
// lbl_mibox02 for the selected one (reference video: "Attack", "Open"), so those
// are put back before the draw. The red frame was the PC's sign of a hostile target;
// the name bar's red frame says it here.
constexpr char kSlotEnginePrefix[] = "lbl_miscroll";
constexpr char kSlotFrame[16] = "kmrx_mibox01";
constexpr char kSlotFrameSelected[16] = "kmrx_mibox02";
constexpr char kArrows[16] = "kmrx_miarrow01";
constexpr char kArrowsSelected[16] = "kmrx_miarrow02";
constexpr std::ptrdiff_t kButtonHilightParams = 0xF4;
constexpr int kNameHeight = 26;                                // LBL_NAME
constexpr int kNameFrame[4] = {-10, -14, 271, 64};             // LBL_INDICATE, from LBL_NAME's corner
constexpr int kHealthBar[4] = {1, 26, 247, 9};                 // PB_HEALTH, from the same corner

template <typename T> T& At(void* base, std::ptrdiff_t offset)
{
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

void* Part(void* base, std::ptrdiff_t offset) { return static_cast<char*>(base) + offset; }

void SetExtent(void* control, const Extent& wanted)
{
    Extent& now = At<Extent>(control, kControlExtent);
    if (now.left == wanted.left && now.top == wanted.top && now.width == wanted.width && now.height == wanted.height)
        return;
    using Fn = void(__thiscall*)(void*, const Extent*);
    Fn fn = reinterpret_cast<Fn>((*reinterpret_cast<void***>(control))[1]);
    fn(control, &wanted);
}

bool SameName(const char* a, const char* b)
{
    return _strnicmp(a, b, 16) == 0;
}

void SetFill(void* params, const char name[16])
{
    if (SameName(&At<char>(params, kParamsFill), name)) return;
    using Fn = void(__thiscall*)(void*, const char*, int);
    reinterpret_cast<Fn>(kSetFillImage)(params, name, 1);
}

// A layout length on this screen, rounding half up, as build_xbox_hud.py rounds.
int Scale(int value, int height)
{
    return value >= 0 ? (2 * value * height + kBaseHeight) / (2 * kBaseHeight)
                      : -((2 * -value * height + kBaseHeight) / (2 * kBaseHeight));
}

// CSWGuiProgressBar (0x150 bytes): its greatest and current value, its border (the
// empty bar) and its fill, each a CSWGuiBorder (Draw is 0x00417F60: the border's
// draw, then the fill's). In a portrait slot the vitality bar is at +0x7A8 and the
// force bar follows it.
constexpr std::ptrdiff_t kPartyBars[2] = {0x7A8, 0x8F8};
constexpr std::ptrdiff_t kBarMost = 0x5C;
constexpr std::ptrdiff_t kBarValue = 0x60;
constexpr std::ptrdiff_t kBarBorder = 0x68;
constexpr std::ptrdiff_t kBarFill = 0xDC;
constexpr std::uintptr_t kBarSetValue = 0x00417FB0;    // CSWGuiProgressBar::SetCurValue
constexpr std::ptrdiff_t kControlFlags = 0x44;
constexpr int kControlVisible = 2;
// What CSWGuiTargetActionMenu::Draw calls to clip its own drawing to a rectangle.
constexpr std::uintptr_t kStartLayer = 0x004591B0;     // AurGUIStartLayer
constexpr std::uintptr_t kStopLayer = 0x004592B0;      // AurGUIStopLayer
constexpr std::uintptr_t kSetupViewport = 0x004592F0;  // AurGUISetupViewport(x, y, w, h, colour, 0, 1.0)
constexpr std::uintptr_t kCloseViewport = 0x00459580;  // AurGUICloseViewport
constexpr std::uintptr_t kNoColouring = 0x0078D3D8;

// The party's bar art runs to the side edge of its texture (lbl_health2: the arc's
// outline is the texture's first column), and the engine samples a GUI texture with
// wrap, so the outer edge was mixed with the texture's far side: the arc's outer
// outline came out half as thick, and a faint dark tick stood at the top and bottom
// of that edge (the maintainer saw both, 2026-10-05). Right after a bar's piece is
// drawn its texture is still the one bound, and it is told to clamp at its edges; the
// setting belongs to the texture, so it holds from the next draw on. These four
// textures are used by nothing but this HUD.
void ClampBoundTexture()
{
    using GetInteger = void(__stdcall*)(unsigned, int*);
    using TexParameter = void(__stdcall*)(unsigned, unsigned, int);
    static const HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    static const GetInteger getInteger = gl ? reinterpret_cast<GetInteger>(GetProcAddress(gl, "glGetIntegerv")) : nullptr;
    static const TexParameter texParameter = gl ? reinterpret_cast<TexParameter>(GetProcAddress(gl, "glTexParameteri")) : nullptr;
    if (!getInteger || !texParameter) return;
    int bound = 0;
    getInteger(0x8069, &bound);                // GL_TEXTURE_BINDING_2D
    if (!bound) return;
    texParameter(0x0DE1, 0x2802, 0x812F);      // GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE
    texParameter(0x0DE1, 0x2803, 0x812F);      // GL_TEXTURE_WRAP_T
}

void SetBarValue(void* bar, int value)
{
    reinterpret_cast<void(__thiscall*)(void*, int)>(kBarSetValue)(bar, value);
}

// A bar emptied for the panel's draw, and the value to draw and give back.
struct Bar { void* bar = nullptr; int value = 0; };
Bar g_bars[3][2];

// The combat-mode message. On the PC it reads "COMBAT MODE engaged. Press the
// Disengage button to cancel." (dialog.tlk 48208), which names a button a pad does
// not have. The Xbox game's line is still in dialog.tlk, 42475: "COMBAT MODE
// engaged. <bbutton> to disengage.", and the PC engine draws no button for the
// token (it becomes a character the PC fonts leave blank). So while that message is up and the pad is in use, the line is the Xbox's
// with the pad's own disengage button in the token's place: the text before the
// token in the message label, right-aligned up to the button; the button, which is
// the X cue label (K1NativeJoystick.cpp shows it while the message is shown); and
// the text after it in the message's background label, left-aligned from the
// button. Any other message, and this one with the mouse in use, is the game's.
//
// CSWGuiMainInterface::SetCombatMessage (0x00687700) keeps the message's number at
// +0x7728. A label's text parameters are at +0xE8 (CSWGuiTextParams: the text, a
// number, the font, the colour at +0x1C and again at +0x2C, the opacity at +0x28,
// the alignment at +0x38; read in the running game), and its CSWGuiText at +0xD0,
// whose GetIdealWidthAndHeight (0x00414F10) gives a line's width to the nearest 10.
constexpr std::ptrdiff_t kHudMessageNumber = 0x7728;
constexpr std::ptrdiff_t kHudMessage = 0x735C;         // LBL_CMBTMODEMSG
constexpr std::ptrdiff_t kHudMessageBack = 0x749C;     // LBL_CMBTMSGBG
constexpr std::ptrdiff_t kLabelText = 0xD0;
constexpr std::ptrdiff_t kLabelTextParams = 0xE8;
constexpr std::ptrdiff_t kTextColour = 0x1C;           // three floats, opacity, three floats
constexpr std::ptrdiff_t kTextOpacity = 0x28;
constexpr std::uintptr_t kSetTextColour = 0x00414E10;  // CSWGuiTextParams::SetColor(Vector*)
constexpr unsigned kEngagedString = 48208;
constexpr int kEngagedPadString = 42475;
constexpr char kButtonCharacter = 0x11;             // what the engine makes of "<bbutton>"
constexpr std::uintptr_t kSetText = 0x00415E00;        // CSWGuiTextParams::SetText(CExoString*)
constexpr std::uintptr_t kTextHeight = 0x00414EB0;     // CSWGuiText::GetIdealHeight()
constexpr std::uintptr_t kMeasureText = 0x00414F10;    // CSWGuiText::GetIdealWidthAndHeight(CSWGuiExtent*)
constexpr std::uintptr_t kStringFromText = 0x005E5A90; // CExoString::CExoString(const char*)
constexpr int kButtonSize = 22;                        // pixels, beside a 16 px font
constexpr int kButtonGap = 9;

struct String { char* text = nullptr; unsigned length = 0; };   // CExoString

void SetText(void* label, String* text)
{
    reinterpret_cast<void(__thiscall*)(void*, String*)>(kSetText)(Part(label, kLabelTextParams), text);
}

int LineWidth(void* label)
{
    Extent measured{};
    reinterpret_cast<void(__thiscall*)(void*, Extent*)>(kMeasureText)(Part(label, kLabelText), &measured);
    return measured.width;
}

Extent g_messageRow{};     // the combat-mode message's row in the Xbox layout (ApplyXbox)

// Called before each draw while the Xbox layout is up, and once more as it is taken
// off, when the pad is no longer the device in use and the game's line comes back.
void CombatMessage(void* hud, void* client, int width)
{
    const Extent messageWas = g_messageRow, backWas = g_messageRow;
    static bool changed = false;
    static String before, after, nothing;
    static bool split = false, tried = false;
    void* message = Part(hud, kHudMessage);
    void* back = Part(hud, kHudMessageBack);
    void* button = KmrpGuiCueK1(hud, kHudMessage);
    if (!tried && client) {
        tried = true;
        String whole;
        reinterpret_cast<void*(__thiscall*)(void*, String*, int)>(kGetGuiString)(client, &whole, kEngagedPadString);
        // The engine has already turned the token into one character, 0x11, which is
        // the B button in the Xbox game's font (seen in the running game: "COMBAT MODE
        // engaged. [0x11] to disengage."); the PC fonts have nothing there.
        const char* token = whole.text ? std::strchr(whole.text, kButtonCharacter) : nullptr;
        if (token) {
            char left[256] = {}, right[256] = {};
            std::size_t n = static_cast<std::size_t>(token - whole.text);
            while (n > 0 && whole.text[n - 1] == ' ') --n;
            if (n < sizeof left) std::memcpy(left, whole.text, n);
            const char* rest = token + 1;
            while (*rest == ' ') ++rest;
            strncpy_s(right, rest, _TRUNCATE);
            using Make = void*(__thiscall*)(String*, const char*);
            reinterpret_cast<Make>(kStringFromText)(&before, left);
            reinterpret_cast<Make>(kStringFromText)(&after, right);
            reinterpret_cast<Make>(kStringFromText)(&nothing, "");
            split = before.text && after.text;
        }
        reinterpret_cast<void(__thiscall*)(String*)>(kStringDestroy)(&whole);
    }
    const bool engaged = split && button && IsControllerInputActiveK1() &&
        At<unsigned>(hud, kHudMessageNumber) == kEngagedString &&
        (At<int>(message, kControlFlags) & kControlVisible) != 0;
    void* messageText = Part(message, kLabelTextParams);
    void* backText = Part(back, kLabelTextParams);
    if (engaged) {
        // The first half keeps its centred text in a rectangle as wide as the text,
        // which ends it at the button; the second half's label starts its text at
        // its left. (Writing the alignment into the text parameters here changed
        // nothing on screen, 2026-10-05.) The second half takes the first's colour
        // and opacity, which the engine sets per message and fades.
        SetText(message, &before);
        SetText(back, &after);
        reinterpret_cast<void(__thiscall*)(void*, void*)>(kSetTextColour)(backText, Part(messageText, kTextColour));
        At<float>(backText, kTextOpacity) = At<float>(messageText, kTextOpacity);
        // The whole line centred: the two texts' widths, with the button between.
        const int first = LineWidth(message);
        const int total = first + kButtonGap + kButtonSize + kButtonGap + LineWidth(back);
        const int joint = (width - total) / 2 + first;
        SetExtent(message, {joint - first, messageWas.top, first, messageWas.height});
        SetExtent(button, {joint + kButtonGap, messageWas.top + (messageWas.height - kButtonSize) / 2, kButtonSize, kButtonSize});
        const int from = joint + kButtonGap + kButtonSize + kButtonGap;
        // The second label's text starts at its top left (the layout's alignment for
        // it, which the engine keeps), the first's is centred in its row: the second
        // is given the row the first's text is on. (Seen 2026-10-05: "to disengage."
        // eight pixels higher than "COMBAT MODE engaged.")
        const int line = reinterpret_cast<int(__thiscall*)(void*)>(kTextHeight)(Part(message, kLabelText));
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
        if (client && At<unsigned>(hud, kHudMessageNumber) == kEngagedString) {
            String own;
            reinterpret_cast<void*(__thiscall*)(void*, String*, int)>(kGetGuiString)(client, &own, static_cast<int>(kEngagedString));
            SetText(message, &own);
            reinterpret_cast<void(__thiscall*)(String*)>(kStringDestroy)(&own);
        }
    }
}

// The first place, as KmrpXboxHudK1 decided it and KmrpXboxHudBarsK1 draws it.
struct FirstPlace {
    bool draw = false, selected = false, dimForce = false;
    char icon[16] = {};
    Extent frame{}, picture{}, force{};
    int width = 0, height = 0;
} g_first;

// The strip the Xbox game lays across the top of the screen in combat mode, with the
// combat-mode message on it and a thin line in the text's blue along its lower edge;
// the target's name bar and the minimap stand below it while it is there (the
// maintainer's frames of the Xbox game: the strip ends 57 units down of 480, and the
// name bar and minimap are 26 lower than without it). The PC HUD has neither. The
// strip and line are drawn before the panel with the spare label, in two plain
// textures of the game's.
constexpr int kStripHeight = 44;        // the Xbox strip is 57; the maintainer asked for less (2026-10-05)
constexpr int kStripShift = 14;         // 26 on the Xbox, under its taller strip
constexpr float kStripAlpha = 0.55f;
constexpr float kLineColour[3] = {0.32f, 0.46f, 0.92f};   // the HUD text's blue (the layout's TEXT colour)
constexpr char kStripFill[16] = "blackfill";
constexpr char kLineFill[16] = "whitefill";
constexpr std::ptrdiff_t kParamsColour = 0x10;         // three floats
constexpr std::ptrdiff_t kHudMapBorder = 0x5CC0;       // LBL_MAPBORDER
constexpr std::ptrdiff_t kHudMapButton = 0x6098;       // BTN_MINIMAP
constexpr std::ptrdiff_t kHudMapWindowTop = 0x6084;    // the rectangle the map is drawn in: left, TOP, width, height

// ---- The layout, applied to the live controls.
//
// The game always loads its own HUD layout (or whatever layout another mod put in
// its place). While the pad is the device in use, each control is moved to its Xbox
// place for the screen the game is drawing and given its Xbox art; when the mouse or
// keyboard takes over, each is put back exactly as it was. Nothing is read from a
// layout file, so the screen's size and shape do not matter, and neither does which
// file the game loaded.
//
// tools/build_xbox_hud.py makes the table. A control is found by its offset in
// CSWGuiMainInterface, where the executable builds it whatever the file says.
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
#include "K1XboxHudLayout.inc"
constexpr int kPieceCount = static_cast<int>(sizeof kPieces / sizeof kPieces[0]);

// A progress bar's two CSWGuiBorders are at +0x68 and +0xDC, each with its
// parameters 0x14 in. A label's font: CSWGuiTextParams keeps the name the layout
// gave at +0x3C (20 bytes) and SetBaseFont (0x00415DD0) takes a new one, adds the
// letter the engine picks for the screen's width and the player's font option
// (CSWGuiManager::GetUpdatedFontName, 0x0040B360) and loads it, as the layout's
// loader does (decompiled, 2026-10-05).
constexpr std::ptrdiff_t kBarBorderParams = 0x7C;
constexpr std::ptrdiff_t kBarFillParams = 0xF0;
constexpr std::ptrdiff_t kTextFontName = 0x3C;
constexpr std::uintptr_t kSetBaseFont = 0x00415DD0;    // CSWGuiTextParams::SetBaseFont(CResRef*)
// What the HUD worked out from its layout when it was built, and keeps beside the
// controls: the bottom edge the action description grows up from
// (SetActionDescription, 0x00685560, reads +0xA454), and the rectangle the map is
// drawn in (+0x6080, LBL_MAPVIEW's in the layout file).
constexpr std::ptrdiff_t kHudDescriptionBottom = 0xA454;
constexpr std::ptrdiff_t kHudMapWindow = 0x6080;       // left, top, width, height
constexpr std::ptrdiff_t kHudQueueButton = 0x6CD0;     // BTN_CLEARONE, which the Y cue follows
// The box a line of speech or a notice appears in is a panel of its own,
// CSWGuiBarkBubble, which CGuiInGame holds at +0x4C. Its Draw (0x006A9CE0) puts it
// back, before every draw, on the rectangle its constructor copied from its layout
// file to +0x1A4 (left, top, width; the height follows the text), so that rectangle
// is what is changed here.
constexpr std::uintptr_t kGetInGameGui = 0x005ED690;   // CClientExoApp::GetInGameGui()
constexpr std::ptrdiff_t kInGameBarkBubble = 0x4C;
constexpr std::ptrdiff_t kBubbleExtent = 0x1A4;

int* BarkBubble()
{
    void* app = *reinterpret_cast<void**>(kAppManager);
    void* client = app ? At<void*>(app, 4) : nullptr;
    void* inGame = client ? reinterpret_cast<void*(__thiscall*)(void*)>(kGetInGameGui)(client) : nullptr;
    void* bubble = inGame ? At<void*>(inGame, kInGameBarkBubble) : nullptr;
    return bubble ? &At<int>(bubble, kBubbleExtent) : nullptr;
}

void* Dress(void* control, Kind kind, int which)     // 0 the fill, 1 the focused fill, 2 a bar's filling
{
    switch (kind) {
    case kLabel: return which == 0 ? Part(control, kLabelBorderParams) : nullptr;
    case kButton: return which == 0 ? Part(control, kButtonBorderParams) : which == 1 ? Part(control, kButtonHilightParams) : nullptr;
    case kProgress: return which == 0 ? Part(control, kBarBorderParams) : which == 2 ? Part(control, kBarFillParams) : nullptr;
    default: return nullptr;
    }
}

void SetFillName(void* params, const char* name)
{
    char padded[16] = {};      // the engine reads all 16 bytes of a resource's name
    for (int i = 0; i < 16 && name[i]; ++i) padded[i] = name[i];
    SetFill(params, padded);
}

void SetFont(void* label, const char* name)
{
    char padded[16] = {};
    for (int i = 0; i < 16 && name[i]; ++i) padded[i] = name[i];
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(kSetBaseFont)(Part(label, kLabelTextParams), padded);
}

struct Kept { Extent extent; char art[3][16]; char font[20]; };
struct Layout {
    void* hud = nullptr;
    bool xbox = false;
    int width = 0, height = 0;         // the screen the Xbox layout was applied for
    Kept kept[kPieceCount]{};
    int descriptionBottom = 0, mapWindow[4]{}, menu[8]{};
    Extent queueCue{};
    char cueFill[16]{};
    bool cues = false;
    int bubble[3]{};
    bool bubbleKept = false;
    float spareAlpha = 1.0f;           // of LBL_MENUBG's fill, which the hooks draw with
} g_layout;

const char* Piece::* const kArt[3] = {&Piece::fill, &Piece::hilight, &Piece::progress};

// The first sight of a HUD object, which is as its layout file and the engine made it.
void Keep(void* hud)
{
    g_layout = Layout{};
    g_layout.hud = hud;
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        void* control = Part(hud, piece.offset);
        Kept& kept = g_layout.kept[i];
        kept.extent = At<Extent>(control, kControlExtent);
        for (int which = 0; which < 3; ++which)
            if (void* params = Dress(control, piece.kind, which))
                std::memcpy(kept.art[which], &At<char>(params, kParamsFill), 16);
        if (piece.kind == kLabel) std::memcpy(kept.font, &At<char>(control, kLabelTextParams + kTextFontName), 20);
    }
    g_layout.spareAlpha = At<float>(Part(Part(hud, kHudSpareLabel), kLabelBorderParams), kParamsAlpha);
    g_layout.descriptionBottom = At<int>(hud, kHudDescriptionBottom);
    std::memcpy(g_layout.mapWindow, &At<int>(hud, kHudMapWindow), sizeof g_layout.mapWindow);
    std::memcpy(g_layout.menu, &At<int>(Part(hud, kHudTargetMenu), kMenuOrigin), sizeof g_layout.menu);
}

Extent Placed(const Piece& piece, const Kept& kept, int width, int height)
{
    const int x = piece.box[0], y = piece.box[1];
    const int w = Scale(piece.box[2], height), h = Scale(piece.box[3], height);
    if (piece.flags & kHide) return {kParked, kParked, kept.extent.width, kept.extent.height};
    if (piece.flags & kParty) {
        // The party's group, smaller about its bottom right corner (build_xbox_hud.py,
        // PARTY_SCALE). Lengths here need not be whole units, so they are scaled as
        // they are and rounded half up once.
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

// Each portrait's frame, put around the portrait as it stands in pixels, with its two
// bars. The table's rectangles for the three frames are the Xbox layout's, in whole
// units, and no two of them hold their portrait alike: scaled, one portrait showed a
// black strip of the frame's panel under it, one beside it, and the leader's none
// (the maintainer saw it, 2026-10-05). The frame's art has lines three pixels thick
// for this (tools/build_xbox_hud_art.py), and the frame is sized and placed here, the
// same way for all three. Above and below, the portrait's edge falls in the middle of
// the frame's line. At the sides the art has a black hairline between the picture and
// each lens, running from the frame's outline at the top to its outline at the bottom
// (the maintainer asked for it from a picture of the Xbox game, 2026-10-05, and for it
// to join the arcs' own black edges), and the portrait's side edges go exactly on the
// hairlines' inner edges. The frame is a whole number of pixels wide, so of the two
// widths nearest the exact one, the one that puts those edges closest is taken.
constexpr std::ptrdiff_t kPartyFrame = 0x1FB0, kPartyPortrait = 0x25F0;   // LBL_BACK1, LBL_CHAR1
constexpr std::ptrdiff_t kPartyVitality = 0x2730, kPartyForce = 0x2880;   // PB_VIT1, PB_FORCE1
// What shares the portrait's rectangle: LBL_CHAR1, BTN_CHAR1, LBL_DEBILATATED1, LBL_LVLUPBG1, LBL_LEVELUP1.
constexpr std::ptrdiff_t kPartyPictures[] = {0x25F0, 0x2C50, 0x20F0, 0x24B0, 0x2370};

void FramePortraits(void* hud)
{
    auto nearest = [](double v) { return static_cast<int>(v + 0.5); };
    for (int member = 0; member < 3; ++member) {
        const std::ptrdiff_t at = member * kPartySize;
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
        // The hairline is a share of the frame, and its edges seldom fall on a pixel's:
        // beside a small portrait (the two companions' at 1280x960) it came to under a
        // pixel, a grey smear on one side and nothing on the other. So the picture is
        // kept a whole pixel clear of each lens, counted from the first pixel the lens
        // does not touch: one full pixel of black shows on each side at any size, and
        // the picture gives up a pixel or two for it, in height as in width (the
        // maintainer's direction, 2026-10-05: "their pictures need to be smaller so
        // both lines are showing on both sides").
        {
            const double lens = (kPortraitInset[0] - kPortraitHairline) / 64.0;      // the lens's inner edge
            const int left = static_cast<int>(std::ceil(now.left + now.width * lens - 0.05)) + 1;
            const int right = static_cast<int>(std::floor(now.left + now.width * (1.0 - lens) + 0.05)) - 1;
            if ((left > portrait.left || right < portrait.left + portrait.width) && right - left > 8) {
                const int less = portrait.width - (right - left);
                portrait = {left, portrait.top + less / 2, right - left, portrait.height - less};
                for (const std::ptrdiff_t part : kPartyPictures) SetExtent(Part(hud, part + at), portrait);
            }
        }
        now.height = nearest(portrait.height * 64.0 / (64.0 - 2 * kPortraitInset[1]));
        now.top = nearest(portrait.top + portrait.height / 2.0 - now.height / 2.0);
        SetExtent(frame, now);
        // The bars, on the frame's two sides and as tall as it. Each is as wide as its
        // art is (16 to 64 of its height) and reaches 9/78 of the frame's width into
        // the frame, which is how the layout has the leader's. It has the companions'
        // bars wider for their height and further in, and their vitality arcs' ends
        // lay over the lens and onto the picture's corners (the maintainer saw it on
        // the second portrait, 2026-10-05), so all three are placed the leader's way.
        const int reach = nearest(now.width * 9.0 / 78.0);
        Extent bar{0, now.top, nearest(now.height * 16.0 / 64.0), now.height};
        bar.left = now.left + reach - bar.width;
        SetExtent(Part(hud, kPartyVitality + at), bar);
        bar.left = now.left + now.width - reach;
        SetExtent(Part(hud, kPartyForce + at), bar);
    }
}

void ApplyXbox(void* hud, int width, int height)
{
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        void* control = Part(hud, piece.offset);
        SetExtent(control, Placed(piece, g_layout.kept[i], width, height));
        for (int which = 0; which < 3; ++which) {
            const char* name = piece.*kArt[which];
            void* params = Dress(control, piece.kind, which);
            if (name && params) SetFillName(params, name);
        }
        if (piece.flags & kSetFont) SetFont(control, kLayoutFont);
    }
    FramePortraits(hud);
    // The box's upper half down to a pixel inside its lower one (build_xbox_hud.py).
    {
        void* upper = Part(hud, kHudMouldings);
        Extent box = At<Extent>(upper, kControlExtent);
        box.height = At<Extent>(Part(upper, 2 * kLabelSize), kControlExtent).top + kSeamOverlap - box.top;
        SetExtent(upper, box);
    }
    At<int>(hud, kHudDescriptionBottom) = height - Scale(kLayoutHeight - kDescriptionBottom - kOutY, height);
    // The minimap is the size the game's own HUD has it, so that it does not change
    // size with the device (the maintainer's direction, 2026-10-05; the Xbox layout's
    // is smaller, 109 px against 120 at 1024x768). Its frame keeps the Xbox frame's
    // top right corner, and the button and the rectangle the map is drawn in keep
    // their places inside the frame.
    {
        void* border = Part(hud, kHudMapBorder);
        void* button = Part(hud, kHudMapButton);
        Extent wasBorder{}, wasButton{};
        for (int i = 0; i < kPieceCount; ++i) {
            if (kPieces[i].offset == kHudMapBorder) wasBorder = g_layout.kept[i].extent;
            if (kPieces[i].offset == kHudMapButton) wasButton = g_layout.kept[i].extent;
        }
        const Extent xbox = At<Extent>(border, kControlExtent);
        const int left = xbox.left + xbox.width - wasBorder.width, top = xbox.top;
        SetExtent(border, {left, top, wasBorder.width, wasBorder.height});
        SetExtent(button, {left + wasButton.left - wasBorder.left, top + wasButton.top - wasBorder.top,
                           wasButton.width, wasButton.height});
        int* map = &At<int>(hud, kHudMapWindow);
        map[0] = left + g_layout.mapWindow[0] - wasBorder.left;
        map[1] = top + g_layout.mapWindow[1] - wasBorder.top;
        map[2] = g_layout.mapWindow[2];
        map[3] = g_layout.mapWindow[3];
    }
    g_messageRow = {0, Scale(kMessageRow[0], height), width, Scale(kMessageRow[1], height)};
    // The pad's two cues on the HUD, labels the patch's own layout adds (they are
    // missing when another mod's layout is loaded, and then there is nothing to do).
    void* queueCue = KmrpGuiCueK1(hud, kHudQueueButton);
    void* messageCue = KmrpGuiCueK1(hud, kHudMessage);
    if (!g_layout.cues) {
        g_layout.cues = true;
        if (queueCue) g_layout.queueCue = At<Extent>(queueCue, kControlExtent);
        if (messageCue) std::memcpy(g_layout.cueFill, &At<char>(messageCue, kLabelBorderParams + kParamsFill), 16);
    }
    if (queueCue)
        SetExtent(queueCue, {width / 2 - Scale(kLayoutWidth / 2 - kQueueCue[0], height),
                             height - Scale(kLayoutHeight - kQueueCue[1] - kOutY, height),
                             Scale(kQueueCue[2], height), Scale(kQueueCue[3], height)});
    if (messageCue) SetFill(Part(messageCue, kLabelBorderParams), kDisengageFill);
    // The speech box: from just left of the target's bar, right under it.
    if (int* bubble = BarkBubble()) {
        if (!g_layout.bubbleKept) {
            g_layout.bubbleKept = true;
            std::memcpy(g_layout.bubble, bubble, sizeof g_layout.bubble);
        }
        bubble[0] = Scale(kBark[0] - kOutX, height);
        bubble[1] = Scale(kBark[1], height);
        bubble[2] = Scale(kBark[2], height);
    }
    g_layout.xbox = true;
    g_layout.width = width;
    g_layout.height = height;
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

// The layout's own geometry, read from the first two personal slots: nothing in the
// engine moves those. Read again for another HUD object or another screen height.
void ReadRow(void* hud, int height)
{
    g_row = Row{};
    g_row.hud = hud;
    g_row.height = height;
    void* first = Part(hud, kHudPersonalActions);
    void* second = Part(first, kActionSize);
    for (int p = 0; p < 4; ++p) g_row.part[p] = At<Extent>(Part(first, kActionParts[p]), kControlExtent);
    // The first two personal slots are kPlace[3] and kPlace[4]: three places apart.
    g_row.pitch = (At<Extent>(second, kControlExtent).left - g_row.part[0].left) / (kPlace[4] - kPlace[3]);
    g_row.nameTop = At<Extent>(Part(Part(hud, kHudTargetMenu), kMenuNameLabel), kControlExtent).top;
    g_row.mapBorderTop = At<Extent>(Part(hud, kHudMapBorder), kControlExtent).top;
    g_row.mapButtonTop = At<Extent>(Part(hud, kHudMapButton), kControlExtent).top;
    g_row.mapWindowTop = At<int>(hud, kHudMapWindowTop);
    // The Xbox layout has the frame at its scaled 41 px and a positive pitch. Anything
    // else is not that layout (the file was replaced, or failed to load): leave it be.
    g_row.usable = g_row.pitch > 0 && g_row.part[0].width == Scale(kSmall[0][0], height) &&
                   g_row.part[0].left >= 0 && g_row.part[0].top >= 0;
}

// The minimap's frame beside another patch. Scaled Kotor (a widescreen patch for
// KOTOR Patch Manager, 1.3.1 read on 2026-10-05) puts LBL_MAPBORDER back on its PC
// place, scaled, inside CSWGuiMainInterface::DrawMap (its hook at 0x0068ABB0, after
// this file's at DrawMap's entry), and sets the map's size, but leaves where the map
// is drawn alone: the map was at the Xbox place and its frame in the opposite corner
// (seen at 1920x1080). So after the panel is drawn the frame is compared with where
// this file put it. If something moved it, the engine's frame is left without art
// while the Xbox layout is up and this file draws one around the map as it is.
// (Without art, not invisible: the engine takes the frame's visibility for "is there
// a minimap", and with none it draws the speech box across the whole screen. Seen
// at 3440x1440 by the maintainer, 2026-10-05.)
Extent g_mapBorderSet{};
bool g_mapBorderForeign = false;
constexpr char kMapFrame[16] = "kmrx_minimap";

// What the hook changes before each draw that the engine does not set again by
// itself: which slots it parked, the frames the engine last gave the target's slots,
// and the arrows it hid.
bool g_parked[7] = {};
char g_engineFrame[3][2][16] = {};
bool g_arrowsHidden = false;

void* SlotAction(void* hud, int slot)
{
    return slot < 3 ? Part(Part(Part(hud, kHudTargetMenu), kMenuActions), slot * kActionSize)
                    : Part(Part(hud, kHudPersonalActions), (slot - 3) * kActionSize);
}

// The HUD as it was: every control back where the layout file and the engine had it,
// in its own art. `seen` is the target, or null.
void RestorePc(void* hud, void* seen)
{
    void* menu = Part(hud, kHudTargetMenu);
    for (int i = 0; i < kPieceCount; ++i) {
        const Piece& piece = kPieces[i];
        const Kept& kept = g_layout.kept[i];
        void* control = Part(hud, piece.offset);
        SetExtent(control, kept.extent);
        // Every fill, not only the ones the table changes: the hooks borrow two parked
        // controls to draw with (LBL_MENUBG, BTN_MSG), and LBL_MENUBG is the dark
        // backing of the PC HUD's menu buttons. (Left in the last art drawn with it,
        // the buttons had no backing after a swap; the maintainer saw it, 2026-10-05.)
        for (int which = 0; which < 3; ++which)
            if (void* params = Dress(control, piece.kind, which)) SetFill(params, kept.art[which]);
        if (piece.flags & kSetFont) SetFont(control, kept.font);
    }
    At<float>(Part(Part(hud, kHudSpareLabel), kLabelBorderParams), kParamsAlpha) = g_layout.spareAlpha;
    At<int>(hud, kHudDescriptionBottom) = g_layout.descriptionBottom;
    std::memcpy(&At<int>(hud, kHudMapWindow), g_layout.mapWindow, sizeof g_layout.mapWindow);
    std::memcpy(&At<int>(menu, kMenuOrigin), g_layout.menu, sizeof g_layout.menu);
    if (g_layout.cues) {
        if (void* cue = KmrpGuiCueK1(hud, kHudQueueButton)) SetExtent(cue, g_layout.queueCue);
        if (void* cue = KmrpGuiCueK1(hud, kHudMessage)) SetFill(Part(cue, kLabelBorderParams), g_layout.cueFill);
    }
    if (g_layout.bubbleKept)
        if (int* bubble = BarkBubble()) std::memcpy(bubble, g_layout.bubble, sizeof g_layout.bubble);
    g_mapBorderForeign = false;        // its art came back with the other controls', above
    // The slots. The engine frames a target's slots when the target changes, and
    // shows a slot's button and arrows when its contents change, not every frame.
    for (int slot = 0; slot < 7; ++slot) {
        void* action = SlotAction(hud, slot);
        if (slot < 3) {
            if (g_engineFrame[slot][0][0]) SetFill(Part(action, kButtonBorderParams), g_engineFrame[slot][0]);
            if (g_engineFrame[slot][1][0]) SetFill(Part(action, kButtonHilightParams), g_engineFrame[slot][1]);
        }
        const int count = slot < 3 ? At<int>(menu, kMenuActionLists + slot * 0xC + 4)
                                   : At<int>(hud, kHudPersonalLists + (slot - 3) * 0xC + 4);
        if (g_parked[slot] && count > 0) At<int>(action, kControlFlags) |= kControlVisible;
        g_parked[slot] = false;
        if (slot == 0 && g_arrowsHidden && count > 1) {
            At<int>(Part(action, kActionParts[2]), kControlFlags) |= kControlVisible;
            At<int>(Part(action, kActionParts[3]), kControlFlags) |= kControlVisible;
        }
    }
    g_arrowsHidden = false;
    // The box's text was this file's ("Attack", "No Action"); the PC HUD has one
    // only while a slot is pointed at.
    void* nothing[2] = {};
    reinterpret_cast<void(__thiscall*)(void*, void*)>(kSetDescription)(hud, nothing);
    // The engine stacks the health bar and the slots under the name again.
    if (seen) reinterpret_cast<void(__thiscall*)(void*, void*)>(kUpdateNameLabel)(menu, seen);
    g_first = FirstPlace{};
    for (auto& member : g_bars)
        for (Bar& held : member) held = Bar{};
    g_layout.xbox = false;
}

Extent Centred(const Extent& on, int width, int height)
{
    return {on.left + (on.width - width) / 2, on.top + (on.height - height) / 2, width, height};
}

// Centred on the box a slot's frame DRAWS, which is not the middle of the frame's
// rectangle: the art has the box two and a half of its 64 pixels above its texture's
// middle and half a pixel left (kSlotBoxCentre). In the large frame of the selected
// slot that is five screen pixels at 1280x960, and the picture and the arrows, put on
// the rectangle's middle, sat low in the box (the maintainer saw the speech icon off
// centre, 2026-10-05).
Extent OnBox(const Extent& frame, int width, int height)
{
    Extent at = Centred(frame, width, height);
    at.left += static_cast<int>(std::floor(frame.width * (kSlotBoxCentre[0] - 32.0) / 64.0 + 0.5));
    at.top += static_cast<int>(std::floor(frame.height * (kSlotBoxCentre[1] - 32.0) / 64.0 + 0.5));
    return at;
}

bool Enabled()
{
    // KOTOR Patch Manager's option when it recorded one; otherwise the setting in
    // kmrp-controller.ini, [Hud] Style=Xbox.
    static const bool on = [] {
        const int option = KmrpPatchOption(L"xbox-hud", -1);
        if (option >= 0) return option != 0;
        wchar_t path[MAX_PATH], style[16];
        const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
        wchar_t* slash = n && n < MAX_PATH ? wcsrchr(path, L'\\') : nullptr;
        if (!slash || wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-controller.ini")) return false;
        GetPrivateProfileStringW(L"Hud", L"Style", L"PC", style, 16, path);
        return _wcsicmp(style, L"Xbox") == 0;
    }();
    return on;
}

}  // namespace

bool KmrpXboxHudEnabledK1() { return Enabled(); }

// K1NativeJoystick.cpp calls this as a panel is built and as it is destroyed
// (NativePanelReleaseGffK1): a HUD object at an address seen before is a new HUD.
void KmrpXboxHudForgetK1(void* panel)
{
    if (!panel || panel != g_layout.hud) return;
    g_layout = Layout{};
    g_row = Row{};
    g_first = FirstPlace{};
    for (auto& member : g_bars)
        for (Bar& held : member) held = Bar{};
    for (bool& parked : g_parked) parked = false;
    g_mapBorderForeign = false;
    std::memset(g_engineFrame, 0, sizeof g_engineFrame);
    g_arrowsHidden = false;
}

// Hooked at the entry of CSWGuiTargetActionMenu::Draw (0x00685ED0, ecx = the menu),
// which the HUD calls right after it has drawn its panel: the filled part of each
// party bar that KmrpXboxHudK1 emptied.
//
// A bar on the Xbox empties from the top and keeps its curve: at half health the
// lower half of the red arc is there (reference video, a wounded companion). The PC's
// progress bar (CSWGuiProgressBar::SetExtent, 0x00419300) instead gives its fill the
// rectangle of the filled part and stretches the texture into it, which is invisible
// with the PC's flat colour and squeezed the whole arc into the lower part with the
// Xbox art (seen 2026-10-05). So the fill is drawn here whole, through a viewport that
// is the filled part's rectangle, the way the engine itself clips the target menu.
extern "C" void __cdecl KmrpXboxHudBarsK1(void* menu)
{
    // The first place of the action row, and without a target the dim frame of the
    // target's Force place, which the engine draws only with a target.
    if (g_first.draw && menu) {
        const FirstPlace first = g_first;
        g_first.draw = false;
        void* hud = At<void*>(menu, kMenuInterface);
        if (hud) {
            void* label = Part(hud, kHudSpareLabel);
            void* button = Part(hud, kHudSpareButton);
            void* frame = Part(label, kLabelBorderParams);
            const Extent labelWas = At<Extent>(label, kControlExtent), buttonWas = At<Extent>(button, kControlExtent);
            using Draw = void(__thiscall*)(void*, float);
            auto draw = [](void* control) {
                reinterpret_cast<Draw>((*reinterpret_cast<void***>(control))[14])(control, 0.0f);
            };
            reinterpret_cast<void(__cdecl*)()>(kStartLayer)();
            using Viewport = int(__cdecl*)(int, int, int, int, void*, int, float);
            // The minimap's frame, when another patch has taken the engine's away.
            Extent mapFrame{};
            {
                const Extent now = At<Extent>(Part(hud, kHudMapBorder), kControlExtent);
                if (!g_mapBorderForeign && (now.left != g_mapBorderSet.left || now.top != g_mapBorderSet.top ||
                                            now.width != g_mapBorderSet.width || now.height != g_mapBorderSet.height))
                    g_mapBorderForeign = true;
                Extent wasBorder{};
                for (int i = 0; i < kPieceCount; ++i)
                    if (kPieces[i].offset == kHudMapBorder) wasBorder = g_layout.kept[i].extent;
                const int* map = &At<int>(hud, kHudMapWindow);
                const int* was = g_layout.mapWindow;
                if (g_mapBorderForeign && was[2] > 0 && was[3] > 0)
                    mapFrame = {map[0] + (wasBorder.left - was[0]) * map[2] / was[2],
                                map[1] + (wasBorder.top - was[1]) * map[3] / was[3],
                                wasBorder.width * map[2] / was[2], wasBorder.height * map[3] / was[3]};
            }
            if (reinterpret_cast<Viewport>(kSetupViewport)(0, 0, first.width, first.height,
                    reinterpret_cast<void*>(kNoColouring), 0, 1.0f)) {
                if (mapFrame.width > 0 && mapFrame.height > 0) {
                    SetFill(frame, kMapFrame);
                    SetExtent(label, mapFrame);
                    draw(label);
                }
                if (first.dimForce) {
                    SetFill(frame, kSlotFrame);
                    At<float>(frame, kParamsAlpha) = 0.5f;
                    SetExtent(label, first.force);
                    draw(label);
                    At<float>(frame, kParamsAlpha) = 1.0f;
                }
                SetFill(frame, first.selected ? kSlotFrameSelected : kSlotFrame);
                SetExtent(label, first.frame);
                draw(label);
                SetFill(Part(button, kButtonBorderParams), first.icon);
                SetExtent(button, first.picture);
                draw(button);
                reinterpret_cast<void(__cdecl*)()>(kCloseViewport)();
            }
            reinterpret_cast<void(__cdecl*)()>(kStopLayer)();
            SetExtent(label, labelWas);
            SetExtent(button, buttonWas);
        }
    }
    for (auto& member : g_bars) {
        for (int kind = 0; kind < 2; ++kind) {
            Bar& held = member[kind];
            if (!held.bar) continue;
            void* bar = held.bar;
            const int value = held.value;
            held = Bar{};
            const Extent whole = At<Extent>(bar, kControlExtent);
            const int most = At<int>(bar, kBarMost);
            At<int>(bar, kControlFlags) |= kControlVisible;
            if (most <= 0 || whole.width <= 2 || whole.height <= 0) continue;
            // Drawn here whole, not by the panel: the empty bar, then its filling
            // through a viewport that is the filled part's rectangle, and each
            // texture told to clamp (ClampBoundTexture).
            // (Until later on 2026-10-05 the bar's outer edge was then drawn once more
            // beside itself, because the game's art has its outline cut by the side
            // of its texture. The bars are drawn art now, kmrx_health and the rest,
            // whose outline is whole, and the maintainer had the extra line removed.)
            const int inset = 0, trim = 0;
            const int filled = value <= 0 ? 0 : value >= most ? whole.height : whole.height * value / most;
            using Viewport = int(__cdecl*)(int, int, int, int, void*, int, float);
            using Draw = void(__thiscall*)(void*, float);
            auto part = [&](std::ptrdiff_t which, int rows) {
                if (rows <= 0) return;
                reinterpret_cast<void(__cdecl*)()>(kStartLayer)();
                if (reinterpret_cast<Viewport>(kSetupViewport)(whole.left + inset, whole.top + whole.height - rows,
                        whole.width - trim, rows, reinterpret_cast<void*>(kNoColouring), 0, 1.0f)) {
                    // The bar full, placed so that its lower `rows` rows are the viewport's.
                    SetExtent(bar, {-inset, rows - whole.height, whole.width, whole.height});
                    SetBarValue(bar, most);
                    void* piece = Part(bar, which);
                    reinterpret_cast<Draw>((*reinterpret_cast<void***>(piece))[3])(piece, 0.0f);
                    ClampBoundTexture();
                    reinterpret_cast<void(__cdecl*)()>(kCloseViewport)();
                }
                reinterpret_cast<void(__cdecl*)()>(kStopLayer)();
            };
            part(kBarBorder, whole.height);
            part(kBarFill, filled);
            SetExtent(bar, whole);
            SetBarValue(bar, value);
        }
    }
}

// Hooked at the entry of CSWGuiMainInterface::DrawMap, ecx = the HUD.
extern "C" void __cdecl KmrpXboxHudK1(void* hud)
{
    if (!hud || !Enabled()) return;
    void* menu = Part(hud, kHudTargetMenu);
    void* manager = At<void*>(hud, kHudManager);
    if (!manager) return;
    const int width = At<short>(manager, kManagerViewportWidth);
    const int height = At<short>(manager, kManagerViewportHeight);
    if (width <= 0 || height <= 0) return;

    void* app = *reinterpret_cast<void**>(kAppManager);
    void* client = app ? At<void*>(app, 4) : nullptr;
    const bool target = (At<unsigned>(menu, kMenuFlags) & 1) != 0;
    void* object = client && target
        ? reinterpret_cast<void*(__thiscall*)(void*, unsigned)>(kGetGameObject)(client, At<unsigned>(hud, kHudTargetId))
        : nullptr;
    void* seen = object
        ? reinterpret_cast<void*(__thiscall*)(void*)>((*reinterpret_cast<void***>(object))[3])(object)   // AsSWCObject
        : nullptr;

    // The Xbox HUD while the pad is the device in use, the game's own otherwise.
    if (g_layout.hud != hud) Keep(hud);
    if (!IsControllerInputActiveK1()) {
        if (g_layout.xbox) {
            CombatMessage(hud, client, width);
            RestorePc(hud, seen);
        }
        return;
    }
    if (!g_layout.xbox || g_layout.width != width || g_layout.height != height) ApplyXbox(hud, width, height);
    if (!g_row.usable) return;

    // The menu's viewport starts at the screen's corner and is as wide as the screen.
    // A clamp rectangle no taller than the menu keeps PositionMenu (0x00686090) from
    // moving it between two draws.
    int* origin = &At<int>(menu, kMenuOrigin);
    origin[0] = 0;
    origin[1] = 0;
    At<int>(menu, kMenuWidth) = width;
    int* clamp = &At<int>(menu, kMenuClamp);
    clamp[0] = 0; clamp[1] = 0; clamp[2] = width; clamp[3] = 0;

    // The default action, the first place's. The executable still has the routine
    // that names it, CClientExoAppInternal::GetDefaultActions (0x00620620), which the
    // PC game never calls (its list was empty in the running game, 2026-10-05): for
    // the HUD's target it makes a one-entry list with the action's name and icon
    // ("Dialog" for someone to talk to, "Open" for a door, "Attack", and "No Action"
    // with i_noaction), which is what the maintainer's frames of the Xbox game show
    // in the first place. It returns without touching its list when there is no
    // target object, so that case is "No Action" here.
    const int kind = At<signed char>(menu, kMenuTargetKind);
    char* usualEntry = nullptr;
    if (seen) {
        void* internal = At<void*>(client, 4);
        reinterpret_cast<void(__thiscall*)(void*)>(kGetDefaultActions)(internal);
        if (At<int>(internal, kDefaultActions + 4) > 0) usualEntry = At<char*>(internal, kDefaultActions);
    }

    CombatMessage(hud, client, width);

    // The target's first list holds the default action too, where it is one of the
    // target's own actions (read from a hostile target's lists in the running game:
    // Critical Strike, Master Power Attack, Attack). The slot keeps to the others:
    // the second place is the feats, a door's lock, a droid's repair.
    char* first = target ? At<char*>(menu, kMenuActionLists) : nullptr;
    const int firstCount = first ? At<int>(menu, kMenuActionLists + 4) : 0;
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
        // The engine's up and down walk the whole list and so reach the default
        // action: coming from the entry after it, it was going backwards, and is
        // sent on to the entry before; otherwise on to the entry after.
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

    // The texts. The Xbox names the selected action in the box and keeps the
    // target's name in the name bar; the PC puts a target slot's action in the name
    // bar and nothing in the box (CSWGuiTargetActionMenu::UpdateNameLabel).
    const int focused = KmrpFocusedActionSlotK1(hud);
    {
        using Describe = void(__thiscall*)(void*, void*);
        const Describe describe = reinterpret_cast<Describe>(kSetDescription);
        if (target && focused >= 0 && focused < kTargetSlots && kind >= 0 && kind < 4) {
            char* list = At<char*>(menu, kMenuActionLists + focused * 0xC);
            const int count = At<int>(menu, kMenuActionLists + focused * 0xC + 4);
            if (list && count > 0) {
                char* entry = list;
                const int chosen = At<int>(menu, kMenuChosen + (kind * 3 + focused) * 4);
                for (int i = 0; i < count; ++i)
                    if (At<int>(list + i * kEntrySize, kEntryId) == chosen) entry = list + i * kEntrySize;
                describe(hud, entry);      // an entry begins with its name, a CExoString
            }
            if (seen) {
                char& named = At<char>(menu, kMenuNamedSlot);
                const char was = named;
                named = -1;
                reinterpret_cast<void(__thiscall*)(void*, void*)>(kUpdateNameLabel)(menu, seen);
                named = was;
            }
        } else if (focused < 0) {
            if (usualEntry) {
                describe(hud, usualEntry);
            } else if (client) {
                static void* noAction[2] = {};     // a CExoString, fetched once and kept
                static bool fetched = false;
                if (!fetched) {
                    reinterpret_cast<void*(__thiscall*)(void*, void*, int)>(kGetGuiString)(client, noAction, kNoActionString);
                    fetched = true;
                }
                describe(hud, noAction);
            }
        }
    }

    // The name, its frame and the health bar. SetNameLabel shrinks the name to its
    // text, gives the background the same rectangle and stacks the bar right under
    // it; the Xbox frame has a fixed row for each. A name too long for one row keeps
    // the height the engine gave it.
    // The strip is there while the engine shows the combat-mode message's label,
    // which it does in combat mode.
    const bool strip = (At<int>(Part(hud, kHudMessage), kControlFlags) & kControlVisible) != 0;
    const int lower = strip ? Scale(kStripShift, height) : 0;
    if (strip) {
        void* label = Part(hud, kHudSpareLabel);
        void* fill = Part(label, kLabelBorderParams);
        const Extent was = At<Extent>(label, kControlExtent);
        float* colour = &At<float>(fill, kParamsColour);
        const float colourWas[3] = {colour[0], colour[1], colour[2]};
        reinterpret_cast<void(__cdecl*)()>(kStartLayer)();
        using Viewport = int(__cdecl*)(int, int, int, int, void*, int, float);
        if (reinterpret_cast<Viewport>(kSetupViewport)(0, 0, width, height, reinterpret_cast<void*>(kNoColouring), 0, 1.0f)) {
            using Draw = void(__thiscall*)(void*, float);
            const Draw draw = reinterpret_cast<Draw>((*reinterpret_cast<void***>(label))[14]);
            const int bottom = Scale(kStripHeight, height);
            SetFill(fill, kStripFill);
            At<float>(fill, kParamsAlpha) = kStripAlpha;
            SetExtent(label, {0, 0, width, bottom});
            draw(label, 0.0f);
            SetFill(fill, kLineFill);
            At<float>(fill, kParamsAlpha) = 1.0f;
            std::memcpy(colour, kLineColour, sizeof kLineColour);
            SetExtent(label, {0, bottom - 2, width, 2});
            draw(label, 0.0f);
            std::memcpy(colour, colourWas, sizeof colourWas);
            reinterpret_cast<void(__cdecl*)()>(kCloseViewport)();
        }
        reinterpret_cast<void(__cdecl*)()>(kStopLayer)();
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

    void* nameLabel = Part(menu, kMenuNameLabel);
    Extent name = At<Extent>(nameLabel, kControlExtent);
    if (name.height < Scale(kNameHeight, height) || name.top != g_row.nameTop + lower) {
        if (name.height < Scale(kNameHeight, height)) name.height = Scale(kNameHeight, height);
        name.top = g_row.nameTop + lower;
        SetExtent(nameLabel, name);
    }
    auto fromName = [&](const int box[4]) {
        return Extent{name.left + Scale(box[0], height), name.top + Scale(box[1], height),
                      Scale(box[2], height), Scale(box[3], height)};
    };
    SetExtent(Part(menu, kMenuNameBackground), fromName(kNameFrame));
    // Red around a hostile target's name, as the Xbox game had it (seen in the
    // reference video: "Sith Soldier" in a red frame over a red bar).
    // The engine's frame on the first target slot is the sign; once the Xbox frame
    // has replaced it, the last sign seen stands until the engine writes another.
    static bool hostile = false;
    {
        const char* frame = &At<char>(Part(menu, kMenuActions), kButtonBorderParams + kParamsFill);
        if (_strnicmp(frame, kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) hostile = SameName(frame, kSlotHostile);
    }
    SetFill(Part(Part(menu, kMenuNameBackground), kLabelBorderParams), hostile ? kFrameHostile : kFrameFriendly);
    SetExtent(Part(menu, kMenuHealthBar), fromName(kHealthBar));
    SetExtent(Part(menu, kMenuHealthBackground), fromName(kHealthBar));

    // Its height: the whole screen. The engine ends the viewport at the health bar
    // for a target with no action, which hides the three slots; the Xbox row shows a
    // slot with nothing in it as a dim frame, and with the Xbox frame on them (below)
    // that is what the engine's empty slots are.
    At<int>(menu, kMenuHeight) = height;
    const bool grenades = (At<unsigned>(menu, kMenuFlags) & 1) != 0 &&
        At<int>(menu, kMenuActionLists + kSharedTarget * 0xC + 4) != 0;

    // The action box, as tall as the description needs.
    {
        void* box = Part(hud, kHudMouldings);
        const Extent text = At<Extent>(Part(hud, kHudDescription), kControlExtent);
        Extent wanted = At<Extent>(box, kControlExtent);
        const int bottom = wanted.top + wanted.height;
        const int textTop = text.height > 0 ? text.top : text.top - Scale(kBoxEmptyLine, height);
        wanted.top = textTop - Scale(kBoxAboveText, height);
        wanted.height = bottom - wanted.top;
        if (wanted.height > 0 && wanted.top >= 0) SetExtent(box, wanted);
    }

    // The party's vitality bars in the Xbox HUD's curved art, and every bar that is
    // neither full nor empty emptied for the panel's draw: KmrpXboxHudBarsK1 draws
    // its filled part afterwards.
    for (int member = 0; member < 3; ++member) {
        void* fill = Part(hud, kHudParty + member * kPartySize + kPartyVitalityFill);
        const char* now = &At<char>(fill, kParamsFill);
        if (SameName(now, kFlatHealth)) SetFill(fill, kCurvedHealth);
        else if (SameName(now, kFlatPoison)) SetFill(fill, kCurvedPoison);
        for (int kind = 0; kind < 2; ++kind) {
            void* bar = Part(hud, kHudParty + member * kPartySize + kPartyBars[kind]);
            Bar& held = g_bars[member][kind];
            held = Bar{};
            if (!(At<int>(bar, kControlFlags) & kControlVisible)) continue;
            held.bar = bar;
            held.value = At<int>(bar, kBarValue);
            At<int>(bar, kControlFlags) &= ~kControlVisible;     // not by the panel: KmrpXboxHudBarsK1 draws it
        }
    }

    // The first place: the default action, selected while no slot has the focus.
    g_first = FirstPlace{};
    g_first.draw = true;
    g_first.selected = focused < 0;
    g_first.dimForce = !target;
    g_first.width = width;
    g_first.height = height;
    std::memcpy(g_first.icon, usualEntry ? usualEntry + kEntryIcon : kNoActionIcon, 16);
    g_first.frame = g_row.part[0];
    g_first.picture = g_row.part[1];
    g_first.force = g_row.part[0];
    g_first.frame.left -= kFirstPersonalPlace * g_row.pitch;
    g_first.picture.left -= kFirstPersonalPlace * g_row.pitch;
    g_first.force.left += (kForcePlace - kFirstPersonalPlace) * g_row.pitch;
    if (g_first.selected) {
        const Extent frame = g_first.frame;
        g_first.frame = Centred(frame, Scale(kLarge[0][0], height), Scale(kLarge[0][1], height));
        g_first.picture = OnBox(g_first.frame, Scale(kLarge[1][0], height), Scale(kLarge[1][1], height));
    } else {
        g_first.picture = OnBox(g_first.frame, g_first.picture.width, g_first.picture.height);
    }

    // The slots: each at its place in the row, the focused one large.
    for (int slot = 0; slot < kSlots; ++slot) {
        void* action = slot < kTargetSlots
            ? Part(Part(menu, kMenuActions), slot * kActionSize)
            : Part(Part(hud, kHudPersonalActions), (slot - kTargetSlots) * kActionSize);
        const int shift = (kPlace[slot] - kFirstPersonalPlace) * g_row.pitch;
        Extent part[4];
        for (int p = 0; p < 4; ++p) {
            part[p] = g_row.part[p];
            part[p].left += shift;
        }
        // The slot's button carries the focus, so it alone is made invisible while the
        // slot is parked, and visible again when the slot comes back: the engine sets
        // that flag when a slot's contents change, not every frame. (Clearing it on
        // the icon as well left the grenade slot as two arrows around nothing when it
        // came back, 2026-10-05.)
        bool* const parked = g_parked;
        if (slot == (grenades ? kSharedPersonal : kSharedTarget) || slot == (feats ? kSkillsSlot : kFeatsSlot)) {
            for (int p = 0; p < 4; ++p) {
                part[p].left = part[p].top = kParked;
                SetExtent(Part(action, kActionParts[p]), part[p]);
            }
            At<int>(action, kControlFlags) &= ~kControlVisible;
            parked[slot] = true;
            continue;
        }
        if (parked[slot]) {
            // Back, and able to take the focus again if it has anything to offer: the
            // engine leaves an empty slot's button invisible (seen 2026-10-05: the
            // focus on an empty mines slot after a fight, a large yellow frame around
            // nothing).
            const int count = slot < kTargetSlots
                ? At<int>(menu, kMenuActionLists + slot * 0xC + 4)
                : At<int>(hud, kHudPersonalLists + (slot - kTargetSlots) * 0xC + 4);
            if (count > 0) At<int>(action, kControlFlags) |= kControlVisible;
            parked[slot] = false;
        }
        const Extent frame = part[0];
        const int (*size)[2] = slot == focused ? kLarge : kSmall;
        if (slot == focused) {
            part[0] = Centred(frame, Scale(size[0][0], height), Scale(size[0][1], height));
            for (int p = 1; p < 3; ++p)
                part[p] = OnBox(part[0], Scale(size[p][0], height), Scale(size[p][1], height));
            part[3] = {part[2].left, part[2].top + part[2].height / 2, part[2].width,
                       part[2].height - part[2].height / 2};
        } else {
            part[1] = OnBox(frame, part[1].width, part[1].height);     // a small slot's picture, in its box's middle too
        }
        if (slot < kTargetSlots) {
            void* normal = Part(action, kButtonBorderParams);
            void* selected = Part(action, kButtonHilightParams);
            if (_strnicmp(&At<char>(normal, kParamsFill), kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) {
                std::memcpy(g_engineFrame[slot][0], &At<char>(normal, kParamsFill), 16);
                SetFill(normal, kSlotFrame);
            }
            if (_strnicmp(&At<char>(selected, kParamsFill), kSlotEnginePrefix, sizeof kSlotEnginePrefix - 1) == 0) {
                std::memcpy(g_engineFrame[slot][1], &At<char>(selected, kParamsFill), 16);
                SetFill(selected, kSlotFrameSelected);
            }
        }
        // The selected slot's arrows are yellow on the Xbox (reference video, 21:21,
        // "Adrenal Strength (self)"), the others' blue. The arrow strip is on the up
        // button (build_xbox_hud.py).
        SetFill(Part(Part(action, kActionParts[2]), kButtonBorderParams), slot == focused ? kArrowsSelected : kArrows);
        for (int p = 0; p < 4; ++p) SetExtent(Part(action, kActionParts[p]), part[p]);
        // With the default action and one feat, the slot has nothing to walk through.
        if (slot == kFeatsSlot && others == 1) {
            g_arrowsHidden = true;
            At<int>(Part(action, kActionParts[2]), kControlFlags) &= ~kControlVisible;
            At<int>(Part(action, kActionParts[3]), kControlFlags) &= ~kControlVisible;
        }
    }
}
