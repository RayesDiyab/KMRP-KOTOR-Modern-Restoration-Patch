using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;

namespace Kmrp
{
    // The Windows installer's half of InstallPlatform: each step calls the class that did it
    // before the core was split out (2026-10-30), with the same arguments.
    internal static partial class InstallPlatform
    {
        static partial void OnArtPlan(ref int workers, ref int sizes, ref double secondsPerSize)
        {
            workers = ArtPreparation.Workers();
            sizes = ArtPreparation.ExpectedSizes();
            secondsPerSize = ArtPreparation.SecondsPerResolution(workers, ArtPreparation.CacheOnSolidState());
        }

        static partial void OnPrepareArt(string folder, string kpatchResource, string moduleEntry, Action<string> report,
            Action<int, string> progress, InstallClock timing, int from, int to)
        {
            ArtPreparation.Run(folder, kpatchResource, moduleEntry, report, progress, timing, from, to);
        }

        static partial void OnRemoveArtCache(Action<string> report) { ArtPreparation.RemoveCache(report); }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool MoveFileExW(string from, string to, uint flags);

        static partial void OnMoveOver(string from, string to, ref bool moved)
        {
            const uint ReplaceExisting = 1, WriteThrough = 8;
            if (!MoveFileExW(from, to, ReplaceExisting | WriteThrough))
            {
                int code = Marshal.GetLastWin32Error();
                if (code == 5)
                    throw new UnauthorizedAccessException(new Win32Exception(code).Message);
                throw new IOException(new Win32Exception(code).Message);
            }
            moved = true;
        }

        // Windows lets nobody open a running program's file for writing, whichever
        // process has it and whatever its bitness, and this names this folder's copy
        // alone; a game running from another folder is no reason to stop. A virus scanner
        // reading the file refuses the same way, for a moment, so it is tried for as long
        // as FileGuard tries: only a refusal that lasts means the game.
        static partial void OnGameRunning(string executablePath, ref bool running)
        {
            int delay = 60;
            for (int attempt = 1; attempt <= 6; attempt++)
            {
                try
                {
                    using (new FileStream(executablePath, FileMode.Open, FileAccess.Write,
                               FileShare.ReadWrite | FileShare.Delete))
                        running = false;
                    return;
                }
                catch (IOException) { running = true; }
                catch (UnauthorizedAccessException) { running = false; return; }    // read-only, not running
                if (attempt < 6)
                    System.Threading.Thread.Sleep(delay);
                delay *= 2;
            }
        }

        static partial void OnInstallDpi(string executablePath, Action<string> report, ref object state)
        {
            state = DpiCompatibilityOperations.Install(executablePath, report);
        }

        static partial void OnRollbackDpi(object state)
        {
            DpiCompatibilityOperations.Rollback(state as DpiCompatibilityEditState);
        }

        static partial void OnRestoreDpi(string executablePath, Action<string> report)
        {
            DpiCompatibilityOperations.Restore(executablePath, report);
        }

        static partial void OnDriverCompatMissing(ref string missing)
        {
            missing = DriverCompatOperations.MissingImport;
        }

        static partial void OnRemoveOldNvidiaSetting(string executablePath, Action<string> report)
        {
            NvidiaPresentOperations.Restore(executablePath, report);
        }

        static partial void OnHighestRefresh(int[] size, ref int rate)
        {
            rate = size == null ? ResolutionSelection.HighestRefresh() : ResolutionSelection.HighestRefresh(size);
        }
    }
}
