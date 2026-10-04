/*
  KMRP for macOS: UseGuiFileLayouts without the installer.

  The widescreen patch lays the menus out itself unless swkotor.ini says UseGuiFileLayouts=1 in
  [Graphics Options], which is for menu files already laid out at the screen's size: KMRP's.
  Until 2026-10-04 KMRP Installer wrote that key. A kmrp.kpatch applied by hand in KotOR Patch
  Manager has no installer, and it carries the menu files itself now (assets.cpp), so the key has
  to hold whenever the module has a set for the size, whatever the file says.

  The widescreen patch's source is FTD's and is compiled as it is. With the menu sets in the
  module, make_kmrp_patch.py compiles it with -Dfopen=kmrp_ini_fopen, so its reads of
  swkotor.ini come here; kmrp-layout's own read comes here through kmrp::g_iniOpen, which this
  part's constructor sets (the part is linked first, so that happens before the widescreen
  patch's own constructor reads the file).

  What the reader gets is the file as it is, with any UseGuiFileLayouts line of
  [Graphics Options] taken out and UseGuiFileLayouts=1 put under the section's header (the
  section itself when the file has none, or there is no file). Only when the size the patch is
  about to use is one KMRP has menus for: ForceWidth and ForceHeight when the file has both,
  else the main display's size in points, which is how the widescreen patch chooses
  (InitTargetResolution). For any other size the file is passed through untouched, and the
  widescreen patch lays the menus out as it does on its own.

  The size the game starts at (since 2026-10-04, with the resolution chosen in the game): the
  game records the size chosen in Options, Graphics as Width and Height, which the widescreen
  patch reads only when it cannot ask the display. So when the file has no ForceWidth and
  ForceHeight of its own, and its Width and Height are a size this display offers (a mode's size
  in points or in pixels) that KMRP has menus for, the reader is given them as ForceWidth and
  ForceHeight: the game starts at the size last chosen. Any other Width and Height (a file from
  another display, 1024x768 from a first run) are left out of it, and the game starts at the
  display's current size.

  The player's file is never written.
*/
#include "assets.h"
#include "widescreen.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <strings.h>

namespace kmrp {
extern FILE* (*g_iniOpen)(const char*, const char*);   // kmrp-layout/kmrp_layout.cpp
extern const char* (*g_sdlPath)();
extern bool g_resolutionListOpen;
extern bool g_widescreenOwnsLayout;
}

namespace {

struct RectShape { double x, y, width, height; };

void DisplayPointSize(int* width, int* height) {
    *width = *height = 0;
    void* cg = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY | RTLD_LOCAL);
    if (!cg) return;
    auto mainDisplay = reinterpret_cast<uint32_t (*)()>(dlsym(cg, "CGMainDisplayID"));
    auto bounds = reinterpret_cast<RectShape (*)(uint32_t)>(dlsym(cg, "CGDisplayBounds"));
    if (mainDisplay && bounds) {
        const RectShape rect = bounds(mainDisplay());
        *width = static_cast<int>(rect.width);
        *height = static_cast<int>(rect.height);
    }
    dlclose(cg);
}

