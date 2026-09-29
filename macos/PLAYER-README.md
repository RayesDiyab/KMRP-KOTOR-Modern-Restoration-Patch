# KMRP for macOS

KMRP (KOTOR Modern Restoration Patch) for the Steam version of *Star Wars: Knights of
the Old Republic* on the Mac. It is the same KMRP as on Windows: the same menus, laid out
for your display's resolution, the same HD fonts, art and icons, and the same engine fixes.

## Requirements

- *Knights of the Old Republic* from **Steam**, the Aspyr macOS build, unmodified
  (`KOTOR_Exe` version 1.4.0). The installer checks this and refuses anything else.
- Apple Silicon Macs need Rosetta 2, as the game itself does.
- Run the game once before installing, so its settings file exists.

## Install

1. Quit KOTOR.
2. Double-click **Install KMRP.command**.
   - If macOS says it cannot be opened because the developer cannot be verified,
     Control-click it, choose **Open**, then **Open** again. Or open Terminal and run:
     `xattr -dr com.apple.quarantine ~/Downloads/KMRP-macOS-1.5.0` (use the folder's
     real path), then double-click it again.
3. On a Retina display, choose the resolution (see *Options*): press Return for native,
   or type `2` for half.
4. Read the summary, type `y` and press Return.
5. Start KOTOR from Steam as usual.

The installer finds the game in your Steam libraries. For a copy somewhere else, run in
Terminal: `./kmrp/kmrp-mac.sh install --game "/path/to/Knights of the Old Republic.app"`.

## What you get

- **KMRP's interface, full screen**, laid out for your resolution: the menu set KMRP builds
  for it, with every list, icon, popup and the area map sized as on Windows. The package
  has sets for every Mac display and every resolution the Windows version offers (66 in
  all); for any other size the installer blends one from the sets around it.
- **HD fonts** baked for your resolution, sharp at any size.
- **KMRP's engine fixes**: no hang on long item descriptions, stack counts that stay
  visible, list rows that stop growing, no blank first line in descriptions, a dialogue
  letterbox that works on any display with a reply list that fills it, and a minimap at the
  vanilla zoom. On a Retina Mac, the screen's full resolution.
- **HD art**: JackInTheBox's HD Icon Pack, MadDerp's Party Portraits, KMRP's HD interface
  textures, and feat, power and skill icons enlarged to fit KMRP's rows. Item icons are
  sized to sit in their slots the way the game's own do.
- **250 map notes moved to where they belong** (Derslok's K1 Area Map Fixes).

## Options

- **Resolution** (Retina displays). *Native* renders every pixel of the screen, for
  example 3024x1964 on a 14" MacBook Pro: the sharpest picture. *Half* renders the size
  macOS lays out its own windows at (1512x982 there) and lets macOS scale it up: lighter
  on the GPU. At native, set **Anti-aliasing to 2x** in the game's graphics options: on an
  M5, 6x at native ran at about 30 fps in game and 2x at about 120. From Terminal:
  `--resolution native` or `--resolution half`.
- **Another display or size**: `./kmrp/kmrp-mac.sh install --size 2560x1440`, for example
  for an external monitor. The interface is laid out for one size; to change it later,
  uninstall and install again.
- **Without the map-note corrections**: `./kmrp/kmrp-mac.sh install --no-map-notes`.

## Uninstall

Quit KOTOR and double-click **Uninstall KMRP.command**. It restores the original
`KOTOR_Exe`, your settings and every file KMRP replaced, and deletes what it added. A file
you changed after installing is left alone and reported.

## What it changes

- `KOTOR_Exe`: one load command so the game loads KotOR Patch Manager's patcher, then an
  ad-hoc re-signature, exactly as KotOR Patch Manager itself does. The original is kept in
  `~/Library/Application Support/KMRP/macos/backup`.
- Next to `KOTOR_Exe`: `KotorPatcher.dylib`, `patch_config.toml`, `patches/` (the
  widescreen patch by J, FTD and Vriff, with KMRP's engine fixes, and KMRP's own patches).
- `swkotor.ini`: `UseGuiFileLayouts`, `ForceWidth` and `ForceHeight`, under
  `[Graphics Options]`. Uninstall puts back what was there before.
- `Contents/Assets/override`: the interface, fonts and art. Portraits and icons you already
  have from another mod are kept; KMRP's own files replace older copies after saving them.

Steam's **Verify integrity of game files** also restores `KOTOR_Exe`; run the uninstaller
afterwards to clean up the rest.

## If you already use KotOR Patch Manager

KMRP installs the widescreen patch itself, in the version with KMRP's engine fixes. The
installer stops if KotOR Patch Manager patches are already installed, rather than overwrite
them: remove them in KPM first, then install KMRP.

## Credits

KMRP by Rayes Diyab (RaymanGT), GPL-3.0. Widescreen patch by J, FTD and Vriff, and
KotOR Patch Manager by LaneDibello and contributors, both MIT. The menu layouts derive from
KOTOR High Resolution Menus by ndix UR, GPL-3.0. HD Icon Pack by JackInTheBox, Party Portraits by MadDerp and K1 Area Map Fixes by
Derslok, each bundled with the author's permission. Licences and notices are in
`kmrp/licenses/`.
