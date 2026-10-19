// Controller remapping at run time: the layout kept in the controller's settings file,
// KMRP\controller.ini in the game folder (KmrpControllerSettingsPath, KmrpOptions.h; the
// game folder's kmrp-controller.ini until 2026-10-20), and the translation of the pad's
// buttons in the world (K1ButtonRemapPolicy.h). The controller patch works without KMRP,
// so the layout lives in its own settings file, as [Hud] Style does (K1XboxHud.cpp).
#include "K1ButtonRemap.h"
#include "KmrpOptions.h"
#include <windows.h>
#include <cstdio>
#include <cwchar>

namespace {
using namespace KmrpRemap;
constexpr const wchar_t* kSection = L"Controller Remap";
Mapping g_saved;
bool g_loaded = false;
Translator g_translator;

// The names here are ASCII (K1ButtonRemapPolicy.h), so widening is a copy.
struct Wide {
    wchar_t text[32] = {};
    explicit Wide(const char* ascii)
    {
        for (int i = 0; ascii && ascii[i] && i < 31; ++i) text[i] = static_cast<wchar_t>(ascii[i]);
    }
};

void Load()
{
    g_loaded = true;
    g_saved = Mapping{};
    wchar_t path[MAX_PATH];
    if (!KmrpControllerSettingsPath(path)) return;
    wchar_t layout[16] = {};
    GetPrivateProfileStringW(kSection, Wide(LayoutKey).text, L"", layout, 16, path);
    if (_wcsicmp(layout, Wide(LayoutName).text) != 0) return;
    Mapping read;
    for (int a = 0; a < ButtonCount; ++a) {
        wchar_t value[16] = {};
        GetPrivateProfileStringW(kSection, Wide(ActionKeys[a]).text, Wide(ButtonNames[a]).text, value, 16, path);
        char ascii[16] = {};
        for (int i = 0; value[i] && i < 15; ++i) ascii[i] = value[i] < 128 ? static_cast<char>(value[i]) : '?';
        read.button[a] = ButtonByName(ascii);
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
    wchar_t path[MAX_PATH];
    if (!KmrpControllerSettingsPath(path)) return false;
    // The section as a whole, so no key of the old layout's is left behind.
    WritePrivateProfileStringW(kSection, nullptr, nullptr, path);
    if (!WritePrivateProfileStringW(kSection, Wide(LayoutKey).text, Wide(LayoutName).text, path)) return false;
    for (int a = 0; a < ButtonCount; ++a)
        if (!WritePrivateProfileStringW(kSection, Wide(ActionKeys[a]).text, Wide(ButtonNames[mapping.button[a]]).text,
                                        path))
            return false;
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