// True when the main display has a mode of this size, in points or in pixels.
bool DisplayOffers(int width, int height) {
    void* cg = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY | RTLD_LOCAL);
    if (!cg) return false;
    const auto mainDisplay = reinterpret_cast<uint32_t (*)()>(dlsym(cg, "CGMainDisplayID"));
    const auto copyModes = reinterpret_cast<void* (*)(uint32_t, void*)>(dlsym(cg, "CGDisplayCopyAllDisplayModes"));
    const auto modeWidth = reinterpret_cast<size_t (*)(void*)>(dlsym(cg, "CGDisplayModeGetWidth"));
    const auto modeHeight = reinterpret_cast<size_t (*)(void*)>(dlsym(cg, "CGDisplayModeGetHeight"));
    const auto pixelWidth = reinterpret_cast<size_t (*)(void*)>(dlsym(cg, "CGDisplayModeGetPixelWidth"));
    const auto pixelHeight = reinterpret_cast<size_t (*)(void*)>(dlsym(cg, "CGDisplayModeGetPixelHeight"));
    const auto count = reinterpret_cast<long (*)(void*)>(dlsym(RTLD_DEFAULT, "CFArrayGetCount"));
    const auto at = reinterpret_cast<void* (*)(void*, long)>(dlsym(RTLD_DEFAULT, "CFArrayGetValueAtIndex"));
    const auto release = reinterpret_cast<void (*)(void*)>(dlsym(RTLD_DEFAULT, "CFRelease"));
    // With the scaled modes of a Retina display, whose size in points is below their pixels:
    // without this option the list holds only the modes drawn one pixel a point (measured
    // 2026-10-04 on a 14" MacBook Pro: 60 modes without, 132 with, 1512x982 only with).
    const auto createDictionary = reinterpret_cast<void* (*)(void*, const void**, const void**, long, const void*, const void*)>(
        dlsym(RTLD_DEFAULT, "CFDictionaryCreate"));
    void** const duplicates = static_cast<void**>(dlsym(cg, "kCGDisplayShowDuplicateLowResolutionModes"));
    void** const yes = static_cast<void**>(dlsym(RTLD_DEFAULT, "kCFBooleanTrue"));
    const void* keyCallbacks = dlsym(RTLD_DEFAULT, "kCFTypeDictionaryKeyCallBacks");
    const void* valueCallbacks = dlsym(RTLD_DEFAULT, "kCFTypeDictionaryValueCallBacks");
    void* options = nullptr;
    if (createDictionary && duplicates && yes && keyCallbacks && valueCallbacks) {
        const void* keys[] = {*duplicates};
        const void* values[] = {*yes};
        options = createDictionary(nullptr, keys, values, 1, keyCallbacks, valueCallbacks);
    }
    bool offered = false;
    if (mainDisplay && copyModes && modeWidth && modeHeight && pixelWidth && pixelHeight && count && at && release) {
        if (void* modes = copyModes(mainDisplay(), options)) {
            for (long i = 0, n = count(modes); i < n && !offered; i++) {
                void* mode = at(modes, i);
                const auto w = static_cast<size_t>(width), h = static_cast<size_t>(height);
                offered = (modeWidth(mode) == w && modeHeight(mode) == h) || (pixelWidth(mode) == w && pixelHeight(mode) == h);
            }
            release(modes);
        }
    }
    if (options && release) release(options);
    dlclose(cg);
    return offered;
}

bool IsHeader(const std::string& line, bool* graphics) {
    std::size_t at = line.find_first_not_of(" \t");
    if (at == std::string::npos || line[at] != '[') return false;
    *graphics = strncasecmp(line.c_str() + at, "[Graphics Options]", 18) == 0;
    return true;
}

bool IsKey(const std::string& line, const char* key) {
    const std::size_t at = line.find_first_not_of(" \t");
    return at != std::string::npos && strncasecmp(line.c_str() + at, key, strlen(key)) == 0;
}

// A read-only stream over text of our own.
struct Cookie { std::string text; std::size_t at = 0; };
int ReadCookie(void* cookie, char* buffer, int size) {
    Cookie* c = static_cast<Cookie*>(cookie);
    const std::size_t n = std::min(static_cast<std::size_t>(size), c->text.size() - c->at);
    memcpy(buffer, c->text.data() + c->at, n);
    c->at += n;
    return static_cast<int>(n);
}
int CloseCookie(void* cookie) {
    delete static_cast<Cookie*>(cookie);
    return 0;
}

bool EndsWith(const char* text, const char* end) {
    const std::size_t a = strlen(text), b = strlen(end);
    return a >= b && strcasecmp(text + a - b, end) == 0;
}

}  // namespace

