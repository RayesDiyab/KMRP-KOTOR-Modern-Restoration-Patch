# In-game text size and font: native Windows contract

Reference, 2026-10-17. Follows the [documentation standard](documentation-standard.md).
This describes the current source, locally built resource bank and the limited
separate-game checks below. It does not describe a released installer. The earlier font-timing investigation
is [Override font metrics before first layout](../reverse-engineering/override-font-metrics.md);
the historical font mechanism is in [font scaling](font-scaling.md).

**Evidence boundary:** source inspection, clean-executable byte reads and native
mock tests support the implementation described below. After the opening-crash
correction, the user confirmed the page opens and size increases work. Read-only
inspection verified the live eight-control panel and 50% initial slider state.
The user subsequently confirmed Default works in the two-style build. The user subsequently confirmed that the four grouped sliders, finer adjustments
and Link Text Sizes work in the separate test game. Three-style switching,
screenshots, controller operation and arbitrary GUI/skin compatibility remain
unverified by that check.

A separate test copy subsequently started successfully at 1080p. Read-only
inspection of its native texture registry found three loaded font objects,
`fnt_console`, `dialogfont16x16b` and `fnt_d16x16b`, each with a 24-pixel font
height, matching the 50% default at that size. This verifies startup/loaded
metrics only; it does not establish the new page's rendered result or interaction.

## Build and address convention

The native ABI sample below was read on 2026-10-17 from clean editable CD K1 1.03,
4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
Addresses are preferred **VA**. For this clean input, **FILE = VA - 0x400000**.
The appended-section convention **FILE = VA - 0x492000** belongs to older patched
reference executables; it must not be used for these clean native sites. No new
PE section is introduced by this settings page. Steam runtime execution of the
page and font hook has not been verified by these measurements.

The inspected three-style `build/native-runtime/native-assets.bin` is 111,305,877 bytes,
SHA-256 `6e74fc081da3c46b53a26f0d969b5b45e3243709aa2c7918960e4de5d8aceb45`,
with 67 groups and 3,158 stored objects (header read plus full-file SHA-256).
The former two-style bank was 110,973,461 bytes and 3,147 objects, SHA-256
`de2ac5e84fb1cec395d11f337093456acf4d5779a731e2b8b270b28fef3c7e9d`.
Adding the original artwork increased the bank by 332,416 bytes, once for all sizes.
This identifies the local resource artifact; it is not an identity for a released
module. Its build and test logs are ignored local outputs.

## 1. What the native page does

[K1TextOptions.cpp](../src/controller-native/K1TextOptions.cpp) runs from the
existing `KmrpCoreGuiWorkK1` GUI frame in
[K1NativeJoystick.cpp](../src/controller-native/K1NativeJoystick.cpp).
[K1RuntimeLayout.cpp](../src/controller-native/K1RuntimeLayout.cpp) supplies the
registered live panels and controls, and notifies the page when a panel dies.

The entry is a native button labeled **Text Size and Font** above **Advanced** in
Graphics Options. It is constructed with the native button constructor and
`0x00418D80` using the actual loaded Advanced control as its prototype. It copies
the native visibility, enable and mouse-focus policy, inherits the same column,
width and height, and follows later geometry/focus-policy changes. It requires the
expected graphics-panel and button vtables; an arbitrary replacement class is not
accepted merely because its tag matches.

For Advanced rectangle `(left, top, width, height)`, the entry rectangle is:

```text
(left, top - height - max(2, height / 3), width, height)
```

Integer division is used. For height 30 the gap is 10 and the new top is
`advanced.top - 40`; for height 6 the gap is 2 and the new top is
`advanced.top - 8`. This is inherited native geometry, not a resolution table.
It does not establish that every possible skin leaves that space free.

The custom native panel loads the current `optgraphics` resource as a template.
It binds twenty controls: title, four size labels, four sliders, Link Text Sizes,
three font choices, help label, four preview labels, Defaults and Back. Templates come from `LBL_TITLE`, `LBL_GAMMA`,
`SLI_GAMMA`, `CB_SHADOWS`, `BTN_DEFAULT`, and `BTN_BACK`; geometry also comes
from `LB_DESC` and `BTN_ADVANCED`. The previews pass the unsuffixed bases `dialogfont16x16`, `fnt_d16x16`,
`dialogfont10x10` and `fnt_console` to `SetBaseFont`; the engine selects the
`a`/`b` atlas suffix where applicable.
No additional `.gui` is embedded, and this feature does not rewrite `.gui` files
on disk. Compatibility with third-party graphics layouts is conditional on the
expected live tags/classes/templates and usable geometry; universal compatibility
is unverified.

