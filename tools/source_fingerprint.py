#!/usr/bin/env python3
"""The code of every Python file under the folders given, for build_kmrp.ps1's step cache.

build_kmrp.ps1 skips a slow step when nothing it reads has changed (Get-InputFingerprint).
It knew a file had changed by its size and time, so editing a comment in tools\\, which
every slow step imports, made all 66 interface sets again (half an hour until 2026-10-27).
This prints one line per .py file, its path and a SHA-256 of its parsed code with the
docstrings taken out: comments and docstrings change nothing it prints, any change to what
the code does changes its line. A file that does not parse is hashed as it is.

With --reach, a step's own entry tools, only what those reach counts in tools\\: 80 of the 136
files there have nothing to do with the build, and a line in any of them made the interface
sets again (audit S-10, 2026-11-01). A tool reaches what it imports, and any tools\\ file it
names as NAME.py, which is how it runs one as a program or loads it by path. That errs towards
counting too much: a name in a comment counts.

    python tools/source_fingerprint.py [--reach TOOL,TOOL] FOLDER...
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def without_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def code_hash(path: Path) -> str:
    data = path.read_bytes()
    try:
        tree = ast.parse(data, filename=str(path))
    except (SyntaxError, ValueError):
        return "raw:" + hashlib.sha256(data).hexdigest()
    return hashlib.sha256(ast.dump(without_docstrings(tree)).encode("utf-8")).hexdigest()


def reached(entries: list[str]) -> set[str]:
    """The tools ENTRIES reach, by name without .py."""
    seen: set[str] = set()
    todo = list(entries)
    while todo:
        name = todo.pop()
        path = TOOLS / f"{name}.py"
        if name in seen or not path.is_file():
            continue
        seen.add(name)
        text = path.read_text(encoding="utf-8", errors="replace")
        todo.extend(re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\.py\b", text))
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                todo.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                todo.append(node.module.split(".")[0])
    return seen


def main() -> int:
    arguments = sys.argv[1:]
    only: set[str] | None = None
    if arguments[:1] == ["--reach"]:
        only = reached(arguments[1].split(","))
        arguments = arguments[2:]
    for folder in arguments:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if only is not None and path.parent.resolve() == TOOLS and path.stem not in only:
                continue
            print(f"{str(path).lower()}|{code_hash(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
