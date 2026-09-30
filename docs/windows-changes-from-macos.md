# Windows: changes the macOS build made first

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: tracker.** The Mac build is meant to look and behave the same as Windows at the same
resolution ([`macos/WINDOWS-PARITY.md`](../macos/WINDOWS-PARITY.md) tracks the other
direction: every Windows change and its state on the Mac). Some changes were made on the Mac
first. Until Windows has them too, the two builds differ. This lists each one: what the Mac
does, where, what Windows needs, and how to check it. Started 2026-09-30.

**Where these come from.** The shared code named below (the resource build, the patcher's
generators, the tests) was changed on the `macos` branch, which reaches `master` through
[pull request #23](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/pull/23).
No Windows build had been made from it by 2026-09-30. Everything marked **build only** is
written and needs only a Windows build from a `master` that has it and a check in play.

**Checked complete on 2026-09-30.** Every commit on the branch (`git log master..macos`)
was read for changes a Windows build lacks: `7d603c8` (items 2, 6, 7 and 9),
`d48758c` (the Mac port and its tests only), `d9eb50a`, `8f098fe` and `1336d53` (the
submodule and notices only), `7c52a84` (item 8), `8f6ac1e`, `0d147a1` and `3366c33` (Mac
documents and tests only; item 5 was found while writing `3366c33`), `4d1fe29` (items 1 to
4), `9eee359` (item 10), `0734db6` (the Mac installer's window, which has no Windows
counterpart to change: it ports the Windows patcher's), `f59663a` (these documents), `13e676c`
and `d44ee0d` (the Mac disk image, its icon and the Mac's controller option, which Windows
already has), and the commit adding item 11.

**Merged and built on 2026-09-30.** The branch up to `3fd22ad` was merged into `master` and
the Windows installer built from it (`04C2DA20…`), with the resources made again from the
merged build code. Items 2, 5 and 11 were done on Windows the same day; the other direction,
what the Mac now needs from that work, is
[`macos-changes-from-windows.md`](macos-changes-from-windows.md).

States: **to do** (Windows has nothing yet), **build only** (shared code already changed;
Windows gets it with a build from the merged code and needs a check in play), **built** (in
a Windows build, its automated checks passing; not yet seen in play), **done** (as the Mac
does it, checked as stated), **doc** (a Windows document to correct).

| # | Change | State |
| --- | --- | --- |
| 1 | Message popups fitted to their contents, width and height, centred | **to do** |
| 2 | Any resolution, not only the listed ones | **built** (2026-09-30) |
| 3 | Controller badges at their designed distance; the Container's buttons widened | **built** |
| 4 | Controller Layout caption boxes: margin over the corrected measure | **built** |
| 5 | `kmrp-controller.ini` removal on restore | **done** (the document corrected) |
| 6 | Skill icons enlarged with the Skills rows | **built** |
| 7 | HD item icons normalised to the game's own framing | **built** |
| 8 | Row frames, tutorial icons and `tutorial.2da` made at install from the player's game | **built** |
| 9 | The 17 Mac resolutions in the catalogue | **built** |
| 10 | The granted popup's rows: hex as tall as the text frame, text inset, rows spaced like the inventory's | **to do** |
| 11 | The header's smoke fades out before the header's bottom edge | **built** (not yet watched) |

## 1. Message popups fitted to their contents

**What the Mac does** (2026-09-30, [`reverse-engineering/message-popup.md`](../reverse-engineering/message-popup.md),
*The Mac: fitted to its contents*). The shared popup (tutorial hints, Exit Game, Solo Mode,
the unspent-points warning) keeps the size `confirm.gui` gives it, sized for its tallest and
widest case. At the end of the popup's own layout, `CSWGuiMessageBox::FixMessageLabel`, the
Mac's layout patch:

1. narrows the message to the least width at which its text still wraps to the same height
   (found by halving, tested with the engine's own wrapping), never narrower than the widest
   shown button or the icon;
2. shrinks the message to its text (the list's inner height less its own fit test,
   padding plus the tallest item);
3. puts OK 4 px under the message and Cancel 2 px under OK, and centres the icon and both
   buttons across the panel, as `FixMessageLabel` itself places them;
4. makes the panel as wide as the message plus its left inset on both sides, ending as far
   below the last shown button as the message starts below its top, and keeps its centre.

It does nothing when the text needs the scrollbar. It has no size of its own: every width and
height comes from the popup's own layout and the engine's own wrapping, so it holds at any
resolution. Seen in play at 3024x1964 only, on 2026-09-30:
the Exit Game box went from 1,224x711 px to 880x365, centred on the screen. The Attributes,
Skills and Feats tutorials came out fitted and centred with their line counts unchanged (4, 7
and 5).

**Where, on the Mac.** `macos/patches/kmrp-layout/popup_fit.cpp`. It replaces
`FixMessageLabel`'s last call (`0x100306a88`, `call 0x10049dc36`) with a call through the
layout patch's near page, and then makes that call itself. The Mac offsets it reads:

| Mac | What |
| --- | --- |
| `0x100306552` | `FixMessageLabel` (Windows `0x006253A0`) |
| `+0x8` | the panel's extent (left, top, width, height), set through the vtable's `+0x10` |
| `+0x850` | the message list; its extent at `+0x858`, inner height `+0x344`, tallest item `+0x368`, padding (byte) `+0x373` |
| `+0x3D0`, `+0x610` | OK and Cancel, extent at `+0x8` of each, shown while bit `0x2` of its `+0x68` is set |
| `+0x238` | the icon, extent `+0x240`, shown when bit `0x10` of the box's `+0x79` is set |
| `+0xC04` | the message's top as the file gave it, saved by the popup |
| `0x1004A81AE`, `0x100306B86` | the list's `SetExtent` and the message rebuild, called after every resize as `FixMessageLabel` does |

**What Windows needs.** The same four steps after `0x006253A0` has laid the popup out, in
the executable patch, since the popup is not part of the optional controller component. The
Windows equivalents of the offsets above are not yet read: `0x006253A0`'s own disassembly
gives them (its stack slots are read in `message-popup.md`, *The stack slots, read
correctly*; the buttons are placed from `0x006254AC` onward). The width search re-lays the
message out at each try, about 11 times per popup, as the Mac's does.

**Check.** At 3440x1440 and one 16:9 size, with the tutorials on: the Exit Game box, a
tutorial on each character-generation screen, and the Solo Mode prompt. Each box should hug
its text, keep its line count, have even margins, and be centred. A text long enough to need
the scrollbar should look exactly as before.

## 2. Any resolution, not only the listed ones

**What the Mac does.** The Mac installer accepts any size (`--size WxH`, or the display it
runs on). A listed size gets its built set. Any other size is made at install
(`macos/README.md`, *Other sizes*; `macos/WINDOWS-PARITY.md`, *Resolutions the build has no
set for*):

| Part | Mac |
| --- | --- |
| `.gui` files | blended from the finished sets around the size (`macos/tools/kmrp-guiblend.c` over `gui-blend.bin`, built by `tools/build_gui_blend_table.py`) |
| the Container | made, not blended: widened by the build's own rule (`fit_container_to_caption`) for the caption width of the set whose fonts are installed |
| the Controller Layout screen | made, not blended: `build_gui`'s arithmetic, with every number from the table by name |
| fonts, prompt art | the nearest listed set's, by height, then shape |
| row frames, tutorial icons, ability icons | made at the exact size from the player's game, as Windows already does for listed sizes |
| engine sizes | computed from the height by formula (`macos/patches/kmrp-layout`), not read from a table |

Measured on the 17 Mac sets, each held out and derived from the others with its own fonts:
99.90% of 151,946 fields within 1 px. The Controller Layout screen matches exactly, and the
Container has 491 of 493 fields within 1 px. At 24 sizes the helper's Controller Layout equals
`build_gui`'s own output byte for byte, and the 45 anchors the blend resolves to themselves
come out as the build's sets, byte for byte (`testing/regression/Test-GuiBlendHelper.py`).

**What Windows does.** Only the catalogue's 66 sizes: `ResolutionCatalog.Find`
(`src/patcher/KmrpPatcher.cs`) throws "The selected resolution is not supported." for
any other. `ResolutionChoice` carries per-size fields (the canvas and others) read from the
catalogue, not computed.

**What Windows needs.**
- The blend in C#: a port of `kmrp-guiblend.c`, including the table's two rules (the
  Container's fit and the Controller Layout generator), or the helper itself shipped for
  Windows and run by the patcher.
- `ResolutionChoice`'s fields computed for a size the catalogue lacks.
- The fonts and prompt art of the nearest set.
- A way to ask for the size in the patcher's UI.

`gui-blend.bin` is already built from the shared resources, so the same table serves both.

**Check.** `Test-GuiBlendHelper.py`'s cases against the C# output, byte for byte, then one
unlisted size in play.

**Done on Windows, 2026-09-30.** `src/patcher/GuiBlend.cs` is the helper's C#, step for step,
and the installer carries the table gzipped (`Kmrp.guiblend`, `build_kmrp.ps1` step 4a). A
size the catalogue lacks installs the nearest set (by height, then shape, as `kmrp-mac.sh`
picks it) with its `.gui` files replaced by the blend; `ResolutionChoice.ForSize` computes the
five map fields with the catalogue's own formula (`tools/analyze_resolution_guis.py`), which
all 66 listed rows equal. The patcher's third step lists this display first and ends with
"Custom size…", which takes any size the sets reach and says which heights they reach at a
shape they do not. `Test-GuiBlendHelper.py` runs on Windows too (the helper built with LLVM
clang through `native_helpers.py`) and requires the installer's own blend, through its
`--derive-gui`, to equal the helper's byte for byte; it did at 369 sizes, 300 of them random,
and both refused the same 7 (2026-09-30, before the badges below).

*And found doing it:* the nearest set's controller badges are drawn for that set's buttons and
came out stretched on the blended ones, up to 1.86 times as wide as tall at 3440x1400, on both
platforms. Since table version 3 both installers draw every badge again for its blended button,
and the HUD's button-row boxes from the blended HUD, byte for byte with the build's
(`macos-changes-from-windows.md`, items 1 and 2). Not yet played at a blended size.

## 3. Controller badges and the Container (shared build code)

**What changed** (2026-09-30, `CHANGELOG.md`, *Fixed*). Two changes to shared build code:

- **The badge measurement.** The prompt generator measured captions with the font's
  `spacingR` scaled by `texturewidth`. That is 10x too much at 3024x1964, so every badge sat
  twice its designed gap from its words, and on long captions on the text. It is now
  `spacingR x 100`, as the engine measures.
- **The Container's buttons.** `container.gui`'s buttons, title, list and panel are widened
  by exactly what "Switch To Give Item" and its badge need, in the 45 sets that were short.

Both are in shared code: `tools/build_controller_prompt_textures.py` and
`tools/prepare_universal_resources.py`.

**What Windows needs.** Nothing written. The next Windows build's resources carry both. The
patcher's `ControllerPromptGenerator` reads the corrected `spacing` from each set's
`kmrp_prompts.txt`, and skips the new `widened` line, as it skips any line it does not know
(read from its parser; not run).

**Check.** On a Windows build made from these resources, with a pad:
- the Gameplay screen's Controller Layout entry, and a Container at 3440x1440 and 1920x1080;
- each badge about its own radius x 0.55 from its words;
- the Container's Square beside "Switch To Give Item", not on it.

## 4. Controller Layout caption boxes (shared build code)

`tools/build_controller_layout.py`'s `RENDER_FACTOR` went from 0.92 to 1.04 with the
corrected measure (item 3). The boxes played at 3440x1440 grow by 7 to 9 px, and those at
3024x1964 lose 18 to 32. **Check** the Controller Layout screen at 3440x1440 on Windows:
every caption on one line.

## 5. `kmrp-controller.ini` on restore (a doc fix)

[`controller-rumble.md`](controller-rumble.md) says Restore leaves the file in place.
`KmrpPatcher.cs` deletes it when it is unchanged and keeps it when edited, the manifest's
usual rule. Its own comment says so, and so does the restore loop of the controller
component, read 2026-09-30. The Mac installer does the same since 2026-09-30. Correct the
document, not the code: removing an untouched default is the rule every other file follows.
**Done 2026-09-30**: `controller-rumble.md` says so, with the correction kept visible.

## 6. Skill icons enlarged with the Skills rows

The Skills tab's rows grow to `42s`. The eight `isk_*` icons are 32x32 textures the engine
draws one texel per pixel, so at 3024x1964 a 32 px icon sat in a 115 px row.
`src/patcher/AbilityIconGenerator.cs` now writes them at `round(32s)`, capped at 64 (commit
`7d603c8`, `CHANGELOG.md`, *The skill icons grow with the Skills rows*). The Mac helper
matches it byte for byte (`Test-AbilityIcons.py`, ten heights), and it was seen on the Mac at
1512x982. **Check** the Skills tab on Windows at 1920x1080 (48 px) and 3440x1440 (64 px).

## 7. HD item icons normalised to the game's own framing

The HD Icon Pack's pictures fill more of their canvas than the game's own icons, so items
overflowed their slots. The resource build now sizes each picture to 39/64 of its canvas,
centred (`ICON_PICTURE_SPAN` and `frame_icon` in `tools/prepare_universal_resources.py`,
commit `7d603c8`). It was seen on the Mac at 1512x982: the Jedi Knight Robe's sleeves sit
inside its hex frame instead of past it. **Check** the inventory and equipment screens on
Windows against a build without it.

## 8. Row frames, tutorial icons and `tutorial.2da` made at install

The four `lbl_hex*` row frames, the thirteen `tut_*` tutorial icons and `tutorial.2da` are
made from the player's own game at install. The package no longer carries anything taken
from the game (commit `7c52a84`). `src/patcher/GameArtGenerator.cs` is the Windows side, and
the Mac's `kmrp-gameart.c` matches it byte for byte (`Test-GameArt.py`). Only the Mac
installer has run it. The same commit makes the resource build stop when a font has no atlas
of ours, where it shipped the game's own atlas beside the scaled `.txi`; every font has one
(`assets/hd-fonts`), so the package does not change. **Check** a Windows install: the files
present, the same sizes as before, the progress bar's "Installing row frames and tutorial
icons…" stage, and the patcher's restore removing them.

## 9. The 17 Mac resolutions in the catalogue

`GROUPS["macOS"]` in `tools/prepare_universal_resources.py` adds the Mac displays' sizes,
native and half, derived from High Resolution Menus (`Test-ResolutionDerivation.py`,
commit `7d603c8`). `ResolutionCatalog` now expects 66 entries, and the Windows launcher lists
them under **macOS**. **Not yet run on Windows**: **check** that the launcher shows them and
that one installs.

## 10. The granted popup's rows

**What the Mac does** (2026-09-30, `macos/patches/kmrp-layout/granted_popup.cpp`). The popup
that lists what a level brought ("You have been granted the following feat(s) this level.",
and the Force-power version; `skillinfo.gui`), at character generation and on level-up. Seen
at 3024x1964, measured on screenshots before and after the change:

| | Before | After |
| --- | --- | --- |
| row pitch, for 115-px rows | 141 px (26 spread per row) | 125 px, 14 px between frames |
| hex frame beside a 111-px text frame | 97 px tall | 111 px tall |
| first letter from the text frame's left line | 2 px | 14 px |
| panel height (4 feats) | 941 px | 876 px, same centre |

Three changes, for this popup's rows only:

1. **The rows' spacing.** The list box shares out the height it has left over between its
   visible rows. `LB_SKILLS` holds four rows with 105 px to spare at 3024x1964; the inventory,
   the same kind of list, spreads 8 to 10% of a row (15 px on 153-px rows at 3024x1964, 7 on 76
   at 1512x982, 7 on 84 at 1920x1080, 10 on 112 at 3440x1440, from each set's
   `inventory.gui`). After the popup's fill hands its rows to the list, the list goes back to
   the file's extent, which gives the engine's own count of rows that fit; its height is then
   cut to that many rows, or as many as were granted if fewer, at a pitch of the row plus an
   eleventh of it. OK moves up by the height taken off, and the panel loses it too, keeping
   its centre. The file's extents are kept at the first fill, so every fill starts from them.
2. **The hex.** The row's hex frame (`lbl_hex_3`), its highlight and the icon are drawn in a
   square as tall as the row, and the texture's hex fills 131 of its 153 rows. The squares grow
   by a seventh of the row, about the same centre and 1/40 of the row lower, so the hex spans
   the text frame.
3. **The text.** The text's rect, the text frames' inner rect, is inset by an eighth of the
   row on each side.

Every size is taken from the row's height (`42s`), so it holds at any resolution. Seen in play
at 3024x1964 only, with four feats; a list long enough to scroll has not been seen.

**Where, on the Mac.** Two calls go through the layout patch's near page:

| Mac | What |
| --- | --- |
| `0x10028E9CA` | the popup's fill; its `call 0x1004A9BE6` (`CSWGuiListBox::AddControls`) at `0x10028EA4F` is replaced |
| `0x10022F228` | `CSWGuiInGameSkillEntry::SetExtent`; its last call, `call 0x1004A3D4C` (the text's rect) at `0x10022F321`, is replaced |
| `0x1005A9E18` | the popup's vtable; the GUI manager keeps the one popup at its `+0x128` |
| `+0x80`, `+0x5B8`, `+0x8` | the list (`LB_SKILLS`), OK and the panel's extent |
| `+0x7F8`, `0x3B8` apart | the ten rows |
| `+0x228`, `+0x2B0`, `+0x338` | a row's hex, highlight and icon squares; `+0x110` its text |
| `+0x344`, `+0x350`, `+0x368`, `+0x378` | the list's inner height, row count, row height and visible count (short) |

**What Windows needs.** The same three changes in the executable patch. The Windows row's
`SetExtent` is the function holding the icon's `42` at `0x006AB8EE`
([`reverse-engineering/inventory-item-rows.md`](../reverse-engineering/inventory-item-rows.md)),
and the row's initialiser sets its height at `0x006ACB20`. Not yet read: that function's start
and its call giving the text its rect, the popup's fill and its call to the list, and the
Windows offsets above. The title's string refs (`0xA510`, `0xA511`, `0xA512`), set right after
each fill on the Mac, lead to the fill's callers.

**Check.** New game, Custom, the Feats step, Recommended, then OK: the popup at 3440x1440
and one 16:9 size. Its rows should sit as the inventory's do, each hex as tall as its text
frame, the text clear of the frame's left line, and the popup centred. Level up with more
than four feats or powers: the list should scroll, four rows high.

## 11. The header's smoke fades out before its bottom edge

**What the Mac does** (2026-09-30, `macos/installer-app/main.m`, `BottomFade`). The patcher's
smoke (`LightField`) is drawn only inside the header strip: `ComposeFrame` renders it into a
bitmap exactly ClientWidth x the header's height, on the reasoning in `OnPaint` that "below
it the card covers everything anyway". The card does not cover the window's margins beside
it, and in the columns where the plume reaches furthest (the front billows as low as 0.58 of
the header, and a low `colReach` leaves the wisps below it thick) the smoke was still dense at
the header's bottom, so it stopped on a straight line there. Seen on the Mac's port of the
same code (reported 2026-09-30). The Mac multiplies the smoke's emission, and each mote's
brightness, by a smoothstep that runs from 1 at 70% of the header's height to 0 at its bottom.
Measured on the window afterwards: the margins' brightness falls from 17.8 to the window's navy
(13.3) about 45 pixels above the edge, with no step at it.

**What Windows needs.** The same factor in `LightField`: in `RenderSmoke`, on
`field[y * w + x] = dens * lit * Exposure`; in `RenderMotes`, on
`float bright = fade * m.Seed * LightAt(mx, my) * MoteAlpha`, with `my` as `v`. **Not yet
seen on Windows**: whether the line shows there depends on where the plume happens to reach,
but nothing in the code prevents it.

**Check.** Watch the Windows patcher's margins beside the card for a minute: no straight edge
where the header ends.

**Built, 2026-09-30.** `LightField.BottomFade` in `src/patcher/KmrpPatcher.cs`, the Mac's
smoothstep over the lowest 30% of the header, on the smoke's emission in `RenderSmoke` and on
each mote's brightness in `RenderMotes`. Not yet watched.