| Control | Source behavior |
| --- | --- |
| Four text-size sliders | 25% through 100%, in 1-point steps; 76 positions, native maximum index 75 |
| Link Text Sizes | On by default; moving any slider matches all four; re-enabling matches the last changed slider |
| Initial/default size | 50%, exactly the previous actual KMRP size |
| Font choices | `Original Font`, `Original Sharpened Font`, `New HD Font`; exactly one selected |
| Defaults | All four groups 50%, Link Text Sizes on, New HD Font |
| Previews | One native text sample from each font group |
| Back / native B event | Requests native panel close; previous parent focus is restored if still alive |

The [policy](../src/controller-native/K1TextOptionsPolicy.h) clamps requested sizes
to integer percentages in 25..100 without five-point rounding. Slider index
`i` maps to `25 + i`. Thus the percentage is relative to the 50% baseline:
25% is half the previous actual size and 100% is twice it.

### Shared font groups and native slider behavior

The groups follow actual font resource names, as requested by the user. They
cannot separate screen uses that share an atlas. The current generated 1920x1080
GUI pack was inspected for explicit `FONT` fields, excluding `mipc` variants:
730 references use `dialogfont16x16`, 45 use `fnt_d16x16`, 423 use `fnt_console`
(often in empty or art-only controls), and one uses `dialogfont10x10`.
These counts describe that generated pack, not every possible mod.

| Slider label | Font families | Shared uses from those GUI fields |
| --- | --- | --- |
| Menus & Replies | `dialogfont12x16`, `dialogfont16x16`, `dialogfont32x32`, `fnt_galahad14` and fallback | Menu-family text; the label overclaims replies, which used the body family in the live sample |
| Subtitles & Body | `fnt_d*`, `fnt_credits*` | Spoken dialogue/subtitles, live dialogue replies, descriptions, journal and credits |
| Small Text | `dialogfont10x10*` | Small entry text; native low-resolution variants also use this family |
| HUD Text | `fnt_console` | HUD/console-family labels |

Correction from the [text-layout inventory](text-layout-inventory.md), 2026-10-17:
the earlier table claimed dialogue replies as a verified menu-font use. The
generated `dialog.gui` reply prototype explicitly names `fnt_d16x16`, a body
font. The later read-only dialogue capture confirmed four native reply labels use
`fnt_d16x16b`. The UI label remains unchanged during this audit. This is a verified
wording defect, not a change to grouping. Likewise, these are resource-family
groups rather than exclusive screen roles: the captured HUD overflow candidate
uses `dialogfont10x10b`, belonging to Small Text rather than HUD Text. See
[the native coverage reference](native-text-coverage.md) for capture identities
and the boundary between observed controls and untested cases.

Suffix variants stay in the same group. Override fonts are grouped by their
original resource name and keep their artwork and glyphs. Each preview uses one
representative family; this does not exhaust every font in that group.

The native input handler was read from the clean executable identified above.
It subtracts or adds one position and calls the native position setter. Generated
Graphics, Mouse and Sound templates all have maximum 100: brightness, sensitivity
and the four volume sliders. The new text controls retain the same native input
behavior, with 75 intervals representing 25..100%, so one position means
one percentage point. The previous source used 15 intervals and mapped each
position to five percentage points; that mapping caused the reported jumps.

