'use strict';
// Constructed drawings of ten of the shaded objects: the wrench, the light side's emblem, the stance, the hand under
// the arc, the two fists, the door, the container, the hand that resists energy (twice).
// Nothing here is traced. Each outline is built from dimensions measured on the GAME's icon (tools/vmap.py,
// tools/objects_c_hex.py for its pixels, tools/objects_c_edge.py for its edges below the pixel), out of straight lines
// and circular arcs; black borders are the same outlines moved out by one unit and are laid first; the shading is
// formulas (parts/symbol_shaded_objects_c.js). ChatGPT's redraw was used only to recognise what a thing is.
// Units: the game icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const O = require('../parts/symbol_shaded_objects_c');

const { INK, BORDER, smooth, bell, curve, shade } = O;
const RAD = Math.PI / 180;

// ---- the wrench (repair) ---------------------------------------------------------------------------------------------
// An open-ended wrench lying from the lower left to the upper right, its jaws opening to the upper right.
// Measured on the game's icon:
//   head     a square plate x 15.03 .. 28.97, y 4.03 .. 17.97 (here 15 .. 29, 4 .. 18), its middle (22, 11); two of its
//            corners are cut: the upper left from (15, 7.3) to (20, 4), the lower right from (29, 13.5) to (24.25, 18)
//            (that edge runs parallel to the handle)
//   jaws     the upper right corner is open: the upper jaw ends at x 23.9, the lower jaw's top is y 7.25, and from
//            that corner a slit 1.4 wide (two black pixels on the diagonal) runs back along the handle's direction to
//            (22.45, 9.9). The outer corners of both jaws are cut by 0.8 (one pixel in the game).
//   handle   its edges run at 42.5 degrees (the upper left one 42.51, the black round it 42.4 on both sides) and its
//            middle line passes through the middle of the head; 6.4 wide (6.43), its end cut square 23.2 from the
//            head's middle, corners cut like the jaws'
// The game's lighting: a white line along the outer edge; the sides turned to the light (up, left) pale, those turned
// away deep blue (two pixels inside the lower edge, one inside the right one, the lower half of the handle, and the
// wall of the slit that faces down); a line of light along the handle's middle (white, 0xf0, two thirds up it) that
// dies away into the head, and a line of light above the head's deep lower edge. All of that is one model here: a
// plate with a bevel 3.2 wide all round (parts: plate), so that on the handle the two bevels meet in a ridge.
// Changed from the game: the black border is one unit everywhere (along the handle the game's is two diagonal pixels).
const WRENCH = {
  head: [15, 4, 29, 18], centre: [22, 11], deg: -42.5, len: 23.2, half: 3.2, cut: 0.8,
  cutA: [3.3, 5.0], cutB: [4.5, 4.75], jaw: [23.9, 7.25], slit: { at: [24.0, 8.5], half: 0.7, back: 1.4 }, light: 3.4,
};
const wrench = (c, q = WRENCH) => {
  const u = [Math.cos(q.deg * RAD), Math.sin(q.deg * RAD)], n = [-u[1], u[0]];
  const [x0, y0, x1, y1] = q.head, [jx, jy] = q.jaw, h = q.half, ce = q.cut;
  const E = [q.centre[0] - q.len * u[0], q.centre[1] - q.len * u[1]];
  const pt = (t, s) => [E[0] + u[0] * t + n[0] * s, E[1] + u[1] * t + n[1] * s];
  // where the handle's upper edge meets the head's left side, and its lower edge the head's lower side
  const A = pt((x0 - E[0] + n[0] * h) / u[0], -h), B = pt((y1 - E[1] - n[1] * h) / u[1], h);
  // the slit: two walls parallel to the handle, a round end
  const sl = q.slit, M = sl.at, sh = sl.half, Cs = [M[0] - sl.back * u[0], M[1] - sl.back * u[1]];
  const t1 = (jx - (M[0] - sh * n[0])) / u[0], t2 = (jy - (M[1] + sh * n[1])) / u[1];
  const w1 = [jx, M[1] - sh * n[1] + t1 * u[1]], w2 = [M[0] + sh * n[0] + t2 * u[0], jy];
  const an = Math.atan2(n[1], n[0]) / RAD;
  const slit = [w1, ...G.arcPts(Cs[0], Cs[1], sh, an + 180, an), w2];
  const outline = (jaw) => [pt(0, -h + ce), pt(ce, -h), A, [x0, y0 + q.cutA[0]], [x0 + q.cutA[1], y0], [jx - ce, y0], [jx, y0 + ce], ...jaw,
    [x1 - ce, jy], [x1, jy + ce], [x1, y1 - q.cutB[0]], [x1 - q.cutB[1], y1], B, pt(ce, h), pt(0, h - ce)];
  // the black: the outline without the slit moved out by one unit (the slit lies inside it and stays black)
  c.fill(S.polygon(G.offsetPts(outline([[jx, jy]]), BORDER)), P.flat(INK));
  // the line of light: along the handle's ridge from 2.2 inside its end, then level along the head 3.4 above its
  // lower edge (where the flat top meets the shaded bevel), ending 2.2 short of the cut corner
  const yl = y1 - q.light, tl = (yl - E[1]) / u[1];
  const light = O.lightLine(O.roundPath([pt(2.2, 0), pt(tl, 0), [x1 - q.cutB[1] - 0.2, yl]], 3.0), 0.42, 2.4);
  O.plate(c, S.polygon(outline(slit)), { extra: (px, g) => g + (0xf8 - g) * light(px.x, px.y) });
};

