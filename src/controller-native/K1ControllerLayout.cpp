// KOTOR 1.03 GUI ABI. See reverse-engineering/custom-gui-controls.md.
#include "K1ControllerLayout.h"
#include <windows.h>
#include "KmrpOptions.h"
#include "K1ButtonRemap.h"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>

extern "C" char __cdecl KmrpGlyphLetterK1();
extern "C" void __cdecl KmrpPaintLayoutEntryPromptK1(void* button, int shown);
bool IsControllerInputActiveK1();
bool ControllerConfirmHeldK1();
std::uint16_t KmrpPadButtonsK1();     // the pad's buttons as pressed (K1NativeJoystick.cpp)
bool KmrpPadPresentK1();              // a pad answered the last read (K1NativeJoystick.cpp)
void KmrpPadFocusExcludeK1(void* control, bool excluded);   // off the pad's focus (K1NativeJoystick.cpp)
bool KmrpQueueLayoutPanelK1(void* panel);   // the screen's pictures for the background (vendor/K1XboxControls.cpp)
bool KmrpPicturesSettledK1();               // a frame went by with nothing left to draw (the same)
void KmrpQueueLayoutControlK1(void* control);

namespace {
// Rows on the Controller Layout screen: GLYPH_nn and TEXT_nn each. Must equal
// ROWS in tools/build_controller_layout.py, which authors the .gui these tags
// are bound from; Test-ControllerPromptAssets.py fails the build otherwise.
constexpr int K1_LAYOUT_ROWS = 13;
constexpr int K1_LAYOUT_FIXED = 10;          // the ten controls before the rows
// Edge art after the rows, DECO_nn: corner brackets, hairlines, readouts and
// the two margin illustrations. Must equal len(DECOR) in
// tools/controller_layout_backdrop.py. Unbound .gui controls are never drawn,
// so each one is bound like any other label.
constexpr int K1_LAYOUT_DECOR = 10;
// Then GLYPH_BACK, the B badge inside the Back button, last so that no earlier
// ID moves. Its fill and visibility follow the pad in refresh().
constexpr int K1_LAYOUT_BACK_GLYPH = K1_LAYOUT_FIXED + 2 * K1_LAYOUT_ROWS + K1_LAYOUT_DECOR;
constexpr int K1_LAYOUT_CONTROLS = K1_LAYOUT_BACK_GLYPH + 1;
// The file's controls, then the remap screen's own (bindAppend): 10 rows of a frame, a
// grey caption and a dot, five padlocks, the footer's six, the two prompts' fourteen,
// and since 2026-10-21 the table's: two heads, two lines, and a name and a picture for
// each of its fifteen rows.
constexpr unsigned kOwnedSlots = 192;
constexpr unsigned kTableControls = 2 + 2 + 2 * 10 + 2 * 5;
static_assert(K1_LAYOUT_CONTROLS + 3 * 10 + 5 + 6 + 14 + kTableControls <= kOwnedSlots, "owned[] holds every control");

template<class T> T& at(void* p, unsigned n) { return *reinterpret_cast<T*>(static_cast<char*>(p)+n); }
template<class T> T fn(unsigned n) { return reinterpret_cast<T>(n); }
using Ctor = void*(__thiscall*)(void*);
using Dtor = void*(__thiscall*)(void*, unsigned);
using PanelCtor = void*(__thiscall*)(void*, void*);
using Simple = void(__thiscall*)(void*);
using StringCtor = void(__thiscall*)(void*, const char*);
using Bind = void(__thiscall*)(void*, void*, void*, int);
using Event = void(__thiscall*)(void*, int, void*, void*);
using Input = void(__thiscall*)(void*, int, int);
using SetActive = void(__thiscall*)(void*, void*, int);
using Exists = int(__thiscall*)(void*, void*);
using Add = void(__thiscall*)(void*, void*, int, int);
using New = void*(__cdecl*)(unsigned);
using Delete = void(__cdecl*)(void*);

// The Controller Layout entry on each Gameplay screen, and whether its A is
// painted and in which family (2026-09-25; see updateEntryBadges).
struct Entry { void* parent; void* button; bool badged; char family; } entries[8] = {};
void* pending = nullptr;
void* current = nullptr;
void* parent = nullptr;
void* returnFocus = nullptr;
std::uintptr_t table[27] = {};
unsigned created=0, destroyed=0, controlsCreated=0, controlsDestroyed=0, callbacks=0;
char family = 0;
int device = -1;
void* owned[kOwnedSlots] = {};
unsigned ownedCount = 0;
// The press that opens the screen must not also close it. A activates the
// entry, the screen opens with Back focused, and the same A -- still held, or
// its release -- then reached Back: the screen flashed for a frame and shut,
// and stayed only while A was held down. So Back does nothing until confirm has
// been seen released on two frames running. Two, not one, because on the frame
// the button comes up the engine may deliver the release before or after this
// hook runs, and one released frame would arm in time for that very release.
//
// The same press must not reopen it either. A on Back closes the screen and
// hands focus back to the Controller Layout entry, and that A then activated
// the entry: the screen closed and came straight back. So after a close the
// entry is ignored until confirm has been released on two frames running, the
// same rule. B was never affected -- it does not activate the entry.
int releasedFrames = 0;
constexpr int K1_LAYOUT_ARM_FRAMES = 2;
bool armed() { return releasedFrames >= K1_LAYOUT_ARM_FRAMES; }
bool blockReopen = false;

// The screen's diagnostics, KMRP\logs\kmrp-layout-lifecycle.log (KmrpLogPath; the game
// folder until 2026-10-20). Null when it cannot be opened.
FILE* openLog() {
    wchar_t path[MAX_PATH];
    FILE* f = nullptr;
    if (!KmrpLogPath(path, L"kmrp-layout-lifecycle.log") || _wfopen_s(&f, path, L"a")) return nullptr;
    return f;
}

void log(const char* event) {
    // Transition-only diagnostics, written with the debug-logs option on. There are
    // no per-frame writes; a session produces only a few short records.
    if (!KmrpDebugLogs()) return;
    FILE* f=nullptr;
    if (!(f = openLog())) return;
    fprintf(f,"%lu %s panel=%p parent=%p created=%u destroyed=%u controls=%u freed=%u callbacks=%u family=%c device=%d\n",
        GetTickCount(),event,current,parent,created,destroyed,controlsCreated,controlsDestroyed,callbacks,family?family:'-',device);
    fclose(f);
}

void destroyControl(void* control) {
    if (!control) return;
    auto v = at<std::uintptr_t*>(control,0);
    reinterpret_cast<Dtor>(v[0])(control,1);
    ++controlsDestroyed;
}

void* bind(void* panel, const char* tag, bool button=false) {
    void* c=fn<New>(0x6FA7E6)(button ? 0x1C4 : 0x140);
    if (!c) return nullptr;
    fn<Ctor>(button ? 0x41C0F0 : 0x41ACD0)(c);
    ++controlsCreated;
    void* name[2] = {};
    fn<StringCtor>(0x5E5A90)(name,tag);
    fn<Bind>(0x40B930)(panel,c,name,1);
    fn<Simple>(0x5E5C20)(name);
    int id=at<int>(c,0x50), count=at<int>(panel,0x24);
    auto array=at<void**>(panel,0x20);
    if (!array || id<0 || id>=count || array[id]!=c) {
        destroyControl(c); log("bind-failed"); return nullptr;
    }
    return c;
}

void requestClose() {
    if (current) {
        // Manager Update removes the modal then calls its deleting destructor.
        // Never delete a panel from the control's callback stack.
        at<unsigned>(current,0x44)=(at<unsigned>(current,0x44)&~0x700u)|0x400u;
        log("close-request");
    }
}
void handleBack();
void __fastcall back(void*,void*,void*) {
    ++callbacks;
    if (!armed()) { log("back-ignored-unarmed"); return; }
    handleBack();
}
void cancelWaiting();
// The panel's own B: the keyboard's Escape. The pad's B reaches input() instead, which
// the remap screen keeps while it waits, since B may be the button chosen; Escape is
// how the keyboard and mouse leave the wait.
void __fastcall onB(void*,void*,int value) { if (value) { ++callbacks; cancelWaiting(); handleBack(); } }
void __fastcall open(void* owner,void*,void*) {
    ++callbacks;
    if (blockReopen) { log("open-ignored-after-close"); return; }
    if (!current && !pending) pending=owner;
    log("open-callback");
}
bool remapInput(int event, int value);
void forgetRemap();
void __fastcall input(void* self,void*,int event,int value) {
    if (remapInput(event, value)) return;
    if (value && event==0x28) { handleBack(); return; }
    fn<Input>(0x409E60)(self,event,value);
}
void* __fastcall destroy(void* self,void*,unsigned flags) {
    log("destroy-begin");
    // Manager already removed the panel on normal closure. Also support an
    // engine shutdown calling the destructor while the panel remains attached.
    void* manager=at<void*>(self,0x18);
    if (manager && fn<Exists>(0x40BD70)(manager,self))
        fn<Exists>(0x40C830)(manager,self);
    fn<SetActive>(0x40A630)(self,nullptr,0);
    auto array=at<void**>(self,0x20);
    for (int i=0;i<at<int>(self,0x24);++i) array[i]=nullptr;
    for (unsigned i=0;i<ownedCount;++i) { destroyControl(owned[i]); owned[i]=nullptr; }
    ownedCount=0;
    forgetRemap();
    fn<Simple>(0x40CF70)(self);
    current=nullptr;
    ++destroyed;
    if (parent && manager && fn<Exists>(0x40BD70)(manager,parent))
        fn<SetActive>(0x40A630)(parent,returnFocus,0);
    parent=nullptr; returnFocus=nullptr;
    blockReopen=true; releasedFrames=0;
    log("destroy-end");
    if (flags&1) fn<Delete>(0x6FA390)(self);
    return self;
}

// ---------------------------------------------------------------- confirm A
//
// The A beside a confirmation box's focused button: Exit Game, Solo Mode,
// overwrite and delete save all use CSWGuiMessageBox and confirm.gui. Its
// FixMessageLabel (0x006253A0) shrinks both buttons to fit their captions, so a
// badge cannot be painted inside one; tools/build_controller_layout.py adds a
// label of its own, LBL_KMRPA, which is bound here and moved each frame to the
// left of whichever button holds focus -- the main menu's travelling A.
//
// Bound at ReleaseGff. The Solo Mode query is built on CSWGuiMessageBox and
// loads confirm.gui from the base constructor (0x00626EB0), so it should arrive
// with the base vtable, 0x0074FDB0, before its own is stored; its own,
// 0x00756F28, is accepted as well rather than trusted never to appear.
constexpr std::uintptr_t K1_MESSAGE_BOX_VTABLE = 0x74FDB0;
constexpr std::uintptr_t K1_SOLO_MODE_QUERY_VTABLE = 0x756F28;
constexpr unsigned K1_MESSAGE_BOX_OK = 0x2F4;      // K1XboxControls.cpp has the
constexpr unsigned K1_MESSAGE_BOX_CANCEL = 0x4B8;  // provenance of both offsets
struct ConfirmBadge { void* panel; void* label; char family; bool shown; }
    confirmBadges[8] = {};

// Committed, readable memory? The badges are forgotten when their box is
// destroyed (ReleaseGff below), and this is the second line of defence the cue
// table lacked: a remembered object read after its pages were released faults,
// which is how loading a save from in game crashed (2026-09-24, in the cue loop).
bool readable(const void* p, std::size_t size) {
    const auto v = reinterpret_cast<std::uintptr_t>(p);
    if (v < 0x10000u || v >= 0x7FFF0000u) return false;
    constexpr DWORD ok = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    const char* at = static_cast<const char*>(p);
    const char* const end = at + size;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(at, &info, sizeof(info)) || info.State != MEM_COMMIT ||
            !(info.Protect & ok) || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)))
            return false;
        at = static_cast<const char*>(info.BaseAddress) + info.RegionSize;
    }
    return true;
}

void showControl(void* c, bool visible) {
    at<unsigned>(c,0x44)=(at<unsigned>(c,0x44)&~2u)|(visible?2u:0);
}

// Every control's slot 1 is SetExtent(const rect*): 0x00417780 for a label,
// 0x00417A20 for a button, both copying {left, top, width, height} to +4.
using SetExtent = void(__thiscall*)(void*, const int*);
void setExtent(void* c, const int* rect) {
    reinterpret_cast<SetExtent>(at<std::uintptr_t*>(c,0)[1])(c,rect);
}

void updateConfirmBadges() {
    const bool pad=IsControllerInputActiveK1();
    const char family=KmrpGlyphLetterK1();
    for (auto& b: confirmBadges) {
        if (!b.panel) continue;
        // The focused button's extent is read up to Cancel+0x14; the label is
        // a 0x140-byte CSWGuiLabel whose fill sits at +0x70.
        if (!readable(b.panel,K1_MESSAGE_BOX_CANCEL+0x14) || !readable(b.label,0x140)) {
            b={}; continue;                 // its box is gone: forget, never touch
        }
        void* active=at<void*>(b.panel,0x1C);
        char* base=static_cast<char*>(b.panel);
        const bool onButton=active==base+K1_MESSAGE_BOX_OK ||
                            active==base+K1_MESSAGE_BOX_CANCEL;
        if (!pad || !onButton) {
            if (b.shown) { showControl(b.label,false); b.shown=false; }
            continue;
        }
        // The button's extent is final by now: FixMessageLabel sizes it when
        // the box is laid out, not per draw. A disc the height of the button,
        // a quarter of that height clear of its left edge.
        const int* r=reinterpret_cast<const int*>(static_cast<char*>(active)+4);
        const int size=r[3];
        const int rect[4]={r[0]-size-size/4, r[1], size, size};
        setExtent(b.label,rect);
        if (family!=b.family) {
            char resref[16]={};
            sprintf_s(resref,"kmr%ccnfa",family);
            using Fill=void(__thiscall*)(void*,const void*,int);
            fn<Fill>(0x414C00)(static_cast<char*>(b.label)+0x70,resref,1);
            b.family=family;
        }
        if (!b.shown) { showControl(b.label,true); b.shown=true; }
    }
}

