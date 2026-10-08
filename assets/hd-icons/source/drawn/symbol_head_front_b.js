'use strict';
// The other icons of the sheet "head, seen from the front": the bust of parts/symbol_head_front.js, placed and scaled
// as drawn/symbol_head_front.js places it, with what each icon adds to it. The bust is ChatGPT's redrawn figure; what
// is ADDED to it is simple, and for simple things the game's own icon gives the design: places, sizes and colours are
// read off its pixels (tools/vmap.py) and stated with each icon; what was changed from the game is stated too.
// Units: the game icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const H = require('../parts/symbol_head_front');
const B = require('../parts/symbol_head_front_b');

// ---- a shield with a cross -----------------------------------------------------------------------------------------
// The emblem on the chest of "Immunity": in the game a black shield 9 wide (x 11 to 20, on the bust's axis) from
// y 19 to 29, its upper edge with a point in the middle and at both corners (one pixel higher than between them), its
// sides upright down to y 26 and its foot rounded in to the axis; a blue line one pixel wide along its edge, white
// outside it; in it a white plus 5 long with bars one pixel wide, its middle at (15.5, 24.5).
//   cx: the axis; top: the y of the corners and of the middle point; half: the half-width; sag: how far the upper edge
//   dips between its points (a circular arc); waist: where the sides end; r: the radius the foot's corners turn in
//   with; bottom: the point on the axis (reached by a straight line from each corner's round)
const shieldPts = (cx, top, half, sag, waist, r, bottom) => {
  const ctr = [cx + half - r, waist], dx = cx - ctr[0], dy = bottom - ctr[1], d = Math.hypot(dx, dy);
  const deg = (Math.atan2(dy, dx) - Math.acos(r / d)) * 180 / Math.PI;               // where the straight line leaves the round
  const right = [...B.bow([cx, top], [cx + half, top], sag), ...G.arcPts(ctr[0], ctr[1], r, 0, deg, 0.04), [cx, bottom]];
  return right.concat(right.slice(1, -1).reverse().map(([x, y]) => [2 * cx - x, y]));
};

// ---- a sore --------------------------------------------------------------------------------------------------------
// A mark on the skin: an ellipse of the bust's saturated red, a little deeper towards its edge, its edge soft over a
// quarter of a unit (it is in the skin, not on it).
const sore = (c, x, y, rx, ry, turn = 0) => {
  const body = B.lin('#f25238'), edge = B.lin('#d9361b');
  c.fill(S.ellipse(x, y, rx, ry, turn), (px) => { B.put(px, B.mix3(edge, body, B.smooth(0, 0.8, -px.d)), B.smooth(0, 0.28, -px.d)); });
};

// ---- dark veins ----------------------------------------------------------------------------------------------------
// The poison of "Affliction": dark veins that climb the chest from its lower edge. Read off the game's pixels (black
// and dark red, one to two pixels wide, a red fringe beside them):
//   the trunk rises on x 14.9 from the bottom to y 26.6, leans left to (11.9, 22.8), turns back up to (13.5, 20.9)
//   and ends in a tip under the neck's left side (13.5, 18.9); a second tip comes in from the neck's right side
//   (16.7, 18.9) and joins it at (13.4, 21.6): a fork;
//   right of it a Y: its stem on x 19.5 from the bottom to y 27, its arms to the tips (18.3, 24.7) and (20.8, 23.9);
//   left of it a short one from the bottom (10.2) to the tip (10.8, 25.7).
// Each is a line of straight pieces joined by circular arcs, of one width (trunk 1.25, the others 1.1) and drawn out
// to a point over its last stretch. Black with the bust's red at the edge and a red shadow beside it (B.hollow).
const VEINS = [
  { line: [[13.5, 18.9], [13.5, 20.9], [11.9, 22.8], [14.9, 26.6], [14.9, 31.5]], r: 1.5, hw: 0.62, tip: 2.6 },
  { line: [[16.7, 18.9], [15.6, 20.3], [13.2, 21.8]], r: 1.2, hw: 0.5, tip: 2.6 },
  { line: [[18.3, 24.7], [18.7, 25.9], [19.5, 27.2], [19.5, 31.5]], r: 1.2, hw: 0.55, tip: 2.2 },
  { line: [[20.8, 23.9], [20.5, 25.5], [19.5, 27.4]], r: 1.2, hw: 0.5, tip: 2.6 },
  { line: [[10.8, 25.7], [10.2, 31.5]], r: 0, hw: 0.55, tip: 2.2 },
];
const veins = (list) => S.union(...list.map((v) => S.polygon(B.taperStroke(B.filletPath(v.line, v.r), (s) => v.hw * Math.min(s / v.tip, 1)))));

