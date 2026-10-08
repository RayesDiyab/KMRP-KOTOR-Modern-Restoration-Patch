'use strict';
// The head in profile: constructed once, placed and scaled in every icon of the sheet; and the few other things the
// sheet's icons are made of (a body with the same edge as the head's, the brain, the pair of fading heads).
//
// The head's OUTLINE is a chain of straight lines and circular arcs, each starting in the direction the last one ended
// in (so the outline is smooth everywhere except at its corners, which are small arcs themselves). The chain was
// fitted to the mean outline of nine of ChatGPT's redrawn heads laid over one another (tools/head_profile_align.py:
// the redraws agree with one another to 0.17 units on average; tools/head_profile_fit.py: the chain keeps within 0.03
// units of their mean on average, 0.15 at most, which is the bust's lower edge: level here, a degree off in the mean).
//
// Its MODELLING is one number per place, the whiteness t: the redraws' colours lie on one line from azure (t = 0) to
// white (t = 1). Along the edge the redraws all carry the same thing, which is written here as a formula of the exact
// distance to the outline: a dark blue line at the very edge that brightens to a white line half a unit inside.
// Beyond the white line the whiteness is read from a small smooth table (symbol_head_profile_tone.json: the mean of
// the aligned redraws as a cubic B-spline surface on a grid of half units; tools/head_profile_shade.py): the light
// falling off from the edge, the forehead, the cheek, the hollow of the eye, the shadow from the neck across the jaw.
//
// The head's own frame: origin at the centre of the skull's upper arc, x towards the face, y down. At scale 1 it is
// as large as it stands in the redrawn "cautious" icons: from -11.55 (back of the skull) to 12.01 (tip of the nose)
// across, from -11.48 (crown) to 17.84 (the bust's lower edge) down.
const S = require('../lib/sdf');
const P = require('../lib/paint');
const TONE = require('./symbol_head_profile_tone.json');

const { clamp, mix } = S;
const RAD = Math.PI / 180;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

// ---- chains ----------------------------------------------------------------------------------------------------------
// A chain: pieces ['L', length] (a straight line) or ['A', radius, degrees turned] (a circular arc), each starting in
// the direction the last one ended in. y runs down, so a turn towards the top of the picture is negative; a chain
// that goes round a shape against the clock (as seen on screen) turns -360 degrees in all.
// walk: from `start` heading `heading`. With `out`, its points are added to it (an arc as a polyline whose chords stay
// within `tol` units of the arc). Returns where the chain ends.
const walk = (pieces, start, heading = 0, out = null, tol = 0.0006) => {
  let x = start[0], y = start[1], th = heading;
  for (const p of pieces) {
    const t = th * RAD;
    if (p[0] === 'L') {
      if (out) out.push([x, y]);
      x += Math.cos(t) * p[1]; y += Math.sin(t) * p[1];
    } else {
      const r = p[1], sw = p[2], sg = sw < 0 ? -1 : 1, cx = x - sg * r * Math.sin(t), cy = y + sg * r * Math.cos(t);
      if (out) {
        const n = Math.max(2, Math.ceil((Math.abs(sw) * RAD) / (2 * Math.acos(1 - Math.min(tol / r, 0.5)))));
        for (let k = 0; k < n; k++) { const a = (th + (sw * k) / n) * RAD; out.push([cx + sg * r * Math.sin(a), cy - sg * r * Math.cos(a)]); }
      }
      th += sw;
      x = cx + sg * r * Math.sin(th * RAD); y = cy - sg * r * Math.cos(th * RAD);
    }
  }
  return [x, y];
};
// A chain closed exactly. Three of its numbers are given as null and follow from the rest: the last arc turns what is
// left of the full turn, and the two pieces named in `slack` (a line's length or an arc's radius) take up what is
// left for the chain to end where it started (where the chain ends is linear in those two: solved outright).
const closeChain = (pieces, start, heading, slack) => {
  const ps = pieces.map((p) => p.slice());
  const turned = ps.reduce((a, p) => a + (p[0] === 'A' && p[2] !== null ? p[2] : 0), 0);
  const last = ps[ps.length - 1];
  if (last[0] === 'A' && last[2] === null) last[2] = -360 - turned;
  const [i, j] = slack;
  const end = (a, b) => { ps[i][1] = a; ps[j][1] = b; return walk(ps, start, heading); };
  const e0 = end(0, 0), ea = end(1, 0), eb = end(0, 1);
  const m00 = ea[0] - e0[0], m10 = ea[1] - e0[1], m01 = eb[0] - e0[0], m11 = eb[1] - e0[1], det = m00 * m11 - m01 * m10;
  const rx = start[0] - e0[0], ry = start[1] - e0[1];
  ps[i][1] = (rx * m11 - m01 * ry) / det; ps[j][1] = (m00 * ry - m10 * rx) / det;
  return ps;
};
const chainPts = (pieces, start, heading, slack, tol) => { const pts = []; walk(closeChain(pieces, start, heading, slack), start, heading, pts, tol); return pts; };

