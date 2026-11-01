#!/usr/bin/env python3
"""A function another file defines is declared in a header, not by hand (audit S-8).

A prototype copied into a .cpp keeps compiling when the definition's signature changes, and the
call then goes wrong in the running game; the same line in a header the definition includes
stops the build. The only ones allowed are the test seams, named *Test*, which the harnesses
define in place of the engine. No game runs.
Run: python testing/regression/Test-HandPrototypes.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
TOOLS = ROOT / "macos/tools"

WORD = r"[A-Za-z_][\w:<>,]*"
TYPE = rf"(?:extern\s+\"C\"\s+|extern\s+)?(?!return\b|else\b|new\b|delete\b|using\b|typedef\b|throw\b|goto\b|case\b){WORD}(?:[\s\*&]+{WORD})*[\s\*&]+"
DECLARATION = re.compile(rf"^[ \t]*{TYPE}(?:__\w+\s+)?(\w+)\(([^;{{}}()]*)\)[ \t]*;", re.M)
DEFINITION = re.compile(rf"^(?:extern\s+\"C\"\s+)?{WORD}(?:[\s\*&]+{WORD})*[\s\*&]+(?:__\w+\s+)?(\w+)\(([^;{{}}]*)\)\s*(?:noexcept\s*)?\{{", re.M)
PARAMETERS = re.compile(r"\b(void|int|char|bool|float|unsigned|long|const|std::|size_t)\b|\w+\*")


def code_of(path):
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    return "\n".join(line.split("//")[0] for line in text.splitlines())


def main():
    sources = {path: code_of(path) for path in sorted(SRC.glob("*.cpp"))}
    defined = {path: {m.group(1) for m in DEFINITION.finditer(text)} for path, text in sources.items()}
    # A probe of the pattern itself, against a file known to hold definitions.
    if "KmrpUpdatePromptsK1" not in defined[SRC / "K1XboxControls.cpp"]:
        print("FAIL the definition pattern has stopped matching")
        return 1
    failed = False
    count = 0
    for path, text in sources.items():
        for match in DECLARATION.finditer(text):
            name, parameters = match.group(1), match.group(2).strip()
            if name in ("if", "while", "for", "switch", "sizeof"):
                continue
            # With arguments that are not types this is a variable being constructed.
            if parameters and not PARAMETERS.search(parameters):
                continue
            count += 1
            if name in defined[path] or "Test" in name:
                continue
            line = text.count("\n", 0, match.start()) + 1
            print(f"FAIL {path.name}:{line} declares {name} by hand: it belongs in a header")
            failed = True
    for tool in ("guiblend", "abilityicons", "gameart", "swoophud", "guiadapt", "merge"):
        if '#include "kmrp-embedded.h"' not in (TOOLS / f"kmrp-{tool}.c").read_text(encoding="utf-8"):
            print(f"FAIL kmrp-{tool}.c does not include kmrp-embedded.h, so nothing checks its prototypes")
            failed = True
    if failed:
        return 1
    print(f"PASS {count} declarations in .cpp files, none for another file's function")
    return 0


if __name__ == "__main__":
    sys.exit(main())
