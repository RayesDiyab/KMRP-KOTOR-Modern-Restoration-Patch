# Font and dialogue-layout scaling

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## What this is

KOTOR renders UI and dialogue text at a fixed pixel size regardless of
resolution, so it is unreadably small at 3440x1440 and above. This is a
separate workstream from the map/marker patch (`universal-resolution-math.md`).
It **is** now fully integrated into KMRP — see "Integration
status" below for the gold snapshot and hash constants involved.

Full technical detail (addresses, struct layout, byte sequences):
`reverse-engineering/font.md`. Investigation log:
`reverse-engineering/experiments/005-font-scale-investigation.md`.
Machine-readable patch specs: `reverse-engineering/patch-records/font_patch/*.json`.

## What it does

Four independent executable-side fixes, each its own standalone build script,
chained by running one against the previous script's output. **Note that fix 1
is now inert**: text sizing moved to the font atlases' own TXI metrics, so the
`.kfs` font-metric constant is permanently 1.0 and only its list-row constant
(fix 2) still does anything.

1. **Font scale** (`tools/build_font_scale_wrapper.py --scale N`). Hooks
   `CAurFont::TextOutA` and `CAurGUIStringInternal::Draw` and multiplies the
   five relevant `CAurFontInfo` fields (height, baseline, texture width,
   horizontal/vertical spacing) by `N` the first time each distinct font
   object is drawn, using a 64-slot dedup table to avoid re-scaling an
   already-scaled font on every subsequent frame. Adds a new `.kfs` PE
   section.
2. **List-row height** (bundled into the same `.kfs` section by the same
   script). Fixes a single shared list-row-setup routine
   (`0x00417992`) used by the save/load list, journal quest list, and the
   graphics resolution popup — without it, bigger text overlaps between
   rows. It has its own float, the second of the two at the start of `.kfs`
   (FILE `0x3DD004`), which the patcher writes per resolution as
   `max(1, height / 720)` -- 1.0 at 800x600, 2.0 at 3440x1440, 12.0 at
   15360x8640, read back from the installer's output on 2026-09-24. The first
   float, the font hooks' (FILE `0x3DD000`), is 1.0 in gold and in every output.
   *Corrected 2026-09-24:* this item said the row height used the same constant
   as the font hooks, true only before text sizing moved to the atlases.
3. **Dialogue letterbox** (`tools/build_letterbox_scale_wrapper.py`, no
   scale parameter — this is a resolution-geometry fix, not a text-size
   one). Vanilla sizes the dialogue letterbox bars from screen *width*,
   which produces an undersized bar at ultrawide independent of font size;
   this replaces that at 9 call sites with a height-derived formula. Adds a
   new `.klb` PE section.

4. **Word-wrap forward progress**
   (`tools/build_wrap_progress_fix.py`). The line-breaker restarts an
   unbreakable line at the position it began at, looping forever and
   exhausting memory — any enlarged font hits this via narrow, space-less
   labels. A 16-byte **in-place** replacement at `0x0045A5E0`; adds no PE
   section. Full analysis in `reverse-engineering/font-atlases.md`.

A fifth, separate fix touches a `.gui` **data** file rather than the
executable: `computer.gui`'s terminal-screen controls were shifted left of
the terminal prop's actual on-screen position (unrelated to font size — a
pre-existing gap in the gold GUI correction pass). Fixed by hand in a KOTOR
GUI editor and registered in `GOLD_GEOMETRY_TEMPLATES`
(`tools/prepare_universal_resources.py`) so the same proportional-transfer
mechanism that already carries the gold GUI corrections to all 49
resolutions now also carries this one.

## Building the patcher

The gold snapshot already contains every executable fix, and the universal
build script defaults to the current gold, v24:

```powershell
.\build_kmrp.ps1
```

To roll a *new* executable fix into the gold, run its build script against the
current gold, then update both hash constants (see "Integration status") before
rebuilding:

```powershell
python tools\build_wrap_progress_fix.py OLD_GOLD.exe NEW_GOLD.exe
```

Gold lineage (most recent last):

