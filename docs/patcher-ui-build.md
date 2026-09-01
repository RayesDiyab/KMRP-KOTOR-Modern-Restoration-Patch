# Patcher UI, asset, and build architecture

This document describes the shipping Windows patcher in
`app/patcher/KotorUniversalPatcher.cs`, the assets compiled into it, and the
build and verification workflow. Resolution and game-engine math remain in
`docs/universal-resolution-math.md`; font and listbox patches remain in
`docs/font-scaling.md` and `reverse-engineering/listbox-geometry.md`.

## Shipping artifact

`build_universal_patcher.ps1` produces one portable executable:

```text
dist/KMRP.exe
```

No companion asset folder is required. The executable embeds:

- the verified clean-to-gold executable delta;
- the 48-resolution catalog;
- one GUI archive for each supported resolution;
- the common Override archive, including shared textures and font atlases;
- the KOTOR High Resolution Menus GPL notice;
- the brand artwork, four step icons, and the Verified status artwork.

The supported editable executable is identified by SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
The current gold-v13 reference is 4,071,424 bytes with SHA-256
`145F46FE85AF5934D6EE55C3D6BD5E54354762B5AFF3078C3875BC054EDE9C90`.
The constants in `GoldPatch`, `tools/generate_gold_delta.py`, and the default
`-GoldExe` argument in `build_universal_patcher.ps1` must always move together.

## Main-window flow

The interface is one four-step card. State is derived from the selected
`swkotor.exe`; it is not stored separately in the UI.

| Step | Before patching | After patching |
| --- | --- | --- |
| 1. Game folder | Browse for the KOTOR directory. | Shows the selected directory. |
| 2. Editable EXE | Verifies the required Deadly Stream executable. Missing or incompatible files expand an inline recovery panel with download, choose, and recheck actions. | Shows the enlarged supplied Verified badge and `Verified`. |
| 3. Resolution | Shows the 48-resolution dropdown, grouped by aspect ratio in each item. | Replaces the dropdown with the installed resolution as read from the patch manifest. |
| 4. Apply | Shows readiness, progress, or a recovery instruction. | Permanently shows `Patched successfully` and `KOTOR is ready to play at W × H.` |

The primary button has one identity at a time:

- a supported clean executable produces **Start Patching**;
- a verified patched install with complete backups produces
  **Restore Original**;
- an unresolved executable or game setup keeps the action disabled;
- while work is running, all mutation controls are disabled and the primary
  button becomes the progress surface: a pale illuminated-blue fill advances
  inside the rounded button while its centred label shows the current stage and
  percentage. Step 4 keeps one calm, stable instruction with no percentage or
  file-level detail.

The success state is deliberately idempotent. Refocusing, clicking, or
reactivating the window calls `RefreshStatus()`, but a gold install is rebuilt
into the same `Patched successfully` state and the same installed-resolution
message. There is no second post-click "protected resolution" message.

### User-facing language boundary

The main card explains the next action and avoids implementation details:

- hashes stay in validation code and logs;
- raw fallback paths are not displayed as user selections;
- `swkotor.ini`, `[Graphics Options]`, and incomplete-key diagnostics are not
  shown in Step 4;
- a missing INI is described as **Game setup needed** with the instruction to
  launch KOTOR once, close it, and check again.

Detailed file paths and verification failures remain available through
**Open Log** and blocking error dialogs where they are actionable.

## Typography, artwork, and status icons

The visual system uses the supplied KOTOR brand image, Old Republic for display
roles, and Segoe UI for body text. The current design-space sizes are:

- step titles: 22 pt;
- step subtitles: 16.5 pt;
- right-side states: 18 pt bold;
- Browse and primary action labels: 18 pt;
- secondary buttons: 15.5 pt;
- recovery title/body/path: 19 / 15 / 14.5 pt;
- footer links and credit: 15.5 pt.

The four step sources and the Verified source live in `App icons/`. Run:

```powershell
python .\tools\prepare_app_icons.py
```

The script:

1. classifies files by filename keyword;
2. crops to pixels with alpha greater than 8;
3. preserves aspect ratio while scaling the longest ink edge to 224 pixels;
4. centres the result on a 256 × 256 transparent canvas;
5. writes white artwork to `app/patcher/icons/`.

