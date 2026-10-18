// Controller remapping at run time: the layout kept in kmrp-controller.ini beside the
// game, and the translation of the pad's buttons in the world (K1ButtonRemapPolicy.h).
// The controller patch works without KMRP, so the layout lives in its own settings
// file, as [Hud] Style does (K1XboxHud.cpp).
#include "K1ButtonRemap.h"
#include <windows.h>
#include <cstdio>
#include <cwchar>

namespace {
using namespace KmrpRemap;
constexpr const char* kSection = "Controller Remap";
Mapping g_saved;
bool g_loaded = false;
Translator g_translator;

bool SettingsPath(char (&path)[MAX_PATH])
{
    const DWORD n = GetModuleFileNameA(nullptr, path, MAX_PATH);
    char* slash = n && n < MAX_PATH ? std::strrchr(path, '\\') : nullptr;
    return slash && !strcpy_s(slash + 1, MAX_PATH - (slash + 1 - path), "kmrp-controller.ini");
}

void Load()
{
    g_loaded = true;
    g_saved = Mapping{};
    char path[MAX_PATH];
    if (!SettingsPath(path)) return;
    Mapping read;
    for (int a = 0; a < ButtonCount; ++a) {
        char value[16] = {};
        GetPrivateProfileStringA(kSection, ActionKeys[a], ButtonNames[a], value, sizeof value, path);
        read.button[a] = ButtonByName(value);
    }
    // A layout that is not complete (edited by hand, or from another version) is not
    // used: the default is, and the screen opens on it.
    if (read.Complete()) g_saved = read;
}
}  // namespace

const Mapping& KmrpRemapSavedK1()
{
    if (!g_loaded) Load();
    return g_saved;
}

bool KmrpRemapSaveK1(const Mapping& mapping)
{
    if (!mapping.Complete()) return false;
    char path[MAX_PATH];
    if (!SettingsPath(path)) return false;
    for (int a = 0; a < ButtonCount; ++a)
        if (!WritePrivateProfileStringA(kSection, ActionKeys[a], ButtonNames[mapping.button[a]], path)) return false;
    g_saved = mapping;
    g_loaded = true;
    return true;
}

std::uint16_t KmrpRemapButtonsK1(std::uint16_t pad, bool world)
{
    return g_translator.Apply(pad, world, KmrpRemapSavedK1());
}

void KmrpRemapGlyphK1(int action, char family, char (&resref)[16])
{
    std::memset(resref, 0, sizeof resref);
    const Mapping& m = KmrpRemapSavedK1();
    int button = action >= 0 && action < ButtonCount ? m.button[action] : None;
    if (button < 0) button = action >= 0 && action < ButtonCount ? action : A;
    sprintf_s(resref, "kmr%crm%s", family, GlyphCodes[button]);
}
