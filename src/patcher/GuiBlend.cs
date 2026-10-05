using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;

namespace Kmrp
{
    /// <summary>KMRP's menus for a resolution the build has no set for.
    ///
    /// The C# of macos/tools/kmrp-guiblend.c, which the Mac installer runs, step for
    /// step, so that one size gets the same menus on both platforms. The table is
    /// gui-blend.bin from tools/build_gui_blend_table.py, whose docstring gives its
    /// format: per .gui file a template, the numeric fields that vary between
    /// resolutions, and their values in each finished set the build made. The blend is
    /// tools/derive_resolution_gui_set.py's: the two aspect-ratio families on either
    /// side of the size, each at the two heights around it, weighted and rounded once
    /// (half away from zero). It interpolates numbers the build made; KMRP's layout
    /// logic stays in the build.
    ///
    /// Two files are made for the size rather than blended, with the fonts of the set
    /// whose fonts and art the installer takes (the nearest listed one): the
    /// Container, widened until "Switch To Give Item" and its badge fit
    /// (fit_container_to_caption), and the Controller Layout screen, laid out with
    /// build_controller_layout.py's build_gui arithmetic, every number from the table
    /// by name.
    ///
    /// The lists scale_listbox_padding.py makes as tall as whole rows (fit_list_to_rows:
    /// the Container, the granted popup, character creation's Feats and a few
    /// full-screen lists at low resolutions) are fitted again on the blend, at the size's
    /// own row heights (FitRows), before the Container is widened, as the build does.
    ///
    /// And the controller badges (2026-09-30): every texture the prompt
    /// manifest lists, drawn again for its blended button. A badge is a 512x64 texture
    /// the engine stretches over its whole button, drawn to come out round on that
    /// button, so the nearest set's, drawn for that set's buttons, came out stretched on
    /// buttons of another shape (1.86 times as wide as tall at 3440x1400). DrawBadge is
    /// build_controller_prompt_textures.py's build_prompt_tga with Pillow's arithmetic,
    /// so a set the blend resolves to itself comes out with the build's badges byte for
    /// byte; the manifest is rewritten with the blended button sizes (and the widening
    /// and row fits), which is what the installer's re-centring for the player's
    /// dialog.tlk then reads. So is
    /// lbl_mileftbot.tga, the HUD's button-row boxes, which build_menubg_texture.py
    /// draws from each set's mipc28x6.gui and which the nearest set's drew out of step
    /// with the blended buttons (DrawHud).
    ///
    /// Table version 4: the row fits and the badges both came as version 3 on
    /// 2026-09-30, on the macos branch and on master, in two formats; the merge of the
    /// two the same day carries both.
    ///
    /// Byte-identical to the helper means the same rounding at every step, so the
    /// expressions below keep the C's order of operations, Round is half to even as
    /// rint and Python's round() are, and RoundHalfAway is the C's
    /// copysign(floor(fabs(v) + 0.5), v). The .NET JIT fuses no multiply-add, which
    /// the helper forbids with FP_CONTRACT OFF. Numbers read from text go through
    /// ParsePrefix, which rounds as strtod does. testing/regression/Test-GuiBlendHelper.py
    /// runs this through the installer's --derive-gui and requires the helper's files,
    /// byte for byte.</summary>
    internal sealed class GuiBlend
    {
        internal const string ResourceName = "Kmrp.guiblend";
        internal const int MinimumWidth = 640;
        internal const int MinimumHeight = 480;

        private sealed class Anchor
        {
            internal uint Width, Height, Family;
        }

        private sealed class Term
        {
            internal int Index;
            internal double Weight;
        }

        /// <summary>build_gui_blend_table.py's fit record: fit_container_to_caption and
        /// the badge geometry of build_controller_prompt_textures.py.</summary>
        private sealed class Fit
        {
            internal string Name, Row;
            internal double RadiusShort, Radius, Gap, Edge, Margin;
            internal uint ShortBelow, Inset, Left, Width, ButtonWidth, ButtonHeight;
            internal uint[] Widths;
        }

        private sealed class Row
        {
            internal char Side;
            internal double GlyphX, RowY;
            internal string Caption;
        }

        /// <summary>build_gui_blend_table.py's row-fit record: a list
        /// scale_listbox_padding.py's fit_list_to_rows makes as tall as whole rows. Offsets
        /// of the list's HEIGHT, its border's DIMENSION, its scrollbar's HEIGHT (0: none),
        /// and in a popup the panel's TOP and HEIGHT and the TOPs of the controls below
        /// the list.</summary>
        private sealed class RowFit
        {
            internal string Name, Tag;
            internal bool Popup;
            internal double Loose;
            internal uint Divisor, Height, Dimension, Bar, PanelTop, PanelHeight;
            internal uint[] Bases, Below;
        }

        /// <summary>build_gui_blend_table.py's layout record: build_controller_layout.py's
        /// layout_constants, layout_rows and where each control's extent sits.</summary>
        private sealed class Layout
        {
            internal string Name, Font;
            internal List<KeyValuePair<string, double>> Constants = new List<KeyValuePair<string, double>>();
            internal List<Row> Rows = new List<Row>();
            internal uint RootWidth, RootHeight;
            internal uint[][] Extents;
        }

        private sealed class GuiFile
        {
            internal string Name;
            internal byte[] Template;
            internal uint[] Offsets;
            internal int[] Values;   // anchor-major: [anchor * slots + slot]
        }

        /// <summary>A caption font as parse_font_metrics reads its TXI, and build_gui's
        /// line height.</summary>
        private sealed class Font
        {
            internal double[] Advances = new double[256];
            internal int Count;
            internal double Spacing, LineHeight;
        }

        /// <summary>Glyph artwork as _load_glyph_art loads it: RGBA, top row first.</summary>
        private sealed class Glyph
        {
            internal int Width, Height;
            internal byte[] Rgba;
        }

        /// <summary>One prompt manifest row: where its button is, its glyph, its backing,
        /// and the controls whose least height sizes it (none: its own).</summary>
        private sealed class Prompt
        {
            internal string ResRef, Gui;
            internal uint WidthAt, HeightAt;
            internal int Glyph;
            internal byte[] Backing;   // null: none
            internal uint[] Sizing;
            // Table version 5: how far inside the button each of its two borders draws
            // its fill (build_controller_prompt_textures.py, fill_inset).
            internal int InsetNormal, InsetFocus;
        }

        // build_prompt_tga's constants.
        private int textureWidth, textureHeight, shortBelow, minArea;
        private double radius, radiusShort, gap, edge, centerY, fallbackX, fitMargin;
        private byte[] footer;
        private readonly List<Glyph> glyphs = new List<Glyph>();
        private readonly List<Prompt> prompts = new List<Prompt>();

        /// <summary>build_menubg_texture.py's lbl_mileftbot.tga: where LBL_MENUBG and the
        /// eight buttons sit in the HUD the size loads.</summary>
        private sealed class Hud
        {
            internal string Gui, Texture;
            internal int Width, Height, EdgeAlpha;
            internal uint BackdropLeft, BackdropWidth;
            internal uint[] Left, ButtonWidth;
        }

        private readonly List<Hud> huds = new List<Hud>();

        private readonly double[] aspects;
        private readonly List<Anchor> anchors = new List<Anchor>();
        private readonly List<Fit> fits = new List<Fit>();
        private readonly List<Layout> layouts = new List<Layout>();
        private readonly List<RowFit> rowFits = new List<RowFit>();
        private readonly List<GuiFile> files = new List<GuiFile>();

        private GuiBlend(double[] aspects)
        {
            this.aspects = aspects;
        }

        // ------------------------------------------------------------ the table

        private static GuiBlend shared;
        private static readonly object sharedLock = new object();

        /// <summary>The installer's table, read once: the resolution list asks it about
        /// every size it offers.</summary>
        internal static GuiBlend Shared()
        {
            lock (sharedLock)
            {
                if (shared == null)
                    shared = Load();
                return shared;
            }
        }

        /// <summary>The table this installer carries, gzipped by build_kmrp.ps1.</summary>
        internal static GuiBlend Load()
        {
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName);
            if (stream == null)
                throw new InvalidDataException("The table for resolutions without a menu set is missing from this patcher.");
            using (stream)
                return Read(ReadAll(stream));
        }

