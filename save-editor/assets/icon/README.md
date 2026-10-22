# The Save Editor's icon

A holocron with a datapad in front of it, 2026-10-22. The holocron is the maintainer's
picture; the datapad is drawn from geometry in the holocron's colours (obsidian, glowing
blue cracks) as a KOTOR-style wedge slab with an Aurebesh holo-screen.

| File | What it is |
| --- | --- |
| `icon.png` | the icon, 1024 px, transparent |
| `holocron-clean.png` | the holocron, 2048 px, the white fringe under its base removed (`clean_holocron.py`) |
| `datapad.py` | the datapad: face texture (brushed obsidian, cracks, a height map lit from the upper left), Aurebesh screen, the wedge in 3D |
| `render_icon.py` | the holocron and the datapad placed with the angles chosen in the 3D viewer: left/right -31°, up/down 46°, tilt 4°, size 52%, position 17% across, -14% up |
| `make_icons.py` | crops and centres the render, writes `../save-editor-icon.png` (512, the window and the header) and `../save-editor.ico` (16 to 256, the program file) |
| `AurebeshAF-CanonTech.otf` | Aurebesh AF by AurekFonts, CC0 public domain (its name table: "CC-0 public domain, created by AurekFonts") |

To remake it (Python with numpy, scipy, Pillow):

```bash
python render_icon.py rendered.png 1024
python make_icons.py rendered.png
```

The render reproduces `icon.png` to a mean difference of 1.2 of 255 (the holocron is
read at 2048 px here; the original picture is 4000 px).
