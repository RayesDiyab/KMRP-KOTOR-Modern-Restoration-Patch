'use strict';
// The bust seen from the front: one construction, placed and scaled in every icon of the sheet, in blue or in red.
//
// HOW TO USE IT (const H = require('../parts/symbol_head_front')):
//   place     pl = { at: [x, y], s }      (x, y): where the top of the head goes, on the bust's axis; s: the scale.
//             At s = 1 the head is 12.18 wide and the neck is narrowest 13.82 below the top; the chest is 21.84 wide.
//   form      H.CHEST       the bust down to the chest (bottom 29.26 s below the top of the head)
//             H.SHOULDERS   the bust cut off below the shoulders (bottom 18.63 s below the top)
//             or your own: { vb, rc, neck, w, r8, cut } (see "the outline" and "the shader" below)
//   draw      H.bust(c, pl, { hue: 'blue' | 'red', ...form })      black border (H.BORDER wide), then the figure.
//             border: 0 leaves the border out; part: 'border' | 'body' draws only that (lay ALL borders of things
//             that touch first, then their bodies).
//   clip      H.clipped(c, mask, pl, o)    the same, but only inside the shape `mask` (a disc, a shield): the bust
//             and its border are cut by the mask's edge. (Draw the disc or shield first, its own border before that.)
//   outline   H.shape(pl, form)            the bust's shape as a distance function (for masks, S.subtract, c.fill)
//             H.outlinePts(pl, form)       the same outline as points [[x, y], ...] in the icon
//             H.head(pl)                   the head alone, closed across the neck (a glow round the head only)
//   glow      H.glow(c, shape, { reach, strength, power, colours, weigh })    a soft light round any shape; draw it
//             BEFORE the bust.
//   dark      H.dark(c, pl, { ...form })   the bust as a black figure with a line of light along its edge;
//             H.darkInside(pl, form) is its black inside as a shape (to lay eyes on)
//   colours   H.ramps.blue(key, px), H.ramps.red(key, px): the bust's colour for a key 0 (saturated) .. 255 (white)
// The exported names and their arguments stay as they are (other files of the sheet rely on them); options are added.
//
// Its OUTLINE is the same left and right of its axis. Each half is a chain of circular arcs and straight lines, each
// starting in the direction the last one ended in (smooth everywhere; the only corners are the two at the bottom, and
// they are small arcs). The chain was fitted to the mean outline of ChatGPT's redrawn busts: fifteen of them, each
// brought to the common size by ONE scale and a shift (tools/head_front_fit2d.py), agree with their mean to 0.04 ..
// 0.12 units; the chain keeps within 0.04 units of the mean on average and 0.11 at most (head_front_mastercheck.py).
// The redraws' heads differ only in size: the small bust with the long chest and the large bust cut off below the
// shoulders are the same figure (their outlines lie on one another down to where the large one is cut).
//
// Its MODELLING is one number per place, the key (0 .. 255): the bust's colours lie on one ramp from the saturated hue
// (key 0) to white (255), so the key says all (for a blue bust it is its R, for a red one its B). The key is read from
// a small table (symbol_head_front_shade.json, six values per unit): the mean of thirteen redrawn busts, each laid
// exactly on the constructed outline, their faces laid on one another, their tones brought to one scale
// (tools/head_front_shade.py, head_front_table.py). It carries the forehead's light, the brow, the eye sockets, the
// nose and its shadow, the mouth, the jaw, the shadow under the chin and down the neck, the shoulders' light.
// The LINE along the edge is not in the table: it is a formula of the exact distance to the outline (the saturated
// hue at the very edge, darker towards the black border, whitening inwards to the white line), so it is equally wide
// all round and as crisp as the outline itself; where the redraws carry no saturated line (down the sides of the
// chest and along the bottom) the white stands at the edge.
//
// The bust's own frame: u across from the axis, v down from the top of the head, in units of the icon's frame for a
// bust at scale 1 (the size it has in the icons that show it down to the chest).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const SHADE = require('./symbol_head_front_shade.json');

const { clamp } = S;
const RAD = Math.PI / 180;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const INK = '#0a0a0c';
// The black line round the bust. The redraws carry 0.58 to 0.77 below the bust (median 0.65) and 0.5 to 0.68 at its
// sides, whatever the bust's size (the cut-out has eaten into it; in the game it is one pixel). One width for every
// bust of the sheet, and the same as the flat symbols' (parts/flat.js).
const BORDER = 0.7;