| Stage | SHA-256 | What it adds |
| --- | --- | --- |
| Gold (pristine) | `D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE` | map/marker patch only |
| Candidate 001 | `DEE9CF8F2A7A3837F59D1781E57045AA93CEF6A3258EA9CE9CDE041F410712F1` | + font scale (2.0x) |
| Candidate 002 | `B4C49441FEA3EF7E2239BD4C2B3FD522D8B3C00C8950D200F40527547CA3E1B5` | + list-row height |
| Candidate 003 | `CDE41D99FA2DA70C294893A4FF47EAB9A4EAE848303695C18410B3846401170C` | + dialogue letterbox |
| `swkotor_gold_v5_rows175.exe` | `3BB2F07A336C5A65C71992FCB341C2E7BFA00566EDD45E86C973E676A30222D6` | + resolution-aware list-row curve |
| `swkotor_gold_v6_wrapfix.exe` | `171D084E8F58AB40B778D97A3378B1A54E24F10EA02D2053A6A78B913318A7B8` | + word-wrap forward progress |
| `swkotor_gold_v8_stackcount.exe` | `879DBCBEAAF6ACEB22E7D95BB8D1566DA955D65B2F3AC07F8D3E08D450308AED` | + wrap guard vs LINE start, short-string guards NOPed |
| `swkotor_gold_v9_listbox.exe` | `4BC5AC6826D60A5BC02095F7D35E06D086AF743B05F35D7AA9288FDCB0D32EB7` | + listbox row-growth fix (`build_listbox_growth_fix.py`) |
| `swkotor_gold_v10_stacklabel.exe` | `8F338C0DC903989A50FA644E8EAD1E1D8F7AF395631B1289F7F311CA0AEB8AD2` | + scalable stack-count label arithmetic in `.ksc` |
| `swkotor_gold_v11_listpad.exe` | `485924D364A8A419B61076CAACD2AAC0F0115E8ECD2D27AEA29D0656FA0AAC2D` | + horizontal-only listbox padding |
| `swkotor_gold_v12_gutterside.exe` | `3556664D46BE5203923C7C1CF3752445254CBA61479619A96774DA5019758A0C` | + gutter follows the scrollbar side in both builders |
| `swkotor_gold_v13_leadingnl.exe` | `145F46FE85AF5934D6EE55C3D6BD5E54354762B5AFF3078C3875BC054EDE9C90` | + leading-newline removal when GUI text is assigned |
| `swkotor_gold_v14_minimap.exe` | `1F1684A5DC8BC440B2C8FF0194873315EDD39DE1C1039CB2E73861A4B3732504` | + HUD minimap zoom (`.kmz`) and fog-grid zoom (`.kfg`) |
| `swkotor_gold_v15_popup.exe` | `79356D1A92637C1B5C619B530FDA742A622A330E19AD628DBA19464202425048` | + message-popup caps and icon rect (in-place, adds no section) |
| `swkotor_gold_v18_markers.exe` | `0AA1A76D0A98F84D16CD7F5B9C183501B9CA06E8C92E063223DEC6C46C9E47AE` | + area map marker sizes and centring, all 14 sites (in-place) |
| `swkotor_gold_v19_areafog.exe` | `D4D4B793F333732D31FBD6D1C66778D527CD15D0DE20894DAC25E88132943A1E` | + area map fog grid stepped by the live surface size (in-place) |
| `swkotor_gold_v20_hittest.exe` | `ACD521B80E48B4D5A0CA043187C2D21BA1745E299D7FDD5CBA7514D525A24713` | + area map hit test centred on the overlay, not the canvas (in-place) |
| `swkotor_gold_v21_mapnotes.exe` | `9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC` | + optional map-note lookup and correction data in `.kmn` |
| **`swkotor_gold_v22_laa.exe`** | `7863BCE3BDDAC279B6A14FEB2412D38572CF94D22D6E0D8EC869D491B7EFCDE8` | + `IMAGE_FILE_LARGE_ADDRESS_AWARE` at PE file offset `0x926` |
| `swkotor_gold_v23_movies.exe` | `29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8` | + both full-screen movie display-mode pairs |
| **`swkotor_gold_v24_movieaspect.exe`** | `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A` | + aspect-fit Bink scaling (`.kmv`), replacing width-only scaling |

`Override/computer.gui` on the live install is also already the corrected
version (also copied into `assets/override-3440x1440/computer.gui`).

## Integration status — all shipped (superseded the old "not integrated" warning)

Every executable hook in this document **is** now part of the Universal
Patcher's gold delta. The gold reference continued through the listbox,
stack-label, gutter, and leading-newline investigations:

| snapshot | sections | contains |
| --- | --- | --- |
| `swkotor_gold_final_D8F0EEBF.exe` | `.kui` | map/marker only — **obsolete, do not build against it** |
| `swkotor_gold_v5_rows175.exe` | `.kui .klb .kfs` | + letterbox, font scale, list-row |
| `swkotor_gold_v6_wrapfix.exe` | `.kui .klb .kfs` | + word-wrap fix (in-place, adds no section) |
| `swkotor_gold_v9_listbox.exe` | `.kui .klb .kfs .kwl` | + stack-count guards, + listbox row-growth fix |
| `swkotor_gold_v10_stacklabel.exe` | `.kui .klb .kfs .kwl .ksc` | + unbounded stack-label geometry |
| `swkotor_gold_v11_listpad.exe` | previous + in-place edits | + horizontal-only listbox padding |
| `swkotor_gold_v12_gutterside.exe` | previous + `.kgs` | + scrollbar-side-aware gutter |
| `swkotor_gold_v13_leadingnl.exe` | previous + `.ktn` | + leading-newline removal |
| `swkotor_gold_v14_minimap.exe` | previous + `.kmz` `.kfg` | + minimap content zoom, + fog grid matched to it |
| `swkotor_gold_v15_popup.exe` | previous + in-place edits | + message-popup auto-fit caps and icon rect |
| `swkotor_gold_v18_markers.exe` | previous + in-place edits | + map marker sizes and centring |
| `swkotor_gold_v19_areafog.exe` | previous + in-place edits | + area map fog grid spans the whole map surface |
| `swkotor_gold_v20_hittest.exe` | previous + in-place edits | + map clicks land where you point |
| `swkotor_gold_v21_mapnotes.exe` | previous + `.kmn` | + optional map-note corrections |
| **`swkotor_gold_v22_laa.exe`** | previous + one PE-header bit | + Large Address Aware / 4 GB support |
| `swkotor_gold_v23_movies.exe` | previous + four in-place operands | + selected-resolution full-screen movie mode |
| **`swkotor_gold_v24_movieaspect.exe`** | previous + `.kmv` | + aspect-fit Bink scaling |

Current gold: `swkotor_gold_v24_movieaspect.exe`, 4,087,808 bytes,
`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`.
*Corrected 2026-10-01:* `build_kmrp.ps1` no longer reads that file;
[the Windows engine recipe](windows-engine-source.md) builds from source. Still confirm any
future gold change by matching `GoldPatch.TargetHash` in
`src/patcher/KmrpPatcher.cs` against the file on disk. (*Corrected 2026-09-24:*
this said v23, and the table stopped there.)

Changing the gold means updating its identity in four places together, or the
build fails: `TargetHash` and `TargetLength` in `KmrpPatcher.cs`,
`EXPECTED_GOLD_SHA256` in `tools/generate_gold_delta.py`, and `-GoldExe` in
`build_kmrp.ps1`. The guard in `generate_gold_delta.py` is deliberate — it is
what catches a stale or unexpected gold, and it did.

A live install's hash will not match the gold: the patcher writes
per-resolution constants on top, so `live = gold + ResolutionPatch`.

