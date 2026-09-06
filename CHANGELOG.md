# Changelog

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


All notable changes to KMRP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **On the entries below.** This project was not git-tagged during its first
> week, so the versions here are reconstructed from the `PatchVersion` constant
> in `src/patcher/KmrpPatcher.cs` and the commit that introduced each
> one. **Dates are the date that constant changed, not a release date.** Where a
> version's gold snapshot is recorded in the build script it is named; for
> 2.0.0–2.5.0 the build script's default still pointed at an older snapshot than
> the documentation describes, so no gold snapshot is claimed for those. Going
> forward, tag releases so this stops being reconstruction. **2.10.0 is where
> that starts:** it is the first tagged version, so every entry above it is
> reconstructed and every entry from it on is not.

## Everything the patch changes in the executable

The version entries below are a running record of *changes*, so they describe
each fix at the moment it landed and never in one place. This section is the
other view: **the complete set of differences between an unmodified
`swkotor.exe` and a patched one, in plain language**, so it can be read without
knowing the project's history.

It is kept honest by
[`reverse-engineering/binary-inventory.md`](reverse-engineering/binary-inventory.md),
which lists all 702 differing byte positions and refuses to pass if any of them has no
technical write-up. If something appears there and not here, this section is out
of date.

**The size of it.** KMRP changes 702 byte positions inside the original
4,042,752-byte executable — 0.017% — and appends ten new 4KB sections holding the code and data
the original has no room for. Nothing else in the file moves.

| What you see in game | What changes in the executable |
| --- | --- |
| **Text is legible at modern resolutions** instead of tiny. | Text size is carried on the font atlases' own metrics rather than scaled at runtime, because scaling it at runtime changed the size one frame *after* the engine had already measured and centred the text, which visibly shifted the first screen of each session. The executable keeps a scale constant for list rows, which are built after nothing has measured them and so have no such ordering problem. |
| **List rows grow with the text**, so save/load and dialogue entries stop overlapping. | A hook rewrites each row's height as the row is constructed. Rows never shrink below vanilla, so short screens are untouched. |
| **Inventory, Abilities and Store rows and icons are sized to match.** | Three separate hardcoded 56s decide the icon box, the text offset and the row height, none of them reachable from any `.gui` file. That is why editing the interface files alone never moved them. |
| **Item stack counts are visible again.** | Two guards blanked any string of one or two characters that did not fit its box, and the enlarged font made the fixed 21px stack label too narrow to pass them, so two-digit counts silently vanished. Both guards are removed, together with a fix to the line-breaking loop that they were the only thing protecting against. |
| **The game no longer crashes** on items with long descriptions. | The line-breaker's only guard compared against the start of the whole string rather than the start of the current line, so a line that could not break looped until memory ran out. |
| **Dialogue gets proper letterboxing** at any aspect ratio. | The bars are derived from screen height rather than assumed. |
| **The area map fills its frame**, at every resolution. | The map picture is drawn on its own canvas, separate from both the window and the marker overlay, and sized so its content fits the frame; the `LBL_Map` control crops whatever overhangs, as it always did. |
| **Fog of war covers the whole map** instead of stopping 242px short on the right. | The fog grid was stepped by a fixed constant while the map was drawn at a different width, so the last strip was never covered by any tile. Two instructions now read the live rectangle instead of that constant. |
| **Clicking a map marker hits the marker.** | The hit test recentred the map's canvas inside the window, but the control that positions it is placed by the overlay, and the canvas overhangs it. Clicks landed 141px to the right; eleven bytes were replaced with eleven, and it was measured live before and after. |
| **Map markers keep their size as the map grows**, and stay on their subject. | Note, party and player-arrow rectangles were built from the original hardcoded sizes while everything around them scaled. |
| **250 map notes point at the right place.** | Optional. A table keyed on each note's shipped world position substitutes a corrected one. It needs no hook of its own, because the code KMRP already redirects receives that position as its own argument. The corrections are Derslok's measurements, used with permission. |
| **The HUD minimap is unaffected by the map work.** | The full map and the HUD minimap share one constructor. The minimap's call to it is wrapped, and the wrapper puts that one instance back to retail values — so the map screen can be resized without dragging the minimap with it. |
| **The process can use more than 2 GB of virtual address space on 64-bit Windows.** | The PE header's standard `IMAGE_FILE_LARGE_ADDRESS_AWARE` bit is enabled. No allocator or code path is changed. |
| **Full-screen movies stay in the selected display mode.** | KOTOR has two independent 640x480 mode pairs around Bink playback even though the renderer itself scales from the live client rectangle. Both pairs are rewritten per resolution, avoiding the forced legacy-mode transition. |
| **Tutorial and confirmation popups fit their text** instead of clipping it. | The shared popup sizes itself from constants that never accounted for larger text. |
| **Interface elements sit where they should** at your resolution, not at 640x480. | Two shared helpers recentre almost every non-HUD screen using the resolution the interface was designed for. The patcher writes your actual resolution into them at install time, which is also why the reference build in this repository has one author's monitor baked in and the shipped executable never does. |
| **The correct interface artwork is chosen for your screen.** | A chain of width comparisons picks a resource set; the first is redirected to your width and the later ones are disabled so they cannot win instead. |
| **Nothing else.** | The remaining changes are the PE header's own bookkeeping — the section count, the image size, and the ten new section headers. One casualty is worth naming: a leftover `Hellspawn Reborn` signature string sitting in the header's unused padding is overwritten by the fifth section header. Nothing reads it. |

