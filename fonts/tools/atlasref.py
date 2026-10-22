"""The game's own letters: each glyph's cell of the HD atlas KMRP ships, as coverage, with
the placement build_hd_original_otf.py used (10 font units per atlas pixel, the baseline
at the stock font's baseline times six)."""
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]       # the KMRP checkout
sys.path.insert(0, str(ROOT / "tools"))
from build_font_from_ttf import slot_character  # noqa: E402
from build_hd_original_fonts import SCALE, Stock  # noqa: E402
from build_hd_original_otf import read_txi  # noqa: E402

ATLASES = Path(os.environ.get("KMRP_ATLASES", ROOT / "assets/hd-original-fonts"))   # another set to compare with
ORIGINALS = ROOT / "build/native-runtime/original-fonts"
RESREF = {"Menu": "dialogfont16x16", "MenuSmall": "dialogfont10x10", "MenuSmallB": "dialogfont10x10b",
          "MenuMedium": "dialogfont12x16", "MenuLarge": "dialogfont32x32", "Dialogue": "fnt_d16x16",
          "Descriptions": "fnt_d16x16b", "Credits": "fnt_credits", "CreditsBold": "fnt_creditsb",
          "Console": "fnt_console", "Light": "fnt_d16x16a"}


@lru_cache(None)
def cells(stem: str):
    """{glyph name: (coverage cell, baseline row)} for a font file stem."""
    res = RESREF[stem.split("-")[-1]]
    head, cl = read_txi(ATLASES / f"{res}.txi")
    rgba = np.asarray(Image.open(ATLASES / f"{res}.tga").convert("RGBA"))   # uint8; cells converted one by one
    H, W = rgba.shape[:2]
    baseline = round(Stock(ORIGINALS, res).baseline * SCALE)
    out = {}
    for c, (x0, y0, x1, y1) in enumerate(cl):
        ch = slot_character(c)
        if ch is None or ch == " ":
            continue
        l, t, r, b = round(x0 * W), round((1 - y0) * H), round(x1 * W), round((1 - y1) * H)
        if r <= l or b <= t:
            continue
        name = f"uni{ord(ch):04X}"
        if name not in out:
            px = rgba[t:b, l:r].astype(np.float64) / 255.0
            out[name] = (px[..., :3].mean(axis=2) * px[..., 3], baseline)
    return out
