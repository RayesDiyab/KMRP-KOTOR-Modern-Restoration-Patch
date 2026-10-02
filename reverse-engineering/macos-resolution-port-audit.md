# macOS resolution acceptance and Windows port audit

This reference follows [the documentation standard](../docs/documentation-standard.md).
Audit date: 2026-10-02. Source comparison, guarded generated-byte checks, a live
mode enumeration, and the user's resolution-popup check are distinguished below.

## Confirmed missing port and repair

Windows `ResolutionPatch.Apply` writes the selected width/height into the first
`IsKnownResolution` pair at VA `0x005F0C65` / `0x005F0C6F` (FILE = VA - 0x400000).
Mac K4 sets the render target and K9 supplies Retina twins, but neither updates
the separate GUI whitelist. The original Mac function accepts only 800x600,
1024x768, 1280x960, 1280x1024 and 1600x1200. The resolution popup calls it via
`0x10028c852` from both its refresh-rate branches, at `0x1002cd1c4` and
`0x1002cd320`. One shared pair therefore covers both branches.

Mac build: Aspyr 1.4.0, clean SHA-256
`c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71`.
Diagnostic executable: 6,324,304 bytes, SHA-256
`5294ae4f8390dcee54473028a69546128a6d4c2308bd355a18b55692d6748e48`.
These Mac original-text sites use preferred VA, FILE = VA - 0x100000000.
No executable on disk is changed by the new runtime group.

| Mac VA | FILE | Guard, 6 bytes | Replacement | Windows counterpart |
| --- | --- | --- | --- | --- |
| `0x10026f1f2` | `0x26f1f2` | `81 fe 20 03 00 00`, cmp esi,800 | cmp esi,W | immediate `0x005F0C65` |
| `0x10026f1ff` | `0x26f1ff` | `81 fa 58 02 00 00`, cmp edx,600 | cmp edx,H | immediate `0x005F0C6F` |

`kmrp_layout.cpp` puts these in one guarded group, using the same configured
W/H as the GUI layout. It replaces the first accepted pair just as Windows does;
the remaining native accepted sizes, OS enumeration, mode indices and refresh
rates are untouched. A conflict in either expected instruction skips the group.

| Configured size | Width comparison immediate | Height comparison immediate |
| --- | ---: | ---: |
| 800x600 | 800 | 600 |
| 1920x1200 | 1920 | 1200 |
| 3024x1964 | 3024 | 1964 |
| 3840x2160 | 3840 | 2160 |

The read-only live enumeration found 26 mode records in the vector at global
`0x1006780c0` (24-byte records, width +0, height +4, refresh +8, HiDPI byte +20).
Index 13 was already **1920x1200, 120 Hz, HiDPI=1**. After the patch the actual
whitelist returned 1 for this size. The user then confirmed it appears in Graphics.
This establishes enumeration and visibility; applying every alternate mode is
not play-tested. No synthetic mode or renamed 1024x768 row was needed.

**Correction:** the previous parity tracker grouped the rendering pair and menu
acceptance pair under a single completed row. That claim missed this function.
The earlier hypothesis that an absent OS mode might prevent this size is rejected
for this MacBook's measured 1920x1200 mode; it remains possible on other displays.

## Scope of the broader comparison

The table below inventories every guarded run from the current Windows source
recipe (`tools/build_windows_engine.py:assemble().runs()`), including its
installer-only fields. Each run is mapped to its Mac implementation or a documented
platform difference. A source counterpart is not proof of equivalent gameplay.
The 11 injected Windows pages are covered by the same functional groups: map,
letterbox, fonts/rows, wrap, stack, gutter, newline, zoom, fog, notes and movies.

The Mac layout regression checks 55 generated sites at 76 sizes, their original
bytes against the clean Mach-O, their lengths, widescreen-hook overlaps, scaling
values and relevant generated instruction sequences. It now checks both menu
acceptance instructions against each configured W/H. Navigation regressions cover
the separate shared graph/list repair and 87 effective GUI resources (67 menus).
These tests do not certify every specialized native panel handler or runtime state.

