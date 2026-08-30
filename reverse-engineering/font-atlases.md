# Font Atlas System Reference

Covers the HD font work that followed the TXI-metric font-scaling fix in
`font.md`: what the 18 font atlases in `TexturePacks/swpc_tex_gui.erf` are,
how the format actually works (established by measurement, not
documentation — none exists), and which screen each resref renders. Written
so this doesn't need re-discovering next session.

## The 18 font resrefs

All live in `TexturePacks/swpc_tex_gui.erf` (`FONT_RESREFS` in
`tools/build_scaled_fonts.py` is the canonical list). Confirmed exhaustive:
searched every `TXI`-type and `TPC`-type resource across the whole
installation (chitin + all ERFs) for the `numchars` marker that identifies a
font atlas — no others exist anywhere in the game.

| Resref | Stock atlas | Stock glyph height | Notes |
| --- | --- | --- | --- |
| `dialogfont10x10` | 256x256 | 10px | |
| `dialogfont10x10a` | 256x256 | 10px | |
| `dialogfont10x10b` | 256x256 | 16px | |
| `dialogfont12x16` | 256x256 | 12px | |
| `dialogfont16x16` | 256x256 | 16px | **Hardcoded engine default** — see below |
| `dialogfont16x16a` | 256x256 | 10px | |
| `dialogfont16x16b` | 256x256 | 16px | |
| `dialogfont32x32` | 512x512 | 32px | |
| `fnt_console` | 128x128 | 16px | Hardcoded string ref (debug console, unconfirmed) |
| `fnt_credits` | 512x512 | 19px | Hardcoded string ref (credits screen, confirmed prior session via `"fnt_credits"` @ 0x0068FB16) |
| `fnt_creditsa` | 256x256 | 14px | |
| `fnt_creditsb` | 512x512 | 19px | |
| `fnt_d10x10b` | 512x512 | 10px | |
| `fnt_d16x16` | 512x512 | 10px | Hardcoded string ref (usage unconfirmed — NOT Latin-shaped when rendered, see below) |
| `fnt_d16x16a` | 256x256 | 14px | |
| `fnt_d16x16b` | 512x512 | 19px | |
| `fnt_dialog16x16` | 256x256 | 14px | Name suggests dialogue family; grouped with `dialogfont16x16` pending confirmation |
| `fnt_galahad14` | 256x256 | 17px | **Not** the dialogue font — see "wrong turns" below. Uses a **packed, non-grid layout** (see Format facts) |

`fnt_galahad14` is legacy Aurora-engine naming; the real "Galahad" typeface is
a calligraphic serif, nothing like what's actually in the atlas. The resref
name is not a reliable guide to a font's role or style.

## Format facts (established by measurement)

1. **The engine renders one texel per pixel.** Glyph width on screen is the
   glyph's texel count (`(lowerright.u - upperleft.u) * texturewidth * 100`);
   glyph height is `fontheight * 100`, independent of the atlas. Confirmed by
   building an atlas 4x larger with the ORIGINAL `texturewidth` still declared:
   text came out badly horizontally stretched (measured ~2.9:1 aspect against
   a true 0.73 aspect — exactly the 4x factor). **A larger atlas therefore
   makes text physically bigger, not sharper** — there is no way to
   supersample. The only way to add sharpness is to render the outlines at
   the exact target size.
2. **`texturewidth * 100` equals the atlas's pixel width in all 18 stock
   fonts — but deliberately scaling it away from that is exactly how text is
   made bigger.** Advance width is `(lowerright.u - upperleft.u) *
   texturewidth * 100`, so multiplying `texturewidth` and `fontheight` by the
   same factor scales the text uniformly. The shipped build does this on every
   font (e.g. a 256px atlas declaring 4.48 at 1.75x) and it renders correctly.
   What actually corrupts text is **coordinates that describe a different
   atlas than the one shipped** — either stock coordinates against an HD atlas
   (see the packaging bug in fact 7) or a vertically mirrored atlas (fact 6).
   Do not "fix" a texturewidth/atlas-size mismatch by forcing them equal; that
   just removes the scaling.
