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

**None of this is on `master` yet.** The shared code named below (the resource build, the
patcher's generators, the tests) was changed on the `macos` branch. On 2026-09-30 that branch
was 9 commits ahead of `master`, touching 34 files outside `macos/` and `third_party/`
(`git diff --stat master..macos -- . ':!macos' ':!third_party'`). A Windows release has
none of it until `master` takes those commits. Everything marked **build only** is written
and needs only that merge, a Windows build and a check in play.

States: **to do** (Windows has nothing yet), **build only** (shared code already changed;
Windows gets it with a build from the merged code and needs a check in play), **doc** (a
Windows document to correct).

| # | Change | State |
| --- | --- | --- |
| 1 | Message popups fitted to their contents, width and height, centred | **to do** |
| 2 | Any resolution, not only the listed ones | **to do** |
| 3 | Controller badges at their designed distance; the Container's buttons widened | **build only** |
| 4 | Controller Layout caption boxes: margin over the corrected measure | **build only** |
| 5 | `kmrp-controller.ini` removal on restore | **doc** |
| 6 | Skill icons enlarged with the Skills rows | **build only** |
| 7 | HD item icons normalised to the game's own framing | **build only** |
| 8 | Row frames, tutorial icons and `tutorial.2da` made at install from the player's game | **build only** |
| 9 | The 17 Mac resolutions in the catalogue | **build only** |

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

It does nothing when the text needs the scrollbar. Seen in play at 3024x1964 on 2026-09-30:
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
installer has run it. **Check** a Windows install: the files present, the same sizes as
before, and the patcher's restore removing them.

## 9. The 17 Mac resolutions in the catalogue

`GROUPS["macOS"]` in `tools/prepare_universal_resources.py` adds the Mac displays' sizes,
native and half, derived from High Resolution Menus (`Test-ResolutionDerivation.py`,
commit `7d603c8`). `ResolutionCatalog` now expects 66 entries, and the Windows launcher lists
them under **macOS**. **Not yet run on Windows**: **check** that the launcher shows them and
that one installs.

