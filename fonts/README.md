# KMRP Original HD fonts

Reference, 2026-10-22, following the [documentation standard](../docs/documentation-standard.md).
The lab record of how the redraw was reached is section 6 of this document.

KOTOR's own fonts in high resolution, as 11 OpenType (CFF) files and one TrueType
collection holding all 11 (`KMRP-OriginalHD.ttc`): the letters of KMRP's (New) Original
HD Font, drawn as straight lines, sharp corners and arcs. **Free to use,
change and share, with credit, under the [SIL Open Font License 1.1](OFL.txt)**:
anyone may bundle them in a game, a mod, an app or a website without asking. No
Reserved Font Name, so a changed version may keep the name.

KMRP draws its game atlases from these files (`tools/build_hd_original_atlases.py`
writes `assets/hd-original-fonts`), and the KMRP Save Editor sets its window in them.

## 1. The files

`otf/`, 11 fonts, CFF outlines. One file per different font the game uses; the game
keeps the same letters under several names, so 11 files serve its 17 text fonts. 1000
units per em; advance widths, ascent and descent are the game's (to a unit), so text
sets as it does in KOTOR. `KMRP-OriginalHD.ttc` holds the same 11 with TrueType outlines
(the cubic curves made quadratic within half a unit, `tools/collection.py`) and
ttfautohint's hints: one file that installs all 11 fonts.

| File | Bytes | Units per em | Glyphs | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `KMRP-OriginalHD-Console.otf` | 16,068 | 1000 | 96 | `1fc40423354679d9481380fc91085a8ec9c6f3cf7bd0cfb7a453618a527eb435` |
| `KMRP-OriginalHD-Credits.otf` | 38,932 | 1000 | 218 | `1df5fec87be4d9f60e2f793148f8a965d2cf683264febde34405076dd143459c` |
| `KMRP-OriginalHD-CreditsBold.otf` | 38,972 | 1000 | 218 | `d4b2b0ece9d4eb9867b488050d37b6314cd9388c8f5e19daa302ae23d22de079` |
| `KMRP-OriginalHD-Descriptions.otf` | 39,008 | 1000 | 218 | `5707034a55761a236345f67c2839f6db2d50c28e952445f639425bdf2a9095c7` |
| `KMRP-OriginalHD-Dialogue.otf` | 38,936 | 1000 | 218 | `1923a13ccfd495fceaf2c386a298c320379e25a9f997d30c234940baef2b0099` |
| `KMRP-OriginalHD-Light.otf` | 31,580 | 1000 | 218 | `4f5e38ca665298e5365710743ab89a01458a9beed5bf9b41bfdfd52cffe493f8` |
| `KMRP-OriginalHD-Menu.otf` | 33,796 | 1000 | 218 | `cf83ee832f9ccd20b1f93d402944b0016f0debc0f407393aa04c757cd9196eb4` |
| `KMRP-OriginalHD-MenuLarge.otf` | 34,980 | 1000 | 218 | `13b013cb7b7ed802268560c0185efd5e0f01d853e95ec89bc4ab45c05abc5086` |
| `KMRP-OriginalHD-MenuMedium.otf` | 34,004 | 1000 | 218 | `fdbc94946b606ee7e1b9aa55997d6845c8441ad3aaa8f2f01d1514087f507a3a` |
| `KMRP-OriginalHD-MenuSmall.otf` | 32,052 | 1000 | 218 | `33e8b0638cc02d4652e01eb5e06d4fa2cebc7bb81f1463f28e0ada704c8537b2` |
| `KMRP-OriginalHD-MenuSmallB.otf` | 33,740 | 1000 | 218 | `88a20c7f5a453445f41ba14f0ceb27b2a1308ffe4e2a92ee766906bd034be8ae` |
| `KMRP-OriginalHD.ttc` | 601,936 | 1000 | 11 fonts | `94e9886a828a93a0346da2bf1f4dd033a0e7b2d974bca0a5623284fe5399d198` |

Which file is which game font:

| File | In the game | Text |
| --- | --- | --- |
| Menu | dialogfont16x16, dialogfont16x16b | screen titles, menu buttons |
| MenuSmall | dialogfont10x10, 10x10a, 16x16a | option lists, small labels |
| MenuSmallB | dialogfont10x10b | tabs, small bold labels |
| MenuMedium | dialogfont12x16 | save and load lists |
| MenuLarge | dialogfont32x32 | the largest headings |
| Dialogue | fnt_d16x16, fnt_d10x10b | conversations, subtitles |
| Descriptions | fnt_d16x16b | reply choices, descriptions |
| Light | fnt_d16x16a, fnt_creditsa, fnt_dialog16x16 | the journal, longer reading |
| Console | fnt_console | the HUD's numbers (the game adds a black ring; not in the file) |
| Credits | fnt_credits | job titles in the end credits |
| CreditsBold | fnt_creditsb | names in the end credits |

