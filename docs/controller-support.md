# Optional Xbox controller support

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It records the exact
> reviewed sources, installed files, hook sites, prompt investigation, and the
> difference between automated verification and play-testing.

**Kind: reference; structurally verified, not play-tested.**

KMRP can install **KPM – Xbox Controls for KOTOR 1 1.2** by Saul0097 as an
opt-in Advanced Settings component. It is an XInput-to-existing-input adapter,
not native engine controller support: the module feeds KOTOR keyboard, mouse,
and existing GUI events while a small KOTOR Patch Manager runtime installs six
in-memory detours.

## Sources and build identity

| Component | Exact source | Local output |
| --- | --- | --- |
| Controller module | `scopeking0117-alt/KPM-Xbox-Controls-K1`, commit `78e7eaa3b9554ec0e6732f749424dc916f3a1895`, plus KMRP prompt, cursor-default, and movie-input patch | `kmrp-controller.module`, 130,560 bytes, SHA-256 `D006428E382A76D4CFA0DD620C2BB873B38371A0C0954DE331C1032F66069E25` |
| Hook runtime | `LaneDibello/Kotor-Patch-Manager`, commit `7d53e52f55622a48ab97001c2680fd9fb59c8f98` | `kmrp-controller-runtime.asi`, 338,432 bytes, SHA-256 `F5CF2A21E4C28DA95CD8DAAF2704F871A6105616BFE250361929C61BCDB43B45` |

Both outputs are 32-bit C++17 MSVC static-runtime builds. The controller module
imports only `USER32.dll` and `KERNEL32.dll`; the hook runtime imports only
`KERNEL32.dll`. The `.module` suffix prevents the ASI loader from loading the
controller a second time as a standalone plugin.

The runtime originally assumed its filename was `KotorPatcher.dll`. KMRP's
reproducible source change, preserved in
`third_party/Included/KPM-Xbox-Controls-K1-1.2 by Saul0097/KMRP-RUNTIME-PATCH.diff`,
finds the module containing `SelfModuleDir` by address instead. A named-executable
launch proved the unmodified build loaded only the runtime; the corrected build
loaded both files.

`KMRP-CONTROLLER-PROMPTS-PATCH.diff` records the second reproducible source
change. It preserves the visible cursor at startup, tracks XInput connection,
and changes existing button normal and highlighted fills through
`CSWGuiBorderParams::SetFillImage` at preferred-image VA `0x00414C00`; those
border parameters begin at `CSWGuiButton + 0x80` and `+ 0xF4`.
Each button is addressed by its verified embedded-object offset in the concrete
panel class. Those offsets and the border layout were read from the K1 1.0.3
address database and checked against the existing controller action paths.

An earlier unreleased build incorrectly passed GUI GFF list indices to
`CSWGuiPanel::GetControl`. Runtime control-array order is not guaranteed to match
GFF list order. On 2026-09-06 this caused an access violation in
`SetFillImage` at `swkotor.exe+0x14C3E` when the live game opened Save/Load with
controller mode active. Windows event 1000 and the matching crash dump identified
the exact call. That lookup was removed; the corrected module uses only the
class-layout offsets below.

From an x86 MSVC native-tools environment, the controller output is reproduced
from the patched source with:

```text
cl /nologo /Brepro /O2 /EHsc /MT /LD K1XboxControls.cpp K1XboxControlsXInput.cpp /link /Brepro /DEF:exports.def /OUT:kmrp-controller.module /INCREMENTAL:NO
```

Two consecutive builds produced the same 130,560-byte SHA-256 above. The linker
retains the upstream export-library name and warns that it differs from the
`.module` output name; the PE export table and all twelve exports are unchanged.

Both components trace back to one MIT licence. KOTOR Patch Manager is MIT, and
the controller module is a derivative of **ExpandedKeyboardControl** -- a patch
that lives *inside* the KPM repository, contributed by "J" as #136 -- so the
same licence covers the inherited work. Saul0097 stated the derivation himself:
"I built the controller mod starting with j's enhanced keyboard." The two source
trees carry an identical file set, which matches that account.

