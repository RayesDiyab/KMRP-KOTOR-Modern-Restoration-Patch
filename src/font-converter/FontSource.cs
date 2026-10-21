// KMRP Font Converter: reading font files through Windows' own DirectWrite.
//
// DirectWrite reads every format the converter accepts: TrueType and OpenType (both
// outline kinds), collections (.ttc, .otc), WOFF and WOFF2 (unpacked first, Windows 10
// 1703 and later), and variable fonts (one face per named instance, Windows 10 1809 and
// later). Nothing else in Windows does all of these, and no font library has to ship.
//
// The interfaces are called through their vtables. The slot numbers are counted from
// the Windows SDK headers (dwrite.h to dwrite_3.h, 10.0.26100.0): IUnknown takes 0 to 2,
// then each interface's methods in declaration order, after those of the interface it
// extends. Two overloads of one name sit next to each other in their vtable, so they
// move no other method.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace KmrpFontConverter
{
    /// <summary>One face of a font file: what the player picks.</summary>
    internal sealed class FontFaceChoice
    {
        public string Path;
        public int FaceIndex;
        public float[] Axes;          // tag/value pairs of a variable font's instance, or null
        public string Name;           // as shown to the player
    }

    /// <summary>A loaded face, ready to give glyph outlines.</summary>
    internal sealed class LoadedFace : IDisposable
    {
        internal IntPtr Face;
        public int UnitsPerEm, Ascent, Descent;
        public float BoxTop = -1, BoxBottom = -1;   // Atlas.Box, once a face
        public string Name;

        public void Dispose()
        {
            if (Face != IntPtr.Zero) { Marshal.Release(Face); Face = IntPtr.Zero; }
        }

        public ushort Glyph(int codePoint)
        {
            uint cp = (uint)codePoint;
            ushort glyph;
            Dw.Check(Dw.Fn<Dw.GetGlyphIndicesFn>(Face, 11)(Face, ref cp, 1, out glyph));
            return glyph;
        }

        public int Advance(ushort glyph)
        {
            Dw.GlyphMetrics metrics;
            var fn = Dw.Fn<Dw.GetDesignGlyphMetricsFn>(Face, 10);
            Dw.Check(fn(Face, ref glyph, 1, out metrics, 0));
            return (int)metrics.advanceWidth;
        }

        /// <summary>The glyph's outline at `emSize` pixels, y down, origin on the baseline.</summary>
        public List<List<PointF2>> Outline(ushort glyph, float emSize)
        {
            var sink = new OutlineSink();
            IntPtr sinkPtr = Marshal.GetComInterfaceForObject(sink, typeof(ISimplifiedGeometrySink));
            try
            {
                var fn = Dw.Fn<Dw.GetGlyphRunOutlineFn>(Face, 14);
                Dw.Check(fn(Face, emSize, ref glyph, IntPtr.Zero, IntPtr.Zero, 1, 0, 0, sinkPtr));
            }
            finally { Marshal.Release(sinkPtr); }
            return sink.Contours;
        }

        public byte[] Table(string tag)
        {
            uint key = (uint)(tag[0] | tag[1] << 8 | tag[2] << 16 | tag[3] << 24);
            IntPtr data, context;
            uint size;
            int exists;
            var fn = Dw.Fn<Dw.TryGetFontTableFn>(Face, 12);
            Dw.Check(fn(Face, key, out data, out size, out context, out exists));
            if (exists == 0) return null;
            var bytes = new byte[size];
            Marshal.Copy(data, bytes, 0, (int)size);
            Dw.Fn<Dw.ReleaseFontTableFn>(Face, 13)(Face, context);
            return bytes;
        }
    }

    internal struct PointF2
    {
        public float X, Y;
        public PointF2(float x, float y) { X = x; Y = y; }
    }

    internal static class FontFiles
    {
        public static readonly string[] Extensions = { ".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2" };

        public static bool Accepted(string path)
        {
            return Array.IndexOf(Extensions, (System.IO.Path.GetExtension(path) ?? "").ToLowerInvariant()) >= 0;
        }

        /// <summary>Every face the player can pick from a file: one per face of a collection,
        /// and one per named instance of a variable font. Throws with a message for the
        /// player when the file is not a font DirectWrite can read.</summary>
        public static List<FontFaceChoice> Faces(string path)
        {
            string real = Unpacked(path);
            var choices = new List<FontFaceChoice>();
            IntPtr file = Dw.FileReference(real);
            try
            {
                int supported, fileType, faceType;
                uint count;
                Dw.Check(Dw.Fn<Dw.AnalyzeFn>(file, 5)(file, out supported, out fileType, out faceType, out count));
                if (supported == 0 || count == 0) throw new InvalidDataException("This file is not a font Windows can read.");
                for (int i = 0; i < count; i++)
                {
                    using (var face = Load(new FontFaceChoice { Path = path, FaceIndex = i }))
                    {
                        var instances = NamedInstances(face);
                        if (instances.Count == 0)
                            choices.Add(new FontFaceChoice { Path = path, FaceIndex = i, Name = face.Name });
                        foreach (var instance in instances)
                        {
                            instance.Path = path;
                            instance.FaceIndex = i;
                            choices.Add(instance);
                        }
                    }
                }
            }
            finally { Marshal.Release(file); }
            return choices;
        }

        public static LoadedFace Load(FontFaceChoice choice)
        {
            string real = Unpacked(choice.Path);
            IntPtr file = Dw.FileReference(real);
            IntPtr face;
            try
            {
                if (choice.Axes != null)
                {
                    IntPtr resource;
                    Dw.Check(Dw.Fn<Dw.CreateFontResourceFn>(Dw.Factory6, 49)(Dw.Factory6, file, (uint)choice.FaceIndex, out resource));
                    try
                    {
                        Dw.Check(Dw.Fn<Dw.ResourceCreateFontFaceFn>(resource, 13)(resource, 0, choice.Axes, (uint)(choice.Axes.Length / 2), out face));
                    }
                    finally { Marshal.Release(resource); }
                }
                else
                {
                    int supported, fileType, faceType;
                    uint count;
                    Dw.Check(Dw.Fn<Dw.AnalyzeFn>(file, 5)(file, out supported, out fileType, out faceType, out count));
                    IntPtr[] files = { file };
                    Dw.Check(Dw.Fn<Dw.CreateFontFaceFn>(Dw.Factory, 9)(Dw.Factory, faceType, 1, files, (uint)choice.FaceIndex, 0, out face));
                }
            }
            finally { Marshal.Release(file); }
            var loaded = new LoadedFace { Face = face };
            Dw.FontMetrics metrics;
            Dw.Fn<Dw.GetMetricsFn>(face, 8)(face, out metrics);
            loaded.UnitsPerEm = metrics.designUnitsPerEm;
            loaded.Ascent = metrics.ascent;
            loaded.Descent = metrics.descent;
            loaded.Name = choice.Name ?? FullName(loaded) ?? System.IO.Path.GetFileNameWithoutExtension(choice.Path);
            return loaded;
        }

        // A WOFF or WOFF2 file, unpacked once to a plain font in the temp folder: DirectWrite
        // unpacks them but reads faces only from a font file.
        private static readonly Dictionary<string, string> unpacked = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        private static string Unpacked(string path)
        {
            string ext = (System.IO.Path.GetExtension(path) ?? "").ToLowerInvariant();
            if (ext != ".woff" && ext != ".woff2") return path;
            string done;
            if (unpacked.TryGetValue(path, out done) && File.Exists(done)) return done;
            byte[] data = File.ReadAllBytes(path);
            // WOFF is read here, so it needs nothing newer than DirectWrite's first version
            // (Windows 7, and Wine under Proton); WOFF2 needs DirectWrite to unpack it.
            byte[] font = ext == ".woff" ? Woff(data) : DirectWriteUnpack(data);
            string folder = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "KMRP Font Converter");
            Directory.CreateDirectory(folder);
            done = System.IO.Path.Combine(folder, Guid.NewGuid().ToString("N") + ".otf");
            File.WriteAllBytes(done, font);
            unpacked[path] = done;
            return done;
        }

        private static byte[] DirectWriteUnpack(byte[] data)
        {
            const string old = "WOFF2 fonts need Windows 10 or newer. Pick the font's TTF or OTF instead.";
            if (Dw.Factory5 == IntPtr.Zero) throw new InvalidDataException(old);
            IntPtr stream;
            GCHandle pin = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                int hr = Dw.Fn<Dw.UnpackFontFileFn>(Dw.Factory5, 47)(Dw.Factory5, 2, pin.AddrOfPinnedObject(), (uint)data.Length, out stream);
                if (hr < 0) throw new InvalidDataException("This web font could not be unpacked. Pick the font's TTF or OTF instead.");
            }
            finally { pin.Free(); }
            try
            {
                ulong size;
                Dw.Check(Dw.Fn<Dw.GetFileSizeFn>(stream, 5)(stream, out size));
                IntPtr fragment, context;
                Dw.Check(Dw.Fn<Dw.ReadFileFragmentFn>(stream, 3)(stream, out fragment, 0, size, out context));
                var font = new byte[size];
                Marshal.Copy(fragment, font, 0, (int)size);
                Dw.Fn<Dw.ReleaseFileFragmentFn>(stream, 4)(stream, context);
                return font;
            }
            finally { Marshal.Release(stream); }
        }

        /// <summary>A WOFF 1.0 file back to the font it packs: each table inflated (zlib)
        /// and laid out again behind a plain table directory.</summary>
        private static byte[] Woff(byte[] w)
        {
            if (w.Length < 44 || U32(w, 0) != 0x774F4646) throw new InvalidDataException("This is not a WOFF font.");
            uint flavor = U32(w, 4);
            int tables = U16(w, 12);
            var tags = new uint[tables];
            var bodies = new byte[tables][];
            var sums = new uint[tables];
            for (int i = 0; i < tables; i++)
            {
                int r = 44 + i * 20;
                tags[i] = U32(w, r);
                int offset = (int)U32(w, r + 4), compressed = (int)U32(w, r + 8), length = (int)U32(w, r + 12);
                sums[i] = U32(w, r + 16);
                if (offset + compressed > w.Length) throw new InvalidDataException("This WOFF font is damaged.");
                var body = new byte[length];
                if (compressed == length) Buffer.BlockCopy(w, offset, body, 0, length);
                else
                    using (var inflate = new System.IO.Compression.DeflateStream(
                        new MemoryStream(w, offset + 2, compressed - 2), System.IO.Compression.CompressionMode.Decompress))
                    {
                        int read = 0, got;
                        while (read < length && (got = inflate.Read(body, read, length - read)) > 0) read += got;
                    }
                bodies[i] = body;
            }
            var output = new MemoryStream();
            var head = new byte[12 + 16 * tables];
            Put32(head, 0, flavor);
            int power = 1, log = 0;
            while (power * 2 <= tables) { power *= 2; log++; }
            Put16(head, 4, tables); Put16(head, 6, power * 16); Put16(head, 8, log); Put16(head, 10, tables * 16 - power * 16);
            int at = head.Length;
            for (int i = 0; i < tables; i++)
            {
                int r = 12 + i * 16;
                Put32(head, r, tags[i]); Put32(head, r + 4, sums[i]); Put32(head, r + 8, (uint)at); Put32(head, r + 12, (uint)bodies[i].Length);
                at += (bodies[i].Length + 3) & ~3;
            }
            output.Write(head, 0, head.Length);
            foreach (var body in bodies)
            {
                output.Write(body, 0, body.Length);
                output.Write(new byte[3], 0, ((body.Length + 3) & ~3) - body.Length);
            }
            return output.ToArray();
        }

        private static void Put16(byte[] b, int o, int v) { b[o] = (byte)(v >> 8); b[o + 1] = (byte)v; }
        private static void Put32(byte[] b, int o, uint v) { b[o] = (byte)(v >> 24); b[o + 1] = (byte)(v >> 16); b[o + 2] = (byte)(v >> 8); b[o + 3] = (byte)v; }

        // ---- the 'name' and 'fvar' tables, read directly ----

        private static ushort U16(byte[] b, int o) { return (ushort)(b[o] << 8 | b[o + 1]); }
        private static uint U32(byte[] b, int o) { return (uint)(b[o] << 24 | b[o + 1] << 16 | b[o + 2] << 8 | b[o + 3]); }

        /// <summary>A name from the 'name' table, English Windows first.</summary>
        public static string NameRecord(LoadedFace face, int id)
        {
            byte[] t = face.Table("name");
            if (t == null || t.Length < 6) return null;
            int count = U16(t, 2), strings = U16(t, 4);
            string best = null;
            int bestScore = -1;
            for (int i = 0; i < count; i++)
            {
                int r = 6 + i * 12;
                if (r + 12 > t.Length) break;
                int platform = U16(t, r), encoding = U16(t, r + 2), language = U16(t, r + 4), name = U16(t, r + 6);
                int length = U16(t, r + 8), offset = U16(t, r + 10);
                if (name != id || strings + offset + length > t.Length) continue;
                int score = platform == 3 && language == 0x409 ? 3 : platform == 3 ? 2 : platform == 0 ? 1 : platform == 1 && encoding == 0 ? 0 : -1;
                if (score <= bestScore) continue;
                string text = platform == 1
                    ? Encoding.GetEncoding(10000).GetString(t, strings + offset, length)
                    : Encoding.BigEndianUnicode.GetString(t, strings + offset, length);
                best = text.Trim();
                bestScore = score;
            }
            return string.IsNullOrEmpty(best) ? null : best;
        }

        private static string FullName(LoadedFace face)
        {
            return NameRecord(face, 4) ?? NameRecord(face, 1);
        }

        /// <summary>A variable font's named instances ("Light", "Bold"...), as faces.</summary>
        private static List<FontFaceChoice> NamedInstances(LoadedFace face)
        {
            var list = new List<FontFaceChoice>();
            if (Dw.Factory6 == IntPtr.Zero) return list;   // before Windows 10 1809: the default instance only
            byte[] t = face.Table("fvar");
            if (t == null || t.Length < 16) return list;
            int axesOffset = U16(t, 4), axisCount = U16(t, 8), axisSize = U16(t, 10);
            int instanceCount = U16(t, 12), instanceSize = U16(t, 14);
            if (axisCount == 0 || axisSize < 20) return list;
            var tags = new uint[axisCount];
            for (int a = 0; a < axisCount; a++)
            {
                int o = axesOffset + a * axisSize;
                // DWRITE_FONT_AXIS_TAG is the tag's four bytes read little-endian.
                tags[a] = (uint)(t[o] | t[o + 1] << 8 | t[o + 2] << 16 | t[o + 3] << 24);
            }
            string family = NameRecord(face, 16) ?? NameRecord(face, 1) ?? "Font";
            var seen = new HashSet<string>();
            int first = axesOffset + axisCount * axisSize;
            for (int n = 0; n < instanceCount; n++)
            {
                int o = first + n * instanceSize;
                if (o + 4 + 4 * axisCount > t.Length) break;
                string sub = NameRecord(face, U16(t, o)) ?? ("Style " + (n + 1));
                var axes = new float[axisCount * 2];
                for (int a = 0; a < axisCount; a++)
                {
                    axes[a * 2] = BitConverter.ToSingle(BitConverter.GetBytes(tags[a]), 0);
                    axes[a * 2 + 1] = (int)U32(t, o + 4 + a * 4) / 65536f;
                }
                string name = family + " " + sub;
                if (!seen.Add(name)) continue;
                list.Add(new FontFaceChoice { Name = name, Axes = axes });
            }
            return list;
        }
    }

    // ---- the outline sink DirectWrite draws a glyph into ----

    [ComImport, Guid("2cd9069e-12e2-11dc-9fed-001143a055f9"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface ISimplifiedGeometrySinkImport { }

    [ComVisible(true), Guid("2cd9069e-12e2-11dc-9fed-001143a055f9"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface ISimplifiedGeometrySink
    {
        [PreserveSig] void SetFillMode(int fillMode);
        [PreserveSig] void SetSegmentFlags(int flags);
        [PreserveSig] void BeginFigure(PointF2Com start, int figureBegin);
        [PreserveSig] void AddLines(IntPtr points, uint count);
        [PreserveSig] void AddBeziers(IntPtr beziers, uint count);
        [PreserveSig] void EndFigure(int figureEnd);
        [PreserveSig] int Close();
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PointF2Com { public float X, Y; }

    [ComVisible(true), ClassInterface(ClassInterfaceType.None)]
    public sealed class OutlineSink : ISimplifiedGeometrySink
    {
        internal readonly List<List<PointF2>> Contours = new List<List<PointF2>>();
        private List<PointF2> current;
        private PointF2 pen;

        public void SetFillMode(int fillMode) { }
        public void SetSegmentFlags(int flags) { }

        public void BeginFigure(PointF2Com start, int figureBegin)
        {
            current = new List<PointF2>();
            pen = new PointF2(start.X, start.Y);
            current.Add(pen);
            Contours.Add(current);
        }

        public void AddLines(IntPtr points, uint count)
        {
            var raw = new float[count * 2];
            Marshal.Copy(points, raw, 0, raw.Length);
            for (int i = 0; i < count; i++)
            {
                pen = new PointF2(raw[i * 2], raw[i * 2 + 1]);
                current.Add(pen);
            }
        }

        // Cubic segments, flattened to lines fine enough that no step is visible at the
        // size the glyph is drawn.
        public void AddBeziers(IntPtr beziers, uint count)
        {
            var raw = new float[count * 6];
            Marshal.Copy(beziers, raw, 0, raw.Length);
            for (int i = 0; i < count; i++)
            {
                PointF2 p0 = pen;
                var p1 = new PointF2(raw[i * 6], raw[i * 6 + 1]);
                var p2 = new PointF2(raw[i * 6 + 2], raw[i * 6 + 3]);
                var p3 = new PointF2(raw[i * 6 + 4], raw[i * 6 + 5]);
                double length = Dist(p0, p1) + Dist(p1, p2) + Dist(p2, p3);
                int steps = Math.Max(2, Math.Min(64, (int)Math.Ceiling(Math.Sqrt(length) * 1.5)));
                for (int s = 1; s <= steps; s++)
                {
                    float t = s / (float)steps, u = 1 - t;
                    float a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
                    current.Add(new PointF2(a * p0.X + b * p1.X + c * p2.X + d * p3.X,
                                            a * p0.Y + b * p1.Y + c * p2.Y + d * p3.Y));
                }
                pen = p3;
            }
        }

        public void EndFigure(int figureEnd) { }
        public int Close() { return 0; }

        private static double Dist(PointF2 a, PointF2 b)
        {
            double dx = a.X - b.X, dy = a.Y - b.Y;
            return Math.Sqrt(dx * dx + dy * dy);
        }
    }

    // ---- DirectWrite by vtable ----

    internal static class Dw
    {
        public static readonly IntPtr Factory, Factory5, Factory6;

        static Dw()
        {
            var iid = new Guid("b859ee5a-d838-4b5b-a2e8-1adc7d93db48");    // IDWriteFactory
            IntPtr factory;
            Check(DWriteCreateFactory(1, ref iid, out factory));            // isolated
            Factory = factory;
            Factory5 = Query(factory, new Guid("958db99a-be2a-4f09-af7d-65189803d1d3"));
            Factory6 = Query(factory, new Guid("f3744d80-21f7-42eb-b35d-995bc72fc223"));
        }

        private static IntPtr Query(IntPtr unknown, Guid iid)
        {
            IntPtr result;
            return Marshal.QueryInterface(unknown, ref iid, out result) >= 0 ? result : IntPtr.Zero;
        }

        public static IntPtr FileReference(string path)
        {
            IntPtr file;
            int hr = Fn<CreateFontFileReferenceFn>(Factory, 7)(Factory, path, IntPtr.Zero, out file);
            if (hr < 0) throw new InvalidDataException("This file could not be opened.");
            return file;
        }

        public static void Check(int hr)
        {
            if (hr < 0) throw new InvalidDataException("Windows could not read this font (0x" + hr.ToString("X8") + ").");
        }

        public static T Fn<T>(IntPtr obj, int slot) where T : class
        {
            IntPtr vtable = Marshal.ReadIntPtr(obj);
            return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(vtable, slot * IntPtr.Size), typeof(T)) as T;
        }

        [DllImport("dwrite.dll")]
        private static extern int DWriteCreateFactory(int type, ref Guid iid, out IntPtr factory);

        [StructLayout(LayoutKind.Sequential)]
        public struct FontMetrics
        {
            public ushort designUnitsPerEm, ascent, descent;
            public short lineGap;
            public ushort capHeight, xHeight;
            public short underlinePosition;
            public ushort underlineThickness;
            public short strikethroughPosition;
            public ushort strikethroughThickness;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct GlyphMetrics
        {
            public int leftSideBearing;
            public uint advanceWidth;
            public int rightSideBearing, topSideBearing;
            public uint advanceHeight;
            public int bottomSideBearing, verticalOriginY;
        }

        [UnmanagedFunctionPointer(CallingConvention.StdCall, CharSet = CharSet.Unicode)]
        public delegate int CreateFontFileReferenceFn(IntPtr self, string path, IntPtr lastWriteTime, out IntPtr file);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int CreateFontFaceFn(IntPtr self, int faceType, uint fileCount, IntPtr[] files, uint faceIndex, int simulations, out IntPtr face);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int AnalyzeFn(IntPtr self, out int supported, out int fileType, out int faceType, out uint faces);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate void GetMetricsFn(IntPtr self, out FontMetrics metrics);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int GetDesignGlyphMetricsFn(IntPtr self, ref ushort glyphs, uint count, out GlyphMetrics metrics, int sideways);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int GetGlyphIndicesFn(IntPtr self, ref uint codePoints, uint count, out ushort glyphs);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int TryGetFontTableFn(IntPtr self, uint tag, out IntPtr data, out uint size, out IntPtr context, out int exists);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate void ReleaseFontTableFn(IntPtr self, IntPtr context);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int GetGlyphRunOutlineFn(IntPtr self, float emSize, ref ushort glyphs, IntPtr advances, IntPtr offsets,
                                                 uint count, int sideways, int rightToLeft, IntPtr sink);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int UnpackFontFileFn(IntPtr self, int container, IntPtr data, uint size, out IntPtr stream);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int GetFileSizeFn(IntPtr self, out ulong size);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int ReadFileFragmentFn(IntPtr self, out IntPtr fragment, ulong offset, ulong size, out IntPtr context);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate void ReleaseFileFragmentFn(IntPtr self, IntPtr context);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int CreateFontResourceFn(IntPtr self, IntPtr file, uint faceIndex, out IntPtr resource);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        public delegate int ResourceCreateFontFaceFn(IntPtr self, int simulations, float[] axisValues, uint count, out IntPtr face);
    }
}
