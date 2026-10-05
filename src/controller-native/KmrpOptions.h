#pragma once
// KMRP's patch options, as the running module reads them.
//
// KOTOR Patch Manager with patch options, and KMRP's installer, record the values a
// patch was applied with in the game folder as configs\<patch id>.ini, section
// [Patch Options], one key per option, a toggle as 1 or 0. For KMRP that is
// configs\kmrp.ini:
//
//   [Patch Options]
//   controller=1
//   map-notes=1
//   debug-logs=0
//
// A manager without options (0.7.1) writes no file and installs every hook, which is
// every option at its default; so a missing file, section or key is the default.
// Each value is read once, the first time it is asked for.
#include <windows.h>
#include <cwchar>

inline int KmrpPatchOption(const wchar_t* option, int fallback)
{
    wchar_t path[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, path, MAX_PATH);
    wchar_t* slash = n && n < MAX_PATH ? std::wcsrchr(path, L'\\') : nullptr;
    // The standalone controller patch is its own patch, "kmrp-controller", with its
    // own file.
#ifdef KMRP_CONTROLLER_STANDALONE
    const wchar_t* file = L"configs\\kmrp-controller.ini";
#else
    const wchar_t* file = L"configs\\kmrp.ini";
#endif
    if (!slash || wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), file)) return fallback;
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
