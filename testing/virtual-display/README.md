# KOTOR virtual-display test environment

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


This profile exposes 49 resolutions on one virtual Windows monitor: the 49 KMRP
listed until 2026-09-29. KMRP lists 66 since then, and the other 17 are not in the
profile. Every mode runs at 60 Hz to keep the driver mode table small and stable.
Since 2026-10-07 the game offers the sizes the connected display reports, so with
the virtual display selected its list is this profile's modes.

## Prepared package

- Driver/control package: `VDD.Control.25.7.23/VDD Control.exe`
- Test profile: `kotor-vdd-settings.xml`
- Upstream project: <https://github.com/VirtualDrivers/Virtual-Display-Driver>
- Download SHA-256:
  `a701f2272e9fcf382849b24f913c6dd07597b3b1116525f2e90182f019609154`

The downloaded control application and driver catalog both have valid
SignPath Foundation Authenticode signatures.

## Intended workflow

1. Install the signed virtual display driver using VDD Control.
2. Copy `kotor-vdd-settings.xml` to
   `C:\VirtualDisplayDriver\vdd_settings.xml` and reload the driver.
3. Verify the modes Windows actually accepted. The upstream driver documents
   support through 8K; modes above 8K are experimental and must be verified.
4. Select the virtual display and the matching test resolution.
5. Capture the virtual display with OBS Studio and fit the source to the OBS
   preview so the complete game frame remains visible on the physical monitor.
6. Run the game, installed by the build under test, in fullscreen on the virtual
   display. (Until 2026-10-04 each resolution took an install of its own.)

Keep the physical monitor enabled until the OBS capture workflow is confirmed.
Do not select "show only" on the virtual monitor during initial setup.

## Files kept here

| File | What it is |
| --- | --- |
| `kotor-vdd-settings.xml` | The profile: 49 modes, all at 60 Hz. Checked on 2026-09-24: its 48 modes were exactly the 48 resolutions of the installer's `--apply` outputs; 2880x1620 was added on 2026-09-25 with the 49th resolution. |
| `swkotor-7680-windowed.ini` | A `swkotor.ini` at 7680×2160, windowed (`FullScreen=0`, `AllowWindowedMode=1`). It is also the seed INI that the regression scripts copy into their throwaway game (four until 2026-10-04, when the first of these was removed): `Test-ControllerSupport.ps1` (the one removed), `Test-DpiCompatibility.ps1`, `Test-LargeAddressAware.ps1` and `Test-ReinstallOverOlderBuild.ps1`. |
| `minimap-7680x2160/`, `mipc28x6.gold-geometry*.gui`, `mipc8x6.minimap-180.gui` | Lab records from the minimap-scale experiments of 2026-08-28 at 7680×2160, committed with the first commit. There are twelve HUD layouts (`mipc*.gui`, GFF `GUI V3.2`), plus `backup-location.txt`, which gives that day's backup path on the build machine. They predate the current map model ([universal-resolution-math.md](../../docs/universal-resolution-math.md)), so they are **not** what the build generates today. Nothing in the repository reads them. |

The ignored `verify-*/` folders and the driver package are described in
[testing/README.md](../README.md#what-is-deliberately-not-committed). (This
section was added on 2026-09-24. Before then the README described only the
profile and the package.)
