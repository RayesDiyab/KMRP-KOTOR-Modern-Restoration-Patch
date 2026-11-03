/*
 * kmrp-prepare: KMRP's art made at install, before the game first starts (handoff item 73).
 *
 *   kmrp-prepare ASSETS PACK store|WxH [...]   makes each in ~/Library/Caches/KMRP/<build>/
 *   kmrp-prepare --sizes PACK                   prints the sizes the main display offers that
 *                                               KMRP covers, one WxH a line, largest first
 *   kmrp-prepare --check                        exits 0 (the installer asks whether it runs)
 *
 * ASSETS is the game's Contents/Assets folder, PACK the art pack, kmrp-assets.pack. "store" is
 * the common files; WxH one size's set. The game's module makes the same files the first time it
 * starts at a size (about 7.5 s to the first frame on a clean start, measured 2026-11-03); Windows'
 * installer makes them ahead with its module's own code (src/patcher/ArtPreparation.cs), and so
 * does this: it is the module's assets.cpp with the helpers it links, compiled into a program
 * (macos/build.sh), given the two paths the module finds itself (assets::SetPaths). Nothing it
 * calls reaches the engine: PrepareStore and PrepareSet read the pack and the game's files and
 * write the cache, as testing/regression/Test-MacAssets.py's driver runs them without a game.
 *
 * x86_64, as the module: the helpers' image arithmetic is then the module's (arm64 contracts
 * multiply-adds and rounds a few icons' pixels differently, audit MAC-4), so a set made here is
 * the one the game would make. The helpers keep their state in globals, so kmrp-mac.sh runs one
 * size a process, several side by side (half the processor's threads, at most six, Windows'
 * rule); the store and each size are folders of their own, built under a working name and renamed.
 *
 * What it says: "made WxH" or "failed WxH" (and "made store") on stdout as each finishes, the
 * module's own lines on stderr. Exit 0 when everything asked for was made, 1 when anything was
 * not (the game then makes it when it first starts at that size), 2 for a wrong command line.
 */
#include "assets.h"

#include <ApplicationServices/ApplicationServices.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <string>
#include <unistd.h>
#include <utility>
#include <vector>

// fonts.cpp fits the fonts for the running game, reading its text options through the engine's
// settings; the game makes them at its first start (about a second, Windows' measure). As the
// regression driver does, the module's call to it is answered by nothing here.
namespace kmrp { namespace fonts { void Prepare(const std::string&, const std::string&, int) {} } }

namespace {

bool ParseSize(const char* text, int& width, int& height) {
    char end = 0;
    return std::sscanf(text, "%dx%d%c", &width, &height, &end) == 2 && width > 0 && height > 0;
}

// The main display's modes as the game's resolution list takes them (kmrp-assets/layouts_ini.cpp,
// DisplayOffers): every mode, the scaled modes of a Retina display included, each by its pixels
// and by its points, either of which the game lists (Aspyr's list in points, with a twin of each
// at the display's pixels, resolution.cpp). Both, since the duplicate low-resolution modes did
// not give a scaled mode's point size as a mode of its own on this 14" MacBook Pro under macOS 27
// (2026-11-03: twelve pixel sizes, 3600x2338 to 1920x1200; 1512x982, the size macOS is set to,
// only as points).
std::vector<std::pair<int, int>> DisplaySizes() {
    std::set<std::pair<int, int>> sizes;
    const void* keys[] = {kCGDisplayShowDuplicateLowResolutionModes};
    const void* values[] = {kCFBooleanTrue};
    CFDictionaryRef options = CFDictionaryCreate(nullptr, keys, values, 1, &kCFTypeDictionaryKeyCallBacks,
                                                 &kCFTypeDictionaryValueCallBacks);
    if (CFArrayRef modes = CGDisplayCopyAllDisplayModes(CGMainDisplayID(), options)) {
        for (CFIndex i = 0, n = CFArrayGetCount(modes); i < n; i++) {
            const auto mode = static_cast<CGDisplayModeRef>(const_cast<void*>(CFArrayGetValueAtIndex(modes, i)));
            sizes.emplace(static_cast<int>(CGDisplayModeGetPixelWidth(mode)), static_cast<int>(CGDisplayModeGetPixelHeight(mode)));
            sizes.emplace(static_cast<int>(CGDisplayModeGetWidth(mode)), static_cast<int>(CGDisplayModeGetHeight(mode)));
        }
        CFRelease(modes);
    }
    if (options) CFRelease(options);
    std::vector<std::pair<int, int>> list(sizes.begin(), sizes.end());
    // The largest first, the longest to make, so the last process to finish is a short one.
    std::stable_sort(list.begin(), list.end(), [](const std::pair<int, int>& a, const std::pair<int, int>& b) {
        return static_cast<long>(a.first) * a.second > static_cast<long>(b.first) * b.second;
    });
    return list;
}

int Usage() {
    std::fprintf(stderr, "usage: kmrp-prepare ASSETS PACK store|WxH [...]\n       kmrp-prepare --sizes PACK\n");
    return 2;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc == 2 && std::strcmp(argv[1], "--check") == 0) return 0;
    // This program's answers on stdout, and nothing else there: the helpers print what they
    // would do (kmrp-guiblend lists the sets it blends from), which goes to stderr with the
    // module's own lines.
    const int answer = dup(STDOUT_FILENO);
    FILE* const out = answer >= 0 ? fdopen(answer, "w") : nullptr;
    if (!out || dup2(STDERR_FILENO, STDOUT_FILENO) < 0) return 1;
    if (argc == 3 && std::strcmp(argv[1], "--sizes") == 0) {
        kmrp::assets::SetPaths(std::string(), argv[2]);
        for (const auto& size : DisplaySizes())
            if (kmrp::assets::Covers(size.first, size.second)) std::fprintf(out, "%dx%d\n", size.first, size.second);
        std::fclose(out);
        return 0;
    }
    if (argc < 4) return Usage();
    for (int i = 3; i < argc; i++) {
        int width, height;
        if (std::strcmp(argv[i], "store") != 0 && !ParseSize(argv[i], width, height)) return Usage();
    }
    kmrp::assets::SetPaths(argv[1], argv[2]);
    bool all = true;
    for (int i = 3; i < argc; i++) {
        int width = 0, height = 0;
        const bool store = std::strcmp(argv[i], "store") == 0;
        if (!store) ParseSize(argv[i], width, height);
        const bool made = store ? kmrp::assets::PrepareStore() : kmrp::assets::PrepareSet(width, height);
        std::fflush(stdout);
        std::fprintf(out, "%s %s\n", made ? "made" : "failed", argv[i]);
        std::fflush(out);
        all = all && made;
    }
    return all ? 0 : 1;
}
