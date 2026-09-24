# Issue #14: the white flash — analysis in progress

**Superseded by [texture-residency.md](../texture-residency.md)**, which carries the same findings plus the residency mechanism and two corrections this file predates. Kept for the issue-#14 framing and the measurement plan.

**Status: no conclusion yet, and nothing changed.** This records what is
established numerically, what was got wrong along the way, and the reads that
would settle it. Written 2026-09-15 from static analysis of the gold image plus
the Ghidra archive; no patching, no experiments on the live game.

## The Ghidra archive matches this build exactly

`Lane-reference/k1_win_gog_swkotor.exe.xml` was assumed to be a different
(GOG) build whose addresses would not apply. **They do apply.** Checked against
nine addresses derived independently, from disassembly, earlier the same day:

| address | derived as | archive name |
| --- | --- | --- |
| `0x0040B930` | the tag binder | `CSWGuiPanel::InitControl` |
| `0x00418840` | resolves a tag against the GFF | `CSWGuiControl::Load` |
| `0x0040B760` | base panel draw, walks the child array | `CSWGuiPanel::Draw` |
| `0x0040B8F0` | deletes the parsed .gui | `CSWGuiPanel::StopLoadFromLayout` |
| `0x0041ACD0` | the label constructor | `CSWGuiLabel::CSWGuiLabel` |
| `0x0056B6F0` | frees the control array's storage | `CExoArrayList::~CExoArrayList` |
| `0x005E5A90` | CExoString from a literal | `CExoString::CExoString` |
| `0x006FA7E6` | the allocator | `operator_new` |
| `0x00414C00` | writes a border's fill resref | `CSWGuiBorderParams::SetFillImage` |

Nine for nine. **30,840 symbols, 24,242 of them functions**, indexed to
`symbols.json` in the session scratchpad. Every previous RE session in this repo
worked without this; it should be the first stop from here on.

## Established, with numbers

**The texture budget is data, not code.** `CClientExoAppInternal::SetTexturePack`
(`0x005F14A0`) loads `texpacks.2da` and feeds `AurTextureSetMem` (`0x00421D90`)
and `AurTextureSetDynamicMemoryRatio` (`0x0041E9B0`). Read out of the live
installation:

| desc | texture pack | `mem` | `dynmemratio` | product |
| --- | --- | ---: | ---: | ---: |
| 32MB_32BIT | `swpc_tex_tpc` | 31,457,280 | 0.750 | 23,592,960 |
| 64MB_32BIT | `swpc_tex_tpb` | 62,900,000 | 0.750 | 47,175,000 |
| 128MB_32BIT | `swpc_tex_tpa` | 134,217,728 | 0.750 | 100,663,296 |

The reporting machine's `swkotor.ini` has `Texture Quality=2`, the top row.

**That product is recomputed every frame.** `AurTextureMakeCurrent`
(`0x00421EE0`) does `fild maxTexMemory; fmul aurDynamicMemoryRatio; frndint`
into a local, drains a refresh queue through
`AurTextureBuildAndStoreAll` (`0x004217F0`), and updates
`maxTextureTime`, `currentTextureTime`, `loadImageTime` and
`maxTextureLoadTime`. A per-frame texture budget with timing instrumentation is
not something an engine carries unless loading is deferred across frames.

**KMRP's shared GUI art, measured from the built `override-common.zip`**: 778
textures, 371,185,976 bytes (354 MB). 98 of them are 1 MB or larger. The font
atlases alone, which essentially every screen needs:

    dialogfont32x32.tga   16,777,234
    fnt_galahad14.tga      4,194,322
    fnt_dialog16x16.tga    4,194,322
    fnt_d16x16a.tga        4,194,322
    fnt_d16x16b.tga        4,194,322
                          -----------
                           33,554,522   ~32 MB

and the largest backgrounds are 6,220,844 bytes (5.9 MB) each.

## Got wrong, and corrected here so nobody repeats it

The loop in `AurTextureBuildAndStoreAll` at `0x00421892` compares `[0x7A4790]`
against `[0x7A4794]` and was read as an accumulator against a memory cap. **It is
not.** It is `std::vector` growth:

```
00421892  mov eax, [0x7A4794]      capacity
00421897  cmp [0x7A4790], eax      count
004218A9  add eax, eax             double it
004218AD  mov eax, 8               ...or 8 from empty
004218C1  call operator_new
004218E0  copy loop
004218FC  call operator_delete     free the old block
0042190F  mov [eax + ecx*4], ebp   array[count] = item
```

`[0x7A4794]` is a capacity in elements, `[0x7A4790]` a count. No byte budget is
being enforced there.

## Not established

1. **What the per-frame `maxTexMemory x ratio` figure actually gates.** It is
   computed; where it is consumed has not been traced.
2. **What is drawn when a texture is not resident.** This is the whole question
   and it is still open. `CAurTexture::IsFullyLoaded` (`0x0041EC10`) has **zero
   direct callers**, so it is reached virtually or inlined, and the obvious
   thread does not pull.
3. **Whether the controller layer is involved at all.** The issue is written
   around party switching with controller-layer suspects, but the report has
   since widened to "GUI screen transitions generally, and not every time",
   which no longer implicates the pad.

There is one precedent worth keeping in view: this repo has shipped white
before. `tools/check_controller_drift.py:143` records that a button whose
`BORDER.FILL` names a texture that was never packaged "loses its art entirely and
draws flat white". So in this engine an unresolved fill does draw white -- but
that was a permanently missing file, not a transient load, and the two need not
share a code path.

## What to read next

* `CSWGuiBorder::Draw` (`0x004168C0`) through `FillCenter` (`0x004157F0`) and
  `FillTile` (`0x004155B0`) to the actual GL call, and what texture id is bound
  when the `CAurTexture` at `border+0x70` has no GL object yet.
* `CAuroraTexture::Load` / `::Unload` (`0x0070EBF0` / `0x0070EC70`) and
  `AurTextureRefreshAll` (`0x00422360`): what evicts a texture, and on what
  trigger.
* The vtable slot that `IsFullyLoaded` occupies, to find its real callers.

## What to measure, when the machine is free

Two questions, both cheap, and the first splits the search space in half:

1. **Does the flash happen navigating with the mouse only, no controller?**
   Yes -> the controller layer is out, and this is about texture residency.
   No -> it is our layer, and the fill writes are the only thing that swaps a
   fill.
2. **Does it recur on a screen already visited in the same session?**
   Only-on-first-visit is a load; recurring is eviction.

A third, if the first two leave it open: set Texture Quality to 32MB and see
whether the flash becomes constant. If the budget is involved, shrinking it four
fold should make the effect obvious rather than intermittent -- and if nothing
changes, the budget is not the mechanism.