3. **Glyphs are NOT laid out on a uniform grid.** Most fonts use fixed square
   cells, but `fnt_galahad14` packs glyphs proportionally — 154 distinct `u`
   positions across only 8 `v` rows (19px apart, 17px boxes), no fixed column
   pitch at all. This is why an early column-count heuristic produced
   nonsense for it ("17px glyphs in 8px cells"). `tools/build_font_from_ttf.py`
   always packs its own output proportionally (assigns each glyph its actual
   rendered width, no grid assumption), which works for every font
   uniformly and wastes no atlas space.
4. **Vanilla small-caps vs true lowercase.** Measuring ink-height ratio
   (lowercase / uppercase) and descender presence: `dialogfont16x16` (and
   most of the 18) render "the quick brown fox" as pure capitals — genuinely
   small-caps in the shipped art, ratio ~0.75-0.83, zero descender pixels.
   This contradicts the look of actual gameplay dialogue (confirmed true
   lowercase with descenders from a user-supplied vanilla screenshot) — an
   unresolved discrepancy between the atlas art and how the game visually
   reads; not yet explained. Do not use "does this stock atlas have
   lowercase" as a proxy for "is this the dialogue font" — see next section.
5. **Zero *packed* `.gui` files specify an explicit `FONT` field.** Checked all
   84 packed GUI resources' controls recursively — none. Font selection for a
   control lacking `FONT` happens via a hardcoded engine default (confirmed for
   one case, see below). **The `.gui` files this project actually ships are a
   different story**: the high-resolution-menus files (and our Override copies)
   *do* carry `FONT` fields — `inventory.gui` names `dialogfont16x16` on its
   item rows and `fnt_d16x16` on `LB_DESCRIPTION`'s `PROTOITEM`. Treat a
   `FONT` field as a strong hint, **not** proof: live debugging showed the
   inventory description control resolving to `fnt_d16x16b`'s metrics
   (fontheight 0.19 / baseline 0.15) despite the GFF naming `fnt_d16x16`, so
   some substitution happens between the declared name and the loaded resource
   that is still not understood. Confirm with a live read before acting on it.
