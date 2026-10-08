'use strict';
// The objects on the skill badges: the two arrows (boost), the wrench (repair), the detonator (demolitions) and the
// computer (computer use). The padlock is in parts/symbol_shaded_badges_b.js with the badge.
//
// The game paints all of them alike: pale blue bodies with a line of white along their edges, no black round them,
// lit from the upper left (the sides that face down or to the right are the deep ones). Each is built here from what
// was read off the game's pixels (tools/objects_b_px.py: the green channel, which falls evenly along the game's blue
// ramp), as straight lines, circles and ellipses of stated dimensions. Units: the game's pixels (frame 32 x 32).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const B = require('./symbol_shaded_badges');
const Q = require('./symbol_shaded_badges_b');

const { hypot, abs, min, max, exp, cos, sin, atan2, sqrt, PI, SQRT1_2 } = Math;
const { clamp } = S;
const { lin, mix3, put, smooth, bell, WHITE } = B;
const { TONE, step, RIM } = Q;

// ---- lines of light ------------------------------------------------------------------------------------------------
// The white along an object's edges: full for LINE.core from the edge, then gone within LINE.soft (a crisp line
// with a soft inner side). The game's is one pixel of white; drawn finer, as the house's lines of light are.
const LINE = { core: 0.34, soft: 0.3 };
const lineAt = (d, core = LINE.core, soft = LINE.soft) => (d <= core ? 1 : exp(-((d - core) * (d - core)) / (soft * soft)));
// how far (x, y) lies from the stretch a to b
const toSeg = (x, y, a, b) => {
  const ex = b[0] - a[0], ey = b[1] - a[1], t = clamp(((x - a[0]) * ex + (y - a[1]) * ey) / (ex * ex + ey * ey || 1e-9), 0, 1);
  return hypot(x - a[0] - ex * t, y - a[1] - ey * t);
};
// the thin dark line on the very edge of a pale body whose edge is white (level 0xa0, as the house's white bodies)
const EDGE_RIM = TONE(0xa0);
// A face: a polygon filled with a level that may change over it. level: (x, y) => 0..255.
//   o.lines  stretches [a, b] (or [a, b, strength]) that carry a line of light, inside this face
//   o.rim    edges [a, b] of this face that lie on the object's outline: the thin dark line runs along them
const face = (c, pts, level, o = {}) => {
  const shape = S.polygon(pts), k = c.k, lines = o.lines || [], rims = o.rim || [], core = o.core === undefined ? LINE.core : o.core, soft = o.soft === undefined ? LINE.soft : o.soft;
  c.fill(shape, (px) => {
    let v = TONE(clamp(level(px.x, px.y), 0, 255)), w = 0;
    for (const l of lines) w = max(w, (l[2] === undefined ? 1 : l[2]) * lineAt(toSeg(px.x, px.y, l[0], l[1]), l[3] === undefined ? core : l[3], l[4] === undefined ? soft : l[4]));
    if (w > 0) v = mix3(v, WHITE, w);
    let r = 0;
    for (const e of rims) r = max(r, step(RIM - toSeg(px.x, px.y, e[0], e[1]), k));
    put(px, r > 0 ? mix3(v, EDGE_RIM, r) : v);
  });
  return shape;
};

// ---- the arrows (boost) ----------------------------------------------------------------------------------------------
// An arrow pointing right: a head with sides at 45 degrees and a shaft, the same above and below its line.
// tip: its point; half: the head's half-height (and so its length); stem: the shaft's half-height; len: its length
const arrowRight = (tip, half, stem, len) => {
  const [x, y] = tip, xb = x - half;
  return [[x, y], [xb, y + half], [xb, y + stem], [xb - len, y + stem], [xb - len, y - stem], [xb, y - stem], [xb, y - half]];
};
// Read off the game's pixels: the white arrow's head stands on x = 23 with its point at 31 (half-height 8, sides at
// 45 degrees: one pixel more to the row), its shaft is 7 rows high (half-height 3.5) and runs from x = 14; the
// second arrow behind it is the same arrow 12 to the left (head on 11, shaft from 2), in blue 5a7cff with a light
// on its tail: a6b8ff at x 3.5, a0b4ff at 4.5, 93a9ff, 7e99ff, 6b89ff, 6181ff, and 5a7cff from 9.5 on.
// Changed from the game: there both lie on y = 15.5, half a pixel above the badge's middle (seven rows cannot be
// centred on thirty-two); here they lie on the middle line.
const BOOST = { y: 16, half: 8, stem: 3.5, len: 9, white: 31, ghost: 19, level: 0x7c, light: [60, 3.4, 9.6], tail: [2.2, 3.4] };
const boostArrows = (c, q = BOOST) => {
  const k = c.k, ghost = arrowRight([q.ghost, q.y], q.half, q.stem, q.len), white = arrowRight([q.white, q.y], q.half, q.stem, q.len);
  // the arrow behind: one blue, deepening a little to its edge, the light on its tail
  c.fill(S.polygon(ghost), (px) => {
    const g = q.level + q.light[0] * (1 - smooth(q.light[1], q.light[2], px.x)) * smooth(q.tail[0], q.tail[1], px.x);
    Q.shade(px, g - 20 * (1 - smooth(0, 0.7, -px.d)), k);
  });
  // the white arrow: white, a touch deeper along its edge, the thin line on it
  const pale = TONE(0xe4);
  c.fill(S.polygon(white), (px) => put(px, mix3(mix3(pale, WHITE, smooth(0, 0.6, -px.d)), EDGE_RIM, step(RIM + px.d, k))));
};

