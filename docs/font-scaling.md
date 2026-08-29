# Font and dialogue-layout scaling

## What this is

KOTOR renders UI and dialogue text at a fixed pixel size regardless of
resolution, so it is unreadably small at 3440x1440 and above. This is a
separate workstream from the map/marker patch (`universal-resolution-math.md`)
and, as of this writing, is **not yet integrated into the Universal Patcher**
— see "Integration status" below before assuming a fresh install gets any of
this.

Full technical detail (addresses, struct layout, byte sequences):
`reverse-engineering/font.md`. Investigation log:
`reverse-engineering/experiments/005-font-scale-investigation.md`.
Machine-readable patch specs: `patches/font_patch/*.json`.

## What it does

Three independent executable-side fixes, each its own standalone build
script, chained together by running one against the previous script's
output:

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

A fourth, separate fix touches a `.gui` **data** file rather than the
executable: `computer.gui`'s terminal-screen controls were shifted left of
the terminal prop's actual on-screen position (unrelated to font size — a
pre-existing gap in the gold GUI correction pass). Fixed by hand in a KOTOR
GUI editor and registered in `GOLD_GEOMETRY_TEMPLATES`
(`tools/prepare_universal_resources.py`) so the same proportional-transfer
mechanism that already carries the gold GUI corrections to all 48
resolutions now also carries this one.

## Reproducing the current live candidate

Chained from the pristine gold 3440x1440 exe (`D8F0EEBF...`):

```powershell
python tools\build_font_scale_wrapper.py GOLD_EXE stage1.exe --scale 2.0
python tools\build_letterbox_scale_wrapper.py stage1.exe candidate_003.exe
```

Current confirmed-live chain (most recent last):

| Stage | SHA-256 | What it adds |
| --- | --- | --- |
| Gold (pristine) | `D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE` | map/marker patch only |
| Candidate 001 | `DEE9CF8F2A7A3837F59D1781E57045AA93CEF6A3258EA9CE9CDE041F410712F1` | + font scale (2.0x) |
| Candidate 002 | `B4C49441FEA3EF7E2239BD4C2B3FD522D8B3C00C8950D200F40527547CA3E1B5` | + list-row height |
| Candidate 003 (live) | `CDE41D99FA2DA70C294893A4FF47EAB9A4EAE848303695C18410B3846401170C` | + dialogue letterbox |

`Override/computer.gui` on the live install is also already the corrected
version (also copied into `assets/override-3440x1440/computer.gui`).

## Integration status — read this before assuming a fresh install has these fixes

**None of the three executable hooks above are part of the Universal
Patcher's shipped "gold" delta.** `generate_gold_delta.py` diffs the clean
exe against `swkotor_gold_final_D8F0EEBF.exe` — a snapshot that predates all
font work in this document. Rebuilding the Universal Patcher today (as was
done to pick up the `computer.gui` fix, see below) reproduces only the
map/marker patch plus whatever's in `assets/override-3440x1440/` — **not**
the font scale, list-row, or letterbox executable hooks, for any resolution
including 3440x1440.

Concretely: `dist/KOTOR_Universal_UI_Patcher.exe`
(`A018BA7FAA83F56F866303452D9ED016D9F650ABF02534550F11C96D9CE48C15`, rebuilt
after the `computer.gui` fix) will install the corrected `computer.gui`
everywhere, but a user selecting any resolution through it — including
3440x1440 — will get small, unscaled text and the original narrow-bar
letterbox. The only place these font-side fixes currently exist is the one
live install they were built and tested against by hand.

**Recommended next step** (not yet done): fold `candidate_003.exe`'s changes
into a new gold reference snapshot so `generate_gold_delta.py` picks them up
automatically — or, more in line with how `ResolutionPatch` already
generalizes the map patch per-resolution in `KotorUniversalPatcher.cs`, add
equivalent hook-application code there directly rather than relying on a
byte-identical gold snapshot (the font/list-row/letterbox hooks don't
actually vary by resolution the way the map fields do, so they may not even
need per-resolution parameterization beyond what's already in `--scale`).
Either way, this needs a decision before it's built, not an assumption.

## Validation status

- **Manually play-tested at 3440x1440**: font scale, list-row height,
  dialogue letterbox, and `computer.gui` positioning. All confirmed via
  direct screenshots during play across many screens (see
  `reverse-engineering/experiments/005-font-scale-investigation.md` for the
  full list).
- **Structurally checked only, not play-tested**: the `computer.gui`
  geometry transfer at 1920x1080 (confirmed every control lands fully
  on-screen; not confirmed to look correct in an actual running game at that
  resolution).
- **Not checked at all**: any resolution other than 3440x1440 for the three
  executable hooks; `computercamera.gui`'s positioning; a resolution-aware
  formula for the scale factor itself (every candidate used a fixed `2.0`,
  chosen because it matches KPM's own known-reasonable value, not derived
  from first principles).
