// Reapply authored geometry to existing native controls after a mode change.
// Text, event bindings, focus, list selection and control ownership remain native.
#include "K1RuntimeLayout.h"
#include "K1RuntimeAssets.h"
#include <windows.h>
#include <map>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <cmath>

namespace {
struct Extent { int left, top, width, height; };
bool operator==(const Extent& a, const Extent& b)
{
    return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height;
}
// A control, the extent its layout file gave it for the size last applied, and
// what the engine's own code had added to that (`moved`, measured at `scale`).
struct Control {
    void* pointer; std::uintptr_t table;
    bool known = false; Extent file{};
    bool adjusted = false; Extent moved{}; double scale = 1;
    int rowsRight = 0;   // how much wider a list was made for its rows (list rows, below)
};
struct Panel {
    std::string resource; std::map<std::string, Control> controls; std::map<std::string, Extent> file;
    bool rowsPlaced = false;   // its lists have been made as wide as their rows need (PlaceLists)
    // The size its controls stand for: the one in force when it was loaded, then the
    // one it was last laid out for (KmrpRuntimeLayoutDimensions). 0 where it could not
    // be read.
    int width = 0, height = 0;
};
std::map<void*, Panel> panels;
int previousWidth = 0, previousHeight = 0;
template<class T> T& Field(void* p, unsigned at) { return *reinterpret_cast<T*>(static_cast<char*>(p) + at); }

struct Gff {
    static constexpr unsigned kAnyType = 0xFFFFFFFFu;
    std::vector<unsigned char> data;
    unsigned structure = 0, structures = 0, fields = 0, fieldCount = 0;
    unsigned labels = 0, labelCount = 0, values = 0, indices = 0, lists = 0;
    bool integer(unsigned at, unsigned& value) const {
        if (at > data.size() || data.size() - at < 4) return false;
        std::memcpy(&value, data.data() + at, 4); return true;
    }
    bool range(unsigned at, unsigned count, unsigned size) const {
        return at <= data.size() && std::uint64_t(count) * size <= data.size() - at;
    }
    bool load(const std::wstring& path) {
        HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
        if (file == INVALID_HANDLE_VALUE) return false;
        DWORD size = GetFileSize(file, nullptr), got = 0;
        bool ok = size >= 56 && size < (16u << 20);
        if (ok) { data.resize(size); ok = ReadFile(file, data.data(), size, &got, nullptr) && got == size; }
        CloseHandle(file);
        if (!ok || std::memcmp(data.data(), "GUI V3.2", 8)) return false;
        return integer(8, structure) && integer(12, structures) && integer(16, fields) && integer(20, fieldCount) &&
            integer(24, labels) && integer(28, labelCount) && integer(32, values) && integer(40, indices) && integer(48, lists) &&
            range(structure, structures, 12) && range(fields, fieldCount, 12) && range(labels, labelCount, 16);
    }
    bool field(unsigned object, const char* name, unsigned type, unsigned& value) const {
        if (object >= structures) return false;
        unsigned count, start;
        if (!integer(structure + object * 12 + 4, start) || !integer(structure + object * 12 + 8, count) || count > fieldCount) return false;
        for (unsigned i = 0; i < count; ++i) {
            unsigned index = start, label, actualType;
            if (count > 1 && !integer(indices + start + i * 4, index)) return false;
            if (index >= fieldCount || !integer(fields + index * 12, actualType) || !integer(fields + index * 12 + 4, label) || label >= labelCount) return false;
            char text[17]{}; std::memcpy(text, data.data() + labels + label * 16, 16);
            if (!std::strcmp(text, name)) return (type == kAnyType || actualType == type) && integer(fields + index * 12 + 8, value);
        }
        return false;
    }
    bool extent(unsigned object, Extent& result) const {
        unsigned child, left, top, width, height;
        if (!field(object, "EXTENT", 14, child) || !field(child, "LEFT", 5, left) || !field(child, "TOP", 5, top) ||
            !field(child, "WIDTH", 5, width) || !field(child, "HEIGHT", 5, height)) return false;
        result = {static_cast<int>(left), static_cast<int>(top), static_cast<int>(width), static_cast<int>(height)};
        return result.width >= 0 && result.height >= 0 && result.width <= 32767 && result.height <= 32767;
    }
    bool tag(unsigned object, std::string& result) const {
        unsigned offset, size;
        if (!field(object, "TAG", 10, offset) || !integer(values + offset, size) || size > 255 || !range(values + offset + 4, size, 1)) return false;
        result.assign(reinterpret_cast<const char*>(data.data() + values + offset + 4), size); return true;
    }
};
struct Change { void* pointer; Extent extent; };

double Scale(int height) { return height > 720 ? height / 720.0 : 1.0; }

// `moved`, measured at one scale, at another: the shared rule, rounded to nearest.
Extent Scaled(const Extent& moved, double from, double to)
{
    const auto at = [from, to](int value) { return static_cast<int>(std::lround(value * to / from)); };
    return {at(moved.left), at(moved.top), at(moved.width), at(moved.height)};
}

// Every top-level control's extent in a layout file, by tag.
bool FileExtents(const Gff& gff, std::map<std::string, Extent>& result)
{
    unsigned offset, count;
    if (!gff.field(0, "CONTROLS", 15, offset) || !gff.integer(gff.lists + offset, count) || count > 512 ||
        !gff.range(gff.lists + offset + 4, count, 4)) return false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned object; std::string tag; Extent extent;
        if (!gff.integer(gff.lists + offset + 4 + i * 4, object) || !gff.tag(object, tag) || !gff.extent(object, extent)) return false;
        result[tag] = extent;
    }
    return true;
}

