"""Builds a searchable PDF: every page is the scan's own JPEG, untouched, with
the recognised words drawn over it as invisible text.

    python build_searchable_pdf.py JPG_DIR JSON_DIR OUT.pdf [CORRECTIONS.json ...]

JPG_DIR    the scans, one JPEG per page, as `pdfimages -j` wrote them
JSON_DIR   one JSON per page from Read-PageText.ps1 (word boxes in the pixels
           of the image that was recognised, which may be an enlarged copy)
CORRECTIONS.json  optional, any number: {"<PDF page>": [fix, ...]}; the fixes
           are described at apply_corrections
"""
import json
import os
import struct
import sys
import zlib

PAGE_W, PAGE_H = 652.8, 521.76  # the source PDF's page, in points

# Helvetica's advance widths for 32..126, per 1000 units (Adobe's AFM).
WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
BACKSLASH = chr(92)


def text_width(data):
    return sum(WIDTHS[b - 32] if 32 <= b <= 126 else 556 for b in data) / 1000.0


def pdf_string(data):
    out = bytearray(b"(")
    for b in data:
        if b in (0x28, 0x29, 0x5C):
            out += BACKSLASH.encode() + bytes([b])
        elif b < 32 or b > 126:
            out += (BACKSLASH + "%03o" % b).encode()
        else:
            out.append(b)
    return bytes(out + b")")


def jpeg_size(data):
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError("not a JPEG marker")
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height, data[i + 9]
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("no frame header")


def find_words(line, old):
    """The index of the first run of words in a line whose texts are `old`."""
    wanted = old.split(" ")
    texts = [w["t"] if w else None for w in line]
    for first in range(len(texts) - len(wanted) + 1):
        if texts[first:first + len(wanted)] == wanted:
            return first, len(wanted)
    raise ValueError("no words %r in line %r" % (old, texts))


def corrected_lines(page, fixes):
    """Returns (lines, added): the recognised lines after the fixes, each still
    at its own index (None for a removed word), and the lines that were added.

    fixes: a list. [line, text] replaces a whole recognised line; [line, first
    word, word count, text] or [line, "old words", text] some of its words (an
    empty text removes them); {"add": [x, y, w, h], "t": text} adds a line the
    recogniser missed, its box in the pixels of the scan."""
    lines = [list(line) for line in page["lines"]]
    scale = page["width"] / float(page["scan_width"])
    added = []
    for fix in fixes:
        if isinstance(fix, dict) and "columns" in fix:
            continue
        if isinstance(fix, dict):
            x, y, w, h = (v * scale for v in fix["add"])
            added.append([{"t": fix["t"], "x": x, "y": y, "w": w, "h": h}])
            continue
        index, text = fix[0], fix[-1]
        line = lines[index]
        if len(fix) == 4:
            first, count = fix[1], fix[2]
        elif len(fix) == 3:
            first, count = find_words(line, fix[1])
        else:
            first, count = 0, len(line)
        old = [w for w in line[first:first + count] if w]
        if not old:
            raise ValueError("line %d has no words %d..%d" % (index, first, first + count))
        merged = []
        if text:
            x0 = min(w["x"] for w in old)
            y0 = min(w["y"] for w in old)
            merged = [{"t": text, "x": x0, "y": y0,
                       "w": max(w["x"] + w["w"] for w in old) - x0,
                       "h": max(w["y"] + w["h"] for w in old) - y0}]
        lines[index] = line[:first] + merged + [None] * (count - len(merged)) + line[first + count:]
    return lines, added


DEFAULT_COLUMNS = [90, 680, 1280]  # the margins' page numbers, the left page, the right page


