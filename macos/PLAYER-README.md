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
2. Open **KMRP-macOS-1.5.0.dmg** and drag **KMRP Installer** onto **Applications**, then
   open it from Applications. (From the `.zip`, if that is the download you have: open
   **KMRP Installer** from the unzipped folder.)
   - KMRP is not signed by an Apple developer account, so the first time macOS asks you to
     allow it. On macOS 15 and later: macOS says it cannot open it; click **Done**, open
     **System Settings → Privacy & Security**, scroll down, click **Open Anyway** beside
     *KMRP Installer*, and confirm. On earlier versions: Control-click the app, choose
     **Open**, then **Open** again.
   - Or, in Terminal: `xattr -dr com.apple.quarantine "/path/to/KMRP Installer.app"`,
     then open it as usual.
3. The installer finds the game in your Steam libraries (step 1; **Browse** for a copy
   somewhere else) and checks it is the unmodified Steam version (step 2).
4. Step 3 says the resolution the game will start at: the one macOS is set to, as
   **System Settings → Displays** shows it (1512 × 982 on a 14" MacBook Pro by default).
   There is nothing to choose: the game lists every resolution the connected display
   supports (see *Options*).
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
  all); for any other size KMRP blends one from the sets around it, the first time the game
  starts at that size.
- **HD fonts** baked for your resolution, sharp at any size.
- **KMRP's engine fixes**: no hang on long item descriptions, stack counts that stay
  visible, list rows that stop growing, no blank first line in descriptions, a dialogue
  letterbox that works on any display with a reply list that fills it, and a minimap at the
  vanilla zoom. On a Retina Mac, the screen's full resolution if you choose it in the game.
- **HD art**: JackInTheBox's HD Icon Pack, MadDerp's Party Portraits, KMRP's HD interface
  textures, and feat, power and skill icons enlarged to fit KMRP's rows. Item icons are
  sized to sit in their slots the way the game's own do.
- **250 map notes moved to where they belong** (Derslok's K1 Area Map Fixes).
- **Controller support**, which the Mac version of KOTOR does not have on its own: KMRP's
  controls from Windows, button prompts drawn for your pad, rumble, an Xbox-style HUD while
  you play with the pad, and a Controller Layout screen. See *Controller* below. On by
  default; it can be turned off (*Options*).
- **High FPS Fix**: D3M0's High FPS Fixes, ported to the Mac game. Above 60 frames per second
  the game's timing goes wrong in places (the dialogue's black bars, standing still after a
  fight, water, particles and other animation); this makes them run by time. On by itself
  where your display runs above 60 Hz, as a MacBook Pro's does; it can be turned on or off
  (*Options*).

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
- **Xbox-style HUD.** While you play with the pad the in-game HUD is laid out like the
  original Xbox version's: the action slots in a box at the bottom left, the target's name at
  the top left, the party at the bottom right. With the mouse or keyboard the game's own HUD
  comes back. To keep the game's own HUD with the pad as well, set `Style=PC` under `[Hud]`
  in the same file; it is read when the game starts.

  ```ini
  [Hud]
  Style=PC
  ```
- If the pad does not respond, turn on **Debug Logs** in Advanced Settings and install again:
  the log `~/Library/Logs/KMRP/controller.log` then says what the game saw; include it when
  you report a problem.

## Options

- **Resolution.** Nothing to choose when installing. The game starts at the resolution macOS
  is set to (1512x982 on a 14" MacBook Pro by default; whatever **System Settings →
  Displays** says if you changed it), and every size your display offers is in the game under
  **Options → Graphics → Screen Resolution**, the Retina size among them (3024x1964 there:
  sharper, and heavier on the GPU). A change takes effect at once and is kept for the next
  start, as long as the display then connected supports it; otherwise the game starts at
  that display's own size. The list is whatever the connected display supports when the game
  starts: connect another display, start the game, and it offers that display's sizes.
  At Retina, set **Anti-aliasing to 2x** in the game's graphics options: on an M5, 6x at
  3024x1964 ran at about 30 fps in game and 2x at about 120.
- **Without the map-note corrections, the HD icons or controller support, and High FPS Fix
  on or off**: the gear button beside **Start Patching** opens **Advanced Settings**, as on
  Windows, with a tile for each: *Native Controller Support*, *Area Map Marker Fixes*, *HD
  Item Icons*, *High FPS Fix* and *Debug Logs*. The first three are on unless you turn them
  off; *High FPS Fix* is on where your display runs above 60 Hz and off on a 60 Hz display,
  until you set it yourself. The installer remembers your choice, and **Restore Defaults**
  puts every tile back. With *HD Item Icons* off the game shows its own
  item icons instead of JackInTheBox's HD Icon Pack; everything else stays. Without controller support the game has none: the Mac version of
  KOTOR has no pad support of its own. *Debug Logs*, off unless you turn it on, is there too.
- **From Terminal**, the installer is a script inside the app:
  `"KMRP Installer.app/Contents/Resources/kmrp/kmrp-mac.sh" install`. On a Retina display it
  asks whether the game should start at the resolution macOS is set to or at the Retina
  size, then asks before it installs; add `--resolution current|native`, `--size 2560x1440`,
  `--no-map-notes`, `--no-hd-icons`, `--no-controller`, `--high-fps` or `--no-high-fps`,
  `--debug-logs`, `--yes` or
  `--game "/path/to/Knights of the Old Republic.app"`. `uninstall` and `status` work the same
  way.

## Uninstall

Quit KOTOR, open **KMRP Installer** (in Applications) and click **Restore Original**. It restores the
original `KOTOR_Exe`, your settings and every file KMRP replaced, and deletes what it added.
A file you changed after installing is left alone and listed in the log.

