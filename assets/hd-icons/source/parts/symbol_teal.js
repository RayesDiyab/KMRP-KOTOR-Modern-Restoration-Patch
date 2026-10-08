'use strict';
// The teal plate of the upgrade items and the line of light round the black silhouette that lies on it.
// The GAME's icons give the design (the user: "look at vanilla for simple shapes as inspiration not chatgpt"): every
// number below is read off the game's 64 pixel icons (one pixel = half a unit), with tools/teal_arch.py (the plate's
// outline from its opacity), tools/teal_tex.py (the plate's own drawing with the silhouettes taken out) and
// tools/teal_sil.py (the silhouettes pixel for pixel). ChatGPT's redraws were used only to see what a thing is.
// They redraw the plate with a tab and sloped shoulders where the game has an arch, give it a bright border the
// game has not, and fatten the line of light to 0.6 with a glow 0.8 wide; none of that is taken over.
//
// What the game has:
//  - TWO plate outlines, pixel for pixel the same within each group: an arch at the top and a notch in the bottom
//    (armorrein, beam, energy, hair, scope), and a tab at the top with the same arch at the bottom (durasteel,
//    imp_eng, powerc, vcell). Both are 21.5 wide about x = 15.75.
//  - THREE drawings of circuit lines on it: one under beam, energy, hair and scope (the dark plate), one under
//    durasteel, imp_eng, powerc and vcell (lighter, lit from the upper left), and a third under armorrein.
//  - The line of light is one pixel (0.5) of 14,255,255 with no glow beside it; only the crystal has a glow.
// Units: the frame is 32 x 32, y down.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const { clamp } = S;

const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

// ---- the plate's outline -----------------------------------------------------------------------------------------
// Sides at x = 5.0 and 26.5 (pixels 10 to 52). The arch is a circle of radius 30.355 (fitted to the opacity of its
// edge pixels within 0.03): at the top about (15.75, 33.834), which puts its crown at y = 3.479 and its ends at
// 5.446; at the bottom the same circle turned over, about (15.75, -2.334): crown 28.021, ends 26.054.
// The notch: 2.5 deep, 8 wide at its floor (y = 25.5) and 13 at the plate's lower edge (y = 28), sides at 45 degrees.
// The tab: 2.5 high, 6 wide at its top (y = 3.5) and 11 at its foot (y = 6), sides at 45 degrees.
const CX = 15.75, HALF = 10.75, ARCH_R = 30.355, ARCH_TOP = 33.834, ARCH_BOTTOM = -2.334;
const archSpan = (Math.asin(HALF / ARCH_R) * 180) / Math.PI;
const OUTLINE = {
  arch: [...G.arcPts(CX, ARCH_TOP, ARCH_R, -90 - archSpan, -90 + archSpan), [26.5, 28], [22.25, 28], [19.75, 25.5], [11.75, 25.5], [9.25, 28], [5, 28]],
  tab: [[5, 6], [10.25, 6], [12.75, 3.5], [18.75, 3.5], [21.25, 6], [26.5, 6], ...G.arcPts(CX, ARCH_BOTTOM, ARCH_R, 90 - archSpan, 90 + archSpan)],
};
const shapes = {};
const plateShape = (kind) => shapes[kind] || (shapes[kind] = S.polygon(OUTLINE[kind]));

