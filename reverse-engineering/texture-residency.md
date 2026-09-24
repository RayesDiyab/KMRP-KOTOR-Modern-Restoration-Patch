# How Aurora keeps textures resident, and how a quad ends up white

Static analysis of the gold image, cross-read against the Ghidra archive in
`Lane-reference/`. Nothing here was patched or tested in game; the confidence of
each claim is marked, and the unproven links are named rather than glossed.

## The archive applies to this build

`Lane-reference/k1_win_gog_swkotor.exe.xml` is a Ghidra export of a GOG build and
was assumed not to share addresses with the 1.0.3 image this project patches.
**It does.** Nine addresses derived independently from raw disassembly on
2026-09-14/15 all resolve to matching names:

| address | derived as | archive name |
| --- | --- | --- |
| `0x0040B930` | the tag binder | `CSWGuiPanel::InitControl` |
| `0x00418840` | resolves a tag against the GFF | `CSWGuiControl::Load` |
| `0x0040B760` | base panel draw, walks the child array | `CSWGuiPanel::Draw` |
| `0x0040B8F0` | deletes the parsed .gui | `CSWGuiPanel::StopLoadFromLayout` |
| `0x0041ACD0` | the label constructor | `CSWGuiLabel::CSWGuiLabel` |
| `0x004167F0` | the border constructor | `CSWGuiBorder::CSWGuiBorder` |
| `0x0056B6F0` | frees the control array's storage | `CExoArrayList::~CExoArrayList` |
| `0x005E5A90` | CExoString from a literal | `CExoString::CExoString` |
| `0x00414C00` | writes a border's fill resref | `CSWGuiBorderParams::SetFillImage` |

**30,840 symbols, 24,242 functions.** It also carries struct layouts, which is
how `downsamplemax` below is named rather than guessed. Start here before
disassembling anything.

Two cautions, both learned the hard way in one session:

* its **function names are authoritative, its field names are not**. Ghidra
  labelled `CSWGuiBorderParams`'s first four ints `x, y, width, height`; the GFF
  parser proves they are `DIMENSION` and `INNEROFFSET`. Where a name and the code
  disagree, the code wins.
* it does not remove the need to read. Two separate misreadings below were caught
  only by reading the instructions.

## The budget is data

`CClientExoAppInternal::SetTexturePack` (`0x005F14A0`) loads **`texpacks.2da`**
and feeds `AurTextureSetMem` (`0x00421D90`) and
`AurTextureSetDynamicMemoryRatio` (`0x0041E9B0`). Read from the installed game:

| desc | pack | `mem` | `dynmemratio` | product |
| --- | --- | ---: | ---: | ---: |
| 32MB_32BIT | `swpc_tex_tpc` | 31,457,280 | 0.750 | 23,592,960 |
| 64MB_32BIT | `swpc_tex_tpb` | 62,900,000 | 0.750 | 47,175,000 |
| 128MB_32BIT | `swpc_tex_tpa` | 134,217,728 | 0.750 | 100,663,296 |

`swkotor.ini`'s `Texture Quality` selects the row. On the machine reporting the
white flash it is `2` -- the top row, so **100,663,296 bytes**.

`AurTextureMakeCurrent` (`0x00421EE0`) recomputes `maxTexMemory x
aurDynamicMemoryRatio` every frame, drains a refresh queue, and keeps
`maxTextureTime`, `currentTextureTime`, `loadImageTime` and
`maxTextureLoadTime`. An engine does not carry per-frame load timing unless
loading is spread across frames.

## Over budget means DOWNSAMPLE, not evict

This is the part that was expected to be an eviction cache and is not.

`AurTextureMemCheck` (`0x00421AC0`) calls `AurTextureCalculateNewTexMem`
(`0x00420DB0`), compares the result against the budget, and when it is over walks
a texture list adjusting fields at `+0xB8` and `+0xBA`. The archive's
`CAurTextureBasic` layout names them:

    short downsamplemax;    // +0xB8
    short downsamplemin;    // +0xBA

So the engine keeps every texture and **reduces its resolution** to fit, rather
than dropping textures entirely. `CAurTextureBasic::FreeImage` (`0x0041F570`) has
exactly **one** caller, the destructor -- nothing frees a texture's image to make
room.

