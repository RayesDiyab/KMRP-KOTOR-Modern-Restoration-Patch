#!/usr/bin/env python3
"""Controller remapping: compile and run its rules (K1ButtonRemapPolicy.h), and check the
tables the header shares with the tools: each button's Controller Layout row
(tools/build_controller_layout.py, LAYOUT) and its prompt picture
(tools/build_controller_layout.py, REMAP_GLYPHS). No game required; needs pykotor (run
with plain `python`)."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def header_list(text: str, name: str) -> list[str]:
    body = re.search(name + r"\[ButtonCount\] = \{(.*?)\};", text, re.S)[1]
    return [v.strip().strip('"') for v in body.replace("\n", " ").split(",") if v.strip()]


def main():
    header = (ROOT / "src/controller-native/K1ButtonRemapPolicy.h").read_text(encoding="utf-8")
    names = header_list(header, "ButtonNames")
    codes = header_list(header, "GlyphCodes")
    rows = [int(v) for v in header_list(header, "LayoutRow")]
    assert names == ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "L3", "R3"], names

    import build_controller_layout as layout
    glyphs = [g for g, _, _, _ in layout.LAYOUT]
    stick = {"L3": "LSTICK", "R3": "RSTICK"}
    for name, row in zip(names, rows):
        assert glyphs[row] == stick.get(name, name), f"{name}: row {row} is {glyphs[row]}"
    print(f"ok    each button's Controller Layout row matches LAYOUT ({len(rows)} buttons)")

    assert [(c, n) for c, n in layout.REMAP_GLYPHS] == list(zip(codes, names)), layout.REMAP_GLYPHS
    print("ok    each button's prompt picture is made by build_controller_layout.py's build_art")

    out = ROOT / "build/button-remap-check"
    out.mkdir(parents=True, exist_ok=True)
    vc = re.search(r"^set VC=(.+)$", (ROOT / "src/controller-native/build_native_runtime.cmd").read_text(), re.M)[1].strip()
    exe = out / "button-remap.exe"
    args = ["cl", "/nologo", "/O2", "/std:c++17", "/EHsc", "/W4", "/WX",
            str(ROOT / "testing/regression/button_remap_harness.cpp"), "/Fo" + str(out) + "/", "/Fe" + str(exe)]
    cmd = out / "build.cmd"
    cmd.write_text('@echo off\ncall "' + vc + '" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline(args) + "\nexit /b %errorlevel%\n", newline="\r\n")
    subprocess.run(["cmd", "/d", "/c", str(cmd)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=out, check=True)


if __name__ == "__main__":
    main()
