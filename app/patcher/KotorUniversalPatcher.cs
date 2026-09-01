using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace KotorUniversalUI
{
    internal enum ExecutableState
    {
        Missing,
        SupportedClean,
        Gold,
        Unsupported,
        Error
    }

    internal sealed class PatchChunk
    {
        internal long Offset;
        internal byte[] Data;
    }

    internal sealed class GoldPatch
    {
        internal const string ResourceName = "KotorUniversalUI.goldpatch";
        internal const string SourceHash = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886";
        internal const string TargetHash = "145F46FE85AF5934D6EE55C3D6BD5E54354762B5AFF3078C3875BC054EDE9C90";
        internal const long SourceLength = 4042752;
        internal const long TargetLength = 4071424;
        internal const string PatchVersion = "2.5.0-stack-label";

        private readonly List<PatchChunk> chunks;

        private GoldPatch(List<PatchChunk> chunksFromResource)
        {
            chunks = chunksFromResource;
        }

        internal static GoldPatch Load()
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName);
            if (stream == null)
                throw new InvalidDataException("Embedded gold patch resource is missing.");

            using (stream)
            using (BinaryReader reader = new BinaryReader(stream, Encoding.ASCII))
            {
                string magic = Encoding.ASCII.GetString(reader.ReadBytes(9));
                if (magic != "KUIPATCH1")
                    throw new InvalidDataException("Embedded patch has an invalid signature.");

                string sourceHash = ToHex(reader.ReadBytes(32));
                string targetHash = ToHex(reader.ReadBytes(32));
                long sourceLength = reader.ReadInt64();
                long targetLength = reader.ReadInt64();
                int count = reader.ReadInt32();

                if (sourceHash != SourceHash || targetHash != TargetHash ||
                    sourceLength != SourceLength || targetLength != TargetLength)
                    throw new InvalidDataException("Embedded patch metadata does not match this patcher.");
                if (count < 1 || count > 100000)
                    throw new InvalidDataException("Embedded patch chunk count is invalid.");

                List<PatchChunk> loaded = new List<PatchChunk>(count);
                for (int index = 0; index < count; index++)
                {
                    long offset = reader.ReadInt64();
                    int length = reader.ReadInt32();
                    if (offset < 0 || length < 1 || offset + length > TargetLength)
                        throw new InvalidDataException("Embedded patch contains an invalid byte range.");
                    byte[] data = reader.ReadBytes(length);
                    if (data.Length != length)
                        throw new EndOfStreamException("Embedded patch ended unexpectedly.");
                    loaded.Add(new PatchChunk { Offset = offset, Data = data });
                }

                if (stream.Position != stream.Length)
                    throw new InvalidDataException("Embedded patch contains unexpected trailing data.");
                return new GoldPatch(loaded);
            }
        }

        internal byte[] Apply(byte[] source, ResolutionChoice resolution)
        {
            if (source.LongLength != SourceLength || HashBytes(source) != SourceHash)
                throw new InvalidDataException("The selected file is not the supported unpatched swkotor.exe.");
            if (resolution == null)
                throw new ArgumentNullException("resolution");

            byte[] target = new byte[TargetLength];
            Buffer.BlockCopy(source, 0, target, 0, source.Length);
            foreach (PatchChunk chunk in chunks)
                Buffer.BlockCopy(chunk.Data, 0, target, checked((int)chunk.Offset), chunk.Data.Length);

            if (HashBytes(target) != TargetHash)
                throw new InvalidDataException("The game update could not be verified.");
            ResolutionPatch.Apply(target, resolution);
            return target;
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
        private readonly string displayName;

        internal ResolutionChoice(string category, int width, int height, int canvasWidth, int canvasHeight,
            int overlayWidth, int centeringWidth, int centeringHeight)
        {
            Category = category;
            Width = width;
            Height = height;
            CanvasWidth = canvasWidth;
            CanvasHeight = canvasHeight;
            OverlayWidth = overlayWidth;
            CenteringWidth = centeringWidth;
            CenteringHeight = centeringHeight;
            displayName = category + "   ·   " + width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture);
        }

        internal string Key
        {
            get
            {
                return Width.ToString(CultureInfo.InvariantCulture) + "x" +
                    Height.ToString(CultureInfo.InvariantCulture);
            }
        }

        public override string ToString()
        {
            return displayName;
        }
    }

    internal static class ResolutionCatalog
    {
        private const string ResourceName = "KotorUniversalUI.resolutions";

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
            if (choices.Count != 48)
                throw new InvalidDataException("The bundled resolution catalog is incomplete.");
            return choices;
        }

        internal static ResolutionChoice Find(int width, int height)
        {
            foreach (ResolutionChoice choice in Load())
            {
                if (choice.Width == width && choice.Height == height)
                    return choice;
            }
            throw new ArgumentOutOfRangeException("resolution", "The selected resolution is not supported.");
        }
    }

    internal static class ResolutionPatch
    {
        private static readonly long[] WidthOffsets = { 0x0000AA65, 0x001F0C65 };
        private static readonly long[] HeightOffsets = { 0x0000AA85, 0x001F0C6F };

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
        private static readonly int[][] RowSizeGroups =
        {
            new[] { 56, 56, 0x002B527F, 0x002B4FA9, 0x002B55E3 },   // inventory
            new[] { 42, 42, 0x002AB8EF, 0x002ACB20 },               // abilities: skills tab
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

        private static void ReplaceSingle(byte[] data, long offset, float expected, float replacement, string label)
        {
            if (offset < 0 || offset + 4 > data.LongLength)
                throw new InvalidDataException("The " + label + " patch address is outside the executable.");
            int index = checked((int)offset);
            float actual = BitConverter.ToSingle(data, index);
            if (actual != expected)
                throw new InvalidDataException("The " + label + " patch did not match the verified gold build.");
            byte[] value = BitConverter.GetBytes(replacement);
            Buffer.BlockCopy(value, 0, data, index, value.Length);
        }

        private static void ReplaceInt32(byte[] data, long offset, int expected, int replacement, string label)
        {
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
            return Path.Combine(directory, "swkotor.ini");
        }

        internal static string BackupPath(string executablePath)
        {
            return PathForExecutable(executablePath) + ".kotor-ui-backup";
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
            }
            else
            {
                for (int index = 0; index <= sectionStart; index++)
                    output.Add(lines[index]);
                output.Add("Height=" + height.ToString(CultureInfo.InvariantCulture));
                output.Add("Width=" + width.ToString(CultureInfo.InvariantCulture));
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
            return String.Equals(key, "Width", StringComparison.OrdinalIgnoreCase) ||
                String.Equals(key, "Height", StringComparison.OrdinalIgnoreCase);
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
                    File.Replace(temporaryPath, path, null, true);
                else
                    File.Move(temporaryPath, path);
            }
            finally
            {
                if (File.Exists(temporaryPath))
                    File.Delete(temporaryPath);
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

    internal sealed class OverrideEditState
    {
        internal bool CreatedManifest;
        internal string ExecutablePath;
    }

    internal static class OverrideOperations
    {
        private const string CommonResourceName = "KotorUniversalUI.override.common";
        private const string GuiResourcePrefix = "KotorUniversalUI.override.gui.";
        private const string ManifestHeader = "KUIOVERRIDE1";

        internal static string OverridePath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "Override");
        }

        private static string BackupRoot(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "KOTOR_UI_Override_Backup");
        }

        private static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), "KOTOR_UI_Override_Backup.manifest");
        }

        internal static OverrideEditState Install(string executablePath, ResolutionChoice resolution,
            Action<string> report)
        {
            return Install(executablePath, resolution, report, null);
        }

        internal static OverrideEditState Install(string executablePath, ResolutionChoice resolution,
            Action<string> report, Action<int, string> progress)
        {
            if (resolution == null)
                throw new ArgumentNullException("resolution");
            executablePath = Path.GetFullPath(executablePath);
            string overrideRoot = OverridePath(executablePath);
            string backupRoot = BackupRoot(executablePath);
            string manifestPath = ManifestPath(executablePath);
            bool existingInstallation = File.Exists(manifestPath);
            List<OverrideRecord> records = existingInstallation ? ReadManifest(manifestPath) : new List<OverrideRecord>();
            Dictionary<string, OverrideRecord> known = new Dictionary<string, OverrideRecord>(StringComparer.OrdinalIgnoreCase);
            foreach (OverrideRecord record in records)
                known.Add(record.RelativePath, record);

            if (!existingInstallation && Directory.Exists(backupRoot))
                throw new IOException("An old interface backup folder already exists. Move it aside before patching:\r\n" + backupRoot);

            Directory.CreateDirectory(overrideRoot);
            if (!existingInstallation)
                Directory.CreateDirectory(backupRoot);

            List<OverrideRecord> processed = new List<OverrideRecord>();
            HashSet<string> processedPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            string[] resources =
            {
                CommonResourceName,
                GuiResourcePrefix + resolution.Key
            };
            // Feat/power icons are built here from the game's own texture pack
            // rather than embedded: 200 icons x 48 resolutions would add ~57 MB of
            // pure duplication, and the source art is already on disk. Null when
            // the pack is missing or the resolution needs no enlargement, in which
            // case the icons simply stay vanilla-sized.
            HashSet<string> shipped = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string resourceName in resources)
            {
                using (Stream listing = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
                {
                    if (listing == null)
                        throw new InvalidDataException("The matching interface files are missing from this patcher.");
                    using (ZipArchive listingArchive = new ZipArchive(listing, ZipArchiveMode.Read, false))
                        foreach (ZipArchiveEntry listed in listingArchive.Entries)
                            if (!String.IsNullOrEmpty(listed.Name))
                                shipped.Add(NormalizeRelativePath(listed.FullName));
                }
            }
            MemoryStream generatedIcons = AbilityIconGenerator.TryBuild(
                executablePath, ResolutionPatch.ScaleForHeight(resolution.Height), shipped);

            try
            {
                int archiveCount = resources.Length + (generatedIcons != null ? 1 : 0);
                for (int resourceIndex = 0; resourceIndex < archiveCount; resourceIndex++)
                {
                    Stream resource;
                    if (resourceIndex < resources.Length)
                    {
                        resource = Assembly.GetExecutingAssembly().GetManifestResourceStream(resources[resourceIndex]);
                        if (resource == null)
                            throw new InvalidDataException("The matching interface files are missing from this patcher.");
                    }
                    else
                    {
                        resource = generatedIcons;
                    }
                    using (resource)
                    using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read, false))
                    {
                        long totalBytes = 0;
                        foreach (ZipArchiveEntry archiveEntry in archive.Entries)
                        {
                            if (!String.IsNullOrEmpty(archiveEntry.Name))
                                totalBytes += archiveEntry.Length;
                        }
                        long completedBytes = 0;
                        SafeProgress(progress, resourceIndex == 0 ? 18 : 88,
                            resourceIndex == 0 ? "Installing interface artwork…" : "Installing resolution layout…");

                        foreach (ZipArchiveEntry entry in archive.Entries)
                        {
                            if (String.IsNullOrEmpty(entry.Name))
                                continue;
                            string relative = NormalizeRelativePath(entry.FullName);
                            string target = SafeDestination(overrideRoot, relative);
                            string targetDirectory = Path.GetDirectoryName(target);
                            Directory.CreateDirectory(targetDirectory);

                            OverrideRecord record;
                            if (existingInstallation)
                            {
                                if (!known.TryGetValue(relative, out record))
                                    throw new InvalidDataException("The installed interface belongs to a different resolution. Restore it before selecting another resolution.");
                            }
                            else if (known.TryGetValue(relative, out record))
                            {
                                // Already installed by an earlier archive in this
                                // same run. Keep the original record -- its
                                // HadOriginal/OriginalHash describe the user's file,
                                // and a second record would make the backup folder
                                // hold the patcher's own file and stop restore.
                                record.InstalledHash = String.Empty;
                            }
                            else
                            {
                                record = new OverrideRecord();
                                record.RelativePath = relative;
                                record.HadOriginal = File.Exists(target);
                                record.OriginalHash = String.Empty;
                                if (record.HadOriginal)
                                {
                                    string backup = SafeDestination(backupRoot, relative);
                                    Directory.CreateDirectory(Path.GetDirectoryName(backup));
                                    File.Copy(target, backup, false);
                                    record.OriginalHash = GoldPatch.HashFile(backup);
                                    if (record.OriginalHash != GoldPatch.HashFile(target))
                                        throw new IOException("An interface file could not be backed up safely: " + relative);
                                }
                                records.Add(record);
                                known.Add(relative, record);
                            }

                            string temporary = target + ".kotor-ui-new-" + Guid.NewGuid().ToString("N") + ".tmp";
                            try
                            {
                                using (Stream input = entry.Open())
                                using (FileStream output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                                {
                                    input.CopyTo(output);
                                    output.Flush(true);
                                }
                                string installedHash = GoldPatch.HashFile(temporary);
                                if (String.IsNullOrEmpty(record.InstalledHash))
                                    record.InstalledHash = installedHash;
                                else if (record.InstalledHash != installedHash)
                                    throw new InvalidDataException("The installed interface belongs to a different resolution. Restore it before selecting another resolution.");

                                if (processedPaths.Add(relative))
                                    processed.Add(record);
                                if (File.Exists(target))
                                    File.Replace(temporary, target, null, true);
                                else
                                    File.Move(temporary, target);
                                if (GoldPatch.HashFile(target) != record.InstalledHash)
                                    throw new IOException("An interface file could not be installed safely: " + relative);

                                completedBytes += entry.Length;
                                int rangeStart = resourceIndex == 0 ? 18 : 88;
                                int rangeLength = resourceIndex == 0 ? 70 : 6;
                                int percent = rangeStart + (int)Math.Min((long)rangeLength,
                                    completedBytes * rangeLength / Math.Max(1L, totalBytes));
                                SafeProgress(progress, percent,
                                    resourceIndex == 0 ? "Installing interface artwork…" : "Installing resolution layout…");
                            }
                            finally
                            {
                                if (File.Exists(temporary))
                                    File.Delete(temporary);
                            }
                        }
                    }
                }

                if (existingInstallation && processed.Count != records.Count)
                    throw new InvalidDataException("The installed interface belongs to a different resolution. Restore it before selecting another resolution.");
                if (!existingInstallation)
                    WriteManifest(manifestPath, records);
                SafeProgress(progress, 95, "Finishing interface setup…");
                SafeReport(report, "Installed " + records.Count.ToString(CultureInfo.InvariantCulture) +
                    " interface files for " + resolution.Width.ToString(CultureInfo.InvariantCulture) + " × " +
                    resolution.Height.ToString(CultureInfo.InvariantCulture) + ".");
                return new OverrideEditState { CreatedManifest = !existingInstallation, ExecutablePath = executablePath };
            }
            catch
            {
                if (!existingInstallation)
                {
                    RollbackRecords(overrideRoot, backupRoot, processed);
                    if (File.Exists(manifestPath))
                        File.Delete(manifestPath);
                    if (Directory.Exists(backupRoot))
                        Directory.Delete(backupRoot, true);
                }
                throw;
            }
        }

        internal static void Rollback(OverrideEditState state)
        {
            if (state != null && state.CreatedManifest)
            {
                try { Restore(state.ExecutablePath, null); }
                catch { }
            }
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

        private static void RollbackRecords(string overrideRoot, string backupRoot, List<OverrideRecord> records)
        {
            for (int index = records.Count - 1; index >= 0; index--)
            {
                OverrideRecord record = records[index];
                string target = SafeDestination(overrideRoot, record.RelativePath);
                if (record.HadOriginal)
                {
                    string backup = SafeDestination(backupRoot, record.RelativePath);
                    if (File.Exists(backup))
                        File.Copy(backup, target, true);
                }
                else if (File.Exists(target))
                {
                    File.Delete(target);
                }
            }
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
            string destination = Path.GetFullPath(Path.Combine(fullRoot, relative));
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

    internal static class PatchOperations
    {
        internal static string BackupPath(string targetPath)
        {
            return targetPath + ".kotor-ui-backup";
        }

        internal static string LogPath(string targetPath)
        {
            string directory = Path.GetDirectoryName(Path.GetFullPath(targetPath));
            return Path.Combine(directory, "KOTOR_UI_Gold_Patcher.log");
        }

        internal static string ManifestPath(string targetPath)
        {
            return targetPath + ".kotor-ui-patch.json";
        }

        internal static string Describe(string targetPath)
        {
            if (!File.Exists(targetPath))
                return "File not found";

            try
            {
                FileInfo info = new FileInfo(targetPath);
                string hash = GoldPatch.HashFile(targetPath);
                if (info.Length == GoldPatch.SourceLength && hash == GoldPatch.SourceHash)
                    return "Supported clean build — ready to patch";
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
            if (String.IsNullOrWhiteSpace(targetPath) || !File.Exists(targetPath))
                return ExecutableState.Missing;
            try
            {
                FileInfo info = new FileInfo(targetPath);
                string hash = GoldPatch.HashFile(targetPath);
                if (info.Length == GoldPatch.SourceLength && hash == GoldPatch.SourceHash)
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
            try
            {
                if (Inspect(targetPath) != ExecutableState.Gold)
                    return false;
                string executableBackup = BackupPath(targetPath);
                return File.Exists(executableBackup) &&
                    GoldPatch.HashFile(executableBackup) == GoldPatch.SourceHash &&
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
            SafeProgress(progress, 0, "Preparing game files…");
            targetPath = Path.GetFullPath(targetPath);
            RequireExistingFile(targetPath);
            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);

            string currentHash = GoldPatch.HashFile(targetPath);
            SafeProgress(progress, 5, "Checking game files…");
            if (Inspect(targetPath) == ExecutableState.Gold)
            {
                int installedWidth;
                int installedHeight;
                if (TryReadInstalledResolution(targetPath, out installedWidth, out installedHeight) &&
                    (installedWidth != width || installedHeight != height))
                    throw new InvalidOperationException("Restore the current interface first, then patch the new resolution.");
                IniEditState existingIniState = null;
                OverrideEditState existingOverrideState = null;
                try
                {
                    SafeProgress(progress, 12, "Updating display settings…");
                    existingIniState = IniOperations.Configure(targetPath, width, height, report);
                    existingOverrideState = OverrideOperations.Install(targetPath, resolution, report, progress);
                    SafeProgress(progress, 98, "Saving patch information…");
                    WriteManifest(targetPath, BackupPath(targetPath), false, width, height, currentHash);
                    SafeProgress(progress, 100, "Patch complete");
                    SafeReport(report, "KOTOR is ready to play at " +
                        width.ToString(CultureInfo.InvariantCulture) + " × " +
                        height.ToString(CultureInfo.InvariantCulture) + ".");
                }
                catch
                {
                    OverrideOperations.Rollback(existingOverrideState);
                    IniOperations.Rollback(existingIniState);
                    throw;
                }
                return;
            }
            if (currentHash != GoldPatch.SourceHash || new FileInfo(targetPath).Length != GoldPatch.SourceLength)
                throw new InvalidDataException("This swkotor.exe is not supported. No changes were made.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before patching.",
                    IniOperations.PathForExecutable(targetPath));

            string backupPath = BackupPath(targetPath);
            if (File.Exists(backupPath))
            {
                if (GoldPatch.HashFile(backupPath) != GoldPatch.SourceHash)
                    throw new InvalidDataException("The existing backup is not the supported clean build. Move it aside before patching:\r\n" + backupPath);
            }
            else
            {
                SafeProgress(progress, 7, "Creating a safety backup…");
                File.Copy(targetPath, backupPath, false);
                if (GoldPatch.HashFile(backupPath) != GoldPatch.SourceHash)
                    throw new IOException("Backup verification failed. No patch was applied.");
                SafeReport(report, "Backup created: " + backupPath);
            }

            string temporaryPath = targetPath + ".kotor-ui-new-" + Guid.NewGuid().ToString("N") + ".tmp";
            bool installed = false;
            IniEditState iniState = null;
            OverrideEditState overrideState = null;
            try
            {
                SafeProgress(progress, 10, "Updating the game executable…");
                GoldPatch patch = GoldPatch.Load();
                byte[] source = File.ReadAllBytes(targetPath);
                byte[] target = patch.Apply(source, resolution);
                string targetHash = GoldPatch.HashBytes(target);
                WriteVerifiedFile(temporaryPath, target, targetHash);
                File.Replace(temporaryPath, targetPath, null, true);
                installed = true;

                if (GoldPatch.HashFile(targetPath) != targetHash)
                    throw new IOException("Post-install verification failed.");

                SafeProgress(progress, 15, "Updating display settings…");
                iniState = IniOperations.Configure(targetPath, width, height, report);
                overrideState = OverrideOperations.Install(targetPath, resolution, report, progress);
                SafeProgress(progress, 98, "Saving patch information…");
                WriteManifest(targetPath, backupPath, false, width, height, targetHash);
                SafeProgress(progress, 100, "Patch complete");
                SafeReport(report, "KOTOR is ready to play at " +
                    width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture) + ".");
            }
            catch
            {
                OverrideOperations.Rollback(overrideState);
                try { IniOperations.Rollback(iniState); }
                catch { }
                if (installed && File.Exists(backupPath))
                {
                    File.Copy(backupPath, targetPath, true);
                    if (GoldPatch.HashFile(targetPath) != GoldPatch.SourceHash)
                        throw new IOException("Patch failed and automatic rollback could not be completed. Use the backup at: " + backupPath);
                }
                throw;
            }
            finally
            {
                if (File.Exists(temporaryPath))
                    File.Delete(temporaryPath);
            }
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

            GoldPatch patch = GoldPatch.Load();
            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);
            byte[] target = patch.Apply(File.ReadAllBytes(sourcePath), resolution);
            WriteVerifiedFile(outputPath, target, GoldPatch.HashBytes(target));
        }

        internal static void Restore(string targetPath, Action<string> report)
        {
            Restore(targetPath, report, null);
        }

        internal static void Restore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            SafeProgress(progress, 0, "Preparing to restore…");
            targetPath = Path.GetFullPath(targetPath);
            RequireExistingFile(targetPath);
            string currentHash = GoldPatch.HashFile(targetPath);
            if (currentHash == GoldPatch.SourceHash)
            {
                OverrideOperations.Restore(targetPath, report, progress);
                SafeProgress(progress, 92, "Restoring display settings…");
                IniOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving restore information…");
                WriteManifest(targetPath, BackupPath(targetPath), true, 0, 0, GoldPatch.SourceHash);
                SafeProgress(progress, 100, "Restore complete");
                SafeReport(report, "The original game files and settings have been restored.");
                return;
            }
            if (Inspect(targetPath) != ExecutableState.Gold)
                throw new InvalidDataException("The current executable was not created by this patcher. Restore was blocked to protect it.");

            string backupPath = BackupPath(targetPath);
            RequireExistingFile(backupPath);
            if (GoldPatch.HashFile(backupPath) != GoldPatch.SourceHash)
                throw new InvalidDataException("Backup verification failed. Restore was blocked.");

            string temporaryPath = targetPath + ".kotor-ui-restore-" + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                SafeProgress(progress, 5, "Checking the original game backup…");
                File.Copy(backupPath, temporaryPath, false);
                if (GoldPatch.HashFile(temporaryPath) != GoldPatch.SourceHash)
                    throw new IOException("Temporary restore verification failed.");
                OverrideOperations.Restore(targetPath, report, progress);
                SafeProgress(progress, 90, "Restoring the game executable…");
                File.Replace(temporaryPath, targetPath, null, true);
                if (GoldPatch.HashFile(targetPath) != GoldPatch.SourceHash)
                    throw new IOException("Post-restore verification failed.");
                SafeProgress(progress, 94, "Restoring display settings…");
                IniOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving restore information…");
                WriteManifest(targetPath, backupPath, true, 0, 0, GoldPatch.SourceHash);
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
            File.AppendAllText(LogPath(targetPath), line, new UTF8Encoding(false));
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
                "  \"sourceSha256\": \"" + GoldPatch.SourceHash + "\",\r\n" +
                "  \"patchedSha256\": \"" + executableHash + "\"\r\n" +
                "}\r\n";
            File.WriteAllText(ManifestPath(targetPath), json, new UTF8Encoding(false));
        }

        private static bool IsVerifiedPatchedInstall(string targetPath, string actualHash)
        {
            try
            {
                string manifestPath = ManifestPath(targetPath);
                if (!File.Exists(manifestPath) || new FileInfo(targetPath).Length != GoldPatch.TargetLength)
                    return false;
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

        private static bool TryReadInstalledResolution(string targetPath, out int width, out int height)
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

    internal static class UiTheme
    {
        internal static readonly Color Window = Color.FromArgb(11, 16, 24);
        internal static readonly Color Panel = Color.FromArgb(20, 29, 40);
        internal static readonly Color PanelDeep = Color.FromArgb(7, 14, 23);
        internal static readonly Color PanelHover = Color.FromArgb(28, 49, 63);
        internal static readonly Color Border = Color.FromArgb(34, 103, 132);
        internal static readonly Color Accent = Color.FromArgb(42, 198, 239);
        internal static readonly Color AccentStrong = Color.FromArgb(0, 166, 214);
        internal static readonly Color AccentDark = Color.FromArgb(0, 83, 116);
        internal static readonly Color Gold = Color.FromArgb(226, 195, 92);
        internal static readonly Color Text = Color.FromArgb(236, 243, 248);
        internal static readonly Color TextMuted = Color.FromArgb(177, 195, 208);
        internal static readonly Color Success = Color.FromArgb(126, 224, 171);
        internal static readonly Color Warning = Color.FromArgb(255, 207, 112);
        internal static readonly Color Error = Color.FromArgb(255, 142, 142);
        internal static readonly Color Disabled = Color.FromArgb(47, 56, 67);
        internal static readonly Color DisabledText = Color.FromArgb(139, 151, 164);

        // The dark-glass palette the new shell is drawn with.
        internal static readonly Color GlowTop = Color.FromArgb(16, 26, 40);
        internal static readonly Color Card = Color.FromArgb(17, 24, 33);
        internal static readonly Color CardHover = Color.FromArgb(24, 34, 46);
        internal static readonly Color CardEdge = Color.FromArgb(35, 48, 63);
        internal static readonly Color Hairline = Color.FromArgb(28, 39, 52);
        internal static readonly Color Badge = Color.FromArgb(25, 35, 47);
        internal static readonly Color BadgeEdge = Color.FromArgb(38, 54, 71);
        internal static readonly Color Field = Color.FromArgb(13, 20, 28);
        internal static readonly Color AccentLit = Color.FromArgb(96, 178, 255);
        internal static readonly Color TextFaint = Color.FromArgb(122, 138, 154);

        internal enum Glyph { Folder, Shield, Monitor, Tools }

        internal static GraphicsPath RoundedRect(Rectangle r, int radius)
        {
            int d = Math.Max(1, radius * 2);
            GraphicsPath path = new GraphicsPath();
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        /// <summary>Step icons, drawn rather than shipped, so the patcher stays a single file.</summary>
        internal static void DrawGlyph(Graphics g, Glyph glyph, Rectangle circle, Color color)
        {
            float s = circle.Width / 46F;
            float cx = circle.X + circle.Width / 2F;
            float cy = circle.Y + circle.Height / 2F;
            using (Pen pen = new Pen(color, 1.7F * s))
            {
                pen.StartCap = LineCap.Round;
                pen.EndCap = LineCap.Round;
                pen.LineJoin = LineJoin.Round;
                if (glyph == Glyph.Folder)
                {
                    g.DrawLines(pen, new PointF[] {
                        new PointF(cx - 9 * s, cy + 6 * s), new PointF(cx - 9 * s, cy - 6 * s),
                        new PointF(cx - 3 * s, cy - 6 * s), new PointF(cx - 1 * s, cy - 3.5F * s),
                        new PointF(cx + 9 * s, cy - 3.5F * s), new PointF(cx + 9 * s, cy + 6 * s) });
                    g.DrawLine(pen, cx - 9 * s, cy + 6 * s, cx + 9 * s, cy + 6 * s);
                }
                else if (glyph == Glyph.Shield)
                {
                    g.DrawLines(pen, new PointF[] {
                        new PointF(cx, cy - 8 * s), new PointF(cx + 7 * s, cy - 5 * s),
                        new PointF(cx + 7 * s, cy + 1 * s), new PointF(cx, cy + 8 * s),
                        new PointF(cx - 7 * s, cy + 1 * s), new PointF(cx - 7 * s, cy - 5 * s) });
                    g.DrawLines(pen, new PointF[] {
                        new PointF(cx - 3.2F * s, cy), new PointF(cx - 0.8F * s, cy + 2.6F * s),
                        new PointF(cx + 3.6F * s, cy - 2.6F * s) });
                }
                else if (glyph == Glyph.Monitor)
                {
                    g.DrawRectangle(pen, cx - 9 * s, cy - 7 * s, 18 * s, 12 * s);
                    g.DrawLine(pen, cx - 4 * s, cy + 8 * s, cx + 4 * s, cy + 8 * s);
                    g.DrawLine(pen, cx, cy + 5 * s, cx, cy + 8 * s);
                }
                else
                {
                    g.DrawLine(pen, cx - 7 * s, cy + 7 * s, cx + 2 * s, cy - 2 * s);
                    g.DrawLines(pen, new PointF[] {
                        new PointF(cx + 1 * s, cy - 3 * s), new PointF(cx + 4 * s, cy - 7 * s),
                        new PointF(cx + 8 * s, cy - 6 * s), new PointF(cx + 8 * s, cy - 2 * s),
                        new PointF(cx + 4 * s, cy - 1 * s), new PointF(cx + 1 * s, cy - 3 * s) });
                }
            }
        }

        internal static Font DisplayFont(float size, FontStyle style)
        {
            try { return new Font("Bahnschrift SemiCondensed", size, style); }
            catch { return new Font("Segoe UI Semibold", size, style); }
        }

        internal static void StyleButton(Button button, bool primary)
        {
            button.FlatStyle = FlatStyle.Flat;
            button.FlatAppearance.BorderSize = 1;
            button.FlatAppearance.BorderColor = primary ? Accent : Border;
            button.FlatAppearance.MouseOverBackColor = primary ? Color.FromArgb(54, 211, 247) : PanelHover;
            button.FlatAppearance.MouseDownBackColor = primary ? Color.FromArgb(24, 179, 218) : AccentDark;
            button.BackColor = primary ? AccentStrong : Panel;
            button.ForeColor = primary ? PanelDeep : Text;
            button.Font = DisplayFont(9.2F, FontStyle.Bold);
            button.Cursor = Cursors.Hand;
        }
    }

    internal sealed class KotorProgressBar : Control
    {
        private int minimum;
        private int maximum = 100;
        private int currentValue;

        internal KotorProgressBar()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
            TabStop = false;
        }

        internal int Minimum
        {
            get { return minimum; }
            set { minimum = value; Value = currentValue; }
        }

        internal int Maximum
        {
            get { return maximum; }
            set { maximum = Math.Max(minimum + 1, value); Value = currentValue; }
        }

        internal int Value
        {
            get { return currentValue; }
            set
            {
                currentValue = Math.Max(minimum, Math.Min(maximum, value));
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Rectangle track = ClientRectangle;
            if (track.Width <= 1 || track.Height <= 1)
                return;
            track.Width -= 1;
            track.Height -= 1;

            using (SolidBrush background = new SolidBrush(UiTheme.PanelDeep))
                e.Graphics.FillRectangle(background, track);
            using (Pen border = new Pen(UiTheme.Border))
                e.Graphics.DrawRectangle(border, track);

            double fraction = (double)(currentValue - minimum) / (maximum - minimum);
            int fillWidth = (int)Math.Round((track.Width - 2) * fraction);
            if (fillWidth <= 0)
                return;

            Rectangle fill = new Rectangle(track.Left + 1, track.Top + 1,
                fillWidth, Math.Max(1, track.Height - 1));
            using (SolidBrush energy = new SolidBrush(UiTheme.AccentStrong))
                e.Graphics.FillRectangle(energy, fill);

            if (fill.Width >= 4)
            {
                Rectangle tip = new Rectangle(fill.Right - 2, fill.Top, 2, fill.Height);
                using (SolidBrush highlight = new SolidBrush(UiTheme.Gold))
                    e.Graphics.FillRectangle(highlight, tip);
            }
        }
    }

    internal sealed class CompatibilityDialog : Form
    {
        private const string DownloadUrl = "https://deadlystream.com/files/file/1320-kotor-editable-executable/";
        private readonly Func<ExecutableState> inspect;
        private readonly Func<string> selectedPath;
        private readonly Action<IWin32Window> browse;
        private readonly Label stateLabel;

        internal CompatibilityDialog(Func<ExecutableState> inspectFile, Func<string> getSelectedPath,
            Action<IWin32Window> browseForFile)
        {
            inspect = inspectFile;
            selectedPath = getSelectedPath;
            browse = browseForFile;

            Text = "Compatible executable required";
            ClientSize = new Size(620, 330);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent;
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 9F);
            BackColor = UiTheme.Window;
            ForeColor = UiTheme.Text;

            Label title = new Label();
            title.Text = "Use the editable swkotor.exe";
            title.Font = UiTheme.DisplayFont(16F, FontStyle.Bold);
            title.ForeColor = UiTheme.Accent;
            title.SetBounds(26, 22, 568, 36);
            Controls.Add(title);

            Panel titleRule = new Panel();
            titleRule.BackColor = UiTheme.Border;
            titleRule.SetBounds(28, 60, 564, 1);
            Controls.Add(titleRule);

            Label body = new Label();
            body.Text = "KOTOR needs the editable swkotor.exe from Deadly Stream before the display update can be installed.\r\n\r\n" +
                "Download it, replace swkotor.exe in your KOTOR folder, then return here and choose CHECK AGAIN.";
            body.SetBounds(28, 70, 564, 94);
            Controls.Add(body);

            stateLabel = new Label();
            stateLabel.BackColor = UiTheme.Panel;
            stateLabel.ForeColor = UiTheme.Text;
            stateLabel.BorderStyle = BorderStyle.FixedSingle;
            stateLabel.Padding = new Padding(10, 8, 10, 8);
            stateLabel.SetBounds(28, 177, 564, 58);
            stateLabel.AutoEllipsis = true;
            Controls.Add(stateLabel);

            Button download = NewDialogButton("OPEN DEADLY STREAM PAGE", 28, 255, 218, 46, true);
            download.Click += delegate { OpenDownloadPage(this); };
            Controls.Add(download);

            Button browseButton = NewDialogButton("CHOOSE REPLACEMENT", 256, 255, 172, 46, false);
            browseButton.Click += delegate
            {
                browse(this);
                UpdateState();
            };
            Controls.Add(browseButton);

            Button check = NewDialogButton("CHECK AGAIN", 438, 255, 154, 46, false);
            check.Click += delegate
            {
                UpdateState();
                ExecutableState state = inspect();
                if (state == ExecutableState.SupportedClean || state == ExecutableState.Gold)
                {
                    DialogResult = DialogResult.OK;
                    Close();
                }
            };
            Controls.Add(check);

            UpdateState();
        }

        private void UpdateState()
        {
            ExecutableState state = inspect();
            if (state == ExecutableState.SupportedClean)
            {
                stateLabel.ForeColor = UiTheme.Success;
                stateLabel.Text = "Compatible editable executable detected.\r\n" + selectedPath();
            }
            else if (state == ExecutableState.Gold)
            {
                stateLabel.ForeColor = UiTheme.Success;
                stateLabel.Text = "This game is already patched.\r\n" + selectedPath();
            }
            else
            {
                stateLabel.ForeColor = UiTheme.Warning;
                stateLabel.Text = "Not ready yet. Replace or select swkotor.exe, then choose CHECK AGAIN.\r\n" +
                    selectedPath();
            }
        }

        private static Button NewDialogButton(string text, int x, int y, int width, int height, bool primary)
        {
            Button button = new Button();
            button.Text = text;
            button.SetBounds(x, y, width, height);
            UiTheme.StyleButton(button, primary);
            return button;
        }

        internal static void OpenDownloadPage(IWin32Window owner)
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = DownloadUrl;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(owner, ex.Message, "Unable to open download page",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    /// <summary>A rounded, faintly lit card. The whole UI sits on one of these.</summary>
    internal sealed class CardPanel : Panel
    {
        internal int Radius = 14;
        internal Color Fill = UiTheme.Card;
        internal Color Edge = UiTheme.CardEdge;

        internal CardPanel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = Color.Transparent;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (GraphicsPath path = UiTheme.RoundedRect(r, Radius))
            using (SolidBrush fill = new SolidBrush(Fill))
            using (Pen edge = new Pen(Edge))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(edge, path);
            }
        }
    }

    /// <summary>One numbered step: a lit glyph badge, a title, a subtitle, and room on
    /// the right for whatever that step needs (a button, a dropdown, a status word).</summary>
    internal sealed class StepRow : Panel
    {
        internal string Title = String.Empty;
        internal string Subtitle = String.Empty;
        internal UiTheme.Glyph Icon = UiTheme.Glyph.Folder;
        internal bool DrawSeparator = true;

        internal StepRow()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = Color.Transparent;
            Height = 96;
        }

        internal void SetSubtitle(string value)
        {
            if (Subtitle == value)
                return;
            Subtitle = value;
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

            if (DrawSeparator)
                using (Pen line = new Pen(UiTheme.Hairline))
                    g.DrawLine(line, 26, Height - 1, Width - 26, Height - 1);

            int badge = 46;
            Rectangle circle = new Rectangle(28, (Height - badge) / 2, badge, badge);
            using (SolidBrush disc = new SolidBrush(UiTheme.Badge))
                g.FillEllipse(disc, circle);
            using (Pen ring = new Pen(UiTheme.BadgeEdge))
                g.DrawEllipse(ring, circle);
            UiTheme.DrawGlyph(g, Icon, circle, UiTheme.Accent);

            using (SolidBrush text = new SolidBrush(UiTheme.Text))
            using (Font f = UiTheme.DisplayFont(13.5F, FontStyle.Bold))
                g.DrawString(Title, f, text, 92, Height / 2 - 24);
            using (SolidBrush text = new SolidBrush(UiTheme.TextMuted))
            using (Font f = new Font("Segoe UI", 9.5F))
                g.DrawString(Subtitle, f, text, 92, Height / 2 + 2);
        }
    }

    /// <summary>Flat pill button. `Primary` gets the lit gradient, everything else the
    /// quiet outline used for Restore.</summary>
    internal sealed class PillButton : Control
    {
        internal bool Primary;
        private bool hover;
        private bool down;

        internal PillButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;
            Cursor = Cursors.Hand;
            Height = 44;
        }

        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);

            using (GraphicsPath path = UiTheme.RoundedRect(r, 8))
            {
                if (!Enabled)
                {
                    using (SolidBrush fill = new SolidBrush(UiTheme.Disabled))
                        g.FillPath(fill, path);
                }
                else if (Primary)
                {
                    Color top = down ? UiTheme.AccentDark : (hover ? UiTheme.AccentLit : UiTheme.Accent);
                    Color bottom = down ? UiTheme.AccentDark : UiTheme.AccentStrong;
                    using (LinearGradientBrush fill = new LinearGradientBrush(
                               new Rectangle(0, 0, Math.Max(1, Width), Math.Max(1, Height)), top, bottom, 90F))
                        g.FillPath(fill, path);
                }
                else
                {
                    using (SolidBrush fill = new SolidBrush(hover ? UiTheme.CardHover : UiTheme.Card))
                        g.FillPath(fill, path);
                    using (Pen edge = new Pen(hover ? UiTheme.Accent : UiTheme.CardEdge))
                        g.DrawPath(edge, path);
                }
            }

            Color ink = !Enabled ? UiTheme.DisabledText : (Primary ? Color.White : UiTheme.Text);
            using (StringFormat sf = new StringFormat())
            using (SolidBrush brush = new SolidBrush(ink))
            using (Font f = UiTheme.DisplayFont(Primary ? 13F : 10.5F, FontStyle.Bold))
            {
                sf.Alignment = StringAlignment.Center;
                sf.LineAlignment = StringAlignment.Center;
                g.DrawString(Text, f, brush, new RectangleF(0, 0, Width, Height), sf);
            }
        }
    }

    /// <summary>A hairline progress track that only shows itself while something is running.</summary>
    internal sealed class ThinProgress : Control
    {
        private int percent;

        internal ThinProgress()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw |
                     ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;
            Height = 4;
        }

        internal int Percent
        {
            get { return percent; }
            set
            {
                int clamped = Math.Max(0, Math.Min(100, value));
                if (clamped == percent)
                    return;
                percent = clamped;
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (GraphicsPath track = UiTheme.RoundedRect(new Rectangle(0, 0, Width - 1, Height - 1), Height / 2))
            using (SolidBrush back = new SolidBrush(UiTheme.Badge))
                g.FillPath(back, track);
            int filled = (int)Math.Round(Width * percent / 100.0);
            if (filled <= 1)
                return;
            using (GraphicsPath bar = UiTheme.RoundedRect(new Rectangle(0, 0, filled - 1, Height - 1), Height / 2))
            using (LinearGradientBrush fill = new LinearGradientBrush(
                       new Rectangle(0, 0, Math.Max(1, filled), Height), UiTheme.Accent, UiTheme.AccentStrong, 0F))
                g.FillPath(fill, bar);
        }
    }

    /// <summary>ComboBox with the system's light border painted over, plus our own chevron.
    /// `FlatStyle.Flat` still draws a Windows border and drop button, so the only way to a
    /// dark field short of reimplementing selection is to repaint after WM_PAINT.</summary>
    internal sealed class DarkCombo : ComboBox
    {
        private const int WM_PAINT = 0x000F;

        internal DarkCombo()
        {
            DropDownStyle = ComboBoxStyle.DropDownList;
            FlatStyle = FlatStyle.Flat;
            DrawMode = DrawMode.OwnerDrawFixed;
            BackColor = UiTheme.Field;
            ForeColor = UiTheme.Text;
            ItemHeight = 26;
            IntegralHeight = false;
            DropDownHeight = 320;
        }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (m.Msg != WM_PAINT)
                return;
            using (Graphics g = Graphics.FromHwnd(Handle))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                int button = 30;
                using (SolidBrush fill = new SolidBrush(UiTheme.Field))
                    g.FillRectangle(fill, Width - button, 1, button - 1, Height - 2);
                using (Pen edge = new Pen(UiTheme.CardEdge))
                    g.DrawRectangle(edge, 0, 0, Width - 1, Height - 1);
                float cx = Width - button / 2F - 2;
                float cy = Height / 2F - 1;
                using (Pen chevron = new Pen(UiTheme.TextMuted, 1.6F))
                {
                    chevron.StartCap = LineCap.Round;
                    chevron.EndCap = LineCap.Round;
                    g.DrawLines(chevron, new PointF[] {
                        new PointF(cx - 4.5F, cy - 2F), new PointF(cx, cy + 2.5F), new PointF(cx + 4.5F, cy - 2F) });
                }
            }
        }
    }

    internal sealed class MainForm : Form
    {
        private delegate void UiOperation(Action<string> report, Action<int, string> progress);

        internal const string AppName = "KOTOR Modern Restoration Patch";
        internal const string ShortName = "KMRP";
        internal const string Version = "v1.0.0";
        // The header is measured from the brand artwork rather than fixed, so widening
        // the window scales the lockup and the card follows it down.
        // The lockup is sized against the card, not the window, so the two read as one
        // block: half the card's width, centred on it.
        private const double BrandCardFraction = 0.5;
        // The card is a fixed 3:2 rectangle rather than something that stretches to the
        // window's edges: on a wide window a full-width row leaves a desert between a
        // step's subtitle and its control. Its height is fully determined by the row
        // heights below, so the width follows from the ratio.
        private const double CardAspect = 2.25;   // 1.5 was the first pass; this is 50% wider
        private const int StepHeight = 96;
        // Where the wordmark's ink actually ends inside the brand image, as a fraction of
        // its width. The PNG carries transparent margin and glow beyond the last letter, so
        // the drawn width is not the visible width -- measured on the artwork: the R's right
        // edge sits at 0.9774.
        private const double WordmarkInkRight = 0.9774;
        private readonly int headerHeight;
        private readonly int brandWidth;
        private readonly int brandHeight;
        private const string CreatorUrl = "https://deadlystream.com/profile/68365-raymangt/";

        private readonly TextBox pathBox;              // data holder; the path is shown in step 1's subtitle
        private readonly DarkCombo resolutionBox;
        private readonly ThinProgress progressBar;
        private readonly PillButton patchButton;
        private readonly PillButton restoreButton;
        private readonly PillButton browseButton;
        private readonly StepRow stepFolder;
        private readonly StepRow stepVerify;
        private readonly StepRow stepResolution;
        private readonly StepRow stepApply;
        private readonly Label verifyState;
        private readonly Label applyState;
        private readonly Panel optionsHost;           // reserved: future checkboxes land here
        private readonly LinkLabel logLink;
        private Image brand;
        private bool startupPromptShown;
        private bool operationRunning;
        private string lastDetail = String.Empty;

        internal MainForm()
        {
            Text = ShortName + " – " + AppName;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            DoubleBuffered = true;
            Font = new Font("Segoe UI", 9F);
            BackColor = UiTheme.Window;
            ForeColor = UiTheme.Text;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch { }
            HandleCreated += delegate { UseDarkTitleBar(Handle); };
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream("KotorUniversalUI.brand"))
                    if (stream != null)
                        brand = Image.FromStream(stream);
            }
            catch { brand = null; }

            // Height is the sum of the fixed pieces: four steps, the gap above the primary
            // button, the button, the gap above Restore, Restore, and the bottom padding.
            int cardHeight = 4 * StepHeight + 22 + 58 + 24 + 40 + 26;
            int cardWidth = (int)Math.Round(cardHeight * CardAspect);

            brandWidth = (int)Math.Round(cardWidth * BrandCardFraction);
            brandHeight = brand == null ? 150
                : (int)Math.Round(brand.Height * (brandWidth / (double)brand.Width));
            headerHeight = 14 + brandHeight + 46;

            // The window's side margin is not a free choice: it is set equal to the gap
            // between the end of the wordmark and the card's edge, so the lockup, the card
            // and the window frame all breathe at the same rhythm. Both the card and the
            // lockup are centred, so that gap is cardWidth/2 minus how far the ink reaches
            // past the lockup's own centre.
            int gapInsideCard = (int)Math.Round(cardWidth / 2.0
                                                - (WordmarkInkRight - 0.5) * brandWidth);
            int clientWidth = cardWidth + 2 * gapInsideCard;
            ClientSize = new Size(clientWidth, 900);
            MinimumSize = new Size(clientWidth + 16, 700);
            MaximumSize = new Size(clientWidth + 16, Screen.PrimaryScreen.WorkingArea.Height);

            pathBox = new TextBox();
            pathBox.TextChanged += delegate { RefreshStatus(); };

            CardPanel card = new CardPanel();
            card.SetBounds((ClientSize.Width - cardWidth) / 2, headerHeight, cardWidth, cardHeight);
            card.Anchor = AnchorStyles.Top;
            Controls.Add(card);

            stepFolder = NewStep(card, 0, UiTheme.Glyph.Folder, "1. Select Game Folder",
                "Choose your Knights of the Old Republic folder.");
            browseButton = new PillButton();
            browseButton.Text = "Browse";
            browseButton.SetBounds(card.Width - 154, 26, 118, 42);
            browseButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            browseButton.Click += delegate { BrowseForExecutable(this); };
            stepFolder.Controls.Add(browseButton);

            stepVerify = NewStep(card, 1, UiTheme.Glyph.Shield, "2. Verify Executable",
                "Checking for the required executable.");
            verifyState = NewStateLabel(stepVerify, card.Width);

            stepResolution = NewStep(card, 2, UiTheme.Glyph.Monitor, "3. Choose Resolution",
                "Select the resolution you want to patch for.");
            resolutionBox = new DarkCombo();
            resolutionBox.Font = new Font("Segoe UI", 10.5F);
            resolutionBox.SetBounds(card.Width - 434, 30, 398, 34);
            resolutionBox.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            resolutionBox.DrawItem += ResolutionDrawItem;
            int preferredResolution = 0;
            List<ResolutionChoice> resolutions = ResolutionCatalog.Load();
            for (int index = 0; index < resolutions.Count; index++)
            {
                resolutionBox.Items.Add(resolutions[index]);
                if (resolutions[index].Width == 3440 && resolutions[index].Height == 1440)
                    preferredResolution = index;
            }
            if (resolutionBox.Items.Count > 0)
                resolutionBox.SelectedIndex = preferredResolution;
            resolutionBox.SelectedIndexChanged += delegate { RefreshStatus(); };
            stepResolution.Controls.Add(resolutionBox);

            stepApply = NewStep(card, 3, UiTheme.Glyph.Tools, "4. Apply Patch",
                "Patches will be applied to make KOTOR modern-ready.");
            stepApply.DrawSeparator = false;
            applyState = NewStateLabel(stepApply, card.Width);

            // Reserved for optional toggles (16:9 HUD safe zone on 21:9/32:9, and so on).
            // Empty and zero-height today; giving it a home now means adding one later is
            // a matter of dropping a checkbox in and growing the card, not a redesign.
            optionsHost = new Panel();
            optionsHost.SetBounds(0, 4 * 96, card.Width, 0);
            optionsHost.BackColor = Color.Transparent;
            optionsHost.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            card.Controls.Add(optionsHost);

            patchButton = new PillButton();
            patchButton.Primary = true;
            patchButton.Text = "Start Patching";
            patchButton.SetBounds(112, optionsHost.Bottom + 22, card.Width - 224, 58);
            patchButton.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            patchButton.Click += PatchClicked;
            card.Controls.Add(patchButton);

            progressBar = new ThinProgress();
            progressBar.SetBounds(112, patchButton.Bottom + 10, card.Width - 224, 4);
            progressBar.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            progressBar.Visible = false;
            card.Controls.Add(progressBar);

            restoreButton = new PillButton();
            restoreButton.Text = "Restore Original";
            restoreButton.SetBounds(112, patchButton.Bottom + 24, card.Width - 224, 40);
            restoreButton.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            restoreButton.Click += RestoreClicked;
            card.Controls.Add(restoreButton);

            card.Height = restoreButton.Bottom + 26;

            logLink = new LinkLabel();
            logLink.Text = Version + "   ·   Open Log";
            logLink.LinkArea = new LinkArea(Version.Length + 6, 8);
            logLink.Font = new Font("Segoe UI", 9F);
            logLink.ForeColor = UiTheme.TextFaint;
            logLink.LinkColor = UiTheme.Accent;
            logLink.ActiveLinkColor = Color.White;
            logLink.VisitedLinkColor = UiTheme.Accent;
            logLink.LinkBehavior = LinkBehavior.HoverUnderline;
            logLink.BackColor = Color.Transparent;
            logLink.SetBounds(card.Left + 8, card.Bottom + 20, 240, 22);
            logLink.Anchor = AnchorStyles.Top;
            logLink.LinkClicked += OpenLogClicked;
            Controls.Add(logLink);

            LinkLabel credit = new LinkLabel();
            credit.Text = "Created by RaymanGT";
            credit.Font = new Font("Segoe UI", 9F);
            credit.LinkColor = UiTheme.TextFaint;
            credit.ActiveLinkColor = UiTheme.Accent;
            credit.VisitedLinkColor = UiTheme.TextFaint;
            credit.LinkBehavior = LinkBehavior.HoverUnderline;
            credit.BackColor = Color.Transparent;
            credit.TextAlign = ContentAlignment.MiddleRight;
            credit.SetBounds(card.Right - 228, card.Bottom + 20, 220, 22);
            credit.Anchor = AnchorStyles.Top;
            credit.LinkClicked += delegate { OpenCreatorPage(); };
            Controls.Add(credit);

            ClientSize = new Size(ClientSize.Width, credit.Bottom + 24);

            pathBox.Text = FindDefaultExecutable();
            RefreshStatus();

            Activated += delegate { RefreshStatus(); };
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (!operationRunning)
                    return;
                e.Cancel = true;
                MessageBox.Show(this, "Please wait for the current operation to finish.", "Patcher is working",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
            Shown += delegate
            {
                if (!startupPromptShown)
                {
                    startupPromptShown = true;
                    BeginInvoke(new MethodInvoker(ShowCompatibilityPromptIfNeeded));
                }
            };
        }

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr window, int attribute, ref int value, int size);

        /// <summary>Ask the shell for a dark title bar. Attribute 20 on Windows 11 and later
        /// builds of 10, 19 on the first that supported it; both are ignored elsewhere.</summary>
        private static void UseDarkTitleBar(IntPtr handle)
        {
            int on = 1;
            try
            {
                if (DwmSetWindowAttribute(handle, 20, ref on, sizeof(int)) != 0)
                    DwmSetWindowAttribute(handle, 19, ref on, sizeof(int));
            }
            catch { }
        }

        private StepRow NewStep(CardPanel card, int index, UiTheme.Glyph icon, string title, string subtitle)
        {
            StepRow row = new StepRow();
            row.Icon = icon;
            row.Title = title;
            row.Subtitle = subtitle;
            row.SetBounds(0, index * 96, card.Width, 96);
            row.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            card.Controls.Add(row);
            return row;
        }

        private static Label NewStateLabel(StepRow row, int cardWidth)
        {
            Label label = new Label();
            label.Font = UiTheme.DisplayFont(11F, FontStyle.Bold);
            label.ForeColor = UiTheme.TextMuted;
            label.BackColor = Color.Transparent;
            label.TextAlign = ContentAlignment.MiddleRight;
            label.SetBounds(cardWidth - 330, 34, 294, 28);
            label.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            row.Controls.Add(label);
            return label;
        }

        private void ResolutionDrawItem(object sender, DrawItemEventArgs e)
        {
            if (e.Index < 0)
                return;
            bool selected = (e.State & DrawItemState.Selected) == DrawItemState.Selected;
            using (SolidBrush back = new SolidBrush(selected ? UiTheme.AccentDark : UiTheme.Field))
                e.Graphics.FillRectangle(back, e.Bounds);
            using (SolidBrush ink = new SolidBrush(UiTheme.Text))
            using (StringFormat sf = new StringFormat())
            {
                sf.LineAlignment = StringAlignment.Center;
                e.Graphics.DrawString(resolutionBox.Items[e.Index].ToString(), e.Font, ink,
                    new RectangleF(e.Bounds.X + 10, e.Bounds.Y, e.Bounds.Width - 12, e.Bounds.Height), sf);
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

            using (LinearGradientBrush sky = new LinearGradientBrush(
                       new Rectangle(0, 0, Math.Max(1, ClientSize.Width), headerHeight),
                       UiTheme.GlowTop, UiTheme.Window, 90F))
                g.FillRectangle(sky, 0, 0, ClientSize.Width, headerHeight);

            // The crest and the metallic wordmark are one baked lockup, so the crest's
            // fade lines up with the letters exactly as it was composed.
            int taglineTop = 30;
            if (brand != null)
            {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(brand, (ClientSize.Width - brandWidth) / 2, 14, brandWidth, brandHeight);
                taglineTop = 14 + brandHeight + 2;
            }

            using (StringFormat sf = new StringFormat())
            using (Font f = new Font("Segoe UI", 10.5F, FontStyle.Bold))
            using (SolidBrush ink = new SolidBrush(UiTheme.Accent))
            {
                sf.Alignment = StringAlignment.Center;
                sf.FormatFlags = StringFormatFlags.NoWrap;
                g.DrawString("M O D E R N .   R E S T O R E D .   S I M P L E .", f, ink,
                    new RectangleF(0, taglineTop, ClientSize.Width, 26), sf);
            }
        }

        private void OpenCreatorPage()
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = CreatorUrl;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open the creator's page",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private static string FindDefaultExecutable()
        {
            string besidePatcher = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "swkotor.exe");
            if (File.Exists(besidePatcher))
                return besidePatcher;
            string current = Path.Combine(Environment.CurrentDirectory, "swkotor.exe");
            return File.Exists(current) ? current : besidePatcher;
        }

        private void ShowCompatibilityPromptIfNeeded()
        {
            ExecutableState state = PatchOperations.Inspect(pathBox.Text.Trim());
            if (state == ExecutableState.SupportedClean || state == ExecutableState.Gold)
                return;

            using (CompatibilityDialog dialog = new CompatibilityDialog(
                delegate { return PatchOperations.Inspect(pathBox.Text.Trim()); },
                delegate { return pathBox.Text.Trim(); },
                BrowseForExecutable))
            {
                dialog.ShowDialog(this);
            }
            RefreshStatus();
        }

        private void BrowseForExecutable(IWin32Window owner)
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "Select swkotor.exe in your KOTOR folder";
                dialog.Filter = "KOTOR executable (swkotor.exe)|swkotor.exe|Executable files (*.exe)|*.exe|All files (*.*)|*.*";
                if (File.Exists(pathBox.Text))
                    dialog.InitialDirectory = Path.GetDirectoryName(Path.GetFullPath(pathBox.Text));
                if (dialog.ShowDialog(owner) == DialogResult.OK)
                    pathBox.Text = dialog.FileName;
            }
        }

        private void SetState(Label label, string text, Color color)
        {
            label.Text = text;
            label.ForeColor = color;
        }

        private void RefreshStatus()
        {
            if (patchButton == null || restoreButton == null || applyState == null)
                return;
            if (operationRunning)
                return;

            string target = pathBox.Text.Trim();
            ExecutableState state = PatchOperations.Inspect(target);
            bool iniExists = false;
            try { iniExists = File.Exists(IniOperations.PathForExecutable(target)); }
            catch { }

            string folder = null;
            try { folder = File.Exists(target) ? Path.GetDirectoryName(Path.GetFullPath(target)) : null; }
            catch { }
            stepFolder.SetSubtitle(String.IsNullOrEmpty(folder)
                ? "Choose your Knights of the Old Republic folder."
                : folder);

            bool executableReady = state == ExecutableState.SupportedClean || state == ExecutableState.Gold;
            patchButton.Enabled = executableReady && iniExists;
            restoreButton.Enabled = PatchOperations.CanRestore(target);

            if (state == ExecutableState.SupportedClean || state == ExecutableState.Gold)
                SetState(verifyState, "✓  Verified", UiTheme.Success);
            else if (state == ExecutableState.Missing)
                SetState(verifyState, "Not found", UiTheme.Warning);
            else if (state == ExecutableState.Unsupported)
                SetState(verifyState, "Not the editable exe", UiTheme.Warning);
            else
                SetState(verifyState, "Unable to verify", UiTheme.Error);

            if (state == ExecutableState.Gold)
            {
                SetState(applyState, "Patched", UiTheme.Success);
                lastDetail = iniExists
                    ? "The installed resolution is protected. To choose a different one, restore the original first."
                    : "The executable is patched, but swkotor.ini is missing beside it.";
            }
            else if (executableReady && iniExists)
            {
                SetState(applyState, "Ready to patch", UiTheme.Accent);
                lastDetail = IniOperations.Describe(target);
            }
            else if (executableReady)
            {
                SetState(applyState, "swkotor.ini required", UiTheme.Warning);
                lastDetail = "Launch the game once so it writes swkotor.ini beside the executable, then check again.";
            }
            else
            {
                SetState(applyState, "Not patched", UiTheme.TextMuted);
                lastDetail = PatchOperations.Describe(target);
            }
            stepApply.SetSubtitle(lastDetail);
        }

        private void PatchClicked(object sender, EventArgs e)
        {
            ResolutionChoice resolution = resolutionBox.SelectedItem as ResolutionChoice;
            if (resolution == null)
            {
                MessageBox.Show(this, "Select a target resolution.", "Resolution required",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            RunOperation("Patch", delegate(Action<string> report, Action<int, string> progress)
            {
                PatchOperations.ApplyInPlace(pathBox.Text.Trim(), resolution.Width, resolution.Height, report, progress);
            });
        }

        private void RestoreClicked(object sender, EventArgs e)
        {
            RunOperation("Restore", delegate(Action<string> report, Action<int, string> progress)
            {
                PatchOperations.Restore(pathBox.Text.Trim(), report, progress);
            });
        }

        private void RunOperation(string name, UiOperation operation)
        {
            if (operationRunning)
                return;

            string target = pathBox.Text.Trim();
            progressBar.Percent = 0;
            progressBar.Visible = true;
            operationRunning = true;
            SetBusyState(true);
            SetState(applyState, name == "Patch" ? "Patching…" : "Restoring…", UiTheme.Accent);
            stepApply.SetSubtitle(name == "Patch" ? "Preparing to patch…" : "Preparing to restore…");

            BackgroundWorker worker = new BackgroundWorker();
            worker.WorkerReportsProgress = true;
            worker.DoWork += delegate(object sender, DoWorkEventArgs e)
            {
                string result = null;
                operation(
                    delegate(string message)
                    {
                        result = message;
                        try { PatchOperations.AppendLog(target, name + ": " + message); }
                        catch { }
                    },
                    delegate(int percent, string message)
                    {
                        worker.ReportProgress(Math.Max(0, Math.Min(100, percent)), message);
                    });
                e.Result = result;
            };
            worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs e)
            {
                int percent = Math.Max(0, Math.Min(100, e.ProgressPercentage));
                progressBar.Percent = percent;
                string message = e.UserState as string;
                stepApply.SetSubtitle((String.IsNullOrWhiteSpace(message) ? "Working…" : message) +
                    "   " + percent.ToString(CultureInfo.InvariantCulture) + "%");
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
            {
                operationRunning = false;
                SetBusyState(false);

                if (e.Error != null)
                {
                    progressBar.Percent = 0;
                    progressBar.Visible = false;
                    RefreshStatus();
                    SetState(applyState, "Error", UiTheme.Error);
                    stepApply.SetSubtitle(name + " stopped — no incomplete changes were left behind.");
                    try { PatchOperations.AppendLog(target, name + " failed: " + e.Error); } catch { }
                    MessageBox.Show(this, e.Error.Message, name + " blocked", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                progressBar.Percent = 100;
                string result = e.Result as string;
                RefreshStatus();
                SetState(applyState, name == "Patch" ? "Patched successfully" : "Restored successfully", UiTheme.Success);
                stepApply.SetSubtitle(result ?? (name + " completed."));
                MessageBox.Show(this, result ?? (name + " completed."), name + " successful",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
            worker.RunWorkerAsync();
        }

        private void SetBusyState(bool busy)
        {
            resolutionBox.Enabled = !busy;
            browseButton.Enabled = !busy;
            patchButton.Enabled = !busy;
            restoreButton.Enabled = !busy;
            logLink.Enabled = !busy;
            UseWaitCursor = busy;
        }

        private void OpenLogClicked(object sender, LinkLabelLinkClickedEventArgs e)
        {
            try
            {
                string logPath = PatchOperations.LogPath(pathBox.Text.Trim());
                if (!File.Exists(logPath))
                    File.WriteAllText(logPath, AppName + " log\r\n", new UTF8Encoding(false));
                Process.Start(logPath);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open log", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 3 && args[0] == "--apply")
                {
                    PatchOperations.ApplyToNewFile(args[1], args[2], 3440, 1440);
                    return 0;
                }
                if (args.Length == 4 && args[0] == "--apply")
                {
                    int width;
                    int height;
                    ParseResolution(args[3], out width, out height);
                    PatchOperations.ApplyToNewFile(args[1], args[2], width, height);
                    return 0;
                }
                if (args.Length == 2 && args[0] == "--in-place")
                {
                    PatchOperations.ApplyInPlace(args[1], delegate { });
                    return 0;
                }
                if (args.Length == 3 && args[0] == "--in-place")
                {
                    int width;
                    int height;
                    ParseResolution(args[2], out width, out height);
                    PatchOperations.ApplyInPlace(args[1], width, height, delegate { });
                    return 0;
                }
                if (args.Length == 2 && args[0] == "--restore")
                {
                    PatchOperations.Restore(args[1], delegate { });
                    return 0;
                }
                if (args.Length != 0)
                    return 64;

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm());
                return 0;
            }
            catch (Exception ex)
            {
                // Log startup failures for the window too, not just the CLI -- a GUI that
                // exits with code 1 and no trace is impossible to diagnose.
                try
                {
                    File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
                        "KMRP.startup-error.log"), ex.ToString(), new UTF8Encoding(false));
                }
                catch { }
                if (args == null || args.Length == 0)
                {
                    try
                    {
                        MessageBox.Show(ex.ToString(), "KMRP could not start",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                    catch { }
                }
                return 1;
            }
        }

        private static void ParseResolution(string value, out int width, out int height)
        {
            width = 0;
            height = 0;
            Match match = Regex.Match(value ?? String.Empty, "^(\\d+)[xX](\\d+)$",
                RegexOptions.CultureInvariant);
            if (!match.Success ||
                !Int32.TryParse(match.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out width) ||
                !Int32.TryParse(match.Groups[2].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out height))
                throw new ArgumentException("Resolution must use WIDTHxHEIGHT, for example 3440x1440.");
            ResolutionCatalog.Find(width, height);
        }
    }
}
