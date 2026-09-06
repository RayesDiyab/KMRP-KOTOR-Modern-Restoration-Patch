# The retained Xbox GUI event system

> **Documentation standard.** This document follows
> [`../docs/documentation-standard.md`](../docs/documentation-standard.md).
> Every address below was read out of the executable and says how; what has not
> been established is listed at the end rather than implied.

**Kind: reference.** The mechanism as it exists in the shipped PC executable.
The controller component that consumes it is
[`../docs/controller-support.md`](../docs/controller-support.md); work not yet
written is in [`../docs/controller-planned-work.md`](../docs/controller-planned-work.md).

**Build.** `swkotor.exe` after KMRP's patch, 4,087,808 bytes, SHA-256
`BF91192F8695BD750B1DB8F4AF1A355E47725A14F47188C997D1437E324397C5`. These are
original-image sites, so `FILE = VA - 0x400000` throughout; none of them is in an
appended KMRP section and none is written by the patch.

## What this is

KOTOR's PC build kept the console UI's input model. Menu panels still implement
handlers for Xbox controller events, keyed by numeric event codes, and those
handlers still run. They are unreachable in normal play only because nothing
sends the events.

This was found on 2026-09-06 while trying to make the Abilities screen's Skills /
Powers / Feats tabs reachable with a controller. Three attempts were made to add
tab switching, including a plan to bind the shoulder buttons and move party
cycling to the stick clicks. All of it was unnecessary: **the engine already
cycles those tabs on event `0x29`, the Xbox X button**, and the module already
had a path that sends it. Pressing X on that screen works and always did.

## The dispatch mechanism

Every panel's event dispatcher is virtual, at **vtable + 0x3C**, taking
`(event, flag)`. `CSWGuiPanel`'s own button entry points, read from the image,
show the codes:

| Function | VA | Sends event |
| --- | --- | --- |
| `CSWGuiPanel::OnAButtonPressed` | `0x0040B640` | `0x27` |
| `CSWGuiPanel::OnBButtonPressed` | `0x0040B650` | `0x28` |
| `CSWGuiPanel::OnXButtonPressed` | `0x0040B660` | `0x29` |
| `CSWGuiPanel::OnYButtonPressed` | `0x0040B670` | `0x2A` |
| `CSWGuiPanel::OnBlackButtonPressed` | `0x0040B680` | `0x2B` |

Each is five instructions and does nothing but dispatch:

```asm
0040B660  8b 01     mov  eax, [ecx]      ; the panel's vtable
0040B662  6a 01     push 1               ; flag
0040B664  6a 29     push 0x29            ; the X event
0040B666  ff 50 3c  call [eax+0x3C]      ; the panel's dispatcher
0040B669  c2 04 00  ret  4
```

Controls have their own per-button slots as well: `OnBButtonPressed_2`
(`0x00624BB0`) and its siblings forward to control vtable `+0x54`, `+0x58`,
`+0x5C`, `+0x60`.

Most panel dispatchers compile to a jump table over the event code:

```asm
006AE600  mov   esi, [esp+0xC]                ; the event
006AE604  lea   eax, [esi-0x28]               ; bias to the table's first event
006AE607  cmp   eax, 0xB7
006AE60C  ja    0x006AE891                    ; default: ignore
006AE612  movzx eax, byte ptr [eax+0x006AE8C8]   ; event -> case index
006AE619  jmp   dword ptr [eax*4+0x006AE8A8]     ; case index -> handler
```

Both tables are plain data, so the mapping is readable without running the game.
[`../tools/map_retained_gui_events.py`](../tools/map_retained_gui_events.py)
decodes it for every panel and prints the matrix below; it also handles the
`cmp`/`je` chain form some panels use instead.

## Event vocabulary

| Code | Meaning | How established |
| --- | --- | --- |
| `0x27` | A | `OnAButtonPressed` |
| `0x28` | B | `OnBButtonPressed` |
| `0x29` | X | `OnXButtonPressed` |
| `0x2A` | Y | `OnYButtonPressed` |
| `0x2B` | Black | `OnBlackButtonPressed` |
| `0x2F` / `0x30` | D-pad left / right | the controller module's own constants |
| `0x31` / `0x32` | scroll a listbox up / down | Abilities `0x39`/`0x3A` forward these to its description listbox |
| `0x39` / `0x3A` | panel-level scroll of the description box | see below |
| `0x2D`, `0x2E`, `0x3B`–`0x3F` | share handlers with the above on several panels; individual meanings **not established** | — |

The description-scroll pair is worth showing, because it proves `0x31`/`0x32` are
control-level events rather than panel-level ones:

```asm
006AE7CD  mov  eax, [edi+0x33BC]     ; the Abilities description listbox
006AE7D3  lea  ecx, [edi+0x33BC]
006AE7D9  push 1
006AE7DB  push 0x31                  ; re-dispatch as a scroll event
006AE7DD  call [eax+0x3C]
```

`0x33BC` is `description_listbox` in `kotor1_0_3.db` for
`CSWGuiInGameAbilities`, and is the value already shipping in the controller
module as `K1_ABILITIES_DESC_OFFSET`.

## What each panel still implements

Produced by the tool named above against the build stated at the top. `.` means
the event reaches the default case, i.e. the panel ignores it. Anything else is
the address of the handler that runs.

