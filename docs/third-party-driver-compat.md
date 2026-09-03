# K1 Modern Driver Compatibility: what KMRP bundles, and why it does not collide

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing this
> file, and check the result still meets it — measured claims only, every site tabulated,
> rejected alternatives and corrections kept visible, and anything untested labelled as
> untested.

**Kind: reference.**

KMRP ships **K1 Modern Driver Compatibility (K1DC) 1.2.0** by **Synchro**, MPL-2.0,
with the author's permission. This document records what it is, exactly what it
writes, the check that proves it does not collide with anything KMRP writes, and how
a user turns it off.

It is **not** a KMRP fix. Every line of it is Synchro's work. KMRP's only
contribution is installing it, removing it again, and the compatibility check below.

## The build this describes

| | |
| --- | --- |
| K1DC | 1.2.0 standalone, `k1-modern-driver-compatibility-v1.2.0-standalone.zip`, 1,631,672 bytes, SHA-256 `E35E7DA022DC859E10A2C5F29FDE101B846F5789B2A14BB5D297FB57777F24A8` |
| vendored at | `third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/` |
| KMRP gold | `swkotor_gold_v20_hittest.exe`, `ACD521B80E48B4D5A0CA043187C2D21BA1745E299D7FDD5CBA7514D525A24713` |
| source | <https://codeberg.org/Synchro/kotor-modern-driver-compatibility> |
| release page | <https://deadlystream.com/files/file/3048-k1-modern-driver-compatibility-patch> |

Addresses below are `VA`; `FILE = VA − 0x400000` for all of them, since every site
K1DC touches is in an original section.

## 1. What it fixes, in the author's terms

KOTOR chooses its lighting path once, at startup, between two 2003-era methods:
NVIDIA's `GL_NV_register_combiners` and ATI's `GL_ATI_fragment_shader`. On most
machines today neither is offered, so the game falls back to a path that was never
finished — no wall and floor lighting, no reflections, no fog, no soft shadows, no
screen effects.

K1DC answers "yes" to the `GL_ATI_fragment_shader` capability question and then
**reimplements that entire path on `GL_ARB_fragment_program`**, which every current
driver supports. That is why it is a large payload rather than eight byte edits: the
edits are the doorway, and the shader translations, dispatcher and framebuffer
effects behind it are the actual patch.

The grass is part of the same story. `RenderGrassPolys` picks one of two draw paths,
and only the correct one is taken when that capability reports true — which is why
grass tears across the sky **even on NVIDIA**, where the lighting has always worked.

## 2. Every byte K1DC writes

Read out of `third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/kotor1.hooks.toml`,
which the author publishes for exactly this purpose. Four detours and four in-place
edits:

| VA | FILE | size | what |
| --- | --- | --- | --- |
| `0x004367D4` | `0x0367D4` | 5 | detour: `CheckExtension("GL_ATI_fragment_shader")` -> `ARB_FragmentPathAvailable` |
| `0x004373BD` | `0x0373BD` | 5 | detour: `InitializeATIFragmentShaders` -> `ARB_InstallFragmentPath` |
| `0x00428859` | `0x028859` | 5 | detour: framebuffer-effect shader init -> `ARB_InstallFrameBufferShaders` |
| `0x0044DF8E` | `0x04DF8E` | 5 | detour: `InitializeImageSpaceSoftShadows` -> `ARB_InstallSoftShadowShader` |
| `0x00740968` | `0x340968` | 23 | `.rdata` string `GL_EXT_texture_cube_map` -> `GL_ARB_texture_cube_map` (folded-in CubeMapFix; Intel exposes cube maps only under the ARB name) |
| `0x0045F7E7` | `0x05F7E7` | 2 | `jnz` -> `jmp`, dropping the `AllowSoftShadows` ini gate |
| `0x0045FA6C` | `0x05FA6C` | 2 | `jz` -> two `nop`, same flag's second consumer |
| `0x00470EB6` | `0x070EB6` | 12 | `PartTriMesh::GetRenderPath` forced to case 5, so bump lighting runs on every vendor rather than only on a GeForce |

**None of these is applied to the file on disk.** The standalone build patches its
own process in memory at startup (§3), and checks only these eight places rather than
hashing the executable — which is precisely why it tolerates KMRP.

## 3. How it installs, and how KMRP installs it

Two files go beside `swkotor.exe`:

* `dinput8.dll` (2,407,648 bytes) — a proxy DLL. Windows loads it from the game
  folder ahead of the system one, so it is in the process at startup; it forwards the
  real `dinput8` calls on and acts as a loader.
* `k1-modern-driver-compatibility.asi` (1,536,631 bytes) — the payload that loader
  loads. An `.asi` is a renamed DLL.

`swkotor.exe` is never written to. KMRP's own install, backup, sidecar and restore
paths are therefore completely untouched by it.

`DriverCompatOperations` in `src/patcher/KmrpPatcher.cs` writes both files from
embedded resources (`Kmrp.drivercompat.dinput8`, `Kmrp.drivercompat.asi`) and records
their names and SHA-256 in **`KMRP_DriverCompat.manifest`** beside the executable.

* **It never clobbers.** If either filename already exists and its hash is not one we
  recorded — someone's own ASI loader, or K1DC installed by hand — both files are left
  alone and the log says so.
* **Restore removes them**, but only where the hash still matches. A file changed
  since install is left in place and reported, so a hand-upgraded K1DC is not deleted.
* Restore runs on every uninstall regardless of the current setting, so turning the
  option off does not strand the files.

## 4. The compatibility check

This is the check Synchro asked for before shipping, and it is reproducible (§8).

