'use strict';
// Constructed drawings of the flat sharp symbols, second part: power attack I to III, power shot I to III, rapid shot
// I to III, slow, suppress. As in drawn/flat_sharp.js nothing is traced: outlines are straight lines and circular arcs
// from measured dimensions, borders are the same outlines moved out with sharp corners, shading is formulas in each
// object's own frame. The GAME's icon gives each design (its pixels read with tools/vmap.py and tools/sharp_b_px.py);
// where a drawing departs from the game, its comment says so.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const W = require('../parts/weapons');
const F = require('../parts/flat');
const B = require('../parts/flat_sharp_b');

// ---- rapid shot ----------------------------------------------------------------------------------------------------
// Rows of the same bullet, as the game places them: I two large ones, one above the other (bases at x 8, axes y 10 and
// 21); II three small ones (axes y 8, 16, 24; bases at x 10, the middle one at 14); III six (the same rows, two to a
// row 13 apart; bases at x 3 and 16, the middle row at 7 and 20). The small bullet is the large one at two thirds.
const SMALL = 2 / 3;

// ---- power shot ------------------------------------------------------------------------------------------------------
// What it is: the large bullet flying to the right inside a glowing wake. A thin red line runs round its back (above,
// behind and below it, black between line and bullet), and in front of it the line opens into a bow: a crescent whose
// two horns sweep back past the line. The glow is hottest along the bow's leading edge and cools towards the back:
// white, pink, salmon, red, and the deep red be1b00 for the line's rear half. I has the bow alone; II has a second
// pair of horns in red behind the first; III is all fire: the wake is a red sheet from the bow back to two pairs of
// long streaks, with only the bow's leading edge white.
// Read off the game's pixels (I; mirror images about y 16):
//   bullet   base at x 7, axis y 16 (III: base at x 9; there the whole wake stands 2 further right)
//   line     one pixel wide: y 10 to 11 and 21 to 22, two pixels of black between it and the bullet
//   bow      outer edge: the pixels' outer corners lie on the circle about (17, 16) of radius 12 (29 on the axis, 27 in
//            row 9, 25 in row 7; the horn's point in row 4, columns 16 and 17); a horn's inner edge is the straight
//            line x - y = 11.5 (one pixel further right in every row down, from the point to the line at x 21.5);
//            behind the bow the black round the bullet's nose is bounded by a flat arc (x 23.7 on the axis, 22.85 in
//            row 12: a circle of radius 7.5 about (16.2, 16)), and the line's inner side thickens into it over its
//            last four pixels (row 11: 460a00, 7c1200, ab1900, d63318 from x 18)
//   colours  along the line and on into the bow, by the distance behind the bow's white (which runs 1.8 inside the
//            outer circle, two pixels wide): ffffff, 1 ffe8e4, 2 ffc9c0, 3 ffb8ad, 5 ffb3a6, 6 ff8f7c, 8 ff735b,
//            10 ff5c41, 12 e54227, 14 d53217, from 16 on be1b00; the bow's outermost pixel is the red d63318, and so
//            is the pixel along a horn's inner edge and along the black round the nose
//   II       the second horns: outer edge a circle about (10.2, 16) of radius 10.6 (x 14.4 in row 6, 16.3 in row 7,
//            18.3 in row 9), inner edge the line x - y = 4.2, point at (9.6, 5.4); they stand on the line and are
//            coloured as it is there (e13e23 to f65338); the black between first and second horn reaches up to the
//            straight line from point to point; the bow's white runs out to its edge (no red pixel outside it)
//   III      upper edge level at y 4 from the circle's top to the first streak's point at x 5.2; the streak's lower
//            edge falls one in three to a notch at (14.2, 7); from there the second streak's upper edge runs level at
//            y 7 to its point, and its lower edge falls one in three on to the line at x 10.5; black between the two
//            streaks up to the straight line from point to point. Colours behind the white: 0 ffe4df, 1 ffa698,
//            2 ff5c41, 3 de3b20, 4 d02d12, 8 c8250a, be1b00 at the back; each streak carries a light of its own
//            (ffb8ad over x 12 to 16 of the first, ffac9e over x 9 to 12 of the second, cooling to red at the points)
// Changed from the game:
//   I: the line's rear stretch stands two pixels behind the bullet as in III (x 4 to 5). In the game it touches the
//   bullet's base (x 6 to 7) with three pixels of black behind it, in II it stands at x 5 to 6: one gap for all three.
//   The game lays up to three soft pixels of black inside a horn's curve and one outside; here the border is the
//   sheet's 0.7 all round.
//   III: the second streak's point stands at x 1.8 (in the game it fades out against the frame at x 0 to 1), so that
//   the point and its border are whole; both streaks are the same spike, 9 long. The lower half is the mirror image
//   of the upper (in the game it is a pixel longer and a little paler).
const PS = {
  R: 12, centre: 17, bullet: 7,                   // the bow's outer circle; x of its centre and of the bullet's base
  line: [4, 5, 10, 11],                           // the line: its rear stretch from x 4 to 5, its upper stretch from y 10 to 11
  horn: 11.5, nose: [16.2, 7.5], flare: [18, 12.2], // a horn's inner edge (x - y); the arc round the nose (centre x, radius); the thickening: from x 18 on the line's inner side to the arc at y 12.2
  wing: { centre: 10.2, R: 10.6, edge: 4.2 },     // II: the second horns
  streak: { top: [5.2, 4], notch: [14.2, 7], low: [1.8, 7], foot: [10.8, 10] },   // III: the two streaks' points, the notch between them, where the lower one meets the line
};
const HEAT = [[0, '#ffffff'], [0.7, '#fffaf9'], [1.1, '#ffe8e4'], [1.7, '#ffd0c8'], [2.5, '#ffccc3'], [3.5, '#ffbdb2'], [5.1, '#ffb3a6'], [6.1, '#ff8f7c'], [7.1, '#ff816c'], [8.1, '#ff735b'],
  [9.1, '#ff6a52'], [10.1, '#ff5c41'], [11.1, '#f14e33'], [12.1, '#e54227'], [13.1, '#db381d'], [14.1, '#d53217'], [15.1, '#c62308'], [16, '#be1b00'], [40, '#be1b00']];
