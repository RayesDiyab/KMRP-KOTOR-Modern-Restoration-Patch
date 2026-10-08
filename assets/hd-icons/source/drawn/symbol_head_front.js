'use strict';
// The icons of the sheet "head, seen from the front": the bust of parts/symbol_head_front.js, placed and scaled, with
// what each icon adds to it. The bust is ChatGPT's redrawn figure (measured: see the parts file). What is ADDED to it
// (a cross, a ring, letters, a disc, a glow) is simple, and for simple things the game's own icon gives the design:
// their places, sizes and colours are read off its pixels (tools/vmap.py, tools/head_front_px.py) and stated with
// each icon. Shapes the game's frame squeezed or cut are drawn whole, and what was changed for that is said.
// Units: the game icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const H = require('../parts/symbol_head_front');

const INK = H.INK, BORDER = H.BORDER;
const smooth = H.smooth;
const lin = (h) => P.hex(h).map(P.toLinear);
const put = (px, v) => { px.r = P.toSRGB(v[0]); px.g = P.toSRGB(v[1]); px.b = P.toSRGB(v[2]); px.a = 1; };
const mix3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];

// Where the busts stand. Scale 1 is the bust of the icons that show it down to the chest: in the game its black
// border runs from y 0 to 31 and from x 4 to 27 (or one further right); the redrawn bust with its 0.7 border fills
// the same room (body from y 0.8 to 30.06, 10.92 to each side of the axis). The axis is the game's (15.5 or 16.5).
const CHEST_TOP = 0.8;
// A disc's rim is two pixels in the game where the bust's border is one: here 1.4, twice 0.7, its outer edge where
// the game has it.
const RIM = 1.4;

// ---- two bars crossed ----------------------------------------------------------------------------------------------
// The cross that strikes something out: two straight bars of one width, crossing in their middles at 45 degrees, one
// piece (no edge where they cross), deepening to the edge with a thin dark line along it. No black border: in the
// game it is painted on the figure.  at: the crossing; half: from there to an end of a bar; w: the bars' width
const CROSS_RED = { rim: '#6a0e02', edge: '#a41804', body: '#c8250a' };
const cross = (c, at, half, w, palette = CROSS_RED) => {
  const k = half * Math.SQRT1_2, [x, y] = at;
  const shape = S.union(S.bar(x - k, y - k, x + k, y + k, w), S.bar(x - k, y + k, x + k, y - k, w));
  c.fill(shape, F.deepening(c.k, palette, { depth: 0.45, rim: 0.12 }));
  return shape;
};

// ---- a ring with a light middle ------------------------------------------------------------------------------------
// The mark on the chest of the "empathy" icons: a black ring, and inside it a white disc whose edge deepens to blue.
// In the game the ring is black from 3.5 to 5.2 round (15.5, 23.5), on the bust's axis (the redraw's ring is thinner,
// 3.9 to 4.9, with a soft blue ball in it).  at: the centre; ro, ri: the ring's outer and inner radius
const ORB = { at: [15.5, 23.5], ro: 5.2, ri: 3.5 };
const ORB_LIGHT = P.byDepth(1.5, [[0, '#1b47f2'], [0.1, '#3e65ff'], [0.34, '#7e99ff'], [0.62, '#dfe6ff'], [1, '#ffffff']]);
const orb = (c, { at, ro, ri } = ORB) => {
  c.fill(S.circle(at[0], at[1], ro), P.flat(INK));
  c.fill(S.circle(at[0], at[1], ri), ORB_LIGHT);
};

