# KMRP 1.5 press kit

Release art for KMRP 1.5 (2026-10-09, Windows and macOS): the cover and the pages
for mod pages, posts and articles. Use them as they are; please do not crop a frame
out of its page without saying what it shows.

| File | What |
| --- | --- |
| [`00-cover.png`](00-cover.png) | The cover: KMRP 1.5, what ships as standard, Windows and macOS |
| [`01-inventory-1080p.png`](01-inventory-1080p.png) | Inventory: the original game at 1280x960 beside KMRP at 1920x1080 |
| [`02-equipment-1080p.png`](02-equipment-1080p.png) | Equipment, the same pair of sizes |
| [`03-area-map-1080p.png`](03-area-map-1080p.png) | Area map |
| [`04-abilities-1080p.png`](04-abilities-1080p.png) | Abilities |
| [`05-character-1080p.png`](05-character-1080p.png) | Character |
| [`06-journal-1080p.png`](06-journal-1080p.png) | Journal |
| [`07-hud-1080p.png`](07-hud-1080p.png) | In the game |
| [`11-inventory-ultrawide.png`](11-inventory-ultrawide.png) | Inventory: the original game at 1600x1200 above KMRP at 3440x1440 |
| [`12-equipment-ultrawide.png`](12-equipment-ultrawide.png) | Equipment, ultrawide |
| [`13-area-map-ultrawide.png`](13-area-map-ultrawide.png) | Area map, ultrawide |
| [`14-abilities-ultrawide.png`](14-abilities-ultrawide.png) | Abilities, ultrawide |
| [`15-hud-ultrawide.png`](15-hud-ultrawide.png) | In the game, ultrawide |
| [`21-controller-xbox-hud.png`](21-controller-xbox-hud.png) | Controller: the Xbox-style HUD, paused, 1920x1080 |
| [`22-controller-xbox-hud-ultrawide.png`](22-controller-xbox-hud-ultrawide.png) | Controller: the Xbox-style HUD, 3440x1440 |
| [`23-controller-layout.png`](23-controller-layout.png) | Controller: the Controller Layout screen |
| [`24-controller-menus.png`](24-controller-menus.png) | Controller: button pictures on four menus |
| [`31-4k.png`](31-4k.png) | 4K: in the game with the Xbox-style HUD, 3840x2160 |
| [`40-new-platform-macos.png`](40-new-platform-macos.png) | Announcement: new platform, macOS support |
| [`41-mac-installer.png`](41-mac-installer.png) | macOS: the installer after patching |
| [`42-mac-options.png`](42-mac-options.png) | macOS: the installer's Advanced Settings |
| [`43-mac-character.png`](43-mac-character.png) | macOS: the Character screen with a pad, 1512x982 |
| [`44-mac-map.png`](44-mac-map.png) | macOS: the area map with a pad, 1512x982 |
| [`45-mac-screens.png`](45-mac-screens.png) | macOS: six screens on one sheet |
| [`50-linux-proton.png`](50-linux-proton.png) | Announcement: tested on Linux, Ubuntu with Proton |

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
