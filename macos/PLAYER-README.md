# KMRP for macOS

KMRP (KOTOR Modern Restoration Patch) for the Steam version of *Star Wars: Knights of
the Old Republic* on the Mac. It is the same KMRP as on Windows: the same menus, laid out
for your display's resolution, the same HD fonts, art and icons, and the same engine fixes.

## Requirements

- *Knights of the Old Republic* from **Steam**, the Aspyr macOS build, unmodified
  (`KOTOR_Exe` version 1.4.0). The installer checks this and refuses anything else.
- macOS 10.13 or later. Apple Silicon Macs need Rosetta 2, as the game itself does.
- Run the game once before installing, so its settings file exists.

## Install

1. Quit KOTOR.
2. Open **KMRP-macOS-1.5.0.dmg** (or unzip the `.zip`, if that is the download you have), then
   open **KMRP Installer** in it. It runs from there; nothing needs copying.
   - KMRP is not signed by an Apple developer account, so the first time macOS asks you to
     allow it. On macOS 15 and later: macOS says it cannot open it; click **Done**, open
     **System Settings → Privacy & Security**, scroll down, click **Open Anyway** beside
     *KMRP Installer*, and confirm. On earlier versions: Control-click the app, choose
     **Open**, then **Open** again.
   - Or, in Terminal: `xattr -dr com.apple.quarantine "/path/to/KMRP Installer.app"`,
     then open it as usual.
3. The installer finds the game in your Steam libraries (step 1; **Browse** for a copy
   somewhere else) and checks it is the unmodified Steam version (step 2).
4. Step 3 has this display's resolution chosen already. Click it to pick another: this
   display's half size, the sizes of other Macs and displays, grouped by shape, or
   **Custom size…** for any other (see *Options*).
5. Click **Start Patching**. The button fills as it works; step 4 says **Patched
   successfully** when it is done.
6. Start KOTOR from Steam as usual.

What the installer did is in **Open Log** (`~/Library/Logs/KMRP/installer.log`). If macOS
stops it from changing the game ("Operation not permitted"), allow **KMRP Installer** in
**System Settings → Privacy & Security → App Management** and click **Start Patching**
again.

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
- **Controller support**, which the Mac version of KOTOR does not have on its own: KMRP's
  controls from Windows, button prompts drawn for your pad, rumble, and a Controller Layout
  screen. See *Controller* below.

## Controller

Pads are read through SDL, as on Windows, which knows Xbox, PlayStation, Switch Pro and most
other pads. The controls are KMRP's, the same as on Windows: the full list is on the
**Controller Layout** screen, under **Options → Gameplay**.

- Button prompts appear on screen in your pad's style (Xbox, PlayStation, Switch or Steam
  Deck) while you play with the pad, and disappear as soon as you use the mouse or keyboard.
  The mouse pointer hides while the pad is in use and comes back when you move the mouse.
- **Rumble** can be changed in a text file the installer puts next to `swkotor.ini`:
  `~/Library/Application Support/Knights of the Old Republic/kmrp-controller.ini`.

  ```ini
  [Rumble]
  Mode=Enhanced
  Strength=100
  ```

  `Mode` is `Enhanced` (the default: the game's own rumble plus KMRP's), `Original` (only
  what the game had) or `Off`. `Strength` is 0 to 100. The file explains the other settings.
  The game picks up a change within a second, without restarting. Once you edit the file it
  is yours: installing again never overwrites it, and uninstalling leaves it.
- If the pad does not respond, the log `~/Library/Logs/KMRP/controller.log` says what the
  game saw; include it when you report a problem.

## Options

- **Resolution** (Retina displays). *Native* renders every pixel of the screen, for
  example 3024x1964 on a 14" MacBook Pro: the sharpest picture, and the one the installer
  chooses. *Half* renders the size macOS lays out its own windows at (1512x982 there) and
  lets macOS scale it up: lighter on the GPU. At native, set **Anti-aliasing to 2x** in the
  game's graphics options: on an M5, 6x at native ran at about 30 fps in game and 2x at
  about 120.
- **Another display or size**: pick it in step 3, for example for an external monitor. The
  list has the sizes KMRP has a finished menu set for; **Custom size…** takes any other
  from 4:3 to 32:9, and the installer blends a set for it. The interface is laid out for one
  size; to change it later, **Restore Original** and patch again.
- **Without the map-note corrections**: the gear button beside **Start Patching** opens
  **Advanced Settings**; turn off *Area Map Marker Fixes*.
- **From Terminal**, the installer is a script inside the app:
  `"KMRP Installer.app/Contents/Resources/kmrp/kmrp-mac.sh" install` asks the same
  questions; add `--resolution native|half`, `--size 2560x1440`, `--no-map-notes` or
  `--game "/path/to/Knights of the Old Republic.app"`. `uninstall` and `status` work
  the same way.

## Uninstall

Quit KOTOR, open **KMRP Installer** and click **Restore Original**. It restores the
original `KOTOR_Exe`, your settings and every file KMRP replaced, and deletes what it added.
A file you changed after installing is left alone and listed in the log.

## What it changes

- `KOTOR_Exe`: one load command so the game loads KotOR Patch Manager's patcher, then an
  ad-hoc re-signature, exactly as KotOR Patch Manager itself does. The original is kept in
  `~/Library/Application Support/KMRP/macos/backup`.
- Next to `KOTOR_Exe`: `KotorPatcher.dylib`, `patch_config.toml`, `patches/` (the
  widescreen patch by FTD, RaymanGT, J and Vriff, with KMRP's engine fixes, KMRP's own
  patches, and the SDL library the controller support reads pads with).
- `swkotor.ini`: `UseGuiFileLayouts`, `ForceWidth` and `ForceHeight`, under
  `[Graphics Options]`. Uninstall puts back what was there before.
- `kmrp-controller.ini` next to it, the controller settings, if you do not have one yet.
- `Contents/Assets/override`: the interface, fonts and art. Portraits and icons you already
  have from another mod are kept; KMRP's own files replace older copies after saving them.
  A few files are made from your own copy of the game while installing (the enlarged ability
  icons, the list-row frames, the tutorial popup's icons and `tutorial.2da`), because KMRP
  does not ship anything taken from the game.

Steam's **Verify integrity of game files** also restores `KOTOR_Exe`; run the uninstaller
afterwards to clean up the rest.

## If you already use KotOR Patch Manager

KMRP installs the widescreen patch itself, in the version with KMRP's engine fixes. The
installer stops if KotOR Patch Manager patches are already installed, rather than overwrite
them: remove them in KPM first, then install KMRP.

## Credits

KMRP by Rayes Diyab (RaymanGT), GPL-3.0. Widescreen patch by FTD, RaymanGT, J and Vriff, and
KotOR Patch Manager by LaneDibello and contributors, both MIT. The menu layouts derive from
KOTOR High Resolution Menus by ndix UR, GPL-3.0. HD Icon Pack by JackInTheBox, Party Portraits by MadDerp and K1 Area Map Fixes by
Derslok, each bundled with the author's permission. The controller support builds on
Saul0097's KPM – Xbox Controls for KOTOR 1 (MIT, with his permission), reads pads through SDL
(zlib licence), and draws its buttons with Xelu's free controller prompts (CC0). Licences and
notices are in `kmrp/licenses/`.
