'use strict';
// The painter: shapes (signed distance functions) are laid on a canvas with shaders.
//
// Edges are anti-aliased from the distance itself: a pixel is covered by clamp(0.5 - d * pixels per unit), which is
// one pixel wide at whatever size is rendered. Colours are mixed in linear light (sRGB decoded, blended, encoded):
// mixed as stored values, the pixels along an edge between two colours come out too dark.
// A shader is a function (px) -> writes px.r, px.g, px.b (sRGB 0..1) and px.a (0..1) for the pixel described by px:
//   px.x, px.y   the place, in units          px.d    the distance to the shape's edge there (negative inside)
//   px.gx, px.gy the direction away from the nearest edge (the gradient of d, unit length)

const zlib = require('zlib');
const fs = require('fs');
const { clamp, mix } = require('./sdf');

const toLinear = (v) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
const toSRGB = (v) => (v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055);
const hex = (h) => { const n = parseInt(h.replace('#', ''), 16); return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; };
const rgb = (c) => (typeof c === 'string' ? hex(c) : c);

// a colour ramp: stops = [[t, colour], ...] with t rising; mixed in linear light
const ramp = (stops) => {
  const ts = stops.map((s) => s[0]), cs = stops.map((s) => rgb(s[1]).map(toLinear));
  return (t, out) => {
    let i = 0;
    while (i < ts.length - 2 && t > ts[i + 1]) i++;
    const f = clamp((t - ts[i]) / (ts[i + 1] - ts[i] || 1e-9), 0, 1), a = cs[i], b = cs[i + 1];
    out.r = toSRGB(mix(a[0], b[0], f)); out.g = toSRGB(mix(a[1], b[1], f)); out.b = toSRGB(mix(a[2], b[2], f));
  };
};

// ---- shaders -----------------------------------------------------------------------------------------------------
const flat = (colour, alpha = 1) => { const c = rgb(colour); return (px) => { px.r = c[0]; px.g = c[1]; px.b = c[2]; px.a = alpha; }; };
// a ramp along the line from (x0, y0) to (x1, y1)
const linear = (x0, y0, x1, y1, stops, alpha = 1) => {
  const r = ramp(stops), ex = x1 - x0, ey = y1 - y0, ee = ex * ex + ey * ey || 1e-9;
  return (px) => { r(clamp(((px.x - x0) * ex + (px.y - y0) * ey) / ee, 0, 1), px); px.a = alpha; };
};
// a ramp from the centre (t = 0) out to radius r1 (t = 1)
const radial = (cx, cy, r1, stops, alpha = 1) => {
  const r = ramp(stops);
  return (px) => { r(clamp(Math.hypot(px.x - cx, px.y - cy) / r1, 0, 1), px); px.a = alpha; };
};
// a ramp by depth inside the shape: t = 0 at the edge, 1 at `depth` units in
const byDepth = (depth, stops, alpha = 1) => { const r = ramp(stops); return (px) => { r(clamp(-px.d / depth, 0, 1), px); px.a = alpha; }; };
// The form shader. The shape is treated as a cushion: its surface rises from the edge over `depth` units along a
// quarter circle and is flat beyond. The surface normal follows from the distance field's gradient; lit from
// `light` (a direction, z towards the viewer) it gives a shade 0..1 that picks the colour off `stops`, plus a
// highlight of strength `gloss` and tightness `shine`.
const form = ({ stops, depth = 3, light = [-0.45, -0.6, 0.66], gloss = 0, shine = 24, ambient = 0.35, alpha = 1 }) => {
  const r = ramp(stops), ll = Math.hypot(...light), lx = light[0] / ll, ly = light[1] / ll, lz = light[2] / ll;
  const hl = Math.hypot(lx, ly, lz + 1), hx = lx / hl, hy = ly / hl, hz = (lz + 1) / hl;
  return (px) => {
    const t = clamp(-px.d / depth, 0, 1), u = 1 - t;                 // u = 1 at the edge, 0 on the flat
    const slope = u / Math.sqrt(Math.max(1 - u * u, 1e-4));          // the cushion's steepness there
    let nx = px.gx * slope, ny = px.gy * slope, nz = 1;
    const nl = Math.hypot(nx, ny, nz); nx /= nl; ny /= nl; nz /= nl;
    const diffuse = Math.max(nx * lx + ny * ly + nz * lz, 0);
    r(clamp(ambient + (1 - ambient) * diffuse, 0, 1), px);
    if (gloss > 0) {
      const s = gloss * Math.pow(Math.max(nx * hx + ny * hy + nz * hz, 0), shine);
      px.r = mix(px.r, 1, s); px.g = mix(px.g, 1, s); px.b = mix(px.b, 1, s);
    }
    px.a = alpha;
  };
};
// any shader with another laid over it through its own alpha
const over = (below, above) => (px) => {
  below(px); const r = px.r, g = px.g, b = px.b, a = px.a;
  above(px); const k = px.a;
  px.r = mix(r, px.r, k); px.g = mix(g, px.g, k); px.b = mix(b, px.b, k); px.a = a + (1 - a) * k;
};
// a shader with a light line laid along the inside of the shape's edge: full strength at the edge, gone `width` in
// The light is at full strength for `core` units from the edge (a crisp line) and dies away over `width` beyond that.
const rimmed = (shader, { colour = '#ffffff', width = 0.7, strength = 0.85, core = 0 } = {}) => {
  const c = rgb(colour);
  return (px) => {
    shader(px);
    const t = Math.max(-px.d - core, 0) / width;
    if (t > 3) return;
    const s = strength * Math.exp(-t * t * 2.2);
    px.r = mix(px.r, c[0], s); px.g = mix(px.g, c[1], s); px.b = mix(px.b, c[2], s);
  };
};
// a shader darkened (or lightened, with a light colour) towards one side: t runs along (x0, y0) -> (x1, y1)
const graded = (shader, x0, y0, x1, y1, colour, strength = 0.5) => {
  const c = rgb(colour), ex = x1 - x0, ey = y1 - y0, ee = ex * ex + ey * ey || 1e-9;
  return (px) => {
    shader(px);
    const s = strength * clamp(((px.x - x0) * ex + (px.y - y0) * ey) / ee, 0, 1);
    px.r = mix(px.r, c[0], s); px.g = mix(px.g, c[1], s); px.b = mix(px.b, c[2], s);
  };
};

