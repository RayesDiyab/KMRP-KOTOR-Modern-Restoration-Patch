# Mac applicability of Windows memory-safety fixes

Reference, audited 2026-10-02; follows [the documentation standard](../docs/documentation-standard.md).
The applicability audit was followed by four guarded core REPLACE hooks and machine-code regression tests. Gameplay crash reproduction and grass-area play-testing remain pending.

Build: clean Aspyr 1.4.0 x86_64 `KOTOR_Exe`, 6,333,424 bytes, SHA-256
`c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71`.
All Mac addresses below are preferred VA; original-text FILE = VA − 0x100000000.
Windows addresses are VA from the checked-in `src/controller-native/kotor1.hooks.toml`;
Windows FILE = VA − 0x400000. Windows bytes and calling conventions cannot be copied to Mac.
The initial audit changed no executable or installed game file. Implementation now adds runtime hooks to the core package; the clean executable and installed game remain unchanged.

## Result

| Windows protection | Mac applicability | Remaining validation |
| --- | --- | --- |
| Texture insertion bounds, `0x0046BE64`; maximum saturation, `0x0041FEB5` | Implemented insertion range check and maximum saturation. Draw ordering already has a native range filter. | Machine-code boundary tests pass; natural high-ID session reproduction pending. |
| Grass alias checks, `0x004A8380`, `0x004A847C` | Implemented equality guards at both cleanup sites. Normal completion clears the temporary alias. | Establish a live cleanup path retaining the alias; no gameplay double free reproduced. |
| Save-resource buffer free, `0x005DDE32` | Do not port: Mac already releases the copied resource buffer on normal exit and its exception cleanup path. An additional free would duplicate native cleanup. | Repeated-save memory profiling was not run; this conclusion covers the particular Windows abandoned-buffer defect. |

## Texture buckets

Three arrays at `0x1005f6cb0`, `0x10060a530`, `0x10061ddb0` each contain
5000 entries of 16 bytes. Initialization at `0x1001d40e9` zeros 80000 bytes per
array; the reset loop at `0x1001951c4` visits 5000 entries.

The driver supplies IDs through `glGenTextures` (stub `0x1004b0672`) at
`0x1001f70e8`. The first generated ID is copied into texture field +0x7c at
`0x1001f70f3`; the virtual texture getter `0x1001f7362` returns that field.
Material getter `0x1001945aa` forwards it to insertion at `0x1001d0611`:

```asm
1001d065e call 1001945aa       ; raw texture ID
1001d0663 cdqe                ; signed widening, no bounds check
1001d0665 shl rax,4           ; 16-byte bucket stride
1001d0669 lea rdi,[meshbase]   ; 1005f6cb0
1001d0670 add rdi,rax         ; unchecked address
1001d0676 call 1001de004      ; append part to bucket
```

ID 4999 selects FILE-relative bucket offset 79984; ID 5000 selects 80000,
one entry beyond the array. A draw-order filter cannot protect this earlier write.
`AurTextureGetOrdering` at `0x1001fa1e3` already accepts only IDs 1..4999:
`lea ecx,[rsi-1]; cmp ecx,0x1386; ja skip` at `0x1001fa24d`..`0x1001fa256`.
It resets and updates maximum global `0x100635ba8` only for accepted IDs.
However the all-texture builder writes that global without the same filter at
`0x1001fa195`..`0x1001fa19d`. Getter `0x1001fa2bb` returns it unclamped;
caller `0x1001d0d4f` clears all three arrays through maxID inclusive at
`0x1001d0d8b`..`0x1001d0dbd`. Thus saturation remains relevant to a potentially
unbounded producer, although the normal draw-order rebuild already bounds it.
Call ordering that exposes an oversized builder maximum has not been reproduced.

## Grass ownership

Identification follows `Scene::AddFacesToBins` at `0x10019cfd6`: it constructs
an 0x88-byte bin through `0x1001e005c`, then calls triangle addition at
`0x1001e01a6`. Its rendering counterpart calls `0x1001e16a4`.
These are semantic matches for CAurTriangleBin, rather than recovered symbol names.