// ---- a disc behind the bust ------------------------------------------------------------------------------------------
// at: its centre; r: its outer radius (its rim included); rim: the black rim's width (0: none); ring: the width of a
// white ring inside the rim (0: none); stops: its colours by radius, [[radius, colour], ...] from the middle out;
// fringe: a thin blue line outside the rim (its width); part: 'border' (the black alone) or 'body' (the rest).
// The blue deepens to the disc's edge and carries a thin dark line there.
const disc = (c, at, r, { rim = 0, ring = 0, stops, fringe = 0, part = null, edge = '#0a2fc4' } = {}) => {
  const [x, y] = at, body = r - fringe - rim, blue = body - ring;
  if (part !== 'body') {
    if (fringe > 0) c.fill(S.circle(x, y, r), P.flat('#1541ec'));
    if (rim > 0) c.fill(S.circle(x, y, r - fringe), P.flat(INK));
  }
  if (part === 'border') return;
  if (ring > 0) {
    // the white ring: white in its middle, a little blue to both its edges
    const mid = body - ring / 2, pale = lin('#c3cfff'), white = lin('#ffffff');
    c.fill(S.circle(x, y, body), (px) => put(px, mix3(white, pale, smooth(0.25, 1, Math.abs(Math.hypot(px.x - x, px.y - y) - mid) / (ring / 2)))));
  }
  const ramp = P.ramp(stops.map(([rr, col]) => [rr / blue, col])), dark = P.hex(edge);
  c.fill(S.circle(x, y, blue), (px) => {
    ramp(Math.hypot(px.x - x, px.y - y) / blue, px);
    const w = S.clamp((0.14 + px.d) * c.k + 0.5, 0, 1);
    px.r += (dark[0] - px.r) * w; px.g += (dark[1] - px.g) * w; px.b += (dark[2] - px.b) * w; px.a = 1;
  });
};
// The disc of light behind the "empathy" busts (and the scoundrel's): pale where the bust stands, deepening to blue
// at its edge. Read off the game about (15.5, 15.5): e2e8ff at radius 7, c6d2ff at 8, a8baff at 9, 7e99ff at 10,
// 5a7cff at 11, 234ffa at 12, 0e3ae5 at 12.5.
const GLOW_DISC = [[0, '#e8edff'], [7, '#e2e8ff'], [8, '#c6d2ff'], [9, '#a8baff'], [10, '#7e99ff'], [11, '#5a7cff'], [12, '#234ffa'], [12.5, '#0e3ae5']];
const grown = (stops, k) => stops.map(([r, col]) => [r * k, col]);
// The ball behind the "Jedi defence" and "fortitude" busts: deep blue at its edge, paling towards the bust. In the game
// about (15.5, 15.5): 022ed9 at radius 12.5, 133fea at 11.5, 234ffa at 10.5, 3f66ff at 9.5, 5b7dff at 8.5, 7793ff at
// 7.5, 8fa6ff at 6.5.
const BALL = [[0, '#a6b8ff'], [5.5, '#a2b5ff'], [6.5, '#8fa6ff'], [7.5, '#7793ff'], [8.5, '#5b7dff'], [9.5, '#3f66ff'], [10.5, '#234ffa'], [11.5, '#133fea'], [12.9, '#022ed9']];

// ---- small white things with a black border --------------------------------------------------------------------------
const WHITE = { rim: '#8ea4ee', edge: '#e4eaff', body: '#ffffff' };          // (parts/flat.js: the white of the blue symbols)
const LETTER = { rim: '#8a8a96', edge: '#e4e4ec', body: '#ffffff' };         // the same without blue, for a red icon
// a plus sign: its middle, the length of an arm from the middle, the bars' width
const plus = (at, arm, w) => {
  const [x, y] = at, h = w / 2;
  return [[x - h, y - arm], [x + h, y - arm], [x + h, y - h], [x + arm, y - h], [x + arm, y + h], [x + h, y + h], [x + h, y + arm], [x - h, y + arm], [x - h, y + h], [x - arm, y + h], [x - arm, y - h], [x - h, y - h]];
};
// a star of four points: its middle, the points' distance from it, the distance of the corners between them
const star4 = (at, r, ri) => Array.from({ length: 8 }, (_, i) => { const a = ((-90 + 45 * i) * Math.PI) / 180, q = i % 2 ? ri : r; return [at[0] + q * Math.cos(a), at[1] + q * Math.sin(a)]; });
// The letter Z of the given width and height standing with its upper left corner at (x, y): two level bars and the
// slanted one between their far ends, all of the thickness t (the slanted bar measured across itself).
const zed = (x, y, w, h, t) => {
  // the slanted bar's width measured level, dx: dx * (h - 2t) / hypot(w - dx, h - 2t) = t
  const m = h - 2 * t, A = m * m - t * t, B = 2 * t * t * w, Cc = -t * t * (w * w + m * m);
  const dx = (-B + Math.sqrt(B * B - 4 * A * Cc)) / (2 * A);
  return [[x, y], [x + w, y], [x + w, y + t], [x + dx, y + h - t], [x + w, y + h - t], [x + w, y + h], [x, y + h], [x, y + h - t], [x + w - dx, y + t], [x, y + t]];
};
// white bodies from outlines' points, without their borders (those are laid first, with everything else's)
const whites = (c, list, palette = WHITE, st = {}) => { for (const pts of list) F.solid(c, pts, { palette, border: 0, depth: 0.3, rim: 0.1, ...st }); };