Correction, 2026-10-18: this paragraph said the text sliders also keep the native
**drag**. They did until that day, and dragged with the mouse they stopped at 99%:
the native mouse move (VA `0x00419250`) takes `maximum * (x - left) / width`, rounded
down, from the pointer, while the layout (VA `0x00418F20`) draws the thumb's left
edge at `left + (width - thumb width) * value / maximum`, so the pointer on a thumb
drawn at the end of the track gives 74 of 75. Only a drag carried past the track
reached 100%. Keys and the pad (the decrement and increment below) were not affected.
Each text slider now gets KMRP's copy of the native slider table (VA `0x0073E9D0`,
40 entries) with the mouse move (entry 4) replaced and the left button down (entry 6)
wrapped, so the thumb stays where it was taken and the value is the one it is drawn at,
to the nearest step ([K1SliderGrip.h](../src/controller-native/K1SliderGrip.h)). The
HUD Size page shares it; the measurement, the disassembly and the checks are in
[HUD Size: dragging a slider](hud-size-options.md#dragging-a-slider-with-the-mouse).
These sites are unchanged in the clean executable identified above.

| Native observation, unchanged engine code | VA | FILE | Measured instruction / value |
| --- | --- | --- | --- |
| Decrement slider | 0x0041AE50 | 0x0001AE50 | `dec eax`, current position read from control +0x74 |
| Increment slider | 0x0041AE62 | 0x0001AE62 | `inc eax`, compared against maximum at +0x70 |
| Apply position | 0x0041AE68 | 0x0001AE68 | Calls 0x00417EE0, which clamps to 0..maximum |

Four label/track pairs divide the space from the live brightness label to the
Advanced/Default boundary. Link Text Sizes follows the fourth slider. Font choices
and four previews use the existing description column. Geometry tests cover the
66 generated sizes and four transformed fixtures. A metric-based caption-width
check at 800x600/100% required shortening the body label: `Dialogue & Subtitles`
would occupy 328 pixels in either original style against 300 available. The
chosen `Subtitles & Body` label measures 280 pixels in those styles (224.7 in HD)
and fits that width. This is an advance-width estimate,
not a screenshot or a guarantee for arbitrary replacement fonts.

Changes are queued by callbacks and applied at the next GUI frame. A style change
first materializes the chosen resources. Failure restores the previous preference
and reports it on the page. Font reload retains native texture/font objects;
a style change resets/reloads image state, while a size change reloads metrics.
`KmrpReflowTextK1` recursively resets registered panels' fonts and reapplies each
control's existing extent so native strings re-wrap. Whether every live control
class redraws correctly is not established by the mock tests.

## 2. Native ABI calls and memory changes

These are **sample native calls used by the source**, not new detour sites or a
complete engine ABI specification. Their clean bytes were read directly and
disassembled with Capstone. Methods use the source's x86 `__thiscall` declarations
(ECX is the object); allocation/deallocation use `__cdecl`.

| Purpose in this source | VA | FILE | Measured entry bytes | Treatment |
| --- | --- | --- | --- | --- |
| Panel construction | 0x0040B570 | 0x0000B570 | `6A FF 68 9E 47 71 00` | Called; unchanged |
| Append panel control | 0x0040B9A0 | 0x0000B9A0 | `53 8B 5C 24 08 56` | Called; unchanged |
| Button construction | 0x0041C0F0 | 0x0001C0F0 | `6A FF 68 31 53 71 00` | Called; unchanged |
| Initialize from button prototype | 0x00418D80 | 0x00018D80 | `8B 44 24 08 8B 11` | Called; unchanged |
| Slider maximum | 0x00417EC0 | 0x00017EC0 | `8B 44 24 04 39 41 70` | Called with 75; unchanged |
| Slider position | 0x00417EE0 | 0x00017EE0 | `8B 44 24 04 85 C0` | Called with 0..75; unchanged |
| Add native event callback | 0x0041AB20 | 0x0001AB20 | `53 56 8B 71 3C` | Called; unchanged |
| Set panel focus | 0x0040A630 | 0x0000A630 | `56 8B 74 24 08` | Called; unchanged |
| Existing early font-timing detour | 0x00422CC1 | 0x00022CC1 | `8B 8C 24 14 20 00 00` | 7-byte guarded KPM detour; original instruction replayed |

```text
00418D80 mov eax,[esp+8]         ; native prototype argument read
00418D84 mov edx,[ecx]           ; destination object's vtable
00417EC0 mov eax,[esp+4]         ; requested slider maximum
00417EC4 cmp [ecx+70],eax        ; native slider maximum field
00422CC1 mov ecx,[esp+2014]      ; replayed loader epilogue instruction
00422CC8 pop edi                ; texture owner still in EDI at hook entry
```

The settings page adds **zero native hook sites** beyond the earlier font-timing
hook already specified in
[kotor1-native-runtime.hooks.toml](../src/controller-native/kotor1-native-runtime.hooks.toml).
It uses existing frame/layout notifications, native callbacks and an allocated
panel-local vtable. That table copies 27 base-panel slots from VA `0x0073E010`,
then replaces slots 0 (destructor), 15 (input) and 21 (B action). The loaded
graphics/button vtable checks are VA `0x007586F8` / `0x0073E658`. Since 2026-10-18
each of the four sliders also points at a module-owned copy of the native slider
table, VA `0x0073E9D0`, 40 slots, with slot 4 (mouse move, `0x00419250`) replaced and
slot 6 (left button down, `0x004191D0`) wrapped; a slider whose table is not
`0x0073E9D0` is left alone. That is an in-memory pointer, not a hook site
([HUD Size: dragging a slider](hud-size-options.md#dragging-a-slider-with-the-mouse)).

| In-memory state | Source treatment |
| --- | --- |
| Panel +0x20/+0x24 | Native control array/count; IDs equal appended array indices, including holes |
| Control +0x04 | Extent set through native virtual SetExtent |
| Control +0x44 | Inherit native entry policy; modal close requests set native close-state bits |
| Control +0x50 | Unique control ID |
| Control +0x5C/+0x60/+0x64/+0x68 | Native up/left/down/right neighbors |
| Slider +0x74 | Native position sampled each frame |
| Panel +0x1C | Previous native focus recorded/restored while parent remains registered |

Destruction removes a modal from its manager, clears native focus and array
references, destroys owned controls, and clears retained pointers. Parent
removal queues the modal's close. The entry is removed/destroyed when its parent
is destroyed. These ownership paths are covered with mocked ABI functions.

A two-frame release guard prevents the initiating confirm press from immediately
acting on the new page and prevents reopening after close. While waiting for the opening press to end, held mouse left,
Return and Space reset the counter. If `kmrp-controller.dll` is loaded, the page
optionally resolves its read-only `KmrpControllerConfirmHeldK1` export; a held
controller confirm also resets the counter. Missing controller support is allowed.
This query does not dispatch input or add a controller hook. Native B input
closes directly; the Back button and other guarded callbacks require two observed
released GUI frames after opening. Once armed, the guard stays armed for later
clicks/confirm presses until the next open/close transition. The controller query
and actual input timing still require a game play-test.

## 3. Font resources, metrics and preserved Override ownership

[build_native_assets.py](../tools/build_native_assets.py) skips all 36 named
font `.tga`/`.txi` files from the offline resolution/common archives. It stores
18 font pairs for each of three styles in the common group under private names
`kmrfhd00..17`, `kmrfpc00..17` and `kmrfog00..17`. **The bank has no per-resolution font atlas
sets.** Historical offline archives still contain their previous fonts for
comparison. The runtime uses one shared source per font/style at every size.

HD art is the existing 3x source in `assets/hd-fonts`.
That source was re-baked on 2026-10-18 (uncommitted at the time of writing),
after the converter was found to draw the face's missing-glyph box in slots 0x80
to 0x9F and in every control-code slot; the latter put two vertical lines after
"HUD:" on this page. See
[font scaling](font-scaling.md#what-each-slot-holds-and-the-2026-10-18-re-bake).
The bank identity in "Build and address convention" predates the re-bake, so a
bank built since has different HD font objects and a different hash; the new
hash was not read for this note, and the fix has not yet been seen in game.
[build_original_fonts.py](../tools/build_original_fonts.py) creates original-PC
art at build time from all 18 resources in the supplied GUI texture pack.
Original Font preserves their RGBA pixels and original atlas dimensions, then
uses the engine to scale them. Original Sharpened uses
4x Lanczos alpha enlargement followed by the steepness-7 coverage curve documented
in the script. RGB is white and coverage is alpha. The upstream comparison is
identified by the script as `jryantomes/kmdlswap`, commit `31bd877`; that comparison
is corroboration for the sharpening algorithm, not engine ABI evidence.
There is no runtime rasterizer, glyph synthesis or font installation.

Two resource names, `fnt_d10x10b` and `fnt_d16x16`, receive a grid metadata repair.
Both measured raw resources are identical and share the **single accepted hash**
`9e0c0819c16b2a1bb6170e5973ffc4e58740eaaf741d2a3a5fbb8e70e728375b`.
For these two names any other hash is rejected, as are unexpected 512x512 source
atlas dimensions. The repair uses existing 32x19 cells, 16 columns and 256 glyph
entries, derives advances from alpha bounds, and keeps a positive blank advance.
It does not invent glyph pixels. This guard is not a general repair for unknown
font packs, nor a hash check on every other font resource.

[K1RuntimeAssets.cpp](../src/controller-native/K1RuntimeAssets.cpp) uses HD metrics
as the baseline for all three styles. For shared HD `fontheight` H and screen height h:

```text
p = lround(H * 100)
s = floor((max(720, h) * 1000000 + 360) / 720)
baseline = round_half_even(p * s / 3000000) / 100
target = baseline * sizePercent / 50
```

The six-decimal scale and half-even pixel rounding preserve the former baker's
results, including the 1050p rounding case. `fontheight`, `baselineheight`,
`texturewidth`, `spacingR` and `spacingB` are scaled together. Glyph UVs stay
unchanged when size changes. Example computed by `shared_font_txi` from
`fnt_d16x16b` H=0.48:

| Screen height | 25% target | 50% baseline | 100% target |
| --- | --- | --- | --- |
| 600 or 720 | 0.08 | 0.16 | 0.32 |
| 1050 | 0.115 | 0.23 | 0.46 |
| 1080 | 0.12 | 0.24 | 0.48 |
| 1200 | 0.135 | 0.27 | 0.54 |
| 1440 | 0.16 | 0.32 | 0.64 |
| 2160 | 0.24 | 0.48 | 0.96 |

Resources are materialized in KMRP's private cache. Existing Override font files
retain priority and are not rewritten or deleted. Style switching skips font
names with an Override `.tga`, `.tpc` or `.txi`. Their loaded native metrics can
still follow the size preference: the early `0x00422CC1` callback receives the
texture in EDI after loose/embedded metadata parsing and before first layout.
It scales CAurFontInfo fields +0x04 through +0x14, then assigns exact target
fontheight to make repeated notification idempotent. It preserves UVs, pointers,
glyph texture bytes and source files; null/unknown/invalid cases return unchanged.
See the earlier timing reference for the complete hook proof and guards.

## 4. Saved preferences and limits

The game executable's directory determines `swkotor.ini`; preferences are separate
from the patch's install options:

```ini
[KMRP Text]
Size=50
MenuSize=50
BodySize=50
SmallSize=50
HudSize=50
LinkSizes=1
FontStyle=0
OriginalFont=0
```

`FontStyle=0` selects New HD, `1` Original Sharpened, and `2` Original.
If the new key is missing, legacy `OriginalFont=0` maps to New HD and nonzero maps
to Original Sharpened. The legacy key is still written (`0` for HD, `1` for either
original style). Missing settings use 50/HD; invalid style IDs use HD. `Size` is retained for older builds. Missing group keys inherit it. The four
group keys are clamped to 25..100 without five-point rounding. `LinkSizes` defaults
to 1; when loading linked settings, all groups match MenuSize. During the session,
re-linking matches the most recently changed group. Its anchor is not persisted. Save uses the Windows profile API
after applying a change. A failed save leaves the session updated and displays a
writability message. A failed style application restores the old selection.
These paths are implemented; real INI-permission failure presentation is untested.

Large text is allowed within the fixed native screen geometry. The source does
not promise that every label, list, translated string or modded skin fits at
100%. Each preview demonstrates only one representative font. English captions are
literal source strings, not new talk-table localization entries. Changes to
Override during a running session are outside the existing resource-listing
contract; see the runtime resource implementation.

## 5. Verification and rejected alternatives

The current implementation's integration checks report:

| Check | Coverage and result | What it does not establish |
| --- | --- | --- |
| `Test-TextOptions.py` + production-source native mock harness | 70 fixtures: 66 generated Graphics layouts plus four transformed layouts; cloned geometry/focus, IDs, navigation links, 20 controls, default captions, independent/linked changes, all 76 percentage positions, precise saved values, actions, style failure rollback, held-confirm reopen guard and cleanup pass | Native engine ABI execution, rendering, real controller navigation or arbitrary skins. The slider table swap: the harness has no engine table to copy, so the call is compiled out under `KMRP_TEXT_OPTIONS_TEST` |
| `Test-HudOptions.py` (the shared drag, `DragValue` in `K1SliderGrip.h`) | Maxima 75, 100 and 10, every travel from twice the maximum to 3000 px: both ends, every step, and the value of every drawn thumb position given back. Passed 2026-10-18 | The engine calls in the replaced entries; a drag on this page in the game |
| Previous default metrics comparison | All 1,188 heights (66 sizes x 18 fonts) equal the historical archive values | Visual identity of every string/layout |
| Original atlas comparison | Alpha pixels of 16 non-repaired resources exactly match the local upstream comparison fixture | RGB equality, the two intentionally repaired metadata grids, or runtime appearance |
| `Test-OverrideFontMetrics.py` | 11,880 original/translation-font cases, including 2,376 mixed-group cases; first use, reload, round trip, no compounded scaling, UV/pointer/texture preservation and invalid guards pass | New page execution in the game |
| `Test-NativeAssetsBank.py` | Current bank log: all 3,158 objects decompress to their keys; six sample sets reproduce 4,835 omitted files exactly; all checks pass | Every omitted file regenerated for all 66 sizes unless run with `--all` |

The inspected fixture files contain 70 GUI rows and 1,188 metric rows; the bank
identity/counts above were independently read from the built file. Test assertions
are reproducible from the scripts below. The limited live observations and
failures are recorded in the corrections below. Mocked native calls are not a
substitute for a game screenshot or mouse/keyboard/controller play-test.

Deliberately rejected approaches are a fixed-resolution replacement Graphics GUI,
a per-resolution atlas bank for this feature, and runtime font rasterization.
The implemented page inherits native templates and geometry; the bank shares art
and adjusts native metrics. Moving Override scaling to a later GUI frame was
previously rejected because first layout could cache old line breaks before the
metrics changed; the early loader hook fixes that timing.

### Correction: opening-page crash, 2026-10-17

The first separate-game play-test crashed while opening Text Size and Font.
Windows event 1000 and the saved minidump identify an access violation reading
address `0x24` at VA `0x0045A321`: the line breaker had a null font-info pointer
in EDI. The stack contains `SetBaseFont` returning at `0x00415DE7`, KMRP's
`MakeScreen` call at module RVA `0x26F57`, and the requested name
`fnt_d16x16bb`. The loaded KMRP module for that crash was SHA-256
`69894bc4cb31c50e46dffdb22960d1b2a2bcfe229b24b3ede627e5527e92b36f`.

The preview incorrectly supplied `fnt_d16x16b` as a **base** font name.
`SetBaseFont` calls `ResetFont`, which asks `GetUpdatedFontName` to append the
native resolution/font-option suffix. The resulting atlas did not exist. This
was a preview-name bug before slider/style interaction; it is not evidence of a
fault in dynamic scaling. The correction supplies `fnt_d16x16` and lets the
engine choose a valid variant.

| Measured native site | VA | FILE | Observation |
| --- | --- | --- | --- |
| SetBaseFont | 0x00415DD0 | 0x00015DD0 | Saves the supplied base, then calls ResetFont at 0x00415DE2 |
| ResetFont suffix selection | 0x00415D85 | 0x00015D85 | Calls GetUpdatedFontName with a copy of the base |
| Normal large-width suffix | 0x0040B3D8 | 0x0000B3D8 | Writes `b` after the supplied name, then a null byte |
| Font-info dereference | 0x0045A321 | 0x0005A321 | Reads `[edi+0x24]`; crash dump EDI was zero |

The previous mock's SetBaseFont was a no-op and could not catch this error.
Its replacement checks the unsuffixed argument on both page creations in all
70 fixtures and models both suffix outcomes. The new assertion failed against
the crashing source and passes with the correction. This is regression coverage
for the measured cause, not a replacement for repeating the real page test.
The corrected build was installed only to the separate test copy. The user then
confirmed the page opens. Read-only process inspection found a live custom panel
with eight controls, slider index 5 of maximum 15 (50%), and valid
`fnt_d16x16b` font info at 24 pixels. The installed module for this retest is
SHA-256 `9c3e64accf5a3377e27daac07eb9ac73f59e14c0e45f8ee27bf90a64f048e49f`.
This verifies opening and initial native state; slider/style interaction and
rendered appearance remain pending.

### Correction: toggle and Default blocked by their own press

After the preview correction, the user reported that size changes work, while
font toggle and Default do not. The guard was resetting `releasedFrames` to zero
on every held confirm, including a subsequent button press. `Toggle`, `Defaults`
and `Back` then rejected that press because `Armed()` was false.

The guard now latches after the opening press has ended and two released GUI
frames have been observed. Subsequent presses may run their callbacks while
held. Opening/destruction resets the counter, preserving protection against
click-through and reopening from held confirm. Native B still closes directly.
The new regression models held opening confirm, release, and fresh held presses:
it fails on the previous source at the toggle assertion and passes on the
corrected source across all 70 fixtures, including Default and held-close
reopen checks. The earlier mock tests invoked button callbacks while confirm
was released, so they did not cover this sequence. The corrected module, SHA-256
`b28ef093e980e355524f4fdca718e071591ab028c5f380ab287adde81bd82bec`,
was installed only to the separate test copy. Real button retest is pending.

### Correction: solid glyph rectangles after changing style

The next separate-game check reached the font-toggle callback (`OriginalFont=1`
and size 70 were saved), but the user screenshot showed solid colored rectangles
in place of glyphs. Read-only inspection of all three loaded font objects found
valid metrics (33.6 pixels, matching 24 * 70 / 50) and decoded CPU images, but no
GPU texture array or primary GL ID. Field +0xE8 also contained `0xFFFFFFFF`,
but that value alone is not evidence of a missing GPU texture (see correction below).
The failing module was SHA-256
`b28ef093e980e355524f4fdca718e071591ab028c5f380ab287adde81bd82bec`.

| Observed member, relative to each native texture | Value after failed switch | Meaning established from native disassembly |
| --- | --- | --- |
| +0x44 | Non-null CPU image pointer | ConstructImage decoded pixels |
| +0xE0 | 1 | CPU image constructed |
| +0x40 | null | No allocated GL texture-ID array |
| +0x58 | 0 | No primary GL texture ID |
| +0xE8 | 0xFFFFFFFF | Meaning not established; working font objects also have this value |

Correction to the initial live reading: +0xE8 was initially described as a
last-bound GL ID. A later running-game snapshot found valid non-null +0x40 arrays
and +0x58 IDs 35/29/28 while +0xE8 remained `0xFFFFFFFF`. That interpretation
was unsupported and is rejected. The failed upload is established by the missing
+0x40 arrays and zero +0x58 IDs, not by +0xE8. The mock now checks those measured
GPU fields only.

The previous reload stopped at `ConstructImage`. That method constructs CPU
pixels; it does not complete the GPU upload. The correction enqueues each loaded,
recognized GUI font into the engine's ordinary refresh queue, then drains it once
before reflow. Size-only changes still reload only metrics.

| Native operation | VA | FILE | Use / measured call chain |
| --- | --- | --- | --- |
| Refresh-list append | 0x0046BD10 | 0x0006BD10 | Thiscall on the list at VA 0x007A4770 with the texture argument; same idiom as native texture creation |
| AurTextureBuildAndStoreAll | 0x004217F0 | 0x000217F0 | Cdecl, no arguments; drains the list, updates texture-ID registry and maximum ID |
| BuildAndStoreTexture | 0x004216A0 | 0x000216A0 | Called for each queued texture; constructs CPU pixels if needed |
| Store image | 0x00420970 | 0x00020970 | Called from 0x004216EC; allocates IDs and uploads the image |

The texture registry may also contain non-font metadata at +0x38 (observed for
`NormCubeMap`), so the reload now filters the 18 canonical GUI font resource names
through the runtime asset module's existing name list. It no longer treats every
non-null metadata pointer as a font.

The extended native mock distinguishes CPU decode from GPU upload, invalidates
IDs on reset, and requires a valid texture after style switch. It fails on the
previous source and passes all 70 fixtures with the queued build. A non-font
metadata fixture verifies it is excluded. The early-metric regression still
passes all 9,504 original/translation cases. Corrected GPU upload in the running
game remains pending its separate retest.

### Three mutually exclusive native font choices

At the user's request, the cycling button is replaced with three native round
options rows. From top to bottom: Original Font, Original Sharpened Font, New HD
Font. Their column, width, row height and starting position come from the live
resolution button; the gap is `max(2, rowHeight / 3)`. Help starts below the rows.

Each row uses the current Graphics `CB_SHADOWS` template and the native options
checkbox constructor. Its automatic toggle event is set to -1, so clicking the
selected row cannot clear it. Callbacks explicitly choose a style and the group
sets exactly one selected flag. Native up/down navigation joins all three rows
to the slider and Defaults/Back. Default still selects 50% and New HD.

| Native operation / member | VA or offset | FILE, where applicable | Measured contract |
| --- | --- | --- | --- |
| Options checkbox constructor | 0x006E00D0 | 0x002E00D0 | Calls toggle constructor then assigns vtable 0x00758258 |
| Options checkbox object | size 0x2B4 | N/A | Address database size; constructor chain and native member offsets corroborate |
| SetSelected | 0x00685540 | 0x00285540 | Thiscall, 4-byte argument; changes bit 0 of control +0x1C8 |
| Automatic toggle event | control +0x1C4 | N/A | HandleInputEvent at 0x0041ADBD compares this to the incoming event before flipping bit 0 |

The 70 native mock fixtures cover all three choices, re-selecting the current
choice without reload, exactly-one selection, row geometry, Default, rollback,
held presses and legacy/new preference round trips. Pixel comparison against the
supplied game pack verifies all 18 Original Font RGBA atlases at their original
dimensions. The shared bank now contains all three styles without resolution
copies; font sizing still changes native metrics only. Both original-art styles
retain the guarded two-resource metadata repair described above.

The three-choice module installed to the separate test copy is SHA-256
`d67d8f3e98257245ebbd7207b687006947e2ecd2064cd74a7165cd00096593a6`.
Its real selection/rendering check is pending. The earlier two-style build's
Default was reported working by the user; that does not establish this new
selector's runtime behavior.

### Four grouped sliders: separate-game check, 2026-10-17

The user reported that fine adjustments and turning Link Text Sizes off and on
work, then left the page open. Read-only process inspection at 1920x1080 found
20 controls, four sliders each at index25/maximum75 (50%), Link selected, and
exactly one font option selected (New HD). Four representative font objects were
loaded: `fnt_console`, `dialogfont16x16b`, `dialogfont10x10b`, `fnt_d16x16b`.
Each had 24-pixel metrics, non-null GPU arrays at +0x40 and nonzero GL IDs at +0x58.
This snapshot establishes current live state; the reported interactions are user
observations, not a captured transition trace or a controller test.

The installer rebuilt from this source is 129,066,496 bytes, SHA-256
`a02bc9f611cbc0f4f1a2cd5ae112bf8340bff397372dba3e2887ed878984d79f`.
The final `Test-InstallerPatch.ps1` run passed install, option preservation,
High FPS and restore cases. The core package's DLL was read back and equals the
installed test DLL. This proves packaging identity, not additional game behavior.

The single-file test module is 111,874,560 bytes, SHA-256
`f0dc43b4e06b9295eeb4ee959e859d8a016a80708f968a7b3477087f3c59f319`.
The prior `d67d8f3e...` module was copied aside before replacement. The separate
game executable was unchanged. This was installed only into the isolated test
copy, not the Steam installation. Tests of switching all three styles, other
resolutions/skins and translations in game remain separate checks.

## 6. What is deliberately not changed

The settings page adds no executable on-disk writes, hook sites, `.gui` resource,
installer resolution choice, or dependency on the controller patch. It retains
the actual previous font size at 50%. Override font files and glyph resources
remain owned by the player/mod that supplied them. Native engine control
construction, events, focus and wrapping remain the mechanisms used by this page;
since 2026-10-18 the sliders' mouse drag is KMRP's, and their keys and pad stepping
stay native. Sliders on other pages (brightness, sensitivity, volumes) keep the
native drag.
Other scaling subsystems and macOS behavior are outside this implementation.

## 7. Verifying by hand

From the repository root with the documented Python dependencies and MSVC x86
build environment, build resources/module through the normal project workflow,
then run:

```powershell
python testing/regression/Test-TextOptions.py
python testing/regression/Test-HudOptions.py
python testing/regression/Test-OverrideFontMetrics.py
python testing/regression/Test-NativeAssetsBank.py
python .github/scripts/check_links.py
```

The original-font alpha comparison is conditional on the local upstream fixture
`build/font-comparison-2026-10-17/original-pc`; check the printed comparison count
is 16. Without that fixture the test can pass with zero comparisons. The native
bank test defaults to six sample sets; use `--all` for all-set reconstruction.
These tests build ignored test artifacts and do not install or launch the game.

For clean-byte verification, check the executable length/hash above, read each
ABI sample at its FILE offset, and disassemble the loader span
FILE `0x22AF0..0x22CDB`. Confirm the seven guarded bytes at FILE `0x22CC1`, texture
ownership in EDI, and replay before return. Read the bank's little-endian counts
at offset 8 (67 groups, 3,158 objects for the identified artifact) and hash the
entire bank. Inspect common-group `kmrfhd`/`kmrfpc`/`kmrfog` names and absence of original
font names in every resolution group; the bank regression checks that contract.

The remaining manual check requires an explicitly installed test build: open
Graphics Options, inspect the new entry and page, use all four sliders, turn Link Text Sizes off and on, and use all three styles,
restore defaults, reopen, reload resolution, and restart to check persistence.
Repeat with mouse/keyboard and controller, held confirm through close, modified
Graphics skins and representative Override fonts. Capture screenshots at named
resolutions and record the module/bank hashes. Until those observations exist,
live rendering and universal GUI/controller claims remain unverified.
