/* Paths for KMRP's C helpers (guiadapt, guiblend, gameart, abilityicons, swoophud).
 *
 * Every path these helpers are given is UTF-8, and every file or folder they open or make
 * goes through here. On Windows the path becomes UTF-16 for _wfopen and _wmkdir, so a game
 * folder or a user name in any script works. Until 2026-10-30 paths came in the system's
 * ANSI code page through plain fopen: a name outside it (a Cyrillic or Chinese user name on
 * a Windows set to a Western language) could not be passed at all, and the module skipped
 * every live layout and every set it would have made, silently. On the Mac paths are UTF-8
 * already and these are the plain calls. */
#ifndef KMRP_PATH_H
#define KMRP_PATH_H

#include <stdio.h>

#ifdef _WIN32
#include <direct.h>
#include <wchar.h>
/* MSVC's way of naming the library; clang and MinGW link kernel32 by default, and a
 * pragma they do not know fails the tests' -Werror builds (Test-GameArt.py). */
#ifdef _MSC_VER
#pragma comment(lib, "kernel32.lib")
#endif
__declspec(dllimport) int __stdcall MultiByteToWideChar(unsigned int code_page, unsigned long flags,
                                                         const char *text, int length, wchar_t *wide, int room);

/* CP_UTF8 (65001), MB_ERR_INVALID_CHARS (8): a path that is not UTF-8 is refused. */
static __inline int kmrp_wide(const char *text, wchar_t *wide, int room) {
    return text && MultiByteToWideChar(65001u, 8u, text, -1, wide, room) > 0;
}

static __inline FILE *kmrp_fopen(const char *path, const char *mode) {
    wchar_t wide[4096], wmode[8];
    return kmrp_wide(path, wide, 4096) && kmrp_wide(mode, wmode, 8) ? _wfopen(wide, wmode) : NULL;
}

static __inline int kmrp_mkdir(const char *path) {
    wchar_t wide[4096];
    return kmrp_wide(path, wide, 4096) ? _wmkdir(wide) : -1;
}
#else
#include <sys/stat.h>
#define kmrp_fopen fopen
#define kmrp_mkdir(path) mkdir(path, 0755)
#endif

#endif
