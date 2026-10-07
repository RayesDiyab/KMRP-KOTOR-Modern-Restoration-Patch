# KMRP for macOS: what it installs, byte for byte

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

The macOS port of KMRP for the Steam Aspyr build of KOTOR: how it is built, what the
installer writes, and how each part of the Windows patch is carried over. The goal is a Mac
build that cannot be told apart from Windows at the same resolution; the tracker for that,
Windows site by Windows site, is [`WINDOWS-PARITY.md`](WINDOWS-PARITY.md). The player-facing
instructions ship in the package as `README.md` ([`PLAYER-README.md`](PLAYER-README.md)).
Everything below was measured on a 14" MacBook Pro (M5, macOS 27.0, 1512x982 points,
3024x1964 pixels, Rosetta 2), on 2026-09-29 unless a passage gives another date; what was
not tested is said where it matters and collected under *Coverage*. The document describes
the build as of 2026-10-08. Where a design was replaced, the passage says from when to when
it held, and keeps what was measured then.

## The build this describes

| | |
| --- | --- |
| Game | *Star Wars: Knights of the Old Republic*, Steam, Aspyr macOS port |
| Executable | `Knights of the Old Republic.app/Contents/MacOS/KOTOR_Exe`, version 1.4.0 (176481) |
| Size, SHA-256 | 6,333,424 bytes, `C1FCB8D37C702849882A17751C63EE0AF7C2B9CBBC3B31B98A5F0EDBC27C6D71` |
| Format | thin Mach-O x86_64, not position-independent; `__TEXT` at VA `0x100000000`, file offset 0 |
| Signature | Aspyr, team `VF8SGH77F7`, CodeDirectory flags 0 (no hardened runtime, no library validation) |

**Address convention.** Addresses are virtual addresses as Ghidra and `otool` show them.
The image always loads at `0x100000000`, and within `__TEXT` the file offset is
`VA − 0x100000000`. The Windows convention (`FILE = VA − 0x400000`) does not apply here.

The installer refuses any other `KOTOR_Exe`.

## 1. How the Mac port is put together

**What KMRP for macOS is now** (2026-10-08): four KotOR Patch Manager patches, installed by
KMRP Installer or ticked by hand in KotOR Patch Manager.

| Patch file | Id, and the module it installs | Whose | What |
| --- | --- | --- | --- |
| `K1StrayBugFixes.kpatch` | `k1-stray-bug-fixes-patch`, `patches/k1-stray-bug-fixes-patch.dylib` | FTD's, unchanged | the engine fixes that hold at any resolution (K1, K2, K3, K5 below), the memory-safety fixes among them |
| `K1WidescreenPatch.kpatch` | `k1widescreenpatch`, `patches/k1widescreenpatch.dylib` | FTD's, unchanged | the resolution, the video mode (K4, K8, K9, the letterbox bars) and its `.gui` mode: no layout of its own, and the sizes, lists, popups and map that menus laid out for the resolution need |
| `KMRP-macOS.kpatch` | `kmrp`, `patches/kmrp.dylib`; name "KMRP for macOS" | KMRP's | every resolution's menu set and the artwork inside the module, the resolution chosen in the game, list rows centred, keyboard navigation, the text-height fixes, the status summary, map notes. `requires` the two above |
| `KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch` | `kmrp-controller`, `patches/kmrp-controller.dylib`; name "KOTOR 1 Native Controller Mod + Xbox HUD (macOS)" | KMRP's | controller support with its own files and SDL (sections 7 and 7a). Requires nothing: it also works without KMRP and without FTD's patches |

The two files of KMRP's own carry these names since 2026-10-08 (the maintainer: "macos both
kpatch files are macos specific"). Until then they were `kmrp.kpatch` and
`kmrp-controller.kpatch`; `kmrp-mac.sh` removes a copy under an old name from KotOR Patch
Manager's patch folder when it is KMRP's (`OLD_KPATCH_FILES`), since KPM would list the patch
twice. Windows' files are `KMRP.kpatch` and `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`,
with the same two ids; neither system's files run on the other. The ids did not change, so
the installed modules and the option files (`configs/kmrp.ini`,
`configs/kmrp-controller.ini`) keep their names.

How it got here, in short (each step is dated where this document describes it): four
patches, FTD's widescreen patch and KMRP's layout, map-note and controller patches
(2026-09-29); one patch, `kmrp`, with a
copy of FTD's two inside it and a conflict declared with them (2026-09-30); the menus inside
the module and nothing in the game's override folder, then KMRP as a patch that requires
FTD's two (both 2026-10-04); the controller as a fourth patch (2026-10-07).

The Mac executable is a different compiler's x86_64 build than Windows', so what Windows
changes in its executable is ported site by site; the menu files, fonts and artwork are the
same resource build's.

| Layer | What | Where it comes from |
| --- | --- | --- |
| Hook runtime | `KotorPatcher.dylib`, loaded by one `LC_LOAD_DYLIB` in `KOTOR_Exe` | KotOR Patch Manager (MIT), built from source by `build.sh` |
| FTD's two patches | *K1WidescreenPatch* by FTD and RaymanGT and *K1StrayBugFixes* by RaymanGT and FTD (MIT), which carry KMRP's engine fixes K1 to K9 (below) | built unchanged from the KotOR Patch Manager tree given to `build.sh` as `--kpm`, with that tree's own `Patches/create-patch.py` (section 9) |
| KMRP's patch | `kmrp`, built by `tools/make_kmrp_patch.py --split` from three parts | `patches/kmrp-assets/`, `patches/kmrp-layout/`, `patches/kmrp-map-notes/` |
| … menus and artwork | every resolution's set and the artwork in a bank inside the module; the resolution chosen in the game; list rows centred ("The menus inside the module" and the two sections after it) | `patches/kmrp-assets/`, `tools/make_kmrp_assets.py` |
| … layout | keyboard navigation, the text-height fixes, the status summary and KMRP's work in the GUI frame. Its resolution-dependent sites (section 4) are written by the Widescreen Patch's `.gui` mode since 2026-10-04, not by this part | `patches/kmrp-layout/` |
| … map notes | Derslok's 250 map-note corrections (the patch's `map-notes` option) | `patches/kmrp-map-notes/` |
| The controller patch | KMRP's Windows controller module, ported (section 7), reading the pad through SDL 3.4.16, with the Xbox-style HUD | `patches/kmrp-controller/`, `tools/make_controller_assets.py`; SDL's official macOS release, inside the module |
| Menus and fonts | every resolution's set from KMRP's resource build, pooled; any other size blended by the module the first time the game starts at it | `tools/prepare_universal_resources.py`, `pack_resolution_layouts.py`, `build_gui_blend_table.py`, all unchanged from Windows |
| Artwork | `override-common.zip`, less what the Mac does not use | the same resource build |
| Feat, power and skill icons | enlarged from the game's texture pack by the module | `tools/kmrp-abilityicons.c`, a port of `AbilityIconGenerator.cs`, compiled into the module |
| Row frames, tutorial icons, `tutorial.2da` | made by the module from the player's game: nothing of the game's ships | `tools/kmrp-gameart.c`, a port of `GameArtGenerator.cs`, compiled into the module |
| Installer | `kmrp-mac.sh`: install, uninstall, status, with a hashed manifest; run by `KMRP Installer.app`, the Windows patcher's window ported | this directory, `installer-app/` |

**Why the widescreen patch is the base** (decided 2026-09-29, after a day on which KMRP was to
ship a patch of its own instead): it is the Mac's resolution unlock, and KMRP's engine fixes
were contributed to it, so KMRP builds on it rather than carrying a second implementation.
What depends on KMRP's layouts stays in KMRP. Since 2026-10-04 KMRP talks to it through two
entry points, `K1Widescreen_UseGuiFileLayouts` and `K1Widescreen_SetTargetResolution` ("KMRP
on FTD's patches", below), which were merged into KotOR Patch Manager upstream on 2026-10-05
(LaneDibello/Kotor-Patch-Manager#319, merge commit `7546ae5`). The engine fixes are
documented beside their code, in `Patches/K1WidescreenPatch/KMRP-ENGINE-FIXES.md` of that
tree:

| | Fix | Windows equivalent |
| --- | --- | --- |
| K1 | word-wrap forward progress and the two short-string guards | `.kwl`, `0x0045A3B7`, `0x0045A3DC` |
| K2 | list rows stop growing | `0x0041B507`, `0x0041B52C` |
| K3 | leading newline trimmed | `.ktn` |
| K4 | video mode follows the target resolution | none: the Windows patcher writes the resolution into the executable |
| K5 | a line taller than its box is drawn, not dropped | none: Windows sizes the stack label with the font (`.ksc`) so the case does not arise |
| K6 | 0.5 px wrap margin | TXI `spacingR`; **no longer applied since 2026-10-05**: the fonts carry `spacingR 0` ([`docs/macos-two-patches-handoff.md`](../docs/macos-two-patches-handoff.md), section 3) |
| K7 | dialogue letterbox from the height; reply list fills the bar | `.klb`, nine sites |
| K8 | minimap keeps the vanilla zoom | `.kmz`, `.kfg` |
| K9 | the display's pixel resolution is a valid mode (Retina) | none: Windows display modes are already in pixels |

Since 2026-09-30 K1, K2, K3, K5 and K6, the fixes that hold at any resolution, are FTD's separate
*Stray Bug Fixes* patch (`Patches/K1StrayBugFixes`), which the widescreen patch requires; K4, K8,
K9 and the letterbox bars stay in the widescreen patch.

### The installer app

The package is `KMRP Installer.app` and the player README (`PLAYER-README.md`, shipped as
`README.md`). The app carries `kmrp-mac.sh` and
everything it installs in `Contents/Resources/kmrp` (the folder the package held as `kmrp/`
until 2026-09-30, beside `Install KMRP.command` and `Uninstall KMRP.command`, which it
replaces), and runs the script:

| The app | `kmrp-mac.sh` |
| --- | --- |
| at launch and after every run | `status --brief`: `install.info`, or the game and its build, without hashing every installed file (a full status takes seconds once KMRP is installed) |
| **Start Patching** | `install --yes --resolution current` (the size macOS is set to; `native` and `--size WxH` are the script's alone since 2026-10-07, section 5), with `--no-map-notes` when *Area Map Marker Fixes* is off, `--no-hd-icons` when *HD Icons* is off (since 2026-10-08), `--no-controller` when *Controller Support* is off, `--debug-logs` when *Debug Logs* is on (Advanced Settings, as on Windows), `--game` when one was chosen with **Browse** |
| **Restore Original** | `uninstall --yes` (and `--game`) |

What the script refuses (the game running, another build), the app shows as a blocking
message with the script's own words. A game KotOR Patch Manager manages is not refused: the
script replaces an install of FTD's two patches alone and installs for KPM beside any other
patch (section 2, *Ownership rules*), and the second step then reads "Managed by KotOR Patch
Manager: tick KMRP there, then Apply and Launch." The
script's output goes to `~/Library/Logs/KMRP/installer.log` (**Open Log**), and its stage
lines move the progress fill.

**It looks like the Windows patcher** (`installer-app/main.m`, a port of `MainForm`):
`UiTheme`'s colours, the brand lockup with the tagline set to the wordmark's ink width,
`LightField`'s smoke and motes (every constant Windows', faded out over the header's lowest
30% so they do not stop on a line beside the card, as they can on Windows:
`docs/windows-changes-from-macos.md`, item 11; rendered at 1/12 of the header's
pixels on a background queue every 62 ms and resampled with vImage), the four-step card
with the step and state art from `src/patcher/icons`, the pill buttons with the primary's
progress fill, the Advanced Settings view with its four toggles (*Area Map Marker Fixes*,
*HD Icons* since 2026-10-08, *Controller Support*, *Debug Logs*), and the footer. Its icon is the
Mac's own, shared with the disk image: the crest over "KMRP" (`tools/make_package_art.py`;
the Windows executable's `src/patcher/favicon.ico` until 2026-09-30, when the player asked
for the crest). Every rectangle is the Windows design-space one; the scale is `FitInitialSizeToWorkingArea`'s times 1.3,
because a Mac's points are denser than the 96-dpi pixels the Windows formula assumes (the
text was reported too small at 1.0, 2026-09-30); on a 14" MacBook Pro the window is
1,310x717 points. Bahnschrift and Segoe UI are Microsoft's and cannot ship: DIN Alternate
Bold narrowed to 92% and the system font stand in. All text is one Core Text line at an
explicit baseline: labels centred on their capitals, and each step's title and subtitle
(baselines 30 apart, as on Windows) centred together on its badge. AppKit's box drawing had
put the DIN labels about 5 pt low and clipped the step titles' descenders (both reported
2026-09-30); measured on the window afterwards, Browse's label sits 0.5 px from its
button's centre and the state labels on their badges' centre lines.

