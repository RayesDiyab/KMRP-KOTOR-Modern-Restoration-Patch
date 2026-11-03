// KMRP for macOS, controller support: the Controller Layout screen, its entry on the Gameplay
// screen, the A beside a confirmation box's focused button and at the end of the highlighted
// reply in a conversation, and the status summary laid out again at the font's size.
//
// The Mac port of src/controller-native/K1ControllerLayout.cpp, with the same rules; the
// reasoning is written there and in docs/controller-layout.md. The screen is a plain
// CSWGuiPanel that KMRP builds from kmrplayout.gui (tools/build_controller_layout.py), with a
// copy of the base panel's vtable whose destructors and input handler are KMRP's; the entry is a
// button bound by tag (BTN_KMRPLAY, which the resource build adds to optgameplay.gui) while the
// Gameplay screen still has its .gui.
//
// On the Mac (KOTOR_Exe 1.4.0): CSWGuiPanel's constructor is 0x10049D7F8 (a bare panel is 0x80
// bytes), its complete destructor 0x10049D8C8, its vtable 0x1005B3730 (28 entries: the complete
// and deleting destructors first, as the Itanium ABI has them, HandleInputEvent at +0x80);
// StartLoadFromLayout (panel, CResRef*) 0x10049DFE4 and StopLoadFromLayout 0x10049D986;
// CSWGuiManager::AddPanel 0x10049ECAE, PanelExists 0x10049D9CE, RemovePanel 0x10049DA14; the
// manager deletes a panel whose flags word (+0x5C) has 0x400 of 0x600, as on Windows (0x10049F6xx);
// a button is 0x240 bytes (constructor 0x1004A5E8E), a label 0x198 (0x1004A54AA);
// CSWGuiControl::AddEvent (control, event, receiver, handler, this-adjust) 0x1004A4C5A, whose
// handler is called with the receiver and the control, for a press and a release alike, the value
// left at control +0x70. CSWGuiInGameGameplay is 0x1005A76D0;
// CSWGuiMessageBox 0x1005AE880 with OK at +0x3D0 and Cancel at +0x610; the Solo Mode query,
// built on it, 0x1005ABEA0.
#include "layout.h"
#include "../kmrp-layout/text.h"

#include "engine.h"
#include "pad.h"
#include "preload.h"
#include "prompts.h"
#include "remap.h"
#include "state.h"

#include <ApplicationServices/ApplicationServices.h>
#include <dlfcn.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>
#include <string>

namespace kmrp {
namespace layout {
namespace {

using engine::At;

// Rows on the screen: GLYPH_nn and TEXT_nn each; then the edge art, DECO_nn; then GLYPH_BACK.
// Must equal ROWS and len(DECOR) in tools/build_controller_layout.py and
// tools/controller_layout_backdrop.py, as on Windows.
const int kRows = 13;
const int kFixed = 10;   // the ten controls before the rows
const int kDecor = 10;
const int kBackGlyph = kFixed + 2 * kRows + kDecor;
const int kControls = kBackGlyph + 1;
// The file's controls, then the remap screen's own (BindAppend): 10 rows of a frame, a grey
// caption and a dot, five padlocks, the footer's six, the two prompts' fourteen, and the table's:
// two heads, two lines, and a name and a picture for each of its fifteen rows.
const unsigned kOwnedSlots = 192;
const unsigned kTableControls = 2 + 2 + 2 * 10 + 2 * 5;
static_assert(kControls + 3 * 10 + 5 + 6 + 14 + kTableControls <= kOwnedSlots, "owned[] holds every control");

using CtorFn = void (*)(void* object);
using PanelCtorFn = void (*)(void* panel, void* manager);
using InitControlFn = void (*)(void* panel, void* control, void* tag, int add);
using StringFn = void (*)(void* string, const char* text);
using StringFreeFn = void (*)(void* string);
using ResRefFn = void (*)(void* resref, const char* text);
using LoadFn = void (*)(void* panel, const void* resref);
using PanelFn = void (*)(void* panel);
using AddEventFn = void (*)(void* control, int event, void* receiver, void* handler, long adjust);
using AddPanelFn = void (*)(void* manager, void* panel, int flags, int sound);
using ExistsFn = int (*)(void* manager, void* panel);
using SetActiveFn = void (*)(void* panel, void* control, int sound);
using HandleFn = void (*)(void* panel, int event, int value);
using SetExtentFn = void (*)(void* control, const int* rect);
using SetFillImageFn = void (*)(void* params, const void* resref, int force);
using DeletingDtorFn = void (*)(void* object);

template <typename T> T Fn(std::uintptr_t address) { return reinterpret_cast<T>(address); }

// Controls a screen keeps for the mouse but takes off the pad's focus: buttons the pad presses with
// a button of its own, which the D-pad must not land on. A control that cannot be selected cannot
// be clicked either, so the selectable flag is not the way. Registered by the screen as it opens
// and taken back as it closes, so no address outlives its control (g_padFocusExcluded).
void* g_padFocusExcluded[32] = {};

const std::uintptr_t kLabelCtor = 0x1004a54aaUL, kButtonCtor = 0x1004a5e8eUL;
const std::size_t kLabelSize = 0x198, kButtonSize = 0x240, kPanelSize = 0x80;
const std::uintptr_t kPanelCtor = 0x10049d7f8UL, kPanelDtor = 0x10049d8c8UL;
const std::uintptr_t kBasePanelVtable = 0x1005b3730UL;
const int kBaseVtableSlots = 28;
const std::uintptr_t kInitControl = 0x10049e476UL;
const std::uintptr_t kStringCtor = 0x10034cca8UL, kStringDtor = 0x10034cdf2UL, kResRefCtor = 0x100367b62UL;
const std::uintptr_t kStartLoad = 0x10049dfe4UL, kStopLoad = 0x10049d986UL;
const std::uintptr_t kAddEvent = 0x1004a4c5aUL;
const std::uintptr_t kAddPanel = 0x10049ecaeUL, kPanelExists = 0x10049d9ceUL, kRemovePanel = 0x10049da14UL;
const std::uintptr_t kSetActive = 0x10049de24UL, kPanelHandleInput = 0x10049dc72UL;
const std::uintptr_t kSetFillImage = 0x1004a17c2UL;

const std::uintptr_t kGameplayVtable = 0x1005a76d0UL;      // CSWGuiInGameGameplay
const std::uintptr_t kMessageBoxVtable = 0x1005ae880UL;    // CSWGuiMessageBox
const std::uintptr_t kSoloModeVtable = 0x1005abea0UL;      // CSWGuiSoloModeQuery
const std::size_t kMessageBoxOk = 0x3d0, kMessageBoxCancel = 0x610;

const std::size_t kPanelManager = 0x20, kPanelActive = 0x28, kPanelControls = 0x30, kPanelControlCount = 0x38;
const std::size_t kPanelGff = 0x40, kPanelFlags = 0x5c;
const std::size_t kCtlExtent = 0x08, kCtlId = 0x74, kCtlFlags = 0x68;
const std::uint8_t kCtlVisible = 0x02;
const std::size_t kLabelFillParams = 0x88 + 0x18;   // the label's border params
const std::size_t kVtSetExtent = 0x10, kVtDeletingDtor = 0x08;
const int kEventA = 0x27, kEventB = 0x28;

bool LooksLikePointer(const void* p) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    return v >= 0x100000 && v < 0x800000000000ULL;
}
std::uintptr_t VtableOf(void* object) { return LooksLikePointer(object) ? At<std::uintptr_t>(object, 0) : 0; }

struct Entry { void* parent; void* button; bool badged; char family; };
Entry g_entries[8] = {};
void* g_pending = nullptr;
void* g_current = nullptr;
void* g_parent = nullptr;
void* g_returnFocus = nullptr;
std::uintptr_t g_table[kBaseVtableSlots + 2] = {};   // offset-to-top, RTTI, then the slots
unsigned g_created = 0, g_destroyed = 0, g_controlsCreated = 0, g_controlsDestroyed = 0, g_callbacks = 0;
char g_family = 0;
int g_device = -1;
void* g_owned[kOwnedSlots] = {};
unsigned g_ownedCount = 0;
// The press that opens the screen must not also close it, nor the press that closes it reopen
// it: Back and the entry wait until confirm has been seen released on two frames running.
int g_releasedFrames = 0;
const int kArmFrames = 2;
bool Armed() { return g_releasedFrames >= kArmFrames; }
bool g_blockReopen = false;
bool g_remapDirty = true;

// The remap screen, further down.
bool BuildRemap(void* panel);
void LayoutRemap();
void RemapFrame();
void ForgetRemap();
void HandleBack();
bool RemapInput(int event, int value);

void Note(const char* event) {
    Log("layout: %s (screen %p, parent %p; %u opened, %u closed, controls %u made, %u freed, %u callbacks, "
        "art %c, pad %d)",
        event, g_current, g_parent, g_created, g_destroyed, g_controlsCreated, g_controlsDestroyed, g_callbacks,
        g_family ? g_family : '-', g_device);
}

void DestroyControl(void* control) {
    if (!LooksLikePointer(control)) return;
    reinterpret_cast<DeletingDtorFn>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtDeletingDtor))(control);
    ++g_controlsDestroyed;
}

// A control bound by tag, as the panel's own are, or null when the .gui has no such tag.
void* Bind(void* panel, const char* tag, bool button) {
    void* control = ::operator new(button ? kButtonSize : kLabelSize, std::nothrow);
    if (!control) return nullptr;
    std::memset(control, 0, button ? kButtonSize : kLabelSize);
    Fn<CtorFn>(button ? kButtonCtor : kLabelCtor)(control);
    ++g_controlsCreated;
    void* name[2] = {nullptr, nullptr};   // CExoString
    Fn<StringFn>(kStringCtor)(name, tag);
    Fn<InitControlFn>(kInitControl)(panel, control, name, 1);
    Fn<StringFreeFn>(kStringDtor)(name);
    const int id = At<int>(control, kCtlId), count = At<int>(panel, kPanelControlCount);
    void** array = At<void**>(panel, kPanelControls);
    if (!LooksLikePointer(array) || id < 0 || id >= count || array[id] != control) {
        DestroyControl(control);
        Note("a control's tag is not in its .gui");
        return nullptr;
    }
    return control;
}

void ShowControl(void* control, bool visible) {
    std::uint8_t& flags = At<std::uint8_t>(control, kCtlFlags);
    flags = visible ? (flags | kCtlVisible) : (flags & ~kCtlVisible);
}

void SetExtent(void* control, const int* rect) {
    reinterpret_cast<SetExtentFn>(*reinterpret_cast<std::uintptr_t*>(VtableOf(control) + kVtSetExtent))(control, rect);
}

void SetFill(void* label, const char* resref) {
    char name[32] = {};
    std::snprintf(name, sizeof name, "%s", resref);
    Fn<SetFillImageFn>(kSetFillImage)(static_cast<char*>(label) + kLabelFillParams, name, 1);
}

// The manager's Update removes the panel and calls its deleting destructor. Never delete a
// panel from its own control's callback.
void RequestClose() {
    if (!g_current) return;
    std::uint16_t& flags = At<std::uint16_t>(g_current, kPanelFlags);
    flags = static_cast<std::uint16_t>((flags & ~0x700u) | 0x400u);
    Note("close requested");
}

// Handlers, called as (receiver, control).
void OnBack(void*, void* control) {
    ++g_callbacks;
    if (!At<int>(control, 0x70)) return;   // its release: CSWGuiControl::HandleInputEvent tells both
    if (!Armed()) { Note("Back ignored: the opening press is still down"); return; }
    HandleBack();
}
void OnOpen(void* owner, void*) {
    ++g_callbacks;
    if (g_blockReopen) { Note("the entry ignored: the closing press is still down"); return; }
    if (!g_current && !g_pending) g_pending = owner;
}