A downsample is not free: the texture has to be rebuilt and re-uploaded, which is
what `aurRefreshTextures` / `AurTextureBuildAndStoreAll` (`0x004217F0`) and
`CAurTextureBasic::BuildAndStoreTexture` (`0x004216A0`) exist for.

## The GUI fill draw chain, end to end

Every step below is named in the archive and was followed in the disassembly.

```
CSWGuiPanel::Draw            0x0040B760   walks the child array, gates on bit_flags & 2
  control->Draw              vtable +0x38
    CSWGuiBorder::Draw       0x004168C0
      CSWGuiBorder::FillCenter  0x004157F0     (or ::FillTile 0x004155B0)
        image->GetImageWidth    CAurGUIImageInternal vtable +0x10
        image->GetImageHeight                        vtable +0x0C
        image->Draw                                  vtable +0x18  -> 0x00459920
```

`FillCenter` is nine instructions of arithmetic around three virtual calls on the
object at **`border+0x70`**, and nothing else. It is not where a decision is made.

**`border+0x70` is a `CAurGUIImage*`.** `CSWGuiBorderParams::SetFillImage`
(`0x00414C00`) owns it:

```
00414C37  mov  eax, [eax + 0x70]      the existing image
00414C44  call [edx + 4]              its virtual destructor, flag 1
00414C4A  mov  [eax + 0x70], 0        cleared first
00414C53  call CResRef::IsValid       an empty resref stops here
00414C6D  call NewCAurGUIImage
00414C78  mov  [ecx + 0x70], eax      the replacement
```

So writing a fill resref destroys the previous image and builds a new one, and an
**empty** resref leaves `border+0x70` null -- which is why clearing a fill removes
the art rather than showing a blank texture.

**`NewCAurGUIImage` (`0x0045A260`) never returns null for a name it cannot
resolve.** It unconditionally allocates 8 bytes and constructs a
`CAurGUIImageInternal`, choosing between two constructors purely on whether a
name was passed (`0x00459790` for none, `0x004598A0` for one). A missing texture
therefore yields a perfectly valid image object; the failure is carried inside
it, as a texture id.

`CAurGUIImageInternal::Draw` (`0x00459920`) computes its UVs by indexing a
texture-dimension table -- `0x007B946C` / `0x007B946E`, stride 10 bytes, indexed
by the id at `0x007B9460` -- and divides the quad's corners by those dimensions.
The class keeps `CAurGUIImage::guiTID` (`0x007BB4D8`), `::material`, `::alpha`
and `::isVTC` as globals.

## Where white comes from — answered

A fill's name becomes a texture in `Material::InitializeTextures` (`0x0047B560`),
and it has exactly two outcomes:

```
0047B565  test ebx, ebx            no name
0047B56E  cmp  byte [ebx], 0       empty name
0047B575  mov  esi, 0x73EE04       the literal "NULL"
0047B581  repe cmpsb
0047B587  call AurTextureGetReference   <- a real name
0047B591  call AurTextureGetNULL        <- none of the above
```

`AurTextureGetNULL` (`0x004230C0`) is a lazy singleton. It allocates **0x18
bytes**, runs the bare `CAurTexture::CAurTexture` (`0x00422E30`), caches the
result in `0x007A477C` and hands it back for ever after. It is a `CAurTexture`
with **no `CAurTextureBasic` behind it** -- no image, no GL object, nothing.

Which lands exactly on the bind:

```
CAurTexture::glImage        0x00421430
00421433  call [eax + 8]        resolve to the CAurTextureBasic
0042143A  call [edx + 4]
0042143F  xor  eax, eax
00421441  test esi, esi
00421443  je   0x421473         <- none: return, binding NOTHING
00421457  call CAurTextureBasic::glImage
```

So the full chain, every step read:

    fill resref absent / empty / "NULL", or its texture not built
      -> AurTextureGetNULL, a CAurTexture with no basic texture
      -> CAurTexture::glImage binds nothing and returns
      -> the quad is drawn with no texture
      -> its colour is the vertex colour alone

