// The standalone controller patch ("KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"): KMRP's native
// controller support on a game that has no KMRP. Built with
// KMRP_CONTROLLER_STANDALONE by build_controller_standalone.cmd.
//
// This file is what the controller sources need from the rest of KMRP's module,
// reduced to what a controller needs:
//
//   - its files (the layout changes and the art made for the game's ORIGINAL
//     interface by tools/build_controller_assets.py, and SDL), embedded in the
//     module, unpacked to a private folder in %TEMP% and registered with the
//     game's resource manager. Nothing is written to Override or the game folder.
//   - no engine changes: no interface scaling, no memory, movie or map fixes. The
//     movie frame only reads the pad; KMRP's black bars are KMRP's.
//
// K1RuntimeAssets.cpp is the same mechanism for KMRP's own module, with a set per
// resolution and the blended sizes; this one has a single set, because the game's
// own menus are one 640x480 layout at every size it offers.
#include "K1RuntimeAssets.h"
#include "KmrpOptions.h"
#include "ControllerAssets.generated.h"
#include "K1ControllerBackend.h"
#include "K1Xpress.h"
#include "K1ResourceFolder.h"
#include <windows.h>
#include <bcrypt.h>
#include "K1Sha256.h"
#include "K1TempFolders.h"
#include <array>
#include <cstring>
#include <string>
#include <vector>

namespace {
using Key = std::array<unsigned char, 32>;
struct File { std::string name; Key key; const unsigned char* bytes; unsigned size, compressed; };

std::vector<File> files;
std::wstring cache;
bool unpacked = false;
bool registered = false;
std::string directoryAlias;

// One file, always present in a cache this module made: how a stale one is known.
// Until 2026-10-11 it was kmrplayout.gui, which LeaveLayoutsToKmrp deletes beside
// KMRP: no cache made with both patches installed was ever recognised, and each
// start of the game left its 177 MB behind (83 folders, 15 GB, on the maintainer's
// PC that day; 5.5 GB in a Proton prefix after one afternoon). The controller
// library is in every bank (tools/build_controller_assets.py, pack) and is never
// taken out of the folder, so those older folders are recognised by it too.
const char kMarker[] = "kmrp-sdl3.dll";
const wchar_t kMarkerW[] = L"kmrp-sdl3.dll";
const wchar_t kLockSuffix[] = L".lock";

void Report(const char* text)
{
    wchar_t path[MAX_PATH];
    if (!KmrpLogPath(path, L"kmrp-controller.log")) return;
    HANDLE file = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    SYSTEMTIME now; GetLocalTime(&now);
    char line[512];
    const int length = wsprintfA(line, "%04u-%02u-%02u %02u:%02u:%02u %s\r\n", now.wYear, now.wMonth,
                                 now.wDay, now.wHour, now.wMinute, now.wSecond, text);
    DWORD written;
    WriteFile(file, line, static_cast<DWORD>(length), &written, nullptr);
    CloseHandle(file);
}

// The bank: "KCAST001", a file count, then per file its name (u16 length, ASCII, no
// path), SHA-256, size, compressed size and XPRESS-Huffman stream.
bool ReadBank()
{
    if (!files.empty()) return true;
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&ReadBank), &module)) return false;
    HRSRC resource = FindResourceW(module, MAKEINTRESOURCEW(101), MAKEINTRESOURCEW(10));
    if (!resource) return false;
    const unsigned size = SizeofResource(module, resource);
    auto at = static_cast<const unsigned char*>(LockResource(LoadResource(module, resource)));
    if (!at || size < 12 || std::memcmp(at, "KCAST001", 8)) return false;
    const unsigned char* end = at + size;
    unsigned count;
    std::memcpy(&count, at + 8, 4);
    at += 12;
    if (!count || count > 4000) return false;
    std::vector<File> parsed;
    bool marker = false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned short length;
        if (end - at < 2) return false;
        std::memcpy(&length, at, 2); at += 2;
        if (!length || length > 255 || end - at < length + 40) return false;
        File file;
        file.name.assign(reinterpret_cast<const char*>(at), length); at += length;
        if (file.name.find_first_of("/\\:") != std::string::npos || file.name.find("..") != std::string::npos) return false;
        std::memcpy(file.key.data(), at, 32); at += 32;
        std::memcpy(&file.size, at, 4); std::memcpy(&file.compressed, at + 4, 4); at += 8;
        if (!file.size || file.size > (64u << 20) || static_cast<std::size_t>(end - at) < file.compressed) return false;
        file.bytes = at; at += file.compressed;
        marker = marker || file.name == kMarker;
        parsed.push_back(std::move(file));
    }
    if (at != end || !marker) return false;
    files.swap(parsed);
    return true;
}

