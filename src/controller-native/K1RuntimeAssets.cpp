// Embedded resources, materialized into a private process cache and registered
// through the game's resource manager. Never writes the player's Override.
//
// The bank (tools/build_native_assets.py, KNAST002) names every file of every
// resolution's set with its SHA-256, and stores only the objects this module cannot
// make: the build ran the blend helper below for every set and left out each file
// the helper writes exactly as the set has it. So a set is produced in three steps
// (KmrpRuntimeAssetsDimensions): the files the bank holds are written, the helper
// writes the rest, and every file is held against the set's index. Until
// 2026-10-05 the bank stored every file (KNAST001, 243 MB of a 249 MB patch).
#include "K1RuntimeAssets.h"
#include "NativeAssets.generated.h"
#include "KmrpOptions.h"
#include "K1Xpress.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <map>
#include <vector>
#include <string>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <cstdio>

extern "C" int KmrpGuiBlend(const char*, unsigned, unsigned, const char*, const char*);
extern "C" int KmrpGuiBlendCovers(const char*, unsigned, unsigned);
// macos/tools/kmrp-abilityicons.c and kmrp-gameart.c, compiled with KMRP_EMBEDDED.
extern "C" int KmrpAbilityIcons(const char* erf, unsigned height, const char* outdir, const char* reserved);
extern "C" int KmrpGameArt(const char* erf, const char* key, unsigned height, const char* outdir);
void KmrpRuntimeLog(const char* line);       // K1RuntimeEngine.cpp: one line into kmrp-kpm.log

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