// The small shield on the chest of the "Jedi defence" busts. In the game: white, 7 wide (x 12 to 19) from y 20 down
// to a point at 27, its sides straight as far as y 25; its upper edge has three points of one height (the two
// corners and the middle) with a shallow hollow between each two (a pixel deep, two wide); round it a line one pixel
// wide, dark navy (00166b), not black. Here each hollow is a circular arc 2.9 wide and 0.5 deep.
const CHEST_SHIELD = S.mirrored(15.5, [[15.5, 20.0], ...G.arcPts(16.95, 18.15, 2.35, 128.1, 51.9).slice(1), [19.0, 20.0, 0.2], [19.0, 24.8, 0.3],
  ...Array.from({ length: 10 }, (_, i) => { const a = (Math.PI / 2) * ((i + 1) / 11); return [15.5 + 3.5 * Math.pow(Math.cos(a), 0.8), 24.8 + 2.2 * Math.pow(Math.sin(a), 1.15)]; }),
  [15.5, 27.0, 0.3]], { r: 0 });
const chestShield = (c) => {
  c.fill(CHEST_SHIELD, P.flat('#00145c'), BORDER);
  c.fill(CHEST_SHIELD, F.deepening(c.k, WHITE, { depth: 0.5, rim: 0.1 }));
};

// ---- the busts on a disc ---------------------------------------------------------------------------------------------
// The chest bust in front of a disc, each with its own black border (the "empathy" icons, the scoundrel's):
// all borders first, then the disc, then the bust.
const CHEST = { at: [15.5, CHEST_TOP], s: 1 };
// The chest bust standing IN a ball of its own blue (the "Jedi defence" icons, "fortitude"): in the game no black line
// runs between the two, the bust's white edge stands on the ball's blue; the black border goes round the two together.
// draw(c): what is laid between the ball and the bust.
const inBall = (c, pl, o, at, r, layers) => {
  const sh = H.shape(pl, o), body = S.circle(at[0], at[1], r - BORDER);
  c.fill(S.union(body, sh), P.flat(INK), BORDER);
  layers(body);
  const on = (y, x) => smooth(r - BORDER + 0.35, r - BORDER - 0.35, Math.hypot(x - at[0], y - at[1]));
  H.bust(c, pl, { hue: 'blue', ...o, border: 0, lit: on });
  return sh;
};

// ---- rays --------------------------------------------------------------------------------------------------------------
// A ray of light: a straight line that is widest (w) at its near end and comes to a point at its far end, pale and
// strong where it is wide, deep blue and faint at its point (in the game the rays are a pixel wide at most, pale blue
// at 0.7 opacity beside the head and fading out away from it).
const ray = (c, near, far, w) => {
  const f = G.frame(near, far), col = P.ramp([[0, '#dbe3ff'], [0.45, '#9fb3ff'], [1, '#2450fb']]);
  c.fill(S.polygon(f.pts([[0, -w / 2], [f.L, 0], [0, w / 2]])), (px) => { const t = S.clamp(f.t(px.x, px.y) / f.L, 0, 1); col(t, px); px.a = 0.95 - 0.6 * t; });
};

