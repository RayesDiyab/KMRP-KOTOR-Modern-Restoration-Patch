/*
  KMRP for macOS, controller support: Pazaak's two screens (handoff items 109 and 110) and class
  selection's Select (item 106) with the pad.

  The Mac port of K1NativeJoystick.cpp's two sections, "Pazaak's table, the Xbox way" and "Pazaak's
  side deck screen", which say why each thing is done and what the maintainer saw; the formula and
  the measures are in docs/controller-live-adaptive-layout.md. The buttons themselves are gui.cpp's
  (kRemaps: X plays the focused card, A ends the turn, Y stands, LB flips, and A is Play on the side
  deck), and so is the hand's focus; prompts.cpp badges End Turn, Stand, Add Card and Play. This file
  is the rest of what the screens show.

  The table (CSWGuiPazaakGame, vtable 0x1005A5B80). The Xbox's "(X) Play Hand Card, (White) Flip
  Hand Card, (A) End Turn, (Y) Stand" as four boxes along the table's foot: End Turn twice over,
  as CSWGuiActivatedButtons of this patch's, for Play and Flip; their boxes mirror Stand and End
  Turn about the gap left of End Turn, and the strip under them is mirrored into the panel's
  picture, a private copy. The PC's four small flip buttons and the flip legend draw only for the
  mouse. All four captions stand on one line, in dialogfont10x10 where they do not fit, scaled only
  if that is still too wide.

  The side deck (CSWGuiPazaakStart, vtable 0x1005A5A90), redrawn as the Xbox drew it: the panel's
  picture made at the panel's size over the table's lbl_pazaak, the cards moved, Add Card shown (the
  panel's m_btnSwitch, which the PC binds on the table's screen only), Play, and the LT and RT
  glyphs beside the two list titles. With the mouse both screens are as the game has them.

  What is the Mac's, read from its executable on 2026-11-03:

    - CSWGuiPazaakGame's constructor is 0x1002204A6: LBL_FLIPICON +0x8630, LBL_FLIPLEGEND +0x87C8,
      BTN_XTEXT +0x8960, BTN_YTEXT +0x8BB0, BTN_FLIP0..3 from +0x7D30, 0x240 apart, the hand from
      +0x3A40, 0x3F0 apart; [panel+0xAB20] the turn's state and [panel+0xAB30] the card mode. A
      card's value is at +0x3D8 (SetCard, 0x10021D200; Windows +0x304).
    - CSWGuiPazaakStart's is 0x10021E7C0: LBL_TITLE +0x80, the 18 available cards from +0x218, their
      counts from +0x48F8, 0x198 apart, the 10 chosen from +0x65A8, the switch +0x8D08, BTN_ATEXT
      +0x8F58, LBL_LTEXT +0x91A8, LBL_RTEXT +0x9340; a card's face label at +0x240.
    - CSWGuiActivatedButton is 0x250 bytes, its constructor 0x10021CE50 (Windows builds it inline).
      A press's pulse is four floats at +0x240, which End Turn's handler (0x100221CD4) writes.
    - SetEnabled is the vtable's +0x110 and Draw its +0x78 (a control's vtable has two destructors).
    - A panel's border is the pointer at +0x70, its params 0x18 in (StartLoadFromLayout, 0x10049DFE4).
    - The texture behind a name is 0x1001F9FF4, its GL name 0x1001F7362, CAurTexture::Bind
      0x1001F72B0. Mac textures are read back through OpenGL here as Windows' K1CaptionInk does.
    - A picture this file draws is written to this run's folder of links with a .txi beside it and
      the folder listed anew in place (standalone::ListAgain), as Windows lists its folder anew
      (K1WriteDrawnTexture).

  What differs from Windows in kind: the LT and RT glyphs are the carried kmr?rmlt and kmr?rmrt
  (Windows draws them; handoff item 101), and the table's picture is brought in by Bind on first
  need rather than preloaded (KmrpQueueTexturePreloadK1 has no Mac counterpart: handoff item 112 is
  not ported), so the first side deck of a session can show the game's own screen for a frame or two.

  Class selection (CSWGuiClassSelection, vtable 0x1005AF890; handoff item 106, last part), here for
  the pictures and made controls it shares with the side deck. With the pad in use the foot shows
  Select (A) on the left and Cancel (B) on the right, the two arrows and the gaps between all four
  equal, on a drawing of the panel's own picture with two capsules (BuildClassSelectArtK1,
  K1ClassSelectArt.h, the Windows file included as it is). Select is a button made like Cancel
  (BTN_BACK, +0x19B0 from the screen's constructor, 0x100335ED0), the game's own string 236, kept
  off the pad's focus: A already picks the focused class. Where the picture's foot is not a capsule
  between two arrows nothing changes. Windows tries that again every frame; here a picture read and
  refused is not read again until it, the panel or Cancel changes. Compiled, not played.

  The table and the side deck were seen working in the game run of 2026-11-03.
*/
#include "pazaak.h"

#define GL_SILENCE_DEPRECATION
#include <OpenGL/gl.h>

#include "../kmrp-layout/text.h"
#include "engine.h"
#include "layout.h"
#include "overlays.h"
#include "pad.h"
#include "prompts.h"
#include "standalone.h"

// The picture's pure half, shared with Windows. Its rectangle's helper is Windows' calling
// convention, which this file does not use.
#define __thiscall
#include "../../../src/controller-native/K1ClassSelectArt.h"
#undef __thiscall

#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <string>
#include <strings.h>
#include <utility>
#include <vector>

namespace kmrp {
namespace pazaak {
namespace {

using engine::At;
using text::LooksLikePointer;
using text::Readable;

struct Box { int left, top, width, height; };
struct String { char* text = nullptr; std::uint64_t length = 0; };   // CExoString, 16 bytes

const std::size_t kResRefBytes = 17;
const std::size_t kCtlExtent = 0x08, kCtlFlags = 0x68, kCtlId = 0x74;
const std::uint8_t kCtlVisible = 0x02;
const std::size_t kVtDeletingDtor = 0x08, kVtSetExtent = 0x10, kVtDraw = 0x78, kVtSetEnabled = 0x110;
const std::size_t kPanelActive = 0x28, kPanelControls = 0x30, kPanelControlCount = 0x38, kPanelGff = 0x40, kPanelBorder = 0x70;
const std::size_t kBorderParams = 0x18, kParamsFill = 0x3d, kParamsStyle = 0x1c;
const std::uintptr_t kBasePanelVtable = 0x1005b3730UL;
const std::uintptr_t kButtonVtable = 0x1005b47b8UL, kLabelVtable = 0x1005b3c50UL;
const std::size_t kLabelSize = 0x198, kLabelBorder = 0x88 + kBorderParams, kLabelTextParams = 0x130;
const std::size_t kButtonText = 0x1b8, kButtonTextParams = 0x1d8;
const std::size_t kTextColour = 0x28, kTextFontName = 0x45;
const std::size_t kButtonSize = 0x240, kActivatedSize = 0x250, kPulse = 0x240;
const std::size_t kVtTextLayOut = 0xa0;            // the string's lines worked out again (SetText, 0x1004A3714)

const auto LabelCtor = reinterpret_cast<void (*)(void*)>(0x1004a54aaUL);
const auto ActivatedCtor = reinterpret_cast<void (*)(void*)>(0x10021ce50UL);
const auto ButtonCtor = reinterpret_cast<void (*)(void*)>(0x1004a5e8eUL);
const auto InitControl = reinterpret_cast<void (*)(void* panel, void* control, void* tag, int add)>(0x10049e476UL);
const auto ArrayAdd = reinterpret_cast<void (*)(void* list, void* item)>(0x100215440UL);
const auto StringFromText = reinterpret_cast<void (*)(String*, const char*)>(0x10034cca8UL);
const auto StringDestroy = reinterpret_cast<void (*)(String*)>(0x10034cdf2UL);
const auto GetGuiString = reinterpret_cast<void (*)(String* out, void* app, std::uint64_t strref)>(0x10028c4baUL);
const auto SetTextOf = reinterpret_cast<void (*)(void* params, String* text)>(0x1004a3714UL);
const auto SetStrRef = reinterpret_cast<void (*)(void* params, std::uint64_t strref)>(0x1004a30ccUL);
const auto SetTextColour = reinterpret_cast<void (*)(void* params, const void* vector)>(0x1004a380eUL);
const auto SetFontOf = reinterpret_cast<void (*)(void* params)>(0x1004a3670UL);
const auto SetFillImage = reinterpret_cast<void (*)(void* params, const void* resref, int force)>(0x1004a17c2UL);
const auto TextureByName = reinterpret_cast<void* (*)(const char* name, void*)>(0x1001f9ff4UL);
const auto AssignTexture = reinterpret_cast<void* (*)(void** slot, void* reference)>(0x100194f60UL);
const auto TextureName = reinterpret_cast<unsigned (*)(void* reference)>(0x1001f7362UL);
const auto TextureBind = reinterpret_cast<void (*)(void* reference)>(0x1001f72b0UL);

char* Part(void* base, std::size_t offset) { return static_cast<char*>(base) + offset; }
std::uintptr_t VtableOf(void* object) { return LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }
bool Same(const Box& a, const Box& b) { return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height; }
const Box& BoxOf(void* control) { return At<Box>(control, kCtlExtent); }

void SetBox(void* control, const Box& box) {
    if (Same(BoxOf(control), box)) return;
    reinterpret_cast<void (*)(void*, const Box*)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtSetExtent))(control, &box);
}

void SetFill(void* params, const char* name) {
    char padded[kResRefBytes] = {};
    for (std::size_t i = 0; i + 1 < kResRefBytes && name[i]; ++i) padded[i] = name[i];
    SetFillImage(params, padded, 1);
}

// The panel's own picture: its border's params.
char* PanelFillParams(void* panel) {
    char* const border = At<char*>(panel, kPanelBorder);
    return LooksLikePointer(border) ? border + kBorderParams : nullptr;
}

void DeleteControl(void* control) {
    reinterpret_cast<void (*)(void*)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtDeletingDtor))(control);
}

