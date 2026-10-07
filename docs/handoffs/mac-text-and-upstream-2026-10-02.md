# Mac text and upstream verification handoff, 2026-10-02

This handoff follows [the documentation standard](../documentation-standard.md).

> **A record of 2026-10-02.** The three scenarios it asked for were confirmed that day (the
> last section). What it calls the current implementation has changed in shape since: the
> four variants of one patch are now four patches, the Scripts Enter fix is carried by FTD's
> Stray Bug Fixes, and FTD's layout writers, which this note says are not linked alongside
> KMRP's, are what writes the layout sites since 2026-10-04. The five text-height hooks and
> the XP fitting are still KMRP's. Present state: [`macos/README.md`](../../macos/README.md).

## Current implementation

The failed action-label GUI-frame resizing pass is removed. Five guarded native
height hooks round upward, including the companion font-height getter needed by
confirmation-button sizing. XP native-wrap fitting remains. The independent
Scripts Enter callback fix from FTD is included in all variants. The GUI branch
is joint work by FTD and the KMRP maintainer; its new runtime layout writers
conflict with KMRP's existing ownership and are not linked alongside it.

References: [height measurements and sites](../universal-resolution-math.md),
[upstream audit](../ftd-macos-upstream-audit.md),
[Windows handoff](windows-text-clipping-2026-10-02.md).

## Artifact and evidence

`dist/macos/KMRP-macOS-1.5.0.dmg`:159,273,371bytes, SHA256
`5a1ec26ab9bb76b4b9fec07b7a6d09bd05bc7790822d833e2010ccd6be447d6e`.
App signature and882payload hashes verify from the mounted image. All four
variants validate against the clean Aspyr executable with94/74/93/73hooks,
no overlaps, and correct constructor order. All66resource archives round-trip
through the pool. Native height payload regression, status-summary source
regression and documentation links pass.

At1920×1200, diagnostic measurements show `Adrenal Stamina (self)` retains
55px for two lines at GUI update, HUD draw and label draw; one-line Medpac gets
28px. This establishes sufficient bounds, not visual confirmation. The previous
54px reset is absent. XP was visually confirmed earlier by the maintainer.

The first upstream diagnostic hung while opening exit confirmation. A process
sample identifies the button-width loop comparing ideal height against font
height. The companion font-height ceiling hook was added afterward; termination
had not yet been play-tested at this diagnostic stage. The latest DMG includes
that companion hook; the dated maintainer confirmation below records the
subsequent successful Exit Game test.

## Original verification checklist

**Status correction, 2026-10-03:** the maintainer subsequently confirmed the
two-line action name, Exit Game and Scripts-menu Enter, as recorded below.
Broader resolutions, controller selection, other confirmation dialogs and
individual Cancel/Exit paths still need separately recorded coverage.

1. Close the old frozen diagnostic process before launching the corrected copy.
2. At1920×1200, confirm the full blue action name and `(SELF)` are visible for
   two-line text, then switch to one-line Medpac. Check XP remains visible.
3. Open Exit Game confirmation. Confirm it responds; test Cancel and Exit.
4. Open Character Sheet → Scripts with the Combat Scripts tutorial available.
   Enter must dismiss the tutorial while leaving Scripts open. A subsequent
   Enter or Select button should select the script. Check mouse selection and,
   where available, controller selection.
5. Check other confirmation popups and menus for sizing regressions. The generic
   height getter affects callers beyond the measured HUD case.

Diagnostic copies/logs and machine-specific state stay in ignored
`docs/agent-memory/HANDOFF.md`; no game binaries, DMGs or logs belong in Git.
The new package was built, not installed into the live game by this follow-up.

## Maintainer confirmation, 2026-10-02

After testing the actual game with the rebuilt package, the maintainer reported
that Exit Game, the two-line action name and Scripts-menu Enter all worked
perfectly, and that the game looked stable. These three requested scenarios are
now play-tested. This does not establish every resolution, controller selection,
or every other caller of the generic height getter.
