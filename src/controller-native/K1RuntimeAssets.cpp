// KMRP's art, unpacked from its art pack into a cache of KMRP's own and registered
// through the game's resource manager. Never writes the player's Override.
//
// The pack, kmrp-assets.pack beside this module in the game's patches folder
// (tools/kmrp_pack.py writes it, K1AssetPack.cpp reads it), names every file of every
// resolution's set with its SHA-256, and stores only the files this module cannot
// make: the build ran the blend helper below for every set and left out each file the
// helper writes exactly as the set has it (tools/build_native_assets.py). So a set is
// produced in three steps (BuildSet): the files the pack holds are written, the helper
// writes the rest, and every file is held against the set's index. Until 2026-10-05
// every file was stored (KNAST001, 243 MB of a 249 MB patch); until 2026-10-19 the
// stored files were a bank inside this module (KNAST002, XPRESS, 109 MB of 113 MB),
// which the pack replaced at 56 MB, so the installer that carries it is half the size
// (the maintainer, 2026-10-19: "have the smallest possible installer"). The installer
// also has every size the display offers made before the game first starts
// (KmrpRuntimeAssetsPrepare), and the game does the same for any it has not
// (Prebuild).
//
// The cache is kept between runs (2026-10-19, as the Mac's since 2026-10-08,
// macos/patches/kmrp-assets/assets.cpp, whose design this follows):
// %LOCALAPPDATA%\KMRP\cache\<build>\, <build> being the first 16 characters of the
// bank's identity, so a new build starts a new cache and the old ones are removed.
//
//     store\            the common files, unpacked once
//     sets\<W>x<H>\     a size's set, made the first time the size is used: the bank's
//                       files, the helper's, the bank's again where the helper's differ,
//                       and what KMRP makes from the player's own game for that height
//     fonts\            the fonts at each size they have been drawn at, made once each
//     gui-blend.bin     the blend helper's table, which it reads from a file
//     art-<pid>\        this run's links to store\, but for what Override has
//     fonts-<pid>\      this run's fonts at the sizes in use (links to fonts\)
//     set-<pid>-<n>\    this run's links to a set, one folder for each registration
//
// Until then every launch unpacked and checked every common file into a new folder in
// %TEMP%, and every change of resolution did it again: measured on the maintainer's PC
// on 2026-10-19, 14.0 s for the files at a start at 3440x1440 and 7.0 to 9.5 s at a
// change of size, 2.9 s of each change going to common files that never change. A
// set's layouts are made with the fonts at the default text size, as the build makes
// them (build_native_assets.shared_font_txi), so a set depends on its size alone; the
// text size is the fonts' business (the maintainer, 2026-10-19: "these should be
// independent"). Until then the helper measured captions with the fonts at the text
// size in use, which made a set's helper-made files differ from the build's.
#include "K1RuntimeAssets.h"
#include "NativeAssets.generated.h"
#include "KmrpOptions.h"
#include "K1AssetPack.h"
#include "K1PartyRosterGui.h"
#include "K1PartyRosterState.h"
#include "K1TextOptions.h"
#include "K1TextOptionsPolicy.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <list>
#include <map>
#include <set>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <algorithm>
#include <cstdio>
#include <sstream>
#include <iomanip>

extern "C" int KmrpGuiBlend(const char*, unsigned, unsigned, const char*, const char*);
extern "C" int KmrpGuiBlendCovers(const char*, unsigned, unsigned);
// macos/tools/kmrp-abilityicons.c and kmrp-gameart.c, compiled with KMRP_EMBEDDED.
extern "C" int KmrpAbilityIcons(const char* erf, unsigned height, const char* outdir, const char* reserved);
extern "C" int KmrpGameArt(const char* erf, const char* key, unsigned height, const char* outdir);
// macos/tools/kmrp-swoophud.c: the swoop race's HUD model, its parked speed segment moved
// out of a wide screen's view (issue #47). 0 written, 1 not the game's model (left alone),
// 3 the screen is not wide enough to need it.
extern "C" int KmrpSwoopHud(const char* key, const char* outdir, unsigned width, unsigned height);
// macos/tools/kmrp-guiadapt.c: the galaxy map's planets and Live slots where the game's
// 640x480 layout (or a mod's, in Override) has them, on this size's map (issue 67). 0
// written, 1 a layout could not be read, 2 could not write, 3 the mod's file is not
// 640x480 (left to the game).
extern "C" int KmrpGalaxyMap(const char* key, const char* setGui, const char* outGui, const char* sourceGui);
// The same file: the main menu's buttons on the bars of their art. 0 written.
extern "C" int KmrpMainMenuBars(const char* setGui, const char* outGui);
// The same file: Live Adaptive Layout, a screen the game's own file or a mod's (in Override)
// lays out, laid out for the size (tools/build_live_layout.py). 0 written, 1 a layout could
// not be read, 2 could not write, 3 the mod's file is not laid out for the game's size (left
// to the game), 4 not a screen it lays out.
extern "C" int KmrpLiveLayout(const char* key, const char* name, const char* sourceGui, int width, int height,
                              const char* outGui);
extern "C" int KmrpLiveLayoutCount(void);
extern "C" const char* KmrpLiveLayoutName(int i);
void KmrpRuntimeLog(const char* line);       // K1RuntimeEngine.cpp: one line into kmrp-kpm.log

namespace {
using Key = KmrpPack::Key;
using Entry = KmrpPack::Entry;
using Group = KmrpPack::Group;
// The art pack's index (Initialize), and the pack, open for the run.
std::map<Key, KmrpPack::Object> objects;
std::vector<Group> groups;
std::vector<KmrpPack::Block> blocks;
Key tableKey{};
HANDLE packFile = INVALID_HANDLE_VALUE;
bool packTried = false;                  // looked for once, until ClosePack
HANDLE runLock = INVALID_HANDLE_VALUE;   // root\run-<pid>.lock (Running)
std::wstring root;        // %LOCALAPPDATA%\KMRP\cache\<build>
std::wstring store;       // root\store
std::wstring cache;       // root\art-<pid>: this run's common files (KmrpRuntimeAssetDirectory)
std::wstring fontsView;   // root\fonts-<pid>
std::wstring setView;     // the newest size's folder as the game is shown it (KmrpRuntimeLayoutDirectory):
                          // root\sets\<W>x<H>, or root\set-<pid>-<n> of links
std::wstring rosterView;  // root\roster-<pid>-<n>: the party roster adapted for it, when there is one
int generation = 0;
int currentWidth = 0, currentHeight = 0;
bool registered = false;  // the common files and the fonts given to the game
// The blend helper and the game-art helpers keep their state in globals, so one size is
// made at a time, by the game's thread or the one that makes sizes ahead (Prebuild).
SRWLOCK buildLock = SRWLOCK_INIT;
struct Locked {
    Locked() { AcquireSRWLockExclusive(&buildLock); }
    ~Locked() { ReleaseSRWLockExclusive(&buildLock); }
};
// True only after adapting the supplied roster GUI successfully for this size.
bool managedPartyRoster = false;

bool Sha(const unsigned char* data, unsigned size, Key& result)
{
    // Opened once a thread: a set is some 2,100 files, each hashed on its way to the
    // cache, and opening the provider for every one of them was measurable.
    static thread_local BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    if (!algorithm && BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) {
        algorithm = nullptr;
        return false;
    }
    bool ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
        BCryptHashData(hash, const_cast<unsigned char*>(data), size, 0) >= 0 &&
        BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    return ok;
}

const wchar_t kLockSuffix[] = L".lock";

std::wstring Pid() { return std::to_wstring(GetCurrentProcessId()); }

bool IsDirectory(const std::wstring& path)
{
    const DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) &&
           !(attributes & FILE_ATTRIBUTE_REPARSE_POINT);
}

