'use strict';
// Building blocks of the flat round symbols: outlines put together from straight lines and circular arcs, glows that
// fall off as the game's own do, rings, discs. Units: the vanilla icon's pixels (frame 32 x 32, y down).
// Nothing here is traced. The GAME's icon gives each design (its pixels are read with tools/vmap.py and
// tools/flat_round_m.py); the redraw only helps to see what a thing is. Each icon states its measured dimensions.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const F = require('./flat');
const { hypot, sqrt, atan2, cos, sin, abs, max, min, exp, pow, PI } = Math;
const { clamp } = S;

const BLACK = '#0a0a0c';
const FARTHEST = 99;          // a polygon whose distance is wanted exactly at any range (for glows)

// ---- small tools ---------------------------------------------------------------------------------------------------
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c, a = 1) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = a; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const degOf = (cx, cy, p) => (atan2(p[1] - cy, p[0] - cx) * 180) / PI;
const at = (cx, cy, r, deg) => [cx + r * cos((deg * PI) / 180), cy + r * sin((deg * PI) / 180)];

// several stretches of points (a point, or a list of points) as one outline, doubled points left out
const outline = (...parts) => {
  const out = [];
  const add = (p) => { const q = out[out.length - 1]; if (!q || hypot(p[0] - q[0], p[1] - q[1]) > 1e-6) out.push(p.slice()); };
  for (const part of parts) { if (typeof part[0] === 'number') add(part); else for (const p of part) add(p); }
  if (out.length > 1 && hypot(out[0][0] - out[out.length - 1][0], out[0][1] - out[out.length - 1][1]) < 1e-6) out.pop();
  return out;
};
// an arc as points (degrees, y down: angles grow clockwise on screen); coarser than geom's default, still exact to
// a hundredth of a pixel at 512
const arc = (cx, cy, r, a0, a1, step = 0.16) => G.arcPts(cx, cy, r, a0, a1, step);
// The outline of a shape that is the same left and right of x = cx, from its right half: the points from the top of
// the axis round the right side to the bottom of the axis. Points on the axis are not doubled.
const mirrorOutline = (cx, right) => {
  const left = right.filter((p) => abs(p[0] - cx) > 1e-6).map((p) => [2 * cx - p[0], ...p.slice(1)]).reverse();
  return outline(right, left);
};
// the two places where the circles (a, ra) and (b, rb) cross
const circleCross = (a, ra, b, rb) => {
  const d = hypot(b[0] - a[0], b[1] - a[1]), k = (ra * ra - rb * rb + d * d) / (2 * d), h = sqrt(max(ra * ra - k * k, 0));
  const ux = (b[0] - a[0]) / d, uy = (b[1] - a[1]) / d, mx = a[0] + k * ux, my = a[1] + k * uy;
  return [[mx - h * uy, my + h * ux], [mx + h * uy, my - h * ux]];
};

// A limb that is thicker at one end: the two discs (a, ra) and (b, rb) and everything between them (the straight
// lines that touch both). After Inigo Quilez's uneven capsule.
const roundCone = (a, ra, b, rb) => {
  const h = hypot(b[0] - a[0], b[1] - a[1]), ux = (b[0] - a[0]) / h, uy = (b[1] - a[1]) / h, k = (ra - rb) / h, w = sqrt(max(1 - k * k, 0));
  return (x, y) => {
    const px = x - a[0], py = y - a[1], t = px * ux + py * uy, s = abs(-px * uy + py * ux), q = -k * s + w * t;
    if (q < 0) return hypot(s, t) - ra;
    if (q > w * h) return hypot(s, t - h) - rb;
    return s * w + t * k - ra;
  };
};

