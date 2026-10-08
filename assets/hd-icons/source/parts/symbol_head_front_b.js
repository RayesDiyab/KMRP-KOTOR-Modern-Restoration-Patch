'use strict';
// Pieces shared between the icons of drawn/symbol_head_front_b.js: what is laid on or round the bust of
// parts/symbol_head_front.js (the bust itself is never redrawn here: it is placed, and its own shader is used).
// The added shapes are the GAME's (read off its pixels with tools/vmap.py): the redraws fatten and reshape them.
// Units: the game icon's pixels (frame 32 x 32, y down).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const F = require('./flat');
const H = require('./symbol_head_front');

const { clamp } = S;
const smooth = H.smooth;
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c, a = 1) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = a; };

// ---- where the busts stand -----------------------------------------------------------------------------------------
// The same places as in drawn/symbol_head_front.js, so that equal busts are equal across the sheet:
//   the bust down to the chest: scale 1, the top of the head at y 0.8, on the game's axis (15.5 or 16.5);
//   the bust cut off below the shoulders ("Aura" and the icons that share its layout in the game): scale 1.2, top at
//   y 7.9, axis 16;  the small bust of "Sleep": scale 1.05, top at y 10.85, axis 16, narrow below the neck.
const CHEST_TOP = 0.8;
const chest = (axis) => ({ at: [axis, CHEST_TOP], s: 1 });
const AURA = { pl: { at: [16.0, 7.9], s: 1.2 }, form: H.SHOULDERS };
const SMALL = { pl: { at: [16.0, 10.85], s: 1.05 }, form: { neck: 0.6, w: 7.55, r8: 2.0, vb: 18.2, rc: 0.5, cut: true } };
// a point of the bust's own frame (u across from the axis, v down from the top of the head) in the icon
const onBust = (pl) => (u, v) => [pl.at[0] + pl.s * u, pl.at[1] + pl.s * v];

// the saturated hue and the dark of a bust's colour (its ramp's first stop; the deep tone of its shadows)
const HUE = {
  blue: { sat: '#003cfc', deep: '#001a7c', dark: '#000822', line: '#2a56e8', pale: '#dbe2ff' },
  red: { sat: '#fd0200', deep: '#771200', dark: '#140300', line: '#e2452a', pale: '#ffe5e1' },
};

