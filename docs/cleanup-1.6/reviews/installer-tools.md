> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

**The report file does not exist.** The Write tool refused it ("Subagents should return findings as text, not write report files"), so the whole report is below instead of at `report-installer-tools.md`.

**Summary.** 232 rows: keep 114, change 47, document 20, move 20, merge 12, remove 10, unverified 9. Nothing was run or changed.

1. About 3,100 lines in the installers are reference code no install runs: `ResolutionPatch`, `WindowsEnginePatch`, the three generators and most of `GuiBlend`. They are reached only by `--apply`, `--derive-gui` or test compiles.
2. The per-size arithmetic the game really runs (`resolution_fields()`, `K1RuntimeEngine.cpp`) has no test. The tests check the unused C# copy.
3. The build cache hashes all of `tools/` recursively, so 80 of 136 tool files outside the build can still force the slow steps.

Also: the legacy swkotor.exe path is not dead; it serves v1.0.0 upgrades only. `font-converter/` is at the root, not in `src/`.

---

# Audit report: installers, tools, build, tests, documents and repository hygiene

Issue 82, read-only audit of 2026-11-01, at commit `2194acf` on master. Scope: everything outside `src/controller-native` that `docs/cleanup-audit-1.6.md` does not list. Nothing was built, run or changed. No test was run; a test's row says what reading it shows, not that it passes. Helper scripts and their output are in the scratchpad (`csmap.py`, `csdead.py`, `toolsuse.py`, `toolhead.py`, `testsum.py`, `docaudit.py`, `guinames.py`, `covgap.py`).

**How "no caller" was established.** Whole-word search of every `.cs` file in `src/patcher`, `src/installer-linux` and `testing/regression`, comments removed, then the hits read by hand. A call by reflection would not show; I found no reflection on these names. Tool use was traced from `build_kmrp.ps1` and the `.cmd` files through Python imports, `import_module` and named script paths, with tests, `macos/`, CI and documents counted apart.

A `remove` or `move` here is a proposal; nothing goes without the maintainer's word.

## 1. The entries

### 1.1 `src/patcher`: jobs by line range

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `KmrpPatcher.cs` 23-396 DPI (`DpiCompatibilityOperations`) | move | Windows only, live: `InstallPlatform.Windows.cs` calls Install, Rollback, Restore. Own file, P4. |
| `KmrpPatcher.cs` 398-745 `NvDrsSession` | change | Only `NvidiaPresentOperations` uses it. `FindProfile`, `CreateProfile`, `AddApplication`, `SetDword` have no caller since `81dac75` (2026-10-30), yet their entry points are fetched in the constructor, which throws if a driver lacks one. P3. |
| `KmrpPatcher.cs` 747-920 `NvidiaPresentOperations` | keep | `Restore` runs at every install and restore, for a record older installs left (`docs/nvidia-present-method.md`). `Describe` is called only by `NvidiaPresentSelfTest.cs`. |
| `KmrpPatcher.cs` 922-1007 `DriverCompatOperations` | change | `MissingImport`, `CanRunHere` live. `Version` (935) has no reader. |
| `KmrpPatcher.cs` 1009-1445 `UiTheme` | move | Window drawing; holds a repeat, see 1.3. |
| `KmrpPatcher.cs` 1446-1937 controls (`KotorProgressBar`, `CardPanel`, `StepRow`, `StateLabel`, `PillButton`, `DarkCombo`) | change | `DarkCombo` (1880-1937): no `new DarkCombo`, only a type test at 3790. Dead since the resolution dropdown went (2026-10-07). P3. |
| `KmrpPatcher.cs` 1938-2068 `LightField` partial | keep | Windows half of `LightField.cs`, as its header says. |
| `KmrpPatcher.cs` 2069-2162 `UpdateDialog` | keep | Called from `OfferUpdate` (4456). |
| `KmrpPatcher.cs` 2163-2273 `ResolutionSelection` | change | `Covered` is a one-line forward. `Start` repeats `MainWindow.StartSize`, 1.3. |
| `KmrpPatcher.cs` 2274-2857 option row and scrolling | move | Live UI. Option row set-up repeats at 3260-3388, 1.3. |
| `KmrpPatcher.cs` 2858-4935 `MainForm` | change | 2,078 lines: constructor 3009-3505 (497), resize and scale 3544-3830, header drawing 3842-4060, settings page 4180-4260, painting 4292-4412, status 4514-4712, actions 4744-4935. `UseDarkScrollBars` (4162) has no caller. Split in P4. |
| `KmrpPatcher.cs` 4936-5151 `GameFolders` | keep | Windows game search, live. No test names it. |
| `KmrpPatcher.cs` 5152-5268 `Program` | change | Seven command forms. `--apply` and `--derive-gui` are test tools. Two-argument `--in-place` and three-argument `--apply` default to 3440x1440 (`IniOperations.DefaultWidth`), left from gold. |
| `InstallCore.cs` 28-38 `GamePath` | keep | Live on both installers. |
| `InstallCore.cs` 40-47 `ExecutableState` | change | `Gold` now means "KMRP is installed" (`KpmEdition.cs:306`). Rename to `Installed`. |
| `InstallCore.cs` 49-99 `PeCompatibility` | keep | Live on every status check: `InspectStandalone` calls `IsSupportedSourceFile` for CD and GOG files. The offset is used by `WriteCharacteristics`. |
| `InstallCore.cs` 101-187 `GameExecutable` | keep | The three accepted builds; live. |
| `InstallCore.cs` 189-239 `GoldPatch` | change | Misnamed: holds the live hashes, `HashFile`, `HashBytes`, `PatchVersion`. `TargetHash`, `TargetLength` are the legacy part. `build_kmrp.ps1:431` and `tools/build_linux_installer.ps1` find `PatchVersion` by regex over this file, so a move must change both. |
| `InstallCore.cs` 241-444 `ResolutionChoice`, `ResolutionCatalog` | change | `Relabel`, `Blended` have no caller. Map fields (`CanvasWidth` and the rest) are read only by `ResolutionPatch`. `Covers`, `Find` live. |
| `InstallCore.cs` 446-989 `ResolutionPatch` | move | 544 lines, 277 of them comment. One caller: `WindowsEnginePatch.BuildData`. The game's path is `build_native_engine.py` and `K1RuntimeEngine.cpp`. P1. |
| `InstallCore.cs` 991-1406 `IniOperations` | change | Live. `Describe` (1022) has no caller. `HashBytes` repeats `GoldPatch.HashBytes`. |
| `InstallCore.cs` 1408-1554 `ControllerOperations` | move | `Restore`, `Owns` serve an install from before 2026-09-29. `DefaultSettings` is live and belongs with the controller's settings; the class name misleads. |
| `InstallCore.cs` 1556-1736 `OverrideOperations` | change | `Restore` live for pre-2026-10-04 installs (`KpmEdition.cs:631`, `InstallCore.cs:2300,2330`). `WriteManifest` (1682) has no caller. |
| `InstallCore.cs` 1738-1867 `FileGuard` | keep | Live; no test names it. |
| `InstallCore.cs` 1869-1984 `DriverCompatStandalone` | keep | Windows 7 and 8 route, and removal on both systems. |
| `InstallCore.cs` 1986-2147 `KmrpFolder` | keep | Migration table; `Test-InstallerPatch.ps1` case 11. |
| `InstallCore.cs` 2149-2486 `PatchOperations` | change | Its plain members only forward to `KpmEditionOperations`. The rest is the legacy path, 1.2. |
| `InstallCore.cs` 2488-2806 `KmrpSettings` | change | Seven identical regex blocks (2725-2772), six identical setters. Orphan comment 2556-2558 names a checklist removed on 2026-10-07. |
| `InstallCore.cs` 2808-2882 `UpdateCheck` | keep | `Test-UpdateCheck.ps1`. |
| `InstallCore.cs` 2884-2889 `ControllerPromptGenerator` partial | remove | Exists only so `GuiBlend` compiles on Linux. Goes with P1. |
| `KpmEdition.cs` 22-69 `BuildStamp` | move | Live. Own file; no test names it. |
| `KpmEdition.cs` 118-224 constants | change | Comment 137-143 is corrected by 148-157; 162 says High FPS is "off by default", while `KmrpSettings` turns it on by itself above 60 Hz. |
| `KpmEdition.cs` 228-362 state | keep | Live. |
| `KpmEdition.cs` 366-580 install | change | `InstallCore` is one 197-line method: checks, migration, removal, writes, rollback, report text. P4. |
| `KpmEdition.cs` 585-871 restore and KPM takeover | keep | Live; comments give the measured reasons. |
| `KpmEdition.cs` 875-1169 runtime, patch choice, `patch_config.toml`, options file | keep | Live. |
| `KpmEdition.cs` 1171-1319 KPM state, backup, 4 GB flag | keep | Live. Read-only handling repeats 797-809, 1.3. |
| `KpmEdition.cs` 1326-1424 undo, resources | merge | `PatchModule` equals `ArtPreparation.ModuleBytes`, 1.3. |
| `KpmEdition.cs` 1426-1804 owned files, `.kpatch` delivery, KPM settings, manifest | keep | Live. `HashBytes` (1748) repeats `GoldPatch.HashBytes`. |
| `KpmEdition.cs` 1845-1997 `InstallClock` | move | Live. Own file; no test names it, though it holds the most arithmetic in the installer. |
| `GuiBlend.cs` 62-1755 | change | Install uses `Shared`, `Covers`, `MinimumHeight` (`InstallCore.cs:394,428`, `ArtPreparation.cs:382`). `Derive`, `Generate`, `DrawBadge`, `DrawHud`, `RewriteManifest` and the rest, about 1,100 lines, run only under `--derive-gui`. `SetFilesNeeded`, `Describe` have no caller. P2. |
| `ArtPreparation.cs` | keep | Windows only, live through `InstallPlatform`. |
| `AbilityIconGenerator.cs` | move | `TryBuild` is called only by `Test-AbilityIcons.py`'s driver, by nothing in either installer. P1. |
| `GameArtGenerator.cs` | move | Same: only `Test-GameArt.py`. P1. |
| `ControllerPromptGenerator.cs` | move | `TryBuild` has no caller at all, and no test drives it. Only `ManifestName` is read. If nothing needs it, `remove`. |
| `WindowsEnginePatch.cs` | move | `ApplyToExecutable` is called only by `ApplyToNewFile`; `BuildData` only by that and `WindowsEngineSelfTest.cs`. Also compiled into the Linux installer, which has no `--apply`. P1. |
| `InstallPlatform.cs`, `.Windows.cs` | keep | A clean seam (2026-10-30). |
| `LightField.cs` | change | `BlitMs`, `BloomMs`, `LastRenderMs`, `MapMs`, `MotesMs`, `SmokeMs`: no reader found. |
| `AssemblyInfo.cs` | keep | Checked against `PatchVersion` at build. |
| `KPM-PATCHES-README.txt`, `brand.png`, `favicon.ico`, `icons/` | keep | Embedded by `build_kmrp.ps1`. |
| `src/patcher/README.md` | document | Says NVIDIA is set and three options exist; section 3. |

