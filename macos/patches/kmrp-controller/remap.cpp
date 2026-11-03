// KMRP for macOS, controller support: controller remapping at run time. The Mac port of
// src/controller-native/K1ButtonRemap.cpp: the layout kept in the controller's settings file,
// section [Controller Remap], and the translation of the pad's buttons in the world
// (K1ButtonRemapPolicy.h, whose rules are shared and tested by Test-ButtonRemap.py).
//
// The settings file is the one rumble.cpp and the HUD read (standalone::SettingsPath). Windows
// has GetPrivateProfileString and WritePrivateProfileString for it; here its text is read and
// written by the same rules: section and key names in any case, the rest of the file left as it
// was (the installer's comments, the player's other settings), and the section replaced whole, so
// no key of the old layout's is left behind. It is written beside itself and moved over, so a
// crash cannot leave half a file.
#include "remap.h"

#include "standalone.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <unistd.h>
#include <vector>

namespace kmrp {
namespace remap {
namespace {

using namespace KmrpRemap;

const char kSection[] = "Controller Remap";
Mapping g_saved;
bool g_loaded = false;
Translator g_translator;
std::uint16_t g_physical = 0;

std::string Trimmed(const std::string& text) {
    std::size_t first = 0, last = text.size();
    while (first < last && (text[first] == ' ' || text[first] == '\t')) ++first;
    while (last > first && strchr(" \t\r\n", text[last - 1])) --last;
    return text.substr(first, last - first);
}

// The file's lines, without their line ends; empty when it cannot be read.
std::vector<std::string> ReadLines(const std::string& path) {
    std::vector<std::string> lines;
    FILE* f = path.empty() ? nullptr : fopen(path.c_str(), "r");
    if (!f) return lines;
    std::string text;
    char chunk[4096];
    std::size_t got;
    while ((got = fread(chunk, 1, sizeof chunk, f)) > 0) text.append(chunk, got);
    fclose(f);
    std::size_t at = 0;
    while (at < text.size()) {
        std::size_t end = text.find('\n', at);
        if (end == std::string::npos) end = text.size();
        std::string line = text.substr(at, end - at);
        if (!line.empty() && line.back() == '\r') line.pop_back();
        lines.push_back(line);
        at = end + 1;
    }
    return lines;
}

// A line's section name when it opens one.
bool SectionOf(const std::string& line, std::string& name) {
    const std::string trimmed = Trimmed(line);
    if (trimmed.size() < 2 || trimmed.front() != '[' || trimmed.back() != ']') return false;
    name = Trimmed(trimmed.substr(1, trimmed.size() - 2));
    return true;
}

bool IsOurs(const std::string& section) { return strcasecmp(section.c_str(), kSection) == 0; }

void Load() {
    g_loaded = true;
    g_saved = Mapping{};
    std::string layout;
    std::string values[ButtonCount];
    bool inside = false;
    for (const std::string& line : ReadLines(standalone::SettingsPath())) {
        std::string section;
        if (SectionOf(line, section)) { inside = IsOurs(section); continue; }
        if (!inside) continue;
        const std::string trimmed = Trimmed(line);
        const std::size_t equals = trimmed.find('=');
        if (trimmed.empty() || trimmed[0] == ';' || equals == std::string::npos) continue;
        const std::string key = Trimmed(trimmed.substr(0, equals)), value = Trimmed(trimmed.substr(equals + 1));
        if (strcasecmp(key.c_str(), LayoutKey) == 0) layout = value;
        for (int a = 0; a < ButtonCount; ++a)
            if (strcasecmp(key.c_str(), ActionKeys[a]) == 0) values[a] = value;
    }
    if (strcasecmp(layout.c_str(), LayoutName) != 0) return;
    Mapping read;
    for (int a = 0; a < ButtonCount; ++a)
        read.button[a] = ButtonByName(values[a].empty() ? ButtonNames[a] : values[a].c_str());
    // A layout that is not complete (edited by hand, or from another version) is not used: the
    // default is, and the screen opens on it.
    if (read.Complete()) g_saved = read;
}

}  // namespace

const Mapping& Saved() {
    if (!g_loaded) Load();
    return g_saved;
}

bool Save(const Mapping& mapping) {
    if (!mapping.Complete()) return false;
    const std::string path = standalone::SettingsPath();
    if (path.empty()) return false;
    // Everything but the section, then the section at the end, as WritePrivateProfileString
    // leaves a section it has deleted and made again.
    std::string text;
    bool inside = false;
    for (const std::string& line : ReadLines(path)) {
        std::string section;
        if (SectionOf(line, section)) inside = IsOurs(section);
        if (!inside) text += line + "\n";
    }
    if (!text.empty() && text.size() >= 2 && text.compare(text.size() - 2, 2, "\n\n") != 0) text += "\n";
    text += std::string("[") + kSection + "]\n" + LayoutKey + "=" + LayoutName + "\n";
    for (int a = 0; a < ButtonCount; ++a)
        text += std::string(ActionKeys[a]) + "=" + ButtonNames[mapping.button[a]] + "\n";
    const std::string work = path + ".tmp" + std::to_string(getpid());
    FILE* f = fopen(work.c_str(), "wb");
    if (!f) return false;
    const bool written = fwrite(text.data(), 1, text.size(), f) == text.size();
    if (fclose(f) != 0 || !written || rename(work.c_str(), path.c_str()) != 0) {
        unlink(work.c_str());
        return false;
    }
    g_saved = mapping;
    g_loaded = true;
    return true;
}

std::uint16_t Apply(std::uint16_t buttons, bool world) {
    g_physical = buttons;
    return g_translator.Apply(buttons, world, Saved());
}

std::uint16_t Physical() { return g_physical; }

void Glyph(int action, char family, char (&resref)[16]) {
    std::memset(resref, 0, sizeof resref);
    const Mapping& m = Saved();
    int button = action >= 0 && action < ButtonCount ? m.button[action] : None;
    if (button < 0) button = action >= 0 && action < ButtonCount ? action : A;
    snprintf(resref, sizeof resref, "kmr%crm%s", family, GlyphCodes[button]);
}

}  // namespace remap
}  // namespace kmrp