| Windows VA | Guard bytes | Mac counterpart / disposition |
| --- | ---: | --- |
| `0x00403D6C` | 4 | Aspyr native movie path; existing platform-specific behavior, not retested here |
| `0x00403D78` | 4 | Aspyr native movie path; existing platform-specific behavior, not retested here |
| `0x004057AC` | 7 | Aspyr native movie path; existing platform-specific behavior, not retested here |
| `0x0040AA65` | 4 | Widescreen K4: target video mode |
| `0x0040AA85` | 4 | Widescreen K4: target video mode |
| `0x0040B6C7` | 4 | Widescreen UseGuiFileLayouts: full-screen recentring |
| `0x0040B6DA` | 4 | Widescreen UseGuiFileLayouts: full-screen recentring |
| `0x0040BA6C` | 4 | Widescreen UseGuiFileLayouts: full-screen recentring |
| `0x0040BA83` | 4 | Widescreen UseGuiFileLayouts: full-screen recentring |
| `0x00415E0D` | 5 | Stray K3: leading-newline trim |
| `0x00417992` | 10 | resolution_sizes.cpp: text-list row scale |
| `0x0041A2F2` | 15 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B1C4` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B26B` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B339` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B3AE` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B46D` | 12 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B48C` | 5 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B507` | 2 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B52E` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0041B553` | 1 | listbox_padding.cpp: gutter, item and scrollbar geometry |
| `0x0045992A` | 26 | Widescreen K8: minimap zoom/fog |
| `0x0045A3B7` | 6 | Stray K1: short-string guards and wrap progress |
| `0x0045A3DC` | 6 | Stray K1: short-string guards and wrap progress |
| `0x0045A5E0` | 16 | Stray K1: short-string guards and wrap progress |
| `0x0045A850` | 7 | Runtime font scaling disabled with UseGuiFileLayouts; baked atlases |
| `0x004A1770` | 13 | Runtime font scaling disabled with UseGuiFileLayouts; baked atlases |
| `0x005F0C65` | 4 | New guarded layout group: resolution menu acceptance |
| `0x005F0C6F` | 4 | New guarded layout group: resolution menu acceptance |
| `0x005F5B3B` | 12 | Aspyr native movie path; existing platform-specific behavior, not retested here |
| `0x0062540D` | 4 | resolution_sizes.cpp / popup_fit.cpp: popup caps and icon sizes |
| `0x006256DC` | 11 | resolution_sizes.cpp / popup_fit.cpp: popup caps and icon sizes |
| `0x006256F6` | 4 | resolution_sizes.cpp / popup_fit.cpp: popup caps and icon sizes |
| `0x00625759` | 4 | resolution_sizes.cpp / popup_fit.cpp: popup caps and icon sizes |
| `0x00626F95` | 4 | resolution_sizes.cpp / popup_fit.cpp: popup caps and icon sizes |
| `0x0062B39B` | 5 | Not needed for Mac map-only rect constants; HUD has separate construction |
| `0x0068AC9F` | 5 | kmrp-map-notes: corrected note coordinates |
| `0x0068C4E3` | 4 | Widescreen UseGuiFileLayouts: KMRP HUD resource selector |
| `0x0068C4F4` | 8 | Widescreen UseGuiFileLayouts: KMRP HUD resource selector |
| `0x006928B3` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006928C3` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x0069405B` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006940DC` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006944A8` | 6 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006944C4` | 6 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006946F4` | 5 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x0069471A` | 13 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694763` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694777` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694A13` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694A39` | 5 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694A53` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694AAC` | 5 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694AC4` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00694AD0` | 5 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x0069505C` | 12 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00695082` | 12 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x006A74D2` | 48 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A7560` | 50 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A7943` | 41 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A7B59` | 48 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A7CD0` | 28 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A7F3D` | 55 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A8C4C` | 44 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006A8E1D` | 9 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |
| `0x006AB8EF` | 4 | resolution_sizes.cpp: skills rows |
| `0x006ACB20` | 4 | resolution_sizes.cpp: skills rows |
| `0x006B4FA9` | 4 | resolution_sizes.cpp: inventory rows and stack label |
| `0x006B527F` | 4 | resolution_sizes.cpp: inventory rows and stack label |
| `0x006B5332` | 36 | resolution_sizes.cpp: inventory rows and stack label |
| `0x006B55E3` | 4 | resolution_sizes.cpp: inventory rows and stack label |
| `0x006C265F` | 4 | resolution_sizes.cpp plus widescreen store icon hook |
| `0x006C2A23` | 4 | resolution_sizes.cpp plus widescreen store icon hook |
| `0x006CD8D9` | 4 | resolution_sizes.cpp: feats/powers chain rows |
| `0x006CDB79` | 4 | resolution_sizes.cpp: feats/powers chain rows |
| `0x006DE012` | 4 | resolution_sizes.cpp: options checkbox geometry |
| `0x006DE031` | 1 | resolution_sizes.cpp: options checkbox geometry |
| `0x006DE08E` | 6 | resolution_sizes.cpp: options checkbox geometry |
| `0x006DE0D1` | 13 | resolution_sizes.cpp: options checkbox geometry |
| `0x0075477C` | 4 | area_map.cpp plus full-screen recentring: map geometry and hit testing |
| `0x00755788` | 3 | Widescreen K7 / dialogue_replies.cpp: letterbox and reply extent |