and a GUI fill's colour is `1.0, 1.0, 1.0` -- read live from a party-screen
button's normal border block during the badge work. **White.**

White is therefore not a placeholder texture and not an error colour. It is the
literal absence of a texture bind, showing the fill's own colour. That matches
the shipped precedent in `tools/check_controller_drift.py` -- the comment ending
"loses its art entirely and draws flat white", at line 153 on 2026-09-24 (this
said line 143 until the file moved) -- where buttons whose `BORDER.FILL` named an
unpackaged texture draw flat white: the same path, reached permanently instead
of for one frame.

**What this means for a transient flash.** A white frame is a frame in which that
control's texture had no basic image. Two things can produce that, and they are
not distinguished yet:

* the texture has not been built yet -- first use, still in `aurRefreshTextures`
  waiting for `AurTextureBuildAndStoreAll`;
* the texture is being rebuilt after `AurTextureMemCheck` downsampled it to fit
  the budget.

Both are transient, both are invisible once the texture is resident, and both
would look identical on screen. Telling them apart needs a measurement, not more
reading -- see the bottom of this document.

## The pipeline, traced — and why both proposed causes fail

Following every call rather than the plausible ones overturned the two
explanations offered earlier in this document. Both are kept below, struck
through, because the reasoning that produced them is the kind worth not
repeating.

### The GUI fill draw drains its own build queue

```
CSWGuiBorder::FillCenter          0x004157F0
  -> CAurGUIImageInternal::Draw   0x00459920   (vtable +0x18) computes UVs
    -> CAurGUIImageInternal::Draw 0x004599B0   (vtable +0x14) via call [edx+0x14]
       004599F4  call AurTextureMakeCurrent    <- drains aurRefreshTextures
       00459A00  call Material::BindTexture0   <- binds, AFTER
```

`AurTextureMakeCurrent` (`0x00421EE0`) runs `AurTextureBuildAndStoreAll`
(`0x004217F0`), which drains the queue through
`CAurTextureBasic::BuildAndStoreTexture` (`0x004216A0`) ->
`ConstructImage` (`0x0041FA30`) -> `LoadImageA`, `ImageDecode`,
`ImageGammaCorrect`, `ImageFillAlpha` -> `glImage`.

And a texture joins that queue **when it is created**: `AurTextureGet`
(`0x00423490`) misses in `AurTextureFind`, allocates `0xEC` bytes, constructs,
and increments `aurRefreshTexturesCount` at `0x004235D4`. For a GUI fill that
creation happens at panel construction, in `SetFillImage`.

**So the texture is queued at construction and built by the first draw that needs
it, before that draw binds anything.** The engine already does, inside the draw,
what a pre-warm would do outside it.

### ~~The first-build cause~~ — does not apply to GUI fills

The earlier account here said a fill's texture is created empty, drawn the same
frame, and binds nothing. The first two steps are right and the third is wrong:
the draw calls `MakeCurrent` before `BindTexture0`, so the image exists by the
time the bind runs. The constructor genuinely does no loading
(`CAurTextureBasic::CAurTextureBasic`, `0x00423150`, makes four calls and none of
them reads a file) -- but the gap that creates is closed inside the same draw.

### ~~The downsample cause~~ — does not run during play

`AurTextureMemCheck` (`0x00421AC0`) is the budget enforcer, and it has **two
callers, both inside `AurTextureSetMem`** (`0x00421D90`). `AurTextureSetMem` in
turn has three:

    AurTextureRefreshAll+0x19          <- 1 caller: CAurInternalGL::Initialize
    SetTexturePack+0x2a1               <- the Texture Quality option
    CAuroraInterface::CAuroraInterface <- construction

So the budget is applied at GL initialisation, at construction, and when the
player changes Texture Quality. **It is not a per-frame check and not a
per-transition check.** Downsample levels are decided once and then stay put,
which means the budget cannot produce an intermittent flash during ordinary play.

The `texpacks.2da` numbers earlier in this document are still correct, and the
40 MB of KMRP font atlases is still a real cost worth knowing. What is wrong is
the claim that exceeding the budget causes rebuilds *while playing*.

### What this means for preloading

