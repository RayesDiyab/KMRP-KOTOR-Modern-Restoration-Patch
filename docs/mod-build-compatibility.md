# Mod-build and executable compatibility

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: reference.** This records what KMRP can safely recognize, which tools
compose without touching the same bytes, and the install order that keeps
restore predictable. It does not turn unknown executables into supported ones.

## Executable boundary

KMRP accepts the 4,042,752-byte editable PC 1.03 executable in exactly two
states:

| Input | SHA-256 | Supported |
| --- | --- | --- |
| Canonical editable executable | `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` | yes |
| Same file with only `IMAGE_FILE_LARGE_ADDRESS_AWARE` set | `CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889` | yes |
| Any other changed byte | varies | no |

The second row is proven by clearing only file-header bit `0x20` in memory and
requiring the canonical hash. It is not a same-length exception or a relaxed
hash check. Both inputs produce identical KMRP output, while restore returns the
exact incoming file. See
[`../reverse-engineering/large-address-aware.md`](../reverse-engineering/large-address-aware.md).

## Recommended order

1. Start from the editable executable and a clean or deliberately prepared game
   directory.
2. Install K1 Community Patch, K1 Restoration, and other content mods first.
   TSLPatcher/HoloPatcher can then merge their 2DA, TLK, module, and Override
   changes without KMRP's interface files being an intermediate input.
3. Do **not** install UniWS, KOTOR High Resolution Menus, or a separate 4 GB
   patch. KMRP supplies the resolution executable changes, matching GUI set, and
   LAA flag itself. An already-LAA clean executable is harmless and supported.
4. Run KMRP last against the real game directory. Its ownership manifest records
   every Override file it replaces and restores the preceding modded state.
5. If another tool must modify `swkotor.exe` afterward, restore that tool to the
   exact KMRP bytes before asking KMRP to restore. A post-KMRP executable edit
   intentionally invalidates KMRP's ownership hash.

K1 Community Patch 1.10.0 and K1 Restoration 1.2 were previously inspected and
tested with KMRP: neither supplied GUI files nor edited the executable in those
versions. That does not certify later releases; inspect their manifests again
when versions change. The current K1CP repository recommends installing K1CP
before most other mods, which agrees with the order above.

## KOTORganizer / Mod Organizer 2

The KOTORganizer author lists widescreen, 4 GB patches, and upscaled movies as
manual steps outside Sync. KMRP replaces the first two steps:

1. Let KOTORganizer finish Sync.
2. Run KMRP manually against the real KOTOR directory, not MO2's downloads or
   staging directory.
3. Launch through MO2 as usual.

MO2's virtual filesystem can take precedence over physical files. A profile that
supplies its own `.gui`, font, portrait, or icon with the same name can therefore
hide KMRP's installed copy at runtime even though KMRP's hash and manifest are
correct. Disable separate widescreen/high-resolution UI packages in that profile.
This workflow follows KOTORganizer's published manual-patch boundary; it has not
yet been run end-to-end on this workstation.

## KotOR Patch Manager

*Since 2026-09-28* there is a KMRP edition for KPM itself, which never modifies
the executable and so passes KPM's hash gate: see
[kpm-edition.md](kpm-edition.md). What follows describes the standalone edition.

KotOR Patch Manager normally injects dynamic hooks without rewriting the
executable, but patch manifests declare `supported_versions` by executable hash.
A KMRP resolution build therefore needs an address-database/hash entry or an
adapter even when its hook sites are untouched. KMRP bundles the standalone
version of K1 Modern Driver Compatibility specifically to avoid that hash gate;
none of its eight runtime hook sites overlaps any of the 742 byte positions the
KMRP installer writes at any of its 48 resolutions, so all eight keep their stock
bytes in every output (checked 2026-09-24 against the installer's `--apply`
output; first checked on gold v23).

KPM also supports static hooks, including its own 4 GB patch. Do not enable that
duplicate after KMRP: the bit is already set. Other KPM patches require their own
site-by-site collision audit and version recognition; “runtime injection” alone
is not proof of compatibility.

KMRP's controller support -- an Advanced Settings component, on by default
since 2026-09-24 -- embeds a narrowly configured KPM runtime, but it owns the
game-root `patch_config.toml`. It refuses to overwrite or merge a configuration
owned by a separate KPM installation, and the rest of the patch still installs.
Turn KMRP's controller option off when using external KPM patches; combining
the configurations requires an explicit, versioned merge workflow that does not
exist yet. See [`controller-support.md`](controller-support.md).

## Other executable patchers measured