## What it changes

- `KOTOR_Exe`: one load command so the game loads KotOR Patch Manager's patcher, then an
  ad-hoc re-signature, exactly as KotOR Patch Manager itself does. The original is kept in
  `~/Library/Application Support/KMRP/macos/backup`.
- Next to `KOTOR_Exe`: `KotorPatcher.dylib`, `patch_config.toml`, KotOR Patch Manager's own
  record of the install (`kpm_install_state.json` and a copy of the untouched game,
  `KOTOR_Exe.backup.<date>`), `configs/` with each patch's options (`kmrp.ini`,
  `kmrp-controller.ini`), and `patches/`, which holds up to five KotOR Patch Manager patches:
  FTD's Widescreen Patch and Stray Bug Fixes, KMRP's own (`kmrp.dylib`, with the interface
  for every resolution inside it), while Native Controller Support is on the controller's
  (`kmrp-controller.dylib`, which also works in a game without KMRP), and while High FPS Fix
  is on High FPS Fixes (`high-fps-fixes.dylib`, which works by itself too).
- `swkotor.ini`: the resolution the game starts at, under `[Graphics Options]`. Uninstall
  puts back what was there before, unless you have chosen another resolution in the game
  since, which stays.
- Aspyr's launcher is set to start the game full screen. Uninstall puts that back too,
  unless you changed it yourself afterwards.
- `kmrp-controller.ini` next to `swkotor.ini`, the controller settings, if you do not have
  one yet.
- Nothing in `Contents/Assets/override`. The interface, fonts and art are inside KMRP's
  patch and are unpacked to `~/Library/Caches/KMRP` when the game starts; the controller's
  to `~/Library/Caches/KMRP-Controller`. A few files are made there from your own copy of
  the game (the enlarged ability icons, the list-row frames, the tutorial popup's icons and
  `tutorial.2da`), because KMRP does not ship anything taken from the game. Uninstall leaves
  these two cache folders; you can delete them.

Steam's **Verify integrity of game files** also restores `KOTOR_Exe`; run the uninstaller
afterwards to clean up the rest.

## If you already use KotOR Patch Manager

KMRP for macOS is five KotOR Patch Manager patches that work together. KMRP Installer
installs them itself, and when you have KotOR Patch Manager it also puts the files in KPM's
patch folder, so KPM lists them:

| File | Name in KotOR Patch Manager |
| --- | --- |
| `K1StrayBugFixes.kpatch` | Stray Bug Fixes (FTD's) |
| `K1WidescreenPatch.kpatch` | Widescreen Patch (beta) (FTD's) |
| `KMRP-macOS.kpatch` | KMRP for macOS; it needs the two above ticked with it |
| `KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch` | KOTOR 1 Native Controller Mod + Xbox HUD (macOS); it needs none of the others, and works in a game without KMRP |
| `High FPS Fixes (macOS).kpatch` | High FPS Fixes (macOS), D3M0's patch ported to the Mac; it needs none of the others. Delivered while High FPS Fix is on |

**The two KMRP files and High FPS Fixes (macOS) in this package work on the Mac only.** The Windows package has files
for the same two patches, `KMRP.kpatch` and `KOTOR 1 Native Controller Mod + Xbox
HUD.kpatch`, and those work on Windows only. Use the files that came with the package for
your system. (Before 8 October 2026 the Mac files were named `kmrp.kpatch` and
`kmrp-controller.kpatch`; the installer removes those from KPM's patch folder so the patches
are not listed twice.)

- **FTD's Widescreen Patch and Stray Bug Fixes already installed through KPM, and nothing
  else:** KMRP Installer replaces that install. It puts back the untouched game from KPM's
  copy, removes the patch files beside the game, and installs its patches, FTD's two
  among them in the version KMRP was built with. Restore Original then leaves the untouched
  game; install FTD's patches in KPM again if you want them without KMRP.
- **Other KotOR Patch Manager patches installed:** KMRP Installer installs for KPM, as on
  Windows. It writes the resolution, the full-screen setting and the controller settings,
  leaves the game and KPM's files as they are, and puts its files in KPM's patch
  folder. Open KPM, tick **KMRP for macOS**, **Widescreen Patch (beta)** and **Stray Bug
  Fixes** (and the controller patch if you
  want it, and **High FPS Fixes (macOS)** if you want that), and press Apply. The options (map notes, debug logs, the Xbox-style HUD) are
  then chosen in KPM, if your version of KPM offers patch options.
- **An install KMRP Installer made by itself:** KPM recognises it as its own, lists the
  patches and can apply others beside them. If you press Apply in KPM with only KMRP's
  patches ticked, Restore Original still puts back the untouched game. With other KPM
  patches beside KMRP's, it removes KMRP's own files and leaves the rest to KPM: then untick
  KMRP's patches in KPM and press Apply.

## Credits

KMRP by Rayes Diyab (RaymanGT), GPL-3.0. High FPS Fixes by D3M0, MIT, ported to the Mac by RaymanGT. Widescreen patch by FTD and RaymanGT,
Stray Bug Fixes by RaymanGT and FTD, and KotOR Patch Manager by LaneDibello and contributors,
all MIT. The menu layouts derive from
KOTOR High Resolution Menus by ndix UR, GPL-3.0. HD Icon Pack by JackInTheBox, Party Portraits by MadDerp and K1 Area Map Fixes by
Derslok, each bundled with the author's permission. The controller support builds on
Saul0097's KPM – Xbox Controls for KOTOR 1 (MIT, with his permission), reads pads through SDL
(zlib licence), and draws its buttons with Xelu's free controller prompts (CC0). Licences and
notices are inside the app, in `Contents/Resources/kmrp/licenses`.
