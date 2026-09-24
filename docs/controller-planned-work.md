# Controller support: planned work

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Every constraint
> below was read out of the source or the address database and says which;
> anything not yet checked is labelled unverified.

**Kind: plan.** It is neither a lab record nor a reference — it is the agreed
design for work not yet written, kept here so the next session starts from the
constraints rather than rediscovering them. The finished mechanisms belong in
[`controller-support.md`](controller-support.md) once they ship; delete each
section here when that happens.

Written 2026-09-06 against `kmrp-controller.module` SHA-256
`D006428E382A76D4CFA0DD620C2BB873B38371A0C0954DE331C1032F66069E25`, 130,560
bytes, built from `build/research/KPM-Xbox-Controls-K1/` at that date. The
files now live in `src/controller-native/vendor/`, where the same code has moved
(on 2026-09-25, `XI_LEFT_TRIGGER` is at line 68 and `ReadPad` at 281).

**Status on 2026-09-24:** §1 (Guide) and §2 (virtual-pad slot safety) are still
unbuilt -- neither `XInputGetStateEx` nor any Guide binding is in the source, and
`virtual_pad_server.py` has no refusal or idle timeout. §3 shipped and §3b and
§3c are done. Of §4, R3 shipped and LB/RB did not.

---

## 1. Xbox Guide button opens the Inventory

**Wanted:** pressing the Guide button (the round Xbox logo) sends the game's
inventory key, so the pad has a one-press route to Inventory the way a console
build does.

**The blocker, and it is a real one.** The public `XInputGetState` **masks the
Guide button out**. It is reported only by the undocumented `XInputGetStateEx`,
exported by ordinal 100 rather than by name, as button bit `0x0400`. The module
currently resolves its entry point by name:

```cpp
// K1XboxControlsXInput.cpp, the XInput loader
g_getState = reinterpret_cast<XInputGetStateFn>(
    GetProcAddress(module, "XInputGetState"));
```

so as written it can never see the Guide button, no matter what binding is added.

**A bit collision that must be fixed first.** The module manufactures synthetic
button bits for the analogue triggers, and one of them is already `0x0400` —
the same value real XInput uses for Guide:

```cpp
// K1XboxControlsXInput.cpp, the trigger bit constants
constexpr std::uint16_t XI_LEFT_TRIGGER  = 0x0400;   // collides with GUIDE
constexpr std::uint16_t XI_RIGHT_TRIGGER = 0x0800;
```

`buttons` is a `std::uint16_t` and the real XInput bits occupy everything except
`0x0400` and `0x0800`, which is presumably why those two were chosen. Reading the
Guide bit therefore requires moving the synthetic bits somewhere else.

**Plan:**

| step | change |
| --- | --- |
| 1 | Widen the button word from `std::uint16_t` to `std::uint32_t` through `PollXInputK1`, `ApplyDpad`, `ButtonBinding.mask` and `ConsumeMovieSkipK1`. |
| 2 | Move the synthetic triggers to `0x00010000` / `0x00020000`, freeing `0x0400` for its real meaning. |
| 3 | Resolve `XInputGetStateEx` by ordinal — `GetProcAddress(module, MAKEINTRESOURCEA(100))` — and fall back to the named `XInputGetState` when it is absent. Guide is simply unavailable in that case; nothing else regresses. |
| 4 | Add `{XI_GUIDE, SC_I, 0}` to `BUTTON_BINDINGS`. |

**Unverified, check before building:** that KOTOR's inventory key is `I`. That is
the user's report from play, not something read out of the game's keymap, and the
whole binding is wrong if it is another key. Read it from the key-mapping data or
confirm in game first.

**Also unverified:** whether Guide reaches the process at all on this machine.
Steam and the Xbox Game Bar both capture it in some configurations. If an overlay
takes it, `XInputGetStateEx` still reports it — but confirm by observation rather
than assuming, and record the result here.

**Rejected:** binding Guide through the ordinary named API by "detecting" it from
some other signal. There is no such signal; the bit is masked at the API boundary.

---

## 2. The virtual pad must not take a slot from a real controller

**Why this is not a nicety.** On 2026-09-06 the user's physical controller stopped
working in game entirely. Nothing was wrong with the module. The test rig's
virtual pad from `testing/controller/virtual_pad_server.py` was still running and
held XInput slot 0; the physical controller was on slot 1. `ReadPad` takes the
first slot that answers and **stays on it** until that slot goes quiet:

```cpp
// K1XboxControlsXInput.cpp, ReadPad  (abridged)
bool ReadPad(XInputState* out)
{
    if (g_padSlot >= 0) {                       // sticky
        if (g_getState(g_padSlot, out) == XI_SUCCESS) { ... return true; }
        g_padSlot = -1;
    }
    for (std::uint32_t slot = 0; slot < 4; ++slot) { ... }   // first wins
}
```

so the module read an idle virtual pad and never looked at the real one. The same
trap fired in the opposite direction earlier the same day: the user's controller
held slot 0 and the virtual pad on slot 1 was invisible to the module, which is
why driving the game from a script appeared to do nothing.

**Plan for `virtual_pad_server.py`:**

1. **Refuse to start when a physical pad is connected**, unless `--force` is
   passed. Print which slot it is on and say plainly that starting anyway will
   take a lower slot and disable it.
2. **Idle timeout.** Exit after ten minutes with no command received, so a
   forgotten server cannot sit on slot 0 indefinitely.
3. Print the occupied slots on startup and on exit.

**How to tell the two apart**, measured this session and reliable:
`XInputGetBatteryInformation` reports `BATTERY_TYPE_NIMH` (3) or `ALKALINE` (2)
for a physical wireless pad, and `WIRED` (1) or `DISCONNECTED` (0) for a ViGEm
virtual pad. A wired physical pad would also report `WIRED`, so this test is
sufficient for the wireless case that actually occurs here and **is not a general
discriminator** — say so in the warning rather than claiming certainty.

---

## 3. Dynamic hint icons for controls that do not exist in the game's classes  — SHIPPED 2026-09-15

The R3 party-switch cue between the portraits on Abilities, Character, Equipment
and Inventory, shown only while a controller is in use. Removed from this plan,
as its own rule asks; the finished mechanism is in
[`../reverse-engineering/custom-gui-controls.md`](../reverse-engineering/custom-gui-controls.md).

It did not use the lookup this section planned. Rather than walking the panel's
control array at run time and matching tags -- the plan written against the
2026-09-06 index-lookup crash -- the control is added to the `.gui` at build
time and bound by tag through the engine's own binder while the panel still has
its `.gui` loaded, at `CSWGuiPanel::ReleaseGff`. The same mechanism later carried
the LT/RT and swap-tabs cues and the confirmation-box A.

---

## 3b. Focus must survive activating a tab  — IMPLEMENTED 2026-09-06

**Reported from play, 2026-09-06:** reaching a tab with the D-pad works, but
pressing A to select it leaves the screen with no focused control at all, so the
next D-pad press has nothing to move from.

**Why.** A is not intercepted; it is injected as `Return` and the game activates
whatever control has focus. The tab's own handler then repopulates the screen,
and the panel's active-control pointer -- `panel + 0x1C`, GameConfig's
`panelActiveControlOffset` -- is left null. The module never learns the press
happened, so nothing restores focus.

**Fix: a per-frame focus keeper, scoped to panels that declare a header.**
`UpdateK1ControllerPrompts` already runs every frame from `DispatchMenuInputK1`,
which is the natural place for a sibling check:

1. Read the active control each frame. When it is non-null, remember it together
   with its panel.
2. When it is **null**, the panel is the one remembered, and controller mode is
   active, re-assert the remembered control with
   `K1_CONFIG.setActiveControl(panel, remembered, 1)`.

**Why "null" is the right trigger and not something cleverer.** Focus moving
somewhere else is legitimate and must not be fought -- pressing Down into the
list is a normal thing to do. A *null* active control is never useful state; it
is precisely the "focus went away" the report describes. Restoring only from null
leaves every deliberate movement alone.

**Scope it to panels with a header** (today Abilities and Key Mapping) so that no
other screen changes behaviour, and so a screen that genuinely wants null focus --
a modal opening over the top, for instance -- is unaffected.

**Check before shipping:** that a modal appearing over the Abilities screen does
not cause the keeper to fight it for focus. If it does, also require that the
remembered panel is still the one `FindK1MenuPanelForInput` returns.

**Verified by this report:** the Abilities strip entry works. Up from the ability
list reaches the tab row and A activates the tab -- the section above marking that
untested is now superseded for the navigation half.

## 3c. Do menu focus in the engine, not in the input translator  — DONE 2026-09-06

**Agreed 2026-09-06.** Sections 3b and its two revisions are workarounds for a
design mismatch, and should be replaced rather than refined.

**The mismatch.** The module is an XInput-to-keyboard translator: it presses keys
and never learns what happened next. Menu focus is the one feature that needs to
*observe and control engine state* rather than synthesise input, and every bug in
this area traces to that:

