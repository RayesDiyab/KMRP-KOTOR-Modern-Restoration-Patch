# KMRP 1.6 on the Mac: what was ported, and what was seen

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md): measured claims only, and
> anything untested is labelled untested.

**Kind: port record**, 2026-11-03, against [`docs/macos-handoff-1.5-to-1.6.md`](../docs/macos-handoff-1.5-to-1.6.md)
(items 42 to 142), at `master` 4b34210 with the changes uncommitted. The package is
`KMRP-macOS-1.6.0.dmg`, built by `macos/build.sh` from the repository alone. The submodule's pin has
no widescreen entry points (audit MAC-1) and stays as Windows has it, so FTD's two Mac patches are a
copy in `macos/third_party/kpm-patches` (its `SOURCE.md` says from which commits and why): FTD's
latest of 2026-11-02, taken the same day, whose widescreen patch is upstream's with KMRP's two
commits merged. Until 2026-11-03 the package needed `--kpm` and a KotOR Patch Manager clone kept
beside the repository.

**FTD's latest (2026-11-03, after the playtest below).** His newest Stray Bug Fixes changes the
Scripts Enter fix at `0x1002d3e34`, which `kmrp-layout` also declared, identically until then; it
no longer does. Rebuilt and checked: original bytes against the game, the App Store translation of
the new hooks, the six Mac suites, and in the Steam game a save loaded, the menus, and two loads
from inside the game across a change of module, with no crash (`SOURCE.md` has the details).

## How it was checked

- **Seen in play** means run in the Steam game (KOTOR_Exe 1.4.0) at 3024x1964 and, where named, at
  1024x768, driven by the devkit with a scripted pad (`KMRP_PAD_SCRIPT`) and screenshots read one by
  one. No physical pad was connected: rumble, a pad going off and on, and SDL's own device list were
  not exercised.
- **Pazaak and the galaxy map** were opened by a test-only trigger built into a private copy of the
  controller module (never in the repository): the Pazaak start routine (0x100279E20) and the
  `ShowGalaxyMap` script. No save reaches either.
- **Regression tests on the Mac:** Test-MacAssets (now on the art pack, items 126, 139 and 140 added),
  Test-MacInstaller, Test-MacAppStore, Test-MacKpmOwnership, Test-MacFullscreen,
  Test-KmrpLayoutPatch (58 sites, 76 resolutions), Test-MacMemorySafety: all pass. Shared:
  Test-LiveLayout PASSED (73 screens against 66 sets, 19,706 C/Python layouts); Test-ModCompatibility
  837 checks, 0 failed; the text fit, button remap, display mode and HUD options harnesses pass when
  built with clang; Test-ControllerGlyphs passes.
- **Audit MAC-4 measured:** `kmrp-guiadapt.c` built for arm64 and x86_64 gives the same bytes for 438
  layouts (73 screens at six sizes). The icon helpers do not: Test-MacAssets now builds its reference
  tools for x86_64, the module's architecture, or a few icons differ by rounding.

## Items

