# KMRP's features, technically

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It is an index: each row
> names the mechanism and points at the document that holds the measurements. Where
> something has not been seen in the game, the row says so.

The same list as [features.md](features.md), the players' version, with how each
feature is done, which of the two patches carries it and where to read more. State
of 2026-10-08.

## How KMRP reaches the game

| Piece | What it is | Source |
| --- | --- | --- |
| Installer | `KMRP-Windows-1.5.1.exe` on the release (the build writes it to `dist` as `KMRP - KOTOR Modern Restoration Patch.exe`), a .NET Framework 4 program. It installs KOTOR Patch Manager 0.7.1's runtime beside the game as KPM's own proxy deployment (`binkw32.dll` proxy, `KotorPatcher.dll`, `patch_config.toml`), the patches' modules under `patches\`, and their settings under `configs\`. | `src/patcher/KmrpPatcher.cs`, `src/patcher/KpmEdition.cs`; [patcher-ui-build.md](patcher-ui-build.md), [kpm-edition.md](kpm-edition.md) |
| `KMRP.kpatch` | Patch id `kmrp`, 28 hooks, module `patches\kmrp.dll`. Options `map-notes` (on), `hd-icons` (on) and `debug-logs` (off), recorded in `configs\kmrp.ini`. Carries the engine recipe and every resolution's interface files. | `tools/build_native_kpatch.py`, `src/controller-native/K1Runtime*.cpp`, `K1KpmApplier.cpp` |
| `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` | Patch id `kmrp-controller`, 36 hooks, module `patches\kmrp-controller.dll`. Options `xbox-hud` (on since 2026-10-08) and `debug-logs` (off), recorded in `configs\kmrp-controller.ini`; the player's settings (rumble, HUD style, button layout) are `KMRP\controller.ini` in the game folder (`kmrp-controller.ini` beside the game until 2026-10-20). Requires nothing and does not conflict with `kmrp`. Installed while Controller Support is on. | `tools/build_controller_kpatch.py`, `src/controller-native/`; [controller-standalone.md](controller-standalone.md) |
| `HighFpsFixes.kpatch` | D3M0's High FPS Fixes 1.0.1 (MIT), patch id `high-fps-fixes`, 36 hooks (18 detours, 14 replacements, 4 byte patches), module `patches/high-fps-fixes.dll`, no options. The release's own file, unchanged. Installed only while High FPS Fix is on in Advanced Settings: on by itself where the display reports 62 Hz or more at its current size (`ResolutionSelection.HighestRefresh`), off otherwise, the player's own choice kept (since 2026-10-09). **Not run in the game by KMRP.** | `third_party/Included/HighFpsFixes-1.0.1 by D3M0`, `tools/build_bundled_kpatch_config.py`; `THIRD_PARTY_NOTICES.md` |
| Engine changes | Applied in memory when the game starts, after the original instructions at every site have been checked. The recipe is built from source: no clean or patched executable is a build input. Eleven code and data pages are placed as one relocated block; per-resolution operands are computed for the size in use and again on a mode switch. | `src/engine/windows-sites.json`, `tools/build_windows_engine.py`, `tools/build_native_engine.py`; [windows-engine-source.md](windows-engine-source.md) |
| Interface files | One art pack of distinct files, `kmrp-assets.pack`, beside the module in the game's `patches` folder (since 2026-10-19; until then a bank inside the module), with an index per resolution: LZMA, images through a reversible filter first ([`tools/kmrp_pack.py`](../tools/kmrp_pack.py)). The installer writes it and makes every size the display offers before the game first starts; the set of the size in use is in a cache under `%LOCALAPPDATA%\KMRP\cache` that the game reads ahead of `Override`; since 2026-10-11 a file the player has in `Override` is taken out of the cache first, so Override's is the one used (not yet run in a game). For the active 32-slot roster patch, its GUI is generated at runtime when missing, or a validated adaptation of its supplied GUI stays in the cache; [roster compatibility](../reverse-engineering/party-roster-compatibility.md). Files the module can produce exactly from its blend table are left out of the pack and written when a size is made. | `tools/build_native_assets.py`, `tools/kmrp_pack.py`, `K1AssetPack.cpp`, `K1RuntimeAssets.cpp`, `ArtPreparation` in `KpmEdition.cs`; [universal-resolution-math.md](universal-resolution-math.md) |
| The one change on disk | The Large Address Aware bit of `swkotor.exe`, on the GOG and editable 1.03 builds only. Steam's file is never written. | `KpmEditionOperations.SetLargeAddressAware`; [large-address-aware.md](../reverse-engineering/large-address-aware.md) |
| KMRP's own folder | Since 2026-10-20 (not run in a game): `KMRP` in the game folder holds KMRP's manifests (`kpm.manifest`, `dpi.manifest`, `nvidia.manifest`, `driver-compat.manifest`), the controller's settings (`controller.ini`), KPM's licence, `logs\` (the installer's `install.log` and the modules' logs) and `backups\` (`swkotor.ini` and its hash). Until then they were loose in the game folder; an install or restore moves an earlier install's (`KmrpFolder.Migrate`), and Restore Original removes the folders it leaves empty. What the game or KPM loads stays in the game folder. | `KmrpFolder` in `KmrpPatcher.cs`, `KmrpOptions.h`; [kpm-edition.md](kpm-edition.md#kmrps-own-folder-since-2026-10-20) |

Accepted executables: Steam's, GOG's and the editable 1.03 build, the last two also
with the Large Address Aware bit already set
([mod-build-compatibility.md](mod-build-compatibility.md)).

## Resolution and screen

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| The game lists what the display reports | `kmrp` | The game builds its Screen Resolution list from `EnumDisplaySettingsA`; KMRP filters the import slot only to drop repeated rows. The game's `IsValidResolution` is answered by `KmrpAllowRuntimeResolutionK1`: a size is valid when KMRP has a layout for it and the display reports a mode of it (`DisplayReports`). | `K1RuntimeResolution.cpp`; [runtime-resolution-preview.md](../reverse-engineering/runtime-resolution-preview.md) |
| Start at the display's own size | `kmrp` | The game's two 800x600 fallbacks (`ReadVideoModeSettings`, `ReadAndSetVideoMode`) are rewritten at load to the desktop's size (`KmrpStartAtDisplaySize`). `swkotor.ini` is not rewritten. Tested by putting a size the display lacks into the file; **not seen on a second display.** | `K1RuntimeResolution.cpp`; CHANGELOG, 2026-10-07 |
| Frame rate | installer and `kmrp` | The game's Screen Resolution list has a row for each refresh rate of 60 Hz or more and hides those above 85 Hz unless `AllowHighMonitorFrequency=1` is in `swkotor.ini`. With High FPS Fix the installer writes that and `RefreshRate` as the display's highest; without it, `RefreshRate=60` and `V-Sync=1`, and the module hides the rates above 60 from the list (`EnumModesOnce`) unless `high-fps-fixes.dll` is loaded. Seen in a scratch copy: 120 and 60 screen updates a second at the menu. | `KmrpPatcher.cs` (`FrameRateLines`), `K1RuntimeResolution.cpp`; [resolution-switch.md](../reverse-engineering/resolution-switch.md), CHANGELOG, 2026-10-09 |
| Change resolution in the game | `kmrp` | On a mode switch the module recomputes the engine operands, unpacks the new size's interface set, fonts included, and lays every live panel out again, the area map's surfaces with it (since 2026-10-09; not seen in the game). | `K1RuntimeEngine.cpp`, `K1RuntimeAssets.cpp`, `K1RuntimeLayout.cpp`; [resolution-switch.md](../reverse-engineering/resolution-switch.md) |
| 66 built sets, any other size blended | `kmrp` | Layouts are generated per resolution from one rule, `max(1.0, height / 720)`. A size without a set gets layouts blended from the sets around it, with the fonts of the nearest listed size. | `tools/prepare_universal_resources.py`, `src/patcher/GuiBlend.cs` and its module counterpart; [universal-resolution-math.md](universal-resolution-math.md) |
| DPI awareness | installer | A per-executable compatibility value for the current user, recorded in `KMRP\dpi.manifest` (`KMRP_DPI.manifest` until 2026-10-20) and restored. | [windows-dpi-scaling.md](windows-dpi-scaling.md) |
| Mouse confinement | `kmrp` (the controller patch when alone) | The cursor is clipped to the game's window in fullscreen, from the GUI frame hook. | `K1NativeJoystick.cpp`; [controller-support.md](controller-support.md) |

## Text and menus

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| Fonts per resolution | `kmrp` | All 18 atlases are rasterised from vector outlines at build time, once per resolution at its own scale, one texel per pixel. `spacingR 0` since 2026-10-05, which stops text overrunning its box. *Corrected 2026-10-18:* since 2026-10-17 the module holds one set per font style instead and sizes it at run time (next row); the per-resolution sets now only feed the build's layouts. | `tools/build_font_scale_sets.py`; [font-scaling.md](font-scaling.md), [font-atlases.md](../reverse-engineering/font-atlases.md) |
| Text Size and Font page; HD Original font | `kmrp` | A native page in Graphics Options: four text sizes, 25% to 100% (50% the earlier size), and three fonts: Original Font, (New) Original HD Font (the default since 2026-10-18) and (Old) HD Font. HD Original is the game's own fonts redrawn from Bank Gothic Medium and Helvetica at sizes, spacing and weight measured from the originals to a fraction of a pixel. Both HD sets are baked at 6x and fitted to the drawn size at run time. Saved in `swkotor.ini`. **HD Original not yet seen in the game.** | `K1TextOptions.cpp`, `K1RuntimeAssets.cpp`, `tools/build_hd_original_fonts.py`; [ingame-text-options.md](ingame-text-options.md), [hd-original-font.md](hd-original-font.md) |
| Rows and icons scale | `kmrp` | Row heights and icon sizes are constants in the executable; they are replaced by values from the scale rule. | [inventory-item-rows.md](../reverse-engineering/inventory-item-rows.md) |
| Rows centred in their box | `kmrp` | Three detours in `CSWGuiListBox::OrganizeControls` (`KmrpListRowK1`), with a gap for the store's and workbench's lists. **Not seen at most sizes.** | `K1ListRows.inc`, `K1RuntimeLayout.cpp`; [listbox-geometry.md](../reverse-engineering/listbox-geometry.md) |
| Rows do not grow | `kmrp` | The list box added a row count to a row height and wrote the result back into reused controls; corrected. | [listbox-geometry.md](../reverse-engineering/listbox-geometry.md) |
| Stack counts | `kmrp` | The count label is rebuilt against the scaled icon box. | [inventory-item-rows.md](../reverse-engineering/inventory-item-rows.md) |
| Descriptions clear of the scrollbar | `kmrp` | The gutter is set on the panes vanilla left at 0, and line measurement is corrected. | [listbox-geometry.md](../reverse-engineering/listbox-geometry.md), [text-padding.md](../reverse-engineering/text-padding.md) |
| Popups fit their text | `kmrp` | The auto-fit loop's 640x480 cap is replaced; a fit detour sizes message, tutorial and confirmation boxes. | `K1PopupFit`; [message-popup.md](../reverse-engineering/message-popup.md) |
| HUD notices and Feedback at 4K | `kmrp` | Short-lived HUD controls follow the height rule; the Feedback list keeps a gutter. | [universal-resolution-math.md](universal-resolution-math.md#reported-4k-layout-repairs) |
| Dialogue letterbox | `kmrp` | Bar height was derived from screen width; corrected. | [font-scaling.md](font-scaling.md) |
| Keyboard navigation of menus | `kmrp` | Three hooks: the source port of the Mac's row and list-boundary repair. **Not verified against the keyboard failure it was written for.** | [windows-keyboard-navigation.md](../reverse-engineering/windows-keyboard-navigation.md) |

## Map

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| Map fills its frame, fog covers it | `kmrp` | The map picture is drawn on a canvas wider than the overlay that carries fog and markers; the surplus is cropped and the control sized to the overlay. | [area-map-surface.md](../reverse-engineering/area-map-surface.md), [map-scaling.md](../reverse-engineering/map-scaling.md) |
| Marker clicks and marker size | `kmrp` | The hit test uses the origin the overlay is drawn from; markers follow the scale rule. | [map-markers.md](../reverse-engineering/map-markers.md) |
| HUD minimap follows the player | `kmrp` | Vanilla sizes the minimap's picture for a 120-pixel viewport; the picture is scaled by `viewport / 120` about the centre. | [map.md](../reverse-engineering/map.md), CHANGELOG |
| 250 corrected map notes | `kmrp`, option `map-notes` | Derslok's corrected positions, applied by the module when the option is on. | [map-markers.md](../reverse-engineering/map-markers.md) |

## Movies

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| No mode switch | `kmrp` | Bink playback has two resolution pairs of its own; both receive the size the game is running at. Since 2026-10-20 they are a recipe feature of their own (bit 8), which `original-movie-mode=1` under `[Movies]` in `configs\kmrp.ini`, written only by a player and kept by an install, leaves out: the game's own switch to 640x480 for movies, the fallback for issue 48. A change of resolution in the game leaves those operands alone while it is on (`FieldInForce`). **Not run.** There is a third pair, the check after a playlist (`0x00403EA7`, `0x00403EB3`), left at 640x480 until 2026-10-20; since then (after `4a1cd73`) it gets the game's size too, so no full-screen movie ends in a rebuild of the renderer and a second display-mode change, and the start-up anti-aliasing rebuild the game left to that rebuild is made before the start-up movies (`0x005F92A8`, `jne` to two `nop`s). Both are in bit 8. **Not run either.** | [movies.md](../reverse-engineering/movies.md) |
| Aspect-fit with black bars | `kmrp` | The scale is taken from whichever of width and height runs out first; the per-frame hook is `KmrpCoreMovieWorkK1`. Since 2026-10-20 the width it fits to is at most a 16:9 area's, `min(W, H × 16 / 9)`: a 2.35:1 movie is 2560x1088 at 3440x1440 (3388x1440 until then). A movie at least as wide or as tall as the screen, a replacement made for it, is fitted to the whole screen as before. **No movie has been watched since that hook moved (CHANGELOG), nor with the 16:9 area.** | [movies.md](../reverse-engineering/movies.md) |
| Bink draws with GDI | `kmrp` | Since 2026-10-20 `BinkBufferOpen` is asked for buffer type 2, a DIB section drawn with GDI, instead of Bink's own choice: one byte at `0x00405734`, for everyone. Aimed at the black startup movies of issue 48 (Windows 7, AMD). **Not run on any PC.** | [movies.md](../reverse-engineering/movies.md) |

## Stability

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| Inventory crash | `kmrp` | The line-breaker compared against the start of the string, not of the line, and looped until allocation failed; corrected. | [font-atlases.md](../reverse-engineering/font-atlases.md) |
| 4 GB address space | installer, or KPM from the patch's static hook | The PE header's Large Address Aware bit; not on Steam's executable. | [large-address-aware.md](../reverse-engineering/large-address-aware.md) |
| Texture bucket, grass, save game | `kmrp` | KOTOR Patch Manager's memory-safety fixes, included in the patch; KPM's own ones are declared as conflicts. | `tools/build_native_kpatch.py`, `tools/check_kpm_overlaps.py` |
| Modern Driver Compatibility | installer, optional | Synchro's ASI loader (`dinput8.dll`) and payload beside the game, recorded in `KMRP\driver-compat.manifest` (`KMRP_DriverCompat.manifest` until 2026-10-20). The collision check against KMRP's sites was last run on the reference images of 2026-09-24, not in memory. (*Corrected 2026-10-20:* it has been run against what KMRP writes in memory since 2026-10-19, last on 2026-10-20, with 0 of 28 sites colliding.) Left out on Windows 7, until Synchro's own release with Windows 7 support. | [third-party-driver-compat.md](third-party-driver-compat.md) |
| NVIDIA present method | installer and module | "Prefer native" is set for `swkotor.exe` only when the global setting would give half-drawn frames, recorded in `KMRP\nvidia.manifest` by the installer (`KMRP_NVIDIA.manifest` until 2026-10-20; the module's own step still writes that name) and removed on restore. | [nvidia-present-method.md](nvidia-present-method.md) |

## Artwork

| Feature | Patch | How | Read |
| --- | --- | --- | --- |
| Portraits | `kmrp` | MadDerp's Party Portraits, in the module's bank. | `THIRD_PARTY_NOTICES.md` |
| Item icons | `kmrp`, option `hd-icons` | JackInTheBox's HD Icon Pack, 351 icons in the module's bank. With the option off the module does not unpack them (`HdIcon`, `K1RuntimeAssets.cpp`) and the game draws its own. **The option off has not been seen in the game.** | `THIRD_PARTY_NOTICES.md`, `testing/regression/Test-NativeAssetsBank.py` |
| Menu art, ability icons | `kmrp` | Built by the resource tools; ability icons and row icon frames are scaled per resolution. | `tools/scale_ability_icons.py`, `tools/scale_row_icon_frames.py`; [patcher-ui-build.md](patcher-ui-build.md) |

## Controller support

All of it is the controller patch, `kmrp-controller`, unless a row says otherwise.

| Feature | How | Read |
| --- | --- | --- |
| Pad backends | XInput for Xbox pads; bundled SDL 3 with HIDAPI for PlayStation, Switch and Steam Deck. The pad used last is the one read. | `K1ControllerBackend.cpp`; [controller-sdl-backend.md](controller-sdl-backend.md) |
| Native input | The module presents the joystick device the game's retained console input expects; no key presses are synthesised. Movement is proportional with a 15% deadzone. | `K1NativeJoystick.cpp`; [controller-native-path.md](controller-native-path.md), [retained-xbox-gui-events.md](../reverse-engineering/retained-xbox-gui-events.md) |
| What every button does | Per screen, as measured. | [controller-behaviour-matrix.md](controller-behaviour-matrix.md), [controller-parity.md](controller-parity.md) |
| Button layout | Since 2026-10-19 (issue 49), the original Xbox game's, White and Black on LB and RB: in the world LB pauses, RB switches the party leader, LT and RT cycle targets, B lets go of the action bar or disengages, X does what A does, Y undoes the last queued action or flourishes, Start reopens the menu screen used last; in menus RB is Black (the Journal's sort, the party switch on the four party screens), and Pazaak's table takes X, LB, A and Y as the Xbox's footer names them. Until then KMRP's own (LB and RB targets, LT party, RT pause, X disengage, Start the Map). **Not seen in the game.** | `K1_GAMEPLAY_ACTIONS`, `K1_BUTTONS`, `K1_BUTTON_REMAPS` in `K1NativeJoystick.cpp`; [controller-parity.md](controller-parity.md), [controller-layout.md](controller-layout.md) |
| Button prompts | Badge textures for four pad families, placed from the running game's own controls so they fit any interface (seen beside KMRP at 3440x1440 and beside Scaled Kotor 1.3.1). Hidden while mouse or keyboard is in use. | `tools/build_controller_prompt_textures.py`, `vendor/K1XboxControls.cpp`; [controller-prompt-specification.md](controller-prompt-specification.md), [button-focus-badge-geometry.md](../reverse-engineering/button-focus-badge-geometry.md) |
| Controller Layout screen | A panel added under Options, Gameplay, with live glyphs. | `K1ControllerLayout.cpp`, `tools/build_controller_layout.py`; [controller-layout.md](controller-layout.md) |
| Button remapping | Since 2026-10-18, uncommitted when written. On the Controller Layout screen, which opens as a view: A, B, X, Y, LB, RB, LT, RT and the two stick clicks; no swapping, Save only when every action has a button. Since 2026-10-20 the view has Default too, which asks, then saves the Xbox layout; not seen. The pad's buttons are translated after the pad is read, in the world only (input classes 0 and 4), each press keeping its meaning until released; no hook added. The HUD's Y and B cues (Y and X until 2026-10-19) and the pause notice follow a saved remap. `[Controller Remap]` in `KMRP\controller.ini` in the game folder (`kmrp-controller.ini` beside the game until 2026-10-20), with a `Layout=Xbox` line since 2026-10-19, without which a saved layout is not read (one saved against the old defaults opens as the Xbox ones). The screen's 55 controls are made at run time from the layout file's own. **Seen with mouse and keyboard at 3440x1440 and 1920x1080; nothing with a pad has been run.** | `K1ButtonRemapPolicy.h`, `K1ButtonRemap.cpp`, `K1ControllerLayout.cpp`, `K1NativeJoystick.cpp`, `testing/regression/Test-ButtonRemap.py`; [controller-layout.md](controller-layout.md#button-remapping) |
| Rumble | Off, Original (BioWare's table) or Enhanced; `[Rumble]` in `KMRP\controller.ini` in the game folder (`kmrp-controller.ini` beside the game until 2026-10-20), read again while playing. | `K1Rumble.cpp`; [controller-rumble.md](controller-rumble.md) |
| Xbox-style HUD | On by default since 2026-10-08 (**the default not yet seen in the game**); off with the option `xbox-hud`, or `Style=PC` under `[Hud]` in `KMRP\controller.ini`. Shown while the pad is in use. Laid out at run time for any screen size, with frames drawn as geometry; hot-swaps with the PC HUD on input change. | `K1XboxHud.cpp`, `tools/build_xbox_hud.py`; [controller-xbox-hud.md](controller-xbox-hud.md) |
| Hand checks | Each dated pass on a real pad. Minigame buttons (Pazaak, swoop, turret) are registered but **have not been observed in play.** | [controller-playtest-checklist.md](controller-playtest-checklist.md) |
| Open work | The Guide button and virtual-pad slot safety. | [controller-planned-work.md](controller-planned-work.md) |

## Installer

| Feature | How | Read |
| --- | --- | --- |
| Finds the game | Steam libraries, then GOG, or Browse. Under Wine and Proton, Linux's Steam libraries first (since 2026-10-11, not yet run there). | `GameFolders` in `KmrpPatcher.cs` |
| Restore Original | Every written or renamed file and the flag are recorded with hashes in `KMRP\kpm.manifest` (`KMRP_KPM.manifest` until 2026-10-20); a file changed since install is left alone and reported. | `KpmEdition.cs`; [patcher-ui-build.md](patcher-ui-build.md) |
| Replaces older installs | A build that rewrote `swkotor.exe` is restored from its backup; a four-patch or `Override` install is removed first. | `testing/regression/Test-ReinstallOverOlderBuild.ps1` |
| With KOTOR Patch Manager | The two `.kpatch` files go to KPM's patch folder; where KPM's runtime is already in the game folder, the installer leaves the patches to KPM. `--export-kpm-patches <folder>` writes both out. | [kpm-edition.md](kpm-edition.md) |
| Advanced Settings | Controller support, driver compatibility, map notes, HD item icons (on), High FPS Fix and debug logs (off); remembered in `%LOCALAPPDATA%\KMRP\settings.json`. | `KmrpPatcher.cs` |
| Update check | One request to GitHub's releases when the window opens. | [SECURITY.md](../SECURITY.md) |
| Command line | `--in-place`, `--restore`, `--apply`, `--export-kpm-patches`. | [README](../README.md) |

## How it is checked

| Check | Command |
| --- | --- |
| The packaged patches | `python testing/regression/Test-KpatchSource.py`, `python testing/regression/Test-ControllerKpatch.py` |
| What the installer puts in a game folder, and restore | `.\testing\regression\Test-InstallerPatch.ps1` |
| Install over an older build | `.\testing\regression\Test-ReinstallOverOlderBuild.ps1` |
| Hook overlaps with KOTOR Patch Manager's patches | `python tools/check_kpm_overlaps.py` |
| Documentation links | `python .github/scripts/check_links.py` |

The full list is in [testing/README.md](../testing/README.md).

## Other platforms

- **macOS:** a separate installer for the Aspyr build, maintained on its own; see
  [macos/README.md](../macos/README.md).
- **Linux and Proton:** the build of 2026-10-01, which still wrote `Override`
  files, has a measured record under Proton Experimental on Ubuntu. A later
  development build of 1.5, without `Override` files, was run by the maintainer on
  Ubuntu under the stable Proton and Proton Experimental and worked (his report of
  2026-10-08; the build's hash, the Proton versions and what was played were not
  recorded). The released build **has not been run under Proton**, and **no Steam
  Deck has been tried.** See [linux-proton-steam-deck.md](linux-proton-steam-deck.md).
