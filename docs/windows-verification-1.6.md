# KMRP 1.6: Windows verification journal

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: running journal, newest entry last.** It records the autonomous verification pass the
maintainer started on the night of 2026-11-02, so that results survive an interrupted session. It
says what was run, on what, and what was seen. Status of each audit finding stays in
[`cleanup-audit-1.6-disposition.md`](cleanup-audit-1.6-disposition.md), and the maintainer's own
game checks in [`gameplay-checklist-1.6.md`](gameplay-checklist-1.6.md).

A result here is one of **pass**, **fail**, **blocked** or **inconclusive**. A virtual pad test
against the running game is a real game test. It says nothing about any physical pad.

## Starting state

| What | Measured |
| --- | --- |
| Repository | `master` at `9eb5738`, equal to `origin/master`, clean |
| Last tests | On the source of `472ea9c` (later commit is documents only): quick 36, full 22, settings 2, all passed. Mac 12 and Test-BuildCache not run |
| Installed, Steam folder | `kmrp.dll` `2999EA4C5DB07FD6`, `kmrp-controller.dll` `114E6CDCCEB2ABC5`, `swkotor.exe` `34E6D971C034222A`, from installer `D339BB78` |
| Patches in that game | kmrp, kmrp-controller, high-fps-fixes, k1-marked-empty-containers, k1-modern-driver-compatibility |
| Override | 4,260 files (K1 Community Patch), 26 save folders. Not to be changed |
| Display | One NVIDIA RTX 3080, driver 32.0.16.1656, 3440x1440. No second monitor, no AMD or Intel GPU |
| Virtual pad | ViGEmBus 1.17.333.0 present. `vgamepad` 0.2.0 makes a pad from Git Bash's Python. PowerShell's Python cannot import it |
| Other tools | ffmpeg, OBS Studio (installed at `C:\Program Files\obs-studio`), x32dbg (must not attach to the Steam game on this PC) |

Audit findings still **Open** at the start: PAD-3, GFX-01. Issues open: 78, 82, 83, 87, 88, 89, 90, 91.

## Journal

### 2026-11-02, night: test setup

An isolated copy of the Steam folder is in `build/verify/steam` (ignored by Git). The game was
never started from the Steam folder in this pass. `testing/controller/live_harness.py` starts a
game folder, reads its GUI manager and movie player from outside, and presses the virtual pad, only
while the game holds the foreground. Keyboard and mouse are not sent.

### PAD-9: the A that skipped a movie reaches the game a second time

The maintainer's report: one A on the intro movie also activates New Game, sometimes. It is a new
finding, numbered here, and separate from PAD-3 until shown otherwise.

- **Measured, real game, virtual pad, `kmrp-controller.dll` with level 2 lines:** the movie reads
  the pad itself and cancels; the game does not poll during a movie, so `lastButtons` stays as it
  was. A held past the movie's end then goes out at the first poll as `pad 1000 press class 2`,
  about 140 ms after it went down: one physical press, dispatched twice.
- **Why only sometimes:** that first poll comes within about 10 ms of the main menu panel being
  added. In the runs so far the panel was not ready, so the press reached nothing.

### GFX-01 and issue 39: static results (read-only analysis, not yet a game run)

- **Measured from issue 39's own screenshots:** an all-black rectangle at exactly x=0, y=0, 1600x1200, hard edges, nothing inside it. That is the fill's size and place. It is 38.8% of 3440x1440, not the 46% the audit said.
- **The fill:** `PatBlt` at `0x00401B71`, in the thread `0x00401A30`, started from `ReInitAurora` (`0x00403885`), only on a full screen to full screen re-init. It is GDI on the screen DC, so no GL state or KMRP site touches it, and it lands on the primary monitor.
- **Not proven:** why it stays visible (leading idea: a compatibility layer or driver forces composition), and that issue 91 is the same.

### Issue 78: static results (read-only analysis, not a reproduction)

- **The scene:** module `tar_m05ab`; `tar05_synthodor` in `tar05_corpsepile` fires `k_ptar_pile_hb`, then the conversation `tar05_pile_dlg`. No Bink movie and no camera video effect: one fade, a camera shake, placed cameras. The reporter's branch ends in `k_ptar_rancorcs3`.
- **The model:** `c_rancor` is not unusual (15 bones in use, 4 weights), apart from many shadow-only meshes. K1R has no `m05ab` entry.
- **Versions:** 1.5.1 shipped K1DC 1.2.0. The Rancor skin bump branch came in K1DC 2.0.0, so the lead in the issue reply does not apply to the reporter's build. It is a separate risk for 1.6 on AMD.
- **KMRP 1.5.1:** one bounded `Sleep`, at start-up, and no hook in skin drawing. KPM and K1DC were not audited for waits. No source writes AMD, display or shader cache state.
- **What this PC cannot do:** prove an AMD fault. A driver hang remains the suspicion, from the reporter's symptoms only.