// Every list's PADDING and scrollbar width in a layout file, by tag. The engine reads
// both once, with the panel.
struct ListFile { int padding, bar; };
void FileLists(const Gff& gff, std::map<std::string, ListFile>& result)
{
    unsigned offset, count;
    if (!gff.field(0, "CONTROLS", 15, offset) || !gff.integer(gff.lists + offset, count) || count > 512 ||
        !gff.range(gff.lists + offset + 4, count, 4)) return;
    for (unsigned i = 0; i < count; ++i) {
        unsigned object, type, padding, bar, extent, width;
        std::string tag;
        if (!gff.integer(gff.lists + offset + 4 + i * 4, object) || !gff.tag(object, tag) ||
            !gff.field(object, "CONTROLTYPE", 5, type) || type != 11 ||
            !gff.field(object, "PADDING", Gff::kAnyType, padding)) continue;
        ListFile list{static_cast<int>(padding & 0xff), -1};
        if (gff.field(object, "SCROLLBAR", 14, bar) && gff.field(bar, "EXTENT", 14, extent) &&
            gff.field(extent, "WIDTH", 5, width) && width <= 4096) list.bar = static_cast<int>(width);
        result[tag] = list;
    }
}

/*
  List rows, as far from their box's left border as from its right.

  The Mac's work of 2026-10-04 (macos/patches/kmrp-assets/layout.cpp on the branch
  macos-standalone-kpatch, "List rows"), brought here on 2026-10-06 at the maintainer's
  request. A list's box is drawn by its panel's artwork, not by the list, and the rows'
  rectangle the layout file gives is not centred in it; a row's own artwork also begins
  further inside its rectangle on one side than on the other. Counted on Windows before
  this, the inventory at about 3440x1440 in a window (3432x1409, a blended size): 19 dark
  columns between the box's left border and the icon's frame, 12 between the button and
  the right border.

  Two numbers make the difference, as on the Mac:

    * where the file puts the rows' rectangle in the box: K1ListRows.inc, per menu set and
      list, the Mac's measurement of the sets and the artwork. The Windows build's sets
      measure to the same 66 rows (the Mac's tool run on build/kmrp/resources, 2026-10-06).
      A size the build has no set for takes the sets nearest in shape, then in height,
      scaled by the heights (MeasuredOffset).
    * where a row's artwork begins inside its rectangle, by the row's kind (RowInset): the
      Mac's numbers, fitted to what the Mac drew. For an item row they give 7 at that size
      with the table's -1, which is the 19 less 12 counted above.

  Counted on Windows at 3440x1440 with this in (2026-10-06, dark columns left and right of
  the rows): the inventory 7 and 7, the journal 5 and 6, the store 0 and 1. The powers'
  chart was 11 and 7 with the Mac's number for its row, and is 0 here instead: see
  RowInset. A skill's row and a script's are the Mac's numbers, not counted here yet.

  The store's rows, and by the same artwork the workbench's, reach both borders of their
  box once they are centred. They are set in from both by kRowGap, at the maintainer's
  request on seeing a merchant that day.

  A row of any kind is given its rectangle by its list, in CSWGuiListBox::OrganizeControls
  (0x0041B140): one rectangle on the stack for every row, [esp+0x20], left = PADDING on the
  scrollbar's side and width = the content's less PADDING since KMRP's own changes to that
  routine (reverse-engineering/listbox-geometry.md), and three places that hand it to a
  row's SetExtent: 0x0041B4BF (the rows above the first shown), 0x0041B540 (the rows shown)
  and 0x0041B59F (the rows below). A detour on each (KmrpListRowK1: esi the list, ecx the
  row, the rectangle) writes the rectangle's left and width again for the row about to
  get it: the sum of the two above further left, and as much wider, never further than
  PADDING, so the row stays in the list and its right edge where it was. Where the sum is
  negative for the list's usual row (the store, the workbench: the box reaches further
  right than the rows), the list is made that much wider instead and the rows end further
  right (PlaceLists, on the first frame after its panel has loaded: this module has no
  hook at the end of a panel's loading).

  The lists: K1ListRows.inc's ten. Not touched, as on the Mac: the equip screen's list and
  the container's, whose rows have no outline on the right to compare with, and the lists
  that have no box (saved games, movies, key mapping, messages, feedback options).
*/
#include "K1ListRows.inc"

