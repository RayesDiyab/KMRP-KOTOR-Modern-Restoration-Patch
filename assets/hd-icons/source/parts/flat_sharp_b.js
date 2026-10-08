'use strict';
// Pieces shared by the combat symbols of drawn/flat_sharp_b.js: the bullet (rapid shot, power shot).
// Built like parts/weapons.js and parts/flat.js: every outline is a polygon of straight lines and circular arcs from
// measured dimensions, the black border is the same outline moved out, and every gradient is a formula in the
// object's own frame. Shapes, proportions and colours are read off the GAME's pixels (tools/vmap.py,
// tools/sharp_b_px.py); the redraws only helped to see what a thing is.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const W = require('./weapons');
const { clamp } = S;

const BLACK = '#0a0a0c';
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = 1; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bell = (d, w) => Math.exp(-(d * d) / (w * w));
// a colour picked off stops [[t, colour], ...] (mixed in linear light), as linear values
const rampLin = (stops) => {
  const ts = stops.map((s) => s[0]), cs = stops.map((s) => lin(s[1]));
  return (t) => {
    let i = 0;
    while (i < ts.length - 2 && t > ts[i + 1]) i++;
    return mix3(cs[i], cs[i + 1], clamp((t - ts[i]) / (ts[i + 1] - ts[i] || 1e-9), 0, 1));
  };
};

// ---- curves as points ------------------------------------------------------------------------------------------------
// A circular arc from p to q that stands `sag` off their chord at its middle (to the right of the direction p to q as
// seen on screen; negative: to the left): its points, p and q included.
const bow = (p, q, sag, step = 0.05) => {
  if (Math.abs(sag) < 1e-6) return [p, q];
  const f = G.frame(p, q), h = f.L / 2, R = (h * h + sag * sag) / (2 * Math.abs(sag)), side = sag > 0 ? 1 : -1;
  const ctr = f.pt(h, -side * (R - Math.abs(sag))), deg = (v) => (Math.atan2(v[1] - ctr[1], v[0] - ctr[0]) * 180) / Math.PI;
  let a0 = deg(p), a1 = deg(q);
  if (side > 0) { while (a1 > a0) a1 -= 360; } else { while (a1 < a0) a1 += 360; }
  return G.arcPts(ctr[0], ctr[1], R, a0, a1, step);
};
// points on an ellipse about (cx, cy) with half-axes rx, ry, from angle a0 to a1 (degrees of its parameter)
const ellipsePts = (cx, cy, rx, ry, a0, a1, n = 160) => {
  const out = [];
  for (let i = 0; i <= n; i++) { const a = ((a0 + ((a1 - a0) * i) / n) * Math.PI) / 180; out.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]); }
  return out;
};
// mirror image about the level line y = cy (the order of the points reversed, so the outline keeps its sense)
const flipped = (pts, cy) => pts.map(([x, y]) => [x, 2 * cy - y]).reverse();
// The same arc, its side given by a point instead of a sign: with sag > 0 it bows away from `from`, with sag < 0
// towards it (so that a shape can be described from its middle line: "bowed out by 0.8").
const bowFrom = (p, q, sag, from, step) => {
  const f = G.frame(p, q), side = f.s(from[0], from[1]) > 0 ? -1 : 1;
  return bow(p, q, side * sag, step);
};

