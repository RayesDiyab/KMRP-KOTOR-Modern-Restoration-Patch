'use strict';
// Constructed drawings of the flat sharp symbols (the combat icons). Nothing here is traced: every outline is built
// from measured dimensions out of straight lines and circular arcs (tools/swords.py prints a sword's axis, its
// outline's corners and the colours across it), borders are the same outlines moved out with sharp corners, and the
// shading is formulas in each object's own frame. Only what the game's icon and its redraw show is drawn.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const W = require('../parts/weapons');
const F = require('../parts/flat');

const shifted = (p, d) => [p[0] + d[0], p[1] + d[1]];

// ---- the blue sword ------------------------------------------------------------------------------------------------
// In the game it is a blue blade with a line of light down its middle, brightest (white) where it crosses the guard.
// Measured on the redraw: grip 2.0 wide ending in a point 1.25 long; guard 6.8 long, its middle 8.05 from the grip's
// end, 1.4 thick, its ends coming to points like the grip's and the blade's; blade 2.15 wide, point 1.4 long.
// The light stops 2.2 short of the tip and 2.2 short of the grip's end (the same at both, by the user's rule); on the
// guard it is a thin line. The sword is one body: no line separates the guard from the blade and the grip.
const BLUE_SWORD = { pommel: 1.25, grip: 2.0, guardAt: 8.05, guard: 6.8, guardT: 1.4, guardPoint: 0.75, blade: 2.15, taper: 1.4 };
const blueSword = (c, E, T, o = BLUE_SWORD, st = {}) => W.glowSword(c, E, T, o, { palette: 'blue', side: -1, ...st });
// several swords together: all their black borders first, then the swords in the order given (the last lies on top)
const swords = (c, list) => { for (const part of ['border', 'body']) for (const [E, T, o, st] of list) W.glowSword(c, E, T, o, { ...st, part }); };

// ---- the outlined pair (two-weapon fighting II and III) ---------------------------------------------------------
// Two blue swords, the second the first moved by (6, 5), and ONE neon line round both: it starts beside the first
// sword's guard, steps in to run up the blade's left side, turns round the point in a gable (its peak on the sword's
// axis, sides at 45 degrees), comes down between the swords, turns back up in a square hairpin, goes round the second
// point the same way, comes down the second blade's right side and steps out round that guard. (The user's corrected
// source and the game's icon; the line's middle stands 2.85 from each sword's axis, as in the game: 4 pixels across.)
// The line is drawn like the swords (the user: "more similiar to the sword look blue with a white glow"): a blue
// body 1.5 wide with a white line down its middle. Similar to the swords, not the same (their word): the white line
// is 0.5 wide, bolder than a blade's 0.34, so that the outline still reads as light and the swords as swords.
const PAIR_LINE = { A: 2.85, hw: 0.75, core: 0.25, halo: 0.24, white: 0.42, peak: 3.0, step: 1.45, out: 5.2, tail: 2.0, hairpin: 4.0 };
// A circular arc from p to q that bows out from their chord by `sag` (to the right of the direction p to q as seen on
// screen; negative: to the left): its points, p and q included.
const bow = (p, q, sag) => {
  const f = G.frame(p, q), h = f.L / 2, R = (h * h + sag * sag) / (2 * Math.abs(sag)), side = sag > 0 ? 1 : -1;
  const ctr = f.pt(h, -side * (R - Math.abs(sag))), deg = (v) => (Math.atan2(v[1] - ctr[1], v[0] - ctr[0]) * 180) / Math.PI;
  let a0 = deg(p), a1 = deg(q);
  if (side > 0) { while (a1 > a0) a1 -= 360; } else { while (a1 < a0) a1 += 360; }
  return G.arcPts(ctr[0], ctr[1], R, a0, a1);
};

// The swing of two-weapon fighting III: a blade of light bent over the points of the two swords, coming to a point at
// each end AND at its top (the user: "The swing top needs to be more pointed not flat", then "its not centered"; in
// the game the frame cuts it flat along the top and the right, which they did not want either).
// It is symmetric about the middle line between the two swords, and given in that line's frame (t along it from the
// middle of the two grip ends, s across): its ends at t 19.0, s -13.3 and +13.3; its top on the line at t 33.8; the
// two outer edges circular arcs from an end to the top, bowed out by 1.6; the inner edge a circle about the point
// t 9.5 on the line through both ends (r 16.3: it passes x 27 at y 15 as the game's icon does).
const SWING = { ends: [19.0, 13.3], top: 33.8, sag: 1.6, inner: 9.5 };
const swingPts = (f, q = SWING) => {
  const left = f.pt(q.ends[0], -q.ends[1]), right = f.pt(q.ends[0], q.ends[1]), top = f.pt(q.top, 0), ctr = f.pt(q.inner, 0);
  const r = Math.hypot(left[0] - ctr[0], left[1] - ctr[1]), deg = (v) => (Math.atan2(v[1] - ctr[1], v[0] - ctr[0]) * 180) / Math.PI;
  let b0 = deg(right), b1 = deg(left); if (b1 > b0) b1 -= 360;
  return [...bow(left, top, -q.sag), ...bow(top, right, -q.sag).slice(1), ...G.arcPts(ctr[0], ctr[1], r, b0, b1).slice(1, -1)];
};