```
panel                                  A         B         X         Y     Black        2c        2d        2e  DpadLeft DpadRight  ScrollUpScrollDown        33        34        35        36        37        38    DescUp  DescDown
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
ABILITIES                              .    6ae7e5    6ae714         .         .         .    6ae7e5    6ae7e5    6ae818    6ae818    6ae839    6ae839         .         .         .         .         .         .    6ae7cd    6ae7b5
ABILITIES_CHARGEN                 6f890f    6f88af         .    6f892f         .         .    6f890f    6f88af    6f88cf    6f88ef         .         .         .         .         .         .         .         .    6f8975    6f8959
CHARACTER                         6b2295    6b2459    6b22dd    6b233c         .         .    6b2459    6b2459         .         .         .         .         .         .         .         .         .         .         .         .
CLASS_SELECT                           .    6dbd57         .         .         .         .         .    6dbd57         .         .         .         .         .         .    6dbd92    6dbdab         .         .         .         .
CONTROLLER_LOSS_BOX                    .    62516f         .         .         .         .         .    62516f         .         .         .         .         .         .         .         .         .         .         .    625141   [chain]
EQUIP                                  .    6ba41f         .         .         .         .    6ba581    6ba41f         .         .         .         .         .         .         .         .         .         .    6ba71e    6ba700
FEATS                             6f46ef    6f46af    6f46cf    6f471b         .         .    6f46ef    6f46af    6f473b    6f473b    6f473b    6f473b         .         .         .         .         .         .    6f4780    6f475e
INGAME_GAMEPLAY                        .    6e61af         .         .         .         .    6e61e2    6e61af         .         .         .         .         .         .         .         .         .         .    6e622e    6e6250
INGAME_OPTIONS                         .    6aaee9         .         .         .         .    6aaee9    6aaee9         .         .         .         .         .         .    6aaf16    6aaf16         .         .         .         .
INVENTORY                              .    6b3f88    6b3fc3         .         .         .    6b3f88    6b3f88         .         .         .         .         .         .         .         .         .         .    6b3f23    6b3f01
JOURNAL                                .    645cab    645c8c    6459ce    64573f         .    645cab    645cab         .         .         .         .         .         .         .         .         .         .    645cda    645cef
KEY_MAPPINGS                           .    6ec529         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
MAP                               693c44    693ce2    693c09         .         .         .    693ce2    693ce2         .         .    693d11    693d41         .         .         .         .         .         .         .         .
MESSAGES                               .    6282c8    6282a5         .         .         .    6282c8    6282c8         .         .         .         .         .         .         .         .         .         .         .         .
MESSAGE_BOX                            .    62516f         .         .         .         .         .    62516f         .         .         .         .         .         .         .         .         .         .         .    625141   [chain]
OPTIONS_FEEDBACK                       .    6de45f         .         .         .         .    6de492    6de45f         .         .         .         .         .         .         .         .         .         .    6de4de    6de500
OPTIONS_MAIN                           .    6dff58         .         .         .         .    6dff3f    6dff58         .         .         .         .         .         .         .         .         .         .    6dff99    6dffbb
OPTIONS_MOUSE                          .    6e61af         .         .         .         .    6e61e2    6e61af         .         .         .         .         .         .         .         .         .         .    6e622e    6e6250
OPTIONS_SOUND                          .    6ddbd8         .         .         .         .    6ddbbf    6ddbd8         .         .         .         .         .         .         .         .         .         .    6ddc0b    6ddc2d
OPTIONS_SOUND_ADVANCED                 .    6e0fdb         .         .         .         .    6e0fcd    6e0fdb         .         .         .         .         .         .         .         .         .         .    6e11f4    6e1209
PARTY_SELECT                           .    6bee01         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
PAZAAK_GAME                            .    67e90f         .         .         .         .         .    67e93b         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
PAZAAK_SETUP                           .    68175c         .    6817bc         .         .         .    68175c         .         .         .         .         .         .    6817d6    68180b         .         .         .         .
POWERS                            6f290f    6f28ef    6f294f    6f292f         .         .    6f290f    6f28ef    6f297b    6f297b    6f297b    6f297b         .         .         .         .         .         .    6f29c0    6f299e
SAVELOAD                               .    6c86f0         .         .         .         .         .    6c872f         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
SKILLS                            6f6a9f    6f6a3f         .    6f6abf         .         .    6f6a9f    6f6a3f    6f6a5f    6f6a7f         .         .         .         .         .         .         .         .    6f6afb    6f6adf
SOLO_MODE_QUERY                        .         .         .         .         .         .         .    6c2488         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
STORE                                  .    6c21c6    6c222f         .         .         .         .    6c21c6         .         .         .         .         .         .         .         .         .         .    6c220d    6c21eb
UPGRADE                                .    6c6aaf         .         .         .         .         .    6c6aaf         .         .         .         .         .         .         .         .         .         .    6c6b17    6c6aec
UPGRADE_ITEM_SELECT                    .    6c2d57         .         .         .         .         .    6c2d57         .         .         .         .         .         .         .         .         .         .    6c2da3    6c2d81
UPGRADE_SELECTION                      .    6c2b2b         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
```

**The controller module sends five of these codes.** Everything else in the
table is reachable code that nothing currently triggers.

## The Abilities tabs, in detail

The active tab is a **byte on a global object**, not a panel member: reached as
`[0x007A39FC]` → `+4` → `call 0x005ED690` → `+0xBC0`. Every write in the image is
in the Abilities code and stores 0, 1 or 2:

| VA | Writes | In |
| --- | --- | --- |
| `0x006ADAE2` | `0` | the three tab buttons' click handlers |
| `0x006ADAB2` | `1` | " |
| `0x006ADA82` | `2` | " |
| `0x006AE74D` | `0` | **the `0x29` (X) handler** |
| `0x006AE783` | `1` | " |
| `0x006AE7A2` | `2` | " |

So the X button and the three on-screen tabs write the same variable. The X
handler at `0x006AE714` reads the current value and switches on 0/1/2, which is
how one button cycles three tabs.

**Confirmed in play**: pressing X on the Abilities screen cycles Skills, Powers
and Feats, with the engine's own focus handling. No KMRP change was needed.

## What the X handlers actually do

Confirmed in play on 2026-09-06, not inferred from the disassembly:

| Panel | Event `0x29` (X) does | Corroboration |
| --- | --- | --- |
| Abilities | cycles Skills / Powers / Feats | the handler writes the `+0xBC0` tab index with 0, 1 and 2 |
| Map | **returns the party to the Ebon Hawk** | the handler calls `0x00692BC0`; the image contains the script name `k_sup_gohawk` at `0x007546E0` |
| Messages | shows the feedback view | the handler branches on `[panel+0xA8] & 2` |
| Journal | `X` and `Y` move between quests, completed quests and the feedback view | the dispatcher reads a filter byte at `+0xBC4`, one past the Abilities tab index |
| Inventory | cycles the item filter: all, new, quest, equippable, utility, usable | the handler sets `[panel+0x1DE4] |= 1` before filtering |
| Character | **Scripts** — the button KMRP already badges with an X | handler `0x006B22DD`; the shipped badge `kmrpx_charscr` sits on `BTN_SCRIPTS` |

**These are not variations on one idea, and that is the important finding.** The
same event code cycles a tab on one screen and fast-travels the party across the
galaxy on another. There is no uniform "X = secondary action" to bind.

**So a global X binding would be actively dangerous.** The controller module
already dispatches `0x29` to whatever menu panel is open, which means that on the
Map screen a single press is a fast travel with no confirmation. Any future work
that sends these events must decide **per panel** which are wanted, and treat
Map's as something the player should have to mean.

This also corrects a claim made while planning: trying the unreached `X` handlers
was described as free, on the grounds that it only reveals what already-present
code does. It is not free. One of the four suggested screens teleports the party.

## Other console leftovers found while looking

| String | VA | Note |
| --- | --- | --- |
| `EVENT_CONTROLLER_RUMBLE` | `0x0074498C` | a script event name; rumble is in the event vocabulary |
| `RumbleCutOff`, `RumblePattern` | `0x0074EC1C`, `0x0074EC2C` | settings keys |
| `HD0:DATAXBOX\gui`, `\scripts`, `\items` | `0x0074EB70` onward | Xbox filesystem paths |
| `RIMSXBOX`, `LIVE%d:RIMSXBOX\live%ddx` | `0x0074DE0C` onward | Xbox Live / RIM paths |

**Correction, kept visible.** `EVENT_LEFT_TRIGGER` at `0x00744BBC` was briefly
read as a controller trigger event. It is not. It sits between
`EVENT_ENTERED_TRIGGER` and `EVENT_TIMED_EVENT` in the *script* event name table
and means leaving a trigger volume. Nothing about the analogue triggers was
established from it.

## The second mechanism: registered bindings

Everything above this point reads dispatchers compiled into vtables. That is
**half the system**, and the survey was silently reporting it as the whole.

`CSWGuiControl::AddEvent(eventCode, receiver, handler)` at `0x0041AB20` appends a
twelve-byte `{receiver, handler, eventCode}` entry to a control's table at `+0x38`
(count at `+0x3C`). `CSWGuiControl::HandleInputEvent` walks that table for any
event the class did not handle itself. Handlers are therefore **registered at
construction time**, not only compiled in.

