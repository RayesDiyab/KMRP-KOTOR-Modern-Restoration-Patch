# Security policy

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## Scope

KMRP is a desktop patcher for a single-player 2003 game. It has no network
functionality, no telemetry, and no service component. The realistic risk is not
remote compromise but **damage to a player's game installation**, so that is what
this policy is mainly about.

The patcher modifies `swkotor.exe`, `swkotor.ini` and the `Override` folder; the
current user's Windows compatibility value for that one executable, to mark it
DPI-aware; on NVIDIA, where the driver would show half-drawn frames, that
executable's present-method profile; and, for the optional components, the
files they install beside `swkotor.exe`. Before writing, it copies the executable
and INI aside and records everything else it adds or replaces, with hashes or
prior values, in manifests used by **Restore Original**. (This paragraph listed
only the first three until 2026-09-24.)

## Reporting

Report suspected security issues, and any bug that can **destroy or fail to
restore** a player's files, privately — open a
[GitHub security advisory](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/security/advisories/new)
rather than a public issue, so it can be fixed before it is described publicly.

Please include the patcher version (Properties → Details on the executable;
KMRP 1.0 mislabels itself 2.7.0.0 there, and 1.5 shows 1.5.0.0),
your resolution, and the SHA-256 of the executable involved. **Do not attach
game executables or copyrighted game resources.**

Expect an initial response within a few days. This is a hobby project maintained
by one person; there is no paid support and no bounty.

## Things that are working as intended

These are deliberate refusals, not bugs:

- The patcher **refuses to patch an executable it does not recognise** by hash
  and length. Patching an arbitrary binary is not supported.
- It **refuses to restore an executable it did not create**, to avoid
  overwriting something it has no verified backup for.
- It **refuses to install a different resolution** over an existing install
  without a restore first, so the backup chain stays unambiguous.

## For anyone building from source

The build embeds a binary delta against a specific gold snapshot, identified by
SHA-256 in `src/patcher/KmrpPatcher.cs`. If you change the gold
snapshot, the hash constants must move with it — the patcher verifies both the
source and the result and will refuse the delta otherwise. Do not weaken those
checks to make a build work; they are the mechanism that stops a mismatched
patch from being applied to a player's game.
