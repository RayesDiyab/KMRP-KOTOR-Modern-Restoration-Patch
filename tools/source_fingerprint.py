#!/usr/bin/env python3
"""The code of every Python file under the folders given, for build_kmrp.ps1's step cache.

build_kmrp.ps1 skips a slow step when nothing it reads has changed (Get-InputFingerprint).
It knew a file had changed by its size and time, so editing a comment in tools\\, which
every slow step imports, made all 66 interface sets again (half an hour until 2026-10-27).
This prints one line per .py file, its path and a SHA-256 of its parsed code with the
docstrings taken out: comments and docstrings change nothing it prints, any change to what
the code does changes its line. A file that does not parse is hashed as it is.

    python tools/source_fingerprint.py FOLDER...
"""
from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path


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


def main() -> int:
    for folder in sys.argv[1:]:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            print(f"{str(path).lower()}|{code_hash(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
