'use strict';
// Outlines built from points, exactly: a polygon with every edge moved out (corners kept sharp), a line of one width
// with sharp joints, and a frame of reference laid along an object's axis.
const { hypot, cos, sin, PI } = Math;

const signedArea = (pts) => { let a = 0; for (let i = 0, n = pts.length; i < n; i++) { const p = pts[i], q = pts[(i + 1) % n]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };

// The polygon with every edge moved out by w (in, if w is negative). Corners stay sharp (mitred). A corner whose
// point would stand further than limit * |w| from the old corner is cut square across its bisector, so that a very
// sharp tip does not grow a spike.
const offsetPts = (pts, w, limit = 2.6) => {
  const n = pts.length, sgn = signedArea(pts) > 0 ? 1 : -1, out = [], e = [], nr = [];
  for (let i = 0; i < n; i++) {
    const p = pts[i], q = pts[(i + 1) % n], l = hypot(q[0] - p[0], q[1] - p[1]) || 1e-9, ex = (q[0] - p[0]) / l, ey = (q[1] - p[1]) / l;
    e.push([ex, ey]); nr.push([ey * sgn, -ex * sgn]);              // the edge's direction and its normal pointing out
  }
  for (let i = 0; i < n; i++) {
    const a = (i + n - 1) % n, V = pts[i], na = nr[a], nb = nr[i], dot = na[0] * nb[0] + na[1] * nb[1];
    if (1 + dot < 1e-6) { out.push([V[0] + na[0] * w, V[1] + na[1] * w], [V[0] + nb[0] * w, V[1] + nb[1] * w]); continue; }
    const mx = (na[0] + nb[0]) / (1 + dot), my = (na[1] + nb[1]) / (1 + dot), ml = hypot(mx, my);
    const convex = (e[a][0] * e[i][1] - e[a][1] * e[i][0]) * sgn > 0;
    if (ml > limit && ((convex && w > 0) || (!convex && w < 0))) {
      const s = w > 0 ? 1 : -1, bx = (s * mx) / ml, by = (s * my) / ml, cut = limit * Math.abs(w);
      const sa = (cut - w * (na[0] * bx + na[1] * by)) / (e[a][0] * bx + e[a][1] * by);
      const sb = (cut - w * (nb[0] * bx + nb[1] * by)) / (e[i][0] * bx + e[i][1] * by);
      out.push([V[0] + w * na[0] + sa * e[a][0], V[1] + w * na[1] + sa * e[a][1]], [V[0] + w * nb[0] + sb * e[i][0], V[1] + w * nb[1] + sb * e[i][1]]);
    } else out.push([V[0] + mx * w, V[1] + my * w]);
  }
  return out;
};

// A line of half-width hw along the given points, joints sharp, ends cut square: its outline as a polygon.
// lengthen: both ends moved out by that much (negative: drawn in).
const strokePts = (line, hw, { limit = 2.6, lengthen = 0 } = {}) => {
  const pts = line.map((p) => [p[0], p[1]]), n = pts.length;
  const dir = (i) => { const p = pts[i], q = pts[i + 1], l = hypot(q[0] - p[0], q[1] - p[1]) || 1e-9; return [(q[0] - p[0]) / l, (q[1] - p[1]) / l]; };
  if (lengthen) {
    const d0 = dir(0), d1 = dir(n - 2);
    pts[0] = [pts[0][0] - d0[0] * lengthen, pts[0][1] - d0[1] * lengthen];
    pts[n - 1] = [pts[n - 1][0] + d1[0] * lengthen, pts[n - 1][1] + d1[1] * lengthen];
  }
  const left = [], right = [];
  for (let i = 0; i < n; i++) {
    const V = pts[i];
    if (i === 0 || i === n - 1) {
      const d = dir(i === 0 ? 0 : n - 2), nx = -d[1], ny = d[0];
      left.push([V[0] + nx * hw, V[1] + ny * hw]); right.push([V[0] - nx * hw, V[1] - ny * hw]);
      continue;
    }
    const da = dir(i - 1), db = dir(i), na = [-da[1], da[0]], nb = [-db[1], db[0]], dot = na[0] * nb[0] + na[1] * nb[1];
    const mx = (na[0] + nb[0]) / (1 + dot || 1e-9), my = (na[1] + nb[1]) / (1 + dot || 1e-9), ml = hypot(mx, my);
    const turnsLeft = da[0] * db[1] - da[1] * db[0] > 0;            // towards the side its normal points to
    for (const [side, list] of [[1, left], [-1, right]]) {
      const outer = side === 1 ? !turnsLeft : turnsLeft;
      if (ml > limit && outer) {
        const bx = (side * mx) / ml, by = (side * my) / ml, cut = limit * hw;
        const sa = (cut - side * hw * (na[0] * bx + na[1] * by)) / (da[0] * bx + da[1] * by);
        const sb = (cut - side * hw * (nb[0] * bx + nb[1] * by)) / (db[0] * bx + db[1] * by);
        list.push([V[0] + side * hw * na[0] + sa * da[0], V[1] + side * hw * na[1] + sa * da[1]], [V[0] + side * hw * nb[0] + sb * db[0], V[1] + side * hw * nb[1] + sb * db[1]]);
      } else list.push([V[0] + side * hw * mx, V[1] + side * hw * my]);
    }
  }
  // line.point (set on the array of points): both ends come to a point, as long as the line is half wide
  const R2 = right.reverse();
  if (!line.point) return left.concat(R2);
  const d0 = dir(0), d1 = dir(n - 2);
  return [...left, [pts[n - 1][0] + d1[0] * hw, pts[n - 1][1] + d1[1] * hw], ...R2, [pts[0][0] - d0[0] * hw, pts[0][1] - d0[1] * hw]];
};

// A frame laid along an object: from E (its near end) towards T (its far end). t runs along it from E, s across it
// (positive to the right of the direction of travel as seen on screen, where y runs down).
const frame = (E, T) => {
  const L = hypot(T[0] - E[0], T[1] - E[1]), ux = (T[0] - E[0]) / L, uy = (T[1] - E[1]) / L, nx = -uy, ny = ux;
  return {
    L, E, T, u: [ux, uy], n: [nx, ny],
    pt: (t, s) => [E[0] + ux * t + nx * s, E[1] + uy * t + ny * s],
    t: (x, y) => (x - E[0]) * ux + (y - E[1]) * uy,
    s: (x, y) => (x - E[0]) * nx + (y - E[1]) * ny,
    pts: (list) => list.map(([t, s]) => [E[0] + ux * t + nx * s, E[1] + uy * t + ny * s]),
  };
};
// the same from a starting point, an angle (degrees; y runs down, so -45 points up and to the right) and a length
const frameAt = (E, deg, L) => frame(E, [E[0] + L * cos((deg * PI) / 180), E[1] + L * sin((deg * PI) / 180)]);

// points on a circular arc from angle a0 to a1 (degrees), as a polyline fine enough to be exact at any size drawn
const arcPts = (cx, cy, r, a0, a1, step = 0.08) => {
  const n = Math.max(2, Math.ceil((Math.abs(a1 - a0) * PI / 180 * r) / step)), out = [];
  for (let i = 0; i <= n; i++) { const a = ((a0 + ((a1 - a0) * i) / n) * PI) / 180; out.push([cx + r * cos(a), cy + r * sin(a)]); }
  return out;
};

// A line (open) with the corners at the given places rounded by circular arcs of radius r (cut down where a side is
// too short for it); the other corners stay sharp. which: the indices of the corners to round.
const filletLine = (pts, r, which) => {
  const out = [];
  pts.forEach((B, i) => {
    // which: a list of corners (all get r), or { corner: [radius, share of the shorter side it may use] }
    const own = Array.isArray(which) ? (which.includes(i) ? [r, 0.5] : null) : which[i];
    if (i === 0 || i === pts.length - 1 || !own) { out.push(B); return; }
    const A = pts[i - 1], Cn = pts[i + 1], ux = A[0] - B[0], uy = A[1] - B[1], vx = Cn[0] - B[0], vy = Cn[1] - B[1], lu = hypot(ux, uy), lv = hypot(vx, vy);
    const half = Math.acos(Math.max(-1, Math.min(1, (ux * vx + uy * vy) / (lu * lv)))) / 2;
    let t = own[0] / Math.tan(half); const tMax = Math.min(lu, lv) * own[1]; let rr = own[0]; if (t > tMax) { t = tMax; rr = t * Math.tan(half); }
    const p1 = [B[0] + (ux / lu) * t, B[1] + (uy / lu) * t], p2 = [B[0] + (vx / lv) * t, B[1] + (vy / lv) * t];
    let bx = ux / lu + vx / lv, by = uy / lu + vy / lv; const bl = hypot(bx, by); bx /= bl; by /= bl;
    const cx = B[0] + (bx * rr) / sin(half), cy = B[1] + (by * rr) / sin(half);
    const a1 = Math.atan2(p1[1] - cy, p1[0] - cx); let da = Math.atan2(p2[1] - cy, p2[0] - cx) - a1;
    while (da > PI) da -= 2 * PI; while (da < -PI) da += 2 * PI;
    const n = Math.max(3, Math.ceil((Math.abs(da) * rr) / 0.05));
    for (let k = 0; k <= n; k++) { const a = a1 + (da * k) / n; out.push([cx + rr * cos(a), cy + rr * sin(a)]); }
  });
  return out;
};

module.exports = { filletLine, signedArea, offsetPts, strokePts, frame, frameAt, arcPts };
