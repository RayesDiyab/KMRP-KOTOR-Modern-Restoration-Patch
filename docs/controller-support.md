# Optional Xbox controller support

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). It records the exact
> reviewed sources, installed files, hook sites, prompt investigation, and the
> difference between automated verification and play-testing.

**Kind: reference.** Play-tested with a physical pad at 3440x1440 for what
`CHANGELOG.md` marks play-tested; everything else is structurally verified only,
and says so.

KMRP installs controller support as an Advanced Settings component, on by
default since 2026-09-24 (it was opt-in). It began as **KPM – Xbox Controls for
KOTOR 1 1.2** by Saul0097, an XInput-to-keyboard adapter, and parts of that
module are still in it. What ships now is KMRP's **native path**: it feeds the
pad into KOTOR's own retained joystick pipeline rather than pressing keys
([`controller-native-path.md`](controller-native-path.md)), reads Xbox pads
through XInput and PlayStation, Switch and Steam Deck controllers through SDL 3
([`controller-sdl-backend.md`](controller-sdl-backend.md)), draws button
prompts in four families, and adds the Controller Layout screen. A KOTOR Patch
Manager runtime applies its hooks in memory from `patch_config.toml`: 18
detours and 4 byte patches in the 2026-09-24 build, 26 detours and 4 byte
patches after the rumble mixer of 2026-09-25, and 33 detours and 4 byte patches
since the echo guard of 2026-09-28 (`tools/check_patcher_hook_table.py`; the
eight rumble hooks are in [`controller-rumble.md`](controller-rumble.md)).
Without controller support the runtime still installs, with 5 detours and the
same 4 byte patches (*Installation*, below).

*Corrected 2026-09-24:* this introduction still described the first
integration -- an adapter feeding keyboard and GUI events through six detours,
not play-tested -- and much of what follows was written then. Sections that
describe that first version now say so.

## Sources and build identity

