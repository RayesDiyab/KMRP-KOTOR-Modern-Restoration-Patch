// KMRP Font Converter: a font face to the game's font atlases.
//
// The rules are tools/build_font_from_ttf.py's, measured from the game's own atlases;
// read that file's notes before changing any of them:
//
//   * A slot is a byte of the game's text in Windows-1252. Control codes and the five
//     bytes the code page leaves undefined are blank.
//   * The engine draws one texel per pixel; `texturewidth * 100` is the atlas's width.
//   * A glyph's cell is its advance and nothing outside it is drawn, so a glyph whose
//     ink reaches past its advance gets a wider cell and is moved right inside it.
//   * No slot is zero wide: the game's word wrap loops until it runs out of memory on a
//     zero-wide glyph. A slot the face has no letter for keeps the width of KMRP's HD
//     Original font's glyph there.
//   * 4 pixels between glyphs, so filtering never reaches the next row's ink.
//
// The atlases are made at the HD Original font's size, six times the original fonts'
// (docs/hd-original-font.md), from its TXI headers: the same heights, baselines and
// spacing, so text keeps its place and size in every interface.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;

namespace KmrpFontConverter
{
    /// <summary>One of the game's fonts as KMRP's HD Original draws it.</summary>
    internal sealed class Reference
    {
        public string Resref;
        public int AtlasWidth;
        public List<string> Header = new List<string>();
        public int[] Widths;

        public int NumChars { get { return (int)Field("numchars"); } }
        public int GlyphHeight { get { return (int)Math.Round(Field("fontheight") * 100); } }
        public int Baseline { get { return (int)Math.Round(Field("baselineheight") * 100); } }

        public double Field(string name)
        {
            foreach (string line in Header)
            {
                string[] parts = line.Split(' ');
                if (parts.Length > 1 && parts[0] == name) return double.Parse(parts[1], CultureInfo.InvariantCulture);
            }
            return 0;
        }

        /// <summary>references.txt, made by make_data.py.</summary>
        public static Dictionary<string, Reference> Parse(string text)
        {
            var all = new Dictionary<string, Reference>();
            Reference current = null;
            foreach (string raw in text.Split('\n'))
            {
                string line = raw.TrimEnd('\r');
                if (line.StartsWith("font "))
                {
                    string[] parts = line.Split(' ');
                    current = new Reference { Resref = parts[1], AtlasWidth = int.Parse(parts[2], CultureInfo.InvariantCulture) };
                    all[current.Resref] = current;
                }
                else if (line.StartsWith("  widths "))
                    current.Widths = line.Substring(9).Split(' ').Select(s => int.Parse(s, CultureInfo.InvariantCulture)).ToArray();
                else if (line.StartsWith("  "))
                    current.Header.Add(line.Trim());
            }
            return all;
        }
    }

    internal static class Atlas
    {
        public const int Padding = 4;
        private static readonly Encoding Cp1252 = Encoding.GetEncoding(1252);

        /// <summary>The character slot `index` holds, or -1 for a blank one.</summary>
        public static int SlotCharacter(int index)
        {
            if (index < 0x20 || index == 0x7F || index > 0xFF) return -1;
            if (index == 0x81 || index == 0x8D || index == 0x8F || index == 0x90 || index == 0x9D) return -1;
            return Cp1252.GetString(new[] { (byte)index })[0];
        }

        /// <summary>The glyph a face draws in a slot: its own, a space for a missing
        /// no-break space, a hyphen for a missing soft hyphen; 0 when it has none.</summary>
        public static ushort SlotGlyph(LoadedFace face, int character)
        {
            ushort glyph = face.Glyph(character);
            if (glyph == 0 && character == 0xA0) glyph = face.Glyph(' ');
            if (glyph == 0 && character == 0xAD) glyph = face.Glyph('-');
            return glyph;
        }

        /// <summary>The letters of the game's text the face has no glyph for.</summary>
        public static List<char> Missing(LoadedFace face)
        {
            var missing = new List<char>();
            for (int i = 0x20; i < 0x100; i++)
            {
                int c = SlotCharacter(i);
                if (c >= 0 && SlotGlyph(face, c) == 0) missing.Add((char)c);
            }
            return missing;
        }

        /// <summary>What the glyph box holds, in design units above and below the baseline:
        /// the face's ascent and descent, or more where a letter of the game's text reaches
        /// further (a caron over a capital often does), so no letter is cut off.</summary>
        public static void Box(LoadedFace face, out float top, out float bottom)
        {
            if (face.BoxTop < 0)
            {
                float up = face.Ascent, down = face.Descent;
                for (int i = 0x20; i < 0x100; i++)
                {
                    int c = SlotCharacter(i);
                    ushort glyph = c >= 0 ? SlotGlyph(face, c) : (ushort)0;
                    if (glyph == 0) continue;
                    foreach (var contour in face.Outline(glyph, face.UnitsPerEm))
                        foreach (var p in contour) { up = Math.Max(up, -p.Y); down = Math.Max(down, p.Y); }
                }
                face.BoxTop = up;
                face.BoxBottom = down;
            }
            top = face.BoxTop;
            bottom = face.BoxBottom;
        }