// ---------------------------------------------------------------- dialogue A
//
// An A at the end of the highlighted reply's text (issue #21). Until 2026-09-25
// it sat left of the reply's number, like the main menu's travelling A, and was
// never seen: at 3440x1440 the text starts at the panel's left edge, the A landed
// at panel x -41, and the engine does not draw a panel's children outside the
// panel. The end of the text is always inside it.
//
// A in dialogue picks the highlighted reply once the line has finished, and
// skips the line while it plays (CSWGuiDialog::HandleInputEvent, 0x006A7266),
// so the A is shown only while replies can be picked.
// tools/prepare_universal_resources.py adds LBL_KMRPDLG to dialog.gui at every
// resolution; it reuses the confirm boxes' A art, kmr?cnfa.
//
// Read from the clean executable, 2026-09-25:
//   0x006A8B6C  the dialogue constructor stores vtable 0x755800, then loads
//               "dialog" and calls ReleaseGff at 0x006A8C1E with it in place
//   0x006A8BC7  LB_REPLIES is the CSWGuiListBox at panel+0x19C4
//   0x006A7266  [panel+0x1DF8] bit 0 set: a line is playing, A skips it
//   0x006A72B9  D-pad up/down move [panel+0x68], floored at 0 and capped at
//               [panel+0x6C]-1 -- taken as the highlighted reply
//   0x0041B1E0  the list's rows are the controls in [list+0x29C], [list+0x2A0]
//               of them, each given its rect by SetExtent
// Which space those row rects are in (the list's or the panel's) was not
// settled statically, so the geometry is logged the first time each
// conversation shows replies, for the play-test to confirm. Rows are taken as
// relative to the list until that says otherwise.
constexpr std::uintptr_t K1_DIALOG_VTABLE = 0x755800;
constexpr unsigned K1_DIALOG_REPLIES = 0x19C4;
constexpr unsigned K1_DIALOG_FLAGS = 0x1DF8;
constexpr unsigned K1_DIALOG_HIGHLIGHT = 0x68;
constexpr unsigned K1_LIST_ROWS = 0x29C;
constexpr unsigned K1_LIST_ROW_COUNT = 0x2A0;
constexpr unsigned K1_LIST_SELECTED = 0x2C8;           // int16, the list's own
constexpr int K1_DIALOG_MAX_ROWS = 64;
struct DialogBadge {
    void* panel; void* label; char family; bool shown; int loggedCount;
} dialogBadges[4] = {};

// The highlighted reply's CSWGuiText: +0xD0 of what the row's vtable+0x50
// returns -- the object CSWGuiDialog::SetReplyActive (0x006A6FC0) colours
// through +0xE8, which is that text's parameters (+0x18).
void* replyText(void* row) {
    if (!readable(row,4)) return nullptr;
    void** const vtable=at<void**>(row,0);
    if (!readable(vtable,0x54)) return nullptr;
    using Owner=char*(__thiscall*)(void*);
    char* const owner=reinterpret_cast<Owner>(vtable[0x50/4])(row);
    if (!readable(owner,0xD0+0x70)) return nullptr;
    void* const text=owner+0xD0;
    return readable(at<void*>(text,0x14),0x44) ? text : nullptr;
}

// Where the reply's last line ends, in pixels from the text's left edge, read
// from the layout the engine draws. The text object ([CSWGuiText+0x14], vtable
// 0x00741878) keeps its string at +0x14, its font at +0x18, each line's length
// at [+0x34] and the line count at +0x38; Draw (0x0045A850) walks them the same
// way -- a negative length is the same length, and one space or newline after a
// line is skipped. A glyph is (lower-right u - upper-left u) x texturewidth x 100
// texels wide: the font information (the font's vtable+0x38) holds the two
// arrays at +0x24 and +0x18, 12 bytes a glyph, and texturewidth at +0x0C, as
// the line breaker (0x0045A2F0) reads them. KMRP's atlases draw one texel per
// pixel (Test-FontAtlasScale.py), so texels are pixels.
//
// Not CSWGuiText::GetIdealWidthAndHeight (0x00414F10), which the first builds
// used: at 3440x1440 it measured a reply at 320 px that the screen showed at
// about 600, and the A landed mid-sentence (play-test, 2026-09-25). Why is not
// established. This comment first blamed the text object's scale (+0x40), but
// the next play-test logged textScale=1.0000. It also re-wraps the text at each
// width it tries, which reading the drawn layout does not.
struct ReplyLine { int width; int lines; float scale; int lineHeight; };

bool lastReplyLine(void* text, ReplyLine& out) {
    char* const object=at<char*>(text,0x14);
    if (!readable(object,0x44)) return false;
    const char* const string=at<const char*>(object,0x14);
    void* const font=at<void*>(object,0x18);
    const int lines=at<int>(object,0x38);
    const int* const lengths=at<const int*>(object,0x34);
    if (lines<1 || lines>32 || !readable(lengths,lines*sizeof(int)) || !readable(font,4))
        return false;
    auto length=[&](int i) { return lengths[i]<0 ? -lengths[i] : lengths[i]; };
    int total=1;                                    // the terminator
    for (int i=0;i<lines;++i) total+=length(i)+1;   // a line and its separator
    if (total>4096 || !readable(string,total-1)) return false;
    void** const vtable=at<void**>(font,0);
    if (!readable(vtable,0x3C)) return false;
    using Info=char*(__thiscall*)(void*);
    char* const info=reinterpret_cast<Info>(vtable[0x38/4])(font);
    if (!readable(info,0x28)) return false;
    const char* const upperLeft=at<const char*>(info,0x18);
    const char* const lowerRight=at<const char*>(info,0x24);
    if (!readable(upperLeft,256*12) || !readable(lowerRight,256*12)) return false;
    const float texels=at<float>(info,0x0C)*100.0f;
    const char* line=string;
    for (int i=0;i+1<lines;++i) {
        line+=length(i);
        if (*line=='\n' || *line==' ') ++line;
    }
    int end=length(lines-1);
    while (end>0 && line[end-1]==' ') --end;        // a trailing space is not text
    float width=0.0f;
    for (int i=0;i<end && line[i];++i) {
        const int glyph=static_cast<unsigned char>(line[i])*12;
        width+=(*reinterpret_cast<const float*>(lowerRight+glyph)
               -*reinterpret_cast<const float*>(upperLeft+glyph))*texels;
    }
    out.width=static_cast<int>(width+0.5f);
    out.lines=lines;
    out.scale=at<float>(object,0x40);
    // One drawn line: fontheight x 100 texels (font information +0x04, as
    // CSWGuiText's height function reads it), texels being pixels here.
    out.lineHeight=static_cast<int>(at<float>(info,0x04)*100.0f+0.5f);
    return out.width>0;
}
unsigned dialogGeometryLogs = 0;

void logDialogGeometry(const DialogBadge& b, char* list, void** rows, int count,
                       int highlight, const int* placed, const ReplyLine& last) {
    if (!KmrpDebugLogs() || dialogGeometryLogs >= 24) return;   // a session's worth, no more
    ++dialogGeometryLogs;
    FILE* f=nullptr;
    if (!(f = openLog())) return;
    const int* panelRect=reinterpret_cast<const int*>(static_cast<char*>(b.panel)+4);
    const int* listRect=reinterpret_cast<const int*>(list+4);
    fprintf(f,"%lu dialog-geometry panel=%p rect=(%d,%d,%d,%d) list=(%d,%d,%d,%d) rows=%d "
              "highlight=%d listSelected=%d flags=%08X placed=(%d,%d,%d,%d) "
              "lineWidth=%d lines=%d lineHeight=%d textScale=%.4f",
        GetTickCount(),b.panel,panelRect[0],panelRect[1],panelRect[2],panelRect[3],
        listRect[0],listRect[1],listRect[2],listRect[3],count,highlight,
        static_cast<int>(at<short>(list,K1_LIST_SELECTED)),
        at<unsigned>(b.panel,K1_DIALOG_FLAGS),placed[0],placed[1],placed[2],placed[3],
        last.width,last.lines,last.lineHeight,static_cast<double>(last.scale));
    // The render viewport the text is normalised by (index at 0x007B9460, 10-byte
    // entries from 0x007B946C), to check the scale above against it.
    const short viewport=*reinterpret_cast<const short*>(0x7B9460);
    if (viewport>=0 && viewport<8)
        fprintf(f," viewport=%d:%dx%d",viewport,
                *reinterpret_cast<const short*>(0x7B946C+viewport*10),
                *reinterpret_cast<const short*>(0x7B946E + viewport*10));
    for (int i=0;i<count && i<6;++i) {
        if (!readable(rows[i],0x14)) break;
        const int* r=reinterpret_cast<const int*>(static_cast<char*>(rows[i])+4);
        fprintf(f," row%d=(%d,%d,%d,%d)",i,r[0],r[1],r[2],r[3]);
    }
    fputc('\n',f);
    fclose(f);
}

void updateDialogBadges() {
    const bool pad=IsControllerInputActiveK1();
    const char family=KmrpGlyphLetterK1();
    for (auto& b: dialogBadges) {
        if (!b.panel) continue;
        if (!readable(b.panel,K1_DIALOG_FLAGS+4) || !readable(b.label,0x140)) {
            b={}; continue;                 // the panel is gone: forget, never touch
        }
        char* list=static_cast<char*>(b.panel)+K1_DIALOG_REPLIES;
        const bool linePlaying=(at<unsigned>(b.panel,K1_DIALOG_FLAGS)&1u)!=0;
        const int count=at<int>(list,K1_LIST_ROW_COUNT);
        void** rows=at<void**>(list,K1_LIST_ROWS);
        const int highlight=at<int>(b.panel,K1_DIALOG_HIGHLIGHT);
        const bool choosing=pad && !linePlaying && count>0 && count<=K1_DIALOG_MAX_ROWS &&
            rows && readable(rows,count*sizeof(void*)) && highlight>=0 && highlight<count &&
            readable(rows[highlight],0x14);
        if (!choosing) {
            if (b.shown) { showControl(b.label,false); b.shown=false; }
            if (count<=0) b.loggedCount=0;      // the next set of replies logs again
            continue;
        }
        // One text line: the shortest row, so a reply that wraps onto two lines
        // still gets a glyph the height of a line, level with its first line.
        int line=0;
        for (int i=0;i<count;++i) {
            if (!readable(rows[i],0x14)) continue;
            const int h=at<int>(rows[i],0x10);
            if (h>0 && (line==0 || h<line)) line=h;
        }
        const int* listRect=reinterpret_cast<const int*>(list+4);
        const int* r=reinterpret_cast<const int*>(static_cast<char*>(rows[highlight])+4);
        if (line<=0) line=r[3];
        // A quarter larger than a one-line row (maintainer, 2026-09-25): the art
        // has a transparent rim, and at the row's own height the A read smaller
        // than the text.
        const int size=line+line/4;
        // The reply text starts after the list's scrollbar, which sits on the
        // left and is the width the rows leave free (list width - row width):
        // at 3440x1440 the rows are 3312 wide in a 3344 list, so 32 px. The
        // first build placed the A from the row's own x and missed this, which
        // put it at panel x -77 -- screen x -29, off the left edge. Measured
        // from the play-test log of 2026-09-25; at 1920x1080 the same rule
        // gives the text start seen in the screenshot, 48 + 16 = 64 px.
        const int scrollbar=listRect[2]>r[2] ? listRect[2]-r[2] : 0;
        const int textStart=listRect[0]+r[0]+scrollbar;
        const int* panelRect=reinterpret_cast<const int*>(static_cast<char*>(b.panel)+4);
        // The end of the reply's last line, read from the layout being drawn.
        void* const text=replyText(rows[highlight]);
        ReplyLine last={};
        const bool measured=text && lastReplyLine(text,last);
        // Half the badge past the text: an eighth, with the art's rim, still
        // touched the last letter in play (2026-09-25). Inside the panel, since
        // the engine does not draw a panel's children outside it.
        int left=textStart+last.width+size/2;
        if (left+size>panelRect[2]) left=panelRect[2]-size;
        if (left<0) left=0;
        // Centred on the letters of the last line, from the line height
        // (maintainer, 2026-09-25: "vertical lineheight based centering"). A
        // reply of n lines is n lines of the font, centred in its row, so its
        // last line starts n-1 lines below the block's top. Within that line the
        // letters are low: the play-test screenshot of 2026-09-25 put this font's
        // capital tops and baseline 11 and 28 px into a 32 px line at 3440x1440,
        // so their middle is 5/8 of a line down, and the A's middle goes there.
        // The two builds before put it at half a line (seen as sitting high) and
        // at a whole line (seen as low).
        const int lines=measured ? last.lines : 1;
        const int lineHeight=measured && last.lineHeight>0 ? last.lineHeight : line;
        const int block=lines*lineHeight;
        const int lastLineTop=r[1]+(r[3]>block ? (r[3]-block)/2 : 0)+(lines-1)*lineHeight;
        const int centre=lastLineTop+lineHeight*5/8;
        int top=listRect[1]+centre-size/2;
        if (top+size>panelRect[3]) top=panelRect[3]-size;
        if (top<0) top=0;
        // Shown while its row is in the list's view; the badge itself is kept
        // inside the panel above, so a bottom row does not lose it.
        const bool inList=centre>=0 && centre<=listRect[3];
        const int rect[4]={left, top, size, size};
        if (b.loggedCount!=count) {
            logDialogGeometry(b,list,rows,count,highlight,rect,last);
            b.loggedCount=count;
        }
        if (!inList || !measured) {             // scrolled out, or nothing measured
            if (b.shown) { showControl(b.label,false); b.shown=false; }
            continue;
        }
        setExtent(b.label,rect);
        if (family!=b.family) {
            char resref[16]={};
            sprintf_s(resref,"kmr%ccnfa",family);
            using Fill=void(__thiscall*)(void*,const void*,int);
            fn<Fill>(0x414C00)(static_cast<char*>(b.label)+0x70,resref,1);
            b.family=family;
        }
        if (!b.shown) { showControl(b.label,true); b.shown=true; }
    }
}