### PAD-9: result

`trial_movie_skip.py`, 40 trials each on `build/verify/steam`, virtual pad, holds of 0.1 to 0.5 s, 0.2 and 0.7 s into the last movie.

| Module | Press sent again | Past the main menu | Stalled |
| --- | --- | --- | --- |
| Without the fix | 25 (every hold of 0.22 s or more, 1 of 8 at 0.16 s) | 0 | 0 |
| With the fix | 0 | 0 | 1 |

**Pass** for the duplicate press. **Inconclusive** for New Game opening: it never opened, on either module, so the visible failure was not reproduced. Hold times of up to 2.5 s on the installed build did not open it either.

The stalled trial, and one boot after it, waited for a third movie line that did not come, 40 s, and the game was stopped. **Inconclusive**: one reading is that the skip ended the playlist; no trial tested that, and two stalls in about 42 fixed runs against none in 40 before is not enough to clear the fix. The boot now waits for the menu rather than a count.

### Combat: running game, virtual pad, fresh launch, no mouse before the pad presses

Setup: `build/verify/steam`, the fixed module, debug level 2, `Tutorial Popups=0`. Fixture saves from `build_combat_fixture.py`: Endar Spire (Sith soldier as target) and Dantooine (two creatures made hostile, so not a story fight). Mouse clicks were used only in the separate baseline runs, each its own launch.

| Check | Observed | Result |
| --- | --- | --- |
| Issue 88: Y removes the last action, first press | Two default A (queue 1, 2), then Y, Y gave 1, 0. Both fixtures | pass |
| Issue 90: Y on a fresh launch | The same runs: no mouse click first | pass |
| Issue 90: B disengages | Queue 1 to 0 on the first press, with no slot held (Endar Spire) | pass |
| Default A | One action per press, every run | pass |
| PAD-2: X and D-pad after A | Focus and the module's activation count moved. X added nothing to either queue; nor did the mouse on these slots | inconclusive |
| PAD-3: A on a slot | Two presses, `hud` activations 2. Power Blast, Critical Strike, grenade and medpack slots added nothing to the combat round list or the object's action list, for pad or mouse | inconclusive |
| Steam Input on, a physical pad, Controller only, target switching, menus in combat | Not run | blocked |

The issues' reporters ran 1.5.1 with mods. This is the closest scenario here, not their setup, so neither issue should be closed on it.

### GFX-01: running game

`gfx_layer` run, Anti Aliasing 8, `build/verify/steam`, main menu frame by ddagrab at 3440x1440. No layer, `~ WIN7RTM HIGHDPIAWARE`, and `~ DISABLEDXMAXIMIZEDWINDOWEDMODE HIGHDPIAWARE` were set on the copy's path and removed after each run. Black share inside the fill's box: 0.376, 0.339, 0.368, against 0.55 outside it, so no solid block. **Inconclusive:** not reproduced, and it was not checked that the layers took effect. KMRP 1.5.1, where the block was reported, was not run. No AMD hardware or second monitor here.

### Issues not worked in this pass

| Issue | State |
| --- | --- |
| 87 | Blocked: no bark bubble was raised in a trial. BOS:SR is not in this game. Nothing new |
| 89 | Blocked: the report names no software or symptom. ddagrab desktop capture worked in every trial above. OBS was not run |
| 91 | Not reproduced. Needs a photo: the fill is 83% of a 1080p screen, and a half-scale viewport would be 75% with the picture at lower left |
| 78 | Static results only, above. The scene was not run: no save is in the module, and this PC has no AMD card |
| 83 | Checklist: rows above only. Sections 2 to 12 were not run |
| 82 | No new work. GUI audit's 55 unreviewed groups stand |

### Correction, and PAD-3 found: A on a slot did nothing

Two earlier statements here were wrong. **The combat rows for PAD-2 and PAD-3 above are replaced by this section.**