// ---- the plate's own drawing ---------------------------------------------------------------------------------------
// Each drawing is a tone that changes evenly across the plate, lighter and darker panels, and lines. Lines and panels
// are given in the game's own pixels, [first column, first row, last column, last row, strength]: a line one pixel
// wide is a column (or a row) of pixels, a pad is a block of them. Drawn here, such a line is 0.46 wide at half its
// height (the game's pixel is 0.5) with soft sides, and a pad is a block with the same soft sides; their corners are
// square. Strength 1 adds `add` to the plate's tone at the line's crest (what makes a line's pixel in the game as
// bright as it is there, a pixel being 0.85 of the crest on average).
//   tone: green = g0 + gx (x - 15.75) + gy (y - 15.75); blue is 1.32 times green, red 0 (the plate's tones in the game
//         keep that proportion: 0,46,61 on the dark plate, 0,65,86 on the light one)
//   rim:  the plate's edge is a little lighter than the plate (in the game the dark plate's left edge is 20 levels
//         lighter than the pixels beside it, its lower edges 20, its right 10, its top 5; the light plate's tab and
//         shoulders 20 to 25, its other edges under 10): strength at the edge, and how much more it is on the left
//         and on the lower (negative: the upper) edges
const TEX = {
  // beam, energy, hair, scope. Tone 0,47,62 all over (46 to 48 in the panels, 52 near the top).
  dark: {
    tone: [47, 0, 0], add: [12, 64, 76], rim: { g: 13, left: 0.6, down: 0.45 },
    panels: [[10, 23, 15, 28, 0.42]],                                       // the pad on the left edge (68 to 75 against 47)
    lines: [
      [30, 5, 31, 10, 1.0], [27, 11, 31, 11, 1.0], [27, 11, 27, 25, 1.0, 0.07], [27, 23, 30, 25, 1.0],   // down from the top, a step left, down to a pad
      [23, 5, 23, 22, 0.4],                                                 // a faint line beside it
      [40, 5, 40, 12, 0.6], [33, 12, 40, 12, 0.5], [34, 12, 34, 18, 0.5], [34, 18, 43, 18, 0.5], [42, 18, 43, 26, 0.45],   // the hook at the upper right
      [45, 26, 49, 26, 0.4], [45, 29, 49, 29, 0.5], [45, 26, 45, 39, 0.35], [48, 26, 48, 35, 0.22],      // a small frame under it, two faint lines on down
      [51, 36, 53, 37, 1.0],                                                // a bright pad on the right edge
      [10, 23, 15, 23, 0.75], [15, 23, 15, 28, 0.75], [10, 28, 15, 28, 0.75],                           // the left pad's brighter edges
      [9, 45, 24, 45, 0.75], [24, 41, 24, 45, 0.7], [24, 41, 29, 42, 0.6], [29, 41, 29, 51, 0.65],      // in from the left, a step up, down to the notch
      [38, 40, 45, 40, 0.6], [38, 46, 45, 46, 0.65], [38, 40, 38, 46, 0.8], [45, 40, 45, 48, 0.8], [40, 42, 42, 43, 0.7],   // the box with its dot
      [33, 42, 38, 42, 0.55], [34, 39, 34, 42, 0.4],                        // a stub into the box's left side
      [46, 48, 53, 48, 0.7], [45, 48, 45, 51, 0.5], [45, 51, 51, 51, 0.5],  // out to the right edge under the box
    ],
  },
  // durasteel, imp_eng, powerc, vcell. Tone 0,64,84 in the middle, 0.8 more per unit to the left and 0.3 per unit
  // upwards (85 at the upper left, 56 at the right, 50 at the bottom).
  light: {
    tone: [64, -0.8, -0.3], add: [8, 75, 98], rim: { g: 9, left: 0.3, down: -0.9 },
    panels: [[10, 12, 19, 21, 0.2], [28, 46, 39, 51, -0.16], [10, 47, 12, 51, 0.3]],                    // lighter upper left, the dark field at the bottom, a light block
    lines: [
      [31, 5, 31, 17, 0.45], [24, 6, 24, 18, 0.36],                         // two lines down from the tab
      [47, 12, 48, 15, 0.9], [44, 16, 48, 17, 0.95], [44, 16, 44, 27, 0.85],   // the hook at the upper right
      [44, 32, 48, 33, 0.4], [48, 33, 48, 37, 0.28], [48, 37, 53, 37, 0.35],  // a faint step out to the right edge
      [13, 36, 18, 37, 0.8], [13, 37, 13, 46, 0.75], [9, 46, 13, 46, 0.78],   // the hook at the lower left
      [21, 45, 24, 45, 0.7], [25, 45, 33, 45, 0.35], [34, 45, 41, 45, 0.5], [47, 45, 53, 45, 0.65],     // a line across under the middle
      [41, 45, 41, 56, 0.7], [47, 45, 47, 48, 0.6], [46, 48, 47, 54, 0.85],                             // two lines down from it
      [26, 46, 27, 52, 0.36], [26, 52, 33, 52, 0.36],                       // the dark field's faint left and lower edge
      [19, 52, 21, 55, 0.65],                                               // a pad on the lower edge
    ],
  },
  // armorrein (the shirt hides most of it). Tone 0,59,79 along the top, 85 at the lower left.
  shirt: {
    tone: [66, -0.55, 0.75], add: [0, 70, 95], rim: { g: 8, left: 0.4, down: 0.2 },
    panels: [[34, 10, 40, 11, 0.22], [13, 33, 16, 56, 0.3]],
    lines: [
      [20, 5, 21, 13, 0.4], [24, 5, 25, 13, 0.2], [43, 5, 43, 13, 0.22],
      [9, 13, 12, 13, 0.6], [12, 13, 12, 18, 0.5],
      [13, 28, 13, 33, 0.5], [9, 45, 13, 46, 0.4],
      [49, 28, 49, 35, 0.54], [48, 37, 53, 38, 0.87], [48, 37, 48, 45, 0.7], [46, 45, 48, 45, 0.6],
      [28, 49, 32, 50, 0.4], [38, 49, 38, 50, 0.5],
    ],
  },
};
const CORE = 0.12, SOFT = 0.13;        // a line's flat middle (half-width) and how its sides fall off: exp(-((d - CORE) / SOFT)^2)
// pixels to units: the middle of pixel n lies at (n + 0.5) / 2
const cells = (list) => {
  const n = list.length, f = new Float64Array(n * 6);
  list.forEach((e, i) => f.set([(e[0] + 0.5) / 2, (e[1] + 0.5) / 2, (e[2] + 0.5) / 2, (e[3] + 0.5) / 2, e[4], CORE + (e[5] || 0)], i * 6));
  return { n, f };
};
// How strongly the lines (or panels) show at a place. The distance to a block of pixels is measured squarely (across
// it and beyond its ends alike), so corners and ends are square at every strength. Lines: the strongest one there
// (two lines that meet do not add up to a bright knot). Panels: added together.
const strongest = ({ n, f }) => (x, y) => {
  let v = 0;
  for (let i = 0; i < n * 6; i += 6) {
    const dx = Math.max(f[i] - x, x - f[i + 2], 0), dy = Math.max(f[i + 1] - y, y - f[i + 3], 0), d = (dx > dy ? dx : dy) - f[i + 5];
    if (d > 0.45) continue;
    const w = f[i + 4] * (d <= 0 ? 1 : Math.exp(-(d * d) / (SOFT * SOFT)));
    if (w > v) v = w;
  }
  return v;
};
const summed = ({ n, f }) => (x, y) => {
  let v = 0;
  for (let i = 0; i < n * 6; i += 6) {
    const dx = Math.max(f[i] - x, x - f[i + 2], 0), dy = Math.max(f[i + 1] - y, y - f[i + 3], 0), d = (dx > dy ? dx : dy) - 0.25;   // a panel reaches to its pixels' edges
    if (d > 0.9) continue;
    v += f[i + 4] * (d <= 0 ? 1 : Math.exp(-(d * d) / (0.3 * 0.3)));
  }
  return v;
};
const built = {};
const texture = (name) => built[name] || (built[name] = { ...TEX[name], line: strongest(cells(TEX[name].lines)), panel: summed(cells(TEX[name].panels)) });

