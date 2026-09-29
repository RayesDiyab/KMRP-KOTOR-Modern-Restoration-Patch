# KOTOR Patch Manager's runtime, built for KMRP's installer

A reference: what this directory builds and why. The installer that uses it is
described in [`docs/kpm-edition.md`](../../docs/kpm-edition.md).
Documentation standard: [`docs/documentation-standard.md`](../../docs/documentation-standard.md).

KMRP's Windows installer installs KOTOR Patch Manager's runtime itself, laid out
the way KOTOR Patch Manager's own proxy deployment lays out a game folder
(`KPatchCore/Applicators/KProxyInstaller.cs` and `PatchApplicator.cs` in the
submodule): the game loads `binkw32.dll`, which is KPM's proxy; the proxy loads
`KotorPatcher.dll`; `KotorPatcher.dll` reads `patch_config.toml` and loads the
patch modules under `patches\`. The game's own `binkw32.dll` is renamed
`binkw32Hooked.dll`, and the proxy forwards every Bink call to it. `swkotor.exe`
is not rewritten, which is what lets the installer serve Steam's executable,
whose DRM refuses a changed file.

`build.cmd` builds both DLLs from the submodule at `third_party/Kotor-Patch-Manager`
(`git submodule update --init`) into `build\kpm-runtime\`, and `build_kmrp.ps1`
runs it and embeds the results:

| Output | Sources | Resource in the installer |
| --- | --- | --- |
| `KotorPatcher.dll` | `src/KotorPatcher/src/core/{config_reader,patcher,trampoline,wrapper_x86}.cpp`, `src/KotorPatcher/src/{platform_win32,dllmain}.cpp` | `Kmrp.engine.runtime` |
| `binkw32.dll` | `src/KProxy/kproxy.cpp` with `src/KProxy/bink_forwards.def` | `Kmrp.engine.proxy` |

## Why not KPM's own build

KPM's `publish.bat` builds `KotorPatcher.dll` from its `.vcxproj`, which links
the C runtime dynamically (`/MD`). Measured 2026-09-29 on that build: it imports
`MSVCP140.dll`, `VCRUNTIME140.dll` and eight `api-ms-win-crt-*` DLLs, so it would
not load on a PC without the Visual C++ redistributable. `build.cmd` compiles the
same six sources with `/MT`; the result imports `KERNEL32.dll` only, as
`kmrp-controller.module` does. The `.vcxproj` also links `sqlite3.lib`, which
nothing in those sources calls (the `/MD` build does not import `sqlite3.dll`
either), so it is left out, and no `sqlite3.dll` is installed. KPM builds its
proxy with MinGW only; `build.cmd` builds it with MSVC, `/MT`, and the same
`.def` file.

## The build, measured

Built 2026-09-29 from submodule commit `17fd051` with MSVC `cl` 19.39.33523 for
x86 (Visual Studio 2022 Build Tools). `/Brepro` makes the output reproducible: two
builds in a row gave the same bytes, and so did every `build_kmrp.ps1` run that day.
The same evening the submodule moved to `9884466`, FTD's `widescreen-patch` branch
with KMRP's engine fixes merged, whose tree is `17fd051`'s (`7a6f19ec…`); built
from it, both files were byte for byte the same. Later still it moved to `71ac5fa`,
where FTD's branch gained new patches under `Patches/` and nothing under `src/`;
built from it, again the same bytes.

| File | Bytes | SHA-256 | Imports |
| --- | --- | --- | --- |
| `KotorPatcher.dll` | 347,136 | `E7D6AE7F44ABA1FD…` | `KERNEL32.dll` |
| `binkw32.dll` | 88,064 | `3A35A77EB4EEFC96…` | `KERNEL32.dll` |

The runtime waits for Steam's DRM before it patches: at load time a Steam hook
site still holds ciphertext, so `patcher.cpp` hands the apply to a worker thread
that polls every 15 ms, for up to 30 seconds, until every hook site reads as its
original bytes (`AllHookSitesReadable`, `DeferredApply`). CD 1.03 is plaintext on
disk, and there the runtime patches at once, while the proxy is being loaded.

KOTOR Patch Manager is MIT-licensed; the installer writes its licence beside the
runtime as `kmrp-kotor-patch-manager-LICENSE.txt`.
