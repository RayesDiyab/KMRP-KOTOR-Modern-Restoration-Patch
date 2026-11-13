# KMRP 1.6 press kit

Release art for KMRP 1.6 (Windows, Linux and macOS): the cover and the pages for mod
pages, posts and articles. Use them as they are; please do not crop a frame out of its
page without saying what it shows.

Twelve pages, in the order to show them, each 1920x1080.

| File | What |
| --- | --- |
| [`01-cover.png`](01-cover.png) | Cover: KMRP 1.6, its headline features, Windows, Linux and macOS |
| [`02-controller-xbox-controls.png`](02-controller-xbox-controls.png) | Controller: the original Xbox controls, with the Controller Layout screen's remapping, 1920x1080 |
| [`03-controller-layout.png`](03-controller-layout.png) | The Controller Layout screen with the Xbox layout, Default and Remap, 3440x1440 |
| [`04-pazaak.png`](04-pazaak.png) | Pazaak with a pad: the table, the side deck and the wager, 1920x1080 |
| [`05-swoop-racing.png`](05-swoop-racing.png) | Swoop racing with a pad, 1920x1080 |
| [`06-text-hud-icon-size.png`](06-text-hud-icon-size.png) | Text Size and Font (with Icon Size), and HUD Size for mouse and keyboard and for a controller, 1920x1080 |
| [`07-live-adaptive-layout.png`](07-live-adaptive-layout.png) | Live Adaptive Layout: the menus laid out as the game runs |
| [`08-inventory-1080p.png`](08-inventory-1080p.png) | Inventory: the original game at 1280x960 beside KMRP at 1920x1080 (1.5 frames) |
| [`09-inventory-ultrawide.png`](09-inventory-ultrawide.png) | Inventory, ultrawide: the original at 1600x1200 above KMRP at 3440x1440 (1.5 frames) |
| [`10-4k.png`](10-4k.png) | 4K: in the game, 3840x2160 (a 1.5 frame) |
| [`11-installing.png`](11-installing.png) | Installing: the installer's size and what it does |
| [`12-platforms.png`](12-platforms.png) | Platforms: Windows, Linux and macOS |

## How they were made

- **The pages** are drawn by `tools/build_release_kit_16.py` (`python tools/build_release_kit_16.py`,
  or with a page name's start, such as `03`, for one page). The look was settled by the
  maintainer on 2026-11-13: a night sky of mixed stars, the crest's blue glow, thin red and
  orange smoke along the bottom, KOTOR in polished silver, KMRP in gold on the same bevel, 1.6
  in cyan metal with a soft glow, white feature lines, holo-blue page titles and a white footer
  line on every page. The lettering
  is `tools/build_release_cover.py`'s, so the wordmarks keep the 1.5 kit's bevel.
- **The cover's KOTOR** comes from `src/patcher/brand.png`, polished on the cover only. That
  artwork has lighter patches where each stem meets its bottom serif (they are on the 1.5 and
  1.5.1 covers too); the cover smooths them. `brand.png` itself is unchanged.
- **Nothing inside a frame is retouched or cropped:** each frame is the whole screen, scaled
  down, with its own resolution under it.
- **The 1.6 frames** (pages 02 to 06) are the maintainer's screenshots of 2026-11-13,
  kept in this release folder beside the kit: 1920x1080, and page 03's at 3440x1440
  (added the same evening, 22:38, with a wide frame centred on its page).
- **Pages 08 to 10 reuse frames from the 1.5 kit** (`build/controller-standalone/shots`); each
  frame's label says "KMRP 1.5". They were taken with 1.5, before 1.6 made the HD Original
  font the default, so their text is not 1.6's.
- **The facts on the word pages** are the README's "Coming in 1.6" list and the CHANGELOG. The
  installer's size is the Windows installer built on 2026-11-13, `KMRP-Windows-1.6.0.exe`,
  59,700,224 bytes (57 MiB); 1.5.1's was 146,916,352 bytes (140 MiB). Until 2026-11-13
  evening page 11 said "down from 126 MiB in 1.5", a development build's size.

## Not shown

- **No 1.6 frame of the Xbox-style HUD in play.** 1.6 redrew the button pictures and changed
  the controls, so the 1.5 controller pages would show the old version; page 02 shows the
  Controller Layout screen instead, with remapping, and page 03 the screen as it opens.
- **Movies and Alt-Tab** (16:9 movies on wide screens, no screen reset after a movie, Alt-Tab in
  full screen without the rebuild, keyboard and mouse kept after the startup movies) have no
  page: they had not been seen in play when the kit was made.

What 1.6 changes is listed in [`docs/features.md`](../../../docs/features.md).