`Copyright (c) 2025 Lane Dibello and KotOR Patch Manager contributors`; the
contributors clause covers J's patch. The full text is vendored as
`LICENSE-KOTOR-PATCH-MANAGER.txt`.

All three parties gave explicit permission for KMRP to bundle the result on
2026-09-04; `NOTICE.txt` quotes each of them. Saul0097's own repository still has
no standalone LICENSE file, which is worth closing so his own additions are
stated in his words rather than inferred, but it does not leave the integration
unlicensed.

## Installed files and ownership

Enabling the option also enables K1 Modern Driver Compatibility because its
`dinput8.dll` is the ASI loader. KMRP installs four controller-owned files beside
the selected executable:

| File | Purpose |
| --- | --- |
| `kmrp-controller-runtime.asi` | Loads and applies the KPM hook configuration. |
| `kmrp-controller.module` | Polls XInput and translates controller state. |
| `patch_config.toml` | Declares the selected executable hash and the six hooks below. |
| `KMRP_Controller.manifest` | Records exact hashes for ownership-aware restore. |

Installation refuses an existing controller filename or `patch_config.toml`
that KMRP does not own. Restore removes only files whose current hashes still
match the manifest; modified files are retained. A failed controller install
rolls back the executable and a newly installed ASI loader.

This means a separate KPM installation and KMRP's embedded controller runtime
cannot share one game directory today: both own `patch_config.toml`. Leave the
KMRP controller option off when using an external KPM configuration.

## Hook sites

The executable described here is gold v23, 4,083,712 bytes, SHA-256
`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`.
Addresses are preferred-image virtual addresses (VA); these original-image
sites use `FILE = VA - 0x400000`. KMRP does not write these bytes on disk. The
runtime verifies the listed stock sequence and replaces its start with an
in-memory `E9` detour.

| VA | FILE | Expected bytes | Export |
| --- | --- | --- | --- |
| `0x005E271E` | `0x1E271E` | `8B 84 24 E4 00 00 00` | `CaptureActionBarInputK1` |
| `0x006227E0` | `0x2227E0` | `6A FF 68 E9 89 72 00` | `DispatchMenuInputK1` |
| `0x004051C3` | `0x0051C3` | `8B C6 83 E8 1C` | `CancelMovieOnSpaceK1` |
| `0x00404D96` | `0x004D96` | `8B 46 48 8B 48 08` | `PollMovieControllerK1` |
| `0x00686BA0` | `0x286BA0` | `53 56 57 8B F1` | `UpdateActionBarControlsK1` |
| `0x0068B170` | `0x28B170` | `6A FF 68 B0 F7 72 00` | `ClearActionBarControlsK1` |
| `0x0040C1F6` | `0x00C1F6` | `89 1E 89 7E 04` | `CancelActionBarKeyboardFocusOnMouseMoveK1` |

All six expected sequences were read back from a generated 1920×1080 executable.
In a named-copy launch through K1DC's loader, both controller modules appeared in
the process and `ReadProcessMemory` found `E9` at all six sites. The named copy's
SHA-256 remained unchanged before and after launch.

## Controls and requirements

The module requires an XInput device and the game's default key bindings. It is
an input translator: with three exceptions it presses keyboard keys rather than
talking to the GUI, so what a button does is whatever that key does in the
current context. The table below gives the scancode each button sends, read from
`BUTTON_BINDINGS` in `K1XboxControlsXInput.cpp`, and then what the game does with
it in each context.

