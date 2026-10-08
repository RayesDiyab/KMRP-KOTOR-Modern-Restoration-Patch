'use strict';
// Swords and neon lines, drawn from measured dimensions. Every outline is a polygon of straight lines; borders are
// the same outline moved out with its corners kept sharp; every change of colour that is meant to be an edge is a
// polygon's edge, and every gradient is a formula in the object's own frame (t along its axis, s across it).
// Nothing is drawn that the reference does not show: these are building blocks, the icons say what goes where.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');

const BLACK = '#0a0a0c';

// The outline of a sword in its frame. o: pommel (length of the point at the grip's end; 0 = cut square), grip
// (width), guardAt (the cross-guard's middle, from the grip's end), guard (its length across), guardT (its
// thickness), blade (width), taper (length of the point).
// guardPoint: the length of the point each end of the cross-guard comes to (0 = cut square).
const guardOutline = (o) => {
  const hg = o.guard / 2, gm = o.guardAt, g0 = gm - o.guardT / 2, g1 = gm + o.guardT / 2, gp = o.guardPoint || 0;
  return gp ? [[g0, -(hg - gp)], [gm, -hg], [g1, -(hg - gp)], [g1, hg - gp], [gm, hg], [g0, hg - gp]] : [[g0, -hg], [g1, -hg], [g1, hg], [g0, hg]];
};
const swordOutline = (L, o) => {
  const hb = o.blade / 2, hr = o.grip / 2, g0 = o.guardAt - o.guardT / 2, g1 = o.guardAt + o.guardT / 2, pm = o.pommel || 0;
  const g = guardOutline(o), n = g.length / 2;
  const tf = o.tipFlat || 0, tip = tf ? [[L, -tf], [L, tf]] : [[L, 0]];        // tipFlat: half-width of a flat end (0: a point)
  return [...(pm ? [[0, 0], [pm, -hr]] : [[0, -hr]]), [g0, -hr], ...g.slice(0, n), [g1, -hb], [L - o.taper, -hb], ...tip, [L - o.taper, hb], [g1, hb], ...g.slice(n), [g0, hr], ...(pm ? [[pm, hr]] : [[0, hr]])];
};
// the blade alone (from the guard's middle to the point)
const bladeOutline = (L, o) => [[o.guardAt, -o.blade / 2], [L - o.taper, -o.blade / 2], [L, 0], [L - o.taper, o.blade / 2], [o.guardAt, o.blade / 2]];

// a colour that changes along the object: stops = [[t, colour], ...] in units from its near end (one colour: flat)
const along = (f, stops) => {
  if (typeof stops === 'string') return P.flat(stops);
  const r = P.ramp(stops);
  return (px) => { r(f.t(px.x, px.y), px); px.a = 1; };
};

// The sword's body: black border, then the whole outline filled. Returns the outline's shape (for masks).
const body = (c, f, o, { fill, border = 0.7, ink = BLACK } = {}) => {
  const sil = f.pts(swordOutline(f.L, o)), shape = S.polygon(sil);
  if (border > 0) c.fill(S.polygon(G.offsetPts(sil, border)), P.flat(ink));
  c.fill(shape, along(f, fill));
  return shape;
};

// a rectangle in the object's frame: from t0 to t1 along it, s0 to s1 across
const rect = (f, t0, t1, s0, s1) => S.polygon(f.pts([[t0, s0], [t1, s0], [t1, s1], [t0, s1]]));

// A line of light from a to b (both [t, s] in the object's frame): a crisp line of half-width w that may come to a
// point at either end (taperA, taperB: the length of the point), with a soft glow round it that stays inside `mask`.
const light = (c, f, a, b, { w = 0.17, taperA = 0, taperB = 0, colour = '#ffffff', halo = 0, haloColour = '#ffffff', haloStrength = 0.8, mask = null } = {}) => {
  const A = f.pt(a[0], a[1]), B = f.pt(b[0], b[1]), g = G.frame(A, B), L = g.L;
  if (halo > 0 && mask) {
    const hc = P.hex(haloColour);
    c.fill(mask, (px) => {
      const t = g.t(px.x, px.y), s = g.s(px.x, px.y), d = Math.max(Math.hypot(Math.max(-t, 0, t - L), s) - w, 0);
      // the glow dies away with the line where the line comes to a point
      const fade = Math.min(taperA > 0 ? Math.max(t / taperA, 0) : 1, taperB > 0 ? Math.max((L - t) / taperB, 0) : 1, 1);
      px.r = hc[0]; px.g = hc[1]; px.b = hc[2]; px.a = haloStrength * fade * Math.exp(-(d * d) / (halo * halo));
    });
  }
  const pts = taperA > 0 ? [[0, 0], [taperA, -w]] : [[0, -w]];
  if (taperB > 0) pts.push([L - taperB, -w], [L, 0], [L - taperB, w]); else pts.push([L, -w], [L, w]);
  pts.push(taperA > 0 ? [taperA, w] : [0, w]);
  // one colour, or a colour that changes along the line: [[0, colour at a], ..., [1, colour at b]]
  const r = typeof colour === 'string' ? null : P.ramp(colour);
  c.fill(S.polygon(g.pts(pts)), r ? (px) => { r(g.t(px.x, px.y) / L, px); px.a = 1; } : P.flat(colour));
};