// ---- the door (open a door) --------------------------------------------------------------------------------------------
// An arrow flying to the right through a door frame, whose door stands open towards the viewer. All of it is straight
// lines, and the game draws it on the pixel grid:
//   two bars   x 2..5 and 6..9, y 13..21: the arrow's trail. A white line one wide round a blue middle (0x97).
//   the arrow  a triangle with its base on x 10 (y 8.5 .. 24.5) and its point at (18, 16.5), sides at 45 degrees;
//              a white line round it, inside blue that deepens from 0xac at the base to 0x7f. It lies in FRONT of
//              the frame's post and its point touches the door.
//   the frame  seen at a slant: a post x 14..17 from y 2 down to 24.1 (24.8 at its right), and from its top a lintel
//              of the same width (3, measured upright) that falls to the right by 4 in 17 (measured: one pixel in
//              four) to the hinge at (31, 6). White along both edges, blue between: 0xc8 at the corner, deepening
//              to 0x7f down the post and to 0x9b along the lintel.
//   the door   a slanted panel x 18..31: its free edge from (18, 9) to (18, 31), its hinged edge from (31, 6) to
//              (31, 28) (it rises to the right by 3 in 13). A white line one wide round it; inside that, along the
//              free edge, a blue line (0x69, the door's thickness) x 19..20 and a pale one x 20..21; the face falls
//              evenly from 0xec at the upper left to 0x67 at the lower right (a plane fitted to the game's pixels:
//              389.8 - 4.15 x - 6.2 y).
// Changed from the game: everything stands half a unit further left and up, so that the black line at the right
// and below lies whole inside the frame (in the game it is the frame's last column and row). The white line round
// the door is whole (the game's fades out half way up the hinged edge).
const DOOR = {
  move: [-0.5, -0.5],
  bars: [[2, 13, 5, 21], [6, 13, 9, 21]], arrow: [[10, 8.5], [18, 16.5], [10, 24.5]],
  post: [14, 17], top: 2, fall: 4 / 17, thick: 3, foot: 24.1, hinge: [31, 6], leaf: [18, 9, 22], line: 1.0,
};
const door = (c, q = DOOR) => {
  const [mx, my] = q.move, k = c.k, mv = (pts) => pts.map(([x, y]) => [x + mx, y + my]);
  const [p0, p1] = q.post, [hx, hy] = q.hinge, [lx, ly, lh] = q.leaf, m = q.fall;
  const bars = q.bars.map(([x0, y0, x1, y1]) => mv([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]));
  const arrow = mv(q.arrow);
  const lintel = (x) => q.top + m * (x - p0);                       // the frame's upper edge
  const frame = mv([[p0, q.top], [hx, lintel(hx)], [hx, lintel(hx) + q.thick], [p1, lintel(p1) + q.thick], [p1, q.foot + m * (p1 - p0)], [p0, q.foot]]);
  const leaf = mv([[lx, ly], [hx, hy], [hx, hy + lh], [lx, ly + lh]]);
  F.borders(c, [...bars, arrow, frame, leaf], BORDER);
  // a body that is white along its edge for the given width (the outline moved in, its corners sharp), with whatever
  // level the inside has
  const lined = (pts, w, inside) => {
    c.fill(S.polygon(pts), (px) => shade(px, 0xff, k));
    c.fill(S.polygon(G.offsetPts(pts, -w)), (px) => shade(px, inside(px.x - mx, px.y - my), k, 0));
  };
  // the frame: the blue between its white lines deepens away from its upper left corner
  // (read off the game: down the post 0xc9 at y 6.5, 0x9a at 12.5, 0x7f from 13.5; along the lintel 0x9b at x 22.5)
  lined(frame, q.line, (x, y) => (x > p1 ? Math.max(0x9b, 0xc8 - 6.4 * Math.max(x - 16.5, 0)) : Math.max(0x7f, 0xc8 - 7.2 * Math.max(y - 5.5, 0))));
  // the door
  lined(leaf, q.line, (x, y) => {
    const face = 389.8 - 4.15 * x - 6.2 * y;
    const blue = O.step(lx + 2 - x, k), pale = O.step(lx + 3 - x, k);
    return blue * 0x69 + (1 - blue) * (pale * Math.min(0xf4, face + 45) + (1 - pale) * face);
  });
  lined(arrow, 0.9, (x) => Math.max(0xac - 15 * (x - 11.5), 0x7f));
  for (const b of bars) lined(b, q.line, () => 0x97);
};