// The screen's HandleInputEvent: the remap screen's buttons, then B leaves; the rest is the base
// panel's.
void ScreenInput(void* self, int event, int value) {
    if (RemapInput(event, value)) return;
    if (value && event == kEventB) { HandleBack(); return; }
    Fn<HandleFn>(kPanelHandleInput)(self, event, value);
}

// The screen's destructors. The manager has removed the panel already on a normal close; an
// engine shutdown may destroy it still attached.
void Destroy(void* self) {
    void* manager = At<void*>(self, kPanelManager);
    if (LooksLikePointer(manager) && Fn<ExistsFn>(kPanelExists)(manager, self))
        Fn<ExistsFn>(kRemovePanel)(manager, self);
    Fn<SetActiveFn>(kSetActive)(self, nullptr, 0);
    void** array = At<void**>(self, kPanelControls);
    for (int i = 0; LooksLikePointer(array) && i < At<int>(self, kPanelControlCount); ++i) array[i] = nullptr;
    for (unsigned i = 0; i < g_ownedCount; ++i) { DestroyControl(g_owned[i]); g_owned[i] = nullptr; }
    g_ownedCount = 0;
    ForgetRemap();
    Fn<PanelFn>(kPanelDtor)(self);
    g_current = nullptr;
    ++g_destroyed;
    if (g_parent && LooksLikePointer(manager) && Fn<ExistsFn>(kPanelExists)(manager, g_parent))
        Fn<SetActiveFn>(kSetActive)(g_parent, g_returnFocus, 0);
    g_parent = nullptr;
    g_returnFocus = nullptr;
    g_blockReopen = true;
    g_releasedFrames = 0;
    Note("closed");
}
void DestroyComplete(void* self) { Destroy(self); }
void DestroyDeleting(void* self) {
    Destroy(self);
    ::operator delete(self);
}

// The screen follows the pad: its family's heading, diagram and row glyphs, which device is in
// use, and the B inside Back while the pad is. Only on a change.
void Refresh() {
    const char next = prompts::FamilyLetter();
    const int active = device::PadInUse() ? 1 : 0;
    if (next == g_family && active == g_device) return;
    g_family = next;
    g_device = active;
    void** array = At<void**>(g_current, kPanelControls);
    // IDs 2..5 are the family headings, 6 and 7 the device in use.
    for (int i = 2; i < 8; ++i)
        if (array[i]) ShowControl(array[i], i < 6 ? "psnd"[i - 2] == g_family : i == 6 + active);
    char resref[32];
    if (array[8]) {   // the diagram, drawn per family
        std::snprintf(resref, sizeof resref, "kmr%clytdiag", g_family);
        SetFill(array[8], resref);
    }
    if (void* backGlyph = array[kBackGlyph]) {
        std::snprintf(resref, sizeof resref, "kmr%clytbk", g_family);
        SetFill(backGlyph, resref);
        ShowControl(backGlyph, active != 0);
    }
    for (int i = 0; i < kRows; ++i) {
        void* glyph = array[kFixed + i];
        if (!glyph) continue;
        std::snprintf(resref, sizeof resref, "kmr%clyt%02d", g_family, i);
        SetFill(glyph, resref);
    }
    g_remapDirty = true;   // the rows' glyphs and the footer's are the remap screen's again
    Note("refreshed");
}

void Open(void* manager, void* owner) {
    void* panel = ::operator new(kPanelSize, std::nothrow);
    if (!panel) return;
    std::memset(panel, 0, kPanelSize);
    Fn<PanelCtorFn>(kPanelCtor)(panel, manager);
    std::memcpy(g_table, reinterpret_cast<const void*>(kBasePanelVtable - 16), sizeof g_table);
    g_table[2 + 0] = reinterpret_cast<std::uintptr_t>(&DestroyComplete);
    g_table[2 + 1] = reinterpret_cast<std::uintptr_t>(&DestroyDeleting);
    g_table[2 + 16] = reinterpret_cast<std::uintptr_t>(&ScreenInput);   // HandleInputEvent, +0x80
    At<std::uintptr_t*>(panel, 0) = &g_table[2];
    g_current = panel;
    g_parent = owner;
    g_returnFocus = At<void*>(owner, kPanelActive);
    ++g_created;
    g_ownedCount = 0;
    char resref[32] = {};
    Fn<ResRefFn>(kResRefCtor)(resref, "kmrplayout");
    Fn<LoadFn>(kStartLoad)(panel, resref);
    static const char* const kTags[kFixed] = {"LBL_TITLE", "BTN_BACK", "LBL_XBOX", "LBL_PS", "LBL_SWITCH",
                                              "LBL_DECK", "LBL_KBM", "LBL_PAD", "LBL_DIAGRAM", "LBL_HELP"};
    bool complete = true;
    void* backButton = nullptr;
    for (int i = 0; i < kControls; ++i) {
        char tag[24] = {};
        const int row = i - kFixed;
        if (i < kFixed) std::snprintf(tag, sizeof tag, "%s", kTags[i]);
        else if (row < kRows) std::snprintf(tag, sizeof tag, "GLYPH_%02d", row);
        else if (row < 2 * kRows) std::snprintf(tag, sizeof tag, "TEXT_%02d", row - kRows);
        else if (i == kBackGlyph) std::snprintf(tag, sizeof tag, "GLYPH_BACK");
        else std::snprintf(tag, sizeof tag, "DECO_%02d", row - 2 * kRows);
        void* control = Bind(panel, tag, i == 1);
        if (!control) { complete = false; break; }
        g_owned[g_ownedCount++] = control;
        if (i == 1) backButton = control;
    }
    ForgetRemap();
    if (complete && !BuildRemap(panel)) complete = false;
    Fn<PanelFn>(kStopLoad)(panel);
    if (!complete) { DestroyDeleting(panel); return; }
    Fn<AddEventFn>(kAddEvent)(backButton, kEventA, panel, reinterpret_cast<void*>(&OnBack), 0);
    // Opened in View: nothing there is a place for the focus; the screen's buttons are pad buttons
    // (Default Y, Remap X, Back B).
    Fn<SetActiveFn>(kSetActive)(panel, nullptr, 0);
    g_family = 0;
    g_device = -1;
    g_releasedFrames = 0;
    Refresh();
    LayoutRemap();
    Fn<AddPanelFn>(kAddPanel)(manager, panel, 3, 1);
    Note("opened");
}

// ---------------------------------------------------------------- the entry's A

// The Controller Layout entry's A, while it has its screen's focus and the pad is in use --
// FocusOnly, as Mouse and Key Mapping above it. Repainted only on a change.
void UpdateEntryBadges() {
    const bool pad = device::PadInUse();
    const char glyph = prompts::FamilyLetter();
    for (Entry& e : g_entries) {
        if (!e.parent) continue;
        const bool want = pad && At<void*>(e.parent, kPanelActive) == e.button;
        if (want == e.badged && (!want || glyph == e.family)) continue;
        prompts::PaintLayoutEntry(e.button, want);
        e.badged = want;
        e.family = glyph;
    }
}

// ---------------------------------------------------------------- confirm A

// The A beside a confirmation box's focused button (Exit Game, Solo Mode, overwrite and delete
// save all use CSWGuiMessageBox and confirm.gui). Its buttons shrink to their captions, so the
// badge is a label of its own, LBL_KMRPA, moved each frame to the left of whichever button has
// the focus: a disc the button's height, a quarter of that clear of its left edge.
struct ConfirmBadge { void* panel; void* label; char family; bool shown; };
ConfirmBadge g_confirmBadges[8] = {};

void UpdateConfirmBadges() {
    const bool pad = device::PadInUse();
    const char family = prompts::FamilyLetter();
    for (ConfirmBadge& b : g_confirmBadges) {
        if (!b.panel) continue;
        void* active = At<void*>(b.panel, kPanelActive);
        char* base = static_cast<char*>(b.panel);
        const bool onButton = active == base + kMessageBoxOk || active == base + kMessageBoxCancel;
        if (!pad || !onButton) {
            if (b.shown) { ShowControl(b.label, false); b.shown = false; }
            continue;
        }
        const int* r = reinterpret_cast<const int*>(static_cast<char*>(active) + kCtlExtent);
        const int size = r[3];
        const int rect[4] = {r[0] - size - size / 4, r[1], size, size};
        SetExtent(b.label, rect);
        if (family != b.family) {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%ccnfa", family);
            SetFill(b.label, resref);
            b.family = family;
        }
        if (!b.shown) { ShowControl(b.label, true); b.shown = true; }
    }
}

// ---------------------------------------------------------------- text as drawn

// A range that can be read: its first and last byte answer (readable()'s part).
// The text measuring is shared with the status summary's layout, which every build has
// (kmrp-layout/status_summary.cpp).
using text::Font;
using text::FontOf;
using text::GlyphWidth;
using text::LabelTextWidth;
using text::Readable;
using text::SetExtentIfChanged;
using text::kLabelText;
using text::kObjLineCount;
using text::kObjLineLengths;
using text::kObjScale;
using text::kObjString;
using text::kTextObject;

// Where a text's last line ends, in pixels from its left edge, from the layout the engine draws
// (lastReplyLine): a negative length is the same length, and one space or newline after a line
// is skipped.
struct ReplyLine { int width; int lines; float scale; int lineHeight; };

bool LastLine(void* text, ReplyLine& out) {
    char* const object = At<char*>(text, kTextObject);
    if (!Readable(object, 0x60)) return false;
    const char* const string = At<const char*>(object, kObjString);
    const int lines = At<int>(object, kObjLineCount);
    const int* const lengths = At<const int*>(object, kObjLineLengths);
    if (lines < 1 || lines > 32 || !Readable(lengths, lines * sizeof(int))) return false;
    auto length = [&](int i) { return lengths[i] < 0 ? -lengths[i] : lengths[i]; };
    int total = 1;
    for (int i = 0; i < lines; ++i) total += length(i) + 1;
    if (total > 4096 || !Readable(string, total - 1)) return false;
    Font font{};
    if (!FontOf(object, font)) return false;
    const char* line = string;
    for (int i = 0; i + 1 < lines; ++i) {
        line += length(i);
        if (*line == '\n' || *line == ' ') ++line;
    }
    int end = length(lines - 1);
    while (end > 0 && line[end - 1] == ' ') --end;
    float width = 0.0f;
    for (int i = 0; i < end && line[i]; ++i) width += GlyphWidth(font, static_cast<unsigned char>(line[i]));
    out.width = static_cast<int>(width + 0.5f);
    out.lines = lines;
    out.scale = At<float>(object, kObjScale);
    out.lineHeight = font.lineHeight;
    return out.width > 0;
}

// ---------------------------------------------------------------- dialogue A

// An A at the end of the highlighted reply's text, shown only while replies can be picked
// (issue #21; K1ControllerLayout.cpp's reasoning, and its placement, measured in play at
// 3440x1440). The conversation panel is CSWGuiDialogCinematic (0x1005A6C88), which loads
// dialog.gui; its replies are the CSWGuiListBox at +0x20C0, whose rows are CSWGuiLabels in
// [+0x348], [+0x350] of them, the one it selects at +0x37A. CSWGuiDialog::HandleInputEvent
// (0x100243DDC): A skips the line while bit 0 of +0x2618 is set, and Up and Down move the
// highlighted reply at +0x80, capped at +0x84 - 1.
const std::uintptr_t kDialogVtable = 0x1005a6c88UL;
const std::size_t kDialogReplies = 0x20c0, kDialogFlags = 0x2618, kDialogHighlight = 0x80;
const std::size_t kListRows = 0x348, kListRowCount = 0x350;
const int kDialogMaxRows = 64;

struct DialogBadge { void* panel; void* label; char family; bool shown; int loggedCount; };
DialogBadge g_dialogBadges[4] = {};
unsigned g_dialogGeometryLogs = 0;