The public
[KOTOR1 Engine Fixes](https://github.com/VexFlint/KOTOR1-Engine-Fixes) commit
`a93154bac4b9b8621a06d9cf1b105bdaad48e3f2` changes a frame-cap value, LAA,
eight code sites, and five code caves (`kotor_patch.py` at that commit). In
every one of the 48 executables the KMRP installer writes, all eight sites still
contain its expected stock bytes, the caves at `0x73C200`-`0x73C2FF` are still
zero, the frame-cap float at `0x7A3C64` is still zero, and none of it intersects
the 742 byte positions KMRP writes; both set the same LAA bit. Checked
2026-09-24 against the installer's `--apply` output; the first check, on gold
v23, counted gold's then 702-byte delta. That proves the two patch sets do not
overwrite the same bytes; it does **not** make the combined workflow supported:

- applied first, its executable is not one of KMRP's two recognized inputs;
- applied after KMRP, its edits invalidate KMRP's exact manifest hash, so KMRP
  correctly blocks restore until its own output is put back.

KMRP therefore does not currently advertise that combination. Preserving an
external patch through apply and restore requires a separately specified,
versioned overlay contract—not a blanket exception—and remains unfinished.

## Issue #15: crashes on the next module load -- analysis, 2026-09-25

**Status: a hypothesis, not a reproduction.** The ten reported mods were not
installed here. That would take ten downloads, one of them behind a Nexus login.

The reports share a pattern. The mods are unrelated in kind: loose files,
patcher installs, module edits and texture packs. The reporter runs more than 130
mods. The game crashes on a *module load*, either the Endar Spire after character
creation, or the next load after KMRP was applied mid-save, and the same build
loads without KMRP. A single content conflict does not fit that pattern. A shared
limit that the whole stack approaches does, and KMRP 1.0 moved three such limits
the wrong way. Each was measured here:

| Limit | KMRP 1.0 (tag `v2.10.0`) | KMRP 1.5 |
| --- | --- | --- |
| **2 GB address space** | Accepted only the unpatched `761F9466…` executable, so a player's own 4 GB patch had to be removed first. Its output keeps characteristics `0x010F`, without Large Address Aware (`git show v2.10.0` has no LAA code). | Accepts an executable with the LAA bit already set, and sets it on every output (`0x012F`, read from the installer's output; `Test-LargeAddressAware.ps1`). |
| **Resident font atlases** | One set baked at 3.0x for every resolution: 42.0 MB resident, +39.2 MB over vanilla ([texture-residency.md](../reverse-engineering/texture-residency.md)). | Per resolution: 9.8 MB at 720p, 18.0 MB at 1080p, 27.0 MB at 1440p. At 2160p and above it is **more**, 66.0 MB. |
| **Texture-bucket overrun** | Unbounded. `ClearBuckets` iterates to the highest GL texture name seen, with no clamp (KPM's crash site `0x0046BF22`); `AddPartToMeshBuckets` writes out of range (`0x0046BEAE`). Both grow with the number of textures ever loaded. | Bounded at 5000 by KPM's two `replace` patches, installed with the controller component (on by default). See [texture-bucket-overrun.md](../reverse-engineering/experiments/texture-bucket-overrun.md). |

None of this is shown to be *the* cause. The overrun was measured far from its
limit in ordinary play: `maxTexID` peaked at 471 and 296. The Endar Spire crash
right after character creation happens early in a session, which fits a texture
count better than address-space exhaustion.

**What would settle it:** have the reporter retest with 1.5. If it still crashes,
ask for the Windows Event Viewer entry (*Application Error*, faulting module
`swkotor.exe` and its offset). An offset of `0x0006BF22` or `0x0006BEAE` is the
bucket overrun, and memory near 2 GB at the crash is address space. Not yet
asked; nothing was posted to the issue.

## What remains untested or requires people

- KOTORganizer Sync → KMRP → MO2 launch has not been exercised end-to-end.
- A memory-heavy mod build has not been played long enough to cross the old 2 GB
  address ceiling.
- Current K1CP/K1R versions beyond the measured 1.10.0/1.2 pair need a fresh
  file-manifest audit.
- Controller support has been play-tested with a physical pad at 3440x1440 (the
  play-tests `CHANGELOG.md` records entry by entry); physical PlayStation, Switch
  and Steam Deck controllers, Proton and the Steam Deck itself remain untested.
- Coordination with Doug Dimmadab and JC is not an engineering operation and was
  not performed; no external message is sent without explicit authorization.

## Verification

Run the LAA, reinstall, and driver collision checks:

```powershell
.\testing\regression\Test-LargeAddressAware.ps1
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
python tools\build_binary_inventory.py `
  build-inputs\swkotornopatch.exe `
  build\kmrp\swkotor_gold_v24_movieaspect.exe
```

To check a collision against what the installer actually writes rather than
gold alone, add `--installed` with its `--apply` outputs; see
[`../reverse-engineering/binary-inventory.md`](../reverse-engineering/binary-inventory.md) §2.

For a real mod build, record the executable hash before KMRP, hash any existing
backup, list colliding Override filenames, and perform a complete restore before
calling the workflow compatible.