// ---- the container (open a container) ---------------------------------------------------------------------------------
// A ball cut in two: the lower part stands as a bowl, the upper part (the lid) is swung up and to the right. Beside
// it, at the upper left, a plus sign. Measured on the game's icon:
//   the ball   radius 9.5, cut 0.45 above its middle. The bowl: round (15.5, 20.5), its cut edge level at y 20.05
//              (measured 20.03; it is 19 wide and reaches down to y 30). The lid: round (18.5, 14.0) (it reaches
//              x 28.03 and y 4.47), its cut edge at 41.5 degrees (41.52) and 0.41 beyond the centre.
//   the plus   three crosses one inside the other about (8.5, 13.5), each one unit larger all round: a white plus
//              with arms 1 wide and 5 long, a dark blue cross behind it (deep blue at the upper left, 0x25, black at
//              the lower right), a white cross behind that (arms 5 wide, 9 long), and the black round it.
// The game's lighting. Bowl: a light in the middle of its cut edge (white, 0xf8) that falls off as a bell, 6.3 wide
// to each side and 3.6 down (its levels down the middle: f8 d6 b2 86 65 51 46 3f), to deep blue 0x3e below. Lid:
// white across its middle from the cut edge to its top, falling to 0x80 towards both ends of the cut edge (f1 at 3
// from the middle, b4 at 4.7, 8a at 6). Both carry a pale line along the round edge.
const BALL = { r: 9.5, cut: 0.45, bowl: [15.5, 20.5], lid: [18.5, 14.0], deg: 41.5, plus: [8.5, 13.5] };
const cross = (cx, cy, a, b) => [[cx - a, cy - b], [cx + a, cy - b], [cx + a, cy - a], [cx + b, cy - a], [cx + b, cy + a], [cx + a, cy + a],
  [cx + a, cy + b], [cx - a, cy + b], [cx - a, cy + a], [cx - b, cy + a], [cx - b, cy - a], [cx - a, cy - a]];
const container = (c, q = BALL) => {
  const k = c.k, r = q.r, [bx, by] = q.bowl, [lx, ly] = q.lid, [px0, py0] = q.plus;
  const u = [Math.cos(q.deg * RAD), Math.sin(q.deg * RAD)], n = [u[1], -u[0]];             // along the lid's cut edge; into the lid
  const mid = [lx + q.cut * n[0], ly + q.cut * n[1]];                                       // the middle of the lid's cut edge
  const bowl = S.intersect(S.circle(bx, by, r), S.halfPlane(bx, by - q.cut, 0, -1));
  const lid = S.intersect(S.circle(lx, ly, r), S.halfPlane(mid[0], mid[1], -n[0], -n[1]));
  c.fill(S.polygon(cross(px0, py0, 3.5, 5.5)), P.flat(INK));
  c.fill(lid, P.flat(INK), BORDER);
  c.fill(bowl, P.flat(INK), BORDER);
  // the pale line along the round edge: `round` is the depth inside the ball's own circle
  const rim = (g, round) => g + (0xec - g) * (1 - smooth(0.5, 0.95, round));
  const flat = (v, a, w) => (Math.abs(v) < a ? 1 : bell(Math.abs(v) - a, w));
  c.fill(lid, (px) => {
    const t = (px.x - mid[0]) * u[0] + (px.y - mid[1]) * u[1];
    shade(px, rim(0x80 + (0xff - 0x80) * flat(t, 2, 3.3), r - Math.hypot(px.x - lx, px.y - ly)), k);
  });
  c.fill(bowl, (px) => {
    const g = 0x3e + 190 * bell(px.x - bx, 6.3) * bell(px.y - (by - q.cut), 3.6);
    shade(px, rim(g, r - Math.hypot(px.x - bx, px.y - by)), k);
  });
  c.fill(S.polygon(cross(px0, py0, 2.5, 4.5)), (px) => shade(px, 0xff, k));
  c.fill(S.polygon(cross(px0, py0, 1.5, 3.5)), (px) => shade(px, 0x06 + 0x1f * smooth(1.5, -1.5, px.x - px0 + px.y - py0), k, 0));
  c.fill(S.polygon(cross(px0, py0, 0.5, 2.5)), (px) => shade(px, 0xff, k, 0));
};

