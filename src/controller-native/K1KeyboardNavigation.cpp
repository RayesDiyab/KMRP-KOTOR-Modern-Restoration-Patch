// Windows CD/GOG/Steam 1.03, preferred VAs. Port of the Mac row-navigation
// repair, with Windows object layouts and thiscall callbacks. Keyboard arrows
// arrive as 0x3D..0x40; the controller's 0x2F..0x32 path remains independent.
#include <algorithm>
#include <cstdint>
#include <cstdlib>

namespace {
template<class T> T& Field(void* p, unsigned offset) {
    return *reinterpret_cast<T*>(static_cast<char*>(p) + offset);
}
using CastFn = void* (__thiscall*)(void*);
using FocusFn = void (__thiscall*)(void*, void*, int);
using InputFn = int (__thiscall*)(void*, int, int);
constexpr std::uintptr_t ListInput = 0x0041CE20;
constexpr std::uintptr_t SliderInput = 0x0041ADF0;
void* keyboardManager = nullptr;
void* keyboardPanel = nullptr;
void* keyboardControl = nullptr;
int keyboardX = 0, keyboardY = 0;
int keyboardPanelCount = 0, keyboardModalCount = 0;

bool Arrow(int event, int value) {
    return value != 0 && event >= 0x3D && event <= 0x40;
}
int Direction(int event) {
    return event == 0x3D ? 0 : event == 0x3F ? 1 : event == 0x3E ? 2 : 3;
}
void* Navigable(void* c) {
    auto* table = Field<std::uintptr_t*>(c, 0);
    return reinterpret_cast<CastFn>(table[0x4C / 4])(c);
}
bool SelectableList(void* c, std::uintptr_t* table) {
    if (table[0x3C / 4] != ListInput) return false;
    void** entries = Field<void**>(c, 0x29C);
    const int count = Field<int>(c, 0x2A0);
    if (!entries || count <= 0 || count > 4096) return false;
    for (int i = 0; i < count; ++i) {
        void* entry = entries[i];
        if (entry && (Field<unsigned char>(entry, 0x44) & 8) && Navigable(entry)) return true;
    }
    return false;
}

struct Item { void* control; void* nav; int x, y, id, width; };

// Compute a keyboard-only neighbour instead of rewriting the shared MOVETO
// fields. Preserve complete resource-defined vertical cycles; otherwise use
// the Mac repair's rows and nearest column. Never follow an unbound pointer.
void* Target(void* panel, void* current, int event, bool& repaired) {
    repaired = false;
    if (!panel) return nullptr;
    void** controls = Field<void**>(panel, 0x20);
    const int count = Field<int>(panel, 0x24);
    if (!controls || count <= 0 || count > 512) return nullptr;
    Item items[512];
    int used = 0;
    for (int id = 0; id < count; ++id) {
        void* c = controls[id];
        if (!c || Field<int>(c, 0x50) != id || Field<void*>(c, 0x34) != panel) continue;
        if ((Field<unsigned char>(c, 0x44) & 0x2A) != 0x0A) continue;
        auto* table = Field<std::uintptr_t*>(c, 0);
        const int events = Field<int>(c, 0x3C);
        if (!(Field<void*>(c, 0x38) && events > 0 && events <= 64) && !SelectableList(c, table)) continue;
        if (Field<int>(c, 0x0C) <= 0 || Field<int>(c, 0x10) <= 0) continue;
        void* nav = Navigable(c);
        if (nav) items[used++] = {c, nav, Field<int>(c, 4), Field<int>(c, 8), id, Field<int>(c, 0x0C)};
    }
    auto indexOf = [&](void* c) {
        for (int i = 0; i < used; ++i) if (items[i].control == c) return i;
        return -1;
    };
    int active = indexOf(current);
    if (used < 2 || active < 0) return nullptr;
    bool complete = true, sharedRow = false;
    for (unsigned offset : {0x5CU, 0x64U}) {
        bool seen[512] = {};
        int index = 0;
        for (int step = 0; step < used; ++step) {
            if (index < 0 || seen[index]) { complete = false; break; }
            seen[index] = true;
            index = indexOf(Field<void*>(items[index].nav, offset));
        }
        if (index != 0) complete = false;
    }
    for (int i = 0; i < used; ++i)
        for (int j = i + 1; j < used; ++j) sharedRow |= items[i].y == items[j].y;
    if (complete && !sharedRow) {
        void* target = Field<void*>(items[active].nav, 0x5C + Direction(event) * 4);
        return indexOf(target) >= 0 ? target : nullptr;
    }
    std::sort(items, items + used, [](const Item& a, const Item& b) {
        return a.y != b.y ? a.y < b.y : a.x != b.x ? a.x < b.x : a.id < b.id;
    });
    active = indexOf(current);
    int starts[512], ends[512], rows = 0, activeRow = 0;
    for (int i = 0; i < used;) {
        const int start = i++;
        while (i < used && items[i].y == items[start].y) ++i;
        starts[rows] = start; ends[rows] = i;
        if (active >= start && active < i) activeRow = rows;
        ++rows;
    }
    const int direction = Direction(event);
    if (direction == 1 || direction == 3) {
        const int start = starts[activeRow], end = ends[activeRow];
        if (end - start < 2) return nullptr;
        repaired = true;
        const int next = direction == 1 ? (active > start ? active - 1 : end - 1)
                                       : (active + 1 < end ? active + 1 : start);
        return items[next].control;
    }
    if (rows < 2) return nullptr;
    const int row = (activeRow + (direction == 0 ? rows - 1 : 1)) % rows;
    const int center = items[active].x + items[active].width / 2;
    int best = starts[row];
    for (int j = best + 1; j < ends[row]; ++j)
        if (std::abs(items[j].x + items[j].width / 2 - center) <
            std::abs(items[best].x + items[best].width / 2 - center)) best = j;
    repaired = true;
    return items[best].control;
}

void Note(void* panel) {
    void* manager = panel ? Field<void*>(panel, 0x18) : nullptr;
    keyboardManager = manager;
    keyboardPanel = panel;
    keyboardControl = panel ? Field<void*>(panel, 0x1C) : nullptr;
    if (manager) {
        keyboardX = Field<int>(manager, 0); keyboardY = Field<int>(manager, 4);
        keyboardPanelCount = Field<int>(manager, 0x8C);
        keyboardModalCount = Field<int>(manager, 0x98);
    }
}
void Focus(void* panel, void* target) {
    auto* table = Field<std::uintptr_t*>(panel, 0);
    reinterpret_cast<FocusFn>(table[0x08 / 4])(panel, target, 1);
    Note(panel);
}
void BaseInput(void* control, int event, int value) {
#ifdef KMRP_KEYBOARD_TEST
    (void)control; (void)event; (void)value;
#else
    reinterpret_cast<InputFn>(0x00418750)(control, event, value);
#endif
}
}