**What is *not* changed in the executable**, though the patch installs it:
interface layout files, font atlases and icon artwork all ship as ordinary
`Override` files, and the bundled *K1 Modern Driver Compatibility* patches its
own process in memory at startup without writing to `swkotor.exe` at all.

## [Unreleased]

### Added
- **Linux/Proton diagnostics and a reproducible Steam Deck procedure.** A new
  case-sensitive package audit checks all 48 resolution archives, 3,889 GUI
  resources, referenced font pairs, archive collisions/paths, and the active
  target-name font chain. A read-only report collector records hashes, manifests,
  resolution, key HUD/font resources, and case collisions without copying game
  content. The Protontricks install/restore workflow and remaining stable,
  Experimental, controller, and hardware matrix are documented without claiming
  unperformed gameplay tests. See `docs/linux-proton-steam-deck.md`.
- **Optional Xbox controller support is now integrated under Advanced Settings.**
  KMRP embeds Saul0097's KPM Xbox Controls K1 1.2 module and a statically linked
  KOTOR Patch Manager runtime, generates a hash-bound seven-detour configuration,
  and uses ownership manifests for safe install and restore. The option is off by
  default and enables the bundled ASI loader when selected. Automated regression
  covers exact hook bytes, TOML structure, foreign-config refusal, rollback, and
  restore; a named-copy Windows launch loaded both modules and showed `E9`
  detours at the original six sites without changing the executable on disk. Physical
  XInput gameplay and Proton/Steam Deck remain untested. Dynamic, original KMRP
  A/B/X badges now appear on ten verified Character, Container, Save/Load, and
  Upgrade action buttons while XInput is connected, and clear on disconnect.
  Normal and highlighted button fills are both covered so focused controller
  navigation does not hide the badge. All 480 resolution-specific
  textures and control mappings are regression-checked. The PC data's retained
  Xbox strings and seven legacy textures remain unused because their console
  mapping conflicts with this module. See `docs/controller-support.md`.

### Changed
- **Mod-build compatibility now has an explicit supported-input and install-order
  contract.** The exact LAA-only source variant is accepted, K1CP/K1R content
  installs before KMRP, separate UniWS/High Resolution Menus/4 GB steps are
  replaced by KMRP, and KOTORganizer's manual-patch workflow is documented.
  KotOR Patch Manager and another public executable-fix set were audited rather
  than treated as automatically compatible; their remaining hash/restore limits
  are stated in `docs/mod-build-compatibility.md`.

### Fixed
- **Controller button badges now sit next to the button's words, and use the
  words your game actually shows.** The A/B/X badge used to sit at a fixed
  distance from the button's left edge, while the game centres a button's label —
  so on a wide button such as the 978-pixel "Upgrade Items" the badge floated most
  of a screen away from the text it belonged to. It is now placed against the
  measured width of the label, about thirteen pixels to its left, the way the
  original Xbox release drew it.

  Which words those are is no longer guessed. All ten buttons store a `dialog.tlk`
  string reference rather than literal text, and the first version of this
  measured a hand-written list of English labels that was wrong for five of the
  ten: the Container "Cancel" button and both "Back" buttons actually read
  "Close", the save/load button reads "Save" or "Load" rather than always "Load",
  and "Switch To Give Items" is two shorter strings that add up to something
  else. The patcher now reads those references out of your own `dialog.tlk` at
  install time and re-places each badge against the real label, so localised
  installs are measured correctly too. Where a button's wording changes while the
  screen is open — save versus load — it is measured against the wider of the two
  so the text can never overlap the badge. If `dialog.tlk` cannot be read, the
  English placement is used and nothing fails.