bool Sha(const unsigned char* data, unsigned size, Key& result)
{
    // Opened once: a set is some 2,100 files, each hashed three times on its way to
    // the cache, and opening the provider for every one of them was measurable.
    static BCRYPT_ALG_HANDLE algorithm = nullptr;
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
    // The first eight bytes name the compression (tools/build_native_assets.py):
    // XPRESS with Huffman, the one shipped and the one this module decodes itself
    // (K1Xpress.cpp). The builder's --lzms bank, KNASL002, needed Windows' own
    // decoder, which Wine and Proton do not have (issue 30), and is refused.
    if (!data || size < 48 || std::memcmp(data, "KNAST002", 8)) return false;
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
    // The common files are all stored. A set's may be left to the blend helper.
    for (const auto& group : parsed) {
        if (group.width != 0) continue;
        for (const auto& entry : group.entries) if (!bank.count(entry.key)) return false;
    }
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
    output.resize(object.size);
    if (!KmrpXpressDecode(object.bytes, object.compressed, output.data(), output.size())) return false;
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

// `known`: the bytes' SHA-256 where the caller has just established it (Decode holds
// every object against its key), so it is not computed a second time. Hashing is
// most of what a set costs to write: measured 2026-10-05, 6.4 s for 2,038 files with
// each hashed three times (decoded, before writing, read back).
bool Write(const std::string& name, const std::vector<unsigned char>& bytes, const Key* known = nullptr)
{
    std::wstring path = cache + L"\\" + std::wstring(name.begin(), name.end());
    Key key;
    if (known) key = *known;
    else if (!Sha(bytes.data(), static_cast<unsigned>(bytes.size()), key)) return false;
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
// The order of the two directories is left as it is, and a file the player has in
// Override is taken out of this one before the game is shown it: that also covers
// a texture in the other format, which the order alone would not (the game prefers
// a .tpc to a .tga wherever each is). A texture is one thing with its .txi: a .tga
// or .tpc in Override removes KMRP's .tga, .tpc and .txi of that name, so a font
// from Override is read with its own metrics or the game's, never KMRP's.
//
// Override is listed once, as the game lists it once: a file put there while the
// game runs is not seen by either. What is taken out is forgotten in `written`, so
// the next size writes it again (the blend helper reads some of these files) and
// this runs again after it. Returns how many files were left to Override.
// The glyph height KMRP's own font of each name has at the size in use, for the
// fonts Override supplies in its place (lower-case names, without extension).
std::map<std::string, float> overrideFontHeights;
bool overrideFontsChanged = false;

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

unsigned YieldToOverride()
{
    static bool listed = false;
    static std::map<std::wstring, bool> names, textures;
    if (!listed) {
        listed = true;
        wchar_t folder[MAX_PATH];
        const DWORD size = GetModuleFileNameW(nullptr, folder, MAX_PATH);
        wchar_t* slash = size && size < MAX_PATH ? wcsrchr(folder, L'\\') : nullptr;
        if (!slash) return 0;
        *slash = 0;
        WIN32_FIND_DATAW found{};
        HANDLE search = FindFirstFileW((std::wstring(folder) + L"\\override\\*").c_str(), &found);
        if (search == INVALID_HANDLE_VALUE) return 0;
        do {
            if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            const std::wstring name = Lower(found.cFileName);
            names[name] = true;
            const std::size_t dot = name.find_last_of(L'.');
            if (dot != std::wstring::npos && (!name.compare(dot, std::wstring::npos, L".tga") ||
                                              !name.compare(dot, std::wstring::npos, L".tpc")))
                textures[name.substr(0, dot)] = true;
        } while (FindNextFileW(search, &found));
        FindClose(search);
    }
    if (names.empty()) return 0;
    unsigned yielded = 0;
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((cache + L"\\*").c_str(), &found);
    if (search == INVALID_HANDLE_VALUE) return 0;
    do {
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        const std::wstring name = Lower(found.cFileName);
        const std::size_t dot = name.find_last_of(L'.');
        const std::wstring extension = dot == std::wstring::npos ? std::wstring() : name.substr(dot);
        // Not resources of the game: the controller library, which is loaded from
        // here, and the blend helper's table.
        if (extension == L".dll" || extension == L".bin") continue;
        const bool texture = extension == L".tga" || extension == L".tpc" || extension == L".txi";
        if (!names.count(name) && !(texture && textures.count(name.substr(0, dot)))) continue;
        const std::wstring path = cache + L"\\" + found.cFileName;
        // A font of Override's: what KMRP's own of that name measures here is kept,
        // for KmrpScaleOverrideFontsK1.
        if (extension == L".txi" && textures.count(name.substr(0, dot))) {
            std::vector<unsigned char> txi;
            const float height = Read(path, txi) ? FontHeightOf(txi) : 0.0f;
            if (height > 0.0f) {
                const std::wstring stem = name.substr(0, dot);
                overrideFontHeights[std::string(stem.begin(), stem.end())] = height;
                overrideFontsChanged = true;
            }
        }
        if (!DeleteFileW(path.c_str())) continue;
        written.erase(path);
        ++yielded;
    } while (FindNextFileW(search, &found));
    FindClose(search);
    return yielded;
}
}

const std::wstring& KmrpRuntimeAssetDirectory() { return cache; }

// A font from Override is drawn at the size KMRP's own font of that name has.
//
// A font is a texture and its metrics, and since 2026-10-11 Override's replaces
// KMRP's whole (YieldToOverride). A translation's fonts are made for the game's
// own interface: the Polish one's dialogfont16x16 is 16 pixels high in a 256-pixel
// texture, where KMRP's at 1440 lines is 32. Its letters were right and half the
// size the layouts are made for (the maintainer's play of that day, 3440x1440:
// "the text is tiny").
//
// The engine draws a glyph (its width in the texture x texturewidth + spacingR) x
// 100 pixels wide and fontheight x 100 high (0x0045A2F0, 0x0045A850), from the
// font information at texture+0x38, which the TXI parser fills (0x00422245 on:
// fontheight +0x04, baselineheight +0x08, texturewidth +0x0C, spacingR +0x10,
// spacingB +0x14; the glyphs' places in the texture, +0x18 and +0x24, are
// fractions and stay). So those five are multiplied by KMRP's height over the
// font's own: the same letters, enlarged, as sharp as the texture is.
//
// A texture's metrics are parsed when it is made and when KMRP reads them again
// after a change of size (ReloadFontMetrics), so this is asked at every GUI frame,
// as each panel starts loading and after that reload, and walks the textures only
// when their number has changed or `again` says the metrics were just read. The
// first text laid out with a font in the moment it is made is measured small.
void KmrpScaleOverrideFontsK1(bool again)
{
    static int walked = -1;
    if (overrideFontHeights.empty()) return;
    void** const textures = *reinterpret_cast<void***>(0x007A4798);
    const int count = *reinterpret_cast<const int*>(0x007A479C);
    if (!textures || count <= 0 || count > 0x100000) return;
    if (!again && !overrideFontsChanged && count == walked) return;
    walked = count;
    overrideFontsChanged = false;
    for (int i = 0; i < count; ++i) {
        char* const texture = static_cast<char*>(textures[i]);
        float* const info = texture ? *reinterpret_cast<float**>(texture + 0x38) : nullptr;
        if (!info) continue;
        char name[20] = {};
        strncpy_s(name, texture + 0x98, 16);
        CharLowerBuffA(name, static_cast<DWORD>(std::strlen(name)));
        const auto found = overrideFontHeights.find(name);
        if (found == overrideFontHeights.end()) continue;
        const float own = info[1];
        if (!(own > 0.001f) || !(own < 100.0f)) continue;
        const float factor = found->second / own;
        if (factor > 0.99f && factor < 1.01f) continue;
        if (!(factor > 0.1f) || !(factor < 16.0f)) continue;
        for (int field = 1; field <= 5; ++field) info[field] *= factor;
        char line[160];
        sprintf_s(line, "[KMRP] Override's font %s drawn %.2f times its size, as KMRP's own is here", name, factor);
        KmrpRuntimeLog(line);
    }
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

// A file of the bundled HD item icons (JackInTheBox's KOTOR 1 HD Icon Pack): among
// the common files those are the .tpc files named ia_*, ii_* and iw_*, the game's
// own names for armour, item and weapon icons, 351 of them and nothing else
// (testing/regression/Test-NativeAssetsBank.py holds the bank to that).
static bool HdIcon(const std::string& name)
{
    if (name.size() < 8 || _stricmp(name.c_str() + name.size() - 4, ".tpc") != 0) return false;
    const char kind = static_cast<char>(name[1] | 0x20);
    return (name[0] | 0x20) == 'i' && (kind == 'a' || kind == 'i' || kind == 'w') && name[2] == '_';
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
    if (!covered && Decode(tableKey, output) && Write("gui-blend.bin", output, &tableKey) &&
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
    const ULONGLONG started = GetTickCount64();
    ULONGLONG helperTime = 0;
    // 1. The files the bank holds: the common ones and this set's.
    const bool exact = static_cast<int>(selected->width) == width && static_cast<int>(selected->height) == height;
    bool derive = !exact;
    const bool hdIcons = KmrpPatchOption(L"hd-icons", 1) != 0;
    std::vector<unsigned char> output;
    for (const auto& group : groups) {
        if (&group != selected && group.width != 0) continue;
        for (const auto& entry : group.entries) {
            // The HD item icons are an option (hd-icons, on by default): left out,
            // the game draws its own icons of the same names.
            if (group.width == 0 && !hdIcons && HdIcon(entry.name)) continue;
            if (!objects.count(entry.key)) { derive = true; continue; }
            if (!Decode(entry.key, output) || !Write(entry.name, output, &entry.key)) return false;
        }
    }
    // 2. The rest, from the blend helper: the layouts, badges, prompt manifest and
    // HUD box of exactly this size. It reads the set's caption widths and font
    // metrics, which step 1 wrote, and writes into the same directory.
    if (derive) {
        if (!Decode(tableKey, output) || !Write("gui-blend.bin", output, &tableKey)) return false;
        char directory[MAX_PATH]; BOOL substituted = FALSE;
        if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, cache.c_str(), -1, directory, MAX_PATH, nullptr, &substituted) || substituted) return false;
        std::string table = std::string(directory) + "\\gui-blend.bin";
        const ULONGLONG helperStarted = GetTickCount64();
        if (KmrpGuiBlend(table.c_str(), width, height, directory, directory)) return false;
        helperTime = GetTickCount64() - helperStarted;
        // Adopt what the helper wrote, over our files and beside them: the next
        // transition's ownership check, and GameArt's sweep of files that are not
        // ours, both go by this list. The helper writes a set's files and nothing
        // else, and every set has the same file names, so the set's names are the
        // ones to read again; the common files are as step 1 left them. (Until
        // 2026-10-05 every file written so far was read and hashed again here,
        // 300 MB of common files included.)
        for (const auto& entry : selected->entries) {
            const std::wstring path = cache + L"\\" + std::wstring(entry.name.begin(), entry.name.end());
            Key measured;
            if (!Read(path, output) || !Sha(output.data(), static_cast<unsigned>(output.size()), measured)) return false;
            written[path] = measured;
        }
        // 3. A listed size is the build's own set, not a blend. Where the helper
        // wrote a file differently the bank holds the set's (that is why it was
        // kept), and it goes back over the helper's; then every file is held
        // against the index. A difference left after that is the helper computing
        // differently on this machine than on the build's: the interface is then
        // the blend's, a pixel off here and there and whole, and the log says so.
        if (exact) {
            unsigned differing = 0;
            for (const auto& entry : selected->entries) {
                const std::wstring path = cache + L"\\" + std::wstring(entry.name.begin(), entry.name.end());
                if (written[path] == entry.key) continue;
                if (objects.count(entry.key) && Decode(entry.key, output) && Write(entry.name, output, &entry.key)) continue;
                ++differing;
            }
            if (differing) {
                char line[160];
                sprintf_s(line, "[KMRP] warning: %u of %u interface files for %dx%d were made differently than the build made them",
                          differing, static_cast<unsigned>(selected->entries.size()), width, height);
                KmrpRuntimeLog(line);
            }
        }
    }
    const ULONGLONG filesTime = GetTickCount64() - started;
    GameArt(*selected, height);
    if (const unsigned yielded = YieldToOverride()) {
        char line[160];
        sprintf_s(line, "[KMRP] %u of KMRP's interface files left out for %dx%d: the Override folder has its own", yielded, width, height);
        KmrpRuntimeLog(line);
    }
    if (KmrpDebugLogs()) {
        char line[160];
        sprintf_s(line, "[KMRP] interface files for %dx%d: %llu ms, of which the blend helper %llu ms; the game's own art %llu ms",
                  width, height, filesTime, helperTime, GetTickCount64() - started - filesTime);
        KmrpRuntimeLog(line);
    }
    if (!RegisterDirectory()) return false;
    currentWidth = width; currentHeight = height;
    return true;
}