// ---- the outline -----------------------------------------------------------------------------------------------------
// The right half, from the top of the head on the axis (heading right) to the bottom on the axis:
//   crown     an arc of radius 11.8 about a point on the axis, as far as heading 8.8 degrees
//   temple    radius 4.96, to heading 85 (the head's upper corner)
//   cheek     radius 26.4, to heading 100.6 (the side of the head: widest, 6.09 from the axis, 6.91 below the top)
//   jaw       radius 2.0, to heading 144
//   under the jaw, a straight line 0.39 long
//   neck      a hollow of radius 0.71, to heading 18.2 (the neck is narrowest, 4.24 from the axis, 13.82 below the top)
//   shoulder  a straight line at 18.2 degrees below level, as long as it takes for the round to end at W
//   round     radius 3.4, to straight down, 10.92 from the axis (19.0 below the top)
//   side      straight down
//   corner    radius 0.65
//   bottom    level, 29.26 below the top
// A bust that is cut off higher (vb less than the round's end + the corner's radius) has its corner where the bottom
// meets the shoulder's round: a circle of the corner's radius touching both.
// Options: vb (the bottom), rc (the corner's radius), neck (a straight piece added to the neck at its narrowest),
// w (the half-width the shoulder's round ends at), r8 (the round's radius).
const DIM = { R1: 11.8, A1: 8.8, R2: 4.96, A2: 85, R3: 26.4, A3: 100.6, R4: 2.0, A4: 144, L5: 0.39, R6: 0.71, A6: 18.2, R8: 3.4, W: 10.92, RC: 0.65, VB: 29.26 };
const CROP = SHADE.crop;            // the bust cut off below the shoulders: vb 18.63, rc 0.5 (measured on four redraws)
const TOL = 0.001;                  // an arc is drawn as chords that stay this close to it (units)

const halfOutline = (o = {}) => {
  const vb = o.vb === undefined ? DIM.VB : o.vb, rc = o.rc === undefined ? DIM.RC : o.rc, neck = o.neck || 0;
  const W = o.w === undefined ? DIM.W : o.w, R8 = o.r8 === undefined ? DIM.R8 : o.r8;
  const pts = [[0, 0]];
  let x = 0, y = 0, th = 0;
  // an arc of radius r (negative: it turns against the clock, a hollow) to the heading `to`
  const arc = (r, to) => {
    const t0 = th * RAD, t1 = to * RAD, cx = x - r * Math.sin(t0), cy = y + r * Math.cos(t0);
    const n = Math.max(2, Math.ceil(Math.abs((t1 - t0) * r) / Math.sqrt(8 * Math.abs(r) * TOL)));
    for (let i = 1; i <= n; i++) { const a = t0 + ((t1 - t0) * i) / n; pts.push([cx + r * Math.sin(a), cy - r * Math.cos(a)]); }
    x = pts[pts.length - 1][0]; y = pts[pts.length - 1][1]; th = to;
    return [cx, cy];
  };
  const line = (len) => { x += len * Math.cos(th * RAD); y += len * Math.sin(th * RAD); pts.push([x, y]); };
  arc(DIM.R1, DIM.A1); arc(DIM.R2, DIM.A2); arc(DIM.R3, DIM.A3); arc(DIM.R4, DIM.A4); line(DIM.L5);
  let neckAt = 0;
  if (neck > 0) { arc(-DIM.R6, 90); neckAt = y; line(neck); arc(-DIM.R6, DIM.A6); } else { const ctr = arc(-DIM.R6, DIM.A6); neckAt = ctr[1]; }
  const a6 = DIM.A6 * RAD;
  line((W - R8 * (1 - Math.sin(a6)) - x) / Math.cos(a6));
  const c8 = [x - R8 * Math.sin(a6), y + R8 * Math.cos(a6)];           // the centre of the shoulder's round
  if (vb - rc >= c8[1]) { arc(R8, 90); line(vb - rc - y); arc(rc, 180); }
  else {
    const cy = vb - rc, cx = c8[0] + Math.sqrt((R8 - rc) * (R8 - rc) - (cy - c8[1]) * (cy - c8[1]));
    arc(R8, Math.atan2(cy - c8[1], cx - c8[0]) / RAD + 90); arc(rc, 180);
  }
  pts.push([0, vb]);
  return { pts, neckAt, sideTop: c8[1], vb };
};
// the closed outline in the bust's own frame (the left half is the right half's mirror image)
const outline = (o) => { const h = halfOutline(o).pts; return h.concat(h.slice(1, -1).reverse().map(([u, v]) => [-u, v])); };