## Additional runtime-hook gaps found

These Windows hooks are outside the 81-run engine recipe. The Mac source/hook
search found no implementation, and the old tracker omitted them. They are
**applicability checks now traced in the [memory-safety audit](macos-memory-safety-audit.md)**.

| Windows sites (VA) | Purpose | Mac result |
| --- | --- | --- |
| `0x0041FEB5`, `0x0046BE64` | texture-bucket saturation and insertion bounds | Implemented guarded insertion bounds and maximum saturation. Native draw ordering already filters IDs. Machine-code tests pass; high-ID gameplay reproduction pending. |
| `0x004A847C`, `0x004A8380` | prevent aliased grass buffers being freed twice | Implemented guarded equality checks for Mac +0x38/+0x40 in both cleanup routines. Machine-code ownership tests pass; a live failing cleanup has not been reproduced. |
| `0x005DDE32` | free an abandoned save-resource buffer | Native Mac normal and exception cleanup already releases this buffer. Do not add the Windows free. |

The shared popup-fit and granted-row runtime callbacks do have Mac counterparts
(`popup_fit.cpp`, `granted_popup.cpp`), independent of the controller option.
The status-summary layout has already been moved into the core in this worktree,
but the user's missing XP text remains unresolved; do not label that port verified.
Tutorial art is generated by `kmrp-gameart.c`, including tutorial.2da, so the old
tracker warning that it must stop being excluded is stale, not a new missing port.
Controller dispatch/confirmation wrappers exist in `gui.cpp`; a complete replay
of every controller interaction was not performed in this keyboard/resolution audit.

## Review of the recent repairs

The acceptance operands neither alter control loading nor mouse coordinates.
The measured MOVETO zero slots, disconnected footer links, list handler bypass,
stationary-mouse focus takeover and desktop-point cursor clamp each remain
independent reasons for their repairs. No navigation repair was removed merely
because the menu now offers the right mode. The generic list handoff replaces
menu-specific footer routing; same-row navigation is shared, not Feedback-only.

The clamp uses the active viewport when the native default desktop rectangle is
seen. Arbitrary live resolution switching and explicit clipping transitions have
not been exhaustively tested. Likewise, resources are installed for a selected
size: exposing other native modes does not regenerate their GUI assets on the fly,
which is also true of Windows' per-resolution resource installation.

## Verification commands

```sh
../work/venv/bin/python testing/regression/Test-KmrpLayoutPatch.py CLEAN_KOTOR_EXE
clang++ -std=c++17 macos/patches/kmrp-layout/navigation.cpp \
  testing/regression/Test-MacOptionsNavigation.cpp -o /tmp/kmrp-options-test
/tmp/kmrp-options-test
../work/venv/bin/python testing/regression/Test-MacGuiNavigation.py \
  --game GAME_ASSETS --report REPORT_JSON
dotnet build/macos/kpm-cli/kpm-cli.dll validate PATH_TO/kmrp.kpatch CLEAN_KOTOR_EXE
```

Results: combined package 84 hooks and minimal package (no controller/map notes)
63 hooks; both pass original-byte/parameter validation with zero hook overlaps.
The structural GUI audit reports 87 resources, 67 menus, zero failures; the
standalone navigation regression passes, including horizontal list handoff.

The normal Windows source recipe is the comparison input; the Windows game was
not executed on this Mac. No release, live installation, commit or push is part
of this verification. The user's diagnostic popup check is the live confirmation.
