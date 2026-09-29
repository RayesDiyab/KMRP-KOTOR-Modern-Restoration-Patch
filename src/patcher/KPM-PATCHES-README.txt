KMRP's patches for KOTOR Patch Manager
======================================

The KOTOR Modern Restoration Patch as four patches for KOTOR Patch Manager
(KPM), for players who manage their patches with KPM. They make the same
changes KMRP's installer makes on its own, and never modify swkotor.exe: KPM
applies them when the game starts, so KMRP can be combined with other KPM
patches.

If you do not use KOTOR Patch Manager, you do not need these: KMRP's
installer, "KMRP - KOTOR Modern Restoration Patch.exe", installs KPM's
runtime itself, for the editable swkotor.exe and Steam's alike, and you start
the game as usual.

  KMRP - KOTOR Modern Restoration Patch   required: the widescreen and
                                          high-resolution interface, with
                                          the 4 GB, texture, grass and
                                          save-game memory fixes built in
  KMRP Controller                         controller support
  KMRP Movies                             movies at your resolution, fitted
                                          to their aspect, black around them
  KMRP Map Notes                          Derslok's area-map marker fixes

Requirements
------------
- KOTOR 1, version 1.03, with either
    the "editable" swkotor.exe (SHA-256 761F9466...), or
    Steam's own swkotor.exe (SHA-256 34E6D971...).
  GOG's executable is not supported yet.
- KOTOR Patch Manager 0.7.1 or later.

Install
-------
1. Run KMRP's installer, "KMRP - KOTOR Modern Restoration Patch.exe", choose
   your KOTOR folder and a resolution. If KOTOR Patch Manager already manages
   the game folder, the installer sees it and installs for KPM by itself;
   otherwise open Advanced Settings and turn on "KOTOR Patch Manager" first.
   Then press Start Patching. This installs KMRP's interface files, sets the
   resolution in swkotor.ini, and writes kmrp-kpm.dat, the data KMRP's
   patches read. swkotor.exe is not modified. An earlier KMRP install is
   replaced.
2. In KOTOR Patch Manager, set the patch directory to this folder (or copy
   the four .kpatch files into your own patch directory).
3. Tick "KMRP - KOTOR Modern Restoration Patch", and any of KMRP Controller,
   KMRP Movies and KMRP Map Notes. Leave KPM's own 4GB Patch, Texture Bucket
   Safety, Grass Memory Safety and Save Game Memory Leak unticked: KMRP
   already makes those fixes, and KPM refuses both at once.
4. Press Apply, then start the game with Launch.

Steam players, in addition:
- Before pressing Apply, switch KOTOR Patch Manager to the proxy
  deployment (binkw32.dll). Steam's swkotor.exe hands its own start over to
  Steam, so KPM's default, injecting into the game it starts, never reaches
  the game that actually runs.
- Start the game from Steam as usual.
- Steam refuses to start its swkotor.exe if the file is changed at all, so
  on Steam the game runs without the 4 GB flag. KMRP has not been seen to
  need it; it is a safety margin the editable executable gets.

To add or remove one of the optional patches, tick or untick it in KOTOR
Patch Manager and press Apply. To change the resolution, run KMRP's
installer again. To remove KMRP, run it and press Restore Original, then
untick the KMRP patches in KOTOR Patch Manager and press Apply.

Until 2026-09-29 these came with an installer of their own, "KMRP for
KPM.exe"; KMRP's installer does its job now.

Not compatible with
-------------------
KMRP: Map Texture Patch and Scaled Kotor (they change the same things), and
KPM's 4GB Patch, Texture Bucket Safety, Grass Memory Safety and Save Game
Memory Leak (KMRP makes the same fixes itself).
KMRP Movies: Movie Patch -- use one or the other.
KMRP Controller: Expanded Keyboard Control and Xbox Controls K1.
KPM refuses these combinations itself.

If KMRP does not take effect, kmrp-kpm.log in the game folder says why.
Nothing is applied unless every byte KMRP changes is exactly what it expects.
