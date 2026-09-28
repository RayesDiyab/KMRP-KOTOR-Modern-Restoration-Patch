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

## Character creation: a panel that answers A and passes it on

Found 2026-09-25 from a crash. `CSWGuiAbilitiesCharGen` (`0x006F8880`),
`CSWGuiSkillsCharGen` (`0x006F6A10`), `CSWGuiFeatsCharGen` (`0x006F4680`),
`CSWGuiPowersLevelUp` (`0x006F28C0`) and `CSWGuiPortraitCharGen` (`0x006F8FF0`)
run their own handler for an event and then call `CSWGuiPanel::HandleInputEvent`
(`0x00409E60`). That forwards the same event to `[panel+0x1C]`, the focused
control. Their buttons register A (`0x27`, the click) to handlers that raise
the panel's own events:

| handler | raises |
| --- | --- |
| `0x00624BA0` `AcceptButtonCallback` | A: vtable `+0x50`, `0x0040B640`, `HandleInputEvent(0x27, 1)` |
| `0x00624BB0` | B: `+0x54`, `0x28` |
| `0x00624BC0` | X: `+0x58`, `0x29` |
| `0x00644720` | Y |
| `0x0067CB40` / `0x0067CB50` | D-pad left / right, `0x2F` / `0x30` (the − and + buttons) |

A reaching the panel with a button focused whose click raises A (Attributes'
OK, Skills' OK, Feats' Add, Powers' OK, Portrait's OK) never ends. The stack
overflows: `0xC00000FD` at `swkotor.exe+0x3000BE`, three times on the
maintainer's machine. A focused button whose click raises something else runs
after the panel's A (A on Cancel: accept, then cancel). The mouse never meets
either, because `[panel+0x1C]` is set by focus navigation, not by clicking.
The module's guard, `GuardChargenConfirmK1`, hooks all five entries. See
`CHANGELOG.md`.

### Every panel that carries such a button (2026-09-26)

Found while previewing level-up: with the D-pad focus on the Character screen's
Level Up, one A opened the level-up screen twice and the game froze. Every
`AddEvent` that registers one of these handlers was listed from the image; each
panel's vtable `+0x50` is `0x0040B640` and `+0x5C` is `0x0040B670`, so each
click raises A or Y on its own panel. Whether A then acts twice or without end
depends only on whether the pad can put the focus on the button:

| panel (.gui) | vtable | dispatcher | the panel answers | pad focus on the button |
| --- | --- | --- | --- | --- |
| status summary (`statussummary`) | `0x0074FF68` | `0x00625AC0` | A: closes | never, `K1_NO_PAD_FOCUS_PANELS`; the loop measured 2026-09-25 |
| Character (`character`) | `0x00756100` | `0x006B2250` | A: level up; Y: auto level up | never, the same list; the double level-up measured 2026-09-26 |
| skill-info notice (`skillinfo`): granted feats, recommended powers | `0x00757940` | `0x006CD3C0` | A, B: close | never, the same list; in play its list held the focus |
| Attributes, Skills, Feats, Powers, Portrait, Name | | hooked | A and Y | allowed: `GuardChargenConfirmK1` presses the focused button once |
| Map (`map`) | `0x00754830` | `0x00693BC0` | A | the Map navigates itself, so the pad moves no focus there |
| galaxy map (`galaxymap`, `BTN_ACCEPT`) | `0x00754910` | `0x00695980` | not decoded | **not measured** |
| Journal (`journal`, `BTN_SWAPTEXT`, raises Y) | `0x00751960` | `0x006456E0` | Y (`0x006459CE`); not A | **not measured** |
| Inventory (`inventory`, `BTN_USEITEM`) | `0x007564E0` | `0x006B3ED0` | not A | **not measured** |
| Container (`container`) | `0x007567E0` | `0x006B92F0` | not decoded | **not measured** |
| Save / Load (`saveload`, `LB_GAMES`) | `0x00757650` | `0x006C86D0` | not A | **measured safe**: with `LB_GAMES` focused (`[panel+0x1C]` = panel `+0x934`), A loaded the save, on 2026-09-26 and 2026-09-28 |
| Script Select (`ScriptSelect`, `BTN_Accept`) | `0x007590A8` | `0x006E9BC0` | A (`0x006E9BEF`) | **not measured** |
| credits (`credits`) | `0x007541F0` | `0x0068F350` | not decoded | **not measured** |
| `pause` | `0x00756DC8` | `0x00409E60` itself | nothing | **not measured** |

What happens on a **not measured** row cannot be read from this table. A
focused control's own class decides what it does with the event before any
registered handler runs: Save / Load's thunk sits on a list box, and A with
that list focused loaded the save once, no loop. So nothing here says those
screens misbehave; only that they have not been walked.

*Corrected 2026-09-28:* the first version of this table said that on
Inventory, Save / Load and `pause` "a focused button raising A would loop",
and on the Journal that A "would act once more". Those were inferences, and
Save / Load's was wrong.

A panel is safe when its list keeps the D-pad (focus stays on the list, as on
the granted-feats notice) or when it navigates itself (the Map). The rows
marked **not measured** needed a pad-only walk of that screen, or a guard that
covers them all at once: `CSWGuiPanel::HandleInputEvent` (`0x00409E60`)
forwarding an event to a focused control whose handler for it raises the same
event on the same panel is recursion with no legitimate use. The guard was
built on 2026-09-28 (next section).

### The echo guard, for every panel (2026-09-28)

At the maintainer's request ("create this for all screens"), every `AddEvent`
call in the image was listed (`0x0041AB20`; 515 calls). An entry is 12 bytes,
`{receiver, handler, event}`, at `[control+0x38]`, count at `+0x3C`, and
`CSWGuiControl::HandleInputEvent` (`0x00418750`) runs the first entry for the
event with a non-null handler; the button class (`0x0041AD40`) plays its click
sound (`0x0040A140`) and then does the same through `0x0041A9D0`. 62 of the
515 register one of the four raise thunks, on 39 panels:

| panel (.gui) | vtable | dispatcher | answers A itself | buttons: what the click presses |
| --- | --- | --- | --- | --- |
| `messages` | `0x0074FD18` | `0x00628260` | no | `?` → X, `?` → B |
| `statussummary` | `0x0074FF68` | `0x00625AC0` | yes | `+0x44` → A |
| `journal` | `0x00751960` | `0x006456E0` | no | `+0x44` → X, `+0xA68` → Y, `+0xDF0` → B |
| `credits` | `0x007541F0` | `0x0068F350` | yes | `?` → A |
| `map` | `0x00754830` | `0x00693BC0` | yes | `?` → X, `+0x728` → A, `+0x8EC` → B |
| `optionsingame` | `0x00755DE0` | `0x006AAEC0` | no | `+0x1BE8` → B |
| `abilities` | `0x00755E50` | `0x006AE5F0` | no | `+0x369C` → B |
| `character` | `0x00756100` | `0x006B2250` | yes | `+0x47A4` → Y, `+0x4968` → A, `+0x523C` → B, `+0x5400` → X |
| `inventory` | `0x007564E0` | `0x006B3ED0` | no | `+0x1164` → B, `+0x1328` → A, `+0x14EC` → X |
| `container` | `0x007567E0` | `0x006B92F0` | yes | `+0x44` → A, `+0xC94` → B, `+0xE58` → X |
| `equip` | `0x007569A0` | `0x006BA3F0` | no | `+0x385C` → B |
| `partyselection` | `0x00756D28` | `0x006BEDE0` | not decoded | `+0x44` → B |
| `pause` | `0x00756DC8` | `0x00409E60` | no | `+0x44` → A |
| `store` | `0x00756E38` | `0x006C2190` | no | `+0x1D20` → B |
| `upgradeitems` | `0x00757228` | `0x006C2D30` | no | `+0xA68` → B |
| `upgrade` | `0x00757298` | `0x006C6A80` | no | `+0x2D84` → B |
| `saveload` | `0x00757650` | `0x006C86D0` | not decoded | `+0x44` → A, `+0x44` → X, `+0xDD8` → B |
| `skillinfo` | `0x00757940` | `0x006CD3C0` | yes | `+0x484` → A |
| `QuestItem` | `0x00757C20` | `0x006D24D0` | no | `+0x10` → B |
| `CHARGEN` | `0x00758020` | `0x006DBD30` | no | `+0x14` → B |
| `titlemovie` | `0x00758130` | `0x006DCE80` | not decoded | `+0x44` → B |
| `optfeedback` | `0x007581E8` | `0x006DE430` | no | `+0x8A4` → B |
| `optresolution` | `0x00758348` | `0x006E0CF0` | not decoded | `?` → B |
| `optmouse` | `0x007585F8` | `0x006E6180` | no | `?` → B |
| `optsound` | `0x007587C0` | `0x006DDB90` | no | `+0x11A4` → B |
| `optionsmain` | `0x00758838` | `0x006DFF10` | no | `?` → B |
| `optgameplay` | `0x00758E00` | `0x006E6180` | no | `+0x5C4` → B |
| `ScriptSelect` | `0x007590A8` | `0x006E9BC0` | yes | `+0x8B0` → B |
| `OPTKeyMapping` | `0x00759358` | `0x006EC510` | not decoded | `+0x538` → B |
| `LEVELUPPNL` | `0x00759568` | `0x006EE720` | not decoded | `+0x1944` → B |
| `CUSTPNL` | `0x007595E0` | `0x006EF610` | not decoded | `+0x1AF8` → B |
| `QUICKPNL` | `0x00759668` | `0x006F0280` | not decoded | `+0xE10` → B |
| `QORCPNL` | `0x00759710` | `0x006F0E10` | no | `+0xBD4` → B |
| `pwrlvlup` | `0x00759780` | `0x006F28C0` | yes | `+0x12AC` → Y, `+0x1470` → X, `+0x1634` → A, `+0x17F8` → B |
| `FTCHRGEN` | `0x007598B0` | `0x006F4680` | yes | `+0xCEC` → X, `+0xEB0` → B, `+0x1074` → Y, `+0x1238` → A |
| `SKCHRGEN` | `0x00759990` | `0x006F6A10` | yes | `+0x27EC` → A, `+0x29B0` → B |
| `ABCHRGEN` | `0x00759C68` | `0x006F8880` | yes | `+0x2324` → A, `+0x24E8` → B |
| `PORTCUST` | `0x00759EA8` | `0x006F8FF0` | yes | `?` → B |
| `NAME` | `0x00759F38` | `0x006FA220` | no | `?` → B, `+0x7D4` → Y |

