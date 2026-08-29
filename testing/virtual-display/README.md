# KOTOR virtual-display test environment

This profile exposes the 48 resolutions supported by the KOTOR Universal UI
Patcher on one virtual Windows monitor. Every mode runs at 60 Hz to keep the
driver mode table small and stable.

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
6. Run the matching KOTOR patcher build in fullscreen on the virtual display.

Keep the physical monitor enabled until the OBS capture workflow is confirmed.
Do not select "show only" on the virtual monitor during initial setup.