// The plain files directly in a folder, or its folders.
std::vector<std::wstring> Names(const std::wstring& directory, bool folders = false)
{
    std::vector<std::wstring> names;
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((directory + L"\\*").c_str(), &found);
    if (search == INVALID_HANDLE_VALUE) return names;
    do {
        const bool folder = (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (folder && (!wcscmp(found.cFileName, L".") || !wcscmp(found.cFileName, L".."))) continue;
        if (folder == folders && !(found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) names.push_back(found.cFileName);
    } while (FindNextFileW(search, &found));
    FindClose(search);
    return names;
}

// One of the cache's folders, which hold plain files only, and the folder itself.
void RemoveFlat(const std::wstring& directory)
{
    if (!IsDirectory(directory)) return;
    for (const auto& name : Names(directory)) {
        const std::wstring path = directory + L"\\" + name;
        SetFileAttributesW(path.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileW(path.c_str());
    }
    RemoveDirectoryW(directory.c_str());
}

// Whether a game is running that made a folder of the cache: it holds run-<pid>.lock
// open, delete on close, for its life. A lock that can be deleted is a game's that is
// gone (and is deleted with that).
bool Running(const std::wstring& folder, const std::wstring& pid)
{
    if (pid == Pid()) return true;
    const std::wstring lock = folder + L"\\run-" + pid + L".lock";
    return GetFileAttributesW(lock.c_str()) != INVALID_FILE_ATTRIBUTES && !DeleteFileW(lock.c_str());
}

// The caches of other builds, once no game of theirs runs, and this cache's folders of
// games that are no longer running: their links, and a set or font they left half made.
void RemoveStale(const std::wstring& parent, const std::wstring& build)
{
    for (const auto& name : Names(parent, true)) {
        if (name == build || name.size() != 16 || name.find_first_not_of(L"0123456789abcdef") != std::wstring::npos) continue;
        const std::wstring old = parent + L"\\" + name;
        bool busy = false;
        for (const auto& file : Names(old)) {
            if (file.compare(0, 4, L"run-") != 0) continue;
            const std::wstring pid = file.substr(4, file.find(L'.') - 4);
            if (Running(old, pid)) busy = true;
        }
        if (busy) continue;
        for (const auto& inner : Names(old, true)) {
            const std::wstring path = old + L"\\" + inner;
            for (const auto& deeper : Names(path, true)) RemoveFlat(path + L"\\" + deeper);
            RemoveFlat(path);
        }
        RemoveFlat(old);
    }
    const std::wstring here = parent + L"\\" + build;
    for (const auto& name : Names(here, true)) {
        std::wstring pid;
        if (!name.compare(0, 4, L"art-")) pid = name.substr(4);
        else if (!name.compare(0, 6, L"fonts-")) pid = name.substr(6);
        else if (!name.compare(0, 4, L"set-")) pid = name.substr(4, name.find(L'-', 4) - 4);
        else if (!name.compare(0, 7, L"roster-")) pid = name.substr(7, name.find(L'-', 7) - 7);
        else continue;
        if (!Running(here, pid)) RemoveFlat(here + L"\\" + name);
    }
    for (const auto* folder : {L"\\sets", L"\\fonts"}) {
        const std::wstring path = here + folder;
        for (const auto& name : Names(path, true)) {
            const std::size_t at = name.find(L".tmp");
            if (at != std::wstring::npos && !Running(here, name.substr(at + 4))) RemoveFlat(path + L"\\" + name);
        }
        for (const auto& name : Names(path)) {
            const std::size_t at = name.find(L".tmp");
            if (at != std::wstring::npos && !Running(here, name.substr(at + 4))) DeleteFileW((path + L"\\" + name).c_str());
        }
    }
}

// The per-launch caches in %TEMP% of builds before 2026-10-19. Each launch made its
// own directory (about 100 MB), and until 2026-10-04 nothing ever removed one:
// 63 had collected in %TEMP%, 5.4 GB.
//
// A cache is this module's when it is a KMR*.tmp directory, the name
// GetTempFileNameW gave it, holding the font atlas every size has. It is in use
// while its game holds the lock beside it, which cannot be deleted then. A cache
// from before the lock existed has none and is taken as stale. Only plain files
// directly inside are removed: this module never makes a subdirectory, so one that
// has any is left alone.
void RemoveStaleCaches(const std::wstring& temp)
{
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((temp + L"KMR*.tmp").c_str(), &found);
    if (search == INVALID_HANDLE_VALUE) return;
    do {
        if (!(found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
            (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) continue;
        const std::wstring directory = temp + found.cFileName;
        if (GetFileAttributesW((directory + L"\\dialogfont16x16.txi").c_str()) == INVALID_FILE_ATTRIBUTES) continue;
        const std::wstring lock = directory + kLockSuffix;
        if (GetFileAttributesW(lock.c_str()) != INVALID_FILE_ATTRIBUTES && !DeleteFileW(lock.c_str())) continue;
        WIN32_FIND_DATAW file{};
        HANDLE files = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (files == INVALID_HANDLE_VALUE) continue;
        bool plain = true;
        do {
            if (!wcscmp(file.cFileName, L".") || !wcscmp(file.cFileName, L"..")) continue;
            if (file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { plain = false; break; }
        } while (FindNextFileW(files, &file));
        FindClose(files);
        if (!plain) continue;
        files = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (files == INVALID_HANDLE_VALUE) continue;
        do {
            if (!(file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
                DeleteFileW((directory + L"\\" + file.cFileName).c_str());
        } while (FindNextFileW(files, &file));
        FindClose(files);
        RemoveDirectoryW(directory.c_str());
        DeleteFileW((directory + L".reserved.txt").c_str());
    } while (FindNextFileW(search, &found));
    FindClose(search);
}

// Bytes of the pack from `offset`, as many as `out` holds.
bool ReadAt(HANDLE file, std::uint32_t offset, std::vector<unsigned char>& out)
{
    OVERLAPPED at{};
    at.Offset = offset;
    DWORD got = 0;
    return ReadFile(file, out.data(), static_cast<DWORD>(out.size()), &got, &at) && got == out.size();
}

bool Initialize()
{
    if (!groups.empty()) return true;
    // Looked for once a run: a pack that is missing or another build's stays so.
    if (packTried) return false;
    packTried = true;
    // The art pack beside this module, in the game's patches folder, where the installer
    // writes it (tools/kmrp_pack.py); or in the game's patches folder when the module is
    // elsewhere, as the installer's copy is when it prepares the art
    // (KmrpRuntimeAssetsPrepare). Its index read now, a file's block when the file is
    // needed (Decode). Held open for the run, shared for deleting: an installer may remove
    // or replace it while a game runs, and this run keeps the file it opened.
    HMODULE module = nullptr;
    wchar_t path[MAX_PATH];
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&Initialize), &module)) return false;
    const DWORD named = GetModuleFileNameW(module, path, MAX_PATH);
    wchar_t* slash = named && named < MAX_PATH ? wcsrchr(path, L'\\') : nullptr;
    if (!slash || wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"kmrp-assets.pack")) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                              FILE_FLAG_RANDOM_ACCESS, nullptr);
    if (file == INVALID_HANDLE_VALUE && KmrpGamePath(path, L"patches\\kmrp-assets.pack"))
        file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                           FILE_FLAG_RANDOM_ACCESS, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        KmrpRuntimeLog("[KMRP] kmrp-assets.pack is not in the patches folder beside kmrp.dll, so KMRP's interface "
                       "cannot be made: install KMRP with its installer, which writes it");
        return false;
    }
    LARGE_INTEGER fileSize{};
    std::vector<unsigned char> index(KmrpPack::kHeaderSize);
    Key identity{};
    std::uint32_t start = 0;
    KmrpPack::Index parsed;
    bool ok = GetFileSizeEx(file, &fileSize) && ReadAt(file, 0, index) &&
              KmrpPack::ReadHeader(index.data(), index.size(), identity, start) && start <= fileSize.QuadPart;
    if (ok) {
        // The pack this module was built with, and no other: a module put in by hand beside
        // an older pack would name files the pack does not have.
        const std::string text = KmrpPack::IdentityText(identity);
        ok = std::wstring(text.begin(), text.end()) == KMRP_ASSET_BUILD;
        if (!ok) KmrpRuntimeLog("[KMRP] kmrp-assets.pack is from another build of KMRP than kmrp.dll: install KMRP again");
    }
    if (ok) {
        index.resize(start);
        ok = ReadAt(file, 0, index) &&
             KmrpPack::ReadIndex(index.data(), index.size(), static_cast<std::uint64_t>(fileSize.QuadPart), parsed) &&
             parsed.groups.size() == 67;
    }
    // The common files are all stored. A set's may be left to the blend helper.
    for (const auto& group : parsed.groups) {
        if (!ok || group.width != 0) continue;
        for (const auto& entry : group.entries) if (!parsed.objects.count(entry.key)) ok = false;
    }
    if (!ok) {
        CloseHandle(file);
        KmrpRuntimeLog("[KMRP] kmrp-assets.pack cannot be read");
        return false;
    }
    wchar_t temp[MAX_PATH]{};
    if (GetTempPathW(MAX_PATH, temp)) RemoveStaleCaches(temp);
    // The cache, under %LOCALAPPDATA% (or %TEMP% where that is not set), named after
    // the pack, so a new build starts a new one (RemoveStale removes the old).
    wchar_t local[MAX_PATH];
    const DWORD length = GetEnvironmentVariableW(L"LOCALAPPDATA", local, MAX_PATH);
    std::wstring parent = length && length < MAX_PATH ? std::wstring(local) : std::wstring(temp);
    if (parent.empty()) { CloseHandle(file); return false; }
    if (parent.back() != L'\\') parent += L'\\';
    parent += L"KMRP";
    CreateDirectoryW(parent.c_str(), nullptr);
    parent += L"\\cache";
    CreateDirectoryW(parent.c_str(), nullptr);
    const std::wstring build = std::wstring(KMRP_ASSET_BUILD).substr(0, 16);
    root = parent + L"\\" + build;
    if (!IsDirectory(root) && !CreateDirectoryW(root.c_str(), nullptr)) { CloseHandle(file); return false; }
    CreateDirectoryW((root + L"\\sets").c_str(), nullptr);
    CreateDirectoryW((root + L"\\fonts").c_str(), nullptr);
    // Held for the life of the process and deleted with it, even on a crash: a later
    // run reads a lock it can delete as "that game is gone" (Running).
    runLock = CreateFileW((root + L"\\run-" + Pid() + kLockSuffix).c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                          FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
    RemoveStale(parent, build);
    store = root + L"\\store";
    cache = root + L"\\art-" + Pid();
    fontsView = root + L"\\fonts-" + Pid();
    objects.swap(parsed.objects);
    groups.swap(parsed.groups);
    blocks.swap(parsed.blocks);
    tableKey = parsed.table;
    packFile = file;
    return true;
}

// Blocks that hold several files, kept unpacked while their files are asked for one at a
// time (a size's set, the common files), newest first, up to kKeepUnpacked bytes; let go
// once the work is done (ForgetUnpacked). A file that is a block of its own is unpacked
// straight into the caller's buffer.
SRWLOCK packLock = SRWLOCK_INIT;
std::list<std::pair<std::uint32_t, std::vector<unsigned char>>> unpacked;
std::size_t unpackedBytes = 0;
const std::size_t kKeepUnpacked = 48u << 20;

bool UnpackBlock(std::uint32_t number, std::vector<unsigned char>& out)
{
    const auto& block = blocks[number];
    std::vector<unsigned char> stored(block.stored);
    out.resize(block.size);
    return ReadAt(packFile, block.offset, stored) && KmrpPack::Unpack(block, stored.data(), out.data());
}

bool Decode(const Key& key, std::vector<unsigned char>& output)
{
    auto found = objects.find(key);
    if (found == objects.end()) return false;
    const auto& object = found->second;
    const auto& block = blocks[object.block];
    bool ok = false;
    AcquireSRWLockExclusive(&packLock);
    if (object.offset == 0 && object.size == block.size) {
        ok = UnpackBlock(object.block, output);
    } else {
        auto kept = std::find_if(unpacked.begin(), unpacked.end(),
                                 [&](const std::pair<std::uint32_t, std::vector<unsigned char>>& b) { return b.first == object.block; });
        if (kept != unpacked.end()) {
            unpacked.splice(unpacked.begin(), unpacked, kept);
            ok = true;
        } else {
            std::vector<unsigned char> data;
            if (UnpackBlock(object.block, data)) {
                unpackedBytes += data.size();
                unpacked.emplace_front(object.block, std::move(data));
                while (unpackedBytes > kKeepUnpacked && unpacked.size() > 1) {
                    unpackedBytes -= unpacked.back().second.size();
                    unpacked.pop_back();
                }
                ok = true;
            }
        }
        if (ok) {
            const auto& data = unpacked.front().second;
            output.assign(data.begin() + object.offset, data.begin() + object.offset + object.size);
        }
    }
    ReleaseSRWLockExclusive(&packLock);
    Key measured;
    return ok && KmrpPack::Unfilter(object.filter, output.data(), output.size()) &&
           Sha(output.data(), static_cast<unsigned>(output.size()), measured) && measured == key;
}

void ForgetUnpacked()
{
    AcquireSRWLockExclusive(&packLock);
    unpacked.clear();
    unpackedBytes = 0;
    ReleaseSRWLockExclusive(&packLock);
}

// The pack and the run's lock let go, when the installer has finished preparing: it may
// write the pack again in the same session (a reinstall), and the lock would otherwise
// mark the cache in use until the installer closes. The next Initialize starts afresh.
void ClosePack()
{
    ForgetUnpacked();
    if (packFile != INVALID_HANDLE_VALUE) CloseHandle(packFile);
    if (runLock != INVALID_HANDLE_VALUE) CloseHandle(runLock);
    packFile = runLock = INVALID_HANDLE_VALUE;
    objects.clear();
    groups.clear();
    blocks.clear();
    packTried = false;
}

bool Read(const std::wstring& path, std::vector<unsigned char>& output)
{
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    bool ok = GetFileSizeEx(file, &size) && size.QuadPart >= 0 && size.QuadPart < (256u << 20);
    if (ok) {
        output.resize(static_cast<std::size_t>(size.QuadPart)); DWORD got;
        ok = ReadFile(file, output.data(), static_cast<DWORD>(output.size()), &got, nullptr) && got == output.size();
    }
    CloseHandle(file); return ok;
}

// A new file, never written through an existing one: a folder of links shares its
// files with the cache, so writing into one would change the cache's. `known`: the
// bytes' SHA-256, held against what is read back.
bool WriteNew(const std::wstring& path, const std::vector<unsigned char>& bytes, const Key* known = nullptr)
{
    SetFileAttributesW(path.c_str(), FILE_ATTRIBUTE_NORMAL);
    DeleteFileW(path.c_str());
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    DWORD size = 0;
    const bool ok = WriteFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &size, nullptr) && size == bytes.size();
    CloseHandle(file);
    if (!ok || !known) return ok;
    std::vector<unsigned char> actual; Key measured;
    return Read(path, actual) && Sha(actual.data(), static_cast<unsigned>(actual.size()), measured) && measured == *known;
}

// A cached file shown in one of this run's folders: a hard link, which costs no copy
// (NTFS, and Wine on Linux file systems), or a copy where the file system has none.
bool Link(const std::wstring& from, const std::wstring& to)
{
    SetFileAttributesW(to.c_str(), FILE_ATTRIBUTE_NORMAL);
    DeleteFileW(to.c_str());
    return CreateHardLinkW(to.c_str(), from.c_str(), nullptr) || CopyFileW(from.c_str(), to.c_str(), TRUE);
}

// A folder is complete when the marker beside it (never inside: the game lists the
// folder as resources) holds the text it was finished with. Built under another name
// and renamed, so a run cut short leaves nothing that looks finished.
bool Complete(const std::wstring& directory, const std::string& stamp)
{
    std::vector<unsigned char> text;
    return IsDirectory(directory) && Read(directory + L".complete", text) &&
           std::string(text.begin(), text.end()) == stamp;
}

template<class Fill>
bool Build(const std::wstring& directory, const std::string& stamp, Fill fill)
{
    if (Complete(directory, stamp)) return true;
    const std::wstring work = directory + L".tmp" + Pid();
    DeleteFileW((directory + L".complete").c_str());
    RemoveFlat(directory);
    RemoveFlat(work);
    if (IsDirectory(directory) || !CreateDirectoryW(work.c_str(), nullptr)) return false;
    if (!fill(work) || !MoveFileExW(work.c_str(), directory.c_str(), 0)) {
        RemoveFlat(work);
        return false;
    }
    return WriteNew(directory + L".complete", std::vector<unsigned char>(stamp.begin(), stamp.end()));
}

// A path for the helpers, which take the system's code page; "" when the path has a
// character it cannot write.
std::string Narrow(const std::wstring& path)
{
    char text[MAX_PATH]; BOOL substituted = FALSE;
    if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, path.c_str(), -1, text, MAX_PATH, nullptr, &substituted) ||
        substituted) return std::string();
    return text;
}