// ---- the head's outline ----------------------------------------------------------------------------------------------
// From the left end of the bust's lower edge, heading right, round the head. The bust's lower edge and the front of
// the neck are the two pieces that take up the slack.
const START = [-10.2741, 17.8384];
const CHAIN = [
  ['L', null],            //  0 the bust's lower edge
  ['A', 0.32, -103.7],    //  1 its front corner
  ['L', null],            //  2 the front of the neck
  ['A', 0.40, 110.3],     //  3 where the neck meets the jaw
  ['L', 1.17],            //  4 under the jaw
  ['A', 3.45, -28.6],     //  5 the jaw rounding into
  ['A', 2.21, -66.9],     //  6 the chin
  ['L', 0.59],            //  7 the chin's front
  ['A', 2.40, 28.1],      //  8 the hollow under the lower lip
  ['A', 1.18, -108.8],    //  9 the lower lip
  ['L', 1.91],            // 10 the mouth's lower edge
  ['A', 0.25, 161.2],     // 11 the corner of the mouth
  ['L', 2.28],            // 12 the mouth's upper edge
  ['A', 0.96, -88.9],     // 13 the upper lip
  ['A', 0.52, 75.9],      // 14 the hollow under the nose
  ['L', 0.75],            // 15 the underside of the nose
  ['A', 3.47, -18.0],     // 16 rounding into
  ['A', 1.47, -67.1],     // 17 the tip of the nose
  ['A', 2.52, -9.8],      // 18 and out of it
  ['L', 4.30],            // 19 the bridge of the nose
  ['A', 2.30, 30.7],      // 20 the hollow between nose and brow
  ['A', 2.85, -15.2],     // 21 the brow
  ['L', 3.21],            // 22 the forehead
  ['A', 4.86, -39.4],     // 23 the forehead rounding into
  ['A', 11.48, -96.1],    // 24 the skull, over the top (its centre is the origin)
  ['A', 10.31, -65.4],    // 25 the skull, down the back
  ['A', 8.02, 71.7],      // 26 the back of the neck
  ['L', 0.69],            // 27 the slope of the shoulder
  ['A', 2.93, -40.3],     // 28 the shoulder rounding into
  ['A', 1.28, null],      // 29 the bust's back corner
];
const closed = closeChain(CHAIN, START, 0, [0, 2]);
// the outline's points in the head's own frame
const OUTLINE = (() => { const pts = []; walk(closed, START, 0, pts); return pts; })();
const BOX = OUTLINE.reduce((b, p) => [Math.min(b[0], p[0]), Math.min(b[1], p[1]), Math.max(b[2], p[0]), Math.max(b[3], p[1])], [1e9, 1e9, -1e9, -1e9]);

// The same head with its lips shut: the fading heads of "stealth" (in the game their profile has no notch where the
// other heads have the open mouth; in the redraw the lips meet and a dark line runs in from where they meet).
// Everything but the lips is the chain above with its numbers as they are; the five pieces of the open mouth (the
// lower lip, the mouth's two edges and its corner, the upper lip) give way to three: the lower lip, a tight turn
// where the lips meet, the upper lip. The three turn as much in all as the five did; the two lips' radii take up
// the slack, so that the chain passes through the same point above and below the mouth as before.
// Fitted to the front head of the redrawn "stealth" (tools/head_profile_face.py lays its profile in this frame):
// with these turns the lips keep within 0.05 units of it on average, 0.15 at most.
const closedShut = (() => {
  const ps = closed.map((p) => p.slice()), was = ps.slice(9, 14).reduce((a, p) => a + (p[0] === 'A' ? p[2] : 0), 0);
  ps.splice(9, 5, ['A', null, -60], ['A', 0.15, 64], ['A', null, was + 60 - 64]);
  return closeChain(ps, START, 0, [9, 11]);
})();
const OUTLINE_SHUT = (() => { const pts = []; walk(closedShut, START, 0, pts); return pts; })();
// where the lips meet (the middle of the tight turn), for the line that runs in from there
const LIPS_MEET = (() => { const ps = closedShut.slice(0, 11).map((p) => p.slice()); ps[10][2] /= 2; return walk(ps, START, 0); })();

// The same head with a shoulder behind it: the person of "sneak attack", whom the game shows from the back of the
// skull to a shoulder that runs out five pixels behind the neck and drops straight to the bust's lower edge.
// Everything from the bust's lower edge round the face and over the skull is the chain above with its numbers as
// they are; then the back of the neck turns tighter (radius 3.8) into the shoulder's line (6 long, falling 18
// degrees), a rounded corner, the straight side and a tight lower corner; the side and the added length of the
// lower edge take up the slack. In the game (its person laid in this frame, skull 0.716 the size here): the neck's
// deepest point at (-9.8, 7.5), the shoulder's corner at (-17.9, 12.0), its side at -18.2: here (-9.2, 6.8),
// (-17.5, 12.2) and -18.3.
const closedShoulder = (() => {
  const ps = closed.slice(0, 26).map((p) => p.slice());
  ps.push(['A', 3.8, 103.7], ['L', 6.0], ['A', 1.2, -72], ['L', null], ['A', 0.32, -90], ['L', null]);
  return closeChain(ps, START, 0, [29, 31]);
})();
const OUTLINE_SHOULDER = (() => { const pts = []; walk(closedShoulder, START, 0, pts); return pts; })();

