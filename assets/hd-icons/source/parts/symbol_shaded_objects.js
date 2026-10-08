'use strict';
// The objects of the sheet symbol_shaded_objects, constructed once each: the chip of the implant icons, the padlock,
// the turret of the droid icons and its shield, the breastplate, the pointing hand.
//
// The GAME's icon gives each design: outline, proportions, what lies in front of what, where each colour is (read off
// its pixels with tools/vmap.py and as hex colours). ChatGPT's redraw only shows what a thing is and how its light
// might be modelled. Every outline is made of straight lines and circular arcs with stated dimensions; black borders
// are laid first, each the outline moved out by one width; shading is formulas and stays soft and structural: a
// colour that falls from a lit side to a shaded side, deepens to the edge of its shape, and a thin dark line on the
// edge.
// Units: the vanilla icon's pixels (frame 32 x 32, y down). The light stands above and to the left, as in the game.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const G = require('../lib/geom');

const INK = '#0a0a0c';
// The black line round a body: one unit everywhere on this sheet, the one pixel of the game's icons (the chip, the
// padlock and the turret are drawn on the pixel grid there, and the redraws of those keep it: 1.0). The shield of
// the droid icons carries its own, two wide in the game.
const BORDER = 1.0;
// the thin dark line along the very edge of a body, as on the other sheets
const RIM = 0.13;

const { clamp } = S;
const lin = (c) => (typeof c === 'string' ? P.hex(c) : c).map(P.toLinear);
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const put = (px, c, a = 1) => { px.r = P.toSRGB(c[0]); px.g = P.toSRGB(c[1]); px.b = P.toSRGB(c[2]); px.a = a; };
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bell = (d, w) => Math.exp(-(d * d) / (w * w));
// a colour ramp that returns the colour (linear light): stops = [[t, '#rrggbb'], ...] with t rising
const ramp = (stops) => {
  const ts = stops.map((s) => s[0]), cs = stops.map((s) => lin(s[1]));
  return (t) => {
    let i = 0;
    while (i < ts.length - 2 && t > ts[i + 1]) i++;
    return mix3(cs[i], cs[i + 1], clamp((t - ts[i]) / (ts[i + 1] - ts[i] || 1e-9), 0, 1));
  };
};
// a curve through measured values: stops = [[t, value], ...] with t rising, straight between them
const curve = (stops) => (t) => {
  let i = 0;
  while (i < stops.length - 2 && t > stops[i + 1][0]) i++;
  const a = stops[i], b = stops[i + 1];
  return a[1] + (b[1] - a[1]) * clamp((t - a[0]) / (b[0] - a[0] || 1e-9), 0, 1);
};
// a rectangle by its corners
const rect = (x0, y0, x1, y1) => S.box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2);
// one pixel of soft edge where a formula changes colour across the line v = 0 (v in units, k pixels per unit)
const step = (v, k) => clamp(v * k + 0.5, 0, 1);

// ---- the game's blues ------------------------------------------------------------------------------------------------
// Every blue of these icons lies on one ramp, from white through 0x9fb3ff and 0x3c64ff down to navy, and its green
// channel falls evenly along it. So a shade is given here by its green level (0 to 255, as read off a pixel of the
// game: 0x8ea5ff is level 0xa5) and every colour comes off this one ramp.
const TONE = ramp([[0x00, '#00020a'], [0x0b, '#000b33'], [0x11, '#001151'], [0x1a, '#001a7c'], [0x26, '#0026b8'], [0x2e, '#022ed9'], [0x39, '#0d39e4'],
  [0x48, '#1c48f3'], [0x57, '#2b57ff'], [0x64, '#3c64ff'], [0x7b, '#597bff'], [0x8b, '#6e8bff'], [0x9f, '#869fff'], [0xb3, '#9fb3ff'], [0xc4, '#b5c4ff'],
  [0xd7, '#cdd7ff'], [0xec, '#e7ecff'], [0xff, '#ffffff']]);
// The thin dark line on a body's edge is the body's own colour 95 levels deeper (white gets 0xa0, the 0x8ea4ee of
// the other sheets' white bodies; a blue of level 0x7b gets their navy 0x1c).
const rimLevel = (g) => Math.max(g - 95, 0x12);
// a level laid on a pixel, with the thin dark line where the pixel lies within RIM of its shape's edge
// (tone: another ramp than the blue one; alpha: for a form that fades out)
const shade = (px, g, k, rim = RIM, tone = TONE, alpha = 1) => put(px, mix3(tone(clamp(g, 0, 255)), tone(rimLevel(g)), rim > 0 ? step(rim + px.d, k) : 0), alpha);
// Inside a rectangle: how deep a point lies (distance to the nearest side) and how far it belongs to the two sides
// that face the light (top and left: lit = 1) or the two turned away (right and bottom: 0). The change runs along
// the diagonals of the corners and is spread over `soft` units, so that it is a gradient and no facet.
const sides = (x0, y0, x1, y1, soft) => (x, y) => {
  const l = x - x0, t = y - y0, r = x1 - x, b = y1 - y, a = Math.min(l, t), d = Math.min(r, b);
  return { depth: Math.min(a, d), lit: smooth(-soft, soft, d - a), l, t, r, b };
};

// ---- the chip (implants I, II, III) ---------------------------------------------------------------------------------
// The game draws it on the pixel grid:
//   top face of the body  x 10..22, y 10..23 (12 x 13); under it a lower face one unit tall (y 23..24), navy
//   sixteen pins, each 1 wide, four to a side, 3 apart: the upper and lower ones centred on x = 16, those at the
//   sides centred on y = 17, the middle of the body with its lower face (y 10..24)
//   inside the top face: a white frame 1 wide, a light band and a blue ring (each 1 wide), a raised square
//   x 13..19, y 13..20 with its upper and left edge white
//   the black behind it reaches one unit beyond the pins and the body: a cross of three rectangles
// Changed from the game: there the lower pins show three pixels (y 24..27) and the others four. Here every pin is 4
// long, the lower ones from under the lower face (y 24) to 28, so that the sixteen are equal and the whole chip is
// the same above and below y = 17 (and with it the line and the corner squares of implants II and III).
// The game's lighting: the pins above and to the left are pale to their roots, those below and to the right stand in
// the body's shadow (navy at the root); the ring is a little lighter at the left (0x78) than elsewhere (0x64).
const CHIP = {
  face: [10, 10, 22, 23], under: 1, square: [13, 13, 19, 20],
  pinW: 1, pinL: 4, pitch: 3, cx: 16, cy: 17,
  // the cross of black behind it, clockwise from its upper left corner
  cross: [[10, 5], [22, 5], [22, 9], [23, 9], [23, 11], [27, 11], [27, 23], [23, 23], [23, 25], [22, 25], [22, 29], [10, 29], [10, 25], [9, 25], [9, 23], [5, 23], [5, 11], [9, 11], [9, 9], [10, 9]],
};
// Levels along a pin from its tip (0) to its root (1). The game's four pixels: above c4 9f 87 48, left ca 9e 88 65;
// right b8 92 5c 1e, below d2 a9 57 and the navy of the lower face. (Set 0x1c higher here: the thin dark lines along
// a pin's two edges take a quarter of its width, and the pin as a whole should come out at the game's level.)
const PIN_LIT = curve([[0, 0xf2], [0.125, 0xe6], [0.375, 0xba], [0.625, 0xa2], [0.875, 0x72], [1, 0x60]]);
const PIN_SHADE = curve([[0, 0xf0], [0.125, 0xe2], [0.375, 0xb8], [0.625, 0x76], [0.875, 0x32], [1, 0x22]]);
// Levels of the top face by depth from its edge. The game's three rings: white f5, band a8 (ad at the left), ring 64
// (78 at the left). Three flat rings as in the game (a gradient across them would crease along the corners'
// diagonals); the ring is 0x76 on the sides towards the light and 0x56 on those away from it.
const FACE_LIT = curve([[0, 0xff], [0.85, 0xff], [1.15, 0xae], [1.85, 0xae], [2.15, 0x76], [3, 0x74]]);
const FACE_SHADE = curve([[0, 0xfd], [0.85, 0xfd], [1.15, 0xa6], [1.85, 0xa6], [2.15, 0x56], [3, 0x52]]);

const chipPins = () => {
  const q = CHIP, [x0, y0, x1, y1] = q.face, out = [];
  for (let i = 0; i < 4; i++) {
    const o = (i - 1.5) * q.pitch, h = q.pinW / 2;
    out.push({ box: [q.cx + o - h, y0 - q.pinL, q.cx + o + h, y0 + 0.5], lit: true, axis: 'y', tip: y0 - q.pinL, root: y0 });           // above
    out.push({ box: [q.cx + o - h, y1, q.cx + o + h, y1 + q.under + q.pinL], lit: false, axis: 'y', tip: y1 + q.under + q.pinL, root: y1 + q.under });   // below
    out.push({ box: [x0 - q.pinL, q.cy + o - h, x0 + 0.5, q.cy + o + h], lit: true, axis: 'x', tip: x0 - q.pinL, root: x0 });           // left
    out.push({ box: [x1 - 0.5, q.cy + o - h, x1 + q.pinL, q.cy + o + h], lit: false, axis: 'x', tip: x1 + q.pinL, root: x1 });          // right
  }
  return out;
};

