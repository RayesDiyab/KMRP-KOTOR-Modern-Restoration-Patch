# Mac memory-safety fixes for your PR

We have four non-GUI safety hooks in KMRP that you could add to your PR. They're
Mac versions of the texture-bucket and grass protections already available on
Windows. They don't need any GUI files, resolution settings, controller code or
new C++ functions.

I'd put them in **K1StrayBugFixes**, since they apply at any resolution and
K1Widescreen already depends on it. Adding Mac support to the separate
TextureBucketSafety and GrassMemorySafety patches would also work. Just give
each hook one owner so we don't install it twice.

## What they fix

- **Texture insertion:** the engine indexes three5000-entry arrays using raw
  OpenGL texture IDs. There's no bounds check before the write. ID5000 is already
  outside the array. This skips the bucket insertion for IDs≥5000 but still
  reaches the native shadow path.
- **Texture maximum:** another path can set the maximum texture ID without a
  range check. The bucket-clearing loop then uses that maximum. This caps it
  at4999. We need this as well as the insertion check.
- **Grass destructor and DestroyGrassPolys:** both can delete the temporary
  pointer and then the primary pointer even when they point to the same
  allocation. These two hooks skip the temporary delete when the pointers match.
  Different pointers still get freed normally.

## Binary these are for

Aspyr KOTOR1.4.0, x86_64 `KOTOR_Exe`,6,333,424bytes.

SHA256:
`C1FCB8D37C702849882A17751C63EE0AF7C2B9CBBC3B31B98A5F0EDBC27C6D71`

Game key: `kotor1_steam_aspyr_macos`.

The addresses below are preferred VA. FILE = VA −0x100000000.
This executable is non-PIE. Two payloads use fixed game addresses, so please
keep the hash check and don't reuse them on a different build.

| Hook | VA | FILE | Original bytes |
| --- | --- | --- | --- |
| Texture insertion | 0x1001d0663 | 0x1d0663 | `48 98 48 c1 e0 04` |
| Texture maximum | 0x1001fa2bf | 0x1fa2bf | `8b 05 e3 b8 43 00` |
| Grass destructor | 0x1001e00cd | 0x1e00cd | `48 8b 7b 40 48 85 ff` |
| DestroyGrassPolys | 0x1001e1627 | 0x1e1627 | `48 8b 7b 40 48 85 ff` |

## Hooks to copy

These are the exact bytes we're using in KMRP. Add them to the selected patch's
`kotor1-steam-aspyr-macos.hooks.toml`. No parameters or dylib symbols are needed.
Keep the byte/REPLACE hooks before detours, as in our combined build.

```toml
[[hooks]]
address = 0x1001d0663
type = "replace"
original_bytes = [0x48, 0x98, 0x48, 0xc1, 0xe0, 0x04]
replacement_bytes = [0x3d, 0x88, 0x13, 0x00, 0x00, 0x72, 0x10, 0x50, 0x48, 0xb8, 0x7b, 0x06, 0x1d, 0x00, 0x01, 0x00, 0x00, 0x00, 0x48, 0x87, 0x04, 0x24, 0xc3, 0x48, 0x98, 0x48, 0xc1, 0xe0, 0x04]

[[hooks]]
address = 0x1001fa2bf
type = "replace"
original_bytes = [0x8b, 0x05, 0xe3, 0xb8, 0x43, 0x00]
replacement_bytes = [0x9c, 0x48, 0xb8, 0xa8, 0x5b, 0x63, 0x00, 0x01, 0x00, 0x00, 0x00, 0x8b, 0x00, 0x3d, 0x88, 0x13, 0x00, 0x00, 0x72, 0x05, 0xb8, 0x87, 0x13, 0x00, 0x00, 0x9d]

[[hooks]]
address = 0x1001e00cd
type = "replace"
original_bytes = [0x48, 0x8b, 0x7b, 0x40, 0x48, 0x85, 0xff]
replacement_bytes = [0x48, 0x8b, 0x7b, 0x40, 0x48, 0x3b, 0x7b, 0x38, 0x75, 0x02, 0x31, 0xff, 0x48, 0x85, 0xff]

[[hooks]]
address = 0x1001e1627
type = "replace"
original_bytes = [0x48, 0x8b, 0x7b, 0x40, 0x48, 0x85, 0xff]
replacement_bytes = [0x48, 0x8b, 0x7b, 0x40, 0x48, 0x3b, 0x7b, 0x38, 0x75, 0x02, 0x31, 0xff, 0x48, 0x85, 0xff]

```

## A few details worth keeping

The insertion hook accepts unsigned IDs0..4999 and replays the original
`cdqe; shl rax,4`. Everything else goes to0x1001d067b, the native shadow
continuation. The `push/movabs/xchg/ret` transfer preserves RAX and balances RSP.
That continuation doesn't need the flags from the valid-path shift.

The maximum hook reads global0x100635ba8, caps its unsigned value at4999 and
preserves RFLAGS. The normal draw-order builder already filters IDs, but the
separate all-texture builder doesn't. That's why the insertion guard alone
isn't enough.

For grass, +0x38 is the primary buffer and +0x40 is the temporary alias. Normal
completion usually clears the alias, but both cleanup routines still need the
ownership check. The hooks zero only the RDI argument when the pointers match,
then replay `test rdi,rdi` so the native JE skips the duplicate delete. Primary
cleanup and field clearing stay as they were.
