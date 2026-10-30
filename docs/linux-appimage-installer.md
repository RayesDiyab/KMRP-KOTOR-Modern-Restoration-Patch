# Linux AppImage installer: design

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Measured facts about
> today's installer are marked as measured; everything else is the plan.

**Progress, 2026-10-30 (uncommitted when written).** Step 1 is done and step 2 started, with
the layout changed from section 2's plan: the core stays in `src/patcher`, split out of the
mixed files, and is not moved to a folder of its own. That keeps the tests and tools that
read or compile these files by path working:

| File | What it is |
| --- | --- |
| `src/patcher/InstallCore.cs` | the 17 portable classes from `KmrpPatcher.cs` (game facts, INI, file, patch and controller operations, settings, the update check), moved unchanged; plus `GamePath`, below |
| `src/patcher/KpmEdition.cs` | the install and restore rules, without `ArtPreparation` |
| `src/patcher/ArtPreparation.cs` | the art prebuild through `kmrp.dll`, Windows only, moved unchanged |
| `src/patcher/InstallPlatform.cs` | the steps only Windows has, as partial methods: the DPI value, K1DC, the old NVIDIA setting, the art prebuild, the display's refresh rate |
| `src/patcher/InstallPlatform.Windows.cs` | the Windows installer's half of them, calling the same classes as before |
| `src/installer-linux/` | the .NET 8 program: so far `kmrp-installer inspect <game folder>` |

Checked:
- The move is exact: every line of the two old files is in the new ones. The only lines
  added are each new file's header and `using` lines.
- The core compiles alone, with no WinForms, GDI+, registry or NvAPI.
- The Windows installer builds, and its tests pass: update check, Large Address Aware,
  DPI, NVIDIA removal, K1DC imports, the blend and the art preparation. The last of these
  read the log from the game folder's root; it has been fixed to read `KMRP\logs`, where the
  module writes since 2026-10-20.
