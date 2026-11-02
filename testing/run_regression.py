#!/usr/bin/env python3
"""Run KMRP's regression tests and say exactly what ran, what passed and what did not.

Every test in testing/regression has a row below, so a new test with no row fails the run.
A run leaves testing's logs and summary.json in build/test-results/<name>, and --compare
names what changed against an earlier summary. Nothing here weakens a test: "skipped"
says why it could not run.

    python testing/run_regression.py                      everything this PC can run
    python testing/run_regression.py --group quick        the group build_kmrp.ps1 runs
    python testing/run_regression.py --only Test-TextRows Test-HudOptions
    python testing/run_regression.py --name baseline --compare build/test-results/x/summary.json

The groups: quick (no game files, under a minute or so each), full (needs the built resources
or the game), settings (borrows the player's installer settings and puts them back, so it
never runs at the same time as anything else), mac (needs macOS or the Mac executable).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "testing" / "regression"
STEAM_GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
CSC = Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe")
PWSH = "pwsh"
AUDIT_REPORT = ROOT / "build" / "test-results" / "gui-audit.md"
# Run alone, after the tests that can share the machine. The two asset tests build into one folder.
# Test-GuiAudit takes every core it can get, and timed out beside 12 others. The rest move the
# player's real settings aside for the run (Hide-KpmLauncherSettings): two side by side took
# the file from each other, one failed putting it back, and it was left in its work folder
# (2026-11-01, on going from 4 workers to 12). shared_settings() holds this list to the sources.
ONE_AT_A_TIME = {"Test-AssetPack", "Test-AssetPrepare", "Test-GuiAudit", "Test-DpiCompatibility",
                 "Test-LargeAddressAware", "Test-UpdateCheck", "Test-NvidiaPresentMethod", "Test-MovieResolution"}


def py(name, *args):
    return [sys.executable, str(REGRESSION / f"{name}.py"), *map(str, args)]


def ps(name, *args):
    return [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(REGRESSION / f"{name}.ps1"), *map(str, args)]


def cmd(name):
    return ["cmd", "/d", "/c", str(REGRESSION / f"{name}.cmd")]


def tool(name, *args):
    return [sys.executable, str(ROOT / "tools" / f"{name}.py"), *map(str, args)]


# name: (group, command, what the test needs, note)
TESTS = {
    "Test-AbilityIcons": ("full", py("Test-AbilityIcons", ROOT / "build-inputs/swpc_tex_gui.erf"), [], ""),
    "Test-AssetPack": ("quick", cmd("Test-AssetPack"), [], ""),
    "Test-AssetPrepare": ("full", py("Test-AssetPrepare"), [], ""),
    "Test-BadgeShape": ("quick", py("Test-BadgeShape"), [], ""),
    # Rebuilds KMRP about a dozen times, so only when asked for by name or group.
    "Test-BuildCache": ("build", ps("Test-BuildCache"), [], ""),
    "Test-LiveSuitePaths": ("quick", py("Test-LiveSuitePaths"), [], ""),
    "Test-OffscreenFrame": ("quick", py("Test-OffscreenFrame"), [], ""),
    "Test-RumbleMixer": ("quick", py("Test-RumbleMixer"), [], ""),
    "Test-ButtonRemap": ("quick", py("Test-ButtonRemap"), [], ""),
    "Test-ClassModelTrace": ("quick", py("Test-ClassModelTrace"), [], ""),
    "Test-ControllerGlyphs": ("full", py("Test-ControllerGlyphs"), [], ""),
    "Test-ControllerKpatch": ("quick", py("Test-ControllerKpatch"), [], ""),
    "Test-ControllerPreload": ("full", py("Test-ControllerPreload"), [STEAM_GAME], ""),
    "Test-ControllerPromptAssets": ("full", py("Test-ControllerPromptAssets"), [], ""),
    "Test-DpiCompatibility": ("full", ps("Test-DpiCompatibility"), [], ""),
    "Test-DriverCompatImports": ("quick", py("Test-DriverCompatImports"), [], ""),
    "Test-EngineFields": ("quick", py("Test-EngineFields"), [], ""),
    "Test-FontAtlasScale": ("full", py("Test-FontAtlasScale"), [], ""),
    "Test-GameArt": ("full", py("Test-GameArt", STEAM_GAME), [STEAM_GAME], ""),
    "Test-GeneratedGuiGeometry": ("full", py("Test-GeneratedGuiGeometry"), [], ""),
    "Test-GuiAudit": ("full", py("Test-GuiAudit", "--skip-build", "--report", AUDIT_REPORT), [], ""),
    "Test-GuiBlendHelper": ("full", py("Test-GuiBlendHelper"), [], ""),
    "Test-GuiModelPreload": ("quick", py("Test-GuiModelPreload"), [], ""),
    "Test-HudOptions": ("quick", py("Test-HudOptions"), [], ""),
    "Test-HudPress": ("quick", py("Test-HudPress"), [], ""),
    "Test-InstallerPatch": ("settings", ps("Test-InstallerPatch"), [], ""),
    "Test-KmrpLayoutPatch": ("mac", None, [], "needs the Mac executable"),
    "Test-KpatchSource": ("quick", py("Test-KpatchSource"), [], ""),
    "Test-LargeAddressAware": ("full", ps("Test-LargeAddressAware"), [], ""),
    "Test-LiveLayout": ("full", py("Test-LiveLayout"), [], ""),
    "Test-MacAppStore": ("mac", None, [], "needs the Mac package and executable"),
    "Test-MacAssets": ("mac", None, [], "needs the Mac bank"),
    "Test-MacFullscreen": ("mac", None, [], "runs kmrp-mac.sh's functions on macOS"),
    "Test-MacGuiNavigation": ("mac", None, [], "needs clang on macOS"),
    "Test-MacInstaller": ("mac", None, [], "needs the Mac package"),
    "Test-MacKpmOwnership": ("mac", None, [], "runs kmrp-mac.sh's functions on macOS"),
    "Test-MacMemorySafety": ("mac", None, [], "needs the Mac executable"),
    "Test-MacNavigationTrace": ("mac", None, [], "a log comparer, needs captured logs"),
    "Test-MacOptionsNavigation": ("mac", None, [], "built by the Mac tests"),
    "Test-MacStatusSummary": ("mac", None, [], "built by the Mac tests"),
    "Test-MacTextHeight": ("mac", None, [], "needs the Mac executable"),
    "Test-MiniGameFire": ("quick", py("Test-MiniGameFire"), [], ""),
    "Test-ModCompatibility": ("full", py("Test-ModCompatibility"), [], ""),
    "Test-MovieResolution": ("full", ps("Test-MovieResolution"), [], ""),
    "Test-NativeAssetsBank": ("full", py("Test-NativeAssetsBank"), [], ""),
    "Test-NativeTextLayout": ("quick", py("Test-NativeTextLayout"), [], ""),
    "Test-RuntimeRelayout": ("quick", py("Test-RuntimeRelayout"), [], ""),
    "Test-PictureKey": ("quick", py("Test-PictureKey"), [], ""),
    "Test-EngineAddresses": ("quick", py("Test-EngineAddresses"), [], ""),
    "Test-HandPrototypes": ("quick", py("Test-HandPrototypes"), [], ""),
    "Test-FontInfo": ("quick", py("Test-FontInfo"), [], ""),
    "Test-PadCarry": ("quick", py("Test-PadCarry"), [], ""),
    "Test-GameArtFailure": ("quick", py("Test-GameArtFailure"), [], ""),
    "Test-NvidiaPresentMethod": ("full", ps("Test-NvidiaPresentMethod"), [], ""),
    "Test-OverrideFontMetrics": ("quick", py("Test-OverrideFontMetrics"), [], ""),
    "Test-PartyRosterFixture": ("full", py("Test-PartyRosterFixture"),
                                [ROOT / "build/party-roster-check"], ""),
    "Test-PartyRosterGui": ("quick", py("Test-PartyRosterGui"), [], ""),
    "Test-PazaakActions": ("quick", py("Test-PazaakActions"), [], ""),
    "Test-ProtonResourceCompatibility": ("full", py("Test-ProtonResourceCompatibility"), [], ""),
    "Test-ResolutionGate": ("quick", py("Test-ResolutionGate"), [], ""),
    "Test-ReinstallOverOlderBuild": ("settings", ps("Test-ReinstallOverOlderBuild", "-OlderPatcher",
                                                    ROOT / "build/legacy/KMRP-standalone.exe"),
                                     [ROOT / "build/legacy/KMRP-standalone.exe"], ""),
    "Test-ResolutionDerivation": ("full", py("Test-ResolutionDerivation"), [], ""),
    "Test-ResourceFolder": ("quick", py("Test-ResourceFolder"), [], ""),
    "Test-SwoopPrompt": ("quick", py("Test-SwoopPrompt"), [], ""),
    "Test-TextFitPolicy": ("quick", py("Test-TextFitPolicy"), [], ""),
    "Test-TextLayoutRows": ("quick", py("Test-TextLayoutRows"), [], ""),
    "Test-TextOptions": ("quick", py("Test-TextOptions"), [], ""),
    "Test-TextRows": ("quick", py("Test-TextRows"), [], ""),
    "Test-UpdateCheck": ("full", ps("Test-UpdateCheck"), [], ""),
    "Test-WindowsEngineSource": ("full", py("Test-WindowsEngineSource", "--csc", CSC), [CSC], ""),
    "Test-WindowsKeyboardNavigation": ("quick", cmd("Test-WindowsKeyboardNavigation"), [], ""),
    "Test-Xpress": ("quick", py("Test-Xpress"), [], ""),
    "check_controller_drift": ("quick", tool("check_controller_drift"), [], ""),
    "check_links": ("quick", [sys.executable, str(ROOT / ".github/scripts/check_links.py")], [], ""),
}


def shared_settings():
    """Tests that touch a file of the player's or a setting of the machine, which must run alone."""
    marks = ("Hide-KpmLauncherSettings", "Restore-TestNvidiaProfiles", "KPatchLauncher", "HKCU:", "settings.json")
    found = []
    for path in REGRESSION.glob("Test-*.ps1"):
        name = path.stem
        if name in TESTS and TESTS[name][0] != "mac" and any(mark in path.read_text(encoding="utf-8", errors="replace") for mark in marks):
            found.append(name)
    return [n for n in found if TESTS[n][0] not in ("settings", "build") and n not in ONE_AT_A_TIME]


