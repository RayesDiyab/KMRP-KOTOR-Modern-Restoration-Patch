# KOTOR Universal UI & Map Patcher

The standalone universal patcher is built at `dist/KMRP.exe`.
It supports 48 selectable resolutions across 4:3, 16:10, 16:9, 21:9, and
32:9. See `docs/universal-resolution-math.md` for the executable fields,
coordinate math, GUI packaging, reproduction steps, and validation status.
See `docs/font-scaling.md` for the font/dialogue-letterbox/list-row scaling
work, which **is** part of the Universal Patcher — its "Integration status"
section covers the gold snapshot and the hash constants involved.
See `docs/patcher-ui-build.md` for the desktop UI state machine, proportional
resize implementation, supplied-icon pipeline, embedded resources, build
process, transaction safety, and release checklist.

The completed 3440×1440-only gold patcher remains frozen at
`releases/3440x1440-gold-final/KOTOR_UI_Gold_Patcher_3440x1440_FINAL.exe`.
Third-party attribution and licensing notes are in `THIRD_PARTY_NOTICES.md`.

This directory is the source workspace for the resolution-independent KOTOR UI
patcher. Phase 0 (map/marker) and the font/dialogue-layout scaling workstream
are both complete and play-test confirmed.

## Engine bugs found and fixed

Each of these was diagnosed against the executable and is now part of the
shipped gold delta. Full analysis in `reverse-engineering/font-atlases.md`;
the inventory row/icon trace has its own writeup in
`reverse-engineering/inventory-item-rows.md`.

| Symptom | Cause | Fix |
| --- | --- | --- |
| **Inventory crashes** on items with long descriptions | `CAurGUIString`'s line-breaker restarts an unbreakable line at the position it began at. Its only guard compares against the start of the *string*, not the current *line*, so it loops forever appending entries until the allocator fails, then writes through NULL. Any enlarged font trips it via the 21px stack-count label, whose text is a bare number with no space to break on — vanilla clears that label by exactly **one pixel**. | 16-byte **in-place** patch at `0x0045A5E0` comparing against the line start, plus a `.kwl` stub that consumes an unbreakable line whole and rejoins the engine at `0x0045A785` (snapping to `lineStart+1` terminates but emits one character per line, which `Draw`'s vertical centring then pushes off the control). Two short-string guards at `0x0045A3B7`/`0x0045A3DC` are NOPed with it. `tools/build_wrap_progress_fix.py` |
| Text stayed **unreadably small** at high resolutions | Vanilla renders UI text at a fixed pixel size regardless of resolution. | Per-resolution TXI metrics, `max(1.0, height/720)`. |
| Dialogue letterbox **too small at ultrawide** | Bar height derived from screen *width*. | Height-derived formula at 9 call sites (`.klb` section). |
| List rows **overlapped** with bigger text | Row height copied verbatim, never scaled. | Resolution-aware row scale (`.kfs` section). |
| Description text ran **under the scrollbar** | Two separate defects. The engine's line measurement truncates each glyph advance to an integer and so under-measures a line by ~3% (1202 vs 1238 read live), letting it clip; and vanilla left the listbox `PADDING` gutter at 0 on six description panes while never scaling the small values it did set elsewhere. | `spacingR` raised to a flat 0.5px per glyph as a **wrap margin** — it feeds the line-breaker at `0x0045A5C9` but *not* the renderer at `0x0045A806`, so it costs no visible letter spacing; plus a resolution-scaled `PADDING` gutter (`tools/scale_listbox_padding.py`). |
| Inventory, Abilities and Store rows and **icons stayed vanilla-sized** | Rows and icons size from hardcoded constants in the exe (56 inventory, 42 abilities, 56 store), independent of resolution and font. `PROTOITEM`'s own `EXTENT.HEIGHT` is parsed into the control and then never used for the row, so no GUI edit can reach it. | All seven sites scaled by `max(1.0, height/720)` (`RowSizeGroups`). They are reached only by the inventory item row, so unlike the `.kfs` list-row float they cannot disturb save/load or the journal. Full trace in `reverse-engineering/inventory-item-rows.md`. |
| List rows **grew every time a list was re-populated** | `CAurGUIListBox`'s variable-height layout adds a row *count* to a row *height* (`add ebp,edx` at `0x0041B507`, where `edx` is the result of an `idiv` counting how many rows fit), then writes the inflated rect back into reused row controls that the next pass re-reads via `max(item->height)`. A **vanilla BioWare bug** — reproduced with a `.gui` byte-identical to the original. Invisible at low resolution because growth is clamped by box height; a large box lets it ratchet (measured 42 → 56 → 126 on the Powers tab). | Both inflation sites neutralised in the gold build (`tools/build_listbox_growth_fix.py`). Row positions are unaffected — they use a separate accumulator. |
| Item **stack-count numbers vanished** once the font was enlarged | The label is built in the inventory row's `SetRect` (`0x006B5270`), not in any `.gui`, and is bottom-right-aligned inside the icon box — 21x19 at a top offset of 37, where `37 + 19 = 56` is the vanilla icon size. Scaling the icon left the label behind, and the widest two-digit pair needs 22px in a 21px box. | All four constants scale with the icon (`StackCountSites`); three were imm8 operands capped at 127, so `tools/build_stack_count_fix.py` relocates that arithmetic into a `.ksc` stub with imm32 operands (gold v10) and it scales without limit. |

