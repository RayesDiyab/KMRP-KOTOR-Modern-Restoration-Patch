# Listbox geometry: where every margin comes from

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


How the engine turns a `.gui` listbox into rows on screen, which field controls
which margin, and the method for finding the next one. Everything here was read
out of `swkotornopatch.exe` or a live process — no inference unless labelled.

> **Scope.** This file covers listboxes. They are 81 of the 640 text-bearing
> controls in the game; the other 559 -- labels, buttons, toggles -- have no
> `PADDING` field and share none of this code. For changing gaps *uniformly*
> across both families, start from [text-padding.md](text-padding.md).

**The single most important fact: there is one code path.** `CAurGUIListBox`
lays out *every* listbox in the game — inventory, journal, store, the message
logs, the HUD action queues. A margin that looks wrong on one screen is not a
per-screen bug and does not need a per-screen patch. What differs per screen is
the **`PADDING` byte in that screen's `.gui`**. Patch the code once, then tune
each screen with one field.

## The two functions

### 1. Client rect — `0x0041BF80`

Runs when the control's rect is set. Turns the `.gui` `EXTENT` into the usable
interior, stored at `listbox+0x28C..0x298` = `{left, top, width, height}`.

```
0041BF8B  mov  ebx, [esi+0x110]         ; the scrollbar's own EXTENT width, from the .gui
0041BFC0  test byte [esi+0x2BC], 0x10   ; the LEFTSCROLLBAR flag
0041BFCD  add  [esp+0xc], ebx           ; left  += scrollbarWidth   -- only when the flag is set
0041BFD7  sub  ecx, ebx                 ; width -= scrollbarWidth   -- always
0041BFFB  lea  edx, [esi+0x28c]         ; copy the 16-byte rect into the listbox
```

Neither line consults whether a scrollbar is currently *shown*, so
`LEFTSCROLLBAR` costs a permanent left margin the width of the bar. Vanilla drew
~16px bars; the HD layout scales them to 64-95px, which is why a margin nobody
noticed in 2003 is obvious now. **The size of that margin is the scrollbar's
authored `EXTENT/WIDTH`** — a `.gui` number, not a code constant.

### 2. Row layout — `0x0041B140`

Builds each row's rect and calls the row's `SetRect` (vtable `+0x04`). The rect
lives at `[esp+0x20..0x2C]` = `{left, top, width, height}`.

`PADDING` (`[listbox+0x2C0]`, a **byte**) is read for **six** different jobs:

| what | where | vanilla |
| --- | --- | --- |
| `rect.left` | `0x0041B46D` | `= PADDING` |
| `rect.width` | `0x0041B48C` | `= contentWidth - 2*PADDING` |
| first row's top | `0x0041B4A1` | chain starts at `PADDING` |
| row **pitch** | `0x0041B1C4`, `0x0041B26B`, `0x0041B553` | `= rowHeight + PADDING` |
| the "does it fit?" test | `0x0041B339`, `0x0041B3AE` | `PADDING + rowHeight` vs box height |

So raising `PADDING` to get a left gutter also spaced the rows apart, inset the
right edge and pushed the whole list down. That is why the field was unusable on
multi-row lists before gold v11.

## Gold lineage

| version | tool | what it does |
| --- | --- | --- |
| v10 | `build_stack_count_fix.py` | stack-count label into `.ksc` with imm32 operands |
| v11 | `build_listbox_padding_fix.py` | `PADDING` becomes a purely horizontal left inset — 3 pitch sites, the width/top site, and both fit tests |
| v12 | `build_gutter_side_fix.py` | the gutter follows the scrollbar, in **both** rect builders (`.kgs`) |
| v13 | `build_leading_newline_fix.py` | strip leading newlines from GUI text at set time (`.ktn`) |
| v14 | `build_minimap_zoom_fix.py`, `build_minimap_fog_fix.py` | HUD minimap zoomed to the player (`.kmz`) and its fog grid matched to it (`.kfg`) — see [map.md](map.md) |

Each takes the previous gold as input. `TargetLength` is **4079616** and lives in
`GoldPatch.TargetLength`; `TargetHash`, `EXPECTED_GOLD_SHA256` in
`generate_gold_delta.py`, and `-GoldExe` in `build_kmrp.ps1` all
move together. Getting one out of step is caught by the patcher's own startup
check, which has fired twice in this work — reproduce it against the built
`gold.kup` before shipping rather than after.

## The patches

### Gold v11 — `tools/build_listbox_padding_fix.py`

