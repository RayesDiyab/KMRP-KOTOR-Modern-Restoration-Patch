# KOTOR Universal UI & Map Patcher

The standalone universal patcher is built at `dist/KOTOR_Universal_UI_Patcher.exe`.
It supports 48 selectable resolutions across 4:3, 16:10, 16:9, 21:9, and
32:9. See `docs/universal-resolution-math.md` for the executable fields,
coordinate math, GUI packaging, reproduction steps, and validation status.

The completed 3440×1440-only gold patcher remains frozen at
`releases/3440x1440-gold-final/KOTOR_UI_Gold_Patcher_3440x1440_FINAL.exe`.
Third-party attribution and licensing notes are in `THIRD_PARTY_NOTICES.md`.

This directory is the source workspace for the resolution-independent KOTOR UI
patcher. Development is gated by Phase 0: prove a safe, repeatable map fix before
building the general UI generator or installer.

## Current status

- Codex-to-x32dbg MCP connection verified with plugin version 2.3.0.
- Known executable candidates inventoried and hashed.
- The isolated full-map marker wrapper is visually confirmed at 3440x1440.
- Gameplay minimap and full-map fog/grid regressions are absent.
- The user-tested live `swkotor.exe` is frozen as the gold build with SHA-256
  `D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE`.
- A strict source-to-gold Windows patcher is available in `dist/`. It embeds
  only the 4.7 KB byte delta, creates a verified backup, supports restore, and
  refuses unknown executables.

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
