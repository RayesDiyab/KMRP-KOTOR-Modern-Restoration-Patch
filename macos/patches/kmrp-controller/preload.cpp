// KMRP for macOS, controller support: the controller's preloads. Item 112's, the files the
// upcoming screens need, read during the movies (below), and item 113's, first-priority 3D preview
// initialization: the Mac port of src/controller-native/K1GuiModelPreload.h
// (docs/controller-live-adaptive-layout.md, "Priority 3D preview initialization"). The maintainer
// saw black models on the first New Game opening on Windows, and on the main menu; no root cause is
// established there. Each actual preview renders once with no colour output, zero time and
// framebuffer effects off, immediately before its first visible draw, on the thread drawing it; the
// original draw buffer, time and effects are put back first. Whether the Mac shows the black frame
// at all has not been measured.
//
// On the Mac (KOTOR_Exe 1.4.0), all read from its code:
//   - CSWGui3DSceneView's vtable is 0x1005B4B18; its Draw (view in rdi, seconds in xmm0) is
//     0x1004AB58C, slot +0x78 (Windows 0x0067ACB0, slot +0x38), which is CSWGuiScene::Draw
//     (0x1004A46C0) on the CSWGuiScene at view +0x88: the scene's animate, the viewport (depth and
//     stencil cleared), the camera's render. The Scene is at view +0xA0 (Windows +0x70).
//   - Scene::Render (0x10019972E) counts its renders at +0x58 (Windows +0x50) and makes its first-
//     render call (0x100199648) while that count is 0; its children are counted at +0x68 (Windows
//     +0x58, Scene::Animate's list).
//   - Scene::RenderSinglePass runs the framebuffer effects (0x1001E8166, which may copy or redirect
//     the frame) only while the pointer at +0x108 is set (0x100199a54 onward, three tests; Windows'
//     DWORD at +0xD4). It is a pointer here, so all eight bytes are kept and put back.
//   - Scene::Render's own time is the float at 0x1005CA818 (Windows 0x0078E574), MainLoop's frame
//     seconds.
//   - the 3D GUI flag is 0x1005D3B9C (Windows 0x0078D1E4): the panels load no model without it.
//   - CSWGuiClassSelection's vtable is 0x1005AF890, its six views at +0x2D0, 0x320 apart, the
//     constructor's 3D_MODEL1..6 (Windows +0x230, 0x25C apart); CSWGuiMainMenu's is 0x1005AEFA0,
//     its LBL_3DVIEW at +0x448 (Windows +0x360).
//
// The slot is taken in the vtable, as Windows takes it, and only while it holds the game's Draw, so
// another patch's Draw there is left alone.
//
// Item 112, the Mac port of K1ControllerPreload.cpp (docs/controller-live-adaptive-layout.md,
// "Movie-triggered controller GUI preload"). When the movies play (gameplay.cpp's movie frame), or
// on the first GUI frame when they were skipped, a thread of this module reads the screens Windows
// lists (classsel, kmrplayout, pazaaksetup, pazaakgame, savename, galaxymap) and their pictures:
// file reads only, through the shared readers KmrpReadPreloadGui (macos/tools/kmrp-guiadapt.c) and
// KmrpReadPreloadTexture (kmrp-gameart.c), which make_kmrp_patch.py links into this module. No
// engine or OpenGL call runs on it. A screen comes from this patch's files when it carries one
// (kmrplayout), else the game's override folder, else the game's chitin.key. The pictures read and
// then referenced are Windows' list mapped to what the Mac carries: every kmr* picture those
// screens name, which Windows draws on its worker and the Mac carries made, in the pad's family
// (Windows draws the other three later; here they would only take memory), the class screen's
// fill and lbl_pazaak. Then, on GUI frames with a GL context current and no preview waiting to be
// primed (Windows' Pending), two a frame are referenced through the engine,
// AurTextureGetReference (0x1001F9FF4, Windows 0x00423A60) and CAurTexture::Bind (0x1001F72B0,
// Windows 0x004214B0), so it uploads them, as kmrp-assets/hud_options.cpp's PreloadPage does, and
// kept. Done again only when the pad's family changes. KMRP is not needed for any of it, and no
// size is read: the Mac's carried pictures have one size, and HUD and text sizes stay KMRP's.
// Beside KMRP the screens the game loads are KMRP's set's, whose folder this module does not
// know; their kmr* names are this patch's, so the pictures are the same.
#include "preload.h"

#include "engine.h"
#include "pad.h"
#include "prompts.h"
#include "standalone.h"
#include "state.h"
#include "../kmrp-layout/text.h"
#include "../../../src/controller-native/K1GuiPreloadData.h"

#include <OpenGL/OpenGL.h>
#include <OpenGL/gl.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>