void LogDialogGeometry(void* panel, char* list, int count, int highlight, const int* placed, const ReplyLine& last) {
    if (g_dialogGeometryLogs >= 24) return;
    ++g_dialogGeometryLogs;
    const int* p = reinterpret_cast<const int*>(static_cast<char*>(panel) + kCtlExtent);
    const int* l = reinterpret_cast<const int*>(list + kCtlExtent);
    Log("layout: dialogue geometry panel=(%d,%d,%d,%d) list=(%d,%d,%d,%d) rows=%d highlight=%d placed=(%d,%d,%d,%d) "
        "lineWidth=%d lines=%d lineHeight=%d textScale=%.4f",
        p[0], p[1], p[2], p[3], l[0], l[1], l[2], l[3], count, highlight, placed[0], placed[1], placed[2], placed[3],
        last.width, last.lines, last.lineHeight, static_cast<double>(last.scale));
}

void UpdateDialogBadges() {
    const bool pad = device::PadInUse();
    const char family = prompts::FamilyLetter();
    for (DialogBadge& b : g_dialogBadges) {
        if (!b.panel) continue;
        if (!Readable(b.panel, kDialogFlags + 4) || !Readable(b.label, kLabelSize)) { b = {}; continue; }
        char* list = static_cast<char*>(b.panel) + kDialogReplies;
        const bool linePlaying = (At<std::uint8_t>(b.panel, kDialogFlags) & 1u) != 0;
        const int count = At<int>(list, kListRowCount);
        void** rows = At<void**>(list, kListRows);
        const int highlight = At<int>(b.panel, kDialogHighlight);
        const bool choosing = pad && !linePlaying && count > 0 && count <= kDialogMaxRows && rows &&
                              Readable(rows, count * sizeof(void*)) && highlight >= 0 && highlight < count &&
                              Readable(rows[highlight], kLabelSize);
        if (!choosing) {
            if (b.shown) { ShowControl(b.label, false); b.shown = false; }
            if (count <= 0) b.loggedCount = 0;
            continue;
        }
        // One text line: the shortest row.
        int line = 0;
        for (int i = 0; i < count; ++i) {
            if (!Readable(rows[i], 0x18)) continue;
            const int h = At<int>(rows[i], kCtlExtent + 12);
            if (h > 0 && (line == 0 || h < line)) line = h;
        }
        const int* listRect = reinterpret_cast<const int*>(list + kCtlExtent);
        const int* r = reinterpret_cast<const int*>(static_cast<char*>(rows[highlight]) + kCtlExtent);
        if (line <= 0) line = r[3];
        const int size = line + line / 4;
        const int scrollbar = listRect[2] > r[2] ? listRect[2] - r[2] : 0;
        const int textStart = listRect[0] + r[0] + scrollbar;
        const int* panelRect = reinterpret_cast<const int*>(static_cast<char*>(b.panel) + kCtlExtent);
        ReplyLine last{};
        const bool measured = LastLine(static_cast<char*>(rows[highlight]) + kLabelText, last);
        int left = textStart + last.width + size / 2;
        if (left + size > panelRect[2]) left = panelRect[2] - size;
        if (left < 0) left = 0;
        const int lines = measured ? last.lines : 1;
        const int lineHeight = measured && last.lineHeight > 0 ? last.lineHeight : line;
        const int block = lines * lineHeight;
        const int lastLineTop = r[1] + (r[3] > block ? (r[3] - block) / 2 : 0) + (lines - 1) * lineHeight;
        const int centre = lastLineTop + lineHeight * 5 / 8;
        int top = listRect[1] + centre - size / 2;
        if (top + size > panelRect[3]) top = panelRect[3] - size;
        if (top < 0) top = 0;
        const bool inList = centre >= 0 && centre <= listRect[3];
        const int rect[4] = {left, top, size, size};
        if (b.loggedCount != count) {
            LogDialogGeometry(b.panel, list, count, highlight, rect, last);
            b.loggedCount = count;
        }
        if (!inList || !measured) {
            if (b.shown) { ShowControl(b.label, false); b.shown = false; }
            continue;
        }
        SetExtent(b.label, rect);
        if (family != b.family) {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%ccnfa", family);
            SetFill(b.label, resref);
            b.family = family;
        }
        if (!b.shown) { ShowControl(b.label, true); b.shown = true; }
    }
}

// ---------------------------------------------------------------- status summary

// The box listing what just changed ("Journal Entry Added", "Credits Lost: 100"): its layout at
// the font's size is kmrp-layout/status_summary.cpp's since 2026-10-02, so it is made without
// controller support too; here the pad's A beside OK. CSWGuiStatusSummary is 0x1005AE9A0.
const std::uintptr_t kStatusSummaryVtable = 0x1005ae9a0UL;

struct SummaryBadge { void* panel; void* label; char family; bool shown; };
SummaryBadge g_summaryBadges[4] = {};
unsigned g_summaryLogs = 0;

// statussummary.gui is the game's own and has no control for a badge, so the label is made from
// one it does have: loaded by tag without being stored (InitControl's last argument 0), then put
// in the array's first empty slot.
void* BindExtraLabel(void* panel, const char* like) {
    void* control = ::operator new(kLabelSize, std::nothrow);
    if (!control) return nullptr;
    std::memset(control, 0, kLabelSize);
    Fn<CtorFn>(kLabelCtor)(control);
    ++g_controlsCreated;
    At<int>(control, kCtlId) = -1;   // set by the load only if `like` exists
    void* name[2] = {nullptr, nullptr};
    Fn<StringFn>(kStringCtor)(name, like);
    Fn<InitControlFn>(kInitControl)(panel, control, name, 0);
    Fn<StringFreeFn>(kStringDtor)(name);
    void** const array = At<void**>(panel, kPanelControls);
    const int count = At<int>(panel, kPanelControlCount);
    int slot = -1;
    if (At<int>(control, kCtlId) >= 0 && LooksLikePointer(array) && count > 0)
        for (int i = 0; i < count; ++i) if (!array[i]) { slot = i; break; }
    if (slot < 0) { DestroyControl(control); Note("the status summary's A found no slot"); return nullptr; }
    At<int>(control, kCtlId) = slot;
    array[slot] = control;
    return control;
}

bool UpdateSummaryBadge(void* panel, const int* ok) {
    for (SummaryBadge& b : g_summaryBadges) {
        if (b.panel != panel) continue;
        if (!device::PadInUse()) {
            if (b.shown) { ShowControl(b.label, false); b.shown = false; }
            return false;
        }
        const int size = ok[3];
        const int rect[4] = {ok[0] - size - size / 4, ok[1], size, size};
        SetExtentIfChanged(b.label, rect);
        const char family = prompts::FamilyLetter();
        if (family != b.family) {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%ccnfa", family);
            SetFill(b.label, resref);
            b.family = family;
        }
        if (!b.shown) { ShowControl(b.label, true); b.shown = true; }
        return true;
    }
    return false;
}

// The pad's A beside the status summary's OK, wherever that button is: the game's own place, or
// the one KMRP's patch gives it when it lays the summary out at the font's size (its own frame
// hook, kmrp-layout/status_summary.cpp; until 2026-10-07 this module called that layout itself).
void UpdateStatusSummary(void* manager) {
    void* const panel = summary::Find(manager);
    if (!panel) return;
    const int* const ok = &At<int>(static_cast<char*>(panel) + summary::kSummaryOk, kCtlExtent);
    const bool badged = UpdateSummaryBadge(panel, ok);
    if (g_summaryLogs < 8) {
        ++g_summaryLogs;
        Log("layout: status summary ok=(%d,%d,%d,%d) badge=%d", ok[0], ok[1], ok[2], ok[3], badged ? 1 : 0);
    }
}

// Pad A, Return or Space held (ControllerConfirmHeldK1).
bool ConfirmHeld() {
    return (g_padButtons & kPadA) != 0 || CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, 36) ||
           CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, 49);
}

// ---------------------------------------------------------------- remapping

// The screen is where the controller is remapped (items 60, 79, 80 of the 1.5-to-1.6 handoff; the
// reasoning, K1ControllerLayout.cpp and docs/controller-layout.md, "The screen, state by state"
// and "The table"). It opens on the drawing, whose rows are buttons; Remap swaps the drawing for
// a table, whose rows are actions, with the five controls that stay under a line. Giving an action
// a button takes that button from the action that had it (Mapping::Assign), and a layout is saved
// only when every action has one. The pad: the D-pad moves between the table's rows, A asks for a
// row's new button, Y puts back the default, X saves, B leaves, asking first when something is not
// saved. While waiting for a button the screen reads the pad itself (remap::Physical): menus send
// no event for LB or a stick's click, and every one of them may be chosen. Back cancels there,
// because it can never be chosen.
//
// Nothing here is in the layout file: every control is made from one of the file's own as the
// screen opens (BindAppend), and placed from the file's rows, so it follows the file at every
// resolution. The art is carried (item 101): the Mac draws no picture at run time, so a fill is
// the bare name, kmr?rm<code>, kmrrmask, kmrrmlock, kmrrmdot and the drawing's kmr?lyt<row>.
//
// On the Mac: a label's text parameters are +0x130 and a button's +0x1D8 (CSWGuiLabel::Load and
// CSWGuiButton::Load's CSWGuiText at +0x110 and +0x1B8; Windows +0xE8, +0x16C), the colour at
// +0x28 within them; a button's normal border parameters +0xC0 (Windows +0x80), the corner, edge
// and fill names at +0x1D, +0x2D, +0x3D within them, the alpha at +0x0C and the colour at +0x10
// (CSWGuiBorder::Load and Draw). CSWGuiPanel::AddControl is 0x10049E5E2 (Windows 0x0040B9A0): a
// control not yet in the array gets the panel as its parent (+0x50) and goes at the array's end,
// through its Add (0x100215440), so its slot is the end and not the ID in the file. Escape needs no slot of its own, as
// Windows' panel B has: CSWGuiManager's input (0x10049F096) turns it into 0x28 for the panel in
// front, which is ScreenInput, and CSWGuiPanel::OnBButtonPressed only calls HandleInputEvent.
const int kRemapRows = KmrpRemap::ButtonCount;
const char* const kActionNames[kRemapRows] = {
    "Interact", "Disengage", "Add to queue", "Undo or flourish", "Pause",
    "Switch ally", "Previous target", "Next target", "Flourish", "Free look"};
// What stays with each button: after its action, or before it on the sticks.
const char* const kFixedAfter[kRemapRows] = {
    "/ Select", "/ Back", "/ Menu action", "/ Menu action", "", "/ Menu action", "/ Prev tab", "/ Next tab", "", ""};
const char* const kFixedBefore[kRemapRows] = {
    "", "", "", "", "", "", "", "", "Move / Click:", "Camera / Click:"};
const int kRowBack = 2, kRowDpad = 4, kRowStart = 7;      // LAYOUT's fixed rows
// The table's rows that stay: a name, and the drawing's own picture of the control.
const int kStayRows = 5;
struct Stay { const char* name; int row; };
const Stay kStay[kStayRows] = {
    {"Move", 3}, {"Camera", 12}, {"Action bar", kRowDpad}, {"Menus", kRowStart}, {"Solo mode", kRowBack}};
const float kGrey[3] = {150 / 255.0f, 150 / 255.0f, 155 / 255.0f};
const float kYellow[3] = {236 / 255.0f, 226 / 255.0f, 38 / 255.0f};
const float kOrange[3] = {245 / 255.0f, 140 / 255.0f, 30 / 255.0f};
const char kAsk[] = "kmrrmask", kLock[] = "kmrrmlock", kDot[] = "kmrrmdot", kBlack[] = "blackfill";

