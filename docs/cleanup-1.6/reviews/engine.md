> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# First pass: engine recipe and run-time writes (saved from the agent's reply; to be verified)

160 rows: keep 142, remove 5, change 6, document 5, unverified 2. All 87 guards match the clean exe. Real counts: 87 runs + 59 operands (146).
Findings doc :19 says 89/57: wrong. kmrp.dll applies 85 (build_native_engine.py:72 leaves out 0x005F0C65, 0x005F0C6F), 847 bytes; 79 with original-movie-mode.
All 59 operands keep. Not duplicates (checked): FitMessageBoxK1 vs popup operands; KmrpListRowK1 vs gutter runs; KmrpTextStringWrapK1 vs wrap runs (hook leaves native body);
K1PcHud vs minimap runs; #63-69 one job at separate sites; Live Layout depends on #7-12.

Verdicts not keep: remove #29 0x0045A850, #30 0x004A1770, #31 0x005F0C65, #32 0x005F0C6F (with --apply), #87 0x00755788. change #38 0x006256FC, #43 0x0068C4E3, #78 0x006C2704, #84 0x006DE08E, #85 0x006DE0D1.
document #14 0x00417992, #26 0x0045A3B7, #27 0x0045A3DC. Section 3: row 1 change, 3 unverified, 5, 6 document, 8e unverified.

## Proposals
- P1 remove #29, #30: .kfs Draw and TextOutA stubs multiply metrics by 1.0 at 0x0086F000 on every text draw (build_windows_engine.py:198), no field writes it. Also removes the
  one RWX page. Files: src/engine/windows-sites.json, build_windows_engine.py:198-207,251, build_native_engine.py:79, build_font_scale_wrapper.py, WindowsEnginePatch.cs:53,199,210,
  Test-WindowsEngineSource.py (page length, 46 relocs, 457 instr, 68-run assertion). proven. Hook 0x0045A857 stays.
- P2 remove #87: float 0x00755788: five readers 0x006A74E0, 0x006A7572, 0x006A7951, 0x006A7B6A, 0x006A7F4F all inside bytes #63-66, #68 replace. map.md:399 it made another mod's check refuse. proven.
- P3 applier file format leftovers (table): DllMain #ifndef 649-674, InstalledFeatures 338-378, IsCoreCopy 624-635, ReadFileBytes and kmrp-kpm.dat 315-336,402-406, header checks 407-477,
  FNV 413 recomputed at K1RuntimeEngine.cpp:123, payload copies, Edit list. Emit plain tables. Keep guard check, thread pause, rollback, VanillaImage, reloc proof. Merge with kmrp report P3.
- P4 movies feature bit always on (K1RuntimeEngine.cpp:108), g_moviesOff always false, KpmMoviesOffK1 constant per module. Keep bits 8, 4.
- P5 DECISION for maintainer: --apply. FieldValue/resolution_fields (shipped) vs ResolutionPatch (C#, 545 lines InstallCore.cs, only --apply and self-test). Test-WindowsEngineSource validates the C#
  twin; shipped FieldValue has NO test. Option b recommended: test FieldValue at every size, remove ResolutionPatch, WindowsEnginePatch.cs, --apply, Kmrp.engine.source, KMRPSRC1 template, kpm_originals.py.
  Costs: Test-LargeAddressAware.ps1, Test-MovieResolution.ps1, AGENTS.md line, build_binary_inventory.py --installed.
- P6 #38,#78,#84,#85: assemble() records old==new, build_native_engine.py:92-99 replaces by VA. Put real bytes in Recipe.site.
- P7 #43: fixed compare 3440 picks mipc210x7 only at width 3440, others mipc28x6. Docs wrong. Check difference between the two files before changing.
- P8 wglMakeCurrent patch maybe unneeded; needs debug counter with K1DC on/off.
- P9 Does start size write arrive in time on Steam? module loads 460-500 ms, after code decrypted (332) and window (352); kpm-edition.md:503 another run 913 ms. Check ini with absent size on Steam.
  Same for K1OffscreenFrame.cpp:380.
- P10 optional: packing block (5,761 of 45,056 bytes), kpm_originals.py, main() of build_*_fix.py.

## Docs wrong
findings:19; audit:179 + binary-inventory.md:100, windows-engine-source.md:54, third-party-driver-compat.md:341 (85 applied); audit:343-344 (:620,:621; slot name CSWGuiSkillFlow vs Ability Chain);
CHANGELOG.md:103, binary-inventory.md:472, build_technical_reconstruction_doc.py:520 (fixed 3440); binary-inventory.md:482; CHANGELOG.md:65, :99, :83; windows-engine-source.md:81; binary-inventory 5.2 dated;
font.md:85 (CSWGuiButton::SetStyle); K1RuntimeResolution.cpp:215 (0x005F5AB0); K1TextRows.cpp:47,67; kpm_relocations.py:4-13,38; build_windows_engine.py:6; InstallCore.cs:520-524; macos/WINDOWS-PARITY.md:195.

## Unverified
K1DC's calls (source absent); Steam load timing; Proton hot-patch form; load order KMRP/K1DC on SwapBuffers slot; reconstruction coverage for P8; mipc210x7 vs mipc28x6 diff; CenteringWidth in C#; #26,#27 firing today.
