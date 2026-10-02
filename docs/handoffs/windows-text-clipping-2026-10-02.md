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

At the initial handoff stage, the Mac frame-fitting candidate passed synthetic
tests but had not been confirmed by a real game play-test. **Status correction,
2026-10-03:** that candidate subsequently failed and was removed. The final
native getter repair and its companion font-height hook were then confirmed
in game on 2026-10-02, as recorded in the follow-up below.

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


## Follow-up after the rebuilt Mac installer was tested

The maintainer reported that the action-name repair still failed. Probes confirmed
55px after the GUI callback and at HUD draw entry, then54px at the label's own
draw entry. Native action layout overwrote the frame-based repair. That pass is
removed; the correction now rounds upward in the upstream Mac ideal-height getter
at its existing quantization stages. See the dated site table in the
[resolution reference](../universal-resolution-math.md). The corrected diagnostic retains55px through label draw for the two-line
action name. Visual confirmation was pending at this diagnostic stage; the
subsequent maintainer confirmation is recorded below. The first upstream build exposed
an exit-confirmation sizing loop: ideal height and font height must round
consistently, so the font-height getter is also corrected. On Windows, measure the getter's rounding and the final
label draw state rather than porting the superseded frame pass.

The latest Mac package SHA256 is
`5a1ec26ab9bb76b4b9fec07b7a6d09bd05bc7790822d833e2010ccd6be447d6e`.
See the [Mac verification handoff](mac-text-and-upstream-2026-10-02.md) for
the remaining checks. Do not port upward rounding to one getter without checking
callers that compare it to the font-height getter.

The maintainer subsequently confirmed the final Mac two-line action name,
Exit Game and Scripts-menu Enter all work in the actual game (2026-10-02).
Windows reproduction and applicability remain unverified.

## Windows native getter inspection, 2026-10-02

PR #27 was merged locally at `1c18bef`. The following observations are from
disassembling the clean Windows CD 1.03 input, 4,042,752 bytes, SHA256
`761f9466f456a83909036baebb5c43167d722387be66e54617ba20a8c49e9886`.
Addresses are VA; for these original-image sites, FILE = VA - 0x400000.
This is static evidence, not a reproduction of either clipping case.

| Native calculation | VA | FILE | Observed arithmetic |
| --- | --- | --- | --- |
| Font pixel height | 0x00459610 | 0x059610 | `fontheight * 100 + 0.5`, then the native truncating conversion |
| Ideal height, existing wrapping | 0x0045B7DA | 0x05B7DA | `(spacingB + fontheight) * objectScale * 100 * lineCount + 0.5`, then conversion |
| Ideal height, newly computed wrapping | 0x0045B850 | 0x05B850 | Same total-height rounding after native wrapping |
| Ideal height, explicit width | 0x0045B8ED | 0x05B8ED | Round base line pixels, round scaled line pixels, multiply by the native line count |
| Centred text draw | 0x0045A922 | 0x05A922 | Store `fontheight * objectScale * 100` as float32; compare floating-point total with the integer box |
| Bottom-aligned text draw | 0x0045A9A2 | 0x05A9A2 | Same float32 line height; skip leading lines while the total exceeds the box |

The GUI-string vtable at VA 0x00741878 points to the font-height getter at
slot +0x48 and the ideal-height getter at slot +0x50. The outer GUI-text
wrappers at 0x00414EE0 and 0x00414EB0 respectively add one pixel when the
reported font height is below 16; preserve that existing small-font rule.

The companion-getter warning applies to Windows too. The native message-box
layout at 0x006253A0 contains two button-width loops which require equality
between ideal text height (GUI-text vtable +0x08) and the outer font-height
getter. Their retry branches are at 0x006254FF and 0x006255C9. For example:

```asm
006254EF mov ecx, ebp
006254F1 call dword ptr [edx+08] ; button text's ideal height
006254F4 mov ecx, ebp
006254F6 mov ebx, eax
006254F8 call 00414EE0           ; corresponding font height
006254FD cmp ebx, eax           ; equality is required
006254FF jne 006254D5           ; widen by 10 and retry
```

