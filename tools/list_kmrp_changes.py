#!/usr/bin/env python3
"""Every place KMRP changes the game, as one list for the 1.6 cleanup audit (issue 82).

Reads, never writes anything but the list:

  * the KOTOR Patch Manager hooks of every patch the installer can put in, from the
    patch_config.toml sections the build makes (build/kmrp/kpm-config/*.hooks.toml), each
    with the comment above it in its source table and where its handler is defined;
  * the engine recipe kmrp.dll applies in memory (tools/build_windows_engine.py): every
    byte run, the resolution operands written at each mode change, and the block;
  * the writes KMRP's modules make themselves at run time (import and vtable slots,
    hot patches, engine globals), a hand-kept table below, checked against the sources;
  * the native modules' sources by size.

Run after a build (build_kmrp.ps1), from the repository:

    python tools/list_kmrp_changes.py --out docs/cleanup-audit-1.6.md

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

CONFIG = ROOT / "build/kmrp/kpm-config"
NATIVE = ROOT / "src/controller-native"

# patch id, its config file, who wrote it, where its hooks' comments are.
PATCHES = [
    ("kmrp", "kmrp.hooks.toml", "KMRP",
     [NATIVE / "kotor1.hooks.toml", NATIVE / "kotor1-native-runtime.hooks.toml", ROOT / "tools/build_native_kpatch.py"]),
    ("kmrp-controller", "kmrp-controller.hooks.toml", "KMRP",
     [NATIVE / "kotor1.hooks.toml", ROOT / "tools/build_controller_kpatch.py", ROOT / "tools/kmrp_controller.py"]),
    ("high-fps-fixes", "high-fps-fixes.hooks.toml", "D3M0 (bundled, unchanged)", []),
    ("k1-marked-empty-containers", "k1-marked-empty-containers.hooks.toml", "ShaeMyName (bundled, unchanged)", []),
    ("k1-modern-driver-compatibility", "k1-modern-driver-compatibility.hooks.toml", "Synchro (bundled, unchanged)", []),
]

# Writes KMRP's modules make at run time outside KOTOR Patch Manager: what, where in the
# game, the code that does it. Kept by hand; main() checks each source still names the
# address or function.
RUNTIME_WRITES = [
    ("engine recipe: every byte run below, the block and its relocations", "see section 2",
     "K1RuntimeEngine.cpp", "void InitializeEngineAt("),
    ("resolution operands at each mode change (section 2.2)", "see section 2.2",
     "K1RuntimeEngine.cpp", "bool CommitEngineAt(int width, int height)"),
    ("start size in the game's own resolution checks", "0x005F0FB2, 0x005F5B84",
     "K1RuntimeResolution.cpp", "WriteSize(0x005F0FB2"),
    ("EnumDisplaySettingsA import slot, the display's modes filtered", "0x0073D3E4",
     "K1RuntimeResolution.cpp", "0x0073D3E4"),
    ("CSWGuiInGameSkillEntry::SetExtent vtable slot (issue 80 icons)", "0x00755ED4",
     "K1RuntimeLayout.cpp", "0x00755ED0"),
    ("CSWGuiAbilityChain::SetExtent vtable slot (issue 80 icons)", "0x007578AC",
     "K1RuntimeLayout.cpp", "0x007578A8"),
    ("SwapBuffers import slot, the offscreen frame (issue 14)", "the game's gdi32 SwapBuffers slot",
     "K1OffscreenFrame.cpp", "&SwapForGame"),
    ("opengl32 hot patches: glCopyTexImage2D, glCopyTexSubImage2D, glReadPixels, wglGetProcAddress, wglMakeCurrent",
     "opengl32.dll", "K1OffscreenFrame.cpp", "HotPatch("),
    ("joystick deadzone float set to 0 (KMRP's radial deadzone instead)", "K1_JOY_MIN_USEABLE",
     "K1NativeJoystick.cpp", "K1_JOY_MIN_USEABLE"),
    ("the game's cached hardware-mipmap answer set to 1 under K1DC", "0x0078E538",
     "K1CoreFrames.cpp", "int* const answer = reinterpret_cast<int*>(0x0078E538);"),
]


def hook_comments(paths: list[Path]) -> dict[int, tuple[str, str]]:
    """Address -> (the comment above its [[hooks]] or dict, file:line), first source wins."""
    found: dict[int, tuple[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.search(r"address\s*[=:]\s*'?(0x[0-9A-Fa-f]{6,8})", line)
            if not m:
                continue
            address = int(m.group(1), 16)
            if address in found:
                continue
            # Walk up past the [[hooks]] line to the comment block above it.
            j = i - 1
            while j >= 0 and lines[j].strip() and not lines[j].lstrip().startswith("#") and "[[hooks]]" not in lines[j] \
                    and not lines[j].lstrip().startswith("{"):
                j -= 1
            if j >= 0 and ("[[hooks]]" in lines[j] or lines[j].lstrip().startswith("{")):
                j -= 1
            comment = []
            while j >= 0 and lines[j].lstrip().startswith("#"):
                comment.insert(0, lines[j].lstrip("# ").rstrip())
                j -= 1
            text = " ".join(c for c in comment if c)
            found[address] = (text, f"{path.relative_to(ROOT).as_posix()}:{i + 1}")
    return found


def module_sources(script: str) -> list[Path]:
    """The .cpp files a module's build script compiles (build_native_runtime.cmd for
    kmrp.dll, build_controller_standalone.cmd for the controller patch's module)."""
    text = (NATIVE / script).read_text(encoding="utf-8")
    names = set(re.findall(r"([\w]+\.cpp)", text))
    return sorted(p for p in list(NATIVE.glob("*.cpp")) if p.name in names)


