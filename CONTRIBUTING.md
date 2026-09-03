# Contributing to KMRP

Thanks for looking. This document covers how to build the project, and the
working rules it holds itself to — most of which exist because breaking them
already cost a day at some point.

## Ground rules

**Never commit game binaries or game resources.** `swkotor.exe`, `.erf`, `.bif`,
`.key`, `.rim`, `.mod` and save files are blocked in `.gitignore` and must stay
blocked. The gold snapshots live only on build machines; what the repository
records is the *chain of hashes* that identifies them, in
[docs/font-scaling.md](docs/font-scaling.md), so any of them can be rebuilt and
verified from a clean executable.

**Never experiment on the live `swkotor.exe`.** Work on a named copy, record its
SHA-256 first, and keep the verified backup the patcher makes.

**Measure; do not judge by eye.** "It looks about right" has been wrong here
often enough to be a rule. Read the value back out of the file, capture the
screen and compare pixel counts, or set a breakpoint — then say what you
measured. Several fixes in this repository were only found because a number
disagreed with an impression.

**Record what was disproved.** The reverse-engineering notes deliberately keep
theories that turned out to be wrong, with the evidence that killed them —
`spacingR` having no effect on the message popup, the minimap duplication not
being a sampler wrap. This is not clutter; it is what stops the same dead end
being explored twice. If you disprove something, write it down next to the thing
it disproves.

**Documentation has a standard, and it is written down.** Before creating or
updating any document, read [docs/documentation-standard.md](docs/documentation-standard.md).
It defines what counts as a measured claim, how offsets are tabulated, why
rejected alternatives and corrections stay visible, and the checklist to run
before committing. The benchmark is `reverse-engineering/map-scaling.md`.

**Corrections belong in the document, not only in the commit.** If a document
states something that later proves wrong, correct the document *and* say what
the earlier reading was and why it was wrong.

## Building

### Prerequisites

| | |
| --- | --- |
| .NET Framework 4.x | `csc.exe` from `C:\Windows\Microsoft.NET\Framework\v4.0.30319` |
| Python 3 | with `pykotor`; `Pillow` and `numpy` for some asset tools |
| Game files | `swpc_tex_gui.erf` and a clean `swkotor.exe`, placed in [`build-inputs/`](build-inputs/README.md) |

**The project folder is self-contained**: everything the build reads is inside
it, so it can live anywhere. Only the two game-derived files above must be
supplied, and `.gitignore` keeps them out of the repository.

Every path is still a parameter — see the `param()` block at the top of
`build_kmrp.ps1` — and can be overridden with `-SourceExe` /
`-TexturePack`, the `KMRP_*` environment variables, or a gitignored
`build.local.ps1` (copy `build.local.example.ps1`).

### Commands

```powershell
# Full build: regenerate all 48 resource archives, then compile the patcher.
.\build_kmrp.ps1

# Recompile only, reusing the resource archives from the previous run.
.\build_kmrp.ps1 -ReuseResources
```

Output lands in `dist/`. The script prints the source, gold and output hashes;
check them against the constants in `src/patcher/KmrpPatcher.cs`.

## Patching the executable

Read [reverse-engineering/exe-patching.md](reverse-engineering/exe-patching.md)
before touching the binary. It exists because these invariants were learned by
breaking them:

- **In-place edits must not change the file length.** A `bytearray` slice
  assignment of a different length *inserts* rather than overwrites, sliding
  every later section and every offset with it. Assert the length afterwards.
- **Verification must re-read every `.k??` section**, not just the one you
  touched. A fault in a section you did not edit means offsets have shifted.
- **Assume there is a second copy — and a third.** Height caps, row pitch, rect
  builders and width caps have each turned out to have two or three sites.
  Patching one and leaving the others is the most common failure mode in this
  codebase. **Finding a site means the search is incomplete, not finished:**
  disassemble the whole enclosing function, follow *every conditional branch*,
  and look for parallel constructions. The map markers took three attempts — a
  map note has separate selected and unselected draw paths, and two marker
  textures each carry their own control extent — ending at fourteen sites, with
  each missed layer found only after a play-test said the change had not worked.
  Report the count and how you established it, not just the change.
- **Disassemble stubs from the raw bytes** you wrote, not from the assembly you
  intended to write.

New engine code goes into its own PE section (`.kui`, `.klb`, `.kfs`, `.kwl`,
`.ksc`, `.kgs`, `.ktn`, `.kmz`, `.kfg`) via a builder in `tools/`; simple
constant changes are in-place `imm32` rewrites. Each builder verifies the bytes
it expects to find before writing anything, and refuses to proceed otherwise —
keep that pattern.

## Resolution scaling

Anything sized in pixels must scale by `max(1.0, height / 720)`, the same rule
used by the font metrics (`font_scale_for` in
`tools/prepare_universal_resources.py`) and by the executable constants
(`ScaleForHeight` in `src/patcher/KmrpPatcher.cs`). **If you change one
side, change the other**: a `.gui` layout and the executable constants that
interact with it must be generated from the same scale or they drift apart at
every resolution except the one you tested.

Verify across the range, not just your own monitor. The practical check is to
build, run `--apply` at several resolutions, and read the values back out of the
resulting executables and archives.

## Pull requests

- One subject per pull request.
- Say what you **measured**, and how. Include the numbers.
- Note anything you could not verify, and say so plainly rather than implying
  coverage you do not have.
- Update the affected document(s) in `docs/` or `reverse-engineering/` in the
  same change.
- Add a `CHANGELOG.md` entry under `## [Unreleased]`.

Commit messages in this repository are long-form on purpose: they explain the
cause, not just the change. Follow that where it helps.

## Reporting problems

Open an issue using the templates in `.github/ISSUE_TEMPLATE`. For anything
touching backups, restore, or an executable that will not patch, include your
resolution, the patcher version from the executable's Properties → Details tab,
and the relevant hashes. Please do not attach game executables.
