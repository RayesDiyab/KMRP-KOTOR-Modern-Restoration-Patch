/*
  KMRP for macOS: the menu sets and artwork inside the module.

  Until 2026-10-04 KMRP Installer put the menu set for the chosen resolution, KMRP's artwork and
  what it makes from the player's game into the game's override folder, and KMRP-macOS.kpatch applied
  by hand in KotOR Patch Manager had the engine side only. Now the module carries all of it, as
  Windows' does (src/controller-native/K1RuntimeAssets.cpp, whose design this follows): a bank of
  every resolution's set and the artwork (macos/tools/make_kmrp_assets.py), linked into the
  module as the section __KMRP,__assets, unpacked to a cache of KMRP's own and registered with the
  game's resource manager. Nothing is written to the game's override folder.

  The cache: ~/Library/Caches/KMRP/<build>/, <build> being the bank's identity, so a new build
  starts a new cache and the old ones are removed.

      store/             every file of KMRP's artwork and the bundled third-party art
      sets/<W>x<H>/      the set for that size: the bank's, or for a size it has no set for the
                         nearest set (by height, then shape) with the .gui files, badges and
                         prompt manifest kmrp-guiblend blends for it; and what KMRP makes from the
                         player's own game for that height (kmrp-gameart, kmrp-abilityicons)
      art-<pid>/         hard links to store/ for this run of the game: KMRP's artwork and the
                         bundled art, but for what the player's override folder has
      set-<pid>-<n>/     hard links to a set for this run, likewise: the folder the game is given

  The player's override comes first (2026-10-12, as Windows' 1.5.1): see PlayerHas.

  Unlike Windows, which unpacks about 100 MB on every launch into a folder of that launch, the
  store and each set are unpacked once and kept: the Mac's artwork is 348 MB.

  The engine (KOTOR_Exe 1.4.0, C1FCB8D3...6D71; read with Ghidra, see
  docs/macos-standalone-kpatch-handoff.md, section 5a):

      0x10034cca8  CExoString::CExoString(const char*)        Windows 0x5E5A90
      0x10034cdf2  CExoString::~CExoString()                  Windows 0x5E5C20
      0x100677cb8  the CExoBase; its alias list is [+0x18]    Windows [0x7A39E0], +0x0C
      0x10034c9de  CExoAliasList::Add(name, path)             Windows 0x5E6880
      0x1003693bc  CExoResMan::AddResourceDirectory(name)     Windows 0x408800

  A directory is named "ALIAS:": a name without a colon resolves to nothing (0x1003534e2). A new
  key table goes to the head of the manager's list (AddKeyTable, 0x100369130, calls the list's
  0x10034c0b8), so a directory registered after OVERRIDE: is searched before it.

  The hook is where the game registers OVERRIDE: itself (0x10026c739, in the client's start-up
  0x10026c3f0), a relative call the handler makes and then adds KMRP's two directories. Windows
  hooks CExoResMan::GetKeyEntry instead and registers on the first lookup; that function is not
  identified on the Mac, and this place is before any lookup that could find a KMRP file.
*/
#include "assets.h"

#include "../kmrp-layout/options.h"
#include "widescreen.h"

#include <CommonCrypto/CommonDigest.h>
#include <array>
#include <cerrno>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <mach-o/getsect.h>
#include <map>
#include <signal.h>
#include <string>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include <zlib.h>

// macos/tools/kmrp-guiblend.c (KMRP_GUI_EMBEDDED), kmrp-abilityicons.c and kmrp-gameart.c
// (KMRP_EMBEDDED): the installer's helpers, compiled into the module.
extern "C" int KmrpGuiBlend(const char* table, unsigned width, unsigned height, const char* outdir, const char* setdir);
extern "C" int KmrpGuiBlendCovers(const char* table, unsigned width, unsigned height);
extern "C" int KmrpAbilityIcons(const char* erf, unsigned height, const char* outdir, const char* reserved);
extern "C" int KmrpGameArt(const char* erf, const char* key, unsigned height, const char* outdir);

