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
bytes, built from `build/research/KPM-Xbox-Controls-K1/` at that date. Line
numbers below refer to that tree.

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
// K1XboxControlsXInput.cpp:257
g_getState = reinterpret_cast<XInputGetStateFn>(
    GetProcAddress(module, "XInputGetState"));
```

so as written it can never see the Guide button, no matter what binding is added.

**A bit collision that must be fixed first.** The module manufactures synthetic
button bits for the analogue triggers, and one of them is already `0x0400` —
the same value real XInput uses for Guide:

```cpp
// K1XboxControlsXInput.cpp:67-68
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
// K1XboxControlsXInput.cpp:271-296  (abridged)
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

## 3. Dynamic hint icons for controls that do not exist in the game's classes

**Wanted:** small L3 / R3 glyphs beside the crew portraits at the bottom left of
the Abilities screen, so the party-cycling binding is discoverable, appearing only
while a controller is in use like every other badge.

**Why the existing mechanism cannot do it.** A badge is installed by writing a
fill into a control the module addresses by a **fixed class-member offset** —
`exit_button` is `0x369C` in `CSWGuiInGameAbilities`. The two portraits cannot be
used because their `BORDER.FILL` already holds the crew member's face
(`po_pzaalbar`, `po_phk47` at 3440x1440) and the badge would erase it. There is
no spare empty-fill control near them: the screen has seventeen controls and the
nearest is the ability list at `TOP=681`, far above.

So the icons must be **new controls added to `abilities.gui` at build time**, and
a control invented in the GUI has no class member — the module has no address for
it and cannot toggle its fill. Left there, the hint would be permanently visible,
including for keyboard-and-mouse players, which is exactly the behaviour the badge
system was changed to avoid.

**The lookup that must be solved, and the reason it is delicate.** An earlier
unreleased build addressed controls by their GFF list index through
`CSWGuiPanel::GetControl`. Runtime control-array order is not guaranteed to match
GFF list order, and on 2026-09-06 that caused an access violation in
`SetFillImage` at `swkotor.exe+0x14C3E` when Save/Load opened with controller mode
active, identified from Windows event 1000 and the matching crash dump. That
lookup was removed. Any new lookup must not reintroduce it.

**Preferred approach: content-addressed lookup by TAG.** Walk the panel's control
array at runtime and match the control's tag string, rather than trusting an
index. A tag is stable across resolutions and cannot silently point at the wrong
object the way an index can.

**What has to be found first** (from `kotor1_0_3.db`, class `CSWGuiPanel`):

- the offset of the panel's control array and its count
- the offset of the tag string within a control, and whether it is a `CExoString`
  or an inline `CResRef`

Note the fill field is an **inline 16-byte ResRef** at border-params `+0x40`, not a
`CExoString` — established this session against a live badge, after reading it as
`{char* text; int length}` produced a false "the badges do not work" report. Do
not assume the tag has the same shape as the fill; measure it.

**Rejected: shipping the hint always-visible** as a stopgap. It is cheap, but it
undoes a behaviour the user specifically asked for, and a visible-to-everyone
Xbox glyph on a keyboard player's screen is worse than no hint.

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

## 4. Tab switching and the agreed menu button layout

**Already implemented, not yet play-verified:** the Abilities panel now has an
entry in `GetK1SettingsStripExit`, so Up from the top of the ability list reaches
the tab row and Left/Right moves along it. Offsets are from `kotor1_0_3.db`, class
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
| **LT / RT** | move between screens — Map, Inventory, Character… | already works; vanilla `Q` / `E` |
| **LB / RB** | move between tabs within a screen | to implement |
| **L3 / R3** | change which crew member the screen is about | to implement |

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

**Artwork needed.** `third_party/Included/Xelu-Free-Controller-Prompts-CC0/`
vendors ten glyphs and already has `360_LB.png` and `360_RB.png`. It does **not**
have L3 / R3. Both exist in the upstream CC0 pack; vendor them and add the two
filenames to the list in `THIRD_PARTY_NOTICES.md`. CC0, so no permission is
required, but the notice must still list what is redistributed.

---

## What is verified, and what is not

| claim | how |
| --- | --- |
| Guide is masked by `XInputGetState`, exposed by `XInputGetStateEx` ordinal 100 as `0x0400` | Microsoft's documented XInput behaviour; **not** measured on this machine |
| `XI_LEFT_TRIGGER` already uses `0x0400` | read from `K1XboxControlsXInput.cpp:67` |
| `ReadPad` sticks to the first answering slot | read from `K1XboxControlsXInput.cpp:271-296` |
| A virtual pad on a lower slot disables a real one | observed twice in both directions on 2026-09-06 |
| Physical pads report NIMH/ALKALINE, ViGEm reports WIRED | measured on both this session |
| Abilities member offsets | `kotor1_0_3.db`, corroborated by `description_listbox` matching the shipping constant |
| The fill field is an inline 16-byte ResRef at border-params `+0x40` | read from a live badge in memory |
| Abilities tab navigation reaches the tabs | **verified in play 2026-09-06.** Up from the list reaches the tab row and A activates a tab |
| Focus survives activating a tab | keeper implemented and installed; **play-test still owed** |
| The inventory key is `I` | user's report from play; not read from the keymap |
