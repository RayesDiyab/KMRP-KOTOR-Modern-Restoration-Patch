// A change of size, run on K1RuntimeLayout.cpp itself. Test-RuntimeRelayout.py writes the
// layout files and builds this; panels and controls are plain memory with the engine's
// offsets, and a control's SetExtent is its table's second slot, as in the game.
#include "../../src/controller-native/K1RuntimeLayout.cpp"
#include <cstdio>
#include <set>

// What K1RuntimeLayout.cpp calls that this test has no part in.
void KmrpRuntimeLog(const char* line) { std::puts(line); }
void KmrpTextOptionsDestroyedK1(void*) {}
void KmrpHudOptionsDestroyedK1(void*) {}
void KmrpPcHudForgetK1(void*) {}
void KmrpTextLayoutFontsChangedK1() {}
void KmrpTextLayoutTrackPanelK1(void*, const char*) {}
void KmrpTextLayoutTrackControlK1(void*, void*, const char*) {}
void KmrpTextLayoutForgetControlK1(void*) {}
void KmrpTextLayoutForgetPanelK1(void*) {}
void KmrpTextRowsForgetK1(void*) {}
int KmrpIconSizePercentK1() { return 100; }
void KmrpPartyPortraitsK1(void*) {}

// The Container's record, K1TextLayout.cpp's half: tested in native_text_layout_harness.
static std::map<void*, int> widenedBy;
static std::set<void*> forgotten;
int KmrpTextLayoutWidenedK1(void*, void* control)
{
    const auto found = widenedBy.find(control);
    return found == widenedBy.end() ? 0 : found->second;
}
void KmrpTextLayoutForgetWidenedK1(void* panel) { forgotten.insert(panel); }

static std::wstring g_folder, g_size;
std::wstring KmrpRuntimeLayoutFile(const std::wstring& name) { return g_folder + L"\\" + g_size + L"\\" + name; }

namespace harness {
struct Memory { alignas(8) unsigned char data[0x400]{}; operator void*() { return data; } };
static int failures = 0;
static void Check(bool ok, const char* what)
{
    std::printf("%s %s\n", ok ? "ok  " : "FAIL", what);
    if (!ok) ++failures;
}
static void __fastcall RecordExtent(void* self, void*, const Extent* extent) { At<Extent>(self, 4) = *extent; }
static std::uintptr_t table[4] = {0, reinterpret_cast<std::uintptr_t>(&RecordExtent), 0, 0};
static void Make(Memory& object, void* panel, const Extent& extent)
{
    At<std::uintptr_t>(object, 0) = reinterpret_cast<std::uintptr_t>(table);
    At<Extent>(object, 4) = extent;
    At<void*>(object, 0x34) = panel;
}
struct Label { const char* text; unsigned size; };
static void Bind(void* panel, void* control, const char* tag)
{
    Label label{tag, static_cast<unsigned>(std::strlen(tag) + 1)};
    void* controlSlot = control;
    void* labelSlot = &label;
    int filed = 1;
    KmrpPanelControlK1(panel, &controlSlot, &labelSlot, &filed);
}
static void Load(void* panel, const char* resource) { KmrpPanelLayoutStartK1(panel, &resource); }
static bool Is(void* control, const Extent& want) { return At<Extent>(control, 4) == want; }
static void Size(void* manager, short width, short height, const wchar_t* folder)
{
    At<short>(manager, 0x6C) = width;
    At<short>(manager, 0x6E) = height;
    g_size = folder;
}
}

int wmain(int, wchar_t** argv)
{
    using namespace harness;
    g_folder = argv[1];
    Memory manager, broken, container, ok, give, list, options, moved;
    Size(manager, 1280, 720, L"1280x720");
    KmrpRuntimeLayoutDimensions(manager, 1280, 720);
    At<void*>(broken, 0x18) = manager;
    At<void*>(container, 0x18) = manager;
    At<void*>(options, 0x18) = manager;

    // A panel with a file the new size cannot read, loaded first by map order or not.
    Make(broken, nullptr, {0, 0, 100, 100});
    Load(broken, "brokenroot");
    // The Container, widened by 28 at 1280x720.
    Make(container, nullptr, {326, 160, 628, 400});
    Load(container, "container");
    Make(ok, container, {20, 340, 128, 40});
    Make(give, container, {160, 340, 128, 40});
    Make(list, container, {20, 40, 588, 280});
    Bind(container, ok, "BTN_OK");
    Bind(container, give, "BTN_GIVEITEMS");
    Bind(container, list, "LB_ITEMS");
    widenedBy[ok] = widenedBy[give] = widenedBy[list] = 28;
    // A screen whose buttons the engine moved down after loading: that stays, scaled.
    Make(options, nullptr, {340, 160, 600, 400});
    Load(options, "optmain");
    Make(moved, options, {20, 120, 100, 40});     // the file says 100 for the top
    Bind(options, moved, "BTN_FIRST");

    Size(manager, 1920, 1080, L"1920x1080");
    Check(KmrpRuntimeLayoutDimensions(manager, 1920, 1080), "the change of size is answered");

    Check(Is(ok, {30, 510, 150, 60}), "Container: OK at its file's place, KMRP's widening not kept");
    Check(Is(give, {240, 510, 150, 60}), "Container: Give at its file's place");
    Check(Is(list, {30, 60, 840, 420}), "Container: the list at its file's place");
    Check(At<Extent>(container, 4).width == 900, "Container: the panel at its file's width");
    Check(forgotten.count(container) == 1, "Container: the widening's record ended, so the next frame fits afresh");
    // GUI-3: the screen after the odd one was still laid out.
    Check(Is(moved, {30, 180, 150, 60}), "a panel after an odd file is still changed, the engine's 20 px scaled to 30");
    Check(At<Extent>(options, 4).width == 900, "its panel too");
    Check(Is(broken, {0, 0, 100, 100}), "the odd panel itself keeps its place");

    // Back: the same pixels as before, and the file read once, not every frame.
    widenedBy.clear();
    Size(manager, 1280, 720, L"1280x720");
    Check(KmrpRuntimeLayoutDimensions(manager, 1280, 720), "and back");
    Check(Is(moved, {20, 120, 100, 40}), "the engine's addition returns to its pixels");
    Check(Is(ok, {20, 340, 100, 40}), "Container: OK at its file's width, no widening left");

    KmrpPanelDestroyedK1(broken);
    KmrpPanelDestroyedK1(container);
    KmrpPanelDestroyedK1(options);
    std::printf("%d failed\n", failures);
    return failures ? 1 : 0;
}