// gui-blend.bin, beside the cache's folders: the blend helper reads it from a file.
bool TablePath(std::string& path)
{
    const std::wstring wide = root + L"\\gui-blend.bin";
    path = Narrow(wide);
    if (path.empty()) return false;
    if (GetFileAttributesW(wide.c_str()) != INVALID_FILE_ATTRIBUTES) return true;
    std::vector<unsigned char> table;
    const std::wstring work = wide + L".tmp" + Pid();
    if (Decode(tableKey, table) && WriteNew(work, table, &tableKey) && MoveFileExW(work.c_str(), wide.c_str(), 0)) return true;
    // Another of the installer's workers (KmrpRuntimeAssetsPrepare) wrote it first.
    DeleteFileW(work.c_str());
    return GetFileAttributesW(wide.c_str()) != INVALID_FILE_ATTRIBUTES;
}

// A folder given to the game under an alias of its own: the resource manager takes
// "ALIAS:", and CExoAliasList::ResolveFileName reads the text before ':' as an alias,
// drive letters included, so an absolute Windows path is never passed. `again`: a
// folder given before whose files changed is listed anew (0x4088E0) instead of added.
// The game searches the folder given last first (CExoResMan::AddKeyTable, 0x00406E20).
bool RegisterFolder(const std::wstring& folder, const std::string& alias, bool again)
{
    void* manager = *reinterpret_cast<void**>(0x7A39E8);
    if (!manager) return false;
    const std::string path = Narrow(folder);
    if (path.empty()) return false;
    if (!again) {
        void* base = *reinterpret_cast<void**>(0x7A39E0);
        if (!base) return false;
        void* aliases = *reinterpret_cast<void**>(static_cast<unsigned char*>(base) + 0x0C);
        if (!aliases) return false;
        void* aliasName[2]{}; void* aliasPath[2]{};
        reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasName, alias.c_str());
        reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasPath, path.c_str());
        reinterpret_cast<void(__thiscall*)(void*, void*, void*)>(0x5E6880)(aliases, aliasName, aliasPath);
        reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasPath);
        reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasName);
    }
    void* name[2]{};
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(name, (alias + ":").c_str());
    const int result = reinterpret_cast<int(__thiscall*)(void*, void*)>(again ? 0x4088E0 : 0x408800)(manager, name);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(name);
    return result != 0;
}

std::wstring Lower(std::wstring text)
{
    if (!text.empty()) CharLowerBuffW(&text[0], static_cast<DWORD>(text.size()));
    return text;
}

// The player's Override comes before KMRP's files (the maintainer's decision,
// 2026-10-11, after a player's own Override files had no effect). The game searches
// the directory registered last first (CExoResMan::AddKeyTable, 0x00406E20, links a
// new table at the head of its list with 0x005E9D70), and this module's is
// registered after Override, so until then KMRP's file won whenever both had one.
//
// The order of the directories is left as it is, and a file the player has in
// Override is left out of the folders the game is shown (OverrideHas, since
// 2026-10-19 when this run's folders are made; until then it was deleted from the one
// folder after it was written): that also covers a texture in the other format, which
// the order alone would not (the game prefers a .tpc to a .tga wherever each is). A
// texture is one thing with its .txi: a .tga or .tpc in Override leaves out KMRP's
// .tga, .tpc and .txi of that name, so a font from Override is read with its own
// metrics or the game's, never KMRP's. The cache itself keeps every file.
//
// Override is listed once, as the game lists it once: a file put there while the
// game runs is not seen by either.
// The glyph height KMRP's own font of each name has at the size in use, for the
// fonts Override supplies in its place (lower-case names, without extension).
std::map<std::string, float> overrideFontHeights;
const char* const fontNames[] = {
    "dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b", "dialogfont12x16",
    "dialogfont16x16", "dialogfont16x16a", "dialogfont16x16b", "dialogfont32x32",
    "fnt_console", "fnt_credits", "fnt_creditsa", "fnt_creditsb", "fnt_d10x10b",
    "fnt_d16x16", "fnt_d16x16a", "fnt_d16x16b", "fnt_dialog16x16", "fnt_galahad14"
};
int fontHeight = 720;

const Entry* FindEntry(const Group& group, const std::string& name)
{
    for (const auto& e : group.entries) if (e.name == name) return &e;
    return nullptr;
}