### 1.2 Code paths left from before the KPM edition

Every place that writes `swkotor.exe`, and what else remains. Public releases: `v1.0.0` (2026-09-25) wrote gold; `v1.5.0` and `v1.5.1` install through `KpmEditionOperations` (read from the v1.5.0 tag). So the legacy upgrade path serves **1.0 installs only**, and development builds from before 2026-09-29.

| Entry | Verdict | Callers, every one |
| --- | --- | --- |
| `KpmEditionOperations.WriteCharacteristics` (one bit of `swkotor.exe`) | keep | `SetLargeAddressAware` 1251, 1254; `RemoveKpmRuntime` 823; `UndoEngineChanges` 1369. Live on CD and GOG. |
| `RemoveKpmRuntime` `File.Copy` over the executable (800) | keep | `Restore` 637, when KPM took over with only KMRP's patches. Live. |
| `PatchOperations.RestoreStandalone`, `FileGuard.Replace` of the executable (2336) | keep | `KpmEdition.cs:445` (install over 1.0), `:599` (restore of 1.0). `Test-ReinstallOverOlderBuild.ps1` covers it; `build/legacy/KMRP-standalone.exe` exists. Not dead. Gather into one legacy file, P4. |
| `InspectStandalone`, `DescribeStandalone`, `CanRestoreStandalone`, `TryReadInstalledResolutionStandalone`, `IsVerifiedPatchedInstall` | keep | All from `KpmEdition.cs`. Despite the name, `InspectStandalone` is also how a clean CD or GOG file is recognised. |
| `PatchOperations.WriteManifest` | change | Two callers, both `restored: true`. The `patched` branch and width and height are unreachable. Still writes `swkotor.exe.kotor-ui-patch.json` into a game folder after a restore. |
| `PatchOperations.ApplyToNewFile`, `WriteVerifiedFile` | move | `Program` `--apply` only. Writes a new file, never the game's. Used by `Test-LargeAddressAware.ps1`, `Test-MovieResolution.ps1` and by hand per `CONTRIBUTING.md`. |
| Embedded `Kmrp.engine.source`, step 2 of the build | move | Read only by `WindowsEnginePatch.BuildData`. `build_native_engine.py:69` calls `engine.build()` again, so the engine is assembled twice per build. |
| `PatchOperations.ApplyInPlace` two-argument form | change | `--in-place <exe>` only, 3440x1440. No test uses it. |
| `OverrideOperations.WriteManifest` | remove | No caller. |
| `RetiredKpatchNames`, `kmrp-movies`, `kmrp-map-notes` in `EnginePatches`, `KmrpFolder.Legacy` | keep | Read when restoring older installs. |
| `build_kmrp.ps1:506-508` removal of `dist\KMRP for KPM`, `dist\KPM patches` | remove | One-time clean-up from 2026-10-04 on the maintainer's own folder. Harmless. |

### 1.3 Repeats from `build/f4/dupes.txt`, read