// CSWGuiListBox (reverse-engineering/listbox-geometry.md): the scrollbar's width, which
// SetExtent (0x0041BF80) reads; the content's width; the rows' height; the flags, of which
// 0x10 is the scrollbar on the left; PADDING, a byte.
const unsigned kListBarWidth = 0x110, kListContentWidth = 0x294, kListRowHeight = 0x2B4, kListFlags = 0x2BC, kListPadding = 0x2C0;
const std::uintptr_t kListTable = 0x0073E840;          // CSWGuiListBox's vtable
// CSWGuiInGameMap: its vtable, its CSWGuiMapHider and its canvas (KmrpRuntimeLayoutDimensions).
const std::uintptr_t kMapPanelTable = 0x00754830;
const unsigned kMapOverlay = 0xE38, kMapCanvas = 0x1080;
const unsigned kControlPanel = 0x34, kPanelManager = 0x18, kManagerWidth = 0x6C, kManagerHeight = 0x6E;   // the last two are shorts

// The row's kind, by its vtable (the names are the Ghidra archive's), and how much further
// in its artwork begins on the left than it ends on the right, in pixels (RowInset). A
// button's outline is as far in on both sides.
enum RowKind { kButtonRow, kItemRow, kSkillRow, kChartRow, kStoreRow, kUpgradeRow, kScriptRow };
RowKind KindOf(std::uintptr_t vtable, RowKind usual)
{
    switch (vtable) {
        case 0x007568F8: return kItemRow;      // CSWGuiInGameItemEntry: inventory, equip, quest items, container
        case 0x00755ED0: return kSkillRow;     // CSWGuiInGameSkillEntry
        case 0x007578A8: return kChartRow;     // CSWGuiSkillFlow: a row of the powers' or the feats' chart
        case 0x00756850: return kStoreRow;     // CSWGuiStoreItemEntry: its icon is the row's height
        case 0x00757108: return kUpgradeRow;   // CSWUpgradeItemEntry: its icon is 56 at every size
        case 0x0073EB88: return kScriptRow;    // CSWGuiButtonToggle: a party member's script (CSWGuiScriptSelect::CreateOption)
    }
    return usual;
}
double RowInset(RowKind kind, double scale, int rowHeight)
{
    // An item row's icon is a cell of 56 * scale; the store's is its row's height, the
    // workbench's 56 at every size: the item's line, by the cell.
    const auto item = [](double cell) { return 4.39 * cell / 56 - 0.89; };
    switch (kind) {
        case kItemRow:    return item(56 * scale);
        case kSkillRow:   return 5.89 * scale - 2.97;
        // Not the Mac's -1.47 * scale. A chart's row puts its first picture at its
        // rectangle's left and its third at the right, each the row's height square
        // (CSWGuiSkillFlow::SetExtent, 0x006CCE30: left, left + (width - height) / 2,
        // left + width - height), so nothing is further in on one side; with the Mac's
        // number the pictures' boxes stood 11 columns from the left border and 7 from
        // the right at 3440x1440.
        case kChartRow:   return 0;
        case kStoreRow:   return item(rowHeight);
        case kUpgradeRow: return item(56);
        case kScriptRow:  return 1.47 * scale;
        default:          return 0;
    }
}

