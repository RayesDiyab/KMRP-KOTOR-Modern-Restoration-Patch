/*
  KMRP for macOS: the widescreen patch, as KMRP's code talks to it.

  FTD's K1WidescreenPatch is either built into this module (make_kmrp_patch.py, since
  2026-09-30) or a patch of its own that KMRP's requires, loaded before it. Either way its
  symbols are found by name, so the same code serves both. KotorPatcher loads each patch's
  module privately, so a name is not found process-wide (measured 2026-10-04: dlsym with
  RTLD_DEFAULT found nothing of a widescreen patch loaded beside this module). It is looked for
  in this module's own image, then in the widescreen patch's, which KotOR Patch Manager puts
  beside this one under the patch's id, patches/k1widescreenpatch.dylib:

      K1Widescreen_UseGuiFileLayouts(1)        the entry points the patch has had since the
      K1Widescreen_SetTargetResolution(w, h)   2026-10-04 adjustment made for this (its
      K1Widescreen_GetTargetResolution(&w,&h)  mac_widescreen.cpp, "For a patch that brings its
                                               own .gui sets")
      g_targetWidth, g_targetHeight,           the patch's own variables and function, for a
      InitTargetResolution()                   version of it without those entry points

  With the entry points, a change of size also re-applies everything of the patch's that depends
  on it. Without them only the two variables are written, which is what kmrp-layout's own
  constants and the patch's per-frame code read.
*/
#include "widescreen.h"

#include <dlfcn.h>
#include <string>

namespace kmrp {
namespace widescreen {
namespace {

const char kWidescreenModule[] = "k1widescreenpatch.dylib";

// This module's image and the widescreen patch's, when it is loaded: handles to images already
// in the process (RTLD_NOLOAD), never a load of our own.
void* const* Images() {
    static void* images[2] = {nullptr, nullptr};
    static bool looked = false;
    if (looked) return images;
    looked = true;
    Dl_info self;
    if (!dladdr(reinterpret_cast<const void*>(&Images), &self) || !self.dli_fname) return images;
    const std::string path(self.dli_fname);
    images[0] = dlopen(path.c_str(), RTLD_NOLOAD | RTLD_LAZY);
    const std::size_t slash = path.rfind('/');
    if (slash != std::string::npos)
        images[1] = dlopen((path.substr(0, slash + 1) + kWidescreenModule).c_str(), RTLD_NOLOAD | RTLD_LAZY);
    return images;
}

template <typename T> T Find(const char* name) {
    void* const* images = Images();
    for (int i = 0; i < 2; i++)
        if (images[i])
            if (void* found = dlsym(images[i], name)) return reinterpret_cast<T>(found);
    return reinterpret_cast<T>(dlsym(RTLD_DEFAULT, name));
}

void Initialise() {
    if (const auto init = Find<void (*)()>("_Z20InitTargetResolutionv")) init();
}

}  // namespace

void Target(int* width, int* height) {
    *width = *height = 0;
    if (const auto get = Find<void (*)(int*, int*)>("K1Widescreen_GetTargetResolution")) {
        get(width, height);
        return;
    }
    Initialise();
    const int* w = Find<const int*>("g_targetWidth");
    const int* h = Find<const int*>("g_targetHeight");
    if (w && h) { *width = *w; *height = *h; }
}

void SetTarget(int width, int height) {
    if (const auto set = Find<void (*)(int, int)>("K1Widescreen_SetTargetResolution")) {
        set(width, height);
        return;
    }
    int* w = Find<int*>("g_targetWidth");
    int* h = Find<int*>("g_targetHeight");
    if (w && h) { *w = width; *h = height; }
}

bool UseGuiFileLayouts() {
    const auto use = Find<int (*)(int)>("K1Widescreen_UseGuiFileLayouts");
    return use && use(1) != 0;
}

}  // namespace widescreen
}  // namespace kmrp
