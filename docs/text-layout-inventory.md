# Text layout inventory and proposed fitting policies

Audit reference and implementation plan, 2026-10-17. This follows the
[documentation standard](documentation-standard.md). The inventory reads generated
GUI metadata; it does not implement a fitting policy or change the installed game.
Current font scaling is described in [in-game text options](ingame-text-options.md).
The follow-up [native-path and live-object audit](native-text-coverage.md) records
creation paths, default fonts, runtime-only owners and measured menu/gameplay
censuses, with remaining behavioral checks kept explicit.

## Scope and evidence

The reproducible catalog contains **2,071 distinct font-bearing text slots**, read
from all **83 GUI files in each of 66 generated resolution archives**: 5,478 GUI
instances and 136,686 text-slot instances. There are explicit font fields in 82 files;
`ntscpat.gui` contains none. An independent recursive count of every `FONT` field
in the 1920x1080 archive also returned 2,071, matching the catalog exactly. Each
catalog identity is present in all 66 archives, with no duplicate keys.

These are definitions, not a count of visible text boxes or native objects. The
catalog includes unused HUD variants, prototypes and empty slots. Of the 2,071
slots, 1,479 have neither a nonempty literal nor a valid talk-table reference;
they may be decorative or populated at runtime. They are retained for review.
The other slots have 217 literals and 375 talk-table references. Game strings
are not copied into the catalog.

The [inventory generator](../tools/inventory_text_layout.py) writes ignored outputs
under `build/text-layout-inventory/`: `controls.csv` and `manifest.json`. The CSV
records every slot's GUI, recursive path, prototype owner, numeric control type,
font family, alignment, baseline template geometry, raw border/padding fields,
content source, candidate group, evidence status and geometry range across sizes.
The manifest hashes all input archives and the generator. These identify the local
resource corpus, not a released build or proof of runtime geometry.

The current generated packs have consistent control type, font group, alignment
and candidate classification for each identity across all inspected sizes. This
consistency does not establish that layouts fit or that all native classes use
those fields unchanged. Template dimensions are deliberately **not** treated as
usable text rectangles; padding, icons and native control constructors may alter
that space. A maximum font percentage is not inferred from a template alone.

The extractor now also records `TEXT` definitions without `FONT`; the inspected
current corpus has none, and all 2,071 font names are nonempty. The native loader
does support a default font, so this remains an explicit check for new corpora.

Dynamically created controls are a separate coverage layer: the new Text Size and
Font page constructs 20 native controls from templates, and roster paging adds
controls at runtime. Third-party GUIs and translated strings are also outside the
static corpus until supplied. These omissions must remain visible in the ledger.

## 1. Behavior families for shared fixes

This is the proposed policy taxonomy, not an implemented dispatch table. Group by
layout behavior and native ownership, independently of the four font-size sliders.
The same font resource can occur in multiple behavior families. The native audit
added editable fields and unboxed screen printing to the initial six families.

| Family | What defines the usable space | Proposed shared rule | Required verification |
| --- | --- | --- | --- |
| Fixed caption | Native text-content rectangle inside a title, button, toggle or compact counter | Preserve the intended line count; cap local text scale by width and height | Confirm line count, actual insets and native class; check all interaction states |
| Bounded wrapped text | A fixed content area intended to contain a whole short message | Wrap using effective metrics; find the largest scale at or below the request that fits the allowed lines and height | Confirm that content is meant to fit, rather than scroll; check longest strings |
| Scrollable body | A viewport plus separately sized content/continuation rows | Preserve requested text size where a line fits; recompute wrapping, content height and scroll range | Preserve full content, starting scroll position, end reachability and selection |
| Selectable list row | Row width minus icon, padding and other columns; list owns row pitch and hit areas | Measure wrapped content; grow supported rows and relayout list, or fit within a verified fixed row | Check row height, visible count, scroll range, focus, icons and click targets together |
| Anchored adaptive HUD | Screen anchor, available width and a frame that follows content | Remeasure within anchor limits; grow supported frame/text areas; cap where expansion would collide or leave the screen | Check PC and Xbox HUDs, notifications, changing content and frame state |
| Editable field | Native edit text, caret/selection region and horizontal-scroll contract | Preserve editing behavior; coordinate scale, cursor placement and scrolling | Test insertion, deletion, selection, long input and focus |
| Screen text outside GUI controls | Screen-print position and renderer state; no control box is guaranteed | Keep separate from GUI fitting until its bounding contract is established | Trace overlay/posted-string callers and avoid inventing a caption rectangle |
| Unknown or empty slot | Behavior and native text ownership not yet established | Record and inspect before assigning an automatic fitting policy | Establish whether it draws text, native owner, bounds and intended overflow behavior |

