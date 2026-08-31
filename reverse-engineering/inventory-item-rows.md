# List rows and item icons: how they are sized, and how we found out

The Inventory, Abilities and Store lists size their rows and item icons from
**hardcoded constants in the executable** — 56, 42 and 56 respectively. Nothing
in the `.gui` files can change them. This document
records the addresses, the full call chain, the method used to find them, and
the results that ruled everything else out — so none of it has to be
re-discovered.

Play-test confirmed at 3440x1440. Everything below was read live from a running
game under x32dbg, not inferred.

## The answer

**Three screens** build their list rows from the same class shape, each with its
own hardcoded size. The first constant in each group is the row's square icon
box (which also sets the text's left offset and width); the rest are the row
**height** handed to `SetRect`.

| screen | vanilla size | icon site | height site(s) |
| --- | --- | --- | --- |
| Inventory | 56 | `0x002B527F` (`0x006B527E`) | `0x002B4FA9`, `0x002B55E3` |
| Abilities (skills/powers/feats) | 42 | `0x002AB8EF` (`0x006AB8EE`) | `0x002ACB20` |
| Store / merchant | 56 | `0x002C265F` (`0x006C265E`) | `0x002C2A23` |

All are **imm32** encodings (`BF` = `mov edi, imm32`; `C7 44 24 xx` =
`mov dword [esp+xx], imm32`), so they take values far beyond a byte. Present and
identical in both the clean and gold executables. All three screens draw the
same `lbl_hex_3` icon frame.

**Each group's icon and height must move together.** Patching only the icon constant grows the
icons *into the row below* — verified in game. The icon and the row height
travel through completely separate paths that happen to share the same constant.

`RowSizeGroups` in `app/patcher/KotorUniversalPatcher.cs` now scales them
by `max(1.0, height/720)`, the same rule as the font atlases: 56 at 720p, 84 at
1080p, 112 at 1440p, 168 at 2160p.

These sites are reached **only** by their own screen's list row. That is what
makes them safe, and it is the difference between them and the `.kfs` list-row
float at `0x003DD004`, which is shared (see "Ruled out" below).

## How the size actually propagates

The icon is sized directly from constant #1. The row height takes a longer
route, which is why writing it at any single point does not stick:

```
  0x006B4FA5 / 0x006B55DF   mov <rect>.height, 56
        |
        v
  0x006B5270  row SetRect (vtable +0x04)      copies the rect into row+0x04..+0x10
        |
        v
  row+0x10  (the row's own height)
        |
        v  appended with the row's whole rect by 0x0041C271 -> 0x0041B860
  per-item rect array at [listbox+0x2A8]      every entry {0, 0, 1256, 56}
        |
        v  0x0041B202  call [item vtable+0x34]  ->  0x004064A0: mov eax,[ecx+0x10]
  0x0041B20D   [listbox+0x2B4] = max(item->height)
        |
        v
  0x0041B479   every row's rect height  <-  [listbox+0x2B4]
```

Row **pitch** is then `[listbox+0x2B4] + [listbox+0x2C0]`, computed at
`0x0041B1BD`, where `+0x2C0` is the GUI's `PADDING` byte. That is the mechanism
behind the `PADDING` test described in `font-atlases.md`.

> Writing `[listbox+0x2B4]` directly does **not** persist. It is recomputed as
> `max(item->height)` on every layout pass — confirmed live: a write of 96
> reverted to 56 on the next scroll. Only the source constants stick.

### Object layout reference (read live)

| what | where |
| --- | --- |
| inventory panel | `esi`/`edi` in `0x006B3xxx`–`0x006B4xxx`; instance seen at `0x1CEC3618` |
| panel binds `LB_ITEMS` | `0x006B36B5` → panel `+0x564` (`LB_DESCRIPTION` → `+0x844`) |
| **the listbox** | embedded at **panel+0x564** (not a pointer) |
| panel's row-object array / count / capacity | `+0x1DC0` / `+0x1DC4` / `+0x1DC8` |
| listbox content width / height | panel `+0x7F8` / `+0x7FC` = 1256 / 860 |
| listbox item-rect array ptr / count / cap | `+0x2A8` / `+0x2AC` / `+0x2B0` |
| **listbox row height** | **`+0x2B4`** |
| listbox `PADDING` (byte) | `+0x2C0` (= panel `+0x824`) |
| listbox item-control array | `+0x29C`, count word at `+0x2C8` |
| row allocation → ctor | `0x006B4502` (`new`) → `0x006B7EE0` |
| **row class vtable** | **`0x007568F8`** |
| row layout (vtable `+0xA0`) | `0x006B4DB0` |
| row `SetRect` (vtable `+0x04`) | `0x006B5270` |
| row height getter (vtable `+0x34`) | `0x004064A0` — `mov eax,[ecx+0x10]; ret` |
| row rect | `+0x04` left, `+0x08` top, `+0x0C` width, `+0x10` height |
| row → owning listbox | `+0x34` |
| row text sub-rect | `+0x6C` left (=icon width), `+0x74` width, `+0x78` height |
| row icon frame sub-object | `+0x1DC`, fill texture `lbl_hex_3` |
| listbox layout loop | `0x0041B460`; initial pass `0x0041B1E0` |

Controls share the rect layout `+0x04 left, +0x08 top, +0x0C width, +0x10
height` — the same shape as `CAurGUIStringInternal` documented in `font.md`.

## How to repeat this

The general method, which worked where five rounds of guessing did not:

1. **Find the control by its tag string.** `LB_ITEMS` is at `0x00751A14` in
   `.rdata`. Search `.text` for the 4-byte little-endian address to get the
   xrefs — `0x006B36B5` is where the inventory panel binds it, and the
   neighbouring `LB_DESCRIPTION` bind at `0x006B367E` confirms you are in the
   right function. The instruction right after each bind stores the control
   into the panel (`lea eax,[esi+0x564]`).
2. **Follow the object, not the code.** Break on the row layout
   (`0x006B4DB0`), read `ecx` for the object and `edx` for its vtable, then
   dump the object and look for values you can recognise on screen — 1256 (the
   content width) and 58/56 (the visible row pitch) identified the rect
   immediately.
3. **Watchpoint the field, don't hunt the writer.** A hardware write
   breakpoint on the row's `+0x10` caught `0x006B52A4`; one on
   `[listbox+0x2B4]` caught `0x0041B1D6`; one on the rect array's height caught
   `0x0041B8A2`. Each hop took one game action (scroll, or close/reopen the
   inventory) and no guessing.
4. **Scan for sibling constants once you know the value.** Disassembling
   `0x00415000-0x00420000` and `0x006B3000-0x006B9000` and filtering for
   instructions with an immediate `0x38` surfaced all three sites at once —
   including the two the watchpoints had not yet reached.
5. **Scan for the SHAPE, not the value, to find sibling screens.** Two
   signatures find every one of these row classes in the whole binary:
   `mov <reg>,imm ; cmp <reg2>,<reg> ; jle` locates each row class's icon
   constant, and a `mov [esp+X],imm` within a few instructions of
   `call [<reg>+4]` locates its height constant. That is how the abilities (42)
   and store (56) groups were found without any further debugging.

   > **Sweep with resync.** Capstone's linear disassembly *stops at the first
   > undecodable byte*, and `.text` is full of padding and data. A single
   > `md.disasm(whole_section)` silently returns a truncated result and will
   > make you believe there are no matches. Re-enter the loop one byte past
   > wherever it stopped.

6. **Test by poking memory, not by rebuilding.** Writing the immediates in the
   live process gave an instant visual answer with no build cycle and nothing
   written to disk; it reverts on restart.

### Debugger notes

- The process runs at base `0x400000` with no ASLR, so static VAs are usable
  directly. Attach with `attach <pid>`.
- **Clear every breakpoint before detaching.** Two earlier sessions ended in an
  apparent "freeze" that was actually a stale *conditional* breakpoint left at
  `0x0045A2F0` — the word-wrap function, which runs constantly. It had
  accumulated 26,114 hits and the game was simply stopped at it. Nothing was
  wrong with the game.
- Prefer `singleshot` breakpoints in layout paths; a plain one in a
  per-row function halts once per row.

## Ruled out (do not retest)

Every one of these was tested in game at 3440x1440 and left the list at exactly
15 rows in an 868px box:

| changed | result |
| --- | --- |
| `LB_ITEMS.PROTOITEM.EXTENT.HEIGHT` 100 → 200 | nothing |
| `LB_ITEMS.PROTOITEM.BORDER.INNEROFFSET` 10 → 40 | nothing |
| `LB_ITEMS.PROTOITEM.BORDER.DIMENSION` 14 → 40 | thick frames, row text vanished, **pitch unchanged** |
| `.kfs` row-scale float `0x003DD004` 2.0 → 3.0 | **save/load rows grew, inventory untouched** |
| `dialogfont16x16` fontheight doubled (atlas shipped) | nothing, anywhere on screen |

The protoitem's `EXTENT` *is* parsed correctly — read live, the protoitem
control at `0x0453BD10` held `+0x04`=440, `+0x08`=145, `+0x0C`=245,
`+0x10`=**100**, exactly matching the GFF. The engine reads the 100 and then
never uses it for the row. A widely-repeated claim that `PROTOITEM` determines
list row height does not hold for this list.

`dialogfont16x16` is what `inventory.gui` declares as the `LB_ITEMS` protoitem
font, yet changing it has no visible effect — the engine substitutes its own.
This matches the caution in `font-atlases.md` about treating a `FONT` field as a
hint rather than proof.

## Powers and Feats: unsolved, and what has been ruled out

The Abilities screen's Skills tab uses the 42 row class above, but its **Powers
and Feats tabs do not** — patching 42 scales Skills only, confirmed in game.
Those two tabs still render at vanilla size and **no fix is known**.

Everything below is a hard result, not an inference. Do not re-run these.

| tested | result |
| --- | --- |
| the listbox row-height path (`0x0041B202`) | **never reached.** A conditional breakpoint there logged `hit_count = 0` across repeated Feats↔Powers switches, so the grid is not laid out as listbox rows at all and `RowSizeGroups` can never reach it |
| `LB_ABILITY.PROTOITEM.EXTENT.HEIGHT` 40 → 100 | nothing |
| icon **texture** size, `ip_*` upscaled 32 → 64 | nothing. Proven loaded, not ignored: deleting the files mid-session turned those icons **white**, so the game was actively reading them. The icons are NOT drawn at texture size |
| square-rect constants, immediate pairs | zero in the entire `.text` |
| square-rect constants via a register (the inventory pattern) | 18 sites binary-wide, **none** in the abilities panel; the three 32px ones belong to the journal, map and save/load screens |
| `mov reg,imm ; cmp ; jle` icon signature | only abilities' 42 (Skills), inventory's 56, store's 56 |

So the size is neither a listbox property, nor the GUI, nor the texture, nor a
square constant. It is presumably computed — from the tree's column/row layout,
or written as a non-square rect from registers.

> **Next approach, if it is ever worth it:** breakpoint the texture draw call
> and filter for the icon, then walk back to the rect. This is a **per-frame hot
> path** — the two apparent "freezes" earlier in this project were both stale
> conditional breakpoints in hot code, so this needs a tightly scoped condition
> and prompt removal. Weigh that against the payoff, which is icon size on two
> tabs.

## Cross-checked against the open-source reimplementations

Three projects reimplement this engine and are the best available "how is it
programmed" reference: **reone** (github.com/seedhartha/reone), **KotOR.js**
(github.com/KobaltBlu/KotOR.js) and **xoreos** (github.com/xoreos/xoreos).

**reone independently confirms the model derived here.** Its
`ImageButton::render` (`src/libs/gui/control/imagebutton.cpp`) does:

```cpp
borderOffset.x += _extent.height;                                 // text left offset = row height
glm::ivec2 size(_extent.width - _extent.height, _extent.height);  // text width = width - height
pass.drawImage(*iconFrame,   {left, top}, {_extent.height, _extent.height});
pass.drawImage(*iconTexture, {left, top}, {_extent.height, _extent.height});
```

That is exactly the layout read out of the binary — icon square of side N, text
starting at N, text width `rowWidth - N` — where the original hardcodes N as
56/42/56. **The icon size and the row height are conceptually the same
quantity**, which is why patching only the icon constant produced overlap, and
why scaling them together is correct rather than merely empirical.

reone also confirms `lbl_hex_3` as K1's row icon frame (TSL uses
`uibit_eqp_itm1`), matching the frame-scaling work here.

