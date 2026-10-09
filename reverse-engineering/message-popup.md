# The shared message popup: what was changed and why

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


The box that carries the tutorial hints ("The attributes of your character apply
bonuses or penalties…") and the game's Yes/No confirmations. Every value below
was read back out of the installed files after the change; nothing here is
intent or inference. Where something is untested it says so.

> **Where the changes live (note of 2026-10-08, read from the source).** The
> values are as described; where they are written is not what the sections of
> September say. Since 2026-09-29 KMRP's installer does not write the six sizes
> into `swkotor.exe`, and since 2026-10-04 it puts no file into `Override`.
> Everything here is done by the module of `KMRP.kpatch` under KOTOR Patch
> Manager's runtime:
>
> | Part | Now |
> | --- | --- |
> | The six sizes of `PopupSizeGroups` (450, 800 and 64 at scale 1.0) | applied in memory, computed for the size the game runs at and written again when it changes (`FieldValue` in `K1RuntimeEngine.cpp`, over `resolution_fields()` in `tools/build_native_engine.py`: `0x6256E3`, `0x625759`, `0x6256DC`, `0x6256F6`, `0x626F95`, `0x62540D`). `ResolutionPatch` makes them only for `--apply`, the patched executable written to a new file as the reference |
> | `confirm.gui` per resolution | in the module's bank or written by its blend helper, never in `Override` ([runtime-resolution-preview.md](runtime-resolution-preview.md)) |
> | The 13 `tut_` icons and `tutorial.2da` | made by the module from the player's own game each time a size's files are produced (`KmrpGameArt`, `macos/tools/kmrp-gameart.c` compiled into it, called from `K1RuntimeAssets.cpp`) |
> | The fit to the contents | the detour at `0x006258E2`, as "Windows: fitted to its contents" below describes; one of the 28 hooks of KMRP's patch |

## What the popup is

`confirm.gui` backs the engine's shared message-popup class, whose constructor
loads it by name:

```
00626DF0  <message popup base ctor>
00626EB0  push 0x0074FDA4      ; "confirm"
00626EBE  call 0x00406D80      ; CExoString
00626ECA  call 0x0040A680      ; load GUI by name
```

The tutorial popups derive from that class -- their constructor at `0x006AA100`
calls it -- so they are `confirm.gui` wearing different text. The body comes from
`tutorial.2da`, read at `0x006AA724` through the table the manager holds at
`[manager+0x118]`, using the columns `Message%i` and `Icon` (43 rows).

**The class is constructed once per session**, so the GUI is read at startup and
reused. Editing `confirm.gui` mid-session does nothing; the game must restart.

## How the popup lays itself out

Re-derived by changing one value at a time and measuring the result from a
screen capture. The layout function is `0x006253A0`.

| behaviour | evidence |
| --- | --- |
| The panel's authored size is a **starting point**, not the result | measured panel differs from the authored `EXTENT` every time |
| The engine **adds the icon size to the panel height** (`panel.height += icon`) | authored 300 rendered ~428 with a 128px icon |
| The icon sits at the **top**, and the message is pushed **down** by the icon size (`message.top += icon`) | reading the stack slots correctly; see below |
| `BTN_OK` is anchored at **`LB_MESSAGE`'s bottom edge**, not at its own authored `TOP` | moving `BTN_OK` 203 → 350 shifted it 3px; changing `LB_MESSAGE`'s top moved it wholesale |
| Therefore **gap above OK = `LB_MESSAGE` height − text height** | 4-line message ~116px tall; box 210 gave 93px of gap, box 150 gives ~34px |
| Buttons **auto-size their width**: start at `0x64`, grow by `0xA` until the label fits | `0x006254AC` onward |

### The stack slots, read correctly

`0x006253A0` builds its rects on the stack, and after `push edi` at `0x006253F9`
every `[esp+N]` refers to pre-push `[esp+N-4]`. Getting that wrong is what made
an earlier reading of the icon branch describe it as `message.width += icon`:

```
00625404  mov ebx, [esp+0x2c]   -> panel.height += icon
00625408  mov edi, [esp+0x34]   -> message.top  += icon
00625415  mov edx, [esp+0x24]   -> panel.top    -= 16
```

Turning that `add edi, edx` into a `sub` lifted the text up over the icon, which
is how the mistake surfaced. **`0x00625413` is left vanilla.**

## The changes

### 1. Executable — five in-place `imm32` rewrites

`tools/build_message_popup_size.py`, folded into **gold v15**
(`79356D1A…`, 4,079,616 bytes, length unchanged). Gold bakes the values
play-tested at 3440x1440; `ResolutionPatch` rescales all six per resolution
(see *Every resolution* below). No size change, no new section; verified in
the installed exe (`EFA167CD403EDECD…`, 4,079,616 bytes, all nine `.k??` sections
reading back). The six sites are unchanged since: gold v24 holds the same
values, and the 2026-09-24 installer's `--apply` output carries them scaled per
resolution (`docs/universal-resolution-math.md`, *Executable fields*).

| site | was | now | why |
| --- | --- | --- | --- |
| `0x006256E2` | `cmp eax, 0x118` | `cmp eax, 0x384` | stop condition for the auto-fit loop, not a height limit |
| `0x00625758` | `cmp eax, 0x118` | `cmp eax, 0x384` | **second site** -- patching one leaves the other clamping |
| `0x006256DA` | `cmp ecx, 0x1B8` | `cmp ecx, 0x640` | width cap |
| `0x006256F4` | `cmp ecx, 0x1B8` | `cmp ecx, 0x640` | second width site |
| `0x00626F94` | `mov eax, 0x20` | `mov eax, 0x80` | the icon control's rect, 32 → 128 |
| `0x0062540C` | `mov edx, 0x20` | `mov edx, 0x80` | the matching message offset; must move with the rect |

Gold binaries are not tracked (`build/` is ignored), so v15 is reproduced from
v14 with:

```bash
python tools/build_message_popup_size.py build/kmrp/swkotor_gold_v14_minimap.exe build/kmrp/swkotor_gold_v15_popup.exe --height-cap 900 --width-cap 1600 --icon-size 128
```

**The width cap is the fix for clipped text.** The auto-fit loop widens the popup
40 units at a time to fit its message, but only while the panel is narrower than
the cap. 440 was authored for 640x480, so at any HD size the panel already
exceeds it and the loop never runs -- the message keeps whatever width the `.gui`
gave it and long lines lose their last character.

### 2. `confirm.gui` — the tuned layout

`tools/scale_message_popup.py --tuned`. Read back from the 2026-09-24
installer's 3440x1440 archive:

```
TGuiPanel    (733, 468, 900, 525)
  LB_MESSAGE (60, 24, 780, 150)   PADDING = 30   SCROLLBAR width = 0
  BTN_OK     (60, 320, 780, 80)
  BTN_CANCEL (60, 410, 780, 80)
```

The panel was first `(733, 543, 900, 375)`; see *Panel height* below.

* **`PADDING` 2 → 30.** The listbox lays text out inside
  `width - scrollbar - 2*border - PADDING`, so `PADDING` pulls the **wrap** edge
  in while the text is still **clipped** at the control edge. That difference is
  the slack the engine's line measurement needs -- it truncates each glyph's
  advance and runs short, so a line it believes fits renders wider.
* **`LB_MESSAGE` height 150** sets the gap above OK to ~34px. It must stay taller
  than the text: a shorter box makes the text overflow, which switches the
  auto-fit loop back on and brings the clipping with it.
* **Panel height 375, then 525.** Tuned on a tutorial popup: 420 left 114px of
  dead space under the button, 300 clipped the button against the panel edge,
  340 put it flush; 375 left ~35px. But a Yes/No box has no icon, and at 375 its
  panel ended at y=375 while `BTN_CANCEL` ended at 490 -- the clipped
  confirmation reported at 3840x2160. The height is now 525, which keeps a 35px
  margin under Cancel (`TUNED` in `scale_message_popup.py`;
  `docs/universal-resolution-math.md`, *Reported 4K layout repairs*). Tutorial
  popups, which add the icon's height on top, have not been re-checked since.
* **Scrollbar width 15 → 0.** Tried as a clipping fix and it made no difference,
  but the box is sized to hold the message so nothing scrolls, and it stops the
  bar eating content width. Harmless, kept.

### 3. Icons — private copies at 128px

`tools/scale_tutorial_icons.py`. Verified: 13 files in Override, each
`type=2 128x128 bpp=32 desc=0x08`, and `tutorial.2da`'s `icon` column now names
all 13 `tut_*` resrefs.

The engine draws GUI textures **one texel per pixel**. A texture smaller than the
rect **tiles** (a 32px icon in a 64px rect drew as four copies) and a larger one
is **cropped**. So rect and texture must match.

They could not simply be scaled in place, because **8 of the 13 are shared**:
`i_attack` is a feat icon `scale_ability_icons.py` sizes for the Abilities rows,
and seven `lbl_i*` are HUD status icons KMRP ships in `override-common.zip`.
Scaling those would have broken both. The popup therefore gets private copies
under a `tut_` prefix and the 2DA is repointed at them; every other use of the
originals is untouched. All seven HUD icons verified byte-identical to the
shipped archive.

Nearest-neighbour on exact multiples (these are hard-edged glyphs), bilinear
otherwise.

**Correction.** This first recorded the sources as 32x32 x6 and 48x48 x7. That
was measured through an `Installation`, which resolves Override **first** -- so
seven of the reads were KMRP's own scaled HUD icons, not the stock art, and the
generator was compounding its own output. Read from the stock texture pack they
are a clean **32x32 x6 and 64x64 x7**, so the seven now upscale by an exact
integer factor instead of being resampled from an intermediate size. Six of the
thirteen came out byte-identical either way; the other seven are sharper.
`export_tutorial_icons.py` therefore reads the pack directly and never an
`Installation`.

### 4. A TGA writer bug fixed along the way

The icons came out upside down. `src/patcher/AbilityIconGenerator.cs` already
states the rule -- *"TPC pixel rows run bottom-up, and so does the TGA we write,
so no [flip]"* -- and the writer reversed the rows anyway. Fixed here and in
`build_padded_minimap_atlases.py`, which carried the same bug.

## Every resolution

Everything above was tuned at 3440x1440. It ships at all 49 resolutions by
scaling against **font scale**, `max(1.0, height/720)` -- the same rule the font
atlases' TXI metrics use, mirrored in `ScaleForHeight`. That is the right basis
because what the popup has to hold is *text*, and the text is sized by that rule:
a popup scaled the same way holds the same number of lines everywhere. 3440x1440
is font scale 2.0, so every tuned number above is stored as its half.

| what | scale 1.0 | at 3440x1440 | where |
| --- | --- | --- | --- |
| panel | 450x263 | 900x525 | `TUNED` in `scale_message_popup.py` (was 450x188 and 900x375) |
| `LB_MESSAGE` | 30,12,390,75 | 60,24,780,150 | same |
| `PADDING` | 15 | 30 | same |
| auto-fit height stop | 450 | 900 | `PopupSizeGroups` |
| auto-fit width cap | 800 | 1600 | `PopupSizeGroups` |
| icon rect + message inset | 64 | 128 | `PopupSizeGroups` |
| icon texture | 64px | 128px | `export_tutorial_icons.py` |

The three have to move together: the width cap must exceed the panel or the
auto-fit loop cannot run and the text clips again, and the icon texture must
equal the icon rect or it tiles or crops. Verified by reading the six patch sites
back out of executables the patcher actually produced at 800x600, 1280x720,
1920x1080, 3440x1440, 3840x2160 and 15360x8640 -- every one consistent, cap
always above panel width.

**A ratio transfer would have been wrong here**, which is why `confirm.gui` was
removed from `GOLD_GEOMETRY_TEMPLATES`. That mechanism transfers gold's
proportional correction onto each resolution's own stock file, and it suits GUIs
that upstream authored consistently. Upstream sizes *this* popup by screen
**width** (870px at 1920x1080, 1740 at 3840x1080, both 1080-tall) while gold
deliberately shrank it, so transferring gold's ratio onto 800x600 yields a 209px
popup -- narrower than vanilla's own 363, for text that has not shrunk. The
generated layout gives 450 there instead.

`confirm.gui` is generated for **every** resolution including 3440x1440, ahead of
the branch that otherwise passes gold's files through untouched. The layout is
absolute rather than relative, so re-running it over the already-tuned gold copy
reproduces that copy byte for byte -- checked, and it is what makes it safe for
gold to hold the hand-tuned file.

The 13 icons shipped **per resolution** in `gui-<res>.zip`, because their size is
tied to the scaled rect; `tutorial.2da` is resolution-independent and shipped once
in `override-common.zip`. They were in exactly one archive each, which is what
keeps the restore manifest sound. Since 2026-09-29 neither ships: both installers
make the icons (at the same `64s`) and the table from the player's own game
(`src/patcher/GameArtGenerator.cs`, `macos/tools/kmrp-gameart.c`), as one more
payload, so each is still written exactly once.

## The Mac: fitted to its contents (2026-09-30)

The layout above never shrinks anything: the panel keeps `confirm.gui`'s height (plus the
icon, less one button's height when there is only one), and the message keeps the height
tuned for a four-line tutorial, with OK anchored to its bottom. A short text therefore
leaves space above OK, and every popup keeps the height its tallest case needed. Measured
on the Mac at 3024x1964: the Exit Game box was 711 px tall for about 430 px of contents,
165 px empty above OK and 250 below Cancel.

The Mac's layout patch (`macos/patches/kmrp-layout/popup_fit.cpp`) now finishes the job at
the end of the Mac's `FixMessageLabel` (`0x100306552`), in place of its last call:

| step | how |
| --- | --- |
| the message narrows | to the least width at which its text wraps to the same height, found by halving with the engine's own wrapping (the list's `SetExtent` and the rebuild below, at each try), never narrower than the widest shown button or the icon: a one-line question shrinks to its sentence, a paragraph keeps its line count |
| the message shrinks to its text | the list's inner height (`+0x344`) less its own fit test, padding (`+0x373`) plus the tallest item (`+0x368`); then the list's `SetExtent` (`0x1004A81AE`) and the message rebuild (`0x100306B86`), as `FixMessageLabel` does after each resize |
| the buttons follow it | OK 4 px under the message, Cancel 2 px under OK, as `FixMessageLabel` places them |
| the panel fits | as wide as the message plus its left inset on both sides, ending as far below the last shown button as the message starts below its top in the file (the saved top, `+0xC04`); the icon and buttons re-centred across it, and the panel keeps its centre (the corner moves by half of each change, as `FixMessageLabel` does) |

