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
`693..787`, so `x=698 y=1230 84x84`, filling the portrait height; since
2026-09-24 it is 90% of that (`R3_CUE_SCALE`), `x=702 y=1234 76x76`, still
centred. Where the gap cannot hold that size -- 4:3, 16:10 and 16:9, 6 px at
800x600 -- it goes right of the second portrait instead (`r3_cue_extent` in
`tools/prepare_universal_resources.py`) -- with `CONTROLTYPE 4`, the R3 badge as its
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

## A second use: LT and RT beside the menu tab strip

The same mechanism, and the reason it generalised without changing shape.

The eight menu tabs are **not** in the screens that show them -- `inventory.gui`
and the rest have no tab controls at all. They live in **`top.gui`**, a panel of
its own: eight `LBLH_*` icons at `192x192` and eight `BTN_*` hit areas beneath,
16 controls, highest id 15.

Its panel is found the same way as the others -- the one constructor that binds
`LBLH_EQU`, at `0x00627AF8`:

| | |
| --- | --- |
| vtable | `0x00750148`, stored at `0x006279BB` |
| `ReleaseGff` | `0x00627E21` |
| Draw | `0x0040B760` -- the BASE implementation |

That last row matters: this panel draws with the same base `CSWGuiPanel::Draw`
whose child-walk this whole approach rests on, so nothing new had to be checked.

The two cues are placed from the strip's own geometry rather than from numbers:
its pitch (`BTN_INV.left - BTN_EQU.left`), its height, and its vertical centre,
with each cue one pitch beyond the outermost tab -- where a ninth and a zeroth tab
would sit. At 3440x1440 that puts LT at `166, 129, 120x120` and RT at `3155`.

The only change to the runtime side was the shape of the table, from a list of
panels sharing one tag to a list of (panel, tag) pairs, because `top.gui` wants
two.

## A third: X beside the Skills / Powers / Feats tabs

ABILITIES registers `0x29` -- X -- at `0x006AE714`, and that handler is the whole
confirmation that the cue is honest:

```
006AE726  call 0x5ED690                 the CGuiInGame
006AE72B  movzx eax, byte [eax+0xBC0]   the sub-tab index
006AE732  sub eax, 0    / je ...        0
006AE737  dec eax       / je ...        1
006AE73A  dec eax       / jne ...       2
006AE74D  mov byte [eax+0xBC0], 0       and the third arm wraps
```

A three-state cycle over a byte, which is three sub-tabs.

It needed one new thing and it was small: the cue builder now takes a height as
well as a width, because `Swap_tabs.png` is about two to one rather than square.
Giving the control the same aspect as its texture keeps the engine's stretch
equal on both axes -- the same reasoning the caption badges use in reverse, where
the control's shape is fixed and the ART is pre-compensated instead.

By then the table needed no change at all: ABILITIES simply appears twice.

## A fourth: the A on confirmation boxes (`LBL_KMRPA`)

Added 2026-09-24; documented here the same day, when an audit found it in the
code and `CHANGELOG.md` only. Exit Game, Solo Mode, overwrite save and delete
save all open `CSWGuiMessageBox` with `confirm.gui`. Its `FixMessageLabel`
(`0x006253A0`) shrinks both buttons to fit their captions before drawing, so the
usual badge -- the button's own `BORDER.FILL` -- cannot be used: the texture
would be stretched across a button a fraction of its declared width. The A is a
control of its own instead, moved each frame beside whichever button has focus,
like the main menu's travelling A.

**Build time.** `add_confirm_badge` in `tools/build_controller_layout.py` adds
`LBL_KMRPA` to `confirm.gui`. The file has no plain label to clone --
`LB_MESSAGE` is a list box -- so the struct is `LBL_TITLE` from the Controller
Layout `.gui`, retagged, with `ID` one past the highest, empty text, fill
`kmrpcnfa` and a zero extent, since the runtime sets it. Read from the
2026-09-24 installer: `LBL_KMRPA` is in all 48 `confirm.gui` files with
extent `(0,0,0,0)`, and `kmrpcnfa`, `kmrscnfa`, `kmrncnfa` and `kmrdcnfa` -- one
per family -- are in `override-common.zip`.

