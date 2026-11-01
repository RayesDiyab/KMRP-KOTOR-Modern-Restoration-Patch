#pragma once
// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll): giving a
// folder to the game's resource manager. Two copies until 2026-11-01, and the controller's
// lacked KMRP's fix of 2026-10-30 for a user name outside the code page: its folder was then
// never given, and its preparation repeated on every resource lookup (audit THR-2).
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <string>

// A path in the system's code page as it is, or "" when it has a character the page lacks.
inline std::string KmrpCodePagePathK1(const std::wstring& path)
{
    char text[MAX_PATH]; BOOL substituted = FALSE;
    if (!WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, path.c_str(), -1, text, MAX_PATH, nullptr, &substituted) ||
        substituted) return std::string();
    return text;
}

// A folder's path for the game's resource manager, which takes the system's code page; "" when
// even the short form cannot be written. A path with a character the code page lacks (a
// Cyrillic or Chinese user name on a Windows set to a Western language) is written with the 8.3
// short name Windows keeps for folders on the system drive (C:\Users\5D6F~1\...), of its
// longest part that exists, the rest as it is. Other drives often keep no short names
// (checked on the test PC 2026-10-30: C: has them, E: does not).
inline std::string KmrpNarrowPathK1(const std::wstring& path)
{
    std::string text = KmrpCodePagePathK1(path);
    if (!text.empty() || path.empty()) return text;
    std::wstring head = path, tail;
    for (;;) {
        const DWORD attributes = GetFileAttributesW(head.c_str());
        if (attributes != INVALID_FILE_ATTRIBUTES) break;
        const size_t slash = head.find_last_of(L"\\/");
        if (slash == std::wstring::npos || slash == 0) return std::string();
        tail = head.substr(slash) + tail;
        head.resize(slash);
    }
    const DWORD length = GetShortPathNameW(head.c_str(), nullptr, 0);
    std::wstring shortened(length ? length : 1, L'\0');
    if (!length || !GetShortPathNameW(head.c_str(), &shortened[0], length)) return std::string();
    shortened.resize(wcslen(shortened.c_str()));
    return KmrpCodePagePathK1(shortened + tail);
}

#ifndef KMRP_RESOURCE_FOLDER_TEST
// CExoAliasList::ResolveFileName reads the text before ':' as an alias, drive letters
// included, so an absolute Windows path is never passed: the folder gets a private alias and
// is given through it. The game searches the folder given last first
// (CExoResMan::AddKeyTable, 0x00406E20).
inline bool KmrpGiveFolderK1(const std::string& path, const std::string& alias)
{
    void* manager = *reinterpret_cast<void**>(0x7A39E8);
    void* base = *reinterpret_cast<void**>(0x7A39E0);
    if (!manager || !base || path.empty()) return false;
    void* aliases = *reinterpret_cast<void**>(static_cast<unsigned char*>(base) + 0x0C);
    if (!aliases) return false;
    void* aliasName[2]{}; void* aliasPath[2]{};
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasName, alias.c_str());
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(aliasPath, path.c_str());
    reinterpret_cast<void(__thiscall*)(void*, void*, void*)>(0x5E6880)(aliases, aliasName, aliasPath);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasPath);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(aliasName);
    void* name[2]{};
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(name, (alias + ":").c_str());
    const int result = reinterpret_cast<int(__thiscall*)(void*, void*)>(0x408800)(manager, name);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(name);
    return result != 0;
}

// A folder given before whose files changed is listed anew. `name` is "ALIAS:".
inline bool KmrpRelistFolderK1(const std::string& name)
{
    void* manager = *reinterpret_cast<void**>(0x7A39E8);
    if (!manager || name.empty()) return false;
    void* text[2]{};
    reinterpret_cast<void(__thiscall*)(void*, const char*)>(0x5E5A90)(text, name.c_str());
    const int result = reinterpret_cast<int(__thiscall*)(void*, void*)>(0x4088E0)(manager, text);
    reinterpret_cast<void(__thiscall*)(void*)>(0x5E5C20)(text);
    return result != 0;
}
#endif
