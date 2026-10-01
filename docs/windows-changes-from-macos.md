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
already has), and the commits adding items 11 to 15. Pull request #24 (`45b7457`, `2245026`,
merged 2026-10-01) needs nothing on Windows: KMRP as one KPM patch on FTD's current patches is
the Mac's install; the dialogue reply list's stretch (`dialogue_replies.cpp`) is Windows'
`.klb` already; the stick fix answers the Mac engine's own normalising of the axes, which
Windows' engine does not do; and KPM's runtime, rebuilt from the new submodule commit, was
byte for byte the same.

**Merged and built on 2026-09-30.** The branch up to `3fd22ad` was merged into `master` and
the Windows installer built from it (`04C2DA20…`), with the resources made again from the
merged build code. Items 2, 5 and 11 were done on Windows the same day; the other direction,
what the Mac now needs from that work, is
[`macos-changes-from-windows.md`](macos-changes-from-windows.md). **Merged again the same
evening**, up to `d672b8d` (items 12 to 15), and built as `97BEA480…` with the resources made
again: items 12, 14 and 15 are in that build, and item 13 was written for Windows then.

States: **to do** (Windows has nothing yet), **build only** (shared code already changed;
Windows gets it with a build from the merged code and needs a check in play), **built** (in
a Windows build, its automated checks passing; not yet seen in play), **done** (as the Mac
does it, checked as stated), **doc** (a Windows document to correct).

| # | Change | State |
| --- | --- | --- |
| 1 | Message popups fitted to their contents, width and height, centred | **built** (2026-09-30; seen at 3440x1440) |
| 2 | Any resolution, not only the listed ones | **built** (2026-09-30) |
| 3 | Controller badges at their designed distance; the Container's buttons widened | **built** |
| 4 | Controller Layout caption boxes: margin over the corrected measure | **built** |
| 5 | `kmrp-controller.ini` removal on restore | **done** (the document corrected) |
| 6 | Skill icons enlarged with the Skills rows | **built** |
| 7 | HD item icons normalised to the game's own framing | **built** |
| 8 | Row frames, tutorial icons and `tutorial.2da` made at install from the player's game | **built** |
| 9 | The 17 Mac resolutions in the catalogue | **built** |
| 10 | The granted popup's rows: hex as tall as the text frame, text inset, rows spaced like the inventory's | **built** (2026-09-30; seen at 3440x1440) |
| 11 | The header's smoke fades out before the header's bottom edge | **built** (not yet watched) |
| 12 | The journal's quest rows: six to the list, spaced as the inventory's | **built** (2026-09-30) |
| 13 | The Options check boxes' circle and label offset scaled with the resolution | **built** (2026-09-30; seen at 3440x1440) |
| 14 | Lists as tall as whole rows: the Container, the granted popup, character creation's Feats, low-resolution lists | **built** (2026-09-30) |
| 15 | Skill rows as tall as the Feats and Powers rows (`50s`), the skill icons with them | **built** (2026-09-30) |
| 16 | Uninstall after KPM's takeover: removes KPM's runtime too when KMRP is its only patch; a takeover found from any runtime file, not `patch_config.toml` alone | **built** (2026-10-01; `Test-KpmEdition.ps1` Cases 10b and 10c; not run under KPM's window on Windows) |

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

**Built on Windows, 2026-09-30** (`17EE496D…`; the maintainer: "you didnt apply the quit game fixes
we did on macos"). Not in the executable patch after all but in KMRP's module, which every
one of KMRP's KPM patches loads, the core one included: `FitMessageBoxK1`
(`src/controller-native/K1PopupFit.cpp`), a detour with `install = "always"` in
`kotor1.hooks.toml` at `0x006258E2`, `FixMessageLabel`'s epilogue after its last call, with
esi the box. It is `popup_fit.cpp`'s four steps with the same arithmetic, and one more call:
Windows' last call, `0x0040A600`, centres the panel on the screen from its size, so the fit
runs after it and calls it again. The Windows offsets, read from `0x006253A0`:

| Mac | Windows | What |
| --- | --- | --- |
| `+0x8` | `+0x4` | the panel's extent, set through vtable slot 1 (the Mac's `+0x10`) |
| `+0x850` | `+0x67C` | the message list; inner height `+0x298`, tallest item `+0x2B4`, padding (byte) `+0x2C0` |
| `+0x3D0`, `+0x610` | `+0x2F4`, `+0x4B8` | OK and Cancel, shown while bit `0x2` of their `+0x44` is set |
| `+0x238`, `+0x79` bit `0x10` | `+0x1B4`, `+0x64` bit `0x10` | the icon, and whether it is shown |
| `+0xC04` | `+0x970` | the message's top in the file (the saved message extent is at `+0x96C`, the panel's at `+0x95C`) |
| `0x100306B86` | `0x006252F0` | the message rebuild |
| `0x10049DC36` | `0x0040A600` | the last call: the panel centred on the screen |

