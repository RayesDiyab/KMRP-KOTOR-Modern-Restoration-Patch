/*
  KMRP for macOS, the controller patch: what makes it a patch of its own (2026-10-07).

  Until then controller support was part of KMRP's module, an option of KMRP's patch, and took
  from the rest of it: its artwork and layouts from KMRP's menu sets, SDL from KMRP's bank, the
  options from KMRP's options file. This file is what a controller needs of that, so that the
  patch works on a game with no KMRP, beside KMRP, or beside another interface patch. Windows'
  counterpart is src/controller-native/K1ControllerStandalone.cpp.

  1. Its files. macos/tools/make_controller_assets.py makes them with the steps Windows' patch
     uses (tools/build_controller_assets.py), on the Mac game's own layout files: the game's
     layouts with the controller's cues added, the Controller Layout screen, the badge and cue
     art of four controller families, the Xbox-style HUD's art, and SDL. They are linked into
     the module as the section __KMRPC,__assets:

         "KMCAS001"
         32 bytes   SHA-256 of the rest: the build's identity, which names the cache
         u32        files
         per file   u16 name length, name, 32-byte SHA-256, u32 size, u32 stored size, zlib

     Unpacked once to ~/Library/Caches/KMRP-Controller/<build>/files, checked against each
     file's hash. Nothing is written to the game's override folder.

  2. Registered with the game's resource manager through an alias of its own, as KMRP's module
     registers its menu sets (kmrp-assets/assets.cpp): CExoAliasList::Add (0x10034C9DE) on the
     alias list at [CExoBase + 0x18] (0x100677CB8), then CExoResMan::AddResourceDirectory
     (0x1003693BC). What is registered is a folder of links made for this run,
     <build>/run-<pid>, so that what the game sees can differ from run to run:

       - beside KMRP (its module, patches/kmrp.dylib, is loaded) the folder has no layout
         file: KMRP's layouts load, which already hold the controls this patch adds to the
         game's own (the same tags, from the same build step);
       - otherwise it has everything.

     The game searches the directory added last first. The hook is the instruction after the
     game adds its own OVERRIDE: directory, which is where KMRP's module adds its menu set
     (0x10026C739), so this patch's folder is added after both and its artwork is found before
     KMRP's of the same names: the patch draws from its own files and fits them to whatever
     interface is loaded (prompts.cpp), and takes nothing from another patch. KMRP adds another
     set when the resolution is changed in the game; RegisterAgain puts this patch's folder in
     front again.

  3. SDL from its own bank (backend_sdl.cpp asks g_sdlPath), and the rumble settings written
     once when there are none, as KMRP's installer writes them, for a game with no installer.
*/
#include "standalone.h"

#include "pad.h"

#include <CommonCrypto/CommonDigest.h>
#include <array>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <dlfcn.h>
#include <mach-o/getsect.h>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include <zlib.h>