// ---- the shield round a bust (the "stance" icons) --------------------------------------------------------------------
// The outline of the game's shield, read off its pixels: a level upper edge with square corners (y 3), straight sides
// (x 5 and 26) down to `waist` (y 23), from there a straight edge at 45 degrees, and a round bottom: an arc of radius
// r (8.5) about a point on the axis that the slanting edges run into smoothly; its lowest point is then at
// waist + half - 0.414 r (y 30).
const shieldPts = (cx, top, half, waist, r) => {
  const cy = half + waist - r * Math.SQRT2, arc = G.arcPts(cx, cy, r, 45, 135);
  return [[cx - half, top], [cx + half, top], [cx + half, waist], ...arc, [cx - half, waist]];
};
// In the game: a black line (x 4 and 27, y 2, down to y 31), inside it a white band a pixel wide,
// then the field: deep blue (2854fe) in I, pale (c8d3ff) in II and III. The bust stands in the field without a border
// of its own, its head's top against the band (y 4), its shoulders running out to the band, its chest filling the
// shield's lower part. Along the shield's slanting lower edges the band is pale blue instead of white, and white
// again at the bottom. III has a second, outer frame: a white band between two black lines.
// k: the shield's size (1: as in I and II); outer: with the outer frame.
const stance = (c, field, { k = 1, outer = false } = {}) => {
  const cx = 15.5, top = outer ? 2.5 : 3.0, pts = shieldPts(cx, top, 10.5 * k, top + 20.0 * k, 8.5 * k);
  const shape = S.polygon(pts, 40), band = 1.0;
  if (outer) { c.fill(S.polygon(G.offsetPts(pts, 2.4), 40), P.flat(INK)); c.fill(S.polygon(G.offsetPts(pts, 1.7), 40), P.flat('#ffffff')); }
  c.fill(S.polygon(G.offsetPts(pts, BORDER), 40), P.flat(INK));
  // the band: white; pale along the slanting lower edges, white again at the bottom
  const white = lin('#ffffff'), pale = lin('#b4c4ff'), y0 = top + 19.6 * k, y1 = top + 26.6 * k;
  c.fill(shape, (px) => put(px, mix3(white, pale, smooth(y0, y0 + 1.6, px.y) * (1 - smooth(y1 - 2.2, y1 - 0.6, px.y)))));
  const inside = S.polygon(G.offsetPts(pts, -band), 40);
  c.fill(inside, field);
  H.clipped(c, inside, { at: [cx, top + band - 0.1], s: k }, { hue: 'blue', border: 0, lit: () => 1 });
};