A HUD contains several families. A counter can be a fixed caption, an action
description can be wrapped/adaptive, and a message history can scroll. Likewise,
a list prototype alone does not tell us whether its rows are selectable items or
pieces of a scrolling paragraph. Surface names and font names cannot decide this.

## 2. Generated catalog buckets

The extractor supplies conservative **candidate** groups to make review manageable.
Every generated row starts with `behavior_status=unreviewed`, `native_class=unverified`,
`actual_text_rectangle=unverified`, and no assigned fitting policy. These buckets
are not equivalent to the reviewed behavior families above.

| Candidate bucket | Slots | Basis and limitation |
| --- | ---: | --- |
| HUD slot | 1,034 | Resource name identifies a HUD template; includes many empty/unused variants |
| Unclassified slot | 506 | No supported behavioral conclusion from the definition |
| Control caption | 398 | Button/toggle-like numeric type; actual class and intended wrapping need review |
| List-row template | 80 | Inside `PROTOITEM`; includes selectable rows and description continuations |
| Fixed caption | 39 | Title-like tag; this is a name-based hint, not proof of one-line behavior |
| Body text | 14 | Body-family font outside the above buckets; scrolling/wrapping is not established |

Use the CSV to filter by GUI, prototype owner, group and review status. Never
apply a runtime change merely because a row matched a title tag or body font.
Geometry variants remain in the manifest/corpus; a definition mismatch is flagged
rather than silently merged. Native type numbers are retained without pretending
that a template type proves the concrete C++ class instantiated by the engine.

## 3. Initial review ledger

Dimensions below are template width x height at **1920x1080**, unless explicitly
marked live. A prototype's dimensions are not the final list-row/text dimensions.
Source references name files in the generated archive or current repository.
An unverified failure is never promoted to confirmed by its candidate group.

| ID | Screen/control | Measured definition or source behavior | Evidence status | Family / next action |
| --- | --- | --- | --- | --- |
| T01 | Runtime Text Size and Font title | Live text rectangle 1497 x 47; one centered line; at 98% HD font is 47.04 px; local scale 1 | **Confirmed cause:** centered draw path skips its only line | Fixed caption; local height/width cap before layout and drawing |
| T02 | `optgraphics.gui / LBL_TITLE` | Template 1497 x 47; `dialogfont16x16`, alignment 18; prototype for T01 | Template inspected; its own live screen was not measured for this failure | Candidate fixed caption; verify actual native text rectangle |
| T03 | Runtime font choices and Default/Close | Native options toggles/buttons; caption parameters differ from label parameters | Construction source inspected; text rectangles at maximum size not measured | Candidate control captions; measure caption bounds including toggle art |
| T04 | HUD wrapping reported by user | HUD-associated unnamed label: 828 x 90, two centered lines at 47.04000056 px each; registered `mipc28x6.gui` | **Numeric overflow measured**; exact visible message/event and intended line count still unresolved | Anchored HUD candidate; identify the message before choosing fit versus expansion |
| T05 | `maininterface.gui / LBL_NAME` | Template 741 x 59; menu-family font, centered alignment 18 | Template inspected; not established as T04's failing label | Candidate fixed HUD caption; inspect active variant and live extent |
| T06 | HUD action-description frame | `K1XboxHud.cpp` derives the frame from the description extent while drawing | Source verified; does not prove text layout responds correctly to font preferences | Adaptive HUD candidate; inspect description and frame together |
| T07 | `inventory.gui / LB_ITEMS / PROTOITEM` | Live `CSWGuiInGameItemEntry` name member +0x154: 654 x 76; sampled row extent 746 x 84 | Four of 97 names wrap to two lines needing 94.08000112 px; centered offset -9.04000056 matches leading-line skip condition | Selectable-row candidate; font fitting and native row/scroll/hit layout require separate decisions |
| T08 | `inventory.gui / LB_DESCRIPTION / PROTOITEM` | Live label content 674 x 1458, 14 lines; list viewport 728 x 240 | Native scrollable content geometry captured; interaction not tested | Scrollable body; do not fit an entire description into one viewport |
| T09 | `journal.gui / LB_ITEMS / PROTOITEM` | Template 241 x 57; menu-family font, alignment 18 | Template inspected; no scaling failure asserted | Selectable-row candidate; verify same class/policy as other row types |
| T10 | `journal.gui / LBL_ITEM_DESCRIPTION / PROTOITEM` | Template 237 x 84; body-family font, alignment 9 | Template inspected; no scaling failure asserted | Scrollable-body candidate; verify content rows and scroll range |
| T11 | `dialog.gui / LBL_MESSAGE` | Template 544 x 100; `fnt_d16x16`, alignment 10 | Template inspected; live letterbox/text dimensions may differ | Bounded/adaptive dialogue candidate; establish native sizing and longest lines |
| T12 | `dialog.gui / LB_REPLIES / PROTOITEM` | Four live native-label replies: 1808 x 47, top aligned, `fnt_d16x16b`; unequal-height list mode on | Body-family font assignment live-verified; three visible rows in a 1808 x 141 viewport | Selectable/wrapped rows; preserve native variable-height behavior; multiline and interaction checks pending |
| T13 | `inventory.gui / LBL_CREDITS_VALUE` | Template 255 x 56; menu-family font, alignment 20 | Template inspected; no failure asserted | Compact-caption candidate; test maximum numeric width and alignment |
| T14 | Runtime font previews | Four native labels using four font families | Source inspected; prior 50% live geometry recorded | Bounded sample candidates; inspect wrapping/height at requested limits |

