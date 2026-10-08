# Handoff to the Mac side, 2026-10-09

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It says what was built
> and seen on Windows, and marks what is a guess about the Mac as a guess.

What changed on Windows from 2026-10-07 to 2026-10-09, after
[macos-two-patches-handoff.md](macos-two-patches-handoff.md), and what each change
asks of the macOS build. Written on Windows. **Nothing in it was run on a Mac**, and
the Mac's own documents were not edited: the tracker
([macos-changes-from-windows.md](macos-changes-from-windows.md)) has no rows for
these yet, so take the items below as the list. Windows state: `master` at the commit
that adds this file.

Each item says what it is, where the code is, and one of:

- **port**: shared behaviour the Mac build should have too;
- **decide**: the Mac has its own way of doing this, and whether to follow is its call;
- **Windows only**: nothing to do, listed so that nobody wonders.

## Summary

| # | Change | For the Mac |
| --- | --- | --- |
| 1 | The area map keeps the first size's surfaces after a change of resolution in the game | **port**, if the Mac build changes size in the game |
| 2 | Two Character screen buttons wider after a change of size and back (controller patch) | **check**: only if the Mac's controller patch grows buttons for badges |
| 3 | The Xbox-style HUD is on by default | **decide**: the Mac has no Xbox-style HUD that I can find |
| 4 | HD item icons are an option, on by default | **decide** |
| 5 | High FPS Fixes (D3M0) as a third patch, on by itself above 60 Hz | **decide**; the patch itself has no Mac build |
| 6 | Frame rates through the game's own resolution list | **decide**; the mechanism is Windows' |
| 7 | No resolution choice in the installer (2026-10-07) | already the tracker's item 30 |
| 8 | Advanced Settings: six tiles, new order, "Native Controller Support by RaymanGT" | **decide** (wording and order) |
| 9 | Documents: a features list for players, a technical one, the index regrouped | read; nothing to build |
| 10 | Bundled work checked for newer versions | read |
| 11 | Windows-only items | nothing |

## 1. The area map after a change of resolution

**Seen on Windows** by the maintainer: started at 3440x1440, changed to 1920x1080 in
Options, opened the map. The frame was the new size's; the picture and its grid were
the old size's and ran out of the frame.

**Cause.** `CSWGuiInGameMap`'s constructor sizes two things no layout file holds: the
picture's canvas (a `CSWGuiImage` inside the panel) and the markers' and fog's overlay
(the `CSWGuiMapHider`). The panel is constructed once, with the game. On a change of
size the game makes the HUD, the dialogue and the message box again
(`CGuiInGame::ResetInterfaceForSize`) and nothing else. The Windows module wrote the
recipe's four operands for the new size, but nothing ran them again.

**Repair on Windows.** `KmrpRuntimeLayoutDimensions` in
`src/controller-native/K1RuntimeLayout.cpp`: for a live panel with
`CSWGuiInGameMap`'s vtable, `SetExtent` on the canvas and the overlay with the new
size's rectangles (canvas `round(width / 2 * 512 / 440)` by `height / 2`, overlay
`width / 2` by `height / 2`), and the overlay's two pictures (arrow and selection
circle) at the marker rule's 32 and 16. The HUD's own instance, for the minimap, is
recognised by the game's 512x256 and 440x256 and left alone. **Not seen in the game
with the repair.**

**For the Mac.** `macos/patches/kmrp-assets/layout.cpp`, on the branch
`macos-standalone-kpatch` (it is not on `master`), is where the Mac lays live panels
out again, and it has the same kind of code as the Windows file (the list rows came
from there). If the Mac build lets the player change size in the game, it
has this fault for the same reason, with the Mac executable's own offsets: the
Windows ones are the panel's `+0x1080` (canvas) and `+0xE38` (overlay), and the
overlay's `+0x60` and `+0x64`. **I do not know the Mac's offsets or its vtable.**