const FIRE = [[0, '#ffeeea'], [0.3, '#ffe4df'], [0.7, '#ffc0b5'], [1.2, '#ff9887'], [2.1, '#ff5e43'], [3.1, '#e23f24'], [4.1, '#d43015'], [6, '#cf2c11'], [8, '#c8250a'], [12, '#c21f04'], [16, '#be1b00'], [40, '#be1b00']];
const blast = (c, level) => {
  const q = PS, y0 = 16, dx = level === 3 ? 2 : 0, cx = q.centre + dx, R = q.R, ridge = level === 3 ? 10.45 : 10.2;
  const lx0 = q.line[0] + dx, lx1 = q.line[1] + dx, ly0 = q.line[2], ly1 = q.line[3];
  const mirror = (p) => [p[0], 2 * y0 - p[1]], deg = (p, ctr) => (Math.atan2(p[1] - y0, p[0] - ctr) * 180) / Math.PI;
  // where the line x - y = e meets the circle about (ctr, y0) of radius r, on its upper side
  const meet = (e, ctr, r) => { const a = e - ctr, b = a - y0, y = (-b - Math.sqrt(b * b - 2 * (a * a + y0 * y0 - r * r))) / 2; return [y + e, y]; };
  // the upper half of the wake's outline, from the bow's foremost point round to the middle of the line's rear stretch
  let half; const bridges = [];
  if (level < 3) {
    const tip = meet(q.horn + dx, cx, R), foot = [ly0 + q.horn + dx, ly0];
    half = [...G.arcPts(cx, y0, R, 0, deg(tip, cx), 0.12), foot];
    if (level === 2) {
      const w = q.wing, wtip = meet(w.edge, w.centre, w.R), wfoot = [w.centre + Math.sqrt(w.R * w.R - (y0 - ly0) * (y0 - ly0)), ly0];
      half.push(...G.arcPts(w.centre, y0, w.R, deg(wfoot, w.centre), deg(wtip, w.centre), 0.12), [ly0 + w.edge, ly0]);
      bridges.push([wtip, tip, foot, wfoot]);
    }
  } else {
    const s = q.streak;
    half = [...G.arcPts(cx, y0, R, 0, -90, 0.12), s.top, s.notch, s.low, s.foot];
    bridges.push([s.top, s.notch, s.low]);
  }
  half.push([lx0, ly0], [lx0, y0]);
  const outer = half.concat(half.map(mirror).reverse().slice(1, -1));
  // the black round the bullet: straight behind, above and below it, an arc round its nose, the line thickening into the arc
  const nx = q.nose[0] + dx, nr = q.nose[1], fx = q.flare[0] + dx, fy = q.flare[1], fa = (Math.asin((y0 - fy) / nr) * 180) / Math.PI, bx = nx + nr * Math.cos((fa * Math.PI) / 180);
  // (the user: the black round the bullet has the bullet's shape: its outline moved out by the gap, no corners in front)
  const hole = G.offsetPts(B.bulletPts(q.bullet + dx, y0), lx1 - (q.bullet + dx) > 0 ? q.bullet + dx - lx1 : 2);
  const holeF = c.field(S.polygon(hole));
  // black: the outline's border, and the ground between neighbouring points
  const lim = level === 3 ? 1.6 : 2.6;
  c.fill(S.polygon(G.offsetPts(outer, 0.7, lim)), P.flat(C.black));
  for (const b of bridges) for (const pts of [b, b.map(mirror).reverse()]) c.fill(S.polygon(G.offsetPts(pts, 0.7, lim)), P.flat(C.black));
  // the glow: every place takes its colour from how far it lies behind the white (HEAT, FIRE: pixels to colour)
  const heat = B.rampLin(level === 3 ? FIRE : HEAT), rimC = B.lin('#d63318'), dark = B.lin('#5e0703'), k = c.k;
  const xr = (y) => cx + Math.sqrt(Math.max(ridge * ridge - (y - y0) * (y - y0), 0));          // the white's circle at a level
  const lineY = (ly0 + ly1) / 2, flareK = (fy - ly1) / (bx - fx), outerRim = level !== 2;
  const at = (stops, x) => { let i = 0; while (i < stops.length - 2 && x > stops[i + 1][0]) i++; const a = stops[i], b = stops[i + 1]; return a[1] + (b[1] - a[1]) * S.clamp((x - a[0]) / (b[0] - a[0]), 0, 1); };
  // I and II: measured along the level, as the game's colours run along the line (the second horns are coloured as
  // the line they stand on, and no hotter than f65338, the brightest the game gives them); the white runs out to the
  // bow's edge.
  // III: measured straight to the white, which is a thin line 1.55 inside the bow's edge with red on both sides. It
  // runs on from the top of its circle (80 degrees up from the front) into the first streak, 0.5 under the streak's
  // level edge, and cools along it (the game's row 4: ffb8ad at x 14, ffa494 at 12, ff7b65 at 10, ef4c31 at 8,
  // c42106 at 6); the second streak has a line of its own (row 7: ffac9e over x 9 to 12, cooling to both ends). A
  // streak's light is narrow: beside it the red returns two and a half times as fast as beside the bow's white.
  const A80 = (80 * Math.PI) / 180, end = [cx + ridge * Math.cos(A80), y0 - ridge * Math.sin(A80)], sk = q.streak;
  const la = { y: sk.top[1] + 0.5, x: 14, cool: [[6, 9], [7, 3.3], [8, 2.7], [9, 2.1], [10, 1.6], [12, 1.1], [14, 0.8]] };
  const lb = { y: sk.low[1] + 0.5, cool: [[2.6, 9], [3, 3.3], [4, 2.7], [5, 2.1], [6, 1.6], [7, 1.3], [9, 1.0], [12, 1.0], [13, 1.25], [14, 2.2], [15, 6], [15.5, 9]] };
  const sg = [la.x - end[0], la.y - end[1]], sg2 = sg[0] * sg[0] + sg[1] * sg[1];
  const behind = level < 3
    ? (x, y, inWing) => (inWing ? Math.max(xr(lineY) - x, 10.6) : Math.max(xr(y) - x, 0))
    : (x, y) => {
      // (outside the white's line the bow stays white to its edge: the user wanted no red line on the outer arch)
      // (and past the top of its circle the white does not stop at a cut: it cools gradually along the streak, half as fast
      // as elsewhere, so that it merges into the streak's light: the user)
      let d = Math.hypot(0.5 * Math.max(end[0] - x, 0), Math.max(ridge - Math.hypot(x - cx, y - y0), 0));
      const t = S.clamp(((x - end[0]) * sg[0] + (y - end[1]) * sg[1]) / sg2, 0, 1);              // the stretch from the circle's top into the first streak
      d = Math.min(d, 0.8 * t + 1.5 * Math.hypot(x - end[0] - t * sg[0], y - end[1] - t * sg[1]));
      if (x <= la.x) d = Math.min(d, at(la.cool, x) + 2.5 * Math.abs(y - la.y));
      return Math.min(d, at(lb.cool, x) + 2.5 * Math.abs(y - lb.y));
    };
  c.fill(S.subtract(S.polygon(outer), S.polygon(hole)), (px) => {
    const x = px.x, y = y0 - Math.abs(px.y - y0);                         // (the lower half is the upper half's mirror image)
    const inHorn = level < 3 && y < ly0 && x - y >= q.horn + dx, inWing = level < 3 && y < ly0 && !inHorn;
    let col = heat(behind(x, y, inWing));
    // The red along the bow's edges (the game's one red pixel there): full for 0.55 from the edge, gone at 1.05.
    const red = (d) => 1 - B.smooth(0.55, 1.05, d);
    let m = 0;
    const r = Math.hypot(x - cx, y - y0);
    // its outer edge (only the bow's own side of the circle). II: the game leaves the bow's front white to its edge,
    // and red only towards the horns' points
    if (level !== 3 && r <= R + 0.05 && x > cx - 2 && (y >= ly0 || inHorn)) m = red(R - r) * (outerRim ? 1 : B.smooth(50, 85, (Math.atan2(y0 - y, x - cx) * 180) / Math.PI));
    // a horn's inner edge: red at the point, paling towards the line (game: f04d32, ff654b, dd3a1f, then ff917f, ffafa1)
    if (inHorn) m = Math.max(m, red((x - y - q.horn - dx) / Math.SQRT2) * B.smooth(ly0 - 0.3, ly0 - 3, y));
    // the thickening of the line where it runs into the bow: red (game: 7c1200, ab1900, d63318), paling at its end
    if (x > fx) m = Math.max(m, red(Math.max(holeF[px.i], 0)) * B.smooth(fx, fx + 2, x));
    // the arc round the bullet's nose: red beside the nose (game: ff6248, c01d02), paling towards the line
    col = B.mix3(col, rimC, m);
    B.put(px, B.mix3(col, dark, S.clamp((0.13 + px.d) * k + 0.5, 0, 1)));
  });
  B.bullet(c, q.bullet + dx, y0, 1, { band: 'red' });
};