// ---- the dark sword of power attack -----------------------------------------------------------------------------------
// In the game the sword of the three power attack icons is the plain red sword of "attack" gone dark: a black sword
// as large as that one with its border (five pixels across the blade), and down its middle a thin red sword, one
// pixel wide. Both are one body each; the red one is drawn like the sheet's other red bodies.
// Read off the game's pixels (their weights give the widths: a pixel of 941500 is 0.78 covered by the full red be1b00):
//   red     29.6 long; blade 0.8 to 0.95 wide; cross-guard 6.5 long and 0.7 thick, its middle 7.2 from the grip's
//           end; grip 0.55. (Here the guard is thinner than blade and grip, by the user's rule for swords: 0.6, 0.9, 0.75.)
//   black   2.1 to 2.4 to either side of the red blade's middle (2.25); its point a gable with sides at 45 degrees,
//           1.4 beyond the red point; round the guard 1.5 beyond its ends and 1.9 to either side of its middle; round
//           the grip 2.1 to either side; its lower end a gable like the point, 1.9 beyond the red end
const DARK_SWORD = {
  L: 29.6,
  red: { pommel: 0.8, grip: 1.5, guardAt: 7.2, guard: 6.5, guardT: 1.1, guardPoint: 0.6, blade: 1.8, taper: 1.5 },   // (thicker than the game's one pixel, and the guard's ends pointed: the user's corrections)
  black: { below: 1.9, above: 1.4, pommel: 2.1, grip: 4.6, guard: 9.5, guardT: 3.8, guardPoint: 1.4, blade: 4.9, taper: 2.45 },
};
// f: the frame of the RED sword (from its grip's end to its point). part: 'black' | 'red' (both if not given)
const darkSword = (c, f, part, q = DARK_SWORD) => {
  if (part !== 'red') {
    const b = q.black, fb = G.frame(f.pt(-b.below, 0), f.pt(q.L + b.above, 0));
    c.fill(S.polygon(fb.pts(W.swordOutline(fb.L, { ...b, guardAt: q.red.guardAt + b.below }))), P.flat(BLACK));
  }
  if (part !== 'black') W.glowSword(c, f.E, f.pt(q.L, 0), q.red, { palette: 'red', core: 0, plain: true, border: 0, depth: 0.5, rim: 0.1 });
};
// the black sword's outline alone (for cutting it out of other shapes or measuring against it)
const darkSwordPts = (f, q = DARK_SWORD) => {
  const b = q.black, fb = G.frame(f.pt(-b.below, 0), f.pt(q.L + b.above, 0));
  return fb.pts(W.swordOutline(fb.L, { ...b, guardAt: q.red.guardAt + b.below }));
};

// ---- the bullet ----------------------------------------------------------------------------------------------------
// A cartridge seen from the side, flying to the right. In the game it is ONE small picture, used at two sizes: 15.5
// long and 6 high (rapid shot I, power shot I to III) and 10 long and 4 high (rapid shot II and III): a square base,
// a straight case, a nose that is half a circle of the case's half height (its edge pixels fit a circle of radius 3
// about the point 3 before the tip), and a band two pixels wide one pixel in from the base.
// Its colours, row by row down the case (six rows), where no light falls: fa583e, ff8e7c, ffb0a3, ff8470, ff6046,
// f45237: a salmon red, palest a little above the middle and deepest along the lower edge; the nose's rim is the deep
// red be1b00. A light lies along the third row (one sixth of the half height above the axis): strongest (ffebe7)
// over the middle of the case, weaker beside the band and towards the nose, and it also lightens the rows next to it.
// The band is grey in rapid shot (515151 to 7e7e7e, palest on the light's row) and a deeper red in power shot
// (c62308 to f35035).
// Here: ONE bullet for all icons, 15.5 x 6, drawn at scale 1 or 2/3 (the small one comes out 10.33 x 4).
const BULLET = {
  L: 15.5, H: 6,
  band: [1.0, 3.0],               // the band: from here to here, measured from the base
  axis: -1 / 6,                   // where the light runs: this share of the half height off the axis (minus: above)
  light: [0.03, 0.26, 0.71, 0.9], // the light along the length (shares of it): its point at the base, the stretch at full strength, its point on the nose
  core: 0.2, halo: 0.95,          // half the thickness of the light's white line, and how far its glow reaches
  border: 0.7,
};
// the case's colour across it: from -1 (upper edge) to +1 (lower edge), read off the game's rows where no light falls
const CASE = [[-1, '#f24f36'], [-0.833, '#fa583e'], [-0.5, '#ff8e7c'], [-1 / 6, '#ffb0a3'], [1 / 6, '#ff8470'], [0.5, '#ff6046'], [0.833, '#f45237'], [1, '#e84a30']];
const BAND = {
  grey: [[-1, '#4a4a4a'], [-0.833, '#525252'], [-0.5, '#646464'], [-1 / 6, '#787878'], [1 / 6, '#6c6c6c'], [0.5, '#5c5c5c'], [0.833, '#505050'], [1, '#484848']],
  red: [[-1, '#be1e05'], [-0.833, '#c62308'], [-0.5, '#da371c'], [-1 / 6, '#ec492e'], [1 / 6, '#e23f24'], [0.5, '#d02d12'], [0.833, '#c62308'], [1, '#bc1c03']],
};
const DEEP = '#be1b00', RIM = '#5e0703';