// ---- heights for reliefs: (x, y, d) -> how high the surface stands there, in units ----------------------------------
// a cushion: rises from the shape's edge over `depth` units along a quarter circle to `rise`, flat beyond
const cushion = (depth, rise = depth) => (x, y, d) => { const u = 1 - clamp(-d / depth, 0, 1); return rise * Math.sqrt(1 - u * u); };
// a rounded hill at (cx, cy): rise * exp(-(r / radius)^2), stretched by (sx, sy) and turned by `turn` degrees
const hill = (cx, cy, radius, rise, sx = 1, sy = 1, turn = 0) => {
  const c = Math.cos((turn * Math.PI) / 180), s = Math.sin((turn * Math.PI) / 180);
  return (x, y) => { const px = x - cx, py = y - cy, u = (px * c + py * s) / sx, v = (-px * s + py * c) / sy; return rise * Math.exp(-(u * u + v * v) / (radius * radius)); };
};
// heights added together
const sum = (...hs) => (x, y, d) => { let h = 0; for (let i = 0; i < hs.length; i++) h += hs[i](x, y, d); return h; };

// a Gaussian blur of a square field (sigma in pixels), edges held
const blur = (src, S, sigma) => {
  const r = Math.max(1, Math.ceil(sigma * 2.5)), w = new Float32Array(2 * r + 1);
  let tot = 0;
  for (let i = -r; i <= r; i++) { w[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); tot += w[i + r]; }
  for (let i = 0; i < w.length; i++) w[i] /= tot;
  const tmp = new Float32Array(S * S), out = new Float32Array(S * S);
  for (let j = 0; j < S; j++) for (let n = 0; n < S; n++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * src[j * S + clamp(n + t, 0, S - 1)]; tmp[j * S + n] = a; }
  for (let j = 0; j < S; j++) for (let n = 0; n < S; n++) { let a = 0; for (let t = -r; t <= r; t++) a += w[t + r] * tmp[clamp(j + t, 0, S - 1) * S + n]; out[j * S + n] = a; }
  return out;
};

