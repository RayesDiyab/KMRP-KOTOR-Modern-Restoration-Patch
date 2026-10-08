'use strict';
// 2D signed distance functions. A shape is a function (x, y) -> distance to its edge in units, negative inside.
// Units are the vanilla icon's own pixels: the drawing space is 32 x 32, x to the right, y down.
// Formulas after Inigo Quilez, https://iquilezles.org/articles/distfunctions2d

const { abs, min, max, sqrt, hypot, sin, cos, atan2, PI } = Math;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const mix = (a, b, t) => a + (b - a) * t;
const rad = (deg) => (deg * PI) / 180;

// ---- primitives --------------------------------------------------------------------------------------------------
const circle = (cx, cy, r) => (x, y) => hypot(x - cx, y - cy) - r;

// a ring: the band of width w centred on radius r
const ring = (cx, cy, r, w) => (x, y) => abs(hypot(x - cx, y - cy) - r) - w / 2;

// a box with half sizes hw, hh, corners rounded by r
const box = (cx, cy, hw, hh, r = 0) => (x, y) => {
  const dx = abs(x - cx) - hw + r, dy = abs(y - cy) - hh + r;
  return hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0) - r;
};

// a line from a to b of thickness w with round ends
const capsule = (ax, ay, bx, by, w) => {
  const ex = bx - ax, ey = by - ay, ee = ex * ex + ey * ey || 1e-9;
  return (x, y) => {
    const wx = x - ax, wy = y - ay, t = clamp((wx * ex + wy * ey) / ee, 0, 1);
    return hypot(wx - ex * t, wy - ey * t) - w / 2;
  };
};

// a line from a to b of thickness w with square ends (a box turned to the line)
const bar = (ax, ay, bx, by, w) => {
  const len = hypot(bx - ax, by - ay) || 1e-9, ux = (bx - ax) / len, uy = (by - ay) / len;
  const mx = (ax + bx) / 2, my = (ay + by) / 2;
  return (x, y) => {
    const px = x - mx, py = y - my, dx = abs(px * ux + py * uy) - len / 2, dy = abs(-px * uy + py * ux) - w / 2;
    return hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0);
  };
};

// everything on one side of the line through (px, py); (nx, ny) points OUT of the shape
const halfPlane = (px, py, nx, ny) => {
  const l = hypot(nx, ny) || 1e-9; nx /= l; ny /= l;
  return (x, y) => (x - px) * nx + (y - py) * ny;
};

// an exact polygon; pts = [[x, y], ...] in order
const FAR = 7;      // further than this from a polygon's bounding box, the box's distance is returned (a lower bound:
                    // nothing drawn reaches that far, and small shapes cost almost nothing on the rest of the canvas)
// rule: 'evenodd' (default) or 'nonzero' (an outline that crosses itself is filled where it overlaps itself)
const polygon = (pts, far = FAR, rule = 'evenodd') => {
  const nonzero = rule === 'nonzero';
  const n = pts.length, vx = new Float64Array(n), vy = new Float64Array(n);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) {
    vx[i] = pts[i][0]; vy[i] = pts[i][1];
    x0 = min(x0, vx[i]); x1 = max(x1, vx[i]); y0 = min(y0, vy[i]); y1 = max(y1, vy[i]);
  }
  return (x, y) => {
    const ox = max(x0 - x, x - x1, 0), oy = max(y0 - y, y - y1, 0);
    if (ox > far || oy > far) return hypot(ox, oy);
    let d = (x - vx[0]) * (x - vx[0]) + (y - vy[0]) * (y - vy[0]), s = 1, wn = 0;
    for (let i = 0, j = n - 1; i < n; j = i, i++) {
      const ex = vx[j] - vx[i], ey = vy[j] - vy[i], wx = x - vx[i], wy = y - vy[i];
      const t = clamp((wx * ex + wy * ey) / (ex * ex + ey * ey || 1e-12), 0, 1);
      const bx = wx - ex * t, by = wy - ey * t, dd = bx * bx + by * by;
      if (dd < d) d = dd;
      const c1 = y >= vy[i], c2 = y < vy[j], c3 = ex * wy > ey * wx;
      if (c1 && c2 && c3) { s = -s; wn++; } else if (!c1 && !c2 && !c3) { s = -s; wn--; }
    }
    return (nonzero ? (wn !== 0 ? -1 : 1) : s) * sqrt(d);
  };
};

