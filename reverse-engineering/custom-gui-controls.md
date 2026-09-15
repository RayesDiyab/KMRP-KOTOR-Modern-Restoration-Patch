# Adding a control the game never had

**Status: fully measured, implementation in progress.**
Everything below was read out of the tracked gold image
(`build-inputs/swkotornopatch.exe`) statically. Where a claim came from watching
the game instead, it says so.

The motivating case: R3 changes which party member Character, Equipment,
Inventory and Skills/Powers/Feats are showing, and there is nowhere to put the
cue. The portraits' `BORDER.FILL` *is* the portrait, rewritten per character; the
94px gap between them holds no control; and no spare control exists to move
there -- Inventory has 15 controls and uses all of them.

## Why a control added to a .gui is never drawn

Recorded in `docs/controller-support.md` as an observation about `mainmenu.gui`
with an explanation attached. Both halves now have evidence.

Confirmed by experiment first: a label cloned from `BTN_CHANGE2`, retagged,
moved into the gap and given a portrait as its fill was added to a live
`inventory.gui` (16 controls, 14,376 bytes). Nothing appeared.

The reason is in the binder. A panel does not load the file's controls; it asks
for the ones it knows by name:

```
0040B930  CSWGuiPanel::BindControl(control, tag, addToArray)
0040B948  call 0x418840        control->InitFromGui(panel, [panel+0x2C], &[panel+0x30], tag)
0040B956  mov  edi, [ebp+0x50] the control's ID
0040B95D  mov  eax, [esi+0x24] the panel's control-array COUNT
0040B964  mov  eax, [esi+0x20] the panel's control-array BASE
0040B967  mov  [eax+edi*4], ebp store the control pointer AT INDEX = its ID
```

and `0x418840` resolves the tag by walking the GFF:

```
00418874  call 0x411940        get the CONTROLS list
004188A1  call 0x411990        struct at index i
004188BE  push 0x73E470        "TAG"
004188D4  call 0x411EC0        read it, compare
```

So the `.gui` is a **lookup table keyed by tag**, not a list that is
instantiated. A control nobody asks for is never constructed, which is why there
was nothing to draw.

## Why registering one IS enough to draw it

`CSWGuiPanel::Draw` -- vtable slot 6, base implementation `0x0040B760`, which
ABILITIES uses unmodified while CHARACTER, EQUIP and INVENTORY override it --
ends by walking that same array:

```
0040B831  xor  edi, edi
0040B833  test ebp, ebp            the child count
0040B837  mov  eax, [esi+0x20]     the array
0040B83A  mov  ecx, [eax+edi*4]    child i
0040B83D  test ecx, ecx / je       a null slot is skipped
0040B841  test byte [ecx+0x44], 2  the visible bit
0040B847  mov  edx, [ecx]
0040B84A  call [edx+0x38]          child->Draw
```

Three things follow, and they are what make this feasible:

* a control in the array is drawn, with no other registration anywhere;
* **holes are skipped**, so growing the array past the existing IDs is safe;
* visibility is one bit -- `+0x44 & 2` -- which is how the cue would follow the
  pad without touching any fill.

The binder already grows the array when an ID lands past the end
(`0x0040B970` onwards, pushing through `0x671C00` until the count passes the
index), so a high ID needs no separate allocation.

## The class, and its size

`BTN_QUESTITEMS` on INVENTORY is the embedded object at `panel+0x14EC`, and a
button like the two portraits:

```
006B35CF  call 0x41C0F0   ecx = panel+0x14EC    constructor
006B41C9  call 0x419DA0   ecx = panel+0x14EC    destructor
```

Found by searching the image for the byte pattern of a `lea` with displacement
`0x14EC` rather than by disassembling around the bind site: decoding from an
arbitrary offset had rendered `0x006B35C4` as a bogus `dec dword [ebp+0x14EC8E]`
and hidden the constructor entirely. This is the same failure
`tools/extract_control_offsets.py` documents.

The object size comes from the spacing of the two portrait buttons, which agree
on three independent panels:

| panel | BTN_CHANGE1 | BTN_CHANGE2 | delta |
| --- | --- | --- | --- |
| ABILITIES | `0x3860` | `0x3A24` | `0x1C4` |
| EQUIP | `0x3A20` | `0x3BE4` | `0x1C4` |
| CHARACTER | `0x4B2C` | `0x4CF0` | `0x1C4` |
| INVENTORY | `0x16B0` | `0x1874` | `0x1C4` |

So a button is **`0x1C4` bytes**, agreed by four panels.

INVENTORY's `BTN_CHANGE1` is `0x16B0`, and `0x14EC` is `BTN_QUESTITEMS`.
`tools/extract_control_offsets.py` gave both the same offset until it was fixed;
43 of its 673 rows were wrong the same way. See its docstring.

### The label

```
006B350F  call 0x41ACD0   ecx = panel+0x1A4    CSWGuiLabel constructor
006B43A3  mov [edi], 0x73E5B8                  its vtable
```