- **"Nor did the mouse":** those clicks never reached the game. `SetCursorPos` alone moves no pointer the game reads, and the frames showed focus unmoved. With small relative moves first, a click on Force Push took the queue from 1 to 2.
- **The auto pause:** the first edit had damaged the copy's `swkotor.ini`, and `[Autopause Options]` was gone, so the world was not paused. The copy now holds the Steam file with tutorials off (the Steam file was only read). The sections survive a run, so the game did not cause the damage.

So the mouse queued and the pad did not: a defect. A level 2 probe showed the frame's event field stay 0 after the press and the icon's stay unset, and sending the same event to the icon set it to 0x27 and added one action. The game registers 0x27 on the icon only (`0x0068B9D0`), and the focus sits on the frame. `2a83b64` (2026-11-01) brought this in by replacing a direct call of the handler, so it is in the Steam folder's install and in no release.

`trial_action_slots.py`, fixed module, fresh launch, pad only, in the game's pause, three runs:

| Check | Observed | Result |
| --- | --- | --- |
| PAD-3: A on feats | Queue +1 | pass |
| PAD-3: A on Force Push, twice | +1, +1 | pass |
| PAD-3: A on grenade, own power | +1 each | pass |
| A on the defensive item | At full health the game refuses it: the caption says Full Health and nothing queues. With the character at 20 of 66, the Energy Shield entry took one action (+1). Use of the item itself was not watched to its end | pass |
| PAD-2: Down, Up right after A | Critical Strike, Flurry, Critical Strike | pass |
| PAD-2: X on the slot | +1 | pass |
| Queue limit | A fifth action is not added: four, then nothing | seen |
| Y | One off per press, 4 to 0, then the action list | pass |

Physical pads, Steam Input and Controller only were not tried.

### Around a fight, section 1 and the menus

`trial_play.py`, fixed module, virtual pad, frames read by eye.

| Check | Observed | Result |
| --- | --- | --- |
| Target switching | LT and RT moved between targets, friend and enemy, the bar's colour with them | pass |
| Menu in combat | Start opened it, RT walked Options, Equip, Inventory, Character, Abilities, Messages, Journal, Map, LT back. Layout and badges right on each | pass |
| PAD-5 | Four D-pad presses in a menu, then closed: the HUD's active control was the same address, and the frame showed the same slot | pass |
| Party | RB changed the leader. A slot the new leader lacks let the focus go | pass |
| View | Solo Mode box, Cancel focused | pass |

### PAD-4 and issue 87: not reached

A script in the copy's Override calling `BarkString`, as a module heartbeat and then as the heartbeat of 21 creatures, raised no bubble in any frame or panel list. Whether the script ran was not established. **Blocked.** The two fixture attempts are not kept.

### Installer: all-users compatibility mode

`ReportMachineWideMode` opened the machine key from a 32-bit program, so it read the 32-bit view. It now asks for the 64-bit view on a 64-bit system. Whether Windows keeps that key apart between views was not measured, and the path was not run with a real all-users value: that needs administrator rights. The installer compiles with the change; no test covers this line.

### GFX-01: full audit and two runs

Audit: [`gfx01-fill.md`](cleanup-1.6/reviews/gfx01-fill.md). It replaces the static section above where they differ. In short: the earlier run did not test the reported order. In 1.5.x the fill ran after the logos; `3ab7a87` (2026-10-20) moved it before them on master. Two players in issue 39 said turning compatibility mode off removed the block on 1.5.1 (reported).

The block is 38.8% of the screen, so a solid one would put that box near 1.0 black.

| Run, `build/verify/steam`, AA 8 | Black in the box, of the menu frame | Result |
| --- | --- | --- |
| T1: `Disable Movies=1`; no layer, Win7, Win8, `DISABLEDXMAXIMIZEDWINDOWEDMODE` | 0.16 to 0.19, over 0 to 8 s | no block |
| T2: movies on, 640 and 480 written back at `0x00403EAD` and `0x00403EB9` in memory, the 1.5.x order; no layer, Win7, Win8 | 0.16 to 0.19 | no block |
| T0: 32-bit module list | `aclayers.dll` and `apphelp.dll` load with Win7 and Win8, not without | layers took effect |

The OS version in the game's PEB stayed 10.0 under a layer, so that read proves nothing. XP mode needs elevation here and was not run. **Not reachable on this PC:** H1 stands unproven, and a present path or vendor difference (H4) cannot be settled without an AMD card or an affected player. T2 does not restore 1.5.x's DirectDraw Bink surface or forced Prefer native. Whether the fill ran in each run was not measured. The audit's fix (`jmp` at `0x00401B09`) was not made: nothing shows it cures the block.