        /// <summary>A table as build_gui_blend_table.py writes it, or gzipped.</summary>
        internal static GuiBlend Read(byte[] table)
        {
            if (table.Length > 2 && table[0] == 0x1F && table[1] == 0x8B)
                using (GZipStream unzip = new GZipStream(new MemoryStream(table), CompressionMode.Decompress))
                    table = ReadAll(unzip);
            Reader r = new Reader(table);
            if (r.Ascii(4) != "KGBL" || r.U32() != 5)
                throw new InvalidDataException("Not a version 5 blend table.");
            uint familyCount = r.U32();
            if (familyCount == 0 || familyCount > 16)
                throw new InvalidDataException("The blend table has a bad family count.");
            double[] aspects = new double[familyCount];
            for (int i = 0; i < aspects.Length; i++)
                aspects[i] = r.F64();
            GuiBlend blend = new GuiBlend(aspects);
            uint anchorCount = r.U32();
            for (uint i = 0; i < anchorCount; i++)
                blend.anchors.Add(new Anchor { Width = r.U32(), Height = r.U32(), Family = r.U32() });

            uint fitCount = r.U32();
            if (fitCount > 4)
                throw new InvalidDataException("The blend table has a bad fit count.");
            for (uint i = 0; i < fitCount; i++)
            {
                Fit fit = new Fit();
                fit.Name = r.Text(256);
                fit.Row = r.Text(64);
                fit.RadiusShort = r.F64();
                fit.Radius = r.F64();
                fit.ShortBelow = r.U32();
                fit.Gap = r.F64();
                fit.Edge = r.F64();
                fit.Inset = r.U32();
                fit.Margin = r.F64();
                fit.Left = r.U32();
                fit.Width = r.U32();
                fit.ButtonWidth = r.U32();
                fit.ButtonHeight = r.U32();
                uint count = r.U32();
                if (count > 16)
                    throw new InvalidDataException("The blend table has a bad fit record.");
                fit.Widths = new uint[count];
                for (int k = 0; k < fit.Widths.Length; k++)
                    fit.Widths[k] = r.U32();
                blend.fits.Add(fit);
            }

            uint layoutCount = r.U32();
            if (layoutCount > 1)
                throw new InvalidDataException("The blend table has a bad layout count.");
            for (uint i = 0; i < layoutCount; i++)
            {
                Layout layout = new Layout();
                layout.Name = r.Text(256);
                layout.Font = r.Text(64);
                uint constants = r.U32();
                if (constants > 96)
                    throw new InvalidDataException("The blend table has a bad layout record.");
                for (uint k = 0; k < constants; k++)
                {
                    string name = r.Text(32);
                    layout.Constants.Add(new KeyValuePair<string, double>(name, r.F64()));
                }
                uint rows = r.U32();
                if (rows > 32)
                    throw new InvalidDataException("The blend table has a bad layout record.");
                for (uint k = 0; k < rows; k++)
                {
                    Row row = new Row();
                    row.Side = (char)r.U8();
                    row.GlyphX = r.F64();
                    row.RowY = r.F64();
                    row.Caption = r.Text(128);
                    layout.Rows.Add(row);
                }
                layout.RootWidth = r.U32();
                layout.RootHeight = r.U32();
                uint controls = r.U32();
                if (controls > 96)
                    throw new InvalidDataException("The blend table has a bad layout record.");
                layout.Extents = new uint[controls][];
                for (uint k = 0; k < controls; k++)
                    layout.Extents[k] = new[] { r.U32(), r.U32(), r.U32(), r.U32() };
                // build_gui's control count, which Generate writes in order.
                uint expected = 10 + 2 * (uint)Constant(layout, "ROWS") + (uint)Constant(layout, "DECOR_COUNT") + 1;
                if (controls != expected || rows != (uint)Constant(layout, "ROWS"))
                    throw new InvalidDataException(layout.Name + ": " + controls + " controls, the layout makes " + expected + ".");
                blend.layouts.Add(layout);
            }

            uint rowFitCount = r.U32();
            if (rowFitCount > 16)
                throw new InvalidDataException("The blend table has a bad row-fit count.");
            for (uint i = 0; i < rowFitCount; i++)
            {
                RowFit fit = new RowFit { Name = r.Text(256), Tag = r.Text(64) };
                fit.Popup = r.U8() != 0;
                fit.Loose = r.F64();
                fit.Divisor = r.U32();
                uint bases = r.U32();
                if (fit.Divisor == 0 || bases == 0 || bases > 4)
                    throw new InvalidDataException("The blend table has a bad row-fit record.");
                fit.Bases = new uint[bases];
                for (int k = 0; k < fit.Bases.Length; k++)
                    fit.Bases[k] = r.U32();
                fit.Height = r.U32();
                fit.Dimension = r.U32();
                fit.Bar = r.U32();
                fit.PanelTop = r.U32();
                fit.PanelHeight = r.U32();
                uint below = r.U32();
                if (below > 16)
                    throw new InvalidDataException("The blend table has a bad row-fit record.");
                fit.Below = new uint[below];
                for (int k = 0; k < fit.Below.Length; k++)
                    fit.Below[k] = r.U32();
                blend.rowFits.Add(fit);
            }

            blend.textureWidth = (int)r.U32();
            blend.textureHeight = (int)r.U32();
            blend.radius = r.F64();
            blend.radiusShort = r.F64();
            blend.shortBelow = (int)r.U32();
            blend.gap = r.F64();
            blend.edge = r.F64();
            blend.centerY = r.F64();
            blend.fallbackX = r.F64();
            blend.minArea = (int)r.U32();
            blend.fitMargin = r.F64();
            int footerLength = r.U16();
            if (footerLength > 64 || blend.textureWidth <= 0 || blend.textureWidth > 4096 ||
                blend.textureHeight <= 0 || blend.textureHeight > 4096)
                throw new InvalidDataException("The blend table has a bad badge record.");
            blend.footer = r.Bytes(footerLength);
            uint glyphCount = r.U32();
            if (glyphCount > 64)
                throw new InvalidDataException("The blend table has a bad glyph count.");
            for (uint i = 0; i < glyphCount; i++)
            {
                Glyph glyph = new Glyph { Width = (int)r.U32(), Height = (int)r.U32() };
                if (glyph.Width <= 0 || glyph.Height <= 0 || glyph.Width > 1024 || glyph.Height > 1024)
                    throw new InvalidDataException("The blend table has a bad glyph.");
                glyph.Rgba = r.Bytes(glyph.Width * glyph.Height * 4);
                blend.glyphs.Add(glyph);
            }
            uint promptCount = r.U32();
            if (promptCount > 4096)
                throw new InvalidDataException("The blend table has a bad prompt count.");
            for (uint i = 0; i < promptCount; i++)
            {
                Prompt prompt = new Prompt { ResRef = r.Text(32), Gui = r.Text(256) };
                prompt.WidthAt = r.U32();
                prompt.HeightAt = r.U32();
                prompt.Glyph = (int)r.U32();
                bool backed = r.U8() != 0;
                byte[] backing = r.Bytes(4);
                prompt.Backing = backed ? backing : null;
                uint sizing = r.U32();
                if (prompt.Glyph < 0 || prompt.Glyph >= blend.glyphs.Count || sizing > 16)
                    throw new InvalidDataException("The blend table has a bad prompt record.");
                prompt.Sizing = new uint[sizing];
                for (int k = 0; k < prompt.Sizing.Length; k++)
                    prompt.Sizing[k] = r.U32();
                uint insetNormal = r.U32(), insetFocus = r.U32();
                if (insetNormal > 4096 || insetFocus > 4096)
                    throw new InvalidDataException("The blend table has a bad prompt record.");
                prompt.InsetNormal = (int)insetNormal;
                prompt.InsetFocus = (int)insetFocus;
                blend.prompts.Add(prompt);
            }
            uint hudCount = r.U32();
            if (hudCount > 1)
                throw new InvalidDataException("The blend table has a bad HUD count.");
            for (uint i = 0; i < hudCount; i++)
            {
                Hud hud = new Hud { Gui = r.Text(256), Texture = r.Text(64) };
                hud.Width = (int)r.U32();
                hud.Height = (int)r.U32();
                hud.EdgeAlpha = (int)r.U32();
                hud.BackdropLeft = r.U32();
                hud.BackdropWidth = r.U32();
                uint count = r.U32();
                if (count > 16 || hud.Width <= 0 || hud.Width > 4096 || hud.Height <= 0 || hud.Height > 4096 ||
                    hud.EdgeAlpha > 255 || hud.Texture.IndexOf('/') >= 0 || hud.Texture.IndexOf('\\') >= 0)
                    throw new InvalidDataException("The blend table has a bad HUD record.");
                hud.Left = new uint[count];
                hud.ButtonWidth = new uint[count];
                for (int k = 0; k < count; k++)
                {
                    hud.Left[k] = r.U32();
                    hud.ButtonWidth[k] = r.U32();
                }
                blend.huds.Add(hud);
            }

            uint fileCount = r.U32();
            for (uint i = 0; i < fileCount; i++)
            {
                GuiFile file = new GuiFile();
                int nameLength = r.U16();
                if (nameLength == 0 || nameLength >= 256)
                    throw new InvalidDataException("The blend table has a bad file name.");
                file.Name = r.Ascii(nameLength);
                if (file.Name.IndexOf('/') >= 0 || file.Name.IndexOf('\\') >= 0)
                    throw new InvalidDataException("The blend table has a bad file name: " + file.Name);
                file.Template = r.Bytes((int)r.U32());
                uint slots = r.U32();
                file.Offsets = new uint[slots];
                for (uint s = 0; s < slots; s++)
                {
                    file.Offsets[s] = r.U32();
                    if (r.U32() != 5 || file.Offsets[s] + 4 > file.Template.Length)
                        throw new InvalidDataException(file.Name + ": unsupported field in the blend table.");
                }
                file.Values = new int[checked((int)(anchorCount * slots))];
                for (int v = 0; v < file.Values.Length; v++)
                    file.Values[v] = (int)r.U32();
                blend.files.Add(file);
            }
            return blend;
        }