namespace kmrp {
namespace assets {
namespace {

using Key = std::array<unsigned char, 32>;
struct Object { const unsigned char* bytes; unsigned size, stored; };
struct Entry { std::string name; Key key; };
struct Group { unsigned width, height; std::vector<Entry> entries; };

const char kMagic[] = "KMAST002";
const std::size_t kArtGroups = 3;   // the groups before the sets

// One object made on first use, not globals: a global with a constructor is one more load-time
// initialiser of the module, run in an order the hooks and the other parts cannot rely on.
struct State {
    std::map<Key, Object> objects;
    std::vector<Group> groups;   // [0] KMRP's artwork, [1] the bundled art, [2] the HD icon pack, then the sets
    Key table{};
    std::string build, root, store;
    bool loaded = false, registered = false, disabled = false;
    std::string art;                               // this run's artwork folder, once linked
    std::map<std::pair<int, int>, bool> sets;      // the sizes whose set is registered
    std::pair<int, int> newest{0, 0};              // the size registered last, which is searched first
    std::string newestDirectory;
    int generation = 0;
    // The player's override folder, listed once, as the game lists it once: every file's name
    // in lower case, and the names of its textures without their extension.
    bool overrideListed = false;
    std::map<std::string, bool> overrideNames, overrideTextures;
    // The glyph height KMRP's own font of each name has at the size in use, for the fonts the
    // player's override supplies in its place (lower-case names, without extension).
    std::map<std::string, float> overrideFontHeights;
    bool overrideFontsChanged = false;
    std::map<std::pair<int, int>, bool> covered;
};
State& TheState() {
    static State* state = new State;
    return *state;
}
#define g_objects (TheState().objects)
#define g_groups (TheState().groups)
#define g_table (TheState().table)
#define g_build (TheState().build)
#define g_root (TheState().root)
#define g_store (TheState().store)
#define g_loaded (TheState().loaded)
#define g_registered (TheState().registered)

void Log(const char* format, ...) __attribute__((format(printf, 1, 2)));
void Log(const char* format, ...) {
    char line[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof line, format, args);
    va_end(args);
    fprintf(stderr, "[KMRP assets] %s\n", line);
    if (!DebugLogs()) return;
    static FILE* file = [] {
        const char* home = getenv("HOME");
        if (!home) return static_cast<FILE*>(nullptr);
        const std::string dir = std::string(home) + "/Library/Logs/KMRP";
        mkdir((std::string(home) + "/Library/Logs").c_str(), 0755);
        mkdir(dir.c_str(), 0755);
        return fopen((dir + "/assets.log").c_str(), "w");
    }();
    if (file) { fprintf(file, "%s\n", line); fflush(file); }
}

struct Reader {
    const unsigned char* at;
    const unsigned char* end;
    bool bytes(void* out, std::size_t size) {
        if (static_cast<std::size_t>(end - at) < size) return false;
        memcpy(out, at, size);
        at += size;
        return true;
    }
    bool integer(unsigned& value) { return bytes(&value, 4); }
    bool name(std::string& value) {
        unsigned short size;
        if (!bytes(&size, 2) || !size || size > 255 || end - at < size) return false;
        value.assign(reinterpret_cast<const char*>(at), size);
        at += size;
        return value.find('/') == std::string::npos && value.find("..") == std::string::npos;
    }
};

std::string Hex(const unsigned char* bytes, std::size_t count) {
    static const char digits[] = "0123456789abcdef";
    std::string text;
    for (std::size_t i = 0; i < count; i++) { text += digits[bytes[i] >> 4]; text += digits[bytes[i] & 15]; }
    return text;
}

bool IsDirectory(const std::string& path) {
    struct stat info;
    return stat(path.c_str(), &info) == 0 && S_ISDIR(info.st_mode);
}

bool Exists(const std::string& path) {
    struct stat info;
    return lstat(path.c_str(), &info) == 0;
}

bool MakeDirectories(const std::string& path) {
    for (std::size_t at = 1; at <= path.size(); at++) {
        if (at != path.size() && path[at] != '/') continue;
        const std::string part = path.substr(0, at);
        if (mkdir(part.c_str(), 0755) != 0 && errno != EEXIST) return false;
    }
    return IsDirectory(path);
}

std::vector<std::string> Names(const std::string& directory) {
    std::vector<std::string> names;
    DIR* dir = opendir(directory.c_str());
    if (!dir) return names;
    while (dirent* entry = readdir(dir)) {
        if (strcmp(entry->d_name, ".") != 0 && strcmp(entry->d_name, "..") != 0) names.push_back(entry->d_name);
    }
    closedir(dir);
    return names;
}

// A folder this module made: plain files only, one level. Anything else in it is not ours, and
// the folder is then left where it is.
void RemoveFlat(const std::string& directory) {
    for (const std::string& name : Names(directory)) unlink((directory + "/" + name).c_str());
    rmdir(directory.c_str());
}

bool WriteFile(const std::string& path, const unsigned char* data, std::size_t size) {
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    const bool ok = fwrite(data, 1, size, f) == size;
    return fclose(f) == 0 && ok;
}

// The bank, from this module's own image.
bool Load() {
    if (g_loaded) return !g_groups.empty();
    g_loaded = true;
    Dl_info info;
    if (!dladdr(reinterpret_cast<const void*>(&Load), &info) || !info.dli_fbase) return false;
    unsigned long size = 0;
    const unsigned char* data = getsectiondata(static_cast<const mach_header_64*>(info.dli_fbase), "__KMRP", "__assets", &size);
    if (!data || size < 8 + 32 + 8 + 32 || memcmp(data, kMagic, 8) != 0) {
        Log("the module carries no menu sets (it was built without them)");
        return false;
    }
    Reader reader{data + 8, data + size};
    unsigned char build[32];
    unsigned groupCount, objectCount;
    if (!reader.bytes(build, 32) || !reader.integer(groupCount) || groupCount < 4 || groupCount > 4096 ||
        !reader.integer(objectCount) || objectCount > 200000 || !reader.bytes(g_table.data(), 32)) return false;
    std::vector<Group> groups;
    for (unsigned i = 0; i < groupCount; i++) {
        Group group{};
        unsigned count;
        if (!reader.integer(group.width) || !reader.integer(group.height) || !reader.integer(count) || count > 4096) return false;
        for (unsigned j = 0; j < count; j++) {
            Entry entry;
            if (!reader.name(entry.name) || !reader.bytes(entry.key.data(), 32)) return false;
            group.entries.push_back(entry);
        }
        groups.push_back(std::move(group));
    }
    std::map<Key, Object> objects;
    for (unsigned i = 0; i < objectCount; i++) {
        Key key;
        Object object{};
        if (!reader.bytes(key.data(), 32) || !reader.integer(object.size) || !reader.integer(object.stored) ||
            !object.size || object.size > (256u << 20) || static_cast<std::size_t>(reader.end - reader.at) < object.stored ||
            objects.count(key)) return false;
        object.bytes = reader.at;
        reader.at += object.stored;
        objects.emplace(key, object);
    }
    if (reader.at != reader.end || !objects.count(g_table)) return false;
    if (groups[0].width || groups[0].height || groups[1].width || groups[1].height != 1 ||
        groups[2].width || groups[2].height != 2) return false;
    // The artwork is all in the bank. A set's file may be one the module makes itself (BuildSet):
    // its entry then names an object the bank does not hold.
    for (std::size_t i = 0; i < kArtGroups; i++)
        for (const Entry& entry : groups[i].entries)
            if (!objects.count(entry.key)) return false;
    const char* home = getenv("HOME");
    if (!home || !*home) return false;
    g_build = Hex(build, 8);
    g_root = std::string(home) + "/Library/Caches/KMRP/" + g_build;
    g_objects.swap(objects);
    g_groups.swap(groups);
    return true;
}

bool Decode(const Key& key, std::vector<unsigned char>& output) {
    const auto found = g_objects.find(key);
    if (found == g_objects.end()) return false;
    const Object& object = found->second;
    output.resize(object.size);
    uLongf size = object.size;
    if (uncompress(output.data(), &size, object.bytes, object.stored) != Z_OK || size != object.size) return false;
    Key measured;
    CC_SHA256(output.data(), static_cast<CC_LONG>(output.size()), measured.data());
    return measured == key;
}


// The group's files that the bank holds; `left`, when given, counts those it does not (a set's
// files the module makes itself), which without it are an error.
bool Unpack(const Group& group, const std::string& directory, unsigned* left = nullptr) {
    std::vector<unsigned char> data;
    for (const Entry& entry : group.entries) {
        if (left && !g_objects.count(entry.key)) { ++*left; continue; }
        if (!Decode(entry.key, data) || !WriteFile(directory + "/" + entry.name, data.data(), data.size())) {
            Log("could not unpack %s", entry.name.c_str());
            return false;
        }
    }
    return true;
}

// A folder is complete when the marker beside it (never inside: the game lists the folder as
// resources) holds the text it was finished with. Built under another name and renamed, so a
// launch that was cut short leaves nothing that looks finished.
bool Complete(const std::string& directory, const std::string& stamp) {
    FILE* f = fopen((directory + ".complete").c_str(), "r");
    if (!f) return false;
    char text[256] = "";
    const std::size_t n = fread(text, 1, sizeof text - 1, f);
    fclose(f);
    return IsDirectory(directory) && std::string(text, n) == stamp;
}

template <typename Fill>
bool Build(const std::string& directory, const std::string& stamp, Fill fill) {
    if (Complete(directory, stamp)) return true;
    const std::string work = directory + ".tmp" + std::to_string(getpid());
    unlink((directory + ".complete").c_str());
    RemoveFlat(directory);
    RemoveFlat(work);
    if (Exists(directory) || !MakeDirectories(work)) return false;
    if (!fill(work) || rename(work.c_str(), directory.c_str()) != 0) {
        RemoveFlat(work);
        return false;
    }
    return WriteFile(directory + ".complete", reinterpret_cast<const unsigned char*>(stamp.data()), stamp.size());
}

// Caches of other builds, and the link folders of games that are no longer running.
void RemoveStale() {
    const std::string parent = g_root.substr(0, g_root.rfind('/'));
    for (const std::string& name : Names(parent)) {
        if (name == g_build || name.size() != 16 || name.find_first_not_of("0123456789abcdef") != std::string::npos) continue;
        const std::string old = parent + "/" + name;
        for (const std::string& inner : Names(old)) {
            const std::string path = old + "/" + inner;
            if (inner == "sets") {
                for (const std::string& set : Names(path)) {
                    if (IsDirectory(path + "/" + set)) RemoveFlat(path + "/" + set);
                    else unlink((path + "/" + set).c_str());
                }
                rmdir(path.c_str());
            } else if (IsDirectory(path)) {
                RemoveFlat(path);
            } else {
                unlink(path.c_str());
            }
        }
        rmdir(old.c_str());
    }
    for (const std::string& name : Names(g_root)) {
        if (name.find(".tmp") != std::string::npos && !IsDirectory(g_root + "/" + name)) continue;
        if (name.compare(0, 4, "art-") != 0 && name.compare(0, 4, "set-") != 0) continue;
        const int pid = atoi(name.c_str() + 4);
        if (pid > 0 && pid != getpid() && kill(pid, 0) != 0 && errno == ESRCH) RemoveFlat(g_root + "/" + name);
    }
}

// The game's folders, from the executable: <app>/Contents/MacOS/KOTOR_Exe, <app>/Contents/Assets.
std::string AssetsDirectory() {
    char path[4096];
    uint32_t size = sizeof path;
    if (_NSGetExecutablePath(path, &size) != 0) return std::string();
    char resolved[PATH_MAX];
    std::string exe = realpath(path, resolved) ? resolved : path;
    for (int up = 0; up < 2; up++) {
        const std::size_t slash = exe.rfind('/');
        if (slash == std::string::npos) return std::string();
        exe.erase(slash);
    }
    return exe + "/Assets";
}

std::string Lower(std::string text) {
    for (char& c : text) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    return text;
}

// The player's override folder comes before KMRP's files (2026-10-12, as Windows since 1.5.1:
// K1RuntimeAssets.cpp, YieldToOverride). KMRP's folders are registered after OVERRIDE: and so
// searched before it; a file the player has there, a mod's layout, texture or font, was ignored
// wherever KMRP had one of the same name. So what the player has is left out of the folders the
// game is shown: a file of the same name, and for a texture KMRP's .tga, .tpc and .txi of that
// name whichever of the two formats the player's is (the game prefers a .tpc to a .tga wherever
// each is, and a texture is one thing with its .txi). Until then only the bundled third-party
// art yielded, to a texture of either kind (the installer's rule, kmrp-mac.sh, texture_present).
void ListOverride() {
    State& state = TheState();
    if (state.overrideListed) return;
    state.overrideListed = true;
    const std::string assets = AssetsDirectory();
    if (assets.empty()) return;
    for (const std::string& file : Names(assets + "/override")) {
        const std::string name = Lower(file);
        state.overrideNames[name] = true;
        const std::size_t dot = name.rfind('.');
        if (dot != std::string::npos && (name.compare(dot, std::string::npos, ".tga") == 0 ||
                                         name.compare(dot, std::string::npos, ".tpc") == 0))
            state.overrideTextures[name.substr(0, dot)] = true;
    }
}

bool PlayerHas(const std::string& file) {
    ListOverride();
    const State& state = TheState();
    const std::string name = Lower(file);
    if (state.overrideNames.count(name)) return true;
    const std::size_t dot = name.rfind('.');
    if (dot == std::string::npos) return false;
    const std::string kind = name.substr(dot);
    return (kind == ".tga" || kind == ".tpc" || kind == ".txi") && state.overrideTextures.count(name.substr(0, dot)) != 0;
}

// `fontheight` out of a .txi's text, or 0 (FontHeightOf).
float FontHeightOf(const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return 0.0f;
    std::string text;
    char buffer[4096];
    std::size_t n;
    while ((n = fread(buffer, 1, sizeof buffer, f)) > 0 && text.size() < (1u << 20)) text.append(buffer, n);
    fclose(f);
    static const char key[] = "fontheight";
    for (std::size_t at = text.find(key); at != std::string::npos; at = text.find(key, at + 1)) {
        if (at != 0 && text[at - 1] != '\n' && text[at - 1] != '\r') continue;
        const double value = atof(text.c_str() + at + sizeof(key) - 1);
        if (value > 0.0 && value < 100.0) return static_cast<float>(value);
    }
    return 0.0f;
}

// A file of KMRP's the player's override replaces. When it is the metrics of a font whose
// texture the player supplies, what KMRP's own font measures here is kept, for
// ScaleOverrideFonts.
void NoteYielded(const std::string& path, const std::string& file) {
    const std::string name = Lower(file);
    const std::size_t dot = name.rfind('.');
    if (dot == std::string::npos || name.compare(dot, std::string::npos, ".txi") != 0) return;
    State& state = TheState();
    if (!state.overrideTextures.count(name.substr(0, dot))) return;
    const float height = FontHeightOf(path);
    if (height > 0.0f) {
        state.overrideFontHeights[name.substr(0, dot)] = height;
        state.overrideFontsChanged = true;
    }
}

bool Link(const std::string& from, const std::string& to) {
    if (link(from.c_str(), to.c_str()) == 0) return true;
    return symlink(from.c_str(), to.c_str()) == 0;
}

// This run's artwork folder: links, so it costs nothing to make each launch, and the bundled
// art can follow what the player's override folder holds today.
bool LinkArtwork(std::string& directory) {
    // Once a run: the folder is registered with the game after the first time.
    if (!TheState().art.empty()) { directory = TheState().art; return true; }
    directory = g_root + "/art-" + std::to_string(getpid());
    RemoveFlat(directory);
    if (!MakeDirectories(directory)) return false;
    unsigned own = 0, ownYielded = 0;
    for (const Entry& entry : g_groups[0].entries) {
        if (PlayerHas(entry.name)) { NoteYielded(g_store + "/" + entry.name, entry.name); ownYielded++; continue; }
        if (!Link(g_store + "/" + entry.name, directory + "/" + entry.name)) return false;
        own++;
    }
    // The HD icon pack is bundled art like the rest, and the patch's hd-icons option leaves it
    // out (since 2026-10-08): the game then shows its own item icons, or the player's.
    const bool icons = HdIconsOption();
    unsigned yielded = 0, given = 0;
    for (const Group* bundled : {&g_groups[1], &g_groups[2]}) {
        if (bundled == &g_groups[2] && !icons) continue;
        for (const Entry& entry : bundled->entries) {
            if (PlayerHas(entry.name)) { yielded++; continue; }
            if (!Link(g_store + "/" + entry.name, directory + "/" + entry.name)) return false;
            given++;
        }
    }
    Log("artwork: %u files of KMRP's (%u left to files in the game's override), %u bundled (%u left to them), the HD "
        "icon pack %s",
        own, ownYielded, given, yielded, icons ? "among them" : "left out: the option is off");
    TheState().art = directory;
    return true;
}

// The folder the game is shown for a set: links to the set's files but for those the player's
// override has (above). The set itself stays whole in the cache, where the blend helper and the
// next run read it. One folder a registration: a key table already given to the game keeps its
// path.
bool LinkSet(const std::string& set, int generation, std::string& view) {
    view = g_root + "/set-" + std::to_string(getpid()) + "-" + std::to_string(generation);
    RemoveFlat(view);
    if (!MakeDirectories(view)) return false;
    unsigned linked = 0, yielded = 0;
    for (const std::string& name : Names(set)) {
        const std::string path = set + "/" + name;
        if (IsDirectory(path)) continue;
        if (PlayerHas(name)) { NoteYielded(path, name); yielded++; continue; }
        if (!Link(path, view + "/" + name)) return false;
        linked++;
    }
    Log("set %s: %u files, %u left to files in the game's override", view.c_str(), linked, yielded);
    return true;
}

const Group* SetFor(int width, int height, bool& exact) {
    const Group* nearest = nullptr;
    exact = false;
    for (std::size_t i = kArtGroups; i < g_groups.size(); i++) {
        const Group& group = g_groups[i];
        if (static_cast<int>(group.width) == width && static_cast<int>(group.height) == height) { exact = true; return &group; }
        // The nearest set by height, then by shape (Windows' rule and the installer's).
        const int distance = std::abs(static_cast<int>(group.height) - height);
        const double shape = std::fabs(double(group.width) / group.height - double(width) / height);
        if (!nearest) { nearest = &group; continue; }
        const int best = std::abs(static_cast<int>(nearest->height) - height);
        const double bestShape = std::fabs(double(nearest->width) / nearest->height - double(width) / height);
        if (distance < best || (distance == best && shape < bestShape)) nearest = &group;
    }
    return nearest;
}

// gui-blend.bin, beside the cache's folders: kmrp-guiblend reads it from a file.
bool TablePath(std::string& path) {
    path = g_root + "/gui-blend.bin";
    if (Exists(path)) return true;
    std::vector<unsigned char> table;
    if (!MakeDirectories(g_root) || !Decode(g_table, table)) return false;
    const std::string work = path + ".tmp" + std::to_string(getpid());
    return WriteFile(work, table.data(), table.size()) && rename(work.c_str(), path.c_str()) == 0;
}

bool BuildSet(int width, int height, std::string& directory) {
    bool exact;
    const Group* group = SetFor(width, height, exact);
    if (!group) return false;
    const std::string assets = AssetsDirectory();
    const std::string pack = assets + "/TexturePacks/swpc_tex_gui.erf", key = assets + "/chitin.key";
    // What is made from the player's game belongs to the texture pack it was made from.
    struct stat packInfo{};
    stat(pack.c_str(), &packInfo);
    const std::string stamp = std::to_string(width) + "x" + std::to_string(height) + " pack " +
        std::to_string(static_cast<long long>(packInfo.st_size)) + " " + std::to_string(static_cast<long long>(packInfo.st_mtime)) + "\n";
    directory = g_root + "/sets/" + std::to_string(width) + "x" + std::to_string(height);
    if (!MakeDirectories(g_root + "/sets")) return false;
    return Build(directory, stamp, [&](const std::string& work) {
        // Since 2026-10-08 the bank leaves out what the helper writes exactly as the build's set
        // has it (make_kmrp_assets.py --helper, as Windows' bank since 2026-10-05: most layouts
        // and badges of most sizes), which halved the module. So, for a size with a set: the
        // files the bank holds, then the helper's, then the bank's again where the helper wrote
        // one differently than the build did, and every file held against the set's index. For
        // a size without one, as before: the nearest set's files with the helper's for the size
        // over them, which are all the names a set has that the bank does not hold.
        unsigned left = 0;
        if (!Unpack(*group, work, &left)) return false;
        if (!exact || left) {
            std::string table;
            if (!TablePath(table)) return false;
            if (KmrpGuiBlend(table.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height),
                             work.c_str(), work.c_str()) != 0) {
                Log("kmrp-guiblend could not %s %dx%d", exact ? "rebuild" : "blend", width, height);
                return false;
            }
        }
        if (exact && left) {
            unsigned restored = 0;
            std::vector<unsigned char> data, stored;
            for (const Entry& entry : group->entries) {
                const std::string path = work + "/" + entry.name;
                FILE* f = fopen(path.c_str(), "rb");
                if (!f) { Log("set %dx%d: %s was not made", width, height, entry.name.c_str()); return false; }
                data.clear();
                unsigned char buffer[65536];
                std::size_t n;
                while ((n = fread(buffer, 1, sizeof buffer, f)) > 0) data.insert(data.end(), buffer, buffer + n);
                fclose(f);
                Key measured;
                CC_SHA256(data.data(), static_cast<CC_LONG>(data.size()), measured.data());
                if (measured == entry.key) continue;
                // The helper's version of a file the build made otherwise: the bank's goes back.
                if (!g_objects.count(entry.key) || !Decode(entry.key, stored) || !WriteFile(path, stored.data(), stored.size())) {
                    Log("set %dx%d: %s is not the build's file and the bank has none", width, height, entry.name.c_str());
                    return false;
                }
                restored++;
            }
            Log("set %dx%d: %u files made by the module, %u of the bank's put back over its own", width, height, left, restored);
        } else if (!exact) {
            for (const Entry& entry : group->entries)
                if (!Exists(work + "/" + entry.name)) { Log("set %dx%d: %s is missing", width, height, entry.name.c_str()); return false; }
        }
        // The icons the bank already supplies are not the helper's to make. Beside the folder.
        const std::string reserved = work + ".reserved.txt";
        if (FILE* list = fopen(reserved.c_str(), "w")) {
            for (const Group* listed : std::initializer_list<const Group*>{&g_groups[0], &g_groups[1], &g_groups[2], group})
                for (const Entry& entry : listed->entries) fprintf(list, "%s\n", entry.name.c_str());
            fclose(list);
        }
        // Not fatal: a game without its texture pack keeps the game's own icons.
        if (KmrpGameArt(pack.c_str(), key.c_str(), static_cast<unsigned>(height), work.c_str()) != 0)
            Log("the row frames, tutorial icons and tutorial.2da could not be made; the game keeps its own");
        if (KmrpAbilityIcons(pack.c_str(), static_cast<unsigned>(height), work.c_str(), reserved.c_str()) != 0)
            Log("the feat, power and skill icons could not be enlarged; they stay their original size");
        unlink(reserved.c_str());
        Log("set %dx%d: %s", width, height, exact ? "the bank's" : "blended from the nearest set");
        return true;
    });
}

bool BuildStore() {
    g_store = g_root + "/store";
    return Build(g_store, "store\n", [&](const std::string& work) {
        return Unpack(g_groups[0], work) && Unpack(g_groups[1], work) && Unpack(g_groups[2], work);
    });
}

// ---------------------------------------------------------------------------------- the engine
struct ExoString { char* text; int length; int pad; };
const auto MakeString = reinterpret_cast<void (*)(ExoString*, const char*)>(0x10034cca8);
const auto FreeString = reinterpret_cast<void (*)(ExoString*)>(0x10034cdf2);
const auto AliasAdd = reinterpret_cast<void (*)(void*, ExoString*, ExoString*)>(0x10034c9de);
const auto AddDirectory = reinterpret_cast<int (*)(void*, ExoString*)>(0x1003693bc);
void** const kExoBase = reinterpret_cast<void**>(0x100677cb8);

bool AddAliasedDirectory(void* manager, const char* alias, const std::string& path) {
    void* base = *kExoBase;
    void* aliases = base ? *reinterpret_cast<void**>(static_cast<char*>(base) + 0x18) : nullptr;
    if (!aliases) return false;
    ExoString name{}, value{}, directory{};
    MakeString(&name, alias);
    MakeString(&value, (path + "/").c_str());
    AliasAdd(aliases, &name, &value);
    FreeString(&value);
    FreeString(&name);
    MakeString(&directory, (std::string(alias) + ":").c_str());
    const int result = AddDirectory(manager, &directory);
    FreeString(&directory);
    return result != 0;
}

}  // namespace

bool Registered() { return g_registered; }
void Disable() { TheState().disabled = true; }
const std::string& NewestSetDirectory() { return TheState().newestDirectory; }
const std::string& ArtworkDirectory() { return TheState().art; }

std::string OverrideDirectory() {
    const std::string assets = AssetsDirectory();
    return assets.empty() ? assets : assets + "/override";
}

// A font from the player's override is drawn at the size KMRP's own font of that name has
// (2026-10-12, as Windows since 1.5.1: K1RuntimeAssets.cpp, KmrpScaleOverrideFontsK1).
//
// A font is a texture and its metrics, and the player's replaces KMRP's whole. A translation's
// fonts are made for the game's own interface: its dialogfont16x16 is 16 pixels high where
// KMRP's at 1440 lines is 32, so its letters were right and half the size the layouts are made
// for. The engine draws a glyph (its width in the texture x texturewidth + spacingR) x 100 pixels
// wide and fontheight x 100 high, from the font information the TXI parser fills (the object at
// texture+0x48: fontheight +0x04, baselineheight +0x08, texturewidth +0x0C, spacingR +0x10,
// spacingB +0x14; the glyphs' places in the texture are fractions and stay). Those five are
// multiplied by KMRP's height over the font's own: the same letters, enlarged, as sharp as the
// texture is. A font in the override under a name KMRP has no font for is left as it is.
//
// A texture's metrics are parsed when it is made and when KMRP reads them again after a change
// of size (resolution.cpp, ReloadFontMetrics), so this is asked at every GUI frame, as each
// panel starts loading and after that reload, and walks the textures (the array at 0x100635b58,
// 0x100635b60 of them, names at +0xbc) only when their number has changed or `again` says the
// metrics were just read. The first text laid out with a font in the moment it is made is
// measured small, as on Windows.
void ScaleOverrideFonts(bool again) {
    static int walked = -1;
    State& state = TheState();
    if (state.overrideFontHeights.empty()) return;
    void** const textures = *reinterpret_cast<void***>(0x100635b58);
    const int count = *reinterpret_cast<const int*>(0x100635b60);
    if (!textures || count <= 0 || count > 0x100000) return;
    if (!again && !state.overrideFontsChanged && count == walked) return;
    walked = count;
    state.overrideFontsChanged = false;
    for (int i = 0; i < count; i++) {
        char* const texture = static_cast<char*>(textures[i]);
        float* const info = texture ? *reinterpret_cast<float**>(texture + 0x48) : nullptr;
        if (!info) continue;
        const std::string name = Lower(std::string(texture + 0xbc, strnlen(texture + 0xbc, 16)));
        const auto found = state.overrideFontHeights.find(name);
        if (found == state.overrideFontHeights.end()) continue;
        const float own = info[1];
        if (!(own > 0.001f) || !(own < 100.0f)) continue;
        const float factor = found->second / own;
        if (factor > 0.99f && factor < 1.01f) continue;
        if (!(factor > 0.1f) || !(factor < 16.0f)) continue;
        for (int field = 1; field <= 5; field++) info[field] *= factor;
        Log("the override's font %s drawn %.2f times its size, as KMRP's own is here", name.c_str(), factor);
    }
}

bool Covers(int width, int height) {
    if (TheState().disabled) return false;
    if (width < 640 || height < 480 || width > 32767 || height > 32767 || !Load()) return false;
    // Asked more than once a launch, and the helper reads the whole table each time.
    const auto size = std::make_pair(width, height);
    const auto known = TheState().covered.find(size);
    if (known != TheState().covered.end()) return known->second;
    bool exact, covered = false;
    if (SetFor(width, height, exact)) {
        std::string table;
        covered = exact || (TablePath(table) &&
            KmrpGuiBlendCovers(table.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height)) != 0);
    }
    TheState().covered[size] = covered;
    return covered;
}