// ---- placing ---------------------------------------------------------------------------------------------------------
// A place: { at: [x, y] where the origin (the centre of the skull) goes in the icon, s: the scale, flip: true for a
// head that looks to the left, shut: true for the head with its lips shut, shoulder: true for the one with a
// shoulder behind it }.
const toIcon = (pl) => { const f = pl.flip ? -1 : 1, s = pl.s || 1; return (p) => [pl.at[0] + f * s * p[0], pl.at[1] + s * p[1]]; };
const outlineOf = (pl) => (pl.shut ? OUTLINE_SHUT : pl.shoulder ? OUTLINE_SHOULDER : OUTLINE);
const outlinePts = (pl) => outlineOf(pl).map(toIcon(pl));
// the head's shape in the icon (one function per place, so that the canvas computes its distances once)
const shapes = new Map();
const shape = (pl) => {
  const key = [pl.at[0], pl.at[1], pl.s || 1, pl.flip ? 1 : 0, pl.shut ? 1 : 0, pl.shoulder ? 1 : 0].join(' ');
  if (!shapes.has(key)) shapes.set(key, S.polygon(outlinePts(pl), 40));
  return shapes.get(key);
};

// ---- the modelling ---------------------------------------------------------------------------------------------------
// the table's surface at (u, v) of the head's own frame (a cubic B-spline; outside the grid its edge value: white)
const tone = (() => {
  const { x0, y0, cell, nx, ny, coef } = TONE, flat = new Float32Array(nx * ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) flat[j * nx + i] = coef[j][i];
  const w = new Float64Array(8);
  const weights = (f, o) => { const g = 1 - f; w[o] = (g * g * g) / 6; w[o + 1] = (3 * f * f * f - 6 * f * f + 4) / 6; w[o + 2] = (-3 * f * f * f + 3 * f * f + 3 * f + 1) / 6; w[o + 3] = (f * f * f) / 6; };
  return (u, v) => {
    const gx = (u - x0) / cell, gy = (v - y0) / cell, ix = Math.floor(gx), iy = Math.floor(gy);
    weights(gx - ix, 0); weights(gy - iy, 4);
    let sum = 0;
    for (let b = 0; b < 4; b++) {
      const row = clamp(iy - 1 + b, 0, ny - 1) * nx;
      let a = 0;
      for (let k = 0; k < 4; k++) a += w[k] * flat[row + clamp(ix - 1 + k, 0, nx - 1)];
      sum += w[4 + b] * a;
    }
    return sum;
  };
})();

// A palette says what colour a whiteness is, and how an edge is made (depths in units of the head's own frame):
//   colour(t, out)   whiteness -> sRGB 0..1 written to out.r, out.g, out.b
//   line             the depth at which the light line along an edge begins
//   rise(d)          how much of the line's whiteness is reached at depth d between the edge and the line (0..1)
//   under(d)         what is taken off the whiteness close to the edge (the colour there is deeper than at t = 0)
//   dim(d)           how much of the colour's light is left at depth d (the dark line at the very edge)
//   fade             [from, to]: the depths over which the white line gives way to the table
//
// Blue, measured on the redraws (tools/head_profile_edge.py, the median colour at each depth round three heads):
//   depth   0.02      0.08      0.14      0.21      0.27       0.33       0.39       0.46      0.52
//   colour  001486    0931b9    265ce0    4f88f7    82b2fe     b0d4ff     dbeefe     f6fcfc    fdfdfb
// that is whiteness 0 at 0.03 rising to 1 at 0.50 as a smooth step, on a colour that is deeper than azure at the very
// edge and carries 0.19 of its light there, all of it from 0.25 on; white as far as 0.65, the table's own from 0.85.
// In the body the colours lie on the line from azure (0, 87, 252) to white: G = 87 + 0.655 R, B = 252. Below t = 0,
// where R is 0, G goes on down at the same rate (the darkest of a head's own shadow is (0, 54, 252) at -0.2), and
// from -0.12 the blue itself darkens: the faded heads of "stealth" reach (0, 47, 228) and, under the neck, (0, 32, 195).
const BLUE = {
  colour: (t, out) => {
    // The GAME's blue (the user, 2026-10-08: the redraw's azure was too green): its head's colours lie on the line
    // green = 52 + 0.79 red, blue 255 (measured: 21,65,233  68,106,255  116,145,255  170,188,255).
    // (and its shadows are paler than the redraw's: the game's deepest are 21,65,233 on a few pixels, most of the head
    // lies between 116 and 170 of red; so the whiteness is lifted in its lower half)
    t = t >= 0 ? t + 0.16 * (1 - t) * (1 - t) : t + 0.16 * Math.max(1 + t / 0.2, 0);      // (the lift runs out smoothly below 0: no step)
    if (t >= 0) { out.r = Math.min(t, 1); out.g = Math.min(52 + 203 * t, 255) / 255; out.b = Math.min(252 + 3 * t, 255) / 255; return; }
    out.r = 0; out.g = (t > -0.2 ? 52 + 130 * t : Math.max(26 + 60 * (t + 0.2), 12)) / 255;
    out.b = (252 - 300 * Math.pow(Math.max(-t - 0.12, 0), 1.4)) / 255;
  },
  line: 0.5,
  rise: (d) => smooth(0.03, 0.5, d),
  under: (d) => -0.2 * (1 - smooth(0, 0.14, d)),
  dim: (d) => 0.12 + 0.88 * smooth(-0.05, 0.25, d),
  fade: [0.55, 0.85],
};
// Red, measured on "affect mind" (tools/head_profile_tint.py pairs the redraw's colours with the whiteness the blue
// head has at the same place: one straight line again, R = 253, G = 44 + 211 t, B = 14 + 241 t), and its edge
// (tools/head_profile_edge.py; depths from the place 0.8 inside the redraw's outer edge, where the black border ends):
//   depth   0.0       0.1       0.2       0.3       0.4       0.47      0.53      0.59      0.66      0.78
//   colour  9d0202    be0102    d70202    ee0c0a    f8372d    fc6d5d    fd9a8b    fdcabd    fde9e1    white
// a pure red that carries a third of its light at the edge and all of it from 0.4 on, then whitens to the line at
// 0.74; white as far as 0.9, the table's own from 1.5.
const RED = {
  colour: (t, out) => { out.r = (253 + 2 * clamp(t, 0, 1)) / 255; out.g = clamp(44 + 211 * t, 0, 255) / 255; out.b = clamp(14 + 241 * t, 0, 255) / 255; },
  line: 0.74,
  rise: (d) => smooth(0.34, 0.74, d),
  under: (d) => -0.2 * (1 - smooth(0.34, 0.6, d)),
  dim: (d) => clamp(0.34 + 1.65 * d, 0, 1),
  fade: [0.9, 1.5],
};

