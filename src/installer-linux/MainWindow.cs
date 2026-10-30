using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Platform.Storage;
using Avalonia.Threading;

namespace Kmrp
{
    /// <summary>The Windows installer's look, for the Linux installer's window (issue 76).
    ///
    /// The Windows window (MainForm, UiTheme and its controls in src/patcher/KmrpPatcher.cs) is
    /// drawn by hand with GDI+ on a design grid: 1980 x 1083, the card 1300 x 597 under a
    /// 420-pixel header, uniformly scaled to the window. This draws the same grid with
    /// Avalonia, element for element, with Windows' rectangles, colours and radii, and its
    /// font sizes converted from points (x 96/72). Fonts: Selawik for Segoe UI and Barlow Semi
    /// Condensed for Bahnschrift SemiCondensed (fonts/README.md). The header's smoke is the
    /// shared LightField (src/patcher/LightField.cs); the logo and the icons are the Windows
    /// installer's own resources (Kmrp.brand, Kmrp.icon.*), embedded under the same names.
    /// The Mac installer is the same design again (macos/installer-app/main.m).</summary>
    internal static class Ui
    {
        internal static readonly Color Window = Color.FromRgb(7, 12, 21);
        internal static readonly Color Accent = Color.FromRgb(42, 198, 239);
        internal static readonly Color AccentStrong = Color.FromRgb(0, 166, 214);
        internal static readonly Color AccentDark = Color.FromRgb(0, 83, 116);
        internal static readonly Color AccentLit = Color.FromRgb(96, 178, 255);
        internal static readonly Color Border = Color.FromRgb(34, 103, 132);
        internal static readonly Color Text = Color.FromRgb(236, 243, 248);
        internal static readonly Color TextMuted = Color.FromRgb(177, 195, 208);
        internal static readonly Color TextFaint = Color.FromRgb(122, 138, 154);
        internal static readonly Color Success = Color.FromRgb(126, 224, 171);
        internal static readonly Color Warning = Color.FromRgb(255, 207, 112);
        internal static readonly Color Error = Color.FromRgb(255, 142, 142);
        internal static readonly Color Disabled = Color.FromRgb(47, 56, 67);
        internal static readonly Color DisabledText = Color.FromRgb(139, 151, 164);
        internal static readonly Color Card = Color.FromRgb(13, 21, 34);
        internal static readonly Color CardHover = Color.FromRgb(19, 30, 47);
        internal static readonly Color CardEdge = Color.FromRgb(31, 46, 69);
        internal static readonly Color Hairline = Color.FromRgb(23, 34, 52);
        internal static readonly Color Badge = Color.FromRgb(18, 28, 44);
        internal static readonly Color BadgeEdge = Color.FromRgb(30, 45, 68);
        internal static readonly Color AuthorInk = Color.FromRgb(146, 170, 200);
        internal static readonly Color GlyphInk = Color.FromRgb(92, 165, 250);

        internal static readonly FontFamily Body = new FontFamily("avares://kmrp-installer/fonts#Selawik");
        internal static readonly FontFamily Display = new FontFamily("avares://kmrp-installer/fonts#Barlow Semi Condensed");

        /// <summary>Windows sizes its fonts in points; this grid is in pixels at 96 dpi.</summary>
        internal static double Pt(double points) { return points * 96.0 / 72.0; }

        internal static IBrush Brush(Color c) { return new SolidColorBrush(c); }

        internal static FormattedText Text_(string text, FontFamily family, FontWeight weight, double points, Color color)
        {
            return new FormattedText(text ?? "", CultureInfo.InvariantCulture, FlowDirection.LeftToRight,
                new Typeface(family, FontStyle.Normal, weight), Pt(points), Brush(color));
        }

        private static readonly Dictionary<string, Bitmap> art = new Dictionary<string, Bitmap>();

        /// <summary>An embedded image of the Windows installer's (Kmrp.brand, Kmrp.icon.NAME), or null.</summary>
        internal static Bitmap Resource(string name)
        {
            Bitmap found;
            if (art.TryGetValue(name, out found))
                return found;
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
                    found = stream == null ? null : new Bitmap(stream);
            }
            catch { found = null; }
            art[name] = found;
            return found;
        }

        private static readonly Dictionary<string, Rect> inks = new Dictionary<string, Rect>();

        /// <summary>The smallest rectangle of the image holding every pixel that is not
        /// effectively transparent, as UiTheme.InkBoundsOf measures it.</summary>
        internal static Rect InkBounds(string name, Bitmap image)
        {
            Rect bounds;
            if (inks.TryGetValue(name, out bounds))
                return bounds;
            int w = image.PixelSize.Width, h = image.PixelSize.Height;
            bounds = new Rect(0, 0, w, h);
            try
            {
                byte[] px = new byte[w * h * 4];
                GCHandle pin = GCHandle.Alloc(px, GCHandleType.Pinned);
                try { image.CopyPixels(new PixelRect(0, 0, w, h), pin.AddrOfPinnedObject(), px.Length, w * 4); }
                finally { pin.Free(); }
                int minX = w, minY = h, maxX = -1, maxY = -1;
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                        if (px[(y * w + x) * 4 + 3] > 8)
                        {
                            if (x < minX) minX = x;
                            if (x > maxX) maxX = x;
                            if (y < minY) minY = y;
                            if (y > maxY) maxY = y;
                        }
                if (maxX >= minX && maxY >= minY)
                    bounds = new Rect(minX, minY, maxX - minX + 1, maxY - minY + 1);
            }
            catch { }
            inks[name] = bounds;
            return bounds;
        }

        /// <summary>An icon as a silhouette of COLOR in BOX: the art's alpha keeps the shape, the
        /// colour is ours (UiTheme.DrawIconArt, DrawStatusArt and DrawIconMask; the art is white
        /// line work but for the gear, which is black). CROP fits only the ink, as DrawIconMask.</summary>
        internal static void Icon(DrawingContext dc, string name, Rect box, Color color, bool crop)
        {
            Bitmap image = Resource("Kmrp.icon." + name);
            if (image == null || box.Width <= 0 || box.Height <= 0)
                return;
            Rect target = box;
            ImageBrush mask = new ImageBrush(image) { Stretch = Stretch.Fill };
            if (crop)
            {
                Rect ink = InkBounds(name, image);
                double scale = Math.Min(box.Width / ink.Width, box.Height / ink.Height);
                double dw = Math.Max(1, Math.Round(ink.Width * scale)), dh = Math.Max(1, Math.Round(ink.Height * scale));
                target = new Rect(box.X + Math.Floor((box.Width - dw) / 2), box.Y + Math.Floor((box.Height - dh) / 2), dw, dh);
                mask.SourceRect = new RelativeRect(ink, RelativeUnit.Absolute);
            }
            using (dc.PushOpacityMask(mask, target))
                dc.FillRectangle(Brush(color), target);
        }

