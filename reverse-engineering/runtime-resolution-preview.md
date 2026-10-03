# Standalone native resolution preview

Reference and measured experiment, 2026-10-03. This follows the
[documentation standard](../docs/documentation-standard.md). The broader package
design and unfinished migration are in
[the runtime design](../docs/kpatch-runtime-design.md).

## Status and scope

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
[the existing package builder](../tools/build_kpatch.py). Only CD 1.03 was run
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
