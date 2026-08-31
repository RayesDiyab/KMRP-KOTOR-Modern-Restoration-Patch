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

## Powers and Feats: a vanilla listbox bug that high resolution exposes

The Abilities screen's Skills tab uses the 42 row class above; **Powers and
Feats do not**. Their rows are feat/power *progression chains*, and their height
**accumulates on every rebuild** until it hits a ceiling.

### What it is

Measured numerically out of `[listbox+0x2B4]` (not judged by eye): **42 -> 56 ->
126** over successive clicks of the Powers tab. Re-clicking the *same* tab is
enough; closing the whole menu resets it, because the accumulator lives on the
listbox object and dies with the screen.

**Very probably vanilla behaviour rather than something this project
introduced -- but read the caveat.** Growth is clamped by the box height, so a
small box clamps on the first pass and nothing is visible, while a 1324x510
`LB_ABILITY` has room to ratchet. Shrinking `LB_ABILITY` back to vanilla's
extent visibly lowered the ceiling, which is that clamp moving. Every patch this
project makes was also eliminated by direct experiment (table below), and the
accumulator itself is plainly a type confusion in stock engine code.

> **Correction.** An earlier version of this document claimed the upstream
> `abilities.gui` was "byte-identical to the packed vanilla file" and cited that
> as proof the bug is BioWare's. **That evidence was wrong.** pykotor's
> `Installation.resource()` searches Override *before* the BIFs, so the
> "extracted vanilla" file was really the upstream file that had just been
> installed into Override -- it was compared against itself. The real BIF file
> differs (same length, extents edited in place). The conclusion still looks
> right on the clamp reasoning, but it is an inference, not a proof: no test ever
> ran stock-BIF geometry in a box large enough to ratchet. **When reading a
> "vanilla" resource for comparison, read it from the BIF explicitly via
> `chitin_resources()`, never through `Installation.resource()`.**

### Ruled out by direct experiment

Each of these was tested in isolation, in game:

| suspect | result |
| --- | --- |
| our exe row/icon constants (abilities 42->84) | innocent -- patched into an otherwise vanilla game, no growth |
| our `LB_DESC` `PADDING` = 24 | innocent -- zeroed, still grows |
| `LB_ABILITY.PROTOITEM.BORDER.DIMENSION` (=14, matched the increment) | innocent -- zeroed, still grows. The 14 was coincidence |
| the pykotor GFF rewrite of our `.gui` files | innocent -- pristine upstream file still grows |
| fonts / textures | innocent -- Override with assets but no `.gui` files does not grow |
| `.kfs` list-row scale | innocent |

### The accumulator, and the fix

Two sites inflate the row height on every layout pass:

```
0041B465  idiv ecx              ; eax = how many rows fit in the box
0041B488  mov [esp+18], eax     ; ...stashed
0041B4FD  mov ebp,[esi+2B4]     ; ebp = listbox row height, in PIXELS
0041B507  add ebp, edx          ; + that COUNT        <-- type confusion
0041B522  mov [esp+2C], ebp     ; becomes the row's rect height
0041B52C  lea edx,[ebp+1]       ; +1px on the first `ebx` rows
```

**A row count is added to a row height.** Either would be harmless if discarded,
but the layout writes the inflated rect back into the row controls, and the next
pass recomputes `[listbox+0x2B4] = max(item->height)` (`0x0041B20D`) over those
same reused rows. `[+0x2B4]` *is* reset to 0 at `0x0041B1D6` each populate --
which is what made this so hard to see -- but the max immediately reads the
inflated value back out of rows that were never rebuilt.

`tools/build_listbox_growth_fix.py` patches both, and is now part of the gold
build (v9):

| VA | file | was | now |
| --- | --- | --- | --- |
| `0x0041B507` | `0x0001B507` | `03 EA` (`add ebp,edx`) | `90 90` |
| `0x0041B52C` | `0x0001B52C` | `8D 55 01` (`lea edx,[ebp+1]`) | `8D 55 00` |

Row *positions* still advance normally -- that uses a separate accumulator in
`edi` -- so lists lay out as before and simply stop growing. Verified in game:
`[listbox+0x2B4]` holds at 40 across repeated Powers clicks, where it previously
went 42 -> 56 -> 126.

**This also unblocked the original goal.** Scaling the feat/power chain row
height (`0x002CD8D9` / `0x002CDB79`, vanilla 40) produced runaway growth before,
because it was feeding a broken loop; with the loop fixed it scales cleanly and
is now in `RowSizeGroups`.

### Method note

Two debugger traps produced false results here, both worth avoiding:

1. **x64dbg removes a `singleshot` breakpoint on its first hit even when the
   condition evaluates false.** A conditional singleshot at `0x0041B202` was
   silently deleted by an unrelated hit, and its `hit_count = 0` was recorded
   here as proof that the grid never reaches the listbox row path. That was
   wrong -- the rows demonstrably do. Use non-singleshot breakpoints when
   conditions are involved.
2. **Do not judge growth by eye when the UI is rendering small.** Tests run with
   the `.gui` files parked drew the screen as a tiny centred box (vanilla GUI
   coordinates against a resolution-patched exe); a few pixels of growth there
   is invisible, and two "no growth" readings taken that way were false
   negatives that misdirected the whole exe-vs-assets bisect. Read
   `[listbox+0x2B4]` numerically instead.

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
