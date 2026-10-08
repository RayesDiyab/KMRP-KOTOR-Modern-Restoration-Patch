# Patcher UI, asset, and build architecture

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


**Corrections, 2026-10-04 ([one patch since 2026-10-04](kpm-edition.md#one-patch-since-2026-10-04)).** This document was
written for the installer that installed four patches, a data file and the
Override files, and most of its tables are measurements of that build. What no
longer holds (the right-hand column was brought up to 2026-10-08: two patches since
2026-10-05, no resolution choice since 2026-10-07):

| Here | Now |
| --- | --- |
| "Current build, 2026-10-01 ... 168,698,880 bytes ... 33 resources" and its table | 146,874,368 bytes as built on 2026-10-06 (195,751,424 on 2026-10-04, before the bank left out what the module can write itself). Gone: `Kmrp.override.layouts`, `Kmrp.override.common`, `Kmrp.bundled`, `Kmrp.controller.module`, `Kmrp.controller.sdl`, `Kmrp.controller.sdllicense`, the four `Kmrp.engine.config.*` and the four `Kmrp.kpatch.*`. New: `Kmrp.kpatch` (KMRP's patch, which holds its module), `KmrpController.kpatch` (the controller patch, since 2026-10-05), `Kmrp.engine.hooks` and `KmrpController.engine.hooks`; `Kmrp.kpatch.readme` is kept (resource names read from `build_kmrp.ps1`; the assembly's resources were not enumerated again) |
| Step 3 as a list of 66 resolutions with a custom size, `resolutionBox` | "3. Resolutions": one line and no control, "Starts at W × H. The game lists every resolution the connected display supports." (`ResolutionSelection.Summary`). From 2026-10-04 to 2026-10-07 it had a *Choose* button opening `ResolutionsDialog`, a checklist with custom sizes; both were removed with the choice |
| Install building `kmrp-kpm.dat`, writing the data file, SDL and the modules, and the Override files | none of these: KMRP's module, `patches\kmrp.dll`, the controller patch's, `patches\kmrp-controller.dll`, while Controller Support is on, and `patch_config.toml` with both patches' hooks and no options table |
| "restores replaced Override files" | only for an install made before 2026-10-04 |
| "packages the KPM patches", "the four KPM packages", the pool "which the installer embeds" | two packages, `KMRP.kpatch` (`tools/build_native_kpatch.py`) and `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` (`tools/build_controller_kpatch.py`); the pool is still built, for the module's resource bank and the macOS build, and is not embedded |
| `--in-place` as the "full runtime, DPI, INI, Override" transaction | runtime, DPI, NVIDIA, INI; no Override |
| The regression list naming `Test-ControllerSupport.ps1` and `Test-InstalledOverride.ps1` | corrected in place below: `Test-InstallerPatch.ps1`, `Test-KpatchSource.py` and `Test-ControllerKpatch.py` |
| Advanced Settings with three rows | six since 2026-10-09, in the maintainer's order (Native Controller Support, Modern Driver Compatibility, Area Map Marker Fixes, HD Item Icons, High FPS Fix, Debug Logs), with High FPS Fix (`KmrpSettings.HighFpsFix`, D3M0's patch as a third one, off by default); five since 2026-10-08, with HD Item Icons (`KmrpSettings.HdIcons`, the `hd-icons` option of KMRP's patch, on by default); four before that: Debug Logs, off by default, was the fourth (`KmrpSettings.DebugLogs`, the `debug-logs` option of both patches). Controller Support decides whether the controller patch is installed at all, not an option of KMRP's patch |
| The options written into `patch_config.toml` | written to `configs\kmrp.ini` (`map-notes`, `debug-logs`) and, with the controller patch, `configs\kmrp-controller.ini` (`debug-logs`), section `[Patch Options]` (`WritePatchOptions`); a manifest row `options` records it for restore |
| `tools/build_kpatch.py`, `tools/check_patcher_hook_table.py`, `src/controller-native/build.cmd` | removed on 2026-10-04; `tools/kpatch_common.py` holds the shared helpers |
| Any resolution list, dropdown or checklist in the window, wherever the text below names one (the dimmed step 3, the animation measured "while scrolling the resolution dropdown") | there is none since 2026-10-07; those passages are measurements of the builds that had one |

This document describes the shipping Windows patcher in
`src/patcher/KmrpPatcher.cs`, the assets compiled into it, and the
build and verification workflow. The current 1.5.0 candidate is unreleased;
the dated measurements below are not all from the public 1.0 installer.
Resolution and game-engine math remain in
`docs/universal-resolution-math.md`; font and listbox patches remain in
`docs/font-scaling.md` and `reverse-engineering/listbox-geometry.md`.

## Shipping artifact

`build_kmrp.ps1` produces one portable executable:

```text
dist/KMRP - KOTOR Modern Restoration Patch.exe
```

No companion asset folder is required. **Current build, 2026-10-01:** installer
1.5.0, 168,698,880 bytes, SHA-256
`7C8CB15327EA353564CAFCF3F52E1459EBDC80178145AF9E4044A88565877B38`,
cross-built on Ubuntu. Reflection over the actual assembly's
`GetManifestResourceNames()` returned **33 resources**. The names and lengths
are retained locally in ignored `build/windows-installer-resource-audit.json`.

| Resource group | Count | Current payload |
| --- | ---: | --- |
| `Kmrp.engine.source` | 1 | 48,012-byte source-built engine template; no gold delta or clean-image fragments |
| `Kmrp.resolutions`, `Kmrp.override.layouts`, `Kmrp.override.common`, `Kmrp.bundled`, `Kmrp.guiblend` | 5 | 66-resolution catalog, verified layout pool, common artwork, bundled-file list, custom-size blend table |
| `Kmrp.controller.module`, `.sdl`, `.sdllicense` | 3 | Native KMRP module, SDL 3.4.16 and its licence |
| `Kmrp.engine.runtime`, `.proxy`, `.license` | 3 | KPM DLL, Bink proxy and KPM licence |
| `Kmrp.engine.config.kmrp`, `.kmrp-controller`, `.kmrp-movies`, `.kmrp-map-notes` | 4 | Four config sections generated from the patch hook table |
| `Kmrp.kpatch.kmrp`, `.kmrp-controller`, `.kmrp-movies`, `.kmrp-map-notes`, `Kmrp.kpatch.readme` | 5 | Four KPM packages and their instructions |
| `Kmrp.drivercompat.dinput8`, `.asi`, `Kmrp.license.drivercompat` | 3 | Optional Modern Driver Compatibility payload and licence |
| `Kmrp.license.highresolutionmenus` | 1 | High Resolution Menus GPL notice |
| `Kmrp.brand`, seven `Kmrp.icon.*` | 8 | Branding and installer icons |

**Correction, 2026-10-01:** the former resources `Kmrp.goldpatch`,
`Kmrp.kpm.relocations` and `Kmrp.kpm.originals` are absent. Relocations and
original-byte guards are now in the source template. See
[Windows engine source](windows-engine-source.md) for the recipe and regression.
High FPS Fixes is not an embedded installer component.

The historical 2026-09-25 build (`4EF3C181…`, 145,208,320 bytes) embedded
22 resources:

| resource | what |
| --- | --- |
| `Kmrp.goldpatch` | the verified clean-to-gold executable delta, 47,730 bytes |
| `Kmrp.resolutions` | the 49-resolution catalog, `resolutions.tsv` |
| `Kmrp.override.layouts` | the GUI files of all 49 resolutions, each set with that resolution's 18 font atlases, as one pool: each distinct file once, and an index per resolution (`tools/pack_resolution_layouts.py`; the installer reads it through `GuiPool`) |
| `Kmrp.override.common` | the common Override archive: shared textures, icons, portraits and prompt art, but no font atlas |
| `Kmrp.bundled` | the list of bundled third-party Override files, which yield to the player's own |
| `Kmrp.license.highresolutionmenus`, `Kmrp.license.drivercompat` | the KOTOR High Resolution Menus GPL notice and K1DC's MPL licence |
| `Kmrp.drivercompat.dinput8`, `Kmrp.drivercompat.asi` | K1 Modern Driver Compatibility and its ASI loader |
| `Kmrp.controller.module`, `.runtime`, `.sdl`, `.sdllicense`, `.kpmlicense` | the controller component: KMRP's module, the KPM runtime, SDL 3 and its licence, and KPM's MIT licence. Since 2026-09-29 `.runtime` and `.kpmlicense` are gone; see below |
| `Kmrp.brand`, seven `Kmrp.icon.*` | the brand artwork and the UI icons: folder, missing, monitor, Settings, shield, tools, verified |

Since 2026-09-29 the catalog and the pool hold 66 resolutions: the 17 of the macOS group
were added. The 2026-10-01 Ubuntu build above measured all 66; the older
unmeasured-build wording is superseded by its package and source checks.

Until 2026-09-25 each resolution's archive was embedded whole, as
`Kmrp.override.gui.<W>x<H>`: 70 resources, and 208,672,256 bytes in the last
such build (`DB9D7A08…`). Why the pool replaced them is under *Changed* in
`CHANGELOG.md`.

Since 2026-09-29, when the installer moved onto KOTOR Patch Manager's runtime
([kpm-edition.md](kpm-edition.md), section 1a), it also embeds:

| resource | what |
| --- | --- |
| `Kmrp.engine.runtime`, `Kmrp.engine.proxy` | `KotorPatcher.dll` and KProxy's `binkw32.dll`, built from the submodule by `src/kpm-runtime/build.cmd` |
| `Kmrp.engine.license` | KOTOR Patch Manager's MIT licence, the submodule's `LICENSE` |
| `Kmrp.engine.config.kmrp`, `.kmrp-controller`, `.kmrp-movies`, `.kmrp-map-notes` | each KMRP patch's `patch_config.toml` section (`tools/build_kpatch.py --config-dir`) |
| `Kmrp.kpm.relocations`, `Kmrp.kpm.originals` | the relocation table and the unmodified executable's bytes the data file is built from |

and no longer `Kmrp.controller.runtime` or `Kmrp.controller.kpmlicense`, the
standalone's runtime from Saul0097's package and that package's copy of the
same licence. The resolution catalog, `Kmrp.resolutions`, has 66 rows since the
macOS sizes were added the same day.

The supported editable executable is identified by SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
The current gold, v24, is 4,087,808 bytes with SHA-256
`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`.
`TargetHash` and `TargetLength` in `GoldPatch`, `EXPECTED_GOLD_SHA256` in
`tools/generate_gold_delta.py` identify the historical gold reference.
**Correction, 2026-10-01:** `build_kmrp.ps1` no longer has a `-GoldExe` argument
and does not read that snapshot. *Corrected 2026-09-24:* this section
named gold v14 as current, and listed six resources.

## Main-window flow

The interface is one four-step card. State is derived from the selected
`swkotor.exe`; it is not stored separately in the UI.

| Step | Before patching | After patching |
| --- | --- | --- |
| 1. Game folder | Browse for the KOTOR directory. | Shows the selected directory. |
| 2. Game version | Hash-verifies a supported Steam, GOG or editable CD 1.03 executable and names the detected build. A missing or unsupported file is named on the step's subtitle line (until 2026-09-30 it expanded a recovery panel). | Shows the supplied Verified badge and installed state. |
| 3. Resolutions | Nothing to choose since 2026-10-07: "Starts at W × H. The game lists every resolution the connected display supports." (Until 2026-10-04 a dropdown of the listed resolutions, grouped by aspect ratio, with a custom size; then a *Choose* checklist until 2026-10-07.) | Shows the size the game starts at, read from the install's record, and "The game starts at this size. Choose another in the game, under Options, Graphics." |
| 4. Apply | Shows readiness, progress, or a recovery instruction. | Permanently shows `Patched successfully` and `KOTOR is ready to play at W × H.`, or, in a game KOTOR Patch Manager manages, "Managed by KOTOR Patch Manager: tick KMRP there, then Apply and Launch." |

The primary button has one identity at a time:

- a supported clean executable produces **Start Patching**;
- a verified patched install with complete backups produces
  **Restore Original**;
- an unresolved executable or game setup keeps the action disabled;
- while work is running, all mutation controls are disabled and the primary
  button becomes the progress surface: a pale illuminated-blue fill advances
  inside the rounded button while its centred label shows the current stage and
  percentage. Step 4 keeps one calm, stable instruction with no percentage or
  file-level detail.

The success state is deliberately idempotent. Refocusing, clicking, or
reactivating the window calls `RefreshStatus()`, but a gold install is rebuilt
into the same `Patched successfully` state and the same installed-resolution
message. There is no second post-click "protected resolution" message.

### The verification recovery state

*Retired 2026-09-30, kept as the record of its design.* Step 2 no longer expands:
since KMRP takes Steam's, GOG's and the editable executable as they are, it names
the version found, or says on its one subtitle line which file it could not use,
with no *Get Editable EXE* or *Check Again* buttons. What remains in the code is
the dimming: steps 3 and 4 are drawn dimmed (`StepRow.Dimmed`) until a supported
executable is found. `resolutionBox`, named below, no longer exists.

When the editable executable was missing or wrong, step 2 expanded to carry the recovery
actions. It has to look like the same product as the rest of the card, and three
things were making it look borrowed from somewhere else:

- it was a **darker fill inside its own border**, a second level of nesting that
  appears nowhere else in the UI. It now uses the card's own fill and edge, so it
  reads as part of step 2 rather than as a panel within a panel;
- its content was **indented inside that box**, breaking the left alignment every
  other row shares. It now starts at the same content left as the step titles;
- it carried a **bold amber heading**, the only warm colour in the product, restating
  what the step title and subtitle had already said twice. The heading is gone. Which
  failure state it is comes from the chip on the right of the step, the way it does
  for every other step, and each body line stands on its own.

The guidance is **one line**, on the step's own subtitle, and the badge on the right
stands alone with no words beside it -- the subtitle already says which failure it is
and what to do, so repeating it in the chip was the same duplication in a smaller
font. `StateLabel` draws the badge at 48 design pixels instead of 32 when its text is
empty, which is why the state labels are 56 tall rather than 36.

Spacing inside the step is measured ink-to-ink, not from control boxes: the fonts
carry different internal leading, so box positions do not predict the visual gap. On a
render at uiScale 0.868 the title-to-subtitle gap was 11px and the subtitle-to-buttons
gap 5px; moving the button strip from y84 to y91 makes both 11. The guidance used to be three
stacked restatements -- the subtitle, a heading, and a path line -- which made step 2
tall enough to push the rest of the flow off the card.

That reclaimed height pays for **step 3 staying in the flow**, dimmed, so the card
never collapses into a shorter, different-looking product. `StepRow.Dimmed` draws the
icon, title and subtitle in `TextFaint`; measured, the title drops from peak ink
luminance 242 to 136. The resolution dropdown is hidden while dimmed, because a live
control inside a dimmed row invites a click that does nothing. Step 4 has no room, and
the action button below already stands for it.

Two things to know if this is edited again. `resolutionBox.Visible` is set in two
places -- the recovery update and the general status refresh -- and the second runs
last, so both must agree or the dropdown reappears inside the dimmed row. And moving a
step means moving its entry in `designBounds`, not just its live bounds, because
`ApplyControlScale` restores every control from that dictionary on each rescale; that
is what `PlaceStep` is for.

### User-facing language boundary

The main card explains the next action and avoids implementation details:

- hashes stay in validation code and logs;
- raw fallback paths are not displayed as user selections;
- `swkotor.ini`, `[Graphics Options]`, and incomplete-key diagnostics are not
  shown in Step 4;
- a missing INI is described as **Game setup needed** with the instruction to
  launch KOTOR once, close it, and check again.

Detailed file paths and verification failures remain available through
**Open Log** and blocking error dialogs where they are actionable.

## Typography, artwork, and status icons

The visual system uses the supplied KOTOR brand image, Old Republic for display
roles, and Segoe UI for body text. The current design-space sizes are:

- step titles: 22 pt;
- step subtitles: 16.5 pt;
- right-side states: 18 pt bold;
- Browse and primary action labels: 18 pt;
- secondary buttons: 15.5 pt;
- recovery title/body/path: 19 / 15 / 14.5 pt;
- footer links and credit: 15.5 pt.

The seven sources -- the four step icons, Verified, Missing and the Advanced
Settings gear -- live in `assets/branding/ui-icons/`. Run:

```powershell
python .\tools\prepare_app_icons.py
```

The script:

1. classifies files by filename keyword;
2. crops to pixels with alpha greater than 8;
3. preserves aspect ratio while scaling the longest ink edge to 224 pixels;
4. centres the result on a 256 × 256 transparent canvas;
5. writes white artwork to `src/patcher/icons/`.

White is intentional. The patcher multiplies the resource by the current theme
colour at draw time, keeping icon colour controlled by the UI palette. Missing
step artwork falls back to the built-in vector glyph. Missing Verified artwork
falls back to the text-only state. The Verified resource is drawn at 32 design
pixels and grouped optically with its label.

## Header ambience

Light enters the top bar from a source above the window, lights a volume of drifting
smoke, and small motes fall through it. It is generated in code by `LightField` --
procedural noise plus a particle pass -- not imported from any stock asset, so no
third-party licence is attached to it.

The source itself is deliberately off-screen and spans the full width. An earlier
version put a point source behind the crest; it read as a glowing ball, and it cost
the wordmark its legibility (see the table below). With the light entering from above
the top edge instead, it has died away by the time it reaches the letters, so density
and legibility stopped competing.

### How it is built

The billowing structure is fBm noise rather than sprites, because soft blobs cannot
produce the fractal, curdled edge that reads as smoke. The turbulence comes from
**domain warping**: the noise field is sampled at coordinates that are themselves
offset by another noise field, which folds the plume into itself instead of leaving
it as smooth drifting fog. Perlin gradient noise, not value noise -- value noise
shows axis-aligned blocking once it is warped.

The smoke, the light falloff, and the descending shafts accumulate into one scalar
emission buffer at `1/Downscale` resolution. A single bloom pass and a single colour
ramp then light all of them consistently, and the buffer is upscaled, which supplies
the final softening for free. The ramp is the blue counterpart of the reference's
black to olive to gold to white-hot core.

### Cost

This is per-pixel CPU work, so it is measured, not assumed. `Downscale` is the
dominant lever: the noise is evaluated nine times per buffer pixel, so halving it
quadruples the cost.

At full design scale (a 1980 x 420 header, the worst case) the shipping settings
render in **20.2 ms average**, against a 46.8 ms frame budget -- a 40 ms
WinForms timer lands on Windows' 15.6 ms granularity and therefore fires every
~46.8 ms, or about 21 fps. Measured in the running application, the effect costs
about **40% of one core** while the window is focused and idle.

One thing was required to get it that low and should be kept:

- the scaled brand is cached as a bitmap. The header repaints on every animation
  frame, and re-running a 650 x 350 bicubic resize per frame cost more than the plume
  itself -- removing it took the process from 57% of a core to 40%;
- the effect keeps running while a patch is in progress, while the window is in the
  background, and through a live resize. Patching is on a `BackgroundWorker` and reaches the UI thread only
  through `ReportProgress`, so painting the header does not delay the file work and
  the file work does not stall the animation. It costs roughly 40% of a core for as
  long as the window is open, background included; if that ever needs reducing, halve
  the timer rate when the window is not active rather than stopping it.

### Threading

Frames are generated on a private `BelowNormal` thread into an off-screen surface;
the UI thread only blits the finished frame and draws the brand over it. Two
double-buffered surfaces are swapped under a lock, so the UI thread reads the front
while the render thread draws the back and neither ever touches the other's bitmap.

This was not the original design and the reason for it is worth keeping. Painting the
plume inline cost the UI thread about 20 ms of every 62 ms frame. That is fine on an
idle window, but it leaves too little headroom to also service a dropdown being
scrolled, and the animation stuttered there. Measured per thread after the move:

| Thread | Share of one core |
| --- | --- |
| Render thread | 22.9% |
| UI thread | 5.5% |

Total CPU is unchanged at about 28%; what changed is where it is spent.

**Frames are presented straight to the window from the render thread**, not posted to
the UI thread. Posting them put every frame in the message queue behind whatever was
already there. Measured while scrolling the resolution dropdown, with the render
thread already off the UI thread:

| | Value |
| --- | --- |
| Frame interval | mean 61.9 ms, sd **1.0 ms** |
| Present latency | mean 0.9-7.2 ms, max **61.8 ms** |

Frames were being produced within a millisecond of perfect and then waiting up to a
full frame period to reach the screen. That is the stutter, and no amount of further
optimising the render loop would have touched it -- the two numbers separate the two
possible causes, which is why they are recorded separately.

`PresentDirect` takes its own device context for the window and blits one opaque
bitmap, serialised against the UI thread through the same lock the surfaces are
swapped under. It requires the frame to be complete, so the render thread also
composites the brand and tagline, baked to a transparent overlay by the UI thread
whenever the header size changes -- fonts and scaled artwork cannot be touched from
the render thread. Direct presentation is disabled while a resize preview is up,
where the UI thread owns the frame, and while minimised.

The instrumentation that produced those numbers was removed once it had done its job,
so a stray keypress in a released build cannot raise a dialog full of frame times. If
this ever needs diagnosing again, restore it from commit `63545f6`: it recorded both
figures into ring buffers and dumped mean, max and standard deviation to the log. The
lesson worth keeping is that the two must be measured separately -- three fixes were
aimed at frame generation when generation was never the problem.

Two earlier attempts at this failed and are worth not repeating. A
`System.Windows.Forms.Timer` is `SetTimer`, and WM_TIMER is synthesized by Windows
only when the thread's message queue is otherwise empty -- the lowest priority
message there is, alongside WM_PAINT. A wheel-scroll flood starves it completely, so
the animation stopped dead over the dropdown. Moving to a `System.Threading.Timer`
marshalled through `BeginInvoke` fixed the stopping, because a posted message is not
queue-synthesized and is dispatched by the nested modal loops dropdowns run -- but it
did not fix the stutter, because the expensive work was still on the UI thread.
`Invalidate` is still followed by `Update()` for the same starvation reason.

Timing comes from a `Stopwatch`, not `Environment.TickCount`: TickCount advances in
~15.6 ms steps, so at a 62 ms frame it quantises the delta by nearly a quarter and
the plume pulses.

The simulation never stops. `Step` runs on every tick regardless of window state, so
the plume is never frozen in time and never resumes from a stale frame; only painting
is ever skipped, and only when the window is minimised, where Windows delivers no
paint to the client area and rendering would be invisible work.

**The header animates during a live resize too.** The snapshot exists because
re-laying out the card's child controls on every mouse move is expensive -- but the
header has no child controls, so it can be repainted live over the frozen frame. At
`BeginResizePreview` the brand and tagline are baked into a transparent layer; each
resize frame then paints background, plume, and that layer stretched over the top.
Stretching the baked layer is one bilinear blit, where rebuilding it would mean a
bicubic resample of the artwork per frame -- exactly what the brand cache exists to
avoid. The layer is drawn with `AntiAliasGridFit` rather than ClearType, because
subpixel hinting against transparency leaves coloured fringes once composited.

Two details matter there. `uiScale` still holds its pre-resize value while a preview
is up, so the header's on-screen height is the captured height scaled by how far the
window has been dragged; `LiveHeaderHeight()` is the single source of that number, so
the invalidate rectangle and the paint cannot drift apart and leave a stale band when
the window grows. And the whole live-header block is wrapped in a catch that drops the
layer and reverts to the plain snapshot: an exception escaping a paint handler
mid-drag would surface as a JIT dialog.

If it needs to be cheaper still, raise `Downscale`, drop `Octaves` from 3 to 2, or
lengthen the timer interval -- the plume is slow enough to survive a lower frame rate.

### Where the frame time goes

Attribute before optimising. `LightField` carries per-stage timers (`SmokeMs`,
`BloomMs`, `MapMs`, `BlitMs`, `MotesMs`) for exactly this. At full design scale:

| Stage | Before | After | |
| --- | --- | --- | --- |
| Upscale blit | 10.9 ms | 9.9 ms | only the rows containing smoke are scaled |
| Motes | 8.9 ms | 3.9 ms | pre-tinted sprites instead of a per-draw ColorMatrix |
| Smoke noise | 9.0 ms | 6.1 ms | `Downscale` 10 to 12 |
| Bloom + ramp | 0.2 ms | 0.2 ms | already negligible |
| **Total** | **29.0 ms** | **20.2 ms** | |

Two results worth keeping in mind:

- **A per-draw `ColorMatrix` is expensive.** Tinting each mote through
  `ImageAttributes` put GDI+ on a slow blit path. The colour never varies -- only the
  brightness -- so 24 pre-tinted sprites at fixed alpha levels replace it, with no
  visible banding on something this small and soft. That alone was more than half the
  saving.
- **`InterpolationMode.Bilinear` is not faster than `HighQualityBilinear` here, it is
  six times slower** -- 10.9 ms to 66.5 ms. The reasoning that the "high quality"
  prefilter only matters when minifying is sound and completely wrong in practice:
  GDI+ has an optimised implementation for the HighQuality modes at this
  magnification. The comment in `Render` says so; do not "optimise" it back.

### Frame rate

The timer asks for 60 ms, which Windows' 15.6 ms granularity rounds to 62.4 ms, or
16 fps. It was 40 ms, rounded to 46.8 ms and 21.4 fps. Measured in the running
application, that took the effect from about 40% of one core to 28%.

`AnimationIntervalMs` and the mote fall speed must change together. Motes are the
fastest thing on screen and the only part near the threshold where motion stops
reading as travel: at a 364 px header the fastest covers ~2.6 px per frame while its
bright core is 1.5 to 5.2 px across, so a small fast mote is already moving close to
its own width per frame. Dropping the frame rate without slowing them would have
taken that to 3.5 px, past the point where a mote reads as reappearing somewhere else
rather than moving. The fall speed was scaled by 0.75 alongside the 0.748 change in
frame interval, so distance per frame is unchanged. Ageing is tied to `Fall`, so
slower motes also age slower and still reach the same depth before dying.

The smoke itself is nowhere near that threshold -- 0.94 px per frame before, 1.25
after -- so it was left alone.

Verified after the change: 15.9 fps measured against 16.0 predicted, from the
duplicate-frame rate in a 29.75 fps capture.

If it ever needs to be cheaper still, the remaining lever is throttling further while
the window is unfocused.

### Measured settings

Averaged over 59 frames of steady state on a rendered 1980 x 420 header, with the
brand composited exactly as the form composites it. `Lit` is the share of the header
above the flat window colour, `blown` the share saturated past luminance 200:

| Candidate | Lit | Blown | Mean lit pixel | Wordmark contrast |
| --- | --- | --- | --- | --- |
| Point source behind the crest | 65.1% | -- | rgb 45, 71, 105 | **17.9** |
| Off-screen source, blue ramp | 33.7% | 0.0% | rgb 17, 34, 61 | 115.1 |
| Blue ramp turned up hard | 87.5% | 8.4% | rgb 70, 97, 126 | 103.0 |
| Grey ramp, long reach | 91.9% | 0.0% | rgb 33, 39, 48 | 106.1 |
| Wispy, extinction curve | 97.1% | 0.0% | rgb 33, 39, 48 | 106.6 |
| White plume with a front | 73.2% | 0.0% | rgb 67, 72, 80 | 108.3 |
| Shipping: plus per-column variation | 75.8% | **0.0%** | rgb 68, 73, 81 | **101.8** |

Three separate failures are recorded there, and each was caught by a number rather
than by eye:

- the point source scored 17.9 and would have swallowed the wordmark;
- turning the blue ramp up to cover the bar saturated 8.4% of the header into a flat
  pale band, because the blue ramp tops out near white. The grey ramp tops out at
  rgb 185, 192, 205, so the same coverage now blows out nothing at all;
- reaching further down the bar is what costs legibility, not density as such.
  Coverage nearly tripled, from 33.7% to 91.9%, for only nine points of contrast.

### Matching the reference clip

The look is modelled on a stock white-smoke plate: near-opaque white entering at the
top edge, a ragged billowing front roughly a third of the way down, and fine wisps
trailing below it. Three things were needed, none of which a smooth vertical falloff
can produce:

- **A front, not a fade.** The vertical profile is solid above a boundary and decays
  exponentially below it, and the boundary height is itself noise. That is what makes
  the edge billow rather than sit on a line. It is continuous at the boundary --
  `exp(0)` is 1 -- so there is no seam.
- **The vertical shape multiplies optical thickness, not the final value.** Scaling
  the result only dims the plume; scaling thickness lets the top genuinely saturate
  toward opaque while the wisps below stay thin.
- **Anisotropic noise.** Features are stretched along v so tendrils hang downward.
  This is easy to overdo: at `NoiseAspectY` 0.45 the plume stops reading as smoke and
  becomes a comb of vertical streaks. 0.80 keeps the downward bias without it.

### Motes

The falling motes are blue rather than taking the smoke's white, so they read as
embers of light in the plume rather than as brighter specks of the same smoke. Each
is one sprite carrying two gaussian lobes -- a tight core inside a wide halo -- so
the glow costs one draw per mote rather than a separate halo pass.

`MoteGlowScale` and the lobe widths in `BuildMote` have to be kept in step, because
between them they decide both the glow's size and its cost, and the cost is the
square of the scale. The first version drew at 4.5x the core radius with lobes only
0.30 wide, so roughly 70% of every sprite was transparent: the mote pass cost 17.4 ms
of a 35.7 ms frame. Widening the lobes and shrinking the sprite to 2.4x is visually
identical and costs 7.6 ms.

Motes are drawn at full resolution, after the smoke buffer is upscaled. Accumulated
into the buffer instead they were clamped to a single buffer pixel, so they could not
be made smaller and were upscaled into a soft 16px disc.

### Non-uniformity

A front alone still descends to roughly one depth and falls straight down. Three
further fields, all slow noise in u, break that up: each column gets its own trail
falloff (`ReachVariation`), its own sideways lean that grows with depth
(`LateralDrift`, so a tendril leans further the further it falls and neighbouring
columns lean opposite ways), and its own density (`PatchDepth`).

`reachSD` measures this: the standard deviation, across columns, of the lowest row
the smoke actually reaches. The front noise alone gives 31.6 px; the three added
fields take it to 54.1 px, about 13% of the header height.

All three depend on u and time but not on v, so they are evaluated once per column
rather than once per pixel -- 198 noise samples a frame instead of 198 x 42. Hoisting
the front calculation the same way paid for all three: frame time is unchanged at
22.1 ms. Note that pushing the variation harder can *lower* `reachSD`: dropping
`ReachScale` to 2.2 makes the variation broader and lower-frequency, so fewer
independent regions fit across the width and the per-column spread falls.

### Slabs versus wisps

Two things made the plume read as drifting solid masses rather than smoke, and
neither was obvious from looking at it:

**Density was clamped.** `density` was computed linearly and then clamped to 1, so
everything past the saturation point rendered as one flat opaque value and large
regions had no internal variation at all. It now uses Beer-Lambert extinction,
`1 - exp(-thickness * DensityGain)`, which approaches full opacity without reaching
it. That is both how light actually attenuates through a medium and what keeps the
smoke see-through.

**`NoiseScale` was far too low, and resolution was the wrong suspect.** At 2.4 the
finest octave had features roughly 100 px across -- far coarser than the buffer could
already resolve -- so the plume had no fine structure to show. The instinct is to
raise the buffer resolution, and that is measurably wrong here:

| Change | Frame time | Detail | Slab |
| --- | --- | --- | --- |
| `Downscale` 8 -> 3 | 22.9 -> 71.3 ms | 1.49 -> 1.58 | 92.4% -> 90.5% |
| `NoiseScale` 2.4 -> 12 | 22.9 -> 25.3 ms | 1.49 -> 2.58 | 92.4% -> 80.1% |
| Adding the ragged front | no change | 4.34 -> 8.36 | 63.1% -> 36.5% |

Tripling the cost bought 6% more detail; the noise scale bought 73% more for 2 ms.
Detail is limited by feature size, not by buffer resolution. Because of that,
`Downscale` was then *raised* from 8 to 10 to pay for the finer noise, which holds
frame time where it was and still keeps most of the gain.

`detail` is the mean local luminance slope over lit pixels and `slab` the share of
lit pixels flatter than a threshold, both sampled at an 8 px stride. The stride
matters: measured between adjacent pixels, both figures describe the bilinear
upscale rather than the smoke, and report everything as flat regardless of settings.
Note also that `slab` conflates dim with flat -- dropping `MaxAlpha` shrinks every
luminance slope and makes the metric look worse while the structure is unchanged, so
compare it only between renders of similar brightness.

### Two measurement traps

**The contrast metric is colour-dependent and was rebuilt.** It originally separated
letters from ground by blue-minus-red, which works only while the plume is blue. Grey
smoke is the same hue as the silver letters, so that test silently stops measuring
anything. The mask is now built once from a composite rendered with no plume behind
it, which is independent of whatever colour the smoke happens to be.

**Screen capture of this header is misleading.** GDI capture preserves the BGRA alpha
channel, and drawing the 32-bit ARGB buffer zeroes destination alpha across the whole
header rect, so a recording shows the header as transparent -- white, in most viewers.
Encode captures through `format=rgb24` to discard alpha. On screen it is always
correct; the desktop compositor ignores per-pixel alpha for ordinary windows.

## Startup

The window must be complete the moment it is displayed. Three separate things broke
that, and all three are only visible in a screen recording of the launch:

- **The initial fit ran on `Shown`.** The window appeared at its full design size,
  1980 x 900, and then snapped to the fitted size in front of the user. It now runs in
  `OnLoad`, before the window is displayed.
- **The render thread started on `HandleCreated`.** At that point WinForms has not
  painted the client area, so the thread blitted a finished header over an unpainted
  body and the window briefly showed the desktop through its own card. It now starts
  in `OnShown`, and `OnLoad` composes one frame up front through `ComposeFrame` so the
  very first paint already carries the plume rather than popping in a frame later.
- **Transparent child controls flashed white.** `Color.Transparent` in WinForms means
  "inherit the parent's background", and during the window-open fade there is no
  painted parent to inherit, so `PillButton`, `StateLabel`, the options host and the
  footer links rendered as white rectangles. They now carry the opaque colour that is
  actually behind them -- `UiTheme.Card` for anything on the card, `UiTheme.Window` for
  the footer.

Do not extend that last change to `CardPanel` or `StepRow`. Both deliberately stay
transparent: the card is a rounded rectangle, and a step row spans the full card width,
so an opaque background on either would square off the card's corners.

Measured across the frames of the open animation, the near-white area inside the window
fell from a peak of 20.6% to 0.17%, and the residue is the silver wordmark.

**The update check starts in `OnShown` too**, on a background thread, so neither
the first paint nor the render thread waits on the network. A newer release is
offered through `BeginInvoke` in `UpdateDialog`, a themed modal. It takes the main
window's `uiScale` and dark title bar, and it never opens while `operationRunning`
is set. `UpdateCheck` holds the request, the tag parser and the comparison;
`SECURITY.md` says what the request sends. Added 2026-09-25. The dialog has been
rendered off screen by `Test-UpdateCheck.ps1 -RenderTo`, not seen in the real
window.

## Window sizing and smooth proportional resize

All controls are authored once in design-space coordinates. Their rectangles
and font templates are captured after construction, then scaled uniformly.
Width and height cannot be stretched independently.

The approved 1080p target is a centred 1300 × 700 outer window on a
1920 × 1040 usable desktop. Startup sizing uses:

```text
monitor_scale = min(work_area_width / 1920,
                    work_area_height / 1040)

startup_scale = reference_ui_scale × monitor_scale
startup_scale = min(startup_scale, scale_that_fits_94_percent_of_work_area)
startup_scale = max(startup_scale, 0.35)
```

The height is normally the limiting dimension on ultrawide monitors. This
prevents the patcher from becoming enormous simply because the desktop is wide.
The minimum uniform scale is 0.35.

During a live resize, WinForms would otherwise re-layout and repaint every
label, icon, panel, and native control for every mouse movement. The patcher
instead:

1. finishes pending state and paint work;
2. captures the current client area into a premultiplied 32-bit bitmap;
3. hides child controls and scales that bitmap with the window;
4. performs one real layout and font update when the resize ends;
5. restores controls, refreshes state, repaints, and disposes the bitmap.

Old scaled fonts are retained for 750 ms before disposal. This prevents a
queued `LinkLabel` paint from using a font object that was replaced during the
resize burst—the cause of the earlier `System.ArgumentException: Invalid
parameter` JIT dialog.

## Executable, DPI, INI, and Override transaction

**Since 2026-09-29** `PatchOperations.ApplyInPlace` calls
`KpmEditionOperations.Install` (`src/patcher/KpmEdition.cs`), which never writes
the gold image to `swkotor.exe`. In its order: every check that can refuse --
the executable (CD 1.03 or Steam's), `swkotor.ini`, an earlier KMRP's backups,
and, with KMRP's own runtime, the game's `binkw32.dll` -- and the choice of
install: for KOTOR Patch Manager when KPM's runtime is already in the folder
(until 2026-09-30 also when an Advanced Settings option was on), otherwise with
KMRP's own; then restoring an
earlier KMRP, or this installer's own earlier install; building `kmrp-kpm.dat`
from the carried originals; steps 5 to 8 below, unchanged; the data file, SDL
and the controller settings; with KMRP's own runtime, KOTOR Patch Manager's
runtime, `patch_config.toml`, the modules and the `binkw32.dll` proxy, the 4 GB
flag on CD 1.03 and K1DC when it is on; and `KMRP_KPM.manifest`. A failure at any step rolls every earlier one
back. [kpm-edition.md](kpm-edition.md), section 1a, has the details. The list
below is the standalone path as it was until then, kept as its record; its
restore still runs to upgrade an install it made.

**Since 2026-10-04** the paragraph above no longer holds in three places: no
`kmrp-kpm.dat` is built or written, no SDL or controller settings file is written
beside the game, and step 8 below (the Override archives) is gone. What is written
is KOTOR Patch Manager's runtime, `patch_config.toml`, `patches\kmrp.dll`,
`configs\kmrp.ini`, and since 2026-10-05, while Controller Support is on,
`patches\kmrp-controller.dll` and `configs\kmrp-controller.ini`
([kpm-edition.md](kpm-edition.md), its first two sections). The INI step writes
the display's current size; since 2026-10-07 nothing else is written for the
resolution.

The in-place patch path is deliberately conservative. In the order
`PatchOperations.ApplyInPlace` ran it until 2026-09-29:

1. verify the source executable hash and length;
2. create or verify the executable backup;
3. apply the clean-to-gold delta and the resolution patch to a temporary file,
   clearing the map-note flag when that correction is turned off;
4. verify the result before atomically replacing `swkotor.exe`;
5. add `HIGHDPIAWARE` to the exact executable's per-user Windows compatibility
   value and record the prior value in `KMRP_DPI.manifest`;
6. on NVIDIA, set the game's present method where the driver would show it
   half-drawn frames, recorded in `KMRP_NVIDIA.manifest`
   ([`nvidia-present-method.md`](nvidia-present-method.md));
7. update `swkotor.ini` under `[Graphics Options]`, removing duplicate Width
   and Height keys while preserving unrelated sections, comments, encoding,
   and line endings;
8. install the common and selected-resolution Override archives, backing up
   conflicting files and recording introduced ones;
9. install K1 Modern Driver Compatibility, or only its ASI loader when just the
   controller needs it, recorded in `KMRP_DriverCompat.manifest`;
10. install the controller component when it is on, recorded in
    `KMRP_Controller.manifest`;
11. write the patch manifest and installed resolution.

*Corrected 2026-09-24:* this list stopped at the Override archives; the NVIDIA,
driver and controller steps were missing.

Every file replacement goes through `FileGuard.Replace`, never `File.Replace`
directly. `File.Replace` has to **delete** the destination, which fails with "the file
to be replaced cannot be removed" while any process holds a handle opened without
FILE_SHARE_DELETE -- antivirus scanning a file moments after it was written is the
usual cause, and a restore rewrites 662 Override files plus the INI, which leaves a
scanner busy in exactly that folder. It was reproduced as a patch failing immediately
after a restore.

`FileGuard` clears the read-only attribute, retries six times with a delay doubling
from 60 ms, and then falls back to overwriting the destination in place: `Replace`
needs to delete the file, whereas copying only needs to open it for writing, which a
reader holding FILE_SHARE_WRITE still permits. That fallback gives up atomicity, which
is safe here only because every caller verifies the result by hash afterwards, so a
partial write is caught and rolled back rather than mistaken for success. If even that
fails the exception carries a message naming the file and what to close, instead of the
localised OS text.

Verified against the shipping class with a lock held deliberately: no lock replaces in
4 ms; a reader without share-delete -- the reported failure -- retries and then succeeds
by overwrite; an exclusive lock is refused with the actionable message.

Failure rolls back changes made by the current operation. Restore verifies the
backup records, restores the EXE and INI, restores replaced Override files, and
removes files introduced by KMRP. It restores the exact prior DPI compatibility
value only while the live value still equals KMRP's installed value; a later
user or Windows change is left untouched. The complete registry and sidecar
contract is in [`windows-dpi-scaling.md`](windows-dpi-scaling.md).

## Build workflow

Requirements currently encoded by the build script:

- Python 3 with `requirements.txt`: found on PATH, or selected through `-Python`,
  `KMRP_PYTHON` or `KmrpPython` in ignored `build.local.ps1`;
- C# compiler: `.NET Framework` `csc.exe` under
  `C:\Windows\Microsoft.NET\Framework\v4.0.30319`;
- Pillow, and the rest of `requirements.txt`. The resource pipeline needs it:
  `prepare_universal_resources.py` compresses the menu backgrounds and the
  bundled icons with it, and the controller prompt, layout and backdrop tools
  draw their textures with it. Without Pillow the backgrounds ship uncompressed
  and the prompt art falls back to drawn discs. *Corrected 2026-09-24:* this
  said the pipeline intentionally did not need Pillow, true before the prompt
  art and texture compression.

If the source icons changed, first run `prepare_app_icons.py` with a Python
environment that has Pillow. Then perform a full release build:

```powershell
python .\tools\prepare_app_icons.py  # requires Pillow; skip if icons are unchanged
.\build_kmrp.ps1
```

Use `-ReuseResources` after a successful full resource build when interface
resources have not changed. It skips resource regeneration, but still assembles
the source engine, pools the archives, builds the blend table, compiles KOTOR
Patch Manager's runtime, KMRP's module and the controller patch's module, and
packages the two KPM patches before compiling the installer. The controller
patch's step needs the game's layout files in `build-inputs\vanilla-gui`
([build-inputs](../build-inputs/README.md)):

```powershell
.\build_kmrp.ps1 -ReuseResources
```

Between the resources and the compile, `build_kmrp.ps1` packs the 66 resolution
archives into one pool, `build\kmrp\resolution-layouts.zip`
(`tools/pack_resolution_layouts.py`), which the installer embedded in their place
until 2026-10-04 and which now feeds the module's resource bank and the macOS
build. The step
runs with `-ReuseResources` as well. It stops the build unless every resolution
rebuilt from the pool matches its archive, and took 41 seconds on 2026-09-25.

`build_kmrp.ps1` uses the
`assets/branding/favicon.ico`. `src/patcher/favicon.ico` is retained as a
synchronised compatibility copy, not as an independent source of truth.
After compilation the universal builder sends `SHCNE_UPDATEITEM` for the output
path so Explorer is prompted to refresh an icon cached for `dist/KMRP - KOTOR Modern Restoration Patch.exe`.

The final build prints the output path and SHA-256. A build's KMRP hash is not a
stable project constant because compiler metadata can change; record the hash
next to a release artifact rather than in source-level architecture docs.

## Command-line modes

The shipped name contains spaces, so quote it on the command line.

```text
"KMRP - KOTOR Modern Restoration Patch.exe" --apply clean.exe output.exe WIDTHxHEIGHT
"KMRP - KOTOR Modern Restoration Patch.exe" --in-place swkotor.exe WIDTHxHEIGHT
"KMRP - KOTOR Modern Restoration Patch.exe" --restore swkotor.exe
```

`--apply` creates an offline reference from a supported editable CD/GOG input;
it does not install KMRP. `--in-place` performs the full runtime, DPI, NVIDIA, INI
and optional-component transaction (and wrote the Override files until
2026-10-04); its resolution is the size `swkotor.ini` starts the game at. It preserves Steam's EXE and sets
only the LAA header bit on the supported editable CD/GOG file. `--restore`
restores KMRP-owned changes and preserves subsequently modified or foreign
files. None of
them checks for updates; that belongs to the window. Omitting
the resolution in the legacy `--apply` and `--in-place` forms selects
3440 × 1440.

## Release verification checklist

1. Run `prepare_app_icons.py`; confirm all seven supplied roles are reported.
2. Run a full `build_kmrp.ps1` without `-ReuseResources`.
3. Confirm the embedded source engine template, the 66-entry resolution table
   and the two KPM packages, `KMRP.kpatch` and `KOTOR 1 Native Controller Mod +
   Xbox HUD.kpatch` (four until 2026-10-04). Run `Test-WindowsEngineSource.py`,
   `Test-KpatchSource.py` and `Test-ControllerKpatch.py`; verify the guards, relocation omission checks and
   corrupted-package rejection. Confirm the obsolete gold/originals resources
   are absent by enumerating the assembly's manifest resources.
4. Extract the executable's 32px and 256px icon frames and confirm both show the
   current `assets/branding/favicon.ico` artwork.
5. Test missing, unsupported, clean, patched, restoring, error, and success UI
   states.
6. Confirm the Verified badge size and that the success message survives window
   activation.
7. Resize from the minimum size to a large size and confirm the aspect ratio,
   snapshot preview, final sharp text, complete footer, and absence of flicker
   or JIT errors.
8. Patch a clean install; verify the EXE (unchanged but for the 4 GB flag, and
   unchanged on Steam), the INI, `patch_config.toml`, the modules under
   `patches\` and that nothing was written to `Override`; launch the game, check
   that Options, Graphics lists the display's resolutions, then restore and
   compare all backups.
9. Run `testing/regression/Test-DpiCompatibility.ps1`; verify its exact registry
   paths are absent or restored after completion.
10. Run `python testing/regression/Test-GeneratedGuiGeometry.py`; verify all 66
    packaged archives pass: upstream list prototypes, the Feedback gutter, Script
    Selection centring, confirmation containment, the active HUD and the R3 cue.
11. Run `testing/regression/Test-LargeAddressAware.ps1`; verify canonical and
    pre-LAA inputs converge, unrelated header changes fail, and both exact
    source states survive patch/restore.
12. With optional historical fixtures available, run `tools/build_binary_inventory.py`
    against the clean executable and historical gold, with `--installed` and
    the installer's `--apply` output at all 66 resolutions. This is additional
    binary comparison, not a build prerequisite; record unavailable fixtures
    explicitly. The source regression independently checks all 68 documented
    historical runs and the 81 current guarded runs without them.
13. Run the rest of the regression set: `Test-InstallerPatch.ps1`,
    `Test-KpatchSource.py`, `Test-ControllerKpatch.py`,
    `Test-NativeAssetsBank.py`, `Test-ReinstallOverOlderBuild.ps1`,
    `Test-UpdateCheck.ps1 -Live`, `Test-MovieResolution.ps1`,
    `Test-NvidiaPresentMethod.ps1`, `Test-ControllerPromptAssets.py`,
    `Test-FontAtlasScale.py` and `Test-ProtonResourceCompatibility.py`, then
    `tools/check_controller_drift.py`, `tools/check_kpm_overlaps.py` on the two
    packages, `tools/check_hook_stolen_bytes.py` and
    `.github/scripts/check_links.py`. (`tools/check_patcher_hook_table.py`, named
    here until 2026-10-08, was removed on 2026-10-04.)
14. Record the final `dist/KMRP - KOTOR Modern Restoration Patch.exe` SHA-256 in the release directory.
15. Confirm Properties → Details on the built installer shows the release's
    version (1.5.0 for KMRP 1.5), the same string as `PatchVersion` in
    `KmrpPatcher.cs`. `build_kmrp.ps1` refuses to compile while
    `AssemblyInfo.cs` disagrees with it. (Added 2026-09-24, after the
    `2.11.0-movieaspect` build was found reporting `2.10.0-mapnotes`.)