// ---- the rings of a stunned head -----------------------------------------------------------------------------------
// "Stun", "Stun droid" and "Insanity": two rings of thin light round the head, like the lines drawn round something
// that shakes. In the game (the three icons carry the same rings, one pixel wide, pale red at four tenths opacity,
// the same left and right of x 16): the inner one runs unbroken from beside the jaw (y 23) up the side at x 6.5,
// over the head at y 5.5 and down the other side; the outer one is in three pieces: a bar over the head at y 2.5
// from x 12 to 20, and one down each side from (9, 3.3) round to x 2.5 and down to y 18.5.
// Here both follow the head's own outline at one distance each (2.3 and 5.8: the game's 2.2 beside and 2.4 above
// the head, 6.2 and 5.4), so they are concentric with it; the outer one's pieces end where the game's do.
const RINGS = { inner: 2.3, outer: 5.8, innerTo: 23.0, top: 4.3, side: 7.0, sideTo: 18.6, hw: 0.5, colour: '#ff9c8c', strength: 0.78 };
const rings = (c, pl, form, q = RINGS) => {
  const head = B.headLine(pl, form, 13.0), ax = pl.at[0];
  const lines = [
    ...B.pieces(B.beside(head, q.inner), (x, y) => y <= q.innerTo),
    ...B.pieces(B.beside(head, q.outer), (x, y) => Math.abs(x - ax) <= q.top || (Math.abs(x - ax) >= q.side && y <= q.sideTo)),
  ];
  for (const l of lines) B.softLine(c, l, q.hw, q.colour, q.strength);
};

// ---- the crescent over the head ------------------------------------------------------------------------------------
// "Sleep" (the blue one) and "Stasis": a broad crescent of one flat colour bent over the small bust. Fitted to the
// game's pixels (the two icons carry the same shape): its outer edge a circle of radius 15.4 about (16, 16.7), its
// inner edge a circle of radius 12.6 about (16, 20.8) (each within a third of a pixel), 6 thick over the head and 3
// beside it; below y 19.5 the arms draw in to points at y 24.5 (3, 2, 2, 1, 1 pixels wide by row).
// Changed from the game: there the frame cuts the outer circle flat at both sides. Here its radius is 15.2, so that
// it stands whole inside the frame with its border. The arms' points are made by one straight line each: the inner
// circle's tangent at y 19.5, carried on to the outer circle (which it meets at y 24.6).
const CRESCENT = { outer: [16, 16.8, 15.2], inner: [16, 20.8, 12.6], straightFrom: 19.5 };
const crescentPts = (q = CRESCENT) => {
  const [ox, oy, R] = q.outer, [ix, iy, r] = q.inner, deg = (a) => (a * 180) / Math.PI;
  const dy = q.straightFrom - iy, dx = Math.sqrt(r * r - dy * dy), T = [ix + dx, q.straightFrom];      // where the right arm's inner edge turns straight
  const t = [-dy / r, dx / r];                                   // the tangent there, heading down
  // the point where that line meets the outer circle
  const fx = T[0] - ox, fy = T[1] - oy, b = fx * t[0] + fy * t[1], k = -b + Math.sqrt(b * b - (fx * fx + fy * fy - R * R));
  const tip = [T[0] + t[0] * k, T[1] + t[1] * k], aTip = deg(Math.atan2(tip[1] - oy, tip[0] - ox)), aT = deg(Math.atan2(dy, dx));
  // round the outside from the left point over the top to the right point, then back along the inside
  return [...G.arcPts(ox, oy, R, 180 - aTip, 360 + aTip, 0.05), ...G.arcPts(ix, iy, r, 360 + aT, 180 - aT, 0.05)];
};
const FLAT = {
  blue: { rim: '#0b1c86', edge: '#2452f0', body: '#5484fc' },
  red: { rim: '#6c0c0c', edge: '#d43018', body: '#fc543c' },
};
const underCrescent = (c, hue) => {
  F.solid(c, crescentPts(), { palette: FLAT[hue], border: H.BORDER, depth: 1.0 });
  H.bust(c, B.SMALL.pl, { hue, ...B.SMALL.form });
};

