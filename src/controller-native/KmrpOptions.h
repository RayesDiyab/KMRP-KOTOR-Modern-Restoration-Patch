#pragma once
// KMRP's patch options, as the running module reads them.
//
// KOTOR Patch Manager with patch options, and KMRP's installer, record the values a
// patch was applied with in the game folder as configs\<patch id>.ini, section
// [Patch Options], one key per option, a toggle as 1 or 0. For KMRP that is
// configs\kmrp.ini:
//
//   [Patch Options]
//   map-notes=1
//   hd-icons=1
//   debug-logs=0
//
// A manager without options (0.7.1) writes no file and installs every hook, which is
// every option at its default; so a missing file, section or key is the default.
// Each value is read once, the first time it is asked for.
#include <windows.h>
#include <cwchar>

// The game's folder: the running program's, or the one named here when KMRP's installer
// loads the module to make its art before the game first starts (KmrpPrepareAssets,
// K1RuntimeEngine.cpp; the running program is then the installer).
inline wchar_t* KmrpGameFolderNamed()
{
    static wchar_t folder[MAX_PATH];
    return folder;
}

inline bool KmrpGameFolder(wchar_t (&path)[MAX_PATH])
{
    if (*KmrpGameFolderNamed()) return !wcscpy_s(path, KmrpGameFolderNamed());
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? std::wcsrchr(path, L'\\') : nullptr;
    if (!slash) return false;
    *slash = 0;
    return true;
}

// `path` set to the file `name` in the game's folder.
inline bool KmrpGamePath(wchar_t (&path)[MAX_PATH], const wchar_t* name)
{
    return KmrpGameFolder(path) && !wcscat_s(path, L"\\") && !wcscat_s(path, name);
}

inline int KmrpPatchOption(const wchar_t* option, int fallback)
{
    wchar_t path[MAX_PATH];
    // The standalone controller patch is its own patch, "kmrp-controller", with its
    // own file.
#ifdef KMRP_CONTROLLER_STANDALONE
    const wchar_t* file = L"configs\\kmrp-controller.ini";
#else
    const wchar_t* file = L"configs\\kmrp.ini";
#endif
    if (!KmrpGamePath(path, file)) return fallback;
    return static_cast<int>(GetPrivateProfileIntW(L"Patch Options", option, fallback, path));
}

// The diagnostic logs (kmrp-native-preview.log, kmrp-layout-lifecycle.log,
// kmrp-confirm-focus.log, kmrp-native-joystick.log and the progress lines of
// kmrp-kpm.log) are written only with the debug-logs option on. Errors and warnings
// in kmrp-kpm.log are written regardless: that file then exists only when something
// went wrong.
inline bool KmrpDebugLogs()
{
    static const bool on = KmrpPatchOption(L"debug-logs", 0) != 0;
    return on;
}
// The option's number: 1 is what the installer's switch writes. 2, written by hand,
// adds the controller's frame-by-frame lines to kmrp-controller-events.log
// (ControllerLogK1, K1NativeJoystick.cpp).
inline int KmrpDebugLevel()
{
    static const int level = KmrpPatchOption(L"debug-logs", 0);
    return level;
}