| Repeat | Verdict | What it is |
| --- | --- | --- |
| `KmrpPatcher.cs:1094`, `1282` (168 tokens); `1201`, `1271` (67) | merge | The same `ImageAttributes` tint block in `DrawStatusArt` and `DrawIconMask`. |
| `KmrpPatcher.cs:2249`, `MainWindow.cs:726` (96) | merge | "Current size where covered, else the largest". Belongs in `ResolutionCatalog`, given the sizes. |
| `InstallCore.cs:1718`, `2364` (93) | change | **Not as alike as the name suggests.** Seven `SafeReport`: five swallow a callback's exception (`IniOperations`, `OverrideOperations`, `PatchOperations`, DPI, NVIDIA); `ControllerOperations` and `KpmEdition` do not. Three `SafeProgress`: two clamp to 0-100, `KpmEdition`'s does not. One helper means choosing. |
| `KmrpPatcher.cs:431`, `958` (69) | keep | `LoadLibraryEx` imports, one per class. |
| `ArtPreparation.cs:4`, `KpmEdition.cs:1` (67) | keep | `using` lists. |
| `ArtPreparation.cs:449-470`, `KpmEdition.cs:1403-1440` (126) | merge | `ModuleBytes` is `PatchModule` with `required` true. Make `PatchModule` internal. |
| `ArtPreparation.cs:383`, `KmrpPatcher.cs:2202`, `2228` (62, 57, 54) | merge | One `EnumDisplaySettings` loop in several places. One `DisplayModes()` iterator. |
| `InstallCore.cs:840`, `848`; `932`, `983` (57, 53) | keep | Inside `ResolutionPatch`; goes with P1. |
| `InstallCore.cs:2300`, `2330` (51) | merge | The same restore chain twice inside `RestoreStandalone`. |
| `KpmEdition.cs:820`, `1366` (50) | merge | Clear the 4 GB flag and verify it. |
| `KpmEdition.cs:797-809`, `1298-1318` | merge | Clear read-only, catch two exceptions, rethrow the in-use message. Found reading, not in `dupes.txt`. |
| `KmrpPatcher.cs:3260-3388` (169, 167, 91) | merge | The option rows. `AddOption(title, author, detail, get, set, column, top)`. |
| `InstallCore.cs:2724-2772` (128, 110) | merge | `KmrpSettings.Load`. `ReadBool(json, name, ref field)`. |
| `GuiBlend.cs:264`, `336`; `1285`, `1331` (131, 118) | keep | Table readers and reference drawing; P2. |
| `KmrpPatcher.cs:1343`, `1409` (97); `1009`, `MainWindow.cs:32` (94) | keep | Glyph drawing; two palettes in two toolkits. |
| `MainWindow.cs:413`, `460` (69) | keep | Pointer handling of two small Avalonia controls. |
| Three `HashBytes` (`GoldPatch`, `IniOperations`, `KpmEdition`) | merge | Not in `dupes.txt`. All give upper-case hex SHA-256. |
| `FolderOf`, `KmrpFolder.GameFolder`, and open-coded copies | merge | `Path.GetDirectoryName(Path.GetFullPath(...))`. |
| `JsonEscape`, `JsonString` | keep | Different: only `JsonString` handles control characters. |

### 1.4 `src/installer-linux`

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `Program.cs` | keep | Five commands over `PatchOperations`. |
| `MainWindow.cs` 1-519 views | keep | Avalonia controls; a toolkit-bound copy of the look, not of rules. |
| `MainWindow.cs` 520-1031 `MainWindow` | change | `Refresh` 746-822 and `UpdateGameStep` 823 follow `RefreshStatus` 4577 and `UpdateGameStep` 4523 in `KmrpPatcher.cs`. A core `InstallStatus` needs a line-by-line comparison I did not make. |
| `InstallPlatform.Linux.cs` | keep | Clean. |
| `LinuxDisplay.cs`, `SteamLibraries.cs` | keep | No regression test names either. |
| `KmrpLinux.csproj` | change | Compiles `WindowsEnginePatch.cs`, `GameArtGenerator.cs`, `AbilityIconGenerator.cs`, which the Linux program never calls, and `GuiBlend.cs` whole. |
| `fonts/` | keep | Carried for Avalonia, licences beside them. |

### 1.5 `tools/`

