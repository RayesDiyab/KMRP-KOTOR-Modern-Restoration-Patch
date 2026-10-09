# Linux, Proton, and Steam Deck compatibility

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It separates the
> reproducible installation procedure and package-level measurements from the
> observed gameplay and the coverage that remains untested.

**Kind: compatibility procedure and test record.** KMRP is a Windows patcher for
a Windows game. Installer 1.5.0 passed install/restore tests under Proton
Experimental on Ubuntu on 2026-10-01, followed by limited gameplay at 3440×1440:
dialogue, save/load, NPC labels, menus, and virtual Xbox movement and camera.
Stable Proton was untested in that record, and the Steam Deck still is. The
procedure below follows the
official Protontricks and Valve Proton interfaces; the test record distinguishes
the tested direct Proton/Sniper launch from the community-reported Protontricks
launcher and does not claim full hardware or gameplay coverage.

**What that test did not cover (added 2026-10-08).** The installer tested on
2026-10-01 (`7C8CB153…`) installed four patches, a data file and about 1,850
`Override` files. The installer built since 2026-10-04 installs none of those:
KMRP's module carries every resolution's files and unpacks the set in use to a
folder under the user's temporary folder, the controller is a second patch since
2026-10-05, and since 2026-10-07 the game lists the sizes the display reports.
**None of that has been run under Proton**: the records below, including every
count of Override files and "KMRP's four components", describe the 2026-10-01
build.

**The maintainer's later test (reported 2026-10-08).** A development build of 1.5
from after 2026-10-04, so one that writes nothing to `Override` and offers the
resolution in the game, was installed and played by the maintainer on Ubuntu under
the stable Proton of the day and under Proton Experimental, and worked. This is
his report, not a measured record like the one below: the build's hash, the two
Proton versions, the Ubuntu version, the resolution and what was played were not
written down. It lifts two statements of this page, "stable Proton untested" and
"none of that has been run under Proton", for that build. **Still not done:** the
released 1.5 installer itself under Proton, any distribution other than Ubuntu,
and a Steam Deck, which is why the two are named separately wherever KMRP's
platforms are listed.

