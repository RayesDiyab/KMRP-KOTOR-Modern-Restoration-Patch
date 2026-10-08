/*
  KMRP for macOS: the panels that exist when the resolution changes.

  The game's mode switch loads the main menu and the options screen again from their layout
  files. Every other panel that exists at that moment keeps the extents the old size's files gave
  it: the screen the player is looking at, and the ones the game keeps for later. Seen on
  2026-10-04, 1512x982 to 1024x768 from Graphics Options: the screen's frame was drawn and none
  of its controls.

  As on Windows (src/controller-native/K1RuntimeLayout.cpp, of which this is the port): each
  panel's layout file and each control bound to it by tag are remembered as the game makes them,
  and after a switch every such control is given the extent the new size's file has for its tag.
  What the game's own code added to a control's extent after loading it is kept, scaled by the
  shared rule max(1, height / 720). Text, events, focus and ownership stay the game's.

  The engine (KOTOR_Exe 1.4.0):

      0x10049dfe4  CSWGuiPanel::StartLoadFromLayout(panel, CResRef* layout)   Windows 0x40A680
      0x10049e476  CSWGuiPanel::InitControl(panel, control, CExoString* tag, int)      0x40B930
      0x10049d8c8  CSWGuiPanel::~CSWGuiPanel (the base's, which every panel's calls)   0x40CF70
      +0x08        a panel's or a control's extent: left, top, width, height
      +0x20        a panel's manager; +0x50 a control's panel (set by 0x1004a4e1e)
      vtable+0x10  SetExtent(const int*)
      manager +0xA4, +0xA6   the viewport, 16 bits each

  Windows also hooks the control's destructor. Here a control is checked instead before it is
  touched: still readable, the same vtable, still pointing at its panel. The controls bound by
  tag are members of their panel's object, so they go when it goes, and the panel's destructor
  is hooked.
*/
#include "assets.h"
#include "widescreen.h"

#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <map>
#include <string>
#include <vector>

namespace kmrp {
extern void (*g_frameHook)(void* manager);   // kmrp-layout/kmrp_layout.cpp
void KeepSurface(int width, int height);     // resolution.cpp
}