// the bullet's outline: base at x0, axis on yc, k its scale
const bulletPts = (x0, yc, k = 1, q = BULLET) => {
  const r = (q.H * k) / 2, x1 = x0 + q.L * k;
  return [[x0, yc - r], ...G.arcPts(x1 - r, yc, r, -90, 90, 0.05), [x0, yc + r]];
};
// The bullet. st: band ('grey' | 'red'), part ('border' | 'body': one of the two only), border (0 = none)
const bullet = (c, x0, yc, k = 1, st = {}) => {
  const q = st.dims || BULLET, L = q.L * k, r = (q.H * k) / 2, xn = x0 + L - r, v0 = q.axis, pk = c.k;
  const border = st.border === undefined ? q.border : st.border;
  const pts = bulletPts(x0, yc, k, q), shape = S.polygon(pts);
  if (border > 0 && st.part !== 'body') c.fill(S.polygon(G.offsetPts(pts, border)), P.flat(st.ink || BLACK));
  if (st.part === 'border') return { pts, shape, x1: x0 + L, r };
  // Where a place stands across the case: -1 on the upper edge, +1 on the lower, v0 on the light's line. On the nose
  // the same is measured from the end of the light's line out to the nose's circle, so that every band of colour
  // comes to a rounded end inside the nose.
  const across = (x, y) => {
    const ax = (x - xn) / r, v = (y - yc) / r;
    if (ax <= 0) return v;
    const dy = v - v0, dl = Math.hypot(ax, dy);
    if (dl < 1e-9) return v0;
    const uy = dy / dl, b = v0 * uy, far = dl / (-b + Math.sqrt(b * b + 1 - v0 * v0));      // 0 at the line's end, 1 on the circle
    return dy < 0 ? v0 - far * (1 + v0) : v0 + far * (1 - v0);
  };
  // the light: a line from a to d along the case, at full strength from b to c, and how strong it is at a place
  const [la, lb, lc, ld] = q.light.map((s) => x0 + s * L), ya = yc + v0 * r;
  const strength = (x) => clamp(Math.min((x - la) / (lb - la), (ld - x) / (ld - lc)), 0, 1);
  const white = [1, 1, 1], halo = q.halo * k, core = q.core * k, bf = c.field(shape);
  // (the distance to the BULLET's outline decides the deepening, also on the band: the band has no edge of its own)
  const shade = (ramp, glow, deep, rim) => (px) => {
    const d = bf[px.i];
    let col = ramp(clamp(across(px.x, px.y), -1, 1));
    // the light's glow: falls off smoothly from its line, and is weaker where the line is weaker
    const s = strength(px.x);
    col = mix3(col, white, glow * s * bell(Math.max(Math.abs(px.y - ya) - core * s, 0), halo));
    // deeper to the edge, and a thin dark line along it
    col = mix3(col, deep, 0.8 * smooth(0.5 * k, 0, -d));
    put(px, mix3(col, rim, clamp((0.13 * Math.sqrt(k) + d) * pk + 0.5, 0, 1)));
  };
  c.fill(shape, shade(rampLin(CASE), 0.78, lin(DEEP), lin(RIM)));
  // the light's white line: full thickness from b to c, drawn in to a point at either end
  c.fill(S.polygon([[la, ya], [lb, ya - core], [lc, ya - core], [ld, ya], [lc, ya + core], [lb, ya + core]]), P.flat('#ffffff'));
  // the band: a ring round the case, lit like the case
  const b0 = x0 + q.band[0] * k, b1 = x0 + q.band[1] * k, grey = st.band !== 'red';
  c.fill(S.intersect(shape, S.polygon([[b0, yc - r - 1], [b1, yc - r - 1], [b1, yc + r + 1], [b0, yc + r + 1]])),
    shade(rampLin(BAND[grey ? 'grey' : 'red']), grey ? 0.3 : 0.2, lin(grey ? '#3c3c3c' : '#9a1400'), lin(grey ? '#202022' : RIM)));
  return { pts, shape, x1: x0 + L, r };
};
// several bullets: all their black borders first, then the bullets (no border cuts into a neighbour)
const bullets = (c, list, st = {}) => { for (const part of ['border', 'body']) for (const [x, y, k] of list) bullet(c, x, y, k, { ...st, part }); };

module.exports = { BULLET, bulletPts, bullet, bullets, bow, bowFrom, ellipsePts, flipped, DARK_SWORD, darkSword, darkSwordPts, BLACK, lin, mix3, put, smooth, bell, rampLin };
