'use strict';
// The round badges of the sheet symbol_shaded_badges, and the objects that lie on them.
//
// HOW TO USE (for every file that draws on these badges; the names and call signatures here stay as they are):
//
//   const B = require('../parts/symbol_shaded_badges');
//   B.focusBadge(c);                  the periwinkle disc in a black border (weapon focus)
//   B.focusBadge(c, { flat: true });  the same with the flat, lighter face (toughness)
//   B.profBadge(c);                   deep blue disc, lighter ring, white rim and crosshair (weapon proficiency)
//   B.specBadge(c);                   pale disc with a white ring and crosshair (weapon specialisation)
//
//   Radii, all about the centre (B.X, B.Y) = (16, 16):
//     B.R_OUT   15.9   the outer edge of every badge (whole, inside the frame)
//     B.R_DISC  13.95  the blue disc's edge on the focus and specialisation badges (black from there to R_OUT);
//                      the last B.W_EDGE (0.7) inside it is a deep blue line: keep objects inside R_DISC - W_EDGE
//     B.R_RIM0  13.62, B.R_RIM1 14.6   the proficiency badge's white rim; its disc lies inside R_RIM0
//     B.R_INNER 10.18  the proficiency badge's darker inner disc
//     B.R_RING  7.88, B.W_RING, B.W_CROSS   the specialisation badge's ring, and the white lines' width
//
//   Where an object sits: the game's icons are the authority, and the game's badge is larger than the frame (outer
//   radius 16.34, cut flat on four sides). Here the badge is whole, so everything on it is the game's shrunk by
//   B.SHRINK (0.973) about the centre: read a position off the game's pixels and pass it through B.shrunk([x, y]),
//   or place a construction with B.placeGame(E, deg, k) (E in the game's pixels).
//   An object on a badge: its outline (B.W_OUTLINE wide, in the badge's ink B.PAINT.<kind>.ink) is laid on the
//   badge's face, then its body: B.body(c, points, { ink, pal }) does both in the house style.
//
// Everything is constructed from the GAME's icons (their pixels read with tools/badges_vhex.py, badges_vprofile.py,
// badges_vsil.py): circles about one centre, straight lines, polygons; borders are the same outlines moved out by
// one width; shading is soft and structural (a colour deepening to the edge of a shape with a thin dark line along
// it, a lit side and a shaded side, the lights the game's icon shows). ChatGPT's redraws were used to recognise what
// a thing is, not for its shape. Units: the game's pixels (frame 32 x 32, y down).
//
// Changed from the game, on every badge: there the badge's border runs out of the frame (the border's outer edge
// lies at radius 16.34 and the frame cuts it flat on all four sides). Here the border is whole and of one width, and
// to make room the badge with everything on it is 2.7 per cent smaller (SHRINK).
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');

const { hypot, atan2, abs, min, max, exp, cos, sin, sqrt, asin, PI } = Math;
const { clamp } = S;

// ---- colour arithmetic (linear light) ------------------------------------------------------------------------------
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c, a = 1) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = a; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bell = (d, w) => exp(-(d * d) / (w * w));
// a ramp of measured colours: stops [[t, colour], ...], t rising -> (t) => colour in linear light
const ramp3 = (stops) => {
  const ts = stops.map((s) => s[0]), cs = stops.map((s) => lin(s[1]));
  return (t) => {
    let i = 0;
    while (i < ts.length - 2 && t > ts[i + 1]) i++;
    return mix3(cs[i], cs[i + 1], clamp((t - ts[i]) / (ts[i + 1] - ts[i] || 1e-9), 0, 1));
  };
};
// a value read off a table [[x, y], ...] (x rising), straight between its entries
const table = (rows) => (x) => {
  if (x <= rows[0][0]) return rows[0][1];
  for (let i = 1; i < rows.length; i++) if (x <= rows[i][0]) return rows[i - 1][1] + ((rows[i][1] - rows[i - 1][1]) * (x - rows[i - 1][0])) / (rows[i][0] - rows[i - 1][0]);
  return rows[rows.length - 1][1];
};
// The game's blue. Every blue of these icons lies on one line: red L, green 52.5 + 0.79 L, blue 255 (b8c6ff, 9cb1ff,
// 7491ff, 5074ff, 2854ff all fit it to within two levels). A blue is named here by its level L, the red it has.
const blue = (L) => lin([clamp(L, 0, 255) / 255, clamp(52.5 + 0.79 * L, 0, 255) / 255, 1]);

