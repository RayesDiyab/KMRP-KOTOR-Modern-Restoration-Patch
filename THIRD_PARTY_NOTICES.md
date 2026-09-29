# Third-party notices

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

## The game's own files

No KMRP release carries a file taken from *Star Wars: Knights of the Old Republic*.
What KMRP needs of the game's own art and data it makes at install, from the
player's copy:

| Made at install | From | By |
| --- | --- | --- |
| enlarged feat, Force-power and skill icons | `TexturePacks/swpc_tex_gui.erf` | `AbilityIconGenerator.cs`, `macos/tools/kmrp-abilityicons.c` |
| the four hex row frames (`lbl_hex*`), the tutorial popup's thirteen `tut_*` icons | `TexturePacks/swpc_tex_gui.erf` | `GameArtGenerator.cs`, `macos/tools/kmrp-gameart.c` |
| `tutorial.2da`, its `icon` column pointed at the `tut_*` copies | `chitin.key`, `data/2da.bif` | the same |

*Corrected 2026-09-29:* until then the hex frames and tutorial icons were exported
from the build machine's game into every resolution's archive, and `tutorial.2da`
was committed to this repository and shipped. Checked the same day against every
shipped image: nothing else in either installer is the game's art. The fonts are
KMRP's own renderings, and `lbl_mileftbot` is KMRP's own drawing under the game's
name. The HD icons, portraits and menu art below are their authors' remakes,
bundled with permission.


## Party Portraits

Party and player portrait artwork is **Party Portraits** by **MadDerp**, bundled with
the author's permission and installed as part of KMRP's Override payload:

169 `.tga` files, shipped unmodified. The mod also offers the same portraits as
`.tpc` and its ReadMe says to install one format or the other; KMRP ships the TGAs,
matching the rest of the Override payload.

Vendored at `third_party/Included/Party Portraits by MadDerp/`.

## KOTOR 1 HD Icon Pack

Interface icon artwork is the **KOTOR1 HD Icon Pack 1.0** by **JackInTheBox**, bundled
with the author's permission:

The 351 icons in the mod's `Override` folder, **converted at build time**: each
192×192 32-bit `.tga` is downscaled to 160×160 and compressed to a DXT5 `.tpc`,
49.4 MB of TGA becoming 8.6 MB (`compress_bundled_icons` in
`tools/prepare_universal_resources.py`). At the mod's own size the Inventory and
Equipment screens, which draw dozens of icons at once, stalled and flashed when
switched between quickly. The optional `BonusICON` variants the mod also offers are
**not** included.

Since 2026-09-29 the same resample also sizes each picture within its canvas, centred:
to 39/64 of it, the median of the game's own icons, instead of the 0.56 to 0.95 the
pack's pictures span, so every item sits in its slot at the size vanilla's does
(`ICON_PICTURE_SPAN`). Nothing of any picture is cut off.

*Corrected 2026-09-24:* this section said the icons shipped as unmodified `.tga`.
They have been converted since commit `6793e48` (2026-09-14); the installer holds
all 351 as `.tpc` and not one of the pack's TGAs.

Vendored at
`third_party/Included/KOTOR1 HD ICON PACK ver1.0 1.0.0 by JackInTheBox/`.

Both of the above are **not optional**: they are artwork, and they replace none of
KMRP's own files. They also **never displace a player's file**: a portrait or icon
already in `Override` that KMRP did not put there -- K1CP's `ia_class8_004` and
`ia_class9_003`, for instance -- is left in place and not recorded, so the player's
file keeps winning and restore does not touch it (`BundledNames` in
`src/patcher/KmrpPatcher.cs`). An earlier version of this paragraph said
`OverrideOperations` backed up whatever they displaced; they displace nothing.

## K1 Area Map Fixes

The 250-entry map-note correction table is from **K1 Area Map Fixes** by **Derslok**,
used with the author's permission:

https://deadlystream.com/files/file/3062-k1-area-map-fixes/

Licensed under the **GNU General Public License version 3**. A copy travels with the
data at:

`third_party/Included/K1-Area-Map-Fixes-1.0.0 by derslok/More info/LICENSE`

**Only the data is used.** `note_table.bin` -- 250 entries of four little-endian
floats, each a note's shipped world position and Derslok's hand-measured correction --
is baked into KMRP's `.kmn` section, SHA-256
`880a325d982d74df496b02782faefdd3ae3802efbba030b9fbccc967cc0ccaa5`, unmodified. The
lookup that reads it is KMRP's own, and none of his code, his scaling work or his
patcher is included or derived from. His `TECHNICAL.txt` ships beside the table so the
data's provenance travels with it.

