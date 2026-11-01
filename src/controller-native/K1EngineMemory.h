#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Reading the game's objects: a field at an offset, an engine routine at an address, and
// whether an address is one, and its memory readable now.
// Until 2026-10-31 this lived in K1NativeJoystick.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md). Inline, as they were inside that
// file: moved into a .cpp of their own, every check became a call (2026-10-31, measured
// function by function).
// The one copy of each since 2026-11-01 (issue 82, F4): At had four names across the files,
// and three more copies of the memory check existed. EngineFn is not used where a test
// harness swaps the engine's routines (K1TextLayout, K1TextOptions, K1TextRows: their Fn).
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <cstddef>
#include <cstdint>

template <typename T> T& At(const void* base, std::ptrdiff_t offset)
{
    return *reinterpret_cast<T*>(reinterpret_cast<std::uintptr_t>(base) + offset);
}

template <typename T> T* FieldAt(void* base, std::size_t offset)
{
    return &At<T>(base, static_cast<std::ptrdiff_t>(offset));
}

template <typename T> T EngineFn(std::uintptr_t address)
{
    return reinterpret_cast<T>(address);
}

// Send a GUI control an input event as the game's panels do: its HandleInputEvent, vtable
// +0x3C (CSWGuiControl's is 0x00418750). That function stores the value at +0x4C and the
// event at +0x48 before it calls the handler registered for the event, and the HUD's
// handlers exit when +0x4C is 0: called directly they answered whatever the field held, as
// nothing else sets it (0x0068B057, 0x0068B0A4; audit PAD-1, issues 88 and 90). The Mac port
// has always pressed this way (hud.cpp Press).
inline void SendControlEventK1(void* control, int event, int value = 1)
{
    using HandleInputFn = void(__thiscall*)(void*, int, int);
    reinterpret_cast<HandleInputFn>(At<std::uintptr_t*>(control, 0)[0x3C / 4])(control, event, value);
}

inline bool LooksLikePointerK1(const void* p)
{
    const std::uintptr_t v = reinterpret_cast<std::uintptr_t>(p);
    // Up to the top of a large-address game's space: KPM sets the flag on CD and GOG, and
    // 0x7FFF0000 here refused real objects above 2 GB (audit MEM-01).
    return v >= 0x00010000u && v < 0xFFFF0000u;
}

// Is [p, p + size) committed, readable memory right now? LooksLikePointerK1 only
// says an address is in range, and a remembered object can outlive itself:
// loading a save destroys every in-game screen, and once a freed page is
// released, reading it faults. That was the Load Game crash of 2026-09-24,
// kmrp-controller.module+0x3CC8, in the cue loop. VirtualQuery answers without
// touching the memory.
inline bool IsReadableK1(const void* p, std::size_t size)
{
    if (!LooksLikePointerK1(p) || size == 0) {
        return false;
    }
    constexpr DWORD readable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    const std::uint8_t* at = static_cast<const std::uint8_t*>(p);
    const std::uint8_t* const end = at + size;
    while (at < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(at, &info, sizeof(info)) || info.State != MEM_COMMIT ||
            !(info.Protect & readable) || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS))) {
            return false;
        }
        at = static_cast<const std::uint8_t*>(info.BaseAddress) + info.RegionSize;
    }
    return true;
}