// ---- the sheet's line weights and its bodies ------------------------------------------------------------------------
// The game's black borders are of two kinds: one pixel (round the plus, the arrows, the second shield, the lines of
// the sight) and two pixels (the rings that fill the frame, between the rings of the target). Drawn 0.7 and 1.5:
// 0.7 is the width the approved flat sharp sheet gives the game's one-pixel border.
// A white body of the game carries blue pixels between its white and its black wherever the edge does not lie along
// the pixel grid (22, 66, 237 on average; half a pixel wide over a whole outline): a blue line just inside the edge.
const W = { thin: 0.7, thick: 1.5, line: 0.55 };
const BLUE_LINE = [[0, '#0c36e0'], [1, '#2c58fa']];           // across the blue line, from the body's edge inwards
// The game's red discs are one flat red (190, 27, 0); drawn with the sheet's soft shading: a little deeper to the edge,
// a thin dark line along it. (The flat sharp sheet's red field of the second critical strike is the same red.)
const RED = { rim: '#4a0702', edge: '#a01602', body: '#c41c02' };
// A white body: black border round it (grown from the body: the same width everywhere), a blue line just inside its
// edge, white within. o: border (0 = none), line (0 = none), white
const whiteBody = (c, shape, { border = W.thin, line = W.line, white = '#ffffff' } = {}) => {
  if (border > 0) c.fill(shape, P.flat(BLACK), border);
  if (line > 0) { c.fill(shape, P.byDepth(line, BLUE_LINE)); c.fill(shape, P.flat(white), -line); } else c.fill(shape, P.flat(white));
  return shape;
};
// The flat sharp sheet's shading for a body of one colour (parts/flat.js): the colour deepens a little to the edge
// and a thin dark line runs along it. For any shape (its own distance decides).
const deep = (c, palette, o) => F.deepening(c.k, palette, o);

// ---- glows ---------------------------------------------------------------------------------------------------------
// a field blurred (Gaussian, sigma in pixels); beyond the canvas there is nothing
const blurred = (src, S_, sigma) => {
  const r = max(1, Math.ceil(sigma * 3)), w = new Float32Array(2 * r + 1);
  let tot = 0;
  for (let i = -r; i <= r; i++) { w[i + r] = exp(-(i * i) / (2 * sigma * sigma)); tot += w[i + r]; }
  for (let i = 0; i < w.length; i++) w[i] /= tot;
  const tmp = new Float32Array(S_ * S_), out = new Float32Array(S_ * S_);
  for (let j = 0; j < S_; j++) for (let n = 0; n < S_; n++) { let a = 0; for (let t = max(-r, -n), t1 = min(r, S_ - 1 - n); t <= t1; t++) a += w[t + r] * src[j * S_ + n + t]; tmp[j * S_ + n] = a; }
  for (let j = 0; j < S_; j++) for (let n = 0; n < S_; n++) { let a = 0; for (let t = max(-r, -j), t1 = min(r, S_ - 1 - j); t <= t1; t++) a += w[t + r] * tmp[(j + t) * S_ + n]; out[j * S_ + n] = a; }
  return out;
};
// a value read off a table [[x, y], ...] (x rising), straight between its entries
const table = (rows) => (x) => {
  if (x <= rows[0][0]) return rows[0][1];
  for (let i = 1; i < rows.length; i++) if (x <= rows[i][0]) return rows[i - 1][1] + ((rows[i][1] - rows[i - 1][1]) * (x - rows[i - 1][0])) / (rows[i][0] - rows[i - 1][0]);
  return rows[rows.length - 1][1];
};
// The game's glow round a body, made as the game's own was: the body's silhouette blurred (sigma, in units), the
// blur put through a curve (curve: [[blur, opacity], ...]), and the colour going with the opacity (stops). Smooth
// everywhere, weaker off a corner than off a side. Laid before the body, which covers its inside.
const softHalo = (c, shape, { sigma, curve, stops }) => {
  const f = c.field(shape), k = c.k, n = f.length, m = new Float32Array(n);
  for (let i = 0; i < n; i++) m[i] = clamp(0.5 - f[i] * k, 0, 1);
  const b = blurred(m, c.size, sigma * k), r = P.ramp(stops), op = table(curve);
  return c._lay(b, (px) => { const al = op(b[px.i]); r(al, px); px.a = al; }, () => 1);
};
// The round light behind the hourglasses and the figures: one and the same in all eight of the game's icons. Read
// along rows, columns and diagonals of four of them: round about (16, 16), its opacity 0.95 at radius 2, 0.80 at 4,
// 0.64 at 5, 0.44 at 6, 0.25 at 7, 0.11 at 8, 0.04 at 9, nothing at 10: exp(-(r / 6.4)^3.2) to within 0.02. Its
// colour goes with its opacity: the game's blue (40, 84, 255) where it is faint, white where it is full.
//   band: { shape, width, colour }: beside that shape, for `width`, the light takes that colour (the white hourglass:
//   in the game the pixel of light next to its black border is red, as strong as the light is there).
const light = (c, { cx = 16, cy = 16, band = null } = {}) => {
  const blue = lin('#2854ff'), white = [1, 1, 1], bf = band ? c.field(band.shape) : null, bc = band ? lin(band.colour) : null, k = c.k;
  return c._lay(c.field(S.circle(cx, cy, 11)), (px) => {
    const al = exp(-pow(hypot(px.x - cx, px.y - cy) / 6.4, 3.2));
    let v = mix3(blue, white, al);
    if (bf) v = mix3(v, bc, clamp(0.5 - (bf[px.i] - band.width) * k, 0, 1));
    put(px, v, al);
  }, (d, kk) => (d < 0 ? 1 : 0));
};

