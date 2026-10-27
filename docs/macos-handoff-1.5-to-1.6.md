# macOS handoff: everything from 1.5 to 1.6

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: handoff.** Started 2026-10-22 at the maintainer's request: Mac players have **KMRP
1.5.0** (tag `v1.5.0`, 2026-10-09) and nothing after it. The Mac's 1.5.1 installer was taken
down the day it was added, so 1.5.1's repairs never reached them either. Everything that
changed from 1.5 to 1.6, small or large, that the Mac needs is here; the changes that are
Windows' alone are listed at the end with the reason. It replaces
`docs/macos-changes-from-windows.md` (items 1 to 87, in git history up to 1ec85d1): the
items before 42 were all from before 1.5.0 and are dropped; items 42 to 87 are carried over
with their numbers and their text, and 88 to 94 were added after a commit-by-commit check of
`v1.5.0..1ec85d1` on 2026-10-22. Where that check found an item incomplete, a paragraph
headed **Also (2026-10-22)** says what it lacked.

Each item says what changed on Windows, where, what the Mac needs and how to check it.
Nothing here was built or run on a Mac for this document. The Mac's own reference is
[`macos/README.md`](../macos/README.md), and [`macos/WINDOWS-PARITY.md`](../macos/WINDOWS-PARITY.md)
keeps the table of every Windows change and its state on the Mac.

| # | Change |
| --- | --- |
| 42 | 1.5.1: the player's Override comes before KMRP's files (`YieldToOverride`, 2026-10-11) |
| 43 | 1.5.1: a font from Override is drawn at the size of KMRP's own (`KmrpScaleOverrideFontsK1`, issue 34) |
| 44 | 1.5.1: Pazaak, A plays the focused hand card (issue 42) |
| 45 | 1.5.1: one pad seen twice no longer stutters (the 80 ms take-over; the pointer while the pad is held) |
| 46 | 1.5.1: a log of controller events for a player's report |
| 47 | 1.5.1: a key that is not the keyboard's is not keyboard use (a pad's Back as `KEY_BACK` under Linux) |
| 48 | 1.5.1: a destroyed input object used after a change of resolution (seen on SteamOS) |
| 49 | 1.5.1: the modules decode their own banks (no `cabinet.dll`), XInput loaded at run time (Windows 7), the installer under Wine, Restore Original at another path, the `%TEMP%` folders |
| 50 | Anti-aliasing off at 3840x2160 pixels or more, in the module |
| 51 | The Mac App Store's game |
| 52 | Xbox-style HUD: Stealth in the action row |
| 53 | Controller: swoop racing and the gun turret |
| 54 | Swoop race: the speed gauge's parked segment on a wide screen |
| 55 | Override fonts finalized before the first text layout |
| 56 | Native text-size and font page, shared font atlases |
| 57 | Text fitted to its space at any text size |
| 58 | Xbox-style HUD: the action row as the Xbox manual's six places (issues #55, #50) |
| 59 | HUD Size page; the mouse and keyboard HUD placed at run time |
| 60 | Controller remapping on the Controller Layout screen |
| 61 | HUD Size and Text Size sliders: the mouse reaches 100% |
| 62 | HUD Size preview: Disengage in its frame |
| 63 | HD font atlases rebuilt: every Windows-1252 character, no stray lines |
| 64 | HD Original font, the default; the HD fonts at 6x, fitted at run time |
| 65 | The action description at the text size; the Xbox action box as tall as the tallest action |
| 66 | From the pad to the mouse at once; HUD Size up to twice; HUD sliders with a pad |
| 67 | KMRP's option pages with a pad; the entry buttons' A |
| 68 | The size search finds the largest size that fits |
| 69 | Xbox-style HUD: the name bar grows with a long name |
| 70 | Text Size and Font: the right-hand column inside its frame |
| 71 | Dated builds and Upgrade in the installer |
| 72 | Windows keeps its cache too, and goes two steps further |
| 73 | The art pack, and every size made at install: the Mac does the same |
| 74 | Modern Driver Compatibility left out where it cannot run: not on the Mac |
| 75 | Marked Empty Containers, and Advanced Settings that scrolls: the Mac needs a port |
| 76 | The original Xbox controls everywhere: the Mac's controller patch needs the same |
| 77 | KMRP's files in one folder: the Mac should do the same |
| 78 | Movies in a 16:9 area, and Bink with GDI: what applies to the Mac |
| 79 | A Default button on the Controller Layout screen as it opens |
| 80 | Remapping in a table |
| 81 | A round o in the Original HD Font |
| 82 | The HUD font's black outline |
| 83 | The stick's vector never longer than 1 at the engine |
| 84 | Free look looks up and down |
| 85 | The galaxy map navigates itself, and the action row has one lit place |
| 86 | A shop's list widened by its rows' real height (issue 61) |
| 87 | The galaxy map from the game's own places (issue 67) |
| 88 | The 32-slot party roster (issue 38) |
| 89 | A on a message box no longer clicks the button behind it |
| 90 | The left stick walks a conversation's replies |
| 91 | The left stick on screens that navigate themselves |
| 92 | The pad log lists SDL's pads (issue 54) |
| 93 | The run-time asset notes only with debug logs |
| 94 | The stick's vector inside the unit circle, in the buffer |
| 95 | Glyph buttons are hints: the D-pad never lands on them |
| 96 | Main menu captions in the middle of their bars |

