# Why a controller badge shrinks when its button takes focus

**Status: on hold, unresolved.** One measurement separates the two remaining
explanations; it is named at the bottom. Everything above it was measured on a
live 1.0.3 process under x32dbg on 2026-09-14, party selection screen, 3440x1440.

Nothing here is implemented. The live heap writes used to get these numbers were
all reverted in the same session.

## The report

The party screen's Cancel carries a permanent B badge. On focus the B is drawn
noticeably smaller -- "it's like the focus replaces the button". The same happens
on every badged button; it is most visible on Cancel because that badge is
permanent, so both states are seen back to back.

## What a focused button actually does

A button holds **two complete border definitions**, and the engine draws the
focus one **instead of** the normal one -- not on top of it:

    control + 0x80   normal
    control + 0xF4   focus (HILIGHT)

This is already recorded: `docs/controller-support.md:204`, and the regression it
caused is CHANGELOG line 723 -- an earlier build wrote the badge only to the
normal fill and the badge vanished the instant a control took focus. That is why
`SetK1ControllerPromptFill` writes both.

So the focused badge genuinely *is* a second, separately-drawn copy. The player's
description of it as a redraw is literally correct, and "just don't draw a badge
on focus" is not available: clearing the focus copy's fill removes the badge
while focused rather than leaving the old one showing.

## Both blocks, read live

Party selection `BTN_BACK`, control at `0x140B400C`:

| offset in block | field | normal (`+0x80`) | focus (`+0xF4`) |
| --- | --- | --- | --- |
| `+0x00` | DIMENSION | 2 | 6 |
| `+0x04` | INNEROFFSET | 0 | 0 |
| `+0x0C..0x18` | COLOR rgba | 1, 1, 1, 1 | 1, .929, 1, .929 |
| `+0x20` | CORNER | *(empty)* | `boxline3` |
| `+0x30` | EDGE | *(empty)* | `boxline4` |
| `+0x40` | FILL (inline resref) | `kmrpb_ptyback` | `kmrpb_ptyback` |
| `+0x50` | fill texture object | ptr | ptr |
| `+0x64` | *(not this structure -- see below)* | 2118, 1230, 785, 84 | 2124, 1236, 773, 72 |

`BTN_BACK`'s authored EXTENT is `2118, 1230, 785, 84`, which is byte-identical to
what the normal block's `+0x64` returned. That agreement is real but the field is
not part of the params block at all; the reading below says what was actually
being read.

A note on the reference: `Lane-reference/swkotor.exe.h` names the first four
`CSWGuiBorderParams` fields `x, y, width, height`. That is a Ghidra placeholder
and it is wrong here. The GFF parser settles it -- `0x00415514` stores
`INNEROFFSET` to `[border+0x18]`, which is `params+0x04`, and the DIMENSION
getter at `0x00414CD0` is called with `ecx = border+0x14`, which is `params+0x00`.
So the first two are DIMENSION and INNEROFFSET, as the table says.

Field offsets are relative to what `SetK1ControllerPromptFill` passes, which is
`control+0x80` / `control+0xF4`. The GFF parser's own base is `0x14` lower --
`0x00415514` stores INNEROFFSET to `[ebx+0x18]` and the DIMENSION getter at
`0x00414CD0` is called with `ecx = ebx+0x14` -- which is why DIMENSION lands at
`+0x00` and INNEROFFSET at `+0x04` in the table above. Both were confirmed
against the `.gui`.

## Ruled out, with the evidence

**`INNEROFFSET` is not the fill inset.** Gold `partyselection.gui` authors
`HILIGHT.INNEROFFSET = 9`; the live install has `0` (a build-time transform,
since reverted, had flattened it). **Both produce an inset of 6.** A field whose
two very different values give the same answer is not the input.

This also disposes of the `flatten_prompt_highlights` experiment entirely: it
could never have fixed this, and it is what removed the map screen's button text
-- see below.

**`DIMENSION` is the outline thickness, not the badge size.** Set live from 6 to
2 on the focus block: the green focus outline disappeared, and the badge stayed
exactly as small. Two separate effects, and only one of them answered.

**The `+0x64` rect was never the badge's rect, and the test was meaningless.**
Overwriting it changed nothing on screen, which was read at the time as "this
field does not drive the fill". The real reason is worse: `+0x64` is not part of
that structure at all.