// ---- suppress ------------------------------------------------------------------------------------------------------
// What it is: an arrow pressing down on a bowl that gives way under it, and two thin layers below, arched the other
// way. Plain red in the game (c11e03 throughout; its darker pixels are only edges that cover half a pixel).
// Read off the game's pixels:
//   arrow   stem 5 wide from y 2 to 11; head 13 wide in its first row and two pixels narrower with every row, down to
//           one pixel in row 17: sides at 45 degrees, 7.0 to each side at y 11, the point at y 18.0
//   bowl    upper edge 16.8 at x 1.5, 18.2 at 6.5, 19.65 in the middle: a circle (it sags 2.9 over the width; the game
//           within 0.3 of it); lower edge 20.3 at x 2.5, 21.8 at 5.5, 22.9 at 9.5, 23.0 from 10 to 22
//   layers  upper edge 26.2 at x 3.5, 25.0 at 6.5, 24.0 from 10 to 22; lower edge 26.8 at 4.5, 26.0 in the middle;
//           their ends are points at x 1.6 and 30.4, y 27.3; the second layer is the first, 3 lower
// Changed from the game:
//   The arrow stands on the middle line of the bowl (x 16); in the game it is half a pixel to the left of it.
//   The bowl's lower edge and the first layer's upper edge are cut flat there for twelve pixels, where they would
//   run into one another (a single row of black parts them). Here both are whole arcs: the bowl's through y 23.0 at
//   the middle, a layer's through 0.3 above its flat (so that it keeps the game's thickness half way out, within 0.4);
//   one border's width of black is left between the two.
//   The bowl runs out of the frame at both sides in the game (its ends are cut upright, 2.7 high, one pixel from the
//   frame). Here it is whole: its lower edge is a three-centred arch hung from the two ends of the upper edge: a
//   quarter turn of radius 5 at either end and one flat arc between them (radius 42.5: what follows from the two ends,
//   the depth and the radius 5). That arch is the game's own lower edge to within 0.2 (20.8 at x 3.5, 21.4 at 4.5,
//   22.1 at 7.5), and it carries the edge on round to the end of the upper one, where the bowl comes to a point
//   inside the frame.
const SUPPRESS = {
  stem: 2.5, top: 2, head: 11, half: 7.0,          // the arrow: half its stem's width, its top, where the head begins, the head's half width (and so its height)
  bowl: { ends: [14.6, 16.75], sag: 2.9, deep: 6.25, turn: 5 },    // the ends (from the middle line; y), how far the upper edge sags, how far the lower edge hangs below the ends, the radius of its turn at either end
  layer: { ends: [14.4, 27.3], rise: 3.6, under: 1.3, step: 3 },   // the ends, how far the upper and the lower edge rise above them, the second layer's distance
};
// a three-centred arch hanging from (cx - a, y) and (cx + a, y) down to y + b: its points from the right end to the left
const hangingArch = (cx, y, a, b, r) => {
  const R = (a * a + b * b - 2 * a * r) / (2 * (b - r)), th = (Math.atan2(R - b, a - r) * 180) / Math.PI;
  return [...G.arcPts(cx + a - r, y, r, 0, th, 0.05), ...G.arcPts(cx, y + b - R, R, th, 180 - th, 0.05).slice(1), ...G.arcPts(cx - a + r, y, r, 180 - th, 180, 0.05).slice(1)];
};
const suppress = (c, q = SUPPRESS) => {
  const x = 16, a = q.half;
  const arrow = [[x - q.stem, q.top], [x + q.stem, q.top], [x + q.stem, q.head], [x + a, q.head], [x, q.head + a], [x - a, q.head], [x - q.stem, q.head]];
  const [bx, by] = q.bowl.ends, bowl = [...B.bow([x - bx, by], [x + bx, by], q.bowl.sag), ...hangingArch(x, by, bx, q.bowl.deep, q.bowl.turn).slice(1, -1)];
  const [lx, ly] = q.layer.ends, L = [x - lx, ly], R = [x + lx, ly];
  const layer = [...B.bow(L, R, -q.layer.rise), ...B.bow(R, L, q.layer.under).slice(1, -1)];
  const all = [arrow, bowl, layer, F.moved(layer, 0, q.layer.step)];
  // neighbours: all the black first, then the bodies (the thin points of the layers get a short border: limit 1.5)
  F.borders(c, all, 0.7, 1.5);
  for (const pts of all) F.solid(c, pts, { palette: 'red', border: 0, depth: 0.6 });   // (one depth for all four: the thin layers are as red as the arrow)
};