Seen in play at 3440x1440 in a scratch copy: the Exit Game box ("Do you really want to
quit?") 657x272 px, centred (1719, 720); the character-generation Attributes tutorial
776x413, the Skills tutorial and the Solo Mode prompt fitted and centred. Not seen at a 16:9
size, nor with a text long enough to scroll. All nine Windows suites pass on it, `Test-ControllerSupport.ps1` checking the new hooks against the module's exports and KMRP's patch configurations.

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
| the lists made as tall as whole rows (item 14) | made, not blended: the build's `fit_list_to_rows` on the blend, at the size's own row heights (table version 3 on this branch; 4 since the merge into `master`) |
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
- The blend in C#: a port of `kmrp-guiblend.c`, including the table's three rules (the
  Container's fit, the Controller Layout generator and the row fit of item 14), or the helper
  itself shipped for Windows and run by the patcher.
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
platforms. Since table version 3 on `master` (4 since the merge of items 12 to 15) both
installers draw every badge again for its blended button,
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

The Skills tab's rows grow to `42s` (`50s` since item 15). The eight `isk_*` icons are
32x32 textures the engine draws one texel per pixel, so at 3024x1964 a 32 px icon sat in a
115 px row. `src/patcher/AbilityIconGenerator.cs` now writes them at `round(32s)`, capped at
64 (commit `7d603c8`, `CHANGELOG.md`, *The skill icons grow with the Skills rows*); since
item 15, `round(32s x 50 / 42)`, so they keep their proportion to the taller rows. The Mac helper
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

Every size is taken from the row's height (`42s` then; `50s` since item 15), so it holds at
any resolution. Seen in play
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

**What Windows needs.** Since item 14 the first change comes from `skillinfo.gui` itself: the
build makes the list as tall as its rows at the same pitch, so a Windows build has the spacing
for a full popup. Still Mac-only: the cut to fewer rows when fewer are granted, the hex and
the text. Those two, and that cut, in the executable patch. The Windows row's
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

**Built on Windows, 2026-09-30** (`17EE496D…`), in KMRP's module as item 1 is:
`src/controller-native/K1GrantedPopup.cpp`, two `always` detours. The Windows side, read
from the executable:

| Mac | Windows | What |
| --- | --- | --- |
| `0x1005A9E18` | `0x00757940` | the popup's vtable (constructor `0x006CE7E0`) |
| `+0x80`, `+0x5B8`, `+0x8` | `+0x64`, `+0x484`, `+0x4` | `LB_SKILLS`, `BTN_OK` and the panel's extent (`LBL_MESSAGE` is `+0x344`) |
| `+0x7F8`, `0x3B8` apart | `+0x648`, `0x310` apart | the ten rows (row constructor `0x006ACC50`) |
| `+0x228`, `+0x2B0`, `+0x338`; `+0x110` | `+0x1B4`, `+0x228`, `+0x29C`; `+0xD0` | a row's hex, highlight and icon (controls, extent at `+0x4`); its text |
| `+0x344`, `+0x350`, `+0x368`, `+0x378` | `+0x298`, `+0x2A0`, `+0x2B4`, `+0x2C4` | the list's inner height, item count, row height and rows that fit (short), from `OrganizeControls` (`0x0041B140`) |
| `0x10028E9CA`, `call` at `0x10028EA4F` | `0x006CDFC0`, `call 0x0041C1D0` at `0x006CE0AB` | the fill, and its hand-over of the rows to the list |
| `0x10022F228`, last call at `0x10022F321` | `0x006AB8E0`, last call at `0x006AB9D8` | the row's `SetExtent`, and its call giving the text its rect |

`GrantedPopupFilledK1` runs after the fill's hand-over (`0x006CE0B0`), with esi the list: it
remembers the popup and fits the list, OK and the panel. The list's `SetExtent`
(`0x0041BF80`) lays the rows out again (`OrganizeControls`), so the first fill's rows are
refitted too; the Mac sets its popup before the hand-over instead, one hook more.
`GrantedRowTextK1` runs before the row's last call (`0x006AB9D5`, with esi the text and eax its
rect) and, for this popup's rows only, grows the three squares and insets the rect. Seen in
play at 3440x1440: "The following feat(s) have been recommended." with one feat, the list cut
to its one row, OK under it, the panel fitted and centred, the hex as tall as the text frame
and the text 13 px inside the frame's left line. Not seen with four or more rows, nor on
level-up.

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