| Button | Sends | In gameplay | In a menu |
| --- | --- | --- | --- |
| A | `Return` (+`R`) | default / primary action | activates the focused control |
| B | `Delete` | — | **back / close.** `Delete` is rewritten to `Escape` whenever a menu panel is open |
| X | `G` + `End` | stealth | `End` is captured and dispatched as the Xbox X GUI event |
| Y | `F` + `Home` | disengage combat | `Home` dispatched as the Y GUI event |
| LB | `Space` + `Insert` | pause | `Insert` dispatched as the Black-button GUI event |
| RB | `Tab` | change party member | change party member |
| LT / RT | `Q` / `E` | cycle targets | **move between menu screens** — Map, Inventory, Character… |
| Back | `V` | toggle solo mode | — |
| Start | `Escape` | opens the menu | closes the screen |
| L3 / R3 | `X` / `Caps Lock` | flourish, first-person view | nothing |
| D-pad | arrow keys | action-bar navigation | menu navigation, repeating while held after 400 ms at 120 ms intervals |
| Left stick | movement keys | move, with a walk/run threshold | — |
| Right stick | `Page Up` / `Page Down` | camera | scrolls the description box |

The three exceptions to "presses a key" are the X, Y and LB secondary scancodes,
which the module intercepts and turns into the retained Xbox GUI events so each
panel's own handler runs.

**The menu column is not derivable from the binding column,** and reading only the
bindings has already produced one wrong conclusion in this repository: LT/RT were
described as inert in menus because `Q` and `E` are target-cycling keys, when in
fact they move between menu screens. A binding table says which key is sent, not
what the game does with it.

The mouse remains available by default; F9 toggles parking and hiding it for a
controller-only session.

Planned additions — the Guide button, tab cycling on the bumpers and party
cycling on the stick clicks — are specified in
[`controller-planned-work.md`](controller-planned-work.md).

Steam Input is not claimed to work by the upstream author. PlayStation and other
non-XInput controllers require an external XInput translation layer. Proton and
Steam Deck remain untested; use the explicit matrix and report procedure in
[`linux-proton-steam-deck.md`](linux-proton-steam-deck.md).

## Dynamic controller prompts

The PC data contains two prompt systems rather than one switchable set:

- `dialog.tlk` contains PC tutorial prose at string references `48324` onward,
  including mouse clicks and keyboard tokens. `assets/override-common/tutorial.2da`
  selects this PC block for KMRP's tutorial popups.
- The same TLK retains Xbox-era prose, including references `39461`, `39462`,
  `39465`, `39482`, and `41875`. Tokens such as `<abutton>` and `<whbutton>`
  appear in those strings.
- `TexturePacks/swpc_tex_gui.erf` retains seven matching 32×32 textures:
  `abutton`, `bbutton`, `xbutton`, `ybutton`, `startbutton`, `whitebutton`, and
  `blackbutton`.
- The generated PC `.gui` files contain ordinary button labels and STRREFs; a
  recursive scan found no controls referencing those Xbox texture names.

Blindly selecting the retained Xbox strings was rejected. They describe the
original console mapping—most importantly white-button pause and console trigger
semantics—which conflicts with this module's LB pause and PC-oriented mapping.
That would replace accurate keyboard help with inaccurate controller help.

Two rendering experiments were also rejected in the isolated 3440×1440 game
copy. Literal `<abutton>` text in a `.gui` stayed literal. An Xbox TLK entry
removed its `<abutton>` token on PC but drew no glyph. Appending a new label to
`mainmenu.gui` drew nothing because the screen constructor initializes only its
known controls. Replacing an existing label's fill with `abutton` did render the
retained 32×32 art, proving that existing fills are the usable PC path, but the
legacy texture was visibly enlarged and is not shipped as KMRP prompt art.

KMRP assigns CC0 Xbox 360 button artwork (see `THIRD_PARTY_NOTICES.md`) to both
the normal and highlighted fills of existing action buttons **while the pad is the
input device in use**, not merely while one is plugged in. Covering both fill
states is required because controller navigation focuses a button immediately and
KOTOR then renders its separate highlight border. Touching mouse or keyboard
removes the artwork; a disconnect removes it too.