Items 46 and 47 are in the 1.5.1 group below (46: the controller events log; 47: a Linux
pad's own key, Windows and Wine only).

## 1.5.1's repairs on the Mac (items 42 to 49)

**Not released.** Ported in `master` on 2026-10-12, but the Mac's 1.5.1 installer was taken
down the day it was added (`CHANGELOG.md`, "macOS, the Mac App Store's game: work in
progress"): Mac players have 1.5.0, and these reach them with the Mac's 1.6. Items 43 and
45 are already superseded on Windows by items 55 and 66.

| # | 1.5.1's change | State on the Mac (as written 2026-10-12) |
| --- | --- | --- |
| 42 | 1.5.1: the player's Override comes before KMRP's files (`YieldToOverride`, 2026-10-11) | **ported 2026-10-12**: the Mac had the same fault, not "none" as 1.5.1's note says. `assets.cpp`, `PlayerHas`, `LinkSet`; `Test-MacAssets.py` case 3. Not seen in the game with a mod's files |
| 43 | 1.5.1: a font from Override is drawn at the size of KMRP's own (`KmrpScaleOverrideFontsK1`, issue 34) | **ported 2026-10-12** (`assets.cpp`, `ScaleOverrideFonts`), from the Mac's texture array and font object. **Not seen in the game**: no translation installed |
| 44 | 1.5.1: Pazaak, A plays the focused hand card (issue 42) | **ported 2026-10-12** from the executable (`gui.cpp`, `PazaakPlayFocusedCard`). **Not played**: no save reaches a table |
| 45 | 1.5.1: one pad seen twice no longer stutters (the 80 ms take-over; the pointer while the pad is held) | **ported 2026-10-12** (`backend_sdl.cpp`, `prompts.cpp`). **Not measured**: no translator or second view of a pad at hand |
| 46 | 1.5.1: a log of controller events for a player's report | **the Mac's `controller.log` is such a log already**; added 2026-10-12: the key that took the game to the keyboard, and a pad's product id beside its vendor |
| 47 | 1.5.1: a key that is not the keyboard's is not keyboard use (a pad's Back as `KEY_BACK` under Linux) | **not needed on the Mac**: the fault is Linux's kernel driver presenting the pad as a keyboard too; the key is now logged (item 46) should it ever show |
| 48 | 1.5.1: a destroyed input object used after a change of resolution (seen on SteamOS) | **not on the Mac**: see the section |
| 49 | 1.5.1: the modules decode their own banks (no `cabinet.dll`), XInput loaded at run time (Windows 7), the installer under Wine, Restore Original at another path, the `%TEMP%` folders | **n/a**: Windows, Wine and Proton only; the Mac's banks are zlib and its caches are per build, with ended runs' folders removed |

**2026-10-12.** 1.5.1 was released for Windows and for Linux with Proton with the note that
none of its faults is in the Mac build. Each entry of `CHANGELOG.md`'s [1.5.1] was read against
the Mac's code that day; three faults were there too.

**Override first (42).** The Mac registers its two folders after `OVERRIDE:`, and a folder
registered later is searched first (`macos/README.md`, "The menus inside the module"): exactly
Windows' 1.5.0. Only the bundled third-party art yielded to the player's files. Now `Prepare`
(`patches/kmrp-assets/assets.cpp`) gives the game links to the cache without any file the
override folder has (`PlayerHas`: the same name, and for a texture the `.tga`, `.tpc` and
`.txi` of that name, as `YieldToOverride`). Where Windows deletes the files from its folder of
the launch, the Mac leaves the set whole in its cache and makes a folder of links a
registration, `set-<pid>-<n>`, beside `art-<pid>`; both are removed when their run has ended.
`layout.cpp`'s `LoadLayout` reads a layout from the override folder when the player's has taken
the set's place. `Test-MacAssets.py`, case 3: with five files in the override folder (a KMRP
texture, a layout, a font's texture in the other format, two of the bundled art) exactly those
and their `.txi` are left out, and the cache keeps the set. **Not seen in the game.**

**Fonts (43).** The Mac's textures are the array at `0x100635b58` (`0x100635b60` of them),
names at +0xBC, the font object at +0x48 (`resolution.cpp`, `ReloadFontMetrics`); its fields
are Windows' (`kmrp-layout/text.h`). `ScaleOverrideFonts` multiplies fontheight,
baselineheight, texturewidth, spacingR and spacingB (+0x04 to +0x14) by KMRP's `fontheight`
for that name over the font's own. The five offsets were read from the Mac's TXI parser
(`CAurFontInfo::ParseField`, `0x1001F850E`), which writes them in that order. Called where
Windows calls it: each GUI frame, as a panel starts loading, and
after the metrics are read again.

**Pazaak (44).** `CSWGuiPazaakGame` (constructor `0x1002204A6`, vtable `0x1005A5B80`,
`HandleInputEvent` `0x100222B9C`) has four `CSWGuiPazaakCard`s from +0x3A40, 0x3F0 apart
(`SetHandEnabled`, `0x100222AC4`). Each gets four handlers (`0x100220F4E` on): A (0x27)
`0x100221B7C`, which plays the card only when `[panel+0xAB30] == 1`; the drop of a drag
(0x17FEB) `0x100221BD6`; 0x1F9 `0x100221C5A`, which plays it on the player's turn
(`[panel+0xAB20] == 3`); 0x44 `0x100221C78`. Windows calls "the mouse's" handler
(`0x0067EF80`); here that is taken to be `0x100221C5A`, the one that plays a card with no
further condition, **not matched to Windows' by its code**. A on a focused card with no mode
set calls it and the engine's A is not sent, in the menu class and the mini-game class.

**Also (2026-10-22).** On the original Xbox layout (item 76) Pazaak's A is End Turn and X
plays the focused card: the Mac's port of playing the focused card on A has to move to X.

**Two views of one pad (45).** `ReadSdlPad` took whichever pad moved, at once, as Windows'
did. The 80 ms rule and the second and a half in which a moving pointer is not mouse use are
Windows' (`K1ControllerBackend.cpp`, `MouseIsBeingUsedK1`). The Mac reads pads through SDL
only (GameController only when SDL is missing), so one pad twice needs Steam Input or a
translator; none was tried.

**Also (2026-10-22).** The "pad that types" rule (`KmrpNoteKeyboardK1`, 161559c): a key
pressed while one of Valve's pads is held is made a release and is not keyboard use (a Steam
Controller's lizard mode types arrow keys, Enter and Escape). Needed on the Mac wherever its
keyboard-use test runs. The SDL-before-XInput order does not apply (the Mac has SDL only).

**The input object (48).** Windows kept the object its `GetEvents` hook saw and polled it
later in the frame from the movement hook, after a change of resolution had destroyed it. The
Mac keeps the pointer too (`native.cpp`, `g_input`) but uses it only inside the engine's own
poll of that object (the device read), and its movement, camera and HUD hooks are handed
their object by the engine each call. Changes of resolution with a save loaded and the pad in
use were made on 2026-10-08 (items 31, 32 and 41) without a crash.

## 50. Anti-aliasing off at 3840x2160 pixels or more, in the module

**Mac only, 2026-10-12.** Windows has no such rule. The installer's (2026-10-09) went by the
display at the time of install; the module now keeps it by the size the renderer is started
with, at start-up (`KmrpStartRenderer`, hook `0x10026cf81`) and at a change of size
(`KmrpModeSwitch`), by setting the renderer's sample count (`0x1006338e4`) and leaving the
player's setting (`CClientOptions` +0x38, `swkotor.ini`) as it is. `keep-anti-aliasing=1` in
`configs/kmrp.ini` (the installer's `--keep-anti-aliasing`) turns the rule off. Measured with
the cut-off lowered on a 1512x982 game: 0 sample buffers with the rule, 1 buffer of 2 samples
without. Not seen at 3840x2160 itself, nor across a change of size in the game.

## 51. The Mac App Store's game

**Mac only, 2026-10-12** (`docs/macos-app-store.md`, section 7). A second build of the game
that cannot be installed into: KMRP is an app beside it that starts it with the patcher
inserted, every address translated from Steam's build by the Mac build's tools
(`macos/tools/appstore/`). Nothing of it is in Windows' code or installer.

So the Mac version is to support two games from its 1.6 (built in `master` since 1.5.1's
work, not released), as Windows supports three executables,
but not in the same way. Windows' three are told apart by the installer and patched in
place by one runtime with an address table for each. The Mac's two are told apart by bundle
id and SHA-256; Steam's is patched in place, and the App Store's is left as it is and
started by KMRP's app, with the sources' addresses translated at build time instead of
looked up at run time. The row-by-row comparison is in `macos/README.md`, "The two games".
Since the same day KMRP also makes that game's window cover the display
(`docs/macos-app-store.md`, section 7.5): set to full screen it opened a window with a title
bar, which Steam's game does not.

## 52. Xbox-style HUD: Stealth in the action row

**To do on the Mac, 2026-10-13** (issue #50; `src/controller-native/K1XboxHud.cpp`,
`KmrpXboxHudStealthK1`; `docs/controller-xbox-hud.md`, "Stealth"). On Windows the controller
patch has one more hook, at the entry of `CSWGuiTargetActionMenu::PopulateMenus`
(`0x00689410`), which adds a "Stealth" entry to the first personal action list while the Xbox
layout is shown and the leader can use Stealth (superseded on 2026-10-18 by item 58: one hook
later in the same routine, Stealth with the feats and skills). Seen working on Windows by the maintainer the
same day, after a first build that ended the game on A: `PartyMenuStealth` takes two words
off the stack, which a decompiler's signature did not show. Check the Mac routine's own
arguments before calling it.

What the Mac needs: the same routine in its copy of the HUD, hooked where the Mac game calls
the target menu's `PopulateMenus` from the HUD's, with the Mac addresses of `IsStealthCapable`,
`PartyMenuStealth`, `GetSWParty`, `GetPlayerCharacter`, the action list's `Allocate`,
`CExoString`'s assignment and `GetGUIString`, and the entry's layout checked there (on
Windows `0x38` bytes; the routine at `+0x0C` is called as a member of the character with the
id and the character on the stack, and takes both off). To check: a character with the skill
and a stealth field generator shows "Stealth" in the row's second place; A toggles it.

## 53. Controller: swoop racing and the gun turret

**To do on the Mac, 2026-10-13** (issue #47; `src/controller-native/K1NativeJoystick.cpp`,
`NativeMiniGameAxisK1`; `docs/controller-native-path.md`, "Swoop racing and the turret"). On
Windows the pad did nothing in a swoop race or in the turret: the game polls keyboard actions
there. One new hook at the entry of `CSWMiniGame::UpdateAxis` (`0x00670FB0` on Windows) adds
the left stick to the polled vector and calls `CSWMiniPlayer::Fire` once for each press of A
or a trigger (triggers in the turret only). **Update, 2026-10-16:** the maintainer
confirmed the swoop prompt works and A, LT and RT each fire in Windows Steam's
turret. Start and the turret's vertical direction remain unreported from play.

What the Mac needs: the same routine at the Mac game's `UpdateAxis`, with the Mac's offsets
of the game's type and player and the address of `Fire`, each read from the Mac executable
(what a routine takes off the stack included: item 52). To check: a swoop race steers with
the stick and A starts and shifts; the turret aims with the stick and a trigger fires.

**Also (2026-10-22), not in the text above** (fd14f6a): the swoop race's shift prompt shows the
pad's A glyph instead of the Space picture while a pad is in use (`UpdateSwoopPromptK1`,
`SwoopPromptMaterialK1`, found through the race's `m17mg_camera` model, `Plane14`), with four
private glyph textures from `tools/build_controller_assets.py`; and the turret's fire inputs
each keep their own held bit (`NativeMiniGameAxisK1`), so one fire a frame is asked for.

## 54. Swoop race: the speed gauge's parked segment on a wide screen

**To do on the Mac, 2026-10-13** (issue #47; `macos/tools/kmrp-swoophud.c`; CHANGELOG,
[Unreleased]). On a screen wider than 16:9 a red chevron stands at the bottom left of a swoop
race, outside the dashboard: the ninth segment of the speed gauge in the HUD's model,
`m17mg_camera`, parked just outside a 4:3 view. The new helper makes a copy of the model from
the player's game with that segment parked far away (five floats changed) and writes it with
its `.mdx`. Windows calls it from `K1RuntimeAssets.cpp` after `KmrpGameArt`, into the same
cache. Built and installed on Windows; **not yet seen in the game there.**

What the Mac needs: `kmrp-swoophud.c` in the list of helpers linked into the patch
(`macos/tools/make_kmrp_patch.py`, with `-DKMRP_EMBEDDED`) and a call to
`KmrpSwoopHud(key, outdir)` where the Mac makes its game art. The file was compiled with
clang and MSVC on Windows only. To check: a race at a wide size shows no chevron outside the
dashboard, and the gauge's last two segments still light at top speed.

## 55. Override fonts finalized before the first text layout

**To do on the Mac, 2026-10-17** (issue #63;
[Windows reference](../reverse-engineering/override-font-metrics.md)). Windows now
sizes the five existing Override font metrics at the native TXI loader's common
return, replacing the frame/panel-start walk. This prevents first-use line breaks
from being measured before enlargement. The same callback finalizes resolution
reloads, preserving source files, artwork and glyph coordinates. Native control-flow,
9,504 metric cases and Windows installer/package regressions pass; real dialogue
wrapping with translation fonts is not yet visually verified.

The Mac still uses `ScaleOverrideFonts` in `assets.cpp`, called from its GUI-frame,
panel-start and resolution-reload paths. A port must first measure the Mac's own
font-loader completion path and apply sizing before the first layout consumer.
No Mac addresses or in-game result are claimed by this Windows change.

## 56. Native text-size and font page, shared font atlases

**To do on the Mac, 2026-10-17.** Windows now clones the live Graphics screen's
Advanced button for a Text Size and Font entry. Its native page provides four shared-font sliders (menus/replies, subtitles/body,
small text and HUD), with 1% increments and Link Text Sizes on by default,
and mutually exclusive Original/Original Sharpened/New HD font choices, with the former actual size labeled
50%. The module stores one atlas set per style, scales native metrics and reflows
strings live; it does not rasterize fonts while playing. Override translation
fonts keep their files and glyphs. Windows source/mock verification is described
in [in-game text options](ingame-text-options.md); actual game presentation and
interaction remain unverified. This menu, shared-bank format and saved preferences
have not been ported to the macOS module.

## 57. Text fitted to its space at any text size

**To do on the Mac, 2026-10-17** (depends on item 56). Windows fits each native
text string on its own when the engine wraps and draws it
(`src/controller-native/K1TextLayout.cpp`, `K1TextRows.cpp`, `K1TextFitPolicy.h`):
fixed boxes draw at the largest size up to the chosen one that fits; list rows grow
with their text and the list's scroll, selection and click areas follow; scrolling
descriptions and text entry keep the chosen size; the PC pause notice takes the
menu-button row's width. Five new hooks sit on `CSWGuiText`'s constructor,
destructor, wrap and draw and on the list box's draw (Windows addresses in
`kotor1-native-runtime.hooks.toml`). The size search (`K1TextFitPolicy.h`) is
platform-independent; the Mac needs its own addresses for those five functions and
the same object offsets confirmed. The store/inventory and workbench row classes
pin their button's border, highlight and text to the icon height whatever the row's
height (Windows `0x006B5270`, `0x006C2650`), so the row adapter also stretches those
three; check the Mac's copies of both functions do the same. Windows mock tests pass; not yet play-tested on
Windows either.

An item's stack count (`+0x324` on inventory and store rows, `+0x334` on workbench
rows) is a box the size of its digits at the chosen text size, its lower right
corner at (52, 54) of the 56 px hex art in proportion to the live icon, capped at
half the icon each way with the digits shrunk to fit beyond that. The maintainer
placed it in play on Windows on 2026-10-18, after trying it centred in the hex's
lower-right notch, at (52, 53), (56, 56) and (52, 52). The Mac should use the same
proportions.

