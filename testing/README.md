# Testing support

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


Material for checking KMRP at resolutions the build machine's monitor cannot
display, plus the installer cases that can be checked without a display at all.
Layout verification is still done by hand: patch at a resolution and compare the
result against what the tooling intended. Installer behaviour is scripted.

| | |
| --- | --- |
| [`virtual-display/`](virtual-display/) | A virtual-monitor profile exposing all 48 supported resolutions on one Windows machine, so a layout can be seen at 7680×2160 without owning such a display. |
| [`regression/`](regression/) | Scripted installer checks. Each runs the built patcher against throwaway copies of the game files and reads the result back as SHA-256. |
| `gold-geometry-diffs.txt` | A recorded field-by-field diff of GUI geometry between two builds — the format these comparisons are read in. |

## Running the installer checks

```powershell
.\build_kmrp.ps1                                        # the checks run the built patcher
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
```

Each script exits non-zero if any check fails and prints one PASS or FAIL line
per assertion. They need `build-inputs\swkotornopatch.exe`, and they patch only
throwaway copies under the system temp folder — no installed game is touched.

| Script | What it pins |
| --- | --- |
| `Test-ReinstallOverOlderBuild.ps1` | Reinstalling a newer build over an older one replaces the executable instead of skipping it; reinstalling the same build changes nothing; an unsupported executable is refused; a damaged backup blocks a patch. |

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