**Resolutions** (step 3), exactly as on Windows since 2026-10-08: no button, and before an
install the line "Starts at W × H. The game lists every resolution the connected display
supports." Installed, it reads "The game starts at this size. Choose another in the game,
under Options, Graphics.", with the size on the right. The game's
Screen Resolution list is Aspyr's list of the display's modes (each with its twin at the
display's pixels), of which `KmrpResolutionKnown` accepts a size when KMRP has menus for it and
the display reports a mode of it, in points or in pixels. Nothing is written for the list. For
one day (2026-10-07) step 3 had Windows' checklist of that week, with a custom size, written
beside `KOTOR_Exe` as `kmrp-resolutions.txt` and read by a hook in Aspyr's list builder
(`KmrpDisplayModes`, `0x10001deca`); Windows removed its checklist that day and the Mac's went
with it: `kmrp-mac.sh` has no `--resolutions`, removes a list file left over, and the module
has neither the reader nor the hook. Aspyr builds its list once, when the game starts, for
the main display of that moment: a display connected while the game runs is offered after a
restart (planned for KMRP 1.6, below). Known limit: of the game's own five sizes, 1024x768 stays listed, because Aspyr adds
it to its list itself and the game's whitelist accepts it before KMRP is asked.

**Planned for KMRP 1.6: the list made again when the display changes** (the maintainer,
2026-10-08: left for 1.6). Windows makes its list from the connected display each time the
dialog opens; the Mac game cannot yet. What was read on 2026-10-08 (KOTOR_Exe 1.4.0, Ghidra),
so that it need not be read again:

- The game has SDL 2 linked into it, which reads the displays once, when its video part
  starts, and keeps them: the video object at `[0x10067d1a8]`, its displays at `+0x250`
  (`0x70` bytes each, `+0x248` of them), a display's desktop mode at `+0x18` and its modes at
  `+0x10`, `+0xc` of them, read once by the driver's function at `+0x38` of the video object.
  `0x1000bc0a0`, `0x10003014d` and `0x1000bbf30` are its desktop mode, number of modes and
  mode.
- `0x10001ddee`, called once from `0x100002214` at start-up, makes the game's list from
  display 0 only (its loop ends after one pass): the display's modes, Aspyr's three sizes
  (`0x10001deca`), then what is no larger than the desktop mode, each with its twin at the
  display's pixels, kept as one set in the vector at `0x1006780c0`. `0x10001e1b8` at its head
  only reserves room, so a second call would add a second set and not replace the first.
- The game never changes the display's mode: a resolution is the size it draws at, into a
  surface KMRP resizes (`SizeSurface`).

What it would take: when the Screen Resolution dialog opens and the main display or its size
is no longer what SDL holds, write the display's identifier, desktop mode and an empty mode
list into SDL's record of display 0, empty the game's vector, and call `0x10001ddee` again.
Nothing would run while the display is the one the game started on. Not known: how the game's
window behaves when the display changes under it, which the list does not mend. To try
without a second display: change the scaling in System Settings, Displays, while the game
runs, which changes the main display's size as another display would.

**Quarantine.** A downloaded package keeps the quarantine flag on every file, and
Gatekeeper kills a flagged helper as it starts: a flagged copy of `kmrp-guiblend` exited
137, `spctl` "rejected" (tested 2026-09-30). The app's bundle is read-only when macOS runs it
from where it was downloaded, so the flag cannot be taken off there: `kmrp-mac.sh` copies
`bin/` into its work folder and removes the flag from the copy, and the app does the same
for its own dry run. **Not yet tested:** a downloaded, quarantined copy of the app itself
through Gatekeeper's first-run approval, and App Management (macOS 13 and later), which may
ask the player to allow the app to change the game's bundle; the app says how if the script
fails with "Operation not permitted".

**Seen**, from the package at 3024x1964, 2026-09-30, through the app's scripted-check
arguments: the installed and not-installed states, Advanced Settings, the progress fill at
"Installing artwork… 34%", and **Restore Original** then **Start Patching** on the live
game, the second leaving the same `KOTOR_Exe` (`5294ae4f…`) and install as `kmrp-mac.sh`
does alone. Also seen that day and removed since: the resolution list of that build from top
to end and its custom-size dialog, with a size outside the sets refused. `Test-MacInstaller.py`
passed on the app's `Contents/Resources/kmrp`. Built for x86_64 (macOS 10.13 and later, the
floor of the controller's SDL3 and the helpers) and arm64, with `-Wunguarded-availability`.
**Not looked at in the window:** step 3 as it reads since 2026-10-08, and the second step's
wording for a game KotOR Patch Manager manages (2026-10-07).

**Scripted checks.** The arguments the app takes after `open … --args`, from the comment at
the top of `installer-app/main.m`:

| Argument | What it does |
| --- | --- |
| `-KMRPRun install\|uninstall` | presses the action button once the status is in |
| `-KMRPNoMapNotes YES` | turns *Area Map Marker Fixes* off |
| `-KMRPNoHdIcons YES` | turns *HD Icons* off |
| `-KMRPNoController YES` | turns *Controller Support* off |
| `-KMRPSettings YES` | shows Advanced Settings |
| `-KMRPSnapshot <prefix>` | writes `<prefix>-ready.png` when the window is ready, `<prefix>-progress.png` once a run is a third through, and `<prefix>-done.png` and `<prefix>-log.txt` when it ends |
| `-KMRPQuit YES` | quits after that |

Until 2026-10-08 there were seven more, which set, opened and clicked through the resolution
checklist of 2026-10-07; they went with it.

## 2. Every file the installer writes

`kmrp-mac.sh install`, run from the package, in this order. Paths are relative to
`Knights of the Old Republic.app/Contents`. Read from the script on 2026-10-08; the last
install whose records were counted is of 2026-10-04 (12 records, three patches), before the
controller became a patch of its own.

| Path | Kind | Notes |
| --- | --- | --- |
| `~/Library/Application Support/KMRP/macos/` | made | KMRP's own records: `install.info`, `manifest.tsv` and `backup/` (below) |
| `~/Library/Application Support/KMRP/macos/backup/KOTOR_Exe` | copy | the original, re-hashed before anything is written |
| `MacOS/KotorPatcher.dylib` | added | KPM's runtime |
| `MacOS/patches/k1-stray-bug-fixes-patch.dylib`, `k1widescreenpatch.dylib`, `kmrp.dylib` | added | each patch's module, taken out of its `.kpatch` (`binaries/macos_x86_64.dylib`) under the name KPM gives it, the patch's id. `kmrp.dylib` holds the menu set for every resolution and the artwork; KMRP's two modules are signed ad hoc by the build and verified here |
| `MacOS/patches/kmrp-controller.dylib` | added unless `--no-controller` | the controller patch's module, with its own files and SDL 3.4.16 inside (section 7a) |
| `MacOS/patch_config.toml` | added | KPM's hook list, written at build time by KPM's own KPatchCore: the four patches' 109 hooks (16, 45, 24 and 24), or with `--no-controller` the three patches' 85 (`engine/patch_config.controller-off.toml`); counted in the package built on 2026-10-08 |
| `MacOS/configs/kmrp.ini` | section `[Patch Options]` written | `map-notes`, `hd-icons` (since 2026-10-08: off, the module leaves the bundled HD icon pack out of the artwork it gives the game, `LinkArtwork`) and `debug-logs` as `1` or `0`, where a KotOR Patch Manager with patch options records them (LaneDibello/Kotor-Patch-Manager#310) and `kmrp.dylib` reads them. Anything else in the file is kept; uninstall takes the section out, and deletes the file and the folder when nothing else is left. Not written by an install for KPM, where the options are KPM's to choose |
| `MacOS/configs/kmrp-controller.ini` | section `[Patch Options]` written, unless `--no-controller` | `debug-logs` only: the patch's other option, `xbox-hud`, is left to `Style` under `[Hud]` in the player's settings file (below) |
| `MacOS/KOTOR_Exe.backup.<yyyyMMdd_HHmmss>` and its `.json` | added | the untouched game in KotOR Patch Manager's format (`BackupManager`, `BackupInfo`), made before the load command, from which KPM's Apply starts (since 2026-10-01, as Windows' `WriteKpmBackup`) |
| `MacOS/kpm_install_state.json` | added | KPM's record of the install (`ManagedInstallState`, schema 1): the untouched game's hash and size, KPM's name for it ("1 1.4.0 (Aspyr macOS)", macOS, Steam, x86_64, its Mach-O identity), `InstalledPatches` with the installed patches' ids, `LinkedDependencyInstalled` true; KPM identifies the modified game by it (since 2026-10-01, as Windows' `KpmState`) |
| `MacOS/KOTOR_Exe` | edited | one load command, then `codesign --force --sign - --identifier KOTOR_Exe` |
| KPM's patch folder: `K1StrayBugFixes.kpatch`, `K1WidescreenPatch.kpatch`, `KMRP-macOS.kpatch`, `KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch` | added, or an older KMRP's replaced | where KPM's settings (`KPatchLauncher/settings.json` under `~/.config`, or `~/Library/Application Support`) say its patches are, so KPM lists them (since 2026-10-01, as Windows' `DeliverKpatches`). A file already there with the same contents is left and not recorded; an older `KMRP-macOS.kpatch` or controller patch is replaced when its manifest has KMRP's id; FTD's Stray Bug Fixes of any version is left; his Widescreen Patch from before the entry points is copied aside, replaced, and put back at uninstall. `kmrp.kpatch` and `kmrp-controller.kpatch`, the names until 2026-10-08, are removed from the folder when they are KMRP's. With no KPM settings, nothing is delivered, except in an install for KPM, which uses a folder "KPM patches" beside the game's |
| `~/Library/Application Support/Knights of the Old Republic/swkotor.ini` | two keys under `[Graphics Options]` | `Width` and `Height`, the size the game starts at (section 5), when it is the main display's size in points or in pixels; `ForceWidth` and `ForceHeight` instead for a `--size` that is neither. The file is created if the game never ran. `UseGuiFileLayouts` is not written since 2026-10-04 |
| `MacOS/kmrp-resolutions.txt` | removed if present | left by an install of 2026-10-07, the one day the installer had a resolution checklist; nothing is written for the game's list |
| `~/Library/Preferences/com.aspyr.kotor.steam.plist` | one key | `DisplayFullScreen` set to 1 (section 11, "Fullscreen default") |
| `~/Library/Application Support/Knights of the Old Republic/kmrp-controller.ini` | added if absent, unless `--no-controller` | the controller's settings (section 7): Windows' rumble defaults and `Style=Xbox` under `[Hud]`. A copy already there is the player's and is kept; one without a `[Hud]` section is given that section, and nothing else in it is touched |
| `MacOS/kmrp-sdl3.dylib` | not installed since 2026-10-04 | SDL 3.4.16 is inside the controller patch's module (inside `kmrp.dylib` until 2026-10-07), which unpacks it to its cache and loads it from there. The library of the official macOS release, its code unchanged and its signature redone ad hoc (`THIRD_PARTY_NOTICES.md`) |
| `Assets/override/` | not written since 2026-10-04 | the menu sets, KMRP's artwork and what it makes from the player's game are inside `patches/kmrp.dylib` ("The menus inside the module", below) |
| `~/Library/Caches/KMRP/<build>/` | made by the game, not the installer | KMRP's module's cache: `store/` (the artwork, 348 MB, unpacked once), `sets/<W>x<H>/` (a size's set, unpacked or blended the first time the game runs at it, with what is made from the player's game) and `art-<pid>/` (this run's links to the store). A new build starts a new folder and removes the old ones. Uninstall does not remove it |
| `~/Library/Caches/KMRP-Controller/<build>/` | made by the game, not the installer | the controller patch's cache: `files/` (its layouts, art and SDL, unpacked once) and `run-<pid>/` (this run's links). Uninstall does not remove it |

**In an install for KotOR Patch Manager** (other KPM patches already beside the game; see
*Ownership rules*) only the rows for KPM's patch folder, `swkotor.ini`, the Aspyr preference
and `kmrp-controller.ini` apply: no runtime, no modules, no load command, `KOTOR_Exe`
untouched.

**Until 2026-10-04** the installer also wrote the menus and artwork into `Assets/override/`:
1,855 files at 3024x1964, read from the manifest of an install of the package built from
`0d147a1`. They were 854 artwork files (98 of them the controller's: 22 prompt textures in
each of the four pad families and 10 for the Controller Layout screen); the resolution's set,
673 files (82 `.gui`, 36 font files, `lbl_mileftbot`, and the controller's 552 prompt and cue
textures sized for it, `kmrplayout.gui` and `kmrp_prompts.txt`); 18 made from the game (four
row frames, 13 `tut_*` icons, `tutorial.2da`: section 6); 310 enlarged feat, power and skill
icons. *Corrected 2026-09-29:* that row first said 757 artwork files and a set of 136 (83
`.gui`, 36 font files, the tutorial icons and `tutorial.2da`, the row-frame art); the tutorial
files and the row frames were made at install from that day, and the controller's art was
installed from the day it was ported. The same files are what the module registers now
(`Test-MacAssets.py`, below).

The `KOTOR_Exe` edit, measured on the installed file:

| | before | after |
| --- | --- | --- |
| `ncmds` / `sizeofcmds` | 45 / 5848 | 46 / 5912 |
| free load-command space | 1544 bytes | 1480 bytes |
| added command | — | `LC_LOAD_DYLIB` `@executable_path/KotorPatcher.dylib`, cmdsize 64, at file offset `0x16f8` |
| signature | Aspyr, team `VF8SGH77F7` | ad hoc, identifier `KOTOR_Exe` |
| size | 6,333,424 | 6,324,304 (the ad-hoc signature is smaller than Aspyr's) |
| SHA-256 | `C1FCB8D3…6D71` | `5294AE4F8390DCEE54473028A69546128A6D4C2308BD355A18B55692D6748E48` (the same in every install where it was read) |

This is the edit KPM's own installer makes (`KPatchCore/Applicators/MachODependencies.cs`):
the command goes into the space the linker left after the load commands, so no address
moves. `tools/kmrp-macho.c` does it without .NET, so players need nothing installed. Adding
and then removing the command reproduces the original file byte for byte (checked on a
copy). Only `KOTOR_Exe` is re-signed: the bundle's `_CodeSignature/CodeResources` is not
touched (its hash was compared before and after on a copy of the bundle). It no longer
matches the executable, which nothing on the launch path checks; see *Coverage*.

**Ownership rules**, carried over from the Windows installer:

- A file KMRP's installer writes over an existing one is copied to `backup/` first
  (`install_file`), and a name it would write twice stops the install and rolls it back: the
  second write would back up KMRP's own first copy as "the original", the bug the Windows
  installer had with `i_checkbox01.tga`. Since 2026-10-04 the installer writes so few files
  that neither case arises in a normal install; the rules stay in the script.
- Bundled third-party art (the names in `bundled-override.txt`: Party Portraits, the HD Icon
  Pack) yields to a texture already in the game's override folder under either extension,
  because the engine prefers `.tpc` over `.tga` for the same resref. Until 2026-10-04 the
  installer applied this when it copied the files (tested then: a pre-existing
  `ia_class4_005.tpc` was left alone and the rest installed); the module applies it now, each
  launch, to the folder it registers ("The menus inside the module").
- The installer stops without writing anything when `KOTOR_Exe` is not the build above,
  when this game is running, when the texture pack is missing, when the package does not
  match its `SHA256SUMS`, or when a KMRP install is already recorded. A size outside the
  shapes the sets cover (4:3 to 32:9, asked of `kmrp-guiblend`) stops it before anything is
  written to the game.
- With KotOR Patch Manager's files present (`KotorPatcher.dylib`, `patch_config.toml`,
  `patches/`, `kpm_install_state.json`, `addresses.db` or `KOTOR_Exe.backup.*` beside
  `KOTOR_Exe`), since 2026-10-01 as the Windows installer does it (`KpmEdition.cs`): an
  install of FTD's two patches alone is replaced (the untouched game put back from KPM's
  copy, his files deleted, then the four patches installed, his two among them in the
  version KMRP was built with; the maintainer: that "should still work"); with any other
  patch installed, KMRP installs *for* KPM: the resolution in `swkotor.ini`, the fullscreen
  preference and the controller's settings file, no runtime, no load command, `KOTOR_Exe`
  untouched, and the `.kpatch` files in KPM's patch folder (or in "KPM patches" beside the
  game's folder when KPM's settings name none) for the player to tick in KPM. Until
  2026-10-01 that case was refused.
- KMRP's own install is one KPM recognises and takes over: `kpm_install_state.json`, the
  KPM-format backup and the `.kpatch` files (the file table above). Once KPM's Apply has
  rewritten any of the runtime, `uninstall` leaves the runtime, the load command and KPM's
  records to KPM and removes only KMRP's own files, as Windows' Restore does; when KMRP's
  patches are the only ones KPM holds, it removes KPM's runtime too and puts back the
  untouched game ("Uninstall ownership correction", section 11).

**The manifest.** Every write is recorded in
`~/Library/Application Support/KMRP/macos/manifest.tsv` (kind, path, SHA-256 as written,
backup name), outside the app bundle so a Steam update cannot delete it. `uninstall`
walks it newest first:

- deletes an added file only if its hash still matches;
- restores a replaced one only if ours is still there;
- puts the original `KOTOR_Exe` back only if the installed one is unchanged;
- puts each INI key back to its old value, or removes it if it had none, only if it still
  holds what KMRP wrote (`ini` rows: key, value written, value before);
- leaves `Width` and `Height` as they are when the player has chosen another resolution in
  the game since: those two keys are the game's own;
- deletes `kmrp-controller.ini` only if it is still as written (`settings` row); an edited
  one is the player's, kept without counting as a change, so it never holds back the rest;
- takes its `[Patch Options]` section out of each options file (`options` rows), puts the
  Aspyr fullscreen preference back (`fullscreen` row), and removes a `.kpatch` it put in
  KPM's folder while that file is as written (`kpatch` rows);
- reports anything that changed and keeps its backup.

The INI is edited key by key, in place, keeping the file's CRLF line ends. An install and
uninstall left the player's INI byte-identical, including a `ForceWidth` it had before
(`testing/regression/Test-MacInstaller.py`), and so did a rollback (below).

`install.info` is written before the first change (`complete=0`) and completed at the end
(`complete=1`), so an install cut short even by a kill -9 can be undone by `uninstall`.

**Rollback.** A failure part-way through undoes itself. Tested on 2026-09-29, with the
installer of that day, by placing a directory where `lbl_map.tpc` went in the override
folder: the copy failed, the installer reported it, and the app bundle's file
list and sizes, `KOTOR_Exe`'s hash, the state directory and `swkotor.ini` all matched the
state before the install. *Corrected 2026-09-29:* the first version of the rollback hung it on an `EXIT`
trap and never ran, leaving a half-installed game. zsh does not run `EXIT` when errexit
ends the script; it runs `ZERR`. The same test caught it, and both traps now run the
rollback.

### The menus inside the module

Since 2026-10-04 KMRP's patch (`KMRP-macOS.kpatch`; `kmrp.kpatch` until 2026-10-08) brings its
own menus, as Windows' does: ticked by hand in KotOR Patch Manager with the two patches it
requires, with no installer run, it is the whole of KMRP's interface. What Windows does is in
`src/controller-native/K1RuntimeAssets.cpp`; the Mac follows it in its own terms.

| | |
| --- | --- |
| The bank | `tools/make_kmrp_assets.py`: KMRP's artwork, the bundled third-party art, all 66 menu sets and `gui-blend.bin`, each distinct file once, zlib-compressed, linked into the module as the section `__KMRP,__assets`. In the build measured on 2026-10-04: 335 artwork files (SDL among them then; it is the controller patch's since 2026-10-07), 520 of third-party art, 17,127 objects, 158,594,907 bytes. Since 2026-10-08 the bank leaves out what the module makes itself, as Windows' does since 2026-10-05: the module's blend helper writes most layouts and badges of most sizes exactly as the build's set has them, `make_kmrp_assets.py --helper` runs it for every set (as x86_64 code, like the module's copy) and stores an object only where some file that needs it is not what the helper writes, and `BuildSet` in `assets.cpp` writes the bank's files, runs the helper, puts the bank's back where the helper differs and holds every file against the set's index. Measured that day: 216,600,987 bytes with every object (32,135 objects), 104,605,483 like this (3,865 objects; 59,285 of the sets' 64,482 files left to the module; 45 sets rebuilt whole, 20 in part, 1280x1080 stored whole). `Test-MacAssets.py` with `KMRP_ALL_SETS=1` made all 66 sets through the module and each was the build's, byte for byte; in the game, 1512x982 (867 files made, 65 of the bank's put back) and 3024x1890 (blended) were seen |
| The code | `patches/kmrp-assets/assets.cpp`, with the installer's three helpers compiled in (`tools/kmrp-guiblend.c`, `kmrp-abilityicons.c`, `kmrp-gameart.c`) |
| When | the game's start-up registers its resource folders one after another; a detour on its call for `OVERRIDE:` (`0x10026c739`) makes that call and then registers KMRP's two folders, the artwork and the size's set. A folder registered later is searched first, so the set wins over the artwork and both over the game's override folder |
| The size | the widescreen patch's target: `ForceWidth` and `ForceHeight` when `swkotor.ini` has them, else `Width` and `Height` when the display reports that size, else the display's size in points ("The resolution chosen in the game") |
| A size without a set | the nearest set by height, then shape, with the files `kmrp-guiblend` blends over it: the installer's procedure, run by the module the first time the game starts at that size |
| Bundled art | left out of this run's artwork folder when the game's override folder already has that texture, as `.tga` or `.tpc`: the installer's rule, applied each launch |
| `UseGuiFileLayouts` | no longer written to `swkotor.ini`. KMRP's module asks the Widescreen Patch for its `.gui` mode through `K1Widescreen_UseGuiFileLayouts(1)` whenever it has menus for the size (`patches/kmrp-assets/layouts_ini.cpp`, `widescreen.cpp`). The player's file is not changed. For a size the sets do not cover, nothing is asked and the widescreen patch lays the menus out itself. (On 2026-10-04, for the hours the widescreen patch was still compiled into `kmrp.dylib`, it was compiled with `-Dfopen=kmrp_ini_fopen` and a reader added the key to what it read; that reader is still what KMRP's own parts read the file through) |
| SDL | not in this module since 2026-10-07: the controller patch carries it and unpacks it to its own cache (section 7a) |

Measured on 2026-10-04 (macOS 27.0.1, Apple Silicon, the Steam game):

| Check | Result |
| --- | --- |
| The files the game is given at 1512x982 (a set of its own) and 1800x1169 (blended), against the installer's procedure run with the same tools | 1,756 and 1,855 files, every name and every byte the same (`testing/regression/Test-MacAssets.py`) |
| `kmrp.kpatch` alone (that day's one patch, with FTD's two inside it), applied to the untouched game by KPM's patch-options build (`90b5602`), no installer, empty override folder, no `UseGuiFileLayouts` in `swkotor.ini` | the game started at 1512x982, the module logged both folders registered, and the Options screen is KMRP's |
| That Options screen against the same screen after an install by the installer of the build before (files in the override folder), same size | 2,362 of 1,484,784 pixels differ by more than 8 of 255, at most by 24 |
| The new installer at 1920x1200, then the game | 8 files recorded, nothing in the override folder; SDL loaded from the cache; the 1920x1200 set registered |

Not measured: how long the first start takes while the store is unpacked; a display other
than the built-in one; `Test-MacAssets.py` and the file counts above against a build since
the controller's files left this module (2026-10-07).


### The resolution chosen in the game

Since 2026-10-04, as on Windows (`src/controller-native/K1RuntimeResolution.cpp`,
`K1RuntimeLayout.cpp`). The Mac's code is `patches/kmrp-assets/resolution.cpp`, `layout.cpp`
and `layouts_ini.cpp`.

What the engine does by itself (KOTOR_Exe 1.4.0, read with Ghidra): Options, Graphics, Screen
Resolution (`CSWGuiOptionsResolution::OnResolutionChosen`, `0x1002cd6f8`) calls the game's mode
switch (`0x10026ef34`), which reads the mode from Aspyr's list, stores its size
(`0x1005d3b8c`, `0x1005d3b90`), re-initialises the renderer (`Global::ReInitAurora`,
`0x1004ac827`), resizes the GUI manager (`0x10049ffdc`) and loads the main menu and the options
screen again; then the popup writes `Width`, `Height` and `RefreshRate` to `swkotor.ini`.
Before this work the switch changed nothing on screen: everything was laid out for one target
size, fixed at start (measured: 1024x768 chosen, viewport still 1512x982, `Width=1024` written).

| Piece | Where | What it does |
| --- | --- | --- |
| The list | `KmrpResolutionKnown`, a detour at `0x10026f1ee`, the game's whitelist of five sizes | a size is accepted when KMRP has menus for it and the display reports a mode of it, in points or in pixels (since 2026-10-08; from 2026-10-04 any size KMRP has menus for, which listed Aspyr's own 1280x720 and 1344x756 on a display with no such mode). `kmrp-layout` no longer writes the one configured size into that whitelist (it did from 2026-10-02 to 2026-10-04: [the port audit](../reverse-engineering/macos-resolution-port-audit.md)) |
| Retina modes | the Widescreen Patch's own hook at `0x10001de6c` | the display's pixel/point ratio always, so Aspyr's list has every mode's pixel twin whatever size the game started at. Until its adjustment of 2026-10-04 that patch gave the ratio only for a start above the point size, and KMRP's module, which still contained the patch, took the hook with a function of its own (`KMRP_DisplayModeScale`, compiled now only under `KMRP_BUNDLED_WIDESCREEN`) |
| The switch | `KmrpModeSwitch`, a detour on the call to `ReInitAurora`, `0x10026f0ec` | before the call: the widescreen patch's target set through `K1Widescreen_SetTargetResolution`, which applies that patch's size-dependent sites again, the new size's set registered under a new alias so it is searched first, and every font's TXI read again (`0x1001f866a` over the texture array `0x100635b58`). After it: the drawing surface resized |
| The surface | `CGLSetParameter(kCGLCPSurfaceBackingSize)`, at the switch and once a GUI frame | Aspyr sizes its fullscreen surface once; without this a smaller mode was drawn into a corner of the old surface and a larger one cut off |
| Existing panels | detours at `CSWGuiPanel::StartLoadFromLayout` `0x10049dfe4`, `InitControl` `0x10049e476`, `~CSWGuiPanel` `0x10049d8c8`; applied in the GUI frame | each control bound by tag gets the extent the new size's layout file has for it, keeping what the game's code had added, scaled by `max(1, height / 720)` |
| The size at start | `layouts_ini.cpp` | `Width` and `Height` in `swkotor.ini`, when the display has a mode of that size in points or pixels and KMRP has menus for it, are handed to the widescreen patch as its target when KMRP's module loads (`K1Widescreen_SetTargetResolution`; since 2026-10-07, see below); otherwise the game starts at the display's current size. `ForceWidth` and `ForceHeight`, when the file has them, still win |