### Issue 78: full audit

Audit: [`issue78-rancor.md`](cleanup-1.6/reviews/issue78-rancor.md). Static only, on no GPU. No step of the scene breaks a limit, and no candidate is more than suspected. **This corrects the static section above:** the pile starts with two grenades, so a player who left them gets the grenade branch whatever they added, and the reporter's branch is unknown; camera shake and rumble are in that branch only; skin meshes never cast stencil shadows; `glFinish` was swallowed already in K1DC 1.2.0. The scene was not reached in a game: no save stands in it, and the fixture needs the console.

Questions for the reporter: did they empty the pile, their `swkotor.ini`, event times, and the AMD dumps.

### Dialogue, Pazaak and the display rows

Fixed module, virtual pad, a copy of a real Taris save, frames read by eye.

| Check | Observed | Result |
| --- | --- | --- |
| 9a: dialogue, first line on | Bars, replies and spoken line in place, one press one step, into the game's next screen | pass |
| 7: Pazaak side deck, KMRP + controller | Y adds a card, count falls, ten chosen, badges beside their captions, the too-few box and the confirm box fit | pass |
| Pazaak play | X plays a hand card and its caption greys, A ends the turn, the set box works, one set played to its end | pass |
| GFX-04: AA 0, 4, 8 | `offscreen frame: on` at each, no `refused`, to a loaded save | pass |
| GFX-04: `window-drawn=1` | Log says not used, the game runs | pass |
| GFX-05 | A save load at each AA: game ran. A stale picture was not looked for beyond one frame each | partial |

Seen, not a defect by itself: on the side deck the D-pad can rest on the empty place below +5, and the confirm box opens on Cancel. Neither was compared with vanilla.

### Still not run

Section 1: PAD-4 blocked, PAD-6, PAD-8, Controller only. Sections 2, 3, 4, 5, 6, 8 and 9, the store and map rows of 9a, 10's brightness rows, 11, 12. Steam Input and physical pads. The Steam folder still has the build of `472ea9c`, without PAD-9 or the slot fix.

### Everything that needs no person: second pass

Same copy, virtual pad. **Controller only** means KMRP's patch removed from the copy's `patch_config.toml`, which ran at 800x600. All of these ran with K1 Community Patch in Override, so they are the checklist's K1CP setup too.

| Check | Observed | Result |
| --- | --- | --- |
| Settings 2, BuildCache | Passed. Mac 12 need a Mac | pass |
| PAD-9 stall | 92 more trials: 0 sent again, 0 past the menu. 3 waited for a third movie; the 2 caught both stood at the main menu, alive. A skip can end the playlist: the trial's wait, not a hang | pass |
| 2: Text Size page | Sliders, Save lighting up, Close warning, Save reaching `swkotor.ini` | pass |
| 2: Text and Icon sizes | 100/50, 50/25, 50/100, 100/75 at 3440x1440, 50/50, 100/100 at 1920x1080: Skills and Feats follow, centred, nothing outside its row | pass |
| 3: size change in Options | To 1920x1440 live, Graphics rebuilt, `swkotor.ini` updated | pass |
| 4: rumble, Enhanced | Log: ignite, hum, hit, player damage, grenade, clash. Log only; nothing felt | pass |
| 4: rumble, Original | No event in 12 s of the same fight, as its rows fire from scripts. Not a full check | partial |
| PAD-8 | Load with a blade lit: `stop all`, then no output | pass |
| Controller only: slots, Y, X, Up and Down, targets, menus, Pazaak | As with KMRP, after the two fixes in the changelog | pass |
| 7: Pazaak side deck, Controller only | Fixed, frame read | pass |

**Open, seen, not fixed:**

- Controller only, 800x600: on the Pazaak table the badges cover the first letter of Play, Flip and End, and two captions wrap.
- Controller only, 800x600: the Xbox HUD's Enemy Sighted banner overlaps the target's bar.
- Graphics Options descriptions: fixed after this pass, see the changelog. With every patch off the game itself leaves Advanced Options showing Grass.
- One frame showed a solid NVIDIA green box at the top right of the desktop, outside the game. Taken for the NVIDIA App's overlay; not traced.

