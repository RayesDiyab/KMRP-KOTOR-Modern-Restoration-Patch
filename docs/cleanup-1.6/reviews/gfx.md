> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass GFX (saved from agent's reply). Nothing run.

GFX-01 HIGH, code path confirmed, link strongly suspected: fixed 1600x1200 black rect on screen DC in full-screen rebuild: game 0x00401A30 initCinematicBackdrop started from ReInitAurora 0x00403885; CreateWindowExA class "Knights Cinematic Backdrop" but registered "KotorCin" (0x00401A8E), wndproc 0x00401590 returns 0: NULL; GetDC(NULL); PatBlt(0,0,1600,1200,BLACKNESS) 0x00401B71. Vanilla followed with real mode change; KMRP rebuilds at same mode. Candidate cause of issue 91 and closed 39. Shares: 83% 1080p, 52% 1440, 46% 3440. Fix: first measure in issue 39 screenshots (1600x1200 top left); recipe run je->jmp 0x00401B09. Check nothing relies on curtain.
GFX-02 MEDIUM very low, confirmed path: hot patch live before real pointer: K1OffscreenFrame.cpp:371-377. Fix: set real first.
GFX-03 MEDIUM strongly suspected: K1DC wraps KMRP at SwapBuffers, reverse of docs (K1OffscreenFrame.cpp:21-24,117,317; third-party-driver-compat.md:314-316). Test brightness slider with AA8 + K1DC. Correct comments. resolves load order.
GFX-04 HIGH if it happens, likelihood unknown; theoretical failure, confirmed missing check: no check blit worked, no off switch (K1OffscreenFrame.cpp:336-345, line 15). glGetError after first Show + Refuse, hand-set ini key. AMD/Intel runs AA 0,4,8.
GFX-05 LOW confirmed by reading: drawnOffscreen ignores binding K1OffscreenFrame.cpp:350-360.
GFX-06 LOW: ReadPlain resolves whole frame K1OffscreenFrame.cpp:199; measure first.
GFX-07 LOW: g_k1SceneFills never pruned (same as THR-5): K1XboxControls.cpp:2314,2323,2397,2610.

Issue 91: offscreen not in 1.5.1; GFX-01 lead; ask primary res, version, block top left 1600x1200.
Issue 89: symptoms unknown. 1.6 cautions: movies GDI separate window not captured by GL hook; tool patching opengl32 first makes offscreen turn off (log only), flash returns on layered present.
Issue 78: 1.5.1, GOG, 7800XT, 165 Hz. No cause shown. Lead: 1.5.1 HighFpsFixAuto above 60 Hz (KmrpPatcher.cs:4839) + K1DC 1.2.0: add High FPS off, 60 Hz to test matrix.

Verified safe: GL state restored; hot-patch arithmetic; context rebuild; pixel format; game pbuffers; no depth reads; second SwapBuffers site; CorrectHardwareMipmapsK1; ReadUploaded; Preload restore; frameTime 0 with High FPS (0x1153,0x17A7); rumble dt; quiet frames count frames; drawn pictures per-run temp; buckets; Marked Empty Containers EAX; Party Roster; K1CP; Scaled Kotor conflict declared. Hook overlap all five tables 0 collisions.
Supports engine P8 (wglMakeCurrent branch not needed by game; K1DC unknown).
Docs wrong: K1OffscreenFrame.cpp:42,:380,:21-24,117; third-party-driver-compat.md:315,:424,:447,:484,:492; no warning kpatch K1DC route unseen with offscreen frame: Steam test folder still runs standalone route!
Disagree P9: 2026-11-01 logs read "before its window" at 758-997 ms.
Unverified: K1DC swap function; BinkCopyToBuffer DIB; AMD, Intel, Proton offscreen; CD/GOG with offscreen; Steam overlay; AurTextureGetReference cost; info K1MovieWindow.cpp:127.
macOS: not portable: hot patch, import slots, WGL, wglGetProcAddress, pbuffers, NVAPI, DWM, GDI movie, Bink DIB. Portable idea: offscreen frame, ink from pixels, drawn-picture files.