**Preloading GUI fill textures would implement something the engine already
does.** Calling `AurTextureBuildAndStoreAll` after panel construction would drain
a queue that the panel's own first draw is about to drain regardless. The likely
measured result is "no change", which is easy to misread as the fix not working
rather than the fix being unnecessary.

The one place suspension does occur is area loading:
`AurTextureSuspendUpdates` (`0x00420490`) and `AurTextureResumeUpdates`
(`0x004204A0`) have exactly one caller each, both inside `CSWCArea::LoadArea`.
While suspended, `MakeCurrent` returns at its first instruction without draining.
Anything drawn in that window binds whatever it already had -- which is a real
white-frame mechanism, but for area transitions, not menu screens.

### Where that leaves the reported flash

The player's evidence, which is the strongest signal available:

* it happens **only** when the HD inventory icons are being loaded;
* it does **not** happen in vanilla;
* **compressing the icons made it less frequent, not absent.**

Frequency scaling with file size means load *time*, not residency. And the icon
path is not special: `CSWGuiStoreItemEntry::Draw` (`0x006B4D40`, the row class
whose vtable is `0x007568F8`) is six virtual calls to `CSWGuiBorder::Draw`
(`vtable +0x0C` on each border sub-object). Icons go through the same
FillCenter -> CAurGUIImageInternal::Draw -> MakeCurrent -> BindTexture0 chain as
every other fill.

**So the traced model and the observation disagree**, and the model is what
should be doubted. What the model says is that the drain runs before the bind, so
a first-use icon cannot draw white. What the player sees is white, tied to icon
loading, scaling with icon size.

One property of the drain is worth holding on to while looking for the gap: it is
**unbounded and synchronous**. `AurTextureBuildAndStoreAll` empties the entire
queue in one go -- no time budget, no cap -- and each entry costs a disk read and
a decode inside `ConstructImage`. The first border that draws after a screen
queues N icons pays for all N, in that frame. With vanilla's small icons that is
cheap; with KMRP's it is not, and compression reduced it. That matches the
evidence exactly, and it makes the frame **long** -- but a long frame is not
obviously a white one, and asserting that it is would be the same mistake this
section already records twice.

### Textures are not freed during play

Two readings rule out a free-and-reload cycle, which the filter rotation would
otherwise be an obvious candidate for:

* `SafePointer<CAurObject>::operator=` (`0x00447FA0`) is **not** a refcount. It
  keeps a back-reference list on the target (`obj+4`): assigning removes `this`
  from the old target's list and appends it to the new one. Releasing the last
  SafePointer destroys nothing.
* `CAurTextureBasic::~CAurTextureBasic` has **zero** direct callers, and its
  scalar-deleting form (`0x004233C0`) appears as a dword exactly **once** in the
  entire image -- one vtable slot. With `FreeImage` reachable only from that
  destructor, a texture that has been built stays built.

So an icon is loaded once and cached for the session.

### What that leaves, and the prediction it makes

The remaining explanation consistent with every reported fact is **first load, in
a batch**:

* the filter rotation replaces the visible item set, so a switch asks for many
  icons that have never been loaded, all at once;
* `AurTextureBuildAndStoreAll` drains the whole queue in one unbounded
  synchronous pass, each entry a disk read plus a decode in `ConstructImage`;
* KMRP's icons are far larger than vanilla's, so that pass is far more expensive;
* compressing them made it cheaper, and the flash rarer -- exactly as reported.

This is **falsifiable without a build**, but the test has to be stated
carefully, because a loose version of it was already run and misread.

Reported: pressing X to rotate the filter, "the first two presses don't have a
flash, usually the third and fourth do". That is **within one rotation**, and it
does not contradict first-load -- it is what first-load predicts if the later
filters are the ones holding items whose icons have not been seen yet. Which
filter flashes depends on what is in the player's inventory, not on the press
index.

The real test is **complete rotations, repeated**. Go all the way round the
filters three or four times without leaving the screen:

* flashes on the first full rotation, then progressively fewer, then none ->
  first load, and the cache is doing its job;
* flashes at the same rate on the fourth rotation as the first -> textures ARE
  being freed somewhere the two readings above did not find, and this model is
  wrong.

