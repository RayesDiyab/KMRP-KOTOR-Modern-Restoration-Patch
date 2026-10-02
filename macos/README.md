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
3024x1964 pixels, Rosetta 2) on 2026-09-29; what was not tested is said where it matters and
collected under *Coverage*.

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

On Windows KMRP is three things: the `.gui` set for the chosen resolution (KOTOR High
Resolution Menus plus KMRP's edits) with fonts baked for it, an executable patch (the gold
delta), and the sizes its installer writes into that executable for the resolution. The Mac
executable is a different compiler's x86_64 build, so the executable part is ported site by
site; the files are the same.

| Layer | What | Where it comes from |
| --- | --- | --- |
| Hook runtime | `KotorPatcher.dylib`, loaded by one `LC_LOAD_DYLIB` in `KOTOR_Exe` | KotOR Patch Manager (MIT), built from source by `build.sh` |
| KMRP's patch | one KPM patch, `kmrp` (`patches/kmrp.dylib`), built by `tools/make_kmrp_patch.py` from four parts (since 2026-09-30; they were four patches before) | see below |
| … FTD's patches | FTD's widescreen patch and the Stray Bug Fixes it requires, which carry KMRP's engine fixes: the resolution (Retina modes included), K1–K9 (K7's reply list is KMRP's layout code since 2026-09-30), and, with `UseGuiFileLayouts=1`, no layout of their own | *K1WidescreenPatch* by FTD and RaymanGT and *K1StrayBugFixes* by RaymanGT and FTD (MIT), compiled from their source: branch `kmrp` of `RayesDiyab/Kotor-Patch-Manager`, FTD's `widescreen-patch` (where KMRP's fixes were merged as [FTD516/Kotor-Patch-Manager#1](https://github.com/FTD516/Kotor-Patch-Manager/pull/1)) as KMRP takes it (section 10) |
| … layout | the sizes the Windows installer writes per resolution, and the list-box, area-map, popup and dialogue-reply changes the gold delta makes | `patches/kmrp-layout/` |
| … map notes | Derslok's 250 map-note corrections (optional) | `patches/kmrp-map-notes/` |
| … controller | KMRP's Windows controller module, ported (section 7), reading the pad through SDL 3.4.16 (optional) | `patches/kmrp-controller/`; SDL's official macOS release, shipped as `kmrp-sdl3.dylib` beside the game |
| Menus and fonts | every resolution's set from KMRP's resource build, pooled; any other size blended at install | `tools/prepare_universal_resources.py`, `pack_resolution_layouts.py`, `build_gui_blend_table.py`, all unchanged from Windows |
| Artwork | `override-common.zip`, less what the Mac does not use | the same resource build |
| Feat, power and skill icons | enlarged from the game's texture pack at install | `tools/kmrp-abilityicons.c`, a port of `AbilityIconGenerator.cs` |
| Row frames, tutorial icons, `tutorial.2da` | made at install from the player's game: nothing of the game's ships | `tools/kmrp-gameart.c`, a port of `GameArtGenerator.cs` |
| Installer | `kmrp-mac.sh`: install, uninstall, status, with a hashed manifest; run by `KMRP Installer.app`, the Windows patcher's window ported | this directory, `installer-app/` |

**Why the widescreen patch is the base** (decided 2026-09-29, after a day on which KMRP was to
ship a patch of its own instead): it is the Mac's resolution unlock, and KMRP's engine fixes
were contributed to it, so KMRP ships and installs that version rather than a second copy.
What depends on KMRP's layouts stays in KMRP: the `UseGuiFileLayouts` switch is the only
thing the widescreen patch carries for it, and everything the switch leaves undone is the
layout patch's. The engine fixes are documented beside their code, in the branch's
`Patches/K1WidescreenPatch/KMRP-ENGINE-FIXES.md`:

| | Fix | Windows equivalent |
| --- | --- | --- |
| K1 | word-wrap forward progress and the two short-string guards | `.kwl`, `0x0045A3B7`, `0x0045A3DC` |
| K2 | list rows stop growing | `0x0041B507`, `0x0041B52C` |
| K3 | leading newline trimmed | `.ktn` |
| K4 | video mode follows the target resolution | none: the Windows patcher writes the resolution into the executable |
| K5 | a line taller than its box is drawn, not dropped | none: Windows sizes the stack label with the font (`.ksc`) so the case does not arise |
| K6 | 0.5 px wrap margin | TXI `spacingR` |
| K7 | dialogue letterbox from the height; reply list fills the bar (the list's stretch is KMRP's layout patch since 2026-09-30, `dialogue_replies.cpp`: the widescreen patch dropped its hook) | `.klb`, nine sites |
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
| **Start Patching** | `install --yes`, with `--resolution half` (current) or `native` (Retina) for this display's rows, `--size WxH` for any other, `--no-map-notes` when *Area Map Marker Fixes* is off, `--no-controller` when *Controller Support* is off (Advanced Settings, as on Windows), `--game` when one was chosen with **Browse** |
| **Restore Original** | `uninstall --yes` (and `--game`) |

What the script refuses (the game running, another build), the app shows as a blocking
message with the script's own words. A game KotOR Patch Manager manages is not refused: the
second step says whether KMRP replaces FTD's install or installs for KPM (below). The
script's output goes to `~/Library/Logs/KMRP/installer.log` (**Open Log**), and its stage
lines move the progress fill.

**It looks like the Windows patcher** (`installer-app/main.m`, a port of `MainForm`):
`UiTheme`'s colours, the brand lockup with the tagline set to the wordmark's ink width,
`LightField`'s smoke and motes (every constant Windows', faded out over the header's lowest
30% so they do not stop on a line beside the card, as they can on Windows:
`docs/windows-changes-from-macos.md`, item 11; rendered at 1/12 of the header's
pixels on a background queue every 62 ms and resampled with vImage), the four-step card
with the step and state art from `src/patcher/icons`, the pill buttons with the primary's
progress fill, the Advanced Settings view with its two toggles, and the footer. Its icon is the
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

