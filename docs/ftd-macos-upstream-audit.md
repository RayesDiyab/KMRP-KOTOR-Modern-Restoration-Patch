# FTD Mac upstream audit, 2026-10-02

This reference follows [the documentation standard](documentation-standard.md).
The GUI branch is joint work by FTD and the KMRP maintainer. The audit fetched all advertised branches from FTD516/Kotor-Patch-Manager without
changing the pinned submodule checkout. The former `widescreen-patch` branch is
no longer advertised. These are source comparisons, not upstream play-test claims.

| Source | Exact commit | Result |
| --- | --- | --- |
| Integrated submodule | `2a784bf92a21dbc179ef17cbd89a07d694bc768d` | Baseline: FTD `074972b` with duplicate Stray hooks removed |
| FTD master | `f72a22e03f6cddebbf8a23a56c046466196f31f8` | Since `074972b`, only `mac_widescreen.cpp` differs: 933 additions, 108 deletions |
| FTD widescreen-gui-mode | `1ae0dc910ca60fedc5b0741df18a0f5e3d417e0c` | Same C++ as current master; README and manifest differ |
| FTD ScriptsEnterFix | `bfc425fd6534a03dc7662c420cfff75068ad9fdd` | Branch delta adds a guarded Scripts callback hook and its documentation |

Compare topic branches using their merge base (`git diff master...topic`), not a
raw two-tip diff: ScriptsEnterFix predates the GUI-layout additions and a raw diff
misleadingly presents those additions as removals. Its Stray C++ is byte-identical
to our pinned copy (SHA256 `2feea14e9c5dc3d0d84d92658c0258e8e37bde563f7ea1d00caac48b1936394e`).

## Integration decisions

The new Scripts fix is incorporated unchanged in KMRP's core hook list, with
upstream attribution and commit identity, so it is included with or without
controller/map notes. The submodule stays pinned; no dependency commit is needed
for this one independently guarded source hook.

Clean input: Aspyr 1.4.0 x86_64, 6,333,424 bytes, SHA256
`c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71`.
Preferred VA; FILE = VA − 0x100000000.

| VA | FILE | Bytes | Before | After | Purpose |
| --- | --- | --- | --- | --- | --- |
| 0x1002d3e34 | 0x2d3e34 | 1 | 55 (`push rbp`) | c3 (`ret`) | Disable the script-row Enter callback that closes the underlying panel behind the tutorial |

Disassembling from that exact entry confirms the callback saves the selected
script, calls the panel manager at0x10049eeb2, and sets the closing flag0x200.
FTD reports that native ScriptSelect input handling and the Select button still
perform selection. The first-byte replacement and full hook validation are
checked against the identified clean input; tutorial dismissal, Enter selection,
mouse selection and controller selection still require in-game testing.

The new GUI code is not linked alongside KMRP. Its constructor and WindowDraw
install unguarded runtime writers at sites already owned by KMRP. Hook TOML
collision checks alone would miss those internal writes.

| FTD addition | Representative conflicting VA | Existing KMRP owner / decision |
| --- | --- | --- |
| List gutter/row/template layout | 0x1004a8838, 0x1004a937a, 0x1004a5a05 | `listbox_padding.cpp`, `resolution_sizes.cpp`; retain guarded implementation |
| Area-map bridges and markers | 0x1002b4fca, 0x1002b541b, 0x1002b54c2 | `area_map.cpp`; retain KMRP geometry and bridges |
| Message-box fitting | 0x100306a88, 0x100306879 | `popup_fit.cpp`, `resolution_sizes.cpp`; retain KMRP fitting and current text repair |
| Dialogue reply stretch | 0x100244d7d | `dialogue_replies.cpp`; same intended stretch, retain guarded relocated code |
| Options checkboxes | 0x1002cecee | `resolution_sizes.cpp`; retain KMRP scaling |
| Granted ability popup | 0x10028ea4f, 0x10022f321 | `granted_popup.cpp`; retain KMRP row count/extent repair |

Other C++ changes add INI override-presence flags, graphics/base-scale knobs,
INI polling/cache optimizations, GUI-mode map sizing and badge defaults, skip
legacy menu-tree scaling in GUI mode, and remove unused trampolines/constants.
Those accompany FTD's new layout ownership rather than a separate uncovered
engine fix. KMRP already supplies generated GUI sizes and its guarded runtime
layout; enabling the new writers would replace that ownership. No new text-height
rounding or exit-confirmation fix appears in the upstream delta. Our five native
height hooks and removal of the failed action frame pass remain necessary.

Reproduce with `git fetch https://github.com/FTD516/Kotor-Patch-Manager.git
'+refs/heads/*:refs/remotes/ftd-audit/*'` inside the submodule, then compare the
commits above. Upstream branch content can change; the commit IDs identify this
audit. The DMG was rebuilt with this additional hook; the exit-confirmation dialog
still needs retesting.

## Verification

The combined source build validates all four variants against the clean Mac
executable:94hooks with controller/map notes,74without controller,93without map
notes,73without either. KPM reports valid hooks and parameter sources, with no
hook overlap. The builder also verifies constructor order. The single new
Scripts hook introduces no constructor or runtime code writer. All66 reused
resource archives round-trip exactly through the pool;882payload files are
hashed for package verification. The five native-height payload tests and479
relative documentation links pass. These checks do not establish in-game
Scripts tutorial/selection behavior or exit-dialog termination.

The maintainer subsequently confirmed Scripts-menu Enter, Exit Game and the
two-line action name all worked in the actual game (2026-10-02). Controller
selection and broader menu/resolution coverage were not separately reported.