// ---------------------------------------------------------------- status summary
//
// The box that lists what just changed, each line beside its icon, with OK under
// them: "Journal Entry Added", "Credits Lost: 100", "Experience Points (XP)
// Received: 50", "Item(s) Received". Reported broken at 3440x1440 on 2026-09-25
// from three screenshots: text past the box's right edge, OK drawn over the last
// line as a bar, and the XP line showing only "Received: 50".
//
// CSWGuiStatusSummary (constructor 0x006272A0, vtable 0x0074FF68) loads
// statussummary.gui, which High Resolution Menus does not ship, so it is the
// game's own 640x480 file (gui.bif): a 322x332 box, 32x32 icons at x 10, lines at
// x 52 that are 32 tall, OK 100x22. Its layout is code, 0x00625C60, in the same
// pixels: rows from y 10 and 37 apart (0x0062622A); each line 150 wide at first
// and widened 20 at a time (0x006261E8) until the line breaker fits it on one line,
// but never past 440 (0x006261AE, 0x006261F4); the box that width plus 62, centred
// on the screen (0x00626274..0x006262B4); OK 7 above where the next row would
// start and the box 32 below that (0x0062627B, 0x00626282).
//
// That was right for a 16 px font. KMRP draws text at the resolution's scale --
// 32 px a line at 3440x1440 -- so the rows collide, OK lands on the last line, the
// XP line hits the 440 cap and wraps with only its second line in view (the box
// measured 507 px on the screenshot, the formula gives 502), and the breaker's
// measure, which truncates each glyph, stops the widening short of the drawn text.
//
// So the box is laid out again every frame after the engine's own pass: the same
// layout scaled by the lines' font height over 16, each line as wide as the glyphs
// the engine draws for it (the dialogue A's measure, lastReplyLine above), capped
// only by the screen. Only the extents change, and only when they differ.
// Seen in game at 3440x1440 on 2026-09-25 with one row, "Journal Entry Added"
// after Trask's first conversation: box 489x144 on the screen's centre, the line
// inside it, OK centred under it. Two or more rows have not been seen yet.
constexpr std::uintptr_t K1_STATUS_SUMMARY_VTABLE = 0x74FF68;
constexpr unsigned K1_SUMMARY_ICONS = 0x300;   // nine CSWGuiLabels, 0x140 apart
constexpr unsigned K1_SUMMARY_LINES = 0xE40;   // their lines, in the same order
constexpr unsigned K1_SUMMARY_OK = 0x1980;     // CSWGuiButton
constexpr unsigned K1_LABEL_SIZE = 0x140;
constexpr int K1_SUMMARY_ROWS = 9;

// The pad's A beside OK, placed as the confirm boxes place theirs (2026-09-25:
// "just add the glyph to the journal entry popup"). A is OK here: the constructor
// registers OK's handler, 0x00624BA0, for 0x27 on BTN_OK (0x0062776E..0x00627772).
//
// statussummary.gui is the game's own, KMRP does not ship it, and it has no
// control for a badge, so the label is made from one it does have. bind's last
// argument says whether the control is stored in the panel's array: with 0 it is
// only loaded from the .gui by tag (0x0040B94D skips the store; the loader,
// 0x00418840, sets the parent and calls the control's own load), so a new label
// takes LBL_JOURNAL's struct -- a plain near-white 32x32 icon label -- and
// LBL_JOURNAL keeps its slot. The new one goes in the array's first empty slot:
// the binder pads with nulls up to each ID it stores (0x0040B970), and the .gui
// has no ID 16, the net shift's, so there is one between the lines and OK.
struct SummaryBadge { void* panel; void* label; char family; bool shown; }
    summaryBadges[4] = {};

void* bindExtraLabel(void* panel, const char* like) {
    void* c=fn<New>(0x6FA7E6)(K1_LABEL_SIZE);
    if (!c) return nullptr;
    fn<Ctor>(0x41ACD0)(c);
    ++controlsCreated;
    at<int>(c,0x50)=-1;                    // set by the load only if `like` exists
    void* name[2] = {};
    fn<StringCtor>(0x5E5A90)(name,like);
    fn<Bind>(0x40B930)(panel,c,name,0);
    fn<Simple>(0x5E5C20)(name);
    void** const array=at<void**>(panel,0x20);
    const int count=at<int>(panel,0x24);
    int slot=-1;
    if (at<int>(c,0x50)>=0 && array && count>0 && readable(array,count*sizeof(void*)))
        for (int i=0;i<count;++i) if (!array[i]) { slot=i; break; }
    if (slot<0) { destroyControl(c); log("bind-failed"); return nullptr; }
    at<int>(c,0x50)=slot;
    array[slot]=c;
    return c;
}

// Is this control one of the panel's own? One of the nine rows, the net shift
// (LBL_NETSHIFT and its line), has no control in statussummary.gui, so binding
// left it out of the panel's array and the engine never draws it; such a row must
// not take a place.
bool boundTo(void* panel, void* control) {
    const int id=at<int>(control,0x50), count=at<int>(panel,0x24);
    void** const array=at<void**>(panel,0x20);
    return id>=0 && id<count && readable(array,count*sizeof(void*)) && array[id]==control;
}

// The width of a label's whole text on one line, in pixels, from the glyphs its
// font draws -- the measure lastReplyLine uses -- and that font's line height.
//
// Plus the font's spacingR after each glyph but the last, which that measure
// leaves out: Draw adds font information +0x10 to every glyph's width before
// scaling it (0x0045ABDF: (u width x texturewidth + spacingR) x scale), and
// KMRP's dialogfont16x16 has spacingR 0.005, half a pixel, at 1920x1080 and
// 3440x1440 alike (+0x10 read from the game's memory, 2026-09-25; +0x14 beside
// it is spacingB). Without it "Journal Entry Added" measured 262 px at 1920x1080
// and drew 273, 6 px from the box's edge (357 and 364 at 3440x1440).
// lastReplyLine keeps the short measure: the dialogue A's gap was tuned by eye
// on top of it.
// The width of a control's text in its own font: a label's CSWGuiText is at +0xD0
// (its text parameters, +0xE8, are 0x18 into it), a button's at +0x154 (parameters at
// +0x16C, as setText writes them).
int controlTextWidth(void* control, unsigned textAt, int& lineHeight);
int labelTextWidth(void* label, int& lineHeight) { return controlTextWidth(label, 0xD0, lineHeight); }
int buttonTextWidth(void* button) { int lh = 0; return controlTextWidth(button, 0x154, lh); }
int controlTextWidth(void* control, unsigned textAt, int& lineHeight) {
    char* const text=static_cast<char*>(control)+textAt;  // its CSWGuiText
    if (!readable(text,0x18)) return 0;
    char* const object=at<char*>(text,0x14);
    if (!readable(object,0x44)) return 0;
    const char* const string=at<const char*>(object,0x14);
    void* const font=at<void*>(object,0x18);
    if (!readable(string,1) || !readable(font,4)) return 0;
    void** const vtable=at<void**>(font,0);
    if (!readable(vtable,0x3C)) return 0;
    using Info=char*(__thiscall*)(void*);
    char* const info=reinterpret_cast<Info>(vtable[0x38/4])(font);
    if (!readable(info,0x28)) return 0;
    const char* const upperLeft=at<const char*>(info,0x18);
    const char* const lowerRight=at<const char*>(info,0x24);
    if (!readable(upperLeft,256*12) || !readable(lowerRight,256*12)) return 0;
    const float texels=at<float>(info,0x0C)*100.0f;
    const float spacing=at<float>(info,0x10)*100.0f;
    float width=0.0f;
    int glyphs=0;
    for (int i=0;i<256;++i) {
        if (!readable(string+i,1) || string[i]=='\0') break;
        if (string[i]=='\n') continue;
        const int glyph=static_cast<unsigned char>(string[i])*12;
        width+=(*reinterpret_cast<const float*>(lowerRight+glyph)
               -*reinterpret_cast<const float*>(upperLeft+glyph))*texels;
        ++glyphs;
    }
    if (glyphs>1 && spacing>0.0f && spacing<8.0f) width+=spacing*(glyphs-1);
    lineHeight=static_cast<int>(at<float>(info,0x04)*100.0f+0.5f);
    return static_cast<int>(width+0.5f);
}

void setExtentIfChanged(void* control, const int* rect) {
    const int* now=reinterpret_cast<const int*>(static_cast<char*>(control)+4);
    if (now[0]!=rect[0] || now[1]!=rect[1] || now[2]!=rect[2] || now[3]!=rect[3])
        setExtent(control,rect);
}

// Shown while a pad is in use: a disc the height of OK, a quarter of that height
// clear of its left edge, as updateConfirmBadges does it. `ok` is OK's rect.
bool updateSummaryBadge(void* panel, const int* ok) {
    for (auto& b: summaryBadges) {
        if (b.panel!=panel) continue;
        if (!readable(b.label,K1_LABEL_SIZE)) { b={}; return false; }
        if (!IsControllerInputActiveK1()) {
            if (b.shown) { showControl(b.label,false); b.shown=false; }
            return false;
        }
        const int size=ok[3];
        const int rect[4]={ok[0]-size-size/4, ok[1], size, size};
        setExtentIfChanged(b.label,rect);
        const char family=KmrpGlyphLetterK1();
        if (family!=b.family) {
            char resref[16]={};
            sprintf_s(resref,"kmr%ccnfa",family);
            using Fill=void(__thiscall*)(void*,const void*,int);
            fn<Fill>(0x414C00)(static_cast<char*>(b.label)+0x70,resref,1);
            b.family=family;
        }
        if (!b.shown) { showControl(b.label,true); b.shown=true; }
        return true;
    }
    return false;
}

unsigned summaryLogs = 0;

void layoutStatusSummary(void* manager, void* panel) {
    if (!readable(panel,K1_SUMMARY_OK+0x1C4) || !readable(manager,0x70)) return;
    char* const base=static_cast<char*>(panel);
    int rows[K1_SUMMARY_ROWS]={};
    int count=0, widest=0, lineHeight=0;
    for (int i=0;i<K1_SUMMARY_ROWS;++i) {
        void* const icon=base+K1_SUMMARY_ICONS+i*K1_LABEL_SIZE;
        void* const line=base+K1_SUMMARY_LINES+i*K1_LABEL_SIZE;
        // The engine shows a row by setting its icon's visible bit (0x0062604x
        // and 0x00626245 clear it again).
        if (!(at<unsigned>(icon,0x44)&2u) || !boundTo(panel,icon) || !boundTo(panel,line))
            continue;
        int height=0;
        const int width=labelTextWidth(line,height);
        if (width<=0 || height<=0) continue;
        if (width>widest) widest=width;
        if (height>lineHeight) lineHeight=height;
        rows[count++]=i;
    }
    if (!count) return;
    // The 640x480 layout, in units of its own 16 px line.
    auto at16=[lineHeight](int v) { return (v*lineHeight+8)/16; };
    const int screenW=at<short>(manager,0x6C), screenH=at<short>(manager,0x6E);
    if (screenW<=0 || screenH<=0) return;
    const int lineX=at16(52);
    // The widest line as drawn, and a quarter of a line more: the art's border
    // sits on the box's edge, and text touching it read as clipped.
    int lineW=widest+lineHeight/4;
    int boxW=lineX+lineW+at16(10);
    if (boxW>screenW) { boxW=screenW; lineW=boxW-lineX-at16(10); }
    // Room for OK, the pad's A left of it and as much again on the right, so OK
    // stays centred; one short line would otherwise put the A on the box's edge.
    const int okW=at16(100), okH=at16(22);
    const int roomy=okW+2*(okH+okH/4+at16(4));
    if (boxW<roomy) boxW=roomy<screenW ? roomy : screenW;
    int y=at16(10);
    for (int n=0;n<count;++n) {
        void* const icon=base+K1_SUMMARY_ICONS+rows[n]*K1_LABEL_SIZE;
        void* const line=base+K1_SUMMARY_LINES+rows[n]*K1_LABEL_SIZE;
        const int iconRect[4]={at16(10),y,at16(32),at16(32)};
        const int lineRect[4]={lineX,y-at16(1),lineW,at16(32)};
        setExtentIfChanged(icon,iconRect);
        setExtentIfChanged(line,lineRect);
        y+=at16(37);
    }
    const int okY=y-at16(7);
    const int boxH=okY+at16(32);
    const int okRect[4]={(boxW-okW)/2,okY,okW,okH};
    const int boxRect[4]={(screenW-boxW)/2,(screenH-boxH)/2,boxW,boxH};
    setExtentIfChanged(base+K1_SUMMARY_OK,okRect);
    setExtentIfChanged(panel,boxRect);
    const bool badged=updateSummaryBadge(panel,okRect);
    if (KmrpDebugLogs() && summaryLogs<8) {
        ++summaryLogs;
        FILE* f=nullptr;
        if ((f = openLog()) != nullptr) {
            fprintf(f,"%lu status-summary rows=%d lineHeight=%d widest=%d box=(%d,%d,%d,%d) ok=(%d,%d,%d,%d) badge=%d\n",
                GetTickCount(),count,lineHeight,widest,boxRect[0],boxRect[1],boxRect[2],boxRect[3],
                okRect[0],okRect[1],okRect[2],okRect[3],badged?1:0);
            fclose(f);
        }
    }
}