// The chip, drawn where the game has it.
const chip = (c) => {
  const q = CHIP, k = c.k, [x0, y0, x1, y1] = q.face, [sx0, sy0, sx1, sy1] = q.square;
  c.fill(S.polygon(q.cross), P.flat(INK));
  for (const p of chipPins()) {
    const along = p.lit ? PIN_LIT : PIN_SHADE, len = Math.abs(p.root - p.tip);
    c.fill(rect(...p.box), (px) => shade(px, along(Math.abs((p.axis === 'y' ? px.y : px.x) - p.tip) / len), k));
  }
  // the lower face: the game's row of navy (0x001a7c), over the roots of the lower pins
  c.fill(rect(x0, y1 - 0.5, x1, y1 + q.under), (px) => shade(px, 0x22 - 0x0c * (px.y - y1) / q.under, k, 0));
  // the top face: white frame, band and ring, deeper on the two sides turned from the light
  const side = sides(x0, y0, x1, y1, 1.2);
  c.fill(rect(x0, y0, x1, y1), (px) => {
    const s = side(px.x, px.y);
    shade(px, FACE_SHADE(s.depth) + (FACE_LIT(s.depth) - FACE_SHADE(s.depth)) * s.lit, k);
  });
  // The raised square. In the game its fill falls from 0xbb at the upper left to 0xa1 at the lower right, mostly
  // from left to right; here a little more (0xc6 to 0x90) so that it reads as a lit face. A white line runs along
  // its upper and left edge (the game's row and column of 0xe9..0xf1).
  c.fill(rect(sx0, sy0, sx1, sy1), (px) => {
    const e = Math.min(px.x - sx0, px.y - sy0), g = 0xc6 - 6 * (px.x - sx0 - 0.5) - 3 * (px.y - sy0 - 0.5);
    shade(px, g + (0xf6 - g) * (e < 0.45 ? 1 : bell(e - 0.45, 0.35)), k, 0);
  });
};

// The line round the chip of implants II and III: the cross's outline moved out by one unit (white) and by two
// (black), corners square, as in the game. part: 'border' the black only, 'body' the white only.
const chipLine = (c, part) => {
  if (part !== 'body') c.fill(S.polygon(G.offsetPts(CHIP.cross, 2 * BORDER)), P.flat(INK));
  if (part !== 'border') c.fill(S.polygon(G.offsetPts(CHIP.cross, BORDER)), P.flat('#ffffff'));
};
// The four white squares in the corners of implant III: each 2 wide and 4 high with one unit of black round it,
// standing in the corners the line leaves (x 4..6 and 26..28; y 4..8 and 26..30). In the game the lower two are
// 3 high (see the chip's own note): here all four are equal.
const CHIP_CORNERS = { at: [[4, 4], [26, 4], [4, 26], [26, 26]], w: 2, h: 4 };
const chipCorners = (c, part) => {
  const q = CHIP_CORNERS;
  for (const [x, y] of q.at) {
    if (part !== 'body') c.fill(rect(x - BORDER, y - BORDER, x + q.w + BORDER, y + q.h + BORDER), P.flat(INK));
    if (part !== 'border') c.fill(rect(x, y, x + q.w, y + q.h), P.flat('#ffffff'));
  }
};

// ---- the padlock in its square -------------------------------------------------------------------------------------
// All on the pixel grid in the game:
//   the square: black 2..30, a pale band 3..29 that is 2 wide (flat 0xdfe6ff), a black line 1 wide inside it; clear
//   within (6..26)
//   the shackle: x 10..22, from y 7 down into the body, its bar 2 wide: the outer half 0xc8, the inner half 0xe2,
//   both deepening down the legs (0xa5 and 0xb5 where they meet the body); the opening x 13..19, y 10..13 is clear
//   the body: x 8..24, y 14..24 with a lower face y 24..25 (0x85); on it a light rim 1 wide (f0 above, e8 below, d5 at
//   the sides), a panel x 11..21, y 16..22 (0xd3), and between them a face that falls from 0xbc at the upper left
//   to 0x9c at the lower right
// The shackle's legs run into the body without a black line between them (as in the game).
const LOCK = { frame: [3, 3, 29, 29], band: 2, shackle: [10, 7, 22, 14], bar: 2, body: [8, 14, 24, 24], under: 1, rim: 1, panel: [11, 16, 21, 22] };

const padlock = (c) => {
  const q = LOCK, k = c.k, [fx0, fy0, fx1, fy1] = q.frame, [hx0, hy0, hx1, hy1] = q.shackle, [bx0, by0, bx1, by1] = q.body, [px0, py0, px1, py1] = q.panel;
  // all the black first: the square's two lines, the shackle's outside and inside, the body's
  c.fill(S.subtract(rect(fx0 - BORDER, fy0 - BORDER, fx1 + BORDER, fy1 + BORDER), rect(fx0 + q.band + BORDER, fy0 + q.band + BORDER, fx1 - q.band - BORDER, fy1 - q.band - BORDER)), P.flat(INK));
  c.fill(S.subtract(rect(hx0 - BORDER, hy0 - BORDER, hx1 + BORDER, hy1), rect(hx0 + q.bar + BORDER, hy0 + q.bar + BORDER, hx1 - q.bar - BORDER, hy1 - BORDER)), P.flat(INK));
  c.fill(rect(bx0 - BORDER, by0 - BORDER, bx1 + BORDER, by1 + q.under + BORDER), P.flat(INK));
  // the band of the square: one flat pale colour, a touch deeper along its two edges
  const band = S.subtract(rect(fx0, fy0, fx1, fy1), rect(fx0 + q.band, fy0 + q.band, fx1 - q.band, fy1 - q.band));
  c.fill(band, (px) => shade(px, 0xee - 0x08 * (1 - smooth(0, 0.6, -px.d)), k));
  // the shackle: one bar of one width, lighter along its inner half, deepening down its legs
  const bow = S.subtract(rect(hx0, hy0, hx1, hy1 + 1), rect(hx0 + q.bar, hy0 + q.bar, hx1 - q.bar, hy1 + 2));
  const outer = rect(hx0, hy0, hx1, hy1 + 9), of = c.field(outer);
  c.fill(bow, (px) => {
    const t = clamp(-of[px.i] / q.bar, 0, 1);                        // 0 at the bar's outer edge, 1 at its inner
    shade(px, 0xc8 + (0xe4 - 0xc8) * smooth(0.25, 0.75, t) - 11 * Math.max(px.y - 10.5, 0), k);
  });
  // the body: its lower face, then the top face with rim and panel
  c.fill(rect(bx0, by1 - 0.5, bx1, by1 + q.under), (px) => shade(px, 0x8c - 0x10 * (px.y - by1) / q.under, k));
  const face = sides(bx0, by0, bx1, by1, 0.5);
  c.fill(rect(bx0, by0, bx1, by1), (px) => {
    const x = px.x, y = px.y, s = face(x, y);
    // the face between rim and panel falls along the diagonal away from the light
    const field = 0xbc - 1.6 * ((x - bx0 - q.rim) + (y - by0 - q.rim));
    // the rim: white above and below, a little less at the two sides
    const upDown = smooth(-0.5, 0.5, Math.min(s.l, s.r) - Math.min(s.t, s.b));
    const rim = (0xd6 + (s.t < s.b ? 0xf2 - 0xd6 : 0xea - 0xd6) * upDown);
    const g = field + (rim - field) * (1 - smooth(q.rim - 0.3, q.rim + 0.3, s.depth));
    shade(px, g, k, by1 - y < RIM * 2 ? 0 : RIM);                    // (no dark line where the top face meets the lower one)
  });
  c.fill(rect(px0, py0, px1, py1), (px) => shade(px, 0xd9 - 0.6 * ((px.x - px0) + (px.y - py0)), k, 0));
};

// ---- the turret of the droid icons ------------------------------------------------------------------------------------
// The game has it in two sizes. The small one stands on a base on the shields (i_droidac, 01, 02, 03: the same pixels
// in all four), the large one stands over the crate of the upgrade icons (i_droidup01, 02, 03). Both are the same
// machine, part for part; the large one shows a little more (three slots instead of two bars, a light line inside
// its left end too, a navy line under its middle), as the game's own two drawings do.
//   handle   a bar with pointed ends, the black round it cut at its corners; a neck down to the head
//   head     a long box, its left corners cut by 2, its right ones by 1
//   eye      at the head's right end, an octagon (corners cut by 1); between head and eye a black slit
//   in the head: a light row inside its upper and its lower edge (the lower one lighter to the right), a navy
//            window with a dash above it, light bars, a round light, a light column inside its right end
//   in the eye: a white middle on blue
// Small (read off i_droidac): handle x 11..17, y 6..7; a black neck x 13..15; head x 6..22, y 10..17; eye x 22..26,
//   y 11..16; slit x 21..22, y 12..15; window x 8..12.8, y 12..15, dash x 9..11.2, y 11..12; bars x 13..14 and
//   15..16, y 12..14; light at 19.5, 13.3; stem (black) x 10..19; base x 7..25, y 20..23, upper corners cut by 1, a
//   light upper row, a deep middle row with a white reflection at x 14..17, a lighter lower row.
// Large (read off i_droidup01): handle x 10..17, y 2..3; neck x 13..14 (blue), y 4..5; head x 4..24, y 6..15;
//   eye x 24..29, y 7..14; slit x 23..24, y 8..13; window x 6..12, y 9..11 in a deeper surround x 5..12, y 8..12,
//   dash x 7..10, y 7..8; light bars x 12..14, 15..16, 17..18 with black slots x 14..15, 16..17, 18..19, y 9..11;
//   light x 19..22, y 9..12, a light pixel above and below each slot; a navy line y 12..13 from x 5 to 20; the
//   lower light band two rows deep.
// Black is each part's outline moved out by one unit; all black is laid first.
const TURRET = {
  handle: [[11.5, 6], [16.5, 6], [17, 6.5], [16.5, 7], [11.5, 7], [11, 6.5]], handleLevel: 0x8c, handleEnd: 0x20, neck: [13, 7, 15, 9.5], neckBlue: null,
  head: [[8, 10], [21, 10], [22, 11], [22, 16], [21, 17], [8, 17], [6, 15], [6, 12]], box: [6, 10, 22, 17], cut: [2, 1],
  // levels: the head's plain blue, the light inside its upper edge, inside its lower edge (left, right, from x to x),
  // inside its left end (null: none), how deep the lower light band is
  base0: 0x56, top: 0x9c, bottom: [0x9c, 0xca, 12, 20], left: null, bottomDeep: 1, line: null,
  eye: [[23, 11], [25, 11], [26, 12], [26, 15], [25, 16], [23, 16], [22, 15], [22, 12]], eyeLight: [24.6, 13.5, 2.1, 2.2], eyeRing: 0x5c,
  slit: [21, 12, 22.2, 15],
  window: [8, 12, 12.8, 15], windowRows: [[12, 0x1e], [12.5, 0x18], [13.5, 0x0e], [14.5, 0x26], [15, 0x2c]], surround: null, dash: [9, 11, 11.2, 12.2, 0x24],
  bars: [[13, 14, 0xa4, 0xc8], [15, 16, 0x94, 0xa0]], slots: [[14, 15, 0x4c, 0x30]], ticks: null, barsY: [12, 14], light: [19.5, 13.3, 1.5], endLine: [20.5, 11.2, 16.2, 0.5, 0xb6],
  stem: [10, 17.5, 19, 19.5],
  base: [[8, 20], [24, 20], [25, 21], [25, 23], [7, 23], [7, 21]], baseRows: [[20, 0x92], [20.8, 0x84], [21.3, 0x54], [21.8, 0x5c], [22.5, 0x8a], [23, 0x90]], shine: [15.8, 21.85, 2.3, 1.2],
};
const TURRET_UP = {
  handle: [[10.5, 2], [16.5, 2], [17, 2.5], [16.5, 3], [10.5, 3], [10, 2.5]], handleLevel: 0xae, handleEnd: 0, neck: [12, 3, 15, 5.5], neckBlue: [13, 4, 14, 5, 0xb0],
  head: [[6, 6], [23, 6], [24, 7], [24, 14], [23, 15], [6, 15], [4, 13], [4, 8]], box: [4, 6, 24, 15], cut: [2, 1],
  base0: 0x48, top: 0xc0, bottom: [0x92, 0xbc, 15, 20], left: 0x94, bottomDeep: 2, line: [5, 12, 20, 13, 0x1d],
  eye: [[25, 7], [28, 7], [29, 8], [29, 13], [28, 14], [25, 14], [24, 13], [24, 8]], eyeLight: [27, 10.5, 2.6, 3.2], eyeRing: 0x3c,
  slit: [23, 8, 24.2, 13],
  window: [6, 9, 12, 11], windowRows: [[9, 0x14], [10, 0x0f], [11, 0x14]], surround: [5, 8, 12, 12, 0x36], dash: [7, 7, 10, 8, 0x1d],
  bars: [[12, 14, 0x96, 0xa2], [15, 16, 0xc2, 0xd4], [17, 18, 0xcc, 0xec]], slots: [[14, 15, 0x06, 0x06], [16, 17, 0x06, 0x06], [18, 19, 0x06, 0x06]], ticks: 0xaa, barsY: [9, 11],
  light: [20.3, 10.1, 1.6], endLine: [21.5, 7.8, 13.2, 0.45, 0xf6],
  stem: [9, 15.5, 21, 17.5], base: null,
};

