'use strict';
// Constructed drawings of the icons with a head in profile. The head is one construction (parts/symbol_head_profile.js:
// an outline of straight lines and circular arcs, a white line along its edge by formula, its modelling from a small
// smooth table); every icon places it and adds what the game's icon shows beside it.
// The HEAD follows ChatGPT's redraw (outline and modelling). Everything ADDED to it follows the game's own icon: its
// shapes are read off the game's pixels (tools/head_profile_vdump.py prints them as numbers), because the redraw
// fattens and reshapes simple things. Where a drawing departs from the game, its comment says how and why.
// Sizes: the game draws the head 0.95 of the size it has in the parts file wherever it fills the icon, the redraws
// 0.98 to 1.0; here 0.98 (and the game's smaller heads as much larger than the game's). Black borders are 0.8, the
// width the redraws give the game's one-pixel line; all borders of an icon are laid before any of its bodies.
// Units: the vanilla icon's pixels (frame 32 x 32, y down).
const { S, P, C } = require('../kit');
const G = require('../lib/geom');
const F = require('../parts/flat');
const H = require('../parts/symbol_head_profile');

const RAD = Math.PI / 180;
const ink = P.flat(H.INK);
// the head where it fills the icon: one size, and the skull's centre at one height (the game's: 13.1 to 13.15)
const FULL = 0.98, LEVEL = 13.15;

// ---- the exclamation mark ("cautious") -------------------------------------------------------------------------------
// Black, on the skull, in the head's own frame. The game's: a stem three pixels wide and six high that draws in over
// two more rows to one pixel, a gap of two rows, a dot one pixel wide (three with its dark blue neighbours) and two
// high; its middle line 2.15 behind the skull's centre. (The redraw's stem draws in from the top down and its dot
// is a square of two.)
const BANG = { u: -2.15, top: -6.43, taper: -0.5, tip: 1.94, half: 1.57, tipHalf: 0.52, dot: [5.07, 0.9, 1.05, 0.45] };
const bang = (c, pl) => {
  const T = H.toIcon(pl), q = BANG, s = pl.s || 1;
  c.fill(S.polygon([[q.u - q.half, q.top], [q.u + q.half, q.top], [q.u + q.half, q.taper], [q.u + q.tipHalf, q.tip], [q.u - q.tipHalf, q.tip], [q.u - q.half, q.taper]].map(T)), ink);
  const [x, y] = T([q.u, q.dot[0]]);
  c.fill(S.box(x, y, q.dot[1] * s, q.dot[2] * s, q.dot[3] * s), ink);
};

// ---- what the watchful eye sees ("cautious") -------------------------------------------------------------------------
// In the game a thin arc stands before the face, and in two of the four icons a wedge runs from the eye to the arc:
// the eye's field of view. Read off the game's pixels: the arc two pixels of white all along, its middle line
// through (26.3, 1.5), (29, 12) and (26.5, 22.5): a circle of radius 22.5 about (6.5, 12); the wedge's point at
// (23.6, 12), right at the head's border before the eye, its two sides meeting the arc's inside at y 8.5 and 15.5
// (39 degrees either side of level). Arc and wedge are one white piece.
// Changed from the game: there the arc's upper end touches the top of the frame; here the arc runs 26.4 degrees to
// either side instead of 28, so that its border is whole.
const VIEW = { c: [6.5, 12], r: 22.5, w: 2.0, reach: 26.4, apex: [23.6, 12], half: 39 };
// (the arc as the mind icons' arcs: slimmer and deeper blue towards its rounded ends: the user)
const viewArc = () => lightArc(VIEW.c[0], VIEW.c[1], VIEW.r, VIEW.w, -VIEW.reach, VIEW.reach);
const viewCone = () => {
  const [ax, ay] = VIEW.apex, far = 14, dx = far * Math.cos(VIEW.half * RAD), dy = far * Math.sin(VIEW.half * RAD);
  const arc = viewArc();
  return { shader: arc.shader, shape: S.union(arc.shape, S.intersect(S.polygon([[ax, ay], [ax + dx, ay - dy], [ax + dx, ay + dy]]), S.circle(VIEW.c[0], VIEW.c[1], VIEW.r))) };
};
// the head with the mark, and what stands before it (null: nothing)
const cautious = (c, at, before) => {
  const pl = { at, s: FULL }, head = H.shape(pl);
  H.borders(c, before ? [head, before.shape] : [head], { close: 0.4 });
  c.fill(head, H.shader(pl));
  bang(c, pl);
  if (before) c.fill(before.shape, before.shader);
};

