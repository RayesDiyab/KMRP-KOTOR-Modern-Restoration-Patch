using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;

namespace Kmrp
{
    /// <summary>KMRP's art made ahead under Proton, as the Windows installer makes it
    /// (ArtPreparation.cs): every size the display offers, into the cache in the game's own
    /// prefix (%LOCALAPPDATA%\KMRP\cache), so the game starts without making it. Until
    /// 2026-11-03 the Linux installer left it to the game, whose first start was then long
    /// (the maintainer, SteamOS: "on linux its instant but it takes longer to launch the game").
    ///
    /// The work is kmrp-prepare.exe's (src/installer-linux/prepare), a 32-bit Windows program
    /// with no .NET and no window, which loads the installed patches\kmrp.dll and calls its
    /// KmrpPrepareAssets, started with the Proton the game last ran with (`proton run`).
    /// Its workers write their progress to one file each, read here while they work: through
    /// Proton's standard output nothing arrived until the end (SteamOS, 2026-11-03). Anything
    /// missing, the prefix, that Proton, or Steam's own folder, leaves the art to the game, as
    /// before.</summary>
    internal static class ProtonArt
    {
        private const string Worker = "kmrp-prepare.exe";

        /// <summary>Half the processor's threads, at most six, as on Windows.</summary>
        internal static int Workers()
        {
            return Math.Max(1, Math.Min(6, Environment.ProcessorCount / 2));
        }

        internal static void Run(string folder, Action<string> report, Action<int, string> progress, InstallClock timing,
            int from, int to)
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
            string lines = Path.Combine(work, "progress");
            Directory.CreateDirectory(lines);
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
                Make(proton, steam, compat, exe, module, folder, lines, report, progress, timing, from, to);
            }
            finally
            {
                try { Directory.Delete(work, true); }
                catch { }
            }
        }

        private static void Make(string proton, string steam, string compat, string exe, string module, string folder,
            string lines, Action<string> report, Action<int, string> progress, InstallClock timing, int from, int to)
        {
            int workers = Workers();
            ProcessStartInfo start = new ProcessStartInfo(Path.Combine(proton, "proton"))
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };
            foreach (string argument in new[] { "run", exe, WinePath(module), WinePath(folder),
                         workers.ToString(CultureInfo.InvariantCulture), WinePath(lines) })
                start.ArgumentList.Add(argument);
            start.Environment["STEAM_COMPAT_DATA_PATH"] = compat;
            start.Environment["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam;
            start.Environment["SteamAppId"] = "32370";
            start.Environment["SteamGameId"] = "32370";
            start.Environment["WINEDEBUG"] = "-all";
            ArtProgress shares = new ArtProgress(workers, timing);
            long[] read = new long[workers];
            shares.Tell(progress, from, to);
            Stopwatch clock = Stopwatch.StartNew();
            bool late = false;
            using (Process process = Process.Start(start))
            {
                // Proton's and Wine's own output, not the work's: drained, so a full pipe never
                // stops them.
                process.OutputDataReceived += delegate { };
                process.ErrorDataReceived += delegate { };
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                while (!process.WaitForExit(250))
                {
                    if (Poll(lines, read, shares))
                        shares.Tell(progress, from, to);
                    // As on Windows, far longer than the slowest disk measured.
                    if (clock.Elapsed > TimeSpan.FromMinutes(30))
                    {
                        late = true;
                        try { process.Kill(true); }
                        catch { }
                        process.WaitForExit();
                        break;
                    }
                }
            }
            if (Poll(lines, read, shares))
                shares.Tell(progress, from, to);
            // Each worker's "made" line is the result: Proton does not always pass the
            // program's exit code on.
            int made = 0;
            bool failed = late;
            for (int i = 0; i < workers; i++)
            {
                if (shares.Made(i) < 0)
                    failed = true;
                else
                    made += shares.Made(i);
            }
            string seconds = ((int)Math.Round(clock.Elapsed.TotalSeconds)).ToString(CultureInfo.InvariantCulture);
            report?.Invoke(failed
                ? "KMRP's interface was made ahead for " + made.ToString(CultureInfo.InvariantCulture) +
                  " resolutions under Proton, but not all; the game makes the rest when it needs them."
                : "KMRP's interface is ready for " + made.ToString(CultureInfo.InvariantCulture) +
                  (made == 1 ? " resolution" : " resolutions") + " your display offers (" + seconds + " s, " +
                  workers.ToString(CultureInfo.InvariantCulture) + (workers == 1 ? " worker" : " workers") + ", under Proton).");
        }

        /// <summary>Reads the new whole lines in every worker's file (share-N.txt) from where
        /// the last read stopped. True when one was a progress line.</summary>
        private static bool Poll(string lines, long[] read, ArtProgress shares)
        {
            bool any = false;
            for (int i = 0; i < read.Length; i++)
            {
                string path = Path.Combine(lines, "share-" + i.ToString(CultureInfo.InvariantCulture) + ".txt");
                byte[] fresh;
                try
                {
                    using (FileStream file = new FileStream(path, FileMode.Open, FileAccess.Read,
                               FileShare.ReadWrite | FileShare.Delete))
                    {
                        if (file.Length <= read[i])
                            continue;
                        file.Seek(read[i], SeekOrigin.Begin);
                        fresh = new byte[file.Length - read[i]];
                        int got = 0, count;
                        while (got < fresh.Length && (count = file.Read(fresh, got, fresh.Length - got)) > 0)
                            got += count;
                        Array.Resize(ref fresh, got);
                    }
                }
                catch (IOException) { continue; }
                catch (UnauthorizedAccessException) { continue; }
                // Only whole lines: the rest is read again next time.
                int end = Array.LastIndexOf(fresh, (byte)'\n');
                if (end < 0)
                    continue;
                read[i] += end + 1;
                foreach (string line in Encoding.ASCII.GetString(fresh, 0, end).Split('\n'))
                    any |= shares.Read(i, line);
            }
            return any;
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