// ---- the canvas --------------------------------------------------------------------------------------------------
class Canvas {
  constructor(size = 512, units = 32) {
    this.size = size; this.units = units; this.k = size / units;       // pixels per unit
    this.buf = new Float32Array(size * size * 4);                      // linear light, premultiplied by alpha
    this.fields = new Map();
  }
  // the shape's distances over the whole canvas, in units (kept: a shape used twice is computed once)
  field(shape) {
    let f = this.fields.get(shape);
    if (f) return f;
    const S = this.size, k = this.k; f = new Float32Array(S * S);
    for (let j = 0, i = 0; j < S; j++) { const y = (j + 0.5) / k; for (let n = 0; n < S; n++, i++) f[i] = shape((n + 0.5) / k, y); }
    this.fields.set(shape, f);
    return f;
  }
  _lay(f, shader, coverage) {
    const S = this.size, k = this.k, buf = this.buf, px = { x: 0, y: 0, d: 0, gx: 0, gy: 0, r: 0, g: 0, b: 0, a: 1 };
    for (let j = 0, i = 0; j < S; j++) {
      for (let n = 0; n < S; n++, i++) {
        const d = f[i], cov = coverage(d, k);
        if (cov <= 0) continue;
        let gx = (f[n < S - 1 ? i + 1 : i] - f[n > 0 ? i - 1 : i]), gy = (f[j < S - 1 ? i + S : i] - f[j > 0 ? i - S : i]);
        const gl = Math.hypot(gx, gy) || 1; gx /= gl; gy /= gl;
        px.x = (n + 0.5) / k; px.y = (j + 0.5) / k; px.d = d; px.gx = gx; px.gy = gy; px.i = i;
        shader(px);
        const a = clamp(px.a, 0, 1) * cov, o = i * 4, q = 1 - a;
        buf[o] = toLinear(clamp(px.r, 0, 1)) * a + buf[o] * q;
        buf[o + 1] = toLinear(clamp(px.g, 0, 1)) * a + buf[o + 1] * q;
        buf[o + 2] = toLinear(clamp(px.b, 0, 1)) * a + buf[o + 2] * q;
        buf[o + 3] = a + buf[o + 3] * q;
      }
    }
    return this;
  }
  // the shape filled with a shader (a colour is a flat shader); grown by `grow` units if given
  fill(shape, shader, grow = 0) {
    let f = this.field(shape);
    if (grow) { const g = new Float32Array(f.length); for (let i = 0; i < f.length; i++) g[i] = f[i] - grow; f = g; }
    return this._lay(f, typeof shader === 'function' ? shader : flat(shader), (d, k) => clamp(0.5 - d * k, 0, 1));
  }
  // a glow round the shape: strongest at its edge, falling off as exp(-(d / reach)^2) outside (and solid inside)
  glow(shape, colour, reach, strength = 1) {
    const c = flat(colour);
    return this._lay(this.field(shape), (px) => { c(px); const d = Math.max(px.d, 0) / reach; px.a = strength * Math.exp(-d * d); }, () => 1);
  }
  // a shadow / dark halo inside the shape along its edge: strongest at the edge, gone at `reach` units in
  shade(shape, colour, reach, strength = 1) {
    const c = flat(colour);
    return this._lay(this.field(shape), (px) => { c(px); const t = clamp(-px.d / reach, 0, 1); px.a = strength * (1 - t) * (1 - t); }, (d, k) => clamp(0.5 - d * k, 0, 1));
  }
  // the line of width w along the shape's edge (centred on it; `shift` moves it in (negative) or out)
  stroke(shape, w, shader, shift = 0) {
    const f = this.field(shape), g = new Float32Array(f.length);
    for (let i = 0; i < f.length; i++) g[i] = Math.abs(f[i] - shift) - w / 2;
    return this._lay(g, typeof shader === 'function' ? shader : flat(shader), (d, k) => clamp(0.5 - d * k, 0, 1));
  }
  // A relief: the shape as a lit surface. height(x, y, d) gives how high the surface stands (units). The normal is
  // taken from the heights over the canvas; lit from `light` it picks a colour off `stops` (0 = unlit, 1 = fully lit),
  // with a highlight of strength `gloss`. `rim` lays a light line along the inside of the edge.
  relief(shape, { height, stops, light = [-0.42, -0.62, 0.66], glossLight = null, ambient = 0.3, gloss = 0, shine = 28, rim = null, alpha = 1, tone = null, soften = 0.35 }) {
    const S = this.size, k = this.k, f = this.field(shape);
    let H = new Float32Array(S * S);
    for (let j = 0, i = 0; j < S; j++) { const y = (j + 0.5) / k; for (let n = 0; n < S; n++, i++) H[i] = f[i] < 4 / k ? height((n + 0.5) / k, y, Math.min(f[i], 0)) : 0; }
    if (soften > 0) H = blur(H, S, soften * k);      // the creases where two slopes of a cushion meet are rounded off
    const r = ramp(stops), ll = Math.hypot(...light), lx = light[0] / ll, ly = light[1] / ll, lz = light[2] / ll;
    const g = glossLight || light, gl = Math.hypot(...g), gx = g[0] / gl, gy = g[1] / gl, gz = g[2] / gl;
    const hl = Math.hypot(gx, gy, gz + 1), hx = gx / hl, hy = gy / hl, hz = (gz + 1) / hl;
    let shader = (px) => {
      const i = px.i, n = i % S, j = (i - n) / S;
      let nx = -(H[n < S - 1 ? i + 1 : i] - H[n > 0 ? i - 1 : i]) * k * 0.5, ny = -(H[j < S - 1 ? i + S : i] - H[j > 0 ? i - S : i]) * k * 0.5, nz = 1;
      const nl = Math.hypot(nx, ny, nz); nx /= nl; ny /= nl; nz /= nl;
      const diffuse = Math.max(nx * lx + ny * ly + nz * lz, 0);
      r(clamp(ambient + (1 - ambient) * diffuse, 0, 1), px);
      if (gloss > 0) { const s = gloss * Math.pow(Math.max(nx * hx + ny * hy + nz * hz, 0), shine); px.r = mix(px.r, 1, s); px.g = mix(px.g, 1, s); px.b = mix(px.b, 1, s); }
      if (tone) tone(px);
      px.a = alpha;
    };
    if (rim) shader = rimmed(shader, rim);
    return this._lay(f, shader, (d, kk) => clamp(0.5 - d * kk, 0, 1));
  }
  // An airbrushed spot: colour at strength * exp(-r^2), r measured in the spot's own radii (rx, ry), turned by `turn`
  // degrees. With a mask it stays inside that shape. For soft lights and shadows on a body.
  blob(cx, cy, rx, ry, colour, strength = 1, { mask = null, turn = 0 } = {}) {
    const S = this.size, k = this.k, buf = this.buf, c = rgb(colour).map(toLinear), m = mask ? this.field(mask) : null;
    const co = Math.cos((turn * Math.PI) / 180), si = Math.sin((turn * Math.PI) / 180), reach = 2.6 * Math.max(rx, ry);
    const j0 = Math.max(0, Math.floor((cy - reach) * k)), j1 = Math.min(S, Math.ceil((cy + reach) * k));
    const n0 = Math.max(0, Math.floor((cx - reach) * k)), n1 = Math.min(S, Math.ceil((cx + reach) * k));
    for (let j = j0; j < j1; j++) {
      for (let n = n0; n < n1; n++) {
        const px = (n + 0.5) / k - cx, py = (j + 0.5) / k - cy, u = (px * co + py * si) / rx, v = (-px * si + py * co) / ry;
        let a = strength * Math.exp(-(u * u + v * v));
        const i = j * S + n;
        if (m) a *= clamp(0.5 - m[i] * k, 0, 1);
        if (a <= 0.002) continue;
        const o = i * 4, q = 1 - a;
        buf[o] = c[0] * a + buf[o] * q; buf[o + 1] = c[1] * a + buf[o + 1] * q; buf[o + 2] = c[2] * a + buf[o + 2] * q; buf[o + 3] = a + buf[o + 3] * q;
      }
    }
    return this;
  }
  // Draw on a sheet of its own, then lay that over the canvas: at strength `alpha`, and only inside `mask` if given.
  layer(draw, { alpha = 1, mask = null } = {}) {
    const top = new Canvas(this.size, this.units);
    draw(top);
    const S = this.size, k = this.k, a = this.buf, b = top.buf, m = mask ? this.field(mask) : null;
    for (let i = 0, o = 0; i < S * S; i++, o += 4) {
      let w = alpha;
      if (m) w *= clamp(0.5 - m[i] * k, 0, 1);
      const ta = b[o + 3] * w;
      if (ta <= 0) continue;
      const q = 1 - ta;
      a[o] = b[o] * w + a[o] * q; a[o + 1] = b[o + 1] * w + a[o + 1] * q; a[o + 2] = b[o + 2] * w + a[o + 2] * q; a[o + 3] = ta + a[o + 3] * q;
    }
    return this;
  }
  // make everything outside the shape clear (a hard clip of what has been drawn so far)
  clip(shape) {
    const f = this.field(shape), k = this.k, a = this.buf;
    for (let i = 0, o = 0; i < f.length; i++, o += 4) { const w = clamp(0.5 - f[i] * k, 0, 1); if (w < 1) { a[o] *= w; a[o + 1] *= w; a[o + 2] *= w; a[o + 3] *= w; } }
    return this;
  }
  // make everything outside ALL of the shapes clear (what lies in any one of them stays)
  clipAny(shapes) {
    const k = this.k, a = this.buf, fields = shapes.map((s) => this.field(s)), n = this.size * this.size;
    for (let i = 0, o = 0; i < n; i++, o += 4) {
      // the shapes' coverages are added (two shapes that share an edge each cover half of a pixel on it: together all)
      let w = 0;
      for (let f = 0; f < fields.length && w < 1; f++) w += clamp(0.5 - fields[f][i] * k, 0, 1);
      if (w < 1) { a[o] *= w; a[o + 1] *= w; a[o + 2] *= w; a[o + 3] *= w; }
    }
    return this;
  }
  // a whole-frame layer given as a fitted surface of premultiplied colour and opacity: laid over what is there
  wash(sample) {
    const S = this.size, k = this.k, buf = this.buf, v = [0, 0, 0, 0];
    for (let j = 0, o = 0; j < S; j++) {
      for (let n = 0; n < S; n++, o += 4) {
        sample((n + 0.5) / k, (j + 0.5) / k, v);
        const a = clamp(v[3] / 255, 0, 1);
        if (a <= 0.004) continue;
        const q = 1 - a;                                         // v[0..2] are sRGB values times opacity
        buf[o] = toLinear(clamp(v[0] / 255 / a, 0, 1)) * a + buf[o] * q; buf[o + 1] = toLinear(clamp(v[1] / 255 / a, 0, 1)) * a + buf[o + 1] * q;
        buf[o + 2] = toLinear(clamp(v[2] / 255 / a, 0, 1)) * a + buf[o + 2] * q; buf[o + 3] = a + buf[o + 3] * q;
      }
    }
    return this;
  }
  // straight-alpha sRGB bytes
  bytes() {
    const S = this.size, out = Buffer.alloc(S * S * 4), buf = this.buf;
    for (let i = 0, o = 0; i < S * S; i++, o += 4) {
      const a = buf[o + 3];
      if (a <= 1e-5) continue;
      out[o] = Math.round(clamp(toSRGB(buf[o] / a), 0, 1) * 255); out[o + 1] = Math.round(clamp(toSRGB(buf[o + 1] / a), 0, 1) * 255);
      out[o + 2] = Math.round(clamp(toSRGB(buf[o + 2] / a), 0, 1) * 255); out[o + 3] = Math.round(clamp(a, 0, 1) * 255);
    }
    return out;
  }
  save(file) { fs.writeFileSync(file, png(this.size, this.size, this.bytes())); return this; }
}

// a PNG file (RGBA, 8 bits) from raw bytes
const crcTable = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc = (b) => { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = crcTable[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const body = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(body)); return Buffer.concat([len, body, c]); };
const png = (w, h, rgba) => {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 4 + 1)] = 0; rgba.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4); }
  const head = Buffer.alloc(13); head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', head), chunk('IDAT', zlib.deflateSync(raw, { level: 9 })), chunk('IEND', Buffer.alloc(0))]);
};

module.exports = { Canvas, flat, linear, radial, byDepth, form, over, rimmed, graded, cushion, hill, sum, ramp, hex, png, toLinear, toSRGB };
