/*
  KMRP for macOS: the patch's options.

  KOTOR Patch Manager with patch options (LaneDibello/Kotor-Patch-Manager#310), and KMRP's
  installer, record the values a patch was applied with beside the game's executable as
  configs/<patch id>.ini, section [Patch Options], one key per option, a toggle as 1 or 0. For
  KMRP, in the app bundle:

      Knights of the Old Republic.app/Contents/MacOS/configs/kmrp.ini

      [Patch Options]
      controller=1
      map-notes=1
      debug-logs=0

  A hook whose `when` does not hold is left out by whoever installs. A manager without options
  (0.7.1) installs every hook and writes no file. So the hooks alone cannot say what was chosen,
  and everything the module does on its own (its constructors, and the hooks that stay whatever
  was chosen) asks here instead. A missing file, section or key is the option's default, which
  is what such a manager installs: controller support and map notes on, logs off.

  The folder is found from the module's own path: patches/kmrp.dylib is one folder below the
  executable. Each value is read once, the first time it is asked for. The manager writes the
  section with CRLF line ends and nothing around the `=`; a file edited by hand may have spaces
  and either line end, and section and key names compare without case, as Windows'
  GetPrivateProfileInt reads them.
*/
#include "options.h"

#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <string>
#include <strings.h>

namespace kmrp {
namespace {

const char kFile[] = "/configs/kmrp.ini";
const char kSection[] = "Patch Options";

std::string Trimmed(const std::string& s) {
    const std::size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return std::string();
    return s.substr(first, s.find_last_not_of(" \t\r\n") - first + 1);
}

std::string OptionsPath() {
    Dl_info info;
    if (!dladdr(reinterpret_cast<const void*>(&OptionsPath), &info) || !info.dli_fname) return std::string();
    std::string path(info.dli_fname);
    for (int up = 0; up < 2; up++) {
        const std::size_t slash = path.rfind('/');
        if (slash == std::string::npos) return std::string();
        path.erase(slash);
    }
    return path + kFile;
}

}  // namespace

int PatchOption(const char* id, int fallback) {
    static const std::string path = OptionsPath();
    FILE* f = path.empty() ? nullptr : fopen(path.c_str(), "r");
    if (!f) return fallback;
    int value = fallback;
    bool ours = false;
    char buffer[1024];
    while (fgets(buffer, sizeof buffer, f)) {
        const std::string line = Trimmed(buffer);
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;
        if (line[0] == '[') {
            const std::size_t close = line.find(']');
            ours = close != std::string::npos && strcasecmp(Trimmed(line.substr(1, close - 1)).c_str(), kSection) == 0;
            continue;
        }
        const std::size_t eq = line.find('=');
        if (!ours || eq == std::string::npos) continue;
        if (strcasecmp(Trimmed(line.substr(0, eq)).c_str(), id) != 0) continue;
        // The first of a key, as GetPrivateProfileInt takes it; text that is no number is 0 there.
        value = atoi(Trimmed(line.substr(eq + 1)).c_str());
        break;
    }
    fclose(f);
    return value;
}

bool ControllerOption() {
    static const bool on = PatchOption("controller", 1) != 0;
    return on;
}

bool MapNotesOption() {
    static const bool on = PatchOption("map-notes", 1) != 0;
    return on;
}

bool DebugLogs() {
    static const bool on = PatchOption("debug-logs", 0) != 0;
    return on;
}

}  // namespace kmrp
