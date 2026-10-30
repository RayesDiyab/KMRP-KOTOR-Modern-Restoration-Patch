using System;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using Avalonia;

namespace Kmrp
{
    // KMRP's native Linux installer, console front end over the shared core (issue 76,
    // docs/linux-appimage-installer.md). The commands call what the Windows window calls:
    // PatchOperations.ApplyInPlace and PatchOperations.Restore, with every line of the report
    // also written to KMRP/logs/install.log (PatchOperations.AppendLog).
    internal static class LinuxProgram
    {
        private static int Main(string[] args)
        {
            // No command and a display to show it on: the window (MainWindow.cs).
            if (args.Length == 0 && (Environment.GetEnvironmentVariable("DISPLAY") != null ||
                                     Environment.GetEnvironmentVariable("WAYLAND_DISPLAY") != null))
                return AppBuilder.Configure<InstallerApp>().UsePlatformDetect()
                    .StartWithClassicDesktopLifetime(args);
            try
            {
                if (args.Length == 1 && args[0] == "find")
                {
                    string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                    var folders = SteamLibraries.KotorFolders(home);
                    foreach (string folder in folders)
                        Console.WriteLine(folder);
                    if (folders.Count == 0)
                        Console.Error.WriteLine("kmrp-installer: KOTOR was not found in Steam's libraries; name its folder");
                    return folders.Count == 0 ? 1 : 0;
                }
                if (args.Length == 1 && args[0] == "sizes")
                {
                    int[] start = LinuxDisplay.Start();
                    Console.WriteLine("Gamescope: " + (LinuxDisplay.UnderGamescope() ? "yes" : "no"));
                    Console.WriteLine("start at:  " + (start == null ? "unknown" : start[0] + "x" + start[1]));
                    foreach (int[] size in LinuxDisplay.Sizes())
                        Console.WriteLine(string.Format(CultureInfo.InvariantCulture, "  {0}x{1}  {2} Hz{3}", size[0], size[1],
                            LinuxDisplay.HighestRefresh(size), ResolutionCatalog.Covers(size[0], size[1]) ? "" : "  (not covered)"));
                    return 0;
                }
                if (args.Length >= 2 && args[0] == "inspect")
                    return Inspect(Executable(args[1]));
                if (args.Length >= 2 && args[0] == "install")
                    return Install(Executable(args[1]), args);
                if (args.Length >= 2 && args[0] == "restore")
                    return Restore(Executable(args[1]));
                Console.WriteLine("KMRP " + GoldPatch.PatchVersion + " for Linux");
                Console.WriteLine("usage: kmrp-installer find");
                Console.WriteLine("       kmrp-installer sizes");
                Console.WriteLine("       kmrp-installer inspect <game folder>");
                Console.WriteLine("       kmrp-installer install <game folder> [--size WIDTHxHEIGHT]");
                Console.WriteLine("       kmrp-installer restore <game folder>");
                return args.Length == 0 ? 0 : 64;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("kmrp-installer: " + ex.Message);
                return 1;
            }
        }

        private static string Executable(string folder)
        {
            string exe = Path.Combine(Path.GetFullPath(folder), "swkotor.exe");
            if (!File.Exists(exe))
                throw new FileNotFoundException("no swkotor.exe in " + folder);
            InstallPlatform.GameFolder = Path.GetDirectoryName(exe);
            return exe;
        }

        private static int Inspect(string exe)
        {
            Console.WriteLine("game:       " + exe);
            Console.WriteLine("state:      " + PatchOperations.Describe(exe));
            Console.WriteLine("restorable: " + (PatchOperations.CanRestore(exe) ? "yes" : "no"));
            int width, height;
            if (PatchOperations.TryReadInstalledResolution(exe, out width, out height))
                Console.WriteLine("installed:  " + width + "x" + height);
            return 0;
        }

        private static int Install(string exe, string[] args)
        {
            int[] size = null;
            for (int i = 2; i + 1 < args.Length; i++)
                if (args[i] == "--size")
                    size = ParseSize(args[i + 1]);
            if (size == null)
            {
                // The display's size (LinuxDisplay.Start: the monitor's own under Gamescope), as the
                // Windows installer starts at the display's; else what swkotor.ini has.
                int[] display = LinuxDisplay.Start();
                size = display != null && ResolutionCatalog.Covers(display[0], display[1]) ? display : IniSize(exe);
            }
            if (size == null)
                throw new ArgumentException("no size given and swkotor.ini has none: pass --size WIDTHxHEIGHT");
            Console.WriteLine("Installing KMRP into " + Path.GetDirectoryName(exe) + " at " + size[0] + "x" + size[1]);
            PatchOperations.ApplyInPlace(exe, size[0], size[1], Reporter(exe, "install"), Progress);
            Console.WriteLine();
            return 0;
        }

        private static int Restore(string exe)
        {
            Console.WriteLine("Restoring " + Path.GetDirectoryName(exe));
            PatchOperations.Restore(exe, Reporter(exe, "restore"), Progress);
            Console.WriteLine();
            return 0;
        }

        private static Action<string> Reporter(string exe, string what)
        {
            return delegate(string message)
            {
                Console.WriteLine("  " + message);
                try { PatchOperations.AppendLog(exe, what + ": " + message); }
                catch { }
            };
        }

        private static int lastPercent = -1;

        private static void Progress(int percent, string message)
        {
            if (percent == lastPercent)
                return;
            lastPercent = percent;
            string text = message == null ? "" : message.Split('\t')[0];
            Console.WriteLine(string.Format(CultureInfo.InvariantCulture, "  [{0,3}%] {1}", percent, text));
        }

        private static int[] ParseSize(string text)
        {
            Match m = Regex.Match(text ?? "", @"^(\d{3,5})x(\d{3,5})$");
            if (!m.Success)
                throw new ArgumentException("--size wants WIDTHxHEIGHT, as 1920x1080");
            return new[] { int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture),
                           int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture) };
        }

        // The size swkotor.ini starts the game at, until display detection is built.
        internal static int[] IniSize(string exe)
        {
            string ini = Path.Combine(Path.GetDirectoryName(exe), "swkotor.ini");
            if (!File.Exists(ini))
                return null;
            int width = 0, height = 0;
            foreach (string line in File.ReadAllLines(ini))
            {
                Match m = Regex.Match(line, @"^\s*(Width|Height)\s*=\s*(\d+)\s*$", RegexOptions.IgnoreCase);
                if (!m.Success)
                    continue;
                int value = int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture);
                if (m.Groups[1].Value.Equals("Width", StringComparison.OrdinalIgnoreCase)) width = value;
                else height = value;
            }
            return width > 0 && height > 0 ? new[] { width, height } : null;
        }
    }
}