// ---- the yellow rings ------------------------------------------------------------------------------------------------
// The ring round the hourglasses and the figures: the game's is yellow (255, 255, 0), 50 pixels wide and 49 high in
// its 64 (outer radius 12.4), 2.26 pixels thick (1.13), and stands a quarter of a unit above the middle of the frame.
// Drawn round, about (16, 16) (so that what stands in it stands in its middle). The redraw's is half as thick again.
// With `arcs` the second, inner ring of the third level: four arcs at radius 10.5, 1.05 thick, each from 13.2 to 80.7
// degrees off the level (the gaps at the sides 26.4 degrees wide, those at the top and bottom 18.6), a dimmer yellow
// (in the game 249, 244, 0 at 85 per cent opacity: drawn solid in the colour that gives over black).
const RING = { r: 11.835, w: 1.13, arcR: 10.5, arcW: 1.05, from: 13.2, to: 80.7 };
const yellowRing = (c, { arcs = false } = {}) => {
  const q = RING;
  if (arcs) for (const a of [0, 90, 180, 270]) c.fill(S.arc(16, 16, q.arcR, q.arcW, a + (a % 180 ? 90 - q.to : q.from), a + (a % 180 ? 90 - q.from : q.to)), P.flat('#d6d100'));
  c.fill(S.ring(16, 16, q.r, q.w), P.byDepth(q.w / 2, [[0, '#f2ea00'], [0.5, '#fffa08'], [1, '#ffff10']]));
};