// ---- the wrench (repair) ---------------------------------------------------------------------------------------------
// An open-ended wrench lying at 45 degrees, its jaw at the upper right. The game's (the same drawing as isk_repair's,
// one pixel higher) is a plate with bevelled edges: a line of white all round its outline; inside, pale blue
// (6f8cff to 869fff) on top and on the edges that face up or left, deep blue (1e4af5 to 3f66ff) in a band 2.8 wide
// along the edges that face down or right, and a second line of white where that band meets the top.
// Read off the pixels, along the wrench's line (x + y = 31.4; u along it towards the jaw, v across it, both from
// where it crosses x = y) and made the same either side of it:
//   the handle   3.3 to each side (its three lines of white lie on x + y = 27, 31 and 35), its end at u = -14.6
//   the head     7.0 to each side (x + y = 22 and 41.7); its two back edges upright and level in the game (x = 15,
//                y = 17): at 45 degrees to the line, from the handle out to the sides; its two front edges level
//                and upright as well (y = 3, x = 29), they would meet on the line at u = 18.4
//   the jaw      a notch between them: 2.8 to each side at the front, closing to a point on the line at u = 10.6
//                (the game's: 45 degrees wide, its point at (23.5, 8.5))
const WRENCH = { axis: 31.4, end: -14.6, hw: 3.3, head: 7.0, back: -1.4, front: 18.4, mouth: 2.8, point: 10.6, bevel: 2.8, top: 0x8c, deep: 0x56, ridge: 0.24 };
const wrenchPts = (q = WRENCH) => {
  const uv = [[q.end, -q.hw], [q.hw + q.back, -q.hw], [q.head + q.back, -q.head], [q.front - q.head, -q.head], [q.front - q.mouth, -q.mouth], [q.point, 0],
    [q.front - q.mouth, q.mouth], [q.front - q.head, q.head], [q.head + q.back, q.head], [q.hw + q.back, q.hw], [q.end, q.hw]];
  return uv.map(([u, v]) => [(u + v) * SQRT1_2 + q.axis / 2, (v - u) * SQRT1_2 + q.axis / 2]);
};
// A bevelled plate: `bevel` wide along its edge the surface slopes down to the edge. Lit from the upper left: where
// the nearest edge faces down or right the bevel is deep, elsewhere it is as light as the top.
const AWAY = [SQRT1_2, SQRT1_2];            // the direction away from the light, on screen
const bevelled = (c, pts, o) => {
  const shape = S.polygon(pts), k = c.k;
  c.fill(shape, (px) => {
    const depth = -px.d, away = smooth(0.15, 0.45, px.gx * AWAY[0] + px.gy * AWAY[1]);      // 1: this edge faces away from the light
    const onBevel = 1 - step(depth - o.bevel, k);
    let v = TONE(o.top + (o.deep - o.top) * away * onBevel);
    v = mix3(v, WHITE, away * lineAt(abs(depth - o.bevel), o.ridge, 0.2));                 // the line where a deep bevel meets the top
    v = mix3(v, WHITE, lineAt(depth));                                                     // the line along the outline
    put(px, mix3(v, EDGE_RIM, step(RIM - depth, k)));
  });
  return shape;
};
const wrench = (c, q = WRENCH) => bevelled(c, wrenchPts(q), q);

module.exports = { LINE, lineAt, toSeg, EDGE_RIM, face, arrowRight, BOOST, boostArrows, WRENCH, wrenchPts, AWAY, bevelled, wrench };