Measured on 2026-10-04 (14" MacBook Pro, built-in display, 1512x982 points, 3024x1964 pixels,
fullscreen, the Steam game driven by the dev kit):

| Check | Result |
| --- | --- |
| The list | 1147x716 … 1512x982 … 3024x1964 at 120 Hz, the current size selected |
| 1512x982 to 1024x768, from the Graphics screen | viewport and surface 1024x768; Options and the main menu drawn for 1024x768 with their text intact; 36 extents set on 9 panels |
| 1512x982 to 3024x1964 | viewport and surface 3024x1964; the Graphics screen that was open, Options and the main menu laid out for it |
| A start with `Width=3024`, `Height=1964` | the game starts at 3024x1964, surface 3024x1964 |
| Without the font reload | every label garbled after a switch (seen before it was added) |

Tested 2026-10-07 with the scripted pad, a game loaded: 1512x982 to 1280x720 and 1280x720 to
2688x1512, the HUD and all eight in-game screens afterwards, and a restart at each size (the
size last chosen is handed to the widescreen patch when the module loads, `layouts_ini.cpp`,
since that patch reads `swkotor.ini` itself). That day 1280x720, which is no mode of this
display, was still listed and was kept for the next start through a record of the choice
(`chosen-resolution.txt` in KMRP's cache). Since 2026-10-08 neither holds: a size the display
does not report is not listed and not used, and the game starts at the display's own, which
is Windows' rule. No run in the game is recorded for that change.

Not tested: windowed mode,
several switches in a row back to a size already used, an external display, the movies after a
switch. 1024x768 is not one of this display's modes; it was reachable only while the list still
held the game's five sizes, and is no longer offered here.

### List rows, centred in their box

A list's box is part of its panel's artwork (the panel's FILL texture, stretched over the
panel), and the rows' rectangle the layout file gives is not centred in it: at 1512x982 the
inventory's rows began 17 dark columns after the box's left border and ended 7 before its
right one. Since 2026-10-04 the module centres them, for the lists whose box is in the artwork:

| What | Where |
| --- | --- |
| Per set and list, how far right of centre the rows' rectangle is | `macos/tools/measure_list_rows.py` writes `macos/patches/kmrp-assets/list_rows.inc`, from `layouts.zip` and the artwork; `macos/build.sh` fails when the committed file is not what they measure to |
| Per kind of row, how much further in its artwork begins on the left than it ends on the right | `RowInset` in `macos/patches/kmrp-assets/layout.cpp`, fitted to the game's picture at four sizes |
| The row's rectangle, moved left by the sum and made as much wider | `KmrpListRow`, a detour at the three places `CSWGuiListBox::OrganizeControls` hands a row its rectangle (`0x1004a88be`, `0x1004a8950`, `0x1004a89be`) |
| A list made wider instead, where the box reaches further right than the rows (store, workbench) | `KmrpPanelLoaded`, a detour after `CSWGuiPanel::StopLoadFromLayout`'s prologue (`0x10049d98c`; the entry is the controller's hook) |