**Correction, 2026-10-01:** this page previously said no Proton gameplay or
native hook execution had been tested. The initial installer-only record was
superseded by the launch, menu and gameplay checks below.

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
protontricks-launch --appid 32370 "/absolute/path/to/KMRP-Windows-1.5.0.exe"
```

In the patcher, select the `swkotor.exe` inside the real Steam KOTOR directory,
not the copy of the patcher and not a file under `compatdata`. Steam's usual
location is `steamapps/common/swkotor/swkotor.exe`; the library root varies.
Apply, then launch KOTOR normally through Steam. No resolution is chosen in the
installer since 2026-10-04: the game starts at the display's current size (Steam
Deck LCD/OLED handheld mode is normally 1280×800) and any other size the display
reports is chosen in the game; since 2026-10-07 the installer has no resolution
control at all. Not run under Proton with that build, so what display modes
Proton reports to the game, and which sizes its list then shows, is unmeasured.

**Steam's own executable is supported since 2026-09-29.** KMRP's installer no
longer rewrites `swkotor.exe`: it installs KOTOR Patch Manager's runtime, loaded
through KPM's `binkw32.dll` proxy, which applies KMRP in memory when the game
starts ([kpm-edition.md](kpm-edition.md), section 1a). So Steam's `swkotor.exe`
(`34E6D971…`) no longer has to be replaced with the editable one. Measured on
Windows originally; the installer's file operations were subsequently tested
on Ubuntu on 2026-10-01. The game subsequently loaded KPM and applied all 81
engine guard runs under Proton Experimental; the controller hooks accepted
virtual Xbox input. The Bink proxy loaded from the game folder without an added
Bink DLL override in this test. Steam's *Verify integrity of game
files* puts Steam's own `binkw32.dll` back, which unloads KMRP until it is
installed again.

*Until 2026-09-29* this said the installer accepted only the editable 1.03
`swkotor.exe` (`761F9466…`) and refused Steam's, because Steam's DRM will not
start a changed file, so Steam's had to be replaced with the editable one before
patching. That still describes any KMRP installer from before that day.

Use the same command to open KMRP and choose **Restore Original**. A reinstall
test is: apply, launch, restore, compare the restored hashes, then apply again.
Do not delete the Proton prefix as a substitute for KMRP restore; the prefix does
not own the executable, the INI or KMRP's files in the Steam library.

The official [`protontricks-launch` documentation](https://github.com/Matoking/protontricks#protontricks-launch)
also documents `PROTON_VERSION` for selecting a specific installed Proton build.
Use that to repeat the same test with Proton Experimental and one stable Proton
release. **Tested choice:** Proton Experimental
`experimental-11.0-20260924-x86_64` is the reproducible choice from the Ubuntu
record below. Stable Proton has not been compared, so no superiority is claimed.

## Ubuntu installer test (2026-10-01)

Installer 1.5.0, 168,698,880 bytes, SHA-256
`7C8CB15327EA353564CAFCF3F52E1459EBDC80178145AF9E4044A88565877B38`,
was cross-built from source on Ubuntu 26.04.1 LTS, with Steam's texture pack as
its only game-derived build input. No editable EXE or gold snapshot was present.
See [the cross-build record](windows-engine-source.md#ubuntu-cross-build-and-installation-record-2026-10-01)
for native artifact identities and package checks.

The installer ran inside Steam App 32370's existing prefix using Proton
Experimental `experimental-11.0-20260924-x86_64` and Steam's Sniper runtime.
Its `--in-place` and `--restore` commands passed at 3440×1440 and 1920×1080 in
isolated Steam fixtures: 1,526 installed Override files per resolution matched
the build archives, and restore recovered the exact EXE, INI and Bink hashes.
The live Steam copy was subsequently installed at 3440×1440, after a copy-aside
checkpoint. Its EXE remained unchanged and all 1,854 live Override ownership
hashes passed, including artwork generated from the installed game.

The first capture attempts failed: native desktop capture was unavailable and
GNOME's fallback produced black images. Later the same day, a locally installed
Flameshot captured the installer showing Steam detection, 3440×1440 and
“Patched successfully”. Steam then launched App 32370 with the installed patch;
its introductory movie and main menu rendered. `kmrp-kpm.log` recorded all
81 guarded runs (768 bytes) and 46 relocations applied before the game window,
772 ms after startup. The Steam EXE remained 4,395,008 bytes, SHA-256
`34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`.
The running process mapped `KotorPatcher.dll`, the Bink proxy and the KMRP and
controller patch DLLs; the driver compatibility log reported 8/8 startup hooks.

Local evidence is recorded in ignored `build/proton-game-launch-validation.json`,
`build/proton-runtime-kpm.log`, `build/proton-runtime-driver.log` and
`build/screenshots/06-patched-game-menu.png`. An abandoned GNOME screenshot
permission dialog initially overlaid the captures and blocked ordinary interaction;
a later explicitly authorized keyboard script dismissed it with Escape.
`build/screenshots/08-popup-dismissed.png` records the unobstructed main menu.
A subsequent menu demonstration used a temporary Linux `uinput` virtual Xbox
360 device (`045e:028e`) through Steam's existing joystick access. Its D-pad moved
selection; A opened and B returned from the main Options screen, all five main
settings menus (Gameplay, Feedback, Auto-pause, Graphics, Sound), and Controller
Layout. Xbox A/B/Y prompts rendered at 3440×1440. No keyboard or mouse events
were used for this menu demonstration. The virtual device was removed afterward,
and the game remained at the main menu. Local identities and screenshots are in
ignored `build/proton-virtual-xbox-menus.json`.

At the end of the initial menu test, no game session, NPC/door labels,
in-game inventory/map/abilities navigation,
setting changes, physical controller, rumble, reconnect, launches after restore
or reinstall, stable Proton, or Steam Deck gameplay was tested. Issue 13 was
closed as completed at the maintainer's request on 2026-10-01 after this Ubuntu
check and review of current master (`183c372`). The target/name-strip layout
fix is in `4fdd5f3`, merged by `2f1daa9`; `183c372` adds the Windows stale
action-slot interaction fix. Closing the issue does not extend the measured
coverage listed above.

## Ubuntu gameplay follow-up (2026-10-01)

The same installer, original Steam EXE and Proton Experimental build were used
at 3440×1440 on a 120 Hz monitor. This follow-up also loaded D3M0's **High FPS
Fixes 1.0.0** as a separate KPM patch, after KMRP's four components. It is an
additional live test component, not part of installer 1.5.0. Its 36 K1 hooks were
checked in process memory on the first combined launch; all were installed.
The subsequent gameplay launch again logged all 81 KMRP runs and 46 relocations.
These observations establish the tested combination, not an A/B test of each
FPS fix or completion of issue 22's installer integration.

| Check | Observed result and method |
| --- | --- |
| New game and dialogue | A fresh soldier named `KMRP FPS Test` reached Trask's opening conversation. Reply choices worked; subtitles, reply text and the letterbox rendered. |
| Save/load | A new test slot was saved. A separate copy of an existing Manaan save was loaded successfully; the source save's five file hashes remained unchanged when the copy was made. |
| HUD and NPC labels | Manaan's HUD, minimap, action icons and `SELKATH` target name rendered. This checks an NPC label, not the reported door-name case or every HUD element. |
| Controller movement and camera | A temporary Linux virtual Xbox 360 pad (`045e:028e`) reached XInput slot 0 with Steam Input enabled and its **Gamepad** template selected. Left-stick Y moved the character; right-stick X rotated the view. Screenshots and the native log corroborate both; `camwr` reached 117 after the camera test. |
| Frame rate | Steam's visible performance monitor showed 119–121 FPS in dialogue and 120 FPS in Manaan. An independent 80-sample engine frame-delta reading had median 8.3395 ms, implying about 119.91 FPS. A 120 FPS MangoHud cap was configured. This is sampled coverage, not a sustained benchmark. |

The first Steam Input template used keyboard/mouse mappings and triggered a
GNOME remote-desktop permission dialog; it did not establish native controller
support. Selecting the Gamepad template produced the XInput result above.
**Measurement correction:** an earlier counter-rate estimate was discarded
because that counter did not reliably measure rendered frames. The frame-delta
sample and visible Steam counter are the FPS evidence used here.

Local evidence is retained in ignored `build/proton-gameplay-validation.json`,
`build/research/high-fps-live-hooks.json`,
`build/research/high-fps-menu-deltas.json`,
`build/research/fps-test-save-copy.json` and screenshots
`57-large-fps-counter.png`, `58-dialogue-choice.png`,
`82-template-applied.png`, `90-test-save-menu.png`,
`96-manaan-test.png`, `97-manaan-camera.png` and `98-manaan-movement.png`
under `build/screenshots/`. These screenshots are local evidence and are not
shipped game resources.

To repeat the covered checks, use the identified installer and Proton build,
install at 3440×1440, and launch through Steam. Read `kmrp-kpm.log` for the
81/81 runs and 46 relocations. Create a new test character, select a dialogue
reply, and save to a new slot; load a private copy of a save for free movement.
For controller gameplay, select Steam Input's Gamepad template and check
left-stick movement and right-stick camera against the native joystick log.
Turn on Steam's performance monitor to record the visible FPS alongside each
scene. Testing KMRP alone requires omitting the separate High FPS patch; do not
label the combined follow-up as that comparison.

Still **untested**: door/object labels, in-game inventory/map/abilities
navigation, combat and post-combat movement, physical pads and motor output,
disconnect/reconnect, stable Proton, Steam Deck, 1280×800 gameplay, and game
launches after restore/reinstall. Repeated tutorial conversations interrupted
the fresh-character camera test; the camera check was therefore performed in
the private Manaan save. No cause is attributed without a comparison test.

[Issue 13](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/issues/13)
was confirmed **closed / completed** through GitHub on 2026-10-01 (closure time
14:47:45 UTC). That maintainer decision does not convert the remaining Steam
Deck and hardware tests into completed acceptance criteria.

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
separate width-driven geometry defect in KMRP 1.0; the generator of KMRP 1.5
gives it the shared `max(1, height / 720)` scale and verifies its
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

1. KMRP 1.5 (tag v1.5.0) versus KMRP 1.0 (tag v1.0.0, v2.10.0 until 2026-09-25);
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
been tested on a physical pad under Proton. The virtual Xbox menu and gameplay
coverage above is now established. Under Proton the component also depends on:
- KOTOR Patch Manager's runtime and its `binkw32.dll` proxy, since 2026-09-29
  (until then, the `dinput8.dll` ASI loader, which needed Wine's
  `dinput8=n,b` override; K1DC still does);
- Proton's XInput translation, or the SDL backend for other controllers.

The following remain gameplay tests under Proton, not automated claims:

- combat/action-bar interaction, controller dialogue confirmation, inventory,
  map and pause; movement, camera and the listed settings menus have the limited
  virtual-device coverage above;
- controller connect, disconnect/reconnect, and multiple-device behavior;
- physical-controller Steam Input settings; enabled with the Gamepad template
  worked for the virtual Xbox gameplay test, but disabled was not validated there;
- rumble (KMRP now supplies the engine's rumble table, BioWare's own 22 patterns
  since 2026-09-25, so it works on Windows; see *Rumble works* and *Rumble uses
  BioWare's own patterns* in `CHANGELOG.md`. The Enhanced haptics and the mixer
  of the same day are untested on any platform: `docs/controller-rumble.md`);
- suspend/resume and handheld/docked switching on Steam Deck; and
- game launches following patch, restore, and reinstall under Proton Experimental
  and stable Proton. Installer-only operations under Experimental passed in the
  Ubuntu record above; launches after those operations remain untested.

(Until 2026-09-24 this section said no physical XInput device was available and
that there was no KMRP rumble claim. Both predate the controller work recorded in
`CHANGELOG.md`.)

## Deliberately not changed

- KMRP does not install Wine, Proton, Protontricks, Steam, or Flatpak permissions.
- It does not weaken executable hash validation for a Wine/Proton path.
- The package audit does not label archive inspection as gameplay verification.
- The tested Experimental build is identified; broad Proton/Steam Deck support
  is not inferred from the Ubuntu checks.