**Font sizing no longer uses the runtime `--scale` constant.** It rides on the
atlases' TXI metrics per resolution, via `font_scale_for(height) =
max(1.0, height/720)` in `prepare_universal_resources.py`, mirrored by
`ResolutionPatch.ScaleForHeight` in `KmrpPatcher.cs` for list-row
heights. The `.kfs` section's font-metric constant is permanently 1.0; its
list-row constant is still live. **Both copies of that formula must change
together.**

### Regenerating the font assets

Baking the atlases is a manual step, not run by the build. Two kinds:

- **The per-resolution sets** that ship, one per scale, from
  `tools/build_font_scale_sets.py` into the gitignored `build/fonts` (24
  folders on 2026-09-24; the 12.0 one is empty, see *The one resolution that
  still resamples* below). `build_kmrp.ps1` passes that folder to the resource
  build when it exists and warns when it does not:

  ```powershell
  python tools\build_font_scale_sets.py build-inputs\swpc_tex_gui.erf build\fonts
  ```

- **The shared 3.0 bake** in `assets/hd-fonts`, committed, which ships only
  where no set exists -- 15360x8640:

  ```powershell
  python tools\build_font_from_ttf.py assets\fonts\OldRepublic.ttf   build-inputs\swpc_tex_gui.erf assets\hd-fonts --fonts <the 17 menu resrefs> --scale 3.0
  python tools\build_font_from_ttf.py assets\fonts\Arimo-Medium.ttf build-inputs\swpc_tex_gui.erf assets\hd-fonts --fonts fnt_d16x16b --scale 2.526316
  ```

(The texture pack now lives in `build-inputs/`; these commands used to point
at `..\TexturePacks\`.)

Note the two DIFFERENT scales. `fnt_d16x16b`'s `2.526316` is `3.0 x 16/19`,
cancelling vanilla's 19px-vs-16px size difference so descriptions and menus
match. **Baking it at plain 3.0 silently restores that mismatch.**

Rendered letter spacing is fixed at bake time, in the glyph cell widths. The
`spacingR` metric is drawn after every glyph but hardly counted when lines are
broken, so KMRP's sets carry `spacingR 0`
(`reverse-engineering/font-atlases.md`, corrected 2026-10-05) and there is no
spacing table to regenerate. To adjust how tightly letters sit, change the
padding/advance logic in `build_font_from_ttf.py` and re-bake.

## Why the text looks pixelated above 720p (issue #16)

**In play, 2026-09-25:** with the per-resolution atlases, the maintainer
reported the text right at 3440x1440, the second reporter's resolution.
1080p, the first reporter's, has not been checked in play.

Two players reported aliased, pixelated text — one at 1920x1080, one at
3440x1440 — which ruled out any single scale factor being at fault. The cause is
structural, and it is in this document's own design rather than in the
rasteriser.

**The rasterisation is not the problem.** The shipped atlases are antialiased:
`dialogfont16x16.tga` is 1024x1024 with 256 distinct alpha values and 2.30% of
its texels at intermediate alpha, `dialogfont10x10.tga` 5.54%. A hard-edged
atlas would show two alpha values, not 256.

**Before the fix below, one atlas served every resolution, and it was correct
at exactly one of them.** The `.tga` files were not in the per-resolution
archives at all — they shipped once in `override-common.zip`. Only the `.txi`
travelled per resolution, and it differed in exactly three fields (the
2026-09-24 installer has no atlas in `override-common.zip` and 18 in every
resolution archive):

| Resolution | `fontheight` | `texturewidth` | declares the atlas as | true atlas |
| --- | --- | --- | --- | --- |
| 1024x576, 1280x720 | 0.16 | 3.41333 | 341 px | 1024 px |
| 1920x1080 | 0.24 | 5.12 | 512 px | 1024 px |
| 2560x1440, 3440x1440 | 0.32 | 6.82667 | 683 px | 1024 px |
| **3840x2160** | 0.48 | **10.24** | **1024 px** | **1024 px** |
| 7680x4320 | 0.96 | 20.48 | 2048 px | 1024 px |

Every glyph coordinate is **identical at every resolution**. `texturewidth * 100`
is what turns normalised coordinates into texels, and it equals the atlas's real
width at 3840x2160 and nowhere else. `assets/hd-fonts` was baked at `--scale 3.0`,
so **2160p is the one resolution that renders one texel per pixel**. Everything
below it minifies the same atlas; everything above magnifies it.

And the minification is unfiltered. Every font `.txi` carries:

```text
mipmap 0
filter 0
```

So shrinking is point-sampled: texels are dropped rather than blended, which
throws away the antialiasing the atlas does have. 1080p drops every other texel
(2:1); 1440p is worse because 1.5:1 drops them unevenly, which is what makes
strokes look ragged rather than merely soft. That is why the two reports came
from 1080p and 1440p ultrawide while the developer's own testing nearer 3x
looked crisp.

### The fix: one atlas set per scale

The typeface does not change. `OldRepublic.ttf` still renders the 17 menu
resrefs and Arimo Medium still renders `fnt_d16x16b`; these are the same faces,
baked more than once.

`tools/build_font_scale_sets.py` bakes a complete set at every scale the
shipped resolutions ask for, keeping Arimo's 2.526316/3.0 ratio so the two faces
stay the same size on screen. `prepare_universal_resources.py` takes
`--font-scale-sets` and, for a resolution whose scale has a set, ships those
atlases **in that resolution's own archive** and writes their metrics with a
factor of exactly 1.0. `texturewidth * 100` is then the atlas's real width, so
the engine draws one texel per pixel and nothing is resampled — neither the
point-sampled minification that made 1080p and 1440p ragged, nor the
magnification above 2160p.

`testing/regression/Test-FontAtlasScale.py` asserts that invariant directly, per
font and per resolution, rather than trusting the build to have picked the right
set.

**Atlases now ship only in the per-resolution archives**, never in
`override-common.zip`. The first attempt left the shared 3.0 bake there for the
one resolution with no set of its own, and the installer refused the build
outright: *"Two interface archives disagree about dialogfont10x10.tga."* That
guard is right — a file present in both archives with different contents has no
defined winner — so a resolution without a matched set now carries its own copy
of the shared bake instead.

**What it costs.** The first estimate here projected from texture area and said
108 MB. That was wrong by about six times: the art is thin strokes on mostly
empty textures, so stored size grows with roughly `scale^1.3`. Measured, as
deflate-compressed bytes:

| scale | raw | stored | | scale | raw | stored |
| --- | --- | --- | --- | --- | --- | --- |
| 1.0 | 9.9 MB | 219 KB | | 2.5 | 42.2 MB | 611 KB |
| 1.5 | 18.2 MB | 354 KB | | 3.0 | 66.2 MB | 770 KB |
| 2.0 | 27.2 MB | 453 KB | | 4.0 | 84.2 MB | 1018 KB |
| 2.22 | 36.2 MB | 536 KB | | 6.4 | 264.2 MB | 1901 KB |

23 sets total 15.2 MB stored, from 1.4 GB raw. The cache lives in `build/fonts`,
which is gitignored; the build passes it when it exists and warns loudly when it
does not, because silently falling back is exactly the defect being fixed.

**The one resolution that still resamples.** 15360x8640 asks for scale 12.0, and
`dialogfont32x32` at that scale needs an atlas past what the baker can produce,
so that resolution alone keeps the shared 3.0 atlas. It is listed as a known
fallback in the regression rather than hidden.

On 2026-10-01, regenerating the current 41 requested scales on Ubuntu baked
40 sets and then failed at scale 12 because the underlying baker accepts only
0.5 through 8.0. The cache builder now reports that known fallback and skips its
bake, so the documented command succeeds. The scale-12 resolution still uses
the shared atlas; no claim of native scale-12 rendering is added.

**Rejected on the way.** Replacing Old Republic with a trace of the game's own
32px master (`tools/build_kotor_font.py`) was built and measured — the trace
reproduces the vanilla letterforms, and against the master Old Republic runs
0.934x width-for-height, 1.039x stroke density, and within 1.5% on advances for
letters and digits. It was rejected on looks. So was a hybrid keeping Old
Republic's letters and substituting vanilla punctuation. Neither ships; the
shipped face is unchanged.

## Validation status

- **Play-tested on a CLEAN install at 3440x1440** through the gold-v13
  workstream:
  a fresh retail game patched end-to-end, all screens confirmed working.
  Specifically re-verified after the listbox growth fix, because it touches code
  shared by every list: **save/load, journal, inventory and messages unchanged**,
  and Powers/Feats rows now stable across repeated tab clicks.
- **Play-tested and confirmed at 3440x1440**: the word-wrap crash fix (Inventory
  opens on the item that previously crashed the game), crisp menu and dialogue
  text, matched description/menu sizes, dialogue subtitles and reply lists,
  message log, skills and inventory panels; the description-box gutter; and
  scaled rows/icons on the inventory, abilities, store and powers/feats lists.
- **Play-tested at 3440x1440 (earlier gold)**: font scale, list-row height,
  dialogue letterbox, `computer.gui` positioning — see
  `reverse-engineering/experiments/005-font-scale-investigation.md`.
- **Verified by measurement against the shipped archives**, not assumed:
  - Every embedded resource appears **byte-verbatim** in the built `.exe`.
    That was measured before 2026-09-25. Since then the per-resolution
    archives are embedded as one pool, so they no longer appear verbatim;
    `Test-InstalledOverride.ps1` compares what the installer writes with them
    instead.
  - Each of the 18 atlases was matched back to the typeface it was rendered
    from by extracting glyphs and diffing against candidate renders —
    17 → Old Republic, `fnt_d16x16b` → Arimo Medium, all zero-pixel exact.
  - **0 of 94** glyphs clipped at their cell edge in either font, on either
    side — including glyphs whose ink starts left of the pen origin.
  - (Removed: an earlier gap/ink "letter spacing" figure here was produced by a
    simulation of the spacing between glyphs, not from the game. See
    `reverse-engineering/font-atlases.md` for what `spacingR` does.)
  - Description and menu text render at identical heights at 1080p, 1440p,
    3440x1440 and 2160p.
  - Per-resolution scale: 720p 1.00x, 1080p 1.50x, 1440p 2.00x, 2160p 3.00x.

**Reusable check when touching fonts:** rasterise the TTF at the atlas's own
glyph height and diff every glyph against the atlas. Zero difference means the
shipped bitmaps really came from the font you think. Two separate bugs (the
left-side-bearing shift and the clipped ink) were caught only because this
check returned "not exact" and that was chased rather than shrugged at.
- **Item stack-count numbers**: fixed — the label is built in the inventory
  row's `SetRect`, bottom-right-aligned inside the icon box, and now scales
  with it. See `reverse-engineering/font-atlases.md`.
- **Not checked at all**: resolutions other than the spot-checks above;
  `computercamera.gui`'s positioning.