// The status summary, wherever the manager holds it: its panel list or, while it
// waits for OK, its modal list.
void updateStatusSummary(void* manager) {
    if (!readable(manager,0x9C)) return;
    const unsigned lists[2][2]={{0x88,0x8C},{0x94,0x98}};
    for (const auto& list: lists) {
        void** const panels=at<void**>(manager,list[0]);
        const int count=at<int>(manager,list[1]);
        if (count<=0 || count>256 || !readable(panels,count*sizeof(void*))) continue;
        for (int i=0;i<count;++i) {
            void* const panel=panels[i];
            if (readable(panel,4) && at<std::uintptr_t>(panel,0)==K1_STATUS_SUMMARY_VTABLE) {
                layoutStatusSummary(manager,panel);
                return;
            }
        }
    }
}

// The Controller Layout entry's A, while it has its screen's focus and a pad is
// in use -- FocusOnly, as Mouse and Key Mapping above it
// (vendor/K1XboxControls.cpp). The button is bound here at run time, so it has no
// offset in that file's tables; it is painted through KmrpPaintLayoutEntryPromptK1,
// which keeps the resref there. Repainted only on a change.
void updateEntryBadges() {
    const bool pad=IsControllerInputActiveK1();
    const char glyph=KmrpGlyphLetterK1();
    for (auto& e: entries) {
        if (!e.parent) continue;
        if (!readable(e.parent,0x20) || !readable(e.button,0x1C4)) continue;
        const bool want=pad && at<void*>(e.parent,0x1C)==e.button;
        if (want==e.badged && (!want || glyph==e.family)) continue;
        KmrpPaintLayoutEntryPromptK1(e.button,want?1:0);
        e.badged=want; e.family=glyph;
    }
}

// ---------------------------------------------------------------- remapping
//
// The screen is where the controller is remapped (the maintainer's design,
// 2026-10-18, from mockups he approved; the rules are K1ButtonRemapPolicy.h, the
// runtime K1ButtonRemap.cpp). It opens on the drawing: each row's line points at one
// button, so a row is a BUTTON and shows the action on it, and what stays with a
// button is grey beside it (its meaning in menus, which keep every button where it is,
// or a stick's movement). Moving, the camera, the D-pad, Start and Back cannot be
// changed and carry a padlock.
//
// Remap swaps the drawing for a table (the maintainer, 2026-10-21: "make it a table
// thats easier for the user to understand"; layoutTable): one row per ACTION, its name
// and its button's picture, in the order of kActionNames; then, under a line, the five
// that stay, grey with a padlock. Giving an action a button takes that button from the
// action that had it (Mapping::Assign), which then shows an orange question mark
// until it gets another. Until that day remapping happened on the drawing, whose rows
// are buttons: an action given another button moved to that button's row, and the
// displaced one waited in the row the mover left (Editor::Assign, still there).
//
// The pad: the D-pad moves between the table's rows (the focus layer, K1NativeJoystick.cpp:
// each changeable row has a frame, a button with no picture of its own, whose focus
// draws the game's own border), A asks for a row's new button, Y puts back the
// default, X saves (only once every action has a button), B leaves, asking first when
// something is not saved. The footer's buttons are pad buttons, not places for the
// focus: (A) Change (a button since 2026-10-21, the hint "Change button" before),
// (Y) Default, (X) Save and (B) Close cannot be selected, so the D-pad never reaches
// them, and the mouse still clicks them. While waiting for a button the screen reads the pad
// itself (KmrpPadButtonsK1): menus send no event for LB or a stick's click, RB's
// (Black, the Journal's sort) means nothing on this screen, and every one of them may
// be chosen. Back cancels there, because it can never be chosen.
//
// Before Remap, in the view, Y is Default too (2026-10-20): it asks first, then saves
// the default layout; greyed while the saved layout is already the default. Remap is
// greyed while no pad answers, and the help line asks for one (2026-10-21).
//
// The actions and their defaults are the original Xbox game's (issue 49, 2026-10-19).
//
// Nothing here is in the layout file: every control is made from one of the file's
// own as the screen opens (bindAppend), and placed from the file's rows, so it follows
// the file at every resolution, and the file stays as KMRP's sets have it.
constexpr int kRemapRows = KmrpRemap::ButtonCount;
const char* const kActionNames[kRemapRows] = {
    "Interact", "Disengage", "Add to queue", "Undo or flourish", "Pause",
    "Switch ally", "Previous target", "Next target", "Flourish", "Free look"};
// What stays with each button: after its action, or before it on the sticks. RB's
// menu action is the Xbox's Black: the next party member on the four screens about
// one, and the Journal's sort.
const char* const kFixedAfter[kRemapRows] = {
    "/ Select", "/ Back", "/ Menu action", "/ Menu action", "", "/ Menu action", "/ Prev tab", "/ Next tab", "", ""};
const char* const kFixedBefore[kRemapRows] = {
    "", "", "", "", "", "", "", "", "Move / Click:", "Camera / Click:"};
constexpr int kRowBack = 2, kRowDpad = 4, kRowStart = 7;      // LAYOUT's fixed rows
// The table's rows that stay, after the actions: a name, and the drawing's own picture
// of the control (its LAYOUT row, kmr?lyt<row>), the plain stick rather than the click.
constexpr int kStayRows = 5;
struct Stay { const char* name; int row; };
constexpr Stay kStay[kStayRows] = {
    {"Move", 3}, {"Camera", 12}, {"Action bar", kRowDpad}, {"Menus", kRowStart}, {"Solo mode", kRowBack}};
constexpr float kGrey[3] = {150 / 255.0f, 150 / 255.0f, 155 / 255.0f};
constexpr float kYellow[3] = {236 / 255.0f, 226 / 255.0f, 38 / 255.0f};
constexpr float kOrange[3] = {245 / 255.0f, 140 / 255.0f, 30 / 255.0f};
constexpr char kAsk[16] = "kmrrmask", kLock[16] = "kmrrmlock", kDot[16] = "kmrrmdot";
constexpr char kBlack[16] = "blackfill";

// View: the layout shown, nothing to change; Default (Y), Remap (X) or Back (B). Browse:
// remapping, a row's A asks for its button; Default (Y), Save (X) or Close (B), which
// goes back to View. Listen: a button awaited. Unsaved: Close with changes not saved.
// Default: the view's Default asking before it replaces the saved layout (the
// maintainer, 2026-10-20: "add a default button to the controller layout").
enum class Mode { View, Browse, Listen, Unsaved, Default };
struct Remap {
    bool built = false;
    void* frame[kRemapRows] = {};
    void* fixed[kRemapRows] = {};
    void* dot[kRemapRows] = {};
    void* lockMove = nullptr; void* lockCamera = nullptr; void* lockDpad = nullptr;
    void* lockBack = nullptr; void* lockStart = nullptr;
    void* change = nullptr; void* changeGlyph = nullptr;   // (A) Change, while remapping (2026-10-21)
    void* defaults = nullptr; void* defaultsGlyph = nullptr;
    void* save = nullptr; void* saveGlyph = nullptr;
    void* backButton = nullptr;      // the file's BTN_BACK, kept off the pad's focus while open
    void* listenBox = nullptr; void* listenTitle = nullptr; void* listenLine = nullptr;
    void* listenGlyph = nullptr; void* listenCancel = nullptr;
    void* dim = nullptr; void* unsavedBox = nullptr; void* unsavedTitle = nullptr;
    void* unsavedLine1 = nullptr; void* unsavedLine2 = nullptr;
    void* discard = nullptr; void* discardGlyph = nullptr; void* cancel = nullptr; void* cancelGlyph = nullptr;
    // The table (layoutTable): its two heads, the line under them and the line above the
    // rows that stay, each action's name and button, each staying control's name and
    // picture. The frames, the dots and the padlocks are the drawing's, placed again.
    void* head[2] = {}; void* line[2] = {};
    void* actionText[kRemapRows] = {}; void* actionGlyph[kRemapRows] = {};
    void* stayText[kStayRows] = {}; void* stayGlyph[kStayRows] = {};
    float cyan[3] = {};              // the captions' own colour, as the file gives it
    float saveBorder[3] = {};        // Save's and Default's border colour, while they can be pressed
    int help[4] = {}, back[4] = {}, backGlyph[4] = {};   // the file's, before anything moved
    int text[K1_LAYOUT_ROWS][4] = {};    // each row's caption box, as the file has it: every layout starts from it
} rm;
KmrpRemap::Editor editor;
Mode mode = Mode::View;
int listenRow = -1;
int browseRow = 0;            // the table row the focus was last on, Interact's at first
std::uint16_t listenSeen = 0;
bool settle = false;          // after a choice: every event ignored until the pad's buttons are all up
bool remapDirty = true;
char remapFamily = 0;
void* remapFocus = nullptr;
bool remapPad = false;
bool remapPadHere = false;     // whether a pad answered when the screen was last laid out

void ownControl(void* c) { if (c && ownedCount < kOwnedSlots) owned[ownedCount++] = c; }

// A control made from one of the file's, by its tag, and added after the others
// (CSWGuiPanel::AddControl, 0x0040B9A0, `ret 4`): the file's array has no free slots.
void* bindAppend(void* panel, const char* like, bool button) {
    void* c = fn<New>(0x6FA7E6)(button ? 0x1C4 : 0x140);
    if (!c) return nullptr;
    fn<Ctor>(button ? 0x41C0F0 : 0x41ACD0)(c);
    ++controlsCreated;
    at<int>(c, 0x50) = -1;
    void* name[2] = {};
    fn<StringCtor>(0x5E5A90)(name, like);
    fn<Bind>(0x40B930)(panel, c, name, 0);
    fn<Simple>(0x5E5C20)(name);
    const int count = at<int>(panel, 0x24);
    if (at<int>(c, 0x50) < 0 || count < 0 || count >= 512) { destroyControl(c); log("bind-failed"); return nullptr; }
    at<int>(c, 0x50) = count;
    fn<void(__thiscall*)(void*, void*)>(0x40B9A0)(panel, c);
    void** const array = at<void**>(panel, 0x20);
    if (at<int>(panel, 0x24) != count + 1 || !array || array[count] != c) { destroyControl(c); log("bind-failed"); return nullptr; }
    ownControl(c);
    return c;
}

void setText(void* c, const char* text, bool button = false) {
    void* string[2] = {};
    fn<StringCtor>(0x5E5A90)(string, text);
    fn<void(__thiscall*)(void*, void*)>(0x415E00)(static_cast<char*>(c) + (button ? 0x16C : 0xE8), string);
    fn<Simple>(0x5E5C20)(string);
}
// CSWGuiTextParams::SetColor (0x00414E10, `ret 4`): the colour at +0x1C of a label's
// text parameters (+0xE8), passed on to its text.
void setColour(void* label, const float* rgb) {
    const float* now = reinterpret_cast<const float*>(static_cast<char*>(label) + 0xE8 + 0x1C);
    if (now[0] == rgb[0] && now[1] == rgb[1] && now[2] == rgb[2]) return;
    fn<void(__thiscall*)(void*, const float*)>(0x414E10)(static_cast<char*>(label) + 0xE8, rgb);
}
void setFill(void* params, const char* resref) {
    char name[16] = {};
    strncpy_s(name, resref, _TRUNCATE);
    if (!_strnicmp(static_cast<char*>(params) + 0x40, name, 16)) return;
    using Fill = void(__thiscall*)(void*, const void*, int);
    fn<Fill>(0x414C00)(params, name, 1);
}
void labelFill(void* label, const char* resref) { setFill(static_cast<char*>(label) + 0x70, resref); }
// A border with no picture: CSWGuiBorderParams::SetCornerImage (0x00414AE0) and
// SetEdgeImage (0x00414B70), `ret 8` both, as SetFillImage beside them; an empty name
// loads nothing.
void clearBorder(void* params) {
    const char none[16] = {};
    using Image = void(__thiscall*)(void*, const void*, int);
    fn<Image>(0x414AE0)(params, none, 1);
    fn<Image>(0x414B70)(params, none, 1);
    fn<Image>(0x414C00)(params, none, 1);
}
void selectable(void* c, bool on) { at<unsigned>(c, 0x44) = (at<unsigned>(c, 0x44) & ~8u) | (on ? 8u : 0u); }
int* rectOf(void* c) { return reinterpret_cast<int*>(static_cast<char*>(c) + 4); }
void place(void* c, int left, int top, int width, int height) {
    const int r[4] = {left, top, width > 1 ? width : 1, height > 1 ? height : 1};
    setExtentIfChanged(c, r);
}
int textWidth(void* label) { int lh = 0; return labelTextWidth(label, lh); }
void* rowGlyph(int row) { return owned[K1_LAYOUT_FIXED + row]; }
void* rowText(int row) { return owned[K1_LAYOUT_FIXED + K1_LAYOUT_ROWS + row]; }
void* deco(int i) { return owned[K1_LAYOUT_FIXED + 2 * K1_LAYOUT_ROWS + i]; }

// Which side of the drawing a row's caption is on: LAYOUT's L rows read towards the
// glyph from the left.
bool leftSide(int row) { return row <= 4; }

void __fastcall rowPressed(void*, void*, void*);
void __fastcall defaultsPressed(void*, void*, void*);
void __fastcall savePressed(void*, void*, void*);
void __fastcall discardPressed(void*, void*, void*);
void __fastcall cancelPressed(void*, void*, void*);
void __fastcall listenCancelPressed(void*, void*, void*);
void __fastcall changePressed(void*, void*, void*);

