# Controller behaviour matrix

What every controller input actually does, screen by screen, as the native path
currently stands. This is a measurement pass: **no mapping, navigation behaviour, prompt graphic,
UI layout or controller logic was changed to produce it.** The diagnostics it
reads — the module's navigation and stick-click counters — already existed.

Two questions are kept apart throughout, because conflating them is the easiest
way to be confidently wrong here:

* **Is the event delivered?** Read from the input description's value while the
  button is held. Proves the wiring.
* **Does the screen respond?** Read from live engine state — the panel stack, the
  focused control, the input class, the camera mode. Proves the behaviour.

A row saying "event delivered, no observable state change" means the button
reaches the screen and the screen ignores it. That is a real and common answer,
and it is not the same as "unbound".

## How each claim was established

| Mark | Meaning |
| --- | --- |
| **S** | statically proven — the panel's dispatcher and the handler's call targets, from the binary |
| **L** | verified from live engine state — panel stack, focus pointer, input class, camera mode |
| **V** | verified with the virtual gamepad driving the running game |
| **H** | still needs a human with a physical controller |

Tools: `tools/controller_behaviour_matrix.py` (static),
`testing/controller/audit_screen_behaviour.py` (live).

## Input classes

`CClientExoAppInternal+0x9c`, read live:

| Value | Name | When |
| --- | --- | --- |
| 0 | `ICPC` | normal gameplay |
| 2 | `ICPCGUI` | any GUI screen has the input |
| 3 | `ICDialog` | conversations |
| 4 | `ICFreeLook` | free look |

A description is polled only in the classes it was registered for. KMRP registers
the buttons in 0, 2 and — since the dialogue fix — the five events with a
consumer in 3. **Class 4 is deliberately not given the general button set**: it
carries only the free-look *exit* event `0x06`, which is what R3 uses to leave,
alongside the game's own Start. Duplicating class 0 into class 4 would put a
live button map behind a camera mode that has no use for one.

The class matters because KMRP's focus navigation runs **only** at class 2, and
because the D-pad's native codes are suppressed only where that layer acts.

---

# 1. Master matrix

One row per screen. `nav` = KMRP spatial focus navigation. "—" = delivered but
the screen does nothing with it.

| Screen | A | B | X | Y | LB | RB | LT | RT | Start | Back | D-pad | L-stick | L3 | R-stick | R3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Gameplay** | **use target** | — | — | — | — | — | — | — | **open menu** | — | — | **move** | **flourish** | **camera** | **free look** |
| **Main menu** | **activate** | — | — | — | — | — | — | — | — | — | **nav** | **nav** | — | — | — |
| **In-game menu root** | **activate** | **close to game** | — | — | — | — | **prev tab** | **next tab** | — | — | **nav** | **nav** | — | — | — |
| **Equipment** | activate | close | — | — | list scroll | list scroll | prev tab | next tab | — | — | nav | nav | — | — | — |
| **Inventory** | activate | **close to game** | **next filter** | — | list scroll | list scroll | prev tab | next tab | — | — | nav | nav | — | — | — |
| **Character** | **level up** | close | **char sheet** | **equip** | — | — | prev tab | next tab | — | — | nav | nav | — | — | — |
| **Abilities** | activate | close | **use/assign** | — | list scroll | list scroll | prev tab | next tab | — | — | **native** | nav | — | — | — |
| **Messages** | activate | close | **clear** | — | — | — | prev tab | next tab | — | — | nav | nav | — | — | — |
| **Journal** | activate | close | **sort** | **quest sel.** | list scroll | list scroll | prev tab | next tab | — | **Black** | nav | nav | — | — | — |
| **Map** | **activate** | close | **transit** | — | — | — | prev tab | next tab | — | — | **native** | nav | — | — | — |
| **Save / Load** | activate | close | **delete** | — | — | — | — | — | — | — | nav | nav | — | — | — |
| **Options (in-game)** | activate | close | — | — | — | — | prev tab | next tab | — | — | nav | nav | — | — | — |
| **Message box** | activate | dismiss | — | — | — | list scroll | — | — | — | — | nav | nav | — | — | — |
| **Feats / Powers / Skills** | activate | close | — | — | list scroll | list scroll | — | — | — | — | **native** | nav | — | — | — |
| **Store (merchant)** | activate | close | **buy/sell** | — | list scroll | list scroll | — | — | — | — | nav | nav | — | — | — |
| **Container** | **take** | close | **take all** | — | — | — | — | — | — | — | nav | nav | — | — | — |
| **Party select** | activate | close | — | — | — | — | — | — | — | — | nav | nav | — | — | — |
| **Level up** | activate | close | — | — | — | — | — | — | — | — | nav | nav | — | — | — |
| **Character creation** | activate | back | — | **name** | list scroll | list scroll | **prev step** | **next step** | — | — | **native** | nav | — | — | — |
| **Options sub-screens** | activate | close | — | — | list scroll | list scroll | — | — | — | — | nav | nav | — | — | — |
| **Dialogue** | **select / skip** | — | — | — | **terminal scroll** | **terminal scroll** | — | — | — | — | **Up/Down = reply** | — | — | camera | — |