        /// <summary>The files Derive reads from the set: the prompt manifest, and the
        /// fonts as "&lt;resref&gt;.txi".</summary>
        internal List<string> SetFilesNeeded()
        {
            List<string> names = new List<string>();
            names.Add(ControllerPromptGenerator.ManifestName);
            foreach (Layout layout in layouts)
                names.Add(layout.Font + ".txi");
            return names;
        }

        // ------------------------------------------------------------ the blend

        /// <summary>The finished sets the blend takes, as "WxH weight" lines, as the
        /// helper prints them; empty when the size is outside what they cover.</summary>
        internal List<string> Describe(int width, int height)
        {
            List<string> lines = new List<string>();
            foreach (Term term in Terms(width, height))
                lines.Add(anchors[term.Index].Width.ToString(CultureInfo.InvariantCulture) + "x" +
                    anchors[term.Index].Height.ToString(CultureInfo.InvariantCulture) + " " +
                    term.Weight.ToString("F6", CultureInfo.InvariantCulture));
            return lines;
        }

        /// <summary>Whether the finished sets reach this size: from 640x480 up, and
        /// between the widest and narrowest families, each with sets above and below
        /// the height.</summary>
        internal bool Covers(int width, int height)
        {
            return Terms(width, height).Count > 0;
        }

        /// <summary>Every .gui of the table, in its order, for WIDTHxHEIGHT, then every
        /// badge the prompt manifest lists, the manifest itself and the HUD's button-row
        /// boxes, with the set's files
        /// (SetFilesNeeded) read through readSetFile. Throws when the size is outside the
        /// sets' reach or a set file is missing or unreadable.</summary>
        internal List<KeyValuePair<string, byte[]>> Derive(int width, int height, Func<string, string> readSetFile)
        {
            List<Term> terms = Terms(width, height);
            if (terms.Count == 0)
                throw new ArgumentException(width.ToString(CultureInfo.InvariantCulture) +
                    "x" + height.ToString(CultureInfo.InvariantCulture) + " is outside the resolutions the menu sets cover.");

            double[] captions = new double[fits.Count];
            if (fits.Count > 0)
            {
                string manifest = readSetFile(ControllerPromptGenerator.ManifestName);
                for (int i = 0; i < fits.Count; i++)
                    if (!CaptionWidth(manifest, fits[i].Row, out captions[i]))
                        throw new InvalidDataException(ControllerPromptGenerator.ManifestName + " has no row for " + fits[i].Row + ".");
            }
            Font[] fonts = new Font[layouts.Count];
            for (int i = 0; i < layouts.Count; i++)
            {
                fonts[i] = ReadFont(readSetFile(layouts[i].Font + ".txi"));
                if (fonts[i] == null)
                    throw new InvalidDataException(layouts[i].Font + ".txi has no glyph metrics.");
            }

            List<KeyValuePair<string, byte[]>> result = new List<KeyValuePair<string, byte[]>>();
            Dictionary<string, byte[]> byName = new Dictionary<string, byte[]>(StringComparer.Ordinal);
            int[] widened = new int[fits.Count];
            int[] fitted = new int[rowFits.Count];
            foreach (GuiFile file in files)
            {
                byte[] output = (byte[])file.Template.Clone();
                int slots = file.Offsets.Length;
                for (int s = 0; s < slots; s++)
                {
                    double sum = 0.0;
                    foreach (Term term in terms)
                    {
                        double product = file.Values[term.Index * slots + s] * term.Weight;
                        sum = sum + product;
                    }
                    SetI32(output, file.Offsets[s], (int)RoundHalfAway(sum));
                }
                // The row fits first, as the build makes them before widening the Container.
                for (int i = 0; i < rowFits.Count; i++)
                {
                    if (rowFits[i].Name != file.Name)
                        continue;
                    RowFit rowFit = rowFits[i];
                    bool bad = rowFit.Height + 4 > output.Length || rowFit.Dimension + 4 > output.Length ||
                        rowFit.Bar + 4 > output.Length || rowFit.PanelTop + 4 > output.Length ||
                        rowFit.PanelHeight + 4 > output.Length;
                    foreach (uint offset in rowFit.Below)
                        bad |= offset + 4 > output.Length;
                    if (bad || (rowFit.Popup && (rowFit.PanelTop == 0 || rowFit.PanelHeight == 0)))
                        throw new InvalidDataException(file.Name + ": the row fit is outside the file.");
                    fitted[i] = FitRows(rowFit, output, height);
                }
                for (int i = 0; i < fits.Count; i++)
                {
                    if (fits[i].Name != file.Name)
                        continue;
                    Fit fit = fits[i];
                    bool bad = fit.Left + 4 > output.Length || fit.Width + 4 > output.Length ||
                        fit.ButtonWidth + 4 > output.Length || fit.ButtonHeight + 4 > output.Length;
                    foreach (uint offset in fit.Widths)
                        bad |= offset + 4 > output.Length;
                    if (bad)
                        throw new InvalidDataException(file.Name + ": the fit is outside the file.");
                    widened[i] = ApplyFit(fit, output, captions[i]);
                }
                for (int i = 0; i < layouts.Count; i++)
                {
                    if (layouts[i].Name != file.Name)
                        continue;
                    Layout layout = layouts[i];
                    bool bad = layout.RootWidth + 4 > output.Length || layout.RootHeight + 4 > output.Length;
                    foreach (uint[] extent in layout.Extents)
                        foreach (uint offset in extent)
                            bad |= offset + 4 > output.Length;
                    if (bad)
                        throw new InvalidDataException(file.Name + ": the layout is outside the file.");
                    Generate(layout, fonts[i], output);
                }
                result.Add(new KeyValuePair<string, byte[]>(file.Name, output));
                byName[file.Name] = output;
            }

            // The badges, each for its blended button, with the label width the set's
            // manifest gives it, and that manifest with the blended button sizes.
            string promptManifest = readSetFile(ControllerPromptGenerator.ManifestName);
            int[][] sizes = new int[prompts.Count][];
            for (int i = 0; i < prompts.Count; i++)
            {
                Prompt prompt = prompts[i];
                byte[] gui;
                bool bad = !byName.TryGetValue(prompt.Gui, out gui) ||
                    prompt.WidthAt + 4 > gui.Length || prompt.HeightAt + 4 > gui.Length;
                foreach (uint offset in prompt.Sizing)
                    bad |= gui == null || offset + 4 > gui.Length;
                if (bad)
                    throw new InvalidDataException(prompt.ResRef + ": its button is outside " + prompt.Gui + ".");
                int controlWidth = GetI32(gui, prompt.WidthAt), controlHeight = GetI32(gui, prompt.HeightAt);
                int radiusHeight = 0;
                for (int k = 0; k < prompt.Sizing.Length; k++)
                {
                    int sized = GetI32(gui, prompt.Sizing[k]);
                    if (k == 0 || sized < radiusHeight)
                        radiusHeight = sized;
                }
                double label;
                if (controlWidth <= 0 || controlHeight <= 0 || !CaptionWidth(promptManifest, prompt.ResRef, out label))
                    throw new InvalidDataException(prompt.ResRef + ": no manifest row, or no button.");
                sizes[i] = new[] { controlWidth, controlHeight };
                if (controlWidth <= 2 * prompt.InsetNormal || controlHeight <= 2 * prompt.InsetNormal ||
                    controlWidth <= 2 * prompt.InsetFocus || controlHeight <= 2 * prompt.InsetFocus)
                    throw new InvalidDataException(prompt.ResRef + ": its border leaves nothing of its button.");
                result.Add(new KeyValuePair<string, byte[]>(prompt.ResRef + ".tga",
                    DrawBadge(glyphs[prompt.Glyph], controlWidth, controlHeight, label, radiusHeight, prompt.Backing,
                        prompt.InsetNormal)));
                if (prompt.InsetFocus != prompt.InsetNormal)   // focus_resref: "kmf" for "kmr"
                    result.Add(new KeyValuePair<string, byte[]>("kmf" + prompt.ResRef.Substring(3) + ".tga",
                        DrawBadge(glyphs[prompt.Glyph], controlWidth, controlHeight, label, radiusHeight, prompt.Backing,
                            prompt.InsetFocus)));
            }
            result.Add(new KeyValuePair<string, byte[]>(ControllerPromptGenerator.ManifestName,
                RewriteManifest(promptManifest, sizes, widened, fitted)));
            foreach (Hud hud in huds)
            {
                byte[] gui;
                bool bad = !byName.TryGetValue(hud.Gui, out gui) ||
                    hud.BackdropLeft + 4 > gui.Length || hud.BackdropWidth + 4 > gui.Length;
                for (int k = 0; !bad && k < hud.Left.Length; k++)
                    bad |= hud.Left[k] + 4 > gui.Length || hud.ButtonWidth[k] + 4 > gui.Length;
                if (bad)
                    throw new InvalidDataException(hud.Texture + ": its HUD is outside " + hud.Gui + ".");
                result.Add(new KeyValuePair<string, byte[]>(hud.Texture, DrawHud(hud, gui)));
            }
            return result;
        }