// ---- the hourglass ---------------------------------------------------------------------------------------------------
// The game's hourglass (64 pixel icons, read pixel by pixel; the same outline in its blue and its white version), the
// same left and right of x = 16 and above and below y = 16: a cap 8 wide and 1 high at each end (y 9 to 10, 22 to 23),
// the glass 7 wide between them, drawn in from y 13.25 by a cone (1.42 out for 1 up) to a neck 2 wide from y 15 to 17;
// the corner between the glass's wall and the cone is rounded (radius 2.0 fits the rows there). Half a unit of black
// round it (one pixel of the 64).
const hourglassPts = () => {
  const q = [[4, 9], [4, 10], [3.5, 10], [3.5, 13.24, 2.0], [1, 15], [1, 17], [3.5, 18.76, 2.0], [3.5, 22], [4, 22], [4, 23]];
  return S.roundedPoints(q.map(([x, y, r]) => [16 + x, y, r || 0]).concat(q.map(([x, y, r]) => [16 - x, y, r || 0]).reverse()), 0, 0.1);
};
const HOURGLASS = { border: 0.5, sandTop: 12.4, pileTop: 20.1, pileSide: 20.9, inset: 0.45 };
// kind 'blue': the glass a deep blue (25, 69, 240), deeper at its edges and under the caps (0, 42, 205); the caps
// light bars; in the upper half pale sand from y 12.4 down into the neck, a thin stream of it through the lower half
// to a low mound on the bottom, brighter where the stream lands; a soft upright light on the glass above the sand
// (in the game a paler stripe one unit wide, 1.5 right of the axis, through every row of the upper half).
// kind 'white': caps and glass one white body.
const hourglass = (c, kind = 'blue') => {
  const H = HOURGLASS, pts = hourglassPts(), body = S.polygon(pts);
  c.fill(S.polygon(G.offsetPts(pts, H.border)), P.flat(BLACK));
  if (kind === 'white') { c.fill(body, deep(c, { rim: '#9aa4c8', edge: '#eef1fb', body: '#ffffff' }, { depth: 0.6, rim: 0.1 })); return body; }
  const glass = S.intersect(body, S.box(16, 16, 5, 6)), room = S.grow(glass, -H.inset);
  c.fill(body, P.linear(16, 9, 16, 10, [[0, '#a9bdff'], [1, '#4f73ff']]));                      // the caps (the lower one below)
  c.fill(S.intersect(body, S.box(16, 22.5, 5, 0.5)), P.linear(16, 22, 16, 23, [[0, '#a9bdff'], [1, '#4f73ff']]));
  c.fill(glass, deep(c, { rim: '#06187a', edge: '#002acd', body: '#1945f0' }, { depth: 0.7, rim: 0.12 }));
  // the light on the glass above the sand
  c.fill(S.intersect(room, S.box(16, 11.2, 5, H.sandTop - 11.2)), (px) => {
    const u = (px.x - 17.5) / 0.36, v = clamp((H.sandTop - px.y) / (H.sandTop - 10.4), 0, 1);
    px.r = 0.78; px.g = 0.84; px.b = 1; px.a = 0.6 * exp(-u * u) * (0.3 + 0.7 * v) * smooth(10.45, 11.0, px.y);
  });
  // the sand: what is left above, the stream, the mound: one pale piece
  const stream = S.polygon([[15.45, 15], [16.55, 15], [16.2, 15.9], [16.2, 21], [15.8, 21], [15.8, 15.9]]);
  const Rm = (3.05 * 3.05 + (H.pileSide - H.pileTop) * (H.pileSide - H.pileTop)) / (2 * (H.pileSide - H.pileTop));
  const sand = S.union(S.intersect(room, S.box(16, (H.sandTop + 15.05) / 2, 5, (15.05 - H.sandTop) / 2)), stream, S.intersect(room, S.circle(16, H.pileTop + Rm, Rm)));
  c.fill(sand, deep(c, { rim: '#7f99ff', edge: '#93aaff', body: '#b4c4ff' }, { depth: 0.5, rim: 0 }));
  c.blob(16, H.pileTop + 0.55, 0.75, 0.5, '#f0f4ff', 0.9, { mask: sand });
  return body;
};

// ---- the figure ------------------------------------------------------------------------------------------------------
// The game's standing figure (64 pixel icons; half-widths read off 28 rows): a black silhouette 14 high. Head 2.1
// wide from y 8.6 (the game's sits on the shoulders without a neck one could see; drawn with a neck a little narrower
// than the head, so that it reads as a head); square shoulders at 12.1, 4.7 wide; arms and body one block widening
// to 5.4 at the hands (17.45); then the legs, one piece 3.4 wide narrowing to 2.3 and rounded off at the feet (22.6).
// (x: the axis; k: the size, measured from the level of the hands, as the game's smaller figures are.)
const figure = (x = 16, k = 1) => {
  const Y = (y) => 17.45 + (y - 17.45) * k, half = [[0.9, 11.2], [0.9, 11.7], [2.35, 12.15, 0.35], [2.7, 16.9], [2.7, 17.45, 0.45], [1.7, 17.45], [1.3, 19.3], [1.15, 21.4], [0.8, 22.6, 0.5]];
  const pts = half.map(([px, py, r]) => [x + px * k, Y(py), (r || 0) * k]).concat(half.map(([px, py, r]) => [x - px * k, Y(py), (r || 0) * k]).reverse());
  return S.union(S.polygon(S.roundedPoints(pts, 0, 0.08)), S.ellipse(x, Y(9.98), 1.05 * k, 1.4 * k));
};

// ---- outlines --------------------------------------------------------------------------------------------------------
// An arrow pointing up: a head with sides at 45 degrees and a shaft. (x, y): its point. head: half the head's width
// (and its height), shaft: half the shaft's width, length: the whole arrow's.
const arrowUp = (x, y, { head, shaft, length }) => [[x, y], [x + head, y + head], [x + shaft, y + head], [x + shaft, y + length], [x - shaft, y + length], [x - shaft, y + head], [x - head, y + head]];