### On Powers/Feats specifically, there is no reference implementation

- **reone** does not implement those tabs. `AbilitiesMenu::onGUILoaded`
  explicitly calls `setDisabled(true)` on `BTN_SKILLS`, `BTN_POWERS` and
  `BTN_FEATS`; only the Skills list is populated.
- **xoreos** has only chargen GUIs for KotOR, no in-game abilities menu.
- **KotOR.js** implements it for **TSL only**. Its model (`GUIFeatItem.ts`) is
  that each row is a feat *chain* — a root feat with no prerequisites, plus
  every feat whose `prereqFeat1`/`prereqFeat2` points back to it — with
  `extent.height = 45` hardcoded, `iconHeight = extent.height`, and
  `arrowHeight = iconHeight / 2`.

The chain structure matches what K1 renders. The sizing does **not** appear to
be implemented the same way in K1: there is no arrow-texture xref anywhere in
the abilities panel, and a binary-wide scan for "size constant, then halved"
(the `iconHeight / 2` signature) returns zero sites. So K1's feat tree lives
outside the abilities panel code and sizes itself by some other means.

## Known loose end

`lbl_hex_3.tga`, the row's icon frame art, is **56x56** — the same number as the
code constant. At higher scales the engine upscales it, so it will soften the
way the fonts did before they were re-rendered. If it reads blurry rather than
merely bigger, re-render the frame art at the baked size and ship it in the
Override, exactly as the font atlases are handled.
