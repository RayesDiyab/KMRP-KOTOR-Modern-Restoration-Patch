# F5: the party portrait repair with KMRP alone

> **Documentation standard.** This document follows
> [`../documentation-standard.md`](../documentation-standard.md).

**Kind: fix report** (issue 82, finding F5 of
[`../cleanup-audit-1.6-findings.md`](../cleanup-audit-1.6-findings.md)). Done 2026-11-01,
uncommitted. Found while fixing F1
([`F1-kmrp-without-controller-code.md`](F1-kmrp-without-controller-code.md)).

## The problem

KMRP repairs a fault of another mod, **Party Roster Limit 32** (`party-roster-limit-32-k1.dll`,
a KOTOR Patch Manager patch that lets the party roster hold more companions). On the roster's
party selection page the mod leaves a companion's portrait empty: it takes the picture from
a field of the base object that is empty for them. `KmrpPartyPortraitsK1` fills each slot
with the companion's portrait as the game itself finds it: which character sits in a slot,
and whether they are selectable, from the two functions the mod exports
(`GetNPCObject32`, `GetNPCSelectability32`), then the game's own portrait getter
(`0x004F8370`), then the slot's picture. Nothing of the mod's internal memory is read, and
without the mod nothing happens.

It acts only on a page whose five buttons it knows by their IDs (OK, Add/Remove, Back, the
previous and the next page): that is how it tells the roster's page from any other party
screen. The same IDs serve a second fix, `KmrpMirrorPartyPageFocusK1`, which gives the page
buttons OK's focus rule.

**Until 2026-11-01 only the controller patch found those IDs**, in its ReleaseGff hook
(`CapturePartyRosterBindingsK1`, `K1NativeJoystick.cpp`), by binding a probe control per tag
while the panel's `.gui` still existed. `kmrp.dll` has no such hook, so its map stayed
empty: `KmrpCoreGuiWorkK1` called both fixes every frame, and both returned at once. With KMRP
alone the portraits stayed empty. The maintainer, 2026-11-01: "this should work with KMRP
alone. This should be separate from the controller patch."

## Where KMRP could find them

Measured on the clean executable (capstone, `build-inputs/swkotornopatch.exe`):

| Site | Why not |
| --- | --- |
| `0x0040B8F0`, the entry of `CSWGuiPanel::StopLoadFromLayout`, where a panel's constructor ends | Scaled Kotor 1.3.1 hooks it; KOTOR Patch Manager allows one patch per address (`tools/build_controller_kpatch.py`, 2026-10-05) |
| `0x00409B80`, the entry of `CRes::Release` | the controller patch's (`NativePanelLoadedK1`) |
| `0x00409B81` (`mov ecx, [0x7A39E8]`, 6 bytes) | inside the 7 bytes the controller's hook above takes, so the two would overlap |
| `0x0040B8F9` (`mov ecx, [esi+0x2C]`; `call 0x00409B80`) | the call is relative, and KOTOR Patch Manager's trampolines do not move a relative operand |
| `0x0040B901` (`mov ecx, [esi+0x2C]`; `test ecx, ecx`, 5 bytes, clean) | after `CRes::Release` at `0x0040B8FC`: binding a probe by tag is no longer safe there |

So no new hook. KMRP needs none: it already hooks the control binder (`0x0040B930`,
`KmrpPanelControlK1`), which records every control a panel binds, by its tag, with the
control's class (`K1RuntimeLayout.cpp`, `Panel::controls`), and the control destructor
(`0x00419A20`, `KmrpControlDestroyedK1`), which takes a destroyed control out of those
records. A control bound to a tag gets the tag's ID from the layout, which is what the
controller's probe reads back. So KMRP reads the five IDs from its own records.

## The change

- `KmrpCapturePartyIdsK1` (`K1PartyRosterState.h`, inline): for the roster's page only
  (vtable `0x00756D28`), with the mod active (`KmrpPartyRoster32ActiveK1`), and once per
  panel, the ID of the control recorded for each of the five tags, each control still this
  panel's (`+0x34`) and its ID in range; all five, or nothing is recorded.
- `CapturePartyRoster` (`K1RuntimeLayout.cpp`) asks it from `PlaceLists`, on the panel's frames,
  before the two fixes, with its records as the lookup: a control whose class is no longer
  the one recorded is taken as gone.
- `KmrpPanelDestroyedK1` forgets the panel's IDs, so a panel made later at the same address
  finds its own.
- The controller patch is unchanged: it keeps its own capture and its own copy of both fixes,
  so it still repairs the portraits without KMRP. With both, each module repairs from its own
  map; the second finds each portrait filled (`KmrpPresentPartyRecordK1` returns when the
  picture is set) and the page buttons' rule already copied, and changes nothing.

## How it was checked

- `testing/regression/party_roster_controller_harness.cpp` (run by `Test-PartyRosterGui.py`),
  on its fake roster page with separately allocated buttons and arbitrary IDs: KMRP's capture
  finds exactly the IDs the controller's tests use, and records nothing when a tag has no
  control, a button is not the panel's, an ID is out of range, the mod is not active, or the
  panel is another screen; and it leaves a panel already known alone. Passed, with the rest of
  the test (71 resolutions, the portraits and page fills).
- `kmrp.dll`'s map links `KmrpCapturePartyIdsK1`; the full build passed; `Test-LiveLayout`,
  `Test-ModCompatibility` (630 checks), `Test-HudOptions`, `Test-TextOptions`, `Test-TextRows`,
  `Test-NativeTextLayout`, `Test-KpatchSource`, `Test-RuntimeKpatch`, `Test-ControllerKpatch` passed.

**Not tested:** in a game, with the Party Roster Limit 32 mod installed, with KMRP alone or
with both patches. Whether the mod binds its page buttons through the game's binder, which
this relies on (the controller's probe does not need it), is read from the code, not seen:
if it does not, KMRP's capture finds nothing and the page stays as it was, never wrong.