// swung: with the swing over the points. Then the swing and the neon line are ONE white piece: the
// crescent fills everything outside the line's middle, the points of the swords stay in view inside the line, and the
// colour deepens only along the outer edge of the two together (no edge runs between them).
const outlinedPair = (c, { E = [2.05, 25.0], deg = -47.9, L = 29.6, d = [6, 5], o = BLUE_SWORD, q = PAIR_LINE, swung = false } = {}) => {
  const f1 = G.frameAt(E, deg, L), f2 = G.frameAt(shifted(E, d), deg, L);
  const swing = swung ? swingPts(G.frameAt([E[0] + d[0] / 2, E[1] + d[1] / 2], deg, L)) : null;
  const gm = o.guardAt, g1 = gm + o.guardT / 2, ds = d[0] * f1.n[0] + d[1] * f1.n[1];
  const top = L + q.peak, tA = top - q.A, tS = g1 + q.step, tH = gm + q.hairpin;
  let line = [f1.pt(gm - q.tail, -q.out), f1.pt(tS, -q.out), f1.pt(tS, -q.A), f1.pt(tA, -q.A), f1.pt(top, 0), f1.pt(tA, q.A), f1.pt(tH, q.A), f1.pt(tH - (ds - 2 * q.A) / 2, ds / 2),   // (the turn between the swords is a point like the tops, not a square U: the user)
    f1.pt(tH, ds - q.A), f2.pt(tA, -q.A), f2.pt(top, 0), f2.pt(tA, q.A), f2.pt(tS, q.A), f2.pt(tS, q.out), f2.pt(gm - q.tail, q.out)];
  const inside = S.polygon(line.slice(2, 13));
  // (the outer corner of each step a wide round, the inner one a small one; the line's two ends pointed: the user)
  line = G.filletLine(line, 0, { 1: [1.9, 0.72], 2: [0.6, 0.28], 12: [0.6, 0.28], 13: [1.9, 0.72] }); line.point = true;
  // a blue hue between the line and the swords (the user): strongest beside the line, gone 1.6 from it; measured from
  // the line itself, so that nothing shows along the open side behind the guards
  const hueF = c.field(S.polygon(G.strokePts(line, q.hw), undefined, 'nonzero')), hue0 = P.hex('#0a0a0c'), hue1 = P.hex('#2450e6');
  // (it is LIGHT, not paint: the line's own glow on the dark, brightest against the line and dying away smoothly)
  // A THIN glow hugging the line on both its sides and all round the pointed turn (the user): blue light on the black,
  // brightest against the line, gone half a unit from it.
  const around = S.polygon(G.strokePts(line, q.hw + 0.7, { lengthen: 0.7 }), undefined, 'nonzero');
  // The line as a LIGHTSABER's glow (the user): a white-hot core, and round it blue light that is strongest against the
  // core and dies away softly with no edge of its own (a tight bright fall and a wider faint one), on black.
  const coreHw = 0.24, coreF = c.field(S.polygon(G.strokePts(line, coreHw), undefined, 'nonzero')), wide = S.polygon(G.strokePts(line, q.hw + 1.5, { lengthen: 1.5 }), undefined, 'nonzero');
  const hue = () => {
    c.fill(inside, P.flat(C.black));
    c.fill(wide, (px) => { const d = Math.max(coreF[px.i], 0), w = Math.min(d / 0.28, 1), m = w * w * (3 - 2 * w);
      px.r = 1 + (hue1[0] - 1) * m; px.g = 1 + (hue1[1] - 1) * m; px.b = 1 + (hue1[2] - 1) * m; px.a = Math.min(1, 0.95 * Math.exp(-(d * d) / (0.7 * 0.7)) + 0.3 * Math.exp(-d / 0.6) + (d <= 0 ? 1 : 0)); });
  };
  // The swords' black borders first, then the glow over them: inside the line the glow reaches the swords themselves,
  // with no black between (a glow like the speed chevrons': saturated blue, brightest at the line, dying away smoothly).
  const lit = { palette: 'blue', side: -1, core: 0.24, coreEnd: 1.6 };   // (the swords' line of light a bit thicker and longer here, still short of both ends: the user)
  const pair = [[f1.E, f1.T, o, lit], [f2.E, f2.T, o, lit]];
  for (const [E, T, oo, st] of pair) W.glowSword(c, E, T, oo, { ...st, part: 'border' });
  // In the game the line is white round the points and turns to a deeper blue on its way down to the guards (rows 1 to 6
  // W, then b, then B): the same here, a blue laid over the line that grows from nothing 9 below the tops to its full
  // strength at the steps.
  const deepen = () => {};
  if (!swing) {
    W.tube(c, line, q.hw, { palette: 'blue', border: 0.7, core: q.core, halo: q.halo, look: 'body', part: 'border' });
    hue();

  } else {
    c.fill(S.polygon(G.offsetPts(swing, 0.7)), P.flat(C.black));
    W.tube(c, line, q.hw, { palette: 'blue', border: 0.7, core: q.core, part: 'border' });
    hue();

    // the white piece: the swing outside the line's middle, and the line itself as far as it lies within the swing
    const lineShape = S.polygon(G.strokePts(line, q.hw), undefined, 'nonzero'), lf = c.field(lineShape);
    const sw = S.polygon(swing), both = S.union(S.subtract(sw, inside), S.intersect(lineShape, sw)), edge = P.byDepth(q.hw - q.white, W.TUBE.blue);
    // Where the line runs in under the swing the two CONNECT (the user: "Remove the border from swing with rest of
    // outline it should connect"): the swing's own deepening edge is left out along the line's white middle and its
    // glow, so the line's light runs on into the white without a break.
    c.fill(both, (px) => {
      edge(px);
      const d = lf[px.i];
      if (d < 0) { const m = Math.max(q.hw + d - q.core, 0) / q.halo, w = Math.exp(-m * m); px.r += (1 - px.r) * w; px.g += (1 - px.g) * w; px.b += (1 - px.b) * w; }
    });
  }
  deepen();
  for (const [E, T, oo, st] of pair) W.glowSword(c, E, T, oo, { ...st, part: 'body' });
  return { f1, f2, line };
};

// ---- the red sword that glows (flurry) ---------------------------------------------------------------------------
const HOT = { rim: '#5e0703', edge: '#b01408', body: '#e22a16', lit: '#f04430', glow: '#ffd2c8', gripFar: '#c80e08', guardEdge: '#e0140c', core: '#ffffff', coreEnd: '#ffd0c6' };