Separately, and predating this: his published research identified the two area-map
tile-size operands and the 440:512 atlas relationship that KMRP's own map scaling is
built on. That is acknowledged in
[`reverse-engineering/area-map-surface.md`](reverse-engineering/area-map-surface.md).

The correction can be turned off under *Advanced Settings*; see
[`docs/third-party-driver-compat.md`](docs/third-party-driver-compat.md) for how the
optional components are installed.

## K1 Modern Driver Compatibility

**K1 Modern Driver Compatibility 1.2.0** by **Synchro** is redistributed inside the
patcher, with the author's permission, and installed into the game folder unless the
user turns it off under *Advanced Settings*.

https://codeberg.org/Synchro/kotor-modern-driver-compatibility
https://deadlystream.com/files/file/3048-k1-modern-driver-compatibility-patch

Licensed under the **Mozilla Public License 2.0**. The licence text ships inside the
patcher and a copy is preserved at:

`third_party/Included/k1-modern-driver-compatibility-1.2.0 by Synchro/LICENSE`

The two shipped binaries -- `dinput8.dll` and `k1-modern-driver-compatibility.asi` --
are the author's released standalone build, unmodified and byte-for-byte identical to
the published release, so they can be hashed against it. No KMRP code is derived from
K1DC, and none of its code is altered. It does not modify `swkotor.exe`.

What it writes, and the check showing it does not collide with anything KMRP writes,
is documented in [`docs/third-party-driver-compat.md`](docs/third-party-driver-compat.md).

## KPM – Xbox Controls for KOTOR 1

**KPM – Xbox Controls for KOTOR 1 1.2** by **Saul0097** is the basis of KMRP's
controller support, an Advanced Settings component that is on by default, used
with the author's permission:

https://github.com/scopeking0117-alt/KPM-Xbox-Controls-K1

KMRP builds `kmrp-controller.module` from its own sources and Saul0097's source at
commit `78e7eaa3b9554ec0e6732f749424dc916f3a1895`, as modified by KMRP; the
modifications are recorded in `KMRP-CONTROLLER-MODULE.diff` (below). The module
has grown well past the original -- a native joystick path, an XInput/SDL
backend, button prompts, the Controller Layout screen -- but the original's
files are still in it, so the credit and licence below still apply.

**Licence: MIT**, inherited. The module is a derivative of
`ExpandedKeyboardControl`, a patch inside the KOTOR Patch Manager repository
contributed by **J**, so it is covered by that project's licence --
`Copyright (c) 2025 Lane Dibello and KotOR Patch Manager contributors`, vendored
as `LICENSE-KOTOR-PATCH-MANAGER.txt`. Saul0097 described the derivation himself
and all three authors gave explicit permission to bundle; the exact quotations
are recorded in `NOTICE.txt` beside the binaries.

Credit is due to **Saul0097** (controller module), **J** (the expanded keyboard
patch it builds on) and **Lane Dibello** (KOTOR Patch Manager).

The module is loaded by a statically linked build of **KOTOR Patch Manager** by
**Lane Dibello and contributors**, commit
`7d53e52f55622a48ab97001c2680fd9fb59c8f98`, licensed under MIT:

https://github.com/LaneDibello/Kotor-Patch-Manager

The MIT text, source revisions, the runtime binary and its hash, KMRP's
self-module-name patch to the runtime (`KMRP-RUNTIME-PATCH.diff`) and KMRP's
changes to the controller source (`KMRP-CONTROLLER-MODULE.diff`) are preserved
under `third_party/Included/KPM-Xbox-Controls-K1-1.2 by Saul0097/`, whose
`NOTICE.txt` gives the hashes of the runtime and module the installer ships. The
exact runtime design and test boundary are documented in
[`docs/controller-support.md`](docs/controller-support.md).

**The installer carries the MIT text since 2026-09-25.** It embeds
`LICENSE-KOTOR-PATCH-MANAGER.txt` as `Kmrp.controller.kpmlicense` and installs it
beside the module as `kmrp-kotor-patch-manager-LICENSE.txt`, the way it installs
`kmrp-sdl3-LICENSE.txt`. The copy covers the runtime, the module and the three
memory-safety patches below. `Test-ControllerSupport.ps1` checks that the
installed file is byte-identical to the vendored one and that Restore removes it.
Until then, "Permission is hereby granted" occurred nowhere in the installer
(`ECA3DE4B…`, 2026-09-24), although the installer shipped both the runtime and
the module. The phrase occurs once in `7933…`.

