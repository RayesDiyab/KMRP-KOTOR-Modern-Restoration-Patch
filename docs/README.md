# Documentation

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it -- measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

Design and build documentation. Engine analysis lives one level over, in
[`reverse-engineering/`](../reverse-engineering/README.md).

## Where to start

- **Auditing text scaling and clipping?** [Text layout inventory](text-layout-inventory.md)
  records candidate control families, measured failures and the review process for shared fixes.
  The [native coverage audit](native-text-coverage.md) adds runtime creation paths and live-object checks.

- **Playing, not building?** The [main README](../README.md) installs it, and
  [features.md](features.md) says what it changes.
- **Want the mechanism behind a feature?** [features-technical.md](features-technical.md)
  names it and links the document with the measurements.
- **Starting an agent task?** Read the root [`AGENTS.md`](../AGENTS.md), then use
  the routing table in [`agent-memory/README.md`](agent-memory/README.md).
- **Adding a resolution?** `universal-resolution-math.md`, then
  `GROUPS` in `tools/prepare_universal_resources.py`.
- **Changing an engine constant?** Read
  [exe-patching.md](../reverse-engineering/exe-patching.md) first, then the
  document for that subsystem.

## What KMRP does

| Document | What it covers |
| --- | --- |
| [features.md](features.md) | **For players:** everything KMRP changes compared with the unmodified game, in plain words. |
| [features-technical.md](features-technical.md) | The same list with the mechanism, the patch that carries it, the source files and the reference document for each feature, and what has not been seen in the game. |
| [hud-size-options.md](hud-size-options.md) | The HUD Size page, and the mouse and keyboard HUD placed by KMRP at run time from a table, as the Xbox-style HUD is. |
| [ingame-text-options.md](ingame-text-options.md) | The Text Size and Font page: its native controls, the three font styles in the bank, how text is sized, and what is saved. |
| [hd-original-font.md](hd-original-font.md) | The HD Original font, the default: the game's own fonts redrawn, measured from the originals to a fraction of a pixel, and the rules each letter follows. |
| [release-1.6-progress.md](release-1.6-progress.md) | **1.6 in progress:** every Windows change on `master` since 1.5.1, the issues each answers, and what has been seen in play. |

## How it is built and installed

| Document | What it covers |
| --- | --- |
| [kpm-edition.md](kpm-edition.md) | **KMRP on KOTOR Patch Manager's runtime.** Its first sections are the current state: two patches, nothing in `Override`, the resolution chosen in the game. The rest is the record of the four-patch edition, of which the relocation table and the applier still describe live code. The runtime's build is in [src/kpm-runtime/README.md](../src/kpm-runtime/README.md). |
| [patcher-ui-build.md](patcher-ui-build.md) | The Windows installer itself: window flow, proportional resize, icon pipeline, embedded resources, build process, transaction safety, and the release checklist. |
| [windows-engine-source.md](windows-engine-source.md) | The source-built Windows engine recipe: no clean or gold executable as input, the byte guards, the eleven relocatable pages, package checks, and the measured Ubuntu cross-build. |
| [universal-resolution-math.md](universal-resolution-math.md) | How one build covers 66 resolutions and blends the rest: the fields that hold screen geometry, the coordinate math, how the interface files are packaged, and **which resolutions have actually been play-tested.** |
| [font-scaling.md](font-scaling.md) | The font, dialogue-letterbox and list-row scaling work, and the gold snapshot chain, kept as the reference the source recipe was checked against. |
| [documentation-standard.md](documentation-standard.md) | **The standard every document here is held to.** Read before writing or updating one. |
| [agent-memory/](agent-memory/) | Repository-local guidance for coding agents: orientation, task routing, build and verification workflows, durable discoveries. |

## Compatibility

| Document | What it covers |
| --- | --- |
| [mod-build-compatibility.md](mod-build-compatibility.md) | Accepted executables, K1CP, K1R and KOTORganizer, KOTOR Patch Manager's hash boundary, and measured limits for other executable patchers. |
| [third-party-driver-compat.md](third-party-driver-compat.md) | **K1 Modern Driver Compatibility**, bundled with Synchro's permission: what it fixes on each vendor, every byte it writes, and the check that none of its eight sites collides with KMRP's. |
| [windows-dpi-scaling.md](windows-dpi-scaling.md) | Why Windows display scaling can zoom KOTOR a second time, the compatibility value KMRP manages, restore ownership, and the tested matrix. |
| [nvidia-present-method.md](nvidia-present-method.md) | The NVIDIA present method set for `swkotor.exe` when the driver would otherwise show half-drawn frames: when it is written, when the player's choice is left alone, restore. |
| [linux-proton-steam-deck.md](linux-proton-steam-deck.md) | Linux and Proton procedure, the measured Ubuntu run of 2026-10-01, and what is unverified since. |

## Tools beside KMRP

| Document | What it covers |
| --- | --- |
| [save-editor.md](../save-editor/docs/save-editor.md) | The **KMRP Save Editor** for KotOR 1 and 2: where it finds saves, every field it writes and under which rule, the bugs of older editors it avoids, how a write stays safe, and what was tested in both games. |
| [save-editor-format.md](../save-editor/docs/save-editor-format.md) | The save format of both games, file by file and field by field, each fact tagged with how it was measured. |
| [fonts/README.md](../fonts/README.md) | The **KMRP Original HD fonts**: 11 OTF files under the SIL Open Font License 1.1, how they were drawn from the HD atlases as lines, corners and arcs, what was measured, and how KMRP's atlases are drawn from them. |

