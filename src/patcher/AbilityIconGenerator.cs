using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace Kmrp
{
    /// <summary>
    /// Builds enlarged feat/Force-power icons at patch time from the game's own
    /// texture pack, instead of shipping 48 pre-scaled copies inside the patcher.
    ///
    /// The Abilities screen draws each feat/power icon inside a chain-row slot.
    /// Read live at 3440x1440: the slot's frame is 80x80 and the icon control is
    /// 76x76 -- both scale with the row -- but the artwork is a 32x32 texture drawn
    /// at its native size, so enlarging the rows leaves a small icon in a big
    /// frame. The engine never scales GUI artwork at draw time (the same
    /// one-texel-per-pixel rule as the fonts), so the only way to enlarge an icon
    /// is to supply a bigger file.
    ///
    /// Generating them here rather than embedding them keeps ~57 MB out of the
    /// patcher: 200 icons x 48 resolutions is pure duplication, and the source art
    /// is on the user's disk already.
    ///
    /// The eight skill icons (`isk_*`, 32x32) have the same problem in the
    /// Skills tab, whose rows grow to 50s (RowSizeGroups; vanilla's are 42): stock,
    /// a 32 px icon sat in a 136 px row at 3024x1964. They grow by the same factor
    /// as their row, `round(32 * s * 50 / 42)`, so they keep their vanilla
    /// proportion to it, capped at 2x like the rest. (From 2026-09-29 the rows grew
    /// from 42 and the icons by `s` alone; the rows moved to 50 on 2026-09-30.) They are drawn only in the
    /// Skills tab and the skill info list (whose template rows grow by s too), so
    /// they fit wherever they appear; character creation shows no skill icons.
    /// Added 2026-09-29, for Windows and macOS together.
    ///
    /// That kept stock's proportion, and stock's skill art fills its whole 32x32
    /// canvas, so the picture sat on the frame's border rather than inside it --
    /// in stock too. The frame is lbl_hex_3 fitted to the row's icon box (42s);
    /// measured in game at 3440x1440 (box 84), its outline spans x 8..70 and
    /// y 11..80 of the box, the opening about 57x65, and the 64 px canvas, centred
    /// in the box, covered the border on the right and at the bottom. Reported in
    /// play the same day. So the canvas keeps its size and place, and the picture
    /// inside it is SkillPictureOfBox of the box, on transparent pixels, moved to
    /// the opening's centre (SkillShiftX, SkillShiftY): 52 px at 1440p, at every
    /// resolution including 720 and below.
    ///
    /// The two changes met in a merge on 2026-09-30: the box is 50s now, and the
    /// frame is stretched over it (lbl_hex_3 is 64x64 with its outline at x 7..55,
    /// y 6..59, which stretched to 84 gives the outline measured above), so the
    /// picture stays SkillPictureOfBox of the box and its move grows with the box,
    /// by 50 / 42. At 1440p that is a 62 px picture in the 64 px canvas, so the move
    /// up is cut from 5 px to 1 by the canvas's edge. Not yet seen in play.
    ///
    /// Names another archive already installs are skipped: `reserved` carries them
    /// in, so this can never write a file the patcher also ships.
    ///
    /// Only the uncompressed icons are handled. The pack's large textures are
    /// DXT-compressed (a non-zero dataSize), but every `i_*` / `ip_*` / `isk_*`
    /// icon stores raw pixels, so no decompressor is needed. Anything unexpected
    /// is skipped.
    /// </summary>
    internal static class AbilityIconGenerator
    {
        private const int TpcHeaderSize = 128;      // verified: 128 + w*h*bpp + TXI == resource size
        private const int ErfKeyRecordSize = 24;    // 16-byte resref, uint32 id, uint16 type, uint16 pad
        private const int ErfResourceRecordSize = 8;
        private const int ResourceTypeTpc = 3007;
        private const int FeatRowBase = 50;         // must match the feat/power group in RowSizeGroups
        private const int SkillRowBase = 50;        // must match the skills group in RowSizeGroups
        private const int VanillaSkillRow = 42;     // the row the 32 px skill icons were drawn for
        private const int IconInset = 4;            // icon control is the row height minus this
        // The skill picture's edge as a share of the Skills row's icon box, and how far
        // it moves from the canvas's centre, in pixels per unit of scale of the vanilla
        // box (42), so times SkillRowBase / VanillaSkillRow for the box it is now: the
        // canvas sits about 1.5 px right of and 2 px below lbl_hex_3's opening at 1440p,
        // so the picture moves left and up to the opening's centre. Chosen by measurement
        // at 3440x1440 (box 84): the largest picture whose every opaque pixel, for all
        // eight skills, stays 2 px clear of the frame's border -- 52 px moved (-1, -4);
        // 46 px was the most without the move, and 55 px touches.
        private const double SkillPictureOfBox = 0.62;
        private const double SkillShiftX = -0.5;
        private const double SkillShiftY = -2.0;

        /// <summary>Icon edge for this scale: the slot's icon box, capped at 2x the
        /// source. The art is 32x32 or 64x64; past 2x it is interpolated blur.</summary>
        private static int TargetSize(double scale, int nativeSize)
        {
            int box = (int)Math.Round(FeatRowBase * scale) - IconInset;
            if (box <= nativeSize)
                return nativeSize;
            return Math.Min(box, nativeSize * 2);
        }

        /// <summary>Skill icon edge for this scale: grown with the Skills row
        /// (50s, from vanilla's 42), so round(native * s * 50 / 42), capped at 2x
        /// the source.</summary>
        private static int SkillTargetSize(double scale, int nativeSize)
        {
            int grown = (int)Math.Round(nativeSize * scale * SkillRowBase / VanillaSkillRow);
            if (grown <= nativeSize)
                return nativeSize;
            return Math.Min(grown, nativeSize * 2);
        }

        /// <summary>The skill picture's edge inside that canvas: SkillPictureOfBox of
        /// the row's icon box (50s), never more than the canvas.</summary>
        private static int SkillPictureSize(double scale, int canvas)
        {
            int picture = (int)Math.Round(SkillRowBase * scale * SkillPictureOfBox);
            return Math.Min(picture, canvas);
        }

        internal static string TexturePackPath(string executablePath)
        {
            string gameRoot = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            return Path.Combine(gameRoot, "TexturePacks", "swpc_tex_gui.erf");
        }

        /// <summary>
        /// Returns a zip stream of enlarged icons, or null when nothing needs
        /// generating or the pack cannot be read. Never throws: a missing or
        /// modified texture pack must not stop the patch, it just means the icons
        /// stay vanilla-sized.
        /// </summary>
        internal static MemoryStream TryBuild(string executablePath, double scale,
                                              ICollection<string> reserved)
        {
            try
            {
                string packPath = TexturePackPath(executablePath);
                if (!File.Exists(packPath))
                    return null;

                byte[] pack = File.ReadAllBytes(packPath);
                List<KeyValuePair<string, byte[]>> icons = new List<KeyValuePair<string, byte[]>>();

                foreach (KeyValuePair<string, int[]> entry in EnumerateTpcEntries(pack))
                {
                    string name = entry.Key;
                    bool skill = name.StartsWith("isk_", StringComparison.Ordinal);
                    if (!(skill ||
                          name.StartsWith("i_", StringComparison.Ordinal) ||
                          name.StartsWith("ip_", StringComparison.Ordinal)))
                        continue;

                    // Never claim a name another archive installs. The `i_` prefix
                    // is not exclusive to ability icons: the shared archive ships
                    // i_checkbox01/02.tga, so without this the same path was
                    // written twice and recorded in the manifest twice, and restore
                    // then refused to run because the file on disk no longer
                    // matched the FIRST of its two records.
                    if (reserved != null && reserved.Contains(name + ".tga"))
                        continue;

                    byte[] tga = TryConvert(pack, entry.Value[0], entry.Value[1], scale, skill);
                    if (tga != null)
                        icons.Add(new KeyValuePair<string, byte[]>(name + ".tga", tga));
                }

                if (icons.Count == 0)
                    return null;

                MemoryStream buffer = new MemoryStream();
                using (ZipArchive archive = new ZipArchive(buffer, ZipArchiveMode.Create, true))
                {
                    foreach (KeyValuePair<string, byte[]> icon in icons)
                    {
                        ZipArchiveEntry zipEntry = archive.CreateEntry(icon.Key, CompressionLevel.Optimal);
                        using (Stream target = zipEntry.Open())
                            target.Write(icon.Value, 0, icon.Value.Length);
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

        /// <summary>Every TPC in the pack: lower-case resref -> {offset, size}, in
        /// the pack's own order. Shared with GameArtGenerator.</summary>
        internal static IEnumerable<KeyValuePair<string, int[]>> EnumerateTpcEntries(byte[] pack)
        {
            if (pack.Length < 0x20 ||
                Encoding.ASCII.GetString(pack, 0, 4) != "ERF ")
                yield break;

            int entryCount = BitConverter.ToInt32(pack, 16);
            int keysOffset = BitConverter.ToInt32(pack, 24);
            int resourcesOffset = BitConverter.ToInt32(pack, 28);

            for (int i = 0; i < entryCount; i++)
            {
                int keyAt = keysOffset + i * ErfKeyRecordSize;
                int resourceAt = resourcesOffset + i * ErfResourceRecordSize;
                if (keyAt + ErfKeyRecordSize > pack.Length ||
                    resourceAt + ErfResourceRecordSize > pack.Length)
                    yield break;

                if (BitConverter.ToUInt16(pack, keyAt + 20) != ResourceTypeTpc)
                    continue;

                int nameLength = 0;
                while (nameLength < 16 && pack[keyAt + nameLength] != 0)
                    nameLength++;
                string name = Encoding.ASCII.GetString(pack, keyAt, nameLength).ToLowerInvariant();

                int offset = BitConverter.ToInt32(pack, resourceAt);
                int size = BitConverter.ToInt32(pack, resourceAt + 4);
                if (offset < 0 || size < 0 || (long)offset + size > pack.Length)
                    continue;

                yield return new KeyValuePair<string, int[]>(name, new[] { offset, size });
            }
        }

        private static byte[] TryConvert(byte[] pack, int offset, int size, double scale, bool skill)
        {
            if (size < TpcHeaderSize + 4)
                return null;

            int dataSize = BitConverter.ToInt32(pack, offset);
            int width = BitConverter.ToUInt16(pack, offset + 8);
            int height = BitConverter.ToUInt16(pack, offset + 10);
            int encoding = pack[offset + 12];

            // dataSize != 0 means DXT-compressed. Icons are never compressed; skip
            // anything that is rather than guessing at a decoder.
            if (dataSize != 0 || width <= 0 || height <= 0 || width != height)
                return null;

            int channels;
            switch (encoding)
            {
                case 2: channels = 3; break;    // RGB
                case 4: channels = 4; break;    // RGBA
                default: return null;           // grayscale or unknown: leave alone
            }

            int pixelBytes = width * height * channels;
            if (TpcHeaderSize + pixelBytes > size)
                return null;

            int target = skill ? SkillTargetSize(scale, width) : TargetSize(scale, width);
            int picture = skill ? SkillPictureSize(scale, target) : target;
            if (target == width && picture == width)
                return null;                    // already right for this resolution

            // TPC pixel rows run bottom-up, and so does the TGA we write, so no
            // flip is needed anywhere in this path.
            byte[] source = new byte[width * height * 4];
            for (int i = 0; i < width * height; i++)
            {
                int from = offset + TpcHeaderSize + i * channels;
                source[i * 4] = pack[from];
                source[i * 4 + 1] = pack[from + 1];
                source[i * 4 + 2] = pack[from + 2];
                source[i * 4 + 3] = channels == 4 ? pack[from + 3] : (byte)255;
            }

            byte[] resized = Resize(source, width, height, picture, picture);
            if (picture == target)
                return WriteTga(resized, target, target);
            // On a transparent canvas of the full size, so the icon keeps its place in
            // the row: centred, then moved to the frame opening's centre, never past
            // the canvas's edge.
            byte[] canvas = new byte[target * target * 4];
            int inset = (target - picture) / 2;
            int left = Math.Max(0, Math.Min(target - picture,
                inset + (int)Math.Round(SkillShiftX * scale * SkillRowBase / VanillaSkillRow)));
            int top = Math.Max(0, Math.Min(target - picture,
                inset + (int)Math.Round(SkillShiftY * scale * SkillRowBase / VanillaSkillRow)));
            // Rows are bottom-up here, as in the TGA: the picture's top is at row
            // target - top - picture from the bottom.
            int bottom = target - top - picture;
            for (int y = 0; y < picture; y++)
                Buffer.BlockCopy(resized, y * picture * 4, canvas, ((y + bottom) * target + left) * 4, picture * 4);
            return WriteTga(canvas, target, target);
        }

        /// <summary>Bilinear, sampled at pixel centres; the same arithmetic as
        /// resize_rgba in tools/scale_row_icon_frames.py. Shared with GameArtGenerator.</summary>
        internal static byte[] Resize(byte[] pixels, int width, int height, int newWidth, int newHeight)
        {
            byte[] result = new byte[newWidth * newHeight * 4];
            double xRatio = (double)width / newWidth;
            double yRatio = (double)height / newHeight;

            for (int y = 0; y < newHeight; y++)
            {
                // Sample at pixel centres so the result stays centred rather than
                // drifting half a texel towards the origin.
                double sy = (y + 0.5) * yRatio - 0.5;
                int y0 = Math.Max(0, Math.Min(height - 1, (int)sy));
                int y1 = Math.Min(height - 1, y0 + 1);
                double wy = sy - y0;
                if (wy < 0) wy = 0;

                for (int x = 0; x < newWidth; x++)
                {
                    double sx = (x + 0.5) * xRatio - 0.5;
                    int x0 = Math.Max(0, Math.Min(width - 1, (int)sx));
                    int x1 = Math.Min(width - 1, x0 + 1);
                    double wx = sx - x0;
                    if (wx < 0) wx = 0;

                    int i00 = (y0 * width + x0) * 4;
                    int i01 = (y0 * width + x1) * 4;
                    int i10 = (y1 * width + x0) * 4;
                    int i11 = (y1 * width + x1) * 4;
                    int o = (y * newWidth + x) * 4;

                    for (int c = 0; c < 4; c++)
                    {
                        double top = pixels[i00 + c] * (1 - wx) + pixels[i01 + c] * wx;
                        double bottom = pixels[i10 + c] * (1 - wx) + pixels[i11 + c] * wx;
                        result[o + c] = (byte)(top * (1 - wy) + bottom * wy + 0.5);
                    }
                }
            }
            return result;
        }

        /// <summary>Uncompressed 32-bit BGRA TGA, bottom-up, matching the game's own.
        /// `rgba` is bottom-up. Shared with GameArtGenerator.</summary>
        internal static byte[] WriteTga(byte[] rgba, int width, int height)
        {
            byte[] tga = new byte[18 + width * height * 4];
            tga[2] = 2;                                   // uncompressed true-colour
            tga[12] = (byte)(width & 0xFF);
            tga[13] = (byte)((width >> 8) & 0xFF);
            tga[14] = (byte)(height & 0xFF);
            tga[15] = (byte)((height >> 8) & 0xFF);
            tga[16] = 32;                                 // bits per pixel
            tga[17] = 0x08;                               // 8 alpha bits, origin bottom-left

            for (int i = 0; i < width * height; i++)
            {
                int from = i * 4;
                int to = 18 + i * 4;
                tga[to] = rgba[from + 2];                 // B
                tga[to + 1] = rgba[from + 1];             // G
                tga[to + 2] = rgba[from];                 // R
                tga[to + 3] = rgba[from + 3];             // A
            }
            return tga;
        }
    }
}
