# The KPM edition: KMRP through KOTOR Patch Manager

**Reference.** What the KPM edition does, byte for byte, and how it is proved to
make the same game as the standalone installer, for the editable 1.03 executable
and Steam's. Built and measured on 2026-09-28 and, for the final build on Steam,
2026-09-29; the lab record of how it was designed is in the session notes
summarised under *Rejected alternatives* below.

## The build this describes

| | |
| --- | --- |
| Unmodified executable | the editable KOTOR 1.03 `swkotor.exe`, `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`, 4,042,752 bytes (`build-inputs/swkotornopatch.exe`). Called **CD 1.03** in this document and in the KPM edition's code, after KPM's own key for it, `kotor1_cdcrack_103` -- KPM's version table names it "HellSpawn CD Crack version 1.0.3", GOG's v1.03 with a 16-byte watermark ([map-scaling.md](../reverse-engineering/map-scaling.md)). It is not the retail CD's executable, which KMRP has not measured, nor GOG's own (`9C10E045…`), which KMRP refuses by hash |
| Steam's executable | `34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`, 4,395,008 bytes, KPM's `kotor1_steam_103`; a clean Steam install lent by the maintainer on 2026-09-28 (`build-inputs/swkotor-steam.exe`, optional) |
| Gold | `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`, 4,087,808 bytes (`build/kmrp/swkotor_gold_v24_movieaspect.exe`) |
| KOTOR Patch Manager | 0.7.1 (release zip `0EFEFAC8…`, source zip `Kotor-Patch-Manager-0.7.1.zip`), read and run on 2026-09-28; 0.7.1 (2026-09-21) was still KPM's newest release on 2026-09-29. The clone in `build/research/Kotor-Patch-Manager` is at an **older** development commit, `7d53e52` of 2026-09-05 -- before 0.7.0 (09-07) and 0.7.1 -- and differs. (*Corrected 2026-09-29:* this called it a later commit) |
| Module | `kmrp-controller.module`, 245,248 bytes, `4B1131DABC4550D5F4F18B2C52EE93291E8350C2B35FA2A5215660A0F4C13AD3` |
| Installers | standalone `603DC45D…`, KMRP for KPM `1533474E…`; `KMRP.kpatch` `C27E108A…`, `KMRP Controller.kpatch` `56C45ED3…`, `KMRP Movies.kpatch` `014743BB…`, `KMRP Map Notes.kpatch` `D7977A3A…` |

The edition changed twice on 2026-09-28. It first shipped as two `.kpatch` files,
KMRP with and without its controller; then as four patches, one per fix, with
KMRP requiring KPM's 4GB and three memory-safety patches; and finally, to support
Steam's executable, with KMRP carrying those fixes itself (section 5).

Addresses are **VA** unless marked FILE. For the original sections `FILE = VA −
0x400000`; for gold's eleven appended sections `FILE = VA − 0x492000`
([`binary-inventory.md`](../reverse-engineering/binary-inventory.md)).

## 1. Two editions, one source

KMRP ships two ways, built by one `build_kmrp.ps1` run from the same sources:

| | standalone | KPM edition |
| --- | --- | --- |
| Output | `dist\KMRP - KOTOR Modern Restoration Patch.exe` | `dist\KMRP for KPM\`: `KMRP for KPM.exe`, `KMRP.kpatch`, `KMRP Controller.kpatch`, `KMRP Movies.kpatch`, `KMRP Map Notes.kpatch`, README, KPM's MIT licence |
| Executables | CD 1.03 | CD 1.03 and **Steam's** |
| swkotor.exe | the gold delta written in, per resolution | **never modified** by KMRP. On CD 1.03 KPM sets the large-address flag from KMRP's own static hook; Steam's is left alone, since Steam refuses a changed file |
| Executable changes | in the file | applied in memory by KMRP's module, from `kmrp-kpm.dat` |
| Run-time hooks | KMRP's own copy of the KPM runtime, `patch_config.toml` written by the installer | KPM's runtime, from the `.kpatch` hook table |
| Memory-safety fixes | KMRP's copies of KPM's three patches | the same copies, in the KMRP patch, which conflicts with KPM's own |
| Driver compatibility | Synchro's standalone K1DC, optional | not installed; Synchro's own `.kpatch` in KPM |
| Controller, movies, map notes | the controller and map-note options are checkboxes; the movie fixes are always in | three optional patches, ticked in KPM beside the required `KMRP` |
| Override, `swkotor.ini`, DPI, NVIDIA | installed | installed, by the same code |

What is shared, so the editions cannot drift apart:

- **The executable's bytes.** The KPM installer builds the final image as the
  standalone does -- the embedded gold delta, `ResolutionPatch` for the resolution,
  the map-note flag on -- over the unmodified executable's bytes it carries
  (section 6), and records only how it differs from the unmodified executable, each
  change tagged with the patch it belongs to (`KpmEditionOperations.BuildData`,
  `src/patcher/KpmEdition.cs`). No per-resolution rule exists in two places, and
  `Test-KpmEdition.ps1` proves the result is the standalone's executable.
- **The hook sets.** Both come from `src/controller-native/kotor1.hooks.toml`
  through `tools/kmrp_controller.py`: `installed_set(controller)` for the
  standalone, `kpm_patch_hooks(id)` for each KPM patch, from the hook's
  `kpm_patch` key. The five hooks tagged `kpm_provided_by` are in both; the KPM
  edition's KMRP patch conflicts with the KPM patches that make them.
- **The module.** One binary: the standalone loads it from its own runtime, KPM
  from `patches\<id>.dll`, once for each KMRP patch that has hooks. Its applier
  runs only in an unmodified image, and only in the core patch's copy (below).

## 2. What the module applies, and why the code has to move

Gold's delta has three parts; the KPM edition reproduces all three in memory:

| part | size | in the KPM edition |
| --- | --- | --- |
| Runs in the original image | 81 runs in `.text` (560 bytes) and 2 in `.rdata` (5 bytes) at the byte level; 89 to 91 runs of 576 to 582 bytes once the per-resolution values and the relocated fields are added (measured at 1024x768, 1920x1080, 3440x1440) | written by the module after every original byte is checked |
| Eleven appended sections, `.kui` ... `.kmv`, `0x0086D000`-`0x00877FFF` | 45,056 bytes, 5,726 used | copied as one block into memory the module allocates, and relocated |
| PE header | 71 byte-runs, 156 bytes | not written by the module. Only the large-address flag matters at run time: on CD 1.03 KPM writes it into the file from the KMRP patch's static hook; Steam's executable cannot take it |

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

1. returns at once unless the image is unmodified -- CD 1.03's (base `0x400000`,
   four sections, `SizeOfImage` `0x46D000`) or Steam's (five sections, the fifth
   `.bind`, `SizeOfImage` `0x4C3000`) -- so in the standalone edition, whose
   executable already carries all of this, it does nothing;
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
6. pauses every other thread of the game, retrying while any is stopped inside a
   run, writes the chosen runs, putting back any already written if one fails, and
   lets the threads go.

All or nothing: any failure logs the reason to `kmrp-kpm.log` beside the game and
leaves the game unmodified. Success logs two lines such as `applied: KMRP + Movies
+ Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 02CD0000 (moved by
+38154240), 46 relocations.` and `Steam executable; 457 ms after the game started,
after its window; 8 other thread(s) paused while writing.` (measured on Steam at
1920x1080).

**On Steam the game is already running.** Steam's executable is CD 1.03's program
behind SteamStub: its code is encrypted on disk, and once the stub has decrypted it
in memory it is CD 1.03's byte for byte -- all 3,387,856 bytes of `.text`, every
one of KMRP's 115 spans and the five memory-safety sites (read from a running game
on 2026-09-28). The only other differences are the stub's `.bind` section and the
letter case of eight DLL names in `.rdata`'s import table. But KPM can only patch it
after decryption: its runtime finds every hook site unreadable at load and hands the
apply to a worker thread that polls every 15 ms (`patcher.cpp`, `DeferredApply`,
the same in 0.7.1's source). Measured from outside, the code reads decrypted about
332 ms after the process starts and the game's window exists 20 ms later; KMRP
applied at 457 ms in the trial and at 501 ms with the final build (whose window,
that time, came later still). That is before any screen KMRP changes is built -- the main menu,
character generation, Options and movies all matched CD 1.03's captures (section 7)
-- and the pause in step 6 keeps the game's own threads out of the bytes being
written.

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
| `KMRP.kpatch` | `kmrp` | 7: `CoreGuiFrameK1`, `CoreMovieFrameK1` and the five memory-safety hooks; its module applies the executable changes. On CD 1.03 also the large-address flag, a static hook | none | `hud-minimap-map-size-fix-v1`, `scaled-kotor`, and the four KPM patches whose fixes it makes: `4gb-patch`, `grass-memory-safety`, `save_mem_leak`, `texture-bucket-safety` |
| `KMRP Controller.kpatch` | `kmrp-controller` | 28: the controller set, less the two frames the core holds, the movie window's two and the memory-safety five | `kmrp` | `expanded-keyboard-control`, `xbox-controls-k1` |
| `KMRP Movies.kpatch` | `kmrp-movies` | 2: `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1`; selects the movie runs | `kmrp` | `better-movie-playback-v1` |
| `KMRP Map Notes.kpatch` | `kmrp-map-notes` | none; selects the `.kmn` flag | `kmrp` | none |

Every patch supports CD 1.03 (`kotor1_cdcrack_103`) and Steam's executable
(`kotor1_steam_103`). With all four ticked the hooked sites are the standalone's 37
with the controller on, and the executable is the standalone's with its marker
fixes on -- on CD 1.03 including the large-address flag.

**Why KMRP carries the memory fixes itself.** KPM 0.7.1 has one `requires` list per
patch, checked the same on every game version (`ManifestParser.cs`,
`DependencyValidator.cs`), and Texture Bucket Safety and Grass Memory Safety list no
Steam executable. KPM's 4GB Patch lists Steam's but writes the CD/GOG header offset
(`0x00400926`; Steam's `e_lfanew` is `0x110`, its flag at `0x00400126`), so KPM
refuses it -- and Steam refuses any changed executable anyway ("Application load
error 3:0000065432", seen 2026-09-28 with the flag written at the right offset). So
a KMRP that required them could not be installed on Steam. No KPM 0.7.1 patch
requires any of the four, so conflicting with them costs a player nothing: KMRP
does their job. The large-address flag is a static hook in a separate hooks file,
`kotor1-cd-large-address.hooks.toml`, targeting CD 1.03 alone and derived by
`build_kpatch.py` from the unmodified header (`Characteristics` OR `0x0020`, the
standalone's own one-bit change).

Why the other conflicts: Movie Patch (`better-movie-playback-v1`) also keeps movies in
the game window and fits their aspect; its hook at `0x00405855` is 162 bytes past
the jump into KMRP's `.kmv` fit at `0x004057AC`. Map Texture Patch
(`hud-minimap-map-size-fix-v1`) forces a 512x256 minimap draw size at
`0x0068ABF8`, 163 bytes before KMRP's call into its fog grid at `0x0068AC9F`, which
is the core's; whether both are in one function was not established. Scaled Kotor
is a competing widescreen patch.

`KMRP.kpatch`, `KMRP Controller.kpatch` and `KMRP Movies.kpatch` each hold
`manifest.toml`, `kotor1.hooks.toml` (tagged with the CD 1.03 and Steam hashes) and
`binaries/windows_x86.dll`, the module; `KMRP.kpatch` also the CD-only
large-address hooks file. `KMRP Map Notes.kpatch` holds only its
manifest: KPM lists such a patch, installs it, writes it into `patch_config.toml`
as `id = "kmrp-map-notes"` with an empty `dll`, and its runtime skips it -- read in
KPM 0.7.1's `PatchRepository.cs`, `PatchApplicator.cs` (step 5 skips a patch with
no module and no detours) and `config_reader.cpp` ("has no hooks and no DLL -
skipping"). A module with no hooks would instead be loaded as a DLL-only patch,
which `--check` refuses.

**Measured, not guessed.** `tools/check_kpm_overlaps.py` intersects KMRP's
footprint -- every byte the delta changes, every KMRP hook site and the
large-address flag, 121 spans, 795 bytes -- with every hook of every K1 patch KPM
0.7.1 ships: exactly the four declared overlaps (4GB Patch at the flag; Grass
Memory Safety, Save Game Memory Leak and Texture Bucket Safety at the five
memory-safety sites), **no undeclared overlap**, and no hook within 32 bytes. It
fails on an overlap no KMRP patch declares; checked by dropping `4gb-patch` from the
conflicts. Movie Patch and Map Texture Patch are conflicts by behaviour,
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
pre-install check); every function exported by the module; exactly the four KMRP
patches, so a stale one from an earlier build fails; both executables supported,
and every hooks file targeting only supported ones; and a static hook only in the
header, with the header's own bytes, targeting CD 1.03 alone. Planted faults -- an
empty author, a wrong stolen byte, a missing export, a hook on a byte the delta
changes, two patches on one address, a module in the marker patch, detours without
a module, a leftover `kmrp-no-controller`, the static hook aimed at Steam, a wrong
header byte, and Steam dropped from a manifest -- are each reported.

## 6. The KMRP for KPM installer

The same code as the standalone, compiled with `KPM_EDITION`
(`build_kmrp.ps1` step 6). Its `Inspect`, `Describe`, `CanRestore`, `ApplyInPlace`,
`Restore` and `TryReadInstalledResolution` go to `KpmEditionOperations`. It:

- accepts the unmodified 1.03 executable, with or without the large-address flag,
  and Steam's (`KpmEditionOperations.IsSteam`), and refuses a game the standalone
  installer patched (restore that first). The standalone refuses Steam's executable
  with its own message: Steam will not start it patched, use KMRP for KPM;
- builds the data file from the **unmodified executable's bytes it carries**, not
  from the player's file, since Steam's is encrypted on disk: `Kmrp.kpm.originals`
  (`tools/kpm_originals.py`, 91 ranges, 4,777 bytes, 681 of them past the header)
  holds CD 1.03's header, its bytes under every gold-delta chunk, every inbound
  relocation field whole and every field `ResolutionPatch` handles whole, and zero
  stands for everything else (`OriginalsImage`, `GoldPatch.ApplyToOriginals`). The
  resolution fields come from the installer itself: the build runs the standalone
  it just compiled with `--kpm-sites`, which applies all 49 resolutions while
  `ResolutionPatch` records every field it reads or writes (52), so the list cannot
  drift from the code. The first version carried only the chunks and relocated
  fields, and the installer refused its own picture -- "The stack-count label patch
  did not match the verified gold build" -- because gold changed only some bytes of
  some fields and none of a few (the powers row height stays vanilla's 40). The tool
  proves the coverage before the build embeds it, and a data file built this way at
  1920x1080 is byte for byte the one the earlier, file-reading installer wrote
  (`28DAA6A9…`);
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
| `tools/build_kpatch.py --check` | the four patches pass KPM 0.7.1's rules; eleven planted faults each caught (section 5) |
| `tools/check_kpm_overlaps.py` | 121 spans, 795 bytes: exactly the four declared overlaps with KPM's 4GB and memory-safety patches, no undeclared one; dropping a declared conflict fails |
| `tools/kpm_originals.py` | run by every build: the carried bytes cover every changed byte, every relocated field and all 52 resolution fields; a dropped range fails. The data file built from them at 1920x1080 is byte for byte the file-reading installer's (`28DAA6A9…`) |
| `Test-KpmEdition.ps1` (107 checks, final build `603DC45D…`) | at 1920x1080, 3440x1440, 1024x768, the KPM install made with the standalone's marker setting off: the executable stays byte-for-byte unmodified; **the data file makes exactly the standalone's executable** with all four patches, every byte of every original section and of the eleven sections (`tools/kpm_data.py --equals`); **without Map Notes, exactly the standalone's with its marker fixes off**; without Movies, the same less exactly the movie sites; the Movies runs lie within the four operands and the aspect-fit entry and cover them all (5 runs), and Map Notes is exactly the `.kmn` flag; reinstall at another resolution; restore; a standalone-patched game refused and left alone. **Steam's executable**: installed over and left unmodified, the data file byte for byte the editable executable's at the same resolution, restored; the standalone refuses it |
| In game, final build, the editable executable | `KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-controller kmrp-movies kmrp-map-notes` -- no KPM patch ticked -- in a scratch copy at 1920x1080: 91 of 91 runs, KMRP's code at `0x00F40000`, memory exact, **all 37 sites hooked** (the five memory-safety sites by KMRP's own copies), and **the large-address flag set by KMRP's static hook**: the file became `CA9D22EA…` (CD 1.03 with only that bit) and the running game's header reads `0x012F`. The applier logged 293 ms after start, before the window, 3 other threads paused. Main menu with the A prompt |
| In game, Steam's executable, trial build | a clean Steam install lent by the maintainer, 1920x1080, KPM's proxy deployment, the game started by Steam: 91 of 91 runs at `0x02CD0000`, memory exact, 37 sites hooked; applied 457 ms after start, after the window, 8 other threads paused. Main menu, character creation (class selection, Quick or Custom), Options and a movie compared with the editable executable's captures: Options pixel-identical, the rest differing only in the randomly chosen character models and animation frames; the movie played at 1920x1080 with no mode switch. The trial had the final module (`4B1131DA…`) and the same data file (`28DAA6A9…`); only its KMRP patch differed, requiring KPM's Save Game Memory Leak instead of carrying that hook |
| In game, Steam's executable, final build | 2026-09-29, the same install: the final installer installed over it (executable untouched, data file `28DAA6A9…`, 1,846 Override files), KPM applied the four KMRP patches through its proxy, and Steam started the game: `applied: KMRP + Movies + Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 001D0000 (moved by -6934528)` -- the first run with the block placed *below* the image, and **`tools/kpm_data.py --memory` exact** there too -- 501 ms after start, before the window, 6 other threads paused; all 37 sites hooked. The same screen sequence as the trial, driven by the virtual pad: Options pixel-identical to the editable executable's capture, the others differing only in the random character models (checked by eye on the largest, Quick or Custom, 2.2%), the movie at 1920x1080 with no mode switch. A first attempt the evening before was not started: Steam reported the account already playing KOTOR on another computer (the maintainer's macOS session). After each run the install was restored and checked against its backups |
| Steam's executable, measured | decrypted in memory, `.text` byte for byte the editable executable's, all 115 KMRP spans and the five memory-safety sites identical; `.rdata` differs only in the import table and in the letter case of eight DLL names. Writing the large-address flag into the file at its own offset made Steam refuse to start it ("Application load error 3:0000065432") |
| In game, the four-patch build before it was self-contained (`125DEA64…`), all four patches | KPM 0.7.1's own launcher, `KPatchLauncher.exe <exe> --patches <dir> kmrp kmrp-controller kmrp-movies kmrp-map-notes` and the four required, in a scratch copy at 1920x1080: KPM installed the manifest-only Map Notes and listed it in `patch_config.toml`; `kmrp-kpm.log`: `applied: KMRP + Movies + Map Notes -- 91 of 91 runs (577 bytes) and KMRP's code at 01600000 (moved by +14233600), 46 relocations.`; **`tools/kpm_data.py --memory`: every run and every block byte exactly** (the only exemption is `.kfs`'s own cache, which the game writes); all 37 hook sites hooked. Main menu with the A prompt; the D-pad moves focus; a movie plays at 1920x1080, fitted, and the pad's A skips it -- the core's two frames handing over to KMRP Controller's |
| In game, `125DEA64…`, KMRP and KMRP Controller | `applied: KMRP -- 86 of 91 runs (564 bytes)`, code at `0x01D90000`: memory exact with the five movie runs **left as the game's own** and the map-note flag clear; 35 sites hooked, the movie window's two untouched; the pad works; the Republic Commando teaser **switches the display to 640x480** as the unmodified game does, and the pad's skip returns to the list at 1920x1080 |
| In game, `125DEA64…`, KMRP, Movies and Map Notes, no controller | 91 of 91 runs, code at `0x010F0000`: memory exact; 9 sites hooked (KMRP's four and KPM's five); no prompts, the D-pad inert; the teaser, started with the mouse, plays at 1920x1080 fitted -- the core's own copy painting |
| The first, two-variant design | earlier the same day: memory exact at `0x01560000` and `0x01110000`, 37 and 9 sites hooked; the main menu, HUD, Map and Inventory matched the standalone's captures at 1920x1080 |
| The standalone, final build `603DC45D…` | `Test-ControllerSupport.ps1` (143), `Test-ReinstallOverOlderBuild.ps1` (12), `Test-MovieResolution.ps1` (36), `Test-LargeAddressAware.ps1` (15), `Test-InstalledOverride.ps1` (28) pass; with the first design's module, in game, 37 hooks and no `kmrp-kpm.log`: the applier stood aside |