// ---- the emblem of the light side ---------------------------------------------------------------------------------------
// Two wings round an open middle, a disc below: one pale blue (0xccccfc) with no black round it; in the game the pixels
// along its edge are a deeper blue (0x9cb4fc, 0x849cfc), which is drawn here as the colour deepening to the edge.
// Measured on the game's icon (its axis stands at x 16.47; the left wing, the right one is its mirror image):
//   outer edge   a circle of radius 13.76 about a point 1.38 left of the axis (y 15.28), from the shoulder at y 9.05
//                down to y 20.3; from there the edge runs on, a little straighter, to the tail's point at (5.7, 27.6)
//   inner edge   a circle of radius 8.67 about a point 2.02 RIGHT of the axis (y 15.4): the wing is 8.4 thick at its
//                middle and 5.3 where it ends at the gap
//   upper edge   straight, at 41.4 degrees, from the notch at (4.55, 10.8) up to y 2; the wing's top is cut level there
//   gap          between the wings, 2.5 wide (x 15.22 .. 17.72)
//   shoulder     a point on the outer circle at y 9.05, and a notch behind it
//   lower end    two points: a tooth at (8.7, 24.4) and the long tail; the notch between them ends at (5.75, 20.7)
//   disc         radius 4.09 about a point on the axis, y 25.96
// Changed from the game: the frame cut the right wing flat at x 31 (the left one reaches x 1.33); here the emblem
// stands on the middle of the frame (axis 16.0) and both wings are whole.
const EMBLEM = {
  axis: 16.0, outer: [-1.38, 15.28, 13.76], inner: [2.02, 15.4, 8.67], gap: 1.25, top: 2.0, upper: [-2.31, 2.0],
  horn: 9.05, notch: [-11.92, 10.8], leave: 20.3, tail: [-10.77, 27.6], split: [-10.72, 20.7], tooth: [-7.77, 24.4], toothEnd: 21.2,
  disc: [25.96, 4.09], colour: { rim: '#6f88f4', edge: '#93aafc', body: '#ccccfc' },
};
const emblem = (c, q = EMBLEM) => {
  const ax = q.axis, at = (p) => [ax + p[0], p[1]], deg = (cx, cy, p) => Math.atan2(p[1] - cy, p[0] - cx) / RAD;
  const [ox, oy, or] = [ax + q.outer[0], q.outer[1], q.outer[2]], [ix, iy, ir] = [ax + q.inner[0], q.inner[1], q.inner[2]];
  const onOuter = (y) => [ox - Math.sqrt(or * or - (y - oy) * (y - oy)), y], onInner = (y, x) => (x === undefined ? [ix - Math.sqrt(ir * ir - (y - iy) * (y - iy)), y] : [x, iy - Math.sqrt(ir * ir - (x - ix) * (x - ix))]);
  const gapTop = [ax - q.gap, q.top], gapEnd = onInner(0, ax - q.gap), toothEnd = onInner(q.toothEnd);
  const leave = onOuter(q.leave), horn = onOuter(q.horn), tail = at(q.tail);
  // the tail's outer edge: the arc that leaves the outer circle in its own direction and ends in the tail's point
  const e = [(ox - leave[0]) / or, (oy - leave[1]) / or], d = [tail[0] - leave[0], tail[1] - leave[1]];
  const rho = (d[0] * d[0] + d[1] * d[1]) / (2 * (d[0] * e[0] + d[1] * e[1])), tc = [leave[0] + rho * e[0], leave[1] + rho * e[1]];
  const arc = (cx, cy, r, p0, p1) => { let a0 = deg(cx, cy, p0), a1 = deg(cx, cy, p1); if (a1 - a0 > 180) a1 -= 360; if (a0 - a1 > 180) a1 += 360; return G.arcPts(cx, cy, r, a0, a1); };
  const wing = [gapTop, ...arc(ix, iy, ir, gapEnd, toothEnd), at(q.tooth), at(q.split), ...arc(tc[0], tc[1], rho, tail, leave), ...arc(ox, oy, or, leave, horn).slice(1),
    at(q.notch), at(q.upper)];
  const all = S.union(S.polygon(wing), S.polygon(F.mirrored(wing, ax)), S.circle(ax, q.disc[0], q.disc[1]));
  c.fill(all, F.deepening(c.k, q.colour, { depth: 0.75, rim: 0.12 }));
};