// A shield, the same left and right of x = cx. Its upper edge is given by the corners of its right half from the axis
// outwards, [x from the axis, y] or [x, y, r] to round that corner with radius r; straight sides down to `spring`;
// and a lower edge of three arcs that run into one another smoothly: an arc of radius `corner` at each side and one
// about the axis through the lowest point `foot` (its radius follows from the other measures).
const shieldPts = ({ cx = 16, top, spring, foot, corner }) => {
  const a = top[top.length - 1][0], b = foot - spring, R = (a * a - 2 * a * corner + b * b) / (2 * (b - corner));
  const cc = [cx + a - corner, spring], cr = [cx, foot - R], d = hypot(cc[0] - cr[0], cc[1] - cr[1]);
  const J = [cr[0] + (R * (cc[0] - cr[0])) / d, cr[1] + (R * (cc[1] - cr[1])) / d];          // where the two arcs meet
  const right = [...top.map((p) => [cx + p[0], ...p.slice(1)]), [cx + a, spring],
    ...arc(cc[0], cc[1], corner, 0, degOf(cc[0], cc[1], J)).slice(1), ...arc(cr[0], cr[1], R, degOf(cr[0], cr[1], J), 90).slice(1)];
  return S.roundedPoints(mirrorOutline(cx, right), 0, 0.1);
};

// A crescent between two circles, pointed at both ends: its inner edge lies on the circle (c, r); it reaches `span`
// degrees up and down from the level of c and is `thick` at its middle. side: -1 left of c, +1 right of it.
const lunePts = ({ c = [16, 16], r, span, thick, side = -1 }) => {
  const h = r * sin((span * PI) / 180), dx = r * cos((span * PI) / 180), s = r + thick - dx, ro = (h * h + s * s) / (2 * s), ox = c[0] - (r + thick - ro);
  // (the outer circle passes through both points and the place `thick` beyond the inner circle's leftmost)
  const a = ((degOf(ox, c[1], [c[0] - dx, c[1] + h]) % 360) + 360) % 360;          // the lower point seen from the outer centre
  const left = outline(arc(ox, c[1], ro, 360 - a, a), arc(c[0], c[1], r, 180 - span, 180 + span));
  return side < 0 ? left : left.map(([x, y]) => [2 * c[0] - x, y]).reverse();
};

// A band along a circle that narrows to a point at each end: between the radii ri and ro about (cx, cy), full width
// from -full to +full degrees either side of the direction `mid`, its points at -tip and +tip on the band's middle
// radius. The narrowing edges are circular arcs too, each leaving its edge of the band without a corner.
const taperArcPts = ({ c = [16, 16], ri, ro, mid = 180, full, tip }) => {
  const rm = (ri + ro) / 2, D = ((tip - full) * PI) / 180;
  const end = (sgn) => {                                    // from the outer edge's end to the point and on to the inner edge's end
    const a1 = mid + sgn * full, T = at(c[0], c[1], rm, mid + sgn * tip), out = [];
    for (const [r, flip] of [[ro, false], [ri, true]]) {
      const t = (rm * rm - r * r) / (2 * (rm * cos(D) - r)), q = at(c[0], c[1], t, a1), R = abs(t - r), P1 = at(c[0], c[1], r, a1);
      let b0 = degOf(q[0], q[1], P1), b1 = degOf(q[0], q[1], T);
      while (b1 - b0 > 180) b1 -= 360; while (b1 - b0 < -180) b1 += 360;
      const pts = arc(q[0], q[1], R, b0, b1, 0.1);
      out.push(...(flip ? pts.reverse() : pts));
    }
    return out;
  };
  const upper = end(1), lower = end(-1);                    // (+: the end at mid + tip)
  return outline(arc(c[0], c[1], ro, mid - full, mid + full), upper, arc(c[0], c[1], ri, mid + full, mid - full), lower.reverse());
};