Following the active device was previously rejected, and the reason is worth
keeping: KOTOR recentres its own cursor during scene and menu transitions, that
arrives at the mouse hook as an ordinary move, and the artwork vanished every
time. `MouseIsBeingUsedK1` now separates the two -- a recentre is a single jump to
one point, real use is a stream -- by requiring at least two distinct positions
and 24px of accumulated movement inside 250ms. Isolated jumps never reach the
threshold. No `.gui`, TLK
string, localized label, or executable byte is changed.

The ordinary `ProcessInput` loop does not run while Bink owns the playback loop,
so controller-to-keyboard translation cannot skip a movie there. A seventh
detour at the database-identified `CExoMoviePlayerInternal::PlayMovieLoop`
playback loop (`0x00404D96`, inside `PlayMovieLoop`) polls the pad once per
movie frame and edge-triggers cancel
for A, B, LB, or Start. Physical
Spacebar cancellation remains on the existing movie-window hook.

The first measured prompt set covers ten controls. “GUI index” is used only by
the asset generator to validate the packaged GFF; “object offset” is the runtime
address relative to the concrete panel object:

| Screen | Control | GUI index | Object offset | Prompt |
| --- | --- | ---: | --- | --- |
| Character | `BTN_EXIT` / `BTN_SCRIPTS` | 60 / 61 | `0x523C` / `0x5400` | B / X |
| Container | `BTN_OK` / `BTN_GIVEITEMS` / `BTN_CANCEL` | 2 / 3 / 4 | `0x0AD0` / `0x0E58` / `0x0C94` | A / X / B |
| Save/Load | `BTN_DELETE` / `BTN_BACK` / `BTN_SAVELOAD` | 8 / 9 / 10 | `0x0F9C` / `0x0DD8` / `0x0C14` | X / B / A |
| Upgrade category | `BTN_UPGRADEITEMS` / `BTN_BACK` | 9 / 10 | `0x01A4` / `0x0368` | A / B |

The generator reads the final GUI for each resolution, requires the expected tag
at each index, requires the original normal fill to be empty, and pre-compensates
the badge for that control's exact aspect ratio. This keeps the badge round even
though the renderer stretches `BORDER.FILL` across the full button. The ten TGA
resrefs are present but unused when controller support is disabled.

### Placing the badge beside the label

The engine centres a button's label, so a badge at a fixed inset from the left
edge floats far from the words on a wide button — most of a screen away on the
978px `BTN_UPGRADEITEMS`. The badge is therefore placed against the measured
label:

```
center_x = (control_width - label_width) / 2 - gap - radius
```

with `gap = radius * 0.55`, clamped so it cannot leave the button. Label widths
come from the resolution's own `dialogfont16x16.txi`: the engine renders one
texel per pixel, so a glyph's width is `(lr.u - ul.u) * texturewidth * 100` (see
[`../reverse-engineering/font-atlases.md`](../reverse-engineering/font-atlases.md)).

**The label text is not chosen by KMRP.** All ten buttons carry `TEXT.STRREF` and
no inline `TEXT` string, so the words are whatever the player's `dialog.tlk` holds:

| Control | STRREF | Retail English |
| --- | ---: | --- |
| `BTN_EXIT`, `BTN_CANCEL`, `BTN_BACK` (upgrade) | 1582 | Close |
| `BTN_SCRIPTS` | 1067 | Scripts |
| `BTN_OK` | 38542 | Get Items |
| `BTN_GIVEITEMS` | 47884 + 47885 | Switch To Give Item |
| `BTN_DELETE` | 1560 | Delete |
| `BTN_BACK` (save/load) | 1581 | Cancel |
| `BTN_SAVELOAD` | 1587 / 1589 | Save / Load |
| `BTN_UPGRADEITEMS` | 42295 | Upgrade Items |

Two are set by code rather than from one reference — `BTN_SAVELOAD` reads "Save"
on the save screen and "Load" on the load screen, and `BTN_GIVEITEMS`
concatenates two strings — so each control is measured against the **widest**
wording it can show. A badge measured against the narrower one would be
overlapped by the wider one.

