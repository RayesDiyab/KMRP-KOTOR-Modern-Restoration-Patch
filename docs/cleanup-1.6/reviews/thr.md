> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass THR (saved from agent's reply). Costs estimated, nothing run.

Settled P1: neither first-pass fix site right. No GL context on movie thread (23 wglMakeCurrent 0x00425C03..0x0044EBED; closure from ThreadProc 0x00405B30, 141 functions, no opengl32 import, 31 indirect not followed). Correct site KmrpCoreGuiWorkK1.

THR-1 MEDIUM confirmed: KMRP alone never preloads HUD textures; K1HudOptions.cpp:874,880-906, K1NativeJoystick.cpp:2472-2481, K1CoreFrames.cpp:116. Even beside controller real Bind only in GUI frames (K1ControllerPreload.cpp:153-172); main spins in WaitForMovie. Skipped movies: no HUD preload. Fallback also on movie thread beside older controller module lacking KmrpQueueTexturePreloadK1. Slow first opening 363-427 ms. Fix: call KmrpPreloadHudPagesK1 from KmrpCoreGuiWorkK1 with wglGetCurrentContext check, two per frame, early return; delete export (build_native_kpatch.py:236), K1NativeJoystick.cpp:2472-2481.
THR-2 HIGH low likelihood, confirmed by reading: failed preparation repeats all work on every lookup/frame: K1RuntimeAssets.cpp:1724-1738; K1ControllerStandalone.cpp:372-394,244-248,175-196; K1XboxControls.cpp:2288-2308,2676-2686. KMRP: failure after Initialize repeats fonts, 73 layouts per GetKeyEntry, new roster-<pid>-<n> folder each (1926-1937). Pack missing: two ini reads each lookup. Controller alone with user path outside code page: CueScreens per lookup, effectively hang (traces P5). Disk full Unpack each frame. Pictures no failure memory. Fix: one latch per module, retry on new size, remember failed names, Unpack stored failure. 
THR-3 MEDIUM confirmed path: bad_alloc on bg threads kills game: K1XboxControls.cpp:2204-2207, K1RuntimeAssets.cpp:1790-1812. Fix try/catch.
THR-4 MEDIUM confirmed: game thread blocks on buildLock for known size: K1RuntimeAssets.cpp:1743-1751,1790-1800; Covers in IsValidResolution for each mode, each may wait a build (7-9.5 s). Fix: small lock for known.
THR-5 MEDIUM confirmed, cost estimated: picture sweep linear in 4 lists per border per frame, two only grow: K1XboxControls.cpp:2744-2784,2321-2329,2094-2104,2007-2015,2314. 0.4-2 ms per frame, largest item. Fix: hash maps; skip unchanged.
THR-6 MEDIUM leak confirmed, cost suspected: text work on every live panel, artPlaces never shrinks: K1TextLayout.cpp:936-973,714-769,615; K1TextRows.cpp:201-256,314-324. 0.2-1 ms. Fix: visible filter, erase in ForgetControl, no rehash per draw.
THR-7 LOW confirmed: KmrpControllerGuiMovieK1 per frame K1ControllerPreload.cpp:77-92,153-159, 30-80 us. Return first if unchanged; cache lookups.
THR-8 MEDIUM confirmed by reading: one cache for all game folders: K1RuntimeAssets.cpp:387-388,1544-1547,536-550. Two installs rebuild each launch; Build RemoveFlat no Running check can delete a live set. Fix: sets\<W>x<H>-<hash>. Cache here 554 MB, 19 sizes.
THR-9 LOW theoretical: SHIFT global: K1RuntimeAssets.cpp:1241,141-142, kmrp-swoophud.c:80,232.
THR-10 LOW theoretical: sampler vs applier suspend each other: K1NativeJoystick.cpp:2638, K1RuntimeEngine.cpp:193.
Locks: order consistent buildLock then packLock. None across engine call. g_k1PictureFilesLock holds during write: narrow it, Low.
Verified safe: movie-thread calls no engine/GL; movie stack; pad reads; startup order; OtherThreads and sampler; worker; shutdown; crash/full disk temp+rename; GDI/GL leaks; cache invalidation for Override, text, font; thread_local.
Docs wrong: K1HudOptions.cpp:873; K1ControllerPreload.cpp:154; K1RuntimeAssets.cpp:141-142,1787-1789.
Unverified: contextless Bind state; main GetEvents during load-module movie; SDL double close; DllMain BCrypt when gui-blend.bin absent; timings; Mac cache.