const std::uintptr_t kAddControl = 0x10049e5e2UL;          // CSWGuiPanel::AddControl
const std::uintptr_t kSetCornerImage = 0x1004a1656UL, kSetEdgeImage = 0x1004a170cUL;
const std::uintptr_t kSetText = 0x1004a3714UL, kSetTextColour = 0x1004a380eUL;
const std::size_t kLabelTextParams = 0x130, kButtonTextParams = 0x1d8, kButtonText = 0x1b8;
const std::size_t kTextColour = 0x28;
const std::size_t kButtonBorder = 0xc0, kBorderAlpha = 0x0c, kBorderColour = 0x10, kBorderFill = 0x3d;
const std::size_t kCtlEventValue = 0x70;   // what CSWGuiControl::HandleInputEvent was last given
const std::uint8_t kCtlSelectable = 0x08;
const int kEventX = 0x29, kEventY = 0x2a;
const std::uint16_t kPadStartBack = 0x0030;

using AddControlFn = void (*)(void* panel, void* control);
using ImageFn = void (*)(void* params, const void* resref, int force);
using SetTextFn = void (*)(void* params, void* string);
using SetColourFn = void (*)(void* params, const float* rgb);

// View: the layout shown; Default (Y), Remap (X) or Back (B). Browse: remapping, a row's A asks for
// its button; Default (Y), Save (X) or Close (B). Listen: a button awaited. Unsaved: Close with
// changes not saved. Default: the view's Default asking before it replaces the saved layout.
enum class Mode { View, Browse, Listen, Unsaved, Default };
struct Remap {
    bool built = false;
    void* frame[kRemapRows] = {};
    void* fixed[kRemapRows] = {};
    void* dot[kRemapRows] = {};
    void* lockMove = nullptr; void* lockCamera = nullptr; void* lockDpad = nullptr;
    void* lockBack = nullptr; void* lockStart = nullptr;
    void* change = nullptr; void* changeGlyph = nullptr;
    void* defaults = nullptr; void* defaultsGlyph = nullptr;
    void* save = nullptr; void* saveGlyph = nullptr;
    void* backButton = nullptr;      // the file's BTN_BACK, kept off the pad's focus while open
    void* listenBox = nullptr; void* listenTitle = nullptr; void* listenLine = nullptr;
    void* listenGlyph = nullptr; void* listenCancel = nullptr;
    void* dim = nullptr; void* unsavedBox = nullptr; void* unsavedTitle = nullptr;
    void* unsavedLine1 = nullptr; void* unsavedLine2 = nullptr;
    void* discard = nullptr; void* discardGlyph = nullptr; void* cancel = nullptr; void* cancelGlyph = nullptr;
    void* head[2] = {}; void* line[2] = {};
    void* actionText[kRemapRows] = {}; void* actionGlyph[kRemapRows] = {};
    void* stayText[kStayRows] = {}; void* stayGlyph[kStayRows] = {};
    float cyan[3] = {};              // the captions' own colour, as the file gives it
    float saveBorder[3] = {};        // Save's and Default's border colour, while they can be pressed
    int help[4] = {}, back[4] = {}, backGlyph[4] = {};   // the file's, before anything moved
    int text[kRows][4] = {};         // each row's caption box, as the file has it
} g_rm;
KmrpRemap::Editor g_editor;
Mode g_mode = Mode::View;
int g_listenRow = -1;
int g_browseRow = 0;             // the table row the focus was last on, Interact's at first
std::uint16_t g_listenSeen = 0;
bool g_settle = false;           // after a choice: every event ignored until the pad's buttons are all up
char g_remapFamily = 0;
void* g_remapFocus = nullptr;
bool g_remapPad = false;
bool g_remapPadHere = false;     // whether a pad answered when the screen was last laid out
unsigned g_frameNumber = 0, g_backFrame = ~0u;

// Whether a pad answers (KmrpPadPresentK1): Remap opens only while one does.
bool PadPresent() { return PadFamily() >= 0; }

void OwnControl(void* control) { if (control && g_ownedCount < kOwnedSlots) g_owned[g_ownedCount++] = control; }

// A control made from one of the file's, by its tag, and added after the others: the file's array
// has no free slots.
void* BindAppend(void* panel, const char* like, bool button) {
    void* control = ::operator new(button ? kButtonSize : kLabelSize, std::nothrow);
    if (!control) return nullptr;
    std::memset(control, 0, button ? kButtonSize : kLabelSize);
    Fn<CtorFn>(button ? kButtonCtor : kLabelCtor)(control);
    ++g_controlsCreated;
    At<int>(control, kCtlId) = -1;   // set by the load only if `like` exists
    void* name[2] = {nullptr, nullptr};
    Fn<StringFn>(kStringCtor)(name, like);
    Fn<InitControlFn>(kInitControl)(panel, control, name, 0);
    Fn<StringFreeFn>(kStringDtor)(name);
    const int count = At<int>(panel, kPanelControlCount);
    if (At<int>(control, kCtlId) < 0 || count < 0 || count >= 512) {
        DestroyControl(control);
        Note("a control's tag is not in its .gui");
        return nullptr;
    }
    At<int>(control, kCtlId) = count;
    Fn<AddControlFn>(kAddControl)(panel, control);
    void** const array = At<void**>(panel, kPanelControls);
    if (At<int>(panel, kPanelControlCount) != count + 1 || !LooksLikePointer(array) || array[count] != control) {
        DestroyControl(control);
        Note("a control could not be added");
        return nullptr;
    }
    OwnControl(control);
    return control;
}

void SetControlText(void* control, const char* text, bool button = false) {
    void* string[2] = {nullptr, nullptr};
    Fn<StringFn>(kStringCtor)(string, text);
    Fn<SetTextFn>(kSetText)(static_cast<char*>(control) + (button ? kButtonTextParams : kLabelTextParams), string);
    Fn<StringFreeFn>(kStringDtor)(string);
}
// The colour of a label's text, or of a button's, passed on to its text.
void SetColour(void* control, const float* rgb, bool button = false) {
    char* const params = static_cast<char*>(control) + (button ? kButtonTextParams : kLabelTextParams);
    const float* now = reinterpret_cast<const float*>(params + kTextColour);
    if (now[0] == rgb[0] && now[1] == rgb[1] && now[2] == rgb[2]) return;
    Fn<SetColourFn>(kSetTextColour)(params, rgb);
}
// A fill by name, unless it already shows that picture.
void SetFillParams(void* params, const char* resref) {
    char name[32] = {};
    std::snprintf(name, sizeof name, "%s", resref);
    if (!strncasecmp(static_cast<const char*>(params) + kBorderFill, name, 16)) return;
    Fn<SetFillImageFn>(kSetFillImage)(params, name, 1);
}
void LabelFill(void* label, const char* resref) { SetFillParams(static_cast<char*>(label) + kLabelFillParams, resref); }
float& FillAlpha(void* label) { return At<float>(label, kLabelFillParams + kBorderAlpha); }
// A border with no picture; an empty name loads nothing.
void ClearBorder(void* params) {
    const char none[16] = {};
    Fn<ImageFn>(kSetCornerImage)(params, none, 1);
    Fn<ImageFn>(kSetEdgeImage)(params, none, 1);
    Fn<ImageFn>(kSetFillImage)(params, none, 1);
}
void Selectable(void* control, bool on) {
    std::uint8_t& flags = At<std::uint8_t>(control, kCtlFlags);
    flags = on ? (flags | kCtlSelectable) : (flags & ~kCtlSelectable);
}
int* RectOf(void* control) { return &At<int>(control, kCtlExtent); }
void Place(void* control, int left, int top, int width, int height) {
    const int r[4] = {left, top, width > 1 ? width : 1, height > 1 ? height : 1};
    text::SetExtentIfChanged(control, r);
}
// The scale KMRP's text fit is asked to draw a string at (kmrp-layout/text_fit.cpp,
// KmrpTextRequestedScale, found through KMRP's module as overlays.cpp finds it: a patch's module is
// loaded local, audit MAC-5): the player's text size. The string's own scale is that request only
// between a wrap and the next draw, and the fit's result after it. Without KMRP, the string's own.
using RequestedScaleFn = float (*)(void* object);
RequestedScaleFn RequestedScale() {
    static RequestedScaleFn requested = nullptr;
    static bool looked = false;
    if (looked) return requested;
    looked = true;
    Dl_info self;
    if (!dladdr(reinterpret_cast<const void*>(&RequestedScale), &self) || !self.dli_fname) return nullptr;
    std::string path(self.dli_fname);
    path = path.substr(0, path.rfind('/') + 1) + "kmrp.dylib";
    if (void* const module = dlopen(path.c_str(), RTLD_NOLOAD | RTLD_LAZY)) {
        requested = reinterpret_cast<RequestedScaleFn>(dlsym(module, "KmrpTextRequestedScale"));
        dlclose(module);
    }
    return requested;
}

// A text as it is asked to be drawn, at the player's text size: its one-line width and one line's
// height, in pixels. The font's own measure is the text at scale 1, which at 100% text is about
// half what is drawn (the screen broke there at 3024x1964, 2026-11-03: captions past both edges,
// the top two run together, the footer's glyphs over their captions).
struct Measure { int width, line; };
Measure MeasureText(void* label) {
    int line = 0;
    const int width = LabelTextWidth(label, line);
    char* const object = At<char*>(static_cast<char*>(label) + kLabelText, kTextObject);
    float scale = 1.0f;
    if (text::Readable(object, kObjScale + 4)) {
        const RequestedScaleFn requested = RequestedScale();
        scale = requested ? requested(object) : At<float>(object, kObjScale);
        if (!(scale > 0.01f && scale < 100.0f)) scale = 1.0f;
    }
    return {static_cast<int>(width * scale + 0.5f), static_cast<int>(line * scale + 0.5f)};
}
int TextWidth(void* label) { return MeasureText(label).width; }
// A button's text is the same object as a label's, at its own place in the button.
void* ButtonAsLabel(void* button) { return static_cast<char*>(button) + kButtonText - kLabelText; }
int ButtonTextWidth(void* button) { return MeasureText(ButtonAsLabel(button)).width; }

// A caption in a box of its own: as wide as `width`, one line of the text tall, centred on the
// band `top`..`top + height`. Where the room is narrower than the text, KMRP's text fit draws it
// smaller to the box (a bounded text, its default), which one line's height keeps from wrapping.
void PlaceCaption(void* label, int left, int top, int width, int height) {
    const int line = std::max(1, MeasureText(label).line) + 2;
    Place(label, left, top + (height - line) / 2, width, line);
}
// The text inside a button, its own box clear of the glyph on both sides, so a caption centred in it
// never runs under the glyph (CSWGuiText::SetExtent, 0x1004A3D4C; the button's SetExtent puts the
// text back over the whole button, so this follows every Place).
const std::uintptr_t kTextSetExtent = 0x1004a3d4cUL;
void InsetButtonText(void* button, int inset) {
    const int* r = RectOf(button);
    const int line = std::max(1, MeasureText(ButtonAsLabel(button)).line) + 2;
    const int box[4] = {r[0] + inset, r[1] + (r[3] - std::min(r[3], line)) / 2, std::max(1, r[2] - 2 * inset),
                        std::min(r[3], line)};
    int* const now = &At<int>(static_cast<char*>(button) + kButtonText, 0x08);
    if (now[0] == box[0] && now[1] == box[1] && now[2] == box[2] && now[3] == box[3]) return;
    reinterpret_cast<void (*)(void*, const int*)>(kTextSetExtent)(static_cast<char*>(button) + kButtonText, box);
}
void* RowGlyph(int row) { return g_owned[kFixed + row]; }
void* RowText(int row) { return g_owned[kFixed + kRows + row]; }
void* Deco(int i) { return g_owned[kFixed + 2 * kRows + i]; }
// Which side of the drawing a row's caption is on: LAYOUT's L rows read towards the glyph.
bool LeftSide(int row) { return row <= 4; }
// A control's handlers hear its press and its release alike (CSWGuiControl::HandleInputEvent);
// only the press acts.
bool Pressed(void* control) { return At<int>(control, kCtlEventValue) != 0; }

