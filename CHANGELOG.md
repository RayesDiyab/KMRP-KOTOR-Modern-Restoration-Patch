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
> that starts:** it is the first tagged version. The entries below it, 2.7.0 back
> to 2.0.0, are reconstructed; it and everything above it are not. (Until
> 2026-09-24 this said "every entry above it is reconstructed". Newest entries
> are at the top, so that had the direction backwards.)
>
> **Public names.** 2.10.0 is **KMRP 1.0**, and [Unreleased] is **KMRP 1.5**.
> The headings keep the internal `PatchVersion` numbers, because the tag
> `v2.10.0` and the 2.0.0 hash record use them.

## Everything the patch changes in the executable

The version entries below are a running record of *changes*, so they describe
each fix at the moment it landed and never in one place. This section is the
other view: **the complete set of differences between an unmodified
`swkotor.exe` and a patched one, in plain language**, so it can be read without
knowing the project's history.

It is kept honest by
[`reverse-engineering/binary-inventory.md`](reverse-engineering/binary-inventory.md),
which lists every byte position the installer changes -- the 721 where gold
differs from the clean executable and the 21 more it writes over values gold
leaves vanilla -- and refuses to pass if any run of them has no technical
write-up. If something appears there and not here, this section is out of date.

**The size of it.** KMRP's installer changes 742 byte positions inside the
original 4,042,752-byte executable, at one resolution or another — 0.018% — and
appends eleven new 4KB sections holding the code and data the original has no
room for, so every patched executable is 4,087,808 bytes. Nothing else in the
file moves. Measured on 2026-09-24 by running the installer (`ECA3DE4B…`) at all
48 resolutions.

*Corrected 2026-09-24:* this section said 702 positions and ten sections, the
count before gold v24 added the movie aspect fit, and before the installer's
own output rather than gold was counted. It also lacked five of the rows below:
the movie aspect fit, the list gutter, the blank first line, the HUD minimap's
zoom and fog, and two of the resolution fields.

| What you see in game | What changes in the executable |
| --- | --- |
| **Text is legible at modern resolutions** instead of tiny. | Text size is carried on the font atlases' own metrics rather than scaled at runtime, because scaling it at runtime changed the size one frame *after* the engine had already measured and centred the text, which visibly shifted the first screen of each session. The executable keeps a scale constant for list rows, which are built after nothing has measured them and so have no such ordering problem. |
| **List rows grow with the text**, so save/load and dialogue entries stop overlapping. | A hook rewrites each row's height as the row is constructed. Rows never shrink below vanilla, so short screens are untouched. |
| **Inventory, Abilities and Store rows and icons are sized to match.** | Three separate hardcoded 56s decide the icon box, the text offset and the row height, none of them reachable from any `.gui` file. That is why editing the interface files alone never moved them. |
| **Item stack counts are visible again.** | Two guards blanked any string of one or two characters that did not fit its box, and the enlarged font made the fixed 21px stack label too narrow to pass them, so two-digit counts silently vanished. Both guards are removed, together with a fix to the line-breaking loop that they were the only thing protecting against. |
| **The game no longer crashes** on items with long descriptions. | The line-breaker's only guard compared against the start of the whole string rather than the start of the current line, so a line that could not break looped until memory ran out. |
| **Lists keep their gaps where they belong.** | Each list's `PADDING` byte did six jobs at once -- left and right inset, the first row's top, the row pitch and two fit tests -- so a gutter beside the text also spread the rows apart and pushed the list down. It is now a horizontal gutter only, on the scrollbar's side, in both of the engine's list-rect builders. |
| **Descriptions no longer open with a blank line.** | The game builds a description by prefixing a newline to each property line, so an item whose description starts with properties began with an empty line. Leading newlines are stripped as the text is set. |
| **Dialogue gets proper letterboxing** at any aspect ratio. | The bars are derived from screen height rather than assumed. |
| **The area map fills its frame**, at every resolution. | The map picture is drawn on its own canvas, separate from both the window and the marker overlay, and sized so its content fits the frame; the `LBL_Map` control crops whatever overhangs, as it always did. |
| **Fog of war covers the whole map** instead of stopping 242px short on the right. | The fog grid was stepped by a fixed constant while the map was drawn at a different width, so the last strip was never covered by any tile. Two instructions now read the live rectangle instead of that constant. |
| **Clicking a map marker hits the marker.** | The hit test recentred the map's canvas inside the window, but the control that positions it is placed by the overlay, and the canvas overhangs it. Clicks landed 141px to the right; eleven bytes were replaced with eleven, and it was measured live before and after. |
| **Map markers keep their size as the map grows**, and stay on their subject. | Note, party and player-arrow rectangles were built from the original hardcoded sizes while everything around them scaled. |
| **250 map notes point at the right place.** | Optional. A table keyed on each note's shipped world position substitutes a corrected one. It needs no hook of its own, because the code KMRP already redirects receives that position as its own argument. The corrections are Derslok's measurements, used with permission. |
| **The HUD minimap stays zoomed in on you**, however large it is drawn. | Vanilla sizes the minimap's map picture for a 120-pixel viewport, so an enlarged viewport showed a zoomed-out map. The picture is scaled by `viewport / 120` about the centre -- only when the viewport is square and the source is the map atlas, so nothing else that shares the draw is touched -- and the fog grid is scaled to match, or explored ground re-fogged as it left the middle. |
| **The HUD minimap is unaffected by the map work.** | The full map and the HUD minimap share one constructor. The minimap's call to it is wrapped, and the wrapper puts that one instance back to retail values — so the map screen can be resized without dragging the minimap with it. |
| **The process can use more than 2 GB of virtual address space on 64-bit Windows.** | The PE header's standard `IMAGE_FILE_LARGE_ADDRESS_AWARE` bit is enabled. No allocator or code path is changed. |
| **Full-screen movies stay in the selected display mode.** | KOTOR has two independent 640x480 mode pairs around Bink playback even though the renderer itself scales from the live client rectangle. Both pairs are rewritten per resolution, avoiding the forced legacy-mode transition. |
| **Movies keep their shape** instead of being cropped. | Retail scaled every movie by the screen width alone, so a 640x480 logo became 3440x2580 on a 3440x1440 screen and lost 1140 rows. The scale is now the smaller of the width and height ratios, in a small appended routine. The bars this leaves beside a narrow movie are painted black by the optional controller component; without it they show whatever was on screen. |
| **Tutorial and confirmation popups fit their text** instead of clipping it. | The shared popup sizes itself from constants that never accounted for larger text. |
| **Interface elements sit where they should** at your resolution, not at 640x480. | Two shared helpers recentre almost every non-HUD screen using the resolution the interface was designed for. The patcher writes your actual resolution into them at install time, which is also why the reference build in this repository has one author's monitor baked in and the shipped executable never does. Two more width and height pairs get the same treatment: a centring subtraction that assumed 640 pixels, and a mode comparison against 800x600. |
| **The correct interface artwork is chosen for your screen.** | A chain of width comparisons picks a resource set; the first is redirected to your width and the later ones are disabled so they cannot win instead. |
| **Nothing else.** | The remaining changes are the PE header's own bookkeeping — the section count, the code and image sizes, a zeroed checksum, and the eleven new section headers. One casualty is worth naming: a leftover `Hellspawn Reborn` signature string sitting in the header's unused padding is overwritten by the fifth section header. Nothing reads it. |

**What is *not* changed in the executable**, though the patch installs it:
interface layout files, font atlases and icon artwork all ship as ordinary
`Override` files, and the bundled *K1 Modern Driver Compatibility* patches its
own process in memory at startup without writing to `swkotor.exe` at all. The
optional controller component is the same: its hooks, including three memory
fixes from the KOTOR Patch Manager project, are applied in memory by its runtime
from `patch_config.toml`.

## [Unreleased]

**This is KMRP 1.5**, the build in progress. Its installer reports 1.5.0 in
Properties → Details and in the install record
(`swkotor.exe.kotor-ui-patch.json`).

Until 2026-09-24 it carried internal numbers, and they disagreed.
`PatchVersion` read `2.11.0-movieaspect`, but Properties → Details still
reported `2.10.0-mapnotes`. It was the second time these two drifted apart;
1.0 itself reports 2.7.0.0 there. `build_kmrp.ps1` now refuses to compile
while they disagree. Before the versions were corrected, it was run against
the real mismatch and refused it.

The 1.5.0 installer of 2026-09-25 (`B599303A…57108`, 179,624,960 bytes) was
compared with the play-tested one of 2026-09-24 (`ECA3DE4B…`):
- its `--apply` output at the 48 resolutions both builds share is
  byte-identical, so every executable measurement below that cites `ECA3DE4B…`
  also holds for it;
- the 49th resolution, 2880x1620, is new (below);
- its GUI archives differ, because every resolution now ships `dialog.gui` for
  the dialogue A. It has 70 resources: the 49 archives, the MIT licence and the
  controller module with the fixes below.