// the black of a turret (drawn first, with the black of whatever stands beside it)
const turretBlack = (c, q = TURRET) => {
  const parts = [S.polygon(G.offsetPts(q.handle, BORDER, 1.0)), rect(...q.neck), S.polygon(G.offsetPts(q.head, BORDER)), S.polygon(G.offsetPts(q.eye, BORDER))];
  if (q.stem) parts.push(rect(...q.stem));
  if (q.base) parts.push(S.polygon(G.offsetPts(q.base, BORDER)));
  c.fill(S.union(...parts), P.flat(INK));
};
const turretBody = (c, q = TURRET) => {
  const k = c.k, [x0, y0, x1, y1] = q.box, mid = (y0 + y1) / 2;
  // the handle: one bar, lightest along its middle (the game: 0x6b to 0x88 on the small one, its right end darker)
  const hx1 = q.handle[2][0];
  c.fill(S.polygon(q.handle), (px) => shade(px, q.handleLevel + 0x1c * smooth(0, 0.5, -px.d) - q.handleEnd * smooth(hx1 - 1.4, hx1, px.x), k));
  if (q.neckBlue) c.fill(rect(...q.neckBlue.slice(0, 4)), (px) => shade(px, q.neckBlue[4], k, 0));
  // the head: plain blue, with a light row inside its edge: above, below (lighter to the right) and, on the large
  // one, at the left; the row follows the cut corners
  const [lx, ly0, ly1, lw, lg] = q.endLine;
  c.fill(S.polygon(q.head), (px) => {
    const x = px.x, y = px.y, depth = -px.d;
    const dl = x - x0, dr = x1 - x, vt = y - y0, vb = y1 - y;
    const low = y > mid, bot = q.bottom[0] + (q.bottom[1] - q.bottom[0]) * smooth(q.bottom[2], q.bottom[3], x);
    let edge = low ? bot : q.top;
    const atLeft = smooth(-0.3, 0.3, Math.min(vt, vb) - dl - q.cut[0] * 0.5);        // nearest to the upright left end
    edge += ((q.left === null ? q.base0 : q.left) - edge) * atLeft;
    edge += (q.base0 - edge) * smooth(-0.3, 0.3, Math.min(vt, vb) - dr - q.cut[1] * 0.5);                 // none inside the right end
    const deep = low && atLeft < 0.5 ? q.bottomDeep : 1;
    let g = q.base0 + (edge - q.base0) * (1 - smooth(deep - 0.3, deep + 0.25, depth));
    g += (lg - g) * 0.92 * bell(x - lx, lw) * smooth(0, 0.5, Math.min(y - ly0, ly1 - y));       // the light column inside the right end
    shade(px, g, k);
  });
  if (q.line) c.fill(rect(...q.line.slice(0, 4)), (px) => shade(px, q.line[4], k, 0));
  // the eye: blue, with a white middle that falls off to the blue round it
  const [ex, ey, erx, ery] = q.eyeLight;
  c.fill(S.polygon(q.eye), (px) => {
    const e = Math.hypot((px.x - ex) / erx, (px.y - ey) / ery);
    shade(px, q.eyeRing + (0xff - q.eyeRing) * (1 - smooth(0.42, 1.0, e)), k);
  });
  // the slit between head and eye
  c.fill(rect(...q.slit), P.flat(INK));
  // the window, the deeper blue round it (large), the dash above it
  if (q.surround) c.fill(rect(...q.surround.slice(0, 4)), (px) => shade(px, q.surround[4], k, 0));
  const win = curve(q.windowRows);
  c.fill(rect(...q.window), (px) => { const g = win(px.y); shade(px, g + (0x44 - g) * (1 - smooth(0, 0.3, -px.d)), k, 0); });
  c.fill(rect(...q.dash.slice(0, 4)), (px) => shade(px, q.dash[4], k, 0));
  // the light bars (each lighter towards its lower end, as in the game), the slots between them, the round light
  const [by0, by1] = q.barsY;
  for (const [bx0, bx1, g0, g1] of q.slots) {
    if (q.ticks) c.fill(rect(bx0, by0 - 1, bx1, by1 + 1), (px) => shade(px, q.ticks, k, 0));
    c.fill(rect(bx0, by0, bx1, by1), (px) => shade(px, g0 + (g1 - g0) * (px.y - by0) / (by1 - by0), k, 0));
  }
  for (const [bx0, bx1, g0, g1] of q.bars) c.fill(rect(bx0, by0, bx1, by1), (px) => shade(px, g0 + (g1 - g0) * (px.y - by0) / (by1 - by0), k, 0));
  const [cx, cy, cr] = q.light;
  c.fill(S.circle(cx, cy, cr), (px) => { const r = Math.hypot(px.x - cx, px.y - cy) / cr; put(px, TONE(0xff - (0xff - 0xb4) * smooth(0.5, 1, r)), 1 - smooth(0.8, 1, r)); });
  // the base and the reflection in its middle
  if (q.base) {
    const rows = curve(q.baseRows), [sx, sy, rx, ry] = q.shine;
    c.fill(S.polygon(q.base), (px) => {
      const g = rows(px.y), e = Math.hypot((px.x - sx) / rx, (px.y - sy) / ry);
      shade(px, g + (0xff - g) * (1 - smooth(0.4, 1.05, e)), k);
    });
  }
};
const turret = (c, q = TURRET) => { turretBlack(c, q); turretBody(c, q); };

// The shield behind the turret: straight above and at the sides (x 4..28, from y 4), below it the arc of a circle
// about the middle of the icon (16, 16) with radius 13.5. Read off the game's icon: sides at 4 and 28, lowest point
// 29.55; the redraws are the same figure (arc about 15.9..16.0, 16.4..16.9). With a border, the border is 2 wide all
// round, as in the game: the same figure with its sides at 2 and 30, from y 2, and radius 15.5 (the game's lowest
// point: 31.55), so that all of it lies inside the frame.
const SHIELD = { half: 12, top: 4, cx: 16, cy: 16, r: 13.5, border: 2 };
// (grown by `grow`, its upper corners are rounded by that much: an even border; the game's icon has those corners cut)
const shieldShape = (grow = 0) => {
  const q = SHIELD, hw = q.half + grow, top = q.top - grow;
  const upper = S.box(q.cx, (top + 60) / 2, hw, (60 - top) / 2, grow);
  return S.intersect(upper, S.union(S.halfPlane(q.cx, q.cy, 0, 1), S.circle(q.cx, q.cy, q.r + grow)));
};
// colour: the field's flat colour as in the game (white 0xfefeff, red 0xfc0c0c, yellow 0xfcfc0c). A coloured field
// deepens a little to its edge like every body here; a white one stays white.
const shield = (c, colour, border = true, edge = null) => {
  if (border) c.fill(shieldShape(SHIELD.border), P.flat(INK));
  const body = lin(colour), deep = edge ? lin(edge) : body;
  c.fill(shieldShape(0), (px) => put(px, mix3(deep, body, smooth(0, 1.4, -px.d))));
};

