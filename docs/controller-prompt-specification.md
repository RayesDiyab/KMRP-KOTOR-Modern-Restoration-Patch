# Controller prompt specification

What each screen should show, and when. **Nothing here is implemented** — this
is a specification drawn from `controller-behaviour-matrix.md`, and every rule
below traces to a measurement in it.

One rule governs all of it: **a prompt must not appear for an input that cannot
act.** That is stricter than it sounds, because of the input-class finding.

## The blocker that outranks the design

A description is polled only in the classes it was registered for. Buttons live
in classes 0 and 2, plus five events in class 3 for dialogue. Class 4 carries
only free look's own exit event, and classes 1 and 5 carry nothing.

**Dialogue is now bound and verified**, so its prompts are live specifications.
Minigames (class 1) and movies (class 5) are still unbound, so **no prompt should
be specified for them**: a glyph there would advertise a button that provably
does nothing.

## Global glyph vocabulary

| Glyph | Label | Shown when |
| --- | --- | --- |
| A | context verb — "Select", "Activate", "Take", "Buy" | a focusable control has focus |
| B | "Back" at a sub-screen, "Close" at a tab root | the screen can be left with B |
| X | **screen-specific label, never generic** | only on the screens listed below |
| Y | **screen-specific label, never generic** | only on the screens listed below |
| LB / RB | "Scroll" | the focused control is a list box |
| LT / RT | tab names or arrows | the in-game 8-tab strip is active **and** no modal is up |
| Start | "Menu" | gameplay only |
| L3 | "Flourish" | gameplay only |
| R3 | "Free Look" | gameplay only |
| Back/View | — | **never**; it does nothing on 39 of 40 panels |
| D-pad | — | not prompted; navigation is self-evident |

## Per-screen

### Gameplay (class 0)

| Glyph | Label | Location | Show when | Hide / dim when |
| --- | --- | --- | --- | --- |
| A | Talk / Use / Open — context | near the target reticle | a target is selected | `[internal+0x2b4]` is `0x7F000000` |
| Start | Menu | bottom-right cluster | always in gameplay | any GUI screen is up |
| L3 | Flourish | bottom-right cluster | always in gameplay | in a menu, dialogue or free look |
| R3 | Free Look | bottom-right cluster | always in gameplay | in a menu or dialogue; **see below** |

Nothing else earns a prompt here: B, X, Y, LB, RB, Back, LT, RT and the D-pad
all deliver their events and the world ignores every one of them.

**R3 dimming is specified but not yet implementable.** After a flourish, free
look declines for 4–7 seconds and the exact predicate was not identified. Either
find it first, or do not dim at all — a prompt that dims on a four-second timer
would be wrong for the seven-second case.

**A is now the interact button**, bridged to the engine's own router for event
`0xEF` — talk, open, use, on whatever is targeted. It should carry a
context-sensitive label where the game knows one, and be **hidden when nothing
is targeted** (`[CClientExoAppInternal+0x2b4]` reads `0x7F000000`), which is the
one cheap predicate this area does have.

### Main menu

| Glyph | Label | Location | Show when |
| --- | --- | --- | --- |
| A | Select | bottom strip | always |

B, X, Y, LB, RB, LT, RT, Start, L3 and R3 all do nothing here — no prompts.

### In-game menu — the 8-tab strip

The cycle is Equipment → Inventory → Character → Abilities → Messages → Journal
→ Map → Options, both directions.

| Glyph | Label | Location | Show when | Hide when |
| --- | --- | --- | --- | --- |
| **LT** | previous tab | **far left edge of the tab strip** | the strip is active | a modal owns input |
| **RT** | next tab | **far right edge of the tab strip** | the strip is active | a modal owns input |
| A | Select | bottom strip | a control has focus | — |
| B | Close | bottom strip | always | — |

**Hide LT/RT while `CSWGuiTutorialBox` is on the panel stack.** Tab cycling
demonstrably stops working while it is up. This is a recommendation from
observed behaviour; the box has not been proven to be a formal modal.

### Per-tab X and Y

Only these, and only with these labels:

| Tab | Glyph | Label | Evidence |
| --- | --- | --- | --- |
| Inventory | X | **Filter** | `SetNextFilter`, **verified live** |
| Journal | X | Sort | S |
| Journal | Y | Quest Select | S |
| Journal | Back | (the only screen implementing it) | S — prompt only if it proves useful |
| Map | X | Transit | S |
| Character | X | Character Sheet | S |
| Character | Y | Equip | S |
| Messages | X | Clear | S |
| Save / Load | X | **Delete** | S — destructive, so the label must be exact |
| Store | X | Buy / Sell | S |
| Container | X | Take All | S |

Every row marked S needs live confirmation before shipping its prompt. Inventory
is the only one confirmed.

### LB / RB

Show "Scroll" only on: Equipment, Inventory, Abilities, Journal, Store, Upgrade,
Upgrade Item Select, and the options sub-screens. Silent everywhere else, so a
prompt would be a lie.

### Confirmation boxes

| Glyph | Label |
| --- | --- |
| A | Confirm |
| B | Cancel |

`CSWGuiSoloModeQuery` is included: it implements both `0x27` (Toggle Party
Follow) and `0x28` (`HideSoloMode`), contrary to the first pass's claim.

### Dialogue — live and verified

| Glyph | Label | Location | Show when |
| --- | --- | --- | --- |
| A | **Select** while replies show, **Skip** while a line plays | beneath the reply list | always in dialogue |
| D-pad up/down | — | not prompted; the yellow highlight already shows it | — |
| LB / RB | Scroll | computer terminals only | the panel is `CSWGuiDialogComputer` |

B, X, Y, Back, LT, RT, Start, L3 and R3 reach the dialogue dispatcher's default
case and do nothing, so they must not be prompted.

A's label is genuinely two things: its handler skips the current line while one
is playing and chooses the highlighted reply otherwise. A single "Select" is a
half-truth, and the state is readable, so the label can follow it.

## Screens needing no prompts

The six native-direction screens (Abilities, Feats, Powers, Skills, Map, chargen
Abilities) beyond their A/B/X/Y rows; free look, where only Start works and
leaving is R3; and gameplay beyond the three listed.