## KOTOR Patch Manager — three memory-safety patches

Three patches from the **KOTOR Patch Manager** repository, commit
`7d53e52f55622a48ab97001c2680fd9fb59c8f98`, are installed through KMRP's own
hook table. Their replacement bytes are **copied verbatim rather than
re-derived**, so the behaviour is the one reviewed in that project.

https://github.com/LaneDibello/Kotor-Patch-Manager

| KPM patch id | author | what KMRP installs |
| --- | --- | --- |
| `texture-bucket-safety` | **VexFlint** | two `replace` patches, at `0x0041FEB5` and `0x0046BE64` |
| `grass-memory-safety` | **VexFlint** | two `replace` patches, at `0x004A847C` and `0x004A8380` |
| `save_mem_leak` | **Lane Dibello** | one detour at `0x005DDE32`, into KMRP's own `NativeFreeSaveBufferK1` |

Licensed under **MIT**, `Copyright (c) 2025 Lane Dibello and KotOR Patch Manager
contributors`, the same licence already vendored for the controller module as
`LICENSE-KOTOR-PATCH-MANAGER.txt`.

Only the save-game fix carries KMRP code: the detour calls a handler in
`kmrp-controller.module` that frees the abandoned buffer, because KMRP's hook
table reaches an exported function more cleanly than it reaches a code cave.
The analysis of *which* buffer leaks is KPM's.

`swkotor.exe` is not modified by any of the five: they are entries in
`patch_config.toml`, written at runtime like every other KMRP hook. None of the
five overlaps any of the 742 byte positions KMRP's installer writes at any of its
48 resolutions, and each finds its expected original bytes in every one of those
outputs -- checked 2026-09-24 against the installer's own `--apply` output. (The
first check used gold's delta, then 702 bytes; gold alone misses the 21 bytes
the installer writes over values gold leaves vanilla.)

Background on the texture-bucket pair, including the measured
`maxTexID` values from play, is in
[`reverse-engineering/experiments/texture-bucket-overrun.md`](reverse-engineering/experiments/texture-bucket-overrun.md).

## KOTOR Patch Manager and the K1 Widescreen Patch — macOS

The macOS package (`macos/`) installs two pieces of the **KOTOR Patch Manager**
repository into the game's `Contents/MacOS`:

- **KotorPatcher**, KPM's runtime, by **Lane Dibello** and the KPM contributors,
  built from `src/KotorPatcher`;
- **K1WidescreenPatch** by **FTD, RaymanGT, J and Vriff**, built from
  `Patches/K1WidescreenPatch`, with KMRP's engine fixes.

Both are built from FTD's fork https://github.com/FTD516/Kotor-Patch-Manager,
branch `widescreen-patch` (commit `9884466`), where KMRP's fixes were merged on
2026-09-29 (https://github.com/FTD516/Kotor-Patch-Manager/pull/1). Licensed under **MIT**,
`Copyright (c) 2025 Lane Dibello and KotOR Patch Manager contributors`; the
package carries the licence as `licenses/KotOR-Patch-Manager-LICENSE.txt`.

## NVIDIA NvAPI — interface identifiers

The patcher's NVIDIA present-method step talks to the driver's own
`nvapi64.dll` / `nvapi.dll`, loaded from System32 at run time. **No NVIDIA code
or library is redistributed or linked.** What KMRP takes from NVIDIA's public
NvAPI headers is interface data: sixteen function identifiers passed to
`nvapi_QueryInterface`, the setting id `OGL_CPL_PREFER_DXPRESENT` (`0x20D690F8`)
and its values, the status codes it checks, and the layouts of `NVDRS_SETTING`,
`NVDRS_APPLICATION` and `NVDRS_PROFILE`, marshalled by explicit offset.

https://github.com/NVIDIA/nvapi (`nvapi_interface.h`, `NvApiDriverSettings.h`,
`nvapi_lite_common.h`; the repository's libraries are MIT-licensed,
`Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES`).

The layouts were cross-checked against **NVIDIA Profile Inspector** (Orbmu2k,
MIT), https://github.com/Orbmu2k/nvidiaProfileInspector — read, not copied: KMRP
uses NVIDIA's documented entry points throughout, where Profile Inspector
prefers undocumented ones for getting and setting a value. See
[`docs/nvidia-present-method.md`](docs/nvidia-present-method.md).