// ---- the rays ("sense") ----------------------------------------------------------------------------------------------
// Three thin white bars before the brow, each in a black border. The game's (force sense): the middle one level,
// six pixels long and one thick; the outer ones begin 3 above and below it and spread by 12.7 degrees; all three one
// length; a clear pixel between their black and the head's. In the head's own frame: the middle one at v = -4.74,
// from u = 12.55 (the game's begin at 11.63; a unit further out here, so that the clear between the rays' black and
// the head's is a whole unit all the way down to the brow, and not a sliver), 5.9 long so that the middle one's
// border ends inside the frame. (The redraws make them half as thick again and fan them wider.)
const RAY = { v: -4.74, u0: 12.55, len: 5.9, off: 3.17, fan: 12.66, w: 1.0 };
// A set of three rays on the face side of a head: { x0: the upright line they begin on, dir: +1 (they run right)
// or -1, ym: the middle ray's level, off: how far above and below it the outer ones begin, len }.
// from: the x they begin at (default: the game's place); len: their length (default: the game's, at the head's scale)
const rays = (pl, o = {}) => {
  const s = pl.s || 1, x0 = o.from === undefined ? pl.at[0] + RAY.u0 * s : o.from;
  return { x0, dir: 1, ym: pl.at[1] + RAY.v * s, off: RAY.off * s + Math.tan(RAY.fan * RAD) * (x0 - pl.at[0] - RAY.u0 * s), len: o.len === undefined ? RAY.len * s : o.len };
};
// the same set mirrored about the upright line x = axis
const flipped = (set, axis) => ({ ...set, x0: 2 * axis - set.x0, dir: -set.dir });
// One ray of a set (which: 0 the middle one, -1 the upper, +1 the lower) as a shape: a bar of half-width h from the
// set's upright line (moved back by `back`) to its end (moved on by `on`); its near end is cut upright, on that line,
// its far end square across the bar.
const rayShape = (set, which, h, back = 0, on = 0) => {
  const a = which * RAY.fan * RAD, d = [set.dir * Math.cos(a), Math.sin(a)], E = [set.x0, set.ym + which * set.off];
  const bar = S.polygon(G.strokePts([[E[0] - 3 * d[0], E[1] - 3 * d[1]], [E[0] + (set.len + on) * d[0], E[1] + (set.len + on) * d[1]]], h));
  return S.intersect(bar, S.halfPlane(set.x0 - set.dir * back, 0, -set.dir, 0));
};
// Their black: each ray's border (square at the far end), and at the near end one upright black line that closes all
// three, as in the game: the borders' near ends lie on one upright line and the black between them is whole as far
// as the white begins. sets: the sets of rays; beside: other bodies whose borders are laid with theirs (the head,
// where it has a border); where a ray's border comes within 0.6 of such a body's the two run together.
const rayBorders = (c, sets, { w = RAY.w, border = H.BORDER, beside = [] } = {}) => {
  const all = [], h = w / 2 + border, t = Math.tan(RAY.fan * RAD), hc = h / Math.cos(RAY.fan * RAD);
  for (const set of sets) {
    for (const which of [0, -1, 1]) { c.fill(rayShape(set, which, h, border, border), ink); all.push(rayShape(set, which, w / 2)); }
    const xs = set.x0 - set.dir * border, top = set.ym - set.off - hc, bottom = set.ym + set.off + hc;
    c.fill(S.polygon([[xs, top + t * border], [set.x0, top], [set.x0, bottom], [xs, bottom - t * border]]), ink);
  }
  if (beside.length) H.borders(c, [...all, ...beside], { border, close: 0.3 });
};
const rayBodies = (c, sets, w = RAY.w) => { for (const set of sets) for (const which of [0, -1, 1]) c.fill(rayShape(set, which, w / 2), H.bodyShader({ tone: 1, s: 0.5 * w })); };
// how near two borders must come to run together (the clear gap between them: twice this)
const CLOSE = 0.75;

