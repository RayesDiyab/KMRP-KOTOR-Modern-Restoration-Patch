# KMRP 1.6: what only the game can check

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: working checklist for the maintainer.** Every fix below passed whatever could be checked
without the game, and none has been seen in one. A fix is not done until its row here is ticked.
The findings' full record is [`cleanup-audit-1.6-disposition.md`](cleanup-audit-1.6-disposition.md).

## Before you start

**Installed in the Steam folder on 2026-11-02:** installer `D339BB78...`, from commit `472ea9c`, `kmrp.dll`
`2999EA4C...`, `kmrp-controller.dll` `114E6CDC...`, debug logs on. A later build needs its own install.
What it replaced is in `KMRP\backups\before-s8-2026-11-02`, the builds before that in
`before-movie-log-2026-11-02`, `before-save-fixes-2026-11-01`, `before-save-button-2026-11-01` and
`before-font-refit-2026-11-01`, and what the audit build replaced in `before-audit-build-2026-11-01`,
each with `hashes.txt`.

**Check first:** the audit build's install also moved K1 Modern Driver Compatibility from the standalone 2.0.0
(`dinput8.dll` and an `.asi`) to the bundled 2.0.1 patch, as this build is meant to. That route has
never been seen beside the offscreen frame. So start by launching the game and opening a save, with
the `Bundled K1DC` row and GFX-03 in section 10. If it does not start, stop there and tell me.

Otherwise install the latest `dist` build with Upgrade, so your settings stay. Turn debug logs on in
Advanced Settings: several steps read `KMRP\logs`. The five setups the checks refer to:

| Setup | What it is |
| --- | --- |
| **Vanilla** | a clean game, no KMRP, for comparing behaviour |
| **Controller only** | the controller patch alone, KMRP's patch off |
| **KMRP + controller** | the default install |
| **K1CP** | KMRP + controller with K1 Community Patch in Override (your Steam folder) |
| **Sleheyron** | KMRP + controller with the Sleheyron mod |

Unless a row says otherwise, use **KMRP + controller** at 3440x1440.

## 1. Controller in combat (issues 87, 88, 90)

Fresh launch for each of these, pad only: no mouse click since the game started. A mouse click
hides the bug these fixed.

| Done | Finding | Steps | Expected | Also try |
| --- | --- | --- | --- | --- |
| [ ] | PAD-1 | Load a save near enemies. Enter combat. Queue two actions with A. Press Y. | The last queued action goes, first press. Press Y again with nothing queued: the character flourishes the weapon. | Controller only |
| [ ] | PAD-1 | In combat, queue two actions and press B. | The whole queue clears and the character disengages, first press. | Controller only |
| [ ] | PAD-2 | In combat, on an action slot: press A, release, then D-pad Up, D-pad Down, then X. | Up and Down cycle that slot's options straight after A. X uses the slot. No need to move focus away and back. | Controller only |
| [ ] | PAD-3 | On a focused action slot, press A once and watch the queue. | One action queued. Fixed 2026-11-02: since 2026-11-01 A here did nothing. Seen with the virtual pad; a physical pad is the check left. | |
| [ ] | PAD-4 | Stand where a character barks during a fight: a BOS:SR fight, or any script bark. While the bubble shows, press D-pad, A and B. | The action bar keeps working. A does not fall back to a plain attack, and B does not disengage. | Vanilla for comparison |
| [ ] | PAD-5 | In a menu press D-pad a few times, close it, look at the action bar. | The bar has not moved. | |
| [ ] | PAD-6 | Open Options, change a control setting while holding a button, close, release the button. | No second press from the held button. The next press of it works. | |
| [ ] | PAD-8 | With a lightsaber lit, load another save, then a save with no saber lit. | No hum after the load. | |

