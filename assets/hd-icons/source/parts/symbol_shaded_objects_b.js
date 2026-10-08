'use strict';
// Objects of the sheet symbol_shaded_objects, second part: the cube of the three red Force icons (hold, push,
// breach), the hand under it, the pushing arrow and the bolt.
//
// The GAME's icon gives each design: outline, proportions, what lies in front of what, where each colour is (read off
// its pixels with tools/vmap.py, tools/objects_b_px.py and tools/objects_b_runs.py, which gives an edge's place to a
// fraction of a pixel). ChatGPT's redraw only shows what a thing is. Every outline is made of straight lines and
// circular arcs with stated dimensions; black borders are laid first; shading is formulas and stays soft and
// structural: a face that falls from a lit side to a shaded one, light along an edge, a thin dark line on the outline.
// Units: the vanilla icon's pixels (frame 32 x 32, y down). The light stands above and to the left, as in the game.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');

const INK = '#0a0a0c';
// The black line round a body: one unit, the one pixel of the game's icons, as on the rest of this sheet
// (parts/symbol_shaded_objects.js). RIM: the thin dark line along the very edge of a body, as on the other sheets.
const BORDER = 1.0;
const RIM = 0.13;

const { clamp } = S;
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c, a = 1) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = a; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bell = (d, w) => Math.exp(-(d * d) / (w * w));
// a colour ramp that returns the colour (linear light): stops = [[t, '#rrggbb'], ...] with t rising
const ramp = (stops) => {
  const ts = stops.map((s) => s[0]), cs = stops.map((s) => lin(s[1]));
  return (t) => {
    let i = 0;
    while (i < ts.length - 2 && t > ts[i + 1]) i++;
    return mix3(cs[i], cs[i + 1], clamp((t - ts[i]) / (ts[i + 1] - ts[i] || 1e-9), 0, 1));
  };
};
// a curve through measured values: stops = [[t, value], ...] with t rising, straight between them
const curve = (stops) => (t) => {
  let i = 0;
  while (i < stops.length - 2 && t > stops[i + 1][0]) i++;
  const a = stops[i], b = stops[i + 1];
  return a[1] + (b[1] - a[1]) * clamp((t - a[0]) / (b[0] - a[0] || 1e-9), 0, 1);
};
const rect = (x0, y0, x1, y1) => S.box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2);
// one pixel of soft edge where a formula changes colour across the line v = 0 (v in units, k pixels per unit)
const step = (v, k) => clamp(v * k + 0.5, 0, 1);
// a closed outline from points with rounded corners: [[x, y] or [x, y, r], ...] -> its points
const outline = (pts) => S.roundedPoints(pts, 0, 0.06);

// ---- the game's colours ----------------------------------------------------------------------------------------------
// Every colour of these icons lies on one ramp per hue, from white down to the deepest tone, and its green channel
// falls evenly along it. So a shade is given by its green level (0 to 255, as read off a pixel of the game) and every
// colour comes off the ramp (tools/objects_b_ramp.py prints the ramp of any icons: the middle colour of each level).
// The blues are the ramp of parts/symbol_shaded_objects.js; the reds are read off the three Force icons.
const BLUE = ramp([[0x00, '#00020a'], [0x0b, '#000b33'], [0x11, '#001151'], [0x1a, '#001a7c'], [0x26, '#0026b8'], [0x2e, '#022ed9'], [0x39, '#0d39e4'],
  [0x48, '#1c48f3'], [0x57, '#2b57ff'], [0x64, '#3c64ff'], [0x7b, '#597bff'], [0x8b, '#6e8bff'], [0x9f, '#869fff'], [0xb3, '#9fb3ff'], [0xc4, '#b5c4ff'],
  [0xd7, '#cdd7ff'], [0xec, '#e7ecff'], [0xff, '#ffffff']]);
