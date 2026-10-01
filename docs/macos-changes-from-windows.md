# macOS: changes the Windows build made first

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it -- measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: tracker.** The other direction of
[`windows-changes-from-macos.md`](windows-changes-from-macos.md): what was changed on Windows,
or in shared code from Windows, that the Mac build does not have yet or has not yet built and
checked. Each item says what changed, where, what the Mac needs, and how to check it.
[`macos/WINDOWS-PARITY.md`](../macos/WINDOWS-PARITY.md) stays the table of every Windows
change and its state on the Mac. Started 2026-09-30, at the maintainer's request: "any changes
macos needs should be documented in another file as well".

**Where these come from.** The merge of pull request #23 into `master` on 2026-09-30 and the
Windows work after it on the same day: any resolution on Windows, the game version named in
the patcher's second step, GOG's executable, and the badge fix below. Everything was built and
tested on Windows only (LLVM clang 18.1.8 for the helper, as one x64 program through
`testing/regression/native_helpers.py`). No Mac build had been made from it. Items 9 and 10
come from merging the macos branch again the same evening (`e28a131`, `dc11efc`, `d672b8d`:
the journal's rows, the Options check boxes, lists as tall as whole rows and skill rows at
`50s`), where both branches had changed the same code.

States: **build and check** (shared code already changed; the Mac gets it with a build from
`master` and needs the checks named), **to do** (the Mac has nothing yet), **n/a** (with the
reason).

| # | Change | State |
| --- | --- | --- |
| 1 | Controller badges drawn again for the blended buttons at a size with no set | **build and check** |
| 2 | The HUD's button-row boxes (`lbl_mileftbot.tga`) drawn from the blended HUD | **build and check** |
| 3 | `kmrp-mac.sh` installs every file the helper writes, not only the `.gui` files | **build and check** |
| 4 | The installer window's second step names the game version it finds | **to do** |
| 5 | Wording that says a blended size takes the nearest set's "fonts and art" | **to do** |
| 6 | KOTOR Patch Manager recognises KMRP's install by itself, and KMRP installs for KPM when KPM manages the game | **done** (built and checked on a Mac 2026-10-01 with KPM 0.7.1's window; four fixes, see the section) |
| 7 | GOG's executable | **n/a**: the Mac build is Aspyr's Steam build only |
| 8 | Step 1 finds Steam's KOTOR by itself | **n/a**: the Mac did it first (`find_game`); Windows follows it since 2026-09-30 |
| 9 | `gui-blend.bin` version 4: the row fits and the badges in one table; the helper's manifest carries this blend's row fits | **build and check** |
| 10 | The skill picture inside its frame grows with the `50s` row | **build and check** |
| 11 | The Feedback list's rows grow with the resolution, so the `25s` circles fit | **build and check** |
| 12 | Every font atlas at its set's own scale: check the Mac's cache | **check** |

## 1. Badges drawn for the blended buttons

**What was wrong, on both platforms.** A controller badge is a 512x64 texture the engine
stretches over its whole button, drawn so that it comes out round on that button
(`tools/build_controller_prompt_textures.py`, `build_prompt_tga`). For a size with no set, both
installers took the badges of the nearest set (by height, then shape), drawn for that set's
buttons, and the blended buttons have other shapes. Measured on the blended files, the worst
badge on each size, as drawn width over drawn height (1.0 is round):

| Size | Nearest set | Worst badge | Stretch |
| --- | --- | --- | --- |
| 3440x1400 | 1856x1392 | `optresolution.gui` BTN_OK, 336x64 drawn for, 624x64 shown on | 1.857 |
| 3200x1350 | 1856x1392 | `map.gui` BTN_RETURN, 806x38 for, 1401x36 on | 1.835 |
| 2560x1200 | 1920x1200 | `map.gui` BTN_RETURN, 834x33 for, 1112x32 on | 1.375 |
| 1600x1000 | 1512x982 | `optionsingame.gui` BTN_LOADGAME, 567x72 for, 600x73 on | 1.044 |
| 3000x2000 | 3024x1964 | `optresolution.gui` BTN_CANCEL, 572x90 for, 567x92 on | 0.970 |
| 2400x1080 | 2560x1080 | `custpnl.gui` BTN_BACK, 460x63 for, 431x63 on | 0.937 |

The maintainer confirmed it needs fixing on both platforms (2026-09-30).

