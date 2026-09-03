# Font & Dialogue-Layout Reverse-Engineering Notes

**See also `font-atlases.md`** for the later HD-font-atlas work: the 18 font
resrefs, the packed/proportional atlas format, the "one texel per pixel"
rendering rule, and which resref renders which screen (in progress).

## Scope

This covers the font-size and dialogue-letterbox investigation that followed
the map patch (see `map.md`). Goal: KOTOR renders UI/dialogue text at a fixed
pixel size regardless of resolution, so it is tiny at 3440x1440 and above.
Reference material: the third-party Kotor Patch Manager patch set at
`https://github.com/J0-o/KotorUniResPatch` ("2x Font", "2x List Item Height",
"Scaled Letterbox"). Its addresses and byte sequences were independently
re-verified against our own copy of the same clean executable before use —
its `manifest.toml` targets `kotor1_cdcrack_103` with SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`, identical
to this project's `SourceHash`.

## CAurFontInfo structure

Confirmed live (breakpoint on `CAurGUIStringInternal::Draw`, main-menu label
font instance): fields are small **normalized floats**, not raw pixel values.
A sampled instance read `fontHeight = baselineHeight ≈ 0.16`,
`textureWidth ≈ 2.56`, `spacingR = spacingB = 0.0`.

| Offset | Field | Type |
| --- | --- | --- |
| `+0x04` | fontHeight | float |
| `+0x08` | baselineHeight | float |
| `+0x0C` | textureWidth | float |
| `+0x10` | spacingR | float |
| `+0x14` | spacingB | float |

`CAurFont::GetFontPixelHeight` (`0x00459610`) confirms the unit conversion:
`mov ecx,[ecx+0x18]; mov eax,[ecx]; call [eax+0x38]; fld [eax+0x04]; fmul
[0x00741838]; fadd [0x0073E9AC]` — i.e. `pixelHeight = fontHeight * 100.0 +
0.5`. `0x00741838` = `100.0f` and `0x0073E9AC` = `0.5f` are fixed unit-scale
constants (percent-to-pixel conversion with round-to-nearest bias), **not**
resolution-dependent levers — do not repurpose them as a scaling hook.

## Key functions

- `0x004A1770`: `CAurFont::TextOutA`. `ecx` = `CAurFont*`. Reads
  `CAurFontInfo*` directly from `[ecx+0x18]`. 13-byte SEH prologue:
  `6A FF 68 5C 7E 71 00 64 A1 00 00 00 00`.
- `0x0045A850`: `CAurGUIStringInternal::Draw`. `ecx` = the GUI-string object.
  `[ecx+0x18]` holds a "safe pointer" whose vtable slot `+0x38` resolves to
  the same `CAurFontInfo*`. 7-byte prologue: `83 EC 4C 89 4C 24 04`.
- `0x00459610`: `CAurFont::GetFontPixelHeight` (read-only reference, not
  hooked — see unit-conversion note above).
- `0x0041EFA0` (and identical-shape neighbors at `0x0041EFC0`, `0x0041EFE0`):
  **not** a font constructor/loader. This is a generic, compiler-generated
  template thunk ("resolve safe-pointer, return field at fixed offset")
  reused all over the engine for unrelated offsets (`+0x38`, `+0x44`,
  `+0x78`). A dead end for finding a one-time font-load hook point — see
  Known unknowns.
- `0x00417992`: generic composite list-row setup, shared by the save/load
  list, journal quest list, and the graphics resolution popup rows. Original
  10 bytes: `8B 40 0C 89 41 0C 8B 4C 24 6C` (`mov eax,[eax+0x0C]; mov
  [ecx+0x0C],eax; mov ecx,[esp+0x6C]`) — copies a row-height field verbatim
  with no scaling.
- Nine dialogue-letterbox/reply-box call sites at `0x006A74D2`, `0x006A7560`,
  `0x006A7943`, `0x006A7B59`, `0x006A7F3D`, `0x006A8C4C`, `0x006A7CD0`,
  `0x006A8E1D`, `0x006A7F71` (see Letterbox section).

## Confirmed patch: font scale (candidate 001/002)

`tools/build_font_scale_wrapper.py` adds a new `.kfs` PE section
(`code|execute|read|write`, unlike the read-only `.kui` map section, because
it holds mutable state). Layout: `+0x000` scale constant (float32),
`+0x004` dedup count (uint32), `+0x008` 64-slot pointer dedup table,
`+0x108` shared `scale_fontinfo` subroutine, followed by the `TextOutA` and
`Draw` hook stubs.

Both hooks are trampolines: overwrite the function's own prologue with a
5-byte `E9` jump (NOP-padded to the original prologue length), landing in a
stub that (a) recovers the `CAurFontInfo*` the same way the original code
would, (b) calls `scale_fontinfo`, (c) re-executes the original prologue
bytes verbatim, (d) jumps back to resume normal execution immediately after
the hooked bytes.

`scale_fontinfo(eax=CAurFontInfo*)` is required because both hook functions
fire every rendered frame and `CAurFontInfo` instances are shared/persistent
(mutated in place) — without de-duplication the fields would be multiplied
again on every call and grow without bound within seconds. It linear-scans
the 64-slot pointer table; if the pointer is already present it does
nothing; otherwise (bounded by `MaxTrackedFontInfos = 64`, matching KPM's own
cache size) it records the pointer and multiplies all five fields by the
embedded scale constant via `fld`/`fmul`/`fstp`.

A third hook (`0x00417992`, list-row height) reuses the *same* embedded
scale constant via `fild`/`fmul`/`fistp` on the integer height value, so the
list-row fix always stays proportional to whatever scale the font hooks use
— there is a single source of truth for the scale factor, not two
independently-tunable values.

Verified live at 3440x1440, scale=2.0: main menu, HUD, load-game list, equip,
inventory, character sheet, powers, skills, store, dialogue-choice list, a
map confirm popup, and multiple dialogue/subtitle screens all render text
correctly sized with no garbling and no runaway growth (confirms the dedup
table works in practice, not just in theory).

## Confirmed patch: dialogue letterbox (candidate 003)

Root cause: vanilla derives the dialogue letterbox bar height from screen
**width**: `barHeight = round((screenHeight - round(screenWidth * scale)) *
0.5)`, using an aspect-scalar float at `0x00755788` (a second one at
`0x00755AE4` for one call site). At ultrawide, `screenWidth * scale`
approaches or exceeds `screenHeight`, so the bar becomes tiny — independent
of the font-scale patch; the bigger font just made the pre-existing
undersized bar's clipping/occasional-non-display visible.

Fix (from KPM's "Scaled Letterbox", re-verified against our exe): 9 call
sites replaced with a height-derived formula, `barHeight = round(screenHeight
/ 6)`, computed via `(field + 3) / 6` integer division (classic
add-half-divisor rounding). `tools/build_letterbox_scale_wrapper.py`
implements all 9. Seven replacements are the same length or shorter than
what they replace and are patched in place with trailing NOPs. Two are
longer and need a trampoline into a new `.klb` PE section:

- `0x006A7CD0` (`CSWGuiDialog::SetRect`, sizes `LB_REPLIES`) — original 28
  bytes, replacement 58 bytes.
- `0x006A8E1D` (`CSWGuiDialogCinematic::SetReplies`) — original 9 bytes,
  replacement 42 bytes. This one has an internal conditional branch that
  uses a `push addr; ret` idiom to jump to a *different* address
  (`0x006A8E75`) than the trampoline's own resume point
  (`0x006A8E1D + 9 = 0x006A8E26`), for one of its two paths. Both
  destinations were manually traced against the original `test/je` logic
  and confirmed correct before shipping — do not "simplify" this stub
  without re-deriving the branch.

Verified live at 3440x1440: dialogue subtitle text and the numbered
reply-choice list both render without bottom-clipping, and no further
non-display reports after this candidate (earlier candidates showed
intermittent failure to display and descender clipping — e.g. the tail of
'y' cut off).

## GUI positioning fix: `computer.gui` (data-side, not an executable patch)

Separately from the executable hooks above: the computer-terminal screen
(`Override/computer.gui`) uses `LB_MESSAGE`/`LB_REPLIES` listboxes and a
`LBL_OBSCURE` stat-panel background whose `EXTENT` fields were authored
without ever being corrected for the 3440x1440 "gold" build (unlike 16 other
`.gui` files already listed in `GOLD_GEOMETRY_TEMPLATES`). All controls
appeared shifted left of the terminal prop's actual on-screen position. The
user manually repositioned/resized every control in a KOTOR GUI editor; the
result was not a uniform pixel shift — some controls (`LBL_STATIC1`,
`LB_MESSAGE`) kept nearly the same center while shrinking in width, while
others (`LBL_OBSCURE`, the stat-label cluster) shifted their center by
roughly 100px. This is exactly the shape of correction
`tools/transfer_gold_gui_geometry.py` already exists to propagate (per-field
ratio transfer, not a rigid translation), so `computer.gui` was added to
`GOLD_GEOMETRY_TEMPLATES` in `tools/prepare_universal_resources.py` and the
edited file became the new `assets/override-3440x1440/computer.gui`.
Verified by transferring onto a 1920x1080 target and confirming every
control still lands fully on-screen with the same proportional correction.

`computercamera.gui` (the security-camera hacking screen) likely has the
same class of issue but has not been reported or investigated.

## Proven vs empirical

**Proven by direct disassembly/live memory reads against our own exe copy:**
all addresses and byte sequences above; the `CAurFontInfo` field layout and
its normalized-float representation; the `GetFontPixelHeight` unit-conversion
formula; the vanilla letterbox width-based formula and its ultrawide failure
mode.

**Empirical, KPM-authored tuning values, not derived from first principles:**
the `screenHeight / 6` letterbox ratio; the 64-slot dedup table size
(sufficient in observed play so far — main-menu labels alone reuse a single
`CAurFontInfo*` instance across many draw calls, so the true number of
distinct font objects in the game may be much smaller than 64, but this has
not been enumerated).

**Resolution-aware scale formula — now established** (was "not yet derived"):
`max(1.0, height / 720)`, i.e. 1.00x at 720p, 1.50x at 1080p, 2.00x at 1440p,
3.00x at 2160p. Chosen with the user against real screenshots, not derived from
first principles — an earlier `- 0.25` offset gave 1.75x/2.75x at 1440p/2160p,
which play-tested too small. It lives in **two** places that must stay in
step: `font_scale_for` in `tools/prepare_universal_resources.py` (atlas TXI
metrics) and `ResolutionPatch.ScaleForHeight` in
`src/patcher/KmrpPatcher.cs` (list-row heights).

## Known unknowns

- How many distinct `CAurFontInfo` instances/font "classes" the game
  actually uses across all screens (only observed: one shared instance for
  main-menu labels; dialogue/subtitle text has not been sampled the same
  way).
- Whether `CAurFont::TextOutA` is reached by any screen that was actually
  play-tested this session — it recorded zero hits at the main menu; its
  actual invocation path is still unconfirmed.
- Cross-resolution validation: every fix in this file has only been
  confirmed by direct play at 3440x1440. The `computer.gui` transfer was
  checked for structural sanity (no off-screen controls) at 1920x1080 but
  not play-tested there.
- ~~The three executable hooks are not part of the shipped gold delta.~~
  **Resolved** — all are in the gold snapshot
  (`swkotor_gold_v6_wrapfix.exe`), together with a fourth fix found later: the
  word-wrap forward-progress patch at `0x0045A5E0`, which any enlarged font
  needs to avoid an infinite line-breaking loop. See
  `reverse-engineering/font-atlases.md` for that analysis and
  `docs/font-scaling.md` for the build/hash procedure.
- The font-scale hook's own constant is now permanently 1.0: text sizing moved
  to the atlases' TXI metrics and is resolution-aware. The `.kfs` section's
  *list-row* constant is still live.
- `computercamera.gui`'s alignment, mentioned above, unverified.
