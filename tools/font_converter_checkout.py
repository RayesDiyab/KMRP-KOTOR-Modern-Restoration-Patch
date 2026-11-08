"""Where the KOTOR-KMRP Font Converter repository is, for KMRP's tools that read the KMRP
Original HD fonts.

The fonts (fonts/otf) and their redraw tools (fonts/tools) moved out of this repository on
2026-11-08, with the KMRP Font Converter, into their own: KOTOR-KMRP Font Converter,
https://github.com/RayesDiyab/KOTOR-KMRP-Font-Converter. KMRP still ships its HD Font: the
atlases drawn from those fonts stay here in assets/hd-original-fonts, and no build reads
the fonts. Only drawing the atlases again (tools/build_hd_original_atlases.py) and the
controller glyph vectors' outline tools (tools/build_controller_glyph_vectors.py) need the
other repository, found in this order:

  1. the folder named by the KMRP_FONT_CONVERTER environment variable;
  2. a folder next to this checkout named "KOTOR-KMRP Font Converter" or
     "KOTOR-KMRP-Font-Converter" (the maintainer's and GitHub's names).
"""
import os
from pathlib import Path

KMRP = Path(__file__).resolve().parents[1]
NAMES = ("KOTOR-KMRP Font Converter", "KOTOR-KMRP-Font-Converter")


def font_converter_root():
    """The KOTOR-KMRP Font Converter checkout; stops with a message when there is none."""
    named = os.environ.get("KMRP_FONT_CONVERTER")
    candidates = [Path(named)] if named else []
    candidates += [KMRP.parent / name for name in NAMES]
    for candidate in candidates:
        if (candidate / "fonts" / "otf").is_dir() and (candidate / "fonts" / "tools").is_dir():
            return candidate
    raise SystemExit("The KMRP Original HD fonts are in the KOTOR-KMRP Font Converter repository since "
                     "2026-11-08: clone it next to this checkout, or set KMRP_FONT_CONVERTER to it.")
