/*
  The "granted" popup: rows like the inventory's
  ----------------------------------------------------------------------------------------------
  The popup that lists what a level brought ("You have been granted the following feat(s) this
  level.", and the Force-power version), skillinfo.gui, shown at character generation and on
  level-up. The GUI manager keeps one (its +0x128, 0x2D28 bytes, vtable 0x1005A9E18, built by
  0x10028E468). Its ten rows are CSWGuiInGameSkillEntry controls at +0x7F8, 0x3B8 apart, in the
  list box at +0x80 (LB_SKILLS); OK is the button at +0x5B8; the panel's extent is at +0x8. Each
  time it is shown, its fill (0x10028E9CA; called from 0x100213C6B, 0x1002C3A67, 0x1002EE1C1 and
  0x1002EF1BE) gives each row its feat or power and hands the rows to the list
  (CSWGuiListBox::AddControls, 0x1004A9BE6), which lays them out.

  Three things looked wrong at 3024x1964 (2026-09-30):
    - the rows sat 141 px apart for 115-px rows: the list box shares out the height it has
      left over between its visible rows (OrganizeControls, 0x1004A82B4; listbox_padding.cpp),
      and LB_SKILLS holds four rows with 105 px to spare. The inventory, the same kind of list,
      spreads 8 to 10% of a row: 15 px on its 153-px rows at 3024x1964, 7 on 76 at 1512x982,
      7 on 84 at 1920x1080, 10 on 112 at 3440x1440 (from each set's inventory.gui:
      (height - 8) mod row, over the 7 rows that fit);
    - the row's hex frame (lbl_hex_3) was drawn in a square as tall as the row, and the
      texture's hex fills 131 of its 153 rows, so the hex was 97 px tall beside a 111-px text
      frame;
    - the text started at the text frame's inner edge, its first letter against the frame's
      left line.

  CSWGuiInGameSkillEntry::SetExtent (0x10022F228) puts the hex frame, its highlight and the
  icon at +0x228, +0x2B0 and +0x338 (left, top, width, height), each a square as tall as the
  row (resolution_sizes.cpp scales it), and the text frames after it. Its last call
  (0x10022F321, `call 0x1004A3D4C`) gives the text control at +0x110 the frames' inner rect.

  So, for this popup's rows only:
    1. At the end of each row's SetExtent (in place of that last call, which it then makes):
       the three squares grow by a seventh, about the same centre and 1/40 of the row lower,
       so the hex's visible part spans the text frame's; the text's rect is inset by an eighth
       of the row on each side.
    2. After the fill's AddControls (in place of that call, 0x10028EA4F, which it makes first):
       the list goes back to the file's extent, which gives the engine's own count of rows
       that fit; its height is then cut to that many rows (or fewer, if fewer were granted)
       at a pitch of the row plus an eleventh of it; OK moves up by the height taken off, and
       the panel loses it too, keeping its centre. The list's own layout spreads what is left
       (an eleventh per row), so its arithmetic is unchanged.
  The file's extents are kept the first time the popup is filled, so every fill starts from
  them: the one popup is filled again at every level.
*/
#include "sites.h"

#include <cstdint>
#include <cstring>

namespace {

const uintptr_t kFillAddControls = 0x10028ea4f;   // call 0x1004a9be6, in the fill (0x10028e9ca)
const uintptr_t kAddControlsAddress = 0x1004a9be6;
const uintptr_t kRowTextExtent = 0x10022f321;     // call 0x1004a3d4c, SetExtent's last call
const uintptr_t kTextSetExtentAddress = 0x1004a3d4c;
const uintptr_t kGrantedVtable = 0x1005a9e18;
const auto AddControls = reinterpret_cast<void (*)(void*, void*, int, int, int)>(0x1004a9be6UL);
const auto TextSetExtent = reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a3d4cUL);
const auto ListSetExtent = reinterpret_cast<void (*)(void*, const int32_t*)>(0x1004a81aeUL);

const size_t kExtent = 0x8, kList = 0x80, kOk = 0x5b8, kRows = 0x7f8, kRowStride = 0x3b8, kRowCount = 10;
const size_t kRowText = 0x110, kHex = 0x228, kHexLit = 0x2b0, kIcon = 0x338;
const size_t kListInner = 0x344, kListCount = 0x350, kListRow = 0x368, kListVisible = 0x378;

template <typename T> T& At(void* base, size_t offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + offset);
}

void SetExtent(void* control, const int32_t* extent) {   // the control's own, vtable + 0x10
    using Fn = void (*)(void*, const int32_t*);
    (*reinterpret_cast<Fn*>(*reinterpret_cast<char**>(control) + 0x10))(control, extent);
}

