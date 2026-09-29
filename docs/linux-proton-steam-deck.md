# Linux, Proton, and Steam Deck compatibility

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It separates the
> reproducible installation procedure and package-level measurements from the
> gameplay coverage that has not yet been performed.

**Kind: compatibility procedure and test record.** KMRP is a Windows patcher for
a Windows game. A community report says the patcher launches through Protontricks,
but KMRP has not yet been play-tested under Proton or on Steam Deck. The procedure
below follows the official Protontricks and Valve Proton interfaces; it is not a
claim of completed gameplay support.

## Installation procedure

KOTOR's Steam App ID is `32370`. Install the Windows build through Steam, select
the Proton version you intend to test in the game's Compatibility properties,
then launch the game once so Steam creates both `swkotor.ini` and its Proton
prefix.

Install [Protontricks](https://github.com/Matoking/protontricks#installation)
using its documented method for your distribution. On Steam Deck, its project
recommends the Discover/Flatpak package. If the game is in a library outside the
default Steam location, grant the Flatpak access to that library as described by
the same installation documentation.

Run the patcher inside KOTOR's Proton environment:

```bash
protontricks-launch --appid 32370 "/absolute/path/to/KMRP - KOTOR Modern Restoration Patch.exe"
```

In the patcher, select the `swkotor.exe` inside the real Steam KOTOR directory,
not the copy of the patcher and not a file under `compatdata`. Steam's usual
location is `steamapps/common/swkotor/swkotor.exe`; the library root varies.
Choose the display's native resolution (Steam Deck LCD/OLED handheld mode is
normally 1280×800), apply, then launch KOTOR normally through Steam.

**Steam's own executable is supported since 2026-09-29.** KMRP's installer no
longer rewrites `swkotor.exe`: it installs KOTOR Patch Manager's runtime, loaded
through KPM's `binkw32.dll` proxy, which applies KMRP in memory when the game
starts ([kpm-edition.md](kpm-edition.md), section 1a). So Steam's `swkotor.exe`
(`34E6D971…`) no longer has to be replaced with the editable one. Measured on
Windows only: **nothing of the new install has been run under Proton**. Wine has
no built-in `binkw32.dll`, so it should load the proxy from the game folder
without a DLL override, but that is untested. Steam's *Verify integrity of game
files* puts Steam's own `binkw32.dll` back, which unloads KMRP until it is
installed again.

*Until 2026-09-29* this said the installer accepted only the editable 1.03
`swkotor.exe` (`761F9466…`) and refused Steam's, because Steam's DRM will not
start a changed file, so Steam's had to be replaced with the editable one before
patching. That still describes any KMRP installer from before that day.

Use the same command to open KMRP and choose **Restore Original**. A reinstall
test is: apply, launch, restore, compare the restored hashes, then apply again.
Do not delete the Proton prefix as a substitute for KMRP restore; the prefix does
not own the executable, INI, or Override files in the Steam library.