#include <mach-o/dyld.h>
#include <sys/stat.h>

#include <algorithm>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace kmrp {
namespace preload {
namespace {

using engine::At;
using text::Readable;

const std::uintptr_t kSceneViewVtable = 0x1005b4b18UL, kSceneViewDraw = 0x1004ab58cUL;
const std::size_t kVtDraw = 0x78;
const std::uintptr_t kClassSelectVtable = 0x1005af890UL, kMainMenuVtable = 0x1005aefa0UL;
const std::uintptr_t k3dGuiFlag = 0x1005d3b9cUL, kFrameSeconds = 0x1005ca818UL;
const std::size_t kClassViews = 0x2d0, kClassViewStride = 0x320, kMainMenuView = 0x448;
const std::size_t kViewScene = 0xa0;
const std::size_t kSceneRenders = 0x58, kSceneChildren = 0x68, kSceneEffects = 0x108;
const std::size_t kCtlFlags = 0x68;
const std::uint8_t kCtlVisible = 0x02;

using DrawFn = void (*)(void* view, float seconds);

struct Job { void* panel; void* view; const char* kind; };
struct Ready { Job job; int primed; bool hidden; };
std::vector<Job>* g_pending = nullptr;
std::vector<Ready>* g_ready = nullptr;
bool g_slotTaken = false, g_slotRefused = false;

bool Enabled3d() { return *reinterpret_cast<const int*>(k3dGuiFlag) != 0; }

char* SceneOf(void* view) {
    if (!Readable(view, kViewScene + 8)) return nullptr;
    char* const scene = At<char*>(view, kViewScene);
    return Readable(scene, kSceneEffects + 8) ? scene : nullptr;
}

// Whether a hidden pass happened, for the visible draw that follows it.
bool Prime(void* view) {
    if (!g_pending) return false;
    const auto found = std::find_if(g_pending->begin(), g_pending->end(), [=](const Job& j) { return j.view == view; });
    if (found == g_pending->end()) return false;
    char* const scene = SceneOf(view);
    if (!scene || !Enabled3d() || !(At<std::uint8_t>(view, kCtlFlags) & kCtlVisible) ||
        At<int>(scene, kSceneRenders) != 0 || At<int>(scene, kSceneChildren) <= 0) {
        g_pending->erase(found);
        return false;
    }
    if (!CGLGetCurrentContext()) return false;   // deferred: no graphics context on this thread
    const Job job = *found;
    g_pending->erase(found);
    GLint oldBuffer = 0;
    glGetIntegerv(GL_DRAW_BUFFER, &oldBuffer);
    void*& effects = At<void*>(scene, kSceneEffects);
    float& seconds = *reinterpret_cast<float*>(kFrameSeconds);
    void* const oldEffects = effects;
    const float oldSeconds = seconds;
    // Postprocessing can read and select buffers itself. Off in this hidden pass, and back before
    // the normal draw; the view clears depth and stencil again for the visible pass.
    effects = nullptr;
    seconds = 0.0f;
    glDrawBuffer(GL_NONE);
    GLint target = -1;
    glGetIntegerv(GL_DRAW_BUFFER, &target);
    const bool hidden = target == GL_NONE;
    if (hidden) reinterpret_cast<DrawFn>(kSceneViewDraw)(view, 0.0f);
    GLint after = -1;
    glGetIntegerv(GL_DRAW_BUFFER, &after);
    glDrawBuffer(static_cast<GLenum>(oldBuffer));
    seconds = oldSeconds;
    effects = oldEffects;
    if (!hidden) return false;
    if (!g_ready) g_ready = new std::vector<Ready>;
    g_ready->push_back({job, At<int>(scene, kSceneRenders), after == GL_NONE});
    return true;
}

// One line after a few visible draws, so the first frames are not spent on the log.
void AfterDraw(void* view) {
    char* const scene = SceneOf(view);
    if (!g_ready || !scene || At<int>(scene, kSceneRenders) < 5) return;
    for (auto it = g_ready->begin(); it != g_ready->end();) {
        if (it->job.view != view) { ++it; continue; }
        Log("model-preload priority=1 kind=%s view=%p renders=0->%d hidden=%u", it->job.kind, view, it->primed,
            it->hidden ? 1u : 0u);
        it = g_ready->erase(it);
    }
}

// In the vtable's slot in place of the game's Draw.
void ViewDraw(void* view, float seconds) {
    Prime(view);
    reinterpret_cast<DrawFn>(kSceneViewDraw)(view, seconds);
    AfterDraw(view);
}

// Writes into the game's image, the region's protection put back afterwards (gui.cpp's
// WriteProtected, for a vtable page that may be read-only or writable data).
bool WriteSlot(std::uintptr_t address, std::uintptr_t value) {
    mach_vm_address_t region = address;
    mach_vm_size_t regionSize = 0;
    vm_region_basic_info_data_64_t info{};
    mach_msg_type_number_t infoCount = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object = MACH_PORT_NULL;
    if (mach_vm_region(mach_task_self(), &region, &regionSize, VM_REGION_BASIC_INFO_64,
                       reinterpret_cast<vm_region_info_t>(&info), &infoCount, &object) != KERN_SUCCESS ||
        region > address)
        return false;
    const std::uintptr_t first = address & ~std::uintptr_t(0xFFF);
    const std::uintptr_t last = (address + sizeof value + 0xFFF) & ~std::uintptr_t(0xFFF);
    if (vm_protect(mach_task_self(), first, last - first, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) !=
        KERN_SUCCESS)
        return false;
    std::memcpy(reinterpret_cast<void*>(address), &value, sizeof value);
    vm_protect(mach_task_self(), first, last - first, FALSE, info.protection);
    return true;
}

bool TakeSlot() {
    if (g_slotTaken) return true;
    if (g_slotRefused) return false;
    const std::uintptr_t slot = kSceneViewVtable + kVtDraw;
    const std::uintptr_t now = *reinterpret_cast<const std::uintptr_t*>(slot);
    if (now == kSceneViewDraw && WriteSlot(slot, reinterpret_cast<std::uintptr_t>(&ViewDraw))) {
        g_slotTaken = true;
        return true;
    }
    g_slotRefused = true;
    Log("model-preload: the 3D view's Draw belongs to another patch (0x%lx); not primed", static_cast<unsigned long>(now));
    return false;
}

void Forget(void* panel) {
    if (g_pending)
        g_pending->erase(std::remove_if(g_pending->begin(), g_pending->end(), [=](const Job& j) { return j.panel == panel; }),
                         g_pending->end());
    if (g_ready)
        g_ready->erase(std::remove_if(g_ready->begin(), g_ready->end(), [=](const Ready& r) { return r.job.panel == panel; }),
                       g_ready->end());
}

void Queue(void* panel, void* view, const char* kind) {
    if (!g_pending) g_pending = new std::vector<Job>;
    if (*static_cast<const std::uintptr_t*>(view) == kSceneViewVtable) g_pending->push_back({panel, view, kind});
}

// ------------------------------------------------------------------------ item 112

const std::uintptr_t kTextureReference = 0x1001f9ff4UL, kTextureBind = 0x1001f72b0UL;
using TextureReferenceFn = void* (*)(const char* name, const char* alternative);
using TextureBindFn = void (*)(void* texture);
const char* const kScreens[] = {"classsel", "kmrplayout", "pazaaksetup", "pazaakgame", "savename", "galaxymap"};
const int kPerFrame = 2;

// Between the thread and the GUI frames.
struct Shared {
    std::mutex lock;
    std::vector<std::string> ready;   // read, to be referenced
    unsigned filesRead = 0;
    bool working = false;
};
Shared* g_shared = nullptr;
char g_submitted = 0;                  // the family last submitted, 0 before the first
std::vector<std::string>* g_referenced = nullptr;
std::vector<void*>* g_kept = nullptr;
unsigned g_referencedCount = 0;
bool g_reported = true;

bool IsFile(const std::string& path) { struct stat s; return stat(path.c_str(), &s) == 0 && S_ISREG(s.st_mode); }

// The game's Assets folder, from the executable, <app>/Contents/MacOS/KOTOR_Exe
// (kmrp-assets/assets.cpp's AssetsDirectory, which this module does not link).
std::string AssetsDirectory() {
    char path[4096];
    uint32_t size = sizeof path;
    if (_NSGetExecutablePath(path, &size) != 0) return std::string();
    char resolved[PATH_MAX];
    std::string exe = realpath(path, resolved) ? resolved : path;
    for (int up = 0; up < 2; ++up) {
        const std::size_t slash = exe.rfind('/');
        if (slash == std::string::npos) return std::string();
        exe.erase(slash);
    }
    return exe + "/Assets";
}

// A whole file read and dropped: what stays is the system's cache of it.
bool ReadWhole(const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    std::vector<char> chunk(1 << 20);
    while (fread(chunk.data(), 1, chunk.size(), f) == chunk.size()) {}
    fclose(f);
    return true;
}

// The thread's work: files only, no engine object and no OpenGL.
void Work(std::string assets, std::string files, char family) {
    const std::string key = assets + "/chitin.key";
    std::vector<std::string> names;
    unsigned read = 0;
    auto add = [&names](const std::string& name) {
        if (!name.empty() && name.size() <= 16 && std::find(names.begin(), names.end(), name) == names.end())
            names.push_back(name);
    };
    std::vector<K1PreloadPicture> pictures(512);
    for (const char* screen : kScreens) {
        std::string source = files.empty() ? std::string() : files + "/" + screen + ".gui";
        if (source.empty() || !IsFile(source)) {
            source = assets + "/override/" + screen + ".gui";
            if (!IsFile(source)) source.clear();   // the game's own, through chitin.key
        }
        K1PreloadClassInfo info{};
        const int count = KmrpReadPreloadGui(key.c_str(), source.c_str(), screen, &info, pictures.data(),
                                             static_cast<int>(pictures.size()));
        if (count < 0) continue;
        ++read;
        for (int i = 0; i < count; ++i) {
            std::string fill = pictures[i].fill;
            if (fill.compare(0, 3, "kmr") != 0) continue;
            if (fill.compare(0, 4, "kmrp") == 0 && fill.size() > 4) fill[3] = family;
            add(fill);
        }
        if (std::strcmp(screen, "classsel") == 0) add(info.fill);
    }
    add("lbl_pazaak");
    for (const std::string& name : names) {
        bool got = false;
        for (const char* extension : {".tga", ".tpc"})
            if (!got && !files.empty()) got = ReadWhole(files + "/" + name + extension);
        if (!got) {
            int width = 0, height = 0;
            unsigned char* pixels = KmrpReadPreloadTexture(assets.c_str(), "", name.c_str(), &width, &height);
            got = pixels != nullptr;
            free(pixels);
        }
        if (got) ++read;
    }
    // Every name is referenced, read here or not: the engine finds what these readers cannot.
    std::lock_guard<std::mutex> guard(g_shared->lock);
    g_shared->filesRead += read;
    g_shared->ready.insert(g_shared->ready.end(), names.begin(), names.end());
    g_shared->working = false;
}

void Submit(const char* why) {
    const char family = prompts::FamilyLetter();
    if (family == g_submitted) return;
    if (!g_shared) g_shared = new Shared;
    {
        std::lock_guard<std::mutex> guard(g_shared->lock);
        if (g_shared->working) return;    // one at a time; the next frame asks again
        g_shared->working = true;
    }
    const std::string assets = AssetsDirectory();
    const char* files = standalone::FilesDirectory();
    g_submitted = family;
    g_reported = false;
    std::thread(Work, assets, std::string(files ? files : ""), family).detach();
    Log("preload: the controller's screens queued from %s, art %c", why, family);
}

}  // namespace

void MovieFrame() { Submit("a movie"); }

void GuiFrame() {
    Submit("a GUI frame");                          // also covers skipped movies
    if (!g_shared) return;
    if (g_pending && !g_pending->empty()) return;   // the previews' first render comes first
    if (!CGLGetCurrentContext()) return;
    if (!g_referenced) g_referenced = new std::vector<std::string>;
    if (!g_kept) g_kept = new std::vector<void*>;
    for (int done = 0; done < kPerFrame;) {
        std::string name;
        {
            std::lock_guard<std::mutex> guard(g_shared->lock);
            if (g_shared->ready.empty()) break;
            name = std::move(g_shared->ready.front());
            g_shared->ready.erase(g_shared->ready.begin());
        }
        if (std::find(g_referenced->begin(), g_referenced->end(), name) != g_referenced->end()) continue;
        g_referenced->push_back(name);
        void* const texture = reinterpret_cast<TextureReferenceFn>(kTextureReference)(name.c_str(), nullptr);
        if (!texture) continue;
        reinterpret_cast<TextureBindFn>(kTextureBind)(texture);
        g_kept->push_back(texture);
        ++g_referencedCount;
        ++done;
    }
    bool idle;
    unsigned filesRead;
    {
        std::lock_guard<std::mutex> guard(g_shared->lock);
        idle = !g_shared->working && g_shared->ready.empty();
        filesRead = g_shared->filesRead;
    }
    if (idle && !g_reported) {
        g_reported = true;
        Log("preload: %u files read during the movie, %u textures referenced", filesRead, g_referencedCount);
    }
}

void PanelLoaded(void* panel, bool hasGui) {
    Forget(panel);
    if (!hasGui || !Enabled3d()) return;
    const std::uintptr_t vtable = *static_cast<const std::uintptr_t*>(panel);
    if (vtable != kClassSelectVtable && vtable != kMainMenuVtable) return;
    if (!TakeSlot()) return;
    char* const base = static_cast<char*>(panel);
    if (vtable == kMainMenuVtable) {
        Queue(panel, base + kMainMenuView, "main-menu");
        return;
    }
    for (std::size_t i = 0; i < 6; ++i) Queue(panel, base + kClassViews + i * kClassViewStride, "class");
}

}  // namespace preload
}  // namespace kmrp
