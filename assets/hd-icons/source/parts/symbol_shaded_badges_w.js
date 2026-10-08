'use strict';
// The other weapons of the weapon badges (rifle, grenade, heavy weapon, lightsaber hilt, the three blades, the
// sword), the brighter gears and the other toughness badges. The badges, the house body and the pistol are in
// parts/symbol_shaded_badges.js.
//
// Each weapon is ONE construction used on its three badges, measured on the GAME's drawings of it: the silhouette
// read off the pixels (tools/badges_vsil.py), measured along its own axis (tools/badges_vaxis.py: lengths, widths,
// where the white pixels lie), and the outline's placement found where it covers the silhouette best
// (tools/badges_fit.py). The game's drawings are a few pixels across and blobby; what each one IS decides the
// outline (a rifle with a grip, a hilt, a ball), the game's pixels its proportions and where its lights lie.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');
const W = require('./weapons');
const B = require('./symbol_shaded_badges');

const { hypot, atan2, abs, min, max, cos, sin, PI } = Math;
const { lin, mix3, put, smooth, bell, X, Y, SHRINK } = B;
const { clamp } = S;

// a light along a line in an object's frame: from (t0, s) to (t1, s), half-width hw
const streak = (c, f, t0, t1, s, hw, o = {}) => {
  const p = f.pt(t0, s), q = f.pt(t1, s);
  return B.lightOn(c, S.capsule(p[0], p[1], q[0], q[1], 2 * hw * f.k), o);
};

// ---- the blaster rifle (02) --------------------------------------------------------------------------------------------
// Frame: t from the muzzle back along the rifle, s across (below is positive). In the game it is a thick bar from the
// upper left to the lower right, 27 long, with a grip hanging straight down on screen under its rear half; its
// rear end is cut off at an angle. Measured on the focus badge's drawing: the bar 4.4 wide at the muzzle and 5.5
// at the rear; the grip 5 wide, its foot 8.3 below the axis. The outline covers the game's silhouette to 81 per
// cent, lying at 31.5 degrees. The game's white: a line along the upper side of the rear two thirds, and a pixel
// behind the muzzle.
// What it is decides one thing the game's blob does not show: the barrel in front is thinner than the body behind
// it (the underside steps up 8 from the muzzle), so that it reads as a rifle and not as a bar. The outline then
// covers the game's silhouette to 77 per cent instead of 81 (tools/badges_fit.py).
const RIFLE = [[0, -2.2], [24.0, -3.2], [25.6, -1.6], [25.6, 1.0], [24.2, 2.3], [20.8, 2.3], [23.3, 6.4], [19.4, 8.3], [15.8, 2.3], [8.6, 2.3], [7.6, 0.5], [0, 0.4]];
const rifle = (c, f, paint, o = {}) => {
  const cb = lin(paint.body), cs = lin(paint.shade), pale = lin(paint.pale);
  const over = B.lights(streak(c, f, 10.5, 22.6, -1.0, 0.42, { glow: pale, halo: 0.45 }), streak(c, f, 1.6, 2.8, -0.9, 0.36, { glow: pale, halo: 0.35 }));
  // lit along its middle, in shade along its upper edge (the game's upper rows are the deeper blue) and on the grip
  const tone = (px) => {
    const t = f.t(px.x, px.y), s = f.s(px.x, px.y);
    return mix3(mix3(cb, cs, 0.7 * smooth(-1.5, -2.9, s)), cs, 0.6 * smooth(2.6, 4.2, s));
  };
  return B.body(c, f.pts(RIFLE), { ink: paint.ink, pal: paint, tone, over, part: o.part });
};

// ---- the heavy weapon (04) ---------------------------------------------------------------------------------------------
// In the game: a long barrel from the upper left into a thicker body, a block on top of the body's front (its
// carrying handle), a grip hanging down under the rear, the rear end bevelled. Measured on the focus badge's
// drawing (frame as the rifle's): barrel 11.5 long and 3.8 wide, body to 27 and 5.5 wide, the handle from 12.6 to
// 18.4 and 1.6 high, the grip's foot 8.3 below the axis. The outline covers the game's silhouettes to 81 and 84 per
// cent, lying at 27 degrees. The game's white: on the barrel before the body, and twice on the body.
const HEAVY = [[0, -1.8], [11.5, -2.2], [12.6, -4.4], [18.4, -4.4], [19.4, -2.8], [25.5, -3.0], [27.0, -1.5], [27.0, 1.2], [25.5, 2.5], [23.4, 2.5], [25.6, 6.6], [22.1, 8.3], [19.0, 2.5], [0, 2.0]];
const heavy = (c, f, paint, o = {}) => {
  const cb = lin(paint.body), cs = lin(paint.shade), pale = lin(paint.pale);
  const over = B.lights(streak(c, f, 7.5, 10.8, 0.2, 0.42, { glow: pale, halo: 0.45 }), streak(c, f, 15.0, 19.0, -0.6, 0.5, { glow: pale, halo: 0.45 }),
    streak(c, f, 21.4, 24.4, -0.9, 0.45, { glow: pale, halo: 0.4 }));
  const tone = (px) => {
    const s = f.s(px.x, px.y);
    return mix3(mix3(cb, cs, 0.65 * smooth(-2.0, -3.4, s)), cs, 0.6 * smooth(2.8, 4.4, s));
  };
  return B.body(c, f.pts(HEAVY), { ink: paint.ink, pal: paint, tone, over, part: o.part });
};

