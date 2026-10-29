#include <windows.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "K1ControllerPreload.h"
#include "K1GuiPreloadData.h"
#include "K1HudOptionsPolicy.h"
static int testWidth = 640, testHeight = 480;
static std::wstring testGame, testFolder, testCoreFolder;
static std::thread::id caller, actualWorker;
static std::atomic<int> writes{0}, warmed{0};
static std::mutex finishedLock;
static std::condition_variable finished;
static void Require(bool value, const char* reason) { if (!value) { std::puts(reason); std::exit(1); } }
static void WorkerOnly() {
    Require(std::this_thread::get_id() != caller, "Preload ran on movie/caller thread");
    if (actualWorker == std::thread::id()) actualWorker = std::this_thread::get_id();
    Require(actualWorker == std::this_thread::get_id(), "Preloads used different workers");
}
const std::wstring& KmrpRuntimeAssetDirectory() { return testFolder; }
extern "C" char __cdecl KmrpGlyphLetterK1() { return 's'; }
static bool modelsPending = false;
static int graphicsLookups = 0;
bool KmrpGuiModelsPendingK1() { return modelsPending; }
bool KmrpControllerRelistK1() { Require(false, "Worker called engine resource registration"); return false; }
void ControllerLogK1(const char*) {}
void KmrpWarmControllerPictureK1(const char*, int w, int h, bool) { WorkerOnly(); if (w > 0 && h > 0) ++warmed; }
bool KmrpWritePreloadPictureK1(const char*, const std::vector<std::uint8_t>& rgba, int w, int h) {
    WorkerOnly(); Require(rgba.size() == static_cast<std::size_t>(w) * h * 4, "Bad class art output");
    ++writes; finished.notify_all(); return true;
}
bool KmrpPreloadPictureReadyK1(const char*) { Require(std::this_thread::get_id() == caller, "Worker queried engine readiness"); return true; }
static DWORD WINAPI PreloadGetModuleFileNameW(HMODULE, LPWSTR out, DWORD n) {
    const std::wstring path = testGame + L"/swkotor.exe";
    Require(path.size() + 1 < n, "Path overflow"); std::wcscpy(out, path.c_str()); return static_cast<DWORD>(path.size());
}
static int __cdecl FakeCorePath(const char* name, wchar_t* out, unsigned n) {
    const std::wstring path = *name ? testCoreFolder + L"/" + std::wstring(name, name + std::strlen(name)) + L".gui" : testCoreFolder;
    if (path.size() >= n || GetFileAttributesW(path.c_str()) == INVALID_FILE_ATTRIBUTES) return 0;
    std::wcscpy(out, path.c_str()); return 1;
}
static HMODULE WINAPI PreloadGetModuleHandleW(LPCWSTR name) {
    if (!_wcsicmp(name, L"opengl32.dll")) ++graphicsLookups;
    return !testCoreFolder.empty() && !_wcsicmp(name, L"kmrp.dll") ? reinterpret_cast<HMODULE>(1) : nullptr;
}
static FARPROC WINAPI PreloadGetProcAddress(HMODULE, LPCSTR name) {
    return !std::strcmp(name, "KmrpPreloadGuiPathK1") ? reinterpret_cast<FARPROC>(&FakeCorePath) : nullptr;
}
struct K1Scene { std::string name; };
struct K1BackgroundJob { const K1Scene* scene; int width, height; char name[17]; };
struct K1BackgroundDone { std::string name, scene; int width, height; unsigned long ms; bool ok; };
static std::mutex g_bgLock;
static std::condition_variable g_bgWake;
static std::vector<K1BackgroundJob> g_bgJobs, g_bgLater;
static std::vector<std::string> g_bgClaimed;
static std::string g_bgDrawing;
static std::vector<K1BackgroundDone> g_bgDone;
static std::vector<std::function<void()>> g_bgGuiWork;
static bool g_bgRunning = false;
static bool K1ComposeScene(const K1Scene&, int, int, std::vector<std::uint8_t>&, bool) { WorkerOnly(); return true; }
static bool K1WriteTextureFiles(const char*, const std::vector<std::uint8_t>&, int, int) { WorkerOnly(); return true; }
// PRODUCTION_WORKER
#define GetModuleHandleW PreloadGetModuleHandleW
#define GetModuleFileNameW PreloadGetModuleFileNameW
#define GetProcAddress PreloadGetProcAddress
// PRODUCTION_PRELOAD