// ---- outlines ------------------------------------------------------------------------------------------------------
// A circular arc from p to q that bows out from their chord by `sag` (to the right of the direction p to q as seen on
// screen; negative: to the left): its points, p and q included. (The same construction as in drawn/flat_sharp.js.)
const bow = (p, q, sag) => {
  const f = G.frame(p, q), h = f.L / 2, R = (h * h + sag * sag) / (2 * Math.abs(sag)), side = sag > 0 ? 1 : -1;
  const ctr = f.pt(h, -side * (R - Math.abs(sag))), deg = (v) => (Math.atan2(v[1] - ctr[1], v[0] - ctr[0]) * 180) / Math.PI;
  let a0 = deg(p), a1 = deg(q);
  if (side > 0) { while (a1 > a0) a1 -= 360; } else { while (a1 < a0) a1 += 360; }
  return G.arcPts(ctr[0], ctr[1], R, a0, a1, 0.04);
};
// A line through the given points with its corners rounded by circular arcs of radius r (a corner may give its own:
// [x, y, r]; a radius too large for a corner's sides is cut down to fit): the points along it, fine enough to be exact.
const filletPath = (pts, r = 0, step = 0.05) => {
  const out = [[pts[0][0], pts[0][1]]];
  for (let i = 1; i < pts.length - 1; i++) {
    const A = pts[i - 1], V = pts[i], Bn = pts[i + 1];
    let rr = V.length > 2 ? V[2] : r;
    const ux = A[0] - V[0], uy = A[1] - V[1], vx = Bn[0] - V[0], vy = Bn[1] - V[1], lu = Math.hypot(ux, uy), lv = Math.hypot(vx, vy);
    const half = Math.acos(clamp((ux * vx + uy * vy) / (lu * lv), -1, 1)) / 2;
    if (rr <= 0 || half > Math.PI / 2 - 1e-3 || half < 1e-3) { out.push([V[0], V[1]]); continue; }
    let t = rr / Math.tan(half);
    const tMax = Math.min(i === 1 ? lu : lu / 2, i === pts.length - 2 ? lv : lv / 2);
    if (t > tMax) { t = tMax; rr = t * Math.tan(half); }
    const p1 = [V[0] + (ux / lu) * t, V[1] + (uy / lu) * t], p2 = [V[0] + (vx / lv) * t, V[1] + (vy / lv) * t];
    let bx = ux / lu + vx / lv, by = uy / lu + vy / lv; const bl = Math.hypot(bx, by); bx /= bl; by /= bl;
    const cx = V[0] + (bx * rr) / Math.sin(half), cy = V[1] + (by * rr) / Math.sin(half);
    let a1 = Math.atan2(p1[1] - cy, p1[0] - cx), a2 = Math.atan2(p2[1] - cy, p2[0] - cx), da = a2 - a1;
    while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    const n = Math.max(2, Math.ceil((Math.abs(da) * rr) / step));
    for (let k = 0; k <= n; k++) { const a = a1 + (da * k) / n; out.push([cx + rr * Math.cos(a), cy + rr * Math.sin(a)]); }
  }
  out.push([pts[pts.length - 1][0], pts[pts.length - 1][1]]);
  return out;
};
// the same line with points no further apart than `step` (so that a width that changes along it changes evenly)
const resample = (line, step = 0.08) => {
  const out = [line[0]];
  for (let i = 1; i < line.length; i++) {
    const p = line[i - 1], q = line[i], n = Math.max(1, Math.ceil(Math.hypot(q[0] - p[0], q[1] - p[1]) / step));
    for (let k = 1; k <= n; k++) out.push([p[0] + ((q[0] - p[0]) * k) / n, p[1] + ((q[1] - p[1]) * k) / n]);
  }
  return out;
};
// A line whose width changes along it: its outline as a polygon. hw(s, L): the half-width at the length s along the
// line of whole length L. Where the half-width is nothing the outline comes to a point.
const taperStroke = (line, hw) => {
  const pts = resample(line), n = pts.length, len = [0];
  for (let i = 1; i < n; i++) len.push(len[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const L = len[n - 1], left = [], right = [];
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(i - 1, 0)], b = pts[Math.min(i + 1, n - 1)], l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-9;
    const nx = -(b[1] - a[1]) / l, ny = (b[0] - a[0]) / l, w = Math.max(hw(len[i], L), 0);
    if (w < 1e-6) { if (i === 0 || i === n - 1) { left.push([pts[i][0], pts[i][1]]); } continue; }
    left.push([pts[i][0] + nx * w, pts[i][1] + ny * w]); right.push([pts[i][0] - nx * w, pts[i][1] - ny * w]);
  }
  return left.concat(right.reverse());
};
// A line of one width with round ends, as a shape: everything within hw of the line through the points.
const lineShape = (pts, hw, far = 5) => {
  const n = pts.length, vx = new Float64Array(n), vy = new Float64Array(n);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) { vx[i] = pts[i][0]; vy[i] = pts[i][1]; x0 = Math.min(x0, vx[i]); x1 = Math.max(x1, vx[i]); y0 = Math.min(y0, vy[i]); y1 = Math.max(y1, vy[i]); }
  return (x, y) => {
    const ox = Math.max(x0 - x, x - x1, 0), oy = Math.max(y0 - y, y - y1, 0);
    if (ox > far || oy > far) return Math.hypot(ox, oy) - hw;        // far away: the box's distance (a lower bound)
    let d = Infinity;
    for (let i = 1; i < n; i++) {
      const ex = vx[i] - vx[i - 1], ey = vy[i] - vy[i - 1], wx = x - vx[i - 1], wy = y - vy[i - 1];
      const t = clamp((wx * ex + wy * ey) / (ex * ex + ey * ey || 1e-12), 0, 1), bx = wx - ex * t, by = wy - ey * t, dd = bx * bx + by * by;
      if (dd < d) d = dd;
    }
    return Math.sqrt(d) - hw;
  };
};
// the line that runs at the distance d outside a smooth open line (to the left of its direction of travel if d > 0)
const beside = (line, d) => line.map((p, i) => {
  const a = line[Math.max(i - 1, 0)], b = line[Math.min(i + 1, line.length - 1)], l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-9;
  return [p[0] + ((b[1] - a[1]) / l) * d, p[1] - ((b[0] - a[0]) / l) * d];
});
// A plus: two bars of thickness t crossing in their middles at (cx, cy), each reaching `half` to either side.
const plus = (cx, cy, half, t) => {
  const h = t / 2;
  return [[cx - h, cy - half], [cx + h, cy - half], [cx + h, cy - h], [cx + half, cy - h], [cx + half, cy + h], [cx + h, cy + h],
    [cx + h, cy + half], [cx - h, cy + half], [cx - h, cy + h], [cx - half, cy + h], [cx - half, cy - h], [cx - h, cy - h]];
};