There are **515 call sites**, in essentially every panel constructor.
`tools/map_gui_event_bindings.py` extracts them; `reverse-engineering/gui-event-bindings.txt`
is the output.

| Code | Bindings | Where |
| --- | --- | --- |
| `0x27` A | 287 | everywhere |
| `0x2D` | 58 | list entries and options rows, always alongside `0x27` |
| `0x00` / `0x01` | 69 / 25 | matches the base handler's `vtable+0x40` call with 1 / 0 |
| `0x35` / `0x36` | 8 / 8 | `CSWGuiInGameMenu` only — eight of each, one per menu tab |
| `0x2F` / `0x30` | 7 / 7 | with `0x3F` / `0x40` at 6 / 6 |
| `0x2A` Y | **5** | `CSWGuiOptionsGraphics` ×1, `CSWGuiOptionsSound` ×4 |
| `0x1F4` / `0x1F5` / `0x1F8` / `0x1F9` | 4 / 4 / 3 / 3 | sliders and ability lists |
| `0x44` | 2 | `CSWGuiPazaakGame`, `CSWGuiMainInterfaceChar` |
| `0x29` X | **1** | `CSWGuiSaveLoad::PopulateGameList` |
| `0x28` B | **0** | nothing, anywhere in the image |
| `0x2B` Black | **0** | nothing |
| `0x31` / `0x32` | **0** | nothing |

**This answers the Y question.** The user reported that Y works in the Journal and
nowhere else. Y has five registrations and the Journal is not among them — so the
Journal's Y is its *dispatcher*, and the five registrations are a separate,
unrelated use in the sound and graphics options. The two mechanisms overlap
almost not at all, which is why reading only one produced a confident wrong
picture of which buttons "work".

**B, Black and `0x31`/`0x32` are bound to nothing at all.** They exist only in
dispatchers. For KMRP that is the useful fact in this whole document: those codes
can be driven without colliding with anything the game registers for itself.

Codes left unnamed above are unnamed deliberately. `0x2D` appearing 58 times
beside `0x27` on list rows suggests a selection or activation notification rather
than a button, and `0x35`/`0x36` appearing exactly eight times each on the eight
in-game menu tabs suggests tab enter/leave — but neither has been confirmed, and
a guessed name in a reference document cannot be told apart later from a
measured one.

## The sending end: how a button was supposed to reach a panel

Everything before this section reads receivers — dispatchers and registered
bindings, both answering "what happens if this event arrives". Neither answers
what sends one. That question turns out to have the most useful answer in this
document. `tools/map_console_input_layers.py` produces
`reverse-engineering/console-input-layers.txt`.

### Layer 1: the panel button thunks

Five four-instruction functions sit consecutively at `0x0040B640`:

```asm
0040B640  mov  eax, dword ptr [ecx]
0040B642  push 1                       ; the pressed flag
0040B644  push 0x27                    ; the event
0040B646  call dword ptr [eax+0x3C]    ; -> this panel's HandleInputEvent
0040B649  ret  4
```

| Address | Function | Raises | Panel vtable slot |
| --- | --- | --- | --- |
| `0x0040B640` | `CSWGuiPanel::OnAButtonPressed` | `0x27` A | `+0x50` |
| `0x0040B650` | `CSWGuiPanel::OnBButtonPressed` | `0x28` B | `+0x54` |
| `0x0040B660` | `CSWGuiPanel::OnXButtonPressed` | `0x29` X | `+0x58` |
| `0x0040B670` | `CSWGuiPanel::OnYButtonPressed` | `0x2A` Y | `+0x5C` |
| `0x0040B680` | `CSWGuiPanel::OnBlackButtonPressed` | `0x2B` Black | `+0x60` |

They appear in **76 panel vtables each**, and **nothing in the executable calls
any of them**. Not one direct caller, on any of the five. They are reached only
through the vtable slot, and no code indexes those slots.

That is the shape of the whole finding: the console entry points are present in
every panel, correctly wired to the event system beneath them, and nothing above
them ever fires.

**This also corrects a correction.** An earlier pass in this document dismissed
"per-control button slots at `+0x54`…`+0x60`" as a false lead, on the grounds
that those offsets hold `Global::return_zero` and destructors. That was true and
irrelevant: it was measured on **control** vtables. On **panel** vtables the same
offsets are exactly the button entry points. Right offsets, wrong class.

### Layer 2: the client action router

`CClientExoAppInternal::HandleInputEvent` (`0x00621210`) is a separate, higher
layer — game actions rather than GUI events. It dispatches through a direct table
at `0x00622128` (ids `0x01`…`0x0C`) and an indexed table at `0x006221FC` /
`0x00622154` (ids `0x19`…`0x108`): **64 ids across 40 handlers**.

The handlers come in **pairs**, one low id and one high:

| Handler | Ids | Reaches |
| --- | --- | --- |
| `0x00621308` | `0x09`, `0xCE` | `ChangeCharacterToNextLivingPartyMember` |
| `0x0062184C` | `0x06`, `0xCC` | `RestoreCamera`, `SetInputClass` |
| `0x0062180F` | `0x05`, `0xCD` | `SelectNearestObject` |
| `0x006216C7` | `0x01`, `0xD0` | `GetPlayerCreature`, `GetServerCreature` |
| `0x0062137F` | `0x0A`, `0xCF` | — |
| `0x006213BC` | `0x0B`, `0xDF` | — |

`0x09`/`0xCE` is the confirmation. `0xCE` is the code this document already
recorded as reaching party change from the Character screen, found by a different
route entirely; here it shares a handler with a low id. So the low ids are the
surviving input source and `0xCC`…`0xE0` is a second one feeding the same
actions.

Several high ids have **no low-id partner**, meaning an action the surviving
input source cannot reach at all:

| Ids | Handler | Reaches |
| --- | --- | --- |
| `0xD1`…`0xD8` | `0x006218D5` | `OnBlackButtonPressed_2`, `RestoreCamera`, `SetInputClass` — eight of them |
| `0xDA` | `0x00621A75` | `CExoInput::ClearEvents`, `ResetDriveAcceleration`, `DoQuickSave`, `CoolDownEvent` |
| `0xD9` | `0x00621C45` | `GetPausedByCombat` |
| `0xDB`…`0xDE`, `0xE1`…`0xEF` | various | not read |

### Other console leftovers named in the symbol table

- **`CSWGuiControllerLossBox`** — `OnAccept` (`0x00625A40`), `OnPanelAdded`
  (`0x00627220`). A whole panel class for a disconnected controller.
- **`CClientExoAppInternal::LookUpAndPerformRumbleWithCutOff`** (`0x005EDF60`) —
  rumble.
- **`CClientExoApp::ResetDriveAcceleration`** (`0x005EDBA0`), reached only from
  the unpaired `0xDA`.
- **`CExoInput::CoolDownEvent`** / **`ClearEvents`** — input repeat suppression.

### What this does and does not establish

It establishes **reachability**, which is a fact about the binary: these entry
points exist, they are correctly wired downward, and they have no callers.

It does not establish intent, and no claim about intent is made here. "The PC
build kept the console UI and cut the input layer above it" is the obvious
reading and it may well be right, but this document has already been wrong four
times by treating an obvious reading as a measurement. What is measured is the
call graph.