| Component | Exact source | Local output |
| --- | --- | --- |
| Controller module | KMRP's sources in `src/controller-native/`, with `scopeking0117-alt/KPM-Xbox-Controls-K1` at commit `78e7eaa3b9554ec0e6732f749424dc916f3a1895` as modified by KMRP (`KMRP-CONTROLLER-MODULE.diff`) | `kmrp-controller.module`, 181,248 bytes, SHA-256 `AC2C41EC4C935B19EFF4693E3FBB43D176D28C5B37DE0CDC2C706F72379652C9` in the 2026-09-24 installer; 204,288 bytes, SHA-256 `E52826A2724038E765DFD45B86171160A017E054E346E29CF4A1CE5D0F74DE21` in the haptics hardware-test installer `C796489A…`; 204,800 bytes, SHA-256 `577AAE92D0FE18766EDEC669C54959A0213BA1618030F4E1B0EED92E4D9CC251` in `D58A2E33…`, `7C2FFF8B…` and `AD3DC07D…` (X and Y in combat, the dialogue A moved); 205,824 bytes, SHA-256 `32F018CFE3D93AE9C9C5F4D20DDCB85FE422DD09EECAC798F13263F03BA43E9C` in `E5AFC981…` (the dialogue A from the drawn layout); 206,336 bytes, SHA-256 `628D4DC244535E26E4EBD81F4DC4710691A60CC19A6885735F66AF551BB10F90` in `EC98B10F…` (the character-creation A guard); 209,408 bytes, SHA-256 `B7307208D5C2B93B86821DC9746E39EEE8C84B17D09919AD7EFD4171D37E0D59` in `1720E0C1…` (character-creation badges, Attributes/Skills navigation); 209,920 bytes, SHA-256 `B28A80F7B635595A59651458E2D35AB20145BCD62EBC5DFC3DE4CDF72696B43B` in `DB9D7A08…` (Feats' A/X swap, name-entry guard, dialogue A adjustment) and `4EF3C181…` (the same module; the resolution layouts pooled); 216,576 bytes, SHA-256 `36D23D9B89039E2FB16C69CF3676F919676B2DDD2482E8DFC14C7794E51819C9` in `D407BF3A…` (settings: Y on Default, D-pad on −/+ rows and arrow glyphs; Pazaak's wager; the dialogue A on its line; the status summary's layout); 217,600 bytes, SHA-256 `D13FF3CBAC051905AC7FBF6620659E65B8A17D69B05836465761FE020A5A55E1` in `63E7AAB9…` (the status summary's A), `1419AD0471ED85AA6C8825480FA0493B82C36B28D96959DD9129F32986FF5809` in `B5D3CBB7…` (the D-pad kept off its OK), `42426D92AEF3738A66753060734801EAB2AC91AA5E705320E02C263522F7D5D9` in `49671B67…` (the line spacing misread) and `CB61BF176471DA5E24E415CFFAD4B90E501D01A0FB524D9FBE9FA216AF988020` in `80616FE6…` (the line spacing counted); 218,112 bytes, SHA-256 `C19CC7725DCBBDAF79E76AADA9F0139CC9A06C2D7759A259AC186F190C424A8C` in `128CDC79…` (Level Up, Auto Level Up and the skill-info notice badges; the D-pad kept off the Character screen); 217,600 bytes, SHA-256 `69E1811B33EFB36284A1D4CA2CA35D972EC5BEE521E763D46051BB40A254941A` in `9736B41F…` (the echo guard on every panel; the −/+ arrows keep their art); 217,600 bytes, SHA-256 `AF223C4D4542B4A983EF4D1137C08AB4AA7F6C999DD7D2C3402DE2DD3BC2D312` in `C77F7640…` (the core stand-ins; the runtime on every patch); 236,544 bytes, SHA-256 `57E68A912782D6CDEDC083A07D29A73AF878CC99A03E03F043C98FD706DC91E0` in `D6E40FAF…` and the KPM edition (the applier, [kpm-edition.md](kpm-edition.md)); 241,664 bytes, SHA-256 `0C89C330245F752A303A22D5B731C2E16D19D4731078413B195F01C71972E955` in `125DEA64…` and the four-patch KPM edition (the core's frames handing over to KMRP Controller's; the movie bars KMRP Movies'); 245,248 bytes, SHA-256 `4B1131DABC4550D5F4F18B2C52EE93291E8350C2B35FA2A5215660A0F4C13AD3` in `603DC45D…` and the KPM edition with Steam support (the applier accepts Steam's executable and pauses the game's threads while writing), unchanged in `112CA755…`, KMRP's installer on KOTOR Patch Manager's runtime |
| Hook runtime | since 2026-09-29: the submodule `third_party/Kotor-Patch-Manager` at `71ac5fa` (FTD's `widescreen-patch`; first built from `17fd051`, then `9884466`, all three with the same runtime sources and building the same bytes), since 2026-10-01 `2a784bf`, `RayesDiyab/Kotor-Patch-Manager` branch `kmrp` (FTD's `074972b` with one hook-list fix; nothing under `src/KotorPatcher` changed, and rebuilt from it the runtime was byte for byte the same), built by `src/kpm-runtime/build.cmd` ([README](../src/kpm-runtime/README.md)); until then `LaneDibello/Kotor-Patch-Manager`, commit `7d53e52f55622a48ab97001c2680fd9fb59c8f98`, from Saul0097's package | since 2026-09-29 `KotorPatcher.dll`, 347,136 bytes, SHA-256 `E7D6AE7F44ABA1FD…`, loaded by KProxy's `binkw32.dll`, 88,064 bytes, `3A35A77EB4EEFC96…`; until then `kmrp-controller-runtime.asi`, 338,432 bytes, SHA-256 `F5CF2A21E4C28DA95CD8DAAF2704F871A6105616BFE250361929C61BCDB43B45` |
| SDL | official SDL 3.4.16, Windows x86 | `kmrp-sdl3.dll`, 2,358,784 bytes, and its licence |

The outputs are those embedded in the 2026-09-24 installer (`ECA3DE4B…`). Both
KMRP-built outputs are 32-bit C++17 MSVC static-runtime builds. The controller
module imports `XINPUT1_4.dll`, `GDI32.dll`, `USER32.dll` and `KERNEL32.dll`,
and loads `kmrp-sdl3.dll` at run time; the hook runtime imports only
`KERNEL32.dll`. (Until 2026-09-24 this table gave the first integration's
module: 130,560 bytes, `47B94364…`, importing only `USER32.dll` and
`KERNEL32.dll`.) The `.module` suffix prevents the ASI loader from loading the
controller a second time as a standalone plugin.

