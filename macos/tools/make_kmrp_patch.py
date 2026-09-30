#!/usr/bin/env python3
"""Build KMRP for macOS as one KotOR Patch Manager patch, `kmrp`.

The patch is FTD's two patches, built from their source as KPM's Patches/create-patch.py builds
them, with KMRP's own code linked into the same module:

    K1WidescreenPatch   FTD, RaymanGT, J, Vriff (MIT): the resolution, and with
                        UseGuiFileLayouts=1 no layout of its own
    K1StrayBugFixes     RaymanGT, FTD (MIT): the engine fixes that hold at any resolution
    kmrp-layout         KMRP: the sizes, lists, popups and map of KMRP's menu layouts
    kmrp-map-notes      KMRP: Derslok's map-note corrections (optional)
    kmrp-controller     KMRP: controller support (optional)

One patch rather than five (2026-09-30, with FTD's agreement): KMRP replaces an install of FTD's
patches instead of building on it, so a player sees one patch, and KPM never has two of them
hooking one place.

The module: each part's sources compiled with that part's own flags (FTD's with
create-patch.py's Mac flags), then linked in the order above. The order matters: a module's
constructors run in link order, and FTD's DylibInit must run before KMRP's ApplyLayoutSupport:
with UseGuiFileLayouts it puts some of its byte hooks back to vanilla, where the layout patch then
writes KMRP's values. The built module is checked for that order.

The hook list: every part's hooks, all byte hooks first and all detours last, each group in the
order above. KotorPatcher applies hooks in file order and loads the module at the first detour,
whose constructors rewrite byte hooks already applied; a byte hook after a detour would then fail
its check and stop every hook behind it (FTD's note in K1WidescreenPatch's hook file). A hook two
parts declare identically is kept once (FTD's branch declared the Stray Bug Fixes' 11 hooks in
both his patches on 2026-09-30); two different hooks at one address stop the build.

    python macos/tools/make_kmrp_patch.py --widescreen DIR --stray DIR --layout DIR
        --notes DIR --notes-include DIR --controller DIR --sdl DIR --version X.Y.Z
        [--no-map-notes] [--no-controller] --out FILE.kpatch
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

HOOKS_FILE = "kotor1-steam-aspyr-macos.hooks.toml"
GAME_SHA = "C1FCB8D37C702849882A17751C63EE0AF7C2B9CBBC3B31B98A5F0EDBC27C6D71"

# create-patch.py's Mac toolchain (KPM's Patches/create-patch.py, PATCH_TOOLCHAINS), for FTD's parts.
FTD_FLAGS = ["-arch", "x86_64", "-O2", "-fPIC", "-mmacosx-version-min=10.9", "-fno-exceptions", "-fno-rtti"]
# macos/build.sh's flags for KMRP's patches, as they were built as patches of their own.
LAYOUT_FLAGS = ["-arch", "x86_64", "-std=c++17", "-O2", "-mmacosx-version-min=10.9", "-w"]
CONTROLLER_FLAGS = ["-arch", "x86_64", "-std=c++17", "-O2", "-mmacosx-version-min=10.13", "-Wall", "-Wextra",
                    "-Wno-#warnings", "-fobjc-arc"]
LINK_FLAGS = ["-arch", "x86_64", "-dynamiclib", "-mmacosx-version-min=10.13", "-framework", "OpenGL",
              "-Wl,-dead_strip_dylibs", "-install_name", "@executable_path/macos_x86_64.dylib"]
CONTROLLER_LINK = ["-fobjc-arc", "-fobjc-link-runtime", "-framework", "Foundation", "-framework", "AppKit",
                   "-framework", "ApplicationServices", "-weak_framework", "GameController"]


def fail(message: str) -> None:
    raise SystemExit(f"make_kmrp_patch: {message}")


def sources(directory: Path, patterns: tuple[str, ...]) -> list[Path]:
    """create-patch.py's find_sources: the folder and one level below, sorted."""
    return sorted(p for pattern in patterns for p in (*directory.glob(pattern), *directory.glob(f"*/{pattern}")))


