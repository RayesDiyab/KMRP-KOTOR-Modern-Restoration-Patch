# macOS handoff: KMRP as one standalone `.kpatch` with options

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it -- measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: handoff.** Written on Windows on 2026-10-04 for whoever does the Mac side
next. It says what the Windows build became that day, why, and what the Mac build
has to become to match. Nothing in it was built or run on a Mac: every statement
about the Mac is either read from this repository's Mac files and the tracker, and
says so, or is a piece of work still to do.

The tracker, [`macos-changes-from-windows.md`](macos-changes-from-windows.md), keeps
the item-by-item record (items 14, 15 and 16 are this subject). This document is
the one to read first: it puts those three items in order and adds what changed
after they were written.

## 1. What was decided

| When (2026-10-04) | The maintainer | Meaning |
| --- | --- | --- |
| midday | "The final kmrp should be now the standalone kpatch with oprions shipped inside the installer basically" | KMRP is one KPM patch that needs nothing beside it. The installer only delivers it |
| midday | "movie fix should not be an optional thing. That should be standard baked into KMRP, non-negotiable." | the movie fixes are not an option |
| afternoon | "Macos is next to become like the windows version as a one file kpatcher with options" | this handoff |
| evening | "Let's uh, implement it in the way that we have the architecture now with the latest PR." | KMRP follows the option layout of KOTOR Patch Manager's patch-options pull request (section 3) |

## 2. What Windows is now

