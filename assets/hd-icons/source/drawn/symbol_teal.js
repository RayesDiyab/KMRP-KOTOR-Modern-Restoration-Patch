'use strict';
// The upgrade items: a black silhouette with a line of light round it, on the teal plate (parts/symbol_teal.js).
// The GAME's icons give every design. Each silhouette is built from straight lines and circular arcs at the game's
// own dimensions, read off its 64 pixel icon (one pixel is half a unit):
//   - where the game's line of light is crisp (shirt, plate of durasteel, rifle) off the pixels themselves
//     (tools/teal_sil.py): the outline given is the silhouette's OUTER edge, the outer side of that one-pixel line;
//   - where it is blurred over two pixels (the turned and curved silhouettes) off the crest of its light, found to
//     a fraction of a pixel (tools/teal_ridge.py): the outline given is the MIDDLE of the line, which then lies half
//     its width to either side ({ middle: ... }, or T.outerOf for outlines that have only sharp corners).
// The line of light is 0.5 wide (one game pixel) and the black lies inside it. ChatGPT's redraws were used to see
// what each thing is, not for shape: they fatten the line, add a glow and reshape the silhouettes.
// What is changed from the game is said at each icon. Units: frame 32 x 32, y down. The plate's axis is x = 15.75.
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const T = require('../parts/symbol_teal');

const AX = T.CX;
// pieces of an outline joined into one (a point that all but repeats the one before it is left out)
const joined = (...parts) => {
  const out = [];
  for (const p of parts.flat()) { const q = out[out.length - 1]; if (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > 0.02) out.push(p); }
  if (out.length > 1 && Math.hypot(out[0][0] - out[out.length - 1][0], out[0][1] - out[out.length - 1][1]) < 0.02) out.pop();
  return out;
};

