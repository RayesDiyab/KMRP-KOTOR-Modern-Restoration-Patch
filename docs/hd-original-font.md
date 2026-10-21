# HD Original font: the game's own fonts, redrawn

Reference, 2026-10-18. Follows the [documentation standard](documentation-standard.md).
This covers [build_hd_original_fonts.py](../tools/build_hd_original_fonts.py) and what
it writes to `assets/hd-original-fonts`: the atlases of the **(New) Original HD Font**
style, the default since 2026-10-18. How the style is chosen, stored in the bank and
fitted to the drawn size is in [in-game text options](ingame-text-options.md); the
Old HD atlases are in [font scaling](font-scaling.md).

**Typography research credit:** Thanks to **SithHolocron** of DeadlyStream and Discord for
providing the initial typeface research and comparisons that identified Bank Gothic and
Helvetica as the likely basis for KOTOR's fonts. Those references were the starting point
for KMRP's glyph-by-glyph reconstruction against the original game atlases.

Provenance: every number below was read from the original atlases and from the
built HD atlases with the tool's own `Stock` class (and `fit_ring`, `fit_donor`), on
2026-10-18; section 8 repeats each read. The comparison images were drawn by local
scripts that are not in the repository. The fonts were reviewed by the maintainer
at 4K and 100% text, menu font first. **Not seen in game at the time of writing.**

## The build this describes

No executable bytes are involved. The tool reads files only:

| Input | Bytes | SHA-256 |
| --- | --- | --- |
| `build-inputs/swpc_tex_gui.erf` (the GUI texture pack), through `build/native-runtime/original-fonts/kmrfogNN` | 111,598,685 | `da937e430573856a99c76f8df3960669022e545e149339022168c0d2a57bfe95` |
| `build-inputs/local-fonts/BankGothicMedium.otf` (not in the repository) | 24,348 | `f23c68b985aedbe0cea487c6cf2b0354b5c54169906d8616cd69e43350c9a9a8` |
| `build-inputs/local-fonts/Helvetica.ttf` (Apple; not in the repository) | 317,968 | `5f865ddf37549ae44630b13a501f813086e2ae974adc86b97337cd9ee4b1e4ff` |
| `build-inputs/local-fonts/Helvetica-Bold.ttf` (Apple; not in the repository) | 308,628 | `05291f9de00325c3a3f1acdf9a35a8ce4b4fd7d32394482ebb1699ba7ac73ed5` |
| `assets/fonts/Arimo-Medium.ttf` (the ß and the euro sign) | 321,308 | `d7da3d766ed7121c8f1f318a4d123bd98cbaa28b3bef16870b06e746281cb088` |

The face files stay out of the repository; only the atlases baked from them are
committed and shipped (the maintainer's ruling on 2026-10-18).

## 1. The originals: three designs

The 18 stock atlases are hand-made pixel fonts. Measured by drawing each original
letter beside each candidate face at the same box:

| Design | Fonts | Face used |
| --- | --- | --- |
| Menu: Bank Gothic, lower case as small capitals | dialogfont10x10, 10x10a, 10x10b, 12x16, 16x16, 16x16a, 16x16b, 32x32 | Bank Gothic Medium |
| Body: a bold Helvetica-style sans | fnt_d16x16, d16x16b, d10x10b, credits, creditsb, console (in cells of one width) | Helvetica Bold |
| Light: the same sans, light | fnt_creditsa, d16x16a, dialog16x16 | Helvetica |
| fnt_galahad14, a decorative face | the original enlarged and sharpened (no face) | none |

The 12x16 and 32x32 menu fonts hold only ASCII; their other slots (122 and 121;
32x32 has 255) are placeholder boxes in the original and get the face's real
characters here, at the face's own width (the original font must support everything
translations use). **Correction:** the first build also took 32x32's `|`, a solid
bar 2 pixels wide, for a placeholder box (edges full, inside empty: a 2 pixel box has
no inside) and drew it at the face's width; `Test-TextOptions.py` caught it on
2026-10-18. A box now needs at least 3 columns.

## 2. Measuring to a fraction of a pixel