const RED = ramp([[0x00, '#000000'], [0x05, '#1f0500'], [0x0a, '#430a00'], [0x0d, '#5b0d00'], [0x11, '#751100'], [0x16, '#941600'], [0x1a, '#b31a00'],
  [0x23, '#c52309'], [0x2d, '#d02d12'], [0x34, '#d73419'], [0x3b, '#dd3b20'], [0x44, '#e74429'], [0x49, '#ec492f'], [0x53, '#f65339'], [0x5a, '#fd5a3f'],
  [0x62, '#ff6248'], [0x6c, '#ff6c53'], [0x73, '#ff735b'], [0x7d, '#ff7d67'], [0x85, '#ff8571'], [0x8b, '#ff8b78'], [0x94, '#ff9482'], [0x9c, '#ff9c8b'],
  [0xac, '#ffac9e'], [0xb4, '#ffb4a8'], [0xc4, '#ffc4ba'], [0xcc, '#ffccc3'], [0xd4, '#ffd4cd'], [0xdb, '#ffdbd5'], [0xe4, '#ffe4df'], [0xec, '#ffece9'],
  [0xf4, '#fff4f3'], [0xff, '#ffffff']]);
// The thin dark line on a body's edge is the body's own colour 95 levels deeper (as on the rest of the sheet).
const rimLevel = (g) => Math.max(g - 95, 0x12);
// a level laid on a pixel, with the thin dark line where the pixel lies within `rim` of its shape's edge
const shade = (px, tone, g, k, rim = RIM) => put(px, mix3(tone(clamp(g, 0, 255)), tone(rimLevel(g)), rim > 0 ? step(rim + px.d, k) : 0));

// a Gaussian blur of a square field (sigma in pixels), edges held
const blurField = (src, n, sigma) => {
  const r = Math.max(1, Math.ceil(sigma * 2.5)), w = new Float32Array(2 * r + 1);
  let tot = 0;
  for (let i = -r; i <= r; i++) { w[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); tot += w[i + r]; }
  for (let i = 0; i < w.length; i++) w[i] /= tot;
  const tmp = new Float32Array(n * n), out = new Float32Array(n * n);
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * src[j * n + clamp(x + t, 0, n - 1)]; tmp[j * n + x] = a; }
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * tmp[clamp(j + t, 0, n - 1) * n + x]; out[j * n + x] = a; }
  return out;
};

// A rounded form shaded by itself, in the way of the hand of parts/symbol_shaded_objects.js: light in its middle
// (level `hi`), deepening to `lo` at its edge. The light middle stands off towards the light by `lean` units, so that
// the side turned from the light is the broader and deeper one; along the edge facing the light the colour deepens
// only over `edge` units and only to `lit`. core: how far in from the edge the colour reaches `hi`; bend: how the
// colour rises over that distance. soft: the depths are smoothed over that many units first, so that the light has no
// ridges where the nearest edge changes. adjust(level, px) -> level: a change laid over it (a shadow, a paler end).
const AWAY = [0.63, 0.78];                 // the direction away from the light
const cushion = (c, shape, tone, o) => {
  const n = c.size, k = c.k, f = c.field(shape), lean = o.lean === undefined ? 0.4 : o.lean, soft = o.soft === undefined ? 0.4 : o.soft;
  let D = new Float32Array(n * n);
  for (let i = 0; i < D.length; i++) D[i] = f[i] < 0 ? -f[i] : 0;
  if (soft > 0) D = blurField(D, n, soft * k);
  const away = o.away || AWAY, ox = Math.round(away[0] * lean * k), oy = Math.round(away[1] * lean * k);
  const hi = o.hi, lo = o.lo, core = o.core, edge = o.edge === undefined ? 0.55 : o.edge, lit = o.lit === undefined ? (lo + hi) / 2 : o.lit, bend = o.bend || 1.3;
  return c.fill(shape, (px) => {
    const i = px.i, x = i % n, j = (i - x) / n;
    const t = clamp(D[clamp(j + oy, 0, n - 1) * n + clamp(x + ox, 0, n - 1)] / core, 0, 1);
    let g = Math.min(lo + (hi - lo) * Math.pow(t, bend), lit + (hi - lit) * smooth(0, edge, -px.d));
    if (o.adjust) g = o.adjust(g, px);
    shade(px, tone, g, k, o.rim === undefined ? RIM : o.rim);
    if (o.alpha) px.a = o.alpha(px);               // (a form that melts into the one under it)
  });
};