## 2. Abilities and icon sizes (GUI-2, decision 4)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Options, Text Size page: Text 50, Icon Size 50. Open Abilities, Skills tab. | As before this cycle. |
| [ ] | Text 100, Icon 50. Open Skills. | Text larger. Icons as Icon Size says, centred on their rows. |
| [x] | Save, greyed (its look seen by the maintainer, 2026-11-01). Open Options, Text Size page and change nothing. | Save's caption and frame are dimmed, its caption level with Default's and Close's, clicking it does nothing, and a pad shows no X on it. Close closes at once. |
| [ ] | Save, HD Font. Drag a slider up. Then press Save, and try X on a pad. | The slider stays smooth and the text a little soft. Save lights up, shows "Saving...", then goes dim with the text fully sharp. At a size never used before that takes a second or so. |
| [x] | Close warning (its look seen by the maintainer, 2026-11-01). Change something and press Close, or B. | "You have unsaved changes." sized to fit. Save and Don't Save are one width with room around their text, and Save has the focus and the pad's A. |
| [ ] | In that box press Don't Save (B). Reopen the page, and restart the game. | Sizes, font, link and icons are all as they were saved, and the text is sharp. |
| [ ] | Change something, Close, then Save (A). Restart the game. | The page closes after saving, and the change is still there after the restart. |
| [ ] | Try a font without saving: pick Original Font, then Close and Don't Save. | HD Font is back, sharp. |
| [ ] | All of the above from the main menu and from in a game, and at a second resolution. | The same. The box is centred each time. |
| [ ] | Text 50, Icon 25, then 75, then 100, in one session without restarting. Open Skills each time. | Icons follow the slider each time, centred, sharp at 50. |
| [ ] | Text 100, Icon 75. Open Skills, then Feats and Powers. | Icons follow the slider. Nothing outside its row. |
| [ ] | Repeat with **K1CP**. | The same. |

## 3. Interface at a size change

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | GUI-3 | Options, Graphics: change resolution and back, with a mod's `.gui` in Override (**K1CP**, **Sleheyron**). | No freeze, no half-laid-out screen. `kmrp-kpm.log` may name a skipped control. |
| [ ] | THR-1 | Fresh launch, KMRP's patch alone. From the main menu open Options, HUD Size. | The page opens without the 0.4 s stall of the first opening. |
| [ ] | GUI-5 | Nothing to do unless a set's icons were ever missing. | If `kmrp-kpm.log` warns about icons, the next start tries again. |

## 4. Rumble (audit R-1, PAD-7)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | With a pad, Enhanced haptics on, then Original: ignite a saber, throw a grenade near an enemy, take a hit. | Rumble as before. KMRP no longer gives the engine a pattern table, which nothing read. |
| [ ] | PAD-7. With a held rumble going (a saber lit with Saber Hum on, or an explosion), let a cutscene movie start, for example by leaving a planet in the Ebon Hawk. | The motors stop as the movie starts, and rumble works after it. |

## 5. The Container after a change of size (audit GUI-4)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Open a container at 1920x1080 with a large Text Size. Close it, change the resolution in Options to another size, and open a container again. Change once more. | The three buttons stay inside the panel, "Switch To Give Item" fits, and the panel does not grow with each change. |

## 6. Pictures after the lookup change (audit THR-5)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | With the Xbox HUD on: play a few minutes of combat, open the Controller Layout, change the pad family, and change the resolution once. | No white frame or badge that stays white, and no picture of the wrong family or size. |

## 7. Badges beside their captions (decision 6)

**Controller only** at 1920x1080 and 3440x1440: each badge sits beside its caption, not far off to
the left. With **KMRP + controller** they should look as they did before.

| Done | Screen | Buttons |
| --- | --- | --- |
| [ ] | Galaxy map | Travel, Cancel |
| [ ] | Name a save | OK, Cancel |
| [ ] | Pazaak card selection | Add card, Play |

## 8. A mod's already-scaled screen (decision 5)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Any mod whose `.gui` is already made for your size, for example a Scaled KOTOR screen, at that size. | Exactly as its author made it, gutters and list heights included. At another size it is converted, and the log says so. |

