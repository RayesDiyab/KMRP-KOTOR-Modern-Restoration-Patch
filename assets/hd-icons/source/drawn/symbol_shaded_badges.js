'use strict';
// Constructed drawings of the shaded badges: the 21 weapon badges, the gears and the toughness badges. The badges
// and the objects are built in parts/symbol_shaded_badges.js and parts/symbol_shaded_badges_w.js from the GAME's
// icons (what was read off their pixels is stated there); here each icon says which badge it is and where its
// object lies. Positions are given in the game's pixels and shrunk with the badge (the game's badge runs out of the
// frame; here it is whole). Each weapon is one construction on its three badges.
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const B = require('../parts/symbol_shaded_badges');
const W = require('../parts/symbol_shaded_badges_w');

// the three kinds of weapon badge: its drawing, its paint, and the face an object may lie on
const KIND = {
  foc: { badge: B.focusBadge, paint: B.PAINT.focus, face: S.circle(B.X, B.Y, B.R_DISC - B.W_EDGE) },
  prof: { badge: B.profBadge, paint: B.PAINT.prof, face: S.circle(B.X, B.Y, B.R_RIM0) },
  spec: { badge: B.specBadge, paint: B.PAINT.spec, face: S.circle(B.X, B.Y, B.R_DISC - B.W_EDGE) },
};
// one weapon on its three badges: where[kind] says where it lies there
const onBadges = (number, draw, where) => {
  const out = {};
  for (const kind of Object.keys(KIND)) out['i_weap' + kind + number] = (c) => { KIND[kind].badge(c); draw(c, where[kind], KIND[kind].paint, KIND[kind]); };
  return out;
};
const shifted = (p, dx, dy) => [p[0] + dx, p[1] + dy];

// ---- 01 the blaster pistol ---------------------------------------------------------------------------------------------
// Where one outline covers the game's two drawings best (tools/badges_pistolfit.py): on the focus badge level, its
// muzzle at (4.03, 13.48), 1.134 times the size; on the proficiency badge turned 22.5 degrees, muzzle at
// (6.70, 10.58). The specialisation badge's is the proficiency badge's moved 2 left and 1 down, as in the game.
// Changed from the game on the focus badge: at 1.134 the grip's heel runs into the badge's border (in the game it
// touches it); it is drawn at 1.09, and 0.15 higher, so that pistol and outline lie whole on the face.
const PISTOL = { foc: [[4.03, 13.33], 0, 1.09], prof: [[6.7, 10.58], 22.5, 1], spec: [[4.7, 11.58], 22.5, 1] };

// ---- 02 the blaster rifle ----------------------------------------------------------------------------------------------
// The game draws it at the same place on all three badges. Fitted: muzzle at (5.85, 8.31), 31.5 degrees, full size.
// Changed from the game: there its muzzle and its rear end touch the disc's edge; it is drawn at 0.96, about its
// middle, so that it lies whole on the face.
const RIFLE = [[6.3, 8.6], 31.5, 0.96];

// ---- 04 the heavy weapon -----------------------------------------------------------------------------------------------
// Fitted: on the focus badge muzzle at (5.15, 9.52), 0.94 the size; on proficiency (6.36, 10.02), 0.86; at 27
// degrees. The specialisation badge's is the proficiency badge's moved 2 left and 1 down (as the pistol's).
// Changed from the game on the focus badge: drawn at 0.91 so that muzzle and rear end keep clear of the edge.
const HEAVY = { foc: [[5.5, 9.65], 27, 0.91], prof: [[6.36, 10.02], 27, 0.862], spec: [[4.36, 11.02], 27, 0.862] };

// ---- 05 the lightsaber's hilt ------------------------------------------------------------------------------------------
// Fitted: the middle of its upper round end at (9.40, 9.36) on the focus badge; (10.09, 10.35) and 0.85 the size on
// the other two (the game draws it slimmer there, and at the same place on both).
const HILT = { foc: [[9.4, 9.36], 45, 1], prof: [[10.09, 10.35], 45, 0.85], spec: [[10.09, 10.35], 45, 0.85] };

// ---- 07 the sword ------------------------------------------------------------------------------------------------------
// The grip's end and the point on the focus badge; the proficiency badge's lies one pixel further left, the
// specialisation badge's where the focus badge's does (the game).
const SWORD = [[24.18, 25.44], [7.45, 6.9]];

module.exports = {
  ...onBadges('01', (c, at, paint) => B.pistol(c, B.placeGame(...at), paint), PISTOL),
  ...onBadges('02', (c, at, paint) => W.rifle(c, B.placeGame(...at), paint), { foc: RIFLE, prof: RIFLE, spec: RIFLE }),
  // 03 the grenade: a ball on the badge's centre (in the game its middle lies within half a pixel of the ring's),
  // 7.6 in radius on the focus badge, 7.1 on proficiency, 5.3 inside the specialisation badge's ring
  ...onBadges('03', (c, r, paint) => W.grenade(c, [B.X, B.Y], r, paint), { foc: 7.58, prof: 7.13, spec: 5.28 }),
  ...onBadges('04', (c, at, paint) => W.heavy(c, B.placeGame(...at), paint), HEAVY),
  ...onBadges('05', (c, at, paint) => W.hilt(c, B.placeGame(...at), paint), HILT),
  // 06 the three blades and their reflection
  ...onBadges('06', (c, at, paint, kind) => W.blades(c, paint, kind.face), { foc: 0, prof: 0, spec: 0 }),
  ...onBadges('07', (c, dx, paint) => W.sword(c, shifted(SWORD[0], dx, 0), shifted(SWORD[1], dx, 0), paint), { foc: 0, prof: -1, spec: 0 }),

  // the gear: the game's, at the game's size (it is whole there). gearhead01 is the same drawing in the game.
  i_gearhead(c) { B.gear(c); },
  i_gearhead01(c) { B.gear(c); },
  i_gearhead02(c) { B.gear(c); W.gearLights(c, { middle: 'white' }); },
  i_gearhead03(c) { B.gear(c); W.gearLights(c, { middle: 'lip', cross: true }); },

  // toughness: the flexed arm. toughn02 is toughn's drawing in the game (only the border's soft outer pixels differ).
  i_toughn(c) { B.focusBadge(c, { flat: true }); B.arm(c); },
  i_toughn02(c) { B.focusBadge(c, { flat: true }); B.arm(c); },
  i_toughn01(c) { W.whiteBadge(c, '#001b80'); B.arm(c); },
  i_toughn03(c) { W.whiteBadge(c); B.arm(c); },
};
