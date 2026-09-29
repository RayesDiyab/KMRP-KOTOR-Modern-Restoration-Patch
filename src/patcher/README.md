# KMRP application

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


`KMRP - KOTOR Modern Restoration Patch.exe` is the single-file installer for all 66
supported resolutions. It contains the executable update, shared interface
artwork, and every matching GUI set, so no companion folders need to be
shipped.

The patcher accepts the supported editable `swkotor.exe`, creates recoverable
backups, updates the game executable, marks it DPI-aware for the current user,
sets NVIDIA's present method for it where the driver would otherwise show
half-drawn frames, and configures `swkotor.ini`. Three optional components,
each on by default and each independent, are chosen under *Advanced Settings*:
K1 Modern Driver Compatibility, the map-note corrections, and controller
support. See `docs/patcher-ui-build.md` for the order of every step. Under
`[Graphics Options]`, it removes duplicate resolution keys and writes the
selected values, for example:

```ini
Height=1440
Width=3440
```

All other INI sections and settings are preserved.

The shared artwork is generated from the repository snapshot:

```text
assets\override-3440x1440
```

The per-resolution GUI layouts come from the preserved KOTOR High Resolution
Menus source package, with the exact final 3440 × 1440 GUI collection used for
that gold selection. During installation the selected files are written to the
game's `Override` directory and replace files with the same names. Existing
conflicting files are backed up first -- except the bundled third-party art
(portraits and item icons), which yields to a file already there and leaves it
alone. **Restore Original** restores replaced
files and removes files introduced by the patcher.

At startup, a missing or unsupported executable expands an inline compatibility
guide in Step 2. It links directly to the required
[KOTOR Editable Executable](https://deadlystream.com/files/file/1320-kotor-editable-executable/)
on Deadly Stream. **Start Patching** remains disabled until a compatible
executable and the initial game configuration are available. Once patched, the
same button becomes **Restore Original** when the verified backups exist.
While patching or restoring, that button becomes an in-button progress display:
its pale-blue fill advances left to right and its label carries the current
stage and percentage. Step 4 itself remains stable and uncluttered.

`build_kmrp.ps1` uses `assets/branding/favicon.ico` for the Windows application
and window icon. The main window resizes at a locked aspect ratio:
controls, fonts, icons, and hit targets scale together. It opens at an approved
1300 × 700 footprint on a 1080p desktop and scales proportionally for other
working areas. During a resize, a cached frame is stretched and the real layout
is rebuilt once when the drag ends, avoiding repeated WinForms repaint flicker.

The seven UI icons -- four steps, Verified, Missing and the Advanced Settings
gear -- are prepared from `assets\branding\ui-icons\` by
`tools\prepare_app_icons.py`. See
`docs\patcher-ui-build.md` for the complete UI state machine, copy rules, icon
normalisation, resize algorithm, embedded-resource inventory, transaction
model, and release checklist.

Build from the project directory:

```powershell
python .\tools\prepare_app_icons.py  # requires Pillow; only when source icons change
.\build_kmrp.ps1
```

For a C#/icon-only iteration after a successful full resource build:

```powershell
.\build_kmrp.ps1 -ReuseResources
```

Automation-only command-line modes are also available:

```text
"KMRP - KOTOR Modern Restoration Patch.exe" --apply clean.exe output.exe 1920x1080
"KMRP - KOTOR Modern Restoration Patch.exe" --in-place swkotor.exe 1920x1080
"KMRP - KOTOR Modern Restoration Patch.exe" --restore swkotor.exe
```

`--in-place` performs the complete installation. `--restore` restores the EXE,
INI, and Override files. `--apply` creates only a patched executable and does
not change the INI or Override directory.
