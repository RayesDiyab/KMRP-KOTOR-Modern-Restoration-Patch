#pragma once
// Old per-launch folders in %TEMP%, for the two modules that once made them
// (K1RuntimeAssets.cpp, K1ControllerStandalone.cpp; audit S-8). Needs <windows.h>.
#include <cwchar>
#include <string>

// Each launch made its own folder, and nothing else would ever remove one: 63 had collected
// in %TEMP% by 2026-10-04, 5.4 GB. A folder is a module's when it matches `pattern`, the name
// GetTempFileNameW gave it, and holds `marker`. It is in use while its game holds the lock
// beside it (`lockSuffix`), which cannot be deleted then; one from before the lock existed has
// none and is taken as stale. Only plain files directly inside are removed, as neither module
// makes a subfolder, so a folder that has one is left alone. `extra`, when given, is a suffix of
// one more file beside the folder to remove with it.
inline void KmrpRemoveStaleCaches(const std::wstring& temp, const wchar_t* pattern, const std::wstring& marker,
                                  const wchar_t* lockSuffix, const wchar_t* extra = nullptr)
{
    WIN32_FIND_DATAW found{};
    HANDLE search = FindFirstFileW((temp + pattern).c_str(), &found);
    if (search == INVALID_HANDLE_VALUE) return;
    do {
        if (!(found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
            (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) continue;
        const std::wstring directory = temp + found.cFileName;
        if (GetFileAttributesW((directory + L"\\" + marker).c_str()) == INVALID_FILE_ATTRIBUTES) continue;
        const std::wstring lock = directory + lockSuffix;
        if (GetFileAttributesW(lock.c_str()) != INVALID_FILE_ATTRIBUTES && !DeleteFileW(lock.c_str())) continue;
        WIN32_FIND_DATAW file{};
        HANDLE files = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (files == INVALID_HANDLE_VALUE) continue;
        bool plain = true;
        do {
            if (!wcscmp(file.cFileName, L".") || !wcscmp(file.cFileName, L"..")) continue;
            if (file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { plain = false; break; }
        } while (FindNextFileW(files, &file));
        FindClose(files);
        if (!plain) continue;
        files = FindFirstFileW((directory + L"\\*").c_str(), &file);
        if (files == INVALID_HANDLE_VALUE) continue;
        do {
            if (!(file.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
                DeleteFileW((directory + L"\\" + file.cFileName).c_str());
        } while (FindNextFileW(files, &file));
        FindClose(files);
        RemoveDirectoryW(directory.c_str());
        if (extra) DeleteFileW((directory + extra).c_str());
    } while (FindNextFileW(search, &found));
    FindClose(search);
}