// ---- the round badge ("focus") ---------------------------------------------------------------------------------------
// The game's: a black ring from radius 13.25 to 15.4 about the icon's middle, and inside it a disc of one blue
// (77, 114, 255) that deepens over its last half unit towards the ring (40, 84, 255).
const BADGE = { out: 15.4, in: 13.4, blue: '#4d72ff', deep: '#2450f6' };
const badge = (c, shade = null) => {
  c.fill(S.circle(16, 16, BADGE.out), ink);
  const base = P.byDepth(0.7, [[0, BADGE.deep], [1, BADGE.blue]]);
  c.fill(S.circle(16, 16, BADGE.in), shade ? (px) => { base(px); shade(px); } : base);
};

// ---- the yellow rings (stealth, of the larger icons) -----------------------------------------------------------------
// The game's (64 pixel icons, so half units): one ring of pure yellow, 1.07 thick, its middle at radius 11.85 about
// (16, 15.75); in the third icon four arcs inside it, 0.82 thick at radius 10.55, a paler yellow, each 75 degrees
// long and centred on a diagonal, a third of a unit clear of the ring. No border, no glow.
// (The redraws make the ring 1.3 thick.)
const RING = { c: [16, 15.75], r: 11.85, w: 1.05, inner: 10.55, innerW: 0.8, span: 75 };
const YELLOW = { rim: '#8f8400', edge: '#f4e800', body: '#fff400' }, YELLOW_PALE = { rim: '#8a8010', edge: '#d8d01c', body: '#e6de20' };
const ring = (c) => c.fill(S.ring(RING.c[0], RING.c[1], RING.r, RING.w), F.deepening(c.k, YELLOW, { depth: 0.3, rim: 0.09 }));
const ringArcs = (c) => {
  for (let i = 0; i < 4; i++) {
    const mid = 45 + 90 * i;
    c.fill(S.arc(RING.c[0], RING.c[1], RING.inner, RING.innerW, mid - RING.span / 2, mid + RING.span / 2), F.deepening(c.k, YELLOW_PALE, { depth: 0.25, rim: 0.08 }));
  }
};
// The small heads of those icons: the head with its lips shut, 0.49 of the size in the parts file (the game's), its
// border and its edge as much smaller (the game draws its one-pixel line on a 64 pixel icon here: half a unit).
// One head: the skull's centre on the ring's upright axis (the game's), the head centred between top and bottom.
// Two: the pair of "stealth", 3.6 apart (the game's), the smallest circle round the pair centred on the ring.
const SMALL = { s: 0.49, border: 0.4, one: { at: [16.0, 13.8] }, pair: [{ at: [15.04, 13.6] }, { at: [18.64, 13.6] }], pairS: 0.48 };
// (The game's "one" head is two as well, as the user saw: a paler head with a white line round it, and behind it the
// same head 1.5 further right, deeper blue, of which the face shows. Drawn as the pair is, the two 1.5 apart.)
const smallHead = (c) => {
  const [x, y] = SMALL.one.at, back = { at: [x + 0.75, y], s: SMALL.s, shut: true }, front = { at: [x - 0.75, y], s: SMALL.s, shut: true };
  // (the outline of the whole is the RIGHT, deeper head's alone; the paler head shows only inside it: the user)
  // The white line runs round the OUTER head (the right, deeper one), whole; the second face inside it is only a paler
  // tone with no line of its own, kept clear of that white line (the user).
  H.draw(c, back, { border: SMALL.border });
  // the second face: the head itself in its own colours (not paled), 2.75 to the left of the outer one, shown only
  // inside the outer head's white line, which stays whole (the user)
  const inner = { ...front, at: [back.at[0] - 2.75, back.at[1]] };   // (the game's: its darker band before the inner face is 5 to 6 of its pixels wide, 2.5 to 3 units)
  // coloured as the two heads of "stealth" are (the user): the outer head deep blue, the inner one lighter with its
  // bright edge; our outline and our places kept
  // The inner head as a pale veil over the deeper one (the user, after seeing that the game's is a flat pale lavender,
  // 166,184,255, with hardly any shading of its own): the pair as before, then that lavender laid over the inner head
  // at 0.62, so that a little of the face's shading and of the head behind still shows through.
  c.layer((t) => { H.fadedPair(t, back, inner, { lower: 0.3, lift: 0.04 }); t.fill(H.shape(inner), (px) => { px.r = 166 / 255; px.g = 184 / 255; px.b = 1; px.a = 0.62; }); }, { mask: S.grow(H.shape(back), -0.34) });
};
const smallPair = (c) => {
  const [back, front] = SMALL.pair.map((p) => ({ ...p, s: SMALL.pairS, shut: true }));
  H.borders(c, [H.shape(back), H.shape(front)], { border: SMALL.border });
  H.fadedPair(c, back, front);
};

