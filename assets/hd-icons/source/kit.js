'use strict';
// The house style: one palette, one set of line weights, and the building blocks every icon is made of.
// All measures are in units of the vanilla icon's pixels (the drawing space is 32 x 32, centre 16, 16).
const S = require('./lib/sdf');
const P = require('./lib/paint');

// Colours read off the vanilla icons (their commonest solid colours).
const C = {
  black: '#0a0a0c', white: '#ffffff',
  navy: '#0a0e3c', blueDeep: '#0a1680', blue: '#1432d8', blueMid: '#3a5cf4', blueSoft: '#7c98fc', blueLight: '#a4b8fc', bluePale: '#dfe5ff',
  redDark: '#3c0602', redDeep: '#8a1608', red: '#c42c16', redMid: '#e8543a', redSoft: '#fc8c74', redLight: '#fcb4a4', redPale: '#ffe6e0',
  yellow: '#fcf00c', yellowDeep: '#b8a800', grey: '#b4b4b8', greyDark: '#58585e', greyLight: '#dcdce0',
  teal: '#0c3c54', tealDark: '#06202e', cyan: '#28e4fc',
};

// Line weights: the same everywhere.
const W = {
  border: 1.25,       // the black line round every body
  line: 0.9,          // a drawn line (crosshair, panel line)
  rim: 1.2,           // how far the light inside an edge dies away, beyond its crisp line
  rimCore: 0.38,      // the crisp white line just inside the black border
  edge: 15.9,         // the radius of a disc that fills the icon (a hair inside the frame, so its edge is whole)
};

// A heater shield: flat sides down to `waist`, then drawn in to a point at `bottom`. top: the y of its upper corners;
// peak > 0 raises a point in the middle of the upper edge (with a dip either side of it), 0 leaves the edge straight.
const shieldShape = (cx, top, half, waist, bottom, peak = 0, r = 0.3) => {
  const right = [[cx, top + (peak ? 0.55 - peak : 0)]];
  if (peak) right.push([cx + half * 0.42, top + 0.75, 0.5]);
  right.push([cx + half, top, r], [cx + half, waist, 0.2]);
  for (let i = 1; i < 12; i++) {                                 // the lower edge: a quarter of a pointed oval
    const a = (Math.PI / 2) * (i / 12);
    right.push([cx + half * Math.pow(Math.cos(a), 0.82), waist + (bottom - waist) * Math.pow(Math.sin(a), 1.15)]);
  }
  right.push([cx, bottom, 0.35]);
  return S.mirrored(cx, right, { r: 0 });
};

// Lit surfaces: colour by how much light a place gets (0 dark .. 1 facing the light).
const RAMP = {
  blue: [[0, '#030a50'], [0.4, '#0f2cc8'], [0.68, '#2c50ee'], [0.86, '#5878f8'], [1, '#8aa2fc']],
  red: [[0, '#460602'], [0.4, '#aa200c'], [0.68, '#e2452a'], [0.86, '#f8755c'], [1, '#fc9e8a']],
  grey: [[0, '#26262c'], [0.4, '#6c6c76'], [0.72, '#b0b0ba'], [0.9, '#d8d8e0'], [1, '#ececf2']],
};
const DEEP = { blue: C.blueDeep, red: C.redDeep, grey: '#34343c' };
const PALE = { blue: C.bluePale, red: C.redPale, grey: '#f4f4f8' };
const FRONT = [-0.1, -0.32, 0.94];          // where the light stands: in front, a little above and to the left
const GLINT = [-0.5, -0.62, 0.6];           // where highlights come from

const SH = {
  black: P.flat(C.black),
  // a white body with a thin blue line just inside its edge (the flat symbols)
  whiteBlue: P.byDepth(0.9, [[0, C.blue], [0.3, C.blueMid], [0.65, C.bluePale], [1, C.white]]),
  whiteGrey: P.byDepth(0.8, [[0, '#7c7c88'], [0.5, '#d4d4dc'], [1, C.white]]),
};

// a flat body with the black border round it (round every edge of it, cut-outs included)
const body = (c, shape, shader, border = W.border) => {
  if (border > 0) c.fill(S.grow(shape, border), SH.black);
  c.fill(shape, shader);
  return shape;
};

// A lit body: black border, a surface that rises from its edge, a light line inside the edge.
//   hue      'blue' | 'red' | 'grey'       height  the surface (default: a cushion)
//   rim      false, or { width, strength, colour }           border  0 for none
const solid = (c, shape, o = {}) => {
  const { hue = 'blue', border = W.border, depth = 2.4, rise = 0.9, height = null, rim = {}, gloss = 0.35, shine = 26, ambient = 0.2, borderColour = C.black } = o;
  if (border > 0) c.fill(S.grow(shape, border), P.flat(borderColour));
  c.relief(shape, {
    height: height || P.cushion(depth, rise), stops: RAMP[hue], light: FRONT, glossLight: GLINT, ambient, gloss, shine,
    rim: rim === false ? null : { colour: C.white, width: W.rim, core: W.rimCore, strength: 0.97, ...rim },
  });
  return shape;
};

module.exports = { S, P, C, W, SH, RAMP, DEEP, PALE, FRONT, GLINT, body, solid, shieldShape };
