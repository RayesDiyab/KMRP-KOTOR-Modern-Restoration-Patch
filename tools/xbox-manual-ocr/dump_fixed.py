"""Prints the text layer as it stands after the fixes, one recognised line per
row with its index, then the added lines.

    python dump_fixed.py JPG_DIR JSON_DIR FIRST LAST CORRECTIONS.json ...
"""
import json, os, sys
import build_searchable_pdf as b

jpg_dir, json_dir, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
fixes = {}
for path in sys.argv[5:]:
    for page, items in json.load(open(path, encoding="utf-8")).items():
        fixes.setdefault(page, []).extend(items)
for n in range(first, last + 1):
    page = json.load(open(os.path.join(json_dir, "p-%03d.json" % (n - 1)), encoding="utf-8"))
    page["scan_width"] = page["width"] // 2
    lines, added = b.corrected_lines(page, fixes.get(str(n), []))
    print("=== PDF page", n)
    for i, line in enumerate(lines):
        words = [w for w in line if w]
        if words:
            print("%d (%d,%d) %s" % (i, words[0]["x"] / 2, words[0]["y"] / 2, " ".join(w["t"] for w in words)))
    for line in added:
        w = line[0]
        print("+ (%d,%d) %s" % (w["x"] / 2, w["y"] / 2, w["t"]))