// ---- the crate of the droid upgrade icons ----------------------------------------------------------------------------
// Read off the game's icon (i_droidup01, 02, 03): a box x 4..28, y 18..30, its upper corners cut by 2, in the lighter
// blue (0x6e8bff); in it, in the deeper blue (0x2854ff): the two slanted side faces, three compartments
// (x 9..13, 14..18, 19..23, y 22..29) and the tops of the two partitions between them (x 13..14 and 18..19,
// y 19..21). A bottle stands in a compartment and fills it: a body 4 wide (y 22..29) and a neck 2 wide (y 20..22).
// One white bottle in the middle (I), two red ones at the left and the middle (II), three yellow ones (III).
const CRATE = {
  box: [[6, 18], [26, 18], [28, 20], [28, 30], [4, 30], [4, 20]],
  sides: [[[7, 19], [9, 19], [8, 21], [8, 29], [5, 29], [5, 21]], [[23, 19], [25, 19], [27, 21], [27, 29], [24, 29], [24, 21]]],
  rooms: [9, 14, 19], roomW: 4, roomY: [22, 29], tops: [[13, 19, 14, 21], [18, 19, 19, 21]], neck: [1, 20, 22],
};
const BOTTLE = {
  white: { rim: '#8ea4ee', edge: '#e4eaff', body: '#ffffff' },
  red: { rim: '#5e0703', edge: '#c8140a', body: '#fc1408' },
  yellow: { rim: '#6a5c00', edge: '#e2d400', body: '#fcf40c' },
};
const crateBlack = (c) => c.fill(S.polygon(G.offsetPts(CRATE.box, BORDER)), P.flat(INK));
// bottles: a list of [compartment (0, 1, 2), colour]
const crateBody = (c, bottles = []) => {
  const q = CRATE, k = c.k;
  c.fill(S.polygon(q.box), (px) => shade(px, 0x8e - 0x10 * (1 - smooth(0, 0.8, -px.d)), k));
  const deep = (px) => shade(px, 0x54 + 0x06 * smooth(0, 0.6, -px.d), k, 0);
  for (const pts of q.sides) c.fill(S.polygon(pts), deep);
  for (const x of q.rooms) c.fill(rect(x, q.roomY[0], x + q.roomW, q.roomY[1]), deep);
  for (const t of q.tops) c.fill(rect(...t), deep);
  for (const [i, colour] of bottles) {
    const x = q.rooms[i], n = q.neck[0], pal = BOTTLE[colour], cr = lin(pal.rim), ce = lin(pal.edge), cb = lin(pal.body);
    const pts = [[x + n, q.neck[1]], [x + q.roomW - n, q.neck[1]], [x + q.roomW - n, q.neck[2]], [x + q.roomW, q.neck[2]], [x + q.roomW, q.roomY[1]], [x, q.roomY[1]], [x, q.neck[2]], [x + n, q.neck[2]]];
    c.fill(S.polygon(pts), (px) => put(px, mix3(mix3(ce, cb, smooth(0, 0.7, -px.d)), cr, step(RIM + px.d, k))));
  }
};

// ---- bodies modelled as surfaces --------------------------------------------------------------------------------------
// The rounded things of this sheet (the breastplate, the hand) are lit as surfaces: a body is given a height at every
// point, built from a few simple forms (a tube, a dome, a cushion with a flat top), and each place takes its level
// from how its surface stands to the light: what faces the viewer squarely gets the level `flat`, what leans to the
// light is lighter up to white, what leans away is deeper. So a form has a lit side and a shaded side, deepens
// where it rolls away to its edge, and two forms that meet make a crease; nothing else is drawn on it.
const LIGHT = [-0.42, -0.52, 0.74];       // from above and to the left, as in the game's icons
// the level a place gets by how much it faces the light (1: squarely; 0.74: a place facing the viewer)
const LEVELS = curve([[-1, 0x16], [-0.3, 0x20], [0, 0x36], [0.25, 0x56], [0.5, 0x80], [0.74, 0xb8], [0.9, 0xee], [1, 0xff]]);
// a Gaussian blur of a square field (sigma in pixels), edges held
const blurField = (src, n, sigma) => {
  const r = Math.max(1, Math.ceil(sigma * 2.5)), w = new Float32Array(2 * r + 1);
  let tot = 0;
  for (let i = -r; i <= r; i++) { w[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); tot += w[i + r]; }
  for (let i = 0; i < w.length; i++) w[i] /= tot;
  const tmp = new Float32Array(n * n), out = new Float32Array(n * n);
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * src[j * n + clamp(x + t, 0, n - 1)]; tmp[j * n + x] = a; }
  for (let j = 0; j < n; j++) for (let x = 0; x < n; x++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * tmp[clamp(j + t, 0, n - 1) * n + x]; out[j * n + x] = a; }
  return out;
};
// The shape drawn as a lit surface. height(x, y): how high the body stands there (units; 0 off it).
//   o.soften  the heights are smoothed over this many units first (creases and corners rounded off; default 0.22)
//   o.levels  the level by how much a place faces the light (default LEVELS);  o.light  (default LIGHT)
//   o.adjust  (level, px, facing) -> level: a change laid over the lighting (a shadow one form casts on another)
//   o.edge    how many levels the colour deepens at the outline, o.depth over how far in (default 0x20 over 0.7)
//   o.rim     the thin dark line on the outline (default RIM; 0 for none)
const surface = (c, shape, height, o = {}) => {
  const n = c.size, k = c.k, f = c.field(shape);
  let H = new Float32Array(n * n);
  for (let j = 0, i = 0; j < n; j++) { const y = (j + 0.5) / k; for (let x = 0; x < n; x++, i++) H[i] = f[i] < 1.5 ? height((x + 0.5) / k, y) : 0; }
  const soften = o.soften === undefined ? 0.22 : o.soften;
  if (soften > 0) H = blurField(H, n, soften * k);
  const l = o.light || LIGHT, ll = Math.hypot(l[0], l[1], l[2]), lx = l[0] / ll, ly = l[1] / ll, lz = l[2] / ll;
  const lev = o.levels || LEVELS, edge = o.edge === undefined ? 0x20 : o.edge, depth = o.depth || 0.7, rim = o.rim === undefined ? RIM : o.rim;
  return c.fill(shape, (px) => {
    const i = px.i, x = i % n, j = (i - x) / n;
    const nx = -(H[x < n - 1 ? i + 1 : i] - H[x > 0 ? i - 1 : i]) * k * 0.5, ny = -(H[j < n - 1 ? i + n : i] - H[j > 0 ? i - n : i]) * k * 0.5;
    const facing = (nx * lx + ny * ly + lz) / Math.hypot(nx, ny, 1);
    let g = lev(facing);
    if (o.adjust) g = o.adjust(g, px, facing);
    shade(px, g - edge * (1 - smooth(0, depth, -px.d)), k, rim);
  });
};
// heights: a tube from a to b (a half round bar of radius r, rising to `rise` along its middle, its ends round)
const tube = (ax, ay, bx, by, r, rise = r) => {
  const d = S.capsule(ax, ay, bx, by, 0);
  return (x, y) => { const q = d(x, y) / r; return q >= 1 ? 0 : rise * Math.sqrt(1 - q * q); };
};
// a dome over an ellipse: `rise` at its middle, falling to nothing at its rim (the cap of a paraboloid: its slope
// stays finite, so that its rim is no hard line); turned by `turn` degrees
const dome = (cx, cy, rx, ry, rise, turn = 0) => {
  const co = Math.cos((turn * Math.PI) / 180), si = Math.sin((turn * Math.PI) / 180);
  return (x, y) => { const px = x - cx, py = y - cy, u = (px * co + py * si) / rx, v = (-px * si + py * co) / ry, q = u * u + v * v; return q >= 1 ? 0 : rise * (1 - q); };
};
// a cushion over a shape: rises from its edge over `depth` units along a quarter circle to `rise`, flat beyond
const pillow = (sdf, depth, rise) => (x, y) => { const d = sdf(x, y); if (d >= 0) return 0; const u = 1 - clamp(-d / depth, 0, 1); return rise * Math.sqrt(1 - u * u); };
const highest = (...hs) => (x, y) => { let h = 0; for (let i = 0; i < hs.length; i++) { const v = hs[i](x, y); if (v > h) h = v; } return h; };
const added = (...hs) => (x, y) => { let h = 0; for (let i = 0; i < hs.length; i++) h += hs[i](x, y); return h; };
// a closed outline from points with rounded corners: [[x, y] or [x, y, r], ...] -> its points
const outline = (pts) => S.roundedPoints(pts, 0, 0.06);
const mirrorPts = (pts, cx) => pts.map((p) => [2 * cx - p[0], p[1], ...p.slice(2)]).reverse();

