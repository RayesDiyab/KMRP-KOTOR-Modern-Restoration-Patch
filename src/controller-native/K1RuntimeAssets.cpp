// Embedded resources, materialized into a private process cache and registered
// through the game's resource manager. Never writes the player's Override.
#include "K1RuntimeAssets.h"
#include "NativeAssets.generated.h"
#include <windows.h>
#include <compressapi.h>
#include <bcrypt.h>
#include <array>
#include <map>
#include <vector>
#include <string>
#include <cstring>
#include <cmath>
#include <cstdio>

extern "C" int KmrpGuiBlend(const char*, unsigned, unsigned, const char*, const char*);
extern "C" int KmrpGuiBlendCovers(const char*, unsigned, unsigned);
// macos/tools/kmrp-abilityicons.c and kmrp-gameart.c, compiled with KMRP_EMBEDDED.
extern "C" int KmrpAbilityIcons(const char* erf, unsigned height, const char* outdir, const char* reserved);
extern "C" int KmrpGameArt(const char* erf, const char* key, unsigned height, const char* outdir);

namespace {
using Key = std::array<unsigned char, 32>;
struct Object { const unsigned char* bytes; unsigned size, compressed; };
struct Entry { std::string name; Key key; };
struct Group { unsigned width, height; std::vector<Entry> entries; };
std::map<Key, Object> objects;
std::vector<Group> groups;
Key tableKey{};
std::wstring cache;
std::map<std::wstring, Key> written;
int currentWidth = 0, currentHeight = 0;
bool registered = false;
std::string directoryAlias;
DECOMPRESSOR_HANDLE decompressor = nullptr;

bool Sha(const unsigned char* data, unsigned size, Key& result)
{
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return false;
    bool ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
        BCryptHashData(hash, const_cast<unsigned char*>(data), size, 0) >= 0 &&
        BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
}

struct Reader {
    const unsigned char* at; const unsigned char* end;
    bool bytes(void* out, unsigned size) {
        if (static_cast<std::size_t>(end - at) < size) return false;
        std::memcpy(out, at, size); at += size; return true;
    }
    bool integer(unsigned& value) { return bytes(&value, 4); }
    bool name(std::string& value) {
        unsigned short size;
        if (!bytes(&size, 2) || !size || size > 255 || end - at < size) return false;
        value.assign(reinterpret_cast<const char*>(at), size); at += size;
        return value.find_first_of("/\\") == std::string::npos && value.find("..") == std::string::npos;
    }
};

const wchar_t kLockSuffix[] = L".lock";

// Remove the caches of games that are no longer running. Each launch makes its
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

bool Initialize()
{
    if (!groups.empty()) return true;
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&Initialize), &module)) return false;
    HRSRC resource = FindResourceW(module, MAKEINTRESOURCEW(101), MAKEINTRESOURCEW(10));
    if (!resource) return false;
    unsigned size = SizeofResource(module, resource);
    auto data = static_cast<const unsigned char*>(LockResource(LoadResource(module, resource)));
    if (!data || size < 48 || std::memcmp(data, "KNAST001", 8)) return false;
    Reader reader{data + 8, data + size};
    unsigned groupCount, objectCount;
    if (!reader.integer(groupCount) || groupCount != 67 || !reader.integer(objectCount) || objectCount > 60000 ||
        !reader.bytes(tableKey.data(), 32)) return false;
    std::vector<Group> parsed;
    for (unsigned i = 0; i < groupCount; ++i) {
        Group group{}; unsigned count;
        if (!reader.integer(group.width) || !reader.integer(group.height) || !reader.integer(count) || count > 2000) return false;
        for (unsigned j = 0; j < count; ++j) {
            Entry entry;
            if (!reader.name(entry.name) || !reader.bytes(entry.key.data(), 32)) return false;
            group.entries.push_back(entry);
        }
        parsed.push_back(std::move(group));
    }
    std::map<Key, Object> bank;
    for (unsigned i = 0; i < objectCount; ++i) {
        Key key; Object object{};
        if (!reader.bytes(key.data(), 32) || !reader.integer(object.size) || !reader.integer(object.compressed) ||
            !object.size || object.size > (256u << 20) || reader.end - reader.at < object.compressed || bank.count(key)) return false;
        object.bytes = reader.at; reader.at += object.compressed; bank.emplace(key, object);
    }
    if (reader.at != reader.end || !bank.count(tableKey)) return false;
    for (const auto& group : parsed) for (const auto& entry : group.entries) if (!bank.count(entry.key)) return false;
    if (!CreateDecompressor(COMPRESS_ALGORITHM_XPRESS_HUFF, nullptr, &decompressor)) return false;
    wchar_t temp[MAX_PATH], reserved[MAX_PATH];
    if (!GetTempPathW(MAX_PATH, temp)) return false;
    RemoveStaleCaches(temp);
    if (!GetTempFileNameW(temp, L"KMR", 0, reserved)) return false;
    // This is exclusively the empty reservation just created by this process.
    if (!DeleteFileW(reserved) || !CreateDirectoryW(reserved, nullptr)) return false;
    cache = reserved;
    // Held for the life of the process and deleted with it, even on a crash: the
    // next launch reads a lock it can delete as "that game is gone".
    CreateFileW((cache + kLockSuffix).c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
    objects.swap(bank); groups.swap(parsed);
    return true;
}