// The lists whose rows are placed: those of K1ListRows.inc, with the kind of row they usually hold.
const RowKind kUsualRow[] = {kItemRow, kSkillRow, kButtonRow, kItemRow, kStoreRow, kStoreRow, kUpgradeRow, kChartRow, kChartRow, kScriptRow};
constexpr int kMeasuredListCount = sizeof kMeasuredLists / sizeof *kMeasuredLists;
static_assert(sizeof kUsualRow / sizeof *kUsualRow == kMeasuredListCount, "a usual row for every measured list");

// The lists whose rows are set in from both borders of their box as well, and by how
// much for each 720 lines of the screen: the store's two, whose rows stood against both
// borders once centred (no dark column on the left and one on the right at 3440x1440),
// and the workbench's, whose box the artwork draws alike (not seen in game). 3.5 is
// what the inventory's rows keep at that size, 7 on each side.
const double kRowGap[] = {0, 0, 0, 0, 3.5, 3.5, 3.5, 0, 0, 0};
static_assert(sizeof kRowGap / sizeof *kRowGap == kMeasuredListCount, "a gap for every measured list");

int MeasuredList(const std::string& name)
{
    for (int i = 0; i < kMeasuredListCount; ++i)
        if (name == kMeasuredLists[i]) return i;
    return -1;
}

// A list's offset at a size: the set's own; else, from the sets nearest in shape (shapes
// within 2% are one, the families the sets are made in), the mean of the three nearest in
// height, each scaled by the heights. False where the artwork has no box for the list.
bool MeasuredOffset(int list, int width, int height, double& offset)
{
    if (list < 0 || width <= 0 || height <= 0) return false;
    struct Near { double shape, tall, value; };
    Near nearest[3];
    int count = 0;
    for (const MeasuredSet& set : kMeasuredSets) {
        if (set.offset[list] == kNoBox) continue;
        if (set.width == width && set.height == height) { offset = set.offset[list]; return true; }
        Near one{std::floor(std::fabs(std::log(double(set.width) / set.height * height / width)) / 0.02),
                 std::fabs(std::log(double(set.height) / height)),
                 set.offset[list] * Scale(height) / Scale(set.height)};
        // Kept in order: nearest in shape, then in height.
        int at = count < 3 ? count : 3;
        while (at > 0 && (one.shape < nearest[at - 1].shape ||
                          (one.shape == nearest[at - 1].shape && one.tall < nearest[at - 1].tall))) {
            if (at < 3) nearest[at] = nearest[at - 1];
            --at;
        }
        if (at < 3) nearest[at] = one;
        if (count < 3) ++count;
    }
    if (!count) return false;
    double sum = 0;
    int used = 0;
    for (int i = 0; i < count; ++i)
        if (nearest[i].shape == nearest[0].shape) { sum += nearest[i].value; ++used; }
    offset = sum / used;
    return true;
}

// A list bound to a panel by tag, for its rows: which measured list it is, and how much
// wider it was made.
struct BoundList { std::string name; int measured = -1; int wider = 0; };
std::map<void*, BoundList> boundLists;

// The size in force, from the list's panel's manager.
bool SizeOf(void* list, int& width, int& height)
{
    void* panel = Field<void*>(list, kControlPanel);
    void* manager = panel ? Field<void*>(panel, kPanelManager) : nullptr;
    if (!manager) return false;
    width = Field<short>(manager, kManagerWidth);
    height = Field<short>(manager, kManagerHeight);
    return width > 0 && height > 0;
}

// How much wider a list is to be at a size: what its usual row would have to move right.
int ListWider(int measured, void* list, int width, int height)
{
    double offset;
    if (!MeasuredOffset(measured, width, height, offset)) return 0;
    const double total = offset + RowInset(kUsualRow[measured], Scale(height), Field<int>(list, kListRowHeight));
    return total < 0 ? static_cast<int>(std::lround(-total)) : 0;
}

void SetExtent(void* object, const Extent& extent)
{
    auto table = Field<std::uintptr_t*>(object, 0);
    reinterpret_cast<void(__thiscall*)(void*, const Extent*)>(table[1])(object, &extent);
}