**Binding.** `ControllerLayoutReleaseGffK1` in
`src/controller-native/K1ControllerLayout.cpp`, on the same `ReleaseGff` hook
as the cues, binds it when the panel's vtable is `CSWGuiMessageBox`'s
(`0x0074FDB0`) and the `.gui` is still loaded. The Solo Mode query's own vtable,
`0x00756F28`, is accepted too, although that box loads `confirm.gui` from the
base constructor (`0x00626EB0`) with the base vtable still in place. Up to eight
boxes are tracked; a `confirm.gui` without the label binds nothing.

**Per frame** (`updateConfirmBadges`), only while a controller is the active
device, and only while focus (`[panel+0x1C]`) is OK (`panel+0x2F4`) or Cancel
(`panel+0x4B8`):

| step | how |
| --- | --- |
| place it | `SetExtent`, vtable slot 1: a square the button's height, a quarter of that height clear of the button's left edge |
| pick the art | when the family changes, `0x00414C00` on the label's fill at `+0x70`, resref `kmr?cnfa` |
| show or hide | bit `2` of `+0x44`, as for the cues |

Before touching either object it confirms with `VirtualQuery` that the panel,
up to `Cancel+0x14`, and the `0x140`-byte label are still committed memory,
and forgets the entry otherwise -- the check the cue table lacked (see the
correction below). When the box is destroyed, the base destructor's
`ReleaseGff` (vtable reset to `0x0073E010`, `.gui` pointer null) clears the
label's slot in the panel's control array and destroys it.

**Untested in game**, as its `CHANGELOG.md` entry says.

## A fifth: the A beside the highlighted dialogue reply (`LBL_KMRPDLG`)