## 12. The journal's quest rows (shared build code)

**What changed** (2026-09-30, `CHANGELOG.md`, *Fixed*; reported from play on the Mac at
3024x1964). A list box shares the height its rows leave over between them
(`CSWGuiListBox::OrganizeControls`, Windows `0x0041B140`): with `inner` the list's height
less twice its border, `n = inner // row` rows show, each `(inner - n * row) // n` from the
next. A quest row is `journal.gui`'s `LB_ITEMS` template height times the row scale (the
`.kfs` hook at `0x00417992`). Every set kept upstream's template of 78, twice vanilla's 39,
so four rows fit and each gap was 22% of a row, at every size from 720p up:

| Set | Before: rows, row, gap | After: template, row, gap |
| --- | --- | --- |
| 1920x1080 | 4 x 117 px, 25 px | 57, 6 x 86 px, 8 px |
| 3440x1440 | 4 x 156 px, 34 px | 58, 6 x 116 px, 10 px |
| 3024x1964 | 4 x 213 px, 47 px | 58, 6 x 158 px, 15 px |
| 3840x2160 | 4 x 234 px, 52 px | 58, 6 x 174 px, 17 px |

The inventory's gaps are 8 to 10% of its rows (15 px under 153 at 3024x1964), and vanilla's
journal showed six rows at 640x480. The resource build (`tools/prepare_universal_resources.py`)
now calls `fit_rows_to_list` (`tools/scale_listbox_padding.py`) on each set's `journal.gui`:
the largest template whose six rows leave an eleventh of a row between each, from that set's
own list. Only `PROTOITEM`'s height changes. Across the 66 sets the gaps come out at 8 to 11%
of a row.

**What Windows needs.** Nothing written. The row arithmetic is the same on both (the Mac's
row code is ported from Windows' `.kfs` hook: `macos/patches/kmrp-layout/resolution_sizes.cpp`),
so the next Windows build's `journal.gui` files give the same rows. Seen in play on the Mac
only.

**Check.** On a Windows build made from these resources, at 3440x1440 and 1920x1080: the
journal's Active and Completed quests show six rows, as evenly spaced as the inventory's,
with each quest name centred in its frame.

**Built on Windows, 2026-09-30** (`97BEA480…`). `Test-GeneratedGuiGeometry.py` recomputes the
engine's layout of every set's journal and passes on the 66 sets the Windows build made. Not
yet seen in play on Windows.

## 13. The Options check boxes

**What the Mac does** (2026-09-30, `macos/patches/kmrp-layout/resolution_sizes.cpp`,
*Options check boxes*). The Options screens' toggles (Feedback's list, Auto-pause, Gameplay,
Graphics, Advanced Graphics, Mouse, Advanced Sound) are `CSWGuiOptionsCheckbox`. Its
`SetExtent` puts the circle's four state images in a fixed 25x25 square at the control's
left, 2 px below its middle, and the label 30 px in, whatever the resolution
([`../reverse-engineering/listbox-geometry.md`](../reverse-engineering/listbox-geometry.md),
*Checkbox rows beside a left scrollbar*, read the same function on Windows). At 3024x1964 the
toggles are 117 to 164 px tall, so the circle was about a sixth of them; vanilla drew it in
43- and 60-px ones. The Mac replaces the function with the same layout at 25s, 30s and 2s,
`s = max(1, H / 720)`:

