using System;

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

        static partial void OnInstallDriverCompat(string executablePath, Action<string> report)
        {
            DriverCompatOperations.Install(executablePath, report);
        }

        static partial void OnRestoreDriverCompat(string executablePath, Action<string> report)
        {
            DriverCompatOperations.Restore(executablePath, report);
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
