# HD icons, redrawn from scratch

Work in progress. Nothing here is installed by KMRP yet: this folder holds the
finished icons so far and the program that draws them.

The game's feat, power and skill symbols are 32 x 32 (a few 64 x 64) pixels.
Each one is redrawn here as a small JavaScript program that constructs the
picture from geometry: straight lines, circular arcs, exact circles, sharp or
rounded corners, and shading given as formulas. The result is rendered at
512 x 512 with a transparent background and can be rendered at any other size.
No picture is traced or upscaled.

## What is here

| Path | Contents |
| --- | --- |
| `icons/symbol_flat_sharp/` | 34 combat symbols (attack, two-weapon fighting, duelling, flurry, critical strike, power attack, power shot, rapid shot, lightsaber throw, lightning, jump, speed, slow, suppress). Reviewed. |
| `icons/symbol_head_profile/` | 28 symbols built on the head in profile (mind, cautious, dialog, sense, stealth, stealth mode, sneak attack I to X). Reviewed. |
| `source/` | The program: one function per icon in `drawn/`, shared parts in `parts/`, the drawing library in `lib/`. |
| `source/tools/` | The measuring tools used while drawing (Python). |

File names are the game's own texture names (`i_attack`, `ip_mind`, ...).

`source/drawn/` also holds drawings for sheets that have not been reviewed yet
(round symbols, front busts, badges, objects, teal plates). They render, but
they are not finished and their pictures are not in `icons/`.

## How an icon is made

1. **Read the game's icon.** Its pixels decide what the icon is: the outline,
   the proportions, what lies in front of what, where each colour is.
   `tools/vmap.py` prints an icon as text, pixel for pixel.
2. **Measure.** Lengths, angles, radii, centres and colours are taken with the
   tools and written into the drawing as comments. An AI redraw of each sheet
   served only as a hint for what a blurred shape is meant to be.
3. **Construct.** The icon is built from primitives: `lib/sdf.js` (shapes as
   signed distance functions), `lib/geom.js` (a polygon moved out with sharp
   corners, a line of one width with sharp joints, rounded corners) and
   `lib/paint.js` (a canvas that composites in linear light, with edges
   anti-aliased from the distance itself).
4. **Compare and correct** against the game's icon at high zoom, then by eye.

Rules the drawings follow:

- Straight lines are exactly straight and circles exactly round.
- One object is one body; a black border is whole and of one width, or absent.
- Objects that touch get all their borders first and then their bodies, so no
  border cuts into a neighbour.
- Where the game's 32-pixel frame cut a shape flat, the shape is drawn whole
  and the icon is made a little smaller to fit.
- Shading is soft and structural only: a colour that deepens to the edge of its
  shape, glows that fall off smoothly. No detail the game's icon does not show.

## Rendering

Node is the only requirement.

```bash
node source/render.js
```

draws every icon that has a drawing into `icons/<sheet>/<icon>.png`.

```bash
node source/render.js --size 256 --out some/folder i_attack ip_mind
```

draws the named icons at another size into another folder.

## The measuring tools

The tools in `source/tools/` read the game's own icons and the AI redraws from
a working folder outside this repository (`C:\ComfyUI\kotor`), which is not
part of KMRP: the game's textures are proprietary and are not committed. The
tools are kept here as a record of the method; to run them, extract the icons
from your own copy of the game and point the paths at the top of each script at
them.
