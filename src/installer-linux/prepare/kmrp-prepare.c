/* KMRP's art made ahead, run by the Linux installer under Proton (issue 76's open question:
   docs/linux-appimage-installer.md, section 6).

   On Windows the installer does this itself (ArtPreparation.cs): workers, each a copy of the
   installer, load kmrp.dll with KMRP_PREPARE set, so its DllMain leaves the process alone, and
   call its export KmrpPrepareAssets with the game's folder and their share of the display's
   sizes. The Linux installer cannot load a 32-bit Windows DLL, and a Proton prefix usually has
   no .NET Framework to run the Windows installer with, so this small program does the same
   work there, inside the game's own prefix, where the game reads the cache
   (%LOCALAPPDATA%\KMRP\cache). Without it the game made the art at its first start, which was
   the long first launch the maintainer saw under SteamOS (2026-11-03).

       kmrp-prepare.exe <kmrp.dll> <game folder> <workers> <progress folder>
           starts the workers, waits
       kmrp-prepare.exe <kmrp.dll> <game folder> <progress folder> <share> <of>
           one worker

   Each worker appends its lines to share-<share>.txt in the progress folder, which the Linux
   installer reads as they come (ProtonArt.cs): "step <done> <total> <width> <height>" before
   each part and "made <sizes>" at the end, the lines the Windows installer's workers write
   (ArtProgress.cs), or "failed <why>". The program is linked for the windowed subsystem: built
   as a console program, Proton gave it a console window of its own, which showed the work and
   took its standard output, so the installer saw no progress until the end (the maintainer,
   SteamOS, 2026-11-03). The exit code is 0 when every worker made its share. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef int(__stdcall* PrepareStep)(int done, int total, int width, int height, void* context);
typedef int(__cdecl* PrepareAssets)(const wchar_t* game, int share, int shares, PrepareStep step, void* context);

static HANDLE g_progress = INVALID_HANDLE_VALUE;

static void Line(const char* text)
{
    DWORD written = 0;
    WriteFile(g_progress, text, (DWORD)strlen(text), &written, NULL);    /* one write a line */
}

static int __stdcall Step(int done, int total, int width, int height, void* context)
{
    char text[96];
    (void)context;
    _snprintf_s(text, sizeof text, _TRUNCATE, "step %d %d %d %d\n", done, total, width, height);
    Line(text);
    return 0;
}

static int Worker(const wchar_t* module, const wchar_t* game, const wchar_t* folder, int share, int shares)
{
    wchar_t path[MAX_PATH + 32];
    char text[64];
    HMODULE library;
    PrepareAssets prepare;
    int made;
    _snwprintf_s(path, sizeof path / sizeof path[0], _TRUNCATE, L"%s\\share-%d.txt", folder, share);
    g_progress = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (g_progress == INVALID_HANDLE_VALUE) return 4;
    SetEnvironmentVariableW(L"KMRP_PREPARE", L"1");
    library = LoadLibraryExW(module, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    SetEnvironmentVariableW(L"KMRP_PREPARE", NULL);
    if (!library) {
        _snprintf_s(text, sizeof text, _TRUNCATE, "failed load %lu\n", GetLastError());
        Line(text);
        return 2;
    }
    prepare = (PrepareAssets)GetProcAddress(library, "KmrpPrepareAssets");
    if (!prepare) {
        Line("failed export\n");
        return 3;
    }
    made = prepare(game, share, shares, Step, NULL);
    _snprintf_s(text, sizeof text, _TRUNCATE, "made %d\n", made);
    Line(text);
    FreeLibrary(library);
    CloseHandle(g_progress);
    return made < 0 ? 1 : 0;
}

static int Workers(const wchar_t* self, const wchar_t* module, const wchar_t* game, const wchar_t* folder, int count)
{
    HANDLE processes[MAXIMUM_WAIT_OBJECTS];
    int started = 0, failed = 0, i;
    for (i = 0; i < count && i < MAXIMUM_WAIT_OBJECTS; i++) {
        wchar_t command[4 * MAX_PATH + 64];
        STARTUPINFOW startup;
        PROCESS_INFORMATION process;
        ZeroMemory(&startup, sizeof startup);
        startup.cb = sizeof startup;
        _snwprintf_s(command, sizeof command / sizeof command[0], _TRUNCATE, L"\"%s\" \"%s\" \"%s\" \"%s\" %d %d",
                     self, module, game, folder, i, count);
        if (!CreateProcessW(self, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &startup, &process)) {
            ++failed;
            continue;
        }
        CloseHandle(process.hThread);
        processes[started++] = process.hProcess;
    }
    if (started) WaitForMultipleObjects((DWORD)started, processes, TRUE, INFINITE);
    for (i = 0; i < started; i++) {
        DWORD code = 1;
        GetExitCodeProcess(processes[i], &code);
        if (code != 0) ++failed;
        CloseHandle(processes[i]);
    }
    return failed ? 1 : 0;
}

/* wmain, through /ENTRY:wmainCRTStartup, so the arguments come parsed with no console. */
int wmain(int argc, wchar_t** argv)
{
    wchar_t self[MAX_PATH];
    if (argc == 6) return Worker(argv[1], argv[2], argv[3], _wtoi(argv[4]), _wtoi(argv[5]));
    if (argc != 5 || !GetModuleFileNameW(NULL, self, MAX_PATH)) return 64;
    return Workers(self, argv[1], argv[2], argv[4], max(1, _wtoi(argv[3])));
}
