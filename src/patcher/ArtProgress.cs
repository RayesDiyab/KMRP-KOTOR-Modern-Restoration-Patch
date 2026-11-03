// The art prebuild's progress, read from its workers' lines: the Windows installer's own
// workers (ArtPreparation.cs) and kmrp-prepare.exe's under Proton (src/installer-linux,
// ProtonArt.cs). Split from ArtPreparation.cs on 2026-11-03 so both count the same way.
using System;
using System.Globalization;

namespace Kmrp
{
    /// <summary>What every worker has reported: "step DONE TOTAL WIDTH HEIGHT" before each part
    /// (worker 0's first part is the common files, every other part one resolution) and "made N"
    /// at the end. Not synchronised: the caller holds its own lock.</summary>
    internal sealed class ArtProgress
    {
        private readonly int[] done, total, made;
        private readonly InstallClock timing;

        internal ArtProgress(int workers, InstallClock timing)
        {
            int count = Math.Max(1, workers);
            done = new int[count];
            total = new int[count];
            made = new int[count];
            for (int i = 0; i < count; i++)
                total[i] = made[i] = -1;
            this.timing = timing;
        }

        /// <summary>Worker `index`'s line; false when it is not a progress line.</summary>
        internal bool Read(int index, string line)
        {
            if (index < 0 || index >= done.Length)
                return false;
            string[] parts = (line ?? String.Empty).Trim().Split(' ');
            int first, second;
            if (parts.Length == 5 && parts[0] == "step" &&
                Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out first) &&
                Int32.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out second))
            {
                done[index] = first;
                total[index] = second;
                // The time left is the install's clock's, worker by worker.
                if (timing != null)
                    timing.ArtWorker(index, first, second);
                return true;
            }
            if (parts.Length == 2 && parts[0] == "made" &&
                Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out first))
            {
                made[index] = first;
                return true;
            }
            return false;
        }

        /// <summary>The percent between `from` and `to`, and what the window says.</summary>
        internal void Tell(Action<int, string> progress, int from, int to)
        {
            int all = 0, finished = 0, sizes = 0, ready = 0;
            for (int i = 0; i < done.Length; i++)
            {
                if (total[i] < 0)
                    continue;
                int parts = Math.Min(done[i], total[i]);
                all += total[i];
                finished += parts;
                sizes += i == 0 ? Math.Max(0, total[i] - 1) : total[i];
                ready += i == 0 ? Math.Max(0, parts - 1) : parts;
            }
            int percent = from + (all > 0 ? (to - from) * finished / all : 0);
            string what = ready == 0 || sizes == 0 ? "Unpacking KMRP's art…"
                : ready.ToString(CultureInfo.InvariantCulture) + " of " + sizes.ToString(CultureInfo.InvariantCulture) +
                  " resolutions ready…";
            if (progress != null)
            {
                try { progress(percent, what); }
                catch { }
            }
        }

        /// <summary>The sizes worker `index` made, -1 until it said.</summary>
        internal int Made(int index)
        {
            return index >= 0 && index < made.Length ? made[index] : -1;
        }
    }
}