6. **A decoded TPC's first row is the image's BOTTOM.** `write_tga` reverses
   whatever it is handed (the game's TGA is bottom-up), so **its input must be
   top-down**. PIL images are top-down and work directly; passing
   `bytes(mipmap.data)` from a TPC straight through mirrors the atlas
   vertically and every glyph lookup lands on the wrong row, rendering all
   text as Aurebesh-looking gibberish. `export_fonts` flips TPC rows before
   writing. **Verify orientation by rendering, not by reasoning** — an
   "ink inside the glyph rectangles" heuristic returned 5,592 vs 5,999 for the
   two orientations (7% apart, i.e. noise) and pointed the wrong way. Print
   glyph `'A'` as ASCII art instead; only the correct combination forms a
   legible letter. See "Verifying an atlas" below.
7. **A standalone `.txi` in Override does NOT override a packed `.tpc`.** With
   the artwork still inside the `.tpc`, the engine keeps that file's embedded
   metrics and the loose `.txi` is ignored — text simply never changes size.
   The unmodified `.tga` must ship beside it for the override to win.
   (`build_scaled_fonts.export_fonts` documented the opposite for a long time,
   claiming "confirmed in game"; that claim was false and cost a full build
   cycle where every menu stayed vanilla-sized.)
8. **Glyph padding must survive downscaling.** The HD atlas is rasterised at
   the top of the scale range and filtered *down* at every smaller resolution;
   bilinear sampling reaches past a glyph's own rectangle. At 1px padding it
   pulled in the ascenders of the row below, appearing in game as stray dots
   under the text. `GLYPH_PADDING` is 4.

## Which resref renders which screen

**Confirmed via disassembly + GFF dump**, not guessed: `dialog.gui`'s
`LBL_MESSAGE` control (the conversation subtitle bar) has fields
`CONTROLTYPE, ID, Obj_Locked, Obj_Parent, TAG, Obj_ParentID, EXTENT, BORDER,
TEXT` — no `FONT` field. Two code sites (`0x00416099`, `0x004170CE` in
`swkotornopatch.exe`) push the literal string `"dialogfont16x16"`
immediately after a GFF field read whose neighbouring string constants are
`FONT`/`STRREF`/`TEXT` — i.e. this is the engine's fallback font, used
whenever a control's `FONT` field is absent. **`dialogfont16x16` is
confirmed as (at minimum) the dialogue subtitle font.**

**Wrong turns already made, so they aren't repeated:**
- `fnt_galahad14` was initially assumed to be the dialogue font because it
  measured with a subtle true-lowercase signal (+2px descender on 'g') where
  every other font measured zero. Playtest disproved this: reassigning
  `fnt_galahad14` to a different typeface had no visible effect on the
  dialogue subtitle, which still rendered in whatever the OTHER 17 fonts
  were set to. The descender measurement was likely a one-glyph artifact,
  not evidence the font is actually used for body text.
- Assuming `dialogfont16x16` was used ONLY for dialogue was also wrong.
  Reassigning the full `dialogfont*` + `fnt_dialog16x16` family to one
  typeface and everything else to another (`fnt_galahad14`, credits,
  console, `fnt_d16x16` family) still left MANY non-dialogue screens
  (options menu list items, skills list items, inventory item names)
  rendering in the "dialogue" typeface, AND the skill/item description
  panel rendering in the "everything else" typeface — the reverse of what
  was intended. **So `dialogfont16x16` (or a sibling) is also the fallback
  for many generic list/menu labels, not exclusively conversation text** —
  consistent with it being a single engine-wide "no FONT field" default
  rather than a dialogue-specific assignment.

**CONFIRMED, sourced from a working third-party mod** rather than our own
diagnostic (the diagnostic screenshots showed none of our 4 placeholder
typefaces rendering, before it could return a result — superseded by this
better source): Deadly Stream's ["Larger Text Fonts for
KOTOR"](https://deadlystream.com/files/file/1891-larger-text-fonts-for-kotor/)
(by SovietShipGirl/Xela) ships pre-sized replacements for exactly three
resrefs, organised into three named categories per its own README ("Dialogue
is used for dialogue, Menu is used for the menus, and Names are used for
names"):

| Category | Resref(s) | Confirmed role |
| --- | --- | --- |
| Dialogue + Description | `fnt_d16x16b` | Conversation subtitle bar AND item/skill/power description panels — **the one resref that should get a true-lowercase readable typeface.** Verified directly: rendered the mod's own shipped `fnt_d16x16b.tga` (from its "VeryBig" tier) and got clean, correctly-spaced genuine lowercase ("the quick brown fox jumps") — this is a real different typeface in the mod, not small-caps. |
| Menu | `dialogfont16x16`, `dialogfont16x16b` | Main menu, options, skills/powers/feats list items, inventory item names — i.e. most generic UI labels. **Confirmed NOT dialogue-specific**, despite the name — this is what made earlier "assign the whole dialogfont* family to a readable font" attempts fail (menus and inventory came out in the wrong typeface as a direct result). |
| Names | `dialogfont10x10b` | NPC name label shown when targeting/selecting an NPC. |

The mod also ships two resrefs that are **not real base-game resources** —
confirmed absent from the exhaustive whole-installation `numchars` search
above, and absent as hardcoded ASCII strings in the executable:
`savefont16x16b` (paired with a resized `saveload_p.gui`, for the save/load
list specifically) and `pfont16x16b` ("VeryBig" tier only, paired with
`skillinfo_p.gui`). Their own `_p.gui` files carry no explicit `FONT` field
either (checked directly) — so the author almost certainly found ALL of
these mappings empirically (renaming files and testing in-game), the same
way our own diagnostic test was attempting to, just faster. **These two are
speculative extras from that mod, not confirmed necessary for this
project** — not yet replicated here, since `dialogfont16x16b` (Menu) already
covers save/load and skill info adequately without them.

The remaining 14 resrefs are untouched by that mod entirely (no folder
references them), consistent with them being low-visibility (`fnt_console`
debug, `fnt_credits*` credits screen) or genuinely rare in normal play. They
default to the Menu-style authentic typeface.

**Current build** (fully wired into `prepare_universal_resources.py`): all 18
resrefs ship as HD atlases baked by `tools/build_font_from_ttf.py` into
`assets/hd-fonts`.

| resref | typeface | bake scale |
| --- | --- | --- |
| `fnt_d16x16b` — descriptions + dialogue subtitles | **Arimo Medium** (Apache; Google's metric-compatible Arial substitute) | **2.526316** |
| the other 17 — menus, item names, buttons | **Old Republic** | 3.0 |

> ⚠️ **`fnt_d16x16b`'s bake scale is deliberately not 3.0.** Vanilla sizes it
> at 19px against the menu fonts' 16px, so it rendered 19% larger than
> everything around it. `3.0 × 16/19 = 2.526316` cancels that: both bake to
> 48px and render at identical heights at every resolution. **Re-baking it
> with plain `--scale 3.0` silently restores the mismatch.**

Arimo was chosen after testing the vanilla dialogue atlas against Nimbus Sans,
Arial, Montserrat and Chakra Petch — the vanilla face is Helvetica/Arial-like
(genuine lowercase with a real descender, unlike the small-caps menu atlases),
and Arimo ships static weights, so unlike a variable font there is no instance
to pin wrong. `assets/fonts/` also keeps Arimo-SemiBold (one step heavier) and
`KOTOR_UI_Open.ttf` (the licensing fallback).

Both are TrueType, i.e. **vector outlines with no resolution of their own** —
there is nothing to "upscale" and no tracing involved. They are rasterised once
at the top of the resolution curve and scaled *down* per resolution, so every
resolution is crisp and 2160p renders at the native baked size. No stock bitmap
artwork ships any more.

`assets/fonts/KOTOR_UI_Open.ttf` — our own trace of the game's 32px master — is
**kept in the repo but no longer shipped**. It reproduces the vanilla
letterforms exactly, so it remains the fallback if Old Republic ever has to be
dropped for licensing (see below), and the section on building it stays below
for that reason.

## SOLVED — Inventory crash: engine word-wrap has no forward-progress guarantee

Enlarging any font that a **narrow, space-less** label uses crashed Inventory.
Earlier hypotheses in this file blamed listbox `PROTOITEM` row heights and were
**wrong**; so were "atlas size" and "size increase independent of packing",
each tested and disproven. The real cause was found by attaching to a running
game with a *conditional* breakpoint that fires only once the state is already
corrupt (`0x0045A69E`, condition `[esi+2C]>3E8` — the line array far past any
legitimate count), which freezes the bug mid-act instead of letting it die.

**The defect** is at `0x0045A5E0`, inside the line-breaker `0x0045A2F0`. When a
line overflows and contains no space to break on, it backs the cursor up one
character and restarts the line there, guarded only against the start of the
whole *string*:

```
0045A5E0  mov eax,[esi+14]   ; start of the STRING
0045A5E3  dec ebx
0045A5E4  cmp ebx,eax
0045A5EA  je  0045A834       ; bails only at the string start
```

Wrong reference point. The failure is an **oscillation**: a line starts at P,
accumulation advances to P+1, `w(P)+w(P+1) >= maxWidth` ends the line, no space
was seen, so the hard-break path subtracts the last character and `dec ebx`
lands back exactly on P — restart at P, forever, appending an entry each pass.
It terminates only if P is the string's first byte. Each append grows two
arrays by doubling until the allocator fails; the grow helper at `0x005E03C0`
never checks its result, so the game dies writing through NULL. Observed live:
33.5 million entries, a 268MB request, then the crash.

**Why any enlargement triggers it — vanilla's margin is ONE pixel.** The
crashing control was not the description box (718x250) but the item
**stack-count label**, measured live at **21px wide**, whose text is a bare
number and so never contains a space:

| | stock | 1.25x |
| --- | --- | --- |
| widest digit | 10px | 11px |
| **widest two-digit pair** | **20px** | **22px** |
| control width | 21px | 21px |
| digit pairs overflowing | **0/100** | **55/100** |

`"159"`: stock `5+9 = 19` fits; enlarged `5+9 = 22` does not. **This is not
fixable from the font side** — do not chase it in the generator again.

**The fix**: `tools/build_wrap_progress_fix.py`, an in-place, exactly-16-byte
replacement — no new PE section, no trampoline. It compares against the current
*line's* start (`[esp+18]`) instead of the string's, and snaps the cursor to
`lineStart+1` when a line would make no progress, so the line start rises
monotonically and the loop always terminates:

```
4B            dec ebx
3B 5C 24 18   cmp ebx,[esp+18]    ; the current LINE's start
89 4C 24 10   mov [esp+10],ecx    ; original side effect, preserved
77 05         ja  +5
8B 5C 24 18   mov ebx,[esp+18]
43            inc ebx             ; -> lineStart + 1
```

Deliberately *not* the engine's own bail at `0x0045A834`, which zeroes both
entry counts and makes `Draw` render nothing. `eax` (loaded by the original,
unused here) is dead — `0x0045A5F0` immediately overwrites it. Playtest
confirmed: Inventory opens, descriptions render enlarged.

**A cautionary note on the first attempt.** An earlier patch tried to clamp the
*requested* capacity in the grow helper to 4096. That was actively dangerous:
the copy loop's bound is the *old* count (~33M), which the clamp did not touch,
turning a clean NULL dereference into a 33-million-element write into a
4096-element buffer. The game then crashed at the loading screen. **When
patching a grow/copy helper, clamp the copy bound and the capacity together or
not at all.**

**Still open — stack counts disappear when scaled.** The 21x19 label exists in
no `.gui` file (every 1080p GUI scanned; nothing under 60x40 matches), so it is
built in engine code and cannot be widened by editing geometry. At 1.75x its
glyphs are ~33px inside a fixed 19px label, so it clips away regardless of
wrapping. Fixing it needs either locating where that label is constructed and
scaling its extent, or a wrap patch that renders the run unwrapped/overflowing
instead of breaking it.

## Verifying an atlas

Never trust reasoning about orientation or coordinates — render a glyph and
look at it. Read the `.tga`, remember the file is bottom-up so
`rows = [...][::-1]` gives `rows[0]` = top, then for character `c`:

```
x0,x1 = UL[c].u * W,        LR[c].u * W
y0,y1 = (1 - UL[c].v) * H,  (1 - LR[c].v) * H
```

and print `'#'` where alpha > 110. If it does not look like the letter, the
atlas or the coordinates are wrong. This single check would have caught both
the mirrored-atlas bug and the clobbered-metrics bug immediately.

## Tooling

- `tools/build_scaled_fonts.py` — exports stock atlases (optionally
  unmodified art, metrics-only) with the five TXI metric fields multiplied
  by a scale factor. `raw_txi()` recovers the TXI as the trailing
  printable-ASCII block of the TPC resource, since pykotor's own TXI parser
  silently drops fields it doesn't model (e.g. `compresstexture`) and
  reorders others — diffing against pykotor's own re-parse of the original
  hid this for a long time; always diff against the raw bytes.
- `tools/build_font_from_ttf.py` — renders a genuinely new atlas from a
  TrueType font at a given render scale. An open reimplementation of the old
  closed "KOTOR Font Tool (NWN Font Maker)" written against the measured
  format above, not against that tool. Two rules it enforces, both learned the
  hard way: every one of the 256 slots gets a **non-zero** advance (falling
  back to the stock atlas's own width for characters the TrueType face has no
  advance for — stock fonts have no zero-width slot anywhere, narrowest 4px);
  glyphs are padded by 4px so downscale filtering cannot pull in the row below;
  and **the cell is widened to contain ink that escapes on either side**. In
  this format a glyph's cell width *is* its advance — there is no side bearing
  to overhang into — so anything outside is sliced off. Typefaces spill both
  ways: `f w y V` overhang right, and `j w ( Y` start **left of the pen
  origin**. Both are handled, the left case by nudging the glyph right as well
  as widening. Verified 0/94 clipped for both shipped fonts.
- **Bake high, scale down.** `assets/hd-fonts` is rendered at `--scale 2.75`,
  the top of the resolution curve (52px glyphs in 1024x1024, 4MB), and
  `prepare_universal_resources.py` divides by `HD_FONT_BAKE_SCALE` so every
  resolution scales it *down*. The engine draws one texel per pixel, so an
  atlas stretched past the size it was rasterised at is simply blurry — this
  keeps 2160p pixel-exact and everything below crisp. It also replaced a
  2048x2048/16MB atlas that held 19px glyphs. **If the bake scale changes,
  `HD_FONT_BAKE_SCALE` must change with it** or the enlargement is applied
  twice.
- `tools/build_wrap_progress_fix.py` — the 16-byte in-place engine fix for the
  word-wrap crash described above.
- `tools/build_hd_fonts.py` — superseded. AI-upscales the stock bitmaps
  (Lanczos + smoothstep edge correction); rejected by the user as visibly
  soft/blobby compared to true vector rendering. Kept for reference only.

## Recreating the KOTOR UI typeface (`tools/build_kotor_font.py`)

Shipping vanilla artwork keeps the authentic letterforms but leaves menus
visibly blocky: `dialogfont16x16` rasterises at **16px** and gets stretched to
20px at 1080p, 28px at 1440p, 44px at 2160p. Bitmaps cannot be sharpened after
the fact, so the letterforms had to become outlines.

**The master is `dialogfont32x32`** — the same typeface at **32px** (512 atlas,
255 chars), double the resolution of the atlas the menus actually use. Check
every resref's `fontheight` before assuming the size in front of you is the
best the game ships; this one is easy to miss.

The trace exploits the design being geometric. Each glyph's filled pixels are
converted to their exact boundary polygon — every pixel contributes the edges
facing an empty neighbour, chained into closed loops — then collinear points
are dropped and Douglas-Peucker at **0.34px** removes the staircase along
diagonals and curves while leaving straight runs exactly where they were.
Edges are emitted counter-clockwise around each filled pixel in font
coordinates, so outer contours come out CCW and enclosed counters CW: already
TrueType's non-zero winding, with no orientation fixing afterwards.
`unitsPerEm` is 1024 with ascent + descent equal to exactly one em (split taken
from the master's own `baselineheight`), so rendering at N pixels yields an N
pixel glyph box — what `build_font_from_ttf.py` assumes when picking a point
size.

**Verified pixel-identical to the vanilla master**: rendering the TTF at 32pt
and diffing against the 32px atlas row by row reproduces C, S and A exactly.
95 printable-ASCII glyphs, 131 contours. Output:
`assets/fonts/KOTOR_UI_Open.ttf`.

Requires `fonttools`, `numpy` and Pillow. Like `build_font_from_ttf.py` this is
a **manual asset step whose output is committed** — do not add it to the build
pipeline, which must stay pure-stdlib (see the PIL/PowerShell gotcha in
`docs/font-scaling.md`).

## Letter spacing: measured per font and scale, not modelled

Text from the shared atlas reads tighter at some sizes than others. Menu text
measured a gap/ink ratio of **0.098 at 1080p against 0.126 at 1440p** — visibly
cramped, and reported from play.

The obvious explanation — that downsampling the atlas fattens the ink and eats
the gap — is **wrong**, or at least not the whole story. Baseline ratios run
0.114 at 720p, 0.098 at 1080p, 0.126 at 1440p, 0.120 at 2160p: **not monotonic**
in how hard the atlas is downscaled. What actually varies is integer rounding of
each glyph's advance landing differently at each specific pixel size. A smooth
`f = scale / bake` curve therefore fits noise, and one that was tried overshot
hard at the small end (720p menus at **0.198** against a 0.120 target, dialogue
at 0.271).

`tools/measure_letter_spacing.py` measures instead. For every font and every one
of the 23 distinct scales the resolution list asks for, it reconstructs how the
engine will rasterise the atlas at that size, measures mean ink width and the
gap that follows, and solves for the `spacingR` that returns the ratio to that
font's own value **at the native baked size** — where nothing is resampled, so
that ratio is the typeface's true design spacing. It only ever loosens.

The answer turns out to be sparse: **only the menu font at 1080p needs anything
(0.35px)**. Everything else already sits at or above its native ratio. That is
exactly why a flat constant looked wrong — it loosened 1440p, which was already
correct.

Result is committed as `assets/letter-spacing.json` (`{resref: {scale: px}}`)
and read by `prepare_universal_resources.py`, keeping the build pure-stdlib.
`spacingR` is written **after** `scale_txi`, never through it: this is a
pixel-space correction, and scaling it with the resolution would reintroduce
the very thing it fixes.

> **Re-baking the atlases invalidates the table.** Re-run
> `measure_letter_spacing.py` afterwards. The build fails with an explicit
> message if `letter-spacing.json` is missing rather than silently shipping
> zeros.

### Hand-refining the font (the intended finishing step)

Automated tracing rounds the steps convincingly but cannot invent the curve the
original designer would have drawn — it only approximates what the pixels
imply. `assets/fonts/KOTOR_UI_Open.ttf` is therefore a **starting point meant to
be hand-refined and committed in that refined state**.

> **Re-running `build_kotor_font.py` overwrites that file and destroys any hand
> editing.** To regenerate only the automated base, write it somewhere else:
> `python tools/build_kotor_font.py ERF /tmp/base.ttf`.

Nothing downstream re-derives the font — `build_font_from_ttf.py` reads whatever
TTF it is pointed at — so a hand-edited file flows into the atlases with no code
changes. Workflow:

1. Open `assets/fonts/KOTOR_UI_Open.ttf` in FontForge (free; Glyphr Studio is a
   browser-based alternative).
2. `tools/export_glyph_templates.py` writes one PNG per glyph to
   `assets/fonts/glyph-templates/`, each exactly one em tall with the glyph
   already positioned on its baseline and advance, plus a contact sheet. In
   FontForge: open a glyph, `File > Import`, select the PNG, choose **as
   background**, then draw over it and remove the background when finished.
   Because the template is pre-positioned, a drawing traced over it lands on the
   correct baseline and advance with no further nudging.
3. Export the TTF back over `assets/fonts/KOTOR_UI_Open.ttf`.
4. Rebuild — `build_font_from_ttf.py` bakes the atlases from it automatically.

Drawing the letterforms rather than tracing them also produces original artwork,
which materially weakens the provenance concern discussed under Licensing.

## Licensing note

The shipped build embeds two typefaces: **Arimo Medium** (Apache 2.0) for
`fnt_d16x16b`, and **Old Republic** for the other 17 resrefs. Full attribution
in `THIRD_PARTY_NOTICES.md`.

**Old Republic is marked "free for personal use only"** (dafont, by Trollax
Kinora), and its author notes it is "a reproduction of the font from the Lucas
Arts game, Knights of the Old Republic II ... made ... from screens of the
game", adding that because it is "designed after the intellectual property of
someone else it will never be released as anything other than for personal
use." A permission request was sent and is not expected to be answered — the
rights in question are not the author's to grant.

**Decision taken: ship it in the patcher, and remove it if Lucasfilm objects.**
The reasoning, recorded so it is not re-argued:

- **No font file is distributed.** Verified across every embedded archive: the
  patcher carries the gold delta, `override-common.zip`, 48 `gui-*.zip`,
  `resolutions.tsv` and a license text — zero `.ttf`/`.otf`. The TTFs under
  `assets/fonts/` are build-time inputs only; users receive **rendered TGA
  atlases**. Bundling is therefore not redistribution of font software.
- The residual question is the LucasArts IP, which the atlases inherit
  regardless of which typeface rendered them — **`KOTOR_UI_Open.ttf` is not a
  cleaner alternative**, being traced from KOTOR 1's own atlas. It is a
  *typographic* fallback, not a licensing one.
- The patcher already requires owning the game, and ships modified game assets
  throughout, as KOTOR mods generally do.

If it ever has to go, swapping the 17 menu resrefs to `KOTOR_UI_Open.ttf` is a
one-line change to the `--fonts` invocation. For a genuinely clean public
release the route is generating the atlases from the user's own installed game
files at patch time, so nothing derived is redistributed — not designed or
costed.

**Provenance, and the decision taken.** KOTOR UI Open's outlines are traced
from BioWare's shipped bitmaps. Typeface *designs* are generally not
copyrightable in the US (font *software* is, and design rights do exist in some
other jurisdictions), but a trace is still derived from their artwork.

**Decided: the TTF ships only inside the patcher and will not be released
standalone.** That keeps it in the same position as the `assets/override-*`
artwork this project already redistributes — it only reaches people who already
own the game. `assets/fonts/KOTOR_UI_Open.ttf` is a build input, not a
deliverable. If that ever changes, the standalone question reopens and the
honest answer is that the outlines would need redrawing rather than tracing.

"Old Republic" (dafont, by Trollax Kinora) is **"free for personal use only"**
and is **not** used by the shipped build. It was evaluated earlier when the
plan was to restyle all 18 resrefs; if it is ever reintroduced it would again
block public distribution without the author's permission. Other SIL-OFL
candidates fetched and rendered for comparison: Rajdhani, Exo 2. "SF Old
Republic" (1001 Free Fonts) was suggested as a possible closer match but was
never fetched or verified.

Redistributing the extracted vanilla atlases is the same class of act as the
existing `assets/override-*` art this project already ships; it is noted here
only so the decision is explicit rather than accidental.