void RowPressed(void*, void*);
void DefaultsPressed(void*, void*);
void SavePressed(void*, void*);
void DiscardPressed(void*, void*);
void CancelPressed(void*, void*);
void ListenCancelPressed(void*, void*);
void ChangePressed(void*, void*);

void AddPress(void* control, void* panel, void (*handler)(void*, void*)) {
    Fn<AddEventFn>(kAddEvent)(control, kEventA, panel, reinterpret_cast<void*>(handler), 0);
}

// Whether Default would change anything: the saved layout in the view (and in its box), the
// layout being changed while remapping.
bool CanDefault() {
    const bool view = g_mode == Mode::View || g_mode == Mode::Default;
    return !(view ? remap::Saved() : g_editor.mapping).IsDefault();
}

// Made as the screen opens, before the file is let go (StopLoadFromLayout).
bool BuildRemap(void* p) {
    g_editor = KmrpRemap::Editor(remap::Saved());
    g_rm = Remap{};
    std::memcpy(g_rm.cyan, static_cast<char*>(RowText(0)) + kLabelTextParams + kTextColour, sizeof g_rm.cyan);
    void* const help = g_owned[9];
    void* const backButton = g_owned[1];
    g_rm.backButton = backButton;
    std::memcpy(g_rm.help, RectOf(help), sizeof g_rm.help);
    std::memcpy(g_rm.back, RectOf(backButton), sizeof g_rm.back);
    std::memcpy(g_rm.backGlyph, RectOf(g_owned[kBackGlyph]), sizeof g_rm.backGlyph);
    for (int row = 0; row < kRows; ++row) std::memcpy(g_rm.text[row], RectOf(RowText(row)), sizeof g_rm.text[row]);
    for (int b = 0; b < kRemapRows; ++b) {
        // The frame: a button with no picture of its own, whose focus draws the game's.
        void* frame = BindAppend(p, "BTN_BACK", true);
        if (!frame) return false;
        ClearBorder(static_cast<char*>(frame) + kButtonBorder);
        SetControlText(frame, "", true);
        AddPress(frame, p, &RowPressed);
        g_rm.frame[b] = frame;
        g_rm.fixed[b] = BindAppend(p, "TEXT_05", false);
        g_rm.dot[b] = BindAppend(p, "GLYPH_BACK", false);
        if (!g_rm.fixed[b] || !g_rm.dot[b]) return false;
        LabelFill(g_rm.dot[b], kDot);
        SetColour(g_rm.fixed[b], kGrey);
    }
    void** locks[] = {&g_rm.lockMove, &g_rm.lockCamera, &g_rm.lockDpad, &g_rm.lockBack, &g_rm.lockStart};
    for (void** lock : locks) {
        *lock = BindAppend(p, "GLYPH_BACK", false);
        if (!*lock) return false;
        LabelFill(*lock, kLock);
    }
    g_rm.change = BindAppend(p, "BTN_BACK", true);
    g_rm.changeGlyph = BindAppend(p, "GLYPH_BACK", false);
    g_rm.defaults = BindAppend(p, "BTN_BACK", true);
    g_rm.defaultsGlyph = BindAppend(p, "GLYPH_BACK", false);
    g_rm.save = BindAppend(p, "BTN_BACK", true);
    g_rm.saveGlyph = BindAppend(p, "GLYPH_BACK", false);
    if (!g_rm.change || !g_rm.changeGlyph || !g_rm.defaults || !g_rm.defaultsGlyph || !g_rm.save || !g_rm.saveGlyph)
        return false;
    SetControlText(g_rm.change, "Change", true);
    SetControlText(g_rm.defaults, "Default", true);
    SetControlText(g_rm.save, "Save", true);
    std::memcpy(g_rm.saveBorder, static_cast<char*>(g_rm.save) + kButtonBorder + kBorderColour, sizeof g_rm.saveBorder);
    AddPress(g_rm.defaults, p, &DefaultsPressed);
    AddPress(g_rm.save, p, &SavePressed);
    AddPress(g_rm.change, p, &ChangePressed);
    // The table, made before the prompts so that their dimmed box covers it. Names from TEXT_05,
    // a right-hand caption, so they read from the left; pictures from GLYPH_BACK; the lines from
    // DECO_04, the hairline under the heading.
    for (int i = 0; i < 2; ++i) {
        g_rm.head[i] = BindAppend(p, "TEXT_05", false);
        g_rm.line[i] = BindAppend(p, "DECO_04", false);
        if (!g_rm.head[i] || !g_rm.line[i]) return false;
        SetColour(g_rm.head[i], kGrey);
    }
    SetControlText(g_rm.head[0], "Action");
    SetControlText(g_rm.head[1], "Button");
    for (int a = 0; a < kRemapRows; ++a) {
        g_rm.actionText[a] = BindAppend(p, "TEXT_05", false);
        g_rm.actionGlyph[a] = BindAppend(p, "GLYPH_BACK", false);
        if (!g_rm.actionText[a] || !g_rm.actionGlyph[a]) return false;
        SetControlText(g_rm.actionText[a], kActionNames[a]);
    }
    for (int s = 0; s < kStayRows; ++s) {
        g_rm.stayText[s] = BindAppend(p, "TEXT_05", false);
        g_rm.stayGlyph[s] = BindAppend(p, "GLYPH_BACK", false);
        if (!g_rm.stayText[s] || !g_rm.stayGlyph[s]) return false;
        SetControlText(g_rm.stayText[s], kStay[s].name);
    }
    // The prompt while a button is awaited, in the footer's place.
    g_rm.listenBox = BindAppend(p, "BTN_BACK", true);
    g_rm.listenTitle = BindAppend(p, "LBL_TITLE", false);
    g_rm.listenLine = BindAppend(p, "LBL_HELP", false);
    g_rm.listenGlyph = BindAppend(p, "GLYPH_BACK", false);
    g_rm.listenCancel = BindAppend(p, "BTN_BACK", true);
    // Leaving with something not saved: the screen dimmed, a box over it.
    g_rm.dim = BindAppend(p, "LBL_DIAGRAM", false);
    g_rm.unsavedBox = BindAppend(p, "BTN_BACK", true);
    g_rm.unsavedTitle = BindAppend(p, "LBL_TITLE", false);
    g_rm.unsavedLine1 = BindAppend(p, "LBL_HELP", false);
    g_rm.unsavedLine2 = BindAppend(p, "LBL_HELP", false);
    g_rm.discard = BindAppend(p, "BTN_BACK", true);
    g_rm.discardGlyph = BindAppend(p, "GLYPH_BACK", false);
    g_rm.cancel = BindAppend(p, "BTN_BACK", true);
    g_rm.cancelGlyph = BindAppend(p, "GLYPH_BACK", false);
    void* const modal[] = {g_rm.listenBox, g_rm.listenTitle, g_rm.listenLine, g_rm.listenGlyph, g_rm.listenCancel,
                           g_rm.dim, g_rm.unsavedBox, g_rm.unsavedTitle, g_rm.unsavedLine1, g_rm.unsavedLine2,
                           g_rm.discard, g_rm.discardGlyph, g_rm.cancel, g_rm.cancelGlyph};
    for (void* c : modal) if (!c) return false;
    for (void* box : {g_rm.listenBox, g_rm.unsavedBox}) {
        SetControlText(box, "", true);
        SetFillParams(static_cast<char*>(box) + kButtonBorder, kBlack);
        Selectable(box, false);
    }
    SetControlText(g_rm.listenLine, "If another action has that button, it is left without one");
    SetControlText(g_rm.listenCancel, "Cancel", true);
    AddPress(g_rm.listenCancel, p, &ListenCancelPressed);
    LabelFill(g_rm.dim, kBlack);
    FillAlpha(g_rm.dim) = 0.7f;
    // The box's title, lines and first button are set as it is laid out: it asks one of two things.
    SetControlText(g_rm.cancel, "Cancel", true);
    AddPress(g_rm.discard, p, &DiscardPressed);
    AddPress(g_rm.cancel, p, &CancelPressed);
    // Pad buttons, not places for the pad's focus; the mouse still clicks them.
    for (void* c : {backButton, g_rm.change, g_rm.defaults, g_rm.save, g_rm.discard, g_rm.cancel, g_rm.listenCancel})
        PadFocusExclude(c, true);
    g_rm.built = true;
    return true;
}