| | 1920x1080 | 3024x1964 |
| --- | --- | --- |
| circle | 38 px | 68 px |
| label from the left edge | 45 px | 82 px |
| below the middle | 3 px | 5 px |

Only this class's objects use it: one vtable, built by the Options screens' code. The party
selection and HUD controls of the same `.gui` type are other classes. Checked against the
game binary by `Test-KmrpLayoutPatch.py`; not yet seen in play.

**What Windows needs.** The same three numbers in `0x006DE000`: the square's `0x19`, the label
offset `0x1E` and the `+2`, as `(int)Math.Round(base * s)` like the other sizes
`ResolutionPatch.Apply` writes. Where an immediate is too short for the scaled value, the
function needs relocating, as the stack-count label was (`.ksc`).

**Check.** At 3440x1440 and 1920x1080: Options, then Feedback and Gameplay. Each circle is
about 0.6 of its row's height, centred on the row, with its label clear of it.

**Built on Windows, 2026-09-30** (`97BEA480…`). `ResolutionPatch.Apply` writes the three numbers
into `0x006DE000` (`src/patcher/KmrpPatcher.cs`, `CheckboxSquareOffset` and the rest;
[`../reverse-engineering/listbox-geometry.md`](../reverse-engineering/listbox-geometry.md),
*The circle and label scaled*). The square's `0x19` is an imm32 and the drop's `+2` a signed
byte, both written in place. The label's `0x1E` is two signed bytes, `sub ecx` and `add eax`
at `0x006DE08E`, and `30s` passes 127 above 3048 px tall, so rather than relocate the
function into a section, or cap the scale as the map markers do, those six bytes become a
jump into the 15 bytes of padding after the function's `ret 4` (`0x006DE0D1`), where the two
operations take 32-bit operands and jump back. Read back from the installer's `--apply`: 25,
2, 30 at 800x600; 38, 3, 45 at 1920x1080; 50, 4, 60 at 3440x1440; 75, 6, 90 at 3840x2160;
300, 24, 360 at 15360x8640. KOTOR Patch Manager installs carry the new sites by themselves
(`--kpm-sites`): `Test-KpmEdition.ps1` requires the data file to give the standalone's
executable byte for byte, and passed. `build_binary_inventory.py` finds all four runs
documented.

*Found in play, and fixed for both platforms:* at 3440x1440 the Gameplay, Auto-pause and
Graphics circles were 50 px in 120-px toggles, as intended, but the Feedback list's circles
overlapped, 50 px circles 44 px apart. Its rows are check boxes too, built at the height of
`LB_OPTIONS`'s row template, 43 in every set, and the runtime row scale that grows text rows
does not reach them, so they stayed 43 px at every resolution. The Mac's patch has the same
effect there (68-px circles in 43-px rows at 3024x1964; not seen in play on the Mac). The
resource build now scales that template as the row hook scales a text row's, `round(43s)`
(`tools/scale_listbox_padding.py`, `FEEDBACK_LIST` and `scale_row_template`): 86 px at
3440x1440, so the circle keeps vanilla's 25 of 43, and ten rows fit the list at every scaled
size for its nine options (seven at 1920x540, as before). `Test-GeneratedGuiGeometry.py` checks
it in the 66 sets; the Mac gets it with its next build
([`macos-changes-from-windows.md`](macos-changes-from-windows.md), item 11). Seen in play at
3440x1440 after the fix: see `CHANGELOG.md`.

