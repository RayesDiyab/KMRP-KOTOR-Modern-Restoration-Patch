using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using Microsoft.Win32;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace Kmrp
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
            if (GoldPatch.HashBytes(normalized) != GoldPatch.SourceHash)
            {
                normalized = null;
                return false;
            }
            return true;
        }

    }

    internal sealed class GoldPatch
    {
        internal const string ResourceName = "Kmrp.goldpatch";
        internal const string SourceHash = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886";
        internal const string TargetHash = "9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A";
        internal const long SourceLength = 4042752;
        internal const long TargetLength = 4087808;
        internal const string PatchVersion = "1.5.0";

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
            byte[] normalizedSource;
            if (!PeCompatibility.TryNormalizeSupportedSource(source, out normalizedSource))
                throw new InvalidDataException("The selected file is not the supported unpatched swkotor.exe.");
            if (resolution == null)
                throw new ArgumentNullException("resolution");

            byte[] target = new byte[TargetLength];
            Buffer.BlockCopy(normalizedSource, 0, target, 0, normalizedSource.Length);
            foreach (PatchChunk chunk in chunks)
                Buffer.BlockCopy(chunk.Data, 0, target, checked((int)chunk.Offset), chunk.Data.Length);

            if (HashBytes(target) != TargetHash)
                throw new InvalidDataException("The game update could not be verified.");
            ResolutionPatch.Apply(target, resolution);
            // The map-note corrections are data in .kmn plus a lookup the wrapper always
            // calls; the flag is what decides whether the lookup does anything. Gold ships
            // it enabled, so this only ever has to clear it.
            if (!KmrpSettings.MarkerFixes)
                ResolutionPatch.WriteInt32(target, ResolutionPatch.MapNoteFlagOffset, 0);
            return target;
        }

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
        private const string ResourceName = "Kmrp.resolutions";

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
        private static readonly long[] MovieWidthOffsets = { 0x00003D6C, 0x001F5B3B };
        private static readonly long[] MovieHeightOffsets = { 0x00003D78, 0x001F5B43 };

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

        private static void ReplaceSByte(byte[] data, long offset, int expected, int replacement, string label)
        {
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
            byte[] encoded = BitConverter.GetBytes(value);
            Buffer.BlockCopy(encoded, 0, data, checked((int)offset), encoded.Length);
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

    internal sealed class DpiCompatibilityEditState
    {
        internal string ExecutablePath;
        internal bool HadRegistryValue;
        internal string RegistryValue;
        internal bool HadManifest;
        internal byte[] ManifestBytes;
        internal bool Changed;
    }

    /// <summary>Opts the game executable out of Windows DPI virtualization.
    ///
    /// KMRP already scales KOTOR's interface for the selected framebuffer. If Windows
    /// applies its own compatibility scaling on top, a 3840x2160 game at 150% desktop
    /// scaling is rendered as though its usable surface were smaller and the UI appears
    /// zoomed. The Properties -> Compatibility -> High DPI override -> Application fix
    /// writes HIGHDPIAWARE to this per-user AppCompat value.
    ///
    /// A sidecar preserves the exact value that existed before KMRP added its token.
    /// Restore changes the registry only while it still equals the value KMRP wrote;
    /// a later user or Windows change is left untouched.</summary>
    internal static class DpiCompatibilityOperations
    {
        private const string LayersKeyPath = @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers";
        private const string Token = "HIGHDPIAWARE";
        private const string ManifestHeader = "KMRPDPI1";
        private const string ManifestName = "KMRP_DPI.manifest";

        private sealed class DpiRecord
        {
            internal string ExecutablePath;
            internal bool HadPreviousValue;
            internal string PreviousValue;
            internal string InstalledValue;
        }

        private static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), ManifestName);
        }

        internal static DpiCompatibilityEditState Install(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            DpiCompatibilityEditState state = new DpiCompatibilityEditState();
            state.ExecutablePath = executablePath;
            state.HadManifest = File.Exists(manifestPath);
            state.ManifestBytes = state.HadManifest ? File.ReadAllBytes(manifestPath) : null;

            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
                {
                    if (key == null)
                        throw new IOException("The Windows compatibility settings key could not be opened.");

                    object raw = key.GetValue(executablePath, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                    state.HadRegistryValue = raw != null;
                    state.RegistryValue = raw as string;
                    if (raw != null && state.RegistryValue == null)
                        throw new InvalidDataException("The existing Windows compatibility setting is not a string value.");

                    if (ContainsToken(state.RegistryValue, Token))
                    {
                        SafeReport(report, "Verified the Windows high-DPI application override for swkotor.exe.");
                        return state;
                    }

                    string installed = AppendToken(state.RegistryValue, Token);
                    DpiRecord record = new DpiRecord();
                    record.ExecutablePath = executablePath;
                    record.HadPreviousValue = state.HadRegistryValue;
                    record.PreviousValue = state.RegistryValue ?? String.Empty;
                    record.InstalledValue = installed;

                    try
                    {
                        key.SetValue(executablePath, installed, RegistryValueKind.String);
                        object verified = key.GetValue(executablePath, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                        if (!String.Equals(verified as string, installed, StringComparison.Ordinal))
                            throw new IOException("The Windows high-DPI compatibility setting could not be verified.");
                        WriteManifest(manifestPath, record);
                    }
                    catch
                    {
                        RestoreRegistryValue(key, executablePath, state.HadRegistryValue, state.RegistryValue);
                        throw;
                    }
                    state.Changed = true;
                    SafeReport(report, "Enabled the Windows high-DPI application override for swkotor.exe.");
                    return state;
                }
            }
            catch (UnauthorizedAccessException ex)
            {
                SafeReport(report, "Windows high-DPI handling could not be configured automatically: " + ex.Message +
                    " Set swkotor.exe Compatibility -> High DPI scaling override to Application.");
                return state;
            }
            catch (System.Security.SecurityException ex)
            {
                SafeReport(report, "Windows high-DPI handling could not be configured automatically: " + ex.Message +
                    " Set swkotor.exe Compatibility -> High DPI scaling override to Application.");
                return state;
            }
        }

        internal static void Rollback(DpiCompatibilityEditState state)
        {
            if (state == null || !state.Changed)
                return;
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
            {
                if (key == null)
                    throw new IOException("The Windows compatibility settings key could not be opened for rollback.");
                RestoreRegistryValue(key, state.ExecutablePath, state.HadRegistryValue, state.RegistryValue);
            }
            string manifestPath = ManifestPath(state.ExecutablePath);
            if (state.HadManifest)
                File.WriteAllBytes(manifestPath, state.ManifestBytes);
            else if (File.Exists(manifestPath))
                File.Delete(manifestPath);
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            DpiRecord record = ReadManifest(manifestPath);
            if (!String.Equals(record.ExecutablePath, executablePath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The Windows high-DPI manifest belongs to a different executable path.");

            bool restored = false;
            bool kept = false;
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
            {
                if (key == null)
                    throw new IOException("The Windows compatibility settings key could not be opened for restore.");
                object raw = key.GetValue(executablePath, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                string current = raw as string;
                if (raw != null && current == null)
                {
                    kept = true;
                }
                else if (String.Equals(current, record.InstalledValue, StringComparison.Ordinal))
                {
                    RestoreRegistryValue(key, executablePath, record.HadPreviousValue, record.PreviousValue);
                    restored = true;
                }
                else
                {
                    kept = true;
                }
            }

            File.Delete(manifestPath);
            if (restored)
                SafeReport(report, "Restored the previous Windows high-DPI compatibility setting.");
            if (kept)
                SafeReport(report, "Left the Windows high-DPI compatibility setting in place because it changed after install.");
        }

        private static bool ContainsToken(string value, string token)
        {
            if (String.IsNullOrWhiteSpace(value))
                return false;
            foreach (string part in Regex.Split(value.Trim(), "\\s+"))
                if (String.Equals(part, token, StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        private static string AppendToken(string value, string token)
        {
            if (String.IsNullOrWhiteSpace(value))
                return token;
            return value.TrimEnd() + " " + token;
        }

        private static void RestoreRegistryValue(RegistryKey key, string name, bool hadValue, string value)
        {
            if (hadValue)
                key.SetValue(name, value ?? String.Empty, RegistryValueKind.String);
            else
                key.DeleteValue(name, false);
        }

        private static void WriteManifest(string path, DpiRecord record)
        {
            string text = ManifestHeader + "\r\n" +
                Encode(record.ExecutablePath) + "\r\n" +
                (record.HadPreviousValue ? "1" : "0") + "\r\n" +
                Encode(record.PreviousValue) + "\r\n" +
                Encode(record.InstalledValue) + "\r\n";
            File.WriteAllText(path, text, new UTF8Encoding(false));
        }

        private static DpiRecord ReadManifest(string path)
        {
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            if (lines.Length != 5 || lines[0] != ManifestHeader ||
                (lines[2] != "0" && lines[2] != "1"))
                throw new InvalidDataException("The Windows high-DPI manifest is invalid. Restore was blocked.");
            DpiRecord record = new DpiRecord();
            record.ExecutablePath = Decode(lines[1]);
            record.HadPreviousValue = lines[2] == "1";
            record.PreviousValue = Decode(lines[3]);
            record.InstalledValue = Decode(lines[4]);
            if (!ContainsToken(record.InstalledValue, Token))
                throw new InvalidDataException("The Windows high-DPI manifest does not contain the installed setting.");
            return record;
        }

        private static string Encode(string value)
        {
            return Convert.ToBase64String(Encoding.UTF8.GetBytes(value ?? String.Empty));
        }

        private static string Decode(string value)
        {
            try { return Encoding.UTF8.GetString(Convert.FromBase64String(value)); }
            catch (FormatException ex)
            {
                throw new InvalidDataException("The Windows high-DPI manifest contains invalid text.", ex);
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

    /// <summary>The slice of NVIDIA's driver-settings interface (NvAPI DRS) the patcher
    /// uses. Entry points are the documented ones from nvapi_interface.h, fetched through
    /// nvapi_QueryInterface; structures are marshalled by explicit offset from nvapi.h,
    /// where every string is NVAPI_UNICODE_STRING_MAX = 2048 UTF-16 units and every other
    /// field is 32-bit, so the layouts have no padding:
    ///
    ///   NVDRS_SETTING v1      12320 bytes  version 0, settingId 4100, settingType 4104,
    ///                                      settingLocation 4108, currentValue 8220
    ///   NVDRS_APPLICATION v4  20492 bytes  version 0, appName 8
    ///   NVDRS_PROFILE v1       4116 bytes  version 0, profileName 4, numOfApps 4108,
    ///                                      numOfSettings 4112
    ///
    /// A struct's version word is its size | (version &lt;&lt; 16), NVAPI's MAKE_NVAPI_VERSION.</summary>
    internal sealed class NvDrsSession : IDisposable
    {
        internal const int Ok = 0;
        internal const int InvalidUserPrivilege = -137;
        private const int SettingNotFound = -160;
        private const int ProfileNotFound = -163;
        private const int ExecutableNotFound = -166;
        internal const int LocationCurrentProfile = 0;   // NVDRS_CURRENT_PROFILE_LOCATION

        private const int StringBytes = 4096;
        private const int SettingSize = 12320;
        private const int SettingIdOffset = 4100;
        private const int SettingTypeOffset = 4104;
        private const int SettingLocationOffset = 4108;
        private const int SettingCurrentOffset = 8220;
        private const int ApplicationSize = 20492;
        private const int ApplicationNameOffset = 8;
        private const int ProfileSize = 4116;
        private const int ProfileNameOffset = 4;
        private const int ProfileAppsOffset = 4108;
        private const int ProfileSettingsOffset = 4112;

        private const uint LoadLibrarySearchSystem32 = 0x00000800;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryEx(string name, IntPtr reserved, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true)]
        private static extern IntPtr GetProcAddress(IntPtr module, string name);

        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate IntPtr QueryInterfaceFn(uint id);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int NoArgFn();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int HandleOutFn(out IntPtr handle);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int SessionFn(IntPtr session);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int SessionHandleOutFn(IntPtr session, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int FindApplicationFn(IntPtr session, IntPtr appName, out IntPtr profile, IntPtr application);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int FindProfileFn(IntPtr session, IntPtr profileName, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int CreateProfileFn(IntPtr session, IntPtr profileInfo, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int ProfileFn(IntPtr session, IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int ProfileStructFn(IntPtr session, IntPtr profile, IntPtr data);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int GetSettingFn(IntPtr session, IntPtr profile, uint settingId, IntPtr setting);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int DeleteSettingFn(IntPtr session, IntPtr profile, uint settingId);

        private readonly NoArgFn unload;
        private readonly SessionFn destroySession;
        private readonly SessionFn saveSettings;
        private readonly FindApplicationFn findApplication;
        private readonly FindProfileFn findProfile;
        private readonly SessionHandleOutFn globalProfile;
        private readonly CreateProfileFn createProfile;
        private readonly ProfileFn deleteProfile;
        private readonly ProfileStructFn profileInfo;
        private readonly ProfileStructFn createApplication;
        private readonly GetSettingFn getSetting;
        private readonly ProfileStructFn setSetting;
        private readonly DeleteSettingFn deleteSetting;
        private IntPtr session;

        private NvDrsSession(QueryInterfaceFn query)
        {
            unload = Function<NoArgFn>(query, 0xD22BDD7E);
            destroySession = Function<SessionFn>(query, 0xDAD9CFF8);
            saveSettings = Function<SessionFn>(query, 0xFCBC7E14);
            findApplication = Function<FindApplicationFn>(query, 0xEEE566B2);
            findProfile = Function<FindProfileFn>(query, 0x7E4A9A0B);
            globalProfile = Function<SessionHandleOutFn>(query, 0x617BFF9F);
            createProfile = Function<CreateProfileFn>(query, 0xCC176068);
            deleteProfile = Function<ProfileFn>(query, 0x17093206);
            profileInfo = Function<ProfileStructFn>(query, 0x61CD6FD6);
            createApplication = Function<ProfileStructFn>(query, 0x4347A9DE);
            getSetting = Function<GetSettingFn>(query, 0x73BF8338);
            setSetting = Function<ProfileStructFn>(query, 0x577DD202);
            deleteSetting = Function<DeleteSettingFn>(query, 0xE4A26362);
        }

        /// <summary>A loaded driver-settings session, or null with the reason when there is
        /// no NVIDIA driver to talk to. nvapi is loaded from System32 only, never from the
        /// patcher's own folder.</summary>
        internal static NvDrsSession TryOpen(out string unavailable)
        {
            IntPtr module = LoadLibraryEx(IntPtr.Size == 8 ? "nvapi64.dll" : "nvapi.dll",
                IntPtr.Zero, LoadLibrarySearchSystem32);
            if (module == IntPtr.Zero)
            {
                unavailable = "no NVIDIA driver is installed";
                return null;
            }
            IntPtr queryAddress = GetProcAddress(module, "nvapi_QueryInterface");
            if (queryAddress == IntPtr.Zero)
            {
                unavailable = "nvapi has no nvapi_QueryInterface";
                return null;
            }
            QueryInterfaceFn query = (QueryInterfaceFn)Marshal.GetDelegateForFunctionPointer(
                queryAddress, typeof(QueryInterfaceFn));
            NoArgFn initialize = Function<NoArgFn>(query, 0x0150E828);
            int status = initialize();
            if (status != Ok)
            {
                unavailable = "NvAPI_Initialize returned " + status.ToString(CultureInfo.InvariantCulture);
                return null;
            }
            NvDrsSession drs = new NvDrsSession(query);
            try
            {
                HandleOutFn create = Function<HandleOutFn>(query, 0x0694D52E);
                Check("NvAPI_DRS_CreateSession", create(out drs.session));
                Check("NvAPI_DRS_LoadSettings", Function<SessionFn>(query, 0x375DBD6B)(drs.session));
            }
            catch
            {
                drs.Dispose();
                throw;
            }
            unavailable = null;
            return drs;
        }

        /// <summary>The profile the driver applies to this executable, or zero when no
        /// profile names it. Given a full path, NvAPI answers for that path.</summary>
        internal IntPtr FindApplicationProfile(string executablePath)
        {
            IntPtr name = NewString(executablePath);
            IntPtr application = NewStruct(ApplicationSize, 4);
            try
            {
                IntPtr profile;
                int status = findApplication(session, name, out profile, application);
                if (status == ExecutableNotFound)
                    return IntPtr.Zero;
                Check("NvAPI_DRS_FindApplicationByName", status);
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(name);
                Marshal.FreeHGlobal(application);
            }
        }

        internal IntPtr GlobalProfile()
        {
            IntPtr profile;
            Check("NvAPI_DRS_GetCurrentGlobalProfile", globalProfile(session, out profile));
            return profile;
        }

        internal IntPtr FindProfile(string profileName)
        {
            IntPtr name = NewString(profileName);
            try
            {
                IntPtr profile;
                int status = findProfile(session, name, out profile);
                if (status == ProfileNotFound)
                    return IntPtr.Zero;
                Check("NvAPI_DRS_FindProfileByName", status);
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(name);
            }
        }

        internal IntPtr CreateProfile(string profileName)
        {
            IntPtr info = NewStruct(ProfileSize, 1);
            try
            {
                WriteString(info, ProfileNameOffset, profileName);
                IntPtr profile;
                Check("NvAPI_DRS_CreateProfile", createProfile(session, info, out profile));
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(info);
            }
        }

        internal void DeleteProfile(IntPtr profile)
        {
            Check("NvAPI_DRS_DeleteProfile", deleteProfile(session, profile));
        }

        /// <summary>The profile's name and how many applications and settings it holds.</summary>
        internal void ProfileInfo(IntPtr profile, out string name, out int applications, out int settings)
        {
            IntPtr info = NewStruct(ProfileSize, 1);
            try
            {
                Check("NvAPI_DRS_GetProfileInfo", profileInfo(session, profile, info));
                name = Marshal.PtrToStringUni(new IntPtr(info.ToInt64() + ProfileNameOffset));
                applications = Marshal.ReadInt32(info, ProfileAppsOffset);
                settings = Marshal.ReadInt32(info, ProfileSettingsOffset);
            }
            finally
            {
                Marshal.FreeHGlobal(info);
            }
        }

        internal void AddApplication(IntPtr profile, string applicationName)
        {
            IntPtr application = NewStruct(ApplicationSize, 4);
            try
            {
                WriteString(application, ApplicationNameOffset, applicationName);
                Check("NvAPI_DRS_CreateApplication", createApplication(session, profile, application));
            }
            finally
            {
                Marshal.FreeHGlobal(application);
            }
        }

        /// <summary>The setting's value as the driver resolves it for this profile, and
        /// where that value comes from: the profile itself (LocationCurrentProfile), or
        /// the global, base or default profile it inherits from. False when no profile
        /// holds the setting at all.</summary>
        internal bool TryGetDword(IntPtr profile, uint settingId, out uint value, out int location)
        {
            IntPtr setting = NewStruct(SettingSize, 1);
            try
            {
                int status = getSetting(session, profile, settingId, setting);
                if (status == SettingNotFound)
                {
                    value = 0;
                    location = -1;
                    return false;
                }
                Check("NvAPI_DRS_GetSetting", status);
                value = unchecked((uint)Marshal.ReadInt32(setting, SettingCurrentOffset));
                location = Marshal.ReadInt32(setting, SettingLocationOffset);
                return true;
            }
            finally
            {
                Marshal.FreeHGlobal(setting);
            }
        }

        internal void SetDword(IntPtr profile, uint settingId, uint value)
        {
            IntPtr setting = NewStruct(SettingSize, 1);
            try
            {
                Marshal.WriteInt32(setting, SettingIdOffset, unchecked((int)settingId));
                Marshal.WriteInt32(setting, SettingTypeOffset, 0);   // NVDRS_DWORD_TYPE
                Marshal.WriteInt32(setting, SettingCurrentOffset, unchecked((int)value));
                Check("NvAPI_DRS_SetSetting", setSetting(session, profile, setting));
            }
            finally
            {
                Marshal.FreeHGlobal(setting);
            }
        }

        internal void DeleteSetting(IntPtr profile, uint settingId)
        {
            int status = deleteSetting(session, profile, settingId);
            if (status != SettingNotFound)
                Check("NvAPI_DRS_DeleteProfileSetting", status);
        }

        /// <summary>Writes the session's changes to the driver. Returned rather than
        /// thrown, because InvalidUserPrivilege has a useful answer.</summary>
        internal int Save()
        {
            return saveSettings(session);
        }

        public void Dispose()
        {
            if (session != IntPtr.Zero)
            {
                destroySession(session);
                session = IntPtr.Zero;
            }
            unload();
        }

        private static T Function<T>(QueryInterfaceFn query, uint id) where T : class
        {
            IntPtr address = query(id);
            if (address == IntPtr.Zero)
                throw new NotSupportedException("This NVIDIA driver does not provide NvAPI function 0x" +
                    id.ToString("X8", CultureInfo.InvariantCulture) + ".");
            return (T)(object)Marshal.GetDelegateForFunctionPointer(address, typeof(T));
        }

        private static void Check(string function, int status)
        {
            if (status != Ok)
                throw new IOException(function + " returned " + status.ToString(CultureInfo.InvariantCulture) + ".");
        }

        private static IntPtr NewStruct(int size, int version)
        {
            IntPtr block = Marshal.AllocHGlobal(size);
            Marshal.Copy(new byte[size], 0, block, size);
            Marshal.WriteInt32(block, 0, size | (version << 16));
            return block;
        }

        private static IntPtr NewString(string value)
        {
            IntPtr block = Marshal.AllocHGlobal(StringBytes);
            Marshal.Copy(new byte[StringBytes], 0, block, StringBytes);
            WriteString(block, 0, value);
            return block;
        }

        private static void WriteString(IntPtr block, int offset, string value)
        {
            byte[] text = Encoding.Unicode.GetBytes(value ?? String.Empty);
            if (text.Length > StringBytes - 2)
                throw new ArgumentException("An NvAPI string is limited to 2047 characters.");
            Marshal.Copy(text, 0, new IntPtr(block.ToInt64() + offset), text.Length);
        }
    }

    internal sealed class NvidiaPresentEditState
    {
        internal string ExecutablePath;
        internal bool Changed;
    }

    /// <summary>Keeps NVIDIA from presenting KOTOR through a DXGI swap chain.
    ///
    /// NVIDIA's "Vulkan/OpenGL present method" can route an OpenGL game's frames through
    /// a Direct3D swap chain ("Prefer layered on DXGI Swapchain"). On that path KOTOR
    /// shows frames it has not finished drawing whenever one stalls: the white flash in
    /// the menus, a menu backdrop drawn alone, a half-drawn world. On NVIDIA's own
    /// default, Auto, the driver presents KOTOR natively and none of that appears.
    ///
    /// So this acts only when swkotor.exe would inherit "Prefer layered" -- from the
    /// global profile, with nothing set for the game itself -- and then sets the game's
    /// own profile to "Prefer native", which outranks the global one. A value set for the
    /// game deliberately, by NVIDIA or by the player, is left alone. NVIDIA matches
    /// profiles by executable name, so the setting reaches every swkotor.exe on the
    /// machine, which is also true of the same change made in the NVIDIA Control Panel.
    ///
    /// A sidecar records what KMRP did; restore undoes it only while the setting is still
    /// KMRP's. None of this may fail an install: an error is reported with the manual
    /// equivalent and patching continues.
    /// See reverse-engineering/experiments/white-flash-video-capture.md.</summary>
    internal static class NvidiaPresentOperations
    {
        // NvApiDriverSettings.h: OGL_CPL_PREFER_DXPRESENT, "Vulkan/OpenGL present method".
        private const uint PresentMethodId = 0x20D690F8;
        private const uint PreferNative = 0;    // OGL_CPL_PREFER_DXPRESENT_PREFER_DISABLED
        private const uint PreferLayered = 1;   // OGL_CPL_PREFER_DXPRESENT_PREFER_ENABLED
        private const uint PresentAuto = 2;     // OGL_CPL_PREFER_DXPRESENT_AUTO, the default
        internal const string ProfileName = "KMRP - Star Wars: Knights of the Old Republic";
        private const string ManifestHeader = "KMRPNV1";
        private const string ManifestName = "KMRP_NVIDIA.manifest";
        private const string ManualFix = " To do it by hand: NVIDIA Control Panel -> Manage 3D settings -> " +
            "Program Settings -> swkotor.exe -> Vulkan/OpenGL present method -> Prefer native.";

        private static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), ManifestName);
        }

        internal static NvidiaPresentEditState Install(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            NvidiaPresentEditState state = new NvidiaPresentEditState();
            state.ExecutablePath = executablePath;
            if (File.Exists(ManifestPath(executablePath)))
                return state;   // already KMRP's, from an earlier install

            try
            {
                string unavailable;
                using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
                {
                    if (drs == null)
                        return state;   // not an NVIDIA machine: nothing to do

                    IntPtr profile = drs.FindApplicationProfile(executablePath);
                    uint value;
                    int location;
                    bool found = drs.TryGetDword(profile != IntPtr.Zero ? profile : drs.GlobalProfile(),
                        PresentMethodId, out value, out location);
                    if (profile != IntPtr.Zero && found && location == NvDrsSession.LocationCurrentProfile)
                    {
                        if (value == PreferLayered)
                            SafeReport(report, "NVIDIA is set to present swkotor.exe through a DXGI swap chain in the " +
                                "game's own profile; left as chosen. If menus flash or show half-drawn frames, set its " +
                                "Vulkan/OpenGL present method to Auto or Prefer native.");
                        return state;
                    }
                    if (!found || value != PreferLayered)
                        return state;   // Auto or native, inherited: already right

                    if (profile != IntPtr.Zero)
                    {
                        string existingName;
                        int applications, settings;
                        drs.ProfileInfo(profile, out existingName, out applications, out settings);
                        if (applications != 1)
                        {
                            SafeReport(report, "Left the shared NVIDIA profile " + existingName +
                                " alone; its present method also affects other applications." + ManualFix);
                            return state;
                        }
                    }

                    bool createdProfile = false;
                    if (profile == IntPtr.Zero)
                    {
                        profile = drs.FindProfile(ProfileName);
                        if (profile != IntPtr.Zero)
                        {
                            SafeReport(report, "Left the existing NVIDIA profile named " +
                                ProfileName + " alone: it is not associated with this game." + ManualFix);
                            return state;
                        }
                        profile = drs.CreateProfile(ProfileName);
                        createdProfile = true;
                        drs.AddApplication(profile, Path.GetFileName(executablePath));
                    }
                    drs.SetDword(profile, PresentMethodId, PreferNative);
                    // The record first: a saved value with no record could never be
                    // restored, while a record whose save failed is recognised as not
                    // KMRP's and simply dropped.
                    string manifestPath = ManifestPath(executablePath);
                    WriteManifest(manifestPath, executablePath, createdProfile);
                    int saved = drs.Save();
                    if (saved != NvDrsSession.Ok)
                        File.Delete(manifestPath);
                    if (saved == NvDrsSession.InvalidUserPrivilege)
                    {
                        SafeReport(report, "NVIDIA would show half-drawn frames in KOTOR (its global present method " +
                            "prefers DXGI), and Windows did not allow the patcher to change that." + ManualFix);
                        return state;
                    }
                    if (saved != NvDrsSession.Ok)
                        throw new IOException("NvAPI_DRS_SaveSettings returned " +
                            saved.ToString(CultureInfo.InvariantCulture) + ".");
                    // A successful save needs rollback even if the fresh-session
                    // verification below fails (for example during a driver reset).
                    state.Changed = true;
                }

                if (!IsKmrpValue(executablePath))
                    throw new IOException("the setting did not read back after saving.");
                state.Changed = true;
                SafeReport(report, "Set NVIDIA's present method for swkotor.exe to Prefer native. It was inheriting " +
                    "Prefer layered on DXGI Swapchain, which shows half-drawn frames in KOTOR.");
            }
            catch (Exception ex)
            {
                SafeReport(report, "NVIDIA's present method for swkotor.exe could not be checked or set: " +
                    ex.Message + ManualFix);
            }
            return state;
        }

        internal static void Rollback(NvidiaPresentEditState state)
        {
            if (state == null || !state.Changed)
                return;
            Restore(state.ExecutablePath, null);
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            try
            {
                bool createdProfile;
                string recordedPath = ReadManifest(manifestPath, out createdProfile);
                if (!String.Equals(recordedPath, executablePath, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("the NVIDIA manifest belongs to a different executable path.");

                bool restored = false;
                string unavailable;
                using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
                {
                    if (drs == null)
                    {
                        // Unavailable can mean a transient driver/service failure;
                        // it does not prove that the saved profile was deleted.
                        SafeReport(report, "Kept KMRP's NVIDIA present-method record for a later restore: " + unavailable + ".");
                        return;
                    }
                    IntPtr profile = drs.FindApplicationProfile(executablePath);
                    uint value;
                    int location;
                    if (profile != IntPtr.Zero &&
                        drs.TryGetDword(profile, PresentMethodId, out value, out location) &&
                        location == NvDrsSession.LocationCurrentProfile && value == PreferNative)
                    {
                        string name;
                        int applications;
                        int settings;
                        drs.ProfileInfo(profile, out name, out applications, out settings);
                        // The whole profile only when KMRP made it and nothing else was
                        // added since; otherwise just the one setting.
                        if (createdProfile && name == ProfileName && applications == 1 && settings == 1)
                            drs.DeleteProfile(profile);
                        else
                            drs.DeleteSetting(profile, PresentMethodId);
                        int saved = drs.Save();
                        if (saved != NvDrsSession.Ok)
                        {
                            SafeReport(report, "KMRP's NVIDIA present-method setting for swkotor.exe could not be " +
                                "removed (NvAPI_DRS_SaveSettings returned " +
                                saved.ToString(CultureInfo.InvariantCulture) + "). Set it back to Use global " +
                                "setting in the NVIDIA Control Panel if you want the old behaviour.");
                            return;   // manifest kept, so a later restore can retry
                        }
                        restored = true;
                    }
                }

                File.Delete(manifestPath);
                if (restored)
                    SafeReport(report, "Removed KMRP's NVIDIA present-method setting for swkotor.exe.");
                else
                    SafeReport(report, "Left NVIDIA's present method for swkotor.exe as it is: it changed after install.");
            }
            catch (Exception ex)
            {
                SafeReport(report, "KMRP's NVIDIA present-method setting for swkotor.exe could not be restored: " +
                    ex.Message);
            }
        }

        /// <summary>One line on what NVIDIA will do for this executable, for logs and tests.</summary>
        internal static string Describe(string executablePath)
        {
            executablePath = Path.GetFullPath(executablePath);
            string unavailable;
            using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
            {
                if (drs == null)
                    return "NVIDIA: unavailable (" + unavailable + ")";
                IntPtr profile = drs.FindApplicationProfile(executablePath);
                IntPtr global = drs.GlobalProfile();
                uint value;
                int location;
                string game = "no profile names it";
                if (profile != IntPtr.Zero)
                {
                    string name;
                    int applications;
                    int settings;
                    drs.ProfileInfo(profile, out name, out applications, out settings);
                    game = "profile \"" + name + "\", " + (drs.TryGetDword(profile, PresentMethodId, out value, out location)
                        ? "present method " + Name(value) + " from " + Location(location)
                        : "present method not set anywhere");
                }
                string globalValue = drs.TryGetDword(global, PresentMethodId, out value, out location)
                    ? Name(value) : "not set (Auto)";
                return "NVIDIA: " + game + "; global " + globalValue +
                    (File.Exists(ManifestPath(executablePath)) ? "; KMRP manifest present" : "");
            }
        }

        private static bool IsKmrpValue(string executablePath)
        {
            string unavailable;
            using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
            {
                if (drs == null)
                    return false;
                IntPtr profile = drs.FindApplicationProfile(executablePath);
                uint value;
                int location;
                return profile != IntPtr.Zero &&
                    drs.TryGetDword(profile, PresentMethodId, out value, out location) &&
                    location == NvDrsSession.LocationCurrentProfile && value == PreferNative;
            }
        }

        private static string Name(uint value)
        {
            switch (value)
            {
                case PreferNative: return "Prefer native";
                case PreferLayered: return "Prefer layered on DXGI Swapchain";
                case PresentAuto: return "Auto";
                default: return "0x" + value.ToString("X8", CultureInfo.InvariantCulture);
            }
        }

        private static string Location(int location)
        {
            switch (location)
            {
                case 0: return "the game's own profile";
                case 1: return "the global profile";
                case 2: return "the base profile";
                case 3: return "the driver default";
                default: return "location " + location.ToString(CultureInfo.InvariantCulture);
            }
        }

        private static void WriteManifest(string path, string executablePath, bool createdProfile)
        {
            string text = ManifestHeader + "\r\n" +
                Convert.ToBase64String(Encoding.UTF8.GetBytes(executablePath)) + "\r\n" +
                (createdProfile ? "1" : "0") + "\r\n";
            File.WriteAllText(path, text, new UTF8Encoding(false));
        }

        private static string ReadManifest(string path, out bool createdProfile)
        {
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            if (lines.Length != 3 || lines[0] != ManifestHeader || (lines[2] != "0" && lines[2] != "1"))
                throw new InvalidDataException("the NVIDIA manifest is invalid.");
            createdProfile = lines[2] == "1";
            try { return Encoding.UTF8.GetString(Convert.FromBase64String(lines[1])); }
            catch (FormatException ex)
            {
                throw new InvalidDataException("the NVIDIA manifest contains invalid text.", ex);
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

    /// <summary>Installs and removes the bundled K1 Modern Driver Compatibility patch.
    ///
    /// K1DC is by Synchro, MPL-2.0, and is shipped here as the standalone build the
    /// author publishes for exactly this case: an executable another patcher has already
    /// modified, which his Patch Manager will not recognise. See
    /// docs/third-party-driver-compat.md.
    ///
    /// It is two files dropped beside swkotor.exe -- a `dinput8.dll` proxy that Windows
    /// loads at startup, and the `.asi` payload it loads in turn. **The executable is
    /// never touched.** K1DC patches its eight sites in memory at run time and checks
    /// only those, which is why it does not care that KMRP has changed bytes
    /// elsewhere. Verified against gold: all eight sites still hold the exact bytes his
    /// `kotor1.hooks.toml` declares, and none overlaps anything KMRP writes.
    ///
    /// A separate manifest from the Override one because these files live in the game
    /// folder rather than Override, and because the choice to install them is the user's
    /// and can differ between two installs of the same KMRP build.</summary>
    internal static class DriverCompatOperations
    {
        private sealed class InstalledFile
        {
            internal string Name;
            internal string Hash;
        }

        // Resource name -> file name in the game folder.
        private static readonly string[] ResourceNames = { "Kmrp.drivercompat.dinput8", "Kmrp.drivercompat.asi" };
        private static readonly string[] FileNames = { "dinput8.dll", "k1-modern-driver-compatibility.asi" };

        internal const string Version = "1.2.0";

        private static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)),
                                "KMRP_DriverCompat.manifest");
        }

        internal static bool Available
        {
            get
            {
                for (int i = 0; i < ResourceNames.Length; i++)
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream(ResourceNames[i]))
                        if (stream == null)
                            return false;
                return true;
            }
        }

        /// <summary>The two options are independent, and this is what makes them so.
        ///
        /// `dinput8.dll` is Ultimate ASI Loader (ThirteenAG, unmodified; see the notices in
        /// K1DC's folder), and it loads every `.asi` beside the game -- K1DC's payload and
        /// KMRP's controller runtime alike. So the loader is needed whenever EITHER option
        /// is on, and K1DC's own `.asi` only when driver compatibility is. Until
        /// 2026-09-24 the settings page forced driver compatibility on with the
        /// controller instead.
        ///
        /// Always restores first: going from both options to controller only must remove
        /// K1DC's `.asi`, or the loader would go on loading it.</summary>
        internal static void Apply(string executablePath, bool driverCompatibility,
            bool controllerSupport, Action<string> report)
        {
            Restore(executablePath, report);
            if (driverCompatibility || controllerSupport)
                Install(executablePath, report, driverCompatibility);
        }

        /// <summary>Write the loader, and K1DC's payload when `includePayload`, into the
        /// game folder, unless something already occupies one of those names that we did
        /// not put there.</summary>
        internal static void Install(string executablePath, Action<string> report,
            bool includePayload = true)
        {
            if (!Available)
                return;
            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            List<InstalledFile> installed = new List<InstalledFile>();
            // The loader is FileNames[0]; the payload, FileNames[1].
            int count = includePayload ? FileNames.Length : 1;

            for (int i = 0; i < count; i++)
            {
                string target = Path.Combine(folder, FileNames[i]);
                // Never clobber a file we did not write. A user may already run a
                // different ASI loader, or K1DC installed by hand, and silently replacing
                // either would be both destructive and undiagnosable.
                if (File.Exists(target) && !WasInstalledByUs(executablePath, FileNames[i], target))
                {
                    SafeReport(report, "Left the existing " + FileNames[i] +
                        " alone; the driver compatibility patch was not installed.");
                    return;
                }
            }

            for (int i = 0; i < count; i++)
            {
                string target = Path.Combine(folder, FileNames[i]);
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream(ResourceNames[i]))
                using (FileStream output = File.Create(target))
                    stream.CopyTo(output);
                InstalledFile record = new InstalledFile();
                record.Name = FileNames[i];
                record.Hash = GoldPatch.HashFile(target);
                installed.Add(record);
            }

            WriteManifest(executablePath, installed);
            if (includePayload)
                SafeReport(report, "Installed K1 Modern Driver Compatibility " + Version +
                    " (by Synchro). swkotor.exe was not modified.");
            else
                SafeReport(report, "Installed the ASI loader for controller support; " +
                    "Modern Driver Compatibility itself stays off.");
        }

        /// <summary>Remove both files, if we installed them and nothing has changed them
        /// since. Always safe to call: no manifest means nothing to do.</summary>
        internal static void Restore(string executablePath, Action<string> report)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            List<InstalledFile> records = ReadManifest(manifestPath);
            int removed = 0;
            int kept = 0;
            foreach (InstalledFile record in records)
            {
                string target = Path.Combine(folder, record.Name);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record.Hash)
                {
                    // Changed since we wrote it -- upgraded by hand, most likely. Leave
                    // it, and say so, rather than deleting someone else's newer copy.
                    kept++;
                    continue;
                }
                File.Delete(target);
                removed++;
            }

            File.Delete(manifestPath);
            if (removed > 0)
                SafeReport(report, "Removed the bundled driver compatibility patch.");
            if (kept > 0)
                SafeReport(report, "Left " + kept +
                    " driver compatibility file(s) in place because they changed after install.");
        }

        private static bool WasInstalledByUs(string executablePath, string name, string target)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return false;
            foreach (InstalledFile record in ReadManifest(manifestPath))
                if (String.Equals(record.Name, name, StringComparison.OrdinalIgnoreCase))
                    return GoldPatch.HashFile(target) == record.Hash;
            return false;
        }

        private static void WriteManifest(string executablePath, List<InstalledFile> files)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(Version).Append("\r\n");
            foreach (InstalledFile record in files)
                text.Append(record.Name).Append('\t').Append(record.Hash).Append("\r\n");
            File.WriteAllText(ManifestPath(executablePath), text.ToString(), new UTF8Encoding(false));
        }

        private static List<InstalledFile> ReadManifest(string manifestPath)
        {
            List<InstalledFile> records = new List<InstalledFile>();
            try
            {
                foreach (string line in File.ReadAllLines(manifestPath, Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length != 2 || parts[0] == "version")
                        continue;
                    InstalledFile record = new InstalledFile();
                    record.Name = parts[0];
                    record.Hash = parts[1];
                    records.Add(record);
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

    /// <summary>Installs the optional Xbox Controls module through KMRP's existing
    /// ASI loader. The hook engine is the MIT KOTOR Patch Manager runtime; the
    /// controller module is Saul0097's author-approved KPM Xbox Controls K1 1.2.
    /// Neither component writes to swkotor.exe: the six verified hooks are applied
    /// in memory when the game starts.</summary>
    internal static class ControllerOperations
    {
        private sealed class InstalledFile
        {
            internal string Name;
            internal string Hash;
        }

        // The last pair is the MIT licence of KOTOR Patch Manager, which covers the
        // runtime, the module derived from Saul0097's KPM Xbox Controls, and the
        // memory-safety patches in patch_config.toml. MIT asks for the notice to go
        // with every copy, and until 2026-09-25 the installer shipped those copies
        // without it. Keep it last: BuildConfig names the module as FileNames[1].
        private static readonly string[] ResourceNames =
            { "Kmrp.controller.runtime", "Kmrp.controller.module", "Kmrp.controller.sdl",
              "Kmrp.controller.sdllicense", "Kmrp.controller.kpmlicense" };
        private static readonly string[] FileNames =
            { "kmrp-controller-runtime.asi", "kmrp-controller.module", "kmrp-sdl3.dll",
              "kmrp-sdl3-LICENSE.txt", "kmrp-kotor-patch-manager-LICENSE.txt" };
        private const string ConfigName = "patch_config.toml";
        internal const string Version = "1.2";

        // The controller's own settings, read by the module (src/controller-native/
        // K1Rumble.cpp). Unlike every other file here it is the PLAYER'S to edit,
        // so it is written only when absent or still exactly as installed, is
        // never a reason to decline an install, and restore removes it only if it
        // is unchanged -- the manifest's usual rule.
        private const string SettingsName = "kmrp-controller.ini";
        // Every value here is what the user settled on in the pad tests of
        // 2026-09-25. Debug was 1 in the hardware-test builds, writing every
        // rumble event to kmrp-rumble.log; it is off now that those tests passed.
        private const string DefaultSettings =
            "; KMRP controller settings. Read by kmrp-controller.module while the game runs;\r\n" +
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
            "; 1 writes every rumble event to kmrp-rumble.log in this folder\r\n" +
            "Debug=0\r\n";

        private static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)),
                                "KMRP_Controller.manifest");
        }

        internal static bool Available
        {
            get
            {
                for (int i = 0; i < ResourceNames.Length; i++)
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream(ResourceNames[i]))
                        if (stream == null)
                            return false;
                return true;
            }
        }

        internal static void Install(string executablePath, string executableHash,
            Action<string> report)
        {
            // Controller support is OPTIONAL, so every reason it cannot install is
            // reported and skipped rather than thrown. Throwing aborted the whole patch:
            // a user who happened to have a `patch_config.toml` from any other KPM mod
            // got no fonts, no GUI archives and no executable patch either, with a .NET
            // stack trace as the only explanation. DriverCompatOperations.Install has
            // always declined this way; this now matches it.
            if (!Available)
            {
                SafeReport(report, "Controller support was not installed: this build does " +
                    "not carry the optional controller resources.");
                return;
            }

            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            if (!File.Exists(Path.Combine(folder, "dinput8.dll")))
            {
                SafeReport(report, "Controller support was not installed: its ASI loader " +
                    "(dinput8.dll) is not present.");
                return;
            }

            List<string> allNames = new List<string>(FileNames);
            allNames.Add(ConfigName);
            foreach (string name in allNames)
            {
                string target = Path.Combine(folder, name);
                // Never clobber a file we did not write. `patch_config.toml` in particular
                // belongs to whichever KPM mod created it, and overwriting it would break
                // that mod silently.
                if (File.Exists(target) && !WasInstalledByUs(executablePath, name, target))
                {
                    SafeReport(report, "Left the existing " + name +
                        " alone; controller support was not installed.");
                    return;
                }
            }

            List<InstalledFile> installed = new List<InstalledFile>();
            try
            {
                for (int i = 0; i < FileNames.Length; i++)
                {
                    string target = Path.Combine(folder, FileNames[i]);
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream(ResourceNames[i]))
                    using (FileStream output = File.Create(target))
                        stream.CopyTo(output);
                    installed.Add(new InstalledFile
                        { Name = FileNames[i], Hash = GoldPatch.HashFile(target) });
                }

                string configPath = Path.Combine(folder, ConfigName);
                File.WriteAllText(configPath, BuildConfig(executableHash), new UTF8Encoding(false));
                installed.Add(new InstalledFile
                    { Name = ConfigName, Hash = GoldPatch.HashFile(configPath) });

                // Read the manifest before WriteManifest replaces it: whether the
                // settings file is still ours is decided against the old record.
                string settingsPath = Path.Combine(folder, SettingsName);
                if (!File.Exists(settingsPath) ||
                    WasInstalledByUs(executablePath, SettingsName, settingsPath))
                {
                    File.WriteAllText(settingsPath, DefaultSettings, new UTF8Encoding(false));
                    installed.Add(new InstalledFile
                        { Name = SettingsName, Hash = GoldPatch.HashFile(settingsPath) });
                }
                else
                {
                    SafeReport(report, "Kept your " + SettingsName + " settings.");
                }
                WriteManifest(executablePath, installed);
            }
            catch
            {
                foreach (InstalledFile record in installed)
                {
                    string target = Path.Combine(folder, record.Name);
                    if (File.Exists(target) && GoldPatch.HashFile(target) == record.Hash)
                        File.Delete(target);
                }
                throw;
            }

            SafeReport(report, "Installed controller support " + Version +
                " through the KOTOR Patch Manager runtime.");
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
                string target = Path.Combine(folder, record.Name);
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
                SafeReport(report, "Removed the optional Xbox Controls component.");
            if (kept > 0)
                SafeReport(report, "Left " + kept +
                    " controller file(s) in place because they changed after install.");
        }

        private static string BuildConfig(string executableHash)
        {
            StringBuilder text = new StringBuilder();
            text.Append("target_version_sha = \"").Append(executableHash).Append("\"\r\n\r\n");
            text.Append("[[patches]]\r\nid = \"kmrp-xbox-controls-k1\"\r\n")
                .Append("dll = \"").Append(FileNames[1]).Append("\"\r\n");
            // The native hook table, generated from src/controller-native/kotor1.hooks.toml
            // and kept in step with it by tools/check_controller_drift.py.
            //
            // This replaces Saul0097's eight legacy detours rather than joining
            // them: four of these addresses (0x005E271E, 0x0040C1F6, 0x00686BA0,
            // 0x00404D96) are the same sites his module hooked, and the module
            // shipped here now exports both sets, with the native ones doing the
            // work. See docs/controller-handover-plan.md for which legacy parts
            // the native path replaces and which it keeps.
            //
            // Every entry's stolen bytes are position-independent, or are skipped
            // so they are never re-executed; tools/check_hook_stolen_bytes.py
            // asserts that and must stay green if any address here changes.
            AppendHook(text, "0x005E24E0", "6A, FF, 68, FD, 48, 72, 00",
                "NativeJoystickInitK1", new[] { "ecx" }, new[] { "pointer" });
            // Two hooks DECLINE the original code rather than run beside it, so
            // they skip the stolen bytes and name the address KPM jumps to when
            // the handler returns non-zero. Both steal a relative branch, which a
            // trampoline may not re-execute -- skipping is what makes them legal.
            AppendHook(text, "0x005E30F6", "89, 5C, 24, 2C, 74, 0F",
                "NativeJoystickBufferK1", new[] { "esi" }, new[] { "pointer" },
                new[] { "eax" }, "0x005E319B", true);
            AppendHook(text, "0x00679940", "D9, 05, 64, D7, 73, 00",
                "NativeJoystickMovementK1", new[] { "ecx" }, new[] { "pointer" });
            AppendHook(text, "0x00679B71", "E8, BA, 15, E3, FF",
                "NativeJoystickSkipNormalizeK1", new[] { "ecx" }, new[] { "pointer" },
                new[] { "eax" }, "0x00679B76", true);
            AppendHook(text, "0x0040CE70", "51, 53, 55, 56, 8B, E9",
                "NativeGuiFrameK1", new[] { "ecx" }, new[] { "pointer" });
            // Two more that decline, but these keep their stolen bytes: both are
            // ordinary loads. They consume A only when Cancel holds focus, and
            // exit into the panel's own 0x28 handler, so A on Cancel closes the
            // panel exactly as B does instead of running its confirm action.
            // A on Cancel in the two panels that answer A themselves: rewritten
            // to B at the handler's entry. No consumed exit -- KPM runs stolen
            // bytes before its TEST EAX, which is how the old Solo hook
            // consumed every A. See kotor1.hooks.toml.
            AppendHook(text, "0x006C2400", "8B, 54, 24, 08, 85, D2",
                "ResolveSoloModeConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006E0CF0", "55, 8B, EC, 83, E4, F8",
                "ResolveResolutionConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            // Character creation and level-up: A on the five panels that answer A
            // themselves and then pass it to the focused control, whose click can
            // raise A on the panel again -- a stack overflow with OK focused. Same
            // shape as the two above; see kotor1.hooks.toml.
            AppendHook(text, "0x006F8880", "53, 8B, 5C, 24, 08",
                "GuardAbilitiesConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006F6A10", "53, 8B, 5C, 24, 08",
                "GuardSkillsConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006F4680", "53, 8B, 5C, 24, 0C",
                "GuardFeatsConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006F28C0", "53, 8B, 5C, 24, 0C",
                "GuardPowersConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006F8FF0", "53, 8B, 5C, 24, 08",
                "GuardPortraitConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            // Name entry: the release of the A that opened it confirmed the name.
            AppendHook(text, "0x006FA220", "53, 8B, 5C, 24, 08",
                "GuardNameConfirmK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            // The echo guard, on every panel: CSWGuiPanel::HandleInputEvent never
            // hands an event to a focused control that would only press it back.
            AppendHook(text, "0x00409E60", "8B, 49, 1C, 85, C9",
                "GuardPanelEchoK1", new[] { "ecx", "esp+4", "esp+8" },
                new[] { "pointer", "pointer", "pointer" });
            AppendHook(text, "0x006039CF", "A1, E0, 39, 7A, 00, 8B, 48, 04",
                "NativeCameraFrameK1", new[] { "esi" }, new[] { "pointer" });
            AppendHook(text, "0x00404D96", "8B, 46, 48, 8B, 48, 08",
                "NativeMovieFrameK1", new[] { "esi" }, new[] { "pointer" });
            // Two hooks exist only to black the movie window. The grey flash
            // at either end of a movie is the "SWMovieWindow" class, which
            // InitializeMovie registers with hbrBackground NULL; see
            // src/controller-native/kotor1.hooks.toml for the addresses that
            // show it.
            AppendHook(text, "0x0040554B", "8B, 0D, F8, 39, 7A, 00",
                "NativeMovieWindowOpenK1", new[] { "esi" }, new[] { "pointer" });
            AppendHook(text, "0x00404BB0", "83, EC, 7C, 56, 8B, F1",
                "NativeMovieWindowCloseK1", new[] { "ecx" }, new[] { "pointer" });
            // The engine still runs the Xbox build's rumble subsystem and ends
            // it in DirectInput force feedback, which the invented pad cannot
            // receive. This carries the magnitudes to XInput instead.
            // The fourth parameter is UpdateRumble's frame-time argument, which
            // drives the mixer's clock. Decimal: KPM parses the offset with stoi,
            // so "esp+0x18" would silently read esp+0.
            AppendHook(text, "0x005F7617", "68, C0, 27, 09, 00",
                "NativeRumbleK1", new[] { "eax", "ecx", "ebp", "esp+24" },
                new[] { "int", "int", "pointer", "pointer" });
            // Rumble and haptics (src/controller-native/K1Rumble.cpp). Every
            // pattern the engine starts is played by KMRP's mixer: the play hook
            // declines the engine's own queue, exiting at PlayRumblePattern's
            // `return 0`, which is what the shipped PC game always returned.
            // The rest only observe. See docs/controller-rumble.md.
            AppendHook(text, "0x005FB49F", "3B, A9, 44, 03, 00, 00",
                "NativeRumblePlayK1", new[] { "ecx", "ebp" }, new[] { "pointer", "int" },
                new[] { "eax" }, "0x005FB536");
            AppendHook(text, "0x005F74B0", "56, 8B, B1, 50, 03, 00, 00",
                "NativeRumbleStopK1", new[] { "ecx", "esp+4" }, new[] { "pointer", "pointer" });
            AppendHook(text, "0x005FB98E", "0F, B6, 45, 0C, 83, E8, 00",
                "NativeRumbleCutoffK1", new[] { "ebp" }, new[] { "pointer" });
            AppendHook(text, "0x00646BA0", "A1, FC, 39, 7A, 00, 56",
                "NativeSaberPowerK1", new[] { "ecx", "esp+4" }, new[] { "pointer", "pointer" });
            AppendHook(text, "0x0060DE20", "83, EC, 1C, 56, 8B, F1",
                "NativeSaberContactK1", new[] { "ecx" }, new[] { "pointer" });
            AppendHook(text, "0x0063C4F0", "51, 8B, 49, 68, 85, C9",
                "NativeParryK1", new[] { "ecx" }, new[] { "pointer" });
            AppendHook(text, "0x006D4440", "53, 8B, 5C, 24, 08, 56",
                "NativeMuzzleFlashK1", new[] { "ecx" }, new[] { "pointer" });
            AppendHook(text, "0x00617EB0", "64, A1, 00, 00, 00, 00",
                "NativeMeleeHitK1", new[] { "esp+12" }, new[] { "pointer" });
            AppendHook(text, "0x00686BA0", "53, 56, 57, 8B, F1",
                "NativeActionBarK1", new[] { "ecx" }, new[] { "pointer" });
            // CSWGuiPanel::ReleaseGff, called last by all 68 panel
            // constructors. It deletes the parsed .gui, so it is the final
            // instant at which a control can be bound by tag -- which is how
            // the R3 party-switch cue exists at all. The handler ignores every
            // panel that is not one of the four party screens. See
            // reverse-engineering/custom-gui-controls.md.
            AppendHook(text, "0x0040B8F0", "56, 8B, F1, F6, 46, 44, 02",
                "NativePanelReleaseGffK1", new[] { "ecx" }, new[] { "pointer" });
            // Memory safety, adopted from the Kotor Patch Manager project
            // (VexFlint). Not controller hooks -- they are here because this is
            // the only hook table KMRP ships, and because KMRP loads far more
            // textures and data than vanilla, which is what makes an unbounded
            // write and a double free start to matter.
            //
            // Bytes copied verbatim from KPM rather than re-derived, so this is
            // the behaviour reviewed there. See
            // reverse-engineering/experiments/texture-bucket-overrun.md.

            // Three 5000-entry bucket arrays are indexed by driver-assigned GL
            // texture names with no range check. Saturate the id getter...
            AppendBytePatch(text, "0x0041FEB5",
                "C3, 90, 90, 90, 90",
                "3D, 88, 13, 00, 00, 72, 05, B8, 87, 13, 00, 00, C3");
            // ...and range-check the indexed write, rejoining at 0x0046BEB1 so
            // shadow casting is preserved for an out-of-range part.
            AppendBytePatch(text, "0x0046BE64",
                "8D, 34, 40, 8B, 04, B5, E8, 94, 81, 00",
                "3D, 88, 13, 00, 00, 72, 13, A1, BC, BF, 7F, 00, 8B, 0D, B8, " +
                "BF, 7F, 00, 3B, C8, 68, B1, BE, 46, 00, C3, 8D, 34, 40, 8B, " +
                "04, B5, E8, 94, 81, 00");

            // CreateArrays stores one allocation in both 0x38 and 0x3C, and two
            // paths free each of them. Zero the argument when it aliases 0x38;
            // free() guards NULL, so that is a safe no-op.
            AppendBytePatch(text, "0x004A847C",
                "8B, 56, 3C, 52, E8, 0B, 1F, 25, 00",
                "8B, 56, 3C, 3B, 56, 38, 75, 02, 33, D2, 52, B8, 90, A3, 6F, " +
                "00, FF, D0");
            AppendBytePatch(text, "0x004A8380",
                "8B, 46, 3C, 50, E8, 07, 20, 25, 00",
                "8B, 46, 3C, 3B, 46, 38, 75, 02, 33, C0, 50, B9, 90, A3, 6F, " +
                "00, FF, D1");

            // Every save leaks one buffer per resource written:
            // CERFFile::WriteResource hands the buffer to the writer and then
            // abandons it. Adopted from KPM's SaveGameMemoryLeak (Lane Dibello).
            AppendHook(text, "0x005DDE32", "8B, 8B, C0, 00, 00, 00",
                "NativeFreeSaveBufferK1", new[] { "esi" }, new[] { "pointer" });

            // The one legacy-owned hook the native path REQUIRES. Its action
            // bar helpers cache the interface in g_mainInterface every frame,
            // and this is the only thing that clears it -- it is hooked on
            // CSWGuiMainInterface's destructor. Without it the cache dangles
            // the moment a save is loaded over a loaded game, and the next GUI
            // frame walks freed memory: measured at 0x611E4B30 dereferencing a
            // freed 0x14D31F38, called from NativeGuiFrameK1.
            AppendHook(text, "0x0068B170", "6A, FF, 68, B0, F7, 72, 00",
                "ClearActionBarControlsK1", new[] { "ecx" }, new[] { "pointer" });
            AppendHook(text, "0x005E271E", "8B, 84, 24, E4, 00, 00, 00",
                "NativeNoteKeyboardK1", new[] { "eax", "edx" },
                new[] { "pointer", "int" });
            AppendHook(text, "0x0040C1F6", "89, 1E, 89, 7E, 04",
                "NativeNoteMouseK1", new[] { "esi", "ebx", "edi" },
                new[] { "pointer", "int", "int" });
            return text.ToString();
        }

        private static void AppendHook(StringBuilder text, string address, string bytes,
            string function, string[] sources, string[] types)
        {
            AppendHook(text, address, bytes, function, sources, types, null, null, false);
        }

        /// <summary>
        /// A hook that writes bytes rather than calling into the module: no
        /// function, no parameters. The runtime writes `replacement_bytes` and,
        /// for a `replace`, jumps to a cave -- so the replacement may be longer
        /// than the original, which is why these are not `simple` hooks.
        /// </summary>
        private static void AppendBytePatch(StringBuilder text, string address,
            string originalBytes, string replacementBytes)
        {
            text.Append("\r\n[[patches.hooks]]\r\naddress = ").Append(address)
                .Append("\r\ntype = \"replace\"\r\noriginal_bytes = [");
            AppendByteList(text, originalBytes);
            text.Append("]\r\nreplacement_bytes = [");
            AppendByteList(text, replacementBytes);
            text.Append("]\r\nexclude_from_restore = []\r\n");
        }

        private static void AppendByteList(StringBuilder text, string bytes)
        {
            string[] values = bytes.Split(new[] { ", " }, StringSplitOptions.None);
            for (int i = 0; i < values.Length; i++)
            {
                if (i > 0) text.Append(", ");
                text.Append("0x").Append(values[i]);
            }
        }

        private static void AppendHook(StringBuilder text, string address, string bytes,
            string function, string[] sources, string[] types,
            string[] exclude, string consumedExitAddress)
        {
            AppendHook(text, address, bytes, function, sources, types,
                exclude, consumedExitAddress, false);
        }

        /// <summary>
        /// `exclude` names registers the handler is allowed to change, and
        /// `consumedExitAddress` is where KPM transfers control when the handler
        /// returns non-zero in EAX. Together they let a hook DECLINE the original
        /// code rather than only run beside it, which is what the focus hook
        /// needs: correcting focus afterwards always draws one wrong frame first.
        /// </summary>
        private static void AppendHook(StringBuilder text, string address, string bytes,
            string function, string[] sources, string[] types,
            string[] exclude, string consumedExitAddress, bool skipOriginalBytes)
        {
            string[] values = bytes.Split(new[] { ", " }, StringSplitOptions.None);
            text.Append("\r\n[[patches.hooks]]\r\naddress = ").Append(address)
                .Append("\r\ntype = \"detour\"\r\nfunction = \"").Append(function)
                .Append("\"\r\noriginal_bytes = [");
            for (int i = 0; i < values.Length; i++)
            {
                if (i > 0) text.Append(", ");
                text.Append("0x").Append(values[i]);
            }
            text.Append("]\r\nskip_original_bytes = ")
                .Append(skipOriginalBytes ? "true" : "false")
                .Append("\r\nexclude_from_restore = [");
            if (exclude != null)
                for (int i = 0; i < exclude.Length; i++)
                {
                    if (i > 0) text.Append(", ");
                    text.Append("\"").Append(exclude[i]).Append("\"");
                }
            text.Append("]\r\n");
            if (!String.IsNullOrEmpty(consumedExitAddress))
                text.Append("consumed_exit_address = ").Append(consumedExitAddress).Append("\r\n");
            for (int i = 0; i < sources.Length; i++)
                text.Append("[[patches.hooks.parameters]]\r\nsource = \"")
                    .Append(sources[i]).Append("\"\r\ntype = \"")
                    .Append(types[i]).Append("\"\r\n");
        }

        private static bool WasInstalledByUs(string executablePath, string name, string target)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return false;
            foreach (InstalledFile record in ReadManifest(manifestPath))
                if (String.Equals(record.Name, name, StringComparison.OrdinalIgnoreCase))
                    return GoldPatch.HashFile(target) == record.Hash;
            return false;
        }

        private static void WriteManifest(string executablePath, List<InstalledFile> files)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(Version).Append("\r\n");
            foreach (InstalledFile record in files)
                text.Append(record.Name).Append('\t').Append(record.Hash).Append("\r\n");
            File.WriteAllText(ManifestPath(executablePath), text.ToString(), new UTF8Encoding(false));
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

    /// <summary>A file the installer writes to Override: its name there, the zip
    /// entry holding its bytes, and, for a file from the layout pool, its object
    /// name -- the first 16 hex digits of its SHA-256.</summary>
    internal sealed class PayloadFile
    {
        internal string Name;
        internal ZipArchiveEntry Entry;
        internal string Object;
    }

    /// <summary>
    /// The per-resolution interface files, each distinct file stored once.
    ///
    /// The installer embedded one archive per resolution, 49 of them and 118 MB,
    /// to install one. Most of their files are the same bytes at several
    /// resolutions: a prompt badge is drawn for its button's size, and many
    /// buttons share a size. On 2026-09-25 the 27,342 files held 11,930 distinct
    /// ones. tools/pack_resolution_layouts.py packs them into one zip:
    ///
    ///     index/WxH.txt       one line per file, in that resolution's archive
    ///                         order: the Override name, a tab, the object
    ///     objects/OBJECT      each distinct file once, named by the first 16
    ///                         hex digits of its SHA-256, upper case
    ///
    /// The build rebuilds every resolution from the pool and stops unless each
    /// matches its archive. Install checks every file it writes against its
    /// object name.
    /// </summary>
    internal sealed class GuiPool : IDisposable
    {
        internal const string ResourceName = "Kmrp.override.layouts";
        private const string MissingMessage = "The matching interface files are missing from this patcher.";

        private readonly ZipArchive archive;
        private readonly List<PayloadFile> files = new List<PayloadFile>();
        private readonly Dictionary<string, PayloadFile> byName =
            new Dictionary<string, PayloadFile>(StringComparer.Ordinal);

        private GuiPool(ZipArchive archive)
        {
            this.archive = archive;
        }

        /// <summary>This resolution's files, in its archive's order.</summary>
        internal List<PayloadFile> Files
        {
            get { return files; }
        }

        /// <summary>One file by its exact Override name, as ZipArchive.GetEntry
        /// found it in the resolution archive; null when the layout has none.</summary>
        internal ZipArchiveEntry GetEntry(string name)
        {
            PayloadFile file;
            return byName.TryGetValue(name, out file) ? file.Entry : null;
        }

        /// <summary>The pool opened at one resolution. Throws InvalidDataException
        /// when this patcher has no layout for it, or names an object it lacks.</summary>
        internal static GuiPool Open(string resolutionKey)
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName);
            if (stream == null)
                throw new InvalidDataException(MissingMessage);
            ZipArchive archive = null;
            try
            {
                archive = new ZipArchive(stream, ZipArchiveMode.Read, false);
                GuiPool pool = new GuiPool(archive);
                pool.ReadIndex(resolutionKey);
                return pool;
            }
            catch
            {
                if (archive != null)
                    archive.Dispose();
                else
                    stream.Dispose();
                throw;
            }
        }

        private void ReadIndex(string resolutionKey)
        {
            ZipArchiveEntry index = archive.GetEntry("index/" + resolutionKey + ".txt");
            if (index == null)
                throw new InvalidDataException(MissingMessage);
            using (StreamReader reader = new StreamReader(index.Open(), Encoding.UTF8))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (line.Length == 0)
                        continue;
                    int tab = line.IndexOf('\t');
                    ZipArchiveEntry entry = tab > 0
                        ? archive.GetEntry("objects/" + line.Substring(tab + 1))
                        : null;
                    if (entry == null)
                        throw new InvalidDataException("The interface files in this patcher are damaged.");
                    PayloadFile file = new PayloadFile
                    {
                        Name = line.Substring(0, tab),
                        Entry = entry,
                        Object = line.Substring(tab + 1)
                    };
                    files.Add(file);
                    byName[file.Name] = file;
                }
            }
            if (files.Count == 0)
                throw new InvalidDataException(MissingMessage);
        }

        public void Dispose()
        {
            archive.Dispose();
        }
    }

    internal static class OverrideOperations
    {
        private const string CommonResourceName = "Kmrp.override.common";
        private const string ManifestHeader = "KUIOVERRIDE1";

        /// <summary>A zip archive's files as payload, leaving out folder entries.</summary>
        private static List<PayloadFile> ArchiveFiles(ZipArchive archive)
        {
            List<PayloadFile> files = new List<PayloadFile>();
            foreach (ZipArchiveEntry entry in archive.Entries)
                if (!String.IsNullOrEmpty(entry.Name))
                    files.Add(new PayloadFile { Name = entry.FullName, Entry = entry });
            return files;
        }

        /// <summary>Is this texture already provided, under any texture extension?
        ///
        /// KOTOR resolves a texture by resref, and prefers .tpc over .tga when both
        /// exist. So a bundled `icon.tpc` installed next to a player's `icon.tga`
        /// does not sit harmlessly beside it -- it replaces it. Deferral therefore
        /// has to look for the resref, not the filename.</summary>
        private static bool TextureAlreadyPresent(string target, string relative,
            Dictionary<string, OverrideRecord> known)
        {
            if (File.Exists(target))
                return true;
            string sibling = SiblingTexturePath(relative);
            if (sibling == null)
                return false;
            // A sibling WE installed is not the player's file, and deferring to it
            // means deferring to ourselves. That is how the DXT5 icons could never
            // reach anyone upgrading: installing i_x.tpc looks up i_x.tpc in the
            // manifest, does not find it -- the manifest holds i_x.tga from the
            // build before -- and then yields to that .tga. Measured on a live
            // install: 1095 .tga, zero .tpc, and 351 of the 399 uncompressed
            // 147,500-byte icons were bundled as .tpc by the build it had just run.
            if (known.ContainsKey(sibling))
                return false;
            return File.Exists(Path.ChangeExtension(target, Path.GetExtension(sibling)));
        }

        /// <summary>The same resref under the other texture extension, as a relative
        /// path, or null when this is not a texture. KOTOR resolves a texture by
        /// resref and prefers .tpc over .tga, so the two names are one resource.</summary>
        private static string SiblingTexturePath(string relative)
        {
            string extension = Path.GetExtension(relative);
            bool tpc = ".tpc".Equals(extension, StringComparison.OrdinalIgnoreCase);
            bool tga = ".tga".Equals(extension, StringComparison.OrdinalIgnoreCase);
            if (!tpc && !tga)
                return null;
            return Path.ChangeExtension(relative, tpc ? ".tga" : ".tpc");
        }

        private static HashSet<string> bundledNames;

        /// <summary>The bundled third-party art -- Party Portraits, the HD Icon Pack --
        /// as opposed to KMRP's own interface files.
        ///
        /// These defer to whatever is already in Override. K1CP, for example, replaces
        /// `ia_class8_004.tga` and `ia_class9_003.tga`, which the HD Icon Pack also
        /// ships; art we merely bundle should never overwrite a mod the player installed
        /// on purpose. KMRP's own files are not in this set and install as always --
        /// a blanket "skip what exists" would let any stray file suppress the interface
        /// this patcher exists to deliver.</summary>
        private static HashSet<string> BundledNames()
        {
            if (bundledNames != null)
                return bundledNames;
            bundledNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream("Kmrp.bundled"))
                {
                    if (stream != null)
                        using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                        {
                            string line;
                            while ((line = reader.ReadLine()) != null)
                            {
                                line = line.Trim();
                                if (line.Length > 0)
                                    bundledNames.Add(line);
                            }
                        }
                }
            }
            catch { }
            return bundledNames;
        }

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
            // relative path -> hash written during THIS run, so a genuine
            // two-archives-disagree conflict is still caught while an ordinary
            // content update is not mistaken for one.
            Dictionary<string, string> writtenThisRun =
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            int deferred = 0;
            // Our own earlier copies of a texture, under the extension the
            // build no longer ships it with, removed as the new one lands.
            int supersededRemoved = 0;
            // The common artwork, this resolution's layout and the generated ability
            // icons, each as the files it installs. Opened inside the try, so that a
            // patcher without its interface files takes away the backup folder it has
            // just made, rather than leaving it to block the next attempt.
            List<IDisposable> opened = new List<IDisposable>();
            try
            {
                List<List<PayloadFile>> payloads = new List<List<PayloadFile>>();
                // What the progress bar says while each payload installs.
                List<string> payloadStages = new List<string>();
                Stream commonResource = Assembly.GetExecutingAssembly()
                    .GetManifestResourceStream(CommonResourceName);
                if (commonResource == null)
                    throw new InvalidDataException("The matching interface files are missing from this patcher.");
                ZipArchive common = new ZipArchive(commonResource, ZipArchiveMode.Read, false);
                opened.Add(common);
                payloads.Add(ArchiveFiles(common));
                payloadStages.Add("Installing interface artwork…");
                GuiPool layout = GuiPool.Open(resolution.Key);
                opened.Add(layout);
                payloads.Add(layout.Files);
                payloadStages.Add("Installing resolution layout…");

                // Feat/power icons are built here from the game's own texture pack
                // rather than embedded: 200 icons x 48 resolutions would add ~57 MB of
                // pure duplication, and the source art is already on disk. Null when
                // the pack is missing or the resolution needs no enlargement, in which
                // case the icons simply stay vanilla-sized.
                HashSet<string> shipped = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (List<PayloadFile> payload in payloads)
                    foreach (PayloadFile listed in payload)
                        shipped.Add(NormalizeRelativePath(listed.Name));
                MemoryStream generatedIcons = AbilityIconGenerator.TryBuild(
                    executablePath, ResolutionPatch.ScaleForHeight(resolution.Height), shipped);
                if (generatedIcons != null)
                {
                    ZipArchive icons = new ZipArchive(generatedIcons, ZipArchiveMode.Read, false);
                    opened.Add(icons);
                    payloads.Add(ArchiveFiles(icons));
                    payloadStages.Add("Installing ability icons…");
                }
                // The files made from the game's own art and data -- the hex row
                // frames, the tutorial popup's icons and tutorial.2da -- built from
                // this player's game, because no release carries anything of the
                // game's (GameArtGenerator, 2026-09-29). Null when the texture pack
                // or chitin.key cannot be read; the game then keeps its own.
                MemoryStream gameArt = GameArtGenerator.TryBuild(executablePath, resolution.Height, shipped);
                if (gameArt != null)
                {
                    ZipArchive art = new ZipArchive(gameArt, ZipArchiveMode.Read, false);
                    opened.Add(art);
                    payloads.Add(ArchiveFiles(art));
                    payloadStages.Add("Installing row frames and tutorial icons…");
                }
                // The ten controller prompt badges, re-placed against the label this
                // player's dialog.tlk actually draws. Null when that file is missing or
                // unreadable, in which case the shipped English placement stands.
                Dictionary<string, byte[]> promptReplacements =
                    ControllerPromptGenerator.TryBuild(executablePath, layout);

                // Each archive gets a slice of the 18-94 band proportional to its size.
                // The ranges used to be hardcoded as "18 to 88 for the first, 88 to 94 for
                // anything else", which was written when there were two archives. There are
                // up to four: the common artwork, the resolution layout, the generated
                // ability icons and the generated game art. The second and third once shared
                // one range, and the bar visibly fell back from 94% to 88% when the icons
                // began installing.
                long[] archiveBytes = new long[payloads.Count];
                long totalArchiveBytes = 0;
                for (int sizingIndex = 0; sizingIndex < payloads.Count; sizingIndex++)
                {
                    foreach (PayloadFile sized in payloads[sizingIndex])
                        archiveBytes[sizingIndex] += sized.Entry.Length;
                    totalArchiveBytes += archiveBytes[sizingIndex];
                }

                long bytesBeforeArchive = 0;
                for (int resourceIndex = 0; resourceIndex < payloads.Count; resourceIndex++)
                {
                    long totalBytes = archiveBytes[resourceIndex];
                    long completedBytes = 0;
                    int rangeStart = (int)(18 + 76L * bytesBeforeArchive
                        / Math.Max(1L, totalArchiveBytes));
                    int rangeLength = (int)(76L * archiveBytes[resourceIndex]
                        / Math.Max(1L, totalArchiveBytes));
                    string stage = payloadStages[resourceIndex];
                    SafeProgress(progress, rangeStart, stage);

                    foreach (PayloadFile file in payloads[resourceIndex])
                    {
                        string relative = NormalizeRelativePath(file.Name);

                        // Build-time metadata, not a game resource. The prompt
                        // placement manifest rides in the archive so the patcher
                        // can read it (ControllerPromptGenerator), but the game
                        // has no use for it and it should not be left sitting in
                        // the player's Override folder.
                        if (String.Equals(relative, ControllerPromptGenerator.ManifestName,
                                          StringComparison.OrdinalIgnoreCase))
                        {
                            completedBytes += file.Entry.Length;
                            continue;
                        }

                        string target = SafeDestination(overrideRoot, relative);

                        // Bundled art yields to a file already there that we did not
                        // put there. Not recorded either, so restore leaves it alone.
                        //
                        // The check has to span texture extensions, not just the exact
                        // name. The bundled item icons ship as .tpc, and the engine
                        // prefers .tpc over .tga for the same resref -- so testing only
                        // for our own filename would install ours beside a player's
                        // K1CP .tga and then silently win over it, which is the exact
                        // thing this deferral exists to prevent.
                        if (!known.ContainsKey(relative)
                            && BundledNames().Contains(Path.GetFileName(relative))
                            && TextureAlreadyPresent(target, relative, known))
                        {
                            deferred++;
                            completedBytes += file.Entry.Length;
                            continue;
                        }

                        string targetDirectory = Path.GetDirectoryName(target);
                        Directory.CreateDirectory(targetDirectory);

                        // Installing a texture over OUR OWN copy of the same
                        // resref under the other extension: take the old one
                        // away. The engine would ignore it -- .tpc wins over
                        // .tga -- but leaving it means the uncompressed icons
                        // this replaced stay on disk forever, and keep being
                        // found by the deferral above on every future install.
                        //
                        // The manifest record for that sibling is deliberately
                        // left in place. Restore skips its hash check when the
                        // file is gone, and still copies the player's original
                        // back if they had one.
                        string superseded = SiblingTexturePath(relative);
                        if (superseded != null && known.ContainsKey(superseded))
                        {
                            string supersededPath = SafeDestination(overrideRoot, superseded);
                            if (File.Exists(supersededPath))
                            {
                                try
                                {
                                    File.Delete(supersededPath);
                                    supersededRemoved++;
                                }
                                catch (IOException) { }
                                catch (UnauthorizedAccessException) { }
                            }
                        }

                        OverrideRecord record;
                        if (known.TryGetValue(relative, out record))
                        {
                            if (!existingInstallation)
                            {
                                // Already installed by an earlier archive in this
                                // same run. Keep the original record -- its
                                // HadOriginal/OriginalHash describe the user's file,
                                // and a second record would make the backup folder
                                // hold the patcher's own file and stop restore.
                                record.InstalledHash = String.Empty;
                            }
                        }
                        else
                        {
                            // Not in the manifest. On a fresh install that is every
                            // file; over an EXISTING install it is a file a newer
                            // build added -- tutorial.2da and the thirteen tut_*.tga
                            // popup icons arrived exactly this way in 2.7.0.
                            //
                            // This used to throw "belongs to a different resolution",
                            // which was the wrong diagnosis and, worse, a permanent
                            // block on ever shipping a NEW Override file to anyone
                            // who already had the patch installed: the only way out
                            // was a full restore. A real resolution mismatch is
                            // already caught upstream in ApplyInPlace, which compares
                            // the installed resolution against the requested one
                            // before any of this runs, so nothing is lost by treating
                            // an unknown path as what it is -- a new file, backed up
                            // first if the user already had one.
                            //
                            record = new OverrideRecord();
                            record.RelativePath = relative;
                            record.HadOriginal = File.Exists(target);
                            record.OriginalHash = String.Empty;
                            if (record.HadOriginal)
                            {
                                string backup = SafeDestination(backupRoot, relative);
                                Directory.CreateDirectory(Path.GetDirectoryName(backup));
                                if (File.Exists(backup))
                                {
                                    // A backup with no manifest record: an earlier
                                    // install was interrupted after copying this file
                                    // but before the manifest was written. The file
                                    // already on disk is the OLDER one, so it is the
                                    // better claim to being the user's original --
                                    // keep it and adopt its hash. Overwriting it with
                                    // the current file would destroy the original,
                                    // and File.Copy(false) used to just throw and
                                    // leave the install permanently stuck.
                                    record.OriginalHash = GoldPatch.HashFile(backup);
                                }
                                else
                                {
                                    File.Copy(target, backup, false);
                                    record.OriginalHash = GoldPatch.HashFile(backup);
                                    if (record.OriginalHash != GoldPatch.HashFile(target))
                                        throw new IOException("An interface file could not be backed up safely: " + relative);
                                }
                            }
                            records.Add(record);
                            known.Add(relative, record);
                        }

                        string temporary = target + ".kotor-ui-new-" + Guid.NewGuid().ToString("N") + ".tmp";
                        try
                        {
                            // A controller prompt badge whose position was
                            // recomputed against the player's own dialog.tlk
                            // replaces the archive's English-placed copy. It is
                            // substituted here rather than shipped as a fourth
                            // archive so that it stays ONE write of one path: a
                            // second archive carrying the same name would trip
                            // the two-archives-disagree guard below, which
                            // exists for a real bug and should not be taught to
                            // tolerate exceptions.
                            byte[] replacement = null;
                            if (promptReplacements != null)
                                promptReplacements.TryGetValue(relative, out replacement);
                            if (replacement != null)
                            {
                                using (FileStream output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                                {
                                    output.Write(replacement, 0, replacement.Length);
                                    output.Flush(true);
                                }
                            }
                            else
                            {
                                using (Stream input = file.Entry.Open())
                                using (FileStream output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                                {
                                    input.CopyTo(output);
                                    output.Flush(true);
                                }
                            }
                            string installedHash = GoldPatch.HashFile(temporary);
                            // A file from the layout pool must be the object it was
                            // stored as. The build verified the pool; this catches
                            // one damaged since. A prompt badge moved for this
                            // player's dialog.tlk is meant to differ, so not those.
                            if (file.Object != null && replacement == null &&
                                !installedHash.StartsWith(file.Object, StringComparison.Ordinal))
                                throw new InvalidDataException(
                                    "An interface file inside this patcher is damaged: " + relative);
                            // Guard the one thing this can actually catch: the SAME
                            // relative path arriving from two archives in THIS run
                            // with different content, which silently breaks restore
                            // (see the override-manifest duplicate fixed 2026-08-31).
                            //
                            // It used to compare against record.InstalledHash, which
                            // over an existing installation is the hash from the
                            // PREVIOUS build -- so every file whose content changed
                            // tripped it and no update could ever be installed
                            // without a full restore first. That is not a duplicate;
                            // it is the update working.
                            string writtenEarlier;
                            if (writtenThisRun.TryGetValue(relative, out writtenEarlier))
                            {
                                if (writtenEarlier != installedHash)
                                    throw new InvalidDataException("Two interface archives disagree about " +
                                        relative + ". This build is inconsistent; please report it.");
                            }
                            else
                            {
                                writtenThisRun.Add(relative, installedHash);
                            }
                            record.InstalledHash = installedHash;

                            if (processedPaths.Add(relative))
                                processed.Add(record);
                            if (File.Exists(target))
                                FileGuard.Replace(temporary, target);
                            else
                                File.Move(temporary, target);
                            if (GoldPatch.HashFile(target) != record.InstalledHash)
                                throw new IOException("An interface file could not be installed safely: " + relative);

                            completedBytes += file.Entry.Length;
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
                    bytesBeforeArchive += archiveBytes[resourceIndex];
                }

                // A record this run did not touch is a file an older build shipped and
                // this one no longer does. It stays on disk and keeps its record, so
                // restore still puts the user's original back -- which is exactly what
                // should happen. This used to throw, which meant a build could never
                // drop a file either. A genuine resolution mismatch is caught upstream
                // in ApplyInPlace before any of this runs.
                //
                // The manifest is now rewritten on updates as well as fresh installs.
                // Previously it was written only for a fresh install, so files a newer
                // build ADDED (tutorial.2da and the tut_*.tga popup icons, 2.7.0) got
                // no record at all and restore would have left them behind in Override.
                if (deferred > 0)
                    SafeReport(report, "Left " + deferred +
                        " bundled art file(s) alone: another mod already provides them.");
                if (supersededRemoved > 0)
                    SafeReport(report, "Replaced " + supersededRemoved +
                        " interface file(s) with a smaller compressed version.");
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
            finally
            {
                for (int index = opened.Count - 1; index >= 0; index--)
                    opened[index].Dispose();
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
            try
            {
                if (Inspect(targetPath) != ExecutableState.Gold)
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

                // A sidecar that matches the bytes on disk proves only that nothing has
                // edited the executable since this patcher wrote it -- not that those bytes
                // came from *this* build. Reinstalling a newer KMRP over an older one used
                // to be skipped on that evidence alone: the sidecar was rewritten to say the
                // install was current while the old executable stayed exactly as it was.
                // Recompute what this build would produce from the clean backup and compare;
                // anything else is an earlier build and has to come out before this goes in.
                if (IsCurrentBuildInstall(targetPath, currentHash, resolution))
                {
                    RefreshInstalledResolution(targetPath, resolution, width, height, currentHash, report, progress);
                    return;
                }

                SafeProgress(progress, 6, "Removing the earlier build…");
                SafeReport(report, "The installed files came from an earlier build of this patcher. " +
                    "Restoring the original game files before applying this one.");
                Restore(targetPath, report, null);
                currentHash = GoldPatch.HashFile(targetPath);
                if (!GoldPatch.IsSupportedSourceFile(targetPath))
                    throw new InvalidDataException("The earlier build could not be removed, so no changes were made.");
            }
            if (!GoldPatch.IsSupportedSourceFile(targetPath))
                throw new InvalidDataException("This swkotor.exe is not supported. No changes were made.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before patching.",
                    IniOperations.PathForExecutable(targetPath));

            string backupPath = BackupPath(targetPath);
            if (File.Exists(backupPath))
            {
                if (!GoldPatch.IsSupportedSourceFile(backupPath) ||
                    GoldPatch.HashFile(backupPath) != currentHash)
                    throw new InvalidDataException("The existing backup is not the exact supported input executable. Move it aside before patching:\r\n" + backupPath);
            }
            else
            {
                SafeProgress(progress, 7, "Creating a safety backup…");
                File.Copy(targetPath, backupPath, false);
                if (GoldPatch.HashFile(backupPath) != currentHash)
                    throw new IOException("Backup verification failed. No patch was applied.");
                SafeReport(report, "Backup created: " + backupPath);
            }

            string temporaryPath = targetPath + ".kotor-ui-new-" + Guid.NewGuid().ToString("N") + ".tmp";
            bool installed = false;
            IniEditState iniState = null;
            DpiCompatibilityEditState dpiState = null;
            NvidiaPresentEditState nvidiaState = null;
            OverrideEditState overrideState = null;
            try
            {
                SafeProgress(progress, 10, "Updating the game executable…");
                GoldPatch patch = GoldPatch.Load();
                byte[] source = File.ReadAllBytes(targetPath);
                byte[] target = patch.Apply(source, resolution);
                string targetHash = GoldPatch.HashBytes(target);
                WriteVerifiedFile(temporaryPath, target, targetHash);
                FileGuard.Replace(temporaryPath, targetPath);
                installed = true;

                if (GoldPatch.HashFile(targetPath) != targetHash)
                    throw new IOException("Post-install verification failed.");

                SafeProgress(progress, 15, "Updating display settings…");
                dpiState = DpiCompatibilityOperations.Install(targetPath, report);
                nvidiaState = NvidiaPresentOperations.Install(targetPath, report);
                iniState = IniOperations.Configure(targetPath, width, height, report);
                overrideState = OverrideOperations.Install(targetPath, resolution, report, progress);
                DriverCompatOperations.Apply(targetPath, KmrpSettings.DriverCompatibility,
                    KmrpSettings.ControllerSupport, report);
                if (KmrpSettings.ControllerSupport)
                    ControllerOperations.Install(targetPath, targetHash, report);
                SafeProgress(progress, 98, "Saving patch information…");
                WriteManifest(targetPath, backupPath, false, width, height, targetHash);
                SafeProgress(progress, 100, "Patch complete");
                SafeReport(report, "KOTOR is ready to play at " +
                    width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture) + ".");
            }
            catch
            {
                try { ControllerOperations.Restore(targetPath, report); }
                catch { }
                try { DriverCompatOperations.Restore(targetPath, report); }
                catch { }
                OverrideOperations.Rollback(overrideState);
                try { IniOperations.Rollback(iniState); }
                catch { }
                try { DpiCompatibilityOperations.Rollback(dpiState); }
                catch { }
                NvidiaPresentOperations.Rollback(nvidiaState);
                if (installed && File.Exists(backupPath))
                {
                    File.Copy(backupPath, targetPath, true);
                    if (GoldPatch.HashFile(targetPath) != GoldPatch.HashFile(backupPath))
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
            if (GoldPatch.IsSupportedSourceFile(targetPath))
            {
                OverrideOperations.Restore(targetPath, report, progress);
                ControllerOperations.Restore(targetPath, report);
                DriverCompatOperations.Restore(targetPath, report);
                DpiCompatibilityOperations.Restore(targetPath, report);
                NvidiaPresentOperations.Restore(targetPath, report);
                SafeProgress(progress, 92, "Restoring display settings…");
                IniOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving restore information…");
                WriteManifest(targetPath, BackupPath(targetPath), true, 0, 0, currentHash);
                SafeProgress(progress, 100, "Restore complete");
                SafeReport(report, "The original game files and settings have been restored.");
                return;
            }
            if (Inspect(targetPath) != ExecutableState.Gold)
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
                DriverCompatOperations.Restore(targetPath, report);
                DpiCompatibilityOperations.Restore(targetPath, report);
                NvidiaPresentOperations.Restore(targetPath, report);
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

        // The refresh path for an install this build already produced: the executable is
        // already the right bytes, so only the INI and the override files are rewritten.
        private static void RefreshInstalledResolution(string targetPath, ResolutionChoice resolution,
            int width, int height, string currentHash, Action<string> report, Action<int, string> progress)
        {
            IniEditState existingIniState = null;
            DpiCompatibilityEditState existingDpiState = null;
            NvidiaPresentEditState existingNvidiaState = null;
            OverrideEditState existingOverrideState = null;
            try
            {
                SafeProgress(progress, 12, "Updating display settings…");
                existingDpiState = DpiCompatibilityOperations.Install(targetPath, report);
                existingNvidiaState = NvidiaPresentOperations.Install(targetPath, report);
                existingIniState = IniOperations.Configure(targetPath, width, height, report);
                existingOverrideState = OverrideOperations.Install(targetPath, resolution, report, progress);
                DriverCompatOperations.Apply(targetPath, KmrpSettings.DriverCompatibility,
                    KmrpSettings.ControllerSupport, report);
                if (KmrpSettings.ControllerSupport)
                    ControllerOperations.Install(targetPath, currentHash, report);
                else
                    ControllerOperations.Restore(targetPath, report);
                SafeProgress(progress, 98, "Saving patch information…");
                WriteManifest(targetPath, BackupPath(targetPath), false, width, height, currentHash);
                SafeProgress(progress, 100, "Patch complete");
                SafeReport(report, "KOTOR is ready to play at " +
                    width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture) + ".");
            }
            catch
            {
                try { ControllerOperations.Restore(targetPath, report); }
                catch { }
                try { DriverCompatOperations.Restore(targetPath, report); }
                catch { }
                OverrideOperations.Rollback(existingOverrideState);
                try { IniOperations.Rollback(existingIniState); }
                catch { }
                try { DpiCompatibilityOperations.Rollback(existingDpiState); }
                catch { }
                NvidiaPresentOperations.Rollback(existingNvidiaState);
                throw;
            }
        }

        // True when the bytes on disk are the ones this build would write for this
        // resolution. The authoritative test rebuilds them from the clean backup, so it
        // never has to trust the sidecar about which build wrote the file. Throws when the
        // install is known to come from a different build but the backup needed to replace
        // it is gone: that cannot be repaired in place, and calling such an install current
        // is exactly what let a stale executable survive a reinstall.
        private static bool IsCurrentBuildInstall(string targetPath, string actualHash, ResolutionChoice resolution)
        {
            string expectedHash;
            if (TryComputeCurrentBuildHash(targetPath, resolution, out expectedHash))
                return String.Equals(expectedHash, actualHash, StringComparison.OrdinalIgnoreCase);

            string recordedGold = ReadManifestGoldTarget(targetPath);
            if (recordedGold.Length != 0 &&
                !String.Equals(recordedGold, GoldPatch.TargetHash, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The installed interface came from a different build of this " +
                    "patcher, and the clean backup needed to replace it is missing or unusable. Reinstall the " +
                    "original swkotor.exe, then patch again.");

            // Nothing to rebuild from and nothing saying the build differs: leave the
            // install alone rather than tearing down something that may well be correct.
            return true;
        }

        // Applies this build's gold delta and resolution constants to the verified clean
        // backup, giving the hash the installed executable must have. False when there is
        // no usable backup to compute it from.
        private static bool TryComputeCurrentBuildHash(string targetPath, ResolutionChoice resolution,
            out string expectedHash)
        {
            expectedHash = String.Empty;
            try
            {
                string backupPath = BackupPath(targetPath);
                if (!File.Exists(backupPath) || new FileInfo(backupPath).Length != GoldPatch.SourceLength)
                    return false;
                byte[] source = File.ReadAllBytes(backupPath);
                byte[] normalized;
                if (!PeCompatibility.TryNormalizeSupportedSource(source, out normalized))
                    return false;
                expectedHash = GoldPatch.HashBytes(GoldPatch.Load().Apply(source, resolution));
                return true;
            }
            catch
            {
                return false;
            }
        }

        // The gold hash of the build that last patched this install, or an empty string
        // when the sidecar is missing, unreadable, or predates the field.
        private static string ReadManifestGoldTarget(string targetPath)
        {
            try
            {
                string manifestPath = ManifestPath(targetPath);
                if (!File.Exists(manifestPath))
                    return String.Empty;
                Match value = Regex.Match(File.ReadAllText(manifestPath, Encoding.UTF8),
                    "\\\"goldTargetSha256\\\"\\s*:\\s*\\\"([0-9A-Fa-f]{64})\\\"",
                    RegexOptions.CultureInvariant);
                return value.Success ? value.Groups[1].Value : String.Empty;
            }
            catch
            {
                return String.Empty;
            }
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
        // Attribution ink. Desaturated silver-blue: readable against the card, clearly
        // secondary to Accent (42,198,239) so a credit never reads as a control.
        internal static readonly Color AuthorInk = Color.FromArgb(146, 170, 200);
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
        // Icons rendered at the exact size they are drawn, keyed "name@WxH". Built once
        // and reused, because rescaling the source on every paint stalled the animation.
        private static readonly Dictionary<string, Bitmap> ScaledArt = new Dictionary<string, Bitmap>();
        // The opaque bounding box of each icon, so its transparent margin is not drawn.
        private static readonly Dictionary<string, Rectangle> InkBounds = new Dictionary<string, Rectangle>();

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
                                   .GetManifestResourceStream("Kmrp.icon." + names[i]))
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
        /// <summary>Draws supplied artwork as a solid-colour silhouette taken from its
        /// alpha channel, cropped to its ink and pre-scaled.
        ///
        /// **Why the tint replaces rather than multiplies.** `DrawStatusArt` multiplies
        /// the source by the colour, which only works for white artwork -- and every icon
        /// that predates this one is white. The settings gear is black line art on
        /// transparency, and black times anything is black. This zeroes the source RGB and
        /// adds the wanted colour, keeping alpha, so the shape and its antialiasing come
        /// from the artwork and only the colour is ours. Equivalent to the multiply for
        /// white art, correct for any other.
        ///
        /// **Why it caches.** The source is 2000x2000 and is drawn into a ~35 px box.
        /// Resampling that on every paint with HighQualityBicubic cost enough to visibly
        /// stall the header animation while the pointer sat on the button -- hovering
        /// repaints, and each repaint was rescaling four million pixels. The scaled result
        /// is built once per size and reused, so a repaint is a 1:1 blit of a small bitmap.
        ///
        /// **Why it crops.** The artwork carries roughly 10-16% transparent margin on each
        /// side, so drawing it whole wasted a third of the space it was given. The opaque
        /// bounding box is measured once and only that region is drawn, fitted to the box
        /// with its aspect preserved and centred.</summary>
        internal static bool DrawIconMask(Graphics g, string name, Rectangle box, Color color)
        {
            if (box.Width <= 0 || box.Height <= 0)
                return false;
            Bitmap scaled = ScaledIcon(name, box.Width, box.Height);
            if (scaled == null)
                return false;

            using (ImageAttributes attributes = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { color.R / 255F, color.G / 255F, color.B / 255F, 0, 1 } });
                attributes.SetColorMatrix(matrix);
                // 1:1, so no resampling happens here.
                g.DrawImage(scaled, box, 0, 0, scaled.Width, scaled.Height,
                            GraphicsUnit.Pixel, attributes);
            }
            return true;
        }

        /// <summary>The icon cropped to its ink and rendered at exactly this size, built
        /// once and cached. Returns null if the artwork was not shipped.</summary>
        private static Bitmap ScaledIcon(string name, int width, int height)
        {
            string key = name + "@" + width.ToString(CultureInfo.InvariantCulture)
                       + "x" + height.ToString(CultureInfo.InvariantCulture);
            Bitmap cached;
            if (ScaledArt.TryGetValue(key, out cached))
                return cached;

            Image source = LoadIcon(name);
            if (source == null)
            {
                ScaledArt[key] = null;
                return null;
            }

            Rectangle ink = InkBoundsOf(name, source);
            Bitmap target = new Bitmap(width, height, PixelFormat.Format32bppArgb);
            using (Graphics g = Graphics.FromImage(target))
            {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.CompositingQuality = CompositingQuality.HighQuality;

                // Fit the ink into the box, preserving its aspect and centring it.
                double scale = Math.Min(width / (double)ink.Width, height / (double)ink.Height);
                int drawWidth = Math.Max(1, (int)Math.Round(ink.Width * scale));
                int drawHeight = Math.Max(1, (int)Math.Round(ink.Height * scale));
                Rectangle destination = new Rectangle((width - drawWidth) / 2,
                                                      (height - drawHeight) / 2,
                                                      drawWidth, drawHeight);
                g.DrawImage(source, destination, ink.X, ink.Y, ink.Width, ink.Height,
                            GraphicsUnit.Pixel);
            }
            ScaledArt[key] = target;
            return target;
        }

        private static Image LoadIcon(string name)
        {
            Image art;
            if (StatusArt.TryGetValue(name, out art))
                return art;
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream("Kmrp.icon." + name))
                using (Image source = stream == null ? null : Image.FromStream(stream))
                    art = source == null ? null : new Bitmap(source);
            }
            catch { art = null; }
            StatusArt[name] = art;
            return art;
        }

        /// <summary>The smallest rectangle containing every pixel of the artwork that is
        /// not effectively transparent. Measured once per icon with LockBits -- per-pixel
        /// GetPixel over four million pixels takes long enough to be felt at startup.</summary>
        private static Rectangle InkBoundsOf(string name, Image source)
        {
            Rectangle bounds;
            if (InkBounds.TryGetValue(name, out bounds))
                return bounds;

            bounds = new Rectangle(0, 0, source.Width, source.Height);
            Bitmap bitmap = source as Bitmap;
            if (bitmap != null)
            {
                BitmapData data = null;
                try
                {
                    data = bitmap.LockBits(new Rectangle(0, 0, bitmap.Width, bitmap.Height),
                                           ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                    int minX = bitmap.Width, minY = bitmap.Height, maxX = -1, maxY = -1;
                    // Marshal.Copy rather than a pointer walk: this project compiles
                    // without /unsafe, and one row at a time keeps the copy small.
                    byte[] row = new byte[Math.Abs(data.Stride)];
                    for (int y = 0; y < bitmap.Height; y++)
                    {
                        Marshal.Copy(new IntPtr(data.Scan0.ToInt64() + (long)y * data.Stride),
                                     row, 0, row.Length);
                        for (int x = 0; x < bitmap.Width; x++)
                        {
                            if (row[x * 4 + 3] <= 8)   // alpha, BGRA
                                continue;
                            if (x < minX) minX = x;
                            if (x > maxX) maxX = x;
                            if (y < minY) minY = y;
                            if (y > maxY) maxY = y;
                        }
                    }
                    if (maxX >= minX && maxY >= minY)
                        bounds = new Rectangle(minX, minY, maxX - minX + 1, maxY - minY + 1);
                }
                catch { }
                finally
                {
                    if (data != null)
                        bitmap.UnlockBits(data);
                }
            }
            InkBounds[name] = bounds;
            return bounds;
        }

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
                               .GetManifestResourceStream("Kmrp.icon." + name))
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
        /// <summary>How much taller step 2 becomes when it must offer the recovery
        /// buttons. The card reserves this so the layout never has to grow.</summary>
        internal const int RecoveryExtra = 67;
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
            BackColor = UiTheme.Card;
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
        /// <summary>A quieter secondary: a muted blue resting border instead of the card
        /// edge, and muted ink until hovered. For actions that sit under the primary one
        /// and must not compete with it.</summary>
        internal bool Subtle;
        /// <summary>Name of an embedded icon to draw centred instead of a label. The art
        /// is used as a silhouette, so it may be any colour -- see DrawIconMask.</summary>
        internal string IconName;
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
            // Opaque, not transparent. A transparent control inherits its parent's
            // background, which has not been painted yet while the window fades in, so
            // these appeared as white rectangles during the open animation. Every pill
            // sits on a Card-coloured surface, so this is what is behind it anyway.
            BackColor = UiTheme.Card;
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
                    using (Pen edge = new Pen(hover ? UiTheme.Accent
                               : (Subtle ? UiTheme.Border : UiTheme.CardEdge)))
                        g.DrawPath(edge, path);
                }
            }

            Color ink = progressActive ? Color.White :
                (!Enabled ? UiTheme.DisabledText
                    : (Primary ? Color.White
                        : (Subtle && !hover ? UiTheme.TextMuted : UiTheme.Text)));

            if (!String.IsNullOrEmpty(IconName))
            {
                // Square icon buttons: the glyph is centred and sized against the shorter
                // side, so the button stays legible at any scale.
                int side = (int)Math.Round(Math.Min(Width, Height) * 0.74F);
                Rectangle iconBox = new Rectangle((Width - side) / 2, (Height - side) / 2,
                                                  Math.Max(1, side), Math.Max(1, side));
                UiTheme.DrawIconMask(g, IconName, iconBox, ink);
                return;
            }
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
        // On by default since 2026-09-24, like the other two: Restore Defaults turns
        // all three on, and a default it does not restore would not be a default. It
        // costs a keyboard-and-mouse player nothing -- prompts appear only while a pad
        // is the active device -- and it carries the cursor confinement (issue #20).
        private const bool ControllerSupportDefault = true;

        private static bool loaded;
        private static bool driverCompatibility = DriverCompatibilityDefault;
        private static bool markerFixes = MarkerFixesDefault;
        private static bool controllerSupport = ControllerSupportDefault;
        // The newer version the player asked not to be reminded of again, or "".
        private static string skippedUpdate = "";

        internal static string SettingsPath
        {
            get
            {
                string root = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return Path.Combine(Path.Combine(root, "KMRP"), "settings.json");
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

        /// <summary>Install KMRP's optional controller support.
        ///
        /// Independent of DriverCompatibility since 2026-09-24. Both need the ASI loader,
        /// which DriverCompatOperations.Apply installs for either, so neither option
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
                Match controller = Regex.Match(json,
                    "\\\"controllerSupport\\\"\\s*:\\s*(true|false)",
                    RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
                if (controller.Success)
                    controllerSupport = String.Equals(controller.Groups[1].Value, "true",
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

    /// <summary>"KMRP 1.6.0 is available." Download opens the Deadly Stream page and
    /// Skip version closes. The switch, "Don't remind me again for 1.6.0", keeps that
    /// one version from being offered again, whichever button closes the dialog; a
    /// later version is still offered. There is deliberately no way to turn reminders
    /// off for good.
    ///
    /// The first design (2026-09-25) had a Skip button and a switch titled only
    /// "Don't remind me again", with "Not for 1.6.0; later versions will still show"
    /// beneath it. The maintainer found it unintuitive: the version belongs in the
    /// switch's own words.</summary>
    internal sealed class UpdateDialog : Form
    {
        private readonly OptionToggle remind;

        /// <summary>The switch. The dialog's own result is OK for Download and Cancel
        /// for Skip version, Escape or the close box.</summary>
        internal bool DontRemind { get { return remind.Checked; } }

        /// <summary>`scale` is the main window's, so the dialog matches it on any
        /// monitor; the numbers below are its 1080p design.</summary>
        internal UpdateDialog(string latest, string current, float scale)
        {
            this.scale = Math.Max(0.35F, scale);
            Text = "KMRP update";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = UiTheme.Card;
            Font = new Font("Segoe UI", Points(11F));
            ClientSize = new Size(Px(680), Px(292));
            KeyPreview = true;
            HandleCreated += delegate { MainForm.UseDarkTitleBar(Handle); };

            Label title = new Label();
            title.Text = "KMRP " + latest + " is available";
            title.Font = new Font("Segoe UI Semibold", Points(20F));
            title.ForeColor = UiTheme.Text;
            title.BackColor = UiTheme.Card;
            title.SetBounds(Px(32), Px(26), Px(616), Px(42));
            Controls.Add(title);

            Label body = new Label();
            body.Text = "You have " + current + ". The new version is on Deadly Stream.";
            body.Font = new Font("Segoe UI", Points(13F));
            body.ForeColor = UiTheme.TextMuted;
            body.BackColor = UiTheme.Card;
            body.SetBounds(Px(32), Px(72), Px(616), Px(30));
            Controls.Add(body);

            remind = new OptionToggle();
            remind.UiScale = this.scale;
            remind.Checked = false;
            remind.Title = "Don't remind me again for " + latest;
            // Title only: one line, centred on the switch.
            remind.SetBounds(Px(32), Px(118), Px(616), Px(60));
            Controls.Add(remind);

            PillButton download = new PillButton();
            download.UiScale = this.scale;
            download.Primary = true;
            download.TextSize = 17F;
            download.Text = "Download";
            download.SetBounds(Px(32), Px(206), Px(300), Px(56));
            download.Click += delegate { DialogResult = DialogResult.OK; Close(); };
            Controls.Add(download);

            PillButton skip = new PillButton();
            skip.UiScale = this.scale;
            skip.TextSize = 17F;
            skip.Text = "Skip version";
            skip.SetBounds(Px(348), Px(206), Px(300), Px(56));
            skip.Click += delegate { DialogResult = DialogResult.Cancel; Close(); };
            Controls.Add(skip);
        }

        private readonly float scale;
        private int Px(int design) { return Math.Max(1, (int)Math.Round(design * scale)); }
        private float Points(float design) { return Math.Max(6F, design * scale); }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape)
            {
                DialogResult = DialogResult.Cancel;
                Close();
                return;
            }
            base.OnKeyDown(e);
        }
    }

    /// <summary>One switchable option: a title, a paragraph of explanation, and a pill
    /// switch on the right. Painted rather than a CheckBox so it carries the same ink and
    /// radius as the rest of the card.</summary>
    internal sealed class OptionToggle : Control
    {
        private bool hover;
        private bool isChecked = true;
        internal float UiScale = 1F;
        internal string Title = "";
        internal string Detail = "";
        /// <summary>Who wrote the component. Set right of the title, never folded into
        /// the description.</summary>
        internal string Author = "";
        internal event EventHandler CheckedChanged;

        internal bool Checked
        {
            get { return isChecked; }
            set
            {
                if (isChecked == value)
                    return;
                isChecked = value;
                Invalidate();
                if (CheckedChanged != null)
                    CheckedChanged(this, EventArgs.Empty);
            }
        }

        internal OptionToggle()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = UiTheme.Card;
            Cursor = Cursors.Hand;
            TabStop = false;
        }

        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnClick(EventArgs e) { Checked = !Checked; base.OnClick(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            float scale = Math.Max(0.1F, UiScale);
            int radius = Math.Max(1, (int)Math.Round(10 * scale));
            Rectangle body = new Rectangle(0, 0, Width - 1, Height - 1);

            using (GraphicsPath path = UiTheme.RoundedRect(body, radius))
            {
                using (SolidBrush fill = new SolidBrush(hover ? UiTheme.CardHover : UiTheme.Badge))
                    g.FillPath(fill, path);
                using (Pen edge = new Pen(hover ? UiTheme.Border : UiTheme.CardEdge))
                    g.DrawPath(edge, path);
            }

            int pad = Math.Max(1, (int)Math.Round(20 * scale));
            int switchWidth = Math.Max(8, (int)Math.Round(64 * scale));
            int switchHeight = Math.Max(6, (int)Math.Round(32 * scale));
            int gutter = Math.Max(1, (int)Math.Round(18 * scale));
            // Everything written stops a gutter short of the switch's column. The credit
            // used to end 42px from the edge, over a switch anchored bottom-right in an
            // 86px row, so the two overlapped (reported 2026-09-24).
            int switchLeft = Width - pad - switchWidth;
            int textWidth = Math.Max(1, switchLeft - gutter - pad);

            // Two lines. Title and author share the first and are centred on each other;
            // the description and the switch share the second. The description stops
            // short of the switch so the row never looks crowded.
            using (Font titleFont = new Font("Segoe UI Semibold", Math.Max(6F, 17F * scale)))
            using (Font authorFont = new Font("Segoe UI", Math.Max(6F, 13.5F * scale)))
            using (Font detailFont = new Font("Segoe UI", Math.Max(6F, 13.5F * scale)))
            using (SolidBrush titleInk = new SolidBrush(UiTheme.Text))
            using (SolidBrush authorInk = new SolidBrush(UiTheme.AuthorInk))
            using (SolidBrush detailInk = new SolidBrush(UiTheme.TextMuted))
            using (StringFormat rightAlign = new StringFormat())
            {
                rightAlign.Alignment = StringAlignment.Far;
                rightAlign.LineAlignment = StringAlignment.Center;
                rightAlign.FormatFlags = StringFormatFlags.NoWrap;

                int titleHeight = (int)Math.Ceiling(titleFont.GetHeight(g));
                float titleTop = pad * 0.72F;
                g.DrawString(Title, titleFont, titleInk, new RectangleF(
                    pad, titleTop, textWidth, titleHeight + 2));

                if (!String.IsNullOrEmpty(Author))
                {
                    // Centred on the title's own box, so the two sit on one optical line
                    // whatever the two fonts' ascents do, and right-aligned to the same
                    // column the description stops at -- clear of the switch.
                    g.DrawString("by " + Author, authorFont, authorInk, new RectangleF(
                        pad, titleTop, textWidth, titleHeight + 2), rightAlign);
                }

                RectangleF detailBox = new RectangleF(
                    pad, titleTop + titleHeight + Math.Max(1, 2 * scale),
                    textWidth,
                    Math.Max(1, Height - titleTop - titleHeight - pad * 0.5F));
                g.DrawString(Detail, detailFont, detailInk, detailBox);
            }

            // The switch has the right-hand column to itself, centred on the row.
            Rectangle track = new Rectangle(switchLeft,
                                            (Height - switchHeight) / 2,
                                            switchWidth, switchHeight);
            using (GraphicsPath path = UiTheme.RoundedRect(track, switchHeight / 2))
            {
                using (SolidBrush fill = new SolidBrush(isChecked ? UiTheme.AccentStrong : UiTheme.Disabled))
                    g.FillPath(fill, path);
                using (Pen edge = new Pen(isChecked ? UiTheme.Accent : UiTheme.CardEdge))
                    g.DrawPath(edge, path);
            }
            // The knob is white in both states, as on iOS: the state is carried by the
            // track -- blue when on, grey when off -- and a white knob stays legible on
            // either without becoming a second colour to decode.
            int knob = switchHeight - Math.Max(2, (int)Math.Round(8 * scale));
            int knobX = isChecked ? track.Right - knob - (switchHeight - knob) / 2
                                  : track.Left + (switchHeight - knob) / 2;
            using (SolidBrush knobInk = new SolidBrush(isChecked ? Color.White : UiTheme.TextMuted))
                g.FillEllipse(knobInk, knobX, track.Y + (switchHeight - knob) / 2, knob, knob);
        }
    }

    /// <summary>Cross-fades one view of the card into another.
    ///
    /// Both states are captured as bitmaps and this control paints the incoming one
    /// solid with the outgoing one over it at falling alpha. Painting two opaque bitmaps
    /// avoids WinForms' transparent-control behaviour entirely -- a genuinely translucent
    /// control samples its parent's background, which is exactly the thing being
    /// animated, and flickers.</summary>
    internal sealed class FadeOverlay : Control
    {
        private readonly Bitmap outgoing;
        private readonly Bitmap incoming;
        private float progress;

        internal FadeOverlay(Bitmap outgoingView, Bitmap incomingView)
        {
            outgoing = outgoingView;
            incoming = incomingView;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
            TabStop = false;
        }

        internal float Progress
        {
            get { return progress; }
            set
            {
                progress = value < 0F ? 0F : (value > 1F ? 1F : value);
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            Rectangle box = new Rectangle(0, 0, Width, Height);
            if (incoming != null)
                g.DrawImage(incoming, box, 0, 0, incoming.Width, incoming.Height, GraphicsUnit.Pixel);
            if (outgoing == null || progress >= 1F)
                return;
            using (ImageAttributes attributes = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix();
                matrix.Matrix33 = 1F - progress;
                attributes.SetColorMatrix(matrix);
                g.DrawImage(outgoing, box, 0, 0, outgoing.Width, outgoing.Height,
                            GraphicsUnit.Pixel, attributes);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (outgoing != null) outgoing.Dispose();
                if (incoming != null) incoming.Dispose();
            }
            base.Dispose(disposing);
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
        // Derived, not restated: this said "v1.0.0" while PatchVersion and the
        // file's own version said 1.5.0, a second copy nobody updated.
        internal const string Version = "v" + GoldPatch.PatchVersion;
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
        private readonly CardPanel mainCard;
        private readonly PillButton settingsButton;
        private readonly CardPanel settingsView;
        private readonly OptionToggle driverToggle;
        private readonly OptionToggle markerToggle;
        private readonly OptionToggle controllerToggle;
        private readonly List<Control> mainViewControls = new List<Control>();
        private Timer fadeTimer;
        private FadeOverlay fadeOverlay;
        private bool settingsOpen;
        private readonly PillButton downloadExecutableButton;
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
                           .GetManifestResourceStream("Kmrp.brand"))
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
            mainCard = card;
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

            checkExecutableButton = new PillButton();
            checkExecutableButton.Text = "Check Again";
            // Directly beside Get Editable EXE: the third button here was "Choose
            // Editable EXE", which duplicated step 1's Browse -- the folder picker already
            // selects the executable, and Check Again re-verifies it.
            checkExecutableButton.SetBounds(242, 0, 164, 48);
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
            optionsHost.BackColor = UiTheme.Card;
            optionsHost.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            card.Controls.Add(optionsHost);

            // One action, whose identity follows the executable's state: patch a clean
            // install, restore a patched one. Two permanently visible buttons meant one of
            // them was always disabled, which reads as something being broken rather than
            // as a step that does not apply yet.
            actionButton = new PillButton();
            actionButton.Primary = true;
            actionButton.Text = "Start Patching";
            // The action row is one unit: the primary, a small gap, then a square
            // settings button of the same height. The square is sized from that height so
            // the two always agree, whatever the row height becomes.
            const int ActionHeight = 76;
            const int ActionGap = 12;
            // Step 2 grows by RecoveryExtra when it has to show the "get the editable
            // exe" buttons, and the steps below it move down. That room is reserved here
            // rather than found later: the card is a fixed height and the action row sits
            // a fixed distance from its bottom, so nothing below the card -- the footer,
            // the window, the settings view that covers it -- ever has to resize.
            //
            // Before this, only step 3 was repositioned and everything under it kept its
            // place, so in the recovery state step 3 landed on top of step 4.
            actionButton.SetBounds(80, optionsHost.Bottom + 30 + StepRow.RecoveryExtra,
                                   card.Width - 160 - ActionGap - ActionHeight, ActionHeight);
            actionButton.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            actionButton.Click += ActionClicked;
            card.Controls.Add(actionButton);

            // Secondary, and square: same height and radius as the primary so it reads as
            // part of the same row, but card-filled with a muted border rather than the
            // lit gradient, so it never competes with Start Patching.
            settingsButton = new PillButton();
            settingsButton.Subtle = true;
            settingsButton.IconName = "Settings";
            settingsButton.SetBounds(actionButton.Right + ActionGap, actionButton.Top,
                                     ActionHeight, ActionHeight);
            settingsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            settingsButton.Click += delegate { ShowSettings(true); };
            card.Controls.Add(settingsButton);

            ToolTip settingsTip = new ToolTip();
            settingsTip.SetToolTip(settingsButton, "Advanced Settings");

            card.Height = actionButton.Bottom + 40;

            // --- Settings -------------------------------------------------------
            // The settings view occupies the card, hidden until asked for. It is a
            // sibling of the step rows rather than a separate window so the cross-fade
            // has something to fade between and the window never changes size.
            // A CardPanel, not a plain Panel: it covers the card completely, so a
            // square one squared off the card's rounded corners for as long as settings
            // was open. This paints the same radius, fill and edge.
            settingsView = new CardPanel();
            settingsView.SetBounds(0, 0, card.Width, card.Height);
            settingsView.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            settingsView.Visible = false;
            card.Controls.Add(settingsView);

            Label settingsTitle = new Label();
            settingsTitle.Text = "Advanced Settings";
            settingsTitle.Font = new Font("Segoe UI Semibold", 24F);
            settingsTitle.ForeColor = UiTheme.Text;
            settingsTitle.BackColor = UiTheme.Card;
            settingsTitle.TextAlign = ContentAlignment.MiddleLeft;
            settingsTitle.SetBounds(36, 24, card.Width - 72, 48);
            settingsTitle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            settingsView.Controls.Add(settingsTitle);

            Label settingsSubtitle = new Label();
            settingsSubtitle.Text =
                "Choose optional components. All three are on by default, and each "
                + "can be turned off on its own.";
            settingsSubtitle.Font = new Font("Segoe UI", 14F);
            settingsSubtitle.ForeColor = UiTheme.TextMuted;
            settingsSubtitle.BackColor = UiTheme.Card;
            settingsSubtitle.TextAlign = ContentAlignment.MiddleLeft;
            settingsSubtitle.SetBounds(36, settingsTitle.Bottom + 2, card.Width - 72, 30);
            settingsSubtitle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            settingsView.Controls.Add(settingsSubtitle);

            driverToggle = new OptionToggle();
            driverToggle.Title = "Modern Driver Compatibility";
            driverToggle.Author = "Synchro";
            driverToggle.Detail =
                "Restores modern GPU rendering features and fixes driver-related visual issues.";
            driverToggle.Checked = KmrpSettings.DriverCompatibility;
            driverToggle.SetBounds(36, settingsSubtitle.Bottom + 18, card.Width - 72, 86);
            driverToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            // Independent of the controller since 2026-09-24: the controller brings its
            // own copy of the ASI loader when this is off (DriverCompatOperations.Apply).
            driverToggle.CheckedChanged += delegate
            {
                KmrpSettings.DriverCompatibility = driverToggle.Checked;
            };
            settingsView.Controls.Add(driverToggle);

            markerToggle = new OptionToggle();
            markerToggle.Title = "Area Map Marker Fixes";
            markerToggle.Author = "Derslok";
            markerToggle.Detail =
                "Corrects misplaced area-map marker positions across the game.";
            markerToggle.Checked = KmrpSettings.MarkerFixes;
            markerToggle.SetBounds(36, driverToggle.Bottom + 8, card.Width - 72, 86);
            markerToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            markerToggle.CheckedChanged += delegate
            {
                KmrpSettings.MarkerFixes = markerToggle.Checked;
            };
            settingsView.Controls.Add(markerToggle);

            controllerToggle = new OptionToggle();
            // What ships now, in one line: KMRP's native controller path with SDL3 beside
            // XInput, reading the pad family for its prompts. Saul0097's KPM Xbox Controls
            // is where it began and is still credited in THIRD_PARTY_NOTICES.md.
            controllerToggle.Title = "Controller Support";
            controllerToggle.Author = "KMRP, based on Saul0097";
            controllerToggle.Detail =
                "Xbox, PlayStation, Switch and Steam Deck: play, menus and matching button prompts.";
            controllerToggle.Checked = KmrpSettings.ControllerSupport;
            controllerToggle.SetBounds(36, markerToggle.Bottom + 8, card.Width - 72, 86);
            controllerToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            controllerToggle.CheckedChanged += delegate
            {
                KmrpSettings.ControllerSupport = controllerToggle.Checked;
            };
            settingsView.Controls.Add(controllerToggle);

            // Two actions, sharing the row the single Back button used to have. Restore
            // Defaults is Subtle so Back stays the obvious way out.
            int settingsRowTop = card.Height - 116;
            int settingsRowWidth = (card.Width - 160 - 12) / 2;

            PillButton settingsDefaults = new PillButton();
            settingsDefaults.Subtle = true;
            settingsDefaults.Text = "Restore Defaults";
            settingsDefaults.SetBounds(80, settingsRowTop, settingsRowWidth, 76);
            settingsDefaults.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            settingsDefaults.Click += delegate
            {
                // The documented defaults: all three on (KmrpSettings).
                driverToggle.Checked = true;
                markerToggle.Checked = true;
                controllerToggle.Checked = true;
            };
            settingsView.Controls.Add(settingsDefaults);

            PillButton settingsBack = new PillButton();
            settingsBack.Text = "Back";
            settingsBack.SetBounds(settingsDefaults.Right + 12, settingsRowTop,
                                   settingsRowWidth, 76);
            settingsBack.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            settingsBack.Click += delegate { ShowSettings(false); };
            settingsView.Controls.Add(settingsBack);

            // Everything the settings view replaces. Captured after the card is fully
            // populated so nothing is missed, and excluding the settings view itself.
            foreach (Control child in card.Controls)
                if (child != settingsView)
                    mainViewControls.Add(child);

            logLink = new LinkLabel();
            logLink.Text = Version + "   ·   Open Log";
            logLink.LinkArea = new LinkArea(Version.Length + 7, 8);
            logLink.Font = new Font("Segoe UI Semibold", 15.5F);
            logLink.ForeColor = UiTheme.TextFaint;
            logLink.LinkColor = UiTheme.Accent;
            logLink.ActiveLinkColor = Color.White;
            logLink.VisitedLinkColor = UiTheme.Accent;
            logLink.LinkBehavior = LinkBehavior.HoverUnderline;
            logLink.BackColor = UiTheme.Window;
            logLink.TextAlign = ContentAlignment.MiddleLeft;
            logLink.SetBounds(card.Left + 8, card.Bottom + 14, 240, 34);
            logLink.Anchor = AnchorStyles.Top;
            logLink.LinkClicked += OpenLogClicked;
            Controls.Add(logLink);

            LinkLabel credit = new LinkLabel();
            credit.Text = "Created by RaymanGT";
            credit.Font = new Font("Segoe UI Semibold", 15.5F);
            credit.LinkColor = UiTheme.TextFaint;
            credit.ActiveLinkColor = UiTheme.Accent;
            credit.VisitedLinkColor = UiTheme.TextFaint;
            credit.LinkBehavior = LinkBehavior.HoverUnderline;
            credit.BackColor = UiTheme.Window;
            credit.TextAlign = ContentAlignment.MiddleRight;
            // 260 wide, not 220. "Created by RaymanGT" measures 218px in Segoe UI but
            // 228px in Semibold, so the old box clipped it: a LinkLabel wraps rather than
            // ellipsises, and at 34 tall only the first line showed. The headroom also
            // covers the hinting differences that stop glyph widths scaling perfectly
            // linearly with point size. The right edge is unchanged at card.Right - 8.
            credit.SetBounds(card.Right - 268, card.Bottom + 14, 260, 34);
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

        /// <summary>Everything that has to be settled before the window is displayed.
        /// The fit used to run on Shown, which meant the window appeared at its full
        /// design size and then snapped to the fitted size in front of the user.</summary>
        protected override void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            FitInitialSizeToWorkingArea();

            presentHwnd = Handle;
            desiredHeaderW = Math.Max(1, ClientSize.Width);
            desiredHeaderH = Math.Max(1, ScaleDesign(headerHeight));
            EnsureHeaderOverlay(desiredHeaderW, desiredHeaderH);
            // One frame composed up front, so the very first paint already carries the
            // plume instead of showing a flat header that pops a frame later.
            ComposeFrame(desiredHeaderW, desiredHeaderH);
            UpdatePresentMode();
        }

        /// <summary>Started only once the window has been shown and painted. Presenting
        /// straight to the window before WinForms has drawn the client area leaves the
        /// header sitting over unpainted desktop.</summary>
        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            if (!updateCheckStarted)
            {
                updateCheckStarted = true;
                StartUpdateCheck();
            }
            if (renderThread != null)
                return;
            renderRunning = true;
            renderThread = new System.Threading.Thread(RenderLoop);
            renderThread.IsBackground = true;
            // Below normal: the plume must never win a scheduling contest against the UI
            // thread, or against the file work during a patch.
            renderThread.Priority = System.Threading.ThreadPriority.BelowNormal;
            renderThread.Start();
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
                OptionToggle optionToggle = child as OptionToggle;
                if (optionToggle != null)
                    optionToggle.UiScale = scale;

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
                        ComposeFrame(w, h);

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

        /// <summary>Draws one finished header -- background, plume, then the baked brand
        /// overlay -- into the back surface and swaps it to the front. The frame leaves
        /// here complete, so presenting it is a single opaque blit with nothing left for
        /// the UI thread to draw on top.</summary>
        private void ComposeFrame(int w, int h)
        {
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
            // The surfaces are swapped, never shared: the UI thread reads the front while
            // the render thread draws the back.
            lock (headerSwap)
            {
                Bitmap spare = headerFront;
                headerFront = headerBack;
                headerBack = spare;
            }
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
                FinishFade();
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
        /// builds of 10, 19 on the first that supported it; both are ignored elsewhere.
        /// The update dialog uses it too, so the two windows match.</summary>
        internal static void UseDarkTitleBar(IntPtr handle)
        {
            int on = 1;
            try
            {
                if (DwmSetWindowAttribute(handle, 20, ref on, sizeof(int)) != 0)
                    DwmSetWindowAttribute(handle, 19, ref on, sizeof(int));
            }
            catch { }
        }


        /// <summary>Swap the card between the steps and the settings view, cross-fading.
        ///
        /// Both states are rendered to bitmaps and a FadeOverlay is laid over the card
        /// while the alpha runs down; the real controls are swapped underneath it before
        /// the animation starts, so when the overlay goes away the live view is already
        /// in place and there is no second repaint to see.
        ///
        /// About 160 ms, which is long enough to read as a transition and short enough
        /// that a user clicking the gear twice in a row does not queue up a wait. A
        /// second call while one is running finishes the first immediately rather than
        /// stacking overlays.</summary>
        private void ShowSettings(bool show)
        {
            // Already there, or already going there: do nothing. Without this, pressing
            // the button twice restarted the fade from the top and stacked a second
            // overlay on the first, which looked like a stutter and leaked a timer.
            if (show == settingsOpen)
                return;
            settingsOpen = show;

            // Any fade still running is finished instantly rather than cancelled, so the
            // control tree is in a settled state before the next capture.
            FinishFade();

            Bitmap outgoing = CaptureCard();
            ApplyViewState();
            Bitmap incoming = CaptureCard();

            if (outgoing == null || incoming == null)
            {
                if (outgoing != null) outgoing.Dispose();
                if (incoming != null) incoming.Dispose();
                return;
            }

            fadeOverlay = new FadeOverlay(outgoing, incoming);
            fadeOverlay.SetBounds(0, 0, mainCard.Width, mainCard.Height);
            mainCard.Controls.Add(fadeOverlay);
            fadeOverlay.BringToFront();

            const int stepMs = 16;
            const float perStep = stepMs / 160F;
            fadeTimer = new Timer();
            fadeTimer.Interval = stepMs;
            fadeTimer.Tick += delegate
            {
                if (fadeOverlay == null)
                {
                    FinishFade();
                    return;
                }
                fadeOverlay.Progress = fadeOverlay.Progress + perStep;
                if (fadeOverlay.Progress >= 1F)
                    FinishFade();
            };
            fadeTimer.Start();
        }

        /// <summary>Tear down any running cross-fade, leaving the live controls showing.
        /// Safe to call when none is running.</summary>
        private void FinishFade()
        {
            if (fadeTimer != null)
            {
                fadeTimer.Stop();
                fadeTimer.Dispose();
                fadeTimer = null;
            }
            if (fadeOverlay != null)
            {
                mainCard.Controls.Remove(fadeOverlay);
                fadeOverlay.Dispose();
                fadeOverlay = null;
            }
        }

        /// <summary>The card as it currently looks, or null if it cannot be rendered.
        /// DrawToBitmap fails on a control with no handle or a zero dimension, neither of
        /// which is worth aborting a view switch over.</summary>
        private Bitmap CaptureCard()
        {
            try
            {
                if (mainCard == null || mainCard.Width <= 0 || mainCard.Height <= 0)
                    return null;
                Bitmap shot = new Bitmap(mainCard.Width, mainCard.Height);
                mainCard.DrawToBitmap(shot, new Rectangle(0, 0, mainCard.Width, mainCard.Height));
                return shot;
            }
            catch { return null; }
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

        private bool updateCheckStarted;

        /// <summary>Ask GitHub for the latest release off the UI thread; if it is newer,
        /// offer it once the window is idle. See UpdateCheck.</summary>
        private void StartUpdateCheck()
        {
            System.Threading.Thread check = new System.Threading.Thread(delegate()
            {
                string latest = UpdateCheck.LatestVersion();
                if (latest == null || !UpdateCheck.IsNewer(latest, GoldPatch.PatchVersion))
                    return;
                try { BeginInvoke(new MethodInvoker(delegate { OfferUpdate(latest); })); }
                catch { }   // the window closed first
            });
            check.IsBackground = true;
            check.Start();
        }

        private void OfferUpdate(string latest)
        {
            // Never over a patch in progress, and not for a version the player skipped
            // -- though a version later than that one is offered again.
            if (IsDisposed || operationRunning)
                return;
            string skipped = KmrpSettings.SkippedUpdate;
            if (skipped.Length > 0 && !UpdateCheck.IsNewer(latest, skipped))
                return;
            using (UpdateDialog dialog = new UpdateDialog(latest, GoldPatch.PatchVersion, uiScale))
            {
                bool download = dialog.ShowDialog(this) == DialogResult.OK;
                // The switch counts however the dialog was left, Download included.
                if (dialog.DontRemind)
                    KmrpSettings.SkippedUpdate = latest;
                if (!download)
                    return;
            }
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = UpdateCheck.DownloadPage;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open the download page",
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
                ? StepRow.HeaderHeight + StepRow.RecoveryExtra
                : StepRow.HeaderHeight;
            stepVerify.Height = ScaleDesign(verifyHeight);
            int below = StepRow.HeaderHeight + verifyHeight;
            PlaceStep(stepResolution, below);
            PlaceStep(stepApply, below + StepRow.HeaderHeight);

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
                stepVerify.SetSubtitle("Put the editable swkotor.exe in your KOTOR folder, then check again.");
            else if (state == ExecutableState.Unsupported)
                stepVerify.SetSubtitle("This copy cannot be patched. Replace it, then check again.");
            else
                stepVerify.SetSubtitle("This file could not be read. Replace it, then check again.");

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

            // RefreshStatus decides what the *steps* look like, and says nothing about
            // which view is on screen. It runs on Activated, so without this the settings
            // view was thrown away every time the window regained focus -- click another
            // window, come back, and the main page had returned underneath you.
            ApplyViewState();
        }

        /// <summary>Make the current view match `settingsOpen`.
        ///
        /// The single place that decides which of the two views is visible, so no other
        /// code has to remember. Only the card's direct children are touched: everything
        /// RefreshStatus toggles lives inside a step row and is hidden with its parent.</summary>
        private void ApplyViewState()
        {
            if (settingsView == null)
                return;   // still constructing
            for (int i = 0; i < mainViewControls.Count; i++)
                mainViewControls[i].Visible = !settingsOpen;
            settingsView.Visible = settingsOpen;
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