// Whether Default would change anything: the saved layout in the view (and in its box),
// the layout being changed while remapping.
bool canDefault() {
    const bool view = mode == Mode::View || mode == Mode::Default;
    return !(view ? KmrpRemapSavedK1() : editor.mapping).IsDefault();
}

// Made as the screen opens, before the file is let go (StopLoadFromLayout).
bool buildRemap(void* p) {
    rm = Remap{};
    std::memcpy(rm.cyan, static_cast<char*>(rowText(0)) + 0xE8 + 0x1C, sizeof rm.cyan);
    void* help = owned[9];
    void* backButton = owned[1];
    rm.backButton = backButton;
    std::memcpy(rm.help, rectOf(help), sizeof rm.help);
    std::memcpy(rm.back, rectOf(backButton), sizeof rm.back);
    std::memcpy(rm.backGlyph, rectOf(owned[K1_LAYOUT_BACK_GLYPH]), sizeof rm.backGlyph);
    for (int row = 0; row < K1_LAYOUT_ROWS; ++row) std::memcpy(rm.text[row], rectOf(rowText(row)), sizeof rm.text[row]);
    for (int b = 0; b < kRemapRows; ++b) {
        // The frame: a button with no picture of its own, whose focus draws the game's.
        void* frame = bindAppend(p, "BTN_BACK", true);
        if (!frame) return false;
        clearBorder(static_cast<char*>(frame) + 0x80);
        setText(frame, "", true);
        fn<Event>(0x41AB20)(frame, 0x27, p, reinterpret_cast<void*>(&rowPressed));
        rm.frame[b] = frame;
        rm.fixed[b] = bindAppend(p, "TEXT_05", false);
        rm.dot[b] = bindAppend(p, "GLYPH_BACK", false);
        if (!rm.fixed[b] || !rm.dot[b]) return false;
        labelFill(rm.dot[b], kDot);
        setColour(rm.fixed[b], kGrey);
    }
    void** locks[] = {&rm.lockMove, &rm.lockCamera, &rm.lockDpad, &rm.lockBack, &rm.lockStart};
    for (void** lock : locks) {
        *lock = bindAppend(p, "GLYPH_BACK", false);
        if (!*lock) return false;
        labelFill(*lock, kLock);
    }
    // Until 2026-10-21 A's part was a hint, a glyph and "Change button" between the
    // hairline and the buttons; it is a button now, first of four.
    rm.change = bindAppend(p, "BTN_BACK", true);
    rm.changeGlyph = bindAppend(p, "GLYPH_BACK", false);
    rm.defaults = bindAppend(p, "BTN_BACK", true);
    rm.defaultsGlyph = bindAppend(p, "GLYPH_BACK", false);
    rm.save = bindAppend(p, "BTN_BACK", true);
    rm.saveGlyph = bindAppend(p, "GLYPH_BACK", false);
    if (!rm.change || !rm.changeGlyph || !rm.defaults || !rm.defaultsGlyph || !rm.save || !rm.saveGlyph) return false;
    setText(rm.change, "Change", true);
    setText(rm.defaults, "Default", true);
    setText(rm.save, "Save", true);
    std::memcpy(rm.saveBorder, static_cast<char*>(rm.save) + 0x80 + 0x10, sizeof rm.saveBorder);
    fn<Event>(0x41AB20)(rm.defaults, 0x27, p, reinterpret_cast<void*>(&defaultsPressed));
    fn<Event>(0x41AB20)(rm.save, 0x27, p, reinterpret_cast<void*>(&savePressed));
    fn<Event>(0x41AB20)(rm.change, 0x27, p, reinterpret_cast<void*>(&changePressed));
    // The table, made before the prompts so that their dimmed box covers it. Names from
    // TEXT_05, a right-hand caption, so they read from the left; pictures from
    // GLYPH_BACK; the lines from DECO_04, the hairline under the heading.
    for (int i = 0; i < 2; ++i) {
        rm.head[i] = bindAppend(p, "TEXT_05", false);
        rm.line[i] = bindAppend(p, "DECO_04", false);
        if (!rm.head[i] || !rm.line[i]) return false;
        setColour(rm.head[i], kGrey);
    }
    setText(rm.head[0], "Action");
    setText(rm.head[1], "Button");
    for (int a = 0; a < kRemapRows; ++a) {
        rm.actionText[a] = bindAppend(p, "TEXT_05", false);
        rm.actionGlyph[a] = bindAppend(p, "GLYPH_BACK", false);
        if (!rm.actionText[a] || !rm.actionGlyph[a]) return false;
        setText(rm.actionText[a], kActionNames[a]);
    }
    for (int s = 0; s < kStayRows; ++s) {
        rm.stayText[s] = bindAppend(p, "TEXT_05", false);
        rm.stayGlyph[s] = bindAppend(p, "GLYPH_BACK", false);
        if (!rm.stayText[s] || !rm.stayGlyph[s]) return false;
        setText(rm.stayText[s], kStay[s].name);
    }
    // The prompt while a button is awaited, in the footer's place.
    rm.listenBox = bindAppend(p, "BTN_BACK", true);
    rm.listenTitle = bindAppend(p, "LBL_TITLE", false);
    rm.listenLine = bindAppend(p, "LBL_HELP", false);
    rm.listenGlyph = bindAppend(p, "GLYPH_BACK", false);
    rm.listenCancel = bindAppend(p, "BTN_BACK", true);
    // Leaving with something not saved: the screen dimmed, a box over it.
    rm.dim = bindAppend(p, "LBL_DIAGRAM", false);
    rm.unsavedBox = bindAppend(p, "BTN_BACK", true);
    rm.unsavedTitle = bindAppend(p, "LBL_TITLE", false);
    rm.unsavedLine1 = bindAppend(p, "LBL_HELP", false);
    rm.unsavedLine2 = bindAppend(p, "LBL_HELP", false);
    rm.discard = bindAppend(p, "BTN_BACK", true);
    rm.discardGlyph = bindAppend(p, "GLYPH_BACK", false);
    rm.cancel = bindAppend(p, "BTN_BACK", true);
    rm.cancelGlyph = bindAppend(p, "GLYPH_BACK", false);
    void* modal[] = {rm.listenBox, rm.listenTitle, rm.listenLine, rm.listenGlyph, rm.listenCancel, rm.dim,
                     rm.unsavedBox, rm.unsavedTitle, rm.unsavedLine1, rm.unsavedLine2,
                     rm.discard, rm.discardGlyph, rm.cancel, rm.cancelGlyph};
    for (void* c : modal) if (!c) return false;
    for (void* box : {rm.listenBox, rm.unsavedBox}) {
        setText(box, "", true);
        setFill(static_cast<char*>(box) + 0x80, kBlack);
        selectable(box, false);
    }
    setText(rm.listenLine, "If another action has that button, it is left without one");
    setText(rm.listenCancel, "Cancel", true);
    fn<Event>(0x41AB20)(rm.listenCancel, 0x27, p, reinterpret_cast<void*>(&listenCancelPressed));
    labelFill(rm.dim, kBlack);
    at<float>(rm.dim, 0x70 + 0x0C) = 0.7f;
    // The box's title, lines and first button are set as it is laid out (layoutRemap):
    // it asks one of two things.
    setText(rm.cancel, "Cancel", true);
    fn<Event>(0x41AB20)(rm.discard, 0x27, p, reinterpret_cast<void*>(&discardPressed));
    fn<Event>(0x41AB20)(rm.cancel, 0x27, p, reinterpret_cast<void*>(&cancelPressed));
    // Pad buttons, not places for the pad's focus; the mouse still clicks them.
    for (void* c : {backButton, rm.change, rm.defaults, rm.save, rm.discard, rm.cancel, rm.listenCancel}) KmrpPadFocusExcludeK1(c, true);
    rm.built = true;
    return true;
}

// The drawing, in the view (and under its Default box): each button's row, its caption
// from the glyph outwards, its frame, dot and padlock, the fixed rows grey, and the two
// captions above the diagram apart.
void layoutDrawing(void* focus, char family) {
    for (int b = 0; b < kRemapRows; ++b) {
        const int row = KmrpRemap::LayoutRow[b];
        void* const glyph = rowGlyph(row);
        void* const action = rowText(row);
        void* const fixed = rm.fixed[b];
        const int* g = rectOf(glyph);
        const int* t = rm.text[row];
        const int shown_action = editor.ActionInRow(b);
        const bool waiting = editor.Waiting(b);
        setText(action, shown_action >= 0 ? kActionNames[shown_action] : "");
        const char* fixedText = kFixedBefore[b][0] ? kFixedBefore[b] : kFixedAfter[b];
        setText(fixed, fixedText);
        showControl(fixed, fixedText[0] != 0);
        if (waiting) {
            labelFill(glyph, kAsk);
        } else {
            char resref[16] = {};
            sprintf_s(resref, "kmr%clyt%02d", family, row);
            labelFill(glyph, resref);
        }
        const bool faded = mode == Mode::Listen && b != listenRow;
        float dim[3], dimGrey[3];
        for (int i = 0; i < 3; ++i) { dim[i] = rm.cyan[i] * 0.4f; dimGrey[i] = kGrey[i] * 0.5f; }
        const bool focused = mode != Mode::View && focus == rm.frame[b];
        setColour(action, faded ? dim : waiting ? kOrange : focused ? kYellow : rm.cyan);
        setColour(fixed, faded ? dimGrey : kGrey);
        at<float>(glyph, 0x70 + 0x0C) = faded ? 0.35f : 1.0f;
        // The pieces of the caption on one line, from the glyph outwards: a measured
        // width each, so an action of any length sits beside what stays.
        const int gap = leftSide(row) ? g[0] - (t[0] + t[2]) : t[0] - (g[0] + g[2]);
        const int space = t[3] / 3;
        const int aw = textWidth(action) + 4, fw = fixedText[0] ? textWidth(fixed) + 4 : 0;
        const bool before = kFixedBefore[b][0] != 0;
        int pieces[2][2];            // left and width of the first and second piece
        const int total = aw + (fw ? fw + space : 0);
        const int start = leftSide(row) ? g[0] - gap - total : g[0] + g[2] + gap;
        void* first = before ? fixed : action;
        void* second = before ? action : fixed;
        const int w1 = before ? fw : aw, w2 = before ? aw : fw;
        pieces[0][0] = start; pieces[0][1] = w1;
        pieces[1][0] = start + w1 + (w1 && w2 ? space : 0); pieces[1][1] = w2;
        place(first, pieces[0][0], t[1], pieces[0][1], t[3]);
        if (w2) place(second, pieces[1][0], t[1], pieces[1][1], t[3]);
        // The frame round the glyph and the caption, a sixth of the glyph clear.
        const int pad = g[3] / 6;
        const int left = (std::min)(g[0], start) - pad, right = (std::max)(g[0] + g[2], start + total) + pad;
        place(rm.frame[b], left, g[1] - pad, right - left, g[3] + 2 * pad);
        // A changed button's dot, outside the frame at the row's outer end.
        const bool changed = shown_action >= 0 && shown_action != b && !waiting;
        const int dotSize = g[3] * 3 / 10;
        place(rm.dot[b], leftSide(row) ? left - pad - dotSize : right + pad, g[1] + (g[3] - dotSize) / 2, dotSize, dotSize);
        showControl(rm.dot[b], changed);
        // A stick's movement is fixed: its padlock at the row's outer end, beyond the dot.
        void* lock = b == KmrpRemap::L3 ? rm.lockMove : b == KmrpRemap::R3 ? rm.lockCamera : nullptr;
        if (lock) {
            const int size = g[3] * 11 / 20, beyond = changed ? dotSize + pad : 0;
            place(lock, leftSide(row) ? left - pad - beyond - size : right + pad + beyond, g[1] + (g[3] - size) / 2, size, size);
        }
    }
    // The rows that stay: grey, and padlocked.
    for (int row : {kRowBack, kRowDpad, kRowStart}) setColour(rowText(row), kGrey);
    {
        const int* g = rectOf(rowGlyph(kRowDpad));
        const int* t = rm.text[kRowDpad];
        const int size = g[3] * 11 / 20, pad = g[3] / 6;
        const int textLeft = t[0] + t[2] - textWidth(rowText(kRowDpad));
        place(rm.lockDpad, textLeft - pad - size, g[1] + (g[3] - size) / 2, size, size);
    }
    for (int row : {kRowBack, kRowStart}) {
        const int* g = rectOf(rowGlyph(row));
        const int size = g[3] * 9 / 20;
        place(row == kRowBack ? rm.lockBack : rm.lockStart, g[0] + (g[2] - size) / 2, g[1] + g[3] + g[3] / 10, size, size);
    }
    // Back's and Start's captions, each centred over its glyph above the diagram. Since
    // Start's became "Last menu / Close menu" (issue 49) their words meet: "Solo mode"
    // ran into "Last menu" at 3440x1440 (the maintainer's screenshot, 2026-10-21). They
    // are moved apart here, measured in the screen's own font: Start's only as far as
    // RT's glyph allows, Back's the rest, towards LT's. build_gui's separate_top does the
    // same in the file for the standalone patch's sets, whose boxes are then apart
    // already and do not move.
    {
        void* const backText = rowText(kRowBack);
        void* const startText = rowText(kRowStart);
        const int* bt = rm.text[kRowBack];
        const int* st = rm.text[kRowStart];
        const int bw = textWidth(backText), sw = textWidth(startText);
        const int bc = bt[0] + bt[2] / 2, sc = st[0] + st[2] / 2;
        const int gap = bt[3] * 12 / 26;           // TOP_CAPTION_GAP in TOP_CAPTION_H
        const int shortBy = (bw + sw) / 2 + gap - (sc - bc);
        int moveBack = 0, moveStart = 0;
        if (shortBy > 0) {
            const int* lt = rectOf(rowGlyph(KmrpRemap::LayoutRow[KmrpRemap::LT]));
            const int* rt = rectOf(rowGlyph(KmrpRemap::LayoutRow[KmrpRemap::RT]));
            const int roomLeft = (std::max)(0, bc - bw / 2 - (lt[0] + lt[2] + gap));
            const int roomRight = (std::max)(0, rt[0] - gap - (sc + sw / 2));
            moveStart = (std::min)(roomRight, shortBy / 2);
            moveBack = (std::min)(roomLeft, shortBy - moveStart);
            moveStart = (std::min)(roomRight, shortBy - moveBack);
        }
        place(backText, bt[0] - moveBack, bt[1], bt[2], bt[3]);
        place(startText, st[0] + moveStart, st[1], st[2], st[3]);
    }
}

