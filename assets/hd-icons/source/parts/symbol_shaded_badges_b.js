'use strict';
// The second part of the sheet symbol_shaded_badges: the badges that parts/symbol_shaded_badges.js does not hold, and
// the objects and signs that lie on them. The badge of the sheet (its centre, its border's width, where its light
// comes from, the band of deep blue along a disc's edge) is taken from there: nothing of it is built twice.
//
// The GAME's icon gives each design (tools/vmap.py, tools/badges_vhex.py: its pixels as letters and as colours).
// ChatGPT's redraw only shows what a thing is. Outlines are straight lines and circles of stated dimensions; shading
// is formulas. Units: the vanilla icon's pixels (frame 32 x 32, y down).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const B = require('./symbol_shaded_badges');

const { hypot, atan2, abs, min, max, exp, cos, sin, sqrt, PI } = Math;
const { clamp } = S;
const { X, Y, lin, mix3, put, smooth, bell, ramp3, WHITE } = B;

const INK = B.INK;
// the width of the black border of every badge of the sheet (outer edge to the disc's edge: 1.95)
const W_BORDER = B.R_OUT - B.R_DISC;

// ---- the game's blues ------------------------------------------------------------------------------------------------
// Every blue of the game's icons lies on one ramp from white through 9fb3ff and 3c64ff down to navy, and its green
// channel falls evenly along it (parts/symbol_shaded_objects.js found the same on its sheet). A shade is given here
// by its green level, 0 to 255, as read off a pixel of the game: 5a7cff is level 0x7c.
const TONE = ramp3([[0x00, '#00020a'], [0x0b, '#000b33'], [0x11, '#001151'], [0x1a, '#001a7c'], [0x26, '#0026b8'], [0x2e, '#022ed9'], [0x39, '#0d39e4'],
  [0x48, '#1c48f3'], [0x57, '#2b57ff'], [0x64, '#3c64ff'], [0x7b, '#597bff'], [0x8b, '#6e8bff'], [0x9f, '#869fff'], [0xb3, '#9fb3ff'], [0xc4, '#b5c4ff'],
  [0xd7, '#cdd7ff'], [0xec, '#e7ecff'], [0xff, '#ffffff']]);
// a curve through measured values: stops = [[t, value], ...] with t rising, straight between them
const curve = (stops) => (t) => {
  let i = 0;
  while (i < stops.length - 2 && t > stops[i + 1][0]) i++;
  const a = stops[i], b = stops[i + 1];
  return a[1] + (b[1] - a[1]) * clamp((t - a[0]) / (b[0] - a[0] || 1e-9), 0, 1);
};
// one pixel of soft edge where a formula changes colour across the line v = 0 (v in units, k pixels per unit)
const step = (v, k) => clamp(v * k + 0.5, 0, 1);
// The thin dark line on the very edge of a body (0.13 wide, as on the other sheets): the body's own colour 95 levels
// deeper, never lighter than level 0x12.
const RIM = 0.13;
const rimLevel = (g) => max(g - 95, 0x12);
// a level laid on a pixel of a shape, with the thin dark line where the pixel lies within `rim` of the shape's edge
const shade = (px, g, k, rim = RIM) => put(px, mix3(TONE(clamp(g, 0, 255)), TONE(rimLevel(g)), rim > 0 ? step(rim + px.d, k) : 0));
// a rectangle by its corners
const rect = (x0, y0, x1, y1) => S.box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2);

// ---- the skill badge ---------------------------------------------------------------------------------------------
// The badge of the five skill icons (boost, computer use, demolitions, repair, security): a black border, and in it a
// ring of blue light that falls away into a black middle.
// Measured on the game's icons, in directions clear of the object (tools/badges_vprofile.py):
//   the border's outer edge   15.1 above, below and at the sides, 15.6 on the diagonals (a pixelled circle), 15.4 by
//                             area; the game's frame does not cut it
//   the blue's edge           13.05; the border is black from there out
//   outside the black         a fringe of blue: 031a72 at three quarters of full opacity, 0a33d1 at a third
//   the face by radius        pixel rows above the middle 12.5: 496eff, 11.5: 3f66ff, 10.5: 1e4af5, 9.5: 012dd8,
//                             8.5: 001667, 7.5: 000822, 6.5: 000208; below it 4b70ff, 496eff, 2c58ff, 0d39e4, 001e92,
//                             000d3c, 000411. The lower left is the lighter side (4d72ff against 4168ff at 11.75): the
//                             same face about a point 0.2 to the right of and 0.2 above the middle.
// Drawn in the manner of the sheet's other badges: the black is as wide as theirs (B.R_OUT - B.R_DISC, 1.95: the
// blue's edge comes to 13.15), and the disc's edge is the same deep blue line (B.discEdge). No line of light inside
// the edge: the game's has none, and the focus badge has none.
// The size is the game's: its frame does not cut these badges (they are smaller than the weapon badges there too),
// and their objects reach out over the border to the frame.
const SKILL = { black: 15.1, at: [X + 0.2, Y - 0.2], glow: ['#0c38e3', 0.4, 0.7] };
SKILL.disc = SKILL.black - W_BORDER;
// levels by distance from SKILL.at
const SKILL_FACE = curve([[5.7, 0x01], [6.3, 0x02], [6.7, 0x04], [7.3, 0x08], [7.7, 0x0d], [8.3, 0x16], [8.7, 0x1e], [9.3, 0x2d], [9.7, 0x39], [10.3, 0x4a],
  [10.7, 0x58], [11.3, 0x66], [11.7, 0x6e], [12.7, 0x70]]);