module.exports = {
  // "Kill": the red bust with a cross over the face. In the game the cross is two lines one pixel wide from
  // (13, 6) to (19, 12) and from (19, 6) to (13, 12) (pixel corners 13..20 by 6..13), dark red (b61a00 to d22f14): the
  // crossing at (16.5, 9.5) on the bust's axis, the bars 4.6 long to each side and 1.3 wide (the redraw's are 5.0
  // and 1.7: fatter).
  ip_kill(c) {
    H.bust(c, { at: [16.5, CHEST_TOP], s: 1 }, { hue: 'red' });
    cross(c, [16.5, 9.5], 4.6, 1.3);
  },

  // "Empathy": the blue bust with the ring on its chest; the numbered ones differ by what stands behind it.
  // I: nothing.
  i_empathy01(c) { H.bust(c, CHEST, { hue: 'blue' }); orb(c); },
  // II: a disc of light, 12.5 in radius about (15.5, 15.5), without a border (none in the game; the redraw gives it one).
  i_empathy02(c) {
    disc(c, [15.5, 15.5], 12.5, { stops: GLOW_DISC });
    H.bust(c, CHEST, { hue: 'blue' }); orb(c);
  },
  // III: the disc with a black rim, out to 14.5.
  i_empathy03(c) {
    disc(c, [15.5, 15.5], 14.5, { rim: RIM, stops: grown(GLOW_DISC, 13.1 / 12.5) });
    H.bust(c, CHEST, { hue: 'blue' }); orb(c);
  },
  // (without a number): as III, the rim's outer edge blue (in the game the rim's outermost pixels are navy, not black).
  i_empathy(c) {
    disc(c, [15.5, 15.5], 14.5, { rim: RIM - 0.3, fringe: 0.3, stops: grown(GLOW_DISC, 13.1 / 12.5) });
    H.bust(c, CHEST, { hue: 'blue' }); orb(c);
  },

  // "Jedi defence" I: the blue bust with the small shield on its chest.
  i_jedidef01(c) { H.bust(c, CHEST, { hue: 'blue' }); chestShield(c); },
  // II: the bust in a ball: about (15.5, 15.5) out to 14.5, a border of one pixel, inside it a white ring of one pixel,
  // then deep blue paling towards the bust.
  i_jedidef02(c) {
    inBall(c, CHEST, {}, [15.5, 15.5], 14.5, () => disc(c, [15.5, 15.5], 14.5 - BORDER, { ring: 0.9, stops: BALL }));
    chestShield(c);
  },
  // III: the ball pale (d8e0ff at its edge to b4c3ff), and round the bust a band of deep blue three wide: pale blue
  // against the bust, deepening outwards to a dark line at its edge (in the game: a4b7ff, 7491ff, 4168ff going out from
  // the head at mid height, navy at the band's edge above; the pale that is left lies beside the head like two wings,
  // which is what the redraw made of it).
  i_jedidef03(c) {
    const sh = H.shape(CHEST), at = [15.5, 15.5];
    inBall(c, CHEST, {}, at, 14.5, (body) => {
      disc(c, at, 14.5 - BORDER, { stops: [[0, '#b4c3ff'], [10.5, '#b4c3ff'], [11.5, '#c1ceff'], [12.5, '#cbd6ff'], [13.8, '#d8e0ff']], edge: '#8ea0e8' });
      const band = P.ramp([[0, '#b3c2ff'], [0.3, '#7b96ff'], [0.62, '#4168ff'], [0.86, '#123ee9'], [1, '#0025b4']]), dark = P.hex('#001a7c'), W = 3.0;
      c.fill(S.intersect(S.grow(sh, W), body), (px) => {
        const d = c.field(sh)[px.i];                                   // the distance from the bust
        band(S.clamp(d / W, 0, 1), px);
        const w = S.clamp((d - (W - 0.22)) * c.k + 0.5, 0, 1);
        px.r += (dark[0] - px.r) * w; px.g += (dark[1] - px.g) * w; px.b += (dark[2] - px.b) * w; px.a = 1;
      });
    });
    chestShield(c);
  },

  // "Fortitude": the bust in the ball of "Jedi defence" II, a white star of four points on its chest. In the game the
  // star's points stand 4.5 from (15.5, 23.5), its sides run in to 1.5 beside and above the middle (the corners
  // between the points 2.12 from it), a black line of one pixel round it.
  i_fortitude(c) {
    inBall(c, CHEST, {}, [15.5, 15.5], 14.5, () => disc(c, [15.5, 15.5], 14.5 - BORDER, { ring: 0.9, stops: BALL }));
    const star = star4([15.5, 23.5], 4.5, 2.12);
    F.borders(c, [star], BORDER);
    whites(c, [star], WHITE, { depth: 0.5 });
  },

  // The scoundrel's luck: the blue bust before the disc of light with its black rim, and white plus signs beside the
  // head. The bust stands two lower than elsewhere and ends at y 28 (in the game its head's top is at 3, its body's
  // bottom at 28, with the disc's rim below it). The plus signs are five by five with bars one wide, a black line of
  // one pixel round each: I two, about (6.5, 8.5) and (24.5, 8.5); II two more, about (3.5, 13.5) and (27.5, 13.5).
  i_scdac01(c) { scoundrel(c, [[6.5, 8.5], [24.5, 8.5]], false); },
  i_scdac02(c) { scoundrel(c, [[6.5, 8.5], [24.5, 8.5], [3.5, 13.5], [27.5, 13.5]], false); },
  // III: the disc larger, with a white ring inside its border. In the game it fills the frame from edge to edge (16
  // high, 15.5 wide in radius): here a whole circle of 15.4 about (15.5, 16), so that its border is complete.
  i_scdac03(c) { scoundrel(c, [[6.5, 8.5], [24.5, 8.5], [3.5, 13.5], [27.5, 13.5]], true); },

  // "Force sensitive": the blue bust with the ring on its chest, here half light and half dark, and two arcs of light
  // at each side of the head. In the game the ring is the "empathy" ring; its inside is white on the left of the
  // middle and black on the right, the black half kept from the ring by a white line (a pixel wide). The arcs are white
  // lines a pixel wide without a border, about the middle of the head: radius 10 from 27 degrees above level to 27
  // below, and radius 14 from 23 above to 23 below.
  i_forcesn(c) {
    H.bust(c, CHEST, { hue: 'blue' });
    orb(c);
    const { at, ri } = ORB, dark = S.intersect(S.circle(at[0], at[1], ri - 0.8), S.halfPlane(at[0], at[1], -1, 0));
    c.fill(S.intersect(S.circle(at[0], at[1], ri), S.halfPlane(at[0], at[1], -1, 0)), P.byDepth(0.25, [[0, '#9db1ff'], [1, '#ffffff']]));
    c.fill(dark, P.flat(INK));
    const mid = [15.5, 8.2], white = P.byDepth(0.3, [[0, '#c4c8d4'], [1, '#ffffff']]);
    for (const [r, a] of [[10, 27], [14, 23]]) { c.fill(S.arcRound(mid[0], mid[1], r, 1.0, 180 - a, 180 + a), white); c.fill(S.arcRound(mid[0], mid[1], r, 1.0, -a, a), white); }
  },

  // "Force camouflage": the blue bust, its right half gone dark, a white line down its middle. In the game the line is
  // the pixel column on the bust's axis (16.5) from the top of the head to the bottom, and the right half keeps its
  // modelling in deep blues (its lightest about 5a7cff where the left half is white).
  i_frccamo(c) {
    const pl = { at: [16.5, CHEST_TOP], s: 1 }, sh = H.shape(pl), w = 0.8;
    H.bust(c, pl, { hue: 'blue', tone: (key, x) => key * (1 - 0.64 * smooth(16.5 - 0.1, 16.5 + 0.1, x)) });
    c.fill(S.intersect(S.box(16.5, 16, w / 2, 16), S.grow(sh, -0.12)), P.flat('#ffffff'));
  },

  // "Aura": the blue bust cut off below the shoulders, with a glow round its head. The bust stands as in the redraw
  // (top of the head at y 7.9, scale 1.2). The glow is the game's (tools/head_front_auraglow.py): it follows the
  // head's outline, strongest against it (opacity 0.62 above the head, 0.37 and 0.53 beside it: here 0.74 above and
  // 0.6 beside, the same left and right), falls off evenly to nothing 8.3 away, pales as it strengthens, and dies
  // away between the jaw and the shoulders. The border is whole and of one width; round the head it is lit by the
  // glow (navy instead of black), as in the game and in the redraw.
  ip_aura(c) {
    const pl = { at: [16.0, 7.9], s: 1.2 }, form = H.SHOULDERS, sh = H.shape(pl, form);
    const lit = (y) => smooth(26.4, 22.4, y);                          // 1 round the head, 0 from the shoulders down
    H.glow(c, H.head(pl), {
      reach: 8.3, strength: 0.74, power: 1,
      weigh: (x, y) => (0.82 + 0.18 * (1 - smooth(7, 13, y))) * (1 - smooth(22.0, 26.0, y)),
      colours: [[0, '#000f46'], [0.09, '#00145d'], [0.17, '#0027bd'], [0.25, '#0f3be6'], [0.33, '#234ef9'], [0.41, '#3962ff'], [0.49, '#577aff'], [0.57, '#6f8cff'], [0.68, '#8aa2ff']],
    });
    const ink = P.hex(INK), navy = P.hex('#001b86');
    c.fill(sh, (px) => { const k = lit(px.y); px.r = ink[0] + (navy[0] - ink[0]) * k; px.g = ink[1] + (navy[1] - ink[1]) * k; px.b = ink[2] + (navy[2] - ink[2]) * k; px.a = 1; }, BORDER);
    H.bust(c, pl, { hue: 'blue', ...form, border: 0, lit: (y) => 0.5 * lit(y) });
  },

  // "Jedi armour" I: the bust as a dark figure with a line of light along its edge and two lit eyes, on a blue disc.
  // The disc is the game's: round (16, 16) out to 15.0, a black rim, blue inside, paler towards its rim (4a6fff) and
  // deep behind the figure (002aca).
  // The figure is the bust at scale 1.38 with its head's top at y 4.2 (the redraw's; the game's is 5 per cent smaller),
  // short and narrow below the neck: 9.0 to each side and down to y 28, where its corners lie on the disc's rim,
  // as in the game. The eyes are the game's: white slits 3 wide and 1 high, 2.5 to each side of the axis at y 13.5,
  // each in a small glow (the redraw has round dots).
  i_jediac01(c) {
    disc(c, [16, 16], 15.0, { rim: RIM, stops: JEDI_DISC });
    darkFigure(c);
  },

  // II: the same disc with a white rim instead of the black one (in the game two pixels of white, its outermost edge
  // blue).
  i_jediac02(c) {
    disc(c, [16, 16], 15.0, { fringe: 0.2, ring: RIM - 0.2, stops: JEDI_DISC });
    darkFigure(c);
  },
  // III: as II, and a wedge of white light from each eye out to the rim: in the game its point stands a pixel outside
  // the eye (11, 13.5), its edges rise and fall about 35 degrees, and it lies over the figure's side. The white of the
  // wedges and of the rim is one piece.
  i_jediac03(c) {
    disc(c, [16, 16], 15.0, { fringe: 0.2, ring: RIM - 0.2, stops: JEDI_DISC });
    darkFigure(c);
    const round = S.circle(16, 16, 14.8), white = P.byDepth(0.5, [[0, '#c3cfff'], [1, '#ffffff']]);
    const beam = (x, dir) => S.polygon([[x, 13.5], [x - dir * 12, 13.5 - 12 * 0.7], [x - dir * 12, 13.5 + 12 * 0.7]]);
    c.fill(S.intersect(S.union(beam(11.3, 1), beam(20.7, -1), S.subtract(round, S.circle(16, 16, 13.6))), round), white);
  },

  // "Awareness" (the skill's focus): the blue bust cut off below the shoulders, with seven rays of light round its
  // head. No black border: the game's has none either. The bust stands as in the redraw (scale 1.09, top of the head
  // at y 9.72, the neck 0.9 longer than the standard one, the bottom on the frame's edge). The rays are the game's:
  // one straight up from above the head (x 16, y 8.4 to 1.8), and at each side one up and out (11.7, 9.2 to 7.9, 2.8),
  // one out and a little up (9.2, 11.4 to 2.8, 8.7) and one level (8.4 to 2.8 at y 14.5), each widest beside the head.
  i_focaware(c) {
    for (const [near, far] of [[[16, 8.4], [16, 1.8]], [[11.7, 9.2], [7.9, 2.8]], [[9.2, 11.4], [2.8, 8.7]], [[8.4, 14.5], [2.8, 14.5]]]) {
      ray(c, near, far, 1.1);
      if (near[0] !== 16) ray(c, [32 - near[0], near[1]], [32 - far[0], far[1]], 1.1);
    }
    H.bust(c, { at: [16.0, 9.72], s: 1.09 }, { hue: 'blue', neck: 0.9, vb: 19.5, rc: 0.4, cut: true, border: 0, lit: () => 1 });
  },

  // "Immunity": the blue bust cut off below the shoulders under a white dome, with a sign on its face: fear (!) and
  // confusion (?). In the game the dome is a band from one side of the head over its top to the other, 5 thick above
  // and thinning to its ends at y 23, white with blue edges and a black line round it; the frame's sides squeeze it
  // (its outer edge is flat from y 9 to 21). Here it is whole: the part of a circle of 14.4 about (16, 15.6) that lies
  // outside a circle of 12.69 about (16, 19.09): 5.2 thick at the top, coming to points at (4.3, 24) and (27.7, 24).
  i_immun01(c) {
    immune(c);
    // the "!" of the game: a bar 2 wide from y 12 to 19 and a dot under it (y 21 to 22.5), black, on the bust's axis
    c.fill(S.union(S.box(16, 15.5, 1.0, 3.5), S.circle(16, 21.7, 1.05)), P.flat(INK));
  },
  i_immun02(c) {
    immune(c);
    // the "?" of the game: navy, from y 13 to 20 with its dot at 21.5: a hook 6 wide over a stem on the axis, 1.5 thick
    const q = S.union(S.arcRound(16, 15.2, 2.15, 1.5, 180, 410), S.capsule(17.38, 16.85, 16, 18.1, 1.5), S.capsule(16, 18.1, 16, 19.3, 1.5), S.circle(16, 21.7, 0.95));
    c.fill(q, F.deepening(c.k, { rim: '#00104a', edge: '#0a2fc4', body: '#1541ec' }, { depth: 0.5, rim: 0.12 }));
  },

  // The "stance" icons: the bust in a shield (see stance()). III is 0.96 the size of the others: its outer frame runs
  // off the game's picture at the bottom; drawn whole it needs that much room.
  i_gstance01(c) { stance(c, P.byDepth(1.2, [[0, '#1c44ea'], [1, '#2854fe']])); },
  i_gstance02(c) { stance(c, P.byDepth(1.2, [[0, '#b7c5ff'], [1, '#cbd6ff']])); },
  i_gstance03(c) { stance(c, P.byDepth(1.2, [[0, '#b7c5ff'], [1, '#cbd6ff']]), { k: 0.96, outer: true }); },

  // "Sleep": the red bust, small, with three letters Z rising to the upper right. The bust stands as in the redraw
  // (scale 1.05, top of the head at y 10.85), on the game's axis (16); below the neck it is the narrow one: 7.55 to
  // each side. The letters are the game's: 4, 5 and 6 wide and high, with their upper left corners at (8, 7),
  // (12, 4) and (17, 1), their bars one wide (the redraw's are fatter and lean). White with a black border; the
  // borders of the letters and of the bust run together.
  ip_sleep(c) {
    const pl = { at: [16.0, 10.85], s: 1.05 }, form = { neck: 0.6, w: 7.55, r8: 2.0, vb: 18.2, rc: 0.5, cut: true };
    const letters = [zed(8, 7, 4, 4, 1), zed(12, 4, 5, 5, 1), zed(17, 1, 6, 6, 1)];
    F.borders(c, letters, BORDER);
    H.bust(c, pl, { hue: 'red', ...form, part: 'border' });
    H.bust(c, pl, { hue: 'red', ...form, part: 'body' });
    whites(c, letters, LETTER);
  },
};

