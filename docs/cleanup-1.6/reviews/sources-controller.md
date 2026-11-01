> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# First pass: kmrp-controller.dll sources (saved from the agent's reply; to be verified)

43 entries: keep 22, change 15, document 3, remove 2, move 1. Dead = not in generated exports, absent from linker map, unreachable by identifier walk from 49 exports + DllMain
(scripts ctl_outline.py, ctl_reach.py, ctl_dead.py, ctl_globals.py in scratchpad). Big files read about a third; structure otherwise.
Keep incl: K1ControllerBackend.h, K1ButtonRemap(.cpp/.h/Policy), K1Xpress.cpp, K1MovieWindow.h, K1CursorConfinement, K1StatusSummary.cpp (two passes each frame documented), K1PartyPortraits, K1EngineMemory.h,
KmrpOptions.h (guard line 100 the one real guard), K1Rumble.h, K1ControllerLayout.h, K1ClassSelectArt.h, K1GuiModelPreload.h, K1GuiPreloadData.h, K1PartyRosterState.h, BadgeShapes.inc, XboxHudLayout.inc, K1HudOptionsPolicy.h, K1RuntimeAssets.h.

## Biggest
- 2,030 function lines of vendor/K1XboxControls.cpp and 411 of K1XboxControlsXInput.cpp not in DLL (old keystroke path). Only 6 of 22 functions reachable in XInput, about 70 lines.
- vendor/ not vendor: 86% of live function lines are KMRP's; upstream third_party/Included/KPM-Xbox-Controls-K1-1.2 holds no source. KMRP-CONTROLLER-MODULE.diff stale since 5a33864.
- F9 does nothing: DIK_F9 read only at K1XboxControls.cpp:5865 inside unhooked CaptureActionBarInputK1; docs/controller-support.md:389 and comment 683-685 claim it. Decide.
- K1ClassModelTrace.h writes game vtable slot 0x00752E68 in normal play (lines 19, 155-158), and 0x00758054 at debug level 2 (15): missing from audit section 3.

## File maps
K1NativeJoystick.cpp: 20+ jobs, table of line ranges in agent's text: engine tables 1-654; StickState 655-903; EnsureNativeJoystickK1 904-1316 (289 lines); FillNativeJoystickBufferK1 1317-1862 (532 lines);
stick 1863-1996; rumble 2014-2153, 2404-2456; confirm guards 2154-2403; movie/key notes 2457-2544; FrameTimingK1 2545-2799; panel hooks 2800-2850; HUD/camera 2851-2960; nav tables, cues, lookups 2961-3310;
remaps 3311-3566, 3817-3992; echo/release 3567-3816; cues 3993-4432; family 4433-4756; Pazaak 4757-5085, 5149-5243; class select 5086-5148, 5244-5383; Pazaak setup incl rasteriser 5384-6201; navigation 6202-7275;
menu snapshot 7276-7362; NativeGuiFrameK1 7363-7478; deferred actions 7479-7790; movement 7791-8037; dump 8038-8212; minigame 8213-8340; swoop 8341-8455.
g_stick 112 fields, 60 counters; groups: sample, requests, repeat timers, registration, family. Never written: classRetriesTaken, overrideFrames, deviceCountDeferred. Written never read: verbsBound, buttonsBound, lastNavTick, padStateAllocated, lastX, lastY.
Text readers of this file: kmrp_controller.py:40, check_controller_drift.py:248,328, list_kmrp_changes.py:67, Test-PazaakActions:10, Test-SwoopPrompt:16-18, Test-MiniGameFire:16, Test-GuiAudit:587.
K1XboxControls.cpp: live jobs: prompts 714-1800 + 4083-4244 + 5335-5406; drawn pictures 1801-2863; badge overlay 2864-4082 (ShowK1BadgeOverlay 382 lines); cursor 5116-5334, 7258-7389; action bar 5491-5790; NoteKeyboard 6233-6336; native entries 6337-6564.
dead: 4245-5115, 5407-5490, 5791-5825, 5848-6216, 6565-6703, 6732-7245, 7390-7437. stubs 7438-7455.
K1XboxHud: 50-420 helpers, 421-605 fonts, 609-905 table/placed, 927-1320 layout, 1321-1513, pause 1515-1863 + 2640-2680, 1867-2455, 2460-2633 lists.
K1ControllerLayout: lifecycle 97-187, four badges 189-585, remap editor 587-1472, refresh 1474-1624, predraw 1627-1721, frame 1723-1775.

## Proposals
P1 remove keystroke path (needs maintainer yes: #if 0 comment asks to keep design; git keeps it); harness party_roster_controller_harness.cpp, Test-ControllerPromptAssets:269 asserts dead PollMovieControllerK1, audit_controller_prompt_coverage.py:135 reads dead GetK1SettingsStripExit.
P2 cut XInput to device state K1InputDevice.cpp. P3 IsControllerGeneratedKeyK1 always false (6275). P4 F9 decide. P5 always-true guards (15 in vendor, 2 Backend); harness compiles without define (Test-PartyRosterGui:150, harness:12).
P6 retire 7 legacy hooks in kotor1.hooks.toml, exports.def, select_controller_path.py, kmrp_controller.py leftovers (2.6: 104-111, 121-127, 177-185, 130-149 reshape, 53-62, 242-285 stale); check_controller_drift.py:39 default path gone.
P7 rename vendor/ (licence credit stays). P8 split K1NativeJoystick in 9 ordered steps (1-7 no logic change, compare; 8 g_stick groups, 9 big functions need play; testing/controller reads dump keys). P9 unused constants list. P10 split vendor after P1.
P11 split K1XboxHud. P12 split ControllerLayout. P13 share HUD table: says comment calls copy deliberate (CONTRADICTS kmrp report: comment does not say so). P14 small repeats list (PressDefaultK1 onto PressListedButtonK1 proven, Utf8Path).
P15 one font reader, five readers (K1GuiControls controlTextWidth, K1CaptionInk CaptionWidth, K1XboxControls MeasureK1CaptionByFont 3051, K1XboxHud FontOfLabel/WideIn 435-463, K1ControllerLayout lastReplyLine 324), sums differ on purpose.
P16 move production path out of trace header. P17 one home for addresses (list of 21 addresses named more than once; rule 3). P18 117 hand-written prototypes in .cpp: real headers (wrong extern C signature uncatchable).

## Not proposed: merging KmrpOptions guard, FindK1MenuPanel with FindK1TitleMenuPanel. Real vs look-alike repeats table in agent's text: real 5500/5513, 3490/3546, 1079/1095, 5076/6192 (wider), XboxHud 1369/2196, Layout 239/486/553, 1530/1536/1542, vendor 2385 etc cap only (range check differs), Utf8Path, stale cache; look-alike 4036/6234, 343/500, 1423/1597, all K1Rumble data.

## Docs wrong: README.md:13-14,20-84,65,90,100,103-105,108-111,131; THIRD_PARTY_NOTICES.md:205,216-223; NOTICE.txt:65; hooks.toml:12-13,16-18,28-33; controller-support.md:166-167,389; controller-native-path.md:301-311;
controller-live-adaptive-layout.md:203-204,509-510; kpm-edition.md:733-739; K1Xpress.h; K1StatusSummary.h; comments vendor 77-94, 683-685, 6221-6241, K1NativeJoystick 83-90, 112-138; prompts.cpp:138.
## Unverified: only third of big files read; harness needs; other readers of hooks.toml; size of data left in DLL.