        /// <summary>The family at `height`: one set, or the two around it with their
        /// weights. Among sets of the same height, the one nearest the family's aspect
        /// ratio (1360x768 against 1366x768).</summary>
        private int FamilyAtHeight(uint family, double aspect, uint height, Term[] output, out double widthThere)
        {
            int bestBelow = -1, bestAbove = -1, exact = -1;
            for (int i = 0; i < anchors.Count; i++)
            {
                Anchor a = anchors[i];
                if (a.Family != family)
                    continue;
                double off = Math.Abs((double)a.Width / a.Height - aspect);
                if (a.Height == height)
                {
                    if (exact < 0 || off < Math.Abs((double)anchors[exact].Width / anchors[exact].Height - aspect))
                        exact = i;
                }
                else if (a.Height < height)
                {
                    if (bestBelow < 0 || a.Height > anchors[bestBelow].Height ||
                        (a.Height == anchors[bestBelow].Height &&
                         off < Math.Abs((double)anchors[bestBelow].Width / anchors[bestBelow].Height - aspect)))
                        bestBelow = i;
                }
                else
                {
                    if (bestAbove < 0 || a.Height < anchors[bestAbove].Height ||
                        (a.Height == anchors[bestAbove].Height &&
                         off < Math.Abs((double)anchors[bestAbove].Width / anchors[bestAbove].Height - aspect)))
                        bestAbove = i;
                }
            }
            if (exact >= 0)
            {
                output[0] = new Term { Index = exact, Weight = 1.0 };
                widthThere = anchors[exact].Width;
                return 1;
            }
            widthThere = 0;
            if (bestBelow < 0 || bestAbove < 0)
                return 0;
            Anchor lo = anchors[bestBelow], hi = anchors[bestAbove];
            double t = ((double)height - lo.Height) / ((double)hi.Height - lo.Height);
            output[0] = new Term { Index = bestBelow, Weight = 1.0 - t };
            output[1] = new Term { Index = bestAbove, Weight = t };
            widthThere = lo.Width + ((double)hi.Width - lo.Width) * t;
            return 2;
        }

        private List<Term> Terms(int width, int height)
        {
            List<Term> terms = new List<Term>();
            if (width < MinimumWidth || height < MinimumHeight)
                return terms;

            // Families in order of aspect ratio.
            int[] order = new int[aspects.Length];
            for (int i = 0; i < order.Length; i++)
                order[i] = i;
            for (int i = 1; i < order.Length; i++)
                for (int j = i; j > 0 && aspects[order[j]] < aspects[order[j - 1]]; j--)
                {
                    int swap = order[j];
                    order[j] = order[j - 1];
                    order[j - 1] = swap;
                }

            double aspect = (double)width / height;
            int same = -1;
            for (int i = 0; i < order.Length; i++)
                if (Math.Abs(aspects[order[i]] - aspect) < 0.005)
                {
                    same = order[i];
                    break;
                }
            if (same >= 0)
            {
                Term[] found = new Term[2];
                double unused;
                int count = FamilyAtHeight((uint)same, aspects[same], (uint)height, found, out unused);
                for (int i = 0; i < count; i++)
                    terms.Add(found[i]);
            }
            else
            {
                int lower = -1, upper = -1;
                for (int i = 0; i < order.Length; i++)
                {
                    if (aspects[order[i]] < aspect)
                        lower = order[i];
                    else if (aspects[order[i]] > aspect && upper < 0)
                        upper = order[i];
                }
                Term[] a = new Term[2], b = new Term[2];
                double wa = 0, wb = 0;
                int na = lower >= 0 ? FamilyAtHeight((uint)lower, aspects[lower], (uint)height, a, out wa) : 0;
                int nb = upper >= 0 ? FamilyAtHeight((uint)upper, aspects[upper], (uint)height, b, out wb) : 0;
                if (na > 0 && nb > 0)
                {
                    double s = ((double)width - wa) / (wb - wa);
                    for (int i = 0; i < na; i++)
                        terms.Add(new Term { Index = a[i].Index, Weight = a[i].Weight * (1.0 - s) });
                    for (int i = 0; i < nb; i++)
                        terms.Add(new Term { Index = b[i].Index, Weight = b[i].Weight * s });
                }
            }
            // Drop terms with no weight, as the Python does (weight > 1e-9).
            terms.RemoveAll(term => !(term.Weight > 1e-9));
            return terms;
        }

        // ------------------------------------------------------------ the two made files

        /// <summary>scale_listbox_padding.py's row_height: a row of `baseValue` at a
        /// screen `height`, the base times s = max(1, height / 720) in single precision,
        /// rounded half to even, as the game's layout patch and ResolutionPatch size
        /// them.</summary>
        private static int RowHeight(uint baseValue, int height)
        {
            float s = (float)((double)height / 720.0);
            if (s < 1.0f)
                s = 1.0f;
            float product = (float)((double)(float)baseValue * (double)s);
            return (int)Math.Round((double)product);
        }

        /// <summary>fit_list_to_rows on the blended file: the list as tall as whole rows,
        /// each row / Divisor from the next, every kind of row keeping the count that fits;
        /// a popup's controls below the list move with its bottom and its panel changes
        /// about its centre; a full-screen list only shrinks, and only when a kind's gap
        /// is looser than Loose of its row. Returns the change in height, for the
        /// manifest's "fitted" line.</summary>
        private static int FitRows(RowFit fit, byte[] data, int height)
        {
            int inner = GetI32(data, fit.Height) - 2 * GetI32(data, fit.Dimension);
            int wanted = 0;
            bool loose = false;
            foreach (uint baseValue in fit.Bases)
            {
                int row = RowHeight(baseValue, height);
                if (row < 1 || inner < row)
                    throw new InvalidDataException(fit.Name + " " + fit.Tag + ": no " +
                        row.ToString(CultureInfo.InvariantCulture) + "-px row fits " +
                        inner.ToString(CultureInfo.InvariantCulture) + " px.");
                int rows = inner / row;
                loose |= (double)((inner - rows * row) / rows) > row * fit.Loose;
                int rowsHeight = rows * (row + row / (int)fit.Divisor);
                if (rowsHeight > wanted)
                    wanted = rowsHeight;
            }
            int change = wanted - inner;
            if (change == 0 || (!fit.Popup && (!loose || change > 0)))
                return 0;
            AddI32(data, fit.Height, change);
            if (fit.Bar != 0)
                AddI32(data, fit.Bar, change);
            if (fit.Popup)
            {
                foreach (uint offset in fit.Below)
                    AddI32(data, offset, change);
                AddI32(data, fit.PanelTop, -(int)Math.Floor(change / 2.0));   // Python's change // 2
                AddI32(data, fit.PanelHeight, change);
            }
            return change;
        }

        /// <summary>fit_container_to_caption on the blended file: widen until the button
        /// holds the caption and its badge at the designed gap, by an even number of
        /// pixels, the panel about its centre. Returns the widening, for the manifest.</summary>
        private static int ApplyFit(Fit fit, byte[] data, double caption)
        {
            int height = GetI32(data, fit.ButtonHeight);
            double radius = height * (height < (int)fit.ShortBelow ? fit.RadiusShort : fit.Radius);
            // badge_fit_width with the border's inset: the badge fitted to the smaller area.
            if (fit.Inset > 0)
                radius = Math.Min(radius, (height - 2 * (int)fit.Inset) / 2.0 - fit.Margin);
            double need = caption + 2.0 * (fit.Inset + radius * (fit.Gap + 1.0 + fit.Edge));
            int extra = (int)Math.Ceiling(need - GetI32(data, fit.ButtonWidth));
            if (extra <= 0)
                return 0;
            extra += extra % 2;
            AddI32(data, fit.Left, -(extra / 2));
            AddI32(data, fit.Width, extra);
            foreach (uint offset in fit.Widths)
                AddI32(data, offset, extra);
            return extra;
        }

        private static double Constant(Layout layout, string name)
        {
            foreach (KeyValuePair<string, double> constant in layout.Constants)
                if (constant.Key == name)
                    return constant.Value;
            throw new InvalidDataException("The blend table has no layout constant " + name + ".");
        }

        private static void SetExtent(Layout layout, byte[] data, ref int index, double x, double y, double w, double h)
        {
            double[] v = { x, y, w, h };
            for (int k = 0; k < 4; k++)
                SetI32(data, layout.Extents[index][k], (int)Math.Round(v[k]));   // Python's round(): half to even
            index++;
        }