// ---- slow ------------------------------------------------------------------------------------------------------------
// What it is: the bar of the burst of speed (drawn/flat_sharp.js) in red, stopped by a barrier. A bar 24 high with a
// pointed right end runs from left to right; an upright barrier 2 wide and 28 high stands across it; left of the
// barrier lies one arrowhead of the kind the speed bar carries (a bright line all round a deeper middle), its point
// running in behind the barrier; right of the barrier the bar is dark where it comes out from behind it, and its
// point is the bar's own point.
// Read off the game's pixels (be1b00 is its full red):
//   arrowhead  x 3 to the barrier; a slanted side runs 0.5625 to the right for every one down (x 6.0 in row 5, 9.95
//              in row 12: the same slope as the speed bar's), so its point lies at x 11.9 behind the barrier; its
//              outermost pixel all round is bright (be), the middle 97 to 9d (0.8 of it), and 85 to 91 just inside
//              the slanted line
//   barrier    x 10 to 12, y 2 to 30, plain bright red
//   bar        from x 13; its slanted sides are the arrowhead's, 20 to the right (26.0 in row 5, 29.95 in row 12);
//              along its left side it is black, and the red comes in over three pixels beyond a circle about
//              (-1.8, 16) of radius 17.9 (half way: x 13.9 in row 7, 15.25 in row 10, 16.05 in the middle)
// Changed from the game:
//   There the frame cuts the bar's point off flat (seven pixels high, at x 30). Here the point is whole, and to make
//   room for it everything stands 1.5 to the left.
//   The arrowhead and the bar are one height (y 4 to 28; in the game the arrowhead's outer rows are a third of a
//   pixel thinner). A slit one pixel wide that the game leaves clear between the barrier's and the bar's black is
//   black here.
const SLOW = { shift: -1.5, H: 12, k: 0.5625, base: 3, apex: 11.91, wall: [10, 12, 14], bar: 13, line: 1.0, dark: [-1.8, 17.9] };
const slow = (c, q = SLOW) => {
  const y0 = 16, H = q.H, dx = q.shift, k = q.k;
  const head = (apex, left) => [[left, y0 - H], [apex - H * k, y0 - H], [apex, y0], [apex - H * k, y0 + H], [left, y0 + H]];
  const w0 = q.wall[0] + dx, w1 = q.wall[1] + dx, wall = [[w0, y0 - q.wall[2]], [w1, y0 - q.wall[2]], [w1, y0 + q.wall[2]], [w0, y0 + q.wall[2]]];
  const arrow = head(q.apex + dx, q.base + dx), bar = head(q.apex + 20 + dx, q.bar + dx);
  // the arrowhead as far as it shows (up to the barrier), and its middle: that drawn in by the width of its line
  const reach = (w0 - (q.apex + dx)) / k, seen = [[q.base + dx, y0 - H], [q.apex + dx - H * k, y0 - H], [w0, y0 + reach], [w0, y0 - reach], [q.apex + dx - H * k, y0 + H], [q.base + dx, y0 + H]];
  const middle = G.offsetPts(seen, -q.line);
  F.borders(c, [arrow, wall, bar], 0.7);
  // arrowhead and barrier are one bright piece (its colour deepens only along the outline of the two together)
  const st = { depth: 0.45 }, both = S.union(S.polygon(arrow), S.polygon(wall));
  c.fill(both, F.deepening(c.k, 'red', st));
  F.solid(c, middle, { palette: { rim: '#a01206', edge: '#a01206', body: '#b81509' }, border: 0, depth: 0.7, rim: 0 });
  // the bar: red, black where it comes out from behind the barrier
  const red = F.deepening(c.k, 'red', st), black = P.hex(C.black), cx = q.dark[0] + dx, R = q.dark[1];
  c.fill(S.polygon(bar), (px) => {
    red(px);
    const t = S.clamp((Math.hypot(px.x - cx, px.y - y0) - R + 1.3) / 2.8, 0, 1), s = 1 - t * t * (3 - 2 * t);
    const mixLin = (a, b) => P.toSRGB(P.toLinear(a) + (P.toLinear(b) - P.toLinear(a)) * s);
    px.r = mixLin(px.r, black[0]); px.g = mixLin(px.g, black[1]); px.b = mixLin(px.b, black[2]);
  });
};