// A control made from one of the panel's own, by its tag, and added after the others. Null when
// the panel's layout has no such tag (AppendControlLikeK1).
void* AppendControlLike(void* panel, const char* like, std::size_t size, void (*ctor)(void*)) {
    void* const control = ::operator new(size, std::nothrow);
    if (!control) return nullptr;
    std::memset(control, 0, size);
    ctor(control);
    At<int>(control, kCtlId) = -1;
    String name;
    StringFromText(&name, like);
    InitControl(panel, control, &name, 0);
    StringDestroy(&name);
    const int count = At<int>(panel, kPanelControlCount);
    if (At<int>(control, kCtlId) < 0 || count < 0 || count >= 512) {
        DeleteControl(control);
        return nullptr;
    }
    At<int>(control, kCtlId) = count;
    ArrayAdd(Part(panel, kPanelControls), control);
    void** const controls = At<void**>(panel, kPanelControls);
    // In the array or not, it is not where it should be: left alone, as a cue the binder refused.
    if (At<int>(panel, kPanelControlCount) != count + 1 || !LooksLikePointer(controls) || controls[count] != control) return nullptr;
    return control;
}

// As ForgetGuiCuesK1: a leak is safer than a double free.
void FreeAppended(void* panel, void* control) {
    void** const controls = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    const int id = At<int>(control, kCtlId);
    if (LooksLikePointer(controls) && id >= 0 && id < count && controls[id] == control) {
        controls[id] = nullptr;
        DeleteControl(control);
    }
}

// True at a panel's end: the base destructor's StopLoadFromLayout has the vtable back at CSWGuiPanel
// and the .gui gone (as cues.cpp, overlays.cpp).
bool Ending(void* panel) {
    return Readable(panel, kPanelGff + sizeof(void*)) && VtableOf(panel) == kBasePanelVtable && !At<void*>(panel, kPanelGff);
}

// The pixels of a texture as OpenGL holds them, RGBA, row 0 first (K1CaptionInk::ReadUploaded).
// Null when it cannot be read; the caller frees it. The binding before is put back.
unsigned char* ReadUploaded(unsigned name, int* width, int* height) {
    if (!name) return nullptr;
    GLint before = 0, alignment = 4;
    *width = *height = 0;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &before);
    glBindTexture(GL_TEXTURE_2D, name);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, height);
    unsigned char* pixels = nullptr;
    if (*width > 0 && *height > 0 && *width <= 8192 && *height <= 8192)
        pixels = static_cast<unsigned char*>(std::malloc(static_cast<std::size_t>(*width) * *height * 4));
    if (pixels) {
        glGetIntegerv(GL_PACK_ALIGNMENT, &alignment);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
        glPixelStorei(GL_PACK_ALIGNMENT, alignment);
    }
    glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(before));
    return pixels;
}

// The texture of `name`, bound once so that it is uploaded, and held in `slot`.
unsigned char* ReadTexture(const char* name, void** slot, int* width, int* height) {
    if (!*slot)
        if (void* const reference = TextureByName(name, nullptr)) AssignTexture(slot, reference);
    if (!*slot) return nullptr;
    TextureBind(*slot);
    return ReadUploaded(TextureName(*slot), width, height);
}

// A picture this file drew (`sheet`, RGBA, top row first): written beside this run's links, without
// mipmaps and without repeat, and the folder given to the game again (K1WriteTextureFiles).
bool WritePicture(const char* name, const std::vector<std::uint8_t>& sheet, int width, int height) {
    const char* const folder = standalone::RunDirectory();
    if (!folder) return false;
    std::vector<std::uint8_t> tga(18 + sheet.size() + 26, 0);
    tga[2] = 2;
    tga[12] = static_cast<std::uint8_t>(width);
    tga[13] = static_cast<std::uint8_t>(width >> 8);
    tga[14] = static_cast<std::uint8_t>(height);
    tga[15] = static_cast<std::uint8_t>(height >> 8);
    tga[16] = 32;
    tga[17] = 0x08;                        // bottom row first, as the game's own
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const std::uint8_t* s = &sheet[(static_cast<std::size_t>(height - 1 - y) * width + x) * 4];
            std::uint8_t* d = &tga[18 + (static_cast<std::size_t>(y) * width + x) * 4];
            d[0] = s[2];
            d[1] = s[1];
            d[2] = s[0];
            d[3] = s[3];
        }
    }
    std::memcpy(&tga[18 + sheet.size() + 8], "TRUEVISION-XFILE.", 17);
    const std::string base = std::string(folder) + "/" + name;
    FILE* f = std::fopen((base + ".tga").c_str(), "wb");
    if (!f) return false;
    bool written = std::fwrite(tga.data(), 1, tga.size(), f) == tga.size();
    written = std::fclose(f) == 0 && written;
    if (!written) return false;
    f = std::fopen((base + ".txi").c_str(), "wb");
    if (!f) return false;
    static const char kTxi[] = "mipmap 0\r\nclamp 3\r\n";
    written = std::fwrite(kTxi, 1, sizeof kTxi - 1, f) == sizeof kTxi - 1;
    written = std::fclose(f) == 0 && written;
    if (!written) return false;
    return standalone::ListAgain();
}

// The badge `resref` (the Xbox art's name) on a button, in the pad's family, or none.
void Badge(void* panel, void* button, const char* resref) {
    if (!resref) {
        overlays::Hide(button);
        return;
    }
    char name[kResRefBytes] = {};
    std::snprintf(name, sizeof name, "%s", resref);
    name[3] = prompts::FamilyLetter();
    overlays::Show(panel, button, name);
}

// ------------------------------------------------------------------------- the table

const std::uintptr_t kGameVtable = 0x1005a5b80UL;
const std::size_t kFlips = 0x7d30, kFlipStride = 0x240, kFlipIcon = 0x8630, kFlipLegend = 0x87c8;
const std::size_t kEndTurn = 0x8960, kStand = 0x8bb0;
const std::size_t kHand = 0x3a40, kCardStride = 0x3f0, kCardValue = 0x3d8;
const std::size_t kTurn = 0xab20, kCardMode = 0xab30;
const std::uint64_t kPlayString = 32330, kFlipString = 32331;
const char kSmallFont[] = "dialogfont10x10";
const int kVtableWords = 72;

struct Table {
    void* panel = nullptr;
    void* play = nullptr, *flip = nullptr;    // X: Play Hand Card; LB: Flip Hand Card
    bool artInitialized = false;
    void* mouseVtables[6] = {};
    void* hiddenVtables[2][kVtableWords] = {};
    bool shown = false;
    float scaleBase[4] = {}, scaleSet[4] = {};   // the captions' own size, and the last written
    bool smallFont = false;                      // the row is in the smaller font
    char fontWas[4][kResRefBytes] = {};          // the font each had
    void* picture = nullptr;                     // the panel's own picture, while it is read
} g_table;

std::size_t HiddenOffset(int i) {
    return i < 4 ? kFlips + static_cast<std::size_t>(i) * kFlipStride : i == 4 ? kFlipIcon : kFlipLegend;
}

void* FocusedHandCard(void* panel) {
    if (At<int>(panel, kCardMode) != 0) return nullptr;
    void* const focused = At<void*>(panel, kPanelActive);
    for (int i = 0; i < 4; ++i)
        if (focused == Part(panel, kHand + static_cast<std::size_t>(i) * kCardStride)) {
            const std::uint8_t flags = At<std::uint8_t>(focused, kCtlFlags);
            return (flags & kCtlVisible) ? focused : nullptr;
        }
    return nullptr;
}

bool ActionEnabled(void* panel, bool flip) {
    void* const card = FocusedHandCard(panel);
    const int value = card ? At<int>(card, kCardValue) : -1;
    return card && (flip ? (value >= 12 && value < 18) : (At<int>(panel, kTurn) == 3 && value >= 0));
}

// The PC's flip controls draw for the mouse only: the panel's RefreshDisplay can make them visible
// during Draw, after this file's frame, so their Draw says no while the pad is in use and all of
// the game's visibility and enabled state stays for the mouse (PazaakMouseOnlyDrawK1).
void MouseOnlyDraw(void* control, float seconds) {
    if (device::PadInUse()) return;
    for (int i = 0; i < 6; ++i) {
        if (control != Part(g_table.panel, HiddenOffset(i))) continue;
        if (void* const vtable = g_table.mouseVtables[i])
            reinterpret_cast<void (*)(void*, float)>(*reinterpret_cast<std::uintptr_t*>(static_cast<char*>(vtable) + kVtDraw))(control, seconds);
        return;
    }
}

