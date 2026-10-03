// Shared guarded/relocated applier; this build supplies embedded source data.
// The installer build continues to read its owned kmrp-kpm.dat unchanged.
#ifndef KMRP_NATIVE_RUNTIME
#define KMRP_NATIVE_RUNTIME
#endif
#include "K1KpmApplier.cpp"
#include "K1RuntimeEngine.h"
#include "K1RuntimeResolution.h"
#include "NativeEngine.generated.h"
#include <cmath>
#include <array>

namespace {
int g_engineWidth = 0, g_engineHeight = 0;
std::vector<std::array<std::uint8_t, 4>> g_engineValues;

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
    if (!KmrpRuntimeDimensions(width, height) || !VanillaImage()) return;
    std::vector<std::uint8_t> payload(std::begin(kNativeEngine), std::end(kNativeEngine));
    for (const auto& field : kNativeFields) {
        auto value = FieldValue(field, width, height);
        std::memcpy(payload.data() + field.payload, value.data(), field.size);
        g_engineValues.push_back(value);
    }
    auto checksum = Fnv1a(payload.data(), payload.size() - 4);
    std::memcpy(payload.data() + payload.size() - 4, &checksum, 4);
    Apply(kCore | kMovies | kMapNotes, &payload);
    if (g_nativeBlock) {
        g_engineWidth = width; g_engineHeight = height;
        Log("native embedded engine initialized for %dx%d", width, height);
    } else g_engineValues.clear();
}
}

bool KmrpRuntimeEngineReady() { return g_nativeBlock != nullptr; }

bool KmrpRuntimeEngineDimensions(int width, int height)
{
    if (!g_nativeBlock || !KmrpRuntimeDimensions(width, height)) return false;
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
        if (std::memcmp(reinterpret_cast<const void*>(ranges[i].first), g_engineValues[i].data(), ranges[i].second)) {
            others.Resume(); Log("native size transaction refused: field %08X changed", kNativeFields[i].va); return false;
        }
    }
    bool ok = true;
    std::size_t done = 0;
    for (; done < ranges.size(); ++done) {
        if (!WriteMemory(ranges[done].first, next[done].data(), ranges[done].second) ||
            std::memcmp(reinterpret_cast<const void*>(ranges[done].first), next[done].data(), ranges[done].second)) {
            ok = false; break;
        }
    }
    if (!ok) {
        // Include the failing field, which may have been written before readback failed.
        for (std::size_t i = 0; i <= done && i < ranges.size(); ++i)
            WriteMemory(ranges[i].first, g_engineValues[i].data(), ranges[i].second);
    }
    others.Resume();
    if (ok) {
        g_engineValues.swap(next); g_engineWidth = width; g_engineHeight = height;
        Log("native engine dimensions committed %dx%d (%zu fields)", width, height, ranges.size());
    } else Log("native size transaction failed and restored %dx%d", g_engineWidth, g_engineHeight);
    return ok;
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        InitializeEngine();
    }
    return TRUE;
}