Added 2026-09-25 (issue #21). The maintainer chose the placement: left of the
highlighted reply's number, following the highlight like the main menu's A. It is
the glyph alone, because the margin left of the numbers is about 64 px at
1080p, too narrow for a caption.

**Build time.** High Resolution Menus ships no `dialog.gui`, so every resolution
except 3440x1440 has always loaded the game's own. To carry the label, the build
now ships `dialog.gui` at every resolution:
- 3440x1440 keeps its tuned file;
- the others get a vanilla-equivalent file rebuilt from the tuned asset by
  `vanilla_dialog_gui` in `tools/prepare_universal_resources.py`.

The rebuild writes back vanilla's 17 geometry values
(`VANILLA_DIALOG_GEOMETRY`). Compared field by field with the game's
`gui.bif` copy, the result differs only in four colour floats, in the seventh
decimal. `add_confirm_badge(..., tag=DIALOG_BADGE_TAG)` then adds the label the
way it adds `LBL_KMRPA`: fill `kmrpcnfa` (the confirm A's art) and a zero
extent. `Test-ControllerPromptAssets.py` checks that every archive has exactly
that label, and that the panel is the tuned one at 3440x1440 and vanilla's
everywhere else.

**Binding.** `ControllerLayoutReleaseGffK1` binds it when the panel's vtable is
`0x00755800`. The dialogue constructor (`0x006A8B40`) stores that vtable at
`0x006A8B6C`, loads `dialog` and calls ReleaseGff at `0x006A8C1E` with it in
place. Destruction is handled by the same base-destructor path as the confirm A.

**Per frame** (`updateDialogBadges`), while a controller is the active device:

| step | how |
| --- | --- |
| replies can be picked | bit 0 of `[panel+0x1DF8]` is clear. When set, a line is playing and A skips it (`0x006A7266`) |
| which reply | `[panel+0x68]`, which the D-pad moves (`0x006A72B9`, `0x006A72DB`), within `[list+0x2A0]` rows |
| where | the row control in `[list+0x29C]`, with `LB_REPLIES` at `panel+0x19C4`. A square one text line high (the shortest row), right edge an eighth of that clear of where the text starts: list left + the scrollbar width (list width − row width). Clamped to the screen, and hidden when the row is scrolled out of the list |
| art | `kmr?cnfa` per family, as for the confirm A |

**Not settled statically, and logged for the play-test:** whether the row rects
are relative to the list or to the panel, and whether `[panel+0x68]` or the
list's own `+0x2C8` is the highlighted row. The code assumes list-relative
rects and `[panel+0x68]`. The first time each conversation shows replies, it
writes a `dialog-geometry` line to `kmrp-layout-lifecycle.log` in the game
folder, at most 24 per session. The line holds the panel and list rects, the row
count, both indices, the flags, the placed rect and the first six row rects. One
conversation in play confirms the placement or says how to correct it.

**The first play-test's log (2026-09-25, 3440x1440):**

```
panel rect=(48,1200,3344,240) list=(-37,0,3344,224) rows=3 highlight=0 listSelected=0
row0=(0,0,3312,32) row1=(0,32,3312,32) row2=(0,64,3312,32) placed=(-77,0,32,32)
```

The rows are list-relative, and both indices agree, so both assumptions held.
But the placement ignored the scrollbar. The rows are 32 px narrower than the
list because the 32 px scrollbar sits on their left, and the A landed at panel
x −77, screen x −29, off the edge. The rule in the table above is the
correction: at 3440x1440 it puts the A at screen x ≈ 7, left of text at ≈ 43.
At 1920x1080 it gives a text start of 48 + 16 = 64 px, the start measured in a
screenshot of that resolution. **The corrected placement is untested in
game.**

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

## Correction, 2026-09-24: the cue table outlived its panels

**Loading a save from in game crashed mid loading screen**, reproducibly, when a
save had already been loaded from the main menu. Every crash was an access
violation at `kmrp-controller.module+0x3CC8`. A reproducible rebuild of the same
module with `/MAP` (byte-identical, SHA-256 `F898853D...`) put that inside
`NativeGuiFrameK1`, at the cue loop's `mov edi, [ecx+0x20]`: the read of a
remembered panel's control array.

The module remembered each bound cue as `(panel, control, id)` and never forgot
one. It judged whether a panel still existed by **reading the panel**
(`GuiCueStillLiveK1`), guarded only by a pointer-range test. Loading a save
destroys every in-game screen; once a freed screen's pages are released, that
read faults. The first load, from the main menu, had no cues to read, which is
why only the second one crashed. The table dates from the R3 cue, 2026-09-15.

Fixed three ways in `K1NativeJoystick.cpp`:

* **Forgotten at the panel's end.** `CSWGuiPanel::~CSWGuiPanel` stores its own
  vtable (`0x0040CF8E  mov [esi], 0x73E010`), then calls ReleaseGff
  (`0x0040CFB2  call 0x40B8F0`, the hooked function), and only afterwards frees
  the control array (`0x0040CFEE`). So `ForgetGuiCuesK1`, run from the ReleaseGff
  hook when it sees that vtable with no `.gui`, can still clear the cue's slot,
  and frees the label -- which also ends the `0x140`-byte leak described below.
  `K1ControllerLayout.cpp` keys its own cleanup on the same pair, and its
  lifecycle log records it firing (`entry-destroy`).
* **Never read unverified.** `GuiCueStillLiveK1` is now a second line of defence
  and checks with `VirtualQuery` that the memory is committed and readable
  before touching it (`IsReadableK1`). The Yes/No badge loop got the same guard.
* **Empty slots first.** Binding reuses a slot only when it is empty, or failing
  that through the guarded liveness test.

Not yet confirmed in game.

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
