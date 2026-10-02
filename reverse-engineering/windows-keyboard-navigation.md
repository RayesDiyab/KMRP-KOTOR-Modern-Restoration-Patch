# Windows keyboard menu navigation

Reference for the source port of the Mac row and list-boundary repair. Read the
[documentation standard](../docs/documentation-standard.md) and
[Mac measurements](macos-keyboard-navigation.md). This is not yet a verified fix
for the maintainer's physical-keyboard failure.

## Builds and measurements

Static disassembly uses clean CD 1.03, 4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
Original-code addresses are preferred VA; `FILE = VA - 0x400000`.
GOG has the same program bytes; Steam's decrypted program uses these hook sites.
Variant packaging checks are not live input tests.

The live 3440×1440 measurement on 2026-10-03 used CD 1.03 with the large-address
flag: 4,042,752 bytes, SHA-256
`CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889`.
The installed PR #27 module was 246,784 bytes, SHA-256
`7050BD844F3FC6276E75A3B67231A5D28152A71934B1D505879CECB2B9BF2452`.
These measurements did not change the live executable or installed module.

x32dbg read main-menu panel `0x040C12E0`, manager `0x040159D8`, and active New
Game `0x040C16D0`. New Game's Up pointer was Quit `0x040C2364`; Down was Load
Game `0x040C1894`. A temporary scratch stub on the GUI thread called the native
navigable handler with `(New Game, 0x3E, 1)`. Focus became Load Game and remained
there at the next GUI frame. Registers/flags were preserved and scratch memory
freed. This proves the native route, not physical-key delivery.

**Rejected assumption:** this Windows menu already loads correct MOVETO links;
the Mac zero-slot loader repair is not copied.
**Measurement correction:** automated Down reached the render window's
`WM_KEYDOWN` at `0x00402800` with wParam `0x28`, but lParam `0x01000001` lacked
a scan code. No Down record was captured at the DirectInput matcher. Handled
UI Automation exceptions also paused the game. This is not evidence that a
physical keyboard stops at that point. Physical-key reproduction remains pending.

## Source behavior

[K1KeyboardNavigation.cpp](../src/controller-native/K1KeyboardNavigation.cpp)
adapts the Mac repair to Windows layouts and `__thiscall` callbacks. Manager
input maps PC arrow events `0xB6..0xB9` to `0x3D..0x40` at
`0x0040CA1D/24/2B/32`. The manager's table at `0x0040CC20` supplies those arms;
raw DirectInput scan codes are a different namespace. KMRP's controller
directions use `0x2F..0x32`, and its analog descriptions use `0x3B/0x3C`.
Only pressed keyboard arrow aliases enter the new traversal.

The repair computes neighbours locally; it never rewrites shared MOVETO links.
Eligible controls belong to the panel and ID slot, are visible/selectable/enabled,
have positive extents, and have handlers or selectable list entries. Complete
vertical cycles retain their custom resource order when controls do not share a
row. Otherwise Up/Down changes rows, wraps, and chooses the nearest horizontal
centre; Left/Right walks within a row. Current object coordinates drive the rule,
without menu IDs, resolution constants, or a different scale formula.

Sliders retain native input on their sliding axis. Lists retain native interior
selection and initialization; at a selectable boundary, focus can leave the list.
Handled directions run the old control's base handler once and become the unused
event `0x41`, preventing a second traversal.

The stationary-mouse latch records manager, panel, expected active control, mouse
position, and panel/modal counts. Movement, GUI capture, an auxiliary 3D cursor
receiver, changed panel counts, or a controller-driven focus change releases it.
The auxiliary receiver retains native mouse handling; its in-game states have
not been tested. Only GUI hit testing is skipped;
coordinate storage and 3D cursor work already ran. This ported mechanism has
synthetic coverage; a live Windows stationary-pointer failure remains unmeasured.
The Mac desktop-point clamp and Close-flag patch are not copied without Windows
evidence. Controller spatial traversal and its events remain unchanged.

## Hook and field inventory

All three hooks are core (`install = "always"`) with either controller option.

| VA | FILE | Size/original bytes | Purpose |
| --- | --- | --- | --- |
| `0x0041A9D0` | `0x1A9D0` | 6: `8B 44 24 08 85 C0` | Navigable keyboard repair; handled event becomes `0x41` |
| `0x0041CE20` | `0x1CE20` | 6: `8B 44 24 08 85 C0` | List keyboard boundary handoff; handled event becomes `0x41` |
| `0x0040C24E` | `0xC24E` | 5: `8B 4E 10 85 C9` | Stationary GUI mouse sample; consumed exit `0x0040C55A` |