- **A controller-support conflict no longer aborts the whole patch.** Every
  reason the optional component could not install -- a `patch_config.toml` owned
  by another KPM mod, a missing ASI loader, or a build without the controller
  resources -- threw `InvalidDataException` out of `ApplyInPlace`. A user who
  happened to have any other KPM mod installed therefore got no fonts, no GUI
  archives and no executable patch either, with a .NET stack trace as the only
  explanation; `dist/KMRP.startup-error.log` recorded exactly that. The ownership
  guard itself was right and is unchanged -- KMRP still never overwrites a file it
  does not own. It now reports and skips, which is how
  `DriverCompatOperations.Install` has always handled the identical case
  ("Left the existing dinput8.dll alone"). Optional components decline; they do
  not take the install down with them.
- **Full-screen movies are no longer cropped on a screen wider than the movie.**
  KOTOR derives its Bink scale from the client *width* alone -- `fdiv` of client
  width by movie width at `0x004057CB`, with height never read -- so at 3440x1440
  a 640x480 logo scaled by 5.375 to 3440x2580 and lost 1140 rows off the top and
  bottom. Gold v24 redirects `0x004057AC` into a `.kmv` stub that takes the
  smaller of the width and height ratios, so every movie is letterboxed or
  pillarboxed rather than cropped, and vanilla and upscaled replacements share
  one policy. Verified by simulation across five client/movie pairs and by
  patching a clean executable end to end; **not yet play-tested**.

  Two failures are recorded rather than quietly fixed. The tool that does this
  existed since 2026-09-05 but was wired into nothing and had an empty expected
  output hash, so it had never been run to completion. And its stub jumped to
  `0x0087703C`, one byte inside the shared `mov [esp+0x14], edi`, which would
  have resumed on `7C 24` -- a `jl` into nothing -- on every movie. The
  displacement is `0x0A`, not `0x0B`; it was caught by disassembling the built
  image rather than the intended assembly, and the builder now checks that every
  internal branch lands on an instruction boundary.
- **Holding a D-pad direction now repeats in menus instead of stepping once.**
  The four directions went through the module's held-key demand set, and that set
  produces exactly one edge per state change, so a held direction moved the
  selection a single row and then sat there. Only the right stick repeated, and
  the upstream source says why: DirectInput reports key transitions only. A
  keyboard does not behave that way -- holding an arrow makes the OS auto-repeat
  and the engine sees a stream of keydowns -- so holding a direction was strictly
  *less* faithful than the keyboard it emulates. The directions are now driven as
  repeating taps through `SendInput`, the same mechanism the right-stick scroll
  already used: the press acts immediately, the next waits 400 ms, and the rest
  follow every 120 ms. Pressing a second direction hands over and restarts the
  delay, and holding two at once does nothing rather than walking diagonally at
  double rate. Reported from play-testing; the repeat rate itself has not been
  play-tested yet.
- **The Character Scripts and Feedback screens are no longer rebuilt from stale
  prototype geometry.** `fix_feedback_list_prototypes.py` rewrote each listbox's
  `PROTOITEM` extent to its parent's content area, on the assumption that those
  coordinates share the parent's space. They do not: upstream ships prototypes
  sitting above and to the left of their own parent (`scriptselect`
  `LST_AIState` parent `TOP=103`, prototype `TOP=84`), which no absolute reading
  explains, and the play-tested 3440x1440 gold files leave every one of them at
  its vanilla value while scaling the parent listbox fully. The rewrite shipped
  and the Character Scripts screen came back broken from play-testing. The pass
  is disabled, both screens now match gold field for field, and
  `Test-GeneratedGuiGeometry.py` asserts these extents equal what upstream ships
  -- the inverse of what it asserted before. The 3840x2160 report that prompted
  the change is unexplained again and needs a different diagnosis.
- **Controller buttons can now skip Bink movies.** KOTOR suspends its ordinary
  input loop during playback, so controller-generated keyboard events were
  never produced. A verified seventh runtime detour polls XInput once per movie
  frame and edge-triggers cancel for A, B, LB, or Start.
