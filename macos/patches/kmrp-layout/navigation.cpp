// Aspyr KOTOR 1.4.0 (C1FCB8D3...6D71), preferred x86_64 VAs.
// The Mac navigable/button/slider/list loaders fetch MOVETO but never read its
// direction fields. Before CSWGuiPanel::ResolveNavigation (0x10049e3f0), the
// slots still contain zero; it resolves them to control ID 0. Restore the IDs
// during the common CSWGuiControl::Load, before that one-time resolution pass.
#include <cstdint>
#include <algorithm>
#include <cstdlib>

extern "C" __attribute__((visibility("default")))
void KmrpLoadNavigation(void* control, void* gff, void* controlStruct) {
    if (!control || !gff || !controlStruct) return;
    using NavigableFn = void* (*)(void*);
    using GetStructFn = int (*)(void*, void*, void*, const char*);
    using ReadIntFn = int (*)(void*, void*, const char*, int*, int);
    const auto vtable = *reinterpret_cast<std::uintptr_t**>(control);
    void* const nav = reinterpret_cast<NavigableFn>(vtable[0x98 / 8])(control);
    if (!nav) return;

    // CResStruct's temporary occupies 16 bytes in the original loader.
    alignas(8) unsigned char move[16] = {};
    const auto getStruct = reinterpret_cast<GetStructFn>(0x1003620d4UL);
    const auto readInt = reinterpret_cast<ReadIntFn>(0x100362462UL);
    const bool found = getStruct(gff, move, controlStruct, "MOVETO") != 0;
    const char* const fields[] = {"UP", "LEFT", "DOWN", "RIGHT"};
    auto* const targets = reinterpret_cast<std::intptr_t*>(static_cast<char*>(nav) + 0x88);
    for (int i = 0; i < 4; ++i) {
        int success = 0;
        const int id = found ? readInt(gff, move, fields[i], &success, -1) : -1;
        targets[i] = (found && success) ? id : -1;
    }
}

namespace {
template<class T> T& Field(void* p, unsigned offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(p) + offset);
}
void* keyboardManager = nullptr;
int keyboardMouseX = 0, keyboardMouseY = 0;

bool SelectableList(void* c, std::uintptr_t* table) {
    if (table[0x80 / 8] != 0x1004a8a38UL) return false;
    void** entries = Field<void**>(c, 0x348);
    const int count = Field<int>(c, 0x350);
    if (!entries || count <= 0 || count > 4096) return false;
    for (int i = 0; i < count; ++i) {
        void* item = entries[i];
        if (!item || !(Field<unsigned char>(item, 0x68) & 8)) continue;
        auto* vt = Field<std::uintptr_t*>(item, 0);
        using CastFn = void* (*)(void*);
        if (reinterpret_cast<CastFn>(vt[0x98 / 8])(item)) return true;
    }
    return false;
}

// Repair the live vertical graph only when actionable controls are unreachable
// or its links still contain unresolved IDs. Never dereference a link unless it
// matches one of the panel's current, eligible controls. This includes controls
// added after the original resolver and does not depend on menu IDs or resolution.
void RepairNavigation(void* panel) {
    if (!panel) return;
    void** controls = Field<void**>(panel, 0x30);
    const int count = Field<int>(panel, 0x38);
    if (!controls || count <= 0 || count > 512) return;
    struct Item { void* control; void* nav; int x, y, id, width; bool ownsHorizontal; };
    Item items[512];
    int used = 0;
    for (int id = 0; id < count; ++id) {
        void* c = controls[id];
        if (!c || Field<int>(c, 0x74) != id || Field<void*>(c, 0x50) != panel) continue;
        const auto flags = Field<unsigned char>(c, 0x68);
        if ((flags & 0x2a) != 0x0a) continue;
        auto* table = Field<std::uintptr_t*>(c, 0);
        const int events = Field<int>(c, 0x60);
        const bool hasHandlers = Field<void*>(c, 0x58) && events > 0 && events <= 64;
        if (!hasHandlers && !SelectableList(c, table)) continue;
        if (Field<int>(c, 0x10) <= 0 || Field<int>(c, 0x14) <= 0) continue;
        using CastFn = void* (*)(void*);
        void* nav = reinterpret_cast<CastFn>(table[0x98 / 8])(c);
        if (nav) items[used++] = {c, nav, Field<int>(c, 8), Field<int>(c, 12), id, Field<int>(c, 0x10),
            table[0x80 / 8] == 0x1004a694cUL};
    }
    if (used < 2) return;
    // Each direction must traverse every eligible item and return to its start.
    // A complete resource-defined cycle is preserved, including its custom order.
    bool complete = true;
    for (unsigned offset : {0x88U, 0x98U}) {
        bool seen[512] = {};
        int index = 0;
        for (int step = 0; step < used; ++step) {
            if (index < 0 || seen[index]) { complete = false; break; }
            seen[index] = true;
            void* next = Field<void*>(items[index].nav, offset);
            index = -1;
            for (int j = 0; j < used; ++j)
                if (items[j].control == next) { index = j; break; }
        }
        if (index != 0) complete = false;
    }
    bool sharedRow = false;
    for (int i = 0; i < used; ++i)
        for (int j = i + 1; j < used; ++j) sharedRow |= items[i].y == items[j].y;
    if (complete && !sharedRow) return;
    std::sort(items, items + used, [](const Item& a, const Item& b) {
        if (a.y != b.y) return a.y < b.y;
        if (a.x != b.x) return a.x < b.x;
        return a.id < b.id;
    });
    int rowStart[512], rowEnd[512], rows = 0;
    for (int i = 0; i < used;) {
        const int start = i++;
        while (i < used && items[i].y == items[start].y) ++i;
        rowStart[rows] = start;
        rowEnd[rows++] = i;
    }
    auto nearest = [&](int row, int center) {
        int best = rowStart[row];
        for (int j = best + 1; j < rowEnd[row]; ++j)
            if (std::abs(items[j].x + items[j].width / 2 - center) <
                std::abs(items[best].x + items[best].width / 2 - center)) best = j;
        return items[best].control;
    };
    for (int row = 0; row < rows; ++row) {
        const int start = rowStart[row], end = rowEnd[row];
        for (int i = start; i < end; ++i) {
            const int center = items[i].x + items[i].width / 2;
            // Vertical arrows change rows, retaining the nearest column.
            Field<void*>(items[i].nav, 0x88) = rows > 1 ?
                nearest((row + rows - 1) % rows, center) : items[i].control;
            Field<void*>(items[i].nav, 0x98) = rows > 1 ?
                nearest((row + 1) % rows, center) : items[i].control;
            // Horizontal arrows traverse a shared row. A slider keeps
            // its native horizontal behavior, and single controls keep links.
            if (end - start > 1 && !items[i].ownsHorizontal) {
                Field<void*>(items[i].nav, 0x90) = items[i > start ? i - 1 : end - 1].control;
                Field<void*>(items[i].nav, 0xa0) = items[i + 1 < end ? i + 1 : start].control;
            }
        }
    }
}
}

