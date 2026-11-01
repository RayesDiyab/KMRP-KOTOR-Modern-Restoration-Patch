> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass MAC (saved from agent's reply). Nothing run on a Mac.

Facts: Windows PE x86 32-bit MSVC thiscall; Mac game Mach-O x86_64 SysV under Rosetta; modules x86_64 only; little-endian both. Offsets do not scale (LBL_MAPBORDER 0x5CC0 vs 0x7640; ExoString 8 vs 16; HandleInputEvent +0x3C vs +0x80). Pending Mac PR no longer pending: none open, no Mac branch. KPM route built: needs --kpm with newer tree.

MAC-1 LOW confirmed: submodule pin 2a784bf cannot build (build.sh:11-14,27,249-252). Move fork's kmrp branch pin past 7546ae5 + options.
MAC-2 MEDIUM confirmed: _stricmp K1ButtonRemapPolicy.h:56. Local ASCII compare. Build fix only.
MAC-3 MEDIUM confirmed: K1HudOptionsPolicy.h:72-82 keys on Windows offsets, Mac sliders ignored silently. element column generated in both tables.
MAC-4 MEDIUM suspected: kmrp-guiadapt.c:450-466,478 FP contraction on arm64 tests; add #pragma STDC FP_CONTRACT OFF; K1PcHudLayout.h:58.
MAC-5 MEDIUM confirmed mechanism: make_controller_assets.py:84,87 assign shared.CARRY_DRAWN (rename silently empties Mac bank); 14 names cross modules through GetModuleHandleW; dlsym RTLD_DEFAULT finds nothing on Mac. Pass flags as arguments; one peer lookup header KmrpPeer.h.
MAC-6 MEDIUM confirmed: format logic bound to wide paths K1RuntimeAssets.cpp:1148-1440; UTF-8 KmrpModPipeline over 6-function file layer (issue 81).
MAC-7 LOW confirmed: K1TextOptions.cpp:31,62 Fn(unsigned): uintptr_t.
MAC-8 MEDIUM confirmed: prompts.cpp:138 prompt_table.py absent; 42 Mac tables, 172 rows vs 47; one tag table generating both.

Other assumptions: wchar_t keys K1HudOptionsPolicy.h:63-66; K1EngineMemory.h:16 windows.h for plain templates; Mac has 8 At/Field and 2 Readable copies; case of resource names theoretical; .sh .c .cpp no gitattributes rule, LF in index.

Proposals effect: Before port: P9 kmrp-keyed.h (beside sources, size limit param, static inline; Test-GameArt.py:229 -Werror), P10 kmrp-image.h, P18 K1EngineScale.h (no windows.h), P8/P13 K1XboxHudTable.h (types header, then caller's table, then arithmetic; .inc by name unusable), Union move, P17 Rect/addresses/prototypes helps most, vendor retire (cites), installer P1,P2 once Test-AbilityIcons.py:32, Test-GameArt.py:51 fixed. K1OptionsPage.h only behind Fn/Native seam. Hurts if new .c: P21 guiadapt split (breaks build.sh:112-113, make_kmrp_patch.py:90, build_native_assets.py:79, cmd, Test-LiveLayout:596-599, kmrp-mac.sh:859). Name controller split files after Mac's (native, gameplay, gui, cues, prompts, overlays, hud, layout).
Do NOT remove as unused on Windows: CARRY_DRAWN, CARRY_CUED, --controller-art, --mac, pack_resolution_layouts.py, kmr?rt_pause, K1OptionsPad.h file (overlays.cpp:65, build.sh:218). Keep src/patcher/brand.png, icons (build.sh:454-456). Keep in tools: pack_resolution_layouts, build_gui_blend_table, build_xbox_hud, build_controller_assets.
Generated in step: xbox_hud_layout.inc with K1XboxHudLayout.inc; K1ControllerBadgeShapes.inc; gui-blend.bin; K1ListRows.inc with list_rows.inc; add build_live_layout.py --check to build.sh.
Handoff stale: items 99, 60, 76, 59, 87, 67, 130, 64, 56, 102, 126, 112. Also WINDOWS-PARITY.md:62, build.sh:11-14, native_helpers.py:5-8.
Dup measured: 7,610 Mac lines, 2,340 same (31%); saving about 1,230 by runs (16%), max 1,580. First lift K1Rumble.cpp:49-321, 812-862 into K1RumblePatterns.inc, 253 lines identical. Portable headers another 1,590, K1RuntimeAssets 400 after MAC-6.
Verified safe: K1AssetPack bytes only; (float)(h/720.0)==(float)h/720.0f; RoundEven == nearbyint default; K1ClassSelectArt; K1PartyRosterGui; LF in index; no Mac test reads Windows sources by name; K1HudOptions.cpp:83-84 does not say deliberate.
Moving macos/tools to neutral folder: "now or never": no open PR.
