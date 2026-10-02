# macOS keyboard navigation: restored layout targets

This reference follows [the documentation standard](../docs/documentation-standard.md).
This records the loader repair and follow-up keyboard/mouse fixes. The user verified main-menu and top-level Options fixes at 1920x1200, then
reported unreachable submenu controls. The user confirmed the shared live-graph
repair works, then requested Left/Right within horizontal button rows. That
row-navigation refinement and Feedback list boundary handoff are user-confirmed. No commit has been made.

## Build and address convention

Aspyr KOTOR 1.4.0, x86_64, clean SHA-256
`c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71`.
The diagnostic run used the KPM-load-command executable, 6,324,304 bytes,
SHA-256 `5294ae4f8390dcee54473028a69546128a6d4c2308bd355a18b55692d6748e48`.
Addresses below are preferred Mach-O VAs; these original text sites have
`FILE = VA - 0x100000000`. No on-disk game executable changes are made by this fix.

## Measured failure, 2026-10-02

At 1920x1200, read-only probes at the common control loader, navigation resolver,
navigable event handler and focus setter captured:

| New Game, control ID 7 | Before fix | With loader fix |
| --- | --- | --- |
| Parsed MOVETO UP / DOWN | 12 / 6 | 12 / 6 |
| Slots before panel resolves IDs | 0 / 0 | 12 / 6 |
| Down event | `0x3e`, value 1 | `0x3e`, value 1 |
| Result | focus moved to ID 0 | focus moved to ID 6 |

The clean Mac navigable, button, slider and list loaders fetch the MOVETO
struct, but do not read its four fields before calling the base control loader.
The resolver interprets the zero-initialized slots as control IDs and replaces
all four with control 0's pointer. Resource-only tests missed this: MOVETO in the
GUI file was correct. The user confirmed main-menu Up/Down and wraparound work
with the restored loading. This is not evidence that every menu is fixed.

## Hook and original engine helpers

| VA | FILE | Bytes / role |
| --- | --- | --- |
| `0x1004a4b78` | `0x4a4b78` | Hook 6 bytes `55 48 89 e5 41 57`: common control Load entry; rdi control, rsi GFF, rdx control struct |
| `0x1003620d4` | `0x3620d4` | Original GetStructFromStruct; called, not patched |
| `0x100362462` | `0x362462` | Original ReadFieldINT; called, not patched |
| `0x10049e3f0` | `0x49e3f0` | Original navigation resolver, no longer hooked in production |
| `0x1004a4972` | `0x4a4972` | Hook 6 bytes `55 48 89 e5 41 57`: repair incomplete live vertical links and remember pointer position on keyboard navigation |
| `0x1004a035e` | `0x4a035e` | Hook 6 bytes `55 48 89 e5 41 57`: consume stationary mouse samples after arrows |
| `0x1004a077b` | `0x4a077b` | Consumed exit: original `pop r15; pop rbp; ret`, not patched |
| `0x100028581` | `0x28581` | Hook 6 bytes `55 48 89 e5 8b 0f`: update default cursor clamp from active viewport |
| `0x1002c891a` | `0x2c891a` | 8-byte simple patch `41 80 a7 98 11 00 00 fb` to `41 80 8f 98 11 00 00 04`: set Close mouse-focus bit 4 instead of clearing it |
| `0x10001e36c` | `0x1e36c` | Original desktop bounds reader, called not patched |
| `0x10049de24` | `0x49de24` | Original focus setter, unmodified |

`navigation.cpp` uses virtual slot `+0x98` to obtain the navigable subobject;
non-navigable controls are left alone. Its pointer-sized slots at `+0x88`,
`+0x90`, `+0x98`, `+0xa0` receive UP, LEFT, DOWN, RIGHT signed IDs.
Missing fields use -1. The existing resolver performs ID bounds checks and
turns these IDs into pointers once the panel is fully loaded. KPM validates the
hook's original bytes and preserves registers/flags while running its displaced
prologue. This hook is in the required layout component, including builds with
controller support disabled.

