# Large Address Aware: the one-bit PE-header change

> **Documentation standard.** This document follows
> [`../docs/documentation-standard.md`](../docs/documentation-standard.md).

**Kind: reference.** This records the complete executable change for Large
Address Aware support and the deliberately narrow compatibility rule for inputs
already processed by a 4 GB patcher. It does not claim that a particular mod set
needs more than 2 GB; memory-heavy gameplay remains an empirical test.

> **How the bit is set now (note of 2026-10-08, read from the source).** This is
> the one change KMRP still makes to `swkotor.exe` on disk, and only to the CD
> 1.03 and GOG files; Steam's is never changed, because its DRM refuses a file
> that differs. Two paths write the same bit at the same FILE `0x000926`:
>
> | Install | Who writes it | Where in the source |
> | --- | --- | --- |
> | KMRP's installer on its own | the installer, after leaving KOTOR Patch Manager a backup of the unmodified file; a file that already has the bit is left as it is, and restore leaves it too | `KpmEditionOperations.SetLargeAddressAware`, `WriteKpmBackup` (`src/patcher/KpmEdition.cs`) |
> | `KMRP.kpatch` ticked in KOTOR Patch Manager | KOTOR Patch Manager, from the patch's static hook (`0F 01` to `2F 01`, CD 1.03 and GOG only) | `kotor1-cd-large-address.hooks.toml` in the archive, from `large_address_hook()` (`tools/kpatch_common.py`, `src/engine/windows-sites.json`) |
>
> The gold rows of the table below and the clean-to-gold delta in "Existing 4
> GB-patched inputs" describe the installer until 2026-09-29, which wrote the
> whole patched image. The rule of that section still holds for the installer
> (a known file, or the same file with only this bit set: `GameExecutable.Hash`
> and `LargeAddressAwareHash` in `KmrpPatcher.cs`), now for CD 1.03, GOG and
> Steam. `--apply` still writes the patched image to a new file, and
> `Test-LargeAddressAware.ps1` covers both (its Cases 1 and 2 are `--apply`,
> the later ones the install). The table and the edit itself are unchanged.

## The builds this describes

| Build | Length | SHA-256 | PE characteristics |
| --- | ---: | --- | ---: |
| Supported clean `swkotor.exe` | 4,042,752 | `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` | `0x010F` |
| Same clean file with LAA as its only changed bit | 4,042,752 | `CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889` | `0x012F` |
| Gold v21 map notes | 4,083,712 | `9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC` | `0x010F` |
| Gold v22 LAA | 4,083,712 | `7863BCE3BDDAC279B6A14FEB2412D38572CF94D22D6E0D8EC869D491B7EFCDE8` | `0x012F` |
| Gold v24, current | 4,087,808 | `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A` | `0x012F` |
| What the installer writes, all 48 resolutions | 4,087,808 | per resolution | `0x012F` |
| The same, 2880x1620 (added 2026-09-25) | 4,087,808 | `69DC9BBB…` | `0x012F` |

The last two rows were read on 2026-09-24 from gold and from the 2026-09-24
installer's `--apply` output: v23 and v24 carried the bit forward, and every
executable the installer writes has it.

These values were read directly from the files and re-hashed after the builder
re-read its output. The field is in the PE file header, not a loaded section, so
there is no meaningful VA conversion for this edit.

## The complete edit

Microsoft defines `IMAGE_FILE_LARGE_ADDRESS_AWARE` as bit `0x0020` in
`IMAGE_FILE_HEADER.Characteristics`. On 64-bit Windows, a 32-bit process with
that bit can address up to 4 GB of user virtual address space rather than the
usual 2 GB.

| Structure field | FILE | Size | Before | After | Operation |
| --- | ---: | ---: | ---: | ---: | --- |
| `IMAGE_FILE_HEADER.Characteristics` | `0x000926` | 2 bytes | `0x010F` | `0x012F` | `before OR 0x0020` |

Only the low byte changes, from `0x0F` to `0x2F`. No section, code instruction,
checksum, file length, or other header flag changes. The gold builder is
`tools/build_large_address_aware.py`; it accepts only gold v21's exact length,
hash, and `0x010F` field, writes in place, asserts the length is unchanged, and
requires the exact v22 output hash above.

## Existing 4 GB-patched inputs

KMRP does not add a general “ignore the hash” path. It accepts exactly two source
states: the canonical clean file, or a file whose characteristics are `0x012F`
and which becomes the canonical clean hash after that one LAA bit is cleared in
memory. Any other byte difference—or any other characteristics value—remains
unsupported.

The normalized bytes are used only to apply the deterministic clean-to-gold
delta. The original input is backed up without normalization. Both accepted
inputs therefore produce the same LAA KMRP executable, while **Restore Original**
reproduces the user's incoming executable byte-for-byte: non-LAA stays non-LAA
after restore, and pre-existing LAA stays LAA.

This matches the mechanism described by the
[NTCore 4 GB Patch author](https://ntcore.com/4gb-patch/): set the executable's
internal flag. The official 1.0.0.1 archive was downloaded from that page on
2026-09-05 (ZIP SHA-256
`1E13C263DC55E85CF62E3E30C6B2CE936D4C7E16E3BBA3E311A5A8BED4BE16CA`).
Its executable is unsigned, and the local antivirus command-line scan failed
before producing a verdict, so the downloaded program was **not executed**.
Compatibility is verified against its documented PE mechanism and the exact
one-bit input, not claimed as an end-to-end run of that binary.

## What is deliberately not changed

- KMRP does not accept unknown modded executables, arbitrary same-length files,
  or additional PE-header changes.
- The patch does not allocate memory, modify KOTOR's allocator, or guarantee that
  every engine subsystem safely handles addresses above `0x7FFFFFFF`.
- It does not change the physical-RAM limit of 32-bit Windows. The 4 GB address
  space described here applies to a 32-bit LAA process on 64-bit Windows.
- Restore does not decide that LAA is “better” and impose it on the original; it
  restores the exact verified backup.

## Verification

Rebuild the LAA step, then inventory the current gold snapshot, which carries
it forward:

```powershell
python tools\build_large_address_aware.py `
  build\kmrp\swkotor_gold_v21_mapnotes.exe `
  build\kmrp\swkotor_gold_v22_laa.exe
python tools\build_binary_inventory.py `
  build-inputs\swkotornopatch.exe `
  build\kmrp\swkotor_gold_v24_movieaspect.exe
```

Then build the patcher and run:

```powershell
.\testing\regression\Test-LargeAddressAware.ps1
```

The regression constructs the exact LAA-only input, verifies canonical and
pre-LAA inputs produce identical output, rejects a different header flag, and
performs complete in-place patch/restore cycles for both source states. It reads
`0x000926` and hashes every resulting file. A memory-heavy HD texture/mod setup
and a visual game launch remain untested.