// ---- placing ---------------------------------------------------------------------------------------------------------
// A place: { at: [x, y] where the top of the head on the axis goes in the icon, s: the scale }.
const toIcon = (pl) => (p) => [pl.at[0] + pl.s * p[0], pl.at[1] + pl.s * p[1]];
const outlinePts = (pl, o) => outline(o).map(toIcon(pl));
// the bust's shape in the icon (one function per place and form, so that the canvas computes its distances once)
const shapes = new Map();
const shape = (pl, o = {}) => {
  const key = JSON.stringify([pl.at, pl.s, o.vb, o.rc, o.neck, o.w, o.r8]);
  if (!shapes.has(key)) shapes.set(key, S.polygon(outlinePts(pl, o), 40));
  return shapes.get(key);
};
// The head alone: the outline down to the neck's narrowest place, closed straight across the neck there. For a glow
// round the head, and for whatever else follows the head but not the shoulders.
const headPts = (pl) => {
  const h = halfOutline({}), right = h.pts.filter((p) => p[1] <= h.neckAt + 1e-9);
  return right.concat(right.slice(1).reverse().map(([u, v]) => [-u, v])).map(toIcon(pl));
};
const head = (pl) => {
  const key = 'head ' + JSON.stringify([pl.at, pl.s]);
  if (!shapes.has(key)) shapes.set(key, S.polygon(headPts(pl), 40));
  return shapes.get(key);
};

// ---- the modelling ---------------------------------------------------------------------------------------------------
// a table read at (u, v): Catmull-Rom between its samples, its edge values held outside
const reader = (t) => {
  const { u0, v0, w, h, res } = t, data = Buffer.from(t.data, 'base64');
  const wt = new Float64Array(8);
  const weights = (f, o) => { wt[o] = (((-f + 2) * f - 1) * f) / 2; wt[o + 1] = ((3 * f - 5) * f * f + 2) / 2; wt[o + 2] = (((-3 * f + 4) * f + 1) * f) / 2; wt[o + 3] = ((f - 1) * f * f) / 2; };
  return (u, v) => {
    const gx = clamp((u - u0) * res, 0, w - 1), gy = clamp((v - v0) * res, 0, h - 1);
    const ix = Math.min(Math.floor(gx), w - 2), iy = Math.min(Math.floor(gy), h - 2);
    weights(gx - ix, 0); weights(gy - iy, 4);
    let sum = 0;
    for (let b = 0; b < 4; b++) {
      const row = clamp(iy - 1 + b, 0, h - 1) * w;
      let a = 0;
      for (let k = 0; k < 4; k++) a += wt[k] * data[row + clamp(ix - 1 + k, 0, w - 1)];
      sum += wt[4 + b] * a;
    }
    return sum;
  };
};
const FULL = reader(SHADE.tables.full), CUT = reader(SHADE.tables.crop);

// the colour of a key (sRGB 0..1 written to px.r, px.g, px.b): the measured ramps, a stop every 8 keys
const ramps = {};
for (const hue of Object.keys(SHADE.ramps)) {
  const st = SHADE.ramps[hue];
  ramps[hue] = (key, px) => {
    const k = clamp(key, 0, 255) / 8, i = Math.min(Math.floor(k), st.length - 2), f = Math.min(k - i, 1), a = st[i], b = st[i + 1];
    px.r = (a[1] + (b[1] - a[1]) * f) / 255; px.g = (a[2] + (b[2] - a[2]) * f) / 255; px.b = (a[3] + (b[3] - a[3]) * f) / 255;
  };
}
// How much of the colour's light is left at depth d from the edge: the line along the edge darkens towards the black
// border. Measured on the redraws laid on black (tools/head_front_edge.py), the hue's own channel as a share of its
// full value: blue 0.46 at the edge, 0.65 at 0.1, 0.81 at 0.2, 0.92 at 0.3, all of it from 0.4; red 0.34, 0.47, 0.63,
// 0.77, 0.88 and all of it from 0.55. Where the white stands at the edge (no saturated line) only a thin line darkens.
const DIM_LINE = { blue: [0.46, 0.34], red: [0.34, 0.52] };       // [share at the edge, the depth from which nothing is taken]
const DIM_THIN = [0.72, 0.25];
const dimAt = (d, q) => q[0] + (1 - q[0]) * clamp(d / q[1], 0, 1);

