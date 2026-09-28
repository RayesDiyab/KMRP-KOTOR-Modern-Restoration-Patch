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
| Recovery record | `KMRP_DPI.manifest` beside `swkotor.exe` |

The setting is per user and per executable path. KMRP does not change the global
display scale and does not need administrator access. It installs the token even
at 100% scaling so that moving the game to a differently scaled display or
changing desktop scale later does not silently reactivate virtualization.

If other compatibility flags already exist, KMRP appends `HIGHDPIAWARE` and
preserves the previous string exactly in the recovery record. If the token is
already present, KMRP leaves the value untouched and does not claim ownership of
it.

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
against four throwaway game directories and restores the exact pre-test values
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

**Not a product fault.** A foreign `patch_config.toml` does not refuse the
install. `ControllerOperations.Install` reports and skips KMRP's runtime (then
the optional controller component), on purpose, so the rest of the patch still
applies.
Throwing had aborted the whole patch for players with another KPM mod. So the
DPI value belongs to a completed install, and Restore Original removes it
through `KMRP_DPI.manifest`, as described above. An install that does throw
rolls the value back in its `catch` (`DpiCompatibilityOperations.Rollback`).

**A test fault.** A fixture's value is removed only by that fixture's own
`--restore`, which the scripts reach only on the success path. A failed
assertion, an exception or an interrupt deleted the work folder and left the
value. The four scripts that patch fixtures in place now call
`Remove-TestDpiValues` (in `testing/regression/Restore-TestNvidiaProfiles.ps1`)
in their `finally` whenever they delete the work folder:
- `Test-ControllerSupport.ps1`
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