// The table, while remapping (2026-10-21), in the drawing's place: between the
// heading's hairline and the help line, centred on the screen as the footer is. A row
// is as tall as a one-line caption box (TOP_CAPTION_H, the file's) where there is room,
// less on short screens, since the heads, the ten actions, the five that stay and half
// a row between them must fit. Pictures are square, four fifths of a row; the dot and
// the padlock follow the picture at the drawing's proportions of it. The name column is
// as wide as the widest name, measured in the screen's own font.
void layoutTable(void* focus, char family) {
    const int* headLine = rectOf(deco(4));
    const int helpH = rm.help[3];
    const int boxH = rm.text[kRowBack][3];
    const int top = headLine[1] + headLine[3] + helpH / 2;
    const int bottom = rectOf(deco(5))[1] - helpH - helpH / 4 - helpH / 2;
    const int rows2 = 2 * (1 + kRemapRows + kStayRows) + 1;     // in half rows
    const int rowH = (std::max)(1, (std::min)(boxH, (bottom - top) * 2 / rows2));
    const int pic = rowH * 4 / 5, dot = pic * 3 / 10, lock = pic * 11 / 20;
    const int pad = rowH / 2, colGap = rowH * 2;
    int nameW = textWidth(rm.head[0]);
    for (void* t : rm.actionText) nameW = (std::max)(nameW, textWidth(t));
    for (void* t : rm.stayText) nameW = (std::max)(nameW, textWidth(t));
    nameW += 4;
    const int buttonW = (std::max)(textWidth(rm.head[1]) + 4, pic + pad + (std::max)(dot, lock));
    const int width = pad + nameW + colGap + buttonW + pad;
    const int height = rowH * rows2 / 2;
    const int left = rm.back[0] + rm.back[2] / 2 - width / 2;
    const int tableTop = top + ((bottom - top) - height) / 2;
    const int nameX = left + pad, buttonX = nameX + nameW + colGap;
    const int lineH = (std::max)(1, headLine[3]);
    auto name = [&](void* c, int x, int w, int y) { place(c, x, y + (rowH - boxH) / 2, w, boxH); };
    auto picture = [&](void* c, int y) { place(c, buttonX, y + (rowH - pic) / 2, pic, pic); };
    name(rm.head[0], nameX, nameW, tableTop);
    name(rm.head[1], buttonX, buttonW, tableTop);
    place(rm.line[0], left, tableTop + rowH - lineH / 2, width, lineH);
    // While a button is awaited every other row fades, as the drawing's rows did.
    float dim[3], dimGrey[3];
    for (int i = 0; i < 3; ++i) { dim[i] = rm.cyan[i] * 0.4f; dimGrey[i] = kGrey[i] * 0.5f; }
    const bool listening = mode == Mode::Listen;
    for (int a = 0; a < kRemapRows; ++a) {
        const int y = tableTop + rowH * (1 + a);
        const int button = editor.mapping.button[a];
        const bool none = button < 0 || button >= kRemapRows;
        const bool faded = listening && a != listenRow;
        place(rm.frame[a], left, y, width, rowH);
        name(rm.actionText[a], nameX, nameW, y);
        setColour(rm.actionText[a], faded ? dim : none ? kOrange : focus == rm.frame[a] ? kYellow : rm.cyan);
        if (none) {
            labelFill(rm.actionGlyph[a], kAsk);
        } else {
            char resref[16] = {};
            sprintf_s(resref, "kmr%crm%s", family, KmrpRemap::GlyphCodes[button]);
            labelFill(rm.actionGlyph[a], resref);
        }
        picture(rm.actionGlyph[a], y);
        at<float>(rm.actionGlyph[a], 0x70 + 0x0C) = faded ? 0.35f : 1.0f;
        place(rm.dot[a], buttonX + pic + pad, y + (rowH - dot) / 2, dot, dot);
        showControl(rm.dot[a], !none && button != a);
    }
    // The rows that stay, under a line half a row down: grey, each with its padlock.
    const int stayTop = tableTop + rowH * (1 + kRemapRows) + rowH / 2;
    place(rm.line[1], left, stayTop - rowH / 4 - lineH / 2, width, lineH);
    void* const locks[kStayRows] = {rm.lockMove, rm.lockCamera, rm.lockDpad, rm.lockStart, rm.lockBack};
    for (int s = 0; s < kStayRows; ++s) {
        const int y = stayTop + rowH * s;
        name(rm.stayText[s], nameX, nameW, y);
        setColour(rm.stayText[s], listening ? dimGrey : kGrey);
        char resref[16] = {};
        sprintf_s(resref, "kmr%clyt%02d", family, kStay[s].row);
        labelFill(rm.stayGlyph[s], resref);
        picture(rm.stayGlyph[s], y);
        at<float>(rm.stayGlyph[s], 0x70 + 0x0C) = listening ? 0.35f : 1.0f;
        place(locks[s], buttonX + pic + pad, y + (rowH - lock) / 2, lock, lock);
    }
}

// Where everything goes, and what it says, for the layout being edited and the focus.
void layoutRemap() {
    if (!rm.built || !current) return;
    void* const focus = at<void*>(current, 0x1C);
    const char family = KmrpGlyphLetterK1();
    // The table while remapping (and under its Unsaved Changes box), the drawing in the
    // view and under its Default box. Each hides the other's controls.
    const bool table = mode == Mode::Browse || mode == Mode::Listen || mode == Mode::Unsaved;
    showControl(owned[8], !table);                 // LBL_DIAGRAM, the drawing and its lines
    for (int row = 0; row < K1_LAYOUT_ROWS; ++row) {
        showControl(rowGlyph(row), !table);
        showControl(rowText(row), !table);
    }
    for (void* c : rm.head) showControl(c, table);
    for (void* c : rm.line) showControl(c, table);
    for (int a = 0; a < kRemapRows; ++a) {
        showControl(rm.actionText[a], table);
        showControl(rm.actionGlyph[a], table);
    }
    for (int s = 0; s < kStayRows; ++s) {
        showControl(rm.stayText[s], table);
        showControl(rm.stayGlyph[s], table);
    }
    if (table) {
        for (void* c : rm.fixed) showControl(c, false);
        layoutTable(focus, family);
    } else {
        layoutDrawing(focus, family);
    }
    // The footer: what A does, between the line and the buttons, and Default, Save (Remap
    // in the view) and Back, each with its pad button. The help line above the line.
    void* const help = owned[9];
    void* const line = deco(5);
    const int* l = rectOf(line);
    const int helpH = rm.help[3];
    place(help, rm.help[0], l[1] - helpH - helpH / 4, rm.help[2], helpH);
    const bool complete = editor.Complete();
    const bool padHere = KmrpPadPresentK1();
    if (!table && !padHere) {
        // Remap needs a pad (2026-10-21): the view says so while none answers.
        setText(help, "Connect a controller to remap its buttons.");
        setColour(help, kOrange);
    } else if (complete) {
        setText(help, table ? "A dot marks a changed button.   The grey rows stay as they are, and menus keep every button."
                            : "A dot marks a changed button.   A lock stays as it is: moving, the camera, the D-pad, Start and Back.");
        setColour(help, rm.cyan);
    } else {
        int missing = KmrpRemap::None;
        for (int a = 0; a < kRemapRows && missing < 0; ++a)
            if (editor.mapping.button[a] < 0) missing = a;
        char text[160];
        sprintf_s(text, "%s has no button.   Every action needs one before you can save.",
                  missing >= 0 ? kActionNames[missing] : "An action");
        setText(help, text);
        setColour(help, kOrange);
    }
    const int bh = rm.back[3];
    const int middle = rm.back[0] + rm.back[2] / 2;
    const int gx = rm.backGlyph[0] - rm.back[0], gy = rm.backGlyph[1] - rm.back[1], gs = rm.backGlyph[2];
    void* const backButton = owned[1];
    void* const backGlyph = owned[K1_LAYOUT_BACK_GLYPH];
    // Default's box is the view's: the footer under it keeps the view's buttons.
    const bool view = mode == Mode::View || mode == Mode::Default;
    setText(rm.save, view ? "Remap" : "Save", true);
    setText(backButton, view ? "Back" : "Close", true);
    // The footer's buttons, one size in both states: as wide as the longest label
    // centred clear of the glyph, never wider than the file's Back, and narrower again
    // where four would not fit across the screen. Four while remapping, (A) Change first
    // (the maintainer, 2026-10-21: "the A change button should be a button in the bottom
    // as well ... make them smaller so they fit"); the view's three; each row centred
    // where the file's Back was. Until that day every button was Back's width and the
    // centres 1.4 widths apart.
    int labelW = 0;
    for (void* b : {rm.change, rm.defaults, rm.save, backButton}) labelW = (std::max)(labelW, buttonTextWidth(b));
    const int clear = gx + gs + gs / 2;               // the edge to the glyph's far side, and a half glyph more
    int fw = labelW > 0 ? (std::min)(rm.back[2], labelW + 2 * clear) : rm.back[2] * 4 / 5;
    int gap = fw / 4;
    const int room = rectOf(current)[2] - 2 * gs;
    if (4 * fw + 3 * gap > room) gap = (std::max)(gs / 2, (room - 4 * fw) / 3);
    if (4 * fw + 3 * gap > room) fw = (std::max)(2 * clear, (room - 3 * gap) / 4);
    const int span4 = 4 * fw + 3 * gap;
    const int count = view ? 3 : 4;
    const int first = middle - (count * fw + (count - 1) * gap) / 2;
    struct { void* button; void* glyph; const char* code; } footer[4] = {
        {rm.change, rm.changeGlyph, "a"}, {rm.defaults, rm.defaultsGlyph, "y"},
        {rm.save, rm.saveGlyph, "x"}, {backButton, backGlyph, nullptr}};
    for (int i = view ? 1 : 0, slot = 0; i < 4; ++i, ++slot) {
        const int x = first + slot * (fw + gap);
        place(footer[i].button, x, rm.back[1], fw, bh);
        place(footer[i].glyph, x + gx, rm.back[1] + gy, gs, gs);
        if (footer[i].code) {
            char resref[16] = {};
            sprintf_s(resref, "kmr%crm%s", family, footer[i].code);
            labelFill(footer[i].glyph, resref);
        }
    }
    // Save while the layout cannot be saved, Remap while no pad answers, and Default
    // while the layout already is the default: grey, the glyph faint.
    {
        const bool can[2] = {view ? padHere : complete, canDefault()};
        void* const button[2] = {rm.save, rm.defaults};
        void* const glyph[2] = {rm.saveGlyph, rm.defaultsGlyph};
        for (int i = 0; i < 2; ++i) {
            float* border = reinterpret_cast<float*>(static_cast<char*>(button[i]) + 0x80 + 0x10);
            std::memcpy(border, can[i] ? rm.saveBorder : kGrey, sizeof rm.saveBorder);
            at<float>(glyph[i], 0x70 + 0x0C) = can[i] ? 1.0f : 0.35f;
            fn<void(__thiscall*)(void*, const float*)>(0x414E10)(static_cast<char*>(button[i]) + 0x16C,
                                                                 can[i] ? rm.cyan : kGrey);
        }
    }
    // The prompt, in the help line's and the footer's place, as wide as the four
    // buttons (the three of Back's width until 2026-10-21): what to press, what happens
    // to the button's action, and how to cancel, one under the other, the box round them.
    {
        const int left = middle - span4 / 2, width = span4;
        const int titleH = rectOf(owned[0])[3];
        const int pad = helpH / 2;
        const int height = pad + titleH + helpH / 4 + helpH + pad + bh + pad;
        const int bottom = rm.back[1] + bh;
        const int top = bottom - height;
        place(rm.listenBox, left, top, width, height);
        place(rm.listenTitle, left, top + pad, width, titleH);
        char text[96];
        // The table's rows are actions: the row awaiting a button is its action.
        const int a = listenRow;
        sprintf_s(text, "Press the new button for %s", a >= 0 && a < kRemapRows ? kActionNames[a] : "this action");
        setText(rm.listenTitle, text);
        place(rm.listenLine, left, top + pad + titleH + helpH / 4, width, helpH);
        char resref[16] = {};
        sprintf_s(resref, "kmr%clyt%02d", family, kRowBack);
        labelFill(rm.listenGlyph, resref);
        const int by = top + height - pad - bh;
        place(rm.listenCancel, middle - fw / 2, by, fw, bh);
        place(rm.listenGlyph, middle - fw / 2 + gx, by + gy, gs, gs);
    }
    // Unsaved changes: the screen dimmed, a box in its middle, its two buttons Back's
    // width as the file has it.
    {
        const int bw = rm.back[2];
        const int* panel = rectOf(current);
        place(rm.dim, 0, 0, panel[2], panel[3]);
        const int titleH = rectOf(owned[0])[3];
        const int width = 3 * bw + bw / 4, height = titleH * 2 + helpH * 3 + bh + bh / 2;
        const int left = panel[2] / 2 - width / 2, top = panel[3] / 2 - height / 2;
        place(rm.unsavedBox, left, top, width, height);
        place(rm.unsavedTitle, left, top + titleH / 2, width, titleH);
        place(rm.unsavedLine1, left, top + titleH * 2, width, helpH);
        place(rm.unsavedLine2, left, top + titleH * 2 + helpH + helpH / 4, width, helpH);
        const int by = top + height - bh - bh / 2;
        place(rm.discard, panel[2] / 2 - bw / 4 - bw, by, bw, bh);
        place(rm.cancel, panel[2] / 2 + bw / 4, by, bw, bh);
        place(rm.discardGlyph, panel[2] / 2 - bw / 4 - bw + gx, by + gy, gs, gs);
        place(rm.cancelGlyph, panel[2] / 2 + bw / 4 + gx, by + gy, gs, gs);
        char resref[16] = {};
        sprintf_s(resref, "kmr%crma", family);
        labelFill(rm.discardGlyph, resref);
        sprintf_s(resref, "kmr%crmb", family);
        labelFill(rm.cancelGlyph, resref);
        // The same box asks before the view's Default replaces the saved layout.
        const bool asking = mode == Mode::Default;
        setText(rm.unsavedTitle, asking ? "Default Layout" : "Unsaved Changes");
        setText(rm.unsavedLine1, asking ? "Every action goes back to its Xbox button."
                                        : "You have not saved your new controller layout.");
        setText(rm.unsavedLine2, asking ? "Replace your saved layout?" : "Discard your changes?");
        setText(rm.discard, asking ? "Default" : "Discard", true);
    }
    // What shows in each state. The box is up for Unsaved and for Default.
    const bool browse = mode == Mode::Browse, listen = mode == Mode::Listen;
    const bool unsaved = mode == Mode::Unsaved || mode == Mode::Default;
    const bool pad = IsControllerInputActiveK1();
    for (void* c : {help, rm.save, backButton, rm.defaults}) showControl(c, !listen);
    for (void* c : {rm.saveGlyph, backGlyph, rm.defaultsGlyph}) showControl(c, !listen && pad);
    showControl(rm.change, !listen && !view);
    showControl(rm.changeGlyph, !listen && !view && pad);
    showControl(rm.discardGlyph, unsaved && pad);
    showControl(rm.cancelGlyph, unsaved && pad);
    for (void* c : {rm.listenBox, rm.listenTitle, rm.listenLine, rm.listenCancel}) showControl(c, listen);
    showControl(rm.listenGlyph, listen && pad);
    for (void* c : {rm.dim, rm.unsavedBox, rm.unsavedTitle, rm.unsavedLine1, rm.unsavedLine2, rm.discard, rm.cancel})
        showControl(c, unsaved);
    // While a button is awaited the focus stays on its row; the rows are not places to go.
    for (int b = 0; b < kRemapRows; ++b) selectable(rm.frame[b], browse);
    for (int b = 0; b < kRemapRows; ++b) if (focus == rm.frame[b]) browseRow = b;
    if (browse && focus && !(at<unsigned>(focus, 0x44) & 2u)) {
        fn<SetActive>(0x40A630)(current, rm.frame[browseRow], 0);
        remapDirty = true;            // laid out again next frame, with the focus on its row
    }
    remapFamily = family;
    remapFocus = focus;
    remapPad = pad;
    remapPadHere = padHere;
    remapDirty = false;
}