const INK = '#0a0a0c';
const BORDER = 0.8;         // the black line round a body: the redraws carry 0.76 to 0.83 round a head, 0.9 round an arc

// The light that gathers along an edge the table knows nothing of (the line round the brain): the share of what is
// missing to white that is added at depth d from that edge. Measured on the redraw round the brain: 0.87 at 0.5,
// 0.75 at 0.7, 0.48 at 0.9, 0.35 at 1.1, 0.13 at 1.3, none at 1.5.
const gather = (d) => 0.9 * (1 - smooth(0.45, 1.5, d));

// A head's whiteness: for a head at a place, the function (x, y, dist) -> whiteness at that place of the icon, dist
// being the signed distance to the head's outline there (negative inside, units of the icon; a canvas field's value).
// From the edge to the line the edge's own rise, then the white line giving way to the table.
// With the lips shut, the line where they part: measured on the redraw's "stealth", it runs level from where the lips
// meet 2.6 into the face, a sixth of a unit under the meeting point, half a unit wide at half its depth, as dark as
// the head's deepest shadow (whiteness -0.2) over its outer 1.5 and fading out over the rest.
const white = (pl, pal = BLUE, fade = pal.fade) => {
  const s = pl.s || 1, f = pl.flip ? -1 : 1, ax = pl.at[0], ay = pl.at[1], shut = !!pl.shut;
  const part = (t, u, v) => {
    const k = 0.9 * smooth(LIPS_MEET[0] - 2.6, LIPS_MEET[0] - 1.5, u) * Math.exp(-(((v - LIPS_MEET[1] - 0.16) / 0.3) ** 2));
    return k > 0.004 ? mix(t, -0.2, k) : t;
  };
  // With the shoulder: the table knows the head only as far as its own bust, and is white beyond and along the
  // bust's old edge. Behind the neck it gives way to the shoulder's own whiteness: 0.74 (the game: 170 to 200 of 255
  // inside the shoulder, white along its upper and outer edges, which is the edge's own line here).
  const shoulder = !!pl.shoulder;
  const w = (x, y, dist) => {
    const d = -dist / s, u = (f * (x - ax)) / s, v = (y - ay) / s;
    let t;
    if (d < pal.line) t = pal.rise(d) + pal.under(d);
    else {
      t = tone(u, v);
      if (shoulder) t = mix(t, 0.74, smooth(-6.0, -9.0, u) * smooth(5.0, 8.0, v));
      const k = smooth(fade[0], fade[1], d); if (k < 1) t = mix(1, t, k);
    }
    return shut ? part(t, u, v) : t;
  };
  // (the parting of the lips alone, laid on any whiteness at a place of the icon)
  w.part = shut ? (t, x, y) => part(t, (f * (x - ax)) / s, (y - ay) / s) : (t) => t;
  return w;
};
// a whiteness as a colour, with the dark line of an edge at depth d
const paint = (pal, t, d, px) => {
  pal.colour(t, px);
  const k = pal.dim(d);
  if (k < 1) { px.r = P.toSRGB(P.toLinear(px.r) * k); px.g = P.toSRGB(P.toLinear(px.g) * k); px.b = P.toSRGB(P.toLinear(px.b) * k); }
  px.a = 1;
};