| VA | vanilla | patched | effect |
| --- | --- | --- | --- |
| `0x0041B1C4` | `03 ef` `add ebp,edi` | `8b ef` `mov ebp,edi` | pitch = rowHeight |
| `0x0041B26B` | `03 f9` `add edi,ecx` | `8b f9` `mov edi,ecx` | pitch (visible-row divisor) |
| `0x0041B553` | `03 cd` `add ecx,ebp` | `8b cd` `mov ecx,ebp` | pitch (advances each row top) |
| `0x0041B48C` | `8d 04 3f 2b c8` | `2b cf 33 ff 90` | `sub ecx,edi ; xor edi,edi ; nop` |
| `0x0041B339` | `03 c2` `add eax,edx` | `8b c2` `mov eax,edx` | fit test uses rowHeight alone |
| `0x0041B3AE` | `03 c2` `add eax,edx` | `8b c2` `mov eax,edx` | fit test uses rowHeight alone |

The `0x0041B48C` entry does two things in five bytes: subtracts `PADDING` once instead of
twice (no right inset), then clears the register the row-top chain starts from
(no gap above row 1). `edi`'s only earlier use, `rect.left`, is already stored.

### Gold v10 — `tools/build_stack_count_fix.py`

The stack-count label, bottom-right-aligned inside the icon box by the row's
`SetRect` at `0x006B5270`. Three of its four operands were **imm8**, capped at
127, so they could not scale past ~2160p. Relocated into a `.ksc` section with
imm32 operands. That is the pattern to copy whenever a fix needs *more bytes
than the original instructions occupy*: replace the run with `jmp stub`, re-encode
the same instructions with room to grow, `jmp` back. `jmp` preserves `esp`, so
`[esp+NN]` references in the stub stay valid.

The invariants that pattern relies on -- and the ways breaking one crashes the
game somewhere entirely unrelated -- are in
[exe-patching.md](exe-patching.md). Read it before editing an executable that
already carries other sections, which by gold v11 is all of them.

## Gold v12 — the gutter follows the scrollbar

Gold v11 made `rect.width = contentWidth - PADDING` for **every** listbox, while
`rect.left` stayed `PADDING` unconditionally. For a list with the bar on the left
that is right. For a **description pane**, whose bar is on the right
(`LEFTSCROLLBAR = 0`), it is backwards: the gutter now sits on the left, away
from the scrollbar, and the text runs up to the bar with no gap. Seen in the
journal, and it applies to every description box in the game.

The gutter should follow the scrollbar. In both cases
`width = contentWidth - PADDING` is already correct; only `rect.left` differs:

```
rect.left = (LEFTSCROLLBAR ? PADDING : 0)
```

### There are TWO rect builders

`0x0041B140` lays out the rows when the content **fits**. When it does not,
`0x0041B3CB` hands off to a second routine at **`0x0041A2D0`** which lays the
single item out on its own, with its own copy of the same arithmetic at
`[esp+0x1C..0x28]`:

```
0041A2EB  movzx edi, byte [esi+0x2C0]   ; PADDING
0041A2F2  lea   eax, [edi+edi]
0041A2F5  sub   ecx, eax                ; width = content - 2*PADDING
0041A2F7  test  ebx, ebx                ; flags consumed by the je at 0x0041A30D
0041A2F9  mov   [esp+0x1C], edi         ; left  = PADDING
0041A2FD  mov   [esp+0x24], ecx
0041A3D0  call  [edx+4]                 ; item->SetRect(rect at [esp+0x1C])
```

Its guard at `0x0041B3B0` compares `PADDING + rowHeight` against the box height,
so builder B is exactly the **"content too tall to fit"** case — a pane that
needs a scrollbar. Patching only builder A left the gutter wrong on precisely
those descriptions long enough to scroll, and right on every shorter one. The
bug was located from that observation: *the symptom tracked a condition*, and
the condition named the branch.

Gold v12 (`tools/build_gutter_side_fix.py`) trampolines **both** into one `.kgs`
section. Two constraints:

- `edi` must survive holding `PADDING` — `0x0041B48C` reads it for the width and
  `0x0041B4A1` for the row-top chain — so the zero goes straight to the stack
  slot rather than by clearing the register.
- `test ebx, ebx` is re-issued **last** in builder B's stub: the `je` at
  `0x0041A30D` consumes its flags and only `mov`s sit between.
