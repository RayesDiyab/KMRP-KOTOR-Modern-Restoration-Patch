// Controller-owned preload requests. The movie callback only submits copied paths;
// file I/O, decoding and drawing run on the existing picture worker. GPU upload and
// directory registration are collected only with a context on the GUI thread.
#include "K1ControllerPreload.h"
#include "K1GuiPreloadData.h"
#include <windows.h>
#include <mutex>
#include <set>
#include <string>
#include <memory>
#include <atomic>
#include <cstdlib>

extern const std::wstring& KmrpRuntimeAssetDirectory();
extern bool KmrpControllerRelistK1();
extern "C" char __cdecl KmrpGlyphLetterK1();
extern bool KmrpGuiModelsPendingK1();
extern void ControllerLogK1(const char*);

namespace {
std::mutex stateLock;
std::set<std::string> textures;
std::vector<std::string> readyTextures;
std::vector<void*> keptTextures;
struct ClassCache { std::string fill; ClassBoxK1 panel{}, cancel{}; ClassArtResultK1 art; bool ready = false; };
ClassCache classCache;
int queuedWidth = 0, queuedHeight = 0;
std::wstring queuedClassPath;
std::atomic<unsigned> generation{0};

std::string Utf8(const std::wstring& path) {
    if (path.empty()) return {};
    const int count = WideCharToMultiByte(CP_UTF8, 0, path.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<std::size_t>(count), 0);
    WideCharToMultiByte(CP_UTF8, 0, path.c_str(), -1, &out[0], count, nullptr, nullptr);
    out.resize(count - 1); return out;
}
std::wstring GameDirectory() {
    wchar_t path[32768] = {};
    GetModuleFileNameW(nullptr, path, 32768);
    std::wstring out(path); const auto slash = out.find_last_of(L"\\/");
    return slash == std::wstring::npos ? L"." : out.substr(0, slash);
}
bool Same(const ClassBoxK1& a, const ClassBoxK1& b) { return !std::memcmp(&a, &b, sizeof a); }
bool File(const std::wstring& path) { return GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES; }
std::string CoreAssets() {
    using PathFn = int(__cdecl*)(const char*, wchar_t*, unsigned);
    HMODULE core = GetModuleHandleW(L"kmrp.dll");
    auto path = core ? reinterpret_cast<PathFn>(GetProcAddress(core, "KmrpPreloadGuiPathK1")) : nullptr;
    wchar_t assets[32768] = {};
    return path && path("", assets, 32768) ? Utf8(assets) : std::string();
}

void DecodeTexture(const std::string& game, const std::string& assets, const std::string& name) {
    int w = 0, h = 0;
    std::unique_ptr<unsigned char, decltype(&std::free)> pixels(
        KmrpReadPreloadTexture(game.c_str(), assets.c_str(), name.c_str(), &w, &h), &std::free);
    // Reading and decoding warms the file cache; the engine retains the texture
    // on collection. Resources outside the GUI pack (including engine fills)
    // still get their normal engine preload when this reader cannot decode them.
    // Never call AurTextureGetReference or OpenGL on this worker.
    std::lock_guard<std::mutex> lock(stateLock);
    readyTextures.push_back(name);
}
}

extern "C" void __cdecl KmrpQueueTexturePreloadK1(const char* name) {
    if (!name || !*name || std::strlen(name) > 16) return;
    const std::string texture(name), game = Utf8(GameDirectory()), assets = CoreAssets();
    {
        std::lock_guard<std::mutex> lock(stateLock);
        if (!textures.insert(texture).second) return;
    }
    KmrpQueueControllerGuiWorkK1([game, assets, texture] { DecodeTexture(game, assets, texture); });
}