136 files at the top level, all tracked, plus `tools/xbox-manual-ocr`. 56 are named or imported from the build; three of those only by a comment or a message (`build_linux_installer.ps1`, `build_font_scale_sets.py` and its `build_font_from_ttf.py`). "Hand" means a maintainer runs it; "gold" means its input is a gold snapshot, kept only in the ignored `releases/3440x1440-gold-final`.

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `build_windows_engine.py`, `build_native_engine.py`, `kpm_relocations.py`, `verify_map_patch.py` | keep | Build. |
| Engine emitters imported by `build_windows_engine.py`: `build_font_scale_wrapper`, `build_gutter_side_fix`, `build_hit_test_center_fix`, `build_leading_newline_fix`, `build_letterbox_scale_wrapper`, `build_map_icon_draw_wrapper`, `build_map_note_table`, `build_minimap_fog_fix`, `build_minimap_split_candidate`, `build_minimap_zoom_fix`, `build_movie_aspect_fit`, `build_stack_count_fix`, `build_wrap_progress_fix` | document | Build, through their emit functions; each also keeps a `main` that patched a gold file. A name saying "candidate" or "fix" hides that they supply live code. |
| `build_native_kpatch.py`, `build_controller_kpatch.py`, `build_bundled_kpatch_config.py`, `kpatch_common.py` | keep | Build. |
| `kmrp_controller.py` | change | Build, tests, `testing/controller`. `installed_set` has no caller though its docstring names one. `kpm_patch_of` internal only. `KPM_PATCHES` and `kmrp-movies` still feed `build_native_kpatch.py:203`: live, misnamed. |
| `kmrp_pack.py`, `build_native_assets.py`, `source_fingerprint.py`, `prepare_sdl3.ps1` | keep | Build. |
| `pack_resolution_layouts.py` | keep | `macos/build.sh:174` runs it itself. Its step in `build_kmrp.ps1` has no reader, P6. |
| `prepare_universal_resources.py` and imports `analyze_resolution_guis`, `apply_gold_hud_proportions`, `derive_resolution_gui_set`, `fix_feedback_list_prototypes`, `fix_hud_menubg`, `menu_bottom_row`, `scale_hud_minimap`, `scale_listbox_padding`, `scale_message_popup`, `scale_row_icon_frames`, `transfer_gold_gui_geometry`, `build_menubg_texture` | keep | Build, step 3. 1,926 lines; a split is possible but it runs in no player's game. |
| `build_gui_blend_table.py` | keep | Build, Mac, tests. |
| Controller art: `build_controller_assets`, `build_controller_glyph_vectors`, `build_controller_layout`, `build_controller_prompt_textures`, `build_tab_arrows`, `build_xbox_hud`, `build_xbox_hud_art`, `controller_drawn_art`, `controller_glyphs`, `controller_layout_backdrop` | keep | Build, Mac, tests. |
| `build_original_fonts`, `build_scaled_fonts` | keep | Build, through `build_native_assets.py`. |
| `build_font_scale_sets.py`, `build_font_from_ttf.py` | keep | Hand: make `build/fonts`, which step 3 reads. |
| `build_live_layout.py`, `build_pc_hud.py` | keep | Hand, with a `--check` the tests run; write tracked tables. |
| `build_hd_original_fonts`, `build_hd_original_atlases`, `hud_font_geometry` | keep | Hand: redraw of the HD font. `Test-TextOptions.py` reads the first. |
| `build_hd_original_otf.py` | move | Docstring: superseded on 2026-10-22, kept as a record. Needs `potrace`, absent from `requirements.txt`. |
| `build_hd_fonts.py`, `build_kotor_font.py`, `export_glyph_templates.py` | move | 2026-08-29 and 08-30, the old HD font's route. `assets/hd-fonts` is still a step 3 input. |
| `build_linux_installer.ps1`, `build_linux_appimage.sh` | keep | Hand. `build_kmrp.ps1` writes their resource list. |
| `build_runtime_kpatch.py` | unverified | F11, decision open. The preview's packager; the build does not use it. |
| `check_controller_drift.py` | keep | Hand and `e2e_native_controller.py`; F6. |
| `check_kpm_overlaps.py` | keep | Hand, needs other authors' `.kpatch` files. |
| `check_hook_stolen_bytes.py` | change | Good check, run by nothing. Should run after every build. |
| `check_module_exports.py` | remove | Docstring names `kmrp-controller.module` and `Test-ControllerSupport.ps1`, both gone. `Test-ControllerKpatch.py` checks exports. Check first that `kmrp.dll` is covered too. |
| `check_override_conflicts.py` | remove | Reports what KMRP takes over in Override. Nothing written there since 2026-10-04. |
| `list_kmrp_changes.py` | change | Leaves `K1KpmApplier.cpp` unmarked because `K1RuntimeEngine.cpp:6` `#include`s it. |
| `audit_live_text`, `audit_native_text_paths`, `audit_transient_text`, `inventory_text_layout` | keep | Research, `docs/text-layout-inventory.md`. |
| `audit_controller_prompt_coverage.py`, `audit_generated_gui.py` | unverified | Last changed 2026-09-28 and 09-06. Not run. |
| `classify_controller_screens`, `controller_behaviour_matrix`, `extract_control_offsets`, `map_console_input_layers`, `map_gui_event_bindings`, `map_retained_gui_events` | keep | Research behind tracked tables and documents. |
| `measure_map_screen`, `dump_gui_extents`, `diff_gui`, `render_ui_tga_contact_sheet`, `texture_budget_report`, `collect_proton_report` | keep | Small utilities. |
| `export_tutorial_icons.py`, `scale_ability_icons.py`, `scale_tutorial_icons.py` | change | No longer build steps. `Test-GameArt.py` imports names from the first; the other two have no user. |
| `prepare_app_icons.py` | keep | Hand, when icons change. |
| `build_tab_screen_prompts.py` | remove | `build_controller_prompt_textures.py:222` says these were "previously generated" by it. |
| Gold chain: `build_area_fog_fix`, `build_click_fix_wrapper`, `build_large_address_aware`, `build_listbox_growth_fix`, `build_listbox_padding_fix`, `build_listbox_top_inset`, `build_marker_scale_fix`, `build_message_popup_size`, `build_movie_resolution_fix`, `build_minimap_zoom_wrapper`, `generate_gold_delta`, `kpm_originals`, `verify_universal_matrix` | move | Nothing runs them. They are the record of how sites were found, and the audit's "first named in" column points at them, so keep them until section 2 of the audit is done. |
| Candidates: `build_dynamic_map_surface_candidate`, `build_global_split_candidate`, `build_hit_test_y_candidate`, `build_hud_layout_candidate`, `build_hud_map_surface_candidate`, `build_hud_minimap_view_candidate`, `build_map_icon_candidate`, `build_row_scale_candidate`, `build_stock_render_domain_candidate`, `build_movie_letterbox` | move | Rejected or diagnostic candidates, 2026-08-29 to 09-14; `build_movie_letterbox.py` says "ABANDONED". Only `build_technical_reconstruction_doc.py` imports one. |
| `build_technical_reconstruction_doc.py` | move | Makes a history document; needs `python-docx`, not installed. |
| `build_binary_inventory.py` | change | Compares clean with gold. `AGENTS.md:126` still requires it; since 2026-10-01 a change goes into `windows-sites.json`. P9. |
| `kpm_data.py` | change | `Test-WindowsEngineSource.py` uses `parse`, `moved`. Its purpose, `kmrp-kpm.dat`, ended on 2026-10-04. Follows P1. |
| Release art: `build_before_after`, `build_brand_image`, `build_hotfix_art`, `build_release_cover`, `build_release_shots` | move | Hand. `macos/tools/make_package_art.py` uses the second. |
| One-off asset rewrites: `build_icon_tpc`, `build_menu_background_tpc`, `build_padded_minimap_atlases`, `fit_map_frame_art`, `strip_unused_tga_alpha`, `expand_lbl_map_frame.ps1` | move | Ran on tracked art; run by nothing. |
| `xbox-manual-ocr/` | keep | Rebuilds the manual PDF. Counted in the build cache today, P5. |

### 1.6 `build_kmrp.ps1` and root scripts

**How the cache works.** `Get-InputFingerprint` takes a SHA-256 over: each named file by content; each folder's non-Python files by path, size and write time; each Python file by parsed code without docstrings (`source_fingerprint.py`); plus extra text such as Python and pykotor versions. Stamps sit beside the output and are written only after success: `build/kmrp/resources/inputs.sha256`, `resolution-layouts.zip.inputs.sha256`, `build/native-runtime/kmrp-assets.pack.inputs.sha256`.

| Entry | Verdict | Evidence |
| --- | --- | --- |
| Fingerprints (158-194, 275-282, 336, 476-480) | change | Sound in method. Too wide: all of `tools/` recursively (`rglob`). P5. |
| Step numbering (68, comments 4a, 5) | change | `StepTotal` is 8 or 7, but the pool step is skipped when cached, so the count can stop short. Comment 5 is not a step. |
| Step 2, `windows-engine.bin` (263-266) | change | Only for `Kmrp.engine.source`. Goes with P1. |
| Step 4, layout pool (325-346, comment 403-409) | remove | `build/kmrp/resolution-layouts.zip` has no reader in any tracked file. `macos/build.sh:174` packs its own. Comment 404 names `GuiPool`, which does not exist. P6. |
| Step 4a, blend table (355-364) | keep | Not cached; content-hashed downstream. |
| `prepare_sdl3.ps1` at line 33 and in both module scripts | change | Runs three times per build, with `Expand-Archive -Force` each time. |
| Embedded licences `Kmrp.license.*` (385, 589, 592, 595) | document | No code reads them. I assume they are there so the licence travels in the file; say so. |
| `build_native_runtime.cmd`, plain `python` | change | Used three times. `build_controller_standalone.cmd` uses `KMRP_PYTHON` because vcvars can put another interpreter first (`build_kmrp.ps1:222`). Same risk, no guard. |
| The same, `findstr /x "9"` | change | A second copy of `ASSETS_VERSION = 9` in `tools/build_native_assets.py:74`. They agree today. |
| Fixed Visual Studio path `E:\Microsoft Visual Studio\...` | change | In 10 files. `build.local.ps1` covers Python and the texture pack, not this. |
| `src/kpm-runtime/build.cmd`, `README.md` | keep | Accurate. |
| `build_runtime_preview.cmd` | unverified | F11. |
| `build.local.example.ps1` | keep | Matches what `build_kmrp.ps1` reads. |
| `src/engine/windows-sites.json` | keep | Input of `build_windows_engine.py`. |

### 1.7 `testing/regression`, one row per test

