# KOTOR Universal UI Patcher v2.0.0

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


*Historical record, labelled 2026-09-24.* This page shipped with the 2.0.0 build
of 2026-08-29, whose hash is in `SHA256.txt`, and it describes that build only.
It is kept unchanged below. The current installer differs in ways this page
could not know about. For example, its 3440×1440 output is **not**
byte-identical to the gold snapshot: it differs in 22 bytes across 17 runs,
which are the values the installer writes per resolution (see
[binary-inventory.md](../../reverse-engineering/binary-inventory.md)). For the
current build, read the [main README](../../README.md).

This is the standalone 48-resolution build. No companion files are required.

Before patching, place the Deadly Stream editable `swkotor.exe` in the game
folder and launch KOTOR once so `swkotor.ini` exists. Select the resolution,
choose **Patch Game**, and restart KOTOR before testing.

Use **Restore Original** before changing to a different resolution. This keeps
the executable, INI, and Override backup chain unambiguous.

The 3440×1440 option reproduces the confirmed gold executable exactly. Other
resolutions passed structural generation and installer/restore tests; they
should still receive representative in-game testing before a public release.

See `..\..\docs\universal-resolution-math.md` and
`..\..\THIRD_PARTY_NOTICES.md` in the source workspace for technical details,
credits, and licensing notes.