The lists: the inventory, the abilities (skills, and the charts of powers and feats), the
quests, the quest items, a party member's scripts, the store's two, the workbench's items,
and the feats and powers of character generation and level-up. A size with no set of its own
takes the mean of the three sets nearest in shape and height. What was seen in the game and
what was only measured from the artwork is in `CHANGELOG.md`, 2026-10-04.

After the resolution is changed in the game, a list that already existed takes the new
size's PADDING and scrollbar width (`Relayout`), and the abilities' rows, which are made once
with their panel, take the new size's row height when the list is next filled
(`KmrpListAddRows`, a detour at `CSWGuiListBox::AddControls`, `0x1004a9be6`).

To measure a list again: `KMRP_LIST_ROWS_LOG=<file>` in the game's environment writes each
list and row kind (its vtable) once as it is laid out.

### KMRP on FTD's patches, and the controller as a patch of its own

Since 2026-10-04 KMRP's patch `requires` FTD's two patches instead of containing them. From
2026-09-30 until then `kmrp` was built with a copy of both inside it and declared a conflict
with them. Since 2026-10-07 the controller is a fourth patch, `kmrp-controller`, described in
section 7a; `kmrp` no longer contains it, has no `controller` option, and does its own work
in the GUI's frame at `0x10049f63e` (`KmrpCoreGuiFrame`), the instruction after the entry the
controller patch hooks. The table of the four is at the top of section 1; what follows is how
`kmrp` sits on FTD's two.

| | |
| --- | --- |
| The build | `tools/make_kmrp_patch.py --split`: KMRP's parts only. FTD's two are built from the KPM tree with its own `Patches/create-patch.py` (`build.sh`), and the patches are staged together by KPatchCore, whose overlap check then covers them |
| Hooks FTD's patches already declare | left out of `kmrp` when identical: five, the four memory-safety fixes (`0x1001d0663`, `0x1001fa2bf`, `0x1001e00cd`, `0x1001e1627`) and the Scripts Enter fix (`0x1002d3e34`), which FTD's Stray Bug Fixes carries. `kmrp`'s parts declare 29 hooks and the patch has 24. A different hook at the same address stops the build |
| The `.gui` mode | asked for from KMRP's constructor through `K1Widescreen_UseGuiFileLayouts(1)`, so `swkotor.ini` needs no `UseGuiFileLayouts`. KPM loads a patch after the ones it requires; the Widescreen Patch writes its mode when the engine first sets its video mode, which is later |
| A change of resolution | `K1Widescreen_SetTargetResolution(w, h)`, which applies that patch's size-dependent parts again; KMRP then registers the size's set, reads the fonts again and lays the panels out |
| Finding those entry points | KotorPatcher loads each module privately: `patches/kmrp-assets/widescreen.cpp` looks in `patches/k1widescreenpatch.dylib`, opened with `RTLD_NOLOAD` |
| The layout sites | not written by KMRP (`kmrp-layout`'s 16 groups, section 4): the Widescreen Patch's `.gui` mode writes them. With debug logs on, `~/Library/Logs/KMRP/layout-sites.log` lists each site as found beside what KMRP would write |
| A Widescreen Patch without the entry points | KMRP's menus are not used that run (its files laid out by that patch's own layout would be laid out twice), and the module says so on stderr |
| The installer | takes each module out of its `.kpatch` into `patches/<id>.dylib`, records the patches in KPM's state, and puts the `.kpatch` files in KPM's patch folder; a Widescreen Patch there from before the entry points is copied aside and put back at uninstall |

