// KMRP for macOS: the engine side of KMRP's menu layouts, as a KotOR Patch Manager patch.
//
// The Mac build runs on the widescreen patch (third_party/Kotor-Patch-Manager, Patches/K1WidescreenPatch)
// with UseGuiFileLayouts=1, which unlocks the resolution and lays nothing out, and KMRP's .gui
// set for the resolution in Override. On Windows, KMRP's executable also carries what those
// layouts need from the engine; this patch writes the same into KOTOR_Exe 1.4.0
// (C1FCB8D3...6D71) when the game starts:
//
//   resolution_sizes.cpp  the sizes KMRP's Windows installer writes per resolution: text-list
//                         rows, item and skill rows, the stack-count label, feat and power
//                         chain rows
//   listbox_padding.cpp   PADDING in a list box as a gutter on the scrollbar's side only
//                         (Windows gold v11 and v12)
//   area_map.cpp          the area map's canvas, marker overlay, marker positions and sizes
//
// The resolution is the one the widescreen patch runs at: [Graphics Options] ForceWidth and
// ForceHeight, which KMRP's installer writes, or the main display's size in points (both
// dimensions: the area map is sized from the width too). With
// UseGuiFileLayouts off, the widescreen patch lays out the vanilla menus itself, and this
// patch writes nothing.
//
// Every site is checked for its vanilla bytes (or, where noted, the widescreen patch's) before
// it is written, a group at a time: sizes that must move together are written together or not
// at all. A site holding anything else belongs to another patch and is left alone, with a line
// on stderr. macos/WINDOWS-PARITY.md maps each group to its Windows sites, and
// testing/regression/Test-KmrpLayoutPatch.py checks every site against the game binary.
//
// No C++ global in these files may need initialising at run time: the constructor below can run
// before such initialisers do (a global std::vector was still empty when it read it, 2026-09-29).
// The test checks the module has one initialiser, this one.
#include "sites.h"

#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <strings.h>

namespace kmrp {

std::vector<uint8_t> Bytes(std::initializer_list<uint8_t> bytes) { return bytes; }

std::vector<uint8_t> Int32(int32_t value) {
    std::vector<uint8_t> out(4);
    memcpy(out.data(), &value, 4);
    return out;
}

std::vector<uint8_t> Join(std::initializer_list<std::vector<uint8_t>> parts) {
    std::vector<uint8_t> out;
    for (const auto& part : parts) out.insert(out.end(), part.begin(), part.end());
    return out;
}

namespace {

// ------------------------------------------------------------------------ the resolution

struct GraphicsIni {
    int forceWidth = 0, forceHeight = 0;
    bool guiFileLayouts = false;
};

// The file and keys the widescreen patch reads (LoadGraphicsIniSettings in mac_widescreen.cpp).
GraphicsIni ReadGraphicsIni() {
    GraphicsIni ini;
    char path[1024];
    FILE* f = nullptr;
    if (const char* home = getenv("HOME")) {
        snprintf(path, sizeof path, "%s/Library/Application Support/Knights of the Old Republic/swkotor.ini", home);
        f = fopen(path, "r");
    }
    if (!f) f = fopen("swkotor.ini", "r");
    if (!f) return ini;
    char line[256];
    bool graphics = false;
    while (fgets(line, sizeof line, f)) {
        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '[') {
            graphics = strncasecmp(p, "[Graphics Options]", 18) == 0;
            continue;
        }
        char* eq = strchr(p, '=');
        if (!graphics || !eq) continue;
        const int value = atoi(eq + 1);
        if (strncasecmp(p, "ForceWidth", 10) == 0) ini.forceWidth = value;
        else if (strncasecmp(p, "ForceHeight", 11) == 0) ini.forceHeight = value;
        else if (strncasecmp(p, "UseGuiFileLayouts", 17) == 0) ini.guiFileLayouts = value != 0;
    }
    fclose(f);
    return ini;
}

struct CGRectShape { double x, y, width, height; };

// The main display's size in points, as the widescreen patch detects it; {0, 0} if unavailable.
void DisplayPointSize(int* width, int* height) {
    *width = *height = 0;
    void* cg = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY | RTLD_LOCAL);
    if (!cg) return;
    auto mainDisplay = reinterpret_cast<uint32_t (*)()>(dlsym(cg, "CGMainDisplayID"));
    auto bounds = reinterpret_cast<CGRectShape (*)(uint32_t)>(dlsym(cg, "CGDisplayBounds"));
    if (mainDisplay && bounds) {
        const CGRectShape rect = bounds(mainDisplay());
        *width = static_cast<int>(rect.width);
        *height = static_cast<int>(rect.height);
    }
    dlclose(cg);
}

// ------------------------------------------------------------------------ writing

// 4 KB pages, as the x86_64 process sees them (under Rosetta too).
const uintptr_t kPageMask = 0xFFF;

