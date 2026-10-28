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
#include <cstdio>
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

// KMRP's own files are in one folder in the game's, KMRP, since 2026-10-20 (the
// maintainer: "we shouldnt clutter the folder like this"): the logs in KMRP\logs, the
// controller's settings as KMRP\controller.ini. Until then they were loose in the game's
// folder; KMRP's installer moves an earlier install's (KmrpFolder in
// src/patcher/KmrpPatcher.cs), and KmrpControllerSettingsPath moves the settings itself
// for a controller patch installed without it.

// `path` set to the log `name` in KMRP\logs, the folders made.
inline bool KmrpLogPath(wchar_t (&path)[MAX_PATH], const wchar_t* name)
{
    if (!KmrpGamePath(path, L"KMRP")) return false;
    CreateDirectoryW(path, nullptr);
    if (wcscat_s(path, L"\\logs")) return false;
    CreateDirectoryW(path, nullptr);
    return !wcscat_s(path, L"\\") && !wcscat_s(path, name);
}

// The log `name` in KMRP\logs opened to append to, or null.
inline FILE* KmrpOpenLog(const wchar_t* name)
{
    wchar_t path[MAX_PATH];
    FILE* f = nullptr;
    if (!KmrpLogPath(path, name) || _wfopen_s(&f, path, L"a")) return nullptr;
    return f;
}

// The same as a handle, shared for reading while it is written, or INVALID_HANDLE_VALUE.
inline HANDLE KmrpAppendLog(const wchar_t* name)
{
    wchar_t path[MAX_PATH];
    if (!KmrpLogPath(path, name)) return INVALID_HANDLE_VALUE;
    return CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
}

// `path` set to the controller's settings, KMRP\controller.ini. The game folder's
// kmrp-controller.ini, where they were until 2026-10-20, is moved there the first time.
inline bool KmrpControllerSettingsPath(wchar_t (&path)[MAX_PATH])
{
    wchar_t old[MAX_PATH];
    if (!KmrpGamePath(path, L"KMRP")) return false;
    CreateDirectoryW(path, nullptr);
    if (wcscat_s(path, L"\\controller.ini")) return false;
    if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES && KmrpGamePath(old, L"kmrp-controller.ini") &&
            GetFileAttributesW(old) != INVALID_FILE_ATTRIBUTES) {
        MoveFileExW(old, path, MOVEFILE_COPY_ALLOWED);
    }
    return true;
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
// (ControllerLogK1, K1NativeJoystick.cpp): the pad's readings, the screens up whenever
// they change (each panel's type, size and active control, and every control of the
// one the pad navigates; LogMenuSnapshotK1), each move the pad makes on a screen and
// from where to what (NavigateFocusK1), and the badges placed again after a screen is
// laid out for another size (K1BadgesLaidOutAgain, vendor/K1XboxControls.cpp).
inline int KmrpDebugLevel()
{
    static const int level = KmrpPatchOption(L"debug-logs", 0);
    return level;
}