// The lists of the panels that have finished loading since the last frame, made as wide
// as their rows need. A panel is in `panels` from the start of its loading, which is over
// before the next frame is drawn.
void PlaceLists(void* manager, int width, int height)
{
    for (auto& item : panels) {
        Panel& panel = item.second;
        if (panel.rowsPlaced || Field<void*>(item.first, kPanelManager) != manager) continue;
        panel.rowsPlaced = true;
        for (auto& entry : panel.controls) {
            Control& tracked = entry.second;
            void* list = tracked.pointer;
            const auto bound = boundLists.find(list);
            if (bound == boundLists.end() || bound->second.measured < 0 || tracked.table != kListTable ||
                Field<std::uintptr_t>(list, 0) != kListTable || !(Field<unsigned char>(list, kListFlags) & 0x10)) continue;
            const int wider = ListWider(bound->second.measured, list, width, height);
            bound->second.wider = wider;
            if (!wider) continue;
            Extent extent = Field<Extent>(list, 4);
            extent.width += wider;
            tracked.rowsRight = wider;
            SetExtent(list, extent);   // the content's width with it, and the rows laid out again
        }
    }
}
}

// CSWGuiListBox::OrganizeControls, where it hands a row its rectangle (left, top, width,
// height): see "List rows" above.
extern "C" void __cdecl KmrpListRowK1(void* list, void* row, int* rect)
{
    if (!list || !row || !rect) return;
    const auto bound = boundLists.find(list);
    if (bound == boundLists.end()) return;
    const int measured = bound->second.measured;
    if (measured < 0 || !(Field<unsigned char>(list, kListFlags) & 0x10)) return;
    int width, height;
    if (!SizeOf(list, width, height)) return;
    double offset;
    if (!MeasuredOffset(measured, width, height, offset)) return;
    const int padding = Field<unsigned char>(list, kListPadding);
    const double inset = RowInset(KindOf(Field<std::uintptr_t>(row, 0), kUsualRow[measured]), Scale(height), rect[3]);
    int shift = static_cast<int>(std::lround(offset + inset)) + bound->second.wider;
    if (shift > padding) shift = padding;
    const int gap = static_cast<int>(std::lround(kRowGap[measured] * Scale(height)));
    const int rowWidth = Field<int>(list, kListContentWidth) - padding + shift;
    if (rowWidth <= 4 * gap) return;      // no list of the game's is this narrow
    rect[0] = padding - shift + gap;
    rect[2] = rowWidth - 2 * gap;
}

// CSWGuiListBox::AddControls (0x0041C1D0), its entry: ecx the list, the first argument
// the rows (an array: its pointer, then its count).
//
//     0041C1D0  83 EC 08        sub esp, 8
//     0041C1D3  8B 44 24 0C     mov eax, [esp+0xC]
//
// A list's pitch is the tallest of its rows' own heights, read here. The inventory's
// rows are made again each time it fills. The abilities' rows (a skill; a row of the
// powers' or the feats' chart) are made once, with the height their maker's constant
// had then, so after the resolution was changed in the game they kept the old size's
// pitch under the new size's icons. Found on the Mac on 2026-10-04 (1512x982 to
// 3024x1964: the skills overlapped) and repaired there the next day; brought here on
// 2026-10-09. Each such row is given the height its constant has now: the skill's
// at 0x006ACB20 (CSWGuiInGameSkillEntry::Initialize) and the chart row's at
// 0x006CD8D9 (CSWGuiSkillFlowChart::AddPowerSet; AddFeatSet's at 0x006CDB79 is the
// same number), both written for the size in force by the engine recipe.
// CSWGuiInGameAbilities::UpdateView calls this routine for all three lists.
extern "C" void __cdecl KmrpListAddRowsK1(void* list, void** slot)
{
    void* rows = slot ? *slot : nullptr;
    if (!list || !rows) return;
    void** const row = Field<void**>(rows, 0);
    const int count = Field<int>(rows, 4);
    if (!row || count <= 0 || count > 4096) return;
    for (int i = 0; i < count; ++i) {
        if (!row[i]) continue;
        const int* height = nullptr;
        switch (Field<std::uintptr_t>(row[i], 0)) {
            case 0x00755ED0: height = reinterpret_cast<const int*>(0x006ACB20); break;   // CSWGuiInGameSkillEntry
            case 0x007578A8: height = reinterpret_cast<const int*>(0x006CD8D9); break;   // CSWGuiSkillFlow
        }
        if (height && *height >= 8 && *height <= 4096) Field<Extent>(row[i], 4).height = *height;
    }
}