// The shader of a head at a place. o:
//   palette   BLUE (default) or RED
//   lower     taken off the whiteness everywhere (the same head, darker by that much)
//   inner     [{ field, off }]: the distances (a canvas field, less `off`: positive on the head's surface) to the
//             edge of something set into the head; the head's light gathers along it as along its own edge
const shader = (pl, o = {}) => {
  const pal = o.palette || BLUE, s = pl.s || 1, w = white(pl, pal, o.fade || pal.fade), lower = o.lower || 0, inner = o.inner || [];
  return (px) => {
    let d = -px.d / s, t = w(px.x, px.y, px.d);
    for (const e of inner) {
      const g = (e.field[px.i] - (e.off || 0)) / s;
      if (g >= pal.line + 1.2) continue;
      const lit = t + (1 - t) * gather(Math.max(g, pal.line));
      t = g < pal.line ? pal.rise(g) * lit + pal.under(g) : lit;
      if (g < d) d = g;
    }
    paint(pal, t - lower, d, px);
  };
};

// The head drawn: its black border (0 for none), then its body.
const draw = (c, pl, o = {}) => {
  const sh = shape(pl), border = o.border === undefined ? BORDER : o.border;
  if (border > 0) c.fill(sh, P.flat(o.ink || INK), border);
  c.fill(sh, shader(pl, o));
  return sh;
};

// ---- a plain body with the head's edge -------------------------------------------------------------------------------
// What stands beside a head is made like the head: the black border, the dark line at the very edge brightening to
// the body's own whiteness (the game's arcs: a white middle between blue pixels; measured on the redraw's arc of
// "mind": 0.92 at the line, 0.87 in the middle). o: palette, tone, border, s (the scale the edge is drawn at: that of
// the head it stands beside).
const bodyShader = (o = {}) => {
  const pal = o.palette || BLUE, s = o.s || 1, level = o.tone === undefined ? 0.9 : o.tone;
  return (px) => { const d = -px.d / s; paint(pal, d < pal.line ? pal.rise(d) * level + pal.under(d) : level, d, px); };
};
const body = (c, sh, o = {}) => {
  const border = o.border === undefined ? BORDER : o.border;
  if (border > 0) c.fill(sh, P.flat(o.ink || INK), border);
  c.fill(sh, bodyShader(o));
  return sh;
};

// An arc of one thickness with round ends: everything within w / 2 of the circular line of radius r about (cx, cy)
// from angle a0 to a1 (degrees, clockwise on screen from +x, a0 < a1). Its distances are exact everywhere (the
// library's arcRound is built from a ring cut by two planes, whose distance beyond the cuts is not: grown into a
// border it puts corners on the round ends).
const arcBand = (cx, cy, r, w, a0, a1) => {
  const mid = ((a0 + a1) / 2) * RAD, half = ((a1 - a0) / 2) * RAD;
  const e0 = [cx + r * Math.cos(a0 * RAD), cy + r * Math.sin(a0 * RAD)], e1 = [cx + r * Math.cos(a1 * RAD), cy + r * Math.sin(a1 * RAD)];
  return (x, y) => {
    let a = Math.atan2(y - cy, x - cx) - mid;
    a -= 2 * Math.PI * Math.round(a / (2 * Math.PI));
    const line = Math.abs(a) <= half ? Math.abs(Math.hypot(x - cx, y - cy) - r) : Math.min(Math.hypot(x - e0[0], y - e0[1]), Math.hypot(x - e1[0], y - e1[1]));
    return line - w / 2;
  };
};

