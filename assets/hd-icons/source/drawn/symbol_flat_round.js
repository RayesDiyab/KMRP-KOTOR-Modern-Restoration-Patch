'use strict';
// Constructed drawings of the flat round symbols. Nothing here is traced: every outline is built from measured
// dimensions out of straight lines and circular arcs, borders are the same outlines moved out, and glows and shading
// are formulas. The GAME's icon gives each design: its pixels are read first (tools/vmap.py, tools/flat_round_m.py:
// exact pixels of rows, edges along rows, columns and rays, circles fitted to them; tools/flat_round_glowfit.py: the
// game's glows); the redraw only helps to see what a thing is. Where a drawing departs from the game, its comment
// says how. Units: the vanilla icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const R = require('../parts/symbol_flat_round');
const W = require('../parts/weapons');

// The blue glow of the game's own shield icon (ip_armor), measured with tools/flat_round_glowfit.py: it is the body's
// silhouette blurred by 2.5 units and put through a curve (opacity 0.47 beside the body, 0.35, 0.235, 0.155, 0.09,
// 0.05 at each unit further off a straight side, less off a corner); the fit leaves 0.03 of opacity unexplained,
// against 0.04 for a glow that goes by the distance to the body alone. Its colour goes with its opacity.
const GLOW = { sigma: 2.5, curve: [[0, 0], [0.004, 0.024], [0.027, 0.098], [0.06, 0.165], [0.1, 0.225], [0.14, 0.27], [0.2, 0.34], [0.26, 0.38], [0.33, 0.42], [0.42, 0.47], [0.5, 0.5]] };
const GLOW_BLUE = { ...GLOW,
  stops: [[0, '#000310'], [0.016, '#000410'], [0.044, '#000a2f'], [0.082, '#001259'], [0.129, '#001d8c'], [0.17, '#0026b9'], [0.226, '#0733dd'],
    [0.277, '#1440eb'], [0.329, '#214df8'], [0.371, '#2c56fa'], [0.42, '#3d65fe'], [0.468, '#4b6ffd'], [0.52, '#5377ff']] };
// The glow round the plus (ip_heal) is the same glow (the same blur and curve fit it: 0.40, 0.33, 0.20, 0.125, 0.09,
// 0.06 at each unit from the body) in other colours: a faint glow is the game's blue (40, 84, 255) and it whitens as
// it strengthens (140, 164, 255 at opacity 0.47).
const GLOW_PALE = { ...GLOW, stops: [[0, '#2854ff'], [0.47, '#8ca4ff'], [1, '#ffffff']] };

const whiteHourglass = (c) => {
  R.light(c, { band: { shape: S.polygon(G.offsetPts(R.hourglassPts(), R.HOURGLASS.border), R.FARTHEST), width: 0.5, colour: '#ff0a0a' } });
  R.hourglass(c, 'white');
};
// Three figures: the middle one as it stands alone, the other two 5.25 either side of it, 0.8 of its size with their
// hands on its hands' level, behind it (the game's: 0.77 to 0.82 by their widths and height; the left one stands 5,
// the right one 5.5 from the middle one, which itself stands a quarter of a unit left of the middle of the frame).
const threeFigures = (c) => { for (const [x, k] of [[16 - 5.25, 0.8], [16 + 5.25, 0.8], [16, 1]]) c.fill(R.figure(x, k), P.flat(R.BLACK)); };