bool OverrideFont(const char* name)
{
    wchar_t folder[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, folder, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? wcsrchr(folder, L'\\') : nullptr;
    if (!slash) return true;
    *slash = 0;
    const std::string stem(name);
    const std::wstring base = std::wstring(folder) + L"\\override\\" + std::wstring(stem.begin(), stem.end());
    for (const auto* extension : {L".tga", L".tpc", L".txi"})
        if (GetFileAttributesW((base + extension).c_str()) != INVALID_FILE_ATTRIBUTES) return true;
    return false;
}

// `fontheight` out of a .txi's text, or 0.
float FontHeightOf(const std::vector<unsigned char>& txi)
{
    static const char key[] = "fontheight";
    const std::string text(txi.begin(), txi.end());
    for (std::size_t at = text.find(key); at != std::string::npos; at = text.find(key, at + 1)) {
        if (at != 0 && text[at - 1] != '\n' && text[at - 1] != '\r') continue;
        const double value = std::atof(text.c_str() + at + sizeof(key) - 1);
        if (value > 0.0 && value < 100.0) return static_cast<float>(value);
    }
    return 0.0f;
}

float FontTargetHeight(float sharedHeight, int screenHeight)
{
    // The shared HD sources were baked at 3x. Match the old per-size baker's
    // half-even rounding using integers, independent of the engine's FPU mode.
    const std::uint64_t pixels = static_cast<unsigned>(std::lround(sharedHeight * 100.0f));
    // The old builder rounded its scale to six decimals before baking. Keep
    // that detail too (12-point text at 1050p otherwise changes by one pixel).
    const std::uint64_t scaledHeight = screenHeight > 720 ? screenHeight : 720;
    const std::uint64_t scaleMicros = (scaledHeight * 1000000 + 360) / 720;
    const std::uint64_t numerator = pixels * scaleMicros;
    const std::uint64_t denominator = 3000000;
    std::uint64_t rounded = numerator / denominator;
    const auto remainder = numerator % denominator;
    if (remainder * 2 > denominator || (remainder * 2 == denominator && (rounded & 1))) ++rounded;
    return static_cast<float>(rounded) / 100.0f;
}

bool FontTxiAtHeight(std::vector<unsigned char>& data, float height)
{
    const float own = FontHeightOf(data);
    if (!(own > 0.001f) || !(height > 0.001f)) return false;
    const double factor = static_cast<double>(height) / own;
    std::istringstream input(std::string(data.begin(), data.end()));
    std::ostringstream output;
    std::string line;
    while (std::getline(input, line)) {
        std::istringstream field(line);
        std::string key; double value;
        field >> key;
        const bool dimension = key == "fontheight" || key == "baselineheight" || key == "texturewidth" ||
            key == "spacingR" || key == "spacingB";
        if (dimension && field >> value) {
            output << key << ' ' << std::fixed << std::setprecision(6)
                   << (key == "fontheight" ? height : value * factor) << '\n';
        } else output << line << '\n';
    }
    const std::string text = output.str();
    data.assign(text.begin(), text.end()); return true;
}

// A TXI field set to a value, every other line as it was.
bool SetTxiField(std::vector<unsigned char>& data, const char* key, double value)
{
    std::istringstream input(std::string(data.begin(), data.end()));
    std::ostringstream output;
    std::string line;
    bool found = false;
    while (std::getline(input, line)) {
        std::istringstream field(line);
        std::string name;
        field >> name;
        if (name == key) {
            output << key << ' ' << std::fixed << std::setprecision(6) << value << '\n';
            found = true;
        } else output << line << '\n';
    }
    const std::string text = output.str();
    data.assign(text.begin(), text.end());
    return found;
}

// One axis of an image resampled: each new texel the average of the old ones it
// covers, weighted by how much of each it covers (shrinking), or the two nearest
// blended by distance (growing). `stride` is how far apart one line's texels are.
void ResampleAxis(const std::vector<float>& in, int inLength, int lines, int stride, int lineStride,
                  std::vector<float>& out, int outLength, int outStride, int outLineStride)
{
    const double scale = static_cast<double>(inLength) / outLength;
    for (int o = 0; o < outLength; ++o) {
        // The weights for this texel, the same for every line.
        double start = o * scale, end = (o + 1) * scale;
        int first, last;
        double weights[64];
        if (scale >= 1.0) {
            first = static_cast<int>(start);
            last = (std::min)(inLength - 1, static_cast<int>(std::ceil(end)) - 1);
            if (last - first >= 64) last = first + 63;
            for (int i = first; i <= last; ++i)
                weights[i - first] = ((std::min)(end, i + 1.0) - (std::max)(start, static_cast<double>(i))) / scale;
        } else {
            const double centre = (o + 0.5) * scale - 0.5;
            first = (std::max)(0, static_cast<int>(std::floor(centre)));
            last = (std::min)(inLength - 1, first + 1);
            const double t = (std::min)(1.0, (std::max)(0.0, centre - first));
            weights[0] = last == first ? 1.0 : 1.0 - t;
            if (last != first) weights[1] = t;
        }
        for (int line = 0; line < lines; ++line) {
            double sum = 0.0;
            for (int i = first; i <= last; ++i) sum += weights[i - first] * in[static_cast<size_t>(line) * lineStride + static_cast<size_t>(i) * stride];
            out[static_cast<size_t>(line) * outLineStride + static_cast<size_t>(o) * outStride] = static_cast<float>(sum);
        }
    }
}

// An HD style's atlas (an uncompressed 32-bit TGA, white letters in alpha, as
// tools/build_scaled_fonts.write_tga writes them) made `factor` times its size, so it
// is drawn one texel to one pixel. Its UVs are fractions of the atlas, so they stay
// right; the TXI is given the new width. False if the file is not such a TGA.
bool FitAtlas(std::vector<unsigned char>& tga, float factor, int& newWidth)
{
    if (tga.size() < 18 || tga[1] != 0 || tga[2] != 2 || tga[16] != 32) return false;
    const size_t offset = 18 + tga[0];
    const int width = tga[12] | (tga[13] << 8), height = tga[14] | (tga[15] << 8);
    if (width <= 0 || height <= 0 || tga.size() < offset + static_cast<size_t>(width) * height * 4) return false;
    newWidth = (std::max)(1, static_cast<int>(std::lround(width * factor)));
    const int newHeight = (std::max)(1, static_cast<int>(std::lround(height * static_cast<double>(newWidth) / width)));
    if (newWidth == width && newHeight == height) return true;
    const size_t pixels = static_cast<size_t>(width) * height;
    // White letters (the baked atlases) need only their alpha resampled; an atlas with
    // colour in it (fnt_galahad14, the original's own letters with their dark edge) has
    // every channel resampled.
    bool white = true;
    for (size_t i = 0; i < pixels && white; ++i)
        white = tga[offset + i * 4] == 255 && tga[offset + i * 4 + 1] == 255 && tga[offset + i * 4 + 2] == 255;
    std::vector<unsigned char> out(tga.begin(), tga.begin() + offset);
    out[12] = static_cast<unsigned char>(newWidth & 0xFF); out[13] = static_cast<unsigned char>(newWidth >> 8);
    out[14] = static_cast<unsigned char>(newHeight & 0xFF); out[15] = static_cast<unsigned char>(newHeight >> 8);
    const size_t newPixels = static_cast<size_t>(newWidth) * newHeight;
    out.resize(offset + newPixels * 4, 255);
    std::vector<float> plane(pixels), across(static_cast<size_t>(newWidth) * height), down(newPixels);
    for (int channel = white ? 3 : 0; channel < 4; ++channel) {
        for (size_t i = 0; i < pixels; ++i) plane[i] = tga[offset + i * 4 + channel];
        // Across, then down: each pass reads one plane and writes the next.
        ResampleAxis(plane, width, height, 1, width, across, newWidth, 1, newWidth);
        ResampleAxis(across, height, newWidth, newWidth, 1, down, newHeight, newWidth, 1);
        for (size_t i = 0; i < newPixels; ++i) {
            const long v = std::lround(down[i]);
            out[offset + i * 4 + channel] = static_cast<unsigned char>(v < 0 ? 0 : v > 255 ? 255 : v);
        }
    }
    tga.swap(out);
    return true;
}

// The two HD styles are baked at six times the original fonts' size
// (tools/build_font_from_ttf.py for Old HD, tools/build_hd_original_fonts.py for HD
// Original), the size 100% text is drawn at on a 2160-line screen; each atlas is
// fitted to its drawn size here, so it is drawn one texel to one pixel and is as sharp
// at the largest text size as at the smallest (2026-10-18, the maintainer's
// direction). The sizes text is drawn at are those of the 3x bake they replace.
constexpr float kHdBakeScale = 6.0f;
constexpr float kSizeReferenceScale = 3.0f;

const Group* CommonGroup()
{
    for (const auto& g : groups) if (!g.width) return &g;
    return nullptr;
}

std::wstring Wide(const std::string& name) { return std::wstring(name.begin(), name.end()); }

// The size a font is drawn at on a screen `height` lines high: `target` at the default
// text size (also what an Override font of that name is drawn at,
// KmrpFontMetricsLoadedK1), `sized` at the text size in use.
bool FontSizes(unsigned i, int height, float& target, float& sized)
{
    const Group* common = CommonGroup();
    if (!common) return false;
    char source[32];
    sprintf_s(source, "kmrfhd%02u.txi", i);
    const Entry* baseline = FindEntry(*common, source);
    std::vector<unsigned char> data;
    if (!baseline || !Decode(baseline->key, data)) return false;
    target = FontTargetHeight(FontHeightOf(data) * kSizeReferenceScale / kHdBakeScale, height);
    sized = target * (static_cast<float>(KmrpTextSizeForFontK1(fontNames[i])) / KmrpTextOptions::Default);
    return target > 0.0f;
}

// One font of a style at one size, in the cache's fonts\ (2026-10-19), made the first
// time: the style's TXI set to the size and, for an HD style, its atlas fitted to it
// (FitAtlas). Until then every start and every change of size made all eighteen again,
// 1.0 to 1.3 s on the maintainer's PC. Called under the build lock.
bool CachedFont(const char* prefix, unsigned i, float sized, bool fitted, std::wstring& txiPath, std::wstring& tgaPath)
{
    unsigned bits;
    std::memcpy(&bits, &sized, sizeof bits);
    wchar_t number[24];
    swprintf_s(number, L"%02u-%08X", i, bits);
    const std::wstring base = root + L"\\fonts\\" + std::wstring(prefix, prefix + std::strlen(prefix)) + number;
    txiPath = base + L".txi";
    tgaPath = base + L".tga";
    if (GetFileAttributesW(txiPath.c_str()) != INVALID_FILE_ATTRIBUTES &&
        GetFileAttributesW(tgaPath.c_str()) != INVALID_FILE_ATTRIBUTES) return true;
    const Group* common = CommonGroup();
    if (!common) return false;
    char source[32];
    std::vector<unsigned char> txi, tga;
    sprintf_s(source, "%s%02u.txi", prefix, i);
    const Entry* metrics = FindEntry(*common, source);
    sprintf_s(source, "%s%02u.tga", prefix, i);
    const Entry* atlas = FindEntry(*common, source);
    if (!metrics || !atlas || !Decode(metrics->key, txi) || !Decode(atlas->key, tga)) return false;
    const float own = FontHeightOf(txi);
    if (!(own > 0.001f) || !FontTxiAtHeight(txi, sized)) return false;
    if (fitted) {
        int newWidth = 0;
        if (!FitAtlas(tga, sized / own, newWidth) || !SetTxiField(txi, "texturewidth", newWidth / 100.0)) return false;
    }
    // Each under a working name, the atlas first: a TXI is never there without it.
    const std::wstring work = L".tmp" + Pid();
    if (!WriteNew(tgaPath + work, tga) || !MoveFileExW((tgaPath + work).c_str(), tgaPath.c_str(), MOVEFILE_REPLACE_EXISTING) ||
        !WriteNew(txiPath + work, txi) || !MoveFileExW((txiPath + work).c_str(), txiPath.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        DeleteFileW((tgaPath + work).c_str());
        DeleteFileW((txiPath + work).c_str());
        return false;
    }
    return true;
}

// The metrics the blend helper measures captions with: dialogfont16x16 in HD Original at
// the default text size for a screen `height` lines high, the TXI the build gives the
// helper (build_native_assets.shared_font_txi), made as CachedFont makes that font, in
// the same single precision, without fitting the atlas. So a set is the same at every
// text size and font style, and the helper writes the build's files exactly (since
// 2026-10-19; until then it was given the fonts at the text size in use).
bool ReferenceTxi(int height, std::vector<unsigned char>& txi)
{
    const unsigned i = 4;   // dialogfont16x16
    const Group* common = CommonGroup();
    if (!common) return false;
    float target, sized;
    if (!FontSizes(i, height, target, sized)) return false;
    sized = target;         // the default text size
    // The atlas's width, which FitAtlas scales: read once.
    static int width = 0;
    char source[32];
    std::vector<unsigned char> data;
    if (!width) {
        sprintf_s(source, "kmrfho%02u.tga", i);
        const Entry* atlas = FindEntry(*common, source);
        if (!atlas || !Decode(atlas->key, data) || data.size() < 18) return false;
        width = data[12] | (data[13] << 8);
    }
    sprintf_s(source, "kmrfho%02u.txi", i);
    const Entry* metrics = FindEntry(*common, source);
    if (!metrics || !Decode(metrics->key, txi)) return false;
    const float own = FontHeightOf(txi);
    if (!(own > 0.001f) || !FontTxiAtHeight(txi, sized)) return false;
    const float factor = sized / own;
    const int newWidth = (std::max)(1, static_cast<int>(std::lround(width * factor)));
    return SetTxiField(txi, "texturewidth", newWidth / 100.0);
}

// The style's eighteen fonts at the sizes in use, in this run's fonts folder: links to
// the cache's (CachedFont). A font the player's Override has is the game's to read from
// there (OverrideFont): left out, with the size KMRP's own would have noted
// (overrideFontHeights). `preserveOverride` (a change of style in the game): those keep
// what was noted at the start.
bool ApplyTextPreferences(bool preserveOverride)
{
    const int style = KmrpTextFontStyleK1();
    const bool fitted = style != KmrpTextOptions::Original;
    const char* prefix = style == KmrpTextOptions::Original ? "kmrfog" :
                         style == KmrpTextOptions::HdOriginal ? "kmrfho" : "kmrfhd";
    const Group* common = CommonGroup();
    if (!common || fontsView.empty()) return false;
    // Every source there before anything changes.
    for (unsigned i = 0; i < 18; ++i) {
        if (preserveOverride && OverrideFont(fontNames[i])) continue;
        char source[32];
        for (const char* extension : {".tga", ".txi"}) {
            sprintf_s(source, "%s%02u%s", prefix, i, extension);
            const Entry* entry = FindEntry(*common, source);
            if (!entry || !objects.count(entry->key)) return false;
        }
    }
    if (!IsDirectory(fontsView) && !CreateDirectoryW(fontsView.c_str(), nullptr)) return false;
    for (unsigned i = 0; i < 18; ++i) {
        const bool theirs = OverrideFont(fontNames[i]);
        if (preserveOverride && theirs) continue;
        float target, sized;
        if (!FontSizes(i, fontHeight, target, sized)) return false;
        overrideFontHeights[fontNames[i]] = target;
        const std::wstring name = fontsView + L"\\" + Wide(fontNames[i]);
        if (theirs) {
            DeleteFileW((name + L".tga").c_str());
            DeleteFileW((name + L".txi").c_str());
            continue;
        }
        std::wstring txi, tga;
        {
            Locked lock;
            if (!CachedFont(prefix, i, sized, fitted, txi, tga)) return false;
        }
        if (!Link(tga, name + L".tga") || !Link(txi, name + L".txi")) return false;
    }
    return true;
}

// The fonts of the style in use at a screen height, made ahead (Prebuild).
void PrefitFonts(int height)
{
    const int style = KmrpTextFontStyleK1();
    const bool fitted = style != KmrpTextOptions::Original;
    const char* prefix = style == KmrpTextOptions::Original ? "kmrfog" :
                         style == KmrpTextOptions::HdOriginal ? "kmrfho" : "kmrfhd";
    for (unsigned i = 0; i < 18; ++i) {
        float target, sized;
        if (!FontSizes(i, height, target, sized)) return;
        std::wstring txi, tga;
        Locked lock;
        if (!CachedFont(prefix, i, sized, fitted, txi, tga)) return;
    }
}

// Whether the player's Override has a file of this name, or for a texture a .tga or .tpc
// of its name: the game prefers a .tpc to a .tga wherever each is, and a texture is one
// thing with its .txi. Override is listed once a run, as the game lists it once. Not
// resources of the game, so never Override's: the controller library, loaded from the
// common files' folder.
bool overrideListed = false;
std::map<std::wstring, bool> overrideNames, overrideTextures;
bool OverrideHas(const std::wstring& file)
{
    auto& names = overrideNames;
    auto& textures = overrideTextures;
    if (!overrideListed) {
        overrideListed = true;
        wchar_t folder[MAX_PATH];
        const DWORD size = GetModuleFileNameW(nullptr, folder, MAX_PATH);
        wchar_t* slash = size && size < MAX_PATH ? wcsrchr(folder, L'\\') : nullptr;
        if (!slash) return false;
        *slash = 0;
        for (const auto& found : Names(std::wstring(folder) + L"\\override")) {
            const std::wstring name = Lower(found);
            names[name] = true;
            const std::size_t dot = name.find_last_of(L'.');
            if (dot != std::wstring::npos && (!name.compare(dot, std::wstring::npos, L".tga") ||
                                              !name.compare(dot, std::wstring::npos, L".tpc")))
                textures[name.substr(0, dot)] = true;
        }
    }
    const std::wstring name = Lower(file);
    const std::size_t dot = name.find_last_of(L'.');
    const std::wstring extension = dot == std::wstring::npos ? std::wstring() : name.substr(dot);
    if (extension == L".dll" || extension == L".bin") return false;
    if (names.count(name)) return true;
    return (extension == L".tga" || extension == L".tpc" || extension == L".txi") && textures.count(name.substr(0, dot));
}

// The party roster for the size: KMRP's layout (from the set) adapted to the 32-slot
// roster, written into this run's folder for the size, never into the set.
bool AdaptPartyRosterK1(const std::wstring& set, const std::wstring& view)
{
    managedPartyRoster = false;
    if (!KmrpPartyRoster32ActiveK1()) return false;
    wchar_t game[MAX_PATH];
    const DWORD length=GetModuleFileNameW(nullptr,game,MAX_PATH);
    wchar_t* slash=length && length<MAX_PATH?wcsrchr(game,L'\\'):nullptr;
    if (!slash) return false;
    *slash=0;
    const std::wstring source=std::wstring(game)+L"\\override\\partyselection.gui";
    std::vector<unsigned char> roster,layout,adapted;
    if (!Read(set+L"\\partyselection.gui",layout)) return false;
    WIN32_FILE_ATTRIBUTE_DATA info{};
    const bool supplied=GetFileAttributesExW(source.c_str(),GetFileExInfoStandard,&info)!=0;
    std::string reason;
    bool built=false;
    if(supplied) {
        // Preserve mod-specific captions/IDs/navigation and refuse malformed
        // input rather than masking it with the generated fallback.
        if(info.nFileSizeHigh || info.nFileSizeLow>(2u<<20) || !Read(source,roster))return false;
        built=KmrpBuildPartyRosterGui(roster,layout,adapted,reason);
    } else built=KmrpGeneratePartyRosterGui(layout,adapted,reason);
    if(!built) {
        KmrpRuntimeLog(("[KMRP] party roster: original layout retained; "+reason).c_str());
        return false;
    }
    if (!WriteNew(view+L"\\partyselection.gui",adapted)) return false;
    managedPartyRoster = true;
    KmrpRuntimeLog("[KMRP] party roster: runtime layout ready for this resolution; source files unchanged");
    return true;
}

// The galaxy map for the size: KMRP's map with every planet and Live slot where the game's
// own 640x480 layout puts it on the galaxy, or where a mod's 640x480 galaxymap.gui in
// Override puts it (issue 67), written into `folder`, which the game searches before the
// set and Override. Every size's set came with High Resolution Menus' hand-placed planets,
// another arrangement than the game's; and a mod's file at the game's size, left to the
// game, drew the map 640x480 in the middle of the screen. A mod's file of any other size is
// left to the game, as before. The folder may hold a link into the set under this name
// (LinkSet), so the file is written beside it and moved over it, never written through it.
std::wstring GameFolder();
bool AdaptGalaxyMapK1(const std::wstring& set, const std::wstring& folder)
{
    const std::wstring game = GameFolder();
    if (game.empty()) return false;
    const bool theirs = OverrideHas(L"galaxymap.gui");
    const std::wstring target = folder + L"\\galaxymap.gui", work = target + L".tmp" + Pid();
    const std::string key = Narrow(game + L"\\chitin.key"), layout = Narrow(set + L"\\galaxymap.gui");
    const std::string out = Narrow(work), source = theirs ? Narrow(game + L"\\override\\galaxymap.gui") : std::string();
    if (key.empty() || layout.empty() || out.empty() || (theirs && source.empty())) return false;
    const int result = KmrpGalaxyMap(key.c_str(), layout.c_str(), out.c_str(), theirs ? source.c_str() : nullptr);
    if (result != 0) {
        DeleteFileW(work.c_str());
        if (result == 3) KmrpRuntimeLog("[KMRP] galaxy map: the Override folder's galaxymap.gui is not the game's "
                                        "640x480 layout; it is left to the game");
        else KmrpRuntimeLog("[KMRP] galaxy map: could not be placed; KMRP's map is used as it is");
        return false;
    }
    SetFileAttributesW(target.c_str(), FILE_ATTRIBUTE_NORMAL);
    if (!MoveFileExW(work.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        DeleteFileW(work.c_str());
        return false;
    }
    if (KmrpDebugLogs() || theirs)
        KmrpRuntimeLog(theirs ? "[KMRP] galaxy map: the destinations of the Override folder's galaxymap.gui placed on KMRP's map"
                              : "[KMRP] galaxy map: the planets placed where the game's own layout has them");
    return true;
}

// The main menu's buttons on the bars of their art, in each of the size's main-menu
// layouts (the game picks one by the screen), written into `folder` as the galaxy map is.
// The game's layout spaces the buttons 24 apart and the art's bars 25, which a caption
// drifting six pixels off its bar shows at three times (macos/tools/kmrp-guiadapt.c,
// KmrpMainMenuBars; the maintainer, 2026-10-22). A layout the player's Override has is left
// to the game.
bool AdaptMainMenuK1(const std::wstring& set, const std::wstring& folder)
{
    bool any = false;
    for (const wchar_t* name : {L"mainmenu.gui", L"mainmenu8x6.gui", L"mainmenu10x7.gui", L"mainmenu12x9.gui",
                                L"mainmenu16x12.gui"}) {
        if (OverrideHas(name)) continue;
        const std::wstring target = folder + L"\\" + name, work = target + L".tmp" + Pid();
        const std::string layout = Narrow(set + L"\\" + name), out = Narrow(work);
        if (layout.empty() || out.empty() || KmrpMainMenuBars(layout.c_str(), out.c_str()) != 0) {
            DeleteFileW(work.c_str());
            continue;
        }
        SetFileAttributesW(target.c_str(), FILE_ATTRIBUTE_NORMAL);
        if (!MoveFileExW(work.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING)) {
            DeleteFileW(work.c_str());
            continue;
        }
        any = true;
    }
    return any;
}

// Live Adaptive Layout: the screens its table lists, laid out for the size from the file the
// game would load, a mod's 640x480 file in Override or else the game's own (through
// chitin.key), written into `folder` as the galaxy map is, over the set's. A mod's file laid
// out for another size is left to the game, as before. Until 2026-10-28 these screens came
// only from the set, and a mod's file took the place of the whole screen at 640x480.
bool AdaptLiveLayoutK1(const std::wstring& folder, int width, int height)
{
    const std::wstring game = GameFolder();
    if (game.empty()) return false;
    const std::string key = Narrow(game + L"\\chitin.key");
    if (key.empty()) return false;
    int written = 0, theirs = 0;
    for (int i = 0; i < KmrpLiveLayoutCount(); ++i) {
        const std::wstring name = Wide(KmrpLiveLayoutName(i));
        const bool mod = OverrideHas(name);
        const std::wstring target = folder + L"\\" + name, work = target + L".tmp" + Pid();
        const std::string out = Narrow(work), source = mod ? Narrow(game + L"\\override\\" + name) : std::string();
        if (out.empty() || (mod && source.empty())) continue;
        const int result = KmrpLiveLayout(key.c_str(), KmrpLiveLayoutName(i), mod ? source.c_str() : nullptr,
                                          width, height, out.c_str());
        if (result != 0) {
            DeleteFileW(work.c_str());
            char line[200];
            if (result == 3) sprintf_s(line, "[KMRP] live layout: the Override folder's %s is not laid out for the "
                                             "game's size; it is left to the game", KmrpLiveLayoutName(i));
            else sprintf_s(line, "[KMRP] live layout: %s could not be laid out (%d); the set's is used",
                           KmrpLiveLayoutName(i), result);
            KmrpRuntimeLog(line);
            continue;
        }
        SetFileAttributesW(target.c_str(), FILE_ATTRIBUTE_NORMAL);
        if (!MoveFileExW(work.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING)) {
            DeleteFileW(work.c_str());
            continue;
        }
        ++written;
        if (mod) ++theirs;
    }
    if (theirs || KmrpDebugLogs()) {
        char line[200];
        sprintf_s(line, "[KMRP] live layout: %d screens laid out for %dx%d, %d of them from the Override folder's files",
                  written, width, height, theirs);
        KmrpRuntimeLog(line);
    }
    return written > 0;
}

// A file of the bundled HD item icons (JackInTheBox's KOTOR 1 HD Icon Pack): among
// the common files those are the .tpc files named ia_*, ii_* and iw_*, the game's
// own names for armour, item and weapon icons, 351 of them and nothing else
// (testing/regression/Test-NativeAssetsBank.py holds the bank to that).
bool HdIcon(const std::string& name)
{
    if (name.size() < 8 || _stricmp(name.c_str() + name.size() - 4, ".tpc") != 0) return false;
    const char kind = static_cast<char>(name[1] | 0x20);
    return (name[0] | 0x20) == 'i' && (kind == 'a' || kind == 'i' || kind == 'w') && name[2] == '_';
}

// The common files, unpacked once a build: all but the three font styles' sources,
// which only CachedFont reads, from the pack. Called under the build lock.
bool BuildStore()
{
    return Build(store, "store\n", [](const std::wstring& work) {
        std::vector<unsigned char> data;
        const Group* common = CommonGroup();
        if (!common) return false;
        for (const auto& entry : common->entries) {
            if (!entry.name.compare(0, 4, "kmrf")) continue;
            if (!Decode(entry.key, data) || !WriteNew(work + L"\\" + Wide(entry.name), data)) return false;
        }
        return true;
    });
}

// This run's common files: links to the store but for what the player's Override has,
// and the bundled HD item icons only while their option (hd-icons, on by default) is
// on: left out, the game draws its own icons of the same names. Once a run.
bool LinkArtwork()
{
    RemoveFlat(cache);
    if (!CreateDirectoryW(cache.c_str(), nullptr)) return false;
    const bool hdIcons = KmrpPatchOption(L"hd-icons", 1) != 0;
    const Group* common = CommonGroup();
    if (!common) return false;
    unsigned yielded = 0;
    for (const auto& entry : common->entries) {
        if (!entry.name.compare(0, 4, "kmrf") || (!hdIcons && HdIcon(entry.name))) continue;
        const std::wstring name = Wide(entry.name);
        if (OverrideHas(name)) { ++yielded; continue; }
        if (!Link(store + L"\\" + name, cache + L"\\" + name)) return false;
    }
    if (yielded) {
        char line[160];
        sprintf_s(line, "[KMRP] %u of KMRP's common files left out: the Override folder has its own", yielded);
        KmrpRuntimeLog(line);
    }
    return true;
}

// The set for a size: the listed size's own, or the nearest by height, then by shape
// (the installer's rule).
const Group* SetFor(int width, int height, bool& exact)
{
    const Group* selected = nullptr;
    for (const auto& group : groups) {
        if (!group.width) continue;
        if (!selected || std::abs(static_cast<int>(group.height) - height) < std::abs(static_cast<int>(selected->height) - height) ||
            (std::abs(static_cast<int>(group.height) - height) == std::abs(static_cast<int>(selected->height) - height) &&
             std::abs(double(group.width) / group.height - double(width) / height) <
             std::abs(double(selected->width) / selected->height - double(width) / height))) selected = &group;
    }
    exact = selected && static_cast<int>(selected->width) == width && static_cast<int>(selected->height) == height;
    return selected;
}

std::wstring GameFolder()
{
    wchar_t game[MAX_PATH];
    return KmrpGameFolder(game) ? std::wstring(game) : std::wstring();
}

// A file's size and time, for a stamp: what is made from the player's game belongs to
// the files it was made from.
std::string FileStamp(const std::wstring& path)
{
    WIN32_FILE_ATTRIBUTE_DATA info{};
    if (!GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &info)) return "none";
    char text[64];
    sprintf_s(text, "%lu.%lu.%lu.%lu", info.nFileSizeHigh, info.nFileSizeLow,
              info.ftLastWriteTime.dwHighDateTime, info.ftLastWriteTime.dwLowDateTime);
    return text;
}

// A size's set in the cache, made the first time the size is used (or ahead, Prebuild):
// the files the bank holds; for a size the bank has no set for, or whose set it leaves
// files of to the helper, the blend helper's, given the reference metrics
// (ReferenceTxi); for a listed size the bank's files again where the helper's differ,
// every file held against the index; and what KMRP makes from the player's own game for
// the height (the tutorial popup's icons and tutorial.2da, the hex row frames, the feat,
// power and skill icons at this height's row size, the swoop race's HUD model), which
// no release may carry. Not fatal: a game without its texture pack keeps the game's own
// icons. Called under the build lock.
bool BuildSet(int width, int height, std::wstring& directory)
{
    bool exact = false;
    const Group* selected = SetFor(width, height, exact);
    if (!selected) return false;
    const std::wstring game = GameFolder();
    if (game.empty()) return false;
    const std::wstring packPath = game + L"\\TexturePacks\\swpc_tex_gui.erf", keyPath = game + L"\\chitin.key";
    // "art 2": sets made before 2026-10-23 by the installer's prebuild have no tutorial
    // icons, tutorial.2da or row frames (kmrp-gameart read the key's BIF from the current
    // folder), so they are made again.
    const std::string stamp = std::to_string(width) + "x" + std::to_string(height) + " pack " + FileStamp(packPath) +
                              " key " + FileStamp(keyPath) + " art 2\n";
    directory = root + L"\\sets\\" + std::to_wstring(width) + L"x" + std::to_wstring(height);
    return Build(directory, stamp, [&](const std::wstring& work) {
        // Where the time goes, for the debug log: the pack's files, the blend helper, the
        // check against the index, the icons, the game's art, the swoop HUD.
        ULONGLONG mark = GetTickCount64(), part[6]{};
        auto lap = [&](int which) { const ULONGLONG now = GetTickCount64(); part[which] += now - mark; mark = now; };
        std::vector<unsigned char> output;
        const std::string directoryA = Narrow(work);
        if (directoryA.empty()) return false;
        unsigned left = 0;
        for (const auto& entry : selected->entries) if (!objects.count(entry.key)) ++left;
        // The pack's files, written as Decode checked them. For a listed size they go in
        // after the blend helper has run, over what it wrote, but for the one it reads
        // (kmrp_prompts.txt; the build's HELPER_INPUTS, with the font metrics below): they
        // are the files it makes differently from the build or does not make, so only the
        // files left to it need holding against the index. For any other size the nearest
        // set's files go in first and the helper writes the size's own over them. Until
        // 2026-10-19 every file was written first, read back, and read again after the
        // helper, which cost 3 to 10 s a size once the installer made every size.
        auto stored = [&](bool helperInputs) {
            for (const auto& entry : selected->entries) {
                if (!objects.count(entry.key) || (helperInputs && entry.name != "kmrp_prompts.txt")) continue;
                if (!Decode(entry.key, output) || !WriteNew(work + L"\\" + Wide(entry.name), output)) return false;
            }
            return true;
        };
        const bool helper = !exact || left;
        if (!stored(exact && helper)) return false;
        lap(0);
        if (helper) {
            std::string table;
            if (!TablePath(table) || !ReferenceTxi(height, output) ||
                !WriteNew(work + L"\\dialogfont16x16.txi", output)) return false;
            if (KmrpGuiBlend(table.c_str(), width, height, directoryA.c_str(), directoryA.c_str())) return false;
            // The fonts are the fonts folder's.
            DeleteFileW((work + L"\\dialogfont16x16.txi").c_str());
            lap(1);
            if (exact) {
                if (!stored(false)) return false;
                lap(0);
                unsigned differing = 0;
                for (const auto& entry : selected->entries) {
                    if (objects.count(entry.key)) continue;
                    Key measured;
                    if (!Read(work + L"\\" + Wide(entry.name), output) ||
                        !Sha(output.data(), static_cast<unsigned>(output.size()), measured) || measured != entry.key)
                        ++differing;
                }
                if (differing) {
                    char line[200];
                    sprintf_s(line, "[KMRP] warning: %u of the %u interface files the helper makes for %dx%d were made "
                              "differently than the build made them", differing, left, width, height);
                    KmrpRuntimeLog(line);
                }
            }
        }
        lap(2);
        // The icons the bank already supplies are not the helpers' to make. Beside the
        // folder, not in it: the game must not see it as a resource.
        const std::string game8 = Narrow(game);
        if (game8.empty()) return true;
        const std::string pack = game8 + "\\TexturePacks\\swpc_tex_gui.erf", key = game8 + "\\chitin.key";
        const std::string reserved = directoryA + ".reserved.txt";
        FILE* list = nullptr;
        if (!fopen_s(&list, reserved.c_str(), "w") && list) {
            for (const auto& group : groups) {
                if (&group != selected && group.width != 0) continue;
                for (const auto& entry : group.entries) fprintf(list, "%s\n", entry.name.c_str());
            }
            fclose(list);
        }
        KmrpAbilityIcons(pack.c_str(), static_cast<unsigned>(height), directoryA.c_str(), reserved.c_str());
        DeleteFileA(reserved.c_str());
        lap(3);
        // All or nothing: without its files the tutorial popup tiles the game's small icon,
        // so a failure is always written (it was silent until 2026-10-23).
        if (KmrpGameArt(pack.c_str(), key.c_str(), static_cast<unsigned>(height), directoryA.c_str()) != 0) {
            char line[200];
            sprintf_s(line, "[KMRP] warning: the tutorial popup's icons, tutorial.2da and the row frames for %dx%d "
                      "could not be made from the game's files", width, height);
            KmrpRuntimeLog(line);
        }
        lap(4);
        const int swoop = KmrpSwoopHud(key.c_str(), directoryA.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height));
        lap(5);
        // What was made is a progress note, for the debug log only (KmrpOptions.h): since
        // the installer makes every size (2026-10-19) these lines would otherwise leave a
        // kmrp-kpm.log in every game folder it installs to. A failure is always written.
        if (swoop != 0 && swoop != 1 && swoop != 3) KmrpRuntimeLog("[KMRP] swoop HUD model: could not be written");
        else if (KmrpDebugLogs())
            KmrpRuntimeLog(swoop == 0 ? "[KMRP] swoop HUD model: the parked speed segment moved out of this screen's view"
                         : swoop == 1 ? "[KMRP] swoop HUD model: not the game's own, left as it is"
                                      : "[KMRP] swoop HUD model: the game's own is right for this screen");
        char line[300];
        const int length = sprintf_s(line, "[KMRP] set %dx%d made: %s", width, height,
                  exact ? (left ? "the pack's, with the helper's" : "the pack's") : "blended from the nearest set");
        if (KmrpDebugLogs() && length > 0) {
            sprintf_s(line + length, sizeof line - length, " (ms: pack %llu, helper %llu, check %llu, icons %llu, "
                      "game art %llu, swoop %llu)", part[0], part[1], part[2], part[3], part[4], part[5]);
            KmrpRuntimeLog(line);
        }
        return true;
    });
}

// This run's folder for a set: links to its files but for what the player's Override
// has. One folder a registration: a folder already given to the game keeps its place in
// the game's search, so a size returned to is given again under a new name.
bool LinkSet(const std::wstring& set, std::wstring& view)
{
    view = root + L"\\set-" + Pid() + L"-" + std::to_wstring(++generation);
    RemoveFlat(view);
    if (!CreateDirectoryW(view.c_str(), nullptr)) return false;
    unsigned yielded = 0;
    for (const auto& name : Names(set)) {
        if (OverrideHas(name)) { ++yielded; continue; }
        if (!Link(set + L"\\" + name, view + L"\\" + name)) return false;
    }
    if (yielded) {
        char line[160];
        sprintf_s(line, "[KMRP] %u of KMRP's interface files left out: the Override folder has its own", yielded);
        KmrpRuntimeLog(line);
    }
    return true;
}
}