- **Controller prompt badges remain visible on focused buttons.** The earlier
  implementation changed only the normal button border, but controller
  navigation selects the separate highlight border immediately. Both empty
  fills now receive the badge while an XInput pad is connected.
- **Controller support no longer hides and parks the Windows mouse cursor on
  startup.** Keyboard/mouse remains immediately available; F9 still toggles the
  optional parked controller-only cursor state.
- **Opening Save/Load with controller prompts active no longer dereferences the
  wrong GUI object.** An unreleased prompt build treated packaged GUI list order
  as the live panel control-array order and crashed in `SetFillImage` at
  `swkotor.exe+0x14C3E`. Runtime prompt assignment now uses the ten verified
  embedded button offsets from the K1 1.0.3 class-layout database. The report,
  matching Windows crash dump, and rejected lookup are recorded in
  `docs/controller-support.md`.
- **Full-screen movies no longer request a separate 640×480 display mode.** Gold
  v23 changes the comparison operands at FILE `0x3D6C` / `0x3D78` and the
  temporary-mode operands at `0x1F5B3B` / `0x1F5B43` to 3440×1440;
  `ResolutionPatch` strictly replaces all four with the selected resolution.
  The Bink renderer itself was confirmed to derive scale and centring from the
  live client rectangle and BIK dimensions, so movie files are not stretched or
  rewritten. A published helper's ambiguous second signature was rejected after
  it matched unrelated instructions. Four output resolutions pass structural
  regression; actual movie playback and minimize/focus transitions remain
  untested. See `reverse-engineering/movies.md`.
- **KMRP now enables Large Address Aware / 4 GB virtual-address support on
  64-bit Windows.** Gold v22 changes only
  `IMAGE_FILE_HEADER.Characteristics` at file `0x926`, from `0x010F` to
  `0x012F`. The exact clean executable with that one bit already set is accepted,
  normalized for deterministic patching, and backed up unchanged; restore
  returns either supported input byte-for-byte. Other executable changes remain
  rejected. `testing/regression/Test-LargeAddressAware.ps1` covers both inputs,
  identical output, an unrelated-header rejection, and both restore paths.
  Memory-heavy gameplay remains untested.
- **The remaining reported 3840×2160 HUD and full-screen layout defects are now
  generated from measured geometry instead of width-scaled upstream defaults.**
  `optfeedback.gui` aligns each embedded row prototype with its scaled parent
  list and scrollbar, restoring the full text pane. `scriptselect.gui` now does
  the same for the Character Scripts list and description pane, whose frame had
  scaled while its content rows remained at 640×480 coordinates. The shared
  `confirm.gui` panel now contains both action rows instead of ending 115 pixels
  before Cancel at the tuning scale. The target name/health strip
  and transient journal, credit, XP, item, stealth, and alignment notifications
  now use the shared height-based UI scale and the play-tested 3440×1440 gold
  proportions. `testing/regression/Test-GeneratedGuiGeometry.py` reads all 48
  packaged archives and verifies the active HUD, both affected prototype pairs,
  and confirmation-child containment.
  The packaged 3840×2160 files were installed and hash-verified; in-game visual
  confirmation remains untested.
- **Windows display scaling no longer applies a second zoom layer to KMRP's
  resolution-aware interface.** In-place installs now add the per-user
  `HIGHDPIAWARE` compatibility flag for the selected `swkotor.exe`. KMRP records
  the exact prior compatibility string in `KMRP_DPI.manifest`; restore puts that
  string back only if the value still equals what KMRP installed, so a later user
  change is never overwritten. Permission failures leave the registry unchanged
  and report the manual Compatibility-tab fallback. The four ownership paths are
  covered by `testing/regression/Test-DpiCompatibility.ps1`. Automated on Windows
  11 build 26200; visual tests at 125%, 150%, 175%, and 200% and Windows 10 remain
  untested.

---

## [2.10.0] — 2026-09-04

First tagged release, and the first public one. `PatchVersion` in
`src/patcher/KmrpPatcher.cs` reads `2.10.0-mapnotes`; gold snapshot
`swkotor_gold_v21_mapnotes.exe`, SHA-256
`9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC`.