// ---- the cube ----------------------------------------------------------------------------------------------------------
// The object of the Force icons: a cube seen from above over one edge, so that its outline is a hexagon with upright
// sides. Given by: cx (the middle of its outline), top (the y of its upper corner), a (half its width) and h (the
// length of an upright edge). Measured the same in all three icons (edges fitted to the game's pixels):
//   each slanted edge drops p = 0.62 a from one end to the other (ip_hold 5.2 for a 8.5, ip_push 6.0 for 9.5,
//   ip_breach 4.65 for 7.5)
//   the upright edge in the middle, and with it the lowest corner, stands lean = 0.065 a to the right of the middle
//   of the outline and the upper corner as far to the left (ip_hold: upper corner at x 15.28, lowest at 16.07, the
//   outline from 7 to 24; ip_push 21.4 and 22.3 in 12..31; ip_breach 15.0 and 15.8 in 8..23): the cube is turned a
//   little, its lit left face the broader one
//   the upright edges differ from icon to icon (8.7, 10.5, 9.25) and are given
// The game's lighting, the same in all three icons (levels read off ip_hold and ip_push):
//   upper face  white over its left half, falling to 0xcb towards its right corner; a line of light along its two
//               front edges
//   left face   0x8d at the outline, falling to 0x46 at the middle edge (8d 89 7e 6c 5b 50 46 across ip_hold's seven
//               pixels: slowly at both ends), and a little light on the edge itself (0x62)
//   right face  0x16, lit beside the middle edge: 0x6c on the edge, the light dying away to the right over a quarter
//               of the face at the top (5a 3b 2e 27 20 1b 18) and over less and less further down (43 23 1a 16)
//   and inside the outline, along the sides and the lower edges, a pale line: the one pixel of pale pink between the
//   black and the red in the game (lightest along the lower left edge: 0xc6..0xe8 in the three icons; 0xa1..0xc1
//   along the lower right one).
const CUBE = { drop: 0.62, lean: 0.065 };
const cubePoints = ({ cx, top, a, h }) => {
  const p = CUBE.drop * a, l = CUBE.lean * a;
  return { p, l, T: [cx - l, top], UL: [cx - a, top + p], UR: [cx + a, top + p], M: [cx + l, top + 2 * p],
    LL: [cx - a, top + p + h], LR: [cx + a, top + p + h], B: [cx + l, top + 2 * p + h] };
};
const cubeOutline = (o) => { const q = cubePoints(o); return [q.T, q.UR, q.LR, q.B, q.LL, q.UL]; };
// st.cut: a shape taken out of the cube (the breach); st.part: 'border' the black alone, 'body' all but the black
const cube = (c, o, st = {}) => {
  const { cx, top, a, h } = o, k = c.k, q = cubePoints(o), p = q.p, l = q.l, pts = cubeOutline(o), hex = S.polygon(pts);
  if (st.part !== 'body') c.fill(S.polygon(G.offsetPts(pts, BORDER)), P.flat(INK));
  if (st.part === 'border') return hex;
  const shape = st.cut ? S.subtract(hex, st.cut) : hex;
  // the upper face: u runs along its right-hand edges (from the upper corner to the right one), v along its
  // left-hand ones; toU, toV: the distance between its opposite edges
  const toU = (2 * a * p) / Math.hypot(a - l, p), toV = (2 * a * p) / Math.hypot(a + l, p);
  const mx = q.M[0], my = q.M[1], wl = a + l, wr = a - l;
  c.fill(shape, (px) => {
    const x = px.x, y = px.y, dx = x - mx, Y = (y - top) / p;
    const u = (x - q.T[0] + Y * wr) / (2 * a), v = Y - u;
    const dU = (1 - u) * toU, dV = (1 - v) * toV;                  // the distance to its two front edges (negative: beyond them)
    const low = clamp((y - my) / h, 0, 1);
    let gt = 0xff - 0x34 * clamp((u - 0.42) / 0.48, 0, 1);
    gt += (0xf8 - gt) * 0.8 * (1 - smooth(0.2, 0.8, Math.min(dU, dV)));
    const gl = 0x46 + 0x4c * smooth(0, 0.9, -dx / wl) + 0x1a * bell(dx, 0.45);
    const gr = 0x16 + 0x56 * Math.exp(-Math.max(dx, 0) / (wr * Math.max(0.24 - 0.28 * low, 0.075)));
    // the pale line inside the outline
    const depth = -px.d, line = 1 - smooth(0.5, 0.95, depth), pale = 0xd8 - 0x20 * smooth(-1.5, 1.5, dx);
    const lev = (g) => (pale > g ? g + (pale - g) * line : g);
    const ct = RED(lev(gt)), cl = RED(lev(gl)), cr = RED(lev(gr));
    const left = mix3(cl, ct, step(dV, k)), right = mix3(cr, ct, step(dU, k));
    const g = dx < 0 ? (dV > 0 ? gt : gl) : (dU > 0 ? gt : gr);
    put(px, mix3(mix3(left, right, step(dx, k)), RED(rimLevel(lev(g))), step(RIM + px.d, k)));
  });
  return shape;
};