void startListening(int row) {
    if (mode != Mode::Browse || row < 0 || row >= kRemapRows) return;
    mode = Mode::Listen;
    listenRow = row;
    listenSeen = KmrpPadButtonsK1();          // what is already held does not count
    remapDirty = true;
    log("remap-listen");
}
// After a choice, or a cancel: nothing more until every button is up again, so the
// press that chose cannot also act on the screen.
void endListening() {
    mode = Mode::Browse;
    listenRow = -1;
    settle = true;
    remapDirty = true;
}
// Remap: the rows become places for the focus, from the row it was last on. The press
// that chose it is let go before anything else counts.
void enterRemap() {
    // Only with a pad (2026-10-21): the keyboard and the mouse cannot choose a button.
    if (mode != Mode::View || !current || !KmrpPadPresentK1()) return;
    editor = KmrpRemap::Editor(KmrpRemapSavedK1());
    mode = Mode::Browse;
    settle = true;
    remapDirty = true;
    selectable(rm.frame[browseRow], true);
    fn<SetActive>(0x40A630)(current, rm.frame[browseRow], 0);
    log("remap-enter");
}
// Back to the layout as saved: anything not saved is dropped, and the focus is nowhere,
// since nothing in View is a place for it.
void exitRemap() {
    if (!current) return;
    editor = KmrpRemap::Editor(KmrpRemapSavedK1());
    mode = Mode::View;
    settle = true;
    remapDirty = true;
    fn<SetActive>(0x40A630)(current, nullptr, 0);
    log("remap-exit");
}
// Close while remapping: back to View, asking first if something is not saved.
void leave() {
    if (editor.mapping != KmrpRemapSavedK1()) { mode = Mode::Unsaved; remapDirty = true; log("remap-unsaved"); return; }
    exitRemap();
}
void defaults() { editor.Reset(); remapDirty = true; }
// The view's Default: it replaces the saved layout, so the box asks first.
void askDefault() {
    if (mode != Mode::View || !canDefault()) return;
    mode = Mode::Default;
    remapDirty = true;
    log("remap-default-ask");
}
void useDefault() {
    if (mode != Mode::Default) return;
    if (KmrpRemapSaveK1(KmrpRemap::Mapping{})) log("remap-default-saved");
    editor = KmrpRemap::Editor(KmrpRemapSavedK1());
    mode = Mode::View;
    settle = true;
    remapDirty = true;
}
void saveLayout() {
    if (!editor.Complete()) return;
    if (KmrpRemapSaveK1(editor.mapping)) log("remap-saved");
    remapDirty = true;
}

void __fastcall rowPressed(void*, void*, void*) {
    ++callbacks;
    if (!armed() || settle || mode != Mode::Browse || !current) return;
    void* const focus = at<void*>(current, 0x1C);
    for (int b = 0; b < kRemapRows; ++b) if (rm.frame[b] == focus) startListening(b);
}
void __fastcall defaultsPressed(void*, void*, void*) {
    ++callbacks;
    if (!armed() || settle) return;
    if (mode == Mode::Browse) defaults();
    else if (mode == Mode::View) askDefault();
}
void __fastcall savePressed(void*, void*, void*) {
    ++callbacks;
    if (!armed() || settle) return;
    if (mode == Mode::View) enterRemap();
    else if (mode == Mode::Browse) saveLayout();
}
void __fastcall discardPressed(void*, void*, void*) {
    ++callbacks;
    if (!armed()) return;
    if (mode == Mode::Unsaved) exitRemap();
    else if (mode == Mode::Default) useDefault();
}
void __fastcall cancelPressed(void*, void*, void*) {
    ++callbacks;
    if (!armed()) return;
    if (mode == Mode::Unsaved) { mode = Mode::Browse; remapDirty = true; }
    else if (mode == Mode::Default) { mode = Mode::View; remapDirty = true; }
}
void __fastcall listenCancelPressed(void*, void*, void*) { ++callbacks; if (armed() && mode == Mode::Listen) endListening(); }
// (A) Change in the footer: what A on the focused row does, for the mouse as well.
void __fastcall changePressed(void*, void*, void*) {
    ++callbacks;
    if (armed() && !settle && mode == Mode::Browse) startListening(browseRow);
}

// Every GUI frame while the screen is open: the button awaited, and the layout.
void remapFrame() {
    if (!rm.built || !current) return;
    const std::uint16_t pad = KmrpPadButtonsK1();
    if (settle && (pad & (KmrpRemap::RemappableBits | 0x0030)) == 0 && !ControllerConfirmHeldK1()) settle = false;
    if (mode == Mode::Listen) {
        const std::uint16_t pressed = static_cast<std::uint16_t>(pad & ~listenSeen);
        listenSeen = pad;
        if (pressed & 0x0020) {                    // Back: cancel
            endListening();
        } else {
            for (int b = 0; b < kRemapRows; ++b) {
                if (!(pressed & KmrpRemap::Mask[b])) continue;
                // The row's action gets the button; the action that had it has none.
                editor.mapping.Assign(listenRow, b);
                log("remap-assigned");
                endListening();
                break;
            }
        }
    }
    if (remapDirty || at<void*>(current, 0x1C) != remapFocus || KmrpGlyphLetterK1() != remapFamily ||
        IsControllerInputActiveK1() != remapPad || KmrpPadPresentK1() != remapPadHere)
        layoutRemap();
}

unsigned frameNumber = 0, backFrame = ~0u;
void cancelWaiting() {
    if (rm.built && mode == Mode::Listen) {
        endListening();
        backFrame = frameNumber;          // this Escape is spent
    }
}
// B, Escape, Start (which sends B over a menu), or Back clicked: once per frame, since
// the panel's own B and its input can both be told of one press.
void handleBack() {
    if (backFrame == frameNumber) return;
    backFrame = frameNumber;
    if (!rm.built) { requestClose(); return; }
    if (settle) return;
    if (mode == Mode::View) { requestClose(); return; }
    if (mode == Mode::Unsaved) { mode = Mode::Browse; remapDirty = true; return; }
    if (mode == Mode::Default) { mode = Mode::View; remapDirty = true; return; }
    if (mode == Mode::Listen) return;            // Back cancels there, read from the pad
    leave();
}
// The screen's own buttons, by position as every menu has them. View: Y asks to put
// back the default, X remaps (only while a pad answers), B leaves; A does nothing. Remapping: A asks for a row's
// button (the row's own event), Y puts back the default, X saves, B closes remapping.
// Either box: A for its first button, B to cancel. Waiting for a button and just after
// a choice, every event is swallowed.
bool remapInput(int event, int value) {
    if (!rm.built) return false;
    if (mode == Mode::Listen) {
        // B from the keyboard (Escape) cancels; the pad's B may be the button chosen,
        // and is read from the pad (remapFrame). They are the same event here, so the
        // pad says which it was: its B is down for its own press.
        if (event == 0x28 && value && !(KmrpPadButtonsK1() & KmrpRemap::Mask[KmrpRemap::B])) endListening();
        return true;
    }
    if (settle) return true;
    if (mode == Mode::Unsaved || mode == Mode::Default) {
        if (value && armed()) {
            if (event == 0x27) {
                if (mode == Mode::Unsaved) exitRemap();
                else useDefault();
            } else if (event == 0x28) {
                handleBack();
            }
        }
        return true;
    }
    if (mode == Mode::View) {
        if (event == 0x28) { if (value) handleBack(); return true; }
        if (event == 0x29) { if (value && armed()) enterRemap(); return true; }
        if (event == 0x2A) { if (value && armed()) askDefault(); return true; }
        return event == 0x27;
    }
    if (event == 0x28) { if (value) handleBack(); return true; }
    if (event == 0x29) { if (value && armed()) saveLayout(); return true; }
    if (event == 0x2A) { if (value && armed()) defaults(); return true; }
    return false;
}
void forgetRemap() {
    // Their addresses, not their controls: called after the controls are freed too.
    for (void* c : {rm.backButton, rm.change, rm.defaults, rm.save, rm.discard, rm.cancel, rm.listenCancel})
        if (c) KmrpPadFocusExcludeK1(c, false);
    rm = Remap{};
    mode = Mode::View;
    listenRow = -1;
    browseRow = 0;
    settle = false;
    remapDirty = true;
    remapFocus = nullptr;
}

void refresh() {
    char next=KmrpGlyphLetterK1();
    int active=IsControllerInputActiveK1()?1:0;
    if (next==family && active==device) return;
    family=next; device=active;
    // IDs 2..5 are family headings; 6 and 7 indicate active input device.
    auto array=at<void**>(current,0x20);
    for (int i=2;i<8;++i) if (array[i]) {
        bool visible=i<6 ? "psnd"[i-2]==family : i==6+active;
        at<unsigned>(array[i],0x44)=(at<unsigned>(array[i],0x44)&~2u)|(visible?2u:0);
    }
    using Fill=void(__thiscall*)(void*,const void*,int);
    // The diagram, ID 8, is drawn per family too: the silhouette and its
    // face-button glyphs are baked into kmr?lytdiag.
    if (array[8]) {
        char resref[16]={};
        sprintf_s(resref,"kmr%clytdiag",family);
        fn<Fill>(0x414C00)(static_cast<char*>(array[8])+0x70,resref,1);
    }
    // The B inside Back: the pad's own glyph, and only while a pad is in use.
    if (void* backGlyph=array[K1_LAYOUT_BACK_GLYPH]) {
        char resref[16]={};
        sprintf_s(resref,"kmr%clytbk",family);
        fn<Fill>(0x414C00)(static_cast<char*>(backGlyph)+0x70,resref,1);
        at<unsigned>(backGlyph,0x44)=(at<unsigned>(backGlyph,0x44)&~2u)|(active?2u:0);
    }
    // Glyph controls follow the fixed ten, and use the same family resrefs as HUD.
    for (int i=0;i<K1_LAYOUT_ROWS;++i) {
        void* glyph=array[K1_LAYOUT_FIXED+i];
        if (!glyph) continue;
        char resref[16]={};
        sprintf_s(resref,"kmr%clyt%02d",family,i);
        fn<Fill>(0x414C00)(static_cast<char*>(glyph)+0x70,resref,1);
    }
    remapDirty = true;            // the rows' glyphs and the footer's are the remap screen's again
    log("refresh");
}
}