// Plain data, zero before the first fill: no initialiser runs (kmrp_layout.cpp).
struct FileLayout {
    void* popup;
    int32_t list[4], ok[4], panel[4];
};
FileLayout g_file;
char* g_popup;   // the popup whose rows the list is laying out

bool IsGrantedRow(char* row) {
    char* const first = g_popup + kRows;
    if (row < first || row >= first + kRowCount * kRowStride) return false;
    return (row - first) % kRowStride == 0 && At<uintptr_t>(g_popup, 0) == kGrantedVtable;
}

void FitRows(char* popup) {
    void* const list = popup + kList;
    void* const ok = popup + kOk;
    if (g_file.popup != popup) {
        g_file.popup = popup;
        memcpy(g_file.list, &At<int32_t>(list, kExtent), sizeof g_file.list);
        memcpy(g_file.ok, &At<int32_t>(ok, kExtent), sizeof g_file.ok);
        memcpy(g_file.panel, &At<int32_t>(popup, kExtent), sizeof g_file.panel);
    }
    int32_t extent[4], okExtent[4], panel[4];
    memcpy(extent, g_file.list, sizeof extent);
    memcpy(okExtent, g_file.ok, sizeof okExtent);
    memcpy(panel, g_file.panel, sizeof panel);

    ListSetExtent(list, extent);   // the file's list, laid out: the engine's count of rows that fit
    const int32_t row = At<int32_t>(list, kListRow);
    const int32_t fit = At<int16_t>(list, kListVisible);
    const int32_t count = At<int32_t>(list, kListCount);
    const int32_t rows = count < fit ? count : fit;
    int32_t cut = 0;
    if (row > 0 && rows > 0) {
        const int32_t want = rows * (row + row / 11);
        if (want < At<int32_t>(list, kListInner)) {
            cut = At<int32_t>(list, kListInner) - want;
            extent[3] -= cut;
            ListSetExtent(list, extent);
            if (At<int16_t>(list, kListVisible) != rows) {   // the engine counts otherwise: as the file
                extent[3] += cut;
                cut = 0;
                ListSetExtent(list, extent);
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

// The fill's AddControls, then the list, OK and panel fitted to the rows. Reached by the
// fill's 5-byte call through the near page's thunk, with AddControls' own arguments.
extern "C" __attribute__((visibility("default"))) void KMRP_GrantedFill(void* list, void* rows, int a, int b, int c) {
    char* const popup = static_cast<char*>(list) - kList;
    const bool granted = At<uintptr_t>(popup, 0) == kGrantedVtable;
    if (granted) g_popup = popup;
    AddControls(list, rows, a, b, c);
    if (granted) FitRows(popup);
}

// SetExtent's last call, after this popup's rows' hex, icon and text are refitted. rect is
// SetExtent's own local copy of the text's rect.
extern "C" __attribute__((visibility("default"))) void KMRP_GrantedRowText(void* text, int32_t* rect) {
    char* const row = static_cast<char*>(text) - kRowText;
    if (g_popup && IsGrantedRow(row)) {
        const int32_t size = At<int32_t>(row, kHex + 8);   // the square, as tall as the row
        const int32_t grown = size + size / 7;
        const int32_t left = At<int32_t>(row, kHex) - (grown - size) / 2;
        const int32_t top = At<int32_t>(row, kHex + 4) - (grown - size) / 2 + size / 40;
        const int32_t square[4] = {left, top, grown, grown};
        for (size_t offset : {kHex, kHexLit, kIcon}) memcpy(&At<int32_t>(row, offset), square, sizeof square);
        const int32_t inset = size / 8;
        rect[0] += inset;
        rect[2] -= 2 * inset;
    }
    TextSetExtent(text, rect);
}

namespace kmrp {

void AddGrantedPopup(std::vector<Group>& groups, uintptr_t nearPage) {
    if (!nearPage) return;   // the constructor could not place the page: the popup stays as it is
    const auto call = [](uintptr_t site, uintptr_t target) {
        const int32_t rel = static_cast<int32_t>(static_cast<int64_t>(target) - static_cast<int64_t>(site + 5));
        return Join({Bytes({0xe8}), Int32(rel)});
    };
    groups.push_back({"granted popup rows", {
        {kFillAddControls, call(kFillAddControls, kAddControlsAddress), call(kFillAddControls, nearPage + kGrantedFillThunk)},
        {kRowTextExtent, call(kRowTextExtent, kTextSetExtentAddress), call(kRowTextExtent, nearPage + kGrantedRowThunk)},
    }});
}

}  // namespace kmrp