// ---- the lightsaber's hilt (05) ----------------------------------------------------------------------------------------
// In the game: a rod with round ends lying at 45 degrees, 26.8 long and 7.6 across with its outline (focus badge):
// 19.2 between the middles of its two round ends, 2.8 in radius. The outline covers the game's silhouette to 93 per
// cent (focus; on the proficiency badge the game's is slimmer and lies 0.85 the size). The game's white: a line
// along the middle of its lower right half, and two pixels near its upper left end.
const HILT = { L: 19.2, r: 2.8 };
const hilt = (c, f, paint, o = {}) => {
  const m = HILT, a = f.pt(0, 0), b = f.pt(m.L, 0), deg = f.deg;
  const pts = [...G.arcPts(a[0], a[1], m.r * f.k, deg + 90, deg + 270), ...G.arcPts(b[0], b[1], m.r * f.k, deg - 90, deg + 90)];
  const cb = lin(paint.body), cs = lin(paint.shade), pale = lin(paint.pale);
  const over = B.lights(streak(c, f, 9.6, 19.6, 0, 0.5, { glow: pale, halo: 0.5 }), streak(c, f, -0.5, 0.1, 0, 0.42, { glow: pale, halo: 0.35 }),
    streak(c, f, 2.4, 2.9, 0, 0.42, { glow: pale, halo: 0.35 }));
  // a band of shade across it a third of the way along (the game's deeper pixels between its end and the line of light)
  const tone = (px) => mix3(cb, cs, 0.75 * bell(f.t(px.x, px.y) - 5.6, 1.7));
  return B.body(c, pts, { ink: paint.ink, pal: paint, tone, over, part: o.part });
};

// ---- the grenade (03) --------------------------------------------------------------------------------------------------
// In the game: a ball in a dark ring, 7.6 in radius on the focus badge, 7.1 on proficiency and 5.3 inside the
// specialisation badge's ring; lit from the left (its white pixels lie left of its middle), deeper to the lower
// right. Drawn as a ball: the house body with one soft light and the shade opposite it. The mottling of the game's
// ball is its texture and is left out.
const grenade = (c, at, r, paint, o = {}) => {
  const [cx, cy] = B.shrunk(at), R = r * SHRINK, cb = lin(paint.body), cs = lin(paint.edge), pale = lin('#ffffff');
  const tone = (px) => {
    const dx = (px.x - cx) / R, dy = (px.y - cy) / R;
    const v = mix3(cb, cs, 0.85 * smooth(-0.2, 1.1, 0.75 * dx + 0.55 * dy));
    return mix3(v, pale, 0.95 * bell(hypot(dx + 0.42, dy + 0.12), 0.3) + 0.5 * bell(hypot(dx + 0.05, dy + 0.5), 0.16));
  };
  return B.body(c, G.arcPts(cx, cy, R, 0, 360).slice(1), { ink: paint.ink, pal: paint, tone, depth: 0.9, part: o.part });
};

// ---- swords (07, and the three blades of 06) -----------------------------------------------------------------------------
// The game's sword on the weapon badges is the blue sword of the flat symbols seen small: a blade with a line of
// light down its middle, white where the guard crosses. It is drawn by the same construction (parts/weapons.js),
// in the badge's ink. Measured on the game's drawing (tools/badges_vaxis.py): from its grip's end to its point 25.0
// at 47.9 degrees; the guard 4.0 from the grip's end and 7.4 long; blade and outline together 3.75 wide.
const SWORD = { pommel: 0.8, grip: 1.7, guardAt: 4.0, guard: 7.4, guardT: 1.5, guardPoint: 0.7, blade: 1.75, taper: 1.5 };
// E: the grip's end, T: the point (the game's pixels); st: palette (see parts/weapons.js), part
const sword = (c, E, T, paint, o = SWORD, st = {}) => {
  const e = B.shrunk(E), t = B.shrunk(T), f = G.frame(e, t), k = SHRINK;
  const oo = {}; for (const key of Object.keys(o)) oo[key] = o[key] * k;
  // (the outline is laid here and not by the sword's own routine: its point is cut shorter, so that it does not
  // reach over the badge's edge)
  if (st.part !== 'body') c.fill(S.polygon(G.offsetPts(f.pts(W.swordOutline(f.L, oo)), B.W_OUTLINE, 1.5)), P.flat(paint.ink));
  if (st.part === 'border') return f;
  W.glowSword(c, e, t, oo, { palette: st.palette || 'blue', border: 0, core: 0.17, coreEnd: 1.2 * k, coreTaper: 1.6 * k, halo: 0.34, side: st.side || 1, part: 'body' });
  return f;
};

