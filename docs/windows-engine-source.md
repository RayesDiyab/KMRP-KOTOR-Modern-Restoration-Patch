# Windows engine fixes built without a game executable

Since 2026-10-01 the normal Windows installer build assembles its engine recipe
from tracked patch sites and x86 emitters. Its only required game-derived input
is `TexturePacks/swpc_tex_gui.erf`. Neither an editable clean 1.03 executable nor
a patched gold snapshot is read by `build_kmrp.ps1`.

The full Ubuntu cross-build on 2026-10-01 found that `tools/build_kpatch.py`
still read both files while generating and checking packages. Those reads have
also been removed. `windows-sites.json` now records the measured CD/GOG LAA
header edit separately: FILE `0x926`, little-endian `0F 01` → `2F 01`.
The package checker requires runtime hooks to match
`src/controller-native/kotor1.hooks.toml` exactly, with all three target builds;
it checks every intersecting engine guard and requires the engine's final byte
to equal the hook's original byte, so the core applier cannot invalidate a later
hook. `Test-KpatchSource.py` exercises rejection of corrupted original bytes,
LAA replacement bytes, missing hooks and missing target builds. Runtime byte
validation against the actual game remains unchanged.

This is the source-build change requested during Ubuntu/Proton testing of issue
13. The checks below ran on Ubuntu against source. The complete Windows installer
was then cross-built and its install/restore workflow tested through Proton
Experimental (details below). A native Windows/MSVC build and native Windows
gameplay from this Ubuntu cross-build remain **untested**.
The Steam game had run successfully with Proton Experimental before this change;
that was a vanilla-game test. Subsequent patched-game launch, menus and limited
gameplay were verified under Proton as recorded in the
[Ubuntu follow-up](linux-proton-steam-deck.md#ubuntu-gameplay-follow-up-2026-10-01).

## Source and address conventions

[`windows-sites.json`](../src/engine/windows-sites.json) records the 68 original
code/data runs previously measured against gold v24 in
[`binary-inventory.md`, section 4](../reverse-engineering/binary-inventory.md).
It contains small patch records, not a game image. The assembler expands partial
operands to whole guarded fields, adds the installer-only scaling sites, and
merges adjacent guards into **81 runs**. Addresses are Windows 1.03 **VA**;
original-image FILE offsets are `VA - 0x400000`.

[`build_windows_engine.py`](../tools/build_windows_engine.py) invokes the existing
assembly emitters directly and refuses conflicting source patches. It generates
the eleven pages below, with their established logical base `0x0086D000`. The
module allocates them elsewhere and relocates references at runtime.

| Page | Logical VA | Used bytes | Source emitter |
| --- | --- | --- | --- |
| `.kui` | `0x0086D000` | 445 | `build_map_icon_draw_wrapper`, `build_hit_test_center_fix`, `build_minimap_split_candidate`, `build_map_note_table` |
| `.klb` | `0x0086E000` | 110 | `build_letterbox_scale_wrapper` |
| `.kfs` | `0x0086F000` | 482 | `build_font_scale_wrapper` |
| `.kwl` | `0x00870000` | 17 | `build_wrap_progress_fix` |
| `.ksc` | `0x00871000` | 45 | `build_stack_count_fix` |
| `.kgs` | `0x00872000` | 74 | `build_gutter_side_fix` |
| `.ktn` | `0x00873000` | 42 | `build_leading_newline_fix` |
| `.kmz` | `0x00874000` | 181 | `build_minimap_zoom_fix` |
| `.kfg` | `0x00875000` | 155 | `build_minimap_fog_fix` |
| `.kmn` | `0x00876000` | 4,094 | `build_map_note_table` and Derslok's approved 250-entry table |
| `.kmv` | `0x00877000` | 81 | `build_movie_aspect_fit` |

Each page occupies 4,096 bytes. Only `.kfs` is writable, because it holds its
font cache. The source template is **48,012 bytes**, SHA-256
`BD7865A79C9AA1E59BE65A0A33692B9D782997D57BCB9683D1C769AB7742B0BC`.
Regenerate this identity if any source patch changes.

For example, Capstone disassembly of the generated `.kwl` page produces the
existing 17-byte word-wrap fallback below. Addresses are **logical VA** before
runtime relocation, not FILE offsets. The 443-instruction relocation check
covers the outbound jump along with the other reachable page instructions.

```asm
00870000  mov ebx, [esp+0x18]  ; take the saved remainder pointer
00870004  cmp byte ptr [ebx],0 ; find the remainder's terminator
00870007  je  0087000C         ; terminate the scan
00870009  inc ebx             ; consume another byte
0087000A  jmp 00870004         ; continue scanning
0087000C  jmp 0045A785         ; rejoin the engine's existing line-end path
```

This was read from `assemble().block[0x3000:0x3011]`, not from the emitter's
assembly text. The surrounding progress guard and its historical investigation
are in the [font and text-fix record](font-scaling.md).

## Every guarded original-image run

The table below is generated from `assemble().runs()` in
`tools/build_windows_engine.py`: **81 runs covering 768 guarded bytes**.
`Original` is the source-authored runtime guard; `Recipe` is the replacement
before `ResolutionPatch` specializes it for the chosen size. Guards include
unchanged instruction/operand bytes where needed; 768 is a guarded-byte count,
not the number of bytes whose values differ. Feature 1 is the core engine and
resolution layout; feature 2 is movie playback. The per-site mechanisms are
recorded in the [historical 68-run inventory](../reverse-engineering/binary-inventory.md#4-the-68-code-and-data-runs).

These are original-image **VA** and **FILE** coordinates, with
`FILE = VA - 0x400000`. The injected pages above use logical runtime addresses;
if an offline PE reference is generated, their FILE coordinates instead use
`FILE = VA - 0x492000`. Runtime allocation relocates those pages and is not an
edit to the disk executable.

| VA | FILE | Bytes | Original (hex) | Recipe (hex) | Feature |
| --- | --- | ---: | --- | --- | --- |
| `0x00403D6C` | `0x003D6C` | 4 | `80020000` | `700d0000` | Movies |
| `0x00403D78` | `0x003D78` | 4 | `e0010000` | `a0050000` | Movies |
| `0x004057AC` | `0x0057AC` | 7 | `8b4e488b013bd8` | `e94f1847009090` | Movies |
| `0x0040AA65` | `0x00AA65` | 4 | `80020000` | `700d0000` | Core |
| `0x0040AA85` | `0x00AA85` | 4 | `e0010000` | `a0050000` | Core |
| `0x0040B6C7` | `0x00B6C7` | 4 | `80fdffff` | `90f2ffff` | Core |
| `0x0040B6DA` | `0x00B6DA` | 4 | `20feffff` | `60faffff` | Core |
| `0x0040BA6C` | `0x00BA6C` | 4 | `80fdffff` | `90f2ffff` | Core |
| `0x0040BA83` | `0x00BA83` | 4 | `20feffff` | `60faffff` | Core |
| `0x00415E0D` | `0x015E0D` | 5 | `8b465085c0` | `e9eed14500` | Core |
| `0x00417992` | `0x017992` | 10 | `8b400c89410c8b4c246c` | `e92e7845009090909090` | Core |
| `0x0041A2F2` | `0x01A2F2` | 15 | `8d043f2bc885db897c241c894c2424` | `e92d7d450090909090909090909090` | Core |
| `0x0041B1C4` | `0x01B1C4` | 1 | `03` | `8b` | Core |
| `0x0041B26B` | `0x01B26B` | 1 | `03` | `8b` | Core |
| `0x0041B339` | `0x01B339` | 1 | `03` | `8b` | Core |
| `0x0041B3AE` | `0x01B3AE` | 1 | `03` | `8b` | Core |
| `0x0041B46D` | `0x01B46D` | 12 | `897c2420c744242400000000` | `e98e6b450090909090909090` | Core |
| `0x0041B48C` | `0x01B48C` | 5 | `8d043f2bc8` | `2bcf33ff90` | Core |
| `0x0041B507` | `0x01B507` | 2 | `03ea` | `9090` | Core |
| `0x0041B52E` | `0x01B52E` | 1 | `01` | `00` | Core |
| `0x0041B553` | `0x01B553` | 1 | `03` | `8b` | Core |
| `0x0045992A` | `0x05992A` | 26 | `0fbf0560947b008d0480d1e00fbf906e947b000fbf806c947b00` | `e9d1a64100909090909090909090909090909090909090909090` | Core |
| `0x0045A3B7` | `0x05A3B7` | 6 | `0f8c7f040000` | `909090909090` | Core |
| `0x0045A3DC` | `0x05A3DC` | 6 | `0f8c5a040000` | `909090909090` | Core |
| `0x0045A5E0` | `0x05A5E0` | 16 | `8b46144b3bd8894c24100f8444020000` | `4b3b5c2418894c24107705e9105a4100` | Core |
| `0x0045A850` | `0x05A850` | 7 | `83ec4c894c2404` | `e9454941009090` | Core |
| `0x004A1770` | `0x0A1770` | 13 | `6aff685c7e710064a100000000` | `e903da3c009090909090909090` | Core |
| `0x005F0C65` | `0x1F0C65` | 4 | `20030000` | `700d0000` | Core |
| `0x005F0C6F` | `0x1F0C6F` | 4 | `58020000` | `a0050000` | Core |
| `0x005F5B3B` | `0x1F5B3B` | 12 | `80020000c7442410e0010000` | `700d0000c7442410a0050000` | Movies |
| `0x0062540D` | `0x22540D` | 4 | `20000000` | `80000000` | Core |
| `0x006256DC` | `0x2256DC` | 11 | `b80100007c0b3d18010000` | `400600007c0b3d84030000` | Core |
| `0x006256F6` | `0x2256F6` | 4 | `b8010000` | `40060000` | Core |
| `0x00625759` | `0x225759` | 4 | `18010000` | `84030000` | Core |
| `0x00626F95` | `0x226F95` | 4 | `20000000` | `80000000` | Core |
| `0x0062B39B` | `0x22B39B` | 5 | `e8b0990600` | `e8901d2400` | Core |
| `0x0068AC9F` | `0x28AC9F` | 5 | `e85cd4ffff` | `e85ca31e00` | Core |
| `0x0068C4E3` | `0x28C4E3` | 4 | `00040000` | `700d0000` | Core |
| `0x0068C4F4` | `0x28C4F4` | 8 | `05000074303d4006` | `00000074303d0000` | Core |
| `0x006928B3` | `0x2928B3` | 4 | `80020000` | `be0a0000` | Core |
| `0x006928C3` | `0x2928C3` | 4 | `e0010000` | `78050000` | Core |
| `0x0069405B` | `0x29405B` | 4 | `20000000` | `40000000` | Core |
| `0x006940DC` | `0x2940DC` | 4 | `10000000` | `20000000` | Core |
| `0x006944A8` | `0x2944A8` | 6 | `d83d48777400` | `da7b0c909090` | Core |
| `0x006944C4` | `0x2944C4` | 6 | `d83dd4557400` | `da7b10909090` | Core |
| `0x006946F4` | `0x2946F4` | 5 | `e80747eeff` | `e807891d00` | Core |
| `0x0069471A` | `0x29471A` | 13 | `f689442424b81400000083c1f6` | `ec89442424b82800000083c1ec` | Core |
| `0x00694763` | `0x294763` | 4 | `0e000000` | `1c000000` | Core |
| `0x00694777` | `0x294777` | 4 | `f983c2f9` | `f283c2f2` | Core |
| `0x00694A13` | `0x294A13` | 4 | `10000000` | `20000000` | Core |
| `0x00694A39` | `0x294A39` | 5 | `e87247eeff` | `e842861d00` | Core |
| `0x00694A53` | `0x294A53` | 4 | `f883c2f8` | `f083c2f0` | Core |
| `0x00694AAC` | `0x294AAC` | 5 | `e8ff46eeff` | `e8cf851d00` | Core |
| `0x00694AC4` | `0x294AC4` | 4 | `20000000` | `40000000` | Core |
| `0x00694AD0` | `0x294AD0` | 5 | `f05283c0f0` | `e05283c0e0` | Core |
| `0x0069505C` | `0x29505C` | 12 | `00020000c744242000010000` | `b8060000c7442420d0020000` | Core |
| `0x00695082` | `0x295082` | 12 | `b8010000c744242000010000` | `c6050000c7442420d0020000` | Core |
| `0x006A74D2` | `0x2A74D2` | 48 | `0fbf4f6c894c240cdb44240cd80d88577500e8a33905000fbf576e2bd08954240cdb44240cd80dace97300e88a390500` | `0fbf476e83c0035199b906000000f7f95990909090909090909090909090909090909090909090909090909090909090` | Core |
| `0x006A7560` | `0x2A7560` | 50 | `0fbf4f6c0fbf5f6e894c240cdb44240cd80d88577500e8113905008bd32bd08954240cdb44240cd80dace97300e8fa380500` | `0fbf5f6e8bc383c0035199b906000000f7f95990909090909090909090909090909090909090909090909090909090909090` | Core |
| `0x006A7943` | `0x2A7943` | 41 | `0fbf556c89542410db442410d80d88577500e8323505000fbf4d6e2bc88bc1992bc2d1f82bc383e805` | `0fbf456e83c0035199b906000000f7f9592bc383e80590909090909090909090909090909090909090` | Core |
| `0x006A7B59` | `0x2A7B59` | 48 | `8b7e180fbf576c89542424db442424d80d88577500e8193305000fbf4f6e2bc88bc18b4c2408992bc2d1f82bc183c0fb` | `8b7e180fbf476e83c0035199b906000000f7f9592b44240883c0fb909090909090909090909090909090909090909090` | Core |
| `0x006A7CD0` | `0x2A7CD0` | 28 | `8b96c419000089442410894c240c8d8ec41900008d44240450ff5204` | `e92b631c009090909090909090909090909090909090909090909090` | Core |
| `0x006A7F3D` | `0x2A7F3D` | 55 | `0fbf436c0fbf7b6e89442414db442414d80d88577500e8342f05008bcf2bc88bc1992bc28b542410d1f82bf8897c24280fbf4b6c8b7e10` | `0fbf7b6e8bc783c0035199b906000000f7f9592bf88b542410897c2428909090909090909090909090909090909090900fbf4b6c6a645f` | Core |
| `0x006A8C4C` | `0x2A8C4C` | 44 | `0fbf476c89442410db442410d80de45a7500e8292205000fbf4f6e2bc88bc1992bc28b542464d1f889442428` | `0fbf476e5083c00399b906000000f7f9592bc8894c24288b5424649090909090909090909090909090909090` | Core |
| `0x006A8E1D` | `0x2A8E1D` | 9 | `f686081a000002744f` | `e91d521c0090909090` | Core |
| `0x006AB8EF` | `0x2AB8EF` | 4 | `2a000000` | `2a000000` | Core |
| `0x006ACB20` | `0x2ACB20` | 4 | `2a000000` | `2a000000` | Core |
| `0x006B4FA9` | `0x2B4FA9` | 4 | `38000000` | `38000000` | Core |
| `0x006B527F` | `0x2B527F` | 4 | `38000000` | `38000000` | Core |
| `0x006B5332` | `0x2B5332` | 36 | `130000004983e11583c1158bc18b4c24202bd0894424288b44242403ca83c025894c2420` | `13000000e9c5bc1b00909090909090909090909090909090909090909090909090909090` | Core |
| `0x006B55E3` | `0x2B55E3` | 4 | `38000000` | `38000000` | Core |
| `0x006C265F` | `0x2C265F` | 4 | `38000000` | `38000000` | Core |
| `0x006C2A23` | `0x2C2A23` | 4 | `38000000` | `38000000` | Core |
| `0x006CD8D9` | `0x2CD8D9` | 4 | `28000000` | `28000000` | Core |
| `0x006CDB79` | `0x2CDB79` | 4 | `28000000` | `28000000` | Core |
| `0x006DE012` | `0x2DE012` | 4 | `19000000` | `19000000` | Core |
| `0x006DE031` | `0x2DE031` | 1 | `02` | `02` | Core |
| `0x006DE08E` | `0x2DE08E` | 6 | `83e91e83c01e` | `83e91e83c01e` | Core |
| `0x006DE0D1` | `0x2DE0D1` | 13 | `90909090909090909090909090` | `90909090909090909090909090` | Core |
| `0x0075477C` | `0x35477C` | 4 | `00336900` | `00d18600` | Core |
| `0x00755788` | `0x355788` | 3 | `b96ddb` | `254992` | Core |

To regenerate these rows, import `tools/build_windows_engine.py` and print
`assemble().runs()`; the regression compares the original and replacement
bytes against all 68 independently documented historical runs, then validates
the complete serialized runtime data at all tested sizes.

## Installer and runtime

The installer embeds the template as `Kmrp.engine.source`.
[`WindowsEnginePatch.cs`](../src/patcher/WindowsEnginePatch.cs) validates its
checksum, layout, site ranges and relocation ownership, then specializes its
values through the existing `ResolutionPatch`. A scratch layout array preserves
the established FILE coordinates; it has no executable header and is never
installed as a game executable. Every field scaling touches must be covered by
an authored guard or an injected page, otherwise installation fails.

The installer writes the same `KMRPKPM2` runtime format to `kmrp-kpm.dat`.
[`K1KpmApplier.cpp`](../src/controller-native/K1KpmApplier.cpp) continues to
check every chosen original byte before writing anything, allocate and relocate
the pages, pause the game's other threads during writes and roll back written
runs on a write failure. Steam's instructions are checked after decryption.
Movies runs retain feature bit 2; map-note corrections retain the single
feature-bit-4 enable edit. The temporary movie-mode operands now share a
12-byte guarded run including the unchanged instruction bytes between them.

The source assembler finds **46 relocation fields** and disassembles **443
reachable instructions**. It compares byte scanning with decoded block operands
and proves the instructions and inbound targets after moves by `+0x1F7A3000`
and `-0x500000`. The regression removes each relocation in turn: every omission
must fail the proof.

## Preserved behavior and limits

The shared scale is still `max(1.0, height / 720)`. The same C# code computes map
geometry, list rows, popups, checkbox geometry and marker sizes. Marker signed
offsets retain their existing clamp. Game hash validation, ownership manifests,
upgrade/restore, the controller hooks, and optional feature selection are
unchanged. The editable CD/GOG installation still manages the 4 GB header flag;
Steam's executable is unchanged by installation.

`--apply` remains an optional **offline reference** command: it requires a
supported editable executable, checks its identity and every source guard, and
writes a separate reference image. It is not invoked by the normal build.
Legacy hashes remain in `GoldPatch` for identity/restore; the delta-loading and
snapshot-overlay implementation has been removed. Historical gold builders and
documents remain useful for comparison.

The source test compiled all eight C# installer source files with Mono and
generated runtime data at all 66 shipped sizes plus 640×480, 1919×1079 and
3457×1453. It checks the historical sites, page sizes, relocation omission
detection, original guards, dimensions, scale and optional features. Those
checks do not establish native DLL loading or rendered game behavior. No clean
editable executable or gold image was available here for the repository's full
binary-inventory and offline-reference comparison.

## Verify

```powershell
python tools/build_windows_engine.py --out build/kmrp/windows-engine.bin
python testing/regression/Test-WindowsEngineSource.py --csc C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
.\build_kmrp.ps1 -TexturePack "<Steam game>\TexturePacks\swpc_tex_gui.erf"
```

On Ubuntu the regression can use an extracted Mono tree with
`--mono-root <tree>`; it needs `usr/bin/mono-sgen`, the compiler and framework
assemblies, but no system installation. Python needs `capstone`.

With the Windows installer and optional editable game fixture available, run
`testing/regression/Test-KpmEdition.ps1` and
`testing/regression/Test-ReinstallOverOlderBuild.ps1`, then compare generated
reference images with `tools/build_binary_inventory.py` and the historical
gold. Finally launch under Proton and inspect `kmrp-kpm.log`; see the
[Ubuntu test record](linux-proton-steam-deck.md#ubuntu-installer-test-2026-10-01)
for the measured launch/menu coverage and issue 13's closure.

## Ubuntu cross-build and installation record (2026-10-01)

Ubuntu 26.04.1 LTS built KPM's DLL and Bink proxy from submodule `2a784bf`
using its MinGW Makefile and `KProxy/build-mingw.sh`. The controller module used
MinGW-w64 GCC 13.2, the same nine translation units and `exports.def` listed in
`src/controller-native/build.cmd`, the pinned SDL 3.4.16 headers, and static GCC
runtime linkage. Mono 6.14 compiled the eight installer sources with the same
embedded-resource names and framework references as `build_kmrp.ps1`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Installer 1.5.0 | 168,698,880 | `7C8CB15327EA353564CAFCF3F52E1459EBDC80178145AF9E4044A88565877B38` |
| KPM runtime | 1,376,768 | `78FC9E1391C7B664A7E033A5C6CB5C26FBFC9E91832AEEFCF280E1DE793B96C4` |
| Bink proxy | 16,384 | `BC210EDCCB411F83A4E9D3424770657700E74C5D68300DB022C7BCB84C2134DC` |
| Controller module | 917,239 | `FBC2738B541A93A2026B0EAACB6423A75784F13D4F44DB24D5511BE6C44C1D79` |

The full resource build produced 66 resolution archives. Pool verification
reconstructed every archive exactly: 44,418 entries, 16,253 distinct objects.
The Proton audit parsed 5,478 GUIs and resolved the active HUD name font at all
66 resolutions without case collisions. Font checks covered 1,170 font entries,
with the documented scale-12 shared-atlas exception.

The actual installer ran with `--in-place` and `--restore` in an isolated Steam
fixture at 3440×1440 and 1920×1080, using Proton Experimental
`experimental-11.0-20260924-x86_64` and Steam's installed Sniper runtime. Both
installs wrote 1,526 Override files matching the packaged archives. Both restores
recovered the incoming EXE, INI and Bink hashes and removed installed assets.

The live Steam game was then installed at 3440×1440. All 1,854 Override files
matched their ownership manifest; the additional files are generated from the
live game's artwork/text inputs. All owned runtime files matched their hashes,
the original INI and Bink DLL remained preserved, and Steam's 4,395,008-byte
executable retained SHA-256
`34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`.
At this stage the checks verified installation, not native hook execution or
gameplay. The first installer capture failed: GNOME denied the direct call and
its X11 fallback returned black images. **Follow-up correction, 2026-10-01:**
Flameshot subsequently captured the installer result; Steam launched the
patched game, all 81 guarded runs and 46 relocations applied, and menus and
limited gameplay were exercised. See the
[Ubuntu test record](linux-proton-steam-deck.md#ubuntu-installer-test-2026-10-01)
and its gameplay follow-up for evidence and remaining coverage.
