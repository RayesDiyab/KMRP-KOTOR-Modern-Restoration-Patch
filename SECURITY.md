# Security policy

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## Scope

KMRP is a desktop patcher for a single-player 2003 game. It has no telemetry
and no service component, and one network request: the update check below. The
realistic risk is not remote compromise but **damage to a player's game
installation**, so that is what this policy is mainly about. (Until 2026-09-25
this said KMRP had no network functionality, which was true until the update
check was added that day.)

**The update check.** When the installer's window opens, it makes one HTTPS
request, to `api.github.com/repos/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases/latest`.
- **Sent:** only the User-Agent `KMRP/<version>` that GitHub requires. There
  is no identifier, nothing about the machine, and nothing about the game.
- **Not sent:** the command-line modes never make the request.
- **Read:** only the release's tag name, and only as digits and dots.
- **Link:** the dialog's Download button opens a Deadly Stream address compiled
  into the installer, never one from the answer.
- **Failures:** any failure is silent, including a five-second timeout.

The patcher modifies `swkotor.ini`; one bit of `swkotor.exe`'s header, the Large
Address Aware flag, on GOG's and the editable builds (Steam's executable is never
changed); the files beside `swkotor.exe` that make up KOTOR Patch Manager's runtime
and KMRP's patch, with the game's `binkw32.dll` renamed; the
current user's Windows compatibility value for that one executable, to mark it
DPI-aware; on NVIDIA, where the driver would show half-drawn frames, that
executable's present-method profile; and, for the optional driver-compatibility
component, the two files it installs beside `swkotor.exe`. Before writing, it
copies the INI and the unmodified executable aside and records everything it adds,
renames or sets, with hashes or prior values, in manifests used by **Restore
Original**. While the game runs, KMRP's module unpacks interface files to a folder
of its own under the user's temporary folder and removes it when the game closes.
(This paragraph listed only the first three items until 2026-09-24, and said the
patcher modified the `Override` folder until 2026-10-04: it no longer writes
there, and only removes what an older KMRP put there.)

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
- Installing over an existing KMRP install **restores that install first**, from
  its own records, and only then installs, so the backup chain stays unambiguous.
  (Until 2026-10-04 this said it refused a different resolution over an existing
  install; no resolution is installed any more.)

## For anyone building from source

The engine changes are built from tracked source, each with the original
instruction bytes it expects (`tools/build_windows_engine.py`), and KMRP's module
checks those bytes in the running game before it changes anything; the installer
recognises an executable by SHA-256 (`GameExecutable` in
`src/patcher/KmrpPatcher.cs`). Do not weaken those checks to make a build work;
they are the mechanism that stops a mismatched patch from being applied to a
player's game. (Until 2026-10-01 the build embedded a binary delta against a gold
snapshot, and this section described that.)