The event-handler jump table independently establishes the order:

| Direction | Keyboard event | Retained pad event | Navigation slot |
| --- | --- | --- | --- |
| Up | `0x3d` | `0x31` | `+0x88` |
| Left | `0x3f` | `0x2f` | `+0x90` |
| Down | `0x3e` | `0x32` | `+0x98` |
| Right | `0x40` | `0x30` | `+0xa0` |

## Verification and limitations

`testing/regression/Test-MacNavigationTrace.py before.log after.log` compares
parsed GUI IDs with live resolver slots and immediate keyboard focus changes.
The first capture found incorrect slots in 18/18 navigable controls. The fixed
capture matched 25 controls and 52 keyboard transitions across two panels.
These counts describe that capture, not exhaustive menu coverage.

To reproduce the trace, instrument the above loader/resolver/handler/setter
entries without changing their behavior. The checker documents the line formats
in its regular expressions. At Load, read MOVETO via the original GFF APIs; at
Resolve, read each navigable control's four slots before ID conversion; at the
handler and setter record the event and old/new control IDs. Do not log after
conversion and compare pointers against resource IDs.

## Follow-up Options and mouse failures

The supplied `optionsmain.gui` has Sound DOWN=-1 and all Close directions=-1.
The first repair connected only that screen. **Correction:** after initially
confirming the top-level fix, the user reported that Gameplay, Graphics and
other submenus still could not reach Default, Close or Controller Layout. The
resource inspection showed those footer buttons disconnected, and the Gameplay
cycle omitted Controller Layout. The menu-specific resolver repair was removed.
A proposed table of per-menu ID routes was also discarded before live testing.

The current shared navigation handler validates the live Up/Down graph on each
pressed arrow. It enumerates the panel's bound controls (array +0x30,
count +0x38), requiring a matching ID and panel owner, visible/selectable/enabled
flags, a positive extent, a navigable subobject, and registered input handlers
(control +0x58/+0x60), or a native list with selectable navigable rows. This follows the existing Mac controller navigation's
handler-based eligibility rule; passive description controls are excluded.

When every eligible control occupies its own row and both vertical directions
already form complete cycles, the handler keeps their custom order. Otherwise it
sorts controls by rendered TOP, LEFT, then ID and groups equal-TOP controls into
rows. Up/Down chooses the adjacent row (with wraparound), selecting the control
whose horizontal center is closest. Left/Right cycles within a shared row.
Single-control rows keep their horizontal links. Sliders retain their native horizontal links even on shared rows. Lists can hand
off horizontally to a neighboring control.

Links are live pointers; an existing link is never dereferenced unless it matches
an eligible bound control. This also repairs raw IDs left in controls bound after
ResolveNavigation, including Controller Layout. Hidden, disabled and removed
controls are excluded on the next arrow. Native slider/list handling runs before
a direction falls through to this shared navigable handler. No menu ID route or
resolution constant is used. The user confirmed the shared repair reaches the
submenu controls, then requested the row distinction after the first candidate
cycled footer buttons vertically. The row refinement and Feedback boundary handoff pass automated checks and the
user confirmed them in play. This is not exhaustive coverage of all game panels.

The standalone regression exercises arbitrary panel and control identities,
disconnected cycles, a late-bound control with a raw ID, unavailable and passive
controls, equal-height footer buttons, preservation of complete custom cycles,
native slider horizontal links, row-aware footer directions, and stationary-mouse handoff:

```sh
clang++ -std=c++17 macos/patches/kmrp-layout/navigation.cpp \
  testing/regression/Test-MacOptionsNavigation.cpp -o /tmp/kmrp-options-test
/tmp/kmrp-options-test
```