Bugs in this project's own tooling, fixed along the way and worth not
repeating: glyphs shifted a pixel left (left side bearing must equal the
outline's `xMin`, not 0); every stock atlas mirrored vertically (a decoded
TPC's first row is the image's *bottom*, but `write_tga` takes top-down input);
ink sliced at the cell edge on **both** sides (a glyph's cell width **is** its
advance in this format — there is no side bearing to overhang into, and glyphs
like `j`, `w`, `(`, `Y` start left of the pen origin); a scaled `.txi` alone
silently doing nothing (the `.tga` must ship beside it or the packed `.tpc`'s
embedded metrics win); and a whole letter-spacing mechanism built on a false premise (`spacingR`
feeds only the line-breaker, never the renderer — so the table that tuned it
per font and scale was silently moving wrap points and nothing else; the
cramped text it was meant to fix was actually cured by the atlas rebuild).

## Current status

- **Map/marker patch**: complete and play-test confirmed at 3440x1440,
  including the marker click-hitbox offset (fixed via a `+14` Y-axis
  hit-test correction). The Universal Patcher generalizes it to 48
  resolutions structurally; only 3440x1440 and one full 1920x1080 install
  have been play-tested end-to-end — see `docs/universal-resolution-math.md`
  for exact validation status per resolution.
- **Font scaling, list-row height, dialogue letterbox, and word-wrap
  forward progress**: four executable patches, plus a `computer.gui`
  positioning fix, **all now folded into the Universal Patcher's gold delta**
  — a fresh install gets them automatically. Text size is resolution-aware
  (`max(1.0, height/720)`: 1.00x at 720p, 1.50x at 1080p, 2.00x at
  1440p, 3.00x at 2160p) and rides on the font atlases' TXI metrics rather
  than a runtime constant. See `docs/font-scaling.md`.
- **Fonts**: all 18 atlases are rendered from vector outlines and scaled *down*
  per resolution, so text is crisp everywhere (2160p renders at the native
  baked size). Descriptions and dialogue subtitles use **Arimo Medium**
  (Apache); menus, item names and buttons use **Old Republic**. Both render at
  matched heights — vanilla makes the description font 19% larger, and that is
  deliberately cancelled. No font file is distributed: the patcher embeds only
  rendered TGA atlases, so the TTFs in `assets/fonts/` are build inputs.
  Attribution and the licensing decision on Old Republic are in
  `THIRD_PARTY_NOTICES.md` and `reverse-engineering/font-atlases.md`.
- **Item stack-count numbers**: fixed. The label is built in the inventory
  row's `SetRect` (in no `.gui` file) and is bottom-right-aligned inside the
  icon box — `37 + 19 = 56`, the vanilla icon size — so scaling the icon left it
  behind. All four of its constants now scale with the icon (`StackCountSites`),
  clamped so the three imm8 operands cannot sign-extend negative.
- The current gold snapshot is
  `build/universal-patcher/swkotor_gold_v14_minimap.exe`, SHA-256
  `1F1684A5DC8BC440B2C8FF0194873315EDD39DE1C1039CB2E73861A4B3732504`.
  The universal build script defaults to this file. Gold v14 includes the map,
  marker, font, dialogue, list-row, wrap-progress, stack-label, listbox gutter,
  scrollbar-side, and leading-newline fixes documented in
  `reverse-engineering/listbox-geometry.md`, plus the HUD minimap content zoom
  and the matching fog grid documented in `reverse-engineering/map.md`.
- The standalone Windows patcher in `dist/` embeds the verified executable
  delta, all 48 GUI archives, common Override assets, font atlases, branding,
  icons, and license notice. It creates verified backups, supports full
  EXE/INI/Override restore, and refuses unknown executables.
- This directory is now tracked in a private git repository
  (`github.com/RayesDiyab/kotor-universal-ui`).

## Build the gold patcher

```powershell
.\build_gold_patcher.ps1
```

Build the shipping 48-resolution patcher with:

```powershell
python .\tools\prepare_app_icons.py  # requires Pillow; only when source icons change
.\build_universal_patcher.ps1
```

The supported clean source SHA-256 is
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
See `app/patcher/README.md` for usage and safety behavior.

## Reproduce the confirmed marker patch

Run the self-contained builder against an executable that already contains the
known map-size patch. The requested width and height must match the existing map
render immediates; the builder verifies them before writing anything.

```powershell
python .\tools\build_map_icon_draw_wrapper.py `
  ..\swkotor_phase0_ultrawide.exe `
  ..\swkotor_phase0_icon_confirmed.exe `
  --width 1720 --height 720
```

The builder refuses in-place output, checks all original call bytes, adds the
`.kui` wrapper section, and verifies the written payload.

## Safety rules

- Never experiment on `swkotor.exe` directly.
- Use only the explicitly named `swkotor_phase0_clean.exe` and
  `swkotor_phase0_ultrawide.exe` working copies.
- Record the source SHA-256 before every experiment.
- Prefer reversible in-memory changes until behavior is understood.
- Never commit game executables or proprietary game resources.