// The black of several bodies at once: each one's border; and, with `close`, the borders of DIFFERENT bodies run
// together wherever the clear gap between them is narrower than twice `close` (in the game's icons the nose and the
// arc before it share one black line, and an arc's ends run into the head's border). What stays clear between two
// bodies ends in a round of radius `close`: the black is the borders' area closed by a disc of that radius, which
// is exact geometry (no gap is left that such a disc could not enter) and has a crisp edge everywhere.
// Worked out on the canvas: m is the distance to the nearest body; the clear places a disc's centre may take are
// K = { m >= border + close }; a place is clear if it lies within `close` of K. The distance to K is the distance
// to the nearest point of K's edge (the edge's points taken from m itself, finer than a pixel).
// A hollow of ONE body (the mouth, the corner under the jaw) is left as it is in every other icon: what the same
// closing would fill for each body alone is taken off again.
// (Laid before the bodies themselves, which cover what of it falls on them.)
// closed: for the bodies whose distance fields are given, the field of what the closing adds (negative where black)
const closed_ = (c, fields, T, close) => {
  const N = c.size, k = c.k, n = N * N;
  const m1 = new Float32Array(n);
  for (let i = 0; i < n; i++) { let a = Infinity; for (const f of fields) if (f[i] < a) a = f[i]; m1[i] = a; }
  // the points of K's edge, one for every pixel of K that has a neighbour outside it; kept in a grid of cells so
  // that the nearest one to any place is found by looking in the cells round it
  const cell = Math.max(close, 4 / k), cols = Math.ceil(c.units / cell) + 1, grid = new Map();
  const edgePts = [];
  const put = (px, py) => {
    const key = Math.floor(py / cell) * cols + Math.floor(px / cell);
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(edgePts.length); edgePts.push(px, py);
  };
  // (where m passes through border + close between two neighbouring pixels, along the row or down the column:
  // these points lie on K's edge itself, also where two bodies' distances meet in a corner)
  for (let j = 0; j < N; j++) {
    for (let x = 0, i = j * N; x < N; x++, i++) {
      const a = m1[i] - T;
      if (x < N - 1) { const b = m1[i + 1] - T; if ((a < 0) !== (b < 0)) put((x + 0.5 + a / (a - b)) / k, (j + 0.5) / k); }
      if (j < N - 1) { const b = m1[i + N] - T; if ((a < 0) !== (b < 0)) put((x + 0.5) / k, (j + 0.5 + a / (a - b)) / k); }
    }
  }
  // black: outside K and further than `close` from it. (Only whether a place is nearer than `close`, and by how
  // much near that limit, matters: the search stops two pixels beyond it.)
  const g = new Float32Array(n).fill(1), reach = close + 2 / k, span = Math.ceil(reach / cell);
  for (let j = 0, i = 0; j < N; j++) {
    for (let x = 0; x < N; x++, i++) {
      if (m1[i] >= T) continue;
      if (m1[i] < T - close - 2 / k) { g[i] = -1; continue; }           // (inside a border or a body: black whatever the rest)
      const px = (x + 0.5) / k, py = (j + 0.5) / k, cx = Math.floor(px / cell), cy = Math.floor(py / cell);
      let best = reach * reach;
      for (let b = cy - span; b <= cy + span; b++) {
        for (let a = cx - span; a <= cx + span; a++) {
          const list = a < 0 || b < 0 ? null : grid.get(b * cols + a);
          if (!list) continue;
          for (const e of list) { const dx = edgePts[e] - px, dy = edgePts[e + 1] - py, dd = dx * dx + dy * dy; if (dd < best) best = dd; }
        }
      }
      // (beyond the canvas all is taken to be clear: its edge counts as K's)
      g[i] = close - Math.min(Math.sqrt(best), px, py, c.units - px, c.units - py);
    }
  }
  return { g, m1 };
};
const borders = (c, list, { border = BORDER, ink = INK, close = 0 } = {}) => {
  if (!(close > 0) || list.length < 2) { for (const sh of list) c.fill(sh, P.flat(ink), border); return; }
  const fields = list.map((sh) => c.field(sh)), T = border + close, { g, m1 } = closed_(c, fields, T, close);
  // What each body's own hollows would take is taken off. A hollow is where the closing of that body alone reaches
  // further than its plain border does; there, and two pixels beyond (or the hollow's edge would be left as a hairline),
  // nothing is added.
  const px2 = 2 / c.k;
  for (const f of fields) {
    const own = closed_(c, [f], T, close).g;
    for (let i = 0; i < g.length; i++) { const b = f[i] - border; if (b > 0 && own[i] < px2 && own[i] < b - px2 / 2 && px2 - own[i] > g[i]) g[i] = px2 - own[i]; }
  }
  // the borders and what joins them are one black, laid in one go (two fills meeting along an edge would leave a seam)
  for (let i = 0; i < g.length; i++) { const b = m1[i] - border; if (b < g[i]) g[i] = b; }
  const joined = () => 1;                 // (a shape that stands for the field just worked out)
  c.fields.set(joined, g);
  c.fill(joined, P.flat(ink));
  c.fields.delete(joined);
};

// ---- the brain ("mind") ----------------------------------------------------------------------------------------------
// A blue bean with a black line round it, set into the skull. Its outline, in the head's own frame, is five arcs and
// a line: the lower lobe, the notch, the straight underside, the front end, the long arc over the top, the back
// (the underside and the long arc take up the slack). The shape is the game's bean (main body three pixels high
// and nine long, a lobe four wide hanging five down at the back, the underside rising a pixel towards the front);
// the redraw's bean is the same shape, and the chain was fitted to it (tools/head_profile_chain.py: within 0.05
// units on average, 0.14 at most).
// Size and line are the GAME's, not the redraw's: there the line is one pixel like the head's own and the bean with
// its line takes two thirds of the skull's width, three pixels of head left either side of it; the redraw fattens
// the line to 1.6 and shrinks the blue to make up for it. So: the head's own border width, and the bean 1.18 times
// the redraw's, centred between the back of the skull and the brow, 2.4 under the crown.
// Round the line the head's light gathers as along the head's own edge (the game: white pixels right against it).
// The bean is one blue (the game's 4-5 middle blues, whiteness 0.22), darkening to its edge like every edge here.
const BRAIN = {
  start: [-5.13, 2.59], heading: 22.7, slack: [2, 4], tone: 0.22,
  pieces: [['A', 2.38, -121.5], ['A', 2.26, 81.7], ['L', null], ['A', 1.62, -125.2], ['A', null, -143.1], ['A', 2.54, null]],
};
const brainPts = (pl) => chainPts(BRAIN.pieces, BRAIN.start, BRAIN.heading, BRAIN.slack).map(toIcon(pl));
// the head's body with the brain set into it (the head's own border is not drawn here: see `borders`)
const drawWithBrain = (c, pl, o = {}) => {
  const s = pl.s || 1, bean = S.polygon(brainPts(pl), 40), line = o.line === undefined ? BORDER : o.line;
  c.fill(shape(pl), shader(pl, { ...o, inner: [{ field: c.field(bean), off: line }] }));
  c.fill(bean, P.flat(o.ink || INK), line);
  c.fill(bean, bodyShader({ palette: o.palette, s, tone: BRAIN.tone }));
  return bean;
};

