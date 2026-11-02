// The Windows installer's portable core: the game facts, the file, INI and patch operations,
// the settings and the update check. Split from KmrpPatcher.cs on 2026-10-30, unchanged, so the
// native Linux installer (docs/linux-appimage-installer.md) compiles the same rules: nothing in
// this file may use WinForms, GDI+, the registry or NvAPI. What an install needs from the
// system it runs on goes through InstallPlatform.
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using Microsoft.Win32;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>A path in the game's folder, for the system the installer runs on (2026-10-30).
    /// KMRP's records and constants name files relative to the game folder with '\' (KMRP\kpm.manifest,
    /// patches\kmrp.dll), and keep doing so: a game installed from Windows is restored from Linux
    /// and the other way round, through the same records. Joined to a real folder, the names are
    /// written with the system's own separator; on Windows that changes nothing.</summary>
    internal static class GamePath
    {
        internal static string Combine(params string[] parts)
        {
            if (Path.DirectorySeparatorChar != '\\')
                for (int i = 0; i < parts.Length; i++)
                    if (parts[i] != null)
                        parts[i] = parts[i].Replace('\\', Path.DirectorySeparatorChar);
            return Path.Combine(parts);
        }
    }

    internal enum ExecutableState
    {
        Missing,
        SupportedClean,
        Gold,
        Unsupported,
        Error
    }

    internal static class PeCompatibility
    {
        // IMAGE_FILE_HEADER.Characteristics in the supported PE32 executable.
        // The common "4 GB patcher" changes only IMAGE_FILE_LARGE_ADDRESS_AWARE.
        internal const int CharacteristicsOffset = 0x926;
        internal const ushort OriginalCharacteristics = 0x010F;
        internal const ushort LargeAddressAwareFlag = 0x0020;
        internal const ushort LargeAddressAwareCharacteristics =
            OriginalCharacteristics | LargeAddressAwareFlag;
        internal const string LargeAddressAwareSourceHash =
            "CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889";

        internal static ushort ReadCharacteristics(byte[] executable)
        {
            if (executable == null || executable.Length < CharacteristicsOffset + 2)
                throw new InvalidDataException("The executable is too short to contain a PE file header.");
            return (ushort)(executable[CharacteristicsOffset] |
                (executable[CharacteristicsOffset + 1] << 8));
        }

        internal static bool TryNormalizeSupportedSource(byte[] source, out byte[] normalized)
        {
            normalized = null;
            if (source == null || source.LongLength != GoldPatch.SourceLength)
                return false;
            ushort characteristics = ReadCharacteristics(source);
            if (characteristics != OriginalCharacteristics &&
                characteristics != LargeAddressAwareCharacteristics)
                return false;

            normalized = (byte[])source.Clone();
            normalized[CharacteristicsOffset] = (byte)(OriginalCharacteristics & 0xFF);
            normalized[CharacteristicsOffset + 1] = (byte)(OriginalCharacteristics >> 8);
            string hash = GoldPatch.HashBytes(normalized);
            if (hash == GameExecutable.Gog.Hash)
            {
                // GOG's file is the Editable one without its watermark (GameExecutable):
                // with it put back, the image is the build gold was made from.
                Buffer.BlockCopy(GameExecutable.Watermark, 0, normalized, GameExecutable.WatermarkOffset,
                    GameExecutable.Watermark.Length);
                hash = GoldPatch.HashBytes(normalized);
            }
            if (hash != GoldPatch.SourceHash)
            {
                normalized = null;
                return false;
            }
            return true;
        }

    }

    /// <summary>The swkotor.exe builds KMRP installs on, told apart by SHA-256 alone.
    /// The patcher's second step names the one it finds.
    ///
    ///   Editable  KOTOR 1.03 as the KOTOR Editable Executable ships it, 761F9466...
    ///             (GoldPatch.SourceHash), which KOTOR Patch Manager calls "HellSpawn
    ///             CD Crack version 1.0.3" (kotor1_cdcrack_103): the build every KMRP
    ///             patch site was measured on.
    ///   GOG       GOG's own v1.03, 9C10E045... (kotor1_gog_103): the same file with
    ///             the 16 bytes of "Hellspawn Reborn" at FILE 0x000AC0, header padding
    ///             that nothing reads, zeroed. Zeroing them in the Editable file gives
    ///             GOG's SHA-256 exactly (checked 2026-09-30), so every byte KMRP reads
    ///             or writes is the same in both; gold's fifth section header lands on
    ///             those 16 bytes anyway (reverse-engineering/binary-inventory.md).
    ///   Steam     Steam's, 34E6D971... (kotor1_steam_103): the same program behind
    ///             SteamStub, which refuses to start a changed file, so it never takes
    ///             the 4 GB flag.
    ///
    /// Editable and GOG are also known with the 4 GB flag set, as KMRP's install leaves
    /// them: IMAGE_FILE_LARGE_ADDRESS_AWARE in the header's Characteristics, the one
    /// change PeCompatibility makes. Those two hashes were computed from the unmodified
    /// files by setting the flag.</summary>
    internal sealed class GameExecutable
    {
        internal const int WatermarkOffset = 0x000AC0;
        internal static readonly byte[] Watermark = Encoding.ASCII.GetBytes("Hellspawn Reborn");

        internal static readonly GameExecutable Editable = new GameExecutable("Editable",
            GoldPatch.SourceHash, PeCompatibility.LargeAddressAwareSourceHash, GoldPatch.SourceLength);
        internal static readonly GameExecutable Gog = new GameExecutable("GOG",
            "9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435",
            "01B808251B3EE85F86F4C893FD4EE1A0448F94D9316FE9B09BD8B222C2B4132F", GoldPatch.SourceLength);
        internal static readonly GameExecutable Steam = new GameExecutable("Steam",
            GoldPatch.SteamHash, null, GoldPatch.SteamLength);
        private static readonly GameExecutable[] All = { Editable, Gog, Steam };

        internal readonly string Name;
        internal readonly string Hash;
        internal readonly string LargeAddressAwareHash;   // null: Steam never takes the flag
        internal readonly long Length;

        private GameExecutable(string name, string hash, string largeAddressAwareHash, long length)
        {
            Name = name;
            Hash = hash;
            LargeAddressAwareHash = largeAddressAwareHash;
            Length = length;
        }

        internal bool IsSteam
        {
            get { return this == Steam; }
        }

        /// <summary>KOTOR Patch Manager's Distribution for kpm_install_state.json: GOG 0
        /// (its table has CD 1.03 there too), Steam 1.</summary>
        internal int KpmDistribution
        {
            get { return IsSteam ? 1 : 0; }
        }

        /// <summary>Which build this file is, unmodified or with the 4 GB flag; null for
        /// any other file, a missing one or one that cannot be read.</summary>
        internal static GameExecutable Identify(string path)
        {
            try
            {
                if (String.IsNullOrWhiteSpace(path) || !File.Exists(path))
                    return null;
                long length = new FileInfo(path).Length;
                if (length != GoldPatch.SourceLength && length != GoldPatch.SteamLength)
                    return null;
                return ForHash(GoldPatch.HashFile(path));
            }
            catch
            {
                return null;
            }
        }

        internal static GameExecutable ForHash(string hash)
        {
            foreach (GameExecutable exe in All)
                if (hash == exe.Hash || (exe.LargeAddressAwareHash != null && hash == exe.LargeAddressAwareHash))
                    return exe;
            return null;
        }
    }

    // Legacy executable identities are retained for validation and restoration.
    internal static class GoldPatch
    {
        internal const string SourceHash = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886";
        // Steam's swkotor.exe (KOTOR Patch Manager's kotor1_steam_103): CD 1.03's program
        // behind SteamStub, which refuses to start if the file changes at all
        // ("Application load error 3:0000065432", measured 2026-09-28). Only the KPM
        // edition supports it, in memory; the standalone cannot patch it.
        internal const string SteamHash = "34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88";
        internal const long SteamLength = 4395008;
        internal const string TargetHash = "9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A";
        internal const long SourceLength = 4042752;
        internal const long TargetLength = 4087808;
        internal const string PatchVersion = "1.6.0";

        internal static bool IsSupportedSourceFile(string path)
        {
            try
            {
                byte[] normalized;
                return File.Exists(path) &&
                    PeCompatibility.TryNormalizeSupportedSource(File.ReadAllBytes(path), out normalized);
            }
            catch
            {
                return false;
            }
        }

        internal static string HashFile(string path)
        {
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (SHA256 sha = SHA256.Create())
                return ToHex(sha.ComputeHash(stream));
        }

        internal static string HashBytes(byte[] data)
        {
            using (SHA256 sha = SHA256.Create())
                return ToHex(sha.ComputeHash(data));
        }

        private static string ToHex(byte[] data)
        {
            StringBuilder result = new StringBuilder(data.Length * 2);
            foreach (byte value in data)
                result.Append(value.ToString("X2", CultureInfo.InvariantCulture));
            return result.ToString();
        }
    }

    internal sealed class ResolutionChoice
    {
        internal readonly string Category;
        internal readonly int Width;
        internal readonly int Height;
        internal readonly int CanvasWidth;
        internal readonly int CanvasHeight;
        internal readonly int OverlayWidth;
        internal readonly int CenteringWidth;
        internal readonly int CenteringHeight;
        /// <summary>The listed set whose files install: this size's own, or for a size
        /// the build has no set for, the nearest one (ResolutionCatalog.Nearest), whose
        /// fonts and art install and whose .gui files GuiBlend replaces.</summary>
        internal readonly string SetKey;
        private readonly string displayName;

        internal ResolutionChoice(string category, int width, int height, int canvasWidth, int canvasHeight,
            int overlayWidth, int centeringWidth, int centeringHeight)
            : this(category, width, height, canvasWidth, canvasHeight, overlayWidth, centeringWidth,
                   centeringHeight, null)
        {
        }

        private ResolutionChoice(string category, int width, int height, int canvasWidth, int canvasHeight,
            int overlayWidth, int centeringWidth, int centeringHeight, string setKey)
        {
            Category = category;
            Width = width;
            Height = height;
            CanvasWidth = canvasWidth;
            CanvasHeight = canvasHeight;
            OverlayWidth = overlayWidth;
            CenteringWidth = centeringWidth;
            CenteringHeight = centeringHeight;
            SetKey = setKey ?? Key;
            displayName = category + "   ·   " + width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture);
        }

        /// <summary>A size with its map fields computed as the catalogue's are
        /// (tools/analyze_resolution_guis.py: the overlay W/2 by H/2, the canvas
        /// round(overlay * 512/440) wide, centring at the screen), which every one of
        /// the 66 listed rows equals (checked 2026-09-30).</summary>
        internal static ResolutionChoice ForSize(string category, int width, int height, string setKey)
        {
            int overlay = width / 2;
            return new ResolutionChoice(category, width, height,
                (int)Math.Round(overlay * 512 / 440.0), height / 2, overlay, width, height, setKey);
        }

        /// <summary>The same size under another name in the list ("This display").</summary>
        internal ResolutionChoice Relabel(string category)
        {
            return new ResolutionChoice(category, Width, Height, CanvasWidth, CanvasHeight, OverlayWidth,
                CenteringWidth, CenteringHeight, SetKey);
        }

        internal string Key
        {
            get
            {
                return Width.ToString(CultureInfo.InvariantCulture) + "x" +
                    Height.ToString(CultureInfo.InvariantCulture);
            }
        }

        /// <summary>No set of its own: its menus are blended at install.</summary>
        internal bool Blended
        {
            get { return SetKey != Key; }
        }

        public override string ToString()
        {
            return displayName;
        }
    }

    internal static class ResolutionCatalog
    {
        private const string ResourceName = "Kmrp.resolutions";
        private static readonly Dictionary<string, bool> covered = new Dictionary<string, bool>();

        /// <summary>Whether KMRP covers WIDTHxHEIGHT: a listed size or one the blend reaches.
        /// The installers offer only these (moved from ResolutionSelection.Covered on 2026-10-30,
        /// unchanged, so the Linux installer offers the same).</summary>
        internal static bool Covers(int width, int height)
        {
            string key = width.ToString(CultureInfo.InvariantCulture) + "x" + height.ToString(CultureInfo.InvariantCulture);
            bool known;
            if (covered.TryGetValue(key, out known))
                return known;
            try { Find(width, height); known = true; }
            catch (ArgumentException) { known = false; }
            catch (InvalidDataException) { known = false; }
            covered[key] = known;
            return known;
        }

        internal static List<ResolutionChoice> Load()
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName);
            if (stream == null)
                throw new InvalidDataException("The bundled resolution catalog is missing.");

            List<ResolutionChoice> choices = new List<ResolutionChoice>();
            using (stream)
            using (StreamReader reader = new StreamReader(stream, Encoding.UTF8, true))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (String.IsNullOrWhiteSpace(line) || line.StartsWith("#", StringComparison.Ordinal))
                        continue;
                    string[] fields = line.Split('\t');
                    if (fields.Length != 8)
                        throw new InvalidDataException("The bundled resolution catalog is damaged.");
                    int[] values = new int[7];
                    for (int index = 0; index < values.Length; index++)
                    {
                        if (!Int32.TryParse(fields[index + 1], NumberStyles.Integer,
                            CultureInfo.InvariantCulture, out values[index]))
                            throw new InvalidDataException("The bundled resolution catalog contains an invalid number.");
                    }
                    choices.Add(new ResolutionChoice(fields[0], values[0], values[1], values[2], values[3],
                        values[4], values[5], values[6]));
                }
            }
            // 48 upstream resolutions plus 2880x1620, derived since 2026-09-25 (issue #16),
            // plus 17 Mac displays (category "macOS"), derived since 2026-09-29.
            if (choices.Count != 66)
                throw new InvalidDataException("The bundled resolution catalog is incomplete.");
            return choices;
        }

        /// <summary>A listed size, or any other the menu sets reach (Derived).</summary>
        internal static ResolutionChoice Find(int width, int height)
        {
            List<ResolutionChoice> listed = Load();
            foreach (ResolutionChoice choice in listed)
            {
                if (choice.Width == width && choice.Height == height)
                    return choice;
            }
            return Derived("Custom", width, height, listed);
        }

        /// <summary>A size the catalogue does not list, installed as the Mac installer
        /// installs one (macos/kmrp-mac.sh): the nearest listed set's fonts and art, and
        /// .gui files GuiBlend blends from the finished sets around it. Throws when those
        /// sets do not reach it.</summary>
        internal static ResolutionChoice Derived(string category, int width, int height, List<ResolutionChoice> listed)
        {
            if (!GuiBlend.Shared().Covers(width, height))
                throw new ArgumentException(OutOfReach(width, height));
            return ResolutionChoice.ForSize(category, width, height, Nearest(listed, width, height).Key);
        }

        /// <summary>The listed size nearest WIDTHxHEIGHT, as the Mac installer's
        /// nearest_size picks it: the nearest height (the fonts are baked at
        /// max(1, H / 720)), then the nearest shape, the first in the list on a tie.</summary>
        internal static ResolutionChoice Nearest(List<ResolutionChoice> listed, int width, int height)
        {
            ResolutionChoice best = null;
            double bestHeight = 0, bestShape = 0;
            foreach (ResolutionChoice choice in listed)
            {
                double dh = Math.Abs(choice.Height - height);
                double da = Math.Abs((double)choice.Width / choice.Height - (double)width / height);
                if (best == null || dh < bestHeight || (dh == bestHeight && da < bestShape))
                {
                    best = choice;
                    bestHeight = dh;
                    bestShape = da;
                }
            }
            return best;
        }

        /// <summary>Why a size cannot be installed, with the heights the menu sets reach
        /// at its shape when they reach it at all.</summary>
        internal static string OutOfReach(int width, int height)
        {
            string size = width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture);
            double aspect = (double)width / height;
            int lowest = 0, highest = 0;
            GuiBlend blend = GuiBlend.Shared();
            for (int h = GuiBlend.MinimumHeight; h <= 8640; h++)
            {
                int w = (int)Math.Round(h * aspect);
                if (!blend.Covers(w, h))
                    continue;
                if (lowest == 0)
                    lowest = h;
                highest = h;
            }
            if (lowest == 0)
                return "KMRP's menus do not reach " + size + ": its shape is outside 4:3 to 32:9.";
            return "KMRP's menus do not reach " + size + ". At this shape they reach heights from " +
                lowest.ToString(CultureInfo.InvariantCulture) + " to " +
                highest.ToString(CultureInfo.InvariantCulture) + " pixels.";
        }
    }

    internal sealed class IniEditState
    {
        internal string Path;
        internal byte[] OriginalBytes;
        internal bool Changed;
        internal List<string[]> Rows;   // the manifest's "ini" rows: each key as the install set it
    }

    internal static class IniOperations
    {
        private const string TemporaryInfix = ".kotor-ui-new-";   // KpmEdition.RemoveInProgress clears these
        internal const int DefaultWidth = 3440;
        internal const int DefaultHeight = 1440;
        private const string GraphicsSection = "Graphics Options";

        internal static string PathForExecutable(string executablePath)
        {
            string directory = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            return GamePath.Combine(directory, "swkotor.ini");
        }

        // KMRP\backups\swkotor.ini since 2026-10-20 (KmrpFolder); swkotor.ini.kotor-ui-backup
        // beside the game's until then, and found there until the next install moves it.
        internal static string BackupPath(string executablePath)
        {
            return KmrpFolder.PathOf(executablePath, KmrpFolder.IniBackup);
        }

        private static string BackupHashPath(string executablePath)
        {
            return BackupPath(executablePath) + ".sha256";
        }

        internal static string Describe(string executablePath)
        {
            try
            {
                string iniPath = PathForExecutable(executablePath);
                if (!File.Exists(iniPath))
                    return "swkotor.ini not found";

                int width;
                int height;
                if (!TryReadResolution(iniPath, out width, out height))
                    return "swkotor.ini has no complete [Graphics Options] resolution";
                return "swkotor.ini resolution: " + width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture);
            }
            catch (Exception ex)
            {
                return "Unable to inspect swkotor.ini: " + ex.Message;
            }
        }

        internal static bool HasVerifiedBackup(string executablePath)
        {
            try
            {
                string backupPath = BackupPath(executablePath);
                string hashPath = BackupHashPath(executablePath);
                if (!File.Exists(backupPath) || !File.Exists(hashPath))
                    return false;
                string expectedHash = File.ReadAllText(hashPath, Encoding.ASCII).Trim().ToUpperInvariant();
                return expectedHash.Length == 64 && GoldPatch.HashFile(backupPath) == expectedHash;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>An upgrade keeps the size the player chose in the game, where KMRP can
        /// run at it. `width` and `height` are otherwise the size the install starts at.</summary>
        internal static void KeepChosenSize(string executablePath, ref int width, ref int height, Action<string> report)
        {
            int chosenWidth, chosenHeight;
            string iniPath = PathForExecutable(executablePath);
            if (!File.Exists(iniPath) || !TryReadResolution(iniPath, out chosenWidth, out chosenHeight) ||
                (chosenWidth == width && chosenHeight == height) || !ResolutionCatalog.Covers(chosenWidth, chosenHeight))
                return;
            width = chosenWidth;
            height = chosenHeight;
            SafeReport(report, "Keeping the resolution in swkotor.ini, " +
                width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture) + ".");
        }

        /// <summary>`upgrade`: KMRP is being installed over itself, so swkotor.ini is the
        /// player's as it stands (2026-11-01). The backup stays the one from before KMRP,
        /// and the frame-rate keys are left alone unless High FPS Fix was switched.
        /// Otherwise the backup is taken from the file as it is now: one left by an earlier
        /// install holds settings the player has since changed.</summary>
        internal static IniEditState Configure(string executablePath, int width, int height, bool upgrade,
            Action<string> report)
        {
            string iniPath = PathForExecutable(executablePath);
            if (!File.Exists(iniPath))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before patching.",
                    iniPath);

            byte[] original = File.ReadAllBytes(iniPath);
            EnsureVerifiedBackup(executablePath, original, !upgrade, report);

            Encoding encoding;
            int preambleLength;
            DetectEncoding(original, out encoding, out preambleLength);
            string text = encoding.GetString(original, preambleLength, original.Length - preambleLength);
            string[] current = SplitLines(text);
            bool keepFrameRate = upgrade && KeyValue(current, "AllowHighMonitorFrequency") ==
                (KmrpSettings.HighFpsFix ? "1" : "0");
            string updated = UpdateResolution(text, width, height, keepFrameRate);
            byte[] updatedBytes = Encode(updated, encoding, preambleLength > 0);

            IniEditState state = new IniEditState
            {
                Path = iniPath,
                OriginalBytes = original,
                Changed = !BytesEqual(original, updatedBytes),
                Rows = new List<string[]>()
            };
            string[] written = SplitLines(updated);
            foreach (string key in OwnedKeys)
            {
                string value = KeyValue(written, key);
                if (value != null)
                    state.Rows.Add(new[] { "ini", key, value });
            }

            if (state.Changed)
                WriteBytesAtomically(iniPath, updatedBytes);

            int verifiedWidth;
            int verifiedHeight;
            if (!TryReadResolution(iniPath, out verifiedWidth, out verifiedHeight) ||
                verifiedWidth != width || verifiedHeight != height)
            {
                if (state.Changed)
                    WriteBytesAtomically(iniPath, original);
                throw new IOException("swkotor.ini resolution verification failed.");
            }

            SafeReport(report,
                (state.Changed ? "Updated " : "Verified ") + iniPath + ": Width=" +
                width.ToString(CultureInfo.InvariantCulture) + ", Height=" +
                height.ToString(CultureInfo.InvariantCulture));
            return state;
        }

        internal static void Rollback(IniEditState state)
        {
            if (state != null && state.Changed)
                WriteBytesAtomically(state.Path, state.OriginalBytes);
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            Restore(executablePath, null, report);
        }

        /// <summary>Restore Original, key by key (2026-11-01; until then the whole backup
        /// went back, and everything the player had changed since the first install went
        /// with it). `rows` are the keys the install set and their values, the manifest's
        /// "ini" rows: a key that no longer holds that value is the player's and stays. An
        /// install from before these rows has none, so all its keys go back. KMRP's own
        /// sections go. If nothing else changed the backup's own bytes are written. False
        /// when there is no backup to restore from.</summary>
        internal static bool Restore(string executablePath, List<string[]> rows, Action<string> report)
        {
            string backupPath = BackupPath(executablePath);
            string hashPath = BackupHashPath(executablePath);
            if (!File.Exists(backupPath))
            {
                SafeReport(report, "No swkotor.ini backup exists; INI restore was skipped.");
                return false;
            }
            if (!File.Exists(hashPath))
                throw new InvalidDataException("The swkotor.ini backup verification record is missing. Restore was blocked.");

            string expectedHash = File.ReadAllText(hashPath, Encoding.ASCII).Trim().ToUpperInvariant();
            string actualHash = GoldPatch.HashFile(backupPath);
            if (expectedHash.Length != 64 || actualHash != expectedHash)
                throw new InvalidDataException("The swkotor.ini backup failed its integrity check. Restore was blocked.");

            string iniPath = PathForExecutable(executablePath);
            byte[] backup = File.ReadAllBytes(backupPath);
            if (rows != null && rows.Count == 0)
                rows = null;
            byte[] restored = File.Exists(iniPath) ? MergeOriginalKeys(File.ReadAllBytes(iniPath), backup, rows) : backup;
            WriteBytesAtomically(iniPath, restored);
            if (!BytesEqual(File.ReadAllBytes(iniPath), restored))
                throw new IOException("Post-restore swkotor.ini verification failed.");
            SafeReport(report, BytesEqual(restored, backup)
                ? "Restored the previous swkotor.ini settings."
                : "Put back the swkotor.ini settings KMRP changed; the rest of the file is as you left it.");
            return true;
        }

        // The keys of [Graphics Options] an install sets (UpdateResolution).
        private static readonly string[] OwnedKeys =
            { "Height", "Width", "AllowHighMonitorFrequency", "RefreshRate", "V-Sync" };

        private static string[] SplitLines(string text)
        {
            return Regex.Split(text, "\\r\\n|\\n|\\r");
        }

        // A key's line in [Graphics Options], or -1.
        private static int KeyLine(IList<string> lines, string key)
        {
            bool inGraphics = false;
            for (int index = 0; index < lines.Count; index++)
            {
                string sectionName;
                if (TryGetSectionName(lines[index], out sectionName))
                {
                    inGraphics = String.Equals(sectionName, GraphicsSection, StringComparison.OrdinalIgnoreCase);
                    continue;
                }
                int equals = lines[index].IndexOf('=');
                if (inGraphics && equals >= 0 &&
                    String.Equals(lines[index].Substring(0, equals).Trim(), key, StringComparison.OrdinalIgnoreCase))
                    return index;
            }
            return -1;
        }

        private static string KeyValue(IList<string> lines, string key)
        {
            int index = KeyLine(lines, key);
            return index < 0 ? null : lines[index].Substring(lines[index].IndexOf('=') + 1).Trim();
        }

        private static bool IsKmrpSection(string name)
        {
            return name.StartsWith("KMRP", StringComparison.OrdinalIgnoreCase);
        }

        private static byte[] MergeOriginalKeys(byte[] current, byte[] backup, List<string[]> rows)
        {
            Encoding encoding;
            int preambleLength;
            DetectEncoding(current, out encoding, out preambleLength);
            string text = encoding.GetString(current, preambleLength, current.Length - preambleLength);
            string newline = text.IndexOf("\r\n", StringComparison.Ordinal) >= 0 ? "\r\n" : "\n";
            Encoding backupEncoding;
            int backupPreamble;
            DetectEncoding(backup, out backupEncoding, out backupPreamble);
            string[] before = SplitLines(backupEncoding.GetString(backup, backupPreamble, backup.Length - backupPreamble));

            List<string> lines = new List<string>();
            bool inKmrp = false;
            foreach (string line in SplitLines(text))
            {
                string sectionName;
                if (TryGetSectionName(line, out sectionName))
                    inKmrp = IsKmrpSection(sectionName);
                if (!inKmrp)
                    lines.Add(line);
            }
            foreach (string key in OwnedKeys)
            {
                int index = KeyLine(lines, key);
                string[] row = rows == null ? null : rows.Find(r => r[1] == key);
                if (index >= 0 && rows != null && (row == null ||
                    !String.Equals(KeyValue(lines, key), row[2], StringComparison.Ordinal)))
                    continue;   // the player's since the install
                int original = KeyLine(before, key);
                if (index >= 0 && original >= 0)
                    lines[index] = before[original];
                else if (index >= 0)
                    lines.RemoveAt(index);
            }
            // Nothing but KMRP's keys differed: the file exactly as it was, whatever order
            // the install left the lines in.
            List<string> sortedNow = lines.FindAll(l => l.Trim().Length > 0);
            List<string> sortedBefore = new List<string>(before).FindAll(l => l.Trim().Length > 0);
            sortedNow.Sort(StringComparer.Ordinal);
            sortedBefore.Sort(StringComparer.Ordinal);
            if (sortedNow.Count == sortedBefore.Count)
            {
                bool same = true;
                for (int index = 0; same && index < sortedNow.Count; index++)
                    same = sortedNow[index] == sortedBefore[index];
                if (same)
                    return backup;
            }
            return Encode(String.Join(newline, lines.ToArray()), encoding, preambleLength > 0);
        }

        private static void EnsureVerifiedBackup(string executablePath, byte[] original, bool refresh, Action<string> report)
        {
            string backupPath = BackupPath(executablePath);
            string hashPath = BackupHashPath(executablePath);
            string originalHash = HashBytes(original);

            if (File.Exists(backupPath))
            {
                if (!File.Exists(hashPath))
                    throw new InvalidDataException("An incomplete swkotor.ini backup already exists. Move it aside before patching:\r\n" + backupPath);
                string expected = File.ReadAllText(hashPath, Encoding.ASCII).Trim().ToUpperInvariant();
                if (expected.Length != 64 || GoldPatch.HashFile(backupPath) != expected)
                    throw new InvalidDataException("The existing swkotor.ini backup failed its integrity check. Move it aside before patching:\r\n" + backupPath);
                if (!refresh || expected == originalHash)
                    return;
                File.Delete(backupPath);
                File.Delete(hashPath);
            }

            // The hash first and the backup in one step: stopped at any point there is either
            // no backup or a whole one with its hash. A kill between the two the other way round
            // left a backup with no hash, and every later install refused it (Test-InstallerPatch
            // Case 17 at 250 ms, 2026-11-01).
            File.WriteAllText(hashPath, originalHash + "\r\n", Encoding.ASCII);
            try
            {
                WriteBytesAtomically(backupPath, original);
                if (GoldPatch.HashFile(backupPath) != originalHash)
                    throw new IOException("swkotor.ini backup verification failed. No INI change was applied.");
            }
            catch
            {
                FileGuard.Discard(backupPath);
                FileGuard.Discard(hashPath);
                throw;
            }
            SafeReport(report, "INI backup created: " + backupPath);
        }

        private static string UpdateResolution(string text, int width, int height, bool keepFrameRate)
        {
            List<string> frameRate = keepFrameRate ? new List<string>() : FrameRateLines(width, height);
            string newline = text.IndexOf("\r\n", StringComparison.Ordinal) >= 0 ? "\r\n" :
                (text.IndexOf("\n", StringComparison.Ordinal) >= 0 ? "\n" : Environment.NewLine);
            string[] lines = Regex.Split(text, "\\r\\n|\\n|\\r");
            List<string> output = new List<string>(lines.Length + 4);
            int sectionStart = -1;
            int sectionEnd = lines.Length;

            for (int index = 0; index < lines.Length; index++)
            {
                string sectionName;
                if (!TryGetSectionName(lines[index], out sectionName))
                    continue;
                if (sectionStart < 0 &&
                    String.Equals(sectionName, GraphicsSection, StringComparison.OrdinalIgnoreCase))
                {
                    sectionStart = index;
                    continue;
                }
                if (sectionStart >= 0)
                {
                    sectionEnd = index;
                    break;
                }
            }

            if (sectionStart < 0)
            {
                output.AddRange(lines);
                if (output.Count > 0 && output[output.Count - 1].Length != 0)
                    output.Add(String.Empty);
                output.Add("[Graphics Options]");
                output.Add("Height=" + height.ToString(CultureInfo.InvariantCulture));
                output.Add("Width=" + width.ToString(CultureInfo.InvariantCulture));
                output.AddRange(frameRate);
            }
            else
            {
                for (int index = 0; index <= sectionStart; index++)
                    output.Add(lines[index]);
                output.Add("Height=" + height.ToString(CultureInfo.InvariantCulture));
                output.Add("Width=" + width.ToString(CultureInfo.InvariantCulture));
                output.AddRange(frameRate);
                for (int index = sectionStart + 1; index < sectionEnd; index++)
                {
                    if (!IsResolutionKey(lines[index], keepFrameRate))
                        output.Add(lines[index]);
                }
                for (int index = sectionEnd; index < lines.Length; index++)
                    output.Add(lines[index]);
            }
            return String.Join(newline, output.ToArray());
        }

        private static bool TryReadResolution(string iniPath, out int width, out int height)
        {
            width = 0;
            height = 0;
            bool inGraphics = false;
            foreach (string line in File.ReadAllLines(iniPath))
            {
                string sectionName;
                if (TryGetSectionName(line, out sectionName))
                {
                    inGraphics = String.Equals(sectionName, GraphicsSection, StringComparison.OrdinalIgnoreCase);
                    continue;
                }
                if (!inGraphics)
                    continue;
                int equals = line.IndexOf('=');
                if (equals < 0)
                    continue;
                string key = line.Substring(0, equals).Trim();
                int value;
                if (!Int32.TryParse(line.Substring(equals + 1).Trim(), NumberStyles.Integer,
                    CultureInfo.InvariantCulture, out value))
                    continue;
                if (String.Equals(key, "Width", StringComparison.OrdinalIgnoreCase))
                    width = value;
                else if (String.Equals(key, "Height", StringComparison.OrdinalIgnoreCase))
                    height = value;
            }
            return width > 0 && height > 0;
        }

        private static bool TryGetSectionName(string line, out string sectionName)
        {
            string trimmed = line.Trim();
            if (trimmed.Length >= 3 && trimmed[0] == '[' && trimmed[trimmed.Length - 1] == ']')
            {
                sectionName = trimmed.Substring(1, trimmed.Length - 2).Trim();
                return true;
            }
            sectionName = null;
            return false;
        }

        private static bool IsResolutionKey(string line, bool keepFrameRate)
        {
            int equals = line.IndexOf('=');
            if (equals < 0)
                return false;
            string key = line.Substring(0, equals).Trim();
            if (String.Equals(key, "Width", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(key, "Height", StringComparison.OrdinalIgnoreCase))
                return true;
            if (keepFrameRate)
                return false;
            // The frame-rate lines, written again with the two above (FrameRateLines).
            foreach (string written in FrameRateLines(0, 0))
                if (String.Equals(key, written.Substring(0, written.IndexOf('=')), StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        /// <summary>The game's own frame-rate settings in [Graphics Options], as this
        /// install sets them (2026-10-09, at the maintainer's request).
        ///
        /// The game's Screen Resolution list shows a size once for each refresh rate of
        /// 60 Hz or more, and in fullscreen with V-Sync it draws as many frames a second
        /// as the mode's rate. Rates above 85 Hz are hidden, and a RefreshRate above 85
        /// is read as 60, unless AllowHighMonitorFrequency is 1
        /// (CClientExoAppInternal::ReadVideoModeSettings, 0x005F0CE0, and the dialog's
        /// constructor, 0x006E0710). Above 60 frames a second the game's timing breaks,
        /// which D3M0's High FPS Fixes repairs. So:
        ///   with High FPS Fix: every rate allowed, and the game starts at the highest
        ///     the display reports at the start size; V-Sync is left as it is;
        ///   without it: 60, the higher rates not allowed, and V-Sync on, since without
        ///     it the game draws as fast as it can. KMRP's module also hides the rates
        ///     above 60 from the list then (EnumModesOnce, K1RuntimeResolution.cpp).
        /// Restore puts the whole file back from its backup.</summary>
        private static List<string> FrameRateLines(int width, int height)
        {
            bool high = KmrpSettings.HighFpsFix;
            int rate = 60;
            if (high && width > 0 && height > 0)
                rate = Math.Max(60, InstallPlatform.HighestRefresh(new[] { width, height }));
            List<string> lines = new List<string>
            {
                "AllowHighMonitorFrequency=" + (high ? "1" : "0"),
                "RefreshRate=" + rate.ToString(CultureInfo.InvariantCulture),
            };
            if (!high)
                lines.Add("V-Sync=1");
            return lines;
        }

        private static void DetectEncoding(byte[] data, out Encoding encoding, out int preambleLength)
        {
            if (data.Length >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF)
            {
                encoding = new UTF8Encoding(true);
                preambleLength = 3;
            }
            else if (data.Length >= 2 && data[0] == 0xFF && data[1] == 0xFE)
            {
                encoding = Encoding.Unicode;
                preambleLength = 2;
            }
            else if (data.Length >= 2 && data[0] == 0xFE && data[1] == 0xFF)
            {
                encoding = Encoding.BigEndianUnicode;
                preambleLength = 2;
            }
            else
            {
                encoding = Encoding.Default;
                preambleLength = 0;
            }
        }

        private static byte[] Encode(string text, Encoding encoding, bool includePreamble)
        {
            byte[] content = encoding.GetBytes(text);
            byte[] preamble = includePreamble ? encoding.GetPreamble() : new byte[0];
            byte[] result = new byte[preamble.Length + content.Length];
            Buffer.BlockCopy(preamble, 0, result, 0, preamble.Length);
            Buffer.BlockCopy(content, 0, result, preamble.Length, content.Length);
            return result;
        }

        private static void WriteBytesNew(string path, byte[] data)
        {
            using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(data, 0, data.Length);
                stream.Flush(true);
            }
        }

        private static void WriteBytesAtomically(string path, byte[] data)
        {
            string temporaryPath = path + TemporaryInfix + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                WriteBytesNew(temporaryPath, data);
                // In one step: a kill while File.Replace had the old file aside left the
                // player with no swkotor.ini at all.
                FileGuard.MoveOver(temporaryPath, path);
            }
            finally
            {
                FileGuard.Discard(temporaryPath);
            }
        }

        private static bool BytesEqual(byte[] left, byte[] right)
        {
            if (left.Length != right.Length)
                return false;
            for (int index = 0; index < left.Length; index++)
            {
                if (left[index] != right[index])
                    return false;
            }
            return true;
        }

        private static string HashBytes(byte[] data)
        {
            using (SHA256 sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(data);
                StringBuilder result = new StringBuilder(hash.Length * 2);
                foreach (byte value in hash)
                    result.Append(value.ToString("X2", CultureInfo.InvariantCulture));
                return result.ToString();
            }
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }
    }

    internal sealed class OverrideRecord
    {
        internal string RelativePath;
        internal bool HadOriginal;
        internal string OriginalHash;
        internal string InstalledHash;
    }

    /// <summary>Removes the runtime the standalone installer installed through
    /// K1DC's ASI loader until 2026-09-29: a statically linked KOTOR Patch Manager
    /// runtime (kmrp-controller-runtime.asi), KMRP's module, SDL, the KPM licence and
    /// a one-patch patch_config.toml, recorded in KMRP_Controller.manifest. KMRP's
    /// installer replaces such an install (PatchOperations.RestoreStandalone calls
    /// Restore here); it installs KOTOR Patch Manager's runtime itself instead
    /// (KpmEditionOperations). The file and class names still say "controller"
    /// because they predate the runtime carrying more than the controller.
    ///
    /// The controller's own settings file is still installed, by
    /// KpmEditionOperations, from SettingsName and DefaultSettings here.</summary>
    internal static class ControllerOperations
    {
        private sealed class InstalledFile
        {
            internal string Name;
            internal string Hash;
        }

        // What the standalone installer wrote, and a manifest line may name: the
        // runtime, the module, SDL and its licence, KOTOR Patch Manager's MIT licence,
        // patch_config.toml and the settings file.
        private static readonly string[] FileNames =
            { "kmrp-controller-runtime.asi", "kmrp-controller.module", "kmrp-sdl3.dll",
              "kmrp-sdl3-LICENSE.txt", "kmrp-kotor-patch-manager-LICENSE.txt" };
        private const string ConfigName = "patch_config.toml";

        // The controller's own settings, read by the module (src/controller-native/
        // K1Rumble.cpp). Unlike every other file here it is the PLAYER'S to edit,
        // so it is written only when absent or still exactly as installed, is
        // never a reason to decline an install, and restore removes it only if it
        // is unchanged -- the manifest's usual rule. This is the name the standalone
        // installer's runtime gave it, which its manifest names; since 2026-10-20 it is
        // KMRP\controller.ini (KmrpFolder.ControllerSettings).
        internal const string SettingsName = "kmrp-controller.ini";
        // Every value here is what the user settled on in the pad tests of
        // 2026-09-25. Debug was 1 in the hardware-test builds, writing every
        // rumble event to kmrp-rumble.log; it is off now that those tests passed.
        internal const string DefaultSettings =
            "; KMRP controller settings. Read by the controller patch while the game runs;\r\n" +
            "; changes take effect within a second, no restart needed.\r\n" +
            "[Rumble]\r\n" +
            "; Off, Original (BioWare's shipped rumble only) or Enhanced (adds KMRP's haptics)\r\n" +
            "Mode=Enhanced\r\n" +
            "; 0 to 100 percent\r\n" +
            "Strength=100\r\n" +
            "; the lightsaber hum, 0 to 100 percent of BioWare's level (0 turns it off);\r\n" +
            "; 6 is the weakest an Xbox pad can play\r\n" +
            "SaberHum=6\r\n" +
            "; the hum pulses: on for SaberHumPulseMs (0 = a steady hum), then off until\r\n" +
            "; the next pulse -- a gap picked at random between SaberHumPeriodMinMs and\r\n" +
            "; SaberHumPeriodMaxMs, afresh for every pulse (make them equal for a fixed rhythm)\r\n" +
            "SaberHumPulseMs=100\r\n" +
            "SaberHumPeriodMinMs=500\r\n" +
            "SaberHumPeriodMaxMs=2000\r\n" +
            "; 1 writes every rumble event to kmrp-rumble.log in the logs folder beside this file\r\n" +
            "Debug=0\r\n" +
            "\r\n" +
            "[Hud]\r\n" +
            "; Xbox (laid out like the original Xbox version's while the pad is in use; the\r\n" +
            "; game's own with mouse and keyboard) or PC (the game's own HUD always).\r\n" +
            "; Read when the game starts.\r\n" +
            "Style=Xbox\r\n";

        private static string ManifestPath(string executablePath)
        {
            return GamePath.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)),
                                "KMRP_Controller.manifest");
        }

        /// <summary>Whether the standalone installer's runtime wrote this file and it is
        /// still as written: its restore will remove it.</summary>
        internal static bool Owns(string executablePath, string name)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return false;
            string target = GamePath.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), name);
            foreach (InstalledFile record in ReadManifest(manifestPath))
                if (String.Equals(record.Name, name, StringComparison.OrdinalIgnoreCase))
                    return File.Exists(target) && GoldPatch.HashFile(target) == record.Hash;
            return false;
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;
            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            int removed = 0;
            int kept = 0;
            foreach (InstalledFile record in ReadManifest(manifestPath))
            {
                string target = GamePath.Combine(folder, record.Name);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record.Hash)
                {
                    kept++;
                    continue;
                }
                File.Delete(target);
                removed++;
            }
            File.Delete(manifestPath);
            if (removed > 0)
                SafeReport(report, "Removed KMRP's runtime and controller support.");
            if (kept > 0)
                SafeReport(report, "Left " + kept +
                    " runtime file(s) in place because they changed after install.");
        }

        private static List<InstalledFile> ReadManifest(string manifestPath)
        {
            List<InstalledFile> records = new List<InstalledFile>();
            try
            {
                foreach (string line in File.ReadAllLines(manifestPath, Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length != 2 || parts[0] == "version" ||
                        (Array.IndexOf(FileNames, parts[0]) < 0 && parts[0] != ConfigName &&
                         parts[0] != SettingsName) ||
                        parts[1].Length != 64 || !Regex.IsMatch(parts[1], "\\A[0-9A-Fa-f]{64}\\z"))
                        continue;
                    records.Add(new InstalledFile { Name = parts[0], Hash = parts[1] });
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
    }

    internal static class OverrideOperations
    {
        private const string ManifestHeader = "KUIOVERRIDE1";

        internal static string OverridePath(string executablePath)
        {
            return GamePath.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "Override");
        }

        private static string BackupRoot(string executablePath)
        {
            return GamePath.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "KOTOR_UI_Override_Backup");
        }

        private static string ManifestPath(string executablePath)
        {
            return GamePath.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "KOTOR_UI_Override_Backup.manifest");
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            Restore(executablePath, report, null);
        }

        internal static void Restore(string executablePath, Action<string> report, Action<int, string> progress)
        {
            string overrideRoot = OverridePath(executablePath);
            string backupRoot = BackupRoot(executablePath);
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
            {
                SafeReport(report, "No bundled interface files need to be restored.");
                return;
            }

            List<OverrideRecord> records = CollapseDuplicates(ReadManifest(manifestPath));
            SafeProgress(progress, 8, "Checking installed interface files…");
            for (int recordIndex = 0; recordIndex < records.Count; recordIndex++)
            {
                OverrideRecord record = records[recordIndex];
                string target = SafeDestination(overrideRoot, record.RelativePath);
                string targetHash = File.Exists(target) ? GoldPatch.HashFile(target) : null;
                // The original already back is an earlier restore that stopped part way.
                if (targetHash != null && targetHash != record.InstalledHash &&
                    !(record.HadOriginal && targetHash == record.OriginalHash))
                    throw new InvalidDataException("An installed interface file was changed after patching. Restore was stopped to protect it:\r\n" + target);
                if (record.HadOriginal)
                {
                    string backup = SafeDestination(backupRoot, record.RelativePath);
                    if (!File.Exists(backup) || GoldPatch.HashFile(backup) != record.OriginalHash)
                        throw new InvalidDataException("An interface backup is missing or damaged. Restore was stopped:\r\n" + backup);
                }
                SafeProgress(progress, 8 + (int)(37L * (recordIndex + 1) / Math.Max(1, records.Count)),
                    "Checking installed interface files…");
            }

            for (int recordIndex = 0; recordIndex < records.Count; recordIndex++)
            {
                OverrideRecord record = records[recordIndex];
                string target = SafeDestination(overrideRoot, record.RelativePath);
                if (record.HadOriginal)
                {
                    string backup = SafeDestination(backupRoot, record.RelativePath);
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    File.Copy(backup, target, true);
                }
                else if (File.Exists(target))
                {
                    File.Delete(target);
                }
                SafeProgress(progress, 45 + (int)(43L * (recordIndex + 1) / Math.Max(1, records.Count)),
                    "Restoring previous interface files…");
            }

            File.Delete(manifestPath);
            if (Directory.Exists(backupRoot))
                Directory.Delete(backupRoot, true);
            SafeReport(report, "Restored the previous Override files.");
        }

        /// <summary>
        /// Collapses repeated records for one path, which patchers up to 2.5.0
        /// could write: the generated icons claimed `i_*`, so i_checkbox01/02.tga
        /// were installed by two archives and recorded twice. Restore then compared
        /// the file against the FIRST record and refused, reporting the file as
        /// changed after patching when nothing had touched it.
        ///
        /// The first record describes the user's own file (HadOriginal/OriginalHash)
        /// -- the second's "original" is the patcher's own freshly written file.
        /// The last record describes what is on disk, because its archive wrote
        /// last. Keep each from the record that actually knows it.
        /// </summary>
        private static List<OverrideRecord> CollapseDuplicates(List<OverrideRecord> records)
        {
            Dictionary<string, OverrideRecord> first =
                new Dictionary<string, OverrideRecord>(StringComparer.OrdinalIgnoreCase);
            List<OverrideRecord> collapsed = new List<OverrideRecord>();
            foreach (OverrideRecord record in records)
            {
                OverrideRecord existing;
                if (first.TryGetValue(record.RelativePath, out existing))
                    existing.InstalledHash = record.InstalledHash;
                else
                {
                    first.Add(record.RelativePath, record);
                    collapsed.Add(record);
                }
            }
            return collapsed;
        }

        private static string NormalizeRelativePath(string value)
        {
            string relative = value.Replace('/', Path.DirectorySeparatorChar).TrimStart(Path.DirectorySeparatorChar);
            if (String.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative) ||
                relative.IndexOf(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal) >= 0)
                throw new InvalidDataException("The bundled interface archive contains an unsafe path.");
            return relative;
        }

        private static string SafeDestination(string root, string relative)
        {
            string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string destination = Path.GetFullPath(GamePath.Combine(fullRoot, relative));
            if (!destination.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The bundled interface archive contains an unsafe destination.");
            return destination;
        }

        private static void WriteManifest(string path, List<OverrideRecord> records)
        {
            StringBuilder text = new StringBuilder();
            text.AppendLine(ManifestHeader);
            foreach (OverrideRecord record in records)
            {
                text.Append(Convert.ToBase64String(Encoding.UTF8.GetBytes(record.RelativePath))).Append('\t')
                    .Append(record.HadOriginal ? "1" : "0").Append('\t')
                    .Append(record.OriginalHash ?? String.Empty).Append('\t')
                    .Append(record.InstalledHash ?? String.Empty).AppendLine();
            }
            File.WriteAllText(path, text.ToString(), new UTF8Encoding(false));
        }

        private static List<OverrideRecord> ReadManifest(string path)
        {
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            if (lines.Length < 1 || lines[0] != ManifestHeader)
                throw new InvalidDataException("The interface backup record is not recognized.");
            List<OverrideRecord> records = new List<OverrideRecord>();
            for (int index = 1; index < lines.Length; index++)
            {
                if (String.IsNullOrWhiteSpace(lines[index]))
                    continue;
                string[] fields = lines[index].Split('\t');
                if (fields.Length != 4 || (fields[1] != "0" && fields[1] != "1") || fields[3].Length != 64)
                    throw new InvalidDataException("The interface backup record is damaged.");
                string relative = Encoding.UTF8.GetString(Convert.FromBase64String(fields[0]));
                records.Add(new OverrideRecord
                {
                    RelativePath = NormalizeRelativePath(relative),
                    HadOriginal = fields[1] == "1",
                    OriginalHash = fields[2],
                    InstalledHash = fields[3]
                });
            }
            return records;
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }

        private static void SafeProgress(Action<int, string> progress, int value, string message)
        {
            if (progress == null)
                return;
            try { progress(Math.Max(0, Math.Min(100, value)), message); }
            catch { }
        }
    }

    /// <summary>Replacing a file is not as atomic in practice as File.Replace suggests.
    /// Replace has to delete the destination, and that fails with "the file to be replaced
    /// cannot be removed" while any process holds a handle opened without
    /// FILE_SHARE_DELETE. Antivirus scanning a file moments after it was written is the
    /// usual cause, along with the search indexer, Explorer preview handlers, and the game
    /// or an editor having the file open. All of those are transient or actionable, and
    /// none of them should abort a patch outright.</summary>
    internal static class FileGuard
    {
        private const int Attempts = 6;

        internal static void Replace(string temporaryPath, string targetPath)
        {
            int delay = 60;
            for (int attempt = 1; attempt <= Attempts; attempt++)
            {
                try
                {
                    ClearReadOnly(targetPath);
                    File.Replace(temporaryPath, targetPath, null, true);
                    return;
                }
                catch (IOException)
                {
                    if (attempt == Attempts)
                        break;
                }
                catch (UnauthorizedAccessException)
                {
                    if (attempt == Attempts)
                        break;
                }
                // Doubling from 60ms gives up after about four seconds, which clears a
                // scanner comfortably without leaving the user watching a frozen bar.
                System.Threading.Thread.Sleep(delay);
                delay *= 2;
            }

            // Last resort: overwrite the destination instead of replacing it. Replace needs
            // to delete the file; copying only needs to open it for writing, which a reader
            // holding FILE_SHARE_WRITE still permits. Every caller verifies the result by
            // hash afterwards, so a partial write is caught and rolled back rather than
            // being mistaken for success.
            try
            {
                ClearReadOnly(targetPath);
                File.Copy(temporaryPath, targetPath, true);
                Discard(temporaryPath);
                return;
            }
            catch (IOException error)
            {
                throw new IOException(InUseMessage(targetPath), error);
            }
            catch (UnauthorizedAccessException error)
            {
                throw new IOException(InUseMessage(targetPath), error);
            }
        }

        /// <summary>The temporary file renamed over the target in one step, tried again as
        /// Replace is while something holds the target. For a file a stopped install must
        /// find whole or not at all: File.Replace moves the old file aside before the new one
        /// is in, and a kill between the two left no manifest (Test-InstallerPatch Case 17,
        /// 2026-11-01). Unlike Replace it keeps neither the target's permissions nor its
        /// attributes, so it is for KMRP's own files.</summary>
        internal static void MoveOver(string temporaryPath, string targetPath)
        {
            int delay = 60;
            for (int attempt = 1; ; attempt++)
            {
                try
                {
                    ClearReadOnly(targetPath);
                    InstallPlatform.MoveOver(temporaryPath, targetPath);
                    return;
                }
                catch (IOException error)
                {
                    if (attempt == Attempts)
                        throw new IOException(InUseMessage(targetPath), error);
                }
                catch (UnauthorizedAccessException error)
                {
                    if (attempt == Attempts)
                        throw new IOException(InUseMessage(targetPath), error);
                }
                System.Threading.Thread.Sleep(delay);
                delay *= 2;
            }
        }

        /// <summary>Deletes a scratch file without ever throwing. A throw from a finally
        /// block replaces the exception that is actually being reported.</summary>
        internal static void Discard(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    ClearReadOnly(path);
                    File.Delete(path);
                }
            }
            catch { }
        }

        private static void ClearReadOnly(string path)
        {
            try
            {
                if (!File.Exists(path))
                    return;
                FileAttributes attributes = File.GetAttributes(path);
                if ((attributes & FileAttributes.ReadOnly) != 0)
                    File.SetAttributes(path, attributes & ~FileAttributes.ReadOnly);
            }
            catch { }
        }

        /// <summary>Deletes a file KMRP installed, as Replace replaces one: its read-only
        /// flag cleared, tried again for about four seconds while something holds it, then
        /// a plain message. Until 2026-10-31 the driver compatibility patch's restore
        /// deleted dinput8.dll directly, and with the game still running (Windows keeps a
        /// loaded DLL locked) the player saw .NET's "Access to the path is denied" and its
        /// stack trace, three times in a row (issue 75's log, 2026-10-23).</summary>
        internal static void Delete(string path)
        {
            int delay = 60;
            for (int attempt = 1; ; attempt++)
            {
                try
                {
                    ClearReadOnly(path);
                    if (File.Exists(path))
                        File.Delete(path);
                    return;
                }
                catch (IOException error)
                {
                    if (attempt == Attempts)
                        throw new IOException(InUseMessage(path, "removed"), error);
                }
                catch (UnauthorizedAccessException error)
                {
                    if (attempt == Attempts)
                        throw new IOException(InUseMessage(path, "removed"), error);
                }
                System.Threading.Thread.Sleep(delay);
                delay *= 2;
            }
        }

        /// <summary>The one message for a game file another program holds (KpmEdition.cs
        /// too): what to close, in the player's words.</summary>
        internal static string InUseMessage(string path, string done = "updated")
        {
            return Path.GetFileName(path) + " is being used by another program, so it " +
                "could not be " + done + ". Close KOTOR, Steam, and any editor with the file " +
                "open, then try again.";
        }
    }

    /// <summary>What has to hold before an install or restore touches a game folder (audit
    /// INS-06), so it is refused with a plain message rather than stopping part way with
    /// "Access to the path is denied": the game not running from it, this account allowed
    /// to write there, and no other KMRP installer working on it. The lock is the one thing
    /// held for the whole operation, by whoever disposes of the result. The Mac's has its
    /// own (refuse_if_running, kmrp-mac.sh).</summary>
    internal sealed class InstallGuard : IDisposable
    {
        private readonly System.Threading.Mutex mutex;

        private InstallGuard(System.Threading.Mutex mutex)
        {
            this.mutex = mutex;
        }

        internal static InstallGuard Take(string executablePath)
        {
            if (!File.Exists(executablePath))
                return new InstallGuard(null);
            string executable = Path.GetFullPath(executablePath);
            string folder = Path.GetDirectoryName(executable);
            System.Threading.Mutex mutex = new System.Threading.Mutex(false, "Local\\KMRP-install-" +
                HashName(folder.ToUpperInvariant()));
            bool held = false;
            try
            {
                try { held = mutex.WaitOne(0); }
                // An installer that was killed: the manifest says what it left.
                catch (System.Threading.AbandonedMutexException) { held = true; }
                if (!held)
                    throw new InvalidOperationException("Another KMRP installer is working on this game " +
                        "folder. Wait for it to finish, then try again. No changes were made.");
                if (InstallPlatform.GameRunning(executable))
                    throw new InvalidOperationException("KOTOR is running from this folder. Close it, then " +
                        "try again. No changes were made.");
                RequireWriteAccess(folder);
                return new InstallGuard(mutex);
            }
            catch
            {
                if (held)
                    mutex.ReleaseMutex();
                mutex.Dispose();
                throw;
            }
        }

        private static string HashName(string text)
        {
            using (System.Security.Cryptography.SHA256 sha = System.Security.Cryptography.SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(text))).Replace("-", "");
        }

        private static void RequireWriteAccess(string folder)
        {
            string probe = GamePath.Combine(folder, "kmrp-write-test.kmrp-new");
            try
            {
                File.WriteAllBytes(probe, new byte[0]);
                File.Delete(probe);
            }
            catch (UnauthorizedAccessException error)
            {
                throw new IOException("This account may not change files in " + folder + ". Start the " +
                    "installer as administrator, or move the game to a folder you own. No changes were made.", error);
            }
        }

        public void Dispose()
        {
            if (mutex == null)
                return;
            mutex.ReleaseMutex();
            mutex.Dispose();
        }
    }

    /// <summary>The standalone K1 Modern Driver Compatibility, two files beside the game:
    /// Ultimate ASI Loader's dinput8.dll and K1DC's .asi, recorded in
    /// KMRP\driver-compat.manifest.
    ///
    /// Since 2026-10-31 (issue 44) KMRP installs K1DC as its .kpatch (KpmEdition.cs),
    /// except where that module cannot run: on Windows 7 and 8 this installs its author's
    /// build for them (2.0.1's -standalone-win7 download), since KOTOR Patch Manager's
    /// route needs Windows 10. Windows loads a dinput8.dll beside the game by itself, so no
    /// setting is needed there; under Wine it would be (WINEDLLOVERRIDES), which is why
    /// the .kpatch is everyone else's. Until then this was the only route, with the build
    /// for Windows 8 and later, and Windows 7 had no K1DC. Restore takes the two files out
    /// on both systems, an older KMRP's too, and leaves a file someone changed since, and
    /// says so.</summary>
    internal static class DriverCompatStandalone
    {
        internal const string Version = "2.0.1-win7";

        // Resource name and file name in the game folder.
        private static readonly string[,] Files =
        {
            { "Kmrp.drivercompat.win7.dinput8", "dinput8.dll" },
            { "Kmrp.drivercompat.win7.asi", "k1-modern-driver-compatibility.asi" },
        };

        /// <summary>Writes the two files, unless one of those names already holds a file
        /// KMRP did not put there: a player may run another ASI loader, or K1DC installed
        /// by hand, and replacing either would be destructive and undiagnosable. Returns
        /// whether it installed them.</summary>
        internal static bool Install(string executablePath, Action<string> report)
        {
            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            for (int i = 0; i < Files.GetLength(0); i++)
            {
                if (File.Exists(GamePath.Combine(folder, Files[i, 1])))
                {
                    if (report != null)
                        report("Left the existing " + Files[i, 1] + " alone; the driver compatibility patch was not installed.");
                    return false;
                }
            }
            StringBuilder manifest = new StringBuilder();
            manifest.Append("version\t").Append(Version).Append("\r\n");
            Directory.CreateDirectory(Path.GetDirectoryName(KmrpFolder.PathOf(executablePath, KmrpFolder.DriverCompatManifest)));
            for (int i = 0; i < Files.GetLength(0); i++)
            {
                string target = GamePath.Combine(folder, Files[i, 1]);
                using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(Files[i, 0]))
                {
                    if (stream == null)
                        throw new InvalidDataException("The installer is missing " + Files[i, 0] + ".");
                    using (FileStream output = File.Create(target))
                        stream.CopyTo(output);
                }
                manifest.Append(Files[i, 1]).Append('\t').Append(GoldPatch.HashFile(target)).Append("\r\n");
                // Recorded file by file, so a failure on the second still lets Restore take
                // out the first.
                File.WriteAllText(KmrpFolder.PathOf(executablePath, KmrpFolder.DriverCompatManifest),
                    manifest.ToString(), new UTF8Encoding(false));
            }
            if (report != null)
                report("Installed K1 Modern Driver Compatibility " + Version + " (by Synchro), its build for " +
                    "Windows 7 and 8. swkotor.exe was not modified.");
            return true;
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            string manifestPath = KmrpFolder.PathOf(executablePath, KmrpFolder.DriverCompatManifest);
            if (!File.Exists(manifestPath))
                return;

            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            int removed = 0;
            int kept = 0;
            foreach (string[] record in ReadManifest(manifestPath))
            {
                string target = GamePath.Combine(folder, record[0]);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record[1])
                {
                    // Changed since we wrote it -- upgraded by hand, most likely. Leave
                    // it, and say so, rather than deleting someone else's newer copy.
                    kept++;
                    continue;
                }
                // A running game holds dinput8.dll: a plain message, not a stack trace.
                FileGuard.Delete(target);
                removed++;
            }

            File.Delete(manifestPath);
            if (removed > 0 && report != null)
                report("Removed the standalone driver compatibility files.");
            if (kept > 0 && report != null)
                report("Left " + kept + " driver compatibility file(s) in place because they changed after install.");
        }

        // One file per line, name and SHA-256, after a "version" line.
        private static List<string[]> ReadManifest(string manifestPath)
        {
            List<string[]> records = new List<string[]>();
            try
            {
                foreach (string line in File.ReadAllLines(manifestPath, Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length == 2 && parts[0] != "version" && IsPlainName(parts[0]))
                        records.Add(parts);
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return records;
        }

        // Restore deletes what these rows name, so a name with a folder in it is not one
        // this wrote (audit INS-05; an unreadable record leaves the two files, with no harm).
        private static bool IsPlainName(string name)
        {
            return name.Length > 0 && name.IndexOfAny(new[] { '\\', '/', ':' }) < 0 && name != "." && name != "..";
        }
    }

    /// <summary>KMRP's own files in a game folder, in one folder of their own, KMRP: the
    /// logs in KMRP\logs and what a restore puts back in KMRP\backups (the maintainer,
    /// 2026-10-20: "we shouldnt clutter the folder like this"). What the game or KOTOR
    /// Patch Manager loads from the game folder itself stays there: KPM's runtime,
    /// patch_config.toml, patches\ and configs\ (K1DC's module among them since
    /// 2026-10-31; its standalone dinput8.dll and .asi until then).
    ///
    /// Until 2026-10-20 these files were loose in the game folder, under the names in
    /// Legacy's second column. Migrate moves an earlier install's into place, and PathOf
    /// finds one that has not been moved yet. The files only the standalone installer
    /// wrote, until 2026-09-29 (its executable and Override backups and its manifests),
    /// stay where it wrote them, and its own restore reads them there.</summary>
    internal static class KmrpFolder
    {
        internal const string Name = "KMRP";
        // Names relative to the game folder, as the KPM manifest's rows name files.
        internal const string InstallLog = @"KMRP\logs\install.log";
        internal const string KpmManifest = @"KMRP\kpm.manifest";
        internal const string DriverCompatManifest = @"KMRP\driver-compat.manifest";
        internal const string DpiManifest = @"KMRP\dpi.manifest";
        internal const string NvidiaManifest = @"KMRP\nvidia.manifest";
        internal const string ControllerSettings = @"KMRP\controller.ini";
        internal const string KpmLicense = @"KMRP\kotor-patch-manager-LICENSE.txt";
        internal const string IniBackup = @"KMRP\backups\swkotor.ini";
        private static readonly string[] Folders = { @"KMRP", @"KMRP\logs", @"KMRP\backups" };

        // Each file's place, and its name in the game folder until 2026-10-20. The logs are
        // the game modules' as well as the installer's (src/controller-native/KmrpOptions.h,
        // KmrpLogPath, moves none of them; this does, at the next install).
        private static readonly string[,] Legacy =
        {
            { InstallLog, "KMRP.log" },
            { KpmManifest, "KMRP_KPM.manifest" },
            { DriverCompatManifest, "KMRP_DriverCompat.manifest" },
            { DpiManifest, "KMRP_DPI.manifest" },
            { NvidiaManifest, "KMRP_NVIDIA.manifest" },
            { ControllerSettings, "kmrp-controller.ini" },
            { KpmLicense, "kmrp-kotor-patch-manager-LICENSE.txt" },
            { IniBackup, "swkotor.ini.kotor-ui-backup" },
            { IniBackup + ".sha256", "swkotor.ini.kotor-ui-backup.sha256" },
            { @"KMRP\logs\kmrp-kpm.log", "kmrp-kpm.log" },
            { @"KMRP\logs\kmrp-controller.log", "kmrp-controller.log" },
            { @"KMRP\logs\kmrp-controller-events.log", "kmrp-controller-events.log" },
            { @"KMRP\logs\kmrp-native-joystick.log", "kmrp-native-joystick.log" },
            { @"KMRP\logs\kmrp-native-preview.log", "kmrp-native-preview.log" },
            { @"KMRP\logs\kmrp-layout-lifecycle.log", "kmrp-layout-lifecycle.log" },
            { @"KMRP\logs\kmrp-confirm-focus.log", "kmrp-confirm-focus.log" },
            { @"KMRP\logs\kmrp-rumble.log", "kmrp-rumble.log" },
        };

        internal static string GameFolder(string executablePath)
        {
            return Path.GetDirectoryName(Path.GetFullPath(executablePath));
        }

        /// <summary>A file of KMRP's, named relative to the game folder: where it is, or,
        /// while only an earlier install's copy exists, that copy.</summary>
        internal static string PathOf(string executablePath, string name)
        {
            string folder = GameFolder(executablePath);
            string path = GamePath.Combine(folder, name);
            if (File.Exists(path))
                return path;
            for (int i = 0; i < Legacy.GetLength(0); i++)
            {
                if (!String.Equals(Legacy[i, 0], name, StringComparison.OrdinalIgnoreCase))
                    continue;
                string legacy = GamePath.Combine(folder, Legacy[i, 1]);
                if (File.Exists(legacy))
                    return legacy;
            }
            return path;
        }

        /// <summary>The folders made, and an earlier install's files moved into them: a log
        /// appended to the one already there, anything else moved only when its place is
        /// free. The KPM manifest's rows follow the files they name.</summary>
        internal static void Migrate(string executablePath, Action<string> report)
        {
            string folder = GameFolder(executablePath);
            foreach (string name in Folders)
                Directory.CreateDirectory(GamePath.Combine(folder, name));
            int moved = 0;
            for (int i = 0; i < Legacy.GetLength(0); i++)
            {
                string legacy = GamePath.Combine(folder, Legacy[i, 1]);
                string target = GamePath.Combine(folder, Legacy[i, 0]);
                if (!File.Exists(legacy))
                    continue;
                try
                {
                    if (!File.Exists(target))
                        File.Move(legacy, target);
                    else if (target.EndsWith(".log", StringComparison.OrdinalIgnoreCase))
                    {
                        // The older lines first, as they were written.
                        byte[] older = File.ReadAllBytes(legacy);
                        byte[] newer = File.ReadAllBytes(target);
                        using (FileStream output = new FileStream(target, FileMode.Create, FileAccess.Write))
                        {
                            output.Write(older, 0, older.Length);
                            output.Write(newer, 0, newer.Length);
                        }
                        File.Delete(legacy);
                    }
                    else
                        continue;     // both: the one in KMRP is the newer, the other is left alone
                    moved++;
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
            // Rows naming a file that is now in KMRP's folder, whoever moved it: the game
            // moves the controller's settings itself (KmrpControllerSettingsPath, KmrpOptions.h).
            string manifest = GamePath.Combine(folder, KpmManifest);
            if (File.Exists(manifest))
            {
                string[] lines = File.ReadAllLines(manifest, Encoding.UTF8);
                bool changed = false;
                for (int l = 0; l < lines.Length; l++)
                {
                    string[] parts = lines[l].Split('\t');
                    if (parts.Length != 3 || parts[0] != "file")
                        continue;
                    for (int i = 0; i < Legacy.GetLength(0); i++)
                    {
                        if (String.Equals(parts[1], Legacy[i, 1], StringComparison.OrdinalIgnoreCase) &&
                            File.Exists(GamePath.Combine(folder, Legacy[i, 0])) &&
                            !File.Exists(GamePath.Combine(folder, Legacy[i, 1])))
                        {
                            lines[l] = "file\t" + Legacy[i, 0] + "\t" + parts[2];
                            changed = true;
                        }
                    }
                }
                if (changed)
                    File.WriteAllLines(manifest, lines, new UTF8Encoding(false));
            }
            if (moved > 0 && report != null)
                report("Moved " + moved.ToString(CultureInfo.InvariantCulture) +
                    " of KMRP's files from the game folder into its KMRP folder.");
        }

        /// <summary>After a restore: KMRP's folders that are left empty, removed, the KMRP
        /// folder last. What a restore keeps (the install log, the swkotor.ini backup) keeps
        /// its folder.</summary>
        internal static void RemoveEmpty(string executablePath)
        {
            string folder = GameFolder(executablePath);
            for (int i = Folders.Length - 1; i >= 0; i--)
            {
                string path = GamePath.Combine(folder, Folders[i]);
                try
                {
                    if (Directory.Exists(path) && Directory.GetFileSystemEntries(path).Length == 0)
                        Directory.Delete(path);
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
        }
    }

    internal static class PatchOperations
    {
        internal static string BackupPath(string targetPath)
        {
            return targetPath + ".kotor-ui-backup";
        }

        internal static string LogPath(string targetPath)
        {
            return KmrpFolder.PathOf(targetPath, KmrpFolder.InstallLog);
        }

        internal static string ManifestPath(string targetPath)
        {
            return targetPath + ".kotor-ui-patch.json";
        }

        // The installer installs through KpmEditionOperations since 2026-09-29, and
        // does not rewrite swkotor.exe. The *Standalone members below are how an
        // install by the standalone installer, which did, is recognised and restored
        // before the installer replaces it.

        internal static string Describe(string targetPath)
        {
            return KpmEditionOperations.Describe(targetPath);
        }

        internal static string DescribeStandalone(string targetPath)
        {
            if (!File.Exists(targetPath))
                return "File not found";

            try
            {
                FileInfo info = new FileInfo(targetPath);
                string hash = GoldPatch.HashFile(targetPath);
                if (info.Length == GoldPatch.SourceLength && GoldPatch.IsSupportedSourceFile(targetPath))
                    return hash == PeCompatibility.LargeAddressAwareSourceHash
                        ? "Supported clean build — 4 GB support already detected"
                        : "Supported clean build — ready to patch";
                if (IsVerifiedPatchedInstall(targetPath, hash) ||
                    (info.Length == GoldPatch.TargetLength && hash == GoldPatch.TargetHash))
                    return "Game is already patched";
                return "This executable is not supported. No files were changed.";
            }
            catch (Exception ex)
            {
                return "Unable to inspect file: " + ex.Message;
            }
        }

        internal static ExecutableState Inspect(string targetPath)
        {
            return KpmEditionOperations.Inspect(targetPath);
        }

        /// <summary>The executable as the standalone installer saw it: Gold is an
        /// install of its, SupportedClean the CD 1.03 executable it accepted.</summary>
        internal static ExecutableState InspectStandalone(string targetPath)
        {
            if (String.IsNullOrWhiteSpace(targetPath) || !File.Exists(targetPath))
                return ExecutableState.Missing;
            try
            {
                FileInfo info = new FileInfo(targetPath);
                string hash = GoldPatch.HashFile(targetPath);
                if (info.Length == GoldPatch.SourceLength && GoldPatch.IsSupportedSourceFile(targetPath))
                    return ExecutableState.SupportedClean;
                if (IsVerifiedPatchedInstall(targetPath, hash) ||
                    (info.Length == GoldPatch.TargetLength && hash == GoldPatch.TargetHash))
                    return ExecutableState.Gold;
                return ExecutableState.Unsupported;
            }
            catch
            {
                return ExecutableState.Error;
            }
        }

        internal static bool CanRestore(string targetPath)
        {
            return KpmEditionOperations.CanRestore(targetPath);
        }

        internal static bool CanRestoreStandalone(string targetPath)
        {
            try
            {
                if (InspectStandalone(targetPath) != ExecutableState.Gold)
                    return false;
                string executableBackup = BackupPath(targetPath);
                return File.Exists(executableBackup) &&
                    GoldPatch.IsSupportedSourceFile(executableBackup) &&
                    IniOperations.HasVerifiedBackup(targetPath);
            }
            catch
            {
                return false;
            }
        }

        internal static void ApplyInPlace(string targetPath, Action<string> report)
        {
            ApplyInPlace(targetPath, IniOperations.DefaultWidth, IniOperations.DefaultHeight, report, null);
        }

        internal static void ApplyInPlace(string targetPath, int width, int height, Action<string> report)
        {
            ApplyInPlace(targetPath, width, height, report, null);
        }

        internal static void ApplyInPlace(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress)
        {
            KpmEditionOperations.Install(targetPath, width, height, report, progress);
        }

        internal static void Restore(string targetPath, Action<string> report)
        {
            Restore(targetPath, report, null);
        }

        internal static void Restore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            KpmEditionOperations.Restore(targetPath, report, progress);
        }

        internal static void RestoreStandalone(string targetPath, Action<string> report, Action<int, string> progress)
        {
            RestoreStandalone(targetPath, report, progress, false);
        }

        /// <summary>`keepIni`: an install over this one, which leaves swkotor.ini the
        /// player's (IniOperations.Configure).</summary>
        internal static void RestoreStandalone(string targetPath, Action<string> report, Action<int, string> progress,
            bool keepIni)
        {
            SafeProgress(progress, 0, "Preparing to restore…");
            targetPath = Path.GetFullPath(targetPath);
            RequireExistingFile(targetPath);
            string currentHash = GoldPatch.HashFile(targetPath);
            if (GoldPatch.IsSupportedSourceFile(targetPath))
            {
                OverrideOperations.Restore(targetPath, report, progress);
                ControllerOperations.Restore(targetPath, report);
                InstallPlatform.RestoreDriverCompat(targetPath, report);
                InstallPlatform.RestoreDpi(targetPath, report);
                InstallPlatform.RemoveOldNvidiaSetting(targetPath, report);
                SafeProgress(progress, 92, "Restoring display settings…");
                if (!keepIni)
                    IniOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving restore information…");
                WriteManifest(targetPath, BackupPath(targetPath), true, 0, 0, currentHash);
                SafeProgress(progress, 100, "Restore complete");
                SafeReport(report, "The original game files and settings have been restored.");
                return;
            }
            if (InspectStandalone(targetPath) != ExecutableState.Gold)
                throw new InvalidDataException("The current executable was not created by this patcher. Restore was blocked to protect it.");

            string backupPath = BackupPath(targetPath);
            RequireExistingFile(backupPath);
            if (!GoldPatch.IsSupportedSourceFile(backupPath))
                throw new InvalidDataException("Backup verification failed. Restore was blocked.");

            string backupHash = GoldPatch.HashFile(backupPath);

            string temporaryPath = targetPath + ".kotor-ui-restore-" + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                SafeProgress(progress, 5, "Checking the original game backup…");
                File.Copy(backupPath, temporaryPath, false);
                if (GoldPatch.HashFile(temporaryPath) != backupHash)
                    throw new IOException("Temporary restore verification failed.");
                OverrideOperations.Restore(targetPath, report, progress);
                ControllerOperations.Restore(targetPath, report);
                InstallPlatform.RestoreDriverCompat(targetPath, report);
                InstallPlatform.RestoreDpi(targetPath, report);
                InstallPlatform.RemoveOldNvidiaSetting(targetPath, report);
                SafeProgress(progress, 90, "Restoring the game executable…");
                FileGuard.Replace(temporaryPath, targetPath);
                if (GoldPatch.HashFile(targetPath) != backupHash)
                    throw new IOException("Post-restore verification failed.");
                SafeProgress(progress, 94, "Restoring display settings…");
                if (!keepIni)
                    IniOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving restore information…");
                WriteManifest(targetPath, backupPath, true, 0, 0, backupHash);
                SafeProgress(progress, 100, "Restore complete");
                SafeReport(report, "The original game files and settings have been restored.");
            }
            finally
            {
                if (File.Exists(temporaryPath))
                    File.Delete(temporaryPath);
            }
        }

        internal static void AppendLog(string targetPath, string message)
        {
            string line = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture) + "  " + message + Environment.NewLine;
            string path = LogPath(targetPath);
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.AppendAllText(path, line, new UTF8Encoding(false));
        }

        private static void RequireExistingFile(string path)
        {
            if (!File.Exists(path))
                throw new FileNotFoundException("File not found", path);
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }

        private static void SafeProgress(Action<int, string> progress, int value, string message)
        {
            if (progress == null)
                return;
            try { progress(Math.Max(0, Math.Min(100, value)), message); }
            catch { }
        }

        private static void WriteVerifiedFile(string path, byte[] data, string expectedHash)
        {
            using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(data, 0, data.Length);
                stream.Flush(true);
            }
            if (GoldPatch.HashFile(path) != expectedHash)
            {
                File.Delete(path);
                throw new IOException("The written game file failed its integrity check.");
            }
        }

        private static void WriteManifest(string targetPath, string backupPath, bool restored, int width, int height,
            string executableHash)
        {
            string iniPath = IniOperations.PathForExecutable(targetPath);
            string iniHash = File.Exists(iniPath) ? GoldPatch.HashFile(iniPath) : String.Empty;
            string sourceHash = File.Exists(backupPath)
                ? GoldPatch.HashFile(backupPath)
                : (restored ? executableHash : GoldPatch.SourceHash);
            string json = "{\r\n" +
                "  \"patchVersion\": \"" + GoldPatch.PatchVersion + "\",\r\n" +
                "  \"state\": \"" + (restored ? "restored" : "patched") + "\",\r\n" +
                "  \"timestampUtc\": \"" + DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture) + "\",\r\n" +
                "  \"executable\": \"" + JsonEscape(targetPath) + "\",\r\n" +
                "  \"backup\": \"" + JsonEscape(backupPath) + "\",\r\n" +
                "  \"ini\": \"" + JsonEscape(iniPath) + "\",\r\n" +
                "  \"iniBackup\": \"" + JsonEscape(IniOperations.BackupPath(targetPath)) + "\",\r\n" +
                "  \"iniSha256\": \"" + iniHash + "\",\r\n" +
                "  \"resolution\": " + (restored ? "null" : "\"" +
                    width.ToString(CultureInfo.InvariantCulture) + "x" +
                    height.ToString(CultureInfo.InvariantCulture) + "\"") + ",\r\n" +
                "  \"sourceSha256\": \"" + sourceHash + "\",\r\n" +
                "  \"goldTargetSha256\": \"" + GoldPatch.TargetHash + "\",\r\n" +
                "  \"patchedSha256\": \"" + executableHash + "\"\r\n" +
                "}\r\n";
            File.WriteAllText(ManifestPath(targetPath), json, new UTF8Encoding(false));
        }

        private static bool IsVerifiedPatchedInstall(string targetPath, string actualHash)
        {
            try
            {
                string manifestPath = ManifestPath(targetPath);
                if (!File.Exists(manifestPath))
                    return false;
                // Deliberately NOT gated on GoldPatch.TargetLength. This answers "is this
                // an install KMRP made", which has to stay true for an install made by an
                // *earlier* build -- that is exactly when a restore or an upgrade is
                // needed. Gold v21 added a section and grew the executable by 4,096 bytes,
                // and the length gate then rejected every v20 install before its sidecar
                // was even read: Restore refused with "not created by this patcher", and
                // because the upgrade path calls Restore, upgrading was impossible.
                // The sidecar hash below is the real evidence and is strictly stronger.
                string json = File.ReadAllText(manifestPath, Encoding.UTF8);
                if (!Regex.IsMatch(json, "\\\"state\\\"\\s*:\\s*\\\"patched\\\"",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant))
                    return false;
                Match hash = Regex.Match(json,
                    "\\\"(?:patchedSha256|goldSha256)\\\"\\s*:\\s*\\\"([0-9A-Fa-f]{64})\\\"",
                    RegexOptions.CultureInvariant);
                return hash.Success && String.Equals(hash.Groups[1].Value, actualHash,
                    StringComparison.OrdinalIgnoreCase);
            }
            catch
            {
                return false;
            }
        }

        internal static bool TryReadInstalledResolution(string targetPath, out int width, out int height)
        {
            return KpmEditionOperations.TryReadInstalledResolution(targetPath, out width, out height);
        }

        internal static bool TryReadInstalledResolutionStandalone(string targetPath, out int width, out int height)
        {
            width = 0;
            height = 0;
            try
            {
                string manifestPath = ManifestPath(targetPath);
                if (!File.Exists(manifestPath))
                    return false;
                string json = File.ReadAllText(manifestPath, Encoding.UTF8);
                Match value = Regex.Match(json, "\\\"resolution\\\"\\s*:\\s*\\\"(\\d+)x(\\d+)\\\"",
                    RegexOptions.CultureInvariant);
                return value.Success &&
                    Int32.TryParse(value.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out width) &&
                    Int32.TryParse(value.Groups[2].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out height);
            }
            catch
            {
                return false;
            }
        }

        private static string JsonEscape(string value)
        {
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }

    /// <summary>The handful of choices a user can make about what KMRP installs.
    ///
    /// Kept beside the user's profile rather than next to the executable, because the
    /// patcher is a single file people run from Downloads and we want a choice to survive
    /// being re-downloaded. Written as JSON by hand and read back with a regex, the same
    /// way the install sidecar is handled -- one bool does not justify a serializer, and
    /// the compiler this project uses has no JSON in the framework it targets.
    ///
    /// Every read is defensive: a missing file, an unreadable folder or a malformed value
    /// all fall back to the shipped default rather than throwing. A settings file is never
    /// worth failing a patch over.</summary>
    internal static class KmrpSettings
    {
        // Opt-out, not opt-in: the driver patch is the right default for almost everyone,
        // and the people who most need it are the least likely to know it exists. See
        // docs/third-party-driver-compat.md for what shipping it actually changes.
        private const bool DriverCompatibilityDefault = true;

        private const bool MarkerFixesDefault = true;
        // The bundled HD item icons, an option since 2026-10-08 (always installed
        // until then): a player asked on Deadly Stream why they were mandatory.
        private const bool HdIconsDefault = true;
        // ShaeMyName's Marked Empty Containers, a fourth patch since 2026-10-19 (issue
        // 43): on by default, at the maintainer's choice.
        private const bool MarkedEmptyContainersDefault = true;
        // D3M0's High FPS Fixes, a third patch. Off unless asked for, on the morning of
        // 2026-10-09; since that afternoon, at the maintainer's request, on by itself
        // where the display can run above 60 Hz (HighFpsFixAuto), because the game's
        // timing breaks above 60 frames a second without it. What the player sets in
        // Advanced Settings is kept either way (highFpsFixChosen).
        private const int HighFpsRefreshFloor = 62;   // 59, 60 and 61 Hz all count as 60

        /// <summary>The highest refresh rate the display reports (ResolutionSelection),
        /// asked once.</summary>
        internal static int DisplayRefresh
        {
            get
            {
                if (displayRefresh < 0)
                    displayRefresh = InstallPlatform.HighestRefresh(null);
                return displayRefresh;
            }
        }
        private static int displayRefresh = -1;

        /// <summary>High FPS Fix where the player has not chosen: on for a display that
        /// reports more than 60 Hz.</summary>
        internal static bool HighFpsFixAuto
        {
            get { return DisplayRefresh >= HighFpsRefreshFloor; }
        }
        // On by default since 2026-09-24, like the other two: Restore Defaults turns
        // all three on, and a default it does not restore would not be a default. It
        // costs a keyboard-and-mouse player nothing -- prompts appear only while a pad
        // is the active device -- and it carries the cursor confinement (issue #20).
        private const bool ControllerSupportDefault = true;
        // The one row that is off unless asked for: KMRP's diagnostic log files.
        private const bool DebugLogsDefault = false;

        private static bool loaded;
        private static bool driverCompatibility = DriverCompatibilityDefault;
        private static bool markerFixes = MarkerFixesDefault;
        private static bool hdIcons = HdIconsDefault;
        private static bool markedEmptyContainers = MarkedEmptyContainersDefault;
        private static bool highFpsFix;
        private static bool highFpsFixChosen;   // the settings file holds the player's own choice
        private static bool controllerSupport = ControllerSupportDefault;
        private static bool debugLogs = DebugLogsDefault;
        // The resolution checklist (ResolutionSelection): the display's sizes the player
        // unticked, and the sizes the display does not offer that they ticked. Both
        // empty is the default: every size the display supports, and no other.
        // The newer version the player asked not to be reminded of again, or "".
        private static string skippedUpdate = "";

        internal static string SettingsPath
        {
            get
            {
                string root = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return GamePath.Combine(GamePath.Combine(root, "KMRP"), "settings.json");
            }
        }

        /// <summary>Install the bundled modern-driver-compatibility patch alongside KMRP.</summary>
        internal static bool DriverCompatibility
        {
            get { Load(); return driverCompatibility; }
            set
            {
                Load();
                if (driverCompatibility == value)
                    return;
                driverCompatibility = value;
                Save();
            }
        }

        /// <summary>Apply Derslok's map-note position corrections (K1 Area Map Fixes).</summary>
        internal static bool MarkerFixes
        {
            get { Load(); return markerFixes; }
            set
            {
                Load();
                if (markerFixes == value)
                    return;
                markerFixes = value;
                Save();
            }
        }

        /// <summary>Show JackInTheBox's HD item icons (the patch's hd-icons option).</summary>
        internal static bool HdIcons
        {
            get { Load(); return hdIcons; }
            set
            {
                Load();
                if (hdIcons == value)
                    return;
                hdIcons = value;
                Save();
            }
        }

        /// <summary>Install ShaeMyName's Marked Empty Containers patch beside KMRP's: a
        /// container or corpse with nothing in it is named "... (empty)" when hovered.</summary>
        internal static bool MarkedEmptyContainers
        {
            get { Load(); return markedEmptyContainers; }
            set
            {
                Load();
                if (markedEmptyContainers == value)
                    return;
                markedEmptyContainers = value;
                Save();
            }
        }
        /// <summary>Install D3M0's High FPS Fixes patch beside KMRP's.</summary>
        internal static bool HighFpsFix
        {
            get { Load(); return highFpsFixChosen ? highFpsFix : HighFpsFixAuto; }
            set
            {
                Load();
                if (highFpsFixChosen && highFpsFix == value)
                    return;
                highFpsFix = value;
                highFpsFixChosen = true;
                Save();
            }
        }

        /// <summary>Forgets the player's choice: High FPS Fix follows the display again
        /// (Restore Defaults).</summary>
        internal static void ResetHighFpsFix()
        {
            Load();
            if (!highFpsFixChosen)
                return;
            highFpsFixChosen = false;
            Save();
        }

        /// <summary>Install KMRP's optional controller support.
        ///
        /// Since 2026-09-28 this switches only the controller's own hooks: KMRP's
        /// runtime and its core hooks (memory safety, mouse confinement, movie bars)
        /// install either way. Since 2026-09-29 it decides whether KMRP's installer
        /// installs the KMRP Controller patch (KpmEditionOperations.InstallEngine).
        ///
        /// Independent of DriverCompatibility since 2026-09-24, so neither option
        /// sets the other -- here, in the settings page, or when settings are loaded.
        /// The coupling lived in all three places, and removing only the page's copy
        /// left Load() turning driver compatibility back on.</summary>
        internal static bool ControllerSupport
        {
            get { Load(); return controllerSupport; }
            set
            {
                Load();
                if (controllerSupport == value)
                    return;
                controllerSupport = value;
                Save();
            }
        }

        /// <summary>Have KMRP's module write its diagnostic logs beside the game: the
        /// patch's debug-logs option (KmrpOptions.h). Off by default; errors and warnings
        /// are written to kmrp-kpm.log either way.</summary>
        internal static bool DebugLogs
        {
            get { Load(); return debugLogs; }
            set
            {
                Load();
                if (debugLogs == value)
                    return;
                debugLogs = value;
                Save();
            }
        }

        // "kotorPatchManager", the Advanced Settings option to install for KOTOR Patch
        // Manager (2026-09-29 to 2026-09-30), is no longer read or written: KPM's files in
        // the game folder decide that by themselves (KpmEditionOperations.Install). A
        // settings file that still has it loses it at the next save.

        /// <summary>The version the update prompt was told not to repeat ("Don't
        /// remind me again for 1.6.0"). A later version is announced as usual.</summary>
        internal static string SkippedUpdate
        {
            get { Load(); return skippedUpdate; }
            set
            {
                Load();
                string next = value ?? "";
                if (skippedUpdate == next)
                    return;
                skippedUpdate = next;
                Save();
            }
        }

        private static void Load()
        {
            if (loaded)
                return;
            loaded = true;
            try
            {
                string path = SettingsPath;
                if (!File.Exists(path))
                    return;
                string json = File.ReadAllText(path, Encoding.UTF8);
                Match match = Regex.Match(json,
                    "\\\"driverCompatibility\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (match.Success)
                    driverCompatibility = String.Equals(match.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match markers = Regex.Match(json,
                    "\\\"markerFixes\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (markers.Success)
                    markerFixes = String.Equals(markers.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match icons = Regex.Match(json,
                    "\\\"hdIcons\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (icons.Success)
                    hdIcons = String.Equals(icons.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match empty = Regex.Match(json,
                    "\\\"markedEmptyContainers\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (empty.Success)
                    markedEmptyContainers = String.Equals(empty.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match fps = Regex.Match(json,
                    "\\\"highFpsFix\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (fps.Success)
                {
                    highFpsFix = String.Equals(fps.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                    highFpsFixChosen = true;
                }
                Match controller = Regex.Match(json,
                    "\\\"controllerSupport\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (controller.Success)
                    controllerSupport = String.Equals(controller.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match debug = Regex.Match(json,
                    "\\\"debugLogs\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (debug.Success)
                    debugLogs = String.Equals(debug.Groups[1].Value, "true",
                        StringComparison.OrdinalIgnoreCase);
                Match skipped = Regex.Match(json,
                    "\\\"skippedUpdate\\\"\\s*:\\s*\\\"([0-9.]{1,32})\\\"",
                    RegexOptions.CultureInvariant);
                if (skipped.Success)
                    skippedUpdate = skipped.Groups[1].Value;
            }
            catch { }
        }

        private static void Save()
        {
            try
            {
                string path = SettingsPath;
                string folder = Path.GetDirectoryName(path);
                if (!Directory.Exists(folder))
                    Directory.CreateDirectory(folder);
                string json = "{\r\n" +
                    "  \"driverCompatibility\": " +
                    (driverCompatibility ? "true" : "false") + ",\r\n" +
                    "  \"markerFixes\": " +
                    (markerFixes ? "true" : "false") + ",\r\n" +
                    "  \"controllerSupport\": " +
                    (controllerSupport ? "true" : "false") +
                    (hdIcons ? "" : ",\r\n  \"hdIcons\": false") +
                    (markedEmptyContainers ? "" : ",\r\n  \"markedEmptyContainers\": false") +
                    (highFpsFixChosen ? ",\r\n  \"highFpsFix\": " + (highFpsFix ? "true" : "false") : "") +
                    (debugLogs ? ",\r\n  \"debugLogs\": true" : "") +
                    (skippedUpdate.Length > 0
                        ? ",\r\n  \"skippedUpdate\": \"" + skippedUpdate + "\""
                        : "") +
                    "\r\n}\r\n";
                File.WriteAllText(path, json, new UTF8Encoding(false));
            }
            catch { }
        }
    }

    /// <summary>Is there a newer KMRP than this one? When the window opens, one request
    /// to GitHub's "latest release" for this repository -- no identifier, nothing about
    /// the machine or the game, only the User-Agent GitHub requires -- and nothing when
    /// the patcher runs from the command line. Any failure (offline, rate limited, a
    /// five-second timeout, a tag that is not a version) is silence, never an error.
    ///
    /// Releases are tagged with the public version, "v1.5.0". The first release was
    /// tagged v2.10.0, its internal number, until 2026-09-25, when it was moved to
    /// v1.0.0 on the same commit; a 2.x tag compared as a version would have told
    /// every 1.5 player that "2.10.0" was newer.</summary>
    internal static class UpdateCheck
    {
        internal const string LatestReleaseApi =
            "https://api.github.com/repos/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases/latest";
        internal const string DownloadPage =
            "https://deadlystream.com/files/file/3096-kmrp-kotor-modern-restoration-patch/";

        /// <summary>The latest release's version, "1.6.0", or null.</summary>
        internal static string LatestVersion()
        {
            try
            {
                // TLS 1.2, which GitHub requires; .NET Framework 4 does not offer it by
                // default. 3072 is SecurityProtocolType.Tls12, by value for 4.0.
                ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072;
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(LatestReleaseApi);
                request.UserAgent = "KMRP/" + GoldPatch.PatchVersion;
                request.Accept = "application/vnd.github+json";
                request.Timeout = 5000;
                request.ReadWriteTimeout = 5000;
                using (WebResponse response = request.GetResponse())
                using (StreamReader reader = new StreamReader(response.GetResponseStream(), Encoding.UTF8))
                    return VersionFromReleaseJson(reader.ReadToEnd());
            }
            catch
            {
                return null;
            }
        }

        /// <summary>The version in a release's "tag_name", "v1.6.0" -> "1.6.0". A tag
        /// with anything after the numbers, "v1.6.0-beta", is not a release version.</summary>
        internal static string VersionFromReleaseJson(string json)
        {
            Match tag = Regex.Match(json ?? "",
                "\"tag_name\"\\s*:\\s*\"v?([0-9]{1,6}(?:\\.[0-9]{1,6}){1,3})\"",
                RegexOptions.CultureInvariant);
            return tag.Success ? tag.Groups[1].Value : null;
        }

        /// <summary>Is `candidate` a later version than `current`? Missing parts count
        /// as 0, so "1.6" is later than "1.5.0" and the same as "1.6.0".</summary>
        internal static bool IsNewer(string candidate, string current)
        {
            Version a = Parse(candidate);
            Version b = Parse(current);
            return a != null && b != null && a > b;
        }

        private static Version Parse(string text)
        {
            if (String.IsNullOrEmpty(text))
                return null;
            Match m = Regex.Match(text,
                "^v?([0-9]{1,6})(?:\\.([0-9]{1,6}))?(?:\\.([0-9]{1,6}))?(?:\\.([0-9]{1,6}))?$",
                RegexOptions.CultureInvariant);
            if (!m.Success)
                return null;
            int[] parts = new int[4];
            for (int i = 0; i < 4; i++)
                parts[i] = m.Groups[i + 1].Success
                    ? Int32.Parse(m.Groups[i + 1].Value, CultureInfo.InvariantCulture) : 0;
            return new Version(parts[0], parts[1], parts[2], parts[3]);
        }
    }

    // The controller prompt manifest's name, which GuiBlend.cs reads; the rest of the class draws
    // with GDI+ and is Windows only (ControllerPromptGenerator.cs).
    internal static partial class ControllerPromptGenerator
    {
        internal const string ManifestName = "kmrp_prompts.txt";
    }
}