**Resolutions** (step 3): this display first, its current resolution and on a Retina display
its every pixel, the current one chosen (the main
display, as the widescreen patch reads it), then `installer-app/resolutions.txt`, 34 sizes
grouped by shape (the 17 Mac sizes and common external displays), each one the build
checks is in `layouts.zip`, then **Custom size…**. A custom size is checked with
`kmrp-guiblend`'s dry run (exit 2: outside what the sets cover) before it can be chosen.

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
arguments (`-KMRPSelect`, `-KMRPRun`, `-KMRPSettings`, `-KMRPSnapshot`, `-KMRPQuit`; the
comment at the top of `main.m`): the installed and not-installed states, Advanced Settings,
the progress fill at "Installing artwork… 34%", the resolution list from top to end and the
**Custom size…** dialog, a custom size outside the sets refused, and
**Restore Original** then **Start Patching** on the live game, the second leaving the same
`KOTOR_Exe` (`5294ae4f…`) and install as `kmrp-mac.sh` does alone. `Test-MacInstaller.py`
passes on the app's `Contents/Resources/kmrp`. Built for x86_64 (macOS 10.13 and later, the
floor of the controller's SDL3 and the helpers) and arm64, with `-Wunguarded-availability`.

## 2. Every file the installer writes

`kmrp-mac.sh install`, run from the package, in this order. Paths are relative to
`Knights of the Old Republic.app/Contents`. Counts are for 3024x1964.