**Not verified:** KPM's graphical launcher (its command line runs the same
`InstallPatches` and `Launch`, read in `Program.cs`); gameplay on Steam's
executable (only menus and character creation were opened); GOG's own
executable; any resolution in game but 1920x1080; the map notes on an area map in
game (their flag is checked in memory both ways); KMRP alone without any add-on in
game (its bytes are the `125DEA64…` KMRP-and-Controller row's); play by hand.

## 8. Limits

- **CD 1.03 and Steam only.** GOG's `9C10E045…` shares KPM's address tables for
  many patches, but KMRP's 754 bytes have not been compared with it; the applier
  would refuse a mismatch rather than half-apply.
- **Steam needs KPM's proxy deployment.** Steam's executable hands its own start
  to Steam and exits after about half a second, so a patcher KPM injects into the
  process it started never reaches the game Steam starts. KPM 0.7.1 on Windows
  injects unless the player switches to the proxy (`DeploymentPolicy.cs`); the
  README and the installer say so.
- **No large-address flag on Steam.** SteamStub refuses to start an executable
  changed on disk -- "Application load error 3:0000065432", seen 2026-09-28 with
  only the flag set, at the right offset -- and the flag must be in the file when
  the process is created. KMRP has not been seen to need more than 2 GB
  ([large-address-aware.md](../reverse-engineering/large-address-aware.md) calls
  the flag a margin and memory-heavy play an empirical question); on Steam that
  margin is absent.
- **On Steam, KMRP applies after the game has started** (section 4). Every screen
  checked was built after it applied; a change the game reads in its first ~450 ms
  would be missed, and none has been found. Gameplay on Steam has not been played:
  the test install's Steam Cloud save was left alone.
- **No 4 GB patcher can work on Steam's executable, KPM's or KMRP's.** The flag
  is read by Windows from the file's header when the process is created and fixes
  the address space then; nothing running inside the game can set it later. So it
  has to be written into the file, and SteamStub refuses to start a changed file
  (measured, above). KPM's own 4GB Patch lists Steam's executable anyway: in 0.7.1,
  and in KPM's `master` as fetched on 2026-09-29, its K1 hooks file targets
  `34E6D971…` with the editable executable's offset, `0x00400926`, where Steam's
  file holds `00 00` ("Byte mismatch", measured), so KPM refuses it; at the right
  offset the DRM would refuse the file instead. (The older development commit
  `7d53e52` in `build/research/Kotor-Patch-Manager` briefly listed a different
  Steam hash, `C25E2D9C…`, that nothing else in KPM knows; read release facts from
  the 0.7.1 zip.) Stripping SteamStub first, as Steamless does, would make it
  possible, and is kept out of KMRP (section 9). Not reported upstream.
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
- **Requiring KPM's memory and 4GB patches** -- the four-patch design's first
  version. Rejected once Steam was supported: two of them list no Steam executable,
  the 4GB Patch cannot work on it, and KPM's `requires` cannot differ by game
  version. A requirement list per executable was the maintainer's suggestion; KPM
  0.7.1 has no such thing.
- **A separate "KMRP (Steam)" patch.** It would have kept the requirements on CD
  1.03, but doubled the core patch and made players pick by executable. Carrying the
  fixes needs neither.
- **Reading the unmodified bytes from the player's file.** What the installer did
  until Steam support; Steam's file is encrypted, so the installer carries them.
- **Stripping SteamStub** (what Steamless does) so the standalone could patch Steam's
  executable. That is circumventing DRM, and kept out of KMRP.

## 10. Verifying by hand

```powershell
python tools\kpm_relocations.py                       # the table, both methods, the proof
python tools\kpm_originals.py --clean build-inputs\swkotornopatch.exe --delta build\kmrp\gold.kup `
    --relocations build\kmrp\kpm-relocations.txt --sites build\kmrp\kpm-resolution-sites.txt `
    --out build\kmrp\kpm-originals.bin                 # the carried bytes, and their proof
python tools\build_kpatch.py --check "dist\KMRP for KPM"
python tools\check_kpm_overlaps.py <folder of .kpatch files>
.\testing\regression\Test-KpmEdition.ps1               # the editions agree, per resolution
python tools\kpm_data.py <game>\kmrp-kpm.dat --list    # runs per patch, and the edits
# with a game running under KPM, naming the KMRP patches ticked:
python tools\kpm_data.py <game>\kmrp-kpm.dat --memory --features kmrp,kmrp-movies,kmrp-map-notes
```
