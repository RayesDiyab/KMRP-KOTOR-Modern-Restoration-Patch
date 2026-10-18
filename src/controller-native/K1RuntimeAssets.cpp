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
#include "K1PartyRosterGui.h"
#include "K1PartyRosterState.h"
#include "K1TextOptions.h"
#include "K1TextOptionsPolicy.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <map>
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
// True only after adapting the supplied roster GUI successfully for this size.
bool managedPartyRoster = false;

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
void GameArt(const Group& selected, int width, int height)
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
    // Not a size's file, but made here because this is where the player's own files
    // are read and the cache is cleared of what the helpers made before.
    const int swoop = KmrpSwoopHud(key.c_str(), directory, static_cast<unsigned>(width), static_cast<unsigned>(height));
    KmrpRuntimeLog(swoop == 0 ? "[KMRP] swoop HUD model: the parked speed segment moved out of this screen's view"
                 : swoop == 1 ? "[KMRP] swoop HUD model: not the game's own, left as it is"
                 : swoop == 3 ? "[KMRP] swoop HUD model: the game's own is right for this screen"
                              : "[KMRP] swoop HUD model: could not be written");
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

bool ApplyTextPreferences(bool preserveOverride)
{
    const int style = KmrpTextFontStyleK1();
    const bool fitted = style != KmrpTextOptions::Original;
    const char* prefix = style == KmrpTextOptions::Original ? "kmrfog" :
                         style == KmrpTextOptions::HdOriginal ? "kmrfho" : "kmrfhd";
    const Group* common = nullptr;
    for (const auto& g : groups) if (!g.width) { common = &g; break; }
    if (!common) return false;
    // Original keeps its atlas and has only its TXI's dimensions changed; the HD
    // styles' atlases are resampled to the drawn size (FitAtlas). No glyph is drawn
    // and no font installed in the game process.
    for (unsigned i = 0; i < 18; ++i) {
        if (preserveOverride && OverrideFont(fontNames[i])) continue;
        char source[32];
        for (const char* extension : {".tga", ".txi"}) {
            sprintf_s(source, "%s%02u%s", prefix, i, extension);
            const Entry* entry = FindEntry(*common, source);
            if (!entry || !objects.count(entry->key)) return false;
        }
    }
    std::vector<unsigned char> data, txi, tga;
    for (unsigned i = 0; i < 18; ++i) {
        if (preserveOverride && OverrideFont(fontNames[i])) continue;
        char source[32];
        sprintf_s(source, "kmrfhd%02u.txi", i);
        const Entry* baseline = FindEntry(*common, source);
        if (!baseline || !Decode(baseline->key, data)) return false;
        const float target = FontTargetHeight(FontHeightOf(data) * kSizeReferenceScale / kHdBakeScale, fontHeight);
        if (!(target > 0.0f)) return false;
        overrideFontHeights[fontNames[i]] = target;
        const float sized = target * (static_cast<float>(KmrpTextSizeForFontK1(fontNames[i])) / KmrpTextOptions::Default);
        sprintf_s(source, "%s%02u.txi", prefix, i);
        if (!Decode(FindEntry(*common, source)->key, txi)) return false;
        const float own = FontHeightOf(txi);
        sprintf_s(source, "%s%02u.tga", prefix, i);
        if (!Decode(FindEntry(*common, source)->key, tga)) return false;
        if (!(own > 0.001f) || !FontTxiAtHeight(txi, sized)) return false;
        if (fitted) {
            int newWidth = 0;
            if (!FitAtlas(tga, sized / own, newWidth) || !SetTxiField(txi, "texturewidth", newWidth / 100.0)) return false;
        }
        if (!Write(std::string(fontNames[i]) + ".tga", tga) || !Write(std::string(fontNames[i]) + ".txi", txi)) return false;
    }
    return true;
}

bool AdaptPartyRosterK1()
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
    if (!Read(cache+L"\\partyselection.gui",layout)) return false;
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
    if (!Write("partyselection.gui",adapted)) return false;
    managedPartyRoster = true;
    KmrpRuntimeLog("[KMRP] party roster: runtime layout ready for this resolution; source files unchanged");
    return true;
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
        // The only managed exception: this is a validated, adapted copy of the
        // same supplied roster GUI, not a replacement for an arbitrary mod.
        if (managedPartyRoster && name == L"partyselection.gui") continue;
        const bool texture = extension == L".tga" || extension == L".tpc" || extension == L".txi";
        if (!names.count(name) && !(texture && textures.count(name.substr(0, dot)))) continue;
        const std::wstring path = cache + L"\\" + found.cFileName;
        // A font of Override's: what KMRP's own of that name measures here is kept,
        // for KmrpFontMetricsLoadedK1.
        if (extension == L".txi" && textures.count(name.substr(0, dot))) {
            std::vector<unsigned char> txi;
            const float height = Read(path, txi) ? FontHeightOf(txi) : 0.0f;
            if (height > 0.0f) {
                const std::wstring stem = name.substr(0, dot);
                // The baseline is captured before a selected style replaces the
                // atlas. Never replace it with that style's source metrics.
                overrideFontHeights.emplace(std::string(stem.begin(), stem.end()), height);
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
    // One source atlas per font/style at every resolution. Materialize its TXI
    // dimensions before the blend helper measures captions, then yield to mods.
    fontHeight = height;
    overrideFontHeights.clear();
    if (!ApplyTextPreferences(false)) return false;
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
    GameArt(*selected, width, height);
    AdaptPartyRosterK1();
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