        /// <summary>The atlas and TXI for one font, written into `folder`.</summary>
        public static void Write(LoadedFace face, Reference reference, string folder)
        {
            int height = reference.GlyphHeight;
            float top, bottom;
            Box(face, out top, out bottom);
            float scale = height / Math.Max(1, top + bottom);
            float em = face.UnitsPerEm * scale;
            float ascent = top * scale;
            int count = reference.NumChars;

            var widths = new int[count];
            var offsets = new float[count];
            var outlines = new List<List<PointF2>>[count];
            for (int i = 0; i < count; i++)
            {
                int c = SlotCharacter(i);
                ushort glyph = c >= 0 ? SlotGlyph(face, c) : (ushort)0;
                int advance = 0;
                if (glyph != 0)
                {
                    advance = (int)Math.Round(face.Advance(glyph) * scale);
                    var outline = face.Outline(glyph, em);
                    float minX = float.MaxValue, maxX = float.MinValue;
                    foreach (var contour in outline)
                        foreach (var p in contour) { minX = Math.Min(minX, p.X); maxX = Math.Max(maxX, p.X); }
                    if (minX <= maxX)
                    {
                        float left = Math.Min(0, minX);
                        float right = maxX - left;
                        if (right > advance) advance = (int)Math.Ceiling(right);
                        offsets[i] = -left;
                        outlines[i] = outline;
                    }
                }
                if (advance <= 0) advance = Math.Max(1, i < reference.Widths.Length ? reference.Widths[i] : height / 3);
                // An outlined font's letter gets its ring's width on both sides, so the
                // ring is never cut by the cell (KMRP's own HUD font: one side, the
                // original's letters leaving the other).
                float ringWidth;
                if (Outlined.TryGetValue(reference.Resref, out ringWidth))
                {
                    offsets[i] += ringWidth;
                    advance += (int)Math.Ceiling(2 * ringWidth);
                }
                widths[i] = advance;
            }

            int size = Math.Max(64, reference.AtlasWidth);
            List<Point> positions;
            while ((positions = Pack(widths, height, size)) == null) size *= 2;

            var alpha = new byte[size * size];
            byte[] ring = Outlined.ContainsKey(reference.Resref) ? new byte[size * size] : null;
            for (int i = 0; i < count; i++)
            {
                if (outlines[i] == null) continue;
                var cell = Rasterizer.Fill(outlines[i], widths[i], height, offsets[i], ascent);
                Point at = positions[i];
                for (int y = 0; y < height; y++)
                    Buffer.BlockCopy(cell, y * widths[i], alpha, (at.Y + y) * size + at.X, widths[i]);
                if (ring != null)
                {
                    byte[] spread = Spread(cell, widths[i], height, Outlined[reference.Resref]);
                    for (int y = 0; y < height; y++)
                        Buffer.BlockCopy(spread, y * widths[i], ring, (at.Y + y) * size + at.X, widths[i]);
                }
            }

            Directory.CreateDirectory(folder);
            WriteTga(Path.Combine(folder, reference.Resref + ".tga"), size, alpha, ring);
            File.WriteAllText(Path.Combine(folder, reference.Resref + ".txi"),
                Txi(reference, positions, widths, height, size), Encoding.ASCII);
        }

        // Fonts the game draws with a black ring round every letter, and its width at the
        // atlas's size: fnt_console, the HUD's numbers, one original pixel (six at the HD
        // size), as tools/build_hd_original_fonts.py (OUTLINED) gives KMRP's own.
        internal static readonly Dictionary<string, float> Outlined = new Dictionary<string, float> { { "fnt_console", 6f } };

        /// <summary>A cell's coverage spread by a disc `radius` pixels wide with a soft
        /// edge, inside the cell: the letter's black ring.</summary>
        internal static byte[] Spread(byte[] cell, int w, int h, float radius)
        {
            var spread = new byte[w * h];
            int reach = (int)Math.Ceiling(radius + 1);
            for (int dy = -reach; dy <= reach; dy++)
                for (int dx = -reach; dx <= reach; dx++)
                {
                    float weight = Math.Min(1f, Math.Max(0f, radius + 0.5f - (float)Math.Sqrt(dx * dx + dy * dy)));
                    if (weight <= 0) continue;
                    for (int y = Math.Max(0, dy); y < Math.Min(h, h + dy); y++)
                        for (int x = Math.Max(0, dx); x < Math.Min(w, w + dx); x++)
                        {
                            int v = (int)(cell[(y - dy) * w + x - dx] * weight);
                            if (v > spread[y * w + x]) spread[y * w + x] = (byte)v;
                        }
                }
            return spread;
        }

