'use strict';
// Constructed drawings of the shaded badges, second part: the skill badges, the two force signs and their focus
// badges, battle meditation, the dark side's sign, the plus button and combat regeneration. The badges, objects and
// signs are built in parts/symbol_shaded_badges_b.js and parts/symbol_shaded_badges_b_obj.js (measurements are
// stated there); the sheet's own badge comes from parts/symbol_shaded_badges.js. Every object lies where the game's
// icon has it.
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const B = require('../parts/symbol_shaded_badges');
const Q = require('../parts/symbol_shaded_badges_b');
const O = require('../parts/symbol_shaded_badges_b_obj');

module.exports = {
  // ---- the five skill badges: one badge, the object on it where the game has it -------------------------------------
  // security: the padlock
  i_focsecur(c) { Q.skillBadge(c); Q.padlock(c); },
  // boost: a white arrow, and the same arrow in blue behind it
  i_focboost(c) { Q.skillBadge(c); O.boostArrows(c); },
  // repair: the wrench
  i_focrepair(c) { Q.skillBadge(c); O.wrench(c); },
};
