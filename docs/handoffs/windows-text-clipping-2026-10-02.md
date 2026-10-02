# Windows handoff: verify the XP popup and action-name clipping fixed on Mac

This is an investigation handoff, dated 2026-10-02. **Both failures were measured
on Mac at 1920×1200. Neither exact failure has been reproduced on Windows.**
Check Windows before deciding whether to port the runtime repairs. Do not assume
identical floating-point behavior, offsets, vtable slots or hook timing.

## 1. XP popup loses its description and shows only “50”

The Mac popup contained the complete string
`Experience Points (XP) Received: 50`; this was clipping, not missing text.

| Measured Mac value | Result |
| --- | --- |
| Viewport | 1920×1200 |
| Estimated text width plus margin | 477px |
| First width where native wrapping gives one line | 482px |
| Object scale | 1 |
| Native wrapped line lengths at477px | 32, 2 |
| Actual rendered line height | 27.0000019px |
| Two-line rendered height | 54.0000038px |
| Text-box height | 54px |
| Alignment | 0x11, vertical centre |

The width estimate allowed wrapping. The fractional height then exceeded the
integer box, and the native centred draw path skipped the first line, leaving
`50`. The earlier successful journal-popup test did not verify XP. Repeating
SetExtent on wrapped text did not solve it.

Mac repair in [status_summary.cpp](../../macos/patches/kmrp-layout/status_summary.cpp):

- Ask the native wrapper for the line count achievable at the available screen width.
- Binary-search the narrowest width retaining that count; zero lines is not a fit.
- Use the maximum fitting width for the visible rows.
- Give each row at least `ceil(native rendered line height × native line count)`.
- Grow screen-capped multiline rows and put OK below the final row with a gap.
- Cache measurements, invalidating for text/font/scale/viewport and line-count changes.

The maintainer **confirmed the repaired Mac XP popup in game**. Windows still
uses `labelTextWidth` and `layoutStatusSummary` in
[K1ControllerLayout.cpp](../../src/controller-native/K1ControllerLayout.cpp):
estimated glyph width plus quarter-line padding, fixed row height and the old
OK positioning. `StatusSummaryFrameK1` supplies the no-controller path; both
controller-enabled and disabled builds must be checked.

## 2. Wrapped action names disappear while “(self)” remains

The failing Mac label contained `Adrenal Stamina (self)`.

| Measured Mac value | Result |
| --- | --- |
| Viewport | 1920×1200 |
| Label, text-object and background rect | (1617,1034,295,54) |
| Native line lengths | 15, 6 |
| Actual rendered line height | 27.0000019px |
| Required height for two lines | 55px after ceiling |
| Required height for three lines | 82px after ceiling |
| Alignment | 0x22, bottom |

The bottom-aligned draw path skipped the first line because the two-line height
exceeded54px. A shorter medkit name worked. Do not infer line count from the
screenshot: capture the complete string and the native line lengths.

Two changes were made:

1. **Shared resource generator:**
   [apply_gold_hud_proportions.py](../../tools/apply_gold_hud_proportions.py)
   previously used `ACTION_DESCRIPTION_LINE_AT_720 = 10.0`, producing a17px
   assumption at1200p. It now reserves the measured16px runtime baseline and
   ceilings the three-line total using float32 TXI/draw arithmetic, giving82px.
   This source change applies to generated Windows resources too; regenerate
   them rather than reusing old archives.
2. **Mac runtime:** the shared layout reads the live action label's font, scale
   and native line count. It grows the text and background upward, preserves
   the original bottom anchor and background margins, and restores the baseline
   for shorter text. This runtime behavior is currently Mac-only.

Important distinction: regenerated1920×1200 `mipc28x6.gui` assigns
`dialogfont10x10`, while `maininterface.gui` assigns `dialogfont16x16`. The
measured live Mac object uses the27px font. A GUI's assigned font alone does not
establish the live font. Determine what Windows actually loads.

The Mac action runtime repair passes synthetic tests but **has not yet been
confirmed by a real game play-test**. It is included in the newly built Mac DMG.
Do not record it as user-confirmed.

## Windows verification steps

1. Read AGENTS.md and the routed project instructions. Preserve unrelated work;
   do not commit or push without exact authorization.
2. Record the Windows game build, clean and installed executable hashes, KMRP
   build, resolution, fullscreen/windowed mode and controller option.
3. Reproduce both cases at1920×1200 with the previous Windows build if available.
   Compare with a working higher-resolution case, using the same save and text.
4. For XP, break on the live row and capture the full string, actual font metrics,
   object scale, alignment, native line count/lengths, control and text-object
   extents. Measure the native single-line width threshold. Compare before/after
   our layout and immediately before drawing; establish hook order.
5. For actions, compare a working medkit name with Adrenal Stamina or another
   failing wrapped name. Capture the same text/font/wrap/extent values and the
   background rectangle. Check whether names needing more than three total
   lines can be reached and clipped.
6. Inspect the Windows centred/bottom drawing and height calculations directly.
   The Mac rounding cliff must not be assumed to occur identically on x86 Windows.
7. Rebuild Windows resources with the shared correction, then rerun packaged GUI
   geometry checks. Verify the installed files came from those rebuilt resources.
8. If a Windows runtime failure is measured, adapt native-wrap width fitting and
   upward-rounded actual text height to Windows' own ABI and object layout.
   Avoid a hardcoded482px width, a hardcoded55/82px height or a resolution-specific
   special case. Preserve multiline text when the screen caps width, button
   spacing, background margins and shorter-name restoration.
9. Verify1920×1200 and representative lower/higher resolutions, one/multiple popup
   rows, unavoidable wrapping, and controller-enabled/disabled builds. Record
   automated, inspected, play-tested and untested coverage separately.

## Evidence and tests

- [Status-summary measurements and repair](../../reverse-engineering/custom-gui-controls.md)
- [Action-description measurements and font-assumption correction](../universal-resolution-math.md)
- [Production Mac layout regression](../../testing/regression/Test-MacStatusSummary.cpp)
- [Packaged GUI geometry regression](../../testing/regression/Test-GeneratedGuiGeometry.py)
- [Testing guide](../../testing/README.md)

Mac clean reference: Aspyr1.4.0 x86_64, 6,333,424bytes, SHA-256
`c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71`.
Mac addresses in the linked references are preferred VA, with original-text
FILE=VA−0x100000000; they are not Windows patch addresses.

Local Mac logs are ignored workstation artifacts under
`../work/xp-20261002/`: `popup-v2.log`, `popup-fixed.log`, `hud.log`.
They are not required Windows inputs. The new Mac DMG SHA-256 is
`b92f324177832dd8ee7ea72a19e1ad8ee018991b263c6976990ad08e44a2878e`.
No Windows runtime changes, Windows installation, commit or push were performed
as part of preparing this handoff.
