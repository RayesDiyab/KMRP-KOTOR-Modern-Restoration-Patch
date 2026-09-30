// The "granted" popup's rows, like the inventory's (Windows).
//
// The Windows side of macos/patches/kmrp-layout/granted_popup.cpp, which the Mac has had
// since 2026-09-30 (docs/windows-changes-from-macos.md, item 10), with the same arithmetic
// on Windows' offsets, read from the executable on 2026-09-30.
//
// The popup lists what a level brought ("You have been granted the following feat(s) this
// level.", and the Force-power version): skillinfo.gui, at character generation and on
// level-up. Its constructor (0x006CE7E0) gives it the vtable 0x00757940, the list LB_SKILLS
// at +0x64, LBL_MESSAGE at +0x344, BTN_OK at +0x484 and ten rows of 0x310 bytes from
// +0x648 (CSWGuiInGameSkillEntry, built by 0x006ACC50). Each time it is shown its fill
// (0x006CDFC0) gives each row its feat or power and hands the rows to the list
// (CSWGuiListBox::AddControls, 0x0041C1D0, called at 0x006CE0AB), which lays them out.
//
// On the Mac at 3024x1964 the rows sat far apart, each hex was shorter than its text
// frame, and the text started against the frame's left line. Since item 14 the build
// makes LB_SKILLS as tall as its rows at the inventory's pitch, so a full popup is spaced
// right on both platforms; this does the rest, for this popup's rows only:
//   1. at the end of each row's SetExtent (0x006AB8E0; the hook at 0x006AB9D5, before its
//      last call gives the text its rect): the hex frame, its highlight and the icon
//      (+0x1B4, +0x228, +0x29C, each a square as tall as the row) grow by a seventh, about
//      the same centre and 1/40 of the row lower, so the hex spans the text frame; the
//      text's rect is inset by an eighth of the row on each side;
//   2. after the fill's AddControls (the hook at 0x006CE0B0): the list goes back to the
//      file's extent, which gives the engine's own count of rows that fit; its height is
//      then cut to that many rows, or as many as were granted if fewer, at a pitch of the
//      row plus an eleventh of it; OK moves up by the height taken off, and the panel loses
//      it too, keeping its centre. The list lays its rows out again, through step 1.
// The file's extents are kept the first time the popup is filled, so every fill starts
// from them: the one popup is filled again at every level.
//
// Windows' CSWGuiListBox, from OrganizeControls (0x0041B140): inner height +0x298, item
// count +0x2A0, row height +0x2B4, rows that fit +0x2C4 (a short). Every control's extent
// is at +0x4, set through vtable slot 1.
#include <cstdint>
#include <cstring>

namespace {

constexpr std::uintptr_t kGrantedVtable = 0x00757940;
constexpr std::size_t kExtent = 0x4, kList = 0x64, kOk = 0x484, kRows = 0x648, kRowStride = 0x310, kRowCount = 10;
constexpr std::size_t kRowText = 0xD0, kHex = 0x1B4, kHexLit = 0x228, kIcon = 0x29C;
constexpr std::size_t kListInner = 0x298, kListCount = 0x2A0, kListRow = 0x2B4, kListVisible = 0x2C4;

template <typename T> T& At(void* base, std::size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

using SetExtentCall = void(__thiscall*)(void*, const std::int32_t*);

void SetExtent(void* control, const std::int32_t* extent) {   // vtable slot 1
    SetExtentCall call = (*reinterpret_cast<SetExtentCall**>(control))[1];
    call(control, extent);
}

struct FileLayout {
    void* popup;
    std::int32_t list[4], ok[4], panel[4];
};
FileLayout g_file;
char* g_popup;   // the popup whose rows step 1 refits, once it has been filled

bool IsGrantedRow(char* row) {
    char* const first = g_popup + kRows;
    if (row < first || row >= first + kRowCount * kRowStride) return false;
    return (row - first) % kRowStride == 0 && At<std::uintptr_t>(g_popup, 0) == kGrantedVtable;
}

void FitRows(char* popup) {
    void* const list = popup + kList;
    void* const ok = popup + kOk;
    if (g_file.popup != popup) {
        g_file.popup = popup;
        std::memcpy(g_file.list, &At<std::int32_t>(list, kExtent), sizeof g_file.list);
        std::memcpy(g_file.ok, &At<std::int32_t>(ok, kExtent), sizeof g_file.ok);
        std::memcpy(g_file.panel, &At<std::int32_t>(popup, kExtent), sizeof g_file.panel);
    }
    std::int32_t extent[4], okExtent[4], panel[4];
    std::memcpy(extent, g_file.list, sizeof extent);
    std::memcpy(okExtent, g_file.ok, sizeof okExtent);
    std::memcpy(panel, g_file.panel, sizeof panel);

    SetExtent(list, extent);   // the file's list, laid out: the engine's count of rows that fit
    const std::int32_t row = At<std::int32_t>(list, kListRow);
    const std::int32_t fit = At<std::int16_t>(list, kListVisible);
    const std::int32_t count = At<std::int32_t>(list, kListCount);
    const std::int32_t rows = count < fit ? count : fit;
    std::int32_t cut = 0;
    if (row > 0 && rows > 0) {
        const std::int32_t want = rows * (row + row / 11);
        if (want < At<std::int32_t>(list, kListInner)) {
            cut = At<std::int32_t>(list, kListInner) - want;
            extent[3] -= cut;
            SetExtent(list, extent);
            if (At<std::int16_t>(list, kListVisible) != rows) {   // the engine counts otherwise: as the file
                extent[3] += cut;
                cut = 0;
                SetExtent(list, extent);
            }
        }
    }
    okExtent[1] -= cut;
    SetExtent(ok, okExtent);
    panel[1] += cut / 2;
    panel[3] -= cut;
    SetExtent(popup, panel);
}

}  // namespace

// After the fill's AddControls: remember the popup, then fit the list, OK and the panel to
// its rows. `list` is LB_SKILLS, esi at the hook.
extern "C" void __cdecl GrantedPopupFilledK1(void* list) {
    if (!list) return;
    char* const popup = static_cast<char*>(list) - kList;
    if (At<std::uintptr_t>(popup, 0) != kGrantedVtable) return;
    g_popup = popup;
    FitRows(popup);
}

// Before a row's SetExtent gives its text its rect: this popup's rows' hex, highlight and
// icon refitted and the rect inset. `text` is the row's text control (esi at the hook),
// `rect` SetExtent's own local copy of the text's rect (eax).
extern "C" void __cdecl GrantedRowTextK1(void* text, std::int32_t* rect) {
    if (!text || !rect || !g_popup) return;
    char* const row = static_cast<char*>(text) - kRowText;
    if (!IsGrantedRow(row)) return;
    const std::int32_t size = At<std::int32_t>(row, kHex + kExtent + 8);   // the square, as tall as the row
    const std::int32_t grown = size + size / 7;
    const std::int32_t left = At<std::int32_t>(row, kHex + kExtent) - (grown - size) / 2;
    const std::int32_t top = At<std::int32_t>(row, kHex + kExtent + 4) - (grown - size) / 2 + size / 40;
    const std::int32_t square[4] = {left, top, grown, grown};
    SetExtent(row + kHex, square);
    SetExtent(row + kHexLit, square);
    SetExtent(row + kIcon, square);
    const std::int32_t inset = size / 8;
    rect[0] += inset;
    rect[2] -= 2 * inset;
}