// The shader of a bust at a place. o: hue ('blue' | 'red'), and the form's options (vb, rc, neck, w, r8: see the
// outline; cut: true for the bust cut off below the shoulders, whose lower part is lit differently: a band of light
// along its bottom that widens towards the shoulders, read from the second table laid against the bottom);
// lit: a function (y, x) of the place in the icon saying where the bust has no black border beside it (1: none, as
// where it stands on a disc of its own colour or its border is lit; there the line along the edge does not darken);
// tone: a function (key, x, y) -> key that changes the modelling's key before it is coloured (a half in shadow).
const shader = (pl, o = {}) => {
  const form = halfOutline(o), L = SHADE.line, ramp = ramps[o.hue || 'blue'], dimLine = DIM_LINE[o.hue || 'blue'];
  const x0 = pl.at[0], y0 = pl.at[1], s = pl.s, vb = form.vb, neck = o.neck || 0, neckAt = form.neckAt;
  const side0 = form.sideTop, side1 = side0 + (L.side1 - L.side0);
  const lift = CROP.vb - (vb - neck);                                 // the second table stands against the bottom
  // narrower shoulders: the table's shoulders (from the neck's half-width out to 10.92) are drawn in to the width
  const NECK_U = 4.3, widen = o.w === undefined ? 1 : (DIM.W - NECK_U) / (o.w - NECK_U);
  return (px) => {
    const u0 = (px.x - x0) / s, v0 = (px.y - y0) / s, d = -px.d / s;
    // a lengthened neck: the table is read as if the added piece were not there
    const v = neck > 0 ? (v0 <= neckAt ? v0 : Math.max(v0 - neck, neckAt)) : v0;
    const au = Math.abs(u0), u = widen === 1 || au <= NECK_U || v < 13 ? u0 : Math.sign(u0) * (NECK_U + (au - NECK_U) * widen);
    // how far the saturated line has thinned out: down the side of the chest, and along the bottom (where the
    // nearest edge faces down: the gradient of the distance points away from it)
    const lam = Math.max(clamp((v0 - side0) / (side1 - side0), 0, 1), smooth(0.25, 0.9, px.gy) * smooth(vb - 2.0, vb - 1.2, v0));
    const wide = smooth(L.wideFrom, L.wideTo, v);
    const a = L.d0 + L.wide0 * wide - L.thin0 * lam, b = L.d1 + L.wide1 * wide - L.thin1 * lam;
    let t = FULL(u, v);
    if (o.cut) { const k = smooth(14.4, 15.4, v); if (k > 0) t += (CUT(u, v + lift) - t) * k; }
    const k = o.tone ? o.tone(t * smooth(a, b, d), px.x, px.y) : t * smooth(a, b, d);
    ramp(k, px);
    let dim = dimAt(d, dimLine) * (1 - lam) + dimAt(d, DIM_THIN) * lam;
    if (o.lit) dim += (1 - dim) * o.lit(px.y, px.x);                  // where the border itself is lit, nothing darkens
    px.r *= dim; px.g *= dim; px.b *= dim; px.a = 1;
  };
};

// The bust drawn: its black border, then the figure. pl: the place; o: hue, the form's options, border (0: none),
// part ('border' or 'body': only that, for laying several things' borders first). Returns its shape (for masks and
// for things laid on it).
const bust = (c, pl, o = {}) => {
  const sh = shape(pl, o), border = o.border === undefined ? BORDER : o.border;
  if (border > 0 && o.part !== 'body') c.fill(sh, P.flat(o.ink || INK), border);
  if (o.part !== 'border') c.fill(sh, shader(pl, o));
  return sh;
};
// the forms the sheet uses: the bust down to the chest, and the bust cut off below the shoulders
const CHEST = {};
const SHOULDERS = { vb: CROP.vb, rc: CROP.rc, cut: true };

// The bust inside a mask (a disc, a shield, any shape): drawn on a sheet of its own and laid on only where the mask
// is, so that the mask's edge cuts figure and border alike.
const clipped = (c, mask, pl, o = {}) => { c.layer((t) => bust(t, pl, o), { mask }); return shape(pl, o); };