The official [`protontricks-launch` documentation](https://github.com/Matoking/protontricks#protontricks-launch)
also documents `PROTON_VERSION` for selecting a specific installed Proton build.
Use that to repeat the same test with Proton Experimental and one current stable
Proton release. KMRP does not recommend one over the other until both have been
measured.

## What is verified without Proton

`testing/regression/Test-ProtonResourceCompatibility.py` reads the final package
archives using case-sensitive comparisons, even when it runs on Windows. On
2026-09-24 it measured the archives embedded in that day's installer; all 48
are byte-identical to the installer's resources:

- 48 of 48 resolution archives present (re-run on 2026-09-25 with the 49th,
  2880x1620: 49 archives, 4,067 GUIs, and `LBL_NAME` resolving at all 49);
- 3,937 packaged GUI resources parsed (3,889 on the 2026-09-05 build, before the
  controller screens were added);
- every GUI font reference resolving to exact-case `.tga` and `.txi` names;
- no case-insensitive duplicate names in an archive;
- no absolute, parent-traversal, backslash, or empty archive member paths; and
- `LBL_NAME` in the active HUD resolving to `dialogfont10x10.tga` and
  `dialogfont10x10.txi` at all 48 resolutions.

This rules out an absent or case-only-mismatched KMRP font resource as the direct
cause of the reported missing NPC and door names. It does **not** prove that
Proton loads or renders that resource correctly. The same target strip had a
separate width-driven geometry defect in the public release; the unreleased
generator now gives it the shared `max(1, height / 720)` scale and verifies its
numeric extent at every resolution.

Run the package audit after a full build:

```powershell
python testing/regression/Test-ProtonResourceCompatibility.py
```

## Collecting a useful report

Before changing a failing installation, capture a read-only report:

```bash
python3 tools/collect_proton_report.py "/absolute/path/to/steamapps/common/swkotor" \
  --output kmrp-proton-report.json
```

The JSON contains file sizes and SHA-256 hashes, selected INI resolution,
presence of KMRP manifests/controller files, the active HUD/font resources, and
case-collision results. It does not include executable bytes, game text, saves,
credentials, or the contents of proprietary resources.

For a Proton failure, set Valve's documented launch option in Steam:

```text
PROTON_LOG=1 %command%
```

Valve documents the resulting log as `$HOME/steam-32370.log`; Proton prefixes
normally live under `steamapps/compatdata/32370/pfx`. Attach the report, Proton
log, KMRP log, exact Proton version, distribution/Steam Deck OS version,
resolution, GPU, and whether K1CP/K1R or another Override mod is installed.
Valve's authoritative configuration reference is the
[Proton README](https://github.com/ValveSoftware/Proton#runtime-config-options).

For missing NPC or door names specifically, compare these cases without deleting
the prefix:

1. a current unreleased KMRP package versus public KMRP 1.0 (tag v2.10.0);
2. KMRP alone versus the same install with K1CP/K1R; and
3. the same save at 1280×800 and 1920×1080.

Those comparisons separate the corrected HUD geometry, an Override precedence
conflict, and a Proton rendering problem. Record which names are absent and
whether the health bar/background still appears; that distinction identifies
text rendering versus whole-control placement.

## Controller and Steam Deck coverage still required

The optional controller component has Windows structural and live-hook checks.
It has also been play-tested on Windows with a physical Xbox controller; the
2026-09-24 results are recorded entry by entry in `CHANGELOG.md`. Nothing has
been run under Proton. There the component also depends on:
- KOTOR Patch Manager's runtime and its `binkw32.dll` proxy, since 2026-09-29
  (until then, the `dinput8.dll` ASI loader, which needed Wine's
  `dinput8=n,b` override; K1DC still does);
- Proton's XInput translation, or the SDL backend for other controllers.

The following remain gameplay tests under Proton, not automated claims:

- movement, camera, combat/action-bar, dialogue, inventory, map, pause, and menus;
- controller connect, disconnect/reconnect, and multiple-device behavior;
- whether Steam Input must be enabled or disabled for the selected controller;
- rumble (KMRP now supplies the engine's rumble table, BioWare's own 22 patterns
  since 2026-09-25, so it works on Windows; see *Rumble works* and *Rumble uses
  BioWare's own patterns* in `CHANGELOG.md`. The Enhanced haptics and the mixer
  of the same day are untested on any platform: `docs/controller-rumble.md`);
- suspend/resume and handheld/docked switching on Steam Deck; and
- patch, restore, and reinstall under Proton Experimental and stable Proton.

(Until 2026-09-24 this section said no physical XInput device was available and
that there was no KMRP rumble claim. Both predate the controller work recorded in
`CHANGELOG.md`.)

## Deliberately not changed

- KMRP does not install Wine, Proton, Protontricks, Steam, or Flatpak permissions.
- It does not weaken executable hash validation for a Wine/Proton path.
- The package audit does not label archive inspection as gameplay verification.
- No Proton version is advertised as supported until the matrix above is run.

