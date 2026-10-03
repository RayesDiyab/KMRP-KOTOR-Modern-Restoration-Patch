#include "K1RuntimeResolution.h"
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#ifdef KMRP_NATIVE_RUNTIME
#include "K1RuntimeEngine.h"
#include "K1RuntimeAssets.h"
#include "K1RuntimeLayout.h"
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
}

extern "C" int __cdecl KmrpAllowRuntimeResolutionK1(int width, int height)
{
    return KmrpRuntimeDimensions(width, height) ? 1 : 0;
}
extern "C" void __cdecl KmrpResolutionRequestedK1(void*, int width, int height)
{
#ifdef KMRP_NATIVE_RUNTIME
    if (KmrpRuntimeAssetsDimensions(width, height)) {
        if (!KmrpRuntimeEngineDimensions(width, height)) Log("engine-failed", width, height);
    } else Log("assets-failed", width, height);
#endif
    // A request is not an accepted mode. Sample the manager after native code
    // runs, in the GUI frame, and keep those two facts separate in the trace.
    g_requested = {width, height};
    Log("requested", width, height);
}
extern "C" void __cdecl KmrpResolutionObservedK1(void* manager)
{
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

// Same native allocator and ownership contract as the existing core hook.
// This independent module carries no controller state or controller backend.
extern "C" void __cdecl NativeFreeSaveBufferK1(void* buffer)
{
    if (buffer) reinterpret_cast<void(__cdecl*)(void*)>(0x006FA390)(buffer);
}
