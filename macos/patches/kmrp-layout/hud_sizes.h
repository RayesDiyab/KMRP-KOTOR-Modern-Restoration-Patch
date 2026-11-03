// KMRP for macOS: the sizes the HUD Size page chooses, as both modules read them. KMRP's module
// (kmrp-assets/hud_options.cpp, pc_hud.cpp) writes and reads them; the controller patch's
// (xbox_hud.cpp) only reads, as Windows' K1XboxHud.cpp reads the same section itself. The rules
// are Windows' own header, K1HudOptionsPolicy.h; only what depends on the Mac is here:
//
//   - where the file is. Windows' swkotor.ini stands beside the game; the Mac's in
//     ~/Library/Application Support/Knights of the Old Republic (kmrp_layout.cpp), inside the
//     container for the Mac App Store's game, where HOME is the container. Section
//     [KMRP HUD Size], Windows' keys. The game's own writes of the file leave the section alone:
//     every CExoIni it writes through is a local one, which reads the file first and writes back
//     every section it found (CExoIniInternal::WriteIniEntry, 0x1003525D8).
//   - which part of the Xbox-style HUD a piece of its table belongs to. Windows'
//     XboxElementOf (K1HudOptionsPolicy.h) keys on the Windows offsets of CSWGuiMainInterface,
//     so on the Mac's table it would answer -1 for all but the bottom left and those sliders
//     would do nothing, silently (audit MAC-3). XboxElementOf below keys on the same controls at
//     their Mac offsets, as xbox_hud_layout.inc names them.
//
// A header with inline functions, so each module compiles its own and no global needs
// initialising at load.
#pragma once

#include "../../../src/controller-native/K1HudOptionsPolicy.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <strings.h>

namespace kmrp {
namespace hud {

// The part of the Xbox-style HUD a piece of its table belongs to, or -1. Windows' rule with the
// Mac's offsets: the combat strip across the top keeps its size, and anything else at the bottom
// left is the action menu.
inline int XboxElementOf(unsigned offset, bool party, bool row, bool bottomLeft) {
    using namespace KmrpHudOptions;
    if (party) return XboxParty;
    if (row) return -1;
    switch (offset) {
        case 0x7640: case 0x7B20: return XboxMinimap;                               // LBL_MAPBORDER, BTN_MINIMAP
        case 0x1CB8: case 0x1E50: case 0x2180: case 0x1FE8: return XboxTargetBar;   // LBL_NAME(BG), PB_HEALTH, LBL_HEALTHBG
        // The disengage button and its queue: LBL_COMBATBG1, LBL_QUEUE0..3, BTN_CLEARONE(2).
        case 0x83C0: case 0x7D60: case 0x7EF8: case 0x8090: case 0x8228: case 0x8AA8: case 0x8CE8: return XboxDisengage;
    }
    return bottomLeft ? XboxActions : -1;
}

inline std::string IniPath() {
    const char* home = std::getenv("HOME");
    if (!home || !*home) return std::string();
    return std::string(home) + "/Library/Application Support/Knights of the Old Republic/swkotor.ini";
}

// The policy header's names are wide, for Windows' profile calls.
inline std::string Narrow(const wchar_t* text) {
    std::string out;
    for (; *text; ++text) out += static_cast<char>(*text);
    return out;
}

inline std::string Trimmed(const std::string& s) {
    const std::size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return std::string();
    return s.substr(first, s.find_last_not_of(" \t\r\n") - first + 1);
}

// True for the header of a section, its name in `name`.
inline bool SectionHeader(const std::string& line, std::string& name) {
    const std::string trimmed = Trimmed(line);
    if (trimmed.size() < 2 || trimmed[0] != '[') return false;
    const std::size_t close = trimmed.find(']');
    if (close == std::string::npos) return false;
    name = Trimmed(trimmed.substr(1, close - 1));
    return true;
}

// Every value as stored, then the link, as Windows' Initialize reads them: no file, no section
// or no key is that key's default, and section and key names compare without case, as
// GetPrivateProfileInt reads them. Each value goes through Percent.
inline KmrpHudOptions::Sizes ReadSizes() {
    using namespace KmrpHudOptions;
    Sizes sizes;
    sizes.linked = false;
    bool linked = true;
    const std::string path = IniPath();
    FILE* f = path.empty() ? nullptr : std::fopen(path.c_str(), "r");
    if (f) {
        const std::string section = Narrow(IniSection);
        bool ours = false;
        char buffer[1024];
        while (std::fgets(buffer, sizeof buffer, f)) {
            const std::string line(buffer);
            std::string name;
            if (SectionHeader(line, name)) { ours = strcasecmp(name.c_str(), section.c_str()) == 0; continue; }
            const std::size_t eq = line.find('=');
            if (!ours || eq == std::string::npos) continue;
            const std::string key = Trimmed(line.substr(0, eq));
            const int value = std::atoi(line.c_str() + eq + 1);
            if (strcasecmp(key.c_str(), "LinkSizes") == 0) { linked = value != 0; continue; }
            for (int i = 0; i < ElementCount; ++i)
                if (strcasecmp(key.c_str(), Narrow(IniKeys[i]).c_str()) == 0) sizes.values[i] = Percent(value);
        }
        std::fclose(f);
    }
    sizes.linked = linked;
    return sizes;
}

// The section written again and everything else in the file left as it is: to a file beside it,
// then over it, so a failure leaves the old one whole. The section keeps its place in the file;
// a file without it gets it at the end.
inline bool WriteSizes(const KmrpHudOptions::Sizes& sizes) {
    using namespace KmrpHudOptions;
    const std::string path = IniPath();
    if (path.empty()) return false;
    const std::string section = Narrow(IniSection);
    std::string body = "[" + section + "]\n";
    char value[32];
    for (int i = 0; i < ElementCount; ++i) {
        std::snprintf(value, sizeof value, "=%d\n", sizes.values[i]);
        body += Narrow(IniKeys[i]) + value;
    }
    body += sizes.linked ? "LinkSizes=1\n\n" : "LinkSizes=0\n\n";

    std::string text;
    bool written = false, ours = false;
    if (FILE* f = std::fopen(path.c_str(), "r")) {
        char buffer[1024];
        while (std::fgets(buffer, sizeof buffer, f)) {
            std::string name;
            if (SectionHeader(buffer, name)) {
                ours = strcasecmp(name.c_str(), section.c_str()) == 0;
                if (ours && !written) { text += body; written = true; }
            }
            if (!ours) text += buffer;
        }
        std::fclose(f);
    }
    if (!written) {
        if (!text.empty() && text[text.size() - 1] != '\n') text += '\n';
        text += body;
    }
    const std::string temporary = path + ".kmrp";
    FILE* out = std::fopen(temporary.c_str(), "w");
    if (!out) return false;
    const bool complete = std::fwrite(text.data(), 1, text.size(), out) == text.size();
    const bool closed = std::fclose(out) == 0;
    if (!complete || !closed || std::rename(temporary.c_str(), path.c_str()) != 0) {
        std::remove(temporary.c_str());
        return false;
    }
    return true;
}

}  // namespace hud
}  // namespace kmrp