**`CSWGuiLabel` is `0x140` bytes**, measured from INVENTORY's adjacent embedded
labels -- `LBL_INV 0x01A4`, `LBL_CREDITS 0x02E4`, `LBL_CREDITS_VALUE 0x0424`, a
`0x140` step twice.

### The layouts these sizes come from

`Lane-reference/swkotor.exe.h` is a Ghidra export of a **GOG** build, so its
addresses do not apply here, but its class layouts do -- and they reproduce both
measured sizes exactly:

```
CSWGuiControl    0x5C     ... bit_flags at 0x44, id at 0x50
CSWGuiNavigable  0x5C + 0x10          = 0x6C
CSWGuiBorder     0x74     { vtable, extent at 0x04, border_params at 0x14, ... }
CSWGuiText       0x70
CSWGuiLabel      0x5C + 0x74 + 0x70          = 0x140   (measured: 0x140)
CSWGuiButton     0x6C + 0x74 + 0x74 + 0x70   = 0x1C4   (measured: 0x1C4)
```

Two of those fields are ones this document already relies on, and the reference
names them: `bit_flags` at `control+0x44` is what Draw tests, and `id` at
`control+0x50` is what the binder uses as the array index. Both were read out of
the code first, and agree.

It also accounts for the module's own constants. A button's `border_1` begins at
`0x6C`, and `CSWGuiBorderParams` sits `0x14` into a border -- which is `0x80`,
`K1_BUTTON_BORDER_PARAMS_OFFSET`. `border_2` begins at `0xE0`, giving `0xF4`,
`K1_BUTTON_HILIGHT_PARAMS_OFFSET`. Inside the params, `fill_image_resref` is at
`+0x40`, the offset `SetFillImage` writes.

## When the window closes: the panel throws its GFF away

`0x0040B8F0` is `CSWGuiPanel::ReleaseGff`:

```
0040B8F3  test byte ptr [esi+0x44], 2   only if it still holds one
0040B8F9  mov  ecx, [esi+0x2C]          the CResGFF
0040B8FC  call 0x409B80
0040B908  mov  eax, [ecx] / call [eax]  delete it
0040B911  and  eax, 0xFFFFFFFD          clear the flag
0040B914  mov  dword ptr [esi+0x2C], 0  and null the pointer
```

**68 callers, one per panel constructor**, each immediately after that panel
finishes binding its controls. So `panel+0x2C` is null for the entire time a
screen is on screen, `0x418840` can never resolve a tag again, and there is
exactly one moment when a control can be added: inside the constructor, before
this call.

That moment is also the cleanest possible hook, because the call site is the same
five bytes on every panel and the panel is already in `ecx`:

| panel | release site | preceding instruction |
| --- | --- | --- |
| ABILITIES | `0x006AE38D` | `mov ecx, esi` |
| CHARACTER | `0x006B1F0A` | `mov ecx, esi` |
| EQUIP | `0x006BB283` | `mov ecx, esi` |
| INVENTORY | `0x006B39C1` | `mov ecx, esi` |

Detour the `call`, bind the new control, then call the original. Nothing else in
the constructor is touched, and a panel we do not patch behaves exactly as before.

## Visibility is the engine's own bit, written directly

`bit_flags & 2` at `control+0x44` -- the bit `Draw` tests -- is set and cleared by
ordinary read-modify-write, by the engine, on itself:

```
0040A854  or  dword ptr [esi+0x44], 2      set when a control loads successfully
006B1EF2  and dword ptr [ecx], 0xFFFFFFFD  cleared on each of LBL_GOOD1..10
```

The second is from CHARACTER's constructor, in the loop that binds the ten
alignment-meter labels and then hides them:

```
006B1EC6  push 0x756184                "LBL_GOOD%d"
006B1EE2  add  ecx, -0x44              the control is (stored pointer - 0x44)
006B1EE9  call 0x40B930                bind
006B1EF2  and  dword ptr [ecx], ~2     hide
006B1EF9  add  ecx, 0x140              the next label
```

So driving that bit from outside is not a trick; it is what the game does. The
`add ecx, 0x140` is also a third independent confirmation of the label size, and
this loop is one of the sprintf-generated clusters
`tools/extract_control_offsets.py` declines to resolve -- correctly, since the
control address here is computed rather than a constant offset.

## The implementation

Every part of this is now measured.

**Build time.** Author `LBL_KMRPR3` into the four `.gui` files, positioned from
the two portraits' real extents at each resolution -- at 3440x1440 the gap is
`693..787`, so `x=698 y=1230 84x84` -- with `CONTROLTYPE 4`, the R3 badge as its
`BORDER.FILL`, and an `ID` of `max + 1` for that file: ABILITIES 20,
CHARACTER 66, EQUIP 41, INVENTORY 16.

**Runtime.** Detour the four `call 0x0040B8F0` sites. In the shim, with the panel
in `ecx`:

1. `operator new(0x140)`;
2. call `0x0041ACD0` on it -- `CSWGuiLabel::CSWGuiLabel`;
3. call `0x0040B930(panel, control, "LBL_KMRPR3", 1)`, which reads the `.gui`
   while it is still loaded and files the control at its ID;
4. call the original `0x0040B8F0`.

**Per frame.** Set or clear `control+0x44 & 2` from the pad state, exactly as the
badges are driven now, and the cue appears and disappears with the controller.

The control is never freed by us. The panel owns its children and its destructor
walks the same array, so the object's lifetime is the panel's -- which is also
why the allocation must come from the engine's own `operator new`, the one the
module already calls as `K1_OPERATOR_NEW`.

The glyph art is already selected: `XboxSeriesX_Right_Stick_Click.png`, mapped as
`R3` in `tools/build_controller_prompt_textures.py`.

## The three safety questions, answered

### Does a label bound this way draw, with a fill and no text?

Yes. `CSWGuiLabel::Draw` is `0x00417750` and has no conditions in it at all:

```
00417758  lea ecx, [esi+0x5C]   the border -> virtual draw
00417762  lea ecx, [esi+0xD0]   the text   -> virtual draw
00417774  ret 4
```

It draws the border -- which is where the fill lives -- then asks the text object
to draw, and an empty string draws nothing. No special case is needed, and the
`0x5C` / `0xD0` offsets are the ones the constructor itself uses.

### Does `0x0041ACD0` take arguments beyond `this`?

No. It ends in a bare `ret`, not `ret N`, so it is `__thiscall
CSWGuiLabel::CSWGuiLabel(void)` and returns `this` in `eax`. It is also a clean
confirmation of the whole layout:

```
0041ACED  call 0x41AA80         CSWGuiControl base constructor
0041ACFD  mov  [esi], 0x73E5B8  the vtable
0041ACF2  lea  ecx, [esi+0x5C]  CSWGuiBorder ctor 0x004167F0   -- control is 0x5C
0041AD08  lea  ecx, [esi+0xD0]  CSWGuiText   ctor 0x00417280   -- 0x5C + 0x74
```

`0xD0 + 0x70 = 0x140`, which is the fourth independent agreement on the size.

### Will the panel destructor mishandle a child it did not construct in place?

**No, and it will not free it either.** Two findings:

* The derived destructor (`0x006B40C0` for INVENTORY, reached through the
  scalar-deleting stub at `0x006B4B90`) destroys each embedded control **in
  place, by fixed offset** -- `0x006B41C9  call 0x419DA0` with
  `ecx = panel+0x14EC`. Across 500 decoded instructions it never references the
  control array at `+0x20`/`+0x24`.
* Nothing anywhere can be freeing array entries, and this follows from vanilla
  correctness rather than from reading every destructor: **every entry in that
  array is an embedded object inside the panel**. Calling `operator delete` on
  one would corrupt the heap in the stock game.

So a heap-allocated control registered in the array is simply never freed.

That is a **leak, not a crash** -- `0x140` bytes each time one of the four panels
is constructed. And these panels are per-construction heap objects: both call
sites of the INVENTORY constructor read

```
0062B28A  push 0x1DE8      sizeof(CSWGuiInGameInventory) = 7,656 bytes
0062B28F  call 0x6FA7E6    operator new
0062B2B1  call 0x6B34C0    the constructor (one stack argument besides this)
```

so if a panel is rebuilt per screen-open, the engine is allocating 7,656 bytes
where we add 320 -- about 4%. Whether that is worth removing is a judgement call,
and there are two ways to remove it: detour the four destructors as well and free
our control there, or keep one buffer per panel type in the module and construct
into it, which is only safe if two instances of one panel never coexist -- itself
unproven.

Nothing here blocks implementation.

## Verified: the array's destructor frees storage, nothing else

The argument above -- that nothing frees array entries, because vanilla would
corrupt its own heap -- is now a direct reading. `CSWGuiPanel::~CSWGuiPanel` is
`0x0040CF70`, and the derived destructor chains to it (`0x006B4411` with the
panel in `ecx`). It disposes of the control array through one call:

```
0040CFE6  lea  ecx, [esi+0x20]      the CExoArrayList
0040CFEE  call 0x56B6F0

0056B6F0  mov  esi, ecx
0056B6F3  mov  eax, [esi]           .data -- the pointer array
0056B6F6  call 0x6FA390             operator delete: the ARRAY
0056B6FE  mov  dword ptr [esi], 0
0056B705  ret
```

Nine instructions, and not one of them dereferences an element. The storage is
freed; what the pointers point at is untouched.

So the ownership story is complete and there are no surprises in it:

* embedded controls are destroyed in place by the derived destructor, at fixed
  offsets, exactly as they were constructed;
* the array itself is freed as a block;
* a control we allocate and register is never freed by anything -- a `0x140`
  byte leak per panel construction, against the `0x1DE8` the engine allocates
  for the panel itself.

Nothing in this document is now unverified.