| symptom | cause |
| --- | --- |
| Focus jumps to the list when a tab is activated | A is injected as `Return`; the module never learns the activation happened |
| Fast tab-switching leaves focus in the list | the activation had to be inferred from a 250 ms injected-key window, and a direction pressed inside that window suppressed the restore |
| The focus box flickers for one frame | the hook runs at `ProcessInput` **entry**, so the game moves focus and the frame is drawn before the module can correct it. Correcting after the fact can never remove that frame |
| Every new binding collides | in keyboard space every key already means something; `Tab`, `Q`/`E`, `Space` are all taken |

**The fix: hook `CSWGuiPanel::SetActiveControl`.**

| | |
| --- | --- |
| Address | `0x0040A630` (VA; `FILE = VA - 0x400000` = `0x00A630`) |
| Convention | `__thiscall`, `ecx` = `CSWGuiPanel*` |
| Source | `kotor1_0_3.db` `functions`, class `CSWGuiPanel` |
| Corroboration | the same address already sits in `K1_CONFIG` as `setActiveControl`, which the module calls today |

Every focus change in the GUI passes through this one function. Hooking it turns
the problem inside out: instead of noticing afterwards that focus moved and
putting it back, the module **sees the move as it is requested and can decline
it**. No timing window, no inference, and no wrong frame drawn -- which is the
only way the flicker goes away.

**This does not cost the zero-bytes property, and an earlier note in this
conversation wrongly implied it would.** KPM detours are applied in memory at
run time; the seven existing hooks write nothing to `swkotor.exe` on disk. An
eighth entry in `kotor1.hooks.toml` behaves the same way. "Do it in the engine"
and "modify the executable on disk" are separate decisions, and only the first is
being taken.

**Also found, and relevant beyond focus:** the engine still carries its Xbox
button handlers as real virtual methods on `CSWGuiPanel`, which is why the
retained GUI events work at all --

    OnAButtonPressed      0x0040B640
    OnBButtonPressed      0x0040B650
    OnXButtonPressed      0x0040B660
    OnYButtonPressed      0x0040B670
    OnBlackButtonPressed  0x0040B680
    CSWGuiInGameMenu::SetActiveControlID   0x00624BD0

Section 4's bumper and stick-click work should be reconsidered against these
before it is written: dispatching a real button event to a panel is likely to be
better than borrowing another keyboard key, and it removes the `Tab`-versus-party
collision entirely rather than resolving it.

**Steps:**

1. Add the detour to `kotor1.hooks.toml` with the stock byte sequence at
   `0x0040A630`, read back from the built executable the way the other seven are.
2. Export a handler that receives panel, control and flag; record every focus
   change so the module always knows where focus is, with no inference.
3. Decline a move off a tab that the same frame's activation caused. Keep the
   rule narrow: a move the player asked for must always be honoured.
4. Delete `KeepK1MenuFocus` and its globals once the hook covers the case.

**Do not skip:** the hook site's stock bytes must be verified against the built
executable before shipping, and the whole thing scoped so a panel with no tab row
behaves exactly as it does today.

**Implemented and confirmed in play 2026-09-06.** The hook went in at
`0x0040A638` and `KeepK1MenuFocus` was deleted.

What the three earlier attempts all missed, and only a debugger found: the
Abilities tab handler moves focus TWICE, and the first move is a clear.

    006AD91A  push ebx              ; control = NULL
    006AD91D  call [eax+8]          ; SetActiveControl(panel, NULL)
    006AD923  lea eax, [esi+0x30DC] ; the ability listbox
    006AD92C  call [edx+8]          ; SetActiveControl(panel, listbox)

Every attempt asked "is the panel's current active control a tab?". That is true
on the first call and false on the second, because the first nulled it -- and the
first was skipped anyway by an `if (!control) return 0;` guard. Both moves
escaped every time, which is why the symptom looked intermittent rather than
absent. The guard now remembers the tab when focus ARRIVES on it and reads
nothing back from the panel, so the handler clearing its own field cannot disarm
it, and it declines both calls.

Found by a conditional breakpoint that halted only on the failing case
(`edi == panel && esi == listbox` at the store instruction `0x0040A64E`); the
return address on the stack pointed straight at `0x006AD92F`. Three rounds were
spent guessing at the veto condition when the control flow was five instructions
away in a disassembler.

## 4. Tab switching and the agreed menu button layout

