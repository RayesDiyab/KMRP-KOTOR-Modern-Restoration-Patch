# KOTOR Universal UI & Map Patcher

The standalone universal patcher is built at `dist/KOTOR_Universal_UI_Patcher.exe`.
It supports 48 selectable resolutions across 4:3, 16:10, 16:9, 21:9, and
32:9. See `docs/universal-resolution-math.md` for the executable fields,
coordinate math, GUI packaging, reproduction steps, and validation status.
See `docs/font-scaling.md` for the separate font/dialogue-letterbox/list-row
scaling work — **read its "Integration status" section before assuming the
Universal Patcher includes it; as of this writing it does not.**

The completed 3440×1440-only gold patcher remains frozen at
`releases/3440x1440-gold-final/KOTOR_UI_Gold_Patcher_3440x1440_FINAL.exe`.
Third-party attribution and licensing notes are in `THIRD_PARTY_NOTICES.md`.

This directory is the source workspace for the resolution-independent KOTOR UI
patcher. Phase 0 (a safe, repeatable map/marker fix) is complete and confirmed
by play-test. The current workstream is font/dialogue-layout scaling; see
`docs/font-scaling.md`.

## Current status

- **Map/marker patch**: complete and play-test confirmed at 3440x1440,
  including the marker click-hitbox offset (fixed via a `+14` Y-axis
  hit-test correction). The Universal Patcher generalizes it to 48
  resolutions structurally; only 3440x1440 and one full 1920x1080 install
  have been play-tested end-to-end — see `docs/universal-resolution-math.md`
  for exact validation status per resolution.
- **Font scaling, list-row height, and dialogue letterbox**: three
  standalone executable patches (`tools/build_font_scale_wrapper.py`,
  bundled list-row hook, `tools/build_letterbox_scale_wrapper.py`), plus a
  `computer.gui` positioning fix already folded into the Universal Patcher's
  GUI pipeline. All four are play-test confirmed at 3440x1440. **The three
  executable-side fixes are not yet part of the Universal Patcher's shipped
  gold delta** — see `docs/font-scaling.md`.
- The user-tested live `swkotor.exe` is frozen as the gold build with SHA-256
  `D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE`.
- A strict source-to-gold Windows patcher is available in `dist/`. It embeds
  only the 4.7 KB byte delta, creates a verified backup, supports restore, and
  refuses unknown executables.
- This directory is now tracked in a private git repository
  (`github.com/RayesDiyab/kotor-universal-ui`).

## Build the gold patcher

```powershell
.\build_gold_patcher.ps1
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