// ---- two heads fading ("stealth") ------------------------------------------------------------------------------------
// One head behind another, both fading. Read off the game's icon and measured on the redraw (tools/
// head_profile_tint.py pairs the redraw's colours with the whiteness the plain head has at the same place):
//   a head where it stands alone is the head, darker by 0.45 (the redraw: 0.42 to 0.45 over the whole range; the
//     game: its darkest blues there);
//   where the two lie over one another the picture is LIGHTER, not darker: the redraw has 0.07 + 0.55 w there for the
//     front head's whiteness w whatever the back head's own modelling is at the place, the game its middle blues.
//     So the back head lies behind the front one as an even veil of light, half strength: with it the front head's
//     whiteness w becomes 1 - (1 - 0.5)(1 - w), and the same 0.45 comes off (0.05 + 0.5 w);
//   the front head's own outline stays bright (0.85 at the line; the back head's is 0.55), and its light dies away
//     over two units inward: 0.3 added at the line, none from 2.4;
//   the back head's outline shows through the front head as a line 0.15 lighter than what lies round it: the veil
//     is 0.73 at the back head's line and settles to its half within 1.7 of the edge.
//   the fading does not go on down for ever: what the plain head has below 0.2 all comes out about (0, 45, 230),
//     whiteness -0.3 (the redraw: 002ee8 at 0.19, 002be6 in the shadow of the neck at -0.2). A soft floor there.
// Where the front head's edge lies on the back head there is no dark line: its bright line rises straight out of the
// back head's blue (things of one colour that touch are one piece).
const fadedPair = (c, back, front, o = {}) => {
  const pal = BLUE, lower = o.lower === undefined ? 0.45 : o.lower, lift = o.lift === undefined ? 0.3 : o.lift;
  const a = shape(back), b = shape(front), fa = c.field(a), wa = white(back), wb = white(front), sa = back.s || 1, sb = front.s || 1;
  const floor = (t) => { const x = t + 0.3; return -0.3 + 0.5 * (x + Math.sqrt(x * x + 0.0025)); };
  c.fill(a, (px) => { const d = -px.d / sa; paint(pal, d < pal.line ? wa(px.x, px.y, px.d) - lower : floor(wa(px.x, px.y, px.d) - lower), d, px); });
  c.fill(b, (px) => {
    const d = -px.d / sb, da = -fa[px.i] / sa;
    if (d >= pal.line) {
      const veil = da > 0 ? Math.max(wa.part(pal.rise(da) * (0.5 + 0.23 * (1 - smooth(0.5, 1.7, da))), px.x, px.y), 0) : 0;
      pal.colour(floor(1 - (1 - veil) * (1 - wb(px.x, px.y, px.d)) - lower + lift * (1 - smooth(0.6, 2.4, d))), px); px.a = 1;
      return;
    }
    // the edge: on the border it is the head's own edge; on the back head the bright line fades in over what is there
    const over = smooth(0, 0.5, da), k = mix(pal.dim(d), 1, over);
    pal.colour(mix(wb(px.x, px.y, px.d), wb.part(1, px.x, px.y), over) - lower + lift, px);
    if (k < 1) { px.r = P.toSRGB(P.toLinear(px.r) * k); px.g = P.toSRGB(P.toLinear(px.g) * k); px.b = P.toSRGB(P.toLinear(px.b) * k); }
    px.a = mix(1, pal.rise(d), over);
  });
  return [a, b];
};