## Xelu's Free Controller & Key Prompts

Controller button artwork for the optional controller component. **CC0 1.0
Universal (public domain)** -- no permission was required and none was sought.

    Author:  Nicolae "Xelu" Berbece
    Source:  https://thoseawesomeguys.com/prompts
    Mirror:  https://github.com/DJLink/Xelu_Free_Controller-Key_Prompts
    Vendored at: third_party/Included/Xelu_Free_Controller&Key_Prompts/

The author's own terms, kept verbatim in `Readme.txt` in that folder: "You can
use all these assets in any project you want to (be it commercial or not). All of
the assets are in the public domain under Creative Commons 0 (CC0)."

Four of the pack's sets are used, one per controller family the module can
detect, sixteen actions each (A, B, X, Y, LB, RB, LT, RT, Start, Back, the four
D-pad directions, L3, R3) -- from `Xbox/` (the 360 set, with the Series X art for
R3), `PS5/`, `Switch/` and `Steam Deck/` -- plus KMRP's own swap-tabs
art, one per family since 2026-09-24: `Xbox/Swap_tabs_360.png.png` (the doubled
extension is its real name), `PS5/Swap_tabs_PS5.png`, `Switch/Swap_tabs_Switch.png`
and `Steam Deck/Swap_tabs_SteamDeck.png`. They are source art, not shipped as files:
`tools/build_controller_prompt_textures.py` resizes them per resolution into the
button-fill textures KMRP installs, one set per family.

The Controller Layout screen also uses each family's whole-stick and D-pad art
(`*_Left_Stick.png`, `*_Right_Stick.png`, `*_Dpad.png`) and the pack's two
unlabelled controller diagrams, `Xbox/XboxSeriesX_Diagram_Simple.png` and
`PS5/PS5_Diagram_Simple.png`. `tools/build_controller_layout.py` tints the
diagram, composites the family's own face-button glyphs onto it and bakes the
leader lines into one texture per family. Switch and Steam Deck have no diagram
in the pack, so they are drawn on the Xbox silhouette.

**Only those four families are kept in the repository** (2026-09-24), with
`Readme.txt` for the terms. The pack's `Others/` folder -- PS3, PS4, PS Vita,
PS Move, Wii, Wii U, Xbox One, Ouya, Stadia, Luna, VR and gesture sets -- was
removed, since KMRP supports none of those controllers and no tool read it; the
pack's keyboard export zip and Flash source stay out of git by `.gitignore`.

*Corrected 2026-09-19:* this section used to say ten files were redistributed,
all from the Xbox 360 set, vendored at `third_party/Included/Xelu-Free-Controller-Prompts-CC0/`
with the terms in `UPSTREAM-README.txt` and `LICENSE-CC0.txt`. None of that was
still true: the whole pack is vendored at the path above with its terms in
`Readme.txt`, and the Xbox set had already grown to its sixteen actions before
the other three families were added.

**The Xbox 360 set is used deliberately.** The pack's Series X and Xbox One sets
draw a grey disc with a coloured letter, which loses most of its contrast at
badge size against KOTOR's dark blue panels. The 360 set is a solid coloured
disc, which also matches how the original Xbox build of KOTOR drew its prompts.

**Microsoft's official Xbox glyphs are deliberately NOT used.** They are
trademarked and licensed for Xbox-licensed titles; this repository is public and
GPL-3.0, so redistributing them would not be permissible. Any future replacement
artwork must be CC0 or compatibly licensed for redistribution.

## KOTOR High Resolution Menus

The per-resolution GUI layouts are derived from **KOTOR High Resolution Menus 1.5** by ndix UR:

https://deadlystream.com/files/file/1159-kotor-high-resolution-menus/

The upstream package includes the GNU General Public License version 3. A copy is preserved at:

`third_party/Included/kotor-high-resolution-menus-1.5/LICENSE.txt`

The original archive and generation scripts are retained in the project so the bundled layouts can be reproduced and audited.

## HD menus and UI assets

The shared interface artwork originates from and/or is derived from the HD menu/UI asset set used by RaymanGT's earlier 3440×1440 release:

https://deadlystream.com/files/file/1457-hd-menus-and-ui-assets/

RaymanGT's earlier mod page:

https://deadlystream.com/files/file/2288-kotor-3440x1440-enhanced-hudui-and-menus/

Keep these credits with any public release. Confirm any additional redistribution conditions with the original asset authors before publishing outside the existing agreed project scope.