Read, not run. "Current" means it reads code or output that exists today.

| Test | Verdict | Covers; still current? |
| --- | --- | --- |
| `Test-AbilityIcons.py` | keep | C helper against the C#, byte for byte. Current for the helper the module compiles; docstring wrongly says the installer runs the C#. |
| `Test-AssetPack.cmd`, `asset_pack_harness.cpp`, `asset_prepare_harness.cpp` | keep | Build the pack checkers. Current. |
| `Test-AssetPrepare.py` | keep | `KmrpPrepareAssets` as the installer drives it. Current. |
| `Test-ButtonRemap.py`, `button_remap_harness.cpp` | keep | `K1ButtonRemapPolicy.h`. `K1ButtonRemap.cpp` itself is not reached. |
| `Test-ClassModelTrace.py` | keep | `K1ClassModelTrace.h`. Current. |
| `Test-ControllerGlyphs.py`, `glyph_draw_harness.c` | keep | `draw_glyph` against the Python. Needs LLVM clang. |
| `Test-ControllerKpatch.py` | keep | The controller package. Current, 2026-10-30. |
| `Test-ControllerPreload.py`, `controller_preload_harness.cpp` | keep | Preload worker. Default `--game` is the Steam folder. |
| `Test-ControllerPromptAssets.py` | keep | F9. |
| `Test-DpiCompatibility.ps1` | keep | Writes per-user DPI values for fixtures, removes them. Current. |
| `Test-DriverCompatImports.py` | keep | K1DC routes. Current. |
| `Test-FontAtlasScale.py` | unverified | Reads `gui-*.zip`, last changed 2026-09-24. Windows ships fonts from the pack and fits them at run time (`FitAtlas`), so it may not pin what ships. |
| `Test-GameArt.py` | keep | As `Test-AbilityIcons.py`. |
| `Test-GeneratedGuiGeometry.py` | document | Reads the archives. Since `2a12c80` the 73 live-layout screens in them no longer ship on Windows; the archives stay for tests and the Mac. Say so. |
| `Test-GuiAudit.py`, `gui_audit_model.py`, `GuiAudit-allowlist.json` | keep | F8. Exits 1 by design. |
| `Test-GuiBlendHelper.py` | keep | Needs the C# through `--derive-gui`. Follows P2. |
| `Test-GuiModelPreload.py` | keep | Current. |
| `Test-HudOptions.py`, `hud_options_harness.cpp` | keep | Policy headers and the HUD table. `K1HudOptions.cpp` itself is not reached. |
| `Test-InstallerPatch.ps1` | keep | The main install test, 11 cases. Current. Borrows real settings; not run. |
| `Test-KmrpLayoutPatch.py` | keep | Mac only. Holds Mac values against its own Python `windows_value`, not against C# or the module. |
| `Test-KpatchSource.py` | keep | `KMRP.kpatch`. Docstring stale. |
| `Test-LargeAddressAware.ps1` | change | LAA install and restore current. Its `--apply` cases compare the reference only. P1. |
| `Test-LiveLayout.py` | keep | Current. |
| `Test-MacAppStore.py`, `Test-MacAssets.py`, `Test-MacFullscreen.py`, `Test-MacGuiNavigation.py`, `Test-MacInstaller.py`, `Test-MacKpmOwnership.py`, `Test-MacMemorySafety.py`, `Test-MacNavigationTrace.py`, `Test-MacOptionsNavigation.cpp`, `Test-MacStatusSummary.cpp`, `Test-MacTextHeight.py` | unverified | Mac side. Read for shared paths only. |
| `Test-MiniGameFire.py`, `mini_game_fire_harness.cpp` | keep | Slices the production block. |
| `Test-ModCompatibility.py` | keep | Current. |
| `Test-MovieResolution.ps1` | change | Last changed 2026-09-06. Checks two of the three movie pairs (no `0x3EAD`, `0x3EB9`) and only `--apply`'s output. P1. |
| `Test-NativeAssetsBank.py` | keep | Current. |
| `Test-NativeTextLayout.py`, `native_text_layout_harness.cpp` | keep | Current. |
| `Test-NvidiaPresentMethod.ps1`, `NvidiaPresentSelfTest.cs` | keep | Removal of the old value. Comments at 49, 53 describe an Override step that is gone. |
| `Restore-TestNvidiaProfiles.ps1` | change | Looks for `KMRP_NVIDIA.manifest`; that name left on 2026-10-20 and no install writes a record since 2026-10-30, so that branch looks unable to fire. `Hide-KpmLauncherSettings` is live. |
| `Test-OverrideFontMetrics.py`, `override_font_metrics_harness.cpp` | keep | Current. |
| `Test-PartyRosterFixture.py`, `Build-PartyRosterFixture.py` | keep | Local fixture, needs the third-party package. |
| `Test-PartyRosterGui.py`, `party_roster_gui_harness.cpp`, `party_roster_controller_harness.cpp`, `party_roster_runtime_harness.cpp` | keep | Current. |
| `Test-PazaakActions.py`, `pazaak_actions_harness.cpp` | keep | Current. |
| `Test-ProtonResourceCompatibility.py` | change | Case checks on `gui-*.zip`. What Proton reads now is the pack and the module's cache. Point it there. |
| `Test-ReinstallOverOlderBuild.ps1` | keep | The only test of the 1.0 path. Not run. |
| `Test-ResolutionDerivation.py` | keep | `derive_resolution`, still step 3. |
| `Test-RuntimeKpatch.py` | unverified | F11. |
| `Test-RuntimeResolution.cmd`, `.cpp` | unverified | F11. Reads a DLL of 2026-10-04. |
| `Test-SwoopPrompt.py`, `swoop_prompt_harness.cpp` | keep | F7. |
| `Test-TextFitPolicy.py`, `text_fit_policy_harness.cpp` | keep | Current. |
| `Test-TextLayoutRows.py`, `native_text_layout_rows_harness.cpp` | keep | Current. |
| `Test-TextOptions.py`, `text_options_harness.cpp` | keep | Current. Whether it expects three font styles: not checked. |
| `Test-TextRows.py`, `NativeTextRowsHarness.cpp` | keep | Current. |
| `Test-UpdateCheck.ps1`, `UpdateCheckSelfTest.cs` | keep | Current. Source-list comments stale. |
| `Test-WindowsEngineSource.py`, `WindowsEngineSelfTest.cs` | change | The Python half is good: determinism, relocations, guards. The scaling half tests `ResolutionPatch`, which no player runs. P1. |
| `Test-WindowsKeyboardNavigation.cmd`, `.cpp` | keep | Current; F13 applies. |
| `Test-Xpress.cmd`, `.cpp`, `.py` | keep | Current. |
| `native_helpers.py` | keep | Used by two tests. |
| `testing/controller/` | unverified | Live-game probes, outside one-row scope. `Test-SdlBackend` is the only test naming the SDL path. |
| `testing/virtual-display/`, `testing/GuiAudit-*`, `gold-geometry-diffs.txt` | keep | Dated records and support. |
| No runner | change | Nothing runs the set. `AGENTS.md`, `WORKFLOWS.md` and `testing/README.md` each list a different subset. CI runs `compileall` and links only. |