### Why this matters for KMRP

The module currently synthesises keyboard input to drive menus. This says the
game has a native path that does not need that: calling a panel's `+0x50`…`+0x60`
slot, or `HandleInputEvent(code, 1)` directly, delivers a real console event to
the real handlers.

Combined with the binding survey, **B (`0x28`), Black (`0x2B`) and `0x31`/`0x32`
have no registered handler anywhere in the image**, so driving those collides
with nothing. X (`0x29`) has exactly one registration and a great deal of
per-panel dispatcher behaviour, which is why a global X binding would be wrong —
already established in play, and now explained.

## Upstream: where the console path is actually cut

The chain from a physical input to a panel event, read end to end:

```
CExoInput::GetEvents                       poll, returns events with an id
  -> CClientExoAppInternal::ProcessInput   0x006227E0
       id 0x27..0x40  -> CSWGuiManager::HandleInputEvent   0x0040C8E0
       everything else -> CClientExoAppInternal::HandleInputEvent  0x00621210
```

`ProcessInput` routes the console range **explicitly and intact**:

```asm
00622B89  mov edi, [ecx+0x10]        ; the event id
00622B8C  cmp edi, 0x27
00622B92  jl  0x622B99
00622B94  cmp edi, 0x40
00622B97  jle 0x622BF1               ; 0x27..0x40 -> the GUI branch
...
00622C5C  call 0x0040C8E0            ; CSWGuiManager::HandleInputEvent
```

So the receiving half of the system is not merely present, it is **wired all the
way up to the input pump**. Nothing between `CExoInput` and a panel handler is
missing.

### The cut is at the input-event descriptions

Every input event the game can produce is registered in exactly one function,
`CClientExoAppInternal::SetEventDescriptions` (`0x005EE900`-ish), through
`CExoInput::CreateNewEvent` (27 sites) and `CExoInput::AddEvent` (64 sites).
There are no other registration sites in the executable.

The ids it registers are `0x01`…`0x0D`, `0x17`…`0x19`, `0x41`…`0x46`, `0x50`,
`0xB5`…`0xBB`, plus a data-driven set. **None is in `0x27`…`0x40`.**

The data-driven part comes from **`keymap.2da`** — the name is in the
executable's 2DA table at `0x0074BA88`, and ids are read with
`C2DA::GetINTEntry_3`. Its columns are named in the image: `EventType`, `Action`,
`Disabled`, `Repeatable`, `RepeatWait`, `RepeatRate`, `Scale`, `ScaleMag`,
`ScaleExp`, and six per-input-class flags — `ICPC`, `ICPCGUI`, `ICDialog`,
`ICFreeLook`, `ICMovie`, `ICMiniGame` — which correspond to
`CClientExoAppInternal::SetInputClass`.

The user-facing half of that lives in `swkotor.ini` under `[Keymapping]`, as
`Action<id>=<scancode>`. In the installed ini those ids run `0xCC`…`0x11E`.
**None is in `0x27`…`0x40` either.**

So the console GUI events have **no input source at all**: not hardcoded, not in
the 2DA, not bindable in the ini. That is the cut, and it is one function wide.

### A correction to the previous section

The section above this one read the low/high id pairing in the action router as
"two input sources feeding one action set", and singled out `0xD1`…`0xDA` as
"the surviving input source cannot reach". **That was wrong.** The
`[Keymapping]` ini binds `0xCC`…`0x11E` directly, so the high ids are simply the
**user-configurable keyboard actions**, and the low ids are the fixed ones. A
pair is one action reachable both ways. `0xCE` reaching party change is an
ordinary "next party member" key binding, not a leftover.

The pairing therefore says nothing about a console input source, and the eight
unpaired ids say nothing either. What survives that correction is the part that
was measured rather than interpreted: `0x27`…`0x40` has no registration anywhere.

### What this means for KMRP

The module currently synthesises keyboard scancodes so that the game's keyboard
path will produce menu actions. It does not have to. Three injection points now
exist, in increasing order of narrowness:

1. **`CSWGuiManager::HandleInputEvent` (`0x0040C8E0`)** — the single entry the
   engine itself uses for the console range. Calling it with `(code, 1)` is
   exactly what `ProcessInput` does on the branch that never fires.
2. **A panel's vtable slot `+0x50`…`+0x60`** — the per-button thunks.
3. **`SetEventDescriptions`** — registering real input events for `0x27`…`0x40`
   would light the path up at its source, with repeat, scaling and input-class
   gating all handled by the engine. This is the largest change and the most
   native.

None of this has been tried yet, and the document records none of it as working.

## Which screens really have which console button

The single most useful table here, and the one with the most outside
corroboration. `CSWGuiPanel::On<button>Pressed_2` is not called by anything
either — but it is **registered as a control handler** through `AddEvent`, always
on event `0x27`:

```
AddEvent(0x27, panel, OnXButtonPressed_2)   on the panel's "X" widget
```

So activating the on-screen button with the mouse raises the **console button's
event on its panel**. The mouse path and the controller path converge on one
handler. That is why a console port can show `X SCRIPTS` as a prompt for the same
widget a PC player clicks.

This makes the registration list authoritative for the question KMRP actually
needs answered: **which screens have an X, Y or Black action at all**, and
therefore where a controller prompt belongs.

`tools/map_gui_event_bindings.py --forwarders`.

| Button | Panels |
| --- | --- |
| **B** `0x28` | 40 — essentially every screen. B is Back/Cancel. |
| **X** `0x29` | 9 — `Container`, `FeatsCharGen`, `InGameCharacter`, `InGameInventory`, `InGameJournal`, `InGameMap`, `InGameMessages`, `PowersLevelUp`, `SaveLoad` |
| **Y** `0x2A` | 7 — `AbilitiesCharGen`, `SkillsCharGen`, `FeatsCharGen`, `PowersLevelUp`, `NameChargen`, `InGameCharacter`, `InGameJournal` |
| **Black** `0x2B` | 1 — `InGameJournal` |

### Corroboration from the console release

Screenshots of the Switch port, which drives these same panels, match the table:

- **Character generation / Attributes** shows `Y RECOMMENDED`, `A ACCEPT`,
  `B BACK`. The Y column above is exactly the five character-generation and
  level-up screens, and the class table has `OnRecommendButton` on each
  (`CSWGuiAbilitiesCharGen::OnRecommendButton` `0x006F7390`, and the same on
  `SkillsCharGen`, `FeatsCharGen`, `PowersLevelUp`).
- **Character sheet** shows `X SCRIPTS`, matching `InGameCharacter` in the X row
  and the play-confirmed behaviour this document already records.

Five of the nine X panels have been confirmed in play by the user: Character
(Scripts), Inventory (item filters), Map (Return to Ebon Hawk), Messages
(feedback), and Journal. No contradiction with the table anywhere.

### This resolves the Y question completely

Two earlier readings in this document conflicted. The binding survey found Y
registered five times in the sound and graphics options; the user reported Y
working only in the Journal. Both stand, and the forwarder table is why:

- Those five `0x2A` registrations are `AddEvent(0x2A, …)` — a different thing
  from the forwarder, and unrelated to the button prompts.
- The forwarders put Y on seven panels, and `InGameCharacter` is one of them —
  but Character's Y handler is gated on `CGuiInGame+0x10C`, the level-up flag.
  Outside level-up it does nothing.
