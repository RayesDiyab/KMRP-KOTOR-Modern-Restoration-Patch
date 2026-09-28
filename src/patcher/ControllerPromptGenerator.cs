using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace Kmrp
{
    /// <summary>
    /// Slides each controller prompt badge to sit beside the label the player's
    /// own game actually draws, instead of beside the English one the build
    /// measured.
    ///
    /// All ten prompt buttons carry TEXT.STRREF and no inline TEXT string, so
    /// their label is whatever the installed dialog.tlk holds for that reference.
    /// The build cannot know it: dialog.tlk is a proprietary game file and is not
    /// a build input, so the shipped textures are placed against the retail
    /// English wording. On a localised install those widths are wrong, and the
    /// badge drifts away from the words it belongs to.
    ///
    /// Nothing is re-rendered here. The badge artwork does not depend on the
    /// label at all -- only its horizontal position does, and the engine centres
    /// the label, so the position moves by exactly half of any change in label
    /// width:
    ///
    ///     center_x = (control_width - label_width) / 2 - gap - radius
    ///
    /// So this reads the placement manifest the build wrote into the same
    /// resolution layout, resolves the STRREFs against the real dialog.tlk, measures with
    /// the font advances carried in that manifest, and shifts the already
    /// composited pixels sideways. A whole number of texels, which is at most
    /// about 1.5 screen pixels of quantisation on the widest button -- far below
    /// the roughly 13px gap being aimed for, and it preserves the artwork's
    /// antialiasing exactly, which a resample would not.
    ///
    /// Never throws. A missing, unreadable or unexpected dialog.tlk just means
    /// the shipped English placement stands, which is what shipped before this
    /// existed.
    /// </summary>
    internal static class ControllerPromptGenerator
    {
        internal const string ManifestName = "kmrp_prompts.txt";
        private const int TgaHeaderSize = 18;
        private const int TlkHeaderSize = 20;
        private const int TlkEntrySize = 40;
        private const int TlkTextPresent = 0x1;

        // Must match build_controller_prompt_textures.py.
        private const double RadiusFactor = 0.29;
        private const double GapFactor = 0.55;
        private const double EdgeFactor = 1.15;

        private sealed class Prompt
        {
            internal string ResRef;
            internal int ControlWidth;
            internal int ControlHeight;
            internal double BakedLabelWidth;
            internal List<int[]> Variants;   // each variant is joined with spaces
        }

        internal static string DialogTlkPath(string executablePath)
        {
            string gameRoot = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            return Path.Combine(gameRoot, "dialog.tlk");
        }

        /// <summary>
        /// Relative Override path -> replacement bytes, for the prompt textures
        /// whose badge needs to move. Null when there is nothing to do.
        /// </summary>
        internal static Dictionary<string, byte[]> TryBuild(string executablePath,
                                                            GuiPool layout)
        {
            try
            {
                string tlkPath = DialogTlkPath(executablePath);
                if (!File.Exists(tlkPath))
                    return null;

                int textureWidth = 0;
                int textureHeight = 0;
                double spacing = 0.0;
                double[] advances = null;
                List<Prompt> prompts = new List<Prompt>();
                Dictionary<string, byte[]> baked =
                    new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);

                if (!ReadLayout(layout, prompts, baked,
                                 ref textureWidth, ref textureHeight,
                                 ref spacing, ref advances))
                    return null;
                if (advances == null || prompts.Count == 0)
                    return null;

                Dictionary<int, byte[]> strings = ReadTlkStrings(tlkPath, prompts);
                if (strings == null)
                    return null;

                Dictionary<string, byte[]> replacements =
                    new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);

                foreach (Prompt prompt in prompts)
                {
                    double measured = WidestVariant(prompt, strings, advances, spacing);
                    if (measured <= 0.0)
                        continue;   // no variant resolved; keep the shipped placement

                    double shift = CenterFor(prompt, measured)
                                 - CenterFor(prompt, prompt.BakedLabelWidth);
                    int texels = (int)Math.Round(shift * textureWidth / prompt.ControlWidth);
                    if (texels == 0)
                        continue;

                    string name = prompt.ResRef + ".tga";
                    byte[] source;
                    if (!baked.TryGetValue(name, out source))
                        continue;
                    byte[] shifted = ShiftColumns(source, textureWidth, textureHeight, texels);
                    if (shifted != null)
                        replacements[name] = shifted;
                }

                return replacements.Count > 0 ? replacements : null;
            }
            catch (IOException)
            {
                return null;
            }
            catch (UnauthorizedAccessException)
            {
                return null;
            }
            catch (InvalidDataException)
            {
                return null;
            }
            catch (FormatException)
            {
                return null;
            }
        }

        /// <summary>The badge centre this build's own formula produces, including
        /// its edge clamp, so the shift is exact rather than an approximation of
        /// it near the button's left edge.</summary>
        private static double CenterFor(Prompt prompt, double labelWidth)
        {
            double radius = prompt.ControlHeight * RadiusFactor;
            if (labelWidth <= 0.0)
                return prompt.ControlHeight * 0.58;
            double gap = radius * GapFactor;
            double center = (prompt.ControlWidth - labelWidth) / 2.0 - gap - radius;
            if (center < radius * EdgeFactor)
                center = radius * EdgeFactor;
            double rightLimit = prompt.ControlWidth - radius * EdgeFactor;
            if (center > rightLimit)
                center = rightLimit;
            return center;
        }

        /// <summary>The widest wording the button can show. A badge measured
        /// against the narrower variant would be overlapped by the wider one.</summary>
        private static double WidestVariant(Prompt prompt, Dictionary<int, byte[]> strings,
                                            double[] advances, double spacing)
        {
            double widest = 0.0;
            foreach (int[] variant in prompt.Variants)
            {
                List<byte> line = new List<byte>();
                bool complete = true;
                for (int part = 0; part < variant.Length; part++)
                {
                    byte[] text;
                    if (!strings.TryGetValue(variant[part], out text) || text == null)
                    {
                        complete = false;
                        break;
                    }
                    if (part > 0)
                        line.Add((byte)' ');
                    line.AddRange(text);
                }
                if (!complete || line.Count == 0)
                    continue;
                double width = Measure(line, advances, spacing);
                if (width > widest)
                    widest = width;
            }
            return widest;
        }

        /// <summary>
        /// Measures by BYTE, not by decoded character. KOTOR's font atlases are
        /// 256-glyph tables indexed by the raw byte, and dialog.tlk stores text in
        /// the single-byte codepage of its language, so the byte value IS the
        /// glyph index. Decoding first would be an extra step that can only lose.
        /// </summary>
        private static double Measure(List<byte> text, double[] advances, double spacing)
        {
            double total = 0.0;
            for (int index = 0; index < text.Count; index++)
            {
                int code = text[index];
                if (code < advances.Length)
                    total += advances[code];
                if (index > 0)
                    total += spacing;
            }
            return total;
        }

        private static bool ReadLayout(GuiPool layout, List<Prompt> prompts,
                                       Dictionary<string, byte[]> baked,
                                       ref int textureWidth, ref int textureHeight,
                                       ref double spacing, ref double[] advances)
        {
            ZipArchiveEntry manifest = layout.GetEntry(ManifestName);
            if (manifest == null)
                return false;   // a layout from before this existed
            using (StreamReader reader = new StreamReader(manifest.Open(), Encoding.UTF8))
                ParseManifest(reader, prompts, ref textureWidth, ref textureHeight,
                              ref spacing, ref advances);
            if (prompts.Count == 0)
                return false;

            foreach (Prompt prompt in prompts)
            {
                string name = prompt.ResRef + ".tga";
                ZipArchiveEntry entry = layout.GetEntry(name);
                if (entry == null)
                    continue;
                using (Stream input = entry.Open())
                using (MemoryStream buffer = new MemoryStream())
                {
                    input.CopyTo(buffer);
                    baked[name] = buffer.ToArray();
                }
            }
            return true;
        }

        private static void ParseManifest(StreamReader reader, List<Prompt> prompts,
                                          ref int textureWidth, ref int textureHeight,
                                          ref double spacing, ref double[] advances)
        {
            CultureInfo invariant = CultureInfo.InvariantCulture;
            string line;
            while ((line = reader.ReadLine()) != null)
            {
                if (line.Length == 0 || line[0] == '#')
                    continue;
                string[] parts = line.Split(' ');
                if (parts[0] == "texture" && parts.Length >= 3)
                {
                    textureWidth = Int32.Parse(parts[1], invariant);
                    textureHeight = Int32.Parse(parts[2], invariant);
                }
                else if (parts[0] == "spacing" && parts.Length >= 2)
                {
                    spacing = Double.Parse(parts[1], invariant);
                }
                else if (parts[0] == "advances" && parts.Length >= 2)
                {
                    advances = new double[parts.Length - 1];
                    for (int index = 1; index < parts.Length; index++)
                        advances[index - 1] = Double.Parse(parts[index], invariant);
                }
                else if (parts[0] == "prompt" && parts.Length >= 6)
                {
                    Prompt prompt = new Prompt();
                    prompt.ResRef = parts[1];
                    prompt.ControlWidth = Int32.Parse(parts[2], invariant);
                    prompt.ControlHeight = Int32.Parse(parts[3], invariant);
                    prompt.BakedLabelWidth = Double.Parse(parts[4], invariant);
                    prompt.Variants = new List<int[]>();
                    if (parts[5] != "-")
                    {
                        foreach (string variant in parts[5].Split(';'))
                        {
                            string[] refs = variant.Split('+');
                            int[] parsed = new int[refs.Length];
                            for (int index = 0; index < refs.Length; index++)
                                parsed[index] = Int32.Parse(refs[index], invariant);
                            prompt.Variants.Add(parsed);
                        }
                    }
                    if (prompt.ControlWidth > 0 && prompt.ControlHeight > 0
                        && prompt.Variants.Count > 0)
                        prompts.Add(prompt);
                }
            }
        }

        /// <summary>
        /// The raw bytes of just the STRREFs these prompts need. Reading a
        /// 5 MB dialog.tlk in full to pull ten short strings would be wasteful, so
        /// only the string table entries are walked and only the needed text is
        /// copied out.
        /// </summary>
        private static Dictionary<int, byte[]> ReadTlkStrings(string path, List<Prompt> prompts)
        {
            HashSet<int> wanted = new HashSet<int>();
            foreach (Prompt prompt in prompts)
                foreach (int[] variant in prompt.Variants)
                    foreach (int reference in variant)
                        wanted.Add(reference);
            if (wanted.Count == 0)
                return null;

            using (FileStream file = new FileStream(path, FileMode.Open, FileAccess.Read,
                                                    FileShare.ReadWrite))
            using (BinaryReader reader = new BinaryReader(file))
            {
                if (file.Length < TlkHeaderSize)
                    return null;
                byte[] signature = reader.ReadBytes(8);
                if (Encoding.ASCII.GetString(signature) != "TLK V3.0")
                    return null;
                reader.ReadUInt32();                        // language id
                uint count = reader.ReadUInt32();
                uint entriesOffset = reader.ReadUInt32();
                if (count == 0 || count > 1000000)
                    return null;

                Dictionary<int, byte[]> found = new Dictionary<int, byte[]>();
                foreach (int reference in wanted)
                {
                    if (reference < 0 || reference >= count)
                        continue;
                    long entry = TlkHeaderSize + (long)reference * TlkEntrySize;
                    if (entry + TlkEntrySize > file.Length)
                        continue;
                    file.Position = entry;
                    uint flags = reader.ReadUInt32();
                    if ((flags & TlkTextPresent) == 0)
                        continue;
                    file.Position = entry + 28;
                    uint textOffset = reader.ReadUInt32();
                    uint textSize = reader.ReadUInt32();
                    if (textSize == 0 || textSize > 4096)
                        continue;
                    long start = (long)entriesOffset + textOffset;
                    if (start < 0 || start + textSize > file.Length)
                        continue;
                    file.Position = start;
                    byte[] text = reader.ReadBytes((int)textSize);
                    if (text.Length == (int)textSize)
                        found[reference] = text;
                }
                return found.Count > 0 ? found : null;
            }
        }

        /// <summary>
        /// Translates the image horizontally by whole texels. The TGA is
        /// uncompressed 32-bit BGRA with a bottom-left origin, so rows are
        /// independent and a byte move within each row is the whole operation --
        /// row order does not matter for a horizontal shift.
        ///
        /// The columns the shift vacates repeat the edge column that moved away
        /// from them. On every ordinary badge that column is fully transparent
        /// (all 26,460 badge textures of the 2026-09-26 build), so nothing
        /// changes for them; a badge that stands on its button's own uniform box
        /// (Level Up and Auto Level Up carry dialog2) keeps an unbroken box
        /// instead of a transparent gap.
        /// </summary>
        private static byte[] ShiftColumns(byte[] tga, int width, int height, int texels)
        {
            int stride = width * 4;
            long pixels = (long)stride * height;
            if (tga.Length < TgaHeaderSize + pixels)
                return null;
            // Refuse anything that is not the shape this build writes, rather than
            // reinterpreting somebody else's texture as if it were ours.
            if (tga[2] != 2 || tga[16] != 32)
                return null;
            if (BitConverter.ToUInt16(tga, 12) != width || BitConverter.ToUInt16(tga, 14) != height)
                return null;
            if (Math.Abs(texels) >= width)
                return null;

            byte[] result = new byte[tga.Length];
            Buffer.BlockCopy(tga, 0, result, 0, TgaHeaderSize);
            // Everything past the pixel block (the TGA footer) is carried through.
            int tail = TgaHeaderSize + (int)pixels;
            if (tga.Length > tail)
                Buffer.BlockCopy(tga, tail, result, tail, tga.Length - tail);

            int shiftBytes = Math.Abs(texels) * 4;
            int copyBytes = stride - shiftBytes;
            for (int row = 0; row < height; row++)
            {
                int rowStart = TgaHeaderSize + row * stride;
                if (texels > 0)
                {
                    Buffer.BlockCopy(tga, rowStart, result, rowStart + shiftBytes, copyBytes);
                    for (int column = 0; column < texels; column++)
                        Buffer.BlockCopy(tga, rowStart, result, rowStart + column * 4, 4);
                }
                else
                {
                    Buffer.BlockCopy(tga, rowStart + shiftBytes, result, rowStart, copyBytes);
                    int last = rowStart + stride - 4;
                    for (int column = width + texels; column < width; column++)
                        Buffer.BlockCopy(tga, last, result, rowStart + column * 4, 4);
                }
            }
            return result;
        }
    }
}
