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
