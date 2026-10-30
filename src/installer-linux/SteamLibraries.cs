using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>KOTOR's folders in the user's Steam libraries on Linux (issue 76).
    ///
    /// Steam lists its libraries in steamapps/libraryfolders.vdf under its own folder: native
    /// Steam in ~/.local/share/Steam (with ~/.steam/steam a link to it), the Flatpak in
    /// ~/.var/app/com.valvesoftware.Steam/.local/share/Steam, Debian's old package in
    /// ~/.steam/debian-installation. A library holds a game when its steamapps folder has
    /// appmanifest_32370.acf; the game is then in steamapps/common/&lt;installdir&gt;, the folder
    /// the manifest names. A folder found twice (through a link) is listed once.</summary>
    internal static class SteamLibraries
    {
        private const string AppId = "32370";

        internal static List<string> KotorFolders(string home)
        {
            List<string> found = new List<string>();
            HashSet<string> roots = new HashSet<string>(StringComparer.Ordinal);
            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (string steam in new[] {
                         Path.Combine(home, ".local", "share", "Steam"),
                         Path.Combine(home, ".steam", "steam"),
                         Path.Combine(home, ".steam", "debian-installation"),
                         Path.Combine(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam") })
            {
                // ~/.steam/steam is normally a link to ~/.local/share/Steam: one Steam, read once.
                if (!Directory.Exists(steam) || !roots.Add(RealPath(steam)))
                    continue;
                foreach (string library in Libraries(steam))
                {
                    string game = GameIn(library);
                    if (game != null && seen.Add(RealPath(game)))
                        found.Add(game);
                }
            }
            return found;
        }

        /// <summary>The library folders Steam lists in STEAM's libraryfolders.vdf, STEAM itself
        /// first.</summary>
        internal static List<string> Libraries(string steam)
        {
            List<string> libraries = new List<string>();
            if (Directory.Exists(Path.Combine(steam, "steamapps")))
                libraries.Add(steam);
            string vdf = Path.Combine(steam, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(vdf))
                return libraries;
            foreach (Match m in Regex.Matches(File.ReadAllText(vdf), "\"path\"\\s+\"((?:[^\"\\\\]|\\\\.)*)\""))
            {
                string path = m.Groups[1].Value.Replace("\\\\", "\\");
                if (path.Length > 0 && !libraries.Contains(path))
                    libraries.Add(path);
            }
            return libraries;
        }

        /// <summary>KOTOR's folder in LIBRARY, or null when the library does not hold it.</summary>
        internal static string GameIn(string library)
        {
            string manifest = Path.Combine(library, "steamapps", "appmanifest_" + AppId + ".acf");
            if (!File.Exists(manifest))
                return null;
            Match m = Regex.Match(File.ReadAllText(manifest), "\"installdir\"\\s+\"([^\"]+)\"");
            if (!m.Success)
                return null;
            string game = Path.Combine(library, "steamapps", "common", m.Groups[1].Value);
            return File.Exists(Path.Combine(game, "swkotor.exe")) ? game : null;
        }

        private static string RealPath(string path)
        {
            try
            {
                FileSystemInfo target = new DirectoryInfo(path).ResolveLinkTarget(true);
                return target != null ? target.FullName : Path.GetFullPath(path);
            }
            catch { return Path.GetFullPath(path); }
        }
    }
}
