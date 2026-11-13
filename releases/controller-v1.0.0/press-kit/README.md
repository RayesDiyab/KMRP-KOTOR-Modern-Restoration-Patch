# KOTOR 1 Native Controller Mod + Xbox HUD 1.0: press kit

Release art for the standalone controller patch, `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`
(id `kmrp-controller`, version 1.0.0): the cover and the pages for mod pages, posts and
articles. Use them as they are; please do not crop a frame out of its page without saying
what it shows.

Eight pages, in the order to show them, each 1920x1080.

| File | What |
| --- | --- |
| [`01-cover.png`](01-cover.png) | Cover: the mod's name, the controllers it supports, what it does |
| [`02-controls-remapping.png`](02-controls-remapping.png) | The original Xbox controls, with the Controller Layout screen's remapping (KMRP 1.6) |
| [`03-xbox-hud.png`](03-xbox-hud.png) | The Xbox-style HUD (KMRP 1.5) |
| [`04-every-menu.png`](04-every-menu.png) | Button prompts on the Inventory, Character and Journal screens (KMRP 1.5) |
| [`05-pazaak.png`](05-pazaak.png) | Pazaak with a pad: the table, the side deck and the wager (KMRP 1.6) |
| [`06-swoop-racing.png`](06-swoop-racing.png) | Swoop racing with a pad (KMRP 1.6) |
| [`07-any-interface.png`](07-any-interface.png) | It works on the game's own interface, a mod's or KMRP's |
| [`08-installing.png`](08-installing.png) | One .kpatch for KOTOR Patch Manager |

## How they were made

- **The pages** are drawn by `tools/build_controller_kit_10.py`
  (`python tools/build_controller_kit_10.py`, or with a page name's start, such as `03`, for
  one page). It uses the KMRP 1.6 kit's look and page builders (`tools/build_release_kit_16.py`):
  the night sky, the crest, polished silver KOTOR, the mod's name in gold and its version in
  cyan, white captions and holo-blue page titles.
- **The frames are KMRP's.** The mod is the same code as KMRP's controller support, and the
  maintainer chose KMRP's controller screenshots for this kit (2026-11-13). Each frame's label
  names the KMRP version it was taken with. KMRP's interface (its layouts and fonts) is what
  surrounds the controller in them; on the game's own interface the same prompts and controls
  appear in the game's own layout.
- **The KMRP 1.6 frames** (pages 02, 05, 06) are the maintainer's 1920x1080 screenshots of
  2026-11-13 in `releases/v1.6.0`.
- **The KMRP 1.5 frames** (pages 03, 04) are the 1.5 kit's sources in
  `build/controller-standalone/shots`, taken on 2026-10-08. They show the controller as it was
  then: 1.6 redrew the button pictures and moved the controls to the original Xbox layout, so
  their buttons and HUD are not exactly this release's.
- **Nothing inside a frame is retouched or cropped:** each frame is the whole screen, scaled
  down.
- **The facts** come from the package's manifest (name, version, supported executables,
  options), [`docs/controller-standalone.md`](../../../docs/controller-standalone.md) and the
  CHANGELOG. The package measured: `dist/controller/KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`,
  2,562,366 bytes, SHA-256 `A6A75486...F889E8`, built 2026-11-13 with KMRP 1.6.0.