const WHITE = lin('#ffffff');
const INK = '#0a0a0c';                    // the house black

// ---- the badge: measures -------------------------------------------------------------------------------------------
const X = 16, Y = 16;
const R_OUT = 15.9;                       // the border's outer edge (kit: W.edge)
// The game's border ends at radius 16.34 (where its opacity falls through one half; 16.32 to 16.37 on four icons).
const SHRINK = R_OUT / 16.34;
// The blue disc inside the black border. In the game its edge (where blue falls through one half) lies at 14.2 on
// the focus badges (14.17 to 14.26) and at 14.47 on the specialisation badges; the two borders are drawn alike here,
// from the middle of the two.
const R_DISC = 13.95;
// Just inside the edge the game's disc is a deeper blue for one pixel (focus 13.3 to 14.2, specialisation 13.77 to
// 14.47, proficiency 15.0 to 15.7): the thin dark line along the edge. Its colour: 204cf7 to 2e59ff where a pixel
// holds nothing else.
const W_EDGE = 0.7;
// The proficiency badge. In the game: the white rim from 14.0 to 15.0, a deep blue line from there to 15.7, black
// to the outer edge; the darker inner disc ends at 10.46.
const R_RIM0 = 14.0 * SHRINK, R_RIM1 = 15.0 * SHRINK, R_PROF = 15.7 * SHRINK;
const R_INNER = 10.46 * SHRINK, INNER_SOFT = 0.3;
// The white lines: one pixel wide in the game (crosshair and ring alike), the ring at radius 8.1.
const W_CROSS = 1.0 * SHRINK, W_RING = 1.0 * SHRINK, R_RING = 8.1 * SHRINK;
// Every object on a badge has a dark outline one pixel wide in the game.
const W_OUTLINE = 1.0;

// game coordinates -> the drawing's (the badge and all on it drawn SHRINK smaller about the centre)
const shrunk = (p) => [X + SHRINK * (p[0] - X), Y + SHRINK * (p[1] - Y)];
const shrunkPts = (pts) => pts.map((p) => [X + SHRINK * (p[0] - X), Y + SHRINK * (p[1] - Y), ...p.slice(2)]);

// ---- the badge: edge and light -------------------------------------------------------------------------------------
// The line of light the specialisation badge carries just inside its edge. In the game the disc's outermost pale
// pixels are lighter than its face: near white at the left (f1f4ff, fefeff at 160 to 205 degrees; 0 = right, 90 =
// down), a little lighter all round the top and the right (d4ddff to e2e8ff), not at all along the bottom.
const lit = (x, y) => {
  const a = ((atan2(y - Y, x - X) * 180) / PI + 360) % 360, off = (b) => abs(((a - b + 540) % 360) - 180);
  return (0.4 + 0.55 * (1 - smooth(15, 55, off(180)))) * smooth(25, 60, off(90));
};
const LINE = lin('#2450f8'), LINE_OUT = lin('#1238d6');
const RIM_Q = 1.2, RIM_W = 0.42;          // where that light lies (its depth inside the edge), and how wide it is
// The edge of a disc: v is the face's colour there, q the depth inside the disc's edge, h the strength of the light
// along the edge (0 = none). The face gives way to the deep line over a quarter of a unit.
const discEdge = (v, q, h = 0) => {
  if (h > 0) v = mix3(v, WHITE, h * bell(q - RIM_Q, RIM_W));
  if (q < W_EDGE + 0.25) v = mix3(mix3(LINE_OUT, LINE, smooth(0, W_EDGE, q)), v, smooth(W_EDGE, W_EDGE + 0.25, q));
  return v;
};
const border = (c) => c.fill(S.circle(X, Y, R_OUT), P.flat(INK));
// how far a place lies towards the lower left of the centre (units): the side the game's badges are lit from
const lowerLeft = (x, y) => ((X - x) + (y - Y)) * Math.SQRT1_2;

