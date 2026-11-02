# Issue 78 audit: the full Rancor scene (2026-11-02)

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../../documentation-standard.md).

**Kind: audit record of 2026-11-02.** Static audit of the Rancor scene: nothing here is verified on any GPU. Results since are in
[`windows-verification-1.6.md`](../../windows-verification-1.6.md).

Read-only. Nothing in the repo or a game folder changed, the game was not started, nothing was built, and
nothing in `build/` was run (K1DC's clone there was read with `git show`). **No part of this is verified on AMD.**
Nothing was run on NVIDIA either: every result is static.

Labels: **measured** (read out of a game file or binary here), **source** (read in a reconstruction or source
tree, not run), **suspected** (fits, no direct evidence).

Files: scene data and scripts in the `i78` folder beside this file (`lst/`, `rooms.txt`, `census.jsonl`,
`census2.jsonl`, `q.py`). Game text is not quoted here.

## 1. Result in short

No step of the scene does anything a 7800 XT should find hard. Compared with the rest of the game nothing in it
breaks a limit: no NPOT texture, no degenerate shadow geometry, no bone index outside the program's array, no
non-finite key, no Bink movie, no camera video effect, no spin wait. So **no candidate below is more than
suspected as the cause**. The reporter's dump outranks everything here.

The audit does change four things in the earlier notes, and the first changes what has to be tested:

1. **"No grenade added" does not mean the no-grenade branch.** The pile starts with 2 `g_w_fraggren01` and a
   `g_i_progspike01` in its template (`tar05_corpsepile.utp`, `UseTemplates 1`, no instance list). `k_ptar_grencheck`
   tests the pile's own inventory. A player who did not empty the pile first gets the grenade branch, with the
   Rancor's death, VFX 1045 and the screen shake, without adding anything. Measured. Which branch the reporter hit
   is **unknown**; ask them. The statement in `docs/windows-verification-1.6.md` ("the reporter's branch ends in
   `k_ptar_rancorcs3`") is not established.
2. **The camera shake and rumble exist only in the death branch.** `k_ptar_pile_ud` is signalled with 2000 only
   from the Rancor's user event 1007 (death) in `k_ptar_rancor_hb` (offset 0xD9D to 0xE04). The no-grenade branch has
   one fade, placed cameras, one animation and one sound.
3. **Skin meshes cast no stencil shadows at all.** `PartSkin::Project` (0x00477B90) returns at once while
   `0x00828058` is 0, and the image holds one read of that cell and no write (image search, GOG exe, measured). The
   40 `Ran_*` shadow-only meshes are the real casters: 2,086 faces, largest `Ran_Head` 190. The `shadow` flag on the five
   skins does nothing, and the earlier "many shadow-only meshes" is the mechanism, not an oddity.
4. **`glFinish` was already swallowed in K1DC 1.2.0** (`crates/k1-driver-compat/src/enable.rs` at tag `v1.2.0`), not
   first in 2.0.0 as the notes said. That line of the notes falls away.

## 2. The scene, step by step

Module `tar_m05ab`, vanilla rims as on GOG. The Steam folder has K1CP's `tar_m05ab.mod`, which rewrites these scripts
(new pile tag `cp_tar05_rncpile`, `DestroyObject`, `NoClicksFor`) and is not what the reporter ran.

| # | Step | Runs | Unusual? |
| --- | --- | --- | --- |
| 0 | Player opens the pile, Give Items | `CSWGuiContainer` (0x006B6DC0, layout `container`, `BTN_GIVEITEMS`) | Rare screen, few players see it before this. CPU and GUI only |
| 1 | `tar05_synthodor` goes in; placeable event 0x1B (0x00588305) | `k_ptar_pile_hb` | `OnInvDisturbed`, despite the name |
| 2 | Pile locked, `TAR_RANCOREATING` set, `SetGlobalFadeOut` length 1, wait 0 (black), XP given, Stampy jumped to `tar05_wprancor` | fade quad | One full-screen quad. While black the frame costs almost nothing: see candidate 2 |
| 3 | After `DelayCommand` 1 s and `ActionWait` 1 s: conversation `tar05_pile_dlg` | dialogue GUI, letterbox | 6 entries, 6 replies, no text or VO, Skippable, `CameraAngle 6`, `CamVidEffect -1` |
| 4 | Entry 0, `k_ptar_rancorcs0`: fade in (wait 1, length 1), party jumped to `tar05_wpparty`, Stampy runs to `tar05_wppile` (17.8 m), resurrect and heal for dead party | camera 1 | FOV 55, height 1.5, pitch 100 |
| 5 | Entry 1, `k_ptar_rancorcs`: faction change, 5 s | camera 1 | |
| 6 | Entry 2, `k_ptar_rancorcs1`: `ActionPlayAnimation(119)` (`ANIMATION_FIREFORGET_CUSTOM01`), sound `c_rancor_atk1`, 3 s | camera 2 | FOV 70, height 3, pitch 90, closest view. The model has 27 animations and none named `custom01`, so which one plays was not traced |
| 7 | Reply 2 asks `k_ptar_grencheck`: 9 grenade tags in the pile | | The only condition in the tree |
| 8a | **No grenade.** Reply 3, `k_ptar_rancorcs3`: global cleared, `ActionForceMoveToObject` home, 30 s | camera 2 | Pile may be disturbed again afterwards |
| 8b | **Grenade.** Entry 4, `k_ptar_rancorcs2`: `EffectChoke` 3 s (Rancor has a `choke` animation), VFX 1045 on `imp_headcon_node`, after 0.7 s `cb_gr_fragment`, `c_rancor_bat2`, sound `cb_gr_poison`, 3 s | camera 3 | FOV 55, height 4, pitch 90 |
| 9b | Entry 5, `k_ptar_rancorcs4`: `EffectDeath(1, 1)`, `cdie` 2.63 s, 20 XP. User event 1007 signals 2000 to the pile: 1 s later rumble 11, VFX 6002 (`shaketype 2`, 1 s, rumble 16) | camera 1 | The grenade check also destroys the pile's contents |

`k_ptar_rancordie` holds an older form of the death (choke, delayed death, `DestroyObject`) and no dialogue node names it.

**Cameras (measured):** quaternions of unit length, FOV 55 or 70, no zero or non-finite value. Nothing degenerate for
the projection.

## 3. What is drawn, with numbers

| Item | Numbers (measured) | Against the game |
| --- | --- | --- |
| `c_rancor` render geometry | 5 skins, 2,980 faces, plus 2 eye tri meshes, 56 faces | Most faces of all 54 `c_*` models (5,170 with proxies; median 2,649): less than twice the median |
| Bones | Palette used 13, 13, 15, 4, 4, max 4 weights, bonemap 57 | ARB array is `boneArray[51]`, 17 bones. Game's maximum is 17 (index 16), `c_rakghoul` uses 16, Rancor 15. No model passes 16 |
| Shadow casters | 40 rigid meshes, 2,086 faces, 0 degenerate faces, largest 190 | First of 54 in faces, fourth in meshes (median 23; `c_selkath` 44) |
| Shadow limits | Face records 0x800, vertex marks 0x1000, index buffer 0x3000 bytes = 1,024 edges per mesh, with no bounds check (`RenderShadowArray` 0x00426660) | Rancor is far below. The rigid mesh of 3,301 faces in `m12ab_01a` is not a Taris matter |
| Animations | 27, no non-finite key, no scale controller, largest value 3.05 | Ordinary |
| Textures | `C_Rancor01` 512 DXT5, 10 mips; `C_Rancor01b` 512 RGBA8, 10 mips, 1.4 MB, `isbumpmap 1` | Same as `c_hutt01b`. NPOT textures in the packs: **0 of 3,294** |
| Bump creatures | Only hutt, rakghoul, rancor, terantanak | Rakghouls are in this same module. Not a first |
| Rooms | From `m05ab_16a` the VIS file shows 14b, 14c, 17a: 12,083 faces in 177 meshes, no emitter, 2 small animations in 16a and 14c | Small. All 9 lights in 16a have `shadow` set, but only one light per frame is used (`scene+0x270+0x1C`) |
| Fog, grass | Fog on, 0 to 80; no grass; `SunShadows 0` | Ordinary sewer |
| Corpses round the pile | 21 placeables within 4 m, about 22,500 faces, no shadow meshes (model names assumed equal to template names) | The densest thing in shot, and cheap |
| Particles, no-grenade branch | None | |
| `v_rancorexp_imp` (grenade only) | **18 emitters**, tied first of 102 `v_*` models with `v_drdexpld_01`; median 2. 13 use `fx_rip` (64 x 256 DXT1), which **no other model uses**. `Fx_part_04` chunk emitter, 10 chunks. `impact` animation 48.3 s. Peak about 275 live particles by key and life (smoke 20 a second for 40 s, life 7) | A long effect, not a large one. Pool grows to fit (0x0048F1DA). `fx_rip` is an ordinary texture on a billboard; distortion goes through `RenderForceDistortion`, not this |

Parse coverage: 2,788 of 2,832 models read. 44 failed in pykotor, among them `fx_explode_03`. Skin numbers cover `c_*` and
every skin read by the corrected second census, about 1,800 of 2,832 models when this was written and still running (`census2.jsonl`,
`q.py` reruns it). The first census, whose skin columns are wrong, finished and supplies the emitter ranks.

## 4. Engine paths

All **source** unless marked, `swkotor1-reconstruction`, address as GOG 1.03.

**Skin drawing, `RenderSkinnedVP` 0x0048A520.** The bone loop runs over the bonemap (57), skips -1, writes
`index * 3 + 0x12`. Five programs are chosen by gates; on AMD at 1.2.0 `get_ati_fragment_shaders_disabled` is 0, so the
three bump blocks are skipped and the plain program runs, as for almost every creature. At 2.0.1 `ARB_SkinBranch` opens
those blocks on all cards.

**One real spec violation, but in every skinned creature.** The program does `MUL vReg0, attrib[4], env[16].zzzz`
(env 16 z is 3), then `ARL A0.x` and `boneArray[A0.x + n]`. Unused slots hold -1 with weight 0 (measured on all five
Rancor skins: 8,979 such slots, none with a weight). So `A0.x = -3` reads below `program.env[18]`, outside the declared
array, which the ARB spec leaves undefined. The result is multiplied by zero. Since every skin has done this since
the Endar Spire, it does not explain this scene; recorded because it is exactly the kind of thing a driver may treat
differently from one release to the next.

**Stencil shadows.** `Scene::RenderShadows` 0x00451A50, then `DoGobShadowsForThisLight` 0x00450550, then `PartTriMesh::Project`
0x00474220 per mesh, in the CPU silhouette path. `shadow_mode` 0x00828054, `0x007B9374` (vertex program volumes) and two-sided stencil
`0x007A68DC` have **no writer in the image (measured)**: the vertex program and `EXT_stencil_two_side` paths never
run. Each caster is two `glDrawElements(GL_TRIANGLE_STRIP, ushort)` from client memory, with `glStencilOp` keep/incr/keep and
keep/decr/keep (non-wrapping) and `glFrontFace` swapped. So the Rancor costs at most 80 small draws per frame on one
light, then an 11-vertex fan with depth test off. Strip stitching with shared cap indices gives degenerate triangles,
which is normal. A light inside the Rancor's volume is possible in 16a (lights at about 26 and 33, floor about 24) and
changes only how much is filled.

**Emitters.** `ExplosionEmitter::Update` 0x00497640 is a loop bounded by a spawn count. `updateParticleFrame` 0x0048E460 has `do` and
`while` loops on the frame index, with a nonzero step; it skips when delta is exactly 0. No per-frame wait found.

**Shake.** `UpdateCameraBumpAndShake` 0x00641760: `ms = delta * 1000` truncated, no loop. Above 1,000 frames a second `ms` is 0
and the shake would never end in vanilla. High FPS Fixes detours exactly this site (0x00641827).

**Scan for a spin in engine code on these paths:** none. And a spin only stalls the game. The reporter lost
Ctrl+Alt+Del, so the fault sits below the process (driver, GPU, power).

## 5. KMRP and K1DC on those paths

| | 1.5.1 (reporter) | master |
| --- | --- | --- |
| K1DC | 1.2.0, `dinput8.dll` + `.asi` | 2.0.1 as a kpatch, 28 hooks |
| Skin bump on AMD | No, plain | **Yes, new**, `ARB_SkinBranch` 0x0048AB8F and three more; Rancor and Hutts take block 1, per-light additive passes |
| Soft shadows | Off unless the player set them | **On at K1DC's first run**, from 1.3.0 (`ab8d1d7`), through the game's setters. New on this path |
| Frame | Window's back buffer | **KMRP FBO** (`K1OffscreenFrame.cpp`), stencil shadows land in a `DEPTH24_STENCIL8` renderbuffer, copied at swap. `window-drawn=1` in `[Offscreen]` keeps it out |
| FBO colour | 8 bit | 16 bit in K1DC's targets (`f7681fb`) |
| Mipmaps | CPU | **Hardware**: `0x0078E538` set to 1 (`K1CoreFrames.cpp`); touches every upload, `C_Rancor01b` among them |
| High FPS Fixes | **On by default at 165 Hz** (`HighFpsFixAuto`, floor 62 Hz), `AllowHighMonitorFrequency=1`, `RefreshRate` set to the highest, **V-Sync left as it was** | Bundled; same rule to be confirmed |
| KMRP hooks in the scene | GUI frame, panels, list rows, dialogue layout, rumble to XInput (`NativeRumbleK1`, only in the death branch), no hook in skin, shadow, emitter or fade code | Those, plus the frame code |
| Waits on the render path | `Sleep(1)` at start-up only | Bounded (see the notes); offscreen code has no loops |

**So at 1.5.1 the Rancor's draw path holds no KMRP or K1DC-specific skin code at all.** K1DC's part in this frame is its
ARB fragment programs for world modes and `glEnable` interposing, which the reporter had been running for hours. KMRP's part is the GUI.
High FPS Fixes is a binary DLL with no source here. Its table was read (36 hooks; the letterbox at 0x006A75xx, 0x00623B54, danglymesh, animation UV, camera shake), its DLL was not audited.

K1R: 744 files. None for `m05ab`, Stampy, `c_rancor`, the room textures, the corpses, the pile scripts, `k_def_*` or the effect
models. It replaces global 2DAs including `placeables`, `appearance`, `visualeffects`; rows 80, 1045, 6002 were not compared
beyond the earlier check of row 80. `tar_m05aa.mod` is the neighbouring module. **K1R does not touch the scene's art.**

## 6. Ranked candidates

| Rank | Candidate | Evidence | Why this rank |
| --- | --- | --- | --- |
| 1 | **A fault in the driver or GPU that this scene merely coincided with or tripped**: Adrenalin 26.10.1 on a legacy compatibility GL stream, Windows build 26300 | Suspected. `a2000002` with `AMD_REPORT_UM` points at an AMD driver hang by secondary sources only. Several events, driver reinstall cured the aftermath | Nothing in the scene is special enough to need a scene-specific cause. Time of each event is the first thing to get |
| 2 | **Uncapped frames during black or static views at 1.5.1.** With V-Sync off (left as found, while 1.5.1 raised the rate limits at 165 Hz) the black fade has nearly no work, so frame rate is limited by CPU only | Source for the settings; the reporter's V-Sync value unknown; load suspected | Fits "after a fade, in a still shot". Does not explain why not in any menu. Cheap to rule out: their `swkotor.ini` |
| 3 | **The grenade branch**: 18 emitters, the only user of `fx_rip`, chunks, `EffectDeath`, shake | Measured that it exists and that the reporter may have hit it; link to a hang suspected | The only scene content with a game-wide rank, though small in draw terms. Must be tested first since no one has |
| 4 | **Deferred program compile**: a first draw of a (mode, fog) variant reaching AMD's compiler here. K1DC's own doc says a driver may defer compile to first draw, `warm` is off by default, and a corrupted GL cache would explain "even vanilla fails until a driver reinstall" | Suspected. Mechanism read in K1DC source; no evidence this scene has a new variant | The only idea that connects the freeze to the aftermath. NVIDIA can list the variants |
| 5 | Out-of-range `boneArray` read | Measured in data and program text; harm suspected | All skins, so it needs a driver change to matter, and then the reporter would have failed on the first creature |
| 6 | Shadow fill: 40 casters, 80 draws, light inside the volume | Source; harm suspected | Far below what a modern card notices |
| 7 | A GUI or dialogue state from Give Items, then conversation | Source | Can stall the game, not the PC |

**Rejected on evidence:** Bink (none), camera video effect (none), NPOT (0), Rancor bone limit (15 of 17), degenerate shadow faces (0), non-finite keys or vertices (0), oversized shadow draw (largest caster 190 faces), `glFinish` per upload at 1.5.1, vertex program shadows and `EXT_stencil_two_side` (never run), K1DC 2.0 skin branch for this report (not in 1.2.0), offscreen frame for this report (not in 1.5.1), K1R art in the scene.

**1.6 on AMD, a different question.** Whatever caused this, 1.6 adds on this exact path, for the first time on AMD: the skin bump
branch, soft shadows, KMRP's FBO with stencil, and hardware mipmaps. None has been seen on AMD. Each has a switch
(`bump=off`, K1DC `framebuffer=off`, `window-drawn=1`) except the mipmap answer.

## 7. What can be tested here (NVIDIA, on the copy)

A pass shows only that this GL stream does not hang NVIDIA. It clears nothing on AMD.

**First wait for the regression run**: nothing touches `build/verify/steam` while anything uses `build/`. The maintainer at the PC
drives; do not attach x32dbg to this game (kills it, memory note); swkotor.exe foreground before any input.

**The saves here cannot be used as they are.** Measured: all five saves holding `tar_m05ab` (000088, 000093, 000134, 000920, 000922)
have an empty creature list and no items in the pile. The Rancor is gone from them.

Fixture, modelled on `testing/controller/build_combat_fixture.py`, not written and each step unverified:

1. In `build/verify/steam`, move K1CP's `tar_m05ab.mod` to `KMRP\backups`, so the vanilla rims load as on GOG. Run again with it back for K1CP's version.
2. Script copies 000920 to a new slot, removes the `tar_m05ab` entry from `SAVEGAME.sav` so that the module loads fresh, and adds the
   `tar05_synthodor` item to `INVENTORY.res`, converting the UTI from `tar_m05ab_s.rim` at run time (never committed). Whether the game
   accepts a save with a visited module removed is not known; if it refuses, keep the entry and add the creature instead.
3. Reach the module: `EnableCheats=1`, then `warp tar_m05ab` (the string is in the exe; the console is untried under KMRP). Save there.
4. Second pass of the script on that save: set `Mod_PlayerList` position to about (219, 312) beside the pile, `Min1HP`, as the combat fixture does.
5. Fresh module means Stampy alive, pile with two grenades: leave them for the **grenade branch**, take them for the **no-grenade branch**.

Tests, in order:

| Test | Asks | Measure |
| --- | --- | --- |
| T1 both branches on master, K1DC `log=debug`, `frames=on` | Any `gl error`, any stall | K1DC log, frame times |
| T2 list of (mode, fog) variants first used in the scene | Candidate 4 | Compare with a run through Taris; any variant new at the Rancor is the thing to ask AMD about |
| T3 frame rate in the fade with V-Sync 0 and High FPS Fixes on | Candidate 2 | Swaps a second in the fade and in camera 2. Thousands would make the case |
| T4 1.5.1 with K1DC 1.2.0, in a separate copy | The reporter's stack | Same logs |
| T5 soft shadows on with camera 2 and the Rancor | 1.6 cost | Frame times |

## 8. What needs an AMD user (never claimed here)

Ask the reporter, in this order:

1. Did you empty the pile before adding the item? Any grenades left? Do you recall an explosion or the Rancor dying?
2. Their `swkotor.ini`: `V-Sync`, `RefreshRate`, `AllowHighMonitorFrequency`, `Soft Shadows`, `Frame Buffer`, `Disable Vertex Buffer Objects`, `Anti Aliasing`.
3. Times of each 25 October event, Event IDs 4101, 117, 141, and the `AMD_REPORT_UM` dump, with anything in `C:\Windows\LiveKernelReports\WATCHDOG`.
4. On 1.6, from a save before the pile, one change at a time: Adrenalin Reset Shader Cache first; K1DC `warm=on` (moves any compile fault to start-up); `bump=off`; `framebuffer=off`; `window-drawn=1`; `decline=on`. Then Chill, Anti-Lag and overlays off.
5. A short try of each branch, if they agree. A hard freeze risks their files, so they should say yes knowingly.

Any other AMD owner who reaches this scene on 1.5.1 or 1.6 is worth a request: one pass would say more than this document.

## 9. Not done

The scene has since been run on NVIDIA, both branches, on vanilla and K1CP scripts, with no freeze: see [`windows-verification-1.6.md`](../../windows-verification-1.6.md). That clears nothing on AMD. T2, T4 and T5 not run. When this was written the game had not been run. High FPS Fixes DLL, KPM runtime, K1DC 1.2.0 binary not audited. `ANIMATION_FIREFORGET_CUSTOM01` to model animation not traced. K1R's 2DA rows not diffed in full. Room `m05ab_16a` camera containment not computed. Maintainer's private reverse engineering used only to confirm the fade entry.