// ---- the picture of "sneak attack" -----------------------------------------------------------------------------------
// What it is: a round black window; in it a person seen from behind the shoulder, and behind that person, in the
// dark, two eyes and a jagged white flash. Beside the window a column of bars counts the feat's level: one to five
// white ones, then red ones from the bottom up.
// Read off the game's pixels (the ten icons carry the same picture), in the game's own coordinates:
//   the window: a disc of radius 14.8 about (26.9, 15.9). The game shows only its left 18 units: it cuts the
//     picture off flat at x = 30, through the disc and through the person's head;
//   the person: the head, skull's centre at (32.0, 13.1), 0.716 the size it has here, with the shoulder behind it;
//   the flash: eleven straight edges, a bar with a tooth at its left end and a spur on top, whose right end runs
//     down in a slant to a foot that points down and to the left (its points below). Its tooth and its spur stand
//     out of the window in the game, black border and all; so they do here;
//   the eyes: two lights three pixels wide and two high, four apart, at the level of the person's ear;
//   the bars: nine wide, four high, two apart. (The game's top and bottom bars are five high with their outer
//     corners cut; here all five are one size, the three middle ones exactly where the game has them.)
// Changed from the game (o.whole, the default): the window is drawn WHOLE and the person whole in it, and to make
// room the whole icon, bars and all, is 0.74 of the game's size: the bars and the window keep their sizes relative to
// one another. With o.whole = false the picture is laid out as the game has it, cut flat at x = 30.
const SNEAK = {
  disc: [26.9, 15.9, 14.8], cut: 30.6, person: { at: [32.0, 13.1], s: 0.716, shoulder: true },
  // (the flash as the user outlined it on 2026-10-08: six points: its left point, the notch, the peak, its right point,
  // its lower point, and the inner corner; no teeth, no flat foot)
  // (the user tried other forms on 2026-10-08 and came back to this one: keep it)
  // (its side towards the head is ONE arc that keeps beside the head: a circle about the head's middle (30.6, 11.5),
  // 7.6 in radius, 1.5 outside the head's own outline, from the level of the head's top down to the flash's foot;
  // the game has two straight lines there: the user)
  flash: (() => {
    const cx = 30.6, cy = 11.5, r = 7.6, arc = [], y0 = 5.0, y1 = 11.0;
    for (let i = 0; i <= 40; i++) { const y = y0 + ((y1 - y0) * i) / 40; arc.push([cx - Math.sqrt(r * r - (y - cy) * (y - cy)), y]); }
    return [[15.6, 4.0], [22.9, 4.0], [22.9, 1.8],   /* this inner corner moved right to where the user marked it, under the top point */ ...arc,   /* the top is ONE point too */ [16.3, 11.0], [21.3, 7.75]];   /* the inner corner 1.1 further in, where the user marked it */   // (the upper left end is ONE point, like the lower left one: the user)
  })(),
  eyes: [[16.5, 15.0], [20.5, 15.0]], eye: [1.4, 0.95, 0.35],
  bars: { x: [1, 10], top: 2, high: 4, pitch: 6 },
  white: { rim: '#8ea4ee', edge: '#e4eaff', body: '#ffffff' }, red: { rim: '#6a0502', edge: '#cf0c06', body: '#f60e08' },
};
const sneak = (c, level, o = {}) => {
  const G = require('../lib/geom'), F = require('./flat');
  // The user (2026-10-08): the shrunk whole picture was wrong ("much smaller than the original"), and the person is the
  // FRONT bust, as the game's pixels and ChatGPT's redraw show it: its left half, the picture cut upright at the right.
  // So the default is now the game's own size and layout, and the bust of parts/symbol_head_front.js with its axis on
  // the cut (head 12.2 wide: the game's 6 pixels from x 24 to 30; top of the head at y 5.2, shoulder out to x 19).
  const whole = o.whole === true, k = whole ? 0.74 : 1, q = SNEAK;
  // the game's coordinates to the icon's: the bars' left edge stays at x = 1, the window's middle goes to mid height
  const ox = 1 - k * q.bars.x[0], oy = 16 - k * q.disc[1], T = (p) => [ox + k * p[0], oy + k * p[1]];
  // the bars: `level` of them from the bottom; from level 6 on all five, the lowest (level - 5) red
  for (let i = 0; i < 5; i++) {
    const fromBottom = 4 - i;
    if (fromBottom >= Math.min(level, 5)) continue;
    const y0 = q.bars.top + i * q.bars.pitch, pts = [[q.bars.x[0], y0], [q.bars.x[1], y0], [q.bars.x[1], y0 + q.bars.high], [q.bars.x[0], y0 + q.bars.high]].map(T);
    F.solid(c, pts, { palette: fromBottom < level - 5 ? q.red : q.white, border: 0, depth: 0.7 * k });
  }
  const picture = (t) => {
    const disc = S.circle(...T(q.disc), k * q.disc[2]), flash = q.flash.map(T), pl = { ...q.person, at: T(q.person.at), s: k * q.person.s };
    // all the black first: the window, and the border of the flash where its points stand out of the window
    t.fill(disc, P.flat(INK));
    t.fill(S.polygon(G.offsetPts(flash, BORDER * k)), P.flat(INK));
    if (whole) t.fill(shape(pl), shader(pl));
    else { const HF = require('./symbol_head_front'); HF.bust(t, { at: [q.cut, 5.2], s: 1 }, { hue: 'blue', ...HF.SHOULDERS, border: 0 }); }
    t.fill(S.polygon(flash), bodyShader({ s: 0.8 * k, tone: 1 }));
    for (const e of q.eyes) { const [x, y] = T(e); t.fill(S.box(x, y, k * q.eye[0], k * q.eye[1], k * q.eye[2]), bodyShader({ s: 0.45 * k, tone: 0.92 })); }
  };
  if (whole) picture(c); else c.layer(picture, { mask: S.box(q.cut / 2, 16, q.cut / 2, 20) });
};

module.exports = { walk, closeChain, chainPts, START, CHAIN, OUTLINE, OUTLINE_SHUT, OUTLINE_SHOULDER, LIPS_MEET, BOX, BORDER, INK, BLUE, RED, closed, closedShut, closedShoulder, toIcon, outlineOf, outlinePts, shape, tone, gather, white, paint,
  shader, draw, bodyShader, body, arcBand, borders, BRAIN, brainPts, drawWithBrain, fadedPair, SNEAK, sneak, smooth };
