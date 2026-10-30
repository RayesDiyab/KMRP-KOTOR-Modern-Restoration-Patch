using System;

namespace Kmrp
{
    /// <summary>What an install or restore needs from the system it runs on (2026-10-30).
    ///
    /// The install and restore rules (KpmEdition.cs, InstallCore.cs) are shared by the Windows
    /// installer and the native Linux installer (docs/linux-appimage-installer.md). The steps
    /// below exist only on Windows: the per-user DPI value, K1 Modern Driver Compatibility's
    /// check, removing the NVIDIA present method older KMRP versions set, and making every
    /// display size's art with kmrp.dll before the game first starts; and the display's highest
    /// refresh rate, which each system reads its own way. Each is a partial method:
    /// the Windows installer implements them in InstallPlatform.Windows.cs, calling the classes
    /// that did these steps before the split; a build without that file compiles every call
    /// away, and the art is then made by the game the first time a size is used.</summary>
    internal static partial class InstallPlatform
    {
        static partial void OnArtPlan(ref int workers, ref int sizes, ref double secondsPerSize);
        static partial void OnPrepareArt(string folder, string kpatchResource, string moduleEntry, Action<string> report,
            Action<int, string> progress, InstallClock timing, int from, int to);
        static partial void OnRemoveArtCache(Action<string> report);
        static partial void OnInstallDpi(string executablePath, Action<string> report, ref object state);
        static partial void OnRollbackDpi(object state);
        static partial void OnRestoreDpi(string executablePath, Action<string> report);
        static partial void OnInstallDriverCompat(string executablePath, Action<string> report);
        static partial void OnRestoreDriverCompat(string executablePath, Action<string> report);
        static partial void OnRemoveOldNvidiaSetting(string executablePath, Action<string> report);
        static partial void OnHighestRefresh(int[] size, ref int rate);
        static partial void OnKpmSettingsPath(ref string path);
        static partial void OnLocalPath(ref string path);

        /// <summary>A path a Windows program wrote (KPM's settings), as this system names it: the
        /// same on Windows; under Proton, Wine's drive letters turned into Linux folders.</summary>
        internal static string LocalPath(string path)
        {
            OnLocalPath(ref path);
            return path;
        }

        /// <summary>KOTOR Patch Manager's settings file: PATH, the user's own AppData, on Windows;
        /// on Linux the one in the game's Proton prefix, where KPM runs.</summary>
        internal static string KpmSettingsPath(string path)
        {
            OnKpmSettingsPath(ref path);
            return path;
        }

        /// <summary>The display's highest refresh rate at SIZE (width, height), or at its current
        /// size when SIZE is null; 60 where the system cannot say.</summary>
        internal static int HighestRefresh(int[] size)
        {
            int rate = 60;
            OnHighestRefresh(size, ref rate);
            return rate;
        }

        /// <summary>How the art prebuild will run: its workers, the sizes it makes and the
        /// seconds a size takes; 1, 0 and 0 where there is none.</summary>
        internal static void ArtPlan(out int workers, out int sizes, out double secondsPerSize)
        {
            workers = 1;
            sizes = 0;
            secondsPerSize = 0;
            OnArtPlan(ref workers, ref sizes, ref secondsPerSize);
        }

        internal static void PrepareArt(string folder, string kpatchResource, string moduleEntry, Action<string> report,
            Action<int, string> progress, InstallClock timing, int from, int to)
        {
            OnPrepareArt(folder, kpatchResource, moduleEntry, report, progress, timing, from, to);
        }

        internal static void RemoveArtCache(Action<string> report) { OnRemoveArtCache(report); }

        /// <summary>The DPI value written, or null when nothing was: for RollbackDpi.</summary>
        internal static object InstallDpi(string executablePath, Action<string> report)
        {
            object state = null;
            OnInstallDpi(executablePath, report, ref state);
            return state;
        }

        internal static void RollbackDpi(object state) { OnRollbackDpi(state); }
        internal static void RestoreDpi(string executablePath, Action<string> report) { OnRestoreDpi(executablePath, report); }
        internal static void InstallDriverCompat(string executablePath, Action<string> report) { OnInstallDriverCompat(executablePath, report); }
        internal static void RestoreDriverCompat(string executablePath, Action<string> report) { OnRestoreDriverCompat(executablePath, report); }
        internal static void RemoveOldNvidiaSetting(string executablePath, Action<string> report) { OnRemoveOldNvidiaSetting(executablePath, report); }
    }
}