// ---- the hand under the cube (Force hold) ------------------------------------------------------------------------------
// What the game's icon is: an open hand seen from the side, palm up, reaching in from the left. The wrist is cut off
// straight at the left (x 2, y 22.65..26.45); the heel of the hand is its deepest part (lowest at x 12..17.5,
// y 28.7); the fingers run on to the right and rise, their end at x 27.9; the thumb lies in front, along the upper
// edge, and points right (upper edge y 20.05, end at x 21.3). Between the thumb's end and the fingers a black gap
// runs in to the left and comes to a point at 15.8, 24.7.
// Edges read off the game's pixels (tools/objects_b_runs.py):
//   upper edge   22.65 at x 2, 21.75 at x 9.5, 21.1 at x 12.5, then up to 20.05 from x 15.3 on
//   thumb's underside   x 19.9 at y 22.5, 17.5 at y 23.5;   fingers' upper edge   x 24.7 at y 22.5, 21.5 at y 23.5
//   lower edge   26.5 at x 2 falling 0.21 a unit to 28.75 at x 12.2; level to 17.6; then rising 0.456 a unit
// The game's levels: white (0xe2..0xf0) along the middle of wrist, palm and fingers; pink at the edges (0xb0 above,
// 0x88 below); the thumb pink (0x71..0x90 in its middle, 0xb5..0xcb at its end and along its upper edge).
// One body: no line between thumb and hand but the gap.
const HOLD_HAND = {
  // the thumb's upper edge and its end; its underside, straight to the point of the gap
  top: [[11.0, 21.5, 10], [15.3, 20.05, 6], [21.3, 20.05, 0.95], [21.3, 21.9, 0.9], [14.3, 24.6]],
  // the rest of the outline: the fingers' upper edge (rising 0.16 a unit at first, 0.34 towards the end: the two
  // stretches joined by an arc), their end, the lower edge back to the wrist
  rest: [[21.5, 23.45, 46], [27.9, 21.3, 0.9], [27.9, 23.9, 1.2], [17.6, 28.65, 2.5], [12.2, 28.75, 2.5], [2.0, 26.45, 0.6], [2.0, 22.65, 0.6]],
  // the thumb's root in the palm: where its form ends inside the hand (no line there, only the end of its shade)
  root: [[11.4, 24.05, 1.2], [9.8, 23.2, 1.2], [9.3, 21.75]],
};
const holdHand = (c, part) => {
  const q = HOLD_HAND, all = S.polygon(outline(q.top.concat(q.rest)));
  if (part !== 'body') c.fill(all, P.flat(INK), BORDER);
  if (part === 'border') return all;
  const thumb = S.polygon(outline(q.top.concat(q.root))), tf = c.field(thumb);
  // the hand: white along its middle, pink to its edges; the thumb's shadow lies on it under the thumb
  cushion(c, all, RED, {
    hi: 0xf0, lo: 0x88, lit: 0xb8, core: 1.25, lean: 0.35, edge: 0.6, soft: 0.4, bend: 1.2,
    adjust: (g, px) => g - 0x30 * (1 - smooth(0, 0.9, tf[px.i])) * smooth(10.5, 13.5, px.x),
  });
  // the thumb: a finger of its own in front, light along its upper edge and at its end, deep where it turns under;
  // towards its root it melts into the palm
  cushion(c, thumb, RED, {
    hi: 0xe0, lo: 0x6c, lit: 0xd0, core: 0.8, lean: 0.85, edge: 0.5, soft: 0.3, bend: 1.0, rim: 0,
    adjust: (g, px) => g + (0xc8 - g) * 0.8 * smooth(19.2, 20.9, px.x),
    alpha: (px) => smooth(9.6, 13.6, px.x),
  });
  // the thin dark line on the outline again, where the thumb has covered it
  c.fill(all, (px) => put(px, RED(0x58), step(RIM + px.d, c.k)));
  return all;
};