The entry points were written for this on 2026-10-04 and sent to FTD (the write-up is in his
patch's `KMRP-ENGINE-FIXES.md`, "Entry points for a patch that brings its own menus"). They
were merged into KotOR Patch Manager on 2026-10-05 (LaneDibello/Kotor-Patch-Manager#319,
merge commit `7546ae5`), so KMRP builds on FTD's patches as upstream has them, unchanged.
This repository's submodule (`2a784bf`, section 9) is from before them: `build.sh` refuses
its Widescreen Patch and needs `--kpm` with a KPM tree that has the entry points.

Measured on 2026-10-04 (14" MacBook Pro, the Steam game, fullscreen):

| Check | Result |
| --- | --- |
| Installed by KMRP Installer | 12 files recorded; `patches/` holds the three modules of that day (the controller was still inside `kmrp`); KotorPatcher applied 100 hooks (16, 45 and 39), none refused |
| The Options screen at 1512x982 against that of the build with FTD's patches inside `kmrp` | 2,272 of 1,484,784 pixels differ by more than 8 of 255, at most by 14 |
| The 53 sites of `kmrp-layout`'s 16 groups, as the Widescreen Patch's `.gui` mode left them | 41 hold KMRP's bytes exactly, 11 a jump or call to that patch's stub, 1 vanilla (the area map, done another way there) |
| 1512x982 to 3024x1964 from Options | viewport and surface 3024x1964, 36 extents set on 9 panels |
| The controller part | loads, replaces `GetJoystickBuffer`, loads SDL from the cache |

Not tested that day: a controller in hand; a loaded game (the HUD, inventory, the area map, a
conversation), which is where the Widescreen Patch's own stubs now do what KMRP's did. The
HUD, the eight in-game screens and the map were seen on 2026-10-07 (above, and section 7a);
no conversation is recorded as seen since the Widescreen Patch writes those sites.
**Not tested:** the patches ticked by hand in KPM's window rather than installed
by the installer or staged by KPM's command line.

## 3. What the map-note part writes

One detour, in `patches/kmrp-map-notes/`, a part of `kmrp` (a patch of its own until
2026-09-30). The hook is always installed; its handler does nothing when the patch's
`map-notes` option is off:

| VA | FILE | length | original | kind | purpose |
| --- | --- | --- | --- | --- | --- |
| `0x1002b4f52` | `0x2b4f52` | 7 | `83 BB F4 02 00 00 00` (`cmp dword [rbx+0x2f4], 0`) | detour | `KMRP_CorrectMapNotePosition(rbx)` |

`CSWGuiMapHider::Draw`'s note loop resolves each note to its object in `rbx`, tests the
map-note flag at `+0x2f4`, and then reads the world position the conversion needs:

```
1002b4f52  cmp   dword ptr [rbx + 0x2f4], 0      ; <- detour; the je after it reads these flags
1002b4f59  je    0x1002b536d
...
1002b4f72  movsd xmm0, qword ptr [rbx + 0xd8]    ; x, y
1002b4f7a  movss xmm1, dword ptr [rbx + 0xe0]    ; z
1002b4f82  call  0x100440350                      ; in-map test
1002b4fac  movsd xmm0, qword ptr [rbx + 0xd8]    ; again, for the world->map conversion
```

The detour rewrites x and y at `+0xd8` when the pair is a key of Derslok's table (bitwise,
on the module's own floats). The cut instruction has no RIP-relative operand, and KPM's
wrapper re-executes it after the call, so the `je` sees its flags. `HitCheckMouse`
(`0x1002b5672`) does not read these fields: it tests the note controls `Draw` positions, so
clicks follow the moved markers. The layout patch's conversion call at `0x1002b4fca`
(section 4) comes after this site and does not overlap it.

The table (`note_table.bin`, SHA-256 `880a325d…caa5`, 250 entries) is embedded at build
time by `tools/make_map_notes_table.py`, which refuses repeated keys and a corrected
position that is itself a key (none are: in-place correction cannot chain).

**Verified in play:** at Manaan West Central, three notes moved onto the door and terminals
they name, compared with the same save before installing.

**Rejected:** correcting inside the widescreen patch's own world-to-map bridge
(`MapHider_WorldToMapCoords`), which worked in a test build. It made a content mod part of
the layout patch, which this data's GPL-3.0 licence and FTD's MIT patch argue against.

## 4. What the layout part writes

`patches/kmrp-layout/`, a part of `kmrp`. What it installs through KotOR Patch Manager's
hook list today: the [menu-input hooks](../reverse-engineering/macos-keyboard-navigation.md)
(five detours and one byte patch), the five text-height hooks
(`CAurGUIStringInternal::GetIdealPixelHeight` and the font-height getter, rounded up),
and `KmrpCoreGuiFrame`. The four memory-safety hooks and the Scripts Enter fix in its hook
file are FTD's Stray Bug Fixes' in the shipped patch (section 2, "KMRP on FTD's patches").

**The resolution-dependent sites below are not written by this part since 2026-10-04.**
FTD's Widescreen Patch took them over in its `.gui` mode (his update of 2026-10-03:
`InstallListboxPaddingFix`, `InstallAreaMapLayout`, `InstallMessageBoxLayout`,
`InstallDialogueReplyStretch`, `InstallCheckboxScaling`, `InstallGrantedPopupLayout` and
its row constants) and applies them again when the resolution changes; with that patch a
patch of its own, `kmrp-layout` writes none of them (`g_widescreenOwnsLayout`,
`kmrp_layout.cpp`). Measured 2026-10-04 at 1512x982: of the 53 sites of the 16 groups, 41
held exactly the bytes this part writes, 11 a jump or call to that patch's own stub, and
one of the area map's four was left vanilla by another route to the same end. The table
stays as the record of each site and its Windows counterpart, and it is what
`Test-KmrpLayoutPatch.py` checks this part's code against.

How this part writes them, where it does (a build with the widescreen patch inside the
module): the constructor writes its sites before the game's code runs. Every site is
checked for the bytes it must hold first, group by group; a group whose sites hold anything
else is left alone and named on stderr. The resolution is the widescreen patch's target
(section 5). Sizes scale by the Windows
rule `s = max(1, H / 720)` and are computed as the Windows installer computes them (single
precision, rounded half to even). The full site list and the reasoning for each is in the
sources' comments and, against the Windows sites, in `WINDOWS-PARITY.md`.

| Source | Group | Sites | Windows |
| --- | --- | --- | --- |
| `resolution_sizes.cpp` | text-list rows `×s` | a stub over `CSWGuiButton::Initialize`'s rect copy (`0x1004a5a05`) | the row float and hook at `0x00417992` |
| | inventory rows `56s` | icon `0x1002be441`, height `0x1002be870`, text offsets `0x1002be4da`, `0x1002be4e1` | `RowSizeGroups` |
| | store rows `56s` | height `0x1002bff6d` (the icon follows it by the widescreen patch's hook) | `RowSizeGroups` |
| | skills rows `50s` (vanilla 42; `42s` until 2026-09-30) | icon `0x10022f256`, height `0x10022f60b`, text offsets `0x10022f297`, `0x10022f29d` | `RowSizeGroups` |
| | stack-count label `21s`/`42s`, `37s`, `19s` | the label block `0x1002be4a0` re-encoded with 32-bit operands; the store's label x `0x1002bfbc0` | `StackCountSites`, `.ksc` |
| | feat and power chain rows `50s` | the rect's height at `0x100570efc` | `RowSizeGroups` |
| | message popup: caps `800s`, `450s`, icon `64s` | `0x100306877`, `0x10030687f`, `0x10030688b`, `0x1003068fd`, `0x1003065a1`, the icon rect at `0x100571bb0` | `PopupSizeGroups` |
| | Options check boxes: circle `25s`, label `30s`, drop `2s` (2026-09-30) | `CSWGuiOptionsCheckbox::SetExtent` (`0x1002cecee`) replaced by a jump into the module | `0x006DE012`, `0x006DE031`, `0x006DE08E` (since the same evening; `docs/windows-changes-from-macos.md`, item 13) |
| `popup_fit.cpp` | the message popup fitted to its contents, centred (2026-09-30) | `FixMessageLabel`'s last call (`0x100306a88`), through the near page's third thunk | `FitMessageBoxK1` at `0x006258E2` (since the same evening; `docs/windows-changes-from-macos.md`, item 1) |
| `granted_popup.cpp` | the granted popup's rows: text inset `row/8`, hex grown `row/7`, pitch `row + row/11`, OK and panel fitted, centred (2026-09-30) | the fill's call to `AddControls` (`0x10028ea4f`) and the row's text-rect call in `CSWGuiInGameSkillEntry::SetExtent` (`0x10022f321`), through the near page's fourth and fifth thunks | `GrantedPopupFilledK1` at `0x006CE0B0`, `GrantedRowTextK1` at `0x006AB9D5` (since the same evening; `docs/windows-changes-from-macos.md`, item 10) |
| `dialogue_replies.cpp` | the dialogue reply list stretched to its panel (K7; 2026-09-30, when the widescreen patch dropped its hook) | `CSWGuiDialogCinematic::SetExtent`'s width copy (`0x100244d7d`), through the near page's sixth thunk | `.klb` |
| `listbox_padding.cpp` | `PADDING` a gutter on the scrollbar's side | five reads zeroed in `OrganizeControls`, and stubs for its row block (`0x1004a8838`) and the single-row layout (`0x1004a937a`) | gold v11, v12 (`.klb`, `.kgs`) |
| `area_map.cpp` | canvas and marker overlay | the map screen's two rect constants, `0x100571390`, `0x1005713a0` | `ResolutionPatch` map fields |
| | marker positions | stubs for the three world-to-map calls in `CSWGuiMapHider::Draw` | the `.kui` wrappers |
| | marker sizes `×min(s, 127/16)` | 14 sites in `Draw`, the `mm_barrow` rect, a private copy of `lbl_mapcircle`'s | `MarkerSizeSites`, `MarkerOffsetSites` |

Code that does not fit where it goes (the stubs) lives in the module; the game reaches it by
a 14-byte absolute jump, or, where only a 5-byte call or a 32-bit displacement fits, through
a page the module allocates within 2 GB of the game's code (at `0x101000000` or above, where
KotorPatcher also places its wrappers). `testing/regression/Test-KmrpLayoutPatch.py` checks
every site against the unmodified executable (51 sites at 76 resolutions), every value
against the Windows formula, every rewritten instruction and stub by disassembly, that no
site overlaps a widescreen-patch hook except the two declared, and that the module has a
single load-time initialiser. *Found 2026-09-29:* a global `std::vector` of vanilla bytes was
still empty when the constructor ran, so its group was refused in game; the last check
exists for that.

**What the Windows patch changes that the Mac does not need:** the minimap guard
(`0x0062B39B`), because on the Mac only the map screen's constructor reads the map's rects,
and the area-map hit-test wrapper, because the widescreen patch's recentring already matches
`Draw` and `HandleMouseInput`.

## 5. Resolution

Since 2026-10-04 the resolution is chosen in the game, not at install (section 2, "The
resolution chosen in the game"), and since 2026-10-08 the installer app has nothing to choose,
as on Windows.

| Who | What happens |
| --- | --- |
| KMRP Installer | runs `kmrp-mac.sh install --resolution current`: the game starts at the size macOS is set to, the display's size in points ("Looks like" in System Settings, Displays) |
| `kmrp-mac.sh` by itself | on a display with more pixels than points it asks, current or Retina, unless `--yes` (current) or `--resolution current\|native` decides (`half` is accepted for `current`); `--size WxH` sets any size of at least 640x480 (a window, another display) |
| What is written | the size as `Width` and `Height` under `[Graphics Options]` in `swkotor.ini`, the game's own keys, when it is the main display's size in points or in pixels; `ForceWidth` and `ForceHeight` for any other `--size`, which the game's own list cannot change |
| At start | the game starts at `ForceWidth` and `ForceHeight` when the file has them; else at `Width` and `Height` when the display reports a mode of that size, in points or pixels, and KMRP has menus for it; else at the display's own size in points |
| In the game | Options, Graphics, Screen Resolution lists the display's modes, each with its twin at the display's pixels; a choice takes effect at once and the game writes it to `Width` and `Height` |

| size | frame the game renders on a 14" MacBook Pro |
| --- | --- |
| native ("Retina") | 3024x1964, every pixel of the panel |
| half ("current", the installer's) | 1512x982, the point size, the resolution macOS is set to, scaled up 2x by macOS |

The default is the point size since 2026-10-01 (native until then: a player reading
1512x982 in System Settings took 3024x1964 for a wrong guess). Until 2026-10-04 the choice
was made at install and written as `ForceWidth`, `ForceHeight` and `UseGuiFileLayouts=1`.
KMRP Installer offered both sizes of the display and a size of the player's own until
2026-10-07, when its step 3 became a checklist of sizes for the game's list, removed the
next day (section 1, "Resolutions"). On a display whose pixels are its points there is
nothing to choose.

Native needs engine fix K9: without it the pixel size was not a valid display mode,
and 3024x1964 rendered into a 1024x768 surface, cropped. With K9 and `ForceWidth`/
`ForceHeight`, fullscreen through Aspyr's launcher: surface and viewport 3024x1964, backing
scale 2.00, and clicks land where they are drawn (2026-09-29).

Frame times in game (M5, Manaan West Central, measured with the widescreen patch's own
layout; the layout patch adds nothing per frame, as it writes only at start-up):

| | Anti Aliasing=6 | Anti Aliasing=2 | Anti Aliasing=0 |
| --- | --- | --- | --- |
| half, 1512x982 | 7.5 ms | | |
| native, 3024x1964 | 32.5 ms | 8.0 ms | 8.2 ms |

At native, 6x anti-aliasing costs about 4x; at 2x it runs as fast as half did at 6x. The
installer leaves the anti-aliasing setting alone; the player README recommends 2x for
native.

## 6. Menus and fonts

**Listed sizes.** KMRP's module carries every resolution KMRP's build lays out: the 49 Windows
sizes and 17 Mac ones (`GROUPS["macOS"]` in `prepare_universal_resources.py`, from the 13"
to the 16" MacBook Pro and the external displays Macs ship with, native and half). They are
pooled as the Windows installer pools them (`tools/pack_resolution_layouts.py`):
45,540 files, 18,167 distinct, 86.7 MB. A listed size gets its set exactly: the same `.gui`
files, the same fonts baked at `max(1, H / 720)` with their metrics at that scale, the same
row-frame and tutorial art the Windows installer writes for it. The widescreen patch scales
no font with the switch on, so a texel of the atlas is a pixel on screen, as on Windows.

**Other sizes.** For a size with no set, the `.gui` files are blended from the finished
sets around it (`kmrp-guiblend` over `gui-blend.bin`: the two aspect-ratio families on
either side, each at the two heights around it) and the fonts are those of the nearest set
by height, then shape. Since 2026-10-04 the module does this the first time the game starts
at such a size, with the helper compiled in; until then the installer ran the helper at
install, which is what "the installer" and "at install" mean in the dated passages below.
The package still carries `kmrp-guiblend` and `gui-blend.bin`, with which `kmrp-mac.sh`
asks whether a `--size` can be blended at all. Some layouts are not blended but made for the size (since
2026-09-30): the Container, widened by the build's own rule until "Switch To Give Item" and
its badge fit, with that set's fonts; the Controller Layout screen, which the helper lays out
with `build_gui`'s arithmetic; and (`gui-blend.bin` version 4) the lists the build makes as
tall as whole rows, fitted at the size's own row heights (`WINDOWS-PARITY.md`, *Resolutions
the build has no set for*). Measured by hiding each finished set and predicting it from the
others: 99.89% of numeric fields within 1 px; the 17 Mac sets, held out, 99.90% within 1 px,
every file counted, worst 12 px in a HUD variant the Mac does not load; the Controller
Layout screen exactly, and the Container 491 of 493 fields (`Test-GuiBlendHelper.py`, which
also requires the helper's Controller Layout to equal `build_gui`'s own, byte for byte, at
24 sizes). *Corrected 2026-09-30:* the 99.90% of 2026-09-29 left the Controller Layout
screen out as a file the Mac never loads; it loads it since the controller was ported, and
blended it was up to 32 px off at the Mac sizes. The tutorial
icons of the nearest set can be a few pixels off `64s` for the blended size, and the engine
draws them one texel per pixel, so the layout patch sizes the popup's icon rect from the
installed icon instead (the same `64s` for every listed set: all 66 checked). Since
2026-09-29 the installer makes the icons itself at exactly `64s` for any size, blended ones
included, so the icon it reads is always that.

*Corrected 2026-09-30:* this said the installer takes the nearest set's art as well as its
fonts, and so it did until then: its controller badges, drawn for that set's buttons, were
stretched on blended buttons of another shape, up to 1.86 times as wide as tall at 3440x1400
(measured on the blended files, on both platforms). Since `gui-blend.bin` version 3 on master
(version 4 since the merge with the macos branch's row fits, the same day) the helper
draws every badge again for its blended button, with the build's own arithmetic, and the HUD's
button-row boxes (`lbl_mileftbot.tga`) from the blended HUD; a set the blend resolves to itself
comes out with the build's files byte for byte. Written and tested on Windows first
([`docs/macos-changes-from-windows.md`](../docs/macos-changes-from-windows.md), items 1 to 3);
on the Mac the module's blended set for 1800x1169 was compared with the helper's, file for
file, on 2026-10-04 (`Test-MacAssets.py`, section 2).

**Made from the player's game.** The four hex frames list rows tile behind item icons
(`lbl_hex*`, `56s`), the tutorial popup's thirteen `tut_*` icons (`64s`) and `tutorial.2da`
(the game's own table, its `icon` column pointed at those copies) are made by
`kmrp-gameart` (at install until 2026-10-04; since then by the module, which has it compiled
in, the first time the game runs at a size), from `TexturePacks/swpc_tex_gui.erf` and, through `chitin.key`,
`data/2da.bif`. Until 2026-09-29 the resource build exported them from the build machine's
game and the package carried them. `GameArtGenerator.cs` does the same on Windows, byte for
byte (`Test-GameArt.py`), and the sizes are the ones every set shipped (1,122 textures
checked). If either file cannot be read, none is made and the game keeps its own.

**Feat, power and skill icons.** The engine draws them at their texture's size in rows
that grow with `s`. `kmrp-abilityicons` enlarges every uncompressed square `i_*` and `ip_*`
texture of the game's `swpc_tex_gui.erf` to `round(50s) − 4`, and the eight `isk_*` skill
icons to a canvas of `round(32s x 50 / 42)` (`round(32s)` until 2026-09-30, when the skill
rows moved to `50s`), each at most twice its size -- the skill picture inside it
`round(0.62 × 50s)`, centred and moved `(round(−0.5s × 50 / 42), round(−2s × 50 / 42))` to
the frame opening's centre, so it sits inside its frame (since 2026-09-29; before, it filled
the canvas and covered the frame's border) -- as `AbilityIconGenerator.cs` does on
Windows, byte for byte (`Test-AbilityIcons.py`: 2,688 icons at 10 heights, both slices).
Without them the feat and power icons stayed 32 px in 136 px frames at 3024x1964 (seen
2026-09-29), and the skill icons 32 px in rows of 115 (`42s`; reported from play the same
day). The skill icons are new on both platforms that day; at 3024x1964 they are 64 px, the
2x cap.

**Item icons.** They come with the artwork, from the resource build Windows uses: the HD
Icon Pack, with each picture sized to 39/64 of its canvas, the size of the game's own
icons, so items sit in their slots as vanilla's do (`ICON_PICTURE_SPAN` in
`tools/prepare_universal_resources.py`; the CHANGELOG has the measurements).

## 7. Controller

`patches/kmrp-controller/` is KMRP's Windows controller module (`src/controller-native/`:
`K1NativeJoystick.cpp`, `K1Rumble.cpp`, `K1ControllerLayout.cpp`) ported to this executable,
with the same bindings, event ids, tables, rumble patterns and art. Since 2026-10-07 it is a
KotOR Patch Manager patch of its own, which section 7a describes: how it is packaged, its
files, the badge overlays and the Xbox-style HUD. This section is the port itself. What it does and why is
written once, for Windows, in [`docs/controller-support.md`](../docs/controller-support.md)
and the documents it links; this section covers what the Mac changes. The sources name each
Mac address beside the Windows one it stands for.

**Why a port.** KOTOR I on the Mac has no controller support that works: a pad that works in
other macOS apps did nothing in play (2026-09-29), and Aspyr lists controllers for KOTOR II on
the Mac only. The executable keeps the PC's joystick input chain, which the Windows module
feeds, and a rumble subsystem whose output Aspyr stubbed: `CExoInput::SetRumble`,
`PauseRumble` and `UnpauseRumble` (`0x10035738c`, `0x10035739c`, `0x1003573a2`) return
without doing anything.

**The pad** is read through SDL 3.4.16, the release the Windows installer pins, carried
inside the patch's module and unpacked as `kmrp-sdl3.dylib` to its cache (section 7a; beside
`KOTOR_Exe` until 2026-10-04). Apple's GameController framework, weak-linked, is used only when
that library cannot be loaded, so the two never hold a pad at once. The prompts are drawn in
the pad's family, as on Windows: Xbox, PlayStation, Switch or Steam Deck art (`kmrp*`,
`kmrs*`, `kmrn*`, `kmrd*`).

**Sites.** The patch has 24 hooks: the 21 of the port in the table below, the registration
of the patch's own files (`KmrpControllerResources`, `0x10026c73e`) and the Xbox-style HUD's
two (`KmrpXboxHud`, `0x100237848`; `KmrpXboxHudBars`, `0x100230eee`), which section 7a
describes. Besides them, ten writes the module makes as it loads, each after
checking the bytes or the pointer it replaces; a site holding anything else is left alone and
logged. `FILE = VA − 0x100000000`. *Prologue* below is `55 48 89 E5 41 57 41 56`
(`push rbp; mov rbp, rsp; push r15; push r14`). A *consumed* hook skips the cut instruction
and makes its call itself, because a relative call cannot run from KPM's wrapper.

| VA | len | original | kind | handler (from) | site and purpose | Windows |
| --- | --- | --- | --- | --- | --- | --- |
| `0x100356276` | 13 | prologue, `41 55 41 54 53` | detour | `KmrpControllerTick` (rsi) | `CExoInputInternal::GetEvents`, entry: registers the pad's button descriptions, keeps a pad in the device count, reads it | the input poll, `0x005E23C0` |
| `0x100356ff2` | 6 | `0F 87 02 01 00 00` (`ja 0x1003570fa`) | bytes: `E9 03 01 00 00 90` | — | Aspyr's pad mapping at the end of `GetEvents`, skipped (below) | none: Aspyr's code |
| `0x1002249b2` | 8 | prologue | detour | `KmrpMovementFrame` (rdi) | `CSWPlayerControlCamRelative::Control`, entry: whether the left stick drives | `0x00679940` |
| `0x100224c56` | 5 | `E8 33 A7 14 00` (`Vector::Normalize`) | consumed | `KmrpSkipNormalize` (rdi) | skipped while the stick drives, so the speed follows the deflection | `0x00679B71` |
| `0x100268424` | 5 | `E8 87 11 00 00` (`UpdateCamera`) | consumed | `KmrpCameraFrame` (rdi) | the right stick's turn; L3's flourish, Start's Map, A on the target, R3 out of free look | `0x006039CF` |
| `0x10049f636` | 8 | prologue | detour | `KmrpGuiFrame` (rdi) | `CSWGuiManager::Update`: focus moves, remaps, the party switch, description scrolling, the prompts, the Controller Layout screen | `0x0040CE70` |
| `0x100237a86` | 8 | prologue | detour | `KmrpHudFrame` (rdi) | `CSWGuiMainInterface::Update`: the action bar on the D-pad | `0x00686BA0` |
| `0x100014566` | 7 | `80 BD 51 FB FF FF 00` (`cmp byte [rbp-0x4af], 0`) | detour | `KmrpMovieFrame` (rbp−0x4b0) | Aspyr's movie loop: A and Start skip; the cut test re-runs after the handler | `NativeMovieFrameK1` |
| `0x1003563f3` | 5 | `E8 54 34 00 00` (the keyboard buffer read) | consumed | `KmrpNoteKeyboard` (rdi, rsi) | a key hides the prompts and gives the cursor back | `NativeNoteKeyboardK1` |
| `0x10049d986` | 6 | `55 48 89 E5 53 50` | detour | `KmrpPanelReleaseGff` (rdi) | `CSWGuiPanel::StopLoadFromLayout`: binds the GUI cues and badges while the panel's `.gui` is loaded, forgets them at the base destructor | `0x0040B8F0` |
| `0x1002687f1` | 5 | `E8 00 27 00 00` (`UpdateRumble`) | consumed | `KmrpRumbleFrame` (r13) | the rumble mixer's frame and the pad's motors | `0x005F7617` |
| `0x10027a106` | 6 | `89 F3 31 C0 85 DB` | consumed, exit `0x10027a185` | `KmrpRumblePlay` (rdi, esi) | `PlayRumblePattern`: the pattern goes to the mixer; returns 1 through the function's own epilogue (Windows 0; only a script reads it) | `0x005FB49F` |
| `0x10027a1d2` | 11 | `55 48 89 E5 48 63 87 E8 04 00 00` | detour | `KmrpRumbleStop` (rdi, esi) | `StopRumblePattern`, observed | `0x005F74B0` |
| `0x10027a892` | 8 | prologue | detour | `KmrpRumbleCutoff` (rdi, esi, edx, rcx) | `LookUpAndPerformRumbleWithCutOff`, observed | `0x005FB98E` |
| `0x100359d86` | 8 | `55 48 89 E5 48 8B 7F 08` | detour | `KmrpRumblePause` | `PauseRumble`'s wrapper: the pause the Mac no longer keeps | `CExoInput::PauseRumble` |
| `0x100359d94` | 8 | `55 48 89 E5 48 8B 7F 08` | detour | `KmrpRumbleUnpause` | `UnpauseRumble`'s wrapper | `CExoInput::UnpauseRumble` |
| `0x1002d150e` | 8 | prologue | detour | `KmrpSaberPower` (rdi, esi) | `CSWCItem::ResolveCreaturePoweredAnimations`: a saber lit or put out | `0x00646BA0` |
| `0x100295f16` | 8 | prologue | detour | `KmrpSaberContact` (rdi) | `CSWCCreature::ShowLightSaberContactVisual` | `0x0060DE20` |
| `0x100296007` | 8 | prologue | detour | `KmrpMeleeHit` (rdx) | the creature animation event "hit" | `0x00617EB0` |
| `0x10033cb7e` | 6 | `55 48 89 E5 53 50` | detour | `KmrpParry` (rdi) | `CSWCObject::AnimationParry` | `0x0063C4F0` |
| `0x1002dd810` | 8 | prologue | detour | `KmrpMuzzleFlash` (rdi) | `CSWCProjectile::CreateMuzzleFlash` | `0x006D4440` |

Written as the module loads (`native.cpp`, `InstallController`; `gui.cpp`, `Install`):

| VA | written | checked first | purpose | Windows |
| --- | --- | --- | --- | --- |
| `0x100358cdc` | 14 bytes, `FF 25 00 00 00 00` and the handler's address | `55 48 89 E5 41 57 41 56 41 55 41 54 53 48` | `GetJoystickBuffer` replaced whole by `KmrpGetJoystickBuffer`: the pad's records, in the engine's own format | `0x005E30F6` |
| `0x10049dc72` | 14 bytes, the same jump to `KmrpPanelHandleInputEvent` | the whole 28-byte function | `CSWGuiPanel::HandleInputEvent` replaced whole: the echo guard | a hook on `0x00409E60` |
| eight vtable slots (`+0x80`), below | 8 bytes each, a wrapper's address | the class's own handler | the confirm guards | `GuardChargenConfirmK1` and the Solo Mode and resolution resolvers |

| Class | vtable | slot | handler the wrapper calls |
| --- | --- | --- | --- |
| Attributes (character generation) | `0x1005b0950` | `0x1005b09d0` | `0x100349572` |
| Skills (character generation) | `0x1005a7820` | `0x1005a78a0` | `0x100250a12` |
| Feats | `0x1005adc40` | `0x1005adcc0` | `0x1002eedd2` |
| Powers | `0x1005abb40` | `0x1005abbc0` | `0x1002c36ba` |
| Portrait (character generation) | `0x1005afea0` | `0x1005aff20` | `0x10033fcca` |
| Name (character generation) | `0x1005aac10` | `0x1005aac90` | `0x1002aa9f4` |
| Solo Mode query | `0x1005abea0` | `0x1005abf20` | `0x1002c826a` |
| Resolution | `0x1005ac3a0` | `0x1005ac420` | `0x1002cdb5a` |

**What differs from Windows, and why:**

- **Aspyr's pad mapping is switched off.** The Mac's `GetEvents` ends with a translation
  Windows does not have: a scan of the first pad's records (`0x100356e39`–`0x100356fc5`) that
  reads them as an Xbox 360 DirectInput pad, then an injection (`0x100356fee`–`0x1003570f4`)
  of a second event per press, by input class. It never ran before KMRP, because Aspyr's own
  pad layer finds no pad. With KMRP's records it doubled bindings, and where the layouts
  disagree it acted on its own: KMRP's Start is button 8, which it reads as L3, Flourish.
  Seen 2026-09-29: a Start press in the world opened the menu and queued a flourish. The
  class check before the injection, `cmp r13d, 5; ja <end>`, becomes a jump to `<end>`.
- **The confirm guards sit in vtables.** On Windows they rewrite the event before the
  class's handler reads it. On the Mac the event is in `esi`, and KPM's x86_64 wrapper puts
  the registers back after a detour's handler, so a detour cannot change it. The wrapper in
  the vtable calls the class's handler itself, with the event it settled on.
- **Mouse use is read from the pointer, not from `HandleMouseMove`.** The Mac's input
  processing calls `CSWGuiManager::HandleMouseMove` only while its own cursor is shown and
  was moved in the last 400 ms (the flag at `0x1005d34e4`, which `0x1003578dc` keeps). The
  hidden cursor of pad play is exactly when it is not, so a hook there never saw a hand go
  back to the mouse. The module compares the pointer Aspyr's frame loop samples
  (`0x10068a188`, `0x10068a18c`) instead. *Rejected 2026-09-29:* the hook at
  `HandleMouseMove`, as on Windows; it never fired while the cursor was hidden.
- **The cursor is parked only while the game is the active application**, since a warp made
  while the player is in another app would move the pointer they are using there, and it is
  **not confined to the window** (Windows' `ClipCursor`): macOS has nothing that keeps the
  pointer in a window and still lets it move.
- **Rumble replaces `UpdateRumble`'s call** instead of reading the motors on the way to
  `SetRumble`, which does nothing here, and keeps the rumble pause the engine no longer keeps.
- **SDL3, then GameController.** The first builds read the pad through GameController alone,
  and the maintainer's pad did nothing in game with them; the first build with SDL3 worked
  (2026-09-29). Which part of that change mattered was not isolated. SDL3 is also what the
  Windows module reads pads through, and it sends the rumble.

**Settings and logs.** Two files have this name. `MacOS/configs/kmrp-controller.ini` holds
the patch's options as KotOR Patch Manager or the installer recorded them (`[Patch Options]`:
`xbox-hud`, `debug-logs`; section 7a). The player's settings file is the other one: rumble
reads `kmrp-controller.ini`, section `[Rumble]`, from the
game's settings folder, `~/Library/Application Support/Knights of the Old Republic/`, beside
`swkotor.ini` (on Windows the file sits beside `swkotor.exe`). The keys, ranges and defaults
are Windows': `Mode` = `Off`, `Original` or `Enhanced` (default); `Strength` 0–100 (100);
`SaberHum` 0–100 (6); `SaberHumPulseMs` 0–1000 (100); `SaberHumPeriodMinMs` and
`SaberHumPeriodMaxMs` 50–5000 (500, 2000); `Debug` 0 or 1. The file is re-read within a
second of a change, and a missing file or key means its default. The installer writes the
file as the Windows installer does (`DefaultSettings` in `KmrpPatcher.cs`, the same text but
for the log's path and LF line ends): only when there is none, never over the player's, and
uninstall removes it only if it is unchanged (section 2). The same file's `[Hud]` section
holds `Style`, `Xbox` or `PC`, read when the game starts (section 7a). The module logs to
`~/Library/Logs/KMRP/controller.log` only with the patch's `debug-logs` option on (since
2026-10-04; every run before, since a game started from Steam sends its stderr nowhere), and
rumble events to `rumble.log` there with `Debug=1`.

**Testing without a pad.** `KMRP_PAD_SCRIPT=<file>` replaces the pad with a script, one
`<seconds> <control> <value>` a line, the controls being `A B X Y LB RB BACK START L3 R3
UP DOWN LEFT RIGHT` (1 pressed, 0 released) and the axes `LX LY RX RY LT RT`.
`KMRP_PAD_FAMILY=s`, `n` or `d` draws its prompts in PlayStation, Switch or Steam Deck art
(Xbox otherwise). The scripted pad has no motors: its rumble is read from the logs.

## 7a. The controller patch

Since 2026-10-07 controller support is a KotOR Patch Manager patch of its own, id
`kmrp-controller`, the Windows patch's id (`tools/make_kmrp_patch.py --controller-patch`).
Its file is `KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch` and its name in KotOR
Patch Manager the same without the extension, since 2026-10-08; for its first day they were
`kmrp-controller.kpatch` and "KOTOR 1 Native Controller Mod + Xbox HUD", Windows' name. The
Windows file, `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`, does not run on the Mac nor
this one on Windows. It requires nothing and conflicts with neither KMRP nor FTD's patches. Windows made the same split on 2026-10-05 and 06
(`docs/macos-two-patches-handoff.md`); the rule there, and here, is that it fits itself to
whatever interface is loaded and takes nothing from another patch.

| | |
| --- | --- |
| The module | `macos/patches/kmrp-controller/` with two shared sources, `kmrp-layout/text.cpp` and `options.cpp` (compiled with `KMRP_CONTROLLER_PATCH`, which reads `configs/kmrp-controller.ini`) |
| Its files | `macos/tools/make_controller_assets.py`: the steps of Windows' `tools/build_controller_assets.py` run on the Mac game's own layouts (`build-inputs/vanilla-gui`, extracted by the build), packed with zlib into the section `__KMRPC,__assets`: 17 layout files, the badge and cue art of four controller families, the Xbox-style HUD's art, SDL. 1,014 files, 9.5 MB |
| Unpacked to | `~/Library/Caches/KMRP-Controller/<build>/files`, once; each run registers a folder of links, `run-<pid>`, with the game's resource manager (`standalone.cpp`) |
| Beside KMRP | the run's folder has no layout file, so KMRP's layouts load (they hold the same added controls); the art is still this patch's own |
| Search order | registered at `0x10026c73e`, the instruction after KMRP's patch registers its menu set, so this patch's art is found first; registered again after the resolution is changed in the game (`RegisterAgain`), since KMRP then adds another set |
| A badge's shape | `overlays.cpp`: where the live button's fill area is not the shape the badge was made for (`src/controller-native/K1ControllerBadgeShapes.inc`, the table Windows compiles, which `build.sh` checks against the Mac bank), the badge is drawn on a label of its own, as tall as the fill area, beside the caption as the caption's own font measures it |
| Hooks | 24: the port's 21 (section 7), the registration of its files, and the two of the Xbox-style HUD; none at an address `kmrp`, the Widescreen Patch or the Stray Bug Fixes hook (`build.sh` stages the four together, and the controller patch alone and with FTD's two) |
| After a change of resolution in the game | the files are registered again, and the badges and cues are placed again for the new size: three fixes of 2026-10-07 (`CHANGELOG.md`, "the pad's badges and cues after the resolution is changed in the game"), in `KmrpPanelControl` of KMRP's patch and `overlays.cpp` here |
| Options | `xbox-hud` (on by default; on Windows too since 2026-10-08, off there until then), `debug-logs`; the installer records only `debug-logs`, as Windows' does, so `Style` under `[Hud]` in the player's `kmrp-controller.ini` decides the HUD: `PC` turns the Xbox-style HUD off. The HUD is shown only while the pad is the device in use |
| The installer | installs it while Controller Support is on (`--no-controller` leaves it out), and delivers its `.kpatch` to KPM's patch folder with the others |