### Native follow-up coverage entries

These extend the file ledger; they are not extra GFF slots to add to 2,071.
Full addresses, build identity and limitations are in the
[native audit](native-text-coverage.md).

| ID | Runtime path/owner | Evidence | Review implication |
| --- | --- | --- | --- |
| T15 | Shared GUI-string factory | Three native callers cover resource loading, initialization and lazy text binding | One common string mechanism can support several owner policies |
| T16 | Specialized inventory/store/upgrade rows | Inventory live sample has name +0x154 and separate +0x324 text, 32 x 28; 41 additional fields populated | Both members need reviewed policies; store/upgrade +0x334 still not sampled |
| T17 | Editable text | `savename.gui / EDITBOX`: constructor-verified `CSWGuiSaveGameEditBox`, editable wrapper +0xE0, 1108 x 57, body-family font | Bounds/ownership captured; caret, selection and long-input scrolling remain untested |
| T18 | Runtime helper/popup fields | Menu census roots 22 additional wrappers needing precise source-slot review | Owners are known; layout policies remain unreviewed |
| T19 | List prototypes | Seven wrappers were absent from the first control-tree pass and found via +0x2CC | Include prototypes separately from displayed row arrays |
| T20 | Tutorial popup | One wrapper recovered after checking a placeholder database class size | Verify size/ownership from code; do not trust database placeholders |
| T21 | GUI-manager background label | Manager +0x7C owns a wrapper outside panel arrays; text was empty | Retain runtime-only/dormant slots; do not mistake them for visible labels |
| T22 | Screen overlays / posted strings | Global native registry and embedded bitmap/grid renderer verified; user-confirmed `whereami` and both coordinate objects captured with bitmap selector active | Separate viewport/grid contract; standard GUI font preferences do not resize this bitmap. Normal expiry/cleanup and other resolutions remain untested; registration is not a draw trace |
| T23 | Height-query contracts and rounding | Fractional draw height differs from rounded height; font-height query omits local scale | Use draw-compatible fitting bounds and verify each consumer contract |
| T24 | Message-history pools | Two native arrays of 64 highlight labels, outside generic control and row arrays | Constructor-verified ownership closes 128 heap candidates; pooled/zero-size does not mean visible |
| T25 | Nested dialogue panel | Cinematic panel +0x1DFC owns `CSWGuiDialogTop`; two-line body text measured at 1824 x 139, bottom aligned | Distinct message bounds/alignment; include ownership without assuming a fixed-caption policy |
| T26 | Combat floating HUD text | Positive native capture: peak six labels, ten observed pointer epochs, later removal; 200 x 47 boxes versus 47.04-pixel lines. User clarified game still paused; visual failure unverified | Existing integer height query rounds down at 98%. Use draw-compatible bounds; one construction sample had zero lines. Script action 526 remains a rejected trigger because it routes to history |
| T27 | Merchant row amounts | Buy: 29 rows / nine populated amounts; Sell: 31 rows / nine populated amounts. Separate +0x324 text has 32 x 28 bounds, bottom alignment 0x22 and 47.04 px line height | Numeric bounds mismatch confirmed; bottom-aligned draw branch can skip its only line. Compact counter inside a selectable row; name-only fitting is insufficient |
| T28 | Upgrade item/component rows | Four item rows and four component rows use native `CSWUpgradeItemEntry`; +0x154 names and distinct +0x334 amounts. One component amount populated at 32 x 28 / 47.04 px | Both members captured; one item name also wraps beyond its 76-pixel box. Assembly, all categories, lightsaber slot variants and interaction remain untested |
| T29 | Container rows and captions | Five item rows; three two-line names in 217 x 84 areas, one populated 32 x 28 amount. One two-line button caption in 345 x 56 | Shared inventory-row and fixed-caption failures measured; do not infer a new rendering mechanism |
| T30 | Workbench target banner | Native MainInterface +0x1758 text: 300 x 47, one centered 47.04-pixel line | Screenshot and live state match the same fractional centered-text omission condition as the title; distinct from notification text |
| T31 | XP/status popup | Active `LBL_XP_DESC`: 849 x 94, one 47.04-pixel line; popup 1031 x 211. Existing adapter derives bounds from font metrics | **Already adaptive in this sample.** Preserve the working adapter; review multiline/screen-height/local-scale limits separately |
| T32 | PC HUD pause notice | Live panel 301 x 345 versus eight menu buttons spanning 579 pixels; reason wraps seven lines in 274 x 329 at 47.04 px per line | Anchored expandable container. User requests menu-row width: derive from live button bounds, rewrap, recalculate height and mouse hit area; keep Xbox layout separate. Implemented 2026-10-17 (`Pause` in `src/controller-native/K1TextLayout.cpp`), not yet play-tested |
| T33 | Top combat-mode banner | During 201 actual combat samples: text present, visible, opaque, two centered lines in 828 x 90; fractional text height 94.08 | Bounded HUD message overflows while active. Default ID 48208 alone is not combat proof; constructor initializes it. Fit/expand against real HUD constraints. Bounded fitting implemented 2026-10-17 (`src/controller-native/K1TextLayout.cpp`), not yet play-tested |

