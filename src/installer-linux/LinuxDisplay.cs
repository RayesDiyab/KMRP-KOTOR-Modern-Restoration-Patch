using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>The display sizes and refresh rates a Linux PC offers (issue 76; issue 72).
    ///
    /// Two sources. xrandr, on X11 or through XWayland, gives each connected output's modes, their
    /// rates and the current one (marked '*'). The kernel's DRM list, /sys/class/drm/card*-*/modes
    /// of each connector whose status is "connected", gives the monitor's own modes, its preferred
    /// one first, whatever a compositor shows programs. The two can disagree. Under Gamescope
    /// (Steam Deck's game mode, Bazzite) xrandr sees Gamescope's virtual size, which made the
    /// Windows installer under Proton write a size the monitor does not have into swkotor.ini,
    /// and the main menu broke (issue 72; the reporter's fix was the monitor's own resolution
    /// there). Desktop scaling (KDE's 125%, say) can likewise show XWayland a scaled size.
    ///
    /// So where DRM lists the monitor's modes, those are the sizes, and the game starts at
    /// xrandr's current size only when it is one of them and Gamescope is not running, else at
    /// the monitor's preferred mode. Where DRM lists nothing (some virtual machines; WSLg),
    /// xrandr's modes and its current size are used. Neither available: nothing is offered, and
    /// swkotor.ini's size or --size is used.
    ///
    /// For tests, KMRP_TEST_XRANDR names a file to read as xrandr's output ("none": no xrandr)
    /// and KMRP_TEST_DRM a folder to read as /sys/class/drm.</summary>
    internal static class LinuxDisplay
    {
        internal sealed class Mode
        {
            internal int Width, Height;
            internal double Rate;          // 0 where the source has none (DRM's list)
            internal bool Current, Preferred;
            internal bool Drm;             // from the kernel's list: a mode the monitor has
        }

        private static List<Mode> cached;

        internal static List<Mode> Modes()
        {
            if (cached != null)
                return cached;
            List<Mode> modes = new List<Mode>();
            string xrandrFile = Environment.GetEnvironmentVariable("KMRP_TEST_XRANDR");
            string xrandr = xrandrFile == null ? Run("xrandr", "--query")
                : xrandrFile == "none" || !File.Exists(xrandrFile) ? null : File.ReadAllText(xrandrFile);
            modes.AddRange(FromXrandr(xrandr));
            modes.AddRange(FromDrm(Environment.GetEnvironmentVariable("KMRP_TEST_DRM") ?? "/sys/class/drm"));
            cached = modes;
            return modes;
        }

        internal static bool UnderGamescope()
        {
            return Environment.GetEnvironmentVariable("GAMESCOPE_WAYLAND_DISPLAY") != null ||
                string.Equals(Environment.GetEnvironmentVariable("XDG_CURRENT_DESKTOP"), "gamescope",
                    StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>The sizes to offer, each once, largest first.</summary>
        internal static List<int[]> Sizes()
        {
            List<int[]> sizes = new List<int[]>();
            bool drm = Modes().Exists(m => m.Drm);
            foreach (Mode m in Modes())
                if ((!drm || m.Drm) && m.Width >= 640 && m.Height >= 480 && !sizes.Exists(s => s[0] == m.Width && s[1] == m.Height))
                    sizes.Add(new[] { m.Width, m.Height });
            sizes.Sort((a, b) => b[0] * b[1] != a[0] * a[1] ? (b[0] * b[1]).CompareTo(a[0] * a[1]) : b[0].CompareTo(a[0]));
            return sizes;
        }

        /// <summary>The size to start the game at, or null when no source answered.</summary>
        internal static int[] Start()
        {
            List<Mode> modes = Modes();
            Mode current = modes.Find(m => m.Current);
            if (modes.Exists(m => m.Drm))
            {
                if (current != null && !UnderGamescope() &&
                    modes.Exists(m => m.Drm && m.Width == current.Width && m.Height == current.Height))
                    return new[] { current.Width, current.Height };
                Mode preferred = modes.Find(m => m.Drm && m.Preferred);
                return preferred == null ? null : new[] { preferred.Width, preferred.Height };
            }
            Mode pick = current ?? modes.Find(m => m.Preferred);
            return pick == null ? null : new[] { pick.Width, pick.Height };
        }

        /// <summary>The highest rate xrandr lists at SIZE (or at the current size when null); 0
        /// when it lists none, as the Windows installer answers when it cannot tell.</summary>
        internal static int HighestRefresh(int[] size)
        {
            if (size == null)
                size = Start();
            double best = 0;
            if (size != null)
                foreach (Mode m in Modes())
                    if (m.Width == size[0] && m.Height == size[1] && m.Rate > best)
                        best = m.Rate;
            return (int)Math.Round(best);
        }

        internal static List<Mode> FromXrandr(string output)
        {
            List<Mode> modes = new List<Mode>();
            if (string.IsNullOrEmpty(output))
                return modes;
            bool connected = false;
            foreach (string line in output.Split('\n'))
            {
                if (!line.StartsWith(" ", StringComparison.Ordinal))
                {
                    connected = Regex.IsMatch(line, @"^\S+ connected");
                    continue;
                }
                if (!connected)
                    continue;
                Match size = Regex.Match(line, @"^\s+(\d+)x(\d+)i?\s+(.*)$");
                if (!size.Success)
                    continue;
                int w = int.Parse(size.Groups[1].Value, CultureInfo.InvariantCulture);
                int h = int.Parse(size.Groups[2].Value, CultureInfo.InvariantCulture);
                foreach (Match rate in Regex.Matches(size.Groups[3].Value, @"(\d+(?:\.\d+)?)([*+ ]*)"))
                {
                    if (rate.Groups[1].Value.Length == 0)
                        continue;
                    modes.Add(new Mode
                    {
                        Width = w, Height = h,
                        Rate = double.Parse(rate.Groups[1].Value, CultureInfo.InvariantCulture),
                        Current = rate.Groups[2].Value.Contains("*"),
                        Preferred = rate.Groups[2].Value.Contains("+"),
                    });
                }
            }
            return modes;
        }

        internal static List<Mode> FromDrm(string root)
        {
            List<Mode> modes = new List<Mode>();
            try
            {
                if (!Directory.Exists(root))
                    return modes;
                foreach (string connector in Directory.GetDirectories(root, "card*-*"))
                {
                    string status = Path.Combine(connector, "status"), list = Path.Combine(connector, "modes");
                    if (!File.Exists(status) || !File.Exists(list) || File.ReadAllText(status).Trim() != "connected")
                        continue;
                    bool first = true;
                    foreach (string line in File.ReadAllLines(list))
                    {
                        Match m = Regex.Match(line.Trim(), @"^(\d+)x(\d+)");
                        if (!m.Success)
                            continue;
                        modes.Add(new Mode
                        {
                            Width = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture),
                            Height = int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture),
                            Preferred = first,
                            Drm = true,
                        });
                        first = false;
                    }
                }
            }
            catch { }
            return modes;
        }

        private static string Run(string program, string arguments)
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo(program, arguments)
                {
                    RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false,
                };
                using (Process process = Process.Start(start))
                {
                    string output = process.StandardOutput.ReadToEnd();
                    process.WaitForExit(5000);
                    return process.ExitCode == 0 ? output : null;
                }
            }
            catch { return null; }
        }
    }
}