| Path | Kind | Notes |
| --- | --- | --- |
| `~/Library/Application Support/KMRP/macos/backup/KOTOR_Exe` | copy | the original, re-hashed before anything is written |
| `MacOS/KotorPatcher.dylib` | added | KPM runtime |
| `MacOS/patches/kmrp.dylib` | added | KMRP's one patch: FTD's widescreen patch and Stray Bug Fixes with KMRP's layout code, and the map notes and the controller unless `--no-map-notes` or `--no-controller` (one of four builds, `engine/kmrp[.no-map-notes][.no-controller]/`) |
| `MacOS/kmrp-sdl3.dylib` | added | omitted with `--no-controller`; SDL 3.4.16, the library of the official macOS release, its code unchanged and its signature redone ad hoc (`THIRD_PARTY_NOTICES.md`) |
| `MacOS/patch_config.toml` | added | written at build time by KPM's own `ConfigGenerator` for the `kmrp` patch: 84 hooks with both options (the Stray Bug Fixes' 11, 45 of the widescreen patch's, five menu-input hooks, the map-note detour and the controller's 21), 62 with neither (the 61 and, without the controller, `KmrpCoreGuiFrame`, the status summary's layout; since 2026-10-02); staged with the matching `kmrp.dylib` |
| `MacOS/KOTOR_Exe` | edited | one load command, then `codesign --force --sign - --identifier KOTOR_Exe` |
| `MacOS/KOTOR_Exe.backup.<yyyyMMdd_HHmmss>` and its `.json` | added | the untouched game in KotOR Patch Manager's format (`BackupManager`, `BackupInfo`), made before the load command, from which KPM's Apply starts (since 2026-10-01, as Windows' `WriteKpmBackup`) |
| `MacOS/kpm_install_state.json` | added | KPM's record of the install (`ManagedInstallState`, schema 1): the untouched game's hash and size, KPM's name for it ("1 1.4.0 (Aspyr macOS)", macOS, Steam, x86_64, its Mach-O identity), `InstalledPatches` `["kmrp"]`, `LinkedDependencyInstalled` true; KPM identifies the modified game by it (since 2026-10-01, as Windows' `KpmState`) |
| KPM's patch folder`/kmrp.kpatch` | added, or an older KMRP's replaced | the installed build's `.kpatch`, where KPM's settings (`KPatchLauncher/settings.json` under `~/.config`, or `~/Library/Application Support`) say its patches are, so KPM lists KMRP; declares a conflict with FTD's two patches, which it carries (since 2026-10-01, as Windows' `DeliverKpatches`) |
| `~/Library/Application Support/Knights of the Old Republic/swkotor.ini` | three keys under `[Graphics Options]` | `UseGuiFileLayouts=1`, `ForceWidth`, `ForceHeight` (section 5); the file is created if the game never ran |
| `~/Library/Application Support/Knights of the Old Republic/kmrp-controller.ini` | added if absent | the controller's settings, Windows' defaults (section 7); a copy already there is the player's and is kept; not written with `--no-controller` |
| `Assets/override/` | created if absent | the game's working directory is `Contents/Assets` and it reads `.\override` |
| `Assets/override/*` | added or replaced | 1,855 files: 854 artwork files (98 of them the controller's: 22 prompt textures in each of the four pad families and 10 for the Controller Layout screen); the resolution's set, 673 files (82 `.gui`, 36 font files, `lbl_mileftbot`, and the controller's 552 prompt and cue textures sized for it, `kmrplayout.gui` and `kmrp_prompts.txt`); 18 made from the game (four row frames, 13 `tut_*` icons, `tutorial.2da`: section 6); 310 enlarged feat, power and skill icons |

*Corrected 2026-09-29:* the override row said 757 artwork files and a set of 136 (83 `.gui`,
36 font files, the tutorial icons and `tutorial.2da`, the row-frame art). The tutorial files
and the row frames are made at install since that day (section 6), and the controller's art
is installed since it was ported; the counts above are read from the manifest of an install
of the package built from `0d147a1`.

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

- Bundled third-party art (the names in `bundled-override.txt`: Party Portraits, the HD Icon
  Pack) yields to a texture already in Override under either extension, because the engine
  prefers `.tpc` over `.tga` for the same resref. Tested: a pre-existing `ia_class4_005.tpc`
  was left alone and the rest installed.
- KMRP's own files replace an existing file after copying it to `backup/`.
- A name the package would write twice stops the install (and rolls it back): the second
  write would back up KMRP's own first copy as "the original", the bug the Windows installer
  had with `i_checkbox01.tga`. The feat and power icon generator is handed every name the
  install writes, so it never produces one of them.
- The installer stops without writing anything when `KOTOR_Exe` is not the build above,
  when the game is running, when the texture pack is missing, or when a KMRP install is
  already recorded.
- With KotOR Patch Manager's files present (`KotorPatcher.dylib`, `patch_config.toml`,
  `patches/`, `kpm_install_state.json` or `KOTOR_Exe.backup.*` beside `KOTOR_Exe`), since
  2026-10-01 as the Windows installer does it (`KpmEdition.cs`): an install of FTD's two
  patches alone is replaced (the untouched game put back from KPM's copy, his files deleted,
  KMRP installed; the maintainer: that "should still work"); with any other patch installed,
  KMRP installs *for* KPM: the menus, art, INI and the controller's SDL beside KPM's patches,
  no runtime, no load command, `KOTOR_Exe` untouched, and `kmrp.kpatch` in KPM's patch folder
  (or beside the game when KPM's settings name none) for the player to tick in KPM. Until
  2026-10-01 that case was refused.
- KMRP's own install is one KPM recognises and takes over: `kpm_install_state.json`, the
  KPM-format backup and `kmrp.kpatch` (the file table above). Once KPM's Apply has rewritten
  `patch_config.toml`, `uninstall` leaves the runtime, the load command and KPM's records to
  KPM and removes only KMRP's own files, as Windows' Restore does.

**The manifest.** Every write is recorded in
`~/Library/Application Support/KMRP/macos/manifest.tsv` (kind, path, SHA-256 as written,
backup name), outside the app bundle so a Steam update cannot delete it. `uninstall`
walks it newest first:

- deletes an added file only if its hash still matches;
- restores a replaced one only if ours is still there;
- puts the original `KOTOR_Exe` back only if the installed one is unchanged;
- puts each INI key back to its old value, or removes it if it had none, only if it still
  holds what KMRP wrote (`ini` rows: key, value written, value before);
- deletes `kmrp-controller.ini` only if it is still as written (`settings` row); an edited
  one is the player's, kept without counting as a change, so it never holds back the rest;
- reports anything that changed and keeps its backup.

The INI is edited key by key, in place, keeping the file's CRLF line ends. An install and
uninstall left the player's INI byte-identical, including a `ForceWidth` it had before
(`testing/regression/Test-MacInstaller.py`), and so did a rollback (below).

`install.info` is written before the first change (`complete=0`) and completed at the end
(`complete=1`), so an install cut short even by a kill -9 can be undone by `uninstall`.

**Rollback.** A failure part-way through undoes itself. Tested by placing a directory where
`lbl_map.tpc` goes: the copy failed, the installer reported it, and the app bundle's file
list and sizes, `KOTOR_Exe`'s hash, the state directory and `swkotor.ini` all matched the
state before the install. *Corrected 2026-09-29:* the first version of the rollback hung it on an `EXIT`
trap and never ran, leaving a half-installed game. zsh does not run `EXIT` when errexit
ends the script; it runs `ZERR`. The same test caught it, and both traps now run the
rollback.

## 3. What the map-note patch writes

One detour, in `patches/kmrp-map-notes/`:

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

## 4. What the layout patch writes

The layout component includes the [menu-input hooks](../reverse-engineering/macos-keyboard-navigation.md).
Its resolution-dependent sites remain constructor patches: when
`UseGuiFileLayouts=1` is set, the constructor writes its sites before the game's code runs. Every site is
checked for the bytes it must hold first, group by group; a group whose sites hold anything
else is left alone and named on stderr. The resolution is the widescreen patch's:
`ForceWidth`/`ForceHeight`, or the main display's point size. Sizes scale by the Windows
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
| | Options check boxes: circle `25s`, label `30s`, drop `2s` (2026-09-30) | `CSWGuiOptionsCheckbox::SetExtent` (`0x1002cecee`) replaced by a jump into the module | **none yet** (`docs/windows-changes-from-macos.md`, item 13) |
| `popup_fit.cpp` | the message popup fitted to its contents, centred (2026-09-30) | `FixMessageLabel`'s last call (`0x100306a88`), through the near page's third thunk | **none yet**: Windows keeps the height from `confirm.gui` |
| `granted_popup.cpp` | the granted popup's rows: text inset `row/8`, hex grown `row/7`, pitch `row + row/11`, OK and panel fitted, centred (2026-09-30) | the fill's call to `AddControls` (`0x10028ea4f`) and the row's text-rect call in `CSWGuiInGameSkillEntry::SetExtent` (`0x10022f321`), through the near page's fourth and fifth thunks | **none yet** (`docs/windows-changes-from-macos.md`, item 10) |
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

On a display with more pixels than points (every Retina Mac), the installer app offers both
and chooses half, the resolution macOS is set to (since 2026-10-01; native until then: a
player reading 1512x982 in System Settings took 3024x1964 for a wrong guess); `kmrp-mac.sh` on
its own asks, or takes `--resolution current|native` (`half` is `current`), and
`--size WxH` sets any size (another display, a window):

| choice | frame the game renders here | INI |
| --- | --- | --- |
| native ("Retina") | 3024x1964, every pixel of the panel | `ForceWidth=3024`, `ForceHeight=1964` |
| half ("current", default) | 1512x982, the point size, the resolution macOS is set to, scaled up 2x by macOS | `ForceWidth=1512`, `ForceHeight=982` |

and `UseGuiFileLayouts=1`. On a display whose pixels are its points there is nothing to
choose. Native needs engine fix K9: without it the pixel size was not a valid display mode,
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

**Listed sizes.** The package carries every resolution KMRP's build lays out: the 49 Windows
sizes and 17 Mac ones (`GROUPS["macOS"]` in `prepare_universal_resources.py`, from the 13"
to the 16" MacBook Pro and the external displays Macs ship with, native and half). They are
pooled as the Windows installer pools them (`tools/pack_resolution_layouts.py`):
45,540 files, 18,167 distinct, 86.7 MB. A listed size gets its set exactly: the same `.gui`
files, the same fonts baked at `max(1, H / 720)` with their metrics at that scale, the same
row-frame and tutorial art the Windows installer writes for it. The widescreen patch scales
no font with the switch on, so a texel of the atlas is a pixel on screen, as on Windows.

**Other sizes.** For a size with no set, the installer blends the `.gui` files from the
finished sets around it (`kmrp-guiblend` over `gui-blend.bin`: the two aspect-ratio families
on either side, each at the two heights around it) and takes the fonts of the nearest set
by height, then shape. Some layouts are not blended but made for the size (since
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
comes out with the build's files byte for byte. Built and tested on Windows only so far:
[`docs/macos-changes-from-windows.md`](../docs/macos-changes-from-windows.md), items 1 to 3.

**Made from the player's game.** The four hex frames list rows tile behind item icons
(`lbl_hex*`, `56s`), the tutorial popup's thirteen `tut_*` icons (`64s`) and `tutorial.2da`
(the game's own table, its `icon` column pointed at those copies) are made at install by
`kmrp-gameart`, from `TexturePacks/swpc_tex_gui.erf` and, through `chitin.key`,
`data/2da.bif`. Until 2026-09-29 the resource build exported them from the build machine's
game and the package carried them. `GameArtGenerator.cs` does the same on Windows, byte for
byte (`Test-GameArt.py`), and the sizes are the ones every set shipped (1,122 textures
checked). If either file cannot be read, none is installed and the game keeps its own.

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
with the same bindings, event ids, tables, rumble patterns and art. What it does and why is
written once, for Windows, in [`docs/controller-support.md`](../docs/controller-support.md)
and the documents it links; this section covers what the Mac changes. The sources name each
Mac address beside the Windows one it stands for.

**Why a port.** KOTOR I on the Mac has no controller support that works: a pad that works in
other macOS apps did nothing in play (2026-09-29), and Aspyr lists controllers for KOTOR II on
the Mac only. The executable keeps the PC's joystick input chain, which the Windows module
feeds, and a rumble subsystem whose output Aspyr stubbed: `CExoInput::SetRumble`,
`PauseRumble` and `UnpauseRumble` (`0x10035738c`, `0x10035739c`, `0x1003573a2`) return
without doing anything.

**The pad** is read through SDL 3.4.16, the release the Windows installer pins, shipped as
`kmrp-sdl3.dylib` beside `KOTOR_Exe`. Apple's GameController framework, weak-linked, is used only when
that library cannot be loaded, so the two never hold a pad at once. The prompts are drawn in
the pad's family, as on Windows: Xbox, PlayStation, Switch or Steam Deck art (`kmrp*`,
`kmrs*`, `kmrn*`, `kmrd*`).

**Sites.** The patch's 21 hooks, and ten writes the module makes as it loads, each after
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

**Settings and logs.** Rumble reads `kmrp-controller.ini`, section `[Rumble]`, from the
game's settings folder, `~/Library/Application Support/Knights of the Old Republic/`, beside
`swkotor.ini` (on Windows the file sits beside `swkotor.exe`). The keys, ranges and defaults
are Windows': `Mode` = `Off`, `Original` or `Enhanced` (default); `Strength` 0–100 (100);
`SaberHum` 0–100 (6); `SaberHumPulseMs` 0–1000 (100); `SaberHumPeriodMinMs` and
`SaberHumPeriodMaxMs` 50–5000 (500, 2000); `Debug` 0 or 1. The file is re-read within a
second of a change, and a missing file or key means its default. The installer writes the
file as the Windows installer does (`DefaultSettings` in `KmrpPatcher.cs`, the same text but
for the log's path and LF line ends): only when there is none, never over the player's, and
uninstall removes it only if it is unchanged (section 2). The module logs to
`~/Library/Logs/KMRP/controller.log` every run (a game started from Steam sends its stderr
nowhere), and rumble events to `rumble.log` there with `Debug=1`.

**Testing without a pad.** `KMRP_PAD_SCRIPT=<file>` replaces the pad with a script, one
`<seconds> <control> <value>` a line, the controls being `A B X Y LB RB BACK START L3 R3
UP DOWN LEFT RIGHT` (1 pressed, 0 released) and the axes `LX LY RX RY LT RT`.
`KMRP_PAD_FAMILY=s`, `n` or `d` draws its prompts in PlayStation, Switch or Steam Deck art
(Xbox otherwise). The scripted pad has no motors: its rumble is read from the logs.

## 8. What is deliberately not installed or changed

| Left out | Why |
| --- | --- |
| The 18 fonts in `override-common.zip` | every set carries them at its own size |
| Driver compatibility, DPI and NVIDIA settings, Large Address Aware | Windows code (K1DC is a `dinput8.dll` proxy with an ASI plugin for the 32-bit `swkotor.exe`); the Mac build is 64-bit. *Corrected 2026-09-29:* this called them Direct3D-specific, but KOTOR renders with OpenGL on Windows too, and K1DC repairs an OpenGL lighting path. Whether the Mac port has the same fallback is **not yet checked**: this Mac's OpenGL (Apple M5, 2.1 on Metal) offers neither `GL_NV_register_combiners` nor `GL_ATI_text_fragment_shader`, the two old paths the executable names, but it does offer the ARB fragment programs and GLSL, which the executable also names |
| Movie fixes | Aspyr's Bink 2 player pillarboxes and switches no display mode (checked in play) |
| `swkotor.ini` beyond three keys | the video mode follows the target (K4), so `Width`/`Height` stay as they are |
| Anti-aliasing and other graphics settings | the player's; the README recommends 2x at native (section 5) |
| Update check, settings UI | the Windows installer's; the Mac installer is a script |

*Corrected 2026-09-29:* until this date the Mac build used the widescreen patch's own
layout of the vanilla menus, with `NativeResolution`, `FontScale` (`max(1, H × 1.5 / 1964)`,
the maintainer's anchor) and `FullWidthMenus` in the INI, per-scale font sets, and none of
KMRP's `.gui` sets, row-frame art, tutorial icons or enlarged ability icons. It looked
visibly different from Windows (4:3 menus, larger inventory rows, no feat and power row
fix), and was replaced by what this document describes. Those three keys are gone from the
widescreen patch.

## 9. Building

```sh
git submodule update --init
macos/build.sh --python .venv/bin/python [--reuse-resources]
```

KotOR Patch Manager and FTD's two patches come from the submodule
`third_party/Kotor-Patch-Manager`: `RayesDiyab/Kotor-Patch-Manager`, branch `kmrp`, which is
FTD's `widescreen-patch` (`074972b`, 2026-09-30) with one change: the 11 hooks FTD moved into
*K1StrayBugFixes* taken out of *K1WidescreenPatch*'s hook list, where they were still declared,
so the two patches hooked the same addresses twice (KPM's own check: "Multiple hooks at
address"). FTD's changes reach KMRP when they are merged into that branch; nothing follows his
branch by itself. The [2026-10-02 audit](../docs/ftd-macos-upstream-audit.md)
integrates FTD's separate Scripts Enter fix in KMRP's guarded core hooks; his
new GUI writers overlap our existing layout patches and are not linked alongside
them. The submodule pin is unchanged. Until 2026-09-30 the submodule tracked FTD's `widescreen-patch` directly
(`71ac5fa`: KPM's master `5cafa6a` with his widescreen patch and KMRP's fixes, merged there on
2026-09-29 as FTD516/Kotor-Patch-Manager#1, then #2, which builds it with KPM's own
`create-patch.py`); before that the same fixes on `RayesDiyab/Kotor-Patch-Manager`, branch
`kmrp-engine-fixes`, and then FTD's `9884466`. Since
`1d3ccd2`, KPM's master has changed no file of the runtime, KPatchCore or the address databases
the build uses. `--kpm` and `--widescreen` build from other checkouts instead.

Needs: Xcode command line tools, the .NET 8 SDK, and a Python with `requirements.txt`. The
unmodified game must be installed (the build resolves hooks against `KOTOR_Exe`'s hash and
reads `TexturePacks/swpc_tex_gui.erf` for the fonts); nothing from the game is packaged.
Output: `dist/macos/KMRP-macOS-<version>/` (`KMRP Installer.app` and `README.md`), its disk
image (the Mac download: the app and a link to Applications, 157 MB) and its zip (155 MB, the
folder with the README, for sites that take only archives).
Steps, in order:

1. `make dylib` in KPM's `src/KotorPatcher`;
2. the map-note table; then KMRP's one patch, `kmrp`, in four builds for the two options
   (`tools/make_kmrp_patch.py`: FTD's two patches compiled with `create-patch.py`'s Mac flags,
   KMRP's parts with their own, one module linked with FTD's constructor first, the hook lists
   merged with every byte hook before every detour), each checked and staged by KPM's own
   KPatchCore. Until 2026-09-30 the widescreen patch was built with KPM's `Patches/create-patch.py`, as every KPM patch is built
   (until 2026-09-29 with the patch's own `build_mac.sh`, which FTD516/Kotor-Patch-Manager#2
   removed);
3. the map-note patch, and the layout patch (`patches/kmrp-layout/*.cpp`);
4. SDL 3.4.16: the official `SDL3-3.4.16.dmg`, downloaded once into `build/deps` and refused
   unless its SHA-256 is `675660a9…87fd`; then the controller patch
   (`patches/kmrp-controller/`), which is not linked against SDL but opens
   `kmrp-sdl3.dylib` from its own folder or else the game's, as the Windows module opens
   `kmrp-sdl3.dll`;
5. `tools/kpm-cli` (KPatchCore): `validate` all four, then `stage-many` writes
   `patch_config.toml` with and without the map notes and with and without the controller
   (four configurations; the controller last), and checks for overlapping hooks across
   them;
6. `kmrp-macho`, `kmrp-guiblend` and `kmrp-abilityicons`, universal (arm64, x86_64), ad-hoc
   signed;
7. `prepare_universal_resources.py` exactly as `build_kmrp.ps1` runs it, with the
   per-resolution fonts of `build/fonts` (`tools/build_font_scale_sets.py`) when they are
   there (`--reuse-resources` keeps the previous output). *Corrected 2026-09-29:* this step
   never passed the fonts, so a build without `--reuse-resources` would have shipped the
   shared 3.0 atlas at every size. The packages built so far reused resources built by hand
   with them, and a rebuild with them matched those in 69 of 70 files, the 70th being the
   item icons that had changed;
8. the artwork, filtered as in section 8; the pool (`layouts.zip`) and `gui-blend.bin`;
9. `SHA256SUMS` over the package, which the installer checks before it writes anything;
10. `KMRP Installer.app`: `installer-app/main.m`, universal, with `resolutions.txt` (every
   size checked against `layouts.zip`), the Windows patcher's art and icon, and the payload
   above inside it; the bundle signed ad hoc and verified;
11. the zip, by `ditto` without resource forks or extended attributes. *Corrected
   2026-09-29:* until then every one of the package's 785 files had a `._` AppleDouble
   entry beside it in the zip. Finder's Archive Utility folds those back into the files,
   but `unzip` writes them out as files, which the installer would have copied into the
   game's override. The build now refuses an archive holding one.
12. the disk image: the app and a link to `/Applications`, in a Finder window laid out to
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

## 10. Coverage

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

**Tested outside the game:** `Test-KmrpLayoutPatch.py`, `Test-AbilityIcons.py`,
`Test-GuiBlendHelper.py`, `Test-ResolutionDerivation.py`, and `Test-MacInstaller.py`
(install, status, uninstall into a stand-in game for a listed size and a blended one; the
executable, bundle and INI byte-identical after; the controller's two libraries and its art
installed; its settings file written with the defaults and removed when unchanged, kept
when edited after install without holding back the uninstall, and left alone when the
player already had one). Earlier, with the previous installer's
same code: rollback after a failure, the INI editor's cases, both resolution answers,
`--no-map-notes`, the refusals, the Mach-O edit round trip, `codesign` leaving the bundle
seal alone.

**Not yet tested:**

- store rows and the stack-count label in play (the test save has no stacked item and was
  not at a store);
- a tutorial popup with this build;
- any display other than this one;
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
kmrp/bin/kmrp-macho info "$EXE"                        # ncmds=46 sizeofcmds=5912 free=1480 when installed
kmrp/kmrp-mac.sh status                                # manifest entries changed since install
KPATCH_LOG=/tmp/kpatch.log "$EXE"                      # then: grep "DLL-only patch" /tmp/kpatch.log
head -3 ~/Library/Logs/KMRP/controller.log             # after a run: GetJoystickBuffer replaced, echo guard installed, SDL3 3.4.16 loaded
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
before deciding KMRP is the only patch. A foreign byte-only patch can exist in
state without a module, so checking the config and modules alone was insufficient.
The state list is parsed with macOS `plutil`; missing keys, malformed JSON,
non-array values or IDs other than `kmrp` retain the runtime. An absent state
file preserves legacy behavior, but the config must contain at least one KMRP
ID and no foreign IDs. An empty valid state array is allowed when the config
identifies KMRP, as in the Windows decision. The fixture regression
`testing/regression/Test-MacKpmOwnership.py` exercises the actual shell function,
including module-less foreign patches and invalid state. It passed; a complete
installer takeover/uninstall play test was not run for this change. Existing
DMGs predate this correction.
