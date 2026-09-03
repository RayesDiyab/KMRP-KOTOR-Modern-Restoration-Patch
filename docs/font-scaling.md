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
   rows. Scaled by the *same* embedded constant as the font hooks, so it's
   always proportional to whatever scale factor is chosen; there is no
   separate value to keep in sync.
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
mechanism that already carries the gold GUI corrections to all 48
resolutions now also carries this one.

## Building the patcher

The gold snapshot already contains every executable fix, and the universal
build script defaults to the current gold-v13 file:

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
| **`swkotor_gold_v20_hittest.exe`** | `ACD521B80E48B4D5A0CA043187C2D21BA1745E299D7FDD5CBA7514D525A24713` | + area map hit test centred on the overlay, not the canvas (in-place) |

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
| **`swkotor_gold_v20_hittest.exe`** | previous + in-place edits | + map clicks land where you point |

Current gold: `swkotor_gold_v20_hittest.exe`,
`ACD521B80E48B4D5A0CA043187C2D21BA1745E299D7FDD5CBA7514D525A24713`.
`build_kmrp.ps1` now defaults to that file. Still confirm any
future gold change by matching `GoldPatch.TargetHash` in
`src/patcher/KmrpPatcher.cs` against the file on disk.

Changing the gold requires updating **two** hash constants together or the
build fails: `TargetHash` in `KmrpPatcher.cs` and
`EXPECTED_GOLD_SHA256` in `tools/generate_gold_delta.py`. The latter's guard is
deliberate — it is what catches a stale or unexpected gold, and it did.

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

Baking the atlases is a manual step, committed rather than run by the build
(the build must stay pure-stdlib — Pillow installed from Bash is invisible to
the PowerShell interpreter that `build_kmrp.ps1` uses):

```powershell
python tools\build_font_from_ttf.py assets\fonts\OldRepublic.ttf   ..\TexturePacks\swpc_tex_gui.erf assets\hd-fonts --fonts <the 17 menu resrefs> --scale 3.0
python tools\build_font_from_ttf.py assets\fonts\Arimo-Medium.ttf ..\TexturePacks\swpc_tex_gui.erf assets\hd-fonts --fonts fnt_d16x16b --scale 2.526316
```

Note the two DIFFERENT scales. `fnt_d16x16b`'s `2.526316` is `3.0 x 16/19`,
cancelling vanilla's 19px-vs-16px size difference so descriptions and menus
match. **Baking it at plain 3.0 silently restores that mismatch.**

Rendered letter spacing is fixed at bake time, in the glyph cell widths — the
`spacingR` metric is **not** a typographic control (see below), so there is no
spacing table to regenerate. To adjust how tightly letters sit, change the
padding/advance logic in `build_font_from_ttf.py` and re-bake.

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
  - Each of the 18 atlases was matched back to the typeface it was rendered
    from by extracting glyphs and diffing against candidate renders —
    17 → Old Republic, `fnt_d16x16b` → Arimo Medium, all zero-pixel exact.
  - **0 of 94** glyphs clipped at their cell edge in either font, on either
    side — including glyphs whose ink starts left of the pen origin.
  - (Removed: an earlier gap/ink "letter spacing" figure here was produced by a
    simulation that fed `spacingR` into the glyph advance. The renderer does not
    read `spacingR` at all — see `reverse-engineering/font-atlases.md` — so the
    number measured the model, not the game.)
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