namespace {

struct Extent { int left, top, width, height; };
bool operator==(const Extent& a, const Extent& b) {
    return a.left == b.left && a.top == b.top && a.width == b.width && a.height == b.height;
}

// A control, the extent its layout file gave it for the size last applied, and what the engine's
// own code had added to that (`moved`, measured at `scale`).
struct Control {
    void* pointer;
    std::uintptr_t table;
    bool known = false;
    Extent file{};
    bool adjusted = false;
    Extent moved{};
    double scale = 1;
    int rowsRight = 0;   // how much wider a list was made for its rows (list rows, below)
};
struct Panel {
    std::string resource;
    std::map<std::string, Control> controls;
    std::map<std::string, Extent> file;
    bool rowsPlaced = false;
    int width = 0, height = 0;   // the size in force when the panel was loaded, or last laid out for
};
struct State {
    std::map<void*, Panel> panels;
    int width = 0, height = 0;
};
State& TheState() {
    static State* state = new State;
    return *state;
}

template <class T> T& Field(void* p, std::size_t at) { return *reinterpret_cast<T*>(static_cast<char*>(p) + at); }

const std::size_t kExtent = 0x08, kPanelManager = 0x20, kControlPanel = 0x50, kVtSetExtent = 0x10;
const std::size_t kManagerWidth = 0xA4, kManagerHeight = 0xA6;

bool Readable(const void* p, std::size_t size) {
    mach_vm_address_t address = reinterpret_cast<mach_vm_address_t>(p);
    mach_vm_size_t region = 0;
    vm_region_basic_info_data_64_t info;
    mach_msg_type_number_t count = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object = MACH_PORT_NULL;
    if (mach_vm_region(mach_task_self(), &address, &region, VM_REGION_BASIC_INFO_64,
                       reinterpret_cast<vm_region_info_t>(&info), &count, &object) != KERN_SUCCESS) return false;
    const auto at = reinterpret_cast<mach_vm_address_t>(p);
    return address <= at && at + size <= address + region && (info.protection & VM_PROT_READ);
}

struct Gff {
    std::vector<unsigned char> data;
    unsigned structure = 0, structures = 0, fields = 0, fieldCount = 0;
    unsigned labels = 0, labelCount = 0, values = 0, indices = 0, lists = 0;
    bool integer(unsigned at, unsigned& value) const {
        if (at > data.size() || data.size() - at < 4) return false;
        memcpy(&value, data.data() + at, 4);
        return true;
    }
    bool range(unsigned at, unsigned count, unsigned size) const {
        return at <= data.size() && std::uint64_t(count) * size <= data.size() - at;
    }
    bool load(const std::string& path) {
        FILE* f = fopen(path.c_str(), "rb");
        if (!f) return false;
        fseek(f, 0, SEEK_END);
        const long size = ftell(f);
        fseek(f, 0, SEEK_SET);
        bool ok = size >= 56 && size < (16 << 20);
        if (ok) {
            data.resize(static_cast<std::size_t>(size));
            ok = fread(data.data(), 1, data.size(), f) == data.size();
        }
        fclose(f);
        if (!ok || memcmp(data.data(), "GUI V3.2", 8) != 0) return false;
        return integer(8, structure) && integer(12, structures) && integer(16, fields) && integer(20, fieldCount) &&
            integer(24, labels) && integer(28, labelCount) && integer(32, values) && integer(40, indices) &&
            integer(48, lists) && range(structure, structures, 12) && range(fields, fieldCount, 12) &&
            range(labels, labelCount, 16);
    }
    // `type` kAnyType: whichever the file has (PADDING is a byte in some files, an int in others).
    static constexpr unsigned kAnyType = ~0u;
    bool field(unsigned object, const char* name, unsigned type, unsigned& value) const {
        if (object >= structures) return false;
        unsigned count, start;
        if (!integer(structure + object * 12 + 4, start) || !integer(structure + object * 12 + 8, count) ||
            count > fieldCount) return false;
        for (unsigned i = 0; i < count; ++i) {
            unsigned index = start, label, actualType;
            if (count > 1 && !integer(indices + start + i * 4, index)) return false;
            if (index >= fieldCount || !integer(fields + index * 12, actualType) ||
                !integer(fields + index * 12 + 4, label) || label >= labelCount) return false;
            char text[17]{};
            memcpy(text, data.data() + labels + label * 16, 16);
            if (!strcmp(text, name)) return (type == kAnyType || actualType == type) && integer(fields + index * 12 + 8, value);
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
        if (!field(object, "TAG", 10, offset) || !integer(values + offset, size) || size > 255 ||
            !range(values + offset + 4, size, 1)) return false;
        result.assign(reinterpret_cast<const char*>(data.data() + values + offset + 4), size);
        return true;
    }
};

double Scale(int height) { return height > 720 ? height / 720.0 : 1.0; }

// `moved`, measured at one scale, at another: the shared rule, rounded to nearest.
Extent Scaled(const Extent& moved, double from, double to) {
    const auto at = [from, to](int value) { return static_cast<int>(std::lround(value * to / from)); };
    return {at(moved.left), at(moved.top), at(moved.width), at(moved.height)};
}

// Every top-level control's extent in a layout file, by tag.
bool FileExtents(const Gff& gff, std::map<std::string, Extent>& result) {
    unsigned offset, count;
    if (!gff.field(0, "CONTROLS", 15, offset) || !gff.integer(gff.lists + offset, count) || count > 512 ||
        !gff.range(gff.lists + offset + 4, count, 4)) return false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned object;
        std::string tag;
        Extent extent;
        if (!gff.integer(gff.lists + offset + 4 + i * 4, object) || !gff.tag(object, tag) || !gff.extent(object, extent))
            return false;
        result[tag] = extent;
    }
    return true;
}

// Every top-level list's PADDING and scrollbar width in a layout file, by tag (the width -1 when
// the file gives the list no scrollbar).
struct ListFile { int padding, bar; };
void FileLists(const Gff& gff, std::map<std::string, ListFile>& result) {
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
  List rows, as far from their box's left border as from its right (2026-10-04).

  A list's box is drawn by its panel's artwork, not by the list, and the rows' rectangle in the
  layout file is not centred in it. Measured on the game's own picture at 1512x982, as the dark
  columns between the border's last lit column and the row artwork's first: the inventory 17 on
  the left and 7 on the right, the skills 17 and 7, the powers' and feats' charts 10 and 7, the
  quests 12 and 7, the quest items 23 and 8. The maintainer: every list's rows the same distance
  from the box's border on both sides, measured against the border, not the scrollbar.

  Two things make the difference, and neither is one number times the resolution:

    * where the file puts the rows' rectangle in the box. That depends on the set: by the
      panel's artwork, 5 px too far right for the inventory at 1512x982, 3 at 1920x1080, -1 at
      3440x1440. macos/tools/measure_list_rows.py measures it for every set and list from the
      set's layout and the artwork, into list_rows.inc. A size the build has no set for takes
      the set nearest in shape, then in height, scaled by the heights.
    * where a row's artwork begins inside its rectangle, which depends on the row's kind
      (RowInset below): a button's outline is as far in on both sides; an item's or a skill's
      icon is further in on the left than the button is on the right; a chart of powers or feats
      the other way.

  A row of any kind is given its rectangle by its list, in CSWGuiListBox::OrganizeControls
  (0x1004a82b4): left = PADDING on the scrollbar's side, width = the content's less PADDING
  (listbox_padding.cpp), one rectangle on the stack for every row, [rbp-0x40], and three places
  that hand it to a row's SetExtent (0x1004a88be, 0x1004a8950, 0x1004a89be). A detour on each
  writes the rectangle's left and width again for the row about to get it: the sum of the two
  above further left, and as much wider, never further than PADDING (the row stays in the
  list). Where the sum is negative for the list's usual row (the store, the workbench: the box
  reaches further right than the rows), the list is made that much wider instead, once its
  panel has loaded, and the rows end further right.