A useful secondary observation while doing it: does the flash follow a
*particular filter* rather than a position in the sequence? If it is always the
same filter, that filter holds the unseen icons, which is first load again.

### Ruled out: a stale GUI batch

`CAurGUIImage::guiTID` (`0x007BB4D8`) is a global "texture currently being
batched", and `CAurGUIImageInternal::DrawBuffered` batches draws by it. Since a
filter switch destroys every row's image, a destroy landing mid-batch looked like
a way to flush quads against a dead texture.

It is handled. `~CAurGUIImageInternal` (`0x0045B200`) checks first:

```
0045B22F  call Material::GetTextureTID     this image's TID
0045B234  cmp  [guiTID], eax               the one being batched?
0045B23A  jne  0x45B25E                    no: nothing to do
0045B242  call CAurGUIImage::FlushBuffer   yes: FLUSH first
0045B24A  mov  [guiTID], 0                 then clear
```

The buffer is flushed before the texture is let go, so no buffered draw survives
its texture.

### The measurement that would settle it

## What is NOT established

* **Which of the two absences applies to the reported flash**: a texture not yet
  built on first use, or one being rebuilt after a downsample. Both pass through
  the same queue.
* **Whether the budget is reached at all on the reporting machine.** The GUI art
  numbers below are suggestive, not a measurement of resident bytes.
* **Whether the controller layer is involved.** The issue is framed around party
  switching, but the report has since widened to GUI screen transitions
  generally, which does not implicate the pad.

## How the engine measures a texture

Not in file bytes. `CAurTextureBasic::GetMemoryUsage` (`0x00420710`) computes it,
caches the result in `+0xE8` (initialised to `-1` by the constructor at
`0x0042338F`), and classifies it by name -- `_lm` and `_a00` are counted
separately.

```
shift = [+0xBC] - [+0xBE]          the downsample currently applied
w = max(width  >> shift, 2)
h = max(height >> shift, 2)

compressed      ImageGetS3TCSize(w, h, fmt)         0x0045E270
                  blocks = ceil(w/4) * ceil(h/4)
                  bytes  = blocks * (fmt == 4 ? 16 : 8)      DXT5 : DXT1
uncompressed    bpp = 2 if the 16-bit display mode is set
                      4 if the depth field is 3
                      else the depth field
                  bytes = bpp * w * h
mipmapped       bytes = bytes * 4 / 3
```

`tools/texture_budget_report.py` reproduces this against the built resource
archives, so the figures below can be regenerated rather than trusted.

## Where KMRP's art actually sits in the budget

**The headline number is not 363 MB.** That is everything KMRP ships, and item
icons and portraits are only resident when referenced. The figure that matters is
what stays resident, and for that the font atlases dominate:

| | resident bytes | |
| --- | ---: | --- |
| vanilla font atlases | 2,949,120 | 2.8 MB |
| KMRP font atlases | 44,040,192 | 42.0 MB |
| **added by KMRP** | **41,091,072** | **+39.2 MB, a 14.9x increase** |

Measured with the formula above: vanilla's from the game's own packs, KMRP's from
the built `override-common.zip`.

**Re-measured 2026-09-24: the table above predates issue #16.** It is the shared
3.0 bake, which then shipped in `override-common.zip` for every resolution. Each
resolution now ships its own 18 atlases, baked at its own scale, so the resident
cost depends on the resolution. Summed from the 2026-09-24 installer's archives
with the same formula (32-bit, no mipmaps):

| resolution | KMRP font atlases | `dialogfont32x32` | vs Quality 0 / 1 / 2 |
| --- | ---: | --- | --- |
| 1280x720 | 10,223,616 (9.8 MB) | 512x512 | 43% / 22% / 10% |
| 1920x1080 | 18,874,368 (18.0 MB) | 1024x1024 | 80% / 40% / 19% |
| 2560x1440, 3440x1440 | 28,311,552 (27.0 MB) | 1024x1024 | 120% / 60% / 28% |
| 3840x2160, 15360x8640 | 69,206,016 (66.0 MB) | 2048x2048 | 293% / 147% / 69% |