// ---- the focus badge -------------------------------------------------------------------------------------------------
// The game's face (seven weapon focus icons, the pixel-wise median; tools/badges_vmedian.py, badges_vprofile.py):
// level 175 in the middle, deepening towards the edge (at radius 8.25: 169, 9.75: 165, 10.75: 157, 11.75: 144,
// 12.25: 134, 12.75: 123), and lit from the lower left: 1.2 levels lighter for every pixel that way (lower left at
// radius 9.75 b0c0ff, upper right 9bb0ff). The toughness badge's face is flat instead: b9c7ff out to its edge.
const FOCUS_LEVEL = table([[0, 175], [6.8, 174], [8.0, 170], [9.5, 165], [10.5, 157], [11.4, 144], [11.9, 134.5], [12.4, 123], [13.0, 108]]);
const FOCUS_LIGHT = 1.2 / SHRINK, FLAT_LEVEL = 185;
const focusBadge = (c, o = {}) => {
  border(c);
  c.fill(S.circle(X, Y, R_DISC), (px) => {
    const r = hypot(px.x - X, px.y - Y);
    const v = o.flat ? blue(FLAT_LEVEL) : blue(FOCUS_LEVEL(r) + FOCUS_LIGHT * lowerLeft(px.x, px.y));
    put(px, discEdge(v, R_DISC - r, 0));
  });
};

// ---- the specialisation badge ----------------------------------------------------------------------------------------
// The game's face is pale and flat (c2cfff, level 194). The white ring and crosshair are one white shape. Either
// side of every white line the game's face is deep blue for one pixel (305bff to 5377ff) and a little deepened for
// a second (b1c1ff): the share of that blue at distance d from a line is taken as exp(-((d - 0.25) / 1.1)^2).
// Inside the ring nothing else is drawn: the fringes of ring and crosshair meet there.
const SPEC_LEVEL = 194, FRINGE = blue(59), FRINGE_AT = 0.25, FRINGE_W = 1.1;
const specBadge = (c) => {
  border(c);
  const k = c.k, face = blue(SPEC_LEVEL);
  c.fill(S.circle(X, Y, R_DISC), (px) => {
    const dx = px.x - X, dy = px.y - Y, r = hypot(dx, dy);
    const d = min(min(abs(dx), abs(dy)) - W_CROSS / 2, abs(r - R_RING) - W_RING / 2);     // to the white lines' edge
    let v = mix3(face, FRINGE, bell(max(d - FRINGE_AT, 0), FRINGE_W));
    v = mix3(v, WHITE, clamp(0.5 - d * k, 0, 1));
    put(px, discEdge(v, R_DISC - r, lit(px.x, px.y)));
  });
};

// ---- the proficiency badge ---------------------------------------------------------------------------------------------
// The game's inner disc: level 40 at the centre (2854ff), 51 at radius 4.5, 55 at 6.5, 62 at 8.75, 74 at 9.75; the
// ring round it level 140 at its inner side, 125 at the rim, and lit from the lower left like the focus badge's face
// (one level for every pixel). No fringe beside its white lines. The crosshair runs into the rim: one white piece.
const PROF_INNER = table([[0, 40], [4.4, 51], [6.3, 55], [8.5, 62], [9.5, 74], [10.3, 80]]);
const PROF_RING = table([[10.2, 142], [11.4, 140], [12.9, 125], [13.7, 122]]);
const PROF_LIGHT = 1.0 / SHRINK;
const profBadge = (c) => {
  border(c);
  c.fill(S.circle(X, Y, R_PROF), (px) => put(px, mix3(LINE_OUT, LINE, smooth(R_PROF, R_RIM1, hypot(px.x - X, px.y - Y)))));
  c.fill(S.circle(X, Y, R_RIM1), P.flat('#ffffff'));
  c.fill(S.circle(X, Y, R_RIM0), (px) => {
    const r = hypot(px.x - X, px.y - Y);
    put(px, mix3(blue(PROF_INNER(r)), blue(PROF_RING(r) + PROF_LIGHT * lowerLeft(px.x, px.y)), smooth(R_INNER - INNER_SOFT, R_INNER + INNER_SOFT, r)));
  });
  const mid = (R_RIM0 + R_RIM1) / 2;
  c.fill(S.intersect(S.union(S.box(X, Y, 16, W_CROSS / 2), S.box(X, Y, W_CROSS / 2, 16)), S.circle(X, Y, mid)), P.flat('#ffffff'));
};