        /// <summary>build_controller_layout.py's build_gui, its extents only: every other
        /// byte of the file is the blend's. Each expression keeps the Python's order of
        /// operations, as the helper's does.</summary>
        private static void Generate(Layout L, Font font, byte[] data)
        {
            double width = GetI32(data, L.RootWidth), height = GetI32(data, L.RootHeight);
            double scale = Math.Max(1, height / Constant(L, "SCALE_HEIGHT"));
            double left = width / 2 - Constant(L, "DESIGN_W") / 2 * scale;
            double spread = Math.Min(Constant(L, "SPREAD"),
                Math.Max(0.0, height / scale - Constant(L, "COMPACT_H") - Constant(L, "SCREEN_MARGIN")));
            double up = Math.Round(spread * Constant(L, "SPREAD_UP") / Constant(L, "SPREAD"));
            double down = spread - up;
            double top = Math.Max(Constant(L, "TOP_MIN_PX") + up * scale,
                (height - (Constant(L, "COMPACT_H") + spread) * scale) / 2 + up * scale);
            int index = 0;

            Add(L, data, ref index, left, top, scale, 0, -up, Constant(L, "DESIGN_W"), Constant(L, "TITLE_H"));
            Add(L, data, ref index, left, top, scale, Constant(L, "BACK_X"), Constant(L, "BACK_Y") + down,
                Constant(L, "BACK_W"), Constant(L, "BACK_H"));
            for (int i = 0; i < 4; i++)
                Add(L, data, ref index, left, top, scale, 0, Constant(L, "FAMILY_Y") - up,
                    Constant(L, "DESIGN_W"), Constant(L, "FAMILY_H"));
            for (int i = 0; i < 2; i++)
                Add(L, data, ref index, left, top, scale, 0, 0, 0, 0);
            Add(L, data, ref index, left, top, scale, Constant(L, "BOARD_X"), Constant(L, "BOARD_Y"),
                Constant(L, "BOARD_W"), Constant(L, "BOARD_H"));
            Add(L, data, ref index, left, top, scale, 0, Constant(L, "HELP_Y") + down,
                Constant(L, "DESIGN_W"), Constant(L, "HELP_H"));

            double[] need = { 0.0, 0.0, 0.0 };   // L, R, T
            foreach (Row row in L.Rows)
            {
                double w = Measure(font, row.Caption) * Constant(L, "RENDER_FACTOR") / scale + Constant(L, "CAPTION_PAD");
                int side = row.Side == 'L' ? 0 : row.Side == 'R' ? 1 : 2;
                need[side] = Math.Max(need[side], w);
            }
            double screenLeft = -left / scale + Constant(L, "EDGE_GAP");
            double screenRight = (width - left) / scale - Constant(L, "EDGE_GAP");
            double leftW = Math.Min(Math.Max(Constant(L, "CAPTION_W"), need[0]),
                Constant(L, "LEFT_GLYPH_X") - Constant(L, "CAPTION_GAP") - screenLeft);
            double rightW = Math.Min(Math.Max(Constant(L, "CAPTION_W"), need[1]),
                screenRight - (Constant(L, "RIGHT_GLYPH_X") + Constant(L, "GLYPH") + Constant(L, "CAPTION_GAP")));
            double topW = Math.Max(Constant(L, "TOP_CAPTION_W"), need[2]);
            double overhang = Math.Max(leftW, rightW) - Constant(L, "CAPTION_W");
            double twoLines = Math.Max(Constant(L, "LINE_BOX_H"), Constant(L, "TWO_LINES") * font.LineHeight / scale);
            foreach (Row row in L.Rows)
            {
                double y = Constant(L, "BOARD_Y") + row.RowY;
                Add(L, data, ref index, left, top, scale, row.GlyphX, y - Constant(L, "GLYPH") / 2,
                    Constant(L, "GLYPH"), Constant(L, "GLYPH"));
                if (row.Side == 'T')
                {
                    double tw = topW, tx = row.GlyphX + Constant(L, "GLYPH") / 2 - tw / 2;
                    Add(L, data, ref index, left, top, scale, tx,
                        y - Constant(L, "GLYPH") / 2 - Constant(L, "TOP_CAPTION_RISE"), tw, Constant(L, "TOP_CAPTION_H"));
                    continue;
                }
                double textW = row.Side == 'L' ? leftW : rightW;
                double textX = row.Side == 'L'
                    ? Constant(L, "LEFT_GLYPH_X") - Constant(L, "CAPTION_GAP") - textW
                    : Constant(L, "RIGHT_GLYPH_X") + Constant(L, "GLYPH") + Constant(L, "CAPTION_GAP");
                double caption = Measure(font, row.Caption) * Constant(L, "RENDER_FACTOR") / scale + Constant(L, "CAPTION_PAD");
                double textH = caption > textW ? twoLines : Constant(L, "LINE_BOX_H");
                Add(L, data, ref index, left, top, scale, textX, y - textH / 2, textW, textH);
            }

            // controller_layout_backdrop.py's placements, already rounded there and again here.
            double hairUpper = Constant(L, "HEADING_BOTTOM") - up + Constant(L, "HAIR_BELOW_HEADING");
            double hairLower = down >= Constant(L, "HAIR_OPEN_DOWN")
                ? Constant(L, "HELP_Y") + down - Constant(L, "HAIR_ABOVE_HELP")
                : Constant(L, "HAIR_COMPACT_Y");
            double designW = Constant(L, "DESIGN_W") + 2 * overhang, s = scale;
            double gap = Constant(L, "DECOR_EDGE_GAP") * s, c = Constant(L, "DECOR_CORNER") * s;
            List<double[]> decor = new List<double[]>();
            decor.Add(new[] { gap, gap, c, c });
            decor.Add(new[] { width - gap - c, gap, c, c });
            decor.Add(new[] { gap, height - gap - c, c, c });
            decor.Add(new[] { width - gap - c, height - gap - c, c, c });
            double x0 = gap + c * Constant(L, "HAIR_OVERLAP"), x1 = width - gap - c * Constant(L, "HAIR_OVERLAP");
            foreach (double hair in new[] { hairUpper, hairLower })
            {
                double cy = top + hair * s;
                decor.Add(new[] { x0, cy - Constant(L, "HAIR_H") * s / 2, x1 - x0, Constant(L, "HAIR_H") * s });
            }
            double rw = Constant(L, "READOUT_W") * s, rh = Constant(L, "READOUT_H") * s;
            double inset = gap + Constant(L, "READOUT_INSET") * s;
            decor.Add(new[] { inset, inset, rw, rh });
            decor.Add(new[] { width - inset - rw, height - inset - rh, rw, rh });
            double margin = (width / s - designW) / 2;
            double art = Math.Min(Math.Min(Constant(L, "ART_MAX_W"), margin - 2 * Constant(L, "ART_MARGIN")),
                (height / s - 2 * Constant(L, "DECOR_CORNER")) / 2);
            for (int side = 0; side < 2; side++)
            {
                if (art < Constant(L, "ART_MIN_W"))
                {
                    decor.Add(new[] { 0.0, 0.0, 0.0, 0.0 });
                    continue;
                }
                double cx = side == 0 ? margin / 2 : width / s - margin / 2;
                decor.Add(new[] { (cx - art / 2) * s, height / 2 - art * s, art * s, 2 * art * s });
            }
            foreach (double[] d in decor)
                SetExtent(L, data, ref index, Math.Round(d[0]), Math.Round(d[1]), Math.Round(d[2]), Math.Round(d[3]));

            // The B inside Back.
            double backX = Constant(L, "BACK_X"), backY = Constant(L, "BACK_Y") + down;
            double size = Constant(L, "BACK_H") - Constant(L, "BACK_GLYPH_TRIM");
            SetExtent(L, data, ref index, left + (backX + Constant(L, "BACK_GLYPH_X")) * scale,
                top + (backY + Constant(L, "BACK_GLYPH_Y")) * scale, size * scale, size * scale);
        }

        /// <summary>The helper's ADD: a control in design units, placed and scaled.</summary>
        private static void Add(Layout L, byte[] data, ref int index, double left, double top, double scale,
            double x, double y, double w, double h)
        {
            SetExtent(L, data, ref index, left + x * scale, top + y * scale, w * scale, h * scale);
        }

        // ------------------------------------------------------------ the badges
        //
        // Pillow 12's arithmetic, as build_prompt_tga reaches it: Image.resize(LANCZOS) on
        // RGBA goes through premultiplied RGBa (Convert.c's rgba2rgbA and rgbA2rgba),
        // Resample.c's two passes with precompute_coeffs and normalize_coeffs_8bpc, and
        // 64-bit sums where Pillow's are 32-bit, which never overflow here.

        private const int PrecisionBits = 32 - 8 - 2;

        private static double SincFilter(double x)
        {
            if (x == 0.0)
                return 1.0;
            x = x * Math.PI;
            return Math.Sin(x) / x;
        }

