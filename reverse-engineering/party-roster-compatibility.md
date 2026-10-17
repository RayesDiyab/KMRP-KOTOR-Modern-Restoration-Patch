# Expanded party roster compatibility

Reference, 2026-10-17. Follows the [documentation standard](../docs/documentation-standard.md).
Addresses below are preferred **VA**, with `FILE = VA - 0x400000` in this
original image. There are no new executable edits or hooks in this change.

**Current mechanism:** [runtime generation and named live controls](#runtime-generation-and-named-live-controls-2026-10-17) supersedes the initial
embedded-panel-only implementation below. Earlier sections retain the measured
failures and corrections; their relocated native-control offsets are historical.

## Initial scope and inputs

[Issue #38](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/issues/38)
reported that KMRP 1.5.0's private nine-slot GUI shadowed the roster mod's file.
The general Override-priority repair already landed in 1.5.1. This change adds
KMRP geometry and styling while retaining the supplied expanded roster.

The supported backend is the bundled KPM `PartyRosterLimit32K1`: GOG 1.03 only,
4,042,752-byte executable, SHA-256
`9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435`.
Its manifest, hook guards and DLL still enforce that build. The current GUI has
**32** sets of `BTN_NPC`, `LBL_CHAR` and `LBL_NA` controls, numbered 0 through 31,
and `BTN_PAGE_PREV` / `BTN_PAGE_NEXT`. The backend displays 16 slots per page;
copying just the first 16 records would lose the second page.

At resource preparation, `K1RuntimeAssets.cpp` checks the actual effects of the
roster backend, reads `Override/partyselection.gui`, and passes it with the current
KMRP layout to `K1PartyRosterGui.cpp`. Only a successful adaptation keeps that
file in KMRP's private cache ahead of Override. Backend absent, partial probe,
missing file or unsupported input: normal Override priority applies. No original
mod file is rewritten. A mode change starts with that size's original KMRP layout
and adapts afresh; it never scales the previously adapted output again.

The read-only probe in `K1PartyRosterState.h` checks both allocation operands
against the roster patch's guarded hook manifest:

| VA | FILE | Bytes | Stock | Roster | Purpose |
| --- | --- | --- | --- | --- | --- |
| `0x0062DE20` | `0x0022DE20` | 4 | `80 3A 00 00` | `94 A1 00 00` | First panel allocation becomes `0xA194` |
| `0x00632E50` | `0x00232E50` | 4 | `80 3A 00 00` | `94 A1 00 00` | Second panel allocation becomes `0xA194` |

These identify the current backend's effects, not a general promise of
compatibility with a future roster implementation. KPM's installation guards
remain responsible for validating and applying its complete hook set. Merely
naming a DLL or enabling an option cannot enable the adapter.

## Geometry and functional data

[jryantomes' prototype](https://github.com/jryantomes/kmdlswap/tree/claude/kmdlswap-droid-editing-pt3u7r/tools/kmrp_party32)
demonstrated a useful centre/size transform. This implementation fits that mapping
from KMRP's current layout and transforms the supplied roster's own records.
It does not clone nine-slot controls over them. IDs, tags, navigation, captions,
string references, state and portrait/unavailable fills remain the mod's.
Borders and text font/colour/alignment use KMRP's presentation. Page buttons keep
their own fill and caption; copying Done's fill would give them an A glyph.

Stock geometry, read from `build-inputs/vanilla-gui/partyselection.gui` and asserted
by the regression (units are GUI pixels):

| Samples | Left | Top | Width | Height |
| --- | --- | --- | --- | --- |
| NPC/portrait/unavailable `i=0..8` | `54 + 91*(i%3)` | `109 + 88*(i/3)` (integer division) | 85 | 85 |
| Accept | 73 | 372 | 235 | 33 |
| Done | 247 | 410 | 146 | 28 |

Fit each axis independently over centres: `newCentre = a*oldCentre + b`;
size uses `sum(newSize)/sum(oldSize)`. Slot and bottom-button samples are fitted
separately. Require reconstruction within one pixel. Shared controls and panel
extent use the target KMRP geometry directly. Both pages receive the same map.
The existing generated KMRP layouts remain the source of the shared scaling rule.

**Measured correction during implementation:** at 1280x1080 KMRP's stock slots
are 191 pixels wide at 182-pixel pitch. Direct mapping gives expanded slots of
142 pixels at roughly 136-pixel pitch: overlapping hit boxes. The adapter keeps
centres and aspect ratio, uniformly reducing all slot layers on both pages just
enough to separate them. The minimum gap is `max(1, round(panelHeight/720))`.
A required shrink to 25% or less is rejected. Coincident centres are rejected.
No font or shared global scaling rule is changed.

Malformed GFF sections, duplicate tags/IDs, missing required controls and
unverified geometry fail before replacing the cached layout. Input is bounded to
2 MiB; style recursion and appended data are bounded. The adapter preserves the
GFF structure/field indices and repacks section offsets after styling.

## Controller panel relocation

Source inspection found a second issue: the old nine-slot controller helpers
referenced buttons inside what becomes the enlarged roster array. The backend
moves its panel tail by `(32-9)*0x454 = 0x638C`. Prompt targets now use the
relocated offsets while the backend probe is active:

| Control | Stock panel offset | Expanded offset |
| --- | --- | --- |
| Add/Remove | `0x38B8` | `0x9C44` |
| Done | `0x28B0` | `0x8C3C` |
| Back | `0x36F4` | `0x9A80` |

`vendor/K1XboxControls.cpp` also bypasses its stock three-row navigation repair
for this backend. The roster's own MOVETO links and page rebinding handle the
four-row pages. The normal nine-slot path retains its existing behaviour.

## Verification and controlled play-test

`python testing/regression/Test-PartyRosterGui.py` compiles the production C++
adapter and the production cache integration with an isolated process-image
fixture. Passed 2026-10-17:

- All 66 generated sets plus five sizes produced by the production blend helper:
  1800x1169, 2056x1329, 1710x1112, 1920x1243 and 3440x1400.
- All control IDs/captions/navigation retained, custom last-slot portrait retained,
  page fills retained, positive non-overlapping hit boxes on both pages.
- Stock/partial/active backend probes; ordinary Override yielding; managed layout
  retained; 1920x1080 -> 2560x1440 -> 1920x1080 cache rebuild; malformed source
  falls back; original mod bytes preserved.
- Native runtime and standalone controller compile with MSVC x86. The actual
  controller prompt lookup selects all three stock or relocated buttons correctly.
- The isolated game configuration has 225 disjoint hooks; all expected original
  bytes match the clean GOG input. Its database contains every explicitly required
  roster function, offset and class size.

The controlled fixture builder is
`testing/regression/Build-PartyRosterFixture.py`. It requires the owner's exact
GOG game, a copied save and built modules. It refuses an existing output and
writes only to a new ignored `build/` directory. It copies game assets, installs
the existing GOG-only backend and the changed KMRP modules in that copy, and
creates a local `kmrt32.mod` from the owner's Ebon Hawk resources. No proprietary
resource is committed. Source executable and save hashes are checked unchanged.

Example, after building the roster package in
`build/party-roster-check/roster-package/` with KPM's `create-patch.py`:

```powershell
python testing/regression/Build-PartyRosterFixture.py --game 'PATH-TO-GOG-GAME' --save 'PATH-TO-SAVE'
```

Run the fixture's `Launch Roster Test.cmd`, load the copied save, open the
cheat console, type `warp kmrt32`, and press Enter. An area entry script removes
the copied roster and creates uniquely named test companions in zero-based slots
8, 9, 15, 16 and 31. The picker opens automatically. Page 1 contains 8/9/15;
page 2 contains 16/31. Test selection across pages (9 + 31), Add/Remove, Done,
Back, disabled page ends, mouse, D-pad/stick with A/B, a resolution change away
and back, and save/reload in the fixture only. Instructions and hashes accompany
that local game.

**Not play-tested yet:** gameplay selection, controller focus/page changes,
rendered captions, save/reload and actual mode switching. Automated geometry and
cache checks do not establish those behaviours. Steam was not modified for this
work, and the roster backend does not support its executable.

**Instruction correction, 2026-10-17:** the first fixture instructions called the
KOTOR I console invisible and suggested P to reopen party selection. Those were
incorrect: KOTOR I normally shows a `>` prompt; reopen party selection from the
map screen. Swiss layouts may need Shift + ^, then the key below Esc. This
keyboard workaround has not been verified on the user's keyboard.

## Fixture correction: normal Ebon Hawk departure (2026-10-17)

The user reported being unable to choose companions in the synthetic-room test
and requested the ordinary Ebon Hawk exit. That earlier gameplay path is not
validated. The fixture now provides a fresh save named
`ROSTER TEST - Leave Ebon Hawk`, copied from the owner's `Dan-starmap` save,
whose `LASTMODULE` is `ebo_m12aa` and `AREANAME` is Ebon Hawk.

The saved `m12aa.git` has one `ebn12_ebonexit` trigger. Only its ScriptOnEnter
changes: `k_pebn_leavhawk` -> `kmrt_leave`. The wrapper checks GetEnteringObject
against GetFirstPC, adds test slots only when unavailable, enables them, then
executes the original `k_pebn_leavhawk` on the same trigger. The original script
opens party selection with its original `k_pebn_exithawk` exit callback. No
synthetic-room warp or automatic ShowPartySelectionGUI remains in the new path.

The original crew is retained. Extra UTCs are in this test game's Override so
that they remain available after departure. The save's party table and every
non-GIT resource in its Ebon Hawk capsule were checked byte-identical to the
source. The wrapper compiles and reads back as NCS; the saved trigger and save
name also read back correctly. Native departure and selection still require the
user's play-test. Use the named save, not an earlier autosave or custom room.

## Measured fixture compiler failure and correction (2026-10-17)

The user reported no response at the normal exit, only the exit banner. The
installed PyKotor compiler's EngineCallExpression.compile explicitly pushes
arguments left-to-right; its interpreter reverses popped arguments to agree.
That is inconsistent with the shipped K1 NCS. In `danm13_s.rim`, script
`k_pdan_13_area` pushes CONSTS `p_carth`, then CONSTI 2, then ACTION 697/2
(AddAvailableNPCByTemplate), then MOVSP -4. The failing fixture emitted CONSTI
slot then CONSTS template, so the native VM receives the wrong types. Merely
compiling and reading that script back did not validate runtime compatibility.

The corrected builder emits a small native-order prefix directly: GetEnteringObject
(25/0), GetFirstPC (548/0), equality and a conditional skip; IsAvailableCreature
(696/1); missing template then slot for AddAvailableNPCByTemplate (697/2), discarding
its integer result; selectability then slot for SetNPCSelectability (708/2).
It then falls through to the original shipped `k_pebn_leavhawk` bytecode, retained
byte-for-byte. There is no ExecuteScript wrapper or regenerated original branch.

`python testing/regression/Test-PartyRosterFixture.py` independently interprets
these native stack operations, without the compiler's interpreter. It reproduces
the old wrong-type call and verifies the correction adds only missing test slots,
retains the original crew, balances its stack, reaches the original party picker
with callback `k_pebn_exithawk`, and preserves NPC and planet restrictions. The
original broken NCS is backed up in the ignored fixture for diagnosis. Fully
restart the test game to discard its cached NCS before trying the named save.
Actual gameplay is still awaiting the user's verification.

## Page-arrow mouse hover and hit targets (2026-10-17)

The user confirmed the expanded party screen works and supplied screenshots of
both pages, then reported page arrows retaining their yellow highlight after
mouse-out and having oversized clickable areas. That is gameplay evidence for
the picker and paging, not yet for controller navigation or saved-party reload.

At 1920x1080 the mapped page controls were 222x63 pixels. Each is now a 63x63
square, with its centre and height preserved; at every size the width becomes
`min(mappedWidth, mappedHeight)`. The regression checks both square targets,
non-overlap and panel bounds over all 71 covered layouts.

The controller patch's existing mouse hook, NativeNoteMouseK1 at VA 0x0040C1F6,
also handles the two page arrows. No hook is added. Before native hit testing,
KmrpPartyPageMouseK1 looks only at the manager's old hovered control (offset 8).
It requires the applied roster probe, the party panel vtable 0x00756D28 and one
of the two known page controls. The controls start at panel + 0x9E0C and + 0x9FD0:
stock panel size 0x3A80 + 23*0x454, then native 0x1C4-byte button stride.

If the engine's hit test at the incoming coordinates returns another control or
blank space, the helper clears panel focus only when the old arrow owns it, then
calls native CSWGuiButton::SetActive(0), VA 0x00418E00. Existing portrait focus and
selection remain intact. Controller activity, held pads, programmatic cursor
moves and mouse capture bypass this cleanup. A hover that remains on the arrow
also leaves focus intact. Other buttons and the stock nine-slot panel are excluded.
The helper runs from the controller component's mouse hook; the geometry change
is in KMRP's GUI adapter.

Evidence: local GOG executable disassembly of CSWGuiNavigable::HandleMouseOver
(VA 0x0041A980), manager HandleMouseMove (0x0040C1E0), panel SetActiveControl
(0x0040A630), and button SetActive (0x00418E00); original-image FILE = VA -
0x400000. SetActive updates bit 0 at button+0x44 and resets the button's text
highlight. The production hover helper is exercised with controlled hit/focus
callbacks in party_roster_controller_harness.cpp: both directions, remaining
inside, leaving to blank space, preserving portrait focus, controller/capture
bypass, other controls and absent backend. Updated real hover behaviour still
requires the user's play-test after restarting the controlled game.

## Load-crash correction for the hover helper (2026-10-17)

The first hover update crashed on load. Windows Application Error 1000 recorded
`kmrp-controller.dll`, exception `0xC0000005`, module offset `0x1A83D`. The
matching DLL SHA-256 is
`0F8D1A271EBC0DD6F85C30129CD204F6D25C7EFFB83276DAB7E3E77ACF2BF690`.
Its linker map resolves the fault to KmrpPartyPageMouseK1. Disassembly shows
`mov esi, [edi+0x34]`, immediately after reading the previous hover from manager+8.
The helper called ReadPointer on that control without checking for null.
The actual game registers were not captured; a standalone test with no previous
hover independently reproduced the same access-violation code in the old helper.

The two previously working modules were restored immediately from the verified
arrow-update backups; the save and corrected departure script were left alone.
The crashing DLL/map and measured finding are retained only under ignored
`build/party-roster-check/crash-arrow-hover-20261017`.

The corrected helper first rejects a null old-hover pointer. It then resolves a
live menu panel from the manager's current panel/modal lists and verifies the
party vtable. It compares the previous hover only against that live panel's two
known arrow addresses: it never dereferences the old-hover pointer, so a stale
hover cannot be used to discover an owner. Tests now include null hover during
loading, an unreadable stale address, a missing live panel, ordinary hover exit,
portrait focus preservation and controller/capture guards. The previous tests
covered only a valid hovered control and therefore missed this crash case.

## Match OK's effect on other focus (2026-10-17)

The user confirmed mouse-out now cleared the arrows, but reported that it also
cleared party-member focus. The v2 helper explicitly called
SetActiveControl(panel, nullptr) when an arrow owned panel focus. That was extra
behaviour: native CSWGuiNavigable::HandleMouseOver(false), used by OK, sends the
button its ordinary event 1 and updates only that button's active appearance.
It does not clear the panel's active-control pointer.

The helper now sends the arrow that same virtual mouse-out callback (button
vtable + 0x0C, value 0), instead of clearing panel focus or directly calling
SetActive. The engine handles the button's normal leave callbacks and visual
state. Null/stale-hover and current-live-panel checks from the crash fix remain.
The test verifies panel active-control, current-portrait pointer (panel+0x9E08)
and portrait active flags are preserved while either arrow loses its highlight;
remaining inside, controller/capture bypass and load/teardown cases also pass.
The updated real behaviour still awaits the user's check against OK.

## Copy OK's native focus policy (2026-10-17, supersedes the hover helpers)

The user reported that v3 still cleared party-member focus when entering an
arrow. Calling the same mouse-out method addressed only departure, while the
arrow still entered with different native focus policy. All custom arrow mouse
handling is now removed, including the call from NativeNoteMouseK1. The preceding
sections record failed intermediate designs, not the current implementation.

Primary evidence: Ghidra export of the clean GOG build identified above, party
constructor VA 0x006BFA40, navigable constructor VA 0x0041B8B0, and manager
HandleMouseMove VA 0x0040C1E0. Addresses below are VA; for these original code
sites FILE = VA - 0x400000 (not the appended-section mapping).

| Evidence site VA | FILE | Instruction / meaning |
| --- | --- | --- |
| 0x0041B8CC | 0x0001B8CC | `OR dword ptr [ESI+0x44],4`: navigable constructor sets policy bit 2 |
| 0x006BFF2B | 0x002BFF2B | `AND ECX,0xFFFFFFFB`: party constructor clears it for Back, stored at 0x006BFF2F |
| 0x006BFF52 | 0x002BFF52 | `AND EAX,EBX`, EBX=0xFFFFFFFB: clears Add/Remove's policy, stored at 0x006BFF56 |
| 0x006BFF66 | 0x002BFF66 | `AND dword ptr [EDI+0x44],EBX`: clears OK's policy |
| 0x0040C2AA | 0x0000C2AA | `TEST AL,4`: native mouse manager branches on this policy |

The OK constructor control address is panel+0x28B0; the backend shifts the tail
by (32-9)*0x454 = 0x638C, giving panel+0x8C3C. The existing KPM page buttons
are at panel+0x9E0C and +0x9FD0. They have the ordinary native button vtable
0x0073E658, whose mouse-over virtual method is the same as OK's. The added buttons
retained the navigable default policy bit; the stock constructor never clears
that bit on these extra objects.

KmrpMirrorPartyPageFocusK1 copies exactly `(arrowFlags & ~4) | (okFlags & 4)`.
The complete set of new writes is two four-byte control flags fields:

| Object | Runtime address | Before | After |
| --- | --- | --- | --- |
| Previous page | panel+0x9E50 | native flags, policy bit inherited from constructor | original flags with only bit 2 copied from OK |
| Next page | panel+0xA014 | native flags, policy bit inherited from constructor | original flags with only bit 2 copied from OK |

The helper requires a live party panel, both applied allocation operands, and
native button vtables on OK and both arrows before reading or writing any flag.
It runs after construction from the core's existing tracked-panel frame walk and
the controller's existing prompt update, before that update's cache early return
and regardless of mouse/controller mode. It is deliberately not run at layout
release: the native constructor clears OK's bit only after that callback returns.
No hook site is added. Active/visible/enabled flags, panel and portrait pointers,
event bindings, selection, controller navigation and click callbacks are untouched.
Mouse-in and mouse-out now follow the engine's ordinary path with OK's policy.

Verification: compile/run `testing/regression/party_roster_controller_harness.cpp`
with the Win32 build environment used by Test-PartyRosterGui.py. The harness
compares every byte of a full expanded panel before/after against only the two
permitted bit changes, including both clear/set source policies and repeated
calls. Null/wrong panels, partially applied or absent backend, and unconstructed
buttons are rejected without accessing the expanded tail of a stock-size object.
Both production DLLs build and package validation checks their existing exports
and hook guards. The previous 71-size geometry verification remains applicable;
this change does not alter GUI geometry. The new actual mouse behavior still
requires a game restart and user play-test: select a portrait, enter and leave
OK, then compare both arrows over blank space and another control; repeat paging
and controller navigation.

## Released KPM 0.7.3 installation check (2026-10-17)

**Correction to the coverage assumption:** the preceding working fixture used
this repository's rebuilt roster backend, not the roster binary distributed in
KPM 0.7.3. The user confirmed v4 arrow focus works in that fixture. This does not
establish compatibility with the official released package. A fresh installation
through the official KPM launcher exposed that distinction.

Downloaded the official Windows 0.7.3 ZIP from LaneDibello/Kotor-Patch-Manager;
ZIP SHA-256 `8F69DEA861BFEB7AE23919BC15D9641DB639B16BDADBC8B469AD5E4EA1A8E5C0`.
Its K1 roster manifest is version 0.0.2b, with 53 hooks, versus our rebuilt
0.0.1b/159-hook package. Version numbering alone does not establish source order.
Read the actual released hook table and the source at tag 0.7.3: it allocates
16 reusable view records and two page buttons separately from the stock panel.
Our rebuilt backend instead embeds 32 records and the buttons in a larger panel.
The current detection and arrow addresses target the latter implementation only.

The release omits its required additional GUI. Copied the unmodified file from
`Patches/PartyRosterLimit32K1/Additional/partyselection.gui` at tag 0.7.3 into the
clean test game's Override. It is byte-identical to the GUI already tested:
87,205 bytes, SHA-256
`69B886636934B145FDD9DF7FE4266495872B8917BC447114A2F0F0274B5135A4`.
It contains all 32 GUI slot tags even though the released backend binds 16 view
records. This was a manual supplement, not successful GUI deployment by KPM.

Official KPatchLauncher.exe applied current KMRP, controller and the untouched
released roster package using its `--patches ... --deployment proxy` path. It
returned zero and launched the clean GOG copy. All three installed DLLs match
their respective packages, all 119 configured hook spans are disjoint, and the
running process loads all three modules plus the official runtime/proxy. Global
KPM settings and the previous fixture were not changed. This is an install/start
check; the real party screen in this installation has not been play-tested.

ReadProcessMemory on that process confirmed both panel-allocation operands:

| VA | FILE | Bytes | Live value | Required by current adapter |
| --- | --- | --- | --- | --- |
| 0x0062DE20 | 0x0022DE20 | 4 | 0x3A80 | 0xA194 |
| 0x00632E50 | 0x00232E50 | 4 | 0x3A80 | 0xA194 |

Same clean GOG build/address convention as above; these are original image
addresses, FILE = VA - 0x400000. The current adapter therefore correctly stays
inactive for the release; its stock-sized panel must not be accessed at expanded
offsets. Styling, arrow focus and controller navigation for the released external
view require a separate compatibility path. This remains an open gap. No
production code or executable validation was loosened for this check.

Reproduce: use the official 0.7.3 Windows ZIP, install the three packages via its
launcher in a fresh supported GOG copy, supply the missing unchanged source GUI,
and inspect the two live operands after launch. Local installation commands,
hashes, before-executable backup and results are retained under ignored
`build/party-roster-kpm-check/`. Its original-crew save opens the normal Ebon Hawk
departure flow and contains no injected extra test companions.

## Runtime generation and named live controls (2026-10-17)

The user requested the Xbox-HUD principle: produce the presentation at runtime
and work with native controls. The roster backend continues to own companions,
pages, selection, callbacks and save serialization. No backend source/DLL is
changed. This section supersedes the embedded-panel-only assumptions above.

### Activation and generation

The rebuilt backend remains recognized by both applied allocation operands.
Official 0.7.3 is recognized by the following live effects, together with a loaded
`party-roster-limit-32-k1.dll` exporting `FinishPartySelectionLayout`. These are
activation checks only; no panel size or pointer is inferred from them. The
release's unmodified hook table supplies the bytes below (same GOG build/hash
and original-image VA/FILE convention stated above):

| VA | FILE | Bytes | Vanilla | Applied release | Purpose |
| --- | --- | --- | --- | --- | --- |
| 0x0056554C | 0x0016554C | 1 | 09 | 20 | NPC-count limit |
| 0x005665DD | 0x001665DD | 1 | 09 | 20 | Second NPC-count limit |
| 0x006BFEF6 | 0x002BFEF6 | 1 checked | E8 | E9 | Applied layout hook entry |

The released DLL is 1,403,392 bytes, SHA-256
`76E6CFBF763DAC5BC6F3A127288DA2700861E4A74442732D112E0318E633E8D6`.
Package inventory finds only manifest, hooks and DLL. Its PE32 resource directory
has RVA/size zero and its file contains neither the source GUI bytes nor a raw
GUI header. This alone would not exclude arbitrary compressed data, so the tag
0.7.3 source was checked too: `BindNamedControl` calls the engine's InitControl
against the loaded party GUI; its DLL initialization does not unpack GUI assets.
The manifest explicitly requires the supplied GUI. Thus this package does not
provide the missing file through a KMRP-style embedded layout bank.

AdaptPartyRosterK1 reads the current size's ordinary KMRP party GUI. When a source
Override GUI exists, the validated adapter still preserves its functional fields.
When absent, KmrpGeneratePartyRosterGui clones this layout's native control
**definitions**, assigns the public roster tags/IDs/navigation, then passes the
result through the same geometry/style adapter. There is no bundled proprietary
roster GUI and no Override write. Invalid supplied input is rejected rather than
silently replaced by generated input. With no active roster effects, the ordinary
party GUI remains in use.

Generation uses 32 slot triplets, two page definitions, and the original shared
controls. Physical index is `i % 16`; canonical slot extent is
`(54 + 68*(i%4), 109 + 65*((i%16)/4), 63, 63)`, transformed by the earlier fitted
map. Existing slot 0..8 IDs remain; for slots i>=9, character/button/unavailable
IDs are `39 + 3*(i-9) + {0,1,2}`. Previous/next IDs are 108/109. Four-column MOVETO
links wrap within each row; first-row Up wraps to the bottom row; bottom-row Down
goes to previous/next. Captions are literal `<`/`>`, with no controller badge fill
copied from OK. All these generated functional fields are compared with the
unmodified official source GUI at every covered size.

### Named controls, native focus, lifecycle

The existing ReleaseGff callbacks now resolve `BTN_DONE`, `BTN_ACCEPT`, `BTN_BACK`,
`BTN_PAGE_PREV`, and `BTN_PAGE_NEXT` while the native layout still exists. As in
PlaceCueByReferenceK1, a temporary label asks the engine's InitControl binder for
the tag's ID with `filed=0`; it is destroyed immediately, and any probe entry is
restored from the live control-array snapshot. Only the five IDs are retained.
No pointer to a temporary or mod-owned control is cached. The panel's own control
list resolves the actual control by its stored ID on each use, with bounds, vtable, ID and parent
checks. Native base-panel teardown erases the binding record.

| Native field | Offset | Use |
| --- | --- | --- |
| Panel control pointer array | +0x20 | Search only this live panel's compact list for the stored ID |
| Panel control array count | +0x24 | Require 1..512 entries; IDs can exceed this count |
| Panel loaded GFF | +0x2C | Bind names only before native release |
| Control owner panel | +0x34 | Require the expected owner |
| Control flags | +0x44 | Copy only OK's bit 2 into both arrows |
| Control ID | +0x50 | Require equality with the resolved ID |

The current runtime writes are the two actual arrow controls' four-byte flags
words; `(flags & ~4) | (okFlags & 4)` preserves every other bit. Their addresses
come from names/IDs, not an embedded-panel offset. Existing core/controller frame
paths apply this policy after construction, when the native OK policy is final.
Controller prompt painting and its focus-fallback check resolve the same named
action controls. Its 3x3 navigation repairs stand down only with both page controls
actually bound. Stock party-screen prompt offsets remain the stock fallback.
There are no new hook sites and no custom mouse-in/out callbacks.

### Verification and remaining play coverage

`Test-PartyRosterGui.py` now exercises both supplied and generated paths at all
66 resource sizes plus five production blends. It compares all generated
functional fields against the official source, all generated extents against the
supplied-layout path, positive nonoverlapping bounds on each page, original
portrait/page content, malformed input and duplicate IDs. The runtime cache test
covers missing GUI generation, no source-file write, stock fallback, supplied
source preservation and size round trips. The controller harness uses a tiny
panel with five separately allocated controls at arbitrary IDs; it verifies named
prompt targets, ownership/lifecycle guards, applied/partial/missing backend
checks, and byte-for-byte preservation except the two allowed focus bits.

Both production modules build. Package checks retain 28 core and 38 controller
hooks with their exports/clean GOG guards; controller package/HUD checks pass.
The official 0.7.3 launcher reinstalled both updated packages with its unchanged
released roster package in the isolated game and launched successfully. The manual
Override GUI was backed up and removed first. The live private cache then held a
1920x1080 GUI with 32 NPC controls and 63x63 arrows, while Override had no party
GUI. All three installed DLLs match their packages. This confirms real runtime
generation on the released backend, not yet the interactive party-screen result.

Local before/after hashes, rollback copies, install log and cache proof are under
ignored `build/party-roster-kpm-check/`. The original-crew save has no injected
NPCs; `KPM RELEASE - Extra slots` uses the previously corrected controlled
occupants to exercise both pages with the **released** roster implementation.
Remaining checks: open that save's normal departure screen, compare both arrow
hover transitions with OK, select across both pages, use the controller and test
a resolution round trip and save/reload. Steam and source game/saves are unchanged.

## Released-view list and portrait corrections (2026-10-17)

User play-test of the first runtime-generated build showed missing portraits and
arrow focus differing from OK. The generated GFF was compared with the adapted
unmodified source GUI: all control fields (including visual fields and structure
types) and root fields match; only resource/list packing order differs. The
initial tests had checked geometry and functional fields, not actual texture
assignment in the released native view.

Two distinct causes were measured:

1. The mod's `DetachControl` uses DeleteAt; AddControl then appends controls back.
   Its render list is compacted/reordered, not indexed by ID after paging. Live
   count was 96, while previous/next kept IDs 108/109 at positions 60/61; OK ID36
   was at position9, Add ID38 at11 and Back ID37 at10. Initial lookup assumed
   `controls[id]` and therefore found no action controls. Name capture now checks
   actual stored IDs within the construction snapshot; frame lookup scans this
   **single panel's bounded list**, comparing the control's own ID and owner.
   The controller harness now compacts its list to five entries in reverse order,
   keeping arbitrary IDs up to109, and proves focus/prompts still resolve.
   Live v2 flags: OK=0xA, previous=0x2, next=0xA. Bit2 is clear on all three;
   the real native-policy fix is therefore active on the released implementation.
2. All live available portrait labels had an empty fill resref. Released source
   InitializePatchApi selects `CSWSObject::GetPortrait`, used by SetAvailableViewRecord.
   Clean-GOG disassembly shows it reads object+0x20, while the creature override
   reads the stats pointer at creature+0xA74, then its portrait at stats+0x16E.
   Read-only live lookup through the server's object-ID table confirmed the
   difference for seven stock companions. For example Bastila's base resref was
   empty but the creature resref was `po_pbastila`; Canderous was
   `po_pcanderous`, Carth `po_pcarth`, Juhani `po_pjuhani`, Mission `po_pmission`,
   T3 `po_pt3m3`, and Zaalbar `po_pzaalbar`.

Primary code sites, same clean GOG build and FILE=VA-0x400000:

| VA | FILE | Native operation |
| --- | --- | --- |
| 0x004D01C0 | 0x000D01C0 | Base GetPortrait copies 16 bytes from object+0x20 |
| 0x004F8370 | 0x000F8370 | Creature GetPortrait follows creature+0xA74 to stats+0x16E |
| 0x004AE770 | 0x000AE770 | Server GetCreatureByGameObjectID, preserving its type check |
| 0x004AEE70 | 0x000AEE70 | Server GetPartyTable |
| 0x00414C00 | 0x00014C00 | Native border SetFillImage loads the resref's texture |

```text
004D01C4 add ecx,0x20          ; base object's portrait field
004F8370 mov eax,[ecx+0xA74]   ; creature's stats
004F837B add eax,0x16E         ; creature portrait resref
```

KmrpPartyPortraitsK1 repairs only presentation through native APIs. For an active
bound roster panel and its loaded released implementation, it gets logical NPC
object IDs through the roster's public GetNPCObject32 export with create/recovery
both0, then uses the engine's checked creature lookup and creature portrait getter.
The exact getter prologue is checked before calling it. No roster DLL bytes,
private mod-state offsets, save data or callbacks are changed. A nonempty existing
portrait fill is retained, and already repaired labels are not loaded again.
The native record is checked readable and must have the party-record button
vtable, expected owner and self back-pointer; its character label must have the
native label vtable, owner and visible bit. Empty extra slots (logical>=9 and
native available bit clear) lose only their button's drawn bit, hiding the default
white frame. Original unavailable crew silhouettes are retained. The real native
record fields (shared by the stock and external allocations) are:

| Field | Native record offset | Presentation use |
| --- | --- | --- |
| NPC button | +0 | Confirm vtable0x756BB8 and owner |
| NPC record back-pointer | +0x58 | Require self |
| Character label | +0x308 | Confirm label vtable0x73E5B8 and owner |
| Character border params | +0x378 | Set native fill for empty available portraits |
| Character fill resref | +0x3B8 | Preserve any existing name |
| Record state flags | +0x448 | Available bit0 |
| Logical slot | +0x450 | Query mod API without assuming which page is shown |

This is the native CSWGuiPartySelectionData layout, not the mod's allocation or
panel layout. The controller harness checks one repair, no repeated texture load,
hiding empty extra frames and retaining stock unavailable silhouettes. The next
user screenshot confirmed portraits were now visible, but exposed incorrect
brightness. Texture assignment alone was therefore insufficient; see below.
The original v1 failures and v2 process dumps are retained under ignored
`build/party-roster-kpm-check/`; the previous claim that ID equals list position
was incorrect for this released view and is explicitly superseded here.

## Released-view portrait brightness correction (2026-10-17)

The v3 user screenshot showed available portraits dark except the selected extra
Canderous, while unavailable silhouettes retained bright white frames. Read-only
process inspection of that screen confirmed nine available records: eight
unselected portraits had alpha0.25 and selected logical slot9 had alpha1. All
unavailable normal button borders had alpha1. The released source explicitly
writes portrait alpha from `selected`, rather than selectability, and overwrites
the zero normal-border alpha set by native SetSelected(0) with1 for missing NPCs.
The earlier texture-only repair left both mistakes visible.

Disassembled from the same 4,042,752-byte clean GOG executable identified above;
addresses below are VA, FILE=VA-0x400000. No executable bytes are modified by this
correction. The native OnPanelAdded loop keeps ESI at record+0x8C, so its
`[esi+0x2F8]` is the character label's border alpha at record+0x384.

| VA | FILE | Measured native behavior |
| --- | --- | --- |
| 0x006BF19F | 0x002BF19F | Push logical slot before native GetNPCSelectability at0x005637C0 |
| 0x006BF1A9 | 0x002BF1A9 | Selectable: write float1 at record+0x384 |
| 0x006BF1BE | 0x002BF1BE | Unselectable: write float0.25 at record+0x384 |
| 0x006BE370 | 0x002BE370 | SetSelected changes selection border/state; never portrait alpha |

```text
006BF1A0 call 005637C0           ; query selectability, not selected state
006BF1A5 test al,al
006BF1A7 je 006BF1B5
006BF1A9 mov [esi+2F8],3F800000  ; bright selectable portrait
006BF1BE mov [esi+2F8],3E800000  ; dim blocked portrait
```

The existing presentation pass now obtains selectability through the released
roster's GetNPCSelectability32 export, preserving its extra-slot state. Every
visible available character label receives native alpha1 or0.25 independently
of selection. Missing records have only their normal selection-border alpha
(record+0x8C) restored to0; original unavailable labels remain unchanged, and
empty extra slots retain the preceding drawn-bit repair. Selected-state fields,
highlight borders, focus flags, colors, hover callbacks and party membership are
not changed. This runs in both existing core/controller frame paths and needs
no new hooks or resource generation changes.

The focused native harness covers all four selected/unselected and selectable/
unselectable combinations with already populated textures, asserting that every
record byte except portrait alpha remains unchanged. Missing stock records are
compared byte-for-byte except normal-border alpha; empty extras still hide.
Both modules build and package checks pass. The user confirmed the installed
brightness correction looks correct on the official released-backend fixture,
then closed the game before a post-install live alpha reading. Explicit arrow
hover, controller, cross-page save/reload and resolution-round-trip results for
this build remain unverified. To reproduce,
load the released-backend Extra slots fixture, leave the Hawk, check both pages,
add/remove a companion and verify that choosing them changes their selection
border while all selectable portraits retain full brightness. Also compare
arrow hover entry/exit with OK and exercise controller navigation.
