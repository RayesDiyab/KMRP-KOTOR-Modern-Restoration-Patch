using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;

namespace Kmrp
{
    /// <summary>The KPM edition's install: everything but the executable.
    ///
    /// KMRP ships two ways from one source. The standalone installer writes the gold
    /// delta into swkotor.exe and installs its own KOTOR Patch Manager runtime. The KPM
    /// edition -- this file, used when the installer is compiled with KPM_EDITION --
    /// leaves swkotor.exe unmodified, because KOTOR Patch Manager recognises a game by
    /// its hash, and hands the executable changes to KMRP's four .kpatch files
    /// (tools/build_kpatch.py). The core patch's module applies them in memory when
    /// the game starts (src/controller-native/K1KpmApplier.cpp), from kmrp-kpm.dat,
    /// which this writes -- the Movies and Map Notes parts only when those patches
    /// are ticked in KOTOR Patch Manager.
    ///
    /// The data file is derived, not restated: the final image is built as the
    /// standalone installer builds it -- the unmodified executable, the embedded gold
    /// delta, ResolutionPatch for the chosen resolution, the map-note flag on
    /// (GoldPatch.ApplyToOriginals) -- from the unmodified executable's bytes this
    /// installer carries rather than the player's file, so that Steam's swkotor.exe,
    /// encrypted on disk, is served the same way as CD 1.03. The file records only
    /// how that differs from the unmodified executable, plus the eleven appended
    /// sections and the relocation table tools/kpm_relocations.py computed from gold,
    /// each change tagged with the patch it belongs to. So with all four patches the
    /// two editions run the same bytes and cannot drift apart.
    ///
    /// Everything else is the standalone installer's own code: Override files,
    /// swkotor.ini, DPI and NVIDIA settings. Not installed here: the executable patch,
    /// KMRP's runtime and hook table, and K1 Modern Driver Compatibility -- those are
    /// KOTOR Patch Manager's (Synchro's K1DC ships as a .kpatch of its own).</summary>
    internal static class KpmEditionOperations
    {
        internal const string DataName = "kmrp-kpm.dat";
        internal const string ManifestName = "KMRP_KPM.manifest";
        private const string RelocationResource = "Kmrp.kpm.relocations";
        // CD 1.03's bytes under gold's chunks, at the relocated fields and under every
        // field ResolutionPatch handles (tools/kpm_originals.py): what the data file is
        // built from, for CD 1.03 and Steam's swkotor.exe alike, since Steam's is
        // encrypted on disk.
        private const string OriginalsResource = "Kmrp.kpm.originals";
        private const long SteamLength = 4395008;
        private const uint BlockVa = 0x0086D000;
        private const int BlockSize = 0xB000;
        private const int BlockSections = 11;
        private const uint KindIn = 1, KindOut = 2, KindAbs = 3;

        // KMRP's SDL for PlayStation, Switch and Steam Deck pads, and its licence: KPM
        // extracts only a patch's module, so these go beside the game, where the module
        // looks for them (K1ControllerBackend.cpp).
        private static readonly string[] SupportResources = { "Kmrp.controller.sdl", "Kmrp.controller.sdllicense" };
        private static readonly string[] SupportFiles = { "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt" };

        // Which KPM edition patch each change belongs to; K1KpmApplier.cpp applies a
        // change when its patch is ticked in KOTOR Patch Manager.
        private const uint FeatureCore = 1, FeatureMovies = 2, FeatureMapNotes = 4;

        private sealed class Section
        {
            internal string Name;
            internal uint Va;
            internal int RawOffset;
            internal int RawSize;
            internal uint Characteristics;
        }

        private sealed class Relocation
        {
            internal uint Kind;
            internal uint Field;
        }

        // ------------------------------------------------------------ state

