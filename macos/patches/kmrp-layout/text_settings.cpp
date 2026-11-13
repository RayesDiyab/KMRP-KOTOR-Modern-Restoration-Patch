/*
  KMRP for macOS: the Text Size and Font page's choices, read once from swkotor.ini and held here,
  where the fit, the rows and the fonts ask for them. Windows' Initialize and Save
  (src/controller-native/K1TextOptions.cpp). The file is the game's, in its Application Support
  folder (hud_sizes.h says why [KMRP Text] survives the game's own writes); the section is
  Windows', with its keys: Size, MenuSize, BodySize, SmallSize, HudSize, LinkSizes, IconSize,
  FontStyle, OriginalFont and ModdedFonts. A missing file, section or key is that key's default,
  and a saved FontStyle of 0, the old HD font, reads as HD Font (K1TextOptionsPolicy.h, Style).

  Modded Font (FontStyle 3, handoff item 143, Windows 2026-11-08) is offered only while the game's
  override has a font, and a saved 3 with none there reads as HD Font. Fonts there not seen before
  choose it by themselves, written at once with their set (ModdedFonts), so a choice made since
  stays until the fonts there change (the maintainer: "only auto select when its in Override", and
  a change made later saved "so it doesnt change on restart").
*/
#include "text_settings.h"

#include "hud_sizes.h"
#include "text_fit.h"

#include "../../tools/kmrp-iconsize.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <strings.h>

namespace kmrp {
namespace fonts {
// The override's fonts (kmrp-assets/fonts.cpp). Weak, so a build of this part alone links: no
// fonts, no Modded Font.
__attribute__((weak)) std::uint64_t OverrideFontSet() { return 0; }
}

namespace textfit {
namespace {

using namespace KmrpTextOptions;

const char kSection[] = "KMRP Text";
const char* const kGroupKeys[TextGroupCount] = {"MenuSize", "BodySize", "SmallSize", "HudSize"};

struct Store {
    bool read = false;
    Settings live, saved;
    std::uint64_t moddedSet = 0;   // the override's fonts, 0 when it has none
};
Store& TheStore() {
    static Store* store = new Store;
    return *store;
}

std::string SetText(std::uint64_t set) {
    char text[32];
    std::snprintf(text, sizeof text, "%016llX", static_cast<unsigned long long>(set));
    return text;
}

Settings ReadFile(std::uint64_t moddedSet, std::string& moddedSeen) {
    int legacy = Default, linked = 1, style = HdOriginal, icon = KMRP_ICON_DEFAULT;
    int group[TextGroupCount] = {-1, -1, -1, -1};
    const std::string path = hud::IniPath();
    if (FILE* f = path.empty() ? nullptr : std::fopen(path.c_str(), "r")) {
        bool ours = false;
        char buffer[1024];
        while (std::fgets(buffer, sizeof buffer, f)) {
            const std::string line(buffer);
            std::string name;
            if (hud::SectionHeader(line, name)) { ours = strcasecmp(name.c_str(), kSection) == 0; continue; }
            const std::size_t eq = line.find('=');
            if (!ours || eq == std::string::npos) continue;
            const std::string key = hud::Trimmed(line.substr(0, eq));
            const int value = std::atoi(line.c_str() + eq + 1);
            if (strcasecmp(key.c_str(), "Size") == 0) legacy = value;
            else if (strcasecmp(key.c_str(), "LinkSizes") == 0) linked = value;
            else if (strcasecmp(key.c_str(), "FontStyle") == 0) style = value;
            else if (strcasecmp(key.c_str(), "IconSize") == 0) icon = value;
            else if (strcasecmp(key.c_str(), "ModdedFonts") == 0) moddedSeen = hud::Trimmed(line.substr(eq + 1));
            else for (int i = 0; i < TextGroupCount; ++i)
                if (strcasecmp(key.c_str(), kGroupKeys[i]) == 0) group[i] = value;
        }
        std::fclose(f);
    }
    Settings settings;
    for (int i = 0; i < TextGroupCount; ++i) settings.sizing.values[i] = Percent(group[i] >= 0 ? group[i] : legacy);
    settings.sizing.Link(linked != 0);
    settings.style = Style(style, moddedSet != 0);
    settings.icon = kmrp_icon_percent(icon);
    return settings;
}

Store& Loaded() {
    Store& store = TheStore();
    if (!store.read) {
        store.read = true;
        store.moddedSet = fonts::OverrideFontSet();
        std::string seen;
        store.live = store.saved = ReadFile(store.moddedSet, seen);
        // Fonts in the override not seen before: Modded Font, written at once with their set.
        if (store.moddedSet && strcasecmp(seen.c_str(), SetText(store.moddedSet).c_str()) != 0) {
            store.live.style = Modded;
            if (WriteSettings(store.live)) store.saved = store.live;
        }
    }
    return store;
}

}  // namespace

bool ModdedOffered() { return Loaded().moddedSet != 0; }

Settings& Live() { return Loaded().live; }
Settings& Saved() { return Loaded().saved; }
int FontStyle() { return Live().style; }
int TextSizePercent() { return Live().sizing.values[Menus]; }
int TextSizeForFont(const char* font) { return Live().sizing.values[FontGroup(font)]; }
int IconSizePercent() { return Live().icon; }

// The section written again and everything else in the file left as it is, as hud_sizes.h does.
bool WriteSettings(const Settings& settings) {
    const std::string path = hud::IniPath();
    if (path.empty()) return false;
    std::string body = std::string("[") + kSection + "]\n";
    char value[64];
    std::snprintf(value, sizeof value, "Size=%d\n", settings.sizing.values[Menus]);
    body += value;
    for (int i = 0; i < TextGroupCount; ++i) {
        std::snprintf(value, sizeof value, "%s=%d\n", kGroupKeys[i], settings.sizing.values[i]);
        body += value;
    }
    body += settings.sizing.linked ? "LinkSizes=1\n" : "LinkSizes=0\n";
    std::snprintf(value, sizeof value, "IconSize=%d\nFontStyle=%d\nOriginalFont=1\n", settings.icon, settings.style);
    body += value;
    // The override's fonts this choice was made with (read before Loaded's own write is done).
    if (const std::uint64_t set = TheStore().moddedSet) body += "ModdedFonts=" + SetText(set) + "\n";

    std::string text;
    bool written = false, ours = false;
    if (FILE* f = std::fopen(path.c_str(), "r")) {
        char buffer[1024];
        while (std::fgets(buffer, sizeof buffer, f)) {
            std::string name;
            if (hud::SectionHeader(buffer, name)) {
                ours = strcasecmp(name.c_str(), kSection) == 0;
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

}  // namespace textfit
}  // namespace kmrp