// ---- an arrow pointing down ----------------------------------------------------------------------------------------
// tip: its point; half: the head's half-width (and, its sides standing at 45 degrees, its height); stem: the stem's
// half-width; len: the stem's length
const arrowDown = (tip, half, stem, len) => {
  const [x, y] = tip, yb = y - half;
  return [[x - stem, yb - len], [x + stem, yb - len], [x + stem, yb], [x + half, yb], [x, y], [x - half, yb], [x - stem, yb]];
};
const WHITE = { rim: '#8a8a96', edge: '#e4e4ec', body: '#ffffff' };

module.exports = {
  // "Dominate mind": a white arrow pressing down on an arch of light over a red head. The game's measures: the arrow
  // 10 wide in the stem (x 11 to 21) from y 1, its head 16 wide at y 6 and drawn in at 45 degrees to its point at
  // (16, 14); the arch two pixels wide (white outside, red inside, three across on its slopes: red, white, red), its
  // middle line a half circle of radius 13 about (16, 28) with upright legs down to the frame; the head 13 wide, its
  // top at y 17, cut off under the chin by the frame's lower edge.
  // Changed from the game: arrow and arch stand on x 16 there and the head half a pixel to the right (it is an odd
  // number of pixels wide); here all three share the axis. The arrow stands half a unit lower, so that its point
  // runs into the arch's white middle (white on white: one piece, as in the game, where the two touch). The arch's
  // legs end square just inside the frame with their border whole.
  ip_dominate(c) {
    const W = require('../parts/weapons');
    const arrow = arrowDown([16, 14.5], 8, 5, 5), arch = [[3, 31.2], ...G.arcPts(16, 27.8, 13, 180, 360, 0.05), [29, 31.2]];
    const pl = { at: [16.0, 17.0], s: 1 };
    W.tube(c, arch, 1.1, { palette: 'red', border: H.BORDER, core: 0.36, part: 'border' });
    F.borders(c, [arrow], H.BORDER);
    H.bust(c, pl, { hue: 'red', part: 'border' });
    W.tube(c, arch, 1.1, { palette: 'red', border: 0, core: 0.36, part: 'fill' });
    H.bust(c, pl, { hue: 'red', part: 'body' });
    F.solid(c, arrow, { palette: WHITE, border: 0, depth: 0.5, rim: 0.1 });
  },

  // "Sleep" in blue and "Stasis" in red: the small bust of "Sleep" (the same place and form as there) under the
  // crescent. Their borders do not meet: the head stands 2.7 under the crescent's inner edge, as in the game.
  ip_sleep01(c) { underCrescent(c, 'blue'); },
  ip_stasis(c) { underCrescent(c, 'red'); },

  // "Stun" and "Stun droid" (one picture in the game): the red bust cut off below the shoulders, the rings round its
  // head, and a question mark on its face. The game's mark: dark red, one pixel wide, from y 13 to 19 with its dot
  // at y 21.5, 5 wide (x 13.5 to 18.5), on the bust's axis. Here: a hook of radius 2.15 about (16, 15.5), the line
  // 1.4 wide, in the dark red of the cross of "Kill" (the redraw's mark is half as thick again and black).
  ip_stun(c) {
    rings(c, B.AURA.pl, B.AURA.form);
    H.bust(c, B.AURA.pl, { hue: 'red', ...B.AURA.form });
    c.fill(B.question([16, 15.5], 2.15, 0.7), F.deepening(c.k, B.CROSS_RED, { depth: 0.45, rim: 0.12 }));
  },
  ip_droidstun(c) { module.exports.ip_stun(c); },
  // "Insanity": the same without the mark.
  ip_insanity(c) {
    rings(c, B.AURA.pl, B.AURA.form);
    H.bust(c, B.AURA.pl, { hue: 'red', ...B.AURA.form });
  },

  // "Affliction": the red bust with the veins on its chest (see VEINS). They end where the chest ends.
  ip_affliction(c) {
    const bust = H.bust(c, B.chest(15.5), { hue: 'red' });
    c.layer((t) => B.hollow(t, veins(VEINS), 'red', 0.5), { mask: bust });
  },

  // "Wound": the red bust with a cross on the left of its chest. In the game the cross is the one of "Kill" (the same
  // seven pixels square, the same dark reds b61a00 to d22f14), with its crossing at (10.5, 23.5): the same bars here.
  ip_wound(c) {
    H.bust(c, B.chest(16.5), { hue: 'red' });
    B.cross(c, [10.5, 23.5], 4.6, 1.3);
  },

  // "Cure": the blue bust with a skull's face (what is cured) and a medical cross on its chest. In the game the cross
  // is white, 6 long with bars 2 wide, in a black line one pixel wide (8 by 8 with it), its middle at (17, 23): half
  // a pixel right of the bust's axis, because a bar two pixels wide cannot stand on an axis that runs through the
  // middle of a pixel. Here it stands on the axis.
  ip_cure(c) {
    const pl = B.chest(16.5), bust = H.bust(c, pl, { hue: 'blue' });
    B.skull(c, pl, 'blue', bust);
    B.badgePlus(c, [16.5, 23.0], 4.0, 4.0, bust);
  },

  // "Plague": the red bust with the skull's face and sores on its chest. In the game the sores are patches of the
  // saturated red (f04d32, d9361b) on the pale skin: a small one on the left shoulder (9.5, 20.3), one beside the
  // breastbone (13.4, 23.0, higher than wide), one right of the neck (21.0, 21.4), a round one low on the left
  // (9.0, 26.9) and a long one low on the right (22.4, 26.9). Ellipses of those places and sizes.
  ip_plague(c) {
    const pl = B.chest(16.5), bust = H.bust(c, pl, { hue: 'red' });
    B.skull(c, pl, 'red', bust);
    sore(c, 9.5, 20.3, 1.0, 0.9);
    sore(c, 13.4, 23.0, 1.35, 2.1, 14);
    sore(c, 21.0, 21.4, 1.9, 1.3, -8);
    sore(c, 9.0, 26.9, 1.8, 1.7);
    sore(c, 22.4, 26.9, 2.4, 1.1, -6);
  },

  // "Immunity": the blue bust with the shield and its cross on the chest (see shieldPts for the game's measures).
  ip_immunity(c) {
    const bust = H.bust(c, B.chest(15.5), { hue: 'blue' });
    const pts = shieldPts(15.5, 19.4, 4.5, 0.9, 25.2, 2.6, 28.9), shape = S.polygon(pts);
    c.layer((t) => t.glow(shape, '#ffffff', 0.8, 0.95), { mask: bust });
    c.fill(shape, P.byDepth(0.7, [[0, '#4a6fff'], [0.3, '#1541ec'], [0.62, '#00176f'], [1, H.INK]]));
    c.fill(S.polygon(B.plus(15.5, 24.4, 2.5, 1.1)), P.byDepth(0.25, [[0, '#b9c8ff'], [1, '#ffffff']]));
  },
};