// The drawing, in the view (and under its Default box): each button's row, its caption from the
// glyph outwards, its frame, dot and padlock, the fixed rows grey, and the two captions above the
// diagram apart.
void LayoutDrawing(void* focus, char family) {
    const int screenWidth = RectOf(g_current)[2];
    const int edge = RectOf(g_owned[kBackGlyph])[2] / 2;   // the captions' margin at the screen's edges
    for (int b = 0; b < kRemapRows; ++b) {
        const int row = KmrpRemap::LayoutRow[b];
        void* const glyph = RowGlyph(row);
        void* const action = RowText(row);
        void* const fixed = g_rm.fixed[b];
        const int* g = RectOf(glyph);
        const int* t = g_rm.text[row];
        const int shownAction = g_editor.ActionInRow(b);
        const bool waiting = g_editor.Waiting(b);
        SetControlText(action, shownAction >= 0 ? kActionNames[shownAction] : "");
        const char* fixedText = kFixedBefore[b][0] ? kFixedBefore[b] : kFixedAfter[b];
        SetControlText(fixed, fixedText);
        ShowControl(fixed, fixedText[0] != 0);
        if (waiting) {
            LabelFill(glyph, kAsk);
        } else {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%clyt%02d", family, row);
            LabelFill(glyph, resref);
        }
        const bool faded = g_mode == Mode::Listen && b != g_listenRow;
        float dim[3], dimGrey[3];
        for (int i = 0; i < 3; ++i) { dim[i] = g_rm.cyan[i] * 0.4f; dimGrey[i] = kGrey[i] * 0.5f; }
        const bool focused = g_mode != Mode::View && focus == g_rm.frame[b];
        SetColour(action, faded ? dim : waiting ? kOrange : focused ? kYellow : g_rm.cyan);
        SetColour(fixed, faded ? dimGrey : kGrey);
        FillAlpha(glyph) = faded ? 0.35f : 1.0f;
        // The pieces of the caption on one line, from the glyph outwards: a measured width each,
        // so an action of any length sits beside what stays.
        // Measured at the player's text size, and narrowed together to the room between the glyph
        // and the screen's edge, where KMRP's text fit then draws them smaller.
        const int gap = LeftSide(row) ? g[0] - (t[0] + t[2]) : t[0] - (g[0] + g[2]);
        int space = t[3] / 3;
        int aw = TextWidth(action) + 4, fw = fixedText[0] ? TextWidth(fixed) + 4 : 0;
        // What stands beyond the caption at the row's outer end comes out of its room: the frame's
        // pad, a changed button's dot and a stick's padlock (2026-11-03: "Move / Click: Flourish" was
        // cut at the left edge at 100% text, its padlock past it).
        const int pad = g[3] / 6;
        const bool changed = shownAction >= 0 && shownAction != b && !waiting;
        const int dotSize = g[3] * 3 / 10, lockSize = g[3] * 11 / 20;
        void* const lock = b == KmrpRemap::L3 ? g_rm.lockMove : b == KmrpRemap::R3 ? g_rm.lockCamera : nullptr;
        const int beyond = pad + (changed ? pad + dotSize : 0) + (lock ? pad + lockSize : 0);
        const int room = std::max(1, LeftSide(row) ? g[0] - gap - edge - beyond
                                                   : screenWidth - edge - beyond - (g[0] + g[2] + gap));
        if (aw + (fw ? fw + space : 0) > room) {
            const double fit = static_cast<double>(room) / (aw + (fw ? fw + space : 0));
            aw = std::max(1, static_cast<int>(aw * fit));
            fw = fw ? std::max(1, static_cast<int>(fw * fit)) : 0;
            space = static_cast<int>(space * fit);
        }
        const bool before = kFixedBefore[b][0] != 0;
        const int total = aw + (fw ? fw + space : 0);
        const int start = LeftSide(row) ? g[0] - gap - total : g[0] + g[2] + gap;
        void* first = before ? fixed : action;
        void* second = before ? action : fixed;
        const int w1 = before ? fw : aw, w2 = before ? aw : fw;
        PlaceCaption(first, start, t[1], w1, t[3]);
        if (w2) PlaceCaption(second, start + w1 + (w1 && w2 ? space : 0), t[1], w2, t[3]);
        // The frame round the glyph and the caption, a sixth of the glyph clear.
        const int left = std::min(g[0], start) - pad, right = std::max(g[0] + g[2], start + total) + pad;
        Place(g_rm.frame[b], left, g[1] - pad, right - left, g[3] + 2 * pad);
        // A changed button's dot, outside the frame at the row's outer end.
        Place(g_rm.dot[b], LeftSide(row) ? left - pad - dotSize : right + pad, g[1] + (g[3] - dotSize) / 2, dotSize, dotSize);
        ShowControl(g_rm.dot[b], changed);
        // A stick's movement is fixed: its padlock at the row's outer end, beyond the dot.
        if (lock) {
            const int past = changed ? dotSize + pad : 0;
            Place(lock, LeftSide(row) ? left - pad - past - lockSize : right + pad + past, g[1] + (g[3] - lockSize) / 2,
                  lockSize, lockSize);
        }
    }
    // The rows that stay: grey, and padlocked.
    for (int row : {kRowBack, kRowDpad, kRowStart}) SetColour(RowText(row), kGrey);
    {
        // The D-pad's caption is the file's; it reads towards its glyph, so it is placed as the
        // actions' are, ending a gap short of the glyph, narrowed to the room left of it; its
        // padlock beyond its first letter.
        const int* g = RectOf(RowGlyph(kRowDpad));
        const int* t = g_rm.text[kRowDpad];
        const int size = g[3] * 11 / 20, pad = g[3] / 6;
        const int gap = g[0] - (t[0] + t[2]);
        const int room = std::max(1, g[0] - gap - edge - pad - size);
        const int width = std::min(room, TextWidth(RowText(kRowDpad)) + 4);
        const int textLeft = g[0] - gap - width;
        PlaceCaption(RowText(kRowDpad), textLeft, t[1], width, t[3]);
        Place(g_rm.lockDpad, textLeft - pad - size, g[1] + (g[3] - size) / 2, size, size);
    }
    for (int row : {kRowBack, kRowStart}) {
        const int* g = RectOf(RowGlyph(row));
        const int size = g[3] * 9 / 20;
        Place(row == kRowBack ? g_rm.lockBack : g_rm.lockStart, g[0] + (g[2] - size) / 2, g[1] + g[3] + g[3] / 10, size, size);
    }
    // Back's and Start's captions, each centred over its glyph above the diagram, moved apart
    // where their words would meet, measured in the screen's own font (item 79; "Solo mode" ran
    // into "Last menu" at 3440x1440 on Windows, 2026-10-21). Both stay between LT's glyph and RT's
    // with a gap to each, and a gap between them; where the two do not fit there at the player's text
    // size, both are narrowed by the same factor and KMRP's text fit draws them smaller (at 100%
    // text "Close menu" ran into "Next target", 2026-11-03). Each box is the width of its caption,
    // centred where the caption is to stand.
    {
        void* const backText = RowText(kRowBack);
        void* const startText = RowText(kRowStart);
        const int* bt = g_rm.text[kRowBack];
        const int* st = g_rm.text[kRowStart];
        const int gap = bt[3] * 12 / 26;           // TOP_CAPTION_GAP in TOP_CAPTION_H
        const int* lt = RectOf(RowGlyph(KmrpRemap::LayoutRow[KmrpRemap::LT]));
        const int* rt = RectOf(RowGlyph(KmrpRemap::LayoutRow[KmrpRemap::RT]));
        const int lo = lt[0] + lt[2] + gap, hi = rt[0] - gap;
        int bw = TextWidth(backText) + 4, sw = TextWidth(startText) + 4;
        if (bw + gap + sw > hi - lo) {
            const double fit = static_cast<double>(std::max(2, hi - lo - gap)) / (bw + sw);
            bw = std::max(1, static_cast<int>(bw * fit));
            sw = std::max(1, static_cast<int>(sw * fit));
        }
        // Left edges: each over its glyph, then inside lo..hi, then apart, Start's moved first only
        // as far as RT's glyph allows and Back's the rest, towards LT's.
        int bl = bt[0] + bt[2] / 2 - bw / 2, sl = st[0] + st[2] / 2 - sw / 2;
        bl = std::max(lo, std::min(bl, hi - bw));
        sl = std::max(lo, std::min(sl, hi - sw));
        const int shortBy = bl + bw + gap - sl;
        if (shortBy > 0) {
            int moveStart = std::min(hi - (sl + sw), shortBy / 2);
            const int moveBack = std::min(bl - lo, shortBy - moveStart);
            moveStart = std::min(hi - (sl + sw), shortBy - moveBack);
            bl -= moveBack;
            sl += moveStart;
        }
        PlaceCaption(backText, bl, bt[1], bw, bt[3]);
        PlaceCaption(startText, sl, st[1], sw, st[3]);
    }
}

// The table, while remapping, in the drawing's place: between the heading's hairline and the help
// line, centred on the screen as the footer is. A row is as tall as a one-line caption box where
// there is room, less on short screens, since the heads, the ten actions, the five that stay and
// half a row between them must fit. The name column is as wide as the widest name, measured in
// the screen's own font.
void LayoutTable(void* focus, char family) {
    const int* headLine = RectOf(Deco(4));
    const int helpH = g_rm.help[3];
    const int boxH = g_rm.text[kRowBack][3];
    const int top = headLine[1] + headLine[3] + helpH / 2;
    const int bottom = RectOf(Deco(5))[1] - helpH - helpH / 4 - helpH / 2;
    const int rows2 = 2 * (1 + kRemapRows + kStayRows) + 1;     // in half rows
    const int rowH = std::max(1, std::min(boxH, (bottom - top) * 2 / rows2));
    const int pic = rowH * 4 / 5, dot = pic * 3 / 10, lock = pic * 11 / 20;
    const int pad = rowH / 2, colGap = rowH * 2;
    int nameW = TextWidth(g_rm.head[0]);
    for (void* t : g_rm.actionText) nameW = std::max(nameW, TextWidth(t));
    for (void* t : g_rm.stayText) nameW = std::max(nameW, TextWidth(t));
    nameW += 4;
    const int buttonW = std::max(TextWidth(g_rm.head[1]) + 4, pic + pad + std::max(dot, lock));
    const int width = pad + nameW + colGap + buttonW + pad;
    const int height = rowH * rows2 / 2;
    const int left = g_rm.back[0] + g_rm.back[2] / 2 - width / 2;
    const int tableTop = top + ((bottom - top) - height) / 2;
    const int nameX = left + pad, buttonX = nameX + nameW + colGap;
    const int lineH = std::max(1, headLine[3]);
    auto name = [&](void* c, int x, int w, int y) { Place(c, x, y + (rowH - boxH) / 2, w, boxH); };
    auto picture = [&](void* c, int y) { Place(c, buttonX, y + (rowH - pic) / 2, pic, pic); };
    name(g_rm.head[0], nameX, nameW, tableTop);
    name(g_rm.head[1], buttonX, buttonW, tableTop);
    Place(g_rm.line[0], left, tableTop + rowH - lineH / 2, width, lineH);
    // While a button is awaited every other row fades, as the drawing's rows did.
    float dim[3], dimGrey[3];
    for (int i = 0; i < 3; ++i) { dim[i] = g_rm.cyan[i] * 0.4f; dimGrey[i] = kGrey[i] * 0.5f; }
    const bool listening = g_mode == Mode::Listen;
    for (int a = 0; a < kRemapRows; ++a) {
        const int y = tableTop + rowH * (1 + a);
        const int button = g_editor.mapping.button[a];
        const bool none = button < 0 || button >= kRemapRows;
        const bool faded = listening && a != g_listenRow;
        Place(g_rm.frame[a], left, y, width, rowH);
        name(g_rm.actionText[a], nameX, nameW, y);
        SetColour(g_rm.actionText[a], faded ? dim : none ? kOrange : focus == g_rm.frame[a] ? kYellow : g_rm.cyan);
        if (none) {
            LabelFill(g_rm.actionGlyph[a], kAsk);
        } else {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%crm%s", family, KmrpRemap::GlyphCodes[button]);
            LabelFill(g_rm.actionGlyph[a], resref);
        }
        picture(g_rm.actionGlyph[a], y);
        FillAlpha(g_rm.actionGlyph[a]) = faded ? 0.35f : 1.0f;
        Place(g_rm.dot[a], buttonX + pic + pad, y + (rowH - dot) / 2, dot, dot);
        ShowControl(g_rm.dot[a], !none && button != a);
    }
    // The rows that stay, under a line half a row down: grey, each with its padlock.
    const int stayTop = tableTop + rowH * (1 + kRemapRows) + rowH / 2;
    Place(g_rm.line[1], left, stayTop - rowH / 4 - lineH / 2, width, lineH);
    void* const locks[kStayRows] = {g_rm.lockMove, g_rm.lockCamera, g_rm.lockDpad, g_rm.lockStart, g_rm.lockBack};
    for (int s = 0; s < kStayRows; ++s) {
        const int y = stayTop + rowH * s;
        name(g_rm.stayText[s], nameX, nameW, y);
        SetColour(g_rm.stayText[s], listening ? dimGrey : kGrey);
        char resref[32];
        std::snprintf(resref, sizeof resref, "kmr%clyt%02d", family, kStay[s].row);
        LabelFill(g_rm.stayGlyph[s], resref);
        picture(g_rm.stayGlyph[s], y);
        FillAlpha(g_rm.stayGlyph[s]) = listening ? 0.35f : 1.0f;
        Place(locks[s], buttonX + pic + pad, y + (rowH - lock) / 2, lock, lock);
    }
}