A hand-written table keyed by control tag preceded this and was wrong for five of
the ten: `BTN_CANCEL` and both `BTN_BACK`s are 1582 "Close", not "Cancel" or
"Back"; `BTN_SAVELOAD` is "Save", not "Load"; and `BTN_GIVEITEMS` was measured as
a 20-character string that does not exist.

`dialog.tlk` is a proprietary game file and is not a build input, so the shipped
textures are placed against the retail English widths above. The patcher then
re-places them at install time from the player's own file
([`ControllerPromptGenerator`](../src/patcher/ControllerPromptGenerator.cs)): it
reads the `kmrp_prompts.txt` manifest the build writes into each GUI archive,
resolves those STRREFs against the real `dialog.tlk`, measures with the font
advances the manifest carries, and slides the already-composited pixels sideways.
Nothing is re-rendered — the artwork does not depend on the label, only its
position does, and that position moves by exactly half of any change in label
width. The shift is a whole number of texels, at most about 1.5 screen pixels of
quantisation against a target gap of roughly 13, and a column move preserves the
artwork's antialiasing exactly where a resample would not.

**Limit, measured rather than assumed.** A synthetic German-width `dialog.tlk`
was run through the installer to exercise this path (the retail English file
makes it a no-op, since the shipped placement is already correct). Nine of the
ten badges moved and eight landed exactly where a direct re-render would put
them, the other two one texel away — 1.9px on the widest button. The tenth,
`BTN_SCRIPTS`, did not move because "Skripte" and "Scripts" are within a texel of
each other.

The exception is `BTN_GIVEITEMS`. "Wechseln zu Gegenstand geben" measures 611px
on a 601px button, so the label is wider than the button that holds it and the
engine's centring already pushes it off both edges. The badge clamps to the left
edge and overlaps it. Nothing can be placed well in that case; the screen is
broken independently of the badge, and no retail localisation is known to hit it.
It is recorded here rather than papered over.

A missing or unreadable `dialog.tlk` is not an error: the shipped English
placement simply stands. Because that degradation is silent, the manifest is
checked by `testing/regression/Test-ControllerPromptAssets.py`, which verifies
that every archive carries one, that its extents match the GUI controls, that its
STRREFs are the ones the buttons really draw, and that its embedded font advances
match the archive's own font.

When controller support is disabled, KMRP installs no controller runtime or
prompt override, so all keyboard/mouse prompts remain byte-for-byte unchanged.

## Menu navigation the module supplies

Each panel the module can navigate contributes its own layout to
`GetK1SettingsStripExit`: the column the D-pad walks, the row of action buttons
along the bottom, and optionally a row of tabs above the column reached by
pressing Up from the top. A panel with no entry gets no help at all -- vanilla's
own control links decide where focus can go, which is usually nowhere useful.

**The Abilities screen had no entry until 2026-09-06**, which is why its Skills /
Powers / Feats tabs could not be reached with a controller: they are ordinary
buttons and nothing routed focus to them. Offsets are from `kotor1_0_3.db`, class
`CSWGuiInGameAbilities`. That table corroborates itself here -- its
`description_listbox` is `0x33BC`, the value already shipping as
`K1_ABILITIES_DESC_OFFSET`.

| Member | Offset | On screen at 3440x1440 |
| --- | --- | --- |
| `skills_button` | `0x2F18` | tab, `LEFT=607 TOP=264` |
| `powers_button` | `0x2D54` | tab, `LEFT=1360 TOP=264` |
| `feats_button` | `0x2B90` | tab, `LEFT=2091 TOP=264` |
| `ability_listbox` | `0x30DC` | the column; rows are allocated at runtime, so the entry sets `dynamicColumn` |
| `exit_button` | `0x369C` | Close, `LEFT=2112 TOP=1230` |