// The three blades (06). In the game: three white swords standing in a fan, their points up (the middle one
// upright, 14.3 long, from (16, 15.6) to (16, 1.3); the outer two leaning 18 degrees outwards, 12.4 long), and under
// them the same three again upside down and paler: their reflection, mirrored about the level 16.9.
// The swords reach over the badge's edge: all the outlines are laid first, then the badge's face is NOT drawn over
// them, and no dark edge cuts into a neighbour.
const BLADES = { mid: [[16, 15.6], [16, 1.3]], side: [[9.7, 16.3], [5.9, 4.5]], mirror: 16.9 };
const BLADE = { pommel: 0.6, grip: 1.5, guardAt: 3.3, guard: 6.0, guardT: 1.3, guardPoint: 0.6, blade: 1.7, taper: 1.6 };
const WHITE_SWORD = { rim: '#1c48f0', edge: '#9fb3ff', body: '#eef2ff', lit: '#ffffff', glow: '#ffffff', gripFar: '#b9c7ff', guardEdge: '#dbe3ff', core: '#ffffff', coreEnd: '#ffffff' };
const PALE_SWORD = { rim: '#3760ff', edge: '#7491ff', body: '#b9c7ff', lit: '#c9d4ff', glow: '#dbe3ff', gripFar: '#9cb1ff', guardEdge: '#a9bbff', core: '#dbe3ff', coreEnd: '#c9d4ff' };
const blades = (c, paint, face) => {
  const q = BLADES, flip = ([x, y]) => [x, 2 * q.mirror - y], across = ([x, y]) => [32 - x, y];
  const upper = [[q.side[0], q.side[1]], [across(q.side[0]), across(q.side[1])], [q.mid[0], q.mid[1]]];
  const lower = upper.map(([e, t]) => [flip(e), flip(t)]);
  // the reflections lie on the face only: drawn on a sheet of their own and cut by the face's edge
  c.layer((t) => {
    for (const part of ['border', 'body']) for (const [e, p] of lower) sword(t, e, p, { ink: '#2450f8' }, BLADE, { palette: PALE_SWORD, part });
  }, { mask: face });
  for (const part of ['border', 'body']) for (const [e, p] of upper) sword(c, e, p, { ink: paint.ink }, BLADE, { palette: WHITE_SWORD, part });
};

// ---- the brighter gears -------------------------------------------------------------------------------------------------
// gearhead02 in the game is the gear with three things of white: a ring one pixel wide round the wheel just inside
// the teeth (radius 11 to 12.3), the outer two pixels of the four upright and level teeth, and its middle (a white
// disc of radius 3 in place of the light ring and the hole). gearhead03 has the ring and the teeth, a white lip
// round a dark hole, and a lighter cross along the two axes, as wide as a tooth, from the lip out to the teeth.
const gearLights = (c, { ring = true, tips = true, middle = null, cross = false } = {}) => {
  const m = B.GEAR, k = c.k, white = B.WHITE, shape = S.polygon(B.gearOutline(m)), inside = S.polygon(G.offsetPts(B.gearOutline(m), -0.13));
  if (cross) {
    const bars = S.intersect(S.union(S.box(X, Y, 16, m.hw - 0.2), S.box(X, Y, m.hw - 0.2, 16)), inside, S.invert(S.circle(X, Y, m.lip[1])));
    c.fill(bars, P.flat('#ffffff', 0.5));
  }
  if (ring) c.fill(S.ring(X, Y, 11.65, 1.1), P.flat('#ffffff'));
  if (tips) c.fill(S.intersect(S.union(S.box(X, Y, 16, m.hw - 0.13), S.box(X, Y, m.hw - 0.13, 16)), inside, S.invert(S.circle(X, Y, m.tip - 2.1))), P.flat('#ffffff'));
  if (middle === 'white') c.fill(S.circle(X, Y, m.lip[1]), (px) => put(px, mix3(white, lin('#5f80ff'), smooth(m.lip[1] - 0.8, m.lip[1], hypot(px.x - X, px.y - Y)))));
  if (middle === 'lip') {
    c.fill(S.circle(X, Y, m.lip[1] - 0.3), P.flat('#ffffff'));
    c.fill(S.circle(X, Y, 2.0), P.flat(B.GEAR_PAINT.hole));
  }
  return shape;
};

// ---- the other toughness badges -------------------------------------------------------------------------------------------
// toughn01 in the game: a deep blue face (001b80) out to radius 14.0 and white from there to the badge's edge, with
// no black border; toughn03: white all through. (The game's edge is soft; here it is the common outer circle.)
const whiteBadge = (c, face = null) => {
  c.fill(S.circle(X, Y, B.R_OUT), P.flat('#ffffff'));
  if (face) c.fill(S.circle(X, Y, B.R_RIM0), P.flat(face));
};

module.exports = { streak, RIFLE, rifle, HEAVY, heavy, HILT, hilt, grenade, SWORD, sword, BLADES, BLADE, blades, gearLights, whiteBadge };
