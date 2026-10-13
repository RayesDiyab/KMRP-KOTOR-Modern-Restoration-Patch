"""Lists the words two recognition passes of the same pages disagree on.

    python compare_passes.py JSON_A JSON_B FIRST LAST

For every word of pass A, the word of pass B whose centre lies in A's box is
looked up; a line of A is printed when any of its words has no partner or a
partner with another text.
"""
import json
import os
import sys


def load(directory, number):
    with open(os.path.join(directory, "p-%03d.json" % (number - 1)), encoding="utf-8") as handle:
        return json.load(handle)


def main():
    dir_a, dir_b, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    for number in range(first, last + 1):
        a, b = load(dir_a, number), load(dir_b, number)
        scale = b["width"] / float(a["width"])
        centres = [((w["x"] + w["w"] / 2.0) / scale, (w["y"] + w["h"] / 2.0) / scale, w["t"])
                   for line in b["lines"] for w in line]
        print("=== PDF page", number)
        for index, line in enumerate(a["lines"]):
            notes = []
            for word in line:
                inside = [t for (x, y, t) in centres
                          if word["x"] <= x <= word["x"] + word["w"] and word["y"] <= y <= word["y"] + word["h"]]
                if inside != [word["t"]]:
                    notes.append("%s|%s" % (word["t"], " ".join(inside) or "-"))
            if notes:
                print("%d (%d,%d) %s" % (index, line[0]["x"] / 2, line[0]["y"] / 2, "  ".join(notes)))


if __name__ == "__main__":
    main()