// Where everything goes, and what it says, for the layout being edited and the focus.
void LayoutRemap() {
    if (!g_rm.built || !g_current) return;
    void* const focus = At<void*>(g_current, kPanelActive);
    const char family = prompts::FamilyLetter();
    // The table while remapping (and under its Unsaved Changes box), the drawing in the view and
    // under its Default box. Each hides the other's controls.
    const bool table = g_mode == Mode::Browse || g_mode == Mode::Listen || g_mode == Mode::Unsaved;
    ShowControl(g_owned[8], !table);                 // LBL_DIAGRAM, the drawing and its lines
    for (int row = 0; row < kRows; ++row) {
        ShowControl(RowGlyph(row), !table);
        ShowControl(RowText(row), !table);
    }
    for (void* c : g_rm.head) ShowControl(c, table);
    for (void* c : g_rm.line) ShowControl(c, table);
    for (int a = 0; a < kRemapRows; ++a) {
        ShowControl(g_rm.actionText[a], table);
        ShowControl(g_rm.actionGlyph[a], table);
    }
    for (int s = 0; s < kStayRows; ++s) {
        ShowControl(g_rm.stayText[s], table);
        ShowControl(g_rm.stayGlyph[s], table);
    }
    if (table) {
        for (void* c : g_rm.fixed) ShowControl(c, false);
        LayoutTable(focus, family);
    } else {
        LayoutDrawing(focus, family);
    }
    // The footer: Default, Save (Remap in the view) and Back, each with its pad button, and (A)
    // Change first while remapping. The help line above the line.
    void* const help = g_owned[9];
    void* const line = Deco(5);
    const int* l = RectOf(line);
    const int helpH = g_rm.help[3];
    Place(help, g_rm.help[0], l[1] - helpH - helpH / 4, g_rm.help[2], helpH);
    const bool complete = g_editor.Complete();
    const bool padHere = PadPresent();
    if (!table && !padHere) {
        // Remap needs a pad: the view says so while none answers.
        SetControlText(help, "Connect a controller to remap its buttons.");
        SetColour(help, kOrange);
    } else if (complete) {
        SetControlText(help, table ? "A dot marks a changed button.   The grey rows stay as they are, and menus keep every button."
                                   : "A dot marks a changed button.   A lock stays as it is: moving, the camera, the D-pad, Start and Back.");
        SetColour(help, g_rm.cyan);
    } else {
        int missing = KmrpRemap::None;
        for (int a = 0; a < kRemapRows && missing < 0; ++a)
            if (g_editor.mapping.button[a] < 0) missing = a;
        char message[160];
        std::snprintf(message, sizeof message, "%s has no button.   Every action needs one before you can save.",
                      missing >= 0 ? kActionNames[missing] : "An action");
        SetControlText(help, message);
        SetColour(help, kOrange);
    }
    const int bh = g_rm.back[3];
    const int middle = g_rm.back[0] + g_rm.back[2] / 2;
    const int gx = g_rm.backGlyph[0] - g_rm.back[0], gy = g_rm.backGlyph[1] - g_rm.back[1], gs = g_rm.backGlyph[2];
    void* const backButton = g_owned[1];
    void* const backGlyph = g_owned[kBackGlyph];
    // Default's box is the view's: the footer under it keeps the view's buttons.
    const bool view = g_mode == Mode::View || g_mode == Mode::Default;
    SetControlText(g_rm.save, view ? "Remap" : "Save", true);
    SetControlText(backButton, view ? "Back" : "Close", true);
    // The footer's buttons, one size in both states: as wide as the longest label, measured at the
    // player's text size, centred clear of the glyph, and narrower only where four would not fit
    // across the screen; then the caption's own box keeps clear of the glyph and KMRP's text fit
    // draws it smaller. Each row centred where the file's Back was. (Windows caps them at the
    // file's Back, which a large text size outgrows: the glyphs sat on the captions' first letters.)
    int labelW = 0;
    for (void* b : {g_rm.change, g_rm.defaults, g_rm.save, backButton}) labelW = std::max(labelW, ButtonTextWidth(b));
    const int clear = gx + gs + gs / 2;               // the edge to the glyph's far side, and a half glyph more
    int fw = labelW > 0 ? labelW + 4 + 2 * clear : g_rm.back[2] * 4 / 5;
    int gap = fw / 4;
    const int room = RectOf(g_current)[2] - 2 * gs;
    if (4 * fw + 3 * gap > room) gap = std::max(gs / 2, (room - 4 * fw) / 3);
    if (4 * fw + 3 * gap > room) fw = std::max(2 * clear, (room - 3 * gap) / 4);
    const int span4 = 4 * fw + 3 * gap;
    const int count = view ? 3 : 4;
    const int first = middle - (count * fw + (count - 1) * gap) / 2;
    struct { void* button; void* glyph; const char* code; } footer[4] = {
        {g_rm.change, g_rm.changeGlyph, "a"}, {g_rm.defaults, g_rm.defaultsGlyph, "y"},
        {g_rm.save, g_rm.saveGlyph, "x"}, {backButton, backGlyph, nullptr}};
    for (int i = view ? 1 : 0, slot = 0; i < 4; ++i, ++slot) {
        const int x = first + slot * (fw + gap);
        Place(footer[i].button, x, g_rm.back[1], fw, bh);
        InsetButtonText(footer[i].button, clear);
        Place(footer[i].glyph, x + gx, g_rm.back[1] + gy, gs, gs);
        if (footer[i].code) {
            char resref[32];
            std::snprintf(resref, sizeof resref, "kmr%crm%s", family, footer[i].code);
            LabelFill(footer[i].glyph, resref);
        }
    }
    // Save while the layout cannot be saved, Remap while no pad answers, and Default while the
    // layout already is the default: grey, the glyph faint.
    {
        const bool can[2] = {view ? padHere : complete, CanDefault()};
        void* const button[2] = {g_rm.save, g_rm.defaults};
        void* const glyph[2] = {g_rm.saveGlyph, g_rm.defaultsGlyph};
        for (int i = 0; i < 2; ++i) {
            float* border = reinterpret_cast<float*>(static_cast<char*>(button[i]) + kButtonBorder + kBorderColour);
            std::memcpy(border, can[i] ? g_rm.saveBorder : kGrey, sizeof g_rm.saveBorder);
            FillAlpha(glyph[i]) = can[i] ? 1.0f : 0.35f;
            SetColour(button[i], can[i] ? g_rm.cyan : kGrey, true);
        }
    }
    // The prompt, in the help line's and the footer's place, as wide as the four buttons: what to
    // press, what happens to the button's action, and how to cancel, one under the other.
    {
        const int left = middle - span4 / 2, width = span4;
        const int titleH = RectOf(g_owned[0])[3];
        const int pad = helpH / 2;
        const int height = pad + titleH + helpH / 4 + helpH + pad + bh + pad;
        const int bottom = g_rm.back[1] + bh;
        const int top = bottom - height;
        Place(g_rm.listenBox, left, top, width, height);
        Place(g_rm.listenTitle, left, top + pad, width, titleH);
        char message[96];
        const int a = g_listenRow;   // the table's rows are actions
        std::snprintf(message, sizeof message, "Press the new button for %s",
                      a >= 0 && a < kRemapRows ? kActionNames[a] : "this action");
        SetControlText(g_rm.listenTitle, message);
        Place(g_rm.listenLine, left, top + pad + titleH + helpH / 4, width, helpH);
        char resref[32];
        std::snprintf(resref, sizeof resref, "kmr%clyt%02d", family, kRowBack);
        LabelFill(g_rm.listenGlyph, resref);
        const int by = top + height - pad - bh;
        Place(g_rm.listenCancel, middle - fw / 2, by, fw, bh);
        InsetButtonText(g_rm.listenCancel, clear);
        Place(g_rm.listenGlyph, middle - fw / 2 + gx, by + gy, gs, gs);
    }
    // Unsaved changes: the screen dimmed, a box in its middle, its two buttons Back's width.
    {
        const int bw = g_rm.back[2];
        const int* panel = RectOf(g_current);
        Place(g_rm.dim, 0, 0, panel[2], panel[3]);
        const int titleH = RectOf(g_owned[0])[3];
        const int width = 3 * bw + bw / 4, height = titleH * 2 + helpH * 3 + bh + bh / 2;
        const int left = panel[2] / 2 - width / 2, top = panel[3] / 2 - height / 2;
        Place(g_rm.unsavedBox, left, top, width, height);
        Place(g_rm.unsavedTitle, left, top + titleH / 2, width, titleH);
        Place(g_rm.unsavedLine1, left, top + titleH * 2, width, helpH);
        Place(g_rm.unsavedLine2, left, top + titleH * 2 + helpH + helpH / 4, width, helpH);
        const int by = top + height - bh - bh / 2;
        Place(g_rm.discard, panel[2] / 2 - bw / 4 - bw, by, bw, bh);
        Place(g_rm.cancel, panel[2] / 2 + bw / 4, by, bw, bh);
        InsetButtonText(g_rm.discard, clear);
        InsetButtonText(g_rm.cancel, clear);
        Place(g_rm.discardGlyph, panel[2] / 2 - bw / 4 - bw + gx, by + gy, gs, gs);
        Place(g_rm.cancelGlyph, panel[2] / 2 + bw / 4 + gx, by + gy, gs, gs);
        char resref[32];
        std::snprintf(resref, sizeof resref, "kmr%crma", family);
        LabelFill(g_rm.discardGlyph, resref);
        std::snprintf(resref, sizeof resref, "kmr%crmb", family);
        LabelFill(g_rm.cancelGlyph, resref);
        // The same box asks before the view's Default replaces the saved layout.
        const bool asking = g_mode == Mode::Default;
        SetControlText(g_rm.unsavedTitle, asking ? "Default Layout" : "Unsaved Changes");
        SetControlText(g_rm.unsavedLine1, asking ? "Every action goes back to its Xbox button."
                                                 : "You have not saved your new controller layout.");
        SetControlText(g_rm.unsavedLine2, asking ? "Replace your saved layout?" : "Discard your changes?");
        SetControlText(g_rm.discard, asking ? "Default" : "Discard", true);
    }
    // What shows in each state. The box is up for Unsaved and for Default.
    const bool browse = g_mode == Mode::Browse, listen = g_mode == Mode::Listen;
    const bool unsaved = g_mode == Mode::Unsaved || g_mode == Mode::Default;
    const bool pad = device::PadInUse();
    for (void* c : {help, g_rm.save, backButton, g_rm.defaults}) ShowControl(c, !listen);
    for (void* c : {g_rm.saveGlyph, backGlyph, g_rm.defaultsGlyph}) ShowControl(c, !listen && pad);
    ShowControl(g_rm.change, !listen && !view);
    ShowControl(g_rm.changeGlyph, !listen && !view && pad);
    ShowControl(g_rm.discardGlyph, unsaved && pad);
    ShowControl(g_rm.cancelGlyph, unsaved && pad);
    for (void* c : {g_rm.listenBox, g_rm.listenTitle, g_rm.listenLine, g_rm.listenCancel}) ShowControl(c, listen);
    ShowControl(g_rm.listenGlyph, listen && pad);
    for (void* c : {g_rm.dim, g_rm.unsavedBox, g_rm.unsavedTitle, g_rm.unsavedLine1, g_rm.unsavedLine2, g_rm.discard, g_rm.cancel})
        ShowControl(c, unsaved);
    // While a button is awaited the focus stays on its row; the rows are not places to go.
    for (int b = 0; b < kRemapRows; ++b) Selectable(g_rm.frame[b], browse);
    for (int b = 0; b < kRemapRows; ++b) if (focus == g_rm.frame[b]) g_browseRow = b;
    g_remapFamily = family;
    g_remapFocus = focus;
    g_remapPad = pad;
    g_remapPadHere = padHere;
    g_remapDirty = false;
    if (browse && focus && !(At<std::uint8_t>(focus, kCtlFlags) & kCtlVisible)) {
        Fn<SetActiveFn>(kSetActive)(g_current, g_rm.frame[g_browseRow], 0);
        g_remapDirty = true;          // laid out again next frame, with the focus on its row
    }
}

void StartListening(int row) {
    if (g_mode != Mode::Browse || row < 0 || row >= kRemapRows) return;
    g_mode = Mode::Listen;
    g_listenRow = row;
    g_listenSeen = remap::Physical();         // what is already held does not count
    g_remapDirty = true;
    Note("remap-listen");
}
// After a choice, or a cancel: nothing more until every button is up again, so the press that
// chose cannot also act on the screen.
void EndListening() {
    g_mode = Mode::Browse;
    g_listenRow = -1;
    g_settle = true;
    g_remapDirty = true;
}
// Remap: the rows become places for the focus, from the row it was last on. Only with a pad: the
// keyboard and the mouse cannot choose a button.
void EnterRemap() {
    if (g_mode != Mode::View || !g_current || !PadPresent()) return;
    g_editor = KmrpRemap::Editor(remap::Saved());
    g_mode = Mode::Browse;
    g_settle = true;
    g_remapDirty = true;
    Selectable(g_rm.frame[g_browseRow], true);
    Fn<SetActiveFn>(kSetActive)(g_current, g_rm.frame[g_browseRow], 0);
    Note("remap-enter");
}
// Back to the layout as saved: anything not saved is dropped, and the focus is nowhere, since
// nothing in View is a place for it.
void ExitRemap() {
    if (!g_current) return;
    g_editor = KmrpRemap::Editor(remap::Saved());
    g_mode = Mode::View;
    g_settle = true;
    g_remapDirty = true;
    Fn<SetActiveFn>(kSetActive)(g_current, nullptr, 0);
    Note("remap-exit");
}
// Close while remapping: back to View, asking first if something is not saved.
void Leave() {
    if (g_editor.mapping != remap::Saved()) {
        g_mode = Mode::Unsaved;
        g_remapDirty = true;
        Note("remap-unsaved");
        return;
    }
    ExitRemap();
}
void Defaults() { g_editor.Reset(); g_remapDirty = true; }
// The view's Default: it replaces the saved layout, so the box asks first.
void AskDefault() {
    if (g_mode != Mode::View || !CanDefault()) return;
    g_mode = Mode::Default;
    g_remapDirty = true;
    Note("remap-default-ask");
}
void UseDefault() {
    if (g_mode != Mode::Default) return;
    if (remap::Save(KmrpRemap::Mapping{})) Note("remap-default-saved");
    g_editor = KmrpRemap::Editor(remap::Saved());
    g_mode = Mode::View;
    g_settle = true;
    g_remapDirty = true;
}
void SaveLayout() {
    if (!g_editor.Complete()) return;
    if (remap::Save(g_editor.mapping)) Note("remap-saved");
    g_remapDirty = true;
}