        internal static void OpenOutside(string target)
        {
            try { Process.Start(new ProcessStartInfo("xdg-open", "\"" + target + "\"") { UseShellExecute = false }); }
            catch { }
        }
    }

    /// <summary>The header: LightField's smoke and motes, the brand lockup and the tagline
    /// (MainForm.PaintBrandLayer). The plume steps at 60 ms, as on Windows (AnimationIntervalMs).</summary>
    internal sealed class HeaderView : Control
    {
        private const double BrandWidth = 650, BrandHeight = 350;   // MainForm: half the card's width
        private const double WordmarkInkLeft = 0.0216, WordmarkInkRight = 0.9774;
        private const string Tagline = "M O D E R N .   R E S T O R E D .   S I M P L E .";
        private readonly LightField light = new LightField();
        private readonly DispatcherTimer timer;
        private readonly Stopwatch clock = Stopwatch.StartNew();
        private WriteableBitmap smoke;
        private WriteableBitmap[] motes;
        private double taglineSize;

        internal HeaderView()
        {
            RenderOptions.SetBitmapInterpolationMode(this, BitmapInterpolationMode.HighQuality);
            timer = new DispatcherTimer(TimeSpan.FromMilliseconds(60), DispatcherPriority.Render, delegate
            {
                double seconds = clock.Elapsed.TotalSeconds;
                clock.Restart();
                light.Step((float)Math.Min(0.25, seconds));
                InvalidateVisual();
            });
            timer.Start();
        }

        public override void Render(DrawingContext dc)
        {
            double w = Bounds.Width, h = Bounds.Height;
            if (light.Compute((int)w, (int)h))
            {
                int bw = light.BufferWidth, bh = light.BufferHeight;
                if (smoke == null || smoke.PixelSize.Width != bw || smoke.PixelSize.Height != bh)
                    smoke = new WriteableBitmap(new PixelSize(bw, bh), new Vector(96, 96), PixelFormat.Bgra8888, AlphaFormat.Unpremul);
                using (ILockedFramebuffer frame = smoke.Lock())
                    for (int y = 0; y < bh; y++)
                        Marshal.Copy(light.Pixels, y * bw * 4, frame.Address + y * frame.RowBytes, bw * 4);
                int rows = Math.Min(bh, light.FilledRows);
                if (rows > 0)
                {
                    double destHeight = Math.Min(h, Math.Ceiling(rows * h / bh));
                    dc.DrawImage(smoke, new Rect(0, 0, bw, rows), new Rect(0, 0, w, destHeight));
                }
                DrawMotes(dc, w, h);
            }

            Bitmap brand = Ui.Resource("Kmrp.brand");
            double brandTop = 14, taglineTop = 30;
            if (brand != null)
            {
                dc.DrawImage(brand, new Rect(0, 0, brand.PixelSize.Width, brand.PixelSize.Height),
                    new Rect(Math.Floor((w - BrandWidth) / 2), brandTop, BrandWidth, BrandHeight));
                taglineTop = brandTop + BrandHeight + 2;
            }
            // The tagline is as wide as the wordmark's ink, measured, as on Windows.
            if (taglineSize <= 0)
            {
                FormattedText probe = Ui.Text_(Tagline, Ui.Body, FontWeight.Bold, 20, Ui.Accent);
                double target = (WordmarkInkRight - WordmarkInkLeft) * BrandWidth;
                taglineSize = probe.Width > 1 ? 20 * target / probe.Width : 10.5;
            }
            FormattedText line = Ui.Text_(Tagline, Ui.Body, FontWeight.Bold, taglineSize, Ui.Accent);
            dc.DrawText(line, new Point(Math.Round((w - line.Width) / 2), taglineTop));
        }

        private void DrawMotes(DrawingContext dc, double w, double h)
        {
            if (motes == null)
            {
                motes = new WriteableBitmap[LightField.MoteLevelCount];
                for (int i = 0; i < motes.Length; i++)
                {
                    byte[] px = LightField.MotePixels(48, (i + 1) / (float)LightField.MoteLevelCount);
                    motes[i] = new WriteableBitmap(new PixelSize(48, 48), new Vector(96, 96), PixelFormat.Bgra8888, AlphaFormat.Unpremul);
                    using (ILockedFramebuffer frame = motes[i].Lock())
                        for (int y = 0; y < 48; y++)
                            Marshal.Copy(px, y * 48 * 4, frame.Address + y * frame.RowBytes, 48 * 4);
                }
            }
            for (int i = 0; i < LightField.MoteCountTotal; i++)
            {
                float u, v, radiusOfHeight;
                int level;
                if (!light.MoteAt(i, out u, out v, out radiusOfHeight, out level))
                    continue;
                double radius = radiusOfHeight * h, size = Math.Max(2, (int)(radius * 2));
                dc.DrawImage(motes[level], new Rect(0, 0, 48, 48),
                    new Rect((int)(u * w - radius), (int)(v * h - radius), size, size));
            }
        }
    }

    /// <summary>A numbered step (StepRow): the lit badge, the title and the line under it.</summary>
    internal sealed class StepView : Control
    {
        internal string Title = "", Subtitle = "", IconName = "folder";
        internal bool Dimmed, Separator = true;

        internal void Set(string title, string subtitle)
        {
            if (title != null) Title = title;
            if (subtitle != null) Subtitle = subtitle;
            InvalidateVisual();
        }

        public override void Render(DrawingContext dc)
        {
            double w = Bounds.Width, h = Bounds.Height;
            if (Separator)
                dc.DrawLine(new Pen(Ui.Brush(Ui.Hairline), 1), new Point(26, h - 0.5), new Point(w - 26, h - 0.5));
            Rect circle = new Rect(28, (96 - 64) / 2, 64, 64);
            dc.DrawEllipse(Ui.Brush(Ui.Badge), new Pen(Ui.Brush(Ui.BadgeEdge), 1), circle.Center, 32, 32);
            double side = Math.Round(64 * 0.563);
            Ui.Icon(dc, IconName, new Rect(circle.X + Math.Floor((64 - side) / 2), circle.Y + Math.Floor((64 - side) / 2), side, side),
                Dimmed ? Ui.TextFaint : Ui.GlyphInk, false);
            dc.DrawText(Ui.Text_(Title, Ui.Display, FontWeight.Bold, 22, Dimmed ? Ui.TextFaint : Ui.Text), new Point(120, 48 - 30));
            FormattedText sub = Ui.Text_(Subtitle, Ui.Body, FontWeight.Normal, 16.5, Dimmed ? Ui.TextFaint : Ui.TextMuted);
            sub.MaxTextWidth = Math.Max(1, w - 120 - 24);
            sub.MaxLineCount = 1;
            sub.Trimming = TextTrimming.CharacterEllipsis;
            dc.DrawText(sub, new Point(120, 48 + 4));
        }
    }

    /// <summary>A step's state on the right (StateLabel), with the verified or missing badge.</summary>
    internal sealed class StateView : Control
    {
        internal string Text = "";
        internal Color Ink = Ui.TextMuted;
        internal int Badge;   // 0 none, 1 verified, 2 missing

        internal void Set(string text, Color ink, int badge)
        {
            Text = text ?? "";
            Ink = ink;
            Badge = badge;
            InvalidateVisual();
        }

        public override void Render(DrawingContext dc)
        {
            double w = Bounds.Width, h = Bounds.Height;
            FormattedText text = Ui.Text_(Text, Ui.Display, FontWeight.Bold, 18, Ink);
            double textWidth = Math.Min(w, text.Width);
            if (Badge != 0)
            {
                bool iconOnly = Text.Length == 0;
                double icon = iconOnly ? 48 : 32, gap = iconOnly ? 0 : 8;
                double left = Math.Max(0, w - Math.Min(w, icon + gap + (iconOnly ? 0 : textWidth)));
                Ui.Icon(dc, Badge == 1 ? "verified" : "missing", new Rect(left, Math.Floor((h - icon) / 2), icon, icon), Ink, false);
                if (!iconOnly)
                    dc.DrawText(text, new Point(left + icon + gap, (h - text.Height) / 2));
                return;
            }
            dc.DrawText(text, new Point(w - textWidth, (h - text.Height) / 2));
        }
    }

    /// <summary>The flat pill button (PillButton): Primary lit, Subtle muted, an icon, or
    /// progress filling it.</summary>
    internal sealed class PillView : Control
    {
        internal string Text = "", IconName;
        internal bool Primary, Subtle;
        internal double TextPoints;
        internal int Progress = -1;
        internal event Action Click;
        private bool hover, down;

        internal PillView() { Cursor = new Cursor(StandardCursorType.Hand); }

        internal void SetText(string text) { Text = text; InvalidateVisual(); }

        protected override void OnPointerEntered(PointerEventArgs e) { hover = true; InvalidateVisual(); base.OnPointerEntered(e); }
        protected override void OnPointerExited(PointerEventArgs e) { hover = down = false; InvalidateVisual(); base.OnPointerExited(e); }
        protected override void OnPointerPressed(PointerPressedEventArgs e) { down = true; InvalidateVisual(); base.OnPointerPressed(e); }
        protected override void OnPointerReleased(PointerReleasedEventArgs e)
        {
            bool clicked = down && hover && IsEffectivelyEnabled;
            down = false;
            InvalidateVisual();
            base.OnPointerReleased(e);
            if (clicked && Click != null)
                Click();
        }
        protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
        {
            base.OnPropertyChanged(change);
            if (change.Property == IsEnabledProperty)
                InvalidateVisual();
        }

        public override void Render(DrawingContext dc)
        {
            Rect r = new Rect(0.5, 0.5, Bounds.Width - 1, Bounds.Height - 1);
            RoundedRect shape = new RoundedRect(r, 8);
            bool progress = Progress >= 0;
            if (progress)
            {
                dc.DrawRectangle(Gradient(Ui.AccentDark, Color.FromRgb(0, 112, 151)), null, shape);
                double filled = Math.Round(Bounds.Width * Progress / 100.0);
                if (filled > 0)
                    using (dc.PushClip(shape))
                    {
                        dc.FillRectangle(Gradient(Color.FromRgb(116, 171, 193), Color.FromRgb(59, 132, 162)), new Rect(0, 0, filled, Bounds.Height));
                        dc.FillRectangle(Gradient(Color.FromArgb(34, 255, 255, 255), Color.FromArgb(0, 255, 255, 255)),
                            new Rect(0, 0, filled, Math.Round(Bounds.Height * 0.48)));
                        if (filled < Bounds.Width)
                            dc.DrawLine(new Pen(Ui.Brush(Color.FromArgb(145, 170, 205, 220)), 1.4), new Point(filled, 6), new Point(filled, Bounds.Height - 6));
                    }
                dc.DrawRectangle(null, new Pen(Ui.Brush(Color.FromArgb(105, 119, 177, 202)), 1), shape);
            }
            else if (!IsEffectivelyEnabled)
                dc.DrawRectangle(Ui.Brush(Ui.Disabled), null, shape);
            else if (Primary)
                dc.DrawRectangle(Gradient(down ? Ui.AccentDark : hover ? Ui.AccentLit : Ui.Accent, down ? Ui.AccentDark : Ui.AccentStrong), null, shape);
            else
                dc.DrawRectangle(Ui.Brush(hover ? Ui.CardHover : Ui.Card),
                    new Pen(Ui.Brush(hover ? Ui.Accent : Subtle ? Ui.Border : Ui.CardEdge), 1), shape);

            Color ink = progress ? Colors.White : !IsEffectivelyEnabled ? Ui.DisabledText
                : Primary ? Colors.White : (Subtle && !hover ? Ui.TextMuted : Ui.Text);
            if (!string.IsNullOrEmpty(IconName))
            {
                double side = Math.Round(Math.Min(Bounds.Width, Bounds.Height) * 0.74);
                Ui.Icon(dc, IconName, new Rect(Math.Floor((Bounds.Width - side) / 2), Math.Floor((Bounds.Height - side) / 2), side, side), ink, true);
                return;
            }
            double points = TextPoints > 0 ? TextPoints : (Primary ? 18 : 15.5);
            if (progress)
            {
                FormattedText shadow = Ui.Text_(Text, Ui.Display, FontWeight.Bold, points, Color.FromArgb(115, 0, 39, 58));
                dc.DrawText(shadow, new Point((Bounds.Width - shadow.Width) / 2, (Bounds.Height - shadow.Height) / 2 + 1));
            }
            FormattedText label = Ui.Text_(Text, Ui.Display, FontWeight.Bold, points, ink);
            dc.DrawText(label, new Point((Bounds.Width - label.Width) / 2, (Bounds.Height - label.Height) / 2));
        }

        private static IBrush Gradient(Color top, Color bottom)
        {
            return new LinearGradientBrush
            {
                StartPoint = new RelativePoint(0, 0, RelativeUnit.Relative),
                EndPoint = new RelativePoint(0, 1, RelativeUnit.Relative),
                GradientStops = { new GradientStop(top, 0), new GradientStop(bottom, 1) },
            };
        }
    }

    /// <summary>A footer line (MainForm's logLink and credit): PREFIX in faint ink, then LINK,
    /// underlined while the pointer is on it; RIGHT aligns it to the right edge.</summary>
    internal sealed class LinkView : Control
    {
        internal string Prefix = "", Link = "";
        internal Color Ink = Ui.Accent;
        internal bool Right;
        internal event Action Click;
        private bool hover;

        internal LinkView() { Cursor = new Cursor(StandardCursorType.Hand); }

        protected override void OnPointerEntered(PointerEventArgs e) { hover = true; InvalidateVisual(); base.OnPointerEntered(e); }
        protected override void OnPointerExited(PointerEventArgs e) { hover = false; InvalidateVisual(); base.OnPointerExited(e); }
        protected override void OnPointerReleased(PointerReleasedEventArgs e)
        {
            base.OnPointerReleased(e);
            if (hover && IsEffectivelyEnabled && Click != null)
                Click();
        }

        public override void Render(DrawingContext dc)
        {
            FormattedText prefix = Ui.Text_(Prefix, Ui.Body, FontWeight.SemiBold, 15.5, Ui.TextFaint);
            FormattedText link = Ui.Text_(Link, Ui.Body, FontWeight.SemiBold, 15.5, IsEffectivelyEnabled ? Ink : Ui.TextFaint);
            if (hover && IsEffectivelyEnabled)
                link.SetTextDecorations(TextDecorations.Underline);
            double width = prefix.WidthIncludingTrailingWhitespace + link.Width;
            double x = Right ? Bounds.Width - width : 0, y = (Bounds.Height - link.Height) / 2;
            dc.DrawText(prefix, new Point(x, y));
            dc.DrawText(link, new Point(x + prefix.WidthIncludingTrailingWhitespace, y));
        }
    }

    /// <summary>An Advanced Settings tile (OptionToggle): title, note, description, author and
    /// the switch.</summary>
    internal sealed class ToggleView : Control
    {
        internal string Title = "", Detail = "", Author = "", Note = "";
        internal Color NoteInk = Ui.Success;
        internal event Action<bool> Changed;
        private bool isChecked = true, hover;

        internal ToggleView() { Cursor = new Cursor(StandardCursorType.Hand); }

        internal bool Checked
        {
            get { return isChecked; }
            set
            {
                if (isChecked == value)
                    return;
                isChecked = value;
                InvalidateVisual();
                if (Changed != null)
                    Changed(value);
            }
        }

        protected override void OnPointerEntered(PointerEventArgs e) { hover = true; InvalidateVisual(); base.OnPointerEntered(e); }
        protected override void OnPointerExited(PointerEventArgs e) { hover = false; InvalidateVisual(); base.OnPointerExited(e); }
        protected override void OnPointerReleased(PointerReleasedEventArgs e)
        {
            base.OnPointerReleased(e);
            if (IsEffectivelyEnabled && hover)
                Checked = !Checked;
        }

        public override void Render(DrawingContext dc)
        {
            double w = Bounds.Width, h = Bounds.Height;
            RoundedRect body = new RoundedRect(new Rect(0.5, 0.5, w - 1, h - 1), 10);
            dc.DrawRectangle(Ui.Brush(hover ? Ui.CardHover : Ui.Badge), new Pen(Ui.Brush(hover ? Ui.Border : Ui.CardEdge), 1), body);

            const double pad = 16, switchWidth = 64, switchHeight = 32;
            double textWidth = Math.Max(1, w - 2 * pad), switchLeft = w - pad - switchWidth;
            Rect track = new Rect(switchLeft, h - pad - switchHeight, switchWidth, switchHeight);
            double titleTop = pad * 0.75, titleWidth = textWidth;
            if (!string.IsNullOrEmpty(Note))
            {
                FormattedText note = Ui.Text_(Note, Ui.Body, FontWeight.Normal, 13, NoteInk);
                FormattedText lineProbe = Ui.Text_("Ag", Ui.Body, FontWeight.SemiBold, 16, Ui.Text);
                dc.DrawText(note, new Point(pad + textWidth - note.Width, titleTop + (lineProbe.Height - note.Height) / 2));
                titleWidth = Math.Max(1, textWidth - note.Width - 8);
            }
            FormattedText title = Ui.Text_(Title, Ui.Body, FontWeight.SemiBold, 16, Ui.Text);
            title.MaxTextWidth = titleWidth;
            title.MaxLineCount = 2;
            title.Trimming = TextTrimming.WordEllipsis;
            dc.DrawText(title, new Point(pad, titleTop));
            double detailTop = titleTop + title.Height + 3;
            FormattedText detail = Ui.Text_(Detail, Ui.Body, FontWeight.Normal, 13, Ui.TextMuted);
            FormattedText detailLine = Ui.Text_("Ag", Ui.Body, FontWeight.Normal, 13, Ui.TextMuted);
            detail.MaxTextWidth = textWidth;
            detail.MaxLineCount = Math.Max(1, (int)Math.Floor((track.Top - 4 - detailTop) / detailLine.Height));
            detail.Trimming = TextTrimming.WordEllipsis;
            dc.DrawText(detail, new Point(pad, detailTop));
            if (!string.IsNullOrEmpty(Author))
            {
                FormattedText author = Ui.Text_("by " + Author, Ui.Body, FontWeight.Normal, 13, Ui.AuthorInk);
                author.MaxTextWidth = Math.Max(1, switchLeft - pad - 8);
                author.MaxLineCount = 1;
                author.Trimming = TextTrimming.CharacterEllipsis;
                dc.DrawText(author, new Point(pad, track.Y + (switchHeight - author.Height) / 2));
            }
            bool lit = isChecked && IsEffectivelyEnabled;
            dc.DrawRectangle(Ui.Brush(lit ? Ui.AccentStrong : Ui.Disabled), new Pen(Ui.Brush(lit ? Ui.Accent : Ui.CardEdge), 1),
                new RoundedRect(track, switchHeight / 2));
            double knob = switchHeight - 8;
            double knobX = isChecked ? track.Right - knob - (switchHeight - knob) / 2 : track.Left + (switchHeight - knob) / 2;
            dc.DrawEllipse(Ui.Brush(!IsEffectivelyEnabled ? Ui.TextFaint : isChecked ? Colors.White : Ui.TextMuted), null,
                new Point(knobX + knob / 2, track.Y + switchHeight / 2), knob / 2, knob / 2);
        }
    }

    /// <summary>The Linux installer's window: the Windows installer's, on the same design grid,
    /// over the same core (PatchOperations, KpmEditionOperations).</summary>
    internal sealed class MainWindow : Window
    {
        private const double DesignWidth = 1980, DesignHeight = 1083;
        private const double CardLeft = 340, CardTop = 420, CardWidth = 1300, CardHeight = 597;
        private const double ActionLeft = 80, ActionTop = 481, ActionWidth = 1052, ActionHeight = 76, ActionGap = 12;
        private const int StepLineLimit = 80;
        private const string CreatorUrl = "https://deadlystream.com/profile/68365-raymangt/";

        private readonly Canvas design = new Canvas { Width = DesignWidth, Height = DesignHeight };
        // The card (CardPanel): radius 14, Card fill, CardEdge.
        private readonly Canvas card = new Canvas();
        private readonly Canvas mainView = new Canvas(), settingsView = new Canvas();
        private readonly StepView stepFolder, stepVerify, stepResolution, stepApply;
        private readonly StateView verifyState = new StateView(), resolutionState = new StateView(), applyState = new StateView();
        private readonly PillView browse, action, upgrade, settings;
        private readonly TextBlock timeLeft;
        private readonly LinkView logLink;
        private string folder = "";
        private bool actionIsRestore, running, upgradeOffered;
        private string lastDetail = "";

        internal MainWindow()
        {
            Title = "KMRP – " + "KOTOR Modern Restoration Patch";
            Width = 1300;
            Height = Math.Round(1300 * DesignHeight / DesignWidth);
            MinWidth = 640;
            MinHeight = 350;
            Background = Ui.Brush(Ui.Window);
            Content = new Viewbox { Stretch = Stretch.Uniform, Child = design };

            Place(design, new HeaderView(), 0, 0, DesignWidth, CardTop);
            Border cardFrame = new Border
            {
                Background = Ui.Brush(Ui.Card), BorderBrush = Ui.Brush(Ui.CardEdge), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(14), Child = card, ClipToBounds = true,
            };
            Place(design, cardFrame, CardLeft, CardTop, CardWidth, CardHeight);
            Place(card, mainView, 0, 0, CardWidth, CardHeight);
            Place(card, settingsView, 0, 0, CardWidth, CardHeight);
            settingsView.IsVisible = false;

            stepFolder = Step(0, "folder", "1. Select Game Folder", "Choose your Knights of the Old Republic folder.");
            browse = new PillView { Text = "Browse", TextPoints = 18 };
            browse.Click += async delegate { await Browse(); };
            Place(mainView, browse, CardWidth - 168, 24, 132, 48);
            stepVerify = Step(1, "shield", "2. Detect Game Version", "Looking for swkotor.exe.");
            Place(mainView, verifyState, CardWidth - 340, 96 + 20, 300, 56);
            stepResolution = Step(2, "monitor", "3. Resolutions", Summary());
            Place(mainView, resolutionState, CardWidth - 340, 2 * 96 + 20, 300, 56);
            stepApply = Step(3, "tools", "4. Apply Patch", "Patches will be applied to make KOTOR modern-ready.");
            stepApply.Separator = false;
            Place(mainView, applyState, CardWidth - 340, 3 * 96 + 20, 300, 56);

            action = new PillView { Primary = true, Text = "Start Patching" };
            action.Click += delegate { if (actionIsRestore) Run("Restore"); else Run("Patch"); };
            Place(mainView, action, ActionLeft, ActionTop, ActionWidth, ActionHeight);
            upgrade = new PillView { Primary = true, Text = "Upgrade", IsVisible = false };
            upgrade.Click += delegate { Run("Upgrade"); };
            Place(mainView, upgrade, ActionLeft, ActionTop, ActionWidth, ActionHeight);
            settings = new PillView { Subtle = true, IconName = "Settings" };
            ToolTip.SetTip(settings, "Advanced Settings");
            settings.Click += delegate { ShowSettings(true); };
            Place(mainView, settings, ActionLeft + ActionWidth + ActionGap, ActionTop, ActionHeight, ActionHeight);
            timeLeft = new TextBlock
            {
                FontFamily = Ui.Body, FontSize = Ui.Pt(13), Foreground = Ui.Brush(Ui.TextMuted),
                TextAlignment = TextAlignment.Right, IsVisible = false,
            };
            Place(mainView, timeLeft, ActionLeft, ActionTop + ActionHeight + 4, ActionWidth, 32);

            BuildSettings();

            // The footer: the version and Open Log on the left, the credit on the right.
            logLink = new LinkView { Prefix = "v" + GoldPatch.PatchVersion + "   ·   ", Link = "Open Log", Ink = Ui.Accent };
            logLink.Click += OpenLog;
            Place(design, logLink, CardLeft + 8, CardTop + CardHeight + 14, 260, 34);
            LinkView credit = new LinkView { Link = "Created by RaymanGT", Ink = Ui.TextFaint, Right = true };
            credit.Click += delegate { Ui.OpenOutside(CreatorUrl); };
            Place(design, credit, CardLeft + CardWidth - 268, CardTop + CardHeight + 14, 260, 34);

            List<string> found = SteamLibraries.KotorFolders(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile));
            folder = found.Count > 0 ? found[0] : "";
            Activated += delegate { Refresh(); };
            Opened += delegate { FitInitialSize(); };
            Refresh();
        }

        private static void Place(Panel parent, Control child, double x, double y, double w, double h)
        {
            Canvas.SetLeft(child, x);
            Canvas.SetTop(child, y);
            child.Width = w;
            child.Height = h;
            parent.Children.Add(child);
        }

        private StepView Step(int index, string icon, string title, string subtitle)
        {
            StepView row = new StepView { IconName = icon, Title = title, Subtitle = subtitle };
            Place(mainView, row, 0, index * 96, CardWidth, 96);
            return row;
        }

        private void BuildSettings()
        {
            TextBlock title = new TextBlock
            {
                Text = "Advanced Settings", FontFamily = Ui.Body, FontWeight = FontWeight.SemiBold, FontSize = Ui.Pt(24),
                Foreground = Ui.Brush(Ui.Text), VerticalAlignment = VerticalAlignment.Center,
            };
            Place(settingsView, title, 36, 16, 340, 44);
            TextBlock subtitle = new TextBlock
            {
                Text = "Each can be changed on its own. Restore Defaults puts them back.", FontFamily = Ui.Body,
                FontSize = Ui.Pt(14), Foreground = Ui.Brush(Ui.TextMuted), TextAlignment = TextAlignment.Right,
                VerticalAlignment = VerticalAlignment.Center,
            };
            Place(settingsView, subtitle, 376, 20, CardWidth - 36 - 376, 40);

            const double gap = 10, rowTop = 70;
            double tileWidth = Math.Floor((CardWidth - 72 - 2 * gap) / 3);
            double viewHeight = CardHeight - 96 - 8 - rowTop;
            double tileHeight = Math.Floor((viewHeight - gap) / 2);
            Canvas tiles = new Canvas { Width = CardWidth - 72, Height = 3 * tileHeight + 2 * gap };
            ScrollViewer scroll = new ScrollViewer
            {
                Content = tiles, HorizontalScrollBarVisibility = Avalonia.Controls.Primitives.ScrollBarVisibility.Disabled,
                VerticalScrollBarVisibility = Avalonia.Controls.Primitives.ScrollBarVisibility.Auto,
            };
            Place(settingsView, scroll, 36, rowTop, CardWidth - 36 - 6, viewHeight);

            ToggleView controller = Tile(tiles, 0, 0, tileWidth, tileHeight, "Native Controller Support", "RaymanGT",
                "Xbox, PlayStation, Switch and Steam Deck pads: prompts, rumble and the Xbox-style HUD.",
                KmrpSettings.ControllerSupport, v => KmrpSettings.ControllerSupport = v);
            // K1 Modern Driver Compatibility is installed by the Windows installer only: under
            // Proton it is untested (issue 44), and this installer does not install it.
            ToggleView driver = Tile(tiles, 1, 0, tileWidth, tileHeight, "Modern Driver Compatibility", "Synchro",
                "Fixes lighting, fog, reflections, soft shadows and grass on modern graphics cards.", false, null);
            driver.IsEnabled = false;
            driver.Note = "Windows only";
            driver.NoteInk = Ui.Warning;
            ToggleView marker = Tile(tiles, 2, 0, tileWidth, tileHeight, "Area Map Marker Fixes", "Derslok",
                "Corrects misplaced area-map marker positions across the game.", KmrpSettings.MarkerFixes, v => KmrpSettings.MarkerFixes = v);
            ToggleView icons = Tile(tiles, 0, 1, tileWidth, tileHeight, "HD Item Icons", "JackInTheBox",
                "High-resolution item icons. Turn off to keep the game's own icons.", KmrpSettings.HdIcons, v => KmrpSettings.HdIcons = v);
            ToggleView fps = Tile(tiles, 1, 1, tileWidth, tileHeight, "High FPS Fix", "D3M0",
                "Fixes timing and animation faults above 60 frames per second." +
                (KmrpSettings.HighFpsFixAuto ? " On by default for this display." : " Off by default on a 60 Hz display."),
                KmrpSettings.HighFpsFix, v => KmrpSettings.HighFpsFix = v);
            if (KmrpSettings.HighFpsFixAuto)
                fps.Note = "Display supports " + KmrpSettings.DisplayRefresh.ToString(CultureInfo.InvariantCulture) + " Hz";
            ToggleView empty = Tile(tiles, 2, 1, tileWidth, tileHeight, "Marked Empty Containers", "ShaeMyName",
                "Adds \"(empty)\" to the name of a container or body with nothing left in it.",
                KmrpSettings.MarkedEmptyContainers, v => KmrpSettings.MarkedEmptyContainers = v);
            ToggleView debug = Tile(tiles, 0, 2, tileWidth, tileHeight, "Debug Logs", "KMRP",
                "Writes diagnostic log files beside the game. Turn on when reporting a problem.",
                KmrpSettings.DebugLogs, v => KmrpSettings.DebugLogs = v);

            double buttonWidth = Math.Floor((CardWidth - 160 - 12) / 2);
            PillView defaults = new PillView { Subtle = true, Text = "Restore Defaults" };
            defaults.Click += delegate
            {
                marker.Checked = true;
                icons.Checked = true;
                empty.Checked = true;
                controller.Checked = true;
                fps.Checked = KmrpSettings.HighFpsFixAuto;
                KmrpSettings.ResetHighFpsFix();
                debug.Checked = false;
            };
            Place(settingsView, defaults, 80, CardHeight - 96, buttonWidth, 60);
            PillView back = new PillView { Text = "Back" };
            back.Click += delegate { ShowSettings(false); };
            Place(settingsView, back, 80 + buttonWidth + 12, CardHeight - 96, buttonWidth, 60);
        }

        private static ToggleView Tile(Canvas tiles, int column, int row, double width, double height, string title,
            string author, string detail, bool on, Action<bool> save)
        {
            ToggleView tile = new ToggleView { Title = title, Author = author, Detail = detail };
            tile.Checked = on;
            if (save != null)
                tile.Changed += save;
            Place(tiles, tile, column * (width + 10), row * (height + 10), width, height);
            return tile;
        }

        private void ShowSettings(bool show)
        {
            mainView.IsVisible = !show;
            settingsView.IsVisible = show;
        }

        private string Executable()
        {
            return folder.Length > 0 ? Path.Combine(folder, "swkotor.exe") : "";
        }

        /// <summary>The covered sizes the display offers, and where the game starts:
        /// ResolutionSelection.Start's rule (the current size where covered, else the largest),
        /// with LinuxDisplay's current size (the monitor's own under Gamescope).</summary>
        private static int[] StartSize()
        {
            List<int[]> sizes = LinuxDisplay.Sizes().FindAll(s => ResolutionCatalog.Covers(s[0], s[1]));
            int[] current = LinuxDisplay.Start();
            if (current != null && sizes.Exists(s => s[0] == current[0] && s[1] == current[1]))
                return current;
            int[] largest = null;
            foreach (int[] size in sizes)
                if (largest == null || (long)size[0] * size[1] > (long)largest[0] * largest[1])
                    largest = size;
            return largest;
        }

        private static string Summary()
        {
            int[] start = StartSize();
            if (start == null)
                return "This display reports no resolution KMRP can use.";
            return "Starts at " + start[0].ToString(CultureInfo.InvariantCulture) + " × " +
                start[1].ToString(CultureInfo.InvariantCulture) + ". The game lists every resolution the connected display supports.";
        }

        // MainForm.RefreshStatus and UpdateGameStep, in the same words.
        private void Refresh()
        {
            if (running)
                return;
            string target = Executable();
            InstallPlatform.GameFolder = folder.Length > 0 ? folder : null;
            ExecutableState state = target.Length > 0 ? PatchOperations.Inspect(target) : ExecutableState.Missing;
            bool iniExists = false;
            try { iniExists = target.Length > 0 && File.Exists(IniOperations.PathForExecutable(target)); }
            catch { }
            stepFolder.Set(null, File.Exists(target) ? folder : "Choose your Knights of the Old Republic folder.");

            bool executableReady = state == ExecutableState.SupportedClean || state == ExecutableState.Gold;
            actionIsRestore = target.Length > 0 && PatchOperations.CanRestore(target);
            action.SetText(actionIsRestore ? "Restore Original" : "Start Patching");
            action.IsEnabled = actionIsRestore || (executableReady && iniExists);
            int? age = actionIsRestore ? KpmEditionOperations.CompareInstalled(target) : null;
            bool upgradeNow = age == -1 && iniExists;
            upgrade.IsEnabled = upgradeNow;
            LayoutActionRow(upgradeNow);

            UpdateGameStep(state, target, executableReady);

            bool complete = state == ExecutableState.Gold;
            stepFolder.Set(complete ? "1. Selected Game Folder" : "1. Select Game Folder", null);
            stepVerify.Set(complete ? "2. Detected Game Version" : "2. Detect Game Version", null);
            stepResolution.Set("3. Resolutions", complete
                ? "The game starts at this resolution. Choose another in the game's Graphics options." : Summary());
            resolutionState.IsVisible = complete;
            int width, height;
            if (complete)
                resolutionState.Set(PatchOperations.TryReadInstalledResolution(target, out width, out height)
                    ? width.ToString(CultureInfo.InvariantCulture) + " × " + height.ToString(CultureInfo.InvariantCulture)
                    : "Installed", Ui.Text, 0);

            DateTimeOffset? installed = target.Length > 0 ? KpmEditionOperations.InstalledBuild(target) : null;
            if (complete && upgradeNow)
            {
                applyState.Set("Upgrade available", Ui.Accent, 0);
                lastDetail = installed.HasValue
                    ? "Installed: " + BuildStamp.Display(installed.Value) + ". This build: " + BuildStamp.Display(BuildStamp.Current.Value) + "."
                    : "An earlier KMRP is installed. This installer's build is newer.";
            }
            else if (complete && age == 1 && installed.HasValue)
            {
                applyState.Set("Newer build installed", Ui.Warning, 0);
                lastDetail = "A newer build is installed (" + BuildStamp.Display(installed.Value) + ").";
            }
            else if (complete)
            {
                applyState.Set("Patched successfully", Ui.Success, 0);
                if (KpmEditionOperations.IsInstalledForPatchManager(target))
                    lastDetail = "Managed by KOTOR Patch Manager: tick KMRP there, then Apply and Launch.";
                else
                    lastDetail = PatchOperations.TryReadInstalledResolution(target, out width, out height)
                        ? "KOTOR is ready to play at " + width.ToString(CultureInfo.InvariantCulture) + " × " +
                          height.ToString(CultureInfo.InvariantCulture) + "."
                        : "KOTOR is ready to play.";
            }
            else if (executableReady && iniExists)
            {
                applyState.Set("Ready to patch", Ui.Accent, 0);
                lastDetail = "Everything is ready. Start patching when ready.";
            }
            else if (executableReady)
            {
                applyState.Set("Game setup needed", Ui.Warning, 0);
                lastDetail = "Launch KOTOR once, close it, then return here and check again.";
            }
            else
            {
                applyState.Set("Not patched", Ui.TextMuted, 0);
                lastDetail = target.Length > 0 ? PatchOperations.Describe(target) : "No game folder chosen.";
            }
            stepApply.Set(null, lastDetail);
        }

        private void UpdateGameStep(ExecutableState state, string target, bool executableReady)
        {
            stepResolution.Dimmed = !executableReady;
            stepApply.Dimmed = !executableReady;
            GameExecutable exe = target.Length > 0 ? GameExecutable.Identify(target) : null;
            if (executableReady)
            {
                verifyState.Set(exe != null ? exe.Name : "Detected", Ui.Success, 1);
                if (state == ExecutableState.Gold)
                    stepVerify.Set(null, exe != null
                        ? "KOTOR Modern Restoration Patch detected, on the " + VersionName(exe) + "."
                        : "An earlier KOTOR Modern Restoration Patch detected.");
                else
                    stepVerify.Set(null, exe == null ? "A supported swkotor.exe detected."
                        : exe == GameExecutable.Editable ? "The editable 1.03 swkotor.exe detected."
                        : "The " + VersionName(exe) + " of KOTOR detected.");
                return;
            }
            verifyState.Set("", state == ExecutableState.Error ? Ui.Error : Ui.Warning, 2);
            if (state == ExecutableState.Missing)
                stepVerify.Set(null, "No swkotor.exe here. Choose your KOTOR folder in step 1.");
            else if (state == ExecutableState.Unsupported)
                stepVerify.Set(null, "This swkotor.exe is not the Steam, GOG or editable 1.03 version.");
            else
                stepVerify.Set(null, "This swkotor.exe could not be read.");
        }

        private static string VersionName(GameExecutable exe)
        {
            return exe == GameExecutable.Editable ? "editable 1.03 swkotor.exe" : exe.Name + " version";
        }

        /// <summary>One button across the primary's place, or Restore Original and Upgrade
        /// sharing it (MainForm.LayoutActionRow).</summary>
        private void LayoutActionRow(bool split)
        {
            upgradeOffered = split;
            action.Primary = !split;
            double first = split ? Math.Floor((ActionWidth - ActionGap) / 2) : ActionWidth;
            action.Width = first;
            Canvas.SetLeft(upgrade, ActionLeft + first + ActionGap);
            upgrade.Width = split ? ActionWidth - first - ActionGap : ActionWidth;
            upgrade.IsVisible = split;
            action.InvalidateVisual();
        }

        private async Task Browse()
        {
            IReadOnlyList<IStorageFolder> picked = await StorageProvider.OpenFolderPickerAsync(
                new FolderPickerOpenOptions { Title = "Choose your Knights of the Old Republic folder", AllowMultiple = false });
            if (picked.Count == 0)
                return;
            folder = picked[0].Path.LocalPath;
            Refresh();
        }

        // MainForm.PatchClicked, RestoreClicked and RunOperation.
        private void Run(string name)
        {
            if (running)
                return;
            string target = Executable();
            bool installing = name != "Restore";
            int[] start = installing ? StartSize() : null;
            if (installing && start == null)
            {
                Notice("Resolution required", "This display reports no resolution KMRP can use.");
                return;
            }
            LayoutActionRow(false);
            action.Progress = 0;
            action.SetText(name == "Upgrade" ? "Preparing upgrade…   0%" : installing ? "Preparing patch…   0%" : "Preparing restore…   0%");
            running = true;
            browse.IsEnabled = action.IsEnabled = upgrade.IsEnabled = logLink.IsEnabled = false;
            applyState.Set(name == "Upgrade" ? "Upgrading…" : installing ? "Patching…" : "Restoring…", Ui.Accent, 0);
            stepApply.Set(null, installing ? "KMRP is updating your game. Please wait." : "KMRP is restoring your original files. Please wait.");

            string result = null;
            Action<string> report = delegate(string message)
            {
                result = message;
                try { PatchOperations.AppendLog(target, name + ": " + message); }
                catch { }
            };
            Action<int, string> progress = delegate(int percent, string message)
            {
                Dispatcher.UIThread.Post(delegate
                {
                    percent = Math.Max(0, Math.Min(100, percent));
                    action.Progress = percent;
                    message = message ?? "";
                    int tab = message.IndexOf('\t');
                    string left = tab >= 0 ? message.Substring(tab + 1) : "";
                    if (tab >= 0)
                        message = message.Substring(0, tab);
                    action.SetText((string.IsNullOrWhiteSpace(message) ? "Working…" : message) + "   " +
                        percent.ToString(CultureInfo.InvariantCulture) + "%");
                    timeLeft.Text = left;
                    timeLeft.IsVisible = left.Length > 0;
                });
            };
            Task.Run(delegate
            {
                Exception error = null;
                try
                {
                    if (installing)
                        PatchOperations.ApplyInPlace(target, start[0], start[1], report, progress);
                    else
                        PatchOperations.Restore(target, report, progress);
                }
                catch (Exception ex) { error = ex; }
                Dispatcher.UIThread.Post(delegate { Finished(name, installing, target, result, error); });
            });
        }

        private void Finished(string name, bool installing, string target, string result, Exception error)
        {
            action.Progress = -1;
            timeLeft.IsVisible = false;
            running = false;
            browse.IsEnabled = logLink.IsEnabled = true;
            if (error != null)
            {
                Refresh();
                applyState.Set("Error", Ui.Error, 0);
                stepApply.Set(null, name + " stopped — no incomplete changes were left behind.");
                try { PatchOperations.AppendLog(target, name + " failed: " + error); }
                catch { }
                Notice(name + " blocked", error.Message);
                return;
            }
            Refresh();
            applyState.Set(name == "Upgrade" ? "Upgraded successfully" : installing ? "Patched successfully" : "Restored successfully", Ui.Success, 0);
            stepApply.Set(null, result == null ? name + " completed." : result.Length <= StepLineLimit ? result : lastDetail);
            if (installing && KmrpSettings.ControllerSupport)
                OfferSteamLayout(target);
        }

        /// <summary>MainForm.OfferSteamLayout: under Proton, Steam's controller layout for KOTOR
        /// has to be Gamepad for KMRP's controller support to get the pad. Told, not done.</summary>
        private void OfferSteamLayout(string target)
        {
            const string notice = "For the controller to work, KOTOR's controller layout in Steam has to be " +
                "set to Gamepad.\n\nSteam gives KOTOR a keyboard and mouse layout by default, and the game " +
                "then gets no controller at all.\n\nIn Steam: KOTOR -> the controller icon -> Edit Layout -> " +
                "Templates -> Gamepad -> Apply.";
            try { PatchOperations.AppendLog(target, "Controller under Steam on Linux: " + notice.Replace("\n\n", " ")); }
            catch { }
            Notice("Set the controller layout to Gamepad in Steam", notice);
        }

        private void OpenLog()
        {
            string target = Executable();
            if (target.Length == 0)
                return;
            try
            {
                string log = PatchOperations.LogPath(target);
                if (!File.Exists(log))
                    File.WriteAllText(log, "KOTOR Modern Restoration Patch log\r\n");
                Ui.OpenOutside(log);
            }
            catch (Exception ex) { Notice("Unable to open log", ex.Message); }
        }

        private void Notice(string title, string text)
        {
            Window dialog = new Window
            {
                Title = title, Width = 560, SizeToContent = SizeToContent.Height, CanResize = false,
                Background = Ui.Brush(Ui.Card), WindowStartupLocation = WindowStartupLocation.CenterOwner,
            };
            StackPanel body = new StackPanel { Margin = new Thickness(28), Spacing = 20 };
            body.Children.Add(new TextBlock
            {
                Text = text, TextWrapping = TextWrapping.Wrap, FontFamily = Ui.Body, FontSize = 15, Foreground = Ui.Brush(Ui.Text),
            });
            PillView ok = new PillView { Primary = true, Text = "OK", Width = 140, Height = 44, HorizontalAlignment = HorizontalAlignment.Right };
            ok.Click += delegate { dialog.Close(); };
            body.Children.Add(ok);
            dialog.Content = body;
            dialog.ShowDialog(this);
        }

        internal void ShowSettingsForCheck() { ShowSettings(true); }

        /// <summary>MainForm.FitInitialSizeToWorkingArea: the approved 1300 x 700 composition at
        /// 1080p, scaled by the screen's working area against 1920 x 1040, kept inside 94% of it
        /// and never below 35%.</summary>
        private void FitInitialSize()
        {
            Avalonia.Platform.Screen screen = Screens.ScreenFromWindow(this) ?? Screens.Primary;
            if (screen == null)
                return;
            double scaling = screen.Scaling > 0 ? screen.Scaling : 1;
            double workWidth = screen.WorkingArea.Width / scaling, workHeight = screen.WorkingArea.Height / scaling;
            double reference = Math.Min(1300 / DesignWidth, 700 / DesignHeight);
            double monitor = Math.Min(workWidth / 1920, workHeight / 1040);
            double fit = Math.Min(workWidth * 0.94 / DesignWidth, workHeight * 0.94 / DesignHeight);
            double scale = Math.Max(0.35, Math.Min(reference * monitor, fit));
            Width = Math.Round(DesignWidth * scale);
            Height = Math.Round(DesignHeight * scale);
            Position = new PixelPoint(screen.WorkingArea.X + (int)Math.Max(0, (screen.WorkingArea.Width - Width * scaling) / 2),
                screen.WorkingArea.Y + (int)Math.Max(0, (screen.WorkingArea.Height - Height * scaling) / 2));
        }
    }

    internal sealed class InstallerApp : Application
    {
        public override void Initialize()
        {
            Styles.Add(new Avalonia.Themes.Fluent.FluentTheme());
            RequestedThemeVariant = Avalonia.Styling.ThemeVariant.Dark;
        }

        public override void OnFrameworkInitializationCompleted()
        {
            if (ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
            {
                MainWindow window = new MainWindow();
                desktop.MainWindow = window;
                // For checking the window without a person at the screen: with KMRP_RENDER_PNG set,
                // the window, once open and laid out, is saved as that picture and closed;
                // KMRP_RENDER_SETTINGS=1 shows Advanced Settings first.
                string picture = Environment.GetEnvironmentVariable("KMRP_RENDER_PNG");
                if (!string.IsNullOrEmpty(picture))
                    window.Opened += delegate
                    {
                        if (Environment.GetEnvironmentVariable("KMRP_RENDER_SETTINGS") == "1")
                            window.ShowSettingsForCheck();
                        DispatcherTimer.RunOnce(delegate
                        {
                            PixelSize pixels = new PixelSize((int)window.Bounds.Width, (int)window.Bounds.Height);
                            using (var bitmap = new RenderTargetBitmap(pixels))
                            {
                                bitmap.Render(window);
                                bitmap.Save(picture);
                            }
                            desktop.Shutdown();
                        }, TimeSpan.FromSeconds(6));
                    };
            }
            base.OnFrameworkInitializationCompleted();
        }
    }
}
