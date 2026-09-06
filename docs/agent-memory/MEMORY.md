# Durable engineering memory

This file records cross-cutting facts that prevent repeated mistakes. Subsystem
details still belong in `docs/` or `reverse-engineering/`.

## Executable identity and patch safety

- The supported clean executable is 4,042,752 bytes with SHA-256
  `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
  This is encoded in `GoldPatch` and checked by the build. Re-read the constant
  before relying on it in a future release.
- The v2.10.0 gold image is 4,083,712 bytes with SHA-256
  `9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC`.
  It is historical/current-release identity, not a timeless invariant.
- The current unreleased gold v23 has the same length and SHA-256
  `29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8`.
  Relative to v21 it enables `IMAGE_FILE_LARGE_ADDRESS_AWARE` at PE file
  offset `0x926` and replaces both 640x480 full-screen movie-mode pairs with
  the 3440x1440 gold reference; recheck the build constants before relying on it.
- Restore currently proves KMRP ownership through the sidecar's patched hash and
  requires the backup to match the canonical clean source. Supporting recognized
  prepatched inputs therefore requires coordinated changes to inspection, apply,
  rollback, reinstall, manifest, backup verification, and restore—not merely an
  extra accepted source hash. Evidence: `PatchOperations` in
  `src/patcher/KmrpPatcher.cs`.
- Appended KMRP PE sections use a different VA-to-file relationship from original
  sections. Always take the address convention from
  `reverse-engineering/exe-patching.md`; do not apply `FILE = VA - 0x400000`
  blindly to appended sections.

## Shared scaling behavior

- The shared pixel scale is `max(1.0, height / 720)`: 1× at 720p, 1.5× at
  1080p, 2× at 1440p, and 3× at 2160p. Font TXIs, GUI resources, row/icon sizes,
  popup geometry, and executable constants must remain synchronized.
- Most non-3440 GUI files begin with their upstream resolution-specific version.
  Hand-tuned gold geometry is transferred only when the 3440×1440 gold file
  differs from its upstream counterpart. Dedicated branches own `confirm.gui`,
  `map.gui`, and `mipc*.gui`. Evidence: `tools/prepare_universal_resources.py`.
- At resolutions other than 3440×1440, the engine falls through to
  `mipc28x6.gui`; only 3440×1440 selects `mipc210x7.gui` through the current
  hardcoded selector. Per-resolution menu-background generation depends on that
  behavior. Reverify if the selector is ever generalized.

## Post-release observations recorded 2026-09-05

- Windows DPI scaling can add a second scaling layer to KOTOR at 3840×2160.
  Two independent users reported the zoom and confirmed that Compatibility →
  High DPI scaling override → Application fixes it. The corresponding per-user
  AppCompat layer is `HIGHDPIAWARE`. Issue #3's implementation appends that token
  to the exact executable path, records the prior string in `KMRP_DPI.manifest`,
  and restores only if the live value still equals KMRP's value. The four ownership
  cases pass in `testing/regression/Test-DpiCompatibility.ps1` on Windows 11 build
  26200; visual 125–200% and Windows 10 coverage remain untested. Full contract:
  `docs/windows-dpi-scaling.md`.
- The 3840×2160 Feedback defect came from `LB_OPTIONS` and `LB_DESC` parent
  listboxes being scaled while their embedded `PROTOITEM` rectangles stayed at
  vanilla coordinates and 240-pixel widths. The generator now fits each prototype
  to the exact non-scrollbar part of its parent. The target strip and eight
  transient notification icons had a separate width-driven HUD scaling defect;
  they now use `max(1, height / 720)` relative to the 2× gold values. All 48
  active HUD/prototype pairs pass
  `testing/regression/Test-GeneratedGuiGeometry.py`. A later report found the
  same stale-prototype defect in `scriptselect.gui` and a separate containment
  error in `confirm.gui`: its panel ended at y=375 while Cancel ended at y=490.
  Character Scripts now fits both prototypes to their parent content areas and
  the tuned confirmation panel is 525px high at scale 2. Evidence and exact 4K extents:
  `docs/universal-resolution-math.md#reported-4k-layout-repairs`.
- The clean and v2.10.0 gold executable PE characteristics are `0x010F`; Large
  Address Aware is not enabled. The characteristics field is at file offset
  `0x926`, and enabling `IMAGE_FILE_LARGE_ADDRESS_AWARE` adds bit `0x0020`, yielding
  `0x012F`. This makes issue #7 a one-bit binary change but a multi-path
  validation/restore change.
- Movie rendering is dynamic: the Bink path uses the live client rectangle and
  BIK dimensions for aspect-fit scaling and centring. The hardcoded part is a
  separate 640x480 display mode in two operand pairs. Gold v23 carries 3440x1440
  at FILE `0x3D6C`/`0x3D78` and `0x1F5B3B`/`0x1F5B43`, and
  `ResolutionPatch` replaces all four per install. The short second signature in
  a public helper is ambiguous and corrupts unrelated operands on this build;
  never adopt it. Evidence: `reverse-engineering/movies.md`.
- Optional controller support uses Saul0097's KPM Xbox Controls K1 module through
  a statically linked KPM runtime and K1DC's ASI loader. It owns
  `patch_config.toml`, refuses an external one, and applies six verified in-memory
  detours without changing the executable on disk. The PC `dialog.tlk` and GUI
  texture pack retain Xbox tutorial strings and seven 32x32 button textures, but
  those strings describe the original console layout and conflict with the
  module (for example white-button versus LB pause). Do not enable them wholesale.
  KMRP instead adds last-active-input state to the module and changes the empty
  normal fills of ten existing Character, Container, Save/Load, and Upgrade
  action controls in memory. Each of the 48 archives carries aspect-compensated,
  original A/B/X badge textures; keyboard/mouse input and disconnect clear them.
  Never derive live controls from packaged GUI list indices: an unreleased build
  did so and crashed in `SetFillImage` at `swkotor.exe+0x14C3E`. Use the concrete
  panel's database-verified embedded button offsets documented in the reference.
  Preserve the visible mouse cursor at startup; the upstream hidden/parked
  default made controller-enabled Windows installs appear to have lost mouse
  input. F9 remains the explicit cursor park/hide toggle.
  Evidence and untested visual boundary: `docs/controller-support.md`.
- Proton-sensitive packaged-resource checks must be case-exact even when run on
  Windows. The 2026-09-05 audit parsed 3,889 GUIs in all 48 archives, found no
  case collisions or non-portable member paths, resolved every referenced font
  pair, and confirmed the active HUD's `LBL_NAME` uses
  `dialogfont10x10.tga/.txi`. This excludes a missing/case-only KMRP font asset as
  the direct cause of the reported absent names, but not a Proton render/load or
  old-geometry issue. Evidence: `testing/regression/Test-ProtonResourceCompatibility.py`
  and `docs/linux-proton-steam-deck.md`.

## Approaches to avoid

- Do not accept arbitrary same-length or vaguely "known modded" executables.
- Do not patch a discovered constant before searching the full enclosing function,
  conditional branches, and parallel constructors for duplicate sites.
- Do not edit a generated `gui-<resolution>.zip` as the fix; repair its owning
  source or generator and rebuild.
- Do not infer play-tested coverage from archive inspection or numeric checks.
- Do not copy the changing GitHub backlog into durable memory. Store only findings
  that remain useful after an issue closes.