Changing only ideal-height rounding would therefore risk an analogous
non-terminating Windows confirmation dialog. A candidate repair must operate
in the native shared getters, cover all four ideal-height rounding stages and
the companion getter, and use the actual font/scale/wrapping. No Windows
runtime repair has been applied from this inspection.

Live baseline investigation was blocked by tool access: Computer Use rejected
the isolated `swkotor-pr27.exe` window, and the x64dbg memory tool reported
that approval was required while its approval policy was `never`. The debug
session was stopped. Neither target string, live font, native line lengths,
final draw bounds nor controller/resolution gameplay coverage was measured.
Enable those tools and reproduce the cases before selecting a runtime repair.
The preserved baseline installer and isolated game fixture are ignored local
artifacts, not distributable game data.

To verify these static observations, disassemble the table's sites from the
identified clean input; inspect vtable slots +0x48/+0x50; then disassemble
0x006254EF..0x006254FF and 0x006255B7..0x006255C9. For live verification,
follow the Windows verification steps above and record the final native draw
state rather than a frame callback's temporary rectangle.

## Live access and font measurement correction, 2026-10-03

The earlier tool-access block is resolved. The candidate keyboard-port installer
(164,836,864 bytes, SHA256
`70fe90ed938ffbe90255d057efffbd952d1ac60f5e8d1ce39d217e5de9416cb7`)
was installed through the patcher and started under x32dbg. The live CD 1.03
executable is 4,042,752 bytes, SHA256
`ca9d22eacb5bdfa8e2ad3f8935b0e8e2fed72da8132d0622d576a650aa7e1889`;
its bytes did not change during this test. Controller support was enabled and
the live render viewport table held 1920×1200. The installed native module is
251,392 bytes, SHA256
`452b76d8dc86c832e3df9eed0f53b0768f3305935a5e1665d568435f65d1ba98`.

A breakpoint at VA `0x0045A932` captured the main-menu **Load Game** string,
not either target case. VA/FILE conversion remains FILE = VA − `0x400000`
for original code. The GUI-string object had scale 1, alignment `0x12`, one
native line and a 517×47 text box. Its font information's `+0x04` field was
float32 `0.27000001072883606` (`71 3D 8A 3E`), and the draw stack's `+0x2C`
field was float32 **27.000001907348633** (`01 00 D8 41`). Computing two lines
from that live value gives **54.000003814697266**. This confirms a Windows
fractional-height risk; it does not establish the XP or action label's font,
wrapping, final bounds, or actual skipped lines.

Automated clicks moved the Windows pointer without activating the menu. The
DirectInput probe at VA `0x005E271E`, conditioned on a pressed scan code `0xD0`,
had no hits. A controlled native activation call also did not open Load Game;
neither observation proves the cause of the physical-input report. Physical
reproduction is still needed. No native height repair was added on this evidence.
The candidate remains installed at 3440×1440, with the exact original player INI
restored and all investigation breakpoints and scratch memory removed. Both
target clipping cases and controller on/off gameplay remain unverified.

## Session outcomes recorded before committing, 2026-10-03

- PR #27 was merged locally at `1c18bef`; that merge has not been pushed.
  Windows resources were regenerated for all 66 packaged resolutions after the
  merge. The previous packaged 1920×1200 action-label height was 38px; the
  regenerated resource is 82px. These are archive measurements, not live HUD
  measurements. Representative generated heights are 48px at 800×600 and
  1280×720, 96px at 3440×1440, and 144px at 3840×2160.
- The Mac shared row/list keyboard repair was adapted to Windows object layouts
  and calling conventions, with three core hooks. It computes neighbours locally
  and handles a stationary GUI pointer without modifying controller traversal
  or shared MOVETO links. Windows already loads the measured main-menu MOVETO
  links correctly, so the Mac loader repair was not copied. The source and ABI
  inventory are in the [Windows keyboard reference](../../reverse-engineering/windows-keyboard-navigation.md).