bool Decode(const Key& key, std::vector<unsigned char>& output)
{
    auto found = objects.find(key);
    if (found == objects.end()) return false;
    const auto& object = found->second;
    output.resize(object.size); SIZE_T size = 0;
    if (!Decompress(decompressor, object.bytes, object.compressed, output.data(), output.size(), &size) || size != output.size()) return false;
    Key measured;
    return Sha(output.data(), static_cast<unsigned>(output.size()), measured) && measured == key;
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

bool Write(const std::string& name, const std::vector<unsigned char>& bytes)
{
    std::wstring path = cache + L"\\" + std::wstring(name.begin(), name.end());
    Key key;
    if (!Sha(bytes.data(), static_cast<unsigned>(bytes.size()), key)) return false;
    if (GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES) {
        std::vector<unsigned char> existing; Key measured;
        if (!Read(path, existing) || !Sha(existing.data(), static_cast<unsigned>(existing.size()), measured)) return false;
        auto owner = written.find(path);
        if (owner == written.end() || owner->second != measured) return false;
        if (measured == key) return true;
    }
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr,
        written.count(path) ? TRUNCATE_EXISTING : CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    DWORD size = 0;
    bool ok = WriteFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &size, nullptr) && size == bytes.size();
    CloseHandle(file);
    if (!ok) return false;
    std::vector<unsigned char> actual; Key measured;
    if (!Read(path, actual) || !Sha(actual.data(), static_cast<unsigned>(actual.size()), measured) || measured != key) return false;
    written[path] = key; return true;
}

bool RegisterDirectory()
{
    void* manager = *reinterpret_cast<void**>(0x7A39E8);
    if (!manager) return false;
    char path[MAX_PATH]; BOOL substituted = FALSE;
    if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, path, MAX_PATH, nullptr, &substituted) || substituted) return false;
    // CExoAliasList::ResolveFileName treats the text before ':' as an alias,
    // including drive letters. Register a private alias rather than passing an
    // absolute Windows path to CExoResMan.
    if (directoryAlias.empty()) {
        void* base = *reinterpret_cast<void**>(0x7A39E0);
        if (!base) return false;
        void* aliases = *reinterpret_cast<void**>(static_cast<unsigned char*>(base) + 0x0C);
        if (!aliases) return false;
        std::string alias = "kmrp_" + std::string(path + cache.find_last_of(L"\\") + 1);
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
    int result = reinterpret_cast<int(__thiscall*)(void*, void*)>(registered ? 0x4088E0 : 0x408800)(manager, name);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(name);
    if (result) registered = true;
    return result != 0;
}