module.exports = {
  // A shirt. In the game (pixels 13 to 50 of the plate's 10 to 52: half a pixel right of the plate's middle, as
  // near the middle as 38 pixels fit on 43; on the axis here): top at y = 7.5, hem at 24; a collar 1 deep, 4.5 wide
  // at the top and 2.5 at its floor; shoulders out to 7.25 from the axis; sleeves 9.5 from the axis from y = 9.75 to
  // 12.75, their upper corners cut at 45 degrees; the sleeves' undersides run in to the body (13 wide) at y = 15.
  // Changed from the game: the underside is one straight line there (the game's pixels step at 45 degrees and end
  // in a ledge 1.5 pixels long at the armpit).
  i_armorrein(c) {
    T.icon(c, { kind: 'arch', tex: 'shirt', bodies: [T.mirrored(AX, [[0, 8.5], [1.25, 8.5], [2.25, 7.5], [7.25, 7.5], [9.5, 9.75], [9.5, 12.75], [6.5, 15], [6.5, 24], [0, 24]])] });
  },

  // A plate of durasteel: a square whose upper and lower edges bow outwards. In the game: sides at pixels 20 and 42
  // (x = 10.0 to 21.5, on the plate's axis), 11.3 high at the sides; the upper edge rises 0.78 in the middle and
  // the lower falls 0.97 (measured on the middle of the line of light). Made equal here: both bow 0.875, as arcs of
  // radius 17.97 about the square's middle height, y = 15.89.
  i_durasteel(c) {
    const cy = 15.89, r = 17.97, up = 27.31, span = (Math.asin(5.75 / r) * 180) / Math.PI;
    T.icon(c, { kind: 'tab', tex: 'light', bodies: [[...G.arcPts(AX, up, r, -90 - span, -90 + span), ...G.arcPts(AX, 2 * cy - up, r, 90 - span, 90 + span)]] });
  },

  // A rifle seen from the side, every edge horizontal or vertical, exactly the game's pixels: stock 6.5 x 5 at the
  // left (y 13 to 18); barrel 4 thick (13.5 to 17.5) with a neck 3 thick from x = 19 to 21.5; muzzle block from 21.5
  // to 26; under the barrel a grip 2.5 wide down to 20.5 and, in front of it, a trigger guard 2.5 x 1.5.
  i_scope(c) {
    T.icon(c, { kind: 'arch', tex: 'dark', bodies: [[[5.5, 13], [12, 13], [12, 13.5], [19, 13.5], [19, 14], [21.5, 14], [21.5, 13.5], [26, 13.5], [26, 17.5], [21.5, 17.5], [21.5, 17], [19, 17],
      [19, 18.5], [16.5, 18.5], [16.5, 20.5], [14, 20.5], [14, 17.5], [12, 17.5], [12, 18], [5.5, 18]]] });
  },

  // A hair trigger: the trigger guard as a black frame, and in its opening the trigger, a curved tongue hanging from
  // the top and coming to a small round end. Middles of the game's lines:
  //  - the frame: top at y = 10.3, right side at x = 24.7 (the corner between them square), lower edge at 22.25, left
  //    side at 6.9; three corners cut: the upper left from (10.1, 10.3) to (6.9, 14.6), the lower left from (6.9, 19.5)
  //    to (9.5, 22.25), the lower right at 45 degrees from (24.7, 18.8) to (21.25, 22.25). The cuts' corners are soft
  //    in the game: rounded here by 1.0 to 1.5.
  //  - the opening: a half circle of radius 3.84 about (12.59, 16.59) at the left, level edges at y = 12.75 and 20.43,
  //    the right side at x = 21.7 with an arc of 5.0 into the lower edge.
  //  - the trigger: its left edge upright at x = 16.9 down to y = 14.6, then an arc of radius 3.68 curling to the
  //    left; its right edge an arc of radius 6.5 about (13.47, 12.69); the two meet in a round end (radius 0.48)
  //    near (14.6, 18.5); right of the trigger the opening closes in an arch of radius 0.95 about (20.75, 14.25).
  // In the opening every arc runs into its neighbours without a corner, except at the trigger's root (rounded by 0.9).
  i_hair(c) {
    const frame = S.roundedPoints([[10.1, 10.3, 0.3], [24.7, 10.3], [24.7, 18.8, 1.5], [21.25, 22.25, 1.5], [9.5, 22.25, 1.5], [6.9, 19.5, 1.5], [6.9, 14.6, 1.0]], 0, 0.06);
    const round = [12.59, 16.59], a = [13.22, 14.6], ra = 3.68, b = [13.47, 12.69], arch = [20.75, 14.25], rArch = 0.95, rb = Math.hypot(arch[0] - b[0], arch[1] - b[1]) - rArch, rt = 0.48;
    const tip = T.meet(a, ra + rt, b, rb - rt)[1];                       // the round end's middle: it touches the left arc from outside and the right arc from inside
    const loop = joined([[round[0], 12.75]], G.arcPts(16.0, 13.65, 0.9, -90, 0), G.arcPts(a[0], a[1], ra, 0, T.degOf(a, tip)),
      T.arcBetween(tip, rt, a, [2 * tip[0] - b[0], 2 * tip[1] - b[1]], -1), G.arcPts(b[0], b[1], rb, T.degOf(b, tip), T.degOf(b, arch)),
      G.arcPts(arch[0], arch[1], rArch, T.degOf(arch, b) + 360, 360), G.arcPts(16.7, 15.43, 5.0, 0, 90), G.arcPts(round[0], round[1], 3.84, 90, 270));
    T.icon(c, { kind: 'arch', tex: 'dark', bodies: [{ middle: frame }], islands: [{ middle: loop }] });
  },

  // A power crystal: a long six-sided stone with a point at each end, in a round glow. The middle of the game's line:
  // sides 2.54 from the stone's own axis (which lies a third of a unit right of the plate's; on the plate's axis
  // here), points at y = 7.84 and 22.97, each 3.0 high (their sides at 49.7 degrees). The line is thicker than the
  // other silhouettes' (a pixel and a half: 0.75). Round it the game leaves a dark ring one pixel wide, then the
  // glow: 21,230,231, at full strength out to 5 from the stone's middle and gone at 10.8 (read along the row through
  // the middle, a column and a diagonal: it is round).
  i_powerc(c) {
    const half = 2.54, top = 7.84, bottom = 22.97, tall = 3.0, width = 0.75;
    T.icon(c, { kind: 'tab', tex: 'light', width, bodies: [T.outerOf(T.mirrored(AX, [[0, top], [half, top + tall], [half, bottom - tall], [0, bottom]]), width)],
      glow: { at: [AX, (top + bottom) / 2], full: 5.0, end: 10.8, colour: [21, 230, 231], gapWidth: 0.5 } });
  },

  // A vibration cell: a six-sided body between two eaves. The middle of the game's line, measured from the cell's
  // middle (15.75, 16): walls 6.93 to either side from 1.82 above to 3.1 below; upper eaves out to 8.78 at 4.6 above,
  // their ends leaning in to 8.27 at 2.7 above and their undersides running in to the walls; lower eaves thinner,
  // out to 8.3 between 4.15 and 4.65 below. The body is the same left and right, but its two points are not: the
  // upper one stands 1.25 right of the middle (8.72 above), the lower one 1.25 left of it (8.75 below): the cell is
  // seen a little from the side.
  i_vcell(c) {
    const cy = 16, right = [[8.78, -4.6], [8.27, -2.7], [6.93, -1.82], [6.93, 3.1], [8.3, 4.15], [8.3, 4.65]];
    const all = [[1.25, -8.72], ...right, [-1.25, 8.75], ...right.map(([x, y]) => [-x, y]).reverse()];
    T.icon(c, { kind: 'tab', tex: 'light', bodies: [T.outerOf(all.map(([x, y]) => [AX + x, cy + y]))] });
  },

  // An energy cell: a casing with a round terminal on top, a round knob at its upper left, a tooth at its upper
  // right and two feet. The middle of the game's line: the terminal a dome of radius 1.57 about (15.5, 10.55), its
  // crown at y = 8.98; from its left side (at y = 10.14) a shoulder slopes down to the knob, a circle of radius 1.55
  // about (7.6, 12.9) that runs into the shoulder and into the left wall (x = 7.72) along lines at 45 degrees; the
  // dome's right side runs down into a valley at (20.2, 12.75); then a tooth with a level top 0.7 wide at
  // y = 11.12 and behind it a rounded shoulder (radius 2.25) into the right wall (x = 25.2); underneath two feet,
  // down to y = 21.47 and 22.3, with a level stretch at 20.27 between them.
  // The game's outline is soft here (blurred over two pixels all round): the corners underneath, in the valley and
  // on the tooth are rounded by 0.25 to 0.6.
  i_imp_eng(c) {
    const knob = [7.6, 12.9], body = S.roundedPoints([[9.35, 12.35, 0.3], ...G.arcPts(15.5, 10.55, 1.57, 195, 370), [17.78, 11.59, 0.6], [20.2, 12.75, 0.5],
      [22.22, 11.12, 0.25], [22.95, 11.12, 0.25], ...G.arcPts(22.95, 14.3, 2.25, -90, 0), [25.2, 20.41, 0.4], [20.84, 22.34, 0.6], [19.97, 22.25, 0.6], [16.03, 20.28, 0.6], [14.22, 20.25, 0.6],
      [12.16, 21.47, 0.5], [11.03, 21.47, 0.5], [7.72, 18.91, 0.6], [7.72, 15.22], ...G.arcPts(knob[0], knob[1], 1.55, 135, 315)], 0, 0.06);
    T.icon(c, { kind: 'tab', tex: 'light', bodies: [{ middle: body }] });
  },

  // An open-ended wrench: two prongs at the upper left, a head whose faces are level and upright, and the handle
  // running down to the right at 45 degrees. The middle of the game's line, along the wrench's line (u) and across
  // it (w): prongs 2.4 wide, their tips at u = 13.2, their inner sides 2.0 and their outer sides 4.4 from the line;
  // the jaw between them 4.0 wide with a round floor at u = 17.0; the head's faces: its upper face level at y = 7.9
  // (from x = 15.1 to 17.8), a corner cut at 45 degrees, its right face upright at x = 19.3 down to y = 11.8; then
  // the head is cut across to the handle, 2.7 wide, which ends round at u = 32.75.
  // Changed from the game: the two halves are mirror images about the wrench's line. In the game the prongs lie
  // about x - y = 0, the head about 0.95 and the handle about 1.9 (and the handle grows from 2.35 wide to 3.7 at
  // its end); here all lie about x - y = 0.99 and the lower half is the upper half's mirror image.
  i_beam(c) {
    const upper = [[13.2, -2.0, 0.5], [13.2, -4.4, 0.6], [16.27, -4.4, 0.5], [18.2, -6.33, 0.8], [20.27, -6.33, 0.8], [22.0, -4.6, 0.6], [23.0, -1.35, 0.6], [32.75, -1.35, 1.35]];
    const uw = S.roundedPoints([...G.arcPts(15, 0, 2, 90, -90), ...upper, ...upper.map(([u, w, r]) => [u, -w, r]).reverse()], 0, 0.06);
    T.icon(c, { kind: 'arch', tex: 'dark', bodies: [{ middle: T.turned([0.495, -0.495], 45, uw) }] });
  },

  // A blaster pistol pointing up and to the right: a thick body, the grip standing off below at the lower left, a
  // round trigger guard in front of the grip. The middle of the game's line: the muzzle end is cut upright at
  // x = 14.78 and level at y = 5.1; from (18.6, 5.1) the outline falls through (20.9, 6.05) to (23.03, 8.2) and
  // runs upright to 10.4; the underside runs at 45 degrees along x + y = 33.44. The back (upper left) is stepped:
  // from the muzzle's upright edge it runs at 56.6 degrees to (12.45, 11.1), upright to 12.35, across a ledge to
  // (10.9, 13.35), at 45 degrees to (8.0, 16.25) and steeply down to the upright end at x = 6.97; the lower edge is
  // level at y = 21.2 with the corner before it cut. The trigger guard: an arc of radius 4.65 about (16.03, 14.08)
  // from the underside round to the grip. The grip: 1.95 wide at 45 degrees (its upper edge y = x + 5.1), round at
  // its end (x + y = 42).
  // Changed from the game: the grip's edges are parallel (there it narrows from 2.1 to 1.7).
  i_energy(c) {
    const body = S.roundedPoints([[14.78, 5.1, 0.7], [18.6, 5.1, 0.6], [20.9, 6.05, 1.2], [23.03, 8.2, 0.6], [23.03, 10.41, 0.3], [19.66, 13.78], [19.6, 14.45, 0.3],
      ...G.arcPts(16.03, 14.08, 4.65, 19.2, 103), [14.66, 19.76], [18.45, 23.55, 0.9], [17.07, 24.93, 0.9], [13.34, 21.2], [9.6, 21.2, 0.4], [6.97, 19.6, 0.3], [6.97, 18.8, 0.4],
      [8.0, 16.25, 1.2], [10.9, 13.35, 0.4], [12.45, 12.35, 0.3], [12.45, 11.1], [14.78, 7.6, 0.6]], 0, 0.06);
    T.icon(c, { kind: 'arch', tex: 'dark', bodies: [{ middle: body }] });
  },
};
