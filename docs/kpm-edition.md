# KMRP on KOTOR Patch Manager's runtime: KMRP's installer and the KPM edition

**Reference.** How KMRP runs on KOTOR Patch Manager's runtime, byte for byte, and
how it is proved to make the same game as the standalone installer did, for the
editable 1.03 executable and Steam's. The KPM edition was built and measured on
2026-09-28 and, for the final build on Steam, 2026-09-29. The same day KMRP's own
installer moved onto it (section 1a): since 2026-09-29 **both** installers leave
the executable's code alone. The lab record of how it was designed is in the
session notes summarised under *Rejected alternatives* below.

**"The standalone"** in this document is KMRP's installer as it was until
2026-09-29, which wrote the gold image into `swkotor.exe`. KMRP's installer still
writes that image to a new file with `--apply`, and it remains the reference the
data file is proved against (section 7); installing it is retired.

## One patch since 2026-10-04

**Read this first: most of what follows describes the edition as it was until
2026-10-04.** That day the maintainer made the standalone patch the final KMRP ("the
final kmrp should be now the standalone kpatch with options shipped inside the
installer"). What changed, and what the sections below still get right:

| | Until 2026-10-04 (sections 1 to 7) | Now |
| --- | --- | --- |
| Patches | four: `kmrp`, `kmrp-controller`, `kmrp-movies`, `kmrp-map-notes` | one, `kmrp`, with two options, `controller` and `map-notes` (`tools/build_native_kpatch.py`). The movie fixes are part of it: an option for a few hours that day, then "standard baked into KMRP, non-negotiable" (the maintainer) |
| Module | `kmrp-controller.module`, 245 KB, one copy per patch with detours | `kmrp-native.dll`, about 189 MB, once, as `patches\kmrp.dll`; it embeds the engine recipe, every resolution's files, the controller and SDL |
| Engine data | `kmrp-kpm.dat`, built at install for the chosen resolution | none: the module applies the engine for the size the game runs at, and again when it changes |
| `Override` | about 1,850 files for the chosen resolution | nothing |
| `patch_config.toml` | four sections, from `Kmrp.engine.config.<id>` | one section, written by `KpmEditionOperations.PatchConfigSection`: the hooks that are always installed, those of each option left on, and a `[patches.options]` table |
| Resolution | chosen in the installer, one | the display's current size in `swkotor.ini`; any size the display supports in the game; a checklist for fewer or other sizes (`kmrp-resolutions.txt`) |
| `.kpatch` files delivered | four | one, `KMRP.kpatch` |

Unchanged, and still as sections 1a and 5 describe: KOTOR Patch Manager's runtime
and proxy and how the installer lays them out, `kpm_install_state.json` and the
backup KPM restores from, the 4 GB flag, the install for KPM when its runtime is
already in the folder, the takeover and restore rules, and Steam's executable left
unmodified. The standalone module's own measurements are in
[the runtime experiment](../reverse-engineering/runtime-resolution-preview.md), and
its NVIDIA step in [NVIDIA present method](nvidia-present-method.md#the-standalone-module).

Measured on 2026-10-04 with `dist\KMRP-next.exe` (195.8 MB) on scratch copies of
the editable 1.03 game (`testing/regression/Test-InstallerPatch.ps1` repeats the
first four rows):

| Case | Result |
| --- | --- |
| Install, every option on | `patch_config.toml` holds `kmrp` alone, 52 hooks, `controller` and `map-notes` true (measured while `movies` was a third option, also true); `patches\kmrp.dll` is the module inside `KMRP.kpatch`; no `Override`, no `kmrp-kpm.dat`, no SDL beside the game; the game logs "KMRP + Movies + Map Notes" |
| Install, controller support and map notes off | 24 hooks, the two options false; the game logs "KMRP + Movies" |
| Resolutions chosen (12 of the display's 19 unticked, 3000x1300 added) | `kmrp-resolutions.txt` lists the 8 sizes; the game's list shows the 7 display sizes at their rates and 3000x1300 at 60 Hz; choosing it there switched the game to a 3000x1300 borderless window |
| Restore Original | the folder as it was, `swkotor.exe` `761F9466...` |
| The four-patch edition installed first (`dist` build of 2026-10-03, 1,854 `Override` files) | the new installer's restore removed it, installed the one patch, and the game started |
| The play-test game (`C:\Star Wars - KotOR`), restored with the 2026-10-03 build and installed with the new one | 52 hooks, every option on, the game started |

| Steam's executable (the maintainer's Steam install, holding the four-patch edition) | installed: the old edition removed (1,854 `Override` files), `kmrp` alone with 52 hooks, `target_version_sha` Steam's, `swkotor.exe` unmodified (`34E6D971...`). Started from Steam by the maintainer the same day ("I tested steam it works"); its `kmrp-kpm.log` of 15:04 records "Steam executable; 806 ms after the game started, before its window", the engine initialised for 3440x1440, and a switch in the game to 1600x1200 and back, each committed with 54 fields |

| GOG's executable (`9C10E045...`, a scratch game) | `target_version_sha` GOG's, 52 hooks, the 4 GB flag set (`01B80825...`); the game reached the main menu at 3440x1440 with KMRP's interface; Restore Original left GOG's file. The module's log calls it "CD 1.03 executable": it tells the editable build and GOG's apart by nothing, as they differ only in header padding |

**Not tested:** KOTOR
Patch Manager's own Apply over this install; Proton.

**Removed with it (2026-10-04):** `OverrideOperations.Install` and its helpers,
`GuiPool` and the embedded Override archives, the per-resolution data file's install,
and the three regressions of the four-patch layout (`Test-KpmEdition.ps1`,
`Test-ControllerSupport.ps1`, `Test-InstalledOverride.ps1`). The sections below name
them as they were. **Kept:** the whole restore side (`OverrideOperations.Restore`,
`IniOperations.Restore`, the standalone installer's restore), which removes older
installs; `--apply`, which still builds the reference executable from the engine
source; and `--derive-gui` with the C# generators, the reference the macOS C tools
are compared with. **Still in the tree and unused by the installer:**
`tools/build_kpatch.py`'s four-patch packaging and `src/controller-native/build.cmd`
(the 245 KB module), which other tools still import or name.

## Source-built Windows patches (2026-10-01)

The normal Windows build now assembles its patch recipe from tracked source,
without a clean executable, gold snapshot, `gold.kup`, or `Kmrp.kpm.originals`.
[Windows engine source](windows-engine-source.md) documents the current build
and checks. The historical measurements below still describe the earlier
snapshot-derived implementation. `--apply` remains an optional offline reference
command using a supported editable executable, not an installer build step.

## The build this describes

| | |
| --- | --- |
| Unmodified executable | the editable KOTOR 1.03 `swkotor.exe`, `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`, 4,042,752 bytes (`build-inputs/swkotornopatch.exe`). Called **CD 1.03** in this document and in the KPM edition's code, after KPM's own key for it, `kotor1_cdcrack_103` -- KPM's version table names it "HellSpawn CD Crack version 1.0.3", GOG's v1.03 with a 16-byte watermark ([map-scaling.md](../reverse-engineering/map-scaling.md)). It is not the retail CD's executable, which KMRP has not measured. GOG's own (`9C10E045…`) is this file with those 16 bytes zeroed, measured 2026-09-30, and accepted since (section 8) |
| Steam's executable | `34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`, 4,395,008 bytes, KPM's `kotor1_steam_103`; a clean Steam install lent by the maintainer on 2026-09-28 (`build-inputs/swkotor-steam.exe`, optional) |
| Gold | `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`, 4,087,808 bytes (`build/kmrp/swkotor_gold_v24_movieaspect.exe`) |
| KOTOR Patch Manager | 0.7.1 (release zip `0EFEFAC8…`, source zip `Kotor-Patch-Manager-0.7.1.zip`), read and run on 2026-09-28; 0.7.1 (2026-09-21) was still KPM's newest release on 2026-09-29. The clone in `build/research/Kotor-Patch-Manager` is at an **older** development commit, `7d53e52` of 2026-09-05 -- before 0.7.0 (09-07) and 0.7.1 -- and differs. (*Corrected 2026-09-29:* this called it a later commit) |
| Module | `kmrp-controller.module`, 245,248 bytes, `4B1131DABC4550D5F4F18B2C52EE93291E8350C2B35FA2A5215660A0F4C13AD3`. Section 1a: `F2EDD742…`, 245,248 bytes, whose source differs from commit `5a33864`'s only in two log messages ("run KMRP's installer") and a comment |
| Installers | standalone `603DC45D…`, KMRP for KPM `1533474E…`; `KMRP.kpatch` `C27E108A…`, `KMRP Controller.kpatch` `56C45ED3…`, `KMRP Movies.kpatch` `014743BB…`, `KMRP Map Notes.kpatch` `D7977A3A…`. Section 1a: KMRP's one installer `D25212D7…` of 2026-09-29, 168,930,816 bytes, with `KMRP.kpatch` `8EBBE7FD…` (its description gives 66 resolutions), `KMRP Controller.kpatch` `C20F6623…`, `KMRP Movies.kpatch` `1DDA3E33…` and `KMRP Map Notes.kpatch` `D7977A3A…`; earlier that day `112CA755…` with KMRP for KPM `84AEBDC6…`, before the two became one |
| KPM runtime in KMRP's installer | built from the submodule `third_party/Kotor-Patch-Manager` at `71ac5fa`, FTD's `widescreen-patch` (first at `17fd051`, then `9884466`, all three with the same runtime sources and building the same bytes), since 2026-10-01 `2a784bf`, `RayesDiyab/Kotor-Patch-Manager` branch `kmrp` (FTD's `074972b` with one hook-list fix; nothing under `src/KotorPatcher` changed, and rebuilt from it the runtime was byte for byte the same), by `src/kpm-runtime/build.cmd`: `KotorPatcher.dll` 347,136 bytes `E7D6AE7F44ABA1FD…`, KProxy `binkw32.dll` 88,064 bytes `3A35A77EB4EEFC96…` ([src/kpm-runtime/README.md](../src/kpm-runtime/README.md)) |

The edition changed twice on 2026-09-28. It first shipped as two `.kpatch` files,
KMRP with and without its controller; then as four patches, one per fix, with
KMRP requiring KPM's 4GB and three memory-safety patches; and finally, to support
Steam's executable, with KMRP carrying those fixes itself (section 5).

Addresses are **VA** unless marked FILE. For the original sections `FILE = VA −
0x400000`; for gold's eleven appended sections `FILE = VA − 0x492000`
([`binary-inventory.md`](../reverse-engineering/binary-inventory.md)).

## 1. Two editions, one source

KMRP ships two ways, built by one `build_kmrp.ps1` run from the same sources.
This table compares the KPM edition with the standalone as they stood on
2026-09-28; section 1a says what KMRP's installer does since 2026-09-29, which is
the KPM edition's install plus KOTOR Patch Manager's runtime.

| | standalone (until 2026-09-29) | KPM edition |
| --- | --- | --- |
| Output | `dist\KMRP - KOTOR Modern Restoration Patch.exe` | `dist\KMRP for KPM\`: `KMRP for KPM.exe`, `KMRP.kpatch`, `KMRP Controller.kpatch`, `KMRP Movies.kpatch`, `KMRP Map Notes.kpatch`, README, KPM's MIT licence |
| Executables | CD 1.03 | CD 1.03 and **Steam's** |
| swkotor.exe | the gold delta written in, per resolution | **never modified** by KMRP. On CD 1.03 KPM sets the large-address flag from KMRP's own static hook; Steam's is left alone, since Steam refuses a changed file |
| Executable changes | in the file | applied in memory by KMRP's module, from `kmrp-kpm.dat` |
| Run-time hooks | KMRP's own copy of the KPM runtime, `patch_config.toml` written by the installer | KPM's runtime, from the `.kpatch` hook table |
| Memory-safety fixes | KMRP's copies of KPM's three patches | the same copies, in the KMRP patch, which conflicts with KPM's own |
| Driver compatibility | Synchro's standalone K1DC, optional | not installed; Synchro's own `.kpatch` in KPM |
| Controller, movies, map notes | the controller and map-note options are checkboxes; the movie fixes are always in | three optional patches, ticked in KPM beside the required `KMRP` |
| Override, `swkotor.ini`, DPI, NVIDIA | installed | installed, by the same code |

What is shared, so the editions cannot drift apart:

- **The executable's bytes.** The KPM installer builds the final image as the
  standalone does -- the embedded gold delta, `ResolutionPatch` for the resolution,
  the map-note flag on -- over the unmodified executable's bytes it carries
  (section 6), and records only how it differs from the unmodified executable, each
  change tagged with the patch it belongs to (`KpmEditionOperations.BuildData`,
  `src/patcher/KpmEdition.cs`). No per-resolution rule exists in two places, and
  `Test-KpmEdition.ps1` proves the result is the standalone's executable.
- **The hook sets.** Both come from `src/controller-native/kotor1.hooks.toml`
  through `tools/kmrp_controller.py`: `installed_set(controller)` for the
  standalone, `kpm_patch_hooks(id)` for each KPM patch, from the hook's
  `kpm_patch` key. The five hooks tagged `kpm_provided_by` are in both; the KPM
  edition's KMRP patch conflicts with the KPM patches that make them.
- **The module.** One binary: the standalone loads it from its own runtime, KPM
  from `patches\<id>.dll`, once for each KMRP patch that has hooks. Its applier
  runs only in an unmodified image, and only in the core patch's copy (below).

## 1a. KMRP's installer on KOTOR Patch Manager's runtime

Since 2026-09-29, at the maintainer's request -- "build its own KPM launcher that
accepts the editable version and the Steam version ... just do patch and then I
can start the game normally" -- KMRP's installer is the KPM edition's install
plus KOTOR Patch Manager's runtime, laid out as KPM's own proxy deployment lays
out a game folder (`KPatchCore/Applicators/KProxyInstaller.cs` and
`PatchApplicator.cs` in the submodule). The player starts the game as always,
from Steam or from `swkotor.exe`.

**One installer for both ways** (later the same day, at the maintainer's request:
"we should remove the for kpm version because this is already the standard
version"). Until then the same code compiled with `KPM_EDITION` was a second
installer, KMRP for KPM, for players who manage patches with KPM. Now the one
installer chooses per install (`KpmEditionOperations.Install`,
`src/patcher/KpmEdition.cs`): it installs **for KOTOR Patch Manager** -- the KPM
edition's install, no runtime, `swkotor.exe` untouched -- when KPM's runtime is
already in the game folder (`ForeignRuntimeFile`: `binkw32Hooked.dll`, `KotorPatcher.dll`,
`patch_config.toml` or `kpm_install_state.json` that this install did not write,
or that has changed since it did -- KPM's own Apply over KMRP's install replaces
them). *Corrected 2026-09-30:* until that day a *KOTOR Patch Manager* option in
Advanced Settings (`KmrpSettings.PatchManager`, saved as `kotorPatchManager`) chose
this install as well. It was removed at the maintainer's request ("the kpm option in
advanced settings is redundant now right?"): KMRP's own install is one KPM
recognises and takes over (section 1a), so the option only decided who installed the
runtime first, and on Steam with KPM 0.7.1 it left the runtime to KPM, which then
injected into a process Steam's executable hands off. The key is no longer read, and
`Test-KpmEdition.ps1` Case 9 checks a settings file that still has it on changes
nothing. Otherwise it installs
**with KPM's runtime**, as below.

**The `.kpatch` files are inside the installer** (later that evening, at the
maintainer's request: "cant we bundle it into the exe?"), so `dist\` is one file.
For KPM's app to list KMRP's patches they must be in its patch folder, which KPM
keeps in its settings (`%APPDATA%\KPatchLauncher\settings.json`, `PatchesPath`,
KPatchLauncher's `AppSettings` in 0.7.1, written by System.Text.Json, so the
installer unescapes `\\` and `\uXXXX`). `DeliverKpatches` puts the four there
when KPM names a folder that exists, on either kind of install; otherwise, for an
install for KPM only, into a `KPM patches` folder in the game folder, with the
README and KPM's licence, and says so. Each file is a `kpatch` row in the manifest:
`created` when it was not there, which restore removes while it is as written, or
`replaced` when it was -- an older copy of the same KMRP patch, by the `id` in its
`manifest.toml`, brought up to this version because KMRP's module refuses another
version's data file -- which restore leaves, so a file the player had is never
deleted. A file of the same name that is not KMRP's is left alone and reported.
`--export-kpm-patches <folder>` writes the set out for sharing. Until then the
files shipped beside the installer in `dist\KPM patches\`. `Test-KpmEdition.ps1`
Cases 1-2, 5, 11 and 12 cover it; the six suites that install park KPM's own
settings for their run, so a test never writes into a player's KPM folder. Seen
the same evening with KPM 0.7.1's window on the maintainer's game: its settings
named the game's `patches` folder, a normal install (`C4E01BB6…`) put the four
there, and KPM listed them at 1.5.0 with the game identified as KOTOR 1.0.3.

What KMRP's installer writes beside `swkotor.exe`:

| file | what | from |
| --- | --- | --- |
| `binkw32.dll` | KPM's proxy (KProxy). The game imports `binkw32.dll`, so the loader pulls the proxy in before the game's entry point; it forwards every Bink export to `binkw32Hooked.dll` and loads `KotorPatcher.dll` | `Kmrp.engine.proxy`, `src/kpm-runtime/build.cmd` |
| `binkw32Hooked.dll` | the game's own `binkw32.dll`, renamed, its hash recorded | the game |
| `KotorPatcher.dll` | KPM's runtime: reads `patch_config.toml` beside it, loads each patch's module, writes the hooks | `Kmrp.engine.runtime`, `src/kpm-runtime/build.cmd` |
| `patch_config.toml` | `target_version_sha` (`761F9466…` or Steam's `34E6D971…`), then `kmrp`, `kmrp-movies`, `kmrp-map-notes` (the marker option) and `kmrp-controller` (the controller option), in that order | each patch's section, `Kmrp.engine.config.<id>`, written by `tools/build_kpatch.py --config-dir` from the same hook table as its `.kpatch` and checked against it |
| `patches\kmrp.dll`, `patches\kmrp-movies.dll`, `patches\kmrp-controller.dll` | the module, one copy per patch with detours, as KPM extracts one per patch | `Kmrp.controller.module` |
| `kmrp-kpm.dat`, `kmrp-sdl3.dll`, its licence, `kmrp-controller.ini` | as KMRP for KPM (sections 4 and 6) | |
| `kmrp-kotor-patch-manager-LICENSE.txt` | KPM's MIT licence | the submodule's `LICENSE` |
| `kpm_install_state.json` | KPM's record of the game (`ManagedInstallState`, schema 1): on CD 1.03, that the flagged executable was CD 1.03; on both executables, that the proxy is installed (`LibraryProxyInstalled`), which KPM releases after 0.7.1 keep on Apply and Launch. Steam's executable has had one since the evening of 2026-09-29; before, CD 1.03 only | `KpmEditionOperations.KpmState` |
| `swkotor.exe.backup.<yyyyMMdd_HHmmss>` and its `.json` | CD 1.03, when the installer sets the 4 GB flag: the unmodified `swkotor.exe` as KPM backs one up, and KPM's metadata for it (`BackupManager`, `BackupInfo`) | `KpmEditionOperations.WriteKpmBackup` |
| `dinput8.dll`, `k1-modern-driver-compatibility.asi` | Synchro's K1DC, when that option is on | unchanged |
| KMRP's four `.kpatch` files | into KPM's own patch folder when KPM's settings name one, on either kind of install; otherwise, for KPM only, a `KPM patches` folder here with the README and KPM's licence (above) | `Kmrp.kpatch.*`, `DeliverKpatches` |

The order in the config is the point of it. KotorPatcher applies patches in order
and stops at the first hook that fails, so `kmrp` goes first -- its module's
`DllMain` applies `kmrp-kpm.dat` as it loads, before any other patch's hook is
written -- and `kmrp-controller` last, so that nothing the controller's 28 hooks
do wrong can keep the rest out.

**`swkotor.exe`.** On CD 1.03 the installer sets `IMAGE_FILE_LARGE_ADDRESS_AWARE`
(FILE `0x926`, `0x010F` to `0x012F`), the flag the standalone also set and that
KPM would set from `KMRP.kpatch`'s static hook, and checks the file becomes
`CA9D22EA…`; a file that already has the flag is left alone. Steam's executable is
never written: Steam refuses a changed file. KOTOR Patch Manager knows a game only
by its executable's hash, and `CA9D22EA…` is not one it knows, so two things are
left for it: just before setting the flag, a backup of the unmodified file as KPM
makes one, and on CD 1.03 always, `kpm_install_state.json`, which names the
executable's original. What each is for is under *When KOTOR Patch Manager takes
over*.

**The manifest,** `KMRP_KPM.manifest`, records every file written (`file`, name,
SHA-256), the rename (`moved binkw32.dll binkw32Hooked.dll <hash>`), and whether
it set the flag (`laa set`). Restore removes each file still as written, renames
the game's `binkw32.dll` back -- or, when Steam's file check has already put the
original back, deletes the now duplicate `binkw32Hooked.dll` -- and clears the flag
only if it set it and the file is still `CA9D22EA…`. Anything changed since is
left, and said so. A manifest line that names anything but a file in the game
folder or its `patches\`, or any rename but that one, is ignored.

**What it refuses, before changing anything:** with its own runtime, a game
folder without `binkw32.dll`. A folder where `binkw32Hooked.dll`,
`KotorPatcher.dll`, `patch_config.toml` or `kpm_install_state.json` already exists -- KOTOR Patch Manager's
runtime, or another mod that uses it -- is installed for KPM instead, KPM's files
left as they are; the first build of the day refused it. Until 2026-09-29 the
standalone's runtime step declined such a `patch_config.toml` and the rest
installed; now KMRP's executable changes are that runtime, so half an install
would be a broken game.

**When KOTOR Patch Manager takes over.** The config and layout are KPM's own, so
the KPM app can open a game KMRP installed this way: KPM 0.7.1 reads the
installed patches from `patch_config.toml` (`PatchRemover`: "patch_config.toml is
the source of truth for installed patch IDs") and treats a static hook whose
bytes are already the replacement as applied (`StaticHookApplicator`). What it
must also do is recognise the executable, and it knows one only by its hash.
When a player applies patches in KPM, its Apply first clears what it finds
(`PatchRemover.RemoveAllPatches`): it restores the newest backup of the
executable, `swkotor.exe.backup.<time>`, and deletes it (`BackupManager`),
deletes the modules in `patches\`, `patch_config.toml` and `KotorPatcher.dll`,
and puts the game's `binkw32.dll` back (`KProxyInstaller`); KMRP's data file,
SDL and Override files it does not know and leaves. Then it identifies the
executable (`GameDetector.DetectVersion`) and installs its own: a backup of the
executable as it finds it, the static hooks, a new `patch_config.toml`, its own
`KotorPatcher.dll`, KMRP's modules re-extracted -- the very bytes KMRP
installed -- the proxy, and `kpm_install_state.json`. Its "uninstall all", every
patch unticked in its window, is the same clearing step, and it also deletes
`kpm_install_state.json`. (All read in KPM 0.7.1's source: `PatchRemover.cs`,
`PatchApplicator.cs`, `BackupManager.cs`, `GameDetector.cs` and the window's
`MainViewModel.cs`.)

That is what the two files the installer leaves for KPM are for. Measured with
KPM 0.7.1's own launcher over KMRP's install in the scratch copy on 2026-09-29
(`KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-movies kmrp-map-notes
kmrp-controller fair-pazaak-turn-order --deployment proxy`, KMRP's four patches
and KPM's Fair Pazaak Turn Order):

| KMRP's installer left | KPM's Apply | KPM's backup afterwards |
| --- | --- | --- |
| neither (`5CCC1961…`) | refused every patch: "Game version: KOTOR Unknown (Other, Windows, x86) (hash: CA9D22EACB5BDFA8...)", after its clearing step had already removed KMRP's runtime | none |
| `kpm_install_state.json`, written by hand as `702034D8…` then wrote it | applied all five; the game ran with KMRP's 91 runs, 37 of 37 sites hooked and Fair Pazaak's hook | the flagged `CA9D22EA…` |
| both (`D25212D7…`) | restored KMRP's backup, `761F9466…`, deleted it, applied all five and set the flag itself from `KMRP.kpatch`'s static hook | the unmodified `761F9466…` |

The backup is what makes KPM's own undo complete. With the state file alone,
KPM backs up the flagged file, so its "uninstall all" would put back a flagged
executable and delete the state file, leaving a game KPM no longer recognises
(read in KPM's source; not run). With both, KPM's backup is the unmodified file.
Replaying KPM's clearing step by hand in the scratch copy -- the newest backup
restored, its runtime, config and state file deleted, the proxy undone -- left
`swkotor.exe` `761F9466…` and the game's own `binkw32.dll`; that was a
replay of the steps read in `PatchRemover.cs`, not KPM's window. The state file still
matters where the executable already had the flag before KMRP's install: then
there is no unmodified file to leave, and KPM recognises the game from it.

After the third Apply, the same game started from `swkotor.exe` directly:
KMRP's 91 of 91 runs applied 58 ms after start, memory exactly the data file's,
37 of 37 KMRP sites and Fair Pazaak's `REPLACE` hook at `0x00680085` in place,
"SUCCESS: Patcher initialized", and the main menu at 3440x1440 with KMRP's
layout. Through KPM's launcher the running header read `0x012F`, the flag KPM
set. KMRP's installer run again then installed for KPM, changing none of KPM's
files, its backup included.

So a changed `patch_config.toml` is taken as KPM having taken the runtime over:
the next install is one for KPM, and restore -- the one before it, or a plain
uninstall -- leaves every runtime file, the modules, the proxy, the rename, the
state file, the backup and the 4 GB flag in place for KPM, removing only KMRP's
own content (`ConfigChangedSinceInstall`, `IsRuntimeRecord`). Without that, a
reinstall would have deleted the modules KPM's config names, since their bytes
still matched the manifest. `Test-KpmEdition.ps1` Case 10 covers it.

Since 2026-10-01 (from the Mac, [`windows-changes-from-macos.md`](windows-changes-from-macos.md),
item 16) two things differ. A takeover is any runtime file the manifest records
changed, not `patch_config.toml` alone (`RuntimeChangedSinceInstall`): on the Mac
KPM 0.7.1's Apply wrote the config byte for byte as KMRP had. And a restore
(not a reinstall) after a takeover with only KMRP's patches in KPM's config, state
file and `patches\` removes KPM's runtime too, as KPM's own removal would, and
puts back the untouched executable from KPM's backup (`KpmHoldsOnlyKmrp`,
`RemoveKpmRuntime`); with another patch there it leaves the runtime, as above.
Cases 10b and 10c cover the two.

**Keeping the proxy when KPM applies.** KPM 0.7.1 picks the deployment on every
Apply and Launch from its global *Use library proxy* setting alone. With it off,
the Windows default, an Apply over this install moves the game to injection: the
clean-up puts the game's `binkw32.dll` back, and KMRP then loads only when the
game is started with KPM's Launch. Started directly it ran unpatched, 0 of 37
hook sites (measured 2026-09-29). This was fixed in KPM rather than worked around:
[LaneDibello/Kotor-Patch-Manager#283](https://github.com/LaneDibello/Kotor-Patch-Manager/pull/283),
merged the same evening, keeps the method a game's `kpm_install_state.json`
records, in both directions, on Apply and on Launch, and at Launch injects where
a recorded proxy is gone after Steam's file check. KMRP's installer records the
proxy there on both executables, so from KPM's first release after 0.7.1 an
Apply in KPM keeps KMRP working with nothing to set. KPM's merged code, run
against the state file the installer writes over Steam's executable, identified
Steam's 1.03 and kept the proxy for Apply and Launch with the setting off. With
0.7.1, tick *Use library proxy* before Apply; it is greyed out while patches are
installed, so press Uninstall All first. A workaround in the installer, turning
that global setting on in KPM's own settings file, was begun and dropped the same
evening: it would have been obsolete with KPM's next release, and on 0.7.1 it
would have changed the method for every other game KPM manages.

*Corrected 2026-09-29:* this paragraph said the takeover was read from KPM's
source and "not yet tried with the KPM app", that KPM would identify the flagged
executable from `patch_config.toml`'s `target_version_sha`, and that its Apply
leaves `swkotor.exe` as it is. The first run refused: the clearing step deletes
`patch_config.toml` before the executable is identified. And KPM's Apply does
restore an executable, from a backup of its own, when one exists.

**Upgrading from the standalone.** An install by any earlier KMRP, which wrote
`swkotor.exe`, is restored first with that install's own records and backups
(`PatchOperations.RestoreStandalone`, kept for this): the executable from its
backup, its runtime, K1DC, Override and the INI. With a missing or damaged backup
the install is refused and nothing changes.

**When it runs.** On CD 1.03 the proxy is loaded with the game's static imports,
so KotorPatcher applies at once: the applier's log gave "484 ms after the game
started, before its window; 1 other thread(s) paused while writing". Steam's
code is still encrypted at that point, so KotorPatcher hands the apply to a
worker that waits for SteamStub to decrypt (`DeferredApply`, polling every 15 ms
for up to 30 s): "913 ms after the game started, before its window; 6 other
thread(s) paused".

**Measured in game, 2026-09-29**, at 3440x1440 with every option on, the game
started as a player starts it:

| run | `swkotor.exe` | applier | memory (`kpm_data.py --memory`) | hook sites |
| --- | --- | --- | --- | --- |
| CD 1.03, scratch copy, installed over the standalone `061AD6A2…` | `761F9466…` restored by the upgrade, then `CA9D22EA…` | 91 of 91 runs (582 bytes), KMRP's code at `0x00F40000` (moved by `+0x6D3000`), 46 relocations | core, movies and map notes exactly | 37 of 37 hooked, none unexpected |
| Steam, the maintainer's test install, started through Steam | `34E6D971…`, unchanged | 91 of 91 runs, KMRP's code at `0x001D0000` (moved by `−0x69D000`) | exactly | 37 of 37 |

Both reached the main menu at 3440x1440 with KMRP's layout; on CD a save was
loaded and the Skills and Inventory screens checked (the skill icons' fit is in
the changelog). On Steam K1DC also ran ("hooks installed=8/8"). KotorPatcher's own
output, read over `OutputDebugString`, ended "SUCCESS: Patcher initialized" on
CD. The installer builds were `F7960D68…` for both runs and `09940BAA…` and
`B1F137B7…` for the icon checks; the release candidate `112CA755…` differs from
them in the skill icons and in KMRP for KPM's refusal text, not in the install.
The Steam folder was restored afterwards and checked against backups taken before
the first Steam trial: `swkotor.exe` `34E6D971…`, `binkw32.dll` `2D0AE23A…` and
`swkotor.ini` `85B1C89B…` identical, `Override` empty; the files the game itself
wrote while running (`kmrp-kpm.log`, `kmrp-native-joystick.log`, K1DC's
`K1DriverCompat.ini` and `logs\`) were removed by hand, since restore removes only
what the installer wrote.

Not verified: gameplay beyond the menus on Steam (its test install carries the
maintainer's cloud save, so it was not loaded), any resolution but 3440x1440 in
game, and Steam's "verify integrity" (which by its design replaces `binkw32.dll`;
installing again puts KMRP back).

**Rejected, for the loader.** K1DC's ASI loader (`dinput8.dll`), which loaded the
standalone's runtime: that runtime, a static build from Saul0097's package, has no
wait for SteamStub, and a `dinput8.dll` of KMRP's own would clash with any other
ASI loader a player has. KPM's injection: it needs KPM's launcher, and Steam's
executable hands its launch to Steam, so the injected process exits (measured
2026-09-28). KPM's own `KotorPatcher.dll` build: linked dynamically, it needs the
Visual C++ redistributable ([src/kpm-runtime/README.md](../src/kpm-runtime/README.md)).

## 2. What the module applies, and why the code has to move

Gold's delta has three parts; the KPM edition reproduces all three in memory:

| part | size | in the KPM edition |
| --- | --- | --- |
| Runs in the original image | 81 runs in `.text` (560 bytes) and 2 in `.rdata` (5 bytes) at the byte level; 89 to 91 runs of 576 to 582 bytes once the per-resolution values and the relocated fields are added (measured at 1024x768, 1920x1080, 3440x1440) | written by the module after every original byte is checked |
| Eleven appended sections, `.kui` ... `.kmv`, `0x0086D000`-`0x00877FFF` | 45,056 bytes, 5,726 used | copied as one block into memory the module allocates, and relocated |
| PE header | 71 byte-runs, 156 bytes | not written by the module. Only the large-address flag matters at run time: on CD 1.03 KPM writes it into the file from the KMRP patch's static hook; Steam's executable cannot take it |

**The sections cannot go back to their own addresses.** In an unmodified process
the range is not free: measured on 2026-09-28 with `VirtualQueryEx` over a running
unmodified game from its first sample to the main menu, `0x0086D000`-`0x0086FFFF`
is free and everything from `0x00870000` is a mapped view (`COMMIT MAPPED`,
`0x11000` bytes). The three free pages are also below the 64 KB allocation
granularity after the image's end, so nothing can be reserved there either. So the
block is copied, layout intact, to wherever `VirtualAlloc` puts it, and every
address that names it is moved by the difference.

## 3. Every field that moves: the relocation table

`tools/kpm_relocations.py` finds them in gold, twice, by independent methods that
must agree: a byte scan (every changed byte and every byte of the block's decoded
code, for `E8`/`E9`/`0F 8x` rel32 branches and 32-bit values in range), and
disassembly (aligned linear sweeps over the changed runs, recursive descent through
the block from the inbound entry points). It stops the build otherwise. It then
**proves** the table: it moves the block to a test base, relocates, and
disassembles all 443 decoded instructions again -- each must be the same
instruction with every operand that named the block moved by exactly the delta and
every other operand unchanged -- and it re-discovers every inbound reference on its
own and requires each to be relocated. A table missing any one entry fails, which
was checked by dropping entries of each kind (2026-09-28).

It also refuses what it cannot relocate: an indirect jump through a register or the
block (a switch table), or a value naming the block stored in the block's data.
There are none. Indirect calls are allowed: `.kmv`'s `call [0x0073D484]` goes
through the import table, and `.kfs`'s `call edx` and `.klb`'s `call [edx+4]` are
virtual calls through game objects' vtables.

`IN` fields are outside the block and name it (add the delta); `OUT` fields are in
the block and name game code (subtract it); `ABS` fields are in the block and name
the block (add it). A rel32 from the block to the block needs nothing.

| kind | field VA | FILE | where | instruction |
| --- | --- | --- | --- | --- |
| IN | `0x004057ad` | `0x0057ad` | .text | `0x004057ac` `jmp 0x877000` |
| IN | `0x00415e0e` | `0x015e0e` | .text | `0x00415e0d` `jmp 0x873000` |
| IN | `0x00417993` | `0x017993` | .text | `0x00417992` `jmp 0x86f1c5` |
| IN | `0x0041a2f3` | `0x01a2f3` | .text | `0x0041a2f2` `jmp 0x872024` |
| IN | `0x0041b46e` | `0x01b46e` | .text | `0x0041b46d` `jmp 0x872000` |
| IN | `0x0045992b` | `0x05992b` | .text | `0x0045992a` `jmp 0x874000` |
| IN | `0x0045a5ec` | `0x05a5ec` | .text | `0x0045a5eb` `jmp 0x870000` |
| IN | `0x0045a851` | `0x05a851` | .text | `0x0045a850` `jmp 0x86f19a` |
| IN | `0x004a1771` | `0x0a1771` | .text | `0x004a1770` `jmp 0x86f178` |
| IN | `0x0062b39c` | `0x22b39c` | .text | `0x0062b39b` `call 0x86d130` |
| IN | `0x0068aca0` | `0x28aca0` | .text | `0x0068ac9f` `call 0x875000` |
| IN | `0x006946f5` | `0x2946f5` | .text | `0x006946f4` `call 0x86d000` |
| IN | `0x00694a3a` | `0x294a3a` | .text | `0x00694a39` `call 0x86d080` |
| IN | `0x00694aad` | `0x294aad` | .text | `0x00694aac` `call 0x86d080` |
| IN | `0x006a7cd1` | `0x2a7cd1` | .text | `0x006a7cd0` `jmp 0x86e000` |
| IN | `0x006a8e1e` | `0x2a8e1e` | .text | `0x006a8e1d` `jmp 0x86e03f` |
| IN | `0x006b5337` | `0x2b5337` | .text | `0x006b5336` `jmp 0x871000` |
| IN | `0x0075477c` | `0x35477c` | .rdata | pointer `0x0086D100` (.kui) |
| OUT | `0x0086d129` | `0x3db129` | .kui | `0x0086d128` `jmp 0x693300` |
| OUT | `0x0086d13b` | `0x3db13b` | .kui | `0x0086d13a` `call 0x694d50` |
| OUT | `0x0086e03b` | `0x3dc03b` | .klb | `0x0086e03a` `jmp 0x6a7cec` |
| OUT | `0x0086e06a` | `0x3dc06a` | .klb | `0x0086e069` `jmp 0x6a8e26` |
| ABS | `0x0086f110` | `0x3dd110` | .kfs | `0x0086f10e` `mov ecx, dword ptr [0x86f008]` |
| ABS | `0x0086f11d` | `0x3dd11d` | .kfs | `0x0086f11a` `cmp eax, dword ptr [edx*4 + 0x86f00c]` |
| ABS | `0x0086f12e` | `0x3dd12e` | .kfs | `0x0086f12b` `mov dword ptr [ecx*4 + 0x86f00c], eax` |
| ABS | `0x0086f135` | `0x3dd135` | .kfs | `0x0086f133` `mov dword ptr [0x86f008], ecx` |
| ABS | `0x0086f13e` | `0x3dd13e` | .kfs | `0x0086f13c` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f14a` | `0x3dd14a` | .kfs | `0x0086f148` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f156` | `0x3dd156` | .kfs | `0x0086f154` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f162` | `0x3dd162` | .kfs | `0x0086f160` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f16e` | `0x3dd16e` | .kfs | `0x0086f16c` `fmul dword ptr [0x86f000]` |
| OUT | `0x0086f196` | `0x3dd196` | .kfs | `0x0086f195` `jmp 0x4a177d` |
| OUT | `0x0086f1c1` | `0x3dd1c1` | .kfs | `0x0086f1c0` `jmp 0x45a857` |
| ABS | `0x0086f1ce` | `0x3dd1ce` | .kfs | `0x0086f1cc` `fmul dword ptr [0x86f004]` |
| OUT | `0x0086f1de` | `0x3dd1de` | .kfs | `0x0086f1dd` `jmp 0x41799c` |
| OUT | `0x0087000d` | `0x3de00d` | .kwl | `0x0087000c` `jmp 0x45a785` |
| OUT | `0x00871029` | `0x3df029` | .ksc | `0x00871028` `jmp 0x6b5356` |
| OUT | `0x00872020` | `0x3e0020` | .kgs | `0x0087201f` `jmp 0x41b479` |
| OUT | `0x00872046` | `0x3e0046` | .kgs | `0x00872045` `jmp 0x41a301` |
| OUT | `0x00873026` | `0x3e1026` | .ktn | `0x00873025` `jmp 0x415e12` |
| OUT | `0x008740b1` | `0x3e20b1` | .kmz | `0x008740b0` `jmp 0x459944` |
| OUT | `0x00875064` | `0x3e3064` | .kfg | `0x00875063` `call 0x688100` |
| OUT | `0x00875090` | `0x3e3090` | .kfg | `0x0087508f` `call 0x688100` |
| ABS | `0x00876fbc` | `0x3e4fbc` | .kmn | `0x00876fba` `cmp dword ptr [0x876000], 0` |
| ABS | `0x00876fc8` | `0x3e4fc8` | .kmn | `0x00876fc7` `mov edi, 0x876010` |
| OUT | `0x0087704d` | `0x3e504d` | .kmv | `0x0087704c` `jmp 0x405808` |

**18 + 16 + 12 = 46 fields.** The first ad-hoc scan found 16 inbound fields; the
seventeenth, the branch into `.ktn` at `0x00415E0D`, was missed because Capstone's
`disasm()` stops at the first undecodable byte, so a sweep that met data inside
`.text` went silent and two silent sweeps "agreed" on nothing. The byte scan found
it; the sweep now steps over undecodable bytes. That is why neither method is
trusted alone.

## 4. `kmrp-kpm.dat` and the applier

The KPM installer writes `kmrp-kpm.dat` beside the game. Little-endian:

| field | contents |
| --- | --- |
| magic, version | `KMRPKPM2`, 2 (version 1, `KMRPKPM1`, had no patch tags and is refused) |
| block | VA `0x0086D000`, size `0xB000`, 11 page protections (`PAGE_EXECUTE_READWRITE` for `.kfs`, `PAGE_EXECUTE_READ` for the rest, from the sections' characteristics), then the 45,056 final bytes with the map-note flag cleared |
| runs | count, then per run: patch bit, VA, length, the unmodified bytes, the final bytes. Every IN field lies whole inside a run |
| block edits | count, then per edit: patch bit, offset in the block, length, bytes |
| relocations | count, then per field: kind (1 IN, 2 OUT, 3 ABS) and VA |
| checksum | FNV-1a of everything before it |

The patch bits are 1 for KMRP itself, 2 for KMRP Movies and 4 for KMRP Map Notes;
KMRP Controller changes no executable byte. What belongs to the two optional
patches is decided in `BuildData`, and each run belongs to exactly one:

| patch | what | where |
| --- | --- | --- |
| KMRP Movies | the four movie display-mode operands, per resolution | `0x00403D6C`, `0x00403D78`, `0x005F5B3B`, `0x005F5B43`, 4 bytes each (fewer where a resolution's value shares bytes with 640 or 480) |
| KMRP Movies | the jump into the movie aspect fit | the run `0x004057AC`, 7 bytes (`jmp 0x877000` and two `nop`s), found as the run whose IN field leads into `.kmv` |
| KMRP Map Notes | the `.kmn` enable flag | block edit at `0x00876000`, 4 bytes |

`BuildData` refuses to build a file where a movie run would hold anything else --
an operand run reaching past its operand, or an entry run that also leads
somewhere other than `.kmv` -- or where a relocation overlaps the flag. With KMRP
Movies left out, `.kmv` stays in the block, unreached; with Map Notes left out, the
lookup the map wrapper always calls returns at once, as it does in the standalone
with the marker fixes off.

The module's applier (`src/controller-native/K1KpmApplier.cpp`) runs in its
`DllMain`. KPM loads a patch DLL at that patch's first detour hook, inside
`KotorPatcher.dll`'s own start-up and before any game code runs, for the CD and GOG
executables (read in KPM 0.7.1's `patcher.cpp`, `ProcessInjector.cs`). Every copy
of the module:

1. returns at once unless the image is unmodified -- CD 1.03's (base `0x400000`,
   four sections, `SizeOfImage` `0x46D000`) or Steam's (five sections, the fifth
   `.bind`, `SizeOfImage` `0x4C3000`) -- so in the standalone edition, whose
   executable already carries all of this, it does nothing;
2. reads which KMRP patches are installed from the `patch_config.toml` KPM wrote
   beside the game: every `id = "…"` line, looking for `kmrp-movies` and
   `kmrp-map-notes`.

The core patch's copy, `patches\kmrp.dll`, then:

3. reads and checks the data file (magic, checksum, layout);
4. checks the unmodified bytes of every run it will write, in memory, **before
   writing anything**;
5. allocates the block, copies it, makes the chosen patches' block edits, applies
   the relocations -- an IN field in a run left out is skipped with its run --
   and sets its page protections;
6. pauses every other thread of the game, retrying while any is stopped inside a
   run, writes the chosen runs, putting back any already written if one fails, and
   lets the threads go.

All or nothing: any failure logs the reason to `kmrp-kpm.log` beside the game and
leaves the game unmodified. Success logs two lines such as `applied: KMRP + Movies
+ Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 02CD0000 (moved by
+38154240), 46 relocations.` and `Steam executable; 457 ms after the game started,
after its window; 8 other thread(s) paused while writing.` (measured on Steam at
1920x1080).

**On Steam the game is already running.** Steam's executable is CD 1.03's program
behind SteamStub: its code is encrypted on disk, and once the stub has decrypted it
in memory it is CD 1.03's byte for byte -- all 3,387,856 bytes of `.text`, every
one of KMRP's 115 spans and the five memory-safety sites (read from a running game
on 2026-09-28). The only other differences are the stub's `.bind` section and the
letter case of eight DLL names in `.rdata`'s import table. But KPM can only patch it
after decryption: its runtime finds every hook site unreadable at load and hands the
apply to a worker thread that polls every 15 ms (`patcher.cpp`, `DeferredApply`,
the same in 0.7.1's source). Measured from outside, the code reads decrypted about
332 ms after the process starts and the game's window exists 20 ms later; KMRP
applied at 457 ms in the trial and at 501 ms with the final build (whose window,
that time, came later still). That is before any screen KMRP changes is built -- the main menu,
character generation, Options and movies all matched CD 1.03's captures (section 7)
-- and the pause in step 6 keeps the game's own threads out of the bytes being
written.

**Frames shared between patches.** The controller's GUI and movie frames hook the
same two sites as the core's stand-ins (`0x0040CE70`, `0x00404D96`), and KPM allows
one patch per address. So the core holds both (`kpm_patch = ""` on the controller's
two), and its stand-ins look once for `kmrp-controller.dll` among the loaded modules:
when KMRP Controller is installed its frame runs **instead of** the stand-in's work,
exactly as it holds the site in the standalone edition; otherwise the stand-in does
its own (mouse confinement and the status summary; movie tracking).

**The movie window's black fill is KMRP Movies'.** Its two window hooks
(`0x0040554B`, `0x00404BB0`) are carried by KMRP Movies itself (`kpm_patch =
"kmrp-movies"`), and every copy of the module asks `KpmMoviesOffK1` before painting
the bars, so without KMRP Movies KMRP leaves the movie window as the game draws it.

Why at `DllMain` rather than in a hook: KPM re-checks each detour's bytes as it
writes it, and a DLL loads at its patch's first detour. The applier's runs and
KMRP's own hook sites are disjoint -- `tools/build_kpatch.py --check` requires every
hook's bytes to be the same in the unmodified executable and in gold -- so the
order does not matter to KMRP's hooks. Another patch hooking a byte KMRP changes
would fail either way, which is the conflict KPM's own byte checks are for.

## 5. The `.kpatch` files

`tools/build_kpatch.py` renders them from the tracked table:

| file | id | hooks | requires | conflicts |
| --- | --- | --- | --- | --- |
| `KMRP.kpatch` | `kmrp` | 13: two core frames, five memory-safety hooks, three popup hooks, and three keyboard hooks; its module applies the engine recipe. CD/GOG also carry the separate static large-address header hook | none | `hud-minimap-map-size-fix-v1`, `scaled-kotor`, and the four KPM patches whose fixes it makes: `4gb-patch`, `grass-memory-safety`, `save_mem_leak`, `texture-bucket-safety` |
| `KMRP Controller.kpatch` | `kmrp-controller` | 28: the controller set, less the two frames the core holds, the movie window's two and the memory-safety five | `kmrp` | `expanded-keyboard-control`, `xbox-controls-k1` |
| `KMRP Movies.kpatch` | `kmrp-movies` | 2: `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1`; selects the movie runs | `kmrp` | `better-movie-playback-v1` |
| `KMRP Map Notes.kpatch` | `kmrp-map-notes` | none; selects the `.kmn` flag | `kmrp` | none |

Every patch supports CD 1.03 (`kotor1_cdcrack_103`), GOG (`kotor1_gog_103`), and
Steam (`kotor1_steam_103`). With all four ticked there are 43 runtime hook sites;
turning controller support off leaves 15. These counts are derived from
`kmrp_controller.kpm_patch_hooks`, excluding the CD/GOG static header hook.
**Correction, 2026-10-03:** the earlier table's core count of 7 omitted the three
popup hooks added on 2026-09-30. The keyboard source port adds three more core
hooks, independent of controller support; its physical-keyboard and live mouse/
controller checks remain pending. See the
[Windows reference](../reverse-engineering/windows-keyboard-navigation.md).

**Why KMRP carries the memory fixes itself.** KPM 0.7.1 has one `requires` list per
patch, checked the same on every game version (`ManifestParser.cs`,
`DependencyValidator.cs`), and Texture Bucket Safety and Grass Memory Safety list no
Steam executable. KPM's 4GB Patch lists Steam's but writes the CD/GOG header offset
(`0x00400926`; Steam's `e_lfanew` is `0x110`, its flag at `0x00400126`), so KPM
refuses it -- and Steam refuses any changed executable anyway ("Application load
error 3:0000065432", seen 2026-09-28 with the flag written at the right offset). So
a KMRP that required them could not be installed on Steam. No KPM 0.7.1 patch
requires any of the four, so conflicting with them costs a player nothing: KMRP
does their job. The large-address flag is a static hook in a separate hooks file,
`kotor1-cd-large-address.hooks.toml`, targeting CD 1.03 alone and derived by
`build_kpatch.py` from the unmodified header (`Characteristics` OR `0x0020`, the
standalone's own one-bit change).

Why the other conflicts: Movie Patch (`better-movie-playback-v1`) also keeps movies in
the game window and fits their aspect; its hook at `0x00405855` is 162 bytes past
the jump into KMRP's `.kmv` fit at `0x004057AC`. Map Texture Patch
(`hud-minimap-map-size-fix-v1`) forces a 512x256 minimap draw size at
`0x0068ABF8`, 163 bytes before KMRP's call into its fog grid at `0x0068AC9F`, which
is the core's; whether both are in one function was not established. Scaled Kotor
is a competing widescreen patch.

`KMRP.kpatch`, `KMRP Controller.kpatch` and `KMRP Movies.kpatch` each hold
`manifest.toml`, `kotor1.hooks.toml` (tagged with the CD 1.03 and Steam hashes) and
`binaries/windows_x86.dll`, the module; `KMRP.kpatch` also the CD-only
large-address hooks file. `KMRP Map Notes.kpatch` holds only its
manifest: KPM lists such a patch, installs it, writes it into `patch_config.toml`
as `id = "kmrp-map-notes"` with an empty `dll`, and its runtime skips it -- read in
KPM 0.7.1's `PatchRepository.cs`, `PatchApplicator.cs` (step 5 skips a patch with
no module and no detours) and `config_reader.cpp` ("has no hooks and no DLL -
skipping"). A module with no hooks would instead be loaded as a DLL-only patch,
which `--check` refuses.

**Measured, not guessed.** `tools/check_kpm_overlaps.py` intersects KMRP's
footprint -- every byte the delta changes, every KMRP hook site and the
large-address flag, 121 spans, 795 bytes -- with every hook of every K1 patch KPM
0.7.1 ships: exactly the four declared overlaps (4GB Patch at the flag; Grass
Memory Safety, Save Game Memory Leak and Texture Bucket Safety at the five
memory-safety sites), **no undeclared overlap**, and no hook within 32 bytes. It
fails on an overlap no KMRP patch declares; checked by dropping `4gb-patch` from the
conflicts. Movie Patch and Map Texture Patch are conflicts by behaviour,
found by widening the search to 1,024 bytes; Semi-Transparent Letterbox, also near
KMRP's letterbox runs, only changes the letterbox's alpha and is compatible. High
FPS Fixes 1.0.0 (a third-party `.kpatch`, not in KPM's set) has no byte of its 36
hooks on any byte KMRP changes; its nearest is 39 bytes from a KMRP run in the
dialogue letterbox routine.

`--check` replays KPM 0.7.1's install-time rules, read from its source: manifest
fields; integer addresses in range; one hook per start address, across all four
patches since a player may tick them all; detour with a function, five or more
stolen bytes, and `eax` excluded when it has a consumed exit; a module exactly when
there are detours; the original bytes against the unmodified executable (KPM's
pre-install check); every function exported by the module; exactly the four KMRP
patches, so a stale one from an earlier build fails; both executables supported,
and every hooks file targeting only supported ones; and a static hook only in the
header, with the header's own bytes, targeting CD 1.03 alone. Planted faults -- an
empty author, a wrong stolen byte, a missing export, a hook on a byte the delta
changes, two patches on one address, a module in the marker patch, detours without
a module, a leftover `kmrp-no-controller`, the static hook aimed at Steam, a wrong
header byte, and Steam dropped from a manifest -- are each reported.

## 6. The install for KOTOR Patch Manager

Written when this was the KMRP for KPM installer: the same code as the
standalone, compiled with `KPM_EDITION`. Since 2026-09-29 it is the one
installer's install for KOTOR Patch Manager (section 1a), and everything below
still describes it. Its `Inspect`, `Describe`, `CanRestore`, `ApplyInPlace`,
`Restore` and `TryReadInstalledResolution` go to `KpmEditionOperations`. It:

- accepts the unmodified 1.03 executable, with or without the large-address flag,
  and Steam's (`KpmEditionOperations.IsSteam`), and refuses a game the standalone
  installer patched (restore that first). The standalone refused Steam's executable
  with its own message: Steam will not start it patched, use KMRP for KPM (until
  2026-09-29, when KMRP's installer began installing it, section 1a);
- builds the data file from the **unmodified executable's bytes it carries**, not
  from the player's file, since Steam's is encrypted on disk: `Kmrp.kpm.originals`
  (`tools/kpm_originals.py`, 91 ranges, 4,777 bytes, 681 of them past the header)
  holds CD 1.03's header, its bytes under every gold-delta chunk, every inbound
  relocation field whole and every field `ResolutionPatch` handles whole, and zero
  stands for everything else (`OriginalsImage`, `GoldPatch.ApplyToOriginals`). The
  resolution fields come from the installer itself: the build runs the standalone
  it just compiled with `--kpm-sites`, which applies every resolution in the
  catalog while `ResolutionPatch` records every field it reads or writes (52), so
  the list cannot drift from the code. (49 resolutions when this was written; the
  66 of 2026-09-29 touch the same 52 fields, and the originals are unchanged: 91
  ranges, 4,777 bytes. Since that day the build compiles a small `kmrp-sites.exe`
  for this, because KMRP's installer now embeds the originals too.) The first version carried only the chunks and relocated
  fields, and the installer refused its own picture -- "The stack-count label patch
  did not match the verified gold build" -- because gold changed only some bytes of
  some fields and none of a few (the powers row height stays vanilla's 40). The tool
  proves the coverage before the build embeds it, and a data file built this way at
  1920x1080 is byte for byte the one the earlier, file-reading installer wrote
  (`28DAA6A9…`);
- installs Override, `swkotor.ini`'s resolution, DPI and NVIDIA settings with the
  standalone's own code;
- writes `kmrp-kpm.dat`, `kmrp-sdl3.dll` and its licence beside the game -- KPM
  extracts only a patch's module, so the module also looks for SDL in the game
  folder (`K1ControllerBackend.cpp`) -- and `kmrp-controller.ini` if absent;
- records them with hashes in `KMRP_KPM.manifest`; Restore removes only files whose
  hashes still match;
- ignores the standalone's saved marker-fix setting: the data file always carries
  the map notes, as KMRP Map Notes' edit. Its settings page shows no options, and
  says which patches to tick in KPM instead.

It embeds everything the standalone does except KMRP's runtime, the standalone
module and Synchro's standalone K1DC.

## 7. How it was verified

The table below is the snapshot-era record. **Current verification, 2026-10-01:**
`Test-WindowsEngineSource.py` compiles the installer sources and verifies all
68 historical runs, 81 authored guard runs, eleven pages, 46 relocations and
69 sizes without a game executable. `Test-KpatchSource.py` checks the four
packages and rejects corrupted original bytes, LAA replacement bytes, missing
hooks and missing target versions. The current build no longer invokes
`tools/kpm_originals.py` or the old executable-based relocation command.
See [Windows engine source](windows-engine-source.md) and the
[Ubuntu launch/gameplay record](linux-proton-steam-deck.md).

| check | result |
| --- | --- |
| `tools/kpm_relocations.py` | 46 fields, both methods agree, 443 instructions proved after a move; dropping any entry fails |
| `tools/build_kpatch.py --check` | the four patches pass KPM 0.7.1's rules; eleven planted faults each caught (section 5) |
| `tools/check_kpm_overlaps.py` | 121 spans, 795 bytes: exactly the four declared overlaps with KPM's 4GB and memory-safety patches, no undeclared one; dropping a declared conflict fails |
| `tools/kpm_originals.py` | run by every build: the carried bytes cover every changed byte, every relocated field and all 52 resolution fields; a dropped range fails. The data file built from them at 1920x1080 is byte for byte the file-reading installer's (`28DAA6A9…`) |
| `Test-KpmEdition.ps1` (107 checks, final build `603DC45D…`) | at 1920x1080, 3440x1440, 1024x768, the KPM install made with the standalone's marker setting off: the executable stays byte-for-byte unmodified; **the data file makes exactly the standalone's executable** with all four patches, every byte of every original section and of the eleven sections (`tools/kpm_data.py --equals`); **without Map Notes, exactly the standalone's with its marker fixes off**; without Movies, the same less exactly the movie sites; the Movies runs lie within the four operands and the aspect-fit entry and cover them all (5 runs), and Map Notes is exactly the `.kmn` flag; reinstall at another resolution; restore; a standalone-patched game refused and left alone. **Steam's executable**: installed over and left unmodified, the data file byte for byte the editable executable's at the same resolution, restored; the standalone refuses it |
| In game, final build, the editable executable | `KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-controller kmrp-movies kmrp-map-notes` -- no KPM patch ticked -- in a scratch copy at 1920x1080: 91 of 91 runs, KMRP's code at `0x00F40000`, memory exact, **all 37 sites hooked** (the five memory-safety sites by KMRP's own copies), and **the large-address flag set by KMRP's static hook**: the file became `CA9D22EA…` (CD 1.03 with only that bit) and the running game's header reads `0x012F`. The applier logged 293 ms after start, before the window, 3 other threads paused. Main menu with the A prompt |
| In game, Steam's executable, trial build | a clean Steam install lent by the maintainer, 1920x1080, KPM's proxy deployment, the game started by Steam: 91 of 91 runs at `0x02CD0000`, memory exact, 37 sites hooked; applied 457 ms after start, after the window, 8 other threads paused. Main menu, character creation (class selection, Quick or Custom), Options and a movie compared with the editable executable's captures: Options pixel-identical, the rest differing only in the randomly chosen character models and animation frames; the movie played at 1920x1080 with no mode switch. The trial had the final module (`4B1131DA…`) and the same data file (`28DAA6A9…`); only its KMRP patch differed, requiring KPM's Save Game Memory Leak instead of carrying that hook |
| In game, Steam's executable, final build | 2026-09-29, the same install: the final installer installed over it (executable untouched, data file `28DAA6A9…`, 1,846 Override files), KPM applied the four KMRP patches through its proxy, and Steam started the game: `applied: KMRP + Movies + Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 001D0000 (moved by -6934528)` -- the first run with the block placed *below* the image, and **`tools/kpm_data.py --memory` exact** there too -- 501 ms after start, before the window, 6 other threads paused; all 37 sites hooked. The same screen sequence as the trial, driven by the virtual pad: Options pixel-identical to the editable executable's capture, the others differing only in the random character models (checked by eye on the largest, Quick or Custom, 2.2%), the movie at 1920x1080 with no mode switch. A first attempt the evening before was not started: Steam reported the account already playing KOTOR on another computer (the maintainer's macOS session). After each run the install was restored and checked against its backups |
| Steam's executable, measured | decrypted in memory, `.text` byte for byte the editable executable's, all 115 KMRP spans and the five memory-safety sites identical; `.rdata` differs only in the import table and in the letter case of eight DLL names. Writing the large-address flag into the file at its own offset made Steam refuse to start it ("Application load error 3:0000065432") |
| In game, the four-patch build before it was self-contained (`125DEA64…`), all four patches | KPM 0.7.1's own launcher, `KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-controller kmrp-movies kmrp-map-notes` and the four required, in a scratch copy at 1920x1080: KPM installed the manifest-only Map Notes and listed it in `patch_config.toml`; `kmrp-kpm.log`: `applied: KMRP + Movies + Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 01600000 (moved by +14233600), 46 relocations.`; **`tools/kpm_data.py --memory`: every run and every block byte exactly** (the only exemption is `.kfs`'s own cache, which the game writes); all 37 hook sites hooked. Main menu with the A prompt; the D-pad moves focus; a movie plays at 1920x1080, fitted, and the pad's A skips it -- the core's two frames handing over to KMRP Controller's |
| In game, `125DEA64…`, KMRP and KMRP Controller | `applied: KMRP -- 86 of 91 runs (564 bytes)`, code at `0x01D90000`: memory exact with the five movie runs **left as the game's own** and the map-note flag clear; 35 sites hooked, the movie window's two untouched; the pad works; the Republic Commando teaser **switches the display to 640x480** as the unmodified game does, and the pad's skip returns to the list at 1920x1080 |
| In game, `125DEA64…`, KMRP, Movies and Map Notes, no controller | 91 of 91 runs, code at `0x010F0000`: memory exact; 9 sites hooked (KMRP's four and KPM's five); no prompts, the D-pad inert; the teaser, started with the mouse, plays at 1920x1080 fitted -- the core's own copy painting |
| The first, two-variant design | earlier the same day: memory exact at `0x01560000` and `0x01110000`, 37 and 9 sites hooked; the main menu, HUD, Map and Inventory matched the standalone's captures at 1920x1080 |
| The standalone, final build `603DC45D…` | `Test-ControllerSupport.ps1` (143), `Test-ReinstallOverOlderBuild.ps1` (12), `Test-MovieResolution.ps1` (36), `Test-LargeAddressAware.ps1` (15), `Test-InstalledOverride.ps1` (28) pass; with the first design's module, in game, 37 hooks and no `kmrp-kpm.log`: the applier stood aside |

**Not verified:** KPM's graphical launcher (its command line runs the same
`InstallPatches` and `Launch`, read in `Program.cs`); gameplay on Steam's
executable (only menus and character creation were opened); GOG's own
executable in game (Case 6 of `Test-LargeAddressAware.ps1` installs over one made
from CD 1.03, above); any resolution in game but 1920x1080; the map notes on an area map in
game (their flag is checked in memory both ways); KMRP alone without any add-on in
game (its bytes are the `125DEA64…` KMRP-and-Controller row's); play by hand.

## 8. Limits

- **CD 1.03, GOG and Steam** (GOG since 2026-09-30). *Corrected 2026-09-30:* this
  said "CD 1.03 and Steam only", GOG's `9C10E045…` sharing KPM's address tables
  for many patches but KMRP's bytes not compared with it. They are now: zeroing the
  16 bytes of `Hellspawn Reborn` at FILE `0x000AC0` in CD 1.03 gives GOG's SHA-256
  exactly, so GOG's file is CD 1.03 but for header padding that nothing reads, and
  the data file's runs, which lie inside the sections, never reach it. The installer
  knows GOG's file and its 4 GB-flag form (`01B80825…`, the flag set in that file) by
  hash (`GameExecutable` in `KmrpPatcher.cs`), writes GOG's hash into
  `patch_config.toml`, `kpm_install_state.json` and KPM's backup record, and the four
  `.kpatch` files list it as `kotor1_gog_103`, the static 4 GB hook included.
  `Test-LargeAddressAware.ps1` Case 6 makes GOG's file from CD 1.03 that way and
  installs, flags and restores it; not run on a GOG install, and not in game.
- **Steam needs KPM's proxy deployment.** Steam's executable hands its own start
  to Steam and exits after about half a second, so a patcher KPM injects into the
  process it started never reaches the game Steam starts. KPM 0.7.1 on Windows
  injects unless the player switches to the proxy (`DeploymentPolicy.cs`); the
  README and the installer say so.
- **No large-address flag on Steam.** SteamStub refuses to start an executable
  changed on disk -- "Application load error 3:0000065432", seen 2026-09-28 with
  only the flag set, at the right offset -- and the flag must be in the file when
  the process is created. KMRP has not been seen to need more than 2 GB
  ([large-address-aware.md](../reverse-engineering/large-address-aware.md) calls
  the flag a margin and memory-heavy play an empirical question); on Steam that
  margin is absent.
- **On Steam, KMRP applies after the game has started** (section 4). Every screen
  checked was built after it applied; a change the game reads in its first ~450 ms
  would be missed, and none has been found. Gameplay on Steam has not been played:
  the test install's Steam Cloud save was left alone.
- **No 4 GB patcher can work on Steam's executable, KPM's or KMRP's.** The flag
  is read by Windows from the file's header when the process is created and fixes
  the address space then; nothing running inside the game can set it later. So it
  has to be written into the file, and SteamStub refuses to start a changed file
  (measured, above). KPM's own 4GB Patch lists Steam's executable anyway: in 0.7.1,
  and in KPM's `master` as fetched on 2026-09-29, its K1 hooks file targets
  `34E6D971…` with the editable executable's offset, `0x00400926`, where Steam's
  file holds `00 00` ("Byte mismatch", measured), so KPM refuses it; at the right
  offset the DRM would refuse the file instead. (The older development commit
  `7d53e52` in `build/research/Kotor-Patch-Manager` briefly listed a different
  Steam hash, `C25E2D9C…`, that nothing else in KPM knows; read release facts from
  the 0.7.1 zip.) Stripping SteamStub first, as Steamless does, would make it
  possible, and is kept out of KMRP (section 9). Not reported upstream.
- **The executable changes are invisible to KPM's conflict checks**, which see
  only hook tables: KMRP names its conflicts itself, from measurement. KPM would
  still refuse a patch whose own bytes KMRP changed (its runtime checks every hook's
  bytes), stopping every hook after it.

## 9. Rejected alternatives

- **Putting the sections back at their own addresses** (no relocation at all).
  Appealing because every byte would be gold's. Killed by the measurement in
  section 2: the range is taken before any patch code runs.
- **Rewriting each section's code as C++ detours.** KPM detours restore every
  register but those listed in `exclude_from_restore`, which in practice is EAX:
  most of KMRP's section code works in registers and the FPU stack mid-function, so
  each would need redesigning, and re-testing, from scratch. Moving the proved
  bytes kept them identical to what the standalone ships.
- **KPM `simple` hooks for the unchanged runs, the module for the rest.** It would
  let KPM's checks see those runs, but a failed applier would leave a half-patched
  game with no way back. All or nothing in the module was chosen instead.
- **A second hook table per resolution.** KPM chooses hook files by executable
  hash, not by resolution; the per-resolution values come from the installer that
  already chooses the Override files.
- **Two variants, KMRP with and without its controller** -- the first design,
  built and tested in game on 2026-09-28 and replaced the same day. A player could
  not leave out the movie fixes (to use Movie Patch instead) or the map notes, and
  each further option would have doubled the files. One patch per fix keeps one
  data file.
- **Each optional patch applying its own bytes.** Rejected: the inbound fields need
  the block's address, which only the core's copy knows, and all or nothing across
  three modules has no single place to roll back from. The core reads which patches
  KPM installed instead.
- **Requiring KPM's memory and 4GB patches** -- the four-patch design's first
  version. Rejected once Steam was supported: two of them list no Steam executable,
  the 4GB Patch cannot work on it, and KPM's `requires` cannot differ by game
  version. A requirement list per executable was the maintainer's suggestion; KPM
  0.7.1 has no such thing.
- **A separate "KMRP (Steam)" patch.** It would have kept the requirements on CD
  1.03, but doubled the core patch and made players pick by executable. Carrying the
  fixes needs neither.
- **Reading the unmodified bytes from the player's file.** What the installer did
  until Steam support; Steam's file is encrypted, so the installer carries them.
- **Stripping SteamStub** (what Steamless does) so the standalone could patch Steam's
  executable. That is circumventing DRM, and kept out of KMRP.

## 10. Verifying by hand

For the current source-built installer:

```powershell
python tools\build_windows_engine.py --out build\kmrp\windows-engine.bin
python testing\regression\Test-WindowsEngineSource.py --csc C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
.\build_kmrp.ps1
python testing\regression\Test-KpatchSource.py
python tools\build_kpatch.py --check build\kmrp\kpm-patches
```

On Ubuntu the source regression accepts `--mono-root <extracted Mono tree>`.
The following commands are the **historical snapshot comparison** and require
optional clean/gold fixtures; they are no longer normal build steps:

```powershell
python tools\kpm_relocations.py                       # the table, both methods, the proof
python tools\kpm_originals.py --clean build-inputs\swkotornopatch.exe --delta build\kmrp\gold.kup `
    --relocations build\kmrp\kpm-relocations.txt --sites build\kmrp\kpm-resolution-sites.txt `
    --out build\kmrp\kpm-originals.bin                 # the carried bytes, and their proof
python tools\build_kpatch.py --check build\kmrp\kpm-patches  # "dist\KMRP for KPM", then "dist\KPM patches", until 2026-09-29
python tools\check_kpm_overlaps.py <folder of .kpatch files>
.\testing\regression\Test-KpmEdition.ps1               # the editions agree, per resolution
python tools\kpm_data.py <game>\kmrp-kpm.dat --list    # runs per patch, and the edits
# with a game running under KPM, naming the KMRP patches ticked:
python tools\kpm_data.py <game>\kmrp-kpm.dat --memory --features kmrp,kmrp-movies,kmrp-map-notes
```