def definitions(files: list[Path]) -> dict[str, str]:
    """Exported function name -> file:line where it is defined, in one module's sources:
    the same name is defined once per module, and the two modules build different files."""
    found: dict[str, str] = {}
    pattern = re.compile(r"^(?:extern \"C\"\s+)?(?:[\w:<>*&]+\s+)+(?:__cdecl\s+|__stdcall\s+|__fastcall\s+|WINAPI\s+)?(\w+)\s*\(")
    for path in files:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            if line.startswith((" ", "\t", "//", "#")) or line.rstrip().endswith(";"):
                continue
            m = pattern.match(line)
            if m and m.group(1) not in found:
                found[m.group(1)] = f"{path.relative_to(ROOT).as_posix()}:{i + 1}"
    return found


def short(text: str, n: int = 140) -> str:
    text = text.replace("|", "/").strip()
    return text if len(text) <= n else text[:n - 3].rstrip() + "..."


def kpm_section(out: list[str]) -> int:
    import build_native_kpatch
    module_defs = {"kmrp": definitions(module_sources("build_native_runtime.cmd")),
                   "kmrp-controller": definitions(module_sources("build_controller_standalone.cmd"))}
    when = {h["address"]: c for h, c in build_native_kpatch.option_hooks()}
    total = 0
    out.append("## 1. KOTOR Patch Manager hooks\n")
    out.append("From the `patch_config.toml` sections the build makes. A bundled patch of another "
               "author is listed for overlap and timing only: its code is not KMRP's to change.\n")
    for patch_id, name, author, sources in PATCHES:
        config = tomllib.loads((CONFIG / name).read_text(encoding="utf-8"))
        # A section is "[[patches.hooks]]" blocks without their "[[patches]]" header.
        patches = config["patches"]
        hooks = patches.get("hooks", []) if isinstance(patches, dict) else \
            [h for p in patches for h in p.get("hooks", [])]
        comments = hook_comments(sources)
        total += len(hooks)
        out.append(f"### 1.{PATCHES.index((patch_id, name, author, sources)) + 1} `{patch_id}`, {len(hooks)} hooks ({author})\n")
        if not sources:
            out.append("| # | address | type | function | params | audit |")
            out.append("| --- | --- | --- | --- | --- | --- |")
            for n, h in enumerate(sorted(hooks, key=lambda h: h["address"]), 1):
                out.append(f"| {n} | `0x{h['address']:08X}` | {h['type']} | `{h.get('function', '')}` | "
                           f"{len(h.get('parameters', []))} | n/a: theirs |")
            out.append("")
            continue
        out.append("| # | address | type | function | defined in | when | params | what it is for | audit |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        defs = module_defs[patch_id]
        for n, h in enumerate(sorted(hooks, key=lambda h: h["address"]), 1):
            fn = h.get("function", "")
            comment, at = comments.get(h["address"], ("", ""))
            cond = when.get(h["address"]) if patch_id == "kmrp" else None
            out.append(f"| {n} | `0x{h['address']:08X}` | {h['type']} | `{fn}` | "
                       f"{('`' + defs[fn] + '`') if fn in defs else ''} | {cond or 'always'} | "
                       f"{len(h.get('parameters', []))} | {short(comment) or '(no comment)'} | [ ] |")
        out.append("")
    return total


def recipe_section(out: list[str]) -> int:
    import build_windows_engine as engine
    import build_native_engine
    _, recipe, relocations, _ = engine.build()
    runs = recipe.runs()
    names = {1: "core", 2: "movies", 4: "map notes", 8: "movie display mode"}
    sources = [ROOT / "tools" / p for p in ("build_windows_engine.py", "build_native_engine.py")] + \
              sorted((ROOT / "tools").glob("*.py"))
    texts = {p: p.read_text(encoding="utf-8", errors="replace").splitlines() for p in dict.fromkeys(sources)}

    def where(va: int) -> str:
        keys = (f"0x{va:X}".lower(), f"0x{va:08X}".lower(), f"0x{va:06X}".lower())
        for path, lines in texts.items():
            for i, line in enumerate(lines):
                low = line.lower()
                if any(re.search(re.escape(k) + r"(?![0-9a-f])", low) for k in keys):
                    return f"{path.relative_to(ROOT).as_posix()}:{i + 1}"
        return ""

    out.append("## 2. The engine recipe (applied in memory by `kmrp.dll`)\n")
    out.append(f"{len(runs)} byte runs in the game's own code and data, the {engine.BLOCK_SIZE:#x}-byte block at "
               f"`{engine.BLOCK_VA:#010x}` (KMRP's added code, copied wherever it can be allocated) and "
               f"{len(relocations[0]) if isinstance(relocations, tuple) else len(relocations)} relocated fields. "
               "Section 4 of `reverse-engineering/binary-inventory.md` names the documents for each run.\n")
    out.append("| # | VA | len | feature | first named in | audit |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for n, (feature, va, old, new) in enumerate(runs, 1):
        out.append(f"| {n} | `0x{va:08X}` | {len(old)} | {names.get(feature, feature)} | `{where(va)}` | [ ] |")
    fields = build_native_engine.resolution_fields()
    out.append("\n### 2.2 Resolution operands, written again at every mode change\n")
    out.append("| # | VA | size | kind | base |")
    out.append("| --- | --- | --- | --- | --- |")
    for n, (va, size, kind, base) in enumerate(fields, 1):
        out.append(f"| {n} | `0x{va:08X}` | {size} | {kind} | {base} |")
    out.append("")
    return len(runs) + len(fields)


def runtime_section(out: list[str]) -> int:
    out.append("## 3. Writes KMRP's modules make themselves at run time\n")
    out.append("| # | what | where in the game | done by | audit |")
    out.append("| --- | --- | --- | --- | --- |")
    for n, (what, where, file, needle) in enumerate(RUNTIME_WRITES, 1):
        path = NATIVE / file
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        hit = next((i for i, line in enumerate(lines) if needle in line), None)
        if hit is None:
            raise SystemExit(f"{file} no longer names {needle!r}: update RUNTIME_WRITES")
        out.append(f"| {n} | {what} | {where} | `src/controller-native/{file}:{hit + 1}` | [ ] |")
    out.append("")
    return len(RUNTIME_WRITES)


def modules_section(out: list[str]) -> None:
    out.append("## 4. The native modules' sources, largest first\n")
    out.append("Which module each file is built into is in `build_native_runtime.cmd` and "
               "`build_controller_standalone.cmd`.\n")
    runtime = (NATIVE / "build_native_runtime.cmd").read_text(encoding="utf-8")
    controller = (NATIVE / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    files = [p for p in list(NATIVE.glob("*.cpp")) + list(NATIVE.glob("*.h")) + list(NATIVE.glob("*.inc"))
            ]
    rows = sorted(((sum(1 for _ in p.open(encoding="utf-8", errors="replace")), p) for p in files), reverse=True)
    out.append("| lines | file | in kmrp.dll | in kmrp-controller.dll | audit |")
    out.append("| --- | --- | --- | --- | --- |")
    for count, p in rows:
        rel = p.relative_to(NATIVE).as_posix()
        name = p.name
        out.append(f"| {count} | `{rel}` | {'yes' if name in runtime else ''} | {'yes' if name in controller else ''} | [ ] |")
    out.append("")


def keep_audit(path: Path, body: list[str]) -> list[str]:
    """The audit column filled in by hand survives a new run: each table row is known by
    its section and its second column (the address, VA, write or file)."""
    def rows(lines):
        heading = ""
        for line in lines:
            if line.startswith("#"):
                heading = line
            elif line.startswith("| ") and line.endswith(" |") and not line.startswith("| ---"):
                cells = [c.strip() for c in line[2:-2].split(" | ")]
                if len(cells) > 2 and cells[0] != "#":
                    yield heading, cells, line
    if not path.exists():
        return body
    done = {(h, c[1]): c[-1] for h, c, _ in rows(path.read_text(encoding="utf-8").splitlines()) if c[-1] != "[ ]"}
    result = []
    heading = ""
    for line in body:
        if line.startswith("#"):
            heading = line.rstrip("\n")
        if line.startswith("| ") and line.endswith(" | [ ] |"):
            cells = [c.strip() for c in line[2:-2].split(" | ")]
            if len(cells) > 2 and (heading, cells[1]) in done:
                line = line[: -len("[ ] |")] + done[(heading, cells[1])] + " |"
        result.append(line)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: list[str] = []
    body: list[str] = []
    hooks = kpm_section(body)
    recipe = recipe_section(body)
    runtime = runtime_section(body)
    modules_section(body)
    out.append("# The 1.6 cleanup audit: every place KMRP changes the game\n")
    out.append("> **Documentation standard.** This document follows "
               "[`documentation-standard.md`](documentation-standard.md).\n")
    out.append("**Kind: reference, generated.** Made by `tools/list_kmrp_changes.py` from the build "
               "(issue 82); run it again rather than editing the tables. The audit column is filled by hand.\n")
    out.append(f"In all: {hooks} KPM hooks across five patches, {recipe} engine recipe runs and resolution "
               f"operands, and {runtime} kinds of run-time write.\n")
    out.extend(keep_audit(args.out, body))
    args.out.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.out}: {hooks} hooks, {recipe} recipe entries, {runtime} run-time writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
