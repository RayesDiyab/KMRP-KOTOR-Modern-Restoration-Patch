/*
  KMRP for macOS: the menu sets and artwork, from KMRP's art pack.

  Until 2026-10-04 KMRP Installer put the menu set for the chosen resolution, KMRP's artwork and
  what it makes from the player's game into the game's override folder, and KMRP-macOS.kpatch applied
  by hand in KotOR Patch Manager had the engine side only. Now the module carries all of it, as
  Windows' does (src/controller-native/K1RuntimeAssets.cpp, whose design this follows): a bank of
  every resolution's set and the artwork (macos/tools/make_kmrp_assets.py), linked into the
  module as the section __KMRP,__assets, unpacked to a cache of KMRP's own and registered with the
  game's resource manager. Nothing is written to the game's override folder.

  Since 2026-11-03 the art is not inside the module: it is the art pack Windows' has been since
  2026-10-19, kmrp-assets.pack (tools/kmrp_pack.py documents it, macos/tools/make_kmrp_assets.py
  writes it, src/controller-native/K1AssetPack.cpp decodes it), which the installer writes beside
  the module, and the module holds it against the build it was made with. "The bank" below means
  the pack. Without it the module makes nothing and says so: the patch alone is not the whole of
  KMRP (the maintainer's choice for the smaller installer, 2026-10-19).

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

  Since 2026-11-03 the installer makes the store and the set of every size the display offers
  before the game first starts, as Windows' does (handoff item 73): kmrp-prepare
  (macos/tools/kmrp-prepare.cpp) is this file and the helpers in a program of their own, given
  the game's folder and the pack (SetPaths), making one size a process (PrepareStore,
  PrepareSet). The game then finds each finished and makes only this run's links.

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
#include "fonts.h"
#include "widescreen.h"
#include "../../../src/controller-native/K1AssetPack.h"

#include <CommonCrypto/CommonDigest.h>
#include <algorithm>
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
#include <sys/file.h>
#include <mach-o/dyld.h>
#include <mach-o/getsect.h>
#include <list>
#include <map>
#include <signal.h>
#include <string>
#include <strings.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

// macos/tools/kmrp-guiblend.c (KMRP_GUI_EMBEDDED), kmrp-abilityicons.c and kmrp-gameart.c
// (KMRP_EMBEDDED): the installer's helpers, compiled into the module.
extern "C" int KmrpGuiBlend(const char* table, unsigned width, unsigned height, const char* outdir, const char* setdir);
extern "C" int KmrpGuiBlendCovers(const char* table, unsigned width, unsigned height);
extern "C" int KmrpAbilityIcons(const char* erf, unsigned height, const char* outdir, const char* reserved);
extern "C" int KmrpGameArt(const char* erf, const char* key, unsigned height, const char* outdir);
extern "C" int KmrpDeriveImage(const char* source, int canvas, int picture, int left, int bottom, const char* filter,
                               const char* out);
// macos/tools/kmrp-swoophud.c, kmrp-guiadapt.c and kmrp-merge.c (KMRP_EMBEDDED), as Windows' module
// links them (K1RuntimeAssets.cpp); kmrp-embedded.h has what each returns.
extern "C" int KmrpSwoopHud(const char* key, const char* outdir, unsigned width, unsigned height);
extern "C" int KmrpSwoopHudModel(const char* mdl, const char* mdx, const char* outdir, unsigned width, unsigned height);
extern "C" int KmrpGalaxyMap(const char* key, const char* setGui, const char* outGui, const char* sourceGui);
extern "C" int KmrpMainMenuBars(const char* setGui, const char* outGui);
extern "C" int KmrpLiveLayoutSet(const char* key, const char* name, const char* sourceGui, int width, int height,
                                 const char* outGui, const char* set);
extern "C" int KmrpLiveLayoutCount(void);
extern "C" const char* KmrpLiveLayoutName(int index);
extern "C" const char* KmrpLiveLayoutNotes(void);
extern "C" int KmrpHudCues(const char* sourceGui, const char* outGui);
extern "C" const char* KmrpHudFileName(int index);
extern "C" int KmrpReadKeyedResource(const char* key, const char* resref, int type, unsigned char** data, std::size_t* size);
extern "C" int KmrpMerge2da(const char* name, const uint8_t* base, std::size_t baseSize, const uint8_t* ours,
                            std::size_t oursSize, const uint8_t* theirs, std::size_t theirsSize, uint8_t** out,
                            std::size_t* outSize, char** notes, int counts[4]);
extern "C" void KmrpMergeFree(void* pointer);

namespace kmrp {
namespace assets {
namespace {

using Key = KmrpPack::Key;
using Object = KmrpPack::Object;
using Entry = KmrpPack::Entry;
using Group = KmrpPack::Group;

const std::size_t kArtGroups = 4;   // the groups before the sets

// One object made on first use, not globals: a global with a constructor is one more load-time
// initialiser of the module, run in an order the hooks and the other parts cannot rely on.
struct State {
    std::map<Key, Object> objects;
    std::vector<KmrpPack::Block> blocks;
    std::vector<Group> groups;   // [0] KMRP's artwork, [1] the bundled art, [2] the HD icon pack, [3] the fonts' sources, then the sets
    Key table{};
    const unsigned char* pack = nullptr;   // the file, mapped for the run
    // Blocks of several files, kept unpacked while their files are asked for one at a time (a
    // size's set, the common files), newest first (Decode), let go when the work is done.
    std::list<std::pair<std::uint32_t, std::vector<unsigned char>>> unpacked;
    std::size_t unpackedBytes = 0;
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
    std::map<std::pair<int, int>, bool> covered;
    // Given by kmrp-prepare (SetPaths); empty in the game, where they are found.
    std::string givenAssets, givenPack;
    bool outside = false;
};
State& TheState() {
    static State* state = new State;
    return *state;
}
#define g_objects (TheState().objects)
#define g_blocks (TheState().blocks)
#define g_groups (TheState().groups)
#define g_table (TheState().table)
#define g_build (TheState().build)
#define g_root (TheState().root)
#define g_store (TheState().store)
#define g_loaded (TheState().loaded)
#define g_registered (TheState().registered)

// What was made is a note for the debug log; a failure is always written (Warn), as on Windows
// since 2026-10-19 (K1RuntimeAssets.cpp): the installer's windows show nothing of it otherwise.
void Write(const char* line, bool always) {
    fprintf(stderr, "[KMRP assets] %s\n", line);
    // kmrp-prepare's processes run side by side, and the log is the game's.
    if (TheState().outside || (!always && !DebugLogs())) return;
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

void Log(const char* format, ...) __attribute__((format(printf, 1, 2)));
void Log(const char* format, ...) {
    char line[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof line, format, args);
    va_end(args);
    Write(line, false);
}

void Warn(const char* format, ...) __attribute__((format(printf, 1, 2)));
void Warn(const char* format, ...) {
    char line[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof line, format, args);
    va_end(args);
    Write(line, true);
}

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

bool ReadFile(const std::string& path, std::vector<unsigned char>& data) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    data.clear();
    unsigned char buffer[65536];
    std::size_t n;
    while ((n = fread(buffer, 1, sizeof buffer, f)) > 0) data.insert(data.end(), buffer, buffer + n);
    const bool ok = !ferror(f);
    fclose(f);
    return ok;
}

// What a folder holds, its files and their bytes, which the marker records (Windows' Contents).
std::string Contents(const std::string& directory) {
    unsigned long long files = 0, bytes = 0;
    for (const std::string& name : Names(directory)) {
        struct stat info;
        if (lstat((directory + "/" + name).c_str(), &info) != 0 || !S_ISREG(info.st_mode)) continue;
        files++;
        bytes += static_cast<unsigned long long>(info.st_size);
    }
    return std::to_string(files) + " " + std::to_string(bytes) + "\n";
}

// The folder of this module, as the game loads it: patches/ beside KOTOR_Exe, or the App Store
// launcher's copy.
std::string ModuleDirectory() {
    Dl_info info;
    if (!dladdr(reinterpret_cast<const void*>(&ModuleDirectory), &info) || !info.dli_fname) return std::string();
    const std::string path = info.dli_fname;
    const std::size_t slash = path.rfind('/');
    return slash == std::string::npos ? std::string() : path.substr(0, slash);
}

// The art pack beside this module, where the installer writes it. Its index is read now and a
// file's block when the file is needed (Decode). Mapped for the run: an installer may remove or
// replace the file while a game runs, and this run keeps the file it opened. Tried once a run: a
// pack that is missing or another build's stays so.
bool Load() {
    if (g_loaded) return !g_groups.empty();
    g_loaded = true;
    const std::string path = TheState().outside ? TheState().givenPack : ModuleDirectory() + "/kmrp-assets.pack";
    const int file = open(path.c_str(), O_RDONLY);
    if (file < 0) {
        if (TheState().outside) Warn("the art pack cannot be opened: %s", path.c_str());
        else Warn("kmrp-assets.pack is not beside the module (%s), so KMRP's interface cannot be made: install KMRP with its "
                  "installer, which writes it", path.c_str());
        return false;
    }
    struct stat info;
    void* mapped = fstat(file, &info) == 0 && static_cast<std::size_t>(info.st_size) >= KmrpPack::kHeaderSize
        ? mmap(nullptr, static_cast<std::size_t>(info.st_size), PROT_READ, MAP_PRIVATE, file, 0) : MAP_FAILED;
    close(file);
    if (mapped == MAP_FAILED) { Warn("kmrp-assets.pack cannot be read"); return false; }
    const auto* data = static_cast<const unsigned char*>(mapped);
    const std::size_t size = static_cast<std::size_t>(info.st_size);
    Key identity{};
    std::uint32_t start = 0;
    KmrpPack::Index parsed;
    if (!KmrpPack::ReadHeader(data, size, identity, start) || start > size) {
        munmap(mapped, size);
        Warn("kmrp-assets.pack cannot be read");
        return false;
    }
    // The pack this module was built with, and no other: a module put in by hand beside an older
    // pack would name files the pack does not have.
    if (KmrpPack::IdentityText(identity) != KMRP_ASSET_BUILD) {
        munmap(mapped, size);
        Warn("kmrp-assets.pack is from another build of KMRP than this module: install KMRP again");
        return false;
    }
    bool ok = KmrpPack::ReadIndex(data, start, size, parsed) && parsed.groups.size() > kArtGroups;
    if (ok) {
        const std::vector<Group>& groups = parsed.groups;
        ok = !groups[0].width && !groups[0].height && !groups[1].width && groups[1].height == 1 &&
             !groups[2].width && groups[2].height == 2 && !groups[3].width && groups[3].height == 3 &&
             parsed.objects.count(parsed.table) != 0;
        // The artwork is all in the bank. A set's file may be one the module makes itself
        // (BuildSet): its entry then names an object the bank does not hold.
        for (std::size_t i = 0; ok && i < kArtGroups; i++)
            for (const Entry& entry : groups[i].entries)
                if (!parsed.objects.count(entry.key)) ok = false;
    }
    const char* home = getenv("HOME");
    if (!ok || !home || !*home) {
        munmap(mapped, size);
        Warn("kmrp-assets.pack cannot be read");
        return false;
    }
    g_build = Hex(identity.data(), 8);
    g_root = std::string(home) + "/Library/Caches/KMRP/" + g_build;
    g_table = parsed.table;
    TheState().pack = data;
    g_objects.swap(parsed.objects);
    g_blocks.swap(parsed.blocks);
    g_groups.swap(parsed.groups);
    return true;
}

bool UnpackBlock(std::uint32_t number, std::vector<unsigned char>& out) {
    const KmrpPack::Block& block = g_blocks[number];
    out.resize(block.size);
    return KmrpPack::Unpack(block, TheState().pack + block.offset, out.data());
}

const std::size_t kKeepUnpacked = 48u << 20;

bool Decode(const Key& key, std::vector<unsigned char>& output) {
    const auto found = g_objects.find(key);
    if (found == g_objects.end()) return false;
    const Object& object = found->second;
    const KmrpPack::Block& block = g_blocks[object.block];
    State& state = TheState();
    if (object.offset == 0 && object.size == block.size) {
        // A file that is a block of its own is unpacked straight into the caller's buffer.
        if (!UnpackBlock(object.block, output)) return false;
    } else {
        const auto kept = std::find_if(state.unpacked.begin(), state.unpacked.end(),
            [&](const std::pair<std::uint32_t, std::vector<unsigned char>>& held) { return held.first == object.block; });
        if (kept != state.unpacked.end()) {
            state.unpacked.splice(state.unpacked.begin(), state.unpacked, kept);
        } else {
            std::vector<unsigned char> data;
            if (!UnpackBlock(object.block, data)) return false;
            state.unpackedBytes += data.size();
            state.unpacked.emplace_front(object.block, std::move(data));
            while (state.unpackedBytes > kKeepUnpacked && state.unpacked.size() > 1) {
                state.unpackedBytes -= state.unpacked.back().second.size();
                state.unpacked.pop_back();
            }
        }
        const std::vector<unsigned char>& data = state.unpacked.front().second;
        output.assign(data.begin() + object.offset, data.begin() + object.offset + object.size);
    }
    Key measured;
    if (!KmrpPack::Unfilter(object.filter, output.data(), output.size())) return false;
    CC_SHA256(output.data(), static_cast<CC_LONG>(output.size()), measured.data());
    return measured == key;
}

void ForgetUnpacked() {
    TheState().unpacked.clear();
    TheState().unpackedBytes = 0;
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
// resources) holds the text it was finished with and what it held then. Built under another name
// and renamed, so a launch that was cut short leaves nothing that looks finished. The text alone
// until 2026-11-03: a file taken out afterwards was never made again (Windows' 2026-11-01 fix).
bool Complete(const std::string& directory, const std::string& stamp) {
    std::vector<unsigned char> text;
    return IsDirectory(directory) && ReadFile(directory + ".complete", text) &&
           std::string(text.begin(), text.end()) == stamp + Contents(directory);
}

// `seal` false after the fill: the folder is used, but not marked finished.
// The game and the installer's kmrp-prepare (macos/tools/kmrp-prepare.cpp) may make the same folder
// at once: one start of the game while the installer is still making sizes. Each holds a lock beside
// the folder while it checks, fills and renames, and checks again once it has it, so the second waits
// and then finds the folder finished. Without it the second's rename failed and that run of the game
// had no menus of KMRP's, or its check fell between the other's rename and marker and it emptied a
// finished folder (the 2026-11-03 audit). Released when the process ends, whatever the end.
struct FolderLock {
    int fd = -1;
    explicit FolderLock(const std::string& directory) {
        fd = open((directory + ".lock").c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0644);
        if (fd >= 0 && flock(fd, LOCK_EX) != 0) { close(fd); fd = -1; }
    }
    ~FolderLock() { if (fd >= 0) close(fd); }
};

template <typename Fill>
bool Build(const std::string& directory, const std::string& stamp, Fill fill, const bool* seal = nullptr) {
    if (Complete(directory, stamp)) return true;
    const FolderLock lock(directory);
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
    if (seal && !*seal) return true;
    const std::string marker = stamp + Contents(directory);
    return WriteFile(directory + ".complete", reinterpret_cast<const unsigned char*>(marker.data()), marker.size());
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
    // What a process cut short left while it made something: store.tmp<pid>, sets/<W>x<H>.tmp<pid>
    // (about 170 MB each) and its .reserved.txt, gui-blend.bin.tmp<pid>, fonts' work files. Each name
    // carries the pid that made it; it goes once that process is gone.
    for (const std::string& folder : {g_root, g_root + "/sets", g_root + "/fonts"}) {
        for (const std::string& name : Names(folder)) {
            const std::size_t at = name.rfind(".tmp");
            if (at == std::string::npos) continue;
            const int pid = atoi(name.c_str() + at + 4);
            if (pid <= 0 || pid == getpid() || kill(pid, 0) == 0 || errno != ESRCH) continue;
            const std::string path = folder + "/" + name;
            if (IsDirectory(path)) RemoveFlat(path);
            else unlink(path.c_str());
        }
    }
}

// The game's folders, from the executable: <app>/Contents/MacOS/KOTOR_Exe, <app>/Contents/Assets.
std::string AssetsDirectory() {
    if (TheState().outside) return TheState().givenAssets;
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
        if (PlayerHas(entry.name)) { ownYielded++; continue; }
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
        if (PlayerHas(name)) { yielded++; continue; }
        if (!Link(path, view + "/" + name)) return false;
        linked++;
    }
    Log("set %s: %u files, %u left to files in the game's override", view.c_str(), linked, yielded);
    return true;
}

// The notes of the helpers, one a line, as Windows' LogCompatibilityNotes.
void LogNotes(const char* lead, const char* notes) {
    if (!notes) return;
    for (const char* at = notes; *at;) {
        const char* end = strchr(at, '\n');
        const std::size_t length = end ? static_cast<std::size_t>(end - at) : strlen(at);
        if (length) Warn("compatibility: %s%.*s", lead, static_cast<int>(length), at);
        at += length + (end ? 1 : 0);
    }
}

std::string WorkName(const std::string& target) { return target + ".tmp" + std::to_string(getpid()); }

// `view` holds links into the set, so a file is written beside its target and moved over it: the
// link goes, and the set keeps its own file.
bool MoveOver(const std::string& work, const std::string& target) {
    if (rename(work.c_str(), target.c_str()) == 0) return true;
    unlink(work.c_str());
    return false;
}

// Live Adaptive Layout, Windows' AdaptLiveLayoutK1: the screens its table lists, laid out for the
// size from the file the game would load, a mod's in the override folder or else the game's own
// (through chitin.key). A mod's file laid out for another size is left to the game. Unlike
// Windows' the set keeps its copy of each screen, which stands if a file cannot be laid out.
void AdaptLiveLayout(const std::string& set, const std::string& view, const std::string& key,
                     const std::string& overrideFolder, int width, int height) {
    int written = 0, theirs = 0;
    for (int i = 0; i < KmrpLiveLayoutCount(); i++) {
        const char* const name = KmrpLiveLayoutName(i);
        const bool mod = PlayerHas(name);
        const std::string target = view + "/" + name, work = WorkName(target);
        const std::string source = mod ? overrideFolder + "/" + name : std::string();
        const int result = KmrpLiveLayoutSet(key.c_str(), name, mod ? source.c_str() : nullptr, width, height,
                                             work.c_str(), set.c_str());
        if (mod) LogNotes("the override folder's ", KmrpLiveLayoutNotes());
        if (result != 0) {
            unlink(work.c_str());
            if (result == 3) Warn("compatibility: the override folder's %s: Live Adaptive Layout is off for this "
                                  "screen; the mod's file is used as it is", name);
            else Warn("live layout: %s could not be laid out (%d); the set's own is used", name, result);
            continue;
        }
        if (!MoveOver(work, target)) continue;
        written++;
        if (mod) theirs++;
    }
    Log("live layout: %d screens laid out for %dx%d, %d of them from the override folder's files", written, width, height, theirs);
    // A mod's mouse and keyboard HUD file, given the combat cues KMRP's own carry (item 119).
    for (int i = 0; const char* const name = KmrpHudFileName(i); i++) {
        if (!PlayerHas(name)) continue;
        const std::string target = view + "/" + name, work = WorkName(target), source = overrideFolder + "/" + name;
        const int result = KmrpHudCues(source.c_str(), work.c_str());
        if (result != 0) {
            unlink(work.c_str());
            if (result != 3) Warn("HUD cues: the override folder's %s could not be given them (%d)", name, result);
            continue;
        }
        if (MoveOver(work, target)) Log("HUD cues: the override folder's %s given the combat cues", name);
    }
}

// Windows' AdaptGalaxyMapK1 (issue 67), on the file live layout wrote.
void AdaptGalaxyMap(const std::string& view, const std::string& key, const std::string& overrideFolder) {
    const std::string target = view + "/galaxymap.gui", work = WorkName(target);
    if (!Exists(target)) return;
    const bool theirs = PlayerHas("galaxymap.gui");
    const std::string source = overrideFolder + "/galaxymap.gui";
    const int result = KmrpGalaxyMap(key.c_str(), target.c_str(), work.c_str(), theirs ? source.c_str() : nullptr);
    if (result != 0) {
        unlink(work.c_str());
        if (result == 3) Warn("galaxy map: the override folder's galaxymap.gui is not the game's 640x480 layout; it is left to the game");
        else Warn("galaxy map: could not be placed (%d); the map is left as live layout made it", result);
        return;
    }
    MoveOver(work, target);
}

// Windows' AdaptMainMenuK1: the main menu's buttons on the bars of their art. A layout the
// player's override has keeps its own places.
void AdaptMainMenu(const std::string& view) {
    for (const char* name : {"mainmenu.gui", "mainmenu8x6.gui", "mainmenu10x7.gui", "mainmenu12x9.gui", "mainmenu16x12.gui"}) {
        if (PlayerHas(name)) continue;
        const std::string target = view + "/" + name, work = WorkName(target);
        if (!Exists(target) || KmrpMainMenuBars(target.c_str(), work.c_str()) != 0) { unlink(work.c_str()); continue; }
        MoveOver(work, target);
    }
}

// Windows' DeriveFromOverrideK1 (issue 79): each file the set's kmrp_derive.txt lists whose source
// the player's override has is made again from the mod's copy into `view`, the format choosing
// how: a table merged three ways against the game's, a picture drawn as the game's was, the
// swoop model changed only where it is still the game's. What cannot be made is logged and the
// mod's file is used. kmrp-gameart.c, `derived`, has the record's format.
void DeriveFromOverride(const std::string& set, const std::string& view, const std::string& key,
                        const std::string& overrideFolder, int width, int height) {
    std::vector<unsigned char> record;
    if (!ReadFile(set + "/kmrp_derive.txt", record)) return;
    const std::string text(record.begin(), record.end());
    int made = 0;
    for (std::size_t at = 0; at < text.size();) {
        std::size_t end = text.find('\n', at);
        if (end == std::string::npos) end = text.size();
        std::string line = text.substr(at, end - at);
        at = end + 1;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::vector<std::string> field;
        for (std::size_t from = 0;;) {
            const std::size_t tab = line.find('\t', from);
            field.push_back(line.substr(from, tab == std::string::npos ? std::string::npos : tab - from));
            if (tab == std::string::npos) break;
            from = tab + 1;
        }
        if (field.size() < 2 || field[0].size() < 5 || field[1].empty() || field[1].size() > 16) continue;
        const std::string& output = field[0];
        const std::string& source = field[1];
        const std::string stem = output.substr(0, output.size() - 4), format = Lower(output.substr(output.size() - 4));
        const std::string target = view + "/" + output, work = WorkName(target);
        if (format == ".2da") {
            if (!PlayerHas(source + ".2da")) continue;
            std::vector<unsigned char> theirs, ours;
            unsigned char* base = nullptr;
            std::size_t baseSize = 0;
            const std::string name = source + ".2da";
            if (!ReadFile(overrideFolder + "/" + name, theirs) || !ReadFile(set + "/" + output, ours) ||
                KmrpReadKeyedResource(key.c_str(), source.c_str(), 2017, &base, &baseSize) != 0) {
                free(base);
                Warn("compatibility: the override folder's %s: KMRP's changes to it are off (a copy could not be read); "
                     "the mod's table is used as it is", name.c_str());
                continue;
            }
            uint8_t* merged = nullptr;
            std::size_t mergedSize = 0;
            char* notes = nullptr;
            int counts[4]{};
            const int result = KmrpMerge2da(name.c_str(), base, baseSize, ours.data(), ours.size(), theirs.data(), theirs.size(),
                                            &merged, &mergedSize, &notes, counts);
            free(base);
            LogNotes("the override folder's ", notes);
            KmrpMergeFree(notes);
            if (result == 0 && WriteFile(work, merged, mergedSize) && MoveOver(work, target)) {
                made++;
                Warn("compatibility: the override folder's %s merged with KMRP's: %d changes of KMRP's made, %d kept the "
                     "mod's, %d lost", name.c_str(), counts[3], counts[0], counts[1]);
            } else {
                unlink(work.c_str());
                Warn("compatibility: the override folder's %s: KMRP's changes to it are off; the mod's table is used as it is", name.c_str());
            }
            KmrpMergeFree(merged);
        } else if (format == ".tga" || format == ".tpc") {
            if (field.size() < 7 || !PlayerHas(source + ".tga")) continue;   // a .tga or a .tpc
            const std::string tpc = overrideFolder + "/" + source + ".tpc", tga = overrideFolder + "/" + source + ".tga";
            const std::string from = Exists(tpc) ? tpc : tga;
            const std::string outName = view + "/" + stem + (Exists(overrideFolder + "/" + stem + ".tpc") ? ".tpc" : ".tga");
            const std::string outWork = WorkName(outName);
            const int result = KmrpDeriveImage(from.c_str(), atoi(field[2].c_str()), atoi(field[3].c_str()), atoi(field[4].c_str()),
                                               atoi(field[5].c_str()), field[6].c_str(), outWork.c_str());
            if (result == 0 && MoveOver(outWork, outName)) {
                made++;
                Log("compatibility: %s made from the override folder's %s", output.c_str(), source.c_str());
            } else {
                unlink(outWork.c_str());
                Warn("compatibility: the override folder's %s: KMRP's copy of it (%s) is off, as the picture could not be "
                     "read; the mod's picture is used as it is", source.c_str(), output.c_str());
            }
        } else if (format == ".mdl") {
            if (!PlayerHas(source + ".mdl")) continue;
            const std::string mdl = overrideFolder + "/" + source + ".mdl", mdx = overrideFolder + "/" + source + ".mdx";
            // Made in a folder of its own and moved, as the model comes with its .mdx.
            const std::string workFolder = view + "/model.tmp" + std::to_string(getpid());
            mkdir(workFolder.c_str(), 0755);
            const int result = Exists(mdx) ? KmrpSwoopHudModel(mdl.c_str(), mdx.c_str(), workFolder.c_str(),
                                                               static_cast<unsigned>(width), static_cast<unsigned>(height)) : 1;
            const std::string builtMdl = workFolder + "/" + stem + ".mdl", builtMdx = workFolder + "/" + stem + ".mdx";
            if (result == 0 && MoveOver(builtMdl, view + "/" + stem + ".mdl") && MoveOver(builtMdx, view + "/" + stem + ".mdx")) {
                made++;
                Warn("compatibility: the override folder's %s.mdl given KMRP's change", source.c_str());
            } else if (result != 3) {
                Warn("compatibility: the override folder's %s.mdl: KMRP's change of it (%s) is off, as the part it changes "
                     "is not the game's there; the mod's model is used as it is", source.c_str(), output.c_str());
            }
            RemoveFlat(workFolder);
        } else if (PlayerHas(output)) {
            Warn("compatibility: %s: no way to make a %s file again from a mod's copy; the mod's is used as it is",
                 output.c_str(), format.c_str());
        }
    }
    if (made) Log("compatibility: %d of KMRP's files made from the override folder's copies", made);
}

// In this order, as Windows' since 2026-10-30: live layout, then the galaxy map and the main menu
// on what it wrote, then what is made from a mod's copies.
void AdaptView(const std::string& set, const std::string& view, int width, int height) {
    const std::string assets = AssetsDirectory();
    if (assets.empty()) return;
    const std::string key = assets + "/chitin.key", overrideFolder = assets + "/override";
    if (!Exists(key)) { Warn("no chitin.key in %s: the set's layouts stand as they are", assets.c_str()); return; }
    AdaptLiveLayout(set, view, key, overrideFolder, width, height);
    AdaptGalaxyMap(view, key, overrideFolder);
    AdaptMainMenu(view);
    DeriveFromOverride(set, view, key, overrideFolder, width, height);
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
    struct stat keyInfo{};
    stat(key.c_str(), &keyInfo);
    // "art 3" as Windows': sets before it have no kmrp_derive.txt, the record DeriveFromOverride
    // makes a mod's copies from.
    const std::string stamp = std::to_string(width) + "x" + std::to_string(height) + " pack " +
        std::to_string(static_cast<long long>(packInfo.st_size)) + " " + std::to_string(static_cast<long long>(packInfo.st_mtime)) +
        " key " + std::to_string(static_cast<long long>(keyInfo.st_size)) + " " + std::to_string(static_cast<long long>(keyInfo.st_mtime)) +
        " art 3\n";
    directory = g_root + "/sets/" + std::to_string(width) + "x" + std::to_string(height);
    if (!MakeDirectories(g_root + "/sets")) return false;
    // An art helper that failed with the game's files there: the set is used but not sealed, so
    // the next two starts try again, and a third failure is the files themselves and is sealed,
    // or every start would rebuild the set (Windows' BuildSet, audit GUI-5). The game's files
    // absent is no failure.
    const std::string triesPath = directory + ".tries";
    const bool gameFiles = Exists(pack) && Exists(key);
    bool seal = true;
    const bool built = Build(directory, stamp, [&](const std::string& work) {
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
        if (KmrpGameArt(pack.c_str(), key.c_str(), static_cast<unsigned>(height), work.c_str()) != 0) {
            if (gameFiles) seal = false;
            Warn("the row frames, tutorial icons and tutorial.2da could not be made; the game keeps its own");
        }
        if (KmrpAbilityIcons(pack.c_str(), static_cast<unsigned>(height), work.c_str(), reserved.c_str()) != 0) {
            if (gameFiles) seal = false;
            Warn("the feat, power and skill icons could not be enlarged; they stay their original size");
        }
        unlink(reserved.c_str());
        // The swoop race's chevron parked outside a wide screen's dashboard (handoff item 54).
        const int swoop = KmrpSwoopHud(key.c_str(), work.c_str(), static_cast<unsigned>(width), static_cast<unsigned>(height));
        if (swoop != 0 && swoop != 1 && swoop != 3) Warn("swoop HUD model: could not be written");
        else Log("swoop HUD model: %s", swoop == 0 ? "the parked speed segment moved out of this screen's view"
                                      : swoop == 1 ? "not the game's own, left as it is"
                                                   : "the game's own is right for this screen");
        Log("set %dx%d: %s", width, height, exact ? "the bank's" : "blended from the nearest set");
        if (seal) return true;
        std::vector<unsigned char> tries;
        const std::size_t count = ReadFile(triesPath, tries) ? tries.size() : 0;
        if (count >= 2) { seal = true; unlink(triesPath.c_str()); return true; }
        const std::vector<unsigned char> more(count + 1, '.');
        WriteFile(triesPath, more.data(), more.size());
        return true;
    }, &seal);
    if (built && seal) unlink(triesPath.c_str());
    return built;
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

void ReleaseUnpacked() { ForgetUnpacked(); }

bool Registered() { return g_registered; }
void Disable() { TheState().disabled = true; }
const std::string& NewestSetDirectory() { return TheState().newestDirectory; }
const std::string& ArtworkDirectory() { return TheState().art; }

std::string OverrideDirectory() {
    const std::string assets = AssetsDirectory();
    return assets.empty() ? assets : assets + "/override";
}

// A font's source from the bank, by its private name (fonts.cpp).
bool FontSource(const std::string& name, std::vector<unsigned char>& bytes) {
    if (!Load() || g_groups.size() <= 3) return false;
    for (const Entry& entry : g_groups[3].entries)
        if (entry.name == name) return Decode(entry.key, bytes);
    return false;
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
        Warn("the cache in %s could not be written: the game keeps its own files", g_root.c_str());
        return false;
    }
    AdaptView(whole, *set, width, height);
    kmrp::fonts::Prepare(whole, *set, height);   // the style's fonts at the sizes in use
    ForgetUnpacked();
    return true;
}

// kmrp-prepare, at install: the same cache the game would make on its first start at each size,
// so it starts without making anything (handoff item 73, as Windows' installer does with
// KmrpPrepareAssets). Nothing here reaches the engine: Load, RemoveStale, BuildStore, BuildSet
// and Covers read the pack and the game's files and write the cache, with the helpers.
void SetPaths(const std::string& assets, const std::string& pack) {
    State& state = TheState();
    state.outside = true;
    state.givenAssets = assets;
    state.givenPack = pack;
}

bool PrepareStore() {
    if (!Load()) return false;
    RemoveStale();
    const bool ok = BuildStore();
    ForgetUnpacked();
    if (!ok) Warn("the cache in %s could not be written", g_root.c_str());
    return ok;
}

bool PrepareSet(int width, int height) {
    if (!Covers(width, height)) {
        if (!g_groups.empty()) Warn("no menu set for %dx%d", width, height);
        return false;
    }
    std::string whole;
    const bool ok = BuildSet(width, height, whole);
    ForgetUnpacked();
    if (!ok) Warn("the set for %dx%d could not be written in %s", width, height, g_root.c_str());
    return ok;
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
