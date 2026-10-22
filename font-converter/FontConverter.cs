// KMRP Font Converter: any font file into KOTOR's game fonts, for KMRP.
//
// One window, painted by hand in the KMRP installer's colours: eleven tiles, one for each
// distinct font the game draws its text in, grouped as the game uses them. A tile shows
// its text in KMRP's (New) Original HD Font until the player picks a font for it, then in
// that font. Convert writes the picked fonts' atlases (Atlas.cs) into a folder.
//
// Everything is laid out on a 1600x900 canvas and scaled to the window, so the layout is
// the approved mockup's at any size and any DPI. Pop-ups are drawn in the same window.
// The program is independent of KMRP's code but its fonts are made for KMRP (the pop-up
// at the start says so): KMRP sizes Override fonts for every resolution and text size.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("KMRP Font Converter")]
[assembly: AssemblyProduct("KMRP Font Converter")]
[assembly: AssemblyDescription("Turns any font into KOTOR's game fonts, for KMRP")]
[assembly: AssemblyCompany("RaymanGT")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace KmrpFontConverter
{
    internal static class Program
    {
        public const string Version = "1.0";
        public const string DeadlyStream = "https://deadlystream.com/files/file/3096-kmrp-kotor-modern-restoration-patch/";
        public const string GitHubReleases = "https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases";

        [STAThread]
        private static void Main()
        {
            try { SetProcessDPIAware(); } catch (Exception) { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(Environment.GetCommandLineArgs().Skip(1).ToArray()));
        }

        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        public static Stream Resource(string name)
        {
            return Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
        }

        public static string ResourceText(string name)
        {
            using (var reader = new StreamReader(Resource(name))) return reader.ReadToEnd();
        }

        public static Bitmap ResourceImage(string name)
        {
            var stream = Resource(name);
            return stream == null ? null : new Bitmap(stream);
        }

        public static void Open(string target)
        {
            try { Process.Start(new ProcessStartInfo(target) { UseShellExecute = true }); }
            catch (Exception) { }
        }
    }

    // ---- the colours and type of the KMRP installer ----

    internal static class Theme
    {
        public static readonly Color Window = Color.FromArgb(10, 18, 32);
        public static readonly Color HeaderGlow = Color.FromArgb(22, 36, 58);
        public static readonly Color Group = Color.FromArgb(11, 19, 34);
        public static readonly Color GroupEdge = Color.FromArgb(28, 43, 66);
        public static readonly Color Tile = Color.FromArgb(15, 26, 44);
        public static readonly Color TileHover = Color.FromArgb(19, 32, 53);
        public static readonly Color TileEdge = Color.FromArgb(34, 51, 77);
        public static readonly Color Example = Color.FromArgb(5, 10, 18);
        public static readonly Color ExampleEdge = Color.FromArgb(23, 34, 52);
        public static readonly Color Field = Color.FromArgb(6, 11, 20);
        public static readonly Color Edge = Color.FromArgb(42, 59, 85);
        public static readonly Color Button = Color.FromArgb(11, 20, 36);
        public static readonly Color ButtonHover = Color.FromArgb(20, 34, 56);
        public static readonly Color Panel = Color.FromArgb(13, 22, 38);
        public static readonly Color Accent = Color.FromArgb(42, 198, 239);
        public static readonly Color AccentTop = Color.FromArgb(47, 208, 245);
        public static readonly Color AccentBottom = Color.FromArgb(26, 179, 227);
        public static readonly Color AccentInk = Color.FromArgb(6, 18, 30);
        public static readonly Color Gold = Color.FromArgb(226, 195, 92);
        public static readonly Color GoldEdge = Color.FromArgb(122, 102, 32);
        public static readonly Color Picked = Color.FromArgb(255, 154, 60);   // a tile with a font picked
        public static readonly Color Done = Color.FromArgb(126, 224, 171);    // and converted
        public static readonly Color Text = Color.FromArgb(236, 243, 248);
        public static readonly Color Muted = Color.FromArgb(177, 195, 208);
        public static readonly Color Soft = Color.FromArgb(143, 163, 181);
        public static readonly Color Faint = Color.FromArgb(122, 138, 154);
        public static readonly Color Success = Color.FromArgb(126, 224, 171);
        public static readonly Color Warning = Color.FromArgb(255, 207, 112);
        public static readonly Color Dashed = Color.FromArgb(51, 80, 122);
        public static readonly Color ChooseInk = Color.FromArgb(159, 216, 243);

        private static readonly Dictionary<string, Font> fonts = new Dictionary<string, Font>();
        private static string display, body;

        // The installer's faces, and what stands in for them where Windows' own fonts are
        // missing (Wine under Proton has neither Bahnschrift nor Segoe UI).
        private static string Family(params string[] names)
        {
            var installed = new HashSet<string>(FontFamily.Families.Select(f => f.Name), StringComparer.OrdinalIgnoreCase);
            foreach (string name in names) if (installed.Contains(name)) return name;
            return FontFamily.GenericSansSerif.Name;
        }

        // KMRP's own fonts, carried in the program (fonts/*.ttf, SIL OFL 1.1): Menu for titles,
        // Descriptions for text, as the Save Editor. Loaded from memory, so nothing is
        // installed; the system's faces stand in if they cannot be loaded.
        private static readonly PrivateFontCollection kmrp = new PrivateFontCollection();
        private static bool kmrpLoaded;

        private static FontFamily Kmrp(string name)
        {
            if (!kmrpLoaded)
            {
                kmrpLoaded = true;
                Assembly asm = Assembly.GetExecutingAssembly();
                foreach (string res in asm.GetManifestResourceNames())
                {
                    if (!res.StartsWith("fonts.") || !res.EndsWith(".ttf")) continue;
                    using (Stream s = asm.GetManifestResourceStream(res))
                    {
                        var data = new byte[s.Length];
                        s.Read(data, 0, data.Length);
                        // GDI+ reads the font from this memory for as long as the program runs.
                        IntPtr p = Marshal.AllocCoTaskMem(data.Length);
                        Marshal.Copy(data, 0, p, data.Length);
                        try { kmrp.AddMemoryFont(p, data.Length); } catch (Exception) { }
                    }
                }
            }
            return kmrp.Families.FirstOrDefault(f => f.Name == name);
        }

        public static Font Display(float px)
        {
            FontFamily f = Kmrp("KMRP Original HD Menu");
            if (f != null) return Get(f, px, FontStyle.Regular);
            return Get(display ?? (display = Family("Bahnschrift SemiCondensed", "Bahnschrift", "Segoe UI Semibold", "Tahoma", "Arial")), px, FontStyle.Bold);
        }

        public static Font Body(float px, bool bold = false)
        {
            // Descriptions is the game's bold body face already; one weight serves both.
            FontFamily f = Kmrp("KMRP Original HD Descriptions");
            if (f != null) return Get(f, px, FontStyle.Regular);
            return Get(body ?? (body = Family("Segoe UI", "Tahoma", "Arial")), px, bold ? FontStyle.Bold : FontStyle.Regular);
        }
        public static Font Mono(float px) { return Get(Family("Consolas", "Courier New"), px, FontStyle.Regular); }

        private static Font Get(string family, float px, FontStyle style)
        {
            string key = family + "|" + px + "|" + style;
            Font font;
            if (!fonts.TryGetValue(key, out font)) fonts[key] = font = new Font(family, px, style, GraphicsUnit.Pixel);
            return font;
        }

        private static Font Get(FontFamily family, float px, FontStyle style)
        {
            string key = "kmrp:" + family.Name + "|" + px + "|" + style;
            Font font;
            if (!fonts.TryGetValue(key, out font)) fonts[key] = font = new Font(family, px, style, GraphicsUnit.Pixel);
            return font;
        }

        public static GraphicsPath Round(RectangleF r, float radius)
        {
            var path = new GraphicsPath();
            float d = Math.Min(radius * 2, Math.Min(r.Width, r.Height));
            if (d <= 0) { path.AddRectangle(r); return path; }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        public static void Box(Graphics g, RectangleF r, float radius, Color fill, Color edge, float width = 1)
        {
            using (var path = Round(r, radius))
            {
                using (var brush = new SolidBrush(fill)) g.FillPath(brush, path);
                if (edge.A > 0) using (var pen = new Pen(edge, width)) g.DrawPath(pen, path);
            }
        }

        public static readonly StringFormat Left = new StringFormat(StringFormat.GenericTypographic)
        { LineAlignment = StringAlignment.Center, Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap | StringFormatFlags.MeasureTrailingSpaces };
        public static readonly StringFormat Centre = new StringFormat(StringFormat.GenericTypographic)
        { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center, Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap };
        public static readonly StringFormat Path = new StringFormat(StringFormat.GenericTypographic)
        { LineAlignment = StringAlignment.Center, Trimming = StringTrimming.EllipsisPath, FormatFlags = StringFormatFlags.NoWrap };

        public static void Draw(Graphics g, string text, Font font, Color colour, RectangleF r, StringFormat format = null)
        {
            using (var brush = new SolidBrush(colour)) g.DrawString(text, font, brush, r, format ?? Left);
        }

        /// <summary>Where a capital's ink starts and ends below the top of the line drawn with
        /// StringFormat.GenericTypographic, in pixels: measured from an "H".</summary>
        public static void Caps(Font font, out float top, out float bottom)
        {
            using (var path = new GraphicsPath())
            {
                path.AddString("H", font.FontFamily, (int)font.Style, font.Size, PointF.Empty, StringFormat.GenericTypographic);
                RectangleF ink = path.GetBounds();
                top = ink.Top;
                bottom = ink.Bottom;
            }
        }

        public static float Width(Graphics g, string text, Font font)
        {
            return g.MeasureString(text, font, PointF.Empty, StringFormat.GenericTypographic).Width;
        }
    }

    // ---- what the tiles are ----

    internal sealed class Piece
    {
        public string Name, Resref, Text;
        public float Height;
        public Color Colour;
        public Bitmap Hd;        // drawn in the HD Original font at 3x (make_data.py)
    }

    internal sealed class TileDef
    {
        public string Key, Name, Group, Use;
        public string[] Resrefs;
        public bool Centre;
        public List<List<Piece>> Lines = new List<List<Piece>>();
    }

    internal sealed class Tile
    {
        public TileDef Def;
        public FontFaceChoice Choice;
        public LoadedFace Face;
        public List<FontFaceChoice> FileFaces;     // every face of the picked file, for the picker
        public List<char> Missing;
        public bool Converted;                     // written since it was picked
        public readonly Dictionary<string, Bitmap> Cache = new Dictionary<string, Bitmap>();
        public RectangleF Bounds;

        public void Forget()
        {
            foreach (var b in Cache.Values) b.Dispose();
            Cache.Clear();
        }
    }

    internal static class Tiles
    {
        // The game's 17 text fonts hold 11 distinct letter sets (tools/build_hd_original_otf.py
        // finds them by comparing every glyph). A tile is one set; its font is written to
        // every name that shares it, so text the game draws in either name changes together.
        public static List<TileDef> All()
        {
            var defs = new List<TileDef>
            {
                Def("menu", "Menu", "Menus", "Screen titles and buttons", false, "dialogfont16x16", "dialogfont16x16b"),
                Def("menusmall", "Menu Small", "Menus", "Option lists and small labels", false, "dialogfont10x10", "dialogfont10x10a", "dialogfont16x16a"),
                Def("menusmallb", "Menu Small Bold", "Menus", "Tabs and bold labels", false, "dialogfont10x10b"),
                Def("menumedium", "Menu Medium", "Menus", "Save and load lists", false, "dialogfont12x16"),
                Def("menularge", "Menu Large", "Menus", "The biggest headings", true, "dialogfont32x32"),
                Def("dialogue", "Dialogue", "Reading", "What people say, and subtitles", false, "fnt_d16x16", "fnt_d10x10b"),
                Def("descriptions", "Replies", "Reading", "Your answers, item and skill text", false, "fnt_d16x16b"),
                Def("light", "Journal", "Reading", "The journal and long reading", false, "fnt_d16x16a", "fnt_creditsa", "fnt_dialog16x16"),
                Def("console", "HUD", "HUD", "Credits, level and XP", false, "fnt_console"),
                Def("credits", "Credits", "Credits", "Job titles", true, "fnt_credits"),
                Def("creditsb", "Credits Bold", "Credits", "Names", true, "fnt_creditsb"),
            };
            var byKey = defs.ToDictionary(d => d.Key);
            TileDef tile = null;
            foreach (string raw in Program.ResourceText("examples.txt").Split('\n'))
            {
                string line = raw.TrimEnd('\r');
                if (line.StartsWith("tile ")) tile = byKey[line.Substring(5)];
                else if (line.Trim() == "line") tile.Lines.Add(new List<Piece>());
                else if (line.TrimStart().StartsWith("piece "))
                {
                    string[] p = line.Trim().Split(new[] { ' ' }, 8);
                    tile.Lines[tile.Lines.Count - 1].Add(new Piece
                    {
                        Name = p[1], Resref = p[2], Height = float.Parse(p[3], CultureInfo.InvariantCulture),
                        Colour = Color.FromArgb(int.Parse(p[4]), int.Parse(p[5]), int.Parse(p[6])), Text = p[7],
                        Hd = Program.ResourceImage("examples." + p[1] + ".png"),
                    });
                }
            }
            return defs;
        }

        private static TileDef Def(string key, string name, string group, string use, bool centre, params string[] resrefs)
        {
            return new TileDef { Key = key, Name = name, Group = group, Use = use, Centre = centre, Resrefs = resrefs };
        }
    }

    // ---- where fonts go ----

    internal static class Places
    {
        /// <summary>Where the last font was picked from, for the next pick (this run only).</summary>
        public static string LastFontFolder;

        private static string SettingsFile
        {
            get { return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "KMRP Font Converter", "settings.txt"); }
        }

        public static string SavedFolder()
        {
            try
            {
                if (File.Exists(SettingsFile))
                    foreach (string line in File.ReadAllLines(SettingsFile))
                        if (line.StartsWith("output=") && Directory.Exists(line.Substring(7))) return line.Substring(7);
            }
            catch (Exception) { }
            return null;
        }

        public static void Save(string folder)
        {
            try
            {
                Directory.CreateDirectory(System.IO.Path.GetDirectoryName(SettingsFile));
                File.WriteAllText(SettingsFile, "output=" + folder + Environment.NewLine);
            }
            catch (Exception) { }
        }

        /// <summary>The game's Override folder when the game can be found (Steam or GOG),
        /// else a folder in Documents.</summary>
        public static string DefaultFolder()
        {
            foreach (string game in Games())
                if (File.Exists(System.IO.Path.Combine(game, "swkotor.exe"))) return System.IO.Path.Combine(Cased(game), "Override");
            return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "KMRP Font Converter");
        }

        // A folder's name as the disk spells it (Steam keeps its own path in lower case).
        private static string Cased(string path)
        {
            try
            {
                var dir = new DirectoryInfo(path);
                if (dir.Parent == null) return dir.FullName.ToUpperInvariant();
                var match = dir.Parent.GetDirectories(dir.Name);
                return System.IO.Path.Combine(Cased(dir.Parent.FullName), match.Length > 0 ? match[0].Name : dir.Name);
            }
            catch (Exception) { return path; }
        }

        private static IEnumerable<string> Games()
        {
            var found = new List<string>();
            try
            {
                string steam = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Valve\Steam", "SteamPath", null) as string;
                if (!string.IsNullOrEmpty(steam))
                {
                    var libraries = new List<string> { steam.Replace('/', '\\') };
                    string vdf = System.IO.Path.Combine(steam, "steamapps", "libraryfolders.vdf");
                    if (File.Exists(vdf))
                        foreach (string line in File.ReadAllLines(vdf))
                        {
                            string t = line.Trim();
                            if (!t.StartsWith("\"path\"")) continue;
                            string[] parts = t.Split('"');
                            if (parts.Length >= 4) libraries.Add(parts[3].Replace(@"\\", @"\"));
                        }
                    foreach (string library in libraries) found.Add(System.IO.Path.Combine(library, "steamapps", "common", "swkotor"));
                }
            }
            catch (Exception) { }
            foreach (string key in new[] { @"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\GOG.com\Games\1207666283", @"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\1207666283" })
                try
                {
                    string gog = Registry.GetValue(key, "path", null) as string;
                    if (!string.IsNullOrEmpty(gog)) found.Add(gog);
                }
                catch (Exception) { }
            found.Add(@"C:\Program Files (x86)\Steam\steamapps\common\swkotor");
            found.Add(@"C:\GOG Games\Star Wars - KotOR");
            return found;
        }
    }

    // ---- the window ----

    internal sealed class MainForm : Form
    {
        private const float CanvasW = 1600, CanvasH = 900;

        private readonly List<Tile> tiles;
        private readonly Dictionary<string, Reference> references;
        private readonly Bitmap logo, deadlyStreamLogo, gitHubLogo;
        private readonly Dictionary<string, Bitmap> scaled = new Dictionary<string, Bitmap>();
        private string output;

        private float scale = 1, offsetX, offsetY;
        private readonly List<Hit> hits = new List<Hit>();
        private string hover, pressed;
        private Dialog dialog;
        private Tile dropTarget;
        private volatile int progress = -1, progressTotal;
        private bool quietDone, still;
        private bool converted;     // the last Convert wrote what the tiles show; any change clears it

        private sealed class Hit
        {
            public RectangleF Rect;
            public string Id;
            public Action Click;
        }

        public MainForm(string[] args)
        {
            Text = "KMRP Font Converter";
            BackColor = Theme.Window;
            DoubleBuffered = true;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
            KeyPreview = true;
            AllowDrop = true;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }

            references = Reference.Parse(Program.ResourceText("references.txt"));
            tiles = Tiles.All().Select(d => new Tile { Def = d }).ToList();
            logo = Program.ResourceImage("kmrp-logo.png");
            deadlyStreamLogo = Program.ResourceImage("logo-deadlystream.png");
            gitHubLogo = Program.ResourceImage("logo-github.png");
            output = Places.SavedFolder() ?? Places.DefaultFolder();

            // 1600x900 at the screen's scale, as large as fits the work area.
            float dpi;
            using (var g = CreateGraphics()) dpi = g.DpiX / 96f;
            Rectangle work = Screen.PrimaryScreen.WorkingArea;
            float fit = Math.Min(dpi, Math.Min(work.Width * 0.94f / CanvasW, work.Height * 0.92f / CanvasH));
            ClientSize = new Size((int)(CanvasW * fit), (int)(CanvasH * fit));
            // Smallest: three quarters of the canvas at the screen's scale, where the smallest
            // text is still about 9 pixels at 100%; never more than the work area allows.
            float least = Math.Min(Math.Max(0.75f, dpi * 0.75f), Math.Min(work.Width * 0.94f / CanvasW, work.Height * 0.92f / CanvasH));
            Size frame = Size - ClientSize;
            MinimumSize = new Size((int)(CanvasW * least) + frame.Width, (int)(CanvasH * least) + frame.Height);
            StartPosition = FormStartPosition.CenterScreen;

            dialog = KmrpDialog();
            Preload(args);
        }

        // For screenshots and checks, from the command line:
        //   --no-intro            start without the KMRP pop-up
        //   key=path[#face]       a tile's font (key as in Tiles.All, face by name)
        //   --pick key=path       open the picker for a tile
        //   --done                show the pop-up a finished conversion shows
        //   --out=folder          write to this folder (not remembered)
        //   --convert             convert as soon as the window shows
        //   --no-done             no pop-up after converting
        //   --size=WxH            the window's inside at this size
        //   --still               ignore the mouse (screenshots)
        private void Preload(string[] args)
        {
            foreach (string arg in args)
            {
                if (arg.StartsWith("--out=")) { output = arg.Substring(6); continue; }
                if (arg.StartsWith("--size="))
                {
                    string[] wh = arg.Substring(7).Split('x');
                    ClientSize = new Size(int.Parse(wh[0]), int.Parse(wh[1]));
                    continue;
                }
                if (arg == "--convert") { Shown += (s, e) => Convert(); continue; }
                if (arg == "--no-done") { quietDone = true; continue; }
                if (arg == "--still") { still = true; continue; }
                if (arg == "--no-intro") { dialog = null; continue; }
                if (arg == "--done")
                {
                    dialog = new Dialog
                    {
                        Title = "Done",
                        Body = "6 game fonts made from 3 fonts, in " + output + ".",
                        Note = "Start the game with KMRP to see them. KMRP sizes them for your resolution and text size.",
                        Buttons = { new DialogButton("Open Folder", false, () => CloseDialog(null)), new DialogButton("OK", true, () => CloseDialog(null)) },
                    };
                    continue;
                }
                bool pick = arg.StartsWith("--pick ");
                string spec = pick ? arg.Substring(7) : arg;
                int eq = spec.IndexOf('=');
                if (eq < 0) continue;
                Tile tile = tiles.FirstOrDefault(t => t.Def.Key == spec.Substring(0, eq));
                if (tile == null) continue;
                string path = spec.Substring(eq + 1), face = null;
                int hash = path.IndexOf('#');
                if (hash >= 0) { face = path.Substring(hash + 1); path = path.Substring(0, hash); }
                try
                {
                    var faces = FontFiles.Faces(path);
                    if (pick) { dialog = Picker(tile, faces, false); continue; }
                    var choice = faces.FirstOrDefault(f => face == null || f.Name == face) ?? faces[0];
                    Apply(tile, choice, faces);
                }
                catch (Exception) { }
            }
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            try
            {
                int dark = 1;   // a dark title bar on Windows 10 2004 and later; ignored elsewhere
                DwmSetWindowAttribute(Handle, 20, ref dark, 4);
            }
            catch (Exception) { }
        }

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        // ---- painting ----

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            scale = Math.Min(ClientSize.Width / CanvasW, ClientSize.Height / CanvasH);
            offsetX = (ClientSize.Width - CanvasW * scale) / 2;
            offsetY = (ClientSize.Height - CanvasH * scale) / 2;
            g.Clear(Theme.Window);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            // Grid-fitted: the fonts' hints put stems on whole pixels (plain AntiAlias ignored
            // them and left the text soft).
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.TranslateTransform(offsetX, offsetY);
            g.ScaleTransform(scale, scale);
            hits.Clear();

            PaintHeader(g);
            PaintGroups(g);
            PaintActions(g);
            if (dialog != null)
            {
                hits.Clear();
                using (var dim = new SolidBrush(Color.FromArgb(184, 3, 6, 12))) g.FillRectangle(dim, -offsetX / scale, -offsetY / scale, ClientSize.Width / scale, ClientSize.Height / scale);
                dialog.Paint(this, g);
            }
        }

        private void AddHit(RectangleF rect, string id, Action click)
        {
            hits.Add(new Hit { Rect = rect, Id = id, Click = click });
        }

        private bool Hover(string id) { return hover == id; }

        private void PaintHeader(Graphics g)
        {
            using (var path = new GraphicsPath())
            {
                // From the window's own top and sides, where the canvas does not fill it.
                float left = -offsetX / scale, edge = -offsetY / scale, width = ClientSize.Width / scale;
                path.AddEllipse(288 - 900, edge - 260, 1800, 520);
                using (var glow = new PathGradientBrush(path) { CenterColor = Theme.HeaderGlow, SurroundColors = new[] { Theme.Window }, CenterPoint = new PointF(288, edge) })
                    g.FillRectangle(glow, left, edge, width, 218 - edge);
                using (var fade = new LinearGradientBrush(new RectangleF(left, 86, width, 133), Color.FromArgb(0, Theme.Window), Theme.Window, 90f))
                    g.FillRectangle(fade, left, 87, width, 131);
            }

            float logoW = 0, logoTop = 14, logoH = 116;
            if (logo != null)
            {
                logoW = logoH * logo.Width / logo.Height;
                DrawSharp(g, logo, "logo", new RectangleF(56, logoTop, logoW, logoH));
            }
            // The title's capitals centred on the logo's middle.
            Font title = Theme.Display(42);
            float cap = 0.70f * 42, middle = logoTop + logoH / 2 + 1;
            float ascent = title.Size * title.FontFamily.GetCellAscent(title.Style) / title.FontFamily.GetEmHeight(title.Style);
            float top = middle + cap / 2 - ascent;
            using (var shadow = new SolidBrush(Color.FromArgb(120, 0, 0, 0))) g.DrawString("Font Converter", title, shadow, 56 + logoW + 26 + 1, top + 2, StringFormat.GenericTypographic);
            using (var ink = new SolidBrush(Theme.Text)) g.DrawString("Font Converter", title, ink, 56 + logoW + 26, top, StringFormat.GenericTypographic);

            Rich(g, new RectangleF(800, 46, 740, 60), 15, Theme.Muted, Theme.Text,
                "Pick a font for any kind of text you want to change. ", "*Every size the game needs*",
                " is made from it. Each example shows how that text looks today. Anything you don't pick stays as it is.");
        }

        // Wrapped text with *bold* runs.
        private static void Rich(Graphics g, RectangleF r, float px, Color colour, Color strong, params string[] runs)
        {
            float x = r.X, y = r.Y, line = px * 1.55f;
            foreach (string run in runs)
            {
                bool bold = run.StartsWith("*");
                Font font = Theme.Body(px, bold);
                string text = run.Trim('*');
                foreach (string word in System.Text.RegularExpressions.Regex.Split(text, @"(?<= )"))
                {
                    if (word.Length == 0) continue;
                    float w = Theme.Width(g, word, font);
                    if (x + w > r.Right + 0.5f && x > r.X) { x = r.X; y += line; }
                    using (var b = new SolidBrush(bold ? strong : colour)) g.DrawString(word, font, b, x, y, StringFormat.GenericTypographic);
                    // The word, then its space measured on its own: GDI+ leaves trailing
                    // spaces out of a width, and a no-break space too when the font draws it
                    // with the space's glyph (as KMRP's fonts do).
                    x += Theme.Width(g, word.TrimEnd(' '), font);
                    if (word.EndsWith(" ")) x += Theme.Width(g, "a a", font) - Theme.Width(g, "aa", font);
                }
            }
        }

        private static readonly string[][] Rows = { new[] { "Menus" }, new[] { "Reading", "HUD", "Credits" } };

        private static readonly Dictionary<string, KeyValuePair<Color, string>> GroupInfo = new Dictionary<string, KeyValuePair<Color, string>>
        {
            { "Menus", new KeyValuePair<Color, string>(Color.FromArgb(226, 195, 92), "Every screen you click through") },
            { "Reading", new KeyValuePair<Color, string>(Color.FromArgb(96, 178, 255), "Conversations and the journal") },
            { "HUD", new KeyValuePair<Color, string>(Color.FromArgb(126, 224, 171), "On screen while you play") },
            { "Credits", new KeyValuePair<Color, string>(Color.FromArgb(197, 140, 255), "The end credits") },
        };

        private void PaintGroups(Graphics g)
        {
            float y = 146;
            foreach (string[] row in Rows)
            {
                int count = row.Sum(n => tiles.Count(t => t.Def.Group == n));
                float available = 1480 - 14 * (row.Length - 1), x = 60;
                foreach (string name in row)
                {
                    var members = tiles.Where(t => t.Def.Group == name).ToList();
                    float w = available * members.Count / count;
                    var r = new RectangleF(x, y, w, 291);
                    Theme.Box(g, r, 12, Theme.Group, Theme.GroupEdge);
                    var info = GroupInfo[name];
                    using (var dot = new SolidBrush(info.Key)) g.FillEllipse(dot, x + 16, y + 18, 8, 8);
                    float tx = x + 34;
                    Font head = Theme.Display(15);
                    using (var ink = new SolidBrush(info.Key))
                        foreach (char c in name.ToUpperInvariant())
                        {
                            g.DrawString(c.ToString(), head, ink, tx, y + 13, StringFormat.GenericTypographic);
                            tx += Theme.Width(g, c.ToString(), head) + 3;
                        }
                    Theme.Draw(g, info.Value, Theme.Body(12.5f), Theme.Faint, new RectangleF(tx + 9, y + 12, r.Right - tx - 20, 20));
                    float tw = (w - 24 - 12 * (members.Count - 1)) / members.Count;
                    for (int i = 0; i < members.Count; i++)
                        PaintTile(g, members[i], new RectangleF(x + 12 + i * (tw + 12), y + 43, tw, 236));
                    x += w + 14;
                }
                y += 291 + 14;
            }
        }

        private void PaintTile(Graphics g, Tile tile, RectangleF r)
        {
            tile.Bounds = r;
            bool mine = tile.Face != null;
            string id = "tile:" + tile.Def.Key;
            bool lit = dropTarget == tile;
            // A picked font lights its tile orange; once converted, green.
            Color state = tile.Converted ? Theme.Done : Theme.Picked;
            Color fill = lit ? Theme.TileHover : Theme.Tile;
            Theme.Box(g, r, 8, fill, lit ? Theme.Accent : mine ? state : Theme.TileEdge, lit || mine ? 2 : 1);
            if (mine && !lit)
                using (var path = Theme.Round(r, 8))
                using (var glow = new LinearGradientBrush(new RectangleF(r.X, r.Y - 1, r.Width, r.Height * 0.6f + 2), Color.FromArgb(48, state), Color.FromArgb(0, state), 90f))
                {
                    g.SetClip(path);
                    g.FillRectangle(glow, r.X, r.Y, r.Width, r.Height * 0.6f);
                    g.ResetClip();
                }

            Theme.Draw(g, tile.Def.Name, Theme.Display(19), Theme.Text, new RectangleF(r.X + 14, r.Y + 10, r.Width - 28, 26));
            Theme.Draw(g, tile.Def.Use, Theme.Body(12.5f), Theme.Soft, new RectangleF(r.X + 14, r.Y + 36, r.Width - 28, 18));

            var box = new RectangleF(r.X + 14, r.Y + 62, r.Width - 28, r.Height - 62 - 12 - 34 - 10);
            Theme.Box(g, box, 5, Theme.Example, Theme.ExampleEdge);
            PaintExample(g, tile, box);

            var foot = new RectangleF(r.X + 14, r.Bottom - 12 - 34, r.Width - 28, 34);
            if (!mine)
            {
                bool on = Hover(id + ":choose");
                using (var path = Theme.Round(foot, 5))
                {
                    if (on) using (var b = new SolidBrush(Theme.ButtonHover)) g.FillPath(b, path);
                    using (var pen = new Pen(on ? Theme.Accent : Theme.Dashed) { DashPattern = new[] { 3f, 2f } }) g.DrawPath(pen, path);
                }
                Theme.Draw(g, "Choose a font\u2026", Theme.Display(15), on ? Theme.Text : Theme.ChooseInk, foot, Theme.Centre);
                AddHit(foot, id + ":choose", () => Choose(tile));
            }
            else
            {
                var clear = new RectangleF(foot.Right - 32, foot.Y, 32, foot.Height);
                var chip = new RectangleF(foot.X, foot.Y, foot.Width, foot.Height);
                bool on = Hover(id + ":chip");
                Theme.Box(g, chip, 5, Color.FromArgb(on ? 40 : 22, state), Color.FromArgb(150, state));
                // The font's name; a warning beside it only when the font lacks letters the
                // game's text uses (those are left blank).
                Font name = Theme.Display(15), small = Theme.Body(11.5f);
                string warning = tile.Missing.Count == 0 ? null : "\u26A0 " + tile.Missing.Count + " missing";
                float warnW = warning == null ? 0 : Theme.Width(g, warning, small) + 8;
                float nameW = Math.Min(Theme.Width(g, tile.Face.Name, name) + 2, chip.Width - 20 - 32 - warnW);
                Theme.Draw(g, tile.Face.Name, name, state, new RectangleF(chip.X + 10, chip.Y, Math.Max(20, nameW), chip.Height));
                if (warning != null)
                    Theme.Draw(g, warning, small, Theme.Warning, new RectangleF(chip.X + 10 + Math.Max(20, nameW) + 8, chip.Y + 1, warnW, chip.Height));
                bool x = Hover(id + ":clear");
                Theme.Draw(g, "\u2715", Theme.Body(14), x ? Theme.Text : Theme.Faint, clear, Theme.Centre);
                AddHit(chip, id + ":chip", () => Choose(tile));
                AddHit(clear, id + ":clear", () => Clear(tile));
            }
        }

        // The tile's example lines, each piece in the HD Original font or the picked one,
        // all of a tile's lines shrunk together when the widest would not fit.
        private void PaintExample(Graphics g, Tile tile, RectangleF box)
        {
            bool mine = tile.Face != null;
            const float gap = 18, lineGap = 9;
            float room = box.Width - 24;
            var widths = new List<float>();
            foreach (var line in tile.Def.Lines)
                widths.Add(line.Sum(p => PieceWidth(tile, p)) + gap * (line.Count - 1));
            float shrink = Math.Min(1, room / Math.Max(1, widths.Max()));
            float total = tile.Def.Lines.Sum(l => l.Max(p => p.Height) * shrink) + lineGap * (tile.Def.Lines.Count - 1);
            float y = box.Y + (box.Height - total) / 2;
            for (int n = 0; n < tile.Def.Lines.Count; n++)
            {
                var line = tile.Def.Lines[n];
                float lineH = line.Max(p => p.Height) * shrink;
                float x = tile.Def.Centre ? box.X + (box.Width - widths[n] * shrink) / 2 : box.X + 12;
                foreach (var piece in line)
                {
                    float h = piece.Height * shrink;
                    float w = PieceWidth(tile, piece) * shrink;
                    if (mine) DrawPreview(g, tile, piece, new RectangleF(x, y + (lineH - h) / 2, w, h));
                    else DrawSharp(g, piece.Hd, piece.Name, new RectangleF(x, y + (lineH - h) / 2, w, h));
                    x += w + gap * shrink;
                }
                y += lineH + lineGap;
            }
        }

        // A piece's width at its own height, on the 1600x900 canvas.
        private float PieceWidth(Tile tile, Piece piece)
        {
            if (tile.Face == null) return piece.Hd.Width * piece.Height / piece.Hd.Height;
            Bitmap measure = Preview(tile, piece, piece.Height * 2, true);
            return (measure.Width - 2 * (Margin(measure) - 1)) / 2f;
        }

        // A piece in the picked font, `height` device pixels high. One bitmap a piece (and one
        // to measure with, "measure:" keys), replaced when the size changes, so resizing
        // never piles them up.
        private Bitmap Preview(Tile tile, Piece piece, float height, bool measure = false)
        {
            int h = Math.Max(4, (int)Math.Round(height));
            string key = (measure ? "measure:" : "") + piece.Name;
            Bitmap b;
            if (tile.Cache.TryGetValue(key, out b) && Box(b) == h) return b;
            if (b != null) b.Dispose();
            // The box plus a blank pixel round it (and room for the HUD font's black ring:
            // one original pixel, a sixth of its 6x atlas's 96 pixel glyph box per 16).
            float ring = Atlas.Outlined.ContainsKey(piece.Resref) ? h * Atlas.Outlined[piece.Resref] / 96f : 0;
            b = Atlas.Line(tile.Face, piece.Text, h, piece.Colour, ring);
            tile.Cache[key] = b;
            return b;
        }

        private static int Box(Bitmap b) { return ((int[])b.Tag)[0]; }
        private static int Margin(Bitmap b) { return ((int[])b.Tag)[1]; }

        private void DrawPreview(Graphics g, Tile tile, Piece piece, RectangleF r)
        {
            Bitmap b;
            // While the window is dragged to a new size the last bitmap is stretched; the
            // sharp one is drawn when the drag ends.
            if (resizing && tile.Cache.TryGetValue(piece.Name, out b))
            {
                float f = r.Height * scale / Math.Max(1, Box(b));
                float m = Margin(b) * f / scale;
                DrawStretched(g, b, r.X - m, r.Y - m, b.Width * f, b.Height * f);
                return;
            }
            b = Preview(tile, piece, r.Height * scale);
            DrawDevice(g, b, r.X - (Margin(b) - 1) / scale, r.Y - (Margin(b) - 1) / scale);
        }

        /// <summary>An image drawn at the device's own pixels: scaled once into a cache, so
        /// painting never resamples and stays fast.</summary>
        private void DrawSharp(Graphics g, Bitmap source, string name, RectangleF r)
        {
            if (source == null) return;
            int w = Math.Max(1, (int)Math.Round(r.Width * scale)), h = Math.Max(1, (int)Math.Round(r.Height * scale));
            Bitmap b;
            // One bitmap an image, made again when its size changes; stretched while resizing.
            if (scaled.TryGetValue(name, out b) && (b.Width != w || b.Height != h))
            {
                if (resizing) { DrawStretched(g, b, r.X, r.Y, w, h); return; }
                b.Dispose();
                b = null;
            }
            if (b == null)
            {
                b = new Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
                using (var s = Graphics.FromImage(b))
                {
                    s.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    s.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    s.CompositingQuality = CompositingQuality.HighQuality;
                    using (var attributes = new System.Drawing.Imaging.ImageAttributes())
                    {
                        attributes.SetWrapMode(WrapMode.TileFlipXY);
                        s.DrawImage(source, new Rectangle(0, 0, w, h), 0, 0, source.Width, source.Height, GraphicsUnit.Pixel, attributes);
                    }
                }
                scaled[name] = b;
            }
            DrawDevice(g, b, r.X, r.Y);
        }

        private void DrawStretched(Graphics g, Bitmap b, float x, float y, float w, float h)
        {
            var state = g.Save();
            g.ResetTransform();
            g.InterpolationMode = InterpolationMode.Bilinear;
            g.DrawImage(b, (float)Math.Round(offsetX + x * scale), (float)Math.Round(offsetY + y * scale), w, h);
            g.Restore(state);
        }

        private bool resizing;

        // Dragging an edge keeps the inside 16:9, the canvas's shape, so it is always filled:
        // the other side follows (the bottom for a side edge or corner, the right for the
        // top or bottom edge). Maximized on a screen of another shape, the canvas is centred.
        protected override void WndProc(ref Message m)
        {
            const int WM_SIZING = 0x0214;
            if (m.Msg == WM_SIZING && m.LParam != IntPtr.Zero)
            {
                var r = (WindowRect)Marshal.PtrToStructure(m.LParam, typeof(WindowRect));
                Size frame = Size - ClientSize;
                int edge = m.WParam.ToInt32();
                int w = r.Right - r.Left - frame.Width, h = r.Bottom - r.Top - frame.Height;
                if (edge == 3 || edge == 6)                     // top, bottom: the width follows
                    r.Right = r.Left + (int)Math.Round(h * CanvasW / CanvasH) + frame.Width;
                else
                {
                    int height = (int)Math.Round(w * CanvasH / CanvasW) + frame.Height;
                    if (edge == 4 || edge == 5) r.Top = r.Bottom - height;   // top corners
                    else r.Bottom = r.Top + height;
                }
                Marshal.StructureToPtr(r, m.LParam, false);
                m.Result = (IntPtr)1;
                return;
            }
            base.WndProc(ref m);
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct WindowRect { public int Left, Top, Right, Bottom; }

        protected override void OnResizeBegin(EventArgs e) { base.OnResizeBegin(e); resizing = true; }
        protected override void OnResizeEnd(EventArgs e) { base.OnResizeEnd(e); resizing = false; Invalidate(); }

        private void DrawDevice(Graphics g, Bitmap b, float x, float y)
        {
            var state = g.Save();
            g.ResetTransform();
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.DrawImage(b, (float)Math.Round(offsetX + x * scale), (float)Math.Round(offsetY + y * scale), b.Width, b.Height);
            g.Restore(state);
        }

        private void PaintActions(Graphics g)
        {
            int chosen = tiles.Count(t => t.Face != null);
            Font count = Theme.Display(20);
            float x = 60;
            using (var gold = new SolidBrush(Theme.Gold)) g.DrawString(chosen.ToString(), count, gold, x, 798, StringFormat.GenericTypographic);
            x += Theme.Width(g, chosen.ToString(), count) + 6;
            Theme.Draw(g, "of 11 fonts chosen", count, Theme.Text, new RectangleF(x, 795, 240, 30));

            var path = new RectangleF(325, 780, 771, 58);
            Theme.Box(g, path, 5, Theme.Field, Theme.Edge);
            Theme.Draw(g, "SAVE TO", Theme.Body(11), Theme.Faint, new RectangleF(path.X + 16, path.Y + 9, 200, 16));
            var change = new RectangleF(path.Right - 100, path.Y + 11, 86, 36);
            Theme.Draw(g, output, Theme.Mono(13), Theme.Muted, new RectangleF(path.X + 16, path.Y + 25, change.X - path.X - 30, 24), Theme.Path);
            bool on = Hover("output");
            Theme.Box(g, change, 5, on ? Theme.ButtonHover : Theme.Button, on ? Theme.Accent : Theme.Edge);
            Theme.Draw(g, "Change", Theme.Display(16), Theme.Text, change, Theme.Centre);
            AddHit(change, "output", PickFolder);

            // Clear: every tile back to the Original HD Font.
            var clear = new RectangleF(1110, 780, 140, 58);
            bool busy = progress >= 0, canClear = chosen > 0 && !busy, onClear = canClear && Hover("clearall");
            // A grey button: lighter than the folder's field, quieter than Convert.
            using (var p = Theme.Round(clear, 5))
            using (var b = new LinearGradientBrush(clear,
                canClear ? (onClear ? Color.FromArgb(104, 117, 134) : Color.FromArgb(86, 98, 114)) : Color.FromArgb(40, 48, 60),
                canClear ? (onClear ? Color.FromArgb(82, 94, 110) : Color.FromArgb(66, 77, 92)) : Color.FromArgb(32, 39, 50), 90f))
                g.FillPath(b, p);
            Theme.Draw(g, "Clear", Theme.Display(19), canClear ? Theme.Text : Color.FromArgb(92, 104, 118), clear, Theme.Centre);
            if (canClear) AddHit(clear, "clearall", ClearAll);

            // Convert, or Converted while every picked font is written to this folder as it is.
            var convert = new RectangleF(1264, 780, 276, 58);
            bool done = chosen > 0 && !busy && converted;
            bool ready = chosen > 0 && !busy && !done;
            using (var p = Theme.Round(convert, 5))
            {
                if (ready)
                {
                    Color top = Hover("convert") ? Color.FromArgb(88, 222, 250) : Theme.AccentTop;
                    using (var b = new LinearGradientBrush(convert, top, Theme.AccentBottom, 90f)) g.FillPath(b, p);
                }
                else if (done)
                    using (var b = new LinearGradientBrush(convert, Color.FromArgb(146, 234, 188), Color.FromArgb(96, 204, 148), 90f)) g.FillPath(b, p);
                else using (var b = new SolidBrush(Color.FromArgb(18, 40, 54))) g.FillPath(b, p);
                if (busy && progressTotal > 0)
                {
                    g.SetClip(p);
                    using (var b = new LinearGradientBrush(convert, Theme.AccentTop, Theme.AccentBottom, 90f))
                        g.FillRectangle(b, convert.X, convert.Y, convert.Width * progress / progressTotal, convert.Height);
                    g.ResetClip();
                }
            }
            string label = busy ? "Converting\u2026 " + progress + " of " + progressTotal : done ? "\u2713 Converted" : "Convert";
            Theme.Draw(g, label, Theme.Display(21), ready || busy || done ? Theme.AccentInk : Color.FromArgb(70, 110, 130), convert, Theme.Centre);
            if (ready) AddHit(convert, "convert", Convert);

            Theme.Draw(g, "v" + Program.Version, Theme.Body(15), Theme.Faint, new RectangleF(62, 860, 60, 24));
            Theme.Draw(g, "\u00B7", Theme.Body(15), Theme.Faint, new RectangleF(100, 860, 20, 24));
            var open = new RectangleF(120, 860, Theme.Width(g, "Open Output Folder", Theme.Body(15)) + 4, 24);
            Theme.Draw(g, "Open Output Folder", Theme.Body(15), Hover("open") ? Theme.Text : Theme.Accent, open);
            AddHit(open, "open", () => { Directory.CreateDirectory(output); Program.Open(output); });
            var credit = "Created by RaymanGT";
            float cw = Theme.Width(g, credit, Theme.Body(15));
            Theme.Draw(g, credit, Theme.Body(15), Theme.Faint, new RectangleF(1538 - cw, 860, cw + 4, 24));
        }

        // ---- input ----

        private PointF Canvas(Point p)
        {
            return new PointF((p.X - offsetX) / scale, (p.Y - offsetY) / scale);
        }

        private Hit HitAt(Point p)
        {
            PointF c = Canvas(p);
            for (int i = hits.Count - 1; i >= 0; i--) if (hits[i].Rect.Contains(c)) return hits[i];
            return null;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (still) return;
            Hit hit = HitAt(e.Location);
            string id = hit == null ? null : hit.Id;
            Cursor = hit != null ? Cursors.Hand : Cursors.Default;
            if (id != hover) { hover = id; Invalidate(); }
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
            if (hover != null) { hover = null; Invalidate(); }
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if (e.Button != MouseButtons.Left) return;
            Hit hit = HitAt(e.Location);
            pressed = hit == null ? null : hit.Id;
            if (dialog != null && e.Clicks == 2 && hit != null) dialog.DoubleClick(this, hit.Id);
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
            if (e.Button != MouseButtons.Left) return;
            Hit hit = HitAt(e.Location);
            if (hit != null && hit.Id == pressed && hit.Click != null) hit.Click();
            pressed = null;
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            base.OnMouseWheel(e);
            if (dialog != null) { dialog.Wheel(this, e.Delta); Invalidate(); }
        }

        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            if (dialog != null && dialog.Key(this, keyData)) { Invalidate(); return true; }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        protected override void OnDragOver(DragEventArgs e)
        {
            base.OnDragOver(e);
            Tile over = null;
            if (dialog == null && progress < 0 && e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                PointF c = Canvas(PointToClient(new Point(e.X, e.Y)));
                over = tiles.FirstOrDefault(t => t.Bounds.Contains(c));
            }
            e.Effect = over != null ? DragDropEffects.Copy : DragDropEffects.None;
            if (over != dropTarget) { dropTarget = over; Invalidate(); }
        }

        protected override void OnDragLeave(EventArgs e)
        {
            base.OnDragLeave(e);
            if (dropTarget != null) { dropTarget = null; Invalidate(); }
        }

        protected override void OnDragDrop(DragEventArgs e)
        {
            base.OnDragDrop(e);
            Tile target = dropTarget;
            dropTarget = null;
            var files = e.Data.GetData(DataFormats.FileDrop) as string[];
            if (target != null && files != null && files.Length > 0) BeginInvoke(new Action(() => Open(target, files[0])));
            Invalidate();
        }

        // ---- what the tiles do ----

        private void Choose(Tile tile)
        {
            if (progress >= 0) return;
            if (tile.FileFaces != null && tile.FileFaces.Count > 1)
            {
                dialog = Picker(tile, tile.FileFaces, true);
                Invalidate();
                return;
            }
            Browse(tile);
        }

        private void Browse(Tile tile)
        {
            using (var dialogBox = new OpenFileDialog
            {
                Title = "Choose a font for " + tile.Def.Name,
                Filter = "Fonts (*.ttf, *.otf, *.ttc, *.otc, *.woff, *.woff2)|*.ttf;*.otf;*.ttc;*.otc;*.woff;*.woff2|All files (*.*)|*.*",
            })
            {
                string folder = Places.LastFontFolder;
                if (folder != null) dialogBox.InitialDirectory = folder;
                if (dialogBox.ShowDialog(this) != DialogResult.OK) return;
                Places.LastFontFolder = System.IO.Path.GetDirectoryName(dialogBox.FileName);
                Open(tile, dialogBox.FileName);
            }
        }

        private void Open(Tile tile, string path)
        {
            if (!FontFiles.Accepted(path))
            {
                Message("This font type can't be used", "Pick a TTF, OTF or WOFF font file. " + System.IO.Path.GetFileName(path) + " is not one.");
                return;
            }
            List<FontFaceChoice> faces;
            try
            {
                Cursor = Cursors.WaitCursor;
                faces = FontFiles.Faces(path);
            }
            catch (Exception ex)
            {
                Message("This font can't be read", ex.Message);
                return;
            }
            finally { Cursor = Cursors.Default; }
            if (faces.Count == 1) Apply(tile, faces[0], faces);
            else { dialog = Picker(tile, faces, false); Invalidate(); }
        }

        private void Apply(Tile tile, FontFaceChoice choice, List<FontFaceChoice> faces)
        {
            LoadedFace face;
            try { face = FontFiles.Load(choice); }
            catch (Exception ex) { Message("This font can't be read", ex.Message); return; }
            Release(tile);
            tile.Choice = choice;
            tile.Face = face;
            tile.FileFaces = faces;
            tile.Missing = Atlas.Missing(face);
            tile.Converted = false;
            converted = false;
            Invalidate();
        }

        private void Release(Tile tile)
        {
            tile.Forget();
            if (tile.Face != null) tile.Face.Dispose();
            tile.Face = null;
            tile.Choice = null;
            tile.FileFaces = null;
            tile.Missing = null;
            tile.Converted = false;
        }

        private void Clear(Tile tile)
        {
            if (progress >= 0) return;
            Release(tile);
            converted = false;
            Invalidate();
        }

        private void ClearAll()
        {
            if (progress >= 0) return;
            foreach (var tile in tiles) Release(tile);
            converted = false;
            Invalidate();
        }

        private void PickFolder()
        {
            using (var browse = new FolderBrowserDialog { Description = "Where the game fonts go. The game's Override folder is where the game reads them.", SelectedPath = output, ShowNewFolderButton = true })
            {
                if (browse.ShowDialog(this) != DialogResult.OK) return;
                if (!string.Equals(output, browse.SelectedPath, StringComparison.OrdinalIgnoreCase))
                {
                    foreach (var tile in tiles) tile.Converted = false;   // nothing written there yet
                    converted = false;
                }
                output = browse.SelectedPath;
                Places.Save(output);
                Invalidate();
            }
        }

        private void Convert()
        {
            var chosen = tiles.Where(t => t.Face != null).ToList();
            var names = chosen.SelectMany(t => t.Def.Resrefs).ToList();
            int existing = 0;
            try
            {
                foreach (string n in names)
                    foreach (string ext in new[] { ".tga", ".txi", ".tpc" })
                        if (File.Exists(System.IO.Path.Combine(output, n + ext))) existing++;
            }
            catch (Exception) { }
            if (existing > 0)
            {
                dialog = new Dialog
                {
                    Title = "Replace fonts already there?",
                    Body = "The folder already has " + existing + " font file" + (existing == 1 ? "" : "s") + " with the names these fonts use. Converting replaces them.",
                    Buttons = { new DialogButton("Cancel", false, () => CloseDialog(null)), new DialogButton("Replace", true, () => { CloseDialog(null); Run(chosen); }) },
                };
                Invalidate();
                return;
            }
            Run(chosen);
        }

        private void Run(List<Tile> chosen)
        {
            var work = chosen.SelectMany(t => t.Def.Resrefs.Select(r => new KeyValuePair<Tile, string>(t, r))).ToList();
            string folder = output;
            progressTotal = work.Count;
            progress = 0;
            Invalidate();
            var thread = new Thread(() =>
            {
                Exception failed = null;
                try
                {
                    Directory.CreateDirectory(folder);
                    // A .tpc of the same name would win over the new .tga: moved aside.
                    foreach (var item in work)
                    {
                        string tpc = System.IO.Path.Combine(folder, item.Value + ".tpc");
                        if (File.Exists(tpc)) File.Move(tpc, tpc + ".before-font-converter");
                        Atlas.Write(item.Key.Face, references[item.Value], folder);
                        progress++;
                        BeginInvoke(new Action(Invalidate));
                    }
                }
                catch (Exception ex) { failed = ex; }
                BeginInvoke(new Action(() =>
                {
                    progress = -1;
                    if (failed != null) Message("The fonts could not be written", failed.Message);
                    else
                    {
                        foreach (var t in chosen) t.Converted = true;
                        converted = true;
                        if (!quietDone)
                        dialog = new Dialog
                        {
                            Title = "Done",
                            Body = work.Count + " game fonts made from " + chosen.Count + " font" + (chosen.Count == 1 ? "" : "s") + ", in " + folder + ".",
                            Note = "Start the game with KMRP to see them. KMRP sizes them for your resolution and text size.",
                            Buttons = { new DialogButton("Open Folder", false, () => { Program.Open(folder); CloseDialog(null); }), new DialogButton("OK", true, () => CloseDialog(null)) },
                        };
                    }
                    Invalidate();
                }));
            }) { IsBackground = true };
            thread.Start();
        }

        private void Message(string title, string body)
        {
            dialog = new Dialog { Title = title, Body = body, Buttons = { new DialogButton("OK", true, () => CloseDialog(null)) } };
            Invalidate();
        }

        private void CloseDialog(Dialog next)
        {
            if (dialog != null) dialog.Closed();
            dialog = next;
            Invalidate();
        }

        // ---- pop-ups ----

        private sealed class DialogButton
        {
            public string Label;
            public bool Primary;
            public Action Click;
            public Bitmap Logo;
            public DialogButton(string label, bool primary, Action click, Bitmap logo = null) { Label = label; Primary = primary; Click = click; Logo = logo; }
        }

        private class Dialog
        {
            public string Title, Body, Note;
            public float Width = 640;
            public List<DialogButton> Links = new List<DialogButton>();
            public List<DialogButton> Buttons = new List<DialogButton>();

            public virtual void Paint(MainForm form, Graphics g)
            {
                float bodyH = Lines(g, Body, Width - 56, Theme.Body(15)) * 15 * 1.5f;
                float noteH = Note == null ? 0 : Lines(g, Note, Width - 56, Theme.Body(13.5f)) * 13.5f * 1.5f + 12;
                float linksH = Links.Count > 0 ? 60 : 0;
                float h = 26 + 34 + 10 + bodyH + noteH + linksH + 24 + 48 + 24;
                var r = new RectangleF((CanvasW - Width) / 2, (CanvasH - h) / 2, Width, h);
                Frame(g, r);
                float y = r.Y + 26;
                Theme.Draw(g, Title, Theme.Display(26), Theme.Text, new RectangleF(r.X + 28, y, r.Width - 56, 34));
                y += 44;
                using (var ink = new SolidBrush(Theme.Muted)) g.DrawString(Body, Theme.Body(15), ink, new RectangleF(r.X + 28, y, r.Width - 56, bodyH + 4), Wrap);
                y += bodyH;
                if (Note != null)
                {
                    y += 12;
                    using (var ink = new SolidBrush(Theme.Faint)) g.DrawString(Note, Theme.Body(13.5f), ink, new RectangleF(r.X + 28, y, r.Width - 56, noteH), Wrap);
                    y += noteH - 12;
                }
                if (Links.Count > 0)
                {
                    y += 22;
                    // Compact buttons, side by side in the middle.
                    const float lw = 230, lh = 42;
                    float lx = r.X + (r.Width - Links.Count * lw - 12 * (Links.Count - 1)) / 2;
                    for (int i = 0; i < Links.Count; i++)
                        LinkButton(form, g, Links[i], new RectangleF(lx + i * (lw + 12), y, lw, lh), "link" + i);
                    y += lh - 4;
                }
                y += 24;
                PaintButtons(form, g, Buttons, r, y);
            }

            protected static readonly StringFormat Wrap = new StringFormat(StringFormat.GenericTypographic) { Trimming = StringTrimming.Word };

            protected static int Lines(Graphics g, string text, float width, Font font)
            {
                if (string.IsNullOrEmpty(text)) return 0;
                int chars, lines;
                g.MeasureString(text, font, new SizeF(width, 10000), Wrap, out chars, out lines);
                return Math.Max(1, lines);
            }

            protected static void Frame(Graphics g, RectangleF r)
            {
                using (var shadow = Theme.Round(new RectangleF(r.X - 4, r.Y + 10, r.Width + 8, r.Height + 8), 16))
                using (var b = new SolidBrush(Color.FromArgb(110, 0, 0, 0))) g.FillPath(b, shadow);
                Theme.Box(g, r, 12, Theme.Panel, Theme.Edge);
            }

            protected static void PaintButtons(MainForm form, Graphics g, List<DialogButton> buttons, RectangleF r, float y)
            {
                // One button sits in the middle; more line up on the right.
                float x = r.Right - 28;
                if (buttons.Count == 1)
                    x = r.X + r.Width / 2 + Math.Max(buttons[0].Primary ? 200 : 130, Theme.Width(g, buttons[0].Label, Theme.Display(18)) + 60) / 2;
                for (int i = buttons.Count - 1; i >= 0; i--)
                {
                    var button = buttons[i];
                    float w = Math.Max(button.Primary ? 200 : 130, Theme.Width(g, button.Label, Theme.Display(18)) + 60);
                    var b = new RectangleF(x - w, y, w, 48);
                    string id = "button" + i;
                    bool on = form.Hover(id);
                    if (button.Primary)
                        using (var p = Theme.Round(b, 5))
                        using (var fill = new LinearGradientBrush(b, on ? Color.FromArgb(88, 222, 250) : Theme.AccentTop, Theme.AccentBottom, 90f))
                            g.FillPath(fill, p);
                    else Theme.Box(g, b, 5, on ? Theme.ButtonHover : Theme.Button, on ? Theme.Accent : Theme.Edge);
                    Theme.Draw(g, button.Label, Theme.Display(18), button.Primary ? Theme.AccentInk : Theme.Text, b, Theme.Centre);
                    form.AddHit(b, id, button.Click);
                    x -= w + 12;
                }
            }

            private static void LinkButton(MainForm form, Graphics g, DialogButton link, RectangleF b, string id)
            {
                bool on = form.Hover(id);
                Theme.Box(g, b, 6, on ? Theme.ButtonHover : Theme.Button, on ? Theme.Accent : Theme.Edge);
                // The logo as tall as the label's capitals with a little to spare, and both
                // centred on the button's middle by their ink, not their line boxes.
                Font font = Theme.Display(18);
                float capTop, capBottom;
                Theme.Caps(font, out capTop, out capBottom);
                float textW = Theme.Width(g, link.Label, font);
                float iconH = (float)Math.Round((capBottom - capTop) * 1.7f);
                float iconW = link.Logo != null ? iconH * link.Logo.Width / link.Logo.Height : 0;
                float x = b.X + (b.Width - textW - (iconW > 0 ? iconW + 12 : 0)) / 2, middle = b.Y + b.Height / 2;
                if (link.Logo != null)
                {
                    form.DrawSharp(g, link.Logo, "linklogo:" + link.Label, new RectangleF(x, middle - iconH / 2, iconW, iconH));
                    x += iconW + 12;
                }
                using (var ink = new SolidBrush(Theme.Text))
                    g.DrawString(link.Label, font, ink, x, middle - (capTop + capBottom) / 2, StringFormat.GenericTypographic);
                form.AddHit(b, id, link.Click);
            }

            public virtual bool Key(MainForm form, Keys key)
            {
                if (key == Keys.Escape && Buttons.Count > 0) { (Buttons.FirstOrDefault(b => !b.Primary) ?? Buttons[0]).Click(); return true; }
                if (key == Keys.Enter && Buttons.Count > 0) { (Buttons.FirstOrDefault(b => b.Primary) ?? Buttons[0]).Click(); return true; }
                return false;
            }

            public virtual void Wheel(MainForm form, int delta) { }
            public virtual void DoubleClick(MainForm form, string id) { }
            public virtual void Closed() { }
        }

        private Dialog KmrpDialog()
        {
            var d = new Dialog
            {
                Title = "Made for KMRP",
                Width = 680,
                Body = "The fonts you make here need KMRP to show at the right size in the game.",
                Note = "Don't have KMRP yet? Get it here:",
            };
            d.Links.Add(new DialogButton("DeadlyStream", false, () => Program.Open(Program.DeadlyStream), deadlyStreamLogo));
            d.Links.Add(new DialogButton("GitHub Releases", false, () => Program.Open(Program.GitHubReleases), gitHubLogo));
            d.Buttons.Add(new DialogButton("Continue", true, () => CloseDialog(null)));
            return d;
        }

        /// <summary>The faces of a collection or the styles of a variable font, each in its
        /// own letters, to pick one for a tile.</summary>
        private sealed class PickerDialog : Dialog
        {
            public Tile Tile;
            public List<FontFaceChoice> Faces;
            public int Selected, Top;
            public readonly Dictionary<int, LoadedFace> Loaded = new Dictionary<int, LoadedFace>();
            public readonly Dictionary<string, Bitmap> Samples = new Dictionary<string, Bitmap>();
            public string Sample;
            public Action<int> Use;
            private const int Visible = 6;
            private const float RowH = 76;

            public override void Paint(MainForm form, Graphics g)
            {
                int rows = Math.Min(Visible, Faces.Count);
                float listH = rows * RowH + (rows - 1) * 8;
                float h = 26 + 34 + 8 + 24 + 18 + listH + 22 + 48 + 24;
                var r = new RectangleF((CanvasW - Width) / 2, (CanvasH - h) / 2, Width, h);
                Frame(g, r);
                float y = r.Y + 26;
                Theme.Draw(g, Title, Theme.Display(26), Theme.Text, new RectangleF(r.X + 28, y, r.Width - 56, 34));
                y += 42;
                Font plain = Theme.Body(14.5f), strong = Theme.Body(14.5f, true);
                string a = "Pick the one to use for ", c = ". Each is shown in its own letters.";
                float x = r.X + 28;
                using (var ink = new SolidBrush(Theme.Muted)) g.DrawString(a, plain, ink, x, y, StringFormat.GenericTypographic);
                // The trailing space measured on its own (see Rich).
                x += Theme.Width(g, a.TrimEnd(' '), plain) + Theme.Width(g, "a a", plain) - Theme.Width(g, "aa", plain);
                using (var ink = new SolidBrush(Theme.Text)) g.DrawString(Tile.Def.Name, strong, ink, x, y, StringFormat.GenericTypographic);
                x += Theme.Width(g, Tile.Def.Name, strong);
                using (var ink = new SolidBrush(Theme.Muted)) g.DrawString(c, plain, ink, x, y, StringFormat.GenericTypographic);
                y += 24 + 18;

                var list = new RectangleF(r.X + 28, y, r.Width - 56 - (Faces.Count > Visible ? 14 : 0), listH);
                for (int i = 0; i < rows; i++)
                {
                    int n = Top + i;
                    var row = new RectangleF(list.X, y + i * (RowH + 8), list.Width, RowH);
                    bool on = n == Selected, lit = form.Hover("row" + n);
                    Theme.Box(g, row, 7, on ? Color.FromArgb(11, 28, 44) : lit ? Color.FromArgb(14, 24, 38) : Theme.Window, on ? Theme.Accent : Theme.TileEdge);
                    var dot = new RectangleF(row.X + 16, row.Y + (RowH - 18) / 2, 18, 18);
                    using (var pen = new Pen(on ? Theme.Accent : Color.FromArgb(58, 80, 112), 2)) g.DrawEllipse(pen, dot);
                    if (on) using (var b = new SolidBrush(Theme.Accent)) g.FillEllipse(b, dot.X + 4.5f, dot.Y + 4.5f, 9, 9);
                    Theme.Draw(g, Faces[n].Name, Theme.Display(15), on ? Theme.Accent : Theme.Soft, new RectangleF(row.X + 50, row.Y + 9, row.Width - 66, 20));
                    Bitmap sample = SampleFor(form, n, 34 * form.scale);
                    if (sample != null)
                    {
                        float room = (row.Width - 66) * form.scale;
                        if (sample.Width > room)
                        {
                            var clip = g.Clip;
                            g.SetClip(new RectangleF(row.X + 50, row.Y, row.Width - 62, row.Height));
                            form.DrawDevice(g, sample, row.X + 49, row.Y + 30);
                            g.Clip = clip;
                        }
                        else form.DrawDevice(g, sample, row.X + 49, row.Y + 30);
                    }
                    form.AddHit(row, "row" + n, () => { Selected = n; form.Invalidate(); });
                }
                if (Faces.Count > Visible)
                {
                    var rail = new RectangleF(list.Right + 6, y, 4, listH);
                    Theme.Box(g, rail, 2, Theme.TileEdge, Color.Empty);
                    float thumbH = listH * Visible / Faces.Count, thumbY = y + (listH - thumbH) * Top / (Faces.Count - Visible);
                    Theme.Box(g, new RectangleF(rail.X - 1, thumbY, 6, thumbH), 3, Theme.Accent, Color.Empty);
                }
                PaintButtons(form, g, Buttons, r, y + listH + 22);
            }

            private Bitmap SampleFor(MainForm form, int n, float height)
            {
                string key = n + "@" + (int)height;
                Bitmap b;
                if (Samples.TryGetValue(key, out b)) return b;
                try
                {
                    LoadedFace face;
                    if (!Loaded.TryGetValue(n, out face)) Loaded[n] = face = FontFiles.Load(Faces[n]);
                    b = Atlas.Line(face, Sample, height, Color.FromArgb(200, 226, 250));
                }
                catch (Exception) { b = null; }
                Samples[key] = b;
                return b;
            }

            public override void Wheel(MainForm form, int delta)
            {
                Top = Math.Max(0, Math.Min(Faces.Count - Visible, Top - Math.Sign(delta)));
            }

            public Action Cancel;

            public override bool Key(MainForm form, Keys key)
            {
                if (key == Keys.Escape) { Cancel(); return true; }
                if (key == Keys.Down || key == Keys.Up)
                {
                    Selected = Math.Max(0, Math.Min(Faces.Count - 1, Selected + (key == Keys.Down ? 1 : -1)));
                    if (Selected < Top) Top = Selected;
                    if (Selected >= Top + Visible) Top = Selected - Visible + 1;
                    return true;
                }
                return base.Key(form, key);
            }

            public override void DoubleClick(MainForm form, string id)
            {
                if (id.StartsWith("row")) Use(int.Parse(id.Substring(3)));
            }

            public override void Closed()
            {
                foreach (var face in Loaded.Values) face.Dispose();
                foreach (var b in Samples.Values) if (b != null) b.Dispose();
            }
        }

        private Dialog Picker(Tile tile, List<FontFaceChoice> faces, bool reopen)
        {
            bool styles = faces.Any(f => f.Axes != null);
            var picker = new PickerDialog
            {
                Width = 760,
                Tile = tile,
                Faces = faces,
                Title = System.IO.Path.GetFileName(faces[0].Path) + " holds " + faces.Count + (styles ? " styles" : " fonts"),
                Sample = string.Join(" ", tile.Def.Lines.Select(l => string.Join(" ", l.Select(p => p.Text)))),
            };
            if (reopen && tile.Choice != null)
            {
                int at = faces.FindIndex(f => f.FaceIndex == tile.Choice.FaceIndex && f.Name == tile.Choice.Name);
                if (at >= 0) { picker.Selected = at; picker.Top = Math.Max(0, Math.Min(faces.Count - 6, at - 2)); }
            }
            picker.Use = n => { var f = faces[n]; CloseDialog(null); Apply(tile, f, faces); };
            picker.Cancel = () => CloseDialog(null);
            picker.Buttons.Add(new DialogButton(reopen ? "Another File\u2026" : "Cancel", false, () =>
            {
                CloseDialog(null);
                if (reopen) Browse(tile);
            }));
            picker.Buttons.Add(new DialogButton("Use this font", true, () => picker.Use(picker.Selected)));
            return picker;
        }
    }
}