- Every other Y panel is a character-generation or level-up screen, which a
  player only sees during those flows.

So in ordinary play the Journal is the only screen where Y visibly does
something, which is exactly what was reported. The engine has more Y than the
player can normally reach.

## The engine's own gamepad support

The console entry points have no caller, but that is not the same as the engine
having no gamepad code. It has a complete one, at the raw input layer, and it is
live.

### The device layer runs every frame

`CExoInputInternal::GetEvents` — the per-frame poll — loops over a joystick
device count at `+0x158` and calls `CExoRawInputInternal::GetJoystickBuffer`
(`0x005E30E0`) for each. That function is real DirectInput work, not a stub:

```asm
005E315D  call dword ptr [ecx+0x64]   ; IDirectInputDevice::Poll
005E3170  call dword ptr [ecx+0x24]   ; IDirectInputDevice::GetDeviceData
005E3177  cmp  eax, 0x80070015        ; DIERR_NOTACQUIRED
005E317E  cmp  eax, 0x8007001E        ; DIERR_INPUTLOST
005E318E  call dword ptr [ecx+0x1c]   ; Acquire -- and re-acquire on loss
```

It decodes a **POV hat** as well as buttons. The magic multiply `0x51EB851F`
followed by `shr edx, 5` is a divide by 100, and the compared values are
`0`, `0x2D`, `0x5A`, `0x87`, `0xB4`, `0xE1`, `0x10E`, `0x13B` — 0, 45, 90, 135,
180, 225, 270 and 315. DirectInput reports POV in hundredths of a degree, so
this is eight-direction D-pad decoding with diagonals setting two bits.

Buttons, axes and a D-pad. That is complete gamepad handling.

### The binding layer is where it stops

`CExoInputInternal::CreateNewEvent` (`0x005E0E20`, five arguments) takes
`(eventId, descriptionType, controlValue, …)`. The type selects among six
description kinds through a jump table at `0x005E0F7C`:

| Type | Class allocated | Used by the game |
| --- | --- | --- |
| 0 | base `CExoInputEventDesc`, vtable `0x0074D5FC` | **never** |
| 1 | base `CExoInputEventDesc` | 17 times |
| 2 | base `CExoInputEventDesc` | **never** |
| 3 | `CExoInputEventDescDetailed` (`0x005DFCC0`) | 8 times |
| 4 | `CExoInputeventDesc2ButtonAxis` (`0x005DFD50`) | once |
| 5 | base `CExoInputEventDesc` | **never** |

The type is stored at `desc+0x14` and the control value at `desc+0x18`.

`CExoInputInternal::AddEvent` (`0x005E0FA0`) is a different thing from
`CSWGuiControl::AddEvent`, and much simpler: `AddEvent(inputClass, eventId)`,
with `inputClass < 6`, setting a bit in a per-class bitset. Those six classes are
the `keymap.2da` columns `ICPC`, `ICPCGUI`, `ICDialog`, `ICFreeLook`, `ICMovie`,
`ICMiniGame`, and `CExoInputInternal::IsEventInClass` (`0x005E0D80`) reads them
back.

**Three of the six description types are never constructed.** That is where the
question now sits: whether one of types 0, 2 or 5 is the joystick binding, unused
because nothing binds a joystick control.

### What is still unknown

Two things gate the native path, and neither can be settled from the image:

1. ~~Is a joystick device ever created?~~ **Measured 2026-09-07: no.** The count
   is a hardcoded zero and there is no `EnumDevices` anywhere. See "Measured: the
   joystick count is hardcoded to zero".
2. **Which description type names a joystick control, and in what numbering?**
   Types 0, 2 and 5 are unused; the meaning of each is not established.

Both are runtime questions. Per `AGENTS.md`, they get measured in x64dbg rather
than guessed at, and nothing in this section should be read as a plan until they
are.

## Measured: the joystick count is hardcoded to zero

Settled in the debugger on 2026-09-07, against the running patched game with an
Xbox controller connected. This is measurement, not inference.

**Method.** A single-shot breakpoint on `CExoRawInputInternal::GetJoystickBuffer`
(`0x005E30E0`) never fired. That alone proves nothing — the poll might not be
running — so a control breakpoint went on `CExoInputInternal::GetEvents`
(`0x005E24E0`), which fired immediately. The poll runs every frame; the joystick
body never executes.

**The count.** At the `GetEvents` break, `ecx` was the `CExoInputInternal` object
and `[ecx+0x158]` read **2**. That field is not a joystick count directly:

```asm
005E2627  lea  eax, [edi-2]          ; device index = edi - 2
005E262B  call 0x005E30E0            ; GetJoystickBuffer(index, buffer)
005E2630  mov  eax, [esi+0x158]      ; loop while edi < count
```

`edi` starts at 2, so device 0 is the keyboard, device 1 the mouse, and joysticks
occupy index 2 upward. A count of exactly 2 means **zero joysticks**, and the
loop body is never entered.

**Where the count comes from.** `CExoInputInternal::Constructor`:

```asm
005E2234  mov ecx, [eax+0x18]        ; joysticks found
005E2237  add ecx, 2                 ; + keyboard + mouse
005E223A  mov [esi+0x158], ecx
005E2240  cmp [eax+0x18], ebp        ; clamped at 4
005E2245  mov [esi+0x158], 6         ; 2 + 4 -- the engine supports four pads
```

So the engine is built for four joysticks, which is why `GetJoystickBuffer`
decodes four device blocks.

**And the field is a hardcoded zero.** `CExoRawInputInternal::Constructor`
(`0x005E3E80`) does a complete DirectInput8 setup — `DirectInput8Create`,
`CreateDevice`, `SetDataFormat`, `SetCooperativeLevel`, `SetProperty` for a
buffer size of `0x100` — for **exactly one device**, the keyboard. The mouse gets
its own `InitializeDirectInputMouse`. Then, on the success path:

```asm
005E3F6D  mov dword ptr [esi+0x18], ebx    ; ebx = 0
```

The joystick count is set to zero unconditionally. **There is no `EnumDevices`
call anywhere in the executable**, and no joystick equivalent of
`InitializeDirectInputMouse`. Enumeration was not merely failing — it is absent.

### What this changes

Everything downstream of enumeration is intact and was verified above: buffered
reads with re-acquire, four device blocks, eight-direction POV decoding, the
`0x27`..`0x40` routing in `ProcessInput`, the panel dispatchers, the registered
bindings. All of it is unreachable because one field is zero and nothing fills
it.

So "just add bindings" was too optimistic, and this document should say so
plainly. Two separate pieces were cut, not one:

1. **Device enumeration** — absent. Would have to be written: `EnumDevices` for
   `DI8DEVCLASS_GAMECTRL`, `CreateDevice`, `SetDataFormat` with the joystick
   format, `SetProperty`, `Acquire`, store the pointers in the array at
   `rawInput+0x28`, and set `rawInput+0x18`.
2. **The bindings** — no input-event description names a joystick control, and
   three of the six description types are never constructed.

Both are writable, but together they are a real project, not a small hook. The
narrow alternative remains: call `CSWGuiManager::HandleInputEvent(code, 1)`
(`0x0040C8E0`) from the module's existing pad reader, which needs neither piece
and still delivers genuine console events to the real handlers.

