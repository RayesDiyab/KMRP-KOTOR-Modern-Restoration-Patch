// KMRP for macOS: ShaeMyName's K1 Marked Empty Containers (issue 43), at the Aspyr build's addresses.
//
// Appends " (empty)" to the hover name of a container or corpse that holds nothing. Windows installs
// KotOR Patch Manager's own K1MarkedEmptyContainers.kpatch, 141 bytes for the Windows 1.03 executable
// only (Patches/K1MarkedEmptyContainers/kotor1.hooks.toml); this is the same logic for KOTOR_Exe
// 1.4.0, C1FCB8D3...6D71, with ShaeMyName's permission as on Windows.
//
// CSWGuiTargetActionMenu::UpdateNameLabel (0x100230cb4) builds the hovered object's name in a
// temporary CExoString and calls SetNameLabel (0x1002309c6; Windows 0x685AF0) at 0x100230e8e
// (Windows 0x685E69). The hook replaces that call, changing the temporary first, so the object's real name,
// the loot window's title and scripting are untouched.
//
//   0x100230e87  lea  rsi, [rbp-0x28]    the name
//   0x100230e8b  mov  rdi, r15           the menu
//   0x100230e8e  call 0x1002309c6        <- here
//   0x100230e93  mov  dword [r15+0x1d1c], 0x3f800000
//
// The hovered object does not survive to that call: Windows reads it from the routine's frame, but on
// the Mac it is only in rbx, which 0x100230e53 reuses for the health bar. So a second hook keeps it as
// the routine starts (KmrpHoverObject).
//
// What Windows' bytes do, and the Mac's for each:
//
//   is it a placeable: the client vtable        CSWCPlaceable::GetServerPlaceable (0x10028310c) on any
//                                               object: its server object's slot +0x98, which is the
//                                               object in a placeable (0x100417086) and 0 in every
//                                               other (0x1002843c0)
//   server object +0x324, has an inventory      +0x490, which GetItemCount tests itself
//   CSWSPlaceable::GetItemCount(0)              0x100416e98
//   CExoString::operator=(const char*)          a string made and assigned, as the Mac's is inlined
#include <cstdio>
#include <cstring>

#include "../kmrp-layout/options.h"

namespace {

struct ExoString { char* text; int capacity; int pad; };

const auto SetNameLabel = reinterpret_cast<void (*)(void*, ExoString*)>(0x1002309c6);
const auto GetServerPlaceable = reinterpret_cast<char* (*)(void*)>(0x10028310c);
const auto GetItemCount = reinterpret_cast<int (*)(char*, int)>(0x100416e98);
const auto MakeString = reinterpret_cast<void (*)(ExoString*, const char*)>(0x10034cca8);
const auto FreeString = reinterpret_cast<void (*)(ExoString*)>(0x10034cdf2);
const auto AssignString = reinterpret_cast<void (*)(ExoString*, ExoString*)>(0x10034ce1e);

const std::size_t kHasInventory = 0x490;

bool Empty(void* object) {
    if (!object) return false;
    char* const placeable = GetServerPlaceable(object);
    if (!placeable || !*reinterpret_cast<int*>(placeable + kHasInventory)) return false;
    return GetItemCount(placeable, 0) == 0;
}

}  // namespace

// UpdateNameLabel's second instruction after its frame, rsi the hovered object or null.
static void* g_hovered = nullptr;
extern "C" __attribute__((visibility("default"))) void KmrpHoverObject(void* object) { g_hovered = object; }

// A relative call, so the handler makes it and always consumes.
extern "C" __attribute__((visibility("default"))) int KmrpHoverName(void* menu, ExoString* name) {
    void* const object = g_hovered;
    static const bool on = kmrp::PatchOption("marked-empty", 1) != 0;
    if (on && name && name->text && name->text[0] && Empty(object)) {
        char text[256];
        std::snprintf(text, sizeof text, "%s (empty)", name->text);
        ExoString marked{};
        MakeString(&marked, text);
        AssignString(name, &marked);
        FreeString(&marked);
    }
    SetNameLabel(menu, name);
    return 1;
}
