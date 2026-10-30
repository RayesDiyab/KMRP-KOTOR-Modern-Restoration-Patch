# Linux AppImage installer: design

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Measured facts about
> today's installer are marked as measured; everything else is the plan.

**Kind: design, not yet built (2026-10-30).** Issue 76 asks for a native Linux
installer, `KMRP-Linux-x86_64.AppImage`, that installs, verifies and restores KMRP in
a Proton KOTOR without running the Windows installer under Protontricks. The
maintainer chose .NET 8 with Avalonia on 2026-10-30. The game still runs under
Proton; only the installer is native.

## 1. What the Windows installer is today (measured 2026-10-30)

`src/patcher`, compiled by .NET Framework 4's `csc.exe` from `build_kmrp.ps1`:
11,154 lines in `KmrpPatcher.cs` (8,754) and `KpmEdition.cs` (2,400), plus
`GuiBlend.cs`, `GameArtGenerator.cs`, `AbilityIconGenerator.cs`,
`ControllerPromptGenerator.cs` and `WindowsEnginePatch.cs`. Every class was scanned
for WinForms, the registry, P/Invoke, NvAPI and process control
(`class_map.py` in the session's scratch folder; the hits checked by hand, since
`[Graphics Options]` in INI text matched a naive "Graphics"):

| Group | Classes | Platform |
| --- | --- | --- |
| Install and restore core | `KpmEditionOperations` (`Install`, `Restore`, `Inspect`, `CanRestore`, `PatchConfigSection`), `PatchOperations`, `IniOperations`, `KmrpFolder`, `FileGuard`, `OverrideOperations`, `OverrideRecord`, `InstallClock`, `BuildStamp` | portable: files, TOML, JSON, INI |
| Game facts | `GameExecutable`, `PeCompatibility`, `GoldPatch`, `WindowsEnginePatch`, `ResolutionChoice`, `ResolutionCatalog`, `ResolutionPatch`, `ResolutionSelection`, `GuiBlend` | portable (PE reading and tables) |
| Art made at install | `GameArtGenerator`, `AbilityIconGenerator` | portable; `ControllerPromptGenerator` draws with GDI+ |
| Art prebuilt by the module | `ArtPreparation` (loads `kmrp.dll` with `LoadLibraryEx` and runs `KmrpRuntimeAssetsPrepare` for every display size) | **Windows only**: an x86 Windows DLL |
| Driver checks | `DriverCompatOperations` (loads K1DC's `dinput8.dll` to read it) | **Windows only** as written |
| Windows settings | `DpiCompatibilityOperations` (AppCompat registry flags), `NvDrsSession`, `NvidiaPresentOperations` (NvAPI) | **Windows only**, and not meaningful under Proton |
| Finding the game | `GameFolders` (Steam and GOG from the registry) | **Windows only** |
| User interface | `MainForm` (2,083 lines), `UiTheme`, the custom controls, `KmrpSettings`, `UpdateDialog`, `Program` | WinForms |
| Update check | `UpdateCheck` | portable |

## 2. Architecture

```
src/installer-core/      shared C#: the first three rows above, moved out of
                         KmrpPatcher.cs and KpmEdition.cs, no UI, no Windows API
src/patcher/             the Windows installer: WinForms + Windows-only steps,
                         compiled with installer-core as today (csc, .NET Framework 4)
src/installer-linux/     .NET 8 + Avalonia app: Linux UI, Steam discovery,
                         display detection; compiles installer-core
```

* **One copy of the rules.** The core moves, it is not copied: the Windows build
  compiles the same files. The core must keep compiling under C# 5 / .NET
  Framework 4 (csc), so no newer language features in it.
* **Platform seams** as small interfaces the core calls: `IGameLocator`,
  `IDisplaySizes`, `IReport` (log and progress), `IArtPreparer` (optional). The
  Windows build passes today's code; Linux passes its own or none.
* **Payload.** The same embedded resources as the Windows installer (the KPM
  runtime, `kmrp.dll`, `kmrp-assets.pack`, the controller patch, K1DC), read
  from the same build outputs; `build_kmrp.ps1` gains a Linux target.

## 3. What Linux does differently

| Step | Windows | Linux plan |
| --- | --- | --- |
| Find the game | registry | Steam's `libraryfolders.vdf` (`~/.steam/steam`, `~/.local/share/Steam`, Flatpak `~/.var/app/com.valvesoftware.Steam/...`), app 32370's `appmanifest`, plus manual selection |
| Display sizes | `EnumDisplaySettings` | the host's outputs: `xrandr` on X11; on Wayland the compositor's own (`wlr-randr`, `kscreen-doctor`, `gnome-randr`), `/sys/class/drm/*/modes` as a fallback; manual entry. Gamescope's virtual size kept apart from the output size (issue 72) |
| Prebuilt art | every display size, through `kmrp.dll` | skipped: the module builds each size the first time it is used, as it does for a size the installer did not prebuild. First visit of a size is slower; measured cost to be recorded |
| NVIDIA present method | NvAPI | none: no NVIDIA profile under Proton |
| DPI and compatibility flags | registry | none under Proton (to be confirmed against Wine's prefix registry) |
| K1DC check | loads its DLL | reads the PE version resource instead (portable), or left to the module |
| Logs | `KMRP\logs` | the same folder in the game |

## 4. Packaging

* `dotnet publish -r linux-x64 --self-contained -p:PublishSingleFile=true`, then
  `appimagetool`, in the WSL Ubuntu on the build PC (`wsl -l` lists `Ubuntu`,
  `Ubuntu-20.04` and `steamos-builder`). The .NET 8 SDK is installed on Windows
  (8.0.204, 8.0.427); the Linux build needs it inside WSL too.
* Size: estimated 60 to 80 MB before the payload; the payload is what the
  Windows installer carries.
* No FUSE: document `--appimage-extract-and-run` for systems without it.

## 5. Order of work

1. Move the core into `src/installer-core` with no behaviour change; the Windows
   installer and its tests (`Test-InstallerPatch.ps1`,
   `Test-ReinstallOverOlderBuild.ps1`, `Test-KpmEdition.ps1`) must pass unchanged.
2. A Linux console front end over the core (install, restore, verify, `--game`),
   run in WSL against a copy of a Proton game folder.
3. Steam discovery and display detection, with tests on recorded
   `libraryfolders.vdf` and `xrandr` outputs.
4. The Avalonia UI, matching the Windows installer's steps and options.
5. AppImage build, checksums, Linux documentation; then the tests issue 76 lists
   (Ubuntu, SteamOS and Bazzite, a Steam Deck, Gamescope scaling).

## 6. Open questions

* Prebuilt art on Linux: skipping it is simplest; running the preparer under
  Proton (`proton run`) once after install would match Windows. Decide after
  measuring a first visit's delay.
* Issue 72's runtime half: the module may still need to read Gamescope's size at
  run time; the installer alone cannot fix a size chosen in the game.
* Whether the Avalonia app should also become the Windows installer later (one UI)
  is out of scope here.