// ---- power attack ----------------------------------------------------------------------------------------------------
// The dark sword (parts/flat_sharp_b.js) pointing up to the right, with I a red line round it, II a red swing behind
// its point, III flames.
// The frame of all three: the sword lies on the diagonal x + y = 31.3, grip's end at (4.08, 27.22), point at
// (25.01, 6.29). Changed from the game: there the sword leans 2.8 degrees off that diagonal (its grip's end stands at
// x + y = 32.35, its point at 30.3), while the line, the swing and the flames are all built about the diagonal
// (their upper edges level, their right edges upright). Here the sword lies ON the diagonal, so that what is drawn
// round it is centred on it and keeps its level and upright edges.
const PA = { E: [4.08, 27.22], deg: -45 };
const paFrame = () => G.frameAt(PA.E, PA.deg, B.DARK_SWORD.L);

// I: one red line, one pixel wide, round the sword: beside the guard's ends, a step in, up along the blade, round the
// point in a gable (its peak on the sword's line, its sides level and upright), and down the other side the same.
// Read off the game's pixels: the line's middle 4 pixels across from the sword's (2.83; here 2.85 as in two-weapon
// fighting II); the gable's outer corner in the corner of pixel (26, 4), so the middle line's peak 31.8 from the
// grip's end; the steps 3.35 beyond the guard's middle; beside the guard 5.65 out; the ends level with the guard's
// far edge. Its ends are cut square (in the game each has one faint pixel more on its inner side).
// All that the line encloses is black, as in the game.
const PA_LINE = { A: 2.85, hw: 0.5, peak: 31.8, step: 10.55, out: 5.65, end: 6.8 };
const outlinedSword = (c, q = PA_LINE) => {
  const f = paFrame(), tA = q.peak - q.A;
  const sharp = f.pts([[q.end, -q.out], [q.step, -q.out], [q.step, -q.A], [tA, -q.A], [q.peak, 0], [tA, q.A], [q.step, q.A], [q.step, q.out], [q.end, q.out]]);
  const line = G.filletLine(sharp, 1.1, [1, 2, 6, 7]);              // the steps round the guard are rounded (the user)
  c.fill(S.polygon(G.strokePts(line, q.hw + 0.7, { lengthen: 0.7 }), undefined, 'nonzero'), P.flat(C.black));
  c.fill(S.polygon(sharp), P.flat(C.black));
  B.darkSword(c, f, 'black');
  c.fill(S.polygon(G.strokePts(line, q.hw), undefined, 'nonzero'), F.deepening(c.k, 'red', { depth: 0.35 }));
  B.darkSword(c, f, 'red');
};