Seen in the game on 2026-10-07 with the scripted pad (section 7, "Testing without a pad"), at
1512x982, the eight tabs of the in-game menu in each: beside KMRP; beside FTD's Widescreen
Patch and Stray Bug Fixes alone (that patch's own layout); and alone on the unmodified game,
driven by the pad from the main menu. In all three the badges are round and stand beside their
captions, and the tab strip has its LT and RT arrows. The Xbox-style HUD (`xbox_hud.cpp`, the
port of Windows' `K1XboxHud.cpp`; on by default on the Mac since 2026-10-07, off with
`Style=PC` under `[Hud]` in `kmrp-controller.ini`, which the installer writes as `Style=Xbox`
and adds to a settings file that has no `[Hud]` section) was seen beside KMRP and alone on the
unmodified game: the action box with the default action and its slots, the focused slot large
with its description, the target's name and bar, the map, the party framed with its bars, and
the game's own HUD back on a key press. A fight, the pause notice and the speech box were not
seen. After a change of resolution in the game (1512x982 to 1280x720, then 1280x720 to
2688x1512, the scripted pad, 2026-10-07, once the three fixes named in the table were in):
Graphics Options, the map, Options, Equip, Inventory, Character, Abilities, Messages and
Quests, every badge beside its caption and round within a pixel, Close and the portraits in
place.

**Not seen:** a real pad, rumble, a fight, a conversation, the store's three badges (no save
reaches a store), and everything added on the evening of 2026-10-07, which the maintainer
tests himself: Level Up and Auto Level Up (`ShowBacked`), the cues placed from live controls
(`cues.cpp`, `Adjust`), the HUD's font and texture clamp, the parked slot's return and the
action box's empty line.