// ---- placing an object -------------------------------------------------------------------------------------------------
// An object is constructed in its own frame (t along its axis from its front end, s across, positive to the right of
// that direction on screen) and placed by where its front end lies, its angle and its size.
const place = (E, deg = 0, k = 1) => {
  const ux = cos((deg * PI) / 180), uy = sin((deg * PI) / 180), nx = -uy, ny = ux;
  const pt = (t, s) => [E[0] + k * (ux * t + nx * s), E[1] + k * (uy * t + ny * s)];
  return {
    E, deg, k, pt, pts: (list) => list.map(([t, s]) => pt(t, s)),
    t: (x, y) => ((x - E[0]) * ux + (y - E[1]) * uy) / k,
    s: (x, y) => ((x - E[0]) * nx + (y - E[1]) * ny) / k,
  };
};
// the same from where the object lies in the GAME's icon: position and size are shrunk with the badge
const placeGame = (E, deg = 0, k = 1) => place(shrunk(E), deg, k * SHRINK);
// the line through a and b moved d to its left (on screen, looking from a to b); where two lines meet
const moved = (a, b, d) => { const l = hypot(b[0] - a[0], b[1] - a[1]), nx = (b[1] - a[1]) / l, ny = -(b[0] - a[0]) / l; return [[a[0] + nx * d, a[1] + ny * d], [b[0] + nx * d, b[1] + ny * d]]; };
const meet = ([a, b], [c2, e]) => {
  const rx = b[0] - a[0], ry = b[1] - a[1], sx = e[0] - c2[0], sy = e[1] - c2[1], den = rx * sy - ry * sx;
  const u = ((c2[0] - a[0]) * sy - (c2[1] - a[1]) * sx) / den;
  return [a[0] + rx * u, a[1] + ry * u];
};

// ---- the house body ----------------------------------------------------------------------------------------------------
// What an object is painted with. The outline's colour depends on the badge, as in the game (the pistol's outline is
// 0020a0 on the focus badge, 001468 on proficiency, 000b38 on specialisation; the arm's is charcoal). The body is
// the same everywhere:  rim  the thin dark line along its edge;  edge  the colour just inside it;  body  its
// middle;  shade  its shaded side;  pale  its lights' glow.  (The other keys are kept for files that read them.)
const BODY = { rim: '#0c2fc8', edge: '#3760ff', body: '#a9bbff', shade: '#5f80ff', pale: '#dbe3ff' };
const OLD = { light: BODY.body, mid: BODY.shade, deep: BODY.edge, top: BODY.edge, low: BODY.shade, band: BODY.pale, slot: '#2452f8' };
const PAINT = {
  focus: { ink: '#00209c', ...BODY, ...OLD },
  prof: { ink: '#001468', ...BODY, ...OLD },
  spec: { ink: '#000b38', ...BODY, ...OLD },
};
// A body in the house style (as parts/flat.js and the swords of parts/weapons.js have it): its outline moved out by
// `border` with the corners kept sharp, in the ink; its colour deepening to its edge over `depth`; a thin dark line
// (`rim` wide) along the edge.
//   pts     the outline's points, in order
//   o.ink, o.border, o.pal ({ rim, edge, body }), o.depth, o.rim, o.limit (see geom.offsetPts)
//   o.tone  (px) => the middle's colour there, in linear light (for a lit and a shaded side)
//   o.over  (px, v) => v with the object's lights laid over it
//   o.part  'border' draws only the outline, 'body' everything but it: objects that overlap get all their outlines
//           first and then their bodies, so that no dark edge cuts into a neighbour
const body = (c, pts, o = {}) => {
  const pal = o.pal || BODY, w = o.border === undefined ? W_OUTLINE : o.border, depth = o.depth || 0.9, rim = o.rim === undefined ? 0.13 : o.rim;
  const shape = S.polygon(pts);
  if (w > 0 && o.part !== 'body') c.fill(S.polygon(G.offsetPts(pts, w, o.limit)), P.flat(o.ink || INK));
  if (o.part === 'border') return shape;
  const k = c.k, cr = lin(pal.rim), ce = lin(pal.edge), cb = lin(pal.body);
  c.fill(shape, (px) => {
    let v = mix3(ce, o.tone ? o.tone(px) : cb, smooth(0, depth, -px.d));
    if (o.over) v = o.over(px, v);
    put(px, mix3(v, cr, clamp((rim + px.d) * k + 0.5, 0, 1)));
  });
  return shape;
};
// A light lying on a body: a crisp shape in `core` with a soft glow of `glow` round it (reach `halo`).
const lightOn = (c, shape, { core = WHITE, glow = null, halo = 0.4, strength = 0.75 } = {}) => {
  const f = c.field(shape), k = c.k;
  return (px, v) => {
    const d = f[px.i];
    if (d > 3 * halo + 0.1) return v;
    if (glow) v = mix3(v, glow, strength * bell(max(d, 0), halo));
    return mix3(v, core, clamp(0.5 - d * k, 0, 1));
  };
};
const lights = (...list) => (px, v) => { for (const l of list) v = l(px, v); return v; };