**Not run, and why:** Sleheyron (its installer is a window to work through), section 8 (no scaled mod here), Rancor (the fixture needs the console, and a keyboard), OBS, PAD-6, the Container, a store, the map, brightness, section 11. Mac tests, physical pads and Steam Input need the hardware.

### Issue 89: OBS

The reporter (Discord, 2026-11-01): OBS failed with desktop capture and game capture, either not recording the game or crashing, and they say it began after applying KMRP. Their KMRP version and setup are still unconfirmed.

OBS 30.0.2, RTX 3080, `build/verify/steam`, 3440x1440, game capture on any fullscreen application, OBS started before the game, the movies left to play, 45 s at the menu. A hook retried through the movies in every setup, and attached at the menu.

| Setup | Runs | Game crashed |
| --- | --- | --- |
| No KMRP, no patches, no KPM loader (the game's own `binkw32.dll`) | 3 | 3, exit `0xC0000005`, 6 s after the menu |
| KPM loader, no patches | 4 | 3 |
| KMRP + controller | 4 | 3 (`0xC0000005`, once `0xC0000409`) |
| The same, Bink set back to DirectDraw in memory | 6 | 3 |
| KMRP + controller, `Disable Movies=1` | 4 | 0 |

With the movies skipped at once, game capture recorded menu, loading and play with no crash (1 run). Desktop capture recorded with the movies played (1 run on master).

**Reading:** on this PC the crash is OBS game capture's hook landing after it retried through the movies, and it needs no KMRP code, so KMRP's movie changes do not cause it. Why the retries end in a crash was not traced. Windows logged no crash event. **Not shown:** that the reporter's failure is this one. They also report desktop capture failing, which did not happen here, and 1.5.1 itself was not run. Override held K1 Community Patch in every run. No AMD test.

### Issue 89: where the crash is, and newer OBS

A debugger attached at the menu caught the access violation on OBS's own thread: `ntdll` at `+68E26`, writing near address 0x14, called from `graphics-hook32.dll` through `d3d11.dll`, unpatched game. No KOTOR or KMRP code was executing there. (Attached from the movies on, the crash did not happen.)

| OBS | `Use anti-cheat compatibility hook` | Game | Result |
| --- | --- | --- | --- |
| 30.0.2 | off | unpatched | game crashed, 3 of 3 |
| 30.0.2 | off | KMRP | game crashed, 1 of 3 |
| 33.0.1 portable | on (OBS's default) | either | OBS itself closed after its first hook attempt, 8 of 8, code 0 where read. Game unharmed, nothing captured |
| 33.0.1 portable | off | unpatched | captured, no crash, 3 of 3 |
| 33.0.1 portable | off | KMRP | captured, no crash, 3 of 3 |

**Caveat on the OBS 33 runs with the setting on:** that portable copy could not update the shared 32-bit hook in `C:\ProgramData\obs-studio-hook` (error 32), so with the setting on it used the January 2024 hook. A clean OBS 33 install may behave differently. No patch for KOTOR and OBS was found online. No game-side fix was made: the fault is in OBS's hook, and OBS 33 with the setting off works.

**How to turn the setting off in OBS:**

1. Close KOTOR.
2. In OBS, look at the **Sources** panel, at the bottom of the main window.
3. If there is no Game Capture source yet, click **+** under that panel, choose **Game Capture**, and click **OK** on the name window.
4. Double-click the Game Capture source to open its Properties window. Right-clicking it and choosing **Properties** does the same.
5. Leave **Mode** on **Capture any fullscreen application**.
6. Clear the check box **Use anti-cheat compatibility hook**.
7. Click **OK**, then start KOTOR.

The setting belongs to that one source, and it is on by default, so every new Game Capture source needs the same change. Each OBS scene collection keeps its own sources.

The labels were read from OBS 33.0.1's language files. OBS's source code shows the check box in every mode, on 30.0.2 and on 31.0.0. The trials above turned it off by writing `"anti_cheat_hook": false` into the scene file, not by clicking through this window, so these steps have not been followed by hand.

### Issue 78: the Rancor scene, run

The scene ran to its end on the copy: 3440x1440, AA 8, V-Sync 1, RTX 3080, KMRP + controller + K1DC + High FPS Fixes, master plus the fixes below only in the later runs. No freeze, crash, or Event ID 4101, 117 or 141. **Nothing here says anything about AMD**, and 1.5.1 with K1DC 1.2.0 was not run.

How it was reached, none of it committed: a Dantooine save with no Taris modules stored, one creature's heartbeat script in a copy of it pointed at a small compiled script that gives the odor item and starts `tar_m05ab` at `tar05_wpparty`. A quick save there, the player moved beside the pile, and `TAR_RANCOREATING` cleared, as that character had done the quest. The script and the item were taken out of the copy after. The pile opened and took the odor by pad.

| Branch | Module scripts | Runs | Result |
| --- | --- | --- | --- |
| Grenade: choke, explosion, death, journal and XP | Vanilla rims | 3 | Ran to the end, game went on |
| Grenade | K1CP's `tar_m05ab.mod` | 2 | Ran to the end, game went on |
| No grenade: Rancor lives, goes home, hostile | Vanilla rims | 1 | Ran to the end, game went on |
| No grenade | K1CP's `tar_m05ab.mod` | 1 | Ran to the end, game went on |

Two runs labelled no grenade were really the grenade branch: the script that took the grenades out worked on a copy of the list, as PyKotor's `get_list` returns one. Caught from the video, and the counts above are by what happened.

K1DC with `log=debug` and `frames=on`, one no-grenade run: 36.8 to 120.0 frames a second, 120 the V-Sync cap, so candidate 2 of the audit did not show here with V-Sync on. Not tried with V-Sync off. No GL error in the scene: its three, `soft_shadow` and `glow`, came in the first 12 seconds, before it. These runs did not list shader variants (T2) or time soft shadows (T5).

### Brightness: a black screen, found and fixed

Moving the slider one step in Graphics Options, AA 8: the captured frame went to 0.0 mean brightness, in the first run and each run after, and back to 19.2 on returning to the default. Only with K1DC and the offscreen frame both on, and only with anti-aliasing.

| Setup, one step left of default | Mean: start, left |
| --- | --- |
| Before the fix, full, AA 8 | 19.2, 0.0 |
| `window-drawn=1` | 19.2, 18.9 |
| K1DC out | 19.2, 19.2 (the gamma ramp, which a capture does not show) |
| Controller only | 25.8, 25.8 |
| Full, AA 0 | 19.2, 18.9 |
| **After the fix, full, AA 8** | **19.2, 18.9, then 18.5 on the next step** |

K1DC logged `gl error site=brightness raised=during errors=INVALID_OPERATION` before the fix and not after. After it, 12 steps down 15.0, 24 down 12.4, 40 up 27.9, and the change stayed with the panel closed. What a person sees was not looked at: these are captures. Whether the value is saved was not checked: the test ended the game by killing it, and `swkotor.ini` still said 57. `gl error site=soft_shadow raised=during` at start-up with AA 8 stayed, and was not traced.

### The rest of the list

| Check | Observed | Result |
| --- | --- | --- |
| Container by pad | Opened on the Rancor's pile, Give and Get lists, X switches, A gives, B closes | pass |
| 5: Container after size changes | Text Size 100: 1920x1080, then 1920x1200, then 1680x1050 in one session: buttons inside, panel not growing | pass, after the badge fix |
| 9a store | Dantooine's store by pad: Buy 807 to 767 to 727, Sell up to 747, X switches, B closes, descriptions change | pass |
| 9a map | Moved between notes, A opens Party Selection, B back | pass |
| 10 brightness | Above | pass after the fix |
| PAD-6 | RB held through Options, a setting changed and changed back, menu closed, released: one press, one release, and the next press works | pass, virtual pad |
| 4: Original rumble | The Rancor's death: 178 motor lines, ramped down, `muted` at the end. Log only | pass |
| 7, 800x600, Controller only: Enemy Sighted | Ran over the name bar. Now under it at its width, in two lines | fixed; seen at 800x600 and 1280x720 by frame |
| 800x600, Controller only: Pazaak table | Still there: the badges cover the first letter of Play and End, Flip's too, and Play and Flip wrap | open, cosmetic, this size only |

Regression: 62 passed and 12 skipped with the brightness and Container fixes (the default run, not settings, Mac or build). Quick 38 passed on the final source, banner included; the full group was not repeated after the banner. Mac 12 not run. The Steam folder and the `dist` installer have none of these fixes.

### Regression on the final source

On `0825f2d` with documents only changed since: quick 37 and full 22, 59 passed. Mac 12 and Test-BuildCache not run. The Steam folder was not touched in this pass and still has the build of `472ea9c`, without the PAD-9 fix.