        private static double LanczosFilter(double x)
        {
            if (-3.0 <= x && x < 3.0)
                return SincFilter(x) * SincFilter(x / 3);
            return 0.0;
        }

        /// <summary>Per output pixel: the first input pixel, how many, and their
        /// fixed-point weights.</summary>
        private static int PrecomputeCoeffs(int inSize, int outSize, out int[] bounds, out long[] kk)
        {
            double scale = (double)(float)inSize / outSize, filterscale = scale;
            if (filterscale < 1.0)
                filterscale = 1.0;
            double support = 3.0 * filterscale;
            int ksize = (int)Math.Ceiling(support) * 2 + 1;
            bounds = new int[outSize * 2];
            kk = new long[outSize * ksize];
            double[] k = new double[ksize];
            for (int xx = 0; xx < outSize; xx++)
            {
                double center = 0.0 + (xx + 0.5) * scale, ww = 0.0, ss = 1.0 / filterscale;
                int xmin = (int)(center - support + 0.5);
                if (xmin < 0)
                    xmin = 0;
                int xmax = (int)(center + support + 0.5);
                if (xmax > inSize)
                    xmax = inSize;
                xmax -= xmin;
                for (int x = 0; x < xmax; x++)
                {
                    double w = LanczosFilter((x + xmin - center + 0.5) * ss);
                    k[x] = w;
                    ww += w;
                }
                for (int x = 0; x < xmax; x++)
                {
                    if (ww != 0.0)
                        k[x] /= ww;
                    kk[xx * ksize + x] = k[x] < 0 ? (int)(-0.5 + k[x] * (1 << PrecisionBits))
                                                  : (int)(0.5 + k[x] * (1 << PrecisionBits));
                }
                bounds[xx * 2] = xmin;
                bounds[xx * 2 + 1] = xmax;
            }
            return ksize;
        }

        private static byte Clip8(long value)
        {
            if (value >= (1L << PrecisionBits << 8))
                return 255;
            if (value <= 0)
                return 0;
            return (byte)(value >> PrecisionBits);
        }

        private static byte MulDiv255(uint a, uint b)
        {
            uint t = a * b + 128;
            return (byte)(((t >> 8) + t) >> 8);
        }

        private static byte Div255(uint a)
        {
            uint t = a + 128;
            return (byte)(((t >> 8) + t) >> 8);
        }

        /// <summary>Image.resize((dw, dh), LANCZOS) of a straight-alpha RGBA image.</summary>
        private static byte[] ResizeRgba(byte[] input, int w, int h, int dw, int dh)
        {
            if (dw == w && dh == h)
                return (byte[])input.Clone();   // resize() returns a copy
            byte[] pre = new byte[w * h * 4];
            for (int i = 0; i < w * h; i++)
            {
                uint a = input[i * 4 + 3];
                for (int c = 0; c < 3; c++)
                    pre[i * 4 + c] = MulDiv255(input[i * 4 + c], a);
                pre[i * 4 + 3] = (byte)a;
            }
            int[] hb, vb;
            long[] hk, vk;
            int hks = PrecomputeCoeffs(w, dw, out hb, out hk);
            int vks = PrecomputeCoeffs(h, dh, out vb, out vk);
            byte[] image = pre;
            int imageWidth = w;
            if (dw != w)
            {
                int first = vb[0], last = vb[(dh - 1) * 2] + vb[(dh - 1) * 2 + 1];
                for (int i = 0; i < dh; i++)
                    vb[i * 2] -= first;
                byte[] temp = new byte[dw * (last - first) * 4];
                long[] ss = new long[4];
                for (int yy = first; yy < last; yy++)
                    for (int xx = 0; xx < dw; xx++)
                    {
                        for (int c = 0; c < 4; c++)
                            ss[c] = 1 << (PrecisionBits - 1);
                        int xmin = hb[xx * 2], count = hb[xx * 2 + 1];
                        for (int x = 0; x < count; x++)
                            for (int c = 0; c < 4; c++)
                                ss[c] += image[(yy * imageWidth + x + xmin) * 4 + c] * hk[xx * hks + x];
                        for (int c = 0; c < 4; c++)
                            temp[((yy - first) * dw + xx) * 4 + c] = Clip8(ss[c]);
                    }
                image = temp;
                imageWidth = dw;
            }
            byte[] result = new byte[dw * dh * 4];
            if (dh != h)
            {
                long[] ss = new long[4];
                for (int yy = 0; yy < dh; yy++)
                    for (int xx = 0; xx < imageWidth; xx++)
                    {
                        for (int c = 0; c < 4; c++)
                            ss[c] = 1 << (PrecisionBits - 1);
                        int ymin = vb[yy * 2], count = vb[yy * 2 + 1];
                        for (int y = 0; y < count; y++)
                            for (int c = 0; c < 4; c++)
                                ss[c] += image[((y + ymin) * imageWidth + xx) * 4 + c] * vk[yy * vks + y];
                        for (int c = 0; c < 4; c++)
                            result[(yy * dw + xx) * 4 + c] = Clip8(ss[c]);
                    }
            }
            else
                Buffer.BlockCopy(image, 0, result, 0, dw * dh * 4);
            for (int i = 0; i < dw * dh; i++)   // RGBa back to RGBA
            {
                uint a = result[i * 4 + 3];
                if (a == 255 || a == 0)
                    continue;
                for (int c = 0; c < 3; c++)
                {
                    uint v = 255u * result[i * 4 + c] / a;
                    result[i * 4 + c] = (byte)(v > 255 ? 255 : v);
                }
            }
            return result;
        }

        /// <summary>build_prompt_tga for a control of controlWidth x controlHeight: the
        /// TGA, header and footer included.</summary>
        private byte[] DrawBadge(Glyph art, int controlWidth, int controlHeight, double label, int radiusHeight,
            byte[] backing, int inset)
        {
            int tw = textureWidth, th = textureHeight;
            double center = controlHeight * centerY;
            int sizing = radiusHeight > 0 ? radiusHeight : controlHeight;
            double r = sizing * (sizing < shortBelow ? radiusShort : radius);
            // An area too short for a badge gets a transparent texture (_empty_tga).
            bool blank = inset > 0 && controlHeight - 2 * inset < minArea;
            if (inset > 0 && !blank)
                r = Math.Min(r, (controlHeight - 2 * inset) / 2.0 - fitMargin);
            double centerX;
            if (label > 0)
            {
                double gapWidth = r * gap;
                centerX = (controlWidth - label) / 2.0 - gapWidth - r;
                centerX = Math.Max(r * edge, centerX);
            }
            else
                centerX = controlHeight * fallbackX;
            if (inset > 0)
            {
                // Designed on the whole control, then mapped onto the area the fill covers.
                centerX = Math.Max(centerX, inset + r * edge) - inset;
                center -= inset;
                controlWidth -= 2 * inset;
                controlHeight -= 2 * inset;
            }
            if (blank)
                backing = null;
            double diameter = r * 2.0, aspect = (double)art.Width / art.Height;
            double boxWidth = aspect < 1.0 ? diameter * aspect : diameter;
            double boxHeight = aspect > 1.0 ? diameter / aspect : diameter;
            int drawWidth = Math.Max(1, (int)Math.Round(boxWidth * tw / controlWidth));
            int drawHeight = Math.Max(1, (int)Math.Round(boxHeight * th / controlHeight));
            int left = (int)Math.Round((centerX - boxWidth / 2.0) * tw / controlWidth);
            int top = (int)Math.Round((center - boxHeight / 2.0) * th / controlHeight);
            byte[] glyph = ResizeRgba(art.Rgba, art.Width, art.Height, drawWidth, drawHeight);

            byte[] sheet = new byte[tw * th * 4];   // top row first, RGBA
            for (int y = 0; y < drawHeight && !blank; y++)
            {
                if (top + y < 0 || top + y >= th)
                    continue;
                for (int x = 0; x < drawWidth; x++)
                {
                    if (left + x < 0 || left + x >= tw)
                        continue;
                    int from = (y * drawWidth + x) * 4, to = ((top + y) * tw + left + x) * 4;
                    // paste(art, box, art): BLEND over nothing; on a backing, a copy.
                    for (int c = 0; c < 4; c++)
                        sheet[to + c] = backing != null ? glyph[from + c] : Div255((uint)glyph[from + c] * glyph[from + 3]);
                }
            }
            if (backing != null)   // alpha_composite(the backing, the sheet)
            {
                for (int i = 0; i < tw * th * 4; i += 4)
                {
                    if (sheet[i + 3] == 0)
                    {
                        Buffer.BlockCopy(backing, 0, sheet, i, 4);
                        continue;
                    }
                    uint sa = sheet[i + 3];
                    uint blend = (uint)backing[3] * (255 - sa);
                    uint outa255 = sa * 255 + blend;
                    uint coef1 = sa * 255 * 255 * (1 << 7) / outa255;
                    uint coef2 = 255 * (1 << 7) - coef1;
                    for (int c = 0; c < 3; c++)
                    {
                        uint t = sheet[i + c] * coef1 + backing[c] * coef2 + (0x80 << 7);
                        sheet[i + c] = (byte)((((t >> 8) + t) >> 8) >> 7);
                    }
                    uint alpha = outa255 + 0x80;
                    sheet[i + 3] = (byte)(((alpha >> 8) + alpha) >> 8);
                }
            }
            byte[] tga = new byte[18 + tw * th * 4 + footer.Length];
            tga[2] = 2;
            tga[12] = (byte)tw;
            tga[13] = (byte)(tw >> 8);
            tga[14] = (byte)th;
            tga[15] = (byte)(th >> 8);
            tga[16] = 32;
            tga[17] = 0x08;
            for (int y = 0; y < th; y++)   // bottom row first, BGRA
                for (int x = 0; x < tw; x++)
                {
                    int from = ((th - 1 - y) * tw + x) * 4, to = 18 + (y * tw + x) * 4;
                    tga[to] = sheet[from + 2];
                    tga[to + 1] = sheet[from + 1];
                    tga[to + 2] = sheet[from];
                    tga[to + 3] = sheet[from + 3];
                }
            Buffer.BlockCopy(footer, 0, tga, 18 + tw * th * 4, footer.Length);
            return tga;
        }