// ---- the blaster pistol ------------------------------------------------------------------------------------------------
// Its frame: t from the muzzle back along the barrel's axis, s across (below the barrel is positive).
// The game draws it twice: level on the focus badge, and turned on the proficiency badge (the specialisation badge
// carries the proficiency badge's drawing moved 2 left and 1 down, pixel for pixel). The two drawings differ a
// little (the level one has the thicker barrel and the more upright grip); their silhouettes were read off the
// pixels (tools/badges_vsil.py) and ONE outline fitted to both at once (tools/badges_pistolfit.py): it covers the
// level drawing to 87 per cent at 1.134 times the size and the turned one to 90 per cent, turned 22.5 degrees.
// The fitted dimensions, rounded to a tenth:
const PISTOL = {
  barrel: 8.2, hb: 1.7,                   // the barrel's length and half-width
  top: 4.7, back: 17.8,                   // the receiver's top edge above the axis; where it ends
  tail: [20.0, 0.5],                      // the back strap's tip
  notch: [18.3, 2.1],                     // where the grip's rear edge starts
  toe: [17.5, 9.4],                       // the grip's front lower corner
  gripDeg: 64, heelDeg: -23,              // the grip's edges and its lower edge, measured from the barrel's axis
  guard: 3.5, slope: 10.9,                // the underside at the trigger guard; where the slope down to it ends
  // What lies on it: only what the game's pixels show.
  light: [1.0, 7.2, 0.45],                // the white along the barrel (game: seven pixels in a row): from, to, half-width
  sight: [9.7, 10.6, -3.45, 0.32],        // the white pixel on the receiver's upper front: from, to, across, half-width
  plate: [19.0, 6.75, 0.7, 0.42],         // the white on the grip's foot (two pixels): middle (along, across), half-length, half-width
  trigger: [12.2, 14.0, 2.75, 0.36],      // the deep strip under the receiver (game: four pixels): from, to, across, half-width
};
const pistolOutline = (m = PISTOL) => {
  const g = (m.gripDeg * PI) / 180, h = (m.heelDeg * PI) / 180;
  const rear = [m.notch, [m.notch[0] + cos(g), m.notch[1] + sin(g)]], front = [m.toe, [m.toe[0] + cos(g), m.toe[1] + sin(g)]];
  const heel = meet(rear, [m.toe, [m.toe[0] + cos(h), m.toe[1] + sin(h)]]);
  const gripTop = meet(front, [[0, m.guard], [1, m.guard]]);
  return {
    heel, gripTop,
    pts: [[0, -m.hb], [m.barrel, -m.hb], [m.barrel, -m.top], [m.back, -m.top], m.tail, m.notch, heel, m.toe, gripTop, [m.slope, m.guard], [m.barrel, m.hb], [0, m.hb]],
  };
};
// f: its placement (place / placeGame); paint: one of PAINT; o.part as in body()
const pistol = (c, f, paint, m = PISTOL, o = {}) => {
  const out = pistolOutline(m), cb = lin(paint.body), cs = lin(paint.shade), pale = lin(paint.pale);
  const seg = (a, b, hw) => { const p = f.pt(a[0], a[1]), q = f.pt(b[0], b[1]); return S.capsule(p[0], p[1], q[0], q[1], 2 * hw * f.k); };
  const h = (m.heelDeg * PI) / 180, along = [cos(h) * m.plate[2], sin(h) * m.plate[2]], pc = [m.plate[0], m.plate[1]];
  const over = o.part === 'border' ? null : lights(
    lightOn(c, seg([m.trigger[0], m.trigger[2]], [m.trigger[1], m.trigger[2]], m.trigger[3]), { core: lin(paint.slot) }),
    lightOn(c, seg([m.light[0], 0], [m.light[1], 0], m.light[2]), { glow: pale, halo: 0.45 }),
    lightOn(c, seg([m.sight[0], m.sight[2]], [m.sight[1], m.sight[2]], m.sight[3]), { glow: pale, halo: 0.35 }),
    lightOn(c, seg([pc[0] - along[0], pc[1] - along[1]], [pc[0] + along[0], pc[1] + along[1]], m.plate[3]), { glow: pale, halo: 0.35 }));
  // lit above and in front, shaded below and behind (in the game the receiver's lower rear and the grip are the
  // deeper blue, with a band of shade before the back strap and a lighter strip along it)
  const lean = (m.tail[0] - m.back) / (m.tail[1] + m.top);          // how the rear face leans
  const tone = (px) => {
    const t = f.t(px.x, px.y), s = f.s(px.x, px.y);
    let v = mix3(cb, cs, 0.8 * smooth(0.2, 2.4, s) * smooth(m.barrel + 0.6, m.barrel + 3.6, t));
    v = mix3(v, cs, 0.55 * bell(t - (m.back - 1.3), 0.9) * smooth(2.5, 0.5, s));
    return mix3(v, pale, 0.55 * bell(t - (m.back + (s + m.top) * lean - 0.75), 0.5) * smooth(-m.top + 1.2, -m.top + 2.6, s) * smooth(m.tail[1] + 0.6, m.tail[1] - 0.8, s));
  };
  return body(c, f.pts(out.pts), { ink: paint.ink, pal: paint, tone, over, part: o.part });
};

