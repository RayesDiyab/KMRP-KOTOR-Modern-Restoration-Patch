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
#include <windows.h>
#include <compressapi.h>
#include <bcrypt.h>
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
const char kMarker[] = "kmrplayout.gui";
const wchar_t kMarkerW[] = L"kmrplayout.gui";
const wchar_t kLockSuffix[] = L".lock";

void Report(const char* text)
{
    wchar_t path[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? wcsrchr(path, L'\\') : nullptr;
    if (!slash || wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-controller.log")) return;
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

bool Sha(const unsigned char* data, unsigned size, Key& result)
{
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return false;
    const bool ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
        BCryptHashData(hash, const_cast<unsigned char*>(data), size, 0) >= 0 &&
        BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
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

// Remove the folders of games that are no longer running: each launch makes its
// own, and nothing else would ever remove one. A folder is this module's when it is
// a KMC*.tmp directory, the name GetTempFileNameW gave it, holding the marker; it is
// in use while its game holds the lock beside it, which cannot be deleted then.
// Only plain files directly inside are removed, as this module makes nothing else.
void RemoveStaleCaches(const std::wstring& temp)
{
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((temp + L"KMC*.tmp").c_str(), &found);
    if (search == INVALID_HANDLE_VALUE) return;
    do {
        if (!(found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
            (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) continue;
        const std::wstring directory = temp + found.cFileName;
        if (GetFileAttributesW((directory + L"\\" + kMarkerW).c_str()) == INVALID_FILE_ATTRIBUTES) continue;
        const std::wstring lock = directory + kLockSuffix;
        if (GetFileAttributesW(lock.c_str()) != INVALID_FILE_ATTRIBUTES && !DeleteFileW(lock.c_str())) continue;
        WIN32_FIND_DATAW file{};
        HANDLE inside = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (inside == INVALID_HANDLE_VALUE) continue;
        bool plain = true;
        do {
            if (!wcscmp(file.cFileName, L".") || !wcscmp(file.cFileName, L"..")) continue;
            if (file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { plain = false; break; }
        } while (FindNextFileW(inside, &file));
        FindClose(inside);
        if (!plain) continue;
        inside = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (inside == INVALID_HANDLE_VALUE) continue;
        do {
            if (!(file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
                DeleteFileW((directory + L"\\" + file.cFileName).c_str());
        } while (FindNextFileW(inside, &file));
        FindClose(inside);
        RemoveDirectoryW(directory.c_str());
    } while (FindNextFileW(search, &found));
    FindClose(search);
}

bool MakeCache()
{
    if (!cache.empty()) return true;
    wchar_t temp[MAX_PATH], reserved[MAX_PATH];
    if (!GetTempPathW(MAX_PATH, temp)) return false;
    RemoveStaleCaches(temp);
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
    if (!ReadBank() || !MakeCache()) return false;
    DECOMPRESSOR_HANDLE decompressor = nullptr;
    if (!CreateDecompressor(COMPRESS_ALGORITHM_XPRESS_HUFF, nullptr, &decompressor)) return false;
    std::vector<unsigned char> output;
    bool ok = true;
    for (const File& file : files) {
        output.resize(file.size);
        SIZE_T size = 0;
        Key measured;
        if (!Decompress(decompressor, file.bytes, file.compressed, output.data(), output.size(), &size) ||
            size != output.size() || !Sha(output.data(), file.size, measured) || measured != file.key) { ok = false; break; }
        const std::wstring path = cache + L"\\" + std::wstring(file.name.begin(), file.name.end());
        HANDLE handle = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (handle == INVALID_HANDLE_VALUE) { ok = false; break; }
        DWORD written = 0;
        ok = WriteFile(handle, output.data(), file.size, &written, nullptr) && written == file.size;
        CloseHandle(handle);
        if (!ok) break;
    }
    CloseDecompressor(decompressor);
    unpacked = ok;
    return ok;
}

// As K1RuntimeAssets.cpp: CExoAliasList::ResolveFileName treats the text before ':'
// as an alias, drive letters included, so the folder is given a private alias and
// registered through it.
bool RegisterDirectory()
{
    void* manager = *reinterpret_cast<void**>(0x7A39E8);
    void* base = *reinterpret_cast<void**>(0x7A39E0);
    if (!manager || !base) return false;
    void* aliases = *reinterpret_cast<void**>(static_cast<unsigned char*>(base) + 0x0C);
    if (!aliases) return false;
    char path[MAX_PATH]; BOOL substituted = FALSE;
    if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, path, MAX_PATH, nullptr, &substituted) || substituted) return false;
    if (directoryAlias.empty()) {
        const std::string alias = "kmrc_" + std::string(path + cache.find_last_of(L"\\") + 1);
        void* aliasName[2]{}; void* aliasPath[2]{};
        reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasName, alias.c_str());
        reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasPath, path);
        reinterpret_cast<void(__thiscall*)(void*, void*, void*)>(0x5E6880)(aliases, aliasName, aliasPath);
        reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasPath);
        reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasName);
        directoryAlias = alias + ":";
    }
    void* name[2]{};
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(name, directoryAlias.c_str());
    const int result = reinterpret_cast<int(__thiscall*)(void*, void*)>(0x408800)(manager, name);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(name);
    return result != 0;
}
}

// SDL is loaded from here (K1ControllerBackend.cpp), so the folder exists by the
// time a pad is looked for, whether or not the game has asked for a resource yet.
const std::wstring& KmrpRuntimeAssetDirectory()
{
    Unpack();
    return cache;
}

// The rumble settings, kmrp-controller.ini beside the game (K1Rumble.cpp reads it,
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
; 1 writes every rumble event to kmrp-rumble.log in this folder
Debug=0

[Hud]
; PC (the game's own HUD always) or Xbox (laid out like the original Xbox
; version's while the pad is in use; the game's own with mouse and keyboard).
; Read when the game starts. KOTOR Patch Manager's "Xbox-style HUD" option, where
; the manager offers options, decides instead of this line.
Style=PC
)";

void WriteDefaultSettings()
{
    wchar_t path[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? wcsrchr(path, L'\\') : nullptr;
    if (!slash || wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-controller.ini")) return;
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;      // there already, or the folder is read-only
    DWORD written;
    WriteFile(file, kDefaultSettings, sizeof(kDefaultSettings) - 1, &written, nullptr);
    CloseHandle(file);
}

// Hooked before the game's first resource lookup, on the game's own thread.
extern "C" void __cdecl KmrpPrepareResourcesK1(void* manager)
{
    static bool busy = false, failed = false, settings = false;
    if (!settings) { settings = true; WriteDefaultSettings(); }
    if (busy || registered || failed || !manager || manager != *reinterpret_cast<void**>(0x7A39E8)) return;
    busy = true;
    if (!Unpack()) {
        failed = true;
        Report("The controller's files could not be unpacked to the temporary folder. The pad still "
               "works; its button prompts and the Controller Layout screen are missing.");
    } else {
        if (RegisterDirectory()) registered = true;
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