// A neon line: its middle line is `line` (points), hw its half-width. A white core, its colour deepening to the
// edge, a black border; joints sharp, ends square. st: stops (colour from the edge (0) to the core (1)), border,
// core (half-width of the white), look ('body': drawn like the swords, blue with a thin white line and its glow)
const TUBE = {
  blue: [[0, '#1230c4'], [0.3, '#2f5cf4'], [0.75, '#9db8ff'], [1, '#ffffff']],
  red: [[0, '#b00c06'], [0.3, '#ee2a1c'], [0.75, '#ffb8ac'], [1, '#ffffff']],
};
const tube = (c, line, hw, st = {}) => {
  const border = st.border === undefined ? 0.7 : st.border, core = st.core === undefined ? hw * 0.36 : st.core;
  const stops = st.stops || TUBE[st.palette || 'blue'];
  // (filled by the non-zero rule: where two stretches of a wide line overlap, as inside a hairpin, it stays filled)
  // st.part: 'border' draws only the black round it, 'fill' only the line (for laying other things between the two)
  if (border > 0 && st.part !== 'fill') c.fill(S.polygon(G.strokePts(line, hw + border, { lengthen: border }), undefined, 'nonzero'), P.flat(st.ink || BLACK));
  if (st.part === 'border') return;
  if (st.look === 'body') {
    // the look of the swords: a blue body deepening to its edge, a thin white line down its middle with a soft glow
    const pal = PALETTE[st.palette || 'blue'], col = {}; for (const key of Object.keys(pal)) col[key] = lin(pal[key]);
    const halo = st.halo === undefined ? 0.3 : st.halo, rimW = st.rim === undefined ? 0.13 : st.rim, k = c.k;
    c.fill(S.polygon(G.strokePts(line, hw), undefined, 'nonzero'), (px) => {
      const depth = -px.d;
      let v = mix3(col.edge, col.body, smooth(0, hw * 0.8, depth));
      v = mix3(v, col.glow, 0.8 * bell(Math.max(hw - depth - core, 0), halo));
      put(px, mix3(v, col.rim, clamp((rimW + px.d) * k + 0.5, 0, 1)));
    });
    if (core > 0) c.fill(S.polygon(G.strokePts(line, core, { lengthen: -(hw - core) }), undefined, 'nonzero'), P.flat(pal.core));
    return;
  }
  c.fill(S.polygon(G.strokePts(line, hw), undefined, 'nonzero'), P.byDepth(hw - core, stops));
  if (core > 0) c.fill(S.polygon(G.strokePts(line, core, { lengthen: -(hw - core) }), undefined, 'nonzero'), P.flat('#ffffff'));
};

