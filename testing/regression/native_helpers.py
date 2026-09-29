"""Builds the macOS installer's C helpers for the tests that compare them with the
Windows installer's C# (Test-AbilityIcons.py, Test-GameArt.py).

On macOS each helper is built for x86_64 and arm64, and the tests compare both slices.
On Windows -- where these tests run too since 2026-09-29, with clang from LLVM and the
.NET 8 SDK -- clang builds one x64 helper. The helpers are POSIX C, so a shim stands in
for <strings.h> and for mkdir's second argument, and paths go to them with forward
slashes, since they split paths on "/" only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"


def build(source: Path, out_dir: Path, name: str, flags: tuple[str, ...] = ()) -> dict[str, Path]:
    """The helper at `source`, built into `out_dir`: {slice name: executable}."""
    if not WINDOWS:
        helpers = {}
        for arch in ("x86_64", "arm64"):
            helpers[arch] = out_dir / f"{name}-{arch}"
            subprocess.run(["clang", "-O2", *flags, "-arch", arch, "-o", str(helpers[arch]), str(source)],
                           check=True)
        return helpers
    shim = out_dir / "posix-shim"
    shim.mkdir(exist_ok=True)
    (shim / "strings.h").write_text(
        "#include <string.h>\n#define strcasecmp _stricmp\n#define strncasecmp _strnicmp\n", encoding="ascii")
    (shim / "posix.h").write_text(
        "#include <direct.h>\n#define mkdir(path, mode) _mkdir(path)\n", encoding="ascii")
    helper = out_dir / f"{name}-x64.exe"
    subprocess.run(["clang", "-O2", *flags, "-D_CRT_SECURE_NO_WARNINGS", "-D_CRT_NONSTDC_NO_DEPRECATE",
                    "-I", str(shim), "-include", str(shim / "posix.h"), "-o", str(helper), str(source)],
                   check=True)
    return {"x64": helper}


def arg(path: Path) -> str:
    """A path as the helpers take one: with forward slashes, which Windows accepts too."""
    return path.as_posix()


def slices(helpers: dict[str, Path]) -> str:
    return " and ".join(helpers)
