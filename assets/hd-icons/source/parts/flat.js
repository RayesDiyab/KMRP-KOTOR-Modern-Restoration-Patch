'use strict';
// Flat bodies for the symbols: an outline given as exact points, a black border round it with its corners kept
// sharp, and one colour that deepens a little to the edge with a thin dark line along it (the same shading the
// swords of parts/weapons.js carry, so that a sheet's symbols belong together).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const { clamp } = S;

const BLACK = '#0a0a0c';
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = 1; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

// rim: the thin line along the edge; edge: the colour just inside it; body: the colour of the middle
const BODY = {
  red: { rim: '#5e0703', edge: '#b4120a', body: '#e41a0c' },
  blue: { rim: '#0b1c86', edge: '#2a56e8', body: '#457bfc' },
  white: { rim: '#8ea4ee', edge: '#e4eaff', body: '#ffffff' },
};

// the shader of such a body: for any shape (its own distance decides the deepening)
const deepening = (k, pal, { depth = 0.9, rim = 0.13 } = {}) => {
  const p = typeof pal === 'string' ? BODY[pal] : pal, cr = lin(p.rim), ce = lin(p.edge), cb = lin(p.body);
  return (px) => { put(px, mix3(mix3(ce, cb, smooth(0, depth, -px.d)), cr, clamp((rim + px.d) * k + 0.5, 0, 1))); };
};

// A flat body from its outline's points. st: palette ('red' | 'blue' | 'white' or { rim, edge, body }), border
// (0 = none), depth (how far in the colour deepens), rim (width of the dark line), limit (see geom.offsetPts)
const solid = (c, pts, st = {}) => {
  const border = st.border === undefined ? 0.7 : st.border;
  if (border > 0) c.fill(S.polygon(G.offsetPts(pts, border, st.limit)), P.flat(st.ink || BLACK));
  const shape = S.polygon(pts);
  c.fill(shape, deepening(c.k, st.palette || 'red', st));
  return shape;
};
// the black border alone, of several outlines that overlap (each grown; together they are the border of the whole)
const borders = (c, list, border = 0.7, limit) => { for (const pts of list) c.fill(S.polygon(G.offsetPts(pts, border, limit)), P.flat(BLACK)); };

const moved = (pts, dx, dy) => pts.map(([x, y]) => [x + dx, y + dy]);
// mirror image about the vertical line x = cx (the order of the points is reversed, so the outline keeps its sense)
const mirrored = (pts, cx) => pts.map(([x, y]) => [2 * cx - x, y]).reverse();

module.exports = { BODY, deepening, solid, borders, moved, mirrored, BLACK };