// ---- the stance ----------------------------------------------------------------------------------------------------------
// What the game shows: a round-nosed bar lying in a faint frame, its nose against a bow (a crescent) that closes the
// frame at the right. No black round any of it. Measured on the game's icon (it is the same above and below y 16):
//   the bow     between two circles: the outer one round (16.6, 16) with radius 11.5, the inner one round (12.16, 16)
//               with radius 11.69. It is 4.25 thick in the middle and comes to points at (14.9, 4.6) and (14.9, 27.4)
//               (in the game the points fade out). A white line runs along it 1.6 inside its outer edge (the game's
//               column x 26, with blue 0xab outside it and 0x98 .. 0xb0 inside).
//   the bar     x 7 to 22.25, y 13 to 19, its right end round. Its light lies in slanted bands (they lean to the
//               right by a third of a unit per unit down): deep blue at its left end (0x34), a pale band at x 11.5
//               (0xae), a deep one at 14.6 .. 15.4 (0x42), a pale one at 17 (0xbe), a deep line at 20.4 and a white nose.
//   the frame   lines one unit wide on x 4.5, y 10.5 and y 21.5, see-through: 0.29 solid at the left, rising evenly
//               to 0.82 where they meet the bow. The left line is white, the upper one pale blue (0xb4), the lower
//               one deep blue (0x24) with a pale left end.
// Left out: the dark specks along the game's upper line and the second, upright streak of light in the upper half of
// the bow (the game's picture is a small rendering of something three-dimensional; only what makes the three things
// is drawn).
const STANCE = {
  outer: [16.6, 16, 11.5], inner: [12.16, 16, 11.69], light: 1.6, reach: 58,
  bar: [7, 22.25, 16, 3], slant: 1 / 3, frame: [4.5, 10.5, 21.5, 0.5], solid: [[6, 0.29], [21.5, 0.82]],
};
const stance = (c, q = STANCE) => {
  const k = c.k, [ox, oy, or] = q.outer, [ix, iy, ir] = q.inner, [b0, b1, by, bh] = q.bar, [fx, fy0, fy1, fh] = q.frame;
  // the frame: one line with square corners; how solid it is depends on x alone
  const solid = curve(q.solid), line = S.polygon(G.strokePts([[ox + or - 2, fy0], [fx, fy0], [fx, fy1], [ox + or - 2, fy1]], fh));
  c.fill(line, (px) => {
    const lower = O.step(px.y - 16, k), left = 1 - smooth(fx + fh, fx + fh + 2.4, px.x);
    const g = lower ? 0x24 + (0xff - 0x24) * left : px.x < fx + fh ? 0xff : 0xb4;
    O.put(px, O.TONE(g), solid(px.x));
  });
  // the bow
  const bow = S.subtract(S.circle(ox, oy, or), S.circle(ix, iy, ir));
  const light = O.lightLine(G.arcPts(ox, oy, or - q.light, -q.reach, q.reach), 0.4, 2.4);
  c.fill(bow, (px) => {
    const g = 0x74 + (0xa4 - 0x74) * smooth(0, 0.6, -px.d);
    shade(px, g + (0xff - g) * light(px.x, px.y), k);
  });
  // the bar
  const along = O.flow([[7.0, 0x34], [8.6, 0x38], [10.0, 0x7e], [11.5, 0xae], [12.5, 0xa6], [13.5, 0x7b], [14.6, 0x42], [15.4, 0x4a], [16.3, 0xa4], [17.1, 0xbe],
    [18.0, 0xa6], [19.3, 0xa8], [20.4, 0x54], [21.0, 0xc4], [22.0, 0xfa]]);
  const bar = S.intersect(S.capsule(b0 - 8, by, b1 - bh, by, 2 * bh), S.halfPlane(b0, by, -1, 0));
  c.fill(bar, (px) => { const g = along(px.x - q.slant * (px.y - by)); shade(px, g - 0x18 * (1 - smooth(0, 0.5, -px.d)), k); });
};

module.exports = {
  isk_repair(c) { wrench(c); },
  i_gstance(c) { stance(c); },
  i_goodfull(c) { emblem(c); },
  i_openplace(c) { container(c); },
  i_opendoor(c) { door(c); },
};
