> **Working notes** of the 1.6 audit, 2026-11-01, kept as the evidence for [the report](../../cleanup-audit-1.6-report.md). Not a reference: leads may be overturned there. Documentation standard: [`documentation-standard.md`](../../documentation-standard.md).

# Second pass GUI (saved from agent's reply; verify high ones). 2194acf, nothing run.

GUI-1 HIGH confirmed, low likelihood: cyclic Override .gui stack overflow at start: guiadapt.c:1138,1145,1163 ll_clone_field/struct, no depth/node limit. Reached by R3 screen label template (ll_cue), LBL_QUEUE1 mipc (ll_combat_cues), KmrpControllerCues. K1PartyRosterGui.cpp:141 has guards (depth<12, 4096). Fix: depth 12, cap, early return. Test: Test-ModCompatibility fixture. Affects Mac, controller, Linux.
GUI-2 HIGH confirmed by reading, medium: K1TextRows Stretch (K1TextRows.cpp:180-188) cancels Icon Size slider on skill rows (K1RuntimeLayout.cpp:582-595 SkillRowExtent); third icon part +0x29C = 0x1B4 + 2*0x74. Cases: rows recorded at default then slider moved; Text Size above 50. Chain: Chart K1TextRows.cpp:142-144 caps at box shrunk by ChainRowExtent once g_iconsScaled. Note user saw slider "works perfectly" at text default?. SetFlags bits not read. Fix: one owner; decide with maintainer.
GUI-3 MEDIUM confirmed by reading: odd layout aborts mode change: K1RuntimeLayout.cpp:823-825,830,836,845,881-882, K1RuntimeResolution.cpp:329-331: partial, then retries each GUI frame reading .gui. FileExtents stricter than live layout (guiadapt.c:391,:202,:397 vs K1RuntimeLayout.cpp:86-89,127). Fix: skip bad control; compute before mutate.
GUI-4 MEDIUM strongly suspected: Container's widening read as moved at resolution change: K1TextLayout.cpp:432-465, K1RuntimeLayout.cpp:859-871. Buttons wider than panel. Fix: expose grow, subtract like rowsRight.
GUI-5 MEDIUM strongly suspected: failed art helper sealed in complete set: K1RuntimeAssets.cpp:1624,1629-1634,1654,545-549. Each helper mallocs 111 MB ERF. Fix: fill returns false except absent.
GUI-6 LOW confirmed: AurTextureGetReference without release: K1TextLayout.cpp:646,648,796-797. light stale.
GUI-7 LOW confirmed: kmrp-gameart.c:462-467 keyed_resource unbounded, runs at set build not every start. tutorial.2da 1,948 B in 431,840 2da.bif, chitin.key 569,239: 4 MiB caps fine.
GUI-8 MEDIUM confirmed by reading: "exactly as its author left it" false for third-party scaled: guiadapt.c:785-823,827-828,843,847-855; live-adaptive-layout.md:395; note 749. Gutters, centre rows, fit journal, fit rows, map box still run. Test-ModCompatibility.py:561 passes only as input already went through. Fix: guard each with own_canvas or correct rule; decide with maintainer; mirror build_live_layout.py.
GUI-9 LOW suspected: badge signature ignores scale (K1XboxControls.cpp:3221-3248,4040).
GUI-10 LOW confirmed: "Override's font" logged for KMRP's own 18 fonts (K1RuntimeAssets.cpp:995,1719-1721).
GUI-11 LOW confirmed: unchecked mallocs kmrp-gameart.c:290,297,306,342; cap 4096.
GUI-12 LOW theoretical: size_t wrap kmrp-swoophud.c:161,170,177,191,208, gameart:361-362.

Verified safe: strings map all ctors/dtors seen (0x45B990, one caller 0x45BE4B; vtable 0x741878 only ctor, dtor; dtor 0x45BC70 via 0x45BE80). GFF readers gff_open etc bounded; K1RuntimeLayout Gff; K1PartyRosterGui; TGA/TPC decoders caps 8192; 2DA parser; Merge never writes Override, row never moves (kmrp-2da.h:558); cache keys; KmrpPack LZMA with SHA-256; OtherThreads and CommitEngineAt (vectors before suspension); Build lock; Fit state; badges with KMRP absent; persistence in swkotor.ini not kmrp.ini.
Disagree: P9 4 MB limit not a problem.
Unverified: GUI-2, GUI-4 in game; SetFlags bits; fonts under 256 glyphs (WrappedMeasurement, KmrpTextNaturalWidthK1); small res on option pages; HUD Size interactions; guiblend from 560; large-address-aware state.
