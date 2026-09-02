# The shared message popup: what was changed and why

The box that carries the tutorial hints ("The attributes of your character apply
bonuses or penalties…") and the game's Yes/No confirmations. Every value below
was read back out of the installed files after the change; nothing here is
intent or inference. Where something is untested it says so.

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

`tools/build_message_popup_size.py`. No size change, no new section; verified in
the installed exe (`EFA167CD403EDECD…`, 4,079,616 bytes, all nine `.k??` sections
reading back).

| site | was | now | why |
| --- | --- | --- | --- |
| `0x006256E2` | `cmp eax, 0x118` | `cmp eax, 0x384` | stop condition for the auto-fit loop, not a height limit |
| `0x00625758` | `cmp eax, 0x118` | `cmp eax, 0x384` | **second site** -- patching one leaves the other clamping |
| `0x006256DA` | `cmp ecx, 0x1B8` | `cmp ecx, 0x640` | width cap |
| `0x006256F4` | `cmp ecx, 0x1B8` | `cmp ecx, 0x640` | second width site |
| `0x00626F94` | `mov eax, 0x20` | `mov eax, 0x80` | the icon control's rect, 32 → 128 |
| `0x0062540C` | `mov edx, 0x20` | `mov edx, 0x80` | the matching message offset; must move with the rect |

**The width cap is the fix for clipped text.** The auto-fit loop widens the popup
40 units at a time to fit its message, but only while the panel is narrower than
the cap. 440 was authored for 640x480, so at any HD size the panel already
exceeds it and the loop never runs -- the message keeps whatever width the `.gui`
gave it and long lines lose their last character.

### 2. `confirm.gui` — the tuned layout

`tools/scale_message_popup.py --tuned`. Read back from the installed file:

```
TGuiPanel    (733, 543, 900, 375)
  LB_MESSAGE (60, 24, 780, 150)   PADDING = 30   SCROLLBAR width = 0
  BTN_OK     (60, 320, 780, 80)
  BTN_CANCEL (60, 410, 780, 80)
```

* **`PADDING` 2 → 30.** The listbox lays text out inside
  `width - scrollbar - 2*border - PADDING`, so `PADDING` pulls the **wrap** edge
  in while the text is still **clipped** at the control edge. That difference is
  the slack the engine's line measurement needs -- it truncates each glyph's
  advance and runs short, so a line it believes fits renders wider.
* **`LB_MESSAGE` height 150** sets the gap above OK to ~34px. It must stay taller
  than the text: a shorter box makes the text overflow, which switches the
  auto-fit loop back on and brings the clipping with it.
* **Panel height 375.** 420 left 114px of dead space under the button, 300
  clipped the button against the panel edge, 340 put it flush; 375 leaves ~35px.
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

Nearest-neighbour on exact multiples (these are hard-edged glyphs), Lanczos
otherwise. Source sizes were 32x32 x6 and 48x48 x7.

### 4. A TGA writer bug fixed along the way

The icons came out upside down. `app/patcher/AbilityIconGenerator.cs` already
states the rule -- *"TPC pixel rows run bottom-up, and so does the TGA we write,
so no [flip]"* -- and the writer reversed the rows anyway. Fixed here and in
`build_padded_minimap_atlases.py`, which carried the same bug.

## Verified, and not

**Verified in play** at 3440x1440: the icon is upright and 128px; the message
text is complete with no clipped characters; the gap above OK is ~34px and below
it ~35px; the six patch sites and every GUI value above were read back out of the
installed files.

**Not verified**: the **Yes/No confirm box**, which shares this GUI. It has no
icon, so its message and both buttons sit 128px higher than in the screenshots,
and `BTN_CANCEL` at 410 should fall inside the 375-tall panel once that shift
applies -- but it has not been seen on screen.

Also unexplained: `spacingR` has **no effect** on this control. Setting it to
`0.300` -- 30px per glyph, which would force a break every couple of words --
left the render byte-identical, on both `dialogfont16x16` and `fnt_d16x16`. So
this text does not pass through the line-breaker at `0x0045A5C9` that the font
work targets, and `PADDING` is the lever that works instead. Both fonts were
restored to `0.005`.