**Untested.** The entry is built and installed but the play-test has not been
done. What is verified is that it compiles, that the offsets come from the
database, and that the badge on `exit_button` is generated for all 48
resolutions -- not that pressing Up in game lands on a tab.

## Prompt coverage

`tools/audit_controller_prompt_coverage.py` joins the module's two tables by
panel vtable: every screen it can navigate and that screen's row of action
buttons, against every button that carries a badge. It reported **2 of 30** when
first run and **22 of 31** after the 2026-09-06 expansion.

The nine remaining are all **Default** buttons, and they are bare deliberately:
no controller button performs restore-defaults, so a badge there would depict an
action the pad cannot take. Rule 12 -- this is "left alone on purpose", not "never
looked at".

Badges are assigned in two tiers of confidence, and the source says which:

- **B on back / cancel / close is provable.** B's `Delete` scancode is rewritten
  to `Escape` for any menu panel, and the rewrite is suppressed only for the four
  transient overlays in `IsK1DeleteEscapeSuppressedPanel` -- floaty text, bark
  bubbles, the message box and the controller-loss box.
- **A on a primary action is a convention.** A activates whatever control has
  focus, so an A badge says "this is how you commit on this screen", not "A
  always presses this button from anywhere". It is the same convention the
  original ten badges already used.

## Verification and untested coverage

Run:

```powershell
.\build_kmrp.ps1 -ReuseResources
.\testing\regression\Test-ControllerSupport.ps1
python .\testing\regression\Test-ControllerPromptAssets.py
```

The regression verifies install/restore ownership, valid TOML, seven detours,
eleven parameters, exact on-disk hook bytes, foreign-config refusal, and complete
rollback. The named-copy launch additionally verified runtime/module loading and
live detours on Windows.

The full resource build generated all 48 archives. The prompt regression read
all 480 TGA outputs, verified their 512×64 32-bit headers and non-empty artwork,
and rechecked all ten control indices, tags, and empty source fills in every
archive. A rebuilt module loaded in a named-copy launch, remained alive through
the health window, and again placed `E9` at the original six detour sites. The new
movie-frame detour, focused-state prompt rendering, and controller movie cancel
remain to be exercised in the next named-copy play-test. The named
executable stayed SHA-256-identical before and after.

In a user-observed 3440×1440 Windows play-test on 2026-09-06, the rebuilt game
reached the complete main menu after every intro movie and controller navigation
and actions worked well. That run also established that the first prompt build
showed no badges and could not skip movies, which led to the focused-border and
movie-loop corrections above. Those two corrections still require the next
named-copy play-test. Broader movement, combat, dialogue, inventory, map, rumble,
disconnect/reconnect, and Proton/Steam Deck coverage also remains untested.

### Testing with a virtual controller

`testing/controller/` drives the game with a `vgamepad` virtual pad so the module
sees a genuine XInput device. **One trap, hit twice in both directions on
2026-09-06 and worth stating before anyone repeats it:** `ReadPad` takes the
first XInput slot that answers and stays on it, so whichever pad holds the lower
slot wins and the other is invisible to the module.

- A forgotten virtual pad on slot 0 made the user's physical controller stop
  working in game entirely. Nothing was wrong with the module.
- Earlier the same day the physical pad held slot 0 and the virtual pad on slot 1
  could not drive the game at all.

Shut the pad server down when finished. `XInputGetBatteryInformation` tells the
two apart for the wireless case -- a physical pad reports `NIMH` or `ALKALINE`, a
ViGEm pad reports `WIRED` -- but a wired physical pad also reports `WIRED`, so it
is not a general discriminator.

## Deliberately not changed

- `swkotor.exe` receives no controller-specific on-disk edits.
- `dialog.tlk`, `tutorial.2da`, and every `.gui` remain unchanged; only existing
  controls' empty normal-fill state is changed in memory while prompts are active.
- Existing external KPM configuration is never merged or overwritten.
- Keyboard/mouse operation remains the engine's underlying input path, and the
  cursor is visible and usable by default when controller support is enabled.