```asm
1001e0922 call 1004b020a       ; operator new[]: one allocation
1001e0927 mov rbx,rax
1001e092a mov [r14+38],rbx    ; primary pointer
1001e093a mov [r14+40],rbx    ; alias of that same allocation
1001e15e7 mov qword [r14+40],0 ; normal construction completion clears alias
```

Rendering restores the alias at `0x1001e17b9`..`0x1001e17bd`, calls wind update
at `0x1001e17c7`, then clears it at `0x1001e17cc`. This limits the ordinary
lifetime of the alias; allocation alone does not prove a gameplay crash.

Both cleanup routines test only non-nullness. Destructor `0x1001e00ba` deletes
+0x40 at `0x1001e00d6`, clears it, then independently deletes +0x38 at
`0x1001e00ec`. DestroyGrassPolys `0x1001e160e` performs the same sequence at
`0x1001e1630` and `0x1001e1647`, under its existing flags. All four target
`operator delete[]`, stub `0x1004b01fe`. If the alias survives into either eligible
cleanup, both calls receive the same allocation. Clearing +0x40 does not clear
+0x38. Windows' equality guard is therefore meaningful on Mac, using Mac fields
+0x38/+0x40 and the Mac ABI; Windows uses +0x38/+0x3c.

## Save-resource ownership

The resource overload at `0x100365a38` is called from module-save code at
`0x1004658c9` and `0x100465a01`. It allocates a copy with `operator new[]` at
`0x100365bab`, keeps it in r15, copies resource data, and stores it in the stack
resource object's buffer member `[rbp-0x68]` at `0x100365bd8`.
`CERFResWrite` at `0x100365cc0` borrows that pointer to call `CExoFileWrite`
at `0x100365cec`; it does not release the buffer itself.

```asm
100365c4a mov rdi,[rbp-68]    ; same owned buffer after write
100365c53 test rdi,rdi
100365c56 je 100365c65
100365c58 call 1004b0204      ; native operator delete
100365c5d mov qword [rbp-68],0 ; ownership cleared
```

The exception cleanup likewise loads `[rbp-0x68]`, tests it and calls the same
deallocator at `0x100365caa`. The filename overload at `0x10036564c` also
releases its temporary file buffer, using delete[] at `0x100365851` after write.
This does not claim that every possible save leak or allocator issue is absent;
it disproves the specific missing post-write free targeted by the Windows hook.

## Reverification

Use `otool -tvV` or Capstone on the clean binary and `otool -Iv` to resolve
allocator and OpenGL stubs. Verify the SHA and length first. The critical original
instruction bytes were independently decoded with Capstone from that file:

| Mac VA | FILE | Size | Original bytes | Meaning; replacement |
| --- | --- | --- | --- | --- |
| `0x1001d0663` | `0x1d0663` | 2 | `48 98` | unchecked ID widening; none |
| `0x1001fa2bf` | `0x1fa2bf` | 6 | `8b 05 e3 b8 43 00` | maximum load; none |
| `0x1001e092a` | `0x1e092a` | 4 | `49 89 5e 38` | primary store; none |
| `0x1001e093a` | `0x1e093a` | 4 | `49 89 5e 40` | alias store; none |
| `0x1001e00d6` | `0x1e00d6` | 5 | `e8 23 01 2d 00` | destructor alias delete; none |
| `0x1001e00ec` | `0x1e00ec` | 5 | `e8 0d 01 2d 00` | destructor primary delete; none |
| `0x1001e1630` | `0x1e1630` | 5 | `e8 c9 eb 2c 00` | grass cleanup alias delete; none |
| `0x1001e1647` | `0x1e1647` | 5 | `e8 b2 eb 2c 00` | grass cleanup primary delete; none |
| `0x100365bab` | `0x365bab` | 5 | `e8 5a a6 14 00` | save buffer allocation; none |
| `0x100365c58` | `0x365c58` | 5 | `e8 a7 a5 14 00` | save normal cleanup; none |
| `0x100365caa` | `0x365caa` | 5 | `e8 55 a5 14 00` | save exception cleanup; none |