bool Prepare(int width, int height, std::string* art, std::string* set) {
    if (!Covers(width, height)) {
        if (!g_groups.empty()) Log("no menu set for %dx%d: the game keeps its own files", width, height);
        return false;
    }
    RemoveStale();
    // The set whole in the cache, and of it and the artwork what the game is shown this run:
    // links, without what the player's override has (PlayerHas).
    std::string whole;
    if (!BuildStore() || !BuildSet(width, height, whole) || !LinkArtwork(*art) ||
        !LinkSet(whole, TheState().generation + 1, *set)) {
        Log("the cache in %s could not be written: the game keeps its own files", g_root.c_str());
        return false;
    }
    return true;
}

bool Register(void* manager, int width, int height) {
    if (!manager) return false;
    State& state = TheState();
    const auto size = std::make_pair(width, height);
    if (state.sets.count(size) && state.newest == size) return true;
    std::string art, set;
    if (!Prepare(width, height, &art, &set)) return false;
    // The artwork first, once, and the set after it, so the set, added last, is searched first.
    if (!g_registered) {
        g_registered = AddAliasedDirectory(manager, "KMRPART", art);
        Log("artwork %s: %s", art.c_str(), g_registered ? "registered" : "refused");
        if (!g_registered) return false;
    }
    // A set per size, each under an alias of its own. After a change of resolution in the game
    // the new size's set is registered and so searched before the old one's; a size returned to
    // is registered again under a new alias, since a key table already there stays where it is.
    const std::string alias = "KMRPSET" + std::to_string(++state.generation);
    const bool menus = AddAliasedDirectory(manager, alias.c_str(), set);
    Log("set %s as %s: %s", set.c_str(), alias.c_str(), menus ? "registered" : "refused");
    if (!menus) return false;
    state.sets[size] = true;
    state.newest = size;
    state.newestDirectory = set;
    return true;
}

}  // namespace assets
}  // namespace kmrp


// The client's call to CExoResMan::AddResourceDirectory("OVERRIDE:") (0x10026c739). A relative
// call, so the handler makes it and always consumes. rdi is the manager, rsi the name.
extern "C" __attribute__((visibility("default"))) int KmrpAddOverrideDirectory(void* manager, void* name) {
    reinterpret_cast<int (*)(void*, void*)>(0x1003693bc)(manager, name);
    // The widescreen patch's target size: ForceWidth and ForceHeight when swkotor.ini has them,
    // else the display's size.
    int width = 0, height = 0;
    kmrp::widescreen::Target(&width, &height);
    kmrp::assets::Register(manager, width, height);
    return 1;
}
