using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace Kmrp
{
    /// <summary>
    /// Builds, at install, the files KMRP makes from the game's own art and data,
    /// so that no release carries any of them. Until 2026-09-29 the resource build
    /// exported these from the build machine's copy of the game and shipped them in
    /// every resolution's archive:
    ///
    /// - the four hex frames list rows draw behind item icons (`lbl_hex`,
    ///   `lbl_hex_3`, `lbl_hex_6`, `lbl_hex_7`), at the row's icon box, 56s. The
    ///   rows fill the box with the frame as a tiled texture, so the frame must be
    ///   exactly the box's size (tools/scale_row_icon_frames.py);
    /// - the tutorial popup's thirteen icons, private `tut_*` copies of game icons
    ///   at the popup's icon rect, 64s: the engine draws GUI art one texel per
    ///   pixel, so a smaller icon tiles and a larger one is cropped
    ///   (tools/export_tutorial_icons.py);
    /// - `tutorial.2da`, the game's own table with its `icon` column pointed at
    ///   those copies.
    ///
    /// s is the build's rule, max(1, height / 720) in double precision, rounded
    /// half to even, so every size is the one the build shipped. The textures are
    /// read from TexturePacks/swpc_tex_gui.erf and the table through chitin.key,
    /// beside the executable. macos/tools/kmrp-gameart.c is the same for the Mac,
    /// byte for byte (testing/regression/Test-GameArt.py).
    ///
    /// Sixteen of the seventeen textures are DXT5 in the pack. They are decoded with
    /// the standard formulas in integer arithmetic. The build decoded them with
    /// pykotor, which weights the eight-level alpha codes by i/7 instead of
    /// (i - 1)/7, so the shipped files had slightly wrong alpha on soft edges.
    ///
    /// All or nothing: null when anything cannot be read, and then the game keeps
    /// its own icons and table.
    /// </summary>
    internal static class GameArtGenerator
    {
        private const int FrameBase = 56;          // the vanilla row icon box (RowSizeGroups)
        private const int TutorialIconBase = 64;   // the vanilla popup icon rect (PopupSizeGroups)
        private const int ResourceType2da = 2017;

        private static readonly string[] FrameResrefs = { "lbl_hex", "lbl_hex_3", "lbl_hex_6", "lbl_hex_7" };

        // Game icon -> the popup's private copy; tutorial.2da's icon column is
        // repointed through the same table. Order as export_tutorial_icons.py.
        private static readonly string[][] TutorialIcons =
        {
            new[] { "lbl_icn_abi3", "tut_abi3" },
            new[] { "lbl_icn_char3", "tut_char3" },
            new[] { "lbl_icn_inv3", "tut_inv3" },
            new[] { "lbl_icn_map3", "tut_map3" },
            new[] { "lbl_icn_msg3", "tut_msg3" },
            new[] { "i_attack", "tut_attack" },
            new[] { "lbl_icredits", "tut_credits" },
            new[] { "lbl_idside", "tut_dside" },
            new[] { "lbl_ilside", "tut_lside" },
            new[] { "lbl_iplotxp", "tut_plotxp" },
            new[] { "lbl_iquest", "tut_quest" },
            new[] { "lbl_ireceive", "tut_receive" },
            new[] { "lbl_itaken", "tut_taken" },
        };

        /// <summary>The build's size rule (font_scale_for and the exporters).</summary>
        internal static int ScaledSize(int nativeSize, int height)
        {
            double scale = Math.Max(1.0, height / 720.0);
            return Math.Max(1, (int)Math.Round(nativeSize * scale));
        }

        /// <summary>
        /// A zip of the seventeen textures and tutorial.2da, or null. Never throws.
        /// Names in `reserved` (files another archive installs) are left out.
        /// </summary>
        internal static MemoryStream TryBuild(string executablePath, int height, ICollection<string> reserved)
        {
            try
            {
                List<KeyValuePair<string, byte[]>> files = Build(executablePath, height);
                if (files == null)
                    return null;

                MemoryStream buffer = new MemoryStream();
                using (ZipArchive archive = new ZipArchive(buffer, ZipArchiveMode.Create, true))
                {
                    foreach (KeyValuePair<string, byte[]> file in files)
                    {
                        if (reserved != null && reserved.Contains(file.Key))
                            continue;
                        ZipArchiveEntry entry = archive.CreateEntry(file.Key, CompressionLevel.Optimal);
                        using (Stream target = entry.Open())
                            target.Write(file.Value, 0, file.Value.Length);
                    }
                }
                buffer.Position = 0;
                return buffer;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>The files, in a fixed order, or null.</summary>
        internal static List<KeyValuePair<string, byte[]>> Build(string executablePath, int height)
        {
            string packPath = AbilityIconGenerator.TexturePackPath(executablePath);
            string gameRoot = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            if (!File.Exists(packPath))
                return null;
            byte[] pack = File.ReadAllBytes(packPath);

            // The first entry of each name, as the build's exporters took it.
            Dictionary<string, int[]> entries = new Dictionary<string, int[]>(StringComparer.Ordinal);
            foreach (KeyValuePair<string, int[]> entry in AbilityIconGenerator.EnumerateTpcEntries(pack))
                if (!entries.ContainsKey(entry.Key))
                    entries.Add(entry.Key, entry.Value);

            List<KeyValuePair<string, byte[]>> files = new List<KeyValuePair<string, byte[]>>();

            int frameSize = ScaledSize(FrameBase, height);
            foreach (string resref in FrameResrefs)
            {
                byte[] tga = Scaled(pack, entries, resref, frameSize, false);
                if (tga == null)
                    return null;
                files.Add(new KeyValuePair<string, byte[]>(resref + ".tga", tga));
            }

            int iconSize = ScaledSize(TutorialIconBase, height);
            foreach (string[] icon in TutorialIcons)
            {
                byte[] tga = Scaled(pack, entries, icon[0], iconSize, true);
                if (tga == null)
                    return null;
                files.Add(new KeyValuePair<string, byte[]>(icon[1] + ".tga", tga));
            }

            byte[] table = TutorialTable(gameRoot);
            if (table == null)
                return null;
            files.Add(new KeyValuePair<string, byte[]>("tutorial.2da", table));
            return files;
        }

        /// <summary>One texture at `size` x `size`, as a TGA. Tutorial icons are
        /// scaled nearest-neighbour when the size is a whole multiple (they are
        /// hard-edged glyphs), bilinear otherwise; frames are always bilinear.</summary>
        private static byte[] Scaled(byte[] pack, Dictionary<string, int[]> entries, string resref,
                                     int size, bool nearestOnMultiples)
        {
            int[] location;
            if (!entries.TryGetValue(resref, out location))
                return null;
            int width, height;
            byte[] bottomUp = DecodeTpc(pack, location[0], location[1], out width, out height);
            if (bottomUp == null)
                return null;

            // The build worked on top-down rows and wrote them back bottom-up; the
            // bilinear arithmetic is not exactly symmetric, so the same order is kept.
            byte[] topDown = FlipRows(bottomUp, width, height);
            byte[] scaled;
            if (nearestOnMultiples && width == height && size % width == 0)
                scaled = Nearest(topDown, width, height, size / width);
            else
                scaled = AbilityIconGenerator.Resize(topDown, width, height, size, size);
            return AbilityIconGenerator.WriteTga(FlipRows(scaled, size, size), size, size);
        }

        private static byte[] FlipRows(byte[] pixels, int width, int height)
        {
            byte[] result = new byte[pixels.Length];
            int stride = width * 4;
            for (int y = 0; y < height; y++)
                Buffer.BlockCopy(pixels, y * stride, result, (height - 1 - y) * stride, stride);
            return result;
        }

        private static byte[] Nearest(byte[] pixels, int width, int height, int factor)
        {
            int newWidth = width * factor;
            byte[] result = new byte[newWidth * height * factor * 4];
            for (int y = 0; y < height * factor; y++)
                for (int x = 0; x < newWidth; x++)
                    Buffer.BlockCopy(pixels, ((y / factor) * width + x / factor) * 4,
                                     result, (y * newWidth + x) * 4, 4);
            return result;
        }

        /// <summary>A TPC's top mip level as RGBA in its stored (bottom-up) row
        /// order: uncompressed RGB or RGBA, or DXT5. Null for anything else.</summary>
        private static byte[] DecodeTpc(byte[] pack, int offset, int size, out int width, out int height)
        {
            width = height = 0;
            const int header = 128;
            if (size < header)
                return null;
            int dataSize = BitConverter.ToInt32(pack, offset);
            width = BitConverter.ToUInt16(pack, offset + 8);
            height = BitConverter.ToUInt16(pack, offset + 10);
            int encoding = pack[offset + 12];
            if (width <= 0 || height <= 0)
                return null;
            int pixels = width * height;
            byte[] rgba = new byte[pixels * 4];

            if (dataSize == 0)
            {
                int channels = encoding == 2 ? 3 : encoding == 4 ? 4 : 0;
                if (channels == 0 || header + pixels * channels > size)
                    return null;
                for (int i = 0; i < pixels; i++)
                {
                    int from = offset + header + i * channels;
                    rgba[i * 4] = pack[from];
                    rgba[i * 4 + 1] = pack[from + 1];
                    rgba[i * 4 + 2] = pack[from + 2];
                    rgba[i * 4 + 3] = channels == 4 ? pack[from + 3] : (byte)255;
                }
                return rgba;
            }

            int blocksWide = (width + 3) / 4, blocksHigh = (height + 3) / 4;
            if (encoding != 4 || dataSize != blocksWide * blocksHigh * 16 || header + dataSize > size)
                return null;
            for (int by = 0; by < blocksHigh; by++)
                for (int bx = 0; bx < blocksWide; bx++)
                    DecodeDxt5Block(pack, offset + header + (by * blocksWide + bx) * 16, rgba, width, height, bx * 4, by * 4);
            return rgba;
        }

        /// <summary>One DXT5 (BC3) block, standard formulas, integer arithmetic.</summary>
        private static void DecodeDxt5Block(byte[] data, int at, byte[] rgba, int width, int height, int left, int top)
        {
            int[] alpha = new int[8];
            alpha[0] = data[at];
            alpha[1] = data[at + 1];
            if (alpha[0] > alpha[1])
            {
                for (int i = 2; i < 8; i++)
                    alpha[i] = ((8 - i) * alpha[0] + (i - 1) * alpha[1]) / 7;
            }
            else
            {
                for (int i = 2; i < 6; i++)
                    alpha[i] = ((6 - i) * alpha[0] + (i - 1) * alpha[1]) / 5;
                alpha[6] = 0;
                alpha[7] = 255;
            }
            ulong alphaBits = 0;
            for (int i = 0; i < 6; i++)
                alphaBits |= (ulong)data[at + 2 + i] << (8 * i);

            int color0 = data[at + 8] | (data[at + 9] << 8);
            int color1 = data[at + 10] | (data[at + 11] << 8);
            int[,] color = new int[4, 3];
            Unpack565(color0, color, 0);
            Unpack565(color1, color, 1);
            for (int c = 0; c < 3; c++)
            {
                color[2, c] = (2 * color[0, c] + color[1, c]) / 3;
                color[3, c] = (color[0, c] + 2 * color[1, c]) / 3;
            }
            uint colorBits = (uint)(data[at + 12] | (data[at + 13] << 8) | (data[at + 14] << 16) | (data[at + 15] << 24));

            for (int y = 0; y < 4; y++)
            {
                for (int x = 0; x < 4; x++)
                {
                    int px = left + x, py = top + y;
                    if (px >= width || py >= height)
                        continue;
                    int texel = 4 * y + x;
                    int colorIndex = (int)((colorBits >> (2 * texel)) & 3);
                    int alphaIndex = (int)((alphaBits >> (3 * texel)) & 7);
                    int o = (py * width + px) * 4;
                    rgba[o] = (byte)color[colorIndex, 0];
                    rgba[o + 1] = (byte)color[colorIndex, 1];
                    rgba[o + 2] = (byte)color[colorIndex, 2];
                    rgba[o + 3] = (byte)alpha[alphaIndex];
                }
            }
        }

        private static void Unpack565(int value, int[,] color, int row)
        {
            int r = (value >> 11) & 0x1F, g = (value >> 5) & 0x3F, b = value & 0x1F;
            color[row, 0] = (r << 3) | (r >> 2);
            color[row, 1] = (g << 2) | (g >> 4);
            color[row, 2] = (b << 3) | (b >> 2);
        }

        /// <summary>The game's tutorial.2da (chitin.key and its BIF) with every
        /// `icon` cell named in TutorialIcons repointed at the copy. Written as
        /// pykotor writes a binary 2DA, which reproduces the game's own file
        /// byte for byte. Null when it cannot be read.</summary>
        private static byte[] TutorialTable(string gameRoot)
        {
            byte[] original = ReadKeyedResource(gameRoot, "tutorial", ResourceType2da);
            if (original == null)
                return null;
            List<string> headers;
            List<string> labels;
            string[][] cells;
            if (!Parse2da(original, out headers, out labels, out cells))
                return null;
            int iconColumn = headers.FindIndex(h => String.Equals(h, "icon", StringComparison.OrdinalIgnoreCase));
            if (iconColumn < 0)
                return null;
            foreach (string[] row in cells)
                foreach (string[] icon in TutorialIcons)
                    if (String.Equals(row[iconColumn], icon[0], StringComparison.OrdinalIgnoreCase))
                        row[iconColumn] = icon[1];
            return Write2da(headers, labels, cells);
        }

        /// <summary>A resource from the BIFs chitin.key lists, or null.</summary>
        private static byte[] ReadKeyedResource(string gameRoot, string resref, int type)
        {
            string keyPath = Path.Combine(gameRoot, "chitin.key");
            if (!File.Exists(keyPath))
                return null;
            byte[] key = File.ReadAllBytes(keyPath);
            if (key.Length < 24 || Encoding.ASCII.GetString(key, 0, 8) != "KEY V1  ")
                return null;
            int bifCount = BitConverter.ToInt32(key, 8);
            int keyCount = BitConverter.ToInt32(key, 12);
            int fileTable = BitConverter.ToInt32(key, 16);
            int keyTable = BitConverter.ToInt32(key, 20);
            for (int i = 0; i < keyCount; i++)
            {
                int at = keyTable + i * 22;
                if (at + 22 > key.Length)
                    return null;
                int length = 0;
                while (length < 16 && key[at + length] != 0)
                    length++;
                if (!String.Equals(Encoding.ASCII.GetString(key, at, length), resref, StringComparison.OrdinalIgnoreCase)
                    || BitConverter.ToUInt16(key, at + 16) != type)
                    continue;
                uint id = BitConverter.ToUInt32(key, at + 18);
                int bifIndex = (int)(id >> 20), resourceIndex = (int)(id & 0xFFFFF);
                if (bifIndex >= bifCount)
                    return null;
                int entry = fileTable + bifIndex * 12;
                int nameOffset = BitConverter.ToInt32(key, entry + 4);
                int nameLength = BitConverter.ToUInt16(key, entry + 8);
                string bifName = Encoding.ASCII.GetString(key, nameOffset, nameLength).TrimEnd('\0')
                    .Replace('\\', Path.DirectorySeparatorChar);
                string bifPath = Path.Combine(gameRoot, bifName);
                if (!File.Exists(bifPath))
                    return null;
                byte[] bif = File.ReadAllBytes(bifPath);
                if (bif.Length < 20 || Encoding.ASCII.GetString(bif, 0, 8) != "BIFFV1  ")
                    return null;
                int variableCount = BitConverter.ToInt32(bif, 8);
                int variableTable = BitConverter.ToInt32(bif, 16);
                if (resourceIndex >= variableCount)
                    return null;
                int record = variableTable + resourceIndex * 16;
                if ((BitConverter.ToUInt32(bif, record) & 0xFFFFF) != resourceIndex)
                    return null;
                int offset = BitConverter.ToInt32(bif, record + 4);
                int size = BitConverter.ToInt32(bif, record + 8);
                if (offset < 0 || size < 0 || (long)offset + size > bif.Length)
                    return null;
                byte[] data = new byte[size];
                Buffer.BlockCopy(bif, offset, data, 0, size);
                return data;
            }
            return null;
        }

        // Bytes <-> string one to one, so no cell changes on the way through.
        private static string Latin1(byte[] data, int start, int count)
        {
            char[] chars = new char[count];
            for (int i = 0; i < count; i++)
                chars[i] = (char)data[start + i];
            return new string(chars);
        }

        private static bool Parse2da(byte[] data, out List<string> headers, out List<string> labels, out string[][] cells)
        {
            headers = new List<string>();
            labels = new List<string>();
            cells = null;
            if (data.Length < 9 || Latin1(data, 0, 9) != "2DA V2.b\n")
                return false;
            int at = 9, start = at;
            while (at < data.Length && data[at] != 0)
            {
                if (data[at] == (byte)'\t')
                {
                    headers.Add(Latin1(data, start, at - start));
                    start = at + 1;
                }
                at++;
            }
            if (at >= data.Length || headers.Count == 0)
                return false;
            at++;
            if (at + 4 > data.Length)
                return false;
            int rows = BitConverter.ToInt32(data, at);
            at += 4;
            for (int r = 0; r < rows; r++)
            {
                start = at;
                while (at < data.Length && data[at] != (byte)'\t')
                    at++;
                if (at >= data.Length)
                    return false;
                labels.Add(Latin1(data, start, at - start));
                at++;
            }
            int columns = headers.Count;
            int offsets = at;
            int dataStart = offsets + rows * columns * 2 + 2;
            if (dataStart > data.Length)
                return false;
            cells = new string[rows][];
            for (int r = 0; r < rows; r++)
            {
                cells[r] = new string[columns];
                for (int c = 0; c < columns; c++)
                {
                    int cell = dataStart + BitConverter.ToUInt16(data, offsets + (r * columns + c) * 2);
                    int end = cell;
                    while (end < data.Length && data[end] != 0)
                        end++;
                    if (end >= data.Length)
                        return false;
                    cells[r][c] = Latin1(data, cell, end - cell);
                }
            }
            return true;
        }

        /// <summary>Binary 2DA as pykotor's TwoDABinaryWriter writes it: each distinct
        /// value stored once, in the order cells first use it, row by row.</summary>
        private static byte[] Write2da(List<string> headers, List<string> labels, string[][] cells)
        {
            List<byte> output = new List<byte>();
            Action<string> text = delegate(string value)
            {
                foreach (char c in value)
                    output.Add((byte)c);
            };
            text("2DA V2.b\n");
            foreach (string header in headers)
                text(header + "\t");
            output.Add(0);
            output.AddRange(BitConverter.GetBytes(labels.Count));
            foreach (string label in labels)
                text(label + "\t");

            Dictionary<string, int> offsets = new Dictionary<string, int>(StringComparer.Ordinal);
            List<string> values = new List<string>();
            List<int> cellOffsets = new List<int>();
            int dataSize = 0;
            foreach (string[] row in cells)
            {
                foreach (string cell in row)
                {
                    int offset;
                    if (!offsets.TryGetValue(cell, out offset))
                    {
                        offset = dataSize;
                        offsets.Add(cell, offset);
                        values.Add(cell);
                        dataSize += cell.Length + 1;
                    }
                    cellOffsets.Add(offset);
                }
            }
            foreach (int offset in cellOffsets)
                output.AddRange(BitConverter.GetBytes((ushort)offset));
            output.AddRange(BitConverter.GetBytes((ushort)dataSize));
            foreach (string value in values)
            {
                text(value);
                output.Add(0);
            }
            return output.ToArray();
        }
    }
}