void ControllerLayoutReleaseGffK1(void* panel) {
    if (!panel) return;
    auto v=at<std::uintptr_t>(panel,0);
    if (v==0x73E010 && !at<void*>(panel,0x2C)) {
        // Base destructor resets the vtable, then calls ReleaseGff before
        // disposing of the pointer array. This is an existing verified hook.
        for (auto& e: entries) if (e.parent==panel) {
            if (pending==panel) pending=nullptr;
            if (parent==panel) { parent=nullptr; returnFocus=nullptr; requestClose(); }
            auto array=at<void**>(panel,0x20);
            int id=at<int>(e.button,0x50);
            if (array && id>=0 && id<at<int>(panel,0x24)) array[id]=nullptr;
            destroyControl(e.button); e={}; log("entry-destroy");
        }
        for (auto& b: confirmBadges) if (b.panel==panel) {
            auto array=at<void**>(panel,0x20);
            int id=at<int>(b.label,0x50);
            if (array && id>=0 && id<at<int>(panel,0x24)) array[id]=nullptr;
            destroyControl(b.label); b={};
        }
        for (auto& b: dialogBadges) if (b.panel==panel) {
            auto array=at<void**>(panel,0x20);
            int id=at<int>(b.label,0x50);
            if (array && id>=0 && id<at<int>(panel,0x24)) array[id]=nullptr;
            destroyControl(b.label); b={};
        }
        for (auto& b: summaryBadges) if (b.panel==panel) {
            auto array=at<void**>(panel,0x20);
            int id=at<int>(b.label,0x50);
            if (array && id>=0 && id<at<int>(panel,0x24)) array[id]=nullptr;
            destroyControl(b.label); b={};
        }
        return;
    }
    if (v==K1_STATUS_SUMMARY_VTABLE && at<void*>(panel,0x2C)) {
        for (const auto& b: summaryBadges) if (b.panel==panel) return;
        for (auto& b: summaryBadges) if (!b.panel) {
            void* c=bindExtraLabel(panel,"LBL_JOURNAL");
            if (!c) return;                // no such tag, or no free slot
            showControl(c,false);
            b={panel,c,0,false};
            log("summary-badge-bound");
            return;
        }
        return;
    }
    if (v==K1_DIALOG_VTABLE && at<void*>(panel,0x2C)) {
        for (const auto& b: dialogBadges) if (b.panel==panel) return;
        for (auto& b: dialogBadges) if (!b.panel) {
            void* c=bind(panel,"LBL_KMRPDLG");
            if (!c) return;                // a dialog.gui without the label
            showControl(c,false);
            b={panel,c,0,false,0};
            log("dialog-badge-bound");
            return;
        }
        return;
    }
    if ((v==K1_MESSAGE_BOX_VTABLE || v==K1_SOLO_MODE_QUERY_VTABLE) &&
        at<void*>(panel,0x2C)) {
        for (const auto& b: confirmBadges) if (b.panel==panel) return;
        for (auto& b: confirmBadges) if (!b.panel) {
            void* c=bind(panel,"LBL_KMRPA");
            if (!c) return;                // an older confirm.gui: no badge
            showControl(c,false);
            b={panel,c,0,false};
            return;
        }
        return;
    }
    // The Gameplay screen, CSWGuiOptionsGameplay, where the entry sits under
    // Keymapping. Keeping this to one parent avoids two entry points with
    // subtly different return-focus behaviour. It was CSWGuiOptionsMouse
    // (0x7585F8) until 2026-09-21; Options does not list Mouse at all, so that
    // put the entry two screens deep where nobody found it.
    if (v!=0x758E00 || !at<void*>(panel,0x2C)) return;
    for (const auto& e:entries) if (e.parent==panel) return;
    for (auto& e:entries) if (!e.parent) {
        void* c=bind(panel,"BTN_KMRPLAY",true);
        if (!c) return;
        // Under Keymapping, one step of the column below it, measured on the live
        // buttons. The layout file says the same for the screen as it was made, but
        // another patch may have rescaled the screen before this button existed
        // (Scaled Kotor does, as the layout finishes loading: at 3440x1440 the
        // button stood at the file's place, small, over the first rows; the
        // maintainer saw it, 2026-10-05). optgameplay.gui: BTN_KEYMAP is ID 12,
        // BTN_MOUSE ID 13, in the game's file and in ours.
        {
            struct Rect { int left, top, width, height; };
            auto array=at<void**>(panel,0x20);
            const int count=at<int>(panel,0x24);
            void* keymap=array && count>13 ? array[12] : nullptr;
            void* mouse=array && count>13 ? array[13] : nullptr;
            if (keymap && mouse && keymap!=c && mouse!=c &&
                at<std::uintptr_t>(keymap,0)==at<std::uintptr_t>(c,0) &&
                at<std::uintptr_t>(mouse,0)==at<std::uintptr_t>(c,0)) {
                const Rect k=at<Rect>(keymap,4), m=at<Rect>(mouse,4);
                const int step=k.top-m.top;
                if (step>0 && k.width>0 && k.height>0 && k.left==m.left) {
                    const Rect wanted{k.left,k.top+step,k.width,k.height};
                    using SetExtent=void(__thiscall*)(void*,const Rect*);
                    reinterpret_cast<SetExtent>(at<void**>(c,0)[1])(c,&wanted);
                }
            }
        }
        fn<Event>(0x41AB20)(c,0x27,panel,reinterpret_cast<void*>(&open));
        e={panel,c,false,0}; log("entry-create"); return;
    }
}

// The tag of the screen's i-th control, in the order of `owned`.
void layoutTag(int i, char (&tag)[24]) {
    static const char* const fixed[]={"LBL_TITLE","BTN_BACK","LBL_XBOX","LBL_PS","LBL_SWITCH","LBL_DECK","LBL_KBM","LBL_PAD","LBL_DIAGRAM","LBL_HELP"};
    const int row=i-K1_LAYOUT_FIXED;
    memset(tag,0,sizeof tag);
    if (i<K1_LAYOUT_FIXED) strcpy_s(tag,fixed[i]);
    else if (row<K1_LAYOUT_ROWS) sprintf_s(tag,"GLYPH_%02d",row);
    else if (row<2*K1_LAYOUT_ROWS) sprintf_s(tag,"TEXT_%02d",row-K1_LAYOUT_ROWS);
    else if (i==K1_LAYOUT_BACK_GLYPH) strcpy_s(tag,"GLYPH_BACK");
    else sprintf_s(tag,"DECO_%02d",row-2*K1_LAYOUT_ROWS);
}

// The screen's pictures drawn in the background before it is opened (2026-10-27, the
// maintainer: as the game starts, and right after the resolution changes, without delaying
// the change). Their sizes are what the layout file the game loads now gives them, so the
// screen is made as it is when opened, kmrplayout loaded and every control bound, but never
// added to the manager or shown; each control's picture is queued, and the copy taken apart
// as destroy() takes the screen apart. A few milliseconds on the game thread; the drawing is
// on the patch's own (vendor/K1XboxControls.cpp, K1BackgroundWorker). Done again only for
// another size, and tried again later when the layout file is not there yet.
//
// When, by events and not by time (the maintainer, 2026-10-28: after the last thing the
// resolution change draws, not after a delay): when the size changes, the screens up are
// noted; once the game has made them again for the new size (the panels up, or their
// sizes, differ) and they have held for a frame, and a whole frame has gone by in which the
// patch drew no badge or picture (KmrpPicturesSettledK1), the copy is made. As the game
// starts, from the first such frame with a screen up. The first rule, 15 frames after the
// size changed, came one frame after the switch finished, while the game was making its
// screens again, and the maintainer then found Options' pad focus stuck and a small badge
// under its last button (2560x1440 from 3440x1440). Whether the copy caused that is not
// known: layout-predraw=0 in configs\kmrp-controller.ini turns it off, to tell.
enum class Predraw { Start, Rebuild, Drawn, Done };
Predraw predraw=Predraw::Start;
int seenWidth=0, seenHeight=0;
unsigned long long panelsAtChange=0, panelsLastFrame=0;

// The screens up, as one number: each panel and its size.
unsigned long long panelSignature(void* manager, int& count) {
    auto panels=at<void**>(manager,0x88);              // MANAGER_PANEL_LIST_OFFSET
    count=at<int>(manager,0x8C);                        // MANAGER_PANEL_COUNT_OFFSET
    if (!panels || count<0 || count>64) { count=0; return 0; }
    unsigned long long h=1469598103934665603ull;
    for (int i=0;i<count;++i) {
        void* p=panels[i];
        const unsigned long long parts[3]={reinterpret_cast<std::uintptr_t>(p),
            p ? static_cast<unsigned>(at<int>(p,0x0C)) : 0u, p ? static_cast<unsigned>(at<int>(p,0x10)) : 0u};
        for (unsigned long long v:parts) h=(h^v)*1099511628211ull;
    }
    return h;
}

void probeLayoutPictures(void* manager) {
    static const bool enabled = KmrpPatchOption(L"layout-predraw", 1) != 0;
    if (!enabled) return;
    const int width=*reinterpret_cast<const int*>(0x0078D1D4), height=*reinterpret_cast<const int*>(0x0078D1D8);
    if (width<=0 || height<=0) return;
    int panelCount=0;
    const unsigned long long panels=panelSignature(manager,panelCount);
    const bool held=panels==panelsLastFrame;
    panelsLastFrame=panels;
    if (width!=seenWidth || height!=seenHeight) {
        predraw=seenWidth==0 ? Predraw::Drawn : Predraw::Rebuild;
        panelsAtChange=panels;
        seenWidth=width; seenHeight=height;
        return;
    }
    if (predraw==Predraw::Rebuild) {
        if (panels==panelsAtChange) return;             // not made again yet
        predraw=Predraw::Drawn;
    }
    if (predraw!=Predraw::Drawn || current || pending || panelCount==0) return;
    if (!held || !KmrpPicturesSettledK1()) return;
    void* p=fn<New>(0x6FA7E6)(0x64);
    if (!p) return;
    fn<PanelCtor>(0x40B570)(p,manager);
    char resref[16]="kmrplayout";
    fn<void(__thiscall*)(void*,void*)>(0x40A680)(p,resref);
    void* copies[K1_LAYOUT_CONTROLS]={};
    const bool theScreen=KmrpQueueLayoutPanelK1(p);
    for (int i=0;theScreen && i<K1_LAYOUT_CONTROLS;++i) {
        char tag[24];
        layoutTag(i,tag);
        copies[i]=bind(p,tag,i==1);
        if (copies[i]) KmrpQueueLayoutControlK1(copies[i]);
    }
    auto array=at<void**>(p,0x20);
    for (int i=0;array && i<at<int>(p,0x24);++i) array[i]=nullptr;
    for (void* c:copies) destroyControl(c);
    fn<Simple>(0x40CF70)(p);
    fn<Delete>(0x6FA390)(p);
    if (theScreen) {
        predraw=Predraw::Done; log("pictures-queued");
    } else {
        predraw=Predraw::Rebuild; panelsAtChange=panels;   // tried again when the screens change
    }
}

void ControllerLayoutFrameK1(void* manager) {
#ifdef KMRP_CONTROLLER_STANDALONE
    if (manager) probeLayoutPictures(manager);
#endif
    if (pending) {
        void* owner=pending; pending=nullptr;
        if (!current && fn<Exists>(0x40BD70)(manager,owner)) {
            void* p=fn<New>(0x6FA7E6)(0x64);
            if (!p) return;
            fn<PanelCtor>(0x40B570)(p,manager);
            memcpy(table,reinterpret_cast<void*>(0x73E010),sizeof(table));
            table[0]=reinterpret_cast<std::uintptr_t>(&destroy);
            table[15]=reinterpret_cast<std::uintptr_t>(&input);
            table[21]=reinterpret_cast<std::uintptr_t>(&onB);
            at<std::uintptr_t*>(p,0)=table;
            current=p; parent=owner; returnFocus=at<void*>(owner,0x1C);
            ++created; ownedCount=0;
            char resref[16]="kmrplayout";
            fn<void(__thiscall*)(void*,void*)>(0x40A680)(p,resref);
            bool complete=true;
            void* backButton=nullptr;
            for (int i=0;i<K1_LAYOUT_CONTROLS;++i) {
                char tag[24];
                layoutTag(i,tag);
                void* c=bind(p,tag,i==1);
                if (!c) { complete=false; break; }
                owned[ownedCount++]=c;
                if (i==1) backButton=c;
            }
            forgetRemap();
            editor = KmrpRemap::Editor(KmrpRemapSavedK1());
            if (complete && !buildRemap(p)) complete = false;
            fn<Simple>(0x40B8F0)(p);
            if (!complete) { destroy(p,nullptr,1); return; }
            fn<Event>(0x41AB20)(backButton,0x27,p,reinterpret_cast<void*>(&back));
            // Opened in View: nothing there is a place for the focus; the screen's
            // buttons are pad buttons (Default Y, Remap X, Back B).
            fn<SetActive>(0x40A630)(p,nullptr,0);
            family=0; device=-1; releasedFrames=0; refresh(); layoutRemap();
            fn<Add>(0x40BC70)(manager,p,3,1);
            log("opened");
        }
    }
    updateConfirmBadges();
    updateDialogBadges();
    updateEntryBadges();
    updateStatusSummary(manager);
    // Counted whether or not the screen is open: the reopen guard needs it
    // after the close as much as Back needs it after the open.
    if (ControllerConfirmHeldK1()) releasedFrames=0;
    else if (releasedFrames<K1_LAYOUT_ARM_FRAMES) ++releasedFrames;
    if (blockReopen && armed()) blockReopen=false;
    ++frameNumber;
    if (current) { refresh(); remapFrame(); }
}

// The status summary's layout alone, for the GUI frame without controller support
// (CoreGuiFrameK1): fitting the box to KMRP's larger text is a font fix, not a pad
// one. Its A badge exists only when the controller's ReleaseGff hook added it, so
// without the controller updateSummaryBadge finds none and draws nothing.
void StatusSummaryFrameK1(void* manager) {
    updateStatusSummary(manager);
}
