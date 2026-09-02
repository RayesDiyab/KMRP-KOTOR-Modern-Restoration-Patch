# Padding and gaps: every kind of box, both axes

How to change the space between a box's frame and the text inside it, for every
control type in the game, so the result is uniform rather than partial.

**Read this first, because it is the trap.** There are two families of text
control and they share no layout code:

| family | count | what they are | has `PADDING`? |
| --- | --- | --- | --- |
| **listboxes** (type 11) | 81 | descriptions, message logs, selection lists | **yes**, `+0x2C0` |
| **plain text controls** (types 4, 6, 7) | 559 with text | labels (310), buttons (231), toggles (18) | **no** |

Surveyed across all 82 shipped `.gui` files. Only listboxes have a `PADDING`
field at all; the other 559 carry nothing but `EXTENT` and `BORDER`.

So **any change made through `PADDING` or `CAurGUIListBox` reaches 81 boxes and
misses 559.** That was tried in this project and reverted: a top inset added in
both listbox rect builders gave a gap in descriptions and logs and none in
labels or buttons, which reads worse than no gap at all. Uniform-and-flush beats
partial-and-padded. If you change one family, you must change the other in the
same pass or not ship it.

---

## Family A: listboxes

Laid out by `CAurGUIListBox`. One code path for every listbox in the game — see
[listbox-geometry.md](listbox-geometry.md) for the object layout and the two
rect builders.

### Horizontal

`PADDING` (`+0x2C0`, a **byte**) since gold v11 is a purely horizontal inset,
and since v12 it follows the scrollbar:

```
rect.left  = LEFTSCROLLBAR ? PADDING : 0
rect.width = contentWidth - PADDING
```

**One-sided by design** — the gap lands on the scrollbar's side and the opposite
edge gets nothing but the border. To make it symmetric you must undo v12's
conditional (unconditional `rect.left = PADDING`) *and* restore the doubled
subtraction (`width = content - 2*PADDING`) in **both** builders: builder A in
the `.kgs` fit stub, builder B at its own copy of the arithmetic. Keep v11's
vertical fixes — the doubling is separable from the row pitch.

Where the values live:

| | |
| --- | --- |
| description panes | `GUTTER_AT_UNIT_SCALE = 36.0` → 72px at 3440x1440 |
| icon selection lists | `LIST_GUTTER_AT_UNIT_SCALE = 12.5` → 25px |
| which tags get which | `DESCRIPTION_LISTBOXES` / `LIST_LISTBOXES` in `prepare_universal_resources.py` |
| applied by | `tools/scale_listbox_padding.py`, scaled by `font_scale_for(height)` |

`apply()` never *reduces* a gutter an author set larger, so passes can be
layered; run the smallest tier last with `tags=None` to catch everything else.

**Two limits.**

* `PADDING` is validated at `0x0041C190`: a value greater than half the client
  width **or** half the client height is rejected — the setter skips the store
  and returns. It is a silent no-op, never a fault, so an over-large gutter
  fails by doing nothing.
* A listbox already carries an invisible margin. The client rect at
  `0x0041BF80` always does `width -= scrollbarWidth`, and adds it to `left` when
  `LEFTSCROLLBAR` is set, whether or not a bar is showing. That margin is the
  scrollbar's authored `EXTENT/WIDTH` — 64-95px in the HD layout — so measure
  the client rect at `+0x28C`, not the `.gui` `EXTENT`, before deciding a gutter
  looks wrong.

**Exclude icon lists.** `LB_ACTIONS0..5` (the HUD combat queue) are listboxes of
icons, not text: a gutter shifts the queue rather than opening a margin. They
live in the `mipc*.gui` HUD variants and are the only non-text listboxes a
blanket pass reaches.

### Vertical

Gold v11 removed `PADDING` from every vertical job — three row-pitch sites and
the row-top seed — because one byte driving both made the field unusable. **Do
not put it back.** Row pitch is now `rowHeight` alone.

The top of the first row is set per builder, both inside the `.kgs` stubs:

| builder | when | lever |
| --- | --- | --- |
| A — `0x0041B140` | content fits | `mov dword [esp+0x24], imm32` at `.kgs+0x17` |
| B — `0x0041A2D0` | content scrolls | the `edi` seed at `.kgs+0x41`, read by `sub ebx,edi` (`0x0041A35D`) and `sub edi,eax` (`0x0041A381`) |