## 8. What is deliberately not installed or changed

| Left out | Why |
| --- | --- |
| The 18 fonts in `override-common.zip` | every set carries them at its own size |
| Driver compatibility, DPI and NVIDIA settings, Large Address Aware | Windows code (K1DC is a `dinput8.dll` proxy with an ASI plugin for the 32-bit `swkotor.exe`); the Mac build is 64-bit. *Corrected 2026-09-29:* this called them Direct3D-specific, but KOTOR renders with OpenGL on Windows too, and K1DC repairs an OpenGL lighting path. Whether the Mac port has the same fallback is **not yet checked**: this Mac's OpenGL (Apple M5, 2.1 on Metal) offers neither `GL_NV_register_combiners` nor `GL_ATI_text_fragment_shader`, the two old paths the executable names, but it does offer the ARB fragment programs and GLSL, which the executable also names |
| Movie fixes | Aspyr's Bink 2 player pillarboxes and switches no display mode (checked in play) |
| `swkotor.ini` beyond the size | only the two keys of section 2 are written: `Width` and `Height`, or `ForceWidth` and `ForceHeight` for a size the display does not have. (Until 2026-10-04 it was three keys, `UseGuiFileLayouts`, `ForceWidth` and `ForceHeight`, and `Width`/`Height` were left alone) |
| Anti-aliasing and other graphics settings | the player's; the README recommends 2x at native (section 5) |
| Update check | the Windows installer's; KMRP Installer for the Mac has none |
| Anything in the game's override folder | since 2026-10-04 (section 2); a mod's files there keep their place, and KMRP's bundled third-party art yields to them |

*Corrected 2026-09-29:* until this date the Mac build used the widescreen patch's own
layout of the vanilla menus, with `NativeResolution`, `FontScale` (`max(1, H × 1.5 / 1964)`,
the maintainer's anchor) and `FullWidthMenus` in the INI, per-scale font sets, and none of
KMRP's `.gui` sets, row-frame art, tutorial icons or enlarged ability icons. It looked
visibly different from Windows (4:3 menus, larger inventory rows, no feat and power row
fix), and was replaced by what this document describes. Those three keys are gone from the
widescreen patch.

## 9. Building

```sh
zsh macos/build.sh --kpm "../third_party/Kotor-Patch-Manager" --exe <clean KOTOR_Exe> \
    --python <venv python> [--reuse-resources]
```

| Option | What |
| --- | --- |
| `--kpm <dir>` | the KotOR Patch Manager tree the runtime, KPatchCore and FTD's two patches are built from. It must have the Widescreen Patch's entry points (upstream since `7546ae5`, 2026-10-05); `build.sh` looks for `K1Widescreen_UseGuiFileLayouts` in `Patches/K1WidescreenPatch/mac_widescreen.cpp` and stops without it. The path above is the clone the maintainer's workspace keeps beside this repository |
| `--exe <file>` | an unmodified `KOTOR_Exe`, when the installed game's own is patched (KMRP's backup copy, `~/Library/Application Support/KMRP/macos/backup/KOTOR_Exe`, is one). Without it the game's own is used and must be unmodified |
| `--python <python3>` | a Python with `requirements.txt` installed |
| `--reuse-resources` | keeps the interface resources of the previous build (`build/kmrp/resources`) |
| `--game <app>`, `--widescreen <dir>` | the game bundle, when it is not in the default Steam library; another `Patches/K1WidescreenPatch` |

**The submodule is not what the build uses.** `third_party/Kotor-Patch-Manager` in this
repository is `RayesDiyab/Kotor-Patch-Manager`, branch `kmrp`, pinned at `2a784bf`: FTD's
`widescreen-patch` (`074972b`, 2026-09-30) with the 11 hooks he moved into *K1StrayBugFixes*
taken out of *K1WidescreenPatch*'s hook list, where they were still declared (KPM's own
check: "Multiple hooks at address"). It is from before the entry points and before patch
options, so without `--kpm` the build stops at the check above. It was the build's source
from 2026-09-30 to 2026-10-04, while `kmrp` carried a copy of FTD's two patches. Earlier
still (until 2026-09-30) the submodule tracked FTD's `widescreen-patch` directly (`71ac5fa`:
KPM's master `5cafa6a` with his widescreen patch and KMRP's fixes, merged there on 2026-09-29
as FTD516/Kotor-Patch-Manager#1, then #2, which builds it with KPM's own `create-patch.py`);
before that the same fixes on `RayesDiyab/Kotor-Patch-Manager`, branch `kmrp-engine-fixes`,
and then FTD's `9884466`. The [audit of 2026-10-02](../docs/ftd-macos-upstream-audit.md)
compared FTD's branches of that day with the pin.

Needs: Xcode command line tools, the .NET 8 SDK, and a Python with `requirements.txt`. The
game must be installed (the build reads `TexturePacks/swpc_tex_gui.erf` for the fonts and
the game's own layouts for the controller patch, and resolves hooks against the unmodified
`KOTOR_Exe`'s hash); nothing from the game is packaged.
Output: `dist/macos/KMRP-macOS-<version>/` (`KMRP Installer.app` and `README.md`), its disk
image (the Mac download: the app and a link to Applications) and its zip (the folder with the
README, for sites that take only archives). The image was 159,273,371 bytes on 2026-10-02,
216,963,724 on 2026-10-08 with the controller patch and every set's files in the module, and
about 114 MB the same day once the bank left out what the module makes (Windows' installer:
about 140 MB).

Steps, in the order `build.sh` runs them:

1. `make dylib` in KPM's `src/KotorPatcher`: `KotorPatcher.dylib`;
2. the map-note table (`tools/make_map_notes_table.py`);
3. SDL 3.4.16: the official `SDL3-3.4.16.dmg`, downloaded once into `build/deps` and refused
   unless its SHA-256 is `675660a9…87fd`;
4. `kmrp-macho` and `kmrp-guiblend`, universal (arm64, x86_64), ad-hoc signed: the two
   helpers the package carries. `kmrp-abilityicons` and `kmrp-gameart` were packaged too
   until 2026-10-04; all three of the art helpers are compiled into KMRP's module now;
5. `prepare_universal_resources.py` exactly as `build_kmrp.ps1` runs it, with the
   per-resolution fonts of `build/fonts` (`tools/build_font_scale_sets.py`) when they are
   there (`--reuse-resources` keeps the previous output). *Corrected 2026-09-29:* this step
   never passed the fonts, so a build without `--reuse-resources` would have shipped the
   shared 3.0 atlas at every size. The packages built until then reused resources built by
   hand with them, and a rebuild with them matched those in 69 of 70 files, the 70th being
   the item icons that had changed;
6. the artwork, filtered as in section 8; the pool (`layouts.zip`) and `gui-blend.bin`, of
   which the package keeps the table and `sizes.txt`, the list of sizes with a set;
7. the list rows' check: `measure_list_rows.py --check` stops the build when the committed
   `list_rows.inc` is not what these sets and this artwork measure to;
8. the bank for KMRP's module (`tools/make_kmrp_assets.py`);
9. the controller patch's own files (`tools/make_controller_assets.py`, on the game's own
   layouts, with SDL re-signed ad hoc), with two checks: the badge shapes are the table
   Windows compiles (`src/controller-native/K1ControllerBadgeShapes.inc`), and
   `xbox_hud_layout.inc` is what `tools/build_xbox_hud.py --mac` writes;
10. the four patches. FTD's two with the KPM tree's `Patches/create-patch.py`, as every KPM
    patch is built; `KMRP-macOS.kpatch` with `tools/make_kmrp_patch.py --split --options
    --assets …` (options `map-notes`, `hd-icons` and `debug-logs`, no hook conditional); the controller
    patch with `--controller-patch` (options `xbox-hud` and `debug-logs`). `tools/kpm-cli`
    (KPatchCore) validates them and stages four lists, each with its overlap check: all
    four, the three without the controller (`patch_config.controller-off.toml`, which the
    installer uses with `--no-controller`), the controller patch alone, and the controller
    patch with FTD's two. The build then checks each list's order and that no two of its
    patches hook one address, that `kmrp` requires FTD's two and the controller patch
    requires nothing, and that each staged module is the one in its `.kpatch`. The modules
    are not packaged a second time: the installer takes each out of its `.kpatch`;