// ---- the sword that is shaded as a body ---------------------------------------------------------------------------
const { clamp } = S;
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = 1; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bell = (d, w) => Math.exp(-(d * d) / (w * w));
const PALETTE = {
  blue: { rim: '#0b1c86', edge: '#2148de', body: '#4676f6', lit: '#6690fb', glow: '#bfd2ff', gripFar: '#2748cf', guardEdge: '#3f6cf2', core: '#ffffff', coreEnd: '#c4d6ff' },
  red: { rim: '#5e0703', edge: '#b4120a', body: '#e41a0c', lit: '#f23a26', glow: '#ffd6cc', gripFar: '#b01208', guardEdge: '#d2180c', core: '#ffffff', coreEnd: '#ffc9bf' },
};
// The sword as ONE body (grip, cross-guard and blade are not separated by any line): its colour deepens to the edge of
// its outline, with a thin dark line along that edge; the grip deepens towards its end and the blade is a little
// lighter on one side. With core > 0 a line of light runs along the sword and a thinner one along the guard, each
// coming to a point at its ends, with a soft glow round it and more light where they cross.
//   st: palette, border, rim, depth (how far in from the edge the colour deepens), side (which side of the blade is
//   the lighter: +1 right of the direction grip to tip), core (half-width of the line of light; 0 = none),
//   coreEnd (how far the light stops short of the tip AND of the grip's end: the same at both, by the user's rule),
//   coreTaper (the length of its points, the same at both ends), halo (reach of the glow), flare (strength of the
//   light at the crossing), guardCore (half-width of the light on the guard), guardLight (its half-length),
//   heat (over how far from the point the blade pales, edges first; the palette's `heat` is the colour it reaches)
const glowSword = (c, E, T, o, st = {}) => {
  const f = G.frame(E, T), L = f.L, k = c.k;
  const pal = typeof st.palette === 'object' ? st.palette : PALETTE[st.palette || 'blue'];
  const col = {}; for (const key of Object.keys(pal)) col[key] = lin(pal[key]);
  const hb = o.blade / 2, hg = o.guard / 2, gm = o.guardAt, g0 = gm - o.guardT / 2, g1 = gm + o.guardT / 2, gp = o.guardPoint || 0;
  const pick = (v, d) => (v === undefined ? d : v);
  const border = pick(st.border, 0.7), rimW = pick(st.rim, 0.13), core = pick(st.core, 0.17), halo = pick(st.halo, 0.36), flare = core > 0 ? pick(st.flare, 0.6) : 0;
  const end = pick(st.coreEnd, 2.2), c0 = end, c1 = L - end, taper = pick(st.coreTaper, 2.6), deep = pick(st.depth, 0.8), side = st.side || 1;
  const gc = core > 0 ? pick(st.guardCore, 0.19) : 0, gl = pick(st.guardLight, hg - gp * 0.75 - 0.2);
  const sil = f.pts(swordOutline(L, o));
  // st.part: 'border' draws only the black round the sword, 'body' everything but it. Objects that stand beside or
  // over one another get all their borders first and then their bodies, so that no black edge cuts into a neighbour
  // (the user: "dont cut into the sword next to it let then overlap").
  if (border > 0 && st.part !== 'body') c.fill(S.polygon(G.offsetPts(sil, border)), P.flat(st.ink || BLACK));
  if (st.part === 'border') return f;
  c.fill(S.polygon(sil), (px) => {
    const t = f.t(px.x, px.y), s = f.s(px.x, px.y);
    let v = mix3(col.edge, col.body, smooth(0, deep, -px.d));
    if (t < g0) v = mix3(mix3(v, col.gripFar, 0.75), v, smooth(0, g0, t));                 // the grip deepens towards its end
    else if (t > g1 && !st.plain) v = mix3(v, col.lit, 0.55 * smooth(-hb * 0.1, hb, -s * side) * smooth(g1, g1 + 1.2, t));
    if (st.heat) {                                                // the blade pales towards its point: first along its edges
      const h = smooth(L - st.heat, L - 0.4, t), w = h + (h * h * h - h) * smooth(0.25, 1.0, -px.d);
      v = mix3(v, col.heat || col.glow, w);
    }
    if (core > 0) {
      v = mix3(v, col.glow, 0.8 * bell(Math.hypot(Math.max(c0 - t, 0, t - c1), s), halo));
      if (flare > 0) v = mix3(v, col.glow, flare * bell(Math.hypot(t - gm, s), o.guard * 0.34));
      if (gc > 0) v = mix3(v, col.glow, 0.75 * bell(Math.hypot(t - gm, Math.max(Math.abs(s) - gl, 0)), gc + halo * 0.45));
    }
    put(px, mix3(v, col.rim, clamp((rimW + px.d) * k + 0.5, 0, 1)));
  });
  // the lines of light themselves: along the guard, then along the sword; each comes to a point at its ends
  if (gc > 0) {
    const tp = Math.min(1.4, gl * 0.45), r = P.ramp([[0, pal.core], [0.55, pal.core], [1, pal.coreEnd]]);
    c.fill(S.polygon(f.pts([[gm, -gl], [gm - gc, -gl + tp], [gm - gc, gl - tp], [gm, gl], [gm + gc, gl - tp], [gm + gc, -gl + tp]])), (px) => { r(Math.abs(f.s(px.x, px.y)) / gl, px); px.a = 1; });
  }
  if (core > 0) c.fill(S.polygon(f.pts([[c0, 0], [c0 + taper, -core], [c1 - taper, -core], [c1, 0], [c1 - taper, core], [c0 + taper, core]])), P.flat(pal.core));
  return f;
};

// The swords' look on any band of half-width hw (the band's own distance decides): blue deepening to its edges, a
// white line down its middle with a soft glow. st: palette, core (half-width of the white), halo, rim
const bandLook = (c, shape, hw, st = {}) => {
  const pal = PALETTE[st.palette || 'blue'], col = {}; for (const key of Object.keys(pal)) col[key] = lin(pal[key]);
  const core = st.core === undefined ? hw * 0.36 : st.core, halo = st.halo === undefined ? 0.3 : st.halo, rimW = st.rim === undefined ? 0.13 : st.rim, k = c.k;
  c.fill(shape, (px) => {
    const depth = -px.d;
    let v = mix3(col.edge, col.body, smooth(0, hw * 0.8, depth));
    v = mix3(v, col.glow, 0.8 * bell(Math.max(hw - depth - core, 0), halo));
    put(px, mix3(v, col.rim, clamp((rimW + px.d) * k + 0.5, 0, 1)));
  });
  if (core > 0) c.fill(S.grow(shape, -(hw - core)), P.flat(pal.core));
};

module.exports = { swordOutline, guardOutline, bladeOutline, along, body, rect, light, tube, glowSword, bandLook, PALETTE, TUBE, BLACK };
