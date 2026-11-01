> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# First pass: controller input and GUI hooks (saved from the agent's reply; to be verified)

24 entries: keep 8, change 10, document 5, merge 1. All 24 stolen byte runs match the clean exe; jump-into scan: 3 hits, all not real paths.
Keep: 0x00407235, 0x00409E60, 0x0040C1F6, 0x0040C8E0, 0x005E30F6, 0x00670FB0, 0x00686BA0, 0x006C2400.
Document: 0x005E24E0, 0x005E271E, 0x006039CF, 0x00679940, 0x00679B71. Change: 0x00404D96, 0x00409B80, 0x0040CE70, 0x0040CFAB,
0x006E0CF0, five chargen. Merge: 0x0068B170 into 0x0040CFAB.
Pairs: 0x0040CE70/0x0040CE76 no; 0x00404D96/0x00404D06 no; 0x0040CFAB/0x0040CF70 no (KMRP's entry before base vtable written; controller's gates need it);
0x0040CFAB/0x0068B170 yes for one object.

## Proposals
- P1 HUD preload: same as kmrp report P1 BUT moving the call is UNSAFE: without controller KmrpPreloadHudPagesK1 falls through to 0x00423A60 and
  CAurTexture::Bind (0x004214B0), and movies run on their own thread (started 0x00405E07, movies.md:692). CONTRADICTS the kmrp report's fix. Keep queue branch at
  movie site; run no-controller branch from the GUI frame, or drop it. Check: GL context on movie thread?
  Also call sat in CoreMovieFrameK1 (80f9277^ K1NativeJoystick.cpp:2717) never installed.
- P2 split NativePanelReleaseGffK1 (K1NativeJoystick.cpp:2800-2846): load half and forget half; both hooks run all 12 calls. KmrpXboxHudForgetK1, K1GuiModelPreload::Forget at both.
- P3 ClearActionBarControlsK1 called from NativePanelDestroyedK1; remove 0x0068B170 and REQUIRED_LEGACY; patch 37 hooks. Crash test: load over loaded game. likely.
- P4 one GuardChargenConfirmK1 export for 5 hooks. tidy only; F3's reason (check_patcher_hook_table.py, removed 2026-10-04) wrong either way.
- P5 kNothing 0x7FFF -> K1_GUI_EVENT_INERT 0x41 (:2271,2279).
- P6 name inline blocks in NativeGuiFrameK1 (:7427-7467, :7408-7420).
- P7 KmrpControllerGuiMovieK1 per frame: clears wchar_t[32768] (64 KB) and GetFileAttributesW beside KMRP (via KmrpPreloadGuiPathK1) each GUI frame. Cost unmeasured.
- P8 (a) ReadNativeStickK1 :7948 diagnostic, 8 PollInput per gameplay frame with logs off; (b) NativeJoystickDumpK1 from two hooks; (c) EnsureDeviceCountK1 etc in both, do not remove.
- P9 ClicksOnConfirmK1 :2322, RaisedOnPanelK1 :3648-3662 share a walk.
- P10 One hook table per patch: rows in kotor1.hooks.toml, kotor1-native-runtime.hooks.toml, eight dicts in build_controller_kpatch.py; 7 legacy rows nothing installs; 0x0040B8F0 row removed by builder;
  select_controller_path.py installs a module no longer built; exports.def (68 names) no build user.
- P11 K1MovieWindow.cpp out of controller module; only tracking and armed used.

## Docs wrong
F3; K1NativeJoystick.cpp:2206-2207,2378; :2196 + kotor1.hooks.toml:259-260; :2472-2473; CHANGELOG 597-599; kotor1.hooks.toml:536-539 + K1NativeJoystick.cpp:2951-2960 (movement hook writes nothing);
kotor1.hooks.toml:555-556; controller-native-path.md:41,44; hooks.toml:609-610, native-path:616-618; hooks.toml:1170-1172 + K1NativeJoystick.cpp:2531-2533 (also swallows keys: KmrpNoteKeyboardK1 input->value=0);
hooks.toml:30-33, build_controller_kpatch.py:15-17, kpm-edition.md:733-739; build_native_kpatch.py:112-115; build_controller_kpatch.py:157-158; hooks.toml:957 + :2546; kmrp_controller.py:58;
K1NativeJoystick.cpp:3819-3821, retained-xbox-gui-events.md:157,258; controller-standalone.md section 2 (0x0040C8E0); K1NativeJoystick.cpp:7373-7374, :7930-7931 (ApplyLeftStick reachable only through hook no build installs), :2006-2011;
cleanup-audit rows 1,5,10,25 "what it is for" text is the legacy hook's at that address (list_kmrp_changes.py picks wrong row); 0x0040B8F0 has three names.

## Unverified
GL context on movie thread; whether GUI update 0x00603C9B runs each frame Control runs; reentries>1 in GuardChargenConfirmK1 unreachable?; 0x006FA220 in K1_OWN_CONFIRM_DISPATCHERS;
Scaled Kotor stolen length at 0x0040B8F0; KPM preserves flags at 0x0040C1F6 (je at 0x0040C1FB reads earlier flags); no hook cost measured.