The offset is the control's place in the panel, where the scan could tie the
`AddEvent` call's `this` to one. `?` is a call it could not tie, and `+0x44`
is the first control slot, which several panels reach through a register the
scan did not follow, so treat both as "some button on this panel". "Answers A
itself" is read from the dispatcher's switch; "not decoded" means the scan did
not follow it. The table misses nothing the guard needs: the guard reads the
registrations at run time, not from this list.

With such a button focused, one A reaches the panel, which acts, then hands A
to the button, which presses its own event back: A again (an echo, the loop
above) or B, X or Y (a second action). Two halves in
`src/controller-native/K1NativeJoystick.cpp` fix both, on every panel:

1. **A presses the focused button, and only it** (`PressFocusedRaiseButtonK1`,
   the last entry of `K1_BUTTON_REMAPS`, slot `0x74`). When the panel in front
   has a visible, enabled button focused whose click is one of the four thunks
   on that same panel, the pad's A calls the button's `HandleInputEvent(0x27, 1)`
   instead of raising A on the panel -- exactly what a mouse click does, click
   sound included. The screens with their own A path are left alone:
   Attributes, Skills, Feats, Powers, Portrait, Name and the resolution box
   (`K1_OWN_CONFIRM_DISPATCHERS`). Only buttons (`0x0041AD40`) qualify, so a
   list box such as Save / Load's keeps its own behaviour.
2. **A panel never hands an event to a control that would press it back**
   (`GuardPanelEchoK1`, a detour on `0x00409E60`). When `[panel+0x1C]` is a
   button or plain control (`0x00418750`) whose first handler for the event is
   the thunk that presses that same event on this panel, and the panel's vtable
   slot is the stock `0x0040B640`..`0x0040B670`, the event argument becomes the
   inert `0x41`. The panel has already acted; only the echo is dropped. Stolen
   bytes `8B 49 1C 85 C9` (`mov ecx,[ecx+0x1C]` / `test ecx,ecx`) touch neither
   EAX nor ESP.

Both write to `kmrp-confirm-focus.log` (256 lines at most): `guard panel=<vtable>
event=<e> value=<v> -> A presses the focused button` or `-> the focused control
would press it back -> inert`.