// A circular arc from p to q that bows out from their chord by `sag` (to the right of the direction p to q as seen
// on screen; negative: to the left): its points, p and q included.
const bowPts = (p, q, sag) => {
  const L = hypot(q[0] - p[0], q[1] - p[1]), h = L / 2, R = (h * h + sag * sag) / (2 * abs(sag)), side = sag > 0 ? 1 : -1;
  const ux = (q[0] - p[0]) / L, uy = (q[1] - p[1]) / L, nx = -uy, ny = ux;            // n: to the right of p -> q on screen
  const ctr = [p[0] + ux * h - nx * side * (R - abs(sag)), p[1] + uy * h - ny * side * (R - abs(sag))];
  let a0 = degOf(ctr[0], ctr[1], p), a1 = degOf(ctr[0], ctr[1], q);
  if (side > 0) { while (a1 > a0) a1 -= 360; } else { while (a1 < a0) a1 += 360; }
  return arc(ctr[0], ctr[1], R, a0, a1, 0.12);
};
// a crescent between two arcs that share their end points p and q, bowed out by `inner` and `outer` to the same side
const crescentPts = (p, q, inner, outer) => outline(bowPts(p, q, outer), bowPts(p, q, inner).reverse());

// The circular arc that passes through j in the direction `deg` (screen degrees) and through p: its points from j to p.
const arcFrom = (j, deg, p) => {
  const dx = cos((deg * PI) / 180), dy = sin((deg * PI) / 180), wx = p[0] - j[0], wy = p[1] - j[1];
  const side = dx * wy - dy * wx;                                   // > 0: p lies to the right of the direction (on screen)
  if (abs(side) < 1e-9) return [j.slice(), p.slice()];
  const R = (wx * wx + wy * wy) / (2 * abs(side)), s = side > 0 ? 1 : -1, ctr = [j[0] - dy * s * R, j[1] + dx * s * R];
  let a0 = degOf(ctr[0], ctr[1], j), a1 = degOf(ctr[0], ctr[1], p);
  if (s > 0) { while (a1 < a0) a1 += 360; } else { while (a1 > a0) a1 -= 360; }
  return arc(ctr[0], ctr[1], R, a0, a1, 0.12);
};
// An S: two arcs that run into one another at j, where the curve points along `deg`: from p0 through j to p1.
const sCurvePts = (p0, j, deg, p1) => outline(arcFrom(j, deg + 180, p0).reverse(), arcFrom(j, deg, p1));

// A spiral drawn with compasses, as a band: quarter circles one after the other, each about a point one step back
// along the radius the last one ended on (so that they run into one another without a corner) and that step larger.
//   c0, r0, a0: the first quarter's centre, radius and the screen angle its first radius points to (it turns
//   anticlockwise on screen: the angle falls);  step, grow: the first step and how much longer each next one is;
//   turn: how far it winds in all (degrees);  half(t): half the band's width at t degrees from its inner end
const spiralBandPts = ({ c0, r0, a0, step, grow = 0, turn, half }) => {
  const inner = [], outer = [];
  let cx = c0[0], cy = c0[1], rad = r0, ang = a0, done = 0;
  for (let q = 0; done < turn - 1e-9; q++) {
    const span = min(90, turn - done), n = max(2, Math.ceil(((span * PI) / 180) * rad / 0.1));
    for (let i = q ? 1 : 0; i <= n; i++) {
      const t = ((ang - (span * i) / n) * PI) / 180, h = half(done + (span * i) / n);
      inner.push([cx + (rad - h) * cos(t), cy + (rad - h) * sin(t)]); outer.push([cx + (rad + h) * cos(t), cy + (rad + h) * sin(t)]);
    }
    ang -= 90; done += span;
    const t = (ang * PI) / 180, s = step + grow * q;
    cx -= s * cos(t); cy -= s * sin(t); rad += s;
  }
  return outline(outer, inner.reverse());
};