- `dotnet publish -r linux-x64` builds a 67 MB single file on Windows. In WSL's Ubuntu
  26.04 it read the Steam game through `/mnt/c` and found Steam's executable with KMRP
  installed and restorable. That needed `GamePath.Combine`: KMRP's records name files with
  `\` (`KMRP\kpm.manifest`), which on Linux named one file with a backslash in it. They
  keep `\` in the records, so the same game can be restored from either system, and are
  written natively when joined to a folder; on Windows that changes nothing.

**Later the same day: install and restore from Linux.**
- **The payload.** `build_kmrp.ps1` writes the installer's resources as it compiles them
  (`build\kmrp\installer-resources.tsv`, 31 of them). `tools/build_linux_installer.ps1`
  embeds the same files under the same names, so the two installers cannot carry
  different payloads. The Linux file is 126 MB, uncompressed for now.
- **Commands.** `kmrp-installer find | inspect | install [--size WxH] | restore`. They call
  what the Windows window calls (`PatchOperations.ApplyInPlace`, `PatchOperations.Restore`)
  and log every report line to `KMRP/logs/install.log`.
- **Linux's half of InstallPlatform** (`src/installer-linux/InstallPlatform.Linux.cs`).
  KPM's settings are read from the game's Proton prefix
  (`steamapps/compatdata/32370/pfx/.../AppData/Roaming/KPatchLauncher`), and Wine's
  `Z:` and `C:` paths in them are turned into Linux folders. The DPI value, K1DC, the
  NVIDIA cleanup and the art prebuild do nothing on Linux: the game makes each size's art
  the first time it is used.
- **Tested in WSL's Ubuntu 26.04,** on a game folder on its own case-sensitive disk
  (Steam's unmodified `swkotor.exe`, its `binkw32.dll`, the original `swkotor.ini`):
  - Without `binkw32.dll` the install refused with the Windows installer's message.
  - With it, the install wrote the same files the Windows installer writes, in lowercase
    `patches` and `configs` folders, none with a backslash in its name.
  - A second install at another size worked.
  - Restore left every game file byte-identical. The only files left are the three KMRP
    keeps on purpose (`KMRP/backups/swkotor.ini`, its `.sha256`, `KMRP/logs/install.log`).
- **Steam discovery** (`SteamLibraries.cs`) reads `libraryfolders.vdf` from native Steam,
  `~/.steam/steam`, Debian's location and the Flatpak, and then `appmanifest_32370.acf`'s
  `installdir`. Tested against a fake home: the game in a second library was found once,
  through the `~/.steam/steam` link too; with no manifest it says so and exits 1.

**Later still that day: the window and the AppImage.**
- **Display detection** (`LinuxDisplay.cs`). `xrandr` gives the outputs' modes and rates; the
  kernel's `/sys/class/drm/card*-*/modes` gives the monitor's own modes. Under Gamescope the
  game starts at the monitor's preferred size, not Gamescope's virtual one (issue 72); otherwise
  at the current size, kept to the sizes KMRP covers (`ResolutionCatalog.Covers`, moved into the
  core from `ResolutionSelection.Covered` so both installers use one rule). Under WSLg it found
  the 3440x1440 display and 28 other sizes, 11 of them not covered.
- **The window looks like the Windows installer's** (`MainWindow.cs`, at the maintainer's
  request: "it needs to look like the windows version"). The same design grid (1980 x 1083,
  the card 1300 x 597 under a 420-pixel header, uniformly scaled), the same rectangles,
  colours, radii, texts and step logic, and the font sizes converted from points.
  - **The header's smoke** is the same code. `LightField` was split: its arithmetic moved
    unchanged into `src/patcher/LightField.cs`, and both windows draw its buffer and motes.
    The Windows window, captured before and after the split six seconds after start, differed
    only in the header, in 91 of 1,507,259 pixels by more than 16 levels (animation timing).
  - **Fonts.** Microsoft's Segoe UI and Bahnschrift cannot ship. Selawik, Microsoft's open
    stand-in for Segoe UI, and Barlow Semi Condensed, for Bahnschrift SemiCondensed, are
    carried (`src/installer-linux/fonts/README.md`).
  - **Its first size** follows `FitInitialSizeToWorkingArea`: 1772 x 969 on the 3440x1440
    display, where the Windows window opens at 1633 x 923 with its frame.
  - **K1DC's tile is disabled**, noted "Windows only": this installer does not install it
    (issue 44).
- **The AppImage** (`tools/build_linux_appimage.sh`, run by `tools/build_linux_installer.ps1`
  in WSL): `dist/KMRP-Linux-<version>-x86_64.AppImage`, packed by appimagetool 1.9.1 (its
  SHA-256 checked). It holds the program, Skia's and HarfBuzz's libraries, a launcher, a
  desktop entry and the Windows installer's icon.
- **Size.** Windows' installer needs no runtime, since .NET Framework 4 is part of Windows,
  so its 59.8 MB is almost all payload (59.2 MB, the art pack already LZMA-compressed). Linux
  has no .NET, so the program carries .NET 8 and Avalonia. Untrimmed the program was 134 MB
  and the AppImage 91.5 MB. Trimmed (`PublishTrimmed`, partial: only what it calls; the
  warnings are all Avalonia's designer support) the program is 81 MB and the AppImage
  **70.1 MB**.
- **Tested in WSL** on the trimmed AppImage (FUSE present):
  - `sizes` and `inspect` work.
  - `install` without `--size` used the display's 3440x1440.
  - Reinstall at another size worked.
  - Restore left every game file byte-identical, keeping the three files KMRP keeps.
  - The window opened from it found the test game through a fake Steam library and showed
    "Ready to patch".
  - Afterwards the Windows installer's tests passed again: update check, Large Address
    Aware, DPI, NVIDIA removal, K1DC imports, the blend and the art preparation.

Not done:
- The game run under Proton after a Linux install (WSL has no Steam).
- The window's buttons pressed by a person: its install and restore call the same code the
  tested commands do, but only the commands were run.
- Ubuntu, SteamOS, Bazzite and a Steam Deck (issue 76's list); Wayland without XWayland, where
  only DRM's list answers.
- A game whose existing files differ only in case from KMRP's names.
- K1DC on Linux (issue 44 decides whether it should be installed there).
- The window's step texts are a second copy of `MainForm.RefreshStatus`'s, in the same words.
  Moving them into the core for both windows is left for later.
- `Test-InstallerPatch.ps1` and `Test-ReinstallOverOlderBuild.ps1`, which borrow the real
  KMRP and KPM settings files, were not run.

**Kind: design (2026-10-30), being built.** Issue 76 asks for a native Linux
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