### Added
- **Area map fog now covers the whole map.** The grid was built and normalised
  inside the 1478x720 marker overlay while the map picture was drawn on a
  1720x720 canvas, so 242px down the right showed picture no fog tile ever
  covered. Gold v19 rewrites `0x006944A8` / `0x006944C4` from
  `fdivr [shared constant]` to `fidivr [ebx+0x0C]` / `[ebx+0x10]`, stepping the
  grid by the live rectangle instead of a constant, and gold v21's Option D sizes
  the canvas so the map content fills its frame, `LBL_Map` cropping the surplus
  as vanilla does. See `reverse-engineering/area-map-surface.md`.
- **250 map-note position corrections** from *K1 Area Map Fixes* by Derslok,
  GPL-3.0, used with permission. Only the data is taken; the lookup is KMRP's and
  needs no hook of its own, because the wrapper KMRP already installs at
  `0x0086D000` receives the note's world position as its own first two arguments.
  Optional under Advanced Settings. See `reverse-engineering/map-markers.md` §7.
- **K1 Modern Driver Compatibility 1.2.0** by Synchro, MPL-2.0, bundled with
  permission and installed unless turned off. Two files beside `swkotor.exe`;
  the executable is never touched. Its eight patch sites were checked against
  every byte KMRP writes: 0 of 8 collide, and 8 of 8 still hold the bytes it
  expects. See `docs/third-party-driver-compat.md`.
- **Party Portraits** by MadDerp and the **KOTOR 1 HD Icon Pack 1.0** by
  JackInTheBox, both bundled with permission and not optional.
- **Advanced Settings** in the patcher — a settings view in the same card, with a
  cross-fade, for turning the two optional components off. The choice persists in
  `%LOCALAPPDATA%\KMRP\settings.json`.

### Fixed
- **Map clicks landed 141px right of the pointer** after the map surface moved.
  The hit-test wrapper centred the canvas in the window, but `LBL_Map` is placed
  by the overlay and the canvas overhangs it. Since the overlay is
  `screenWidth // 2`, the inset collapses to `window / 4`: eleven bytes replaced
  by eleven, no relocation. Measured live before and after -- 719, then 860.
- **Hand-tuned 3440x1440 layouts reached only 17 GUI files.** The transfer was an
  allow-list and had drifted, so 23 tuned files -- `abilities.gui`, `store.gui`,
  every options screen -- shipped upstream's extents at every other resolution and
  their text ran to the edge of the artwork. The set is now derived from which
  files actually differ, covering 39.
- **A gap between the map and its frame.** The frame's opening measured 726 rows
  against a 720-row map. `tools/fit_map_frame_art.py` moves the top edge down 5
  and the bottom up 1, touching only the frame's own columns.
- **Bundled artwork no longer overwrites another mod's files.** A bundled file
  already in `Override` that KMRP's manifest does not claim is skipped, so K1CP's
  `ia_class8_004.tga` and `ia_class9_003.tga` survive. Scoped to the bundled art;
  KMRP's own files install as always.

  executable in place.** `IsVerifiedPatchedInstall` called an install patched
  whenever the sidecar's `patchedSha256` matched the file on disk, which proves
  only that nothing edited the executable since — not that those bytes came from
  the current build. `--in-place` therefore exited 0, rewrote the sidecar, and
  skipped the executable: reinstalling over gold v19b left `0x006944A8` still
  reading `fdivr dword ptr [0x008750A0]` instead of the new
  `fidivr dword ptr [ebx+0x0C]`. The Gold branch of `ApplyInPlace` now rebuilds
  the expected bytes from the verified clean backup and compares; anything else
  is restored and re-applied. The sidecar also records `goldTargetSha256`, the
  gold hash of the build that patched the install, which is what the check falls
  back to when no backup is available. Reusing the same `PatchVersion` string
  made the old behaviour easier to hit but was never the cause. Covered by
  `testing/regression/Test-ReinstallOverOlderBuild.ps1`.
- **Area map markers no longer shrink as the map grows.** Map note, party and
  player-arrow rectangles were built from vanilla immediates while the marker
  overlay scaled with the screen, so at 3440x1440 they were 3.4x smaller
  relative to the map than in vanilla. **Fourteen** sites now scale by
  `max(1, height/720)`, giving 2x markers at 1440p: four sizes, eight centring
  offsets and two control extents. A map note has separate selected and
  unselected draw paths, and `mm_barrow` and `lbl_mapcircle` each carry their own
  control extent — the first two attempts scaled only some of them. Gold v18.
  See `reverse-engineering/map-markers.md`.