// A stationary mouse sample follows keyboard events every frame on Aspyr's Mac
// build. Keep the arrow-selected control until actual mouse movement or capture.
extern "C" __attribute__((visibility("default")))
void KmrpNoteArrowNavigation(void* control, int event, int value) {
    if (!control || !value || event < 0x3d || event > 0x40) return;
    void* panel = Field<void*>(control, 0x50);
    RepairNavigation(panel);
    void* manager = panel ? Field<void*>(panel, 0x20) : nullptr;
    if (!manager) return;
    keyboardManager = manager;
    keyboardMouseX = Field<int>(manager, 0);
    keyboardMouseY = Field<int>(manager, 4);
}

extern "C" __attribute__((visibility("default")))
int KmrpKeepKeyboardFocus(void* manager, int x, int y) {
    if (manager != keyboardManager || !manager) return 0;
    if (x != keyboardMouseX || y != keyboardMouseY || Field<void*>(manager, 0x18)) {
        keyboardManager = nullptr;
        return 0;
    }
    return 1;
}

// Both cursor-reading paths clamp converted coordinates here. Replace only the
// default desktop-point rectangle with the current render viewport. Explicit
// restricted rectangles keep their original bounds.
extern "C" __attribute__((visibility("default")))
void KmrpResizeMouseBounds() {
    using BoundsFn = void (*)(int*);
    int desktop[4] = {};
    reinterpret_cast<BoundsFn>(0x10001e36cUL)(desktop);
    auto* clip = reinterpret_cast<int*>(0x100678280UL);
    void* manager = *reinterpret_cast<void**>(0x100677ce0UL);
    bool isDesktop = true;
    for (int i = 0; i < 4; ++i) isDesktop &= clip[i] == desktop[i];
    const int width = manager ? Field<short>(manager, 0xa4) : 0;
    const int height = manager ? Field<short>(manager, 0xa6) : 0;
    if (!isDesktop || width < 640 || height < 480) return;
    clip[0] = clip[1] = 0;
    clip[2] = width;
    clip[3] = height;
}

// List boxes consume vertical arrows without invoking CSWGuiNavigable. Hand
// control back to the panel only at the first/last selectable entry. Interior
// selection and scrolling remain entirely native.
extern "C" __attribute__((visibility("default")))
int KmrpNavigateListBoundary(void* list, int event, int value) {
    if (!list || !value || event < 0x3d || event > 0x40) return 0;
    KmrpNoteArrowNavigation(list, event, value);
    const bool vertical = event == 0x3d || event == 0x3e;
    const int count = Field<int>(list, 0x350);
    const int selected = Field<short>(list, 0x37a);
    if (count < 0 || count > 4096 || selected < -1 || selected >= count) return 0;
    if (vertical && count > 0 && (selected < 0 || (event == 0x3d ? selected > 0 : selected < count - 1))) return 0;
    void* panel = Field<void*>(list, 0x50);
    if (!panel || Field<void*>(panel, 0x28) != list) return 0;
    const unsigned offset = event == 0x3d ? 0x88 : event == 0x3e ? 0x98 : event == 0x3f ? 0x90 : 0xa0;
    void* target = Field<void*>(list, offset);
    if (!target || target == list) return 0;
    void** controls = Field<void**>(panel, 0x30);
    const int controlsCount = Field<int>(panel, 0x38);
    if (!controls || controlsCount <= 0 || controlsCount > 512) return 0;
    bool bound = false;
    for (int i = 0; i < controlsCount; ++i) bound |= controls[i] == target;
    if (!bound) return 0;
    using SetFocusFn = void (*)(void*, void*, int);
    auto* table = Field<std::uintptr_t*>(panel, 0);
    reinterpret_cast<SetFocusFn>(table[0x18 / 8])(panel, target, 1);
    return 1;
}
