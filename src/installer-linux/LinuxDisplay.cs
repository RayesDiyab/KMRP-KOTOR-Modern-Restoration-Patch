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
    /// one first, whatever a compositor shows programs. Under Gamescope (Steam Deck's game mode,
    /// Bazzite) the two can disagree: xrandr sees Gamescope's virtual size, which made the Windows
    /// installer under Proton write a size the monitor does not have (issue 72). So the size the
    /// installer starts the game at is the monitor's preferred one from DRM when Gamescope is
    /// running, and xrandr's current one otherwise; every size either source lists is offered.
    /// Neither available: nothing is offered, and the size is asked for.</summary>
    internal static class LinuxDisplay
    {
        internal sealed class Mode
        {
            internal int Width, Height;
            internal double Rate;          // 0 where the source has none (DRM's list)
            internal bool Current, Preferred;
        }

        private static List<Mode> cached;

        internal static List<Mode> Modes()
        {
            if (cached != null)
                return cached;
            List<Mode> modes = new List<Mode>();
            modes.AddRange(FromXrandr(Run("xrandr", "--query")));
            modes.AddRange(FromDrm("/sys/class/drm"));
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
            foreach (Mode m in Modes())
                if (m.Width >= 640 && m.Height >= 480 && !sizes.Exists(s => s[0] == m.Width && s[1] == m.Height))
                    sizes.Add(new[] { m.Width, m.Height });
            sizes.Sort((a, b) => b[0] * b[1] != a[0] * a[1] ? (b[0] * b[1]).CompareTo(a[0] * a[1]) : b[0].CompareTo(a[0]));
            return sizes;
        }

        /// <summary>The size to start the game at, or null when no source answered.</summary>
        internal static int[] Start()
        {
            Mode pick = null;
            List<Mode> modes = Modes();
            if (UnderGamescope())
                pick = modes.Find(m => m.Preferred);
            if (pick == null)
                pick = modes.Find(m => m.Current);
            if (pick == null)
                pick = modes.Find(m => m.Preferred);
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
