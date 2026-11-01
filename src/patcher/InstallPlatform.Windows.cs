using System;
using System.IO;

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

        // Windows lets nobody open a running program's file for writing, whichever
        // process has it and whatever its bitness, and this names this folder's copy
        // alone; a game running from another folder is no reason to stop.
        static partial void OnGameRunning(string executablePath, ref bool running)
        {
            try
            {
                using (new FileStream(executablePath, FileMode.Open, FileAccess.Write,
                           FileShare.ReadWrite | FileShare.Delete))
                    running = false;
            }
            catch (IOException) { running = true; }
            catch (UnauthorizedAccessException) { running = false; }    // read-only, not running
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