  Seen in the game after this, 1512x982: 7 and 7 on every list above, 8 and 8 on the quest items.
  Not seen in the game, no save reaching them: the store, the workbench, the feats and powers of
  character generation and level-up; theirs is the measurement of the artwork alone.
  KMRP_LIST_ROWS_LOG in the environment names a file that gets each list and row kind once.
*/
#include "list_rows.inc"

const std::size_t kListPadding = 0x373, kListFlags = 0x370, kListContentWidth = 0x340, kListObject = 0x390;
const std::size_t kListRowHeight = 0x368;
const std::size_t kListBarWidth = 0x168;   // the scrollbar's extent is at +0x158's +0x08; CSWGuiListBox::SetExtent reads this

// The row's kind, by its vtable, and how much further in its artwork begins on the left than it
// ends on the right, in pixels (RowInset). A button's outline is as far in on both sides. An
// item's and a skill's icon is further in; how much was fitted to what the game drew with the
// offsets of list_rows.inc applied, on 2026-10-04 (left and right gaps before the fit: the
// inventory 9 and 6 at 1280x720, 7 and 6 at 1280x800, 7 and 7 at 1512x982, 2 and 8 at
// 3024x1964; the skills 8 and 6, 6 and 6, 7 and 7, 2 and 6): a line through the two largest
// sizes, which leaves the two smallest within 1.5 px.
enum RowKind { kButtonRow, kItemRow, kSkillRow, kChartRow, kStoreRow, kUpgradeRow, kScriptRow };
RowKind KindOf(std::uintptr_t vtable, RowKind usual) {
    switch (vtable) {
        case 0x1005ab5f8: return kItemRow;      // CSWGuiInGameItemEntry: inventory, equip, quest items, container
        case 0x1005a6070: return kSkillRow;     // CSWGuiInGameSkillEntry
        case 0x1005a9cd0: return kChartRow;     // a row of the powers' or the feats' chart
        case 0x1005ab848: return kStoreRow;     // CSWGuiStoreItemEntry: its icon is the row's height
        case 0x1005a5270: return kUpgradeRow;   // CSWUpgradeItemEntry: its icon is 56 at every size
        case 0x1005b3da8: return kScriptRow;    // a party member's script: a button with an arrow at each end
    }
    return usual;
}
double RowInset(RowKind kind, double scale, int rowHeight) {
    // An item row's icon is a cell of 56 * scale; the store's is its row's height, the
    // workbench's 56 at every size: the item's line, by the cell.
    const auto item = [](double cell) { return 4.39 * cell / 56 - 0.89; };
    switch (kind) {
        case kItemRow:    return item(56 * scale);
        case kSkillRow:   return 5.89 * scale - 2.97;
        case kChartRow:   return -1.47 * scale;   // 10 and 7 at 1512x982 with a button's inset
        case kStoreRow:   return item(rowHeight);
        case kUpgradeRow: return item(56);
        case kScriptRow:  return 1.47 * scale;    // 9 and 7 at 1512x982, its box centred on its rectangle
        default:          return 0;
    }
}

// The lists whose rows are placed: those of list_rows.inc, with the kind of row they usually hold.
const RowKind kUsualRow[] = {kItemRow, kSkillRow, kButtonRow, kItemRow, kStoreRow, kStoreRow, kUpgradeRow, kChartRow, kChartRow, kScriptRow};
constexpr int kMeasuredListCount = sizeof kMeasuredLists / sizeof *kMeasuredLists;
static_assert(sizeof kUsualRow / sizeof *kUsualRow == kMeasuredListCount, "a usual row for every measured list");

// The lists whose rows are set in from both borders of their box as well, and by how much for
// each 720 lines of the screen: the store's two and the workbench's. Windows' kRowGap
// (src/controller-native/K1RuntimeLayout.cpp, 2026-10-06): centred, the store's rows stood
// against both borders of their box there (no dark column on the left and one on the right at
// 3440x1440), and the maintainer asked for a gap on seeing a merchant; 3.5 is what the
// inventory's rows keep at that size. Taken over on the Mac on 2026-10-07 so the two platforms
// agree; neither list has been seen in the game on the Mac.
const double kRowGap[] = {0, 0, 0, 0, 3.5, 3.5, 3.5, 0, 0, 0};
static_assert(sizeof kRowGap / sizeof *kRowGap == kMeasuredListCount, "a gap for every measured list");

int MeasuredList(const std::string& name) {
    for (int i = 0; i < kMeasuredListCount; ++i)
        if (name == kMeasuredLists[i]) return i;
    return -1;
}

// A list's offset at a size: the set's own; else, from the sets nearest in shape (shapes within
// 2% are one, the families the sets are made in), the mean of the three nearest in height, each
// scaled by the heights. One set's offset is a rounded number, and neighbours of one shape differ
// by up to 2 px (the inventory: 4, 2, 4 at 1024x640, 1152x720, 1280x800). False where the
// artwork has no box for the list.
bool MeasuredOffset(int list, int width, int height, double& offset) {
    if (list < 0 || width <= 0 || height <= 0) return false;
    struct Near { double shape, tall, value; };
    Near near[3];
    int count = 0;
    for (const MeasuredSet& set : kMeasuredSets) {
        if (set.offset[list] == kNoBox) continue;
        if (set.width == width && set.height == height) { offset = set.offset[list]; return true; }
        Near one{std::floor(std::fabs(std::log(double(set.width) / set.height * height / width)) / 0.02),
                 std::fabs(std::log(double(set.height) / height)),
                 set.offset[list] * Scale(height) / Scale(set.height)};
        // Kept in order: nearest in shape, then in height.
        int at = count < 3 ? count : 3;
        while (at > 0 && (one.shape < near[at - 1].shape || (one.shape == near[at - 1].shape && one.tall < near[at - 1].tall))) {
            if (at < 3) near[at] = near[at - 1];
            --at;
        }
        if (at < 3) near[at] = one;
        if (count < 3) ++count;
    }
    if (!count) return false;
    double sum = 0;
    int used = 0;
    for (int i = 0; i < count; ++i)
        if (near[i].shape == near[0].shape) { sum += near[i].value; ++used; }
    offset = sum / used;
    return true;
}

// A list bound to a panel by tag, for its rows: which measured list it is, and how much wider
// it was made.
struct BoundList { std::string name; int measured = -1; int wider = 0; };
std::map<void*, BoundList>& Bound() {
    static auto* bound = new std::map<void*, BoundList>;
    return *bound;
}

void SizeNow(int& width, int& height) {
    width = height = 0;
    kmrp::widescreen::Target(&width, &height);
}

// How much wider a list is to be at a size: what its usual row would have to move right.
int ListWider(int measured, void* list, int width, int height) {
    double offset;
    if (!MeasuredOffset(measured, width, height, offset)) return 0;
    const double total = offset + RowInset(kUsualRow[measured], Scale(height), Field<int>(list, kListRowHeight));
    return total < 0 ? static_cast<int>(std::lround(-total)) : 0;
}

// The layout file the game reads for a panel at the size in force: the set's, else the artwork's.
bool LoadLayout(const std::string& resource, Gff& gff) {
    for (const std::string& directory : {kmrp::assets::NewestSetDirectory(), kmrp::assets::ArtworkDirectory()})
        if (!directory.empty() && gff.load(directory + "/" + resource + ".gui")) return true;
    return false;
}

void SetExtent(void* object, const Extent& extent) {
    const auto table = Field<std::uintptr_t>(object, 0);
    reinterpret_cast<void (*)(void*, const Extent*)>(*reinterpret_cast<std::uintptr_t*>(table + kVtSetExtent))(object, &extent);
}

bool Relayout(void* manager, int width, int height) {
    State& state = TheState();
    struct Change { void* pointer; Extent extent; };
    std::vector<Change> changes;
    const double oldScale = Scale(state.height), newScale = Scale(height);
    for (auto& item : state.panels) {
        void* panel = item.first;
        if (!Readable(panel, 0x60) || Field<void*>(panel, kPanelManager) != manager) continue;
        // A panel the game made for this size is the game's: on a change of size it makes the
        // HUD, the dialogue and the message box again (CGuiInGame::ResetInterfaceForSize), from
        // the new size's files and with its own code's additions already for the new size.
        // Until 2026-10-08 those were laid out here as well, as if what the code had added were
        // the old size's: the conversation's message and reply list came out wider than the
        // screen and its panel at the layout file's place, a black block over most of the
        // picture (seen after 1512x982 to 1920x1200, and by the maintainer after two changes).
        if (item.second.width == width && item.second.height == height) continue;
        item.second.width = width;
        item.second.height = height;
        Gff gff;
        if (!LoadLayout(item.second.resource, gff)) continue;
        Extent root;
        if (!gff.extent(0, root)) continue;
        const Extent old = Field<Extent>(panel, kExtent);
        if (old.width != state.width && old.left == (state.width - old.width) / 2) root.left = (width - root.width) / 2;
        if (old.height != state.height && old.top == (state.height - old.height) / 2) root.top = (height - root.height) / 2;
        changes.push_back({panel, root});
        std::map<std::string, Extent> file;
        if (!FileExtents(gff, file)) continue;
        std::map<std::string, ListFile> lists;
        FileLists(gff, lists);
        for (const auto& entry : file) {
            auto found = item.second.controls.find(entry.first);
            if (found == item.second.controls.end()) continue;
            Control& tracked = found->second;
            void* control = tracked.pointer;
            if (!Readable(control, 0x60) || Field<void*>(control, kControlPanel) != panel ||
                Field<std::uintptr_t>(control, 0) != tracked.table) continue;
            const Extent actual = Field<Extent>(control, kExtent);
            Extent now = actual;
            now.width -= tracked.rowsRight;   // the rows' share is put back below, for the new size
            Extent target = entry.second;
            if (now == target) {
                // The engine has already laid this one out for the new size.
                tracked.adjusted = false;
            } else if (tracked.known) {
                // What the engine's code added to the file after loading it is kept, at the new
                // scale; `moved` is remembered at the scale it was measured, so a round trip
                // returns the same pixels.
                const Extent moved = {now.left - tracked.file.left, now.top - tracked.file.top,
                                      now.width - tracked.file.width, now.height - tracked.file.height};
                if (moved == Extent{0, 0, 0, 0}) {
                    tracked.adjusted = false;
                } else if (!tracked.adjusted || !(moved == Scaled(tracked.moved, tracked.scale, oldScale))) {
                    tracked.adjusted = true;
                    tracked.moved = moved;
                    tracked.scale = oldScale;
                }
                if (tracked.adjusted) {
                    const Extent add = Scaled(tracked.moved, tracked.scale, newScale);
                    target = {target.left + add.left, target.top + add.top, target.width + add.width, target.height + add.height};
                    if (target.width < 0) target.width = 0;
                    if (target.height < 0) target.height = 0;
                }
            }
            tracked.known = true;
            tracked.file = entry.second;
            // A list's PADDING and its scrollbar's width are the new file's too (the engine read
            // them once, with the panel; until 2026-10-04 they stayed the old size's, and the
            // rows began where the old size's bar ended), and its rows are placed for the new size.
            tracked.rowsRight = 0;
            const auto list = lists.find(entry.first);
            if (list != lists.end() && Readable(control, kListObject)) {
                Field<unsigned char>(control, kListPadding) = static_cast<unsigned char>(list->second.padding);
                if (list->second.bar >= 0) Field<int>(control, kListBarWidth) = list->second.bar;
                const auto bound = Bound().find(control);
                if (bound != Bound().end() && bound->second.measured >= 0) {
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
    }
    for (const Change& change : changes) SetExtent(change.pointer, change.extent);
    fprintf(stderr, "[KMRP] %zu panels known, %zu extents set for %dx%d\n", state.panels.size(), changes.size(), width, height);
    state.width = width;
    state.height = height;
    return true;
}

// The GUI's frame: the viewport the manager has now, against the one the panels were laid out
// for. The switch itself has finished by then, with the engine's own reloads.
void Frame(void* manager) {
    if (!manager) return;
    State& state = TheState();
    const int width = Field<short>(manager, kManagerWidth), height = Field<short>(manager, kManagerHeight);
    if (width < 640 || height < 480) return;
    kmrp::KeepSurface(width, height);
    if (!state.width) { state.width = width; state.height = height; return; }
    if (width == state.width && height == state.height) return;
    Relayout(manager, width, height);
}

__attribute__((constructor)) void WatchFrames() { kmrp::g_frameHook = Frame; }

}  // namespace

// CSWGuiPanel::StartLoadFromLayout, entry: rdi the panel, rsi the layout's CResRef (16 characters,
// not always terminated).
extern "C" __attribute__((visibility("default"))) void KmrpPanelLayoutStart(void* panel, const char* resref) {
    if (!panel || !resref) return;
    std::string name(resref, strnlen(resref, 16));
    for (char& c : name) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    if (name.empty() || name.find_first_of("/\\:") != std::string::npos) return;
    Panel& entry = TheState().panels[panel];
    entry = Panel{};
    entry.resource = name;
    SizeNow(entry.width, entry.height);
    // The file the engine is about to load, for the size in force: the baseline each control's
    // later position is compared with.
    Gff gff;
    if (LoadLayout(name, gff)) FileExtents(gff, entry.file);
}

// CSWGuiPanel::InitControl, entry: rdi the panel, rsi the control, rdx the tag (a CExoString),
// ecx whether the panel files the control in its array.
extern "C" __attribute__((visibility("default"))) void KmrpPanelControl(void* panel, void* control, void* label, int filed) {
    if (!control || !label) return;
    State& state = TheState();
    const auto found = state.panels.find(panel);
    if (found == state.panels.end()) return;
    const char* name = Field<const char*>(label, 0);
    const int size = Field<int>(label, 8);
    if (!name || size <= 0 || size > 256) return;
    const std::string tag(name, strnlen(name, static_cast<std::size_t>(size)));
    if (tag.empty()) return;
    // A second control loaded from a tag whose own control is still there, and not filed with the
    // panel, is someone reading the layout (the controller patch finds where a control is in its
    // file that way, cues.cpp, and frees what it loaded): the tag stays its control's. Until
    // 2026-10-07 it became the reader's, and after a resolution change the control kept the old
    // size's place while whatever had taken the freed memory was given its rectangle.
    if (!filed) {
        const auto held = found->second.controls.find(tag);
        if (held != found->second.controls.end() && held->second.pointer != control &&
            Readable(held->second.pointer, 0x60) && Field<void*>(held->second.pointer, kControlPanel) == panel &&
            Field<std::uintptr_t>(held->second.pointer, 0) == held->second.table)
            return;
    }
    Control entry{control, Field<std::uintptr_t>(control, 0)};
    const auto file = found->second.file.find(tag);
    if (file != found->second.file.end()) { entry.known = true; entry.file = file->second; }
    found->second.controls[tag] = entry;
    BoundList bound;
    bound.name = found->second.resource + "." + tag;
    bound.measured = MeasuredList(bound.name);
    Bound()[control] = bound;
}

// CSWGuiPanel::StopLoadFromLayout, after its prologue: rdi is the panel. Every panel's
// constructor ends its loading with it, so each list has what its file gave it and no rows yet.
// The base destructor calls it too, which the flag at +0x5c (loading) tells apart.
extern "C" __attribute__((visibility("default"))) void KmrpPanelLoaded(void* panel) {
    if (!panel || !(Field<unsigned char>(panel, 0x5c) & 2)) return;
    State& state = TheState();
    const auto found = state.panels.find(panel);
    if (found == state.panels.end() || found->second.rowsPlaced) return;
    found->second.rowsPlaced = true;
    int width, height;
    SizeNow(width, height);
    for (auto& item : found->second.controls) {
        Control& tracked = item.second;
        void* list = tracked.pointer;
        const auto bound = Bound().find(list);
        if (bound == Bound().end() || bound->second.measured < 0 || !Readable(list, kListObject) ||
            Field<std::uintptr_t>(list, 0) != tracked.table || !(Field<unsigned short>(list, kListFlags) & 0x10)) continue;
        const int wider = ListWider(bound->second.measured, list, width, height);
        bound->second.wider = wider;
        if (!wider) continue;
        Extent extent = Field<Extent>(list, kExtent);
        extent.width += wider;
        tracked.rowsRight = wider;
        SetExtent(list, extent);   // the content's width with it
    }
}

// CSWGuiListBox::AddControls, entry: rdi the list, rsi the rows (an array's pointer and count).
// A list's pitch is the tallest of its rows' own heights, read here. The inventory's rows are
// made again each time it fills; the abilities' rows (a skill, a chart row of powers or feats)
// are made once with their panel, with the height their creator's constant had then, so after
// the resolution changed in the game they kept the old size's pitch under the new size's icons
// (seen 2026-10-04, 1512x982 to 3024x1964: the skills overlapped). Each is given the height the
// constant has now: the skill's at 0x10022f60f, the chart row's rectangle's at 0x100570efc, both
// rewritten for the size by the layout patch or the widescreen patch.
extern "C" __attribute__((visibility("default"))) void KmrpListAddRows(void* list, void* rows) {
    if (!list || !rows) return;
    void** const row = Field<void**>(rows, 0);
    const int count = Field<int>(rows, 8);
    if (!row || count <= 0 || count > 4096) return;
    for (int i = 0; i < count; ++i) {
        if (!row[i]) continue;
        const int* height = nullptr;
        switch (Field<std::uintptr_t>(row[i], 0)) {
            case 0x1005a6070: height = reinterpret_cast<const int*>(0x10022f60f); break;
            case 0x1005a9cd0: height = reinterpret_cast<const int*>(0x100570efc); break;
        }
        if (height && *height >= 8 && *height <= 4096) Field<Extent>(row[i], kExtent).height = *height;
    }
}

// CSWGuiListBox::OrganizeControls, where it hands a row its rectangle: r12 the list, rdi the row,
// rbp the routine's frame, in which the rectangle is at -0x40 (left, top, width, height). The
// stolen bytes, mov rax, [rdi]; lea rsi, [rbp-0x40], run after this.
extern "C" __attribute__((visibility("default"))) void KmrpListRow(void* list, void* row, char* frame) {
    if (!list || !row || !frame) return;
    const auto bound = Bound().find(list);
    if (bound == Bound().end()) return;
    const std::uintptr_t vtable = Field<std::uintptr_t>(row, 0);
    static const char* log = getenv("KMRP_LIST_ROWS_LOG");
    if (log) {
        static auto* seen = new std::map<std::string, bool>;
        char line[160];
        snprintf(line, sizeof line, "%s@%lx", bound->second.name.c_str(), static_cast<unsigned long>(vtable));
        if (!(*seen)[line]) {
            (*seen)[line] = true;
            if (FILE* f = fopen(log, "a")) { fprintf(f, "%s\n", line); fclose(f); }
        }
    }
    const int measured = bound->second.measured;
    if (measured < 0 || !(Field<unsigned short>(list, kListFlags) & 0x10)) return;
    int width, height;
    SizeNow(width, height);
    double offset;
    if (!MeasuredOffset(measured, width, height, offset)) return;
    int32_t* rect = reinterpret_cast<int32_t*>(frame - 0x40);
    const int padding = Field<unsigned char>(list, kListPadding);
    const double inset = RowInset(KindOf(vtable, kUsualRow[measured]), Scale(height), rect[3]);
    int shift = static_cast<int>(std::lround(offset + inset)) + bound->second.wider;
    if (shift > padding) shift = padding;
    const int gap = static_cast<int>(std::lround(kRowGap[measured] * Scale(height)));
    const int rowWidth = Field<int>(list, kListContentWidth) - padding + shift;
    if (rowWidth <= 4 * gap) return;   // no list of the game's is this narrow
    rect[0] = padding - shift + gap;
    rect[2] = rowWidth - 2 * gap;
}

// CSWGuiPanel::~CSWGuiPanel, entry: rdi the panel.
extern "C" __attribute__((visibility("default"))) void KmrpPanelDestroyed(void* panel) {
    State& state = TheState();
    const auto found = state.panels.find(panel);
    if (found == state.panels.end()) return;
    for (const auto& item : found->second.controls) {
        const auto bound = Bound().find(item.second.pointer);
        if (bound != Bound().end() && bound->second.name == found->second.resource + "." + item.first) Bound().erase(bound);
    }
    state.panels.erase(found);
}
