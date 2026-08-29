# Experiment 005: Font Scale, List-Row Height, and Dialogue Letterbox

## Goal

Text renders at a fixed pixel size regardless of resolution, so it is
unreadably small at 3440x1440 and above. Investigate KOTOR's font-rendering
mechanics, reproduce a working scale patch, and fix whatever else breaks
once text is bigger.

## Reference material

`https://github.com/J0-o/KotorUniResPatch`, a Kotor Patch Manager patch set.
Not copied blindly: every address and byte sequence it names was
independently re-verified against our own copy of the same clean executable
(same hash, `761F9466...`) before being used. See `../font.md` for the full
technical writeup.

## Sequence

1. **Static verification of KPM's claimed addresses.** Read `manifest.toml`
   for "2x Font" — confirmed its target hash matches our `SourceHash`
   exactly. Read `font_scale_2x.cpp` for the exact struct offsets and scale
   math. Confirmed all of it against our own exe file, byte-for-byte, before
   any live session: `CAurFont::TextOutA` prologue and
   `CAurGUIStringInternal::Draw` prologue both matched exactly.
2. **Live confirmation of the CAurFontInfo layout.** A short, read-only
   x32dbg session (single-shot breakpoints only, immediately resumed after
   each capture) sampled a live `CAurFontInfo*` for a main-menu label:
   `fontHeight = baselineHeight ≈ 0.16`, `textureWidth ≈ 2.56`, spacing
   fields `0.0`. Cross-checked against `GetFontPixelHeight`'s
   `fontHeight*100+0.5` formula — consistent.
3. **Dead end: hunting for a one-time font-load hook.** Resolved the
   "safe pointer" getter at `CAurGUIStringInternal::Draw`'s `vtable+0x38`
   call to a concrete address (`0x0041EFA0`) and disassembled it, hoping to
   find where `CAurFontInfo` gets constructed so scaling could happen once
   at load time instead of every frame. It turned out to be a generic,
   compiler-generated accessor thunk reused for unrelated offsets elsewhere
   in the binary — not a loader. Abandoned this path in favor of hooking the
   render-time functions directly, same as KPM, accepting the need for a
   dedup mechanism.
4. **A debugging-workflow failure, not a game-logic one.** Attempting to
   drive the game interactively under x32dbg to sample more font instances,
   a breakpoint that fired every rendered frame (left enabled across many
   pause/resume cycles) froze the render loop long enough that the
   exclusive-fullscreen window minimized itself, and `ShowWindow`/
   `SetForegroundWindow` calls hung waiting on the frozen message loop. This
   ended live debugging as the primary workflow for the rest of the
   session — see `../../feedback_kotor_exe_safety` conventions (not tracked
   in this repo) and the standing rule adopted afterward: build a
   static-analysis-verified candidate first, test by swapping it into the
   live install, never start a new investigation with the debugger.
5. **Candidate 001: font scale only.** `tools/build_font_scale_wrapper.py`,
   `--scale 2.0`, hooking `TextOutA`/`Draw` with the 64-slot dedup table
   described in `../font.md`. Backed up the live exe (gold hash
   `D8F0EEBF...`), installed the candidate, playtested. Result: text
   correctly bigger everywhere sampled (menu, HUD, inventory, equip,
   character sheet, powers, skills, dialogue log, journal), no garbling, no
   runaway growth. One bug: save/load list rows too narrow, text from
   adjacent entries overlapping.
6. **Candidate 002: + generic list-row height.** Traced the overlap to
   `0x00417992`, a routine shared by save/load, journal, and the resolution
   popup (per KPM's own "2x List Item Height" comments). Added a third hook
   to the same `.kfs` section, reusing the font hooks' scale constant so the
   two stay proportional to each other. Verified byte-exact against the file
   before building. Playtested: overlap gone; journal and other lists using
   the same routine also got taller rows with no reported regression.
7. **New bug found: dialogue letterbox.** Playtesting surfaced two more
   symptoms: the dialogue subtitle box sometimes failed to display at all,
   and when visible, text clipped at the bottom (descenders like the tail of
   'y' cut off). Traced to KPM's separately-published "Scaled Letterbox"
   patch, which documents the actual root cause: vanilla sizes the
   letterbox bars from screen *width*, which produces an undersized bar at
   ultrawide independent of any font-scale patch.
8. **Candidate 003: + letterbox fix.** `tools/build_letterbox_scale_wrapper.py`
   reproduces all 9 of KPM's hook sites with a height-derived formula
   (`screenHeight/6`), independently byte-verified first. Two sites needed a
   trampoline into a new `.klb` section (their replacements are longer than
   what they replace); the other seven were shrink-and-NOP-pad in place. One
   trampoline (`CSWGuiDialogCinematic::SetReplies`) has an internal branch
   using a `push addr; ret` idiom to reach a different address than the
   trampoline's own resume point — traced by hand and confirmed correct
   before shipping (see `../font.md` for the exact addresses). Playtested
   across several dialogue scenes: subtitle and reply-choice text both
   render without clipping; no further non-display reports.
9. **`computer.gui` positioning bug, found separately.** Not a scaling
   issue — the computer-terminal screen's `LB_MESSAGE`/`LB_REPLIES`/
   `LBL_OBSCURE` controls were shifted left of the terminal prop's actual
   on-screen position, unrelated to font size. The user fixed it directly in
   a KOTOR GUI editor. Diffed the before/after extents: not a uniform pixel
   shift, a per-field, per-control ratio change (some controls kept their
   center while shrinking, others moved their center by ~100px) — exactly
   what `tools/transfer_gold_gui_geometry.py` already exists to propagate.
   Added `computer.gui` to `GOLD_GEOMETRY_TEMPLATES`; verified the transfer
   produces sane, fully-on-screen output at 1920x1080.

## Result

Live install (3440x1440) as of this experiment: gold delta + font-scale hook
+ list-row hook + letterbox hooks (all three exe-side fixes, chained from the
pristine gold backup, current SHA-256 `CDE41D99FA2DA70C294893A4FF47EAB9A4EAE848303695C18410B3846401170C`)
plus the corrected `computer.gui` in `Override/`. The Universal Patcher was
separately rebuilt (`dist/KOTOR_Universal_UI_Patcher.exe`,
`A018BA7FAA83F56F866303452D9ED016D9F650ABF02534550F11C96D9CE48C15`) to pick
up the `computer.gui` fix for all 48 resolutions — **that rebuild does not
include the font-scale/list-row/letterbox executable hooks**, since they are
not yet wired into `generate_gold_delta.py`'s gold reference. See
`../../docs/font-scaling.md` for the integration gap and recommended next
step.

## Go/no-go proof

- [x] Font scale patch renders correctly across menu, HUD, inventory,
      equip, character, powers, skills, dialogue log, journal.
- [x] Dedup mechanism confirmed to prevent runaway growth in real play, not
      just by code inspection.
- [x] Save/load, journal, and resolution-popup list rows no longer overlap.
- [x] Dialogue letterbox no longer clips or intermittently fails to
      display.
- [x] `computer.gui` terminal controls correctly positioned at 3440x1440;
      transfer mechanism verified structurally at one other resolution.
- [ ] Any resolution other than 3440x1440 actually play-tested with these
      font-side fixes applied.
- [ ] Font-scale/list-row/letterbox hooks folded into the Universal
      Patcher's gold delta so a fresh install at any resolution gets them
      automatically.
- [ ] A resolution-aware formula (vs. a fixed `--scale` value) for the font
      scale factor.
- [ ] `computercamera.gui` checked for the same class of positioning issue.