Intermediate builds of the same days, never installed as releases:
- `D81E640C…`, the relabel without the licence;
- `7933…`, with the licence;
- `78A5CC43…`, the first build with 49 resolutions.

- **The KOTOR Patch Manager MIT licence is installed with the controller.** The
  runtime, the controller module and the memory-safety patches all come from
  KPM, which is MIT-licensed, and MIT asks for the notice to travel with every
  copy. The installer shipped all three without it. It now embeds
  `LICENSE-KOTOR-PATCH-MANAGER.txt` and installs it as
  `kmrp-kotor-patch-manager-LICENSE.txt`; the controller manifest owns it, and
  Restore removes it. `Test-ControllerSupport.ps1` checks the installed copy
  byte for byte, and `Test-ReinstallOverOlderBuild.ps1` also passes.

### Added

- **2880x1620, the 49th resolution** (issue #16), for DSR at 2.25x on 1080p
  screens. High Resolution Menus has no layout for it, and its layouts are made
  by hand per resolution, so scaling one does not reproduce another. But
  2880x1620 is exactly halfway between two it does ship, 1920x1080 and 3840x2160,
  so `tools/derive_resolution_gui_set.py` interpolates every field halfway:
  - an extent upstream doubles comes out 1.5x;
  - one it holds fixed, such as the list prototypes, stays fixed;
  - a hand adjustment lands between its two values.

  The same method, run at a third of the way, reproduces upstream's real
  2560x1440 set: 87.6% of its 9,276 extent fields exactly and the rest within
  1 px, against 73.9% for plain scaling. It gets its own 2.25x font set. The
  installer's catalog check, the build's resolution count and the
  virtual-display profile now expect 49. **Not seen in play**, since no
  maintainer screen runs 2880x1620.

- **An A beside the highlighted dialogue reply** (issue #21), left of the
  reply's number, following the highlight like the main menu's A. It shows only
  while a controller is in use and replies can be picked, and it hides while a
  line plays, when A would skip it instead. Every resolution now ships
  `dialog.gui` to carry the label. Below 3440x1440 that is a vanilla-equivalent
  file rebuilt from the tuned 3440x1440 asset, differing from the game's own
  only in four colour floats in the seventh decimal. The art is the confirm
  boxes' A, in all four families. **Untested in game.** Two of its inputs --
  which field holds the highlighted row, and which space the row rects are in --
  are read from the disassembly, not measured. It writes a `dialog-geometry`
  line to `kmrp-layout-lifecycle.log` the first time each conversation shows
  replies, so one play-test confirms the placement or shows how to fix it.

  **That play-test (2026-09-25, 3440x1440) found it off screen.** The log
  confirmed both inputs: the rows are relative to the list, and `[panel+0x68]`
  and the list's own index agreed. But it read `placed=(-77,0,32,32)` for a panel
  at x 48, which is screen x −29. The rows are 3312 px wide in a 3344 px list,
  because the list's 32 px scrollbar sits on their left, and the A had been
  placed from the row's edge rather than from where the text starts. It is now
  placed just left of the text (list left + scrollbar width), clamped to the
  screen. At 1920x1080 the same rule gives the text start seen in a screenshot,
  48 + 16 = 64 px. **The corrected placement is untested in game.**

- **Menu and dialogue text is drawn at the size it was rendered at** (issue
  #16). Two players reported pixelated, aliased text, one at 1920x1080 and one
  at 3440x1440, which ruled out any single resolution being at fault. The font
  atlases were baked once at scale 3.0 and reused everywhere, with the
  per-resolution TXI rescaling `texturewidth` — and `texturewidth * 100` is what
  turns glyph coordinates into texels, so it matched the atlas's real width at
  3840x2160 and nowhere else. 1080p declared 512 px of a 1024 px atlas, 1440p
  declared 683. Every font TXI also carries `mipmap 0` and `filter 0`, so that
  resampling was point sampled: texels dropped rather than blended, which threw
  away the antialiasing the atlas had, and 1440p's uneven 1.5:1 ratio is what
  made strokes look ragged. Each resolution now ships atlases baked at its own
  scale, so one texel lands on one pixel and nothing is resampled. **The
  typeface is unchanged** — the same Old Republic and Arimo Medium as before,
  baked more than once. Adds about 15 MB to the installer;
  `Test-FontAtlasScale.py` asserts the one-texel-per-pixel invariant for every
  font at every resolution. 15360x8640 is the one exception and still resamples,
  because its scale-12.0 atlas is larger than the baker can produce.

- **The mouse stays inside the game window** on multi-monitor setups (issue
  #20). KOTOR steers the camera with mouse movement but never clips the cursor,
  so a wide enough sweep put the pointer on the next display and the camera
  stopped following. The cursor is now clipped to the game window's client area
  whenever KOTOR is the foreground window, and released on Alt-Tab, on losing
  focus, on minimise and on exit — a crash cannot leave it trapped, because the
  clip does not outlive the process. The game imports no `ClipCursor` of its
  own, so nothing in the engine is being overridden. It ships inside the
  optional controller component, which is installed unless turned off, so a
  player who declines that component does not get it; see
  [controller-support.md](docs/controller-support.md). Untested on real
  multi-monitor hardware.

### Fixed

- **Down from Close no longer loses the focus on in-game Options.** Reported
  2026-09-25 with a screenshot: pressing Down at Close, the bottom entry, left
  nothing highlighted, and Up could not bring the focus back. With nothing
  below Close, the D-pad navigation wrapped to the farthest control above it in
  the same column, which was the description pane. That is a list box, which
  the navigation admits on tab screens so the Messages and Journal lists can be
  reached. The pane draws no focus highlight and keeps every D-pad press to
  scroll its text, so focus could not leave it. The navigation now never chooses
  a screen's description pane. The right stick scrolls it, and the vendor code's
  per-screen table (`FindK1DescriptionListbox`, now exported as
  `KmrpDescriptionPaneK1`) says which control it is. Down from Close wraps to a
  real button instead. **Untested in game**; diagnosed from the code and the
  report, not reproduced.

- **Controller buttons leave every screen when the mouse or keyboard takes
  over**, not only the screen in front. Reported 2026-09-25: switching to mouse
  and keyboard cleared the badges on the current screen, but the next screen
  opened with the mouse still showed them. Badges are texture swaps on a
  screen's own buttons, and the in-game menu builds its tab screens once and
  keeps them, so a tab painted while the pad was in use kept its art. The clear
  ran only on the panel in front when the device changed, assuming that any
  other panel reaching the front in keyboard/mouse mode was new and blank.
  `UpdateK1ControllerPrompts` now records every panel it paints (with its
  vtable, so a freed-and-reused address is not written to) and clears each one
  the first time it comes to the front in keyboard/mouse mode. The R3, LT/RT and
  swap-tab cues never had the problem: every live cue is shown or hidden each
  frame. **Untested in game.**

- **Cancel now cancels on the Solo Mode prompt** (issue #21). Pressing A with
  Cancel highlighted turned Solo Mode on anyway. The panel is a retained Xbox
  one: its handler at `0x006C244C` calls `CClientExoApp::TogglePartyFollow`
  before looking at anything, and never reads which button has focus — on the
  Xbox there was none, A meant yes and B meant no. KMRP now consumes A there
  when Cancel holds focus and exits into the panel's own close path, so A on
  Cancel does exactly what B does. That first fix left **both buttons
  refusing**: it was a KPM consumed-exit hook, and KPM runs a hook's stolen
  bytes before it tests the handler's answer. The stolen instruction loaded
  EAX, so the test never saw the answer and every A took the close path, OK
  included. Both hooks now sit at the panel's input-handler entry and, with
  Cancel focused, rewrite A into B on the stack, so the game's own dispatcher
  cancels; A on OK runs the vanilla confirm once. `check_hook_stolen_bytes.py`
  now refuses a consumed-exit hook whose stolen bytes touch EAX or the stack.
  **Play-tested on 2026-09-24:** A on OK turns Solo Mode on and A on Cancel
  leaves it off; `kmrp-confirm-focus.log` records each decision.
  **The resolution screen had the identical
  defect** and was fixed with it: A applied the highlighted resolution from
  Cancel, through `CSWGuiOptionsResolution::OnResolutionChosen`. That half is
  not yet play-tested. Ordinary
  confirmation boxes were never affected — they implement no `0x27` at all, so
  A genuinely reaches the focused control.

- **Sound Options: Down from Movie Volume reaches Advanced Options.** It jumped
  to Default, while Up from Default reached Advanced correctly. A focused slider
  handled every direction itself, and for Up and Down it follows the game's own
  links, which skip Advanced. A horizontal slider now keeps only Left and Right;
  Up and Down go through the same navigation as every button, on every options
  screen with a slider. Play-tested on 2026-09-24.

- **The Movies screen shows B / Circle on Close.** The screen already closed on
  B; nothing said so. Play-tested on 2026-09-24.

- **Xbox LT and RT use the Xbox 360 trigger art**, like the rest of the Xbox
  set, on the menu tab strip and the Controller Layout screen. Play-tested on
  2026-09-24.

- **The R3 party-switch cue is 10% smaller, and sits beside the portraits
  where it did not fit between them.** On all four party screens. Its side
  was the whole space between the two portraits -- the gap or their height,
  whichever was smaller -- and is now 90% of the portrait height
  (`R3_CUE_SCALE`).

  It stays centred in the gap wherever the gap holds it with a tenth of it
  free either side: every 32:9 and 21:9 resolution but 1280x1080, 3440x1440
  included, where nothing moved. At 4:3, 16:10 and 16:9 the gap is narrower
  than a portrait, and a cue sized to fit it was a few pixels wide -- 6 px at
  800x600, and 5 px once made 10% smaller, which is what prompted the move.
  There it now sits right of the second portrait, a third of a cue away, like
  the tab-strip cues. Right rather than left: the portraits sit at the curved
  left end of a bar the background art draws, and on the left the cue was
  rendered crowding that curve on all four screens, while the bar runs on
  empty to the right. Measured in the built archives, identical on all four
  screens:

  | Resolution | Portrait | Gap | Before | Now | Where |
  | --- | ---: | ---: | ---: | ---: | --- |
  | 800x600 | 35 | 6 | 6 | 32 | right of the portraits |
  | 1920x1440 | 84 | 15 | 15 | 76 | right of the portraits |
  | 1920x1080 | 63 | 36 | 36 | 57 | right of the portraits |
  | 2560x1440 | 84 | 48 | 48 | 76 | right of the portraits |
  | 3840x2160 | 126 | 72 | 72 | 113 | right of the portraits |
  | 3440x1440 | 84 | 94 | 84 | 76 | between them |
  | 5120x2160 | 126 | 138 | 126 | 113 | between them |

  The build refuses a cue that would cover a button or a list, and
  `Test-GeneratedGuiGeometry.py` now checks the cue's size, placement, spacing
  and centring in all 48 archives; nothing checked its geometry before. The new
  check rejected the old placement on the 160 of 192 screens it changes.
  Rendered against the real background art at 800x600, 1920x1080 and
  3440x1440. **Play-tested on 2026-09-24 at 3440x1440**, where the cue stays
  between the portraits; the right-of-portraits placement is not yet seen in
  game.

- **Swap-tabs prompts for every controller.** The "swap tabs" art existed for
  Xbox only, and the other controllers showed a bare X-position button there.
  PlayStation, Switch and Steam Deck now have their own. Reported working in
  play on 2026-09-24; the families tried were not recorded.

- **Installer: the optional components are independent.** Controller support
  no longer forces Modern Driver Compatibility on. Both need the same ASI loader,
  so it is installed whenever either is chosen, and Synchro's patch itself only
  when driver compatibility is. The controller option is described as what it
  now is -- Xbox, PlayStation, Switch and Steam Deck, credited to KMRP and the
  Saul0097 module it grew from -- and each row's credit no longer overlaps its
  switch. Controller support is now on by default like the other two, and
  *Restore Defaults* turns all three on. The independent switches were
  play-tested on 2026-09-24.

- **Loading a save from in game no longer crashes.** With a save already loaded
  from the main menu, loading another from the in-game menu crashed mid loading
  screen, every time. KMRP's controller module kept a table of the controller
  cues it adds to in-game screens and checked each frame whether their screens
  still existed by reading them; loading a save destroys those screens, and once
  their memory was released the check itself crashed. Cues are now forgotten when
  their screen is destroyed, their labels are freed rather than leaked, and no
  remembered screen is read without first confirming its memory is still there.
  Present since the R3 cue was added on 2026-09-15. **Play-tested on
  2026-09-24:** the same sequence now loads.

- **Feedback Options: the circles no longer sit on the scrollbar.** The option
  list keeps its scrollbar on the left, the game starts each row exactly where
  the scrollbar ends, and draws each circle at the row's very edge. The list now
  has a small gutter on that side, 12 px at 3440x1440, scaled with the
  resolution. Awaiting an in-game check.

- **Script Selection: the option rows are centred in their box.** They started
  outside the box's left edge and stopped short of its right one. The box is
  drawn by the background art at a fixed share of the screen width, so the
  rows' left inset is now computed per resolution to leave the same margin on
  both sides. Awaiting an in-game check.

- **Answering a dialog no longer acts on the world behind it** (issue #21).
  Dismissing "do you wish to turn Solo Mode on?" with A went on to start a
  conversation with whoever was targeted. A asks for the world-interaction
  bridge on press, and that request was made whatever owned the input; the
  consumer checks that gameplay is active, but it checks when it runs, and
  closing the dialog handed the input back well inside the request's 250 ms
  window. The request is now gated on press, exactly as B's already was.

- **The resolution screen has controller glyphs**, the one Options screen that
  never did (issue #21). A on OK, B on Cancel, and the D-pad moves between them.

- **A confirmation box no longer blanks the badges of the screen behind it.**
  `CSWGuiMessageBox` was missing from the panel search, and the modal branch
  returns nothing for a top modal it does not recognise, so opening any Yes/No
  dialog cleared the prompts on the screen underneath.

- **Yes/No boxes show an A beside the focused button** (issue #21, Quit Game).
  Exit Game, Solo Mode, overwrite and delete save all use one confirmation
  box, whose buttons the engine shrinks to fit their captions, so no badge can
  be painted inside them. The A is now a control of its own that sits just
  left of whichever button has focus and moves with the D-pad, like the main
  menu's. Shown only while a controller is the active device. Awaiting an
  in-game check.

- **Removed the Solo Mode prompt's Cancel badge**, which drew as a thin red
  smear across the caption rather than a glyph beside it. `FixMessageLabel`
  (`0x006253A0`) rewrites both message-box button extents before drawing,
  overwriting the third field with `0x64`, so the button is roughly an eighth of
  the width its `.gui` declares and the badge is stretched by the wrong factor.
  Rebuilding it for the real width does not help: a disc sized to the control's
  height covers the middle of a button only two and a half times as wide as it
  is tall. These buttons needed a prompt drawn beside them instead of inside,
  which is what the travelling A above now is.

### Added

- Added a **Controller Layout** screen, opened from **Options → Gameplay** by a
  button directly under Keymapping. A real controller diagram — Xelu's CC0
  Xbox Series X or PS5 silhouette, tinted to KOTOR's palette with the pad's own
  face-button glyphs on it — sits between two columns of callouts, each an
  engine-drawn glyph and caption joined to its button by a leader line. It
  follows the pad: Xbox, PlayStation, Switch and Steam Deck each get their own
  diagram and glyphs, swapped live without rebuilding the screen. Captions
  describe what the native controller path actually does (View is solo mode,
  LB/RB cycle targets, Start opens the Map), not the legacy key table the first
  draft used. Row order is searched so that no leader line passes through a
  button that is not its own; on the Xbox silhouette, which three families
  share, none cross either. The screen is full-screen rather than a box: a
  navy backdrop with dim, original edge art anchored to the real screen edges
  at every aspect — corner brackets, hairlines, two status readouts, and in the
  side margins a turret gunnery station and a light freighter's deck plan. Its
  lettering is real Aurebesh (SilvinoR's OFL font) spelling English that means
  what it says. The A that opens it no longer closes it again: the screen used
  to flash for a frame and shut unless A was held. Nor does the A that closes
  it through Back reopen it, and Back now shows the pad's B / Circle glyph.
  The long captions are whole again: the game draws the screen's labels in the
  larger menu font, so they wrapped and showed only their last line ("Free
  look", "Tab"). Their boxes are now sized from that font at every resolution.

- **Options → Gameplay: Mouse Settings, Keymapping and Controller Layout sit
  higher**, by half their own spacing, so the new button no longer touches the
  bottom bar. In-game manual acceptance
  remains outstanding.

- Added a hybrid XInput / SDL3 HIDAPI controller backend and pinned x86 SDL
  packaging. Xbox retains XInput; mapped non-Xbox devices feed the existing
  normalized controller state, physical-position Nintendo glyphs, and rumble.
  Device discovery is throttled and handoff releases old-device input. Runtime
  and physical-device validation remain outstanding; see
  [controller-sdl-backend.md](docs/controller-sdl-backend.md).
- Hardened NVIDIA profile ownership: a same-name foreign profile is not adopted,
  existing shared profiles are left alone, and unavailable-driver restore keeps
  its recovery record. Verified saves remain eligible for rollback even when
  their subsequent readback fails.

- **Controller glyphs follow the controller** (issue #19). The badges and cues
  show PlayStation, Switch or Steam Deck buttons when that is the pad being used,
  and Xbox otherwise. The module asks about the one pad it reads, the way SDL
  does: `XInputGetCapabilitiesEx` (`xinput1_4.dll` ordinal 108) gives the USB
  vendor and product id behind that XInput slot -- Sony `054C` is PlayStation,
  Nintendo `057E` Switch, Valve `28DE:1205` the Steam Deck, anything else Xbox.
  Through **Steam Input** the slot holds Steam's virtual pad (`28DE:11FF`), and
  Steam publishes the physical controller behind it in the file named by
  `SteamVirtualGamepadInfo`, which the module reads for that pad's `[slot N]`. A
  translator that presents an Xbox pad of its own, such as DS4Windows, gets Xbox
  buttons. It is asked only when that pad connects or changes slot, or when Steam
  rewrites its file: no timer, nothing to configure.

  All four families are built and shipped, named by the resref's fourth letter
  (`kmrpb_charexit` Xbox, `kmrsb_…` PlayStation, `kmrnb_…` Switch, `kmrdb_…` Steam
  Deck), so the Xbox names are unchanged and nothing grows past 16 characters;
  the installer grew 28.1 MB. The Switch set maps by button **position** -- the
  bottom button a Switch Pro labels B carries the A action -- which assumes a
  positional translator. `check_controller_drift.py` fails if the module's and the
  build's family letters disagree or any family's art is missing, and
  `Test-ControllerPromptAssets.py` checks every family's badges against that
  family's own art.

  **Verified:** the call on this machine (a virtual Xbox 360 pad reads
  `045E:028E`) and the parsing of Steam's file in SDL's documented format.
  **Untested:** a real Steam virtual pad, any physical PlayStation, Switch or Steam
  Deck controller, Proton, and the new families' art in game. See *Controller
  families* in [`docs/controller-support.md`](docs/controller-support.md).
- **Start opens the Map, and closes the menu again** (issue #18). In the world
  it now sends the engine's own Map hotkey, event `0xD7`, instead of Start's
  `0x0B`, which opened Options; with the in-game menu in front it acts as B, so it
  closes the Map or whichever screen LT/RT moved to. The Map is `0xD7` because the
  router sends `0xD1`–`0xD8` to one handler (`0x006218D5`) that shows screen
  `event - 0xD1`, and the Map's tab ID in `top.gui` is 6. Options and every other
  screen stay one LT/RT away. **Not yet verified in play**;
  `testing/controller/test_hud_release_and_start_map.py` checks it against the
  engine's memory once a save is loaded.
- **X is shown beside the Skills / Powers / Feats tabs.** It has cycled them
  all along and nothing said so.

  That it really does was read from the handler rather than assumed: the
  ABILITIES panel registers `0x29` at `0x006AE714`, which reads a byte at
  `CGuiInGame+0xBC0`, switches on 0, 1 and 2, and writes 0 back on the third
  -- a three-state cycle that wraps, which is exactly three sub-tabs.

  One control rather than two: the bundled `Swap_tabs.png` is already the
  whole phrase, the X button and the arrows together. Its art is about two to
  one, so its control is given that shape and its texture the same, which
  keeps the engine's stretch equal on both axes -- the square cue builder now
  takes a height for exactly this.

  Placed from the sub-tab row: one third of a tab's height past the last tab,
  on the row's own line.
- **LT and RT are shown either side of the menu tab strip.** They have moved
  between the eight in-game screens since controller support landed, and
  nothing said so.

  The same mechanism as the R3 cue, on a panel that took no extra proving:
  the tabs are not in the screens that display them -- `inventory.gui` has no
  tab controls at all -- they belong to `top.gui`, whose panel draws with the
  base `CSWGuiPanel::Draw`, the same child-walk the cue mechanism relies on.

  Both cues are positioned from the strip itself: its pitch, its height and
  its vertical centre, each sitting one pitch beyond the outermost tab, where
  a ninth and a zeroth tab would be. So they follow the strip at every
  resolution with no coordinates to keep in step.

  The runtime table changed shape -- from a list of panels sharing one tag to
  a list of (panel, tag) pairs -- because this panel wants two cues rather
  than one. Nothing else about the binding changed.
- **R3 changes which party member a menu is showing.** Character, Equipment,
  Inventory and the Skills/Powers/Feats screen are each about one party
  member, and with a pad there was no way to switch between them: the two
  portrait buttons in the bottom bar could only be clicked.

  Nothing new had to be invented. `0xCE` is a retained GUI event the screens
  implement themselves, and the full event inventory says exactly four panels
  implement it -- ABILITIES, CHARACTER, EQUIP and INVENTORY, which are
  precisely the four screens that carry the portrait pair. That match is the
  evidence it is the party switch rather than something else sharing a code.

  Dispatched to the panel rather than to `CClientExoAppInternal`. The two are
  different actions with one name: `0x09` changes who the player controls in
  the world, `0xCE` changes who a screen is about. Only the second belongs in
  a menu. It is performed on the GUI frame rather than in the input hook,
  because the handlers rebuild the screen around the new character -- the same
  reason the Journal's remapped buttons are deferred. Counted as `psw`.

  R3's native code is suppressed while a menu is in front. It did nothing
  there already -- free-look enter is registered in `ICPC` only, so the slot
  is not polled in `ICPCGUI` -- but one press meaning one thing is the rule
  the rest of the input layer follows. Free look in gameplay is unchanged.

  **It is advertised by the two portraits, on a control the game does not
  have** -- between them, or right of them where the gap is too narrow (the
  entry above; it was always between them until 2026-09-24, 5 px wide at
  800x600). There was nowhere to put a badge: a badge replaces a control's
  `BORDER.FILL`, the portraits' fill *is* the portrait -- rewritten per
  character by the panel -- and the gap between them holds no control. No
  spare label exists to move there either; Inventory has fifteen controls and
  uses all fifteen.

  Adding one to the `.gui` does nothing on its own, which was measured rather
  than assumed: a control was added to a live `inventory.gui` and nothing
  drew. The reason is that a panel does not load the file's controls, it asks
  for the ones it knows by name -- `0x0040B930` resolves a tag by walking the
  GFF and comparing `TAG` -- so a control nobody asks for is never built.

  So the build adds `LBL_KMRPR3` to the four screens, placed from each
  resolution's own portrait extents, and the module binds it at runtime. That
  is possible in exactly one instant: every panel constructor ends by calling
  `CSWGuiPanel::ReleaseGff`, which deletes the parsed `.gui` and nulls the
  pointer the binder reads. Hooking that one function catches all 68
  constructors with the panel already in `ecx`, and its prologue has no
  relative operand for a trampoline to relocate. Panels that are not party
  screens are ignored.

  The control is then drawn because `CSWGuiPanel::Draw` walks the same array
  the binder files into, skipping null slots and gating each child on
  `bit_flags & 2`. That bit is the engine's own show/hide -- it sets it on a
  control that loaded and clears it to hide one, which is how CHARACTER hides
  its ten alignment-meter labels immediately after binding them -- so the cue
  follows the pad by flipping one bit rather than swapping any artwork.

  Sizes and addresses were read from the gold image and each confirmed more
  than once; `reverse-engineering/custom-gui-controls.md` records every one,
  including the ownership question -- the array's destructor frees the pointer
  block and never dereferences an element, so a control we allocate is never
  freed. That is a `0x140` byte leak per panel construction, against the
  `0x1DE8` the engine allocates for the panel itself.

  The glyph is `XboxSeriesX_Right_Stick_Click.png`, on its own square texture:
  the control is square at every resolution, so unlike the caption badges it
  needs no pre-compensation and one texture serves the whole game. `L3` is
  deliberately left on the 360 artwork -- nothing uses it, and restyling an
  unused glyph is a change nobody asked for.

### Fixed
- **A no longer stays stuck on the bottom-right action bar** (issue #17). Using a
  slot with A now lets go of the bar, so the next A talks to the NPC or opens the
  door again, and **B** lets go of it without using anything -- B had no other
  effect in the world. D-pad Left/Right re-enters the bar as before. The press
  that uses a slot also clears the world interaction's pending request, so one
  press still does exactly one thing now that the bar's focus goes away within
  the same frame. `hrel=` in the diagnostic line counts the releases. **Not yet
  verified in play**; see `testing/controller/test_hud_release_and_start_map.py`.
- **The one-frame white flash in the in-game menus is gone** (issue #14), along
  with two quieter relatives: the menu backdrop drawn alone for a frame when
  switching to the Utility or Equipable filter, and a half-drawn world, with
  characters missing, on the frame a menu closes.

  None of the three was the engine's doing. NVIDIA's **"Vulkan/OpenGL present
  method: Prefer layered on DXGI Swapchain"** puts frames on screen that the game
  has not finished drawing, and each symptom is a frame caught while it stalled:
  the flash is `WinMain`'s bare frame-start `glClear` (the area's `SunFogColor`,
  near-white on Manaan) during the 15–65 ms the inventory takes to rebuild.
  Measured on an RTX 3080, driver 32.0.16.1656, two-minute captures:

  | present method | menu fix | white flashes | other unfinished frames |
  | --- | --- | ---: | ---: |
  | Prefer layered (global) | off | 7 of 8 tab entries | — |
  | Prefer layered (global) | on | 0 | 2 and 6 in two runs |
  | Prefer native | on | 0 | 0 |
  | Prefer native | off (checked in the live process) | 0 | 0 |

  NVIDIA's default is Auto, and on Auto the driver presented both vanilla and
  KMRP natively in-game; this machine's *global* had been set to prefer layered.
  So the patcher now checks, through NvAPI, what the driver will do for the
  installed `swkotor.exe`, and **only if it would inherit Prefer layered** sets
  Prefer native (`OGL_CPL_PREFER_DXPRESENT`, `0x20D690F8` = `0`) in the game's
  own profile — normally NVIDIA's predefined KOTOR profile — recording it in
  `KMRP_NVIDIA.manifest`. A value set for the game on purpose is left alone,
  the global profile is never touched, restore removes only KMRP's value, and
  any error is logged with the manual steps rather than failing the install. No
  administrator rights needed. See
  [`docs/nvidia-present-method.md`](docs/nvidia-present-method.md) and
  `testing/regression/Test-NvidiaPresentMethod.ps1`.

  **Correction, 2026-09-19:** the development renderer-clear mitigation was
  removed from the module, exports, TOML, and installer. It had hooked VA
  `0x0040467C` (`NativeFrameClearK1`) and `0x004512D0`
  (`NativeSceneRenderK1`), with diagnostic `fcl=` counters. Native driver
  presentation is the production fix; no independent engine defect justified
  retaining clear suppression. Historical measurements remain in
  [the investigation](reverse-engineering/experiments/white-flash-video-capture.md).

  **Untested:** a full install writing a real KOTOR profile (this machine's
  already held a value, which the installer correctly kept), 32-bit Windows,
  older drivers, Optimus laptops, and AMD or Intel, where no such path was seen.
- **Three memory-safety patches from the Kotor Patch Manager project are now
  installed.** Two are VexFlint's and one is Lane Dibello's, each adopted
  rather than re-derived: the replacement bytes are copied verbatim, so the
  behaviour is the one reviewed there. KMRP
  had already folded in KPM's *rendering* fixes -- cube maps, grass tearing,
  soft shadows -- and none of its memory ones, and that split was not
  principled. Two of the three are bounds and lifetime bugs that get more
  likely the more textures and data a session loads, which is what KMRP does to
  this engine.

  They install as ordinary entries in KMRP's own hook table, so the executable
  on disk is not touched and the gold SHA-256 is unchanged at
  `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`. Each
  patch's `original_bytes` was checked to match **both** the clean source and
  the gold image -- KMRP's own delta touches none of those four addresses.

  | site | address | type | what it does |
  | --- | --- | --- | --- |
  | `AurTextureGetMaxTexID` | `0x0041FEB5` | `replace` | saturates the returned id at 4999 |
  | `AddPartToMeshBuckets` | `0x0046BE64` | `replace` | range-checks the id before the indexed write, rejoining at `0x0046BEB1` |
  | `DestroyGrassPolys` | `0x004A847C` | `replace` | zeroes the argument when `+0x3C` aliases `+0x38` |
  | `~CAurTriangleBin` | `0x004A8380` | `replace` | the same, with `eax` for `edx` |
  | `CERFFile::WriteResource+0x272` | `0x005DDE32` | `detour` | `NativeFreeSaveBufferK1` frees the buffer the writer abandons |

  The first two are the texture-bucket overrun: three 5000-entry arrays at
  `0x008194E0` are indexed by driver-assigned GL texture names with no range
  check, and `maxTexID` (`0x007A46BC`) only ever rises. Saturating rather than
  masking, because an `AND` would wrap a legitimate 4500 down to 404 and leave
  stale buckets uncleared. See
  [`reverse-engineering/experiments/texture-bucket-overrun.md`](reverse-engineering/experiments/texture-bucket-overrun.md).

  The grass pair is one allocation stored in two fields that two paths each
  free; `free` (`0x006FB7B2`) guards NULL explicitly, so zeroing the aliased
  argument is a safe no-op. The save detour reclaims one buffer per resource
  written, counted as `sbf` in the diagnostic line.

  The hook tooling had to learn that a hook need not name an exported function:
  `kmrp_controller.is_byte_patch` identifies one, ownership for those is KMRP
  directly, the renderer emits `replacement_bytes` instead of `function`, and
  the drift checker matches them by address. Without that, adding the first
  byte patch would have raised `KeyError` in every one of those checks.

  **Measured in play, not assumed:** across two sessions on this build
  `maxTexID` peaked at 471 and 296 against the 5000-entry array, so the
  overrun was not reached in either -- the patch is a guard, and nothing here
  claims it fixed a symptom that was observed. `sbf` stayed 0 because neither
  session saved.
- **Holding a D-pad direction now scrolls a list, on every screen.** Reported
  on Quest Items: a held Down moved one item and stopped.

  Two layers navigate menus, and only one of them repeated. Where KMRP moves
  the focus itself it has always held-and-repeated -- 400 ms, then every
  120 ms -- which is why the tabbed screens behaved. Where the ENGINE
  navigates, KMRP stands down and emits the retained direction code instead:
  `NavigateFocusK1` declines when a focused control navigates itself and the
  screen has no tab strip, and `KmrpOwnsDirectionsK1` agrees. That path sent
  one press and one release, and `CSWGuiListBox` acts on the press and
  nothing after it -- it has no auto-repeat of its own.

  The emitter now repeats the presses it sends, on the same two constants, so
  a held direction feels identical whichever layer is handling the screen. It
  repeats only what actually went out (`dpadEmitted`), so the screens KMRP
  navigates are untouched and the direction is never delivered twice -- the
  double-step `KmrpOwnsDirectionsK1` exists to prevent. Each repeat releases
  before pressing, because a second press with no release in between is not
  an edge and the engine would ignore it. Counted as `drp` in the diagnostic
  line.

- **A pad that is plugged in shows its badges from the first frame**, instead of
  waiting to be pressed. Reported from the launch sequence: skipping the intro
  movies with the pad and then arriving at a main menu with no badges on it.

  "Nobody has used anything yet" was the state that did not exist. The flag was a
  boolean over two meanings -- pad, or not-pad -- with not-pad as the opening
  value, so a menu reached before any press read as keyboard-and-mouse. It is now
  three: the pad is in use, the keyboard or mouse is in use, or the question is
  still open. While it is open a connected pad answers it, because a pad plugged
  in is a statement of intent where a keyboard sitting there is not. The instant
  either device is actually used the question closes for good, so nothing about
  how the two hand over has changed -- only where they start.

  The connected half had to be taught to the native path too.
  `g_controllerConnected` was maintained only by `ReadPad`, which runs from the
  legacy poll; the native module reads XInput itself, so it knew a pad was
  answering while that flag did not, and the opening state could never have
  fired. `ReadPadAxes` now reports presence either way.

  Worth noting for anyone chasing the same symptom: `ConsumeMovieSkipK1` was
  *not* the culprit. It already raises the active flag when a skip button is
  held, so skipping a movie with the pad did count as pad use. **Playtest
  pending.**

### Added
- **An A badge that follows the focus down the main menu**, and badge art for
  the equipment and quest items screens, which had none at all.

  The main menu's badge is a new kind of binding, `FocusOnly`: it is painted only
  while its control holds the panel's focus and cleared otherwise, so one A
  travels with the selection instead of five sitting there at once. Clearing is
  as much the point as painting -- without it the badge would be left behind on
  the entry the focus just left. The focused control is now part of the state the
  repaint compares against, or the early-out would hold the first frame's badge
  for as long as the screen stayed up, which is the trap the inventory filter's
  caption fell into.

  All five are placed as a **badge group**: sized from the shortest control in
  the group and placed against the widest label in it, so they stand in one
  column at one size. Placing each against its own button gave five glyphs that
  stepped sideways down the list, and made Quit's a fifth larger than the rest
  because it is 81 tall where the others are 66.

  | Button | Label | Was | Now |
  | --- | --- | --- | --- |
  | New Game | 181px | x 194.7, r 19.1 | **x 187.0, r 19.1** |
  | Load Game | 197px | x 187.0, r 19.1 | **x 187.0, r 19.1** |
  | Movies | 121px | x 224.8, r 19.1 | **x 187.0, r 19.1** |
  | Options | 142px | x 214.4, r 19.1 | **x 187.0, r 19.1** |
  | Quit | 74px | x 241.8, r **23.5** | **x 187.0, r 19.1** |

  The installer's re-centring survives grouping without any change to it, and
  the reason is worth recording: its shift is
  `CenterFor(measured) - CenterFor(baked)`, which reduces to
  `(baked - measured) / 2` -- the radius cancels. So giving every member of the
  group the same variants in the manifest makes them all resolve the same
  measured width and shift by the same amount, and the column survives a
  language whose wording is longer.

- **The control offsets came out of the engine rather than a symbol database.**
  A panel's controls are embedded objects and the bind call names each one:

  ```
  0067AE38  push 0x752F0C          "BTN_LOADGAME"
  0067AE4D  lea  eax, [esi+0x5B4]   the embedded control
  0067AE5E  call 0x0040B930         bind
  ```

  `tools/extract_control_offsets.py` reads all 771 of those call sites. Doing it
  mechanically mattered: the four upper main-menu buttons sit on a uniform
  `0x1C4` stride and `BTN_EXIT` does not -- it is bound earlier, at `0x1084` --
  so extrapolating the stride would have put that badge on nothing. The register
  holding the control also varies (`ecx`, `eax`, `edx`, and `ebx` loaded 240
  bytes earlier on the quest items screen), which mispaired two tags until the
  extractor matched `lea`/`push` pairs rather than a fixed register; every
  offset below was then checked against the disassembly.

  | Screen | Button | Offset | Badge |
  | --- | --- | --- | --- |
  | Main menu | NEWGAME / LOADGAME / MOVIES / OPTIONS / EXIT | `0x3F0` `0x5B4` `0x778` `0x93C` `0x1084` | A, follows focus |
  | Equip | BTN_EQUIP / BTN_BACK | `0x3698` / `0x385C` | A / B |
  | Quest items | BTN_BACK | `0x8A8` | B |

  **Playtest pending.**

### Fixed
- **The mouse no longer stops working at random, and the pointer hides and
  returns with the input device reliably.** Reported as two symptoms -- sometimes
  no menu item can be clicked, keyboard only; and the cursor not disappearing for
  the pad and reappearing for the mouse -- which turned out to be one mechanism,
  and two faults in it rather than anything to do with detecting input.

  KMRP parks the pointer near the top of the screen and hides it through the
  engine's own reason mask while the pad is the device in use.

  **A failed park or unpark was forgotten.** The pending flag was cleared
  unconditionally, before the move was attempted:

  ```
  g_pendingCursorToggle = false;         // cleared whatever happens
  if (MoveK1Cursor(!g_cursorParked)) {   // and this can fail
  ```

  `MoveK1Cursor` returns false whenever there is no active GUI manager or its
  viewport is not sized -- during a load, a movie, a scene transition. The
  request was dropped there, and since the edge that raised it had already
  recorded the new device, it could never be raised again until the device
  changed a second time. When the failure landed on the *unpark*, the cursor
  stayed parked and hidden while the player was on mouse, and the per-frame
  re-assert kept snapping it back to the top of the screen: invisible, immovable,
  hit-testing nothing. That is the "I can't press any menu items with the mouse"
  exactly, and as intermittent as whether a GUI manager happened to exist at that
  moment. The flag is now cleared only once the move has actually happened.

  **The module counted its own cursor moves as the player using the mouse.**
  `MoveK1Cursor` goes through the engine's `MoveMouseToPosition`, which forwards
  to `HandleMouseMove` -- the very function KMRP hooks to notice mouse activity.
  So every park, and every re-assert of the park spot, read as though a hand had
  moved the pointer. That broke the detector both ways: several panels place the
  cursor on a default control as they open, so the re-assert undoing it could
  accumulate the 24 pixels and 2 events that mean "the mouse is in use" and hand
  the pointer back mid-controller-session; and while parked, a real movement and
  the snap-back cancelling it both counted, so the distance measured bore little
  relation to how far the hand moved. A guard around the module's own moves now
  keeps them out of the detector.

  One consequence of retrying is that a flip can still be pending when the device
  changes again, which would apply it the wrong way round. The device-change edge
  now *assigns* the flag rather than only raising it, so a stale request is
  cancelled -- which also means a device change wins over a pending F9, the right
  precedence for an override that only applies within a mode. **Playtest
  pending.**

- **The Journal's A and Y buttons do what their badges say.** Reported from
  play: the button labelled A, "Active Quests", was pressed by Y, and the button
  labelled Y, "Sort by Priority", answered to nothing.

  Read out of `CSWGuiInGameJournal`'s dispatcher at `0x006456E0`:

  | Event | Handler | What it does | Pad sent it |
  | --- | --- | --- | --- |
  | `0x29` | `0x00645C8C` | opens Quest Items, via `0x0040BC70` on `[panel+0xFB4]` | X |
  | `0x2A` | `0x006459CE` | Active/Completed -- `0x00645610`, then a re-sort | **Y** |
  | `0x2B` | `0x0064573F` | the sort order -- `inc eax / cmp eax, 4` into `[0x00833A90]` | **Back** |
  | `0x28` | `0x00645CAB` | close | B |

  So the badges were right about the intended layout and wrong about the facts.
  The sort was not unreachable -- Back sends `0x2B` -- but no badge says so, so
  in practice it answered to nothing a player would try.

  A now sends `0x2A` and Y sends `0x2B`, on this screen only, through a small
  per-panel remap table. The native code is **suppressed** for a remapped
  button, which is what makes it a remap rather than an addition: without that,
  Y would sort *and* toggle in one press. The decision is taken at the press and
  remembered for the release, the same way the direction codes do it -- deciding
  again at the release would let a screen change mid-press leave a digital
  description holding a value nothing ever clears, and the button would stick on
  for the rest of the session.

  Back keeps `0x2B`. It is a second way to reach the sort, it collides with
  nothing, and removing it was not asked for. The comment on that binding said
  "Journal quest items", which was wrong -- quest items is `0x29`, on X -- and
  now says what `0x2B` actually is.

  `rmp=` in the diagnostic line counts remapped presses performed.
  **Playtest pending.**

### Changed
- **The item icons ship at 160x160 instead of 192x192**, taking the pack from
  12.4 MB to 8.5 MB: 25.0 KB an icon rather than 36.1 KB. This reverses an
  earlier decision to keep them at native size, so the reasoning for the
  reversal is recorded beside the reasoning it replaces.

  The cost is real and measured. `equip.gui` draws item icons through controls
  whose EXTENT is exactly 192x192 at the authored resolution, so 192 is native
  and 160 is upsampled 1.2x on the largest place icons are drawn -- 24.1 dB
  against 27.8 dB on colour weighted by visibility.

  | Size | Each | 351 total | Visible colour |
  | --- | --- | --- | --- |
  | 192 | 36.1 KB | 12.39 MB | 27.8 dB |
  | **160** | **25.0 KB** | **8.57 MB** | **24.1 dB** |
  | 144 | 20.2 KB | 6.94 MB | 23.5 dB |
  | 128 | 16.0 KB | 5.48 MB | 22.6 dB |

  **The free version of this saving does not exist**, which is why resolution
  was the only lever. DXT1 would have halved the size at 34 dB -- it carries no
  alpha, so it spends its whole budget on colour -- but it needs one bit of
  alpha and this executable cannot upload that at all. The format table at
  `0x0073F36C` holds the no-alpha `0x83F0` and DXT5's `0x83F3` and nothing else;
  `GL_COMPRESSED_RGBA_S3TC_DXT1` (`0x83F1`) appears nowhere in the image.
  Repointing `0x83F0` would hand the transparent three-colour mode to all 5,229
  shipped DXT1 textures, and **1,387 of them use it** -- holes through Jawa,
  Gammorean and Ithorian skins and the BioWare logo.

  **The resize is premultiplied**, and that is a correctness fix rather than a
  refinement: the RGB of a fully transparent pixel in these icons is arbitrary,
  and a straight Lanczos blends it into the visible edge as a fringe. Measured
  on twelve icons, the naive and premultiplied resizes differ by 30.5 dB -- the
  same order as the compression error itself, so doing it the easy way would
  have thrown away much of what the remaining pixels buy.

  `ICON_TEXTURE_SIZE` in `prepare_universal_resources.py` is the one place this
  lives; setting it back to `ICON_SOURCE_SIZE` restores native size and nothing
  else has to change. **Playtest pending.**

### Fixed
- **The full-screen menu backgrounds are compressed.** With the item icons
  converted, they were what was left: an installed Override measured 1008 MB, of
  which all 351 icons are 12.4 MB -- 1.2% -- and forty-nine full-screen
  backgrounds are 768 MB, at 15.68 MB apiece, uncompressed 32-bit. Two of them
  are `lbl_equip` and `lbl_invent`, read exactly when the Equipment and
  Inventory screens open, which is where a residual hitch was reported after the
  icons were fixed.

  Measured on the installed files at 2867x1434:

  | | Size | | Quality |
  | --- | --- | --- | --- |
  | uncompressed | 15.68 MB | | |
  | **DXT1** | **1.96 MB** | 8.0x | 37.7 dB |
  | DXT5 | 3.91 MB | 4.0x | same colour; the alpha is all 255 |

  27 of the 49 are fully opaque -- every `lbl_*` menu background, including both
  of the two that matter -- so they take DXT1, which with no alpha to carry
  spends its whole budget on colour. That is why it scores *better* here than
  DXT5 does on the item icons (36.9 dB), where half the bits go to an alpha
  channel. The engine already uploads 5,229 of its own textures this way. The
  other 22 are loading screens carrying alpha on 0.49% of their pixels, and take
  DXT5.

  Across all 49: **768 MB -> 139 MB**, and opening Equipment reads 1.96 MB where
  it read 15.68 MB.

  Two details worth keeping. DXT encodes 4x4 blocks and these are 2867x1434, so
  the image is padded up to the block grid by repeating its last row and column
  -- padded rather than cropped, because the added pixels duplicate the frame
  border where a crop would shave three columns off it. And the source TGAs
  carry descriptor `0x08`, bottom-left origin, matching TPC's own row order, so
  they are flipped before encoding exactly as the icons are; the icons once
  shipped upside down for want of that.

  **Font atlases are excluded and must stay excluded.** `dialogfont32x32` is
  2048x2048 -- *larger* in pixels than these backgrounds, so a size threshold
  alone would catch it -- and DXT on glyph edges would visibly damage every line
  of text in the game. The selection tests the name as well, and the build now
  fails if the number of backgrounds it compresses is not exactly 49, so a
  change to the shared assets cannot quietly pull a font in or drop a background
  out. **Playtest pending.**

- **The compressed item icons can actually reach an existing installation.**
  The HD icons ship as DXT5 `.tpc` rather than 192x192 uncompressed `.tga`,
  because Inventory and Equipment are the only two screens that stall and the
  only two that draw dozens of icons. On any machine that already had KMRP
  installed, that fix could never land, so the stall stayed.

  Bundled third-party art yields to whatever is already in `Override`, so KMRP
  never overwrites a mod the player installed on purpose -- and the test spans
  texture extensions, because the engine resolves a texture by resref and
  prefers `.tpc` over `.tga`, so a bundled `.tpc` would otherwise silently win
  over a player's `.tga`. But it only asked whether a sibling *existed*, never
  whose it was. Installing `i_x.tpc` looks up `i_x.tpc` in the manifest, does
  not find it -- the manifest holds `i_x.tga` from the build before -- and then
  yields to that `.tga`. **KMRP was deferring to itself.**

  Measured on a live installation patched before the change:

  | | |
  | --- | --- |
  | `.tga` in Override | 1095 |
  | `.tpc` in Override | **0** |
  | at 147,500 bytes (192x192, uncompressed) | 399 |
  | of those, bundled by the current build as `.tpc` | **351** |
  | files recorded in the manifest as KMRP's own | 1196 |

  Those 351 total 12.4 MB as `.tpc` against 51.8 MB as `.tga` -- 4.1x smaller,
  39.4 MB less to load on the two screens that stall.

  Two changes. The sibling test now ignores a sibling the manifest already
  records as ours, since a file KMRP installed is not the player's file whatever
  extension it carries. And installing a texture over our own superseded sibling
  deletes that sibling, so the uncompressed copies do not sit on disk forever
  and do not keep blocking every future install. The sibling's manifest record
  is deliberately left in place: restore skips its hash check when the file is
  gone, and still copies the player's original back if they had one.

  The installer now reports how many it replaced.

  **Not changed:** 48 icons still ship as 192x192 uncompressed, and they are
  KMRP's own art rather than the bundled pack -- 18 empty-equipment-slot
  placeholders and 30 `lbl_*` tab and HUD pieces. They are interface chrome with
  hard edges, where DXT artefacts show far more than they do on item art, and 18
  textures are not what makes a full inventory stutter. Left alone on purpose.
  **Playtest pending.**

- **The X badge sits beside the inventory filter button's caption, whichever
  caption it is showing.** It used to be drawn on top of the words. The badge is
  placed against the measured width of the label, and this button was declared
  as STRREF 32182 -- the bare words "Quest Items", which it never says.

  Its caption is built at runtime from an index:

  ```
  006B3A58  call 0x005ED690               CClientExoApp::GetGuiInGame
  006B3A5D  movzx eax, byte [eax+0xBC1]   the current filter
  006B3A64  inc eax                       the button offers the NEXT one
  006B3A65  cmp eax, 6 / mov 0            six wraps to zero
  006B3A88  mov edx, [ecx*4 + 0x756444]   that index into a STRREF table
  006B3AAC  push 0xA577                   42359, "Show"
  006B3ADD  call 0x005E5D10               append
  ```

  so it reads "Show " plus one of six filter names -- All Items, New Items,
  Quest Items, Equippable Items, Utility Items, Useable Items. Six, not the five
  consecutive strings `41818`-`41822`: "New Items" sits apart at `42165`, and is
  the one the `kmrpx_invnew` resref was named for.

  Measured on the 1166px-wide button with the metrics inside the built archive:
  "Quest Items" is 222px, and placing the badge for it put the glyph on top of
  **every one of the six captions** -- 19px into the shortest, 90px into the
  longest. The first pass at these figures used a font atlas found by globbing
  the repository rather than the one this resolution ships, and understated it.

  Rather than place it against the longest caption -- which never overlaps but
  leaves it floating up to 103px away from the shortest -- the build now bakes
  **one badge per caption**, `kmrpx_invnew0`-`5`, and the module picks the
  matching one from the engine's own filter index. Not by reading the label,
  which would depend on the player's language: `CGuiInGame+0xBC1` plus one,
  wrapping at six, is exactly the index the engine itself used to choose the
  words. Every caption now clears the text by the same 15px:

  Clearance is the gap between the badge's right edge and the first letter;
  negative means the glyph is drawn over the words.

  | Index | Caption | Label | Shipped | Widest-only | Per-caption |
  | --- | --- | --- | --- | --- | --- |
  | 0 | Show All Items | 289px | **-19px** | 86px | 15px |
  | 1 | Show New Items | 300px | **-24px** | 80px | 15px |
  | 2 | Show Quest Items | 337px | **-42px** | 62px | 15px |
  | 3 | Show Equippable Items | 431px | **-90px** | 15px | 15px |
  | 4 | Show Utility Items | 353px | **-50px** | 54px | 15px |
  | 5 | Show Useable Items | 379px | **-63px** | 41px | 15px |

  The middle column is what declaring the six captions but keeping one texture
  would have given: never overlapping, but drifting up to 86px from the words.
  The last is what shipped -- the same 15px on every caption, which is the
  generator's own gap constant, `radius * 0.55`.

  Each numbered texture carries only its own wording in the placement manifest,
  so the installer's existing per-row re-centring against the player's real
  `dialog.tlk` handles each one correctly with no change to it. The unnumbered
  `kmrpx_invnew` is still generated, placed against the widest, as the fallback
  for a module that cannot read the index.

  Three other toggling buttons were declaring only one of their wordings and had
  happened to pick the wider one: Messages' "Show Feedback" / "Show Dialog", the
  Journal's "Completed Quests" / "Active Quests", and its four sort orders. They
  now declare all of them. No English art changes, but the installer re-resolves
  these against the player's own `dialog.tlk`, so an undeclared variant is an
  overlapped badge in any localisation where the other wording is longer. These
  keep a single texture: their captions differ by far less, and each would need
  its own index read to do better. **Playtest pending.**

### Removed
- **The D-pad no longer moves focus onto the in-game menu's tab strip.** That
  layer was built before LT and RT changed screens; with those working it was a
  second, worse way to do the same thing, because focus could sit on a tab frame
  and a direction press then had two possible meanings depending on invisible
  state. The strip is no longer a focus target at all: every direction press
  acts on the content of the tab being shown. LT and RT change screen, X still
  cycles sub-tabs.

  Removed with it, each having existed only to serve focus sitting on a frame:
  the frames walk and the enter-content press, both routes back up to the strip
  (off the top of a list, and off a content panel's top boundary), the
  A-on-a-focused-frame bridge and the request the input hook raised for it, the
  tab-frames-only candidate filter, and five helpers left with no callers. The
  `entered`, `returned` and `activated` counters went too, since nothing could
  increment them any more. **Playtest pending.**

### Added
- **The diagnostic line's format and argument list are checked against each
  other.** `check_controller_drift.py` now parses the `wsprintfA` call, counts
  conversions against top-level arguments, and reports the worst-case width
  against the buffer. This is the bug it exists for: a conversion was once
  inserted mid-format with its argument appended at the end of the list, so
  every field after it printed the wrong variable, and the widened line overran
  a 512-byte stack buffer and tripped the `/GS` stack cookie -- the game froze
  on load and the cause looked nothing like a logging change. Verified to fail
  by introducing a mismatch deliberately.

### Fixed
- **Left and right on the equipment screen move sideways instead of jumping a
  row up.** The 3x3 slot grid is 192x192 cells on a row pitch of 150, so
  consecutive rows overlap by 42 pixels while the columns, on a pitch of 268, do
  not overlap at all. The focus layer waived its cross-axis penalty outright
  whenever two controls overlapped on that axis, so pressing right from Body
  scored the correct neighbour (Right Arm), the slot above it (Hands) and the
  slot below it (Right Weapon) at exactly 268 apiece -- same horizontal step, all
  three counted as "in the row". The tie-break is a strict less-than, so the
  first in the control array won, and the array runs top to bottom.

  The waiver is now a discount: a candidate that still touches the row pays a
  third of the rate one that misses it entirely pays, rather than nothing.
  Scored against the real geometry from the generated `equip.gui`, over all nine
  cells and all four directions, the old rule was wrong eight times -- every one
  of them a left or a right, with up and down always correct because the columns
  do not overlap -- and the new rule is wrong none. **Playtest pending.**

### Added
- **Rumble works.** The engine's rumble subsystem was never removed from the PC
  build -- `UpdateRumble` ticks every frame, the pattern evaluator and the mixer
  are both intact, and the module already forwarded the result to XInput. One
  field stopped all of it. `PlayRumblePattern` tests the caller's index against
  the pattern *count* before anything else:

  ```
  005FB49F  cmp ebp, dword ptr [ecx+0x344]
  005FB4A5  jge 0x5fb536                      -> return 0, nothing queued
  ```

  and that count is zero for the life of the process, so every rumble the game
  asked for was dropped at the door. Two instructions in the entire class write
  those fields -- the constructor zeroing them (`0x005FC15C`, `0x005FC168`) and
  the destructor freeing and re-zeroing (`0x005FC82A`, `0x005FC844`) -- found by
  sweeping every instruction in the class's address range, not by inference.
  The loader went with the Xbox build.

  KMRP now supplies the table, and nothing else changes: `PlayRumblePattern`
  appends an instance, `UpdateRumble` walks the list taking each motor's maximum
  through `CSWRumblePattern::GetMagnitudes`, and the detour already sitting on
  `0x005F7617` forwards the pair to XInput.

  **Which patterns exist is measured, not invented.** Two exhaustive sweeps of
  the shipped content:

  | Source | Swept | Patterns found |
  | --- | --- | --- |
  | 2DAs with a `rumblepattern` column | all 209 in `chitin.key` | `footstepsounds` → 17; `visualeffects` → 11, 14, 16, 20 |
  | NCS calls to routine 370, `PlayRumblePattern` | all 401 bifs, rims, erfs and mods | adds 5, 12, 13, 15 |

  The union is 5, 11, 12, 13, 14, 15, 16, 17, 20, so the count is 21 and every
  index nothing references is silent rather than guessed at. The same sweep
  found **no** call to `StopRumblePattern` anywhere in the shipped content, which
  settles the loop flag: a looping pattern would never be stopped and the motors
  would run until the area unloaded, so every entry is one-shot.

  | Pattern | What fires it | Shape |
  | --- | --- | --- |
  | 5 | `k_pend_1b_area2` | a swell, ~1.1s |
  | 11 | tarentatek/terentatek arrivals, `VFX_FNF_TERANTANAK_DEATH` | slow and heavy, ~0.9s |
  | 12 | `k_pkor_ceil_fall` | the hit, then debris, ~1.2s |
  | 13 | `k_pkor_ther_dest` | demolition: full scale, long tail |
  | 14 | all seven grenade VFX plus 18 script sites | a crack and a fast decay, ~0.45s |
  | 15 | `k_pend_rumble01` | a sustained tremor, ~2.2s |
  | 16 | `k_pend_area02`, `VFX_IMP_SCREEN_SHAKE` (cutoff 30) | strong and sustained, ~1.6s |
  | 17 | `footstepsounds` rows 5 and 10, both `Stomp` | one short heavy footfall |
  | 20 | Force Choke, Force Push, Force Wave | a shove, no crack |

  **What each one feels like is authored**, and that is the honest limit here:
  BioWare's envelope data went with the Xbox build and cannot be recovered from
  the PC files. The *mapping* is not authored -- each shape is cut to the events
  the sweeps name.

  The table is allocated with the engine's own `operator new` (`0x006FA7E6`),
  because the destructor frees it with the matching `0x006FA390`. The hook now
  also takes `UpdateRumble`'s own `this` from `EBP` and refuses to install
  unless it matches the module's pointer walk, since a table written to the
  wrong object would be handed to `free()` later. **Playtest-confirmed on a
  real pad**: a frag grenade, pattern 14, rumbles.

  This also settles which magnitude drives which motor, previously left open:
  `0x005F760F` loads envelope B's maximum into `EAX` and `0x005F7613` loads
  envelope A's into `ECX`, so A is the heavy low-frequency motor and B the light
  high-frequency one -- which is the pairing the shapes were cut for.

### Fixed
- **The D-pad moves through the Powers, Feats and Skills lists.** It could not
  before: the press was swallowed and nothing on those screens moved. Their
  selection is not a focused control at all but a cursor owned by the screen, so
  neither a retained event delivered to a control nor the module's own spatial
  focus layer could reach it. Measured in the clean executable --
  `CSWGuiInGamePowers::HandleInputEvent` serves all eight direction events from
  one arm at `0x006F297B`, which walks a cursor object at `panel+0x19FC`
  (`+0x0C` column, `+0x0D` row, `+0x04` the count) through `0x006CDD80`, then
  stores the resulting selection at `panel+0x19C4` via `0x006F1460`.
  `CSWGuiInGameAbilities` does the same at `0x006AE818`/`0x006AE839`, and
  `SKILLS`, `FEATS` and `MAP` are built the same way.

  Behind the tab strip, `NavigateFocusK1` asked `PanelNavigatesItselfK1` with
  `reachable = false`, which by design drops the panel half of the test and
  leaves only the control half, so the panel was never dispatched to and the
  press fell through to the spatial layer, which sees nothing there because the
  grid is not made of controls. The screen is now handed its own direction event
  directly, and before the focused control rather than after: these screens own
  all four directions and forward to their own description box where that is
  what they mean (`0x006F299E` takes `0x3A` and sends `0x32` to the listbox at
  `+0xFCC`), so a description list holding focus would otherwise swallow up and
  down and leave the grid frozen.

  One deliberate consequence: up no longer climbs back to the tab strip on these
  screens. The grid wraps -- `0x006CDDB8` sets the row to 0 on passing the last
  -- so there is no top edge to detect. LT and RT still change screen, which is
  what the strip was being focused to do. **Playtest-confirmed**: the D-pad
  moves through the Powers, Feats and Skills lists.

### Fixed
- **R3 free look no longer crashes the game.** Raising the input device count so
  the engine polls a pad claimed a device that DirectInput never created, and
  nothing allocated its raw state block. `CExoRawInputInternal::GetLastState`
  indexes that block as `[rawInput+0x30] + (deviceIndex - 2) * 0x74`
  (`0x005E397F`-`0x005E3985`), so with the base null it read address 0. Measured
  under x32dbg on the live game: `0x005E399B`, `mov eax,[eax]` with `eax = 0`,
  called from `CExoInputInternal::GetEvents` at `0x005E2968` with `(2, 0)` — the
  pad's index and `DIJOFS_X`. Free look is what reaches it because vanilla
  registers the analog stick events in `ICPC` and `ICFreeLook` only, and the
  enter handler at `0x006216C7` calls `CExoInput::ClearEvents`, emptying the
  buffered records the pad normally speaks through. The module now allocates the
  block alongside the device count it raises, with the engine's own
  `operator new`, and only when the slot is null so a real DirectInput joystick
  keeps its own. Only two functions in the image index that array —
  `GetJoystickBuffer` at `0x005E31D4`, which the module already declines, and
  `GetLastState` — and a sweep of `0x005E2E00`-`0x005E3A00` finds no store to
  the pointer and no null test on it, so nothing gates on it or frees it.
  **Playtest-confirmed on a real pad**: R3 enters and leaves free look
  without crashing.

  A first attempt detoured `GetLastState` itself and was withdrawn: it sourced
  its parameter from `EAX` while also excluding `EAX` from restore, so the
  re-executed `cmp eax,[0074D3D0]` compared the handler's return value against
  the joystick index instead of the device index. It did not fix the crash and it
  broke controller/keyboard device-activity detection.

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
  *Since superseded:* this is the first integration. The component is now KMRP's
  native path -- the pad driving the game's own input pipeline, 18 detours and 4
  byte patches, prompts in four controller families -- and it is on by default
  since 2026-09-24; see the controller entries above.

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
  *Superseded in part:* the prototype rewrite for `optfeedback.gui` and
  `scriptselect.gui` was reverted on 2026-09-06 -- see *The Character Scripts and
  Feedback screens are no longer rebuilt from stale prototype geometry* above --
  and on 2026-09-24 those screens got a scrollbar gutter and centred rows
  instead. The HUD, notification and confirmation parts stand.
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

First tagged release, and the first public one: **KMRP 1.0**. The tag and the
GitHub release keep the internal number, and its Properties → Details report
2.7.0.0 (see [Unreleased]). `PatchVersion` in
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