const std::wstring& KmrpRuntimeAssetDirectory() { return cache; }

bool KmrpRuntimeApplyTextPreferencesK1()
{
    return ApplyTextPreferences(true);
}

bool KmrpRuntimeIsFontK1(const char* name)
{
    if (!name) return false;
    for (const char* font : fontNames) if (!_stricmp(name, font)) return true;
    return false;
}

// CAurTexture::LoadTXI's common return, before the texture reaches any font
// layout consumer. EDI is still the texture here (0x00422CC1). Both loose TXI
// and embedded TPC metadata have finished parsing, including resolution reloads.
//
// Scaling in a later GUI frame left the first line measured at the original
// size and drawn at the new size. Apply the same five dimensional fields here,
// before any caller can measure; glyph coordinates and the source files stay.
extern "C" void __cdecl KmrpFontMetricsLoadedK1(void* object)
{
    if (!object || overrideFontHeights.empty()) return;
    char* const texture = static_cast<char*>(object);
    float* const info = *reinterpret_cast<float**>(texture + 0x38);
    if (!info) return; // missing TXI and non-font textures have no font info
    char name[17] = {};
    std::memcpy(name, texture + 0x98, 16);
    CharLowerBuffA(name, static_cast<DWORD>(std::strlen(name)));
    const auto found = overrideFontHeights.find(name);
    if (found == overrideFontHeights.end()) return;
    const float own = info[1];
    if (!(own > 0.001f) || !(own < 100.0f)) return;
    const float target = found->second * (static_cast<float>(KmrpTextSizeForFontK1(name)) / KmrpTextOptions::Default);
    const float factor = target / own;
    if (!(factor > 0.01f) || !(factor < 128.0f) || own == target) return;
    for (int field = 1; field <= 5; ++field) info[field] *= factor;
    info[1] = target; // exact target makes repeat notifications idempotent
    char line[160];
    sprintf_s(line, "[KMRP] Override's font %s metrics scaled %.2f times before layout", name, factor);
    KmrpRuntimeLog(line);
}

