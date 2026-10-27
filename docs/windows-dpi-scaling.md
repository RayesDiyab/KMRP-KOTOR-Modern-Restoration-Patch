# Windows DPI scaling

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and keep measured behavior separate from untested coverage.

**Kind: reference.**

KMRP sizes KOTOR's interface in framebuffer pixels. Windows can independently
bitmap-scale applications that do not declare DPI awareness, creating a second
scale layer after KMRP has already enlarged the interface. The reported case was
3840×2160 on Windows 11 at 150% desktop scaling: the entire interface appeared
zoomed. Selecting **Properties → Compatibility → Change high DPI settings →
Override high DPI scaling behavior → Application** for `swkotor.exe` removed the
extra zoom.

Microsoft documents the underlying behavior: Windows bitmap-scales applications
that are not DPI-aware, while a DPI-aware declaration tells Windows that the
application handles presentation itself. See [High DPI Desktop Application
Development on Windows](https://learn.microsoft.com/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows)
and [Direct2D and High-DPI](https://learn.microsoft.com/windows/win32/direct2d/direct2d-and-high-dpi).

## Installed setting

An in-place KMRP install manages one named value:

| Field | Value |
| --- | --- |
| Hive | `HKEY_CURRENT_USER` |
| Key | `Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers` |
| Value name | Absolute path of the selected `swkotor.exe` |
| Added token | `HIGHDPIAWARE` |
| Recovery record | `KMRP\dpi.manifest` in the game folder (`KMRP_DPI.manifest` beside `swkotor.exe` until 2026-10-20; an install or restore moves it, and finds it at the old name until then) |

The setting is per user and per executable path. KMRP does not change the global
display scale and does not need administrator access. It installs the token even
at 100% scaling so that moving the game to a differently scaled display or
changing desktop scale later does not silently reactivate virtualization.

If other compatibility flags already exist, KMRP appends `HIGHDPIAWARE` and
preserves the previous string exactly in the recovery record. If the token is
already present and nothing else needs changing, KMRP leaves the value untouched
and does not claim ownership of it.

### Windows compatibility mode (2026-10-27, issue 39)

The same value holds the Compatibility tab's other settings. With a compatibility
mode on for `swkotor.exe`, the game drew a black square over most of the screen
after patching (issue 39; the reporter turned it off by hand and it was gone). The
installer now takes these tokens out of the value while it adds `HIGHDPIAWARE`:
the Windows version modes (`WIN95`, `WIN98`, `NT4SP5`, `WIN2000`, `WINXP`,
`WINXPSP2`, `WINXPSP3`, `WINSRV03SP1`, `WINSRV08SP1`, `VISTARTM`, `VISTASP1`,
`VISTASP2`, `WIN7RTM`, `WIN8RTM`, `WIN81RTM`), reduced colour (`256COLOR`,
`16BITCOLOR`) and `640X480`. Every other token stays, in its order; a value left
with only Windows' `~` marker becomes the token alone. The recovery record keeps
the value from before KMRP, so Restore Original puts the mode back exactly, and a
second install over KMRP keeps the first install's record. The log names what was
turned off.

A mode set with "Change settings for all users" lives in the same key under
`HKEY_LOCAL_MACHINE`. The installer does not run as administrator and cannot
change it: it only reads it and, when it holds a mode, says where to turn it off.

## Restore and failure ownership

The recovery record contains the normalized executable path, whether a prior
value existed, the exact prior string, and the exact string KMRP installed. Text
fields are UTF-8 encoded and Base64-wrapped so empty strings and arbitrary flag
spacing round-trip without ambiguity.

Restore compares the current registry value with the recorded installed value:

| Current state | Restore behavior |
| --- | --- |
| Exact value KMRP installed | Restore the exact prior value, or remove the value if none existed |
| Missing, changed, or non-string value | Leave it untouched; another actor changed it after install |
| Missing or invalid KMRP manifest | Do not guess ownership; an invalid present manifest blocks that restore step |

The manifest is removed after a valid restore record is consumed. During install,
the registry write is verified before the manifest is accepted. If verification
or manifest writing fails, the registry is immediately returned to its prior
state. Access-denied failures do not block the rest of KMRP; the log reports the
manual Compatibility-tab procedure instead.

## Verification record

`testing/regression/Test-DpiCompatibility.ps1` drives the compiled patcher
against six throwaway game directories (cases 5 and 6, a compatibility mode taken
out and put back and an install run twice, added 2026-10-27: all 26 checks pass) and restores the exact pre-test values
in `finally`:

1. no previous value: install creates `HIGHDPIAWARE`, restore removes it;
2. an existing `~ DISABLETHEMES` value: install appends the token, restore returns
   the byte-for-byte previous string;
3. a simulated user edit after install: restore leaves the newer string alone;
4. an unwritable manifest path: install rolls the unrecorded registry write back
   and continues with the manual fallback.

All four cases passed on 2026-09-05 on Windows 11 Pro build 26200. The test host
was at 96 DPI (100%) and the clean executable returned to SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`
after the initial manual apply/restore test.

The script was not re-run against the installer of 2026-09-24. On the play-test
game (`C:\Star Wars - KotOR`), all 16 installs logged between 2026-09-20 and
2026-09-24 took the "token already present" path. That game's value already
held `HIGHDPIAWARE` beside other compatibility flags. Each install logged
*Verified the Windows high-DPI application override for swkotor.exe*, left the
value as it was, and wrote no `KMRP_DPI.manifest`, as described above. None
logged *Enabled…* (the game's `KMRP.log`, read 2026-09-24).

The reported 150% case is user-confirmed with the equivalent Compatibility UI
setting. **On 2026-09-25 the maintainer reported the game working correctly under
Windows display scaling** on this workstation (Windows 11 build 26200), with
the KMRP 1.5 install, **at 150%**, the reported case. 125%, 175% and 200% were
not tested, and Windows 10 remains untested. On the maintainer's judgement,
issue #3 was closed that day, and its closing comment lists these gaps. Those are
validation gaps, not claims that the registry transaction itself differs at
those scales. (Until that day this said the visual runs had not been repeated
on this workstation.)

## Values left behind by regression fixtures — 2026-09-25

Read from `HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers`
on the maintainer's machine: twelve `HIGHDPIAWARE` values for test executables
that were never restored.

| Values | Where from | Files on disk |
| --- | --- | --- |
| 7 × `%TEMP%\kmrp-controller-<guid>\config-conflict\swkotor.exe` | `Test-ControllerSupport.ps1` Case 2 before commit `137fd5d` (2026-09-24), which renamed the fixture to `kmrp-controller-selftest.exe` and added its `--restore` | gone |
| 2 × `%TEMP%\kmrp-controller-<guid>\standard\kmrp-controller-selftest.exe` | the current script's Case 1, from runs that stopped between install and restore | one folder, of 2026-09-21 01:02, still there with its `KMRP_DPI.manifest` |
| `%TEMP%\kmrp-fontcheck4\swkotor.exe`, `%TEMP%\kmrp-case2-probe\swkotor.exe`, `build\movie-aspect-verify\swkotor.exe` | one-off probes: no tracked script and no commit names them | all three folders still there |

**Not a product fault.** (As the installer was on 2026-09-25; since 2026-09-29 a
folder holding KOTOR Patch Manager's own `patch_config.toml` is installed for KPM
instead, by `KpmEditionOperations.Install`.) A foreign `patch_config.toml` does not refuse the
install. `ControllerOperations.Install` reports and skips KMRP's runtime (then
the optional controller component), on purpose, so the rest of the patch still
applies.
Throwing had aborted the whole patch for players with another KPM mod. So the
DPI value belongs to a completed install, and Restore Original removes it
through `KMRP_DPI.manifest` (`KMRP\dpi.manifest` since 2026-10-20), as described above. An install that does throw
rolls the value back in its `catch` (`DpiCompatibilityOperations.Rollback`).

**The game at another path, since 2026-10-11.** The value is filed under the path
the game had at install. Until then Restore Original stopped with "belongs to a
different executable path" when the path differed (issue 36: one folder through two
Wine drives; a folder moved on Windows). It now restores the value under the recorded
path when no game is there any more or it is this same folder, and leaves the value
alone when another copy of the game is still at that path.

**A test fault.** A fixture's value is removed only by that fixture's own
`--restore`, which the scripts reach only on the success path. A failed
assertion, an exception or an interrupt deleted the work folder and left the
value. The four scripts that patch fixtures in place now call
`Remove-TestDpiValues` (in `testing/regression/Restore-TestNvidiaProfiles.ps1`)
in their `finally` whenever they delete the work folder:
- `Test-ControllerSupport.ps1` (removed on 2026-10-04 with the four-patch
  edition; its successor, `Test-InstallerPatch.ps1`, does not call the helper and
  relies on each fixture's own `--restore`, read 2026-10-08)
- `Test-LargeAddressAware.ps1`
- `Test-ReinstallOverOlderBuild.ps1`
- `Test-DpiCompatibility.ps1`

The helper removes only values that are under that run's root and named like a
fixture executable. It was checked against values made for the purpose: it
removed the two fixture-named values under its root and kept a `swkotor.exe`
beside them and a fixture-named value under another root. The twelve existing
values were then deleted, one `reg delete` each, on the maintainer's instruction.
The key went from 50 values to 38, and every real game's entry was unchanged.
The four fixture folders still on disk were left alone.

## Manual fallback

If the patcher reports that Windows high-DPI handling could not be configured:

1. right-click `swkotor.exe` and open **Properties**;
2. select **Compatibility**, then **Change high DPI settings**;
3. enable **Override high DPI scaling behavior** and choose **Application**;
4. apply the change and restart KOTOR.

This is the same setting as the original confirmed workaround.