Built to the OpenType recommendations for CFF fonts ([Microsoft](https://learn.microsoft.com/en-us/typography/opentype/spec/recom),
[SIL's Font Development Best Practices](https://silnrsi.github.io/FDBP/en-US/OpenType.html),
[Adobe's MakeOTF guide](http://adobe-type-tools.github.io/afdko/MakeOTFUserGuide.html)):

| Rule | In these files |
| --- | --- |
| Units per em | 1000, the CFF FontMatrix exactly 1/1000 |
| Outlines | outer contours counter-clockwise (PostScript), overlaps removed (skia-pathops), points on whole units |
| Glyph names | production names from the Adobe Glyph List (`A`, `eacute`), `.notdef` a visible box |
| Names | Windows records only; PostScript name (ID 6) as the CFF's font name; licence (IDs 0, 13, 14), designer, vendor URL |
| OS/2 | version 4, Regular, USE_TYPO_METRICS, `fsType` 0 (no embedding restriction), Unicode and code page ranges (Windows-1252), Console declared monospaced |
| Vertical metrics | hhea = typo; win ascent and descent at least the font's highest and lowest points (Windows clips beyond them) |
| Hints | OTF: Adobe `otfautohint` 3.0.0, alignment zones and stem widths measured from each font's own H, x, O, o, p and q; TTF: ttfautohint, the whole-pixel flag set |
| Size | outlines subroutinised (`cffsubr`); the collection shares the tables that are the same |

Two glyphs are made rather than measured: MenuSmall's underscore, which sits on the
very bottom of its atlas cell and is cut to an 11-unit sliver there (TrueType hinting
rounded it away at 16 px), is a bar 38 units thick like the Menu font's; and ÿ in Light
and MenuLarge, whose game fonts have no ÿ, is their y with the two dots of their ä
centred over it. U+00A0 (no-break space) is the space.

## 2. How they were made

The reference is the HD atlas each font came from (`assets/hd-original-fonts` as it
stood before this redraw, at commit `87547b0`), 6 times the original's size. Nothing
else was opened: not the old OTFs' outlines, not any other foundry's font.

| Step | What it does | Code (`tools/`) |
| --- | --- | --- |
| Edge | Where coverage crosses one half, between pixel centres (marching squares) | `measure.py` |
| Area reading | Each crossing moved to its edge's exact position, read from the coverage as area: across a row the partial pixels of an edge sum to its position (`k + sum(1 - c)` rising, `k + sum(c)` falling). Exact for a straight edge; rows for steep edges, columns for flat ones | `refine.py` |
| Straight edges | Runs whose points lie on one least-squares line: within 2.6 units scatter, no bend beyond 0.6 units (or 0.6% of the length). A short straight edge counts only between sharp corners: in a curve it is a chord | `redraw2.py` |
| Corners | Two straight edges meet where their lines cross, if the outline between follows that corner within 3 units / sin(half the angle) (the anti-aliasing fills acute corners more), at most 8; a stroke's cut end (a short horizontal or vertical edge against a long stroke) up to 10 | `redraw2.py` |
| Curves | Cubic arcs through the measured points, the points at the extremes with horizontal or vertical handles, accepted at 0.6 units mean and 1.5 units most | `redraw2.py`, `redraw.py` |
| Rings | The rings of © and ® are exact: a circle or an axis-aligned oval, whichever the HD ring is closer to (the oval only if it fits at least 30% better and is 1% from round), both edges about one centre, four quarter arcs each | `rings.py` |
| Grid | Points on 1/80 of an atlas pixel while drawing, each arc's handles fitted again to the rounded ends; 1000 units per em in the finished files | `redraw.py` (`realize`), `finish.py` |
| Finish | The rules of section 1, hinting, subroutinising | `finish.py` |
| Collection | TrueType outlines, ttfautohint, one `.ttc` | `collection.py` |

`run.py` redraws all 11 and writes `build/fonts/redrawn`; `finish.py` writes `otf/`;
`collection.py` writes `KMRP-OriginalHD.ttc`; `check.py` compares the fonts with the
atlases (another set with `KMRP_ATLASES`); `sheet2.py` draws comparison sheets.

## 3. Measured

Against the HD atlases the fonts were drawn from (`assets/hd-original-fonts` at commit
`87547b0`; exact area coverage of every pixel of every glyph's cell, mean difference on
the ink; `KMRP_ATLASES=<those atlases> python check.py`), the traced fonts KMRP had
before (`tools/build_hd_original_otf.py`, potrace) and these:

| Font | Traced fonts | These fonts |
| --- | ---: | ---: |
| MenuLarge | 1.38% | 0.62% |
| Console | 2.85% | 0.76% |
| MenuSmallB | 2.49% | 0.84% |
| Menu | 2.39% | 0.85% |
| Dialogue, Credits, CreditsBold | 2.20% | 0.87% |
| Descriptions | 2.21% | 0.88% |
| MenuMedium | 2.97% | 1.01% |
| MenuSmall | 3.90% | 1.60% |
| Light | 3.98% | 1.61% |

Before the move to 1000 units per em the same fonts measured 0.33% to 1.41%: at 1000 a
point can sit half a unit off (a twentieth of an atlas pixel in most fonts, a tenth in
MenuLarge, whose em is 192 atlas pixels). Glyphs further from their atlas than the
traced ones were: in MenuLarge `>`, `<`, `=`, `^`, Y, Ý and ® (by 0.1 to 0.4 points; the
atlas's own anti-aliasing along long diagonals; the edge measurement was checked on
strokes rendered with exact coverage at eight angles, where it is within 0.002 units),
MenuSmall's © and ® (8.6% against 5.2%: the HD ring is 2.5 pixels thick and uneven, the
exact ring is even) and MenuSmallB's k (1.5% against 1.4%). Single pixels differ most at
corners, which the atlas softens and these draw sharp (up to about 75%), at ¤, whose
arms run off the atlas cell (96%), and at MenuSmall's underscore (made, section 1).

| Check | Result |
| --- | --- |
| fontbakery 1.1.0 `check-universal`, each file on its own | no FAIL in any of the 11 OTF and 11 TTF files; one ERROR of fontbakery's own (`opentype/monospace` reads `glyf`, which a CFF font has not) on Console's OTF |
| Windows GDI (`AddFontResourceExW`, `TextOutW`, 16 and 72 px, anti-aliased) | every character of every font draws, from the OTF files and from the collection (MenuSmall's underscore at 16 px only since it is a bar) |
| FreeType 2.12 (unhinted) against the atlases drawn from these fonts | 0.11% (MenuLarge) to 0.65% (Light) |
| `tools/build_hd_original_atlases.py` round trip | the committed atlases against these fonts: 0.01% to 0.04% |

*Corrected 2026-10-22, three times the same day.* (1) The first finished files had no
PostScript name (name ID 6) and no Regular bit, as the traced fonts before them;
Windows' font viewer refused them all ("keine gültige Schriftartendatei"), the old
traced ones too. (2) With those added, the viewer opened them but drew no letters:
Windows' CFF rasteriser left W, w and @ blank at 7680 units per em (and the viewer drops
every sample line holding one); at 1000 every character draws. The fonts were then
rebuilt to the recommendations of section 1 rather than patched. (3) MenuSmall's
underscore vanished at 16 px in the TrueType collection; it is now a bar.

Untested: how the hints look on Windows' and macOS's own renderers beyond GDI's
anti-aliased output above; the fonts in programs other than the font viewer, the save
editor and KMRP's own atlas builder.

## 4. Limits

- Windows-1252 only, as the game's fonts (218 glyphs; Console 96).
- No kerning: the game has none.
- The redraw follows the HD atlases, which were rendered from Bank Gothic Medium and
  Helvetica fitted to the game's letters (`tools/build_hd_original_fonts.py`); a
  typeface's design is not protected by copyright in the US and its protection in the
  EU has long run out for these designs, and no outline data of those fonts is in
  these files (each point was placed by the redraw over the atlas's pixels). This is
  the reasoning, not legal advice.

## 5. Not changed

- The letters' widths, spacing and baseline: the game's.
- The old traced fonts' tool, `tools/build_hd_original_otf.py`, and the atlases' first
  builder, `tools/build_hd_original_fonts.py`, stay in the repository as the record of
  how the atlases were first made; neither is part of any build now.
- `fnt_galahad14`: game art, made at build time, never a font file.

## 6. Lab record: rejected along the way (2026-10-22)

| Tried | Why not |
| --- | --- |
| Matching the traced fonts point for point | Their diagonals are potrace's stair steps from the atlas's anti-aliasing (the y in Light: 2.7 units waves every 21 units); copying them copied the defect. The maintainer: "it shouldn't be jaggy diagonals. Diagonals should be straight." |
| Smoothing the measurements (Gaussian, 0.5 to 1 pixel) | Rejected by the maintainer ("Don't do smoothing. Just redraw... Just draw one diagonal"); it also rounds small details |
| The 50% crossing alone as the edge | It ripples once per pixel along a slanted edge (about 1.5 units), as much as a gentle curve bends over 40 units, so no rule could tell a chord from a straight edge; the area reading fixed it |
| A bend allowance for every run length | Under 80 units the ripple and a curve look alike; the rule that a short straight edge sits between corners replaced it |
| Corners at a fixed 3 or 6 units | Acute corners (V's notch) are filled more by the anti-aliasing than square ones; the allowance now depends on the angle |

## 7. Verifying by hand

```bash
python fonts/tools/check.py                 # every glyph against its atlas (needs the traced fonts in build/fonts)
python tools/build_hd_original_atlases.py --check   # the atlases drawn from these fonts against the committed ones
python -m fontbakery check-universal fonts/otf/KMRP-OriginalHD-Menu.otf   # one file at a time
```

The second one is a round trip: the committed atlases are drawn from these files, so it
reports 0.01 to 0.04% (the rounding of 8-bit pixels). The tools need numpy, fontTools,
Pillow and scipy; numba makes the coverage check fast; `finish.py` needs skia-pathops,
cffsubr and Adobe's `otfautohint` (`pip install afdko`, in a Python AFDKO has wheels
for: 3.12 on 2026-10-22, not 3.14; `OTFAUTOHINT` names the program); `collection.py`
needs ttfautohint-py.
