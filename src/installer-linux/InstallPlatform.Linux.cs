using System;
using System.IO;

namespace Kmrp
{
    // The Linux installer's half of InstallPlatform (src/patcher/InstallPlatform.cs). Windows' DPI
    // value, K1DC's check, the NVIDIA setting and the art prebuild through kmrp.dll have no Linux
    // counterpart and stay unimplemented: their calls compile away, and the game makes each size's
    // art the first time it is used. What Linux does answer is where KPM, running under Proton,
    // keeps its settings and how its Windows paths map to Linux folders.
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
