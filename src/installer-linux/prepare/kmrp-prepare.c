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

       kmrp-prepare.exe <kmrp.dll> <game folder> <workers>      starts the workers, waits
       kmrp-prepare.exe <kmrp.dll> <game folder> <share> <of>   one worker

   Every worker writes "step <share> <done> <total> <width> <height>" lines as it goes and
   "made <share> <sizes>" at the end, to the standard output it was started with, which the
   Linux installer reads. The exit code is 0 when every worker made its share. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef int(__stdcall* PrepareStep)(int done, int total, int width, int height, void* context);
typedef int(__cdecl* PrepareAssets)(const wchar_t* game, int share, int shares, PrepareStep step, void* context);

static HANDLE g_output;
static int g_share;

static void Line(const char* text)
{
    DWORD written = 0;
    WriteFile(g_output, text, (DWORD)strlen(text), &written, NULL);    /* one write a line */
}

static int __stdcall Step(int done, int total, int width, int height, void* context)
{
    char text[96];
    (void)context;
    _snprintf_s(text, sizeof text, _TRUNCATE, "step %d %d %d %d %d\n", g_share, done, total, width, height);
    Line(text);
    return 0;
}

static int Worker(const wchar_t* module, const wchar_t* game, int share, int shares)
{
    char text[64];
    HMODULE library;
    PrepareAssets prepare;
    int made;
    HANDLE nul;
    g_share = share;
    g_output = GetStdHandle(STD_OUTPUT_HANDLE);
    /* The module's helpers print to standard output through its own C runtime, which could
       cut a progress line in two: they get NUL, as on Windows. */
    nul = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (nul != INVALID_HANDLE_VALUE) SetStdHandle(STD_OUTPUT_HANDLE, nul);
    SetEnvironmentVariableW(L"KMRP_PREPARE", L"1");
    library = LoadLibraryExW(module, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    SetEnvironmentVariableW(L"KMRP_PREPARE", NULL);
    if (!library) {
        _snprintf_s(text, sizeof text, _TRUNCATE, "failed %d load %lu\n", share, GetLastError());
        Line(text);
        return 2;
    }
    prepare = (PrepareAssets)GetProcAddress(library, "KmrpPrepareAssets");
    if (!prepare) {
        _snprintf_s(text, sizeof text, _TRUNCATE, "failed %d export\n", share);
        Line(text);
        return 3;
    }
    made = prepare(game, share, shares, Step, NULL);
    _snprintf_s(text, sizeof text, _TRUNCATE, "made %d %d\n", share, made);
    Line(text);
    FreeLibrary(library);
    return made < 0 ? 1 : 0;
}

static int Workers(const wchar_t* self, const wchar_t* module, const wchar_t* game, int count)
{
    HANDLE processes[MAXIMUM_WAIT_OBJECTS];
    int started = 0, failed = 0, i;
    for (i = 0; i < count && i < MAXIMUM_WAIT_OBJECTS; i++) {
        wchar_t command[3 * MAX_PATH + 64];
        STARTUPINFOW startup;
        PROCESS_INFORMATION process;
        ZeroMemory(&startup, sizeof startup);
        startup.cb = sizeof startup;
        startup.dwFlags = STARTF_USESTDHANDLES;
        startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
        startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
        startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        _snwprintf_s(command, sizeof command / sizeof command[0], _TRUNCATE, L"\"%s\" \"%s\" \"%s\" %d %d",
                     self, module, game, i, count);
        if (!CreateProcessW(self, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process)) {
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

int wmain(int argc, wchar_t** argv)
{
    wchar_t self[MAX_PATH];
    if (argc == 5) return Worker(argv[1], argv[2], _wtoi(argv[3]), _wtoi(argv[4]));
    if (argc != 4 || !GetModuleFileNameW(NULL, self, MAX_PATH)) {
        fputs("usage: kmrp-prepare.exe <kmrp.dll> <game folder> <workers>\n", stderr);
        return 64;
    }
    return Workers(self, argv[1], argv[2], max(1, _wtoi(argv[3])));
}