// II: the swing: a red blade bent round the sword's point, coming to a point at its corner and at each end.
// Read off the game's pixels, in the frame of the diagonal (t along it from the sword's grip end, s across):
//   its corner (the outer corner of pixel (26, 4)) on the diagonal at t 32.63, 3.0 beyond the sword's point;
//   its two ends at t 9.93, 10.1 to either side;
//   its outer edges: the game's edge pixels lie within 0.4 of a circle that leaves each end along the diagonal's
//   direction and runs to the corner (radius 30.6; it bows 2.64 out from the straight line end to corner, and
//   arrives at the corner at 47 degrees to the diagonal: that is the game's level upper and upright right edge);
//   its inner edges: circles from each end to a point on the diagonal at t 26.77 (hidden under the sword), bowed out
//   by 1.2 (through s 3.6 at t 22.6, 5.75 at 19.6, 7.6 at 16.2, 9.1 at 12.0: the two arms' edges averaged).
// The game's swing is not quite centred on its own corner (the lower arm stands 0.4 further out than the upper one):
// here both arms are mirror images.
const PA_SWING = { corner: 32.63, ends: [9.93, 10.1], inner: 26.77, sag: 2.64, sagIn: 1.2 };
const swingPts = (f, q = PA_SWING) => {
  const top = f.pt(q.corner, 0), L = f.pt(q.ends[0], -q.ends[1]), R = f.pt(q.ends[0], q.ends[1]), low = f.pt(q.inner, 0), mid = f.pt(q.ends[0] + 4, 0);
  return [...B.bowFrom(L, top, q.sag, mid), ...B.bowFrom(top, R, q.sag, mid).slice(1), ...B.bowFrom(R, low, q.sagIn, mid).slice(1), ...B.bowFrom(low, L, q.sagIn, mid).slice(1, -1)];
};
const swungSword = (c) => {
  const f = paFrame(), swing = swingPts(f);
  F.solid(c, swing, { palette: 'red' });
  B.darkSword(c, f);
};