namespace kmrp {

const char* (*g_sdlPath)() = nullptr;   // backend_sdl.cpp

namespace standalone {
namespace {

using Key = std::array<unsigned char, 32>;
struct File { std::string name; Key key; const unsigned char* bytes; unsigned size, stored; };

const char kMagic[] = "KMCAS001";
const char kSdl[] = "kmrp-sdl3.dylib";
const char kMarker[] = "kmrplayout.gui";   // in every bank: how a bank that is not one is known

std::vector<File>* g_files = nullptr;
std::string* g_root = nullptr;      // ~/Library/Caches/KMRP-Controller/<build>
std::string* g_run = nullptr;       // <root>/run-<pid>, registered with the game
bool g_loaded = false, g_unpacked = false, g_beside = false;
int g_generation = 0;

bool Exists(const std::string& path) { struct stat s; return lstat(path.c_str(), &s) == 0; }

bool MakeDirectories(const std::string& path) {
    for (std::size_t at = 1; at <= path.size(); ++at) {
        if (at != path.size() && path[at] != '/') continue;
        const std::string part = path.substr(0, at);
        if (mkdir(part.c_str(), 0755) != 0 && errno != EEXIST) return false;
    }
    return true;
}

std::vector<std::string> Names(const std::string& directory) {
    std::vector<std::string> names;
    if (DIR* d = opendir(directory.c_str())) {
        while (const dirent* e = readdir(d))
            if (strcmp(e->d_name, ".") != 0 && strcmp(e->d_name, "..") != 0) names.push_back(e->d_name);
        closedir(d);
    }
    return names;
}

// Removes a folder this module made: plain files and links directly inside, then the folder.
void RemoveFlat(const std::string& directory) {
    for (const std::string& name : Names(directory)) unlink((directory + "/" + name).c_str());
    rmdir(directory.c_str());
}

bool Load() {
    if (g_loaded) return g_files != nullptr;
    g_loaded = true;
    Dl_info info;
    if (!dladdr(reinterpret_cast<const void*>(&Load), &info) || !info.dli_fbase) return false;
    unsigned long size = 0;
    const unsigned char* data =
        getsectiondata(static_cast<const mach_header_64*>(info.dli_fbase), "__KMRPC", "__assets", &size);
    if (!data || size < 8 + 32 + 4 || memcmp(data, kMagic, 8) != 0) {
        Log("the module carries no files of its own (it was built without them)");
        return false;
    }
    const unsigned char* at = data + 8 + 32;
    const unsigned char* const end = data + size;
    unsigned count;
    memcpy(&count, at, 4);
    at += 4;
    if (!count || count > 8000) return false;
    auto* files = new std::vector<File>;
    bool marker = false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned short length;
        if (end - at < 2) return false;
        memcpy(&length, at, 2);
        at += 2;
        if (!length || length > 255 || end - at < length + 40) return false;
        File file;
        file.name.assign(reinterpret_cast<const char*>(at), length);
        at += length;
        if (file.name.find_first_of("/\\:") != std::string::npos || file.name.find("..") != std::string::npos) return false;
        memcpy(file.key.data(), at, 32);
        memcpy(&file.size, at + 32, 4);
        memcpy(&file.stored, at + 36, 4);
        at += 40;
        if (!file.size || file.size > (64u << 20) || static_cast<std::size_t>(end - at) < file.stored) return false;
        file.bytes = at;
        at += file.stored;
        marker = marker || file.name == kMarker;
        files->push_back(std::move(file));
    }
    const char* home = getenv("HOME");
    if (at != end || !marker || !home || !*home) return false;
    char build[17];
    for (int i = 0; i < 8; ++i) snprintf(build + 2 * i, 3, "%02x", data[8 + i]);
    g_root = new std::string(std::string(home) + "/Library/Caches/KMRP-Controller/" + build);
    g_files = files;
    return true;
}

bool WriteChecked(const File& file, const std::string& target) {
    std::vector<unsigned char> data(file.size);
    uLongf size = file.size;
    if (uncompress(data.data(), &size, file.bytes, file.stored) != Z_OK || size != file.size) return false;
    Key measured;
    CC_SHA256(data.data(), static_cast<CC_LONG>(data.size()), measured.data());
    if (measured != file.key) return false;
    const std::string work = target + ".tmp" + std::to_string(getpid());
    FILE* f = fopen(work.c_str(), "wb");
    if (!f) return false;
    const bool ok = fwrite(data.data(), 1, data.size(), f) == data.size();
    if (fclose(f) != 0 || !ok || rename(work.c_str(), target.c_str()) != 0) { unlink(work.c_str()); return false; }
    return true;
}

// The caches of other builds of this module, and the run folders of games no longer running.
void RemoveStale() {
    const std::size_t slash = g_root->rfind('/');
    const std::string caches = g_root->substr(0, slash), build = g_root->substr(slash + 1);
    for (const std::string& name : Names(caches)) {
        if (name == build || name.size() != 16 || name.find_first_not_of("0123456789abcdef") != std::string::npos) continue;
        const std::string other = caches + "/" + name;
        for (const std::string& inner : Names(other)) RemoveFlat(other + "/" + inner);
        unlink((other + "/files.complete").c_str());
        rmdir(other.c_str());
    }
    for (const std::string& name : Names(*g_root)) {
        if (name.compare(0, 4, "run-") != 0) continue;
        const int pid = atoi(name.c_str() + 4);
        if (pid > 0 && pid != getpid() && kill(pid, 0) != 0 && errno == ESRCH) RemoveFlat(*g_root + "/" + name);
    }
}

bool Unpack() {
    if (g_unpacked) return true;
    if (!Load()) return false;
    const std::string files = *g_root + "/files", stamp = *g_root + "/files.complete";
    if (!Exists(stamp)) {
        if (!MakeDirectories(files)) return false;
        for (const File& file : *g_files) {
            const std::string target = files + "/" + file.name;
            if (!WriteChecked(file, target)) { Log("the cache could not hold %s", file.name.c_str()); return false; }
            if (file.name == kSdl) chmod(target.c_str(), 0755);
        }
        if (FILE* f = fopen(stamp.c_str(), "w")) fclose(f); else return false;
        Log("%zu files unpacked to %s", g_files->size(), files.c_str());
    }
    RemoveStale();
    g_unpacked = true;
    return true;
}

bool EndsWith(const std::string& name, const char* suffix) {
    const std::size_t length = strlen(suffix);
    return name.size() >= length && name.compare(name.size() - length, length, suffix) == 0;
}

// This run's folder of links: everything, or everything but the layout files beside KMRP.
bool LinkRun() {
    if (g_run) return true;
    if (!Unpack()) return false;
    const std::string run = *g_root + "/run-" + std::to_string(getpid()), files = *g_root + "/files";
    RemoveFlat(run);
    if (!MakeDirectories(run)) return false;
    int linked = 0;
    for (const File& file : *g_files) {
        if (file.name == kSdl || (g_beside && EndsWith(file.name, ".gui"))) continue;
        if (symlink((files + "/" + file.name).c_str(), (run + "/" + file.name).c_str()) != 0) return false;
        ++linked;
    }
    Log("%d files for this run in %s%s", linked, run.c_str(), g_beside ? " (beside KMRP: no layout file)" : "");
    g_run = new std::string(run);
    return true;
}

// ---------------------------------------------------------------------------------- the engine
struct ExoString { char* text; int length; int pad; };
const auto MakeString = reinterpret_cast<void (*)(ExoString*, const char*)>(0x10034cca8);
const auto FreeString = reinterpret_cast<void (*)(ExoString*)>(0x10034cdf2);
const auto AliasAdd = reinterpret_cast<void (*)(void*, ExoString*, ExoString*)>(0x10034c9de);
const auto AddDirectory = reinterpret_cast<int (*)(void*, ExoString*)>(0x1003693bc);
void** const kExoBase = reinterpret_cast<void**>(0x100677cb8);
void** const kResourceManager = reinterpret_cast<void**>(0x100677cc8);

bool AddAliasedDirectory(void* manager, const char* alias, const std::string& path) {
    void* base = *kExoBase;
    void* aliases = base ? *reinterpret_cast<void**>(static_cast<char*>(base) + 0x18) : nullptr;
    if (!aliases || !manager) return false;
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

bool Register(void* manager) {
    if (!LinkRun()) return false;
    const std::string alias = "KMRPCTL" + std::to_string(++g_generation);
    const bool ok = AddAliasedDirectory(manager, alias.c_str(), *g_run);
    Log("files registered as %s: %s", alias.c_str(), ok ? "yes" : "refused");
    return ok;
}

const char* SdlPath() {
    static std::string* path = nullptr;
    if (path) return path->c_str();
    if (!Unpack()) return nullptr;
    const std::string target = *g_root + "/files/" + kSdl;
    if (!Exists(target)) return nullptr;
    path = new std::string(target);
    return path->c_str();
}

// The rumble settings, as KMRP's installer writes them (kmrp-mac.sh, install_settings), with
// the HUD's style added: for a game the patch reaches with no installer. A file already there
// is the player's and is never touched. rumble.cpp reads it, and takes these values without it.
const char kDefaultSettings[] =
    "; KMRP controller settings. Read by the controller module while the game runs;\n"
    "; changes take effect within a second, no restart needed.\n"
    "[Rumble]\n"
    "; Off, Original (BioWare's shipped rumble only) or Enhanced (adds KMRP's haptics)\n"
    "Mode=Enhanced\n"
    "; 0 to 100 percent\n"
    "Strength=100\n"
    "; the lightsaber hum, 0 to 100 percent of BioWare's level (0 turns it off);\n"
    "; 6 is the weakest an Xbox pad can play\n"
    "SaberHum=6\n"
    "; the hum pulses: on for SaberHumPulseMs (0 = a steady hum), then off until\n"
    "; the next pulse -- a gap picked at random between SaberHumPeriodMinMs and\n"
    "; SaberHumPeriodMaxMs, afresh for every pulse (make them equal for a fixed rhythm)\n"
    "SaberHumPulseMs=100\n"
    "SaberHumPeriodMinMs=500\n"
    "SaberHumPeriodMaxMs=2000\n"
    "; 1 writes every rumble event to ~/Library/Logs/KMRP/rumble.log\n"
    "Debug=0\n"
    "\n"
    "[Hud]\n"
    "; Xbox (laid out like the original Xbox version's while the pad is in use; the\n"
    "; game's own with mouse and keyboard) or PC (the game's own HUD always).\n"
    "; Read when the game starts. KotOR Patch Manager's \"Xbox-style HUD\" option, where\n"
    "; the manager offers options, decides instead of this line.\n"
    "Style=Xbox\n";

void WriteDefaultSettings() {
    const char* home = getenv("HOME");
    if (!home || !*home) return;
    const std::string folder = std::string(home) + "/Library/Application Support/Knights of the Old Republic";
    const std::string path = folder + "/kmrp-controller.ini";
    if (Exists(path) || !Exists(folder)) return;   // the game's own settings folder, made by the game
    if (FILE* f = fopen(path.c_str(), "wx")) {
        fwrite(kDefaultSettings, 1, sizeof kDefaultSettings - 1, f);
        fclose(f);
        Log("default settings written to %s", path.c_str());
    }
}

__attribute__((constructor)) void UseOwnFiles() { g_sdlPath = SdlPath; }

}  // namespace

bool BesideKmrp() { return g_beside; }

const char* FilesDirectory() {
    static std::string* files = nullptr;
    if (!files && Unpack()) files = new std::string(*g_root + "/files");
    return files ? files->c_str() : nullptr;
}

void RegisterAgain() {
    if (g_generation && *kResourceManager) Register(*kResourceManager);
}

}  // namespace standalone
}  // namespace kmrp

// The instruction after the game adds its OVERRIDE: directory (0x10026c73e; rbx the resource
// manager, the alias's CExoString at [rbp-0x40]). The stolen bytes are
//     lea rdi, [rbp-0x40]; call CExoString::~CExoString (0x10034cdf2)
// whose call is relative, so they are not run again: the handler frees the string itself.
extern "C" __attribute__((visibility("default"))) void KmrpControllerResources(void* manager, char* frame) {
    using namespace kmrp::standalone;
    FreeString(reinterpret_cast<ExoString*>(frame - 0x40));
    WriteDefaultSettings();
    // KMRP's module beside this one, whichever was loaded first: every patch's module is loaded
    // before the game runs.
    Dl_info self;
    if (dladdr(reinterpret_cast<const void*>(&KmrpControllerResources), &self) && self.dli_fname) {
        std::string path(self.dli_fname);
        path = path.substr(0, path.rfind('/') + 1) + "kmrp.dylib";
        if (void* kmrp = dlopen(path.c_str(), RTLD_NOLOAD | RTLD_LAZY)) { g_beside = true; dlclose(kmrp); }
    }
    Register(manager);
}