// ---- the breastplate (armour proficiencies) ---------------------------------------------------------------------------
// Read off the game's icons. The middle one (i_armprof02) is exactly the same left and right of x = 16; the light one
// (i_armprof01) is the same breastplate without the shoulder plates, its right edge one pixel short. Here both carry
// the one construction, symmetric about x = 16:
//   collar   the upper edge y 9 between the straps, a deep blue band one unit high under it, deepest in the middle
//   chest    x 9..23, y 9..16: two bulges side by side (each light at its upper left, the left one's right side in
//            the crease between them)
//   sides    the body widens to x 8..24 from y 15, runs straight down to y 20 and draws in to x 10.8..21.2 at y 27
//   plate    in front of the lower body, x 11..21, y 16..27: a bar across (light along y 17..18), two pillars
//            (x 11..14 and 18..21) and between them a deeper recess x 14..18 from y 19 down, with a lighter line
//            down its middle
//   straps   two short tabs rising from the chest's upper corners, 3 wide, leaning out by 15 degrees, to y 6.6
//   shoulder plates (II only): at each side an upper plate x 4..8, y 9..14 and under it a lower one x 3..7,
//            y 15..17, a dark gap between them and between them and the body
const ARMOUR = {
  cx: 16,
  // the body's right half from the top of the axis to its bottom: [x, y, radius of the corner]
  half: [[16, 9], [20.5, 9, 0.3], [23, 10.2, 0.5], [23, 13.4, 0.6], [24, 14.8, 0.7], [24, 20, 3], [21.2, 27, 0.6], [16, 27]],
  strap: { at: [22.2, 10.4], lean: 15, len: 3.9, into: 1.2, half: 1.5, r: 0.55 },
  pec: [3.55, 12.9, 3.75, 3.7, 1.25],             // a bulge: its middle's distance from the axis, its y, radii, rise
  plate: [5, 16, 27], recess: [2, 19], neck: [4.5, 1.0],
  // a shoulder plate of II (the right one): the upper plate's outline and the lower one's
  pad: { upper: [[23.9, 9.0, 0.4], [26.7, 9.0, 1.0], [28, 10.8, 0.6], [28, 14.1, 0.4], [23.9, 14.1, 0.3]], lower: [[24.9, 14.9, 0.3], [29, 14.9, 0.5], [29, 17, 0.5], [24.9, 17, 0.3]],
    all: [[23.9, 9.0, 0.4], [26.7, 9.0, 1.0], [28, 10.8, 0.6], [28, 14.4, 0.3], [29, 15.1, 0.4], [29, 17, 0.5], [24.9, 17, 0.3], [24.9, 14.6, 0.2], [23.9, 14.1, 0.2]] },
};
const armourShapes = () => {
  const q = ARMOUR, right = q.half, left = mirrorPts(right.slice(1, -1), q.cx);
  const body = outline(right.concat(left));
  const a = (q.strap.lean * Math.PI) / 180, ax = Math.sin(a), ay = -Math.cos(a), nx = -ay, ny = ax, h = q.strap.half;
  const b = [q.strap.at[0] - ax * q.strap.into, q.strap.at[1] - ay * q.strap.into], e = [q.strap.at[0] + ax * q.strap.len, q.strap.at[1] + ay * q.strap.len];
  const strapR = [[e[0] - nx * h, e[1] - ny * h, q.strap.r], [e[0] + nx * h, e[1] + ny * h, q.strap.r], [b[0] + nx * h, b[1] + ny * h], [b[0] - nx * h, b[1] - ny * h]];
  return { body, strapR: outline(strapR), strapL: outline(mirrorPts(strapR, q.cx)), strapAxis: [b, e],
    pads: [q.pad, { upper: mirrorPts(q.pad.upper, q.cx), lower: mirrorPts(q.pad.lower, q.cx), all: mirrorPts(q.pad.all, q.cx) }] };
};
// pads: with the shoulder plates of II
const armour = (c, { pads = false } = {}) => {
  const q = ARMOUR, k = c.k, sh = armourShapes(), cx = q.cx;
  const body = S.polygon(sh.body), strapR = S.polygon(sh.strapR), strapL = S.polygon(sh.strapL);
  const padShapes = pads ? sh.pads.map((p) => ({ all: S.polygon(outline(p.all)), upper: S.polygon(outline(p.upper)), lower: S.polygon(outline(p.lower)) })) : [];
  // all the black first: one unit round everything
  c.fill(S.union(body, strapR, strapL, ...padShapes.map((p) => p.all)), P.flat(INK), BORDER);
  // the straps: half round tabs (the game: 0xc8..0xdb along the middle, 0x51..0xa2 at the sides, navy on the top end)
  const [sb, se] = sh.strapAxis;
  const sl = Math.hypot(se[0] - sb[0], se[1] - sb[1]), ex = se[0] - ((se[0] - sb[0]) / sl) * 1.0, ey = se[1] - ((se[1] - sb[1]) / sl) * 1.0;
  for (const [shape, m] of [[strapR, 1], [strapL, -1]]) {
    const X = (x) => (m > 0 ? x : 2 * cx - x);
    surface(c, shape, tube(X(sb[0]), sb[1], X(ex), ey, q.strap.half, 1.0), { edge: 0x28 });
  }
  // the body: a cushion with the two bulges of the chest on it and the plate in front of its lower half
  const [pd, py, prx, pry, prise] = q.pec, [ph, pt, pb] = q.plate, [rh, rt] = q.recess;
  const arch = S.intersect(S.subtract(rect(cx - ph, pt, cx + ph, pb + 2), rect(cx - rh, rt, cx + rh, pb + 3)), body);
  const recess = S.intersect(rect(cx - rh, rt, cx + rh, pb + 3), body);
  const height = added(pillow(body, 1.5, 0.75), dome(cx - pd, py, prx, pry, prise), dome(cx + pd, py, prx, pry, prise));
  const af = c.field(arch), rf = c.field(recess);
  // The chest is lit as a surface (it comes out at the game's levels: white at each bulge's upper left, 0x7b in the
  // crease). Below it the levels are the game's own, row by row:
  //   plate   0xe9 at its upper left, falling 2.6 a unit to the right and 9 a unit downwards; deeper towards its
  //           edges: by 60 under its upper edge and beside the recess, 24 at its left edge, 70 over three units
  //           towards its right edge (the right pillar's shaded side), 0x60 along the lower edge
  //   recess  0x48 at its left, 0x60, then a lighter line just right of the middle (0x80: the lit edge of its right
  //           half, as the right bulge of the chest is lit beside the crease), 0x6e at its right
  //   sides   left: 0xe2 at y 15, falling 13 a unit downwards, deeper beside the plate; right, away from the light:
  //           0xb0 falling 15 a unit, deepest beside the plate (0x64)
  const fall = (d, w, a) => a * (1 - smooth(0, w, d));
  const RECESS = curve([[cx - rh, 0x4a], [cx - rh + 0.6, 0x48], [cx - 0.5, 0x60], [cx, 0x68], [cx + 0.15, 0x82], [cx + 0.7, 0x84], [cx + 1.2, 0x6e], [cx + rh, 0x70]]);
  surface(c, body, height, {
    soften: 0.28,
    adjust: (g, px) => {
      const x = px.x, y = px.y, i = px.i;
      if (rf[i] < 0) return RECESS(x) - (RECESS(x) - 0x52) * (x > cx ? 1 - smooth(rt + 1.4, rt + 2.4, y) : 0) - fall(pb - y, 1.0, 0x28);
      if (af[i] < 0) {
        const plane = 0xe9 - 2.6 * (x - (cx - ph + 1)) - 9 * (y - (pt + 1.5));
        return plane - Math.max(fall(y - pt, 1.3, 60), fall(x - (cx - ph), 1.0, 24), fall(cx + ph - x, 3, 70), fall(rf[i], 1.3, 60), fall(pb - y, 1.2, 0x60));
      }
      // the sides below the chest, and the chest's shadow on the plate's upper edge
      const low = smooth(14.0, 15.2, y);
      if (low > 0) {
        const side = x < cx ? Math.max(0xe2 - 13 * (y - 15), 0x2c) - 0x26 * smooth(cx - ph - 1.2, cx - ph, x) : Math.max(0xb0 - 15 * (y - 15.2), 0x24) - 0x44 * (1 - smooth(cx + ph, cx + ph + 1.3, x));
        const beside = smooth(ph - 0.6, ph + 0.4, Math.abs(x - cx));
        g += (side - g) * low * beside - 0x1c * low * (1 - beside);
      }
      return g;
    },
  });
  // the collar: the deep band under the upper edge between the straps
  const [nh, nd] = q.neck, R = (nh * nh + nd * nd) / (2 * nd);
  const band = S.intersect(S.circle(cx, 9 + nd - R, R), S.halfPlane(cx, 9, 0, -1), body);
  c.fill(band, (px) => shade(px, 0x2c + 0x0d * Math.abs(px.x - cx) + 0x30 * smooth(0.55, 0, -px.d), k, 0));
  // the shoulder plates of II, in front of the body's edge: two cushions, the upper one over the lower
  for (const p of padShapes) surface(c, p.all, highest(pillow(p.upper, 1.4, 0.95), pillow(p.lower, 0.9, 0.7)), { edge: 0x28, depth: 0.7 });
};

//// ---- forms shaded as cushions -------------------------------------------------------------------------------------
// A form (a finger, the back of a hand) shaded by itself: light in its middle (level `hi`), deepening to `lo` at its
// edge. The light middle stands off towards the light by `lean` units, so that the side turned from the light is
// the broader and deeper one; along the edge facing the light the colour deepens only over `edge` units and only to
// `lit` (default: half way between lo and hi). core: how far in from the edge the colour reaches `hi`; bend: how the
// colour rises over that distance (1: evenly; more: the deep colour reaches further in and the light stays small).
// soft: the depths are smoothed over that many units first, so that the light has no ridges where the nearest edge
// changes (default 0.4). fall: [x, y, levels a unit, most]: the whole form deepens away from the light, starting at
// that point (its lit side and its shaded side).
// Forms laid over one another this way make the creases of a body: the deep edge of one against the next.
const AWAY = [0.63, 0.78];                 // the direction away from the light
const cushion = (c, shape, o) => {
  const n = c.size, k = c.k, f = c.field(shape), lean = o.lean === undefined ? 0.4 : o.lean, soft = o.soft === undefined ? 0.4 : o.soft;
  let D = new Float32Array(n * n);
  for (let i = 0; i < D.length; i++) D[i] = f[i] < 0 ? -f[i] : 0;
  if (soft > 0) D = blurField(D, n, soft * k);
  const ox = Math.round(AWAY[0] * lean * k), oy = Math.round(AWAY[1] * lean * k);
  const hi = o.hi, lo = o.lo, core = o.core, edge = o.edge === undefined ? 0.55 : o.edge, lit = o.lit === undefined ? (lo + hi) / 2 : o.lit, bend = o.bend || 1.3;
  return c.fill(shape, (px) => {
    const i = px.i, x = i % n, j = (i - x) / n;
    const t = clamp(D[clamp(j + oy, 0, n - 1) * n + clamp(x + ox, 0, n - 1)] / core, 0, 1);
    let g = Math.min(lo + (hi - lo) * Math.pow(t, bend), lit + (hi - lit) * smooth(0, edge, -px.d));
    if (o.fall) g -= clamp(o.fall[2] * ((px.x - o.fall[0]) * AWAY[0] + (px.y - o.fall[1]) * AWAY[1]), 0, o.fall[3]);
    if (o.adjust) g = o.adjust(g, px);
    shade(px, g, k, o.rim === undefined ? 0 : o.rim, o.tone || TONE, o.alpha ? o.alpha(px) : 1);
  });
};
// the thin dark line along the outline of a whole body made of several forms
const rimLine = (c, all, level = 0x16) => { const k = c.k, col = TONE(level); c.fill(all, (px) => put(px, col, step(RIM + px.d, k))); };