// III: flames: the swing grown to a sheet of fire behind the sword, its corner 1.4 further out (the outer corner of
// pixel (27, 3)), with three tongues trailing from each side. In the game the two sides are mirror images about the
// diagonal within a pixel or two; here they are exact mirror images, each feature the mean of its two sides.
// One side, in the frame of the diagonal (t along it from the sword's grip end, s across), read off the game's pixels:
//   the outer edge runs straight from the corner (t 34.04) at 45 degrees (the game's level upper and upright right
//   edge, 11 pixels long) to t 26.3, then draws in a little to the point of the first tongue at t 19.35, s 13.27
//   (left 19.0, 13.8; right 19.7, 12.7): a thin spike along the edge, 1.75 thick at its root;
//   a notch runs in behind it to t 23.2, where the swing's outer circle begins: that circle is this side's edge down
//   to the swing's own end at t 9.93, s 10.1, which is the point of the second tongue (in the game the lower arm
//   of II and the right flame of III share their edge pixel for pixel);
//   a thin crack runs in behind the second tongue to t 13.4, s 8.1 (left 12.8, 8.3; right 14.0, 7.9);
//   the third tongue hangs from there towards the grip, bowed out, to its point at t 4.72, s 4.64 (left 4.55, 3.96;
//   right 4.9, 5.31), 1.4 thick in its middle; its inner edge runs back up to t 11.6, s 4.9, and from there the
//   sheet's inner edge runs at 45 degrees (level on the left at y 16, upright on the right at x 16.15 in the game:
//   t + s = 15.9 and 17.1; here 16.5 on both sides) in to the black of the sword at t 14.2.
const PA_FLAME = { corner: 34.04, straight: 26.3, first: [19.35, 13.27], draw: 0.25, notch: 23.2, crack: [13.4, 8.1], third: [4.72, 4.64], out: 0.75, back: [11.6, 4.9], outIn: 0.47, join: [14.2, 2.3] };
const flamePts = (f, q = PA_FLAME, sw = PA_SWING) => {
  const R = (sw.ends[1] * sw.ends[1] + (sw.corner - sw.ends[0]) * (sw.corner - sw.ends[0])) / (2 * sw.ends[1]), cs = sw.ends[1] - R;   // the swing's outer circle: about (its end's t, cs)
  const deg = (t, s) => (Math.atan2(s - cs, t - sw.ends[0]) * 180) / Math.PI, onCircle = (t) => cs + Math.sqrt(R * R - (t - sw.ends[0]) * (t - sw.ends[0]));
  const p1 = [q.straight, q.corner - q.straight], p3 = [q.notch, onCircle(q.notch)], p4 = [sw.ends[0], sw.ends[1]], axis = (t) => [t, 0];
  const inner = [...B.bowFrom(q.third, q.back, q.outIn, axis(8)), q.join];                 // the third tongue's inner edge and the 45 degree edge
  const half = [[q.corner, 0], ...B.bowFrom(p1, q.first, q.draw, axis(22)), p3,
    ...G.arcPts(sw.ends[0], cs, R, deg(p3[0], p3[1]), 90).slice(1), q.crack,
    ...B.bowFrom(q.crack, q.third, q.out, axis(9)).slice(1), ...inner.slice(1), [q.join[0], 0]];
  const flip = (list) => list.map(([t, s]) => [t, -s]).reverse();
  // The black the sword stands on: in the game the black between the two third tongues is whole down to the straight
  // line from point to point (as all that the line of I encloses is black).
  return { flame: f.pts(half.concat(flip(half.slice(1, -1)))), ground: f.pts(inner.concat(flip(inner))) };
};
const flamingSword = (c) => {
  const f = paFrame(), { flame, ground } = flamePts(f);
  F.borders(c, [flame, ground], 0.7);
  F.solid(c, flame, { palette: 'red', border: 0 });
  B.darkSword(c, f);
};

module.exports = {
  i_pshot01(c) { blast(c, 1); },
  i_pshot02(c) { blast(c, 2); },
  i_pshot03(c) { blast(c, 3); },
  i_pattack01(c) { outlinedSword(c); },
  i_pattack02(c) { swungSword(c); },
  i_pattack03(c) { flamingSword(c); },
  ip_slow(c) { slow(c); },
  ip_surpress(c) { suppress(c); },

  i_rshot01(c) { B.bullets(c, [[8, 10, 1], [8, 21, 1]]); },
  i_rshot02(c) { B.bullets(c, [[10, 8, SMALL], [14, 16, SMALL], [10, 24, SMALL]]); },
  i_rshot03(c) { B.bullets(c, [[3, 8], [16, 8], [7, 16], [20, 16], [3, 24], [16, 24]].map(([x, y]) => [x, y, SMALL])); },
};