// ---- the line of light -------------------------------------------------------------------------------------------
// One game pixel wide: 0.5. In the game it is flat 14,255,255 (84,255,255 round the shirt), hard against the plate
// on one side and the black on the other: no glow lies beside it. Here its colour deepens a little to both edges
// from a lighter crest along its middle (light falls off within the line, not beyond it).
const LIGHT = { width: 0.5, edge: [0, 206, 226], body: [14, 255, 255], crest: [96, 255, 255] };

// The plate. opts: kind ('arch' | 'tab'), tex ('dark' | 'light' | 'shirt'),
//   glow    { at: [x, y], full, end, colour }: a round light on the plate, at full strength within `full` of its
//           middle and gone at `end` (the crystal's); gap: the shape round which the plate stays dark, and how far
const plate = (c, { kind = 'arch', tex = 'dark', glow = null } = {}) => {
  const shape = plateShape(kind), T = texture(tex), [g0, gx, gy] = T.tone, add = T.add, rim = T.rim;
  const gapField = glow && glow.gap ? c.field(glow.gap) : null;
  c.fill(shape, (px) => {
    let g = g0 + gx * (px.x - CX) + gy * (px.y - CX), r = 0;
    const depth = -px.d;
    if (depth < 1.6) g += rim.g * Math.exp(-depth / 0.32) * Math.max(1 - rim.left * px.gx + rim.down * px.gy, 0.15);
    g += add[1] * T.panel(px.x, px.y);
    let b = 1.32 * g;
    const l = T.line(px.x, px.y);
    if (l > 0) { r += add[0] * l; g += add[1] * l; b += add[2] * l; }
    if (glow) {
      let e = 1 - smooth(glow.full, glow.end, Math.hypot(px.x - glow.at[0], px.y - glow.at[1]));
      if (gapField) e *= smooth(glow.gapWidth * 0.75, glow.gapWidth * 1.25, gapField[px.i]);
      r += (glow.colour[0] - r) * e; g += (glow.colour[1] - g) * e; b += (glow.colour[2] - b) * e;
    }
    px.r = r / 255; px.g = g / 255; px.b = b / 255; px.a = 1;
  });
  return shape;
};

// ---- silhouettes -------------------------------------------------------------------------------------------------
const BLACK = '#000000';
// The line of light as a band: `lit` is everything that is not plate (the silhouette with its line), `black` what
// lies inside the line. Across the band the colour runs from LIGHT.edge at both edges through LIGHT.body to
// LIGHT.crest along the middle.
const lightBand = (c, lit, black, clip, light = LIGHT) => {
  const lf = c.field(lit), bf = c.field(black), ramp = P.ramp([[0, light.edge.map((v) => v / 255)], [0.45, light.body.map((v) => v / 255)], [1, light.crest.map((v) => v / 255)]]);
  c.fill(clip ? S.intersect(lit, clip) : lit, (px) => {
    const out = Math.max(-lf[px.i], 0), inn = Math.max(bf[px.i], 0);
    ramp(1 - Math.abs((2 * out) / (out + inn + 1e-9) - 1), px); px.a = 1;          // 1 on the band's middle
  });
};