// ---- the pointing hand (use item) -----------------------------------------------------------------------------------
// What the game's icon is: a gloved right hand seen from its back, the forefinger pointing down and to the right, the
// other three fingers curled under, the thumb at the lower left pointing down, the wrist with its cuff at the upper
// left. Read off its pixels:
//   the forefinger's edges run at exactly 45 degrees (one pixel right for one down); it is 3 wide, its tip at 27.4, 22.9
//   the three curled fingers show as three light streaks side by side, their ends at 20.5, 20.2; 18, 22; 15.6, 23.8
//   the back of the hand: upper edge y 9 from x 9.3 to 18.4, then an edge at 45 degrees down to 22.3, 12.9, parallel
//   to the forefinger; under its lower edge (y 16) the deepest blue of the icon, where the fingers turn under
//   the forefinger's knuckle: the white of the icon (x 20..22, y 16..19), with a dark crease across the finger beyond it
//   the thumb: a broader lobe from 8.4, 16.5 down to its end at y 23, white along its middle
//   the cuff: from its peak at 7.3, 8.3 down the upper left edge to the tip at 2.6, 15, back along the lower edge
// Constructed: all four fingers point the same way (45 degrees) and are one width (3); the three curled ones are one
// finger moved twice by the same step, 3 across and 0.5 back, so that they are evenly spaced with the forefinger
// (in the game their streaks lie 3.1, 3.6 and 3.1 apart). Each part is a cushion; they overlap as the parts of a
// hand do, the deep edge of one making the crease against the next. One body: no line between its parts.
const HAND = {
  finger: 1.5,                                    // half a finger's width
  // fingers by their middle lines in the frame laid along them: s the line's place across, t0 where it starts
  // (under the hand), t1 the middle of its round end; (x, y) = ((t + s), (t - s)) / sqrt 2
  index: { s: 3.2, t0: 27.0, t1: 34.5 },
  curled: { s: 0.2, t0: 22.4, t1: 27.6, step: [-3.0, -0.5], n: 3 },
  knuckle: { s: 2.8, t0: 24.0, t1: 27.5, r: 1.9 },   // the forefinger's root, a little broader than the finger
  thumb: [8.5, 16.3, 9.5, 20.4, 2.6],             // from, to, radius
  back: [[9.3, 9.0, 0.8], [18.4, 9.0, 2.0], [22.3, 12.9, 1.6], [22.6, 15.6, 1.0], [19.0, 16.4, 1.2], [10.0, 17.2, 1.4], [8.2, 14.5]],
  cuff: [[7.3, 8.3, 0.6], [10.8, 9.4, 0.9], [9.4, 16.2, 1.1], [5.5, 17.9, 0.9], [2.6, 15.0, 0.7]],
  // what lies under the fingers and shows between them, in shadow
  palm: [[9.2, 15.6], [19.6, 15.0], [20.4, 19.2, 1], [15.3, 23.4, 1], [12.2, 23.9, 1], [9.4, 22.4, 1]],
};
const handForms = () => {
  const q = HAND, h = Math.SQRT1_2, at = (t, s) => [(t + s) * h, (t - s) * h], r = q.finger;
  const line = (f) => [...at(f.t0, f.s), ...at(f.t1, f.s)];
  const curled = Array.from({ length: q.curled.n }, (_, i) => line({ s: q.curled.s + i * q.curled.step[0], t0: q.curled.t0 + i * q.curled.step[1], t1: q.curled.t1 + i * q.curled.step[1] }));
  return { r, index: line(q.index), curled, knuckle: [...line(q.knuckle), q.knuckle.r], thumb: q.thumb, back: outline(q.back), cuff: outline(q.cuff), palm: outline(q.palm) };
};
// border: with the black round it (the game's second icon of the hand has none)
const hand = (c, { border = true } = {}) => {
  const f = handForms(), r = f.r;
  const cap = (l, rr) => S.capsule(l[0], l[1], l[2], l[3], 2 * rr);
  const back = S.polygon(f.back), cuff = S.polygon(f.cuff), palm = S.polygon(f.palm);
  const index = cap(f.index, r), fingers = f.curled.map((l) => cap(l, r)), knuckle = cap(f.knuckle, f.knuckle[4]), thumb = cap(f.thumb, f.thumb[4]);
  // the back of the hand and the forefinger's knuckle are one form, melted together
  const body = S.blend(back, knuckle, 0.9);
  const all = S.union(body, cuff, palm, index, thumb, ...fingers);
  if (border) c.fill(all, P.flat(INK), BORDER);
  const bf = c.field(body), cf = c.field(cuff);
  // the shadow of the hand's back on what comes out from under its lower edge
  const under = (g, px) => g - 0x50 * (1 - smooth(0, 1.5, bf[px.i]));
  c.fill(palm, (px) => shade(px, 0x2a, c.k, 0));
  for (let i = fingers.length - 1; i >= 0; i--) cushion(c, fingers[i], { hi: 0xfa, lo: 0x30, core: 1.35, bend: 1.15, lean: 0.3, soft: 0.25, adjust: under });
  cushion(c, index, { hi: 0xf8, lo: 0x38, core: 1.35, bend: 1.1, lean: 0.25, soft: 0.25, adjust: (g, px) => g - 0x48 * (1 - smooth(0, 1.0, bf[px.i])) });
  // (the knuckle carries the white of the icon: a soft light on the body's lower right end)
  const kx = (f.knuckle[0] + 3 * f.knuckle[2]) / 4 - 0.25, ky = (f.knuckle[1] + 3 * f.knuckle[3]) / 4 - 0.1;
  cushion(c, body, { hi: 0xf4, lo: 0x40, core: 2.7, bend: 1.3, lean: 1.9, lit: 0x90, soft: 0.7,
    adjust: (g, px) => { const v = g - 0x2c * (1 - smooth(0, 1.6, cf[px.i])); return v + (0xff - v) * 0.95 * bell(Math.hypot(px.x - kx, px.y - ky), 1.25); } });
  cushion(c, thumb, { hi: 0xff, lo: 0x3c, core: 2.2, bend: 1.1, lean: 0.4, soft: 0.4, adjust: (g, px) => g - 0x20 * (1 - smooth(0, 1.0, cf[px.i])) });
  cushion(c, cuff, { hi: 0xf2, lo: 0x58, core: 2.3, bend: 1.2, lean: 1.1, lit: 0xa0, soft: 0.6 });
  rimLine(c, all);
};

// ---- bodies made of several cushions -----------------------------------------------------------------------------------
// A form is { cap: [x0, y0, x1, y1, r] } (a bar with round ends), { taper: [x0, y0, r0, x1, y1, r1] } (a bar that is
// r0 thick at its first end and r1 at its second, its sides straight between the two round ends), { circle: [x, y, r] },
// { poly: [[x, y, r], ...] } (a closed outline, corners rounded) or { blend: [forms], k } (several forms melted into
// one over the distance k: fingers running out of a palm), with the cushion's levels (hi, lo, core, lean, bend, lit, soft) or one flat
// level (flat). fade: [x, y, r0, r1]: the form is clear within r0 of that point and whole beyond r1 (a finger running
// out of a palm without an edge). The forms are laid in the order given; the black goes round all of them together.
// the distance to a bar with round ends of different radii (after Inigo Quilez' uneven capsule)
const taper = (ax, ay, ra, bx, by, rb) => {
  const h = Math.hypot(bx - ax, by - ay) || 1e-9, ux = (bx - ax) / h, uy = (by - ay) / h, b = (ra - rb) / h, a = Math.sqrt(Math.max(1 - b * b, 0));
  return (x, y) => {
    const px = x - ax, py = y - ay, t = px * ux + py * uy, s = Math.abs(-px * uy + py * ux), k = s * -b + t * a;
    if (k < 0) return Math.hypot(s, t) - ra;
    if (k > a * h) return Math.hypot(s, t - h) - rb;
    return s * a + t * b - ra;
  };
};
const formShape = (f) => (f.blend ? f.blend.map(formShape).reduce((p, q) => S.blend(p, q, f.k || 0.6)) : f.cap ? S.capsule(f.cap[0], f.cap[1], f.cap[2], f.cap[3], 2 * f.cap[4])
  : f.taper ? taper(f.taper[0], f.taper[1], f.taper[2], f.taper[3], f.taper[4], f.taper[5]) : f.circle ? S.circle(f.circle[0], f.circle[1], f.circle[2]) : S.polygon(outline(f.poly)));
const mirrorForm = (f, cx) => ({ ...f, ...(f.blend ? { blend: f.blend.map((g) => mirrorForm(g, cx)) } : f.cap ? { cap: [2 * cx - f.cap[0], f.cap[1], 2 * cx - f.cap[2], f.cap[3], f.cap[4]] }
  : f.taper ? { taper: [2 * cx - f.taper[0], f.taper[1], f.taper[2], 2 * cx - f.taper[3], f.taper[4], f.taper[5]] } : f.circle ? { circle: [2 * cx - f.circle[0], f.circle[1], f.circle[2]] } : { poly: mirrorPts(f.poly, cx) }),
  ...(f.fade ? { fade: [2 * cx - f.fade[0], f.fade[1], f.fade[2], f.fade[3]] } : {}) });
// part: 'border' the black only (returns the outline of them all), 'body' everything else; tone: the colour ramp
const figure = (c, forms, { border = true, rim = true, part = null, tone = TONE, rimTone = 0x16 } = {}) => {
  const shapes = forms.map(formShape), all = S.union(...shapes);
  if (border && part !== 'body') c.fill(all, P.flat(INK), BORDER);
  if (part === 'border') return all;
  forms.forEach((f, i) => {
    if (f.flat !== undefined) c.fill(shapes[i], (px) => shade(px, f.flat, c.k, 0, tone));
    else cushion(c, shapes[i], { tone, ...f, alpha: f.fade ? (px) => smooth(f.fade[2], f.fade[3], Math.hypot(px.x - f.fade[0], px.y - f.fade[1])) : null });
  });
  if (rim) { const col = tone(rimTone), k = c.k; c.fill(all, (px) => put(px, col, step(RIM + px.d, k))); }
  return all;
};