`CSWGuiBorder` is `{ vtable, extent at +0x04, border_params at +0x14, ... }` and
is `0x74` bytes -- see
[custom-gui-controls.md](custom-gui-controls.md). What the module calls the
border-params offset is therefore `0x14` INTO a border that starts `0x14`
earlier, so reading `params + 0x64` reads `border + 0x78`, which is past the end
of that border:

| read | actually | value seen |
| --- | --- | --- |
| normal params `+0x64` = button `+0xE4` | `border_2 + 0x04` -- the FOCUS border's extent | 2118, 1230, 785, 84 |
| focus params `+0x64` = button `+0x158` | `text + 0x04` -- the CAPTION's extent | 2124, 1236, 773, 72 |

So the two numbers being compared were a border extent and a text extent, from
different structures. The "inset by 6" that the whole investigation chased is the
inset of the **caption**, not of the badge, and writing the first over the second
would have moved the button's text rather than its glyph.

This does not resolve why the badge changes size; it removes a false lead and the
conclusion drawn from it. Whatever sizes the fill is elsewhere -- the border's
own `extent` at `border+0x04`, or the `x`/`y`/`width`/`height` at the start of
`CSWGuiBorderParams`, neither of which has been read for both borders of the same
button.

**`min(INNEROFFSET, DIMENSION)` is computed, but not for this.** `0x00415360`
onwards reads INNEROFFSET, calls the DIMENSION getter, keeps the smaller, and the
function's tail writes four dwords through a caller-supplied pointer -- a rect
helper. At runtime that is `min(0, 6) = 0`, yet the badge is inset 6. Whatever
this rect feeds, it is not the fill.

## The two candidates left

**Read this section knowing the correction above**: the 6 it discusses was
measured from the caption's extent, so "the inset is 6" is not established for
the badge at all. The two candidates are kept because they remain the obvious
things to test once the badge's real rect is read, not because the 6 stands.

Two things on this button are 6, and nothing done so far separates them:

1. `HILIGHT.DIMENSION` is **6**.
2. `boxline3` and `boxline4` are **12x12 px** (measured from
   `C:\Star Wars - KotOR\Override\boxline3.tga`), and 12 / 2 is **6**.

The distinction decides whether the problem is fixable:

* **If DIMENSION** -- the inset and the outline thickness are the same number.
  A constant-size badge and a full-thickness focus outline cannot both be had.
  It is a trade for the player to choose, not a bug to fix.
* **If the edge texture** -- give the *normal* block a fully transparent 12px
  EDGE texture. Both copies then inset 6, the badge is identical in both states,
  and the outline is untouched, because the normal block draws no visible edge
  art. A free fix.

## The measurement that settles it

First, read the badge's **actual** rect for both borders of one button, which
has never been done. A button's borders are whole `CSWGuiBorder` objects at
`control+0x6C` and `control+0xE0`, each `0x74` bytes:

```
border + 0x04   extent          left, top, width, height
border + 0x14   border_params   dimension, inneroffset, ... , fill at +0x40
```

Dump both borders in full and compare. If their extents differ by the amount the
badge shrinks, that is the field; if they match, the size comes from inside the
params.

Only then is the DIMENSION-versus-edge-texture question worth asking, and it is
asked the same way: set `HILIGHT.DIMENSION` to 2, force a fresh layout by leaving
and re-entering the panel, and re-read `control+0xE0+0x04`.

Note for whoever runs it: **hardware data breakpoints did not work in this
session.** `bphws` at three exact addresses never fired while a software
breakpoint at `0x00415373` fired hard enough to stall the debugger. Memory
breakpoints (`bpm`) are page-granular and drowned in unrelated traffic from the
same 4 KB page. Use software breakpoints and direct reads.

## Related damage, still open

`flatten_prompt_highlights` set `HILIGHT.INNEROFFSET` to 0 on every badged
button at build time. On `map.gui` the three buttons' **caption text stopped
rendering**. The transform is fully reverted and the rebuilt package
(`828B2740...`) restores `INNEROFFSET = 9` there, but **that build has not been
installed**, so the live Override still carries the flattened files and the map
text is still missing. Confirm after installing.

If the text does return, that is a real finding for
[text-padding.md](text-padding.md): `INNEROFFSET` is a **text** lever, which is
the family that document is about -- it is simply not the *fill* lever, which is
what it was misused as here.