### Correction to earlier font-role wording

The earlier description of the Menus & Replies group claimed dialogue reply
choices as a verified menu-font use. The generated `dialog.gui` explicitly assigns
`fnt_d16x16` to `LB_REPLIES/PROTOITEM/TEXT`, placing that template in the body font
group. At the first inventory pass, the actual reply assignment had not been
measured. The later live dialogue capture now confirms four reply rows request
`fnt_d16x16b`, so replies do use the body group in that conversation. The earlier
semantic claim was too broad. The misleading UI label and behavior remain
unchanged during this audit; renaming the group is a separate feature correction.
The extractor records actual template names rather than inferring fonts from the
screen's purpose. See [the native coverage measurements](native-text-coverage.md)
for capture identities, class/heap comparisons and remaining limits.

## 4. Confirmed title failure and current layout gap

The native evidence was read from clean CD K1 1.03, 4,042,752 bytes, SHA-256
`761f9466f456a83909036baebb5c43167d722387be66e54617ba20a8c49e9886`.
Addresses here are preferred **VA**, with **FILE = VA - 0x400000**. No byte at
these addresses was changed by the investigation. The separate-game module was
111,874,560 bytes, SHA-256
`f0dc43b4e06b9295eeb4ee959e859d8a016a80708f968a7b3477087f3c59f319`.

| Observation | VA / object offset | FILE where applicable | Evidence |
| --- | --- | --- | --- |
| Centered-text placement | 0x0045A922 | 0x0005A922 | Reads float font height, per-string scale and wrapped line count |
| Leading-line skip | 0x0045A960 | 0x0005A960 | A negative centered offset advances past complete leading lines |
| All lines skipped | 0x0045AA2D / 0x0045AA30 | 0x0005AA2D / 0x0005AA30 | Exits drawing when skipped count reaches line count |
| Local string scale | string +0x40 | N/A | Live title scale 1; native line-breaker and draw code both multiply by it |
| Line count / alignment | string +0x38 / +0x46 | N/A | Live title one line; alignment byte 0x12 masks to vertical-center 0x10 |

