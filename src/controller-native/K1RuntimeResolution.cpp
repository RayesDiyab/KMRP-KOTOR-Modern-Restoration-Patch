#include "K1EngineAddresses.h"
#include "K1RuntimeResolution.h"
#include <windows.h>
#include "KmrpOptions.h"
#include <cstdio>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <array>
#include <map>
#include <set>
#include <utility>
#include <vector>
#include <intrin.h>
#include "K1RuntimeEngine.h"
#include "K1RuntimeAssets.h"
#include "K1RuntimeLayout.h"
#include "K1DisplayModePolicy.h"

namespace {
// Written only at GUI size-change/frame hooks, on the game's GUI thread.
struct Dimensions { int width = 0, height = 0; } g_requested, g_observed;
void Log(const char* event, int width, int height)
{
    if (!KmrpDebugLogs()) return;
    wchar_t path[MAX_PATH];
    if (!KmrpLogPath(path, L"kmrp-native-preview.log")) return;
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
    if (KmrpRuntimeAssetsDimensions(width, height)) {
        if (!KmrpRuntimeEngineDimensions(width, height)) Log("engine-failed", width, height);
    } else Log("assets-failed", width, height);
}

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
    void** const textures = *reinterpret_cast<void***>(K1_TEXTURE_LIST);
    const int count = *reinterpret_cast<const int*>(K1_TEXTURE_COUNT);
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
    // LoadTXI's common-return hook finalizes each Override font before returning.
}
}

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

// The list is what the connected display reports, whatever display that is: started
// on a 4K television, the game lists that television's sizes. KMRP's patch has a
// layout for every one of them, built or blended (KmrpRuntimeAssetsCovers).
//
// From 2026-10-04 to 2026-10-07 the installer had a checklist of sizes, written
// beside the game as kmrp-resolutions.txt, which this file read: the list was then
// the chosen sizes, and a chosen size the display did not report was run in a
// borderless window. The maintainer had the choice removed on 2026-10-07 ("not have
// any choice in the resolution"). A kmrp-resolutions.txt left by such an install is
// not read.
}