// Rewrite only a handled event to the unused 0x41. The original entry can then
// execute normally, including its EAX load and test, without a consumed exit.
extern "C" int __cdecl KeyboardNavigateK1(void* control, int* eventSlot, int* valueSlot) {
    if (!control || !eventSlot || !valueSlot) return 0;
    const int event = *eventSlot, value = *valueSlot;
    if (!Arrow(event, value)) return 0;
    void* panel = Field<void*>(control, 0x34);
    if (!panel || Field<void*>(panel, 0x1C) != control) return 0;
    Note(panel);
    // Sliders own only the axis along which they slide.
    auto* table = Field<std::uintptr_t*>(control, 0);
    if (table[0x3C / 4] == SliderInput) {
        const bool horizontal = Field<int>(control, 0x10) <= Field<int>(control, 0x0C);
        if (horizontal == (event == 0x3F || event == 0x40)) return 0;
    }
    bool repaired = false;
    void* target = Target(panel, control, event, repaired);
    if (!repaired && target) keyboardControl = target; // native dispatch moves next
    if (!repaired || !target || target == control) return 0;
    Focus(panel, target);
    BaseInput(control, event, value);
    *eventSlot = 0x41;
    return 1;
}

extern "C" int __cdecl KeyboardListBoundaryK1(void* list, int* eventSlot, int* valueSlot) {
    if (!list || !eventSlot || !valueSlot) return 0;
    const int event = *eventSlot, value = *valueSlot;
    if (!Arrow(event, value)) return 0;
    void* panel = Field<void*>(list, 0x34);
    if (!panel || Field<void*>(panel, 0x1C) != list) return 0;
    Note(panel);
    const int count = Field<int>(list, 0x2A0);
    const int selected = Field<short>(list, 0x2C6);
    if (count < 0 || count > 4096 || selected < -1 || selected >= count) return 0;
    if (count > 0 && selected < 0) return 0; // native initialization of selection
    // Skip nonselectable entries when deciding whether the native list can move.
    void** entries = Field<void**>(list, 0x29C);
    if (count > 0 && !entries) return 0;
    if (event == 0x3D || event == 0x3E) {
        const int step = event == 0x3D ? -1 : 1;
        for (int i = selected + step; i >= 0 && i < count; i += step)
            if (entries[i] && (Field<unsigned char>(entries[i], 0x44) & 8)) return 0;
    }
    bool repaired = false;
    void* target = Target(panel, list, event, repaired);
    if (!target || target == list) return 0;
    Focus(panel, target);
    BaseInput(list, event, value);
    *eventSlot = 0x41;
    return 1;
}

// After native coordinate storage and 3D cursor work, before GUI hit testing.
// Mouse capture, movement, panel changes, and controller focus changes release
// the latch. No shared navigation links or controller state are modified.
extern "C" int __cdecl KeyboardKeepFocusK1(void* manager, int x, int y) {
    if (!manager || manager != keyboardManager) return 0;
    bool bound = false;
    void** panels = Field<void**>(manager, 0x88);
    const int count = Field<int>(manager, 0x8C);
    if (panels && count > 0 && count <= 512)
        for (int i = 0; i < count; ++i) bound |= panels[i] == keyboardPanel;
    if (!bound || count != keyboardPanelCount || Field<int>(manager, 0x98) != keyboardModalCount ||
        x != keyboardX || y != keyboardY || Field<void*>(manager, 0x10) ||
        Field<void*>(manager, 0x24) || Field<void*>(keyboardPanel, 0x1C) != keyboardControl) {
        keyboardManager = keyboardPanel = keyboardControl = nullptr;
        return 0;
    }
    return 1;
}