def apply_corrections(page, fixes):
    """The page's lines after the fixes, in reading order: column by column
    (a {"columns": [x, ...]} fix gives the left edges, in scan pixels), each
    column from the top, and lines that stand on one row from the left."""
    lines, added = corrected_lines(page, fixes)
    lines = [[w for w in line if w] for line in lines if any(line)] + added
    scale = page["width"] / float(page["scan_width"])
    columns = next((f["columns"] for f in fixes if isinstance(f, dict) and "columns" in f), DEFAULT_COLUMNS)

    def place(line):
        left = min(w["x"] for w in line) / scale
        middle = sum(w["y"] + w["h"] / 2.0 for w in line) / len(line) / scale
        return sum(1 for edge in columns if left >= edge), middle, left

    placed = sorted(((place(line), line) for line in lines), key=lambda item: item[0][:2])
    ordered, row = [], []
    for (column, middle, left), line in placed:
        if row and (column != row[0][0] or middle - row[0][1] > 6):
            ordered += [entry[3] for entry in sorted(row, key=lambda entry: entry[2])]
            row = []
        row.append((column, middle, left, line))
    ordered += [entry[3] for entry in sorted(row, key=lambda entry: entry[2])]
    return ordered


def page_text(page, fixes):
    sx, sy = PAGE_W / page["width"], PAGE_H / page["height"]
    ops = [b"BT 3 Tr"]
    count = 0
    for line in apply_corrections(page, fixes):
        top = min(w["y"] for w in line)
        bottom = max(w["y"] + w["h"] for w in line)
        size = max(2.0, (bottom - top) * sy * 0.9)
        baseline = PAGE_H - bottom * sy + size * 0.2
        ops.append(b"/F1 %.2f Tf" % size)
        for word in line:
            data = word["t"].encode("cp1252", "ignore")
            natural = text_width(data) * size
            if not data or natural <= 0:
                continue
            stretch = 100.0 * (word["w"] * sx) / natural
            ops.append(b"%.1f Tz 1 0 0 1 %.2f %.2f Tm %s Tj"
                       % (stretch, word["x"] * sx, baseline, pdf_string(data + b" ")))
            count += 1
    ops.append(b"ET")
    return b"\n".join(ops), count


def main():
    jpg_dir, json_dir, out_path = sys.argv[1:4]
    corrections = {}
    for path in sys.argv[4:]:
        with open(path, encoding="utf-8") as handle:
            for page_number, fixes in json.load(handle).items():
                corrections.setdefault(page_number, []).extend(fixes)

    names = sorted(n for n in os.listdir(jpg_dir) if n.lower().endswith(".jpg"))
    objects = {}

    def put(number, body):
        objects[number] = body

    font, pages_obj, catalog, info = 1, 2, 3, 4
    put(font, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    words = 0
    for index, name in enumerate(names):
        with open(os.path.join(jpg_dir, name), "rb") as handle:
            jpeg = handle.read()
        width, height, components = jpeg_size(jpeg)
        if components != 3:
            raise ValueError("%s: %d components, expected RGB" % (name, components))
        with open(os.path.join(json_dir, os.path.splitext(name)[0] + ".json"), encoding="utf-8") as handle:
            page = json.load(handle)
        page["scan_width"] = width
        fixes = corrections.get(str(index + 1), [])
        text, count = page_text(page, fixes)
        words += count

        image, content, page_obj = 5 + index * 3, 6 + index * 3, 7 + index * 3
        put(image, b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                   b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (width, height, len(jpeg))
            + jpeg + b"\nendstream")
        stream = zlib.compress(b"q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q\n" % (PAGE_W, PAGE_H) + text, 9)
        put(content, b"<< /Filter /FlateDecode /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        put(page_obj, b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
                      b"/Resources << /XObject << /Im0 %d 0 R >> /Font << /F1 %d 0 R >> >> >>"
            % (pages_obj, PAGE_W, PAGE_H, content, image, font))
        kids.append(b"%d 0 R" % page_obj)

    put(pages_obj, b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), b" ".join(kids)))
    put(catalog, b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj)
    put(info, b"<< /Title (Star Wars: Knights of the Old Republic, Xbox manual) "
              b"/Subject (Scanned pages with a recognised text layer) >>")

    out = bytearray(b"%PDF-1.4\n%" + bytes([0xE2, 0xE3, 0xCF, 0xD3]) + b"\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj\n" % number + objects[number] + b"\nendobj\n"
    xref = len(out)
    total = max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % total
    for number in range(1, total):
        out += b"%010d 00000 n \n" % offsets[number]
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (total, catalog, info, xref)
    with open(out_path, "wb") as handle:
        handle.write(out)
    print("%d pages, %d words, %d bytes" % (len(names), words, len(out)))


if __name__ == "__main__":
    main()
