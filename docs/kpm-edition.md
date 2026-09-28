# The KPM edition: KMRP through KOTOR Patch Manager

**Reference.** What the KPM edition does, byte for byte, and how it is proved to
make the same game as the standalone installer. Built and measured on 2026-09-28;
the lab record of how it was designed is in the session notes summarised under
*Rejected alternatives* below.

## The build this describes

| | |
| --- | --- |
| Unmodified executable | CD/"editable" KOTOR 1.03, `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`, 4,042,752 bytes (`build-inputs/swkotornopatch.exe`) |
| Gold | `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`, 4,087,808 bytes (`build/kmrp/swkotor_gold_v24_movieaspect.exe`) |
| KOTOR Patch Manager | 0.7.1 (release zip `0EFEFAC8…`, source at the same tag), read and run on 2026-09-28 |
| Module | `kmrp-controller.module`, 241,664 bytes, `0C89C330245F752A303A22D5B731C2E16D19D4731078413B195F01C71972E955` |
| Installers | standalone `125DEA64…`, KMRP for KPM `2C715CA5…`; `KMRP.kpatch` `0E454D87…`, `KMRP Controller.kpatch` `5A29F9CD…`, `KMRP Movies.kpatch` `77CC3D71…`, `KMRP Map Notes.kpatch` `1D365F9F…` |

Until later on 2026-09-28 the edition shipped as two `.kpatch` files, KMRP with
and without its controller, picked one or the other. It is now four patches, one
per fix (section 5).

Addresses are **VA** unless marked FILE. For the original sections `FILE = VA −
0x400000`; for gold's eleven appended sections `FILE = VA − 0x492000`
([`binary-inventory.md`](../reverse-engineering/binary-inventory.md)).

## 1. Two editions, one source

KMRP ships two ways, built by one `build_kmrp.ps1` run from the same sources:

| | standalone | KPM edition |
| --- | --- | --- |
| Output | `dist\KMRP - KOTOR Modern Restoration Patch.exe` | `dist\KMRP for KPM\`: `KMRP for KPM.exe`, `KMRP.kpatch`, `KMRP Controller.kpatch`, `KMRP Movies.kpatch`, `KMRP Map Notes.kpatch`, README, KPM's MIT licence |
| swkotor.exe | the gold delta written in, per resolution | **never modified** (KPM's own `4gb-patch` sets the large-address flag) |
| Executable changes | in the file | applied in memory by KMRP's module, from `kmrp-kpm.dat` |
| Run-time hooks | KMRP's own copy of the KPM runtime, `patch_config.toml` written by the installer | KPM's runtime, from the `.kpatch` hook table |
| Memory-safety fixes | KMRP's copies of KPM's three patches | KPM's own patches, **required** by the `.kpatch` |
| Driver compatibility | Synchro's standalone K1DC, optional | not installed; Synchro's own `.kpatch` in KPM |
| Controller, movies, map notes | the controller and map-note options are checkboxes; the movie fixes are always in | three optional patches, ticked in KPM beside the required `KMRP` |
| Override, `swkotor.ini`, DPI, NVIDIA | installed | installed, by the same code |

What is shared, so the editions cannot drift apart:

- **The executable's bytes.** The KPM installer builds the final image exactly as
  the standalone does -- the unmodified executable, the embedded gold delta,
  `ResolutionPatch` for the resolution, the map-note flag on (`GoldPatch.Apply`) --
  and records only how it differs from the unmodified executable, each change
  tagged with the patch it belongs to (`KpmEditionOperations.BuildData`,
  `src/patcher/KpmEdition.cs`). No per-resolution rule exists in two places.
- **The hook sets.** Both come from `src/controller-native/kotor1.hooks.toml`
  through `tools/kmrp_controller.py`: `installed_set(controller)` for the
  standalone, `kpm_patch_hooks(id)` for each KPM patch, from the hook's
  `kpm_patch` key. The KPM sets leave out the five hooks tagged `kpm_provided_by`
  (KPM's three memory-safety patches make them) and require those patches instead.
- **The module.** One binary: the standalone loads it from its own runtime, KPM
  from `patches\<id>.dll`, once for each KMRP patch that has hooks. Its applier
  runs only in an unmodified image, and only in the core patch's copy (below).

## 2. What the module applies, and why the code has to move

Gold's delta has three parts; the KPM edition reproduces all three in memory:

| part | size | in the KPM edition |
| --- | --- | --- |
| Runs in the original image | 81 runs in `.text` (560 bytes) and 2 in `.rdata` (5 bytes) at the byte level; 89 to 91 runs of 576 to 582 bytes once the per-resolution values and the relocated fields are added (measured at 1024x768, 1920x1080, 3440x1440) | written by the module after every original byte is checked |
| Eleven appended sections, `.kui` ... `.kmv`, `0x0086D000`-`0x00877FFF` | 45,056 bytes, 5,726 used | copied as one block into memory the module allocates, and relocated |
| PE header | 71 byte-runs, 156 bytes | not written. Only the large-address flag matters at run time, and KPM's `4gb-patch` sets it |

**The sections cannot go back to their own addresses.** In an unmodified process
the range is not free: measured on 2026-09-28 with `VirtualQueryEx` over a running
unmodified game from its first sample to the main menu, `0x0086D000`-`0x0086FFFF`
is free and everything from `0x00870000` is a mapped view (`COMMIT MAPPED`,
`0x11000` bytes). The three free pages are also below the 64 KB allocation
granularity after the image's end, so nothing can be reserved there either. So the
block is copied, layout intact, to wherever `VirtualAlloc` puts it, and every
address that names it is moved by the difference.

## 3. Every field that moves: the relocation table

`tools/kpm_relocations.py` finds them in gold, twice, by independent methods that
must agree: a byte scan (every changed byte and every byte of the block's decoded
code, for `E8`/`E9`/`0F 8x` rel32 branches and 32-bit values in range), and
disassembly (aligned linear sweeps over the changed runs, recursive descent through
the block from the inbound entry points). It stops the build otherwise. It then
**proves** the table: it moves the block to a test base, relocates, and
disassembles all 443 decoded instructions again -- each must be the same
instruction with every operand that named the block moved by exactly the delta and
every other operand unchanged -- and it re-discovers every inbound reference on its
own and requires each to be relocated. A table missing any one entry fails, which
was checked by dropping entries of each kind (2026-09-28).

It also refuses what it cannot relocate: an indirect jump through a register or the
block (a switch table), or a value naming the block stored in the block's data.
There are none. Indirect calls are allowed: `.kmv`'s `call [0x0073D484]` goes
through the import table, and `.kfs`'s `call edx` and `.klb`'s `call [edx+4]` are
virtual calls through game objects' vtables.

`IN` fields are outside the block and name it (add the delta); `OUT` fields are in
the block and name game code (subtract it); `ABS` fields are in the block and name
the block (add it). A rel32 from the block to the block needs nothing.

| kind | field VA | FILE | where | instruction |
| --- | --- | --- | --- | --- |
| IN | `0x004057ad` | `0x0057ad` | .text | `0x004057ac` `jmp 0x877000` |
| IN | `0x00415e0e` | `0x015e0e` | .text | `0x00415e0d` `jmp 0x873000` |
| IN | `0x00417993` | `0x017993` | .text | `0x00417992` `jmp 0x86f1c5` |
| IN | `0x0041a2f3` | `0x01a2f3` | .text | `0x0041a2f2` `jmp 0x872024` |
| IN | `0x0041b46e` | `0x01b46e` | .text | `0x0041b46d` `jmp 0x872000` |
| IN | `0x0045992b` | `0x05992b` | .text | `0x0045992a` `jmp 0x874000` |
| IN | `0x0045a5ec` | `0x05a5ec` | .text | `0x0045a5eb` `jmp 0x870000` |
| IN | `0x0045a851` | `0x05a851` | .text | `0x0045a850` `jmp 0x86f19a` |
| IN | `0x004a1771` | `0x0a1771` | .text | `0x004a1770` `jmp 0x86f178` |
| IN | `0x0062b39c` | `0x22b39c` | .text | `0x0062b39b` `call 0x86d130` |
| IN | `0x0068aca0` | `0x28aca0` | .text | `0x0068ac9f` `call 0x875000` |
| IN | `0x006946f5` | `0x2946f5` | .text | `0x006946f4` `call 0x86d000` |
| IN | `0x00694a3a` | `0x294a3a` | .text | `0x00694a39` `call 0x86d080` |
| IN | `0x00694aad` | `0x294aad` | .text | `0x00694aac` `call 0x86d080` |
| IN | `0x006a7cd1` | `0x2a7cd1` | .text | `0x006a7cd0` `jmp 0x86e000` |
| IN | `0x006a8e1e` | `0x2a8e1e` | .text | `0x006a8e1d` `jmp 0x86e03f` |
| IN | `0x006b5337` | `0x2b5337` | .text | `0x006b5336` `jmp 0x871000` |
| IN | `0x0075477c` | `0x35477c` | .rdata | pointer `0x0086D100` (.kui) |
| OUT | `0x0086d129` | `0x3db129` | .kui | `0x0086d128` `jmp 0x693300` |
| OUT | `0x0086d13b` | `0x3db13b` | .kui | `0x0086d13a` `call 0x694d50` |
| OUT | `0x0086e03b` | `0x3dc03b` | .klb | `0x0086e03a` `jmp 0x6a7cec` |
| OUT | `0x0086e06a` | `0x3dc06a` | .klb | `0x0086e069` `jmp 0x6a8e26` |
| ABS | `0x0086f110` | `0x3dd110` | .kfs | `0x0086f10e` `mov ecx, dword ptr [0x86f008]` |
| ABS | `0x0086f11d` | `0x3dd11d` | .kfs | `0x0086f11a` `cmp eax, dword ptr [edx*4 + 0x86f00c]` |
| ABS | `0x0086f12e` | `0x3dd12e` | .kfs | `0x0086f12b` `mov dword ptr [ecx*4 + 0x86f00c], eax` |
| ABS | `0x0086f135` | `0x3dd135` | .kfs | `0x0086f133` `mov dword ptr [0x86f008], ecx` |
| ABS | `0x0086f13e` | `0x3dd13e` | .kfs | `0x0086f13c` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f14a` | `0x3dd14a` | .kfs | `0x0086f148` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f156` | `0x3dd156` | .kfs | `0x0086f154` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f162` | `0x3dd162` | .kfs | `0x0086f160` `fmul dword ptr [0x86f000]` |
| ABS | `0x0086f16e` | `0x3dd16e` | .kfs | `0x0086f16c` `fmul dword ptr [0x86f000]` |
| OUT | `0x0086f196` | `0x3dd196` | .kfs | `0x0086f195` `jmp 0x4a177d` |
| OUT | `0x0086f1c1` | `0x3dd1c1` | .kfs | `0x0086f1c0` `jmp 0x45a857` |
| ABS | `0x0086f1ce` | `0x3dd1ce` | .kfs | `0x0086f1cc` `fmul dword ptr [0x86f004]` |
| OUT | `0x0086f1de` | `0x3dd1de` | .kfs | `0x0086f1dd` `jmp 0x41799c` |
| OUT | `0x0087000d` | `0x3de00d` | .kwl | `0x0087000c` `jmp 0x45a785` |
| OUT | `0x00871029` | `0x3df029` | .ksc | `0x00871028` `jmp 0x6b5356` |
| OUT | `0x00872020` | `0x3e0020` | .kgs | `0x0087201f` `jmp 0x41b479` |
| OUT | `0x00872046` | `0x3e0046` | .kgs | `0x00872045` `jmp 0x41a301` |
| OUT | `0x00873026` | `0x3e1026` | .ktn | `0x00873025` `jmp 0x415e12` |
| OUT | `0x008740b1` | `0x3e20b1` | .kmz | `0x008740b0` `jmp 0x459944` |
| OUT | `0x00875064` | `0x3e3064` | .kfg | `0x00875063` `call 0x688100` |
| OUT | `0x00875090` | `0x3e3090` | .kfg | `0x0087508f` `call 0x688100` |
| ABS | `0x00876fbc` | `0x3e4fbc` | .kmn | `0x00876fba` `cmp dword ptr [0x876000], 0` |
| ABS | `0x00876fc8` | `0x3e4fc8` | .kmn | `0x00876fc7` `mov edi, 0x876010` |
| OUT | `0x0087704d` | `0x3e504d` | .kmv | `0x0087704c` `jmp 0x405808` |