- The candidate installer was rebuilt using `build_kmrp.ps1 -ReuseResources`.
  Synthetic navigation checks passed at heights 600, 720, 1200, 1440, and 2160.
  Installer controller on/off, switching, restore, rollback and CD/Steam checks
  passed all 173 assertions at each of 1280×720, 1920×1200, and 3840×2160.
  Generated-hook equality, original/stolen-byte guards, KPM corruption guards
  and ownership/exports/constants checks passed. The unchanged engine inventory
  against clean/gold and representative offline outputs reported zero
  undocumented code/data runs. Documentation validation passed 497 relative links.
- After explicit approval, the candidate was installed using the normal patcher
  workflow and started under x32dbg at 1920×1200. The font measurement above is
  the live result; neither target clipping case was reproduced. The installation
  was returned to 3440×1440. The game had rewritten player settings on startup;
  that file was copied aside and the exact pre-test INI restored. All 13 runtime
  ownership rows and 1,854 Override rows match installed file hashes. The live
  executable remained unchanged, and all investigation breakpoints and scratch
  allocations were removed. Machine paths, rollback instructions and complete
  snapshot hashes are recorded in ignored local handoff and review artifacts.

Still required: physical arrows/Enter and stationary-pointer gameplay checks,
the exact XP and wrapped action-name reproduction with native wrapping and final
draw bounds, companion height-getter consistency including Exit Game, and live
controller on/off at representative resolutions. No Windows native height
repair or claim of a verified physical-keyboard fix is included in this commit.
The user authorized a local commit and PC shutdown; no push or release was
requested.

## Regenerated Windows resources, 2026-10-03

The full Windows source build (`.\build_kmrp.ps1 -Plain`, without
`-ReuseResources`) completed in 13m19s. The resulting 1.5.0 installer is
164,820,480 bytes, SHA256
`17ae6d0dbc764256d6dbd42b27683936eb94b9b6acb0647a634293ec88933595`.
All 66 regenerated archives reconstruct exactly from the shared resource pool;
`Test-GeneratedGuiGeometry.py` passes on all 66. These are archive measurements:

| Resolution | Active action-label height |
| --- | --- |
| 800×600 | 48px |
| 1280×720 | 48px |
| 1920×1200 | 82px |
| 3440×1440 | 96px |
| 3840×2160 | 144px |

The preserved pre-merge Windows installer, SHA256
`184b2d3ff8d37d404d6037fea422aff0e9007e8a73907ecbac6157b113bd3b40`,
was installed into an isolated game copy at 1920×1200. Its installed
`LBL_ACTIONDESC` rectangle is (1617,1050,295,38). The regenerated archive's
rectangle is (1617,1006,295,82), with the same text bottom at 1088px. Neither
rectangle is a measured final native draw rectangle.

`Test-InstalledOverride.ps1` passed at the five resolutions in the table and at
2560×1200, 1600×1000 and 3440×1400 through the blend path: installed files match
the build, and restore removes the owned resources. The source-only Windows
engine regression also passes its 68 historical runs, 11 pages, 46 relocations
and 69 resolution outputs. The packaged KPM guard regression passes its four
corruption-rejection cases. `Test-ControllerSupport.ps1` passes at 1280×720,
1920×1200 and 3840×2160, including controller on/off, switching the option on an
installed game, core-hook retention, rollback and CD/Steam ownership. These are
installer/configuration checks, not controller gameplay. The reinstall-over-an-
older-build regression passes at 1920×1200, including its legacy-build and
damaged-backup cases. `Test-KpmEdition.ps1` also passes, including runtime
takeover and the unrelated moduleless-patch ownership cases. The Windows module and engine template remain
byte-identical to the baseline; no Windows native rounding repair has been
included. Controller gameplay, both clipping cases and exit-confirmation
termination still require live measurements before Windows support is claimed.