// The blue of the "Jedi armour" discs by radius (the game's: 002aca behind the figure, 0733de at 9.5, 2652fd at 10.5,
// 4067ff at 11.5, 4a6fff at the rim).
const JEDI_DISC = [[0, '#002aca'], [8.5, '#002aca'], [9.5, '#0733de'], [10.5, '#2652fd'], [11.7, '#3f66ff'], [13.6, '#4a6fff']];

// The bust under the dome of the "immunity" icons (see i_immun01): all borders first, then the dome, then the bust.
function immune(c) {
  const pl = { at: [16.0, 8.2], s: 1.17 }, form = H.SHOULDERS;
  const out = [16, 15.6, 14.4], inn = [16, 19.09, 12.69], tip = [16 - 11.7, 24.0];
  const deg = (q, p) => (Math.atan2(p[1] - q[1], p[0] - q[0]) * 180) / Math.PI;
  const a0 = deg(out, tip), b0 = deg(inn, tip);                       // the left point seen from each circle's centre
  // over the top from the left point to the right one along the outer circle, and back along the inner one
  const dome = [...G.arcPts(out[0], out[1], out[2], a0, 540 - a0), ...G.arcPts(inn[0], inn[1], inn[2], 540 - b0, b0).slice(1, -1)];
  F.borders(c, [dome], BORDER);
  H.bust(c, pl, { hue: 'blue', ...form, part: 'border' });
  F.solid(c, dome, { palette: { rim: '#1f4bf6', edge: '#8fa6ff', body: '#ffffff' }, border: 0, depth: 1.1, rim: 0.13 });
  H.bust(c, pl, { hue: 'blue', ...form, part: 'body' });
}

