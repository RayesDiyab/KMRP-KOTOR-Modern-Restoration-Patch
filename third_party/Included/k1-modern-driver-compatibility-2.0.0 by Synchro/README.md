# K1 Modern Driver Compatibility

K1 Modern Driver Compatibility is a patch for *Star Wars: Knights of the Old Republic* that
restores the game's full lighting on current graphics drivers, and stops the grass from
stretching into the sky.

For years, "turn off grass" has been the first advice for almost any KOTOR problem. On many
current PCs, the grass draws as long streaks from the ground to the sky. This patch fixes that,
and the cause behind it.

## Why the game looks wrong

KOTOR supports two ways of shading each pixel, one from ATI and one from NVIDIA, and chooses
between them when it starts. AMD's and Intel's Windows drivers offer neither, so on those drivers
the game uses the path it has for cards without per-pixel shading. On that path:

- Lightmapped walls and floors show only their stored lighting, and the lights in the room don't
  reach them.
- Creatures and surfaces have no bump lighting.
- Shiny surfaces lose most of their reflection.
- In some places, the distance doesn't fade into the fog.
- There are no soft shadows and no screen effects.
- The grass draws from the wrong place in memory.

NVIDIA's drivers still offer NVIDIA's method, and Mesa, on Linux, still offers ATI's, so on
those drivers the unpatched game already uses a shaded path. However, each of those methods
depends on one vendor or project continuing to support it. The patch rebuilds the game's
lighting on `GL_ARB_fragment_program`, which AMD's, Intel's, and NVIDIA's drivers and Mesa all
carry, and puts every card on that one path.

## Grass and fog on Kashyyyk

| Without the patch | With the patch |
|---|---|
| ![The Lower Shadowlands on Kashyyyk, distant fog and grass are rendered incorrectly and missing.](docs/screenshots/kashyyyk-grass-without.webp) | ![The same location, with grass covering the ground, and the distant fog rendering correctly.](docs/screenshots/kashyyyk-grass-with.webp) |

*The Lower Shadowlands. Without the patch, no grass is drawn, and the distant fog doesn't blend properly.*

## The crystal cave on Dantooine

| Without the patch | With the patch |
|---|---|
| ![The crystal cave on Dantooine, crystals are missing their textures and glow.](docs/screenshots/crystals-without.webp) | ![The same cave, with the crystals rendering properly.](docs/screenshots/crystals-with.webp) |

*The crystal cave on Dantooine. With the patch, the crystals render properly and glow again.*

## What the patch restores

- **Grass that stays on the ground.**
- **Light on lightmapped walls and floors.** The lights in the room add to the stored lighting.
- **Reflections** on metal, armour, and polished surfaces, including cube map reflections on
  Intel cards.
- **Fog**, in the places the game meant to have it.
- **Soft shadows and screen effects:** glow, motion blur, film grain, and the distortion around
  Force powers.
- **Bump lighting on creatures**, which the game drew only on NVIDIA cards. The folds of a Hutt's
  skin, most of all along the tail, are the easiest place to see it.
- **Glow and soft shadows that hold still.** In the unpatched game, the glow around lights and
  the edges of soft shadows flicker as the camera moves, more at higher resolutions.
- **A brightness slider that works.** The game asks the display to apply brightness, and a
  driver can refuse; NVIDIA's Windows driver does. The patch applies brightness to the picture
  instead, including in cutscenes.
- **Rendering the game never ran, for mods:** normal mapped surfaces, bump lighting on
  lightmapped surfaces, and reflective skins with a flat reflection map. The game switched off or
  broke each of these on every card.

[What the patch fixes][what-it-fixes] shows each of these with comparison images.

The patch includes the separate cube map fix and soft shadow fix. It works with version 1.03 of
the game as GOG and Steam ship it, and with the `1.03` executable that CD copies run with the
common no-CD crack.

If something looks wrong,
[open an issue](https://codeberg.org/Synchro/kotor-modern-driver-compatibility/issues) and attach
`logs/K1DriverCompat.log` from the game folder. The log records one session, and the patch
replaces it each time the game starts.

## Installing

Download the patch from the
[releases page](https://codeberg.org/Synchro/kotor-modern-driver-compatibility/releases). It's a
`.kpatch` file for the
[KotOR Patch Manager](https://github.com/LaneDibello/Kotor-Patch-Manager), version 0.7.2 or
later. The patch doesn't change `swkotor.exe` on disk: the Patch Manager applies it to the game
as it starts.

- To install with the Patch Manager, follow [the install guide](https://synchro.codeberg.page/kotor-modern-driver-compatibility/installing.html). The
  download includes the same guide as `INSTALLING.md`.
- If the Patch Manager doesn't accept your `swkotor.exe` because another tool has modified it,
  use the standalone download and follow
  [the standalone install guide](https://synchro.codeberg.page/kotor-modern-driver-compatibility/installing-standalone.html). That download includes the
  guide as `INSTALLING-STANDALONE.md`. Use the standard install wherever it works.

## Documentation

The rest of the documentation is [online][book], one chapter for each topic. Its source is in
[the docs folder][docs].

- [What the patch fixes][what-it-fixes]: each fix, with comparison images.
- [Choose between the two looks][looks]: GeForce or Radeon lighting.
- [Settings][settings]: every setting in `K1DriverCompat.ini`, and how to use them to find a fault.
- [Why the game looked wrong][why-it-looked-wrong]: the game's two shading methods, and the grass bug.
- [How the patch works][how-it-works]: what the patch changes, and how its programs are tested.
- [Replacement shaders][replacement-shaders]: write your own shading programs.
- [Building][building]: build the patch and run its tests.

[docs]: https://codeberg.org/Synchro/kotor-modern-driver-compatibility/src/branch/main/docs
[book]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/
[what-it-fixes]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/what-it-fixes.html
[looks]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/looks.html
[settings]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/settings.html
[why-it-looked-wrong]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/why-it-looked-wrong.html
[how-it-works]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/how-it-works.html
[replacement-shaders]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/replacement-shaders.html
[building]: https://synchro.codeberg.page/kotor-modern-driver-compatibility/building.html

## Thanks

**[Lane](https://github.com/LaneDibello)** and **[J](https://github.com/J0-o)**, who tested this on
cards and installs I do not own. Nearly everything here is a claim about how some particular driver
behaves, and a claim like that is worth nothing until somebody with that hardware runs it and reports
back. The faults that turned up that way are ones I had no way of finding on my own, and this would
not have been finishable without them.

Lane also wrote the [KotOR Patch Manager](https://github.com/LaneDibello/Kotor-Patch-Manager), which
is what this ships for.

**[Vriff](https://github.com/vrifftech)**, who took reference screenshots on period-correct
hardware. They show what the game looked like on the cards it was written for, which is what the
patch strives to adhere to.

## LLM Disclosure

This project made use of an LLM during development, in the following capacities:

- **Brainstorming** - exploring possible approaches and design directions
- **Decompilation assistance** - help interpreting and structuring reverse-engineered code
- **Code comments** - refining and clarifying existing comments
- **Skeletons and fixes** - generating initial code scaffolding and minor fixes

All LLM-assisted output was modified and reviewed by a human before being committed.

## Licence

MPL-2.0. See `LICENSE`.