Arrow/list detours restore all registers and replay the original EAX load/test.
They modify event stack slots through pointers, without consumed exits. The mouse
detour excludes EAX from restore; its stolen instructions preserve that answer
and ESP, and its consumed exit uses the existing register/local-stack epilogue.
The normal builders verify original bytes; run the
[stolen-byte checker](../tools/check_hook_stolen_bytes.py) as well.

| Object | Offset | Meaning |
| --- | --- | --- |
| Control | `+0x04/+0x08/+0x0C/+0x10` | left/top/width/height |
| Control | `+0x34/+0x38/+0x3C` | panel/events/event count |
| Control | `+0x44/+0x50` | flags/ID |
| Navigable | `+0x5C/+0x60/+0x64/+0x68` | Up/Left/Down/Right |
| Control vtable | `+0x3C/+0x4C` | input/navigable cast |
| Panel | `+0x18/+0x1C/+0x20/+0x24` | manager/active/controls/count |
| Panel vtable | `+0x08` | SetActiveControl |
| List | `+0x29C/+0x2A0/+0x2C6` | rows/count/selection signed short |
| Manager | `+0/+4/+0x10/+0x24` | X/Y, GUI capture, auxiliary 3D cursor receiver |
| Manager | `+0x88/+0x8C/+0x98` | panels/panel count/modal count |

Native selection reads at `0x0041CE69` and `0x0041CF26` verify `+0x2C6`;
`+0x2C8` is scroll position.

## Verification

The candidate built by `build_kmrp.ps1 -ReuseResources` is 164,836,864 bytes,
SHA-256 `70FE90ED938FFBE90255D057EFFFBD952D1AC60F5E8D1CE39D217E5DE9416CB7`.
Its native module is 251,392 bytes,
SHA-256 `452B76D8DC86C832E3DF9EED0F53B0768F3305935A5E1665D568435F65D1BA98`.
The reused 66 resource archives round-trip through the pool. Packaging validates
43 runtime hooks (13 core, 28 controller, 2 movies); the core keyboard hooks
remain present with controller support disabled. On 2026-10-03 the candidate was
installed through the patcher's normal workflow and started under x32dbg at
1920×1200. The installed module matches the candidate hash. The installed
configuration passes `check_controller_drift.py` with all 43 hooks. Physical
keyboard delivery and the reported menu failure have not been verified; automated
clicks did not activate the menu and the DirectInput Down probe had no hits.
This is startup and installation evidence, not a gameplay pass. The test ended
with the candidate at 3440×1440 and the exact pre-test player INI restored.

`Test-ControllerSupport.ps1` passed all 173 checks at each of 1280×720,
1920×1200, and 3840×2160, including controller on/off, switching, CD/Steam,
rollback and restore. These used isolated fixtures, restoring player settings;
they did not exercise keyboard or controller gameplay. Generated-hook equality,
KPM corruption guards, stolen bytes, and source ownership/exports/constants pass.
The unchanged engine template remains 48,012 bytes, SHA-256
`BD7865A79C9AA1E59BE65A0A33692B9D782997D57BCB9683D1C769AB7742B0BC`.
Binary inventory against the existing gold reference and 1920×1200/3440×1440
offline outputs reports zero undocumented code/data runs; this does not inventory
dynamic detours, whose sites/guards are listed above. Documentation links: 497.

Run `testing\regression\Test-WindowsKeyboardNavigation.cmd` using x86 MSVC.
Synthetic layouts cover unresolved/incomplete routes, hidden/disabled/passive
controls, rows, sliders, selectable list boundaries, custom cycles, stationary
mouse, capture/modal changes, and controller-event exclusion at heights 600, 720,
1200, 1440, and 2160. These are object-layout tests, not live resolution tests.

Run `build_kmrp.ps1 -ReuseResources`, `Test-ControllerSupport.ps1` at representative
resolutions, and the KPM package/stolen-byte checks. Before claiming the reported
failure fixed, test physical arrows/Enter in main menu, Options, modals, sliders,
and list boundaries with controller support on/off. Navigate with the pointer
stationary over another button, then move/click it. Live keyboard, mouse and
controller verification and the separate Windows text-clipping repair remain
unfinished.