// ---- the flexed arm (toughness) ------------------------------------------------------------------------------------------
// The game's arm, read off its pixels (tools/badges_vsil.py: the silhouette row by row; badges_vhex.py: its colours):
// a fist at the upper left, the forearm straight down from it to a pointed elbow at the lower left, the upper arm
// from the elbow up to the right, ending cut upright at the shoulder, with the bicep's dome along its top. Between
// forearm and upper arm the face shows in a V down to the fold of the elbow.
// Its outline as straight lines, the corners rounded by arcs (the third number is the arc's radius). In the GAME's
// pixels; the outline grown by the one pixel of the game's border covers the game's silhouette to 89 per cent.
const ARM = [
  [7.0, 7.0, 1.7], [11.4, 7.0, 1.5],              // the fist's top
  [13.2, 9.6, 1.2], [13.2, 11.6, 1.1],            // its thumb side
  [10.0, 12.8, 0.7], [10.0, 15.5, 1.0],           // the wrist and the forearm's inner side
  [13.8, 20.8, 0],                                // the fold of the elbow
  [21.4, 12.0, 1.0], [24.1, 9.8, 2.8], [27.0, 11.7, 1.2],       // the bicep: a dome (in the game its outline stands a pixel higher in the middle)
  [27.0, 16.2, 0.5],                              // the shoulder's cut
  [12.4, 27.2, 0.9],                              // the elbow
  [8.0, 19.6, 2.5],                               // the forearm's outer side
];
// The game's colours on it: a mid blue arm (3b63ff), deep along the forearm's outer side and in the middle of the
// upper arm (1232ac, 0e3ae5), light along the forearm's inner side (97adff to c4d0ff), and white on the fist's upper
// left and on the bicep's upper left (e3e9ff, dbe2ff). Its outline is charcoal (181c2a), not blue.
const ARM_PAINT = { ink: '#171a24', rim: '#0a1f8c', edge: '#1c3fd0', body: '#3f66ff', shade: '#0f38dc', light: '#9fb3ff', pale: '#e6ecff' };
// a soft light or shade at a place given in the game's pixels: rx by ry, turned; 1 at its middle
const spot = (x, y, rx, ry, turn = 0) => {
  const [cx, cy] = shrunk([x, y]), co = cos((turn * PI) / 180), si = sin((turn * PI) / 180);
  return (px) => { const dx = px.x - cx, dy = px.y - cy, u = (dx * co + dy * si) / (rx * SHRINK), v = (-dx * si + dy * co) / (ry * SHRINK); return exp(-(u * u + v * v)); };
};
// Across each limb the game's blue runs from one side to the other as on a round body. The forearm (elbow to wrist):
// deep along its outer side (1232ac), 3b63ff in the middle, light along its inner side (97adff, c4d0ff at the edge).
// The upper arm (elbow to shoulder): light along its upper side (a3b6ff, b5c4ff), deep in the middle (1541ec,
// 0e3ae5), lighter again along its lower edge (4d72ff, 6a86f1). s: across the limb, in the game's pixels.
const FOREARM = { from: [10.9, 24.0], to: [8.6, 12.2], across: ramp3([[-1.9, '#1232ac'], [-0.7, '#3059ff'], [0.5, '#8ea5ff'], [1.7, '#c4d0ff']]) };
const UPPER_ARM = { from: [12.8, 25.3], to: [27.0, 13.9], across: ramp3([[-3.3, '#b0c0ff'], [-1.9, '#6f8cff'], [-0.3, '#1541ec'], [1.2, '#0e3ae5'], [2.4, '#4d72ff'], [3.2, '#6a86f1']]) };
const arm = (c, o = {}) => {
  const pal = { ...ARM_PAINT, ...(o.pal || {}) }, cp = lin(pal.pale);
  const pts = S.roundedPoints(ARM.map(([x, y, r]) => [...shrunk([x, y]), r * SHRINK]), 0, 0.05);
  const ff = G.frame(shrunk(FOREARM.from), shrunk(FOREARM.to)), fu = G.frame(shrunk(UPPER_ARM.from), shrunk(UPPER_ARM.to));
  const toLine = (f, x, y) => hypot(max(-f.t(x, y), 0, f.t(x, y) - f.L), f.s(x, y));
  const fist = spot(8.3, 8.5, 1.5, 1.2, -30), bicep = spot(21.9, 13.0, 1.2, 1.9, 25);
  const tone = (px) => {
    const w = smooth(-0.8, 0.8, toLine(fu, px.x, px.y) - toLine(ff, px.x, px.y));        // 1 on the forearm, 0 on the upper arm
    const v = mix3(UPPER_ARM.across(fu.s(px.x, px.y) / SHRINK), FOREARM.across(ff.s(px.x, px.y) / SHRINK), w);
    return mix3(v, cp, min(1, 0.95 * fist(px) + 0.95 * bicep(px)));
  };
  // (The game's fist has a dark line across its right half, the fold between fingers and thumb: three pixels. Drawn
  // as a line it made the fist read as a face, so it is left out; o.fold draws it.)
  const shape = body(c, pts, { ink: pal.ink, pal, tone, depth: 0.5, part: o.part });
  if (o.fold && o.part !== 'border') {
    const a = shrunk([11.6, 9.6]), b = shrunk([14.4, 9.6]);
    c.fill(S.intersect(S.bar(a[0], a[1], b[0], b[1], 0.6), shape), P.flat(pal.ink));
  }
  return shape;
};

