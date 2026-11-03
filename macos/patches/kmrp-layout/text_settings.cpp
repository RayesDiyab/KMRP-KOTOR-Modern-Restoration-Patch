/*
  KMRP for macOS: the Text Size and Font page's choices, read once from swkotor.ini and held here,
  where the fit, the rows and the fonts ask for them. Windows' Initialize and Save
  (src/controller-native/K1TextOptions.cpp). The file is the game's, in its Application Support
  folder (hud_sizes.h says why [KMRP Text] survives the game's own writes); the section is
  Windows', with its keys: Size, MenuSize, BodySize, SmallSize, HudSize, LinkSizes, IconSize,
  FontStyle and OriginalFont. A missing file, section or key is that key's default, and a saved
  FontStyle of 0, the old HD font, reads as HD Font (K1TextOptionsPolicy.h, Style).
*/
#include "text_settings.h"

#include "hud_sizes.h"
#include "text_fit.h"

#include "../../tools/kmrp-iconsize.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <strings.h>

namespace kmrp {
namespace textfit {
namespace {

using namespace KmrpTextOptions;

const char kSection[] = "KMRP Text";
const char* const kGroupKeys[TextGroupCount] = {"MenuSize", "BodySize", "SmallSize", "HudSize"};

struct Store {
    bool read = false;
    Settings live, saved;
};
Store& TheStore() {
    static Store* store = new Store;
    return *store;
}

Settings ReadFile() {
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
            else for (int i = 0; i < TextGroupCount; ++i)
                if (strcasecmp(key.c_str(), kGroupKeys[i]) == 0) group[i] = value;
        }
        std::fclose(f);
    }
    Settings settings;
    for (int i = 0; i < TextGroupCount; ++i) settings.sizing.values[i] = Percent(group[i] >= 0 ? group[i] : legacy);
    settings.sizing.Link(linked != 0);
    settings.style = Style(style);
    settings.icon = kmrp_icon_percent(icon);
    return settings;
}

Store& Loaded() {
    Store& store = TheStore();
    if (!store.read) {
        store.read = true;
        store.live = store.saved = ReadFile();
    }
    return store;
}

}  // namespace

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