// ---- lightning bolts -----------------------------------------------------------------------------------------------
// The GAME's bolt, read off its pixels (tools/vmap.py; the redraw's bolts are 1.7 times as wide and lean, and the user
// wants the game's simple shapes): an upright block that draws in from the right as it goes down, a bar across its
// foot that stands out to the right and ends blunt, two units high, and under the bar's right half a spike that
// comes to a point a little to the left. Eight straight edges:
//   x0, x1: the block's left and right at the top;  top: its y;  inner: where the block's right side meets the bar;
//   bar: the bar's top and bottom y;  out: how far right it reaches;  waist: where the block's left side ends (y);
//   spike: the spike's upper left corner;  tip: its point
const bolt = (b) => [[b.x0, b.top], [b.x0, b.waist], b.spike, b.tip, [b.out, b.bar[1]], [b.out, b.bar[0]], [b.inner, b.bar[0]], [b.x1, b.top]];
const SHOCK = { x0: 14, x1: 18, top: 6.2, inner: 16, bar: [16, 18], out: 19, waist: 16.8, spike: [17, 18.2], tip: [16.6, 25.3] };
const TWIN = { x0: 9, x1: 14, top: 5.2, inner: 12, bar: [15, 17], out: 15, waist: 16.0, spike: [11, 17.3], tip: [10.4, 26.2] };
const STORM = [
  { x0: 3, x1: 7, top: 4.2, inner: 7, bar: [15, 17], out: 10, waist: 16.2, spike: [7, 18.3], tip: [7.9, 26.2] },
  { x0: 12, x1: 17, top: 2.2, inner: 16, bar: [15, 17], out: 20, waist: 16.6, spike: [16, 18.3], tip: [17.4, 30.2] },
  { x0: 23, x1: 27.5, top: 4.2, inner: 26, bar: [14, 16], out: 29, waist: 15.4, spike: [25, 16.6], tip: [24.4, 25.2] },
];

// ---- the jump arrows -----------------------------------------------------------------------------------------------
// An arrow pointing up: a head with sides at 45 degrees and a stem, symmetric. apex: its point; half: the head's
// half-width (and so its height); stem: the stem's half-width; len: the stem's length
const arrowUp = (apex, half, stem, len) => {
  const [x, y] = apex, yb = y + half;
  return [[x, y], [x + half, yb], [x + stem, yb], [x + stem, yb + len], [x - stem, yb + len], [x - stem, yb], [x - half, yb]];
};
// The jump: a white arrow in front of the same arrow in blue, standing `drop` lower. One black border round the two.
const jump = (c, apex, half, stem, len, drop) => {
  const white = arrowUp(apex, half, stem, len), blue = arrowUp([apex[0], apex[1] + drop], half, stem, len);
  F.borders(c, [white, blue], 0.7);
  F.solid(c, blue, { palette: 'blue', border: 0 });
  F.solid(c, white, { palette: 'white', border: 0, depth: 0.6 });
};