- Builder B derives `rect.top` from `edi` as well — `sub ebx, edi` at
  `0x0041A35D` on the bottom-anchored branch, `sub edi, eax` at `0x0041A381`
  otherwise — leaving `top = PADDING` when unscrolled, where builder A writes
  `0`. So a pane long enough to scroll also gained a `PADDING`-tall gap above
  its first line. The stub clears `edi` after storing the left edge, which fixes
  both branches: those two subtractions are its only remaining readers.

The same condition, `content taller than the box`, produced three separate
visible symptoms — gutter on the wrong side, and a top gap — all from builder B
being missed. One branch, several faces.

## Gold v13 — the top gap was a leading newline in the string

Not geometry. Read out of the live text control for Brejik's Arm Band
(x32dbg, 3440x1440), the description string at `textControl+0xEC` begins with
`0A`:

```
0A 44 61 6D 61 67 65 ...   "
Damage Resistance: Resist 5/- vs. Slashing

Brejik's arm band, ..."
```

Everything around it measured correct:

| field | value |
| --- | --- |
| client rect `+0x28C` | `{1759, 774, 1311, 322}` |
| `PADDING` `+0x2C0` | 72 |
| flags `+0x2BC` | `0x25109820` — bit `0x10` clear, bar on the right |
| row height `+0x2B4` | 160 = 4 lines x 40 |
| item rect `[+0x2A8]` | `{0, 0, 1239, 160}` — `1311 - 72` |
| item control `+0x5C` sub-rect | `{0, 0, 1239, 160}` |
| text control `+0xD4` | rect `{0,0,1239,160}`, font `fnt_d16x16b`, string ptr `+0xEC` |
| `PROTOITEM/TEXT/ALIGNMENT` | `9` = left + **top** |

So the listbox hands the text a perfect rect and the text itself starts with an
empty line. The game composes a description by prefixing `
` to each property
line, so an item whose description opens with a property block gets a blank
first line and one composed differently does not — which is exactly why the gap
appeared on some items and not others, on both the inventory and quest-item
panes.

Vanilla behaviour: at 800x600 that blank line is ~16px and passes unnoticed; at
3440x1440 with the enlarged font it is ~40px.

**Fixed in gold v13** (`tools/build_leading_newline_fix.py`). Traced with a
hardware write breakpoint on the text control's string pointer:

```
0055F340  the description builder (properties + prose)
006B3D80  call 0x415E00        ; hand the built string to the control
00415E08  call 0x5E5C50        ; CExoString assign -- the write that was caught
00415E0D  mov eax, [esi+0x50]  ; <- hooked; esi is the CExoString
```

`0x00415E00` is the GUI text setter, so one hook covers every GUI text control,
and it runs at **set** time — which matters, because the line-breaker
(`0x0045A5C9`) and the renderer (`0x0045A806`) are separate passes over the same
string; trimming in only one would make them disagree about where lines start.

`[esi+0]` is the char pointer and `[esi+4]` the buffer **capacity**, not a
length — confirmed at `0x005E5C78`, where the assign compares the incoming
length against it to decide whether to reuse the buffer. The string is
NUL-terminated, so the stub shifts it down in place and loops to strip repeats,
with nothing else to update. The five bytes at `0x00415E0D` are exactly a
`jmp rel32`, so no padding was needed.

The alignment encoding, derived from controls whose appearance is known
(`LBL_CREDITS_VALUE` = `0x14` is right-aligned; `MAIN_TITLE_LBL` = `0x12` is
centred):

| bits | meaning |
| --- | --- |
| `0x01` / `0x02` / `0x04` | left / centre / right |
| `0x08` / `0x10` / `0x20` | top / middle / bottom |

## The fit test — why a description that fits was scrolled anyway

The two guards at `0x0041B339` and `0x0041B3AE` decide between the row layout
and the single-item scrolling layout at `0x0041A2D0`:

```
0041B39B  movzx eax, byte [esi+0x2C0]   ; PADDING
0041B3A2  mov   edx, [esi+0x2B4]        ; rowHeight
0041B3AE  add   eax, edx                ; PADDING + rowHeight
0041B3B0  cmp   eax, ecx                ; vs the box's content height
0041B3B2  jle   0x41B3D8                ; fits -> builder A
0041B3CB  call  0x41A2D0                ; does not -> builder B
```

Adding `PADDING` to a **height** made sense in vanilla, where `PADDING` was row
pitch. Since gold v11 it is a horizontal inset, so it has no business here — and
it opens a window where a pane whose text genuinely fits is routed to the
scrolling layout anyway. Builder B then bottom-anchors a single page
(`0x0041A35B`: `top = contentHeight - rowHeight`), which pushes the text down.