The original hover trace captured keyboard focus moving from control 4 to 7,
then a mouse sample at unchanged coordinates (392,420) immediately returning
focus to 4. The event hook remembers the manager and pointer coordinates on
pressed keyboard arrows; the mouse hook consumes matching stationary samples.
Real movement or mouse capture restores native handling. The user confirmed
arrows work in the follow-up test; broader list/slider coverage is still pending.

**Corrected during testing:** the first consumed exit incorrectly jumped directly
to `ret`. KPM replays the six stolen prologue bytes before testing EAX; that path
must therefore execute `pop r15; pop rbp; ret` at `0x1004a077b`. The incorrect
candidate closed the diagnostic process on its first arrow. The corrected path
subsequently handled repeated Up/Down events in the main menu and Options.

The pointer test at 1920x1200 found Close at (747,1025,426,70), while the pointer
stopped at (955,981). A probe at the shared clamp captured input (930,1064) with
bounds (0,0,1512,982). The input had already been converted to render coordinates,
but the clamp still used the Mac display's logical point bounds. Close's flags
were 0x0a; its absent bit 4 was initially suspected, but the coordinate evidence
establishes an earlier obstacle. After correcting the bounds, the user photographed simultaneous yellow highlights
on Sound and Close. The trace recorded Sound as active and Close as hovered.
The ctor clears bit 4 at `0x1002c891a`; the native mouse handler at
`0x1004a068c` requires bits 4 and 8 to transfer focus. The new simple patch sets
bit 4 for Close so hovering it can clear the previous active button. This is a
separate correction for the double highlight, not the coordinate-clipping fix.
The user confirmed the corrected behavior in the subsequent diagnostic run.

The shared clamp hook compares its rectangle at `0x100678280` against the original
desktop bounds. For that default rectangle, it substitutes the active GUI
manager's viewport width/height at +0xa4/+0xa6 (manager pointer at `0x100677ce0`).
The original clamp then limits X to [0,width-1] and Y to [0,height-1]. Explicit
restricted rectangles and startup before a valid viewport retain native behavior.
No 1920x1200 constant is used. **Rejected candidate:** replacing only the call at
`0x100026535` missed the second cursor path; the pointer still stopped at 981.
Both paths reach `0x100028581`, where the current hook is installed. The next
probe measured (977,1058) inside Close with Close as the hovered control,
confirming the corrected extent. The user then confirmed Close works with the final combined changes. XP text is a separate unresolved task.

Manual verification: traverse the five main-menu buttons in both directions,
including wraparound; enter Options, reach and activate Close; leave the pointer
over a button and navigate away with arrows; move and click the pointer again.
Check sliders and list boxes before claiming general navigation coverage.


## Shared list boundary and full resource audit

The native list handler `0x1004a8a38` consumes vertical arrows and falls through to
base Control, not Navigable. The shared six-byte entry detour (FILE `0x4a8a38`,
original `55 48 89 e5 41 57`) calls `KmrpNavigateListBoundary` and uses the same
consumed epilogue `0x1004a077b` as the mouse hook. Rows are at list +0x348,
count +0x350, selected index (signed short) +0x37a. Interior Up/Down stays native;
at the first/last row it follows the repaired panel link. Left/Right can cross
between adjacent lists/buttons; sliders retain their own horizontal handling.

`Test-MacGuiNavigation.py --game GAME_ASSETS --report REPORT_JSON` enumerates
core GUI resources with Override precedence and exercises the compiled production
graph repair against their control geometry. On 2026-10-02: **87 GUI resources,
67 menu layouts, zero structural failures**. Passive text lists (prototype kinds
4/5) are excluded. Every candidate is simulated visible/enabled; this is not a
live audit of every menu state, specialized panel dispatcher or child control.
The additional horizontal list handoff is unit-tested and loaded in the diagnostic
copy, but has no user confirmation across all affected screens.

The resolution-menu acceptance fix touches separate comparison operands and does
not load MOVETO, connect disconnected controls, change mouse focus or resize the
cursor clamp. It does not supersede these repairs. See the
[Windows port comparison](macos-resolution-port-audit.md).
