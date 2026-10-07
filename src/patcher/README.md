# KMRP application

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


`KMRP - KOTOR Modern Restoration Patch.exe` is the single-file installer for all 66
listed resolutions, and since 2026-09-30 for any other size from 4:3 to 32:9, whose
menus it blends from the listed ones and whose controller badges and HUD boxes it
draws for them. Since 2026-10-04 that is done by KMRP's patch module while the game
runs, with `macos/tools/kmrp-guiblend.c` compiled into it; `GuiBlend.cs` is its C#
reference and decides which sizes the installer accepts. The installer contains
`KMRP.kpatch`, whose module holds the engine recipe, the shared interface artwork and
every GUI set, and since 2026-10-05 the controller patch, `KOTOR 1 Native Controller
Mod + Xbox HUD.kpatch`, so no companion folders need to be shipped.

The patcher accepts Steam's, GOG's and the editable 1.03 `swkotor.exe` (`GameExecutable`
in `KmrpPatcher.cs`), creates recoverable
backups, installs KPM's runtime to apply engine fixes in memory, marks it DPI-aware for the current user,
sets NVIDIA's present method for it where the driver would otherwise show
half-drawn frames, and configures `swkotor.ini`. Three optional components,
each on by default and each independent, are chosen under *Advanced Settings*:
K1 Modern Driver Compatibility, the map-note corrections, and controller
support. The map notes are an option of KMRP's patch (`map-notes` in
`configs\kmrp.ini`); controller support is a patch of its own, `kmrp-controller`,
installed only while that switch is on (`KpmEdition.cs`; from 2026-10-04 to
2026-10-05 it was an option of KMRP's patch). See `docs/patcher-ui-build.md` for the
order of every step. Under `[Graphics Options]`, it removes duplicate resolution keys
and writes the display's current size, where the game starts, for example:

```ini
Height=1440
Width=3440
```

All other INI sections and settings are preserved.

**Correction, 2026-10-01:** the normal build no longer reads a clean executable
or gold snapshot, and the installer no longer writes an engine update into
`swkotor.exe`. Steam's file stays unchanged; supported editable CD/GOG files
receive only the existing LAA flag. `WindowsEnginePatch.cs` specializes the
source template and checks scaling-field coverage. See the
[source build reference](../../docs/windows-engine-source.md).

The shared artwork is generated from the repository snapshot:

```text
assets\override-3440x1440
```

The per-resolution GUI layouts come from the preserved KOTOR High Resolution
Menus source package, with the exact final 3440 × 1440 GUI collection used for
that gold selection. Since 2026-10-04 they are carried inside the patch's module
and nothing is written to the game's `Override` directory; the game reads them from
the module's own folder. **Restore Original** still restores the files an older
KMRP replaced in `Override` and removes the ones it introduced, from that install's
manifest.

Step 1 starts at `swkotor.exe` beside the patcher, and otherwise at Steam's KOTOR (Steam's
record of app 32370, then every library in `steamapps\libraryfolders.vdf`, at
`steamapps\common\swkotor`, as the Mac installer looks), then GOG's (its registry entry,
game 1207666283): `GameFolders` in `KmrpPatcher.cs`, since 2026-09-30.
Step 2, *Detect Game Version*, names the executable it finds -- the Steam version,
the GOG version or the editable 1.03 `swkotor.exe` -- beside its badge, or says which
file it could not use; the window checks again whenever it is activated. Until
2026-09-30 it was *Verify Editable EXE*, and a missing or unsupported executable
expanded it into a guide linking to the KOTOR Editable Executable on Deadly Stream,
with *Get Editable EXE* and *Check Again*: KMRP now takes all three versions as they
are. Step 3 has nothing to choose: it reads "Starts at W × H. The game lists every
resolution the connected display supports." (From 2026-10-04 to 2026-10-07 it had a
*Choose* button opening a checklist, `ResolutionsDialog`, removed at the
maintainer's request.)
**Start Patching** remains disabled until a supported
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

To reuse interface resources after a successful full resource build:

```powershell
.\build_kmrp.ps1 -ReuseResources
```

Both forms assemble the source engine, compile KMRP's module, the controller
patch's module and KPM's runtime, and package the two patches, `KMRP.kpatch` and
`KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`. The required game-derived build
inputs are `TexturePacks/swpc_tex_gui.erf` and, for the controller patch, the game's
own layout files in `build-inputs\vanilla-gui` (`build-inputs/README.md`);
per-resolution font caches are optional.

Automation-only command-line modes are also available:

```text
"KMRP - KOTOR Modern Restoration Patch.exe" --apply clean.exe output.exe 1920x1080
"KMRP - KOTOR Modern Restoration Patch.exe" --in-place swkotor.exe 1920x1080
"KMRP - KOTOR Modern Restoration Patch.exe" --restore swkotor.exe
```

`--in-place` performs the complete installation. `--restore` restores owned
runtime, EXE-header, INI and Override changes. `--apply` creates only an offline
reference from a supported editable CD/GOG executable and does not change the
INI or Override directory; it is not a build prerequisite or Steam install mode.