Feat and power chart rows (`CSWGuiSkillFlow`, Windows vtable `0x7578A8`, SetExtent
`0x006CCE30`) grow by the same icon scale (text size / 50, never below 1), and the
drawn rectangle (`CSWGuiImage` +0x14, the only one `Draw` uses) of each cell's feat
icon (cells of 0x128 bytes from +0x5C, icon at +0x74 in each) and of the two arrows
(+0x3D4, +0x428) is scaled about its centre on every list draw, an icon kept inside
its cell. The Mac needs its own offsets for the same layout.

The computer terminal's reply list (`computer.LB_REPLIES`) has its scrollbar put where
its `.gui` puts it, relative to the list, on every GUI frame (`PlaceBars`,
`K1RuntimeLayout.cpp`): the engine's `CSWGuiListBox::SetScrollBarExtent` (Windows
`0x004181F0`) uses only the file's width and moves the bar to the list's edge at the
list's height, beside the track `panel01` draws for it. The bar is the list's member at
+0x104 on Windows; the Mac needs its own offset. Its track (not its whole extent) is the
file's rectangle: the arrows (the bar's image at +0x134, as tall as its texture) go
beyond each end.

The conversation's lower panel (`CSWGuiDialogCinematic`, Windows vtable `0x755800`),
its `LBL_MESSAGE` and its `LB_REPLIES` grow every GUI frame down to the screen's bottom
less the gap between the bottom bar's top and the panel's top (`Dialogue`,
`K1TextLayout.cpp`); the bars keep the letterbox recipe's height. Not checked on the
Mac: whether its letterbox port also leaves the panel 100 tall while a line is spoken.

**Also (2026-10-22).** There are six hooks, not five: the sixth is on `GetIdealHeight`
(`0x0045B7A0`, added 2026-10-18). Not in the text above: the granted-feat popup grows with
its rows up to 1.5 times its size (`K1GrantedPopup.cpp`, `KmrpGrantedPopupFrameK1`; the Mac
has its own `granted_popup.cpp` to bring in line), and the item, skill and power icons of
the inventory's and store's rows are drawn larger with the menu text size (x1.3 at 65%),
not only the feat and power charts.

## 58. Xbox-style HUD: the action row as the Xbox manual's six places (issues #55, #50)

**To do on the Mac, 2026-10-18.** On Windows the controller HUD's row now follows the
Xbox manual (page 8): default action, feats and skills, offensive Force powers, grenades
or mines, the character's own Force powers, medpacs and the other usable items together.
One hook reshapes the lists the game has just made (`KmrpXboxHudListsK1`, Windows
`0x0068947A` in `CSWGuiTargetActionMenu::PopulateMenus`, after the three target lists
are filled and before any slot is shown, `ebp` the menu):

- the third personal list (other items, `GetUsableItems(4)`) is joined to the end of
  the second (medical), then emptied with `CSWGuiInterfaceAction::Clear` (Windows
  `0x0063C000`) on each entry;
- that emptied list holds Stealth while the leader `IsStealthCapable`, and Stealth is
  also joined to the end of the target's feats (target list 0) when it has any.

This replaces item 52's hook at the routine's entry: Stealth is no longer added to the
character's own Force powers. `kPlace` is `{1, 2, 3, 4, 5, 1, 3}` (the feats and the
skills share the second place, grenades and mines the fourth), the pad's order in
`MoveFocus` `{-1, 0, 5, 1, 2, 6, 3, 4}`, and every place with no slot shown is drawn as
a dim frame. The Mac's `macos/patches/kmrp-controller/xbox_hud.cpp` needs its own
addresses for the site, `Clear` and the routines of item 52; see
`docs/controller-xbox-hud.md`, "The six places". Played on Windows by the maintainer on
2026-10-18: "works". Only while the Xbox layout is shown: mouse and keyboard keep the
game's own lists.

## 59. HUD Size page; the mouse and keyboard HUD placed at run time

**To do on the Mac, 2026-10-18** (`docs/hud-size-options.md`). On Windows, Graphics Options
has a HUD Size page (`K1HudOptions.cpp`) with a slider for each part of each HUD, saved in
`swkotor.ini`, `[KMRP HUD Size]`; 50% is today's size, 100% two and a half times it
(`K1HudOptionsPolicy.h`, `Factor`). KMRP's module now places the PC HUD itself from a table
(`K1PcHudLayout.inc`, written by `tools/build_pc_hud.py`; the placing in `K1PcHudLayout.h`
is plain C++ and can be shared as it is) and applies it from its GUI frame (`K1PcHud.cpp`),
finding controls by tag and setting the HUD's own fields: Windows `+0x6080` (map window),
`+0xA454` (description edge), the target menu at `+0xBC` (`+0x15B4` width, `+0x15BC` clamp,
`+0x1AE8`/`+0x1AE9` gaps), each `CSWGuiMainInterfaceChar`'s home at `+0xE98`, and
`LBL_ARROW_MARGIN`. The Mac needs its own offsets for these fields; the tags are the same.
The Xbox-style HUD scales each part in `ApplyXbox` and reads the ini itself; it now keeps
the PC HUD anew each time it takes it (`Keep` before `ApplyXbox` when the layout is not
up). Two exports connect the modules: `KmrpXboxHudOwnsK1` (controller) and
`KmrpHudAppliedSizeK1` (KMRP). To check: at 50% the HUD is as before; each slider sizes its
part about its corner; the target's name stays centred over its circle.

**Also (2026-10-22).** The minimap's picture zooms with its window only from 121 pixels up,
and shows less of the area below that (`docs/hud-size-options.md`, "Minimap"); the
combat-mode message moves right as the minimap grows.

## 60. Controller remapping on the Controller Layout screen

