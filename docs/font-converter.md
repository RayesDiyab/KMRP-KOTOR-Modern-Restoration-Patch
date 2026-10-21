# KMRP Font Converter

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

Reference, 2026-10-21. A separate program that turns any font file into KOTOR's game
fonts. It shares no code with KMRP's patch or installer; it carries KMRP's branding and
its fonts are made for KMRP (section 4). **Not yet seen in the game, nor run under Proton.**

## 1. Files

| File | What it is |
| --- | --- |
| `src/font-converter/FontConverter.cs` | The window: tiles, pop-ups, conversion thread, where the output goes |
| `src/font-converter/FontSource.cs` | Reading font files through DirectWrite, by vtable; WOFF read directly |
| `src/font-converter/Atlas.cs` | Glyph rasteriser and the atlas/TXI writer |
| `src/font-converter/build.ps1` | Builds `dist\KMRP Font Converter.exe` with the .NET Framework 4 `csc` |
| `src/font-converter/logos.html`, `logo-github.png`, `logo-deadlystream.png` | The pop-up's two marks in one colour, the installer's icon ink (92,165,250): GitHub's Octicons mark (MIT), rendered with Edge, headless, on transparency; and DeadlyStream's icon, Darth Nihilus' mask, from the HD picture the maintainer supplied on 2026-10-21, its brightest channel mapped to the blue (dark 16,42,92 to the ink to 176,214,255), the black around it and in its eyes made transparent, 182x256 |
| `src/font-converter/kmrp-logo.png` | The logo, `tools/build_brand_image.py --text KMRP --tracking 0.12 --whole-crest`, 400x300 |
| `tools/build_font_converter_data.py` | Makes `build/font-converter`: `references.txt`, `examples.txt` and the example PNGs, from `assets/hd-original-fonts` |

## 2. What it writes

Eleven tiles, one for each distinct letter set of the game's 17 text fonts (the sets
`tools/build_hd_original_otf.py` finds by comparing every glyph; `fnt_galahad14` is
left out, it is game art). A tile's font is written to every font name of its set:

| Tile | Group | Font names |
| --- | --- | --- |
| Menu | Menus | dialogfont16x16, dialogfont16x16b |
| Menu Small | Menus | dialogfont10x10, dialogfont10x10a, dialogfont16x16a |
| Menu Small Bold | Menus | dialogfont10x10b |
| Menu Medium | Menus | dialogfont12x16 |
| Menu Large | Menus | dialogfont32x32 |
| Dialogue | Reading | fnt_d16x16, fnt_d10x10b |
| Replies | Reading | fnt_d16x16b |
| Journal | Reading | fnt_d16x16a, fnt_creditsa, fnt_dialog16x16 |
| HUD | HUD | fnt_console |
| Credits | Credits | fnt_credits |
| Credits Bold | Credits | fnt_creditsb |

Each atlas is the Original HD Font's TXI header (fontheight, baselineheight, spacing,
numchars, unchanged) with the player's glyphs, so it is the same 6x size as KMRP's own
HD fonts. The rules are `tools/build_font_from_ttf.py`'s, measured from the game's
atlases: Windows-1252 slots, no zero-wide glyph (a slot the font lacks keeps the HD
Original glyph's width and stays blank), ink moved inside its cell, 4 pixels between
cells. One change: the glyph box holds the font's ascent and descent or, where a letter
of the game's text reaches further, that letter (Bahnschrift's caron over S and Z was
cut off at the ascent). A `.tpc` of the same name in the folder would win over the new
`.tga`, so it is renamed `*.tpc.before-font-converter`.

Measured with Bahnschrift, Georgia and Consolas on the maintainer's PC (3440x1440):
the window shows 0.19 to 0.20 s after start, all 17 atlases take 0.47 s, a tile's preview
line 19 ms. Atlases are uncompressed 32-bit TGA, 16 MB at 2048 square.

## 3. Formats

**Window size.** Everything is laid out on a 1600x900 canvas scaled evenly to the
window. Dragging an edge keeps the inside 16:9 (`WM_SIZING`), so the canvas always fills
it; maximized on a screen of another shape it is centred and the header's glow reaches
the window's edges. The window opens at the screen's scale as large as fits 94% of the
work area's width and 92% of its height; the smallest is three quarters of the canvas at
the screen's scale (1200x675 at 100%), where the smallest text is about 9 pixels. Each
image is kept at one size and made again when the size changes, stretched while an edge
is dragged and sharp again when it is let go. Measured on 2026-10-21 by sending the window
`WM_SIZING`: every edge and corner gave a 16:9 inside (1484x835, 2064x1161, 1984x1116,
1384x778), and `--size=1000x560` opened at the minimum, 1200x675.

DirectWrite reads TrueType and OpenType (both outline kinds) and collections; WOFF2 is
unpacked by `IDWriteFactory5::UnpackFontFile` (Windows 10 1703 and later), a variable
font's named instances come from its `fvar` table and are made with
`IDWriteFactory6::CreateFontResource` (Windows 10 1809 and later). WOFF 1.0 is
inflated by the converter itself, so it needs no newer DirectWrite. Where those
interfaces are missing, a variable font shows its default instance only and a WOFF2
file is refused with a message. Other types (Type 1, `.fon`, `.dfont`, `.eot`, SVG
fonts) are refused: "This font type can't be used".

Slot numbers were counted from the 10.0.26100.0 SDK headers: `IDWriteFactory` 3 to 23,
`CreateFontFileReference` 7, `CreateFontFace` 9; `UnpackFontFile` 47;
`CreateFontResource` 49; `IDWriteFontFace::GetMetrics` 8, `GetGlyphIndices` 11,
`TryGetFontTable` 12, `GetGlyphRunOutline` 14; `IDWriteFontResource::CreateFontFace` 13.

**Linux with Proton (untested).** The program is meant to run under Wine/Proton:
.NET Framework comes from wine-mono, DirectWrite from Wine's `dwrite.dll`. Where
Bahnschrift, Segoe UI or Consolas are missing it falls back to Tahoma, Arial or the
system sans; the dark title bar is skipped where DWM is missing.

## 4. Why KMRP is needed

KMRP sizes Override fonts for the resolution and text size in use
(`KmrpFontMetricsLoadedK1`, [ingame-text-options.md](ingame-text-options.md) section 3):
it scales the five TXI metrics to the size its own font of that name is drawn at.
Without KMRP the game draws these 6x atlases at their own size, six times too large.
The pop-up at every start says so, with buttons to KMRP's DeadlyStream page and its
GitHub releases.

**Open question, untested.** KMRP fits its own HD fonts' atlases to the drawn size
(`FitAtlas`); an Override font only has its metrics scaled, so the game shrinks the 6x
atlas when it draws (about 3 times at 1440 lines and the default text size) with
`mipmap 0`. Whether that looks clean has not been seen in the game.

## 5. Command line

For screenshots and checks: `--no-intro`, `key=path[#face name]` (a tile's font, keys
as in `Tiles.All`), `--pick key=path`, `--done`, `--out=folder`, `--convert`,
`--no-done`.
