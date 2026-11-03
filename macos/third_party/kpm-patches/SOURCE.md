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

**What it is.** Both folders exactly as at FTD's latest, commit
`0c74138d33129b024495734f7bef305cf4cd4d3f` (2026-11-02) of FTD516/Kotor-Patch-Manager, branch
`patches/K1StrayBugFixes`:

| Folder | Same as | Last changes |
| --- | --- | --- |
| `K1WidescreenPatch` | LaneDibello/Kotor-Patch-Manager `master` (`2cb9bc1`, 2026-10-28), byte for byte | FTD's #339 (`0eb5f3c`, 2026-10-28), which took in KMRP's two commits: the deferred layout mode and the entry points back, and the `gui-mode` option (`standard`, `gui-files`) |
| `K1StrayBugFixes` | LaneDibello's `master` plus FTD's two commits of 2026-11-02 (`2f7b207` hooks, `0c74138` README), not yet in Lane's | FTD's #338 (`46f85da`, 2026-10-28) and `2f7b207`: the Scripts Enter fix lets a mouse double-click on a row confirm; a module's key table no longer leaves a resource pointing into freed memory when it is unloaded (the crash at a change of module); Caps Lock with no party leader no longer crashes |

Until 2026-11-03 the copy was the KPM clone's `widescreen-gui-mode` branch (`3c0991a`): FTD's
widescreen patch of 2026-10-22 with KMRP's two commits, then not merged, and the Stray Bug Fixes
of 2026-10-03. Taking FTD's latest made one change outside this folder: `kmrp-layout` declared the
old Scripts Enter fix (a `ret` at `0x1002d3e34`) identically to FTD's, and FTD's new one differs,
which `make_kmrp_patch.py` refuses, so `kmrp-layout` no longer declares it.

Checked on 2026-11-03: the 19 hooks' original bytes are the game's (KOTOR_Exe 1.4.0); the App
Store build's hook list translates the new hooks' `movabs` constants and `jmp [rip]` targets (the
two return addresses the double-click check compares with each follow the same `call *0x80(%rax)`
in both builds); the Mac suites pass; in the Steam game, a save loaded, the menus, and two loads
from inside the game (Manaan to the Endar Spire, a change of module) with no crash. The Scripts
menu and Caps Lock fixes were not exercised in play.

**Changing it.** Not by hand here: change the patch in KotOR Patch Manager's tree (FTD takes
changes as pull requests into his `patches/...` branches), then copy both folders again
(`git archive <commit> Patches/K1WidescreenPatch Patches/K1StrayBugFixes`), and update the commit
above.
