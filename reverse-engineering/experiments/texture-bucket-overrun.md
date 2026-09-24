# A verified unbounded write indexed by GL texture id

**Status: strong candidate for the white flash, not yet confirmed in play.**
Found by reading the bundled KOTOR Patch Manager sources rather than by
disassembly, then verified against this project's own gold image.

## What KPM found

`build/research/Kotor-Patch-Manager/Patches/TextureBucketSafety/` ships a patch
by VexFlint whose manifest describes it exactly:

> Bounds-checks the three 5000-entry texture bucket arrays (meshBuckets,
> fadeBuckets, capBuckets), which are indexed by driver-assigned GL texture
> names. ClearBuckets used maxTexID+1 as an iteration count without clamping
> (crash 0x0046BF22), and AddPartToMeshBuckets indexed and wrote through the
> arrays with no range check (crash 0x0046BEAE).

It targets the same two executables KMRP supports, including
`761F9466...C49E9886` -- this project's own source hash.

**KMRP does not ship it.** KMRP folded in `CubeMapFix` (see
`docs/third-party-driver-compat.md`) but nothing in this repository mentions
texture buckets.

## Verified here, not taken on trust

```
AurTextureGetMaxTexID          0x0041FEB0
  mov eax, [0x007A46BC]        maxTexID, returned raw
  ret                          no clamp of any kind

AddPartToMeshBuckets           0x0046BDF0
  0046BE5F  call 0x0047AF00              Material::GetTextureTID
  0046BE64  lea  esi, [eax + eax*2]      tid * 3
  0046BE67  mov  eax, [esi*4 + 0x008194E8]   array[tid*12 + 8]
  0046BE6E  mov  ecx, [esi*4 + 0x008194E4]
  0046BE77  lea  esi, [esi*4 + 0x008194E0]   base 0x008194E0, stride 12
```

A stride-12 array at `0x008194E0`, indexed by a **driver-assigned GL texture
name**, with no bounds check between the id and the access.

And `maxTexID` is written by a function already documented in
[texture-residency.md](../texture-residency.md):

```
AurTextureBuildAndStoreAll     0x004217F0
  0042192B  cmp eax, ecx
  0042192F  mov [0x007A46BC], eax        keep the highest GL id seen
```

so it grows as textures are created and never shrinks.

## Why this fits the report where the earlier models did not

The reported behaviour, in the player's words: the flash happens only with the HD
inventory icons, never in vanilla, became rarer when the icons were compressed,
and on the filter rotation "the first two presses don't have a flash, usually the
third and fourth do".

* **It accumulates.** `maxTexID` only ever rises. Every new icon pushes it
  higher. That is the "third and fourth press" signature, which defeated the
  first-load model -- first load flashes first and then stops.
* **It is specific to loading many textures.** Vanilla never gets near 5000
  distinct GL names in a session; KMRP ships 778 shared textures before a single
  item icon, and the icons are numerous.
* **An overrun corrupts neighbours rather than crashing immediately.** KPM notes
  `meshBuckets` ends exactly at `backgroundBucket`, so the first thing an
  overrun lands on is the skybox list. Corrupted render state for a frame is
  what a flash looks like; the crash at `0x0046BEAE` is the same bug further
  along.
* **It is not a GUI bug**, which is consistent with every GUI mechanism
  examined in texture-residency.md having been ruled out.

## What is NOT established

* **That `maxTexID` actually reaches 5000 on the reporting machine.** This is the
  whole question and it is now measurable -- see below.
* That the corruption manifests as white specifically. An out-of-range write
  through this array lands in whatever follows it; "white for a frame" is
  plausible and unproven.
* Whether KMRP's compression reduced the flash by reducing the *number* of GL
  names or only their size. Compression changes bytes, not obviously ids, so if
  the count is what matters this explanation needs that detail filled in.

## Measuring it

Build `C386A981...` logs `maxTexID` against the array bound every diagnostic
line, in `kmrp-native-joystick.log`:

    tid=<maxTexID>/5000

Open the inventory and rotate the filter until the flash appears, then read the
log. If `tid` is climbing toward 5000 and the flashes start as it approaches,
this is the bug. If it sits in the hundreds, it is not, and this document is
wrong.

## If it is confirmed

KPM's patch is the fix and it already targets this exact executable: saturate
`AurTextureGetMaxTexID` at 4999, and range-check `AddPartToMeshBuckets` so an
out-of-range part skips the bucket insert and rejoins at `0x0046BEB1`, which
preserves shadow casting. The replacement bytes are in
`TextureBucketSafety/kotor1_103.hooks.toml`.

Whether KMRP should adopt it wholesale, reimplement it as a native hook, or
declare a dependency on KPM is a separate decision, and one about project
boundaries rather than about the bug.