bool Write(const Site& site) {
    const uintptr_t first = site.address & ~kPageMask;
    const uintptr_t last = (site.address + site.value.size() + kPageMask) & ~kPageMask;
    if (vm_protect(mach_task_self(), first, last - first, FALSE,
                   VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) != KERN_SUCCESS) {
        return false;
    }
    memcpy(reinterpret_cast<void*>(site.address), site.value.data(), site.value.size());
    vm_protect(mach_task_self(), first, last - first, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
    return true;
}

// Writes every site of the group, or none if any of them does not hold its expected bytes.
void Apply(const Group& group) {
    for (const Site& site : group.sites) {
        if (site.expected.size() != site.value.size() ||
            memcmp(reinterpret_cast<const void*>(site.address), site.expected.data(), site.expected.size()) != 0) {
            fprintf(stderr, "[KMRP] %s: 0x%lx holds other bytes, group left alone:", group.name,
                    static_cast<unsigned long>(site.address));
            const uint8_t* found = reinterpret_cast<const uint8_t*>(site.address);
            for (size_t i = 0; i < site.expected.size(); i++) fprintf(stderr, " %02x", found[i]);
            fputc('\n', stderr);
            return;
        }
    }
    for (const Site& site : group.sites) {
        if (!Write(site)) {
            fprintf(stderr, "[KMRP] %s: could not write 0x%lx\n", group.name, static_cast<unsigned long>(site.address));
            return;
        }
    }
}

// A page for code and data the game's own instructions must reach with a 32-bit displacement
// (a 5-byte call, a RIP-relative operand): within 2 GB of its code at 0x100000000, above its
// image, where KotorPatcher also places its wrappers. Returns 0 if none is free.
uintptr_t NearPage() {
    for (mach_vm_address_t address = 0x101000000; address < 0x170000000; address += 0x1000000) {
        mach_vm_address_t page = address;
        if (mach_vm_allocate(mach_task_self(), &page, 0x1000, VM_FLAGS_FIXED) == KERN_SUCCESS) {
            return static_cast<uintptr_t>(page);
        }
    }
    return 0;
}

}  // namespace

std::vector<Group> Groups(int width, int height, uintptr_t nearPage) {
    std::vector<Group> groups;
    AddResolutionSizes(groups, height);
    AddListboxPadding(groups);
    AddAreaMap(groups, width, height, nearPage);
    return groups;
}

namespace {

__attribute__((constructor)) void ApplyLayoutSupport() {
    const GraphicsIni ini = ReadGraphicsIni();
    if (!ini.guiFileLayouts) return;
    int width = ini.forceWidth, height = ini.forceHeight;
    if (width < 640 || height < 480) DisplayPointSize(&width, &height);
    if (width < 640 || height < 480) return;

    uintptr_t page = NearPage();
    if (page) {
        const std::vector<uint8_t> contents = AreaMapPage(height);
        memcpy(reinterpret_cast<void*>(page), contents.data(), contents.size());
        vm_protect(mach_task_self(), page, 0x1000, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
    } else {
        fprintf(stderr, "[KMRP] no page free near the game's code: area map positions left vanilla\n");
    }
    for (const Group& group : Groups(width, height, page)) Apply(group);
}

}  // namespace
}  // namespace kmrp

// For the regression test: writes "group<TAB>address<TAB>expected hex<TAB>value hex" lines,
// one per site, for a screen size and a near page's address, then "rowscale<TAB>s" (the
// text-list row stub's factor), "overlay<TAB>w<TAB>h" (the map stubs') and "page<TAB>hex" (the
// near page's contents). Not called by the game.
extern "C" float kmrp_row_scale;
extern "C" int32_t kmrp_overlay_width, kmrp_overlay_height;
extern "C" void KMRP_LayoutGroups(int width, int height, uintptr_t nearPage, FILE* out) {
    for (const kmrp::Group& group : kmrp::Groups(width, height, nearPage)) {
        for (const kmrp::Site& site : group.sites) {
            fprintf(out, "%s\t%lx\t", group.name, static_cast<unsigned long>(site.address));
            for (uint8_t b : site.expected) fprintf(out, "%02x", b);
            fputc('\t', out);
            for (uint8_t b : site.value) fprintf(out, "%02x", b);
            fputc('\n', out);
        }
    }
    fprintf(out, "rowscale\t%.9g\n", kmrp_row_scale);
    fprintf(out, "overlay\t%d\t%d\npage\t", kmrp_overlay_width, kmrp_overlay_height);
    for (uint8_t b : kmrp::AreaMapPage(height)) fprintf(out, "%02x", b);
    fputc('\n', out);
}

// For the regression test: the stubs' bytes, "stub<TAB>name<TAB>hex" lines. Not called by the game.
extern "C" const uint8_t kmrp_rows_stub[], kmrp_rows_stub_end[];
extern "C" const uint8_t kmrp_scroll_stub[], kmrp_scroll_stub_end[];
extern "C" const uint8_t kmrp_button_stub[], kmrp_button_stub_end[];
extern "C" const uint8_t kmrp_notes_stub[], kmrp_map_stubs_end[];
extern "C" void KMRP_LayoutStubs(FILE* out) {
    const struct { const char* name; const uint8_t *begin, *end; } stubs[] = {
        {"rows", kmrp_rows_stub, kmrp_rows_stub_end},
        {"scroll", kmrp_scroll_stub, kmrp_scroll_stub_end},
        {"button", kmrp_button_stub, kmrp_button_stub_end},
        {"map", kmrp_notes_stub, kmrp_map_stubs_end},
    };
    for (const auto& stub : stubs) {
        fprintf(out, "stub\t%s\t", stub.name);
        for (const uint8_t* p = stub.begin; p < stub.end; p++) fprintf(out, "%02x", *p);
        fputc('\n', out);
    }
}
