KMRP's patch for KOTOR Patch Manager
====================================

The KOTOR Modern Restoration Patch as one patch for KOTOR Patch Manager
(KPM), for players who manage their patches with KPM. It makes the same
changes KMRP's installer makes on its own, and never modifies swkotor.exe:
KPM applies it when the game starts, so KMRP can be combined with other KPM
patches.

If you do not use KOTOR Patch Manager, you do not need this: KMRP's
installer, "KMRP - KOTOR Modern Restoration Patch.exe", installs KPM's
runtime itself, for the editable swkotor.exe, GOG's and Steam's alike, and
you start the game as usual.

  KMRP.kpatch   the widescreen and high-resolution interface at the
                resolution you choose in the game, with the 4 GB, texture,
                grass and save-game memory fixes and the movie fixes
                (movies at your resolution, fitted to their aspect, black
                around them) built in. Everything it needs is inside the
                file: nothing goes into Override.

It has three options:

  Controller support   Xbox, PlayStation, Switch and Steam Deck pads   (on)
  Map notes            Derslok's area-map marker fixes                 (on)
  Debug logs           diagnostic log files beside the game            (off)

A KOTOR Patch Manager with patch options shows them in the patch's details
and records what you chose in configs\kmrp.ini in the game folder. An older
one (0.7.1) installs the patch with the first two on and no logs.

Requirements
------------
- KOTOR 1, version 1.03, with one of
    the "editable" swkotor.exe (SHA-256 761F9466...),
    GOG's own swkotor.exe (SHA-256 9C10E045...), or
    Steam's own swkotor.exe (SHA-256 34E6D971...).
- KOTOR Patch Manager 0.7.1 or later.

Install
-------
1. Put KMRP.kpatch in KOTOR Patch Manager's patch folder. KMRP's installer
   does this for you when it finds KPM on the PC.
2. Open KPM, tick "KMRP - KOTOR Modern Restoration Patch" and press Apply.
   Leave KPM's own 4 GB, texture bucket, grass and save-game memory patches
   unticked: KMRP includes them, and KPM will say they conflict.
3. Start the game with Launch. Choose your resolution in the game, under
   Options, Graphics, Screen Resolution.

Steam: choose the proxy deployment in KPM and start the game from Steam.
Steam's swkotor.exe cannot take the 4 GB flag.

Patches KMRP replaces
---------------------
Until October 2026 KMRP came as four patches: KMRP, KMRP Controller, KMRP
Movies and KMRP Map Notes. This one patch replaces all four. If the other
three are still in your patch folder, remove them or leave them unticked.

Licences
--------
KMRP is GPL-3.0. The patch file carries its licence and the notices of the
work it includes in its "licenses" folder. KOTOR Patch Manager's licence is
LICENSE-KOTOR-PATCH-MANAGER.txt beside this file.