// ---- the thrown lightsaber -------------------------------------------------------------------------------------------
// What it is (the user: "A sword of light with a glow gradient next to"): the sword is the WHITE: a blade of light
// standing at 45 degrees along the right edge, a guard across it near the lower end and the handle below; the red
// field to its left is its glow, brightest beside the blade and deepening away from it in straight bands. In the
// game: the white line along the right edge of a salmon bar, a paler band across it where the guard is (its ends
// upright), and the part under the band set 2.5 to the right.
//   at: the field's upper left corner; w: its width; up: its height down to the guard; low: the height below the
//   guard; guard: the thickness of the guard's white (the same along its whole length, and thinner than the blade
//   and the handle: the user's corrections);
//   out: how far the guard stands out beyond the field at each side; narrow: how much the lower field is drawn in
//   at the left; blade: the blade's width; thin: a fine line of light inside the field's other edges
const SABER = { rim: '#5e0703', edge: '#b01a16', body: '#d8302c', glow: '#ff9a90' };
const saber = (c, at, w, up, low, st = {}) => {
  const [x, y] = at, pick = (v, d) => (v === undefined ? d : v);
  const guard = pick(st.guard, 0.6), out = pick(st.out, 1.5), narrow = pick(st.narrow, 0),   /* 0: the part under the guard is as wide as the part above it (the user) */ edge = pick(st.edge, 0.3), thin = pick(st.thin, 0.22), blade = pick(st.blade, 1.1);
  // (the guard's part of the outline is its white plus the red edge above and below it)
  const yg = y + up, yh = yg + guard + 2 * edge, yb = yh + low, lx = (yy) => x - (yy - y);        // lx: the field's left edge at a level
  const all = [[x, y], [x + w, y], [lx(yg) + w, yg], [lx(yg) + w + out, yg], [lx(yh) + w + out, yh], [lx(yh) + w, yh], [lx(yb) + w, yb],
    [lx(yb) + narrow, yb], [lx(yh) + narrow, yh], [lx(yh) - out, yh], [lx(yg) - out, yg], [lx(yg), yg]];
  const border = pick(st.border, 0.7);
  if (border > 0 && st.part !== 'body') c.fill(S.polygon(G.offsetPts(all, border)), P.flat(C.black));
  if (st.part === 'border') return;
  const shape = S.polygon(all), room = S.polygon(G.offsetPts(all, -edge));
  // the sword: the blade inside the right edge of the field, on down inside the right edge of the lower field as the
  // handle, and the guard across
  const m = edge + blade / 2, d = m * Math.SQRT2;                 // a line at 45 degrees stands d further left at the same level
  const sword = S.intersect(S.union(
    S.polygon(G.strokePts([[x + w - d + 2, y - 2], [lx(yg) + w - d - 1, yg + 1]], blade / 2)),
    S.polygon(G.strokePts([[lx(yh) + w - d + 1, yh - 1], [lx(yb) + w - d - 2, yb + 2]], blade / 2)),
    S.box((lx(yg) + lx(yh) + w) / 2, (yg + yh) / 2, w / 2 + out + 1, guard / 2)), room);
  // the glow: brightest beside the blade, deepening away from it in straight bands (measured from the blade's line,
  // not from the guard or the handle, round which it would bend: the user saw it "rounded around the handles")
  const k = c.k, lin = (h) => P.hex(h).map(P.toLinear), cr = lin(SABER.rim), ce = lin(SABER.edge), cb = lin(SABER.body), cg = lin(SABER.glow);
  const mix3 = (p0, p1, t) => [p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, p0[2] + (p1[2] - p0[2]) * t], sm = (e0, e1, v) => { const t = S.clamp((v - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
  const reach = pick(st.reach, (w / Math.SQRT2) * 0.8), onLine = x + w + y;
  c.fill(shape, (px) => {
    let v = mix3(cg, mix3(cb, ce, 0.5), sm(0, reach, (onLine - (px.x + px.y)) / Math.SQRT2 - (edge + blade)));
    v = mix3(v, cr, S.clamp((0.13 + px.d) * k + 0.5, 0, 1));
    px.r = P.toSRGB(v[0]); px.g = P.toSRGB(v[1]); px.b = P.toSRGB(v[2]); px.a = 1;
  });
  if (thin > 0) c.fill(S.inner(shape, edge, edge + thin), P.flat('#ffd9d2', 0.85));
  c.fill(sword, P.byDepth(0.16, [[0, '#ffb9ae'], [1, '#ffffff']]));
};

// ---- the speed chevrons --------------------------------------------------------------------------------------------
// The game's design, read off its pixels: white chevrons flying right. Each has a SHARP leading edge and, behind it
// (to the left), a trail that fades from the white through grey into dark; a dark band stands round the whole, and a
// blue glow outside that. (The redraw turned the trail into an even halo all round and squared the ends: not followed.)
// The chevron's shape in the game, from its point: the outer edges run back to the two ends at (-7.6, -11) and
// (-7.6, 11); the inner edges from the notch at (-5.2, 0) back to corners at (-9.2, -5.5) and (-9.2, 5.5); each end
// is cut from its corner to its point. The small ones of the master's icon are the same shape at 0.48.
const CHEVRON = { end: [-7.6, 11], corner: [-9.2, 5.5], notch: -5.2 };
const chevron = (tip, k = 1, trail = 0) => {
  const [x, y] = tip, ex = CHEVRON.end[0] * k, ey = CHEVRON.end[1] * k, bx = CHEVRON.corner[0] * k, by = CHEVRON.corner[1] * k, n = CHEVRON.notch * k;
  // with a trail: the same outline with its back carried `trail` to the left (the chevron and everything it leaves behind)
  return trail ? [[x + ex, y - ey], [x, y], [x + ex, y + ey], [x + ex - trail, y + ey], [x + bx - trail, y + by], [x + n - trail, y], [x + bx - trail, y - by], [x + ex - trail, y - ey]]
    : [[x + ex, y - ey], [x, y], [x + ex, y + ey], [x + bx, y + by], [x + n, y], [x + bx, y - by]];
};
// how far a place lies behind the chevron's back edge, measured level
const behind = (tip, k, x, y) => {
  const v = Math.abs(y - tip[1]) / k, [ex, ey] = CHEVRON.end, [bx, by] = CHEVRON.corner, n = CHEVRON.notch;
  const back = v <= by ? n + ((bx - n) * v) / by : bx + ((ex - bx) * (v - by)) / (ey - by);
  return tip[0] + back * k - x;
};
// o: trail (its length), dark (the width of the dark band), glow (the reach of the blue outside it)
const speed = (c, tips, k, o) => {
  const around = tips.map((t) => S.polygon(G.offsetPts(chevron(t, k, o.trail), o.dark, 1.8)));
  c.glow(S.union(...around), '#2450e6', o.glow, 0.8);
  for (const a of around) c.fill(a, P.flat('#0c1126'));              // all the dark bands first: none cuts into a neighbour
  const fade = P.ramp([[0, '#eceef3'], [0.22, '#cbced9'], [0.5, '#868ca2'], [0.78, '#474e67'], [1, '#191d2f']]);
  for (const t of tips) {
    c.fill(S.polygon(chevron(t, k, o.trail)), (px) => { fade(S.clamp(behind(t, k, px.x, px.y) / o.trail, 0, 1), px); px.a = 1; });
    c.fill(S.polygon(chevron(t, k)), P.flat('#ffffff'));
  }
};

// ---- the burst of speed --------------------------------------------------------------------------------------------
// The game's design (the user: "more similiar to vanilla not chatgpt"): ONE blue bar with a pointed right end, and
// in it three arrowheads one behind the other: each a white line (an upright base and two slanted sides) round a pale
// middle, its point running in behind the next one's base; the last one's point is the bar's own point. The blue
// between them is light, deeper beside the white; at the left the trail of the first one is a deep blue arrowhead of
// the same shape without a line, darkest where it runs in behind the first base.
// Read off the game's pixels: bar 24 high (y 4 to 28); bases 8 apart, their lines 1 wide; a slanted side runs 0.5625
// to the right for every one down, from 13.13 above the middle (so the bar's edge cuts the arrowheads' barbs: their
// white ends flat, 1 inside the edge) to a point 7.4 in front of the base; the blue outside the last side 0.6 wide.
// Changed from the game: there the frame cuts the point off flat (six pixels high). Here the point is whole, and to
// make room for it the plain blue at the left is 5 wide instead of 6.
const BURST = { left: 0.85, blk: 5, pitch: 8, H: 12, inset: 1, line: 1.0, top: 13.13, depth: 7.4, tipRim: 0.6, trail: 7.2 };
const burst = (c, q = BURST) => {
  const y0 = 16, hw = q.line / 2, k = q.depth / q.top, hx = hw * Math.hypot(1, k);      // hx: a slanted line's half-width measured level
  const bases = [0, 1, 2].map((i) => q.left + q.blk + i * q.pitch);
  const tip = bases[2] + 0.5 + q.depth + hx + q.tipRim * Math.hypot(1, k), xr = tip - q.H * k;
  const bar = [[q.left, y0 - q.H], [xr, y0 - q.H], [tip, y0], [xr, y0 + q.H], [q.left, y0 + q.H]], barShape = S.polygon(bar);
  const band = S.box(16, y0, 40, q.H - q.inset);                    // where white may be: one unit inside the bar's long edges
  const tris = bases.map((x) => [[x + 0.5, y0 - q.top], [x + 0.5 + q.depth, y0], [x + 0.5, y0 + q.top]]);
  // an arrowhead's white: its base, its two slanted sides, and its flat ends (the barbs the bar's edge cuts) closed by
  // a line of the same width: one white line all round
  const middle = S.box(16, y0, 40, q.H - q.inset - q.line);
  const whites = tris.map((t, i) => S.intersect(S.union(S.polygon(G.strokePts(t, hw, { limit: 4 })), S.box(bases[i] + 0.5, y0, hw, q.H), S.subtract(S.polygon(t), middle)), band));
  const apex = bases[0] - q.trail + 0.5 + q.depth + hx;             // the trail: the outline of an arrowhead standing `trail` further back
  const trail = S.polygon([[apex - 14 * k, y0 - 14], [apex, y0], [apex - 14 * k, y0 + 14], [q.left - 6, y0 + 14], [q.left - 6, y0 - 14]]);
  const bf = c.field(barShape), wf = c.field(S.union(...whites)), kk = c.k;
  const lin = (h) => P.hex(h).map(P.toLinear), mix3 = (p0, p1, t) => [p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, p0[2] + (p1[2] - p0[2]) * t];
  const sm = (e0, e1, v) => { const t = S.clamp((v - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }, put = (px, v) => { px.r = P.toSRGB(v[0]); px.g = P.toSRGB(v[1]); px.b = P.toSRGB(v[2]); px.a = 1; };
  const col = { rim: lin('#0b1c86'), edge: lin('#0531dc'), lit: lin('#3b63ff'), near: lin('#3760ff'), gap: lin('#7793ff'), trail: lin('#012dd8'), dark: lin('#00040f'), pale: lin('#d6deff'), paleEdge: lin('#b0c0ff') };
  c.fill(S.polygon(G.offsetPts(bar, 0.7)), P.flat(C.black));
  // everything inside the bar is drawn whole on a sheet of its own, and the bar's outline cuts it once
  c.layer((t) => {
    const all = S.box(16, 16, 20, 20), toWhite = (px) => Math.max(wf[px.i], 0);
    t.fill(all, (px) => put(px, mix3(col.near, col.gap, sm(0, 1.3, toWhite(px)))));
    t.fill(trail, (px) => put(px, mix3(col.trail, col.dark, sm(1.15, 0.25, bases[0] - px.x))));
    // the bar deepens to its edge (less so beside white, whose light reaches it), with a thin dark line along it
    t.fill(all, (px) => {
      const depth = -bf[px.i];
      const e = mix3(col.lit, col.edge, sm(0, 1.4, toWhite(px)));
      px.r = P.toSRGB(e[0]); px.g = P.toSRGB(e[1]); px.b = P.toSRGB(e[2]); px.a = 1 - sm(0, 0.9, depth);
    });
    t.fill(all, (px) => { px.r = P.toSRGB(col.rim[0]); px.g = P.toSRGB(col.rim[1]); px.b = P.toSRGB(col.rim[2]); px.a = S.clamp((0.13 + bf[px.i]) * kk + 0.5, 0, 1); });
    tris.forEach((tri, i) => {
      t.fill(S.intersect(S.polygon(tri), band), (px) => put(px, mix3(col.paleEdge, col.pale, sm(0, 1.4, toWhite(px)))));
      t.fill(whites[i], P.flat('#ffffff'));
    });
  }, { mask: barShape });
};

// ---- the critical strike ---------------------------------------------------------------------------------------------
// Two bars crossed on the diagonals, as in the game; the square in which they cross is dark, so that four arms of
// light stand out from it. Each arm is a bar with its outer corners cut. In the first icon an arm glows from red at
// the crossing through pink to white at its end (in the game: red to 7 from the middle, pink at 9.5, white from 10.8);
// in the second the arms are white and stand on a red field.
// ctr: the middle; r0: where an arm begins (half the bars' width or a little more); r1: where it ends; hw: its
// half-width; cut: how much of each outer corner is cut off
const strike = (c, ctr, r0, r1, hw, cut, fill) => {
  const arms = [45, 135, 225, 315].map((deg) => { const f = G.frameAt(ctr, deg, r1); return { f, pts: f.pts([[r0, -hw], [r1 - cut, -hw], [r1, -hw + cut], [r1, hw - cut], [r1 - cut, hw], [r0, hw]]) }; });
  F.borders(c, arms.map((a) => a.pts), 0.7);
  const q = r0 * Math.SQRT2 + 0.2;                                  // the crossing square (it stands on its corner)
  c.fill(S.polygon([[ctr[0] - q, ctr[1]], [ctr[0], ctr[1] - q], [ctr[0] + q, ctr[1]], [ctr[0], ctr[1] + q]]), P.flat(C.black));
  for (const a of arms) c.fill(S.polygon(a.pts), fill(a.f));
};

// ---- the master's flurry ---------------------------------------------------------------------------------------------
// The three swords of the second flurry, burnt out: in the game each is a dark sword with a pale line of light, inside
// a hot edge one pixel wide that runs from dark red at the hilt through grey to white at the point. Fire stands
// between them (a red tongue above and below the middle blade, brightest red at its root and pink at its tip), and
// four sparks fly off the corners (red at the left, ash-pale at the right, where the blades are white hot).
const EMBER = [[0, '#6e1810'], [0.38, '#7a3228'], [0.6, '#a08a86'], [0.8, '#e2d2ce'], [1, '#ffffff']];
// st: ring (the hot edge's width), inner (the dark sword's colour), core (half-width of its light), light (its colour)
const emberSword = (c, E, T, o, st) => {
  const f = G.frame(E, T), L = f.L, sil = f.pts(W.swordOutline(L, o)), shape = S.polygon(sil);
  if (st.part !== 'body') c.fill(S.polygon(G.offsetPts(sil, 0.7)), P.flat(C.black));
  if (st.part === 'border') return;
  const heat = P.ramp(EMBER);
  c.fill(shape, (px) => { heat(f.t(px.x, px.y) / L, px); px.a = 1; });
  c.fill(S.grow(shape, -st.ring), P.flat(st.inner));
  // the light: along the guard and along the sword, each coming to a point at both ends, 2 short of the sword's ends
  const gm = o.guardAt, gl = o.guard / 2 - st.ring - 0.5, c0 = 2.0, c1 = L - 2.0, w = st.core, tp = 0.9, gw = w * 0.8;
  c.fill(S.polygon(f.pts([[gm, -gl], [gm - gw, -gl + tp], [gm - gw, gl - tp], [gm, gl], [gm + gw, gl - tp], [gm + gw, -gl + tp]])), P.flat(st.light));
  c.fill(S.polygon(f.pts([[c0, 0], [c0 + tp, -w], [c1 - tp, -w], [c1, 0], [c1 - tp, w], [c0 + tp, w]])), P.flat(st.light));
};
const SPARK = { rim: '#3a0806', edge: '#7a1810', body: '#cc341e' }, ASH = { rim: '#3a2624', edge: '#7a5450', body: '#c9a8a2' };

module.exports = {
  // the same layout as the second flurry (middle sword on y 15.5, the outer ones 9.5 above and below)
  i_flurry03(c) {
    const small = { pommel: 0, grip: 4.0, guardAt: 6.0, guard: 8.0, guardT: 4.0, blade: 4.0, taper: 0.6, tipFlat: 1.4 }, so = { ring: 1.0, inner: '#5a423e', core: 0.3, light: '#f6dcd6' };
    const list = [[[9.0, 6.0], [30.7, 6.0], small, so], [[9.0, 25.0], [30.7, 25.0], small, so],
      [[1.0, 15.5], [30.7, 15.5], { pommel: 0, grip: 5.0, guardAt: 7.5, guard: 13, guardT: 5.0, blade: 5.0, taper: 0.8, tipFlat: 1.7 }, { ring: 1.0, inner: '#221817', core: 0.42, light: '#ffffff' }]];
    const flip = (pts) => pts.map(([x, y]) => [x, 31 - y]).reverse();           // the mirror image about the middle sword's axis
    // a tongue of fire: from its root behind the middle guard (x 9.5, y 8.6 to 13.4) to its tip at (24.6, 10.9), both edges bowed out
    const flame = [...bow([9.5, 8.6], [24.6, 10.9], -0.4), ...bow([24.6, 10.9], [9.5, 13.4], -0.9).slice(1)];
    const sparkL = [[3.4, 1.5], [9.6, 4.2], [8.6, 6.2]], sparkR = [[21.6, 1.4], [25.8, 3.4], [23.0, 3.7]];
    // ONE big triangle of fire behind all three swords, centred on the middle one (the user's reading of the game):
    // its base upright at the left from the top sword to the bottom one, its point to the right on the middle axis; the
    // two tongues stand out of its sides, one piece with it
    // (the user's drawing: ONE shape. Its point lies under the middle sword's point, its two back corners run out into
    // the thorns beyond the outer swords' grip ends, and its back is drawn in between them. No separate tongues.)
    // the triangle's back stands at the outer swords' grip ends, so that nothing of it shows behind them
    const big = [[9.0, 4.2], [29.5, 15.5], [9.0, 26.8]];   // (its back on the line of the outer swords' grip ends, x 9: the user)
    // thorns of their own on each outer sword, both leaning to the left: a thick one off its grip end, a small one near its point
    const thornL = [[3.4, 1.5], [13.0, 5.4], [9.0, 6.0]], thornR = [[22.4, 2.1], [25.4, 3.4], [23.4, 3.7]], thornR2 = thornR.map(([x, y]) => [x, 12 - y]).reverse();   // a small one above each outer sword and its mirror image below it (the user's picture)
    // (the left thorns are ONE piece with the triangle: its back corners run out into them, no edge between)
    const fire = [big, thornL, flip(thornL)], sparks = [thornR, flip(thornR), thornR2, flip(thornR2)];
    F.borders(c, [...sparks, ...fire], 0.7, 1.8);                                 // all the black first: nothing cuts into a neighbour
    for (const [E, T, o, st] of list) emberSword(c, E, T, o, { ...st, part: 'border' });
    sparks.forEach((pts, i) => F.solid(c, pts, { palette: ASH, border: 0, depth: 0.6 }));
    const hot = P.ramp([[6, '#8a1a10'], [9.5, '#c02a18'], [16, '#d8442e'], [20.5, '#e88a7c'], [24.6, '#f2c2ba'], [27, '#f6d2cc']]), dark = P.hex('#5a120c');
    for (const pts of [0]) c.fill(S.union(...fire.map((p) => S.polygon(p))), (px) => {
      hot(px.x, px);
      const e = 1 - S.clamp(-px.d / 1.0, 0, 1), w = e * e;                         // deeper to its edge
      px.r += (dark[0] - px.r) * w; px.g += (dark[1] - px.g) * w; px.b += (dark[2] - px.b) * w; px.a = 1;
    });
    for (const [E, T, o, st] of list) emberSword(c, E, T, o, { ...st, part: 'body' });
  },

  // The crossed swords of the first duel icon with a line of light round the two together: in the game a white line
  // one pixel wide that follows their outline one pixel off (black between), with no black outside it. The line gets
  // the look the user chose for the outline of the two-weapon icons (blue with a white middle), and its sharp corners
  // are cut square as the game's are.
  i_duel02(c) {
    const o = { ...BLUE_SWORD, guard: 6.5, guardAt: 8.25, blade: 1.95 };
    const A = G.frame([4.8, 27.4], [26.3, 4.1]), B = G.frame([27.2, 27.4], [5.7, 4.1]);
    // (the line follows the swords' plain shape: guards and grip ends taken square, as the game's boxy line does;
    // followed round every little point of the guards it came out jagged)
    const polys = [A, B].map((f) => f.pts(W.swordOutline(f.L, o)));   // (the user: the line comes to diamond points round the guard's ends and the pommel, as the sword does)
    const grown = (r) => S.union(...polys.map((pts) => S.polygon(G.offsetPts(pts, r, 2.4))));
    const inside = grown(0.9);
    c.fill(inside, P.flat(C.black));
    W.bandLook(c, S.subtract(grown(2.1), inside), 0.6, { palette: 'blue', core: 0.26, halo: 0.2 });
    swords(c, [[A.E, A.T, o, { palette: 'blue', side: 1 }], [B.E, B.T, o, { palette: 'blue', side: -1 }]]);
  },

  // the game's measures: middle (15.85, 15.85), bars 3.5 wide, arms from 2.1 to 15.3
  i_crtstrk01(c) {
    const glow = P.ramp([[2.1, '#cc3a26'], [6.5, '#d85a46'], [8.3, '#e58574'], [9.6, '#f2b9b0'], [10.9, '#fff6f4'], [15.3, '#ffffff']]), rim = P.hex('#5e0703');
    strike(c, [15.85, 15.85], 2.1, 15.3, 1.75, 0.75, (f) => (px) => {
      glow(f.t(px.x, px.y), px);
      const e = 1 - S.clamp(-px.d / 0.7, 0, 1), w = S.clamp((0.13 + px.d) * c.k + 0.5, 0, 1);    // deeper to the edge, a thin dark line on it
      px.r *= 1 - 0.18 * e; px.g *= 1 - 0.3 * e; px.b *= 1 - 0.3 * e;
      px.r += (rim[0] - px.r) * w; px.g += (rim[1] - px.g) * w; px.b += (rim[2] - px.b) * w; px.a = 1;
    });
  },
  // the same in white on a red field. In the game the field is a square (x and y 5.3 to 26.4) of one red whose edge
  // fades out softly over two or three pixels, with no black round it; the bars are 4.4 wide, arms from 2.2 to 15.6
  i_crtstrk02(c) {
    const field = S.box(15.85, 15.85, 10.55, 10.55, 1.6);
    c.glow(field, '#be1b00', 1.3, 0.9);
    c.fill(field, P.flat('#c41c02'));
    strike(c, [15.85, 15.85], 2.2, 15.6, 2.2, 0.9, () => P.byDepth(0.4, [[0, '#b9a6a3'], [1, '#ffffff']]));
  },

  ip_speedburst(c) { burst(c); },

  // two large chevrons, their points at (15.9, 16) and 11.3 further right (the game's places, centred in the frame)
  ip_knightspeed(c) { speed(c, [[15.9, 16], [27.2, 16]], 1, { trail: 3.6, dark: 1.3, glow: 1.6 }); },
  // six small ones: two pairs at the left, one above the other, and a pair at the right between them. The game's
  // places drawn in towards the middle by a twentieth, so that the last one's dark band stands whole inside the frame.
  ip_masterspeed(c) {
    speed(c, [[10.3, 8.9], [16.6, 8.9], [10.3, 23.1], [16.6, 23.1], [23.6, 16], [29.9, 16]], 0.48, { trail: 1.4, dark: 1.0, glow: 1.1 });
  },

  // one lightsaber: field from (20.8, 4.6), 10.2 wide and 16.1 high above the guard; the guard's white 0.6 thick and
  // 1.5 out at each side; 4.9 below it
  ip_lsthrow(c) { saber(c, [20.8, 5.2], 10.2, 15.0, 3.6); },
  // three: the single icon's one lower, at the back; before it one at the upper left (field from (16.0, 0.9), 9.0
  // wide, 9.0 high, 3.2 below) and a small one at the lower right, close against the large one (the user: the third
  // was "too far away"; in the game their black edges touch): field from (19.3, 18.9), 5.6 wide, 6.1 high, 2.9 below.
  // They overlap: all borders first, no black between them.
  ip_advlsthrow(c) {
    const three = [[[20.8, 6.2], 10.2, 15.0, 3.6, {}], [[16.0, 0.9], 9.0, 9.0, 3.2, { guard: 0.5, out: 1.3, blade: 0.95, thin: 0.2 }],
      [[19.3, 18.9], 5.6, 6.1, 2.9, { guard: 0.4, out: 0.95, blade: 0.7, thin: 0.16, edge: 0.24 }]];
    for (const part of ['border', 'body']) for (const [at, w, up, low, st] of three) saber(c, at, w, up, low, { ...st, part });
  },

  // one bolt, two bolts (the second 9 to the right), three bolts (the middle one taller); red, no light of their own
  ip_shock(c) { F.solid(c, bolt(SHOCK), { palette: 'red', border: 0.9 }); },
  ip_lightning(c) { const all = [0, 9].map((dx) => F.moved(bolt(TWIN), dx, 0)); F.borders(c, all, 0.9); for (const pts of all) F.solid(c, pts, { palette: 'red', border: 0 }); },
  // (three that stand close: all their borders first, then the bolts)
  ip_storm(c) { const all = STORM.map(bolt); F.borders(c, all, 0.9); for (const pts of all) F.solid(c, pts, { palette: 'red', border: 0 }); },

  // one large arrow pair: apex (16, 0.86), head 12.05 to each side, stem 6.14 to each side and 7.0 long; blue 10.31 lower
  ip_jump(c) { jump(c, [16, 0.86], 12.05, 6.14, 7.0, 10.31); },
  i_jump01(c) { jump(c, [16, 0.86], 12.05, 6.14, 7.0, 10.31); },
  // three small pairs: apexes (16.04, 1.93), (7.82, 14.7), (24.2, 14.7); head 5.6, stem 2.98 by 3.37; blue 4.93 lower
  ip_advjump(c) { for (const a of [[16.02, 1.93], [7.83, 14.7], [24.21, 14.7]]) jump(c, a, 5.6, 2.98, 3.37, 4.93); },
  i_jump02(c) { for (const a of [[16.02, 1.93], [7.83, 14.7], [24.21, 14.7]]) jump(c, a, 5.6, 2.98, 3.37, 4.93); },

  // one red sword: red all over in the game, no light of its own. Shaded as a body only (deeper to its edges).
  // Measured: from (4.49, 27.49) to (26.95, 3.60); grip 2.86 wide ending in a point 1.35 long; guard 7.92 x 1.8, its
  // middle 8.87 from the grip's end; blade 3.32 wide, point 1.9 long.
  i_attack(c) {
    const f = G.frame([4.49, 27.49], [26.95, 3.6]);
    W.glowSword(c, f.E, f.T, { pommel: 0.8, grip: 1.5, guardAt: 8.87, guard: 6.5, guardT: 1.1, guardPoint: 0.6, blade: 1.8, taper: 1.5 }   /* as slim as the power attack's sword: the user */, { palette: 'red', core: 0, plain: true, depth: 0.5, border: 0.85 });
  },

  // two swords side by side: the second is the first moved by (7, 6)
  i_2weap01(c) {
    const a = G.frameAt([1.95, 24.4], -47.9, 31.1);
    swords(c, [[0, 0], [7, 6]].map((d) => [shifted(a.E, d), shifted(a.T, d), BLUE_SWORD, { palette: 'blue', side: -1, core: 0.24, coreEnd: 1.6 }]));   // (the same line of light as in II and III: the user)
  },

  i_2weap02(c) { outlinedPair(c); },
  // the same with the swing across the points. The swords are 3.1 shorter than in II so that the whole crescent,
  // uncut, holds the tops of the line (in the game the frame cuts the crescent instead).
  i_2weap03(c) { outlinedPair(c, { L: 26.5, swung: true }); },

  // two swords crossed, mirror images about x = 16; the one pointing up and to the left lies on top.
  // Measured: from (27.2, 27.4) to (5.7, 4.1) and from (4.8, 27.4) to (26.3, 4.1); blade 1.95 wide, guard 6.5 at 8.25
  i_duel01(c) {
    const o = { ...BLUE_SWORD, guard: 6.5, guardAt: 8.25, blade: 1.95 };
    swords(c, [[[4.8, 27.4], [26.3, 4.1], o, { palette: 'blue', side: 1 }], [[27.2, 27.4], [5.7, 4.1], o, { palette: 'blue', side: -1 }]]);
  },

  // three red swords pointing right, each with a line of light along its whole length and across its guard; the outer
  // two are mirror images about the middle one's axis. The GAME's proportions (the redraw's outer swords are half as
  // thick again): the middle one 29 long from x 1 on y 16, 3 thick from end to end, its guard 3 x 11 with its middle
  // 7.5 from the grip's end; the outer ones 21 long from x 9, 9 above and below, 2 thick, guard 2 x 7 at 6. Blunt ends
  // (the game's are cut nearly square). The light stops 1.5 short of both ends.
  i_flurry01(c) {
    const st = { palette: HOT, border: 0.7, flare: 0.15 };
    const small = { pommel: 0, grip: 2.0, guardAt: 6.0, guard: 7.0, guardT: 2.0, blade: 2.0, taper: 0.8 };
    const outer = { ...st, depth: 0.6, core: 0.15, guardCore: 0.14, guardLight: 2.5, coreEnd: 1.5, coreTaper: 0.8, halo: 0.2, flare: 0.08 };
    swords(c, [[[9.0, 7.0], [30.0, 7.0], small, outer], [[9.0, 25.0], [30.0, 25.0], small, outer],
      [[1.0, 16.0], [30.0, 16.0], { pommel: 0, grip: 3.0, guardAt: 7.5, guard: 11, guardT: 3.0, blade: 3.0, taper: 1.0 }, { ...st, core: 0.3, guardCore: 0.26, guardLight: 4.3, coreEnd: 1.5, coreTaper: 1.0, halo: 0.4 }]]);
  },
  // the same three swords one thicker all round, their blades paling towards blunt ends (in the game the outer rows
  // of each blade turn pink over the last eight pixels and its end is white). The game's proportions: middle 29.7 long
  // from x 1 on y 15.5, 5 thick, guard 5 x 13 at 7.5; outer ones 21.7 long from x 9, 9.5 above and below, 4 thick,
  // guard 4 x 8 at 6.
  i_flurry02(c) {
    const st = { palette: { ...HOT, heat: '#ffe4de' }, border: 0.7, flare: 0.15, heat: 8.5 };
    const small = { pommel: 0, grip: 4.0, guardAt: 6.0, guard: 8.0, guardT: 4.0, blade: 4.0, taper: 0.6, tipFlat: 1.4 };
    const outer = { ...st, core: 0.3, guardCore: 0.28, guardLight: 2.8, coreEnd: 1.5, coreTaper: 0.8 };
    swords(c, [[[9.0, 6.0], [30.7, 6.0], small, outer], [[9.0, 25.0], [30.7, 25.0], small, outer],
      [[1.0, 15.5], [30.7, 15.5], { pommel: 0, grip: 5.0, guardAt: 7.5, guard: 13, guardT: 5.0, blade: 5.0, taper: 0.8, tipFlat: 1.7 }, { ...st, core: 0.45, guardCore: 0.4, guardLight: 5.0, coreEnd: 1.5, coreTaper: 1.0, halo: 0.5 }]]);
  },
};
