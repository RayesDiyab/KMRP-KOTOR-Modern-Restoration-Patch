# Experiment 000: Toolchain and Executable Baseline

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## Hypothesis

Codex can query x32dbg through the local MCP bridge without modifying a target,
and a dedicated clean working executable can be identified before loading it.

## Action

- Verified MCP bridge and plugin health.
- Inventoried candidate executables.
- Selected `swkotor.exe.bak` as the source for `swkotor_phase0_clean.exe`
  because it is byte-identical to the explicitly named unpatched backup.
- Created `swkotor_phase0_ultrawide.exe` from the current active executable so
  existing 3440x1440 behavior can be observed without debugging the live file.

## Observation

- MCP plugin: `x64dbg MCP Server` version 2.3.0, status `ok`.
- Debugger state before loading a target: `stopped`.
- Clean source SHA-256:
  `52AD3AE43E6D5B7ADFCE3AA240E7B26214CFE61BA9C3D9AF121DA065643E3B53`.
- The initial clean working copy loaded successfully as module
  `swkotor_phase0` before it was renamed for role clarity.
- Image base: `0x00400000`.
- Reported module entry: `0x006FB38D`.
- Initial pause: `ntdll` at `0x77BE87F9`, before game execution.
- Twenty-eight modules were present at the initial loader break.
- The debug session was stopped cleanly after the read-only identity check.

## Conclusion

The toolchain is ready for a read-only debugger baseline. No map hypothesis has
been tested and no game executable has been patched.

## Next test

Establish controlled baseline and ultrawide launch procedures, then identify the
first map-open observation points without applying any patch.
