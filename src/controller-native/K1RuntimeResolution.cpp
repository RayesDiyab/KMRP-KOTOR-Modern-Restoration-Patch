#include "K1RuntimeResolution.h"
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <array>
#include <set>
#include <intrin.h>
#ifdef KMRP_NATIVE_RUNTIME
#include "K1RuntimeEngine.h"
#include "K1RuntimeAssets.h"
#include "K1RuntimeLayout.h"
#include "K1RuntimeNvidia.h"
#endif

namespace {
// Written only at GUI size-change/frame hooks, on the game's GUI thread.
struct Dimensions { int width = 0, height = 0; } g_requested, g_observed;
void Log(const char* event, int width, int height)
{
    wchar_t path[MAX_PATH];
    DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? wcsrchr(path, L'\\') : nullptr;
    if (!slash) return;
    if (wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path),
                 L"kmrp-native-preview.log")) return;
    FILE* file = nullptr;
    if (_wfopen_s(&file, path, L"a") || !file) return;
    fprintf(file, "%lu %s %dx%d\n", GetTickCount(), event, width, height);
    fclose(file);
}
bool ReadViewport(void* manager, Dimensions& result)
{
    if (!manager) return false;
    const auto at = reinterpret_cast<std::uintptr_t>(manager) + 0x6c;
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(reinterpret_cast<void*>(at), &info, sizeof info) ||
        info.State != MEM_COMMIT || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)) ||
        !(info.Protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                          PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)) ||
        at + 4 > reinterpret_cast<std::uintptr_t>(info.BaseAddress) + info.RegionSize) return false;
    short size[2];
    std::memcpy(size, reinterpret_cast<void*>(at), sizeof size);
    result = {size[0], size[1]};
    return KmrpRuntimeDimensions(result.width, result.height);
}
// Put this size's resources and engine operands in place. Both keep the size
// they last committed, so a repeated request costs two comparisons.
void Prepare(int width, int height)
{
#ifdef KMRP_NATIVE_RUNTIME
    if (KmrpRuntimeAssetsDimensions(width, height)) {
        if (!KmrpRuntimeEngineDimensions(width, height)) Log("engine-failed", width, height);
    } else Log("assets-failed", width, height);
#else
    (void)width; (void)height;
#endif
}

#ifdef KMRP_NATIVE_RUNTIME
// Re-read every font's TXI after a size change.
//
// The window re-creation reloads each texture's image from the current files,
// but a texture's TXI is parsed once, when the texture is created (0x0042359C),
// and never again. A font's glyph metrics and atlas coordinates are that parsed
// TXI: the 0x30-byte object at texture+0x38 is the CAurFontInfo every CAurFont
// of that name points at. So after a switch the new atlas was drawn with the old
// size's coordinates (measured 2026-10-04: 1920x1080 -> 1920x1200 garbled every
// label, and switching back restored them).
//
// 0x00422AF0 is the engine's own TXI load, __thiscall (texture, name). On a
// texture that already has the object it parses into it in place; the glyph
// arrays at +0x18 and +0x24 are resized by the parser (0x00421FF0 -> 0x00421310),
// so every font keeps its pointer. Only fonts keep the object at all: the load
// frees it when the TXI gave no glyph coordinates (0x00422C19).
//
// 0x007A4798 is the engine's array of textures and 0x007A479C its count: the
// lookup by name walks it (0x00420AE0). The array at 0x007A4770 is not it: that
// one is a queue of textures just created, empty by the time a switch happens,
// which is why the first version of this reloaded nothing. The name the load
// takes is the string at +0x98, as 0x0042358B passes it.
void ReloadFontMetrics()
{
    void** const textures = *reinterpret_cast<void***>(0x007A4798);
    const int count = *reinterpret_cast<const int*>(0x007A479C);
    if (!textures || count <= 0 || count > 0x100000) return;
    int reloaded = 0;
    for (int i = 0; i < count; ++i) {
        void* const texture = textures[i];
        if (!texture || !*reinterpret_cast<void**>(static_cast<char*>(texture) + 0x38)) continue;
        reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x00422AF0)(
            texture, static_cast<const char*>(texture) + 0x98);
        ++reloaded;
    }
    Log("font-metrics", reloaded, count);
}
#endif
}