**To do on the Mac, 2026-10-18** (`docs/controller-layout.md`). On Windows the Controller
Layout screen opens as a view with (X) Remap and (B) Back; Remap makes the rows editable,
with (Y) Default, (X) Save and (B) Close. The rules are plain C++ and can be shared as they
are: `src/controller-native/K1ButtonRemapPolicy.h` (what can be remapped, no swapping, the
editor's rows, the per-press translator), tested by `testing/regression/Test-ButtonRemap.py`.
The runtime, `K1ButtonRemap.cpp`, reads and writes `kmrp-controller.ini`, `[Controller Remap]`.
The Mac needs: the translation applied where its controller patch reads the pad (Windows:
`FillNativeJoystickBufferK1`, after `ReadPadAxes`, in the world input classes only, the
triggers folded into bits `0x0400` and `0x0800`); the screen's controls and states, which
`K1ControllerLayout.cpp` builds from the layout file's own controls (`bindAppend`,
`CSWGuiPanel::AddControl`, Windows `0x0040B9A0`); the pad-focus exclusion for the footer's
buttons (`KmrpPadFocusExcludeK1`); the HUD cues following the remap (`ShowActionCueK1`, the
pause notice's `KmrpRemapGlyphK1`); and the new glyph textures, which
`tools/build_controller_layout.py` already makes for every family (`kmr<family>rm<code>`,
`kmrrmask`, `kmrrmlock`, `kmrrmdot`). Tested on Windows with mouse and keyboard only; the pad
flow is untested there too.

## 61. HUD Size and Text Size sliders: the mouse reaches 100%

**To do on the Mac, 2026-10-18** (`docs/hud-size-options.md`). On Windows KMRP's option
sliders get their own copy of the slider's table (Windows `0x0073E9D0`, 40 entries) with the
mouse move (entry 4, Windows `0x00419250`) replaced and the button down (entry 6, Windows
`0x004191D0`) wrapped, so the value is the one the thumb is drawn at
(`src/controller-native/K1SliderGrip.h`; the arithmetic, `DragValue`, is tested by
`Test-HudOptions.py`). The Mac needs the same table's address and the addresses the header
lists (`SetValue`, the thumb's border rect, the panel's pointer position) for its build. To
check: drag each slider to the end of its track and let go; it reads 100%.

## 62. HUD Size preview: Disengage in its frame

**Build and check, 2026-10-18.** The preview now draws the combat queue's backing and frame
(`LBL_COMBATBG2`, `LBL_COMBATBG3`; the table's preview flag, `K1PcHudLayout.inc` from
`tools/build_pc_hud.py`) and the word Disengage centred (`CSWGuiTextParams::SetAlignment`,
Windows `0x00415F20`, alignment 18). The table is shared; the Mac needs the alignment
routine's address if its port of `K1HudOptions.cpp` sets it.

## 63. HD font atlases rebuilt: every Windows-1252 character, no stray lines

**Build and check, 2026-10-18** (`docs/font-scaling.md`). `tools/build_font_from_ttf.py`
now reads each font place as Windows-1252, leaves control characters blank, keeps each
letter inside its own place and stops if the font lacks a character the original holds;
the 18 atlases in `assets/hd-fonts` were rebuilt with it. Nothing in code changed; the Mac
gets the new atlases with its next build of the shared assets. To check: on the Text Size
page with the New HD Font, the HUD sample reads "HUD: 0123456789" with no lines after the
colon, and a text with a euro sign, curly quotes or an ellipsis shows them.

## 64. HD Original font, the default; the HD fonts at 6x, fitted at run time

**Build, 2026-10-18; not yet seen in the game** (`docs/hd-original-font.md`,
`docs/ingame-text-options.md`). What the Mac needs:

- **A third font set.** `assets/hd-original-fonts` (36 files, from
  `tools/build_hd_original_fonts.py`) is the new style, stored in the bank as
  `kmrfho00` to `kmrfho17` in place of `kmrfpc` (Original Sharpened, retired;
  `tools/build_original_fonts.py` no longer writes it). The bank's font version is 4.
- **The style numbers and default.** `FontStyle` 0 is (Old) HD Font, 1 (New) Original
  HD Font, 2 Original Font; a missing or invalid value means 1 (it meant 0). The
  legacy `OriginalFont=0` means Old HD, anything else or nothing HD Original. Labels:
  "(New) Original HD Font", "(Old) HD Font".
- **6x atlases, fitted.** Both HD sets are baked at 6x (`assets/hd-fonts` too; it was
  3x). `ApplyTextPreferences` takes the reference height as Old HD's `fontheight` times
  3/6 (single precision) and resamples each HD atlas to the drawn size (`FitAtlas`:
  each new texel the area average of the old ones it covers), setting `texturewidth`
  to the new width. A port that draws the 6x atlas unfitted gets text sampled down from
  six times its size.
- **The bank's caption measurement** (`shared_font_txi`) now models HD Original's TXI
  at the default size, since that is what the module hands the blend helper by default.
- **`HD_FONT_BAKE_SCALE` is 6.0** in `tools/prepare_universal_resources.py` (only a
  resolution with no font scale set of its own uses it).
- **Old HD's `fnt_d16x16` and `fnt_d10x10b` are Arimo**, baked from the repaired TXI
  (`stock_txi` in `tools/build_original_fonts.py`) as `fnt_d16x16b`'s twins, in
  `assets/hd-fonts` and in every font scale set (`tools/build_font_scale_sets.py`).
  Rebuild the Mac's scale sets for those two names; the runtime then sizes them as
  `fnt_d16x16b`.

To check: a fresh `swkotor.ini` opens the Text Size page with (New) Original HD Font
selected; menu text then matches the original's letters and line lengths; at 100%
text on a large screen it is sharp.

## 65. The action description at the text size; the Xbox action box as tall as the tallest action

**Build, 2026-10-18; not yet seen in the game** (`docs/controller-xbox-hud.md`).
`KmrpTextIdealHeightK1` (`K1TextLayout.cpp`) no longer measures the HUD's action
description (`CSWGuiMainInterface +0xA1D4`) at the original text size: the
`hudDescription` exception and its frame code are gone, so `SetActionDescription`
sizes the label and its background to the text at the size chosen. In
`K1XboxHud.cpp`, `TallestDescription` remembers every action name the row has shown
this session and measures each with the description label (set as its text,
`CSWGuiText::GetIdealHeight`, the label's text put back); when the label's width or font
metrics change, all of them are measured again. The box is as tall as the tallest, never
smaller during a session, and the description is centred in it. A Mac port of either file
needs both changes together: without the first the box stays at the 50% size, without
the second the box changes height from action to action. (Until 2026-10-19 this sentence
stood after item 67, where an insertion had pushed it.)

## 66. From the pad to the mouse at once; HUD Size up to twice; HUD sliders with a pad

**Build, 2026-10-19; not yet seen in the game.**

- **The pointer guard.** `MouseIsBeingUsedK1` (`vendor/K1XboxControls.cpp`) passed over
  every pointer movement while any pad had been held in the last 1.5 s
  (`ControllerHeldRecentlyK1`, now removed), so the change from the pad to the mouse
  waited up to 1.5 s. It now passes over the pointer only while a Steam Controller or
  Steam Deck (SDL vendor 0x28de, a translator presenting one included) is held, within
  300 ms (`ControllerTypesByItselfK1`). The Mac has its own copy of the old rule:
  `PadHeldRecently` in `macos/patches/kmrp-controller/backend_sdl.cpp`, used by
  `MouseIsBeingUsed` in `prompts.cpp`; it needs the same change (item 45 above names the
  second and a half).
- **HUD Size.** `MostFactor` in `K1HudOptionsPolicy.h` is 2.0 (was 2.5): 100% draws a
  part at twice its normal size. Shared with the Xbox HUD's sizes.
- **The page's sliders.** `ShowHud` in `K1HudOptions.cpp` gives a slider no left or
  right neighbour, as the Text Size page does; the engine's left and right then move it
  and keep the focus on it.

## 67. KMRP's option pages with a pad; the entry buttons' A

**Build, 2026-10-19; not yet seen in the game.** The controller module exports four more
functions (`tools/build_controller_kpatch.py`, `functions()`): `KmrpPadInUseK1`,
`KmrpGlyphLetterK1`, `KmrpPadFocusSkipK1` (`K1NativeJoystick.cpp`) and
`KmrpPaintGraphicsEntryPromptK1` (`vendor/K1XboxControls.cpp`, Advanced Options' A badge
`kmrpa_optgfxadvn` on KMRP's two entry buttons, which are its size). KMRP's pages find
them by name (`K1OptionsPad.h`): the Text Size page has Link above the sliders and opens
on it; the HUD Size page has two tabs, a middle button for the other tab, Link above
side-by-side rows and the preview alone on the right. Both pages handle B (0x28), Y (0x2A)
and (HUD Size) X (0x29) in their input handler, keep those buttons off the pad's focus and
show glyph labels `kmr<family>rm<b|y|x>` beside their captions. A Mac port of the pages
needs its controller module to answer the same four names.

**Also (2026-10-22).** The controller module exports `KmrpControllerConfirmHeldK1` (8830c6b)
too, which the Text Size page asks: a fifth name beside the four above.

## 68. The size search finds the largest size that fits

**Build, 2026-10-19; mock tests pass, not yet seen in the game.** `KmrpTextFit::Fit`
(`src/controller-native/K1TextFitPolicy.h`, shared by both platforms) walks down from
the chosen size in steps of 1/128 to the first size that fits, then refines between it
and the step above; halving takes over only below 13% of the chosen size. It used to
halve until something fitted and bisect below that, which assumes that whatever fits at
one size fits at every smaller one. Native wrapping breaks that: the line breaker
(Windows `0x0045A2F0`) sums glyph advances truncated to whole pixels while the fit
measures the fractional drawn width, so a line the breaker fills may overrun the box by
a few pixels at one size and fit at a slightly smaller one. At 1440x1080 a subtitle
that needed four lines was drawn on one line at about a third of the text size (the
maintainer's capture); with the 2.25 `fnt_d16x16` metrics and a 1368x150 box the old
search gave 0.46 where 1.34 fits, the new one 1.34, within 3% of a 20,000-step scan in
every case simulated. The Mac has no text fitting yet (item 57; `macos/` has no copy of
the search, checked 2026-10-19); building item 57 on the shared header brings this. Test:
`testing/regression/Test-TextFitPolicy.py` (the islands case fails with the old search).

## 69. Xbox-style HUD: the name bar grows with a long name

**Build, 2026-10-19; not yet seen in the game.** In `K1XboxHud.cpp` (Mac:
`macos/patches/kmrp-controller/xbox_hud.cpp`, the block that sets `kMenuNameBackground`
and `kMenuHealthBar` from `fromName`), a name label taller than its row
(`Scale(kNameHeight, ...)`) makes the frame taller by the difference: the frame label's
fill is emptied and `KmrpXboxHudBarsK1`, at the start of the target menu's draw, draws
the top slice `kmrx_miindic1ft` (`et` for an enemy) down to row 32 of the frame's 64,
`...fm` stretched over the extra height and `...fb` under it with `LBL_MENUBG`, in the
frame label's colour and alpha, calling `ClampBoundTexture` after each (the engine's
wrap drew a dark line at both joins without it); the health bar and its background move down by the
difference; the speech box's top (`+0x1A4`) is set every frame to its layout top plus
the combat strip's shift plus the difference (`g_layout.bubbleTop`). The six textures
come from `tools/build_xbox_hud_art.py` (`target_bar_slice`, entries in `DRAWN`), so a
Mac package built from that table's `NAMES` carries them; one that lists the drawings
by hand needs the six added.

## 70. Text Size and Font: the right-hand column inside its frame

**Build, 2026-10-19; not yet seen in the game.** `K1TextOptions.cpp` places the font
choices and the previews from `LB_DESC`: it keeps their left (a 32nd of the list's width
in) and now ends them as far inside the frame's right line as they start from its left
one, the frame being 23/86 of the list's scrollbar width (`LB_DESC +0x110`) left of the
list and ending 13/86 of it short of the scrollbar's strip (the HUD Size page's
measurement, item 67). Until then they ended a 32nd of the width short of the list's
right edge, over the strip, and ran past the frame at 1440x1080. With no scrollbar width
the old rule stands. A Mac port of the page needs the same; `macos/` has no copy of it
yet (checked 2026-10-19).

## 71. Dated builds and Upgrade in the installer

**Build, 2026-10-19; Windows installer only.** The Windows installer now carries the
date of the commit it was built from (CEST, from git; `build_kmrp.ps1`, `BuildStamp`
in `src/patcher/KpmEdition.cs`), records it in the game's manifest, and compares it
with an installed KMRP's: an older one gets Restore Original and Upgrade side by
side, which reinstalls with the settings chosen now; a newer one is never replaced.
If the Mac installer replaces an existing install, it can use the same rule: the
commit's time is the same on every machine, so a Mac and a Windows build of one
commit carry one date. Details in [patcher-ui-build.md](patcher-ui-build.md), *Build
dates*.

## 72. Windows keeps its cache too, and goes two steps further

**Build, 2026-10-19; seen in the Windows test game.** `src/controller-native/K1RuntimeAssets.cpp`
now follows the Mac's `assets.cpp` design: a cache under `%LOCALAPPDATA%\KMRP\cache\<build>\`
with `store\`, `sets\<W>x<H>\` (marker beside each, built under a working name and
renamed), per-run link folders, a run lock, and the stale-cache removal. Two differences
the Mac may want:

- **The cache's folders are registered as they are** when the player's Override has none
  of their files (`OverrideHas`), and link folders are made only otherwise. A change of
  size then costs a registration and nothing else (35 ms on the maintainer's PC, against
  555 ms for linking a set's 1,271 files). The adapted party roster goes into a small
  folder of its own registered after the set, so it is searched first.
- **The blend helper is given the reference metrics** (`ReferenceTxi`: dialogfont16x16 in
  HD Original at the default text size, the TXI the build gives it,
  `build_native_assets.shared_font_txi`), so a set is the same at every text size and
  the helper's files match the build's. The Mac gives the helper whatever fonts the set
  folder holds.

Windows also keeps fitted fonts (`fonts\`, one file pair per style, font and size) and
makes the five largest display sizes ahead on a background thread (`Prebuild`); the Mac
has no runtime font fitting. (Since item 73, every size the display offers, not the five
largest.)

## 73. The art pack, and every size made at install: the Mac does the same

**Build, 2026-10-19; Windows tests pass, not yet seen in play.** The maintainer, the same
day: "Mac must adapt this new bank and whole process as well." On Windows the art left
the module: `kmrp.dll` went from 108.8 MB to 0.7 MB, and the art is a file beside it, the
art pack `kmrp-assets.pack` (55.9 MiB, against 108 MiB as XPRESS), which the installer
carries and writes into the game's `patches` folder. The installer then makes the common
files and every size the display offers that KMRP covers, with the fonts in use at each
height, before the game first starts. What the Mac needs:

- **The format is shared.** `tools/kmrp_pack.py` writes it (`write_pack(path, groups,
  objects, table_key)`, KMRPAK01, documented at the top of the file): the same groups and
  objects as the Mac's bank (KMAST002), so `macos/tools/make_kmrp_assets.py` can call it
  with its own groups, the (0, 1) and (0, 2) groups included. Small files are compressed
  together, one LZMA stream a size; large ones alone; images first through a filter
  (TGA: green taken from red and blue, then the MED predictor; DXT in a TPC: endpoints
  and indices regrouped), each undone exactly.
- **The decoder is shared.** `src/controller-native/K1AssetPack.cpp` and `.h`, plain C++
  with no system calls, and the LZMA SDK's `LzmaDec.c` (`third_party/lzma-sdk`, public
  domain, compiled as C). `assets.cpp` would read the index at start (`ReadHeader`,
  `ReadIndex`), a block when one of its files is needed (`Unpack`, then `Unfilter`), hold
  each file against its SHA-256, and keep blocks of several files unpacked while a set is
  made (Windows keeps up to 48 MiB, `Decode` and `ForgetUnpacked` in
  `K1RuntimeAssets.cpp`). Its identity, the SHA-256 of everything after its field, is the
  build's `KMRP_ASSET_BUILD`; the module refuses a pack of another build.
- **The pack beside the module.** Windows' KPM removes only the modules in `patches`, so
  the pack outlives KPM switching the patch off and on. The Mac needs a place its KPM
  equally leaves alone. Without the pack the module makes nothing and says so in its log;
  the patch alone is no longer the whole of KMRP (the maintainer's choice for the smaller
  installer, "option 2").
- **Every size made at install.** The blend helper and the game-art helpers keep their
  state in globals, so Windows runs workers, each a process: copies of the installer
  started with `--prepare-art`, each loading the module with `KMRP_PREPARE` in its
  environment (its `DllMain` then leaves the process alone) and calling its export
  `KmrpPrepareAssets(game, share, shares, step, context)`; worker 0 also makes the common
  files. Half the processor's threads, at most six. Measured on the maintainer's PC, 19
  sizes and the common files, the game on a hard disk: with the cache on the NVMe SSD 83 s
  with one worker, 33 s with four, 25 s with six, 24 s with eight; with the cache on a hard
  disk 167, 122 (two), 94 (four) and 98 s (eight). The Mac installer could run its module
  the same way in a small host program, or the helpers as programs side by side.
- **A set is made with less reading.** For a listed size the blend helper now runs first
  and the pack's files are written over its output, so only the files left to the helper
  are held against the index (`BuildSet`); nothing is read back after writing, the bytes
  having been checked when unpacked. This cut the common files from 13 to 5 s.
- **Restore Original removes the pack and the cache** (`%LOCALAPPDATA%\KMRP\cache`). An
  install over KMRP keeps the cache, so a reinstall of the same build makes nothing again.
- **What the window shows meanwhile** (the maintainer's design, 2026-10-19): the progress
  text short ("Unpacking KMRP's art…", then "7 of 19 resolutions ready…"), and the time
  left on a line of its own under the button, at its right ("37 s left"), from the
  moment the install starts and counting down a second at a time, never up: first from
  the pace measured for the kind of drive the cache is on, with a margin, then from each
  worker's own, the slowest deciding (`InstallClock`). The Mac can ask the same of its
  drive (solid-state or not). The
  art has 22 to 99% of the bar. Details in [patcher-ui-build.md](patcher-ui-build.md), *Main-window
  flow*. The Mac installer would show the same.

Tests: `testing/regression/Test-NativeAssetsBank.py` reads the pack, with
`asset_pack_harness.cpp` (portable: the test builds it with clang on the Mac);
`Test-AssetPrepare.py` the preparation (Windows); `Test-InstallerPatch.ps1` the pack and
the cache in an install and a restore.

## 74. Modern Driver Compatibility left out where it cannot run: not on the Mac

**State, 2026-10-19: n/a.** On Windows the installer now leaves K1DC out on a PC that lacks
a function its two files import (Windows 7), since there it would keep the game from
starting, and shows the Advanced Settings tile off and disabled with "Needs Windows 8"
([third-party-driver-compat.md](third-party-driver-compat.md), section 3). The Mac installs
no K1DC and no `dinput8.dll`, so there is nothing to take over. If the Mac ever offers an
option that only some systems can run, the same tile (disabled, an amber note giving the
reason, the saved choice kept) is the pattern to copy.

## 75. Marked Empty Containers, and Advanced Settings that scrolls: the Mac needs a port

**State, 2026-10-19: not on the Mac.** Windows installs ShaeMyName's K1 Marked Empty
Containers (issue 43) as a further patch, on by default: KOTOR Patch Manager 0.7.1's own
`K1MarkedEmptyContainers.kpatch`, unchanged, whose one replace hook at `0x00685E69`
(in `CSWGuiTargetActionMenu::UpdateNameLabel`, the call to `SetNameLabel`) appends
" (empty)" to the hovered object's name when it is a placeable with no items. Its 141
bytes call four functions of the Windows 1.03 executable by address
(`CSWCObject::GetServerObject`, `CSWSPlaceable::GetItemCount`, `CExoString::operator=`,
`SetNameLabel`) and read `CSWCPlaceable`'s vtable and the server placeable's `+0x324`,
which `GetItemCount` itself tests first (read as whether it has an inventory). The Mac game is another binary, so the Mac would need the same
logic at the Aspyr build's addresses, as it has its own port of High FPS Fixes
(`macos/patches/high-fps-fixes`). ShaeMyName's permission covers KMRP; a Mac port should
credit them the same way.

The Windows installer's Advanced Settings now scrolls (seven tiles, two rows in view, a
scrollbar drawn after KOTOR's list scrollbars, the wheel over the tiles): if the Mac
installer gains a seventh option it can follow the same look
([patcher-ui-build.md](patcher-ui-build.md)).

## 76. The original Xbox controls everywhere: the Mac's controller patch needs the same

**State, 2026-10-19: to do.** Issue 49, the maintainer's decision: "It should be classic
everywhere", with no second layout. Windows changed the controller module
(`src/controller-native/K1NativeJoystick.cpp`, `K1ButtonRemapPolicy.h`, `K1ButtonRemap.cpp`,
`K1ControllerLayout.cpp`, `K1XboxHud.cpp`, `vendor/K1XboxControls.cpp`) and the shared
tools; the CHANGELOG's entry of the same day has every row. Nothing of it was seen in play
on Windows yet either.

What the Mac's `macos/patches/kmrp-controller` needs, by what the shared tools now build:

- **The world buttons:** LB pause, RB switch ally (the game's ChangeChar), LT previous
  target, RT next target, X what A does, Y undo or (nothing to undo) flourish, B let go of
  the action bar or disengage on both HUDs, Start the menu screen used last
  (`CGuiInGame+0x2C`, opened with that screen's hotkey event `0xD1` plus the index; the
  Map when it holds none).
- **Remap names:** the keys and `Layout=Xbox` in `K1ButtonRemapPolicy.h`; a layout saved
  without that line is not read. The Mac shares the header if it builds from it.
- **Cue art:** the build now makes `kmrprb_party` (RB) where it made `kmrpr3_party`, and
  `LBL_KMRPX` beside Disengage is filled with `kmrpb_cmbt` (B) where it was `kmrpx_cmbt`.
  `macos/patches/kmrp-controller/cues.cpp` binds both tags and should show RB and B; the
  Mac's own party switch moves from R3 to RB in menus, and RB's menu event becomes the
  Journal's sort (`0x2B`), which was Back's.
- **Badges:** the Journal's `kmrpa_jrndone` and `kmrpy_jrnsort` became `kmrpy_jrndone`
  and `kmrprb_jrnsort` (`macos/patches/kmrp-controller/prompts.cpp` names the old ones,
  lines 200 and 201, and the Mac's Journal remaps must go); Pazaak's table has two new
  ones, `kmrpa_pzkend` and `kmrpy_pzkstand`.
- **Pazaak's table:** X plays the focused card, A End Turn, Y Stand, LB flips the focused
  card, End Turn, Stand and the flip buttons off the pad's focus, and the "X Play Hand
  Card" line made at run time (Windows offsets and addresses in K1NativeJoystick.cpp's
  Pazaak section; the Mac's are its own).
- **The pause notice:** Windows shows the button Pause is on (LB) in the standard drawing.
  The lighter RT, `kmr?rt_pause`, is still built for the Mac's `xbox_hud.cpp`
  (`kPauseGlyph`); when the Mac moves to LB too, `tools/build_controller_assets.py` can
  stop making it.

**How to check:** each row of the CHANGELOG's table with a pad; the Controller Layout
screen's captions; a layout saved before opens on the defaults.

**Also (2026-10-22), not in the text above:** LT also leaves free look; Back and R3 send
nothing in menus; RB's scroll of a computer terminal's text in a conversation keeps working
through a description of its own; the screen's eight new caption strings (see
`K1ControllerLayout.cpp`) come with it; and Pazaak's A and X swap (item 44).

## 77. KMRP's files in one folder: the Mac should do the same

**State, 2026-10-20: to do.** The maintainer: "we shouldnt clutter the folder like this".
On Windows everything of KMRP's own that was loose beside the game is now in a `KMRP`
folder in the game folder: the logs in `KMRP\logs`, the restore backups in
`KMRP\backups`, the manifests, the controller's settings (`KMRP\controller.ini`, the
remap and the HUD style) and KOTOR Patch Manager's licence in `KMRP`. The CHANGELOG's
entry of that day has the table. The installer moves an earlier install's files there
(`KmrpFolder` in `src/patcher/KmrpPatcher.cs`); the game modules write their logs there
and move an old `kmrp-controller.ini` themselves (`KmrpLogPath` and
`KmrpControllerSettingsPath` in `src/controller-native/KmrpOptions.h`).

What the Mac needs: `kmrp-mac.sh` and the Mac's modules to put their own files in the
same `KMRP` folder of the game's data folder, with the same names, and to move an
earlier install's; `macos/patches/kmrp-controller` reads its settings and writes its
logs there. **How to check:** after an install over an old one, nothing of KMRP's is
loose beside the game, and the remap and the HUD style survive.

## 78. Movies in a 16:9 area, and Bink with GDI: what applies to the Mac

**State, 2026-10-20: to check.** Windows fits every movie inside a 16:9 area of the
screen (the `.kmv` fit stub, `tools/build_movie_aspect_fit.py`): at 3440x1440 a 2.35:1
story movie is 2560x1088 where it filled the screen; a movie at least as wide or as tall
as the screen still fills it. The maintainer chose it for ultrawide screens; the Mac's movie fit should follow if it fills the height too.
Windows also makes Bink draw with GDI (`0x00405734`, `00` to `02`) for issue 48, black
startup movies on Windows 7 with a Radeon, with `original-movie-mode=1` in
`configs\kmrp.ini` as a fallback. Those two are about Windows' Bink and DirectDraw and
do not apply to the Aspyr build. The same evening Windows stopped the renderer rebuild
and screen-mode change after every movie (`RestoreResolutionFromMovie`'s 640x480 pair at
the game's size, and the start-up anti-aliasing rebuild taken before the movies): if the
Aspyr build rebuilds its renderer after a movie too, the Mac should do the same. **How to check:** a story movie on an ultrawide Mac
screen has bars on all four sides.

## 79. A Default button on the Controller Layout screen as it opens

**State, 2026-10-20: to do** (item 60's screen; `docs/controller-layout.md`, "The screen,
state by state"). The maintainer asked for a Default button on the Controller Layout
screen. On Windows the view, before Remap, now has (Y) Default, (X) Remap and (B) Back,
three across as while remapping. Default there asks first, in the box Unsaved Changes
uses, with the title "Default Layout", the lines "Every action goes back to its Xbox
button." and "Replace your saved layout?", and (A) Default and (B) Cancel; Default saves
the default layout as Save does (`Layout=Xbox` and the ten keys) and goes back to the
view. Default is grey and does nothing while there is nothing to put back, in the view
and while remapping. Nothing in `K1ButtonRemapPolicy.h` changed (`Mapping::IsDefault` was
already there); the change is the screen's (`K1ControllerLayout.cpp`: `Mode::Default`,
`canDefault`, `askDefault`, `useDefault`).

The same day the maintainer asked that the first install of 1.6 start on the classic
layout and later installs keep what is saved. Windows needed no change for it (the
CHANGELOG's entry says why); the Mac holds if its installer, like Windows', writes the
controller's settings file only when it is absent and its restore keeps a changed one.

On 2026-10-21 Back's caption "Solo mode" was seen drawn into Start's "Last menu / Close
menu" at 3440x1440; the Windows screen now moves the two apart as it lays itself out
(`layoutRemap`: Start's only as far as RT's glyph allows, Back's the rest). If the
Mac's screen centres both over their glyphs too, it needs the same.
**How to check:** with a saved layout, Default and then Default in the box gives the
Xbox layout and a grey Default; Cancel changes nothing; the two captions above the
diagram do not touch.

**Also (2026-10-22).** The controller events log gets `remap-default-ask` and
`remap-default-saved` lines.

## 80. Remapping in a table

**State, 2026-10-21: to do** (items 60 and 79; `docs/controller-layout.md`, "The
table"). The maintainer: "make it a table thats easier for the user to understand".
On Windows the Controller Layout screen still opens on the drawing, and Remap swaps it
for a table: heads Action and Button; one row per action, in `kActionNames` order, its
name and its button's prompt picture (`kmr?rm<code>`), a dot when the button is not
the action's own, an orange "?" and an orange name when it has none; under a line the
five that stay, Move, Camera, Action bar, Menus and Solo mode, grey, with the
drawing's own picture of each control and a padlock. Rows are actions, so a row is
given a button through `Mapping::Assign` in `K1ButtonRemapPolicy.h` (shared, already
tested); `Editor`'s waiting rows are the drawing's rule and are no longer used. The
table's size comes from the room between the heading's hairline and the help line
and from the names measured in the screen's font. **How to check:** Remap shows the
table in the drawing's place; A on Undo or flourish then RB gives RB on that row and
an orange "?" on Switch ally's; Close shows the drawing again.

The same day, after the maintainer's screenshot of the table: Remap opens only while a
pad answers (Windows: `KmrpPadPresentK1`, the flag the pad read sets), with Remap grey
and the help line "Connect a controller to remap its buttons." in orange otherwise; and
the "(A) Change button" hint is a footer button, first of four, (A) Change, (Y) Default,
(X) Save, (B) Close, all one size from the longest label (the view's three the same
size). **How to check:** with the pad unplugged Remap is grey and says why; while
remapping the footer shows four buttons whose labels clear their glyphs.

## 81. A round o in the Original HD Font

**State, 2026-10-21: to do** (`docs/hd-original-font.md`, "The body and light fonts'
o"). Windows' HD Original atlases now draw the o, ò ó ô õ ö and ø of the bold text and
console fonts as wide as they are tall (`tools/build_hd_original_fonts.py`, `RoundO`);
the light fonts keep their narrow o (they had the round one for a few hours). The small
menu fonts' o is a box with round corners and their letters keep the original's gaps. The atlases are in
`assets/hd-original-fonts` and the art pack is version 6: the Mac takes the same files
and pack. **How to check:** "before" in a conversation has a round o.

## 82. The HUD font's black outline

**State, 2026-10-21: to do** (`docs/hd-original-font.md`, "The HUD font's black
outline"). The HD Original `fnt_console` atlas now has a black ring round every letter,
as the original has: white letters over black, so it is the first HD atlas whose colour
is not all white. The Mac's font fitting must resample every channel of an atlas with
colour in it, as Windows' `FitAtlas` does for `fnt_galahad14`, not alpha alone, or the
ring comes out white. Same files: `assets/hd-original-fonts/fnt_console.tga` and the
art pack. The letters themselves are now drawn from geometry
(`tools/hud_font_geometry.py`, the same day): the Mac takes the same atlas. **How to
check:** the HUD's credits over a bright part of a map have a black outline, and the 4
is open at the top.

## 83. The stick's vector never longer than 1 at the engine

**State, 2026-10-21: to do** (`docs/controller-native-path.md`, "Deadzone"; issue 46).
The engine turns the character at `turnMin + (turnMax - turnMin) * (1 - r)`, r being
speed over maximum, which is negative past r = 1.11: a stick vector longer than that
turns the character away from the stick and keeps it turning (the circling and drift of
issue 46). Windows' hook that skips `Vector::Normalize` for the stick
(`NativeJoystickSkipNormalizeK1`) now scales a vector longer than 1 back to 1. The Mac's
stick path needs the same bound wherever its vector reaches the engine's `Control`
unnormalised, besides the unit-circle buffer fix of 2026-10-15. **How to check:** run on
one diagonal and switch to the other without letting go; the character turns straight
across, never the long way round.

## 84. Free look looks up and down

**State, 2026-10-21: to do** (`docs/controller-native-path.md`, "The camera"; issue 45).
In free look (input class 4, camera mode 5) the right stick's Y now drives the free-look
camera's pitch rate through the engine's own `CSWCModule` routine (Windows `0x0063FDB0`,
negated; the camera clears the rate every frame, so it is set every frame the stick is
held). The Mac's camera bridge needs the same call at its build's address. **How to
check:** press R3, push the right stick up: the view tilts up and stays there when let go.

## 85. The galaxy map navigates itself, and the action row has one lit place

**State, 2026-10-21: to do** (issues 57 and 56).
- The galaxy map (`CSWGuiInGameGalaxyMap`, dispatcher `0x00695980` on Windows) answers
  Left/Up and Right/Down itself with `PrevPlanet`/`NextPlanet`, which fill the planet's
  description. Windows now lets the D-pad's codes through on it (the list of screens that
  navigate themselves); the Mac's focus layer must stand down on it the same way.
  **How to check:** on the Ebon Hawk's galaxy map, D-pad right changes the planet's name
  and description together.
- The Xbox-style action row is drawn from the slot the HUD holds as its active control,
  even while another screen (the status summary after a fight) has the input. Drawing it
  from "the slot with the input's focus" lit the first place as well as the engine's
  slot. **How to check:** focus a slot during a fight; when "Experience Points Received"
  comes up, only that slot is lit.

**Also (2026-10-22).** With `debug-logs=2` the Xbox-style action row's state is written to
`kmrp-controller-events.log` whenever it changes (the focused slot, the target's kind and
lists), drawn from the slot the HUD holds (`KmrpHeldActionSlotK1`).

## 86. A shop's list widened by its rows' real height (issue 61)

**State, 2026-10-22: changed in `macos/patches/kmrp-assets/layout.cpp`, not built or run.**
`ListWider` took the usual row's height from the list's row-height field (`+0x368` on the
Mac), which the game writes only once rows are organised, so when a panel had just loaded it
held leftover memory: a large value made the store's list and rows far wider than the screen
(issue 61, reported on a MacBook Pro at 2336x1460). It now uses 56 at the size's scale, the
height the store's rows are built with, as Windows does since the same day. **How to check:**
build the Mac patch, open a shop (Dantooine, by the Ebon Hawk) several times: every row
inside its box with its name in view.

## 87. The galaxy map from the game's own places (issue 67)

**State, 2026-10-22: to do.** Windows writes the galaxy map again each time a size's set
is given to the game (`AdaptGalaxyMapK1`, `src/controller-native/K1RuntimeAssets.cpp`),
with every planet and Live slot where the game's 640x480 `galaxymap.gui` has it (read
through `chitin.key`), or where a mod's 640x480 `galaxymap.gui` in Override has it, on the
same spot of the galaxy. The helper, `macos/tools/kmrp-guiadapt.c` (`KmrpGalaxyMap`), is plain C like the
swoop helper, so the Mac can call it the same way from `assets.cpp` into a folder searched
before the set and the player's override (the Mac's `PlayerHas` leaves the player's file to
the game today). The Mac game's own `galaxymap.gui` is read from its resources instead of
`chitin.key`. **How to check:** the map's planets in the game's arrangement (Dantooine
above the core, Taris to its upper right); with a 640x480 `galaxymap.gui` in override, the
map still fills its frame.

## 88. The 32-slot party roster (issue 38)

**To do on the Mac** (ad968de, 2026-10-17; `src/controller-native/K1PartyRosterGui.cpp` and
`.h`, `K1PartyRosterState.h`, `AdaptPartyRosterK1` in `K1RuntimeAssets.cpp`,
`K1RuntimeLayout.cpp`, `K1NativeJoystick.cpp`, `vendor/K1XboxControls.cpp`;
`reverse-engineering/party-roster-compatibility.md`). With KOTOR Patch Manager's Party Roster
Limit 32, the party screen is built at run time from KMRP's layout when the roster patch ships
no layout, and a layout the patch ships gets KMRP's geometry, written into a folder searched
before the set and the override folder. The pad's prompts and its 4x4 navigation use the
roster's own tags and live control ids, and empty portraits are filled through the creature's
portrait getter. `macos/` has no roster code. **How to check:** with the roster patch, the
party screen fills its frame at the Mac's size, both pages of 16, and the pad walks them.

## 89. A on a message box no longer clicks the button behind it

**To check on the Mac** (6d93283, 2026-10-13; `GuardPanelEchoK1` in `K1NativeJoystick.cpp`).
A box acts on A's press and is gone before the release; the release then reached the panel
behind it and clicked its focused button (`0x006250F0`, `0x00409E60`, `0x00418750` on Windows;
seen on Party Selection's Cancel). Windows makes such a release inert on every screen. The
Mac's `GuardChargen` (`patches/kmrp-controller/gui.cpp`) drops releases only for its own
guard. **How to check:** a message box over Party Selection, A: the box closes and the party
screen stays.

## 90. The left stick walks a conversation's replies

**To check on the Mac** (d2c172a, merged 3adb77c, 2026-10-15; `FillNativeJoystickBufferK1`).
In the dialogue class the stick's latched up or down is folded into the D-pad's bits, so the
game gets events `0x31` and `0x32` with the D-pad's press, release and repeat; the real D-pad
wins while held. The Mac registers those events for the dialogue class (`native.cpp`); whether
its stick reaches them is not known. **How to check:** in a conversation, the stick moves
through the replies as the D-pad does.

## 91. The left stick on screens that navigate themselves

**To do on the Mac** (adec405, merged 49718c9, 2026-10-16). The fold of item 90, extended to
the menu class in all four directions, for the screens the engine navigates itself
(character generation's panels, the galaxy map of item 85, lists that keep their own
direction keys), where KMRP's focus layer stands down. **How to check:** character
generation and the galaxy map with the stick only.

## 92. The pad log lists SDL's pads (issue 54)

**To do on the Mac** (a7f4224, 2026-10-21; `ReadControllerK1` in `K1ControllerBackend.cpp`).
With `debug-logs=2` the events log gets SDL's list of gamepads each time it changes, and
whether a pad that appears could be opened ("SDL lists 1 gamepad(s), first id 2", "SDL
gamepad id 2 opened in slot 4: yes"). The Mac reads pads through SDL only, so the same lines
in its controller log would answer a reconnect report the same way.

## 93. The run-time asset notes only with debug logs

**To check on the Mac** (b7c8bfe, b5cbd6a, 2026-10-19). What the module made in the
background (sets, icons, game art, the swoop model) is written to `kmrp-kpm.log` only with
`debug-logs` on; a failure is always written. Since the installer makes every size, the notes
otherwise left a log in every game folder.

## 94. The stick's vector inside the unit circle, in the buffer

**Probably done on the Mac; to confirm** (cae4531, merged 22209f2, 2026-10-15; ivy's pull
request 59). `FillNativeJoystickBufferK1` scales the stick's unit vector by the rescaled
deflection instead of the raw direction, which kept a corner's length of up to 1.41. The
Mac's `StickToAxes` (`native.cpp`) appears to scale the unit vector already: read, not
measured. Item 83 is the second guard at the engine.

## 95. Glyph buttons are hints: the D-pad never lands on them

**To do on the Mac** (2026-10-22; `KmrpPadHintControlK1` in
`src/controller-native/vendor/K1XboxControls.cpp`, `ControlIsNavigableK1` in
`K1NativeJoystick.cpp`). On every screen with a glyph table, a button whose glyph is always
shown (or shown while the focus is elsewhere, FocusFallback) works by its pad button whatever
has the focus, so the pad's focus layer never chooses it; a FocusOnly glyph marks what A
presses and its buttons stay reachable. One test in the focus layer's "can this control be
focused", from the control's panel (`+0x34` on Windows) and that panel's glyph table. The
Mac's controller patch has the same tables (`prompts.cpp`) and focus layer (`gui.cpp`). The
maintainer: "they should be non-focusable with a controller. They should be visual hints."
**How to check:** on Options, Down from Exit Game wraps to the top and never lands on B
Close; on Character, X still opens Scripts while the D-pad never reaches it.

## 96. Main menu captions in the middle of their bars

**To do on the Mac** (2026-10-22; `KmrpMainMenuBars` in `macos/tools/kmrp-guiadapt.c`,
`AdaptMainMenuK1` in `src/controller-native/K1RuntimeAssets.cpp`). The main menu's five
bars in `lbl_mmenubut` are 25 rows apart and the sets' buttons 24, so the captions drifted
up and down the bars. Each time a size's set is given to the game, Windows writes the five
`mainmenu*.gui` again with each button on its bar's rows (by `LBL_MENUBG`'s rectangle),
lifted one row of the art for the engine's low captions, into the same folder as item 87's
galaxy map; a main menu layout in the player's override is left alone. The helper is the
same plain C file as item 87, so the Mac calls it from `assets.cpp` the same way. The
maintainer: "make sure the main menu buttons are centered in the art." **How to check:**
every caption sits in the middle of its bar, New Game to Quit, within a pixel or so.

## 97. HD Original's atlases drawn from KMRP's own fonts

**To do on the Mac** (2026-10-22; [fonts/README.md](../fonts/README.md),
`tools/build_hd_original_atlases.py`). The 17 atlases in `assets/hd-original-fonts` are now
drawn from the KMRP Original HD fonts in `fonts/otf` (SIL OFL 1.1): straight diagonals,
sharp corners, exact rings in © and ®; their TXI files are unchanged. The Mac's font art
must take the new TGA files (whatever copies or packs them from `assets/hd-original-fonts`),
and anything that caches the art by a version must take it again (Windows raised its art
pack to 7). **How to check:** a diagonal in the menus (a V or a W) is one clean edge at a
large size, not stepped, and every menu and dialogue line sets where it did.

## 98. Controller buttons drawn from outlines (issue 68)

**To do on the Mac** (2026-10-27; `tools/controller_glyphs.py`,
`assets/controller-glyphs/glyphs.json`, `macos/tools/kmrp-guiblend.c`). Every controller
badge is drawn from outlines at its size instead of shrinking Xelu's PNGs. For the sets the
build makes this needs nothing on the Mac: they arrive with the new badges. For a size the
build has no set for, `kmrp-guiblend.c` already holds the new drawer (`draw_glyph`) and
reads blend table version 6, so the Mac build must take the new table and helper together:
a version 5 table is refused. `testing/regression/Test-ControllerGlyphs.py` builds the
drawer on its own; on the Mac it should be built for both slices (`native_helpers.build`
does), and `Test-GuiBlendHelper.py` run as before. **How to check:** at a size the build has
no set for, a face button's letter is crisp and centred on its disc.

## 99. Controller art only in the controller (the Mac keeps it in KMRP's sets for now)

**For the Mac: nothing to do yet; one thing to know** (2026-10-27). On Windows KMRP's sets no
longer carry the controller's badges, cues or Controller Layout art: the controller patch,
which works without KMRP, draws and serves its own. The Mac has no separate controller
patch; its controller is part of KMRP's Mac patch and paints its buttons with the sets'
badges, so `macos/build.sh` passes `--controller-art` to `prepare_universal_resources.py`
and the Mac's sets are as before. Two guards: the Mac build stops if it would reuse sets
without badges (`--reuse-resources` after a Windows build), and `build_gui_blend_table.py`
stops on sets of which some carry badges and some do not. When the Mac's controller draws
its own badges at run time, as Windows' is about to, the option can go. **How to check:** a
Mac package built from fresh sets shows badges as before.

## Windows-only changes from 1.5 to 1.6 (nothing for the Mac)

| Change | Commit | Why not the Mac |
| --- | --- | --- |
| KMRP's own XPRESS decoder, no `cabinet.dll`; the game found under Wine; the DPI record restored at another path; the `%TEMP%` copy of `kmrp-sdl3.dll` | 1c40997 | Windows, Wine and Proton installers |
| XInput loaded at run time, not linked | 9fee5e4 | Windows 7 |
| A Linux pad's own key (`KEY_BACK`) not keyboard use; the Gamepad layout notice | 8f60e46 | Linux's kernel driver and Wine |
| K1 Modern Driver Compatibility 2.0.0; left out on Windows 7 | b5cbd6a, f0ca54c | the Mac ships no K1DC or `dinput8.dll` |
| Bink drawn with GDI (`0x00405734`), the `[Movies]` 640x480 mode, feature bit 8 | 4a1cd73, 3ab7a87 | Windows' Bink and DirectDraw (item 78 says what applies) |
| The NVIDIA profile's manifest path, the installer's two registry views, the installer's scrolling Advanced Settings page | b5cbd6a, f0ca54c | Windows installer and drivers |
| The KMRP Font Converter (`font-converter`) | 34dfabb | a Windows program |
| OTF fonts of the HD Original font (`tools/build_hd_original_otf.py`) | 34dfabb, 2a76531 | written to `build/`, not shipped |
| 1.5.1's version and update-check self-test | 7999a0c | Windows installer |
| The Xbox manual, typography credits, `dialogfont32x32` note | 489c4d0, 57b2aa1, 7024b9c | documents only |