// ---- the waves of the Force -------------------------------------------------------------------------------------------
// i_force02 and ip_resistforce are one design in the game: about the middle of the icon a white disc of radius 6, on
// either side of it a band between the radii 9.04 and 11.09 (fitted circles; full width to 57 degrees up and down,
// faded out by 75) and outside that a crescent, which is the very crescent of ip_shield (the same pixels row for
// row); and on the right a pale blue (126, 152, 254) a quarter opaque between the disc and the band, from the upright
// through the middle: half a ring, a little stronger along its outer edge where the band has ended. The bands are a
// light grey white (226), the crescents dimmer (221, less opaque): the waves pale as they go out.
//   k: everything's size about (16, 16);  lune: the radius of the crescents' inner edge
const forceWaves = ({ k = 1, lune = 13.85 } = {}) => ({
  bands: [180, 0].map((mid) => S.polygon(taperArcPts({ ri: 9.04 * k, ro: 11.09 * k, mid, full: 61, tip: 74 }))),
  crescents: [-1, 1].map((side) => S.polygon(lunePts({ r: lune, span: 57, thick: 1.85 * k, side }))),
  // the blue half-ring: x from `from` (off the axis), radii r0 to r1; its outer rim deeper
  blue: (c, from, r0, r1) => {
    const pale = lin('#7e98fe'), rim = lin('#3c62f4');
    return c.fill(S.intersect(S.ring(16, 16, (r0 + r1) / 2, r1 - r0), S.halfPlane(16 + from, 16, -1, 0)), (px) => {
      const t = smooth(r1 - 0.75, r1 - 0.15, hypot(px.x - 16, px.y - 16));
      put(px, mix3(pale, rim, t), 0.255 + 0.2 * t);
    });
  },
});
const PALE = { rim: '#a2a6b6', edge: '#e9ebf2', body: '#ffffff' };          // the neutral white of these icons, a little deeper to its edge

// ---- the target ----------------------------------------------------------------------------------------------------
// A red disc in a white ring, black between them and round the ring, and a white crosshair over all of it from one
// side of the frame to the other. Read off the game's icon along its four diagonals (clear of the crosshair): red to
// radius 12.15, black to 13.83, the ring (a pinkish white, 250 241 239) to 15.33, black to 16.9: the frame cuts that
// last black at its four sides. Changed from the game: the outer black is whole, and to make room everything is drawn
// 0.94 of its size (ring 1.4 wide, the black either side of it 1.5). The game's rings also stand a fifth of a pixel
// apart from one another and from the crosshair; here everything is about (16, 16).
//   inner: the second ring (levels II and III): in the game at radius 8.15, 1.3 wide
//   box:   the square of the sight and its middle (level III). There, in the game, every straight white line carries
//          a black border of its own, one pixel either side (the whole length of the crosshair too), and the disc
//          shows red wherever those borders leave it uncovered: an L in each quarter of the square, a sliver between
//          the square and the ring. The redraw blackens the whole inside of the ring instead.
const TARGET = { edge: 15.9, ring: 1.4, line: 1.0, inner: 7.65, innerWide: 1.2, box: 4.6, dot: 1.4, ringWhite: '#faf1ef' };
const target = (c, { inner = false, box = false } = {}) => {
  const T = TARGET, r0 = T.edge - W.thick, r1 = r0 - T.ring, R = r1 - W.thick, disc = S.circle(16, 16, R);
  c.fill(S.circle(16, 16, T.edge), P.flat(BLACK));
  c.fill(S.ring(16, 16, (r0 + r1) / 2, T.ring), P.flat(T.ringWhite));
  c.fill(disc, deep(c, RED));
  const h = T.line / 2, b = W.thin, cross = S.union(S.bar(0.1, 16, 31.9, 16, T.line), S.bar(16, 0.1, 16, 31.9, T.line));
  const frame = (half, w) => S.subtract(S.box(16, 16, half + w, half + w), S.box(16, 16, half - w, half - w));
  if (box) {
    c.fill(S.intersect(cross, disc), P.flat(BLACK), b);
    c.fill(S.intersect(S.union(frame(T.box, h + b), S.box(16, 16, T.dot + b, T.dot + b)), S.circle(16, 16, T.inner)), P.flat(BLACK));
  }
  if (inner) c.fill(S.ring(16, 16, T.inner, T.innerWide), P.flat(T.ringWhite));
  if (box) c.fill(S.union(frame(T.box, h), S.box(16, 16, T.dot, T.dot)), P.flat('#ffffff'));
  c.fill(cross, P.flat('#ffffff'));
};

module.exports = { BLACK, FARTHEST, W, BLUE_LINE, RED, lin, mix3, put, smooth, degOf, at, outline, arc, mirrorOutline, circleCross, roundCone, blurred, table, softHalo, light,
  whiteBody, deep, arrowUp, shieldPts, lunePts, taperArcPts, bowPts, crescentPts, arcFrom, sCurvePts, spiralBandPts, forceWaves, PALE, TARGET, target, RING, yellowRing, HOURGLASS, hourglassPts, hourglass, figure };
