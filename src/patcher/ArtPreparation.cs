// The art prebuild: loads kmrp.dll and makes every display size's files before the game first
// starts. Windows only; split from KpmEdition.cs on 2026-10-30, unchanged. Called through
// InstallPlatform.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>KMRP's art made ahead, at install, with the module's own code: the common
    /// files and every size the display offers that KMRP covers, each with the fonts in use
    /// at its height, into the cache the game reads (%LOCALAPPDATA%\KMRP\cache\&lt;build&gt;,
    /// K1RuntimeAssets.cpp), so the game starts and changes size without making anything
    /// (the maintainer, 2026-10-19: "let's actually create all the supported resolutions",
    /// "smoother user experience comes priority").
    ///
    /// The module is x86 and its helpers keep their state in globals, so the work is done
    /// by workers, each a copy of this installer (a 32-bit program since then) started with
    /// --prepare-art: each loads a copy of the module, out of the embedded .kpatch, with
    /// KMRP_PREPARE in its environment while it loads, which tells the module's DllMain that
    /// this is not the game (K1RuntimeEngine.cpp), and calls its export KmrpPrepareAssets
    /// with the game's folder and its share of the sizes; the module reads the pack in the
    /// game's patches folder. Measured on the maintainer's PC on 2026-10-19, 19 sizes and
    /// the common files from the test game on a hard disk: with the cache on the NVMe SSD,
    /// 83 s with one worker, 33 s with four, 25 s with six, 24 s with eight; with the cache
    /// on a hard disk, 167, 122 (two), 94 (four) and 98 s (eight). Half the processor's
    /// threads are used, at most six.</summary>
    internal static class ArtPreparation
    {
        private const string Environment_ = "KMRP_PREPARE";
        private const uint LoadWithAlteredSearchPath = 0x00000008;
        internal const string WorkerSwitch = "--prepare-art";

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true, BestFitMapping = false)]
        private static extern IntPtr GetProcAddress(IntPtr module, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool FreeLibrary(IntPtr module);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetStdHandle(int which, IntPtr handle);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr security, uint disposition,
            uint flags, IntPtr template);

        private const int StandardOutput = -11;
        private const uint GenericWrite = 0x40000000, ShareReadWrite = 3, OpenExisting = 3;

        // K1RuntimeAssets.h, KmrpPrepareStep: parts done, parts in all, the size about to
        // be made (0, 0 for the common files and at the end). Nonzero stops.
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        private delegate int PrepareStep(int done, int total, int width, int height, IntPtr context);

        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int PrepareAssets([MarshalAs(UnmanagedType.LPWStr)] string game, int share, int shares,
            PrepareStep step, IntPtr context);

        // One worker's progress, as its lines report it.
        private sealed class Share
        {
            internal int Done;
            internal int Total = -1;
            internal int Made = -1;
        }

        /// <summary>Makes the art for the game in `folder`, reporting progress from `from`
        /// to `to` percent. Never throws: what is not made here, the game makes.</summary>
        internal static void Run(string folder, string kpatchResource, string moduleEntry, Action<string> report,
            Action<int, string> progress, InstallClock timing, int from, int to)
        {
            if (timing != null)
                timing.ArtBegun();
            if (IntPtr.Size != 4)
            {
                Report(report, "KMRP's interface was not made ahead (the installer is not running as a " +
                    "32-bit program); the game makes it when it first starts.");
                return;
            }
            string work = Path.Combine(Path.GetTempPath(),
                "KMRP-prepare-" + Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture));
            int count = Workers();
            List<Process> workers = new List<Process>();
            Share[] shares = new Share[count];
            object gate = new object();
            Stopwatch clock = Stopwatch.StartNew();
            bool stopped = false;
            Action tell = delegate
            {
                lock (gate)
                {
                    if (stopped)
                        return;
                    // Parts: worker 0's first is the common files, every other a resolution.
                    int all = 0, finished = 0, sizes = 0, ready = 0;
                    for (int i = 0; i < shares.Length; i++)
                    {
                        Share each = shares[i];
                        if (each == null || each.Total < 0)
                            continue;
                        int done = Math.Min(each.Done, each.Total);
                        all += each.Total;
                        finished += done;
                        sizes += i == 0 ? Math.Max(0, each.Total - 1) : each.Total;
                        ready += i == 0 ? Math.Max(0, done - 1) : done;
                    }
                    int percent = from + (all > 0 ? (to - from) * finished / all : 0);
                    string what = ready == 0 || sizes == 0 ? "Unpacking KMRP's art…"
                        : ready.ToString(CultureInfo.InvariantCulture) + " of " + sizes.ToString(CultureInfo.InvariantCulture) +
                          " resolutions ready…";
                    // Inside the lock, so nothing is told once the work is over; the
                    // window's progress is posted, not waited for.
                    if (progress != null)
                    {
                        try { progress(percent, what); }
                        catch { }
                    }
                }
            };
            try
            {
                Directory.CreateDirectory(work);
                string copy = Path.Combine(work, "kmrp.dll");
                File.WriteAllBytes(copy, ModuleBytes(kpatchResource, moduleEntry));
                string self = Assembly.GetExecutingAssembly().Location;
                for (int i = 0; i < count; i++)
                {
                    Share share = shares[i] = new Share();
                    int index = i;
                    ProcessStartInfo start = new ProcessStartInfo(self, Quote(WorkerSwitch) + " " + Quote(copy) + " " +
                        Quote(folder) + " " + i.ToString(CultureInfo.InvariantCulture) + " " +
                        count.ToString(CultureInfo.InvariantCulture));
                    start.UseShellExecute = false;
                    start.CreateNoWindow = true;
                    start.RedirectStandardOutput = true;
                    Process worker = new Process();
                    worker.StartInfo = start;
                    worker.OutputDataReceived += delegate(object sender, DataReceivedEventArgs line)
                    {
                        string[] parts = (line.Data ?? String.Empty).Split(' ');
                        int done, total;
                        lock (gate)
                        {
                            if (parts.Length == 5 && parts[0] == "step" &&
                                Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out done) &&
                                Int32.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out total))
                            {
                                share.Done = done;
                                share.Total = total;
                                // The time left is the install's clock's, worker by worker.
                                if (timing != null)
                                    timing.ArtWorker(index, done, total);
                            }
                            else if (parts.Length == 2 && parts[0] == "made")
                                Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out share.Made);
                            else
                                return;
                        }
                        tell();
                    };
                    worker.Start();
                    worker.BeginOutputReadLine();
                    workers.Add(worker);
                }
                tell();
                bool late = false;
                foreach (Process worker in workers)
                {
                    // Far longer than the slowest disk measured; a worker that is still at it
                    // then is stopped, and the game makes what it left.
                    if (!worker.WaitForExit((int)TimeSpan.FromMinutes(30).TotalMilliseconds))
                    {
                        late = true;
                        try { worker.Kill(); }
                        catch { }
                    }
                    worker.WaitForExit();
                }
                int made = 0;
                bool failed = late;
                for (int i = 0; i < workers.Count; i++)
                {
                    if (workers[i].ExitCode != 0 || shares[i].Made < 0)
                        failed = true;
                    else
                        made += shares[i].Made;
                }
                string seconds = ((int)Math.Round(clock.Elapsed.TotalSeconds)).ToString(CultureInfo.InvariantCulture);
                Report(report, failed
                    ? "KMRP's interface was made ahead for " + made.ToString(CultureInfo.InvariantCulture) +
                      " resolutions, but not all; the game makes the rest when it needs them " +
                      "(KMRP\\logs\\kmrp-kpm.log in the game folder says why)."
                    : "KMRP's interface is ready for " + made.ToString(CultureInfo.InvariantCulture) +
                      (made == 1 ? " resolution" : " resolutions") + " your display offers (" + seconds + " s, " +
                      count.ToString(CultureInfo.InvariantCulture) + (count == 1 ? " worker)." : " workers)."));
            }
            catch (Exception error)
            {
                Report(report, "KMRP's interface could not be made ahead (" + error.Message +
                    "); the game makes it when it first starts.");
            }
            finally
            {
                lock (gate)
                    stopped = true;
                foreach (Process worker in workers)
                {
                    try
                    {
                        if (!worker.HasExited)
                            worker.Kill();
                    }
                    catch { }
                    worker.Dispose();
                }
                try { Directory.Delete(work, true); }
                catch { }
            }
        }

        /// <summary>A worker (--prepare-art MODULE GAME SHARE SHARES): loads the module and
        /// makes its share, writing "step DONE TOTAL WIDTH HEIGHT" before each part and
        /// "made N" at the end to standard output, for Run. 0 when the share was made.</summary>
        internal static int Worker(string modulePath, string game, int share, int shares)
        {
            IntPtr module = IntPtr.Zero;
            try
            {
                // The progress lines go to the pipe Run reads; the module's helpers print to
                // standard output too, buffered by its C runtime, which could cut a line in
                // two. So this writer takes the pipe first, and the module, whose C runtime
                // takes the standard handles when it loads, gets NUL.
                TextWriter output = Console.Out;
                IntPtr nul = CreateFile("NUL", GenericWrite, ShareReadWrite, IntPtr.Zero, OpenExisting, 0, IntPtr.Zero);
                if (nul != new IntPtr(-1))
                    SetStdHandle(StandardOutput, nul);
                Environment.SetEnvironmentVariable(Environment_, "1");
                try { module = LoadLibraryEx(modulePath, IntPtr.Zero, LoadWithAlteredSearchPath); }
                finally { Environment.SetEnvironmentVariable(Environment_, null); }
                if (module == IntPtr.Zero)
                    return 2;
                IntPtr address = GetProcAddress(module, "KmrpPrepareAssets");
                if (address == IntPtr.Zero)
                    return 3;
                PrepareAssets prepare = (PrepareAssets)Marshal.GetDelegateForFunctionPointer(address, typeof(PrepareAssets));
                PrepareStep step = delegate(int done, int total, int width, int height, IntPtr context)
                {
                    output.WriteLine("step " + done.ToString(CultureInfo.InvariantCulture) + " " +
                        total.ToString(CultureInfo.InvariantCulture) + " " + width.ToString(CultureInfo.InvariantCulture) +
                        " " + height.ToString(CultureInfo.InvariantCulture));
                    output.Flush();
                    return 0;
                };
                int made = prepare(game, share, shares, step, IntPtr.Zero);
                GC.KeepAlive(step);
                output.WriteLine("made " + made.ToString(CultureInfo.InvariantCulture));
                output.Flush();
                return made < 0 ? 1 : 0;
            }
            finally
            {
                if (module != IntPtr.Zero)
                    FreeLibrary(module);
            }
        }

        /// <summary>How many workers make the art: half the processor's threads, at most
        /// six (measured: six take 25 s for 19 resolutions on an NVMe SSD, eight 24 s).</summary>
        internal static int Workers()
        {
            return Math.Max(1, Math.Min(6, Environment.ProcessorCount / 2));
        }

        /// <summary>A worker's time for one part (a resolution, or the common files), before
        /// any is made: the pace measured on the maintainer's PC on 2026-10-19 for the kind of
        /// drive the cache is on, and a margin, so the clock starts above the truth and only
        /// comes down (InstallClock; the maintainer: "it should overestimate instead of
        /// underestimating"). The first worker, which also makes the common files, finishes
        /// last. With the cache on the NVMe SSD one worker made 19 resolutions in 83 s
        /// (4.1 s each), four in 33 s (the first worker five, 5.6 s each), six in 25 s in the
        /// test game and about 30 s in the maintainer's own install (the first worker four,
        /// 5 to 6.3 s each): 4.2 s, 8% more for each further worker, and a quarter more. On
        /// its hard disk one worker took 167 s (8.4 s a part), four 94 s (15.7 s), eight 98 s
        /// (24.5 s): 8.4 s, 27% more for each further worker, and a tenth more. A drive
        /// Windows does not say is solid-state is taken as a hard disk.</summary>
        internal static double SecondsPerResolution(int workers, bool? solidState)
        {
            int others = Math.Max(1, workers) - 1;
            return solidState == true ? 4.2 * (1 + 0.08 * others) * 1.25 : 8.4 * (1 + 0.27 * others) * 1.1;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct StoragePropertyQuery
        {
            public int PropertyId;
            public int QueryType;
            public int AdditionalParameters;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SeekPenaltyDescriptor
        {
            public int Version;
            public int Size;
            [MarshalAs(UnmanagedType.U1)]
            public bool IncursSeekPenalty;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool DeviceIoControl(IntPtr device, uint code, ref StoragePropertyQuery query, int querySize,
            out SeekPenaltyDescriptor answer, int answerSize, out int returned, IntPtr overlapped);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr handle);

        private const uint StorageQueryProperty = 0x002D1400;   // IOCTL_STORAGE_QUERY_PROPERTY
        private const int SeekPenaltyProperty = 7;              // StorageDeviceSeekPenaltyProperty

        /// <summary>Whether the drive the art cache goes on (%LOCALAPPDATA%'s, as the module
        /// finds it) is solid-state: a drive without a seek penalty, as Windows reports it to
        /// any program (no administrator needed). Null when it does not say, as for a volume
        /// spread over several disks.</summary>
        internal static bool? CacheOnSolidState()
        {
            try
            {
                string local = Environment.GetEnvironmentVariable("LOCALAPPDATA");
                if (String.IsNullOrEmpty(local))
                    local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string root = Path.GetPathRoot(Path.GetFullPath(local));
                if (root == null || root.Length < 2 || root[1] != ':')
                    return null;
                IntPtr volume = CreateFile("\\\\.\\" + root.Substring(0, 2), 0, ShareReadWrite, IntPtr.Zero, OpenExisting,
                    0, IntPtr.Zero);
                if (volume == new IntPtr(-1))
                    return null;
                try
                {
                    StoragePropertyQuery query = new StoragePropertyQuery();
                    query.PropertyId = SeekPenaltyProperty;
                    SeekPenaltyDescriptor answer;
                    int returned;
                    if (!DeviceIoControl(volume, StorageQueryProperty, ref query, Marshal.SizeOf(typeof(StoragePropertyQuery)),
                            out answer, Marshal.SizeOf(typeof(SeekPenaltyDescriptor)), out returned, IntPtr.Zero) || returned < 9)
                        return null;
                    return !answer.IncursSeekPenalty;
                }
                finally
                {
                    CloseHandle(volume);
                }
            }
            catch
            {
                return null;
            }
        }

        /// <summary>The resolutions the display offers that KMRP's sets reach, as the module
        /// will count them (KmrpRuntimeAssetsCovers asks the same table), before it is loaded.</summary>
        internal static int ExpectedSizes()
        {
            int sizes = 0;
            try
            {
                HashSet<long> seen = new HashSet<long>();
                GuiBlend table = GuiBlend.Shared();
                MainForm.DisplayMode mode = new MainForm.DisplayMode();
                mode.StructSize = (short)Marshal.SizeOf(typeof(MainForm.DisplayMode));
                for (int i = 0; MainForm.EnumDisplaySettings(null, i, ref mode); i++)
                {
                    if (mode.BitsPerPel != 32 || mode.PelsWidth < 640 || mode.PelsHeight < 480)
                        continue;
                    if (seen.Add(((long)mode.PelsWidth << 32) | (uint)mode.PelsHeight) &&
                        table.Covers(mode.PelsWidth, mode.PelsHeight))
                        sizes++;
                }
            }
            catch { }
            return sizes > 0 ? sizes : 12;   // not known: about what a display offers
        }

        /// <summary>A path as one argument: in quotes, with a final backslash doubled so that
        /// it does not escape the closing quote (a game in a drive's root folder).</summary>
        private static string Quote(string argument)
        {
            string escaped = argument.Replace("\"", "\\\"");
            if (escaped.EndsWith("\\", StringComparison.Ordinal))
                escaped += "\\";
            return "\"" + escaped + "\"";
        }

        /// <summary>Removes KMRP's art cache, %LOCALAPPDATA%\KMRP\cache, with Restore
        /// Original. A game still running keeps the files it has open; the rest go. Another
        /// game folder with KMRP installed makes what it needs again when it starts.</summary>
        internal static void RemoveCache(Action<string> report)
        {
            // Where the module puts it: %LOCALAPPDATA% as the environment says
            // (K1RuntimeAssets.cpp, Initialize), which a test points elsewhere.
            string local = Environment.GetEnvironmentVariable("LOCALAPPDATA");
            if (String.IsNullOrEmpty(local))
                local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            if (String.IsNullOrEmpty(local))
                return;
            string kmrp = Path.Combine(local, "KMRP");
            string cache = Path.Combine(kmrp, "cache");
            if (!Directory.Exists(cache))
                return;
            int left = 0;
            foreach (string entry in Directory.GetFileSystemEntries(cache))
            {
                try
                {
                    if (Directory.Exists(entry))
                        Directory.Delete(entry, true);
                    else
                        File.Delete(entry);
                }
                catch
                {
                    left++;
                }
            }
            try { Directory.Delete(cache); }
            catch { }
            try { Directory.Delete(kmrp); }
            catch { }
            Report(report, left == 0
                ? "Removed KMRP's prepared interface files (" + cache + ")."
                : "Removed most of KMRP's prepared interface files (" + cache + "); a running game " +
                  "still has some open.");
        }

        private static byte[] ModuleBytes(string resource, string entryName)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
            {
                if (stream == null)
                    throw new InvalidDataException("This build does not carry " + resource + ".");
                using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read, false))
                {
                    ZipArchiveEntry entry = zip.GetEntry(entryName);
                    if (entry == null)
                        throw new InvalidDataException(resource + " carries no module.");
                    using (Stream module = entry.Open())
                    using (MemoryStream copy = new MemoryStream((int)entry.Length))
                    {
                        module.CopyTo(copy);
                        return copy.ToArray();
                    }
                }
            }
        }

        private static void Report(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }
    }

}
