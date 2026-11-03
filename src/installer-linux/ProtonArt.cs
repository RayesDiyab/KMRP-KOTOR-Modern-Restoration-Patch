using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;

namespace Kmrp
{
    /// <summary>KMRP's art made ahead under Proton, as the Windows installer makes it
    /// (ArtPreparation.cs): every size the display offers, into the cache in the game's own
    /// prefix (%LOCALAPPDATA%\KMRP\cache), so the game starts without making it. Until
    /// 2026-11-03 the Linux installer left it to the game, whose first start was then long
    /// (the maintainer, SteamOS: "on linux its instant but it takes longer to launch the game").
    ///
    /// The work is kmrp-prepare.exe's (src/installer-linux/prepare), a 32-bit Windows program
    /// with no .NET, which loads the installed patches\kmrp.dll and calls its KmrpPrepareAssets,
    /// started with the Proton the game last ran with (`proton run`). Anything missing, the
    /// prefix, that Proton, or Steam's own folder, leaves the art to the game, as before.</summary>
    internal static class ProtonArt
    {
        private const string Worker = "kmrp-prepare.exe";

        /// <summary>Half the processor's threads, at most six, as on Windows.</summary>
        internal static int Workers()
        {
            return Math.Max(1, Math.Min(6, Environment.ProcessorCount / 2));
        }

        internal static void Run(string folder, Action<string> report, Action<int, string> progress, int from, int to)
        {
            string prefix = InstallPlatform.Prefix();
            string compat = prefix == null ? null : Path.GetDirectoryName(prefix);
            string proton = compat == null ? null : Proton(compat);
            string steam = SteamRoot();
            string module = Path.Combine(folder, "patches", "kmrp.dll");
            if (prefix == null || proton == null || steam == null || !File.Exists(module))
            {
                report?.Invoke("KMRP's interface was not made ahead (" + (prefix == null ? "no Proton prefix for the game yet: start it once from Steam"
                    : proton == null ? "the Proton the game runs with was not found" : steam == null ? "Steam's folder was not found"
                    : "patches/kmrp.dll is missing") + "); the game makes it when it first starts.");
                return;
            }
            string work = Path.Combine(Path.GetTempPath(), "KMRP-prepare-" + Environment.ProcessId.ToString(CultureInfo.InvariantCulture));
            Directory.CreateDirectory(work);
            string exe = Path.Combine(work, Worker);
            try
            {
                using (Stream source = Assembly.GetExecutingAssembly().GetManifestResourceStream(Worker))
                {
                    if (source == null)
                    {
                        report?.Invoke("KMRP's interface was not made ahead (this installer lacks " + Worker + "); the game makes it when it first starts.");
                        return;
                    }
                    using (FileStream target = File.Create(exe))
                        source.CopyTo(target);
                }
                Make(proton, steam, compat, exe, module, folder, report, progress, from, to);
            }
            finally
            {
                try { Directory.Delete(work, true); }
                catch { }
            }
        }

        private static void Make(string proton, string steam, string compat, string exe, string module, string folder,
            Action<string> report, Action<int, string> progress, int from, int to)
        {
            int workers = Workers();
            ProcessStartInfo start = new ProcessStartInfo(Path.Combine(proton, "proton"))
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };
            foreach (string argument in new[] { "run", exe, WinePath(module), WinePath(folder), workers.ToString(CultureInfo.InvariantCulture) })
                start.ArgumentList.Add(argument);
            start.Environment["STEAM_COMPAT_DATA_PATH"] = compat;
            start.Environment["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam;
            start.Environment["SteamAppId"] = "32370";
            start.Environment["SteamGameId"] = "32370";
            progress?.Invoke(from, "Making KMRP's interface under Proton…");
            Dictionary<int, int[]> shares = new Dictionary<int, int[]>();
            int made = 0, finished = 0;
            Stopwatch clock = Stopwatch.StartNew();
            using (Process process = Process.Start(start))
            {
                process.ErrorDataReceived += delegate { };
                process.BeginErrorReadLine();
                string line;
                while ((line = process.StandardOutput.ReadLine()) != null)
                {
                    string[] part = line.Trim().Split(' ');
                    int share, done, total, count;
                    if (part.Length == 6 && part[0] == "step" && int.TryParse(part[1], out share) &&
                        int.TryParse(part[2], out done) && int.TryParse(part[3], out total))
                    {
                        shares[share] = new[] { done, total };
                        int all = 0, ready = 0;
                        foreach (int[] each in shares.Values) { ready += each[0]; all += each[1]; }
                        if (all > 0)
                            progress?.Invoke(from + (to - from) * ready / all, "Making KMRP's interface under Proton…");
                    }
                    else if (part.Length == 3 && part[0] == "made" && int.TryParse(part[2], out count))
                    {
                        if (count > 0) made += count;
                        ++finished;
                    }
                }
                if (!process.WaitForExit(15 * 60 * 1000))
                {
                    try { process.Kill(true); }
                    catch { }
                }
                bool ok = process.HasExited && process.ExitCode == 0 && finished == workers;
                report?.Invoke(ok
                    ? "Made KMRP's interface ahead under Proton: " + made.ToString(CultureInfo.InvariantCulture) + " display sizes in " +
                      ((int)clock.Elapsed.TotalSeconds).ToString(CultureInfo.InvariantCulture) + " s."
                    : "KMRP's interface was not all made ahead under Proton (" + made.ToString(CultureInfo.InvariantCulture) +
                      " sizes made); the game makes the rest when it first needs them.");
            }
        }

        /// <summary>Wine's name for a Linux path: its Z: drive is the Linux root.</summary>
        internal static string WinePath(string path)
        {
            return "Z:" + Path.GetFullPath(path).Replace('/', '\\');
        }

        /// <summary>The Proton the game last ran with: Proton writes its own folder's paths into
        /// compatdata/&lt;app id&gt;/config_info, one per line after its version, each under its
        /// files folder. Null when that file names no Proton that is still there.</summary>
        internal static string Proton(string compat)
        {
            string info = Path.Combine(compat, "config_info");
            if (!File.Exists(info))
                return null;
            foreach (string line in File.ReadAllLines(info))
            {
                int files = line.IndexOf("/files/", StringComparison.Ordinal);
                if (files <= 0)
                    continue;
                string folder = line.Substring(0, files);
                if (File.Exists(Path.Combine(folder, "proton")))
                    return folder;
            }
            return null;
        }

        /// <summary>Steam's own folder, which `proton run` needs (STEAM_COMPAT_CLIENT_INSTALL_PATH),
        /// in the places Steam installs to, the Flatpak's among them.</summary>
        internal static string SteamRoot()
        {
            string home = Environment.GetEnvironmentVariable("HOME") ?? "";
            foreach (string candidate in new[] { Path.Combine(home, ".steam", "steam"), Path.Combine(home, ".local", "share", "Steam"),
                         Path.Combine(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"), Path.Combine(home, ".steam", "root") })
            {
                if (Directory.Exists(Path.Combine(candidate, "steamapps")) || File.Exists(Path.Combine(candidate, "steam.sh")))
                    return Path.GetFullPath(candidate);
            }
            return null;
        }
    }
}