## Implemented hooks and validation

All four hooks live in `macos/patches/kmrp-layout/kotor1-steam-aspyr-macos.hooks.toml`,
so neither controller nor map-note options disable them. KPM verifies the exact
original bytes, allocates the REPLACE block near the site, writes a relative jump
and pads the remaining original bytes with NOPs. It appends a jump to the first
untouched instruction. No production callback or new allocator is involved.

| Hook VA | FILE | Guard size / original | Replacement behavior |
| --- | --- | --- | --- |
| `0x1001d0663` | `0x1d0663` | 6 / `48 98 48 c1 e0 04` | unsigned ID <5000 replays cdqe/shl; otherwise transfer to native shadow continuation `0x1001d067b` without bucket insertion |
| `0x1001fa2bf` | `0x1fa2bf` | 6 / `8b 05 e3 b8 43 00` | load maximum global, unsigned saturation to4999, preserve flags; resume at native pop rbp/ret |
| `0x1001e00cd` | `0x1e00cd` | 7 / `48 8b 7b 40 48 85 ff` | load alias, compare primary, zero RDI only if equal, test RDI for native JE |
| `0x1001e1627` | `0x1e1627` | 7 / `48 8b 7b 40 48 85 ff` | same guard in DestroyGrassPolys |

The target Mach-O header has no MH_PIE flag (`otool -hv`); the embedded preferred
VA maximum-global and shadow-continuation pointers use that fixed load convention.
The insertion transfer uses `push rax; movabs rax,target; xchg [rsp],rax; ret`:
RAX and RSP are preserved. The valid path sets flags exactly as the original
shift. The invalid path reaches an unconditional shadow append without a flag-based
branch. The maximum hook brackets its comparison with PUSHFQ/POPFQ. Both grass
hooks replay TEST RDI, so the original null-skip branch remains authoritative;
primary deletion and the native field clearing remain untouched.

`testing/regression/Test-MacMemorySafety.py --exe <clean KOTOR_Exe>` verifies
SHA/length, no PIE, original guards and complete instruction boundaries, then
compiles an x86_64 runner and executes the actual TOML payloads under Rosetta.
Only the two embedded absolute operands are relocated to test-owned data/code;
their original game values are asserted first. Fixed game-address mappings failed
with ENOMEM in the standalone runner, so it does not claim game-address execution.
Test IDs: 0, 1, 4998, 4999, 5000, 5001, 0x7fffffff, 0x80000000, 0xffffffff.
Tests check insertion offset/skip, shadow continuation, saturation and flag
preservation. Both grass payloads are exercised with null, equal and distinct
pointers; the original JE decision and retained object fields are checked, as is
one deletion per primary allocation in the native cleanup sequence. Optional
`--kpatch` arguments verify that built packages carry the exact source guards and
payloads. This is controlled machine-code execution, not gameplay play-testing.


Validation run 2026-10-02: all four variants built and passed KPM hook validation,
x64 parameter validation and overlap detection in isolated package directories.
Hook totals: full 88; no-controller 68; no-map-notes 87; minimal 67. Each has
9 REPLACE hooks, including these four. Exact packaged safety payloads match source.
The layout regression also passes 55 sites across 76 resolutions; documentation
links and whitespace checks pass. Package SHA-256 values (local build artifacts):

| Variant | SHA-256 |
| --- | --- |
| full | `1b167dc1eddec02174b927218f91a21d8bc33cffddf83d723b2661a540691c90` |
| minimal | `260ca7c994be7e913739957c7f1d6d8a853ac6a12dc37505e590753bc69c7bc1` |
| no-controller | `8335f4d6ed6ab329b52a2c6afa08adce15744e00c8f332af903e4da7789efc94` |
| no-map-notes | `7568c8fe2798dbac4d16142a32152559d50974227a65b81f8d0b9a31ea12e9c2` |
