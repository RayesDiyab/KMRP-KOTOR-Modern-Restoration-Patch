# K1 Modern Driver Compatibility

**Turn off grass.** For years that has been the first answer to almost any KOTOR problem, and
it was good advice, because on a modern PC the grass really does tear itself across the sky.

This patch fixes that, and quite a lot else. KOTOR decides how to light the world once, when
it starts, choosing between two methods built for graphics cards of 2003. On most machines
today neither is on offer, so the game quietly falls back to a path that was never finished:
no proper lighting on walls and floors, no reflections on metal or armour, no fog, no soft
shadows, and none of the screen effects. It still runs. It just looks wrong, and a lot of people
have never seen it look right.

This patch rebuilds that lighting using something every modern card does support, and puts
the game back on the paths the developers actually finished. The grass is one of them.

If you play on an NVIDIA card, the lighting has been working for you all along and looking
right: those drivers still carry register combiners, one of the two original methods, and it
does the job properly. It is also an extension from 2001 that no other vendor implements and
that survives on one company's willingness to keep shipping it. This patch moves every card
onto a method that is still current, so there is one path everyone is exercising rather than
one propped up by goodwill.

## The cantina on Taris

![The Taris cantina, without the patch and with it](docs/screenshots/taris-cantina-ANIMATED.webp)

Watch the surfaces rather than the lamps. The light in this room is the same in both frames.
What changes is how things answer it: the metal picks up a sheen, the wall panels are roughed up.
This is the shading model itself arriving, rather than any single feature being switched on, which
is why it is worth looking at closely and why it would vanish at thumbnail size.

## The grass, on Dantooine

![Dantooine grass, without the patch and with it](docs/screenshots/dantooine-grass-ANIMATED.webp)

A comparison of grass' behaviour before and after the patch.

## Before and after

Left half of each image is without the patch, right half is with it. Every "before" is
`decline = on`, which stands the patch aside without uninstalling it. The two marked 
**Intel** are different: their left half is a build with the cube map fix removed, 
which is what an Intel card showed before this existed.

| | |
|---|---|
| ![Dantooine grass](docs/screenshots/dantooine-grass.webp) | **Dantooine.** One of the most grassy scenes in the game. |
| ![The Unknown World beach](docs/screenshots/unknown-world-beach.webp) | **Unknown World beach, same issue.** The beach and the sun behind it are almost entirely hidden. Restored rendering gives the correct appearance, and correctly shows the per-pixel lighting for sunshine. |
| ![Soft shadows on the Unknown World](docs/screenshots/unknown-world-softshadows.webp) | **Shadows.** Soft shadows are now functional for all GPU vendors, you can see them on all surfaces. |
| ![The Kashyyyk Great Walkway](docs/screenshots/kashyyyk-great-walkway.webp) | **Kashyyyk, on the walkway.** The lanterns actually shine on the right, showcasing the frame buffer powered lighting effects. |
| ![The Kashyyyk wilds](docs/screenshots/kashyyyk-wilds.webp) | **Under the trees.** Fog is now consistent and rendering consistently for all vendors. |
| ![The grove waterfall](docs/screenshots/grove-waterfall.webp) | **The waterfall is behind all of that.** Frame buffer effects now properly show the shine of the waterfall in sunlight. |
| ![Water in the grove](docs/screenshots/grove-water.webp) | **The same grove, looking the other way.** Water reflections are now consistent across all vendors, with the animated rendering showing up correctly. |
| ![Water in the grove, Intel against the patch](docs/screenshots/grove-water-vs-intel.webp) | **Intel.** What this scene looked like on an Intel card before the patch existed: the cube map check fails, so reflections fall back to a cruder kind. |
| ![Inside the Ebon Hawk](docs/screenshots/ebon-hawk.webp) | **Ebon Hawk.** The ceiling ring lights the room on the right, and the floor and walls carry where the light falls rather than an even wash. |
| ![Bump lighting on the Hutts in the Taris cantinas](docs/screenshots/bump-lighting-hutts.webp) | **Bump lighting on creatures.** Ajuur above, Zax below. The wet highlight in the eyes is lighting the game only ever drew on a GeForce card, even in a world where an AMD card was working, it would have never gotten this effect. |
| ![Sith armour, Intel against the patch](docs/screenshots/taris-sith-armour-vs-intel.webp) | **Intel.** The armour on the left has no reflection in it. This is the cube map fix, and it is the most obvious place in the game to see it. |

