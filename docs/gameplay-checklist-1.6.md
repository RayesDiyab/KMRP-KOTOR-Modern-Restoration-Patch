# KMRP 1.6: what only the game can check

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: working checklist for the maintainer.** Every fix below passed whatever could be checked
without the game, and none has been seen in one. A fix is not done until its row here is ticked.
The findings' full record is [`cleanup-audit-1.6-disposition.md`](cleanup-audit-1.6-disposition.md).

## Before you start

Install the latest `dist` build with Upgrade, so your settings stay. Turn debug logs on in Advanced
Settings: several steps read `KMRP\logs`. The five setups the checks refer to:

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
| [ ] | PAD-3 | On a focused action slot, press A once and watch the queue. | One action queued. Not fixed, only measured: if it queues two, tell me. | |
| [ ] | PAD-4 | Stand where a character barks during a fight: a BOS:SR fight, or any script bark. While the bubble shows, press D-pad, A and B. | The action bar keeps working. A does not fall back to a plain attack, and B does not disengage. | Vanilla for comparison |
| [ ] | PAD-5 | In a menu press D-pad a few times, close it, look at the action bar. | The bar has not moved. | |
| [ ] | PAD-6 | Open Options, change a control setting while holding a button, close, release the button. | No second press from the held button. The next press of it works. | |
| [ ] | PAD-7 | Start a movie while the motors run, for example a cutscene right after being hit. | The motors stop. Not fixed, only suspected: if they hold through it, tell me. | |
| [ ] | PAD-8 | With a lightsaber lit, load another save, then a save with no saber lit. | No hum after the load. | |

## 2. Abilities and icon sizes (GUI-2, decision 4)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Options, Text Size page: Text 50, Icon Size 50. Open Abilities, Skills tab. | As before this cycle. |
| [ ] | Text 100, Icon 50. Open Skills. | Text larger. Icons as Icon Size says, centred on their rows. |
| [ ] | Text 50, Icon 25, then 75, then 100, in one session without restarting. Open Skills each time. | Icons follow the slider each time, centred, sharp at 50. |
| [ ] | Text 100, Icon 75. Open Skills, then Feats and Powers. | Icons follow the slider. Nothing outside its row. |
| [ ] | Repeat with **K1CP**. | The same. |

## 3. Interface at a size change

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | GUI-3 | Options, Graphics: change resolution and back, with a mod's `.gui` in Override (**K1CP**, **Sleheyron**). | No freeze, no half-laid-out screen. `kmrp-kpm.log` may name a skipped control. |
| [ ] | GUI-4 | Open a container so its list widens. Change resolution with the screen in use, then open it again. | Buttons stay inside the panel. Not fixed yet if it fails: tell me. |
| [ ] | THR-1 | Fresh launch, KMRP's patch alone. From the main menu open Options, HUD Size. | The page opens without the 0.4 s stall of the first opening. |
| [ ] | GUI-5 | Nothing to do unless a set's icons were ever missing. | If `kmrp-kpm.log` warns about icons, the next start tries again. |

## 3b. Badges beside their captions (decision 6)

**Controller only** at 1920x1080 and 3440x1440: each badge sits beside its caption, not far off to
the left. With **KMRP + controller** they should look as they did before.

| Done | Screen | Buttons |
| --- | --- | --- |
| [ ] | Galaxy map | Travel, Cancel |
| [ ] | Name a save | OK, Cancel |
| [ ] | Pazaak card selection | Add card, Play |

## 3c. A mod's already-scaled screen (decision 5)

| Done | Steps | Expected |
| --- | --- | --- |
| [ ] | Any mod whose `.gui` is already made for your size, for example a Scaled KOTOR screen, at that size. | Exactly as its author made it, gutters and list heights included. At another size it is converted, and the log says so. |

## 4. Display and drivers

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | GFX-04 | Start normally on your RTX 3080 with AA 0, 4 and 8. | `kmrp-kpm.log` says `offscreen frame: on`, with no `refused`. |
| [ ] | GFX-04 | Add `[Offscreen]` and `window-drawn=1` to `configs\kmrp.ini`. Start the game. Remove it after. | The log says not used. The game runs. On your layered setup the old flash may come back. |
| [ ] | GFX-05 | Play through a save load, a movie and a menu with AA 8. | No frozen or stale picture. |
| [ ] | GFX-03 | K1DC on, AA 8: change brightness in Options. | Brightness applies as with AA 0. |
| [ ] | GFX-04 | On an AMD or Intel PC, if you have one: AA 0, 4, 8. | Picture shows. If a driver refuses, the log says so and the game draws normally. |
| [ ] | GFX-01 | Issues 39 and 91 need an affected player. Send me issue 39's screenshot or the block's size. | Decides whether the game's own 1600x1200 black fill is the cause. Not fixed. |
| [ ] | Bundled K1DC | Install from this build with Modern Driver Compatibility on, on a folder that has never had the standalone route. | Game starts. Brightness works. |

## 5. Installer on your real game

The automated tests cover these on throwaway folders. These rows are the real Steam folder.

| Done | Finding | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | INS-01 | Change volume, Text Size, HUD Size and resolution in the game. Run Upgrade. | All of them survive. |
| [ ] | INS-01 | Restore Original, then look at `swkotor.ini`. | The game's own options stay. `[KMRP ...]` sections gone. |
| [ ] | INS-06 | With KOTOR running, press Upgrade. | About two seconds, then "KOTOR is running from this folder". |
| [ ] | INS-07 | Run Steam's Verify integrity. Open the installer. | "Repair needed", and the button says Repair. It repairs. |
| [ ] | INS-08 | Only if you want to: rename `binkw32Hooked.dll`, Restore Original, rename it back, Verify. | An error naming `binkw32.dll`, not "restored successfully". |

## 6. Mods

| Done | Setup | Steps | Expected |
| --- | --- | --- | --- |
| [ ] | **K1CP** | New game to the first fight, inventory, map, a store. | Nothing lost, and the Speed blur stays absent as K1CP makes it. |
| [ ] | **Sleheyron** | Reach a Sleheyron module, open the map and a dialogue. | As in its own install. |
| [ ] | **Controller only** | Run sections 1 and 3's rows that say so, then a dialogue, a store and Pazaak. | Badges fit the game's own layout, no KMRP files needed. |

## 7. What cannot be checked on your PC

| Check | Needs |
| --- | --- |
| Linux: the running-game check, art cache removal, Repair in the AppImage window | a Linux or Steam Deck machine |
| Proton: the offscreen frame, Proton's `opengl32` | the same |
| Windows 7 and 8: K1DC's standalone route, the rename used for the manifest | those systems |
| A full disk during install | a small volume |
| Mac | waits for the port |
