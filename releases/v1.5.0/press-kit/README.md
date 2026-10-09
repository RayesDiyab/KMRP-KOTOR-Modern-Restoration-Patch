# KMRP 1.5 press kit

Release art for KMRP 1.5 (2026-10-09, Windows and macOS): the cover and the pages
for mod pages, posts and articles. Use them as they are; please do not crop a frame
out of its page without saying what it shows.

The first twelve are the set to lead with, in this order.

| File | What |
| --- | --- |
| [`01-cover.png`](01-cover.png) | Cover: KMRP 1.5, what ships as standard, Windows and macOS |
| [`02-new-platform-macos.png`](02-new-platform-macos.png) | New platform: macOS support |
| [`03-macos-character.png`](03-macos-character.png) | macOS: the Character screen with a pad, 1512x982 |
| [`04-linux-proton.png`](04-linux-proton.png) | Linux: tested on Ubuntu with Proton |
| [`05-inventory-1080p.png`](05-inventory-1080p.png) | Inventory: the original game at 1280x960 beside KMRP at 1920x1080 |
| [`06-equipment-1080p.png`](06-equipment-1080p.png) | Equipment: the original game at 1280x960 beside KMRP at 1920x1080 |
| [`07-inventory-ultrawide.png`](07-inventory-ultrawide.png) | Inventory, ultrawide: the original at 1600x1200 above KMRP at 3440x1440 |
| [`08-4k.png`](08-4k.png) | 4K: in the game, 3840x2160 |
| [`09-controller-xbox-hud.png`](09-controller-xbox-hud.png) | Controller: the Xbox-style HUD, 1920x1080 |
| [`10-controller-xbox-hud-ultrawide.png`](10-controller-xbox-hud-ultrawide.png) | Controller: the Xbox-style HUD, 3440x1440 |
| [`11-controller-menus.png`](11-controller-menus.png) | Controller: button pictures on every menu |
| [`12-controller-layout.png`](12-controller-layout.png) | Controller: the Controller Layout screen |



## How they were made

- **The pages** are composed by `tools/build_release_shots.py` and the cover by
  `tools/build_release_cover.py`, from screenshots. Nothing inside a frame is
  retouched or cropped: each frame is the whole screen, scaled down, with its own
  resolution under it.
- **KMRP frames** were taken on 2026-10-08 in a test copy of the game with the 1.5
  build, at 1920x1080 and 3440x1440, driven with a virtual controller.
- **"Original game" frames** show the game's own interface at the largest size the
  unpatched game offers for that monitor (1280x960 beside 1920x1080, 1600x1200
  beside 3440x1440). They were taken in a copy that has only the controller patch,
  with the pointer moved so that no controller picture is on screen.
- **macOS frames** are the maintainer's screenshots from an Apple Silicon MacBook
  Pro. The six-screen sheet arrived reduced, so its screens are small.
- **The Linux card** has no screenshot: the test on Ubuntu is the maintainer's
  report, recorded in [`docs/linux-proton-steam-deck.md`](../../../docs/linux-proton-steam-deck.md).
- **The 4K frame** is the maintainer's screenshot from a 4K television at 3840x2160.
  It reached this folder reduced to 2000x1125, which is more than the page shows it
  at; the label gives the size it was taken at.

What 1.5 changes is listed in [`docs/features.md`](../../../docs/features.md).
