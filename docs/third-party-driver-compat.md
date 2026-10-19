# K1 Modern Driver Compatibility: what KMRP bundles, and why it does not collide

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing this
> file, and check the result still meets it — measured claims only, every site tabulated,
> rejected alternatives and corrections kept visible, and anything untested labelled as
> untested.

**Kind: reference.**

KMRP ships **K1 Modern Driver Compatibility (K1DC) 2.0.0** by **Synchro**, MPL-2.0,
with the author's permission (since 2026-10-19, at the maintainer's request; 1.2.0 until
then). This document records what it is, exactly what it
writes, the check that proves it does not collide with anything KMRP writes, and how
a user turns it off.

It is **not** a KMRP fix. Every line of it is Synchro's work. KMRP's only
contribution is installing it, removing it again, and the compatibility check below.

## Reported mod interaction (2026-10-01)

The maintainer reports that issue 15's module-loading crashes with some mods
occur only with **Modern Driver Compatibility enabled**. This on/off result
was reported by the maintainer, not reproduced during the Ubuntu test. Use the
opt-out in section 6 for the affected setup and retest the same module load.
The exact failing operation remains unmeasured; the zero-overlap check below
establishes byte-site compatibility, not compatibility with every content mod.
See the [dated compatibility record](mod-build-compatibility.md#issue-15-driver-component-interaction-reported-2026-10-01).

## The build this describes

| | |
| --- | --- |
| K1DC | 2.0.0 standalone, `k1-modern-driver-compatibility-v2.0.0-standalone.zip`, 1,309,453 bytes, SHA-256 `97E2586E89B26EDB4A8EB260F13BDC2ACD5EAAD5E2AFA25372F33FD560FBDCE3`, released 2026-10-11 |
| its hook list | from the same release's `k1-modern-driver-compatibility-v2.0.0.zip`, 333,926 bytes, SHA-256 `CA088F91684ACD9875BF9E3D36C96A5A580CAED3389F0BADF9A423B78BBFD673` (the `.kpatch` inside, `kotor1.hooks.toml`) |
| vendored at | `third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/` |
| until 2026-10-19 | 1.2.0 standalone, `k1-modern-driver-compatibility-v1.2.0-standalone.zip`, 1,631,672 bytes, SHA-256 `E35E7DA022DC859E10A2C5F29FDE101B846F5789B2A14BB5D297FB57777F24A8`; checked against KMRP gold `swkotor_gold_v24_movieaspect.exe`, `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A` |
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

### 2.0.0 (since 2026-10-19)

Read out of `third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/kotor1.hooks.toml`, which the
author publishes for exactly this purpose: 28 sites, 18 detours and 10 byte patches, the
eight of 1.2.0 among them. What each does is in the author's comments in that file; the
new ones carry the release's bump lighting on every card, the lighting paths the game
never drew (normal maps, bump on lightmapped surfaces, reflective skins), the normal
map byte order, and the glow and soft shadow fixes.

| VA | FILE | size | kind | function | in 1.2.0 |
| --- | --- | --- | --- | --- | --- |
| `0x004367D4` | `0x0367D4` | 5 | detour | `ARB_FragmentPathAvailable` | yes |
| `0x004373BD` | `0x0373BD` | 5 | detour | `ARB_InstallFragmentPath` | yes |
| `0x00428859` | `0x028859` | 5 | detour | `ARB_InstallFrameBufferShaders` | yes |
| `0x0044DF8E` | `0x04DF8E` | 5 | detour | `ARB_InstallSoftShadowShader` | yes |
| `0x00740968` | `0x340968` | 23 | bytes |  | yes |
| `0x0045F7E7` | `0x05F7E7` | 2 | bytes |  | yes |
| `0x0045FA6C` | `0x05FA6C` | 2 | bytes |  | yes |
| `0x00470EB6` | `0x070EB6` | 12 | bytes |  | yes |
| `0x0048AB8F` | `0x08AB8F` | 5 | detour | `ARB_SkinBranch` |  |
| `0x0048AD63` | `0x08AD63` | 5 | detour | `ARB_SkinBranch` |  |
| `0x0048B544` | `0x08B544` | 5 | detour | `ARB_SkinBranch` |  |
| `0x0048C59A` | `0x08C59A` | 5 | detour | `ARB_SkinBranch` |  |
| `0x0043D0F2` | `0x03D0F2` | 5 | detour | `ARB_MaterialHasNormalMap` |  |
| `0x00470D51` | `0x070D51` | 5 | detour | `ARB_MaterialHasNormalMap` |  |
| `0x0048B537` | `0x08B537` | 5 | detour | `ARB_MaterialHasNormalMap` |  |
| `0x00474FCA` | `0x074FCA` | 5 | detour | `ARB_AdoptVertexProgram` |  |
| `0x004755A8` | `0x0755A8` | 5 | detour | `ARB_AdoptVertexProgram` |  |
| `0x0048AE0E` | `0x08AE0E` | 5 | detour | `ARB_AdoptVertexProgram` |  |
| `0x0048B5D4` | `0x08B5D4` | 5 | detour | `ARB_AdoptVertexProgram` |  |
| `0x0048741B` | `0x08741B` | 5 | detour | `ARB_AdoptVertexProgram` |  |
| `0x004260D9` | `0x0260D9` | 6 | detour | `ARB_ReorderNormalMap` |  |
| `0x0042BC21` | `0x02BC21` | 6 | bytes |  |  |
| `0x0042BCB5` | `0x02BCB5` | 6 | bytes |  |  |
| `0x0042BD3F` | `0x02BD3F` | 6 | bytes |  |  |
| `0x0042BDD0` | `0x02BDD0` | 6 | bytes |  |  |
| `0x0042BE3A` | `0x02BE3A` | 6 | bytes |  |  |
| `0x004264A2` | `0x0264A2` | 9 | bytes |  |  |
| `0x00426529` | `0x026529` | 13 | bytes |  |  |

Beyond these sites, 2.0.0 points nine entries of the game's import table at its own
functions at run time, and calls what was there before (`crates/k1-sys/src/interpose.rs`,
`Slot::address`, in the release's source):

| VA | import |
| --- | --- |
| `0x0073D390` | `glEnable` |
| `0x0073D22C` | `glDisable` |
| `0x0073D34C` | `glFogi` |
| `0x0073D2B0` | `wglMakeCurrent` |
| `0x0073D254` | `glFinish` |
| `0x0073D00C` | `SwapBuffers` |
| `0x0073D304` | `glDrawBuffer` |
| `0x0073D020` | `SetDeviceGammaRamp` (the brightness slider) |
| `0x0073D46C` | `BinkCopyToBuffer` (movie frames, for the brightness slider) |

### 1.2.0 (until 2026-10-19)

Four detours and four in-place edits:

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

* `dinput8.dll` (2,407,648 bytes, the same file in 1.2.0 and 2.0.0, SHA-256
  `EC2F4824ECA58DD40F425756A4A7CEC77B8E381F21D11D7C846EC4B339B617AB`): a proxy DLL. Windows loads it from the game
  folder ahead of the system one, so it is in the process at startup; it forwards the
  real `dinput8` calls on and acts as a loader.
* `k1-modern-driver-compatibility.asi` (596,992 bytes in 2.0.0, SHA-256
  `BB58F426D5C3EC5D52C21D99F089F5979E4C30934C246F7C740AB269C932735E`; 1,536,631 bytes in
  1.2.0): the payload that loader loads. An `.asi` is a renamed DLL. 2.0.0 keeps its
  settings in `K1DriverCompat.ini` beside the game under a `[K1DriverCompat]` section
  (a file from an earlier version still works); KMRP's installer writes no such file.

`swkotor.exe` is never written to. KMRP's own install, backup, sidecar and restore
paths are therefore completely untouched by it.

`DriverCompatOperations` in `src/patcher/KmrpPatcher.cs` writes both files from
embedded resources (`Kmrp.drivercompat.dinput8`, `Kmrp.drivercompat.asi`) and records
their names and SHA-256 in **`KMRP\driver-compat.manifest`**: `KMRP` is the folder
beside the executable where KMRP keeps its own files since 2026-10-20 (`KmrpFolder` in
the same file). Until then it was `KMRP_DriverCompat.manifest` beside the executable; the next
install or restore moves an earlier install's into place, and finds it at the old
name until then. The two files themselves stay beside the executable, where the game
loads `dinput8.dll` from.

* **It never clobbers.** If either filename already exists and its hash is not one we
  recorded — someone's own ASI loader, or K1DC installed by hand — both files are left
  alone and the log says so.
* **Restore removes them**, but only where the hash still matches. A file changed
  since install is left in place and reported, so a hand-upgraded K1DC is not deleted.
* Restore runs on every uninstall regardless of the current setting, so turning the
  option off does not strand the files.
* **The loader no longer serves anything else** (since 2026-09-29). `dinput8.dll`
  is Ultimate ASI Loader (ThirteenAG, v9.7.4, unmodified -- K1DC's own
  `THIRD-PARTY-NOTICES` says so) and loads every `.asi` in the folder. Until that
  day KMRP's runtime was an `.asi` it loaded, so with driver compatibility off
  `DriverCompatOperations.Apply` installed the loader alone. KMRP's runtime is now
  KOTOR Patch Manager's, loaded by KPM's `binkw32.dll` proxy
  ([kpm-edition.md](kpm-edition.md), section 1a), so K1DC's two files install
  together, with the option on, or not at all.
* **Not on Windows 7** (since 2026-10-19). Both files import functions Windows 7 lacks,
  read from their import tables; everything else they import is Windows Vista's or 7's:

  | file | imports | from |
  | --- | --- | --- |
  | `dinput8.dll`, Ultimate ASI Loader 9.7.4, linker 14.51 | `CreateFile2`, `GetSystemTimePreciseAsFileTime` | `kernel32.dll`, Windows 8 |
  | `.asi`, Rust (`i686-pc-windows-gnu`) | `WaitOnAddress`, `WakeByAddressAll`, `WakeByAddressSingle` | `api-ms-win-core-synch-l1-2-0.dll`, Windows 8 |
  | `.asi` | `ProcessPrng` | `bcryptprimitives.dll`, Windows 8 |

  Rust's standard library calls the last four (Rust 1.78 made Windows 10 its minimum);
  they are not Synchro's own code. Windows will not load a DLL whose imports it
  cannot find, and the game loads `dinput8.dll` as it starts, so installed on Windows 7
  K1DC keeps the game from starting (the reporter of issue 41 met this with 1.0). Before
  it writes anything, `DriverCompatOperations.Install` asks the PC for all six
  (`MissingImport`: `LoadLibraryEx` from the system folder only, then `GetProcAddress`)
  and leaves K1DC out where one is missing, naming it in the log. Advanced Settings then
  shows the tile off and disabled, "Needs Windows 8" in amber, and keeps the player's
  saved choice. Asked of the PC, not its version number, so Wine and Proton answer for
  themselves. `testing/regression/Test-DriverCompatImports.py` holds the list against the
  vendored files' import tables and fails when the files change, so that a new K1DC's
  imports are read again; `Test-InstallerPatch.ps1` case 9 runs the skip with
  `KMRP_TEST_MISSING_IMPORT` set. Not run on Windows 7.
* **A Windows 7 build of the payload, tried on 2026-10-19 and not shipped.** K1DC's own
  source at the `v2.0.0` tag (`3624ed4`, from Codeberg), unchanged, built with Rust's
  tier-3 Windows 7 target instead of `i686-pc-windows-gnu`. Rust nightly 1.101.0
  (2026-10-18) with `rust-src`, and WinLibs GCC 16.2.0 with MinGW-w64 14.0.0, i686,
  msvcrt (the zip's SHA-256 `805D3E02...8FFA8A`, as published):

  ```
  cargo +nightly build --release --target i686-win7-windows-gnu -p k1-driver-compat \
      --features standalone -Z build-std=std,panic_abort
  ```

  with `CARGO_TARGET_I686_WIN7_WINDOWS_GNU_LINKER` set to WinLibs'
  `i686-w64-mingw32-gcc.exe`. The DLL is 760,320 bytes (SHA-256 `C1FE463B...902498`;
  its build stamp makes each build differ). It has the same 10 exports and imports
  none of the six; in their place, `SystemFunction036` from `advapi32.dll`, SRW locks
  and fiber storage, all of Windows Vista or older. In the test game it logged line
  for line what Synchro's build logs (section 4). The payload has not run on Windows 7.
* **A loader for Windows 7: Ultimate ASI Loader 9.7.0** (found 2026-10-19, not shipped).
  The loader's Windows 8 imports came with its move to Visual Studio 2026 (its commit
  `d94eb18`, 2026-03-31). Read from the 32-bit `Ultimate-ASI-Loader.zip` of 17 releases:

  | releases | linker | Windows 8 imports |
  | --- | --- | --- |
  | 6.9.0 to 9.7.0 (2024-01-20 to 2026-01-16) | 14.37 to 14.44 (Visual Studio 2022) | none |
  | 9.7.1 to 9.7.4 (2026-04-03 to 2026-08-16) | 14.50, 14.51 (Visual Studio 2026) | `CreateFile2`, `GetSystemTimePreciseAsFileTime` |

  9.7.0's `dinput8.dll` (2,376,192 bytes, SHA-256 `AD5D8D449CE305CAF62CB17D8698EBF17E94F9120EE993D0DD85211DFE14F8DD`,
  git `f9f6ccf`) imports what 9.7.4 imports, less those two, plus five functions of Windows
  XP (`TlsAlloc`, `TlsFree`, `TlsGetValue`, `TlsSetValue`,
  `InitializeCriticalSectionAndSpinCount`). The 40 commits between the two:
  - the toolset change;
  - code signing;
  - a `dxgi.dll` proxy;
  - a check for one GTA release;
  - zip overlays;
  - "fix iat restoration" (`776f75c`), which restores the loader's own import-table
    hooks when it unloads at exit and does not touch K1DC's.

  None bears on KOTOR. In the test game, 9.7.0 with the Windows 7 payload above logged
  line for line what Synchro's pair logs. Not run on Windows 7.
* **Windows 7 support will come from Synchro** (2026-10-20). Synchro told the
  maintainer that day that they will publish K1DC with Windows 7 support themselves.
  KMRP's own Windows 7 build of the 2.0.0 payload and the Ultimate ASI Loader 9.7.0
  pairing, the two bullets above, will therefore not be shipped; they stay here as the
  record of what was tried. The installer's Windows 7 gate (*Not on Windows 7*, above)
  stays as it is until Synchro's release, and is then looked at again against the
  files that release ships.
* **On Steam's executable too.** K1DC's README lists the GOG, Steam and CD 1.0.3
  releases. Seen on 2026-09-29 in the maintainer's Steam test install, beside
  KMRP's new install: its log gave `hooks installed=8/8`, and the menus drew.
  Not played further there.

## 4. The compatibility check

This is the check Synchro asked for before shipping, and it is reproducible (§8).

**2.0.0, 2026-10-19.** KMRP no longer writes the executable, so the check is against
what KMRP's modules write in memory: every hook of KMRP's patch (35) and of the
controller patch (38), every run of KMRP's engine recipe (83), and the four places the
modules write besides (the `EnumDisplaySettingsA` import slot `0x0073D3E4`, the start
size at `0x005F0FB2` and `0x005F5B84`, the controller's deadzone at `0x0074D708`), with
D3M0's High FPS Fixes (36 hooks), which the installer can install beside it. **0 of the
28 sites collide, and 0 of the 9 import slots.** All 28 sites hold the original bytes
K1DC declares in the unmodified 1.03 executable. KMRP's movie fixes call through a
different Bink import (`BinkBufferSetScale`, `0x0073D484`) than the one K1DC takes over.
**Run beside KMRP on 2026-10-19** in the test game (`build/party-roster-kpm-check/game`,
3440x1440, KMRP and the controller patch, NVIDIA): three starts of up to 48 s, two with
this build and one with a Windows 7 build of the same source (section 3). Each logged
`hooks installed=28/28`, `install programs=67/67`, every interposed slot `owned`
(`movie_decode` and `set_gamma_ramp` among them) and the shader installs. They set up
again at the renderer rebuild after the startup movies (27.5 s), where both builds log
`gl error site=soft_shadow raised=during errors=INVALID_OPERATION` once. Nothing was
looked at on screen; gameplay and movies under K1DC 2.0.0 have not been watched.

**Rerun on 2026-10-20** against the working tree of that day, with the second script of
section 8: the engine recipe has 84 runs, the new one Bink's buffer type at
`0x00405734` ([`../reverse-engineering/movies.md`](../reverse-engineering/movies.md),
*KMRP asks for the DIB section*). **0 of the 28 sites collide**, and all 28 hold their
declared original bytes. The new byte is an operand of the `push` before
`BinkBufferOpen`, not an import slot, so the 9 slots are as before. What K1DC's
`BinkCopyToBuffer` hook does with frames copied into a DIB section, which GDI then
draws, has not been run.

**1.2.0, 2026-09-24:**

The KMRP installer changes **742 byte positions inside the original image, in 164
contiguous runs**, spanning FILE `0x000916`–`0x35578A` -- the union over the
executables it writes at all 48 resolutions, 721 of them in gold v24. Intersecting
those against K1DC's eight ranges:

**0 of 8 collide.**

Stronger than absence of overlap: each site was compared against the `original_bytes`
K1DC declares, in every one of those 48 executables. **8 of 8 hold his exact expected
bytes**, so his eight-site check does not merely avoid KMRP — it *passes* on a
KMRP-patched executable. Measured 2026-09-24 against the installer's `--apply`
output (`ECA3DE4B…`).

*Corrected 2026-09-24:* this section gave 680 bytes in 136 runs, checked in gold
v20 -- an earlier gold's count, and gold rather than what the installer writes. The
result has not changed.

Since 2026-09-29 the installer writes none of those bytes to the file: KMRP's module
applies the same positions in memory when the game starts, and `--apply` still
writes the executables this check read. The check has not been repeated against the
17 resolutions added on 2026-09-29 or against a running game's memory; K1DC's own
log on a KMRP install (section 3, `hooks installed=8/8`) is the evidence there.

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

**Advanced Settings**, the square gear button beside *Start Patching*, opens a
settings view with six independent tiles since 2026-10-09 (four switches until
2026-10-08, when HD Item Icons was added, and High FPS Fix the day after). The first, *Modern Driver
Compatibility*, is **on by default**, like the next two (map-note corrections
and controller support); the fourth, *Debug Logs*, added 2026-10-04, is off.

Opt-out rather than opt-in because the people who most need it — anyone not on
NVIDIA — are the least likely to know it exists, and the grass fix helps everyone.

The choices are stored in `%LOCALAPPDATA%\KMRP\settings.json` as
`{"driverCompatibility": true|false, "markerFixes": true|false,
"controllerSupport": true|false}`, deliberately beside the user's profile rather
than next to the patcher, so they survive re-downloading a single-file executable.
Since 2026-09-25 the file can also hold `"skippedUpdate": "1.6.0"`: the one
newer version the player told the installer's update prompt not to repeat; and
since 2026-10-04 `"debugLogs": true` while that switch is on.
Every read is defensive: a missing file, an unreadable folder or a malformed value
all fall back to the default. A settings file is never worth failing a patch over.

## 7. What is deliberately not changed

* **K1DC's binaries.** Shipped byte-for-byte as released. We do not rebuild, strip or
  repack them, so a user can hash them against the author's release.
* **`swkotor.exe`.** K1DC does not touch it and neither does KMRP on its behalf.
* **The Patch Manager route.** Synchro's ordinary install goes through KOTOR Patch
  Manager, which did not recognise an executable KMRP had rewritten. That is his
  documented reason for publishing the standalone build, and it is the one we bundle.
  Since 2026-09-29 KMRP does not rewrite the executable and installs on KPM's
  runtime itself, so both routes work: users who prefer the manager turn our option
  off and tick Synchro's own `.kpatch` in KPM (`INSTALLING.md` in his release), and
  in a game folder KPM already manages, KMRP's installer leaves K1DC to KPM
  (`KpmEdition.cs`). K1DC's `.kpatch` beside KMRP's two patches in KPM has not been
  run here. Since 2.0.0 that `.kpatch` needs KOTOR Patch Manager 0.7.2 or newer, "for
  the way this release hooks the game" (the release notes); the standalone build KMRP
  bundles needs nothing but the game.
* **His hook addresses.** We read `kotor1.hooks.toml`; we never write to those sites.
* **Where Synchro's files live.** Since 2026-10-20 KMRP keeps its own files in a `KMRP`
  folder in the game folder; only its record of K1DC, `driver-compat.manifest`, moved
  there. `dinput8.dll` and the `.asi` stay beside `swkotor.exe`, where the game loads
  them, and K1DC's own `K1DriverCompat.ini` and `logs\` folder are Synchro's and
  untouched.

## 8. Verifying by hand

Reproduce the collision check against any KMRP gold build. Gold alone misses the
21 bytes the installer writes over values gold leaves vanilla; for the full check,
run it against the installer's `--apply` outputs as well (see
[`../reverse-engineering/binary-inventory.md`](../reverse-engineering/binary-inventory.md) §2):

```bash
python - <<'PY'
import re, ast
gold = open("build/kmrp/swkotor_gold_v24_movieaspect.exe", "rb").read()
clean = open("build-inputs/swkotornopatch.exe", "rb").read()
changed = {i for i in range(len(clean)) if clean[i] != gold[i]}
toml = open("third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/kotor1.hooks.toml").read()   # 1.2.0, from git
for block in toml.split("[[hooks]]")[1:]:
    va = int(re.search(r"address\s*=\s*(0x[0-9A-Fa-f]+)", block).group(1), 16)
    orig = bytes(ast.literal_eval(
        re.search(r"original_bytes\s*=\s*(\[[^]]*\])", block, re.S).group(1).replace("\n", "")))
    f = va - 0x400000
    hit = changed & set(range(f, f + len(orig)))
    print(f"0x{va:08X} len {len(orig):2}  collides={bool(hit):5}  bytes_intact={gold[f:f+len(orig)] == orig}")
PY
```

Expected: `collides=False` and `bytes_intact=True` on all eight lines. (That was
1.2.0's check, against gold. For 2.0.0, against what KMRP writes in memory:)

```python
import sys, tomllib
sys.path.insert(0, "tools")
import build_bundled_kpatch_config as bundled
spans = bundled.spans_of_kmrp()   # KMRP's patch, the controller patch, the engine recipe
spans += [(0x0073D3E4, 4, "import slot"), (0x005F0FB2, 12, "start size"), (0x005F5B84, 10, "start size"),
          (0x0074D708, 4, "deadzone")]
clean = open("build-inputs/swkotornopatch.exe", "rb").read()
hooks = tomllib.load(open("third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/kotor1.hooks.toml", "rb"))["hooks"]
for h in hooks:
    a, n = h["address"], len(h["original_bytes"])
    hit = [o for b, m, o in spans if a < b + m and b < a + n]
    print(f"0x{a:08X} len {n:2}  collides={bool(hit)}  bytes_intact={clean[a - 0x400000:a - 0x400000 + n] == bytes(h['original_bytes'])}")
```

Expected on 2026-10-19: 28 lines, `collides=False` and `bytes_intact=True` on each.

Confirm the shipped binaries match the author's release:

```bash
sha256sum "third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/dinput8.dll"
sha256sum "third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/k1-modern-driver-compatibility.asi"
```

Confirm an install did what it claims — the manifest lists both files and their
hashes, and the executable is untouched by K1DC. Since 2026-09-29 its hash is the
incoming file's on Steam, and the incoming file's with the 4 GB flag set on GOG's
and the editable build (`CA9D22EA…` for the editable one). (This comment said
"still the gold hash" until 2026-09-24, and then, until 2026-10-08, that the
patcher writes per-resolution values on top of gold, which it stopped doing on
2026-09-29.)

```powershell
Get-Content "C:\Star Wars - KotOR\KMRP\driver-compat.manifest"   # KMRP_DriverCompat.manifest until 2026-10-20
Get-FileHash "C:\Star Wars - KotOR\swkotor.exe"   # unchanged by K1DC: still what KMRP left
```

## 9. Licence and credit

K1DC is **MPL-2.0**. The licence text ships inside the patcher
(`Kmrp.license.drivercompat`) and is vendored at
`third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro/LICENSE`, alongside the
author's `README.md`, `THIRD-PARTY-NOTICES` and `INSTALLING-STANDALONE.md`.

**K1 Modern Driver Compatibility is by Synchro.** Bundled with permission. No KMRP
code is derived from it, and none of its code is modified.

Separately, and unrelated to the bundling: Synchro's published research on the area
map — `hires_patch.py` and `TECHNICAL.txt` in *K1 Area Map Fixes* — identified the two
area-map tile-size operands and the 440:512 atlas relationship that KMRP's own map
work is built on. That is acknowledged in
[`../reverse-engineering/area-map-surface.md`](../reverse-engineering/area-map-surface.md);
no code or data from that mod is included either.
