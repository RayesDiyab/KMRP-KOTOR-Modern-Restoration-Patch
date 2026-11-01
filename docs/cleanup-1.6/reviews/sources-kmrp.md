> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# First pass: kmrp.dll sources (saved from the agent's reply; to be verified)

68 rows: keep 30, change 29, document 5, remove 4. Keep (no change): K1PartyRosterGui, K1KeyboardNavigation,
K1GrantedPopup, K1AssetPack, K1PopupFit, K1StatusSummary, K1CursorConfinement, K1PartyPortraits, K1CaptionInk,
K1TextOptionsPolicy, K1TextFitPolicy, K1PartyRosterState, K1SliderGrip, K1EngineMemory, K1AssetPack.h, K1TextLayout.h,
K1TextRows.h, K1PartyRosterGui.h, K1MovieWindow.h, K1StatusSummary.h, K1CursorConfinement.h, K1ListRows.inc (maintainer's
copy, compared by Test-KpatchSource), K1PcHudLayout.inc, K1XboxHudLayout.inc, kmrp-merge.c, kmrp-2da.h, kmrp-path.h,
kmrp-livelayout-table.h, kmrp-glyphs.c (#included by kmrp-guiblend.c:248), LzmaDec.c.

## Proposals
- P1 BEHAVIOUR: KMRP alone never preloads HUD page textures. Only KmrpMovieFrameK1 calls KmrpPreloadHudPagesK1, only the
  controller calls that (K1NativeJoystick.cpp:2472-2480). CHANGELOG.md:597-599, K1HudOptions.cpp:873 claim otherwise. Since d2a3b54.
  Fix: call from KmrpCoreMovieWorkK1, delete export (K1HudOptions.cpp:874, build_native_kpatch.py:236) and GetProcAddress block.
  Call graph proven; slow first opening needs game check. 0x00404CB5..0x00404CE8 not read.
- P2 dead: KmrpRuntimeGuiPiecesK1, KmrpGuiPiece, Gff::resref; KmrpSetTextPreferencesK1; KmrpRuntimeEngineReady;
  KmrpRuntimeLayoutDirectory; kmrp.dll's KmrpRuntimeAssetDirectory; g_requested; Entry::advanced; K1PcHud Key::operator==;
  RegisterFolder's again (false at 1951,1954,1955); set in AdaptGalaxyMapK1 (1291), AdaptMainMenuK1 (1325); list of ListWider (375);
  crypt32.lib in build_native_runtime.cmd:71. proven.
- P3 K1KpmApplier.cpp (#included by K1RuntimeEngine.cpp:6, not "neither module"): dead InstalledFeatures, IsCoreCopy, ReadFileBytes,
  #ifndef DllMain, kmrp-kpm.dat branch. Split Apply (225 lines). LogLine folder walk 97-107 to KmrpOpenLog. about 250 lines fewer.
- P4 F11: Test-RuntimeResolution: 18 cases of one range check in the 2026-10-04 DLL; expectations are NOT today's module answers
  ({1237,813,1}, {5120,1440,1}, {32767,32767,1}). Today's DisplayReports, EnumModesOnce, WriteSize, KmrpStartAtDisplaySize,
  ReloadFontMetrics, Prepare, KmrpResolutionObservedK1: nothing automated. Plan: new resolution_harness.cpp including today's
  K1RuntimeResolution.cpp with mocks; check Test-KpatchSource rejects wrong parameter; THEN remove preview cmd, toml,
  build_runtime_kpatch.py, Test-RuntimeKpatch, Test-RuntimeResolution, #ifdefs (13,51,60,101,202,297,305,328,338-347),
  K1RuntimeEngine.cpp:3-5, K1TextLayout.cpp:780,785, K1ControllerBackend.cpp:4,187. Keep conflict IDs.
- P5 REAL GAP: controller's folder registration lacks KMRP's 2026-10-30 non-code-page fix (K1ControllerStandalone.cpp:201,209,231 vs
  K1RuntimeAssets.cpp:631). User name outside code page: false, registered stays false, nothing logged, failed false too, every later
  hook call reruns LeaveLayoutsToKmrp, CueScreens. New K1ResourceFolder.h. Gap proven; effect needs check.
- P6 temp cleanup K1TempFolders.h; KmrpUtf8Path in KmrpOptions.h (third copy K1ControllerPreload.cpp:33); K1Sha256.h.
- P7 options toolkit: K1OptionsPage.h template, table of line pairs; constraint text_options_harness swaps through Fn/Native. Medium risk.
- P8 Xbox table/Placed: K1HudOptions.cpp:86-93 copy of K1XboxHud.cpp:620-635, 96-118 repeat Scale (315), Placed (879-905).
  NOT documented as deliberate: F12's statement is wrong. K1XboxHudTable.h, PlacedBox. Union from K1PcHudLayout.h to policy; Grow 417-424, K1XboxHud.cpp:1009-1014.
- P9 keyed_resource three copies (kmrp-guiadapt.c:87-129, kmrp-swoophud.c:104-146, kmrp-gameart.c:449-496). gameart's has no bound on
  file table entry, name_offset, BIF name, reads whole BIF. kmrp-keyed.h. 4 MB limit vs tutorial.2da unmeasured.
- P10 resize identical gameart:305, abilityicons:100, tga/write_tga; iconsize dup. kmrp-image.h. Held byte identical to C#.
- P11 K1RuntimeAssets split table; MoveIntoPlace at 1308,1344,1394,1427; KmrpRuntimeDimensions at 1746. harnesses #include whole cpp.
- P12 K1RuntimeLayout split; list_kmrp_changes.py:59-61 looks by name.
- P13 K1TextLayout split; FNV twice 150,817.
- P14 HudOptions preview split, MakeScreen 202 and 188 lines.
- P15 K1TextRows repeat 365-373/385-391; KmrpTextRowsK1 137 lines.
- P16 stale comments commit.
- P17 one Rect (six definitions) and SetExtent (vtable slot called by hand in 8 places).
- P18 half-even rounding three copies K1EngineScale.h.
- P19 K1OptionsPad.h 197-223 repeats K1UniformBadge, placing (K1XboxControls.cpp:3258,3306); use controller export. K1ControllerBadgeShapes.inc leaves.
- P20 OriginalFont written, never read.
- P21 guiadapt/guiblend splits, ll_layout 220 lines, guiblend main 410 lines; KmrpGuiBlendCovers ~ KmrpGuiBlend. lowest priority.
Order: P2, P16, P4 steps 1-2, P1, P5, P6, P8, P9, P18, P17, P3, P7, then splits.

## Docs wrong (selection)
F4 (:83) ReadViewport VirtualQuery K1RuntimeResolution.cpp:36-41 is a read check, unmerged; F11 "resolution exports" one export;
F12 "deliberate" not so; README.md:13-14,20-84; features-technical.md:17-18; K1KpmApplier.cpp:1-66; K1RuntimeEngine.cpp:1-2,84-87;
K1OffscreenFrame.cpp:9-12,42; hooks.toml:55-57; nvidia-present-method.md:13,120, kpm-edition.md:66 name deleted K1RuntimeNvidia.cpp;
ingame-text-options.md:406-407,604; K1MovieWindow.cpp:163,182; exports.def not linked, lists removed names, kmrp_controller.py:45 reads it.
kmrp-gameart.c:6 and abilityicons:6: GameArtGenerator.cs, AbilityIconGenerator.cs maybe dead (installer review).

## Unverified
Whether preview still compiles; dupes.txt lists only top runs (40 of 129, 20 of 154) and no C helper; KmrpLiveLayout callers.