**Left in no test (a name search, so a place to look).** Per-size operands in `K1RuntimeEngine.cpp` and `K1KpmApplier.cpp`; `K1OffscreenFrame.cpp` (named only in NVIDIA comments), `K1MovieWindow.cpp`, `K1Rumble.cpp`, `K1CursorConfinement.cpp`, `K1PopupFit.cpp`, `K1PcHud.cpp`, `K1HudOptions.cpp`, `K1ButtonRemap.cpp`, `K1PartyPortraits.cpp`. In the installers: `InstallClock`, `BuildStamp`, `GameFolders`, `ResolutionSelection`, `LinuxDisplay`, `SteamLibraries`, `FileGuard`, and `ResolutionCatalog` except through an install. `IniOperations` and `OverrideOperations` are reached only by whole installs.

### 1.8 Documents as a set

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `docs/README.md` | document | Eight documents missing, rows stale. Section 3. |
| `reverse-engineering/README.md` | document | Two documents missing; `movies.md` row says four operands. |
| `docs/agent-memory/README.md` | document | Routes install work to `KmrpPatcher.cs`. |
| `docs/agent-memory/PROJECT.md` | change | Says the build in progress is 1.5.0; predates the 2026-10-30 split. |
| `docs/agent-memory/WORKFLOWS.md` | change | Contradicts `build_kmrp.ps1` on `dist\controller`. |
| `docs/documentation-standard.md` | keep | The standard. Its kind rule is unevenly followed: 43 documents state no kind in their first lines (a text search). |
| `docs/kpm-edition.md` | keep | Current first, record after. `GoldPatch.ApplyToOriginals` is in the dated part. |
| `docs/patcher-ui-build.md` | change | Most of it measures the 2026-10-01 installer, corrected by a table at its top. A rewrite is due. |
| `docs/windows-engine-source.md`, `docs/universal-resolution-math.md`, `docs/font-scaling.md` | document | Good dated notes; class locations moved. |
| `docs/ingame-text-options.md` | change | Three font styles; two since 2026-10-31 (`CHANGELOG.md:225`). |
| `docs/controller-support.md` | document | Marks its own stale paragraphs. Long. |
| `docs/cleanup-audit-1.6*.md` | change | The two disagree on counts. |
| `docs/history/`, `docs/handoffs/`, `reverse-engineering/experiments/` | keep | Dated records. |
| `reverse-engineering/*.md` as a set | keep | Dated notes on where bytes are written now, as the index says. Sampled, not every line read. |
| `reverse-engineering/exe-patching.md`, `binary-inventory.md` | document | Rules written for gold; `AGENTS.md` still routes there first. |
| `CONTRIBUTING.md`, `SECURITY.md` | document | Paths; section 3. |
| `AGENTS.md` | document | Line 126. |
| `CLAUDE.md` | keep | Accurate. |

### 1.9 Repository hygiene (described, nothing touched)

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `src/controller-native/*.obj`, `*.exp`, `*.lib` (12 files) | remove | Ignored, dated 2026-10-03 and 10-04, output of `build.cmd`, removed 2026-10-04 (`c6096f5`). Local only. |
| `src/controller-native/kmrp-controller.module` | remove | Same: 251,904 bytes, ignored, 2026-10-04. |
| `.gitignore` | keep | The `third_party` allowlist is sound. Comments at 145-148 say "gold bakes"; 197-200 can go once the files do; 40 is out of date. |
| Root `grep.exe.stackdump`, `docs/grep.exe.stackdump`, `K1DriverCompat.ini`, `swkotor.ini`, `.spec-render/` | remove | Ignored strays. `.spec-render` is empty. |
| `logs/` in the root | unverified | Ignored, numbered folders up to 2026-11-01. Writer not traced. |
| `assets/override-3440x1440/*.gui.bak` (16) | keep | Ignored hand-edit backups. |
| `src/installer-linux/bin`, `obj` | keep | Ignored build output. |
| `backup-pre-email-rewrite`, `backup-pre-msg-rewrite`, `backup-pre-vdd-purge` | document | Local only, 2026-09-04, 141 to 144 commits not in master: history from before the rewrites `AGENTS.md` describes. |
| `hd-icons` | document | 2026-10-08, also on origin, one commit ahead of master, 116 behind. |
| `save-editor-history` | document | 2026-10-23, local, 7 ahead, 448 behind. Work moved to the KMSE repository. |
| `stash@{0}`, 2026-10-16 | document | Autostash on `6d93283`, 14 files, 583 insertions: the swoop and turret work (`0x00670FB0`, `NativeMiniGameAxisK1`), which is in master as hook 21. Not compared hunk by hunk. |
| master against origin | document | 5 commits ahead of `origin/master`. |

### 1.10 Other folders

| Entry | Verdict | Evidence |
| --- | --- | --- |
| `font-converter/` | keep | **At the root, not `src/font-converter`** as the brief and memory say. Tracked, 41 files, builds alone. Missing from `docs/README.md`. |
| `src/` otherwise | keep | `controller-native`, `engine`, `installer-linux`, `kpm-runtime`, `patcher`. |
| `third_party/Included/*`, `Fonts`, `lzma-sdk`, `aurebesh-font` | keep | Each used by the build or a named tool, per `.gitignore`'s notes. `Vanilla Maps HD (K1)` and the two zips are untracked. |
| `third_party/Kotor-Patch-Manager` | keep | Submodule on KMRP's fork, branch `kmrp`. |
| `THIRD_PARTY_NOTICES.md` | document | Fonts section (481-520) describes the old atlases, checked 2026-09-24. NvAPI section says "sixteen" identifiers, 12 after P3. |
| `requirements.txt` | change | Missing `potrace` (`build_hd_original_otf.py`) and `vgamepad` (`testing/controller`). Otherwise matches the imports. |
| `macos/tools/*.c`, `*.h` | document | Not Mac-only: `kmrp-guiblend`, `kmrp-abilityicons`, `kmrp-gameart`, `kmrp-swoophud`, `kmrp-guiadapt`, `kmrp-merge`, `kmrp-glyphs` compile into the Windows modules. The folder name hides the most-shared code in the project. Moving it touches the Mac's build, so it waits for the Mac side. |
| `macos/build.sh:169`, `macos/README.md:735` | document | Both say the Windows installer embeds the pool. Not since 2026-10-04. |
| `archive/`, `releases/` | keep | Records; `archive/README.md` says the build uses nothing there. |

## 2. Proposed changes

Each changes no game behaviour unless it says so. Risk in the installer is covered by `Test-InstallerPatch.ps1` and `Test-ReinstallOverOlderBuild.ps1`, which borrow the real settings: warn the maintainer first.