Measured live, an **equipped** robe in the inventory:

| field | value |
| --- | --- |
| client rect `+0x28C` | `{1724, 764, 1346, 342}` |
| row height `+0x2B4` | 320 — the text *fits* in 342 |
| `PADDING` `+0x2C0` | 72 |
| scroll position `+0x2C2` | 1 |
| the test | `72 + 320 = 392 > 342` → builder B |
| resulting top | `342 - 320` = **22px of gap** |

The user's repro named the mechanism exactly: equipping a robe adds property
lines, which grows `rowHeight` into the `contentHeight - PADDING < rowHeight <=
contentHeight` window. Unequip it and it drops below, takes builder A, and sits
flush. Both guards now use `rowHeight` alone.

## Method that works

1. **Find the field, not the pixels.** Start from the `.gui` field name, find
   where the GFF loader stores it, then hardware-watchpoint that offset in a live
   process to catch every reader.
2. **A repro that names a condition is worth more than any amount of staring.**
   "only when the robe is equipped, and only in the inventory" located a
   two-byte bug that four rounds of reading disassembly had missed: equipping
   grows the text into a narrow window where a fit test is wrong. Ask for the
   condition, then find the branch that tests it.
3. **Assume there is a second copy of the code.** Two independent instances of
   this: three pitch computations where I patched one, and two whole rect
   builders where I patched one. A fix that works on some cases and not others
   is the signature — find what separates them and the condition names the
   branch you missed.
4. **Grep for *every* write, not the first.** The single most expensive mistake
   in this work: patching the first matching site and assuming it is the only
   one. `0x0041B1C4` is overwritten by `0x0041B26B` four instructions later, and
   the loop that actually places rows uses a third site at `0x0041B553`. Three
   failed play-tests before a grep for every write to the pitch stack slot
   (`[esp+0x14]`) found them all.
5. **Measure numerically. Never judge by eye.** Read `[listbox+0x2B4]`,
   `+0x2C0`, the rect array — do not count pixels in a screenshot. Two false
   negatives from eyeballing a small UI misdirected an entire session.
6. **Poke memory before writing bytes.** Change the field in the debugger and
   look, then patch.
7. **Watch the encodings.** `83 /r ib` sign-extends above 127; if a constant has
   to scale with resolution it needs the imm32 form and therefore a trampoline.
8. **A fault in a hook you did not touch is not a clue about that hook.** It is
   the signature of shifted section raw offsets. A one-byte insertion in `.kgs`
   crashed the game inside gold v13's `.ktn` stub at `0x00415E16`, and two
   rounds went into explaining how a listbox edit could corrupt a string before
   a byte-level diff against the working build showed every later section
   displaced by one. Diff the two binaries before theorising:
   `len(a) == len(b)` is the whole answer when it is this.
9. **Bisect under the debugger, not in playtests.** `init "<exe>", "", "<dir>"`
   launches the game with nobody touching it; two `run`s and a `state` say
   whether it survived. Build each independent edit alone when a combined one
   fails -- three runs here beat one wrong theory.

### Debugger traps

- x64dbg deletes a `singleshot` breakpoint on its **first hit even when the
  condition is false** — produces a `hit_count` of 0 that reads as proof of the
  opposite of the truth. Never use singleshot with a condition.
- x64dbg expressions are **hex by default**: `>80` means `>128`.
- A stale conditional breakpoint on a hot path (word-wrap at `0x0045A2F0`, 26k
  hits) looks exactly like the game freezing.

## Object layout reference

| what | where |
| --- | --- |
| client rect `{left, top, width, height}` | `+0x28C` / `+0x290` / `+0x294` / `+0x298` |
| embedded scrollbar | `+0x104` (its width at `+0x110`) |
| flags (bit `0x10` = `LEFTSCROLLBAR`) | `+0x2BC` |
| item-rect array / count / capacity | `+0x2A8` / `+0x2AC` / `+0x2B0` |
| **row height** (recomputed as `max(item->height)` every pass) | `+0x2B4` |
| visible row count | `+0x2C4` (word) |
| **`PADDING`** | `+0x2C0` (byte) |
| item-control array / count | `+0x29C` / `+0x2C8` (word) |
| row rect | `+0x04` left, `+0x08` top, `+0x0C` width, `+0x10` height |

`PADDING` is validated at `0x0041C190`: values above **half the width or half
the height** are rejected, so a gutter cannot exceed either.
