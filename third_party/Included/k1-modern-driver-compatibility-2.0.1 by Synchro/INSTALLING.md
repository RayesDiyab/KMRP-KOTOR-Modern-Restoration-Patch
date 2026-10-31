# Installing K1 Modern Driver Compatibility

To install version 2.0.1 of the patch, you need the
[KotOR Patch Manager](https://github.com/LaneDibello/Kotor-Patch-Manager), version 0.7.2 or
later.

The patch doesn't change `swkotor.exe` on disk. The Patch Manager applies the patch to the game
as it starts, and you can turn the patch off in the Patch Manager.

## Install the patch

1. Download the zip file from the
   [releases page](https://codeberg.org/Synchro/kotor-modern-driver-compatibility/releases), and
   unzip it.
2. Move the `.kpatch` file out of the `Copy into patches folder` folder and into the folder that
   your Patch Manager reads patches from. The Patch Manager's release includes a `patches`
   folder for this. Move the file itself, not the folder that contains it.
3. Open the Patch Manager. Set **Game** to your `swkotor.exe`, and set **Patches** to the folder
   from step 2. The patch appears in the Patch Manager's list of patches.
4. Select the patch's checkbox, and then select **Apply**.
5. Start the game with the Patch Manager's **Launch** button. On Linux, if you play through
   Proton, you can start the game the way you usually do instead.

You don't need to copy anything into your game folder. The Patch Manager adds the files it needs
there itself.

On Windows, the Patch Manager by default applies the patch only to a game it starts. If you
start the game from Steam or a desktop shortcut instead of the **Launch** button, the game runs
without the patch, and the game looks as if the patch does nothing. To have the patch load
however you start the game, turn on the Patch Manager's library proxy, as
[Load the patch however you start the game](#load-the-patch-however-you-start-the-game)
describes.

## Load the patch however you start the game

On Windows, you can have the patch load whenever the game starts, from Steam, a desktop
shortcut, or **Launch**, by using the Patch Manager's library proxy:

1. If any patches are installed, clear their checkboxes, and then select **Apply**. The Patch
   Manager lets you change this option only while no patches are installed.
2. In the **Options** menu, select **Use library proxy**.
3. Select the patches again, and then select **Apply**.

With the library proxy, the Patch Manager puts a stand-in `binkw32.dll` in your game folder and
renames the game's own copy to `binkw32Hooked.dll`. The game loads `binkw32.dll` every time it
starts, and the stand-in loads the patch. On Linux, the Patch Manager always uses this method.

## What appears in your game folder

The first time you run the game with the patch, the patch creates two files:

- `logs/K1DriverCompat.log` records one session, and the patch replaces it each time the game
  starts. If something looks wrong, send this file.
- `K1DriverCompat.ini` lists every setting the patch has, with an explanation of each, all
  commented out. You don't need to change either file to play. For more information, see
  [Settings](https://synchro.codeberg.page/kotor-modern-driver-compatibility/settings.html).

If the Mod Options patch is installed, the patch also writes two menus for its settings into
the `Mod Options` folder, `K1DriverCompat.toml` and `K1DriverCompat Troubleshooting.toml`. They
appear in the game's options screen.

The first run also turns on soft shadows and the screen effects in the game's own graphics
options. The Steam release's settings file has soft shadows off, and the game's options menu
saved both off on cards that the unpatched game judged unable to run them. The patch does this
only on the run that creates `K1DriverCompat.ini`. If you turn either option off afterwards, it
stays off unless you delete that file.

## Troubleshooting

### The patch needs a newer Patch Manager

**Cause:** version 2.0.0 and later of the patch passes values from the game's registers, and
fixed values, to its hooks. The Patch Manager supports both from version 0.7.2, and earlier
versions can't install those hooks.

**Solution:** check the Patch Manager's version, and update it to 0.7.2 or later.

## Uninstall the patch

In the Patch Manager, clear the patch's checkbox, and then select **Apply**. The Patch Manager
removes the files it added.

Some things stay behind. `logs/K1DriverCompat.log` and `K1DriverCompat.ini` remain in your game
folder, and so do the two menus in `Mod Options` if the patch wrote them. You can delete all of
them. Soft shadows and the screen effects stay on in the game's
graphics options until you turn them off there.

## Compatibility

The patch works with version 1.03 of the game as GOG and Steam ship it. It also works with the
`1.03` executable that CD copies run with the common no-CD crack.

The patch includes the separate cube map fix and soft shadow fix. Don't install either of them
alongside this patch.