## 14. Lists as tall as whole rows (shared build code)

**What changed** (2026-09-30, `CHANGELOG.md`, *Fixed*). The list box shares the height left
under its last whole row between its rows (item 12). Rows sized in code (items `56s`, skills and
feats `50s`) sit in lists the upstream layouts scale with the screen, so each list's gaps
depended on what was left over. An audit of every multi-row list at the 66 sets found:

| List | Before, at 3024x1964 | Sets past 13% | After, at 3024x1964 |
| --- | --- | --- | --- |
| `container.gui` `LB_ITEMS` | 4 x 153 px, 34 apart | 64 | 4 x 153 px, 13 apart; panel 85 px shorter, same centre |
| `skillinfo.gui` `LB_SKILLS` (granted popup) | 4 x 115 px, 26 apart | 64 | 4 x 136 px (item 15), 12 apart; OK and panel with it |
| `ftchrgen.gui` `LB_FEATS` | 7 x 136 px, 19 apart | 39 | 7 x 136 px, 12 apart; list 51 px shorter |
| store, level-up powers, equipment, upgrade items, Abilities | within the inventory's range | up to 11, below 1024x768 and at 1920x540 | shortened there |

`tools/scale_listbox_padding.py` (`ROW_LISTS`, `fit_list_to_rows`) makes each as tall as whole
rows, `row // 11` apart: in the two popups the controls below move with the list and the panel
keeps its centre; a full-screen list is only shortened, and only where a gap passes an eighth
of a row. All 66 sets now keep 7.5 to 12.5%, the inventory's range. Each set's
`kmrp_prompts.txt` records every change on a `fitted` line, which the Windows installer skips
as it skips `widened` (read from its parser; not run).

**What Windows needs.** Nothing written. The next Windows build's sets carry it.

**Check.** On a Windows build at 3440x1440 and 1920x1080: a footlocker (the Container), the
granted popup at character creation (Custom, Feats, Recommended, OK) and the Feats step
itself. Rows as evenly spaced as the inventory's; the Container's and the popup's buttons
under their lists, the panels centred.

**Built on Windows, 2026-09-30** (`97BEA480…`). `Test-GeneratedGuiGeometry.py` checks every fitted
list in the 66 sets the Windows build made and passes. For a size with no set, the Windows
installer fits the lists itself: `src/patcher/GuiBlend.cs` reads the row fits from the blend
table (version 4 since the merge, with the badges of item 2) and applies `fit_list_to_rows`
as the helper does (`FitRows`); `Test-GuiBlendHelper.py` requires it to equal the helper
byte for byte, and it did at 369 sizes. Not yet seen in play on Windows.

## 15. Skill rows as tall as the Feats and Powers rows (shared code)

**What changed** (2026-09-30). The Abilities screen shows Skills, Feats and Powers in one list.
With skill rows at `42s` and chain rows at `50s`, one tab stayed loose in 11 sets (Skills 8 to
11 px from 800x600 to 1470x956; Feats and Powers 10 px at 1920x540 and 1024x576), and fitting
the list to either took a row off the other. Skill rows are now scaled from 50:

| | Windows | Mac |
| --- | --- | --- |
| row height and icon box | `RowSizeGroups`: `{ 42, 50, 0x002AB8EF, 0x002ACB20 }` (was `{ 42, 42, ... }`) | `resolution_sizes.cpp`, `AddListRows` |
| skill icons | `AbilityIconGenerator.SkillTargetSize`: `round(32s x 50 / 42)`, capped at 64 | `kmrp-abilityicons.c`, the same, byte for byte |

