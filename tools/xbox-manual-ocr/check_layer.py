"""Two checks of the finished text layer.

    python check_layer.py JSON_A JSON_B CORRECTIONS.json ...

1. Words the second recognition pass (JSON_B) saw where the layer has nothing:
   a line the first pass dropped shows up here.
2. Words of the layer that do not look like words (a letter beside a digit, a
   character outside the usual set), for a last look.
"""
import json
import os
import re
import sys

import build_searchable_pdf as b

USUAL = re.compile(r"^[A-Za-z0-9.,;:'\"()/+\-!?&%$=\[\]*#>•™®©–]+$")
MIXED = re.compile(r"[A-Za-z]\d|\d[A-Za-z]")


def main():
    dir_a, dir_b = sys.argv[1], sys.argv[2]
    fixes = {}
    for path in sys.argv[3:]:
        with open(path, encoding="utf-8") as handle:
            for page, items in json.load(handle).items():
                fixes.setdefault(page, []).extend(items)
    for number in range(1, 31):
        name = "p-%03d.json" % (number - 1)
        with open(os.path.join(dir_a, name), encoding="utf-8") as handle:
            page = json.load(handle)
        with open(os.path.join(dir_b, name), encoding="utf-8") as handle:
            other = json.load(handle)
        page["scan_width"] = page["width"] // 2
        layer = b.apply_corrections(page, fixes.get(str(number), []))
        boxes = [(w["x"] / 2.0, w["y"] / 2.0, (w["x"] + w["w"]) / 2.0, (w["y"] + w["h"]) / 2.0)
                 for line in layer for w in line]
        scale = other["width"] / float(page["scan_width"])
        print("=== PDF page", number)
        for line in other["lines"]:
            loose = []
            for w in line:
                x, y = (w["x"] + w["w"] / 2.0) / scale, (w["y"] + w["h"] / 2.0) / scale
                if not any(x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4 for (x0, y0, x1, y1) in boxes):
                    if re.search(r"[A-Za-z0-9]{2}", w["t"]):
                        loose.append(w["t"])
            if loose:
                print("  unseen (%d,%d) %s" % (line[0]["x"] / scale, line[0]["y"] / scale, " ".join(loose)))
        odd = [w["t"] for line in layer for w in line for t in w["t"].split(" ")
               if not USUAL.match(t) or (MIXED.search(t) and not re.match(r"^(\d+(st|nd|rd|th)|[0-9A-Z\-.()]+|\(?1d20\)?\.?|\[1d20|DC\d+\)?[.,]?|\(DC\d+\)[.,]?|2D|3D)$", t))]
        if odd:
            print("  odd:", " | ".join(sorted(set(odd))))


if __name__ == "__main__":
    main()