bool MakeCache()
{
    if (!cache.empty()) return true;
    wchar_t temp[MAX_PATH], reserved[MAX_PATH];
    if (!GetTempPathW(MAX_PATH, temp)) return false;
    KmrpRemoveStaleCaches(temp, L"KMC*.tmp", kMarkerW, kLockSuffix);
    if (!GetTempFileNameW(temp, L"KMC", 0, reserved)) return false;
    // Exclusively the empty reservation this process just made.
    if (!DeleteFileW(reserved) || !CreateDirectoryW(reserved, nullptr)) return false;
    cache = reserved;
    // Held for the life of the process and deleted with it, even on a crash.
    CreateFileW((cache + kLockSuffix).c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
    return true;
}

bool Unpack()
{
    if (unpacked) return true;
    // Asked every frame (KmrpRuntimeAssetDirectory): a failure is remembered, as trying again
    // decoded and hashed a file each frame on a full disk (audit THR-2).
    static bool failed = false;
    if (failed) return false;
    if (!ReadBank() || !MakeCache()) { failed = true; return false; }
    std::vector<unsigned char> output;
    bool ok = true;
    for (const File& file : files) {
        output.resize(file.size);
        Key measured;
        if (!KmrpXpressDecode(file.bytes, file.compressed, output.data(), output.size()) ||
            !KmrpSha256(output.data(), file.size, measured) || measured != file.key) { ok = false; break; }
        const std::wstring path = cache + L"\\" + std::wstring(file.name.begin(), file.name.end());
        HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (handle == INVALID_HANDLE_VALUE) { ok = false; break; }
        DWORD written = 0;
        ok = WriteFile(handle, output.data(), file.size, &written, nullptr) && written == file.size;
        CloseHandle(handle);
        if (!ok) break;
    }
    unpacked = ok;
    failed = !ok;
    return ok;
}

// Given to the game as K1RuntimeAssets.cpp gives its own (K1ResourceFolder.h).
bool RegisterDirectory()
{
    const std::string path = KmrpNarrowPathK1(cache);
    if (path.empty()) return false;
    const std::string alias = "kmrc_" + path.substr(path.find_last_of('\\') + 1);
    if (!KmrpGiveFolderK1(path, alias)) return false;
    directoryAlias = alias + ":";
    return true;
}
}

// A file written into the folder after it was registered (a badge drawn at the size it is
// shown, K1XboxControls.cpp, issue 68) is found once the folder is listed anew:
// 0x4088E0, as K1RuntimeAssets.cpp's RegisterFolder does for a set whose files changed.
bool KmrpControllerRelistK1()
{
    return registered && KmrpRelistFolderK1(directoryAlias);
}

// SDL is loaded from here (K1ControllerBackend.cpp), so the folder exists by the
// time a pad is looked for, whether or not the game has asked for a resource yet.
const std::wstring& KmrpRuntimeAssetDirectory()
{
    Unpack();
    return cache;
}

// The rumble settings, KMRP\controller.ini in the game folder (kmrp-controller.ini
// beside the game until 2026-10-20; KmrpControllerSettingsPath) (K1Rumble.cpp reads it,
// and takes these same values when it is missing). KMRP's installer writes this
// file; with no installer the module does, once, so the player has something to
// find and edit. A file already there is the player's and is never touched.
const char kDefaultSettings[] = R"(; KMRP Controller settings. Read while the game runs; changes take effect within
; a second, no restart needed. Delete this file to get the defaults back.
[Rumble]
; Off, Original (BioWare's shipped rumble only) or Enhanced (adds KMRP's haptics)
Mode=Enhanced
; 0 to 100 percent
Strength=100
; the lightsaber hum, 0 to 100 percent of BioWare's level (0 turns it off);
; 6 is the weakest an Xbox pad can play
SaberHum=6
; the hum pulses: on for SaberHumPulseMs (0 = a steady hum), then off until
; the next pulse -- a gap picked at random between SaberHumPeriodMinMs and
; SaberHumPeriodMaxMs, afresh for every pulse (make them equal for a fixed rhythm)
SaberHumPulseMs=100
SaberHumPeriodMinMs=500
SaberHumPeriodMaxMs=2000
; 1 writes every rumble event to kmrp-rumble.log in the logs folder beside this file
Debug=0

[Hud]
; Xbox (laid out like the original Xbox version's while the pad is in use; the
; game's own with mouse and keyboard) or PC (the game's own HUD always).
; Read when the game starts. KOTOR Patch Manager's "Xbox-style HUD" option, where
; the manager offers options, decides instead of this line.
Style=Xbox
)";

void WriteDefaultSettings()
{
    // KMRP\controller.ini, an earlier kmrp-controller.ini moved there first
    // (KmrpControllerSettingsPath).
    wchar_t path[MAX_PATH];
    if (!KmrpControllerSettingsPath(path)) return;
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;      // there already, or the folder is read-only
    DWORD written;
    WriteFile(file, kDefaultSettings, sizeof(kDefaultSettings) - 1, &written, nullptr);
    CloseHandle(file);
}

