using System;
using System.IO;

namespace Kmrp
{
    // The Linux installer's half of InstallPlatform (src/patcher/InstallPlatform.cs). Windows' DPI
    // value, K1DC's Windows 7 check (Proton's Wine has every function its module needs) and the
    // NVIDIA setting have no Linux counterpart and stay unimplemented: their calls compile away.
    // What Linux does answer is where KPM, running under Proton, keeps its settings, how its
    // Windows paths map to Linux folders, whether the game is running, the art made ahead under
    // Proton (ProtonArt.cs, since 2026-11-03), and where that art is to remove it.
    internal static partial class InstallPlatform
    {
        /// <summary>The game folder the command works on, set before the core is called.</summary>
        internal static string GameFolder;

        // Steam keeps a game's Proton prefix in its library's steamapps/compatdata/<app id>/pfx;
        // KOTOR's app id is 32370. The game folder is steamapps/common/<name>.
        private const string AppId = "32370";

        /// <summary>The game's Proton prefix (its pfx folder), or null outside a Steam library.</summary>
        internal static string Prefix()
        {
            if (string.IsNullOrEmpty(GameFolder))
                return null;
            DirectoryInfo common = Directory.GetParent(Path.GetFullPath(GameFolder).TrimEnd('/'));
            DirectoryInfo steamapps = common == null ? null : common.Parent;
            if (common == null || steamapps == null || !common.Name.Equals("common", StringComparison.OrdinalIgnoreCase))
                return null;
            string prefix = Path.Combine(steamapps.FullName, "compatdata", AppId, "pfx");
            return Directory.Exists(prefix) ? prefix : null;
        }

        static partial void OnKpmSettingsPath(ref string path)
        {
            string prefix = Prefix();
            path = prefix == null ? "" : Path.Combine(prefix, "drive_c", "users", "steamuser", "AppData", "Roaming",
                "KPatchLauncher", "settings.json");
        }

        // Wine names the process after the program. Any KOTOR running stops the install: nothing
        // here says which folder it came from.
        static partial void OnGameRunning(string executablePath, ref bool running)
        {
            running = System.Diagnostics.Process.GetProcessesByName("swkotor.exe").Length > 0;
        }

        // The game's art cache, in the prefix as KpmSettingsPath's file is. %LOCALAPPDATA% under
        // Proton; the same folder Windows' restore empties (ArtPreparation.RemoveCache).
        static partial void OnRemoveArtCache(Action<string> report)
        {
            string prefix = Prefix();
            if (prefix == null)
                return;
            string cache = Path.Combine(prefix, "drive_c", "users", "steamuser", "AppData", "Local", "KMRP", "cache");
            if (!Directory.Exists(cache))
                return;
            Directory.Delete(cache, true);
            report?.Invoke("Removed KMRP's art cache from the game's Proton prefix.");
        }

        // The art made ahead under Proton, as the Windows installer makes it (ProtonArt.cs). The
        // time it takes is Windows' measure for an SSD, a first guess under Proton.
        static partial void OnArtPlan(ref int workers, ref int sizes, ref double secondsPerSize)
        {
            workers = ProtonArt.Workers();
            int covered = 0;
            foreach (int[] size in LinuxDisplay.Sizes())
                if (ResolutionCatalog.Covers(size[0], size[1]))
                    ++covered;
            sizes = covered > 0 ? covered : 12;
            secondsPerSize = 80.0 / 19 / workers * 1.5;
        }

        static partial void OnPrepareArt(string folder, string kpatchResource, string moduleEntry, Action<string> report,
            Action<int, string> progress, InstallClock timing, int from, int to)
        {
            if (timing != null)
                timing.ArtBegun();
            ProtonArt.Run(folder, report, progress, from, to);
        }

        static partial void OnMoveOver(string from, string to, ref bool moved)
        {
            File.Move(from, to, true);
            moved = true;
        }

        static partial void OnHighestRefresh(int[] size, ref int rate)
        {
            rate = LinuxDisplay.HighestRefresh(size);
        }

        static partial void OnLocalPath(ref string path)
        {
            if (string.IsNullOrEmpty(path) || path.Length < 3 || path[1] != ':' || (path[2] != '\\' && path[2] != '/'))
                return;
            string rest = path.Substring(3).Replace('\\', '/');
            char drive = char.ToUpperInvariant(path[0]);
            if (drive == 'Z')
            {
                path = "/" + rest;     // Wine's Z: is the Linux root
                return;
            }
            string prefix = Prefix();
            if (prefix != null && drive == 'C')
                path = Path.Combine(prefix, "drive_c", rest);
        }
    }
}
