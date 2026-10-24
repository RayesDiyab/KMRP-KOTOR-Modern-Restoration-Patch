"""Kerning for the 11 fonts: a GPOS `kern` feature measured from the outlines.

The letters stand flush left in their advance (all their spacing on the right, as the game
sets them), and the fonts had no kerning, so a letter with a slanted side left a wedge of
empty space beside it: the small-caps a, a triangle, read as a gap after W ("Aw areness",
2026-10-24, a modder's report). This adds pair kerning; the advance widths, the outlines
and the hints stay exactly as they are, and the game's atlases (which draw each glyph on
its own, tools/build_hd_original_atlases.py) are not touched by it.

How a pair is measured. For every height where both letters have ink, from the baseline to
the lower letter's top, the gap between the left letter's right edge and the right letter's
left edge is taken from the outlines (curves flattened, the contours cut by the line at that
height). The target is how a type designer spaces: straight against straight, round against
round, straight against round, the mean of those four pairs (H H, O O, H O, O H for
capitals; n n, o o, n o, o n for the small caps; for one of each, the left letter's two
against the right letter's two). A gap wider than CAP_GAP times the target counts as that
much, so an open side (L, the inside of a C) does not decide alone; the pair's gap is the
mean. A pair looser than its target is drawn in by KEEP of the difference, never so far
that its narrowest point comes closer than FLOOR of H H's gap, and only when that is at
least MIN_KERN units. Only tightening: a pair set closer than its target stays as the game
sets it. Tried first the same day: H H alone as the target (nearly every pair came out
loose and was drawn in alike) and the median pair of each kind (pulled up by the round and
slanted letters, so the small a stayed loose beside straight ones: "G a m" in Gamesave).

Every letter a to z and A to Z kerns as a class with its accented forms (A with Agrave,
Aacute, ...), measured on the plain letter.

Console is left without: it is monospaced (the HUD's numbers keep their columns).

    python kern.py [OTF ...]     default: every fonts/otf/*.otf but Console, rewritten in place

finish.py runs it on every font it finishes, so a rebuild keeps the kerning.
"""
import statistics
import sys
import unicodedata
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
OTF = HERE.parent / "otf"

STEP = 5          # font units between measured heights
KEEP = 0.7        # how much of the difference from the reference a pair is drawn in
FLOOR = 0.5       # the narrowest gap a kerned pair keeps, as a share of H H's gap
CAP_GAP = 2.0     # a wider gap counts as this many times the pair's target
MIN_KERN = 15     # smaller corrections are left out
ROUND = 5         # kerning values in steps of this many units


class Flatten(BasePen):
    """The outline as closed polygons, curves cut into short lines."""

    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.polys, self.cur = [], []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, 17):
            t = i / 16
            u = 1 - t
            self.cur.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                             u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 17):
            t = i / 16
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) > 1:
            self.polys.append(self.cur)
        self.cur = []

    _endPath = _closePath


def profile(font, name):
    """{height: (leftmost, rightmost) ink} every STEP units, and the glyph's top."""
    pen = Flatten(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    edges = [(a, b) for poly in pen.polys for a, b in zip(poly, poly[1:] + poly[:1]) if a[1] != b[1]]
    if not edges:
        return {}, 0
    top = max(p[1] for poly in pen.polys for p in poly)
    out = {}
    for y in range(0, int(top) + 1, STEP):
        y += 0.5
        xs = [a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) for a, b in edges if min(a[1], b[1]) <= y < max(a[1], b[1])]
        if xs:
            out[int(y)] = (min(xs), max(xs))
    return out, top


def gaps(left, right, adv):
    """The gap at every height both letters have ink."""
    return [adv - left[y][1] + right[y][0] for y in left if y in right]


def mean_gap(g, cap):
    return sum(min(x, cap) for x in g) / len(g)


def kern_font(path: Path):
    # the head's date kept: the same font kerned twice is the same file
    font = TTFont(path, recalcTimestamp=False)
    cmap = font.getBestCmap()
    hmtx = font["hmtx"].metrics
    # each plain letter and its accented forms
    classes = {}
    for code, name in cmap.items():
        base = unicodedata.normalize("NFD", chr(code))[0]
        if base.isascii() and base.isalpha() and ord(base) in cmap:
            classes.setdefault(base, set()).add(name)
    letters = sorted(classes)
    prof = {ch: profile(font, cmap[ord(ch)])[0] for ch in letters}
    adv = {ch: hmtx[cmap[ord(ch)]][0] for ch in letters}

    hh = statistics.mean(gaps(prof["H"], prof["H"], adv["H"]))
    refs = lambda ch: "HO" if ch.isupper() else "no"
    target = {}
    for left in (True, False):
        for right in (True, False):
            ra, rb = refs("A" if left else "a"), refs("A" if right else "a")
            target[left, right] = statistics.mean(statistics.mean(gaps(prof[x], prof[y], adv[x])) for x in ra for y in rb)

    pairs = []
    for a in letters:
        for b in letters:
            g = gaps(prof[a], prof[b], adv[a])
            if len(g) < 4:
                continue
            aim = target[a.isupper(), b.isupper()]
            k = KEEP * (aim - mean_gap(g, CAP_GAP * aim))
            k = max(k, -(min(g) - FLOOR * hh))       # never closer than FLOOR at its narrowest
            k = int(round(k / ROUND)) * ROUND
            if k <= -MIN_KERN:
                pairs.append((a, b, k))

    fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
    for ch in letters:
        fea.append(f"@k_{'u' if ch.isupper() else 'l'}{ch} = [{' '.join(sorted(classes[ch]))}];")
    fea.append("feature kern {")
    for a, b, k in pairs:
        ca = f"@k_{'u' if a.isupper() else 'l'}{a}"
        cb = f"@k_{'u' if b.isupper() else 'l'}{b}"
        fea.append(f"    pos {ca} {cb} {k};")
    fea.append("} kern;")
    for t in ("GPOS", "GDEF"):
        if t in font:
            del font[t]
    addOpenTypeFeaturesFromString(font, "\n".join(fea))
    font.save(path)
    return pairs


def monospaced(path: Path) -> bool:
    return "Console" in path.stem


def main():
    files = [Path(a) for a in sys.argv[1:]] or [f for f in sorted(OTF.glob("*.otf")) if not monospaced(f)]
    for f in files:
        pairs = kern_font(f)
        show = {f"{a}{b}": k for a, b, k in pairs if f"{a}{b}" in ("Ga", "am", "sa", "av", "Wa", "aw", "AV", "To", "LT", "Ta", "nn", "oo")}
        print(f"{f.name}: {len(pairs)} pairs  {show}")


if __name__ == "__main__":
    main()