## 9. Things to look out for (no fix made)

| Done | Steps | What it decides |
| --- | --- | --- |
| [ ] | GUI-9. Controller on, on a screen with badges: change Text Size up and down, go back to the screen. | If a badge stands too far from or over its caption, the finding is real and gets its fix. |
| [ ] | GFX-06. Only if convenient: Anti-aliasing 8, `Debug` level 2, two minutes of play, then look for the line counting reads against swaps in `KMRP\logs\kmrp-kpm.log`. | Many reads a swap would make it worth resolving only the part read. |

## 9a. Text after the engine clean-up (audit E-1, E-2)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Main menu, a dialogue with subtitles, a store, the journal, the map, a save list. | All text as before, in both fonts, with no crash on any of it. |
| [ ] | A dialogue from its first line to its end, with bars at the top and bottom. | The bars and the replies stand where they did. |

## 10. Display and drivers

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | GFX-04 | Start normally on your RTX 3080 with AA 0, 4 and 8. | `kmrp-kpm.log` says `offscreen frame: on`, with no `refused`. |
| [ ] | GFX-04 | Add `[Offscreen]` and `window-drawn=1` to `configs\kmrp.ini`. Start the game. Remove it after. | The log says not used. The game runs. On your layered setup the old flash may come back. |
| [ ] | GFX-05 | Play through a save load, a movie and a menu with AA 8. | No frozen or stale picture. |
| [ ] | GFX-03 | K1DC on, AA 8: change brightness in Options. | Brightness applies as with AA 0. |
| [ ] | GFX-04 | On an AMD or Intel PC, if you have one: AA 0, 4, 8. | Picture shows. If a driver refuses, the log says so and the game draws normally. |
| [ ] | GFX-01 | Issues 39 and 91 need an affected player. Send me issue 39's screenshot or the block's size. | Decides whether the game's own 1600x1200 black fill is the cause. Not fixed. |
| [ ] | Bundled K1DC | The Steam folder, as installed (see the top). Change brightness. | Brightness works. `KMRP\logs` has no K1DC errors. Starting, loading a save and the menus were seen working on 2026-11-01. |

## 11. Installer on your real game

The automated tests cover these on throwaway folders. These rows are the real Steam folder.

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | INS-01 | Change volume, Text Size, HUD Size and resolution in the game. Run Upgrade. | All of them survive. The install of 2026-11-01 left `swkotor.ini` byte-identical, but its options had not been changed first. |
| [ ] | INS-01 | Restore Original, then look at `swkotor.ini`. | The game's own options stay. `[KMRP ...]` sections gone. |
| [ ] | INS-06 | With KOTOR running, press Upgrade. | About two seconds, then "KOTOR is running from this folder". |
| [ ] | INS-07 | Run Steam's Verify integrity. Open the installer. | "Repair needed", and the button says Repair. It repairs. |
| [ ] | INS-08 | Only if you want to: rename `binkw32Hooked.dll`, Restore Original, rename it back, Verify. | An error naming `binkw32.dll`, not "restored successfully". |

## 12. Mods

| Done | Setup | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | **K1CP** | New game to the first fight, inventory, map, a store. | Nothing lost, and the Speed blur stays absent as K1CP makes it. |
| [ ] | **Sleheyron** | Reach a Sleheyron module, open the map and a dialogue. | As in its own install. |
| [ ] | **Controller only** | Run sections 1 and 3's rows that say so, then a dialogue, a store and Pazaak. | Badges fit the game's own layout, no KMRP files needed. |

## 13. What cannot be checked on your PC

| Check | Needs |
| --- | --- |
| Linux: the running-game check, art cache removal, Repair in the AppImage window | a Linux or Steam Deck machine |
| Proton: the offscreen frame, Proton's `opengl32` | the same |
| Windows 7 and 8: K1DC's standalone route, the rename used for the manifest | those systems |
| A full disk during install | a small volume |
| Mac | waits for the port |
