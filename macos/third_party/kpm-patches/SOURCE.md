# KotOR Patch Manager's Mac patches, as KMRP for macOS builds them

Five of KotOR Patch Manager's `Patches` folders, MIT licence (`LICENSE` here):

| Folder | Id | By | KMRP |
| --- | --- | --- | --- |
| `K1WidescreenPatch` | `k1widescreenpatch` | FTD516 and RaymanGT | required (`macos/README.md`, section 1) |
| `K1StrayBugFixes` | `k1-stray-bug-fixes-patch` | RaymanGT and FTD516 | required |
| `K1ShaderFixes` | `k1-shader-fixes` (FTD's: `k1_shader_fixes`) | FTD, J, Synchro, Vriff | installed with them since 2026-11-13 |
| `MP3PlaybackFix` | `mp3-playback-fix` | Synchro, FTD, Vriff, Lane | installed with them since 2026-11-13 |
| `AntiCrashProphylactics` | `anti-crash-prophylactics` | (its manifest names none) | installed with them since 2026-11-13 |

`macos/build.sh` builds them from this folder with KotOR Patch Manager's own `create-patch.py`,
unless `--kpm` names another KotOR Patch Manager tree.

**Why a copy here (2026-11-03).** The repository's submodule, `third_party/Kotor-Patch-Manager`,
stays at the commit Windows builds with (`2a784bf`, 2026-09-30, the maintainer's rule: the shared pin
stays as Windows has it). That commit's widescreen patch has no entry points for a patch that brings
its own menus (`K1Widescreen_UseGuiFileLayouts` and the two size calls), which KMRP's module asks for,
so the Mac package could not be built from the repository alone (audit MAC-1).

**What it is.** Each folder exactly as at KotOR Patch Manager's master, LaneDibello/Kotor-Patch-Manager
`60e0407ec1ce4f1046c36dbf4bc5d48cc6ce8bb0` (2026-11-11), but for KMRP's changes below:

| Folder | Its last change there |
| --- | --- |
| `K1WidescreenPatch` | #363 (`bcb5d3b`, FTD, 2026-11-09): the menus' background picture placed again, a guard for a HUD not drawn, popups. It has KMRP's two commits since #339 (2026-10-28): the deferred layout mode with its entry points, and the `gui-mode` option |
| `K1StrayBugFixes` | #369 (`343cef0`, FTD, 2026-11-09): the menus' hover and click sounds on the Mac (four hooks in Aspyr's OpenAL wrapper), and a guard against a missing area in the walkmesh and line-of-sight checks (Dantooine's Ebon Hawk vision, Carth's conversation) |
| `K1ShaderFixes` | #368 (`2cdd16c`, FTD, 2026-11-09); first in #361 (`6dfa455`, 2026-11-03) |
| `MP3PlaybackFix` | #372 (`60e0407`, Jack Greiner, 2026-11-11): K1 on macOS added |
| `AntiCrashProphylactics` | `f312f04` (2026-10-28): K1 on macOS added |

Until 2026-11-13 the copy was FTD's of 2026-11-02 (K1StrayBugFixes and K1WidescreenPatch only), and
before that day the KPM clone's `widescreen-gui-mode` branch (`3c0991a`).

**KMRP's changes to them** (the maintainer, 2026-11-13: "any issues from ftd you find we can fix them
ourselves for kmrp"):

| Folder | Change | Why |
| --- | --- | --- |
| `K1ShaderFixes/manifest.toml` | `id = "k1-shader-fixes"`, FTD's `k1_shader_fixes` | KotOR Patch Manager's rule for an id (`PatchValidator.IsValidPatchId`): lowercase letters, digits and hyphens. Its validator called the manifest invalid; nothing in KPM calls the validator yet, so FTD's id worked, but a KPM that does would refuse it |

**Where they do not go.** K1 Shader Fixes is left out for the Mac App Store's game (`macos/build.sh`,
the App Store step): most of its hooks write code into gaps of Steam's `KOTOR_Exe` around
`0x100525000` and data at `0x1005c8e5c`, which the App Store's file matches with no instruction, so
they cannot be translated (`tools/appstore/translate.py`); porting it there means finding gaps of its
own in that file. The maintainer, 2026-11-13: "kmrp doesnt need to support the app store version right
now". FTD's Mac build of K1 Marked Empty Containers (#362) is not taken: KMRP ports that mod itself
(`patches/kmrp-map-notes/marked_empty.cpp`); with both, a container could read "(empty) (empty)".

**Checked on 2026-11-13.** Every hook's original bytes are the game's (KOTOR_Exe 1.4.0); none overlaps
a hook of KMRP's, its controller patch or High FPS Fixes, but for the four memory-safety hooks KMRP's
layout part and Stray Bug Fixes declare identically (kept once); the widescreen patch's entry points and
`gui-mode` option are there. In the Steam game: all 204 hooks applied; the main menu, load screen,
Options and Equip compared with the build before, the same to 0.2% of their pixels (the main menu's
moving smoke); Dantooine and Manaan with no crash, the differences characters, grass and water in
motion. Not seen: the sounds (the test hears nothing), a crash the guards stop, music from an MP3, a
flawed mod model.

**Changing them.** Take the folders from KotOR Patch Manager again
(`git archive <commit> Patches/<folder>`), apply KMRP's changes above again, and update the commits
here.