// ---- the arrow that pushes the cube (Force push) -------------------------------------------------------------------------
// In the game: a black arrow pointing right with a white line round it and black round that, all on the pixel grid.
// The white line's outer edge: the shaft from x 1 to 8, y 12 to 21 (9 high); the head's back at x 8 from y 8.5 to
// 24.5, its sides at 45 degrees to the point at 16, 16.5. The white is one pixel wide along the shaft and two pixels
// from side to side along the slanted sides (1.4 across); here it is one unit wide everywhere.
// left: 1.15 instead of 1, so that the black round it stands whole inside the frame.
const PUSH_ARROW = { left: 1.15, back: 8, half: 4.5, head: 8, y: 16.5, line: 1.0 };
const pushArrow = (c, part) => {
  const q = PUSH_ARROW, y = q.y;
  const pts = [[q.left, y - q.half], [q.back, y - q.half], [q.back, y - q.head], [q.back + q.head, y], [q.back, y + q.head], [q.back, y + q.half], [q.left, y + q.half]];
  // (the black round the two sharp corners at the head's back is cut square, as the game's is)
  if (part !== 'body') c.fill(S.polygon(G.offsetPts(pts, BORDER, 1.8)), P.flat(INK));
  if (part === 'border') return;
  c.fill(S.polygon(pts), P.flat('#ffffff'));
  c.fill(S.polygon(G.offsetPts(pts, -q.line)), P.flat(INK));
};

// ---- the breach ------------------------------------------------------------------------------------------------------------
// What the game's icon is: the cube struck from above by a bolt that splits its top open, and five bits flying off.
// Read off its pixels: the cube 15 wide (x 8..23), its upper corner at 15.0, 12.16 (behind the bolt), its lower
// corners at y 26.06, its lowest at 30.7. Of its upper face there remain a small piece at the left (under the far
// edge from x 9.2 to 13.3, cut off level at y 16.04), a larger one at the right (under the far edge from x 18.25 to
// the corner, cut off level at y 18, its left side leaning as the bolt's edge does: x 17.8 at y 15.5, 17.0 at y 18)
// and a band along the two front edges. Between them is black: a split that starts on the far left edge at y 16,
// widens to the right along the line to 16.5, 19 and runs on to the cube's right side, which it leaves between y 18
// and 20.4: there it has cut into the right face too, whose pale line follows it. The bolt comes down through the
// gap between the two pieces.
const BREACH = {
  cube: { cx: 15.5, top: 12.16, a: 7.5, h: 9.25 },
  // the split, clockwise from its point; where it leaves the cube (at its point, over the upper corner and at the
  // right side) it is carried on beyond the outline
  split: [[8.43, 16.04], [13.3, 16.04], [13.3, 10], [19.53, 10], [17.0, 18.0], [25, 18.0], [25, 20.85], [16.5, 19.0]],
  // The bolt, the game's shape (as the bolts of the lightning icons, drawn/flat_sharp.js): an upright block that
  // draws in from the right as it goes down (x 11..18.2 at y 2.9, x 11..15.6 at y 7.7), a ledge to the right at its
  // foot (to x 20.1) and from there one long edge down to the point; the block's left part ends at y 10.9.
  // The point: in the game the long edge ends blunt at y 16 (x 14..16); here it is carried on to a point.
  bolt: [[11, 2.9], [18.2, 2.9], [15.6, 7.7], [20.1, 7.7], [14.5, 17.2], [14.0, 10.9], [11, 10.9]],
  // the bits: squares of two units at the game's places, the one at the upper right larger (2.7): [middle x, y, half]
  bits: [[8, 12, 1.0], [6, 17, 1.0], [23.1, 13.3, 1.35], [26, 20, 1.0], [26, 24, 1.0]],
};
// white things in a red icon: white, a little pink towards the edge, a thin red line on it (the game's bolt has a
// pink column along its left side and red in its edge pixels); the bits are the same with more red
const WHITE_HOT = { rim: '#c52309', edge: '#ffc4ba', body: '#ffffff' };
const BIT = { rim: '#941600', edge: '#f65339', body: '#fff4f3' };
const square = ([x, y, r]) => [[x - r, y - r], [x + r, y - r], [x + r, y + r], [x - r, y + r]];

module.exports = { INK, BORDER, RIM, lin, mix3, put, smooth, bell, ramp, curve, rect, step, outline, BLUE, RED, rimLevel, shade, blurField, cushion,
  cubePoints, cubeOutline, cube, HOLD_HAND, holdHand, PUSH_ARROW, pushArrow, BREACH, WHITE_HOT, BIT, square };
