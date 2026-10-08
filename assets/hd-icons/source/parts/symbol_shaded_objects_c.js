'use strict';
// Shared pieces of the icons drawn in drawn/symbol_shaded_objects_c.js (the wrench, the light side's emblem, the
// stance, the hands and fists, the door, the container, the hand that resists energy).
//
// The GAME's icon gives each design: outline, proportions, what lies in front of what, where each colour is (read off
// its pixels with tools/vmap.py and tools/objects_c_hex.py; its edges are measured below the pixel from its
// anti-aliasing with tools/objects_c_edge.py). ChatGPT's redraw only shows what a thing is. Every outline is straight
// lines and circular arcs with stated dimensions; black borders are laid first; shading is formulas and stays soft and
// structural: a lit side and a shaded side, a colour that deepens to the edge of its shape, a thin dark line on the
// edge. Units: the game icon's pixels (frame 32 x 32, y down). The light stands above and to the left, as in the game.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');

const INK = '#0a0a0c';
// The black line round a body: one unit, the one pixel of the game's icons, as on the other icons of this sheet
// (parts/symbol_shaded_objects.js).
const BORDER = 1.0;
// the thin dark line along the very edge of a body, as on the other sheets
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
// the same through a smooth line (a cubic through the values, its slope at each the mean of its neighbours'): for
// levels along an object, where straight pieces would show as bands
const flow = (stops) => {
  const n = stops.length, m = stops.map((s, i) => { const a = stops[Math.max(i - 1, 0)], b = stops[Math.min(i + 1, n - 1)]; return (b[1] - a[1]) / (b[0] - a[0] || 1e-9); });
  return (t) => {
    if (t <= stops[0][0]) return stops[0][1];
    if (t >= stops[n - 1][0]) return stops[n - 1][1];
    let i = 0;
    while (i < n - 2 && t > stops[i + 1][0]) i++;
    const a = stops[i], b = stops[i + 1], h = b[0] - a[0], u = (t - a[0]) / h, u2 = u * u, u3 = u2 * u;
    return (2 * u3 - 3 * u2 + 1) * a[1] + (u3 - 2 * u2 + u) * h * m[i] + (-2 * u3 + 3 * u2) * b[1] + (u3 - u2) * h * m[i + 1];
  };
};
// one pixel of soft edge where a formula changes colour across the line v = 0 (v in units, k pixels per unit)
const step = (v, k) => clamp(v * k + 0.5, 0, 1);

// ---- the game's blues ------------------------------------------------------------------------------------------------
// The same ramp as parts/symbol_shaded_objects.js (the sheet's icons carry one blue): every blue of these icons lies
// on it, from white through 0x9fb3ff and 0x3c64ff down to navy, and its green channel falls evenly along it. A shade
// is given by its green level (0 to 255, as read off a pixel of the game).
const TONE = ramp([[0x00, '#00020a'], [0x0b, '#000b33'], [0x11, '#001151'], [0x1a, '#001a7c'], [0x26, '#0026b8'], [0x2e, '#022ed9'], [0x39, '#0d39e4'],
  [0x48, '#1c48f3'], [0x57, '#2b57ff'], [0x64, '#3c64ff'], [0x7b, '#597bff'], [0x8b, '#6e8bff'], [0x9f, '#869fff'], [0xb3, '#9fb3ff'], [0xc4, '#b5c4ff'],
  [0xd7, '#cdd7ff'], [0xec, '#e7ecff'], [0xff, '#ffffff']]);
// the greys of the waves round the hand that resists energy: black to white, by level
const GREY = (g) => { const v = P.toLinear(clamp(g, 0, 255) / 255); return [v, v, v]; };
// The thin dark line on a body's edge is the body's own colour 95 levels deeper.
const rimLevel = (g) => Math.max(g - 95, 0x12);
// a level laid on a pixel, with the thin dark line where the pixel lies within RIM of its shape's edge
const shade = (px, g, k, rim = RIM, tone = TONE) => put(px, mix3(tone(clamp(g, 0, 255)), tone(rimLevel(g)), rim > 0 ? step(rim + px.d, k) : 0));

// ---- fields ----------------------------------------------------------------------------------------------------------
// a Gaussian blur of a square field (sigma in pixels), edges held
const blur = (src, n, sigma) => {
  const r = Math.max(1, Math.ceil(sigma * 2.5)), w = new Float32Array(2 * r + 1);
  let tot = 0;
  for (let i = -r; i <= r; i++) { w[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); tot += w[i + r]; }
  for (let i = 0; i < w.length; i++) w[i] /= tot;
  const tmp = new Float32Array(n * n), out = new Float32Array(n * n);
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * src[j * n + clamp(x + t, 0, n - 1)]; tmp[j * n + x] = a; }
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * tmp[clamp(j + t, 0, n - 1) * n + x]; out[j * n + x] = a; }
  return out;
};
// How far the edge nearest to each place is turned to the light: 1 facing it, -1 turned away. `to` is the direction
// towards the light as seen on the icon ([-1, -1]: above and to the left). Taken from the direction of the shape's
// distances and smoothed over `soft` units, so that the change from one side of a body to the next is a gradient.
const facing = (c, shape, to = [-1, -1], soft = 0.3) => {
  const f = c.field(shape), n = c.size, out = new Float32Array(n * n), l = Math.hypot(to[0], to[1]), lx = to[0] / l, ly = to[1] / l;
  for (let j = 0, i = 0; j < n; j++) {
    for (let x = 0; x < n; x++, i++) {
      const gx = f[x < n - 1 ? i + 1 : i] - f[x > 0 ? i - 1 : i], gy = f[j < n - 1 ? i + n : i] - f[j > 0 ? i - n : i], gl = Math.hypot(gx, gy) || 1;
      out[i] = (gx * lx + gy * ly) / gl;
    }
  }
  return soft > 0 ? blur(out, n, soft * c.k) : out;
};

