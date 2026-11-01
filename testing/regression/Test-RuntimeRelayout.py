#!/usr/bin/env python3
"""A change of size, on K1RuntimeLayout.cpp itself, with no game (audit GUI-3, GUI-4).

runtime_relayout_harness.cpp includes the shipped file and hands it panels made of plain
memory. This writes the small layout files it reads. Covered: the Container's widening is
not taken for the engine's addition, an odd layout file costs only its own panel, the engine's
real additions stay and scale, and a round trip returns the same pixels. The other half of the
Container, the fit itself, is in native_text_layout_harness.cpp. What the engine's own
SetExtent does with these numbers needs the game.
Run: python testing/regression/Test-RuntimeRelayout.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
sys.path.insert(0, str(ROOT / "tools"))

from pykotor.resource.formats.gff import GFF, GFFContent, GFFFieldType, GFFList, GFFStruct, write_gff
from pykotor.resource.type import ResourceType


def extent(owner, rect):
    box = owner.set_struct("EXTENT", GFFStruct())
    for name, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), rect):
        box.set_int32(name, value)


def layout(path, root, controls):
    gff = GFF(GFFContent.GUI)
    if root:
        extent(gff.root, root)
    gff.root.set_string("TAG", path.stem)
    rows = gff.root.set_list("CONTROLS", GFFList())
    for tag, rect in controls.items():
        row = rows.add(0)
        row.set_string("TAG", tag)
        row.set_int32("CONTROLTYPE", 6)
        extent(row, rect)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gff, path, ResourceType.GUI)


def main():
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        for size, scale in (("1280x720", 1), ("1920x1080", 1.5)):
            at = lambda *v: tuple(int(n * scale) for n in v)
            folder = out / size
            layout(folder / "container.gui", at(340, 160, 600, 400), {
                "BTN_OK": at(20, 340, 100, 40), "BTN_GIVEITEMS": at(160, 340, 100, 40), "LB_ITEMS": at(20, 40, 560, 280)})
            layout(folder / "optmain.gui", at(340, 160, 600, 400), {"BTN_FIRST": at(20, 100, 100, 40)})
            # A file with no root extent, which is what GUI-3's `return false` stopped at.
            layout(folder / "brokenroot.gui", None, {"X": at(0, 0, 10, 10)})
        exe = out / "runtime-relayout.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", f"/I{SRC}", "/DUNICODE", "/D_UNICODE",
                str(Path(__file__).with_name("runtime_relayout_harness.cpp")), "user32.lib", "kernel32.lib",
                f"/Fo{out}\\", f"/Fe{exe}"]
        script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\nexit /b %errorlevel%\n",
                          encoding="utf-8", newline="\r\n")
        built = subprocess.run(["cmd", "/d", "/c", str(script)], cwd=ROOT, capture_output=True, text=True, errors="replace")
        if built.returncode:
            print(built.stdout[-3000:], built.stderr[-1000:])
            print("FAIL the harness did not build")
            return 1
        run = subprocess.run([str(exe), str(out)], capture_output=True, text=True, errors="replace")
        print(run.stdout)
        print("PASSED" if run.returncode == 0 else "FAILED")
        return run.returncode


if __name__ == "__main__":
    sys.exit(main())