## Fonts

**No font file is redistributed.** The patcher embeds only rendered TGA glyph
atlases; the `.ttf`/`.otf` files under `assets/fonts/` are build-time inputs
that stay on the build machine. Verified by inspecting every embedded archive —
there is no `.ttf` or `.otf` anywhere in the shipped executable. Re-checked
2026-09-24 on the installer (`ECA3DE4B…`): none of its 49 embedded archives
holds a font file, and the raw installer contains neither OpenType table tag
(`OTTO`, `glyf`).

### Arimo — item descriptions and dialogue subtitles (`fnt_d16x16b`)

Apache License 2.0, by Steve Matteson / Google Fonts. A metrically compatible
substitute for Arial, chosen because the vanilla dialogue atlas is
Helvetica/Arial-like (true lowercase with real descenders, unlike the
small-caps menu atlases).

https://fonts.google.com/specimen/Arimo

### Old Republic — menus, item names, buttons (the other 17 resrefs)

By **Trollax Kinora**, published on dafont and marked **"free for personal
use"**:

https://www.dafont.com/old-republic.font

The author's own note states it is "a reproduction of the font from the Lucas
Arts game, Knights of the Old Republic II ... made ... from screens of the
game", and that because it is "designed after the intellectual property of
someone else it will never be released as anything other than for personal
use." Permission to redistribute was requested and is not expected to be
granted, since those rights are not the author's to give.

**Decision on record**: ship it inside the patcher (which already requires
owning the game) and remove it if Lucasfilm objects. See
`reverse-engineering/font-atlases.md` for the full reasoning, including why
`assets/fonts/KOTOR_UI_Open.ttf` — our own trace of the game's 32px
`dialogfont32x32` master — is only a *typographic* fallback and not a cleaner
one legally, being derived from the same underlying IP.

### Aurebesh — lettering on the Controller Layout screen's edge art

**Aurebesh** by SilvinoR, SIL Open Font License 1.1, Reserved Font Name
AUREBESH. The no-ligature build, `AurebeshNL.ttf` (sha256
`fab46594e5811925ea4f966e29911b9deb5d307141504db8c63e6fd50b4b56f2`, upstream
commit `1aeb227950f2555923485fb586534cbba8c4a979`), is kept with its licence at
`third_party/aurebesh-font/`. It is a build-time input only:
`tools/controller_layout_backdrop.py` renders labels with it into the
`kmrlyt*.tga` textures, and the font itself is not shipped or modified.

https://github.com/silvinor/font-aurebesh

Its 26 letters were checked against the canonical chart on Wikimedia Commons
(`Star-Wars-aurek-besh-alphabet-chart.svg`) before use.

### Evaluated and not shipped

Chakra Petch (SIL OFL), Montserrat (SIL OFL), Rajdhani, Exo 2, Nimbus Sans L
(GPL, URW), Syncopate (Apache). Retained only as build-machine references.
ITC Blair was considered but is a commercial Monotype/ITC face; it was neither
obtained nor used.


## KotorUniResPatch (KPM), J0-o

`https://github.com/J0-o/KotorUniResPatch`. No licence file is published in the
repository (checked 2026-09-02, `LICENSE` returns 404).

No code is copied from it. Its `Scaled Map + Minimap` module independently
identified `0x00459920` as the HUD minimap's image-draw normaliser, and named the
surrounding functions; reading it confirmed our own disassembly and, more
usefully, showed that the function is shared with other draws and must be gated
before it is altered. Our `tools/build_minimap_zoom_fix.py` is an independent
implementation: a hand-written x86 stub gated on viewport geometry and source
size, where KPM uses a DLL with detours and a flag set around the draw. The
arithmetic differs too — KPM scales by an integer `round(height/600)` and sets
the viewport to match, whereas ours derives the factor from the viewport the GUI
actually produced.

## SDL3

The optional controller component ships unmodified **SDL 3.4.16, Windows x86**
from the [official SDL release](https://github.com/libsdl-org/SDL/releases/tag/release-3.4.16).
It is installed as `kmrp-sdl3.dll` to avoid taking ownership of another mod's
`SDL3.dll`. The original zlib licence is embedded in the installer and installed
as `kmrp-sdl3-LICENSE.txt`. The build downloads a SHA-256-pinned SDK under ignored
`build/deps`; see [the backend reference](docs/controller-sdl-backend.md).

Copyright (C) 1997-2026 Sam Lantinga <slouken@libsdl.org>

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