extern "C" void __cdecl KmrpPrepareResourcesK1(void* manager)
{
    static bool busy = false;
    if (busy || registered || !manager || manager != *reinterpret_cast<void**>(0x7A39E8)) return;
    busy = true;
    wchar_t ini[MAX_PATH];
    DWORD size = GetModuleFileNameW(nullptr, ini, MAX_PATH);
    wchar_t* slash = size && size < MAX_PATH ? wcsrchr(ini, L'\\') : nullptr;
    if (slash && !wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - ini), L"swkotor.ini")) {
        int width = GetPrivateProfileIntW(L"Graphics Options", L"Width", 800, ini);
        int height = GetPrivateProfileIntW(L"Graphics Options", L"Height", 600, ini);
        KmrpRuntimeAssetsDimensions(width, height);
    }
    busy = false;
}

// The installer's rule (GuiBlend.Covers), asked of the same table by the same
// helper. Asked once per size: the game's resolution list asks for every mode the
// driver offers.
bool KmrpRuntimeAssetsCovers(int width, int height)
{
    static std::map<std::pair<int, int>, bool> known;
    if (width < 640 || height < 480 || width > 32767 || height > 32767) return false;
    if (!Initialize()) return false;
    Locked lock;
    const auto size = std::make_pair(width, height);
    const auto found = known.find(size);
    if (found != known.end()) return found->second;
    bool covered = false;
    for (const auto& group : groups)
        if (static_cast<int>(group.width) == width && static_cast<int>(group.height) == height) covered = true;
    std::string table;
    if (!covered && TablePath(table))
        covered = KmrpGuiBlendCovers(table.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height)) != 0;
    known[size] = covered;
    return covered;
}