void KmrpControllerGuiMovieK1() {
    const int width = *reinterpret_cast<const int*>(0x0078D1D4), height = *reinterpret_cast<const int*>(0x0078D1D8);
    if (width <= 0 || height <= 0 || KmrpRuntimeAssetDirectory().empty()) return;
    using PathFn = int(__cdecl*)(const char*, wchar_t*, unsigned);
    HMODULE core = GetModuleHandleW(L"kmrp.dll");
    auto corePath = core ? reinterpret_cast<PathFn>(GetProcAddress(core, "KmrpPreloadGuiPathK1")) : nullptr;
    wchar_t classPath[32768] = {};
    if (corePath) corePath("classsel", classPath, 32768);
    unsigned requested;
    {
        std::lock_guard<std::mutex> lock(stateLock);
        if (width == queuedWidth && height == queuedHeight && queuedClassPath == classPath) return;
        queuedWidth = width; queuedHeight = height;
        queuedClassPath = classPath;
        requested = ++generation;
    }
    const std::wstring game = GameDirectory(), folder = KmrpRuntimeAssetDirectory();
    // The costly controller GUI sources, including their source textures. Other
    // screens can join this list without adding another thread or movie hook.
    const char* names[] = {"classsel", "kmrplayout", "pazaaksetup", "pazaakgame", "savename", "galaxymap"};
    struct Source { std::string name, path; };
    std::vector<Source> sources;
    for (const char* name : names) {
        wchar_t live[32768] = {};
        std::wstring file = folder + L"\\" + std::wstring(name, name + std::strlen(name)) + L".gui";
        if (corePath && corePath(name, live, 32768)) file = live;
        else {
            const std::wstring overrideFile = game + L"\\Override\\" + std::wstring(name, name + std::strlen(name)) + L".gui";
            if (File(overrideFile)) file = overrideFile;
        }
        sources.push_back({name, Utf8(file)});
    }
    const std::string root = Utf8(game), key = Utf8(game + L"\\chitin.key");
    const std::string assets = CoreAssets();
    const char family = KmrpGlyphLetterK1();
    KmrpQueueControllerGuiWorkK1([sources, root, key, assets, requested, family] {
        for (const auto& source : sources) {
            K1PreloadClassInfo info{};
            K1PreloadPicture pictures[512] = {};
            const int count = KmrpReadPreloadGui(key.c_str(), source.path.c_str(), source.name.c_str(), &info, pictures, 512);
            if (count < 0) continue;
            for (int i = 0; i < count; ++i) {
                const auto& p = pictures[i];
                if (!std::strncmp(p.fill, "kmrp", 4)) {
                    std::string name(p.fill); name[3] = family;
                    KmrpWarmControllerPictureK1(name.c_str(), p.width, p.height, false);
                    for (char other : {'p', 's', 'n', 'd'}) if (other != family) {
                        name[3] = other; KmrpWarmControllerPictureK1(name.c_str(), p.width, p.height, true);
                    }
                } else if (!std::strncmp(p.fill, "kmr", 3)) {
                    KmrpWarmControllerPictureK1(p.fill, p.width, p.height, false);
                }
            }
            if (source.name != "classsel" || !info.fill[0]) continue;
            int w = 0, h = 0;
            std::unique_ptr<unsigned char, decltype(&std::free)> pixels(
                KmrpReadPreloadTexture(root.c_str(), assets.c_str(), info.fill, &w, &h), &std::free);
            if (!pixels) continue;
            ClassCache result;
            result.fill = info.fill;
            std::memcpy(&result.panel, info.panel, sizeof result.panel);
            std::memcpy(&result.cancel, info.cancel, sizeof result.cancel);
            if (!BuildClassSelectArtK1(info.fill, result.panel, result.cancel, pixels.get(), w, h, result.art) ||
                !KmrpWritePreloadPictureK1(result.art.drawn, result.art.sheet, w, h)) continue;
            result.art.sheet.clear(); result.art.sheet.shrink_to_fit(); result.ready = true;
            {
                std::lock_guard<std::mutex> lock(stateLock);
                if (requested == generation) classCache = std::move(result);
            }
            DecodeTexture(root, assets, info.fill);
        }
        DecodeTexture(root, assets, "lbl_pazaak");
    });
    ControllerLogK1("preload: controller GUI work queued by movie/startup event");
}

void KmrpControllerGuiPreloadFrameK1() {
    KmrpControllerGuiMovieK1(); // also covers skipped/disabled startup movies
    if (KmrpGuiModelsPendingK1()) return; // preview rendering outranks optional GUI texture uploads
    using CurrentContext = void* (WINAPI*)();
    HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    auto context = gl ? reinterpret_cast<CurrentContext>(GetProcAddress(gl, "wglGetCurrentContext")) : nullptr;
    if (!context || !context()) return;
    for (int i = 0; i < 2; ++i) {
        std::string name;
        {
            std::lock_guard<std::mutex> lock(stateLock);
            if (readyTextures.empty()) break;
            name = std::move(readyTextures.front()); readyTextures.erase(readyTextures.begin());
        }
        void* texture = reinterpret_cast<void*(__cdecl*)(const char*, int)>(0x00423A60)(name.c_str(), 0);
        if (texture) {
            reinterpret_cast<void(__thiscall*)(void*)>(0x004214B0)(texture);
            keptTextures.push_back(texture);
        }
    }
}

bool KmrpPreloadedClassArtK1(const char* fill, const ClassBoxK1& panel, const ClassBoxK1& cancel, ClassArtResultK1& out) {
    std::lock_guard<std::mutex> lock(stateLock);
    if (!classCache.ready || classCache.fill != fill || !Same(panel, classCache.panel) || !Same(cancel, classCache.cancel)) return false;
    if (!KmrpPreloadPictureReadyK1(classCache.art.drawn)) return false;
    std::memcpy(out.drawn, classCache.art.drawn, sizeof out.drawn);
    out.selectAt = classCache.art.selectAt; out.cancelAt = classCache.art.cancelAt;
    return true;
}