extern "C" FILE* kmrp_ini_fopen(const char* path, const char* mode) {
    if (!path || !mode || mode[0] != 'r' || strchr(mode, '+') || !EndsWith(path, "swkotor.ini")) return fopen(path, mode);
    std::string text;
    FILE* real = fopen(path, "r");
    if (real) {
        char buffer[4096];
        std::size_t n;
        while ((n = fread(buffer, 1, sizeof buffer, real)) > 0) text.append(buffer, n);
        fclose(real);
    }
    // The size the widescreen patch will choose from this file.
    int forceWidth = 0, forceHeight = 0, chosenWidth = 0, chosenHeight = 0;
    std::size_t sizeAt = std::string::npos;   // where ForceWidth and ForceHeight would be put
    std::string kept;
    bool graphics = false, placed = false;
    std::size_t start = 0;
    while (start < text.size()) {
        std::size_t end = text.find('\n', start);
        end = end == std::string::npos ? text.size() : end + 1;
        const std::string line = text.substr(start, end - start);
        start = end;
        bool header = false;
        if (IsHeader(line, &header)) {
            graphics = header;
            kept += line;
            if (graphics && !placed) {
                if (kept.empty() || kept.back() != '\n') kept += "\n";
                kept += "UseGuiFileLayouts=1\n";
                placed = true;
                sizeAt = kept.size();
            }
            continue;
        }
        if (graphics) {
            const std::size_t eq = line.find('=');
            if (IsKey(line, "UseGuiFileLayouts")) continue;
            if (eq != std::string::npos && IsKey(line, "ForceWidth")) forceWidth = atoi(line.c_str() + eq + 1);
            if (eq != std::string::npos && IsKey(line, "ForceHeight")) forceHeight = atoi(line.c_str() + eq + 1);
            if (eq != std::string::npos && IsKey(line, "Width")) chosenWidth = atoi(line.c_str() + eq + 1);
            if (eq != std::string::npos && IsKey(line, "Height")) chosenHeight = atoi(line.c_str() + eq + 1);
        }
        kept += line;
    }
    if (!placed) {
        if (!kept.empty() && kept.back() != '\n') kept += "\n";
        kept += "[Graphics Options]\nUseGuiFileLayouts=1\n";
        sizeAt = kept.size();
    }
    int width = forceWidth, height = forceHeight;
    if (width < 640 || height < 480) {
        // The size chosen in the game, when this display offers it.
        static int offeredWidth = 0, offeredHeight = 0, offered = -1;
        if (offered < 0 || offeredWidth != chosenWidth || offeredHeight != chosenHeight) {
            offeredWidth = chosenWidth;
            offeredHeight = chosenHeight;
            offered = chosenWidth >= 640 && chosenHeight >= 480 && DisplayOffers(chosenWidth, chosenHeight) &&
                      kmrp::assets::Covers(chosenWidth, chosenHeight);
            fprintf(stderr, "[KMRP] swkotor.ini has %dx%d: %s\n", chosenWidth, chosenHeight,
                    offered ? "a size of this display, used" : "not a size of this display, or none KMRP has menus for");
        }
        if (offered) {
            width = chosenWidth;
            height = chosenHeight;
            kept.insert(sizeAt, "ForceWidth=" + std::to_string(width) + "\nForceHeight=" + std::to_string(height) + "\n");
        }
    }
    if (width < 640 || height < 480) DisplayPointSize(&width, &height);
    if (!kmrp::assets::Covers(width, height)) return real ? fopen(path, mode) : nullptr;
    Cookie* cookie = new Cookie;
    cookie->text = kept;
    FILE* stream = funopen(cookie, ReadCookie, nullptr, nullptr, CloseCookie);
    if (!stream) delete cookie;
    return stream;
}

namespace {
__attribute__((constructor)) void UseKmrpIni() {
    kmrp::g_iniOpen = kmrp_ini_fopen;
    kmrp::g_sdlPath = kmrp::assets::SdlPath;
    kmrp::g_resolutionListOpen = true;
    // A widescreen patch of its own, loaded before this module: asked directly for the .gui
    // mode, when the size it is about to use is one KMRP has menus for. (Built into this module
    // it has no such entry point in the version KMRP carries, and reads the file through
    // kmrp_ini_fopen above.)
    int width = 0, height = 0;
    kmrp::widescreen::Target(&width, &height);
#ifdef KMRP_BUNDLED_WIDESCREEN
    (void)width; (void)height;
#else
    // The widescreen patch is a patch of its own here, which KMRP requires.
    kmrp::g_widescreenOwnsLayout = true;
    if (!kmrp::assets::Covers(width, height)) return;   // its own layout, for a size without menus
    if (kmrp::widescreen::UseGuiFileLayouts()) {
        fprintf(stderr, "[KMRP] the widescreen patch uses the .gui layouts (%dx%d)\n", width, height);
    } else {
        // A widescreen patch without the entry point (before its 2026-10-04 adjustment), or
        // none: its own layout stays, and KMRP's menu files would be laid out a second time
        // over it. KMRP's menus are left out instead.
        kmrp::assets::Disable();
        fprintf(stderr, "[KMRP] the Widescreen Patch installed has no entry point for menus of KMRP's own "
                        "(K1Widescreen_UseGuiFileLayouts): KMRP's menus are not used. Update the Widescreen Patch.\n");
    }
#endif
}
}  // namespace