// ---- white arrows ----------------------------------------------------------------------------------------------------
// Read off the game's icons: a head that is a right triangle 6 by 6 and a shaft 2.1 wide (three pixels across the
// diagonal). The arrow of "equip" points down and to the right at the corner 9, 9; that of "unequip" is the same
// arrow turned upside down, pointing up and to the right at 29, 3. The arrow of "use on forearm" points left: its
// point at 20, 7.5, its head 5 long and 9 high, its shaft 4 long and 5 high.
const ARROW_IN = [[3.25, 1.75], [6.75, 5.25], [9, 3], [9, 9], [3, 9], [5.25, 6.75], [1.75, 3.25]];
const ARROW_OUT = ARROW_IN.map(([x, y]) => [x + 20, 12 - y]).reverse();
const ARROW_LEFT = [[20, 7.5], [25, 3], [25, 5], [29, 5], [29, 10], [25, 10], [25, 12]];
// part: 'border' the black only, 'body' the white only
const arrow = (c, pts, part) => {
  if (part !== 'body') c.fill(S.polygon(G.offsetPts(pts, BORDER, 1.6)), P.flat(INK));
  if (part !== 'border') c.fill(S.polygon(pts), (px) => shade(px, 0xff, c.k));
};

// ---- the open hands (equip, unequip) ------------------------------------------------------------------------------------
// Read off the game's icons (the redraws lie on them within half a unit).
// Equip: a hand reaching up and to the right, its wrist at the lower left: four fingers 2.5 wide fanning out at
// 35, 26, 23 and 25 degrees above level, their ends at 22.3, 7.2; 26.8, 10.7; 26.9, 15.2; 24.6, 20.9; the thumb a short
// stub at the upper left (end 12.5, 10). In the game the frame cuts the wrist off flat at the left and below; here
// it is finished round inside the frame.
// Unequip: a hand held out to the right, palm up, its wrist at the left: the thumb above, running to 19, 7.7; the
// forefinger level (end 27.5, 16), the others dropping away below it (ends 26.9, 22; 25.2, 25.1; 20.4, 28).
// Each hand is ONE form: the palm and the fingers melted together (a finger 1.5 thick where it leaves the palm, 1.1
// at its end), light all over its middle and deepening to its edge, so that the fingers stand out by their own edges
// and no line parts them from the palm.
const OPEN = { hi: 0xea, lo: 0x58, core: 1.05, lean: 0.25, bend: 1.0, lit: 0xa8, soft: 0.3, k: 0.7 };
const EQUIP = [{ ...OPEN, fall: [6, 14, 3.0, 0x30], blend: [
  { poly: [[10.6, 11.8, 1.2], [15.6, 12.3, 1.0], [18.6, 16.8, 1.5], [19.4, 23.2, 1.2], [11.0, 29.4, 1.5], [4.2, 30.0, 1.8], [2.0, 27.6, 1.4], [2.0, 23.6, 1.5], [5.6, 17.0, 1.0]] },
  { taper: [14.6, 12.4, 1.5, 21.3, 7.8, 1.1] },
  { taper: [16.4, 15.9, 1.5, 25.7, 11.25, 1.1] },
  { taper: [17.0, 19.5, 1.5, 25.8, 15.7, 1.1] },
  { taper: [16.0, 24.8, 1.5, 23.5, 21.4, 1.1] },
  { taper: [9.6, 15.2, 1.7, 12.2, 11.0, 1.3] },
] }];
// (the game shades the hollow of this palm: 0x66 about 7.5, 16.6 in a field of 0xb0 to 0xd0)
const UNEQUIP = [{ ...OPEN, fall: [3, 12, 1.6, 0x20], adjust: (g, px) => g - 0x58 * bell(Math.hypot((px.x - 7.6) / 4.2, (px.y - 16.7) / 2.3), 1), blend: [
  { poly: [[4.8, 11.4, 1.2], [12.6, 12.6, 1.5], [17.2, 14.4, 1.0], [18.2, 21.5, 1.5], [14.0, 25.2, 1.5], [5.0, 23.0, 2.0], [1.0, 19.0, 2.0], [1.0, 15.6, 2.0]] },
  { taper: [12.4, 23.3, 1.4, 19.5, 27.4, 1.05] },
  { taper: [15.4, 21.3, 1.5, 24.1, 24.6, 1.1] },
  { taper: [16.0, 18.9, 1.5, 25.7, 21.6, 1.1] },
  { taper: [15.4, 15.2, 1.5, 26.3, 15.9, 1.1] },
  { taper: [6.4, 12.1, 1.9, 17.5, 8.15, 1.35] },
] }];
// an open hand with its arrow: all black first
const openHand = (c, forms, arrowPts) => {
  figure(c, forms, { part: 'border' }); arrow(c, arrowPts, 'border');
  figure(c, forms, { part: 'body' }); arrow(c, arrowPts, 'body');
};

// ---- the forearm with the cross (use on forearm) ------------------------------------------------------------------------
// Read off the game's icon: a broad plate lying at 45 degrees from the upper left (its end the line x + y = 10.5, its
// long edges x - y = 7.5 and x - y = -8) down to the wrist (x + y = 33), lighter along its edge (0xd0) than within
// (0xa0); below it the hand, a narrower block with the thumb set off by a notch at the bottom (x 20..22). On the
// plate a white disc about 11.5, 11.5 carrying a white cross (arms 1 wide, 5 long) in a navy outline (3 wide, 7 long).
// The white arrow at the upper right points left at it.
const FOREARM = {
  plate: [[9, 1.5, 0.8], [20.25, 12.75, 0.8], [12.5, 20.5, 0.8], [1.25, 9.25, 0.8]],
  hand: [[18.2, 14.6], [26.6, 20.4, 1.5], [29, 23.2, 1.2], [29, 27.2, 1.2], [22.8, 28, 0.8], [22.2, 26, 0.3], [20.2, 26, 0.3], [20, 28, 0.9], [17.4, 28, 0.9], [17.2, 23.5, 1.5], [13.4, 19.6]],
  cross: [11.5, 11.5], disc: 4.2, outer: [1.5, 3.5], inner: [0.5, 2.5],
};
const forearm = (c) => {
  const q = FOREARM, k = c.k, plate = S.polygon(outline(q.plate)), hand = S.polygon(outline(q.hand)), [cx, cy] = q.cross;
  c.fill(S.union(plate, hand), P.flat(INK), BORDER); arrow(c, ARROW_LEFT, 'border');
  cushion(c, hand, { hi: 0xd8, lo: 0x4c, core: 2.4, lean: 0.9, soft: 0.6, rim: RIM });
  // the plate: plain within, falling a little away from the light; a light band one unit wide inside its edge
  c.fill(plate, (px) => {
    const g = 0xb0 - 2.2 * ((px.x - 9) + (px.y - 2)) * 0.5;
    shade(px, g + (0xd6 - g) * (1 - smooth(0.8, 1.25, -px.d)), k);
  });
  const plus = (hw, hl) => S.union(rect(cx - hw, cy - hl, cx + hw, cy + hl), rect(cx - hl, cy - hw, cx + hl, cy + hw));
  c.fill(S.circle(cx, cy, q.disc), (px) => shade(px, 0xf4 - 0x18 * (1 - smooth(0, 0.8, -px.d)), k, 0));
  c.fill(plus(q.outer[0], q.outer[1]), (px) => shade(px, 0x10, k, 0));
  c.fill(plus(q.inner[0], q.inner[1]), P.flat('#ffffff'));
  arrow(c, ARROW_LEFT, 'body');
};

// ---- the red droid (disable droid, destroy droid) ---------------------------------------------------------------------
// The game's reds lie on one ramp too (white, 0xfce4e4, 0xfc9c84, 0xfc543c, 0xe43c24, dark red), again in step with
// the green channel: a shade is given by its green level as for the blues.
const TONE_RED = ramp([[0x00, '#1c0200'], [0x10, '#5e0703'], [0x24, '#b4120a'], [0x3c, '#e43c24'], [0x54, '#fc543c'], [0x6c, '#fc6c54'], [0x84, '#fc846c'], [0x9c, '#fc9c84'],
  [0xb4, '#fcb4b4'], [0xcc, '#fccccc'], [0xe4, '#fce4e4'], [0xff, '#ffffff']]);