#ifdef KMRP_NATIVE_RUNTIME
// One row per resolution and refresh rate in Graphics -> Screen Resolution.
//
// The dialog's constructor (0x006E0710) adds a row for every mode
// EnumDisplaySettingsA reports that is 32-bit and 60 Hz or more (0x006E0978,
// 0x006E0986). Windows reports the same size and rate once for each scaling and
// scan-order variant the driver has, so every row appeared two or three times
// (play-tested 2026-10-04). The game always did this; it showed once the list
// held every size instead of a handful.
//
// Only the constructor's own two calls are filtered: mode 0 at 0x006E094F and the
// loop's next mode at 0x006E0BC3 (`call dword ptr [0x0073D3E4]`, six bytes each,
// returning to 0x006E0955 and 0x006E0BC9). Filtering the first alone changed
// nothing, since every repeat comes from the loop. A repeat
// is handed back as a mode that is not 32-bit, which the constructor's own test
// then skips. The first of each is kept, so a row's value is still a real mode
// index. Every other caller, the mode switch among them, gets Windows' answer
// untouched.
namespace {
using EnumModesFn = BOOL(WINAPI*)(LPCSTR, DWORD, DEVMODEA*);
EnumModesFn g_enumModes = nullptr;

BOOL WINAPI EnumModesOnce(LPCSTR device, DWORD index, DEVMODEA* mode)
{
    const BOOL ok = g_enumModes(device, index, mode);
    const void* const caller = _ReturnAddress();
    if (!ok || !mode || (caller != reinterpret_cast<void*>(0x006E0955) &&
                         caller != reinterpret_cast<void*>(0x006E0BC9))) return ok;
    static std::set<std::array<DWORD, 4>> seen;
    if (index == 0) seen.clear();
    if (!seen.insert({mode->dmPelsWidth, mode->dmPelsHeight, mode->dmBitsPerPel, mode->dmDisplayFrequency}).second)
        mode->dmBitsPerPel = 0;
    return ok;
}
}

// The game's import slot for EnumDisplaySettingsA. Left alone unless it holds
// exactly user32's function: anything else there is someone else's hook.
void KmrpInstallModeListFilter()
{
    auto slot = reinterpret_cast<EnumModesFn*>(0x0073D3E4);
    HMODULE user = GetModuleHandleW(L"user32.dll");
    auto real = user ? reinterpret_cast<EnumModesFn>(GetProcAddress(user, "EnumDisplaySettingsA")) : nullptr;
    // The slot is an address in the game. In any other process (the regression test
    // loads this module by itself) nothing need be there: reading it faulted inside
    // DllMain and the load failed (2026-10-04).
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(slot, &info, sizeof info) || info.State != MEM_COMMIT ||
        (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return;
    DWORD old = 0;
    if (!real || g_enumModes || *slot != real || !VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) return;
    g_enumModes = real;
    *slot = &EnumModesOnce;
    VirtualProtect(slot, sizeof *slot, old, &old);
}
#endif

// The native mode switch (0x005F1830) has stored the new mode's size at
// 0x0078D1D4/0x0078D1D8 and is about to re-create the window (0x00403800), which
// reloads every texture. The new size's files must be in place before that:
// swapping them at SetSize, which the switch calls afterwards, left the fonts'
// old atlas images in video memory under the new glyph metrics until an Alt-Tab
// reloaded them (play-tested 2026-10-04).
extern "C" void __cdecl KmrpModeSwitchK1()
{
    const int width = *reinterpret_cast<const int*>(0x0078D1D4);
    const int height = *reinterpret_cast<const int*>(0x0078D1D8);
    if (!KmrpRuntimeDimensions(width, height)) return;
    Prepare(width, height);
    Log("switching", width, height);
#ifdef KMRP_NATIVE_RUNTIME
    ReloadFontMetrics();
#endif
}

extern "C" int __cdecl KmrpAllowRuntimeResolutionK1(const int* width, const int* height)
{
    if (!width || !height || !KmrpRuntimeDimensions(*width, *height)) return 0;
#ifdef KMRP_NATIVE_RUNTIME
    // And one KMRP has a layout for: the installer refuses the others.
    if (!KmrpRuntimeAssetsCovers(*width, *height)) return 0;
#endif
    return 1;
}
extern "C" void __cdecl KmrpResolutionRequestedK1(void*, const int* widthSlot, const int* heightSlot)
{
    if (!widthSlot || !heightSlot) return;
    const int width = *widthSlot, height = *heightSlot;
    Prepare(width, height);
    // A request is not an accepted mode. Sample the manager after native code
    // runs, in the GUI frame, and keep those two facts separate in the trace.
    g_requested = {width, height};
    Log("requested", width, height);
}
extern "C" void __cdecl KmrpResolutionObservedK1(void* manager)
{
#ifdef KMRP_NATIVE_RUNTIME
    // The first GUI frame: the game's window and its OpenGL context exist, so the
    // driver is loaded. The installer makes this check at install time.
    KmrpNvidiaPresentOnce();
#endif
    Dimensions actual;
    if (!ReadViewport(manager, actual)) return;
    if (actual.width == g_observed.width && actual.height == g_observed.height) return;
#ifdef KMRP_NATIVE_RUNTIME
    if (!KmrpRuntimeLayoutDimensions(manager, actual.width, actual.height)) {
        Log("layout-failed", actual.width, actual.height);
        return;
    }
#endif
    g_observed = actual;
    Log("observed", actual.width, actual.height);
}

#ifndef KMRP_NATIVE_RUNTIME
// The preview module only: the standalone module compiles K1NativeJoystick.cpp,
// which has the hook itself.
// Same native allocator and ownership contract as the existing core hook.
// This independent module carries no controller state or controller backend.
extern "C" void __cdecl NativeFreeSaveBufferK1(void* buffer)
{
    if (buffer) reinterpret_cast<void(__cdecl*)(void*)>(0x006FA390)(buffer);
}
#endif
