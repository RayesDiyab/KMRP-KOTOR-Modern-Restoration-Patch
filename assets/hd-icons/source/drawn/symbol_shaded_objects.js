'use strict';
// Constructed drawings of the shaded objects. Nothing here is traced: each object is built in
// parts/symbol_shaded_objects.js from dimensions read off the game's icon (stated there), and an object that appears
// in several icons is the same construction in each. Where things stand beside or over one another, all their black
// is laid first and then the bodies in order. Only what the game's icon shows is drawn.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const O = require('../parts/symbol_shaded_objects');

// the three upgrade icons: the large turret over the crate, with bottles in the crate's compartments
const upgrade = (c, bottles) => {
  O.turretBlack(c, O.TURRET_UP); O.crateBlack(c);
  O.crateBody(c, bottles); O.turretBody(c, O.TURRET_UP);
};

module.exports = {
  // the chip alone
  i_implant01(c) { O.chip(c); },
  // the chip with a white line round it, one unit from its black and one unit wide
  i_implant02(c) { O.chipLine(c); O.chip(c); },
  // the same with a white square in each corner
  i_implant03(c) { O.chipLine(c, 'border'); O.chipCorners(c, 'border'); O.chipLine(c, 'body'); O.chipCorners(c, 'body'); O.chip(c); },

  // the padlock in its square
  isk_security(c) { O.padlock(c); },

  // the turret on its shield: white without a border, white, red and yellow with one (the game's flat colours)
  i_droidac(c) { O.shield(c, '#fefeff', false); O.turret(c); },
  i_droidac01(c) { O.shield(c, '#fefeff'); O.turret(c); },
  i_droidac02(c) { O.shield(c, '#fc0c0c', true, '#c40a08'); O.turret(c); },
  i_droidac03(c) { O.shield(c, '#fcfc0c', true, '#dccf00'); O.turret(c); },

  // the large turret over the crate: one white bottle in the middle, two red ones, three yellow ones
  i_droidup01(c) { upgrade(c, [[1, 'white']]); },
  i_droidup02(c) { upgrade(c, [[0, 'red'], [1, 'red']]); },
  i_droidup03(c) { upgrade(c, [[0, 'yellow'], [1, 'yellow'], [2, 'yellow']]); },

  // the breastplate; the same with shoulder plates
  i_armprof01(c) { O.armour(c); },
  i_armprof02(c) { O.armour(c, { pads: true }); },
  // the whole suit
  i_armprof03(c) { O.suit(c); },

  // the pointing hand; the same without its black border (as in the game)
  i_useitem(c) { O.hand(c); },
  i_useitem01(c) { O.hand(c, { border: false }); },

  // the open hands with their arrows: into the hand, out of the hand
  i_equip(c) { O.openHand(c, O.EQUIP, O.ARROW_IN); },
  i_unequip(c) { O.openHand(c, O.UNEQUIP, O.ARROW_OUT); },
  // the forearm with the cross, and the arrow pointing at it
  i_useforearm(c) { O.forearm(c); },

  // the red droid: with its head in a clamp; with its head struck off by a hammer
  ip_droiddisable(c) { O.droidHead(c, 'border'); O.droidBody(c, 'border'); O.droidBody(c, 'body'); O.droidHead(c, 'body'); },
  ip_droiddestroy(c) { O.droidHammer(c, 'border'); O.droidBody(c, 'border'); O.droidBody(c, 'body'); O.droidHammer(c, 'body'); },
};
