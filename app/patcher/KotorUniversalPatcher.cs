using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
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

                // Each archive gets a slice of the 18-94 band proportional to its size.
                // The ranges used to be hardcoded as "18 to 88 for the first, 88 to 94 for
                // anything else", which was written when there were two archives. There are
                // three: the common artwork, the resolution layout, and the generated
                // ability icons. The second and third therefore shared one range, and the
                // bar visibly fell back from 94% to 88% when the icons began installing.
                long[] archiveBytes = new long[archiveCount];
                long totalArchiveBytes = 0;
                for (int sizingIndex = 0; sizingIndex < archiveCount; sizingIndex++)
                {
                    if (sizingIndex < resources.Length)
                    {
                        using (Stream sizing = Assembly.GetExecutingAssembly()
                            .GetManifestResourceStream(resources[sizingIndex]))
                        {
                            if (sizing == null)
                                continue;
                            using (ZipArchive sizingArchive =
                                new ZipArchive(sizing, ZipArchiveMode.Read, false))
                                foreach (ZipArchiveEntry sized in sizingArchive.Entries)
                                    if (!String.IsNullOrEmpty(sized.Name))
                                        archiveBytes[sizingIndex] += sized.Length;
                        }
                    }
                    else if (generatedIcons != null)
                    {
                        // Left open and rewound: this stream is installed from below.
                        generatedIcons.Position = 0;
                        using (ZipArchive sizingArchive =
                            new ZipArchive(generatedIcons, ZipArchiveMode.Read, true))
                            foreach (ZipArchiveEntry sized in sizingArchive.Entries)
                                if (!String.IsNullOrEmpty(sized.Name))
                                    archiveBytes[sizingIndex] += sized.Length;
                        generatedIcons.Position = 0;
                    }
                    totalArchiveBytes += archiveBytes[sizingIndex];
                }

                long bytesBeforeArchive = 0;
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
                        int rangeStart = (int)(18 + 76L * bytesBeforeArchive
                            / Math.Max(1L, totalArchiveBytes));
                        int rangeLength = (int)(76L * archiveBytes[resourceIndex]
                            / Math.Max(1L, totalArchiveBytes));
                        string stage = resourceIndex >= resources.Length
                            ? "Installing ability icons…"
                            : (resourceIndex == 0
                                ? "Installing interface artwork…"
                                : "Installing resolution layout…");
                        SafeProgress(progress, rangeStart, stage);

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
                                int percent = rangeStart + (int)Math.Min((long)rangeLength,
                                    completedBytes * rangeLength / Math.Max(1L, totalBytes));
                                SafeProgress(progress, percent, stage);
                            }
                            finally
                            {
                                if (File.Exists(temporary))
                                    File.Delete(temporary);
                            }
                        }
                    }
                    bytesBeforeArchive += archiveBytes[resourceIndex];
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
            return Path.Combine(directory, "KMRP.log");
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

        internal static bool TryReadInstalledResolution(string targetPath, out int width, out int height)
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
        internal static readonly Color Window = Color.FromArgb(7, 12, 21);
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

        // Sampled off the reference: the surround is near-black navy, the card a step
        // lighter and bluer, and the glyph stroke a bright cornflower.
        internal static readonly Color Card = Color.FromArgb(13, 21, 34);
        internal static readonly Color CardHover = Color.FromArgb(19, 30, 47);
        internal static readonly Color CardEdge = Color.FromArgb(31, 46, 69);
        internal static readonly Color Hairline = Color.FromArgb(23, 34, 52);
        internal static readonly Color Badge = Color.FromArgb(18, 28, 44);
        internal static readonly Color BadgeEdge = Color.FromArgb(30, 45, 68);
        internal static readonly Color Field = Color.FromArgb(9, 15, 26);
        internal static readonly Color AccentLit = Color.FromArgb(96, 178, 255);
        internal static readonly Color TextFaint = Color.FromArgb(122, 138, 154);
        // The step glyphs get their own colour rather than reusing Accent, so retuning the
        // primary button never drags the icons with it.
        internal static readonly Color GlyphInk = Color.FromArgb(92, 165, 250);

        internal enum Glyph { Folder, Shield, Monitor, Tools }

        // Hand-drawn icons, when supplied. Each is stored as white ink on transparency, so
        // a colour matrix multiplies it straight to GlyphInk -- the colour stays one
        // constant here instead of being baked into the artwork. Steps without a supplied
        // icon fall back to DrawGlyph, so a partial set still builds and still looks whole.
        private static readonly Dictionary<Glyph, Image> IconArt = new Dictionary<Glyph, Image>();
        private static bool iconsLoaded;
        private static readonly Dictionary<string, Image> StatusArt = new Dictionary<string, Image>();

        private static Image IconFor(Glyph glyph)
        {
            if (!iconsLoaded)
            {
                iconsLoaded = true;
                string[] names = { "folder", "shield", "monitor", "tools" };
                Glyph[] keys = { Glyph.Folder, Glyph.Shield, Glyph.Monitor, Glyph.Tools };
                for (int i = 0; i < names.Length; i++)
                {
                    try
                    {
                        using (Stream stream = Assembly.GetExecutingAssembly()
                                   .GetManifestResourceStream("KotorUniversalUI.icon." + names[i]))
                            if (stream != null)
                                IconArt[keys[i]] = Image.FromStream(stream);
                    }
                    catch { }
                }
            }
            Image art;
            return IconArt.TryGetValue(glyph, out art) ? art : null;
        }

        /// <summary>Draws a supplied icon tinted to `color`, or returns false if there is
        /// none for this step.</summary>
        internal static bool DrawIconArt(Graphics g, Glyph glyph, Rectangle circle, Color color)
        {
            Image art = IconFor(glyph);
            if (art == null)
                return false;

            int side = (int)Math.Round(circle.Width * 0.563F);
            Rectangle box = new Rectangle(circle.X + (circle.Width - side) / 2,
                                          circle.Y + (circle.Height - side) / 2, side, side);
            using (ImageAttributes tint = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { color.R / 255F, 0, 0, 0, 0 },
                    new float[] { 0, color.G / 255F, 0, 0, 0 },
                    new float[] { 0, 0, color.B / 255F, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { 0, 0, 0, 0, 1 } });
                tint.SetColorMatrix(matrix);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(art, box, 0, 0, art.Width, art.Height, GraphicsUnit.Pixel, tint);
            }
            return true;
        }

        /// <summary>Draw the supplied verified-status badge, tinted with the semantic
        /// success colour. The caller keeps the icon and label optically grouped.</summary>
        /// <summary>Draws a supplied status label -- "verified" or "missing" -- tinted to
        /// `color`, or returns false if that artwork was not shipped, in which case the
        /// state falls back to text alone.</summary>
        internal static bool DrawStatusArt(Graphics g, string name, Rectangle box, Color color)
        {
            Image art;
            if (!StatusArt.TryGetValue(name, out art))
            {
                try
                {
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream("KotorUniversalUI.icon." + name))
                    using (Image source = stream == null ? null : Image.FromStream(stream))
                        art = source == null ? null : new Bitmap(source);
                }
                catch { art = null; }
                StatusArt[name] = art;
            }
            if (art == null)
                return false;

            using (ImageAttributes tint = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { color.R / 255F, 0, 0, 0, 0 },
                    new float[] { 0, color.G / 255F, 0, 0, 0 },
                    new float[] { 0, 0, color.B / 255F, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { 0, 0, 0, 0, 1 } });
                tint.SetColorMatrix(matrix);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(art, box, 0, 0, art.Width, art.Height, GraphicsUnit.Pixel, tint);
            }
            return true;
        }

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

        /// <summary>Maps a point given in an icon's unit box onto its placed rectangle.</summary>
        private static PointF P(RectangleF b, float u, float v)
        {
            return new PointF(b.X + u * b.Width, b.Y + v * b.Height);
        }

        /// <summary>The icon's box inside a badge. Measured off the reference set: the ink
        /// spans 0.563 of the disc's diameter, and each glyph has its own aspect.</summary>
        private static RectangleF IconBox(Rectangle circle, float aspect)
        {
            float w = circle.Width * 0.563F;
            float h = w / aspect;
            return new RectangleF(circle.X + (circle.Width - w) / 2F,
                                  circle.Y + (circle.Height - h) / 2F, w, h);
        }

        /// <summary>Step icons, drawn rather than shipped, so the patcher stays a single
        /// file. Every coordinate below was measured off the reference artwork by scanning
        /// ink runs row by row and normalising to each glyph's own bounding box -- including
        /// the details that are easy to get wrong from memory, such as the monitor's stand
        /// being two neck strokes rather than one, and the shield being a peaked crest
        /// rather than a rounded dome.</summary>
        internal static void DrawGlyph(Graphics g, Glyph glyph, Rectangle circle, Color color)
        {
            float stroke = Math.Max(1.4F, circle.Width * 0.052F);
            using (Pen pen = new Pen(color, stroke))
            {
                pen.StartCap = LineCap.Round;
                pen.EndCap = LineCap.Round;
                pen.LineJoin = LineJoin.Round;

                if (glyph == Glyph.Folder)
                {
                    // 190x164 in the reference. A tab at the top left, a diagonal shoulder
                    // to the body's top edge at 0.20, a seam across the full width at 0.30,
                    // and an inner line at 0.80 spanning 0.24..0.86.
                    RectangleF b = IconBox(circle, 190F / 164F);
                    using (GraphicsPath back = new GraphicsPath())
                    {
                        back.AddLine(P(b, 0.02F, 0.34F), P(b, 0.02F, 0.10F));
                        back.AddLine(P(b, 0.02F, 0.10F), P(b, 0.07F, 0.02F));
                        back.AddLine(P(b, 0.07F, 0.02F), P(b, 0.35F, 0.02F));
                        back.AddLine(P(b, 0.35F, 0.02F), P(b, 0.46F, 0.19F));
                        back.AddLine(P(b, 0.46F, 0.19F), P(b, 0.94F, 0.19F));
                        back.AddLine(P(b, 0.94F, 0.19F), P(b, 0.98F, 0.26F));
                        g.DrawPath(pen, back);
                    }
                    using (GraphicsPath front = new GraphicsPath())
                    {
                        front.AddLine(P(b, 0.02F, 0.30F), P(b, 0.98F, 0.30F));
                        front.AddLine(P(b, 0.98F, 0.30F), P(b, 0.98F, 0.92F));
                        front.AddArc(b.X + 0.86F * b.Width, b.Y + 0.86F * b.Height,
                                     0.12F * b.Width, 0.13F * b.Height, 0, 90);
                        front.AddLine(P(b, 0.92F, 0.99F), P(b, 0.08F, 0.99F));
                        front.AddArc(b.X + 0.02F * b.Width, b.Y + 0.86F * b.Height,
                                     0.12F * b.Width, 0.13F * b.Height, 90, 90);
                        front.AddLine(P(b, 0.02F, 0.92F), P(b, 0.02F, 0.30F));
                        g.DrawPath(pen, front);
                    }
                    g.DrawLine(pen, P(b, 0.24F, 0.80F), P(b, 0.86F, 0.80F));
                }
                else if (glyph == Glyph.Shield)
                {
                    // 182x212 -- taller than wide, and peaked: a point at the top centre,
                    // shoulders sweeping out to the full width by 0.25, then curving in to a
                    // point at the bottom.
                    RectangleF b = IconBox(circle, 182F / 212F);
                    using (GraphicsPath shield = new GraphicsPath())
                    {
                        shield.AddLine(P(b, 0.50F, 0.01F), P(b, 0.04F, 0.22F));
                        shield.AddBezier(P(b, 0.04F, 0.22F), P(b, 0.04F, 0.52F),
                                         P(b, 0.18F, 0.84F), P(b, 0.50F, 0.99F));
                        shield.AddBezier(P(b, 0.50F, 0.99F), P(b, 0.82F, 0.84F),
                                         P(b, 0.96F, 0.52F), P(b, 0.96F, 0.22F));
                        shield.AddLine(P(b, 0.96F, 0.22F), P(b, 0.50F, 0.01F));
                        g.DrawPath(pen, shield);
                    }
                }
                else if (glyph == Glyph.Monitor)
                {
                    // 199x177. Screen to 0.78, then TWO neck strokes at 0.445 and 0.56
                    // running to 0.93, then a base bar spanning 0.23..0.76.
                    RectangleF b = IconBox(circle, 199F / 177F);
                    using (GraphicsPath screen = RoundedRect(
                               new Rectangle((int)(b.X + 0.02F * b.Width), (int)(b.Y + 0.02F * b.Height),
                                             (int)(0.96F * b.Width), (int)(0.76F * b.Height)),
                               (int)Math.Max(2F, 0.06F * b.Width)))
                        g.DrawPath(pen, screen);
                    // The reference puts the two neck struts at 0.445 and 0.560. At our icon
                    // size that is barely 4px apart and two round-capped strokes merge into
                    // one blob, losing the very detail that distinguishes this stand. Opened
                    // to 0.40/0.60 so both struts still read -- a deliberate departure from
                    // the measurement, because the measurement does not survive the scale.
                    g.DrawLine(pen, P(b, 0.40F, 0.78F), P(b, 0.40F, 0.93F));
                    g.DrawLine(pen, P(b, 0.60F, 0.78F), P(b, 0.60F, 0.93F));
                    g.DrawLine(pen, P(b, 0.23F, 0.97F), P(b, 0.76F, 0.97F));
                }
                else
                {
                    // 189x197. A screwdriver from the top left down to the bottom right,
                    // crossing a spanner whose open jaw is at the top right.
                    RectangleF b = IconBox(circle, 189F / 197F);
                    // Screwdriver: handle at the top left as a closed blade shape, shaft down
                    // to a tip at the bottom right.
                    using (GraphicsPath handle = new GraphicsPath())
                    {
                        handle.AddLine(P(b, 0.00F, 0.12F), P(b, 0.12F, 0.00F));
                        handle.AddLine(P(b, 0.12F, 0.00F), P(b, 0.38F, 0.22F));
                        handle.AddLine(P(b, 0.38F, 0.22F), P(b, 0.26F, 0.34F));
                        handle.CloseFigure();
                        g.DrawPath(pen, handle);
                    }
                    g.DrawLine(pen, P(b, 0.27F, 0.25F), P(b, 0.94F, 0.94F));
                    // Spanner: shaft from the bottom left up to an open jaw at the top right.
                    g.DrawLine(pen, P(b, 0.06F, 0.94F), P(b, 0.62F, 0.38F));
                    using (GraphicsPath jaw = new GraphicsPath())
                    {
                        // A narrower gap than a plain C: 80 degrees, opening up and to the
                        // right, away from the shaft, so it reads as a jaw and not a letter.
                        jaw.AddArc(b.X + 0.54F * b.Width, b.Y + 0.04F * b.Height,
                                   0.42F * b.Width, 0.42F * b.Height, 25, 280);
                        g.DrawPath(pen, jaw);
                    }
                }
            }
        }

        internal static Font DisplayFont(float size, FontStyle style)
        {
            try { return new Font("Bahnschrift SemiCondensed", size, style); }
            catch { return new Font("Segoe UI Semibold", size, style); }
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

    /// <summary>A rounded, faintly lit card. The whole UI sits on one of these.</summary>
    internal sealed class CardPanel : Panel
    {
        internal int Radius = 14;
        internal Color Fill = UiTheme.Card;
        internal Color Edge = UiTheme.CardEdge;
        internal float UiScale = 1F;

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
            int scaledRadius = Math.Max(1, (int)Math.Round(Radius * UiScale));
            using (GraphicsPath path = UiTheme.RoundedRect(r, scaledRadius))
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
        private bool dimmed;

        /// <summary>A step that is part of the flow but cannot be acted on yet. Drawn in
        /// muted ink so it reads as waiting rather than as available.</summary>
        internal bool Dimmed
        {
            get { return dimmed; }
            set
            {
                if (dimmed == value)
                    return;
                dimmed = value;
                Invalidate();
            }
        }

        internal const int HeaderHeight = 96;
        internal const int ContentLeft = 120;
        internal string Title = String.Empty;
        internal string Subtitle = String.Empty;
        internal UiTheme.Glyph Icon = UiTheme.Glyph.Folder;
        internal bool DrawSeparator = true;
        internal float UiScale = 1F;

        internal StepRow()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = Color.Transparent;
            Height = HeaderHeight;
        }

        internal void SetSubtitle(string value)
        {
            if (Subtitle == value)
                return;
            Subtitle = value;
            Invalidate();
        }

        internal void SetTitle(string value)
        {
            if (Title == value)
                return;
            Title = value;
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            float scale = Math.Max(0.1F, UiScale);
            int horizontalInset = Math.Max(1, (int)Math.Round(26 * scale));

            if (DrawSeparator)
                using (Pen line = new Pen(UiTheme.Hairline, Math.Max(1F, scale)))
                    g.DrawLine(line, horizontalInset, Height - 1, Width - horizontalInset, Height - 1);

            // An unresolved verification step grows below its normal header. Keep the
            // badge and text anchored to the 96px header so expanding the recovery area
            // does not make the row's identity jump vertically.
            int headerHeight = Math.Min(Height, Math.Max(1, (int)Math.Round(HeaderHeight * scale)));
            int badge = Math.Max(1, (int)Math.Round(64 * scale));
            int badgeLeft = Math.Max(1, (int)Math.Round(28 * scale));
            int contentLeft = Math.Max(1, (int)Math.Round(ContentLeft * scale));
            Rectangle circle = new Rectangle(badgeLeft, (headerHeight - badge) / 2, badge, badge);
            using (SolidBrush disc = new SolidBrush(UiTheme.Badge))
                g.FillEllipse(disc, circle);
            using (Pen ring = new Pen(UiTheme.BadgeEdge))
                g.DrawEllipse(ring, circle);
            Color ink = dimmed ? UiTheme.TextFaint : UiTheme.GlyphInk;
            if (!UiTheme.DrawIconArt(g, Icon, circle, ink))
                UiTheme.DrawGlyph(g, Icon, circle, ink);

            using (SolidBrush text = new SolidBrush(dimmed ? UiTheme.TextFaint : UiTheme.Text))
            using (Font f = UiTheme.DisplayFont(22F * scale, FontStyle.Bold))
                g.DrawString(Title, f, text, contentLeft,
                    headerHeight / 2 - (int)Math.Round(30 * scale));
            using (SolidBrush text = new SolidBrush(dimmed ? UiTheme.TextFaint : UiTheme.TextMuted))
            using (Font f = new Font("Segoe UI", Math.Max(6F, 16.5F * scale)))
                g.DrawString(Subtitle, f, text, contentLeft,
                    headerHeight / 2 + (int)Math.Round(4 * scale));
        }
    }

    /// <summary>A right-aligned step status. Verified states can pair the supplied
    /// badge with their text as one compact unit instead of relying on a text glyph.</summary>
    internal sealed class StateLabel : Control
    {
        internal enum StatusBadge { None, Verified, Missing }

        internal float UiScale = 1F;
        private StatusBadge badge;

        internal StatusBadge Badge
        {
            get { return badge; }
            set
            {
                if (badge == value)
                    return;
                badge = value;
                Invalidate();
            }
        }

        internal StateLabel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw |
                     ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;
        }

        protected override void OnTextChanged(EventArgs e)
        {
            Invalidate();
            base.OnTextChanged(e);
        }

        protected override void OnForeColorChanged(EventArgs e)
        {
            Invalidate();
            base.OnForeColorChanged(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            TextFormatFlags flags = TextFormatFlags.SingleLine | TextFormatFlags.VerticalCenter |
                TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix;
            Size textSize = TextRenderer.MeasureText(e.Graphics, Text, Font,
                new Size(Int32.MaxValue, Math.Max(1, Height)), flags);
            int textWidth = Math.Min(Width, textSize.Width);

            if (badge != StatusBadge.None)
            {
                // With no text the badge carries the state on its own, so it is drawn
                // larger and alone. The step's subtitle already says what is wrong.
                bool iconOnly = String.IsNullOrEmpty(Text);
                int iconSize = Math.Max(12, (int)Math.Round((iconOnly ? 48F : 32F) * UiScale));
                int gap = iconOnly ? 0 : Math.Max(4, (int)Math.Round(8 * UiScale));
                int groupWidth = Math.Min(Width, iconSize + gap + (iconOnly ? 0 : textWidth));
                int left = Math.Max(0, Width - groupWidth);
                Rectangle iconBox = new Rectangle(left, Math.Max(0, (Height - iconSize) / 2),
                    iconSize, iconSize);
                string art = badge == StatusBadge.Verified ? "verified" : "missing";
                if (UiTheme.DrawStatusArt(e.Graphics, art, iconBox, ForeColor))
                {
                    if (iconOnly)
                        return;
                    Rectangle textBox = new Rectangle(iconBox.Right + gap, 0,
                        Math.Max(1, Width - iconBox.Right - gap), Height);
                    TextRenderer.DrawText(e.Graphics, Text, Font, textBox, ForeColor,
                        flags | TextFormatFlags.Left);
                    return;
                }
            }

            TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, ForeColor,
                flags | TextFormatFlags.Right);
        }
    }

    /// <summary>Flat pill button. `Primary` gets the lit gradient, everything else the
    /// quiet outline used for Restore.</summary>
    internal sealed class PillButton : Control
    {
        internal bool Primary;
        internal float TextSize;
        internal float UiScale = 1F;
        private int progressPercent = -1;
        private bool hover;
        private bool down;

        /// <summary>-1 restores the normal button. Values from 0 through 100 draw
        /// a clipped, illuminated progress fill inside the existing button shell.</summary>
        internal int ProgressPercent
        {
            get { return progressPercent; }
            set
            {
                int clamped = value < 0 ? -1 : Math.Max(0, Math.Min(100, value));
                if (clamped == progressPercent)
                    return;
                progressPercent = clamped;
                Invalidate();
            }
        }

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
        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            float scale = Math.Max(0.1F, UiScale);
            bool progressActive = progressPercent >= 0;

            using (GraphicsPath path = UiTheme.RoundedRect(r,
                       Math.Max(1, (int)Math.Round(8 * scale))))
            {
                if (progressActive)
                {
                    using (LinearGradientBrush baseFill = new LinearGradientBrush(
                               new Rectangle(0, 0, Math.Max(1, Width), Math.Max(1, Height)),
                               UiTheme.AccentDark, Color.FromArgb(0, 112, 151), 90F))
                        g.FillPath(baseFill, path);

                    int filled = (int)Math.Round(Width * progressPercent / 100.0);
                    if (filled > 0)
                    {
                        GraphicsState state = g.Save();
                        g.SetClip(path);
                        Rectangle fillBox = new Rectangle(0, 0, Math.Max(1, filled), Height);
                        using (LinearGradientBrush fill = new LinearGradientBrush(fillBox,
                                   Color.FromArgb(116, 171, 193), Color.FromArgb(59, 132, 162), 90F))
                            g.FillRectangle(fill, fillBox);

                        int shineHeight = Math.Max(1, (int)Math.Round(Height * 0.48));
                        using (LinearGradientBrush shine = new LinearGradientBrush(
                                   new Rectangle(0, 0, Math.Max(1, filled), shineHeight),
                                   Color.FromArgb(34, 255, 255, 255),
                                   Color.FromArgb(0, 255, 255, 255), 90F))
                            g.FillRectangle(shine, 0, 0, filled, shineHeight);

                        if (filled < Width)
                        {
                            using (Pen leadingEdge = new Pen(Color.FromArgb(145, 170, 205, 220),
                                       Math.Max(1F, 1.4F * scale)))
                                g.DrawLine(leadingEdge, filled,
                                    Math.Max(3, (int)Math.Round(6 * scale)), filled,
                                    Height - Math.Max(3, (int)Math.Round(6 * scale)));
                        }
                        g.Restore(state);
                    }

                    using (Pen edge = new Pen(Color.FromArgb(105, 119, 177, 202),
                               Math.Max(1F, scale)))
                        g.DrawPath(edge, path);
                }
                else if (!Enabled)
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

            Color ink = progressActive ? Color.White :
                (!Enabled ? UiTheme.DisabledText : (Primary ? Color.White : UiTheme.Text));
            float baseTextSize = TextSize > 0F ? TextSize : (Primary ? 18F : 15.5F);
            using (StringFormat sf = new StringFormat())
            using (Font f = UiTheme.DisplayFont(Math.Max(6F, baseTextSize * scale), FontStyle.Bold))
            {
                sf.Alignment = StringAlignment.Center;
                sf.LineAlignment = StringAlignment.Center;
                if (progressActive)
                {
                    using (SolidBrush shadow = new SolidBrush(Color.FromArgb(115, 0, 39, 58)))
                        g.DrawString(Text, f, shadow,
                            new RectangleF(0, Math.Max(1F, scale), Width, Height), sf);
                }
                using (SolidBrush brush = new SolidBrush(ink))
                g.DrawString(Text, f, brush, new RectangleF(0, 0, Width, Height), sf);
            }
        }
    }

    /// <summary>ComboBox with the system's light border painted over, plus our own chevron.
    /// `FlatStyle.Flat` still draws a Windows border and drop button, so the only way to a
    /// dark field short of reimplementing selection is to repaint after WM_PAINT.</summary>
    internal sealed class DarkCombo : ComboBox
    {
        private const int WM_PAINT = 0x000F;
        internal float UiScale = 1F;

        internal DarkCombo()
        {
            DropDownStyle = ComboBoxStyle.DropDownList;
            FlatStyle = FlatStyle.Flat;
            DrawMode = DrawMode.OwnerDrawFixed;
            BackColor = UiTheme.Field;
            ForeColor = UiTheme.Text;
            ItemHeight = 30;
            IntegralHeight = false;
            DropDownHeight = 320;
        }

        internal void SetUiScale(float scale)
        {
            UiScale = Math.Max(0.1F, scale);
            ItemHeight = Math.Max(18, (int)Math.Round(30 * UiScale));
            DropDownHeight = Math.Max(ItemHeight * 4, (int)Math.Round(320 * UiScale));
            Invalidate();
        }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (m.Msg != WM_PAINT)
                return;
            using (Graphics g = Graphics.FromHwnd(Handle))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                float scale = Math.Max(0.1F, UiScale);
                int button = Math.Max(18, (int)Math.Round(30 * scale));
                int buttonLeft = Math.Max(0, Width - button - 1);
                using (SolidBrush fill = new SolidBrush(UiTheme.Field))
                    g.FillRectangle(fill, buttonLeft, 0, Width - buttonLeft, Height);
                using (Pen edge = new Pen(UiTheme.CardEdge, Math.Max(1F, scale)))
                    g.DrawRectangle(edge, 0, 0, Width - 1, Height - 1);
                float cx = buttonLeft + (Width - buttonLeft) / 2F - scale;
                float cy = Height / 2F - scale;
                using (Pen chevron = new Pen(UiTheme.TextMuted, Math.Max(1F, 1.6F * scale)))
                {
                    chevron.StartCap = LineCap.Round;
                    chevron.EndCap = LineCap.Round;
                    g.DrawLines(chevron, new PointF[] {
                        new PointF(cx - 4.5F * scale, cy - 2F * scale),
                        new PointF(cx, cy + 2.5F * scale),
                        new PointF(cx + 4.5F * scale, cy - 2F * scale) });
                }
            }
        }
    }

    /// <summary>A lit volumetric plume. A light source sits behind the crest, luminous
    /// smoke billows down and outward from it, and dust motes fall through the beam.
    ///
    /// The billowing structure is procedural fBm noise, not sprites: soft blobs cannot
    /// produce the fractal, curdled edge that reads as real smoke. The turbulence comes
    /// from domain warping -- the noise field is sampled at coordinates that are themselves
    /// offset by another noise field, which is what folds the plume into itself instead of
    /// leaving it looking like drifting fog.
    ///
    /// Everything is accumulated into one scalar emission buffer at reduced resolution: the
    /// smoke, the source glow, the downward cone, and the motes all add into the same
    /// field, so a single bloom pass and a single colour ramp light all of them
    /// consistently, and the motes glow because they are genuinely part of the lit volume
    /// rather than dots pasted on top. The buffer is then upscaled, which supplies the
    /// final softening for free.
    ///
    /// The cost is per-pixel CPU work, so resolution and octave count are the two dials
    /// that matter for frame time; both are measured rather than guessed.</summary>
    internal sealed class LightField : IDisposable
    {
        private sealed class Mote
        {
            internal float X, Y, Fall, Drift, Phase, Size, Age, Life, Seed;
        }

        // The lamp is off-screen, above the top edge, and spans the whole bar: the source
        // is never visible, only what it lights. A localised source was tried first and
        // read as a glowing ball behind the crest.
        private const float TopFalloff = 0.7F;      // how fast the light dies with depth
        private const float TopStrength = 1.10F;
        private const float ShaftScale = 3.2F;      // lateral width of the descending shafts
        private const float ShaftStrength = 0.55F;  // how much of the light is shaped into shafts
        private const float ShaftDrift = 0.035F;    // how fast the shafts slide sideways

        // Rendering budget. Downscale is the single biggest lever on frame time -- the
        // noise is evaluated nine times per buffer pixel, so halving it quadruples the
        // cost -- but it is NOT the lever on how fine the smoke looks. Detail is limited
        // by NoiseScale, not by buffer resolution: measured, going from Downscale 8 to 3
        // tripled the cost and moved the detail figure by 6%.
        private const int Downscale = 12;
        private const int Octaves = 3;

        // Smoke shape.
        // Feature size. This is the dial that decides whether the plume reads as drifting
        // slabs or as see-through wisps; it was 2.4, where the finest octave had features
        // about 100px across and the smoke looked like a moving mass.
        private const float NoiseScale = 8.0F;
        private const float FbmGain = 0.5F;     // octave falloff; higher keeps finer wisps
        private const float WarpStrength = 1.6F;
        private const float FlowSpeed = 0.055F;   // how fast the plume travels downward
        private const float EvolveSpeed = 0.09F;  // how fast it boils in place
        private const float Threshold = 0.26F;    // noise level where smoke begins
        private const float DensityGain = 3.3F;

        // Tendrils hang downward, so the noise is sampled anisotropically: features are
        // stretched along v. At 1.0 the plume is isotropic and reads as clouds; pushed
        // as far as 0.45 it stops looking like smoke and starts looking like a comb of
        // vertical streaks.
        private const float NoiseAspectY = 0.80F;

        // The plume is dense at the top edge and breaks into wisps below a ragged front.
        // The front height is itself noise, which is what makes it billow instead of
        // sitting at a fixed line -- a smooth vertical falloff has no boundary at all.
        private const float FrontBase = 0.34F;    // mean height of the boundary
        private const float FrontWobble = 0.24F;  // how far the boundary billows
        private const float FrontScale = 5.0F;    // lateral size of the billows
        private const float FrontDrift = 0.05F;   // how fast the boundary slides sideways
        private const float TrailFalloff = 4.2F;  // how fast the wisps die below the front

        // Smoke is not uniform, so none of the above is applied evenly across the width.
        // Each column gets its own reach, its own sideways lean, and its own density, all
        // driven by slow noise in u. Without this the plume descends to a single depth
        // everywhere and falls straight down, which reads as an effect rather than as smoke.
        private const float ReachVariation = 0.75F; // +/- share of TrailFalloff per column
        private const float ReachScale = 3.0F;
        private const float ReachDrift = 0.03F;
        private const float LateralDrift = 3.0F;    // how far a tendril leans as it falls
        private const float DriftScale = 2.5F;
        private const float DriftSpeed = 0.02F;
        private const float PatchDepth = 0.09F;     // how much the smoke threshold varies
        private const float PatchScale = 1.8F;

        private const float BloomWeight = 0.55F;
        private const int BloomRadius = 2;
        private const float Exposure = 1.15F;
        private const float MaxAlpha = 0.85F;
        private const int MoteCount = 90;
        // Mote radius as a fraction of the header height. These are drawn at full
        // resolution rather than into the smoke buffer: at Downscale 8 a mote was
        // clamped to a single buffer pixel, so it could not be made any smaller and
        // upscaled to a soft 16px disc.
        private const float MoteSizeMin = 0.0045F;
        private const float MoteSizeSpan = 0.0115F;
        private const float MoteAlpha = 1.0F;
        // Motes are blue rather than taking the smoke's white, so they read as embers of
        // light in the plume instead of brighter specks of the same smoke.
        private const byte MoteR = 110;
        private const byte MoteG = 180;
        private const byte MoteB = 255;
        // The sprite carries a tight core inside a wide halo, so the drawn rectangle is
        // larger than the core. One draw per mote still, rather than a separate halo
        // pass. Keep this in step with the lobe widths in BuildMote: the two together
        // decide the glow's size, and the cost is the square of this number, so an
        // oversized sprite with narrow lobes pays for transparent pixels. At 4.5 with
        // the original lobes, 70% of every sprite was empty and the pass cost 13 ms.
        private const float MoteGlowScale = 2.4F;
        private const int MoteLevels = 24;   // pre-tinted brightness steps

        // The emission ramp, darkest to brightest: white smoke, with only a slight cool
        // lift so it sits with the rest of the palette. A saturated-blue ramp made the
        // plume look like coloured gas rather than lit smoke.
        private static readonly float[] RampStop = { 0.00F, 0.30F, 0.62F, 1.00F };
        private static readonly int[] RampR = { 10, 72, 168, 240 };
        private static readonly int[] RampG = { 12, 76, 173, 245 };
        private static readonly int[] RampB = { 16, 84, 182, 250 };

        private readonly int[] perm = new int[512];
        private readonly Random random = new Random(20260901);
        private readonly Mote[] motes = new Mote[MoteCount];

        private int width, height;
        private float[] field;
        private float[] scratch;
        private float[] colFront, colReach, colShear, colPatch;
        private byte[] pixels;
        private Bitmap buffer;
        private Bitmap[] moteSprites;
        private float time;
        private double lastRenderMs;
        // Per-stage timings, so the cost can be attributed rather than guessed at.
        private double msSmoke, msBloom, msMap, msBlit, msMotes;
        private int filledRows;   // deepest buffer row holding any smoke

        internal LightField()
        {
            int[] source = new int[256];
            for (int i = 0; i < 256; i++)
                source[i] = i;
            for (int i = 255; i > 0; i--)
            {
                int j = random.Next(i + 1);
                int swap = source[i];
                source[i] = source[j];
                source[j] = swap;
            }
            for (int i = 0; i < 512; i++)
                perm[i] = source[i & 255];

            for (int i = 0; i < MoteCount; i++)
            {
                motes[i] = new Mote();
                Respawn(motes[i], true);
            }
        }

        /// <summary>Milliseconds spent in the last Render, for the frame-budget check.</summary>
        internal double LastRenderMs { get { return lastRenderMs; } }
        internal double SmokeMs { get { return msSmoke; } }
        internal double BloomMs { get { return msBloom; } }
        internal double MapMs { get { return msMap; } }
        internal double BlitMs { get { return msBlit; } }
        internal double MotesMs { get { return msMotes; } }

        private void Respawn(Mote m, bool scatter)
        {
            m.X = (float)random.NextDouble();
            m.Y = scatter ? (float)random.NextDouble() : -(float)random.NextDouble() * 0.12F;
            // Scaled by 0.75 alongside the drop from 21.4 fps to 16 fps, so the distance
            // a mote covers between frames is unchanged and the motion stays as smooth as
            // it was. The fastest mote moves about 2.6px per frame either way, against a
            // bright core 1.5 to 5.2px across; much past that and it reads as a dot
            // reappearing rather than travelling. Ageing is tied to Fall, so a slower mote
            // also ages slower and still reaches the same depth before it dies.
            m.Fall = 0.0338F + (float)random.NextDouble() * 0.0825F;
            m.Drift = 0.012F + (float)random.NextDouble() * 0.035F;
            m.Phase = (float)(random.NextDouble() * Math.PI * 2);
            m.Size = MoteSizeMin + (float)random.NextDouble() * MoteSizeSpan;
            m.Life = 1F;
            m.Age = scatter ? (float)random.NextDouble() : 0F;
            m.Seed = 0.45F + (float)random.NextDouble() * 0.55F;
        }

        internal void Step(float seconds)
        {
            time += seconds;
            for (int i = 0; i < MoteCount; i++)
            {
                Mote m = motes[i];
                // Motes age by how far they have fallen, so a slow mote is not killed
                // early and the fall reaches the bottom of the header.
                m.Age += seconds * m.Fall / 1.15F;
                m.Y += seconds * m.Fall;
                m.Phase += seconds * 0.7F;
                if (m.Age >= m.Life || m.Y > 1.25F)
                    Respawn(m, false);
            }
        }

        internal void Render(Graphics target, Rectangle area)
        {
            if (area.Width < 8 || area.Height < 8)
                return;
            long started = Stopwatch.GetTimestamp();

            int w = Math.Max(8, area.Width / Downscale);
            int h = Math.Max(8, area.Height / Downscale);
            if (buffer == null || width != w || height != h)
            {
                if (buffer != null)
                    buffer.Dispose();
                width = w;
                height = h;
                field = new float[w * h];
                scratch = new float[w * h];
                colFront = new float[w];
                colReach = new float[w];
                colShear = new float[w];
                colPatch = new float[w];
                pixels = new byte[w * h * 4];
                buffer = new Bitmap(w, h, PixelFormat.Format32bppArgb);
            }

            float aspect = area.Width / (float)area.Height;
            double freq = Stopwatch.Frequency / 1000.0;
            long t0 = Stopwatch.GetTimestamp();
            RenderSmoke(w, h, aspect);
            long t1 = Stopwatch.GetTimestamp();
            Bloom(w, h);
            long t2 = Stopwatch.GetTimestamp();
            MapToPixels(w, h);
            long t3 = Stopwatch.GetTimestamp();

            BitmapData data = buffer.LockBits(new Rectangle(0, 0, w, h),
                ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
            buffer.UnlockBits(data);

            // HighQualityBilinear, counter-intuitively, is the fast path here. Plain
            // InterpolationMode.Bilinear was tried on the theory that the "high quality"
            // prefilter only matters when minifying: it made this stage six times slower,
            // 10.9 ms to 66.5 ms. GDI+ has an optimised implementation for the
            // HighQuality modes at this kind of magnification. Do not "optimise" it back.
            //
            // Only the rows that actually contain smoke are scaled. The plume occupies
            // roughly the top half of the header and the rest of the buffer is empty, so
            // blitting the whole thing spends most of its time magnifying zeroes.
            int rows = Math.Min(h, filledRows);
            InterpolationMode previous = target.InterpolationMode;
            target.InterpolationMode = InterpolationMode.HighQualityBilinear;
            if (rows > 0)
            {
                int destHeight = (int)Math.Ceiling(rows * area.Height / (double)h);
                if (destHeight > area.Height)
                    destHeight = area.Height;
                target.DrawImage(buffer,
                    new Rectangle(area.X, area.Y, area.Width, destHeight),
                    0, 0, w, rows, GraphicsUnit.Pixel);
            }
            target.InterpolationMode = previous;
            long t4 = Stopwatch.GetTimestamp();

            RenderMotes(target, area);
            long t5 = Stopwatch.GetTimestamp();

            msSmoke = (t1 - t0) / freq;
            msBloom = (t2 - t1) / freq;
            msMap = (t3 - t2) / freq;
            msBlit = (t4 - t3) / freq;
            msMotes = (t5 - t4) / freq;

            lastRenderMs = (Stopwatch.GetTimestamp() - started) * 1000.0 / Stopwatch.Frequency;
        }

        private void RenderSmoke(int w, int h, float aspect)
        {
            float evolve = time * EvolveSpeed;

            // Per-column variation, hoisted out of the pixel loop: it depends on u and
            // time but not on v, so evaluating it per column instead of per pixel costs
            // w noise samples a frame rather than w*h.
            for (int x = 0; x < w; x++)
            {
                float cu = (x + 0.5F) / w;
                colFront[x] = FrontBase + FrontWobble
                    * Noise(cu * FrontScale + time * FrontDrift, 7.3F, evolve);
                float reach = Noise(cu * ReachScale + time * ReachDrift, 21.5F, evolve * 0.4F);
                colReach[x] = Math.Max(0.6F, TrailFalloff * (1F + ReachVariation * 2F * reach));
                colShear[x] = LateralDrift
                    * Noise(cu * DriftScale + time * DriftSpeed, 33.1F, evolve * 0.4F);
                colPatch[x] = PatchDepth
                    * Noise(cu * PatchScale + time * 0.03F, 51.7F, evolve * 0.3F);
            }

            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5F) / h;

                for (int x = 0; x < w; x++)
                {
                    float u = (x + 0.5F) / w;

                    float lit = LightAt(u, v);
                    if (lit < 0.004F)
                    {
                        field[y * w + x] = 0F;
                        continue;
                    }

                    // Solid above the front, decaying into wisps below it, at a rate
                    // that differs column by column. The front is continuous at the
                    // boundary (exp(0) == 1), so there is no seam.
                    float below = v - colFront[x];
                    float shape = below <= 0F ? 1F
                        : (float)Math.Exp(-below * colReach[x]);

                    // Sample the plume in a frame that travels downward with it. The
                    // lateral offset grows with depth, so a tendril leans further the
                    // further it falls, and neighbouring columns lean different ways.
                    float nx = u * NoiseScale * aspect
                        + colShear[x] * (below <= 0F ? 0F : below);
                    float ny = (v - time * FlowSpeed) * NoiseScale * NoiseAspectY;

                    // Domain warp: offset the lookup by another noise field. This is what
                    // curdles the plume instead of leaving it as smooth drifting fog.
                    float wx = Fbm(nx + 3.1F, ny + 1.7F, evolve);
                    float wy = Fbm(nx - 2.4F, ny + 5.3F, evolve + 2.0F);
                    float n = Fbm(nx + WarpStrength * wx, ny + WarpStrength * wy, evolve);

                    // Beer-Lambert extinction rather than a linear ramp with a clamp.
                    // The clamp was what made the plume read as moving slabs: everything
                    // past the saturation point rendered as one flat opaque value, so
                    // large regions had no internal variation at all. An exponential
                    // approaches full opacity without ever reaching it, which is both how
                    // light actually attenuates through a medium and what keeps the smoke
                    // see-through.
                    float thickness = (n * 0.5F + 0.5F - (Threshold - colPatch[x])) * shape;
                    if (thickness <= 0F)
                    {
                        field[y * w + x] = 0F;
                        continue;
                    }
                    float dens = 1F - (float)Math.Exp(-thickness * DensityGain);

                    field[y * w + x] = dens * lit * Exposure;
                }
            }
        }

        /// <summary>Light entering from above the top edge, across the full width, dying
        /// with depth. Broken into irregular descending shafts so it reads as light coming
        /// through something rather than as a flat gradient -- the shafts are what make the
        /// effect visible while the source itself stays off-screen.</summary>
        private float LightAt(float u, float v)
        {
            if (v < 0F)
                v = 0F;
            float fall = (float)Math.Exp(-v * TopFalloff);
            float s = Noise(u * ShaftScale + time * ShaftDrift, 11.7F, 3.9F) * 0.5F + 0.5F;
            float shaft = 1F - ShaftStrength + ShaftStrength * s * s;
            return TopStrength * fall * shaft;
        }

        /// <summary>Motes are drawn at full resolution, after the smoke buffer has been
        /// upscaled, so their size is independent of Downscale and they stay crisp
        /// against the soft plume. One cached sprite is tinted per mote through a reused
        /// colour matrix, so the pass allocates nothing.</summary>
        private void RenderMotes(Graphics target, Rectangle area)
        {
            if (moteSprites == null)
            {
                moteSprites = new Bitmap[MoteLevels];
                for (int i = 0; i < MoteLevels; i++)
                    moteSprites[i] = BuildMote(48, (i + 1) / (float)MoteLevels);
            }

            InterpolationMode previous = target.InterpolationMode;
            target.InterpolationMode = InterpolationMode.Bilinear;
            for (int i = 0; i < MoteCount; i++)
            {
                Mote m = motes[i];
                float t = m.Age / Math.Max(0.001F, m.Life);
                float fade = t < 0.12F ? t / 0.12F : (t > 0.45F ? 1F - (t - 0.45F) / 0.55F : 1F);
                if (fade <= 0F)
                    continue;

                float mx = m.X + (float)Math.Sin(m.Phase) * m.Drift;
                float my = m.Y;
                if (my < -0.05F || my > 1.05F)
                    continue;

                // A mote is only as bright as the light reaching it.
                float bright = fade * m.Seed * LightAt(mx, my) * MoteAlpha;
                if (bright <= 0.004F)
                    continue;
                if (bright > 1F)
                    bright = 1F;

                // Pick a pre-tinted sprite rather than tinting at draw time. A
                // per-draw ColorMatrix puts GDI+ on a slow blit path, and the colour
                // never varies -- only the brightness, which quantises to these levels
                // without any visible banding on something this small and this soft.
                int level = (int)(bright * (MoteLevels - 1) + 0.5F);
                if (level < 0) level = 0; else if (level >= MoteLevels) level = MoteLevels - 1;

                float radius = m.Size * MoteGlowScale * area.Height;
                float cx = area.Left + mx * area.Width;
                float cy = area.Top + my * area.Height;
                Rectangle dest = new Rectangle(
                    (int)(cx - radius), (int)(cy - radius),
                    Math.Max(2, (int)(radius * 2)), Math.Max(2, (int)(radius * 2)));
                target.DrawImage(moteSprites[level], dest);
            }
            target.InterpolationMode = previous;
        }

        /// <summary>A tight bright core inside a wide soft halo -- two gaussian lobes
        /// rather than one falloff. The narrow lobe keeps the mote a definite point of
        /// light at a few pixels across; the broad lobe is the glow around it. Drawing
        /// one sprite that contains both is cheaper than a separate halo pass, and the
        /// core stays small because the narrow lobe is a small fraction of the sprite.</summary>
        private static Bitmap BuildMote(int size, float level)
        {
            Bitmap bitmap = new Bitmap(size, size, PixelFormat.Format32bppArgb);
            BitmapData data = bitmap.LockBits(new Rectangle(0, 0, size, size),
                ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            byte[] px = new byte[data.Stride * size];
            float centre = (size - 1) / 2F;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = (x - centre) / centre;
                    float dy = (y - centre) / centre;
                    double d = Math.Sqrt(dx * dx + dy * dy);
                    double core = Math.Exp(-(d * d) / (2 * 0.1875 * 0.1875));
                    double halo = Math.Exp(-(d * d) / (2 * 0.55 * 0.55));
                    // Taper to exactly zero at the rim, or the square sprite shows its
                    // edges once the alpha is scaled up.
                    double edge = d >= 1.0 ? 0.0 : Math.Pow(1.0 - d, 1.5);
                    double a = Math.Min(1.0, 0.85 * core + 0.30 * halo) * edge * level;
                    int at = y * data.Stride + x * 4;
                    px[at] = MoteB;
                    px[at + 1] = MoteG;
                    px[at + 2] = MoteR;
                    px[at + 3] = (byte)Math.Max(0, Math.Min(255, (int)(a * 255)));
                }
            }
            Marshal.Copy(px, 0, data.Scan0, px.Length);
            bitmap.UnlockBits(data);
            return bitmap;
        }

        /// <summary>Separable box blur added back over the original. Two narrow passes are
        /// cheaper than one wide one and land close enough to a gaussian for a glow.</summary>
        private void Bloom(int w, int h)
        {
            int r = BloomRadius;
            float inv = 1F / (2 * r + 1);

            for (int y = 0; y < h; y++)
            {
                int row = y * w;
                for (int x = 0; x < w; x++)
                {
                    float sum = 0F;
                    for (int k = -r; k <= r; k++)
                    {
                        int sx = x + k;
                        if (sx < 0) sx = 0; else if (sx >= w) sx = w - 1;
                        sum += field[row + sx];
                    }
                    scratch[row + x] = sum * inv;
                }
            }
            for (int x = 0; x < w; x++)
            {
                for (int y = 0; y < h; y++)
                {
                    float sum = 0F;
                    for (int k = -r; k <= r; k++)
                    {
                        int sy = y + k;
                        if (sy < 0) sy = 0; else if (sy >= h) sy = h - 1;
                        sum += scratch[sy * w + x];
                    }
                    field[y * w + x] += sum * inv * BloomWeight;
                }
            }
        }

        private void MapToPixels(int w, int h)
        {
            int count = w * h;
            int deepest = 0;
            for (int i = 0; i < count; i++)
            {
                int at = i * 4;
                float e = field[i];
                if (e <= 0.002F)
                {
                    pixels[at] = 0;
                    pixels[at + 1] = 0;
                    pixels[at + 2] = 0;
                    pixels[at + 3] = 0;
                    continue;
                }
                if (e > 1F)
                    e = 1F;
                deepest = i / w;

                int stop = 0;
                while (stop < RampStop.Length - 2 && e > RampStop[stop + 1])
                    stop++;
                float span = RampStop[stop + 1] - RampStop[stop];
                float f = span <= 0F ? 0F : (e - RampStop[stop]) / span;
                if (f < 0F) f = 0F; else if (f > 1F) f = 1F;

                pixels[at] = (byte)(RampB[stop] + (RampB[stop + 1] - RampB[stop]) * f);
                pixels[at + 1] = (byte)(RampG[stop] + (RampG[stop + 1] - RampG[stop]) * f);
                pixels[at + 2] = (byte)(RampR[stop] + (RampR[stop + 1] - RampR[stop]) * f);
                // Alpha rises faster than colour so thin smoke is tinted, not merely dim.
                float a = e * 1.35F;
                if (a > 1F) a = 1F;
                pixels[at + 3] = (byte)(a * MaxAlpha * 255F);
            }
            filledRows = Math.Min(h, deepest + 2);   // one row of margin for the upscale
        }

        private float Fbm(float x, float y, float z)
        {
            float sum = 0F, amp = 0.5F, freq = 1F, norm = 0F;
            for (int i = 0; i < Octaves; i++)
            {
                sum += amp * Noise(x * freq, y * freq, z * freq);
                norm += amp;
                freq *= 2F;
                amp *= FbmGain;
            }
            // Normalised, so changing Octaves or FbmGain changes the character of the
            // noise without also changing its overall level -- otherwise every detail
            // tweak silently rescales the density and has to be re-tuned.
            return norm <= 0F ? 0F : sum * 0.5F / norm;
        }

        private static float Fade(float t) { return t * t * t * (t * (t * 6F - 15F) + 10F); }
        private static float Lerp(float a, float b, float t) { return a + (b - a) * t; }

        private static float Grad(int hash, float x, float y, float z)
        {
            int h = hash & 15;
            float u = h < 8 ? x : y;
            float v = h < 4 ? y : (h == 12 || h == 14 ? x : z);
            return ((h & 1) == 0 ? u : -u) + ((h & 2) == 0 ? v : -v);
        }

        /// <summary>Perlin improved gradient noise. Gradient rather than value noise:
        /// value noise leaves visible axis-aligned blocking once it is warped.</summary>
        private float Noise(float x, float y, float z)
        {
            int xi = (int)Math.Floor(x) & 255;
            int yi = (int)Math.Floor(y) & 255;
            int zi = (int)Math.Floor(z) & 255;
            x -= (float)Math.Floor(x);
            y -= (float)Math.Floor(y);
            z -= (float)Math.Floor(z);
            float u = Fade(x), v = Fade(y), t = Fade(z);

            int a = perm[xi] + yi, aa = perm[a] + zi, ab = perm[a + 1] + zi;
            int b = perm[xi + 1] + yi, ba = perm[b] + zi, bb = perm[b + 1] + zi;

            return Lerp(
                Lerp(Lerp(Grad(perm[aa], x, y, z), Grad(perm[ba], x - 1, y, z), u),
                     Lerp(Grad(perm[ab], x, y - 1, z), Grad(perm[bb], x - 1, y - 1, z), u), v),
                Lerp(Lerp(Grad(perm[aa + 1], x, y, z - 1), Grad(perm[ba + 1], x - 1, y, z - 1), u),
                     Lerp(Grad(perm[ab + 1], x, y - 1, z - 1), Grad(perm[bb + 1], x - 1, y - 1, z - 1), u), v),
                t);
        }

        public void Dispose()
        {
            if (buffer != null)
            {
                buffer.Dispose();
                buffer = null;
            }
            if (moteSprites != null)
            {
                for (int i = 0; i < moteSprites.Length; i++)
                    if (moteSprites[i] != null)
                        moteSprites[i].Dispose();
                moteSprites = null;
            }
        }
    }

    internal sealed class MainForm : Form
    {
        private delegate void UiOperation(Action<string> report, Action<int, string> progress);

        private sealed class FontTemplate
        {
            internal readonly string Family;
            internal readonly float Size;
            internal readonly FontStyle Style;
            internal readonly GraphicsUnit Unit;

            internal FontTemplate(Font font)
            {
                Family = font.FontFamily.Name;
                Size = font.Size;
                Style = font.Style;
                Unit = font.Unit;
            }

            internal Font Create(float scale)
            {
                return new Font(Family, Math.Max(6F, Size * scale), Style, Unit);
            }
        }

        internal const string AppName = "KOTOR Modern Restoration Patch";
        internal const string ShortName = "KMRP";
        internal const string Version = "v1.0.0";
        // The header is measured from the brand artwork rather than fixed, so widening
        // the window scales the lockup and the card follows it down.
        // The lockup is sized against the card, not the window, so the two read as one
        // block: half the card's width, centred on it.
        private const double BrandCardFraction = 0.5;
        // The card is a fixed rectangle rather than something that stretches to the
        // window's edges: on a wide window a full-width row leaves a desert between a
        // step's subtitle and its control. Its height is fully determined by the row
        // heights below -- four steps, the gap above the action button, the button, and
        // the bottom padding -- so the width follows from the ratio.
        private const double CardAspect = 2.25;   // 1.5 was the first pass; this is 50% wider
        private const int StepHeight = 108;
        // Where the wordmark's ink actually ends inside the brand image, as a fraction of
        // its width. The PNG carries transparent margin and glow beyond the last letter, so
        // the drawn width is not the visible width -- measured on the artwork: the R's right
        // edge sits at 0.9774.
        private const double WordmarkInkRight = 0.9774;
        private const double WordmarkInkLeft = 0.0216;
        private const string Tagline = "M O D E R N .   R E S T O R E D .   S I M P L E .";
        private const string EditableExeUrl = "https://deadlystream.com/files/file/1320-kotor-editable-executable/";
        private readonly int headerHeight;
        private readonly int brandWidth;
        private readonly int brandHeight;
        private const string CreatorUrl = "https://deadlystream.com/profile/68365-raymangt/";

        private readonly TextBox pathBox;              // data holder; the path is shown in step 1's subtitle
        private readonly DarkCombo resolutionBox;
        private readonly PillButton actionButton;
        private bool actionIsRestore;
        private readonly PillButton browseButton;
        private readonly StepRow stepFolder;
        private readonly StepRow stepVerify;
        private readonly StepRow stepResolution;
        private readonly StepRow stepApply;
        private readonly StateLabel verifyState;
        private readonly StateLabel resolutionState;
        private readonly StateLabel applyState;
        private readonly CardPanel verificationRecovery;
        private readonly PillButton downloadExecutableButton;
        private readonly PillButton chooseExecutableButton;
        private readonly PillButton checkExecutableButton;
        private readonly Panel optionsHost;           // reserved: future checkboxes land here
        private readonly LinkLabel logLink;
        private Image brand;
        private readonly LightField light = new LightField();
        // The header repaints on every animation frame, so the brand must not be
        // resampled on every one of them: a 650x350 bicubic resize per frame cost more
        // than the plume itself. Scaled once per size, then blitted.
        private Bitmap scaledBrand;
        // The plume is generated on its own thread into an off-screen surface; the UI
        // thread only blits the finished frame. Painting it inline cost the UI thread
        // about 20 ms of every 62 ms frame -- fine on an idle window, but not enough
        // headroom left to also service a dropdown being scrolled, which is what made the
        // animation stutter there.
        private System.Threading.Thread renderThread;
        private volatile bool renderRunning;
        private volatile int desiredHeaderW, desiredHeaderH;
        private Bitmap headerFront, headerBack;
        private readonly object headerSwap = new object();
        // The brand and tagline on transparency, composited into each frame by the render
        // thread. The render thread cannot draw them itself -- fonts and the scaled artwork
        // belong to the UI thread -- so they are baked here whenever the size changes.
        private Bitmap headerOverlay;
        private readonly object overlayLock = new object();
        // Presentation goes straight to the window from the render thread. Posting through
        // BeginInvoke put every frame in the message queue behind whatever else was there;
        // measured while scrolling the resolution dropdown, frames were produced with 1.0 ms
        // of jitter but waited up to 61.8 ms to reach the screen, which is a whole frame.
        private volatile IntPtr presentHwnd;
        private volatile bool allowDirectPresent;

        // 60ms, which Windows' 15.6ms timer granularity rounds to 62.4ms -- 16 fps,
        // against 46.8ms and 21.4 fps at the previous 40ms. A quarter fewer frames for a
        // quarter less CPU. See the mote fall speed, which was slowed to match: the two
        // must move together or the fastest motes start stepping.
        private const int AnimationIntervalMs = 60;
        private Font taglineFont;      // sized so the tagline matches the wordmark's width
        private bool operationRunning;
        private string lastDetail = String.Empty;
        private readonly Dictionary<Control, Rectangle> designBounds = new Dictionary<Control, Rectangle>();
        private readonly Dictionary<Control, FontTemplate> designFonts = new Dictionary<Control, FontTemplate>();
        private readonly Dictionary<Control, Font> scaledFonts = new Dictionary<Control, Font>();
        private readonly List<Font> retiredFonts = new List<Font>();
        private readonly Timer fontRetireTimer;
        private Size designClientSize;
        private Size lastClientSize;
        private float uiScale = 1F;
        private float nativeFontScale = 1F;
        private Bitmap resizePreview;
        private bool resizePreviewActive;
        private int resizeHeaderHeight;
        private readonly List<Control> resizePreviewControls = new List<Control>();
        private bool resizeReady;
        private bool enforcingAspect;
        private bool initialFitApplied;
        private const float MinimumUiScale = 0.35F;
        private const int ReferenceWorkingWidth = 1920;
        private const int ReferenceWorkingHeight = 1040;
        private const int ReferenceWindowWidth = 1300;
        private const int ReferenceWindowHeight = 700;

        internal MainForm()
        {
            Text = ShortName + " – " + AppName;
            MaximizeBox = false;
            FormBorderStyle = FormBorderStyle.Sizable;
            SizeGripStyle = SizeGripStyle.Show;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            DoubleBuffered = true;
            SetStyle(ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint |
                ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI", 11F);
            BackColor = UiTheme.Window;
            ForeColor = UiTheme.Text;
            // WinForms can queue a LinkLabel paint while a resize is replacing its font.
            // Keep old scaled fonts alive until the resize/paint burst has gone idle.
            // ~25fps is plenty for a slow haze, and the field only ever invalidates the
            // header strip, so a frame costs one small bitmap and one upscale.
            HandleCreated += delegate
            {
                if (renderThread != null)
                    return;
                desiredHeaderW = Math.Max(1, ClientSize.Width);
                desiredHeaderH = Math.Max(1, ScaleDesign(headerHeight));
                presentHwnd = Handle;
                EnsureHeaderOverlay(desiredHeaderW, desiredHeaderH);
                UpdatePresentMode();
                renderRunning = true;
                renderThread = new System.Threading.Thread(RenderLoop);
                renderThread.IsBackground = true;
                // Below normal: the plume must never win a scheduling contest against the
                // UI thread, or against the file work during a patch.
                renderThread.Priority = System.Threading.ThreadPriority.BelowNormal;
                renderThread.Start();
            };

            fontRetireTimer = new Timer();
            fontRetireTimer.Interval = 750;
            fontRetireTimer.Tick += delegate
            {
                fontRetireTimer.Stop();
                DisposeRetiredFonts();
            };
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
            // action, the action button, and the bottom padding.
            int cardHeight = 4 * StepHeight + 30 + 76 + 40;
            int cardWidth = (int)Math.Round(cardHeight * CardAspect);

            brandWidth = (int)Math.Round(cardWidth * BrandCardFraction);
            brandHeight = brand == null ? 150
                : (int)Math.Round(brand.Height * (brandWidth / (double)brand.Width));
            headerHeight = 14 + brandHeight + 56;

            // The window's side margin is not a free choice: it is set equal to the gap
            // between the end of the wordmark and the card's edge, so the lockup, the card
            // and the window frame all breathe at the same rhythm. Both the card and the
            // lockup are centred, so that gap is cardWidth/2 minus how far the ink reaches
            // past the lockup's own centre.
            int gapInsideCard = (int)Math.Round(cardWidth / 2.0
                                                - (WordmarkInkRight - 0.5) * brandWidth);
            int clientWidth = cardWidth + 2 * gapInsideCard;
            ClientSize = new Size(clientWidth, 900);

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
            browseButton.TextSize = 18F;
            browseButton.SetBounds(card.Width - 168, 24, 132, 48);
            browseButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            browseButton.Click += delegate { BrowseForExecutable(this); };
            stepFolder.Controls.Add(browseButton);

            stepVerify = NewStep(card, 1, UiTheme.Glyph.Shield, "2. Verify Editable EXE",
                "Checking for the required editable swkotor.exe.");
            verifyState = NewStateLabel(stepVerify, card.Width);

            // Verification recovery lives in the step that owns the problem. While the
            // executable is unresolved, this panel expands Step 2 into the space normally
            // used by Steps 3 and 4; there is no interrupting modal and no taller window.
            verificationRecovery = new CardPanel();
            // Same fill and edge as the card it sits in, so it reads as part of step 2
            // rather than as a panel within a panel. Every other step is a single flat
            // row; a sunken bordered box here was the main reason this state looked like
            // it came from a different application.
            verificationRecovery.Fill = UiTheme.Card;
            verificationRecovery.Edge = UiTheme.Card;
            verificationRecovery.Radius = 10;
            // 91, not 84: the gap between the subtitle and these buttons is then the same
            // as the gap between the step title and the subtitle. Measured ink-to-ink,
            // because the fonts carry different internal leading and box positions do not
            // predict the visual gap.
            verificationRecovery.SetBounds(StepRow.ContentLeft, 91, card.Width - StepRow.ContentLeft - 36, 48);
            verificationRecovery.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            verificationRecovery.Visible = false;
            stepVerify.Controls.Add(verificationRecovery);

            downloadExecutableButton = new PillButton();
            downloadExecutableButton.Primary = true;
            downloadExecutableButton.Text = "Get Editable EXE";
            downloadExecutableButton.SetBounds(0, 0, 230, 48);
            downloadExecutableButton.Click += delegate { OpenEditableExecutablePage(); };
            verificationRecovery.Controls.Add(downloadExecutableButton);

            chooseExecutableButton = new PillButton();
            chooseExecutableButton.Text = "Choose Editable EXE";
            chooseExecutableButton.SetBounds(242, 0, 218, 48);
            chooseExecutableButton.Click += delegate { BrowseForExecutable(this); };
            verificationRecovery.Controls.Add(chooseExecutableButton);

            checkExecutableButton = new PillButton();
            checkExecutableButton.Text = "Check Again";
            checkExecutableButton.SetBounds(472, 0, 164, 48);
            checkExecutableButton.Click += delegate { RefreshStatus(); };
            verificationRecovery.Controls.Add(checkExecutableButton);

            stepResolution = NewStep(card, 2, UiTheme.Glyph.Monitor, "3. Choose Resolution",
                "Select the resolution you want to patch for.");
            resolutionBox = new DarkCombo();
            resolutionBox.Font = new Font("Segoe UI Semibold", 17F, FontStyle.Regular);
            resolutionBox.SetBounds(card.Width - 448, 26, 412, 44);
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
            resolutionState = NewStateLabel(stepResolution, card.Width);
            resolutionState.Visible = false;

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

            // One action, whose identity follows the executable's state: patch a clean
            // install, restore a patched one. Two permanently visible buttons meant one of
            // them was always disabled, which reads as something being broken rather than
            // as a step that does not apply yet.
            actionButton = new PillButton();
            actionButton.Primary = true;
            actionButton.Text = "Start Patching";
            actionButton.SetBounds(80, optionsHost.Bottom + 30, card.Width - 160, 76);
            actionButton.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            actionButton.Click += ActionClicked;
            card.Controls.Add(actionButton);

            card.Height = actionButton.Bottom + 40;

            logLink = new LinkLabel();
            logLink.Text = Version + "   ·   Open Log";
            logLink.LinkArea = new LinkArea(Version.Length + 7, 8);
            logLink.Font = new Font("Segoe UI", 15.5F);
            logLink.ForeColor = UiTheme.TextFaint;
            logLink.LinkColor = UiTheme.Accent;
            logLink.ActiveLinkColor = Color.White;
            logLink.VisitedLinkColor = UiTheme.Accent;
            logLink.LinkBehavior = LinkBehavior.HoverUnderline;
            logLink.BackColor = Color.Transparent;
            logLink.TextAlign = ContentAlignment.MiddleLeft;
            logLink.SetBounds(card.Left + 8, card.Bottom + 14, 240, 34);
            logLink.Anchor = AnchorStyles.Top;
            logLink.LinkClicked += OpenLogClicked;
            Controls.Add(logLink);

            LinkLabel credit = new LinkLabel();
            credit.Text = "Created by RaymanGT";
            credit.Font = new Font("Segoe UI", 15.5F);
            credit.LinkColor = UiTheme.TextFaint;
            credit.ActiveLinkColor = UiTheme.Accent;
            credit.VisitedLinkColor = UiTheme.TextFaint;
            credit.LinkBehavior = LinkBehavior.HoverUnderline;
            credit.BackColor = Color.Transparent;
            credit.TextAlign = ContentAlignment.MiddleRight;
            credit.SetBounds(card.Right - 228, card.Bottom + 14, 220, 34);
            credit.Anchor = AnchorStyles.Top;
            credit.LinkClicked += delegate { OpenCreatorPage(); };
            Controls.Add(credit);

            ClientSize = new Size(ClientSize.Width, credit.Bottom + 18);

            // Every element keeps a design-space rectangle. Resizing reapplies those
            // rectangles at one uniform scale, so type, spacing, icons, hit targets and
            // artwork all grow together instead of stretching independently.
            designClientSize = ClientSize;
            lastClientSize = ClientSize;
            CaptureDesignLayout(this);
            MinimumSize = SizeFromClientSize(new Size(
                (int)Math.Round(designClientSize.Width * MinimumUiScale),
                (int)Math.Round(designClientSize.Height * MinimumUiScale)));
            MaximumSize = Size.Empty;

            pathBox.Text = FindDefaultExecutable();
            RefreshStatus();
            resizeReady = true;

            Shown += delegate
            {
                FitInitialSizeToWorkingArea();
            };
            Activated += delegate { RefreshStatus(); };
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (!operationRunning)
                    return;
                e.Cancel = true;
                MessageBox.Show(this, "Please wait for the current operation to finish.", "Patcher is working",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            if (!resizeReady || enforcingAspect || WindowState != FormWindowState.Normal ||
                ClientSize.Width <= 0 || ClientSize.Height <= 0)
                return;

            Size requested = ClientSize;
            double widthDelta = Math.Abs(requested.Width - lastClientSize.Width) /
                (double)Math.Max(1, designClientSize.Width);
            double heightDelta = Math.Abs(requested.Height - lastClientSize.Height) /
                (double)Math.Max(1, designClientSize.Height);
            float requestedScale = widthDelta >= heightDelta
                ? requested.Width / (float)designClientSize.Width
                : requested.Height / (float)designClientSize.Height;
            float scale = Math.Max(MinimumUiScale, requestedScale);
            Size proportional = new Size(
                Math.Max(1, (int)Math.Round(designClientSize.Width * scale)),
                Math.Max(1, (int)Math.Round(designClientSize.Height * scale)));

            enforcingAspect = true;
            try
            {
                if (ClientSize != proportional)
                    ClientSize = proportional;
                if (resizePreviewActive)
                    Invalidate();
                else
                    ApplyUniformScale(scale);
                lastClientSize = ClientSize;
            }
            finally
            {
                enforcingAspect = false;
            }
        }

        protected override void OnResizeBegin(EventArgs e)
        {
            base.OnResizeBegin(e);
            BeginResizePreview();
        }

        protected override void OnResizeEnd(EventArgs e)
        {
            EndResizePreview();
            base.OnResizeEnd(e);
        }

        private void BeginResizePreview()
        {
            if (!resizeReady || resizePreviewActive || ClientSize.Width <= 0 || ClientSize.Height <= 0)
                return;

            // Finish any pending state/paint work before freezing the visual frame. This
            // prevents a partially painted recovery panel from becoming the resize preview.
            if (!operationRunning)
                RefreshStatus();
            Refresh();

            Bitmap preview = null;
            try
            {
                preview = new Bitmap(ClientSize.Width, ClientSize.Height,
                    System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
                using (Graphics capture = Graphics.FromImage(preview))
                {
                    Point clientOrigin = PointToScreen(Point.Empty);
                    capture.CopyFromScreen(clientOrigin, Point.Empty, ClientSize,
                        CopyPixelOperation.SourceCopy);
                }
            }
            catch
            {
                if (preview != null)
                    preview.Dispose();
                return;
            }

            resizePreview = preview;
            resizePreviewActive = true;

            resizeHeaderHeight = ScaleDesign(headerHeight);
            UpdatePresentMode();
            resizePreviewControls.Clear();
            foreach (Control child in Controls)
            {
                if (!child.Visible)
                    continue;
                resizePreviewControls.Add(child);
                child.Visible = false;
            }
            Invalidate();
        }

        private void EndResizePreview()
        {
            if (!resizePreviewActive)
                return;

            try
            {
                float finalScale = Math.Max(MinimumUiScale,
                    ClientSize.Width / (float)Math.Max(1, designClientSize.Width));
                ApplyUniformScale(finalScale);
            }
            finally
            {
                resizePreviewActive = false;
                UpdatePresentMode();
                foreach (Control child in resizePreviewControls)
                    child.Visible = true;
                resizePreviewControls.Clear();

                if (resizePreview != null)
                {
                    resizePreview.Dispose();
                    resizePreview = null;
                }


                if (!operationRunning)
                    RefreshStatus();
                Invalidate(true);
                foreach (Control child in Controls)
                    child.Invalidate(true);
                Update();
            }
        }

        private void FitInitialSizeToWorkingArea()
        {
            if (initialFitApplied)
                return;
            initialFitApplied = true;

            Rectangle workArea = Screen.FromHandle(Handle).WorkingArea;
            int nonClientWidth = Math.Max(0, Width - ClientSize.Width);
            int nonClientHeight = Math.Max(0, Height - ClientSize.Height);

            // The user's approved 1080p composition is a centred 1300x700 window.
            // Scale that physical footprint uniformly from the active monitor's usable
            // dimensions. On ultrawide displays the height becomes the limiting axis,
            // which keeps the patcher comfortably sized instead of stretching with width.
            float referenceUiScale = Math.Min(
                Math.Max(1F, ReferenceWindowWidth - nonClientWidth) /
                    Math.Max(1, designClientSize.Width),
                Math.Max(1F, ReferenceWindowHeight - nonClientHeight) /
                    Math.Max(1, designClientSize.Height));
            float monitorScale = Math.Min(
                workArea.Width / (float)ReferenceWorkingWidth,
                workArea.Height / (float)ReferenceWorkingHeight);
            float startupScale = referenceUiScale * monitorScale;

            // Always retain a small safety margin for the taskbar and unusual aspect ratios.
            float fitScale = Math.Min(
                Math.Max(1F, workArea.Width * 0.94F - nonClientWidth) /
                    Math.Max(1, designClientSize.Width),
                Math.Max(1F, workArea.Height * 0.94F - nonClientHeight) /
                    Math.Max(1, designClientSize.Height));
            startupScale = Math.Min(startupScale, fitScale);
            startupScale = Math.Max(MinimumUiScale, startupScale);

            ClientSize = new Size(
                Math.Max(1, (int)Math.Round(designClientSize.Width * startupScale)),
                Math.Max(1, (int)Math.Round(designClientSize.Height * startupScale)));
            Location = new Point(
                workArea.Left + Math.Max(0, (workArea.Width - Width) / 2),
                workArea.Top + Math.Max(0, (workArea.Height - Height) / 2));

            // The initial fit changes every control after the first shown frame. Repaint
            // the resolved state immediately so the recovery panel never waits for a click.
            if (!operationRunning)
                RefreshStatus();
            Refresh();
        }

        private void CaptureDesignLayout(Control parent)
        {
            foreach (Control child in parent.Controls)
            {
                designBounds[child] = child.Bounds;
                if (child is Label || child is LinkLabel || child is ComboBox || child is TextBox ||
                    child is StateLabel)
                    designFonts[child] = new FontTemplate(child.Font);
                CaptureDesignLayout(child);
            }
        }

        private void ApplyUniformScale(float scale)
        {
            uiScale = Math.Max(MinimumUiScale, scale);
            SuspendLayoutTree(this);
            try
            {
                bool updateNativeFonts = Math.Abs(uiScale - nativeFontScale) >= 0.01F;
                ApplyControlScale(this, uiScale, updateNativeFonts);
                if (updateNativeFonts)
                    nativeFontScale = uiScale;
                if (taglineFont != null)
                {
                    taglineFont.Dispose();
                    taglineFont = null;
                }
            }
            finally
            {
                ResumeLayoutTree(this);
                Invalidate(true);
            }
        }

        private void ApplyControlScale(Control parent, float scale, bool updateNativeFonts)
        {
            foreach (Control child in parent.Controls)
            {
                FontTemplate template;
                if (updateNativeFonts && designFonts.TryGetValue(child, out template))
                {
                    Font replacement = template.Create(scale);
                    Font previous;
                    child.Font = replacement;
                    if (scaledFonts.TryGetValue(child, out previous))
                        retiredFonts.Add(previous);
                    scaledFonts[child] = replacement;
                }

                Rectangle logical;
                if (designBounds.TryGetValue(child, out logical))
                {
                    child.SetBounds(
                        (int)Math.Round(logical.X * scale),
                        (int)Math.Round(logical.Y * scale),
                        Math.Max(1, (int)Math.Round(logical.Width * scale)),
                        Math.Max(1, (int)Math.Round(logical.Height * scale)));
                }

                CardPanel cardPanel = child as CardPanel;
                if (cardPanel != null)
                    cardPanel.UiScale = scale;
                StepRow stepRow = child as StepRow;
                if (stepRow != null)
                    stepRow.UiScale = scale;
                PillButton pillButton = child as PillButton;
                if (pillButton != null)
                    pillButton.UiScale = scale;
                DarkCombo darkCombo = child as DarkCombo;
                if (darkCombo != null)
                    darkCombo.SetUiScale(scale);
                StateLabel stateLabel = child as StateLabel;
                if (stateLabel != null)
                    stateLabel.UiScale = scale;

                ApplyControlScale(child, scale, updateNativeFonts);
            }

            if (retiredFonts.Count > 0)
            {
                fontRetireTimer.Stop();
                fontRetireTimer.Start();
            }
        }

        private static void SuspendLayoutTree(Control parent)
        {
            parent.SuspendLayout();
            foreach (Control child in parent.Controls)
                SuspendLayoutTree(child);
        }

        private static void ResumeLayoutTree(Control parent)
        {
            foreach (Control child in parent.Controls)
                ResumeLayoutTree(child);
            parent.ResumeLayout(false);
        }

        private void DisposeRetiredFonts()
        {
            foreach (Font font in retiredFonts)
                font.Dispose();
            retiredFonts.Clear();
        }

        /// <summary>Generates frames on a private thread and hands each finished surface to
        /// the UI thread to blit. Everything expensive -- the noise, the upscale, the mote
        /// sprites -- happens here, so the UI thread cost of a frame is one opaque blit
        /// rather than the whole render.
        ///
        /// Timing comes from a Stopwatch, not Environment.TickCount. TickCount advances in
        /// ~15.6 ms steps, so at a 62 ms frame it quantises the delta by nearly a quarter
        /// and the plume pulses.</summary>
        private void RenderLoop()
        {
            Stopwatch clock = Stopwatch.StartNew();
            double last = 0;
            while (renderRunning)
            {
                double now = clock.Elapsed.TotalSeconds;
                float seconds = (float)Math.Min(0.25, Math.Max(0.0, now - last));
                last = now;

                int w = desiredHeaderW, h = desiredHeaderH;
                if (w > 0 && h > 0)
                {
                    try
                    {
                        light.Step(seconds);
                        if (headerBack == null || headerBack.Width != w || headerBack.Height != h)
                        {
                            if (headerBack != null)
                                headerBack.Dispose();
                            headerBack = new Bitmap(w, h, PixelFormat.Format32bppPArgb);
                        }
                        using (Graphics g = Graphics.FromImage(headerBack))
                        {
                            g.Clear(UiTheme.Window);
                            light.Render(g, new Rectangle(0, 0, w, h));
                            // The frame leaves this thread complete, so presenting it is a
                            // single opaque blit with nothing left for the UI thread to
                            // draw on top.
                            lock (overlayLock)
                            {
                                if (headerOverlay != null)
                                {
                                    if (headerOverlay.Width == w && headerOverlay.Height == h)
                                        g.DrawImageUnscaled(headerOverlay, 0, 0);
                                    else
                                    {
                                        g.InterpolationMode = InterpolationMode.HighQualityBilinear;
                                        g.DrawImage(headerOverlay, 0, 0, w, h);
                                    }
                                }
                            }
                        }
                        // The surfaces are swapped, never shared: the UI thread reads the
                        // front while this thread draws the back.
                        lock (headerSwap)
                        {
                            Bitmap spare = headerFront;
                            headerFront = headerBack;
                            headerBack = spare;
                        }
                        IntPtr hwnd = presentHwnd;
                        if (allowDirectPresent && hwnd != IntPtr.Zero)
                            PresentDirect(hwnd, w, h);
                        else if (IsHandleCreated && !IsDisposed)
                            BeginInvoke((MethodInvoker)PresentHeader);
                    }
                    catch
                    {
                        // The handle can disappear mid-frame while closing. The loop exits
                        // on renderRunning either way.
                    }
                }

                double spent = (clock.Elapsed.TotalSeconds - now) * 1000.0;
                int rest = (int)Math.Round(AnimationIntervalMs - spent);
                System.Threading.Thread.Sleep(rest > 1 ? rest : 1);
            }
        }

        /// <summary>Blits the finished frame straight to the window from the render
        /// thread, bypassing the message queue entirely. Legal from a non-UI thread: this
        /// takes its own device context for the window and draws one opaque bitmap into it.
        /// It is serialised against the UI thread through the same lock the surfaces are
        /// swapped under, so the two never draw at once. Disabled while a resize preview is
        /// up, where the UI thread owns the frame, and while minimised.</summary>
        private void PresentDirect(IntPtr hwnd, int w, int h)
        {
            try
            {
                lock (headerSwap)
                {
                    if (headerFront == null)
                        return;
                    using (Graphics g = Graphics.FromHwnd(hwnd))
                    {
                        g.CompositingMode = CompositingMode.SourceCopy;
                        g.DrawImageUnscaled(headerFront, 0, 0);
                    }
                }
            }
            catch
            {
                // The window can be destroyed underneath this; the next frame re-checks.
            }
        }

        /// <summary>Bakes the brand and tagline onto transparency at the current header
        /// size. Runs on the UI thread because it needs the scaled artwork and the fonts;
        /// the render thread only composites the result.</summary>
        private void EnsureHeaderOverlay(int w, int h)
        {
            if (w < 1 || h < 1)
                return;
            lock (overlayLock)
            {
                if (headerOverlay != null && headerOverlay.Width == w && headerOverlay.Height == h)
                    return;
            }
            Bitmap baked = null;
            try
            {
                baked = new Bitmap(w, h, PixelFormat.Format32bppArgb);
                using (Graphics g = Graphics.FromImage(baked))
                {
                    g.Clear(Color.Transparent);
                    g.SmoothingMode = SmoothingMode.AntiAlias;
                    // Not ClearType: subpixel hinting against transparency leaves coloured
                    // fringes once the layer is composited.
                    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                    PaintBrandLayer(g, w);
                }
            }
            catch
            {
                if (baked != null)
                {
                    baked.Dispose();
                    baked = null;
                }
            }
            if (baked == null)
                return;
            lock (overlayLock)
            {
                if (headerOverlay != null)
                    headerOverlay.Dispose();
                headerOverlay = baked;
            }
        }

        /// <summary>Direct presentation is off while the UI thread owns the frame -- during
        /// a resize preview -- and while minimised.</summary>
        private void UpdatePresentMode()
        {
            allowDirectPresent = !resizePreviewActive
                && WindowState != FormWindowState.Minimized
                && !IsDisposed;
        }

        /// <summary>Runs on the UI thread when a frame is ready. Update() rather than
        /// waiting for WM_PAINT, which is the lowest priority message there is and would be
        /// starved by the same wheel-message flood this design exists to survive.</summary>
        private void PresentHeader()
        {
            if (IsDisposed || Disposing || WindowState == FormWindowState.Minimized)
                return;
            Invalidate(new Rectangle(0, 0, ClientSize.Width, LiveHeaderHeight()));
            Update();
        }

        /// <summary>Blits the most recent finished frame, and tells the render thread what
        /// size to produce next. SourceCopy because the surface is opaque -- it carries its
        /// own background -- which makes this a straight copy rather than an alpha blend.</summary>
        private void BlitHeader(Graphics g, Rectangle area)
        {
            desiredHeaderW = Math.Max(1, area.Width);
            desiredHeaderH = Math.Max(1, area.Height);
            lock (headerSwap)
            {
                if (headerFront == null)
                {
                    using (SolidBrush back = new SolidBrush(UiTheme.Window))
                        g.FillRectangle(back, area);
                    return;
                }
                CompositingMode previousMode = g.CompositingMode;
                InterpolationMode previousInterp = g.InterpolationMode;
                g.CompositingMode = CompositingMode.SourceCopy;
                if (headerFront.Width == area.Width && headerFront.Height == area.Height)
                {
                    g.DrawImageUnscaled(headerFront, area.X, area.Y);
                }
                else
                {
                    // Only transiently, while the render thread catches up with a resize.
                    g.InterpolationMode = InterpolationMode.Bilinear;
                    g.DrawImage(headerFront, area);
                }
                g.CompositingMode = previousMode;
                g.InterpolationMode = previousInterp;
            }
        }

        /// <summary>Height of the header as it is currently being painted. While a resize
        /// preview is up, uiScale still holds its pre-resize value and the snapshot is
        /// being stretched, so the header's on-screen height is the captured height scaled
        /// by how far the window has been dragged -- which can be taller than the capture.
        /// Invalidating the captured height instead would leave a stale band behind when
        /// the window grows.</summary>
        private int LiveHeaderHeight()
        {
            if (resizePreviewActive && resizePreview != null && resizePreview.Height > 0)
                return Math.Max(1, (int)Math.Round(
                    resizeHeaderHeight * (double)ClientSize.Height / resizePreview.Height));
            return ScaleDesign(headerHeight);
        }

        /// <summary>Moves a step in design space and applies it at the current scale.
        /// The design rectangle is the source of truth -- ApplyControlScale restores every
        /// control from it on each rescale -- so moving a control means moving that, not
        /// just its live bounds.</summary>
        private void PlaceStep(Control step, int designTop)
        {
            Rectangle logical;
            if (!designBounds.TryGetValue(step, out logical))
                return;
            if (logical.Y != designTop)
            {
                logical.Y = designTop;
                designBounds[step] = logical;
            }
            step.SetBounds(
                (int)Math.Round(logical.X * uiScale),
                (int)Math.Round(logical.Y * uiScale),
                Math.Max(1, (int)Math.Round(logical.Width * uiScale)),
                Math.Max(1, (int)Math.Round(logical.Height * uiScale)));
        }

        private int ScaleDesign(int value)
        {
            return Math.Max(1, (int)Math.Round(value * uiScale));
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                fontRetireTimer.Stop();
                fontRetireTimer.Dispose();
                DisposeRetiredFonts();
                foreach (Font font in scaledFonts.Values)
                    font.Dispose();
                scaledFonts.Clear();
                if (taglineFont != null)
                    taglineFont.Dispose();
                renderRunning = false;
                if (renderThread != null)
                {
                    renderThread.Join(500);
                    renderThread = null;
                }
                lock (headerSwap)
                {
                    if (headerFront != null) { headerFront.Dispose(); headerFront = null; }
                    if (headerBack != null) { headerBack.Dispose(); headerBack = null; }
                }
                rowBrush.Dispose();
                rowSelectedBrush.Dispose();
                light.Dispose();
                if (scaledBrand != null)
                    scaledBrand.Dispose();
                if (brand != null)
                    brand.Dispose();
                if (resizePreview != null)
                    resizePreview.Dispose();
                lock (overlayLock)
                {
                    if (headerOverlay != null) { headerOverlay.Dispose(); headerOverlay = null; }
                }
            }
            base.Dispose(disposing);
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

        private static StateLabel NewStateLabel(StepRow row, int cardWidth)
        {
            StateLabel label = new StateLabel();
            label.Font = UiTheme.DisplayFont(18F, FontStyle.Bold);
            label.ForeColor = UiTheme.TextMuted;
            // Tall enough for the icon-only badge; still centred on the header centre
            // line, so the text states sit exactly where they did.
            label.SetBounds(cardWidth - 340, 20, 300, 56);
            label.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            row.Controls.Add(label);
            return label;
        }

        private readonly SolidBrush rowBrush = new SolidBrush(UiTheme.Field);
        private readonly SolidBrush rowSelectedBrush = new SolidBrush(UiTheme.AccentDark);

        private void ResolutionDrawItem(object sender, DrawItemEventArgs e)
        {
            if (e.Index < 0)
                return;
            bool selected = (e.State & DrawItemState.Selected) == DrawItemState.Selected;
            // Cached brushes: a wheel notch repaints several rows, and allocating and
            // finalising a GDI+ brush per row adds up while the list is being scrolled
            // fast enough to back the message queue up.
            e.Graphics.FillRectangle(selected ? rowSelectedBrush : rowBrush, e.Bounds);
            int leftPadding = Math.Max(2, (int)Math.Round(10 * uiScale));
            int rightPadding = Math.Max(2, (int)Math.Round(12 * uiScale));
            Rectangle textBounds = new Rectangle(
                e.Bounds.X + leftPadding,
                e.Bounds.Y,
                Math.Max(1, e.Bounds.Width - leftPadding - rightPadding),
                e.Bounds.Height);
            TextRenderer.DrawText(e.Graphics,
                resolutionBox.Items[e.Index].ToString(),
                e.Font,
                textBounds,
                UiTheme.Text,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter |
                TextFormatFlags.SingleLine | TextFormatFlags.NoPadding |
                TextFormatFlags.NoPrefix);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            if (resizePreviewActive && resizePreview != null)
            {
                e.Graphics.CompositingMode = CompositingMode.SourceCopy;
                e.Graphics.CompositingQuality = CompositingQuality.HighSpeed;
                e.Graphics.InterpolationMode = InterpolationMode.Bilinear;
                e.Graphics.PixelOffsetMode = PixelOffsetMode.HighSpeed;
                e.Graphics.DrawImage(resizePreview, ClientRectangle,
                    0, 0, resizePreview.Width, resizePreview.Height, GraphicsUnit.Pixel);

                // The snapshot exists because re-laying out the card's child controls on
                // every mouse move is expensive. The header has no child controls at all,
                // so it can be repainted live over the frozen frame: background, plume,
                // then the brand layer baked when the resize began. Stretching that layer
                // costs one bilinear blit, where rebuilding it would mean a bicubic
                // resample of the artwork per frame -- the thing the brand cache exists
                // to avoid.
                if (resizePreview.Height > 0)
                {
                    // An exception thrown out of a paint handler mid-drag would surface as
                    // a JIT dialog, so a failure here just leaves the plain frozen snapshot.
                    try
                    {
                        int headerNow = LiveHeaderHeight();
                        if (headerNow > 0)
                        {
                            Rectangle live = new Rectangle(0, 0, ClientSize.Width, headerNow);
                            GraphicsState held = e.Graphics.Save();
                            e.Graphics.SetClip(live);
                            BlitHeader(e.Graphics, live);
                            e.Graphics.Restore(held);
                        }
                    }
                    catch { }
                }
                return;
            }

            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

            // No gradient behind the header: the only fade in this area should be the
            // crest's own, baked into the artwork. A background ramp read as a second,
            // competing fade.

            // Drifting haze, painted first so it passes behind the crest and the wordmark
            // rather than over them. Clipped to the header strip: below it the card covers
            // everything anyway, so drawing there would only be wasted upscaling.
            Rectangle header = new Rectangle(0, 0, ClientSize.Width, ScaleDesign(headerHeight));
            EnsureHeaderOverlay(header.Width, header.Height);
            UpdatePresentMode();
            // The frame already contains the brand and tagline: the render thread composites
            // them, so a repaint here is one blit rather than a re-render of the lockup.
            BlitHeader(g, header);
        }

        /// <summary>The brand lockup and tagline, without the background or the plume.
        /// Split out so the resize path can bake exactly this into a transparent layer
        /// and composite it over live smoke.</summary>
        private void PaintBrandLayer(Graphics g, int clientWidth)
        {
            // The crest and the metallic wordmark are one baked lockup, so the crest's
            // fade lines up with the letters exactly as it was composed.
            int scaledBrandWidth = Math.Max(1, (int)Math.Round(brandWidth * uiScale));
            int scaledBrandHeight = Math.Max(1, (int)Math.Round(brandHeight * uiScale));
            int brandTop = Math.Max(1, (int)Math.Round(14 * uiScale));
            int taglineTop = Math.Max(1, (int)Math.Round(30 * uiScale));
            if (brand != null)
            {
                if (scaledBrand == null || scaledBrand.Width != scaledBrandWidth
                    || scaledBrand.Height != scaledBrandHeight)
                {
                    if (scaledBrand != null)
                        scaledBrand.Dispose();
                    scaledBrand = new Bitmap(scaledBrandWidth, scaledBrandHeight,
                        PixelFormat.Format32bppArgb);
                    using (Graphics bg = Graphics.FromImage(scaledBrand))
                    {
                        bg.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        bg.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        bg.DrawImage(brand, 0, 0, scaledBrandWidth, scaledBrandHeight);
                    }
                }
                g.DrawImageUnscaled(scaledBrand, (clientWidth - scaledBrandWidth) / 2, brandTop);
                taglineTop = brandTop + scaledBrandHeight + Math.Max(1, (int)Math.Round(2 * uiScale));
            }

            // The tagline is set to the width of the wordmark's ink, not the width of the
            // brand image: the artwork carries transparent margin and glow past the last
            // letter, so matching the image would leave the tagline visibly wider.
            // GenericTypographic, not the default: the default format pads either side of
            // the string, so measuring with it makes the tagline come out ~3% narrow and
            // off-centre. Typographic reports the glyphs themselves.
            using (StringFormat sf = new StringFormat(StringFormat.GenericTypographic))
            using (SolidBrush ink = new SolidBrush(UiTheme.Accent))
            {
                sf.Alignment = StringAlignment.Center;
                sf.FormatFlags |= StringFormatFlags.NoWrap;

                if (taglineFont == null)
                {
                    double target = (WordmarkInkRight - WordmarkInkLeft) * scaledBrandWidth;
                    using (Font probe = new Font("Segoe UI", Math.Max(6F, 20F * uiScale), FontStyle.Bold))
                    {
                        float measured = g.MeasureString(Tagline, probe, Int32.MaxValue, sf).Width;
                        float size = measured > 1F
                            ? (float)(20.0 * uiScale * target / measured)
                            : 10.5F * uiScale;
                        taglineFont = new Font("Segoe UI", Math.Max(6F, size), FontStyle.Bold);
                    }
                }

                g.DrawString(Tagline, taglineFont, ink,
                    new RectangleF(0, taglineTop, clientWidth,
                        taglineFont.Height + Math.Max(2, (int)Math.Round(8 * uiScale))), sf);
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

        private void OpenEditableExecutablePage()
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = EditableExeUrl;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open the download page",
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

        private void SetState(StateLabel label, string text, Color color)
        {
            label.Badge = StateLabel.StatusBadge.None;
            label.Text = text;
            label.ForeColor = color;
        }

        private void UpdateVerificationRecovery(ExecutableState state, string target, bool executableReady)
        {
            bool needsRecovery = !executableReady;
            verificationRecovery.Visible = needsRecovery;
            // Step 3 stays in the flow while the executable is unresolved, dimmed and
            // without its dropdown, so the card does not collapse into a different,
            // shorter product. Step 4 has no room, and the action button below already
            // stands for it.
            stepResolution.Visible = true;
            stepResolution.Dimmed = needsRecovery;
            resolutionBox.Visible = executableReady;
            stepApply.Visible = executableReady;

            int verifyHeight = needsRecovery
                ? StepRow.HeaderHeight + 67
                : StepRow.HeaderHeight;
            stepVerify.Height = ScaleDesign(verifyHeight);
            PlaceStep(stepResolution, StepRow.HeaderHeight + verifyHeight);

            if (!needsRecovery)
            {
                stepVerify.SetSubtitle(state == ExecutableState.Gold
                    ? "KOTOR Modern Restoration Patch detected."
                    : "Compatible editable executable detected.");
                stepVerify.Invalidate();
                return;
            }


            // One line, on the step's own subtitle. This used to be three stacked
            // restatements -- the subtitle, a heading, and a path line -- which made the
            // step tall enough to push the rest of the flow off the card.
            if (state == ExecutableState.Missing)
                stepVerify.SetSubtitle("Download the editable swkotor.exe, then choose it here.");
            else if (state == ExecutableState.Unsupported)
                stepVerify.SetSubtitle("This copy cannot be patched. Replace it, then check again.");
            else
                stepVerify.SetSubtitle("This file could not be read. Choose another swkotor.exe.");

            stepVerify.Invalidate();
        }

        private void RefreshStatus()
        {
            if (actionButton == null || applyState == null)
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
            actionIsRestore = PatchOperations.CanRestore(target);
            actionButton.Text = actionIsRestore ? "Restore Original" : "Start Patching";
            actionButton.Enabled = actionIsRestore || (executableReady && iniExists);

            if (state == ExecutableState.SupportedClean || state == ExecutableState.Gold)
            {
                SetState(verifyState, "Verified", UiTheme.Success);
                verifyState.Badge = StateLabel.StatusBadge.Verified;
            }
            else
            {
                // Every unresolved state carries the missing badge: the chip beside it
                // says which one it is, and the badge says the step is not satisfied.
                // No words here: the badge alone marks the step unsatisfied, and the
                // step's own subtitle already says which failure it is and what to do.
                SetState(verifyState, String.Empty,
                    state == ExecutableState.Error ? UiTheme.Error : UiTheme.Warning);
                verifyState.Badge = StateLabel.StatusBadge.Missing;
            }

            UpdateVerificationRecovery(state, target, executableReady);

            bool patchComplete = state == ExecutableState.Gold;
            stepFolder.SetTitle(patchComplete ? "1. Selected Game Folder" : "1. Select Game Folder");
            stepVerify.SetTitle(patchComplete ? "2. Verified Editable EXE" : "2. Verify Editable EXE");
            stepResolution.SetTitle(patchComplete ? "3. Chosen Resolution" : "3. Choose Resolution");
            stepResolution.SetSubtitle(patchComplete
                ? "Installed resolution."
                : "Select the resolution you want to patch for.");
            // Also gated on the executable: step 3 is shown dimmed while verification is
            // outstanding, and a live dropdown inside a dimmed row invites a click that
            // does nothing.
            resolutionBox.Visible = !patchComplete && executableReady;
            resolutionState.Visible = patchComplete;

            if (patchComplete)
            {
                int installedWidth;
                int installedHeight;
                if (PatchOperations.TryReadInstalledResolution(target, out installedWidth, out installedHeight))
                {
                    SetState(resolutionState,
                        installedWidth.ToString(CultureInfo.InvariantCulture) + " × " +
                        installedHeight.ToString(CultureInfo.InvariantCulture), UiTheme.Text);
                }
                else
                {
                    ResolutionChoice selected = resolutionBox.SelectedItem as ResolutionChoice;
                    SetState(resolutionState, selected == null ? "Installed" :
                        selected.Width.ToString(CultureInfo.InvariantCulture) + " × " +
                        selected.Height.ToString(CultureInfo.InvariantCulture), UiTheme.Text);
                }
            }
            else
            {
                resolutionState.Text = String.Empty;
            }

            if (state == ExecutableState.Gold)
            {
                SetState(applyState, "Patched successfully", UiTheme.Success);
                int readyWidth;
                int readyHeight;
                lastDetail = PatchOperations.TryReadInstalledResolution(target, out readyWidth, out readyHeight)
                    ? "KOTOR is ready to play at " +
                        readyWidth.ToString(CultureInfo.InvariantCulture) + " × " +
                        readyHeight.ToString(CultureInfo.InvariantCulture) + "."
                    : "KOTOR is ready to play.";
            }
            else if (executableReady && iniExists)
            {
                SetState(applyState, "Ready to patch", UiTheme.Accent);
                lastDetail = "Everything is ready. Start patching when ready.";
            }
            else if (executableReady)
            {
                SetState(applyState, "Game setup needed", UiTheme.Warning);
                lastDetail = "Launch KOTOR once, close it, then return here and check again.";
            }
            else
            {
                SetState(applyState, "Not patched", UiTheme.TextMuted);
                lastDetail = PatchOperations.Describe(target);
            }
            stepApply.SetSubtitle(lastDetail);
        }

        private void ActionClicked(object sender, EventArgs e)
        {
            if (actionIsRestore)
                RestoreClicked(sender, e);
            else
                PatchClicked(sender, e);
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
            actionButton.ProgressPercent = 0;
            actionButton.Text = name == "Patch" ? "Preparing patch…   0%" : "Preparing restore…   0%";
            operationRunning = true;
            SetBusyState(true);
            SetState(applyState, name == "Patch" ? "Patching…" : "Restoring…", UiTheme.Accent);
            stepApply.SetSubtitle(name == "Patch"
                ? "KMRP is updating your game. Please wait."
                : "KMRP is restoring your original files. Please wait.");

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
                actionButton.ProgressPercent = percent;
                string message = e.UserState as string;
                actionButton.Text = (String.IsNullOrWhiteSpace(message) ? "Working…" : message) +
                    "   " + percent.ToString(CultureInfo.InvariantCulture) + "%";
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
            {
                actionButton.ProgressPercent = -1;
                operationRunning = false;
                SetBusyState(false);

                if (e.Error != null)
                {
                    RefreshStatus();
                    SetState(applyState, "Error", UiTheme.Error);
                    stepApply.SetSubtitle(name + " stopped — no incomplete changes were left behind.");
                    try { PatchOperations.AppendLog(target, name + " failed: " + e.Error); } catch { }
                    MessageBox.Show(this, e.Error.Message, name + " blocked", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                string result = e.Result as string;
                RefreshStatus();
                SetState(applyState, name == "Patch" ? "Patched successfully" : "Restored successfully", UiTheme.Success);
                stepApply.SetSubtitle(result ?? (name + " completed."));
            };
            worker.RunWorkerAsync();
        }

        private void SetBusyState(bool busy)
        {
            resolutionBox.Enabled = !busy;
            browseButton.Enabled = !busy;
            actionButton.Enabled = !busy;
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
