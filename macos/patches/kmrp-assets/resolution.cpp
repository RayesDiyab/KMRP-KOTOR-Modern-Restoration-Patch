/*
  KMRP for macOS: the resolution changed in the game.

  The game's own mode switch (0x10026ef34; Windows 0x005F1830) is what Options, Graphics, Screen
  Resolution calls (CSWGuiOptionsResolution::OnResolutionChosen, 0x1002cd6f8) and what start-up
  calls for the first mode. It reads the mode from Aspyr's list, stores its size in the engine's
  globals (0x1005d3b8c, 0x1005d3b90), re-initialises the renderer (Global::ReInitAurora,
  0x1004ac827), then resizes the GUI manager (0x10049ffdc) and loads the main menu and the
  options screen again from their layout files.

  Until 2026-10-04 a change made there did nothing on the Mac but write the size to swkotor.ini:
  the widescreen patch lays everything out for one target size, fixed when the game starts.
  Now the size the game switches to becomes that target, and everything of KMRP's that depends
  on the size follows, before the renderer is re-initialised and the panels are loaded again, as
  Windows' KmrpModeSwitchK1 does at the same point of its engine
  (src/controller-native/K1RuntimeResolution.cpp):

      the widescreen patch's target   g_targetWidth, g_targetHeight
      kmrp-layout's sizes and stubs   ApplyLayoutForSize
      the menu set                    assets::Register, the new size's set searched first

  The hook is the routine's call to ReInitAurora (0x10026f0ec), a relative call the handler makes
  itself. Its arguments are the size, the depth, whether windowed, and 1.
*/
#include "assets.h"

#include <OpenGL/OpenGL.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "widescreen.h"

namespace kmrp {
void ApplyLayoutForSize(int width, int height);   // kmrp-layout/kmrp_layout.cpp
}

namespace {
void** const kResourceManager = reinterpret_cast<void**>(0x100677cc8);
const auto ReInitAurora = reinterpret_cast<int (*)(int, int, int, int, int)>(0x1004ac827);

// Every font's TXI read again, after the new size's files are registered.
//
// Re-initialising the renderer loads each texture's image again from the current files, but a
// texture's TXI is parsed once, when the texture is created, and a font's glyph metrics and atlas
// coordinates are that parsed TXI (the object at texture+0x48, which the widescreen patch names
// CAurFontInfo). So after a switch the new size's atlas was drawn with the old size's
// coordinates: every label garbled (measured 2026-10-04, 1512x982 to 1024x768, as on Windows,
// whose ReloadFontMetrics this is).
//
// 0x1001f866a is the engine's own TXI load (texture, name): on a texture that already has the
// object it parses into it in place, and frees it when the TXI gave no glyph coordinates, so only
// fonts keep one. The name it is given when a texture is created is the text at +0xbc
// (0x1001f9d67). The engine's textures are the array at 0x100635b58, 0x100635b60 of them, which
// the lookup by name walks (0x1001f9700); 0x100635b88 is the queue of textures just created.
void ReloadFontMetrics() {
    void** const textures = *reinterpret_cast<void***>(0x100635b58);
    const int count = *reinterpret_cast<const int*>(0x100635b60);
    if (!textures || count <= 0 || count > 0x100000) return;
    const auto loadTxi = reinterpret_cast<void (*)(void*, const char*)>(0x1001f866a);
    int reloaded = 0;
    for (int i = 0; i < count; i++) {
        void* const texture = textures[i];
        if (!texture || !*reinterpret_cast<void**>(static_cast<char*>(texture) + 0x48)) continue;
        loadTxi(texture, static_cast<const char*>(texture) + 0xbc);
        reloaded++;
    }
    fprintf(stderr, "[KMRP] font metrics read again for %d of %d textures\n", reloaded, count);
}

// Fullscreen, Aspyr draws into a surface of the mode's size and lets the window server scale it
// onto the display (kCGLCPSurfaceBackingSize, enabled with kCGLCESurfaceBackingSize). It sizes
// that surface when the game starts and not again: after a switch the new mode was drawn into
// the corner of the old surface (measured 2026-10-04, 1512x982 to 1024x768: viewport 1024x768,
// surface still 1512x982). So the surface follows here, on the game's own thread, whose context
// is the one it draws with. Left alone when the game has no such surface (windowed).
void SizeSurface(int width, int height) {
    CGLContextObj context = CGLGetCurrentContext();
    if (!context) return;
    GLint enabled = 0;
    CGLIsEnabled(context, kCGLCESurfaceBackingSize, &enabled);
    if (!enabled) return;
    GLint size[2] = {0, 0};
    CGLGetParameter(context, kCGLCPSurfaceBackingSize, size);
    if (size[0] == width && size[1] == height) return;
    size[0] = width;
    size[1] = height;
    const CGLError error = CGLSetParameter(context, kCGLCPSurfaceBackingSize, size);
    if (error) fprintf(stderr, "[KMRP] the %dx%d surface was refused (%d)\n", width, height, static_cast<int>(error));
    else fprintf(stderr, "[KMRP] surface sized %dx%d\n", width, height);
}

}  // namespace

