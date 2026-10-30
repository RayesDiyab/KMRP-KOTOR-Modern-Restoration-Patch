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
    // Engine installation is source-built by WindowsEnginePatch.
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
        internal const string PatchVersion = "1.5.1";

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

    internal static class ResolutionPatch
    {
        private static readonly long[] WidthOffsets = { 0x0000AA65, 0x001F0C65 };
        private static readonly long[] HeightOffsets = { 0x0000AA85, 0x001F0C6F };

        // Full-screen Bink playback has its own 640x480 display-mode pair, separate
        // from the normal render-resolution constants above.  The first pair is the
        // width/height comparison in the movie entry path (VA 0x00403D66); the
        // second initializes the temporary movie mode (VA 0x005F5B37).  Leaving
        // either pair at 640x480 makes the engine change display mode around a
        // movie, which is the source of the minimize/focus transition seen with
        // resolution-matched upscaled BIKs.  Both pairs are imm32 operands.
        //
        // A community helper searches for only `00 00 C7 44 24 10` for the second
        // pair.  That sequence occurs hundreds of times and its first match in this
        // executable is not a resolution at all.  These addresses instead come
        // from aligned disassembly of the verified source and are guarded by exact
        // gold-reference values on every application. See reverse-engineering/movies.md.
        // Internal: the KPM edition tags these as KMRP Movies' (KpmEdition.cs).
        // Since 2026-10-20 also the third pair, RestoreResolutionFromMovie's comparison
        // (VA 0x00403EA7 and 0x00403EB3): at 640x480 the game rebuilt its renderer and set
        // the display mode again after every full-screen movie (tools/build_windows_engine.py).
        internal static readonly long[] MovieWidthOffsets = { 0x00003D6C, 0x001F5B3B, 0x00003EAD };
        internal static readonly long[] MovieHeightOffsets = { 0x00003D78, 0x001F5B43, 0x00003EB9 };

        // 0x0028C4E3 (VA 0x0068C4E3) is a THIRD width comparison, deliberately NOT included
        // above. It's the last live branch of the HUD minimap-variant (mipc*.gui) selector:
        // vanilla compares the live screen width against a handful of hardcoded pixel widths
        // to choose which mipc*.gui HUD layout to load (the other two branches are already
        // zeroed/disabled in gold, matching the community "Resolution Unlocker" fix, so they
        // never match). Previously this field was included in WidthOffsets, which made
        // ResolutionPatch overwrite it with resolution.Width every build -- making the
        // comparison "liveWidth == liveWidth", tautologically true, so EVERY resolution ever
        // shipped force-loaded mipc210x7.gui (the one file hand-corrected for 3440x1440)
        // regardless of actual aspect ratio, corrupting minimap/HUD icon layout at every other
        // resolution (confirmed: 1920x1080's journal/cash/item icons and the combat message
        // box both end up overlapping the oversized minimap frame). Leaving this field
        // untouched keeps gold's own baked-in value (3440) permanently, so the comparison is
        // now "liveWidth == 3440": mipc210x7.gui still loads correctly at 3440x1440 (the only
        // resolution it was ever hand-tuned for), while every other resolution now correctly
        // falls through to vanilla's own generic default branch (mipc28x6.gui) instead of the
        // wrong ultra-wide-specific file.

        // Negated screen-width/height reference constants used by two shared widget-geometry
        // recentering helpers (vanilla 0x0040B690 / 0x0040BA20) called from essentially every
        // non-main-menu/non-HUD GUI screen. They compute
        //   newX = originalX - (liveScreenWidth  - DESIGN_WIDTH)  / 2
        //   newY = originalY - (liveScreenHeight - DESIGN_HEIGHT) / 2
        // The gold reference build baked in its own resolution (-3440/-1440) as DESIGN_WIDTH/
        // DESIGN_HEIGHT instead of leaving these resolution-agnostic, so the recentering was a
        // no-op only at exactly 3440x1440 and drifted proportionally to distance from it at any
        // other resolution -- the general PC-screen click-offset bug. Found via
        // generate_gold_delta.py's changed_ranges() surfacing these as previously-undocumented
        // gold-delta chunks, then confirmed by disassembly (tools/build_click_fix_wrapper.py).
        private static readonly long[] NegativeWidthOffsets = { 0x0000B6C7, 0x0000BA6C };
        private static readonly long[] NegativeHeightOffsets = { 0x0000B6DA, 0x0000BA83 };

        // The .kfs section (tools/build_font_scale_wrapper.py, baked into the gold
        // reference) holds two 32-bit float scale constants at its very start.
        //
        // Text size itself is NOT scaled here any more: doing it at runtime mutated the
        // shared CAurFontInfo metrics on first draw, one frame after the engine had
        // already measured and centred the text with the unscaled values, which visibly
        // shifted the first screen drawn each session. Font sizing now happens in the
        // font atlases' own TXI metrics instead (tools/build_scaled_fonts.py, shipped per
        // resolution in the GUI archives), so the values are correct before anything
        // measures them. Gold therefore ships the font constant at 1.0 and it stays there.
        //
        // Generic list-row heights keep scaling at runtime: that hook rewrites a row's
        // height as the row is constructed, with nothing having measured it beforehand,
        // so it has no such ordering problem. Rows must grow with the text or entries
        // overlap (originally seen on the save/load list), so this constant is rescaled
        // per resolution using the same height-proportional rule as the font TXIs and the
        // HUD geometry. Clamped at 1.0 so short screens keep vanilla row heights.
        // Text (and therefore row) size grows linearly with screen height: 1.25x at
        // 1080p, 1.75x at 1440p, 2.75x at 2160p. The -0.25 offset holds the scaling a
        // little under a pure height ratio, which read as too large in play-testing.
        // Clamped at 1.0, which takes effect below 900px, so short screens keep vanilla
        // sizing rather than shrinking below it.
        // Inventory item rows size themselves from THREE hardcoded 56s, all
        // independent of resolution and of the font -- which is why enlarged text
        // left the rows and their icons stranded at vanilla size, and why nothing
        // in inventory.gui could move them (PROTOITEM's own 100px EXTENT.HEIGHT is
        // read into the control and then never used for the row).
        //
        //   0x002B527F  mov edi,56              icon box 56x56, text left offset,
        //                                       and text width = row width - 56
        //   0x002B4FA9  mov [esp+0x1C],56       row height -> CSWGuiInGameItemEntry::SetRect
        //   0x002B55E3  mov [esp+0x18],56       row height, second layout path
        //
        // The height ones feed row+0x10, which the listbox harvests as
        // `[listbox+0x2B4] = max(item->height)` and then uses as every row's rect
        // height; row pitch is that plus the GUI's PADDING byte. Patching only the
        // icon constant therefore grows the icons INTO the row below -- all three
        // must move together. Traced and confirmed live under x32dbg.
        //
        // Scaled by the same height rule as the fonts so rows grow with the text.
        // Unlike RowScaleOffset these are reached only by the inventory item row,
        // so they cannot disturb the save/load, journal or resolution lists.
        // Three screens build their list rows from the same class shape, each with
        // its own hardcoded size: the first constant is the row's square icon box
        // (and therefore the text's left offset and width), the rest are the row
        // HEIGHT handed to SetRect. Found by scanning for the shape rather than the
        // value -- `mov <reg>,imm ; cmp <reg2>,<reg> ; jle` locates the icon site in
        // each row class, and `mov [esp+X],imm` right before `call [<reg>+4]`
        // locates the height sites.
        //
        //   inventory  56  0x002B527F icon   0x002B4FA9 + 0x002B55E3 height
        //   abilities  42  0x002AB8EF icon   0x002ACB20 height
        //   store      56  0x002C265F icon   0x002C2A23 height
        //
        // All are imm32, so they take any scale. Each group's icon and height MUST
        // move together: patching the icon alone grows it into the row below, which
        // is exactly what the first inventory attempt did (confirmed in game).
        // Details and the full call chain in
        // reverse-engineering/inventory-item-rows.md.
        // The item STACK-COUNT label, built inside the inventory row's SetRect
        // (0x006B5270) and present in no .gui file. It is bottom-right-aligned
        // INSIDE the icon box: height 19, width 21 for one or two digits and 42 for
        // three or more (`and ecx,21` / `add ecx,21` after a `strlen <= 2` test),
        // top offset 37 -- and 37 + 19 = 56, the vanilla icon size. Scaling the icon
        // without these left a 21x19 label in the corner of a box twice the size,
        // and an enlarged font needs 22px for the widest two-digit pair, so the
        // digits vanished entirely.
        //
        // The width and top operands were originally imm8 (sign-extended), which
        // capped them at 127 -- at 7680x4320 the icon is 336px while the top offset
        // would have stopped at 127, floating the label partway up the icon instead
        // of sitting in its corner. tools/build_stack_count_fix.py relocates that
        // arithmetic into a `.ksc` stub with imm32 operands (gold v10), so all four
        // scale without limit and no clamp is needed.
        // {file offset, operand size in bytes, vanilla value}
        private static readonly int[][] StackCountSites =
        {
            new[] { 0x002B5332, 4, 19 },   // mov [esp+2C], 19  label height (in place)
            new[] { 0x003DF003, 4, 21 },   // and ecx, 21       width, 1-2 digits (.ksc)
            new[] { 0x003DF009, 4, 21 },   // add ecx, 21       width, 3+ digits (.ksc)
            new[] { 0x003DF020, 4, 37 },   // add eax, 37       top offset       (.ksc)
        };

        // {expected vanilla value, value to scale from, offsets...}. The two differ
        // only for the feat/power chain rows, which read too small at the vanilla
        // 40 once everything around them grew -- 50 was chosen by eye in game
        // (100px at 3440x1440) and is a deliberate design choice, not a measurement.
        // The shared message popup (confirm.gui and every tutorial hint) sizes
        // itself in code, not from its .gui, so its geometry has to scale with the
        // font the same way the .gui layout does -- see scale_message_popup.py,
        // whose TUNED table is the matching half of this. Gold bakes the values
        // play-tested at 3440x1440, i.e. font scale 2.0; the second column is the
        // scale-1.0 base, so at 1440p this reproduces gold exactly.
        //
        // Each cap has TWO sites. Patching one leaves the other clamping -- the
        // same "there is always a second copy" pattern as gold v11's three row
        // pitch sites and v12's two rect builders.
        // Area map marker geometry. The overlay markers are drawn on grows with the
        // screen (canvasWidth x 440/512 by canvasHeight), but these rectangles were
        // built from vanilla immediates, so relative to the map they shrank by
        // exactly the factor the overlay grew -- 20 px on a 440-wide overlay is 4.5%
        // of the map, the same 20 px on 1478 is 1.4%.
        //
        // The factor is ScaleForHeight -- max(1, height/720), the same rule the fonts
        // and list rows use -- giving a 2x marker at 1440p. Full proportional scaling
        // against the overlay (screenWidth/1024, 3.36x at 3440x1440) was tried first
        // and play-tested too large. Gold bakes the 3440x1440 values; the second
        // column is vanilla, i.e. factor 1.0.
        //
        // There are TWO map-note paths: 0x0069470B branches on whether the note is
        // the selected one, and each side builds its own rectangle. Scaling only the
        // selected side leaves every other note at vanilla size, which is what the
        // first attempt shipped.
        //
        // Every marker's centring offset is -size/2 and MUST move with its size, or
        // the icon drifts off the point it marks.
        private static readonly int[][] MarkerSizeSites =
        {
            //     gold, vanilla, imm32 offsets...
            new[] {   40,   20, 0x00294720 },   // map note size, selected
            new[] {   28,   14, 0x00294763 },   // map note size, UNSELECTED
            new[] {   32,   16, 0x00294A13 },   // party marker size
            new[] {   64,   32, 0x00294AC4 },   // player arrow size
            new[] {   64,   32, 0x0029405B },   // mm_barrow control extent
            new[] {   32,   16, 0x002940DC },   // lbl_mapcircle control extent
        };

        // Same, for the `add r32, imm8` centring offsets. These are signed bytes,
        // so the factor is clamped at 127/16 -- see MarkerScaleForWidth.
        private static readonly int[][] MarkerOffsetSites =
        {
            new[] {  -20,  -10, 0x0029471A, 0x00294726 },   // note, selected
            new[] {  -14,   -7, 0x00294777, 0x0029477A },   // note, UNSELECTED
            new[] {  -16,   -8, 0x00294A53, 0x00294A56 },   // party
            new[] {  -32,  -16, 0x00294AD0, 0x00294AD4 },   // arrow
        };

        // The largest offset is the arrow's size/2, and it has to fit in a signed
        // byte, so the scale cannot exceed 127/16. The scale follows the HEIGHT, so
        // that binds only above ~5715 px tall: of the 48 shipped resolutions
        // 15360x8640 alone gets under-scaled markers (a third short), still
        // correctly centred. (This said 8192x4608 too, reasoning from width; read
        // back from its output, 8192x4608 is unclamped.) Lifting it needs
        // the adds widened to imm32 in a stub, as the stack-count label needed in
        // gold v10.
        private const float MarkerMaxScale = 127.0f / 16.0f;

        internal static float MarkerScaleForHeight(int height)
        {
            float scale = ScaleForHeight(height);
            return scale > MarkerMaxScale ? MarkerMaxScale : scale;
        }

        private static readonly int[][] PopupSizeGroups =
        {
            //     gold, base@1.0, offsets...
            new[] {  900,  450, 0x002256E3, 0x00225759 },   // auto-fit height stop
            // The width cap is what fixes clipped message text: the auto-fit loop
            // widens the popup 40 units at a time to fit its message, but only
            // while the panel is narrower than this. Authored 440 for 640x480, so
            // at any HD size the panel already exceeds it and the loop never runs.
            new[] { 1600,  800, 0x002256DC, 0x002256F6 },   // auto-fit width cap
            // The icon rect and the inset the message text is pushed down by. They
            // must move together or the text runs under the icon -- and the rect
            // must match the tut_*.tga size GameArtGenerator makes (64s),
            // because the engine draws GUI textures one texel per pixel: a smaller
            // texture TILES, a larger one is CROPPED.
            new[] {  128,   64, 0x00226F95, 0x0022540D },   // icon rect, message inset
        };

        private static readonly int[][] RowSizeGroups =
        {
            new[] { 56, 56, 0x002B527F, 0x002B4FA9, 0x002B55E3 },   // inventory
            // The Skills tab's rows from 50, as the Feats and Powers tabs' chain rows
            // below: one list shows all three tabs, and rows of two heights left one
            // tab's gaps loose at every height (2026-09-30).
            new[] { 42, 50, 0x002AB8EF, 0x002ACB20 },               // abilities: skills tab (1.19x)
            new[] { 56, 56, 0x002C265F, 0x002C2A23 },               // store / merchant
            // The Abilities screen's Powers and Feats tabs are NOT listbox rows and
            // share nothing with the three above -- each row is a feat/power
            // progression chain, built at 0x006CD8CD / 0x006CDB6D as a hardcoded
            // 242x40 rect and laid out by 0x006CCE30 (the chain row's SetRect,
            // which also draws the lbl_skarr arrows and the lbl_indent backing).
            // Only the HEIGHT is scaled: it drives the icon squares inside the row,
            // and doubling it alone was confirmed in game. The width (242, at
            // 0x002CD8D1/0x002CDB71) and the arrow square (32, at 0x002CCE5F) are
            // deliberately left alone -- untested, and the listbox appears to
            // stretch the row's width itself.
            new[] { 40, 50, 0x002CD8D9, 0x002CDB79 },               // abilities: powers/feats chain rows (1.25x)
        };

        // The Options screens' check boxes (Feedback's list, Auto-pause, Gameplay, Graphics,
        // Advanced Graphics, Mouse, Advanced Sound), CSWGuiOptionsCheckbox::SetExtent at
        // 0x006DE000: the circle's four state images in a fixed 25x25 square at the control's
        // left, 2 px below its middle, and the label 30 px in, at every resolution -- a 25 px
        // circle in toggles over 100 px tall at 1440p and up, where vanilla drew it in 43- and
        // 60-px ones. Scaled like the rows, 25s, 2s and 30s, as the Mac's layout patch does
        // (macos/patches/kmrp-layout/resolution_sizes.cpp, AddCheckboxes; the Mac replaces the
        // whole function). Found on the Mac by reading the code, 2026-09-30
        // (docs/windows-changes-from-macos.md, item 13).
        //
        //   0x006DE011  ba 19000000     mov edx, 25            the square, imm32
        //   0x006DE02E  8d 4c 01 02     lea ecx, [ecx+eax+2]   below the middle, disp8
        //   0x006DE08E  83 e9 1e        sub ecx, 30            the label's width
        //   0x006DE091  83 c0 1e        add eax, 30            the label's left
        //
        // The square takes any scale and the drop fits its signed byte up to s = 63, but the
        // label's two immediates are signed bytes too, and 30s passes 127 above 3048 px tall
        // (180 at 7680x4320). Rather than cap the scale, as the map markers do, the two are
        // replaced by a jump into the 15 bytes of NOP padding after the function's `ret 4`
        // (0x006DE0D1..0x006DE0DF, which nothing reaches), where the same two operations
        // take imm32 operands and jump back to 0x006DE094. Flags are not read before the
        // next write. Written at every resolution, 720 and below too, where 30 is vanilla's.
        private const long CheckboxSquareOffset = 0x002DE012;
        private const long CheckboxDropOffset = 0x002DE031;
        private const long CheckboxLabelOffset = 0x002DE08E;
        private const long CheckboxCaveOffset = 0x002DE0D1;
        private static readonly byte[] CheckboxLabelVanilla = { 0x83, 0xE9, 0x1E, 0x83, 0xC0, 0x1E };
        // jmp 0x006DE0D1 (rel32 0x3E from 0x006DE093), then a NOP never reached.
        private static readonly byte[] CheckboxLabelJump = { 0xE9, 0x3E, 0x00, 0x00, 0x00, 0x90 };
        private const int CheckboxCaveLength = 13;   // sub ecx, imm32 (6); add eax, imm32 (5); jmp short (2)

        // The message popup's widening step, in CSWGuiMessageBox::FixMessageLabel
        // (0x006253A0). A box whose text does not fit grows in a loop: each pass adds 40
        // to the width (and takes 20 off the left) while the width is under its cap, and
        // one line of the font to the height. The caps and the line follow the screen
        // (PopupSizeGroups; the font is baked for the height); the 40 never did, so the
        // same text made a wide box at a low resolution and a tall, narrow one at a high
        // one (seen on the Mac at 3840x2160; docs/windows-changes-from-macos.md, item 24).
        //
        //   0x006256FC  83 44 24 38 28   add [esp+38], 40
        //   0x00625701  8b 44 24 20      mov eax, [esp+20]
        //   0x00625705  83 c1 28         add ecx, 40
        //   0x00625708  89 4c 24 28      mov [esp+28], ecx
        //   0x0062570C  83 e8 14         sub eax, 20
        //   0x0062570F  8d 4c 24 30      lea ecx, [esp+30]
        //   0x00625713  89 44 24 20      mov [esp+20], eax
        //
        // The three numbers are signed bytes and cannot hold 120. The same 27 bytes with
        // one 32-bit step, 40s (eax is loaded anew at 0x00625717 and no flag is read):
        //   mov eax, step ; add [esp+38], eax ; add ecx, eax ; mov [esp+28], ecx ;
        //   sar eax, 1 ; sub [esp+20], eax ; lea ecx, [esp+30] ; nop ; nop
        private const long PopupStepOffset = 0x002256FC;
        private static readonly byte[] PopupStepVanilla =
        {
            0x83, 0x44, 0x24, 0x38, 0x28, 0x8B, 0x44, 0x24, 0x20, 0x83, 0xC1, 0x28, 0x89, 0x4C,
            0x24, 0x28, 0x83, 0xE8, 0x14, 0x8D, 0x4C, 0x24, 0x30, 0x89, 0x44, 0x24, 0x20,
        };
        private static readonly byte[] PopupStepCode =
        {
            0xB8, 0x28, 0x00, 0x00, 0x00, 0x01, 0x44, 0x24, 0x38, 0x01, 0xC1, 0x89, 0x4C, 0x24,
            0x28, 0xD1, 0xF8, 0x29, 0x44, 0x24, 0x20, 0x8D, 0x4C, 0x24, 0x30, 0x90, 0x90,
        };

        // The stack-count label of a STORE row, in CSWGuiStoreItemEntry::SetExtent
        // (0x006C2650). The inventory's is 21s wide (42s for three digits or more) and 19s
        // tall in the icon's lower right corner (StackCountSites). The store's kept the
        // game's own: 21 or 42 wide whatever the screen, as tall as the icon, at the row's
        // top (docs/windows-changes-from-macos.md, item 26; on the Mac the count stood in
        // the icon's upper right corner, half outside the frame).
        //
        //   0x006C2704  33 c9            xor ecx, ecx
        //   0x006C2706  83 f8 02         cmp eax, 2            the count's length
        //   0x006C2709  0f 9e c1         setle cl
        //   0x006C270C  8b d7            mov edx, edi          edi: the icon's size
        //   0x006C270E  89 7c 24 2c      mov [esp+2c], edi     height
        //   0x006C2712  49               dec ecx
        //   0x006C2713  83 e1 15         and ecx, 21
        //   0x006C2716  83 c1 15         add ecx, 21
        //   0x006C2719  8b c1            mov eax, ecx
        //   0x006C271B  2b d0            sub edx, eax
        //   0x006C271D  89 44 24 28      mov [esp+28], eax     width
        //   0x006C2721  8b 44 24 20      mov eax, [esp+20]
        //   0x006C2725  03 c2            add eax, edx
        //   0x006C2727  8d 8e 34030000   lea ecx, [esi+334]
        //   0x006C272D  8d 54 24 20      lea edx, [esp+20]
        //   0x006C2731  89 44 24 20      mov [esp+20], eax     left
        //
        // The same 49 bytes by the inventory's rule, with 32-bit operands (eax is loaded
        // anew at 0x006C2735; ecx and edx leave as the game leaves them):
        //   cmp eax, 2 ; mov ecx, 21s ; jle +2 ; add ecx, ecx ; mov [esp+28], ecx ;
        //   add [esp+20], edi ; sub [esp+20], ecx ; mov eax, 19s ; mov [esp+2c], eax ;
        //   sub eax, edi ; sub [esp+24], eax ; lea ecx, [esi+334] ; lea edx, [esp+20]
        // so the top is the row's top and the icon less the label's height: the game's 37
        // at its own size (56 - 19). Built, not yet seen in the game.
        private const long StoreCountOffset = 0x002C2704;
        private static readonly byte[] StoreCountVanilla =
        {
            0x33, 0xC9, 0x83, 0xF8, 0x02, 0x0F, 0x9E, 0xC1, 0x8B, 0xD7, 0x89, 0x7C, 0x24, 0x2C,
            0x49, 0x83, 0xE1, 0x15, 0x83, 0xC1, 0x15, 0x8B, 0xC1, 0x2B, 0xD0, 0x89, 0x44, 0x24,
            0x28, 0x8B, 0x44, 0x24, 0x20, 0x03, 0xC2, 0x8D, 0x8E, 0x34, 0x03, 0x00, 0x00, 0x8D,
            0x54, 0x24, 0x20, 0x89, 0x44, 0x24, 0x20,
        };
        private static readonly byte[] StoreCountCode =
        {
            0x83, 0xF8, 0x02, 0xB9, 0x15, 0x00, 0x00, 0x00, 0x7E, 0x02, 0x03, 0xC9, 0x89, 0x4C,
            0x24, 0x28, 0x01, 0x7C, 0x24, 0x20, 0x29, 0x4C, 0x24, 0x20, 0xB8, 0x13, 0x00, 0x00,
            0x00, 0x89, 0x44, 0x24, 0x2C, 0x2B, 0xC7, 0x29, 0x44, 0x24, 0x24, 0x8D, 0x8E, 0x34,
            0x03, 0x00, 0x00, 0x8D, 0x54, 0x24, 0x20,
        };

        private const long RowScaleOffset = 0x003DD004;
        private const float GoldRowScale = 1.75f;
        private const float ScaleHeightDivisor = 720.0f;
        // Text sizing is height/720 with no offset: 1.00x at 720p, 1.50x at
        // 1080p, 2.00x at 1440p, 3.00x at 2160p. An earlier -0.25 offset made
        // 1440p and 2160p read as 1.75x/2.75x, which play-tested too small.
        // MUST stay in step with font_scale_for() in
        // tools/prepare_universal_resources.py, which sizes the atlas metrics.
        private const float ScaleOffset = 0.0f;

        internal static float ScaleForHeight(int height)
        {
            float scale = height / ScaleHeightDivisor - ScaleOffset;
            return scale < 1.0f ? 1.0f : scale;
        }

        internal static void Apply(byte[] executable, ResolutionChoice resolution)
        {
            if (executable == null || executable.LongLength != GoldPatch.TargetLength)
                throw new InvalidDataException("The executable image has an unexpected size.");

            foreach (long offset in WidthOffsets)
                ReplaceInt32(executable, offset, 3440, resolution.Width, "screen width");
            foreach (long offset in HeightOffsets)
                ReplaceInt32(executable, offset, 1440, resolution.Height, "screen height");
            foreach (long offset in MovieWidthOffsets)
                ReplaceInt32(executable, offset, 3440, resolution.Width, "movie display-mode width");
            foreach (long offset in MovieHeightOffsets)
                ReplaceInt32(executable, offset, 1440, resolution.Height, "movie display-mode height");
            ReplaceSingle(executable, RowScaleOffset, GoldRowScale, ScaleForHeight(resolution.Height),
                "list-row scale");
            float rowSizeScale = ScaleForHeight(resolution.Height);
            foreach (int[] site in StackCountSites)
                ReplaceInt32(executable, site[0], site[2],
                             (int)Math.Round(site[2] * rowSizeScale), "stack-count label");

            foreach (int[] group in RowSizeGroups)
            {
                int expected = group[0];
                int scaled = (int)Math.Round(group[1] * rowSizeScale);
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], expected, scaled, "list row/icon size");
            }

            foreach (int[] group in PopupSizeGroups)
            {
                int expected = group[0];
                int scaled = (int)Math.Round(group[1] * rowSizeScale);
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], expected, scaled, "message popup size");
            }

            // The Options check boxes (CheckboxSquareOffset and the rest, above).
            int checkboxLabel = (int)Math.Round(30 * rowSizeScale);
            ReplaceInt32(executable, CheckboxSquareOffset, 25, (int)Math.Round(25 * rowSizeScale),
                "check box size");
            ReplaceSByte(executable, CheckboxDropOffset, 2, (int)Math.Round(2 * rowSizeScale),
                "check box offset");
            ReplaceBytes(executable, CheckboxLabelOffset, CheckboxLabelVanilla, CheckboxLabelJump,
                "check box label");
            byte[] cave = new byte[CheckboxCaveLength];
            cave[0] = 0x81;                                  // sub ecx, imm32
            cave[1] = 0xE9;
            Buffer.BlockCopy(BitConverter.GetBytes(checkboxLabel), 0, cave, 2, 4);
            cave[6] = 0x05;                                  // add eax, imm32
            Buffer.BlockCopy(BitConverter.GetBytes(checkboxLabel), 0, cave, 7, 4);
            cave[11] = 0xEB;                                 // jmp short 0x006DE094
            cave[12] = 0xB6;
            byte[] padding = new byte[CheckboxCaveLength];
            for (int i = 0; i < padding.Length; i++)
                padding[i] = 0x90;
            ReplaceBytes(executable, CheckboxCaveOffset, padding, cave, "check box label");

            // The message popup's widening step (PopupStepOffset, above).
            byte[] popupStep = (byte[])PopupStepCode.Clone();
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(40 * rowSizeScale)), 0, popupStep, 1, 4);
            ReplaceBytes(executable, PopupStepOffset, PopupStepVanilla, popupStep, "message popup step");

            // The store row's stack-count label (StoreCountOffset, above).
            byte[] storeCount = (byte[])StoreCountCode.Clone();
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(21 * rowSizeScale)), 0, storeCount, 4, 4);
            Buffer.BlockCopy(BitConverter.GetBytes((int)Math.Round(19 * rowSizeScale)), 0, storeCount, 25, 4);
            ReplaceBytes(executable, StoreCountOffset, StoreCountVanilla, storeCount, "store stack-count label");

            float markerScale = MarkerScaleForHeight(resolution.Height);
            foreach (int[] group in MarkerSizeSites)
            {
                int scaled = (int)Math.Round(group[1] * markerScale);
                if (scaled < 1) scaled = 1;
                for (int i = 2; i < group.Length; i++)
                    ReplaceInt32(executable, group[i], group[0], scaled, "map marker size");
            }
            foreach (int[] group in MarkerOffsetSites)
            {
                int scaled = -(int)Math.Round(-group[1] * markerScale);
                if (scaled > -1) scaled = -1;
                for (int i = 2; i < group.Length; i++)
                    ReplaceSByte(executable, group[i], group[0], scaled, "map marker centring");
            }
            foreach (long offset in NegativeWidthOffsets)
                ReplaceInt32(executable, offset, -3440, -resolution.Width, "click-fix width reference");
            foreach (long offset in NegativeHeightOffsets)
                ReplaceInt32(executable, offset, -1440, -resolution.Height, "click-fix height reference");
            ReplaceInt32(executable, 0x002928B3, 2750, resolution.CenteringWidth, "map horizontal centering");
            ReplaceInt32(executable, 0x002928C3, 1400, resolution.CenteringHeight, "map vertical centering");
            ReplaceInt32(executable, 0x0029505C, 1720, resolution.CanvasWidth, "map canvas width");
            ReplaceInt32(executable, 0x00295064, 720, resolution.CanvasHeight, "map canvas height");
            ReplaceInt32(executable, 0x00295082, 1478, resolution.OverlayWidth, "marker overlay width");
            ReplaceInt32(executable, 0x0029508A, 720, resolution.CanvasHeight, "marker overlay height");
        }

        /// <summary>When set, every field Apply reads or writes, as {FILE offset, size}:
        /// WindowsEnginePatch checks them against its source-authored guard coverage,
        /// including fields the old gold snapshot left at their vanilla value.</summary>
        internal static List<long[]> Touched;

        private static void Touch(long offset, int size)
        {
            if (Touched != null)
                Touched.Add(new[] { offset, size });
        }

        private static void ReplaceSingle(byte[] data, long offset, float expected, float replacement, string label)
        {
            Touch(offset, 4);
            if (offset < 0 || offset + 4 > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            int index = checked((int)offset);
            float actual = BitConverter.ToSingle(data, index);
            if (actual != expected)
                throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            byte[] value = BitConverter.GetBytes(replacement);
            Buffer.BlockCopy(value, 0, data, index, value.Length);
        }

        /// <summary>Code, not a value: `expected` must be there whole, and is replaced by
        /// `replacement` of the same length.</summary>
        private static void ReplaceBytes(byte[] data, long offset, byte[] expected, byte[] replacement, string label)
        {
            Touch(offset, expected.Length);
            if (replacement.Length != expected.Length || offset < 0 || offset + expected.Length > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            for (int i = 0; i < expected.Length; i++)
                if (data[offset + i] != expected[i])
                    throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            Buffer.BlockCopy(replacement, 0, data, checked((int)offset), replacement.Length);
        }

        private static void ReplaceSByte(byte[] data, long offset, int expected, int replacement, string label)
        {
            Touch(offset, 1);
            if (replacement < -128 || replacement > 127)
                throw new InvalidDataException("The " + label + " value " + replacement +
                    " does not fit in a signed byte.");
            sbyte found = unchecked((sbyte)data[offset]);
            if (found != expected)
                throw new InvalidDataException("The " + label + " field held " + found +
                    " where " + expected + " was expected.");
            data[offset] = unchecked((byte)(sbyte)replacement);
        }

        /// <summary>FILE offset of the .kmn enable flag. Non-zero applies Derslok's 250
        /// map-note position corrections; zero makes the lookup return immediately, so the
        /// table is inert rather than absent. See tools/build_map_note_table.py.</summary>
        internal const long MapNoteFlagOffset = 0x003E4000;

        internal static void WriteInt32(byte[] data, long offset, int value)
        {
            Touch(offset, 4);
            byte[] encoded = BitConverter.GetBytes(value);
            Buffer.BlockCopy(encoded, 0, data, checked((int)offset), encoded.Length);
        }

        private static void ReplaceInt32(byte[] data, long offset, int expected, int replacement, string label)
        {
            Touch(offset, 4);
            if (offset < 0 || offset + 4 > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            int index = checked((int)offset);
            int actual = BitConverter.ToInt32(data, index);
            if (actual != expected)
                throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            byte[] value = BitConverter.GetBytes(replacement);
            Buffer.BlockCopy(value, 0, data, index, value.Length);
        }
    }

    internal sealed class IniEditState
    {
        internal string Path;
        internal byte[] OriginalBytes;
        internal bool Changed;
    }

    internal static class IniOperations
    {
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

        internal static IniEditState Configure(string executablePath, int width, int height, Action<string> report)
        {
            string iniPath = PathForExecutable(executablePath);
            if (!File.Exists(iniPath))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before patching.",
                    iniPath);

            byte[] original = File.ReadAllBytes(iniPath);
            EnsureVerifiedBackup(executablePath, original, report);

            Encoding encoding;
            int preambleLength;
            DetectEncoding(original, out encoding, out preambleLength);
            string text = encoding.GetString(original, preambleLength, original.Length - preambleLength);
            string updated = UpdateResolution(text, width, height);
            byte[] updatedBytes = Encode(updated, encoding, preambleLength > 0);

            IniEditState state = new IniEditState
            {
                Path = iniPath,
                OriginalBytes = original,
                Changed = !BytesEqual(original, updatedBytes)
            };

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
            string backupPath = BackupPath(executablePath);
            string hashPath = BackupHashPath(executablePath);
            if (!File.Exists(backupPath))
            {
                SafeReport(report, "No swkotor.ini backup exists; INI restore was skipped.");
                return;
            }
            if (!File.Exists(hashPath))
                throw new InvalidDataException("The swkotor.ini backup verification record is missing. Restore was blocked.");

            string expectedHash = File.ReadAllText(hashPath, Encoding.ASCII).Trim().ToUpperInvariant();
            string actualHash = GoldPatch.HashFile(backupPath);
            if (expectedHash.Length != 64 || actualHash != expectedHash)
                throw new InvalidDataException("The swkotor.ini backup failed its integrity check. Restore was blocked.");

            string iniPath = PathForExecutable(executablePath);
            WriteBytesAtomically(iniPath, File.ReadAllBytes(backupPath));
            if (GoldPatch.HashFile(iniPath) != expectedHash)
                throw new IOException("Post-restore swkotor.ini verification failed.");
            SafeReport(report, "Restored the previous swkotor.ini settings.");
        }

        private static void EnsureVerifiedBackup(string executablePath, byte[] original, Action<string> report)
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
                return;
            }

            WriteBytesNew(backupPath, original);
            if (GoldPatch.HashFile(backupPath) != originalHash)
            {
                File.Delete(backupPath);
                throw new IOException("swkotor.ini backup verification failed. No INI change was applied.");
            }
            try
            {
                File.WriteAllText(hashPath, originalHash + "\r\n", Encoding.ASCII);
            }
            catch
            {
                File.Delete(backupPath);
                throw;
            }
            SafeReport(report, "INI backup created: " + backupPath);
        }

        private static string UpdateResolution(string text, int width, int height)
        {
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
                output.AddRange(FrameRateLines(width, height));
            }
            else
            {
                for (int index = 0; index <= sectionStart; index++)
                    output.Add(lines[index]);
                output.Add("Height=" + height.ToString(CultureInfo.InvariantCulture));
                output.Add("Width=" + width.ToString(CultureInfo.InvariantCulture));
                output.AddRange(FrameRateLines(width, height));
                for (int index = sectionStart + 1; index < sectionEnd; index++)
                {
                    if (!IsResolutionKey(lines[index]))
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

        private static bool IsResolutionKey(string line)
        {
            int equals = line.IndexOf('=');
            if (equals < 0)
                return false;
            string key = line.Substring(0, equals).Trim();
            if (String.Equals(key, "Width", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(key, "Height", StringComparison.OrdinalIgnoreCase))
                return true;
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
            string temporaryPath = path + ".kotor-ui-new-" + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                WriteBytesNew(temporaryPath, data);
                if (File.Exists(path))
                    FileGuard.Replace(temporaryPath, path);
                else
                    File.Move(temporaryPath, path);
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
                if (File.Exists(target) && GoldPatch.HashFile(target) != record.InstalledHash)
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

        private static string InUseMessage(string path)
        {
            return Path.GetFileName(path) + " is being used by another program, so it " +
                "could not be updated. Close KOTOR, Steam, and any editor with the file " +
                "open, then try again.";
        }
    }

    /// <summary>KMRP's own files in a game folder, in one folder of their own, KMRP: the
    /// logs in KMRP\logs and what a restore puts back in KMRP\backups (the maintainer,
    /// 2026-10-20: "we shouldnt clutter the folder like this"). What the game or KOTOR
    /// Patch Manager loads from the game folder itself stays there: KPM's runtime,
    /// patch_config.toml, patches\ and configs\, and K1DC's dinput8.dll and .asi.
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

        internal static void ApplyToNewFile(string sourcePath, string outputPath, int width, int height)
        {
            sourcePath = Path.GetFullPath(sourcePath);
            outputPath = Path.GetFullPath(outputPath);
            RequireExistingFile(sourcePath);
            if (String.Equals(sourcePath, outputPath, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Source and output paths must be different.");
            if (File.Exists(outputPath))
                throw new IOException("Output file already exists: " + outputPath);

            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);
            byte[] target = WindowsEnginePatch.ApplyToExecutable(File.ReadAllBytes(sourcePath), resolution,
                KmrpSettings.MarkerFixes);
            WriteVerifiedFile(outputPath, target, GoldPatch.HashBytes(target));
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