// A polygon with its corners rounded by circular arcs (fillets). pts = [[x, y] or [x, y, r], ...]; r is the radius
// for corners that give none (0 = sharp). A radius too large for a corner's sides is cut down to fit.
const roundedPoints = (pts, r = 0, arcStep = 0.12) => {
  const n = pts.length, out = [];
  for (let i = 0; i < n; i++) {
    const A = pts[(i + n - 1) % n], B = pts[i], Cn = pts[(i + 1) % n];
    let rr = B.length > 2 ? B[2] : r;
    const ux = A[0] - B[0], uy = A[1] - B[1], vx = Cn[0] - B[0], vy = Cn[1] - B[1];
    const lu = hypot(ux, uy), lv = hypot(vx, vy);
    if (rr <= 0 || lu < 1e-6 || lv < 1e-6) { out.push([B[0], B[1]]); continue; }
    const cosA = clamp((ux * vx + uy * vy) / (lu * lv), -1, 1), half = Math.acos(cosA) / 2;
    if (half < 1e-3 || half > PI / 2 - 1e-3) { out.push([B[0], B[1]]); continue; }
    let t = rr / Math.tan(half);
    const tMax = min(lu, lv) * 0.5;
    if (t > tMax) { t = tMax; rr = t * Math.tan(half); }
    const p1x = B[0] + (ux / lu) * t, p1y = B[1] + (uy / lu) * t, p2x = B[0] + (vx / lv) * t, p2y = B[1] + (vy / lv) * t;
    let bx = ux / lu + vx / lv, by = uy / lu + vy / lv; const bl = hypot(bx, by); bx /= bl; by /= bl;
    const cx = B[0] + (bx * rr) / sin(half), cy = B[1] + (by * rr) / sin(half);
    let a1 = atan2(p1y - cy, p1x - cx), a2 = atan2(p2y - cy, p2x - cx), da = a2 - a1;
    while (da > PI) da -= 2 * PI; while (da < -PI) da += 2 * PI;
    const steps = max(2, Math.ceil((abs(da) * rr) / arcStep));
    for (let s = 0; s <= steps; s++) { const a = a1 + (da * s) / steps; out.push([cx + rr * cos(a), cy + rr * sin(a)]); }
  }
  return out;
};
const rounded = (pts, r, arcStep) => polygon(roundedPoints(pts, r, arcStep));

// A smooth closed curve through the given points (a centripetal Catmull-Rom spline, as a many-sided polygon).
// A point given as [x, y, 'c'] is a corner: the curve stops and starts again there.
const splinePoints = (pts, perSpan = 14) => {
  const n = pts.length, out = [];
  const P = (i) => pts[((i % n) + n) % n];
  for (let i = 0; i < n; i++) {
    const p1 = P(i), p2 = P(i + 1);
    const p0 = p1[2] === 'c' ? p1 : P(i - 1), p3 = p2[2] === 'c' ? p2 : P(i + 2);       // a corner has no way in or out
    const t01 = Math.pow(hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.5) || 1e-3, t12 = Math.pow(hypot(p2[0] - p1[0], p2[1] - p1[1]), 0.5) || 1e-3,
      t23 = Math.pow(hypot(p3[0] - p2[0], p3[1] - p2[1]), 0.5) || 1e-3;
    const m1 = [0, 1].map((k) => (p2[k] - p1[k]) + t12 * ((p1[k] - p0[k]) / t01 - (p2[k] - p0[k]) / (t01 + t12)));
    const m2 = [0, 1].map((k) => (p2[k] - p1[k]) + t12 * ((p3[k] - p2[k]) / t23 - (p3[k] - p1[k]) / (t12 + t23)));
    for (let s = 0; s < perSpan; s++) {
      const t = s / perSpan, t2 = t * t, t3 = t2 * t;
      const h00 = 2 * t3 - 3 * t2 + 1, h10 = t3 - 2 * t2 + t, h01 = -2 * t3 + 3 * t2, h11 = t3 - t2;
      out.push([h00 * p1[0] + h10 * m1[0] + h01 * p2[0] + h11 * m2[0], h00 * p1[1] + h10 * m1[1] + h01 * p2[1] + h11 * m2[1]]);
    }
  }
  return out;
};
const spline = (pts, perSpan) => polygon(splinePoints(pts, perSpan));