```text
0045A922 fld   dword ptr [esi+4]    ; font height
0045A925 fmul  dword ptr [ecx+40]   ; local string scale
0045A928 fmul  dword ptr [741838]   ; 100 normalized units to pixels
0045A935 fild  dword ptr [ecx+38]   ; wrapped line count
0045A970 mov   al,byte ptr [edi]    ; advance over a skipped line
0045AA2D cmp   ebx,[ecx+38]        ; skipped count against line count
0045AA30 jge   0045B1D5            ; no remaining lines to draw
```

For this one-line title, `lineHeight = 24 * percentage / 50` and
`centerOffset = (47 - lineHeight) / 2`:

| Requested size | Height | Center offset | Observed / inferred result |
| --- | ---: | ---: | --- |
| 97% | 46.56 px | +0.22 px | User screenshot shows title |
| 98% | 47.04 px | -0.02 px | Screenshot and live state match the line-skip branch conditions |
| 100% | 48 px | -0.5 px | Predicted overflow from the same formula; not a separate traced execution |

The title string remained present, with one wrapped line and valid font/GPU data.
This rules out a missing font or texture in this case. The draw branch was
statically disassembled, not breakpoint-traced. Reusing this explanation for a
particular HUD label or inventory row requires its own live bounds and line count.

Current [reflow code](../src/controller-native/K1RuntimeLayout.cpp) resets fonts
and reapplies the controls' existing extents. Resolution-dependent row geometry
and [engine constants](../src/controller-native/K1RuntimeEngine.cpp) do not acquire
a text-preference multiplier just because font metrics changed. The list-row
placement helper changes horizontal placement/width; it is not a general
text-dependent row-height calculation. Some
[Xbox HUD paths](../src/controller-native/K1XboxHud.cpp) already adjust specific
frames/notices, so describing every HUD label as fixed would also be incorrect.

## 5. Architecture and verification before applying fixes

Use one native text measurement/fitting service, with small adapters for the
reviewed layout families. Runtime inputs must be the actual font, string,
content rectangle, allowed lines and container constraints. The inventory is an
audit and test ledger; it must not become a table of hardcoded per-screen maximum
percentages or coordinates.

Preserve requested font size separately from effective per-string scale. Compute
from the request each time the font, text, dimensions or owning container changes,
so repeated reflow cannot progressively shrink text. The same effective metrics
must drive measurement, wrapping and drawing. For fixed content use a bounded
fit and verify after native rounding. For rows/scrolling text update container
layout and interaction geometry as well. Do not modify shared font data while
fitting one label.

Before marking a family ready, record its native class, actual content insets,
intended line count, scrolling/expansion contract, and at least one tested example
for each distinct native implementation. A numeric GUI type or a matching tag is
insufficient. Unknown entries retain review status rather than inheriting an
unproven fallback. Font-family grouping and layout-family grouping remain separate.

| Verification dimension | Cases needed for each applicable native class |
| --- | --- |
| Font preferences | All three styles; 50% baseline; 97/98 boundary; 100%; mixed group sizes; link/unlink; repeated changes |
| Geometry | Small and large screens; narrow/aspect variants; runtime resolution change; a modified GUI with different insets |
| Content | Long caption; large numeric value; explicit newlines; wrapped message; translated/Override font and strings |
| Containers | First/middle/last row; visible count; scroll start/end; icon space; selection; mouse hit area; controller focus |
| Lifecycle | Open/close/reopen; changed text; font reload; GUI reconstruction; no cumulative shrink or stale wrapped lines |

This is a proposed validation matrix, not a record that these cases have passed.
No new runtime fix, installer or game-file change is part of this inventory work.

## 6. Reproduce and extend the catalog

With generated resources and the documented Python dependencies available:

```powershell
python tools/inventory_text_layout.py --all
python .github/scripts/check_links.py
```

Inspect `build/text-layout-inventory/controls.csv` and `manifest.json`. Confirm
66 archives, 83 GUI files per archive, 2,071 slots per archive for the identified
current corpus. Counts may legitimately change when templates change; review the
new definitions instead of forcing them to match old totals. For a quick single
archive run, omit `--all`; do not describe that as all-resolution coverage.

Independently traverse every GFF struct/list and count its `FONT` fields. Verify
this equals the distinct baseline CSV identities; confirm `ntscpat.gui` is the
only current GUI without font fields. Spot-check T02, T07, T08, T11 and T12 against
their raw `TEXT`, `EXTENT` and `PROTOITEM` definitions. Read actual native text
rectangles for runtime cases before promoting their policies from candidates.
Record new runtime-generated controls in the review ledger even when they have
no direct GFF identity, and add supplied modded GUIs as additional input corpora.