**18 + 16 + 12 = 46 fields.** The first ad-hoc scan found 16 inbound fields; the
seventeenth, the branch into `.ktn` at `0x00415E0D`, was missed because Capstone's
`disasm()` stops at the first undecodable byte, so a sweep that met data inside
`.text` went silent and two silent sweeps "agreed" on nothing. The byte scan found
it; the sweep now steps over undecodable bytes. That is why neither method is
trusted alone.

## 4. `kmrp-kpm.dat` and the applier

The KPM installer writes `kmrp-kpm.dat` beside the game. Little-endian:

| field | contents |
| --- | --- |
| magic, version | `KMRPKPM2`, 2 (version 1, `KMRPKPM1`, had no patch tags and is refused) |
| block | VA `0x0086D000`, size `0xB000`, 11 page protections (`PAGE_EXECUTE_READWRITE` for `.kfs`, `PAGE_EXECUTE_READ` for the rest, from the sections' characteristics), then the 45,056 final bytes with the map-note flag cleared |
| runs | count, then per run: patch bit, VA, length, the unmodified bytes, the final bytes. Every IN field lies whole inside a run |
| block edits | count, then per edit: patch bit, offset in the block, length, bytes |
| relocations | count, then per field: kind (1 IN, 2 OUT, 3 ABS) and VA |
| checksum | FNV-1a of everything before it |

The patch bits are 1 for KMRP itself, 2 for KMRP Movies and 4 for KMRP Map Notes;
KMRP Controller changes no executable byte. What belongs to the two optional
patches is decided in `BuildData`, and each run belongs to exactly one:

| patch | what | where |
| --- | --- | --- |
| KMRP Movies | the four movie display-mode operands, per resolution | `0x00403D6C`, `0x00403D78`, `0x005F5B3B`, `0x005F5B43`, 4 bytes each (fewer where a resolution's value shares bytes with 640 or 480) |
| KMRP Movies | the jump into the movie aspect fit | the run `0x004057AC`, 7 bytes (`jmp 0x877000` and two `nop`s), found as the run whose IN field leads into `.kmv` |
| KMRP Map Notes | the `.kmn` enable flag | block edit at `0x00876000`, 4 bytes |

`BuildData` refuses to build a file where a movie run would hold anything else --
an operand run reaching past its operand, or an entry run that also leads
somewhere other than `.kmv` -- or where a relocation overlaps the flag. With KMRP
Movies left out, `.kmv` stays in the block, unreached; with Map Notes left out, the
lookup the map wrapper always calls returns at once, as it does in the standalone
with the marker fixes off.

The module's applier (`src/controller-native/K1KpmApplier.cpp`) runs in its
`DllMain`. KPM loads a patch DLL at that patch's first detour hook, inside
`KotorPatcher.dll`'s own start-up and before any game code runs, for the CD and GOG
executables (read in KPM 0.7.1's `patcher.cpp`, `ProcessInjector.cs`). Every copy
of the module:

1. returns at once unless the image is unmodified (base `0x400000`, four sections,
   `SizeOfImage` `0x46D000`) -- so in the standalone edition, whose executable
   already carries all of this, it does nothing;
2. reads which KMRP patches are installed from the `patch_config.toml` KPM wrote
   beside the game: every `id = "…"` line, looking for `kmrp-movies` and
   `kmrp-map-notes`.

The core patch's copy, `patches\kmrp.dll`, then:

3. reads and checks the data file (magic, checksum, layout);
4. checks the unmodified bytes of every run it will write, in memory, **before
   writing anything**;
5. allocates the block, copies it, makes the chosen patches' block edits, applies
   the relocations -- an IN field in a run left out is skipped with its run --
   and sets its page protections;
6. writes the chosen runs, putting back any already written if one fails.

All or nothing: any failure logs the reason to `kmrp-kpm.log` beside the game and
leaves the game unmodified. Success logs a line such as `applied: KMRP + Movies +
Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 01600000 (moved by
+14233600), 46 relocations.` (measured at 1920x1080).

**Frames shared between patches.** The controller's GUI and movie frames hook the
same two sites as the core's stand-ins (`0x0040CE70`, `0x00404D96`), and KPM allows
one patch per address. So the core holds both (`kpm_patch = ""` on the controller's
two), and its stand-ins look once for `kmrp-controller.dll` among the loaded modules:
when KMRP Controller is installed its frame runs **instead of** the stand-in's work,
exactly as it holds the site in the standalone edition; otherwise the stand-in does
its own (mouse confinement and the status summary; movie tracking).

**The movie window's black fill is KMRP Movies'.** Its two window hooks
(`0x0040554B`, `0x00404BB0`) are carried by KMRP Movies itself (`kpm_patch =
"kmrp-movies"`), and every copy of the module asks `KpmMoviesOffK1` before painting
the bars, so without KMRP Movies KMRP leaves the movie window as the game draws it.

Why at `DllMain` rather than in a hook: KPM re-checks each detour's bytes as it
writes it, and a DLL loads at its patch's first detour. The applier's runs and
KMRP's own hook sites are disjoint -- `tools/build_kpatch.py --check` requires every
hook's bytes to be the same in the unmodified executable and in gold -- so the
order does not matter to KMRP's hooks. Another patch hooking a byte KMRP changes
would fail either way, which is the conflict KPM's own byte checks are for.

## 5. The `.kpatch` files

`tools/build_kpatch.py` renders them from the tracked table:

| file | id | hooks | requires | conflicts |
| --- | --- | --- | --- | --- |
| `KMRP.kpatch` | `kmrp` | 2: `CoreGuiFrameK1`, `CoreMovieFrameK1`; its module applies the executable changes | `4gb-patch`, `grass-memory-safety`, `save_mem_leak`, `texture-bucket-safety` | `hud-minimap-map-size-fix-v1`, `scaled-kotor` |
| `KMRP Controller.kpatch` | `kmrp-controller` | 28: the controller set, less the five KPM provides, the two frames the core holds, and the movie window's two | `kmrp` | `expanded-keyboard-control`, `xbox-controls-k1` |
| `KMRP Movies.kpatch` | `kmrp-movies` | 2: `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1`; selects the movie runs | `kmrp` | `better-movie-playback-v1` |
| `KMRP Map Notes.kpatch` | `kmrp-map-notes` | none; selects the `.kmn` flag | `kmrp` | none |

With all four ticked the hooked sites are the standalone's 37 with the controller
on (32 KMRP's, 5 KPM's memory-safety patches'), and the executable is the
standalone's with its marker fixes on.

Why these conflicts: Movie Patch (`better-movie-playback-v1`) also keeps movies in
the game window and fits their aspect; its hook at `0x00405855` is 162 bytes past
the jump into KMRP's `.kmv` fit at `0x004057AC`. Map Texture Patch
(`hud-minimap-map-size-fix-v1`) forces a 512x256 minimap draw size at
`0x0068ABF8`, 163 bytes before KMRP's call into its fog grid at `0x0068AC9F`, which
is the core's; whether both are in one function was not established. Scaled Kotor
is a competing widescreen patch.

`KMRP.kpatch`, `KMRP Controller.kpatch` and `KMRP Movies.kpatch` each hold
`manifest.toml`, `kotor1.hooks.toml` (tagged with the CD 1.03 hash) and
`binaries/windows_x86.dll`, the module. `KMRP Map Notes.kpatch` holds only its
manifest: KPM lists such a patch, installs it, writes it into `patch_config.toml`
as `id = "kmrp-map-notes"` with an empty `dll`, and its runtime skips it -- read in
KPM 0.7.1's `PatchRepository.cs`, `PatchApplicator.cs` (step 5 skips a patch with
no module and no detours) and `config_reader.cpp` ("has no hooks and no DLL -
skipping"). A module with no hooks would instead be loaded as a DLL-only patch,
which `--check` refuses.

**Measured, not guessed.** `tools/check_kpm_overlaps.py` intersects KMRP's
footprint -- every byte the delta changes and every KMRP hook site, 115 spans, 754
bytes -- with every hook of every K1 patch KPM 0.7.1 ships: **no overlap**, and no
hook within 32 bytes, once the memory-safety patches are required. Checked against a
known positive: with KMRP's own memory-safety hooks included it reports all five
overlaps with KPM's. Movie Patch and Map Texture Patch are conflicts by behaviour,
found by widening the search to 1,024 bytes; Semi-Transparent Letterbox, also near
KMRP's letterbox runs, only changes the letterbox's alpha and is compatible. High
FPS Fixes 1.0.0 (a third-party `.kpatch`, not in KPM's set) has no byte of its 36
hooks on any byte KMRP changes; its nearest is 39 bytes from a KMRP run in the
dialogue letterbox routine.

`--check` replays KPM 0.7.1's install-time rules, read from its source: manifest
fields; integer addresses in range; one hook per start address, across all four
patches since a player may tick them all; detour with a function, five or more
stolen bytes, and `eax` excluded when it has a consumed exit; a module exactly when
there are detours; the original bytes against the unmodified executable (KPM's
pre-install check); every function exported by the module; and exactly the four
KMRP patches, so a stale one from an earlier build fails. Planted faults -- an
empty author, a wrong stolen byte, a missing export, a hook on a byte the delta
changes, and (for the four-patch set) two patches on one address, a module in the
marker patch, detours without a module and a leftover `kmrp-no-controller` -- are
each reported.

## 6. The KMRP for KPM installer

The same code as the standalone, compiled with `KPM_EDITION`
(`build_kmrp.ps1` step 6). Its `Inspect`, `Describe`, `CanRestore`, `ApplyInPlace`,
`Restore` and `TryReadInstalledResolution` go to `KpmEditionOperations`. It:

- accepts the unmodified 1.03 executable, with or without the large-address flag,
  and refuses a game the standalone installer patched (restore that first);
- installs Override, `swkotor.ini`'s resolution, DPI and NVIDIA settings with the
  standalone's own code;
- writes `kmrp-kpm.dat`, `kmrp-sdl3.dll` and its licence beside the game -- KPM
  extracts only a patch's module, so the module also looks for SDL in the game
  folder (`K1ControllerBackend.cpp`) -- and `kmrp-controller.ini` if absent;
- records them with hashes in `KMRP_KPM.manifest`; Restore removes only files whose
  hashes still match;
- ignores the standalone's saved marker-fix setting: the data file always carries
  the map notes, as KMRP Map Notes' edit. Its settings page shows no options, and
  says which patches to tick in KPM instead.

It embeds everything the standalone does except KMRP's runtime, the standalone
module and Synchro's standalone K1DC.

## 7. How it was verified

| check | result |
| --- | --- |
| `tools/kpm_relocations.py` | 46 fields, both methods agree, 443 instructions proved after a move; dropping any entry fails |
| `tools/build_kpatch.py --check` | the four patches pass KPM 0.7.1's rules; the earlier planted faults each caught, and four more for the split -- two patches on one address, a module in the marker patch, detours without a module, a leftover `kmrp-no-controller` |
| `tools/check_kpm_overlaps.py` | no overlap with any K1 patch KPM 0.7.1 ships, with the footprint taken from the four patches (still 115 spans, 754 bytes); known positives found |
| `Test-KpmEdition.ps1` (98 checks) | at 1920x1080, 3440x1440, 1024x768, the KPM install made with the standalone's marker setting off: the executable stays byte-for-byte unmodified; **the data file makes exactly the standalone's executable** with all four patches, every byte of every original section and of the eleven sections (`tools/kpm_data.py --equals`); **without Map Notes, exactly the standalone's with its marker fixes off**; without Movies, the same less exactly the movie sites; the Movies runs lie within the four operands and the aspect-fit entry and cover them all (5 runs), and Map Notes is exactly the `.kmn` flag; reinstall at another resolution; restore; a standalone-patched game refused and left alone |
| In game, all four patches | KPM 0.7.1's own launcher, `KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-controller kmrp-movies kmrp-map-notes` and the four required, in a scratch copy at 1920x1080: KPM installed the manifest-only Map Notes and listed it in `patch_config.toml`; `kmrp-kpm.log`: `applied: KMRP + Movies + Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 01600000 (moved by +14233600), 46 relocations.`; **`tools/kpm_data.py --memory`: every run and every block byte exactly** (the only exemption is `.kfs`'s own cache, which the game writes); all 37 hook sites hooked. Main menu with the A prompt; the D-pad moves focus; a movie plays at 1920x1080, fitted, and the pad's A skips it -- the core's two frames handing over to KMRP Controller's |
| In game, KMRP and KMRP Controller | `applied: KMRP -- 86 of 91 runs (564 bytes)`, code at `0x01D90000`: memory exact with the five movie runs **left as the game's own** and the map-note flag clear; 35 sites hooked, the movie window's two untouched; the pad works; the Republic Commando teaser **switches the display to 640x480** as the unmodified game does, and the pad's skip returns to the list at 1920x1080 |
| In game, KMRP, Movies and Map Notes, no controller | 91 of 91 runs, code at `0x010F0000`: memory exact; 9 sites hooked (KMRP's four and KPM's five); no prompts, the D-pad inert; the teaser, started with the mouse, plays at 1920x1080 fitted -- the core's own copy painting |
| The first, two-variant design | earlier the same day: memory exact at `0x01560000` and `0x01110000`, 37 and 9 sites hooked; the main menu, HUD, Map and Inventory matched the standalone's captures at 1920x1080 |
| The standalone, with the new module | `Test-ControllerSupport.ps1` (143), `Test-ReinstallOverOlderBuild.ps1` (12), `Test-MovieResolution.ps1` (36) pass; with the first design's module also `Test-InstalledOverride.ps1` (28), and in game 37 hooks and no `kmrp-kpm.log`: the applier stood aside |

**Not verified:** KPM's graphical launcher (its command line runs the same
`InstallPatches` and `Launch`, read in `Program.cs`); the `binkw32.dll` proxy
deployment; any executable but the CD 1.03 build; any resolution in game but
1920x1080; the map notes on an area map in game (their flag is checked in memory
both ways); KMRP alone without any add-on in game (its bytes are the second row's);
play by hand.

## 8. Limits

- **CD 1.03 only**, the same executable the standalone needs. GOG's `9C10E045…`
  shares KPM's address tables for many patches, but KMRP's 754 bytes have not been
  compared with it; the applier would refuse a mismatch rather than half-apply.
- **Steam's own executable is not supported as built.** KPM knows it as
  `kotor1_steam_103`, `34E6D971…`, SteamStub-wrapped: its code is encrypted on
  disk, so KPM's runtime finds every hook site unreadable at load and hands the
  apply to a worker thread that polls every 15 ms, for up to 30 s, until the stub
  has decrypted the code -- while the game's main thread is already running (read
  in KPM 0.7.1's `patcher.cpp`, `DeferredApply`). KMRP's module would load then,
  late, and some of its changes are read once at start-up; which ones would be
  missed has not been measured. Of the four patches KMRP requires, 4GB Patch and
  Save Game Memory Leak list the Steam executable in 0.7.1 (22 of its 38 K1
  patches do), but Texture Bucket Safety and Grass Memory Safety do not, so KMRP
  as built could not be installed on it. (KPM's `main` after 0.7.1, commit
  `7d53e52`, lists a different Steam hash for 4GB Patch, `C25E2D9C…`; the clone in
  `build/research/Kotor-Patch-Manager` is at that commit, so read release facts
  from the 0.7.1 zip.) Supporting it would take a Steam executable to compare
  against, that timing measured, and KMRP carrying its own copies of those two
  memory-safety hooks there. A Steam install
  given the 1.03 executable (`761F9466…`) is simply the CD case: the maintainer's
  own Steam copy's original, backed up by an earlier KMRP on 2026-09-05, is that
  file.
- **The executable changes are invisible to KPM's conflict checks**, which see
  only hook tables: KMRP names its conflicts itself, from measurement. KPM would
  still refuse a patch whose own bytes KMRP changed (its runtime checks every hook's
  bytes), stopping every hook after it.

## 9. Rejected alternatives

- **Putting the sections back at their own addresses** (no relocation at all).
  Appealing because every byte would be gold's. Killed by the measurement in
  section 2: the range is taken before any patch code runs.
- **Rewriting each section's code as C++ detours.** KPM detours restore every
  register but those listed in `exclude_from_restore`, which in practice is EAX:
  most of KMRP's section code works in registers and the FPU stack mid-function, so
  each would need redesigning, and re-testing, from scratch. Moving the proved
  bytes kept them identical to what the standalone ships.
- **KPM `simple` hooks for the unchanged runs, the module for the rest.** It would
  let KPM's checks see those runs, but a failed applier would leave a half-patched
  game with no way back. All or nothing in the module was chosen instead.
- **A second hook table per resolution.** KPM chooses hook files by executable
  hash, not by resolution; the per-resolution values come from the installer that
  already chooses the Override files.
- **Two variants, KMRP with and without its controller** -- the first design,
  built and tested in game on 2026-09-28 and replaced the same day. A player could
  not leave out the movie fixes (to use Movie Patch instead) or the map notes, and
  each further option would have doubled the files. One patch per fix keeps one
  data file.
- **Each optional patch applying its own bytes.** Rejected: the inbound fields need
  the block's address, which only the core's copy knows, and all or nothing across
  three modules has no single place to roll back from. The core reads which patches
  KPM installed instead.

## 10. Verifying by hand

```powershell
python tools\kpm_relocations.py                       # the table, both methods, the proof
python tools\build_kpatch.py --check "dist\KMRP for KPM"
python tools\check_kpm_overlaps.py <folder of .kpatch files>
.\testing\regression\Test-KpmEdition.ps1               # the editions agree, per resolution
python tools\kpm_data.py <game>\kmrp-kpm.dat --list    # runs per patch, and the edits
# with a game running under KPM, naming the KMRP patches ticked:
python tools\kpm_data.py <game>\kmrp-kpm.dat --memory --features kmrp,kmrp-movies,kmrp-map-notes
```