The whole path, every per-size operand and whether it is read on each draw or only at
construction, is in
[`reverse-engineering/resolution-switch.md`](../reverse-engineering/resolution-switch.md).
Its section 6 is the list to hold the Mac's sites against: an operand read only at
construction is where the next fault of this kind will be. One is already known and
was the Mac's own find: the abilities' chart (repaired on the Mac on 2026-10-05,
**still not ported to Windows**).

## 2. Buttons wider after a change of size and back

**Seen on Windows** by the maintainer after 3440x1440 to 1920x1080 and back: "some
buttons were slightly stretched horizontally". **Which buttons is not established.**

**Cause, read from the source.** The controller patch grows the Character screen's
Level Up and Auto Level Up buttons to hold their badges (`ShowK1BackedBadge`) and
left them grown while another screen was in front. A change of size lays every live
control out from where it stands, so the grown rectangles were laid out as if they
were the screen's own.

**Repair.** `RestoreK1GrownButtons` in
`src/controller-native/vendor/K1XboxControls.cpp`, called every frame from
`UpdateK1ControllerPrompts`: a grown button is its screen's size again whenever
another screen is in front. **Not seen in the game.**

**For the Mac.** The Mac's controller patch has sources of its own
(`macos/patches/kmrp-controller`: `prompts.cpp`, `cues.cpp`, `hud.cpp`), not this
file, and I found nothing there that grows a button for a badge (searched `master`
and the branch for the Windows names). If the Mac does change a control's
rectangle for its prompts and leaves it changed while the screen is closed, it has
the same fault after a change of size; otherwise there is nothing to do.

## 3. The Xbox-style HUD is on by default

Since 2026-10-08. It is shown only while the pad is in use, as before. Changed: the
module's fallback when `kmrp-controller.ini` has no `Style` under `[Hud]` (`Enabled`
in `K1XboxHud.cpp`: `Xbox`, was `PC`), the settings file the module writes
(`K1ControllerStandalone.cpp`), the one the Windows installer writes, and the
`xbox-hud` option's default in the patch's manifest (`tools/build_controller_kpatch.py`).
A settings file already beside the game keeps what it says.

**For the Mac: decide.** I found no Xbox-style HUD in the Mac's controller patch
(`K1XboxHud.cpp` is a Windows source, and neither `master` nor the branch has a Mac
counterpart by that name), so there is no default to change until there is one.
**Not seen in the game with the new default** on Windows either.

## 4. HD item icons are an option

Since 2026-10-08, after a player asked why the icon pack was mandatory. KMRP's patch
has a third option, `hd-icons`, on by default (`tools/build_native_kpatch.py`); the
Windows installer writes it into `configs\kmrp.ini`. With it off the module does not
unpack the pack's files and the game draws its own icons (`HdIcon` in
`K1RuntimeAssets.cpp`: the common `.tpc` files named `ia_`, `ii_` and `iw_`, 351 of
them, which `Test-NativeAssetsBank.py` holds the bank to).

**For the Mac: decide.** The Mac installs its files its own way. If it offers options,
this is one more; the rule for which files are the pack's is the same on both.

## 5. High FPS Fixes as a third patch