// ---- the bust as a dark figure ---------------------------------------------------------------------------------------
// The same outline with light where the bust has its edge and shoulders, and black inside (the "Jedi armour" icons).
// In the game: a pale line one pixel wide round a black head, two pixels beside the neck, and below the neck the
// whole shoulders pale with a black middle that widens downwards, a line of one pixel under it. The redraw has the
// same parts with a white line that glows blue to both sides.
// Built as two shapes: the bust's outline, filled with light, and inside it the BLACK: the head's outline drawn in
// by `line`, and from it down a middle strip (the neck drawn in by `neckIn` at each side) that widens from where the
// shoulders' sides begin to `shoulderIn` inside the outline at the bottom, ending `foot` above the bust's bottom.
// (All four in units of the icon: the light is as wide on a large figure as on a small one.)
// The light is white, turning through the hue to black over the last 0.6 before the black, and fading in over 0.18
// from the outline (so that it sits softly on whatever lies behind). Returns { shape, black } (the black for eyes).
const LINE = { at: 0.3, core: 0.3, fade: 0.75, line: 1.0, neckIn: 1.9, shoulderIn: 3.2, foot: 0.85 };
const NECK_HALF = 4.24;             // the neck's half-width at its narrowest (at scale 1)
// the black inside of the dark figure at a place (one function per place and form)
const darkInside = (pl, o = {}) => {
  const q = { ...LINE, ...o }, key = 'dark ' + JSON.stringify([pl.at, pl.s, o.vb, o.rc, o.neck, o.w, o.r8, q.line, q.neckIn, q.shoulderIn, q.foot]);
  if (!shapes.has(key)) {
    const form = halfOutline(o), s = pl.s, [x, y] = pl.at;
    const n = Math.max(NECK_HALF * s - q.neckIn, 0.5), w = Math.max((o.w === undefined ? DIM.W : o.w) * s - q.shoulderIn, n);
    const yTop = y + 11.0 * s, yFlare = y + Math.min(form.sideTop, form.vb - 1.5) * s, yFoot = y + form.vb * s - q.foot;
    const lower = S.polygon([[x - n, yTop], [x + n, yTop], [x + n, yFlare], [x + w, yFoot], [x - w, yFoot], [x - n, yFlare]]);
    shapes.set(key, S.union(S.grow(head(pl), -q.line), lower));
  }
  return shapes.get(key);
};
// (an older, simpler shader: light by the depth inside the outline alone. Kept for whoever uses it.)
const darkShader = (o = {}) => {
  const q = { ...LINE, ...o }, ramp = ramps[o.hue || 'blue'];
  return (px) => {
    const d = -px.d;
    const white = smooth(0, q.at, d) * (1 - smooth(q.at + q.core, q.at + q.core + q.fade * 0.55, d));
    const light = 1 - smooth(q.at + q.core + q.fade * 0.35, q.at + q.core + q.fade, d);
    ramp(255 * white, px);
    px.r *= light; px.g *= light; px.b *= light;
    px.a = smooth(-0.02, q.at * 0.6, d);
  };
};
// The dark figure drawn (no black border: its light is its edge). Returns the bust's shape; H.darkInside(pl, o) gives
// the black inside (for laying eyes on it).
const dark = (c, pl, o = {}) => {
  const sh = shape(pl, o), fb = c.field(darkInside(pl, o)), ramp = ramps[o.hue || 'blue'];
  c.fill(sh, (px) => {
    const db = fb[px.i];                                             // the distance to the black, outside it
    ramp(255 * smooth(0.12, 0.6, db), px);
    const light = smooth(-0.3, 0.22, db);
    px.r *= light; px.g *= light; px.b *= light;
    px.a = smooth(-0.02, 0.18, -px.d);
  });
  return sh;
};

// ---- a glow behind the bust ------------------------------------------------------------------------------------------
// A soft light round a shape: its opacity falls off with the distance d from the shape's outline as
// strength * (1 - d / reach) ^ power, and its colour pales with its opacity (colours: [[opacity, colour], ...]).
// weigh(x, y): a factor per place (default 1), e.g. to let the glow die away below the head.
const glow = (c, sh, { reach, strength = 1, power = 1, colours, weigh = null }) => {
  const ramp = P.ramp(colours);
  c.fill(sh, (px) => {
    const d = Math.max(px.d + reach, 0);                               // (the shape is laid `reach` larger: px.d is measured from there)
    let a = strength * Math.pow(clamp(1 - d / reach, 0, 1), power);
    if (weigh) a *= weigh(px.x, px.y);
    ramp(a, px); px.a = a;
  }, reach);
};

module.exports = { DIM, BORDER, INK, CHEST, SHOULDERS, LINE, halfOutline, outline, outlinePts, toIcon, shape, shader, bust, darkShader, dark, glow, ramps, smooth,
  head, headPts, clipped, darkInside };
