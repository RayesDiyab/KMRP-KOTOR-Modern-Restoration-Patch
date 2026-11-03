# FTD's two Mac patches, as KMRP for macOS builds them

KotOR Patch Manager's `Patches/K1WidescreenPatch` and `Patches/K1StrayBugFixes`, by FTD516 and the
KotOR Patch Manager contributors, MIT licence (`LICENSE` here). KMRP for macOS requires both
(`macos/README.md`, section 1); `macos/build.sh` builds them from this folder unless `--kpm` names
another KotOR Patch Manager tree.

**Why a copy here (2026-11-03).** The repository's submodule, `third_party/Kotor-Patch-Manager`,
stays at the commit Windows builds with (`2a784bf`, 2026-09-30, the maintainer's rule: the shared pin
stays as Windows has it). That commit's widescreen patch has no entry points for a patch that brings
its own menus (`K1Widescreen_UseGuiFileLayouts` and the two size calls), which KMRP's module asks for,
and its Stray Bug Fixes hooks differ from the widescreen patch that goes with them, so the Mac
package could not be built from the repository alone (audit MAC-1); it was built with `--kpm` and a
KotOR Patch Manager clone kept beside the repository.

**What it is.** Both folders exactly as at commit `3c0991a3ebd61b5006c397d96dfe4a224009b2fd` of that
clone, branch `widescreen-gui-mode`:

| Commit | By | What |
| --- | --- | --- |
| `b3a50d1` | FTD516 | FTD's widescreen patch as of 2026-10-22 (FTD516/Kotor-Patch-Manager, branch `patches/K1WidescreenPatch`) |
| `306381e` | Rayes Diyab | brings back the deferred layout mode and the entry points `b3a50d1` removed |
| `3c0991a` | Rayes Diyab | the `gui-mode` patch option (`standard`, `gui-files`) |

The last two are offered to FTD as a pull request into his branch (text in
`kmrp-macos/work/pr-widescreen-gui-mode.md`); they are not merged there yet. When they are, this copy
should be replaced by FTD's version, or the build pointed at a tree that has it.

**Changing it.** Not by hand here: change the patch in KotOR Patch Manager's tree, then copy both
folders again (`git archive <commit> Patches/K1WidescreenPatch Patches/K1StrayBugFixes`), and update the
commit above.