The runtime originally assumed its filename was `KotorPatcher.dll`. KMRP's
reproducible source change, preserved in
`third_party/Included/KPM-Xbox-Controls-K1-1.2 by Saul0097/KMRP-RUNTIME-PATCH.diff`,
finds the module containing `SelfModuleDir` by address instead. A named-executable
launch proved the unmodified build loaded only the runtime; the corrected build
loaded both files.

`KMRP-CONTROLLER-PROMPTS-PATCH.diff` records the first integration's changes to
Saul0097's source, kept as history; the current delta is
`KMRP-CONTROLLER-MODULE.diff`, which reproduces the tracked files exactly. The
first integration's change: It preserves the visible cursor at startup, tracks XInput connection,
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

The shipped module is built by `src/controller-native/build.cmd` (x86 MSVC,
`/Brepro`, SDL headers from the pinned SDK); see
[`../src/controller-native/README.md`](../src/controller-native/README.md). The
first integration was built from Saul0097's two source files alone, from an x86
MSVC native-tools environment, with:

```text
cl /nologo /Brepro /O2 /EHsc /MT /LD K1XboxControls.cpp K1XboxControlsXInput.cpp /link /Brepro /DEF:exports.def /OUT:kmrp-controller.module /INCREMENTAL:NO
```

Two consecutive builds produced the same 130,560-byte SHA-256, the first
integration's. The linker
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

**Since 2026-09-28 the runtime installs on every patch, and this option switches
only the controller's own hooks.** The runtime also carries fixes that have
nothing to do with a pad, and until then turning the option off took them with
it. Which hook goes where is the `install` key in
`src/controller-native/kotor1.hooks.toml`:

| Set | Hooks | Installed |
| --- | --- | --- |
| core (`always`) | the movie window's two (`NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1`), the four memory-safety byte patches, `NativeFreeSaveBufferK1`, and since 2026-09-30 the popup fit (`FitMessageBoxK1`) and the granted popup's two (`GrantedPopupFilledK1`, `GrantedRowTextK1`) | always, first in the table |
| controller | the other 30 detours, including `NativeGuiFrameK1` and `NativeMovieFrameK1` | with the option on: 40 hooks in all (37 until 2026-09-30) |
| core stand-ins (`no-controller`) | `CoreGuiFrameK1` at `0x0040CE70` (mouse confinement, the status summary's layout) and `CoreMovieFrameK1` at `0x00404D96` (the movie bars) | with the option off: 12 hooks in all (9 until 2026-09-30) |

The core goes first because KPM's runtime stops at the first hook that fails.
With the option off nothing reads the pad, draws a prompt or rumbles. The files
below are the same either way, and their names still say "controller" because
renaming them would orphan older installs' manifests.

**Since 2026-09-29** KMRP's installer runs KMRP on KOTOR Patch Manager's own
runtime, laid out as KPM's proxy deployment lays out a game folder, with KMRP's
four KPM patches ([kpm-edition.md](kpm-edition.md), section 1a). The controller
option decides whether the `kmrp-controller` patch goes into `patch_config.toml`,
with its module as `patches\kmrp-controller.dll`; the core's frames hand their
site to it when it is loaded (`ControllerFrameK1`), and do the core's work
themselves when it is not, so the two hook sets above are now the patches
`kmrp` plus `kmrp-controller`, and `kmrp` alone. The files:

| File | Purpose |
| --- | --- |
| `binkw32.dll`, `binkw32Hooked.dll` | KPM's proxy, which loads the runtime, and the game's own `binkw32.dll`, renamed, which the proxy forwards to |
| `KotorPatcher.dll` | KPM's runtime: reads `patch_config.toml`, loads the modules, writes the hooks |
| `patch_config.toml` | The executable's hash and the chosen patches, each with its hooks |
| `patches\kmrp.dll`, `patches\kmrp-movies.dll`, `patches\kmrp-controller.dll` | `kmrp-controller.module`, one copy per patch |
| `kmrp-kpm.dat` | The executable changes the core's copy applies in memory |
| `kmrp-sdl3.dll`, `kmrp-sdl3-LICENSE.txt` | SDL 3 for non-Xbox controllers, and its zlib licence |
| `kmrp-kotor-patch-manager-LICENSE.txt` | KOTOR Patch Manager's MIT licence |
| `kmrp-controller.ini` | The player's rumble settings, written only when absent |
| `KMRP_KPM.manifest` | Every file with its hash, the rename, and the 4 GB flag, for restore |

K1DC's ASI loader is no longer needed by KMRP and installs only with K1DC. A
folder with KOTOR Patch Manager's own runtime is installed for KPM instead, with
none of the files above but the data file, SDL and settings, and KPM's left as
they are; the player ticks KMRP Controller there. `Test-ControllerSupport.ps1` was rewritten for this layout the
same day. What follows describes the install until then, and is kept as the
record of it.

Until 2026-09-29: the option is independent of K1 Modern Driver Compatibility. The runtime needs the
ASI loader, `dinput8.dll` -- Ultimate ASI Loader, which K1DC's package ships
unmodified and which loads every `.asi` beside the game -- so
`DriverCompatOperations.Apply` installs the loader on every patch since
2026-09-28 (before, whenever either option was on), and K1DC's own `.asi` only
when driver compatibility is. Until 2026-09-24 the settings page forced driver
compatibility on with this option instead. `Test-ControllerSupport.ps1` covers
every combination of the two options, and switching this one on an installed
game both ways. KMRP installs eight runtime files beside the selected executable:

| File | Purpose |
| --- | --- |
| `kmrp-controller-runtime.asi` | Loads and applies the KPM hook configuration. |
| `kmrp-controller.module` | Reads the pad and drives the game's own input pipeline. |
| `kmrp-sdl3.dll`, `kmrp-sdl3-LICENSE.txt` | SDL 3 for non-Xbox controllers, and its zlib licence. |
| `kmrp-kotor-patch-manager-LICENSE.txt` | The MIT licence of KOTOR Patch Manager, which covers the runtime, the module and the memory-safety patches. |
| `patch_config.toml` | Declares the selected executable hash and the native path's hooks. |
| `kmrp-controller.ini` | The player's rumble settings: Mode, Strength, Debug ([`controller-rumble.md`](controller-rumble.md)). Written only when absent or still as installed. |
| `KMRP_Controller.manifest` | Records exact hashes for ownership-aware restore. |

Eight files, as `Test-ControllerSupport.ps1` Case 4 checks: the four this table
listed until 2026-09-24, the two SDL files the hybrid backend added, the MIT
licence added on 2026-09-25, and the settings file added with the rumble mixer
the same day. (This said seven until the settings file.)

Installation refuses an existing controller filename or `patch_config.toml`
that KMRP does not own. Restore removes only files whose current hashes still
match the manifest; modified files are retained. `kmrp-controller.ini` is the
exception to the first rule, because it is the player's to edit: an edited
copy never blocks an install, is never overwritten, and is not claimed by the
new manifest (`Test-ControllerSupport.ps1` Case 7). A failed controller install
rolls back the executable and a newly installed ASI loader.

This means a separate KPM installation and KMRP's embedded runtime cannot share
one game directory today: both own `patch_config.toml`. KMRP declines to install
its runtime beside an external KPM configuration -- the controller option makes
no difference to that since 2026-09-28 -- so such a game gets neither KMRP's
controller support nor its run-time fixes; the rest of the patch still applies.

## Hook sites

The executable described here is gold v24, 4,087,808 bytes, SHA-256
`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`, and the
executables the installer writes from it. (This line said gold v23 and
4,083,712 bytes beside v24's hash until 2026-09-24.)
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
| `0x0040A638` | `0x00A638` | `8B 4F 1C 3B CE` | `OnSetActiveControlK1` |

These eight are the legacy module's. `src/controller-native/kotor1.hooks.toml`
holds **46 entries** since 2026-09-28 -- 42 detours and 4 `replace` patches,
counted from its `[[hooks]]` blocks -- the rest being the native path's,
documented in [`controller-native-path.md`](controller-native-path.md). Seven of
the legacy eight are in the table but never installed (`CaptureActionBarInputK1`,
`DispatchMenuInputK1`, `CancelMovieOnSpaceK1`, `PollMovieControllerK1`,
`UpdateActionBarControlsK1`, `CancelActionBarKeyboardFocusOnMouseMoveK1`,
`OnSetActiveControlK1`); `ClearActionBarControlsK1` is, because the native path
needs it. That leaves 39 installable entries, 35 detours and 4 `replace`, which is
what `tools/check_patcher_hook_table.py` found in agreement with
`ControllerOperations.BuildConfig`, the installer's hand-written table, until
2026-09-29. The standalone installer wrote 37 of them with the controller option
on (33 detours, 4 `replace`) and 9 with it off (5 detours, 4 `replace`;
*Installed files and ownership*, above).

Since 2026-09-29 the installer writes the KPM edition's patches instead, from
sections `tools/build_kpatch.py` generates, and `check_patcher_hook_table.py`
checks those: `kmrp` 7, `kmrp-movies` 2 and `kmrp-controller` 28, 37 hooks with
every option on (since the popups of 2026-09-30, `kmrp` 10 and 40 in all, 12 with the
controller off) -- the same 37 sites, with `CoreGuiFrameK1` and `CoreMovieFrameK1`
in place of `NativeGuiFrameK1` and `NativeMovieFrameK1`, which hand over to KMRP
Controller's frames -- and 9 with the controller off.

The table's size over time, counted from its `[[hooks]]` blocks at each commit
that changed it: 29 entries on 2026-09-24 (`137fd5d`; 25 detours, 4 `replace`);
37 after the rumble mixer's eight on 2026-09-25 (`d0e4ed6`; 33 detours); 44 after
the character-creation guards, the name-entry guard and the echo guard
(`0f60aa1`, 2026-09-28; 40 detours); 46 with the two no-controller stand-ins,
`CoreGuiFrameK1` and `CoreMovieFrameK1` (`d5a54e7`, 2026-09-28; 42 detours).
*Corrected 2026-09-28:* this paragraph stopped at "37 since the rumble mixer's
eight", nine entries short, and said the verification below covered 29 entries
without saying that the later ones had not been checked the same way.

On 2026-09-24 the expected bytes of all 29 entries of the time were found in every
one of the 48 executables the installer (`ECA3DE4B…`) writes with `--apply`, and
none of their sites overlapped a byte the installer writes. On 2026-09-28 the same
check was repeated for **all 46 entries** -- including the echo guard,
`GuardPanelEchoK1` at `0x00409E60` -- against every one of the **49** executables
installer `09B1AE2C…` writes (`--apply` on the clean executable at each catalog
resolution): every expected sequence present, no site overlapping a byte the
installer writes. Checked against a known positive: an entry planted on the movie
display-mode width at `0x00403D6C`, which the installer does write, is reported
on both counts.

Earlier, and kept as it was measured: all eight expected sequences were read
back from a generated 1920×1080 executable, and in a named-copy launch through
K1DC's loader, both controller modules appeared in the process and
`ReadProcessMemory` found `E9` at all six sites then in use. The named copy's
SHA-256 remained unchanged before and after launch.

## Controls and requirements

> **This section describes the first integration's keyboard path**, Saul0097's
> original transport. The installer no longer installs it: the native path
> replaces the input transport, and `testing/controller/select_controller_path.py`
> can still select the old one for comparison. What each button does on the path
> that ships is in [`controller-behaviour-matrix.md`](controller-behaviour-matrix.md)
> and, side by side with this table, [`controller-parity.md`](controller-parity.md).
> Kept because the difference is the evidence the native path was built from.

The module required an XInput device and the game's default key bindings. It is
an input translator: with three exceptions it presses keyboard keys rather than
talking to the GUI, so what a button does is whatever that key does in the
current context. The table below gives the scancode each button sends, read from
`BUTTON_BINDINGS` in `K1XboxControlsXInput.cpp`, and then what the game does with
it in each context.

| Button | Sends | In gameplay | In a menu |
| --- | --- | --- | --- |
| A | `Return` (+`R`) | default / primary action | activates the focused control |
| B | `Delete` | lets go of the bottom-right action bar when one of its slots has focus (issue #17) | **back / close.** `Delete` is rewritten to `Escape` whenever a menu panel is open |
| X | `G` + `End` | stealth | `End` is captured and dispatched as the Xbox X GUI event |
| Y | `F` + `Home` | disengage combat | `Home` dispatched as the Y GUI event |
| LB | `Space` + `Insert` | pause | `Insert` dispatched as the Black-button GUI event |
| RB | `Tab` | change party member | change party member |
| LT / RT | `Q` / `E` | cycle targets | **move between menu screens** — Map, Inventory, Character… |
| Back | `V` | toggle solo mode | — |
| Start | native (see below) | opens the **Map** (issue #18) | closes the in-game menu, from the Map or any tab LT/RT reached |
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

Planned additions -- the Guide button and tab cycling on the bumpers -- are
specified in [`controller-planned-work.md`](controller-planned-work.md). Party
cycling on R3, the third, shipped on 2026-09-15.

**Start and the action bar, on the native path (issues #17 and #18).** Start in
the world opens the Map through the engine's own Map hotkey (event `0xD7`, whose
handler at `0x006218D5` shows screen `event - 0xD1`), instead of the game's Start
event `0x0B`, which opens Options. With the in-game menu in front, Start sends B's
control code, the close measured from every tab. A slot of the bottom-right action
bar used with A keeps focus, so A can be pressed again straight away -- attack,
attack, attack. B lets go of it without doing anything else -- B has no other
effect in the world -- and D-pad Left/Right re-enters the bar as before. (Until
2026-09-25 a used slot let go of focus too, so the next A acted on the world; in
combat that meant D-pad Right before every action, and the user asked for the
bar to stay.) The mechanisms are in
[`controller-native-path.md`](controller-native-path.md). **Play-tested on
2026-09-25** at 3440x1440 for A keeping focus ("works perfectly"); B's release was
not separately reported. `testing/controller/test_hud_release_and_start_map.py`
checks both against the engine's memory and has not been run on a loaded save.

Steam Input is not claimed to work by the upstream author. Since the hybrid
backend, KMRP reads PlayStation, Switch and Steam Deck controllers itself,
through SDL 3's HIDAPI, and Xbox pads through XInput, so an XInput translation
layer is no longer needed for **input** (until then, "KMRP reads XInput only"
was true). The **glyphs** follow the pad it reads, and through Steam Input the
controller Steam says is behind it: see *Controller families* below. None of the
non-Xbox hardware has been tested yet (`controller-sdl-backend.md`). Proton
and Steam Deck remain untested; use the explicit matrix and report procedure in
[`linux-proton-steam-deck.md`](linux-proton-steam-deck.md).

## Dynamic controller prompts

The PC data contains two prompt systems rather than one switchable set:

- `dialog.tlk` contains PC tutorial prose at string references `48324` onward,
  including mouse clicks and keyboard tokens. The game's own `tutorial.2da` selects
  this PC block; the one KMRP installs changes only its `icon` column. (*Corrected
  2026-09-29:* this said KMRP's committed copy selected it. It differs from the game's
  in 20 icon cells and nothing else, and since that date the installers make it from
  the game's own table.)
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
artwork's antialiasing exactly where a resample would not. The columns a shift
vacates repeat the edge column that moved away: transparent on every ordinary
badge, and the button's own box on the two that stand on one, Level Up and Auto
Level Up (2026-09-26).

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

When controller support is disabled, the runtime installs only its core hooks
(since 2026-09-28; before, no runtime at all). The prompt code runs only from
controller hooks, so no prompt is ever drawn and keyboard/mouse screens show no
badge. *Corrected 2026-09-28:* this said no prompt override was installed; the
per-resolution interface files carry the badge controls either way, empty and
invisible until the module fills one.

### Controller families (issue #19)

**Correction, 2026-09-19:** the following XInput/Steam identity path remains for
Xbox and translated controllers. A new SDL3/HIDAPI backend now supplies standalone
non-Xbox input through the same normalized state. Its packaging is tested, but
runtime and physical-device checks remain outstanding. See the
[hybrid backend reference](controller-sdl-backend.md) for the current mechanism,
Nintendo position mapping, and exact validation boundary.


The badges and cues show the buttons of **the pad KMRP actually reads**: Xbox,
PlayStation, Switch or Steam Deck. The module identifies it the way SDL does.
`XInputGetCapabilitiesEx` -- `xinput1_4.dll` ordinal 108, undocumented but
present since Windows 8 -- returns the USB vendor and product id of the device
behind an XInput slot, and the module asks it about the slot it reads from:

| vendor | product | family |
| --- | --- | --- |
| `054C` Sony | any | PlayStation |
| `057E` Nintendo | any | Switch |
| `28DE` Valve | `1205` | Steam Deck (its built-in controls) |
| `28DE` Valve | `11FF` | Steam Input's virtual pad -- Steam says what is behind it |
| anything else | | Xbox |

**Steam Input** presents every controller as its own virtual pad, but publishes
what is behind each one: the file named by the `SteamVirtualGamepadInfo`
environment variable has a `[slot N]` section per virtual pad with the physical
controller's `VID` and `PID`, and for Steam's pad the capabilities' last field is
that `N`. Those ids are then read against the same table. So a DualSense, a Switch
Pro or the Deck's own controls through Steam each get their own buttons.

**Translators that present an Xbox 360 pad of their own** -- DS4Windows, for one --
are indistinguishable from the pad they imitate, and get Xbox buttons. That is
what they tell every game; the module does not second-guess it.

The question is asked only when it can have a new answer: when the pad the module
reads connects or moves to another XInput slot, and, for Steam's pad, when Steam
rewrites its file (its modification time, looked at once a second -- SDL looks
every three). There is no timer otherwise and nothing to configure. Where the call
does not exist (Windows 7, a Wine without it) the family is Xbox, or Steam Deck when
Steam has set `SteamDeck=1`. The diagnostic line's `gly=family/changes` shows the
result (0 Xbox, 1 PlayStation, 2 Switch, 3 Steam Deck).

*Corrected 2026-09-19:* the first version of this read every HID device on the
machine through Raw Input and picked the most specific family present, every two
seconds, with a `kmrp-controller.ini` override. It guessed from what was plugged
in rather than what was in use -- a DualSense on a charging cable would have put
PlayStation buttons on screen while the player held an Xbox pad -- and was
replaced before it shipped. The file override went with it.

**Every family is shipped.** Each badge and cue texture is built once per family,
and the names differ only in the resref's fourth letter -- `kmrpb_charexit` is the
Xbox B badge, `kmrsb_charexit` the PlayStation one, `kmrn` Switch, `kmrd` Steam
Deck -- so no name grows past a resref's 16 characters and the Xbox names are the
ones that always shipped. The module's tables name the Xbox art;
`SetK1ControllerPromptFill` rewrites the letter for badges, and
`MatchCueFamilyK1` re-fills the cue labels (a `CSWGuiLabel`'s border params at
`+0x70`, fill resref at `+0x40` within them). `check_controller_drift.py` fails if
the letters in the module and the build disagree, or if any family's art is
missing. The cost is the badge art three more times: the installer grew from
114.1 MB to 142.2 MB (28.1 MB), and each installed resolution gets 61 more
badge textures per family in Override, plus four cue textures per family.

The Switch and Steam Deck sets are Xelu's dark-grey style -- the same low
contrast against KOTOR's dark blue panels that ruled out the Series X set for
Xbox. Judged from a contact sheet of the built textures, not in game.

**The Switch glyphs follow position, not letter.** XInput A is the bottom face
button, which a Switch Pro labels B, so the badge beside an A action shows
Nintendo's B, and likewise A↔B and X↔Y. That is right when the translator maps by
position (Steam Input with "Use Nintendo Button Layout" off) and backwards when it
maps by label. **Untested either way.** The swap-tabs cue has art of its own for
every family since 2026-09-24, drawn for KMRP; until then only Xbox had it.

**Verified:** the call itself on this machine -- ordinal 108 resolves in
`xinput1_4.dll`, the structure is 32 bytes as SDL declares it, and a virtual
Xbox 360 pad from the ViGEm driver reports `045E:028E`, which is Xbox; and the
Steam file's parsing, with `GetPrivateProfileStringA` on a file in SDL's documented
format, hex and decimal ids alike (`0x054c` and `1406` read as PlayStation and
Switch, `0x28de`/`0x1205` as Steam Deck, a slot not yet written as Xbox).
**Untested:** a real Steam virtual pad, any physical PlayStation, Switch or Steam
Deck controller, Proton, and the new families' art in game. **Reported working by the maintainer on 2026-09-28**, and issue #19
closed that day; which controllers were used was not recorded.

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
database, and that the badge on `exit_button` is generated for all 49
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

The figures in this section describe the earlier 2026-09-06 prompt iteration.
For the current hybrid backend, dependency ownership and hook counts, use the
[2026-09-19 validation reference](controller-sdl-backend.md#verification-and-remaining-work).


Run:

```powershell
.\build_kmrp.ps1 -ReuseResources
.\testing\regression\Test-ControllerSupport.ps1
python .\testing\regression\Test-ControllerPromptAssets.py
```

The regression verifies install/restore ownership, valid TOML whose hooks and
parameters match the source table entry for entry -- no fixed count, since a
copied count had gone stale at fourteen -- exact on-disk hook bytes at the
byte-checked sites, foreign-config refusal, controller-only and driver-only
installs, the defaults with no saved settings, and complete rollback: Cases 1-6,
all passing against the 2026-09-24 installer. It said "seven detours, eleven
parameters" when first written. The named-copy launch additionally verified
runtime/module loading and live detours on Windows.

The full resource build generates all 49 archives (48 until 2026-09-25). On
2026-09-25 the prompt regression passed on all 49, with 11,172 target textures.
On 2026-09-24 the prompt
regression checked 10,944 target textures across the four controller families
and 57 verified control mappings in every archive, plus the Controller Layout
screen. When first written it read 480 TGA outputs at 512×64 and ten control
indices, the Xbox-only first version. A rebuilt module loaded in a named-copy launch, remained alive through
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

## Mouse confinement on multi-monitor setups

Not a controller feature, and it ships here only because this module is the one
piece of KMRP's own code that runs inside the game — see the caveat below.

KOTOR turns the camera with mouse movement but never clips the cursor: on a
multi-monitor desktop a wide enough sweep walks the pointer onto the next
display, and the camera stops following. The game imports no `ClipCursor` at
all — `SetCapture`, `ShowCursor` and `SetCursorPos` are the only cursor calls in
its import table — so nothing in the engine competes for this.

`UpdateCursorConfinementK1` runs from `NativeGuiFrameK1`, the per-frame GUI hook,
and clips the cursor to the game window's client rectangle whenever KOTOR owns
the foreground window and is not minimised.

| Case | Behaviour | Why |
| --- | --- | --- |
| Game is foreground | cursor clipped to the client rect | re-applied every frame, so moving the window or changing resolution is picked up next frame |
| Alt-Tab, another app takes focus | released | Windows drops a clip when the foreground window changes; the explicit release covers focus loss without one |
| Minimised | released | `IsIconic` |
| Game exits or crashes | released | the clip does not outlive the process, so a crash cannot leave the pointer trapped |
| Windowed | clipped to the window, not the monitor | it follows the window rectangle |

The diagnostic line reports `cur=<clipped>/<takes>/<releases>`.

**Installed with or without controller support since 2026-09-28.** Until then
it lived in the optional controller component, so a mouse-only player who
declined controller support got no confinement; this said the honest fix was a
small always-installed component of KMRP's own. That is what the runtime now
is: without controller support, `CoreGuiFrameK1` holds the GUI frame and
confines the cursor (*Installation*, above). Issue #20.

**Untested.** Written from the Win32 contract and the game's import table; no
multi-monitor session has exercised it, and neither has Alt-Tab, minimise or a
windowed game.

## Deliberately not changed

- `swkotor.exe` receives no controller-specific on-disk edits.
- `dialog.tlk`, `tutorial.2da`, and every `.gui` remain unchanged; only existing
  controls' empty normal-fill state is changed in memory while prompts are active.
- Existing external KPM configuration is never merged or overwritten.
- Keyboard/mouse operation remains the engine's underlying input path, and the
  cursor is visible and usable by default when controller support is enabled.
