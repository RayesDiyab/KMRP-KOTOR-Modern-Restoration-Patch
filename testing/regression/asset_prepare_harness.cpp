// What KMRP's installer does after it writes the art pack (ArtPreparation, KpmEdition.cs):
// loads the module with KMRP_PREPARE in its environment, so that DllMain leaves this
// process alone, and calls KmrpPrepareAssets with a game folder. Run by
// Test-AssetPrepare.py as a 32-bit program, as the installer is.
//
//     asset_prepare_harness MODULE GAME [SHARE SHARES]
//
// SHARE of SHARES: this worker's part, as the installer runs several (0 of 1 by default).
//
// Prints each step and the sizes made; then checks that the module let go of the pack
// (the installer may write it again in the same session) and that nothing of the game's
// was touched in this process. Exit 0 when the common files and at least one size were
// made.
#include <windows.h>
#include <chrono>
#include <cstdio>
#include <string>

namespace {
typedef int(__stdcall* Step)(int done, int total, int width, int height, void* context);
typedef int(__cdecl* Prepare)(const wchar_t* game, int share, int shares, Step step, void* context);

std::chrono::steady_clock::time_point started, last;

int __stdcall Report(int done, int total, int width, int height, void*)
{
    const auto now = std::chrono::steady_clock::now();
    const double part = std::chrono::duration<double>(now - last).count();
    last = now;
    if (done) std::printf("  %.1f s\n", part);
    if (width) std::printf("%d of %d: %dx%d", done, total - 1, width, height);
    else if (!done) std::printf("the common files");
    std::fflush(stdout);
    return 0;
}
}

int wmain(int argc, wchar_t** argv)
{
    if (argc < 3) {
        std::printf("FAIL usage: asset_prepare_harness MODULE GAME\n");
        return 1;
    }
    SetEnvironmentVariableW(L"KMRP_PREPARE", L"1");
    HMODULE module = LoadLibraryExW(argv[1], nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    SetEnvironmentVariableW(L"KMRP_PREPARE", nullptr);
    if (!module) {
        std::printf("FAIL the module did not load (error %lu)\n", GetLastError());
        return 1;
    }
    auto prepare = reinterpret_cast<Prepare>(GetProcAddress(module, "KmrpPrepareAssets"));
    if (!prepare) {
        std::printf("FAIL the module has no KmrpPrepareAssets\n");
        return 1;
    }
    started = last = std::chrono::steady_clock::now();
    const int share = argc > 4 ? _wtoi(argv[3]) : 0, shares = argc > 4 ? _wtoi(argv[4]) : 1;
    const int made = prepare(argv[2], share, shares, Report, nullptr);
    const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::printf("sizes made: %d in %.1f s\n", made, seconds);
    // The pack beside the module, closed: it can be opened for writing (alone: other
    // workers may still be reading it).
    std::wstring pack = argv[1];
    pack = pack.substr(0, pack.find_last_of(L"\\/") + 1) + L"kmrp-assets.pack";
    if (GetFileAttributesW(pack.c_str()) == INVALID_FILE_ATTRIBUTES)
        pack = std::wstring(argv[2]) + L"\\patches\\kmrp-assets.pack";
    HANDLE file = CreateFileW(pack.c_str(), GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    const bool released = file != INVALID_HANDLE_VALUE || shares > 1;
    if (released) CloseHandle(file);
    std::printf("%s the module let go of the pack\n", released ? "ok  " : "FAIL");
    FreeLibrary(module);
    if (made < 0 || (made < 1 && shares == 1) || !released) {
        std::printf("FAIL\n");
        return 1;
    }
    std::printf("PASS\n");
    return 0;
}
