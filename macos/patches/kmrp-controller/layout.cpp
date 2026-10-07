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
// handler is called with the receiver and the control. CSWGuiInGameGameplay is 0x1005A76D0;
// CSWGuiMessageBox 0x1005AE880 with OK at +0x3D0 and Cancel at +0x610; the Solo Mode query,
// built on it, 0x1005ABEA0.
#include "layout.h"
#include "../kmrp-layout/text.h"

#include "engine.h"
#include "pad.h"
#include "prompts.h"
#include "state.h"

#include <ApplicationServices/ApplicationServices.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>

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
static_assert(kControls <= 64, "owned[] holds 64 controls");

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
void* g_owned[64] = {};
unsigned g_ownedCount = 0;
// The press that opens the screen must not also close it, nor the press that closes it reopen
// it: Back and the entry wait until confirm has been seen released on two frames running.
int g_releasedFrames = 0;
const int kArmFrames = 2;
bool Armed() { return g_releasedFrames >= kArmFrames; }
bool g_blockReopen = false;

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
void OnBack(void*, void*) {
    ++g_callbacks;
    if (!Armed()) { Note("Back ignored: the opening press is still down"); return; }
    RequestClose();
}
void OnOpen(void* owner, void*) {
    ++g_callbacks;
    if (g_blockReopen) { Note("the entry ignored: the closing press is still down"); return; }
    if (!g_current && !g_pending) g_pending = owner;
}

// The screen's HandleInputEvent: B closes it; the rest is the base panel's.
void ScreenInput(void* self, int event, int value) {
    if (value && event == kEventB) { RequestClose(); return; }
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
    Fn<PanelFn>(kStopLoad)(panel);
    if (!complete) { DestroyDeleting(panel); return; }
    Fn<AddEventFn>(kAddEvent)(backButton, kEventA, panel, reinterpret_cast<void*>(&OnBack), 0);
    Fn<SetActiveFn>(kSetActive)(panel, backButton, 0);
    g_family = 0;
    g_device = -1;
    g_releasedFrames = 0;
    Refresh();
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

// Frees a KMRP label bound into a panel that is going away, if the panel still holds it.
void Unbind(void* panel, void* control) {
    void** array = At<void**>(panel, kPanelControls);
    const int id = At<int>(control, kCtlId);
    if (LooksLikePointer(array) && id >= 0 && id < At<int>(panel, kPanelControlCount) && array[id] == control)
        array[id] = nullptr;
    DestroyControl(control);
}

}  // namespace

void ReleaseGff(void* panel) {
    if (!LooksLikePointer(panel)) return;
    const std::uintptr_t vtable = VtableOf(panel);
    const bool hasGui = LooksLikePointer(At<void*>(panel, kPanelGff));
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
    if (g_current) Refresh();
}

}  // namespace layout
}  // namespace kmrp
