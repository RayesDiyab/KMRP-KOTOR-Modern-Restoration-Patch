KMRP's patches for KOTOR Patch Manager
======================================

The KOTOR Modern Restoration Patch as two patches for KOTOR Patch Manager
(KPM), for players who manage their patches with KPM. They make the same
changes KMRP's installer makes on its own, and never modify swkotor.exe:
KPM applies them when the game starts, so KMRP can be combined with other
KPM patches.

If you do not use KOTOR Patch Manager, you do not need this: KMRP's
installer, "KMRP - KOTOR Modern Restoration Patch.exe", installs KPM's
runtime itself, for the editable swkotor.exe, GOG's and Steam's alike, and
you start the game as usual.

  KMRP.kpatch
      The widescreen and high-resolution interface at any resolution your
      display supports, with the 4 GB, texture, grass and save-game memory
      fixes and the movie fixes (movies at your resolution, fitted to
      their aspect, black around them) built in. Everything it needs is
      inside the file: nothing goes into Override.

      Options:
        Map notes       Derslok's area-map marker fixes          (on)
        HD item icons   JackInTheBox's high-resolution icons     (on)
        Debug logs      diagnostic log files beside the game     (off)

  KOTOR 1 Native Controller Mod + Xbox HUD.kpatch
      Controller support: the pad in the game and in every menu, button
      prompts for Xbox, PlayStation, Switch and Steam Deck pads, rumble
      and the Controller Layout screen. It is in this folder when
      Controller Support was on in KMRP's installer.

      Options:
        Xbox-style HUD   the in-game HUD laid out like the original Xbox
                         version's while the pad is in use         (on)
        Debug logs       diagnostic log files beside the game      (off)

  HighFpsFixes.kpatch   (only if High FPS Fix was on in KMRP's installer)
      D3M0's High FPS Fixes 1.0.1, unchanged: timing and animation fixes
      for play above 60 frames per second. It is not KMRP's work; its
      home is https://github.com/gnw-d3m0/D3M0s-KPatches (MIT licence,
      Copyright (c) 2026 D3M0). It has no options.

Each patch works without the other. Tick both for KMRP with a controller,
KMRP.kpatch alone for mouse and keyboard, or the controller patch alone
for a game without KMRP.

A KOTOR Patch Manager with patch options shows them in a patch's details
and records what you chose in configs\kmrp.ini and
configs\kmrp-controller.ini in the game folder. An older one (0.7.1)
installs each patch with its options as listed above.

Requirements
------------
- KOTOR 1, version 1.03, with one of
    the "editable" swkotor.exe (SHA-256 761F9466...),
    GOG's own swkotor.exe (SHA-256 9C10E045...), or
    Steam's own swkotor.exe (SHA-256 34E6D971...).
- KOTOR Patch Manager 0.7.1 or later.

Install
-------
1. Put the .kpatch files in KOTOR Patch Manager's patch folder. KMRP's
   installer does this for you when it finds KPM on the PC.
2. Open KPM, tick "KMRP - KOTOR Modern Restoration Patch" and, for a
   controller, "KOTOR 1 Native Controller Mod + Xbox HUD", and press
   Apply. Leave KPM's own 4 GB, texture bucket, grass and save-game memory
   patches unticked: KMRP includes them, and KPM will say they conflict.
3. Start the game with Launch. Choose your resolution in the game, under
   Options, Graphics, Screen Resolution: it lists every resolution your
   display supports.

Steam: choose the proxy deployment in KPM and start the game from Steam.
Steam's swkotor.exe cannot take the 4 GB flag.

Patches KMRP replaces
---------------------
Until October 2026 KMRP came as four patches: KMRP, KMRP Controller, KMRP
Movies and KMRP Map Notes. These two replace all four. If the older ones
are still in your patch folder, remove them or leave them unticked.

Licences
--------
KMRP is GPL-3.0. Each patch file carries its licence and the notices of
the work it includes in its "licenses" folder. KOTOR Patch Manager's
licence is LICENSE-KOTOR-PATCH-MANAGER.txt beside this file.