void SetActionEnabled(void* button, bool enabled) {
    // Native disabled Pazaak text is still cyan: an explicit gray, cancelling a previous card's
    // pulse so its Draw cannot paint over the disabled colour. Play becomes disabled as soon as
    // its accepted action consumes the card, and that press finishes flashing.
    if (!enabled && button != g_table.play) At<float>(button, kPulse) = -1.0f;
    reinterpret_cast<void (*)(void*, int)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(button) + kVtSetEnabled))(button, enabled ? 1 : 0);
    if (!enabled) {
        const float gray[3] = {0.5f, 0.5f, 0.5f};
        SetTextColour(Part(button, kButtonTextParams), gray);
    }
}

float CaptionScale(void* button) {
    char* const object = At<char*>(Part(button, kButtonText), text::kTextObject);
    return Readable(object, 0x60) ? At<float>(object, text::kObjScale) : 0.0f;
}

void SetCaptionScale(void* button, float scale) {
    char* const object = At<char*>(Part(button, kButtonText), text::kTextObject);
    if (!Readable(object, 0x60)) return;
    At<float>(object, text::kObjScale) = scale;
    reinterpret_cast<void (*)(void*, int)>(*reinterpret_cast<std::uintptr_t*>(VtableOf(object) + kVtTextLayOut))(object, -1);
}

void SetFont(void* button, const char* name) {
    char* const params = Part(button, kButtonTextParams);
    std::memset(params + kTextFontName, 0, kResRefBytes);
    std::snprintf(params + kTextFontName, kResRefBytes, "%s", name);
    SetFontOf(params);
}