Rows in bold were verified live with the virtual pad. The rest are statically
proven and marked per screen below.

## Changed since this measurement

Read from the code on 2026-09-24 (`K1NativeJoystick.cpp`), **not re-measured**
with the virtual pad. The matrix above and the per-screen tables below are the
measurement as it was taken; where they disagree with this list, this list is
what the current build does.

| Since | Change | Where in the code |
| --- | --- | --- |
| 2026-09-14 | **Gameplay verbs.** In gameplay (class 0) LB is SelectPrev, which also leaves free look; RB SelectNext; Back PartyActive, the Solo Mode query; LT ChangeChar, the next living party member; RT Pause. So those five gameplay cells are no longer "—" | `K1_GAMEPLAY_ACTIONS` |
| 2026-09-14 | **LB and RB carry no menu event.** The "list scroll" cells above are the right stick now, which scrolls descriptions with its own hold-and-repeat | `GuiEventWantedInMenusK1`, `UpdateDescriptionScrollK1` |
| 2026-09-15 | **R3 switches party member** on Abilities, Character, Equipment and Inventory: event `0xCE` to the panel's own dispatcher. Those four R3 cells are no longer "—" | `PerformPendingPartySwitchK1`, `K1_PARTY_SWITCH_PANELS` |
| 2026-09-19 | **Start opens the Map** in gameplay, and closes the in-game menu from any tab; see the note under *Gameplay* | `K1_START_OPENS_MAP`, `K1_START_CLOSES_MENU` |
| -- | **R3 leaves free look too.** A press in class 4 is bridged to the exit, `0x06`, on the gameplay frame, so R3 toggles and LB also leaves | `PerformPendingFreeLookExitK1` |

**One cell was wrong when written.** Abilities' X is not "use/assign": its `0x29`
handler at `0x006AE714` cycles the Skills / Powers / Feats sub-tab, a three-state
index at `CGuiInGame+0xBC0` that wraps -- read from the disassembly in
[`../reverse-engineering/custom-gui-controls.md`](../reverse-engineering/custom-gui-controls.md),
and the reason the swap-tabs cue sits beside those tabs.

---

# 2. Per-screen detail

## Gameplay — input class 0

Top panel is `CSWGuiFade` over `CSWGuiMainInterface`. No GUI screen owns the
input, so KMRP's focus navigation does not run and the D-pad's native codes are
**not** suppressed.

| Input | Event | Slot / code | Result | Source | Trigger | Verified |
| --- | --- | --- | --- | --- | --- | --- |
| A | `0x27` | `0x74` / `BUTTON(0)` | delivered; no observable state change | KMRP native joystick event | press | L V |
| B | `0x28` | `0x75` / `BUTTON(1)` | delivered; nothing | KMRP native joystick event | press | L V |
| X | `0x29` | `0x76` / `BUTTON(2)` | delivered; nothing | KMRP native joystick event | press | L V |
| Y | `0x2A` | `0x77` / `BUTTON(3)` | delivered; nothing | KMRP native joystick event | press | L V |
| LB | `0x39` | `0x78` / `BUTTON(4)` | delivered; nothing | KMRP native joystick event | press | L V |
| RB | `0x3A` | `0x79` / `BUTTON(5)` | delivered; nothing | KMRP native joystick event | press | L V |
| Back | `0x2B` | `0x7A` / `BUTTON(6)` | delivered; nothing | KMRP native joystick event | press | L V |
| LT | `0x35` | `0x7B` / `BUTTON(7)` | delivered; nothing | KMRP native joystick event | press | L V |
| RT | `0x36` | `0x7D` / `BUTTON(9)` | delivered; nothing | KMRP native joystick event | press | L V |
| **Start** | `0x0B` | `0x7C` / `BUTTON(8)` | **opens the in-game menu**; class 0 → 2, panel depth 2 → 3, 81% of screen | Native retained event, action router `0x006213BC` | press | S L V |
| D-pad | `0x2F`–`0x32` | `0x7F`–`0x82` / POV | delivered; nothing | KMRP native joystick event | press | L V |
| **Left stick** | `0x07` / `0x08` | `0x6E` / `0x6F` | **moves the character**, proportional | Native retained event | analog | S L V |
| **L3** | none | none | **flourish weapons** | KMRP engine bridge → `CClientExoApp::PlayerFlourishWeapons` | press | S L V |
| **Right stick** | none | none | **turns the camera**; mouse-delta peaks ±14.00, sign-correct, 0 at rest | KMRP engine bridge (mouse-delta injection) | analog | S L V |
| **R3** | `0x01` / `0x06` | `0x7E` / `BUTTON(10)` | **toggles free look**; camera 3 ↔ 5, class 0 ↔ 4 | Native retained event, action router | press | S L V |

**A now acts on the target** — see section 8. B, X, Y, LB, RB, Back, LT, RT and
the D-pad still deliver their events and the world still ignores them: those are
GUI events and gameplay has no handler for them.

