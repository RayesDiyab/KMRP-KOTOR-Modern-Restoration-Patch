# KMRP 1.6: progress so far (Windows)

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It is a **progress record**,
> not release notes: 1.6 is not finished, and this lists what is on `master` so far.
> The details of each change, with addresses and measurements, are in the
> [CHANGELOG](../CHANGELOG.md) (section "Unreleased") and the documents linked from it.

## How this list was made

Compiled on 2026-10-18 from three sources, each read in full:

1. **The commits since the 1.5.1 tag.** `git log v1.5.1..8830c6b`: 14 commits. The tag is
   `7999a0c` (2026-10-12 10:36 +0200); the 1.5.1 release was published on GitHub at
   2026-10-12 08:37 UTC.
2. **The CHANGELOG's "Unreleased" section** at `8830c6b`.
3. **The GitHub issues** closed since 2026-10-11, the merged pull requests in the same
   time, and the open issues the new work answers.

**Windows only.** The macOS work since 1.5.1 is left out on purpose: three commits
(`4587552`, `9f0adbd`, `cf4b208`, the Mac App Store's game) and the macOS entries of the
CHANGELOG. So is issue #61 (a shop's item name box past the screen edge), which was reported
on a MacBook and has not been looked at on Windows.

**What "seen in play" means here.** Every item says whether someone ran it in the game,
who, and what they saw. "Built" means the module compiles and its tests pass; it says
nothing about the game.

## Where `master` stands

| | |
| --- | --- |
| Last commit | the controller remapping, slider and HD font commit after `e634603` (2026-10-18), pushed to `origin/master` |
| KMRP's own module, hooks | 13 in 1.5.1, **20** now (`src/controller-native/kotor1-native-runtime.hooks.toml`) |
| Controller patch, hooks | 36 in 1.5.1, **38** now (`tools/build_controller_kpatch.py`; `Test-ControllerKpatch.py` checks 38) |
| Installer | No 1.6 installer has been built. Testing during this work used module builds swapped into a separate test game (`build/party-roster-kpm-check/game`). |

The seven new hooks of KMRP's module:

| Address (VA) | Function | Purpose |
| --- | --- | --- |
| `0x00422CC1` | `KmrpFontMetricsLoadedK1` | An Override font's metrics are sized when the engine finishes loading its TXI (issue #63) |
| `0x0045BAC0` | `KmrpTextStringCreatedK1` | A text object is made |
| `0x0045BC70` | `KmrpTextStringDestroyedK1` | A text object is freed |
| `0x0045A2F0` | `KmrpTextStringWrapK1` | The engine wraps a text: it sees the chosen size |
| `0x0045B7A0` | `KmrpTextIdealHeightK1` | The engine asks a text's height: it sees the chosen size |
| `0x0045A857` | `KmrpTextStringDrawK1` | A text is drawn: it is fitted to its box here |
| `0x0041A3E0` | `KmrpTextListDrawK1` | A list is drawn: its rows are grown to their text |

The two new hooks of the controller patch: `0x00689410` (`KmrpXboxHudStealthK1`, Stealth in
the action row) and `0x00670FB0` (`NativeMiniGameAxisK1`, swoop racing and the turret).

## What is new

### Text size and font

| Feature | What the player gets | Commit | Issues | Seen in play |
| --- | --- | --- | --- | --- |
| **Text Size and Font page** in Graphics Options | Four sliders (menus and replies, subtitles and body, small text, HUD text), 1% steps, 50% is the game's original size; "Link Text Sizes" moves them together; three fonts: Original, Original Sharpened, New HD (since 2026-10-18: Original, (New) Original HD, the default, and (Old) HD; see the HD Original section below). Saved in `swkotor.ini`, applied live. | `8830c6b` | #51, #52 (in part), #63, #65 | Opening, sizing, Default, the grouped sliders and linking: yes, by the maintainer in the test game. Switching between the three fonts: Confirmed in play by the maintainer, 2026-10-18. |
| **Override fonts wrap at their real size** | A translation or custom font in `Override` is measured at KMRP's size before the game first wraps a line with it. | `8830c6b` | #63 | Confirmed in play by the maintainer, 2026-10-18. Also covered by mock checks (11,880 metric cases). |
| **Text fits its box** | A label, button or title that is too small for its text at the chosen size draws it at the largest size that fits. The fit is made only at draw time, so it survives a restart (the target's name over a character, the quit box). | `8830c6b` | #51, #65 | The target's name after a restart: yes, by the maintainer, 2026-10-18. The quit box: Confirmed in play by the maintainer, 2026-10-18. |
| **List rows grow with their text** | Inventory, store, workbench, skills, powers, save/load and option rows get taller instead of cutting a two-line name; scrolling and clicking follow. | `8830c6b` | #51, #65 | Inventory: yes. Load Game, store, workbench, skills and powers: Confirmed in play by the maintainer, 2026-10-18. |
| **Item, skill and power icons grow** | The game's own icon art drawn larger with the text size (x1.3 at 65%), no new art. The hex frame stretches instead of tiling into four pieces. | `8830c6b` | | Yes: inventory. |
| **Stack counts** | The count is a box the size of its digits, its lower right corner at (52, 54) of the 56 pixel hex art, inside the frame's arrow tips. Placed with the maintainer step by step. | `8830c6b` | | Yes, 2026-10-18: "looks good". |
| **Feat and power charts** | Rows, cells, feat icons and the arrows between them grow with the text size; unchanged at 50%. | `8830c6b` | | Yes, feats chart, 2026-10-18: "it works correctly". Powers chart: Confirmed in play by the maintainer, 2026-10-18. |
| **Pause notice** | Sits under the menu buttons at the top right and grows with its text. | `8830c6b` | | Moved there at the maintainer's request. Confirmed in play by the maintainer, 2026-10-18. |
| **Container panel** | Widens so "Switch To Give Item" fits with room around it. | `8830c6b` | | Yes, 2026-10-18. |
| **"Granted" feats popup** | Grows with its rows, at most to 1.5 times its size; at 50% it keeps its original size. | `8830c6b` | | Growth and the 1.5x limit: yes. The fix for "does not size down at 50%": Confirmed in play by the maintainer, 2026-10-18. |
| **Class name** in character creation | "Female Soldier" sits in the middle of its band (`classsel.gui`). | `8830c6b` | | Yes, 2026-10-18. |
| **Computer terminal scrollbar** | The reply scrollbar sits on the blue bar the terminal art draws for it, the arrows beyond its ends. | `8830c6b` | | First version yes (too short, corrected). The corrected version: Confirmed in play by the maintainer, 2026-10-18. |
| **Conversation text** | The black bars and the picture stay as they are. Inside the bottom bar, the spoken line and the reply list reach down to the screen's edge, less the same gap as above them: a two-line subtitle is no longer cut, a longer one is fitted, more replies scroll. | `8830c6b` | #65 | Yes, 2026-10-18: "its good I tested it". |

**Other resolutions:** the maintainer switched to a resolution other than 3440x1440 and
confirmed the text work there in play, 2026-10-18 (which resolution was not recorded).
Not recorded as tested: many size changes in a row.

**Rejected on the way, kept here so it is not tried again:** making the conversation's black
bars taller with the text size. It was built and installed on 2026-10-18 and reverted the same
day at the maintainer's word: at 100% the picture shrank to a third of the screen. The text's
room grows inside the bar instead (row "Conversation text" above).

### Party roster

| Feature | What the player gets | Commit | Issues | Seen in play |
| --- | --- | --- | --- | --- |
| **KPM's 32-slot Party Roster** | With KOTOR Patch Manager's released roster patch (0.7.3, which ships no layout file), the party screen is made at run time from KMRP's own layout: 16 slots a page, KMRP's look, the roster's own navigation. Portraits, brightness and page arrows repaired. | `ad968de` | #38 | Yes, by the maintainer with official KPM: portrait brightness confirmed. Save and reload, controller use and a change of resolution: **limited**. |

### Controller

| Feature | What the player gets | Commit | Issues | Seen in play |
| --- | --- | --- | --- | --- |
| **Stealth in the Xbox HUD's action row** | "Stealth" is an entry of the action row's second place whenever the game's own Stealth button would work; A switches it on and off. | `6d93283` | #50 | Yes, by the maintainer, 2026-10-13: "stealth works now". |
| **A on a message box no longer clicks behind it** | On Party Selection with a forced party, A on "You cannot cancel..." closed the box and opened it again; now it closes it. | `6d93283` | | Yes, 2026-10-13: "the popup fix works too". Other screens: Confirmed in play by the maintainer, 2026-10-18. |
| **Stick speed stays constant in the corners** | A quick tilt into a corner of the stick's gate no longer runs the character faster (1.41 times) or, at times, the wrong way. | `cae4531` (PR #59) | related to #46 | Yes, on a ROG Ally X under Proton: constant speed, the reversal not seen again. |
| **Left stick walks conversation replies** | The stick moves through replies as the D-pad does. | `d2c172a` (PR #60) | #58 | Yes, on a pad-only device. |
| **Left stick on self-navigating screens** | In character creation and similar screens the stick moves the selection as the D-pad does. | `adec405` (PR #64) | | Yes, on Linux: every character creation screen. |
| **Swoop racing and the gun turret** | The left stick steers and aims; A starts the bike, changes gear and shoots; the triggers also shoot in the turret; Start pauses. The keyboard keeps working. | `fd14f6a` | #47, #62 | Yes, by the maintainer in Steam's game: A, LT and RT each fire. Start, overlapping holds and the turret's vertical direction: Confirmed in play by the maintainer, 2026-10-18. |
| **Independent fire buttons** | Holding A or one trigger no longer swallows a new press of another. | `fd14f6a` | #62 | Confirmed in play by the maintainer, 2026-10-18. Also covered by a 512-transition regression. |
| **Swoop shift prompt** | At the shift point the race's "Space" image shows the pad's confirm glyph instead, and Space again for keyboard and mouse. Found through the live race model, so it costs nothing per frame. | `fd14f6a` | #47 | Yes, in Steam, 2026-10-16. Glyph families other than Xbox: **not played**. |
| **Swoop HUD's stray chevron** | The ninth speed segment, parked inside a wide screen's view, is parked out of view as the tenth is. Made from the player's own model file into KMRP's cache. | `8830c6b` (`macos/tools/kmrp-swoophud.c`, called by the Windows module) | #47 | Confirmed in play by the maintainer, 2026-10-18. |

**Still open from #47:** the race's "PAUSED" box is small and see-through, with its text
running over. Not looked at.

### Documentation

| Item | Commit |
| --- | --- |
| The original Xbox manual, searchable (`docs/reference/kotor-xbox-manual.pdf`), as the reference for the pad and the HUD; the tools that made its text layer in `tools/xbox-manual-ocr` | `489c4d0` |
| Text layout inventory, native text coverage, in-game text options, Override font timing | `8830c6b` |

## Issues

**Closed since 1.5.1 for work that is in 1.6:**

| Issue | Title | Work |
| --- | --- | --- |
| #38 | Party selection: support KPM's Party Roster Limit 32 | `ad968de` |
| #47 | Swoop Racing | `fd14f6a`, `8830c6b` (the "PAUSED" box is still open) |
| #50 | Controller: Stealth ability missing from action menu | `6d93283` |
| #58 | Controller: allow left stick to navigate dialogue choices | `d2c172a` (PR #60) |
| #62 | Controller: drive the swoop race and the turret from the pad | `fd14f6a` |

**Closed since 1.5.1 without a change of KMRP's:**

| Issue | Why it was closed |
| --- | --- |
| #39 | Black square after patching: the reporter's `swkotor.exe` had Windows compatibility mode on; switching it off fixed it. |
| #53 | DualSense circling: a duplicate, folded into #46, which is still open. |

**Closed on 2026-10-12 as fixed in 1.5.1, not 1.6:** #30, #31, #32, #34, #35, #36, #37, #40, #41, #42.

**Open, answered by work in 1.6 but not closed yet** (they wait for the release):

| Issue | Title | What is done |
| --- | --- | --- |
| #51 | Adjustable text scaling independent of resolution | The Text Size and Font page and the fitting work |
| #52 | Original KOTOR-style font in HD | Built, uncommitted (2026-10-18): the HD Original font, the default, replacing the "Original Sharpened" choice. Not yet seen in the game. |
| #63 | Original PC font, and Override fonts wrapping | The font choice and the Override font timing |
| #65 | Dialog text size | The subtitles slider and the conversation text room |
| #46 | Analog-stick movement conflicts | Related: the corner speed (`cae4531`). The issue's own cases (Steam Controller, DualSense, both sticks) wait for the reporter's hardware results. |

**Open and not worked on for 1.6 yet:** #66 (the player's icon on the minimap at different
resolutions), #57, #56, #54, #49, #48, #45, #44, #43, #15. (#55 is answered by the action
row below.)

### HUD Size and the action row (the commit after `8830c6b`)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **The Xbox HUD's action row as the Xbox manual's six places** | Default action, feats and skills (Stealth after the target's feats, or alone with no target), offensive Force powers, grenades or mines, the character's own Force powers, medpacs and other items together. Empty places are dim frames. One hook replaces Stealth's (`0x0068947A` for `0x00689410`), so still 38. Mouse and keyboard unchanged. | #55, #50 | Yes, by the maintainer, 2026-10-18: "works". |
| **HUD Size page** in Graphics Options | A slider for each part of each HUD, the mouse and keyboard HUD's and the controller HUD's apart, 25% to 100% (50% today's size, 100% twice since 2026-10-19, two and a half times before), each part grown about its corner and kept on the screen; Link HUD Sizes; a preview on a slate backdrop. [`hud-size-options.md`](hud-size-options.md) | | The page and the mouse and keyboard HUD at 25%, 50%, 100% (twice and 2.5 times): yes, in the test game at 3440x1440 by scripted input, screenshots reviewed by the maintainer: "Looks great". The live Xbox HUD at other sizes: **not seen** (needs a pad). |
| **The mouse and keyboard HUD placed at run time** | Placed by KMRP from a table of its 3440x1440 HUD, as the Xbox HUD is, whatever HUD layout file is loaded, so it works beside other widescreen mods. At 3440x1440 and 50% it is exactly the HUD before. The target's circle is allowed over more of the screen. | | As above. Beside another mod's HUD file and at other screen sizes: **not seen**. |

### Controller remapping, sliders and the HD font (the commit after `e634603`)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **Controller remapping** on the Controller Layout screen | The screen opens as a view with (X) Remap and (B) Back. Remap: A on a row, then the new button. Face buttons, bumpers, triggers and stick clicks can be given to any action; moving, the camera, the D-pad, Start and Back stay. No swapping: the action left without a button waits with "?", and Save works once all have one. (Y) Default, (X) Save, (B) Close with an "Unsaved Changes" question. Menus keep their buttons; the world follows the remap. Saved in `kmrp-controller.ini`. [`controller-layout.md`](controller-layout.md) | | The screen with mouse and keyboard: yes, in the test game at 3440x1440 and 1920x1080 by scripted input, screenshots sent to the maintainer. With a pad, and the remap in play: **not tested** (no virtual pad on the test machine). |
| **Sliders reach 100% with the mouse** | HUD Size and Text Size sliders dragged to the end read 100%, not 99%; the value is the one the thumb is drawn at. | | Yes, in the test game at 1920x1080 by scripted drags with the value read from memory. |
| **Disengage in the HUD Size preview** | The preview shows the combat queue's frame round Disengage, as the game draws it, with the word centred. | | Yes, at 1920x1080 by scripted input. |
| **HD font: every character, no stray lines** | The New HD Font shows the euro sign, curly quotes, ellipsis, dashes, the trade mark sign and Œ, Š, Ž as the original font does (they were boxes), and the lines after spaces in the HUD's font are gone. | #52 (the HD font) | The lines: seen before the fix at 1920x1080 and 3440x1440. After the rebuild: **not yet seen in the game**. |

### Smaller installer, every resolution ready (uncommitted, 2026-10-19)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **A 72 MiB installer** | The installer is 75.7 MB (75,675,648 bytes, the build of 2026-10-19 18:29 with K1DC 2.0.0) instead of 125.6 MiB: KMRP's art is an LZMA pack beside the module (55.9 MiB) instead of a bank inside it. KPM can still switch the patch off and on after the installer has installed it. See the CHANGELOG entry. | | Not yet. |
| **Every resolution made at install** | The installer makes KMRP's interface for every resolution the display offers before the game first starts, so the game never makes one. Measured on the maintainer's PC, 19 sizes: about 25 s with the cache on an NVMe SSD (six workers; one worker 83 s), about 95 s on a hard disk (94 s with four workers, 98 s with eight; one worker 167 s). The button counts the resolutions ready and the time left is shown under it. | | Not yet. |

### Fast starts and resolution changes (committed `b7c8bfe`, 2026-10-19)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **KMRP's files kept between runs** | A start costs KMRP 35 ms instead of 14 s; a change between prepared sizes about 1.6 s in all instead of 8.5 to 11 s. The five largest display sizes are made ahead on the first start. Layouts no longer depend on the text size. See the CHANGELOG entry. | | Yes, by the maintainer in the test game, 3440x1440 and 2560x1440, 2026-10-19: "It looks right". |

### Fitted text at the largest size (uncommitted, 2026-10-19)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **Xbox HUD name bar grows with a long name** | A target's name on two lines (or one at a large text size) gets a taller frame; the health bar and the speech box move down with it, the frame's lines unchanged. [`controller-xbox-hud.md`](controller-xbox-hud.md) | | The taller frame: seen by the maintainer at 1440x1080, 2026-10-19, with dark lines at the joins; the build that removes them: not yet. |
| **Text Size page's right column inside its frame** | The font names and previews stay inside the right-hand box's lines at every resolution. [`ingame-text-options.md`](ingame-text-options.md) | | Not yet. The overflow: seen by the maintainer at 1440x1080, 2026-10-19. |
| **Fitted text keeps the largest size that fits** | A conversation line, label or button too long for its box at the chosen size is drawn at the largest size that fits (within 3%), not at a fraction of it: at 1440x1080 some subtitles were drawn on one tiny line. `K1TextFitPolicy.h`; see the CHANGELOG entry. | #65 | Not yet. The tiny line: seen by the maintainer at 1440x1080, 2026-10-19. |

### Option pages with a pad (uncommitted, 2026-10-19)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **Text Size and HUD Size pages with a pad** | Text Size: Link above the sliders, the page opening on it, right reaching the fonts. HUD Size: tabs for the two HUDs, an X button for the other tab, Link above shorter side-by-side sliders, the preview alone on the right. Y Default, B Close (and X) from anywhere, with their glyphs; those buttons never take the pad's focus. Graphics Options' two KMRP buttons show A when focused. [`hud-size-options.md`](hud-size-options.md) | | Not yet. |

### Action description at the text size (uncommitted, 2026-10-18)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **The action's name grows with the text size** | Mouse and keyboard: the action's name in the bottom right corner is drawn at the chosen text size, its box growing to fit (it stayed at the original size). Pad: the Xbox-style HUD's action box grows with the text size and is as tall as the longest action name seen this session, so it keeps its height while scrolling and never shrinks; the name is centred in it. [`controller-xbox-hud.md`](controller-xbox-hud.md) | | Not yet. |

### HD Original font (uncommitted, 2026-10-18)

| Feature | What the player gets | Issues | Seen in play |
| --- | --- | --- | --- |
| **HD Original font, the default** | The game's own fonts redrawn sharp from Bank Gothic Medium and Helvetica at the original's sizes, spacing and weight; the menu O and o the original's own slightly wide ring; every character of the original. Text Size page: Original Font, **(New) Original HD Font** (default), **(Old) HD Font** (the former New HD); Original Sharpened is gone. Both HD fonts sharp up to 100% text at 4K. [`hd-original-font.md`](hd-original-font.md) | #52 | The menu font at 4K, reviewed by the maintainer during the work ("Looks good", before the last changes to the O and the ß); the final sheet was sent, not yet answered. In the game: **not yet seen**. |

## Keeping this up to date

Add a row when a change lands on `master`, with its commit, the issue it answers and
whether it was seen in play. When 1.6 is released, this document becomes the source for its
release notes and is then kept as the record of how 1.6 was put together.