        private static List<Point> Pack(int[] widths, int height, int size)
        {
            var positions = new List<Point>(widths.Length);
            int x = 0, y = 0;
            foreach (int width in widths)
            {
                if (x + width + Padding > size) { x = 0; y += height + Padding; }
                if (y + height > size || width > size) return null;
                positions.Add(new Point(x, y));
                x += width + Padding;
            }
            return positions;
        }

        private static string Txi(Reference reference, List<Point> positions, int[] widths, int height, int size)
        {
            var b = new StringBuilder();
            foreach (string line in reference.Header)
            {
                string key = line.Split(' ')[0];
                if (key == "texturewidth") b.Append("texturewidth ").Append(F(size / 100.0)).Append('\n');
                else b.Append(line).Append('\n');
            }
            b.Append("upperleftcoords ").Append(positions.Count).Append('\n');
            foreach (var p in positions)
                b.Append(F(p.X / (double)size)).Append(' ').Append(F(1.0 - p.Y / (double)size)).Append(" 0\n");
            b.Append("lowerrightcoords ").Append(positions.Count).Append('\n');
            for (int i = 0; i < positions.Count; i++)
                b.Append(F((positions[i].X + widths[i]) / (double)size)).Append(' ')
                 .Append(F(1.0 - (positions[i].Y + height) / (double)size)).Append(" 0\n");
            return b.ToString();
        }

        private static string F(double v) { return v.ToString("0.000000", CultureInfo.InvariantCulture); }