## Controller support

| Document | What it covers |
| --- | --- |
| [controller-support.md](controller-support.md) | The overview: how controller support ships, its provenance and build, installed files, hook sites, prompt families and validation. |
| [controller-standalone.md](controller-standalone.md) | **KOTOR 1 Native Controller Mod + Xbox HUD**, the controller patch as a file of its own: what it carries, how it fits any interface, its limits, what was and was not tested. |
| [controller-xbox-hud.md](controller-xbox-hud.md) | **The Xbox-style HUD**, the controller patch's option: layout and behaviour against the original Xbox version, the hooks, limits and what was run. |
| [controller-native-path.md](controller-native-path.md) | How it works: the joystick device the game's console input expects, the mapping, focus navigation, the camera, the tab bar, movies and the action bar. |
| [controller-sdl-backend.md](controller-sdl-backend.md) | The XInput and SDL backends: dependency, normalisation, ownership and outstanding hardware validation. |
| [controller-rumble.md](controller-rumble.md) | Rumble: the three modes, the events, the settings file. |
| [controller-layout.md](controller-layout.md) | The Controller Layout screen: resource generation, panel callbacks, lifecycle and acceptance test. |
| [controller-prompt-specification.md](controller-prompt-specification.md) | Which button prompt appears where, and the rules for placing it. |
| [controller-behaviour-matrix.md](controller-behaviour-matrix.md) | What every input does on every screen, as measured, with what has changed since. |
| [controller-parity.md](controller-parity.md) | The native path against the legacy keyboard path, button by button. |
| [controller-playtest-checklist.md](controller-playtest-checklist.md) | The physical-pad checklist, with each dated pass on a real controller. |
| [controller-planned-work.md](controller-planned-work.md) | What is still open: the Guide button and virtual-pad slot safety. |
| [reference/kotor-xbox-manual.pdf](reference/kotor-xbox-manual.pdf) | The original Xbox version's printed manual (LucasArts, 2003), a scan of 30 spreads at 150 dpi: the pad's buttons on page 5, the action menu's six icons on page 8, combat and the action queue on pages 28-29, Stealth mode on page 30 (the manual's own page numbers; two to a PDF page). The text layer was added on 2026-10-13 with the recogniser built into Windows, over the untouched scans, and then corrected by hand on all 30 pages: every heading and label in the display fonts typed in, the body text read line by line beside a second recognition pass, the credits and the licence beside enlarged crops, the contents list and the page numbers added. The text follows the reading order (left page, then right; column by column in the credits). Not in the layer: the text inside the screenshots. Where the layer and the printed page differ, the page is right. How it was made and how to rebuild it: [`tools/xbox-manual-ocr/README.md`](../tools/xbox-manual-ocr/README.md). |

## macOS

| Document | What it covers |
| --- | --- |
| [macos/README.md](../macos/README.md) | The macOS build. |
| [macos/PLAYER-README.md](../macos/PLAYER-README.md) | The players' instructions, shipped in the Mac package as `README.md`. |
| [macos/WINDOWS-PARITY.md](../macos/WINDOWS-PARITY.md) | Every Windows engine site and its state on the Mac. |
| [macos-handoff-1.5-to-1.6.md](macos-handoff-1.5-to-1.6.md) | **The Mac's handoff from 1.5 to 1.6, 2026-10-22:** Mac players have 1.5.0 only (1.5.1 never reached them), so every change since that the macOS build needs, 1.5.1's repairs included, with what to do and how to check it. Read it first. |
| [macos-changes-from-windows.md](macos-changes-from-windows.md) | Retired 2026-10-22 for the file above; points to the old tracker in git history. |
| [windows-changes-from-macos.md](windows-changes-from-macos.md) | The other direction: changes the macOS build made first. |
| [macos-handoff-2026-10-09.md](macos-handoff-2026-10-09.md) | **Handoff to the Mac side, 2026-10-09:** the area map and the grown buttons after a change of resolution, the Xbox-style HUD on by default, HD icons and High FPS Fixes as options, frame rates through the game's own list, and what each asks of the Mac. Older than the 1.5 to 1.6 handoff above. |
| [macos-two-patches-handoff.md](macos-two-patches-handoff.md) | Handoff to the Mac side, 2026-10-06: KMRP and the controller as two patches. |
| [macos-standalone-kpatch-handoff.md](macos-standalone-kpatch-handoff.md) | Handoff to the Mac side, 2026-10-04: the self-contained patch and its options format. |
| [ftd-macos-upstream-audit.md](ftd-macos-upstream-audit.md) | Audit of FTD's upstream macOS patches against KMRP's. |
| [handoffs/](handoffs/) | Dated handoff notes between the Windows and Mac sides. |

## History

Records of how the project got here. Nothing in them describes the current build.

| Document | What it covers |
| --- | --- |
| [history/kpatch-runtime-design.md](history/kpatch-runtime-design.md) | The design proposal of 2026-10-03 for a self-contained patch and a separate controller patch. |
| [history/controller-handover-plan.md](history/controller-handover-plan.md) | The plan to remove the legacy controller path, which was never carried out as written; that path is no longer installed. |
| [history/v1.5-development-validation.md](history/v1.5-development-validation.md) | Dated development checks and issue disposition, 2026-09-19 to 2026-10-01. |
| [history/phase-0-plan.md](history/phase-0-plan.md) | The original proof plan for the map fix, the project's first milestone. |
| [history/technical-reconstruction/](history/technical-reconstruction/) | A long-form reconstruction of an early gold build: the Word document, a PDF render and page images. |
