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