| # | State on the Mac |
| --- | --- |
| 42-49 | As 2026-10-12; item 45's pad that types: `ControllerTypesByItself`, unrun with a Steam pad |
| 50, 51 | Mac's own. **51 seen in play 2026-11-03**: the App Store game through KMRP's launcher, the art pack read inside the sandbox, a save loaded and played |
| 52, 58 | Six places, Stealth with feats and in the third list (`KmrpXboxHudLists`, 0x100231179). Dim frames seen in play; Stealth not, no stealth generator at hand |
| 53, 54 | Stick, fire and Start in the swoop race and the turret (two hooks at the Mac's `UpdateAxis` calls); swoop model made into every set. **Not seen in play**: neither module was reached |
| 55 | Override fonts finished at the TXI loader (0x1001F887A). Not seen with a translation installed |
| 56, 64, 129 | Text Size and Font page, Original Font and HD Font, fitted atlases from the art pack. **Seen in play**: page, sliders, Link, Save, the unsaved-changes box; 36 fitted fonts in the cache. The Original Font seen at a start with it saved (`FontStyle=2`); switching on the page while the game runs not seen |
| 57, 68, 70 | Text fit, rows, stack counts, charts, pause notice, conversation panel, granted popup, and the Container widened for its captions. **Seen at 50% and 100% text** through all eight in-game screens, at 3024x1964 and 1024x768. A figure such as the vitality's "944/ 1056" breaks only at its space, never inside a number |
| 59, 61, 62, 66, 119 | HUD Size page, the PC HUD placed from the shared table. **Seen**: both tabs, the PC HUD after a key, the Xbox HUD back on the pad. Mouse drag to 100% not driven |
| 60, 79, 80 | Controller Layout: drawing, table, listening, Default box, Save refused while an action has no button. **Seen in play**, RB given to Undo or flourish; the screen lays itself out from its captions at the chosen text size, seen at 50% and 100% |
| 63, 81, 82, 97, 98 | Shared art, taken with the build |
| 65, 69, 85, 136 | Xbox HUD's description box, name bar, one lit place, pause notice. Pause notice with LB **seen**; a long name not seen |
| 67 | Controller exports for the pages (`pages.cpp`), found with `dlopen(RTLD_NOLOAD)` (audit MAC-5). Glyphs on the pages **seen** |
| 71 | Not applicable: the Mac installer refuses an install over an install |
| 72, 73 | The art pack, kmrp-assets.pack, beside the module (Windows' format and decoder), and every size the display offers made at install by `bin/kmrp-prepare` (Steam's game; the App Store game's cache is in its container, which the installer cannot write). **Measured**: pack 64.6 MB with the font sources, against 104 MB for the bank it replaces; KMRP-macOS.kpatch 100.5 MB to 0.35 MB; the disk image 114.8 MB to 76.2 MB. The install makes 23 sizes in 7 to 8 s on this Mac, a 3.9 GB cache; the first frame then comes at 4.7 s after launch (7.5 s with an empty cache); a change of size in the game registers a made set and unpacks nothing. Not made at install: the fitted fonts, which the first start makes |
| 74 | Not applicable |
| 75 | K1 Marked Empty Containers at the Mac's addresses (kmrp-map-notes, two hooks), option `marked-empty`, a tile in the installer. **Seen**: "Footlocker (empty)" after the last item was taken |
| 76 | The original Xbox controls. **Seen**: LB pause, RT/LT targets, RB ally, X the queued action (a medpac), L3 flourish, Start the last screen, R3 free look, LT out of it |
| 77 | `KMRP/controller.ini` in the game's settings folder; an older `kmrp-controller.ini` is moved there. Seen moved by the installer |
| 78 | Not checked on an ultrawide Mac display |
| 83, 84, 94 | Stick bound to 1; free look pitch (0x100291266) **seen**; 94 holds by reading |
| 86, 87, 96, 102, 111, 114-121, 123, 124 | Live Adaptive Layout from `assets.cpp` in Windows' order, then galaxy map and main menu. **Seen**: 73 screens laid out at 3024x1964 and 1024x768; main menu captions on their bars; galaxy map planets in the game's arrangement. The sets still carry their copies (a fallback), and the controller still carries its cued screens (124) |
| 88 | Not applicable: Party Roster Limit 32 has no Mac build |
| 89, 90, 91, 95, 100, 103, 106, 107, 108 | Pad on menus. **Seen**: Options never reaches Close, Graphics' resolution box keeps Graphics, character creation with Select and Cancel on two capsules, galaxy map by position, the save name popup stays up |
| 92, 125 | SDL's pad list in `controller.log`; 125 judged not needed (SDL on its own thread). Neither checked with a real pad |
| 99, 101 | The Mac carries every controller picture; checked against the built files |
| 104 | Letters centred, captions on their art, badges on the letters' middle (`KmrpCaptionLetters`). **Seen** at 1024x768 |
| 105 | Shared data |
| 109, 110, 44 | Pazaak's side deck as the Xbox's, the table's four boxes, X plays. **Seen**: a whole hand |
| 112 | The controller's screens read during the opening movie by a worker of the controller module (file reads only), their textures referenced two a GUI frame with a GL context. **Seen** in Steam's and the App Store's game: "33 files read during the movie, 27 textures referenced". Only the pad's family of pictures is warmed |
| 113 | Hidden first render. **Seen** in the log, seven views primed; the models lit on the first frame |
| 122, 128 | Shared C |
| 126 | Merged from Override (`DeriveFromOverride`). Tested by Test-MacAssets (a mod's tutorial.2da) |
| 130 | Icon Size slider, the two SetExtent wrappers. Not seen at another size |
| 131, 132, 134, 138, 141 | Fixed where the Mac had the fault; unrun with a real pad |
| 133 | As its rows; the Container widened at run time (GUI-4's subtraction at a change of size included), **seen** at 50% and 100% |
| 135 | Descriptions for the three rows. **Seen** |
| 137 | Holds already: `layouts_ini.cpp` uses a saved size only when the display offers it and KMRP covers it |
| 139, 140 | Marker counts the files; a failed helper tries twice more. Tested by Test-MacAssets |
| 142 | Judged not needed: the edge turn reads the GUI manager's pointer, which stays parked while the pad is in use |

## Audit (2026-11-03)

Three reviewers read the whole change against the Mac executable, its decompile and Windows' code:
the controller patch, KMRP's own runtime, and the installer, build and tests. Found and fixed the
same day:

| Finding | Fix |
| --- | --- |
| **High:** the map-note correction hook lost its `rbx` parameter when the Marked Empty hooks were added, and a duplicate hook hid it | The parameter restored; `make_kmrp_patch.py` now refuses a hook a part declares twice |
| The game and the installer's preparation could build the same cache folder at once | A lock beside each folder around check, fill and rename |
| Work folders of a process cut short were never removed (hundreds of MB each) | Removed once their process is gone |
| Unpacked blocks kept for the run after a change of font | Let go after the change |
| The installer's art step left `kmrp-prepare` running on a timeout or Ctrl-C | Each program's own PID kept, killed and waited for; Ctrl-C ends the step and completes the install |
| Uninstall removed the art pack under KotOR Patch Manager's KMRP module, or left it unowned | Kept while KMRP's module remains, removed when nothing of KMRP's does |
| A failed copy could not be rolled back (row written after the copy) | Row first, copy under a temporary name, then renamed |
| `grep -q` under `pipefail` in three checks (one let an archive with `._` entries pass) | Output captured first |
| The move of an older `kmrp-controller.ini` was not undone by a failed install | Recorded and undone; a test round added |
| The mini-games read the raw pad, so a button held through a movie fired there | They read the filtered word, as Windows does |
| A texture call declared with an `int` where the engine takes a pointer | Declared as a pointer, passed null |

The two low findings left at first were fixed the same day, after the playtest below:

| Finding | Fix | Seen |
| --- | --- | --- |
| A drawn picture (Pazaak, class selection) gave the controller's folder to the game again under a new alias, so the search list grew by one a picture | `standalone::ListAgain`: the same alias added again, which `CExoResMan::AddKeyTable` (0x100369130) answers by rebuilding that table in place (0x10035C2F4) as Windows' 0x4088E0 does; `RegisterAgain` is kept for a change of resolution, which needs the folder in front again | A Pazaak hand: its pictures shown, the folder registered once (`KMRPCTL1`) in the run |
| The rumble hook at 0x10027A106, from before this port, never took its consumed exit: KotOR Patch Manager runs the stolen bytes before its test, and their `xor eax, eax` cleared the handler's 1, so the engine's queue code ran after every rumble | The hook moved to the function's entry (0x10027A0FC), the prologue stolen: no instruction there touches `eax`, the epilogue at the exit unwinds that frame, and a 0 resumes at 0x10027A106 untouched | A script's `PlayRumblePattern(9999)` returns 1 (the exit taken) where the old hook returned the engine's 0, told apart by the pattern the script played next; the script's pattern 1 reaches the mixer. Not with a physical pad |

## Playtest (2026-11-03)

The final package installed as a player gets it (Steam's game, 23 sizes made in 7 s, nothing left
running), then played with a scripted pad, the keyboard and, separately, in the Mac App Store's game.
Seen: a new game from class selection through the quick character, name, the opening film and
Trask's conversation on the Endar Spire; Game 22 on Manaan: every in-game screen at 50% and 100% text,
the Graphics, HUD Size, Text Size and Controller Layout pages, a remap, the Original Font, a change of
resolution, the save name popup, the area map with its notes, a conversation's replies, the workbench
upgrade screen, the galaxy map and a hand of Pazaak (both opened by a test-only trigger), the
footlocker marked empty and the Container screen; the keyboard's hotkeys, the PC HUD and Esc with no
badges shown; the App Store game loading a save. **Not reached:** a fight against an enemy (the saves
at hand have none near; a script that made a bystander hostile did not take), the swoop race and the
turret. No run crashed.

## The release build (2026-11-03)

Built from a fresh checkout, the package showed that `build/fonts`, the font sets
`tools/build_font_scale_sets.py` makes and `build.sh` reads, had been a cache from 2026-09-29 in
every earlier build, before the font tools' changes of 2026-10-18 to 2026-11-01 (README.md,
section 9). Made afresh, every atlas file differs from the old cache. The package built from
scratch with them passes the seven Mac suites, Test-MacAssets included, and was seen in the
Steam game at 50% and 100% text and with the Original font (Options, Equip, Inventory, the HUD),
the Original font's glyphs told apart from the HD font's.

## Faults known at the end

None found in play that is not fixed above. Still unseen with a physical pad: rumble, a pad switched
off and on, SDL's device list. The Mac App Store game was not given every size at install (its cache is
its container's).
