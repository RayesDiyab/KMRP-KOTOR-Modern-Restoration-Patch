# Experiment 001: Controlled 3440x1440 Launch

## Hypothesis

`swkotor_phase0_ultrawide.exe` reproduces the current 3440x1440 game and broken
map behavior while allowing debugger observations without touching the live
`swkotor.exe`.

## Preconditions

- x32dbg MCP plugin health is `ok`.
- `swkotor_phase0_ultrawide.exe` SHA-256 is
  `D7DD19449F1BA2DE1D91D19E1BAA4BE15A7480AE4C9ED7F986DE5E2424E97909`.
- `swkotor.ini` requests 3440x1440 fullscreen at 60 Hz.
- No breakpoint, memory patch, or disk patch is active.

## Procedure

1. Load only `swkotor_phase0_ultrawide.exe` in x32dbg.
2. Record image base, entry point, initial modules, and initial pause location.
3. Run to the main menu without changing memory.
4. Load a known save and record the module/scene identifier.
5. Pause immediately before opening the map, while the map is displayed, and
   immediately after closing it.
6. Record visible map geometry and marker errors before tracing any functions.
7. Stop the debug session cleanly.

## Evidence to capture

- Whether the working copy reaches the main menu and loads the save normally.
- Exact visual description of the broken map.
- Relevant thread and instruction pointer at each manual pause.
- New modules or graphics state changes associated with opening the map.
- Any debugger exceptions or stability changes.

## Safety boundary

This experiment is observation-only. Do not write memory, assemble instructions,
apply patches, or export a modified executable.