Builder A's is already an imm32, so it costs no bytes. Builder B's needs three
bytes for `push imm8 / pop edi` where two are free — grow into the section's
padding and **overwrite, never insert** (see [exe-patching.md](exe-patching.md);
getting this wrong crashed the game on launch).

Patch both or neither: builder B is chosen whenever the content is taller than
the box, so patching only A insets short panes and not scrolling ones.

Bottom padding is not exposed. There is no field or site for it.

---

## Family B: labels, buttons, toggles

No `PADDING`. The available levers, in the order worth trying:

**1. `EXTENT` — always works, never uniform.** Shrinking a control's rect insets
its text. It is per-control, so 559 edits, and it moves the frame too. Use only
for one-off fixes.

**2. `BORDER.INNEROFFSET` — the likely lever, not yet verified.** Loaded by the
GUI reader and stored on the border object:

```
00415503  push 0x0073E354       ; "INNEROFFSET"
0041550F  call 0x00411C90       ; the GFF get-int helper
00415514  mov [ebx+0x18], eax   ; -> border+0x18
```

Authors use it deliberately — buttons carry 9, 4, 14 and 10; labels carry 12 and
−5; toggles ±4 — so it does *something*. What it does geometrically is
**unverified**, and one negative result exists: set on a listbox's
`LB_DESCRIPTION` alongside `PADDING`, it changed nothing. That may mean it is
ignored on listboxes specifically rather than generally.

To settle it, follow the project's own method: hardware-watchpoint `border+0x18`
on a live control and catch every reader. Do that before writing any patch —
if `INNEROFFSET` already insets text on labels and buttons, uniformity is a
`.gui` change with no exe patch at all, which is by far the best outcome
available here.

**3. `TEXT.ALIGNMENT` — positions, does not pad.** Bits, derived from controls
whose appearance is known:

| bits | meaning |
| --- | --- |
| `0x01` / `0x02` / `0x04` | left / centre / right |
| `0x08` / `0x10` / `0x20` | top / middle / bottom |

Loaded at `0x00416197` and `0x00416F7E`. Centring is not padding — it changes
where text sits when there is slack, and does nothing when the text fills the
box.

**4. The text setter, `0x00415E00` — universal, but content not geometry.**
This is the one place every GUI text control passes through, which is why gold
v13 hooked it to strip leading newlines. It receives the string, not the rect,
so it can change what is drawn but not where. Worth knowing it exists: a
vertical gap that varies per item is usually a leading `\n` in the string, not
geometry — that was v13's finding, and it is why some item descriptions had a
top gap and others did not.

---

## The procedure for a uniform result

1. **Decide the number once**, at unit scale, and derive every value from it by
   `font_scale_for(height)`. A gap authored in pixels at one resolution is wrong
   at all the others.
2. **Settle `INNEROFFSET` first** (family B, step 2). Everything downstream
   depends on whether family B is a `.gui` change or an exe patch.
3. **Family B, horizontal and vertical**, by whatever step 2 established.
4. **Family A, horizontal** — `scale_listbox_padding.py`, all three tiers, with
   `LB_ACTIONS0..5` excluded. Decide one-sided or symmetric and apply it in both
   rect builders.
5. **Family A, vertical** — both `.kgs` stubs, or neither.
6. **Verify by measurement, not by eye.** Read the client rect at `+0x28C`,
   `PADDING` at `+0x2C0`, and the item rect at `+0x2A8` in a live process. Two
   false negatives from eyeballing a small UI cost a whole session once already.
7. **Check one control of each type**: a description pane, a message log, a
   selection list, a plain label, a button. If any one of the five differs, the
   change is partial and should not ship.

## What not to do

* Do not ship a listbox-only change. 81 boxes vs 559.
* Do not use `PADDING` for anything vertical. v11 removed those uses on purpose.
* Do not exceed half the client width or height — silently ignored.
* Do not patch one rect builder. There are always two.
* Do not grow a stub by inserting bytes. See [exe-patching.md](exe-patching.md).

## Open questions

* **What does `BORDER.INNEROFFSET` actually do, and on which control types?**
  The single most valuable unknown here — it decides whether family B needs an
  exe patch at all. Anchor: `border+0x18`, stored at `0x00415514`.
* **Is there any bottom-padding lever?** None found for either family.
* **`BORDER.DIMENSION`** is the frame artwork's edge thickness (0, 1, 2, 4, 6
  and 16 in the shipped files). Whether it also insets text is untested.