White is intentional. The patcher multiplies the resource by the current theme
colour at draw time, keeping icon colour controlled by the UI palette. Missing
step artwork falls back to the built-in vector glyph. Missing Verified artwork
falls back to the text-only state. The Verified resource is drawn at 32 design
pixels and grouped optically with its label.

## Header ambience

Light enters the top bar from a source above the window, lights a volume of drifting
smoke, and small motes fall through it. It is generated in code by `LightField` --
procedural noise plus a particle pass -- not imported from any stock asset, so no
third-party licence is attached to it.

The source itself is deliberately off-screen and spans the full width. An earlier
version put a point source behind the crest; it read as a glowing ball, and it cost
the wordmark its legibility (see the table below). With the light entering from above
the top edge instead, it has died away by the time it reaches the letters, so density
and legibility stopped competing.

### How it is built

The billowing structure is fBm noise rather than sprites, because soft blobs cannot
produce the fractal, curdled edge that reads as smoke. The turbulence comes from
**domain warping**: the noise field is sampled at coordinates that are themselves
offset by another noise field, which folds the plume into itself instead of leaving
it as smooth drifting fog. Perlin gradient noise, not value noise -- value noise
shows axis-aligned blocking once it is warped.

The smoke, the light falloff, and the descending shafts accumulate into one scalar
emission buffer at `1/Downscale` resolution. A single bloom pass and a single colour
ramp then light all of them consistently, and the buffer is upscaled, which supplies
the final softening for free. The ramp is the blue counterpart of the reference's
black to olive to gold to white-hot core.

Motes are drawn **after** the upscale, at full resolution. They were originally
accumulated into the smoke buffer, but at `Downscale = 8` a mote is clamped to a
single buffer pixel, so it could not be made smaller and upscaled into a soft 16px
disc. Drawing them separately decouples their size from the buffer resolution.

### Cost

This is per-pixel CPU work, so it is measured, not assumed. `Downscale` is the
dominant lever: the noise is evaluated nine times per buffer pixel, so halving it
quadruples the cost.

At full design scale (a 1980 x 420 header, the worst case) the shipping settings
render in **22.1 ms average, 27.1 ms max**, against a 46.8 ms frame budget -- a 40 ms
WinForms timer lands on Windows' 15.6 ms granularity and therefore fires every
~46.8 ms, or about 21 fps. Measured in the running application, the effect costs
about **40% of one core** while the window is focused and idle.

Two things were required to get it that low, and both should be kept:

- the scaled brand is cached as a bitmap. The header repaints on every animation
  frame, and re-running a 650 x 350 bicubic resize per frame cost more than the plume
  itself -- removing it took the process from 57% of a core to 40%;
- the effect stops entirely while a patch is running, during the snapshot resize,
  when minimised, and when the window is not active.

If it needs to be cheaper still, raise `Downscale`, drop `Octaves` from 3 to 2, or
lengthen the timer interval -- the plume is slow enough to survive a lower frame rate.

### Measured settings

Averaged over 59 frames of steady state on a rendered 1980 x 420 header, with the
brand composited exactly as the form composites it:

| Candidate | Lit | Mean lit pixel | Wordmark contrast |
| --- | --- | --- | --- |
| Point source behind the crest, dense | 65.1% | rgb 45, 71, 105 | **17.9** |
| Shipping: off-screen source, full width | 33.7% | rgb 17, 34, 61 | **115.1** |

Wordmark contrast is the luminance gap between the silver letters and the ground
immediately behind them; ink is separated from ground by blue-minus-red, since the
letters are neutral and the plume is strongly blue. The point-source version scored
17.9 and would have swallowed the wordmark. Any future change to the light model
should be checked against this number, not against a screenshot.

## Window sizing and smooth proportional resize

All controls are authored once in design-space coordinates. Their rectangles
and font templates are captured after construction, then scaled uniformly.
Width and height cannot be stretched independently.

The approved 1080p target is a centred 1300 × 700 outer window on a
1920 × 1040 usable desktop. Startup sizing uses:

```text
monitor_scale = min(work_area_width / 1920,
                    work_area_height / 1040)

startup_scale = reference_ui_scale × monitor_scale
startup_scale = min(startup_scale, scale_that_fits_94_percent_of_work_area)
startup_scale = max(startup_scale, 0.35)
```

