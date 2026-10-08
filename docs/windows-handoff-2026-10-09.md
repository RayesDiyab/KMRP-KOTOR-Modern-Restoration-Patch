# Handoff to the Windows side, 2026-10-09

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It says what was built
> and seen on the Mac, and marks what is a guess about Windows as a guess.

What changed on the Mac on 2026-10-08 and 2026-10-09 that Windows has in the same form, and
what each asks of the Windows build. Written on the Mac. **Nothing in it was run on
Windows**, and no Windows source or Windows document was edited. The details of each item,
with addresses and the Mac's code, are in the tracker,
[windows-changes-from-macos.md](windows-changes-from-macos.md), under the item number given;
this file is the list. Mac state: `master` at the commit that adds this file.

All of it came from the maintainer playing the Mac build on a 4K television (3840x2160 at
60 Hz) with a PlayStation pad, and from his photographs.

Each item is one of:

- **port**: shared behaviour or shared code; Windows has the same fault as far as the code
  shows;
- **check**: may not show on Windows; worth one look;
- **Mac only**: nothing to do, listed so that nobody wonders.

## Summary

| # | Change | For Windows | Tracker |
| --- | --- | --- | --- |
| 1 | Controller badges are never less than three quarters of their button's height | **port** | item 23 |
| 2 | The message popup's widening step follows the screen | **port** | item 24 |
| 3 | The combat-mode message's picture, gaps and widths come from the font | **port** | item 25 |
| 4 | The store row's stack count sits in the icon's lower right corner, as the inventory's | **port** | item 26 |
| 5 | High FPS Fixes: particle fountains emit what the game emits at 60 frames a second | **check** | below |
| 6 | Anti-aliasing off on a 4K display | **check** | below |
| 7 | The pointer after a change of resolution in the game | **Mac only** | below |
| 8 | Still open from 2026-10-08: items 20 to 22 seen in the game on Windows | **check** | items 20 to 22 |

## 1. Badges: a least size (port)

The rule of master `843320b`, as large as fits the button both ways, leaves a badge whose
texture is a long strip a fraction of its button's height. The container's three buttons were
made for a fill area of 273x10; in KMRP's sets their badges came out a quarter of the
button's height, at every resolution. The Mac took the rule on 2026-10-08 and has the same
table, so Windows has this too. Repair: after the fit, never less than three quarters of the
area's height (three lines at the end of `K1UniformBadge`). The main menu's Quit, which the
rule was made for, is at 0.79 and is not touched. **Seen right on the Mac at 3840x2160.**

## 2. The popup's widening step (port)

`CSWGuiMessageBox::FixMessageLabel` (Windows `0x006253A0`) grows a box whose text does not
fit by 40 of width and one line of height per pass. The caps and the line follow the screen;
the 40 never did. At 4K a long text makes a tall, narrow box. The Mac writes
`40 * height / 720` there. **Seen right on the Mac at 3840x2160** (a long tutorial text).

## 3. The combat-mode message (port)

`kButtonSize = 22` and `kButtonGap = 9` in `K1XboxHud.cpp`, made beside a 16 px font, and
widths from the engine's measure, to the nearest 10. At 4K the picture is a dot and the first
text breaks. The Mac sizes all of it from the font's line height, as the pause notice is.
**Seen right on the Mac at 3840x2160.**

## 4. The store's stack count (port)

In a shop the count on a stack of items stood at the icon's upper right corner, half outside
the frame, where the inventory's is at the lower right. The label is made in code. KMRP
scales the inventory's width, height and place with the screen; the store's row has the same
instructions and only its icon was scaled, on the Mac and, by the Mac's own note, on Windows
("Windows scales only the inventory's label; the store's keeps 21x19 at 37"). The Mac now
gives the store's the same three numbers and puts its top at the icon less the label's
height. **Built and installed on the Mac; not yet seen in the game.** The workbench was not
looked at.

## 5. High FPS Fixes and particles (check)

Windows installs D3M0's own patch; the Mac has a port of it
(`macos/patches/high-fps-fixes`). D3M0's rule for particle fountains emits an emitter's rate
exactly and makes up for lost time; the game's own rule drops the part of a particle left
over. On the Mac's main menu, whose smoke is what the frame rate hangs on at a high
resolution, that was 116 particles a second against the game's 100, and at 3024x1964 the
menu ran at 60 frames a second with a frame of 119 to 462 ms in every five seconds, against
73 to 79 without the patch (the maintainer saw it as a stutter "like 15 FPS"). The Mac's
port now runs the game's own rule in steps of a sixtieth of a second and does not make up
for a long frame: 70 to 74, no long frames.

**For Windows:** this is D3M0's code, not KMRP's, and Windows' graphics cards have more room.
Worth one look at the main menu at 4K with High FPS Fix on and off; if it stutters only with
it on, this is why. Nothing to change in KMRP either way.

## 6. Anti-aliasing at 4K (check)

On the Mac's 4K television at 60 Hz the main menu ran at 59 frames a second at 2x
anti-aliasing and 82 with it off; frame-buffer effects and soft shadows made no difference.
Just under 60 with V-Sync is a stutter. The Mac's installer now writes `Anti Aliasing=0` when
the display has 3840x2160 pixels or more, and puts the old value back at uninstall.

**For Windows:** the Mac draws through Rosetta and Apple's OpenGL on Metal, so the numbers do
not carry over. Only if the menu stutters at 4K on a 60 Hz display there.

## 7. The pointer after a change of resolution (Mac only)

Aspyr's port keeps a ratio of game pixels to window points that it worked out once; after a
change of resolution in the game the pointer reached only the old size's part of the screen.
The Mac refreshes it after every switch. Windows has no such ratio.

## 8. Still open from 2026-10-08

Items 20 (the parked action slot), 21 (the pause box, both hooks) and 22 (the conversation
after a change of resolution) are built on Windows since master `aaaa037` and, by that
commit's own words, not all seen in the game there.

## Left as it is on both

The journal and experience icons stay top centre in the Xbox-style HUD (the maintainer,
2026-10-09: "leave them").