11. `kmrp-mac.sh`, `VERSION`, the licences, and `SHA256SUMS` over the package, which the
    installer checks before it writes anything;
12. `KMRP Installer.app`: `installer-app/main.m`, universal, with the Windows patcher's art
    and the Mac's icon, and the payload above inside it; the bundle signed ad hoc and
    verified;
13. the zip, by `ditto` without resource forks or extended attributes. *Corrected
    2026-09-29:* until then every one of the package's 785 files had a `._` AppleDouble
    entry beside it in the zip. Finder's Archive Utility folds those back into the files,
    but `unzip` writes them out as files, which the installer of that day would have copied
    into the game's override folder. The build now refuses an archive holding one;
14. the disk image: the app and a link to `/Applications`, in a Finder window laid out to
    drag one onto the other. The background (`tools/make_package_art.py`: the installer's
    navy, smoke, lockup and accent, with slate plates under the icon labels, which Finder draws
    black in Light Mode and white in Dark Mode), the disk's icon (the crest, cut out of the
    lockup with its wordmark removed, over "KMRP" in the wordmark's Georgia and metal) and the
    layout are written by Finder through
    AppleScript into a writable image, which is then compressed (HFS+, LZFSE, readable from
    macOS 10.11). Finder must be allowed to take the build terminal's orders (Privacy &
    Security, Automation); without that the image is made plain, with a warning. Then mounted
    read-only and checked as a player gets it: the app and the link at its root, the app's
    signature intact, the payload matching `SHA256SUMS`, and the window's settings and
    background present. Read back from the image of 2026-09-30: both icons where placed and the
    window 640x428. **Not yet looked at on screen.**

How the patch was built before, for reading older entries of `CHANGELOG.md`: the widescreen
patch and KMRP's layout, map-note and controller patches staged as four until 2026-09-30;
from then one patch, `kmrp`,
with FTD's two compiled in (`create-patch.py`'s Mac flags, one module linked with FTD's
constructor first, every byte hook before every detour), in four builds for the two options
`--no-map-notes` and `--no-controller`; from 2026-10-04 built once with `--options`, Windows'
three options in its manifest (`controller`, `map-notes`, `debug-logs`) and
`when = "controller"` on 20 of the controller's hooks, staged with and without that option
(94 and 74 hooks); the same day split from FTD's two (`--split`); and since 2026-10-07
without the controller, which is a patch of its own.

## 10. Coverage

What was seen, by date. The build changed shape three times after the first tests (section
1): the screens of 2026-09-29 and 2026-09-30 were seen with the installer writing the menus
into the override folder and `kmrp-layout` writing the layout sites, which the module and
FTD's Widescreen Patch do now. What was seen with the present arrangement is in section 2
("The menus inside the module", "The resolution chosen in the game", "KMRP on FTD's
patches") and section 7a, dated 2026-10-04 and 2026-10-07.

**Play-tested as installed by `kmrp-mac.sh`** from the package, native 3024x1964,
fullscreen through Aspyr's launcher, 2026-09-29: main menu, Load Game (two-line save rows),
the HUD and minimap, inventory (seven 153 px rows, no gaps), abilities (skills with the
description gutter on the scrollbar's side, powers with the enlarged icons), journal (quest
rows scaled), the area map (canvas in KMRP's frame, markers on the corridors), options, and
the quit confirmation; the inventory scrolled 48 rows down (rows stay packed at every
position); a conversation with Bastila (bars a sixth of the screen each, the line in the top
bar, all three replies in the bottom one). No layout-patch group was refused. The same
screens, plus feats, from test builds that differed only in the icon-size lookup
(section 6). **At half, 1512x982**, installed with `--resolution half`, fullscreen: the same
screens from the main menu to the quit confirmation, clicks landing, 76 px inventory rows
and 64 px power icons. **A blended size, 1352x878** (no set in the package), installed with
`--size 1352x878`, windowed: the installer blended the `.gui` files and took the fonts and art
of 1440x900; main menu, Load Game, inventory, powers, journal and area map laid out as at the
listed sizes, and every click landed. **Map notes clicked** at 3024x1964: the top and the
middle note each became the selected one ("To Docking Bay", "Port Official"), so the map's
hit test needs no wrapper on the Mac (section 4). **The skill and item icons** at 1512x982,
installed with `--resolution half` from the package of 2026-09-29 (`EF968C78…`): the skill
icons at 44 px, filling their frames where the 32 px ones had sat small in them, and the
HD item icons at the stock size, the Jedi Knight Robe's sleeves inside its hex frame
instead of past it.

**The controller** (section 7), with builds of the code committed as `0d147a1`, at
3024x1964, 2026-09-29. With a scripted pad (PlayStation art) and mouse events posted at the
HID level: walking and running on the stick, the camera, L3's flourish, Start to the Map, the
menus and their remaps, a movie skipped, the action bar on the D-pad, the prompts and their
hiding on mouse and on keyboard use, the parked cursor, the GUI cues, the saber's rumble
(lit, hum, put out; silent in menus and in the combat pause), read in `rumble.log`, and the
Controller Layout screen (opened from Gameplay, closed, the focus given back, the press
guards). With the package installed from `0d147a1`: the exit confirmation, reached on the pad
through Options, showed the Cross beside OK, a disc OK's height a quarter of its size clear
of it, and B cancelled the box. With the maintainer's own pad through SDL3: walking and the
menus, in play; that session also found Aspyr's pad mapping (B out of a menu started a
flourish), which is now off.

**Message popups fitted to their contents** (section 4, `popup_fit.cpp`), at 3024x1964,
2026-09-30, from the package installed on the live game:
- the Exit Game box went from 1,224x711 px to 880x365, centred on the screen, with the pad's
  Cross beside OK;
- in New Game, Custom Character, the Attributes, Skills and Feats tutorials came out fitted
  and centred, with their line counts unchanged (4, 7 and 5);
- the unspent-points warning came out fitted, seen before the width step.

**The granted popup's rows** (`granted_popup.cpp`), at 3024x1964, 2026-09-30, with the
layout patch's test build on the live game, New Game, Custom, Feats, Recommended, OK: four
feats, rows 125 px apart with 14 px between frames (141
before), each hex 111 px tall beside its 111-px text frame (97 before), the first letter
14 px inside the frame (2 before), the popup 876 px tall (941 before) and centred.

**Tested outside the game, as of 2026-09-30:** `Test-KmrpLayoutPatch.py`, `Test-AbilityIcons.py`,
`Test-GuiBlendHelper.py`, `Test-ResolutionDerivation.py`, and `Test-MacInstaller.py`
(install, status, uninstall into a stand-in game for a listed size and a blended one; the
executable, bundle and INI byte-identical after; the controller's two libraries and its art
installed; its settings file written with the defaults and removed when unchanged, kept
when edited after install without holding back the uninstall, and left alone when the
player already had one). Earlier, with the previous installer's
same code: rollback after a failure, the INI editor's cases, both resolution answers,
`--no-map-notes`, the refusals, the Mach-O edit round trip, `codesign` leaving the bundle
seal alone. Added since: `Test-MacAssets.py` (2026-10-04, section 2), `Test-MacFullscreen.py`
and `Test-MacKpmOwnership.py` (2026-10-02, section 11), and `Test-MacInstaller.py` brought
along with each change of the installer (`CHANGELOG.md`). None of them was run for the
revision of this document of 2026-10-08.

**Not yet tested:**

- store rows and the stack-count label in play (the test save has no stacked item and was
  not at a store);
- a tutorial popup with this build;
- any display other than this one, and a display connected or changed while the game runs
  (section 1, "Planned for KMRP 1.6");
- the four patches ticked by hand in KotOR Patch Manager's window, and the controller patch
  ticked there alone;
- the installer's window since step 3 lost its button (2026-10-08);
- whether the quit confirmation's narrow OK and Cancel match Windows (the popup sizes
  buttons to their label from 100 px in both builds' code);
- pressing Play in the Steam client itself. Aspyr's launcher, which Steam starts, was tested
  with the edited `KOTOR_Exe`, so the bundle seal is not checked on that path;
- Intel Macs;
- a game with other Override mods installed first;
- the controller's rumble in combat (hits, parries, shots, damage taken), and any rumble felt
  on a real pad: the scripted pad has no motors;
- the dialogue A and the status summary's A, and the status summary's layout without
  controller support. The layout is `kmrp-layout/status_summary.cpp`'s since 2026-10-02, so a
  build without the controller has it too, as Windows' core stand-in does
  (`StatusSummaryFrameK1`); before, such a build showed the game's own 640x480 box, the XP line
  wrapped to "50" alone (a tester's screenshot). With the controller the layout was seen right
  in play (the maintainer, 2026-10-01). The A labels are made when their
  panels are built (logged), but no conversation with replies and no status summary was
  reached on the pad: the test save's Selkath only bark, and LB and RB do not target party
  members;
- the character-generation, Solo Mode and resolution confirm guards;
- prompt art other than PlayStation's; the GameController fallback (SDL3 was always there);
- the widened Container in play (2026-09-30; its layout and badge checked by the tests and
  the installed file read back, the screen not yet opened), and a blended size since the
  helper makes the Container and the Controller Layout screen itself (installed into a
  stand-in game by `Test-MacInstaller.py`, not played).

## 11. Verifying by hand

```sh
EXE="$HOME/Library/Application Support/Steam/steamapps/common/swkotor/Knights of the Old Republic.app/Contents/MacOS/KOTOR_Exe"
shasum -a 256 "$EXE"                                   # C1FCB8D3… before, 5294AE4F… after
otool -l "$EXE" | grep -A2 LC_LOAD_DYLIB | grep KotorPatcher
codesign -dv "$EXE" 2>&1 | grep -E 'Identifier|Signature'
KMRP="/Applications/KMRP Installer.app/Contents/Resources/kmrp"   # the package, inside the app
"$KMRP/bin/kmrp-macho" info "$EXE"                     # ncmds=46 sizeofcmds=5912 free=1480 when installed
"$KMRP/kmrp-mac.sh" status                             # manifest entries changed since install
ls "${EXE:h}/patches"                                  # k1-stray-bug-fixes-patch, k1widescreenpatch, kmrp, kmrp-controller (.dylib)
grep -c '^\[\[patches.hooks\]\]' "${EXE:h}/patch_config.toml" # 109 with the controller patch, 85 without (the package built 2026-10-08)
KPATCH_LOG=/tmp/kpatch.log "$EXE"                      # then: grep "DLL-only patch" /tmp/kpatch.log
head -3 ~/Library/Logs/KMRP/controller.log             # with Debug Logs on, after a run: GetJoystickBuffer replaced, echo guard installed, SDL3 3.4.16 loaded
```

A layout-patch group that finds other bytes at one of its sites prints `[KMRP] <group>:
0x... holds other bytes, group left alone` with the bytes it found, on the game's stderr.
The controller module logs a site it leaves alone the same way, in `controller.log`
(`GetJoystickBuffer at 0x... holds other bytes`, `echo guard: ... not installed`,
`<class> guard: the vtable slot holds 0x...`).

### Fullscreen default

Installation now sets `DisplayFullScreen=true` in
`~/Library/Preferences/com.aspyr.kotor.steam.plist`, the launcher preference
measured as 0 for windowed mode and 1 after enabling fullscreen on 2026-10-02.
The installer records the previous key value in its manifest. Uninstall and rollback
restore that key only while its value still matches KMRP’s 1; later player changes
are preserved. An originally absent key is deleted, and other preferences remain
untouched. The installer window itself keeps its normal windowed interface.

Validation: `testing/regression/Test-MacFullscreen.py` exercises the actual installer
functions against a temporary preference file: absent key, prior windowed value,
install/uninstall, a later player change, and an unrelated key. All pass.

### Uninstall ownership correction, 2026-10-02

When KPM takes over an install, uninstall checks `patch_config.toml`,
`kpm_install_state.json` → `InstalledPatches`, and the contents of `patches/`
before deciding KMRP's patches are the only ones. A foreign byte-only patch can exist in
state without a module, so checking the config and modules alone was insufficient.
The state list is parsed with macOS `plutil`; missing keys, malformed JSON,
non-array values or a foreign id retain the runtime. An absent state
file preserves legacy behavior, but the config must contain `kmrp`
and no foreign id. An empty valid state array is allowed when the config
identifies KMRP, as in the Windows decision. "KMRP's" is `kmrp` alone in the correction
as written on 2026-10-02; since 2026-10-04 it is `kmrp` with the two patches of FTD's it
requires, and since 2026-10-07 the controller patch as well (`KMRP_IDS` in `kmrp-mac.sh`).
The fixture regression
`testing/regression/Test-MacKpmOwnership.py` exercises the actual shell function,
including module-less foreign patches and invalid state. It passed on 2026-10-02; a complete
installer takeover/uninstall play test was not run for this change.