        internal static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), ManifestName);
        }

        private static string FolderOf(string executablePath)
        {
            return Path.GetDirectoryName(Path.GetFullPath(executablePath));
        }

        internal static bool IsInstalled(string executablePath)
        {
            try { return File.Exists(ManifestPath(executablePath)); }
            catch { return false; }
        }

        /// <summary>Steam's swkotor.exe, which only this edition supports.</summary>
        internal static bool IsSteam(string targetPath)
        {
            try
            {
                return File.Exists(targetPath) && new FileInfo(targetPath).Length == SteamLength &&
                    GoldPatch.HashFile(targetPath) == GoldPatch.SteamHash;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>The executable as this edition sees it: CD 1.03 as the standalone
        /// accepts it, or Steam's.</summary>
        private static ExecutableState InspectSource(string targetPath)
        {
            ExecutableState standalone = PatchOperations.InspectStandalone(targetPath);
            return standalone == ExecutableState.Unsupported && IsSteam(targetPath)
                ? ExecutableState.SupportedClean : standalone;
        }

        /// <summary>Gold here means "KMRP for KPM is installed": the executable is the
        /// unmodified one either way. An executable the standalone installer patched is
        /// Unsupported, and Describe says why.</summary>
        internal static ExecutableState Inspect(string targetPath)
        {
            ExecutableState source = InspectSource(targetPath);
            if (source != ExecutableState.SupportedClean)
                return source == ExecutableState.Gold ? ExecutableState.Unsupported : source;
            return IsInstalled(targetPath) ? ExecutableState.Gold : ExecutableState.SupportedClean;
        }

        internal static string Describe(string targetPath)
        {
            if (PatchOperations.InspectStandalone(targetPath) == ExecutableState.Gold)
                return "The standalone KMRP is installed in this game. Restore it with the " +
                    "standalone installer first; the KPM edition needs the unmodified swkotor.exe.";
            if (IsInstalled(targetPath))
                return "KMRP for KPM is installed.";
            if (IsSteam(targetPath))
                return "Steam's swkotor.exe — ready to install.";
            return PatchOperations.DescribeStandalone(targetPath);
        }

        internal static bool CanRestore(string targetPath)
        {
            return IsInstalled(targetPath) && InspectSource(targetPath) == ExecutableState.SupportedClean;
        }

        internal static bool TryReadInstalledResolution(string targetPath, out int width, out int height)
        {
            width = 0;
            height = 0;
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length == 3 && parts[0] == "resolution")
                        return Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out width) &&
                            Int32.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out height);
                }
            }
            catch { }
            return false;
        }

        // ------------------------------------------------------------ install

        internal static void Install(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress)
        {
            SafeProgress(progress, 0, "Preparing game files…");
            targetPath = Path.GetFullPath(targetPath);
            if (!File.Exists(targetPath))
                throw new FileNotFoundException("swkotor.exe was not found.", targetPath);
            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);

            SafeProgress(progress, 5, "Checking game files…");
            if (PatchOperations.InspectStandalone(targetPath) == ExecutableState.Gold)
                throw new InvalidOperationException(Describe(targetPath));
            bool steam = IsSteam(targetPath);
            if (!steam && !GoldPatch.IsSupportedSourceFile(targetPath))
                throw new InvalidDataException("This swkotor.exe is not supported. No changes were made.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before installing.",
                    IniOperations.PathForExecutable(targetPath));
            if (IsInstalled(targetPath))
            {
                SafeReport(report, "Replacing the installed KMRP for KPM files.");
                Restore(targetPath, report, null);
            }

            // The final image, built as the standalone installer builds it, from the
            // unmodified executable's bytes this installer carries -- the same for CD
            // 1.03 and Steam, whose code is encrypted on disk. Nothing of it is written
            // to swkotor.exe.
            SafeProgress(progress, 10, "Building KMRP's game changes…");
            byte[] clean = OriginalsImage();
            byte[] final = GoldPatch.Load().ApplyToOriginals(clean, resolution, true);
            byte[] data = BuildData(clean, final);

            string folder = FolderOf(targetPath);
            List<string[]> records = new List<string[]>();
            IniEditState iniState = null;
            DpiCompatibilityEditState dpiState = null;
            NvidiaPresentEditState nvidiaState = null;
            OverrideEditState overrideState = null;
            try
            {
                SafeProgress(progress, 15, "Updating display settings…");
                dpiState = DpiCompatibilityOperations.Install(targetPath, report);
                nvidiaState = NvidiaPresentOperations.Install(targetPath, report);
                iniState = IniOperations.Configure(targetPath, width, height, report);
                overrideState = OverrideOperations.Install(targetPath, resolution, report, progress);

                SafeProgress(progress, 96, "Writing KMRP's data for KOTOR Patch Manager…");
                WriteOwned(folder, DataName, data, records);
                for (int i = 0; i < SupportResources.Length; i++)
                    WriteOwned(folder, SupportFiles[i], ReadResource(SupportResources[i]), records);
                // The controller's settings are the player's to edit: written only when
                // absent, and claimed only then, as the standalone installer does.
                string settings = Path.Combine(folder, ControllerOperations.SettingsName);
                if (!File.Exists(settings))
                    WriteOwned(folder, ControllerOperations.SettingsName,
                        new UTF8Encoding(false).GetBytes(ControllerOperations.DefaultSettings), records);
                WriteManifest(targetPath, width, height, records);
            }
            catch
            {
                RemoveOwned(folder, records, null);
                try { File.Delete(ManifestPath(targetPath)); }
                catch { }
                OverrideOperations.Rollback(overrideState);
                try { IniOperations.Rollback(iniState); }
                catch { }
                try { DpiCompatibilityOperations.Rollback(dpiState); }
                catch { }
                NvidiaPresentOperations.Rollback(nvidiaState);
                throw;
            }
            SafeProgress(progress, 100, "Installed");
            SafeReport(report, "KMRP for KPM is installed for " +
                width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture) + ". swkotor.exe was not modified.");
            SafeReport(report, "Now open KOTOR Patch Manager and tick KMRP, plus whichever of " +
                "KMRP Controller, KMRP Movies and KMRP Map Notes you want. KMRP includes the " +
                "4 GB, texture, grass and save-game memory fixes, so leave KPM's own ones " +
                "unticked. Press Apply, and start the game with Launch.");
            if (steam)
                SafeReport(report, "Steam: in KOTOR Patch Manager choose the proxy deployment, " +
                    "and start the game from Steam. Steam's swkotor.exe cannot take the 4 GB flag.");
        }

        internal static void Restore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            SafeProgress(progress, 0, "Preparing to restore…");
            targetPath = Path.GetFullPath(targetPath);
            string folder = FolderOf(targetPath);
            OverrideOperations.Restore(targetPath, report, progress);
            RemoveOwned(folder, ReadRecords(targetPath), report);
            DpiCompatibilityOperations.Restore(targetPath, report);
            NvidiaPresentOperations.Restore(targetPath, report);
            SafeProgress(progress, 92, "Restoring display settings…");
            IniOperations.Restore(targetPath, report);
            try { File.Delete(ManifestPath(targetPath)); }
            catch { }
            SafeProgress(progress, 100, "Restore complete");
            SafeReport(report, "KMRP for KPM's files and settings have been removed. " +
                "Untick KMRP in KOTOR Patch Manager and press Apply to finish.");
        }

        // ------------------------------------------------------------ the data file

        /// <summary>kmrp-kpm.dat: how <paramref name="final"/> differs from
        /// <paramref name="clean"/>, for K1KpmApplier.cpp, whose header describes the
        /// format. <paramref name="final"/> is built with the map notes enabled; the
        /// data file carries them as KMRP Map Notes' edit. Public to the assembly so a
        /// test can build one without installing.</summary>
        internal static byte[] BuildData(byte[] clean, byte[] final)
        {
            List<Section> original = Sections(clean);
            List<Section> patched = Sections(final);
            List<Relocation> relocations = LoadRelocations();

            // The block: gold's eleven appended sections, 4 KB each, from BlockVa.
            List<Section> block = patched.FindAll(s => s.Va >= BlockVa);
            if (block.Count != BlockSections)
                throw new InvalidDataException("The patched image does not carry KMRP's " +
                    BlockSections + " code sections.");
            for (int i = 0; i < block.Count; i++)
                if (block[i].Va != BlockVa + (uint)(i * 0x1000) || block[i].RawSize != 0x1000)
                    throw new InvalidDataException("KMRP's code sections are not where this build expects them.");
            byte[] blockBytes = new byte[BlockSize];
            Buffer.BlockCopy(final, block[0].RawOffset, blockBytes, 0, BlockSize);

            // KMRP Map Notes: the .kmn enable flag, cleared in the block and set again by
            // the edit when that patch is ticked.
            int flag = checked((int)ResolutionPatch.MapNoteFlagOffset) - block[0].RawOffset;
            if (flag < 0 || flag + 4 > BlockSize || BitConverter.ToInt32(blockBytes, flag) == 0)
                throw new InvalidDataException("The map-note flag is not set in KMRP's code sections.");
            byte[] mapNotes = new byte[4];
            Buffer.BlockCopy(blockBytes, flag, mapNotes, 0, 4);
            Array.Clear(blockBytes, flag, 4);
            uint flagVa = BlockVa + (uint)flag;
            foreach (Relocation r in relocations)
                if (r.Field < flagVa + 4 && r.Field + 4 > flagVa)
                    throw new InvalidDataException("A relocation overlaps the map-note flag.");

            // KMRP Movies: the four movie display-mode operands, and every run that
            // enters the movie aspect fit's section.
            Section kmv = block.Find(s => s.Name == ".kmv");
            if (kmv == null)
                throw new InvalidDataException("KMRP's movie section (.kmv) is missing.");
            List<uint> movieOperands = new List<uint>();
            foreach (long offset in ResolutionPatch.MovieWidthOffsets)
                movieOperands.Add(VaOf(original, offset));
            foreach (long offset in ResolutionPatch.MovieHeightOffsets)
                movieOperands.Add(VaOf(original, offset));

            // Which bytes of the original image change, plus every IN field whole, so the
            // module can add its delta to a field inside one run.
            Dictionary<uint, bool> inField = new Dictionary<uint, bool>();
            foreach (Relocation r in relocations)
                if (r.Kind == KindIn)
                    for (uint b = 0; b < 4; b++)
                        inField[r.Field + b] = true;

            List<KeyValuePair<uint, int>> runs = new List<KeyValuePair<uint, int>>();
            foreach (Section s in original)
            {
                int start = -1;
                for (int i = 0; i <= s.RawSize; i++)
                {
                    bool changed = i < s.RawSize &&
                        (clean[s.RawOffset + i] != final[s.RawOffset + i] || inField.ContainsKey(s.Va + (uint)i));
                    if (changed && start < 0)
                        start = i;
                    else if (!changed && start >= 0)
                    {
                        runs.Add(new KeyValuePair<uint, int>(s.Va + (uint)start, i - start));
                        start = -1;
                    }
                }
            }
            foreach (Relocation r in relocations)
            {
                if (r.Kind == KindIn && !runs.Exists(run => r.Field >= run.Key && r.Field + 4 <= run.Key + run.Value))
                    throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                        "Relocation {0:X8} is not inside a changed run.", r.Field));
                if ((r.Kind == KindOut || r.Kind == KindAbs) &&
                    (r.Field < BlockVa || r.Field + 4 > BlockVa + BlockSize))
                    throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                        "Relocation {0:X8} is not inside KMRP's code sections.", r.Field));
            }

            // Each run belongs to one patch, and a Movies run holds nothing else: an
            // operand run lies within its operand, and an entry run leads only into .kmv.
            List<uint> features = new List<uint>();
            foreach (KeyValuePair<uint, int> run in runs)
            {
                uint start = run.Key, end = run.Key + (uint)run.Value;
                uint feature = FeatureCore;
                foreach (uint operand in movieOperands)
                    if (start < operand + 4 && end > operand)
                    {
                        if (start < operand || end > operand + 4)
                            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                                "The run at {0:X8} holds more than the movie operand at {1:X8}.", start, operand));
                        feature = FeatureMovies;
                    }
                bool intoMovies = false, elsewhere = false;
                foreach (Relocation r in relocations)
                {
                    if (r.Kind != KindIn || r.Field < start || r.Field + 4 > end)
                        continue;
                    int offset = OffsetOf(original, r.Field);
                    uint value = BitConverter.ToUInt32(final, offset);
                    uint relative = unchecked(r.Field + 4 + value);
                    uint target = relative >= BlockVa && relative < BlockVa + BlockSize ? relative : value;
                    if (target >= kmv.Va && target < kmv.Va + (uint)kmv.RawSize)
                        intoMovies = true;
                    else
                        elsewhere = true;
                }
                if (intoMovies)
                {
                    if (elsewhere || feature == FeatureMovies)
                        throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                            "The run at {0:X8} enters the movie section and does something else too.", start));
                    feature = FeatureMovies;
                }
                features.Add(feature);
            }

            using (MemoryStream stream = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(stream))
            {
                writer.Write(Encoding.ASCII.GetBytes("KMRPKPM2"));
                writer.Write(2u);
                writer.Write(BlockVa);
                writer.Write((uint)BlockSize);
                writer.Write((uint)BlockSections);
                foreach (Section s in block)
                    // IMAGE_SCN_MEM_WRITE: .kfs keeps a cache in its own page.
                    writer.Write((s.Characteristics & 0x80000000u) != 0 ? 0x40u : 0x20u);
                writer.Write(blockBytes);
                writer.Write((uint)runs.Count);
                for (int i = 0; i < runs.Count; i++)
                {
                    int offset = OffsetOf(original, runs[i].Key);
                    writer.Write(features[i]);
                    writer.Write(runs[i].Key);
                    writer.Write((uint)runs[i].Value);
                    writer.Write(clean, offset, runs[i].Value);
                    writer.Write(final, offset, runs[i].Value);
                }
                writer.Write(1u);
                writer.Write(FeatureMapNotes);
                writer.Write((uint)flag);
                writer.Write((uint)mapNotes.Length);
                writer.Write(mapNotes);
                writer.Write((uint)relocations.Count);
                foreach (Relocation r in relocations)
                {
                    writer.Write(r.Kind);
                    writer.Write(r.Field);
                }
                writer.Flush();
                byte[] body = stream.ToArray();
                uint hash = 2166136261u;
                foreach (byte b in body)
                {
                    hash ^= b;
                    hash *= 16777619u;
                }
                byte[] result = new byte[body.Length + 4];
                Buffer.BlockCopy(body, 0, result, 0, body.Length);
                Buffer.BlockCopy(BitConverter.GetBytes(hash), 0, result, body.Length, 4);
                return result;
            }
        }

        private static List<Section> Sections(byte[] image)
        {
            int pe = BitConverter.ToInt32(image, 0x3C);
            int count = BitConverter.ToUInt16(image, pe + 6);
            int optional = BitConverter.ToUInt16(image, pe + 20);
            uint imageBase = BitConverter.ToUInt32(image, pe + 24 + 28);
            List<Section> sections = new List<Section>();
            for (int i = 0; i < count; i++)
            {
                int o = pe + 24 + optional + 40 * i;
                sections.Add(new Section
                {
                    Name = Encoding.ASCII.GetString(image, o, 8).TrimEnd('\0'),
                    Va = imageBase + BitConverter.ToUInt32(image, o + 12),
                    RawSize = BitConverter.ToInt32(image, o + 16),
                    RawOffset = BitConverter.ToInt32(image, o + 20),
                    Characteristics = BitConverter.ToUInt32(image, o + 36),
                });
            }
            return sections;
        }

        private static uint VaOf(List<Section> sections, long fileOffset)
        {
            foreach (Section s in sections)
                if (fileOffset >= s.RawOffset && fileOffset < s.RawOffset + (long)s.RawSize)
                    return s.Va + (uint)(fileOffset - s.RawOffset);
            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                "File offset {0:X} is not in the executable's raw data.", fileOffset));
        }

        private static int OffsetOf(List<Section> sections, uint va)
        {
            foreach (Section s in sections)
                if (va >= s.Va && va < s.Va + (uint)s.RawSize)
                    return s.RawOffset + (int)(va - s.Va);
            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                "{0:X8} is not in the executable's raw data.", va));
        }

        private static List<Relocation> LoadRelocations()
        {
            string text = Encoding.ASCII.GetString(ReadResource(RelocationResource));
            List<Relocation> relocations = new List<Relocation>();
            bool goldMatches = false;
            foreach (string raw in text.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0)
                    continue;
                if (line.StartsWith("#", StringComparison.Ordinal))
                {
                    if (line.IndexOf(GoldPatch.TargetHash, StringComparison.OrdinalIgnoreCase) >= 0)
                        goldMatches = true;
                    continue;
                }
                string[] parts = line.Split(' ');
                uint kind = parts[0] == "IN" ? KindIn : parts[0] == "OUT" ? KindOut : parts[0] == "ABS" ? KindAbs : 0;
                uint field;
                if (parts.Length != 2 || kind == 0 ||
                    !UInt32.TryParse(parts[1], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out field))
                    throw new InvalidDataException("The embedded relocation table is damaged: " + line);
                relocations.Add(new Relocation { Kind = kind, Field = field });
            }
            // Computed from a different gold would move the wrong bytes.
            if (!goldMatches)
                throw new InvalidDataException("The embedded relocation table was computed from a different gold build.");
            return relocations;
        }

        /// <summary>Build-time: every field ResolutionPatch reads or writes, at all 49
        /// resolutions, as "FILE offset size" lines, for tools/kpm_originals.py. The
        /// installer needs the unmodified executable's bytes under each whole field --
        /// gold changed only some bytes of some fields, and none of a few (the powers
        /// row height stays vanilla's 40 in gold) -- and this list is ResolutionPatch's
        /// own, so it cannot drift from the fields it writes.</summary>
        internal static void WriteResolutionSites(string cleanExe, string outPath)
        {
            byte[] source = File.ReadAllBytes(cleanExe);
            GoldPatch gold = GoldPatch.Load();
            SortedDictionary<long, int> sites = new SortedDictionary<long, int>();
            ResolutionPatch.Touched = new List<long[]>();
            try
            {
                foreach (ResolutionChoice resolution in ResolutionCatalog.Load())
                    gold.Apply(source, resolution, true);
                foreach (long[] touched in ResolutionPatch.Touched)
                {
                    int size;
                    if (!sites.TryGetValue(touched[0], out size) || size < touched[1])
                        sites[touched[0]] = (int)touched[1];
                }
            }
            finally
            {
                ResolutionPatch.Touched = null;
            }
            StringBuilder text = new StringBuilder("# ResolutionPatch's fields, FILE offset and size, from all 49 resolutions\r\n");
            foreach (KeyValuePair<long, int> site in sites)
                text.Append(site.Key.ToString("X", CultureInfo.InvariantCulture)).Append(' ')
                    .Append(site.Value.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            File.WriteAllText(outPath, text.ToString(), new UTF8Encoding(false));
        }

        /// <summary>A picture of CD 1.03 as long as the file: its bytes where
        /// tools/kpm_originals.py carried them (the header, under gold's chunks, the
        /// relocated fields), zero elsewhere. Enough for BuildData, which records only
        /// where gold differs from the unmodified executable.</summary>
        internal static byte[] OriginalsImage()
        {
            byte[] resource = ReadResource(OriginalsResource);
            if (resource.Length < 48 || Encoding.ASCII.GetString(resource, 0, 8) != "KMRPORG1")
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged.");
            uint hash = 2166136261u;
            for (int i = 0; i < resource.Length - 4; i++)
            {
                hash ^= resource[i];
                hash *= 16777619u;
            }
            if (hash != BitConverter.ToUInt32(resource, resource.Length - 4))
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (checksum).");
            StringBuilder source = new StringBuilder();
            for (int i = 8; i < 40; i++)
                source.Append(resource[i].ToString("X2", CultureInfo.InvariantCulture));
            if (source.ToString() != GoldPatch.SourceHash)
                throw new InvalidDataException("The embedded unmodified-executable bytes are from a different executable.");

            byte[] image = new byte[GoldPatch.SourceLength];
            int count = BitConverter.ToInt32(resource, 40);
            int at = 44;
            for (int i = 0; i < count; i++)
            {
                int offset = BitConverter.ToInt32(resource, at);
                int length = BitConverter.ToInt32(resource, at + 4);
                at += 8;
                if (offset < 0 || length <= 0 || offset + (long)length > image.Length ||
                    at + (long)length > resource.Length - 4)
                    throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (range).");
                Buffer.BlockCopy(resource, at, image, offset, length);
                at += length;
            }
            if (at != resource.Length - 4)
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (length).");
            return image;
        }

        private static byte[] ReadResource(string name)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (stream == null)
                    throw new InvalidDataException("This build does not carry " + name + ".");
                using (MemoryStream copy = new MemoryStream())
                {
                    stream.CopyTo(copy);
                    return copy.ToArray();
                }
            }
        }

        // ------------------------------------------------------------ owned files

        private static void WriteOwned(string folder, string name, byte[] data, List<string[]> records)
        {
            string target = Path.Combine(folder, name);
            if (File.Exists(target))
            {
                // Never clobber a file this installer did not write.
                bool ours = false;
                foreach (string[] record in records)
                    if (String.Equals(record[0], name, StringComparison.OrdinalIgnoreCase))
                        ours = true;
                if (!ours)
                    throw new IOException("Left the existing " + name + " alone; KMRP for KPM was not installed. " +
                        "Move it aside and try again.");
            }
            File.WriteAllBytes(target, data);
            records.Add(new[] { name, GoldPatch.HashFile(target) });
        }

        private static void RemoveOwned(string folder, List<string[]> records, Action<string> report)
        {
            int kept = 0;
            foreach (string[] record in records)
            {
                string target = Path.Combine(folder, record[0]);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record[1])
                {
                    kept++;
                    continue;
                }
                File.Delete(target);
            }
            if (kept > 0)
                SafeReport(report, "Left " + kept.ToString(CultureInfo.InvariantCulture) +
                    " file(s) in place because they changed after install.");
        }

        private static void WriteManifest(string targetPath, int width, int height, List<string[]> records)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(GoldPatch.PatchVersion).Append("\r\n");
            text.Append("resolution\t").Append(width.ToString(CultureInfo.InvariantCulture)).Append('\t')
                .Append(height.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            foreach (string[] record in records)
                text.Append("file\t").Append(record[0]).Append('\t').Append(record[1]).Append("\r\n");
            File.WriteAllText(ManifestPath(targetPath), text.ToString(), new UTF8Encoding(false));
        }

        private static List<string[]> ReadRecords(string targetPath)
        {
            List<string[]> records = new List<string[]>();
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length == 3 && parts[0] == "file")
                        records.Add(new[] { parts[1], parts[2] });
                }
            }
            catch { }
            return records;
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report != null)
                report(message);
        }

        private static void SafeProgress(Action<int, string> progress, int value, string message)
        {
            if (progress != null)
                progress(value, message);
        }
    }
}