namespace kmrp {
// Once a GUI frame (layout.cpp), with the manager's viewport: the surface is kept at the size the
// game draws at. The switch sizes it too, but start-up's own switch comes before the game has
// its surface: a game started at the display's pixel size (3024x1964) then drew into a surface
// of the point size and showed a quarter of itself (measured 2026-10-04).
void KeepSurface(int width, int height) { SizeSurface(width, height); }
}  // namespace kmrp

extern "C" __attribute__((visibility("default")))
int KmrpModeSwitch(int width, int height, int depth, int windowed, int flag) {
    int targetWidth = 0, targetHeight = 0;
    kmrp::widescreen::Target(&targetWidth, &targetHeight);
    // A size KMRP has no menus for is the game's own business, as it was.
    if (kmrp::assets::Covers(width, height)) {
        const bool changed = width != targetWidth || height != targetHeight;
        if (changed) {
            fprintf(stderr, "[KMRP] resolution %dx%d -> %dx%d\n", targetWidth, targetHeight, width, height);
            kmrp::widescreen::SetTarget(width, height);
        }
        // kmrp-layout's sizes and stubs for the size. With the widescreen patch a patch of its
        // own these are that patch's, written by its .gui mode, and this writes nothing (with
        // debug logs on it records how the two compare; start-up's switch gives it the chance
        // once that patch has written its mode). The same size a second time costs nothing.
        kmrp::ApplyLayoutForSize(width, height);
        // Only once the game has registered its own folders (KmrpAddOverrideDirectory): the first
        // switch of a run can come before.
        if (changed && kmrp::assets::Registered() && kmrp::assets::Register(*kResourceManager, width, height))
            ReloadFontMetrics();
    }
    ReInitAurora(width, height, depth, windowed, flag);
    SizeSurface(width, height);
    return 1;
}

// The game's whitelist of sizes for its Screen Resolution list (0x10026f1ee; Windows
// IsValidResolution, KmrpAllowRuntimeResolutionK1): 800x600, 1024x768, 1280x960, 1280x1024 and
// 1600x1200, asked for every mode of Aspyr's display-mode list. Any size KMRP has menus for is
// accepted here instead, so the list offers what the display offers. Until 2026-10-04 kmrp-layout
// wrote the one configured size into the first pair of that whitelist.
//
// A size accepted leaves through the routine's own epilogue with 1 (the consumed exit); for any
// other the stolen bytes, its prologue and first comparison, run again and the game's own list
// decides. rsi is the width, rdx the height.
extern "C" __attribute__((visibility("default"))) int KmrpResolutionKnown(void*, int width, int height) {
    return kmrp::assets::Covers(width, height) ? 1 : 0;
}

#ifdef KMRP_BUNDLED_WIDESCREEN
// Only with the widescreen patch built into this module, in a version whose own function gives
// the ratio only for a start above the point size. A widescreen patch of its own (required, not
// built in) gives it always since its 2026-10-04 adjustment, and keeps the hook.
//
// The widescreen patch's display sizes (mac_widescreen.cpp, InitTargetResolution).
extern int g_displayPointWidth, g_displayPointHeight, g_displayPixelWidth, g_displayPixelHeight;
void InitTargetResolution();

// The display's pixel/point ratio, for Aspyr's mode list (0x10001de6c): with it the list gets a
// twin of every mode at the display's pixels, so a Retina display's native size is a mode. The
// widescreen patch's own function of this name (K9, kmrp_engine_fixes.cpp) gives the ratio only
// when the game starts at a size above the display's points, since the list is built once and
// nothing could switch to a twin afterwards. Now the player can, in the game, so the twins are
// always listed. The patch's function is compiled under another name (make_kmrp_patch.py,
// -DKMRP_DisplayModeScale=...), and this one takes the hook.
extern "C" __attribute__((visibility("default"))) uint64_t KMRP_DisplayModeScale() {
    InitTargetResolution();
    double scale = 1.0;
    if (g_displayPointWidth > 0 && g_displayPixelWidth > g_displayPointWidth)
        scale = static_cast<double>(g_displayPixelWidth) / g_displayPointWidth;
    uint64_t bits;
    memcpy(&bits, &scale, sizeof bits);
    return bits;
}
#endif  // KMRP_BUNDLED_WIDESCREEN