namespace {
BOOL WINAPI EnumModesOnce(LPCSTR device, DWORD index, DEVMODEA* mode)
{
    BOOL ok = g_enumModes(device, index, mode);
    // The current and the registry settings are asked for by index too; those and a
    // null answer are Windows' alone.
    if (!mode || index == ENUM_CURRENT_SETTINGS || index == ENUM_REGISTRY_SETTINGS) return ok;
    const void* const caller = _ReturnAddress();
    if (!ok || (caller != reinterpret_cast<void*>(0x006E0955) &&
                caller != reinterpret_cast<void*>(0x006E0BC9))) return ok;
    static std::set<std::array<DWORD, 4>> seen;
    // Each size's lowest rate of 60 Hz or more, and whether the rates above 60 are
    // offered: see "Refresh rates" below.
    static std::map<std::pair<DWORD, DWORD>, DWORD> lowest;
    static bool highRates = false;
    if (index == 0) {
        seen.clear();
        lowest.clear();
        highRates = GetModuleHandleW(L"high-fps-fixes.dll") != nullptr;
        DEVMODEA each{};
        each.dmSize = sizeof each;
        for (DWORD i = 0; g_enumModes(device, i, &each); ++i) {
            if (each.dmBitsPerPel != 32 || each.dmDisplayFrequency < 60) continue;
            const auto found = lowest.find({each.dmPelsWidth, each.dmPelsHeight});
            if (found == lowest.end()) lowest[{each.dmPelsWidth, each.dmPelsHeight}] = each.dmDisplayFrequency;
            else if (each.dmDisplayFrequency < found->second) found->second = each.dmDisplayFrequency;
        }
    }
    // Hidden from the dialog: a repeat.
    if (!seen.insert({mode->dmPelsWidth, mode->dmPelsHeight, mode->dmBitsPerPel, mode->dmDisplayFrequency}).second)
        mode->dmBitsPerPel = 0;
    // Refresh rates. The dialog lists a size once for each rate of 60 Hz or more, as
    // "W x H @ N Hz" (its constructor, 0x006E0710; above 85 Hz only with
    // AllowHighMonitorFrequency=1 in swkotor.ini, which KMRP's installer writes with
    // High FPS Fix). The game's timing breaks above 60 frames a second, so without
    // D3M0's High FPS Fixes loaded beside this module only a size's rate of 60 is
    // listed: its lowest of 60 or more, so that a display with no 60 Hz mode of a size
    // still offers the size (the maintainer, 2026-10-09).
    else if (!highRates && mode->dmBitsPerPel == 32 && mode->dmDisplayFrequency > 61) {
        const auto found = lowest.find({mode->dmPelsWidth, mode->dmPelsHeight});
        if (found != lowest.end() && mode->dmDisplayFrequency != found->second) mode->dmBitsPerPel = 0;
    }
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

// The size the game starts at on a display that does not have swkotor.ini's size.
//
// swkotor.ini holds the size of the display the installer was run on. The game reads
// it in CClientExoAppInternal::ReadVideoModeSettings (0x005F0CE0), which ends:
//
//     005F0FA9  E8 B2 FC FF FF       call 0x005F0C60     IsValidResolution(width, height)
//     005F0FAE  85 C0                test eax, eax
//     005F0FB0  75 0C                jne 0x005F0FBE
//     005F0FB2  C7 07 20 03 00 00    mov [edi], 800
//     005F0FB8  C7 02 58 02 00 00    mov [edx], 600
//
// and, where the display has no mode of the size it read, asks for the mode nearest
// 800x600 (ReadAndSetVideoMode, 0x005F5B80: push 60, push 32, push 600, push 800,
// call GetNearestVideoMode).
//
// KMRP answers IsValidResolution itself (KmrpAllowRuntimeResolutionK1) and said yes to
// every size it has a layout for. Measured 2026-10-07 with 3000x1300 in swkotor.ini on
// a 3440x1440 display: the game kept 3000x1300 as its size (0x0078D1D4), the engine
// took the largest mode that fits inside it (CAurInternal::GetValidMode, 0x0044D6E0:
// 1920x1200) and the menu was drawn for 3000x1300 on a 1920x1200 screen, unreadable.
// That is what a PC moved from one display to another would meet.
//
// So a size is valid only if the display reports a mode of it (DisplayReports), and
// both 800x600s are written again, when the module loads and before the game reads
// its settings, as the size the display is in then: the desktop's. A size the display
// lacks is thus read as the desktop's size everywhere the game reads it. Left as they
// are when the bytes are not the game's own, when the desktop's size cannot be read,
// or when KMRP has no layout for it. swkotor.ini is not rewritten: its size is used
// again as soon as a display reports it.
namespace {
bool DisplayReports(int width, int height)
{
    // The Screen Resolution dialog asks about every mode in turn: one enumeration
    // serves the calls of a moment.
    static std::set<std::pair<DWORD, DWORD>> sizes;
    static ULONGLONG read = 0;
    const ULONGLONG now = GetTickCount64();
    if (sizes.empty() || now - read > 2000) {
        sizes.clear();
        DEVMODEA mode{};
        mode.dmSize = sizeof mode;
        for (DWORD index = 0; EnumDisplaySettingsA(nullptr, index, &mode); ++index)
            if (mode.dmBitsPerPel == 32) sizes.insert({mode.dmPelsWidth, mode.dmPelsHeight});
        read = now;
    }
    // No answer from the display at all: nothing is refused on that account.
    return sizes.empty() || sizes.count({static_cast<DWORD>(width), static_cast<DWORD>(height)}) != 0;
}

bool WriteSize(std::uintptr_t address, const unsigned char* original, size_t size, size_t widthAt, size_t heightAt,
               int width, int height)
{
    auto site = reinterpret_cast<unsigned char*>(address);
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(site, &info, sizeof info) || info.State != MEM_COMMIT ||
        (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) || memcmp(site, original, size)) return false;
    DWORD old = 0;
    if (!VirtualProtect(site, size, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(site + widthAt, &width, 4);
    memcpy(site + heightAt, &height, 4);
    VirtualProtect(site, size, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, size);
    return true;
}
}

// The mode in swkotor.ini against the modes the display has now (issue 92; the rules are in
// K1DisplayModePolicy.h). When the module loads, so before the game reads its settings and
// before any font or layout is chosen for a size. A mode that has to go is replaced in the file
// too, those keys alone, so the next start finds a good one; a mode that stays is not written,
// which leaves the file exactly as it was. The display is the one the game opens on, the one
// the game's own list asks about (a null device name).
void KmrpSettleSavedDisplayMode()
{
    wchar_t ini[MAX_PATH], fix[MAX_PATH];
    if (!KmrpGamePath(ini, L"swkotor.ini") || GetFileAttributesW(ini) == INVALID_FILE_ATTRIBUTES) return;
    const wchar_t* const section = L"Graphics Options";
    const KmrpDisplayMode::Mode saved{static_cast<int>(GetPrivateProfileIntW(section, L"Width", 0, ini)),
                                      static_cast<int>(GetPrivateProfileIntW(section, L"Height", 0, ini)),
                                      static_cast<int>(GetPrivateProfileIntW(section, L"RefreshRate", 0, ini))};
    std::vector<KmrpDisplayMode::Mode> modes;
    DEVMODEA mode{};
    mode.dmSize = sizeof mode;
    for (DWORD index = 0; EnumDisplaySettingsA(nullptr, index, &mode); ++index) {
        if (mode.dmBitsPerPel != 32 || (mode.dmDisplayFlags & DM_INTERLACED)) continue;
        modes.push_back({static_cast<int>(mode.dmPelsWidth), static_cast<int>(mode.dmPelsHeight), static_cast<int>(mode.dmDisplayFrequency)});
    }
    // As the installer decides: High FPS Fix installed and the game allowed to use it. Its module
    // is not loaded yet at this point.
    const bool highRates = GetPrivateProfileIntW(section, L"AllowHighMonitorFrequency", 0, ini) == 1 &&
        KmrpGamePath(fix, L"patches\\high-fps-fixes.dll") && GetFileAttributesW(fix) != INVALID_FILE_ATTRIBUTES;
    const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    const bool wine = ntdll && GetProcAddress(ntdll, "wine_get_version");
    const auto covers = [](int width, int height) {
        return KmrpRuntimeDimensions(width, height) && KmrpRuntimeAssetsCovers(width, height);
    };
    const KmrpDisplayMode::Choice choice = KmrpDisplayMode::Decide(saved, modes, covers, highRates, wine);
    char line[220];
    sprintf_s(line, "[KMRP] display mode: %dx%d at %d Hz in swkotor.ini: %s", saved.width, saved.height, saved.rate, choice.why);
    KmrpRuntimeLog(line);
    if (!choice.change) return;
    const auto write = [&](const wchar_t* key, int was, int value) {
        wchar_t text[16];
        swprintf_s(text, L"%d", value);
        return was == value || WritePrivateProfileStringW(section, key, text, ini);
    };
    const bool written = write(L"Width", saved.width, choice.mode.width) && write(L"Height", saved.height, choice.mode.height) &&
        write(L"RefreshRate", saved.rate, choice.mode.rate);
    sprintf_s(line, "[KMRP] display mode: %s %dx%d at %d Hz", written ? "now" : "could not write", choice.mode.width, choice.mode.height, choice.mode.rate);
    KmrpRuntimeLog(line);
}

void KmrpStartAtDisplaySize()
{
    DEVMODEA desktop{};
    desktop.dmSize = sizeof desktop;
    if (!EnumDisplaySettingsA(nullptr, ENUM_CURRENT_SETTINGS, &desktop)) return;
    const int width = static_cast<int>(desktop.dmPelsWidth), height = static_cast<int>(desktop.dmPelsHeight);
    if (!KmrpRuntimeDimensions(width, height) || !KmrpRuntimeAssetsCovers(width, height)) return;
    static const unsigned char read[] = {0xC7, 0x07, 0x20, 0x03, 0x00, 0x00, 0xC7, 0x02, 0x58, 0x02, 0x00, 0x00};
    static const unsigned char nearest[] = {0x68, 0x58, 0x02, 0x00, 0x00, 0x68, 0x20, 0x03, 0x00, 0x00};
    const bool first = WriteSize(0x005F0FB2, read, sizeof read, 2, 8, width, height);
    const bool second = WriteSize(0x005F5B84, nearest, sizeof nearest, 6, 1, width, height);
    if (first || second) Log("start fallback", width, height);
}

// The native mode switch (0x005F1830) has stored the new mode's size at
// 0x0078D1D4/0x0078D1D8 and is about to re-create the window (0x00403800), which
// reloads every texture. The new size's files must be in place before that:
// swapping them at SetSize, which the switch calls afterwards, left the fonts'
// old atlas images in video memory under the new glyph metrics until an Alt-Tab
// reloaded them (play-tested 2026-10-04).
extern "C" void __cdecl KmrpModeSwitchK1()
{
    const int width = *reinterpret_cast<const int*>(K1_SCREEN_WIDTH);
    const int height = *reinterpret_cast<const int*>(K1_SCREEN_HEIGHT);
    if (!KmrpRuntimeDimensions(width, height)) return;
    Prepare(width, height);
    Log("switching", width, height);
    ReloadFontMetrics();
}

// Back from Alt-Tab in full screen, without the rebuild (issue 96).
//
// The game leaving the foreground in full screen: its window procedure (0x00402800)
// minimises the window (0x004029DB) and calls the renderer's virtual at +0x18
// (0x0044D8D0): the gamma ramp at 1.0, then ChangeDisplaySettingsA(NULL, 0), the
// desktop's mode. Coming back, it calls the one at +0x1C (0x0044D900): the game's own
// gamma ramp again and ChangeDisplaySettingsA of the mode the renderer was made in,
// tested first, then CDS_FULLSCREEN. That brings back the picture's brightness and the
// game's mode, and keeps the window and its OpenGL context. Then it stored 2 at
// 0x007A3A2C (0x00402A66), and the next pass of the main loop rebuilt everything for
// it (0x0040460E -> ReInitAurora, 0x00404663): a new window, OpenGL context and input,
// and every texture loaded again. That rebuild is where a return to the game was
// reported to freeze (issue 96, from players of 1.5.1, not reproduced by KMRP).
//
// This hook replaces that store. Where the display is back at the game's size, the
// window and its context are kept: the procedure goes on as it does for a game in a
// window, which kept them all along (0x00402A72: the interrupted movies started again,
// RestartMoviesIfNecessary at 0x00402AA2), and drawing resumes (ActivateRenderWindow,
// 0x00402AD1, which the hook at 0x00402ACF makes it call in full screen too). Where it
// is not, or the call is not for the main window, the store is made here and the game
// rebuilds as it always did. `rebuild=1` in [Alt-Tab] of configs\kmrp.ini keeps the
// rebuild every time.
//
// KOTOR Patch Manager's Alt Tab Patch (J, MIT) does the same with its own display mode
// switch in place of the game's +0x1C: that leaves the gamma ramp +0x18 set at 1.0, so
// the picture comes back at the desktop's brightness, not the game's. This keeps the
// game's call. The two patches cannot both be installed: KMRP's lists it as a conflict.
// Each return and what was decided, with debug logs on (issue 96). The trace that found the
// outer window on 2026-11-10 also logged every swap for five seconds after a return, why the
// offscreen buffer was made again, and every ReInitAurora with its caller (a hook at
// 0x00403800); those were taken out once it had: alt-tab-fullscreen.md, section 2.
namespace {
void AltTabTrace(const char* format, ...)
{
    if (!KmrpDebugLogs()) return;
    char text[256];
    va_list args;
    va_start(args, format);
    vsprintf_s(text, format, args);
    va_end(args);
    char line[300];
    sprintf_s(line, "[Alt-Tab trace] %lu %s (rebuild flag %d)", GetTickCount(), text,
              *reinterpret_cast<const volatile int*>(K1_RENDER_REBUILD));
    KmrpRuntimeLog(line);
}
}

extern "C" int __cdecl KmrpFullscreenReturnK1(void* const* windowSlot)
{
    AltTabTrace("WM_ACTIVATEAPP back in full screen: hwnd %p, main %p, iconic %d",
                windowSlot ? *windowSlot : nullptr, *reinterpret_cast<void* const*>(K1_MAIN_WINDOW),
                IsIconic(*reinterpret_cast<const HWND*>(K1_MAIN_WINDOW)) ? 1 : 0);
    const HWND main = *reinterpret_cast<const HWND*>(K1_MAIN_WINDOW);   // the procedure's hwnd is at [esp+0x38]
    const auto rebuild = [](const char* why) {
        *reinterpret_cast<volatile int*>(K1_RENDER_REBUILD) = 2;   // the instruction the hook replaced
        if (why) {
            char line[200];
            sprintf_s(line, "[KMRP] back from Alt-Tab: %s; the game rebuilds its window", why);
            KmrpRuntimeLog(line);
        }
        AltTabTrace("  -> rebuild");
        return 0;
    };
    // The game has two windows, and both get WM_ACTIVATEAPP: the render window (0x007A39D8)
    // and the outer one (g_hWindow, 0x007A39D4, in the reconstruction). The procedure asks
    // for the rebuild for either, the render window after its +0x1C (0x00402A53 jumps past
    // the call for the other). The first version of this hook kept only the render window's
    // and let the outer window's through, which rebuilt everything all the same: seen in the
    // trace of 2026-11-10, the render window kept at 104526812, the outer window's rebuild
    // 47 ms later, ReInitAurora from the main loop (0x00404668), and a new window and context.
    const HWND outer = *reinterpret_cast<const HWND*>(K1_OUTER_WINDOW);
    const HWND hwnd = windowSlot ? static_cast<HWND>(*windowSlot) : nullptr;
    if (!main || !hwnd || (hwnd != main && hwnd != outer)) return rebuild(nullptr);   // not one of the game's
    wchar_t options[MAX_PATH];
    if (KmrpGamePath(options, L"configs\\kmrp.ini") && GetPrivateProfileIntW(L"Alt-Tab", L"rebuild", 0, options) != 0)
        return rebuild(KmrpDebugLogs() ? "rebuild=1 in configs\\kmrp.ini" : nullptr);
    const int width = *reinterpret_cast<const int*>(K1_SCREEN_WIDTH);
    const int height = *reinterpret_cast<const int*>(K1_SCREEN_HEIGHT);
    DEVMODEA display{};
    display.dmSize = sizeof display;
    if (!EnumDisplaySettingsA(nullptr, ENUM_CURRENT_SETTINGS, &display)) return rebuild("the display mode cannot be read");
    if (static_cast<int>(display.dmPelsWidth) != width || static_cast<int>(display.dmPelsHeight) != height) {
        char why[120];
        sprintf_s(why, "the display came back at %lux%lu, not the game's %dx%d", display.dmPelsWidth,
                  display.dmPelsHeight, width, height);
        return rebuild(why);
    }
    // The window the game minimised, shown again. Asynchronously: this runs inside the
    // window's own WM_ACTIVATEAPP, which a synchronous restore would enter again. The outer
    // window is left as it is, as the game leaves it.
    if (hwnd != main) {
    } else if (IsIconic(main)) {
        ShowWindowAsync(main, SW_RESTORE);
    } else {
        // At the top left at the game's size, as the window the rebuild would have made.
        RECT client{};
        POINT origin{};
        if (GetClientRect(main, &client) && ClientToScreen(main, &origin) &&
            (origin.x || origin.y || client.right != width || client.bottom != height)) {
            RECT frame = {0, 0, width, height};
            if (AdjustWindowRectEx(&frame, static_cast<DWORD>(GetWindowLongPtrA(main, GWL_STYLE)), FALSE,
                                   static_cast<DWORD>(GetWindowLongPtrA(main, GWL_EXSTYLE))))
                SetWindowPos(main, nullptr, frame.left, frame.top, frame.right - frame.left, frame.bottom - frame.top,
                             SWP_NOZORDER | SWP_NOACTIVATE);
        }
    }
    if (KmrpDebugLogs()) {
        char line[160];
        sprintf_s(line, "[KMRP] back from Alt-Tab at %dx%d: the same window and OpenGL context, no rebuild", width, height);
        KmrpRuntimeLog(line);
    }
    AltTabTrace("  -> kept the window and context");
    return 1;
}

extern "C" int __cdecl KmrpAllowRuntimeResolutionK1(const int* width, const int* height)
{
    if (!width || !height || !KmrpRuntimeDimensions(*width, *height)) return 0;
    // And one KMRP has a layout for: the installer refuses the others.
    if (!KmrpRuntimeAssetsCovers(*width, *height)) return 0;
    // And one the display has a mode of: see KmrpStartAtDisplaySize.
    if (!DisplayReports(*width, *height)) return 0;
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
    Dimensions actual;
    if (!ReadViewport(manager, actual)) return;
    if (actual.width == g_observed.width && actual.height == g_observed.height) return;
    if (!KmrpRuntimeLayoutDimensions(manager, actual.width, actual.height)) {
        Log("layout-failed", actual.width, actual.height);
        return;
    }
    g_observed = actual;
    Log("observed", actual.width, actual.height);
}

