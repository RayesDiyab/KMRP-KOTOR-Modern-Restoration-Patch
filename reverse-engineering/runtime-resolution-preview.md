# Standalone native resolution preview

Reference and measured experiment, 2026-10-03. This follows the
[documentation standard](../docs/documentation-standard.md). The broader package
design and unfinished migration are in
[the runtime design](../docs/history/kpatch-runtime-design.md).

## What the module does now (read from the source, 2026-10-08)

Everything below this section is a dated record: the preview of 2026-10-03, the
standalone package of 2026-10-04 and the bank of 2026-10-05. This section is the
present state, read from `tools/build_native_kpatch.py`,
`src/controller-native/kotor1-native-runtime.hooks.toml`, `K1RuntimeResolution.cpp`
and `K1RuntimeEngine.cpp` on 2026-10-08. Nothing in it was measured again that day;
what was measured, and what was not, is in [`CHANGELOG.md`](../CHANGELOG.md),
`[Unreleased]`.

**The patch.** `KMRP.kpatch`, id `kmrp`, run by KOTOR Patch Manager 0.7.1 on the
unmodified `swkotor.exe`: one module (`patches\kmrp.dll`), 27 hooks
(`build_native_kpatch.all_hooks()`), the options `map-notes` (on) and `debug-logs`
(off), no `controller` option and no controller hook. Controller support is a second
patch with its own module, "KOTOR 1 Native Controller Mod + Xbox HUD", id
`kmrp-controller`, since 2026-10-05; neither needs the other
([KPM edition](../docs/kpm-edition.md#two-patches-since-2026-10-05)). Where the
records below say one patch with a `controller` option, 24 or 52 hooks, or the frame
sites `0x0040CE70` and `0x00404D96`, that is the state of their day: KMRP's own frame
sites are `0x0040CE76` (`KmrpCoreGuiWorkK1`) and `0x00404D06`
(`KmrpCoreMovieWorkK1`), and the two older ones are the controller patch's.

**The resolution: no choice, the display's own modes (since 2026-10-07).** Addresses
are original-image VA on clean CD 1.03, FILE = VA minus `0x400000`.

| VA | Kind | What the module does there |
| --- | --- | --- |
| `0x005F0C64` | Detour, `KmrpAllowRuntimeResolutionK1` | `IsValidResolution` (`0x005F0C60`) answers yes only if all three hold: width in `[640,32767]` and height in `[480,32767]` (`KmrpRuntimeDimensions`); KMRP has a layout for the size, built or blended (`KmrpRuntimeAssetsCovers`); and the display reports a 32-bit mode of that size (`DisplayReports`, one `EnumDisplaySettingsA` pass kept for two seconds; if the display reports nothing at all, nothing is refused on that account) |
| `0x0073D3E4` | Import slot, `EnumDisplaySettingsA` | *Since 2026-10-09 it also hides every refresh rate above 60 from the dialog unless `high-fps-fixes.dll` is loaded (a size keeps its lowest rate of 60 or more); see [resolution-switch.md](resolution-switch.md) and CHANGELOG.* Replaced by `EnumModesOnce` only when it holds user32's function. For the Screen Resolution dialog's two callers (returning to `0x006E0955` and `0x006E0BC9`) a repeated size, depth and rate is handed back as a mode that is not 32-bit, so each row is listed once. No mode is added |
| `0x005F0FB2` | 12 bytes rewritten at load, guarded: `C7 07 20 03 00 00 C7 02 58 02 00 00` | The 800x600 that `ReadVideoModeSettings` (`0x005F0CE0`) falls back to when the size in `swkotor.ini` is not valid becomes the desktop's size (`KmrpStartAtDisplaySize`) |
| `0x005F5B84` | 10 bytes rewritten at load, guarded: `68 58 02 00 00 68 20 03 00 00` | The 800x600 that `ReadAndSetVideoMode` asks the nearest mode of becomes the desktop's size. Both are left alone when the bytes are not the game's own, when the desktop's size cannot be read, or when KMRP has no layout for it |
| `0x0040BE70` | Detour, `KmrpResolutionRequestedK1` | GUI `SetSize`: the size's interface files and the engine's per-resolution operands are put in place (`Prepare`) |
| `0x005F18F6` | Detour, `KmrpModeSwitchK1` | The mode switch, before the window is made again: the same, then every font's TXI is read again (`ReloadFontMetrics`) |
| `0x0062785F` | Simple, `75 59` to `75 3F` | The tooltip fallback for a 1280-wide size, as in the preview below |

So the game's Screen Resolution list is what the connected display reports, and a
game whose `swkotor.ini` holds a size this display lacks starts at the desktop's
size; `swkotor.ini` is not rewritten.

**Removed on 2026-10-07**, at the maintainer's request ("not have any choice in the
resolution"), after standing from 2026-10-04: the installer's resolution checklist
and the file it wrote beside the game, `kmrp-resolutions.txt`, which the module read;
the modes the module added past the display's own; the hook on the game's
`ChangeDisplaySettingsA` import slot (`0x0073D3E8`), which ran an added size in a
borderless window; the centring of the game's windows and the cursor confinement for
that window. A `kmrp-resolutions.txt` left by such an install is not read, and the
installer removes it with that install. The validator also said yes to every size it
had a layout for until that day; why that was wrong on a display lacking the size is
in the comment above `KmrpStartAtDisplaySize` and in the CHANGELOG entry "No
resolution choice". **Not seen:** the game on a second display.

**The engine and the interface files.** The module applies KMRP's executable changes
in memory when it loads, for the size in `swkotor.ini` if KMRP has a layout for it,
otherwise at the first size the game sets (`InitializeEngine`,
`KmrpRuntimeEngineDimensions`), and writes the per-resolution operands again at each
later size (`kNativeFields`, `tools/build_native_engine.py`). It needs no
`kmrp-kpm.dat` and no `Override` file: the interface files come from the bank
described at the end of this document.

## Status and scope

**This section is the preview of 2026-10-03.** The complete patch built from it is
described from [Standalone package](#standalone-package-2026-10-04) on, and since
2026-10-04 it is KMRP's patch `kmrp`, which the installer installs
([KPM edition](../docs/kpm-edition.md#one-patch-since-2026-10-04)); what that patch
is today is in the section above.

`KMRP Native Preview.kpatch` is an experimental first slice, not the complete
KMRP replacement. It has no controller code, SDL dependency, generated Override
archive or external `kmrp-kpm.dat`. It needs KOTOR Patch Manager and the player's
ordinary game assets. It contains three keyboard repairs, five existing memory
safety sites, the native resolution validator, two viewport trace hooks and one
tooltip fallback branch: twelve hook sites, seven DLL exports.

Full KMRP GUI geometry, scaled fonts, clipping fixes, maps, movies, credits and
additional controls have **not** been migrated. The prototype retains native
vanilla layout sizes. No live installation or remote publication was performed.

## Build and address convention

Primary evidence: clean Windows CD 1.03 executable, 4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
Addresses below are preferred virtual addresses (VA), with original-image
`FILE = VA - 0x400000`. No appended engine section is used by this prototype;
KPM allocates detours and replacement stubs in process memory.

The package declares the same CD/GOG/Steam targets as the existing core. GOG and
decrypted Steam code equivalence is documented in
the package builder of the time (`tools/build_kpatch.py`, removed on 2026-10-04; its helpers are in [`tools/kpatch_common.py`](../tools/kpatch_common.py)). Only CD 1.03 was run
in this experiment. The game's disk executable was unchanged in the fixture.

| VA | FILE | Kind | Guarded original bytes | Callback or replacement |
| --- | --- | --- | --- | --- |
| `0x0040BE70` | `0x00BE70` | Detour, 5 bytes | `8b 44 24 04 56` | Requested viewport trace |
| `0x0040C24E` | `0x00C24E` | Detour, 5 bytes | `8b 4e 10 85 c9` | KeyboardKeepFocusK1 |
| `0x0040CE70` | `0x00CE70` | Detour, 6 bytes | `51 53 55 56 8b e9` | Observed viewport trace |
| `0x0041A9D0` | `0x01A9D0` | Detour, 6 bytes | `8b 44 24 08 85 c0` | KeyboardNavigateK1 |
| `0x0041CE20` | `0x01CE20` | Detour, 6 bytes | `8b 44 24 08 85 c0` | KeyboardListBoundaryK1 |
| `0x0041FEB5` | `0x01FEB5` | Replace, 5 bytes | `c3 90 90 90 90` | Existing texture bucket limit repair |
| `0x0046BE64` | `0x06BE64` | Replace, 10 bytes | `8d 34 40 8b 04 b5 e8 94 81 00` | Existing texture bucket safety repair |
| `0x004A8380` | `0x0A8380` | Replace, 9 bytes | `8b 46 3c 50 e8 07 20 25 00` | Existing grass memory repair |
| `0x004A847C` | `0x0A847C` | Replace, 9 bytes | `8b 56 3c 52 e8 0b 1f 25 00` | Existing grass memory repair |
| `0x005DDE32` | `0x1DDE32` | Detour, 6 bytes | `8b 8b c0 00 00 00` | Existing save-buffer release contract |
| `0x005F0C64` | `0x1F0C64` | Detour, 5 bytes | `3d 20 03 00 00` | KmrpAllowRuntimeResolutionK1 |
| `0x0062785F` | `0x22785F` | Simple, 2 bytes | `75 59` | `75 3f`: tooltip fallback |

The exact reused replacement stubs remain authoritative in
[the core hook table](../src/controller-native/kotor1.hooks.toml), as selected by
[the controller tooling](../tools/kmrp_controller.py). The new sites and parameter
contracts are in [the preview hook table](../src/controller-native/kotor1-runtime-preview.hooks.toml).
Keyboard behavior is covered by [its separate reference](windows-keyboard-navigation.md).

## Resolution selection and limits

The native resolution dialog constructor at VA `0x006E0710` already enumerates
Windows display settings. It keeps the engine's color-depth/refresh filters and
uses the OS mode index as each list row's custom value. Its selected-mode
callback at `0x006DF690` calls the native mode switcher at `0x005ED8D0`.
Those functions and the driver acceptance checks are not replaced.

The internal GUI resolution validator at `0x005F0C60` formerly accepted only its
fixed width/height combinations. The new callback returns one for widths in
`[640,32767]` and heights in `[480,32767]`, zero otherwise. The upper limits follow
the measured signed 16-bit viewport fields at GUI manager offsets `+0x6C/+0x6E`;
they are mechanical bounds, not a claim of usable layouts at 32767 pixels.
The mode must still exist in the native OS enumeration and succeed in the native
switcher. This does not add a custom-size text field or every integer size to
the graphics menu.

The hook takes width from `[esp+4]`, height from `[esp+8]`, and retains EAX. It
replays `cmp eax,800`, then KPM tests EAX for the consumed exit. One returns
through the original `ret 8` at `0x005F0CD2`; zero follows the original width
checks with EAX zero and ends in the original zero return. Replay is necessary
to supply the flags used by the following native conditional branch.

Live startup at 1920x1200 stopped at `0x005F0CD2` with EAX=1 and stack bytes:
`ae 0f 5f 00 80 07 00 00 b0 04 00 00 01 00 00 00`.
The return address was `0x005F0FAE`, followed by width 1920 and height 1200.
The installed site at `0x005F0C64` contained `e9 97 f3 87 00`, proving the
KPM detour was installed in that process. Its allocated jump target is transient.

The SetSize callback records a **request** before native SetSize. The GUI Update
callback reads actual manager fields and records an **observed** change only
when dimensions differ from the previous observation. A request alone is not
proof of a successful switch. The trace is `kmrp-native-preview.log` beside the
test game's executable; callbacks do not resize controls or update fonts.

## Rejected first attempt: widening the validator alone

The first eleven-site preview could switch 1920x1200 to 1920x1080, but selecting
1280x720 failed during GUI reconstruction. x32dbg stopped at `0x00411645`:

```asm
0041163D mov esi,ecx             ; missing GFF object: ECX=0
00411645 mov ecx,[esi+54]        ; null dereference
```

The stack led through InitControl (`0x0040B94D`) to the tooltip constructor
(`0x006278E5`). Clean disassembly exposed the missing layout load:

```asm
00627832 cmp eax,500             ; width 1280
00627837 jne 00627868            ; other widths have a default path
00627839 mov eax,[0078D1D8]      ; current height
0062783E cmp eax,3C0             ; 960 uses tooltip12x9
00627843 jne 0062785A
0062785A cmp eax,400             ; 1024 uses tooltip12x10
0062785F jne 006278BA            ; other heights SKIP loading a layout
006278A0 push 0074FFDC           ; existing tooltip6X4 fallback
006278B5 call 0040A680           ; StartLoadFromLayout
006278BA mov edx,[esi+44]        ; continues even if no layout was loaded
006278E0 call 0040B930           ; InitControl needs that layout
```

The two-byte branch replacement moves only the non-960/non-1024 path to
`0x006278A0`. Existing vanilla modes keep their original resources. This fixes
the width-1280 family generally, rather than introducing a 1280x720 special case.
It does not substitute a resource archive or suppress a failed pointer check.

## Live verification and remaining coverage

The isolated fixture used a canonical clean executable, normal game archives,
KPM's Bink proxy/runtime and the preview module/config. It had no Override folder,
no controller DLL/SDL and no external engine data. Tests used Windows native
rendering, not archive dimensions or a simulated font renderer.

| Action | Measured result | Coverage limit |
| --- | --- | --- |
| Start at 1920x1200 | Validator EAX=1; manager observed 1920x1200 | Before tooltip fix; vanilla GUI sizes |
| Options → Graphics → Screen Resolution | Mouse opens dialog; 1920x1080 and 1920x1200 rows visible | Native OS list retains duplicate mode rows |
| Apply 1920x1080 @75 | Request and observed 1920x1080; INI 1920/1080/75 | Windowed test, before tooltip fix |
| Apply 1280x720 in first preview | Null layout failure above | Rejected eleven-site preview |
| Revised preview start at 1280x720 | Observed 1280x720; main menu and graphics menu operate | Twelve-site preview |
| Select 1152x864 then Cancel | Picker closes; INI remains 1280x720; no new viewport trace | Cancellation before applying a mode |
| Apply 2560x1440 @75 from 720p | Request/observed 2560x1440; INI agrees; graphics panel draws | Subsequent automated clicking did not reopen picker; unresolved |

The twelve-site package's compiled DLL also passed a live native-call matrix in
x32dbg: eighteen calls to the actually hooked validator at `0x005F0C60`, nine
accepted and nine rejected, with ESP identical before/after every call. Accepted
dimensions were 640x480, 800x600, 1280x720, 1920x1200, 2560x1440, 3440x1440,
5120x1440, the uncatalogued 1237x813 and the mechanical boundary 32767x32767.
Rejected inputs covered each lower/upper boundary, negative/zero dimensions and
INT_MAX. These were validator calls, **not display-mode or layout tests**.
The scratch caller saved/restored registers and flags; its allocation was freed
and the isolated process stopped afterward. The installed tooltip branch read
back as `75 3f`. Module SHA-256:
`B040BBB500B8BD88DF86F1865DD0BD2740094296B4A1C9B98B6E41EDF247815E`.

Automated package regressions passed corrupted-byte/target/parameter/dependency
rejection and deterministic archive rebuild. All twelve clean byte guards passed.
The separate x86 callback harness compiled, but Windows refused launching it with
a sharing/access error; do not count that harness as executed. The native-call
matrix above supplied the actual compiled callback/trampoline coverage instead.
509 relative documentation links passed after adding this reference and memory link.
The clean-to-fixture disk inventory had zero changes. The existing production
v24 gold snapshot inventory had 82 runs, 721 differing original-image bytes and
zero undocumented code/data runs; it is a production baseline, not the preview's
runtime footprint.

Synthetic Up did not visibly change the list selection. Do not claim physical
keyboard verification from that attempt. Fullscreen confirmation timeout/revert,
live 3440x1440/32:9/custom windowed sizes, repeated accept/revert, Alt-Tab,
translated text, font clipping, maps, movies and gameplay remain untested.

## Rebuild and verify

### 2026-10-03 embedded-resource follow-up (unfinished)

The separate `build_native_runtime.cmd` experiment now embeds the engine recipe
and the generated Windows resource bank. It is not the three-entry preview
archive described above, and no full standalone KMRP archive is claimed here.
The isolated clean CD input remains 4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
Addresses below are original-image VA; FILE = VA minus `0x400000`.

| VA | FILE | Native operation | Measurement |
| --- | --- | --- | --- |
| `0x40B760` | `0x00B760` | Panel drawing | Rejects a panel extending beyond the viewport; root geometry left at 3440 pixels explained the blank menu after a 2560-pixel switch. |
| `0x40B930` | `0x00B930` | InitControl | Control is argument 1, label argument 2, activation argument 3. PUSH EBP shifts the original argument 1 to esp+8 at `0x40B935`. |
| `0x5E5ABE` | `0x1E5ABE` | CExoString constructor | Increments strlen before storing allocation length at object `+4` at `0x5E5AC0`. |
| `0x61D9A0` | `0x21D9A0` | Default graphics options | A fresh 1920x1200 Default click reached this handler and reset a changed brightness slider. |

**Visible correction:** the first geometry-tracking attempt used the CExoString
allocation length as a tag length, retaining the terminating zero and preventing
matches with GFF TAG strings. A subsequent disassembly reading incorrectly
declared the control/label arguments reversed, missing PUSH EBP's stack shift.
Direct measurement at `0x40B935` disproved that reading: original argument 1 was
a control with vtable `0x73E5B8`; original argument 2 was CExoString `LBL_TITLE`,
allocation length 10. The original argument order is restored and the tag-length
fix retained.
The first 17-hook build switched 1920x1200 to 2560x1440 but retained old control
positions. Its Close click did not return to Options. The apparently interrupted
switch was a debugger first-chance UI Automation exception, not a proven game
crash; continuing it completed the requested/observed mode transition.

Before the switch, fresh 1920x1200 Close returned to Options and Default reset
brightness. This does not establish arbitrary-resolution or keyboard support.
With the tag fix and original argument order, module SHA-256
`9EEF23DACF485DF0E8F11976A31C33CD147C853A54D717513B465312D67D55C7`
(141,583,872 bytes) moved the 2560x1440 Graphics bottom buttons into their new
positions. A native hovered Default control read back extent
`LEFT=452, TOP=1230, WIDTH=584, HEIGHT=84`. Subsequent interaction reached a
different options menu with corrupted text; a Close release read no captured
control at GUI manager `+0x10`. The native graphics reset handler was not observed
in this post-switch run. Thus post-switch Close/Default reliability is not a pass,
even though the geometry now updates. Investigate active-panel/capture routing
alongside font-cache migration before declaring support.
Height-change font metadata, child geometry, clipping, map/movie coverage,
transaction rollback and full packaging remain unfinished.

### Standalone package (2026-10-04)

`src\controller-native\build_native_runtime.cmd` followed by
`python tools/build_native_kpatch.py` now produces
`dist/native/KMRP Standalone.kpatch`: patch id `kmrp-native`, 24 runtime hooks
(the `kmrp` and `kmrp-movies` hooks of
[the core table](../src/controller-native/kotor1.hooks.toml) plus
[the standalone table](../src/controller-native/kotor1-native-runtime.hooks.toml)),
one module, the CD/GOG large-address static hook and the licence texts. It
conflicts with the installer edition's four patches. Addresses below are
original-image VA on clean CD 1.03; FILE = VA minus `0x400000`.

**Visible correction: the parameter spelling.** The hook tables above used
`[esp+N]`. KOTOR Patch Manager 0.7.1's released runtime
(`KotorPatcher.dll`, SHA-256 `20CD07AF...7DDE3B4`) accepts that spelling at
install and then pushes nothing for it at run time ("Unsupported parameter
source"), so every later argument is misplaced. Installed through KPM's own
command line on a clean fixture, the first standalone build faulted seven seconds
after launch in `KmrpPanelControlK1`, reading a label pointer that was the saved
EFLAGS value `0x00200246`. The earlier fixture ran KMRP's own runtime build
(`E7D6AE7F...79D7B532`), which hid it. Both tables now use `esp+N`, which passes
the **address** of the slot, as `KeyboardNavigateK1` always has.

| VA | Finding | How established |
| --- | --- | --- |
| `0x5F1830` | The native mode switch stores the new size at `0x78D1D4`/`0x78D1D8`, re-creates the window at `0x5F19B2` (`0x403800`), and only then calls GUI SetSize at `0x5F19DE` | Disassembly; x32dbg counted one hit of each per switch |
| `0x5F18F6` | New detour, `KmrpModeSwitchK1`: `83 3D 2C 3A 7A 00 01`, one absolute `cmp`, a branch target only at its first byte | Guarded bytes; `switching WxH` in the trace precedes `requested` |
| `0x422AF0` | A texture's TXI load, `__thiscall (texture, name)`. Called once, when the texture is created (`0x42359C`). Parses in place when the object at texture `+0x38` exists | x32dbg: 18 then 5 hits per switch, all for newly created panel textures (`load_default`, `dialog2`, `800x600load`), none for a font |
| texture `+0x38` | The 0x30-byte TXI object is the `CAurFontInfo`: `+0x04` font height, `+0x08` baseline, `+0x0C` texture width, glyph coordinate arrays at `+0x18` and `+0x24` | Constructor `0x4221C0`, parser `0x422210`, array parser `0x421FF0` (resizes through `0x421310`) |
| `0x7A4798` / `0x7A479C` | The texture registry and its count; the lookup by name walks it at `0x420AE0`, names at `+0x78` | Disassembly. `0x7A4770` is a queue of textures just created and is empty at a switch |

So a switch reloaded each font's atlas image and kept its metrics: 1920x1080 to
1920x1200 garbled every label, and switching back restored them. Moving the
resource swap to `0x5F18F6` alone made it worse (new image, old metrics, and
Alt-Tab, which had been reloading images, no longer repaired it). A first
metrics reload walked `0x7A4770` and reloaded nothing. The module now calls
`0x422AF0` on every registry texture that has a TXI object, after the swap; the
trace line is `font-metrics <reloaded>x<textures>`. The maintainer play-tested
3440x1440 to 1920x1200 to 1440x1080 with readable text.

Measured input facts for anyone driving the fixture: with x32dbg attached,
injected keys reach the menus and injected clicks do not; detached, the reverse.

**Later the same day.** Measured or changed after the audit below was written:

| Subject | Finding or change | How established |
| --- | --- | --- |
| Override priority | KMRP's private directory wins over Override | Five 800x600 `mainmenu*.gui` files in the fixture's Override; the 1440x1080 main menu was still KMRP's. One file family only. A `.tpc` in Override may still beat a KMRP `.tga`: the installer's check for that exists because the engine prefers the format, and it was not measured here |
| Options buttons after a switch | `optionsmain` loads `BTN_GAMEPLAY` at file top 245 and the engine's code moves it to 265 (all five buttons, +20 at 1080 lines). The re-layout applied the bare file. It now keeps `position - file` per control, remembered at the scale it was measured and re-applied at the new one | Trace of every control before and after a 1440x1080 to 1366x768 to 1440x1080 round trip; only `optionsmain` differed. After the fix the button is at 265 again |
| Screen Resolution dialog | No drift. Its scrollbar on the left and its translucent fill are `optresolution.gui` as authored (`LB_RESOLUTIONS` at 16,88 in a 666-wide panel, fill `dialog`), identical on a fresh start and after a switch | Layout dump and captures |
| Repeated rows | `EnumDisplaySettingsA` reports each size and rate once per `dmDisplayFixedOutput` value (0, 1, 2 on the test machine: 27 modes for 1440x1080 at 32 bits). The constructor at `0x6E0710` calls it at `0x6E094F` (mode 0) and `0x6E0BC3` (the loop). The module replaces the import slot `0x73D3E4`, only when it holds user32's function, and for those two callers returns a repeat as a non-32-bit mode | Raw enumeration; filtering the first call alone changed nothing; with both, one row each, and a switch chosen from the list still landed (1366x768 at 75 Hz in the trace and the ini) |
| Map notes | The engine payload carries the `.kmn` flag cleared and one block edit of feature 4 that sets it, as `kmrp-kpm.dat` does. The module adds feature 4 when `patch_config.toml` names `kmrp-native-map-notes` | `kmrp-kpm.log`: "KMRP + Movies + Map Notes" with the add-on installed through KPM, "KMRP + Movies" without |
| Reachable sizes | `KmrpRuntimeAssetsCovers`: a catalogued size, or one the blend table reaches (the helper's own answer, exit status 0 with no output directory). Asked by the validator hook, the asset swap and the engine | The list still offers the covered sizes. No uncovered size was available on the test display to select |

**Two packages, one module (2026-10-04, evening).** `tools/build_native_kpatch.py`
now writes two archives from the same `kmrp-native.dll`:

| Package | Id | For | Hooks |
| --- | --- | --- | --- |
| `dist/native/KMRP Standalone.kpatch` | `kmrp-native` | KOTOR Patch Manager 0.7.1 | 24, none conditional. No controller; map notes by the add-on |
| `dist/native-options/KMRP.kpatch` | `kmrp-native-options` | A KPM with patch options (upstream issue 13; local prototype in `build/research/kpm-options-fork`), and KPM 0.7.1 with every option on | 52, of which 30 carry `when`: 28 for `controller`, 2 for `movies`. No address has two hooks |

The options package declares three toggles, all default on: `controller`,
`map-notes`, `movies`. The frame sites `0x0040CE70` and `0x00404D96` each have one
unconditional hook, `CoreGuiFrameK1` and `CoreMovieFrameK1`, which run
`NativeGuiFrameK1` and `NativeMovieFrameK1` themselves when `controller` is on
(`KmrpControllerOptionK1`). `map-notes` gates no hook: the module reads
its options (`OptionalFeatures` in `K1RuntimeEngine.cpp`) and passes the map-note
and movie features to the engine applier. An option nobody recorded is at its
default. *Since later on 2026-10-04 the options are read from `configs\kmrp.ini`,
section `[Patch Options]` (`KmrpOptions.h`), and there is a third, `debug-logs`,
off by default; when this was written they were a `[patches.options]` table under
the patch's id in `patch_config.toml`, which is what the next paragraph's "options
table" and "four lines" mean.* Both GUI frames call
`KmrpResolutionObservedK1` first in this module.

The first version had two hooks at each frame site, one per state of
`controller`. KPM 0.7.1 ignores `when` and `[[patch.options]]`, so it took both
and refused the package with "Hook conflicts detected". With one hook per
address it installs all 52, writes no options table, and the module treats
that as every default: the config it writes is the fork's default install minus
the four `[patches.options]` lines (compared 2026-10-04). `option_hooks()` in
`tools/build_native_kpatch.py` now fails the build if two hooks share an address.

The module now compiles the controller sources (`K1NativeJoystick.cpp`,
`K1ControllerBackend.cpp`, `K1Rumble.cpp`, the vendor pair), so
`K1RuntimeCore.cpp`, a temporary copy of the core frames, is gone. The bank
carries every installed file, the `kmr*` badges and `kmrplayout.gui` included,
and `kmrp-sdl3.dll`, which `InitSdl` loads from the module's cache when it is
neither beside the module nor beside the game: 17,127 objects, 188,437,845
bytes, module 188,856,832 bytes.

| Check | Result |
| --- | --- |
| Options package, defaults, through the fork's CLI | 52 hooks written, `controller = true`, `map-notes = true`, `movies = true`; engine log "KMRP + Movies + Map Notes"; game at the main menu |
| Virtual Xbox pad (ViGEm) with `controller` on | D-pad moves the main menu focus and the A badge follows; A opens Options and Gameplay, which shows Controller Layout and Y/B badges |
| Options package with all three off (`--option`) | 22 hooks; engine log "KMRP", 75 of 79 runs; the pad does nothing (the active control in the panel stack does not change) |
| Stock package through KPM 0.7.1 | 24 hooks, engine log "KMRP + Movies", game runs |
| Options package through KPM 0.7.1 | 52 hooks, no options table; engine log "KMRP + Movies + Map Notes"; the virtual pad walks the main menu and A opens Load Game, read from the panel stack (`testing/controller/dump_panel_stack.py`) |

A fullscreen game must be captured with `ddagrab`: a GDI screen copy returned the
same stale frame through every pad press and looked like dead input (2026-10-04).
A pad connected after the game started was not picked up at the main menu.

Not checked: the Gameplay screen with `controller` off, SDL pads (only the XInput
virtual pad was used), rumble, a live resolution switch with the controller on,
and map notes in an area map.

**Gaps against the installer edition** (audit of `KmrpPatcher.cs` and
`KpmEdition.cs`, 2026-10-04). Closed that day: installer-made game art, the DPI
opt-out, licence texts, cache removal, map notes as an option, the refusal of
unreachable sizes, the Options layout after a switch. Open:

| Gap | Effect |
| --- | --- |
| NVIDIA present method (issue #14) | Closed 2026-10-04 at the maintainer's decision ("log a warning and then set it"): the module makes the installer's check at the first frame, logs a warning and sets Prefer native in the game's profile (`K1RuntimeNvidia.cpp`, [reference](../docs/nvidia-present-method.md#the-standalone-module)). Until then it was left out on purpose, as a machine-wide driver profile that a KPM patch has no uninstall step to restore; that still holds, and the log line says how to undo it by hand |
| K1 Modern Driver Compatibility is not included | The player adds Synchro's own patch in KPM |
| Movies are always on | No opt-out |
| No controller in the 0.7.1 package | KPM 0.7.1 has one module per patch and no options. The options package has it |

```powershell
.\src\controller-native\build_runtime_preview.cmd
python tools/build_runtime_kpatch.py
python tools/build_runtime_kpatch.py --check "dist/native-preview/KMRP Native Preview.kpatch"
python tools/build_runtime_kpatch.py --check "dist/native-preview/KMRP Native Preview.kpatch" --verify-clean build-inputs/swkotornopatch.exe
.\testing\regression\Test-RuntimeResolution.cmd
python testing/regression/Test-RuntimeKpatch.py
python .github/scripts/check_links.py
```

The optional clean input is verification-only; neither archive nor module embeds
game executable bytes or installer payloads. The builder verifies the twelve
clean site guards, native `ret 8`, targets, callback parameter contracts, export
set, archive contents, overlapping spans and equal-length simple writes. KPM
also verifies the process bytes before installing each hook. Build the same
inputs twice to compare archive SHA-256. Test the packaged callback with the x86
regression harness to verify boundary returns and cdecl stack balance.

For manual reproduction, install only the preview in a separate clean game
through KPM, open Graphics → Screen Resolution, select a driver mode, then compare
the observed viewport trace, native drawing and INI. Reproduce the tooltip case
by switching to a driver-provided width-1280 mode whose height is neither 960 nor
1024. Removing the preview through KPM reverses its runtime hook selection;
it has no KMRP Override files to restore. Preserve any existing KPM ownership.

### The bank leaves out what the module makes (2026-10-05)

Until this change the module's resource bank (`build/native-runtime/native-assets.bin`,
`KNAST001`) stored every file of every resolution's set: 62,898 files for 66 sizes,
30,848 distinct objects, 248,545,368 bytes of a 249,026,195 byte patch. By kind,
measured on the build of 2026-10-05 (packed sizes, XPRESS-Huffman):

| Kind | Objects | Packed |
| --- | ---: | ---: |
| Badge and cue textures (`kmr...`) | 11,717 | 51.2 MB |
| Focused-state badge textures (`kmf...`) | 12,021 | 50.7 MB |
| Layouts (`.gui`) | 5,414 | 32.1 MB |
| Fonts and the other common textures | 1,148 | 80.7 MB |
| Loading screens | 23 | 25.6 MB |
| Everything else (font metrics, SDL, the blend table, manifests) | 525 | 3.7 MB |

The module already carried the means to make the first three: `KmrpGuiBlend`, the
blend helper (`macos/tools/kmrp-guiblend.c`), which it ran for a size with no set.
`Test-GuiBlendHelper.py` has long shown that for the 45 sizes the blend resolves to
themselves, the helper's output is the build's set byte for byte.

**The format, `KNAST002`.** Unchanged except that an object may be absent: the header
(magic, group count, object count, the blend table's key), then each group's size and
entries (name, SHA-256), then the stored objects (key, size, packed size, bytes).
`tools/build_native_assets.py` builds the helper as an x86 program with the module's
own compiler flags, runs it for every set on that set's own two input files
(`kmrp_prompts.txt`, `dialogfont16x16.txi`), and marks each file it wrote exactly as
the set has it. An object is stored if any file that is not so marked needs it. On
the same build: 3,758 objects, 128,804,860 bytes; 45 sets rebuilt whole, 20 in part
(32 to 329 files differ, 3440x1440 the most), and 1280x1080 stored whole because the
helper answers that the blend does not cover it (exit status 2, the answer
`KmrpGuiBlendCovers` gives the module).

**The module, `KmrpRuntimeAssetsDimensions` in `K1RuntimeAssets.cpp`.**

1. Every file of the common group and of the chosen set whose object is stored is
   decoded and written. If the size is not a listed one, or any file of the set has
   no object, the helper is needed.
2. The helper writes the set for exactly this size into the same folder, reading
   the two input files step 1 wrote. What it wrote is then adopted by name: the
   set's entries are read back and hashed, since the next size change's ownership
   check and `GameArt`'s sweep of unowned files both go by that list.
3. At a listed size, each entry whose file does not hash to its key gets the stored
   object written back over it (that is exactly why the object was stored), and an
   entry that still differs is counted. A count above zero is written to
   `kmrp-kpm.log` as a warning and the game continues with the helper's file. That
   case is the helper computing differently on the player's PC than on the build's;
   it was not seen.

**Measured in a scratch install** (CD 1.03 executable, the committed installer's
install with only `patches\kmrp.dll` replaced), every file of the module's folder
hashed and compared with the folder the committed build's module made:

| Size | Kind | Files | Differing |
| --- | --- | ---: | ---: |
| 1920x1080 | rebuilt whole | 2,136 | 0 |
| 1360x768 | 244 files stored | 2,037 | 0 |
| 1344x840 | 70 files stored | 2,037 | 0 |
| 1280x1080 | stored whole, no helper | 2,037 | 0 |
| 1700x1000 | not listed: the blend, as before | 2,038 | 0 |

The new module's folder also holds `gui-blend.bin` at a listed size, which the old
one wrote only for an unlisted one. The game asks for no resource of that name.

**Time**, from the line the module writes with the `debug-logs` option on
("interface files for WxH: N ms, of which the blend helper M ms"), on the
maintainer's PC:

| | Interface files | Of which the helper |
| --- | ---: | ---: |
| 1280x1080, every file stored (the path every listed size took before) | 5.9 s | 0 |
| 1920x1080, rebuilt whole | 6.5 s | 1.3 s |
| 1360x768, 244 files stored and written twice | 7.6 s | 1.4 s |

The same change removes two costs, which is why a rebuilt size is not 1.3 s slower
than before: `Write` no longer hashes a decoded object that `Decode` has just held
against its key (each file was hashed three times: decoded, before writing, read
back), and after the helper only the set's files are read back and hashed, not every
file written so far. With only the second of those in, the same sizes took 6.4 s
(1280x1080) and 6.7 s (1920x1080). The old module has no timing line, so its own
figure was not measured; 6.4 s is the nearest to it. What remains is mostly the
creation of about 2,100 files.

**Stronger compression: a switch, off.** The bank's first eight bytes name its
compression, `KNAST002` for XPRESS with Huffman and `KNASL002` for LZMS, and the
module makes its decompressor to match. `tools/build_native_assets.py --lzms` builds
the second. Measured on the same build, the module rebuilt around each bank and run in
the scratch install at 1920x1080, twice each:

| Bank | Bytes | Interface files | Files against the committed build's |
| --- | ---: | ---: | --- |
| XPRESS-Huffman (shipped) | 128,804,860 | 6.4 s, 6.6 s | identical |
| LZMS | 94,534,820 | 9.0 s, 9.1 s | identical |

So 34 MB less to download for 2.5 s more at every start of the game on this PC, and
more than that on a slower one: the common files, 299 MB unpacked, are decoded at
every start, and LZMS decoded them in 2.57 s where XPRESS took 0.64 s. Building the
LZMS bank takes about four minutes instead of one. The shipped bank stays XPRESS
until the maintainer decides otherwise.

**Not run:** fullscreen, a size change inside the game (the folder is reused and the
ownership check runs), the GOG and Steam executables, a PC other than this one, and
the Mac, whose packaging does not use this bank.
`testing/regression/Test-NativeAssetsBank.py` checks the bank itself.