## The device layer, field by field

Read from live memory on 2026-09-07 with the game running, plus the surviving
mouse initialiser as a template. This is the structure any native-input work has
to satisfy.

### `CExoRawInputInternal`

Reached as `CExoInputInternal + 0x140`. Live values from the running game, with a
controller connected:

| Offset | Live value | Meaning |
| --- | --- | --- |
| `+0x00` | `1` | initialised |
| `+0x04` | `0` | null-checked by `GetJoystickBuffer`; **never written anywhere** |
| `+0x18` | `0` | joystick count — the hardcoded zero |
| `+0x1C` | `0x15D7E0C4` | **`IDirectInput8*`, live and usable** |
| `+0x20` | `0x15F23FC4` | keyboard device |
| `+0x24` | `0x00A7546C` | mouse device |
| `+0x28` | `0` | array of joystick device pointers |
| `+0x2C` | `0` | struct with `+4` and `+0x18`; **never written anywhere** |
| `+0x30` | `0` | null-checked only; **never written anywhere** |

The interface at `+0x1C` matters: DirectInput8 is already created. Any
enumeration work would use the existing interface rather than initialising one.

`+0x04`, `+0x2C` and `+0x30` are written by **nothing in the executable** — only
`ShutDownDirectInput` zeroes `+0x2C`. They were populated by the deleted
enumeration, so their layout is knowable only from their consumers.

### The mouse initialiser as a template

`CExoRawInputInternal::InitializeDirectInputMouse` (`0x005E3FA0`) is the only
surviving per-device setup, and it is a plain DirectInput8 sequence:

```
[edi+0x1C] -> IDirectInput8
  CreateDevice        vtable +0x0C   GUID at 0x0074D6A4 -> &[edi+0x24]
  SetDataFormat       vtable +0x2C   format at 0x0074DB04
  SetCooperativeLevel vtable +0x34   hwnd [0x007A39D8], flags 0x0A
  SetProperty         vtable +0x18   DIPROP_BUFFERSIZE, dwData 0x100
```

Useful constants that fall out: the **HWND is the global at `0x007A39D8`**, the
keyboard GUID is at `0x0074D694` and its format at `0x0074D8FC`. There is **no
joystick data format in the image**; one would have to be supplied.

### Why replacing `GetJoystickBuffer` beats enumerating

Enumeration alone is not enough. `GetJoystickBuffer` also requires `+0x2C` — and
dereferences it, reading `+4` and `+0x18` from whatever it points at. Nothing
constructs that structure, so feeding the original function means reconstructing
a deleted type from its consumers and hoping the reconstruction is right.

Replacing the function avoids the whole question. Its contract is small and
entirely visible: `GetJoystickBuffer(deviceIndex, outBuffer)`, where `outBuffer`
is `{void* records, int count}` — the function allocates `0x1400` bytes for the
records and resets the count to zero at `0x005E3110`. An implementation owned by
KMRP needs only that contract plus `rawInput+0x18` set non-zero, and every layer
above it stays the engine's own.

The record format written into that buffer is **`DIDEVICEOBJECTDATA[256]`** —
solved statically, see "The `GetJoystickBuffer` contract, solved" below.

Nothing here has been implemented or tried.

## The `GetJoystickBuffer` contract, solved

The last unknown in the device layer, and it turned out to be two standard
DirectInput structures rather than anything proprietary.

### Input: polled `DIJOYSTATE`

```asm
005E315D  call dword ptr [ecx+0x64]   ; IDirectInputDevice8::Poll
005E3168  lea  edx, [esp+0x40]        ; a STACK buffer, not the heap one
005E316D  push 0x50                   ; 80 = sizeof(DIJOYSTATE)
005E3170  call dword ptr [ecx+0x24]   ; GetDeviceState  (0x28 would be GetDeviceData)
005E3177  cmp  eax, 0x80070015        ; DIERR_NOTACQUIRED
005E318E  call dword ptr [ecx+0x1c]   ; Acquire, then retry
```

Vtable `+0x24` is `GetDeviceState` and `+0x64` is `Poll`, so the joystick is read
as **polled state**, not as a buffered device. `DIJOYSTATE` also explains the POV
decoding documented above: it carries `rgdwPOV[4]`.

### Output: synthesised `DIDEVICEOBJECTDATA[256]`

The `0x1400`-byte allocation is `256 × 0x14`, and `0x14` is
`sizeof(DIDEVICEOBJECTDATA)` on 32-bit. The append sequence proves the stride:

```asm
005E3219  mov eax, [esi+4]          ; count
005E321C  mov ebx, [esi]            ; base
005E321E  lea eax, [eax+eax*4]      ; count * 5
005E3221  mov [ebx+eax*4],      ecx ;   * 4 -> count * 20 ; dwOfs
005E3232  mov [ebp+eax*4+4],   ebx  ; dwData
005E324C  mov [ebp+eax*4+8],   ebx  ; dwTimeStamp = 0
005E3240  mov [ebp+eax*4+0xc], ebx  ; dwSequence  = 0
005E3258  mov [esi+4], eax          ; ++count
```

Fields at `0`, `4`, `8`, `0xC` are exactly `dwOfs`, `dwData`, `dwTimeStamp`,
`dwSequence`. The engine polls a state snapshot and then **hand-builds
buffered-style records from it**, edge-triggered:

```asm
005E320A  mov edi, 0x20             ; 32 = DIJOYSTATE.rgbButtons[32]
005E3210  mov al, [ecx+ebx]         ; current button byte
005E3213  xor al, [edx]             ; against the previous snapshot
005E3217  jns 0x5E325B              ; unchanged -> emit nothing
005E322F  shr ebx, 7                ; high bit -> dwData 0 or 1
```

Thirty-two buttons, a record emitted only on change. Hence
`DIPROP_BUFFERSIZE = 0x100` in the sibling initialisers: 256 records is the
engine's uniform buffer depth.

### The contract

```c
struct RecordBuffer {            // the caller's out-parameter
    DIDEVICEOBJECTDATA* records; // +0x00, 0x1400 bytes, 256 entries
    int                 count;   // +0x04, reset to 0 on entry
};

void __thiscall GetJoystickBuffer(int deviceIndex, RecordBuffer* out);
```

Both structures are documented Win32, which makes an owned replacement ordinary
code: read the pad, diff against the previous snapshot, append a record per
change, set the count. Nothing about `rawInput+0x2C`, `+0x30` or `+0x04` needs to
be understood, because a replacement never reaches the code that checks them.

**Credit and correction.** The `0x1400 / 0x14 = 0x100` observation came from the
user's other assistant, and it was right. This document had first argued against
it on the grounds that the append stride looked like 4 bytes — a misreading of
`[ebp+eax*4+4]` that missed the `lea eax,[eax+eax*4]` five-multiply immediately
above it. The correct half of that objection is only that the DirectInput *read*
is `GetDeviceState`/`DIJOYSTATE`, not a buffered `GetDeviceData`; the records are
built by the engine afterwards. Both structures are standard.

## Coverage: what has been walked, and what has not

The sweep is tracked explicitly because a decoder blind spot and a genuine
absence look identical in the output, and this document has already been wrong
that way once.