// An arc of light as the game draws it (the user, 2026-10-08): thickest in its middle and drawn out thin to a point at
// either end, and coloured the same way: white in the middle, a deeper blue towards the ends. cx, cy, r: its circle;
// w: its thickness in the middle; a0, a1: its ends (degrees). Returns its shape and its shader.
const lightArc = (cx, cy, r, w, a0, a1) => {
  const n = 90, outer = [], inner = [], end = 0.38, half = (t) => (w / 2) * (end + (1 - end) * Math.pow(Math.sin(Math.PI * t), 0.9));   // slimmer at the ends (0.38 of the middle), not pointed
  for (let i = 0; i <= n; i++) { const t = i / n, a = (a0 + (a1 - a0) * t) * RAD, h = half(t); outer.push([cx + (r + h) * Math.cos(a), cy + (r + h) * Math.sin(a)]); inner.push([cx + (r - h) * Math.cos(a), cy + (r - h) * Math.sin(a)]); }
  // each end closed by a half round of the end's own thickness
  const cap = (a, from) => { const m = [cx + r * Math.cos(a * RAD), cy + r * Math.sin(a * RAD)], rr = (w / 2) * end, out = []; for (let i = 1; i < 12; i++) { const b = from + (Math.PI * i) / 12; out.push([m[0] + rr * Math.cos(b), m[1] + rr * Math.sin(b)]); } return out; };
  const shape = S.polygon([...outer, ...cap(a1, a1 * RAD), ...inner.slice().reverse(), ...cap(a0, a0 * RAD + Math.PI)]), mid = ((a0 + a1) / 2) * RAD, span = ((a1 - a0) / 2) * RAD;
  const ramp = P.ramp([[0, '#ffffff'], [0.45, '#f2f5ff'], [0.7, '#a9bfff'], [0.88, '#4a74f6'], [1, '#1c3fe0']]), edge = P.hex('#2f5cf4');
  const shader = (px) => {
    let a = Math.atan2(px.y - cy, px.x - cx) - mid; a -= 2 * Math.PI * Math.round(a / (2 * Math.PI));
    ramp(Math.min(Math.abs(a) / span, 1), px);
    const e = 1 - S.clamp(-px.d / 0.22, 0, 1);                       // a thin blue edge all along it
    px.r += (edge[0] - px.r) * e * 0.8; px.g += (edge[1] - px.g) * e * 0.8; px.b += (edge[2] - px.b) * e * 0.8; px.a = 1;
  };
  return { shape, shader };
};