// ---- two bars crossed ----------------------------------------------------------------------------------------------
// The cross that strikes something out, exactly as drawn/symbol_head_front.js draws it on the face of "Kill" (the
// same construction and colours; it is not exported there): two straight bars of one width crossing in their middles
// at 45 degrees, one piece, deepening to the edge with a thin dark line along it, no black border.
const CROSS_RED = { rim: '#6a0e02', edge: '#a41804', body: '#c8250a' };
const cross = (c, at, half, w, palette = CROSS_RED) => {
  const k = half * Math.SQRT1_2, [x, y] = at;
  const shape = S.union(S.bar(x - k, y - k, x + k, y + k, w), S.bar(x - k, y + k, x + k, y - k, w));
  c.fill(shape, F.deepening(c.k, palette, { depth: 0.45, rim: 0.12 }));
  return shape;
};

// ---- rings round the head ------------------------------------------------------------------------------------------
// The head's outline in the icon as an open line: from the jaw on the left up its side, over the top and down the
// right side, as far down as `to` below the top of the head (bust units).
const headLine = (pl, form, to) => {
  const half = [];
  for (const p of H.halfOutline(form).pts) { if (p[1] > to) break; half.push(p); }
  const at = onBust(pl);
  return resample(half.slice(1).reverse().map(([u, v]) => at(-u, v)).concat(half.map(([u, v]) => at(u, v))), 0.06);
};
// the stretches of a line that satisfy keep(x, y), each as a line of its own
const pieces = (line, keep) => {
  const out = []; let cur = null;
  for (const p of line) { if (keep(p[0], p[1])) { if (!cur) out.push(cur = []); cur.push(p); } else cur = null; }
  return out.filter((l) => l.length > 1);
};
// A thin line of light: a core of full strength that dies away to both sides (hw: its half-width out to nothing).
const softLine = (c, pts, hw, colour, strength = 0.75, core = 0.3) => {
  const col = P.hex(colour);
  c.fill(lineShape(pts, hw), (px) => { px.r = col[0]; px.g = col[1]; px.b = col[2]; px.a = strength * smooth(0, hw * (1 - core), -px.d); });
};

// ---- a question mark -----------------------------------------------------------------------------------------------
// One line of one width with round ends: a hook (three quarters of a circle of radius r about `at`, from its left
// end over the top and round to `turn` degrees below level on the right), a counter-curve that brings it back onto
// the axis heading straight down, a short stem, and a round dot under it. Returns the shape.
//   at: the hook's centre; r: its radius (to the middle of the line); hw: half the line's width;
//   turn: how far past level the hook runs (65); stem: the straight piece; gap: from the stem's end to the dot's middle
const question = (at, r, hw, { turn = 65, stem = 0.45, gap = 2.2, dot = 1.15 } = {}) => {
  const [cx, cy] = at, a = (turn * Math.PI) / 180, rho = (r * Math.cos(a)) / (1 - Math.cos(a));
  const end = [cx + r * Math.cos(a), cy + r * Math.sin(a)], ctr = [end[0] + rho * Math.cos(a), end[1] + rho * Math.sin(a)];
  const line = [...G.arcPts(cx, cy, r, 180, 360 + turn, 0.04), ...G.arcPts(ctr[0], ctr[1], rho, 180 + turn, 180, 0.04).slice(1)];
  const foot = line[line.length - 1];
  line.push([foot[0], foot[1] + stem]);
  return S.union(lineShape(line, hw), S.circle(cx, foot[1] + stem + gap, hw * dot));
};

