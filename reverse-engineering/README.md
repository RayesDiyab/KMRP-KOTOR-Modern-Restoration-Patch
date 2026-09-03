# Reverse-engineering notes

How KOTOR's interface actually works, read out of the executable at runtime and
from the disassembly. One document per subsystem.

These are written for someone who was not there. They record the addresses, the
measurements, and — deliberately — **the theories that turned out to be wrong**,
with the evidence that killed them. That is not clutter: it is what stops the
same dead end from being explored a second time.

| Document | What it covers |
| --- | --- |
| [exe-patching.md](exe-patching.md) | **Read this first before touching the binary.** The invariants every tool in `tools/` shares, and the ways breaking one fails *silently* — length-changing edits that slide every later section, verification that checks only the section you touched, and the recurring "there is always a second copy" constant. |
| [map-scaling.md](map-scaling.md) | **The finished mechanism, byte for byte.** Every offset KMRP writes for the area map, how the four domains are derived per resolution, the injected wrappers, the three ways the map and HUD minimap are kept separate, and the precision lattice the design costs. Written so a collision with another executable patcher is diagnosable by someone who is not us. |
| [map.md](map.md) | The area map and HUD minimap: how the map is drawn and panned, the marker hit-test offset, the minimap content zoom, and the fog-of-war grid. Includes the corrected model of the minimap duplication — two draw calls, not a sampler wrap. |
| [font.md](font.md) | The original font and dialogue-layout work: how text size is decided, and the letterbox geometry. |
| [font-atlases.md](font-atlases.md) | The 18 font atlases — the packed/proportional format, the "one texel per pixel" rule, rendering atlases from vector outlines, and the TXI metrics that carry size. Also several of this project's own tooling bugs, kept so they are not repeated. |
| [listbox-geometry.md](listbox-geometry.md) | How a `.gui` listbox becomes rows on screen: which field controls which margin, the vanilla row-growth bug, and the method for finding the next margin. |
| [inventory-item-rows.md](inventory-item-rows.md) | Row and icon sizing for Inventory, Abilities and Store — hardcoded constants that no `.gui` edit can reach — and the stack-count label built in code. |
| [text-padding.md](text-padding.md) | Padding and gaps for **every** control type and both axes, so a change can be uniform rather than partial. Includes the survey of how many controls each mechanism actually reaches. |
| [message-popup.md](message-popup.md) | The shared message popup behind tutorial hints and confirmations: how it lays itself out, why its text was clipped, and how it is scaled to every resolution. |

## Supporting material

- [`experiments/`](experiments/) — numbered lab notes, in order, from the first
  ultrawide launch onward. Each records what was tried and what it showed,
  including the candidates that were rejected.
- [`patch-records/`](patch-records/) — machine-readable JSON descriptions of the
  confirmed map and font patches: the addresses, the original bytes and the
  replacements, so a patch can be checked without re-reading the tooling.
- [`binaries/`](binaries/) — local-only staging for analysis material.
  **Proprietary executables and debugger artifacts are never committed.**
- `map_icon_draw_wrappers*.asm` — the hand-written x86 stubs for the map marker
  wrapper, with an assembled candidate kept beside them.

## Method

The rule this project works by: **measure, do not judge by eye.** Read the value
back out of the file, capture the screen and compare pixel counts, or set a
breakpoint — then state what was measured. Several fixes here exist only because
a number disagreed with an impression.
