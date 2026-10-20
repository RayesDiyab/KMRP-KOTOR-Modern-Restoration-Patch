// Shared guarded/relocated applier; this build supplies embedded source data.
// The installer build continues to read its owned kmrp-kpm.dat unchanged.
#ifndef KMRP_NATIVE_RUNTIME
#define KMRP_NATIVE_RUNTIME
#endif
#include "K1KpmApplier.cpp"
#include "K1RuntimeEngine.h"
#include "K1RuntimeResolution.h"
#include "K1RuntimeAssets.h"
#include "NativeEngine.generated.h"
#include <cmath>
#include <array>

namespace {
int g_engineWidth = 0, g_engineHeight = 0;
std::vector<std::array<std::uint8_t, 4>> g_engineValues;
std::uint32_t g_engineFeatures = 0;

// The movie display mode's six operands (kMovieMode, tools/build_windows_engine.py; four
// until RestoreResolutionFromMovie's pair joined them, 2026-10-20) are size fields too.
// With original-movie-mode they are not KMRP's (their runs are not applied), so a size
// change neither checks nor writes them; it refused every change until 2026-10-20,
// found by reading this, not in play.
bool FieldInForce(const NativeField& field)
{
    constexpr std::uint32_t kMovieModeFields[] = {0x00403D6C, 0x00403D78, 0x005F5B3B, 0x005F5B43,
                                                  0x00403EAD, 0x00403EB9};
    if ((g_engineFeatures & kMovieMode) != 0) return true;
    for (const std::uint32_t va : kMovieModeFields)
        if (field.va == va) return false;
    return true;
}

int RoundEven(double value)
{
    const double lower = std::floor(value), fraction = value - lower;
    return static_cast<int>(lower + (fraction > .5 ||
        (fraction == .5 && std::fmod(lower, 2.) != 0.) ? 1 : 0));
}

std::array<std::uint8_t, 4> FieldValue(const NativeField& f, int width, int height)
{
    const float scale = height > 720 ? static_cast<float>(height) / 720.f : 1.f;
    const float marker = scale > 127.f / 16.f ? 127.f / 16.f : scale;
    int value = 0;
    std::array<std::uint8_t, 4> result{};
    switch (f.kind) {
    case 1: value = width; break;
    case 2: value = height; break;
    case 3: value = RoundEven(static_cast<float>(f.base) * scale); break;
    case 4: value = -width; break;
    case 5: value = -height; break;
    case 6: value = RoundEven((width / 2) * 512 / 440.0); break;
    case 7: value = width / 2; break;
    case 8: value = height / 2; break;
    case 9: std::memcpy(result.data(), &scale, 4); return result;
    case 10: value = RoundEven(static_cast<float>(f.base) * marker); if (value < 1) value = 1; break;
    case 11: value = -RoundEven(static_cast<float>(-f.base) * marker); if (value > -1) value = -1; break;
    }
    std::memcpy(result.data(), &value, f.size);
    return result;
}

std::uint32_t FieldAddress(const NativeField& field)
{
    return field.va >= kBlockVa ?
        static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(g_nativeBlock)) + field.va - kBlockVa : field.va;
}

// The optional parts: KMRP's patch options (KmrpOptions.h), read from
// configs\kmrp.ini, which KOTOR Patch Manager or KMRP's installer writes.
//
// The patch is "kmrp" (tools/build_native_kpatch.py). Controller support and map
// notes are options, each on by default; the movie fixes are always in. Anything
// but an explicit 0 is on, so a manager without options (0.7.1), which writes no
// file and installs every hook, runs everything.
//
// One more setting, not an option of the patch's and written by nobody but a player:
// original-movie-mode=1 in a section of its own, [Movies], of the same file, leaves out
// the movie display mode (kMovieMode), so the game switches the screen to 640x480 for
// movies as it did unpatched, the fit and the black bars still KMRP's. The fallback for
// issue 48, black movies with sound on Windows 7 with a Radeon, where the unpatched
// game's movies play (2026-10-20). Its own section because the installer rewrites
// [Patch Options] at every install and leaves every other section alone.
bool g_controllerOption = true;

bool OriginalMovieMode()
{
    wchar_t path[MAX_PATH];
    return KmrpGamePath(path, L"configs\\kmrp.ini") &&
           GetPrivateProfileIntW(L"Movies", L"original-movie-mode", 0, path) != 0;
}

std::uint32_t OptionalFeatures()
{
    // Never, since 2026-10-05: controller support is the controller patch's, a module
    // of its own, and this module's copy of that code is not run (its hooks are not
    // installed; tools/build_native_kpatch.py).
    g_controllerOption = false;
    return kMovies | (OriginalMovieMode() ? 0 : kMovieMode) |
           (KmrpPatchOption(L"map-notes", 1) != 0 ? kMapNotes : 0);
}

// Apply the engine for one size: at load, for the size in swkotor.ini, or at the
// first size the game sets when the ini's was one the layouts cannot reach.
void InitializeEngineAt(int width, int height)
{
    if (!KmrpRuntimeDimensions(width, height) || !VanillaImage()) return;
    std::vector<std::uint8_t> payload(std::begin(kNativeEngine), std::end(kNativeEngine));
    for (const auto& field : kNativeFields) {
        auto value = FieldValue(field, width, height);
        std::memcpy(payload.data() + field.payload, value.data(), field.size);
        g_engineValues.push_back(value);
    }
    auto checksum = Fnv1a(payload.data(), payload.size() - 4);
    std::memcpy(payload.data() + payload.size() - 4, &checksum, 4);
    const std::uint32_t features = kCore | OptionalFeatures();
    g_moviesOff = (features & kMovies) == 0;   // the movie frame asks before painting its bars
    g_engineFeatures = features;
    Apply(features, &payload);
    if (g_nativeBlock) {
        g_engineWidth = width; g_engineHeight = height;
        Info("native embedded engine initialized for %dx%d", width, height);
    } else g_engineValues.clear();
}