void RowPressed(void*, void* control) {
    ++g_callbacks;
    if (!Pressed(control) || !Armed() || g_settle || g_mode != Mode::Browse || !g_current) return;
    void* const focus = At<void*>(g_current, kPanelActive);
    for (int b = 0; b < kRemapRows; ++b) if (g_rm.frame[b] == focus) StartListening(b);
}
void DefaultsPressed(void*, void* control) {
    ++g_callbacks;
    if (!Pressed(control) || !Armed() || g_settle) return;
    if (g_mode == Mode::Browse) Defaults();
    else if (g_mode == Mode::View) AskDefault();
}
void SavePressed(void*, void* control) {
    ++g_callbacks;
    if (!Pressed(control) || !Armed() || g_settle) return;
    if (g_mode == Mode::View) EnterRemap();
    else if (g_mode == Mode::Browse) SaveLayout();
}
void DiscardPressed(void*, void* control) {
    ++g_callbacks;
    if (!Pressed(control) || !Armed()) return;
    if (g_mode == Mode::Unsaved) ExitRemap();
    else if (g_mode == Mode::Default) UseDefault();
}
void CancelPressed(void*, void* control) {
    ++g_callbacks;
    if (!Pressed(control) || !Armed()) return;
    if (g_mode == Mode::Unsaved) { g_mode = Mode::Browse; g_remapDirty = true; }
    else if (g_mode == Mode::Default) { g_mode = Mode::View; g_remapDirty = true; }
}
void ListenCancelPressed(void*, void* control) {
    ++g_callbacks;
    if (Pressed(control) && Armed() && g_mode == Mode::Listen) EndListening();
}
// (A) Change in the footer: what A on the focused row does, for the mouse as well.
void ChangePressed(void*, void* control) {
    ++g_callbacks;
    if (Pressed(control) && Armed() && !g_settle && g_mode == Mode::Browse) StartListening(g_browseRow);
}

// Every GUI frame while the screen is open: the button awaited, and the layout.
void RemapFrame() {
    if (!g_rm.built || !g_current) return;
    const std::uint16_t pad = remap::Physical();
    if (g_settle && (pad & (KmrpRemap::RemappableBits | kPadStartBack)) == 0 && !ConfirmHeld()) g_settle = false;
    if (g_mode == Mode::Listen) {
        const std::uint16_t pressed = static_cast<std::uint16_t>(pad & ~g_listenSeen);
        g_listenSeen = pad;
        if (pressed & kPadBack) {
            EndListening();
        } else {
            for (int b = 0; b < kRemapRows; ++b) {
                if (!(pressed & KmrpRemap::Mask[b])) continue;
                // The row's action gets the button; the action that had it has none.
                g_editor.mapping.Assign(g_listenRow, b);
                Note("remap-assigned");
                EndListening();
                break;
            }
        }
    }
    if (g_remapDirty || At<void*>(g_current, kPanelActive) != g_remapFocus || prompts::FamilyLetter() != g_remapFamily ||
        device::PadInUse() != g_remapPad || PadPresent() != g_remapPadHere)
        LayoutRemap();
}

// B, Escape or Back clicked: once per frame.
void HandleBack() {
    if (g_backFrame == g_frameNumber) return;
    g_backFrame = g_frameNumber;
    if (!g_rm.built) { RequestClose(); return; }
    if (g_settle) return;
    if (g_mode == Mode::View) { RequestClose(); return; }
    if (g_mode == Mode::Unsaved) { g_mode = Mode::Browse; g_remapDirty = true; return; }
    if (g_mode == Mode::Default) { g_mode = Mode::View; g_remapDirty = true; return; }
    if (g_mode == Mode::Listen) return;            // Back cancels there, read from the pad
    Leave();
}

// The screen's own buttons, by position as every menu has them. View: Y asks to put back the
// default, X remaps (only while a pad answers), B leaves; A does nothing. Remapping: A asks for a
// row's button (the row's own event), Y puts back the default, X saves, B closes remapping. Either
// box: A for its first button, B to cancel. Waiting for a button and just after a choice, every
// event is swallowed.
bool RemapInput(int event, int value) {
    if (!g_rm.built) return false;
    if (g_mode == Mode::Listen) {
        // B from the keyboard (Escape) cancels; the pad's B may be the button chosen, and is read
        // from the pad (RemapFrame). They are the same event here, so the pad says which it was:
        // its B is down for its own press.
        if (event == kEventB && value && !(remap::Physical() & KmrpRemap::Mask[KmrpRemap::B])) EndListening();
        return true;
    }
    if (g_settle) return true;
    if (g_mode == Mode::Unsaved || g_mode == Mode::Default) {
        if (value && Armed()) {
            if (event == kEventA) {
                if (g_mode == Mode::Unsaved) ExitRemap();
                else UseDefault();
            } else if (event == kEventB) {
                HandleBack();
            }
        }
        return true;
    }
    if (g_mode == Mode::View) {
        if (event == kEventB) { if (value) HandleBack(); return true; }
        if (event == kEventX) { if (value && Armed()) EnterRemap(); return true; }
        if (event == kEventY) { if (value && Armed()) AskDefault(); return true; }
        return event == kEventA;
    }
    if (event == kEventB) { if (value) HandleBack(); return true; }
    if (event == kEventX) { if (value && Armed()) SaveLayout(); return true; }
    if (event == kEventY) { if (value && Armed()) Defaults(); return true; }
    return false;
}

void ForgetRemap() {
    // Their addresses, not their controls: called after the controls are freed too.
    for (void* c : {g_rm.backButton, g_rm.change, g_rm.defaults, g_rm.save, g_rm.discard, g_rm.cancel, g_rm.listenCancel})
        if (c) PadFocusExclude(c, false);
    g_rm = Remap{};
    g_mode = Mode::View;
    g_listenRow = -1;
    g_browseRow = 0;
    g_settle = false;
    g_remapDirty = true;
    g_remapFocus = nullptr;
}

// Frees a KMRP label bound into a panel that is going away, if the panel still holds it.
void Unbind(void* panel, void* control) {
    void** array = At<void**>(panel, kPanelControls);
    const int id = At<int>(control, kCtlId);
    if (LooksLikePointer(array) && id >= 0 && id < At<int>(panel, kPanelControlCount) && array[id] == control)
        array[id] = nullptr;
    DestroyControl(control);
}

}  // namespace

void PadFocusExclude(void* control, bool excluded) {
    for (void*& c : g_padFocusExcluded) {
        if (c != control) continue;
        if (!excluded) c = nullptr;
        return;
    }
    if (!excluded || !control) return;
    for (void*& c : g_padFocusExcluded) {
        if (c) continue;
        c = control;
        return;
    }
}

bool PadFocusExcluded(const void* control) {
    for (const void* c : g_padFocusExcluded) if (c == control) return true;
    return false;
}

void ReleaseGff(void* panel) {
    if (!LooksLikePointer(panel)) return;
    const std::uintptr_t vtable = VtableOf(panel);
    const bool hasGui = LooksLikePointer(At<void*>(panel, kPanelGff));
    preload::PanelLoaded(panel, hasGui);
    if (vtable == kBasePanelVtable && !hasGui) {
        // The base destructor, before the control array goes.
        for (Entry& e : g_entries) {
            if (e.parent != panel) continue;
            if (g_pending == panel) g_pending = nullptr;
            if (g_parent == panel) { g_parent = nullptr; g_returnFocus = nullptr; RequestClose(); }
            Unbind(panel, e.button);
            e = {};
            Note("the entry's screen closed");
        }
        for (ConfirmBadge& b : g_confirmBadges) {
            if (b.panel != panel) continue;
            Unbind(panel, b.label);
            b = {};
        }
        for (DialogBadge& b : g_dialogBadges) {
            if (b.panel != panel) continue;
            Unbind(panel, b.label);
            b = {};
        }
        for (SummaryBadge& b : g_summaryBadges) {
            if (b.panel != panel) continue;
            Unbind(panel, b.label);
            b = {};
        }
        return;
    }
    if (!hasGui) return;
    if (vtable == kStatusSummaryVtable) {
        for (const SummaryBadge& b : g_summaryBadges) if (b.panel == panel) return;
        for (SummaryBadge& b : g_summaryBadges) {
            if (b.panel) continue;
            void* label = BindExtraLabel(panel, "LBL_JOURNAL");
            if (!label) return;
            ShowControl(label, false);
            b = {panel, label, 0, false};
            Note("the status summary's A made");
            return;
        }
        return;
    }
    if (vtable == kDialogVtable) {
        for (const DialogBadge& b : g_dialogBadges) if (b.panel == panel) return;
        for (DialogBadge& b : g_dialogBadges) {
            if (b.panel) continue;
            void* label = Bind(panel, "LBL_KMRPDLG", false);
            if (!label) return;   // a dialog.gui without the label
            ShowControl(label, false);
            b = {panel, label, 0, false, 0};
            Note("the dialogue A made");
            return;
        }
        return;
    }
    if (vtable == kMessageBoxVtable || vtable == kSoloModeVtable) {
        for (const ConfirmBadge& b : g_confirmBadges) if (b.panel == panel) return;
        for (ConfirmBadge& b : g_confirmBadges) {
            if (b.panel) continue;
            void* label = Bind(panel, "LBL_KMRPA", false);
            if (!label) return;   // an older confirm.gui: no badge
            ShowControl(label, false);
            b = {panel, label, 0, false};
            return;
        }
        return;
    }
    // The Gameplay screen, where the entry sits under Key Mapping.
    if (vtable != kGameplayVtable) return;
    for (const Entry& e : g_entries) if (e.parent == panel) return;
    for (Entry& e : g_entries) {
        if (e.parent) continue;
        void* button = Bind(panel, "BTN_KMRPLAY", true);
        if (!button) return;
        Fn<AddEventFn>(kAddEvent)(button, kEventA, panel, reinterpret_cast<void*>(&OnOpen), 0);
        e = {panel, button, false, 0};
        Note("entry made");
        return;
    }
}

void Frame(void* manager) {
    if (g_pending) {
        void* owner = g_pending;
        g_pending = nullptr;
        if (!g_current && LooksLikePointer(manager) && Fn<ExistsFn>(kPanelExists)(manager, owner)) Open(manager, owner);
    }
    UpdateConfirmBadges();
    UpdateDialogBadges();
    UpdateEntryBadges();
    UpdateStatusSummary(manager);
    // Counted whether or not the screen is open: the reopen guard needs it after the close as
    // much as Back needs it after the open.
    if (ConfirmHeld()) g_releasedFrames = 0;
    else if (g_releasedFrames < kArmFrames) ++g_releasedFrames;
    if (g_blockReopen && Armed()) g_blockReopen = false;
    preload::GuiFrame();   // the controller's screens' pictures handed to the engine (item 112)
    ++g_frameNumber;
    if (g_current) {
        Refresh();
        RemapFrame();
    }
}

}  // namespace layout
}  // namespace kmrp
