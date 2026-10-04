# NVIDIA present method

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and keep measured behavior separate from untested coverage.

**Kind: reference.**

NVIDIA's driver can present an OpenGL game through a Direct3D (DXGI) swap chain
instead of natively: **NVIDIA Control Panel → Manage 3D settings → Vulkan/OpenGL
present method → Prefer layered on DXGI Swapchain**. On that path KOTOR shows
frames it has not finished drawing whenever a frame stalls: a one-frame white
flash in the in-game menus, the menu backdrop drawn alone, or a half-drawn world
with characters missing when a menu closes. On the driver's native path none of
this appears. The measurements are in
[Part 4 of the white-flash investigation](../reverse-engineering/experiments/white-flash-video-capture.md#part-4-the-driver-shows-unfinished-frames-and-the-engines-long-frames-expose-it).

NVIDIA's default is **Auto**, and on Auto the driver presented KOTOR natively in
every test. The layered path is reached when the **global** setting has been
changed to prefer it — by hand, or to use a feature that needs it, such as
RTX HDR. So an in-place KMRP install checks what the driver will do for
`swkotor.exe`, and changes it only in that one case.

## Installed setting

| Field | Value |
| --- | --- |
| Interface | NvAPI driver settings (DRS), from `nvapi64.dll` / `nvapi.dll` in System32 |
| Profile | whichever profile the driver applies to the installed `swkotor.exe` (by full path) — normally NVIDIA's predefined **"Star Wars: Knights Of The Old Republic"**; if none names it, a new profile **"KMRP - Star Wars: Knights of the Old Republic"** holding `swkotor.exe` |
| Setting | `OGL_CPL_PREFER_DXPRESENT`, id `0x20D690F8`, "Vulkan/OpenGL present method" |
| Written value | `0` = `OGL_CPL_PREFER_DXPRESENT_PREFER_DISABLED`, shown as **Prefer native** |
| Recovery record | `KMRP_NVIDIA.manifest` beside `swkotor.exe` |

The setting's values, from NVIDIA's `NvApiDriverSettings.h`:

| value | constant | Control Panel |
| --- | --- | --- |
| `0` | `OGL_CPL_PREFER_DXPRESENT_PREFER_DISABLED` | Prefer native |
| `1` | `OGL_CPL_PREFER_DXPRESENT_PREFER_ENABLED` | Prefer layered on DXGI Swapchain |
| `2` | `OGL_CPL_PREFER_DXPRESENT_AUTO` (= `_DEFAULT`) | Auto |

NVIDIA matches profiles by executable name, so the value reaches every
`swkotor.exe` on the machine — the same as making the change in the Control
Panel. KMRP does not touch the global profile. It does not need administrator
access: the save succeeded from a standard, non-elevated process on driver
32.0.16.1656.

## When it writes

The driver resolves the setting for the game's profile and reports where the
value comes from. KMRP acts on that:

| the game's profile | resolved value | KMRP |
| --- | --- | --- |
| holds the setting itself (predefined or set by the player) | anything | leaves it; if it is Prefer layered, logs how to change it by hand |
| inherits it (from the global, base or default profile) | Auto or Prefer native | nothing to do |
| inherits it | **Prefer layered** | sets Prefer native in the game's profile, verifies it in a fresh session, writes the manifest |
| no profile names `swkotor.exe` | the global's value | as the two rows above, creating KMRP's profile first when it must write |

No NVIDIA driver, or no NVIDIA GPU (`NvAPI_Initialize` fails): nothing happens
and nothing is logged. Any error while checking or writing is reported with the
manual steps and the install continues — this step never fails a patch.

## Restore

Restore reads the manifest and removes KMRP's value only while the game's
profile still holds Prefer native itself. It deletes the whole profile only when
KMRP created it and it still holds exactly one application and one setting;
otherwise it deletes just the one setting, so the profile inherits again.
Installation skips an existing profile shared by multiple applications. A profile
with KMRP's name but no association with the game is not adopted. If
the value changed after install, it is left as it is and the manifest is
removed. If NVIDIA refuses the save, the manifest is kept so a later restore can
retry. Driver unavailability also keeps the record for retry: it does not prove
that the saved profile has disappeared. A successful save sets rollback ownership
before the fresh-session verification, so a failed readback does not lose recovery.

## The standalone module

The single-file `.kpatch` has no installer, so its module makes the same check from
inside the game (`src/controller-native/K1RuntimeNvidia.cpp`, a port of
`NvidiaPresentOperations.Install` with the rules of [When it writes](#when-it-writes)
unchanged). Decided by the maintainer on 2026-10-04: "log a warning and then set it
(mention that in the warning)".

| | Installer | Standalone module |
| --- | --- | --- |
| When | once, at install | at the first GUI frame of every run, on a thread of its own |
| Where it reports | the installer's log | `kmrp-kpm.log` beside the game |
| Library | `nvapi64.dll` or `nvapi.dll` | `nvapi.dll` (the game is 32-bit), from System32 only |
| Takes effect | the next start of the game | the next start: the driver has read the profile by the time the module runs |
| Record | `KMRP_NVIDIA.manifest` | the same file, in the same format |
| Undo | Restore | by hand, as the log line says; the installer's Restore also accepts the record (tested below) |

When it is about to write, the log holds two lines: a warning that NVIDIA would
present the game through a DXGI swap chain, why that matters, and that KMRP now sets
Prefer native in the named profile without touching the global setting; then a line
that it is done, that it applies from the next start, and how to undo it. With the
record present, later runs do nothing. A run that finds the game already on Auto or
Prefer native logs nothing.

A patch has no uninstall step, so removing the patch leaves the setting. That is the
cost of doing this from a patch, and the reason the log line names the undo.

| case (2026-10-04, RTX 3080, global Prefer layered; `testing/regression/Test-RuntimeNvidia.cpp` on the throwaway name `kmrp-nvapi-selftest.exe`) | result |
| --- | --- |
| stand-in profile holding only the executable, present method inherited | both lines logged, `Set`; the installer's `Describe` then reads Prefer native from the game's own profile; the record is `KMRPNV1`, the path in base64, `0` |
| the same, a second run | nothing logged, nothing written |
| the installer's `Restore` on that record | "Removed KMRP's NVIDIA present-method setting", the profile inherits Prefer layered again, the record is gone |
| stand-in profile holding Prefer layered itself | left as chosen, one line saying so, no record |
| stand-in profile shared with a second application | the warning, "left the shared NVIDIA profile alone", no record |
| no profile names the executable, and a profile with KMRP's name already exists (a leftover on this machine) | the warning, "left the existing NVIDIA profile ... alone", no record |
| the real game's path (its own profile holds Prefer native) | nothing logged, nothing written |
| in the game: the options package in the fixture, stock KPM 0.7.1 | `nvapi.dll` loaded, the game reached the main menu and answered, no NVIDIA line in `kmrp-kpm.log`, no record |

Every stand-in profile was removed afterwards and the real game's profile read the
same before and after. **Not tested:** the module creating KMRP's own profile where no
profile names the executable (the leftover profile above stops it on this machine;
the installer's regression covers that path for the C# code); the write made from
inside a running game, since the real game's profile here already holds Prefer native;
whether the next start is then free of the flash, which needs a game profile that
inherits the global value; drivers other than 32.0.16.1656.

## Tested

| case | result |
| --- | --- |
| reading NVIDIA's settings for a real install (RTX 3080, driver 32.0.16.1656): predefined KOTOR profile, Auto set in it, global Prefer layered | reported exactly that |
| no profile names the executable, global Prefer layered | KMRP profile created, Prefer native read back from a fresh session, profile removed on restore, global untouched |
| existing profile inheriting Prefer layered — the case real installs take | value set in that profile; restore removed only the value and the profile stayed |
| existing profile holding Prefer layered itself | left alone, no manifest written |
| a second install over the first | no change |
| KMRP-created profile gains another application | restore retains both applications and removes only KMRP's setting |
| existing shared profile | install makes no changes |
| unrelated profile already has KMRP's name | application and explicit setting remain intact; no manifest |
| a real install, 2026-09-20: the play-test game on the RTX 3080 (driver 32.0.16.1656), inheriting Prefer layered | the installer logged *Set NVIDIA's present method for swkotor.exe to Prefer native. It was inheriting Prefer layered on DXGI Swapchain*, and Restore logged *Removed KMRP's NVIDIA present-method setting*; twice, at 12:42Z and 13:08Z (the game's `KMRP.log`). The log does not name the profile. |
| the same game, every install from 2026-09-21 to 2026-09-24 | no NVIDIA line and no manifest: the driver no longer resolved Prefer layered for it, so the step did nothing, as designed. What changed the driver setting is not recorded. |
| the same game, 2026-09-25, read with `NvidiaPresentSelfTest describe` | the driver resolves Prefer native **from the game's own profile** ("Star Wars: Knights Of The Old Republic"), global still Prefer layered; no manifest. The maintainer reported no white flash in play that day (issue #14). The setting fixes the flash; KMRP writing it in a real install is still unplayed. |

`testing/regression/Test-NvidiaPresentMethod.ps1` runs these. The write cases
use a throwaway executable name, `kmrp-nvapi-selftest.exe`, so no real game's
profile is written, and stand-in profiles are removed in a `finally` block.

**Untested:** 32-bit Windows (`nvapi.dll`); older drivers; NVIDIA Optimus laptops; the
restore-retry path after a refused save. AMD and Intel are outside this step
entirely: no equivalent path was seen or tested on them. (Until 2026-09-24 this
list began with "a full KMRP install writing a real KOTOR profile". The game's
`KMRP.log`, shown in the two last rows above, records that it happened on
2026-09-20.)

## Not changed

- NVIDIA's global profile, and every setting other than the present method.
- A present method someone set for the game on purpose, including Prefer
  layered for RTX HDR. Such a player may still see the presentation defects.
- Engine frame clears: the old clear-suppression hooks were removed on
  2026-09-19. The earlier text here promised a menu-only mitigation on the
  layered path; that is no longer shipped.

## Verifying by hand

1. NVIDIA Control Panel → Manage 3D settings → Program Settings → select
   `swkotor.exe` → **Vulkan/OpenGL present method**. After an install on a
   machine whose global prefers layered, it reads **Prefer native**.
2. In-game, list `swkotor.exe`'s modules (`(Get-Process swkotor).Modules`, or
   Process Explorer). `nvwgf2um.dll` or `d3d11.dll` present means the driver is
   on the layered path; absent means native.
3. `KMRP_NVIDIA.manifest` beside `swkotor.exe` exists only while KMRP owns the
   value.