### Documentation
- Repository documentation set: `LICENSE` (GPL-3.0), `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, this changelog, issue and pull request
  templates, a continuous integration workflow, `.gitattributes`, and indexes
  for `docs/` and `reverse-engineering/`.
- **A byte-level audit of the patched executable.** At the time this entry was
  written, `reverse-engineering/binary-inventory.md` called a merged 893-byte
  presentation span “changed bytes.” That wording was corrected on 2026-09-05:
  the current inventory counts actual unequal byte positions separately from
  the readable merged spans and ties every run to the document explaining it;
  `tools/build_binary_inventory.py` regenerates it and exits non-zero if any run
  has no write-up. Its first run found six patch sites that were implemented and
  explained in build scripts but had never reached a document — including the
  reference build's baked-in 3440x1440 constants and the two guards that were
  blanking stack counts. Those six are now written up.
- A plain-language summary of every executable change, above, so the patch can be
  understood without reading the version history.

### Changed
- `README.md` rewritten for people who have not seen the project before:
  what it is, how to install and undo it, what it fixes, and how it works.

---

## [2.7.0] — 2026-09-02

Gold snapshot `swkotor_gold_v15_popup.exe`
(`79356D1A92637C1B5C619B530FDA742A622A330E19AD628DBA19464202425048`).

### Added
- Shared message popup (tutorial hints and confirmations) rebuilt: auto-fit
  height stop, width cap and icon rect raised in the executable, with the
  `confirm.gui` layout generated per resolution from a play-tested table.
- Thirteen tutorial icons shipped at the popup's icon size per resolution, with
  `tutorial.2da` repointed at private copies so the eight shared source
  textures keep their existing sizes everywhere else.

### Fixed
- **Message text clipped mid-word.** The auto-fit loop widens the popup only
  while it is narrower than a cap authored for 640×480, so at any HD size the
  loop never ran.
- **The patcher could not install over an existing installation.** Four places
  assumed every install was a first install, so no build could ship a changed or
  added Override file without a full restore first; three of them reported it as
  a resolution mismatch. An interrupted install could also leave a backup file
  that permanently blocked retries.
- Tutorial icons were written upside down, and were generated from KMRP's own
  scaled output rather than the stock texture pack.

### Changed
- Patcher executable now carries version information (product, description,
  version, copyright) instead of a blank description and `0.0.0.0`.

## [2.6.0] — 2026-09-02

Gold snapshot `swkotor_gold_v14_minimap.exe`
(`1F1684A5DC8BC440B2C8FF0194873315EDD39DE1C1039CB2E73861A4B3732504`).

### Fixed
- **HUD minimap content was not zoomed to the player** at resolutions the engine
  did not recognise, and the fog-of-war grid did not match the zoomed map.
  Added as the `.kmz` and `.kfg` sections.

## [2.5.0] — 2026-08-31

### Fixed
- **Item stack-count numbers disappeared** once the font was enlarged. The label
  is built in the inventory row's `SetRect` rather than any `.gui`, and is
  bottom-right-aligned inside the icon box, so scaling the icon left it behind.
  Three of its four constants were `imm8` operands capped at 127, so the
  arithmetic was relocated into a `.ksc` stub with `imm32` operands.

## [2.4.0] — 2026-08-31

### Fixed
- **List rows grew every time a list was repopulated** — a vanilla BioWare bug,
  reproduced with a `.gui` byte-identical to the original. Invisible at low
  resolution because growth is clamped by box height; measured ratcheting
  42 → 56 → 126 on the Powers tab with a larger box.

## [2.3.0] — 2026-08-31

### Fixed
- Inventory, Abilities and Store rows and icons stayed vanilla-sized, being
  driven by hardcoded constants no `.gui` edit can reach.

## [2.1.0] — 2026-08-30

### Fixed
- **Inventory crash** on items with long descriptions. The line-breaker's only
  guard compared against the start of the string rather than the current line,
  so an unbreakable line looped until the allocator failed.

## [2.0.0] — 2026-08-29

### Added
- First universal release: one patcher covering **48 resolutions** across 4:3,
  16:10, 16:9, 21:9 and 32:9, replacing the earlier 3440×1440-only gold patcher.
- Resolution-aware font scaling (`max(1.0, height / 720)`) carried on the font
  atlases' TXI metrics, list-row scaling, and a height-derived dialogue
  letterbox.
- Verified backup and restore for the executable, INI and Override folder.

[Unreleased]: https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/compare/v2.10.0...HEAD
[2.10.0]: https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases/tag/v2.10.0
