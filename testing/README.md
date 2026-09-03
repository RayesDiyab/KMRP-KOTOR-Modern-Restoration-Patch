# Testing support

Material for checking KMRP at resolutions the build machine's monitor cannot
display. There is no automated test suite: verification here is done by patching
at a resolution and comparing the result against what the tooling intended.

| | |
| --- | --- |
| [`virtual-display/`](virtual-display/) | A virtual-monitor profile exposing all 48 supported resolutions on one Windows machine, so a layout can be seen at 7680×2160 without owning such a display. |
| `gold-geometry-diffs.txt` | A recorded field-by-field diff of GUI geometry between two builds — the format these comparisons are read in. |

## What is deliberately not committed

Two kinds of file under `virtual-display/` are ignored rather than stored:

- **`verify-*/` run artifacts** — the ~80 `.gui` files a patcher run emits at one
  resolution, in a timestamped folder. They are build output: regenerate them by
  running the patcher at that resolution rather than keeping a copy.
- **The virtual display driver package** — a signed third-party download. The
  upstream project and the expected SHA-256 are recorded in
  [`virtual-display/README.md`](virtual-display/README.md), which is what makes
  storing 200 MB of it unnecessary.

## Checking a resolution

```powershell
# Patch a throwaway copy at the resolution under test, then read the values back.
& '.\dist\KMRP - KOTOR Modern Restoration Patch.exe' --apply .\clean\swkotor.exe .\out\swkotor-7680.exe 7680x2160
```

Then compare the generated `gui-<resolution>.zip` and the patched executable's
constants against what the scaling rule predicts — see
[CONTRIBUTING.md](../CONTRIBUTING.md#resolution-scaling). Read the numbers back;
do not judge a layout by eye.