// an ellipse, as an exact polygon of many sides (the closed form is long and no more exact at this size)
const ellipse = (cx, cy, rx, ry, turn = 0, sides = 160) => {
  const pts = [], c = cos(rad(turn)), s = sin(rad(turn));
  for (let i = 0; i < sides; i++) {
    const a = (2 * PI * i) / sides, px = rx * cos(a), py = ry * sin(a);
    pts.push([cx + px * c - py * s, cy + px * s + py * c]);
  }
  return polygon(pts);
};

// a regular polygon / a star: n points, outer radius r, inner radius ri (ri = r cos(pi/n) gives the plain polygon)
const star = (cx, cy, n, r, ri, turn = -90) => {
  const pts = [];
  for (let i = 0; i < 2 * n; i++) {
    const a = rad(turn) + (PI * i) / n, rr = i % 2 ? ri : r;
    pts.push([cx + rr * cos(a), cy + rr * sin(a)]);
  }
  return polygon(pts);
};

// the wedge between two angles (degrees, clockwise on screen from the +x axis), from a0 to a1
const wedge = (cx, cy, a0, a1) => {
  const span = (((a1 - a0) % 360) + 360) % 360 || 360;
  const n0x = sin(rad(a0)), n0y = -cos(rad(a0)), n1x = -sin(rad(a1)), n1y = cos(rad(a1));
  return (x, y) => {
    const d0 = (x - cx) * n0x + (y - cy) * n0y, d1 = (x - cx) * n1x + (y - cy) * n1y;
    return span <= 180 ? max(d0, d1) : min(d0, d1);
  };
};

// an arc: the part of a ring between two angles, cut square at its ends
const arc = (cx, cy, r, w, a0, a1) => intersect(ring(cx, cy, r, w), wedge(cx, cy, a0, a1));
// the same with round ends
const arcRound = (cx, cy, r, w, a0, a1) => union(arc(cx, cy, r, w, a0, a1),
  circle(cx + r * cos(rad(a0)), cy + r * sin(rad(a0)), w / 2), circle(cx + r * cos(rad(a1)), cy + r * sin(rad(a1)), w / 2));
// a crescent that tapers to points at its ends: the part of the disc (cx, cy, r) outside a second disc pushed
// `offset` units towards the angle `to` (degrees). Widest (= offset) on the side facing away from `to`.
const crescent = (cx, cy, r, offset, to) => subtract(circle(cx, cy, r), circle(cx + offset * cos(rad(to)), cy + offset * sin(rad(to)), r));

// a closed outline given like an SVG path: M x y, L x y, H x, V y, Q cx cy x y, C c1x c1y c2x c2y x y, Z.
// Absolute coordinates only. Curves are divided into `steps` straight pieces: the result is an exact polygon.
const pathPoints = (d, steps = 20) => {
  const tok = d.match(/[MLHVQCZ]|-?\d*\.?\d+(?:e-?\d+)?/gi) || [];
  const pts = []; let i = 0, x = 0, y = 0, cmd = '';
  const num = () => parseFloat(tok[i++]);
  while (i < tok.length) {
    if (/[MLHVQCZ]/i.test(tok[i])) cmd = tok[i++].toUpperCase();
    if (cmd === 'Z') continue;
    if (cmd === 'M' || cmd === 'L') { x = num(); y = num(); pts.push([x, y]); if (cmd === 'M') cmd = 'L'; }
    else if (cmd === 'H') { x = num(); pts.push([x, y]); }
    else if (cmd === 'V') { y = num(); pts.push([x, y]); }
    else if (cmd === 'Q') {
      const cx = num(), cy = num(), ex = num(), ey = num();
      for (let s = 1; s <= steps; s++) { const t = s / steps, u = 1 - t; pts.push([u * u * x + 2 * u * t * cx + t * t * ex, u * u * y + 2 * u * t * cy + t * t * ey]); }
      x = ex; y = ey;
    } else if (cmd === 'C') {
      const ax = num(), ay = num(), bx = num(), by = num(), ex = num(), ey = num();
      for (let s = 1; s <= steps; s++) {
        const t = s / steps, u = 1 - t;
        pts.push([u * u * u * x + 3 * u * u * t * ax + 3 * u * t * t * bx + t * t * t * ex, u * u * u * y + 3 * u * u * t * ay + 3 * u * t * t * by + t * t * t * ey]);
      }
      x = ex; y = ey;
    } else throw new Error('path: unknown command ' + cmd);
  }
  return pts;
};
const path = (d, steps) => polygon(pathPoints(d, steps));