def unlisted():
    names = {p.stem for p in REGRESSION.glob("Test-*.*") if p.suffix in (".py", ".ps1", ".cmd", ".cpp")}
    return sorted(names - set(TESTS))


def run(name, folder, timeout):
    group, command, needs, note = TESTS[name]
    if command is None:
        return name, "skipped", 0.0, note
    for need in needs:
        if not Path(need).exists():
            return name, "skipped", 0.0, f"missing {need}"
    env = dict(os.environ)
    env["PATH"] = r"C:\Program Files\dotnet;" + env["PATH"]
    env.setdefault("PYTHONIOENCODING", "utf-8")
    start = time.time()
    log = folder / f"{name}.log"
    with log.open("w", encoding="utf-8", errors="replace") as out:
        try:
            code = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return name, "failed", timeout, f"timed out after {timeout} s"
    seconds = round(time.time() - start, 1)
    if code == 0:
        return name, "passed", seconds, ""
    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:] or [""]
    return name, "failed", seconds, f"exit {code}: {tail[0][:150]}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--group", action="append", choices=("quick", "full", "settings", "mac", "build"))
    parser.add_argument("--only", nargs="+", metavar="TEST")
    parser.add_argument("--name", default=time.strftime("%Y%m%d-%H%M%S"))
    # Tests with their own folder run side by side. On 16 cores the quick group took 71 s with
    # 4, 58 with 12 and 57 with 20, with the same results (2026-11-01). What shares a folder or
    # the player's settings, or times itself, runs alone (ONE_AT_A_TIME, settings and build groups).
    parser.add_argument("--jobs", type=int, default=min(12, os.cpu_count() or 4))
    parser.add_argument("--timeout", type=int, default=3000)
    parser.add_argument("--compare", type=Path, help="an earlier summary.json")
    args = parser.parse_args()
    missing = unlisted()
    if missing:
        print("These tests have no row in testing/run_regression.py:", ", ".join(missing))
        return 2
    together_by_mistake = shared_settings()
    if together_by_mistake:
        print("These tests touch the player's settings and are not run alone:", ", ".join(together_by_mistake))
        return 2
    if args.only:
        unknown = [n for n in args.only if n not in TESTS]
        if unknown:
            print("No such test:", ", ".join(unknown))
            return 2
        names = args.only
    else:
        groups = set(args.group or ("quick", "full", "settings", "mac"))
        names = [n for n, row in TESTS.items() if row[0] in groups]
    folder = ROOT / "build" / "test-results" / args.name
    folder.mkdir(parents=True, exist_ok=True)
    together = [n for n in names if TESTS[n][0] not in ("settings", "build") and n not in ONE_AT_A_TIME]
    alone = [n for n in names if TESTS[n][0] in ("settings", "build") or n in ONE_AT_A_TIME]
    results = []
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for result in pool.map(lambda n: run(n, folder, args.timeout), together):
            results.append(result)
            print(f"{result[1]:9} {result[2]:7.1f}  {result[0]}  {result[3]}", flush=True)
    for name in alone:
        result = run(name, folder, args.timeout)
        results.append(result)
        print(f"{result[1]:9} {result[2]:7.1f}  {result[0]}  {result[3]}", flush=True)
    revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    summary = {"revision": revision + ("+changes" if dirty else ""), "python": platform.python_version(),
               "results": {r[0]: {"state": r[1], "seconds": r[2], "note": r[3]} for r in results}}
    (folder / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    counts = {}
    for r in results:
        counts[r[1]] = counts.get(r[1], 0) + 1
    print(f"\n{revision}: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    print(f"logs: {folder}")
    if args.compare:
        before = json.loads(args.compare.read_text(encoding="utf-8"))["results"]
        for r in results:
            old = before.get(r[0], {}).get("state", "new")
            if old != r[1]:
                print(f"changed: {r[0]}: {old} -> {r[1]}")
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