### P1. Take the reference code out of both installers
- **What.** Move `ResolutionPatch`, `WindowsEnginePatch`, `AbilityIconGenerator`, `GameArtGenerator`, `ControllerPromptGenerator` to `testing/reference-cs/`, compiled only by the tests that need them. Remove `--apply`, `ApplyToNewFile`, `WriteVerifiedFile`, `Kmrp.engine.source` and build step 2. Drop them from `KmrpLinux.csproj`.
- **Then replace the test.** Run `resolution_fields()` through the real arithmetic of `K1RuntimeEngine.cpp`, in a compiled harness, at the 66 sizes plus 640x480, 1919x1079, 3457x1453, and hold the result against what `Test-WindowsEngineSource.py` asserts today. Add `0x403EAD`, `0x403EB9`.
- **Why.** Three copies of the sites (C#, Python table, Mac `resolution_sizes.cpp`), and the tested one is not the one that runs. `resolution_fields` appears in no test. About 2,030 lines leave the shipped files.
- **Risk.** None to the game: none of it runs in an install. The risk is to the Mac's comparisons and `build_binary_inventory.py --installed`.
- **Sure:** `proven` for the callers; `needs a check` that the Mac side does not use `--apply` by hand, and whether `ControllerPromptGenerator.TryBuild` is wanted at all.

### P2. Split `GuiBlend.cs`
- **What.** Keep table reading, `Terms` and `Covers` (about 550 lines) in the core. Move `Derive` and its drawing to `testing/reference-cs/`, with a small test driver in place of `--derive-gui`.
- **Why.** The installer asks it one yes or no.
- **Risk.** A size accepted or refused differently if cut wrongly. **Test:** `Covers` over a grid of sizes before and after, and `Test-GuiBlendHelper.py`.
- **Sure:** `likely`; check how much of `Read` `Terms` needs.

### P3. Remove what has no caller
`NvDrsSession`: `FindProfile`, `CreateProfile`, `AddApplication`, `SetDword`, their delegates and four entry points. `DarkCombo` and its branch at 3790. `MainForm.UseDarkScrollBars`. `DriverCompatOperations.Version`. `ResolutionChoice.Blended`, `Relabel`. `IniOperations.Describe`. `OverrideOperations.WriteManifest`. `GuiBlend.SetFilesNeeded`, `Describe`. `LightField` timing fields. `InstallCore.cs` unused usings (`Microsoft.Win32`, `System.ComponentModel`, `System.Diagnostics`, `System.IO.Compression`, `System.Runtime.InteropServices`: no use found by search). `PatchOperations.WriteManifest`'s unreachable branch. `kmrp_controller.installed_set`. Update the NvAPI count in `THIRD_PARTY_NOTICES.md`.
**Risk:** none to the game; fewer fetched functions makes a restore fail less. **Test:** build, `Test-NvidiaPresentMethod.ps1`. **Sure:** `proven` by search and reading; the compile confirms.

### P4. Split the three big installer files, in this order
1. **Make the list of sources one list first.** It exists six times: `build_kmrp.ps1:413-425`, `KmrpLinux.csproj:29-42`, `Test-NvidiaPresentMethod.ps1:46-63`, `Test-UpdateCheck.ps1:38-53`, `Restore-TestNvidiaProfiles.ps1:10-16`, and a glob in `Test-WindowsEngineSource.py`. Use folders: `src/patcher/core/` compiled by both installers, so the compiler enforces the header's "no WinForms" rule, and `src/patcher/windows/`.
2. **`core/`:** `GameExecutable.cs` (40-239), `ResolutionCatalog.cs` (241-444), `IniOperations.cs`, `FileGuard.cs`, `KmrpFolder.cs`, `DriverCompatStandalone.cs`, `KmrpSettings.cs`, `UpdateCheck.cs`, `BuildStamp.cs`, `InstallClock.cs`, `KpmInstall.cs`, `KpmRestore.cs` (with takeover), `PatchConfig.cs`, `OwnedFiles.cs`, `KpatchDelivery.cs`, and **`LegacyInstalls.cs`**: `PatchOperations`' standalone members, `OverrideOperations` and the runtime half of `ControllerOperations` in one file, so what serves 1.0 upgrades can be seen and one day dropped together.
3. **`windows/`:** `Program.cs`, `GameFolders.cs`, `DpiCompatibility.cs`, `NvidiaPresentRemoval.cs`, `DriverCompatProbe.cs`, `ArtPreparation.cs`, `UiTheme.cs`, `Controls.cs`, `OptionToggle.cs`, `ScrollViews.cs`, `MainForm.cs` with partials `.Layout`, `.Scaling`, `.Header`, `.Status`, `.Operations`.

**Rename** `GoldPatch` and `ExecutableState.Gold`; change the `PatchVersion` regexes in `build_kmrp.ps1:431-433` and `tools/build_linux_installer.ps1` and `AssemblyInfo.cs:25` in the same commit.
**Why:** "no monolithic big structures". **Risk:** none in intent. **Test:** compare each class's compiled IL before and after, as F4 did with instructions; both installers build; the two install tests. **Sure:** `proven` for the mapping, `likely` for the `MainForm` partials, whose fields are shared.

### P5. Narrow the build cache
Fingerprint only what the build reaches: move the rest out of `tools/` (P7) and make `source_fingerprint.py` use `glob`, not `rglob`, or list the files. **Why:** no long rebuild for a research script. **Risk:** a stale step if a real input is left out, the worst failure a cache has. **Test:** import each build root, list `sys.modules` from `tools/`, compare with the list; change one file on each side and watch the stamps. **Sure:** `likely`; dynamic imports need that check.

### P6. Remove the pool step from `build_kmrp.ps1`
Lines 325-346. `pack_resolution_layouts.py` stays. **Risk:** none on Windows. **Test:** full build; Mac build still packs. **Sure:** `proven` for tracked files; `needs a check` that no local habit reads the zip.

### P7. Sort `tools/`
Keep build tools where they are, as tests and the Mac put `tools/` on `sys.path`. Move out: `tools/history/`, `tools/research/`, `tools/release/`, `tools/assets-once/`. Add `tools/README.md`. `list_kmrp_changes.py` must glob the history folder. Do it after audit section 2, whose list points at these names. Backticked tool names need a sweep; `check_links.py` sees only links. **Sure:** `likely`.

### P8. Small installer merges
The `merge` rows of 1.3. For `SafeReport` and `SafeProgress`, take the swallowing, clamping versions and decide that a throwing report does not stop an install: today a throw inside `KpmEdition` reaches the rollback. **Test:** the two install tests. **Sure:** `proven` for identical text, `needs a check` for that one.

### P9. Make the executable check fit the source recipe
`build_binary_inventory.py` should read `build_windows_engine.assemble()` instead of a gold file, so `AGENTS.md:126` can be followed. **Sure:** `likely`; `Test-WindowsEngineSource.py` already holds the inventory's 68 runs against the recipe.

### P10. Build scripts
`KMRP_PYTHON` in `build_native_runtime.cmd`; one `prepare_sdl3.ps1` per build; `ASSETS_VERSION` read once; `VC` from `build.local.ps1` or `vswhere`; correct step count. **Test:** a build, and compare module hashes (`/Brepro`). **Sure:** `proven` as faults.

### P11. A test runner
`testing/Run-Regression.ps1` with named sets (quick, needs-build, borrows-settings, Mac), running `check_hook_stolen_bytes.py` too, replacing the three differing lists. **Sure:** `likely`.

### P12. Local tidying, for the maintainer's hand
Delete the ignored strays in 1.9. Decide on the `backup-pre-*` branches, `hd-icons`, `save-editor-history` and the stash.

## 3. Where documents are wrong or missing

A dated record stating its date is not listed.

| File and line | Says | Reality |
| --- | --- | --- |
| `docs/agent-memory/WORKFLOWS.md:53-54` | `dist\controller` not written by `build_kmrp.ps1` | It is, `build_kmrp.ps1:526-534`, since 2026-10-08. |
| `docs/agent-memory/PROJECT.md:41` | Build in progress is 1.5, installer 1.5.0 | 1.5.1 tagged 2026-10-12; 1.6 in progress. |
| `docs/agent-memory/PROJECT.md:14-22` | Options `map-notes`, `debug-logs`; module embeds every resolution's files | `hd-icons` too; art pack beside the module since 2026-10-19. |
| `docs/README.md:60` | NVIDIA method "set for `swkotor.exe`", "when it is written" | KMRP sets nothing since 2026-10-30; its own document says so. |
| `docs/README.md:37`, `docs/ingame-text-options.md:297,348,580,632,678` | Three font styles | Two since 2026-10-31, `CHANGELOG.md:225`. |
| `docs/cleanup-audit-1.6-findings.md:19` against `cleanup-audit-1.6.md` sections 2, 2.2 | 89 runs, 57 operands | The list has 87 and 59. Both sum to 146. |
| `docs/cleanup-audit-1.6-findings.md:21` | 80 source files | The list's section 4 has 72 rows. |
| `docs/cleanup-audit-1.6-findings.md:65-66` (F3) | `check_patcher_hook_table.py` needs one export per dispatcher | Removed 2026-10-04 (`c6096f5`). `check_controller_drift.py` holds a hook-to-export check. |
| `src/patcher/README.md:23` | Sets NVIDIA's present method | Removed 2026-10-30. |
| `src/patcher/README.md:24-27` | Three optional components | Seven tiles since 2026-10-19 (`KmrpPatcher.cs:3224`). |
| `docs/patcher-ui-build.md:23,869` | `--in-place`: runtime, DPI, NVIDIA, INI | NVIDIA is removal only. |
| `testing/README.md`, `Test-NvidiaPresentMethod.ps1` row | "when it writes" | It tests removal only. |
| `testing/README.md`, `Test-MovieResolution.ps1` row; `reverse-engineering/README.md:37` | Four movie operands | Six since 2026-10-20. |
| `docs/controller-prompt-specification.md:644,652` | `build_tab_screen_prompts.py` regenerates the textures | Replaced, `build_controller_prompt_textures.py:222`. |
| `tools/build_windows_engine.py:6` | Installer specialises the template | Only `--apply` does. |
| `build_kmrp.ps1:404,408` | `GuiPool`; pool built for `--derive-gui` and the Mac | No such class; no reader. |
| `AbilityIconGenerator.cs:9`, `GameArtGenerator.cs:10`, `ControllerPromptGenerator.cs:10-14` summaries | Run at patch or install time | No caller. |
| `Test-AbilityIcons.py:3-5`, `Test-GameArt.py:4-6` | The Windows installer does this with the C# | The module does, with the C helpers. |
| `Test-KpatchSource.py` docstring | Module is 189 MB, stored | 0.7 MB, deflated, since 2026-10-19 (`KpmEdition.cs:1399`). |
| `KpmEdition.cs:111-114` | K1DC through `DriverCompatOperations`, left to KPM; NVIDIA settings | Changed 2026-10-30 and 10-31. |
| `InstallCore.cs:2556-2558` | Resolution checklist fields | Removed 2026-10-07. |
| `macos/build.sh:169`, `macos/README.md:735` | Windows installer embeds the pool | Not since 2026-10-04. |
| `THIRD_PARTY_NOTICES.md:483-489` | Rendered atlases, 49 archives | As of 2026-09-24; KMRP's own OFL fonts since 2026-10-22. |
| `.gitignore:40` | A stackdump sat in the root until 2026-10-05 | Two exist now, ignored. |

**Moved class, old file** (`KmrpPatcher.cs` until 2026-10-30, `InstallCore.cs` since): `SECURITY.md:83`, `CONTRIBUTING.md:154`, `docs/font-scaling.md:180,184,198`, `docs/universal-resolution-math.md:371`, `reverse-engineering/exe-patching.md:146,156`, `reverse-engineering/listbox-geometry.md:108,298`, `reverse-engineering/font.md:233`, `src/patcher/README.md:21`, `docs/agent-memory/README.md:15`, `docs/agent-memory/MEMORY.md:41`, `docs/agent-memory/PROJECT.md:100,105-107`, `Test-KmrpLayoutPatch.py:13`, `Test-AbilityIcons.py:44`, `Test-InstallerPatch.ps1:105`. `ArtPreparation` moved to its own file: `Test-AssetPrepare.py:7`, `asset_prepare_harness.cpp:1`, `Test-InstallerPatch.ps1:161`, `Test-ReinstallOverOlderBuild.ps1:162`. (`MEMORY.md:41` and `exe-patching.md:146,156` were read only as search hits.)

**A rule for a method that no longer exists.** `AGENTS.md:126`, `CONTRIBUTING.md` (the build_binary_inventory step, ending line 132) and `docs/agent-memory/WORKFLOWS.md:119-136` tell an engine change to diff a final gold snapshot. Changes have gone into `src/engine/windows-sites.json` and the emitters since 2026-10-01. `CONTRIBUTING.md:139` half says so, below the instruction.

**Named things that no longer exist**, outside records: `Test-KpmEdition.ps1` (`docs/linux-appimage-installer.md:224`, written after its removal), `Test-ControllerSupport.ps1` (`tools/check_module_exports.py:10`, `testing/README.md` narrative), `Test-InstalledOverride.ps1` (`docs/agent-memory/MEMORY.md:177`).

**Not indexed.** `docs/README.md` lacks `live-adaptive-layout.md`, `controller-live-adaptive-layout.md`, `linux-appimage-installer.md`, `mod-file-inventory.md`, `macos-app-store.md`, `windows-handoff-2026-10-09.md`, `cleanup-audit-1.6.md`, `cleanup-audit-1.6-findings.md`, and `font-converter/`. `reverse-engineering/README.md` lacks `override-font-metrics.md` and `party-roster-compatibility.md`.

**Missing.** A `tools/README.md`. A clear statement that the C# generators are reference code only; `docs/kpm-edition.md:178` is the nearest. The purpose of the embedded `Kmrp.license.*`.

## 4. What I could not verify

- **No test's pass or fail.** Nothing was run. `Test-InstallerPatch.ps1` and `Test-ReinstallOverOlderBuild.ps1` were read only.
- **Mac tests:** only names, dates and references were read.
- **Whether the Mac side uses `--apply` or the C# generators by hand.** No tracked script does.
- **`MainWindow.Refresh` against `MainForm.RefreshStatus`:** similar in outline, not compared line by line.
- **`Test-FontAtlasScale.py`, `audit_controller_prompt_coverage.py`, `audit_generated_gui.py`:** whether they still mean anything against today's output.
- **`Test-TextOptions.py`:** whether its font list expects three styles.
- **`reverse-engineering/` line by line.** Paths, names and the index were checked, and a sample read.
- **`docs/agent-memory/MEMORY.md` in full.** A few references only.
- **`logs/`:** who writes it. A size scan did not finish; a read-only `du` may still be running in the background.
- **The cost in seconds of steps 2, 4 and 4a.** Not timed.
- **The stash:** which hunks landed.
- **Reflection on C# names:** none seen, but a search cannot prove there is none. P3's compile will not catch it either, so run the install tests.