**What changed** (shared code, written on Windows). `gui-blend.bin` was version 3 on `master`
(version 4 since the macos branch's row fits were merged in the same day; item 9): after the
layout records it carries `build_prompt_tga`'s constants, the 16 glyph artworks the badges use
(A, B, X and Y in the four families, as `_load_glyph_art` loads them, RGBA) and, for each of
the 552 rows of the prompt manifest, where its button's extent sits in its `.gui`, its glyph,
its backing and the controls whose least height sizes it (`tools/build_gui_blend_table.py`,
`badge_section`). `macos/tools/kmrp-guiblend.c` draws every badge again for its blended
button, with Pillow 12's arithmetic -- the Lanczos resample on premultiplied alpha in 22-bit
fixed point, the masked paste, `alpha_composite` -- and the label width of SETDIR's manifest,
and writes that manifest with the blended button sizes and the Container's widening. The
Windows installer's `src/patcher/GuiBlend.cs` does the same, byte for byte. Its arguments and
exit codes are unchanged; it writes 637 files where it wrote 83 (the menus, the 552 badges,
the manifest and item 2's texture). The table grew from 3.2 MB to 3.7 MB (0.8 MB gzipped).

**Measured on Windows**, before any Mac build:
- a plain-Python model of that arithmetic reproduced Pillow's `resize` exactly in 60 of 60
  random cases and `build_prompt_tga` exactly in 40 of 40 (with and without a label, a group
  size and the `dialog2` backing);
- the helper, rebuilding the anchors 1920x1080, 1280x720 and 2560x1600 from the table with
  their own fonts, wrote each set's 637 files byte for byte as the build made them;
- the helper and the Windows installer agreed on every file at 3440x1400 and 2560x1200;
- `Test-GuiBlendHelper.py` on Windows, final: the helper equals the Python derivation, which
  draws each badge with the build's own `build_prompt_tga` and the HUD boxes with
  `build_menubg_texture`, at 24 sizes; all 45 anchors rebuilt from the table are the build's
  sets byte for byte, badges, manifest and HUD boxes included; every badge at the 24 sizes is
  round on its blended button (worst 1.049 wide for tall, texel rounding); and the Windows
  installer equals the helper at 369 sizes, 300 of them random, and refuses the same 7;
- in play on Windows at 1600x1024: the main menu, character generation and Load Game badges
  round and beside their words, the HUD's eight boxes under the eight buttons.

**What the Mac needs.** A package built from `master` (`macos/build.sh` packs the table with
`build_gui_blend_table.py` and compiles the helper), then:
- `testing/regression/Test-GuiBlendHelper.py` on the Mac. Its check 3 (every anchor rebuilt
  from the table equals the build's set, badges included) is the one that matters there: the
  Lanczos weights come from `sin()`, the Mac's resources are made by Pillow with Apple's libm
  and the helper links the same libm, so the check proves the two agree on the Mac as they do
  on Windows. Not yet run on a Mac. Both slices should be compared, as the icon tests do
  (`native_helpers.build` builds both on macOS; this test still builds the host's only);
- `testing/regression/Test-MacInstaller.py`, whose blended case now expects every file the
  helper writes;
- in play, a blended size with a pad: the main menu's A, Options' B, the map's X on Return
  To Ebon Hawk -- each round, each beside its words.

## 2. The HUD's button-row boxes

`lbl_mileftbot.tga` is the black boxes behind the HUD's eight top-right buttons, drawn per set
from that set's `mipc28x6.gui` (`tools/build_menubg_texture.py`), the HUD every size but
3440x1440 loads; the Mac loads the same one (`macos/WINDOWS-PARITY.md`, *Resolution and
recentring*). From the nearest set its boxes follow that set's buttons, not the blended ones.
The table now carries where LBL_MENUBG and the eight buttons sit (`hud_section`), and the
helper draws the texture from the blended HUD with `build_menubg_texture.build_tga`'s
arithmetic. The same anchors check covers it (it is one of the 637 files). **Check** in play
at a blended size: the boxes sit under the eight buttons, the gaps between them clear.

## 3. `kmrp-mac.sh` takes every file the helper writes

It copied `"$WORK/blend"/*.gui` over the extracted set; it now copies every file there
(`*(N.)`), so the badges, the manifest and item 2's texture replace the set's too. Written on
Windows and not run: `Test-MacInstaller.py` is the check.

## 4. The second step names the game version

The Windows patcher's second step was "Verify Editable EXE", with "Get Editable EXE" and
"Check Again" when the file was another. Since 2026-09-30 it is "Detect Game Version": it
names what it finds -- the Steam version, the GOG version or the editable 1.03 swkotor.exe --
in its state label and subtitle, and says which file it could not use otherwise. The Mac
window's step is "2. Verify Game", "Checking for the Steam version of KOTOR."
(`macos/installer-app/main.m`). **What the Mac needs**, for the two windows to read alike:
"2. Detect Game Version" and "2. Detected Game Version", the subtitle "The Steam version of
KOTOR detected.", and "Steam" beside the badge where Windows shows the version.

## 5. "Fonts and art of the nearest set"

With items 1 and 2 a blended size takes only its fonts from the nearest set: every other file
that depends on the size is made for it. `kmrp-mac.sh` still says "fonts and art from $from"
(its summary and the `menu_set=` line of `status`), and `macos/README.md`'s section 10 describes
the 1352x878 test of 2026-09-29 that way, correctly for that day. The Mac README's *Other sizes*
paragraph and `WINDOWS-PARITY.md` were corrected with the change. **To do**: the script's two
messages, if the app shows them.

## 6. KOTOR Patch Manager recognises the install by itself

**What the Mac did instead** (pull request #24, `45b7457`, merged into `master` on
2026-10-01). KMRP on the Mac is one KPM patch, `kmrp`, built with KPM's own tools from FTD's
widescreen patch and Stray Bug Fixes and KMRP's layout, map-note and controller code
(`macos/tools/make_kmrp_patch.py`), each of its four builds checked and staged by KPM's own
`KPatchCore`, and installed in KPM's layout beside `KOTOR_Exe` (`KotorPatcher.dylib`,
`patch_config.toml`, `patches/`). An install of FTD's patches made through KPM is replaced,
with FTD's agreement: the untouched game is put back from KPM's copy, his files and KPM's
leftovers deleted, and KMRP installed; any other KPM patch stops the install, by name, with
nothing changed (`kmrp-mac.sh`, `kpm_check` and `kpm_remove`). So the second half of this item
is settled differently: the Mac does not install *for* KPM, it takes over FTD's install, which
its own patch contains. The first half is not: read from `kmrp-mac.sh` on 2026-10-01, the Mac
writes no `kpm_install_state.json`, no KPM-format backup of `KOTOR_Exe` and delivers no patch
to KPM's patch folder, so KPM for macOS would not yet recognise KMRP's install as its own the
way it does on Windows (the table below). Whether that is wanted now that KMRP carries FTD's
patches is the maintainer's call; not tested with KPM's window on a Mac.

**Written, 2026-10-01** (the maintainer: "It should do the same with kpm as windows", and of
FTD's install, "that should still work"). `macos/kmrp-mac.sh`, from Windows' `KpmEdition.cs`,
with KPM's Mac values read from the submodule's KPatchCore (`2a784bf`):

| Windows | Mac |
| --- | --- |
| `KpmState`: `kpm_install_state.json`, `LibraryProxyInstalled` true | `write_kpm_state`: the same file beside `KOTOR_Exe`, Platform 1, Distribution 1, "1 1.4.0 (Aspyr macOS)", Architecture 1, Title 1, the `BuildIdentity`, `LinkedDependencyInstalled` true |
| `WriteKpmBackup`: `swkotor.exe.backup.<time>` and `.json` | `write_kpm_backup`: `KOTOR_Exe.backup.<time>` and `.json`, before the load command |
| `DeliverKpatches`: the four `.kpatch` files into KPM's patch folder from `%APPDATA%\KPatchLauncher\settings.json`, or a "KPM patches" folder for an install for KPM | `deliver_kpatch`: the installed build's `kmrp.kpatch` (now in the package, `build.sh`; its manifest declares a conflict with FTD's two patches, `make_kmrp_patch.py`) into the folder `PatchesPath` names in `~/.config/KPatchLauncher/settings.json` or `~/Library/Application Support/KPatchLauncher/settings.json`, or "KPM patches" beside the game for an install for KPM |
| `ForeignRuntimeFile`: KPM's runtime present, install for KPM | `kpm_check` returning 2: KPM's files present with patches that are not FTD's, install for KPM; FTD's two alone are still replaced (return 0), as pull request #24 made it |
| `Restore`, `ConfigChangedSinceInstall`: runtime left once KPM rewrote `patch_config.toml` (`RuntimeChangedSinceInstall`, any runtime file, since 2026-10-01 from the Mac) | `handed_over` in `restore_from_manifest`: the same, `is_runtime_path` naming what stays |

The app accepts the new case (`forKpm`, "KotOR Patch Manager manages this game. KMRP is
installed for it."). Checked on Windows only: `zsh -n` on the script, and its KPM functions run
against a stand-in game under WSL's zsh 5.9 (the state file and backup as valid JSON with KPM's
values, delivery to KPM's folder and not over another's file, the fallback beside the game,
`kpm_check`'s three answers, and uninstall before and after a takeover: 18 checks).
`Test-MacInstaller.py` is extended (every round checks KPM's records and `kmrp.kpatch`; round 5
installs for KPM beside another patch; round 6 is the takeover) but needs a Mac. **Check on
a Mac**: `build.sh`, `Test-MacInstaller.py`, which .NET folder KPM's settings are really in,
then KPM's own window over an install as the **Check** below says.

**Built and checked on a Mac, 2026-10-01.** `build.sh` and `Test-MacInstaller.py` pass (0
problems). KPM's settings are in `~/Library/Application Support/KPatchLauncher/settings.json`
(KPM 0.7.1, .NET 8). With KPM 0.7.1's own window: KMRP delivered `kmrp.kpatch` to the folder
named there, KPM listed it ticked over KMRP's install, and Apply, then a launch from KPM and
one from Steam, ran the game. Four fixes came out of it (`CHANGELOG.md`, *KotOR Patch
Manager's own window over KMRP*): the movie hook's parameter source, which 0.7.1 refused; SDL
beside the game, which KPM's Apply had deleted from `patches/`; a takeover found from any
runtime file, since KPM writes `patch_config.toml` as KMRP does; and uninstall removing KPM's
runtime too when KMRP is its only patch. The last two are for Windows as well
([`windows-changes-from-macos.md`](windows-changes-from-macos.md), item 16).

Asked for by the maintainer on 2026-09-30 ("how on windows it gets detected automatically by
kpm, this needs to happen as well on macos"), as the next step after the merge. Nothing is
written for the Mac yet. This is what Windows does, what KPM does on the Mac, and what the
Mac installer needs, read from KPM's source (the submodule, FTD's branch at `71ac5fa`; not
yet compared with KPM's own `master`) and from `src/patcher/KpmEdition.cs`.

**How Windows does it** (`KpmEditionOperations`, [`kpm-edition.md`](kpm-edition.md)):

| What | Where | Why KPM needs it |
| --- | --- | --- |
| KPM's own runtime, laid out as KPM's proxy deployment lays it out: `binkw32.dll` (the proxy), the game's renamed `binkw32Hooked.dll`, `KotorPatcher.dll`, `patch_config.toml` with `target_version_sha`, `patches\<id>.dll` | beside `swkotor.exe` (`InstallEngine`) | KPM sees its own install, not a stranger's files |
| `kpm_install_state.json`, KPM's `ManagedInstallState` (schema 1): the unmodified executable's hash, size and version, the installed patch ids, `LibraryProxyInstalled: true` | beside `swkotor.exe` (`KpmState`) | KPM knows a game by its executable's hash; where KMRP changed the executable, KPM's `GameDetector.DetectVersionFromManagedInstallState` identifies it from this file. KPM after 0.7.1 also keeps the deployment it records on Apply and Launch (LaneDibello/Kotor-Patch-Manager#283) |
| A backup of the unmodified executable in KPM's format, `swkotor.exe.backup.<yyyyMMdd_HHmmss>` and `<that>.json` (`BackupInfo`: path, hash, size, time), made before the one change to the executable | beside `swkotor.exe` (`WriteKpmBackup`) | KPM's Apply starts by restoring the newest backup (`PatchRemover.RemoveAllPatches`), so it applies from the unmodified file |
| KMRP's `.kpatch` files | KPM's patch folder, from `PatchesPath` in `%APPDATA%\KPatchLauncher\settings.json` (`DeliverKpatches`) | KPM lists KMRP's patches without the player copying anything |
| Installing for KPM when KPM already manages the game: a KPM runtime file the manifest does not record (`ForeignRuntimeFile`) makes it install the interface, the INI and the data file only | `Install` | the player ticks KMRP in KPM; nothing of KPM's is replaced |
| On restore, leaving the runtime to KPM once KPM's Apply has rewritten `patch_config.toml` (`ConfigChangedSinceInstall`; since 2026-10-01 any runtime file, and the whole runtime removed when KMRP is KPM's only patch) | `Restore` | removing it would break KPM's install |

**What the Mac installer does today** (`macos/kmrp-mac.sh`): KotorPatcher.dylib, `patches/`
and `patch_config.toml` (written by KPM's own KPatchCore at build time) beside `KOTOR_Exe` in
`Contents/MacOS`, the dylib added to `KOTOR_Exe`'s load commands (`kmrp-macho add-dylib`) and
the file re-signed ad hoc; its backup of `KOTOR_Exe` and its manifest in its own state folder,
outside the game. It refuses a game that has KPM's files in it.

**What KPM does on the Mac** (the submodule's KPatchCore):
- A macOS game is always deployed as a linked dependency (`DeploymentPolicy.ForGame`):
  `PatchApplicator` adds `KotorPatcher.dylib` to the executable's dependency list after the
  static hooks (`ExecutableDependencies`) and re-signs it ad hoc (`MachOSigning`), and
  `InstallStateManager.SaveOrUpdate` records `linkedDependencyInstalled: true`. That is what
  KMRP's installer already does, so the two lay the game out alike.
- KPM knows the game as KOTOR 1 "1 1.4.0 (Aspyr macOS)": `KOTOR_Exe`, SHA-256 `C1FCB8D3…`,
  6,333,424 bytes (`0x60A3F0`), `Platform.macOS`, `Distribution.Steam`,
  `Architecture.x86_64`, build identity `macho:05EFCB7E4FCB3536B278E10F812BB06C`
  (`GameDetector.cs`). Once KMRP has added its load command the hash is no longer that one;
  KPM then reads `kpm_install_state.json` from the executable's folder, and failing that
  infers the build from the Mach-O identity, which it marks as not matching byte for byte.
- Its state file and backups live in the executable's folder, `Contents/MacOS`
  (`InstallStateManager.GetStatePath`, `BackupManager`).

**What the Mac needs**, for KPM to recognise KMRP's install as Windows' is recognised:
1. Write `Contents/MacOS/kpm_install_state.json` as `KpmState` writes it, with the Mac's
   values: `GameExeFileName` `KOTOR_Exe`; `OriginalHash` `C1FCB8D3…` and `OriginalFileSize`
   6333424; `OriginalVersion` with `Platform` 1 (macOS), `Distribution` 1 (Steam), `Version`
   "1 1.4.0 (Aspyr macOS)", `Architecture` 1 (x86_64), `Title` 1 (KOTOR1), the same size and
   hash; the installed patch ids; `LibraryProxyInstalled` false and `LinkedDependencyInstalled`
   true. Record it in the manifest and remove it on uninstall while it is as written.
2. Before `add-dylib`, leave the unmodified `KOTOR_Exe` beside it in KPM's format,
   `KOTOR_Exe.backup.<yyyyMMdd_HHmmss>` with its `.json`, as `WriteKpmBackup` does, so that
   KPM's Apply restores it and applies from the unmodified file. The installer's own backup
   in its state folder stays what its uninstall uses.
3. Build KMRP's Mac patches as `.kpatch` files -- `kmrp-layout`, `kmrp-controller`,
   `kmrp-map-notes`; the widescreen patch is FTD's own KPM patch -- and put them in KPM's patch
   folder from `PatchesPath` in KPM's settings. KPM finds that file at
   `Environment.SpecialFolder.ApplicationData/KPatchLauncher/settings.json`
   (`AppSettings.cs`). Which folder .NET gives for that on macOS was not checked here (on
   Unix it has been `~/.config`); **to check on a Mac** before relying on it.
4. Where KPM's files are already in `Contents/MacOS` and the manifest does not record them,
   install for KPM instead of refusing: the menu set, fonts, art and INI, no runtime and no
   load command, and the `.kpatch` files where KPM finds them. KPM's files decide this by
   themselves, with no option: Windows had an Advanced Settings option for it from 2026-09-29
   and removed it on 2026-09-30 (the maintainer: "the kpm option in advanced settings is
   redundant now"), because its own install is one KPM recognises and takes over, so the
   option only decided who installed the runtime first. The Mac should not add one.
5. On uninstall, leave KPM's runtime, the load command and the state file to KPM once KPM
   has taken the install over (its Apply rewrote `patch_config.toml`), as `Restore` does.

**Check.** With KPM for macOS open on a game KMRP installed: KPM names the game "1 1.4.0
(Aspyr macOS)" rather than unknown or inferred, lists KMRP's patches, and after Apply the
game starts from Steam with KMRP applied; KPM's Uninstall All leaves the unmodified
`KOTOR_Exe` (hash `C1FCB8D3…`). And the other way: with KPM's patches installed first, KMRP's
installer installs for KPM without touching KPM's files.

## 7. GOG's executable (Windows only)

The Windows installer accepts GOG's own `swkotor.exe` since 2026-09-30: it is the editable
1.03 build with the 16 bytes of `Hellspawn Reborn` at FILE `0x000AC0` zeroed, which gives GOG's
SHA-256 `9C10E045…` exactly. KMRP's `.kpatch` files list it (`kotor1_gog_103`). The Mac build
is Aspyr's Steam port, so there is nothing to port.

## 8. Finding the game (the Mac did it first)

The Windows patcher's first step started at `swkotor.exe` beside it and otherwise asked for
Browse. Since 2026-09-30 it also looks where Steam installed KOTOR -- Steam's record of app
32370, then every library in `steamapps\libraryfolders.vdf`, at `steamapps\common\swkotor`,
as `kmrp-mac.sh`'s `find_game` looks -- and then at GOG's registry entry (`GameFolders` in
`src/patcher/KmrpPatcher.cs`). Nothing for the Mac to do.

## 9. One blend table for both branches' additions

Both branches made `gui-blend.bin` version 3 on 2026-09-30, in two formats: `master` added the
badges and the HUD's boxes after the layout records (items 1 and 2), the macos branch the row
fits there (`fit_list_to_rows`, `docs/windows-changes-from-macos.md`, item 14). The merge the
same evening makes it version 4 and carries both, in this order: the fits, the layouts, the
row fits, the badges, the HUD, the files (`tools/build_gui_blend_table.py`'s docstring). The
helper refuses both version 3 tables. It applies the row fits before the Container's widening,
as the build does, and since the merge it also writes each `fitted` line of the manifest with
this blend's change, as it writes the `widened` line, so a set the blend resolves to itself
still comes out byte for byte. `src/patcher/GuiBlend.cs` does the same (`FitRows`).
**Check** on the Mac: `Test-GuiBlendHelper.py` (both slices; the Windows-only check 6 skips)
and `Test-MacInstaller.py`, with resources built from `master`.

## 10. The skill picture and the `50s` row

`master` put the skill picture inside its frame on 2026-09-29: a canvas of `round(32s)` with
the picture `round(0.62 × 42s)` in it, moved `(round(−0.5s), round(−2s))`, measured in play at
3440x1440 with the box at 84. The macos branch moved the skill rows to `50s` and the canvas to
`round(32s x 50 / 42)` the next day, without the picture. Merged, the picture is `round(0.62 ×
50s)` and its move grows by `50 / 42` too, since the frame (`lbl_hex_3`, 64x64, outline x
7..55, y 6..59) is stretched over the box: `AbilityIconGenerator.cs` and
`macos/tools/kmrp-abilityicons.c` alike, with `Test-AbilityIcons.py` and `Test-MacInstaller.py`
checking the rule. At 1512x982 that is a 52 px canvas with a 42 px picture at (4, 2); at
3024x1964 the 64 px cap, filled. **Check** on the Mac: `Test-AbilityIcons.py` (both slices),
then the Skills tab at 1512x982 and 3024x1964, each picture inside its hex. Not yet seen in
play on either platform at the new sizes.

## 11. The Feedback list's rows

Seen on Windows at 3440x1440 once the check boxes scaled (`docs/windows-changes-from-macos.md`,
item 13): the Feedback list's circles overlapped, 50 px circles 44 px apart. Its rows are
check boxes built at the height of `LB_OPTIONS`'s row template, 43 in every set, which the
row scale does not reach, so they stayed 43 px at every size. The same holds on the Mac: 68-px
circles in 43-px rows at 3024x1964. The resource build now scales the template, `round(43s)`
(`tools/scale_listbox_padding.py`, `FEEDBACK_LIST`), 117 px at 3024x1964; nothing changes in
the layout patch. Ten rows fit the list at every scaled size. **Check** on the Mac, with
resources built from `master`: Options, Feedback at 3024x1964, nine circles apart and each
beside its label.

## 12. Font atlases at the Mac sizes' own scales

The Windows build machine's cache of fonts baked per scale (`build/fonts`, git-ignored, made
by `tools/build_font_scale_sets.py`) had no set for 16 of the 17 Mac sizes' scales, so from
2026-09-29 to 2026-09-30 the Windows builds' Mac sets used the shared 3.0 bake, resampled
(`Test-FontAtlasScale.py` failed on those 16; the baker was run and they pass). The Mac's
packages come from the Mac's own build, whose cache this repository cannot see. **Check**:
`Test-FontAtlasScale.py` on the Mac's resources; it names any set drawn resampled.