using KmrpHudOptions::ElementCount;
using HudSizes = std::array<int, ElementCount>;
static int sizeReads = 0;
static DWORD HudTick() { static DWORD tick = 0; return tick += 501; }
static BOOL HudAttributes(LPCWSTR, GET_FILEEX_INFO_LEVELS, LPVOID out) {
    static DWORD written = 0;
    static_cast<WIN32_FILE_ATTRIBUTE_DATA*>(out)->ftLastWriteTime.dwLowDateTime = ++written;
    return TRUE;
}
static UINT HudSize(LPCWSTR, LPCWSTR, INT, LPCWSTR) { ++sizeReads; return 100; }
#define GetTickCount HudTick
#define GetFileAttributesExW HudAttributes
#define GetPrivateProfileIntW HudSize
// PRODUCTION_HUD_SIZES
#undef GetTickCount
#undef GetFileAttributesExW
#undef GetPrivateProfileIntW

static bool WaitForClass(int expected) {
    std::unique_lock<std::mutex> lock(finishedLock);
    return finished.wait_for(lock, std::chrono::seconds(20), [&] { return writes >= expected; });
}
int wmain(int argc, wchar_t** argv) {
    Require(argc == 3 || argc == 4, "Need game and controller data paths");
    caller = std::this_thread::get_id(); testGame = argv[1]; testFolder = argv[2];
    if (argc == 4) testCoreFolder = argv[3];
    const auto savedCore = testCoreFolder;
    testCoreFolder.clear();
    for (int size : Sizes()) Require(size == KmrpHudOptions::Default, "Standalone HUD used KMRP sizing");
    Require(sizeReads == 0, "Standalone HUD read KMRP INI settings");
    testCoreFolder = L"fixture-core";
    Require(Sizes()[KmrpHudOptions::XboxActions] == 100 && sizeReads > 0, "Combined HUD did not read KMRP sizing");
    const int previousReads = sizeReads;
    testCoreFolder.clear();
    for (int size : Sizes()) Require(size == KmrpHudOptions::Default, "Stale KMRP HUD sizing persisted standalone");
    Require(sizeReads == previousReads, "Standalone HUD reread KMRP INI settings");
    testCoreFolder = savedCore;
    K1PreloadClassInfo probe{}; K1PreloadPicture probePictures[512] = {};
    const std::string probeKey = Utf8(testGame + L"/chitin.key");
    const std::string sourceGui = testCoreFolder.empty() ? "" : Utf8(testCoreFolder + L"/classsel.gui");
    const int sourceCount = KmrpReadPreloadGui(probeKey.c_str(), sourceGui.c_str(), "classsel", &probe, probePictures, 512);
    int probeW = 0, probeH = 0;
    unsigned char* probePixels = KmrpReadPreloadTexture(Utf8(testGame).c_str(), Utf8(testCoreFolder).c_str(), probe.fill, &probeW, &probeH);
    std::printf("Class source: %d fills, %s, texture %dx%d, panel %d,%d,%d,%d cancel %d,%d,%d,%d\n",
        sourceCount, probe.fill, probeW, probeH, probe.panel[0], probe.panel[1], probe.panel[2], probe.panel[3],
        probe.cancel[0], probe.cancel[1], probe.cancel[2], probe.cancel[3]); std::fflush(stdout);
    if (probePixels) {
        FILE* dump = std::fopen("build/controller-standalone/preload-check/source.rgba", "wb");
        if (dump) { std::fwrite(probePixels, 4, static_cast<std::size_t>(probeW) * probeH, dump); std::fclose(dump); }
    }
    std::free(probePixels);
    for (int i = 0; i < 10; ++i) KmrpControllerGuiMovieK1();
    Require(WaitForClass(1), "Class preparation failed without KMRP");
    // Enqueue a barrier: publication and every earlier task finish before assertions.
    std::atomic<bool> barrier{false};
    KmrpQueueControllerGuiWorkK1([&] { WorkerOnly(); barrier = true; finished.notify_all(); });
    { std::unique_lock<std::mutex> lock(finishedLock); Require(finished.wait_for(lock, std::chrono::seconds(20), [&] { return barrier.load(); }), "Worker did not finish"); }
    Require(writes == 1, "Movie frames submitted duplicate preload jobs");
    K1PreloadClassInfo info{}; K1PreloadPicture pictures[512] = {};
    const std::string key = Utf8(testGame + L"/chitin.key");
    Require(KmrpReadPreloadGui(key.c_str(), sourceGui.c_str(), "classsel", &info, pictures, 512) >= 0, "Native GUI read failed");
    ClassBoxK1 panel{}, cancel{}; std::memcpy(&panel, info.panel, 16); std::memcpy(&cancel, info.cancel, 16);
    ClassArtResultK1 result;
    Require(KmrpPreloadedClassArtK1(info.fill, panel, cancel, result), "Background class result not reusable");
    Require(result.selectAt.left < result.cancelAt.left, "Split buttons out of order");
    ++cancel.width;
    Require(!KmrpPreloadedClassArtK1(info.fill, panel, cancel, result), "Stale geometry accepted");
    Require(warmed > 0, "Controller GUI scene dependencies not queued");
    // Even a resource not decoded from the GUI pack must reach the engine-side
    // queue, preserving the old HUD preload's coverage (for example whitefill).
    KmrpQueueTexturePreloadK1("missing_fixture");
    barrier = false;
    KmrpQueueControllerGuiWorkK1([&] { WorkerOnly(); barrier = true; finished.notify_all(); });
    { std::unique_lock<std::mutex> lock(finishedLock); Require(finished.wait_for(lock, std::chrono::seconds(20), [&] { return barrier.load(); }), "Texture queue did not finish"); }
    { std::lock_guard<std::mutex> lock(stateLock); Require(std::find(readyTextures.begin(), readyTextures.end(), "missing_fixture") != readyTextures.end(), "Undecoded texture lost its engine preload"); }
    // The GUI callback must safely defer all engine upload work without a context.
    modelsPending = true;
    const int beforeGraphics = graphicsLookups;
    KmrpControllerGuiPreloadFrameK1();
    Require(graphicsLookups == beforeGraphics, "Optional GUI uploads ran ahead of model preload");
    modelsPending = false;
    KmrpControllerGuiPreloadFrameK1();
    Require(graphicsLookups > beforeGraphics, "Optional GUI upload path did not resume after model preload");
    // GUI-only startup/resize still submits the worker job if movies were skipped.
    ++testWidth;
    if (!testCoreFolder.empty()) testCoreFolder += L"/.";
    KmrpControllerGuiPreloadFrameK1();
    Require(WaitForClass(2), "GUI-only startup/resize did not queue preparation");
    barrier = false;
    KmrpQueueControllerGuiWorkK1([&] { WorkerOnly(); barrier = true; finished.notify_all(); });
    { std::unique_lock<std::mutex> lock(finishedLock); Require(finished.wait_for(lock, std::chrono::seconds(20), [&] { return barrier.load(); }), "Resize worker did not finish"); }
    Require(writes == 2, "Resize prepared an unexpected number of class pictures");
    std::printf("Controller preload (%s): actual worker differs from movie thread; class art reusable; repeated events deduplicated; stale geometry refused; GUI scenes queued; no engine/OpenGL calls on worker.\n", testCoreFolder.empty() ? "no KMRP" : "KMRP source snapshot");
    std::fflush(stdout);
    std::quick_exit(0); // The production worker intentionally lasts for the process.
}
