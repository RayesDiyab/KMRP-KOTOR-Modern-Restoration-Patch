# Third-party notices

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## KOTOR High Resolution Menus

The per-resolution GUI layouts are derived from **KOTOR High Resolution Menus 1.5** by ndix UR:

https://deadlystream.com/files/file/1159-kotor-high-resolution-menus/

The upstream package includes the GNU General Public License version 3. A copy is preserved at:

`third_party/kotor-high-resolution-menus-1.5/LICENSE.txt`

The original archive and generation scripts are retained in the project so the bundled layouts can be reproduced and audited.

## HD menus and UI assets

The shared interface artwork originates from and/or is derived from the HD menu/UI asset set used by RaymanGT's earlier 3440×1440 release:

https://deadlystream.com/files/file/1457-hd-menus-and-ui-assets/

RaymanGT's earlier mod page:

https://deadlystream.com/files/file/2288-kotor-3440x1440-enhanced-hudui-and-menus/

Keep these credits with any public release. Confirm any additional redistribution conditions with the original asset authors before publishing outside the existing agreed project scope.

## Fonts

**No font file is redistributed.** The patcher embeds only rendered TGA glyph
atlases; the `.ttf`/`.otf` files under `assets/fonts/` are build-time inputs
that stay on the build machine. Verified by inspecting every embedded archive —
there is no `.ttf` or `.otf` anywhere in the shipped executable.

### Arimo — item descriptions and dialogue subtitles (`fnt_d16x16b`)

Apache License 2.0, by Steve Matteson / Google Fonts. A metrically compatible
substitute for Arial, chosen because the vanilla dialogue atlas is
Helvetica/Arial-like (true lowercase with real descenders, unlike the
small-caps menu atlases).

https://fonts.google.com/specimen/Arimo

### Old Republic — menus, item names, buttons (the other 17 resrefs)

By **Trollax Kinora**, published on dafont and marked **"free for personal
use"**:

https://www.dafont.com/old-republic.font

The author's own note states it is "a reproduction of the font from the Lucas
Arts game, Knights of the Old Republic II ... made ... from screens of the
game", and that because it is "designed after the intellectual property of
someone else it will never be released as anything other than for personal
use." Permission to redistribute was requested and is not expected to be
granted, since those rights are not the author's to give.

**Decision on record**: ship it inside the patcher (which already requires
owning the game) and remove it if Lucasfilm objects. See
`reverse-engineering/font-atlases.md` for the full reasoning, including why
`assets/fonts/KOTOR_UI_Open.ttf` — our own trace of the game's 32px
`dialogfont32x32` master — is only a *typographic* fallback and not a cleaner
one legally, being derived from the same underlying IP.

### Evaluated and not shipped

Chakra Petch (SIL OFL), Montserrat (SIL OFL), Rajdhani, Exo 2, Nimbus Sans L
(GPL, URW), Syncopate (Apache). Retained only as build-machine references.
ITC Blair was considered but is a commercial Monotype/ITC face; it was neither
obtained nor used.


## KotorUniResPatch (KPM), J0-o

`https://github.com/J0-o/KotorUniResPatch`. No licence file is published in the
repository (checked 2026-09-02, `LICENSE` returns 404).

No code is copied from it. Its `Scaled Map + Minimap` module independently
identified `0x00459920` as the HUD minimap's image-draw normaliser, and named the
surrounding functions; reading it confirmed our own disassembly and, more
usefully, showed that the function is shared with other draws and must be gated
before it is altered. Our `tools/build_minimap_zoom_fix.py` is an independent
implementation: a hand-written x86 stub gated on viewport geometry and source
size, where KPM uses a DLL with detours and a flag set around the draw. The
arithmetic differs too — KPM scales by an integer `round(height/600)` and sets
the viewport to match, whereas ours derives the factor from the viewport the GUI
actually produced.