// the blue fringe outside a black border: a glow that is gone within three quarters of a unit
const fringe = (c, edge, q = SKILL.glow) => c.glow(edge, q[0], q[1], q[2]);
const skillBadge = (c) => {
  const q = SKILL, edge = S.circle(X, Y, q.black);
  fringe(c, edge);
  c.fill(edge, P.flat(INK));
  c.fill(S.circle(X, Y, q.disc), (px) => {
    put(px, B.discEdge(TONE(SKILL_FACE(hypot(px.x - q.at[0], px.y - q.at[1]))), q.disc - hypot(px.x - X, px.y - Y), 0));
  });
};

// ---- the padlock ---------------------------------------------------------------------------------------------------
// The padlock of the security badge is the padlock of isk_security pixel for pixel (parts/symbol_shaded_objects.js
// draws that one in its square): the same dimensions and the same tones are used here, without the black round it,
// which the badge's padlock does not have.
//   the shackle: x 10..22, from y 7 down into the body, its bar 2 wide: the outer half c8, the inner half e2, both
//   deepening down the legs (a5 and b5 where they meet the body). Through it the badge's black middle is seen.
//   On the badge the left leg shows its inner side, one unit wide and blue (0f3be6 at the top, 0027bd below): the
//   shackle is seen a little from the right.
//   the body: x 8..24, y 14..24 with a lower face y 24..25 (6383ff); on it a light rim 1 wide (f0 above, e8 below, d5
//   at the sides), a panel x 11..21, y 16..22 (c7d3ff), and between them a face that falls from bc at the upper left
//   to 9c at the lower right
const LOCK = { shackle: [10, 7, 22, 14], bar: 2, inner: 1, body: [8, 14, 24, 24], under: 1, rim: 1, panel: [11, 16, 21, 22] };
const padlock = (c) => {
  const q = LOCK, k = c.k, [hx0, hy0, hx1, hy1] = q.shackle, [bx0, by0, bx1, by1] = q.body, [px0, py0, px1, py1] = q.panel;
  // the inner side of the left leg
  c.fill(rect(hx0 + q.bar - 0.5, hy0 + q.bar, hx0 + q.bar + q.inner, hy1 + 0.5), (px) => shade(px, 0x3b - 4.5 * (px.y - hy0 - q.bar), k));
  // the shackle: one bar of one width, lighter along its inner half, deepening down its legs
  const bow = S.subtract(rect(hx0, hy0, hx1, hy1 + 1), rect(hx0 + q.bar, hy0 + q.bar, hx1 - q.bar, hy1 + 2));
  const of = c.field(rect(hx0, hy0, hx1, hy1 + 9));
  c.fill(bow, (px) => {
    const t = clamp(-of[px.i] / q.bar, 0, 1);                        // 0 at the bar's outer edge, 1 at its inner
    shade(px, 0xc8 + (0xe4 - 0xc8) * smooth(0.25, 0.75, t) - 11 * max(px.y - 10.5, 0), k);
  });
  // the body: its lower face, then the top face with rim and panel
  c.fill(rect(bx0, by1 - 0.5, bx1, by1 + q.under), (px) => shade(px, 0x8c - 0x10 * (px.y - by1) / q.under, k));
  c.fill(rect(bx0, by0, bx1, by1), (px) => {
    const x = px.x, y = px.y, l = x - bx0, t = y - by0, r = bx1 - x, b = by1 - y, depth = min(l, t, r, b);
    // the face between rim and panel falls along the diagonal away from the light
    const field = 0xbc - 1.6 * ((x - bx0 - q.rim) + (y - by0 - q.rim));
    // the rim: white above and below, a little less at the two sides
    const upDown = smooth(-0.5, 0.5, min(l, r) - min(t, b));
    const rim = 0xd6 + (t < b ? 0xf2 - 0xd6 : 0xea - 0xd6) * upDown;
    shade(px, field + (rim - field) * (1 - smooth(q.rim - 0.3, q.rim + 0.3, depth)), k, by1 - y < RIM * 2 ? 0 : RIM);
  });
  c.fill(rect(px0, py0, px1, py1), (px) => shade(px, 0xd9 - 0.6 * ((px.x - px0) + (px.y - py0)), k, 0));
};

module.exports = { INK, W_BORDER, TONE, curve, step, RIM, rimLevel, shade, rect, SKILL, fringe, skillBadge, LOCK, padlock };