So at 3440x1440, the resolution of the machine reporting the flash, the fonts
now take 28% of the Quality 2 budget rather than 44%; at 2160p and above they
take more than the 44% measured here. The figures below are the earlier
arithmetic on the old total, kept as they were. The single largest is `dialogfont32x32`, which
vanilla ships at 512x512 (1,048,576 bytes) and KMRP at 2048x2048
(16,777,216 bytes) -- **16x**, in one texture.

Against the three budgets, fonts alone:

| Texture Quality | budget | KMRP fonts | vanilla fonts |
| --- | ---: | ---: | ---: |
| 0 (32MB) | 23,592,960 | **186.7%** | 12.5% |
| 1 (64MB) | 47,175,000 | **93.4%** | 6.3% |
| 2 (128MB) | 100,663,296 | **43.8%** | 2.9% |

At Quality 0 the fonts cannot fit at all, so downsampling is not occasional, it
is the steady state. At Quality 1 they leave about 3 MB for everything else. At
Quality 2 -- the setting on the machine reporting the flash -- they take 44% of
the budget before a single world or GUI texture loads, leaving roughly 56 MB.

That is the shape of a fault that appears **sometimes**: enough headroom that
most transitions fit, not enough that all of them do.

**Assumption, flagged.** That all nine atlases are resident simultaneously is not
measured. Different UI paths use different fonts, and the true simultaneous set
may be smaller. The `dialogfont32x32` figure needs no such assumption -- it is one
texture, 16 MB, and it is the dialogue and menu font.

## Shrinking to fit, with the savings computed

**Read with the correction above.** Budget pressure is applied at GL init and on
the Texture Quality option, not during play, so shrinking these atlases is not a
fix for an in-play flash. The arithmetic is kept because the 40 MB is real and
matters for memory headroom generally -- not as a remedy for issue #14.

The aim is that the engine never needs to downsample, because nothing ever has to
be rebuilt, because nothing ever exceeds the budget.

| change | from | to | saved |
| --- | ---: | ---: | ---: |
| `dialogfont32x32` 2048 -> 1024 | 16,777,216 | 4,194,304 | 12,582,912 |
| all nine atlases halved | 44,040,192 | 11,010,048 | 33,030,144 |
| all nine atlases to DXT5 at current size | 44,040,192 | 11,010,048 | 33,030,144 |

Halving and DXT5 happen to save the same amount (both are 4:1) but they are not
equivalent in quality: halving loses resolution evenly, DXT5 keeps resolution and
quantises, and a font's sharp alpha edges are the worst case for DXT's 4x4 blocks.
For glyph art, halving is the more predictable loss, and is reversible per-atlas.

Either brings the fonts to about 11 MB -- 11% of the Quality 2 budget, 23% of
Quality 1, and under half of Quality 0. That would make KMRP's permanently
resident footprint comparable to vanilla's in kind, if not in size.

**None of this is a fix yet.** It is a hypothesis with arithmetic behind it. What
it needs before anyone changes art is the measurement below: if the flash does
not track the budget, resizing fonts is a cost with no benefit.

## Raising the budget instead — and it needs no executable patch

**Read with the correction above.** Same caveat: this is a real and cheap lever
on texture detail, but it acts where the budget is applied -- init and the
quality option -- so it is not a remedy for an in-play flash either.

The other direction is to give the engine more room rather than asking less of
it, and the budget turns out to be **data**, not code.

`CClientExoAppInternal::SetTexturePack` (`0x005F14A0`) reads `texpacks.2da`
through the ordinary resource path, which Override takes precedence in. KMRP
already ships a 2DA that way -- `tutorial.2da` is in `override-common.zip` and in
the installed game -- so the delivery mechanism exists and is proven.

The two columns are `mem` and `dynmemratio`, and the engine does nothing exotic
with either:

```
AurTextureSetMem(int mem)               0x00421D90
00421DA6  mov [0x78D3F4], eax           maxTexMemory = mem, a plain int32
00421DA0  fmul [0x78D3F0]               x dynmemratio
00421DBD  fistp [edx]                   the rounded product
00421DE9  call CAurTextureBasic::Reset  every texture, then rebuilt

AurTextureSetDynamicMemoryRatio(float)  0x0041E9B0
0041E9B4  mov [0x78D3F0], eax           stored verbatim
```

