"""The save editor's icon files from a rendered icon: cropped to its content, centred in
a square with a small margin, then assets/save-editor-icon.png (512, the window and the
header logo) and assets/save-editor.ico (16 to 256, the .exe).

    python make_icons.py rendered.png
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
im = Image.open(sys.argv[1]).convert("RGBA")
c = im.crop(im.getbbox())
side = round(max(c.size) * 1.04)
sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
sq.alpha_composite(c, ((side - c.width) // 2, (side - c.height) // 2))
sq = sq.resize((1024, 1024), Image.LANCZOS)
sq.save(HERE / "icon.png")
sq.resize((512, 512), Image.LANCZOS).save(HERE.parent / "save-editor-icon.png", optimize=True)
sq.save(HERE.parent / "save-editor.ico", sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)])
print("icon.png, ../save-editor-icon.png, ../save-editor.ico")