// Every GUI frame (KmrpCoreGuiWorkK1): the lists of newly loaded panels.
void KmrpListRowsFrame(void* manager)
{
    if (!manager) return;
    const int width = Field<short>(manager, kManagerWidth), height = Field<short>(manager, kManagerHeight);
    if (width > 0 && height > 0) PlaceLists(manager, width, height);
}

// Stack arguments arrive as the address of their slot (KPM's "esp+N").
extern "C" void __cdecl KmrpPanelLayoutStartK1(void* panel, const char** slot)
{
    const char* resource = slot ? *slot : nullptr;
    if (!panel || !resource) return;
    std::string name(resource, strnlen_s(resource, 16));
    if (name.empty() || name.find_first_of("/\\:") != std::string::npos) return;
    Panel& entry = panels[panel];
    entry = Panel{};
    entry.resource = name;
    // The size in force now. While the game makes its own panels again after a change
    // of size (CGuiInGame::ResetInterfaceForSize) that is already the new one.
    if (void* manager = Field<void*>(panel, 0x18)) {
        entry.width = Field<short>(manager, 0x6C);
        entry.height = Field<short>(manager, 0x6E);
    }
    // The file the engine is about to load, for the size in force: the baseline
    // each control's later position is compared with.
    Gff gff;
    if (gff.load(KmrpRuntimeAssetDirectory() + L"\\" + std::wstring(name.begin(), name.end()) + L".gui"))
        FileExtents(gff, entry.file);
}
extern "C" void __cdecl KmrpPanelControlK1(void* panel, void** controlSlot, void** labelSlot, int* filedSlot)
{
    if (!controlSlot || !labelSlot) return;
    void* control = *controlSlot;
    void* label = *labelSlot;
    // Native InitControl is (CSWGuiControl* control, CExoString* label, int active).
    auto found = panels.find(panel);
    if (found == panels.end() || !control || !label) return;
    const char* name = Field<const char*>(label, 0);
    unsigned size = Field<unsigned>(label, 4);
    // CExoString's allocation length includes the terminator (5E5ABE/5E5AC0).
    // GFF TAG stores only the characters, so never include that terminator in keys.
    if (name && size && size <= 256 && name[size - 1] == '\0') {
        const auto length = strnlen_s(name, size);
        if (length) {
            const std::string tag(name, length);
            // A second control loaded from a tag whose own control is still there, and
            // not filed with the panel (InitControl's last argument 0), is someone
            // reading the layout: the controller patch finds where a control is in its
            // file that way and frees what it loaded (PlaceCueByReferenceK1,
            // K1NativeJoystick.cpp, for BTN_CHANGE1 on the four party screens). The tag
            // stays its control's. Until 2026-10-09 it became the reader's, and went
            // with it when the reader was freed (KmrpControlDestroyedK1), so after a
            // change of resolution in the game the first party portrait kept the old
            // size's place (seen that day on Abilities, 1920x1080 to 1680x1050). The
            // Mac found the same on 2026-10-07 in the code ported from this file.
            if (filedSlot && !*filedSlot) {
                const auto held = found->second.controls.find(tag);
                if (held != found->second.controls.end() && held->second.pointer != control &&
                        Field<std::uintptr_t>(held->second.pointer, 0) == held->second.table &&
                        Field<void*>(held->second.pointer, kControlPanel) == panel)
                    return;
            }
            Control entry{control, Field<std::uintptr_t>(control, 0)};
            const auto file = found->second.file.find(tag);
            if (file != found->second.file.end()) { entry.known = true; entry.file = file->second; }
            found->second.controls[tag] = entry;
            // For its rows, if it is one of the measured lists (list rows, above).
            BoundList bound;
            bound.name = found->second.resource + "." + tag;
            bound.measured = MeasuredList(bound.name);
            if (bound.measured >= 0) boundLists[control] = bound; else boundLists.erase(control);
        }
    }
}
extern "C" void __cdecl KmrpPanelDestroyedK1(void* panel)
{
    const auto found = panels.find(panel);
    if (found == panels.end()) return;
    for (const auto& item : found->second.controls) {
        const auto bound = boundLists.find(item.second.pointer);
        if (bound != boundLists.end() && bound->second.name == found->second.resource + "." + item.first) boundLists.erase(bound);
    }
    panels.erase(found);
}
extern "C" void __cdecl KmrpControlDestroyedK1(void* control)
{
    boundLists.erase(control);
    for (auto& panel : panels) for (auto at = panel.second.controls.begin(); at != panel.second.controls.end();) {
        if (at->second.pointer == control) at = panel.second.controls.erase(at); else ++at;
    }
}

