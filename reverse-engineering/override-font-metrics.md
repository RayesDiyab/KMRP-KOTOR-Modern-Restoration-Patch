# Override font metrics before first layout

Reference, 2026-10-17. Follows the [documentation standard](../docs/documentation-standard.md).
This fixes the timing of existing Windows Override font scaling, reported in
[issue #63](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/issues/63).
The timing fix itself writes no player font files. The later
[native text settings](../docs/ingame-text-options.md) reuse this hook to scale
both bundled and Override fonts, with the old default size labeled 50%.
That feature adds shared HD/original style sources, separately from this hook.
The macOS implementation is not changed here.

## Build and address convention

Measured from clean editable K1 1.03, 4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`,
and the same-sized clean GOG build,
`9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435`.
Addresses below are preferred **VA**; **FILE = VA - 0x400000** applies to these
inputs. The common loader epilogue has identical bytes in both. Steam's on-disk
text is protected and is not treated as a clean byte-verification fixture; its
existing runtime target/hash and original-byte guards remain in force. Actual
Steam execution of this new hook remains unverified.

## The measured failure

`KmrpScaleOverrideFontsK1` formerly walked the engine texture list at GUI frames,
panel-load start and after a resolution reload. A font created during that
panel load was absent from the preceding walk. Its first layout could cache
line breaks using original metrics, then the following walk enlarged those same
metrics before drawing. The old source explicitly acknowledged that first text
was measured small. Both measurement and drawing read the metrics; the earlier
explanation that only drawing used the enlargement was imprecise. The problem
was when the values changed.

For `fnt_d16x16b`, read directly from the owner's original pack and current KMRP
GUI archives:

| Resolution | Original fontheight | KMRP target | Multiplier |
| --- | --- | --- | --- |
| 1600x1200 | 0.19 | 0.27 | 1.421053 |
| 2560x1440 | 0.19 | 0.32 | 1.684211 |

The issue author's [script](https://github.com/jryantomes/kmdlswap/blob/31bd877fa0934b512d213ddf51c7c3315a122759/tools/kmrp_pcfont/build.py)
pre-sizes TXI fields for a particular resolution, avoiding the late adjustment.
This implementation retains the already supported source fonts and final sizes,
and changes the native notification point instead.

## Native path and the one new hook

`CAurTexture::LoadTXI` at0x00422AF0 parses either loose metadata or embedded TPC
metadata. Its missing-resource path can free the font-info object and set it to
null. All normal paths converge on its common epilogue; EDI still owns the
texture. Only after that epilogue can the caller use the loaded font.

| VA | FILE | Bytes / native operation | Change |
| --- | --- | --- | --- |
| 0x00422B12 | 0x00022B12 | `8B F9`, EDI=ECX texture | Read-only ownership evidence |
| 0x00422BAA | 0x00022BAA | Missing loose metadata jumps to0x00422CC1 | Callback must tolerate null font info |
| 0x00422CC1 | 0x00022CC1 | `8B 8C 24 14 20 00 00`, MOV ECX,[ESP+0x2014] | KPM detour to KmrpFontMetricsLoadedK1; replay original instruction |
| 0x00422CC8 | 0x00022CC8 | POP EDI | Texture remains available until this point |
| 0x00422CD8 | 0x00022CD8 | RET4 | The sole normal return |
| 0x0042359C | 0x0002359C | Initial texture creation calls LoadTXI | Correct metrics before texture consumers |

```text
00422B12 mov edi,ecx             ; preserve texture through the loader
00422C43 jmp 00422CB2            ; loose metadata joins the tail
00422CB1 pop ebp                 ; embedded metadata joins the tail
00422CB2 call 0045F8B0           ; native finalization
00422CB9 jne 00422CC1            ; branch target is the hook start
00422CC1 mov ecx,[esp+2014]      ; hook before replay; EDI still owns texture
00422CC8 pop edi
00422CCB mov fs:[0],ecx          ; preserve native SEH restoration
00422CD8 ret 4                   ; first caller can now measure
```

The stolen span is one seven-byte instruction, with no relative/absolute image
operand requiring relocation. The callback receives EDI as a pointer. KPM's
normal register restoration is retained, `skip_original_bytes` is false, and no
register is excluded. Native conditional branches target the span's first byte,
never its interior. Missing metadata and non-font textures pass unchanged.
The main patch now has29 hooks; the standalone controller remains38. Target hashes
and every original-byte guard remain unchanged apart from adding this exact site.

## Callback and preserved state

Override detection still records each replaced font's target height from the
current KMRP TXI before yielding to the player's texture/metadata. The callback
looks up only the texture being loaded by its16-byte resource name, never the
global texture list. A null texture/font-info pointer, unknown font, invalid
height or unsupported ratio returns unchanged.

`factor = targetFontHeight / parsedFontHeight`. Multiply the same five fields
as the previous implementation, then assign fontheight to the exact target so
repeat notifications cannot compound rounding error. A native resolution reload
reparses the original metadata and passes the same common-return hook before
returning. The late GUI-frame and panel-start calls and the post-reload walk are
removed entirely. Original Override files and priority remain unchanged.

| Field | CAurFontInfo offset | Treatment |
| --- | --- | --- |
| fontheight | +0x04 | Scale, then exact target assignment |
| baselineheight | +0x08 | Multiply by factor |
| texturewidth | +0x0C | Multiply by factor |
| spacingR | +0x10 | Multiply by factor |
| spacingB | +0x14 | Multiply by factor |
| Other fields, UV arrays and their pointers | Rest of0x30-byte object | Unchanged |
| Texture image, name and other texture fields | Texture object | Unchanged |

The font-info pointer is texture+0x38; its name is texture+0x98. Existing guards
require parsed height in(0.001,100) and factor in(0.01,128). The earlier timing-only
implementation used(0.1,16); shared atlases, high resolutions and the text-size
slider now need the wider bounded range. Unlike the previous
pass's one-percent tolerance, a real size difference is finalized before layout;
identical target height is a no-op. The baseline target matches the previous
per-resolution KMRP font heights, then multiplies by the selected percentage/50.
The shared-atlas derivation is documented in [text options](../docs/ingame-text-options.md).

## Verification and remaining coverage

Run `python testing/regression/Test-OverrideFontMetrics.py`. It compiles the actual
production callback, using the owner's original18 fonts and all66 KMRP target
sizes. Each is tested at25%,50%,75% and100%, at its original size and with
synthetic translation-sized metrics, plus mixed group percentages 35/80/60/95:
11,880 cases (9,504 uniform and 2,376 mixed-group). The previous timing-only test
covered144 cases across four resolutions. Each font is finalized before
a simulated first caller reads its dimensions, without registration in any global
texture array. Reload, resolution round trip and repeated notification preserve
correct size without compounding. All non-dimensional font bytes and every texture
byte are checked unchanged. Unknown names, case-insensitive names, null objects,
null font info, zero/negative/NaN/infinite heights and extreme ratios are covered.

The independent Capstone control-flow check proves that the loader has one normal
return, no normal return is reachable while omitting the hook, EDI retains the
texture, no branch enters the overwritten instruction, and the package retains
native byte guards. It does not execute the game renderer.

Measured build checks passed: native core with22 callback exports and29 hooks;
all29 original-byte guards on editable CD and GOG inputs; both package validation
suites; installer install/restore/options including29+38+36 hooks with High FPS
Fixes; and all five upgrade/refusal cases with the legacy installer. Offline
references at1280x720,1920x1080,3440x1440 and3840x2160 preserve the input executable;
the byte inventory reports zero undocumented code/data runs. The new runtime
font-hook site remains the original MOV in those offline reference files.
Actual dialogue wrapping, translation gameplay, and resolution switching in a
running game still need a visual play-test. Check a long dialogue first shown after a cold load, reopen it,
and switch away from the initial resolution and back with an Override font.

The early callback obtains the percentage for the loaded resource through
`KmrpTextSizeForFontK1(name)`. Shared font families follow the four groups in
[in-game text options](../docs/ingame-text-options.md); no new hook or later
measurement pass is added for independent sizes.