Measured on Windows only; the record is
[KPM edition, "One patch since 2026-10-04"](kpm-edition.md#one-patch-since-2026-10-04).

| | Windows since 2026-10-04 |
| --- | --- |
| The patch | one file, `KMRP.kpatch`, id `kmrp`, built by `tools/build_native_kpatch.py` |
| What is inside its module | the engine changes, every resolution's menu files (a compressed bank), the controller code and SDL. Nothing is written to `Override`, and there is no data file beside the game |
| Put in KPM's patch folder by hand | it is the whole of KMRP: KPM 0.7.1 installs all 52 hooks and the game runs with controller support and map notes on |
| Resolution | not chosen at install. The game starts at the display's current size and every size the display offers can be chosen in the game, under Options, Graphics. The module lays the menus out again when the size changes |
| Options | three toggles in the manifest: `controller` and `map-notes`, default on, and `debug-logs`, default off. Only `controller` gates hooks (28 of the 52) |
| The installer | writes KPM's own layout into the game folder with that one patch, resolves the options itself, and puts `KMRP.kpatch` into KPM's patch folder |
| Diagnostic logs | written only with `debug-logs` on; errors and warnings always go to `kmrp-kpm.log` |

Where to read it:

| Subject | File |
| --- | --- |
| Building the patch, its manifest and options | `tools/build_native_kpatch.py`, `tools/kpatch_common.py` |
| Building the module | `src/controller-native/build_native_runtime.cmd` |
| The menu files inside the module | `tools/build_native_assets.py`, `src/controller-native/K1RuntimeAssets.cpp` |
| Switching resolution in the game | `src/controller-native/K1RuntimeResolution.cpp`, `K1RuntimeLayout.cpp`, and [the runtime experiment](../reverse-engineering/runtime-resolution-preview.md) |
| Reading the options | `src/controller-native/KmrpOptions.h` |
| The installer's side | `src/patcher/KpmEdition.cs` (`InstallEngine`, `PatchConfigSection`, `WritePatchOptions`) |
| The installer's regression | `testing/regression/Test-InstallerPatch.ps1` |

## 3. How options work (the part that changed last)

Upstream: LaneDibello/Kotor-Patch-Manager pull request 310, open on 2026-10-04 and
not merged. Its format is what KMRP uses on Windows.

| | |
| --- | --- |
| Declaring an option | `[[patch.options]]` in `manifest.toml`: `id`, `name`, `description`, `type = "toggle"`, `default` |
| Tying a hook to an option | `when = "controller"` on the hook. A hook without `when` is always installed |
| Two hooks at one address | KMRP has none, on purpose: KPM 0.7.1 ignores `when` and would refuse the patch with "Hook conflicts detected". A site that differs by option has one hook whose function decides at run time (`CoreGuiFrameK1` runs the controller's frame when the option is on) |
| Where the chosen values are recorded | `configs/<patch id>.ini` in the game folder, section `[Patch Options]`, one key per option id, a toggle as `1` or `0`. For KMRP: `configs/kmrp.ini` |
| Who writes that section | whoever installs the patch: a KPM with patch options on Apply, or KMRP's installer. Only that section; the rest of the file is the patch's own and is kept |
| On uninstall | the section is taken out; a file with nothing else in it is deleted, and the folder once it is empty |
| How the module reads it | per key, with the option's default when the file, the section or the key is missing. So KPM 0.7.1, which writes no file, gives the defaults |
| `patch_config.toml` | holds no options. (For a few hours on 2026-10-04 KMRP wrote a `[patches.options]` table there; tracker item 15 was written then and is corrected by item 16) |
| A KPM without options (0.7.1) | installs every hook and writes no file: controller support and map notes on, logs off |

## 4. What the Mac is today

Read from the tracker's item 6 and `macos/README.md` on 2026-10-04, not measured again.

| | Mac |
| --- | --- |
| The patch | already one KPM patch, `kmrp`, built by `macos/tools/make_kmrp_patch.py` from FTD's widescreen patch, Stray Bug Fixes and KMRP's own code |
| What is not inside it | the menu layouts: the installer adds them |
| Resolution | chosen at install |
| Options | `--no-controller` and `--no-map-notes` at install, as separate config variants, not as manifest options |
| KPM | installed in KPM's layout beside `KOTOR_Exe` (`KotorPatcher.dylib`, `patch_config.toml`, `patches/`) |

So the Mac is closer than Windows was: it has one patch already. What it lacks is the
patch being whole without the installer, the resolution chosen in the game, and the
options in KPM's format.

## 5. What the Mac needs

Each line is work, none of it started. The order is the order of dependency.

| # | Work | What Windows did | Unknown on the Mac |
| --- | --- | --- | --- |
| 1 | The menu layouts inside `kmrp.dylib`, so the `.kpatch` alone is the whole of KMRP | a compressed bank of every set's files in the module; the current size is unpacked to a private cache the game's resource manager reads. The blending is the Mac's own C tools compiled into the Windows module (`macos/tools/kmrp-guiblend.c`, `kmrp-abilityicons.c`, `kmrp-gameart.c`, with a `KMRP_EMBEDDED` entry point) | how the Mac build's resource manager can be pointed at a cache folder; where a sandbox lets the dylib write |
| 2 | The resolution chosen in the game, the layouts applied again on a switch | fonts' glyph metrics read again, the new size's files in place before the window is re-created, each control's file extent tracked so panels do not drift | every address: the Mac engine is a different binary. Whether the Mac game re-creates its window on a switch at all |
| 3 | The three options in the manifest, `when = "controller"` on the controller's hooks, no two hooks at one address | `OPTIONS` and `option_hooks()` in `tools/build_native_kpatch.py` | which Mac hooks belong to the controller |
| 4 | The dylib reading `configs/kmrp.ini`, with defaults when it is missing | `KmrpOptions.h`, with Windows' `GetPrivateProfileIntW` | where "beside the game" is inside the app bundle, and whether KPM's macOS build writes the folder there. A small INI reader is needed: the Windows call does not exist |
| 5 | The dylib's logs behind `debug-logs` | every diagnostic log gated; errors and warnings always written | which files the Mac dylib writes today |
| 6 | The installer writing the hooks of the options left on and the `[Patch Options]` section, in place of its config variants; its uninstall taking the section out | `KpmEdition.cs`; restore removes the section and keeps anything else in the file | `kmrp-mac.sh` and the installer app are the Mac's own |
| 7 | The movie fixes always in | not an option on Windows | whether the Mac has an equivalent at all |
| 8 | Conflicts with FTD's two patches | tracker item 14: the generic conflict refusal, decided | unchanged by this handoff |

What does not carry over:

- **Addresses and hook sites.** All of them are for the Windows 1.03 executable.
- **The display-mode work.** Windows adds sizes to what `EnumDisplaySettingsA` reports
  and answers `ChangeDisplaySettingsA` itself; the Mac has neither call.
- **The NVIDIA present-method step** and the 4 GB flag: Windows only.
- **The resolution checklist** in the Windows installer (three sections: this display,
  fits this display, larger than this display) is installer UI. Whether the Mac
  installer wants the same list is the maintainer's call; the Mac's own installer
  already has a custom size.

## 6. How to check it on a Mac

| Check | Expected |
| --- | --- |
| `kmrp.kpatch` put in KPM's patch folder by hand, no installer run, KPM without options | the whole of KMRP, controller support and map notes on, no diagnostic log |
| No `configs` folder | the same: defaults |
| `[Patch Options]` with `controller=0` in `configs/kmrp.ini`, installed by the installer | only the hooks without `when` in `patch_config.toml`; the game runs without the controller code |
| `debug-logs=1` | the logs appear |
| A section of another name already in `configs/kmrp.ini` | still there after install and after uninstall |
| A resolution switch in the game | fonts and panel positions hold |
| Upstream's `tools/validate-patches.py` from pull request 310 on the Mac patch | no error |

## 7. Open questions for the maintainer

1. Pull request 310 is not merged. If its format changes in review (the folder name
   `configs`, the section name `[Patch Options]`), both platforms follow. Windows
   reads the names in one place, `KmrpOptions.h`, and writes them in one,
   `KpmEdition.cs`.
2. Whether the Mac installer should offer the Windows resolution checklist.
3. Whether a Mac `debug-logs` option should also gate what `kmrp-mac.sh` logs, or only
   the dylib.
