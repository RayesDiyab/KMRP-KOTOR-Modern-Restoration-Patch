# Installing without the Patch Manager

If the KotOR Patch Manager accepts your game, use
[the standard install](https://synchro.codeberg.page/kotor-modern-driver-compatibility/installing.html) instead.
It leaves `swkotor.exe` unchanged on disk, and you can turn the patch off in the Patch Manager.

This install is for one case: another tool has already modified your `swkotor.exe`, so the Patch
Manager doesn't recognise it and refuses to patch it. Examples include an executable patched to
use more memory, patched for a widescreen resolution, or unpacked from a store's wrapper. This
install checks only the places in the game that the patch changes, so other modifications don't
stop it.

The install adds two files to your game folder and renames nothing. If your game folder already
has a `dinput8.dll`, copying replaces it. If that file is another mod's copy of Ultimate ASI
Loader, you can keep it and copy only the `.asi` file.

## Install the patch

1. Download the standalone zip file from the
   [releases page](https://codeberg.org/Synchro/kotor-modern-driver-compatibility/releases), and
   unzip it.
2. Copy both files from the `Copy into game folder` folder into your game folder, which is the
   folder that contains `swkotor.exe`. The files are `dinput8.dll` and
   `k1-modern-driver-compatibility.asi`.
3. On Linux, set the environment variable that the next section describes. On Windows, skip this
   step.
4. Start the game the way you usually do, for example from Steam, a desktop shortcut, or
   Proton.

You don't need to open a manager or configure anything.

## On Linux, through Wine or Proton

On Linux, this step is required. Wine includes its own `dinput8.dll` and uses it in place of the
one in your game folder, so unless you tell Wine otherwise, the game starts without the patch.

Set this environment variable when you start the game:

```
WINEDLLOVERRIDES="dinput8=n,b"
```

For a Steam game, add it to the game's launch options, followed by `%command%`:

```
WINEDLLOVERRIDES="dinput8=n,b" %command%
```

In Lutris or Heroic, use the DLL overrides screen instead: add `dinput8` and set it to
`native, builtin`. This setting tells Wine to load the file in the game folder first, and to
use its own only if that file is missing.

## Check that the patch is working

The first time you run the game with the patch, the patch creates `logs/K1DriverCompat.log` in
your game folder. Look for these two lines, in this order. Each line in the log also starts with
the time since the game started and a level, such as `[INFO]`.

```
hooks installed=21/21 waited=0.000
capability ati_fragment_shader=accepted
```

- The `hooks installed` line means that the patch changed the game. Both numbers must be the
  same.
- The `capability` line means that the game reached the patch in time.

If the log has the first line but not the second, and you haven't set
[`decline = on`](https://synchro.codeberg.page/kotor-modern-driver-compatibility/settings.html), the patch loaded too late to take effect. Report it, and include
the log.

If the log says `hooks nothing matched`, the patch couldn't change any place in the game. The log
gives the reason for each place. If a place holds bytes the patch didn't expect, your executable
isn't one that this patch can change.

## Troubleshooting

### The game starts, but no log appears

**Cause:** the game didn't load the patch. This usually has one of two causes:

- On Linux, the `WINEDLLOVERRIDES` environment variable isn't set.
- On Windows, `dinput8.dll` isn't in the same folder as `swkotor.exe`, for example because it's
  still in the folder from the zip file.

**Solution:** on Linux, set the environment variable as the preceding section describes. On
Windows, move `dinput8.dll` and `k1-modern-driver-compatibility.asi` into the folder that
contains `swkotor.exe`.

### The patch doesn't take effect with the standard install also active

**Cause:** this install and the standard install change the same places in the game. Whichever
runs second finds those places already changed, and doesn't apply.

**Solution:** use only one of the two installs.

## What appears in your game folder

The first time you run the game with the patch, the patch creates the same two files as the
standard install:

- `logs/K1DriverCompat.log` records one session, and the patch replaces it each time the game
  starts. If something looks wrong, send this file.
- `K1DriverCompat.ini` lists every setting the patch has, with an explanation of each, all
  commented out. You don't need to change either file to play. For more information, see
  [Settings](https://synchro.codeberg.page/kotor-modern-driver-compatibility/settings.html).

The first run also turns on soft shadows and the screen effects in the game's own graphics
options. The Steam release's settings file has soft shadows off, and the game's options menu
saved both off on cards that the unpatched game judged unable to run them. The patch does this
only on the run that creates `K1DriverCompat.ini`. If you turn either option off afterwards, it
stays off unless you delete that file.

## Uninstall the patch

Delete `dinput8.dll` and `k1-modern-driver-compatibility.asi` from your game folder.

Two things stay behind. `logs/K1DriverCompat.log` and `K1DriverCompat.ini` remain in your game
folder, and you can delete them. Soft shadows and the screen effects stay on in the game's
graphics options until you turn them off there.

## Compatibility

This install works with version 1.03 of the game as GOG and Steam ship it, and with the `1.03`
executable that CD copies run with the common no-CD crack. It also works with copies that another
tool has already modified, as long as that tool didn't change one of the places this patch
changes. The log names any such place.

The patch includes the separate cube map fix and soft shadow fix. Don't install either of them
alongside this patch.

`dinput8.dll` is Ultimate ASI Loader, which isn't part of this patch. Its licence terms, and
those of everything built into it, are in `THIRD-PARTY-NOTICES`.