The height is normally the limiting dimension on ultrawide monitors. This
prevents the patcher from becoming enormous simply because the desktop is wide.
The minimum uniform scale is 0.35.

During a live resize, WinForms would otherwise re-layout and repaint every
label, icon, panel, and native control for every mouse movement. The patcher
instead:

1. finishes pending state and paint work;
2. captures the current client area into a premultiplied 32-bit bitmap;
3. hides child controls and scales that bitmap with the window;
4. performs one real layout and font update when the resize ends;
5. restores controls, refreshes state, repaints, and disposes the bitmap.

Old scaled fonts are retained for 750 ms before disposal. This prevents a
queued `LinkLabel` paint from using a font object that was replaced during the
resize burst—the cause of the earlier `System.ArgumentException: Invalid
parameter` JIT dialog.

## Executable, INI, and Override transaction

The in-place patch path is deliberately conservative:

1. verify the source executable hash and length;
2. create or verify the executable backup;
3. apply the clean-to-gold delta to a temporary file;
4. verify the result before atomically replacing `swkotor.exe`;
5. update `swkotor.ini` under `[Graphics Options]`, removing duplicate Width
   and Height keys while preserving unrelated sections, comments, encoding,
   and line endings;
6. install the common and selected-resolution Override archives;
7. back up conflicting Override files and record introduced files;
8. write the patch manifest and installed resolution.

Failure rolls back changes made by the current operation. Restore verifies the
backup records, restores the EXE and INI, restores replaced Override files, and
removes files introduced by KMRP.

## Build workflow

Requirements currently encoded by the build script:

- Python: `C:\Python314\python.exe`;
- C# compiler: `.NET Framework` `csc.exe` under
  `C:\Windows\Microsoft.NET\Framework\v4.0.30319`;
- Pillow only when regenerating `app/patcher/icons/` with
  `prepare_app_icons.py`. The normal universal resource pipeline intentionally
  does not require Pillow.

If the source icons changed, first run `prepare_app_icons.py` with a Python
environment that has Pillow. Then perform a full release build:

```powershell
python .\tools\prepare_app_icons.py  # requires Pillow; skip if icons are unchanged
.\build_universal_patcher.ps1
```

Use `-ReuseResources` only for a C#/icon-only iteration after a successful full
resource build:

```powershell
.\build_universal_patcher.ps1 -ReuseResources
```

Both `build_universal_patcher.ps1` and `build_gold_patcher.ps1` use the
project-root `favicon.ico`. `app/patcher/favicon.ico` is retained as a
synchronised compatibility copy, not as an independent source of truth.
After compilation the universal builder sends `SHCNE_UPDATEITEM` for the output
path so Explorer is prompted to refresh an icon cached for `dist/KMRP.exe`.

The final build prints the output path and SHA-256. A build's KMRP hash is not a
stable project constant because compiler metadata can change; record the hash
next to a release artifact rather than in source-level architecture docs.

## Command-line modes

```text
KMRP.exe --apply clean.exe output.exe WIDTHxHEIGHT
KMRP.exe --in-place swkotor.exe WIDTHxHEIGHT
KMRP.exe --restore swkotor.exe
```

`--apply` changes only the output executable. `--in-place` performs the full
EXE, INI, and Override transaction. `--restore` restores all three. Omitting
the resolution in the legacy `--apply` and `--in-place` forms selects
3440 × 1440.

## Release verification checklist

1. Run `prepare_app_icons.py`; confirm all five supplied roles are reported.
2. Run a full `build_universal_patcher.ps1` without `-ReuseResources`.
3. Confirm the embedded source/target hashes and the 48-entry resolution table.
4. Extract the executable's 32px and 256px icon frames and confirm both show the
   current root `favicon.ico` artwork.
5. Test missing, unsupported, clean, patched, restoring, error, and success UI
   states.
6. Confirm the Verified badge size and that the success message survives window
   activation.
7. Resize from the minimum size to a large size and confirm the aspect ratio,
   snapshot preview, final sharp text, complete footer, and absence of flicker
   or JIT errors.
8. Patch a clean install, verify the EXE/INI/Override contents, launch the game,
   then restore and compare all backups.
9. Record the final `dist/KMRP.exe` SHA-256 in the release directory.