KMRP changes **680 bytes inside the original image, in 136 runs**, spanning FILE
`0x000916`–`0x35578A`. Intersecting those against K1DC's eight ranges:

**0 of 8 collide.**

Stronger than absence of overlap: each site was compared against the `original_bytes`
K1DC declares, in KMRP's gold v20 image. **8 of 8 hold his exact expected bytes**, so
his eight-site check does not merely avoid KMRP — it *passes* on a KMRP-patched
executable.

His `target_versions` list already includes `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`,
which is the clean executable KMRP builds from.

The two projects are orthogonal by construction rather than by luck: K1DC is GL and
render-init code plus one `.rdata` string; KMRP is UI, resolution and map code.

## 5. What it actually changes, by vendor

Worth stating plainly, because "it restores vanilla behaviour" is true in spirit and
incomplete in fact.

| | AMD / Intel | NVIDIA |
| --- | --- | --- |
| lighting, reflections, fog, bloom, screen effects | restored — none of it works today | already working; **reimplemented** on ARB |
| grass tearing | fixed | **fixed** — it was broken here too |
| soft shadows | enabled where the hardware supports it | **newly enabled**; vanilla hid them behind `AllowSoftShadows=1` |
| bump lighting on creatures | gained; only a GeForce ever had it | unchanged (the forced case 5 is what preserves it) |
| cube maps | fixed on Intel, whose driver only exposes the ARB name | unchanged |

So on NVIDIA it is not purely a repair: it swaps a working implementation for a
different one and turns on a feature vanilla gated off. That is the reasoning behind
shipping it as an **opt-out** rather than silently — see §6.

**Untested by us:** we have installed and run it at 3440x1440 on an RTX 3080 and
confirmed the game launches and reaches a loaded scene with both files present. We
have not compared rendering before and after, on any vendor, and we have not tested
AMD or Intel at all.

## 6. The opt-out

**Advanced Settings** under the primary button on the patcher's card opens a settings
view with one switch, *Modern driver compatibility*, **on by default**.

Opt-out rather than opt-in because the people who most need it — anyone not on
NVIDIA — are the least likely to know it exists, and the grass fix helps everyone.

The choice is stored in `%LOCALAPPDATA%\KMRP\settings.json` as
`{"driverCompatibility": true|false}`, deliberately beside the user's profile rather
than next to the patcher, so it survives re-downloading a single-file executable.
Every read is defensive: a missing file, an unreadable folder or a malformed value
all fall back to the default. A settings file is never worth failing a patch over.

## 7. What is deliberately not changed

* **K1DC's binaries.** Shipped byte-for-byte as released. We do not rebuild, strip or
  repack them, so a user can hash them against the author's release.
* **`swkotor.exe`.** K1DC does not touch it and neither does KMRP on its behalf.
* **The Patch Manager route.** Synchro's ordinary install goes through his own manager,
  which will not recognise a KMRP-patched executable. That is his documented reason for
  publishing the standalone build, and it is the one we bundle. Users who prefer the
  manager should turn our option off and follow `INSTALLING.md` in his release.
* **His hook addresses.** We read `kotor1.hooks.toml`; we never write to those sites.

## 8. Verifying by hand

Reproduce the collision check against any KMRP gold build:

```bash
python - <<'PY'
import re, ast
gold = open("build/kmrp/swkotor_gold_v20_hittest.exe", "rb").read()
clean = open("build-inputs/swkotornopatch.exe", "rb").read()
changed = {i for i in range(len(clean)) if clean[i] != gold[i]}
toml = open("third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/kotor1.hooks.toml").read()
for block in toml.split("[[hooks]]")[1:]:
    va = int(re.search(r"address\s*=\s*(0x[0-9A-Fa-f]+)", block).group(1), 16)
    orig = bytes(ast.literal_eval(
        re.search(r"original_bytes\s*=\s*(\[[^]]*\])", block, re.S).group(1).replace("\n", "")))
    f = va - 0x400000
    hit = changed & set(range(f, f + len(orig)))
    print(f"0x{va:08X} len {len(orig):2}  collides={bool(hit):5}  bytes_intact={gold[f:f+len(orig)] == orig}")
PY
```

Expected: `collides=False` and `bytes_intact=True` on all eight lines.

Confirm the shipped binaries match the author's release:

```bash
sha256sum third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/dinput8.dll
sha256sum third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/k1-modern-driver-compatibility.asi
```

Confirm an install did what it claims — the manifest lists both files and their
hashes, and the executable is untouched:

```powershell
Get-Content "C:\Star Wars - KotOR\KMRP_DriverCompat.manifest"
Get-FileHash "C:\Star Wars - KotOR\swkotor.exe"   # still the gold hash
```

## 9. Licence and credit

K1DC is **MPL-2.0**. The licence text ships inside the patcher
(`Kmrp.license.drivercompat`) and is vendored at
`third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/LICENSE`, alongside the
author's `README.md`, `THIRD-PARTY-NOTICES` and `INSTALLING-STANDALONE.md`.

**K1 Modern Driver Compatibility is by Synchro.** Bundled with permission. No KMRP
code is derived from it, and none of its code is modified.

Separately, and unrelated to the bundling: Synchro's published research on the area
map — `hires_patch.py` and `TECHNICAL.txt` in *K1 Area Map Fixes* — identified the two
area-map tile-size operands and the 440:512 atlas relationship that KMRP's own map
work is built on. That is acknowledged in
[`../reverse-engineering/area-map-surface.md`](../reverse-engineering/area-map-surface.md);
no code or data from that mod is included either.