// The dark figure of the "Jedi armour" icons with its eyes (see i_jediac01).
function darkFigure(c) {
  H.dark(c, { at: [16.0, 4.2], s: 1.38 }, { w: 6.52, r8: 0.8, vb: 17.25, rc: 0.4 });
  for (const x of [13.4, 18.6]) {
    const eye = S.capsule(x - 1.0, 13.5, x + 1.0, 13.5, 1.0);
    c.glow(eye, '#2f58fa', 0.55, 0.95);
    c.fill(eye, P.byDepth(0.3, [[0, '#b9c8ff'], [1, '#ffffff']]));
  }
}

// The scoundrel's icons (see i_scdac01).
function scoundrel(c, at, large) {
  const pl = { at: [15.5, 2.8], s: 1 }, form = { vb: 25.2 }, signs = at.map((p) => plus(p, 2.5, 1.0));
  const mid = large ? [15.5, 16.0] : [15.5, 15.5], r = large ? 15.4 : 14.5;
  // the disc lies behind everything; on it the borders of the signs and of the bust together, then their bodies
  if (large) disc(c, mid, r, { rim: BORDER, ring: RIM, stops: grown(GLOW_DISC, (r - BORDER - RIM) / 12.5) });
  else disc(c, mid, r, { rim: RIM, stops: grown(GLOW_DISC, (r - RIM) / 12.5) });
  F.borders(c, signs, BORDER);
  H.bust(c, pl, { hue: 'blue', ...form, part: 'border' });
  H.bust(c, pl, { hue: 'blue', ...form, part: 'body' });
  whites(c, signs);
}