**Changed 2026-09-19, read from the code, not yet measured in play (S only):**
Start opens the **Map** instead of the Options menu, through the engine's own Map
hotkey `0xD7`, and with the in-game menu up it sends B, so it closes the menu from
any tab (issue #18). B now also lets go of the bottom-right action bar when one of
its slots has focus, and a slot used with A lets go of it too (issue #17). The rows
above are the measurements as they were taken; see
[`controller-native-path.md`](controller-native-path.md).

**R3 is context-dependent.** The enter handler requires a live player creature,
`[internal+0x2c0] == 0`, and not paused by combat. Measured 10/10 from a clean
state, and 6/6 after A, X, Y, Back or a stick push — but see the L3/R3
interaction in section 5.

**The right stick turns the camera**, via `CSWCModule::RotateCamera` from the
`NativeCameraFrameK1` hook at `0x006039CF`. Playtest-confirmed. Note for any
future harness: this is not visible to screen diffing *or* to reading
`CExoInputInternal+0x3A0`, which the engine discards -- see the camera section of
`docs/controller-native-path.md`. The pass condition is a human seeing the view
turn.

## Main menu — `CSWGuiMainMenu`, dispatcher `0x0067B380`

The panel implements only `0x28` and `0x2D`. Neither is A.

| Input | Event | Result | Source | Verified |
| --- | --- | --- | --- | --- |
| **A** | `0x27` | **activates the focused entry.** The panel does not implement `0x27`; the base handler forwards it to the focused control, and `CSWGuiButton` implements exactly `0x27` | Native retained event via the focused control | S; **not re-pressed in automation — it starts a New Game** |
| B | `0x28` | delivered; **nothing observable** at the menu root | Native retained event | S L V |
| X, Y, LB, RB, Back, LT, RT | — | delivered; nothing | KMRP native joystick event | L V |
| Start | `0x0B` | nothing (the action router needs a module) | Native retained event | L V |
| **D-pad Up / Down** | suppressed | **moves focus through the five entries in reading order and wraps**: y 666 → 738 → 810 → 882 → 954 → 666 | KMRP spatial navigation | L V |
| **D-pad Left / Right** | suppressed | **also moves focus**, because the column has no horizontal neighbour and the wrap rule applies — see section 5 | KMRP spatial navigation | L V |
| **Left stick** | suppressed | same as the D-pad; verified 666 → 738 → 810 | KMRP spatial navigation | L V |
| L3, R3 | — | nothing | — | L V |

Focus targets are the five entries only. The background is a control the full
size of the screen carrying the visible and selectable bits; it is excluded
because it registers no events.

## In-game menu — the tab strip

The tab cycle, walked with RT and read from the panel stack:

**Equipment → Inventory → Character → Abilities → Messages → Journal → Map →
Options →** (back to Equipment). Eight tabs, cyclic in both directions. **L V**

The top panel is always `CSWGuiInGameMenu`, the shell that draws the strip; the
tab being looked at is the panel *below* it. Anything reading only the top panel
sees one screen for all eight — which an earlier pass of this audit did.

| Input | Event | Result | Source | Verified |
| --- | --- | --- | --- | --- |
| **LT** | `0x35` | **previous tab** | Native retained event | L V |
| **RT** | `0x36` | **next tab** | Native retained event | L V |
| **B** | `0x28` | **closes the menu to gameplay** (class 2 → 0, 80% of screen) from a tab; on a sub-panel it closes the sub-panel first | Native retained event | L V |
| **A** | `0x27` | activates the focused control; observed opening `CSWGuiSaveLoad` from Options and a `CSWGuiMessageBox` from Inventory | Native retained event via focused control | L V |
| **D-pad** | suppressed | **focus moves** on all four directions, every tab | KMRP spatial navigation | L V |
| Start | `0x0B` | **nothing** — see section 5 | Native retained event | L V |
| X, Y, LB, RB, Back | — | delivered; effect depends on the tab, below | Native retained event | L V |
| L3, R3 | — | nothing at class 2 | gated to gameplay | L V |

### Per-tab, from the panel dispatchers (S)

| Tab | X (`0x29`) | Y (`0x2A`) | LB (`0x39`) | RB (`0x3A`) | Back (`0x2B`) | Directions |
| --- | --- | --- | --- | --- | --- | --- |
| Equipment | — | — | list scroll | list scroll | — | KMRP |
| Inventory | `SetNextFilter` — **verified live**, 3.0% of the screen changes and Y correctly does nothing | — | list scroll | list scroll | — | KMRP |
| Character | char sheet | equip screen | — | — | — | KMRP |
| Abilities | implemented | — | list scroll | list scroll | — | **native** |
| Messages | clear | — | — | — | — | KMRP |
| Journal | sort | quest select | list scroll | list scroll | **Black, implemented** | KMRP |
| Map | transit | — | — | — | — | **native** |
| Options | — | — | — | — | — | KMRP |

`Journal` is the **only** panel in the entire inventory that implements `0x2B`
(Back/Black). Everywhere else Back is delivered and ignored.

## Screens the engine navigates itself

`ABILITIES`, `ABILITIES_CHARGEN`, `FEATS`, `MAP`, `POWERS`, `SKILLS` implement
the direction events in their own dispatcher. On these the KMRP layer **declines**
and the native codes are emitted normally. **S**, and the decline is asserted by
the regression suite. Their internal navigation has **not** been driven end to
end with the pad — **H**.

## Screens not reached live

Statically proven only; each needs live or human verification (**S**, needs **V H**):

| Screen | A | B | X | Y | LB / RB | Directions |
| --- | --- | --- | --- | --- | --- | --- |
| Store (merchant) | focused control | close | buy/sell | — | list scroll | KMRP |
| Container | `0x27` implemented | close | take all | — | — | KMRP |
| Party select | focused control | close | — | — | — | KMRP |
| Level up | focused control | close | — | — | — | KMRP |
| Class select (chargen) | focused control | close | — | — | — | KMRP, plus LT/RT `0x35`/`0x36` |
| Name entry (chargen) | focused control | close | — | implemented | — | KMRP |
| Abilities (chargen) | `0x27` implemented | close | — | implemented | list scroll | **native** |
| Options sub-screens | focused control | close | — | — | list scroll | KMRP |
| Auto-pause options | focused control | close | — | — | — | KMRP |
| Graphics / Resolution | focused control | — | — | — | — | KMRP |
| Pazaak setup / game | focused control | close | — | implemented | — | KMRP |
| Upgrade / item select | focused control | close | — | — | list scroll | KMRP |
| Solo mode query | **panel-level, ignores focus** | close | — | — | — | KMRP |
| Key mappings | focused control | close | — | — | — | KMRP |

**Dialogue** has its own panels — `CSWGuiDialogCinematic`, `CSWGuiDialogTop`,
`CSWGuiDialogLetterbox`, `CSWGuiDialogComputer` — and is fully working as of the
class-3 fix. See section 8.

---

# 3. Global consistency

What holds everywhere, which is what a prompt can safely claim:

| Input | Consistent meaning | Exceptions |
| --- | --- | --- |
| **A** | **confirm / activate the focused control** | **two exceptions, found 2026-09-20.** `SOLO_MODE_QUERY` and `OPTIONS_RESOLUTION` implement `0x27` themselves and never read the active control, so A ran their confirm action from Cancel. KMRP now consumes A on those two when Cancel holds focus — see below |
| **B** | **cancel / back / close** | implemented by 35 of 40 panels. `SOLO_MODE_QUERY` implements **both** `0x28` and `0x2E`, at `0x006C2488`, so B does dismiss it — the earlier "`0x2E` only" came from the stale inventory row corrected on 2026-09-20 |
| **LT / RT** | **previous / next tab**, in the in-game menu only | no effect anywhere else, including the main menu and gameplay |
| **LB / RB** | **scroll the focused list** | only meaningful on the 17–19 panels with a list; silent elsewhere |
| **D-pad** | **move focus** | on the six native-direction screens the engine moves its own selection instead |
| **Left stick** | **move** in gameplay, **move focus** in a GUI | never both: gated on input class |
| **Start** | **open the in-game menu**, from gameplay only | does **not** close it — B does |
| **Back** | nothing | `JOURNAL` alone implements it |
| **X** | **per-screen**, no consistent meaning | Inventory filter, Journal sort, Map transit, Character sheet, Save/Load delete |
| **Y** | **per-screen**, no consistent meaning | 8 panels only |
| **L3** | **flourish weapons**, gameplay only | declines in menus, free look, and with no player |
| **Right stick** | **camera**, gameplay only | horizontal only; there is no vertical axis in the engine |
| **R3** | **free look**, gameplay only | blocked for ~4 s after a flourish — section 5 |

---

# 4. Prompt design recommendations

Recommendations only. **Nothing here is implemented.**

### Safe to show anywhere they apply

* **A = Select/Activate** and **B = Back/Cancel.** These are the only two with a
  meaning that holds on every screen. All 30 existing badges already depict A, B
  or X, and all three kept their meanings — no current badge is misleading.

### The tab strip

* **LT on the left end of the strip, RT on the right end.** This is the one place
  the geometry is unambiguous: LT and RT move the highlighted tab backwards and
  forwards through the eight tabs, and only in the in-game menu.
* Do **not** show LT/RT on the main menu, in gameplay, or on any sub-panel opened
  from a tab (Save/Load, message boxes). They do nothing there.

### Per-screen

* **LB/RB** only on screens with a scrollable list: Equipment, Inventory,
  Abilities, Journal, Store, Upgrade, the options screens. Silent elsewhere, so
  a prompt would be a lie on the others.
* **X** needs a *screen-specific label* — "Filter" on Inventory, "Sort" on
  Journal, "Transit" on Map, "Delete" on Save/Load. A generic X prompt is
  actively misleading because the action differs every time.
* **Y** likewise, and it appears on only 8 panels.
* **Back** — do not prompt at all, except possibly on Journal, the only screen
  that implements it.

### Gameplay HUD

* **Start = Menu** is safe and unconditional.
* **L3 = Flourish** and **R3 = Free Look** are safe *as gameplay-only prompts*,
  but see below: an R3 prompt is briefly inaccurate after a flourish.
* Right stick = camera needs no prompt; it is discovered instantly.

### Where a prompt would mislead

* **Start on any GUI screen.** It looks like a menu toggle and does nothing once
  a screen is open. If a "close" prompt is wanted there it must depict **B**.
* **R3 immediately after L3** — blocked for about four seconds.
* **D-pad Left/Right on a single-column menu**, which currently moves focus
  vertically by wrapping.
* **Any generic X or Y glyph** without a screen-specific label.

### Screens needing no extra prompts

Gameplay (beyond Start/L3/R3), the six native-direction screens, and any
confirmation box, where A and B are self-evident.

---

# 5. Inconsistent or unintuitive mappings found

1. **Start opens the menu but never closes it.** The action router's hide branch
   is gated on the module state reading 3, which stops holding once the GUI is
   up, so a second press re-takes the show branch. B is the close. This matches
   the Xbox idiom but contradicts most modern pads. **S L V**
2. **L3 blocks R3 for about four seconds.** Reproducible: after a flourish, free
   look declines for roughly three attempts and then works; a second flourish
   reproduces it. The engine's own free-look guard requires an idle creature, so
   this is the flourish animation, not a KMRP fault — but it is a consequence of
   putting both on the stick clicks. **L V**
3. **D-pad Left/Right move focus vertically on single-column menus.** With no
   horizontal neighbour the wrap rule fires. Verified on the main menu: Left
   666 → 738, Right 738 → 666. Harmless but not what a player expects. **L V**
4. **A tutorial box temporarily blocks tab cycling.** `CSWGuiTutorialBox`
   appears over the Messages tab; while it is on the stack LT and RT stop
   changing tabs and the strip appears frozen. Measured: an automated pass could
   not reach four of five requested tabs, retrying nine times each. It then
   cleared **without any successful dismissing press** — so it is transient, not
   a deadlock. Which button dismisses it, and how long it lasts, were **not**
   determined. **L V, partially**
5. **Back is bound but does nothing on 39 of 40 panels.** Only Journal
   implements `0x2B`. A controller with a labelled Back button will look broken.
6. **X and Y have no consistent meaning**, which is inherent to the retained
   design rather than a KMRP decision.
7. **`SOLO_MODE_QUERY` implements both `0x27` and `0x28`.** A reaches
   `TogglePartyFollow`, B reaches `CGuiInGame::HideSoloMode`, so **B dismisses
   it**. **Confirmed 2026-09-20, and it is worse than "implements":** the A
   handler at `0x006C244C` calls `CClientExoApp::TogglePartyFollow`
   unconditionally and falls through into the `0x28` path, without ever reading
   the active control. On the PC panel, which draws a highlighted OK and Cancel,
   A therefore turned Solo Mode on from **either** button — the defect reported
   as issue #21. `CSWGuiOptionsResolution` has the identical shape at
   `0x006E0F14`, calling `OnResolutionChosen` the same way. Both are corrected
   in the module; the plain message box is not affected, because `0x006250F0`
   implements no `0x27` at all and so genuinely defers to the focused control. **Corrected 2026-09-24:** the
   first fix refused on BOTH buttons, and the cause was not a second confirm
   route -- the decision log showed exactly one confirm per press, each passed
   through, each refused. It was KPM's wrapper order: stolen bytes run before
   the consumed-exit `TEST EAX`, and the Solo hook's stolen `mov eax,[0x7A39FC]`
   put the app pointer in EAX, so every A took the close path. The resolution
   hook's stolen `push 0` reached its exit with an extra dword on an
   ESP-relative frame. Both now rewrite A to B at the handler's entry
   (`0x006C2400`, `0x006E0CF0`) instead of using a consumed exit. An earlier pass claimed otherwise; that came from a decoder fault which
   accumulated across a `mov ecx, eax` that restarts the arithmetic, inventing
   `0x55`/`0x56`/`0x5B` and hiding the real codes. The same fault invented events
   on `OPTIONS_GRAPHICS`, `OPTIONS_GRAPHICS_ADVANCED` and `OPTIONS_RESOLUTION`.
   Fixed; the inventory is 219 events and every code now falls inside a
   plausible range. **S**

---

# 6. What still needs a human with a physical controller

1. **The screens never reached live** — merchant, containers, party select, level
   up, character creation, the options sub-screens, Pazaak, upgrade. Static
   analysis says what the handlers do; nobody has watched them respond.
2. **Dialogue.** Not a panel, not reached, and the most-used screen in the game.
   This is the single largest gap in this document.
3. **Whether `SOLO_MODE_QUERY` can be closed with B** — finding 7 above. Static
   analysis now says yes (`0x28` -> `0x006C2488` -> `CGuiInGame::HideSoloMode`);
   nobody has yet watched it happen with a pad in hand.
4. **The tutorial box** — which input dismisses it, and whether it can be
   waited out comfortably while the tab strip is unresponsive.
5. **Internal navigation on the six native-direction screens** (Abilities,
   Feats, Powers, Skills, Map, chargen Abilities). The layer correctly declines;
   whether the engine's own selection then moves sensibly with a real D-pad is
   unwatched.
6. **Whether the L3/R3 interaction is acceptable**, or whether L3 should move.
7. **Camera sensitivity, deadzone, and physical D-pad orientation** — carried
   over, still the standing feel items.

---

# 7. Second audit pass — the input-class finding

Everything below was measured after the first pass. It changes the shape of the
document, because it turns a set of per-screen observations into one rule.

## The rule

**A description is polled only in the input classes it was registered for.** The
analog axes are registered in all six; the buttons were registered in 0 and 2
only, which is why the pad was inert wherever the engine used another class.
Class 3 now carries the five dialogue events as well — see section 8. Classes 1
and 5 remain unregistered, deliberately.

From `src/controller-native/K1NativeJoystick.cpp`: every button, trigger and
D-pad binding calls `addEvent(..., K1_CLASS_PCGUI)` and
`addEvent(..., K1_CLASS_PC)` — classes 2 and 0. The axes loop `for (cls = 0; cls
< 6; ++cls)`. Nothing registers class 1, 3 or 5.

| Class | Name | Where | Buttons work? |
| --- | --- | --- | --- |
| 0 | `ICPC` | gameplay | **yes** |
| 1 | `ICMiniGame` | Pazaak, swoop | **no** — untested, predicted |
| 2 | `ICPCGUI` | menus | **yes** |
| 3 | `ICDialog` | conversations | **yes, for five events** — see section 8 |
| 4 | `ICFreeLook` | free look | **no — measured**, except Start and R3's own exit event `0x06`, registered in class 4 on purpose |
| 5 | `ICMovie` | cutscenes | **no** — untested, predicted |

Classes 1 and 5 are marked predicted, not measured. They follow from the same
registration and should be confirmed before being relied on.

## Dialogue — superseded

The dialogue material that stood here recorded a broken state: every button
undelivered in class 3, the reply highlight frozen. That was fixed in the third
pass and the working account is in section 8. The diagnosis it reached still
stands and is repeated there.

## Free look — measured

In class 4, A, B and the D-pad are **not** delivered. **Start is** — the game's
own `0x0B` description covers this class. R3 leaves free look because KMRP
registered the exit event `0x06` in class 4 specifically. So free look is
enterable and leavable, and nothing else on the pad works while in it. **L V**

## L3 blocking R3 — narrowed, not solved

Reproducible: after a flourish, R3 declines to enter free look, then works.
Measured windows of roughly 4 and 7 seconds across runs, so it tracks an
animation rather than a fixed timeout.

What it is **not**: `[CClientExoAppInternal+0x2c0]` reads 0 throughout, and a
512-byte diff of the player control object at `[CClientExoAppInternal+0x2A0]`
showed **no** fields changing across the flourish.

**A cheap engine-readable predicate was not found.** The remaining candidates are
the creature-side checks in the enter handler — `[player+0x138]`, the server
creature's `[+0xFC]`, and `GetPausedByCombat` — none of which were isolated. Any
future "dim the R3 prompt" logic would need one of those confirmed first; timing
it at four seconds would be wrong, since seven was also observed. **L V, cause
undetermined**

## Single-column navigation — exact evidence

Main menu, five entries in one column at x = 1782, heights 66 except the last
at 81. Focus read from the panel's active control each time.

| From (y) | Input | To (y) | Note |
| --- | --- | --- | --- |
| 666 | Up | 954 | wraps to the bottom |
| 954 | Down | 666 | wraps to the top |
| 666 | **Left** | **738** | no horizontal neighbour, so the wrap fallback fires |
| 738 | **Right** | **666** | same |
| 666 → 738 → 810 → 882 → 954 | Down x4 | in reading order | correct |

**This is a design decision, not a defect.** The navigator's wrap fallback takes
the farthest control in the opposite direction when nothing lies ahead, and on a
single column "ahead" is empty for Left and Right. The stated preference —
Left/Right with no candidate on that axis should stay put — is a one-line change
to `ChooseNeighbourK1`, deliberately **not** made during this audit. **L V**

A second single-column screen was not reached; the in-game tab strip is two rows
and does not exercise the same case.

## Tutorial box — partially characterised

`CSWGuiTutorialBox` appears over the Messages tab. While it is on the panel
stack, LT and RT stop changing tabs: an automated pass could not reach four of
five requested tabs, retrying nine times each. It then cleared **without any
successful dismissing press**, so it is transient.

Not determined: what triggers it, how long it lasts, whether any input dismisses
it, and whether it formally owns input as a modal. `CSWGuiTutorialBox` is not in
the retained-event inventory, so its dispatcher has not been decoded. It should
be treated as *probably modal* for prompt purposes — LT/RT should be hidden or
dimmed while it is up — but that is a recommendation from observed behaviour,
not from a proven modal flag. **L V, partial**

## Camera — superseded measurements

`CExoInputInternal+0x3A0` is **not** read by `UpdateCamera`. The figures below
record what KMRP wrote into that dead field before the turn was reimplemented on
`RotateCamera`; no row corresponds to visible rotation, and they are kept only
so the numbers are not mistaken for evidence if they turn up again:

| Input | Peak delta | |
| --- | --- | --- |
| Right stick full right | **+14.00** | sign correct |
| Right stick full left | **−14.00** | sign flips |
| Small deflection | 2.07 | scales |
| Mid deflection | 7.60 | scales |
| Centred | 0.00 | clean |

Earlier the same motion registered as "nothing" under screen diffing. **Pixels
must not be used for camera claims.** Sensitivity remains a feel judgement. **L V**

## Coverage after this pass

| | Count |
| --- | --- |
| Panels in the retained-event inventory | 40 |
| Additional panels found outside it | 3 — `CSWGuiInGameMenu`, `CSWGuiDialog*`, `CSWGuiTutorialBox` |
| Contexts verified live with the pad (**V**) | 13 — gameplay, main menu, in-game menu root, the 8 tabs, dialogue, free look |
| Verified from live engine state (**L**) | the same 13, plus the input-class model |
| Static only (**S**), still needing **V** | 24 panels — merchant, containers, party select, level up, all of character creation, the options sub-screens, Pazaak, upgrade, key mappings. **Message box internals are no longer unread**: `CSWGuiMessageBox`'s constructor at `0x00626DF0` builds `BTN_OK` at `+0x2F4` and `BTN_CANCEL` at `+0x4B8` over the GUI named `confirm`, and its dispatcher `0x006250F0` implements only `0x28`/`0x2E` and `0x3A`. Still unwatched in play. |
| Requiring human QA (**H**) | every feel item, plus everything in the static-only list |

The inventory itself is now believed sound: after the decoder fix, no event code
falls outside the plausible ranges, which was not true before.

---

# 8. Third pass — the two functionality gaps, closed

Section 7 ended with two things that outranked any prompt work: dialogue was
inert, and nothing on the pad could act on the world. Both are fixed and
verified. This section supersedes the "dialogue does not work" material above.

## Dialogue — working

**Cause.** A description is polled only in the input classes it was registered
for. Conversations run in class 3 and KMRP registered its buttons in classes 0
and 2 only, so nothing reached the game. The engine's own handlers were correct
and complete the whole time.

**Fix.** Five events registered in `ICDialog`, chosen from the two dialogue
dispatchers rather than added wholesale:

| Event | Button | Consumer | Effect |
| --- | --- | --- | --- |
| `0x27` | A | `CSWGuiDialog` `0x006A7266` | skip the line while one plays, else choose the highlighted reply |
| `0x31` | D-pad Up | `0x006A72B9` | previous reply — `[panel+0x68]` decremented, floored at 0 |
| `0x32` | D-pad Down | `0x006A72DB` | next reply — incremented, capped at `[panel+0x6C] - 1` |
| `0x39` | LB | `CSWGuiDialogComputer` `0x006A81E0` | re-dispatches `0x31` to a terminal's text |
| `0x3A` | RB | `0x006A81E0` | re-dispatches `0x32` |

B, X, Y, Back, Left, Right, the triggers and Start reach the dialogue
dispatcher's **default case** and are deliberately left unregistered.

**A correction worth keeping.** The reply list *is* a focused `CSWGuiListBox`,
but it never receives these events: the panel owns the selection itself at
`+0x68`, and the default branch forwards to the focused control only for events
0 and 1. So "the list box owns dialogue navigation" was wrong — the panel does.

**Measured**, in a two-reply crew conversation, reading `[panel+0x68]`:

| Check | Result |
| --- | --- |
| Down | reply 0 → 1, one tap one move |
| Down again at the end | clamped at 1 |
| Up | 1 → 0 |
| Up again at the top | clamped at 0 |
| 4× Up then 4× Down | 0, then 1 — bounds correct |
| Hold Up 1.8 s | repeats, clamps at 0, no runaway |
| B, X, Y | still undelivered, as intended |
| A | advances the conversation; reply index resets to 0 on the next node |
| KMRP navigation counters | **0 moves** — it stays out, being gated to class 2 |
| Movement accumulators | **unchanged** — no gameplay movement leaks in |
| Leaving the conversation | class returns to 0 and A, B, Down all deliver again |

**L V**

## World interaction — working, via a bridge to the engine's own router

**The retained path exists.** Event `0xEF`, handler `0x00621FC1`: it checks the
target at `[CClientExoAppInternal+0x2b4]` against `OBJECT_INVALID`
(`0x7F000000`), calls `CClientExoAppInternal::GetDefaultActions`, and executes
the first action. That is what talks to an NPC, opens a container and uses a
door.

**It cannot be a native joystick event.** Descriptions are one per event id and
`0xEF` already carries the keyboard's, on slot `0x44`. Unlike `0x0B`/`0xDF` or
`0x01`/`0xD0`, the router lists **no low-id console partner** for it. So
category A is genuinely unavailable here, which is what justifies a bridge.

**What was rejected.** `0x43` reaches
`CClientExoAppInternal::PerformLButtonDownAction`, which ends in
`CSWGuiManager::HandleLMouseDown` — a click at the cursor, not an action on the
target. It would have required driving a cursor and is not what the console did.

**The bridge.** `CClientExoAppInternal::HandleInputEvent(internal, 0xEF, 1)` —
the engine's **own event router**, not a reimplementation, so every guard in the
retained handler runs. Requested on A's rising edge and performed from the
gameplay heartbeat, the same discipline as the flourish: never from inside the
input hook, dropped if not consumed within 250 ms, and declined outside class 0
or with no target.

**Measured, controller only, no mouse:**

| Check | Result |
| --- | --- |
| A with a crew member targeted | **conversation started** — class 0 → 3, dialogue panels up |
| navigating that conversation | Down 0 → 1, Up 1 → 0, pad only |
| leaving it | class back to 0 |
| three rapid A presses | **one** action performed — no double activation |
| A in a menu or dialogue | declined by the class check |

**Not proven:** "A does nothing with no valid target." The engine's handler
checks it and so does the bridge, but the save's auto-target stayed valid even
facing away, so a targetless state could not be produced. **Needs human QA.**

**Is A the right button?** The evidence supports it: A is the console confirm,
`0x27` did nothing in gameplay before, and the action is the analogue of the
default click. It remains a mapping decision — the bridge is one call and moving
it is one edit.

## Classes 1 and 5 — audited, deliberately not bound

**ICMiniGame (1).** `CSWMiniPlayer::Fire` is reached from the handler for events
`0x0C`/`0x19`, and **`0x0C` already carries the game's own joystick
description** — type 3, device 2, slot `0x71` = `DIJOFS_SLIDER(0)`. The same
shape as Start: a control code the module would only have to emit. Steering does
not come from an input event at all; `CSWMiniPlayer::Control` is called from
`CSWMiniGame::Control`, and the movement axes are already registered in all six
classes. **Not bound**: a minigame was not reachable from this save, and the
description is an analog type whose value semantics for a fire action are
unverified. **S**

**ICMovie (5).** `CClientExoApp::CancelMovie` has exactly one caller,
`0x00402CF4`, inside the movie player's own loop — **no retained input event
reaches it**. That is why the legacy path needs its own movie hooks: the normal
input loop is suspended during playback. There is nothing to register in class
5. **S**

## Free look, unchanged

Class 4 still carries only the free-look exit event `0x06` and the game's own
Start. R3 still enters and leaves free look — asserted by the regression suite,
which passes. Class 0's button set was **not** duplicated into class 4.

## Regression suite

**72 passed, 0 failed, 1 human-QA**, including a new check that all five
ICDialog registrations took (`dlg=0x1f`).


## L3 and R3 by context — measured 2026-09-08

Pressed in each context with `testing/controller/probe_stick_clicks.py`, which
records the screen delta, the input class, the front panel and the module's own
flourish counters. Neither stick click is a retained GUI event: R3 emits the
engine's free-look pair (`0x01` enter / `0x06` exit) and is registered only in
the gameplay and free-look classes, and L3 is a bridge to
`PlayerFlourishWeapons`.

| context | L3 | R3 |
| --- | --- | --- |
| gameplay (ICPC) | **flourish**, one per press, performed counter +1 | changes the view; see below |
| Equipment | ignored (declined) | nothing, 0.3% |
| Inventory | ignored (declined) | nothing, 0.3% |
| Messages | ignored (declined) | nothing, 0.5% |
| Journal | ignored (declined) | nothing, 0.0% |
| Map | ignored (declined) | nothing, 0.0% |
| Options | ignored (declined) | nothing, 0.3% |
| tab strip | ignored (declined) | nothing |

**"Ignored" is now true, and was not before.** The flourish bridge checked free
look but never the input class, so a stick click in ANY menu still swung the
character's weapon behind the open screen -- the performed counter rose on every
press across Equipment, Inventory, Messages, Journal, Map and Options. It now
declines outside gameplay, which is what the table above records.

**One Map reading did not reproduce.** An early pass saw R3 change 42.9% of the
Map screen; a rerun after the fix showed 0.0%. It was the map's own animation
between the two screenshots, not R3.

**R3 in gameplay is not fully characterised.** It changes the view -- 44% on the
first press, 11% on the next -- but `ClientOptions+0x6D`, the camera mode, read 3
both before and after each press, where free look should read 5. The end-to-end
suite's own stick-click test reads the same field and sees `[5, 3, 5, 3, 5, 3]`.
The two disagree and the difference has not been chased down. **R3 was not
changed in this pass**, and its physical crash report stays open.

Not reachable from the harness save, so not measured: character creation, party
selection, the store, upgrade screens, save/load, dialogue, the minigame class
and the movie path.
