# Mod-build and executable compatibility

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: reference.** This records what KMRP can safely recognize, which tools
compose without touching the same bytes, and the install order that keeps
restore predictable. It does not turn unknown executables into supported ones.

**Corrections, 2026-10-04.** Parts of this document predate two changes and are
wrong where they touch them. (1) Since 2026-09-29 and 2026-09-30 KMRP does not
rewrite `swkotor.exe` and accepts Steam's, GOG's and the editable build as they are
([KPM edition](kpm-edition.md)): "exactly two states" below, and the paragraph on a
"narrowly configured KPM runtime", describe the installer before that. (2) Since
2026-10-04 KMRP installs nothing into `Override` ([one patch since 2026-10-04](kpm-edition.md#one-patch-since-2026-10-04)): it replaces
no Override file, so there is nothing for its manifest to record there, the order
of KMRP and content mods no longer matters, and a Mod Organizer profile cannot
hide an installed copy because there is none. The game reads KMRP's files from the
module's own folder ahead of `Override`; that has been measured for the main
menu's layout only, and not under Mod Organizer's virtual file system.

## Executable boundary

KMRP accepts three builds of the PC 1.03 executable, two of them also with the
4 GB flag already set (`GameExecutable` in `src/patcher/KmrpPatcher.cs`). (Until
2026-09-29 this section said "exactly two states", the two editable rows; Steam's
was added that day and GOG's on 2026-09-30.)

| Input | SHA-256 | Supported |
| --- | --- | --- |
| Canonical editable executable, 4,042,752 bytes | `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` | yes |
| Same file with only `IMAGE_FILE_LARGE_ADDRESS_AWARE` set | `CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889` | yes |
| GOG's executable, 4,042,752 bytes (the editable one without its 16-byte header watermark) | `9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435` | yes |
| GOG's with only that flag set | `01B808251B3EE85F86F4C893FD4EE1A0448F94D9316FE9B09BD8B222C2B4132F` | yes |
| Steam's executable, 4,395,008 bytes, never changed by KMRP | `34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88` | yes |
| Any other changed byte | varies | no |

The second row is proven by clearing only file-header bit `0x20` in memory and
requiring the canonical hash. It is not a same-length exception or a relaxed
hash check. Restore returns the exact incoming file. See
[`../reverse-engineering/large-address-aware.md`](../reverse-engineering/large-address-aware.md).

## Recommended order

Since 2026-10-04 KMRP writes nothing into `Override`, so the order of KMRP and
content mods no longer matters for the files; the list below is what remains.
(Until then step 2 said to install content mods first and step 4 to run KMRP last,
because its manifest recorded every Override file it replaced.)

1. Start from a supported executable (Steam's, GOG's or the editable one) and a
   clean or deliberately prepared game directory.
2. Install K1 Community Patch, K1 Restoration, and other content mods before or
   after KMRP.
3. Do **not** install UniWS, KOTOR High Resolution Menus, or a separate 4 GB
   patch. KMRP supplies the resolution changes, matching GUI sets, and LAA flag
   itself. An already-LAA editable or GOG executable is harmless and supported.
4. Run KMRP against the real game directory.
5. If another tool must modify `swkotor.exe` afterward, put back the exact bytes
   KMRP left (the incoming file, with the 4 GB flag on the editable and GOG
   builds) before asking KMRP to restore. A later executable edit intentionally
   invalidates KMRP's ownership hash.

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

MO2's virtual filesystem can take precedence over physical files. Since
2026-10-04 KMRP has no installed copy in `Override` for a profile to hide: the game
reads KMRP's files from the module's own folder ahead of `Override` (measured for
the main menu's layout only, and **not under Mod Organizer's virtual file
system**). Disable separate widescreen/high-resolution UI packages in that profile
all the same.
This workflow follows KOTORganizer's published manual-patch boundary; it has not
yet been run end-to-end on this workstation.

## KotOR Patch Manager

**Now:** KMRP itself runs on KOTOR Patch Manager's runtime, as two KPM patches,
`KMRP.kpatch` and `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`, each working
without the other (since 2026-10-05; [kpm-edition.md](kpm-edition.md)). It never
rewrites the executable's code, so it passes KPM's hash gate, and it supports
Steam's own `swkotor.exe` (seen in game on 2026-09-29). KMRP's own install is one
KPM recognises and takes over; in a folder where KPM's runtime is already
installed, the installer leaves the patches to KPM. KMRP carries the 4 GB and
memory fixes itself, so KPM's own 4GB Patch, Texture Bucket Safety, Grass Memory
Safety and Save Game Memory Leak stay unticked beside it, and both patches
declare the other authors' patches they are known to conflict with
(`tools/check_kpm_overlaps.py`). **The rest of this section describes the
standalone edition, which installed until 2026-09-29, and is kept as its
record**: the hash gate, the "narrowly configured KPM runtime" that owned
`patch_config.toml`, and the advice to turn the controller option off beside
external KPM patches no longer apply.

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

- applied first, its executable is not one of KMRP's recognized inputs (the table
  above);
- applied after KMRP, its edits invalidate KMRP's exact manifest hash, so KMRP
  correctly blocks restore until its own output is put back.

That measurement is of the executables the installer wrote until 2026-09-29, which
`--apply` still writes. Since then KMRP applies the same bytes in memory, where a
patcher that has rewritten the same file's code would meet KMRP's original-byte
guards; that combination has **not been run**.

KMRP therefore does not currently advertise that combination. Preserving an
external patch through apply and restore requires a separately specified,
versioned overlay contract—not a blanket exception—and remains unfinished.

## Issue #15: driver-component interaction reported, 2026-10-01

The maintainer clarified on 2026-10-01 that the reported crashes occur with
some mods **only when Modern Driver Compatibility is enabled**. This is a
maintainer-reported on/off finding, not a new reproduction performed here.
The remaining investigation is the interaction between those mods and the
optional K1DC component; it is not an established crash in KMRP's core engine
or interface fixes. The particular failing driver operation and affected-mod
matrix have not been measured here.

For the affected setup, use the [driver component's opt-out procedure](third-party-driver-compat.md#6-the-opt-out)
and repeat the same new-game or module-transition test. Keep the content mods,
save, resolution and Proton/Windows configuration fixed when comparing driver
on and off. Record K1DC's version, its log and the crash module/offset.
Disjoint hook addresses alone do not rule out a runtime interaction.

**Correction to the historical analysis below:** its address-space, font-memory
and texture-bucket hypotheses were not demonstrated causes of issue 15. The
maintainer's driver-toggle finding narrows the reported failure; the earlier
measurements remain useful independent facts, not proof of that failure's cause.
The GitHub issue body retrieved on 2026-10-01 still contained the original broad
report and no comments; this update attributes the clarification to the
maintainer's direct report in this session.

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
backup, and perform a complete restore before calling the workflow compatible.
(Until 2026-10-04 this also said to list colliding Override filenames; KMRP writes
none now.) For other KPM patches beside KMRP's two, run
`python tools\check_kpm_overlaps.py <folder of .kpatch files>`.
