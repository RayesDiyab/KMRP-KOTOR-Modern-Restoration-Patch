# Durable engineering memory

This file records cross-cutting facts that prevent repeated mistakes. Subsystem
details still belong in `docs/` or `reverse-engineering/`.

## Executable identity and patch safety

- The supported clean executable is 4,042,752 bytes with SHA-256
  `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
  This is encoded in `GoldPatch` and checked by the build. Re-read the constant
  before relying on it in a future release.
- The v2.10.0 (KMRP 1.0) gold image is 4,083,712 bytes with SHA-256
  `9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC`.
  It is historical/current-release identity, not a timeless invariant.
- The current unreleased gold is v24, 4,087,808 bytes with SHA-256
  `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`
  (checked 2026-09-24). Relative to v21 it enables
  `IMAGE_FILE_LARGE_ADDRESS_AWARE` at PE file offset `0x926` (v22), replaces both
  640x480 full-screen movie-mode pairs with the 3440x1440 gold reference (v23),
  and adds the eleventh section, `.kmv`, the Bink aspect fit (v24). Gold is not
  what ships: the installer's output differs from it even at 3440x1440. Recheck
  the build constants before relying on any of this. (This entry named v23 until
  2026-09-24.)
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
  26200. In play, the maintainer reported it working at 150% on 2026-09-25, and
  issue #3 was closed; 125%, 175%, 200% and Windows 10 remain untested. Full contract:
  `docs/windows-dpi-scaling.md`.
- The 3840×2160 Feedback defect was first attributed to `LB_OPTIONS` and
  `LB_DESC` parent listboxes being scaled while their embedded `PROTOITEM`
  rectangles stayed at vanilla coordinates and 240-pixel widths, and the
  generator fitted each prototype to its parent. **That was wrong and was
  reverted on 2026-09-06**: it broke Character Scripts in play, and the
  play-tested gold files leave the prototypes at their upstream values. The
  prototypes now ship exactly as upstream has them, which
  `Test-GeneratedGuiGeometry.py` asserts; Feedback got a scrollbar gutter and
  Script Selection centred rows instead (2026-09-24). The target strip and eight
  transient notification icons had a separate width-driven HUD scaling defect;
  they now use `max(1, height / 720)` relative to the 2× gold values. All 48
  active HUD/prototype pairs pass
  `testing/regression/Test-GeneratedGuiGeometry.py`. A later report found the
  same stale-prototype defect in `scriptselect.gui` and a separate containment
  error in `confirm.gui`: its panel ended at y=375 while Cancel ended at y=490.
  Character Scripts' prototypes were fitted the same way, and reverted with
  Feedback's; the tuned confirmation panel is 525px high at scale 2. Evidence and exact 4K extents:
  `docs/universal-resolution-math.md#reported-4k-layout-repairs`.
- The clean and v2.10.0 (KMRP 1.0) gold executable PE characteristics are `0x010F`; Large
  Address Aware is not enabled. The characteristics field is at file offset
  `0x926`, and enabling `IMAGE_FILE_LARGE_ADDRESS_AWARE` adds bit `0x0020`, yielding
  `0x012F`. This makes issue #7 a one-bit binary change but a multi-path
  validation/restore change.
- Retail Bink playback scales every movie by the client **width** alone, so a
  movie narrower than the screen is cropped; gold v24 redirects `0x004057AC` into
  `.kmv`, a true aspect fit. (This entry used to say the path already
  aspect-fitted -- the claim `reverse-engineering/movies.md` retracted on
  2026-09-06.) Separately, there is a 640x480 display mode in two operand pairs.
  Gold carries 3440x1440 at FILE `0x3D6C`/`0x3D78` and `0x1F5B3B`/`0x1F5B43`, and
  `ResolutionPatch` replaces all four per install. The short second signature in
  a public helper is ambiguous and corrupts unrelated operands on this build;
  never adopt it. Evidence: `reverse-engineering/movies.md`.
- Controller support -- an Advanced Settings component, on by default since
  2026-09-24 -- is KMRP's native path, grown from Saul0097's KPM Xbox Controls K1
  module. Since 2026-09-29 it is the `kmrp-controller` patch on KOTOR Patch
  Manager's runtime, which KMRP's installer installs itself (KPM's `binkw32.dll`
  proxy, `KotorPatcher.dll` from the submodule; `docs/kpm-edition.md` 1a), or for
  KOTOR Patch Manager itself when KPM's runtime is in the folder (KMRP for KPM
  was a separate installer until that day; a "KOTOR Patch Manager" option that
  also chose it was removed on 2026-09-30). Until then it was
  loaded by a statically linked KPM runtime through the ASI loader K1DC
  ships. It owns `patch_config.toml`, refuses an external one, and applies its
  hooks in memory without changing the executable on disk: 18 detours and 4 byte
  patches on 2026-09-24, 26 detours since the rumble mixer of 2026-09-25, and 33
  detours and 4 byte patches since the echo guard of 2026-09-28 -- 37 entries;
  9 (5 detours) with controller support off, since the runtime installs on every
  patch (this entry said six detours, the first integration's count, and then
  stopped at 26 until 2026-09-28). Recount with `tools/check_patcher_hook_table.py`,
  which since 2026-09-29 reads the config sections the build generates
  (`ControllerOperations.BuildConfig`, the hand-written table, is gone); `kotor1.hooks.toml` holds more (46) than
  is installed. The paragraph below is the first integration's prompt design; the
  current one covers 57 controls in four controller families -- see
  `docs/controller-support.md` and `docs/controller-prompt-specification.md`. The PC `dialog.tlk` and GUI
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
  and `docs/linux-proton-steam-deck.md`. Re-run against the 2026-09-24 build:
  3,937 GUIs in 48 archives, still case-exact and collision-free.

## Approaches to avoid

- Do not screenshot a fullscreen game with GDI (`PIL.ImageGrab`, BitBlt): it
  returns a stale frame while KOTOR runs fullscreen. Desktop Duplication reads
  the composed output: `ffmpeg -filter_complex
  ddagrab=output_idx=0,hwdownload,format=bgra -frames:v 1 shot.png` (checked
  2026-09-25 at 3440x1440 and 1920x1080).
- Do not accept arbitrary same-length or vaguely "known modded" executables.
- Do not patch a discovered constant before searching the full enclosing function,
  conditional branches, and parallel constructors for duplicate sites.
- Do not edit a generated `gui-<resolution>.zip` as the fix; repair its owning
  source or generator and rebuild.
- Do not look for the `gui-<resolution>.zip` archives inside the built installer.
  Since 2026-09-25 they are embedded as one pool of distinct files
  (`tools/pack_resolution_layouts.py`, `build\kmrp\resolution-layouts.zip`).
  The archives are the build's intermediates, which the Python checks read;
  `Test-InstalledOverride.ps1` checks what the installer writes from the pool.
- Do not infer play-tested coverage from archive inspection or numeric checks.
- Do not copy the changing GitHub backlog into durable memory. Store only findings
  that remain useful after an issue closes.