**Panel dispatchers — 41 of 41 accounted for.** 39 decoded, 2 explained:

| Shape | How it is written | Panels | Found because |
| --- | --- | --- | --- |
| indexed jump table | `lea eax,[esi-BIAS]` … `movzx`/`jmp [eax*4+T]` | most | the first one looked at |
| indexed, `add` bias | `add eax, -BIAS` instead of `lea` | Journal, Character, Equip | Journal was reported undecodable while implementing the widest event set in the game |
| **direct** jump table | no `movzx`; `jmp [eax*4+T]` straight after the range check | Container | its `cmp eax, 7` prints in decimal, which a hex-only pattern missed |
| `cmp`/`je` chain | compare the code, jump | Party Select, Pazaak, Save/Load, Solo Query, Key Mappings, Upgrade Selection | — |
| `sub`-seeded chain | opens `sub eax, 0x28` with no leading `cmp` | Main Menu, Level Up | the first `je` was dropped without a seed, so the panel read as empty |

The two not decoded are not gaps:

- **`BARK_BUBBLE`** uses `CSWGuiPanel::HandleInputEvent` (`0x00409E60`), the base
  implementation, which handles nothing itself and **forwards the event to the
  focused control** — see the new branch below.
- **`FLOATY_TEXT`** (`0x00418750`) is not an event switch. It branches on the
  *flag* argument, not the event code.

**Whole accepted range walked, not a slice.** Dispatchers accept `0x28..0xDF`;
an earlier pass stopped at `0x3F` and therefore reported the Character panel as
having no party-change handler, when it is reached by event `0xCE`. The full
inventory is
[`retained-gui-event-inventory.txt`](retained-gui-event-inventory.txt),
regenerated by `map_retained_gui_events.py --full`: **39 panels, 212 implemented
events**. The controller module sends five codes.

### The control layer

The base panel handler forwards to the focused control, so controls have their
own dispatchers. Walked 2026-09-06 across all 112 `CSWGui*` classes that carry a
vtable in `kotor1_0_3.db`. **79 implement events at `+0x3C`.**

The four that matter, because everything else inherits them:

| Control | Dispatcher | Implements |
| --- | --- | --- |
| `CSWGuiButton` | `0x0041AD40` | **`0x27` (A) only** |
| `CSWGuiNavigable` / `CSWGuiEditbox` | `0x0041A9D0` | `0x31`+`0x3D` up, `0x32`+`0x3E` down, `0x2F`+`0x3F` left, `0x30`+`0x40` right |
| `CSWGuiListBox` | `0x0041CE20` | `0x31`+`0x3D` up, `0x32`+`0x3E` down, plus its own scroll-bar codes |
| `CSWGuiSlider` | `0x0041ADF0` | up/down or left/right, chosen by the slider's orientation |

Two things fall out of this:

**Why A works at all.** `CSWGuiButton` implements exactly one event, `0x27`. A
button is activated by the A event reaching it through the base panel forwarder.
Nothing panel-specific is involved.

**The unknown codes are aliases.** `0x3D`, `0x3E`, `0x3F` and `0x40` map to the
same handlers as `0x31`, `0x32`, `0x2F` and `0x30` — scroll up, scroll down, left,
right. That accounts for the codes seen on the Abilities and Feats rows that had
no meaning attached.

**Corrections from this pass, both mine:**

- **The per-control button slots were a false lead.** `OnBButtonPressed_2`
  forwarding to control vtable `+0x54`…`+0x60` is real, but those offsets are only
  button handlers *for the class that forwarder was compiled against*. Read on
  arbitrary classes they return whatever happens to sit there — on `CSWGuiBorder`,
  `+0x54` is `CSWGuiImage::Destructor_2`. Most classes point those slots at
  `Global::return_zero` (`0x0063E7F0`) or `Global::self_return` (`0x00641DB0`),
  which are do-nothing stubs. "110 classes have per-button slots" was counting
  stubs and destructors.
- **The ListBox and Slider decodes were wrong twice, in opposite directions.**
  The chain walker first reported codes like `0x22F` and `0x2AE`; I then dismissed
  everything above `0x40` as junk on the grounds that it sat outside `0x28..0xDF`.
  Both were wrong. The walker was wrong because these are search trees, not
  chains. The dismissal was wrong because `0x28..0xDF` bounds the *panel* jump
  tables, never the control dispatchers, and `CSWGuiListBox` compares against
  `0x1F5` explicitly. Read by hand below.

### `CSWGuiListBox` and `CSWGuiSlider`, read by hand

Read instruction by instruction on 2026-09-06, after the chain walker gave two
different wrong answers about them. Both are compiled as **binary search trees**,
not chains: `cmp reg, K` with `jg` to an upper subtree, `je` to K's handler, and
fall-through to the lower one. A linear walker accumulates every `sub`/`dec` it
passes regardless of which branch it is on, which is where `0x22F` and `0x2AE`
came from.

**`CSWGuiListBox::HandleInputEvent` — `0x0041CE20`**

| Event | Handler | Does |
| --- | --- | --- |
| `0x31`, `0x3D` | `0x0041CF26` | scroll selection up |
| `0x32`, `0x3E` | `0x0041CE69` | scroll selection down |
| `0x1F4`, `0x1FB` | `0x0041D047` | scroll bar: line up (`+0x2C2` −= 1, clamped ≥ 1) |
| `0x1F5`, `0x1FC` | `0x0041D16C` | scroll bar: line down (`+0x2C2` += 1, clamped to count) |
| `0x1FD` | `0x0041D31B` | scroll bar: page up (`+0x2C2` −= the float at `+0x2B8`) |
| `0x1FE` | `0x0041D1E1` | scroll bar: page down |

`0x1FB`…`0x1FE` reach the tree through a jump table at `0x0041D3D0`, biased by
`0x1FB`.

**The `0x1F4`…`0x1FE` block is not a console vocabulary.** Every push site for
those codes is inside `CSWGuiListBox` itself, at `0x0041C51C`…`0x0041C596`, where
the scroll bar's own arrow and page-track hits raise them on the listbox through
its own `+0x3C` and stash the code at `+0x88`. They are the scroll bar talking to
its list, not a retained Xbox event. The listbox's retained console events are
only the four in the first two rows.

**`CSWGuiSlider::HandleInputEvent` — `0x0041ADF0`** dispatches on **orientation**
before it dispatches on the event:

```asm
0041AE05  mov eax, [esi+0x10]
0041AE08  cmp eax, [esi+0xC]         ; height vs width
0041AE0C  jle 0x41AE24               ; wider than tall -> horizontal code set
0041AE0E  cmp ebx, 0x3E              ; taller than wide -> vertical code set
```

| Orientation | Decrement | Increment |
| --- | --- | --- |
| Vertical | `0x31`, `0x3D` | `0x32`, `0x3E` |
| Horizontal | `0x2F`, `0x3F` | `0x30`, `0x40` |
| Either | `0x1F5` | `0x1F4` |

This is what the alias set was. `0x3D`/`0x3E`/`0x3F`/`0x40` are not a second
vocabulary and not leftovers; a slider answers to the D-pad axis that matches the
way it is drawn, and the four extra codes are the other axis's pair. Note that
the slider's `0x1F4`/`0x1F5` run the opposite way to the listbox's.

