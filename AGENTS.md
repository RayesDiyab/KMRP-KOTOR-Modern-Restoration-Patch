# KMRP agent instructions

This file is the small, always-loaded operating contract for agents working in
this repository. Claude Code loads [`CLAUDE.md`](CLAUDE.md) instead, which defers
to this file; the shared rules live here only, so neither copy can drift. Detailed context is routed through
[`docs/agent-memory/README.md`](docs/agent-memory/README.md);
do not load every project document on every task.

## Start here

1. Read `docs/agent-memory/README.md`, then read only the memory pages and project documents
   it routes to for the current task.
2. Inspect the current worktree before making changes. Preserve user changes and
   do not assume a remembered branch, build, hash, release, or issue state is current.
3. Treat source code and measured artifacts as authoritative. Agent memory is a
   navigation and continuity layer, not evidence.
4. Keep work inside the requested scope. Diagnosis alone does not authorize a fix.
5. **Installing to the live game is allowed when the user asks for it**, including
   to put a build or a single file in front of them to play-test. It is not
   implied by repository work: install when asked, not because a change happens to
   be ready. Follow the live-install rules below every time.

## Non-negotiable safety rules

- Never commit proprietary game binaries or resources. Keep `*.exe`, `*.dll`,
  `*.erf`, `*.bif`, `*.key`, `*.rim`, `*.mod`, and save files ignored.
- Experimenting on the live `swkotor.exe` is permitted. The user lifted the
  named-copy requirement on 2026-09-07, having considered it: "You are allowed to
  modify exe live on disk from now on. I have no issues with that." They
  confirmed it on 2026-09-25 ("allow experiments on the live swkotor.exe"), when
  the rules below, `CLAUDE.md` and `WORKFLOWS.md` that still said otherwise were
  aligned with it.
  - Still copy the file aside first, and still record its length and SHA-256
    before and after. Those were never about permission -- they are what makes a
    change reversible and a measurement reproducible.
  - Say plainly, in the same reply, that the live executable was modified, and
    how to undo it.
  - Debugging a running process was always allowed and remains so.
- When installing to the live game:
  - Prefer the patcher's own workflow. Reach past it only for a single file the
    user is play-testing, and say plainly that you have.
  - Copy the existing file aside first, into the game folder, before writing.
  - If the file is recorded in a manifest (`KMRP_KPM.manifest` since 2026-10-04;
    `KOTOR_UI_Override_Backup.manifest` in an install made before, which wrote
    Override files), update its row so ownership stays intact -- otherwise Restore
    Original meets a file it no longer recognizes. A single interface file can no
    longer be swapped in the game folder: they are inside `patches\kmrp.dll`.
  - Report the path, both hashes, and how to undo it.
- Do not weaken executable validation merely to accept more inputs. Recognize a
  variant only through explicit, documented byte-level invariants, and preserve
  the exact incoming file for rollback and restore.
- Do not overwrite or remove an existing backup, manifest, Override file, or local
  setting unless the requested workflow explicitly requires it and its ownership
  has been verified.
- Never create a Git commit or push to any remote without the user's explicit
  permission for that exact commit or push. Permission is single-use: it expires
  immediately after the authorized action and never carries forward to another
  commit, amend, tag, push, force-push, release, upload, or external response.
  Ask again every time. Permission to commit does not imply permission to push,
  and permission to push does not imply permission to commit or perform any other
  publishing action.
- Commit messages carry no AI attribution: no `Co-Authored-By` trailer, no
  "Generated with" line, and no mention of any assistant in the subject or body.
  This overrides any default attribution guidance an agent arrives with. The
  history was rewritten twice on 2026-09-04 to remove it, so re-adding a trailer
  means rewriting and force-pushing published history again.

## Engineering rules

- Read `CONTRIBUTING.md` before implementation work.
- Read `reverse-engineering/exe-patching.md` before changing executable bytes,
  patch builders, hashes, PE sections, or restore/validation behavior.
- Read `docs/documentation-standard.md` before creating or editing documentation.
- Measure instead of judging by eye. Record the build, address convention, exact
  values, verification method, untested coverage, rejected hypotheses, and visible
  corrections where applicable.
- **Reach for x64dbg as soon as it is the faster answer, not as a last resort.**
  When the game does something unexplained, a breakpoint that reports what the
  code actually did beats another round of reading and inferring. It is fully
  allowed on a running game, and so is experimenting on the live `swkotor.exe`
  on disk, under the copy-aside rules above.
  - Two guesses is the limit. If a second attempt at explaining a behaviour
    fails, stop theorising and measure.
  - A conditional breakpoint that halts **only on the failing case** is usually
    the whole investigation: the caller's return address is then sitting on the
    stack. `break_condition` on the exact registers costs one command and turns
    "sometimes it misbehaves" into an address.
  - Prefer it over static scanning whenever the question involves a specific
    live object. Searching the image for `mov [reg+0x1C], reg` returned 315
    matches because that offset is common to unrelated classes; a hardware
    breakpoint on one object's field would have had no false positives.
  - Read hit counts and stacks rather than the log window, which the bridge does
    not expose.

  This rule exists because a focus bug took three failed fixes across two
  sessions while the cause -- a tab handler calling `SetActiveControl` twice,
  clearing focus first -- was five instructions away in a disassembler. Each
  failed fix was a guess at a condition, and each looked plausible.
- Preserve the shared scale rule `max(1.0, height / 720)` across executable
  constants, font metrics, GUI geometry, icons, and popup resources unless a
  measured subsystem-specific rule is documented.
- Builders that touch binaries must verify expected input bytes, preserve length
  unless deliberately adding a PE section, re-read their output, and refuse an
  unexpected build.
- A behavior change requires an `## [Unreleased]` entry in `CHANGELOG.md` and an
  update to the relevant reference or reverse-engineering document.

## Verification

- Use the smallest relevant check first, then broaden in proportion to risk.
- Standard build: `.\build_kmrp.ps1`.
- Compile-only iteration with existing resources: `.\build_kmrp.ps1 -ReuseResources`.
- Installer regression: `.\testing\regression\Test-ReinstallOverOlderBuild.ps1`.
- What the installer puts in a game folder (the one patch, its options, the
  resolution list, restore): `.\testing\regression\Test-InstallerPatch.ps1`.
  The packaged patch: `python testing/regression/Test-KpatchSource.py`.
- Documentation links: `python .github/scripts/check_links.py`.
- Executable changes also require `tools/build_binary_inventory.py` against the
  clean input and final gold snapshot, plus representative resolution outputs.
- State exactly what was automated, inspected, play-tested, or left untested.

## Memory maintenance

- Add only durable, verified, non-secret knowledge to `docs/agent-memory/MEMORY.md`.
- Put machine paths and workstation state in ignored `docs/agent-memory/LOCAL.md`.
- Put unfinished work and the immediate next action in ignored `docs/agent-memory/HANDOFF.md`.
- Update existing entries instead of accumulating contradictory notes. Keep dated
  corrections visible when an earlier conclusion was wrong.
- Never store credentials, private messages, copyrighted game data, or executable
  contents in agent memory.