        /// <summary>build_menubg_texture.py's build_tga, from geometry_from_gui's boxes in
        /// the blended HUD: one alpha row, each box opaque black with a 1 px edge at the
        /// edge alpha, every row alike.</summary>
        private byte[] DrawHud(Hud hud, byte[] gui)
        {
            int origin = GetI32(gui, hud.BackdropLeft), span = GetI32(gui, hud.BackdropWidth);
            List<int[]> boxes = new List<int[]>();
            for (int k = 0; k < hud.Left.Length; k++)
            {
                int left = GetI32(gui, hud.Left[k]) - origin;
                boxes.Add(new[] { left, left + GetI32(gui, hud.ButtonWidth[k]) });
            }
            boxes.Sort(delegate(int[] x, int[] y) { return x[0] != y[0] ? x[0].CompareTo(y[0]) : x[1].CompareTo(y[1]); });
            if (span <= 0 || boxes.Count == 0 || boxes[0][0] < 0 || boxes[boxes.Count - 1][1] > span)
                throw new InvalidDataException(hud.Gui + ": its buttons fall outside LBL_MENUBG.");
            int w = hud.Width, h = hud.Height;
            double scale = (double)w / span;
            byte[] alpha = new byte[w];
            foreach (int[] box in boxes)
            {
                int start = Math.Max(0, (int)Math.Round(box[0] * scale));
                int end = Math.Min(w, (int)Math.Round(box[1] * scale));
                for (int x = start; x < end; x++)
                    alpha[x] = (byte)(x == start || x == end - 1 ? hud.EdgeAlpha : 255);
            }
            byte[] tga = new byte[18 + w * h * 4 + footer.Length];
            tga[2] = 2;
            tga[12] = (byte)w;
            tga[13] = (byte)(w >> 8);
            tga[14] = (byte)h;
            tga[15] = (byte)(h >> 8);
            tga[16] = 32;
            tga[17] = 0x08;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    tga[18 + (y * w + x) * 4 + 3] = alpha[x];
            Buffer.BlockCopy(footer, 0, tga, 18 + w * h * 4, footer.Length);
            return tga;
        }

        /// <summary>The set's manifest with each row's button size the blended one, each
        /// widened screen's widening and each fitted list's change this blend's; every
        /// other byte as it was, line ends included.</summary>
        private byte[] RewriteManifest(string manifest, int[][] sizes, int[] widened, int[] fitted)
        {
            StringBuilder output = new StringBuilder(manifest.Length + 256);
            int rows = 0;
            for (int at = 0; at < manifest.Length; )
            {
                int end = manifest.IndexOf('\n', at);
                end = end < 0 ? manifest.Length : end + 1;
                string line = manifest.Substring(at, end - at);
                at = end;
                if (line.StartsWith("prompt ", StringComparison.Ordinal))
                {
                    // "prompt", the resref, the two sizes, then the rest as it was.
                    int[] field = new int[4];
                    int found = 0;
                    for (int i = 0; i < line.Length && found < 4; i++)
                        if (line[i] == ' ')
                            field[found++] = i;
                    if (found < 4 || field[1] - field[0] - 1 >= 32)
                        throw new InvalidDataException("A prompt manifest row is malformed.");
                    string resref = line.Substring(field[0] + 1, field[1] - field[0] - 1);
                    int index = prompts.FindIndex(prompt => prompt.ResRef == resref);
                    if (index < 0)
                        throw new InvalidDataException("The blend table has no badge " + resref + ".");
                    output.Append("prompt ").Append(resref).Append(' ')
                        .Append(sizes[index][0].ToString(CultureInfo.InvariantCulture)).Append(' ')
                        .Append(sizes[index][1].ToString(CultureInfo.InvariantCulture))
                        .Append(line, field[3], line.Length - field[3]);
                    rows++;
                    continue;
                }
                if (line.StartsWith("widened ", StringComparison.Ordinal))
                {
                    int nameEnd = 8;
                    while (nameEnd < line.Length && line[nameEnd] != ' ')
                        nameEnd++;
                    int numberEnd = nameEnd + 1;
                    while (numberEnd < line.Length && line[numberEnd] >= '0' && line[numberEnd] <= '9')
                        numberEnd++;
                    string gui = line.Substring(8, nameEnd - 8);
                    int fit = fits.FindIndex(f => f.Name == gui);
                    if (fit >= 0 && nameEnd < line.Length)
                    {
                        output.Append("widened ").Append(gui).Append(' ')
                            .Append(widened[fit].ToString(CultureInfo.InvariantCulture))
                            .Append(line, Math.Min(numberEnd, line.Length), line.Length - Math.Min(numberEnd, line.Length));
                        continue;
                    }
                }
                if (line.StartsWith("fitted ", StringComparison.Ordinal))
                {
                    // "fitted", the .gui, the list's tag, the change (it may be negative).
                    int nameEnd = 7;
                    while (nameEnd < line.Length && line[nameEnd] != ' ')
                        nameEnd++;
                    int tagEnd = nameEnd + 1;
                    while (tagEnd < line.Length && line[tagEnd] != ' ')
                        tagEnd++;
                    if (tagEnd < line.Length)
                    {
                        int numberEnd = tagEnd + 1;
                        if (numberEnd < line.Length && line[numberEnd] == '-')
                            numberEnd++;
                        while (numberEnd < line.Length && line[numberEnd] >= '0' && line[numberEnd] <= '9')
                            numberEnd++;
                        string gui = line.Substring(7, nameEnd - 7);
                        string tag = line.Substring(nameEnd + 1, tagEnd - nameEnd - 1);
                        int fit = rowFits.FindIndex(f => f.Name == gui && f.Tag == tag);
                        if (fit >= 0)
                        {
                            output.Append("fitted ").Append(gui).Append(' ').Append(tag).Append(' ')
                                .Append(fitted[fit].ToString(CultureInfo.InvariantCulture))
                                .Append(line, numberEnd, line.Length - numberEnd);
                            continue;
                        }
                    }
                }
                output.Append(line);
            }
            if (rows != prompts.Count)
                throw new InvalidDataException("The manifest lists " + rows + " badges, the blend table " + prompts.Count + ".");
            string text = output.ToString();
            byte[] bytes = new byte[text.Length];
            for (int i = 0; i < text.Length; i++)
                bytes[i] = (byte)text[i];
            return bytes;
        }

        // ------------------------------------------------------------ the set's files

        /// <summary>The baked label width of `row` in a prompt manifest: "prompt &lt;row&gt;
        /// &lt;w&gt; &lt;h&gt; &lt;width&gt; ...", as the helper's sscanf reads it.</summary>
        private static bool CaptionWidth(string manifest, string row, out double width)
        {
            width = 0;
            foreach (string line in manifest.Split('\n'))
            {
                List<string> parts = Tokens(line, 5);
                int w, h;
                if (parts.Count == 5 && parts[0] == "prompt" && parts[1] == row &&
                    Int32.TryParse(parts[2], NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out w) &&
                    Int32.TryParse(parts[3], NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out h))
                {
                    int end;
                    width = ParsePrefix(parts[4], 0, out end);
                    if (end > 0)
                        return true;
                }
            }
            return false;
        }