// ---- the gear --------------------------------------------------------------------------------------------------------------
// The game's gear fills the frame and is whole (nothing of it is cut), so it is drawn at the game's size.
// Read off its pixels: eight teeth with upright sides, 6 wide, on a wheel of radius 12.2; the upright and level
// teeth's tips 14 from the centre, the four slanting ones' 15.3 (the game's gear is squarish). All eight are drawn
// alike here, 14.5; a dark outline one pixel wide. In its middle, from the outside in: a dark groove (7.6 to 8.6), a band of deep
// blue (to 5.5), a second dark groove (to 4.5), blue (to 3.7), a light ring (to 2.7), and a dark hole (2.4).
// The wheel's blue changes round the circle as on turned metal: light towards 0, 135 and 270 degrees (level 192,
// 164, 167), deep towards 67, 180 and 315 (23, 93, 73).
const GEAR = { teeth: 8, tip: 14.5, root: 12.2, hw: 3.0, groove1: [7.6, 8.6], band: 5.5, groove2: 4.5, lip: [2.7, 3.7], hole: 2.4 };
const gearOutline = (m = GEAR, cx = X, cy = Y, turn = 0) => {
  const pts = [], step = 360 / m.teeth, half = (asin(m.hw / m.root) * 180) / PI, rootT = sqrt(m.root * m.root - m.hw * m.hw);
  for (let i = 0; i < m.teeth; i++) {
    const a = turn + i * step, f = place([cx, cy], a, 1);
    pts.push(f.pt(rootT, -m.hw), f.pt(m.tip, -m.hw), f.pt(m.tip, m.hw), f.pt(rootT, m.hw));
    pts.push(...G.arcPts(cx, cy, m.root, a + half, a + step - half).slice(1, -1));
  }
  return pts;
};
// the wheel's level by direction (degrees, 0 = right, 90 = down): the game's sixteen readings at radius 10 to 12,
// joined smoothly
const SHEEN = [192, 153, 76, 23, 46, 135, 164, 108, 93, 126, 134, 129, 167, 141, 73, 106];
const sheen = (deg, list = SHEEN) => {
  const n = list.length, u = ((((deg % 360) + 360) % 360) / 360) * n, i = Math.floor(u), t = u - i, s = t * t * (3 - 2 * t);
  return list[i % n] + (list[(i + 1) % n] - list[i % n]) * s;
};
const GEAR_PAINT = { ink: '#000c38', rim: '#0c2fc8', edge: '#5f80ff', groove: '#020a2c', band: '#1a46f0', inner: '#3760ff', hole: '#000b33' };
// o.sheen: the wheel's levels by direction; o.lip: the light ring's level (middle, swing, the direction it is
// lightest towards); o.pal: colours that differ; o.m: dimensions that differ
const gear = (c, o = {}) => {
  const m = { ...GEAR, ...(o.m || {}) }, pal = { ...GEAR_PAINT, ...(o.pal || {}) }, list = o.sheen || SHEEN, k = c.k;
  const dirOf = (px) => (atan2(px.y - Y, px.x - X) * 180) / PI;
  body(c, gearOutline(m), { ink: pal.ink, pal: { rim: pal.rim, edge: pal.edge, body: '#a9bbff' }, tone: (px) => blue(sheen(dirOf(px), list)), depth: 0.6 });
  // the middle: grooves, band, lip and hole, each a circle about the centre
  const g = lin(pal.groove), band = lin(pal.band), bandIn = lin('#2854ff'), inner = lin(pal.inner), hole = lin(pal.hole), lip = o.lip || [125, 45, 285];
  c.fill(S.circle(X, Y, m.groove1[1]), (px) => {
    const r = hypot(px.x - X, px.y - Y), within = (at) => clamp(0.5 - (r - at) * k, 0, 1);
    let v = mix3(g, mix3(band, bandIn, smooth(m.groove1[0], m.band, r)), within(m.groove1[0]));
    v = mix3(v, g, within(m.band));
    v = mix3(v, inner, within(m.groove2));
    v = mix3(v, blue(lip[0] + lip[1] * cos(((dirOf(px) - lip[2]) * PI) / 180)), within(m.lip[1]));
    v = mix3(v, inner, within(m.lip[0]));
    put(px, mix3(v, hole, within(m.hole)));
  });
};

module.exports = { X, Y, R_OUT, R_DISC, R_RIM0, R_RIM1, R_INNER, W_CROSS, R_RING, W_RING, W_OUTLINE, INK, PAINT, PISTOL,
  focusBadge, specBadge, profBadge, place, moved, meet, pistol, pistolOutline, lit, discEdge,
  lin, mix3, put, smooth, bell, ramp3, WHITE,
  // added since: the shrink from the game's size, the deep line's width, the house body, lights, the arm, the gear
  SHRINK, W_EDGE, R_PROF, BODY, shrunk, shrunkPts, placeGame, blue, table, body, lightOn, lights, spot,
  ARM, ARM_PAINT, arm, GEAR, GEAR_PAINT, SHEEN, sheen, gear, gearOutline };
