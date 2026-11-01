> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass MEM (saved from agent's reply). No Critical or High. Nothing run.

MEM-01 MEDIUM strongly suspected, low: LooksLikePointerK1 ceiling 0x7FFF0000 below LAA addresses: K1EngineMemory.h:37-41, K1NativeJoystick.cpp:969; DescriptionPresentK1:925 uses 0xFFFF0000. CD/GOG have LAA. Silent feature loss, pad dead if CExoInput high. Fix ceiling 0xFFFF0000 one helper; LiveStickInputK1 call it.
MEM-02 LOW confirmed stale read: g_stick.hudInterface outlives HUD: K1NativeJoystick.cpp:2901,:7728-7730; K1XboxControls.cpp:7246. One-line zero in NativePanelDestroyedK1 or ClearActionBarControlsK1.
MEM-03 LOW confirmed from code: failure branches on _s calls cannot run: KmrpOptions.h:32,43,58,60,87; K1KpmApplier.cpp:97,101,105,142,318; K1RuntimeAssets.cpp:333; K1ControllerBackend.cpp:145-146. Folder over ~220 chars crash at first log. Fix path-join helper.
MEM-04 LOW theoretical: KPM writes 74 detours on Steam with game running: patcher.cpp:66-79,314-323, trampoline.cpp:52-66. Report upstream.
MEM-05 LOW theoretical: Apply rollback omits failed read-back run: K1KpmApplier.cpp:590-598.

Verified safe: KPM contract PUSHAD/PUSHFD/FXSAVE; lead 0x0040C1F6 closed; esp+N all handlers; position-dependent bytes; 7 byte-scan jump hits none real; five eax exclusions; replace stub 0x0046BE64; ABI 123 pairs zero real mismatches; overlaps only 0x005F0C64 with unapplied site; g_popup not UAF (global panel); g_mainInterface; cue tables; panels/strings maps; keyboardPanel; comparisons only; g_sabers ids; g_stick.input; buffers all 23 unbounded calls safe; copied vtables; Xpress, pack, Gff; applier guards, block protect, no heap under suspend; CommitEngineAt; HotPatch 2-byte; movie thread stack.
Disagree: K1HudOptions.cpp:899-903 Bind branch not live today.
Unverified: addresses above 2 GB; Steam exe flags; main during load-module movies ReadControllerK1; setView; Steam suspended thread return address inside run; glyph arrays index K1TextLayout.cpp:187,890, K1XboxHud.cpp:1752 for fonts under 256; FitAtlas K1RuntimeAssets.cpp:827; vtable call signatures beyond samples; recipe runs vs hook sites beyond KPM check.
Docs wrong: K1NativeJoystick.cpp:7724-7726; K1KpmApplier.cpp:605; KmrpOptions.h.