def compile_part(files: list[Path], flags: list[str], objects: Path, tag: str) -> list[Path]:
    out = []
    for source in files:
        obj = objects / f"{tag}-{source.parent.name}-{source.stem}.o"
        result = subprocess.run(["clang++", *flags, "-c", str(source), "-o", str(obj)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"{source}: does not compile\n{result.stderr}")
        out.append(obj)
    return out


# ---------------------------------------------------------------------------------- hooks
class Hook:
    def __init__(self, part: str, prefix: list[str], body: list[str]):
        self.part, self.prefix, self.body = part, prefix, body
        head = []
        for line in body:
            if line.strip().startswith("[[hooks.parameters]]"):
                break
            head.append(line)
        kind = next((m.group(1) for line in head if (m := re.match(r'\s*type\s*=\s*"(\w+)"', line))), None)
        address = next((m.group(1) for line in head if (m := re.match(r"\s*address\s*=\s*(0x[0-9a-fA-F]+|\d+)", line))), None)
        if kind is None or address is None:
            fail(f"{part}: a hook without an address or a type:\n" + "\n".join(body))
        self.kind, self.address = kind, int(address, 0)
        self.key = [re.sub(r"\s+", "", line.split("#", 1)[0]).lower() for line in body]
        self.key = [line for line in self.key if line]

    def text(self) -> str:
        return "\n".join([*self.prefix, "[[hooks]]", *self.body]).rstrip() + "\n"


def read_hooks(part: str, path: Path) -> list[Hook]:
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[hooks]]"]
    hooks, carried = [], []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[start + 1:end]
        # Comments at the end of a block describe the next hook: they go with it.
        last = max((i for i, line in enumerate(body) if line.strip() and not line.strip().startswith("#")), default=-1)
        trailing = body[last + 1:]
        hooks.append(Hook(part, carried, body[:last + 1]))
        carried = [line for line in trailing if line.strip()]
    doc = tomllib.loads(path.read_text())
    if len(doc.get("hooks", [])) != len(hooks):
        fail(f"{path}: read {len(hooks)} hooks, TOML has {len(doc.get('hooks', []))}")
    return hooks


def merge_hooks(parts: list[tuple[str, Path]]) -> tuple[str, int, int]:
    seen: dict[int, Hook] = {}
    kept: list[Hook] = []
    duplicates = 0
    for part, directory in parts:
        for hook in read_hooks(part, directory / HOOKS_FILE):
            if hook.address in seen:
                if seen[hook.address].key != hook.key:
                    fail(f"{seen[hook.address].part} and {part} hook {hook.address:#x} differently")
                duplicates += 1
                continue
            seen[hook.address] = hook
            kept.append(hook)
    ordered = [h for h in kept if h.kind != "detour"] + [h for h in kept if h.kind == "detour"]
    names = ", ".join(part for part, _ in parts)
    text = (
        "# KMRP for macOS: one patch, merged by macos/tools/make_kmrp_patch.py from " + names + ".\n"
        "# All byte hooks first, then all detours: the first detour loads the module, whose\n"
        "# constructors rewrite byte hooks already applied (see make_kmrp_patch.py).\n"
        "[metadata]\n"
        f'target_versions = ["{GAME_SHA}"]\n\n'
        + "\n".join(h.text() for h in ordered)
    )
    doc = tomllib.loads(text)
    if len(doc["hooks"]) != len(ordered):
        fail("the merged hook list does not read back")
    return text, len(ordered), duplicates


# ---------------------------------------------------------------------------------- constructors
def constructor_order(module: Path) -> list[str]:
    """The module's constructors in the order dyld runs them, by symbol name: the pointers in
    __mod_init_func (or the offsets in __init_offsets), read from the file and named by nm."""
    symbols = {}
    for line in subprocess.run(["nm", "-n", str(module)], capture_output=True, text=True, check=True).stdout.splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[int(fields[0], 16)] = fields[2]
    data = module.read_bytes()
    commands = subprocess.run(["otool", "-l", str(module)], capture_output=True, text=True, check=True).stdout
    order = []
    for block in commands.split("Section")[1:]:
        name = re.search(r"sectname (\S+)", block)
        if not name or name.group(1) not in ("__mod_init_func", "__init_offsets"):
            continue
        size = int(re.search(r"size (0x[0-9a-f]+)", block).group(1), 16)
        offset = int(re.search(r"offset (\d+)", block).group(1))
        width = 8 if name.group(1) == "__mod_init_func" else 4
        for at in range(offset, offset + size, width):
            value = int.from_bytes(data[at:at + width], "little")
            order.append(symbols.get(value, hex(value)))
    return order