namespace {
// Every size the display offers (the game's display, the main one) that KMRP covers,
// largest first: the sizes the game's resolution list offers.
std::vector<std::pair<int, int>> DisplaySizes()
{
    std::set<std::pair<DWORD, DWORD>> modes;
    DEVMODEA mode{};
    mode.dmSize = sizeof mode;
    for (DWORD index = 0; EnumDisplaySettingsA(nullptr, index, &mode); ++index)
        if (mode.dmBitsPerPel == 32) modes.insert({mode.dmPelsWidth, mode.dmPelsHeight});
    std::vector<std::pair<int, int>> sizes;
    for (const auto& size : modes) {
        const int width = static_cast<int>(size.first), height = static_cast<int>(size.second);
        if (KmrpRuntimeAssetsCovers(width, height)) sizes.push_back({width, height});
    }
    std::sort(sizes.begin(), sizes.end(), [](const std::pair<int, int>& a, const std::pair<int, int>& b) {
        return static_cast<long long>(a.first) * a.second > static_cast<long long>(b.first) * b.second;
    });
    return sizes;
}

// Every size the display offers that KMRP covers, made ahead in the background, sets
// and fonts, after the first size is in place: the installer has made them already
// (KmrpRuntimeAssetsPrepare), so this finds them made, unless the display or the cache
// has changed since (the maintainer, 2026-10-19: "let's actually create all the
// supported resolutions"; until then the five largest). A size made already costs a look
// at its marker. One size at a time under the build lock, so a change of size in the
// game waits for one at most.
DWORD WINAPI Prebuild(void*)
{
    SetThreadPriority(GetCurrentThread(), THREAD_MODE_BACKGROUND_BEGIN);
    const ULONGLONG started = GetTickCount64();
    std::string sizes;
    for (const auto& size : DisplaySizes()) {
        std::wstring set;
        {
            Locked lock;
            if (!BuildSet(size.first, size.second, set)) continue;
        }
        PrefitFonts(size.second);
        sizes += (sizes.empty() ? "" : ", ") + std::to_string(size.first) + "x" + std::to_string(size.second);
    }
    ForgetUnpacked();
    if (KmrpDebugLogs()) {
        char line[1200];
        sprintf_s(line, "[KMRP] sizes ready ahead: %.1000s (%llu ms)", sizes.empty() ? "none" : sizes.c_str(),
                  GetTickCount64() - started);
        KmrpRuntimeLog(line);
    }
    return 0;
}
}