void InitializeEngine()
{
    DWORD n = GetModuleFileNameW(nullptr, g_folder, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? wcsrchr(g_folder, L'\\') : nullptr;
    if (!slash) return;
    *slash = 0;
    wchar_t ini[MAX_PATH];
    if (swprintf_s(ini, L"%s\\swkotor.ini", g_folder) < 0) return;
    int width = GetPrivateProfileIntW(L"Graphics Options", L"Width", 800, ini);
    int height = GetPrivateProfileIntW(L"Graphics Options", L"Height", 600, ini);
    if (!KmrpRuntimeAssetsCovers(width, height)) {
        // The installer refuses such a size (ResolutionCatalog.Derived). Here the
        // game refuses it too, through the validator, and falls back to a size of
        // its own; the engine is applied for that one when the game sets it.
        Log("%dx%d is outside the sizes KMRP's layouts reach; waiting for the game's own size.", width, height);
        return;
    }
    InitializeEngineAt(width, height);
}
}

bool KmrpRuntimeEngineReady() { return g_nativeBlock != nullptr; }
bool KmrpControllerOptionK1() { return g_controllerOption; }
void KmrpRuntimeLog(const char* line) { Log("%s", line); }

bool KmrpRuntimeEngineDimensions(int width, int height)
{
    if (!KmrpRuntimeDimensions(width, height) || !KmrpRuntimeAssetsCovers(width, height)) return false;
    if (!g_nativeBlock) {
        InitializeEngineAt(width, height);
        return g_nativeBlock != nullptr;
    }
    if (width == g_engineWidth && height == g_engineHeight) return true;
    std::vector<std::array<std::uint8_t, 4>> next;
    std::vector<std::pair<std::uint32_t, std::uint32_t>> ranges;
    for (const auto& field : kNativeFields) {
        next.push_back(FieldValue(field, width, height));
        ranges.emplace_back(FieldAddress(field), field.size);
    }
    OtherThreads others;
    if (!others.Suspend(ranges)) { others.Resume(); return false; }
    // Check ownership for the complete transaction before writing any operand.
    for (std::size_t i = 0; i < std::size(kNativeFields); ++i) {
        if (!FieldInForce(kNativeFields[i])) continue;
        if (std::memcmp(reinterpret_cast<const void*>(ranges[i].first), g_engineValues[i].data(), ranges[i].second)) {
            others.Resume(); Log("native size transaction refused: field %08X changed", kNativeFields[i].va); return false;
        }
    }
    bool ok = true;
    std::size_t done = 0;
    for (; done < ranges.size(); ++done) {
        if (!FieldInForce(kNativeFields[done])) continue;
        if (!WriteMemory(ranges[done].first, next[done].data(), ranges[done].second) ||
            std::memcmp(reinterpret_cast<const void*>(ranges[done].first), next[done].data(), ranges[done].second)) {
            ok = false; break;
        }
    }
    if (!ok) {
        // Include the failing field, which may have been written before readback failed.
        for (std::size_t i = 0; i <= done && i < ranges.size(); ++i)
            if (FieldInForce(kNativeFields[i])) WriteMemory(ranges[i].first, g_engineValues[i].data(), ranges[i].second);
    }
    others.Resume();
    if (ok) {
        g_engineValues.swap(next); g_engineWidth = width; g_engineHeight = height;
        Info("native engine dimensions committed %dx%d (%zu fields)", width, height, ranges.size());
    } else Log("native size transaction failed and restored %dx%d", g_engineWidth, g_engineHeight);
    return ok;
}

// KMRP's installer makes the art of every size the display offers before the game first
// starts, with this module's own code (the maintainer, 2026-10-19: "smoother user
// experience comes priority"): workers, each a copy of the installer, load the module with
// KMRP_PREPARE set in their environment, so DllMain below leaves them alone, and call this
// with the game's folder and their share of the work (KpmEdition.cs, ArtPreparation). The
// sizes made, or -1.
extern "C" int __cdecl KmrpPrepareAssets(const wchar_t* game, int share, int shares, KmrpPrepareStep step, void* context)
{
    if (!game || !*game || wcscpy_s(g_folder, game) || wcscpy_s(KmrpGameFolderNamed(), MAX_PATH, game)) return -1;
    return KmrpRuntimeAssetsPrepare(share, shares, step, context);
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        // Loaded by KMRP's installer to make the art (KmrpPrepareAssets), not by the game:
        // nothing of the game's is there to change.
        if (GetEnvironmentVariableW(L"KMRP_PREPARE", nullptr, 0)) return TRUE;
        // The installer opts swkotor.exe out of Windows' DPI virtualization with a
        // per-user AppCompat value (DpiCompatibilityOperations in KmrpPatcher.cs),
        // so a scaled desktop does not zoom an interface KMRP has already sized
        // for the framebuffer. With no installer, say the same thing from inside,
        // before the game makes its window. It fails harmlessly when the process
        // already has an awareness, from that value or a manifest.
        SetProcessDPIAware();
        InitializeEngine();
        KmrpInstallModeListFilter();
        KmrpStartAtDisplaySize();
    }
    return TRUE;
}
