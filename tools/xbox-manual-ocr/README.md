# The Xbox manual's text layer

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../../docs/documentation-standard.md).

**Kind: reference.** How the searchable text of
[`docs/reference/kotor-xbox-manual.pdf`](../../docs/reference/kotor-xbox-manual.pdf)
was made, and how to make it again. Built and verified on 2026-10-13 on Windows 11
with Python 3.14 and the `pdfimages` of the TeX Live 2021 xpdf tools.

The PDF is 30 scans of two manual pages each (1360 x 1087 JPEG, 150 dpi), which
had no text. Each scan is embedded as it was, byte for byte, and the text is drawn
over it invisibly. The printed page is the authority; the layer is for searching
and copying.

## The files

| File | What it is |
| --- | --- |
| `Read-PageText.ps1` | Runs the recogniser built into Windows (`Windows.Media.Ocr`, en-US) on page images and writes every word with its box. Windows PowerShell 5.1 only. |
| `recognised/p-000.json` to `p-029.json` | What it read from the scans enlarged to twice their size (Lanczos). Kept, uncorrected, because the fixes name its lines by number. |
| `fixes/*.json` | The corrections made by hand, per PDF page: a line or some of its words replaced or removed, a missed line added with its box in scan pixels, and the column edges of a page that is not two plain pages. The forms are described at `corrected_lines` in the builder. |
| `make_toc_fix.py` | Wrote `fixes/fixb-02-toc.json`, the contents list with its page numbers. |
| `build_searchable_pdf.py` | Builds the PDF from the scans, the recognised words and the fixes, in reading order. |
| `compare_passes.py` | Lists the words on which two recognition passes disagree. |
| `check_layer.py` | Lists what a second pass saw where the finished layer has nothing, and words that do not look like words. |
| `dump_fixed.py`, `crop.py` | For proofreading: a page's text after the fixes, and an enlarged piece of a scan. |

## Building it again

The scans come out of the PDF itself, so nothing else is needed:

```
pdfimages -j docs/reference/kotor-xbox-manual.pdf SCANS/p
python tools/xbox-manual-ocr/build_searchable_pdf.py SCANS tools/xbox-manual-ocr/recognised OUT.pdf <every file in fixes/, by name>
```

Run this way on 2026-10-13, with the fifteen fix files in alphabetical order, the
output was the committed file: 10,430,681 bytes, SHA-256
`64f0ed1cd7d608471350f179fde4424dcd44e63715a92da6460063b59d92c49b`. The order of
the fix files only matters within one page, and no two files that share a page
touch the same words.

Running the recogniser again is not needed and may not give the same lines on
another Windows build; the fixes would then name the wrong ones.

## How the text was checked

- Every heading, label and legend in the manual's two display fonts was typed in
  beside the page; the recogniser read none of them.
- A second pass on the scans at three times their size was compared with the
  first, and every disagreement settled beside the page.
- Every line of every page was read after the fixes. The cover's small print, both
  credits pages and the licence page were read beside crops enlarged 2.2 to 3 times.
- All 30 scans extracted from the result were compared with the originals: identical.
- The controls list on manual page 5 and the Action menu paragraph on page 8 were
  checked word for word.

## What is not certain

- The body text of PDF pages 4 to 27 was read beside the whole page, not beside
  enlarged crops. A word both passes misread the same way into another real word
  would not have been noticed.
- The text inside the screenshots is not in the layer.
- Misprints are kept as printed: "pattens", "Froce", "Cyroban".
- Lines added by hand were placed by eye; a selection can sit a few pixels off.
