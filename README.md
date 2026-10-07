<div align="center">

<img src="assets/branding/release-cover.png" alt="KMRP - KOTOR Modern Restoration Patch" width="100%">

# KMRP - KOTOR Modern Restoration Patch

**A resolution-aware interface patch for *Star Wars: Knights of the Old Republic* (2003).**

Vanilla KOTOR draws its interface at a fixed pixel size. On a modern display the
menus still work, but the text is tiny, list rows overlap once anything is
enlarged, and several layouts were only ever authored for 640×480. KMRP fixes
that in the engine itself rather than by swapping artwork: 66 resolutions built in,
from 800×600 to 15360×8640, and any other size from 4:3 to 32:9 made when the game
runs at it. The resolution is chosen in the game, with no reinstall.

[Install](#install) · [Features](docs/features.md) · [What it fixes](#what-it-fixes) · [How it works](#how-it-works) · [Build from source](#build-from-source) · [Documentation](#documentation) · [Case study](https://rayesdiyab.com/projects/kmrp/) · [Licence](#licence-and-attribution)

</div>

---

## Install

> [!IMPORTANT]
> You run one program once, then start the game as you always do -- from Steam,
> or from `swkotor.exe`. KMRP does not rewrite the game's executable: its engine
> changes are applied in memory each time the game starts, by KOTOR Patch
> Manager's runtime, which the installer puts beside the game.

**Requirements**

| | |
| --- | --- |
| Game | *Star Wars: Knights of the Old Republic* (2003 PC release) |
| `swkotor.exe` | One of three builds, and KMRP refuses every other: **Steam's** (`34E6D971…A439F34C88`), **GOG's** (`9C10E045…DEA91435`), or the **4,042,752-byte editable 1.03 build** (`761F9466…C49E9886`). GOG's and the editable build are also accepted with only the standard Large Address Aware bit already set. |
| OS | Windows with .NET Framework 4.x (shipped with Windows 10/11). Linux with Proton is experimental; see [Other platforms](#other-platforms). |

1. Launch KOTOR once so `swkotor.ini` exists.
2. Run **`KMRP - KOTOR Modern Restoration Patch.exe`**. It finds Steam's KOTOR by itself,
   in any Steam library, and otherwise GOG's; **Browse** picks another `swkotor.exe`.
3. Choose **Start Patching**. There is no resolution to pick: the game starts at
   your display's current resolution, and every resolution your display supports is
   offered in the game, under Options, Graphics, Screen Resolution. Connect another
   display, a 4K television for one, and the game offers that display's resolutions.
4. Start KOTOR as usual.

**Options.** Advanced Settings (the gear) turns off Modern Driver Compatibility, the
area-map marker fixes and controller support, each on its own, and turns on debug
logs, which are off unless you are asked for them with a bug report. To change one
later, use **Restore Original**, then patch again.

**Undo.** **Restore Original** reverses every change KMRP made, from the hashes it
recorded when it installed; a file changed since is left alone, and said so.

**Updating.** Patching over an older KMRP replaces it, whichever way that version
installed itself. If Steam verifies the game's files, it puts its own `binkw32.dll`
back and KMRP stops loading: patch again.

**What it changes** compared with the unmodified game is listed for players in
[docs/features.md](docs/features.md).

### Controller support

`KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` is KMRP's controller support as a
patch of its own: the pad in the game and in every menu, button prompts for Xbox,
PlayStation, Switch and Steam Deck pads, rumble, and the Controller Layout screen.
The installer installs it beside KMRP's patch while Controller Support is on. It
also runs in a game that has no KMRP, on the interface the game ships or beside
another widescreen patch: it needs no other patch, writes nothing to `Override`,
and places its prompts from the running game (seen beside KMRP at 3440x1440, and
beside Scaled Kotor 1.3.1 at 1920x1080 and 3440x1440).

It also brings an **Xbox-style HUD**, on by default: the in-game HUD laid out as
the original Xbox version's while the pad is in use, and the game's own HUD back as
soon as the mouse or keyboard is used. To keep the game's own HUD with the pad too,
set `Style=PC` under `[Hud]` in `kmrp-controller.ini` beside the game. See
[docs/controller-standalone.md](docs/controller-standalone.md) and
[docs/controller-xbox-hud.md](docs/controller-xbox-hud.md). Windows only.

### With KOTOR Patch Manager

KMRP is two KPM patches, each working without the other: `KMRP.kpatch` and the
controller patch above. Both combine with other KPM patches.

- The installer carries both and puts them in KPM's patch folder, the controller
  patch only while Controller Support is on. If KPM's runtime is already in the game
  folder, the installer leaves the patches to KPM and says where the files are.
- In KPM, tick `KMRP`, and the controller patch for the pad, then Apply and Launch.
  KMRP includes the 4 GB and memory fixes, so KPM's own ones stay unticked.
- KMRP's options are map notes, on, and debug logs, off. KPM 0.7.1 has no patch
  options and installs it that way.
- On Steam, switch KPM to its proxy deployment and start the game from Steam.
- With KPM 0.7.1, tick *Use library proxy* in KPM before pressing Apply (press
  Uninstall All if it is greyed out), or only KPM's Launch starts the game patched.
- `--export-kpm-patches <folder>` writes both `.kpatch` files out for sharing.

[docs/kpm-edition.md](docs/kpm-edition.md) describes both ways.

### Other platforms

**macOS (Steam, in development).** A separate installer for the Aspyr build on Steam,
made from the same resources as this one. See [macos/README.md](macos/README.md).

**Linux / Proton / Steam Deck (experimental).** Launch the installer inside the
game's Proton environment with `protontricks-launch --appid 32370`, and use the
same route for restore. The last run under Proton was the installer of 2026-10-01
on Ubuntu, which still wrote `Override` files; the current build has not been run
under Proton, and Steam Deck is untested. The commands and the test matrix are in
the [Linux, Proton, and Steam Deck guide](docs/linux-proton-steam-deck.md).

### What the installer touches

| Where | What |
| --- | --- |
| Beside `swkotor.exe` | KOTOR Patch Manager's runtime, laid out as KPM's own proxy deployment: KPM's `binkw32.dll` proxy in place of the game's (renamed `binkw32Hooked.dll`), `KotorPatcher.dll` and `patch_config.toml`. |
| `patches\` | `kmrp.dll`, KMRP's module, with the engine changes and every resolution's interface files; and `kmrp-controller.dll` while Controller Support is on. |
| `configs\` | `kmrp.ini` and `kmrp-controller.ini`, the options the patches were installed with. |
| `kmrp-controller.ini` | Beside the game: rumble and HUD style, yours to edit. Written only when it is not there. |
| `swkotor.ini` | The starting resolution. Its prior contents are kept in a verified backup. |
| `swkotor.exe` | On GOG's and the editable build, the standard Large Address Aware flag: one bit, with a backup of the unmodified file in KPM's own format. **Steam's is never changed.** |
| `Override` | Nothing. |
| Windows | A per-user compatibility value that marks the game DPI-aware ([details](docs/windows-dpi-scaling.md)). |
| NVIDIA driver | Only where the global present method would show half-drawn frames: **Prefer native** for `swkotor.exe` ([details](docs/nvidia-present-method.md)). |
| Optional | *Modern Driver Compatibility* adds its loader (`dinput8.dll`) and payload beside the game. |

Every change is recorded with hashes in manifests beside the game, and **Restore
Original** reverses each from those records. In a game folder where KOTOR Patch
Manager's runtime is already installed, the installer installs no runtime and does
not touch `swkotor.exe`: KPM applies KMRP's patches.

<details>
<summary><b>Command line</b> (same operations, no window)</summary>

```
KMRP.exe --in-place <game.exe> [WIDTHxHEIGHT]
KMRP.exe --restore  <game.exe>
KMRP.exe --export-kpm-patches <folder>
KMRP.exe --apply    <source.exe> <output.exe> [WIDTHxHEIGHT]
```

The resolution given to `--in-place` is where `swkotor.ini` starts the game.
`--apply` writes a patched copy and leaves the original alone: a reference
executable for one resolution, which the installer does not install.

</details>

<details>
<summary><b>On the version number</b></summary>

The first public release is **KMRP 1.0**, published on 2026-09-04 and tagged
[v1.0.0](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases/tag/v1.0.0).
The build in progress is **KMRP 1.5**, and its installer reports 1.5.0. Internal
development numbers appear in [`CHANGELOG.md`](CHANGELOG.md): 2.0.0 to 2.9.x were
private builds, 2.10.0 is 1.0 (that tag remains on the same commit, and 1.0's
Properties report 2.7.0.0, a mislabel), and 2.11.0 was this build's number until it
was relabelled 1.5.0. One 2.0.0 build left the machine before 1.0; its hash is
recorded in [`releases/universal-v2.0.0/`](releases/universal-v2.0.0/).

</details>

---

## What it fixes

The full list of what changes, in plain words, is in
[docs/features.md](docs/features.md), and with the mechanism of each in
[docs/features-technical.md](docs/features-technical.md). The table below is the
engine defects: every entry was diagnosed against the executable, and each links to
the full trace. Several are vanilla BioWare bugs that only become visible once the
interface is scaled.

| Symptom | Cause | Where |
| --- | --- | --- |
| **Text unreadably small** at high resolution | UI text renders at a fixed pixel size regardless of resolution | [font-scaling](docs/font-scaling.md) |
| **Inventory crash** on items with long descriptions | The line-breaker restarts an unbreakable line at the position it began at, comparing against the start of the *string* rather than the current *line* -- it loops until the allocator fails | [font-atlases](reverse-engineering/font-atlases.md) |
| **List rows grow** every time a list is repopulated | `CAurGUIListBox` adds a row *count* to a row *height*, then writes the inflated rect back into reused controls. A vanilla bug, reproduced with an unmodified `.gui` | [listbox-geometry](reverse-engineering/listbox-geometry.md) |
| **Rows and icons stay vanilla-sized** | Row and icon sizes are hardcoded constants, unreachable from any `.gui` | [inventory-item-rows](reverse-engineering/inventory-item-rows.md) |
| **Stack-count numbers vanish** when the font grows | The label is built in the inventory row's `SetRect`, bottom-right-aligned inside the icon box, so scaling the icon leaves it behind | [inventory-item-rows](reverse-engineering/inventory-item-rows.md) |
| **Description text runs under the scrollbar** | The engine truncates each glyph advance and under-measures a line by ~3%; vanilla also left the listbox gutter at 0 on six panes | [listbox-geometry](reverse-engineering/listbox-geometry.md) |
| **Dialogue letterbox too small** on ultrawide | Bar height derived from screen *width* | [font-scaling](docs/font-scaling.md) |
| **HUD minimap not zoomed** to the player | The minimap pans the map under a centre-pinned marker with no clamping | [map](reverse-engineering/map.md) |
| **Message popups clipped** mid-word | An auto-fit loop widens the popup only while it is narrower than a cap authored for 640×480 | [message-popup](reverse-engineering/message-popup.md) |
| **HUD notifications oversized at 4K**, and **Feedback option circles on the scrollbar** | Short-lived HUD controls were scaled from screen width instead of the common height rule; the Feedback list drew each circle at the row's very edge, which is where its left scrollbar ends, and now keeps a gutter | [universal resolution math](docs/universal-resolution-math.md#reported-4k-layout-repairs) |
| **Out-of-memory failures near the 2 GB process ceiling** | The 32-bit executable did not declare that it can use addresses above 2 GB; KMRP now sets the standard PE Large Address Aware bit | [large-address-aware](reverse-engineering/large-address-aware.md) |
| **Movies trigger a 640×480 mode switch, minimize, or lose focus** | Full-screen Bink playback has two resolution pairs independent of the normal render size; KMRP writes the resolution the game is running at into both | [movies](reverse-engineering/movies.md) |
| **Movies cropped** on wide screens -- a 640×480 logo drawn 3440×2580 at 3440×1440 | Retail scales a movie by the screen *width* alone; KMRP fits it by whichever of width and height runs out first | [movies](reverse-engineering/movies.md) |
| **Map marker click offset** from where it is drawn | The hit test centred the map canvas in the window, while the control that crops it is placed by the marker overlay -- 141px out horizontally | [map-markers](reverse-engineering/map-markers.md) |
| **Unfogged strip** down the right of the area map | The map picture is drawn onto a canvas wider than the overlay the fog grid covers, and nothing cropped the surplus | [area-map-surface](reverse-engineering/area-map-surface.md) |
| **250 map notes in the wrong place** | A 2003 content bug: the notes' stored world positions do not match their subjects | [map-markers](reverse-engineering/map-markers.md) |

---

## What it looks like

Vanilla on the left, KMRP on the right, both frames whole and uncropped.

<img src="assets/screenshots/2-inventory.png" alt="Party inventory, vanilla 800x600 next to KMRP 1920x1080" width="100%">

Rows, icons and stack counts scale with the text, so the item list stops truncating
names and the description panel reads at a glance.

<img src="assets/screenshots/3-area-map.png" alt="Area map, vanilla 800x600 next to KMRP 1920x1080" width="100%">

The map fills its frame, fog reaches the right edge, and the map note sits clear of
the buttons.

It holds at 21:9 as well -- every resolution is generated from the same rules, not
hand-tuned one at a time:

<img src="assets/screenshots/uw-1-hud.png" alt="In-game HUD at 3440x1440" width="100%">

More in [`assets/screenshots/`](assets/screenshots/).

---

## How it works

KMRP builds its engine fixes from tracked source and ships them, with every
resolution's interface resources, inside one module.

```text
 source patch sites + x86 assembly builders
     -> Windows engine template --------------------.
 override-common.zip + resolution layouts -> bank --+-> kmrp-native.dll -> KMRP.kpatch
 game starts -> KPM proxy/runtime -> patches\kmrp.dll
     -> verifies original instructions -> applies fixes in memory for the size in use
     -> unpacks that size's files to a private cache the game reads
     -> a resolution change in the game: both again, for the new size
```

The Windows build uses [`tools/build_windows_engine.py`](tools/build_windows_engine.py)
to assemble the injected code and its original-byte guards. It needs neither a
clean 1.03 executable nor a patched gold snapshot. KMRP's module fills the
template in for the resolution the game is running at, and validates the decrypted
game instructions before applying any memory changes. This serves the supported Steam,
GOG and editable CD 1.03 variants through the same patch recipe.

The eleven code/data pages retain their existing layout and relocations. The
[historical byte inventory](reverse-engineering/binary-inventory.md) records the
sites; the [source build reference](docs/windows-engine-source.md) explains the
new build and verification. Original game files remain hash-validated during
installation, and backup/restore ownership remains unchanged. On the editable
executable the installer still manages the existing 4 GB header flag; Steam's
executable stays unchanged.

**Each interface file is stored once.** Most of the 66 resolutions' files are
the same bytes at several resolutions, so the module embeds them as one bank
of distinct files, compressed, with an index per resolution, and unpacks the set
of the size in use. The bank also leaves out every file the module can write itself, exactly, from
its blend table (most layouts and badges of most sizes), and checks each file it
writes against the set's index. The installer carries the module once, inside
`KMRP.kpatch`, and the controller patch beside it, and is about 140 MB.

**One scaling rule, everywhere.** Font metrics, list rows, icon sizes and popup
geometry all scale by `max(1.0, height / 720)` -- 1.00× at 720p, 1.50× at 1080p,
2.00× at 1440p, 3.00× at 2160p. The `.gui` files and the executable constants
are generated from that same rule so they cannot drift apart.

**Fonts are rendered, not shipped.** All 18 atlases are rasterised from vector
outlines at build time, once per resolution at that resolution's own scale, so
one atlas texel lands on one screen pixel and nothing is resampled. 15360×8640
is the one exception: its scale-12.0 atlas is larger than the baker can produce.
No font file is redistributed -- see
[Licence and attribution](#licence-and-attribution).

---

## What else it installs

Alongside its own fixes, KMRP bundles work by other authors, each with that
author's permission. All of it is optional or deferential -- none of it silently
overwrites a mod you installed yourself.

| Component | Author | Licence | Optional |
| --- | --- | --- | --- |
| [K1 Modern Driver Compatibility](https://codeberg.org/Synchro/kotor-modern-driver-compatibility) 1.2.0 | Synchro | MPL-2.0 | **Yes** -- Advanced Settings |
| Area map marker corrections (250 notes) | Derslok | GPL-3.0 | **Yes** -- Advanced Settings |
| Controller support, based on [KPM – Xbox Controls for KOTOR 1](https://github.com/scopeking0117-alt/KPM-Xbox-Controls-K1) 1.2 | Saul0097 / KMRP | MIT, inherited from KOTOR Patch Manager, with each author's permission (his own licence file pending); SDL zlib | **Yes, on by default** -- Advanced Settings |
| Party Portraits | MadDerp | -- | No |
| KOTOR 1 HD Icon Pack 1.0 | JackInTheBox | -- | No |

**Advanced Settings**, the button beside *Start Patching*, controls all three
optional components. All three default to on, each can be turned off on its own,
and *Restore Defaults* turns all three back on. A fourth row, *Debug Logs*, is off
by default: it makes KMRP write diagnostic log files beside the game. The choices
are remembered in `%LOCALAPPDATA%\KMRP\settings.json`.

**Updates.** When its window opens, the installer asks GitHub whether a newer
KMRP has been released. If one has, it offers the Deadly Stream page or a skip.
*Don't remind me again for* that version silences it, and only it. What the
request sends is in
[SECURITY.md](SECURITY.md).

**Driver compatibility** is two files dropped beside `swkotor.exe`; it never
edits the executable, and KMRP removes them on restore. What it changes, and the
check showing its eight patch sites do not collide with any of the 742 byte
positions KMRP's installer writes at any resolution, is in
[docs/third-party-driver-compat.md](docs/third-party-driver-compat.md).

**KMRP's runtime** is KOTOR Patch Manager's (MIT), built from the
[submodule](third_party/Kotor-Patch-Manager) and loaded through KPM's own
`binkw32.dll` proxy, with KMRP's two KPM patches -- the same ones the
installer carries as `.kpatch` files for KPM's app. KMRP's own patch is installed
every time: KMRP's engine changes, three memory-safety fixes, mouse confinement,
the movies, the movie bars and the status summary's layout.
**Controller support** is the second patch, `kmrp-controller`, installed while
Controller Support is on: its module, its hooks in `patch_config.toml` after
KMRP's, and `configs\kmrp-controller.ini`. The marker option and debug logs are
the two options of KMRP's patch, `map-notes` and `debug-logs`; the installer writes
the two choices into `configs\kmrp.ini` in the game folder (the `[Patch Options]`
section), where a KOTOR Patch Manager with patch options records them too.
Xbox devices retain XInput; SDL3/HIDAPI supplies mapped non-Xbox devices to the
same normalized state. Input still travels through KOTOR's retained controller
events rather than synthetic keys. Options → Gameplay also gains a live
Controller Layout screen. An existing `patch_config.toml`, `KotorPatcher.dll` or
`binkw32Hooked.dll` that KMRP did not write -- KOTOR Patch Manager's own install
-- is left alone, and KMRP is installed for KPM instead. Exact files, mappings, hooks,
dynamic prompt families, layout screen, and the remaining hardware/Proton test
matrix are in [docs/controller-support.md](docs/controller-support.md) and
[docs/controller-layout.md](docs/controller-layout.md).

**KMRP's files take precedence, and replace nothing.** The module's files are
read from its own cache ahead of `Override`, so no file of yours is overwritten
or moved, and removing KMRP leaves `Override` exactly as it was. Measured for the
main menu's layout on 2026-10-04; a content mod's portrait or icon of the same
name has not been compared.

**Tested against** KOTOR 1 Community Patch 1.10.0 and KOTOR 1 Restoration 1.2:
neither ships `.gui` files, neither touches `swkotor.exe`, and neither patches
`tutorial.2da`, the only 2DA KMRP supplies (made from the game's own table by the
module when the game starts). K1CP replaces two icons the HD Icon Pack
also provides. The order in which you install content mods and KMRP no longer
matters, since KMRP writes nothing into `Override`. Do not also install UniWS, High Resolution
Menus, or a separate 4 GB patch. KOTORganizer users should finish Sync and then
run KMRP manually against the real game folder; see the full
[mod-build compatibility and install-order guide](docs/mod-build-compatibility.md).

---

## Build from source

Building is only needed to develop KMRP; players just run the released
executable.

**Prerequisites**

- Windows with .NET Framework 4.x (`csc.exe` from `v4.0.30319`)
- Python 3 with `pykotor`, `capstone`, and `Pillow` + `numpy` for the asset tools
  (`pip install -r requirements.txt`)
- Visual Studio Build Tools (MSVC, x86) for the controller module and KOTOR
  Patch Manager's runtime, which the build compiles from the submodule
  (`git submodule update --init`; [src/kpm-runtime](src/kpm-runtime/README.md))
- Network access on the first build: `tools/prepare_sdl3.ps1` downloads the
  pinned SDL 3 SDK into `build/deps` and checks its hash
- `TexturePacks/swpc_tex_gui.erf` from your own game, placed in
  [`build-inputs/`](build-inputs/README.md). Steam's texture pack is sufficient;
  no game executable is a build input.
- The game's own 84 layout files in `build-inputs/vanilla-gui`, for the controller
  patch the installer carries since 2026-10-05: written once by
  `python tools\build_controller_assets.py --extract <game folder>` from an
  unmodified game.

```powershell
.\build_kmrp.ps1
```

That regenerates all 66 resource archives and compiles the patcher to
`dist/`. Add `-ReuseResources` to skip regenerating the interface archives;
engine assembly, native compilation, pooling and KPM packaging still run.

The build assembles the Windows engine template and compiles KMRP's module, the
controller patch's module and KPM's runtime itself. Optionally generate per-resolution font sets in
`build/fonts` with `tools/build_font_scale_sets.py` first. Without them the build
warns and each resolution falls back to the shared atlas.

The source-only engine regression can run without game files:

```powershell
python testing/regression/Test-WindowsEngineSource.py --csc C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
```

**The project folder is self-contained.** The texture pack and the extracted
layout files are the only required game-derived files supplied from outside, and
are never committed. The build
creates its engine template and native modules inside the project.

> [!NOTE]
> **Game binaries and game resources are never committed.** `.gitignore` blocks
> `*.exe`, `*.erf`, `*.bif`, `*.key` and friends. The gold snapshots live only on
> the build machine; the chain of hashes that identifies them is recorded in
> [docs/font-scaling.md](docs/font-scaling.md) so any of them can be rebuilt and
> verified.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the working rules this project holds
itself to -- verifying before and after every executable edit, measuring rather
than eyeballing, and recording what was disproved alongside what worked.

---

## Repository layout

```
.github/              CI workflow, issue and pull request templates, Dependabot
assets/               Build inputs
  branding/           Logo, favicon, and the patcher's UI icons
  fonts/  hd-fonts/   Font sources and the rendered atlases
  override-*/         GUI layouts and artwork the patch's module carries
docs/                 Build and design documentation
reverse-engineering/  Engine analysis, one document per subsystem
  patch-records/      Machine-readable descriptions of confirmed patches
src/patcher/          The Windows patcher application (C#)
src/controller-native/ KMRP's module and the controller patch's (C++), loaded by KOTOR Patch Manager
src/kpm-runtime/      Builds KOTOR Patch Manager's runtime and proxy from the submodule
tools/                Python tools that build the engine recipe, the patches and resources
testing/              Regression tests, controller harnesses, virtual-display profiles
build-inputs/         Files from your own game copy (never committed)
third_party/          Upstream inputs: GUI layouts, bundled mods, glyph art, a font
archive/              Superseded assets, kept only for reference
releases/             Notes and hashes for past releases
```

## Documentation

| | |
| --- | --- |
| [docs/](docs/) | Build and design documentation -- start at [docs/README.md](docs/README.md) |
| [reverse-engineering/](reverse-engineering/) | Engine analysis, one document per subsystem -- index at [reverse-engineering/README.md](reverse-engineering/README.md) |
| [CHANGELOG.md](CHANGELOG.md) | What changed, per release |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Upstream work this builds on, and the licensing position |

The reverse-engineering notes are written to be read by someone who was not
there: they record the addresses, the measurements, and -- deliberately -- the
theories that turned out to be **wrong**, so the same dead ends are not explored
twice.

---

## Licence and attribution

KMRP is distributed under the **GNU General Public License v3.0** -- see
[LICENSE](LICENSE). The per-resolution GUI layouts derive from *KOTOR High
Resolution Menus 1.5* by **ndix UR**, which is GPL-3.0, and that licence carries
forward.

It also redistributes, with permission: **K1 Modern Driver Compatibility** by
**Synchro** (MPL-2.0), the map-note correction table from **K1 Area Map Fixes** by
**Derslok** (GPL-3.0), **Party Portraits** by **MadDerp**, the **KOTOR 1 HD
Icon Pack** by **JackInTheBox**, and the controller module built on
**Saul0097**'s KPM Xbox Controls with the **KOTOR Patch Manager** runtime (MIT).
The driver files, the note table and the portraits ship unmodified; the 351
icons are downscaled from 192 to 160 px and compressed to DXT5 at build time.
**SDL 3** (zlib) ships unmodified with its licence.

Interface artwork derives from the HD menu/UI asset set used in **RaymanGT**'s
3440×1440 release. Full credits, links, and the reasoning behind each decision
are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) -- including one
**unresolved** point recorded honestly: the *Old Republic* typeface used for
menu text is marked "free for personal use" by its author, who states it cannot
be licensed further because it reproduces someone else's intellectual property.
KMRP embeds rendered glyph atlases rather than the font file, ships only to
people who already own the game, and the position on record is to remove it if
Lucasfilm objects. **If you redistribute KMRP, that point is yours to weigh.**

*Star Wars: Knights of the Old Republic* is © 2003 BioWare Corp. / LucasArts.
This is an unofficial community patch, not affiliated with or endorsed by
BioWare, LucasArts, Lucasfilm, or Disney. You must own the game.