// The files KMRP makes from the player's own game, which no release may carry:
// the tutorial popup's icons and tutorial.2da, the hex row frames, and the feat,
// power and skill icons at this height's row size. The installer makes them once,
// for the resolution it installs (GameArtGenerator.cs, AbilityIconGenerator.cs);
// this module has no installer, so it makes them here, for every size, with the
// Mac installer's two helpers. Without them the engine draws the game's 32 and 64
// pixel icons one texel per pixel inside the enlarged boxes, where they tile
// (play-tested 2026-10-04: the tutorial popup showed its icon four and sixteen
// times).
//
// Not fatal: a game without its texture pack keeps the game's own icons.
void GameArt(const Group& selected, int height)
{
    // Whatever the previous size's helpers made. Everything else in this
    // directory is a bank file this process wrote and still owns.
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((cache + L"\\*").c_str(), &found);
    if (search != INVALID_HANDLE_VALUE) {
        do {
            if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            const std::wstring path = cache + L"\\" + found.cFileName;
            if (!written.count(path)) DeleteFileW(path.c_str());
        } while (FindNextFileW(search, &found));
        FindClose(search);
    }
    char directory[MAX_PATH], game[MAX_PATH]; BOOL substituted = FALSE;
    if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, directory, MAX_PATH, nullptr, &substituted) || substituted) return;
    DWORD size = GetModuleFileNameA(nullptr, game, MAX_PATH);
    char* slash = size && size < MAX_PATH ? std::strrchr(game, '\\') : nullptr;
    if (!slash) return;
    *slash = 0;
    const std::string pack = std::string(game) + "\\TexturePacks\\swpc_tex_gui.erf";
    const std::string key = std::string(game) + "\\chitin.key";
    // The icons this size's bank already supplies are not the helper's to make.
    // Beside the directory, not in it: the game must not see it as a resource.
    const std::string reserved = std::string(directory) + ".reserved.txt";
    FILE* list = nullptr;
    if (!fopen_s(&list, reserved.c_str(), "w") && list) {
        for (const auto& group : groups) {
            if (&group != &selected && group.width != 0) continue;
            for (const auto& entry : group.entries) fprintf(list, "%s\n", entry.name.c_str());
        }
        fclose(list);
    }
    KmrpAbilityIcons(pack.c_str(), static_cast<unsigned>(height), directory, reserved.c_str());
    DeleteFileA(reserved.c_str());
    KmrpGameArt(pack.c_str(), key.c_str(), static_cast<unsigned>(height), directory);
}
}

const std::wstring& KmrpRuntimeAssetDirectory() { return cache; }

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
    const auto size = std::make_pair(width, height);
    const auto found = known.find(size);
    if (found != known.end()) return found->second;
    if (!Initialize()) return false;
    bool covered = false;
    for (const auto& group : groups)
        if (static_cast<int>(group.width) == width && static_cast<int>(group.height) == height) covered = true;
    std::vector<unsigned char> output;
    char directory[MAX_PATH]; BOOL substituted = FALSE;
    if (!covered && Decode(tableKey, output) && Write("gui-blend.bin", output) &&
        WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, directory, MAX_PATH, nullptr, &substituted) && !substituted) {
        const std::string table = std::string(directory) + "\\gui-blend.bin";
        covered = KmrpGuiBlendCovers(table.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height)) != 0;
    }
    known[size] = covered;
    return covered;
}

bool KmrpRuntimeAssetsDimensions(int width, int height)
{
    if (width == currentWidth && height == currentHeight) return true;
    if (!Initialize() || !KmrpRuntimeAssetsCovers(width, height)) return false;
    const Group* selected = nullptr;
    for (const auto& group : groups) {
        if (!group.width) continue;
        if (!selected || std::abs(static_cast<int>(group.height) - height) < std::abs(static_cast<int>(selected->height) - height) ||
            (std::abs(static_cast<int>(group.height) - height) == std::abs(static_cast<int>(selected->height) - height) &&
             std::abs(double(group.width) / group.height - double(width) / height) <
             std::abs(double(selected->width) / selected->height - double(width) / height))) selected = &group;
    }
    if (!selected) return false;
    std::vector<unsigned char> output;
    for (const auto& group : groups) {
        if (&group != selected && group.width != 0) continue;
        for (const auto& entry : group.entries) {
            if (!Decode(entry.key, output) || !Write(entry.name, output)) return false;
        }
    }
    if (selected->width != width || selected->height != height) {
        if (!Decode(tableKey, output) || !Write("gui-blend.bin", output)) return false;
        char directory[MAX_PATH]; BOOL substituted = FALSE;
        if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, directory, MAX_PATH, nullptr, &substituted) || substituted) return false;
        std::string table = std::string(directory) + "\\gui-blend.bin";
        if (KmrpGuiBlend(table.c_str(), width, height, directory, directory)) return false;
        // The shared helper wrote only our derived files. Adopt their new hashes
        // before the next transition's ownership check.
        for (auto& owner : written) {
            if (!Read(owner.first, output) || !Sha(output.data(), static_cast<unsigned>(output.size()), owner.second)) return false;
        }
    }
    GameArt(*selected, height);
    if (!RegisterDirectory()) return false;
    currentWidth = width; currentHeight = height;
    return true;
}