// Read off the game's icons, both the same left and right of x = 16:
//   body    a box x 9.5..22.5 from y 17, drawn in below to a waist x 11.5..20.5 (y 26..28), standing on a low dome
//           (x 7.5..24.5 at y 30.5); light along its upper edge and its left side; in its front a pale square
//           x 13..19, y 18..24 with a dark red cross from corner to corner (strokes 1.4 wide)
//   head    (disable) a pale dome x 10..22, y 2..7, flat below; a neck x 14..18 to y 9
//   clamp   (disable) under the head, x 11..21, y 9..15, its corners rounded, open below (x 15..17 from y 13): red
//           with a white line one unit wide inside its edge
//   destroy: no head; a hammer comes down from the upper right (its head a block about 10.6, 10 with a thin top
//           at x 7..9, its handle 3.6 thick up to 24.5, 3.5), and four pieces fly off
const DROID = {
  cx: 16,
  body: [[9.5, 17, 0.6], [22.5, 17, 0.6], [22.5, 24.6, 1.4], [20.5, 26.2, 0.6], [20.5, 27.9, 0.2], [22.6, 28.3, 1.0], [24.5, 30.5, 0.8], [7.5, 30.5, 0.8], [9.4, 28.3, 1.0], [11.5, 27.9, 0.2], [11.5, 26.2, 0.6], [9.5, 24.6, 1.4]],
  panel: [13, 18, 19, 24], stroke: 0.7,
  dome: [16, 7, 6, 5], neck: [14, 6.5, 18, 9.5],
  clamp: [11, 9, 21, 15, 1.6], gap: [15, 13, 17, 16],
  hammer: { handle: [10.8, 9.4, 23.9, 3.7, 1.8], head: [[8.6, 6.0, 0.5], [13.4, 5.2, 0.5], [14.4, 13.2, 0.5], [9.4, 14.2, 0.5]], top: [[7.0, 1.8, 0.3], [9.0, 1.6, 0.3], [9.6, 8.5], [7.4, 8.8]] },
  pieces: [[[17.2, 10.2, 0.3], [19.9, 12.5, 0.3], [17.2, 14.5, 0.3]], [[6.6, 12.8, 0.3], [6.7, 17.0, 0.3], [3.8, 16.9, 0.3]], [[9.0, 15.9, 0.3], [13.2, 15.9, 0.3], [12.2, 17.6, 0.3], [9.0, 17.6, 0.3]]],
  spark: [4, 10.5, 6, 10.5, 0.55],
};
const droidBody = (c, part) => {
  const q = DROID, k = c.k, body = S.polygon(outline(q.body));
  if (part !== 'body') c.fill(body, P.flat(INK), BORDER);
  if (part === 'border') return;
  // the body: mid red, lighter along its upper edge and down its left side, deeper to the right and in the waist
  c.fill(body, (px) => {
    const x = px.x, y = px.y;
    let g = 0x98 - 3.2 * (x - 10) - 1.2 * (y - 18);
    g += (0xe2 - g) * (1 - smooth(17.5, 18.4, y)) + (0xcc - g) * 0.8 * (1 - smooth(10.2, 11.2, x)) * smooth(17.6, 18.6, y) * (1 - smooth(23.4, 24.6, y));
    g -= 0x40 * smooth(25.4, 26.6, y) * (1 - smooth(27.6, 28.6, y));                       // the waist in shadow
    if (y > 28) g = 0x3c + (0xd0 - 0x3c) * smooth(3.0, 8.0, Math.abs(x - q.cx)) - 0x18 * (1 - smooth(28, 29.4, y));    // the dome it stands on: light at its two ends
    shade(px, g - 0x20 * (1 - smooth(0, 0.7, -px.d)), k, RIM, TONE_RED);
  });
  // the pale square and its cross
  const [x0, y0, x1, y1] = q.panel, panel = rect(x0, y0, x1, y1);
  c.fill(panel, (px) => shade(px, 0xe8 - 0x24 * (1 - smooth(0, 0.6, -px.d)), k, 0, TONE_RED));
  const cross = S.intersect(S.union(S.bar(x0, y0, x1, y1, 2 * q.stroke), S.bar(x1, y0, x0, y1, 2 * q.stroke)), panel);
  c.fill(cross, (px) => shade(px, 0x2e, k, 0, TONE_RED));
};
const droidHead = (c, part) => {
  const q = DROID, k = c.k, [dx, dy, rx, ry] = q.dome, [cx0, cy0, cx1, cy1, cr] = q.clamp;
  const dome = S.intersect(S.ellipse(dx, dy, rx, ry), S.halfPlane(dx, dy, 0, 1)), neck = rect(...q.neck);
  const clamp = S.subtract(S.box((cx0 + cx1) / 2, (cy0 + cy1) / 2, (cx1 - cx0) / 2, (cy1 - cy0) / 2, cr), rect(...q.gap));
  if (part !== 'body') c.fill(S.union(dome, neck, clamp), P.flat(INK), BORDER);
  if (part === 'border') return;
  // the neck: white with a red middle
  c.fill(neck, (px) => shade(px, 0xff - (0xff - 0x60) * (1 - smooth(0.7, 1.1, Math.abs(px.x - q.cx))), k, 0, TONE_RED));
  // the clamp: red, a white line one unit wide inside its edge (round the opening too)
  c.fill(clamp, (px) => shade(px, 0x84 + (0xfa - 0x84) * (1 - smooth(0.85, 1.15, -px.d)) - 0.9 * (px.x - cx0) * smooth(1.0, 1.4, -px.d), k, RIM, TONE_RED));
  // the head: a pale dome, a touch of red towards its rim
  c.fill(dome, (px) => shade(px, 0xfe - 0x40 * (1 - smooth(0, 1.6, -px.d)) - 2.5 * Math.max(px.x - dx, 0), k, RIM, TONE_RED));
};
const droidHammer = (c, part) => {
  const q = DROID.hammer, k = c.k;
  const handle = S.capsule(q.handle[0], q.handle[1], q.handle[2], q.handle[3], 0), bar = (x, y) => handle(x, y) - q.handle[4];
  const square = S.bar(q.handle[0], q.handle[1], q.handle[2], q.handle[3], 2 * q.handle[4]);
  const head = S.polygon(outline(q.head)), top = S.polygon(outline(q.top)), pieces = DROID.pieces.map((p) => S.polygon(outline(p)));
  const spark = S.capsule(...DROID.spark.slice(0, 4), 2 * DROID.spark[4]);
  if (part !== 'body') c.fill(S.union(square, head, top, spark, ...pieces), P.flat(INK), BORDER);
  if (part === 'border') return;
  void bar;
  cushion(c, square, { hi: 0xe6, lo: 0x54, core: 1.5, lean: 0.4, soft: 0.3, tone: TONE_RED, rim: RIM });
  cushion(c, top, { hi: 0xd8, lo: 0x6c, core: 0.9, lean: 0.2, soft: 0.2, tone: TONE_RED, rim: RIM });
  cushion(c, head, { hi: 0xee, lo: 0x54, core: 2.0, lean: 0.6, soft: 0.5, tone: TONE_RED, rim: RIM });
  for (const p of pieces) cushion(c, p, { hi: 0xf0, lo: 0x6c, core: 0.9, lean: 0.2, soft: 0.2, tone: TONE_RED, rim: RIM });
  c.fill(spark, P.flat('#ffffff'));
};

// ---- the suit of armour (heavy armour proficiency) ----------------------------------------------------------------------
// Read off the game's icon, which is exactly the same left and right of x = 16: a suit without a head. Given here
// is its left half; the right half is its mirror image.
//   shoulder plates  x 5.4..12.2, y 2.5..6.2, round on top;  collar  the deep band x 12..20, y 4..5.2 between them
//   chest    x 9.2..22.8, y 5..10.2: two bulges, light at 12 and at 19, the crease on the axis
//   belly    x 10..22 at y 10.8, drawn in to 11.4..20.6 at y 16.4; in its middle a small panel x 14..18, y 11.2..16
//   hips     a plate from x 10.6..21.4 at y 17 down to a blunt end x 14..18 at y 22.6
//   legs     from y 19.6 to 30, x 7.9..14.3 at the thigh, 8..12.7 at the foot
//   arms     upper arm from 6.4, 7 to 4.4, 12.2 (3.8 thick); forearm x 2..5, y 13..21.7; fist about 4.6, 23.9
// The game's deep bands (belt y 10..11, hips y 16..17, elbow, wrist) are the creases where these forms meet.
const SUIT_LIMB = { hi: 0xee, lo: 0x4c, core: 1.3, lean: 0.35, bend: 1.0, soft: 0.3 };
const SUIT_LEFT = [
  { taper: [6.4, 7.0, 2.0, 4.4, 12.2, 1.85], ...SUIT_LIMB, core: 1.6 },
  { taper: [3.7, 14.3, 1.7, 3.5, 20.2, 1.5], ...SUIT_LIMB, core: 1.3 },
  { circle: [4.6, 23.9, 1.95], ...SUIT_LIMB, core: 1.6 },
  { poly: [[8.6, 19.8, 1.0], [12.6, 19.4, 0.8], [14.3, 21.4, 0.6], [13.6, 24.6, 0.5], [12.7, 30, 0.6], [8.0, 30, 0.6], [7.9, 22.5, 0.5]], hi: 0xf2, lo: 0x4c, core: 2.2, lean: 0.9, bend: 1.0, soft: 0.5 },
];
const SUIT_MIDDLE = [
  { poly: [[9.2, 9.6], [22.8, 9.6], [22.2, 11.6], [9.8, 11.6]], flat: 0x5e },
  { poly: [[10.6, 17, 0.4], [21.4, 17, 0.4], [18.0, 22.6, 0.8], [14.0, 22.6, 0.8]], hi: 0xf0, lo: 0x4c, core: 2.0, lean: 0.5, bend: 1.0, soft: 0.5 },
  { poly: [[10, 10.8, 0.5], [22, 10.8, 0.5], [20.6, 16.4, 0.5], [11.4, 16.4, 0.5]], hi: 0xe2, lo: 0x50, core: 1.7, lean: 0.6, bend: 1.0, soft: 0.5 },
  { poly: [[14, 11.2, 0.3], [18, 11.2, 0.3], [18, 16, 0.3], [14, 16, 0.3]], flat: 0x58 },
  { poly: [[15, 12.2, 0.2], [17, 12.2, 0.2], [17, 16, 0.2], [15, 16, 0.2]], flat: 0x94 },
  { poly: [[12, 4], [20, 4], [20, 5.6], [12, 5.6]], flat: 0x48 },
];
const SUIT_FRONT = [
  { poly: [[5.4, 6.5, 0.5], [5.2, 4.3, 1.5], [7.3, 2.5, 1.7], [10.8, 2.5, 1.5], [12.4, 4.4, 0.8], [12.4, 6.5, 0.5]], hi: 0xf6, lo: 0x5c, core: 1.7, lean: 0.6, bend: 1.0, soft: 0.5 },
  { poly: [[8.7, 5.0, 0.8], [16, 5.0, 0.3], [16, 10.2, 0.3], [9.0, 10.2, 0.8]], hi: 0xfa, lo: 0x68, core: 2.2, lean: 1.0, bend: 1.0, lit: 0xd8, soft: 0.6 },
];
const suit = (c) => {
  const both = (list) => list.concat(list.map((f) => mirrorForm(f, 16)));
  figure(c, [...both(SUIT_LEFT), ...SUIT_MIDDLE, ...both(SUIT_FRONT)]);
};

module.exports = { INK, BORDER, RIM, lin, mix3, put, smooth, bell, ramp, curve, rect, step, sides, TONE, rimLevel, shade, CHIP, chip, chipLine, chipCorners, LOCK, padlock,
  TURRET, TURRET_UP, turret, turretBlack, turretBody, SHIELD, shieldShape, shield, CRATE, crateBlack, crateBody,
  LIGHT, LEVELS, surface, tube, dome, pillow, highest, added, outline, mirrorPts, cushion, rimLine, ARMOUR, armour, HAND, hand,
  figure, formShape, mirrorForm, arrow, ARROW_IN, ARROW_OUT, ARROW_LEFT, EQUIP, UNEQUIP, openHand, FOREARM, forearm, TONE_RED, DROID, droidBody, droidHead, droidHammer, suit };