def first(order: list[str], needle: str) -> int:
    return next((i for i, name in enumerate(order) if needle in name), -1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("widescreen", "stray", "layout", "notes", "notes-include", "controller", "sdl"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--no-map-notes", action="store_true")
    parser.add_argument("--no-controller", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    parts = [("K1WidescreenPatch", args.widescreen, FTD_FLAGS, ("*.cpp",)),
             ("K1StrayBugFixes", args.stray, FTD_FLAGS, ("*.cpp",)),
             ("kmrp-layout", args.layout, LAYOUT_FLAGS, ("*.cpp",))]
    if not args.no_map_notes:
        parts.append(("kmrp-map-notes", args.notes, [*LAYOUT_FLAGS, "-I", str(args.notes_include)], ("*.cpp",)))
    if not args.no_controller:
        parts.append(("kmrp-controller", args.controller, [*CONTROLLER_FLAGS, "-F", str(args.sdl)], ("*.cpp", "*.mm")))

    with tempfile.TemporaryDirectory(prefix="kmrp-patch-") as tmp:
        tmp = Path(tmp)
        (tmp / "objects").mkdir()
        (tmp / "binaries").mkdir()
        objects = []
        for part, directory, flags, patterns in parts:
            files = sources(directory, patterns)
            if not files:
                fail(f"{part}: no sources in {directory}")
            objects += compile_part(files, flags, tmp / "objects", part)
        module = tmp / "binaries" / "macos_x86_64.dylib"
        link = ["clang++", *LINK_FLAGS, *([] if args.no_controller else [*CONTROLLER_LINK, "-F", str(args.sdl)]),
                "-o", str(module), *map(str, objects)]
        result = subprocess.run(link, capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"the module does not link\n{result.stderr}")
        subprocess.run(["codesign", "--force", "--sign", "-", str(module)], check=True, capture_output=True)

        order = constructor_order(module)
        ftd, layout = first(order, "DylibInit"), first(order, "ApplyLayoutSupport")
        if ftd < 0 or layout < 0 or ftd > layout:
            fail(f"FTD's DylibInit must run before KMRP's ApplyLayoutSupport; the module runs {order}")

        hooks, count, duplicates = merge_hooks([(part, directory) for part, directory, _, _ in parts])
        (tmp / HOOKS_FILE).write_text(hooks)
        included = ", ".join(part for part, *_ in parts)
        (tmp / "manifest.toml").write_text(
            "[patch]\n"
            'id = "kmrp"\n'
            'name = "KMRP for macOS"\n'
            f'version = "{args.version}"\n'
            f'description = "KMRP for macOS as one patch: {included}. FTD\'s Widescreen Patch and Stray Bug '
            "Fixes (MIT) built from their source with KMRP's layout support and options linked in. It replaces "
            'a separate install of FTD\'s patches. Run through KMRP Installer, which adds the menu layouts."\n'
            'author = "FTD, RaymanGT, J, Vriff (Widescreen Patch); RaymanGT, FTD (Stray Bug Fixes); RaymanGT (KMRP)"\n'
            # It carries FTD's two patches, so KPM must not apply them beside it: the conflict
            # KMRP.kpatch declares on Windows with the KPM patches making KMRP's fixes (2026-10-01).
            'requires = []\n'
            'conflicts = ["k1widescreenpatch", "k1-stray-bug-fixes-patch"]\n\n'
            "[patch.supported_versions]\n"
            f'kotor1_steam_aspyr_macos = "{GAME_SHA}"\n')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("manifest.toml", HOOKS_FILE, "binaries/macos_x86_64.dylib"):
                z.write(tmp / name, name)
    print(f"{args.out.name}: {included}; {count} hooks ({duplicates} duplicates dropped); "
          f"{len(order)} constructors, FTD's DylibInit {ftd + 1}, KMRP's ApplyLayoutSupport {layout + 1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
