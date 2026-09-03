#!/usr/bin/env python3
"""Measure the area map screen from a full-screen capture.

Written because four rounds of this investigation were argued from eyeballed
screenshots and three of them reached the wrong conclusion. Every number this
prints is reproducible from the PNG alone.

**What it separates.** Three things on the map screen look blue and are easy to
confuse:

* the **fog grid** -- the unexplored tiles the area map draws. Dark navy fill
  (`b` about 21) with bright grid lines (`b` > 45, `r` < 15) on a regular pitch.
* the **panel background art** -- a *dimmer* grid baked into the screen's own
  texture, present outside the map surface entirely.
* the **frame art** -- the rounded border, bright but not on a grid pitch.

They are told apart by pitch and by run length, not by colour: the fog grid is
the only one whose bright columns repeat at a constant spacing across a wide
run. `--debug-profile` prints the raw per-bucket counts so a disagreement can be
settled by looking at the same numbers.

**What it reports**, all in screen pixels:

* `grid`      -- first and last column carrying fog-grid lines
* `revealed`  -- columns where the map texture shows through (explored ground
                 *and* any surface region no fog tile covers, which is what the
                 right-hand strip is)
* `strip`     -- the trailing revealed run that reaches the right edge of the
                 map surface with no grid over it

Usage:

    python tools/measure_map_screen.py shot.png
    python tools/measure_map_screen.py shot.png --json out.json
    python tools/measure_map_screen.py shot.png --debug-profile

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


# Colour gates, measured off 3440x1440 captures of the Manaan West Central map.
# Sampled row 717 of map-derslok-consts.png: fog fill (0,0,21..23), fog grid
# lines (0,38,71) and (0,77,123), revealed texture (38,47,63)..(66,74,81).
GRIDLINE_BLUE_MIN = 45
GRIDLINE_RED_MAX = 15
REVEALED_RED_MIN = 30

# The vertical band to look in, as a fraction of screen height. The map surface
# sits inside this at every resolution KMRP ships; the tabs above and the
# buttons below are excluded so their art cannot be mistaken for grid.
BAND_TOP = 0.25
BAND_BOTTOM = 0.78


def columns(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    height = image.shape[0]
    band = image[int(height * BAND_TOP):int(height * BAND_BOTTOM)]
    red, _green, blue = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    gridline = (blue > GRIDLINE_BLUE_MIN) & (red < GRIDLINE_RED_MAX)
    revealed = red > REVEALED_RED_MIN
    return gridline.sum(axis=0), revealed.sum(axis=0), band.shape[0]


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs as (first, last) inclusive column indices."""
    result: list[tuple[int, int]] = []
    start = None
    for index, flag in enumerate(mask):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            result.append((start, index - 1))
            start = None
    if start is not None:
        result.append((start, len(mask) - 1))
    return result


def keep_regular(candidates: list[tuple[int, int]],
                 tolerance: float = 0.22) -> tuple[list[tuple[int, int]], float | None]:
    """Keep only the runs that sit on a regular pitch.

    The frame border is bright, blue and full-height, exactly like a fog grid
    line, so a colour test alone cannot reject it -- an earlier version of this
    tool reported the frame as the grid's right edge and put it 38 px past the
    map surface. What separates them is that fog grid lines repeat at a constant
    spacing and the frame does not: it stands alone, past a gap much larger than
    the pitch.

    The pitch is taken as the median gap between consecutive run centres, then
    runs whose gap to *both* neighbours disagrees with it are dropped. Returns
    the surviving runs and the pitch.
    """
    if len(candidates) < 3:
        return candidates, None
    centres = [(a + b) / 2 for a, b in candidates]
    gaps = [centres[i + 1] - centres[i] for i in range(len(centres) - 1)]
    pitch = float(sorted(gaps)[len(gaps) // 2])
    if pitch <= 0:
        return candidates, None

    def fits(gap: float) -> bool:
        return abs(gap - pitch) <= pitch * tolerance

    kept = []
    for index, run in enumerate(candidates):
        before = fits(gaps[index - 1]) if index > 0 else False
        after = fits(gaps[index]) if index < len(gaps) else False
        if before or after:
            kept.append(run)
    return kept, round(pitch, 2)


def measure(path: Path, debug: bool = False) -> dict:
    image = np.asarray(Image.open(path).convert("RGB")).astype(int)
    height, width = image.shape[0], image.shape[1]
    grid_counts, revealed_counts, band_height = columns(image)

    # A fog-grid column is one where a bright line covers a large part of the
    # band. Grid lines run the full height of the surface, so this rejects the
    # frame art (short bright runs) and the background grid (dim, below the
    # colour gate) without needing to know where the surface is.
    grid_col = grid_counts > band_height * 0.30
    revealed_col = revealed_counts > band_height * 0.30

    all_runs = runs(grid_col)
    grid_runs, pitch = keep_regular(all_runs)
    result: dict = {
        "image": str(path),
        "screen": {"width": width, "height": height},
        "band": {"top": int(height * BAND_TOP), "bottom": int(height * BAND_BOTTOM)},
    }

    if grid_runs:
        first, last = grid_runs[0][0], grid_runs[-1][1]
        result["grid"] = {"first": int(first), "last": int(last),
                          "width": int(last - first + 1),
                          "line_columns": len(grid_runs),
                          "pitch": pitch,
                          "rejected_runs": [{"first": int(a), "last": int(b)}
                                            for a, b in all_runs
                                            if (a, b) not in grid_runs]}
    else:
        result["grid"] = None

    revealed_runs = runs(revealed_col)
    result["revealed_runs"] = [{"first": int(a), "last": int(b),
                                "width": int(b - a + 1)} for a, b in revealed_runs]

    # The strip: a revealed run that begins at or after the last grid column.
    if grid_runs:
        last_grid = grid_runs[-1][1]
        trailing = [r for r in revealed_runs if r[0] >= last_grid - 2]
        if trailing:
            a, b = trailing[0]
            result["strip"] = {"first": int(a), "last": int(b), "width": int(b - a + 1)}
        else:
            result["strip"] = None

    if debug:
        result["profile"] = [
            {"x": x, "gridline_px": int(grid_counts[x:x + 40].sum()),
             "revealed_px": int(revealed_counts[x:x + 40].sum())}
            for x in range(0, width, 40)
            if grid_counts[x:x + 40].sum() or revealed_counts[x:x + 40].sum()
        ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--debug-profile", action="store_true")
    args = parser.parse_args()

    result = measure(args.image, debug=args.debug_profile)
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
