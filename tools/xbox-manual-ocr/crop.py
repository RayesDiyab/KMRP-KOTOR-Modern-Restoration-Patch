"""crop.py ROOT PAGE X0 Y0 X1 Y1 [ZOOM]: saves a region of a scan (scan pixels) enlarged."""
import sys
from PIL import Image
root, page = sys.argv[1], int(sys.argv[2])
x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
zoom = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
im = Image.open(r"%s\jpg\p-%03d.jpg" % (root, page - 1)).crop((x0, y0, x1, y1))
im = im.resize((int(im.width * zoom), int(im.height * zoom)), Image.LANCZOS)
out = r"%s\crop\p%02d_%d_%d.png" % (root, page, x0, y0)
im.save(out)
print(out)