The originals are anti-aliased. An edge pixel is covered by as much of the letter as
stands in it, so the edge lies that far into it; a faint halo of 6 to 10 percent lies
one pixel beyond every edge and is the edge's own coverage, blurred outward
(`Stock.span`, `HALO = 0.15`). Strokes are the coverage summed across them
(`Stock.stroke`: I at half height; `Stock.bar`: down H's middle column).

Counted in whole pixels, as the tool did until this was found on 2026-10-18, two of
the 16 pixel menu font's measures were wrong:

| dialogfont16x16 | Whole pixels | To a fraction | Evidence |
| --- | --- | --- | --- |
| Capital height (H) | 9 | 9.00 | rows 5 to 13 solid, 0.06 above and below (halo) |
| Small-capital height (x) | 7 | **7.47** | every small capital's top row is 37 to 42 percent covered (x n e t r l m s a c o) |
| Vertical stroke (I) | 2 | 2.08 | 0.71 + 1.00 + 0.39 |
| Horizontal stroke (H's bar) | 2 | **1.69** | 0.51 + 1.00 + 0.17 |

7.47 / 9.00 = 0.83 is Bank Gothic's own x height against its H: the originals'
small capitals are the face's, not shortened. A whole-pixel count had made the HD
small capitals 5 percent short and its horizontal strokes 19 percent heavy.

All fonts, read the same way (`cap_height`, `small_cap_height`, `stroke`, `bar`):

| Font | Capital | Small capital | Stroke | Bar | Anti-aliased |
| --- | --- | --- | --- | --- | --- |
| dialogfont10x10, 10x10a, 16x16a | 6.00 | 5.00 | 1.00 | 1.00 | no (1-bit) |
| dialogfont10x10b | 8.96 | 7.44 | 2.08 | 1.68 | yes |
| dialogfont12x16 | 7.25 | 5.85 | 1.68 | 1.41 | yes |
| dialogfont16x16, 16x16b | 9.00 | 7.47 | 2.08 | 1.69 | yes |
| dialogfont32x32 | 18.00 | 14.73 | 4.19 | 3.26 | yes |
| fnt_d16x16, d16x16b, d10x10b, credits, creditsb | 11.44 | 8.25 | 1.85 | 1.98 | yes |
| fnt_console | 9.00 | 7.00 | 2.00 | 1.00 | no |
| fnt_creditsa, d16x16a, dialog16x16 | 8.00 | 6.00 | 1.00 | 1.00 | no |

A font counts as anti-aliased when 5 percent or more of its inked pixels are partly
covered: the anti-aliased ones measure 15.8 to 59.4 percent, the 1-bit ones at most
1.3 percent.

## 3. The rules

Each atlas is baked at six times the original (`SCALE = 6.0`), the size 100% text is
drawn at on a 2160-line screen. For every character:

* its cell is the original cell's width times six, so letter gaps, word spaces, line
  lengths and the HUD's even cells are the original's;
* the TXI's `fontheight`, `baselineheight`, `spacingR` and `spacingB` are the
  original's times six, as Old HD's are. **Correction:** the first build wrote
  `baselineheight` as the row the letters stand on (0.84 for the 16 pixel menu
  fonts, whose original says 0.16, the cell's height); `Test-TextOptions.py` caught
  it on 2026-10-18 before it reached the game. The atlases did not change;
* the capitals and digits are drawn at the original's capital height, and in the menu
  fonts the small capitals at the original's small-capital height, each a pen of its
  own (`Pen`, `settled`);
* each pen has one width factor, the median over its letters of the original's ink
  width over the face's;
* strokes are made as heavy as the original's, only ever heavier, and only where the
  capital is 9 pixels or more (a 6 pixel capital's 1 pixel stroke is the pixel grid's
  limit, not the design's; thinning to it lost thin punctuation);
* each letter is centred where the original's ink is centred;
* accents above the capital line are pressed into the room above it, and tails below
  the baseline into the room below, the letter itself keeping its size.

## 4. The round O

Bank Gothic's O is square; the originals redrew O and o round in some fonts. Each
plain O, o and 0 of an anti-aliased font is fitted with a superellipse ring (centre,
half-width, half-height, exponent n, side and top strokes) by least squares on its
coverage (`fit_ring`); it is round when n is 3 or less. The fits, in original pixels:

| Font | Letter | Width | Height | Width / height | n | Strokes (side / top) | Round |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dialogfont16x16, 16x16b | O | 10.60 | 9.09 | 1.166 | 2.22 | 2.13 / 1.72 | yes |
| dialogfont16x16, 16x16b | o | 9.00 | 7.38 | 1.220 | 2.31 | 1.85 / 1.41 | yes |
| dialogfont16x16, 16x16b | 0 | 10.16 | 9.07 | 1.120 | 5.97 | 1.76 / 1.54 | no |
| dialogfont10x10b | O | 10.16 | 8.85 | 1.148 | 2.56 | 1.91 / 1.65 | yes |
| dialogfont10x10b | o | 9.28 | 7.33 | 1.266 | 2.13 | 1.90 / 1.36 | yes |
| dialogfont12x16 | O | 8.93 | 7.25 | 1.231 | 5.71 | 1.58 / 1.18 | no |
| dialogfont32x32 | O | 22.15 | 18.48 | 1.198 | 5.99 | 4.04 / 3.36 | no |

The fits leave 0.3 percent of the 16 pixel O's coverage unexplained (squared error
0.132 of 40.3), 0.1 percent of its o's (0.032 of 26.7). The HD letter is that ring at six times,
placed where the original's stands, so its cell is the original's and the line keeps
its length. Accented O and o (Ö, ö and the rest), Q, 0 and Ø keep Bank Gothic's
squared shape in every anti-aliased font, as the originals do. The 1-bit fonts
(cap 6) are too coarse to fit (a fit to the 7 by 6 pixel O came out nearly a
diamond, n 1.44): there the ring fills the original's box as an ellipse, and the
corner test (`Stock.round`) decides, which picks the O family.

**Corrections, each at the maintainer's review on 2026-10-18.** Each rule below was
built, shown and replaced:

| Rule | 16 px O at 4K | What was wrong |
| --- | --- | --- |
| The original's whole-pixel box, 10 by 9 (o 10 by 7) | 120 x 108 | an oval; the o 1.43 times wider than tall |
| A circle as wide as that box | 120 x 120 | a bit too large |
| A circle Helvetica's overshoot taller than the line (O 1.0556 times H, o 1.0634 times x), its cell narrowed to keep the gaps | 114 x 114 | too round; lines shorter than the original's (ROOM 576 pixels against 588) |
| The fitted ring (now) | 127 x 109 | |

The third rule was agreed at first; on the next comparison the maintainer saw that
the original's O is a little wider than it is tall and had that copied. The fitted
ring also stands exactly on the capital lines: the originals' O has no overshoot
(top 4.89, bottom 13.98, against H's 5.00 and 14.00).

### The body and light fonts' o (2026-10-21)

The maintainer, from a 4K comparison: in "before", the o of the new font "is taller than
the width ... this specific letter should be wider so its new width equals the already
present height", and for every font of the Helvetica designs (the bold body fonts, the
three light ones and the HUD's `fnt_console`). The face's o, narrowed by the font's one
factor, was taller than wide; the bold original's o is round:

| Font, at six times | o before | o now | Its cell |
| --- | --- | --- | --- |
| bold (`fnt_d16x16`, `d16x16b`, `d10x10b`, `credits`, `creditsb`) | 49.99 x 53.53 | 53.24 x 53.51 | 60, as the original's 10 x 6 |
| light (`fnt_d16x16a`, `creditsa`, `dialog16x16`) | 29.88 x 37.00 | 29.88 x 37.00 again (37.00 x 37.00 for a day) | 36, as the original's (44 for a day) |
| `fnt_console` | 33.85 x 42.00 | 41.74 x 41.96 | 48, its cells all one width |
| the bold original, at one time | 8.51 x 8.59 | | 10 |

(Ink measured by coverage, `Stock.span`'s rule.) How (`RoundO`, `round_o_letter` in
`tools/build_hd_original_fonts.py`): the face's own o is drawn wider by one more factor
k, then its vertical strokes are made lighter again by (k - 1) times its side stroke,
with the same operation that makes strokes heavier (`_spread`), so its sides are as
heavy as every other letter's; k = (h - s) / (w - s), settled on the drawn letter by the
secant method. A stretch of the inside only was tried first in thought and not built:
it would have put a kink in the curve where the stretch begins. The accented ò ó ô õ ö
are the round o with the face's accent (its accented letter less its plain o) centred
on it; ø is widened whole, its bar with it. The o keeps the original's centre, moved in
from a side it would come closer to than a sixth of an original pixel; only where it
cannot fit so is its cell widened, by as much as the o grew, so it keeps its room (the
light fonts: a line with o in it grew by about 1.3 original pixels per o; in the bold
fonts nothing moves). **Correction, the same day:** the maintainer saw the light text's
o as too wide ("It's supposed to be less wide ... light text only"): its original is 5
by 6 pixels, narrower than tall. The round o is now the bold designs' only (`BODY`); the
light fonts are as they were before that day, byte for byte, their o Helvetica's own at
0.81 of its height, and `Test-TextOptions.py` again allows no width but the original's.
**Not seen in the game.**

### The whole-pixel menu fonts' o, and their gaps (2026-10-21)

`dialogfont10x10`, `10x10a` and `16x16a` are drawn in whole pixels; their o is 6 by 5
with one pixel off each corner. The corner test (`Stock.round`) wanted a fifth of the
width, 1.2 pixels, so it took that o for square and Bank Gothic's box was drawn; it
counts in whole pixels now (`w // 5`). The maintainer, shown the circle that fits it,
wanted Bank Gothic's box with rounder corners outside and inside, and chose a
superellipse of exponent 3 (`WHOLE_PIXEL_O_SQUARENESS`) from 3, 4, 5 and 7, its size and
strokes the fitted ring's. Then: "the space between M and O ... should be the same like
in the original". Every letter of these originals ends a pixel before its cell does, 6
atlas pixels; Bank Gothic's letters at the font's one factor were wider than the
original's (M 46.5 against 42, W 58.8 against 54; about 50 letters), which ate the gap
(M to o 0.6). A letter wider than the original's ink is now narrowed to it (by up to
about 12 percent, its strokes with it): M to o is 5.55, every gap 5.3 to 6.5. The five
anti-aliased menu fonts are unchanged. **Not seen in the game.**

### The HUD font's black outline (2026-10-21)

The original `fnt_console`, the HUD's credits, level and XP, draws each white letter in a
black ring one pixel wide that fills the corners too (black, alpha 204 to 255); 70 percent
of its ink is that ring, and no other text font has one. The HD font had dropped it, and a
player saw that the numbers need it to read over every map ("This font could really
benefit from keeping the black border"). `OUTLINED` in `tools/build_hd_original_fonts.py`
now gives it back: a black ring 6 pixels wide at six times (one original pixel), the
letter's coverage spread by a disc with a soft edge, inside each letter's cell, and the
letter white over it. The atlas is the first HD one with colour in it; KMRP fits it as it
fits `fnt_galahad14` (`FitAtlas`, every channel). The original's letters reach their
cell's last column (the 4's bar, M, N, W, m, w), which cut their ring on the right, in
the original too; the maintainer asked for "one more pixel of black border" there. So
the HUD font's cells are one original pixel (6 at six times) wider on the right, 54 in
place of 48, and its `spacingR` that much less, 0.06 in place of 0.12: every letter's
step, cell and spacing together, is the original's, and a line of HUD text is exactly
as long (2,402 pixels both for the same line at 96). `Test-TextOptions.py` compares
those steps now, not the cells alone. **Not seen in the game.**

### The HUD font drawn from geometry (2026-10-21)

The same day the maintainer saw that the HUD font's 4 and small l "don't match the
original": Helvetica Bold, which drew it, has a closed 4, a plain l and I, and no feet on
i and 1, while the original is an 8 by 16 console font with an open 4 and slab-footed l,
i, I and 1. No installed typeface has all of that (Consolas and Ubuntu Mono have the
feet but a closed 4), and tracing the pixels either keeps their stairs (traced enlarged)
or turns the one pixel bars into wedges (traced at the original's size). So every letter
is now written as geometry on the original's own grid, `tools/hud_font_geometry.py`.
A first version joined rectangles, rings and bands; where two met a little apart they
left notches and bumps, and the maintainer saw letters that looked "fused together" (the
s, the 2, the 4). So each letter is now one or two strokes along a centre line, drawn
with a pen the shape of the original's strokes (two pixels wide, one tall, its corners
rounded by 0.35 so a turn's outside is rounder than its inside, as an offset curve's is),
each turn rounded (radius 1.3) where the original cuts a corner and straight where it
steps; a stroke is one piece, so its joins are clean. The thin middle strokes of M, W,
the rings of % use a one pixel pen, as the original does. M, N, W, m and w are not the
pixel font's (a one pixel middle stroke, a staircase that turns down, right and down
again): the maintainer asked for "a normal kind of M" and a W that goes "down and then
one continuous slash", so they are stems with straight diagonals, an M's meeting in the
middle, a W's rising from the foot of each stem, drawn with a slightly narrower pen
(1.7) so three strokes fit the cell. `GEOMETRIC` in `build_hd_original_fonts.py` draws
`fnt_console` from it at six times, in the original's cells, and `OUTLINED` rings it.
Drawn back at the original's size, 32 of the 94 letters match it pixel for pixel and 74
are within 4 pixels; the rest differ where a step became a line or a curve, and W (16)
and w (11) by design. The check is
`python tools/hud_font_geometry.py OUT` (a report and a sheet of each original letter
beside the new one). **Not seen in the game.**

## 5. The ß

Bank Gothic Medium has no real ß (its ß is drawn "SS"). The originals' ß is a plain
sans ß, as a Windows fallback face draws one. Each candidate face's ß was placed and
stretched to best match the 16 pixel original by least squares (`fit_donor`; squared
error left, lower is closer):

| Face | Error |
| --- | --- |
| Microsoft Sans Serif | 3.92 |
| Arial | 4.34 |
| Arimo Medium | 4.43 |
| Arial Bold | 4.76 |
| Trebuchet MS Bold | 6.20 |
| Helvetica Bold | 7.69 |
| Verdana Bold | 7.80 |
| Tahoma Bold | 8.46 |
| Tahoma | 8.57 |
| Helvetica | 9.14 |

Arimo Medium, Arial's open twin and already in the repository, is used: fitted at
ink box (0.48, 4.34), 10.55 by 9.51 pixels, made 0.3 pixels heavier, and scaled by
each menu font's capital height. **Correction:** until 2026-10-18 the ß was the
original's whole-pixel ß enlarged, blurred and cut at half, which left it lumpy (a
bump at the lower right); the maintainer's review found it.

ð and þ are not fallback glyphs: the originals draw Bank Gothic's Ð and Þ at
small-capital size, and so does the tool.

## 6. The result, measured (dialogfont16x16)

The built atlas read back the same way, in original pixels (HD figures divided by 6):

| Measure | Original | HD Original |
| --- | --- | --- |
| Capital height | 9.00 | 9.00 |
| Small-capital height | 7.47 | 7.43 |
| Vertical stroke | 2.08 | 2.03 |
| Horizontal stroke | 1.69 | 1.61 |
| O: width x height, n | 10.60 x 9.09, 2.22 | 10.52 x 9.04, 2.23 |
| o: width x height, n | 9.00 x 7.38, 2.31 | 9.12 x 7.34, 2.22 |
| Ink widths C E G L M S T | 9.86 9.31 10.69 8.89 11.75 10.12 10.30 | 9.75 9.22 10.59 8.79 11.68 10.01 10.31 |
| Ink widths e l n t | 8.10 7.54 9.27 8.97 | 7.95 7.53 9.04 8.87 |
| Every cell width | the original's | the original's, times six |

At 4K and 100% text, "ROOM Controller", "Options LOAD GAME" and "Größe Close Æther"
end on the same pixel column as the original's.

## 7. What is deliberately not changed

* **Per-letter widths.** One width factor per pen keeps Bank Gothic's proportions.
  Four letters stay wider than the original's: R by 0.50 pixels, r 0.54, x 0.95, A
  0.41. Fitting each letter's width would narrow its strokes with it.
* **The faces' designs elsewhere.** Only O and o (where the original is round), ß,
  ¤ (a square ring with corner ticks, as the original) and @ (fitted to the
  original's box) depart from the face.
* **fnt_galahad14** has no face here: it is the original enlarged with Lanczos and
  its edges steepened, as Original Sharpened was. Since that is the game's own art, it
  is not in the repository: the bank build makes it from the game's files every time
  (`build_original_fonts.enlarged`, `build_native_assets.hd_original`, into
  `build/native-runtime/hd-original-fonts`). The maintainer's ruling, 2026-10-19; the
  file it replaces in `assets/hd-original-fonts` was byte for byte the same.
* **Sizes on screen.** The runtime draws every style at the sizes Old HD defined
  ([in-game text options](ingame-text-options.md)); HD Original changes the letters,
  not how large text is.

## 8. Verifying by hand

From the repository root, with the faces in `build-inputs/local-fonts`:

```bash
python tools/build_original_fonts.py --texture-pack build-inputs/swpc_tex_gui.erf --output build/native-runtime/original-fonts
python tools/build_hd_original_fonts.py build/native-runtime/original-fonts assets/hd-original-fonts
python testing/regression/Test-TextOptions.py
```

The second prints, per font, the rounds fitted and their rings; check dialogfont16x16
reports `round 4F 6F` and `O 10.60x9.09 n 2.22`. The test checks that every HD
Original TXI keeps its original's glyph count, cell height, baseline and ASCII cell
widths at six times. To read a measure in section 2 or 4 yourself:

```bash
python -c "import sys; sys.path.insert(0, 'tools'); from pathlib import Path; from build_hd_original_fonts import Stock, fit_ring; s = Stock(Path('build/native-runtime/original-fonts'), 'dialogfont16x16'); print(s.cap_height, s.small_cap_height(), s.stroke(), s.bar(), fit_ring(s, ord('O')))"
```

The trap this subsystem invites is a whole-pixel count: a threshold at half coverage
drops the partly covered edge row and reports 7 for the small capitals and 2 for the
bar. Measure coverage, and check a measure against a letter whose size you know (H
is 9.00) before trusting it.
