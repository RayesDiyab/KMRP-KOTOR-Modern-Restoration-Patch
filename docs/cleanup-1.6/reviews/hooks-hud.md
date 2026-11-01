> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# First pass: rumble and HUD hooks (saved from the agent's reply; to be verified)

Verdicts: keep 0x005F74B0, 0x005FB49F, 0x005FB98E, 0x0060DE20, 0x00617EB0, 0x0063C4F0, 0x00646BA0,
0x006D4440, 0x0068947A, 0x006C02A4; bundled 1.3 to 1.5 keep, no shared site. Move 0x005F7617 to
K1Rumble.cpp. Change 0x00685ED0 and 0x0068AB10 (split). Unverified 0x006C00C0.
All 14 sites' stolen bytes match the clean exe. No two rumble hooks do one job:
play/cutoff differ (cutoff sees lookups past BioWare's cutoff), hit/parry differ (parry has callers
0x006186F0 and 0x0061A934 via 0x00617470; agent did not name those events).
0x00689410 KmrpXboxHudStealthK1 replaced by 0x0068947A KmrpXboxHudListsK1 in e634603.
K1 Marked Empty Containers at 0x00685E69: cooperates, K1XboxHud.cpp:2175 calls UpdateNameLabel.

Sizes today: KmrpXboxHudK1 482 lines, 364 code, 23 steps, 7 jobs (layout swap, screen rules, target
menu, combat, action row, party, pause); KmrpXboxHudBarsK1 160 lines, 136 code, 4 jobs.

## Proposals
- P1 remove EnsureRumbleTableK1, RumbleEnvelopeK1, RumblePatternK1, K1_INTERNAL_RUMBLE_TABLE(_COUNT)
  (K1NativeJoystick.cpp:2014-2153), KmrpBioWareRumbleRowK1, engineHeavy/engineLight, K1Rumble.cpp:1293-1295,
  dump raw= rtab=. Why: NativeRumblePlayK1 returns 1 on all paths so 0x005FB4A5 on never runs; queue append
  0x005FB4E2 past the hook; UpdateRumble reads table only in queue loop 0x005F75B5. "proven" by agent. VERIFY.
- P2 move NativeRumbleK1 into K1Rumble.cpp using KmrpPadPresentK1; rejoin comment K1NativeJoystick.cpp:2155-2188.
- P3 split the two HUD functions into named steps, same order; helper for start-layer sequence at
  1381, 1416, 1494, 2202; remove wasBorder (1425-1427,1436), inset, trim (1488). Needs in-game compare.
- P4 PauseNotice inline font read (1732-1752) and width loop (1794-1811) use FontOfLabel, WideIn. One diff:
  height 0 font.
- P5 test build without 0x006C00C0 and g_pauseStripped; needs film of paused fight; needs KPM reinstall.
- P6 remove LoadSettings() from saber, contact, hit, parry, muzzle hooks; unread Positional::cutoff; second
  include K1EngineMemory.h K1Rumble.cpp:36 (mine, from F4 script).

## Doc errors
release-1.6-progress.md:50 (old hook); controller-rumble.md:97 (40 ms vs 80, K1Rumble.cpp:1206), :98 and
K1Rumble.cpp:515 (never merge), :165 (eight vs nine), :177-179 + K1NativeJoystick.cpp:2106-2110, K1Rumble.cpp:1293,
K1Rumble.h:27-29 (impossible fallback); K1Rumble.cpp:25 (pause mutes, not freezes), :329, :409 (old places),
:48 ("generated", no generator); K1NativeJoystick.cpp:2206 and F3 cite check_patcher_hook_table.py, removed
2026-10-04, and KPM allows shared functions (KmrpListRowK1 has three sites): F3's reason wrong; F12's 361/133;
K1XboxHud.cpp:33 ("one hook", five), :345-347, :217-225; controller-xbox-hud.md:143, :241.

## Unverified, leads for the behaviour pass
- High FPS Fixes compiled code not read.
- Motors during a movie: UpdateRumble callers 0x00603DAB, 0x004B8393; a motor running as a movie starts may hold
  on XInput until it ends.
- g_sabers never cleared, StopAll does not reach it; lit blade before a load may resume hum.
- Whether a shipped script calls StopRumblePattern.
- No test named the mixer's tick (five identifiers searched).
- RestorePauseNotice tests for the picture; g_pauseStripped may hide the box on pad-to-mouse.