Only when the text fits without the scrollbar; otherwise the popup is left as the engine
made it. Seen in play at 3024x1964, 2026-09-30: the Exit Game box 711 → about 365 px tall
and 1,224 → about 880 px wide, centred on the screen, with 30 px above the message and below
the last button; the Attributes, Skills and Feats tutorials fitted and centred, keeping 4, 7
and 5 lines; the unspent-points box fitted (seen before the width step). **Windows is not changed**: the
same step belongs after `0x006253A0`, whose `0x006254AC` onward places the buttons the same
way. Until it is added, the two platforms' popups differ in height. *Windows since the same
evening: below.*

## Windows: fitted to its contents (2026-09-30)

The same four steps, in KMRP's module (`src/controller-native/K1PopupFit.cpp`,
`FitMessageBoxK1`), at a detour in `FixMessageLabel`'s epilogue (`0x006258E2`: `pop edi;
pop esi; pop ebp; pop ebx; add esp, 0x30`, with esi the box), installed with every KMRP
patch. Read from `0x006253A0`:

| | Windows |
| --- | --- |
| the file's panel and message extents, saved | `+0x95C`, `+0x96C` (the message's top `+0x970`) |
| the icon, and whether it is shown | the label at `+0x1B4`; bit `0x10` of `+0x64`: the panel grows 32 and the message moves down 32 |
| OK, Cancel | `+0x2F4`, `+0x4B8`, each shown while bit `0x2` of its `+0x44` is set; widened 10 at a time while their caption does not fit (`0x00414EE0`) |
| the message list | `+0x67C`; inner height `+0x298`, tallest item `+0x2B4`, padding (byte) `+0x2C0`; its `SetExtent` is vtable slot 1, then `0x006252F0` rebuilds the text label to its width |
| the last call | `0x0040A600`: the panel's left and top centred on the screen from its width and height; the fit runs after it and calls it again |

Seen in play at 3440x1440 (`17EE496D…`, a scratch copy): "Do you really want to quit?" in a box
657x272 px, centred; the Attributes tutorial 776x413, centred; the Skills tutorial and the
Solo Mode prompt fitted.

## Verified, and not

**Verified in play** at 3440x1440: the icon is upright and 128px; the message
text is complete with no clipped characters; the gap above OK is ~34px and below
it ~35px; the six patch sites and every GUI value above were read back out of the
installed files.

**The Yes/No confirm box**, which shares this GUI, was listed here as never seen
on screen, with `BTN_CANCEL` expected inside the 375-tall panel. It was not: the
3840x2160 report showed it clipped, which is why the panel is now 525. The box
has been on screen in play since -- the Solo Mode play-test of 2026-09-24, at
3440x1440, with no layout complaint -- but its geometry was not measured then.

Also unexplained: `spacingR` has **no effect** on this control. Setting it to
`0.300` -- 30px per glyph, which would force a break every couple of words --
left the render byte-identical, on both `dialogfont16x16` and `fnt_d16x16`. So
this text does not pass through the line-breaker at `0x0045A5C9` that the font
work targets, and `PADDING` is the lever that works instead. Both fonts were
restored to `0.005`.

*Note of 2026-10-08:* the fonts no longer carry `0.005`. Since 2026-10-05 every
set a release ships has `spacingR 0`, after the engine's `Draw` was found to add
the value after every glyph
([font-atlases.md](font-atlases.md#spacingr-is-drawn-and-a-whole-pixel-set-must-not-carry-it)).
That finding and the observation above ("no effect" at `0.300`) do not agree,
and the observation was not repeated; treat it as unexplained, not as evidence
about `Draw`.

## The widening step (2026-10-09)

**Status: applied, and seen right in the game on Windows on 2026-10-09 (Steam, 3440x1440).
Not looked at on Windows at 3840x2160, where the Mac's maintainer saw the fault.**

The auto-fit loop of `0x006253A0` grows a box whose text does not fit. Each pass adds 40 to
the width, takes 20 off the left so that the box stays centred, and adds one line of the
font to the height. The two caps follow the screen (above), and a line is the font's, which
is baked for the screen's height; the 40 and the 20 are the game's own and never scaled. At
1280x720 a pass adds 40 across and about 20 down; at 3840x2160 it adds 40 across and about
66 down, so the same text makes a wide box at a low resolution and a tall, narrow one at a
high one. Reported on the Mac on 2026-10-08 (`docs/windows-changes-from-macos.md`, item 24).

| VA | bytes | instruction |
| --- | --- | --- |
| `0x006256FC` | `83 44 24 38 28` | `add [esp+0x38], 0x28` |
| `0x00625701` | `8B 44 24 20` | `mov eax, [esp+0x20]` |
| `0x00625705` | `83 C1 28` | `add ecx, 0x28` |
| `0x00625708` | `89 4C 24 28` | `mov [esp+0x28], ecx` |
| `0x0062570C` | `83 E8 14` | `sub eax, 0x14` |
| `0x0062570F` | `8D 4C 24 30` | `lea ecx, [esp+0x30]` |
| `0x00625713` | `89 44 24 20` | `mov [esp+0x20], eax` |

The three numbers are signed bytes: 120, the step at 2160 lines, does not fit. The same 27
bytes are rewritten with one 32-bit step, `40 * height / 720` and never less than 40:

```
006256FC  B8 <step>      mov eax, step
00625701  01 44 24 38    add [esp+0x38], eax
00625705  01 C1          add ecx, eax
00625707  89 4C 24 28    mov [esp+0x28], ecx
0062570B  D1 F8          sar eax, 1
0062570D  29 44 24 20    sub [esp+0x20], eax
00625711  8D 4C 24 30    lea ecx, [esp+0x30]
00625715  90 90          nop ; nop
```

`eax` is loaded anew at `0x00625717` and no flag set here is read. No branch of the function
lands inside the 27 bytes (checked by disassembling `0x006253A0` to its end). The step is a
run-time field of the engine recipe (`POPUP_STEP` in `tools/build_native_engine.py`, at
`0x006256FD`), written again at every change of resolution in the game, and
`PopupStepOffset` in `ResolutionPatch` writes the same bytes into the installer's reference
image.