bool KmrpRuntimeLayoutDimensions(void* manager, int width, int height)
{
    if (!previousWidth) { previousWidth = width; previousHeight = height; return true; }
    if (width == previousWidth && height == previousHeight) return true;
    std::vector<Change> changes;
    const double oldScale = Scale(previousHeight), newScale = Scale(height);
    for (auto& item : panels) {
        void* panel = item.first;
        if (Field<void*>(panel, 0x18) != manager) continue;
        // A panel loaded since the size became this one is left alone: the game makes
        // the HUD, the dialogue and the message box again on a change of size, from the
        // new size's files, with what its own code adds already worked out for the new
        // size. Laid out again here, that addition was taken for the old size's and
        // scaled a second time. Found on the Mac on 2026-10-08, in the code ported
        // from this file: after 1512x982 to 1920x1200 the conversation's message label
        // was 2108 wide where the game had made it 1824, and black covered most of the
        // picture (docs/windows-changes-from-macos.md, item 22). Brought here on
        // 2026-10-09; not seen on Windows before or after.
        if (item.second.width == width && item.second.height == height) continue;
        item.second.width = width;
        item.second.height = height;
        Gff gff;
        std::wstring name(item.second.resource.begin(), item.second.resource.end());
        if (!gff.load(KmrpRuntimeAssetDirectory() + L"\\" + name + L".gui")) continue;
        Extent root;
        if (!gff.extent(0, root)) return false;
        const Extent old = Field<Extent>(panel, 4);
        if (old.width != previousWidth && old.left == (previousWidth - old.width) / 2) root.left = (width - root.width) / 2;
        if (old.height != previousHeight && old.top == (previousHeight - old.height) / 2) root.top = (height - root.height) / 2;
        changes.push_back({panel, root});
        std::map<std::string, Extent> file;
        if (!FileExtents(gff, file)) return false;
        std::map<std::string, ListFile> lists;
        FileLists(gff, lists);
        for (const auto& entry : file) {
            auto found = item.second.controls.find(entry.first);
            if (found == item.second.controls.end()) continue;
            Control& tracked = found->second;
            void* control = tracked.pointer;
            if (Field<void*>(control, 0x34) != panel || Field<std::uintptr_t>(control, 0) != tracked.table) return false;
            const Extent actual = Field<Extent>(control, 4);
            Extent now = actual;
            now.width -= tracked.rowsRight;   // the rows' share is put back below, for the new size
            Extent target = entry.second;
            if (now == target) {
                // The engine has already laid this one out for the new size.
                tracked.adjusted = false;
            } else if (tracked.known) {
                // What the engine's code added to the file after loading it is kept,
                // at the new scale. The Options screen moves its five buttons down
                // after the load; reapplying the bare file put them 20 px high at
                // 1080 lines (measured 2026-10-04). `moved` is remembered at the
                // scale it was measured, so a round trip returns the same pixels.
                const Extent moved = {now.left - tracked.file.left, now.top - tracked.file.top,
                                      now.width - tracked.file.width, now.height - tracked.file.height};
                if (moved == Extent{0, 0, 0, 0}) {
                    tracked.adjusted = false;
                } else if (!tracked.adjusted || !(moved == Scaled(tracked.moved, tracked.scale, oldScale))) {
                    tracked.adjusted = true; tracked.moved = moved; tracked.scale = oldScale;
                }
                if (tracked.adjusted) {
                    const Extent add = Scaled(tracked.moved, tracked.scale, newScale);
                    target = {target.left + add.left, target.top + add.top, target.width + add.width, target.height + add.height};
                    if (target.width < 0) target.width = 0;
                    if (target.height < 0) target.height = 0;
                }
            }
            tracked.known = true; tracked.file = entry.second;
            // A list's PADDING and its scrollbar's width are the new file's too (the engine
            // read them once, with the panel, so they stayed the old size's and the rows
            // began where the old size's bar ended: the Mac saw it on 2026-10-04, and this
            // is the same code), and its rows are placed for the new size.
            tracked.rowsRight = 0;
            const auto list = lists.find(entry.first);
            if (list != lists.end() && tracked.table == kListTable) {
                Field<unsigned char>(control, kListPadding) = static_cast<unsigned char>(list->second.padding);
                if (list->second.bar >= 0) Field<int>(control, kListBarWidth) = list->second.bar;
                const auto bound = boundLists.find(control);
                if (bound != boundLists.end() && bound->second.measured >= 0 &&
                    (Field<unsigned char>(control, kListFlags) & 0x10)) {
                    bound->second.wider = ListWider(bound->second.measured, control, width, height);
                    tracked.rowsRight = bound->second.wider;
                    target.width += tracked.rowsRight;
                }
                changes.push_back({control, target});   // SetExtent lays the rows out again
            } else if (!(actual == target)) {
                changes.push_back({control, target});
            }
        }
        item.second.file.swap(file);
        // The area map's two surfaces, which no layout file holds.
        // CSWGuiInGameMap's constructor (0x00694D50) gives them their sizes after its
        // layout has loaded: the picture's canvas, a CSWGuiImage at +0x1080, {0, 0,
        // 512, 256}, and the markers' and fog's overlay, the CSWGuiMapHider at +0xE38,
        // {0, 0, 440, 256}. Those four numbers are the engine recipe's (0x0069505C,
        // 0x00695064, 0x00695082, 0x0069508A: FieldValue kinds 6, 7 and 8 in
        // K1RuntimeEngine.cpp), written again for the new size, but the panel is made
        // once, with the game, and kept the first size's: after 3440x1440 to
        // 1920x1080 the map was drawn 2001x720 over a 960x540 frame (the maintainer,
        // 2026-10-09). The instance the HUD makes for its minimap is put back to the
        // game's own 512x256 and 440x256 by the recipe's wrapper and is left so.
        if (Field<std::uintptr_t>(panel, 0) == kMapPanelTable) {
            void* canvas = static_cast<char*>(panel) + kMapCanvas;
            void* overlay = static_cast<char*>(panel) + kMapOverlay;
            const Extent canvasNow = Field<Extent>(canvas, 4), overlayNow = Field<Extent>(overlay, 4);
            const bool minimap = canvasNow.width == 512 && canvasNow.height == 256 &&
                                 overlayNow.width == 440 && overlayNow.height == 256;
            if (!minimap) {
                const double exact = (width / 2) * 512 / 440.0, lower = std::floor(exact), part = exact - lower;
                const int canvasWidth = static_cast<int>(lower) +
                    (part > .5 || (part == .5 && std::fmod(lower, 2.) != 0.) ? 1 : 0);
                changes.push_back({canvas, {canvasNow.left, canvasNow.top, canvasWidth, height / 2}});
                changes.push_back({overlay, {overlayNow.left, overlayNow.top, width / 2, height / 2}});
            }
            // The overlay's own two pictures, made by CSWGuiMapHider's constructor
            // (0x00693F60) at the recipe's marker sizes: the player's arrow (+0x60, 32
            // at the game's size, 0x0069405B) and the selection circle (+0x64, 16,
            // 0x006940DC). FieldValue's kind 10. Not seen wrong; set with the rest.
            const float scale = height > 720 ? static_cast<float>(height) / 720.f : 1.f;
            const float marker = scale > 127.f / 16.f ? 127.f / 16.f : scale;
            const struct { unsigned at; int base; } pictures[] = {{0x60, 32}, {0x64, 16}};
            for (const auto& picture : pictures) {
                void* image = Field<void*>(overlay, picture.at);
                if (!image) continue;
                const double exact = static_cast<float>(picture.base) * marker, lower = std::floor(exact), part = exact - lower;
                int side = static_cast<int>(lower) + (part > .5 || (part == .5 && std::fmod(lower, 2.) != 0.) ? 1 : 0);
                if (side < 1) side = 1;
                const Extent now = Field<Extent>(image, 4);
                changes.push_back({image, {now.left, now.top, side, side}});
            }
        }
    }
    for (const auto& change : changes) {
        auto table = Field<std::uintptr_t*>(change.pointer, 0);
        reinterpret_cast<void(__thiscall*)(void*, const Extent*)>(table[1])(change.pointer, &change.extent);
    }
    previousWidth = width; previousHeight = height;
    return true;
}