At 3024x1964 the rows are 136 px (were 115), so the Skills tab shows five skills at a time
where it showed six; the icons stay at the 64 px cap there. At 1920x1080: 75 px rows, 57 px
icons (were 63 and 48).

**What Windows needs.** Nothing more: both changes are in the shared C#. A Windows build.

**Check.** At 3440x1440 and 1920x1080: the Abilities screen's three tabs, rows of one height
and the same spacing; the skill icons centred in their hexes; the granted popup's rows.

**Built on Windows, 2026-09-30** (`97BEA480…`). The installer's `--apply` writes 50, 75, 100, 150
and 600 at the skill rows' two sites at 800x600, 1920x1080, 3440x1440, 3840x2160 and
15360x8640. The skill icons met `master`'s picture inside its frame (2026-09-29) in the
merge: the picture grows with the `50s` box too (`CHANGELOG.md`, *The skill icons sit inside
their frames*, and [`macos-changes-from-windows.md`](macos-changes-from-windows.md), item
10), and `Test-AbilityIcons.py` passes on Windows with that rule, 2,704 icons at ten heights
byte for byte. Not yet seen in play.

## 16. Uninstall after KotOR Patch Manager has taken KMRP's install over

**What changed** (2026-10-01, `macos/kmrp-mac.sh`; asked for by the maintainer: "tell windows
to do same"). Two changes to the uninstall after a takeover, which Windows' `KpmEdition.cs`
`Restore` handles as the Mac did until now.

**1. KMRP as KPM's only patch: the whole install goes.** Until now, an uninstall after a
takeover removed KMRP's own files and asked the player to untick KMRP in KPM and press Apply.
With KMRP the only patch in KPM's list, that Apply removes KPM's whole runtime
(`PatchRemover.RemoveAllPatches`), so the uninstall now does it itself and leaves the untouched
game. With another patch in KPM's list, KMRP's module cannot be taken out without KPM applying
the rest again, so that case is as before.

| | Mac (`kmrp-mac.sh`) | Windows (`KpmEdition.cs`) |
| --- | --- | --- |
| KMRP the only patch | `kpm_holds_only_kmrp`: `patch_config.toml`'s ids are all `kmrp` and `patches/` holds only `kmrp.dylib` | to write: the ids in `patch_config.toml` are only KMRP's four edition patches, and the patches folder holds only their modules |
| then | `restore_from_manifest`: KMRP's own files first, then `kpm_remove` with KMRP's own backup of `KOTOR_Exe` (the untouched game), deleting `KotorPatcher.dylib`, `patch_config.toml`, `patches/`, `kpm_install_state.json`, `addresses.db` and KPM's `KOTOR_Exe.backup.*` | to write: what `PatchRemover.RemoveAllPatches` does on Windows: the executable from the backup, KPM's runtime, its proxy, `addresses.db` and its backups |
| otherwise | as before: "Untick KMRP in KPM and press Apply to finish." | as now |

KPM's `settings.json` still lists `kmrp` among its ticked patches afterwards; with
`kmrp.kpatch` gone from its folder (removed with the rest), KPM no longer shows it.

**2. A takeover found from any runtime file.** On the Mac, KPM 0.7.1's Apply over KMRP's
install wrote `patch_config.toml` and `kmrp.dylib` byte for byte as KMRP had (the same
KPatchCore, the same patch), while `KOTOR_Exe` (re-signed), `KotorPatcher.dylib` (KPM's own
build) and `kpm_install_state.json` changed. `handed_over` compared `patch_config.toml` alone,
found it unchanged, and the uninstall took out the patch list and `patches/` and left KPM's
runtime loading nothing; the game had to be put back by hand (2026-10-01, the maintainer's
own install; the files kept in `~/KMRP-mac-backup/2026-10-01-kpm-takeover`). `handed_over`
now counts a takeover when any runtime file KMRP recorded is still there and differs from what
it wrote, except a `KOTOR_Exe` back to the untouched game (KPM's Remove, not a takeover).
Windows' `ConfigChangedSinceInstall` compared `patch_config.toml` alone too (until 2026-10-01:
below). **Not checked on
Windows** whether KPM's Apply writes it differently there; KMRP's own `swkotor.exe`, KPM's
`KotorPatcher.dll` and proxy, and `kpm_install_state.json` are the same kind of evidence.

**Also seen on the Mac the same night.** KPM's Apply empties the patches folder and puts back
only each patch's module, so `kmrp-sdl3.dylib` there was deleted and the controller fell back
to Apple's GameController. SDL now goes beside the game and the module looks there after its
own folder, as Windows already does (`K1ControllerBackend.cpp`, `KpmEdition.cs`'s
`SupportFiles`). Windows needs nothing for this.

**What Windows needs.** Both changes in `KpmEdition.cs` `Restore`.

**Built on Windows, 2026-10-01** (`src/patcher/KpmEdition.cs`):

| Mac | Windows |
| --- | --- |
| `handed_over`: any recorded runtime file still there and changed, except `KOTOR_Exe` back to the untouched game | `RuntimeChangedSinceInstall`, replacing `ConfigChangedSinceInstall`: any `file` record `IsRuntimeRecord` names (the runtime, the config, the state file, the proxy, KMRP's backup, the modules) still there and changed, except `binkw32.dll` back to the game's own, which KPM's removal does (`KProxyInstaller.Uninstall`); the executable is not a `file` record on Windows |
| `kpm_holds_only_kmrp`: the config's ids all `kmrp`, `patches/` only `kmrp.dylib` | `KpmHoldsOnlyKmrp`: the ids in `patch_config.toml` and `kpm_install_state.json`'s `InstalledPatches` (which also names patches without a module) all among KMRP's four, `patches\` only their `.dll` files; and the untouched executable recoverable: KPM's newest backup (by its `yyyyMMdd_HHmmss` name, as KPM finds it) is the untouched file, or with no backup the executable is the untouched file or has only the 4 GB flag. Otherwise the runtime is left, as before |
| `kpm_remove` with KMRP's own backup | `RemoveKpmRuntime`, after the `.kpatch` files and before KMRP's own files: the executable copied back from KPM's backup and verified, that backup and its `.json` deleted, or else the 4 GB flag cleared and verified; `patch_config.toml`, `KotorPatcher.dll`, `addresses.toml`, `addresses.db`, `sqlite3.dll` and `kpm_install_state.json` deleted whatever their contents, as KPM 0.7.1's `PatchRemover.RemoveAllPatches` lists them, and KMRP's four modules; the proxy deleted when `binkw32Hooked.dll` is still the game's own, so `UndoEngineChanges` moves that back. KPM's app files, should it run from the game folder, are left |

A reinstall that installs for KPM over a takeover keeps KPM's runtime even with KMRP alone in
it (`Install` passes `keepKpmRuntime`), since that install puts no runtime in its place; this
is what `Test-KpmEdition.ps1` Case 10 already checked. The final message is "The original game
files and settings have been restored." when the whole install went.

`Test-KpmEdition.ps1`, against stand-ins: **Case 10b**, KPM's Apply laid out as the Mac saw it
(the config byte for byte, `KotorPatcher.dll` and the state file changed, KMRP's backup under
KPM's name, an `addresses.db`), then restore: the untouched executable back from the flagged
one, the game's own `binkw32.dll`, and no file of KPM's or KMRP's left. **Case 10c**, another
patch in the config and `patches\`, then restore: KPM's runtime, the other patch and the
flagged executable exactly as they were, KMRP's data file gone. Not run with KPM's own window
on Windows.

**Check.** The two cases on a game KMRP installed, each after pressing Apply in KPM:
KMRP alone in KPM, then uninstall: the untouched `swkotor.exe` (`761F9466…` or the Steam
build) and no KPM file left; KMRP and another patch, then uninstall: KPM's runtime and the
other patch as they were, and the message to untick KMRP. `Test-MacInstaller.py`'s round 6
does both on the Mac against a stand-in.
