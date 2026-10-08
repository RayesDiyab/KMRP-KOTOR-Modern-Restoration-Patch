'use strict';
// Constructed drawings of the shaded objects, second part: the three red Force icons with the cube, the two skill
// icons, the two mine icons, the blaster and the two eyes. Nothing here is traced: each object is built in
// parts/symbol_shaded_objects_b.js from dimensions read off the game's icon (stated there). Where things stand beside
// or over one another, all their black is laid first and then the bodies in order.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const B = require('../parts/symbol_shaded_objects_b');

module.exports = {
  // Force hold: the cube over an open hand. The cube as in the game: 17 wide (x 7..24), its upper corner at y 1.9,
  // the upright edges 8.7 long. Its lowest corner (16.05, 21.14) lies behind the thumb, as in the game, where the
  // thumb's upper edge (y 20) follows straight on the cube.
  ip_hold(c) {
    const cube = { cx: 15.5, top: 1.9, a: 8.5, h: 8.7 };
    B.cube(c, cube, { part: 'border' }); B.holdHand(c, 'border');
    B.cube(c, cube, { part: 'body' }); B.holdHand(c, 'body');
  },

  // Force push: the arrow in front of the cube's left side. The cube as in the game: 19 wide, its upper corner at
  // y 3.5, the upright edges 10.5 long. Changed from the game: there the cube's black stands on the frame's right
  // edge (the cube x 12..31 and the black to 32); here the cube is 18.9 wide (to 30.9), so that the black round it is
  // whole.
  ip_push(c) {
    const cube = { cx: 21.45, top: 3.5, a: 9.45, h: 10.5 };
    B.cube(c, cube, { part: 'border' }); B.pushArrow(c, 'border');
    B.cube(c, cube, { part: 'body' }); B.pushArrow(c, 'body');
  },

  // Force breach: the cube split open by a bolt, bits flying off
  ip_breach(c) {
    const q = B.BREACH, bits = q.bits.map(B.square);
    B.cube(c, q.cube, { part: 'border' });
    F.borders(c, [q.bolt, ...bits], B.BORDER);
    B.cube(c, q.cube, { part: 'body', cut: S.polygon(q.split) });
    F.solid(c, q.bolt, { palette: B.WHITE_HOT, border: 0, depth: 0.7 });
    for (const pts of bits) F.solid(c, pts, { palette: B.BIT, border: 0, depth: 0.75 });
  },
};