**The default case forwards; it does not ignore.** `0x0041D2B2`, reached by every
code neither tree matches, is not a discard:

```asm
0041D2B2  mov  ax, [esi+0x2C6]        ; the selected item
0041D2B9  cmp  ax, 0xFFFF
0041D2BD  je   0x41D2D6
0041D2C8  mov  ecx, [eax+edx*4]
0041D2D3  call dword ptr [edx+0x3C]   ; hand it to the selected item
0041D2DE  call 0x00418750             ; then to the base control handler
```

So an unmatched event goes down to the selected row and then to
`CSWGuiControl::HandleInputEvent`. **This qualifies every "the panel ignores that
event" in this document**, including the legend `map_retained_gui_events.py`
prints: a `.` means the class does not handle the event *itself*, not that
nothing happens. The same forwarding is why A works everywhere — `CSWGuiButton`
implements only `0x27` and receives it by propagation.

`0x00418750` also carries a **generic event-to-callback table** keyed on the
event code, walked at `+0x38` with a count at `+0x3C` in twelve-byte entries:

```asm
00418790  cmp  dword ptr [eax+8], edi ; entry's event code == this event?
00418795  mov  ebp, [eax+4]           ; entry's handler
0041879D  add  eax, 0xC               ; next entry
```

Handlers can therefore be **registered on a control at runtime** rather than
compiled into a dispatcher. Nothing in this document has looked at who fills that
table, and it may be where the rest of the console bindings live.

### Panels the controller module does not know about

Found in the class table, absent from the module's vtable list, and implementing
events: `CSWGuiInGameGalaxyMap` (13), `CSWGuiPortraitCharGen` (10),
`CSWGuiInGameCredits` (4), `CSWGuiDialog` and its cinematic/computer variants (4),
`CSWGuiExamine` (4), `CSWGuiQuestItem` (4), `CSWGuiSaveNamePanel` (4),
`CSWGuiStatusSummary` (4), `CSWGuiSkillInfoBox` (4), `CSWGuiQuickOrCustomPanel`
(5), `CSWGuiWagerPopup` (16), plus three debug menus —
`CSWGuiCreateItemMenu` (6), `CSWGuiLoadModuleDebugMenu` (6) and
`CSWGuiPowersFeatsSkillsDebugMenu` (6).

`CSWGuiDialog` implementing four events is the notable one: dialogue screens
respond to controller input, and the module has no entry for them at all.

### Branches found but NOT yet walked

Added here as they are discovered, so the tree is honest about its own edges:

1. ~~`CSWGuiListBox` and `CSWGuiSlider` dispatchers must be read by hand.~~
   **Walked 2026-09-06**, both by hand, section above.
2. ~~`CSWGuiControl::HandleInputEvent` (`0x00418750`) and its `+0x38` callback
   table.~~ **Walked 2026-09-06.** It was reading half the system; the other half
   is `AddEvent` and is now extracted — see "The second mechanism" above. New
   branches out of it:
   - **`0x0041A8A0`** (table grow) and **`0x0048DDE0`** (the single-entry path in
     `AddEvent`) — container internals, not read.
   - **The 510 registered handler bodies.** Their addresses are known; none has
     been read. `CSWGuiInGameMenu`'s `0x00624C00` / `0x00624C30`, bound eight
     times each to the eight menu tabs, is the most interesting.
   - **The five call sites whose arguments were not three literals**, listed in
     `gui-event-bindings.txt`; three are in `CSWGuiMainInterfaceAction::Initialize`
     and push registers.
3. **The `0x1F5` push sites outside the listbox** — `0x0040C722`, `0x00419229`,
   and four in `0x0068BBF7`…`0x0068BCE6`. The last four are far from the GUI code
   and unexplained.
4. **The listbox and slider helpers** called from their handlers and not read:
   `0x0041A290`, `0x0041A2D0`, `0x004182B0`, `0x00417EE0`, and `0x0040A1C0`
   (called after every scroll-bar raise).
5. **The 79 control dispatchers beyond those four** were counted but their event
   sets were not tabulated one by one.
6. **Event codes above `0x40`** — resolved as a category. They are not GUI
   events at all: they are **client action ids** belonging to
   `CClientExoAppInternal::HandleInputEvent`, a different layer. `0xCE` pairs
   with `0x09` on the party-change handler. Still open inside that layer:
   - `0xDB`…`0xDE`, `0xE1`…`0xEF`, `0xF0`…`0xF2`, `0xFA`, `0xFB`, `0x107`,
     `0x108`, `0xB5` — handlers located, bodies not read.
   - ~~What feeds the router.~~ **Walked.** `CClientExoAppInternal::ProcessInput`,
     fed by `CExoInput::GetEvents`. The high ids turned out to be the
     `[Keymapping]` ini bindings, which corrects the pairing claim — see
     "Upstream: where the console path is actually cut".
   - **`CSWGuiControllerLossBox`**, the rumble path, and `ResetDriveAcceleration`
     — named, not read.
7. **The panels the module does not know about**, listed above — none of their
   handlers has been read.
8. **What each handler does.** 212 panel events plus the control layer; six
   confirmed in play. An address proves code runs, not that it does anything a
   player wants.

## What is not established

- **Ten dispatchers are still not decoded**: `BARK_BUBBLE`, `CONTAINER`,
  `FLOATY_TEXT`, `INGAME_AUTOPAUSE`, `LEVEL_UP`, `MAIN_MENU`, `NAME`,
  `OPTIONS_GRAPHICS`, `OPTIONS_GRAPHICS_ADVANCED`, `OPTIONS_RESOLUTION`. Their
  rows are absent from the matrix, which means **unknown, not empty**.

  **Correction.** Thirteen were reported undecodable at first, and three of them
  -- `JOURNAL`, `CHARACTER` and `EQUIP` -- were nothing of the sort. They use a
  jump table like the rest, written `add eax, -0x28` where the others use
  `lea eax, [esi-0x28]`. The tool knew only the `lea` form, so it reported those
  panels as having no readable dispatcher, which reads far too easily as "handles
  nothing". Journal turned out to implement A, B, X, Y *and* Black, the widest
  set in the game. A blind spot in a decoder is indistinguishable from an absence
  in the thing being decoded, which is why the undecoded list is printed rather
  than quietly skipped.
- **Most handlers are still unread.** An address in the table proves code runs,
  not that it does something a player would want. Three are now confirmed in play
  and are tabulated above. `STORE` `0x29` calls `0x006C1B00` and `INVENTORY`
  `0x29` sets `[panel+0x1DE4] |= 1`; neither has been tested, and given what Map's
  turned out to be, neither should be tried casually on a save that matters.
- **`0x2D`, `0x2E` and `0x3B`–`0x3F`** share handlers with known events on
  several panels, so they are aliases of something, but which console input each
  corresponds to is unknown.
- **Whether an "Xbox HUD" exists** was not established. The strings above show
  retained console *paths* and a rumble event, not a second HUD layout.

## Why this matters for KMRP

The controller component synthesises keystrokes, which forces every new binding
to fight one that already exists — the effort to give the Abilities screen tab
switching went through the shoulder buttons, the triggers and the stick clicks
before any of it turned out to be unnecessary. Dispatching a retained event
instead asks the engine to do the thing it already knows how to do, with its own
focus behaviour, and cannot collide with a keyboard binding.