**Implemented, and verified in play on 2026-09-06** (see the table at the end):
the Abilities panel has an entry in `GetK1SettingsStripExit`, so Up from the top
of the ability list reaches the tab row and Left/Right moves along it. Offsets are from `kotor1_0_3.db`, class
`CSWGuiInGameAbilities`; the table corroborates itself because its
`description_listbox` is `0x33BC`, the value already shipping as
`K1_ABILITIES_DESC_OFFSET`.

| member | offset | on screen at 3440x1440 |
| --- | --- | --- |
| `skills_button` | `0x2F18` | tab, `LEFT=607 TOP=264` |
| `powers_button` | `0x2D54` | tab, `LEFT=1360 TOP=264` |
| `feats_button` | `0x2B90` | tab, `LEFT=2091 TOP=264` |
| `ability_listbox` | `0x30DC` | the column |
| `exit_button` | `0x369C` | Close, `LEFT=2112 TOP=1230` |

**The agreed layout**, which nests by scope so that learning one binding predicts
the next:

| input | scope | status |
| --- | --- | --- |
| **LT / RT** | move between screens — Map, Inventory, Character… | works; on the native path, events `0x35` / `0x36` |
| **LB / RB** | move between tabs within a screen | **not built.** On the native path LB and RB carry no menu event; X cycles the Abilities screen's Skills / Powers / Feats tabs instead (event `0x29`), with a cue beside them |
| **L3 / R3** | change which crew member the screen is about | **R3 shipped 2026-09-15**: event `0xCE` on the four party screens, with a cue between the portraits. L3 was not given a menu role |

**Correction, kept visible per rule 11.** An earlier version of this plan proposed
LT / RT for cycling tabs, on the grounds that they were "inert in menus". That was
wrong. It was inferred from `BUTTON_BINDINGS` alone — `{XI_LEFT_TRIGGER, SC_Q}`,
`{XI_RIGHT_TRIGGER, SC_E}` — without checking what `Q` and `E` do once a menu is
open, which is to cycle between the menu screens. The user corrected it from play.
The lesson is that a binding table says what key is sent, not what the game does
with it.

**Conflicts to resolve when implementing:**

- **RB is `Tab`**, which cycles the displayed party member. Moving tabs onto RB
  takes that away, which is why party cycling moves to L3 / R3. The on-screen
  route survives regardless: `character_left_button` (`0x3BE8`),
  `character_right_button` (`0x3DAC`) and the two portraits are reachable by
  D-pad now that the panel has a strip entry.
- **LB sends two scancodes**, `SC_SPACE` and `SC_INSERT`; the second is captured
  and dispatched to the panel as the Black-button GUI event. If LB becomes
  "previous tab" on tabbed panels it must stop doing both.
- Scope the interception to panels that declare a `header` — today Abilities and
  Key Mapping — so no other screen changes behaviour.

**Artwork -- done.** This said the vendored set had ten glyphs and no L3 / R3.
The whole pack's four supported families are vendored now, at
`third_party/Included/Xelu_Free_Controller&Key_Prompts/`, with sixteen actions
each, L3 and R3 included, and `THIRD_PARTY_NOTICES.md` lists what is used.

---

## What is verified, and what is not

*Pointers changed 2026-09-25:* the code excerpts on this page named line numbers
(`:257`, `:67-68`, `:271-296`). Those were right for the 2026-09-06 research tree,
but in the vendor copy they are off by one to eleven lines. They now name the
code they quote.

| claim | how |
| --- | --- |
| Guide is masked by `XInputGetState`, exposed by `XInputGetStateEx` ordinal 100 as `0x0400` | Microsoft's documented XInput behaviour; **not** measured on this machine |
| `XI_LEFT_TRIGGER` already uses `0x0400` | read from the constant in `K1XboxControlsXInput.cpp` |
| `ReadPad` sticks to the first answering slot | read from `ReadPad` in `K1XboxControlsXInput.cpp` |
| A virtual pad on a lower slot disables a real one | observed twice in both directions on 2026-09-06 |
| Physical pads report NIMH/ALKALINE, ViGEm reports WIRED | measured on both this session |
| Abilities member offsets | `kotor1_0_3.db`, corroborated by `description_listbox` matching the shipping constant |
| The fill field is an inline 16-byte ResRef at border-params `+0x40` | read from a live badge in memory |
| Abilities tab navigation reaches the tabs | **verified in play 2026-09-06.** Up from the list reaches the tab row and A activates a tab |
| Focus survives activating a tab | **confirmed in play 2026-09-06**, by the `SetActiveControl` hook of §3c that replaced the keeper (this row said "play-test still owed") |
| The inventory key is `I` | user's report from play; not read from the keymap |