// ---- a hollow in the figure ----------------------------------------------------------------------------------------
// A dark hole in a bust (an eye socket, a nose hole): black in its middle, the bust's saturated hue at its edge, so
// that it sinks into the modelling round it instead of lying on it like a patch. depth: how far in the black begins.
const hollow = (c, shape, hue, depth = 0.55) => {
  const q = HUE[hue], sat = lin(q.sat), deep = lin(q.deep), dark = lin(q.dark);
  c.glow(shape, q.sat, 0.45, 0.55);                                   // the shadow round its edge
  c.fill(shape, (px) => {
    const t = clamp(-px.d / depth, 0, 1);
    put(px, t < 0.5 ? mix3(sat, deep, t * 2) : mix3(deep, dark, t * 2 - 1));
  });
};

// the colour a bust has at a key of its modelling (0: the saturated hue .. 255: white), as sRGB 0..1
const tone = (hue, key) => { const px = {}; H.ramps[hue](key, px); return [px.r, px.g, px.b]; };

// ---- the skull's face ----------------------------------------------------------------------------------------------
// "Cure" and "Plague" show the bust with a skull's face. In the game (head 11 pixels wide): two dark eye sockets
// three pixels wide and two high, their middles 3 to each side of the axis and 7.2 below the top of the head (black
// in the middle, the hue's dark round it); between them the bridge of the nose stays white; a nose hole on the axis,
// one pixel at 8.2 and three at 9.2 to 10.2 below the top (a triangle standing on its base); the cheeks under the
// sockets hollow (two columns of the mid hue down each side of the face, 9 to 13 below the top), the middle of the
// lower face light; a darker groove down the middle of the forehead (three columns wide, 1.5 to 5.5 below the top).
// Here: the sockets are ellipses large enough to take the bust's own brows and eyes into them (1.65 by 1.35, their
// outer ends 8 degrees down, as a skull's are), the nose hole a triangle with rounded corners over the bust's nose
// tip, the hollows and the groove soft shades of the bust's own hue. All in the bust's frame: they scale with it.
const SKULL = { eye: [2.85, 7.2], rx: 1.65, ry: 1.35, tilt: 8, nose: [8.3, 10.5], half: 0.95, cheek: [3.5, 10.7, 1.15, 2.1], groove: [3.4, 0.8, 2.0] };
const skull = (c, pl, hue, mask, q = SKULL) => {
  const at = onBust(pl), s = pl.s;
  for (const side of [-1, 1]) {
    const [x, y] = at(side * q.cheek[0], q.cheek[1]);
    c.blob(x, y, q.cheek[2] * s, q.cheek[3] * s, tone(hue, 70), 0.62, { mask });
  }
  const g = at(0, q.groove[0]);
  c.blob(g[0], g[1], q.groove[1] * s, q.groove[2] * s, tone(hue, 120), 0.5, { mask });
  for (const side of [-1, 1]) {
    const [x, y] = at(side * q.eye[0], q.eye[1]);
    hollow(c, S.ellipse(x, y, q.rx * s, q.ry * s, side * q.tilt), hue, 0.6 * s);
  }
  const top = at(0, q.nose[0]), l = at(-q.half, q.nose[1]), r = at(q.half, q.nose[1]);
  hollow(c, S.rounded([top, r, l], 0.3 * s), hue, 0.42 * s);
};

// ---- a medical cross on the chest ----------------------------------------------------------------------------------
// A white plus with a black line round it and a white light round that, on the bust (the game: a white plus, a black
// line one pixel wide, a white line one pixel wide). half, t: the plus with its black line (the room it takes in the
// game); the line is the bust's own border width, so the white is that much smaller. mask: the bust (the light stays
// on it).
const badgePlus = (c, at, half, t, mask, { border = H.BORDER, halo = 0.8, hue = 'blue' } = {}) => {
  const pts = plus(at[0], at[1], half - border, t - 2 * border), out = S.polygon(plus(at[0], at[1], half, t));
  c.layer((top) => top.glow(out, '#ffffff', halo, 0.95), { mask });
  c.fill(out, P.flat(H.INK));
  c.fill(S.polygon(pts), P.byDepth(0.3, [[0, HUE[hue].pale], [1, '#ffffff']]));
  return pts;
};

module.exports = { CHEST_TOP, chest, AURA, SMALL, onBust, HUE, tone, bow, filletPath, resample, taperStroke, lineShape, beside, headLine, pieces, softLine, question, plus, cross, CROSS_RED, hollow, skull, SKULL, badgePlus, lin, mix3, put, smooth };