// Beside KMRP (its module is patches\kmrp.dll, loaded before the game runs) the
// screens are KMRP's, laid out for the resolution in use, and they already hold the
// controls this patch adds to the game's own layouts (the same tags, from the same
// build step). So this patch's copies of the game's layouts are taken out of the
// folder before it is registered, and only its textures are served.
void LeaveLayoutsToKmrp()
{
    if (!GetModuleHandleW(L"kmrp.dll") || cache.empty()) return;
    WIN32_FIND_DATAW found;
    HANDLE find = FindFirstFileW((cache + L"\\*.gui").c_str(), &found);
    if (find == INVALID_HANDLE_VALUE) return;
    do {
        DeleteFileW((cache + L"\\" + found.cFileName).c_str());
    } while (FindNextFileW(find, &found));
    FindClose(find);
}

extern "C" int KmrpControllerCues(const char* key, const char* name, const char* sourceGui, const char* outGui,
                                  const char* donorGui);
extern "C" const char* KmrpControllerCueScreen(int i);

// Controller Live Adaptive Layout's screens (2026-10-30): the file the game would load, a
// mod's in Override or else the game's own (through chitin.key), with the controller's cues
// added at run time and written into the folder, which the game searches before Override.
// Not laid out: without KMRP every screen keeps its file's size. The party, swap-tabs, LT/RT
// and combat cues, the Controller Layout entry and the travelling A (its label from this
// patch's kmrplayout.gui) are the steps tools/build_controller_assets.py ran on the game's
// own files; the bank carried those 16 files until this date, and a mod's file in Override
// lost to them, its layout replaced by the game's. A file the cues cannot reach (one that
// has them, or lacks the controls they sit by) is left to the game. Beside KMRP its screens
// already carry the cues (LeaveLayoutsToKmrp), so nothing is written.
void CueScreens()
{
    if (GetModuleHandleW(L"kmrp.dll") || cache.empty()) return;
    wchar_t folder[MAX_PATH];
    if (!KmrpGameFolder(folder)) return;
    const std::wstring game = folder;
    const std::string key = KmrpUtf8PathK1(game + L"\\chitin.key"), donor = KmrpUtf8PathK1(cache + L"\\kmrplayout.gui");
    if (key.empty() || donor.empty()) return;
    for (int i = 0; const char* screen = KmrpControllerCueScreen(i); ++i) {
        const std::wstring name(screen, screen + std::strlen(screen)), theirs = game + L"\\override\\" + name;
        const std::wstring target = cache + L"\\" + name, work = target + L".tmp";
        const bool mod = GetFileAttributesW(theirs.c_str()) != INVALID_FILE_ATTRIBUTES;
        const std::string out = KmrpUtf8PathK1(work), source = mod ? KmrpUtf8PathK1(theirs) : std::string();
        if (out.empty() || (mod && source.empty())) continue;
        const int result = KmrpControllerCues(key.c_str(), screen, mod ? source.c_str() : nullptr, out.c_str(), donor.c_str());
        if (result == 0 && MoveFileExW(work.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING)) {
            if (mod) {
                char line[200];
                wsprintfA(line, "The Override folder's %s was given the controller's button prompts.", screen);
                Report(line);
            }
            continue;
        }
        DeleteFileW(work.c_str());
        if (result != 3) {
            char line[200];
            wsprintfA(line, "%s could not be given the controller's button prompts (%d); the game shows it without them.",
                      screen, result);
            Report(line);
        }
    }
}

// Hooked before the game's first resource lookup, on the game's own thread.
extern "C" void __cdecl ControllerPrepareResourcesK1(void* manager)
{
    static bool busy = false, failed = false, settings = false;
    if (!settings) {
        settings = true;
        WriteDefaultSettings();
        // The game's main thread, before its first movie: SDL is started here so it
        // hears about pads coming back all session (StartControllerSdlK1, issue 71).
        StartControllerSdlK1();
    }
    if (busy || registered || failed || !manager || manager != *reinterpret_cast<void**>(0x7A39E8)) return;
    busy = true;
    if (!Unpack()) {
        failed = true;
        Report("The controller's files could not be unpacked to the temporary folder. The pad still "
               "works; its button prompts and the Controller Layout screen are missing.");
    } else {
        LeaveLayoutsToKmrp();
        CueScreens();
        // Once, whichever way: this hook runs on every resource lookup.
        registered = RegisterDirectory();
        if (!registered) {
            failed = true;
            Report("The controller's folder could not be given to the game. The pad still works; "
                   "its button prompts and the Controller Layout screen are missing.");
        }
    }
    busy = false;
}

// The movie window is left as the game draws it: KMRP's bars are KMRP's.
bool KpmMoviesOffK1() { return true; }

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(module);
    return TRUE;
}