### The same water, three ways

![Water in the grove rendered three ways](docs/screenshots/grove-water-THREE-STATES.webp)

Left is how current AMD cards render water reflections. Middle is an Intel iGPU. Right is
the patch working. Two different faults and one fix, which is easier to follow side by side.

## What you get back

- **Grass that stays on the ground.**
- **Lighting on walls and floors.** The baked lighting that makes interiors look lit rather
  than flat.
- **Reflections** on metal, armour and polished surfaces.
- **Fog**, in the places the game meant to have it.
- **Soft shadows**, and the screen effects: bloom, blur, film grain, the distortion around
  force powers, and the colour wash on some cutscenes.
- **Bump lighting on creatures**, which the game only ever drew on an NVIDIA card. The wet
  highlight in a Hutt's eyes is the easiest place to notice it.

It replaces the separate cube map and soft shadow fixes; both are included. It works with the
GOG, Steam and CD 1.0.3 releases.

> If something looks wrong, `logs/K1DriverCompat.log` in the game folder holds one session,
> and that is the file to send. It is overwritten each run, so there is only ever one.

## Installing

Ships as a `.kpatch` for the [KotOR Patch Manager](https://github.com/LaneDibello/Kotor-Patch-Manager),
**version 0.6.2 or newer**. Your game files are not modified; the manager applies the patch
while the game runs.

**[INSTALLING.md](INSTALLING.md) has the steps**, and ships in the download beside the patch.
It is five steps, plus the two things that most often look like a broken patch and are not.

**If the Patch Manager will not accept your `swkotor.exe`**, because something else has already
modified it, there is a second download that installs without the manager.
[INSTALLING-STANDALONE.md](INSTALLING-STANDALONE.md) has those steps. It copies two files into
your game folder and checks only the eight places it is about to change, so it does not mind
what happened elsewhere. Prefer the managed install wherever it works.

Two files appear in your game folder the first time you run it. `logs/K1DriverCompat.log` is
what to send if something looks wrong, and `K1DriverCompat.ini` holds every setting the patch
has, explained, with all of them switched off. You do not need to touch either to play; see
[Settings](#settings) if you ever want to.

## Two looks, and which one you get

The two kinds of card from 2003 did not draw the game quite identically, and you can choose
which one you get.

```
look = nvidia    the default
look = ati       what a Radeon of the period showed
```

The difference is bright light. On a Radeon, a surface lit past full brightness stayed past
it, so strong lights bleach out what they land on. A GeForce trimmed the brightness back
first, so the same scene looks calmer. Neither is a bug. That is genuinely how the two behaved.

They part in one other place. On bumpy shiny surfaces a Radeon could put a highlight on parts
of a surface angled away from the light, which is easiest to spot on something small and round
like a Hutt's eyes in the Taris cantinas. A GeForce did not. This one is less a matter of taste
than the brightness is, and the default avoids it.

The default is the GeForce behaviour, because it is what most people remember and what mods
have been made to look right against. If you want the Radeon lighting, set `look = ati`.

## Settings

You will not need any of these for normal play. They exist so that if something looks wrong,
you can narrow down what.

**The easy way** is a text file called `K1DriverCompat.ini`, in the same folder as
`swkotor.exe`. **The patch writes one for you the first time it runs**, with every setting
listed and explained and all of them commented out, so open that and delete the `#` in front
of whatever you want to change.

One setting per line:

```
look = ati
log = debug
```

That is the whole format. Blank lines and lines starting with `#` are ignored, capitalisation
does not matter, and if you get a line wrong the rest of the file still works. When the patch
reads it you will see `settings source=K1DriverCompat.ini` near the top of the log, which is
how you can tell it found the file.

**The other way** is environment variables, using the same names with `K1DC_` in front, for
example `K1DC_LOOK=ati`. Where both are set the environment wins, which is handy for trying
something once without editing your file.

If you mistype a value the patch keeps the default and says so in the log, so a typo never
looks like a setting that had no effect.

**Worth knowing about:**

| Switch | What it does |
|---|---|
| `look = ati` | Radeon lighting instead of GeForce. See above. |
| `log = debug` | Write much more detail to the log. This is the one to set if you are reporting a problem. |

**For narrowing down a fault.** Each of these turns part of the patch off, so if the problem
goes away you have found which part owns it:

| Switch | What it does |
|---|---|
| `decline = on` | Stand aside entirely. The game draws as it would without the patch. |
| `framebuffer = off` | Turn off the screen effects and soft shadows, keeping the world lighting. |
| `cubemap = off` | Tell the game reflections are unavailable, so shiny surfaces fall back to a simpler kind. |
| `bump = off` | Tell the game bump lighting is unavailable. |
| `disable_modes = 18,1D` | Stop lighting particular kinds of surface, listed below. |
| `warm = on` | Time how long your driver takes to prepare the lighting recipes. For chasing a stutter. |
| `frames = on` | Report frames per second and how much work the patch did, every few hundred frames. Unset, the patch does not watch frames at all. |

The kinds of surface `disable_modes` accepts, as the log names them under `mode=`:

| | |
|---|---|
| `1A` | the baked lighting on walls and floors, by far the most common |
| `02` | flat coloured surfaces |
| `03` | surfaces that fade toward a colour with distance |
| `13` | reflective surfaces |
| `14` | reflective surfaces that also fade, on the Radeon look only |
| `16` | metallic surfaces, which use three textures at once |
| `18` | surfaces whose bumpiness is stored as a direction map |
| `1D` | sets up the six textures the mode above reads |
| `06`, `07` | bump and shine, in two versions |
| `08` | lightmapped surfaces lit by a bump map light |
| `00` | full reset between draws |
| `0D`, `20`, `25` | tidy up after the bump, reflective and cube texture modes |

Turning any of them off makes the picture wrong where that kind of surface appears, which is
the point: it tells you which kind a fault belongs to.

One caveat on `decline = on`: it is close to the unpatched game but not identical, because
installing the patch also makes a couple of small edits the manager does not undo while it
runs. If you need a true before-and-after, uninstall rather than declining.

## Why the grass exploded

The game has three ways of drawing grass. Two of them are wrong, and it has been picking one
of those.

Drawing anything means telling the graphics card where in memory to find the corner points of
the shapes. Two of the three routes point it at the wrong place: an unused slot that is always
zero, sitting right next to the real one. The card does as it is told. It reads whatever
happens to be lying there and treats those numbers as positions, and since they are not
positions of anything the blades stretch off to wherever the numbers land, which is usually
somewhere near the sky.

The third route points at the right place. The game only takes it if the card reports a
particular graphics feature from 2003, and no card made in the last fifteen years reports it,
so everybody has been getting one of the two broken routes instead.

This patch supplies that feature, so the game takes the good route. That same answer is what
brings back the fog, the screen effects and the soft shadows. None of them were broken so much
as never reached.

<details>
<summary>The precise version</summary>

`RenderGrassPolys` has three draw paths. The two taken when
`aurATIFragmentShadersBumpMapAvailable()` returns false pass `glVertexPointer` the address of
`field_0x40`, a field only ever assigned zero, instead of the allocated blade buffer at
`field_0x38`. So OpenGL reads object fields as vertex coordinates. That check wants
`GL_ATI_fragment_shader`, which this patch answers for, and the path at `0x004A6FFC` passes the
right buffer.
</details>

## How it works

At startup the game asks your graphics card a question, and the answer decides how it draws
everything afterwards. The question is whether the card supports a 2003 feature it no longer
does, so the honest answer is no, and no is what breaks the game.

This patch answers yes, then does the work to make that true. The game's lighting recipes are
rewritten in a modern equivalent, and the patch quietly stands in wherever the game reaches
for the old feature, handing it the new versions instead. There are fifty-seven of them: one
for each kind of surface, times four because fog has to be built into each recipe rather than
added on top, plus nine for the screen effects.

The recipes are not guesswork. They are read out of the game's own program file, and every
build checks them by drawing the game's original and the replacement side by side and
requiring the two pictures to match exactly.

One other thing was rebuilt along the way. The screen effects used to be drawn into a kind of
scratch image from 2001 that modern drivers handle badly and inconsistently, which is why they
misbehaved differently on every machine. They now use the modern equivalent.

Nothing in the patch checks which card you have. It takes over even where the game's own path
still works, so everyone is running the same code, which is the code everyone is testing.

<details>
<summary>The precise version</summary>

The game tests for `GL_ATI_fragment_shader` in `GLRender::InitExtensions`; the patch answers
that hook and clears `GL_NV_register_combiners2` so NVIDIA takes the same arm. All twelve world
shaders and nine effect shaders are translated to `GL_ARB_fragment_program`, the world ones
against each of four fog variants, and the dispatch pointer, vendor entry table and the core
GL imports the path needs are taken over. The translations come from the construction calls in
the executable, and `arbfp-differential` renders the game's own `ATI_fragment_shader` programs
beside them through Mesa and requires pixel equality. The offscreen passes moved from pixel
buffers to framebuffer objects.
</details>

## Replacement shaders

*This section is for people who want to change how the game looks by writing their own
lighting code. If that is not you, you can stop here.*

You can drop your own shader files into the game folder and the patch will use them instead of
the ones it generates, with no rebuilding and no tools. They are plain text in ARB fragment
program assembly, which is what the patch compiles its own into.

**Where.** `override/shaders/` in the game folder. Create it if it is not there.

It sits under `override` so a replacement can ship as an ordinary TSLPatcher mod rather than
needing its own packaging, and in a subdirectory because these are not game resources. The
game ignores them completely: it only looks in `override` for the file extensions it knows,
never recurses into subdirectories, and has no idea what an `.arb` file is. Reading them is
this patch's job.

**Naming.** One file per program, named after the program.

- World shaders take the fog variant as well: `<name>_<fog>.arb`, where fog is `off`,
  `linear`, `exp` or `exp2`.
- Effect shaders are just `<name>.arb`. They shade screen space quads, which fog never
  reaches, so they have no variants.

Case is ignored, so a file named on Linux loads on Windows and the other way round.

```
flat            diffuseBlend    lightmap          envMap2D
envMapCube      envThreeTex2D   envThreeTexCube   envMapBlend2D
envMapBlendCube normalTransform bumpShinyA        bumpShinyB

overbrighten    forceDistortion filmNoise         accumulationBlur
saturation      perPixelFlare   decal             decal4
softShadow
```

These are the names the log prints. Running with `log = debug` reports what the dispatcher
picked for each mode, so a line reading `probe mode=1A shader=lightmap fog=Linear` tells you the
file to write is `lightmap_linear.arb`.

**A file is a complete program**, starting at `!!ARBfp1.0` and ending at `END`. Nothing is
wrapped around it. In particular the fog blend is built into each world variant rather than
added afterwards, which is why there are four variants: a replacement for a fogged one has to
apply the fog itself, or that draw stops fogging.

Three are the exception. `diffuseBlend`, `envMapBlend2D` and `envMapBlendCube` already fade to
the fog colour in their own bodies, the way the game's shaders do, so all four of their variants
are the same program and none carries the blend described here. A replacement for one of those
should leave fog alone, or the surface fades to it twice.

Here is `lightmap_linear.arb` as generated, with the last five instructions being the fog:

```
!!ARBfp1.0
PARAM fogParam = state.fog.params;
PARAM fogColour = state.fog.color;
TEMP fogCoord, fogFactor;
TEMP oCol;
TEMP base, lmap, sum;
TEX base, fragment.texcoord[0], texture[0], 2D;
TEX lmap, fragment.texcoord[1], texture[1], 2D;
ADD sum, fragment.color.primary, lmap;
MUL oCol.rgb, base, sum;
MUL oCol.a, fragment.color.primary, base;
ABS fogCoord.x, fragment.fogcoord.x;
SUB fogFactor.x, fogParam.z, fogCoord.x;
MUL_SAT fogFactor.x, fogFactor.x, fogParam.w;
LRP result.color.rgb, fogFactor.x, oCol, fogColour;
MOV result.color.a, oCol;
END
```

That is the `ati` rendering. Under the default the `ADD` is an `ADD_SAT`, which is the one
instruction that differs in this program.

Four programs differ between the two looks at all. `lightmap`, `envThreeTex2D` and
`envThreeTexCube` each saturate a step that can pass one, which is the brightness difference
the [Two looks](#two-looks-and-which-one-you-get) section describes. `bumpShinyA` differs for
a different reason: it clamps two dot products before they are squared, because an unclamped
negative comes back positive and lights the side of a surface facing away from the light. It
runs on creatures rather than rooms, and the Hutts' eyes in the Taris cantinas are the easiest
place to see the two looks apart.

Every other program is identical under both, so a replacement for one of those is a
replacement for both.

**What your program is handed.** Only the program text changes. The patch still binds the same
textures and sets the same constants it would have.

Those inputs reach an ARB fragment program in two ways. Textures arrive on numbered units,
which you read with `TEX dst, fragment.texcoord[n], texture[n], 2D` (or `CUBE`, or `1D`).
Values the engine computes per draw arrive as `program.env[n]`, which you read but never write.

World programs:

| Program | Texture units | `program.env[n]` |
|---|---|---|
| `flat` | none | none |
| `diffuseBlend` | 0 diffuse | `[1]` colour to blend toward |
| `lightmap` | 0 diffuse, 1 lightmap | none |
| `envMap2D` | 0 diffuse, 1 environment | `[0].a` output alpha |
| `envMapCube` | 0 diffuse, 1 environment (cube) | `[0].a` output alpha |
| `envMapBlend2D` | 0 diffuse, 1 environment | `[0].a` output alpha, `[1]` blend colour |
| `envMapBlendCube` | 0 diffuse, 1 environment (cube) | `[0].a` output alpha, `[1]` blend colour |
| `envThreeTex2D` | 0 diffuse, 1 diffuse again, 2 environment | `[0].a` output alpha |
| `envThreeTexCube` | 0 diffuse, 1 diffuse again, 2 environment (cube) | `[0].a` output alpha |
| `normalTransform` | 0 normal map, 1 to 3 basis (cube), 4 refinement (cube), 5 environment (cube) | `[0].a` output alpha |
| `bumpShinyA` | 0 normal map, 1 to 2 basis (cube), 3 modulating | `[0]`, `[1]` light colours |
| `bumpShinyB` | 0 modulating, 1 normal map, 2 to 3 basis (cube) | `[0]`, `[1]` light colours |

Effect programs, which all shade a quad covering the screen:

| Program | Texture units | `program.env[n]` |
|---|---|---|
| `overbrighten`, `perPixelFlare` | 0 frame, 1 to 3 tone curve tables (**1D**) | `[0]` to `[2]` colour matrix rows |
| `forceDistortion` | 0 normal map, 2 frame | none |
| `filmNoise` | 0 frame, 1 noise | none |
| `accumulationBlur` | 0 frame, 1 accumulation buffer | `[0]`, `[1]` weights |
| `saturation` | 0 frame | `[0]` to `[2]` luminance rows, `[3]` to `[5]` per channel weights |
| `decal` | 0 frame | none |
| `decal4`, `softShadow` | 0 to 3 four taps of the frame | `[0]` to `[3]` tap weights |

A few things that will bite if you go by unit number alone:

- **Name the target that is actually bound.** A `TEX` instruction declares what it is sampling,
  and getting it wrong is not a compile error. The tone curve tables on units 1 to 3 of
  `overbrighten` and `perPixelFlare` are `1D`, not `2D`; declaring `2D` samples an incomplete
  target and several drivers return white. The same applies to every `CUBE` above, which is
  why the environment mapped programs come in `2D` and `Cube` pairs at all.
- **In the diffuse modes, the diffuse texture's own alpha is the reflectivity mask.** 1 keeps
  the lit texel, 0 shows the reflection.
- **`forceDistortion` reads the frame on unit 2, not unit 0.** Unit 0 is the normal map, and
  `fragment.texcoord[1]` and `[2]` are the basis vectors it is dotted against.
- **The interpolated colours are inputs too.** `fragment.color.primary` is the lit vertex
  colour, and `fragment.color.secondary.r` is what the blend modes fade by.

**What the log says.** Every replacement that loaded gets a line at install time:

```
[INFO] program override envMapCube_linear.arb
```

A file the patch does not recognise gets a warning instead. That is what catches a misnamed
replacement, which otherwise looks exactly like one nobody wrote:

```
[WARN] program override envMapCube.arb matches no program and was ignored
```

A replacement the driver refuses is reported with the position it stopped at and the driver's
own complaint. That program then falls back to unshaded rather than to the generated version.

**Traps worth knowing before spending time on one.**

- `overbrighten` never binds. The bright pass always resolves to `perPixelFlare`, so a
  replacement for it will sit there doing nothing.
- `bumpShinyB` doesn't run at all. The game reaches it through one function that is gated on
  another returning true, and that one is compiled to `return false` in every build of the
  game looked at. It is translated and verified against the original, but not reachable. My 
  best guess is that it was intended to be used for art that was scraped, it's unfinished and
  would cause a crash if reached.
- The `exp` and `exp2` fog variants cannot render in shipped content. The area format has no
  fog mode field, so the game never leaves linear.
- `forceDistortion` only appears with a force power on screen.

**These are not the game's own shaders.** They are translations of its `ATI_fragment_shader`
constructions, so they expect this game's stage layout and constants. A program lifted from
KOTOR 2 will compile and render wrong unless its inputs are remapped, because the two games
feed their fragment stage differently.

## Building

*Only needed if you want to change the patch itself. To play, download the `.kpatch`.*

The patch is a 32-bit Windows DLL. Any machine can produce it, natively or cross compiled,
given the Rust target and a linker for it. A machine that does not already supply one needs
MinGW-w64.

```
rustup target add i686-pc-windows-gnu
cargo xtask package          # builds the DLL and writes the .kpatch
```

The shader translations are checked against the game's own shaders, read out of a copy of the
executable at test time. Nothing from the game is stored in this repository, so the tests that
need it skip unless you point them at your own copy:

```
K1DC_SWKOTOR_EXE=/path/to/swkotor.exe cargo test
```

Those tests skip rather than fail on a machine without the game, and **a skipped test reads as
a pass**, so check the count rather than the colour.

This needs no capture and no GPU. Mesa implements `GL_ATI_fragment_shader` on every driver it
ships, right down to the software rasteriser, so the game's own shader and our translation can
be rendered in the same process and compared pixel for pixel.

Every comparison also writes a picture to `target/differential/`, whether it passed or not:
the game's shader, ours, and the difference between them amplified so a single level shows up.
Looking at one of those is usually quicker than reading a number.

Note that the differential compares against the game's own shaders, which is `look = ati`.
That is not the shipped default, so a change touching `lightmap` or either `envThreeTex`
variant wants checking both ways.

## Thanks

**[Lane](https://github.com/LaneDibello)** and **[J](https://github.com/J0-o)**, who tested this on
cards and installs I do not own. Nearly everything here is a claim about how some particular driver
behaves, and a claim like that is worth nothing until somebody with that hardware runs it and reports
back. The faults that turned up that way are ones I had no way of finding on my own, and this would
not have been finishable without them.

Lane also wrote the [KotOR Patch Manager](https://github.com/LaneDibello/Kotor-Patch-Manager), which
is what this ships for.

## LLM Disclosure

This project made use of an LLM during development, in the following capacities:

- **Brainstorming** - exploring possible approaches and design directions
- **Decompilation assistance** - help interpreting and structuring reverse-engineered code
- **Code comments** - refining and clarifying existing comments
- **Skeletons and fixes** - generating initial code scaffolding and minor fixes

All LLM-assisted output was modified and reviewed by a human before being committed.

## Licence

MPL-2.0. See `LICENSE`.