**No truncation anywhere.** `maxTexMemory` is a signed int32, so the representable
ceiling is 2,147,483,647 -- the shipped 134,217,728 uses 6% of the range. The
product is also stored through a signed `fistp dword`, so keep `mem x ratio`
inside int32 as well.

Some illustrative values, all reachable by editing the 2DA alone:

| change | budget at Quality 2 | headroom after 42 MB of fonts |
| --- | ---: | ---: |
| shipped | 100,663,296 | 56,623,104 |
| `dynmemratio` 0.750 -> 1.000 | 134,217,728 | 90,177,536 |
| `mem` x2, ratio unchanged | 201,326,592 | 157,286,400 |
| `mem` x3, ratio unchanged | 301,989,888 | 257,949,696 |

**Why this is not obviously reckless.** The figure is a *threshold*, not an
allocation: `AurTextureSetMem` stores it and resets the texture list, and nothing
reserves that many bytes up front. Raising it does not claim memory; it lets
textures stay at full resolution for longer before `AurTextureMemCheck` starts
downsampling. The 2003 default reflects 2003 video cards.

**Why it still needs care.**

* The process is 32-bit. KMRP enables Large Address Aware, so the ceiling is
  about 4 GB rather than 2, but texture data held at full size raises peak
  working set and that ceiling is real.
* `AurTextureSetMem` resets and rebuilds every texture, so the value must be set
  before or during load, not casually at runtime.
* Only two consumers of `maxTexMemory` have been read -- `AurTextureSetMem` and
  `AurTextureMakeCurrent`. `AurTextureRefreshAll` (`0x00422360`) also reads it and
  has not been traced.
* Other mods may ship their own `texpacks.2da`. KMRP's ownership manifest already
  handles Override collisions, but this would be a new file in that set.

**And the limit of the whole idea:** raising the budget removes the *downsample
and rebuild* cause of a white frame. It does **not** remove the *first build*
cause -- a texture still has to be built the first time it is used, and during
that frame it has no image. If the reported flash is first-use rather than
downsample, more budget changes nothing.

Which is why the measurement below still comes first, for either direction.

## Two corrections recorded so they are not repeated

**1. `[0x7A4794]` is not a memory cap.** In `AurTextureBuildAndStoreAll` it was
read as an accumulator against a budget. It is `std::vector` growth:

```
00421892  mov eax, [0x7A4794]      capacity
00421897  cmp [0x7A4790], eax      count
004218A9  add eax, eax             double
004218AD  mov eax, 8               ...or 8 from empty
004218C1  call operator_new
004218FC  call operator_delete
0042190F  mov [eax + ecx*4], ebp   array[count] = item
```

**2. `[edi+0xC2] * [edi+0xC4]` is not width x height.** The layout gives `numx`
at `+0xC2` and `numy` at `+0xC4` -- the texture's cell grid, as used by animated
textures and font atlases. `defaultwidth` and `defaultheight` are at `+0xC8` and
`+0xCA`.

## Next reads

* `AurTextureGetReference` (`0x00423A60`): what a name that *should* resolve
  returns while its texture is still queued -- the NULL texture, or a real one
  with no basic image yet. Both draw white, so this decides only which of the two
  transient causes is in play.
* `AurTextureCalculateNewTexMem` (`0x00420DB0`): what counts toward the budget.
* `CAurTextureBasic::AddToOrderedLists` (`0x00421560`) and the sort at
  `InsertionSortTexture` (`0x0041E9C0`): the priority order that decides which
  textures are downsampled first.
* The vtable slot holding `CAurTexture::IsFullyLoaded` (`0x0041EC10`), which has
  **zero** direct callers and so is reached virtually.

## Cheap measurements, when a machine is free

1. **Does the flash happen with the mouse only?** Splits controller from engine.
2. **Does it recur on a screen already visited in the session?** First-visit-only
   is a build; recurring is a downsample cycle.
3. **Does `Texture Quality=0` (23,592,960 bytes, a quarter of the budget) make it
   constant?** If the budget is the mechanism, quartering it should turn an
   intermittent flash into a reliable one. If nothing changes, the budget is not
   the mechanism and this whole document is about the wrong subsystem.