module.exports = {
  // A white shield in a black frame, a blue line between them, the blue glow round the whole.
  // The game's pixels, column by column (their partly covered pixels read as fractions): the frame's outline is 16
  // wide (x 8 to 24) from y 8 to 25; its upper edge has a point in the middle (7.56, 8.14, 9.0 on the columns 0.5, 1.5
  // and 2.5 off the axis: a point at 7.3 with flanks sloping 0.6, the slope of the white's), a level stretch either
  // side (9.3, out to 6.15 off the axis) and a square horn at each corner (8.0, the outer 1.85); its lower edge is an
  // arc about (16, 16) of radius 9 that runs into the sides through arcs of radius 4 (half-widths 7.5, 6.9, 6.0, 4.7,
  // 2.2 on the rows from 20). The white's upper edge is a W: a point on the axis (10.35), two rounded valleys (12.0,
  // 3.5 off the axis) and the corners up again (10.9), its flanks sloping 0.6; its lowest point 22.0.
  // The game's frame is two pixels of black at the sides and at the top and bottom, with one pixel of blue between it
  // and the white at the top and bottom only. Changed from the game: the blue line runs all round, and so that the
  // black keeps about the same width everywhere (1.95 to 2.15; 1.0 where the white's corners rise into it, as in the
  // game), the white is 11 wide instead of 12 and ends 0.3 lower.
  ip_armor(c) {
    const outer = R.shieldPts({ top: [[0, 7.3], [3.3, 9.3], [6.15, 9.3], [6.15, 8.0], [8, 8.0]], spring: 19, foot: 25, corner: 4 });
    const white = S.polygon(R.shieldPts({ top: [[0, 10.35], [3.2, 12.27, 1.2], [5.5, 10.9]], spring: 18.8, foot: 22.3, corner: 3 }));
    const frame = S.polygon(outer, R.FARTHEST);
    R.softHalo(c, frame, GLOW_BLUE);
    c.fill(frame, P.flat(R.BLACK));
    c.fill(white, P.byDepth(R.W.line, R.BLUE_LINE), R.W.line);          // the blue line: the white grown by its width
    c.fill(white, P.flat('#ffffff'));
  },

  // A white shield between two crescents (the field of force round it). The game's pixels: the white is 16 wide (x 8
  // to 24); its upper edge has a flat-topped bump in the middle (7.25, 1.4 wide, flanks sloping 0.8), a level stretch
  // either side (9.2, from 3.2 to 5.7 off the axis) and a horn at each corner (7.7, the outer 1.7, its inner wall
  // steep); its lower edge an arc about the axis that runs into the sides through arcs of radius 4.5 (half-widths
  // 7.65, 6.94, 6.33, 4.98, 2.51 on the rows from 20; lowest point 25). Round it one pixel of blue (top and bottom)
  // and one of black. Drawn with the blue line and the thin black all round, both of one width; the white 15.5 wide
  // so that the black's outline stays the game's 18.
  // The crescents: the inner edge of each lies on a circle of radius 13.85 about the middle of the icon (fitted to 20
  // rows, 0.04 off at most); each reaches 55 degrees up and down and comes to a point there (4.3 and 27.6). In the
  // game they are 1.5 thick at the middle, where the frame's edge presses them flat, 1.7 above it and 2.3 below.
  // Changed from the game: whole and inside the frame, 1.85 at the middle, the same above and below. No black (the
  // game has none there); white, a thin blue line on the edge (the game's edge pixels there are blue at half opacity).
  ip_shield(c) {
    const white = S.polygon(R.shieldPts({ top: [[0.7, 7.25], [3.2, 9.2, 0.6], [5.7, 9.2, 0.6], [6.3, 7.7], [7.75, 7.7]], spring: 19, foot: 25, corner: 4.5 }));
    const corners = (w) => [-1, 1].map((s) => S.box(16 + s * (7.75 + w / 2), 7.7 - w / 2 + 1, w / 2, w / 2 + 1));     // the horns' outer corners stay square
    const body = S.union(S.grow(white, R.W.line), ...corners(R.W.line));
    c.fill(S.union(S.grow(white, R.W.line + R.W.thin), ...corners(R.W.line + R.W.thin)), P.flat(R.BLACK));
    c.fill(body, P.byDepth(R.W.line, R.BLUE_LINE));
    c.fill(white, P.flat('#ffffff'));
    const pale = R.deep(c, { rim: '#2c58fa', edge: '#c4d2ff', body: '#ffffff' }, { depth: 0.55, rim: 0.16 });
    for (const side of [-1, 1]) c.fill(S.polygon(R.lunePts({ r: 13.85, span: 57, thick: 1.85, side })), pale);
  },

  // A white plus with a thin black border and the pale glow. The game's: arms 14 long and 4 wide about (16, 16), one
  // pixel of black round it. (The game's glow lies a pixel to the right of and below the plus and the frame cuts it at
  // the right; drawn evenly round it.)
  ip_heal(c) {
    const a = 7, w = 2, q = [[w, -a], [w, -w], [a, -w], [a, w], [w, w], [w, a], [-w, a], [-w, w], [-a, w], [-a, -w], [-w, -w], [-w, -a]];
    const plus = q.map(([x, y]) => [16 + x, 16 + y]), edge = G.offsetPts(plus, R.W.thin);
    R.softHalo(c, S.polygon(edge, R.FARTHEST), GLOW_PALE);
    c.fill(S.polygon(edge), P.flat(R.BLACK));
    c.fill(S.polygon(plus), R.deep(c, 'white', { depth: 0.6 }));
  },

  // "No action": a white ring with a bar across it, a blue line inside every edge, black round it, the two openings
  // clear. The game's: the ring's white from radius 12.23 to 15.09 about (16, 16) (2.86 wide), two pixels of black
  // inside it (to 10.32) and the frame cutting the black outside it; the bar 4.42 wide, rising at 42.1 degrees (its
  // middle line read off ten rows), 1.6 of black either side. The redraw lays the bar at 31 degrees and lets the ring
  // run out of the frame. Changed from the game: the black outside the ring is whole and as wide as the black inside
  // it (1.5), for which everything is drawn 0.97 of its size; and the bar goes through the centre (the game's passes
  // 0.64 beside it, and its two openings differ in size).
  i_noaction(c) {
    const out = 15.9 - R.W.thick, wide = 2.8, a = (42 * Math.PI) / 180, ux = 20 * Math.cos(a), uy = -20 * Math.sin(a);
    const body = S.union(S.ring(16, 16, out - wide / 2, wide), S.intersect(S.bar(16 - ux, 16 - uy, 16 + ux, 16 + uy, 4.3), S.circle(16, 16, out)));
    R.whiteBody(c, body, { border: R.W.thick });
  },

  // "Not ready": in the game an opaque black square (laid by render_final.js) with a thin light grey ring. Measured
  // on the game's icon: the ring's middle at radius 13.25, 1.65 wide, its grey 218 of 255; it stands a quarter of a
  // pixel right of and above the middle of the frame there, and is drawn in the middle.
  i_notready(c) {
    c.fill(S.ring(16, 16, 13.25, 1.65), P.flat('#dadbde'));
  },

  // "Pause" and its three levels, "Solo mode" and its three: in the game each is put together from the same pieces
  // (compared pixel by pixel with tools/flat_round_cmp.py: i_pause1 is i_pause plus the ring and nothing else; i_solo1
  // is i_solo2 plus two smaller figures): the round light, the blue or the white hourglass or the figure, the yellow
  // ring, the ring's inner arcs. Drawn from the same pieces (parts), all about (16, 16).
  // (The redraw of i_pause shows a smaller hourglass than that of i_pause1; the game's is the same in both.)
  i_pause(c) { R.light(c); R.hourglass(c, 'blue'); },
  i_pause1(c) { R.light(c); R.hourglass(c, 'blue'); R.yellowRing(c); },
  // the white hourglass: the light is red right beside it (half a unit, as the game's one pixel)
  i_pause2(c) { whiteHourglass(c); R.yellowRing(c); },
  i_pause3(c) { whiteHourglass(c); R.yellowRing(c, { arcs: true }); },
  i_solo(c) { R.light(c); c.fill(R.figure(), P.flat(R.BLACK)); },
  i_solo1(c) { R.light(c); threeFigures(c); R.yellowRing(c); },
  i_solo2(c) { R.light(c); c.fill(R.figure(), P.flat(R.BLACK)); R.yellowRing(c); },
  i_solo3(c) { R.light(c); threeFigures(c); R.yellowRing(c, { arcs: true }); },

  // The waves of the Force (parts: forceWaves). In the middle a white disc of radius 6 whose right part is hollow: in
  // the game solid white from its left edge to 0.4 short of the middle, and from there only a rim 1.7 wide. No black
  // (the game's white pieces have a faint dark pixel beside them at a tenth to a third opacity: left out).
  i_force02(c) {
    const F2 = R.forceWaves();
    F2.blue(c, 0, 6.0, 11.0);
    for (const s of F2.crescents) c.fill(s, R.deep(c, { ...R.PALE, body: '#dcdcde', edge: '#cfd0d6' }, { depth: 0.5, rim: 0.1 }));
    for (const s of F2.bands) c.fill(s, R.deep(c, { ...R.PALE, body: '#f4f4f6' }, { depth: 0.55, rim: 0.1 }));
    c.fill(S.union(S.ring(16, 16, 6.0 - 0.85, 1.7), S.intersect(S.circle(16, 16, 6.0), S.halfPlane(15.6, 16, 1, 0))), R.deep(c, R.PALE, { depth: 0.6, rim: 0.1 }));
  },
  // "Resist Force": the same waves on black, and the disc a ring with a bar across it (the sign for "no"). The game's:
  // the ring white from radius 3.75 to 6.0, the bar 1.5 wide at 45 degrees, black inside the ring; every white piece has
  // black round it, wide enough to fill the gaps between ring, bands and crescents (2.8 and 2.8 to 3.3 wide), and the
  // frame cuts the black outside the crescents away. The blue starts one unit left of the upright there.
  // Changed from the game: the black is 1.5 round everything and whole, for which everything is 0.95 of its size and
  // the crescents stand 0.5 further in (their inner edge at radius 12.65 instead of 13.16).
  ip_resistforce(c) {
    const k = 0.95, F2 = R.forceWaves({ k, lune: 12.65 });
    const sign = S.union(S.ring(16, 16, ((6.0 + 3.75) / 2) * k, 2.25 * k), S.intersect(S.bar(16 - 8, 16 + 8, 16 + 8, 16 - 8, 1.5 * k), S.circle(16, 16, 6.0 * k)));
    F2.blue(c, -1.0 * k, 6.0 * k, 11.0 * k);
    c.fill(S.union(sign, S.circle(16, 16, 4 * k), ...F2.bands, ...F2.crescents), P.flat(R.BLACK), R.W.thick);
    for (const s of F2.crescents) c.fill(s, R.deep(c, { ...R.PALE, body: '#dcdcde', edge: '#cfd0d6' }, { depth: 0.5, rim: 0.1 }));
    for (const s of F2.bands) c.fill(s, R.deep(c, { ...R.PALE, body: '#f4f4f6' }, { depth: 0.55, rim: 0.1 }));
    c.fill(sign, R.deep(c, R.PALE, { depth: 0.6, rim: 0.1 }));
  },

  // "Disengage": a white figure running to the right, a blue line inside its edge, one pixel of black round it.
  // The game's figure, read off its rows: head 4 across about (23.5, 4.2), over the right shoulder; the body a
  // slanted block 6.4 wide, its left edge straight from (16.7, 9.5) to (10.3, 18.5), the shoulders level at y 6.4 from
  // x 13 to 24, the hips 10 wide at y 17.5; the arm behind level along the shoulders to an elbow at (12.5, 7.6) and
  // down to a fist at (8.5, 11.7); the arm in front down the body's right side to an elbow at (23, 14.6) and forward
  // to a hand at (30, 16); the leg behind down to a knee at (10.9, 20.7), level back to (3.6, 21.7) and the foot
  // hanging to y 25.6; the leg in front straight down to the right to (24, 23.7) with the foot pointing right.
  // Drawn as what it is made of: a round head, a body and limbs of one thickness each with round ends, all one white
  // piece. The two notches the game fills with black (under the arm behind; between the body and the arm in front)
  // are black here too.
  i_disengage(c) {
    const limb = (a, b, w) => S.capsule(a[0], a[1], b[0], b[1], w);
    const body = S.union(S.circle(23.5, 4.2, 2.0), limb([23.3, 5.6], [22.6, 7.4], 2.6),
      limb([19.9, 9.0], [14.0, 16.5], 5.2), limb([14.0, 16.5], [18.4, 16.9], 4.2),            // the body; the hips
      limb([19.5, 7.5], [12.6, 7.5], 2.2), limb([12.6, 7.6], [8.8, 11.4], 2.5),                // the arm behind: upper arm, forearm
      limb([22.9, 8.0], [23.0, 14.6], 2.7), limb([23.3, 15.5], [29.5, 16.2], 2.5),             // the arm in front
      limb([13.2, 17.4], [10.9, 20.7], 3.2), limb([10.9, 21.1], [3.9, 21.7], 2.5), limb([3.5, 21.9], [3.5, 24.5], 2.3),      // the leg behind: thigh, shin, foot
      limb([18.6, 17.2], [21.9, 20.9], 3.5), limb([21.9, 20.9], [24.1, 23.7], 2.9), limb([24.4, 24.4], [27.0, 25.2], 2.4));  // the leg in front
    const notches = [[[16.4, 8.9], [13.5, 8.9], [10.6, 12.3], [13.6, 12.9]], [[21.6, 10.8], [21.7, 15.4], [22.4, 17.3], [22.8, 18.4], [20.1, 16.0], [18.6, 15.2]]];
    for (const n of notches) c.fill(S.polygon(n), P.flat(R.BLACK));
    R.whiteBody(c, body);
  },

  // "Force wave": three red waves one under the other, 8 apart, the same wave three times (in the game pixel for
  // pixel), one pixel of black round each. One wave, read off the game's columns: a band with a point at each end,
  // low at the left (3.0, 9.6) and high at the right (29.15, 4.35), where its lower edge comes up steeply (6.0 at x
  // 28.5); its upper edge swells up at the left (5.3 at x 12) and dips at the right (6.6 at x 21); its lower edge
  // keeps nearly level at the left (8.4 at x 9) and swells down at the right (10.6 at x 20): 3 thick at the left, 4
  // at the right. Each edge is two arcs that run into one another (circles fitted to the columns: 12.6 and 13.8 in
  // radius above, 14.7 and 9.5 below). Its red is the game's (204, 36, 12).
  ip_wave(c) {
    const TL = [3.0, 9.6], TR = [29.15, 4.35], red = { rim: '#4a0702', edge: '#aa1c08', body: '#cc240c' };
    const wave = R.outline(R.sCurvePts(TL, [16.7, 6.0], 19.6, TR), R.sCurvePts(TL, [15.8, 9.7], 27, TR).reverse());
    const waves = [0, 8, 16].map((dy) => wave.map(([x, y]) => [x, y + dy]));
    for (const w of waves) c.fill(S.polygon(G.offsetPts(w, R.W.thin, 2.0)), P.flat(R.BLACK));          // all the black first
    for (const w of waves) c.fill(S.polygon(w), R.deep(c, red, { depth: 0.7 }));
  },

  // "Force whirlwind": a red spiral on black with a red sweep outside it at the lower right. The game's arm, read
  // along 72 rays from (12.5, 12.5): it leaves the middle to the right, 1.6 out, and winds anticlockwise two turns and
  // an eighth, to 5.6 after one turn and 11.4 after two; 2.25 to 3.25 wide (2.6 at the median), narrowing to a point
  // at both ends. Drawn as a spiral of quarter circles (tools/flat_round_spiral.py fits one to the 152 points read:
  // first centre (11.96, 11.85), first radius 1.70 pointing 10 degrees below the level, each quarter about a point
  // 1.20 further back, the step growing by 0.034; the game's arm strays 0.26 from it on average, 1.0 at most).
  // The sweep: a crescent from (26.5, 4.3) to (8.6, 27.1), 3.2 wide at its middle (its middle line fits a circle of
  // radius 14.1 about (15.3, 14.1)). The black: in the game it surrounds the red by two units or more, closes every
  // gap between the arms, fades out softly over a pixel and a half, and is cut by the frame at the left, the right and
  // the bottom. Changed from the game: the black is whole, for which everything is drawn 0.93 of its size.
  ip_whirlwind(c) {
    const k = 0.93, Z = (p) => [16 + (p[0] - 16) * k, 16 + (p[1] - 16) * k], turn = 768;
    const half = (t) => 1.3 * k * R.smooth(-12, 75, t) * R.smooth(turn + 4, turn - 55, t);
    const arm = S.polygon(R.spiralBandPts({ c0: Z([11.96, 11.85]), r0: 1.7 * k, a0: 9.9, step: 1.203 * k, grow: 0.0339 * k, turn, half }));
    const sweep = S.polygon(R.crescentPts(Z([26.5, 4.3]), Z([8.6, 27.1]), -9.74 * k, -12.93 * k));
    c.glow(S.grow(S.union(arm, sweep), 1.6), R.BLACK, 0.7, 1);
    for (const s of [arm, sweep]) c.fill(s, R.deep(c, R.RED, { depth: 0.8 }));
  },

  // "Critical strike" III: the crossed bars of I and II (flat sharp sheet) on a red disc in a white ring, a white
  // diamond where they cross. The game's, read along its diagonals and between them: the disc red (190, 27, 0) to
  // radius 12.35, black to 13.75, the ring white to 16.2, where the frame cuts it. Each arm is 3.5 wide and is the
  // disc's red where it leaves the diamond, whitening steadily outwards (a fifth white at radius 6.5, half at 9.5,
  // four fifths at 12.5) until it runs into the ring as white: the black inside the ring stops at the arms. A dark
  // edge lies along each arm, as strong as the arm is light there (none near the middle). The diamond: 7 from point
  // to point, upright. Changed from the game: the ring is whole with a thin black round it, inside the frame, and
  // everything is 0.94 of its size to make room.
  i_crtstrk03(c) {
    const k = 0.94, b = R.W.thin, r0 = 15.9 - b, r1 = r0 - 2.45 * k, Rd = r1 - 1.4 * k, hw = (3.5 * k) / 2, q = 3.5 * k;
    const whiten = (r) => Math.pow(S.clamp((r - 2.9 * k) / (11.6 * k), 0, 1), 1.2);
    c.fill(S.circle(16, 16, 15.9), P.flat(R.BLACK));
    c.fill(S.ring(16, 16, (r0 + r1) / 2, r0 - r1), P.flat('#ffffff'));
    c.fill(S.circle(16, 16, Rd), R.deep(c, R.RED));
    const d = (r1 + 0.6) / Math.SQRT2, arms = S.union(S.bar(16 - d, 16 - d, 16 + d, 16 + d, 2 * hw), S.bar(16 - d, 16 + d, 16 + d, 16 - d, 2 * hw)), af = c.field(arms);
    const red = R.lin(R.RED.body), white = [1, 1, 1], dark = R.lin('#1c0402'), rad = (px) => Math.hypot(px.x - 16, px.y - 16);
    c.fill(S.circle(16, 16, Rd), (px) => { R.put(px, dark, Math.min(1.25 * whiten(rad(px)), 1) * (1 - R.smooth(0, 0.9, af[px.i]))); });      // the dark edge beside the arms
    c.fill(arms, (px) => { R.put(px, R.mix3(red, white, whiten(rad(px)))); });
    c.fill(S.polygon([[16, 16 - q], [16 + q, 16], [16, 16 + q], [16 - q, 16]]), P.flat('#ffffff'));
  },

  // "Duel" III: the crossed swords of I and II (flat sharp sheet: the same two swords) on white. In the game the
  // white is one piece: a disc and, round the swords, the shape that II draws as a line (the swords' outline two
  // units off); the swords stand on it with a dark blue edge instead of a black one; nothing black, nothing outside
  // the white. The game's disc reaches as far as that shape does at the top, the bottom and the sides (26 by 25
  // against 26 by 26); drawn the same way round the swords as the flat sharp sheet draws them: radius 14.5.
  i_duel03(c) {
    const o = { pommel: 1.25, grip: 2.0, guardAt: 8.25, guard: 6.5, guardT: 1.4, guardPoint: 0.75, blade: 1.95, taper: 1.4 };
    const A = G.frame([4.8, 27.4], [26.3, 4.1]), B = G.frame([27.2, 27.4], [5.7, 4.1]);
    const round = [A, B].map((f) => S.polygon(G.offsetPts(f.pts(W.swordOutline(f.L, { ...o, guardPoint: 0, pommel: 0 })), 2.1, 1.5)));
    c.fill(S.union(S.circle(16, 16.3, 14.5), ...round), R.deep(c, 'white', { depth: 0.6 }));
    for (const part of ['border', 'body']) for (const [f, side] of [[A, 1], [B, -1]]) W.glowSword(c, f.E, f.T, o, { palette: 'blue', side, ink: '#0b1c86', part });
  },

  // "Sniper shot" I, II and III: the target (parts: one construction), with a second ring from II and the square of
  // the sight in III.
  i_sshot01(c) { R.target(c); },
  i_sshot02(c) { R.target(c, { inner: true }); },
  i_sshot03(c) { R.target(c, { inner: true, box: true }); },

  // "Force jump" III: three white arrows pointing up inside a white ring, black round everything, clear between.
  // The game's arrow: head 8 wide and 4 high (sides at 45 degrees), shaft 4 wide and 5 long, of which the lowest 3
  // are blue (82, 118, 255: flat, with a hard edge to the white); one pixel of black round it. The first stands on
  // the axis from y 6, the other two 9 lower and 5 either side. The game's ring is white from radius 13.0 to 15.5 with
  // two pixels of black inside it and the frame cutting the black outside it. (The redraw left the blue out.)
  // Changed from the game: the black outside the ring is whole (1.5, as inside it), for which ring and arrows are
  // drawn 0.96 of their size; the first arrow stands 0.16 higher so that its border runs into the ring's as in the game.
  // The arrows are shaded like the jump arrows of the flat sharp sheet (white before blue).
  i_jump03(c) {
    const out = 15.9 - R.W.thick, wide = 2.3, ring = S.ring(16, 16, out - wide / 2, wide), k = 0.964;
    c.fill(ring, P.flat(R.BLACK), R.W.thick);
    c.fill(ring, R.deep(c, 'white', { depth: 0.6 }));
    const A = { head: 4 * k, shaft: 2 * k, length: 9 * k }, tail = 3 * k;
    const arrows = [[16, 6.2], [16 - 5 * k, 16 - k], [16 + 5 * k, 16 - k]].map(([x, y]) => R.arrowUp(x, y, A));
    for (const pts of arrows) c.fill(S.polygon(G.offsetPts(pts, R.W.thin)), P.flat(R.BLACK));
    const white = R.deep(c, 'white', { depth: 0.6 }), blue = R.deep(c, 'blue'), q = { r: 0, g: 0, b: 0 };
    for (const pts of arrows) {
      const y0 = pts[0][1] + A.length - tail;                    // above: white; below: blue. One body, its edge shaded as one.
      c.fill(S.polygon(pts), (px) => {
        const t = S.clamp((px.y - y0) * c.k + 0.5, 0, 1);
        if (t <= 0) return white(px);
        if (t >= 1) return blue(px);
        white(px); q.r = px.r; q.g = px.g; q.b = px.b; blue(px);
        px.r = q.r + (px.r - q.r) * t; px.g = q.g + (px.g - q.g) * t; px.b = q.b + (px.b - q.b) * t;
      });
    }
  },
};