Since 2026-10-09. D3M0's
[High FPS Fixes 1.0.1](https://github.com/gnw-d3m0/D3M0s-KPatches/releases/tag/HighFpsFixes-1.0.1)
(MIT) repairs the game's timing above 60 frames a second. The Windows installer
carries the release's own `HighFpsFixes.kpatch` unchanged
(`third_party/Included/HighFpsFixes-1.0.1 by D3M0`) and, with *High FPS Fix* on,
installs it as a third patch (id `high-fps-fixes`, 36 hooks, no options). The option
is on by itself where the display reports 62 Hz or more at its current size and off
otherwise; a choice the player makes is kept. `tools/build_bundled_kpatch_config.py`
makes its hook blocks and refuses a patch that overlaps KMRP's.

**For the Mac: decide, and most likely nothing.** The patch declares the three
Windows KOTOR 1 executables and two Windows KOTOR 2 ones; it has no hooks for the
Mac executable. Whether the Aspyr build misbehaves above 60 frames a second in the
same way **is not something I know**. If it does, that is a question for D3M0 or a
port of its own, not something to copy across.

## 6. Frame rates

Since 2026-10-09. No new control: the Windows game's Screen Resolution list already
has a row for each refresh rate of 60 Hz or more ("3440 x 1440 @ 120 Hz") and hides
those above 85 Hz unless `AllowHighMonitorFrequency=1` is in `swkotor.ini`.

- With High FPS Fix the installer writes that and `RefreshRate` as the display's
  highest rate at the start size.
- Without it: `AllowHighMonitorFrequency=0`, `RefreshRate=60`, `V-Sync=1`, and the
  module hides every rate above 60 from the list (`EnumModesOnce` in
  `K1RuntimeResolution.cpp`), going by whether `high-fps-fixes.dll` is loaded.

Seen in a scratch copy on Windows: 120 and 60 screen updates a second at the main
menu, and the two lists.

**For the Mac: decide.** All of this stands on `EnumDisplaySettingsA` and the Windows
build's settings reader. **I do not know how the Aspyr build chooses its refresh rate
or whether it has these two settings.**

## 7. No resolution choice

2026-10-07, and already the tracker's item 30 with its own section: the Windows
installer's step 3 has no checklist, the game lists what the connected display
reports, and on a display without `swkotor.ini`'s size the game starts at the
display's own. Nothing new since.

## 8. Advanced Settings

The Windows installer's options are six tiles, three by two, in this order: Native
Controller Support (by RaymanGT; "Controller Support" by KMRP until 2026-10-09),
Modern Driver Compatibility, Area Map Marker Fixes, HD Item Icons, High FPS Fix,
Debug Logs. The High FPS Fix tile says in green what the display can do ("Display
supports 120 Hz").

**For the Mac: decide.** If the Mac installer names the same things, the maintainer
will want the same names and order.

## 9. Documents

- [features.md](features.md): for players, everything KMRP changes compared with the
  unmodified game. [features-technical.md](features-technical.md): the same list with
  mechanism, patch and source. Both describe Windows; the Mac has a line each.
- [README.md](README.md) of this folder is grouped by subject, and five records that
  describe nothing in the current build moved to `docs/history/`.
- The main README's install section was rewritten.
- `KPM-PATCHES-README.txt`, which the Windows installer writes beside the `.kpatch`
  files, described one patch with a controller option until 2026-10-08. If the Mac
  package carries a readme of its own for KOTOR Patch Manager users, check it for
  the same.

The Mac's documents were left as they were, at the maintainer's request, so
statements in them about Windows are as of the day they were written.

## 10. Bundled work

Checked on 2026-10-09:

| Work | Bundled | Current | Result |
| --- | --- | --- | --- |
| K1 Area Map Fixes (Derslok) | 1.0.0 | 1.0.3 | the note table, the one file KMRP takes, is byte for byte the same; nothing changes |
| K1 Modern Driver Compatibility (Synchro) | 1.2.0 | 1.3.0 | **not updated yet** on Windows |

`THIRD_PARTY_NOTICES.md` linked the wrong Deadly Stream page for the map fixes;
corrected.

## 11. Windows only

- The build copies the controller patch to `dist\controller` so the standalone file
  cannot differ from the one the installer carries.
- The installer was scanned on VirusTotal: 2 of 68 engines, both generic
  machine-learning labels. Leaving out the payload, the bundled libraries or the
  update check did not lower that. Signing was considered and dropped.
- Restore after the game was reinstalled over a KMRP install: tried in four ways on
  throwaway folders, all restored and installed again.

## What I would do first on the Mac

1. Merge `master` and resolve the tracker's row 15 (it conflicted before this work).
2. Say whether the Mac's controller patch ever changes a control's rectangle
   (item 2).
3. Read `resolution-switch.md`, section 6, against the Mac's own sites, and try a
   change of size in the game with the map: item 1.
4. Bring the abilities' chart repair to Windows, or say where it is, since Windows
   still lacks it.