// One icon: the plate, and on it the silhouettes.
//   bodies   the silhouettes. Either a list of points: the silhouette's OUTER edge (the line of light is its outer
//            `width`, the black lies inside; corners stay sharp on both sides of the line, as the game's pixels are).
//            Or { middle: points }: the MIDDLE of its line of light, as tools/teal_ridge.py measures it where the
//            game's line is blurred; the line then lies half its width to either side, exactly as wide all along.
//   islands  places inside a silhouette where the plate shows again; the line of light runs round each, outside it
//            (on the black's side). A list of points (the edge of the plate there) or { middle: points }.
//   glow     see plate; with `gap` true the plate stays dark for glow.gapWidth round the silhouettes
const icon = (c, { kind = 'arch', tex = 'dark', bodies = [], islands = [], width = LIGHT.width, glow = null, light = LIGHT } = {}) => {
  const poly = (pts) => S.polygon(pts, undefined, 'nonzero'), any = (list) => (list.length > 1 ? S.union(...list) : list[0]);
  const whole = any(bodies.map((b) => (b.middle ? S.grow(poly(b.middle), width / 2) : poly(b))));
  const inside = any(bodies.map((b) => (b.middle ? S.grow(poly(b.middle), -width / 2) : poly(G.offsetPts(b, -width)))));
  const isle = islands.length ? any(islands.map((b) => (b.middle ? S.grow(poly(b.middle), -width / 2) : poly(b)))) : null;
  const isleOut = islands.length ? any(islands.map((b) => (b.middle ? S.grow(poly(b.middle), width / 2) : poly(G.offsetPts(b, width))))) : null;
  const lit = isle ? S.subtract(whole, isle) : whole;                    // everything that is not plate
  const black = isleOut ? S.subtract(inside, isleOut) : inside;
  const shape = plate(c, { kind, tex, glow: glow ? { ...glow, gap: glow.gapWidth ? lit : null } : null });
  lightBand(c, lit, black, shape, light);
  c.fill(S.intersect(black, shape), P.flat(BLACK));
  return { shape, lit, black };
};

// ---- helpers for outlines ----------------------------------------------------------------------------------------
// a shape that is the same left and right of x = ax: its right half as [distance from the axis, y], from the top of
// the axis round to its bottom
const mirrored = (ax, half) => half.map(([h, y]) => [ax + h, y]).concat(half.filter(([h]) => h > 1e-9).map(([h, y]) => [ax - h, y]).reverse());
// points given along an axis: [u, v] with u along the direction `deg` (y down) from `at` and v across it, to the
// right of that direction as seen on screen
const turned = (at, deg, pts) => { const f = G.frameAt(at, deg, 1); return pts.map(([u, v]) => f.pt(u, v)); };
// Outlines measured on the MIDDLE of the game's line of light (tools/teal_ridge.py finds it to a fraction of a pixel
// where the line is blurred): the silhouette's outer edge lies half the line's width outside it.
const outerOf = (middle, width = LIGHT.width) => G.offsetPts(middle, width / 2);
// the two points where the circles (c1, r1) and (c2, r2) meet: first the one to the left of the way from c1 to c2
// (as seen on screen), then the one to the right
const meet = (c1, r1, c2, r2) => {
  const dx = c2[0] - c1[0], dy = c2[1] - c1[1], d = Math.hypot(dx, dy), a = (r1 * r1 - r2 * r2 + d * d) / (2 * d), h = Math.sqrt(Math.max(r1 * r1 - a * a, 0));
  const mx = c1[0] + (a * dx) / d, my = c1[1] + (a * dy) / d;
  return [[mx + (h * dy) / d, my - (h * dx) / d], [mx - (h * dy) / d, my + (h * dx) / d]];
};
// the direction from c to p in degrees (y down: 90 is straight down)
const degOf = (c, p) => (Math.atan2(p[1] - c[1], p[0] - c[0]) * 180) / Math.PI;
// an arc about c from the direction of p to the direction of q; `turn` +1 goes clockwise on screen (rising angle), -1 the other way
const arcBetween = (c, r, p, q, turn = 1) => {
  let a0 = degOf(c, p), a1 = degOf(c, q);
  if (turn > 0) { while (a1 < a0) a1 += 360; } else { while (a1 > a0) a1 -= 360; }
  return G.arcPts(c[0], c[1], r, a0, a1);
};

module.exports = { CX, HALF, OUTLINE, TEX, plateShape, plate, icon, lightBand, LIGHT, smooth, BLACK, mirrored, turned, outerOf, meet, degOf, arcBetween };