int KmrpRuntimeAssetsPrepare(int share, int shares, KmrpPrepareStep step, void* context)
{
    if (shares < 1 || share < 0 || share >= shares || !Initialize()) return -1;
    // This worker's share: the common files for the first, and every shares-th size from
    // its own. The helpers keep their state in globals, so the installer runs a worker a
    // process (ArtPreparation, KpmEdition.cs).
    std::vector<std::pair<int, int>> sizes;
    const std::vector<std::pair<int, int>> all = DisplaySizes();
    for (std::size_t i = share; i < all.size(); i += shares) sizes.push_back(all[i]);
    const int total = (share == 0 ? 1 : 0) + static_cast<int>(sizes.size());
    int done = 0;
    if (share == 0) {
        if (step && step(0, total, 0, 0, context)) { ClosePack(); return -1; }
        Locked lock;
        if (!BuildStore()) { ClosePack(); return -1; }
        done = 1;
    }
    int made = 0;
    for (const auto& size : sizes) {
        if (step && step(done, total, size.first, size.second, context)) break;
        std::wstring set;
        bool built;
        {
            Locked lock;
            built = BuildSet(size.first, size.second, set);
        }
        if (built) {
            const ULONGLONG fonts = GetTickCount64();
            PrefitFonts(size.second);
            if (KmrpDebugLogs()) {
                char line[120];
                sprintf_s(line, "[KMRP] fonts for %d lines ready in %llu ms", size.second, GetTickCount64() - fonts);
                KmrpRuntimeLog(line);
            }
            ++made;
        }
        ++done;
    }
    ClosePack();
    if (step) step(total, total, 0, 0, context);
    return made;
}

bool KmrpRuntimeAssetsDimensions(int width, int height)
{
    if (width == currentWidth && height == currentHeight) return true;
    if (!Initialize() || !KmrpRuntimeAssetsCovers(width, height)) return false;
    // Where a size's time goes, for the debug log: milliseconds per part, in the order
    // they run.
    LARGE_INTEGER frequency{}, mark{};
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&mark);
    double part[6]{};
    auto lap = [&](int which) {
        LARGE_INTEGER now{};
        QueryPerformanceCounter(&now);
        part[which] += 1000.0 * static_cast<double>(now.QuadPart - mark.QuadPart) / static_cast<double>(frequency.QuadPart);
        mark = now;
    };
    // 1. The common files and the size's set in the cache, each made once.
    std::wstring set;
    {
        Locked lock;
        if (!BuildStore()) { KmrpRuntimeLog("[KMRP] the common files could not be written to the cache"); return false; }
        lap(0);
        if (!BuildSet(width, height, set)) {
            char line[160];
            sprintf_s(line, "[KMRP] the interface files for %dx%d could not be made", width, height);
            KmrpRuntimeLog(line);
            return false;
        }
        lap(1);
    }
    // 2. The fonts at the sizes in use for this height.
    fontHeight = height;
    overrideFontHeights.clear();
    if (!ApplyTextPreferences(false)) return false;
    lap(2);
    // 3. What the game is shown: the cache's own folders when the player's Override has
    // none of their files, the usual case; else this run's folders of links, without
    // Override's files (LinkArtwork, LinkSet), which cost about a second for the common
    // files and half a second for a set on the maintainer's PC (2026-10-19). The common
    // files once a run (the store itself only with the HD icons, which it holds, wanted);
    // the set each time, with the party roster adapted in a folder of its own, searched
    // before the set, when the set is shown as it is.
    if (!registered) {
        bool own = KmrpPatchOption(L"hd-icons", 1) != 0;
        if (const Group* common = CommonGroup())
            for (const auto& entry : common->entries)
                if (own && entry.name.compare(0, 4, "kmrf") && OverrideHas(Wide(entry.name))) own = false;
        if (own) cache = store;
        else if (!LinkArtwork()) return false;
    }
    bool theirs = false;
    for (const auto& name : Names(set)) if (OverrideHas(name)) { theirs = true; break; }
    std::wstring view = set, roster;
    // The galaxy map (AdaptGalaxyMapK1), the main menu (AdaptMainMenuK1) and the screens Live
    // Adaptive Layout lays out (AdaptLiveLayoutK1) are adapted the same way, beside the roster.
    if (theirs) {
        if (!LinkSet(set, view)) return false;
        AdaptPartyRosterK1(set, view);
        AdaptGalaxyMapK1(set, view);
        AdaptMainMenuK1(set, view);
        AdaptLiveLayoutK1(view, width, height);
    } else {
        ++generation;
        roster = root + L"\\roster-" + Pid() + L"-" + std::to_wstring(generation);
        RemoveFlat(roster);
        bool adapted = CreateDirectoryW(roster.c_str(), nullptr) != 0;
        if (adapted) {
            const bool party = AdaptPartyRosterK1(set, roster);
            const bool galaxy = AdaptGalaxyMapK1(set, roster);
            const bool menu = AdaptMainMenuK1(set, roster);
            const bool live = AdaptLiveLayoutK1(roster, width, height);
            adapted = party || galaxy || menu || live;
        }
        if (!adapted) {
            RemoveFlat(roster);
            roster.clear();
        }
    }
    lap(3);
    // 4. Given to the game: the common files and the fonts once, the set each time, so
    // the newest set is searched first (and its roster before it), then the fonts, then
    // the common files. A set returned to is given again under a new name: a folder
    // already given keeps its place in the game's search.
    if (!registered) {
        if (!RegisterFolder(cache, "kmrpart", false) || !RegisterFolder(fontsView, "kmrpfont", false)) return false;
        registered = true;
    }
    if (!RegisterFolder(view, "kmrpset" + std::to_string(generation), false)) return false;
    if (!roster.empty() && !RegisterFolder(roster, "kmrproster" + std::to_string(generation), false)) return false;
    lap(4);
    ForgetUnpacked();
    setView = view;
    rosterView = roster;
    currentWidth = width; currentHeight = height;
    if (KmrpDebugLogs()) {
        char line[300];
        sprintf_s(line, "[KMRP] timing %dx%d in ms: common files %.0f, the size's set %.0f, fonts %.0f, "
                  "this run's folders %.0f, registering %.0f",
                  width, height, part[0], part[1], part[2], part[3], part[4]);
        KmrpRuntimeLog(line);
    }
    static bool ahead = false;
    if (!ahead) {
        ahead = true;
        if (HANDLE thread = CreateThread(nullptr, 0, Prebuild, nullptr, 0, nullptr)) CloseHandle(thread);
    }
    return true;
}

const std::wstring& KmrpRuntimeLayoutDirectory() { return setView; }

// A layout as the game reads it at the size in use: the adapted party roster from its
// own folder when there is one, else the set's.
std::wstring KmrpRuntimeLayoutFile(const std::wstring& name)
{
    if (!rosterView.empty()) {
        const std::wstring adapted = rosterView + L"\\" + name;
        if (GetFileAttributesW(adapted.c_str()) != INVALID_FILE_ATTRIBUTES) return adapted;
    }
    return setView + L"\\" + name;
}
