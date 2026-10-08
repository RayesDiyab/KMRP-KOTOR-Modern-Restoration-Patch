'use strict';
// node render.js [--size 512] [--out DIR] [icon ...]      (no names: every icon that has a drawing)
// Draws each icon by its function in drawn/*.js into <out>/<sheet>/<icon>.png (transparent, straight alpha).
// sheets.json says which sheet an icon belongs to. No dependencies beyond Node.
const fs = require('fs');
const path = require('path');
const kit = require('./kit');

const args = process.argv.slice(2);
let size = 512, out = path.join(__dirname, '..', 'icons'), names = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--size') size = parseInt(args[++i], 10);
  else if (args[i] === '--out') out = args[++i];
  else names.push(args[i]);
}
const sheets = JSON.parse(fs.readFileSync(path.join(__dirname, 'sheets.json'), 'utf8'));
const drawn = {};
for (const f of fs.readdirSync(path.join(__dirname, 'drawn')).filter((x) => x.endsWith('.js'))) {
  try { Object.assign(drawn, require(path.join(__dirname, 'drawn', f))); } catch (e) { console.log('NOT LOADED drawn/' + f + ': ' + String(e.stack || e).split('\n').slice(0, 2).join(' | ')); }
}
if (!names.length) names = Object.keys(drawn).sort();
let failed = 0;
for (const name of names) {
  if (!drawn[name]) { console.log('no drawing for ' + name); failed++; continue; }
  const c = new kit.P.Canvas(size, 32);
  try {
    // "Not ready" is an opaque black square in the game: the square first
    if (name === 'i_notready') c.fill(kit.S.box(16, 16, 16.5, 16.5), kit.P.flat(kit.C.black));
    drawn[name](c, kit);
    const dir = path.join(out, sheets[name] || '_other');
    fs.mkdirSync(dir, { recursive: true });
    c.save(path.join(dir, name + '.png'));
  } catch (e) { console.log('FAILED ' + name + ': ' + String(e.stack || e).split('\n').slice(0, 3).join(' | ')); failed++; }
}
console.log(names.length - failed + ' of ' + names.length + ' drawn at ' + size + ' px');
process.exitCode = failed ? 1 : 0;