// a shape that is the same left and right of x = cx: give the outline of its right half (from top to bottom along
// the axis and round the right side), the left half is its mirror image
const symmetric = (cx, halfD, steps) => {
  const right = pathPoints(halfD, steps), left = right.map(([x, y]) => [2 * cx - x, y]).reverse();
  return polygon(right.concat(left));
};
// the same for a list of points: the right half's points from the top of the axis to its bottom; mirrored to the
// left. With r the corners are rounded; with smooth = true the outline is a spline through the points.
const mirrored = (cx, half, { r = 0, smooth = false } = {}) => {
  const onAxis = (p) => abs(p[0] - cx) < 1e-6;
  const left = half.filter((p) => !onAxis(p)).map((p) => [2 * cx - p[0], p[1], ...p.slice(2)]).reverse();
  const all = half.concat(left);
  return smooth ? spline(all) : rounded(all, r);
};

// ---- operators ---------------------------------------------------------------------------------------------------
const union = (...s) => (x, y) => { let d = s[0](x, y); for (let i = 1; i < s.length; i++) { const e = s[i](x, y); if (e < d) d = e; } return d; };
const intersect = (...s) => (x, y) => { let d = s[0](x, y); for (let i = 1; i < s.length; i++) { const e = s[i](x, y); if (e > d) d = e; } return d; };
const subtract = (a, ...b) => (x, y) => { let d = a(x, y); for (let i = 0; i < b.length; i++) { const e = -b[i](x, y); if (e > d) d = e; } return d; };
const invert = (a) => (x, y) => -a(x, y);
// grown by r (shrunk if r is negative): the same shape with its edge r further out, corners rounded by r
const grow = (a, r) => (x, y) => a(x, y) - r;
// the line of width w along the shape's edge
const outline = (a, w) => (x, y) => abs(a(x, y)) - w / 2;
// the band inside the shape between depths d0 and d1 from its edge (d0 < d1)
const inner = (a, d0, d1) => (x, y) => { const d = a(x, y); return max(d + d0, -(d + d1)); };
// two shapes melted together over a distance k
const blend = (a, b, k) => (x, y) => { const p = a(x, y), q = b(x, y), h = clamp(0.5 + (0.5 * (q - p)) / k, 0, 1); return mix(q, p, h) - k * h * (1 - h); };
const move = (a, dx, dy) => (x, y) => a(x - dx, y - dy);
const turn = (a, deg, cx = 16, cy = 16) => { const c = cos(rad(deg)), s = sin(rad(deg)); return (x, y) => { const px = x - cx, py = y - cy; return a(cx + px * c + py * s, cy - px * s + py * c); }; };
const scale = (a, k, cx = 16, cy = 16) => (x, y) => a(cx + (x - cx) / k, cy + (y - cy) / k) * k;
const mirror = (a, cx = 16) => (x, y) => a(2 * cx - x, y);
// n copies turned evenly round (cx, cy)
const spin = (a, n, cx = 16, cy = 16, start = 0) => union(...Array.from({ length: n }, (_, i) => turn(a, start + (360 * i) / n, cx, cy)));

module.exports = { clamp, mix, rad, circle, ring, box, capsule, bar, halfPlane, polygon, roundedPoints, rounded, splinePoints, spline, ellipse, star, wedge, arc, arcRound, crescent,
  pathPoints, path, symmetric, mirrored,
  union, intersect, subtract, invert, grow, outline, inner, blend, move, turn, scale, mirror, spin };
