# Fonts of the Linux installer's window

The Windows installer draws with two of Microsoft's fonts: Segoe UI, and Bahnschrift
SemiCondensed for its step titles, states and buttons (`UiTheme.DisplayFont` in
`src/patcher/KmrpPatcher.cs`). Neither may be shipped, and a Linux PC has neither. The
Mac installer stands in DIN Alternate and the system font (`macos/installer-app/main.m`).
The Linux installer carries these, all under the SIL Open Font License 1.1, so its window
looks the same on any distribution:

| File | Stands in for | Source | SHA-256 |
| --- | --- | --- | --- |
| `selawk.ttf`, `selawksb.ttf`, `selawkb.ttf` | Segoe UI (Regular, Semibold, Bold) | Selawik 1.01, Microsoft's open substitute made to Segoe UI's metrics: `Selawik_Release.zip` of github.com/microsoft/Selawik release 1.01 | `e9d98518…ee1c`, `0a9e9d05…7783`, `f0db5e17…c904` |
| `BarlowSemiCondensed-Bold.ttf`, `BarlowSemiCondensed-SemiBold.ttf` | Bahnschrift SemiCondensed Bold | Barlow Semi Condensed, `ofl/barlowsemicondensed` of github.com/google/fonts | `5bd6757e…cbb`, `bd299f4b…1424` |

Their licences are beside them: `Selawik-OFL.txt` (the repository's `LICENSE.txt`, "with
Reserved Font Name Selawik") and `BarlowSemiCondensed-OFL.txt`. Downloaded 2026-10-30.
Neither is modified, so the reserved names may stay.