// ---- a plate with a bevelled edge --------------------------------------------------------------------------------------
// The look of the game's tools and panels: a flat piece of metal whose edge is bevelled. The bevels turned to the
// light are pale, those turned away are deep blue; a white line runs along the outer edge all round (dimmer where the
// edge is turned fully away).
//   lit, shaded   the level by depth from the edge, on bevels turned to the light and away from it ([[depth, level]..])
//   rim           [level turned away, level elsewhere, the line's width, the width over which it dies away]
//   extra         (px, g, lit) -> level: anything the object adds (a line of light along a handle)
const PLATE = {
  lit: [[0.8, 0xb6], [1.5, 0xa2], [2.5, 0x90], [3.5, 0x86]],
  shaded: [[0.8, 0x52], [1.2, 0x48], [1.9, 0x48], [2.6, 0x6e], [3.1, 0x86]],
  rim: [0xb8, 0xff, 0.62, 0.42],
};
const plate = (c, shape, o = {}) => {
  const q = { ...PLATE, ...o }, k = c.k, F = facing(c, shape, q.to, q.soft), gl = curve(q.lit), gs = curve(q.shaded);
  const [rimAway, rimLit, rimW, rimSoft] = q.rim;
  c.fill(shape, (px) => {
    const depth = -px.d, f = F[px.i], lit = smooth(-0.3, 0.3, f);
    let g = gs(depth) + (gl(depth) - gs(depth)) * lit;
    if (q.extra) g = q.extra(px, g, lit);
    const rim = rimAway + (rimLit - rimAway) * smooth(-0.95, -0.6, f);
    g += (rim - g) * (1 - smooth(rimW, rimW + rimSoft, depth));
    shade(px, g, k);
  });
};

// A path of straight pieces with its corners rounded by circular arcs of radius r (cut down where a piece is too
// short): the points of the rounded path.
const roundPath = (pts, r) => {
  const out = [pts[0]];
  for (let i = 1; i + 1 < pts.length; i++) {
    const A = pts[i - 1], B = pts[i], Cn = pts[i + 1];
    const la = Math.hypot(A[0] - B[0], A[1] - B[1]), lc = Math.hypot(Cn[0] - B[0], Cn[1] - B[1]);
    const ax = (A[0] - B[0]) / la, ay = (A[1] - B[1]) / la, cx = (Cn[0] - B[0]) / lc, cy = (Cn[1] - B[1]) / lc;
    const half = Math.acos(clamp(ax * cx + ay * cy, -1, 1)) / 2;
    if (half < 1e-3 || half > Math.PI / 2 - 1e-3) { out.push(B); continue; }
    let t = r / Math.tan(half), rr = r;
    const most = Math.min(la, lc) * 0.5;
    if (t > most) { t = most; rr = t * Math.tan(half); }
    let bx = ax + cx, by = ay + cy; const bl = Math.hypot(bx, by); bx /= bl; by /= bl;
    const ox = B[0] + (bx * rr) / Math.sin(half), oy = B[1] + (by * rr) / Math.sin(half);
    const a1 = Math.atan2(B[1] + ay * t - oy, B[0] + ax * t - ox);
    let da = Math.atan2(B[1] + cy * t - oy, B[0] + cx * t - ox) - a1;
    while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    const steps = Math.max(2, Math.ceil((Math.abs(da) * rr) / 0.08));
    for (let s = 0; s <= steps; s++) { const a = a1 + (da * s) / steps; out.push([ox + rr * Math.cos(a), oy + rr * Math.sin(a)]); }
  }
  out.push(pts[pts.length - 1]);
  return out;
};

// A line of light along a path of straight pieces (points [[x, y], ...]): how strongly it lies on the place (x, y),
// 0 .. 1. It is `w` wide (the distance at which it has fallen to 1/e) and comes to a point over `taper` at both ends.
const lightLine = (pts, w, taper) => {
  const seg = [];
  let total = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    seg.push({ a, ux: (b[0] - a[0]) / len, uy: (b[1] - a[1]) / len, len, from: total });
    total += len;
  }
  return (x, y) => {
    let best = Infinity, at = 0;
    for (const s of seg) {
      const t = clamp((x - s.a[0]) * s.ux + (y - s.a[1]) * s.uy, 0, s.len), d = Math.hypot(x - s.a[0] - s.ux * t, y - s.a[1] - s.uy * t);
      if (d < best) { best = d; at = s.from + t; }
    }
    const width = w * clamp(Math.min(at, total - at) / taper, 0, 1);
    return width > 1e-4 ? bell(best, width) : 0;
  };
};

module.exports = { INK, BORDER, RIM, lin, mix3, put, smooth, bell, ramp, curve, flow, step, TONE, GREY, rimLevel, shade, blur, facing, PLATE, plate, roundPath, lightLine };