module.exports = {
  // the head alone, looking left. The redraw's stands at (16.48, 13.05) at 0.994; here at the size and height the
  // head has in every icon it fills.
  i_dialog(c) {
    H.draw(c, { at: [16.48, LEVEL], s: FULL, flip: true });
  },

  // the head with the brain set into its skull, and an arc before its face.
  // The head where the redraw has it (13.32, 13.18; 0.977 there).
  // The arc is the game's (the redraw swells it into a crescent 2.2 thick in the middle with thin points): a band of
  // one thickness along a circle. Read off the game's pixels: two pixels of body all the way (a white one and a
  // blue one), its middle line through (25, 3.5), (28, 16.5) and (25, 28), which is a circle of radius 27.1 about
  // (0.9, 16), 28.5 degrees to either side of the level; two pixels of black between it and the tip of the nose.
  // Here 2.1 thick, with round ends, and set the same two units before the nose (which stands at 25.05).
  // Before the tip of the nose the head's border and the arc's are one black, as in the game's icon.
  ip_mind(c) {
    const pl = { at: [13.32, LEVEL], s: FULL };
    const head = H.shape(pl), arc = lightArc(0.95, 16, 27.15, 2.0, -28.5, 28.5);
    H.borders(c, [head, arc.shape], { close: CLOSE });
    H.drawWithBrain(c, pl);
    c.fill(arc.shape, arc.shader);
  },

  // The head with two arcs, one behind it and one before it: mirror images about the icon's upright middle line.
  // The game's: thin arcs, one pixel of pale grey-white, on a circle of radius 14.6 about the icon's middle, 39.6
  // degrees to either side of level; clear between an arc and the head at mid height, black where its ends come
  // close to the head, and black between the nose and the arc before it. (The redraw makes them crescents three
  // thick.) The game's head here is 0.915; here 0.94, and the arcs 1.2 thick on radius 14.3, so that their
  // borders stay inside the frame (the game's lie on its outermost pixels).
  ip_knightmind(c) {
    const pl = { at: [16.4, 13.6], s: 0.94 }, head = H.shape(pl);
    const before = lightArc(16, 16, 14.2, 1.35, -39.6, 39.6), behind = lightArc(16, 16, 14.2, 1.35, 140.4, 219.6);
    H.borders(c, [head, before.shape, behind.shape], { close: CLOSE });
    c.fill(head, H.shader(pl));
    for (const arc of [before, behind]) c.fill(arc.shape, arc.shader);
  },

  // A smaller head with two arcs on either side, all four about the skull's centre; the two sides mirror images.
  // The game's: arcs two pixels thick (white between blue), on radii 10 and 15.2 about the middle of the skull, a
  // clear pixel between the borders of an outer and an inner one; the outer ones 39 degrees to either side of
  // level, the inner ones from 56 above to 40 below (below, the bust is in their way); the inner arcs' black runs
  // into the head's. The game's head is a narrower drawing of its own, 14 wide and 22 high; the one head is 0.65
  // here (15.3 wide), as large as fits between the inner arcs.
  // Changed from the game: there the outer arcs lie against the frame's sides, which cut their borders off. Here
  // they are on radius 14.1 and the inner ones on 9.8, all 1.7 thick, with their borders whole and a clear unit
  // between them; the inner arcs run from 50 above to 38 below.
  ip_mastermind(c) {
    const pl = { at: [16, 17.4], s: 0.65 }, head = H.shape(pl), [x, y] = pl.at, w = 1.7;
    const arcs = [lightArc(x, y, 14.0, w - 0.1, -39, 39), lightArc(x, y, 14.0, w - 0.1, 141, 219), lightArc(x, y, 9.8, w - 0.1, -50, 38), lightArc(x, y, 9.8, w - 0.1, 142, 230)];
    H.borders(c, [head, ...arcs.map((a) => a.shape)], { close: 0.45 });
    c.fill(head, H.shader(pl));
    for (const arc of arcs) c.fill(arc.shape, arc.shader);
  },

  // the head, and three rays before its brow. The game's head stands at (12.56, 13.15); the middle ray ends one
  // pixel short of the frame, as here.
  ip_sense(c) {
    const pl = { at: [12.6, LEVEL], s: FULL }, set = rays(pl);
    rayBorders(c, [set], { beside: [H.shape(pl)] });
    c.fill(H.shape(pl), H.shader(pl));
    rayBodies(c, [set]);
  },
  // the head with rays on both sides: three before the brow and their mirror images behind the skull, three pixels
  // long each in the game (the head leaves no more room), the two sets mirror images about the icon's upright
  // middle line, the back ones' black running into the head's.
  isa_senses(c) {
    const pl = { at: [17.0, LEVEL], s: FULL }, before = rays(pl, { from: 27.9, len: 3.0 }), behind = flipped(before, 16);
    rayBorders(c, [before, behind], { beside: [H.shape(pl)] });
    c.fill(H.shape(pl), H.shader(pl));
    rayBodies(c, [before, behind]);
  },

  // The head with the exclamation mark on its skull; nothing before it, the arc before it, the arc with the wedge
  // from the eye (twice: the game's first and fourth icons are the same picture).
  // The game sets the head three pixels further left where something stands before it: (12.6, 13.1) against (15.6, 13.1).
  i_cautious01(c) { cautious(c, [15.6, LEVEL], null); },
  i_cautious02(c) { cautious(c, [12.6, LEVEL], viewArc()); },
  i_cautious03(c) { cautious(c, [12.6, LEVEL], viewCone()); },
  i_cautious(c) { cautious(c, [12.6, LEVEL], viewCone()); },

  // the red head, and a black arrow with a white line round it pointing into the skull from behind.
  // The head: the redraw's stands at (19.52, 13.18), scale 1.0, and the frame cuts the border at the tip of its nose
  // (so does the redraw's own); here it is 0.98 and 0.3 further left, so that the border is whole all round.
  // The arrow is the game's: there its black is five pixels high and eleven long, its head nine high and five long
  // (sides at 45 degrees), a white line of one pixel all round and a black one outside that, where it does not lie
  // on the head; its point reaches 0.46 of the way from the back of the skull to the tip of the nose, its middle
  // line lies a third of the way down the head. (The redraw's arrowhead is ten high, its white 1.07.) Drawn 1.07
  // times the game's size, as the head is: black 5.4 high, head 9.6 high and 4.8 long, white 1.0.
  // The white line's corners are sharp; the two barbs, where a sharp corner would stand 2.6 out, are cut square.
  ip_affectmind(c) {
    const pl = { at: [19.2, LEVEL], s: FULL }, head = H.shape(pl);
    const y = 11.5, x0 = 3.0, xb = 13.8, tip = 18.6, hs = 2.7, hh = 4.8;
    const arrow = [[x0, y - hs], [xb, y - hs], [xb, y - hh], [tip, y], [xb, y + hh], [xb, y + hs], [x0, y + hs]];
    const white = G.offsetPts(arrow, 1.0, 1.5), black = G.offsetPts(white, H.BORDER, 1.5);
    c.fill(head, ink, H.BORDER);
    c.fill(S.polygon(black), ink);
    c.fill(head, H.shader(pl, { palette: H.RED }));
    c.fill(S.polygon(white), P.flat('#ffffff'));
    c.fill(S.polygon(arrow), ink);
  },

  // two heads, one behind the other, fading (parts: fadedPair): dark where one stands alone, lighter where the two
  // lie over one another, the front head's outline bright, the back head's showing through it faintly (the game:
  // a line of lighter pixels down the front head's skull where the back head's face is).
  // The redraw draws them without the black line the game has round the pair, and larger by as much; here they
  // keep the line, and stand so that its outer edge lies on the redraw's outline: scale 0.956 both (the redraw's
  // two differ by 1.6 per cent), 6.58 apart. Moved 0.4 to the left of that, for the border to be whole at the tip
  // of the front head's nose, where the frame cuts the redraw.
  isk_stealth(c) {
    const back = { at: [13.02, 13.25], s: 0.956, shut: true }, front = { at: [19.6, 13.25], s: 0.956, shut: true };
    H.borders(c, [H.shape(back), H.shape(front)]);
    H.fadedPair(c, back, front);
  },

  // The badge with the head and its three rays. In the game the head stands on the blue without a border, the
  // disc is dark before the face (black against the profile, dark blue round the rays, back to the disc's blue
  // towards the ring), and the three rays are short pale bars in that dark. The head stands at (12.64, 13.36) at
  // 0.76 there, and the corner of its bust reaches out over the ring and a pixel beyond.
  // Here: 0.75 at (13.2, 13.0), so that the bust's corner lies on the ring but does not leave the badge; the rays as
  // in "sense", at the head's scale (0.9 thick), each in a black border of its own.
  // The dark is a shadow that falls off smoothly, two soft spots run together: a tall one along the face (black
  // against the profile, gone four units before it) and one round the rays.
  i_focsense(c) {
    const pl = { at: [13.2, 13.0], s: 0.75 }, head = H.shape(pl), set = rays(pl), w = 0.9, border = 0.6, dark = P.hex(H.INK);
    const spot = (x, y, cx, cy, rx, ry) => Math.exp(-(((x - cx) / rx) ** 2) - ((y - cy) / ry) ** 2);
    badge(c, (px) => {
      // (the game, level with the mouth: black two pixels before the face, then 0.7, 0.5, 0.35, 0.15 of it, a pixel each)
      const k = 1 - (1 - spot(px.x, px.y, 21.0, 15.6, 4.6, 8.2)) * (1 - 0.9 * spot(px.x, px.y, 24.0, 9.5, 3.4, 4.0));
      px.r += (dark[0] - px.r) * k; px.g += (dark[1] - px.g) * k; px.b += (dark[2] - px.b) * k;
    });
    rayBorders(c, [set], { w, border });
    c.fill(head, H.shader(pl));
    rayBodies(c, [set], w);
  },
  // The badge with the two fading heads. In the game they fill the disc and the ring cuts the back of the one and
  // the nose of the other. Changed from the game: the pair is whole inside the ring (0.69, the smallest circle
  // round it centred on the badge and half a unit clear of the ring). No black line round heads that stand on the
  // disc: their own dark edge line meets the blue.
  i_focstlth(c) {
    const back = { at: [14.83, 12.91], s: 0.69, shut: true }, front = { at: [19.58, 12.91], s: 0.69, shut: true };
    badge(c);
    H.fadedPair(c, back, front);
  },

  // the small head; the same in a yellow ring; the small pair in the ring; the pair in the ring with four arcs
  i_mistealth(c) { smallHead(c); },
  i_mistealth1(c) { ring(c); smallHead(c); },
  i_mistealth2(c) { ring(c); smallPair(c); },
  i_mistealth3(c) { ring(c); ringArcs(c); smallPair(c); },

  // sneak attack I to X: the same picture, the bars count the level (parts: sneak)
  i_sneak01(c) { H.sneak(c, 1); },
  i_sneak02(c) { H.sneak(c, 2); },
  i_sneak03(c) { H.sneak(c, 3); },
  i_sneak04(c) { H.sneak(c, 4); },
  i_sneak05(c) { H.sneak(c, 5); },
  i_sneak06(c) { H.sneak(c, 6); },
  i_sneak07(c) { H.sneak(c, 7); },
  i_sneak08(c) { H.sneak(c, 8); },
  i_sneak09(c) { H.sneak(c, 9); },
  i_sneak10(c) { H.sneak(c, 10); },
};
