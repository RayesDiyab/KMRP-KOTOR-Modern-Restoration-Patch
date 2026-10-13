"""Writes the fixes for the contents list on PDF page 2: every recognised title
line gets its right text, the dot leaders and loose numbers go, and each row's
page number is added at the right edge.

    python make_toc_fix.py JSON_DIR OUT.json
"""
import json
import os
import sys

ROWS = [
    ("Connect to Xbox Live!", "02"), ("Setup", "04"), ("Controls", "05"), ("Introduction", "06"),
    ("Main Menu", "07"), ("Game Screen", "08"), ("In-Game Menus", "09"), ("Equip", "09"),
    ("Party Inventory", "11"), ("Character Info", "12"), ("Scripts", "13"), ("Abilities", "14"),
    ("Map/Party management", "15"), ("Quests", "16"), ("Messages", "16"), ("Options", "17"),
    ("Character Generation", "18"), ("Character Classes", "18"), ("Character Portrait", "19"),
    ("Attributes", "20"), ("Skills", "21"), ("Feats", "23"), ("Rules", "26"),
    ("Playing the Game", "27"), ("Mini Games", "32"), ("Pazaak", "32"),
    ("Ebon Hawk Gunner Station", "34"), ("Swoop Racing", "35"), ("Dialog", "36"),
    ("Advancing Levels", "37"), ("Jedi Classes", "37"), ("Force Powers", "38"),
    ("Core Force Powers", "38"), ("Light Side Force Powers", "39"), ("Dark Side Force Powers", "41"),
    ("Equipment", "43"), ("Weapons", "43"), ("Armor", "45"), ("States", "46"),
    ("How To Contact LucasArts", "50"), ("Credits", "52"), ("Software License/Limited Warranty", "56"),
]
FIRST_LINE, LAST_LINE = 36, 102


def main():
    with open(os.path.join(sys.argv[1], "p-001.json"), encoding="utf-8") as handle:
        page = json.load(handle)
    titles = {}
    fixes = []
    for index in range(FIRST_LINE, LAST_LINE + 1):
        line = page["lines"][index]
        x, y = line[0]["x"] / 2.0, line[0]["y"] / 2.0
        if x < 900 and line[0]["t"][0].isalpha():
            titles[index] = y
        else:
            fixes.append([index, ""])
    ordered = sorted(titles, key=titles.get)
    if len(ordered) != len(ROWS):
        raise SystemExit("%d title lines for %d rows" % (len(ordered), len(ROWS)))
    for index, (title, number) in zip(ordered, ROWS):
        line = page["lines"][index]
        text = " ".join(w["t"] for w in line)
        if text[:4].lower() != title[:4].lower():
            raise SystemExit("line %d %r is not %r" % (index, text, title))
        # Only the title's own words keep the box; a leader recognised as a word would widen it.
        keep = len(title.split(" "))
        fixes.append([index, 0, min(keep, len(line)), title])
        if len(line) > keep:
            fixes.append([index, keep, len(line) - keep, ""])
        fixes.append({"add": [1032, round(titles[index]) + 1, 15, 13], "t": number})
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        json.dump({"2": fixes}, handle, indent=1)
    print(len(fixes), "fixes")


if __name__ == "__main__":
    main()