        /// <summary>parse_font_metrics (build_controller_prompt_textures.py): glyph
        /// advances (lowerright.u - upperleft.u) * texturewidth * 100, spacingR * 100;
        /// and build_gui's line height, fontheight * 100 from the first line matching
        /// "^fontheight (\S+)". Null when the file has no metrics, as the helper fails.</summary>
        private static Font ReadFont(string txi)
        {
            Font font = new Font();
            double[] upper = new double[256], lower = new double[256];
            int uppers = 0, lowers = 0, mode = 0;   // mode: 0 none, 1 upper, 2 lower
            bool haveHeight = false;
            double textureWidth = 0.0, spacing = 0.0;
            foreach (string line in txi.Split('\n'))
            {
                if (!haveHeight && line.Length > 11 &&
                    String.Compare(line, 0, "fontheight ", 0, 11, StringComparison.OrdinalIgnoreCase) == 0 &&
                    " \t\r\n".IndexOf(line[11]) < 0)
                {
                    int unused;
                    font.LineHeight = ParsePrefix(line, 11, out unused) * 100;
                    haveHeight = true;
                }
                List<string> parts = Tokens(line, 4);
                if (parts.Count == 0)
                    continue;
                int end;
                if (String.Equals(parts[0], "texturewidth", StringComparison.OrdinalIgnoreCase) && parts.Count > 1)
                {
                    textureWidth = ParsePrefix(parts[1], 0, out end);
                    mode = 0;
                }
                else if (String.Equals(parts[0], "spacingr", StringComparison.OrdinalIgnoreCase) && parts.Count > 1)
                {
                    spacing = ParsePrefix(parts[1], 0, out end);
                    mode = 0;
                }
                else if (String.Equals(parts[0], "upperleftcoords", StringComparison.OrdinalIgnoreCase))
                    mode = 1;
                else if (String.Equals(parts[0], "lowerrightcoords", StringComparison.OrdinalIgnoreCase))
                    mode = 2;
                else if (mode != 0 && parts.Count >= 2)
                {
                    double value = ParsePrefix(parts[0], 0, out end);
                    if (end != parts[0].Length)
                    {
                        mode = 0;
                        continue;
                    }
                    if (mode == 1 && uppers < 256)
                        upper[uppers++] = value;
                    else if (mode == 2 && lowers < 256)
                        lower[lowers++] = value;
                }
            }
            if (textureWidth == 0.0 || uppers == 0 || lowers < uppers)
                return null;
            font.Count = uppers < lowers ? uppers : lowers;
            for (int i = 0; i < font.Count; i++)
                font.Advances[i] = (lower[i] - upper[i]) * textureWidth * 100.0;
            font.Spacing = spacing * 100.0;
            return font;
        }

        /// <summary>measure_label</summary>
        private static double Measure(Font font, string text)
        {
            double total = 0.0;
            for (int i = 0; i < text.Length; i++)
            {
                int code = text[i];
                if (code < font.Count)
                    total += font.Advances[code];
                if (i > 0)
                    total += font.Spacing;
            }
            return total;
        }

        /// <summary>A line split as strtok splits it, on spaces, tabs and line ends, at
        /// most `limit` pieces.</summary>
        private static List<string> Tokens(string line, int limit)
        {
            List<string> parts = new List<string>();
            foreach (string part in line.Split(new[] { ' ', '\t', '\r', '\n', '\f', '\v' },
                         StringSplitOptions.RemoveEmptyEntries))
            {
                if (parts.Count == limit)
                    break;
                parts.Add(part);
            }
            return parts;
        }

        private static readonly double[] PowersOfTen =
        {
            1e0, 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11,
            1e12, 1e13, 1e14, 1e15, 1e16, 1e17, 1e18, 1e19, 1e20, 1e21, 1e22
        };

        /// <summary>strtod on a decimal number at `start`: leading white space, a sign,
        /// digits with at most one point, an optional exponent; `end` is where it
        /// stopped, `start` when there was no number (and then 0). Rounded as strtod
        /// rounds: a number of up to 2^53 in its digits and a power of ten up to 22 is
        /// one exact operation, correctly rounded, which covers every TXI and manifest
        /// value; anything longer goes to Double.Parse, which .NET Framework does not
        /// always round correctly. Hexadecimal, infinity and NaN, which strtod also
        /// reads, are not numbers here: none of these files has them.</summary>
        internal static double ParsePrefix(string text, int start, out int end)
        {
            int i = start;
            while (i < text.Length && " \t\n\v\f\r".IndexOf(text[i]) >= 0)
                i++;
            int numberStart = i;
            bool negative = false;
            if (i < text.Length && (text[i] == '+' || text[i] == '-'))
            {
                negative = text[i] == '-';
                i++;
            }
            ulong mantissa = 0;
            int digits = 0, significant = 0, exponent = 0;
            bool exact = true;
            for (; i < text.Length && text[i] >= '0' && text[i] <= '9'; i++, digits++)
                Accumulate(text[i], ref mantissa, ref significant, ref exponent, ref exact, false);
            if (i < text.Length && text[i] == '.')
            {
                i++;
                for (; i < text.Length && text[i] >= '0' && text[i] <= '9'; i++, digits++)
                    Accumulate(text[i], ref mantissa, ref significant, ref exponent, ref exact, true);
            }
            if (digits == 0)
            {
                end = start;
                return 0.0;
            }
            if (i < text.Length && (text[i] == 'e' || text[i] == 'E'))
            {
                int j = i + 1;
                bool negativeExponent = false;
                if (j < text.Length && (text[j] == '+' || text[j] == '-'))
                {
                    negativeExponent = text[j] == '-';
                    j++;
                }
                if (j < text.Length && text[j] >= '0' && text[j] <= '9')
                {
                    int value = 0;
                    for (; j < text.Length && text[j] >= '0' && text[j] <= '9'; j++)
                        if (value < 100000)
                            value = value * 10 + (text[j] - '0');
                    exponent += negativeExponent ? -value : value;
                    i = j;
                }
            }
            end = i;
            double result;
            if (exact && mantissa <= (1UL << 53) && exponent >= -22 && exponent <= 22)
                result = exponent < 0 ? mantissa / PowersOfTen[-exponent] : mantissa * PowersOfTen[exponent];
            else
                result = Math.Abs(Double.Parse(text.Substring(numberStart, end - numberStart),
                    NumberStyles.Float, CultureInfo.InvariantCulture));
            return negative ? -result : result;
        }

        private static void Accumulate(char digit, ref ulong mantissa, ref int significant, ref int exponent,
            ref bool exact, bool afterPoint)
        {
            if (mantissa == 0 && digit == '0')
            {
                if (afterPoint)
                    exponent--;
                return;
            }
            if (significant == 19)
            {
                exact = false;
                if (!afterPoint)
                    exponent++;
                return;
            }
            mantissa = mantissa * 10 + (ulong)(digit - '0');
            significant++;
            if (afterPoint)
                exponent--;
        }

        // ------------------------------------------------------------ bytes

        private static double RoundHalfAway(double value)
        {
            double magnitude = Math.Floor(Math.Abs(value) + 0.5);
            return value < 0 ? -magnitude : magnitude;
        }

        private static int GetI32(byte[] data, uint offset)
        {
            return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16 | data[offset + 3] << 24;
        }

        private static void SetI32(byte[] data, uint offset, int value)
        {
            data[offset] = (byte)value;
            data[offset + 1] = (byte)(value >> 8);
            data[offset + 2] = (byte)(value >> 16);
            data[offset + 3] = (byte)(value >> 24);
        }

        private static void AddI32(byte[] data, uint offset, int delta)
        {
            SetI32(data, offset, GetI32(data, offset) + delta);
        }

        /// <summary>A set's text file as the helper reads it: one character per byte.</summary>
        internal static string Text(byte[] bytes)
        {
            char[] chars = new char[bytes.Length];
            for (int i = 0; i < bytes.Length; i++)
                chars[i] = (char)bytes[i];
            return new string(chars);
        }

        private static byte[] ReadAll(Stream stream)
        {
            using (MemoryStream copy = new MemoryStream())
            {
                stream.CopyTo(copy);
                return copy.ToArray();
            }
        }

        private sealed class Reader
        {
            private readonly byte[] data;
            private int position;

            internal Reader(byte[] data)
            {
                this.data = data;
            }

            private int Take(int count)
            {
                if (count < 0 || position + count > data.Length)
                    throw new InvalidDataException("The blend table is truncated.");
                position += count;
                return position - count;
            }

            internal byte[] Bytes(int count)
            {
                byte[] result = new byte[count];
                Buffer.BlockCopy(data, Take(count), result, 0, count);
                return result;
            }

            internal byte U8()
            {
                return data[Take(1)];
            }

            internal int U16()
            {
                int at = Take(2);
                return data[at] | data[at + 1] << 8;
            }

            internal uint U32()
            {
                return BitConverter.ToUInt32(data, Take(4));
            }

            internal double F64()
            {
                return BitConverter.ToDouble(data, Take(8));
            }

            internal string Ascii(int count)
            {
                byte[] b = Bytes(count);
                char[] chars = new char[b.Length];
                for (int i = 0; i < b.Length; i++)
                    chars[i] = (char)b[i];
                return new string(chars);
            }

            /// <summary>take_text: a u16 length, 0 &lt; length &lt; limit, then the bytes.</summary>
            internal string Text(int limit)
            {
                int length = U16();
                if (length == 0 || length >= limit)
                    throw new InvalidDataException("The blend table has a bad record.");
                return Ascii(length);
            }
        }
    }
}