        /// <summary>Uncompressed 32-bit TGA, bottom-up like the game's own: white ink, the
        /// glyphs in alpha.</summary>
        private static void WriteTga(string path, int size, byte[] alpha, byte[] ring = null)
        {
            using (var file = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
            {
                var header = new byte[18];
                header[2] = 2;
                header[12] = (byte)size; header[13] = (byte)(size >> 8);
                header[14] = (byte)size; header[15] = (byte)(size >> 8);
                header[16] = 32; header[17] = 8;
                file.Write(header, 0, 18);
                var row = new byte[size * 4];
                for (int y = size - 1; y >= 0; y--)
                {
                    for (int x = 0; x < size; x++)
                    {
                        int o = x * 4, i = y * size + x;
                        if (ring == null)
                        {
                            row[o] = row[o + 1] = row[o + 2] = 255;
                            row[o + 3] = alpha[i];
                            continue;
                        }
                        // White letter over its black ring.
                        float a = alpha[i] / 255f, r = ring[i] / 255f, total = a + r * (1 - a);
                        byte white = (byte)(total > 0 ? Math.Round(255 * a / total) : 0);
                        row[o] = row[o + 1] = row[o + 2] = white;
                        row[o + 3] = (byte)Math.Round(total * 255);
                    }
                    file.Write(row, 0, row.Length);
                }
            }
        }

        /// <summary>A line of text in the face, as the tiles show it: the glyph box
        /// `boxHeight` pixels high, the face's ascent and descent fitted into it as the
        /// atlases are.</summary>
        public static Bitmap Line(LoadedFace face, string text, float boxHeight, Color colour, float ringRadius = 0)
        {
            float top, bottom;
            Box(face, out top, out bottom);
            float scale = boxHeight / Math.Max(1, top + bottom);
            float em = face.UnitsPerEm * scale, ascent = top * scale;
            var glyphs = new List<KeyValuePair<float, List<List<PointF2>>>>();
            float pen = 0, minX = 0, maxX = 1;
            foreach (char c in text)
            {
                ushort glyph = SlotGlyph(face, c);
                if (glyph == 0) { pen += boxHeight / 3; continue; }
                var outline = face.Outline(glyph, em);
                foreach (var contour in outline)
                    foreach (var p in contour) { minX = Math.Min(minX, pen + p.X); maxX = Math.Max(maxX, pen + p.X); }
                glyphs.Add(new KeyValuePair<float, List<List<PointF2>>>(pen, outline));
                pen += face.Advance(glyph) * scale;
            }
            maxX = Math.Max(maxX, pen);
            int width = (int)Math.Ceiling(maxX - minX) + 2, height = (int)Math.Ceiling(boxHeight) + 2;
            var all = new List<List<PointF2>>();
            foreach (var g in glyphs)
                foreach (var contour in g.Value)
                    all.Add(contour.Select(p => new PointF2(p.X + g.Key, p.Y)).ToList());
            int pad = (int)Math.Ceiling(ringRadius) + 1;
            width += 2 * pad;
            height += 2 * pad;
            byte[] cover = Rasterizer.Fill(all, width, height, 1 - minX + pad, ascent + 1 + pad);
            byte[] ring = ringRadius > 0 ? Spread(cover, width, height, ringRadius) : null;
            var bitmap = new Bitmap(width, height, PixelFormat.Format32bppPArgb);
            var data = bitmap.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.WriteOnly, PixelFormat.Format32bppPArgb);
            var pixels = new byte[data.Stride * height];
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++)
                {
                    // Premultiplied: the coloured letter over its black ring, if any.
                    int a = cover[y * width + x], o = y * data.Stride + x * 4;
                    int r = ring == null ? 0 : ring[y * width + x];
                    int total = a + r * (255 - a) / 255;
                    pixels[o] = (byte)(colour.B * a / 255);
                    pixels[o + 1] = (byte)(colour.G * a / 255);
                    pixels[o + 2] = (byte)(colour.R * a / 255);
                    pixels[o + 3] = (byte)total;
                }
            Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
            bitmap.UnlockBits(data);
            bitmap.Tag = new[] { (int)Math.Ceiling(boxHeight), pad };   // the box asked for, and the margin round it
            return bitmap;
        }
    }

    /// <summary>Exact-area coverage of filled outlines: every pixel the share of it the
    /// shape covers, so edges are smooth at any size without supersampling.</summary>
    internal static class Rasterizer
    {
        public static byte[] Fill(List<List<PointF2>> contours, int width, int height, float dx, float dy)
        {
            int stride = width + 2;
            var acc = new float[stride * height];
            foreach (var contour in contours)
                for (int i = 0; i < contour.Count; i++)
                {
                    PointF2 a = contour[i], b = contour[(i + 1) % contour.Count];
                    Line(acc, stride, width, height, a.X + dx, a.Y + dy, b.X + dx, b.Y + dy);
                }
            var cover = new byte[width * height];
            for (int y = 0; y < height; y++)
            {
                float sum = 0;
                for (int x = 0; x < width; x++)
                {
                    sum += acc[y * stride + x];
                    float v = Math.Min(1f, Math.Abs(sum));
                    cover[y * width + x] = (byte)(v * 255 + 0.5f);
                }
            }
            return cover;
        }

        // One edge's signed area into the accumulation buffer (as in font-rs): a cell gets
        // the area left of the edge inside it, the running sum along a row then fills.
        private static void Line(float[] acc, int stride, int width, int height, float x0, float y0, float x1, float y1)
        {
            if (y0 == y1) return;
            float dir = 1;
            if (y0 > y1) { dir = -1; float t = x0; x0 = x1; x1 = t; t = y0; y0 = y1; y1 = t; }
            x0 = Clamp(x0, 0, width); x1 = Clamp(x1, 0, width);
            float dxdy = (x1 - x0) / (y1 - y0);
            float x = x0;
            if (y0 < 0) { x -= y0 * dxdy; y0 = 0; }
            if (y1 > height) y1 = height;
            if (y0 >= y1) return;
            int yStart = (int)Math.Floor(y0), yEnd = (int)Math.Ceiling(y1);
            for (int y = yStart; y < yEnd; y++)
            {
                int row = y * stride;
                float dy = Math.Min(y + 1, y1) - Math.Max(y, y0);
                float xNext = x + dxdy * dy;
                float d = dy * dir;
                float xa = Math.Min(x, xNext), xb = Math.Max(x, xNext);
                int xaFloor = (int)Math.Floor(xa);
                float xbCeil = (float)Math.Ceiling(xb);
                if (xbCeil <= xaFloor + 1)
                {
                    float xmf = 0.5f * (x + xNext) - xaFloor;
                    acc[row + xaFloor] += d - d * xmf;
                    acc[row + xaFloor + 1] += d * xmf;
                }
                else
                {
                    float s = 1 / (xb - xa);
                    float xaf = xa - xaFloor;
                    float a0 = 0.5f * s * (1 - xaf) * (1 - xaf);
                    float xbf = xb - xbCeil + 1;
                    float am = 0.5f * s * xbf * xbf;
                    int xbInt = (int)xbCeil;
                    acc[row + xaFloor] += d * a0;
                    if (xbInt == xaFloor + 2) acc[row + xaFloor + 1] += d * (1 - a0 - am);
                    else
                    {
                        float a1 = s * (1.5f - xaf);
                        acc[row + xaFloor + 1] += d * (a1 - a0);
                        for (int xi = xaFloor + 2; xi < xbInt - 1; xi++) acc[row + xi] += d * s;
                        float a2 = a1 + (xbInt - xaFloor - 3) * s;
                        acc[row + xbInt - 1] += d * (1 - a2 - am);
                    }
                    acc[row + xbInt] += d * am;
                }
                x = xNext;
            }
        }

        private static float Clamp(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }
    }
}