void InstallTable(void* panel) {
    g_table = Table{};
    g_table.panel = panel;
    layout::PadFocusExclude(Part(panel, kEndTurn), true);
    layout::PadFocusExclude(Part(panel, kStand), true);
    for (int i = 0; i < 4; ++i) layout::PadFocusExclude(Part(panel, HiddenOffset(i)), true);

    g_table.play = AppendControlLike(panel, "BTN_XTEXT", kActivatedSize, ActivatedCtor);
    g_table.flip = AppendControlLike(panel, "BTN_XTEXT", kActivatedSize, ActivatedCtor);
    const std::uint64_t strings[] = {kPlayString, kFlipString};
    void* const buttons[] = {g_table.play, g_table.flip};
    for (int i = 0; i < 2; ++i) {
        void* const button = buttons[i];
        if (!button) continue;
        layout::PadFocusExclude(button, true);
        At<std::uint8_t>(button, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
        if (void* const client = engine::ClientApp()) {
            String words;
            GetGuiString(&words, client, strings[i]);
            SetTextOf(Part(button, kButtonTextParams), &words);
            StringDestroy(&words);
        }
    }
    // Each hidden vtable is a copy with its word before it, so a reader of what stands before a
    // vtable finds what was there.
    for (int i = 0; i < 6; ++i) {
        const int kind = i < 4 ? 0 : 1;
        void* const control = Part(panel, HiddenOffset(i));
        const std::uintptr_t original = VtableOf(control);
        if (original != (kind == 0 ? kButtonVtable : kLabelVtable)) continue;
        void** const copy = g_table.hiddenVtables[kind];
        if (!copy[1]) {
            std::memcpy(copy, reinterpret_cast<void*>(original - sizeof(void*)), sizeof g_table.hiddenVtables[kind]);
            copy[1 + kVtDraw / sizeof(void*)] = reinterpret_cast<void*>(&MouseOnlyDraw);
        }
        g_table.mouseVtables[i] = reinterpret_cast<void*>(original);
        At<void*>(control, 0) = &copy[1];
    }
}

// Four actions on the table's foot (UpdatePazaakActionStripK1). Only the action strip's rows of the
// loaded picture are copied from its right half to its left, mirrored; the copy is this module's.
void UpdateTable() {
    Table& g = g_table;
    void* const panel = g.panel;
    if (!panel || !g.play || !g.flip || !Readable(panel, kStand + kActivatedSize) || VtableOf(panel) != kGameVtable) return;
    char* const params = PanelFillParams(panel);
    if (!params) return;
    static void* owner = nullptr;
    static char original[kResRefBytes] = {}, drawn[kResRefBytes] = {};
    static Box panelWas{}, endWas{}, standWas{};
    if (owner != panel || !g.artInitialized) {
        owner = panel;
        original[0] = drawn[0] = 0;
        g.artInitialized = true;
    }
    char* const fill = params + kParamsFill;
    if (!original[0] || (strncasecmp(fill, original, 16) && strncasecmp(fill, drawn, 16))) {
        std::memcpy(original, fill, 16);
        drawn[0] = 0;
    }
    const Box box = BoxOf(panel);
    void* const endTurn = Part(panel, kEndTurn);
    void* const stand = Part(panel, kStand);
    const Box end = BoxOf(endTurn), standBox = BoxOf(stand);
    const int gap = std::max(0, standBox.left - end.left - end.width);
    // The PC row is not centred on the panel. Its own pitch is continued to the left.
    const int axisTwice = 2 * end.left - gap;
    if (!Same(box, panelWas) || !Same(end, endWas) || !Same(standBox, standWas)) drawn[0] = 0;
    bool shown = device::PadInUse();
    if (shown && !drawn[0] && box.width > 0 && box.height > 0) {
        int w = 0, h = 0;
        void* reference = nullptr;
        unsigned char* const pixels = ReadTexture(original, &reference, &w, &h);
        if (reference) AssignTexture(&reference, nullptr);
        if (pixels && w > 0 && h > 0) {
            // A one-layout-pixel rim includes the red border round the button boxes.
            const Box hand = BoxOf(Part(panel, kHand));
            const int stripTop = std::min(end.top, hand.top + hand.height);
            const int top = std::max(0, (stripTop - box.top - std::max(1, box.height / 480)) * h / box.height);
            const int bottom = std::min(h, (end.top + end.height - box.top + std::max(1, box.height / 480)) * h / box.height);
            const int axisTexTwice = (axisTwice - 2 * box.left) * w / box.width;
            std::vector<std::uint8_t> sheet(static_cast<std::size_t>(w) * h * 4);
            for (int y = 0; y < h; ++y) {
                const unsigned char* row = pixels + static_cast<std::size_t>(h - 1 - y) * w * 4;
                std::uint8_t* out = sheet.data() + static_cast<std::size_t>(y) * w * 4;
                std::memcpy(out, row, static_cast<std::size_t>(w) * 4);
                if (y >= top && y < bottom) {
                    for (int x = 0; x < std::min(w, axisTexTwice / 2); ++x) {
                        const int source = axisTexTwice - 1 - x;
                        if (source >= 0 && source < w) std::memcpy(out + x * 4, row + source * 4, 4);
                    }
                }
            }
            std::uint32_t hash = 2166136261u;
            for (std::uint8_t c : sheet) hash = (hash ^ c) * 16777619u;
            char candidate[kResRefBytes] = {};
            std::snprintf(candidate, sizeof candidate, "kmzpzk%08x", hash);
            if (WritePicture(candidate, sheet, w, h)) {
                std::memcpy(drawn, candidate, sizeof drawn);
                panelWas = box;
                endWas = end;
                standWas = standBox;
            }
        }
        std::free(pixels);
    }
    shown = shown && drawn[0];
    void* const buttons[] = {g.play, g.flip};
    const Box sources[] = {standBox, end};
    const char* const badges[] = {"kmrpx_pzkplay", "kmrpl_pzkflip"};
    for (int i = 0; i < 2; ++i) {
        void* const button = buttons[i];
        bool enabled = false;
        std::uint8_t& flags = At<std::uint8_t>(button, kCtlFlags);
        flags = shown ? (flags | kCtlVisible) : (flags & static_cast<std::uint8_t>(~kCtlVisible));
        if (shown) {
            Box rect = sources[i];
            rect.left = axisTwice - rect.left - rect.width;
            SetBox(button, rect);
            enabled = ActionEnabled(panel, i != 0);
            SetActionEnabled(button, enabled);
        }
        overlays::Centre(button, shown);
        Badge(panel, button, shown ? badges[i] : nullptr);
        overlays::Dim(button, !enabled);
    }
    // All four captions on one line beside their badges, in one size. In the game's own smaller
    // font where they do not fit: its letters are drawn for that size, where the caption's font
    // scaled down looked squeezed. Scaled only if that is still too wide.
    void* const row[] = {g.play, g.flip, endTurn, stand};
    double fit = 1.0;
    for (int i = 0; i < 4; ++i) {
        const float now = CaptionScale(row[i]);
        if (!(now > 0.0f)) continue;
        if (now != g.scaleSet[i]) g.scaleBase[i] = now;      // the game's, or another patch's
        if (i >= 2) overlays::Centre(row[i], shown);
        const Box at = BoxOf(row[i]);
        const int line = overlays::CaptionLineWidth(row[i]);
        const double whole = line * static_cast<double>(g.scaleBase[i]) / now;
        // The badge is about as wide as the button is tall, with half of that at each end.
        const int room = at.width - 2 * at.height;
        if (shown && whole > room && room > 0) fit = std::min(fit, room / whole);
    }
    if (shown != g.smallFont && (!shown || fit < 1.0)) {
        for (int i = 0; i < 4; ++i) {
            char* const name = Part(row[i], kButtonTextParams + kTextFontName);
            if (shown) std::memcpy(g.fontWas[i], name, kResRefBytes);
            SetFont(row[i], shown ? kSmallFont : g.fontWas[i]);
        }
        g.smallFont = shown;
        fit = 1.0;      // measured again next frame, in the new font
    }
    for (int i = 0; i < 4; ++i) {
        if (!(g.scaleBase[i] > 0.0f)) continue;
        const float wanted = static_cast<float>(g.scaleBase[i] * fit);
        if (CaptionScale(row[i]) != wanted) SetCaptionScale(row[i], wanted);
        g.scaleSet[i] = wanted;
    }
    const char* const wanted = shown ? drawn : original;
    if (strncasecmp(fill, wanted, 16)) SetFill(params, wanted);
    g.shown = shown;
}

// The table's end: the controls kept off the pad's focus given back, and the two made here freed
// while the panel still holds them where they were put.
void ForgetTable(void* panel) {
    if (panel != g_table.panel || !Ending(panel)) return;
    layout::PadFocusExclude(Part(panel, kEndTurn), false);
    layout::PadFocusExclude(Part(panel, kStand), false);
    overlays::Centre(Part(panel, kEndTurn), false);
    overlays::Centre(Part(panel, kStand), false);
    for (int i = 0; i < 6; ++i) {
        void* const control = Part(panel, HiddenOffset(i));
        if (i < 4) layout::PadFocusExclude(control, false);
        if (g_table.mouseVtables[i]) At<void*>(control, 0) = g_table.mouseVtables[i];
    }
    for (void* const button : {g_table.play, g_table.flip}) {
        if (!button) continue;
        layout::PadFocusExclude(button, false);
        overlays::Centre(button, false);
        FreeAppended(panel, button);
    }
    g_table = Table{};
}

// ---------------------------------------------------------------------- the side deck

const std::uintptr_t kSetupVtable = 0x1005a5a90UL;
const std::size_t kTitle = 0x80, kAvailable = 0x218, kCounts = 0x48f8, kChosen = 0x65a8;
const std::size_t kSwitch = 0x8d08, kAccept = 0x8f58, kLeftText = 0x91a8, kRightText = 0x9340;
const std::size_t kCardFace = 0x240;
const std::uint64_t kAddCardString = 0x96c9;

// A control this screen moves, where the layout put it and where it is put here.
struct Place { void* control; Box was, at; };

struct Setup {
    void* panel = nullptr;
    void* lt = nullptr, *rt = nullptr;      // the two trigger glyphs, labels made here
    std::vector<Place> places;
    std::uint8_t switchFlagsWas = 0;
    char fillWas[kResRefBytes] = {};        // the panel's own picture
    char drawn[kResRefBytes] = {};          // ours, and what it was drawn for
    std::uint32_t drawnFor = 0;
    Box ltAt{}, rtAt{};
    char ltFor = 0, rtFor = 0;
    int shown = -1;
};
Setup g_setup;
void* g_tableTexture = nullptr;             // lbl_pazaak, kept once it has been read

// ---- drawing: a sheet of RGBA, top row first, and the shapes on it

struct Sheet {
    int width = 0, height = 0;
    std::vector<std::uint8_t> rgba;
    std::vector<std::uint8_t> table;        // the Pazaak table under it, the same size
};

struct Paint { float r, g, b, a; };         // a colour and its opacity over the table

// Coverage (0..1) of a pixel centred at (px, py) by a rectangle whose four corners are rounded by
// `radius` where `round` has the bit (1 top left, 2 top right, 4 bottom right, 8 bottom left): the
// signed distance to its edge, over one pixel.
float RoundedCover(float px, float py, float x0, float y0, float x1, float y1, float radius, unsigned round) {
    const float cx = px < (x0 + x1) / 2 ? x0 : x1, cy = py < (y0 + y1) / 2 ? y0 : y1;
    const unsigned corner = (cy == y0 ? (cx == x0 ? 1u : 2u) : (cx == x1 ? 4u : 8u));
    float d;
    const float r = (round & corner) ? std::min(radius, std::min(x1 - x0, y1 - y0) / 2) : 0.0f;
    const float ix = std::max(x0 + r, std::min(px, x1 - r));
    const float iy = std::max(y0 + r, std::min(py, y1 - r));
    if (r > 0 && (px < x0 + r || px > x1 - r) && (py < y0 + r || py > y1 - r)) {
        d = std::sqrt((px - ix) * (px - ix) + (py - iy) * (py - iy)) - r;
    } else {
        d = std::max(std::max(x0 - px, px - x1), std::max(y0 - py, py - y1));
    }
    return std::max(0.0f, std::min(1.0f, 0.5f - d));
}

// The pixel at (x, y) taken toward `paint` over the table by `cover`.
void Blend(Sheet& s, int x, int y, const Paint& paint, float cover) {
    if (cover <= 0.0f) return;
    std::uint8_t* const p = &s.rgba[(static_cast<std::size_t>(y) * s.width + x) * 4];
    const std::uint8_t* const t = &s.table[(static_cast<std::size_t>(y) * s.width + x) * 4];
    const float want[3] = {t[0] + (paint.r - t[0]) * paint.a, t[1] + (paint.g - t[1]) * paint.a, t[2] + (paint.b - t[2]) * paint.a};
    for (int c = 0; c < 3; ++c) p[c] = static_cast<std::uint8_t>(std::lround(p[c] + (want[c] - p[c]) * cover));
}

void Rounded(Sheet& s, float x0, float y0, float x1, float y1, float radius, unsigned round, const Paint& paint) {
    const int l = std::max(0, static_cast<int>(std::floor(x0)) - 1), r = std::min(s.width - 1, static_cast<int>(std::ceil(x1)) + 1);
    const int t = std::max(0, static_cast<int>(std::floor(y0)) - 1), b = std::min(s.height - 1, static_cast<int>(std::ceil(y1)) + 1);
    for (int y = t; y <= b; ++y)
        for (int x = l; x <= r; ++x) Blend(s, x, y, paint, RoundedCover(x + 0.5f, y + 0.5f, x0, y0, x1, y1, radius, round));
}

// An outline `w` wide just inside the rounded rectangle.
void Outline(Sheet& s, float x0, float y0, float x1, float y1, float radius, unsigned round, float w, const Paint& paint) {
    const int l = std::max(0, static_cast<int>(std::floor(x0)) - 1), r = std::min(s.width - 1, static_cast<int>(std::ceil(x1)) + 1);
    const int t = std::max(0, static_cast<int>(std::floor(y0)) - 1), b = std::min(s.height - 1, static_cast<int>(std::ceil(y1)) + 1);
    for (int y = t; y <= b; ++y) {
        for (int x = l; x <= r; ++x) {
            const float outer = RoundedCover(x + 0.5f, y + 0.5f, x0, y0, x1, y1, radius, round);
            if (outer <= 0.0f) continue;
            const float inner = RoundedCover(x + 0.5f, y + 0.5f, x0 + w, y0 + w, x1 - w, y1 - w, std::max(0.0f, radius - w), round);
            Blend(s, x, y, paint, outer - inner);
        }
    }
}

// A closed polygon, by 4 x 4 samples a pixel (even-odd).
void Polygon(Sheet& s, const std::vector<std::pair<float, float>>& pts, const Paint& paint) {
    if (pts.size() < 3) return;
    float minX = pts[0].first, maxX = minX, minY = pts[0].second, maxY = minY;
    for (const auto& p : pts) {
        minX = std::min(minX, p.first);
        maxX = std::max(maxX, p.first);
        minY = std::min(minY, p.second);
        maxY = std::max(maxY, p.second);
    }
    const int l = std::max(0, static_cast<int>(minX)), r = std::min(s.width - 1, static_cast<int>(maxX) + 1);
    const int t = std::max(0, static_cast<int>(minY)), b = std::min(s.height - 1, static_cast<int>(maxY) + 1);
    if (r < l) return;
    std::vector<float> crossings;
    std::vector<float> cover(static_cast<std::size_t>(r - l + 1));
    for (int y = t; y <= b; ++y) {
        std::fill(cover.begin(), cover.end(), 0.0f);
        for (int sy = 0; sy < 4; ++sy) {
            const float yy = y + (sy + 0.5f) / 4.0f;
            crossings.clear();
            for (std::size_t i = 0; i < pts.size(); ++i) {
                const auto& a = pts[i];
                const auto& c = pts[(i + 1) % pts.size()];
                if ((a.second <= yy) != (c.second <= yy))
                    crossings.push_back(a.first + (yy - a.second) * (c.first - a.first) / (c.second - a.second));
            }
            std::sort(crossings.begin(), crossings.end());
            for (std::size_t i = 0; i + 1 < crossings.size(); i += 2) {
                for (int x = l; x <= r; ++x) {
                    for (int sx = 0; sx < 4; ++sx) {
                        const float xx = x + (sx + 0.5f) / 4.0f;
                        if (xx >= crossings[i] && xx < crossings[i + 1]) cover[x - l] += 1.0f / 16.0f;
                    }
                }
            }
        }
        for (int x = l; x <= r; ++x) Blend(s, x, y, paint, cover[x - l]);
    }
}

// ---- the layout

// The Xbox column's parts, top to bottom, in its 640x480 units (upper box, Available bar, Chosen
// bar, lower box, Play bar), and an Xbox y carried into the column as spaced here.
const float kParts[5][2] = {{38.4f, 198.75f}, {198.8f, 250.3f}, {251.25f, 290.6f}, {296.25f, 403.1f}, {413.4f, 440.6f}};
const float kSetupGap = 7.5f;               // the dark margin and the gap, Xbox units

float ColumnY(float u) {
    float total = 0;
    for (const auto& p : kParts) total += p[1] - p[0];
    const float k = (kParts[4][1] - kParts[0][0] - kSetupGap * 4) / total;
    float at = kParts[0][0];
    float prevU = kParts[0][0], prevV = at;
    if (u <= prevU) return u;
    for (const auto& p : kParts) {
        // the gap before this part (none before the first)
        if (u <= p[0]) return prevV + (at - prevV) * (u - prevU) / ((p[0] - prevU) > 0 ? (p[0] - prevU) : 1.0f);
        const float end = at + (p[1] - p[0]) * k;
        if (u <= p[1]) return at + (end - at) * (u - p[0]) / (p[1] - p[0]);
        prevU = p[1];
        prevV = end;
        at = end + kSetupGap;
    }
    return prevV + (u - prevU);
}

struct Layout {
    float s = 0;                                // Xbox units to pixels
    float panelTop = 0;
    Box panel{};
    float leftL = 0, leftT = 0, leftR = 0, leftB = 0;      // the left panel
    float frameL = 0, frameT = 0, frameR = 0, frameB = 0;  // the right frame's outline
    float colL = 0, colR = 0, boxL = 0, boxR = 0, mid = 0; // the middle column: plates' and boxes' edges, middle
    int cardW = 0, cardH = 0;
    float availPitch = 0;
    int availLeft = 0, availCols = 0;
    std::vector<int> chosenCols;                // the chosen columns' new left edges
    float X(float u) const { return mid + (u - 349.375f) * s; }
    float Y(float u) const { return panelTop + ColumnY(u) * s; }
};

// This screen's entry for a control, its layout place taken again whenever something other than
// this has moved it (the screen laid out again for another size).
Place& EntryOf(void* control) {
    for (Place& p : g_setup.places) {
        if (p.control != control) continue;
        const Box now = BoxOf(control);
        if (!Same(now, p.at) && !Same(now, p.was)) {
            p.was = now;
            p.at = Box{};
        }
        return p;
    }
    g_setup.places.push_back({control, BoxOf(control), Box{}});
    return g_setup.places.back();
}

void Move(void* control, const Box& box) {
    Place& p = EntryOf(control);
    p.at = box;
    SetBox(control, box);
}

void* Card(void* panel, std::size_t first, int i) { return Part(panel, first + static_cast<std::size_t>(i) * kCardStride); }

int TextWidth(void* label) {
    int line = 0;
    return text::LabelTextWidth(label, line);
}

// The columns among cards' left edges: edges within half a card of each other are one column, at
// the leftmost of them. The layout's own differ by a pixel or two within a column.
std::vector<int> Columns(std::vector<int> lefts, int cardW) {
    std::sort(lefts.begin(), lefts.end());
    std::vector<int> cols;
    for (const int left : lefts)
        if (cols.empty() || left - cols.back() > cardW / 2) cols.push_back(left);
    return cols;
}

int ColumnOf(const std::vector<int>& cols, int left) {
    int best = 0;
    for (int i = 1; i < static_cast<int>(cols.size()); ++i)
        if (std::abs(cols[i] - left) < std::abs(cols[best] - left)) best = i;
    return best;
}

// Where everything goes, from the layout's own places.
bool LayoutFor(void* panel, Layout& L) {
    L.panel = BoxOf(panel);
    if (L.panel.width <= 0 || L.panel.height <= 0) return false;
    L.s = L.panel.height / 480.0f;
    L.panelTop = static_cast<float>(L.panel.top);
    // The available cards as laid out: their columns.
    std::vector<int> cols;
    int top = INT_MAX, bottom = INT_MIN;
    for (int i = 0; i < 18; ++i) {
        const Box was = EntryOf(Card(panel, kAvailable, i)).was;
        cols.push_back(was.left);
        top = std::min(top, was.top);
        bottom = std::max(bottom, was.top + was.height);
        L.cardW = was.width;
        L.cardH = was.height;
    }
    if (cols.empty() || L.cardW <= 0) return false;
    cols = Columns(cols, L.cardW);
    L.availLeft = cols.front();
    L.availCols = static_cast<int>(cols.size());
    const float s = L.s;
    // The Xbox's left panel is 196 units wide (cards from 1 unit inside it), here 245.
    L.availPitch = L.availCols > 1 ? (245.0f * s + 2.0f * s - L.cardW) / (L.availCols - 1) : 0.0f;
    L.leftL = L.availLeft + 1.0f * s;
    L.leftT = top - 2.0f * s;
    L.leftR = L.availLeft + L.availPitch * (L.availCols - 1) + L.cardW - 1.0f * s;
    L.leftB = bottom + 2.0f * s;
    // The chosen cards as laid out: the frame round them, the Xbox's margins.
    int cl = INT_MAX, cr = INT_MIN, ct = INT_MAX, cb = INT_MIN;
    std::vector<int> ccols;
    for (int i = 0; i < 10; ++i) {
        const Box was = EntryOf(Card(panel, kChosen, i)).was;
        cl = std::min(cl, was.left);
        cr = std::max(cr, was.left + was.width);
        ct = std::min(ct, was.top);
        cb = std::max(cb, was.top + was.height);
        ccols.push_back(was.left);
    }
    ccols = Columns(ccols, L.cardW);
    L.frameL = cl - 3.5f * s;
    L.frameR = cr + 5.0f * s;
    L.frameT = ct + 1.0f * s - 4.0f * s;
    L.frameB = cb + 4.0f * s;
    // The slots (a card's body, 6.5 units in at each side) with equal gaps across the frame.
    const float slot = L.cardW - 13.0f * s;
    const int n = static_cast<int>(ccols.size());
    const float gap = n > 0 ? (L.frameR - L.frameL - n * slot) / (n + 1) : 0.0f;
    L.chosenCols.clear();
    for (int i = 0; i < n; ++i)
        L.chosenCols.push_back(static_cast<int>(std::lround(L.frameL + gap * (i + 1) + slot * i - 6.5f * s)));
    // The middle column, centred on the panel, 25% wider than the Xbox's (x 250..453.8).
    const float middle = L.panel.left + L.panel.width / 2.0f;
    const auto wide = [&](float u) { return middle + (u - 348.5f) * s * 1.25f; };
    L.boxL = wide(257.5f);
    L.boxR = wide(441.25f);
    L.colL = L.boxL - kSetupGap * s;
    L.colR = L.boxR + kSetupGap * s;
    // Those widths assume KMRP's wider panel. On the game's own 640 units there is no room for
    // both: the third column of cards lay 93 units over the middle one and its captions (Windows,
    // 2026-11-03). Then the cards keep the layout's spacing, and the middle column takes what is
    // between them and the frame.
    if (L.leftR + kSetupGap * s > L.colL || L.colR + kSetupGap * s > L.frameL) {
        if (cols.size() > 1) L.availPitch = static_cast<float>(cols[1] - cols[0]);
        L.leftR = L.availLeft + L.availPitch * (L.availCols - 1) + L.cardW - 1.0f * s;
        L.colL = L.leftR + kSetupGap * s;
        L.colR = L.frameL - kSetupGap * s;
        L.boxL = L.colL + kSetupGap * s;
        L.boxR = L.colR - kSetupGap * s;
    }
    L.mid = (L.boxL + L.boxR) / 2.0f;
    return true;
}

// The picture for the layout: the Pazaak table under it, read from the texture the game loads
// (lbl_pazaak, stretched over the panel as the gameplay screen stretches it), and the parts drawn
// over it. Its name in `out`; false until the table's picture is uploaded.
bool Picture(const Layout& L, int ltLeft, int rtRight, char (&out)[kResRefBytes]) {
    int tw = 0, th = 0;
    unsigned char* const pixels = ReadTexture("lbl_pazaak", &g_tableTexture, &tw, &th);
    if (!pixels) return false;
    Sheet s;
    s.width = L.panel.width;
    s.height = L.panel.height;
    if (s.width > 4096 || s.height > 4096 || tw < 2 || th < 2) {
        std::free(pixels);
        return false;
    }
    s.table.resize(static_cast<std::size_t>(s.width) * s.height * 4);
    // The table stretched over the panel, bilinear; OpenGL's row 0 is the picture's foot.
    for (int y = 0; y < s.height; ++y) {
        const float fy = (y + 0.5f) * th / s.height - 0.5f;
        const int y0 = std::max(0, std::min(th - 1, static_cast<int>(std::floor(fy))));
        const int y1 = std::min(th - 1, y0 + 1);
        const float wy = std::max(0.0f, std::min(1.0f, fy - y0));
        for (int x = 0; x < s.width; ++x) {
            const float fx = (x + 0.5f) * tw / s.width - 0.5f;
            const int x0 = std::max(0, std::min(tw - 1, static_cast<int>(std::floor(fx))));
            const int x1 = std::min(tw - 1, x0 + 1);
            const float wx = std::max(0.0f, std::min(1.0f, fx - x0));
            const auto px = [&](int xx, int yy) { return pixels + (static_cast<std::size_t>(th - 1 - yy) * tw + xx) * 4; };
            std::uint8_t* const o = &s.table[(static_cast<std::size_t>(y) * s.width + x) * 4];
            for (int c = 0; c < 3; ++c) {
                const float top = px(x0, y0)[c] + (px(x1, y0)[c] - px(x0, y0)[c]) * wx;
                const float bottom = px(x0, y1)[c] + (px(x1, y1)[c] - px(x0, y1)[c]) * wx;
                o[c] = static_cast<std::uint8_t>(std::lround(top + (bottom - top) * wy));
            }
            o[3] = 255;
        }
    }
    std::free(pixels);
    // Each part's colour and its opacity over the table, fitted to the Xbox art over its own table
    // (lbl_pazaak01 against lbl_pazaak, per channel; the fit within 1 to 4 of 255).
    const Paint backdrop{0, 0, 0, 0.80f};
    const Paint panelBlue{36, 43, 64, 0.91f};
    const Paint plate{12, 11, 11, 0.92f};
    const Paint frameInside{6, 4, 4, 0.86f};
    const Paint upperInside{18, 19, 23, 0.95f};
    const Paint lowerInside{37, 44, 65, 1.0f};
    const Paint playInside{6, 7, 8, 1.0f};
    const Paint slotBlue{40, 46, 65, 0.95f};
    const Paint line{44, 52, 76, 1.0f};
    const Paint arrowLight{49, 54, 74, 1.0f};
    const Paint arrowDark{12, 13, 17, 1.0f};
    const Paint cyan{0, 175, 255, 1.0f};
    s.rgba = s.table;
    for (int y = 0; y < s.height; ++y)
        for (int x = 0; x < s.width; ++x) Blend(s, x, y, backdrop, 1.0f);
    const float u = L.s, M = kSetupGap * u, R = 8.75f * u, W = 1.25f * u;
    const float ox = static_cast<float>(-L.panel.left), oy = static_cast<float>(-L.panel.top);
    const auto rr = [&](float x0, float y0, float x1, float y1, float radius, unsigned round, const Paint& p) {
        Rounded(s, x0 + ox, y0 + oy, x1 + ox, y1 + oy, radius, round, p);
    };
    const auto ol = [&](float x0, float y0, float x1, float y1, unsigned round) {
        Outline(s, x0 + ox, y0 + oy, x1 + ox, y1 + oy, R, round, W, line);
    };
    const float upT = L.Y(38.4f), upB = L.Y(198.75f), avT = L.Y(198.8f), avB = L.Y(250.3f);
    const float chT = L.Y(251.25f), chB = L.Y(290.6f), loT = L.Y(296.25f), loB = L.Y(403.1f);
    const float plT = L.Y(413.4f), plB = L.Y(440.6f);
    // The dark plates: the column above and below the Available bar, the frame's, and the Chosen
    // bar's joining the column to it.
    rr(L.colL, upT - M, L.colR, upB + M, R + M, 15, plate);
    rr(L.colL, chT - M, L.colR, plB + M, R + M, 15, plate);
    rr(L.frameL - M, L.frameT - M, L.frameR + M, L.frameB + M, R + M, 15, plate);
    rr(L.boxL, chT - M, L.frameL + M, chB + M, 0, 0, plate);
    // The left panel, and the Available bar coming out of it to the column's right edge.
    rr(L.leftL, L.leftT, L.leftR, L.leftB, 7.0f * u, 15, panelBlue);
    rr(L.leftR - 8.0f * u, avT, L.boxR + 5.0f * u, avB, 8.0f * u, 2 | 4, panelBlue);
    // The frame and its slots.
    rr(L.frameL, L.frameT, L.frameR, L.frameB, R, 15, frameInside);
    ol(L.frameL, L.frameT, L.frameR, L.frameB, 15);
    // The boxes, the bar opening into the frame (its edge cut where they meet).
    rr(L.boxL, upT, L.boxR, upB, R, 15, upperInside);
    ol(L.boxL, upT, L.boxR, upB, 15);
    rr(L.boxL, chT, L.frameL + 8.0f * u, chB, R, 15, plate);
    ol(L.boxL, chT, L.frameL + 8.0f * u, chB, 1 | 8);
    rr(L.frameL - 2.0f * u, chT + W, L.frameL + 9.0f * u, chB - W, 0, 0, plate);
    rr(L.boxL, loT, L.boxR, loB, R, 1 | 2, lowerInside);
    ol(L.boxL, loT, L.boxR, loB, 1 | 2);
    rr(L.boxL, plT, L.boxR, plB, R, 4 | 8, playInside);
    ol(L.boxL, plT, L.boxR, plB, 4 | 8);
    // The two arrows, in texels of the Xbox's 512 picture (x 1.25, y 0.9375 to its units).
    const auto at = [&](float tx, float ty) { return std::make_pair(L.X(tx * 1.25f) + ox, L.Y(ty * 0.9375f) + oy); };
    const auto arc = [&](std::vector<std::pair<float, float>>& v, float cx, float cy, float r, float a0, float a1) {
        for (int i = 0; i <= 12; ++i) {
            const float a = (a0 + (a1 - a0) * i / 12.0f) * 3.14159265f / 180.0f;
            v.push_back(at(cx + r * std::cos(a), cy + r * std::sin(a)));
        }
    };
    std::vector<std::pair<float, float>> up{at(246, 80), at(289, 80)};
    arc(up, 289, 101, 21, -90, 0);
    for (const auto& p : {std::make_pair(310.0f, 140.0f), std::make_pair(321.0f, 140.0f), std::make_pair(297.0f, 173.0f),
                          std::make_pair(272.0f, 140.0f), std::make_pair(282.0f, 140.0f), std::make_pair(282.0f, 116.0f),
                          std::make_pair(246.0f, 116.0f)})
        up.push_back(at(p.first, p.second));
    Polygon(s, up, arrowLight);
    std::vector<std::pair<float, float>> down;
    for (const auto& p : {std::make_pair(246.0f, 328.0f), std::make_pair(272.0f, 328.0f), std::make_pair(272.0f, 376.0f),
                          std::make_pair(290.0f, 376.0f), std::make_pair(290.0f, 362.0f), std::make_pair(314.0f, 393.0f),
                          std::make_pair(290.0f, 424.0f), std::make_pair(290.0f, 410.0f), std::make_pair(272.0f, 410.0f)})
        down.push_back(at(p.first, p.second));
    arc(down, 272, 384, 26, 90, 180);
    Polygon(s, down, arrowDark);
    // The cyan arrows beside the two titles, as lbl_arrow_l and lbl_arrow_r draw them (their tips
    // toward the trigger glyph), from the titles' ends.
    const auto cyanArrow = [&](float tipX, float cy, bool left) {
        const float k = left ? 1.0f : -1.0f, q = 0.9f * u;
        const float pts[7][2] = {{0, 0}, {9, -9.5f}, {9, -3.5f}, {13, -3.5f}, {13, 3.5f}, {9, 3.5f}, {9, 9.5f}};
        std::vector<std::pair<float, float>> v;
        for (const auto& p : pts) v.push_back({tipX + k * p[0] * q + ox, cy + p[1] * q + oy});
        Polygon(s, v, cyan);
    };
    const float avMid = (avT + avB) / 2, chMid = (chT + chB) / 2;
    if (ltLeft > 0) cyanArrow(ltLeft - 4.0f * u - 13.0f * 0.9f * u, avMid, true);
    if (rtRight > 0) cyanArrow(rtRight + 4.0f * u + 13.0f * 0.9f * u, chMid, false);
    // The slots, under the chosen cards where they are put.
    for (int i = 0; i < 10; ++i) {
        const Place* p = nullptr;
        for (const Place& e : g_setup.places)
            if (e.control == Card(g_setup.panel, kChosen, i)) p = &e;
        if (!p || p->at.width <= 0) continue;
        const Box& c = p->at;
        rr(c.left + 6.5f * u, c.top + 1.0f * u, c.left + c.width - 6.5f * u, static_cast<float>(c.top + c.height), 4.0f * u, 15, slotBlue);
    }
    std::uint32_t hash = 2166136261u;
    const auto mix = [&](std::uint32_t v) { hash = (hash ^ v) * 16777619u; };
    mix(static_cast<std::uint32_t>(s.width));
    mix(static_cast<std::uint32_t>(s.height));
    mix(static_cast<std::uint32_t>(tw));
    mix(static_cast<std::uint32_t>(th));
    mix(static_cast<std::uint32_t>(ltLeft));
    mix(static_cast<std::uint32_t>(rtRight));
    for (int v : {static_cast<int>(L.leftR), static_cast<int>(L.frameL), static_cast<int>(L.boxL)}) mix(static_cast<std::uint32_t>(v));
    for (std::size_t i = 0; i < s.table.size(); i += 4099) mix(s.table[i]);
    std::snprintf(out, sizeof out, "kmzpzs%08x", hash);
    return WritePicture(out, s.rgba, s.width, s.height);
}

void UpdateSetup();

// As the screen is built: the switch bound, the two trigger glyphs made, hidden and without text.
void InstallSetup(void* panel) {
    g_setup = Setup{};
    g_setup.panel = panel;
    g_setup.shown = -1;
    void* const add = Part(panel, kSwitch);
    g_setup.switchFlagsWas = At<std::uint8_t>(add, kCtlFlags);
    // The switch bound from the layout, as the game binds Play. The PC game binds BTN_YTEXT only
    // on the table's screen (to its own control), so on this screen the switch was never loaded
    // from pazaaksetup.gui nor added to the panel, and nothing drew its caption (Windows' play
    // test, 2026-10-29). Bound here while the layout is still loaded, and added; it stays hidden
    // until the pad's screen shows it.
    {
        String name;
        StringFromText(&name, "BTN_YTEXT");
        InitControl(panel, add, &name, 1);
        StringDestroy(&name);
        std::uint8_t& flags = At<std::uint8_t>(add, kCtlFlags);
        flags = static_cast<std::uint8_t>((flags & ~kCtlVisible) | (g_setup.switchFlagsWas & kCtlVisible));
    }
    const char* const tags[] = {"LBL_LTEXT", "LBL_RTEXT"};
    void* labels[2] = {};
    for (int i = 0; i < 2; ++i) {
        void* const label = AppendControlLike(panel, tags[i], kLabelSize, LabelCtor);
        labels[i] = label;
        if (!label) continue;
        At<std::uint8_t>(label, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
        String none;
        StringFromText(&none, "");
        SetTextOf(Part(label, kLabelTextParams), &none);
        StringDestroy(&none);
        std::uint8_t& style = At<std::uint8_t>(label, kLabelBorder + kParamsStyle);
        style = static_cast<std::uint8_t>((style & ~3) | 2);       // stretched over its label (FILLSTYLE 2)
    }
    g_setup.lt = labels[0];
    g_setup.rt = labels[1];
    overlays::Centre(add, true);
    overlays::Centre(Part(panel, kAccept), true);
    // Add Card's caption. The game sets it only as LT or RT move between the lists, so on the PC it
    // was empty until then. The available list has the focus first.
    SetStrRef(Part(add, kButtonTextParams), kAddCardString);
    // Laid out now, before the screen is first drawn.
    UpdateSetup();
}

// A trigger glyph `height` tall with its far edge at `edge` (its right edge for LT, which stands
// left of its arrow, its left edge for RT), on the line `middle`. Windows draws the glyph at the
// size; here the carried square picture is stretched over a label of that size.
void TriggerGlyph(void* label, const char* code, float edge, bool rightEdge, float middle, float height, Box& at, char& drawnFor) {
    if (!label) return;
    const int size = static_cast<int>(std::lround(height));
    const Box asked{rightEdge ? static_cast<int>(std::lround(edge)) - size : static_cast<int>(std::lround(edge)),
                    static_cast<int>(std::lround(middle - height / 2)), size, size};
    const char family = prompts::FamilyLetter();
    if (!Same(at, asked) || drawnFor != family) {
        char name[kResRefBytes] = {};
        std::snprintf(name, sizeof name, "kmr%crm%s", family, code);
        SetBox(label, asked);
        SetFill(Part(label, kLabelBorder), name);
        at = asked;
        drawnFor = family;
    }
    At<std::uint8_t>(label, kCtlFlags) |= kCtlVisible;
}

void SetupToLayout(void* add, std::uint8_t switchFlagsWas) {
    for (Place& p : g_setup.places) {
        if (p.at.width > 0) SetBox(p.control, p.was);
        p.at = Box{};
    }
    std::uint8_t& flags = At<std::uint8_t>(add, kCtlFlags);
    flags = static_cast<std::uint8_t>((flags & ~kCtlVisible) | (switchFlagsWas & kCtlVisible));
}

void HideGlyphs() {
    for (void* const label : {g_setup.lt, g_setup.rt})
        if (label) At<std::uint8_t>(label, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
}

// Every frame the screen is up.
void UpdateSetup() {
    Setup& g = g_setup;
    void* const panel = g.panel;
    if (!panel || !Readable(panel, kRightText + kLabelSize) || VtableOf(panel) != kSetupVtable) return;
    char* const params = PanelFillParams(panel);
    if (!params) return;
    char* const fill = params + kParamsFill;
    if (!g.fillWas[0] || (strncasecmp(fill, g.drawn, 16) != 0 && strncasecmp(fill, g.fillWas, 16) != 0)) std::memcpy(g.fillWas, fill, 16);
    void* const add = Part(panel, kSwitch);
    void* const play = Part(panel, kAccept);
    void* const title = Part(panel, kTitle);
    void* const ltext = Part(panel, kLeftText);
    void* const rtext = Part(panel, kRightText);
    const bool shown = device::PadInUse();
    Layout L;
    if (!shown || !LayoutFor(panel, L)) {
        if (g.shown == 1) {
            SetupToLayout(add, g.switchFlagsWas);
            if (g.fillWas[0] && strncasecmp(fill, g.fillWas, 16) != 0) SetFill(params, g.fillWas);
        }
        HideGlyphs();
        g.shown = 0;
        return;
    }
    const float u = L.s;
    // The cards: the available ones' columns spread over the wider left panel, the chosen ones'
    // spaced evenly in the frame; rows as the layout has them. A card's face label and (for an
    // available card) its count go with it.
    std::vector<int> availCols;
    for (int i = 0; i < 18; ++i) availCols.push_back(EntryOf(Card(panel, kAvailable, i)).was.left);
    availCols = Columns(availCols, L.cardW);
    std::vector<int> chosenCols;
    for (int i = 0; i < 10; ++i) chosenCols.push_back(EntryOf(Card(panel, kChosen, i)).was.left);
    chosenCols = Columns(chosenCols, L.cardW);
    const auto moveCard = [&](void* card, int newLeft) {
        const Box was = EntryOf(card).was;
        const int dx = newLeft - was.left;
        Move(card, {newLeft, was.top, was.width, was.height});
        void* const face = Part(card, kCardFace);
        const Box fw = EntryOf(face).was;
        Move(face, {fw.left + dx, fw.top, fw.width, fw.height});
        return dx;
    };
    std::vector<std::pair<Box, int>> availMoved;       // each available card's place and move
    for (int i = 0; i < 18; ++i) {
        void* const card = Card(panel, kAvailable, i);
        const Box was = EntryOf(card).was;
        const int col = ColumnOf(availCols, was.left);
        availMoved.push_back({was, moveCard(card, static_cast<int>(std::lround(L.availLeft + L.availPitch * col)))});
    }
    for (int i = 0; i < 10; ++i) {
        void* const card = Card(panel, kChosen, i);
        const Box was = EntryOf(card).was;
        const int col = ColumnOf(chosenCols, was.left);
        if (col < static_cast<int>(L.chosenCols.size())) moveCard(card, L.chosenCols[col]);
    }
    // Each count goes with the card it stands on (the nearest, by their middles).
    for (int i = 0; i < 18; ++i) {
        void* const num = Part(panel, kCounts + static_cast<std::size_t>(i) * kLabelSize);
        const Box nw = EntryOf(num).was;
        long long best = LLONG_MAX;
        int dx = 0;
        for (const auto& m : availMoved) {
            const long long ddx = (nw.left + nw.width / 2) - (m.first.left + m.first.width / 2);
            const long long ddy = (nw.top + nw.height / 2) - (m.first.top + m.first.height / 2);
            if (ddx * ddx + ddy * ddy < best) {
                best = ddx * ddx + ddy * ddy;
                dx = m.second;
            }
        }
        Move(num, {nw.left + dx, nw.top, nw.width, nw.height});
    }
    // What stands in the middle column, at the Xbox's places (its 640x480 units) in the column as
    // spaced here: the title, Add Card and Play (glyph and caption centred together), and the two
    // list titles centred in their bars.
    const auto box = [&](float x0, float y0, float x1, float y1) {
        return Box{static_cast<int>(std::lround(L.X(x0))), static_cast<int>(std::lround(L.Y(y0))),
                   static_cast<int>(std::lround(L.X(x1) - L.X(x0))), static_cast<int>(std::lround(L.Y(y1) - L.Y(y0)))};
    };
    {
        const Box tw = EntryOf(title).was;
        const Box t = box(259, 34, 443, 67);
        Move(title, {t.left + t.width / 2 - std::max(t.width, tw.width) / 2, t.top, std::max(t.width, tw.width), t.height});
    }
    // Add Card and Play centred on the column.
    const auto centred = [&](float width, float y0, float y1) {
        return Box{static_cast<int>(std::lround(L.mid - width * u / 2)), static_cast<int>(std::lround(L.Y(y0))),
                   static_cast<int>(std::lround(width * u)), static_cast<int>(std::lround(L.Y(y1) - L.Y(y0)))};
    };
    Move(add, centred(143, 161, 193));
    // Add Card's caption in the list titles' blue, not the button's own dim blue. The game sets the
    // button's colour as the focus moves, so it is set again every frame.
    {
        const float* const blue = &At<float>(ltext, kLabelTextParams + kTextColour);
        const float* const mine = &At<float>(add, kButtonTextParams + kTextColour);
        if (std::memcmp(blue, mine, 12) != 0) {
            const float colour[3] = {blue[0], blue[1], blue[2]};
            SetTextColour(Part(add, kButtonTextParams), colour);
        }
    }
    Move(play, centred(136, 408, 441));
    At<std::uint8_t>(add, kCtlFlags) |= kCtlVisible;
    const float avMid = (L.Y(198.8f) + L.Y(250.3f)) / 2, chMid = (L.Y(251.25f) + L.Y(290.6f)) / 2;
    const float rowH = 32.0f * u;
    int ltLeft = 0, rtRight = 0;
    {
        // "Available Cards" is left-aligned in its label (ALIGNMENT 17), "Chosen Cards"
        // right-aligned (20): each label is placed so its text is centred on the column.
        const int lw = TextWidth(ltext);
        const int rw = TextWidth(rtext);
        const Box lwas = EntryOf(ltext).was, rwas = EntryOf(rtext).was;
        if (lw > 0) {
            ltLeft = static_cast<int>(std::lround(L.mid - lw / 2.0f));
            Move(ltext, {ltLeft, static_cast<int>(std::lround(avMid - rowH / 2)), std::max(lw + 2, lwas.width / 4), static_cast<int>(std::lround(rowH))});
        }
        if (rw > 0) {
            rtRight = static_cast<int>(std::lround(L.mid + rw / 2.0f));
            const int width = std::max(rw + 2, rwas.width / 4);
            Move(rtext, {rtRight - width, static_cast<int>(std::lround(chMid - rowH / 2)), width, static_cast<int>(std::lround(rowH))});
        }
    }
    // The trigger glyphs beyond the cyan arrows: LT left of "Available Cards", RT right of "Chosen
    // Cards" (the arrow 13 x 0.9 units long, 4 units from the text, 3 more to the glyph).
    const float glyphH = 18.0f * u;
    const float arrowLen = 13.0f * 0.9f * u;
    if (ltLeft > 0) TriggerGlyph(g.lt, "lt", ltLeft - 4.0f * u - arrowLen - 3.0f * u, true, avMid, glyphH, g.ltAt, g.ltFor);
    if (rtRight > 0) TriggerGlyph(g.rt, "rt", rtRight + 4.0f * u + arrowLen + 3.0f * u, false, chMid, glyphH, g.rtAt, g.rtFor);
    // The picture, drawn again only when what it shows has changed.
    std::uint32_t key = 2166136261u;
    for (int v : {L.panel.left, L.panel.top, L.panel.width, L.panel.height, ltLeft, rtRight, static_cast<int>(L.leftR),
                  static_cast<int>(L.frameL), static_cast<int>(L.boxL)})
        key = (key ^ static_cast<std::uint32_t>(v)) * 16777619u;
    if (!g.drawn[0] || g.drawnFor != key) {
        char out[kResRefBytes] = {};
        if (Picture(L, ltLeft, rtRight, out)) {
            std::memcpy(g.drawn, out, sizeof out);
            g.drawnFor = key;
        }
    }
    // Nothing is shown until the picture is: the controls go back in this same frame, before it is
    // drawn, and all of it changes together once the picture is made.
    if (!g.drawn[0]) {
        SetupToLayout(add, g.switchFlagsWas);
        HideGlyphs();
        g.shown = 0;
        return;
    }
    if (strncasecmp(fill, g.drawn, 16) != 0) SetFill(params, g.drawn);
    // Add Card's badge placed for its caption of this frame: the game changes it to Remove Card
    // as the focus changes lists, and glyph and word stay centred together.
    Badge(panel, add, "kmrpy_pzswitch");
    g.shown = 1;
}

// The screen's end: the two labels freed while the panel holds them.
void ForgetSetup(void* panel) {
    if (panel != g_setup.panel || !Ending(panel)) return;
    overlays::Centre(Part(panel, kSwitch), false);
    overlays::Centre(Part(panel, kAccept), false);
    for (void* const label : {g_setup.lt, g_setup.rt})
        if (label) FreeAppended(panel, label);
    g_setup = Setup{};
}

// ------------------------------------------------------------------ class selection's Select

const std::uintptr_t kClassVtable = 0x1005af890UL;
const std::size_t kClassCancel = 0x19b0;
const std::uint64_t kSelectString = 236;           // "Select"

struct ClassSelect {
    void* panel = nullptr;
    void* select = nullptr;                // ours
    Box cancelWas{};                       // Cancel where the layout put it
    char fillWas[kResRefBytes] = {};       // the panel's own picture
    // The drawing, for the picture, panel and Cancel it was made for.
    char madeFor[kResRefBytes] = {};
    Box panelFor{}, cancelFor{};
    bool made = false, ok = false;
    char drawn[kResRefBytes] = {};
    Box selectAt{}, cancelAt{};
} g_class;

// The panel's picture drawn with two capsules between its arrows. `made` is left false only while
// the picture cannot be read yet; `ok` says the foot was a capsule between two arrows.
void ClassArt() {
    ClassSelect& g = g_class;
    g.made = g.ok = false;
    int width = 0, height = 0;
    void* reference = nullptr;
    unsigned char* const pixels = ReadTexture(g.fillWas, &reference, &width, &height);
    if (reference) AssignTexture(&reference, nullptr);
    if (!pixels) return;
    g.made = true;
    const ClassBoxK1 panel{g.panelFor.left, g.panelFor.top, g.panelFor.width, g.panelFor.height};
    const ClassBoxK1 cancel{g.cancelFor.left, g.cancelFor.top, g.cancelFor.width, g.cancelFor.height};
    ClassArtResultK1 result;
    const bool built = BuildClassSelectArtK1(g.fillWas, panel, cancel, pixels, width, height, result);
    std::free(pixels);
    if (!built || !WritePicture(result.drawn, result.sheet, width, height)) return;
    std::memcpy(g.drawn, result.drawn, sizeof g.drawn);
    g.selectAt = {result.selectAt.left, result.selectAt.top, result.selectAt.width, result.selectAt.height};
    g.cancelAt = {result.cancelAt.left, result.cancelAt.top, result.cancelAt.width, result.cancelAt.height};
    g.ok = true;
}

// As the screen is built: Select made, hidden, with its caption, and kept off the focus.
void InstallClassSelect(void* panel) {
    g_class = ClassSelect{};
    g_class.panel = panel;
    void* const select = AppendControlLike(panel, "BTN_BACK", kButtonSize, ButtonCtor);
    if (!select) return;
    g_class.select = select;
    overlays::Centre(select, true);
    overlays::Centre(Part(panel, kClassCancel), true);
    At<std::uint8_t>(select, kCtlFlags) &= static_cast<std::uint8_t>(~kCtlVisible);
    layout::PadFocusExclude(select, true);
    if (void* const client = engine::ClientApp()) {
        String words;
        GetGuiString(&words, client, kSelectString);
        SetTextOf(Part(select, kButtonTextParams), &words);
        StringDestroy(&words);
    }
}

// Every frame the screen is up: with the pad in use the drawn picture, Cancel on the right capsule
// and Select on the left one; otherwise all as the layout has it.
void UpdateClassSelect() {
    ClassSelect& g = g_class;
    void* const panel = g.panel;
    if (!panel || !g.select || !Readable(panel, kClassCancel + kButtonSize) || VtableOf(panel) != kClassVtable) return;
    char* const params = PanelFillParams(panel);
    if (!params) return;
    void* const cancel = Part(panel, kClassCancel);
    char* const fill = params + kParamsFill;
    const Box panelBox = BoxOf(panel);
    const Box cancelNow = BoxOf(cancel);
    // The layout's own, taken again whenever something other than this moved them (the screen
    // laid out again for another size).
    if (!g.fillWas[0] || (strncasecmp(fill, g.drawn, 16) != 0 && strncasecmp(fill, g.fillWas, 16) != 0)) std::memcpy(g.fillWas, fill, 16);
    if (g.cancelWas.width == 0 || (!Same(cancelNow, g.cancelAt) && !Same(cancelNow, g.cancelWas))) g.cancelWas = cancelNow;
    bool shown = device::PadInUse();
    if (shown && (!g.made || strncasecmp(g.madeFor, g.fillWas, 16) != 0 || !Same(g.panelFor, panelBox) || !Same(g.cancelFor, g.cancelWas))) {
        std::memcpy(g.madeFor, g.fillWas, 16);
        g.panelFor = panelBox;
        g.cancelFor = g.cancelWas;
        ClassArt();                        // made once its picture is uploaded: until then nothing changes
    }
    shown = shown && g.made && g.ok;
    std::uint8_t& flags = At<std::uint8_t>(g.select, kCtlFlags);
    if (shown) {
        if (strncasecmp(fill, g.drawn, 16) != 0) SetFill(params, g.drawn);
        SetBox(cancel, g.cancelAt);
        SetBox(g.select, g.selectAt);
        flags |= kCtlVisible;
    } else {
        if (g.fillWas[0] && strncasecmp(fill, g.fillWas, 16) != 0) SetFill(params, g.fillWas);
        if (g.cancelWas.width > 0) SetBox(cancel, g.cancelWas);
        flags &= static_cast<std::uint8_t>(~kCtlVisible);
    }
    Badge(panel, g.select, shown ? "kmrpa_clssel" : nullptr);
}

// The screen's end: Select freed while the panel holds it.
void ForgetClassSelect(void* panel) {
    if (panel != g_class.panel || !Ending(panel)) return;
    overlays::Centre(Part(panel, kClassCancel), false);
    if (void* const select = g_class.select) {
        overlays::Centre(select, false);
        layout::PadFocusExclude(select, false);
        FreeAppended(panel, select);
    }
    g_class = ClassSelect{};
}

}  // namespace

void Install(void* panel) {
    if (!LooksLikePointer(panel) || !LooksLikePointer(At<void*>(panel, kPanelGff))) return;
    const std::uintptr_t vtable = VtableOf(panel);
    if (vtable == kGameVtable) InstallTable(panel);
    else if (vtable == kSetupVtable) InstallSetup(panel);
    else if (vtable == kClassVtable) InstallClassSelect(panel);
}

void Update() {
    UpdateTable();
    UpdateSetup();
    UpdateClassSelect();
}

void ActionFlash(void* panel, bool flip) {
    if (panel != g_table.panel) return;
    void* const button = flip ? g_table.flip : g_table.play;
    if (!button) return;
    At<float>(button, kPulse) = 0.8f;
    At<float>(button, kPulse + 4) = 0.4f;
    At<float>(button, kPulse + 8) = 1.0f;
    At<float>(button, kPulse + 12) = 1.0f;
}

void Forget(void* panel) {
    ForgetTable(panel);
    ForgetSetup(panel);
    ForgetClassSelect(panel);
}

}  // namespace pazaak
}  // namespace kmrp