**Seen in game on 2026-09-28**, `9736B41F…` in a scratch copy at 3440x1440 on
the virtual pad: A on a focused Close on Gameplay and on the in-game Options
(one "A presses" line each, each closing once); OK focused on level-up Skills
with points left (the chargen guard pressed OK, one "unspent skill points" box,
one "inert" line for Skills' vtable `0x00759990`); Save / Load's list, the
Inventory list (one use of a shield, 3/5 to 2/5 charges), Messages, the
Journal's A and Y, the Map's A to Party Selection and B, Abilities, Start, and
a conversation, with no guard line. The rows of the table above that were
**not measured** are covered by the guard, but only those screens were walked.

`CSWGuiManager::HandleInputEvent` (`0x0040C8E0`), for reference: with a modal
panel open, the event goes to the top modal only (`0x0040CA37`). Otherwise it
goes to every panel in the list, from a copy of it (`0x0040CAA2`). The box that
Attributes shows is modal, pushed with `(box, 1, 1)` through `0x0040BC70` →
`0x0040BD90`.

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
SOLO_MODE_QUERY                   6c244c    6c2488         .         .         .         .    6c244c    6c2488         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
STORE                                  .    6c21c6    6c222f         .         .         .         .    6c21c6         .         .         .         .         .         .         .         .         .         .    6c220d    6c21eb
UPGRADE                                .    6c6aaf         .         .         .         .         .    6c6aaf         .         .         .         .         .         .         .         .         .         .    6c6b17    6c6aec
UPGRADE_ITEM_SELECT                    .    6c2d57         .         .         .         .         .    6c2d57         .         .         .         .         .         .         .         .         .         .    6c2da3    6c2d81
UPGRADE_SELECTION                      .    6c2b2b         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .         .   [chain]
```

**The controller module sends five of these codes.** Everything else in the
table is reachable code that nothing currently triggers.

**Correction, 2026-09-20.** The `SOLO_MODE_QUERY` row above read `2e` alone
until today, which contradicted finding 7 in
[`../docs/controller-behaviour-matrix.md`](../docs/controller-behaviour-matrix.md)
and made the panel look as though it implemented neither A nor B. Finding 7 was
right: the row was printed before the decoder fault described in the tool's own
source was fixed, and nobody reprinted it. Re-read from the same executable this
document names, the dispatcher at `0x006C2400` is a `cmp`/`je` chain handling
`0x27`/`0x2D` at `0x006C244C` and `0x28`/`0x2E` at `0x006C2488`, and the row now
says so. Verified against the build in the header, byte-for-byte the installed
`swkotor.exe`.

The rest of the table is **not** regenerated output: `map_retained_gui_events.py`
in its plain table mode now raises `TypeError` on the first chained dispatcher it
meets, because a chain has no jump-table index to look up, so the table cannot be
reprinted as a whole. `--full` handles both shapes and is the authoritative mode
until that is repaired; it is what the correction above was read from.

**Pazaak's wager, decoded by hand 2026-09-25.** The panel is absent from the
table (vtable `0x007534C8`, constructor `0x0067F000`). Its dispatcher,
`0x0067E150`, is a jump table on `event - 0x27`:

| events | handler | what |
| --- | --- | --- |
| `0x27`, `0x2D` | `0x0067E17F` | accept the wager (`0x0067D3B0`), a sound, close |
| `0x28`, `0x2E` | `0x0067E1BB` | quit |
| `0x2F`, `0x32`, `0x3A`, `0x3B`, `0x3E`, `0x3F` | `0x0067E221` | lower the wager while it is above 1 |
| `0x30`, `0x31`, `0x39`, `0x3C`, `0x3D`, `0x40` | `0x0067E23D` | raise it while it is below the maximum (`[panel+0xC98]`) |

Everything then goes on to the base handler, `0x00409E60`. Its Less and More
buttons are a button subclass (vtable `0x007533C8`) carrying two floats, 0.2
and 0.5, at `+0x1C4` and `+0x1C8`. `K1_NATIVE_DIRECTION_PANELS` lists the dispatcher since
that day.

**Where Y and the D-pad are registered on the options screens** (the bindings
tool, `--code`): Y (`0x2A`) on Graphics' gamma slider (`0x006E0190`) and Sound's
four volume sliders (`0x006E0F50`); the D-pad (`0x2F`/`0x30`, `0x3F`/`0x40`) on
Mouse's sensitivity, Graphics' gamma and Sound's four sliders (`0x006DFEE0`,
`0x006DED30`, `0x006DF9B0`), and `0x2F`/`0x30` on Gameplay's Difficulty
(`0x006E68E0`, `0x006E6930`). The slider handlers test their control's `+0x4C`
and re-apply the value.

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

*Since then (checked 2026-09-25 against `src/controller-native/K1NativeJoystick.cpp`,
the module the installer ships):* the native path no longer synthesises
keystrokes for these buttons:
- It registers A, B, X, Y and Black as the retained events `0x27`...`0x2B`
  through the engine's own `CreateNewEvent` and `AddEvent`, which is the third
  route below.
- It calls `CClientExoAppInternal::HandleInputEvent` (`0x00621210`) directly
  for the gameplay verbs and the Map (`0xD7`).

The legacy keyboard path this section describes is no longer what the installer
installs.

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
(*That was true when written. The shipped module now uses route 3. For the
gameplay verbs and the Map it also calls `CClientExoAppInternal::HandleInputEvent`
(`0x00621210`), a different layer from route 1. See the note under "Why this
matters for KMRP" above.*)

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

## Record semantics, and the binding that is still required

Answers to the implementation checklist, from `GetJoystickBuffer`
(`0x005E30E0`) and its consumer `CExoInputInternal::GetEvents` (`0x005E24E0`).

### The record fields

| Field | Offset | Written by the engine | Consumed? |
| --- | --- | --- | --- |
| `dwOfs` | `+0x00` | the control code | **yes** — matched against a description |
| `dwData` | `+0x04` | `0` / `1` for buttons (`shr ebx, 7`) | yes |
| `dwTimeStamp` | `+0x08` | **`0`** | not in this path |
| `dwSequence` | `+0x0C` | **`0`** | **yes**, orders the cross-device merge |
| `uAppData` | `+0x10` | never written | no |

`dwSequence` being read but written as zero is not a contradiction: with every
record carrying zero the merge comparison is always equal and ordering falls back
to device order. A replacement should **write zeros too**. Inventing increasing
sequence numbers would change merge behaviour relative to the keyboard and mouse.

Only the first `0x100` bytes of the `0x1400` allocation are cleared
(`mov ecx, 0x40; rep stosd` at `0x005E3129`), so a replacement must write every
field of every record it emits rather than relying on zeroed memory.

### Buttons

```asm
005E320A  mov   edi, 0x20          ; 32 buttons -- DIJOYSTATE.rgbButtons[32]
005E3210  mov   al, [ecx+ebx]      ; current
005E3213  xor   al, [edx]          ; previous
005E3217  jns   0x5E325B           ; unchanged -> emit nothing
005E322F  shr   ebx, 7             ; high bit -> dwData 0 or 1
```

Edge-triggered, one record per changed button, `dwData` strictly `0` or `1`.

### The previous-state store is `rawInput+0x2C`

The diff reads two parallel arrays, and `0x005E31D1` loads the second from
`rawInput+0x2C` (`mov ebx, [ebx+0x2c]`, then `[ebx+4]` and `[ebx+0x18]`). That
identifies the field this document previously listed as unknown: **`+0x2C` holds
the per-device previous `DIJOYSTATE` snapshot**. A replacement that keeps its own
snapshot never touches it, which retires the last of the three mystery fields.

### Records alone do nothing — a binding is still required

This is the constraint that matters most, and it is easy to miss. `GetEvents`
resolves descriptions **per input class and per device**:

```asm
005E271E  mov ecx, [esp+0xE4]        ; input class
005E2725  lea ecx, [eax+eax*2]       ; class * 3
005E2728  lea eax, [edx+ecx*4]       ; + device index
005E272B  mov ecx, [esi+eax*4+0x14]  ; -> that (class, device) description list
005E2733  mov eax, [ecx]
005E2735  test eax, eax
005E2737  je  0x5E279C               ; empty -> record discarded
```

and then matches each description's control against the record:

```asm
005E275B  mov eax, [edi+0x1c]              ; the description's control slot
005E275E  mov ecx, [esi+eax*4+0x164]       ; slot -> control code
005E2769  cmp ecx, [edx]                   ; against record dwOfs
005E276B  je  0x5E27AE                     ; matched
```

So feeding perfect records into a device with no registered descriptions produces
**nothing at all**. Enumeration or a `GetJoystickBuffer` replacement is necessary
and not sufficient; `SetEventDescriptions` must also register descriptions naming
that device's controls, in the right input class.

There is also a control-code indirection table at `CExoInputInternal+0x164`,
indexed by a description's slot at `+0x1C`. Its contents have not been read.

### Still unmapped

- The exact `dwOfs` values the button, axis and POV paths emit.
- The axis paths (`0x005E34xx`–`0x005E36xx`) and how POV becomes direction bits.
- Truncation behaviour at 256 records.
- The `+0x164` control-code table.
- ~~Which description type names a joystick control.~~ **Answered: none, and
  none is needed.** The type takes no part in matching; the control comes from
  the description's slot field, and the joystick slots are already populated.
  See "The binding system, reconstructed".

## The binding system, reconstructed

The question this phase had to answer: can the surviving event-description system
name a joystick control, without modifying `GetEvents`? **Yes.** The control codes
are already in memory, initialised on every launch, and the description type is
irrelevant to matching.

Confirmed against the running game on 2026-09-07.

### 1. The control-code table at `CExoInputInternal+0x164`

A flat `DWORD[]` indexed by a **control slot id**, holding the device-specific
code that gets compared against `DIDEVICEOBJECTDATA.dwOfs`. Built entirely in
`CExoInputInternal::Constructor` (`0x005E1880`, from `0x005E1958`), where each
slot id is read from a global and the code is an immediate:

```asm
005E1958  mov ecx, [0x0074D5AC]
005E195E  mov dword ptr [esi+ecx*4+0x164], 0x30
```

Slot ids are consecutive from the globals at `0x0074D594` onward. **`0x84` is the
"no control" sentinel** -- `AddEvent` skips a control lookup when the slot equals
it, which is why every `CreateNewEvent` call in `SetEventDescriptions` passes
`132` as its last argument.

Live contents of the joystick range, read from the running process:

| Slot | Code | Meaning |
| --- | --- | --- |
| `0x6E` | `0x00` | `DIJOFS_X` |
| `0x6F` | `0x04` | `DIJOFS_Y` |
| `0x70`, `0x73` | `0x20` | `DIJOFS_POV(0)` |
| `0x71` | `0x18` | `DIJOFS_SLIDER(0)` |
| `0x72` | `0x1C` | `DIJOFS_SLIDER(1)` |
| `0x74` ... `0x7E` | `0x30` ... `0x3A` | **`DIJOFS_BUTTON(0)` ... `DIJOFS_BUTTON(10)`** |
| `0x7F` ... `0x82` | `0x384`, `0x38C`, `0x388`, `0x390` | four further codes, unidentified |

The same table also holds keyboard DIK codes (`0xC8` up, `0xCB` left, `0xCD`
right, `0xD0` down, `0x39` space) and mouse offsets (`0`, `4`, `8` axes; `0xC`,
`0xD`, `0xE` buttons). One table, three device families.

**Nothing about the joystick half was removed.** It is populated in the live
process right now, with no pad attached and no joystick device enumerated.

### 2. Device numbering

Globals, read live: `[0x0074D3C4] = -1` (any/none), `[0x0074D3C8] = 0`
(keyboard), `[0x0074D3CC] = 1` (mouse). **Joysticks are device 2 upward**, which
matches the `lea eax,[edi-2]` index in the poll loop.

### 3. The description object

`CreateNewEvent(eventId, descType, device, controlSlot, secondControlSlot)`,
`ret 0x14`. Field assignments from `0x005E0F44`-`0x005E0F60`:

| Offset | Field |
| --- | --- |
| `+0x00` | vtable |
| `+0x08` | use count, incremented by `AddEvent` |
| `+0x10` | **event id**; also the linked-list node (`AddHead(desc+0x10)`) |
| `+0x14` | description type |
| `+0x18` | **device** |
| `+0x1C` | **control slot**, feeding the `+0x164` lookup |
| `+0x20`, `+0x24` | zero (min / max) |
| `+0x28`, `+0x2C` | `1.0f` (scale) |
| `+0x30` | second control slot, `0x84` when unused |
| `+0x34` | 2-button-axis only |

`descriptions[eventId]` lives at `obj+0x128`, capacity at `obj+0x12C`.
`CreateNewEvent` **fails if the slot is already occupied** (`test ecx,ecx; jne`),
so an event id must be free.

### 4. What types 0, 2 and 5 are

They allocate the plain `CExoInputEventDesc` (`0x20` bytes, vtable `0x0074D5FC`)
-- the same class as type 1. Type 3 allocates `CExoInputEventDescDetailed`
(`0x30` bytes, vtable `0x0074D604`, carrying the scale floats); type 4 allocates
`CExoInputeventDesc2ButtonAxis` (`0x38` bytes, vtable `0x0074D60C`).

**The type does not participate in matching.** The only virtual consulted during
matching is `vtable+4`, and it is a constant: `Global::return_zero` for the base
and Detailed classes, `Global::return_true_2` for `2ButtonAxis`. It answers
whether a second control exists, nothing more.

So types 0, 2 and 5 are not a missing joystick facility *for matching*, and
**any type can name a joystick control**, because the device comes from `+0x18`
and the control from `+0x1C`.

**But the type is not inert.** It selects the value computation in
`PollInput_2`, and types 0, 2 and 5 are the single-control **analog** paths --
see "Analog: the engine carries stick magnitude" below.

### 5. The matching path

```
for each device d, merged across devices by record dwSequence:
  for each record r in buffer[d]:
    list = obj[0x14 + (d + inputClass*12)*4]      # per (class, device)
    if list is empty: discard r                   # 0x005E2737
    for desc in list:
      code = obj[0x164 + desc[0x1C]*4]            # 0x005E275E
      if code == r.dwOfs: MATCH                   # 0x005E2769
      if desc->vtable[1]():                       # 0x005E2771, 2-button axis only
        code2 = obj[0x164 + desc[0x30]*4]
        if code2 == r.dwOfs: MATCH
    on MATCH: raise event desc[0x10]
```

### 6. The minimum description for one joystick button

```c
CreateNewEvent(eventId,        /* any free slot; 0x27..0x40 are all free */
               1,              /* description type -- 1 is the common one */
               2,              /* device: first joystick */
               0x74,           /* control slot -> DIJOFS_BUTTON(0) */
               0x84);          /* no second control */
AddEvent(eventId, inputClass); /* class 2 is ICPCGUI */
```

Two calls. No new structures, no table edits, no `GetEvents` change.

### 7. Is the native architecture still viable?

**Yes, and more cheaply than expected.** The binding half needs no reconstruction
at all -- it needs two ordinary calls into functions that still exist and still
work. What remains missing is only what was already known: the device count is a
hardcoded zero, and no records are produced.

The console event ids `0x27`..`0x40` are all free in `descriptions[]`, since
nothing registers them, so a joystick button can be bound directly to a retained
console event with no id juggling.

### 8. Smallest next proof

Still no `GetJoystickBuffer` replacement. Instead, in the debugger:

1. Register one description as in section 6, bound to a console event id.
2. Force `rawInput+0x18` to 1 so the device count becomes 3 and the poll loop
   runs device index 2.
3. Stage a single `0x14`-byte record with `dwOfs = 0x30`, `dwData = 1`,
   `dwTimeStamp = 0`, `dwSequence = 0`.
4. Break on the matcher at `0x005E2769` and confirm the comparison succeeds, then
   on the resulting event.

That proves the whole chain with two function calls and one staged record, and is
fully reversible.

## PROVEN: one synthetic joystick record becomes one native KOTOR event

Run in the debugger against the live patched game on 2026-09-07. Nothing was
written to disk; every change was in-process and has been reverted.

### Method

A code stub was assembled into a scratch page and executed by hijacking `eip` at
a clean function entry (`CExoInputInternal::GetEvents`), then restoring the
saved registers. The stub made exactly two calls:

```
CreateNewEvent(0x31, 1, 2, 0x74, 0x84)   ; event 0x31, type 1, device 2,
                                         ; control slot 0x74, no 2nd control
AddEvent(0x31, 2)                        ; into input class 2 (ICPCGUI)
```

Both returned **1**. Input class 2 was not guessed: `GetEvents`' third argument
was read live at a breakpoint and was `2`.

Note the argument order, which corrects an earlier note in this document:
`AddEvent(eventId, inputClass)`, not the reverse. `arg1` is the event id
(`descriptions[arg1]` is dereferenced) and `arg2` is bounds-checked against 6.

### The description the engine built

Read back from `descriptions[0x31]` at `0x13846440`:

| Offset | Value | Meaning |
| --- | --- | --- |
| `+0x00` | `0x0074D5FC` | `CExoInputEventDesc` vtable |
| `+0x08` | `1` | use count, incremented by `AddEvent` |
| `+0x10` | `0x31` | event id |
| `+0x14` | `1` | description type |
| `+0x18` | `2` | device — first joystick |
| `+0x1C` | `0x74` | control slot -> `DIJOFS_BUTTON(0)` |

Fields from `+0x20` up are unallocated: the base path allocates only `0x20`
bytes, and `+0x1C` is its last field. That is safe because `+0x30` is read only
when `vtable+4` reports a two-button axis, which this type never does.

The per-(class, device) list at `obj + 0x14 + class*48 + device*4` = `+0x7C`
pointed at a list with **count 1**, whose single node held `desc+0x10`.

### The chain, observed

Device count was forced by writing `CExoInputInternal+0x158 = 3`. Writing
`rawInput+0x18` does nothing at runtime — the constructor already consumed it —
which is worth remembering for the real implementation.

`GetJoystickBuffer` then ran for joystick index 0 and took its null-device exit,
having already allocated the record buffer. One record was written into that
buffer at its exit and the count set to 1:

```
dwOfs = 0x30, dwData = 1, dwTimeStamp = 0, dwSequence = 0, uAppData = 0
```

At the matcher (`0x005E2769`), with a break condition of `ecx == 0x30`:

| Register | Value | Meaning |
| --- | --- | --- |
| `eax` | `0x74` | control slot read from `desc+0x1C` |
| `ecx` | `0x30` | `table164[0x74]`, the resolved control code |
| `edx` | `0x03D4A060` | the staged record |
| `edi` | `0x13846440` | the description |
| `ebx` | `0x03D257D4` | the (class 2, device 2) list slot |

Stepping the `cmp ecx, [edx]` and its `je` landed on **`0x005E27AE`** — the match
path, which sets the matched flag.

Execution then stopped at `0x00622C5C` in `ProcessInput`, the call into
`CSWGuiManager::HandleInputEvent`, with a break condition of `edi == 0x31`:

```
edi = 0x31    the event id carried from desc+0x10
ebp = 1       the dwData carried from the staged record
```

and was allowed to run into the handler.

### What this establishes

A synthetic `DIDEVICEOBJECTDATA` record, attributed to a joystick device that
does not exist, produced a real native KOTOR GUI event through entirely
unmodified engine code. Nothing was patched: the two registration calls are the
engine's own API, and the only writes were a device count, a record, and a count.

**The native-path architecture is proven end to end.** What remains is
implementation rather than feasibility:

1. A `GetJoystickBuffer` replacement that emits records from a real pad. It must
   allocate its record buffer the way the original does, since the consumer frees
   it, and it must write every field of every record because only the first
   `0x100` bytes of the `0x1400` allocation are cleared.
2. Registration of the descriptions KMRP wants, at a point after
   `CExoInputInternal` is constructed.
3. Setting `CExoInputInternal+0x158`, not `rawInput+0x18`.

### Reverted

`+0x158` back to `2`, `rawInput+0x18` back to `0`, scratch page freed, temporary
breakpoints removed. The description registered for event `0x31` remains in
memory for this session only and is inert once the device count is back to 2; it
disappears on restart. No file on disk was modified.

## Analog: the engine carries stick magnitude, and types 0/2/5 are why

The description type turned out to matter after all -- not for matching, but for
**value computation**. This section corrects and completes the earlier claim that
types 0, 2 and 5 were inert numbering.

### `PollInput` returns a float

`CExoInputInternal::PollInput_2` (`0x005E23C0`) takes `(eventId, inputClass)` and
returns a **float in `st(0)`**. It checks `IsEventInClass`, fetches the
description, and then dispatches on `[desc+0x14]`, the description type, through
a jump table at `0x005E24C8`:

| Type | Target | Value computation | Constructed by the game |
| --- | --- | --- | --- |
| **0, 2, 5** | `0x005E241D` | `ScaledValue(desc, desc+0x1C, desc+0x04)` -- **single-control analog** | **never** |
| 1 | `0x005E2410` | returns the constant at `0x0073D700`, which is **`0.0f`** -- digital | 17 times |
| 3 | `0x005E2459` | `ScaledValue` over the range `desc+0x24 - desc+0x04` | 8 times |
| 4 | `0x005E242F` | two `ScaledValue` calls, `fsubr` -- two controls forming one axis | once |

So the three unused types are the **single-control analog value paths**. The PC
build never constructs one because it never binds an analog device. They are
exactly what a joystick axis needs.

Type 1, which the 17 keyboard bindings use, returns `0.0f` from `PollInput`: a
digital key carries no magnitude and is consumed as a discrete event instead.
Type 1 was the right choice for the button proof, and would be the wrong choice
for a stick.

### `ScaledValue` special-cases the joystick axes

`CExoInputInternal::ScaledValue` (`0x005DFD80`) converts the raw integer with
`fild` and then branches on the control slot:

```asm
005DFDA1  mov  eax, [ebx+0x20]        ; scaling configured on this description?
005DFDA6  je   0x5DFF2F               ;   no -> unscaled
005DFDEA  cmp  edi, [0x0074D594]      ; slot 0x6E -- joystick X
005DFDF2  cmp  edi, [0x0074D598]      ; slot 0x6F -- joystick Y
005DFDFA  cmp  edi, [0x0074D5A0]      ; the slider slots
005DFE1A  mov  ecx, [esi+edi*4+0x164] ; resolve the control code
005DFE2C  call GetMaxUseable(device, code)
          ... GetMinUseable(device, code)
```

The joystick X and Y slots are named explicitly, and the raw value is normalised
against the device's usable range. Mouse axes take a different branch and are
multiplied by the constant at `0x00741C24`, which is `0.0078125` -- exactly
`1/128`.

`desc+0x20` gates scaling and is zero on a fresh description, so scaling must be
configured through `CExoInput::ScaleEvent` (`0x005DF480`). The game calls it six
times from `SetEventDescriptions`, fed by the `Scale`, `ScaleMag` and `ScaleExp`
columns of `keymap.2da`.

### Who consumes the float

`CExoInput::PollInput` has **51 call sites**: 47 in
`CClientExoAppInternal::ProcessInput` and 4 in
`CClientExoAppInternal::UpdateCamera`. Gameplay movement and camera read event
values as floats through this API, not as discrete events.

### What this means

Graded analog movement is **available in principle**: the value path exists, the
joystick axis slots are named in the scaling code, the normalisation is against
the device's own range, and the consumers take floats.

What is **not** yet established, and should not be claimed until measured:

- Whether the specific movement events `ProcessInput` polls are among the ones
  that take a magnitude, or whether the surviving PC bindings feed them digitally
  and the movement code thresholds the result anyway.
- What `GetMaxUseable` / `GetMinUseable` return for a joystick device, since both
  currently branch on the keyboard and mouse device ids and no joystick has ever
  been registered.
- What the `Scale`, `ScaleMag` and `ScaleExp` values in `keymap.2da` do to the
  curve.

The cheap test, once a joystick description of type 0 exists on slot `0x6E`, is
to stage records with a quarter, half and full axis value and read `PollInput`'s
return, before involving the movement code at all.

## MEASURED: analog magnitude survives PollInput intact

Run in the debugger against the live game on 2026-09-07. Nothing written to disk.

### Setup

| Item | Value |
| --- | --- |
| Event id | `0x32` (free; nothing registers `0x27`..`0x40`) |
| Description type | **0** — the single-control analog path |
| Device | `2` — first joystick |
| Control slot | `0x6E` -> `DIJOFS_X` |
| Second control | `0x84` (none) |
| Input class | `2` (ICPCGUI), read live from `GetEvents`' third argument |

`CreateNewEvent(0x32, 0, 2, 0x6E, 0x84)` and `AddEvent(0x32, 2)` both returned
`1`. The description at `0x138469E0` read back `+0x14 = 0`, `+0x18 = 2`,
`+0x1C = 0x6E`.

`PollInput` reads the description's stored value at **`desc+0x04`**, not the
record directly (`mov eax,[esi+4]` at `0x005E241D`), so the sweep set `desc+0x04`
and called `CExoInputInternal::PollInput_2` (`0x005E23C0`), capturing `st(0)`.

### Result: exact linear passthrough

| Raw value | Returned float | Ratio |
| --- | --- | --- |
| `0` | `0.0` | — |
| `8192` (25%) | `8192.0` | 1.000000 |
| `16384` (50%) | `16384.0` | 1.000000 |
| `24576` (75%) | `24576.0` | 1.000000 |
| `32767` (100%) | `32767.0` | 1.000000 |
| `-8192` | `-8192.0` | 1.000000 |
| `-16384` | `-16384.0` | 1.000000 |
| `-32768` | `-32768.0` | 1.000000 |

**Linear, signed, unclamped, no deadzone, no curve.** Type 0 returns
`float(rawValue)` exactly.

The reason is structural: `ScaledValue` opens with `call [vtable+0]`, and the
base class used by types 0, 2 and 5 has `Global::return_zero` there, so it takes
the early exit at `0x005DFF2F`, which is `fld` of the value it converted with
`fild` on entry. That early exit happens **before** any control-slot logic, so
slot `0x6F` (Y) is identical by construction rather than by measurement — the
slot is never consulted on this path.

### The type 3 path is the normalised one, and its constants fit XInput

`GetMaxUseable` / `GetMinUseable` for a non-keyboard, non-mouse device with
control code `0`, `4`, `0x18` or `0x1C`:

| | Value |
| --- | --- |
| `GetMaxUseable` (`0x0074D704`) | `32767.0` |
| `GetMinUseable` (`0x0074D708`) | `8191.75` |

`8191.75` is not a minimum, it is a **deadzone** — exactly one quarter of full
scale. `ScaledValue`'s scaling body computes

```
normalised = (|v| - 8191.75 - 1.0) / (32767.0 - 8191.75)
clamped at 1.0, then multiplied by -1.0 when the input was negative
```

which yields:

| Raw | Normalised |
| --- | --- |
| `0` … `8192` | `0.0` (deadzone) |
| `12000` | `0.155` |
| `16384` | `0.333` |
| `24576` | `0.667` |
| `32767` | `1.000` |

**Full scale is `32767`, which is XInput's thumbstick range.** A KMRP
implementation can pass an XInput axis through essentially unchanged.

Scaling is gated on `desc+0x20`, which is only present on the `0x30`-byte
Detailed object, so the normalised curve requires **type 3**, not type 0. Type 0
is safe precisely because its `0x20`-byte object never reaches that read.

### Conclusion

True analog magnitude survives `PollInput`. Two usable shapes exist:

- **type 0** — raw signed passthrough, deadzone and curve left to KMRP;
- **type 3** — the engine's own normalised `0..1` with a 25% deadzone and sign,
  whose full-scale constant already matches XInput.

### Not established

- That a matched record writes `dwData` into `desc+0x04`. The sweep set that
  field directly. The button proof showed a record reaching the handler, but the
  record-to-`desc+0x04` store was not separately observed.
- Whether the movement events `ProcessInput` polls consume the magnitude or
  threshold it. **This remains the open question for analog walking** and was
  deliberately not touched.
- What `keymap.2da`'s `Scale`, `ScaleMag` and `ScaleExp` do on top of this.

### State

Temporary descriptions for events `0x31` and `0x32` remain in this session's
memory, both inert: device 2 produces no records and `desc+0x04` was zeroed.
Device count restored to `2`, scratch pages freed, breakpoints removed. They
disappear on restart; no file was modified.

## The movement path, and the analog measurement

Traced statically first, then measured in-game. The measurement is in
"MEASURED: movement speed is exactly proportional to stick magnitude" below,
and it confirms the static reading.

### 1. The movement events

Inside `CClientExoAppInternal::ProcessInput` (`0x006227E0`), the gameplay input
class is **0** (`ICPC`). The two movement axes are:

| Event | Class | Poll sites | Role |
| --- | --- | --- | --- |
| `0x119` (281) | 0 | `0x00623925`, `0x00623944`, `0x00623971`, `0x0062399A` | one axis |
| `0x118` (280) | 0 | `0x006239B0`, `0x006239CF`, `0x006239FC`, `0x00623A25` | the other axis |
| `0x109` (265) | 0 | `0x00623A84` | walk/run toggle, drives `SetPlayerWalking` |

Both appear in `swkotor.ini` as `Action280A/B` and `Action281A/B`, so they are the
same events the keyboard binds. Events `0x11A`, `0x11B`, `0x11D`, `0x11E` are the
same shape in input class 1 (`ICMiniGame`) — the swoop minigame.

### 2. ProcessInput clamps to [-1, +1]

Each axis is polled and clamped:

```
v = PollInput(event, 0)
if v < -1.0: v = -1.0        ; 0xBF800000 stored directly
if v >  1.0: v =  1.0
```

**This settles the type question.** A type 0 description returns the raw axis
value, so ±32767 would saturate to ±1.0 at every deflection past 1/32767 — fully
digital. The movement path expects an already-normalised value, so movement must
use **type 3**, whose `ScaledValue` output is `-1.0..1.0` with the engine's own
25% deadzone.

### 3. The consumer

```
00623D05  mov  ecx, [esi+0x2A0]     ; CSWPlayerControlCamRelative*
00623D12  call [vtable+0x00]        ; UpDown(float)
00623F20  call [vtable+0x08]        ; LeftRight(float)
00623F3E  call [vtable+0x28]        ; Control(dt)
          [vtable+0x10]             ; SetPlayerWalking(bool)
          [vtable+0x1C]             ; GetCurSpeed() -> float
```

The clamped floats are passed **unmodified**. The setters store them verbatim:

| Function | Address | Effect |
| --- | --- | --- |
| `UpDown` | `0x00679700` | `this+0x10 = value` |
| `LeftRight` | `0x00679720` | `this+0x14 = value` |
| `SetPlayerWalking` | `0x00679740` | `this+0x18 = flag` |
| `GetCurSpeed` | `0x00679750` | `max(abs(this+0x5C), abs(this+0x60))` |
| `GetMaxSpeed` | `0x00679510` | from creature stats |
| `GetAcceleration` | `0x00679870` | from `CSWCCreature::GetDriveAcceleration` |
| `Control` | `0x00679940` | the integrator |

### 4. What `Control` does with the magnitude

```asm
00679B37  fld  [ebp+0x14]          ; LeftRight
00679B42  fchs                     ; -> vector.x, negated
00679B48  fld  [ebp+0x10]          ; UpDown -> vector.y
00679B4F  fcomp 0.0
00679B5A  jnp  0x679B76            ; LeftRight == 0 -> skip normalise
00679B60  fcomp 0.0
00679B6B  jnp  0x679B76            ; UpDown == 0 -> skip normalise
00679B71  call Vector::Normalize   ; only when BOTH are non-zero
00679B76  mov  eax, [ebp+0x18]     ; walking flag
00679B7D  push 0x3F000000          ; 0.5f
00679B86  call Vector::operator*=  ; walking halves the vector
```

`jnp` after `test ah,0x44` is jump-**if-equal**, because equality sets only C3 and
so gives odd parity and `PF = 0`. So `Vector::Normalize` runs **only when both
axes are non-zero**: it is *diagonal* normalisation, present so that a diagonal
does not travel faster than a cardinal, and not a magnitude discard.

The resulting vector then goes to **`CSWRK4Acceleration::Update`**
(`0x006D1190`), a fourth-order Runge-Kutta integrator, with acceleration from the
creature's drive stats. Velocity lands at `this+0x5C` / `this+0x60`.

### 5. Provisional answers

Marked provisional because they rest on reading, not on watching the character.
This document has already been wrong once today about a branch sense.

- **Does a light push move slower?** On a cardinal axis, the static reading says
  yes: the magnitude reaches the vector unchanged and drives an acceleration
  integrator.
- **Continuously?** Apparently yes, through the RK4 integrator rather than a
  step.
- **Discrete walk/run?** Yes, separately: `SetPlayerWalking` from event `0x109`
  multiplies by `0.5`. That is orthogonal to the analog magnitude.
- **Diagonals?** Normalised to unit length, so a 50% diagonal becomes a 100%
  diagonal. **This is the one real problem for analog input**: the code assumes
  digital ±1 per axis. KMRP would need to scale the pair back by the intended
  magnitude after the engine's normalisation, or accept diagonal snap-to-full.
- **Expected range?** `-1.0 .. 1.0`, enforced by the clamp in `ProcessInput`.
- **Type 0 or type 3?** **Type 3**, definitively. Type 0's raw range saturates
  the clamp.
- **Can XInput feed it directly?** Yes. `GetMaxUseable` is `32767.0`, XInput's
  thumbstick full scale, so an XInput axis passes into a type 3 description
  without rescaling.
- **`keymap.2da` scaling?** Not yet examined, deliberately, so as not to mix two
  scaling layers.

### MEASURED: movement speed is exactly proportional to stick magnitude

Run in-game on 2026-09-07 against a loaded save. `UpDown` (`0x00679700`) was
patched to eleven bytes reading a controlled float, so the RK4 integrator could
reach steady state over many frames rather than being sampled mid-acceleration.
Velocity was then read from `playerControl+0x60`. Each value was stable across
repeated reads.

Player control object: `CClientExoAppInternal+0x2A0`.

| Input | `UpDown` | Velocity | velocity / input | Fraction of full |
| --- | --- | --- | --- | --- |
| 0% | `0.00` | `0.0000` | — | `0.0000` |
| 25% | `0.25` | `2.0250` | `8.1000` | `0.2500` |
| 50% | `0.50` | `4.0500` | `8.1000` | `0.5000` |
| 75% | `0.75` | `6.0750` | `8.1000` | `0.7500` |
| 100% | `1.00` | `8.1000` | `8.1000` | `1.0000` |

`velocity = input * 8.1`, exact at every point. `8.1` is the character's full run
speed.

**No threshold, no quantisation, no walk/run step.** KOTOR PC retained genuine
proportional analog movement. It has simply never had an input device able to
deliver a partial value, because the only bound devices are digital.

The provisional reading above is therefore confirmed, including the branch sense
that this document had first got wrong: `Vector::Normalize` really does run only
on diagonals, and cardinal magnitude reaches the integrator untouched.

### Settled answers

1. **KOTOR PC retained true analog character movement** — measured, not inferred.
2. **Partial stick magnitude gives exactly proportional speed**, linearly.
3. **Movement events**: `0x118` and `0x119` in input class `0` (`ICPC`).
   Walk/run is the separate discrete event `0x109`, applying `* 0.5`.
4. **Expected range**: `-1.0 .. 1.0`, clamped in `ProcessInput`.
5. **Description type**: **type 3**. Type 0 returns the raw axis value, which
   saturates the clamp at any deflection past `1/32767` and is therefore digital.
6. **XInput can feed this directly**: `GetMaxUseable` is `32767.0`, exactly
   XInput's thumbstick full scale.
7. **The pipeline**, end to end:

```
PollInput(0x118 / 0x119, class 0)
  -> clamp to [-1, +1]                       0x00623925 .. 0x00623A25
  -> UpDown(f) -> playerControl+0x10          0x00679700
     LeftRight(f) -> playerControl+0x14       0x00679720
  -> Control(dt)                              0x00679940
       vector = (-LeftRight, UpDown)
       if BOTH axes != 0: Vector::Normalize   (diagonal only)
       if walking flag:   vector *= 0.5
  -> CSWRK4Acceleration::Update               0x006D1190
  -> velocity at +0x5C / +0x60  =  input * 8.1
```

### The design consequence for KMRP

**Diagonal normalisation is the one thing to build around.** `Vector::Normalize`
runs only when both axes are non-zero, which is correct for digital keys where
each axis is `+/-1` and a diagonal would otherwise be `sqrt(2)` times too fast.
With an analog stick it is wrong: a 50% diagonal is scaled back up to 100%.

KMRP should re-apply the intended magnitude after the engine's normalisation, or
accept that diagonals snap to full speed. This needs deciding before the stick
mapping is written, not after playtest.

### Restored

`UpDown`'s original bytes rewritten and verified, scratch page freed, velocity
back to `0.0`, game running normally. No file on disk modified.

### Still to do

- The four `UpdateCamera` poll sites, to see whether camera speed is analog too.
- `keymap.2da`'s `Scale`, `ScaleMag` and `ScaleExp` columns, deliberately left
  alone so as not to conflate two scaling layers.
- Confirm the diagonal behaviour empirically; it is currently read, not measured.

## KOTOR already has joystick descriptions, and they are a delta model

Measured in a running game on 2026-09-07 with a ViGEm virtual pad supplying
controllable axes, reading the live process with `ReadProcessMemory`.

### The device layer works end to end

With a `GetJoystickBuffer` replacement emitting synthesised
`DIDEVICEOBJECTDATA` records from XInput, and `CExoInputInternal+0x158` raised
to 3:

```
reg=1 createFail=0 count=3 init=1 buf=826 rec=2 raw=(-1184,-1058)
```

and the descriptions read back with the raw axis values stored in `desc+0x04`.
XInput -> records -> matching -> description is **confirmed working**.

### The game registers its own joystick descriptions

Scanning every description bound to device 2 found seven that KMRP did not
create:

| Event | Type | Slot | Control | Meaning |
| --- | --- | --- | --- | --- |
| `0x03` | 1 | `0x6E` | `DIJOFS_X` | digital X |
| `0x04` | 1 | `0x6F` | `DIJOFS_Y` | digital Y |
| **`0x07`** | **3** | `0x6F` | `DIJOFS_Y` | **analog Y** |
| **`0x08`** | **3** | `0x6E` | `DIJOFS_X` | **analog X** |
| `0x0B` | 1 | `0x7C` | `DIJOFS_BUTTON(8)` | a button |
| `0x0C` | 3 | `0x71` | `DIJOFS_SLIDER(0)` | slider |
| `0x0D` | 3 | `0x72` | `DIJOFS_SLIDER(1)` | slider |

And `ProcessInput` already polls events `7` and `8` in input class 0, at
`0x006238D3` and `0x006238E5`, feeding the same clamp-and-`UpDown` path as the
keyboard. **KOTOR PC has complete native analog joystick movement wired up.** It
has only ever lacked a device.

This corrects an earlier conclusion in this document. The `keymap.2da` loop
branch read at `0x005EF686` hardcodes the keyboard device, but it is not the only
branch: joystick descriptions plainly exist at runtime.

### Which is why registering our own axis events fails

`AddEvent` returned failure for exactly input classes 0 and 4:

```
add=[0 3 3 3 0 3]        classes 0 and 4 rejected, 1/2/3/5 accepted
```

Those are the two classes whose device-2 lists already hold five descriptions
each. `AddEvent` calls `IsControlUsed(slot, device, class)` and bails when the
control is taken, and `DIJOFS_X` / `DIJOFS_Y` are taken there by events `0x08`
and `0x07`. Custom descriptions therefore land only in the classes that do not
matter, never receive values in gameplay (class 0 is the active one), and
`PollInput` returns `0.0` for them:

```
byclass=[0 0 0 0 0 0]
```

### The real bug: type 3 accumulates

The per-type **store** dispatch at `0x005E2F4C` sends type 3 to `0x005E29E8`:

```asm
005E29E8  mov ecx, [edi+4]        ; record dwData
005E29EB  add dword ptr [ebx+0x24], ecx   ; += , it ACCUMULATES
```

and `PollInput`'s type 3 path computes `[desc+0x24] - [desc+0x04]`. That is a
**relative motion model**, not an absolute one.

Feeding it absolute stick positions makes the accumulator grow without bound.
Measured directly: holding the stick fully forward across three test pushes drove
event `0x07` to **-98301**, exactly `-32767 x 3`.

That is the cause of the reported "moves in all directions at different speeds
even at a slight push". It was never a deadzone or sign problem.

### And a second cause, now removed

The first implementation also wrote the stick into `playerControl+0x10` /
`+0x14` from a hook on `Control`'s entry. Since vanilla was *already* driving
those fields from events 7 and 8, two writers raced for the same two floats every
frame. The hook no longer writes; it is kept only as a gameplay heartbeat for the
handover described below.

### What the implementation should be

Much smaller than what was built:

1. **Emit deltas, not positions**, for `DIJOFS_X` and `DIJOFS_Y`, so vanilla's
   accumulating type 3 descriptions integrate to the right value.
2. **Do not create any descriptions.** Events `0x07` and `0x08` already exist,
   already sit in the gameplay class, and are already polled.
3. **Do not hook `Control`**, except as a signal for standing the older XInput
   keystroke layer down in gameplay.
4. Keep the device count and the `GetJoystickBuffer` replacement. Those two are
   the whole of what was missing.

The delta model still needs its exact convention established -- whether the
engine expects a per-frame difference and resets `+0x24`, or a running total that
`+0x04` tracks as a baseline. That is the next measurement, and it should be made
before any further playtest.

### Also learned

KPM detours copy `original_bytes` into a trampoline, so a stolen **relative**
branch is fatal. A hook at `0x00679B71` stole `call Vector::Normalize` and
crashed the game on entering gameplay. Every one of the module's pre-existing
hooks steals only position-independent bytes.
`tools/check_hook_stolen_bytes.py` now enforces that.

### WORKING: native analog movement, driven by XInput

Reached on 2026-09-07 and confirmed by watching the character move. The
implementation is smaller than the first attempt by a wide margin.

**The delta convention.** `PollInput`'s type 3 path is

```asm
005E245F  sub  eax, ecx           ; value = [desc+0x24] - [desc+0x04]
005E2469  call ScaledValue
005E2471  mov  [esi+4], edx       ; baseline = accumulator; the delta is consumed
```

so each poll returns everything accumulated since the previous poll and then
zeroes that. With one record per frame carrying the **absolute** axis position,
and one poll per frame, each poll returns exactly the position. That is the
convention, and it is why axes must **not** be edge-triggered:

- edge-triggered, a held stick emits nothing, the accumulator stops and the poll
  returns zero;
- and any frame the engine does not poll leaves the delta uncollected, so the
  next read returns a stale sum. Holding forward across three pushes was measured
  at `-98301`, exactly `-32767 x 3`.

Buttons stay edge-triggered; the engine's own button loop is edge-triggered too.
A centred stick emits nothing, which is correct: contributing zero and
contributing nothing are the same, and the poll reads zero.

**What the module ends up doing.** Two things, and nothing else:

1. raise `CExoInputInternal+0x158` so the poll loop visits device 2;
2. replace `GetJoystickBuffer` and emit `DIDEVICEOBJECTDATA` from XInput.

No descriptions are created and no movement hook is needed. The game's own
events `0x08` (`DIJOFS_X`) and `0x07` (`DIJOFS_Y`) receive the records, and its
own `ProcessInput` already polls them.

**Measured.** Screen change over two seconds, as a movement proxy:

| Deflection | Change | Reading |
| --- | --- | --- |
| centre | 0.33% | idle animation baseline |
| 25% | 0.32% | no movement -- this is the engine's own deadzone, `8191.75/32767` = exactly 25% |
| 60% | **4.09%** | moving |
| centred again | 0.25% | stops cleanly, no drift |

The character was observed walking from a corridor through a doorway into
another room, with the minimap heading updating. The accumulator's growth rate
also scales with deflection, roughly `32767 x deflection` per frame.

**Still untested**, and the reason the native build was left staged rather than
installed: diagonals, menu navigation with the stick, keyboard movement
coexistence, the right stick, and buttons through the native path. A reading of
100% deflection showed almost no screen change, most likely because the character
was already against a wall from the preceding test, but that was not confirmed.

**Two implementation traps worth keeping.**

- Hook sites must not steal a relative branch: KPM copies stolen bytes to a
  trampoline. `tools/check_hook_stolen_bytes.py` enforces this.
- A virtual ViGEm pad makes `IsControllerInputActiveK1()` true, which hides the
  cursor, which stops mouse clicks driving menus. Automated menu navigation has
  to happen with the pad server stopped.

### Native buttons and D-pad, through the retained console events

The principle here is the user's: use the actions the engine already has rather
than inventing new ones. Buttons turned out to need no invention at all.

**The event ids are free and are the right ones.** `0x27`..`0x40` -- the retained
Xbox console events -- are registered by nothing in the executable, and
`ProcessInput` already routes any id in that range to
`CSWGuiManager::HandleInputEvent`. The panels still implement them. So binding a
pad button to `0x27` makes it reach the game's own console handler, with no
synthetic keystroke anywhere in the path.

**The control slots are free too.** The `+0x164` table maps slots `0x74`..`0x7E`
to `DIJOFS_BUTTON(0)`..`BUTTON(10)`. Only `0x7C` (button 8) is taken, by the
game's own event `0x0B`, and it is left alone.

| XInput | Slot | Control code | Event | |
| --- | --- | --- | --- | --- |
| A | `0x74` | `DIJOFS_BUTTON(0)` | `0x27` | A |
| B | `0x75` | `BUTTON(1)` | `0x28` | B |
| X | `0x76` | `BUTTON(2)` | `0x29` | X |
| Y | `0x77` | `BUTTON(3)` | `0x2A` | Y |
| LB | `0x78` | `BUTTON(4)` | `0x2B` | Black |

Registered in both the GUI and gameplay input classes. Unlike the axes, buttons
stay **edge-triggered**: the digital store path writes `dwData` to `desc+0x04`
rather than accumulating it, so a held button needs no repeat.

**Verified in game.** All five descriptions read back with the right slots and
control codes, and holding B showed `desc+0x04 = 1`. Then, on the Load Game
screen, a single tap of B closed it and returned to the main menu -- a pad
button driving a retained console handler end to end.

### The D-pad

The engine does not expose a POV hat as one control. Its own `GetJoystickBuffer`
decodes the hat angle into four direction codes -- `0x384`, `0x388`, `0x38C`,
`0x390` -- which the `+0x164` table reaches through slots `0x7F`..`0x82`. Those
are unused, so the pad's four directions bind to the retained navigation events:

| Direction | Slot | Code | Event |
| --- | --- | --- | --- |
| Up | `0x7F` | `0x384` | `0x31` scroll up |
| Down | `0x81` | `0x388` | `0x32` scroll down |
| Left | `0x80` | `0x38C` | `0x2F` D-pad left |
| Right | `0x82` | `0x390` | `0x30` D-pad right |

**Which code is which direction is not established.** The engine derives them
through bit shifts this work has not unpicked, so the pairing above is a first
guess; two of the four may need swapping after a playtest. Registration is
confirmed, the direction mapping is not.

## Rumble: complete, running, and starved of one field

The PC build did not lose the rumble subsystem. `UpdateRumble` (`0x005F7500`)
ticks every frame from the main loop, the envelope evaluator and the mixer are
intact, and `CExoInput::SetRumble` is called with the result whether or not
anything is playing. What is missing is the data.

`CClientExoAppInternal::PlayRumblePattern` (`0x005FB490`) gates on the pattern
count:

```
005FB499  jl  0x5fb536                      index < 0
005FB49F  cmp ebp, dword ptr [ecx+0x344]    the COUNT
005FB4A5  jge 0x5fb536                      -> return 0, nothing queued
005FB4AB  mov edx, dword ptr [ecx+0x340]    the table
```

Sweeping every instruction in the class's address range for a write to `+0x340`
or `+0x344` finds exactly two sites, and neither loads anything:

| Site | What it does |
| --- | --- |
| `0x005FC15C`, `0x005FC168` | the constructor, zeroing count then table |
| `0x005FC82A`, `0x005FC844` | the destructor, `free()` then re-zero |

So the count is zero for the life of the process and every trigger in the game
is dropped at `0x005FB4A5`.

### The object

`[[[0x007A39FC]+4]+4]` — the same `CClientExoAppInternal` whose `+0x9C` carries
the input class. `UpdateRumble`'s call site at `0x004B8383` walks exactly that,
and the script-command forwarder at `0x005EDE40` reaches the same object one
dereference later from its own caller.

| Offset | Field |
| --- | --- |
| `+0x340` | `CSWRumblePattern*`, the table |
| `+0x344` | pattern count |
| `+0x34C` | active instance array, stride `0x0C` |
| `+0x350` | active instance count |

An instance is `{int patternIndex, float elapsed, int justStarted}`.

### The pattern

Read out of `CSWRumblePattern::GetMagnitudes` (`0x0068FDD0`) and the envelope
evaluator it calls twice (`0x0068FCB0`).

```
envelope, 0x10 bytes
  +0x00  float* magnitudes
  +0x04  float* times, seconds; the end test reads times[count-1]
  +0x08  int    count
  +0x0C  int    cursor -- the evaluator CACHES its last segment here

pattern, 0x24 bytes
  +0x00  envelope A -> the first magnitude out
  +0x10  envelope B -> the second
  +0x20  int loop
```

The evaluator interpolates linearly between the two keyframes bracketing the
elapsed time (`0x0068FD96`-`0x0068FDB7`). `GetMagnitudes` returns 0 -- which
makes `UpdateRumble` drop the instance -- once the time is past the last
keyframe of **both** envelopes and `loop` is clear. With `loop` set, the
evaluator instead subtracts the total duration until the time falls back in
range (`0x0068FCF0`), and the pattern never ends on its own.

The cursor at `+0x0C` is written by the engine, so a table cannot live in
read-only memory.

### Where the magnitudes go

`UpdateRumble` keeps two accumulators and takes the maximum of each envelope
across every active instance, then:

```
005F760F  mov eax, dword ptr [esp+4]     envelope B's maximum
005F7613  mov ecx, dword ptr [esp+8]     envelope A's maximum
005F7617  push 0x927C0                   <- KMRP's detour
005F7626  call 0x5df550                  CExoInput::SetRumble
```

So a detour at `0x005F7617` sees both magnitudes in registers, as float bit
patterns, and `EBP` still holding `UpdateRumble`'s `this`.

### What the shipped content asks for

| Source | Swept | Patterns |
| --- | --- | --- |
| a `rumblepattern` 2DA column | all 209 2DAs in `chitin.key` | `footstepsounds` 17; `visualeffects` 11, 14, 16, 20 |
| NCS `ACTION` calls to routine 370 | all 401 shipped containers | 5, 11, 12, 13, 14, 15, 16 |

Union: **5, 11, 12, 13, 14, 15, 16, 17, 20**. Routine 371,
`StopRumblePattern`, is called by **nothing** in the shipped content.

Both 2DAs pair the column with `rumblecutoff`, the radius inside which the
rumble is felt: 2 for Force Choke and Force Push, 5 for the grenades and Force
Wave, 20 for a Stomp footfall, 30 for `VFX_IMP_SCREEN_SHAKE`.

The envelope data itself is not in the PC files at all, in any 2DA, BIF or RIM.
It went with the Xbox build.

**Found since, 2026-09-25:** the OpenKotOR wiki publishes K1's `rumble.2da`
([rumble-k1.md](https://github.com/OpenKotOR/wiki/blob/main/wiki/odyssey-engine/2da/rumble-k1.md)), 22 rows (0-21). Each row has a `looping` flag and up to
seven magnitude/time keyframes per motor (`lsamples`, `lmagnitudeN`, `ltimeN`,
and the same for `r`). Its row names match what the sweeps found each index
doing, which is what identifies it as this engine's table. The module now
installs it verbatim (`K1_RUMBLE_2DA`, generated from that page), in place of
the nine shapes KMRP had authored. The table was first placed in
`K1NativeJoystick.cpp`. Since the haptics pass of 2026-09-25 it has lived in
`K1Rumble.cpp`, where a mixer plays it; see
[`docs/controller-rumble.md`](../docs/controller-rumble.md).

| Row | Label | Loop | Heavy (l) samples | Light (r) samples | Fired by shipped content |
| --- | --- | --- | --- | --- | --- |
| 0 | LightSaberOn | yes | 0 | 2 | no |
| 1 | FullBoth-5secs | no | 2 | 2 | no |
| 2 | FullLeft-5secs | no | 2 | 0 | no |
| 3 | FullRight-5secs | no | 0 | 2 | no |
| 4 | WeakBoth-5secs | no | 2 | 2 | no |
| 5 | Sample1 | no | 3 | 3 | `k_pend_1b_area2` |
| 6 | Sample2 | no | 3 | 2 | no |
| 7 | Sample3 | no | 0 | 2 | no |
| 8 | Sample4 | no | 3 | 3 | no |
| 9 | Sample5 | no | 4 | 4 | no |
| 10 | Sample6 | no | 4 | 4 | no |
| 11 | Rancor | no | 5 | 5 | terentatek arrivals, `VFX_FNF_TERANTANAK_DEATH` |
| 12 | Ceiling | no | 7 | 7 | `k_pkor_ceil_fall` |
| 13 | Obilesk | no | 2 | 2 | `k_pkor_ther_dest` |
| 14 | FragGenade | no | 2 | 2 | seven grenade VFX, 18 script sites |
| 15 | Endar_01 | no | 6 | 6 | `k_pend_rumble01` |
| 16 | Endar_02 | no | 2 | 4 | `k_pend_area02`, `VFX_IMP_SCREEN_SHAKE` |
| 17 | Heavy_step | no | 2 | 2 | `footstepsounds` Stomp rows |
| 18 | Light_step | no | 2 | 2 | no |
| 19 | Krayt_dying | no | 4 | 3 | no |
| 20 | Critical_hit | no | 2 | 0 | Force Choke, Force Push, Force Wave |
| 21 | Whirlwind | yes | 7 | 7 | no |

The `l` columns are envelope A and the `r` columns envelope B, because
`UpdateRumble` calls `SetRumble(0, A, B, 600000)` at `0x005F7626`, and XInput's
order is (left, right), with left the heavy motor. How the evaluator reads
BioWare's less regular rows was checked against its code before relying on it:
- A motor with no samples is null pointers and count 0. The evaluator returns
  0.0 for a null pointer (`0x0068FCB9`, `0x0068FCC3`), and `GetMagnitudes`' end
  test reads `times[count-1]` only when that index exists (`0x0068FE0B`),
  otherwise 0.0 from `0x0073D700`.
- A motor whose first keyframe is late, such as Endar_01's left motor at 5.5 s,
  finds no segment before it and returns 0.0 from `0x0068FDBF`: silence, as
  authored.
- A looping row wraps its elapsed time by the last keyframe's time. The only
  looping rows, 0 and 21, are fired by nothing shipped, so they run only if a
  mod plays them, until `StopRumblePattern`. *Since 2026-09-25:* the
  **Enhanced** rumble mode attaches them to the events their names describe:
  0 to a lit lightsaber in the controlled character's hand, and 21 to
  `VFX_DUR_FORCE_WHIRLWIND` on the controlled character. Those attachments are
  KMRP's, not the Xbox game's; what fired them there is not known. **Original**
  mode still plays only what shipped content fires.

All 78 magnitude and time arrays were found byte for byte in the compiled
module. **Not felt on a pad yet.**

### Every rumble entry point, and why the coverage is complete

There are four, and all of them funnel into `PlayRumblePattern`:

| Entry | Call sites | Where the index comes from |
| --- | --- | --- |
| NWScript routine 370 | `0x0054114C`, `0x004FF94D` | literal ints in compiled scripts |
| `LookUpAndPerformRumbleWithCutOff`, category 0 | `0x0061A62D` | `footstepsounds.2da` |
| `LookUpAndPerformRumbleWithCutOff`, category 1 | `0x00690956`, `0x006A653E` | `visualeffects.2da` |

The category is the second argument, a byte, read at `0x005FB98E`: 0 selects the
2DA at `+0x58` in the registry, 1 the one at `+0x88`, and anything else bails.
There is no third category and no fourth caller.

So the nine indices the sweeps found -- 5, 11, 12, 13, 14, 15, 16, 17, 20 -- are
the complete set the shipped game can ask for, and a table covering them leaves
nothing of the original behind.

### Where the shipped data is itself incomplete

Nine grenades have a `spells.2da` row; only seven have a `rumblepattern`:

| Grenade | VFX row | Rumble |
| --- | --- | --- |
| Fragmentation, Stun, Thermal Detonator, Sonic, Cryoban, Plasma, Ion | 3003, 3004, 3005, 3007, 3009, 3010, 3011 | 14 |
| **Poison** | 3006 | none |
| **Adhesive** | 3008 | none |

That is BioWare's data, not an omission in the restoration. The same is true of
the flash grenade: `g_w_flashgren001` exists as an item resource but has no
`spells.2da` row and no `visualeffects` row, so it is not throwable in the
shipped game at all. There is no flare item in K1 -- no `FLARE` row in either
2DA.

Nothing else rumbled on Xbox either. Taking damage, weapon impacts, lightsaber
clashes, swoop racing and doors are all silent in the original, so adding them
would be an addition rather than a restoration. The thirteen indices nothing
shipped references -- 0-4, 6-10, 18 and 19 -- were called "free" here until
2026-09-25. They are not: they are BioWare's own rows (the table above), now
installed as authored, so a mod that plays them gets the original pattern.

### Some screens navigate themselves, and not through any control

Powers, Feats, Skills, Abilities and the Map do not hold their selection in a
focused control. It is a cursor object owned by the **panel**, which is why a
direction event delivered to a control moves nothing on them, and why a focus
layer that walks the panel's control array sees nothing to walk.

`CSWGuiInGamePowers::HandleInputEvent` serves all eight direction events --
`0x2F`, `0x30`, `0x31`, `0x32`, `0x3D`, `0x3E`, `0x3F`, `0x40` -- from a single
arm:

```
006F297B  push edi                    the event id
006F297C  lea  ecx, [esi+0x19FC]      the grid cursor
006F2982  call 0x006CDD80             walk it; returns the new packed index
006F2988  call 0x006F1460             select that index
006F1476  mov  [esi+0x19C4], ebx      the selection, stored on the PANEL
```

The cursor at `panel+0x19FC` is bytes, not controls: `+0x0C` column, `+0x0D`
row, `+0x04` the count. It **wraps** -- `0x006CDDB8` sets the row to 0 on
passing the last one -- so there is no top or bottom edge to detect, and no
press at which "leave this screen" is the natural reading.

| Screen | Dispatcher | Direction site |
| --- | --- | --- |
| `ABILITIES` | `0x006AE5F0` | `0x006AE818` (`0x2F/0x30/0x3F/0x40`), `0x006AE839` (`0x31/0x32/0x3D/0x3E`) |
| `POWERS` | `0x006F28C0` | `0x006F297B`, all eight |
| `SKILLS` | `0x006F6A10` | `0x006F6A5F` (`0x2F/0x3F`), `0x006F6A7F` (`0x30/0x40`) |
| `FEATS` | `0x006F4680` | as `SKILLS` |
| `MAP` | `0x00693BC0` | -- |

These screens also route their **own** description scrolling: `0x006F299E`
takes `0x3A` and sends `0x32` to the listbox at `panel+0xFCC`. So the screen is
the owner of every direction on it, including the ones that end up in a list,
and anything that intercepts a direction on behalf of a focused control gets in
its way.

The module dispatches to the panel directly for these, because behind the
in-game tab strip a retained event cannot be delivered to them at all -- the
strip is the panel in front, and its dispatcher routes to its own focused
control.

### The right stick is not reachable this way

`UpdateCamera` polls event `0x11C` in the gameplay class, and `ProcessInput`
clamps it to `[-1, 1]` exactly as it does the movement axes. But `0x11C` already
has a keyboard description, and `descriptions[]` holds one per event id, so a
joystick description cannot be added for it. Its keyboard description is almost
certainly the single type 4 two-button axis the game registers -- a pair of keys
forming one axis -- which is why keyboard camera turning works at all.

There is a second route that was investigated and **not** taken. `ProcessInput`
has a branch, gated on `ClientOptions+0x6D == 7`, that polls events `0x0C` and
`0x0D` -- the game's own joystick slider descriptions on `DIJOFS_SLIDER(0)` and
`SLIDER(1)`. Feeding those from the right stick would be fully native. But
`+0x6D` is the **camera mode**, written by `CClientOptions::SetCameraMode` and
driven from script through `ExecuteCommandSetCameraMode`; forcing it to 7
globally would change camera behaviour well beyond input. That is a decision for
a playtest, not an assumption.

So the right stick remains on the older keystroke path for now.

### The device model, and why the camera is only half reachable

**Six devices, four of them joysticks.** The constants sit together at
`0x0074D3C4`:

| Address | Value | Meaning |
| --- | --- | --- |
| `0x0074D3C4` | `-1` | any / none |
| `0x0074D3C8` | `0` | keyboard |
| `0x0074D3CC` | `1` | mouse |
| `0x0074D3D0` | `2` | first joystick |
| `0x0074D3D8` | `6` | maximum devices |
| `0x0074D3DC` | `110` (`0x6E`) | first joystick control slot |

So devices 2 through 5 are joysticks, matching the constructor's clamp of the
count to 6. There is **no third device kind** -- no separate gamepad class hiding
behind the keyboard and mouse -- but the engine does natively support **four**
pads, not one. Anything built here should index the device rather than assume 2.

### The camera has two inputs, and only one of them is analog

`CClientExoAppInternal::UpdateCamera` (`0x005F5E10`) reads exactly two things:

```asm
005F5E89  call CClientOptions::GetMouseSenSetting
005F5EB2  call CExoInput::GetMouseDelta        ; analog
005F5ED8  fmul [esp+0x24]                      ; * sensitivity
005F5EDC  fmulp                                ; * invert flag at 0x007A22A4
005F5EE1  call CSWCModule::TiltCamera          ; camera PITCH
...
005F5EF3  call PollInput(0x11C, 0)             ; camera YAW, clamped to [-1,1]
```

**Yaw is not reachable.** Event `0x11C` is description **type 4**, a two-button
axis on **device 0**, with slots `0x36` and `0x33` resolving to `0x20` and `0x1E`
-- `DIK_D` and `DIK_A`. Descriptions are one per event id, so no joystick
description can be added for it, and its value can only ever be the difference of
two digital controls. The same shape explains movement: `0x118` is `DIK_S`/`DIK_W`
and `0x119` is `DIK_C`/`DIK_Z`, which is why the joystick needed the engine's
separate analog events `0x07` and `0x08` instead.

**Pitch is reachable, and is genuinely analog.** `GetMouseDelta` has exactly one
caller, `UpdateCamera`, and it is a plain field read:

```asm
005E00F0  mov eax, [ecx+0x3A0]     ; delta X
005E00FC  mov eax, [ecx+0x3A4]     ; delta Y
```

`UpdateMouseDelta` computes and writes those two fields; `GetMouseDelta` only
reads them back. `ProcessInput` calls `UpdateMouseDelta` at `0x006228A3` and then
`GetEvents` at `0x006228D2`, while `UpdateCamera` runs later in the frame. So a
hook on `GetEvents` -- which this module already has -- sits in exactly the
window between the delta being computed and the camera consuming it, and can add
a stick-derived value to `CExoInputInternal+0x3A4` without touching the cursor,
without hooking `GetMouseDelta`, and without a second writer racing anything.

**It is the X delta, not the Y.** Working the call site's stack through: `push
ecx` shifts `esp` before the second `lea`, so `arg1` is `S+0x1C` and receives
`+0x3A0`, and the `fld [esp+0x1c]` after the call reads that same slot. So
`TiltCamera` is driven by horizontal mouse movement -- camera rotation, which is
exactly what a right stick should drive.

Implemented: the right stick is added to `+0x3A0` from the existing `GetEvents`
hook, with its own radial deadzone. The speed constant is unmeasured against a
real mouse and is the first thing to tune.

### Camera mode 7 is a vehicle mode, not a gamepad mode

Worth recording because it looked promising and is not. `ProcessInput` gates a
block on `ClientOptions+0x6D == 7` that polls the game's own joystick sliders,
events `0x0C` and `0x0D`. Following where those values go:

```asm
00623DE5  call [eax+0x80]            ; fetch an object from the module
00623DF8  cmp  eax, 0x1071           ; only for object type 0x1071
00623E19  fld  [esp+0x18]            ; event 0x0C  -> [edi+0x18]
00623E26  fld  [esp+0x1c]            ; event 0x0D  -> [edi+0x14]
00623E33  fld  [esp+0x1c]            ; and a cross term -> [edi+0x28]
```

Five float inputs written onto a single object of type `0x1071`, alongside the
movement axes. That is a vehicle control block -- the swoop or the turret -- not
a camera. `+0x6D` is written by `CClientOptions::SetCameraMode` and driven from
script through `ExecuteCommandSetCameraMode`, so forcing it would change camera
behaviour far beyond input. Route rejected.

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
regenerated by `map_retained_gui_events.py --full`: **40 panels, 224 implemented
events**.

That count rose from 212 on 2026-09-07 without any new panel being found. The
chain decoder matched immediates only in hex, and capstone prints small ones in
decimal -- `sub eax, 5`, not `sub eax, 0x5`. **This is the second time that exact
assumption has cost this document a handler**: the Container panel was missed for
the same reason, and the fix then was applied only to the jump-table decoder.
Twelve events across eight panels were being reported as unimplemented, including
the Main Menu's `0x2D`.

One caveat on the new rows: `FLOATY_TEXT`'s `0x00` and `0x01` are the flag branch
described above, not event codes. The decoder cannot tell the two shapes apart
and the panel is still not an event switch.

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
